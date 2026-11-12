"""Layout sort worker: the pixel steps (needs numpy and Pillow; run by layout/run.py with LAYOUT_PYTHON).

usage: PYTHON -I layout/worker.py WORDS_JSON PDF OUT_DIR [--copy COPY_MD]

Reads the word boxes (layout/words.py), sorts the paper by the rules in layout/rules.py and writes
OUT_DIR/layout.json (every unit in reading order with its class, page box in PDF points and text),
OUT_DIR/layout.txt (the same as plain text), OUT_DIR/sorted.pdf (the pages with the frame, gutters and
numbered units drawn) and OUT_DIR/report.json (counts, checks, and with --copy a comparison).
Exit status 0, or 3 when a check fails (see report.json "checks").
"""
import collections, difflib, json, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rules as RL   # noqa: E402

DPI = 200; S = DPI / 150          # raster pixels per word-coordinate pixel
M = 10                            # frame margin around the largest main-text box, px at DPI
DRAW_DPI = 110
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
COLOURS = {'main header': (60, 60, 60), 'float': (0, 110, 0), 'alt main text': (230, 110, 0), 'references': (120, 40, 160), 'main text': (180, 0, 0), 'other': (150, 150, 150)}


def render(pdf, tmp):
    subprocess.run(['pdftoppm', '-r', str(DPI), '-gray', '-png', pdf, os.path.join(tmp, 'p')], check=True)
    out = {}
    for f in os.listdir(tmp):
        m = re.fullmatch(r'p-0*(\d+)\.png', f)
        if m: out[int(m.group(1))] = os.path.join(tmp, f)
    return out


def owner_map(words, H, W, rank, cuts=()):
    """Each pixel at most one owner: the segments of each font group, then the gaps between a group's
    own lines (filled only where that group lies above and below within 1 em)."""
    segs = RL.segments(words) if words else []
    gid = RL.groups(segs, cuts)
    ng = max(gid) + 1 if gid else 0
    gcls = [None] * ng
    for s, g in zip(segs, gid): gcls[g] = s['cls']
    own = np.full((H, W), -1, np.int32)
    for s, g in zip(segs, gid):
        x0, y0, x1, y1 = [int(round(v * S)) for v in s['box']]
        view = own[max(y0, 0):max(y1, y0 + 1), max(x0, 0):max(x1, x0 + 1)]; view[view < 0] = g
    gap = np.array([c[1] * DPI / 72 for c in gcls] or [0.0])
    up_o = np.full((H, W), -1, np.int32); up_d = np.zeros((H, W), np.int32)
    lo = np.full(W, -1, np.int32); ld = np.zeros(W, np.int32)
    for y in range(H):
        hit = own[y] >= 0; ld = np.where(hit, 0, ld + 1); lo = np.where(hit, own[y], lo); up_o[y] = lo; up_d[y] = ld
    lo = np.full(W, -1, np.int32); ld = np.zeros(W, np.int32); fill = np.zeros((H, W), bool)
    for y in range(H - 1, -1, -1):
        hit = own[y] >= 0; ld = np.where(hit, 0, ld + 1); lo = np.where(hit, own[y], lo)
        fill[y] = (~hit) & (lo >= 0) & (up_o[y] == lo) & (ld + up_d[y] <= gap[np.maximum(lo, 0)])
    own = np.where(fill, up_o, own)
    return own, [rank.get(c, 99) for c in gcls]


ACCENTS = set('~´¨`˜ˆ^¸˛˚˙') | {chr(c) for c in range(0x300, 0x370)}

def _run_lines(part):
    """Lines of one block of words: the boxer's runs, runs on the same line joined, lifted accents
    attached to the letter under them."""
    accents = [w for w in part if w['text'] and all(ch in ACCENTS for ch in w['text'])]
    rest = [w for w in part if not any(w is a for a in accents)]
    runs_ = collections.OrderedDict()
    for w in rest: runs_.setdefault(w.get('run'), []).append(w)
    lines = []
    for r, rw in runs_.items():
        cys = sorted((w['fb'][1] + w['fb'][3]) / 2 for w in rw); cy = cys[len(cys) // 2]; h = sorted(w['fb'][3] - w['fb'][1] for w in rw)[len(rw) // 2]
        same = next((l for l in lines if abs(l['cy'] - cy) < 0.5 * max(h, l['h'])), None)
        if same: same['w'] += rw
        else: lines.append(dict(cy=cy, h=h, w=list(rw)))
    for a in accents:
        ax = (a['fb'][0] + a['fb'][2]) / 2; ay = (a['fb'][1] + a['fb'][3]) / 2
        under = [l for l in lines if l['cy'] >= ay - 0.3 * l['h'] and any(w['fb'][0] - 2 <= ax <= w['fb'][2] + 2 for w in l['w'])]
        tgt = min(under, key=lambda l: l['cy'] - ay) if under else (min(lines, key=lambda l: abs(l['cy'] - ay)) if lines else None)
        if tgt: tgt['w'].append(a)
        else: lines.append(dict(cy=ay, h=1, w=[a]))
    return [sorted(l['w'], key=lambda w: w['fb'][0]) for l in sorted(lines, key=lambda l: l['cy'])]


def lines_of(ws, depth=0, columns=True):
    """Words into printed lines, in reading order. A unit is cut like a page: a white strip through its
    whole height (wider than SPLIT_EM, both sides at least 8 em) splits it into left and right; else a
    white band across it, wider than 1.5 line heights, splits it into upper and lower; each part is cut
    again (a page-1 header: title, authors, then the affiliation column and the abstract column side by
    side). In each part, lines follow the boxer's runs; lifted accents join the letter under them."""
    if not ws: return []
    hs = sorted(w['fb'][3] - w['fb'][1] for w in ws); em = max(hs[len(hs) // 2], 1)
    if depth < 8 and len(ws) > 3:
        x0 = int(min(w['fb'][0] for w in ws)); x1 = int(np.ceil(max(w['fb'][2] for w in ws)))
        cover = np.zeros(max(x1 - x0, 1), bool)
        for w in ws: cover[max(int(w['fb'][0]) - x0, 0):max(int(np.ceil(w['fb'][2])) - x0, 0)] = True
        gx = [(a + b) / 2 + x0 for a, b in RL.runs((~cover).tolist()) if b - a >= RL.SPLIT_EM * em and a >= 8 * em and len(cover) - b >= 8 * em] if columns else []
        for c in gx:   # a column split needs at least three lines on each side (an author line is not two columns)
            L_ = [w for w in ws if (w['fb'][0] + w['fb'][2]) / 2 < c]; R_ = [w for w in ws if (w['fb'][0] + w['fb'][2]) / 2 >= c]
            if len(_run_lines(L_)) >= 3 and len(_run_lines(R_)) >= 3:
                return lines_of(L_, depth + 1, columns) + lines_of(R_, depth + 1, columns)
        y0 = int(min(w['fb'][1] for w in ws)); y1 = int(np.ceil(max(w['fb'][3] for w in ws)))
        ycov = np.zeros(max(y1 - y0, 1), bool)
        for w in ws: ycov[max(int(w['fb'][1]) - y0, 0):max(int(np.ceil(w['fb'][3])) - y0, 0)] = True
        gy = [(a + b) / 2 + y0 for a, b in RL.runs((~ycov).tolist()) if b - a >= 1.5 * em and a > 0 and b < len(ycov)]
        if gy:
            cuts = [float('-inf')] + gy + [float('inf')]; out = []
            for k in range(len(cuts) - 1):
                out += lines_of([w for w in ws if cuts[k] <= (w['fb'][1] + w['fb'][3]) / 2 < cuts[k + 1]], depth + 1, columns)
            return out
    return _run_lines(ws)


def norm(tokens):
    out = []; carry = ''
    for t in tokens:
        if carry: t = carry + t; carry = ''
        if t.endswith('-') and len(t) > 1: carry = t[:-1]; continue
        t = re.sub(r'[^0-9a-z]', '', t.lower())
        if t: out.append(t)
    if carry: out.append(re.sub(r'[^0-9a-z]', '', carry.lower()))
    return out


def main():
    args = sys.argv[1:]; copy_md = None
    if '--copy' in args: i = args.index('--copy'); copy_md = args[i + 1]; del args[i:i + 2]
    words_json, pdf, out = args; os.makedirs(out, exist_ok=True)
    D = json.load(open(words_json)); P = D['pages']; pages = [p['page'] for p in P]; byn = {p['page']: p for p in P}
    R = dict(pdf=os.path.abspath(pdf), pages=len(P), flags=[], checks={})
    # a scanned paper is not for this method: its font sizes come from OCR, not from the typesetting
    scanned = [p['page'] for p in P if p.get('scanned')]
    if 2 * len(scanned) > len(P) or not any(p['words'] for p in P):
        R['flags'].append(f"scanned document ({len(scanned)} of {len(P)} pages are scans{'' if any(p['words'] for p in P) else ', no text layer'}): the font census does not apply; not sorted")
        R['scanned'] = True; R['references'] = dict(found=False); R['units'] = {}
        json.dump(R, open(os.path.join(out, 'report.json'), 'w'), indent=1); print(json.dumps(dict(flags=R['flags']))); return 4
    # the boxer's own floats and tables (rules 3-4) are large boxes: each is one float; its words take no
    # part in the font census or the font groups, and no gutter passes through it
    FB, PANELS = {}, {}
    bdir = os.path.join(os.path.dirname(os.path.abspath(words_json)), 'boxer')
    for n in pages:
        boxes = []
        try: d = json.load(open(os.path.join(bdir, f'page-{n:02d}.json')))
        except OSError: d = {}
        for t in (d.get('floats') or []) + (d.get('tables') or []):
            b = [float(v) for v in t['box_px']]
            if not any(all(abs(a - c) < 2 for a, c in zip(b, e)) for e in boxes): boxes.append(b)
        # a panel the boxer drew (a tinted or framed box: "Clinical Relevance", "How to cite this article")
        # holds float material, whatever its font, unless it is most of the page
        bx_ = d.get('region_box_px') or [0, 0, 1, 1]; parea = (bx_[2] - bx_[0]) * (bx_[3] - bx_[1])
        PANELS[n] = set()
        for rg in d.get('regions') or []:
            b = [float(v) for v in rg['box_px']]
            if rg.get('source') == 'panel' and (b[2] - b[0]) * (b[3] - b[1]) < 0.5 * parea and not any(all(abs(a - c) < 2 for a, c in zip(b, e)) for e in boxes):
                PANELS[n].add(len(boxes)); boxes.append(b)
        FB[n] = boxes
        for w in byn[n]['words']:
            cx, cy = (w['box'][0] + w['box'][2]) / 2, (w['box'][1] + w['box'][3]) / 2
            w['in_float'] = next((k for k, b in enumerate(boxes) if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]), None)
    R['boxer_floats'] = {n: len(FB[n]) for n in pages if FB[n]}
    free_words = [dict(p, words=[w for w in p['words'] if w['in_float'] is None]) for p in P]
    # census
    size, fonts = RL.main_class(free_words)
    RL.relabel(P, size, fonts)
    # a boxer box that reaches over running body text (three or more long lines of main text, word spaces
    # only) does not own those lines: they stay main text; a table's short cells and the float's own
    # lettering stay in the float
    released = 0
    em150 = size * 150 / 72
    LABELRE = re.compile(r'^(F\s?I\s?G\s?U\s?R\s?E|FIG|Fig(ure)?|T\s?A\s?B\s?L\s?E|Table|BOX|Box|Scheme|Chart)\.?\s*[A-Z]?\d', re.I)
    for p in P:
        byrun = collections.defaultdict(list)
        for w in p['words']:
            if w['in_float'] is not None: byrun[(w['in_float'], w['run'])].append(w)
        # a caption is a run that opens with a float label and the runs that follow it directly below
        caption = set()
        for k in {k for k, _ in byrun}:
            rs = sorted([(r, sorted(ws, key=lambda w: w['box'][0])) for (kk, r), ws in byrun.items() if kk == k], key=lambda t: t[1][0]['box'][1])
            for i, (r, ws) in enumerate(rs):
                if not LABELRE.match(' '.join(w['text'] for w in ws)) or (k, r) in caption: continue
                caption.add((k, r)); last = ws
                for r2, ws2 in rs[i + 1:]:
                    h = max(last[0]['box'][3] - last[0]['box'][1], 1)
                    if ws2[0]['box'][1] - max(w['box'][3] for w in last) <= 1.5 * h and abs(ws2[0]['box'][0] - ws[0]['box'][0]) <= 3 * h:
                        caption.add((k, r2)); last = ws2
                    elif ws2[0]['box'][1] > max(w['box'][3] for w in last) + 1.5 * h: break
        body = collections.defaultdict(list)
        for (k, run), ws in byrun.items():
            if (k, run) in caption: continue
            ms = sorted([w for w in ws if RL.cls(w)[0] == RL.MAIN], key=lambda w: w['box'][0])
            if not ms: continue
            pieces, cur = [], [ms[0]]
            for w in ms[1:]:
                if w['box'][0] - cur[-1]['box'][2] <= RL.SPLIT_EM * em150: cur.append(w)
                else: pieces.append(cur); cur = [w]
            pieces.append(cur)
            if any(pc[-1]['box'][2] - pc[0]['box'][0] >= 20 * em150 for pc in pieces): body[k].append(ws)
        for k, runs_ in body.items():
            if len(runs_) >= 3 and k not in PANELS[p['page']]:
                for ws in runs_:
                    for w in ws: w['in_float'] = None; released += 1
    R['words_released_from_boxer_boxes'] = released
    capruns = 0
    for p in P:
        byrun = collections.OrderedDict()
        for w in p['words']: byrun.setdefault(w['run'], []).append(w)
        for ws in byrun.values():
            ws = sorted(ws, key=lambda w: w['box'][0])
            spaced = re.match(r'^(F I G U R E|T A B L E) \d', ' '.join(w['text'] for w in ws[:7]))
            if spaced or RL.is_caption([(w['text'], w['orig_fonts'][0][0]) for w in ws[:2]], [w['orig_fonts'][0][0] for w in ws[2:]]):   # "Table 1 summarizes ..." stays a sentence
                for w in ws:
                    if RL.cls(w)[0] == RL.MAIN: w['fonts'] = w['orig_fonts']; w['caption_run'] = True
                capruns += 1
    R['caption_runs'] = capruns
    for p in P:
        for w in p['words']:
            if w['in_float'] is not None and RL.cls(w)[0] == RL.MAIN: w['fonts'] = w['orig_fonts']   # a table's cells are not main text
    chars = collections.Counter()
    for p in P:
        for w in p['words']:
            for f, s, m in w['fonts']: chars[(f, s)] += m
    T = sum(chars.values()); rank = {k: i + 1 for i, (k, _) in enumerate(chars.most_common())}
    R.update(main_size=size, main_fonts=fonts, main_share=round(100 * chars[(RL.MAIN, size)] / T, 1),
             census=[dict(font=f, size=s, chars=m, share=round(100 * m / T, 2)) for (f, s), m in chars.most_common(12)])
    tmp = tempfile.mkdtemp(prefix='layout-', dir=out)
    try:
        img = render(pdf, tmp)
        INK, OWN, RANKS = {}, {}, {}
        for n in pages:
            im = Image.open(img[n]).convert('L'); INK[n] = np.asarray(im) < 240
            OWN[n], RANKS[n] = owner_map([w for w in byn[n]['words'] if w['in_float'] is None], im.height, im.width, rank)
        # alignment: share of word boxes with ink under them
        hit = tot = 0
        for n in pages:
            H, W = INK[n].shape
            for w in byn[n]['words']:
                x0, y0, x1, y1 = [int(round(v * S)) for v in w['box']]; tot += 1
                if 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H and INK[n][y0:y1, x0:x1].any(): hit += 1
        R['checks']['words_on_ink'] = round(hit / max(tot, 1), 3)
        # frame
        mains = {}
        for n in pages:
            mw = [[v * S for v in w['box']] for w in byn[n]['words'] if RL.cls(w)[0] == RL.MAIN]
            if mw: mains[n] = RL.union(mw)
        best, B, moves, nofit = RL.frame_moves(mains)
        B = [int(np.floor(B[0])), int(np.floor(B[1])), int(np.ceil(B[2])), int(np.ceil(B[3]))]
        Bw, Bh = B[2] - B[0], B[3] - B[1]
        if nofit:
            R['flags'].append(f'the largest main-text box (page {best}) cannot hold the main text of pages {nofit}: frame enlarged to the widest and tallest')
            Bw = max(Bw, max(int(np.ceil(b[2] - b[0])) for b in mains.values())); Bh = max(Bh, max(int(np.ceil(b[3] - b[1])) for b in mains.values()))
            for n in nofit: moves[n] = (int(np.floor(mains[n][0])) - B[0], int(np.floor(mains[n][1])) - B[1])
        moves = RL.fill_moves(moves, pages)
        FW, FH = Bw + 2 * M + 1, Bh + 2 * M + 1; E = M + 4
        org = {n: (B[0] - M + moves[n][0], B[1] - M + moves[n][1]) for n in pages}     # frame origin on each page, px
        R.update(frame_page=best, frame_px=[FW, FH], moves={n: moves[n] for n in pages})
        def crop(arr, n, fillv):
            x0, y0 = org[n]; o = np.full((FH, FW), fillv, arr.dtype); H, W = arr.shape
            xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + FW, W), min(y0 + FH, H)
            if xb > xa and yb > ya: o[ya - y0:yb - y0, xa - x0:xb - x0] = arr[ya:yb, xa:xb]
            return o
        ink = {n: crop(INK[n], n, False) for n in pages}
        fbm, FBF = {}, {}
        for n in pages:   # boxer float boxes in frame pixels
            m = np.zeros((FH, FW), bool); FBF[n] = []
            for b in FB[n]:
                x0_, y0_, x1_, y1_ = [int(round(v * S)) for v in b]; x0_ -= org[n][0]; x1_ -= org[n][0]; y0_ -= org[n][1]; y1_ -= org[n][1]
                x0_, y0_, x1_, y1_ = max(x0_, 0), max(y0_, 0), min(x1_, FW), min(y1_, FH)
                if x1_ > x0_ and y1_ > y0_: m[y0_:y1_, x0_:x1_] = True; FBF[n].append([x0_, y0_, x1_, y1_])
                else: FBF[n].append(None)
            fbm[n] = m
        own = {n: crop(OWN[n], n, -1) for n in pages}
        # gutters: white through 90% of the main-text rows, on a majority of the pages with main text
        votes = np.zeros(FW, int); texted = []; share_rows = {}; free_by_page = {}; white_share = {}; votes_page = {}
        for n in pages:
            rk = np.array(RANKS[n] + [0]); blocked = (own[n] >= 0) | ink[n]   # finding the gap: ink and text groups (rule 7: large boxes limit its marking, below)
            mrows = ((own[n] >= 0) & (rk[own[n]] == 1)).any(axis=1); mrows[:E] = False; mrows[FH - E:] = False
            if mrows.sum() < 40: continue
            share_rows[n] = round(float(mrows.mean()), 2)
            texted.append(n); white_share[n] = (~blocked[mrows]).mean(axis=0); free_by_page[n] = white_share[n] >= 0.9
            wm = ~blocked[mrows]; cur = np.zeros(FW, int); best = np.zeros(FW, int)
            for row in wm: cur = (cur + 1) * row; best = np.maximum(best, cur)
            # a page votes for a strip white through 90% of its main-text rows, or through one unbroken run of
            # at least half of them (the two-column part under a full-width abstract or above a full-width table)
            votes_page[n] = free_by_page[n] | (best >= 0.5 * len(wm))
        # pages that are mostly figures do not vote: a page votes when its main text fills at least 40% of
        # the frame's height (all pages with main text vote when fewer than two pages qualify)
        voters = [n for n in texted if share_rows[n] >= 0.4]
        if len(voters) < 2: voters = texted
        for n in voters: votes += votes_page[n].astype(int)
        min_w = max(4, int(0.15 * size * DPI / 72))      # a strip white through the text rows of most pages is a gutter, however narrow
        gutters = RL.recurring_gutters(votes.tolist(), len(voters) // 2 + 1, min_w, E, FW) if voters else []
        R['gutter_voters'] = dict(pages=voters, main_rows_share=share_rows)
        prof = []   # strongest white strips (for the report): votes and width
        for v in sorted(set(votes.tolist()), reverse=True)[:4]:
            prof += [dict(x=[a, b], votes=v) for a, b in RL.runs((votes >= v).tolist()) if b - a >= 6 and a > E and b < FW - E]
        R['gutter_profile'] = dict(need=len(voters) // 2 + 1 if voters else 0, strips=prof[:8])
        near = [p_ for p_ in prof if p_['votes'] < (len(voters) // 2 + 1) and p_['votes'] * 3 >= len(voters) and p_['x'][1] - p_['x'][0] >= min_w]
        if near and not gutters: R['flags'].append(f"no gutter on a majority of pages; the strongest white strip (x {near[0]['x']}) is seen on {near[0]['votes']} of {len(voters)} pages and is not used")
        R.update(gutters=gutters, gutter_votes={f'{a}-{b}': int(votes[a:b].min()) for a, b in gutters}, pages_with_main_text=len(texted))
        # each page's gutters: the paper's gutters that are white on this page, and the page's own white
        # strips through its main-text rows (a page set in other columns, such as page 1) with main text on
        # both sides; a page without main text keeps the paper's gutters
        PG, em_px = {}, size * DPI / 72
        for n in pages:
            if n not in free_by_page: PG[n] = list(gutters); continue
            fr = free_by_page[n]; rk = np.array(RANKS[n] + [0]); mainpx = (own[n] >= 0) & (rk[own[n]] == 1)
            mrows = mainpx.any(axis=1); colmain = mainpx.any(axis=0)
            # a paper gutter is dropped on a page only where main text runs through it (half its main rows);
            # a figure or box across it does not count
            lh = 1.2 * size * DPI / 72
            def runs_through(a, b):   # main text in the gutter's middle half (text ending at its edge does not count)
                mid = mainpx[:, a + (b - a) // 4:b - (b - a) // 4].any(axis=1)
                return mid[mrows].mean() >= 0.5 or mid.sum() >= 3 * lh   # half the main rows, or three lines of a wide block
            keep = [(a, b) for a, b in gutters if not runs_through(a, b)]
            if len(keep) == len(gutters) and gutters: PG[n] = keep; continue
            for a, b in RL.runs(fr.tolist()):
                if b - a < max(min_w, 0.5 * em_px) or a <= E or b >= FW - E: continue
                if any(not (b <= ga or a >= gb) for ga, gb in keep): continue
                if colmain[:a].any() and colmain[b:].any(): keep.append((a, b))
            PG[n] = sorted(keep)
        R['page_gutters'] = {n: PG[n] for n in pages if PG[n] != gutters}
        for n in pages:   # rebuild the font groups so that none crosses a gutter of its page
            if PG[n]:
                cuts = [((a + b) / 2 + org[n][0]) / S for a, b in PG[n]]
                OWN[n], RANKS[n] = owner_map([w for w in byn[n]['words'] if w['in_float'] is None], INK[n].shape[0], INK[n].shape[1], rank, cuts)
                own[n] = crop(OWN[n], n, -1)
        UNITS, outside_lines, R['pages_detail'], marks = [], [], {}, {}
        for n in pages:
            gutters_n = PG[n]; bands = RL.column_bands(gutters_n, FW)
            o = own[n]; rk = np.array(RANKS[n] + [0]); main = (o >= 0) & (rk[o] == 1); blocked = (o >= 0) | ink[n] | fbm[n]; ng = len(RANKS[n])
            # gutter marks: rows where the gutter is white at least 60% of its width, runs of 40 px or more
            marks[n] = []
            for a, b in gutters_n:
                keep = [False] * FH
                for y in range(E, FH - E):
                    sp = RL.runs((~blocked[y, a:b]).tolist())
                    keep[y] = bool(sp) and max(e - s for s, e in sp) >= 0.6 * (b - a)
                marks[n].append([(s, e) for s, e in RL.runs(keep) if e - s >= 40])
            full = bool(gutters_n) and all(len(m) == 1 and m[0][1] - m[0][0] >= FH - 2 * E - 1 for m in marks[n])
            ys, xs = np.nonzero(o >= 0); ids = o[ys, xs]; k = max(ng, 1)
            bx0 = np.full(k, FW); by0 = np.full(k, FH); bx1 = np.full(k, -1); by1 = np.full(k, -1)
            if len(ids): np.minimum.at(bx0, ids, xs); np.minimum.at(by0, ids, ys); np.maximum.at(bx1, ids, xs + 1); np.maximum.at(by1, ids, ys + 1)
            def bbox(i): return None if bx1[i] < 0 else [int(bx0[i]), int(by0[i]), int(bx1[i]), int(by1[i])]
            main_ids = [i for i in range(ng) if RANKS[n][i] == 1 and bbox(i)]
            if n == pages[0] and main_ids:   # page 1: short main-font lines above the body of their column belong to the header (rule 10)
                hdr = []
                for lo_, hi_ in bands:
                    inb = [i for i in main_ids if lo_ - 2 <= (bbox(i)[0] + bbox(i)[2]) / 2 <= hi_ + 2]
                    if not inb: continue
                    lh_ = 1.2 * size * DPI / 72
                    paras = [i for i in inb if bbox(i)[3] - bbox(i)[1] >= 2.5 * lh_]          # three lines or more
                    if not paras: continue
                    first = min(paras, key=lambda i: bbox(i)[1])                                 # the column's first full paragraph
                    hdr += [i for i in inb if bbox(i)[3] <= bbox(first)[1] and bbox(i)[3] - bbox(i)[1] <= 2.2 * size * DPI / 72
                            and bbox(first)[1] - bbox(i)[3] > 1.5 * lh_]                       # a heading directly on top of it stays
                if hdr:
                    main_ids = [i for i in main_ids if i not in hdr]; RANKS[n] = [r_ if i not in hdr else 98 for i, r_ in enumerate(RANKS[n])]
                    rk = np.array(RANKS[n] + [0]); main = (o >= 0) & (rk[o] == 1)
            colboxes, rest = [], []
            if not full:
                for kb, (lo_, hi_) in enumerate(bands):
                    mine = [bbox(i) for i in main_ids if bbox(i)[0] >= lo_ - 2 and bbox(i)[2] <= hi_ + 2]
                    if not mine: continue
                    r = RL.union(mine)
                    if gutters_n:
                        if kb > 0: r[0] = lo_
                        if kb < len(bands) - 1: r[2] = hi_
                    for _ in range(50):   # an edge may not cut a group: take the group in
                        inside = o[r[1]:r[3], r[0]:r[2]]
                        cut = [i for i in set(np.unique(inside[inside >= 0]).tolist()) if bbox(i)[0] < r[0] or bbox(i)[1] < r[1] or bbox(i)[2] > r[2] or bbox(i)[3] > r[3]]
                        if not cut: break
                        for i in cut: r = RL.union([r, bbox(i)])
                    colboxes.append(r)
                colmask = np.zeros((FH, FW), bool)
                for r in colboxes: colmask[r[1]:r[3], r[0]:r[2]] = True
                content = blocked & ~colmask & ~fbm[n] & ~main; content[:E] = False; content[FH - E:] = False; content[:, :E] = False; content[:, FW - E:] = False
                sig = [tuple(r[1] <= y < r[3] for r in colboxes) for y in range(FH)]
                y = E; bl = []
                while y < FH - E:
                    z = y
                    while z < FH - E and sig[z] == sig[y]: z += 1
                    bl.append((y, z, sig[y])); y = z
                for ya, yb, sg in bl:
                    occ = [False] * FW
                    for r, on in zip(colboxes, sg):
                        if on:
                            for x in range(r[0], r[2]): occ[x] = True
                    for xa0, xb0 in RL.runs([not v for v in occ]):
                        # material outside the column boxes stays within its column, unless it runs
                        # through the gutter itself (a figure or a header across the page)
                        cuts_x = [xa0] + [x for a_, b_ in gutters_n if xa0 < a_ and b_ < xb0 and not content[ya:yb, a_:b_].any() for x in (a_, b_)] + [xb0]
                        for xa, xb in zip(cuts_x[::2], cuts_x[1::2]):
                            cy, cx = np.nonzero(content[ya:yb, xa:xb])
                            if len(cy) >= 50: rest.append([xa + int(cx.min()), ya + int(cy.min()), xa + int(cx.max()) + 1, ya + int(cy.max()) + 1])
                changed = True
                while changed:
                    changed = False
                    for i in range(len(rest)):
                        for j in range(i + 1, len(rest)):
                            a, b = rest[i], rest[j]; u = RL.union([a, b])
                            def across(r): return [g for g in gutters_n if r[0] < g[0] and r[2] > g[1]]
                            if set(map(tuple, across(u))) - set(map(tuple, across(a) + across(b))): continue   # a join may not cross a gutter
                            if min(a[2], b[2]) - max(a[0], b[0]) > 0 and max(a[1], b[1]) - min(a[3], b[3]) <= 30 and not colmask[u[1]:u[3], u[0]:u[2]].any():
                                rest[i] = u; rest.pop(j); changed = True; break
                        if changed: break
            units = [dict(page=n, kind='main header' if n == pages[0] else 'float', box=r) for r in rest]
            units += [dict(page=n, kind=('main header' if (k in PANELS[n] and n == pages[0]) else 'float'), box=b, boxer_float=k, panel=k in PANELS[n]) for k, b in enumerate(FBF[n]) if b]
            taken = np.zeros((FH, FW), bool)
            for r in rest: taken[r[1]:r[3], r[0]:r[2]] = True
            # non-main blocks inside the columns; inline pieces (at most two lines, main text beside) stay
            blocks, inline = [], 0; LINE = 2.2 * size * DPI / 72
            for i in range(ng):
                if RANKS[n][i] == 1 or not bbox(i): continue
                r = bbox(i)
                if taken[r[1]:r[3], r[0]:r[2]].any(): continue
                ba, bb = bands[RL.band_of((r[0] + r[2]) / 2, bands)]          # its column
                beside = main[r[1]:r[3], ba:r[0]].any() or main[r[1]:r[3], r[2]:bb].any()   # main text on its own line in its column (a bullet, a symbol, a run-in word)
                if r[3] - r[1] <= LINE and beside: inline += 1; continue
                blocks.append(r)
            changed = True
            while changed:
                changed = False
                for i in range(len(blocks)):
                    for j in range(i + 1, len(blocks)):
                        a, b = blocks[i], blocks[j]; u = RL.union([a, b])
                        same = RL.band_of((a[0] + a[2]) / 2, bands) == RL.band_of((b[0] + b[2]) / 2, bands) == RL.band_of(u[0], bands) == RL.band_of(max(u[2] - 1, 0), bands)
                        if same and max(a[0], b[0]) - min(a[2], b[2]) <= 40 and max(a[1], b[1]) - min(a[3], b[3]) <= 40 and not main[u[1]:u[3], u[0]:u[2]].any():
                            blocks[i] = u; blocks.pop(j); changed = True; break
                    if changed: break
            units += [dict(page=n, kind='non-main text', box=r) for r in blocks if (r[2] - r[0]) * (r[3] - r[1]) >= 3000]
            for u in units: taken[u['box'][1]:u['box'][3], u['box'][0]:u['box'][2]] = True
            # pictures: ink outside every group and every box, in 8-px cells, at least 40 px each way
            pic = ink[n] & (o < 0) & ~taken & ~fbm[n]
            for a, b in gutters_n: pic[:, a:b] = False
            cs = 8; gh, gw = FH // cs, FW // cs; cell = pic[:gh * cs, :gw * cs].reshape(gh, cs, gw, cs).any(axis=(1, 3)); seen = np.zeros_like(cell)
            for sy, sx in zip(*np.nonzero(cell)):
                if seen[sy, sx]: continue
                st = [(sy, sx)]; seen[sy, sx] = True; pts = []
                while st:
                    a, b = st.pop(); pts.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u_, v_ = a + da, b + db
                        if 0 <= u_ < gh and 0 <= v_ < gw and cell[u_, v_] and not seen[u_, v_]: seen[u_, v_] = True; st.append((u_, v_))
                ya, xa = min(q[0] for q in pts) * cs, min(q[1] for q in pts) * cs; yb, xb = (max(q[0] for q in pts) + 1) * cs, (max(q[1] for q in pts) + 1) * cs
                if yb - ya >= 40 and xb - xa >= 40: units.append(dict(page=n, kind='float', box=[int(xa), int(ya), int(xb), int(yb)], picture=True))
            for gi in main_ids: units.append(dict(page=n, kind='main text', box=bbox(gi), g=gi))
            # every word to exactly one unit, or outside the frame
            for u in units: u['words'] = []
            unassigned = 0
            for w in byn[n]['words']:
                fb = [w['box'][0] * S - org[n][0], w['box'][1] * S - org[n][1], w['box'][2] * S - org[n][0], w['box'][3] * S - org[n][1]]
                w['fb'] = fb; cx, cy = (fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2
                if not (0 <= cx < FW and 0 <= cy < FH):
                    band = 'top' if cy < 0 else 'bottom' if cy >= FH else 'left' if cx < 0 else 'right'
                    w['band'] = band; outside_lines.append((n, w)); continue
                if w['in_float'] is not None:
                    hitb = [u for u in units if u.get('boxer_float') == w['in_float']]
                    if hitb: hitb[0]['words'].append(w); continue
                g = int(o[int(cy), int(cx)])
                # a main-text word is main text wherever it sits (the user's rule): its own group first
                hitb = [u for u in units if u['kind'] == 'main text' and u['g'] == g and RL.cls(w)[0] == RL.MAIN]
                if hitb: hitb[0]['words'].append(w); continue
                hitb = [u for u in units if u['kind'] != 'main text' and u['box'][0] <= cx <= u['box'][2] and u['box'][1] <= cy <= u['box'][3]]
                if hitb: hitb[0]['words'].append(w); continue
                hitb = [u for u in units if u['kind'] == 'main text' and u['box'][0] - 25 <= cx <= u['box'][2] + 25 and u['box'][1] - 25 <= cy <= u['box'][3] + 25]
                if hitb: min(hitb, key=lambda u: (u['box'][2] - u['box'][0]) * (u['box'][3] - u['box'][1]))['words'].append(w); continue
                # an inline piece (bullet, symbol, run-in word) joins the main-text unit on its line in its column
                col = RL.band_of(cx, bands)
                hitb = [u for u in units if u['kind'] == 'main text' and u['box'][1] <= cy <= u['box'][3] and RL.band_of((u['box'][0] + u['box'][2]) / 2, bands) == col]
                if hitb: min(hitb, key=lambda u: min(abs(cx - u['box'][0]), abs(cx - u['box'][2])))['words'].append(w); continue
                hitb = [u for u in units if u['box'][0] - 25 <= cx <= u['box'][2] + 25 and u['box'][1] - 25 <= cy <= u['box'][3] + 25]
                if hitb: hitb[0]['words'].append(w); continue
                unassigned += 1; units.append(dict(page=n, kind='non-main text', box=[int(fb[0]), int(fb[1]), int(np.ceil(fb[2])), int(np.ceil(fb[3]))], words=[w], stray=True))
            units = [u for u in units if u['words'] or u.get('picture') or u.get('boxer_float') is not None]
            for u in sorted([u for u in units if u['kind'] == 'main text' and 0 < len(u['words']) <= 3], key=lambda u: u['box'][0]):
                cy_ = (u['box'][1] + u['box'][3]) / 2; em_ = size * DPI / 72
                bu = RL.band_of((u['box'][0] + u['box'][2]) / 2, bands)
                host = [v for v in units if v is not u and v['kind'] == 'main text' and len(v['words']) > 3 and v['box'][1] <= cy_ <= v['box'][3]
                        and max(v['box'][0] - u['box'][2], u['box'][0] - v['box'][2]) <= 2 * em_ and RL.band_of((v['box'][0] + v['box'][2]) / 2, bands) == bu]   # same column only
                if host:
                    h_ = host[0]; h_['words'] += u['words']; u['words'] = []
                    h_['box'] = RL.union([h_['box'], u['box']])
            units = [u for u in units if u['words'] or u.get('picture') or u.get('boxer_float') is not None]
            for u in units:   # a unit's box covers every word it holds (words joined by nearness included)
                if u['words']: u['box'] = [int(min([u['box'][0]] + [w['fb'][0] for w in u['words']])), int(min([u['box'][1]] + [w['fb'][1] for w in u['words']])),
                                           int(np.ceil(max([u['box'][2]] + [w['fb'][2] for w in u['words']]))), int(np.ceil(max([u['box'][3]] + [w['fb'][3] for w in u['words']])))]
            for u in units:   # a text float's box is its words' box (a stray mark does not stretch it)
                if u['words'] and u['kind'] in ('non-main text', 'float', 'main header') and u.get('boxer_float') is None and not u.get('picture'):
                    u['box'] = [int(min(w['fb'][0] for w in u['words'])), int(min(w['fb'][1] for w in u['words'])), int(np.ceil(max(w['fb'][2] for w in u['words']))), int(np.ceil(max(w['fb'][3] for w in u['words'])))]
            frames = [u['box'] for u in units if u.get('picture') and (u['box'][2] - u['box'][0]) * (u['box'][3] - u['box'][1]) < 0.5 * FW * FH]
            for u in units:   # body-font text inside a frame drawn as lines (a "How to cite" box) is float material
                if u['kind'] == 'main text' and u['words'] and any(f[0] - 4 <= u['box'][0] and u['box'][2] <= f[2] + 4 and f[1] - 4 <= u['box'][1] and u['box'][3] <= f[3] + 4 for f in frames):
                    u['kind'] = 'non-main text'; u['framed'] = True; u['panel'] = True   # a framed box is a panel: never references
            for u in units:   # a caption set in the body font belongs to its float
                if u['kind'] != 'main text' or not u['words']: continue
                ls = lines_of(u['words']); fw = [(x['text'], x['orig_fonts'][0][0]) for x in ls[0][:2]]
                if RL.is_caption(fw, [x['orig_fonts'][0][0] for l in ls for x in l[2:] if l]): u['kind'] = 'non-main text'; u['caption'] = True
            # two columns joined: a main-text unit with text on both sides of a gutter but none of its own
            # text in the gutter strip along most of its height
            crossing = 0
            for u in units:
                if u['kind'] != 'main text': continue
                for a_, b_ in gutters_n:
                    if not (u['box'][0] < a_ and u['box'][2] > b_): continue
                    strip = (o[u['box'][1]:u['box'][3], a_:b_] == u['g']).any(axis=1)
                    if strip.mean() < 0.2: crossing += 1; u['joins_columns'] = True
            ordered = RL.reading_order(units, gutters_n, FW); assert len(ordered) == len(units)
            UNITS += ordered
            R['pages_detail'][n] = dict(full_gutters=full, columns=len(colboxes), outside_columns=len(rest), non_main=len(blocks), inline=inline,
                                        stray_words=unassigned, main_units_crossing_a_gutter=crossing)
        # outside the frame: repeated lines are other (furniture); the rest is page-1 header or a float
        lines = collections.defaultdict(list)
        for n, w in outside_lines: lines[(n, w['band'], round((w['fb'][1] + w['fb'][3]) / 2 / 12))].append(w)
        keys = [(n, band, collections.Counter(RL.cls(w) for w in ws).most_common(1)[0][0]) for (n, band, _), ws in lines.items()]
        furniture = RL.recurring_outside(keys, len(pages))
        extra = collections.defaultdict(list); other_words = 0
        for ((n, band, _), ws), (_, _, c) in zip(lines.items(), keys):
            if (band, c) in furniture: other_words += len(ws); [w.__setitem__('other', True) for w in ws]
            else: extra[n] += ws
        for n, ws in extra.items():
            u = dict(page=n, kind='main header' if n == pages[0] else 'float', box=[int(min(w['fb'][0] for w in ws)), int(min(w['fb'][1] for w in ws)),
                     int(np.ceil(max(w['fb'][2] for w in ws))), int(np.ceil(max(w['fb'][3] for w in ws)))], words=ws, outside_frame=True)
            if n != pages[0]: R['flags'].append(f'page {n}: {len(ws)} words outside the frame are not repeated furniture; kept as a float')
            first = next(i for i, x in enumerate(UNITS) if x['page'] >= n) if any(x['page'] >= n for x in UNITS) else len(UNITS)
            if n == pages[0]: UNITS.insert(first, u)
            else:
                last = max([i for i, x in enumerate(UNITS) if x['page'] == n], default=first - 1); UNITS.insert(last + 1, u)
        # a block (not main text) repeated on many pages at the frame's edge zone is furniture: other
        cand = [u for u in UNITS if u['kind'] != 'main text' and u['words']]
        rep = RL.repeated_blocks([(u['page'], ' '.join(x['text'] for x in u['words']), u['box']) for u in cand], len(pages))
        for g in rep:
            for u in cand:
                if (u['page'], u['box']) in [(p_, b_) for p_, b_ in g['members']]: u['kind'] = 'other'; u['repeated'] = True
        # references
        # a text block holding two columns of its own (a page set in other columns than the body, such as a
        # reference page) is split at a white strip through its whole height, both sides real columns;
        # the boxer's tables and figures are not split
        em_c = size * DPI / 72; split_units = []
        for u in UNITS:
            if u['kind'] not in ('non-main text', 'float') or u.get('picture') or u.get('boxer_float') is not None or len(u['words']) < 10: split_units.append(u); continue
            x0, x1 = int(min(w['fb'][0] for w in u['words'])), int(np.ceil(max(w['fb'][2] for w in u['words'])))
            cover = np.zeros(max(x1 - x0, 1), bool)
            for w in u['words']: cover[max(int(w['fb'][0]) - x0, 0):max(int(np.ceil(w['fb'][2])) - x0, 0)] = True
            gaps_ = [(a + x0, b + x0) for a, b in RL.runs((~cover).tolist()) if b - a >= RL.SPLIT_EM * em_c and a >= 8 * em_c and len(cover) - b >= 8 * em_c]
            if not gaps_: split_units.append(u); continue
            cutsx = [x0] + [(a + b) / 2 for a, b in gaps_] + [x1 + 1]
            for k in range(len(cutsx) - 1):
                ws = [w for w in u['words'] if cutsx[k] <= (w['fb'][0] + w['fb'][2]) / 2 < cutsx[k + 1]]
                if ws: split_units.append(dict(page=u['page'], kind=u['kind'], words=ws, box=[int(min(w['fb'][0] for w in ws)), int(min(w['fb'][1] for w in ws)),
                                                                                            int(np.ceil(max(w['fb'][2] for w in ws))), int(np.ceil(max(w['fb'][3] for w in ws)))]))
        UNITS[:] = split_units
        for u in UNITS: u['lines'] = [(l[0]['fb'][0], ' '.join(w['text'] for w in l)) for l in lines_of(u['words'], columns=u.get('boxer_float') is None or u.get('panel'))]; u['nwords'] = len(u['words'])
        ref_ix, refinfo = RL.find_references([dict(page=u['page'], kind=u['kind'], picture=u.get('picture'), panel=u.get('panel'), lines=u['lines'], words=u['nwords']) for u in UNITS], pages[int(len(pages) * 0.4)])   # references sit in the later part of a paper (in an author manuscript, tables and figures follow them)
        def first_line(j): return (UNITS[j]['lines'][0][1][:60] if UNITS[j]['lines'] else '') if j is not None else None
        refinfo['passed_over'] = [first_line(j) for j in refinfo['passed_over']]; refinfo['ended_at'] = first_line(refinfo['ended_at'])   # as text, before any split moves indexes
        if refinfo.get('split'):   # the heading is a line inside a block: the lines above it stay a float
            si, sk = refinfo['split']; u = UNITS[si]; ls = lines_of(u['words'])
            top = [w for l in ls[:sk] for w in l]; bot = [w for l in ls[sk:] for w in l]
            def mk(ws, kind): return dict(page=u['page'], kind=kind, words=ws, box=[int(min(w['fb'][0] for w in ws)), int(min(w['fb'][1] for w in ws)), int(np.ceil(max(w['fb'][2] for w in ws))), int(np.ceil(max(w['fb'][3] for w in ws)))],
                                          lines=[(l[0]['fb'][0], ' '.join(w['text'] for w in l)) for l in lines_of(ws)], nwords=len(ws))
            UNITS[si:si + 1] = [mk(top, 'float'), mk(bot, 'non-main text')]
            ref_ix = [j + 1 if j >= si else j for j in ref_ix]
            refinfo['notes'] = {(j + 1 if j >= si else j): k for j, k in refinfo.get('notes', {}).items()}
            if refinfo.get('heading_unit') is not None and refinfo['heading_unit'] >= si: refinfo['heading_unit'] += 1
        notes_u = {id(UNITS[i]): k for i, k in (refinfo.get('notes') or {}).items()}
        hu = UNITS[refinfo['heading_unit']] if refinfo.get('heading_unit') is not None else None   # before any split moves indexes
        for i, u in enumerate(UNITS):
            if i in ref_ix: u['kind'] = 'references'
            elif u['kind'] == 'non-main text': u['kind'] = 'float'
        # a note under the last entry of a reference block (a correspondence address) is split off as a float
        out_u = []
        for u in UNITS:
            k = notes_u.get(id(u))
            if u['kind'] == 'references' and k:
                ls = lines_of(u['words']); top = [w for l in ls[:k] for w in l]; bot = [w for l in ls[k:] for w in l]
                if top and bot:
                    for ws, kind in ((top, 'references'), (bot, 'float')):
                        out_u.append(dict(page=u['page'], kind=kind, words=ws, box=[int(min(w['fb'][0] for w in ws)), int(min(w['fb'][1] for w in ws)), int(np.ceil(max(w['fb'][2] for w in ws))), int(np.ceil(max(w['fb'][3] for w in ws)))],
                                          lines=[(l[0]['fb'][0], ' '.join(w['text'] for w in l)) for l in lines_of(ws)], nwords=len(ws)))
                    continue
            out_u.append(u)
        UNITS[:] = out_u
        # a reference block may hold two columns of its own (reference pages can be set in other columns
        # than the body): a white strip through the block's whole height, wider than SPLIT_EM, splits it
        split_units = []
        for u in UNITS:
            if u['kind'] != 'references' or len(u['words']) < 10: split_units.append(u); continue
            em = size * DPI / 72; x0, x1 = int(min(w['fb'][0] for w in u['words'])), int(np.ceil(max(w['fb'][2] for w in u['words'])))
            cover = np.zeros(max(x1 - x0, 1), bool)
            for w in u['words']: cover[max(int(w['fb'][0]) - x0, 0):max(int(np.ceil(w['fb'][2])) - x0, 0)] = True
            gaps_ = [(a + x0, b + x0) for a, b in RL.runs((~cover).tolist()) if b - a >= RL.SPLIT_EM * em and a >= 8 * em and len(cover) - b >= 8 * em]   # both sides real columns (a column of entry numbers is not)
            if not gaps_: split_units.append(u); continue
            cutsx = [x0] + [(a + b) / 2 for a, b in gaps_] + [x1 + 1]
            for k in range(len(cutsx) - 1):
                ws = [w for w in u['words'] if cutsx[k] <= (w['fb'][0] + w['fb'][2]) / 2 < cutsx[k + 1]]
                if ws: split_units.append(dict(page=u['page'], kind='references', words=ws, split_from=True,
                                              box=[int(min(w['fb'][0] for w in ws)), int(min(w['fb'][1] for w in ws)), int(np.ceil(max(w['fb'][2] for w in ws))), int(np.ceil(max(w['fb'][3] for w in ws)))]))
        UNITS[:] = split_units
        for u in UNITS:
            if u.get('split_from'): u['lines'] = [(l[0]['fb'][0], ' '.join(w['text'] for w in l)) for l in lines_of(u['words'])]; u['nwords'] = len(u['words'])
        # last step of the floats: a text float of one to five words is not a float (a stray label, a
        # heading or a symbol line): it is relabelled alt main text (the user's rule, 2026-10-25)
        for u in UNITS:
            if RL.alt_main(u['kind'], u.get('picture') or u.get('boxer_float') is not None, len(u['words'])): u['kind'] = 'alt main text'   # a boxer float (figure, table) stays a float
        refinfo['pages'] = sorted({u['page'] for u in UNITS if u['kind'] == 'references'})
        R['references'] = refinfo
        # checks
        total = sum(len(p['words']) for p in P); placed = sum(len(u['words']) for u in UNITS)
        main_out = sum(1 for n, w in outside_lines if RL.cls(w)[0] == RL.MAIN)
        R['checks'].update(words=total, words_in_units=placed, words_other=other_words, every_word_once=(placed + other_words == total),
                           stray_words=sum(d['stray_words'] for d in R['pages_detail'].values()), main_words_outside_frame=main_out,
                           main_units_crossing_a_gutter=sum(d['main_units_crossing_a_gutter'] for d in R['pages_detail'].values()),
                           word_overlaps=sum(p.get('overlaps_left', 0) for p in P), runs_unspelled=sum(p.get('runs_unspelled', 0) for p in P))
        fail = [k for k, bad in (('every_word_once', not R['checks']['every_word_once']), ('main_words_outside_frame', main_out > 0),
                                 ('main_units_crossing_a_gutter', R['checks']['main_units_crossing_a_gutter'] > 0),
                                 ('word_overlaps', R['checks']['word_overlaps'] > 0), ('runs_unspelled', R['checks']['runs_unspelled'] > 0), ('words_on_ink', R['checks']['words_on_ink'] < 0.7)) if bad]
        R['checks']['failed'] = fail
        R['units'] = dict(collections.Counter(u['kind'] for u in UNITS))
        # outputs
        pt = 72 / DPI
        def box_pt(u, n): return [round((u['box'][0] + org[n][0]) * pt, 2), round((u['box'][1] + org[n][1]) * pt, 2), round((u['box'][2] + org[n][0]) * pt, 2), round((u['box'][3] + org[n][1]) * pt, 2)]
        LJ = []
        for k, u in enumerate(UNITS, 1):
            u['order'] = k
            LJ.append(dict(order=k, page=u['page'], kind=u['kind'], box_pt=box_pt(u, u['page']), picture=bool(u.get('picture')), outside_frame=bool(u.get('outside_frame')),
                           text='\n'.join(t for _, t in u['lines']),
                           words=[[w['text'], [round(v * 72 / 150, 2) for v in w['box']], w.get('chars', [])] for l in lines_of(u['words']) for w in l]))
        json.dump(dict(pdf=R['pdf'], main_size=size, main_fonts=fonts, frame_pt=[round(FW * pt, 2), round(FH * pt, 2)],
                       frame_origin_pt={n: [round(org[n][0] * pt, 2), round(org[n][1] * pt, 2)] for n in pages},
                       gutters_pt=[[round(a * pt, 2), round(b * pt, 2)] for a, b in gutters], units=LJ), open(os.path.join(out, 'layout.json'), 'w'), indent=1, ensure_ascii=False)
        with open(os.path.join(out, 'layout.txt'), 'w') as f:
            for u in LJ: f.write(f"=== {u['order']} | page {u['page']} | {u['kind']}{' | picture' if u['picture'] else ''}\n{u['text']}\n\n")
        # drawing: full pages; the frame, gutter marks, other words grey, numbered units
        font = ImageFont.truetype(FONT, 11); kd = DRAW_DPI / DPI; L = []
        for n in pages:
            im = Image.open(img[n]).convert('RGB'); im = im.resize((int(im.width * kd), int(im.height * kd))); d = ImageDraw.Draw(im, 'RGBA'); ox, oy = org[n]
            for (a, b), mk in zip(PG[n], marks[n]):
                for s, e in mk: d.rectangle([(a + ox) * kd, (s + oy) * kd, (b + ox) * kd, (e + oy) * kd], fill=(255, 215, 0, 90))
            for m, w in outside_lines:
                if m == n and w.get('other'): d.rectangle([w['box'][0] * S * kd, w['box'][1] * S * kd, w['box'][2] * S * kd, w['box'][3] * S * kd], fill=(150, 150, 150, 110))
            d.rectangle([ox * kd, oy * kd, (ox + FW) * kd, (oy + FH) * kd], outline=(0, 0, 0, 255), width=3)
            for u in UNITS:
                if u['page'] != n: continue
                c = COLOURS[u['kind']]; r = [(u['box'][0] + ox) * kd - 2, (u['box'][1] + oy) * kd - 2, (u['box'][2] + ox) * kd + 2, (u['box'][3] + oy) * kd + 2]
                d.rectangle(r, outline=c + (255,), width=2 if u['kind'] == 'main text' else 3)
                t = f"{u['order']} {u['kind']}" if u['kind'] != 'main text' else str(u['order']); tw = d.textlength(t, font=font)
                ly = r[1] - 15 if r[1] >= 15 else r[3] + 1   # the label sits just outside the box, never over its words
                d.rectangle([r[0], ly, r[0] + tw + 6, ly + 14], fill=(255, 255, 255, 200), outline=c + (255,)); d.text((r[0] + 3, ly), t, fill=c + (255,), font=font)
            L.append(im)
        L[0].save(os.path.join(out, 'sorted.pdf'), save_all=True, append_images=L[1:], resolution=DRAW_DPI)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # comparison with a copy (optional): the main text must appear in the copy in the same order
    if copy_md:
        cp = open(copy_md).read().splitlines()
        end = next((i for i, l in enumerate(cp) if re.match(r'^#+ .*(references|bibliography|literature cited)', l, re.I)), None)
        stop = next((i for i, l in enumerate(cp) if l.startswith(('## Unpaired floats', '## Places the program'))), len(cp))
        body = [re.sub(r'^#+ ', '', l) for l in cp[:end if end is not None else stop] if l.strip() and not l.startswith(('|', '**Fig', '**Table', '**Box', '<!--', '---', '> ['))]
        ctok = norm(' '.join(body).split()); mtok = norm(' '.join(u['text'] for u in LJ if u['kind'] == 'main text').split())
        bag = {k: collections.Counter(norm(' '.join(u['text'] for u in LJ if u['kind'] == k).split())) for k in ('main header', 'float', 'references')}
        cg = {tuple(ctok[i:i + 5]) for i in range(len(ctok) - 4)}
        sm = difflib.SequenceMatcher(None, mtok, ctok, autojunk=False); same = sum(b.size for b in sm.get_matching_blocks())
        problems, copy_only = [], collections.Counter()
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ('delete', 'replace') and i2 - i1 >= 8:
                g = {tuple(mtok[i:i + 5]) for i in range(i1, i2 - 4)}; inc = len(g & cg) / max(len(g), 1)
                problems.append(dict(words=i2 - i1, where='elsewhere in the copy (order differs)' if inc >= 0.6 else 'not in the copy', text=' '.join(mtok[i1:i1 + 20])))
            if tag in ('insert', 'replace') and j2 - j1 >= 8:
                g = collections.Counter(ctok[j1:j2]); best_k = max(bag, key=lambda k: sum((g & bag[k]).values()))
                frac = sum((g & bag[best_k]).values()) / (j2 - j1)
                copy_only[best_k if frac >= 0.6 else 'nowhere in the layout'] += j2 - j1
                if frac < 0.6: problems.append(dict(words=j2 - j1, where='copy text nowhere in the layout', text=' '.join(ctok[j1:j1 + 20])))
        refs_c = [l for l in cp[(end or 0) + 1:stop] if l.startswith('- ')] if end is not None else []
        rtok = norm(' '.join(u['text'] for u in LJ if u['kind'] == 'references').split()); rc = norm(' '.join(l[2:] for l in refs_c).split())
        rsame = sum(b.size for b in difflib.SequenceMatcher(None, rtok, rc, autojunk=False).get_matching_blocks()) if rc else 0
        R['compare'] = dict(copy=os.path.abspath(copy_md), main_words=len(mtok), main_in_copy_order=round(100 * same / max(len(mtok), 1), 1),
                            copy_text_in_other_classes=dict(copy_only), copy_references=len(refs_c),
                            reference_words_in_order=round(100 * rsame / len(rc), 1) if rc else None, problems=problems)
    json.dump(R, open(os.path.join(out, 'report.json'), 'w'), indent=1, default=str, ensure_ascii=False)
    print(json.dumps(dict(main=f"{size} pt, {R['main_share']}%", gutters=len(R['gutters']), units=R['units'], references=f"{R['references']['found']} ({R['references']['entries']} entries, {R['references']['style']})",
                          compare={k: v for k, v in R.get('compare', {}).items() if k in ('main_in_copy_order', 'reference_words_in_order')}, checks_failed=R['checks']['failed'], flags=R['flags']), ensure_ascii=False))
    return 3 if R['checks']['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
