"""Shared evidence for the second pass: the copy, its native trace and the boxer pages.

The second pass reads what the first run wrote (copy.md, copy.trace.json,
page-NN.json, copy.tables.json, authors.json) and the PDF itself. It never
changes the copy text. Coordinates are page pixels at the boxer's 150 dpi,
top-down, in MediaBox space (the page JSON's box_px); trace line boxes are
converted from their 110-dpi form.
"""
import bisect
import json
import re
import statistics
import subprocess
from functools import cached_property
from pathlib import Path

UNCERTAINTY = '## Places the program is not sure of'
DPI = 150
GOOD_LINE = {'unit', 'split', 'split_unverified', 'flagged_repeat', 'uncertainty', 'duplicate', 'partly_excluded'}
BODY_KINDS = {'paragraph', 'list_item', 'abstract_part'}
TEXT_KINDS = BODY_KINDS | {'heading', 'reference', 'footnote', 'end_matter', 'article_information'}
FRONT_KINDS = {'title', 'author', 'affiliation'}
FLOAT_KINDS = {'caption', 'table_cell', 'table_line', 'table_note', 'figure_text', 'image_file'}
SENTENCE_END = re.compile(r'[.!?:;)\]"”’*†‡§¶#\d]\s*$')


def finding(rule, message, page=None, pages=None, box=None, unit=None, offset=None, **evidence):
    """One second-pass item. `pages` lists every page involved; `offset` is a copy character offset."""
    pages = sorted({p for p in (pages or ([page] if page else [])) if p})
    return dict(rule=rule, page=page or (pages[0] if pages else None), pages=pages,
                box=[round(v, 1) for v in box] if box else None, unit=unit, offset=offset,
                message=message, evidence=evidence)


def words(text):
    return re.findall(r"[A-Za-zÀ-ɏͰ-Ͽ]+|\d+", text)


def norm(text):
    return ' '.join(w.lower() for w in words(text))


def overlap(a, b):
    """Intersection area of two boxes."""
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def area(b):
    return max(0.0, b[2]-b[0]) * max(0.0, b[3]-b[1])


def inside(point, box, pad=0.0):
    x, y = point
    return box[0]-pad <= x <= box[2]+pad and box[1]-pad <= y <= box[3]+pad


class Paper:
    """Read-only view of one copy folder."""

    def __init__(self, folder, pdf=None):
        self.folder = Path(folder)
        self.text = (self.folder/'copy.md').read_text(encoding='utf-8')
        self.body_text, mark, notes = self.text.partition(UNCERTAINTY)
        # the program's own list, without items an earlier second pass added
        self.notes_text = '\n'.join(l for l in notes.split('\n') if not l.startswith('- second pass, rule '))
        self.trace = json.loads((self.folder/'copy.trace.json').read_text(encoding='utf-8'))
        self.pdf = str(pdf or self.trace['pdf'].get('path') or '')
        self.units = sorted(self.trace['units'], key=lambda u: (u['span'][0], u['span'][1]))
        self.lines = {l['export_id']: l for l in self.trace['lines']}
        self.line_starts = [0] + [m.end() for m in re.finditer('\n', self.text)]
        self._pages = {}; self._elements = {}; self._shift = {}

    # ---- copy positions -------------------------------------------------
    def copy_line(self, offset):
        """1-based copy.md line number of a character offset."""
        return bisect.bisect_right(self.line_starts, offset) if offset is not None else None

    # ---- pages -----------------------------------------------------------
    @cached_property
    def page_numbers(self):
        return sorted(int(p.stem.split('-')[1]) for p in self.folder.glob('page-[0-9]*.json'))

    def page(self, n):
        if n not in self._pages:
            path = self.folder/f'page-{n:02}.json'
            self._pages[n] = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
        return self._pages[n]

    def elements(self, n):
        """Page elements with box_px moved into the render frame (see shift)."""
        if n in self._elements: return self._elements[n]
        p = self.page(n); dx, dy = self.shift(n)
        out = {}
        for e in (p or {}).get('elements', []):
            e = dict(e)
            if e.get('box_px'): e['box_px'] = self.moved(e['box_px'], n)
            out[e['id']] = e
        self._elements[n] = out
        return out

    def shift(self, n):
        """Offset from the page JSON's box_px frame to the rendered MediaBox frame.

        The trace's line boxes are in the MediaBox frame; on pages whose crop box
        differs from the media box the boxer's pixel frame can be displaced. The
        offset is measured, not assumed: the median difference between each
        single-run trace line's box and its run's box_px.
        """
        if n in self._shift: return self._shift[n]
        raw = {e['id']: e for e in (self.page(n) or {}).get('elements', [])}
        dxs, dys = [], []
        for l in self.trace['lines']:
            if l['page'] != n or len(l.get('runs', [])) != 1: continue
            e = raw.get(l['runs'][0]); b = self.line_box(l)
            if not e or not e.get('box_px') or not b: continue
            dxs.append(b[0]-e['box_px'][0]); dys.append(b[1]-e['box_px'][1])
        value = (statistics.median(dxs), statistics.median(dys)) if len(dxs) >= 3 else (0.0, 0.0)
        value = tuple(0.0 if abs(v) < 1.5 else v for v in value)
        self._shift[n] = value
        return value

    def moved(self, box, n):
        dx, dy = self.shift(n)
        return [box[0]+dx, box[1]+dy, box[2]+dx, box[3]+dy] if box else box

    @cached_property
    def geometry(self):
        """Page media box, crop box (both in PDF points) and rotation, from pdfinfo."""
        out = {}
        if not self.pdf or not Path(self.pdf).is_file(): return out
        try:
            info = subprocess.run(['pdfinfo', '-box', '-f', '1', '-l', '9999', self.pdf], capture_output=True,
                                  text=True, timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            return out
        for line in info.splitlines():
            m = re.match(r'Page\s+(\d+)\s+(MediaBox|CropBox|rot):\s+(.*)', line)
            if not m: continue
            n = int(m.group(1)); rec = out.setdefault(n, {})
            if m.group(2) == 'rot': rec['rotation'] = int(float(m.group(3)))
            else: rec[m.group(2)] = [float(v) for v in m.group(3).split()]
        return out

    def crop_px(self, n):
        """The visible (crop) box in the boxer's MediaBox pixel frame."""
        g = self.geometry.get(n)
        if not g or 'MediaBox' not in g: return None
        mx0, my0, mx1, my1 = g['MediaBox']; cx0, cy0, cx1, cy1 = g.get('CropBox', g['MediaBox'])
        s = DPI/72
        return [(cx0-mx0)*s, (my1-cy1)*s, (cx1-mx0)*s, (my1-cy0)*s]

    def media_px(self, n):
        """The page in the render frame: the trace's media box, else pdfinfo's, else the boxer's page region."""
        s = DPI/72
        for rec in self.trace.get('pdf', {}).get('pages') or []:
            if rec.get('page') == n and rec.get('media_box_pdf_points'):
                x0, y0, x1, y1 = rec['media_box_pdf_points']
                return [0, 0, (x1-x0)*s, (y1-y0)*s]
        g = self.geometry.get(n)
        if g and 'MediaBox' in g:
            x0, y0, x1, y1 = g['MediaBox']
            return [0, 0, (x1-x0)*s, (y1-y0)*s]
        region = (self.page(n) or {}).get('region_box_px')
        return [0, 0, region[2], region[3]] if region else None

    # ---- lines and units -------------------------------------------------
    @staticmethod
    def line_box(line):
        b = line.get('box_110dpi')
        return [v*DPI/110 for v in b] if b else None

    def run_boxes(self, line):
        """Boxes of a trace line's runs (page elements), or the line box for OCR runs."""
        els = self.elements(line['page']); boxes = []
        for r in line.get('runs', []):
            e = els.get(r)
            if e and e.get('box_px'): boxes.append(e['box_px'])
        if not boxes and self.line_box(line): boxes.append(self.line_box(line))
        return boxes

    def line_size(self, line):
        """Text size of a line in pixels: its runs' size, else the box height."""
        els = self.elements(line['page'])
        runs = [els[r] for r in line.get('runs', []) if r in els and els[r].get('size_px')]
        if runs: return max(runs, key=lambda e: len(e.get('text', '')))['size_px']   # the longest run's size
        b = self.line_box(line)
        return (b[3]-b[1])*.8 if b else None

    @cached_property
    def run_line(self):
        """(page, run id) -> trace line."""
        out = {}
        for l in self.trace['lines']:
            for r in l.get('runs', []): out[l['page'], str(r)] = l
        return out

    @cached_property
    def rows(self):
        return {r['row']: r for r in self.trace.get('rows', [])}

    def unit_lines(self, unit):
        """Source lines of a unit with its own claims, in the order its text reads them.

        The order comes from the unit's claimed rows (recorded as the text was
        written); claimed runs follow. Group claims (table cells) give none.
        """
        if unit.get('source_basis') != 'own claims': return []
        out, seen = [], set()
        claims = unit.get('claims') or {}
        refs = [(self.rows[r]['page'], m) for r, a, b in claims.get('rows', []) if r in self.rows for m in self.rows[r]['runs']]
        refs += [(pg, m) for pg, m, partial in claims.get('runs', [])]
        for pg, m in refs:
            l = self.run_line.get((pg, str(m)))
            if l and l['export_id'] not in seen: seen.add(l['export_id']); out.append(l)
        if not out:
            out = [self.lines[s['export_id']] for s in unit.get('sources', []) if s.get('export_id') in self.lines]
        return out

    @cached_property
    def content_units(self):
        return [u for u in self.units if u['status'] != 'generated' and u['text'].strip()
                and u['span'][1] <= len(self.body_text)]

    def body_size(self, n):
        p = self.page(n)
        return ((p or {}).get('main_text') or {}).get('body_size_px') or 21.0

    @cached_property
    def paper_body_size(self):
        sizes = [self.body_size(n) for n in self.page_numbers if self.page(n)]
        return statistics.median(sizes) if sizes else 21.0

    def columns(self, n):
        dx = self.shift(n)[0]
        return [[c[0]+dx, c[1]+dx] for c in ((self.page(n) or {}).get('main_text') or {}).get('columns') or []]

    @cached_property
    def scan_pages(self):
        """Pages whose lines come from an OCR layer (ocr: runs)."""
        pages = set()
        for l in self.trace['lines']:
            if any(str(r).startswith(('ocr:', 'scan:')) for r in l.get('runs', [])): pages.add(l['page'])
        return pages

    def notes(self):
        return [n[2:].strip() for n in self.notes_text.splitlines() if n.startswith('- ')]


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


ORDER_KINDS = BODY_KINDS | {'heading'}


class Layout:
    """The page's own reading order of the copy's body lines.

    Body lines are the source lines of paragraph, list, abstract and heading
    units (paragraphs of one to three letters are lettering and left out).
    Columns are inferred from the lines themselves: lines of eight ems or more
    that overlap by 60% of the wider and have widths within 25% of the group's
    typical line form a cluster; a cluster covering two side-by-side clusters
    is a spanning block (an abstract or title above the columns) and never
    merges; a cluster inside a wider non-spanning one joins it (paragraph ends,
    a column narrowed beside a figure); a narrow block straddling a column edge
    is no column. Lines covering two columns are spanning lines and start a new
    band. The order key is (band, column, printed row, x): column-major within
    each band, bands top to bottom, pieces of one printed row left to right.
    """

    def __init__(self, paper):
        self.paper = paper
        self.seq = []          # (unit index, line) in copy order
        self.unit_of = {}
        for k, u in enumerate(paper.content_units):
            if u['kind'] not in ORDER_KINDS: continue
            # one or two letters copied as a paragraph are figure lettering, not text flow
            if u['kind'] != 'heading' and len(u['text'].strip()) < 4: continue
            for l in paper.unit_lines(u):
                self.seq.append((k, l)); self.unit_of.setdefault(l['export_id'], k)
        self.key = {}
        self.page_lines = {}
        # Pages that print front matter (a title, author or affiliation line):
        # only there can a column be too short to cluster because front matter
        # fills the rest of it (the short-column rule in _keys).
        self.front_pages = {l['page'] for u in paper.content_units if u['kind'] in FRONT_KINDS
                            for l in paper.unit_lines(u)}
        pages = {}
        for _, l in self.seq: pages.setdefault(l['page'], {})[l['export_id']] = l
        for n, ls in pages.items():
            self.page_lines[n] = self._keys(n, list(ls.values()))

    def kind(self, line):
        k = self.unit_of.get(line['export_id'])
        return self.paper.content_units[k]['kind'] if k is not None else None

    def _keys(self, n, lines):
        boxes = {l['export_id']: self.paper.line_box(l) for l in lines if self.paper.line_box(l)}
        if not boxes: return []
        em = self.paper.body_size(n)
        left = min(b[0] for b in boxes.values()); right = max(b[2] for b in boxes.values())
        width = max(1.0, right-left)
        # Lines of one column: overlapping by 60% of the wider and widths within 25%,
        # judged against the cluster's typical (median) line, not its growing extent.
        groups = []
        for b in sorted((b for b in boxes.values() if b[2]-b[0] >= 8*em), key=lambda b: b[0]):
            for g in groups:
                x0 = statistics.median(m[0] for m in g); x1 = statistics.median(m[2] for m in g)
                ov = min(x1, b[2]) - max(x0, b[0]); wa, wb = x1-x0, b[2]-b[0]
                if ov >= .6*max(wa, wb) and min(wa, wb) >= .75*max(wa, wb):
                    g.append(b); break
            else: groups.append([b])
        clusters = [[min(m[0] for m in g), max(m[2] for m in g), len(g)] for g in groups]
        # Clusters of one column found in different orders merge; a cluster lying
        # inside a wider one (paragraph ends, a column narrowed beside a figure)
        # is absorbed by it, unless the wider one spans two columns (an abstract
        # or title block above them).
        def over(a, b, share=.3):
            return min(a[1], b[1]) - max(a[0], b[0]) >= share*(b[1]-b[0])

        def side_by_side(c, group):
            """c covers two clusters of the group that lie side by side (overlapping by under a fifth)."""
            inner = [d for d in group if d is not c and over(c, d)]
            return any(min(x[1], y[1]) - max(x[0], y[0]) < .2*min(x[1]-x[0], y[1]-y[0])
                       for x in inner for y in inner if x is not y)
        changed = True
        while changed:
            changed = False
            big = [c for c in clusters if c[2] >= 3]
            spanning_blocks = [c for c in clusters if side_by_side(c, big)]
            for a in clusters:
                for b in clusters:
                    if a is b: continue
                    ov = min(a[1], b[1]) - max(a[0], b[0])
                    wa, wb = a[1]-a[0], b[1]-b[0]
                    if any(a is c or b is c for c in spanning_blocks): continue
                    if (ov >= .6*max(wa, wb) and min(wa, wb) >= .75*max(wa, wb)) or (wb <= wa and ov >= .9*wb):
                        a[0] = min(a[0], b[0]); a[1] = max(a[1], b[1]); a[2] += b[2]
                        clusters.remove(b); changed = True; break
                if changed: break
        cols = [c for c in clusters if c[2] >= 3]

        def covers(b, c):
            return min(c[1], b[2]) - max(c[0], b[0]) >= .3*(c[1]-c[0])
        cols = [c for c in cols if not side_by_side(c, cols)]
        # a narrow block straddling a column edge (an inset box) is no column of its own
        cols = sorted([c for c in cols if not any(d[2] > c[2] and min(c[1], d[1]) - max(c[0], d[0]) > .2*(c[1]-c[0])
                                                  for d in cols)], key=lambda c: c[0])
        multi = len(cols) > 1
        spanning = {i for i, b in boxes.items() if multi and sum(covers(b, c) for c in cols) >= 2}
        spans = sorted(boxes[i][1] for i in spanning)
        # Lines beside every column, overlapping none, read between the columns either
        # side when that gap holds two or more lines of column width (at least .75 of
        # the narrowest column, the clustering width ratio): a column too short to
        # cluster (AP03 page 1: a heading and two body lines left of the only clustered
        # column, above footnotes). A gap with fewer such lines (a paragraph's last
        # line, list bullets, a heading and its number) keeps the nearest column.
        # Only on a page with front matter (AS14 pages 6-7, a table page, keep the
        # nearest column).
        gaps = {}
        for i, b in boxes.items():
            if cols and n in self.front_pages and i not in spanning and all(min(c[1], b[2]) <= max(c[0], b[0]) for c in cols):
                gaps.setdefault(sum(c[0] < b[0] for c in cols) - .5, []).append(i)
        short_column = {i: g for g, ids in gaps.items()
                        if sum(boxes[i][2]-boxes[i][0] >= .75*min(c[1]-c[0] for c in cols) for i in ids) >= 2
                        for i in ids}
        out = []; place = {}
        for i, b in boxes.items():
            wide = i in spanning
            if wide or not cols: col = -1 if wide else 0
            elif i in short_column:
                col = short_column[i]
            else:
                col = max(range(len(cols)), key=lambda k: (min(cols[k][1], b[2]) - max(cols[k][0], b[0]), -k))
            band = sum(1 for y in spans if y < b[1]-.3*em) + (.5 if wide else 0)
            place[i] = (band, col)
        # A printed row split by a column edge (a boxed block's centred heading)
        # belongs to the spanning block it touches, not to the columns beside it:
        # its pieces lie in two or more columns, none has a line of its own column
        # within two body sizes above or below it, and a spanning line within two
        # body sizes above or below covers the row to within one body size. The
        # row is read just before (or after) that spanning line. Pieces in different
        # columns must be at most two body sizes apart (a word space of one line);
        # an element set far to the right of a line's end is not one line with it.
        def vgap(a, c):
            return max(a[1]-c[3], c[1]-a[3])
        narrow = sorted((i for i in boxes if i not in spanning), key=lambda i: boxes[i][1])
        rows = []
        for i in narrow:
            if rows and boxes[i][1]-boxes[rows[-1][0]][1] <= .45*em: rows[-1].append(i)
            else: rows.append([i])
        # A piece's side: the columns whose left edge lies left of its centre. Left
        # edges hold where a right extent does not (a column cluster that took in a
        # spanning block's short last line reaches into the next column, and a piece
        # just right of the gutter then counts as the left column's).
        def side(i):
            return sum(c[0] <= (boxes[i][0]+boxes[i][2])/2 for c in cols[1:])
        def apart(a, b):
            return place[a][1] != place[b][1] or side(a) != side(b)
        def candidate(row):
            xs = sorted(row, key=lambda i: boxes[i][0])
            return any(apart(a, b) for a, b in zip(xs, xs[1:])) and not any(
                apart(a, b) and boxes[b][0]-boxes[a][2] > 2*em for a, b in zip(xs, xs[1:]))
        # Candidate rows whose pieces of one column lie within two body sizes form
        # one stack (a heading of two or three split lines): the attached test leaves
        # out rows of the same stack, and the stack moves as a whole or not at all;
        # a stack of more than three rows is column prose across a narrow gutter.
        rows = [row for row in rows if candidate(row)]
        root = list(range(len(rows)))
        def find(k):
            while root[k] != k: k = root[k]
            return k
        for k, row in enumerate(rows):
            for m in range(k):
                if any((place[i][1] == place[j][1] or side(i) == side(j)) and vgap(boxes[i], boxes[j]) <= 2*em
                       for i in row for j in rows[m]):
                    root[find(k)] = find(m)
        stacks = {}
        for k, row in enumerate(rows): stacks.setdefault(find(k), []).append(row)
        for stack in stacks.values():
            if len(stack) > 3: continue
            st = [i for row in stack for i in row]
            h = [min(boxes[i][0] for i in st), min(boxes[i][1] for i in st),
                 max(boxes[i][2] for i in st), max(boxes[i][3] for i in st)]
            if any(j not in st and j not in spanning and place[j][1] == place[i][1] and
                   vgap(boxes[i], boxes[j]) <= 2*em for i in st for j in boxes): continue
            touching = [s for s in spanning if -.5*em <= vgap(h, boxes[s]) <= 2*em and
                        boxes[s][0]-em <= h[0] and h[2] <= boxes[s][2]+em]
            if not touching: continue
            s = min(touching, key=lambda s: vgap(h, boxes[s]))
            for i in st: place[i] = (place[s][0] + (-.25 if boxes[s][1] > h[1] else .25), -1)
        # Pieces of one printed line (justified words, a section number before
        # its heading) share a row: tops within .45 em, read left to right.
        rowkey = {}
        for grp in {v for v in place.values()}:
            ids = sorted((i for i in place if place[i] == grp), key=lambda i: boxes[i][1])
            row, top = -1, None
            for i in ids:
                if top is None or boxes[i][1] - top > .45*em: row += 1; top = boxes[i][1]
                rowkey[i] = row
        for i, b in boxes.items():
            self.key[i] = place[i] + (rowkey[i], b[0])
            out.append(i)
        out.sort(key=lambda i: self.key[i])
        self.rank = getattr(self, 'rank', {})
        for r, i in enumerate(out): self.rank[i] = (n, r)
        return out


FUNCTION_WORDS = {'and', 'or', 'of', 'the', 'in', 'with', 'to', 'a', 'an', 'for', 'by', 'on', 'at', 'from', 'as',
                  'that', 'than', 'is', 'are', 'was', 'were', 'be', 'between', 'into', 'which', 'whereas', 'but'}


def clean_end(text):
    """Text without trailing markup, citation markers and spaces."""
    t = re.sub(r'(\*\*|__|\*|_|`)+$', '', text.rstrip())
    t = re.sub(r'[\s ]*(\[[\d,\s–-]+\]|<sup>.*?</sup>|\^\S+)$', '', t)
    return t.rstrip()


def ends_mid(text):
    """A paragraph that stops inside a sentence: ends in a lowercase letter, a comma, a
    line-end hyphen after a letter, or an article/conjunction/preposition."""
    t = clean_end(text)
    if not t: return False
    if re.search(r'(doi|https?|www)\S*$|\S+[/.]\S*[a-z]$', t, re.I) and not re.search(r'\s[a-z]+$', t[-30:]): return False
    if re.search(r'[A-Za-z]-$', t): return True
    last = re.findall(r"[A-Za-z]+[.,;:!?)\]]*$", t)
    if t[-1] == ',': return True
    if t[-1].isalpha() and t[-1].islower():
        return True
    return bool(last) and last[0].lower() in FUNCTION_WORDS


def ends_hyphen(text):
    return bool(re.search(r'[A-Za-z]-$', clean_end(text)))


def continues(text):
    """Text that can continue a broken sentence: starts with a lowercase letter, a digit,
    an opening bracket or a sign (not a capitalised word or a list marker)."""
    t = re.sub(r'^[\s>*_#-]*', '', text)
    t = re.sub(r'^\(?[ivx]+\)\s+|^\d+\.\s+[A-Z]', lambda m: m.group(0) if m.group(0)[-1:] != ' ' else m.group(0), t)
    if not t: return False
    c = t[0]
    return c.islower() or c in '([{±≤≥<>=%–—' or (c.isdigit() and not re.match(r'\d+\.\s', t))


_BOUNDARY = {}


def boundary_functions():
    """Rule 9's shared boundary witness and its end/start tests (element_boxer_sc.py::
    boundary_witness, boundary_open_end, boundary_resumes; lane f5stream R4), compiled from the
    boxer's own source without importing the boxer: the copier and this second pass decide a
    sentence boundary with the same functions."""
    if not _BOUNDARY:
        import ast
        path = Path(__file__).resolve().parents[2]/'standalone'/'element_boxer_sc.py'
        names = ('BODY_ORDER_HYPHENS', 'BODY_ORDER_TERMINAL', 'body_order_textcue_rule', 'BOUNDARY_TERMINAL',
                 'BOUNDARY_OPENING', 'BOUNDARY_OPEN_WORD', 'BOUNDARY_RESUME', 'BOUNDARY_SENTENCE_CUT',
                 'boundary_unfinished_sentence', 'boundary_bracket', 'boundary_open_end',
                 'boundary_resumes', 'boundary_witness')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names or
                isinstance(n, ast.Assign) and any(getattr(t, 'id', None) in names for t in n.targets)]
        ns = {'re': re}
        exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), 'exec'), ns)
        _BOUNDARY.update({k: ns[k] for k in names})
    return _BOUNDARY


def boundary_witness(last, nxt):
    return boundary_functions()['boundary_witness'](last, nxt)


def adjacent(paper, a, b):
    """Line b directly follows line a on the page: same page, next row of the same column."""
    if not a or not b or a['page'] != b['page']: return False
    ba, bb = paper.line_box(a), paper.line_box(b)
    if not ba or not bb: return False
    em = paper.body_size(a['page'])
    return 0 <= bb[1] - ba[1] <= 2.2*em and min(ba[2], bb[2]) - max(ba[0], bb[0]) > 0


def proper_nouns(paper):
    """Capitalised words the copy also uses inside sentences (after a lowercase word)."""
    if getattr(paper, '_proper', None) is None:
        paper._proper = set(re.findall(r"(?<=[a-z,] )([A-Z][a-z]+)", paper.body_text))
    return paper._proper


def pdf_words(paper):
    """Lowercased words of the PDF's own text layer (pdftotext), for vocabulary checks."""
    if getattr(paper, '_pdf_words', None) is None:
        try:
            txt = subprocess.run(['pdftotext', '-q', paper.pdf, '-'], capture_output=True, timeout=120).stdout.decode('utf-8', 'replace')
        except (OSError, subprocess.SubprocessError):
            txt = ''
        paper._pdf_text = txt
        paper._pdf_words = set(w.lower() for w in re.findall(r'[A-Za-z]{2,}', txt))
        # hyphenated line ends rejoined
        paper._pdf_words |= {(a+b).lower() for a, b in re.findall(r'([A-Za-z]{2,})-\n([a-z]{2,})', txt)}
    return paper._pdf_words


def recurring_lines(paper):
    """Normalised texts printed near the top or bottom of three or more pages (running heads and feet)."""
    if getattr(paper, '_recurring', None) is None:
        seen = {}
        for l in paper.trace['lines']:
            b = paper.line_box(l); media = paper.media_px(l['page'])
            if not b or not media: continue
            cy = (b[1]+b[3])/2
            if not (cy < .13*media[3] or cy > .87*media[3]): continue
            key = re.sub(r'[^a-z]', '', l['text'].lower())
            if 6 <= len(key) <= 80: seen.setdefault(key, set()).add(l['page'])
        paper._recurring = {k for k, v in seen.items() if len(v) >= 3}
    return paper._recurring


def margin_band(paper, line, share=.13):
    b = paper.line_box(line); media = paper.media_px(line['page'])
    if not b or not media: return False
    cy = (b[1]+b[3])/2
    return cy < share*media[3] or cy > (1-share)*media[3]
