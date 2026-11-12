"""Check stage, step 1 (CPU, standard library): the copy's paragraphs, where each one was
printed, and the narrow questions the page-reading model is asked.

Ported from the local-checker trial (trials/local-checker/scripts/prep.py, som.py,
run_bplus.py, lc_common.py; design "B+ with (ii) veto", Qwen3.6-27B-FP8, 2026-10-25).

Paragraphs: blank-line separated blocks of copy.md (fenced ``` blocks kept whole; page
marker lines "<!-- end of page N -->" / "<!-- page N -->" are blocks of their own). Each
paragraph is labelled with the page segment its markers put it in.

Block regions (where a paragraph was printed), two sources:
- the copy's native trace (copy.trace.json beside copy.md, schema copy-trace/2): the
  printed lines whose runs the paragraph's units claim, with their 110-dpi boxes. A
  paragraph without a traced unit gets no region (it is generated text: notes, labels).
- without a trace (older copies): the trial's monotone word alignment of the paragraph's
  words against `pdftotext -bbox-layout` words (line-end hyphens merged), giving line
  boxes on the page(s) it matches.
Line boxes are merged into column-coherent rectangles (cluster_lines). A paragraph whose
lines lie on two pages is a two-page block ("multi"); such blocks are never moved.

Questions (answered by worker.py):
- (ii) per page, every boxed paragraph: "what kind of printed text is block k?";
- (i) per page, the boxed paragraphs the model reads as running text: "is the numbering
  the reading order?" (asked by the worker after (ii));
- (iii) joins: adjacent paragraphs, the first ending mid-sentence and the second starting
  in lower case: "does box 2 continue the sentence of box 1?";
- (iv) headings: short title-like first lines of body paragraphs that are not Markdown
  headings yet: "is this line printed as a heading?" and then "main section or sub?".
Nothing here reads or writes the copy's words; it only describes them.
"""
import json
import os
import re
import subprocess
from collections import defaultdict
from xml.etree import ElementTree as ET

DPI = 120  # page images for the model (the trial's resolution)
TRACE_DPI = 110  # copy.trace.json box_110dpi
MARK_END = re.compile(r'^<!-- end of page (\d+) -->\s*$')
MARK_START = re.compile(r'^<!-- page (\d+) -->\s*$')
MARK = re.compile(r'^<!-- (?:end of )?page \d+ -->$')
UNCERTAINTY_TITLE = 'Places the program is not sure of'


# ------------------------------------------------------------------ text helpers
def is_content(r):
    t = r['text'].strip()
    return bool(t) and not MARK.match(t)


def ends_open(t):
    """Paragraph ends mid-sentence (no terminal punctuation) or with a line-end hyphen."""
    t = t.rstrip().rstrip('*').rstrip()
    if not t:
        return False
    if t.endswith('-') and not t.endswith(' -'):
        return True
    return not re.search(r'[.?!:;)\]"”’\']$', t)


def starts_lower(t):
    t = re.sub(r'^\s*(?:#{1,6}|>|-)\s+', '', t.lstrip()).lstrip('*')
    return bool(t) and t[0].islower()


def snippet(t, n_head=12, n_tail=8):
    ws = t.replace('\n', ' ').split()
    if len(ws) <= n_head + n_tail + 2:
        return ' '.join(ws)
    return ' '.join(ws[:n_head]) + ' ... ' + ' '.join(ws[-n_tail:])


def norm_words(s):
    s = s.replace('**', ' ')
    s = re.sub(r'^\s*(#{1,6}|>|-)\s+', ' ', s, flags=re.M)
    out, carry = [], ''
    for t in s.split():
        w = re.sub(r'[^0-9a-z]', '', t.lower())
        if t.endswith('-') and len(t) > 1 and not t.endswith('--'):
            carry += w
            continue
        w = carry + w
        carry = ''
        if w:
            out.append(w)
    if carry:
        out.append(carry)
    return out


# ------------------------------------------------------------------ paragraphs and segments
def paragraphs(text):
    """Blank-line separated paragraphs; fenced ``` blocks kept whole. Returns (start, end, text)."""
    out = []
    pos = 0
    cur_start = None
    in_fence = False
    cur_end = 0
    for ln in text.splitlines(keepends=True):
        s = ln.strip()
        if not in_fence and (MARK_END.match(s) or MARK_START.match(s)):
            if cur_start is not None:
                out.append((cur_start, cur_end))
                cur_start = None
            out.append((pos, pos + len(ln.rstrip('\r\n'))))
            pos += len(ln)
            continue
        if s.startswith('```'):
            in_fence = not in_fence
        if not s and not in_fence:
            if cur_start is not None:
                out.append((cur_start, cur_end))
                cur_start = None
        else:
            if cur_start is None:
                cur_start = pos
            cur_end = pos + len(ln.rstrip('\r\n'))
        pos += len(ln)
    if cur_start is not None:
        out.append((cur_start, cur_end))
    return [(a, b, text[a:b]) for a, b in out]


def segment_pages(paras):
    """Label each paragraph with the page segment it sits in, from the copy markers."""
    ends = [i for i, p in enumerate(paras) if MARK_END.match(p[2])]
    lab = [None] * len(paras)
    if ends:
        nxt = None
        last = int(MARK_END.match(paras[ends[-1]][2]).group(1))
        for i in range(len(paras) - 1, -1, -1):
            m = MARK_END.match(paras[i][2])
            if m:
                nxt = int(m.group(1))
                lab[i] = nxt
            elif nxt is None:
                lab[i] = last  # tail after the last end marker (end matter)
            else:
                lab[i] = nxt
    else:
        cur = 1
        for i, p in enumerate(paras):
            m = MARK_START.match(p[2])
            if m:
                cur = int(m.group(1))
            lab[i] = cur
    return lab


# ------------------------------------------------------------------ regions: pdftotext alignment
def bbox_words(pdf):
    out = subprocess.run(['pdftotext', '-bbox-layout', pdf, '-'], capture_output=True, text=True).stdout
    out = re.sub(r'<!DOCTYPE[^>]*>', '', out)
    out = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', out)
    out = out.replace('xmlns="http://www.w3.org/1999/xhtml"', '')
    root = ET.fromstring(out)
    pages = []
    for pg in root.iter('page'):
        W, H = float(pg.get('width')), float(pg.get('height'))
        words = []
        lid = 0
        for line in pg.iter('line'):
            lid += 1
            lb = [float(line.get(k)) for k in ('xMin', 'yMin', 'xMax', 'yMax')]
            for w in line.iter('word'):
                raw = w.text or ''
                t = re.sub(r'[^0-9a-z]', '', raw.lower())
                if words and words[-1].get('open'):
                    prev = words[-1]
                    prev['w'] += t
                    prev['open'] = False
                    prev['line2'] = lid
                    prev['lbox2'] = lb
                    continue
                if t:
                    words.append({'w': t, 'line': lid, 'lbox': lb,
                                  'box': [float(w.get(k)) for k in ('xMin', 'yMin', 'xMax', 'yMax')],
                                  'open': raw.endswith('-') and len(raw) > 1})
        pages.append({'W': W, 'H': H, 'words': words})
    return pages


def cluster_lines(lboxes):
    """Merge line boxes into column-coherent rectangles."""
    rects = []
    for b in sorted(lboxes, key=lambda b: (b[1], b[0])):
        placed = False
        for r in rects:
            ov = min(r[2], b[2]) - max(r[0], b[0])
            h = b[3] - b[1]
            if ov > 0.4 * min(r[2] - r[0], b[2] - b[0]) and b[1] - r[3] < 1.6 * max(h, 6) and b[1] >= r[1] - 2:
                r[0], r[1], r[2], r[3] = min(r[0], b[0]), min(r[1], b[1]), max(r[2], b[2]), max(r[3], b[3])
                placed = True
                break
        if not placed:
            rects.append(list(b))
    return rects


def map_paragraphs(paras, labels, pages):
    """For each paragraph, find source pages and matched line boxes (monotone word alignment)."""
    from difflib import SequenceMatcher
    streams = [[w['w'] for w in pg['words']] for pg in pages]
    line_words = []
    for pg in pages:
        lw = defaultdict(list)
        for i, w in enumerate(pg['words']):
            lw[w['line']].append(i)
        line_words.append(lw)
    res = []
    for k, (a, b, t) in enumerate(paras):
        ws = norm_words(t)
        info = {'pages': {}, 'n_words': len(ws)}
        if not ws or MARK_END.match(t.strip()) or MARK_START.match(t.strip()):
            res.append(info)
            continue
        seg = labels[k]
        hits = {}
        acov = {}
        if len(ws) <= 4:
            cands = []
            for pi, lw in enumerate(line_words):
                for ln, idx in lw.items():
                    if [streams[pi][i] for i in idx] == ws:
                        cands.append((abs(pi + 1 - (seg or pi + 1)), pi, idx))
            if not cands:  # contiguous run anywhere, near the segment page
                for pi, st in enumerate(streams):
                    for i in range(len(st) - len(ws) + 1):
                        if st[i:i + len(ws)] == ws:
                            cands.append((abs(pi + 1 - (seg or pi + 1)) + 0.5, pi, list(range(i, i + len(ws)))))
            if cands:
                cands.sort(key=lambda c: c[0])
                _, pi, idx = cands[0]
                hits[pi] = list(idx)
        else:
            for pi, st in enumerate(streams):
                sm = SequenceMatcher(None, ws, st, autojunk=False)
                got, cov = [], []
                for blk in sm.get_matching_blocks():
                    if blk.size >= 4:
                        got.extend(range(blk.b, blk.b + blk.size))
                        cov.extend(range(blk.a, blk.a + blk.size))
                if len(got) >= max(4, 0.12 * len(ws)):
                    hits[pi] = got
                    acov[pi] = (min(cov), max(cov))
        for pi, idx in hits.items():
            pg = pages[pi]
            by_line = defaultdict(list)
            for wi in idx:
                by_line[pg['words'][wi]['line']].append(pg['words'][wi]['box'])
            if len(ws) <= 12:
                lb = [[min(x[0] for x in v), min(x[1] for x in v), max(x[2] for x in v), max(x[3] for x in v)]
                      for v in by_line.values()]
            else:
                lbs = {}
                for wi in idx:
                    w = pg['words'][wi]
                    lbs[w['line']] = w['lbox']
                    if 'line2' in w:
                        lbs[w['line2']] = w['lbox2']
                lb = list(lbs.values())
            info['pages'][pi + 1] = {'share': round(len(idx) / len(ws), 3), 'votes': len(idx),
                                     'cov': acov.get(pi, (0, len(ws) - 1)),
                                     'rects_pt': cluster_lines(lb)}
        if info['pages']:
            info['source_page'] = max(info['pages'], key=lambda p: (info['pages'][p]['votes'], -abs(p - (seg or p))))
            src = info['source_page']
            n = len(ws)
            info['on_pages'] = [src]
            for q, v in info['pages'].items():
                if q == src or n <= 12 or v['votes'] < 8:
                    continue
                a0, a1 = v['cov']
                dense = v['votes'] >= 0.8 * (a1 - a0 + 1)
                touches = a0 <= 2 or a1 >= n - 3
                if dense and touches and abs(q - src) == 1:
                    info['on_pages'].append(q)
        res.append(info)
    return res


# ------------------------------------------------------------------ regions: native trace
def load_trace(paper_dir, text):
    """The copy's native trace, when it belongs to this copy.md (same SHA-256 and units in place)."""
    import hashlib
    path = os.path.join(paper_dir, 'copy.trace.json')
    if not os.path.isfile(path):
        return None
    try:
        data = json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not str(data.get('schema', '')).startswith('copy-trace/2'):
        return None
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != (data.get('copy') or {}).get('sha256'):
        return None
    return data


def map_paragraphs_trace(paras, labels, trace):
    """Regions from the trace: the printed lines claimed by each paragraph's units."""
    unit_lines = defaultdict(list)
    for line in trace['lines']:
        for d in line.get('units') or []:
            unit_lines[d['unit_id']].append(line)
    units = sorted((u for u in trace['units'] if u.get('status') != 'span_unresolved' and u['span'][1] > u['span'][0]),
                   key=lambda u: u['span'][0])
    k = 1.0 * 72.0 / TRACE_DPI
    res = []
    ui = 0
    for idx, (a, b, t) in enumerate(paras):
        ws = norm_words(t)
        info = {'pages': {}, 'n_words': len(ws)}
        if not ws or MARK.match(t.strip()):
            res.append(info)
            continue
        while ui < len(units) and units[ui]['span'][1] <= a:
            ui += 1
        by_page = defaultdict(dict)
        j = ui
        while j < len(units) and units[j]['span'][0] < b:
            for line in unit_lines.get(units[j]['id'], []):
                bx = line.get('box_110dpi')
                if bx:
                    by_page[line['page']][line['id']] = [v * k for v in bx]
            j += 1
        seg = labels[idx]
        for p, lines in by_page.items():
            info['pages'][p] = {'share': None, 'votes': len(lines), 'rects_pt': cluster_lines(list(lines.values()))}
        if info['pages']:
            src = max(info['pages'], key=lambda p: (info['pages'][p]['votes'], -abs(p - (seg or p))))
            info['source_page'] = src
            info['on_pages'] = [src] + sorted(p for p in info['pages'] if p != src)
        res.append(info)
    return res


# ------------------------------------------------------------------ blocks and candidates
def page_blocks(paras, page):
    """Set-of-marks blocks of one page: the paragraphs printed there, numbered in copy order."""
    out = []
    for r in paras:
        if not is_content(r) or not r.get('source_page'):
            continue
        pr = r['pages'].get(str(page)) or r['pages'].get(page)
        if not pr or not pr['rects_pt']:
            continue
        if page not in r['on_pages']:
            continue
        out.append({'para': r['id'], 'rects_pt': pr['rects_pt'], 'text': r['text'], 'multi': len(r['on_pages']) > 1})
    for i, b in enumerate(out):
        b['num'] = i + 1
    return out


def head_candidates(paras):
    """Short title-like lines that are not yet headings (after the first Markdown heading of the body)."""
    first_body = None
    tail = None
    for r in paras:
        if UNCERTAINTY_TITLE in r['text']:
            tail = r['id']
            break
    for r in paras:
        if not is_content(r):
            continue
        if (re.match(r'^## ', r['text']) and 'Article information' not in r['text'] and UNCERTAINTY_TITLE not in r['text']) \
                or len(r['text'].split()) >= 40:
            first_body = r['id']
            break
    out = []
    for r in paras:
        if not is_content(r) or (first_body is not None and r['id'] < first_body) or not r.get('source_page') \
                or (tail is not None and r['id'] >= tail):
            continue
        t = r['text']
        if t.startswith('```') or t.startswith('[') or t.startswith('**'):
            continue
        lines = t.split('\n')
        ln = lines[0]
        core = re.sub(r'^\s*(?:(?:>|-)\s+)*', '', ln).strip()
        if not core or ln.lstrip().startswith('#'):
            continue
        words = core.split()
        if not (1 <= len(words) <= 10) or not core[0].isupper() or re.search(r'[.,;:]$', core):
            continue
        if len(lines) == 1 and len(t) > 120:
            continue
        if len(lines) > 1:
            nxt = re.sub(r'^\s*(?:(?:>|-)\s+)*', '', lines[1]).strip()
            if not nxt or not nxt[0].isupper() or len(core) > 0.7 * max(len(l) for l in lines[1:]):
                continue
        if re.search(r'\d{2,}', core) and len(words) <= 2:
            continue
        out.append({'para': r['id'], 'line': ln, 'core': core, 'page': r['source_page']})
    return out


def join_candidates(paras):
    cont = [r for r in paras if is_content(r)]
    out = []
    for a, b in zip(cont, cont[1:]):
        ta, tb = a['text'], b['text']
        if ta.startswith('```') or tb.startswith('```') or ta.lstrip().startswith('#') or tb.lstrip().startswith('#'):
            continue
        if not (a.get('source_page') and b.get('source_page')):
            continue
        if ends_open(ta.split('\n')[-1]) and starts_lower(tb):
            out.append({'a': a['id'], 'b': b['id'], 'pa': a['source_page'], 'pb': b['source_page']})
    return out


# ------------------------------------------------------------------ one paper
def render_pages(pdf, work):
    os.makedirs(work, exist_ok=True)
    if not any(re.match(r'p-\d+\.png$', f) for f in os.listdir(work)):
        subprocess.run(['pdftoppm', '-r', str(DPI), '-png', pdf, os.path.join(work, 'p')], check=True)
    imgs = sorted(f for f in os.listdir(work) if re.match(r'p-\d+\.png$', f))
    return [os.path.join(work, f) for f in imgs]


def page_sizes(pdf):
    """Page sizes in points (pdfinfo), for drawing boxes on the rendered images."""
    out = subprocess.run(['pdfinfo', '-f', '1', '-l', '100000', pdf], capture_output=True, text=True).stdout
    sizes = {}
    for m in re.finditer(r'^Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+) pts', out, re.M):
        sizes[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    rot = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r'^Page\s+(\d+) rot:\s+(\d+)', out, re.M)}
    for n, r in rot.items():
        if n in sizes and r % 180 == 90:
            sizes[n] = (sizes[n][1], sizes[n][0])
    return sizes


def prepare(paper_dir, pdf, work, copy_name='copy.md', use_trace=True, render=True):
    """Everything the worker needs for one paper (spec), plus the paragraph records for the ops builder.

    render=False skips the page images (the model will not run: saved answers or code checks only)."""
    text = open(os.path.join(paper_dir, copy_name), encoding='utf-8').read()
    paras = paragraphs(text)
    labels = segment_pages(paras)
    trace = load_trace(paper_dir, text) if use_trace else None
    sizes = page_sizes(pdf)
    images = render_pages(pdf, work) if render else [None] * len(sizes)
    if trace is not None:
        maps = map_paragraphs_trace(paras, labels, trace)
        pages = [{'page': i + 1, 'image': img, 'W_pt': sizes.get(i + 1, (None, None))[0],
                  'H_pt': sizes.get(i + 1, (None, None))[1]} for i, img in enumerate(images)]
        region_source = 'trace'
    else:
        bw = bbox_words(pdf)
        maps = map_paragraphs(paras, labels, bw)
        pages = [{'page': i + 1, 'image': images[i] if i < len(images) else None, 'W_pt': pg['W'], 'H_pt': pg['H']}
                 for i, pg in enumerate(bw)]
        region_source = 'pdftotext'
    recs = []
    for k, ((a, b, t), lab, m) in enumerate(zip(paras, labels, maps)):
        recs.append({'id': k, 'start': a, 'end': b, 'segment_page': lab, 'text': t,
                     'source_page': m.get('source_page'), 'on_pages': m.get('on_pages', []),
                     'pages': {str(p): v for p, v in m['pages'].items()}, 'n_words': m['n_words']})
    blocks = {}
    for pg in pages:
        bl = page_blocks(recs, pg['page'])
        if bl:
            blocks[pg['page']] = [{'num': b['num'], 'para': b['para'], 'rects_pt': b['rects_pt'], 'multi': b['multi'],
                                   'snippet': snippet(b['text']), 'order_snippet': snippet(b['text'], 8, 5)} for b in bl]
    byid = {r['id']: r for r in recs}
    joins = []
    for c in join_candidates(recs):
        A, B = byid[c['a']], byid[c['b']]
        joins.append(dict(c, rects_a=A['pages'][str(c['pa'])]['rects_pt'], rects_b=B['pages'][str(c['pb'])]['rects_pt'],
                          tail_a=' '.join(A['text'].replace('\n', ' ').split()[-10:]),
                          head_b=' '.join(B['text'].replace('\n', ' ').split()[:10])))
    heads = head_candidates(recs)
    spec = {'paper_dir': os.path.abspath(paper_dir), 'pdf': os.path.abspath(pdf), 'region_source': region_source,
            'pages': pages, 'blocks': {str(k): v for k, v in blocks.items()}, 'joins': joins, 'heads': heads}
    return text, recs, spec
