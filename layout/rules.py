"""Layout sort: the decisions that need no pixels (pure Python, tested by tools/test_layout.py).

The method (the user's rules, worked out on AI11, 2026-10-25):
  words      one box per white-space group of characters (the boxer's rule-1 reading layer), no overlaps
  census     characters by font and size; main text = the most common size, with every letter font set
             at that size (regular, italic, bold of the body face)
  groups     neighbouring words of one font+size form a group; a group never crosses a gutter
  frame      the largest page's main-text box, same size on every page, moved per page only as far as
             needed so that no main-text word is cut; outside it is "other" (running heads, page
             numbers, footers) unless it is not repeated on other pages (then page 1: main header,
             later pages: float, flagged)
  gutters    strips of x that stay white through the main-text rows of a majority of the pages
  columns    a page where every gutter runs full height keeps its gutters; on other pages one box per
             column holds the main text; material outside the column boxes is main header (page 1)
             or float
  inside     non-main blocks inside the columns (inline pieces excepted) and pictures
  order      the page is cut into bands by units that cross a gutter; in a band, column by column,
             each top down
  references a "References" line (or similar) that is the first line of a non-main block or the line
             just before one, in the second half of the paper; blocks after it whose entries read
             like a standard citation style; every other non-main block is a float
"""
import re
import collections

# -- runs of true values -------------------------------------------------------------------------------
def runs(mask):
    """[(start, end)] of consecutive true items, end exclusive."""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None: start = i
        if not v and start is not None: out.append((start, i)); start = None
    if start is not None: out.append((start, len(mask)))
    return out

def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]

# -- census --------------------------------------------------------------------------------------------
MAIN = 'main text'

def main_class(pages, size_tol=0.05, letter_share=0.6):
    """The main size and the fonts merged into main text: every font at the most common size whose
    characters are mostly Latin letters (symbol fonts at that size stay apart)."""
    chars = collections.Counter(); letters = collections.Counter(); total = collections.Counter()
    for p in pages:
        for w in p['words']:
            for f, s, m in w['fonts']: chars[(f, s)] += m
            if len(w['fonts']) == 1:
                f = w['fonts'][0][0]
                letters[f] += sum(ch.isalpha() and ord(ch) < 0x250 for ch in w['text']); total[f] += len(w['text'])
    if not chars: return None, []
    (_, size), _ = chars.most_common(1)[0]
    fonts = sorted({f for (f, s) in chars if abs(s - size) <= size_tol and total[f] and letters[f] / total[f] >= letter_share})
    return size, fonts

def main_angle(pages):
    """The reading angle of most characters (text set at another angle, such as a margin line, is never main text)."""
    c = collections.Counter()
    for p in pages:
        for w in p['words']: c[w.get('angle', 0)] += len(w['text'])
    return c.most_common(1)[0][0] if c else 0

def relabel(pages, size, fonts, size_tol=0.05):
    """Rewrite each word's font list with the main faces merged into one class (only for words at the
    main reading angle)."""
    angle = main_angle(pages)
    for p in pages:
        for w in p['words']:
            w.setdefault('orig_fonts', [list(f) for f in w['fonts']])
            k = collections.Counter()
            for f, s, m in w['fonts']:
                k[(MAIN, size) if (abs(s - size) <= size_tol and f in fonts and w.get('angle', 0) == angle) else (f, s)] += m
            w['fonts'] = [[a, b, m] for (a, b), m in k.most_common()]

def cls(w): return (w['fonts'][0][0], w['fonts'][0][1])

# -- groups --------------------------------------------------------------------------------------------
SPLIT_EM = 0.9      # a gap wider than this inside a line is not a word space (a gutter, a table gap)

def segments(words):
    """Line pieces of one font+size: consecutive words of one run with the same class and a gap of at
    most SPLIT_EM between them."""
    byrun = collections.OrderedDict()
    for w in words: byrun.setdefault(w['run'], []).append(w)
    segs = []
    for ws in byrun.values():
        cur = [ws[0]]
        for w in ws[1:]:
            em = cls(w)[1] * 150 / 72
            if cls(w) == cls(cur[-1]) and w['box'][0] - cur[-1]['box'][2] <= SPLIT_EM * em: cur.append(w)
            else: segs.append(cur); cur = [w]
        segs.append(cur)
    return [dict(cls=cls(s[0]), box=union([w['box'] for w in s]), words=s) for s in segs]

def link(a, b, size, cuts=()):
    """Do two segments of one class belong to one group? Same line: gap below SPLIT_EM. Next line:
    sideways overlap and a vertical gap below 1 em. Never across a gutter (cuts: x positions)."""
    em = size * 150 / 72
    ca, cb = (a[0] + a[2]) / 2, (b[0] + b[2]) / 2
    if any(min(ca, cb) < c < max(ca, cb) for c in cuts): return False
    vo = min(a[3], b[3]) - max(a[1], b[1]); h = min(a[3] - a[1], b[3] - b[1])
    gx = max(b[0] - a[2], a[0] - b[2]); gy = max(b[1] - a[3], a[1] - b[3])
    if vo > 0.5 * h: return gx < SPLIT_EM * em
    return gx < 0 and gy < em

def groups(segs, cuts=()):
    """Union-find over segments; returns a group id per segment."""
    parent = list(range(len(segs)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    order = sorted(range(len(segs)), key=lambda i: segs[i]['box'][1])
    for ai, i in enumerate(order):
        a = segs[i]['box']; em = segs[i]['cls'][1] * 150 / 72
        for j in order[ai + 1:]:
            b = segs[j]['box']
            if b[1] > a[3] + em: break
            if segs[j]['cls'] == segs[i]['cls'] and link(a, b, segs[i]['cls'][1], cuts): parent[find(i)] = find(j)
    ids, out = {}, []
    for i in range(len(segs)):
        r = find(i); out.append(ids.setdefault(r, len(ids)))
    return out

# -- frame ---------------------------------------------------------------------------------------------
def least_move(lo, hi):
    """The whole-number move closest to 0 within [lo, hi], or None when the range is empty."""
    import math
    lo, hi = math.ceil(lo), math.floor(hi)
    if lo > hi: return None
    return 0 if lo <= 0 <= hi else (lo if lo > 0 else hi)

def frame_moves(main_boxes, tol=4):
    """main_boxes: {page: [x0, y0, x1, y1]} of main text. The largest box (by area) is the frame; each
    page moves it the least so that its main text is inside (tol px of rounding allowed). Pages with no
    main text take the most common move of pages of the same parity. Returns (frame, moves, nofit)."""
    area = {n: (b[2] - b[0]) * (b[3] - b[1]) for n, b in main_boxes.items()}
    best = max(area, key=lambda n: (area[n], -n)); B = list(main_boxes[best])
    moves, nofit = {}, []
    for n, b in main_boxes.items():
        dx = least_move(b[2] - B[2] - tol, b[0] - B[0] + tol); dy = least_move(b[3] - B[3] - tol, b[1] - B[1] + tol)
        if dx is None or dy is None: nofit.append(n)
        moves[n] = (dx or 0, dy or 0)
    return best, B, moves, nofit

def fill_moves(moves, all_pages):
    out = dict(moves)
    for n in all_pages:
        if n not in out:
            same = [moves[m] for m in moves if m % 2 == n % 2]
            out[n] = collections.Counter(same).most_common(1)[0][0] if same else (0, 0)
    return out

# -- gutters -------------------------------------------------------------------------------------------
def recurring_gutters(votes, need, min_width, edge, width, join=4):
    """x strips free on at least `need` pages, at least min_width wide, not touching the edges; strips
    closer than `join` px are one gutter (a hairline inside a gutter splits it)."""
    rs = runs([v >= need for v in votes]); merged = []
    for a, b in rs:
        if merged and a - merged[-1][1] < join: merged[-1] = (merged[-1][0], b)
        else: merged.append((a, b))
    return [(a, b) for a, b in merged if b - a >= min_width and a > edge and b < width - edge]

# -- reading order -------------------------------------------------------------------------------------
def band_of(x, bands):
    for i, (a, b) in enumerate(bands):
        if a <= x < b: return i
    return len(bands) - 1 if x >= bands[-1][1] else 0

def column_bands(gutters, width):
    if not gutters: return [(0, width)]
    return [(0, gutters[0][0])] + [(gutters[i][1], gutters[i + 1][0]) for i in range(len(gutters) - 1)] + [(gutters[-1][1], width)]

def reading_order(units, gutters, width):
    """Cut order (the user's rule: left column down, then the next column). First, a white line across
    the whole region below which there is no main text splits it (a section break: references or floats
    under every column, read after the text above). Then a gutter that no unit crosses splits the region
    into left and right, read in that order; otherwise white lines across the whole region split it into
    slabs, read top down; each part is cut again. A unit that spans two of three columns therefore orders
    only the columns it spans. units: dicts with 'box' (and 'kind')."""
    bands = column_bands(gutters, width)
    def cx(u): return (u['box'][0] + u['box'][2]) / 2
    def slabs_of(us):
        slabs, cur, bottom = [], [], float('-inf')
        for u in sorted(us, key=lambda u: (u['box'][1], u['box'][0])):
            if cur and u['box'][1] >= bottom: slabs.append(cur); cur = []
            cur.append(u); bottom = max(bottom, u['box'][3])
        slabs.append(cur)
        return slabs
    def cut(us):
        if len(us) <= 1: return list(us)
        # a section break across the whole region: below a white line there is no main text at all
        # (references or floats under every column); the part above is read first
        sl = slabs_of(us)
        for k in range(1, len(sl)):
            top = [u for s_ in sl[:k] for u in s_]; bot = [u for s_ in sl[k:] for u in s_]
            if not any(u.get('kind') == MAIN for u in top) or any(u.get('kind') == MAIN for u in bot): continue
            # every column with material below the line ends in main text above it (a column whose
            # references simply run on across the line is no break)
            ok = True
            for bi in {band_of(cx(u), bands) for u in bot}:
                above = [u for u in top if band_of(cx(u), bands) == bi]
                if above and max(above, key=lambda u: u['box'][3]).get('kind') != MAIN: ok = False; break
            if ok: return cut(top) + cut(bot)
        for a, b in gutters:
            if not any(u['box'][0] < a and u['box'][2] > b for u in us):
                left = [u for u in us if cx(u) < (a + b) / 2]; right = [u for u in us if cx(u) >= (a + b) / 2]
                if left and right: return cut(left) + cut(right)
        # units across a gutter divide the region into bands (and only they do: a white line that happens
        # to cross both columns is not a break); each band is cut again
        def crosses(u): return any(u['box'][0] < a and u['box'][2] > b for a, b in gutters)
        def cy(u): return (u['box'][1] + u['box'][3]) / 2
        span = sorted([u for u in us if crosses(u)], key=cy)
        if span and len(span) < len(us):
            slots = [[] for _ in range(len(span) + 1)]
            for u in us:
                if not crosses(u): slots[sum(1 for s_ in span if cy(s_) <= cy(u))].append(u)
            out = []
            for k, slot in enumerate(slots):
                out += cut(slot)
                if k < len(span): out.append(span[k])
            return out
        slabs = slabs_of(us)
        if len(slabs) > 1: return [x for sl in slabs for x in cut(sl)]
        return sorted(us, key=lambda u: (band_of(cx(u), bands), u['box'][1]))
    return cut(units)

# -- alt main text ---------------------------------------------------------------------------------------
def alt_main(kind, picture, words):
    """The last step of the floats (the user's rule): a text float of one to five words is not a float;
    it is relabelled alt main text. A picture stays a float whatever lettering it holds."""
    return kind == 'float' and not picture and 1 <= words <= 5

# -- captions ------------------------------------------------------------------------------------------
LABEL = re.compile(r'^(fig(ure)?|table|box|scheme|chart|plate|panel)\.?$', re.I)
NUMBER = re.compile(r'^[A-Z]?\d+[A-Za-z]?([.:|]|\.\d+)?$')

def is_caption(first_words, unit_fonts):
    """first_words: [(text, original font)] of a block's first line. A caption opens with a float label
    and a number ("Figure 1", "Fig. 2.", "TABLE 3:") set apart: by punctuation after the label or number,
    or by a font of its own (the block's other words in another font). "Table 1 summarizes ..." in the
    body font is a sentence, not a caption."""
    if len(first_words) < 2 or not LABEL.match(first_words[0][0]) or not NUMBER.match(first_words[1][0]): return False
    if first_words[0][0].endswith('.') and first_words[0][0].lower() in ('fig.',) and first_words[1][0][-1:] in '.:|': return True
    if first_words[1][0][-1:] in '.:|': return True
    rest = collections.Counter(unit_fonts)
    body = rest.most_common(1)[0][0] if rest else None
    return first_words[0][1] != body

# -- furniture -----------------------------------------------------------------------------------------
def furniture_key(text):
    """Text of a block with digits and spacing dropped, for finding the same block on many pages."""
    return re.sub(r'[^a-z]', '', text.lower())[:60]

def repeated_blocks(blocks, n_pages, share=0.25, place=40):
    """blocks: [(page, text, box)]. Furniture repeats its text in the same place: keys (text, place) of
    blocks found on at least max(2, share * pages) pages with their boxes within `place` px."""
    groups = []
    for page, text, box in blocks:
        k = furniture_key(text)
        if len(k) < 8: continue
        for g in groups:
            if g['key'] == k and all(abs(a - b) <= place for a, b in zip(g['box'], box)): g['pages'].add(page); g['members'].append((page, box)); break
        else: groups.append(dict(key=k, box=list(box), pages={page}, members=[(page, box)]))
    need = max(2, int(share * n_pages + 0.999))
    return [g for g in groups if len(g['pages']) >= need]

def recurring_outside(lines, n_pages, share=0.25):
    """lines: [(page, band, cls)] of lines outside the frame (band: top/bottom/left/right). A line is
    furniture when lines of its class sit in the same band on at least max(2, share * pages) pages."""
    pages_of = collections.defaultdict(set)
    for page, band, c in lines: pages_of[(band, c)].add(page)
    need = max(2, int(share * n_pages + 0.999))
    return {k for k, v in pages_of.items() if len(v) >= need}

# -- references ----------------------------------------------------------------------------------------
HEADWORDS = r'(references?( and notes)?|notes and references|references? cited|cited references|reference list|bibliography|literature( cited)?|works cited|citations)'
REFHEAD = re.compile(r'^(\d+\.?\s*)?' + HEADWORDS + r'\b\W*', re.I)
REFLINE = re.compile(r'(\d+\.?\s*)?' + HEADWORDS + r'\W*', re.I)
YEAR = r'(19|20)\d{2}[a-z]?'
NAME_PARTICLES = {'van', 'von', 'de', 'der', 'den', 'da', 'di', 'du', 'le', 'la', 'del', 'della', 'ter', 'ten', "d'", 'dos', 'das'}
NAME = r"[^\W\d_](?:[^\W\d_]|['’´¨`˜ˆ\-])*"          # a surname in any alphabet, with old spacing accents ("Arau´jo")
LEAD = r'^(?:(?:van|von|de|der|den|da|di|du|le|la|del|della|ter|ten|dos|das)\s+)*'   # name particles before a surname ("van Charante")
STYLES = {   # how an entry starts, in the common styles
    'numbered': re.compile(r'^(\[\d{1,3}\]|\d{1,3}[.)]?)\s+\S'),
    'author-year (APA/Harvard)': re.compile(LEAD + NAME + r'(\s(Jr|Sr)\.?)?,\s+([^\W\d_]\.\s?-?){1,3}'),
    'Vancouver': re.compile(LEAD + NAME + r'(\s' + NAME + r')?\s[^\W\d_a-z]{1,3}([,.]|\s\()'),     # "Amulic B, ..." or a single author "Dickinson DP (2002)" 
    'MLA/Chicago': re.compile(LEAD + NAME + r',\s+[^\W\d_][^\W\d_]+'),
    'organisation': re.compile(r"^[^\W\d_][\w’'&\- ]{3,60}[.,]\s+" + YEAR),
}

def style_of(text, need_year=True):
    t = REFHEAD.sub('', text, count=1).strip()
    first = t.split(' ', 1)[0].lower() if t else ''
    for name, p in STYLES.items():
        if name == 'organisation' and len(t.split()) < 8: continue      # "Accepted for publication June 21, 1999." is no entry
        if name != 'numbered' and t[:1].islower() and first not in NAME_PARTICLES: continue   # a name opens with a capital ("van", "de" excepted)
        if p.match(t) and (not need_year or re.search(YEAR, t)): return name
    return None

def entry_starts(lines):
    """lines: [(x_start, text)] top down. Returns [(first line index, entry text)]. Entries start at one of
    the block's two indent levels: the level whose lines mostly open like an entry (numbered, or a name) -
    the first line set flush with the rest hanging, or the first line indented with the rest flush. With a
    single level, a line that opens like an entry starts one. A heading alone on the first line is left
    out (index 0 is then the line after it)."""
    off = 0
    if lines and REFHEAD.match(lines[0][1]) and not REFHEAD.sub('', lines[0][1], count=1).strip(): lines = lines[1:]; off = 1
    if not lines: return []
    def opens(t): return any(p.match(t) for p in STYLES.values())
    flush = min(x for x, _ in lines)
    level = [abs(x - flush) <= 3 for x, _ in lines]                 # True: flush, False: indented
    two = not all(level) and any(level)
    if two:
        share = {lv: (sum(opens(t) for (x, t), l in zip(lines, level) if l == lv) / max(1, sum(1 for l in level if l == lv))) for lv in (True, False)}
        start_level = max(share, key=share.get)
    out = []
    for k, ((x, t), l) in enumerate(zip(lines, level)):
        new = (l == start_level) if two else opens(t)
        if new or not out: out.append([k + off, t])
        else: out[-1][1] += ' ' + t
    return [tuple(e) for e in out]

def entries(lines):
    return [t for _, t in entry_starts(lines)]

def ref_score(lines):
    """(share of a block's entries that read like references, main style, entries, first line of a trailing
    note or None). A break cuts entries: the first may be the end of one from the block before (no entry
    start: left out), the last may stop before its year. Lines after the last entry that reads like a
    reference (a correspondence address, an acceptance date) are a note, left out of the share."""
    es = entry_starts(lines)
    if not es: return 0.0, None, 0, None
    st = [style_of(e, need_year=(i < len(es) - 1)) for i, (_, e) in enumerate(es)]
    if len(es) > 1 and not st[0] and not style_of(es[0][1], need_year=False): st, es = st[1:], es[1:]
    last = max((i for i, s_ in enumerate(st) if s_), default=None)
    note = None
    if last is not None and last < len(es) - 1: note = es[last + 1][0]; st, es = st[:last + 1], es[:last + 1]
    hit = [s_ for s_ in st if s_]
    return len(hit) / len(es), (collections.Counter(hit).most_common(1)[0][0] if hit else None), len(es), note

def find_references(units, half_page, short_note=40, short_main=25, min_score=0.6):
    """units in reading order: dicts with page, kind ('main text', 'non-main text', 'float', 'other', ...),
    picture, lines [(x, text)], words. A heading candidate is a "References" line (or similar) in the
    second half of the paper: the first line of a non-main block (then the rest of that line, or the
    next line, must open like an entry) or the last line just before one. Candidates are tried in
    reading order; the first one followed by reference blocks wins. Returns (indexes, details)."""
    notes = {}
    def walk(start, from_line=0):
        found, passed, ended = [], [], None
        for i in range(start, len(units)):
            u = units[i]
            if u.get('picture') or u.get('panel') or u['kind'] == 'other': continue      # furniture or a panel ("How to cite this article") between reference blocks is not references
            if u['kind'] in ('non-main text', 'float'):
                lines_ = u['lines'][from_line:] if i == start else u['lines']
                score, style, n, note = ref_score(lines_)
                # the end of an entry cut off at a column break (one entry, no entry start) between reference blocks
                if score < min_score and found and n == 1 and lines_ and not style_of(lines_[0][1], need_year=False) and not lines_[0][1][:1].isupper(): score, style = 1.0, found[-1][1]   # it starts mid-sentence
                if score >= min_score:
                    found.append((i, style, n))
                    if note is not None: notes[i] = note + (from_line if i == start else 0)
                    continue
                if u['words'] < short_note: passed.append(i); continue
                ended = i; break
            if u['kind'] == 'main text' and u['words'] < short_main: continue
            ended = i; break
        return found, passed, ended
    tried = []
    for i, u in enumerate(units):
        if u['page'] < half_page or u['kind'] not in ('non-main text', 'float') or u.get('picture') or not u['lines']: continue
        first = u['lines'][0][1]
        prev = next((units[j] for j in range(i - 1, -1, -1) if units[j]['lines'] and (units[j]['words'] > 2 or REFLINE.fullmatch(units[j]['lines'][-1][1].strip()))), None)   # past stray pieces of one or two words (a heading alone is not stray)
        last_prev = prev['lines'][-1][1].strip() if prev else ''
        m = REFHEAD.match(first); split = None
        inner = next((k for k in range(1, len(u['lines'])) if REFLINE.fullmatch(u['lines'][k][1].strip())), None)
        if m:
            rest = first[m.end():].strip() or (u['lines'][1][1] if len(u['lines']) > 1 else '')
            if not rest or style_of(rest, need_year=False): heading, where = first[:m.end()].strip(), 'first line of the block'
            else: continue
        elif REFLINE.fullmatch(last_prev): heading, where = last_prev, 'line just before the block'
        elif inner is not None: heading, where, split = u['lines'][inner][1].strip(), 'a line inside the block (the block is split there)', inner
        else: continue
        found, passed, ended = walk(i, split or 0); tried.append(heading)
        if found:
            styles = collections.Counter(s for _, s, _ in found)
            return [j for j, _, _ in found], dict(found=True, heading=heading, heading_where=where, split=[i, split] if split else None,
                                                  heading_unit=i - 1 if where == 'line just before the block' else None,
                                                  blocks=len(found), entries=sum(n for _, _, n in found), style=styles.most_common(1)[0][0],
                                                  passed_over=passed, ended_at=ended, candidates_tried=tried, notes=dict(notes))
    return [], dict(found=False, notes={}, heading=None, heading_where=None, heading_unit=None, split=None, blocks=0, entries=0, style=None, passed_over=[], ended_at=None, candidates_tried=tried)
