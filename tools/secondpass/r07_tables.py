"""Rule 7: tables, against the printed rows and columns.

For each table grid in the copy (table_cell units of one group, with their row
and column), the words of every cell are found again in the table's printed
source lines (in reading order, each printed word used once). Then:
  (a) one grid row must not hold two printed data rows: a row with two or more
      cells that each hold numbers from two printed row bands, or header words
      above numbers in two or more cells, is listed (rows merged; header mixed
      with data);
  (b) in a table whose data rows are printed on one line each, a cell printed
      on another grid row's line: all its words (each unique
      in the table) lie on printed rows of other grid rows and on none of its
      own row's lines (labels or values moved between rows);
  (c) one printed cell must not be cut across columns: a printed line lying
      inside one column's band whose words went to two grid columns is listed
      (a label part in a value cell);
  (d) printed lines of the table body in no cell: lines between the grid's
      first and last printed rows (or just below them) whose words are in no
      cell, holding numbers or several words, are listed (a row taken apart);
  (e) a table caption of more than sixty words has taken the table's lines or
      running text into it.
"""
import re
from collections import Counter, defaultdict

from common import finding, load_json

NAME = 'tables'
CAPTION_WORDS = 60    # a table caption is a title and a few notes, not the table
VALUE = re.compile(r'^[-−–+<>≤≥±(~]*\.?\d')   # a printed value (not a header count such as n=267)


def toks(text):
    """Words of a cell or printed line, without Markdown emphasis and escapes."""
    text = re.sub(r'\\(?=[*_#|\[\]`])', '', text)
    text = re.sub(r'(\*\*|__|(?<!\w)[*_]|[*_](?!\w)|`)', '', text)
    return [t for t in re.split(r'\s+', text.strip()) if t]


def bands(ys, em):
    """Cluster line centres into printed row bands (within .55 em)."""
    order = sorted(set(ys)); out = {}; band = -1; last = None
    for y in order:
        if last is None or y - last > .55*em: band += 1
        out[y] = band; last = y
    return out


def grids(paper):
    groups = defaultdict(list)
    for u in paper.units:
        if u['kind'] == 'table_cell' and u.get('row') is not None: groups[u['group']].append(u)
    return groups


def analyse(paper, cells):
    src = cells[0].get('sources') or []
    lines = [paper.lines[s['export_id']] for s in src if s.get('export_id') in paper.lines]
    lines = [l for l in lines if paper.line_box(l)]
    if not lines: return None
    # A table set at 90 degrees reads its rows along x: swap the axes.
    shapes = sorted((paper.line_box(l)[3]-paper.line_box(l)[1]) / max(1.0, paper.line_box(l)[2]-paper.line_box(l)[0]) for l in lines)
    turned = shapes[len(shapes)//2] > 1.5
    def box(l):
        b = paper.line_box(l)
        return [b[1], b[0], b[3], b[2]] if turned else b
    page = lines[0]['page']; em = paper.body_size(page) * .8
    cy = {l['export_id']: (box(l)[1]+box(l)[3])/2 for l in lines}
    bmap = bands(list(cy.values()), em)
    band = {i: bmap[y] for i, y in cy.items()}
    lines.sort(key=lambda l: (band[l['export_id']], box(l)[0]))
    pool = [(l['export_id'], k, t) for l in lines for k, t in enumerate(toks(l['text']))]
    used = [False]*len(pool)
    where = defaultdict(list)       # line -> [(row, col)]
    cell_lines = defaultdict(list)  # (row, col) -> [(line, token)]
    cursor = 0
    for u in sorted(cells, key=lambda u: (u['row'], u['column'])):
        for t in toks(u['text']):
            hit = None
            for j in range(cursor, len(pool)):
                if not used[j] and pool[j][2] == t: hit = j; break
            if hit is None:
                for j in range(0, cursor):
                    if not used[j] and pool[j][2] == t: hit = j; break
            if hit is None: continue
            used[hit] = True; cursor = hit+1
            i = pool[hit][0]
            where[i].append((u['row'], u['column'])); cell_lines[u['row'], u['column']].append((i, t))
    counts = Counter(t for i, k, t in pool)
    return dict(box=box, unique={t for t, c in counts.items() if c == 1 and len(t) >= 3 and re.search(r'\w', t)},
                lines={l['export_id']: l for l in lines}, band=band, where=where, cell_lines=cell_lines,
                used=used, pool=pool, page=page, em=em, cells={(u['row'], u['column']): u for u in cells})


def check(paper):
    """Tables: printed rows merged in one grid row, words moved between rows or columns, printed rows left out."""
    findings = []; stats = Counter()
    for g, cells in grids(paper).items():
        a = analyse(paper, cells)
        if not a: continue
        stats['grids'] += 1
        band, where, cl = a['band'], a['where'], a['cell_lines']
        n = a['page']
        first = min(cells, key=lambda u: u['span'][0])
        rows = sorted({r for r, c in cl})
        first_col = min(u['column'] for u in cells)
        row_band = {}
        for r in rows:
            cnt = Counter(band[i] for (rr, c), lst in cl.items() if rr == r for i, t in lst)
            if cnt: row_band[r] = cnt.most_common(1)[0][0]
        # Rows set on several printed lines by design (a value with its p-value
        # below, wrapped labels) cannot show a moved cell by band: (b) judges
        # only tables whose data rows are printed on one line.
        data_rows = [r for r in rows if any(VALUE.match(t) for (rr, c), lst in cl.items() if rr == r for i, t in lst)]
        heights = sorted(len({band[i] for (rr, c), lst in cl.items() if rr == r for i, t in lst}) for r in data_rows)
        one_line = bool(heights) and heights[len(heights)//2] == 1
        # (a) merged rows / header mixed with data
        for r in rows:
            numeric_multi = 0; header_mixed = 0
            for (rr, c), lst in cl.items():
                if rr != r: continue
                parts = defaultdict(list)
                for i, t in lst: parts[band[i]].append(t)
                if len(parts) < 2: continue
                digit = [b for b, ts in parts.items() if any(VALUE.match(x) for x in ts)]
                words = [b for b, ts in parts.items() if not any(re.search(r'\d', x) for x in ts)]
                if len(digit) >= 2: numeric_multi += 1
                if digit and words and min(words) < min(digit): header_mixed += 1
            # the row's first cell must hold two labels: parts on two printed rows,
            # the later one starting a new label (capital or digit), not a wrapped label
            # labels are placed by words that occur once in the table (a repeated
            # word such as "T0" could be matched on another row's line)
            stub = sorted(((band[i], t) for (rr, c), lst in cl.items() if rr == r and c == first_col for i, t in lst
                           if t in a['unique']), key=lambda bt: bt[0])   # stable: words keep their order within a band
            stub_bands = []   # [band, first word, last word]
            for b, t in stub:
                if not stub_bands or stub_bands[-1][0] != b: stub_bands.append([b, t, t])
                else: stub_bands[-1][2] = t
            # a later part starts a new label (capital or digit) unless the part
            # before it is unfinished (ends with a comma, semicolon, hyphen, "and"
            # or an abbreviation such as "vs.")
            two_labels = any(re.match(r'[A-Z0-9]', first) and not re.search(r'[-,;&]$|^(and|vs\.|et|al\.)$', stub_bands[k-1][2])
                             for k, (b, first, last) in enumerate(stub_bands) if k > 0)
            # a study cited by author and year ("Smith & Jones, 2010") is one label, however it wraps
            stub_unit = a['cells'].get((r, first_col))
            stub_text = ' '.join(toks(stub_unit['text'])) if stub_unit else ''
            if re.search(r"^[A-Z][\w'’-]+.*(?:,|\bal\.?|&|\band)\s*\(?(?:19|20)\d\d[a-z]?\)?$", stub_text) or \
                    re.search(r'\bet\.? al\b', stub_text):
                two_labels = False
            if (numeric_multi >= 2 or header_mixed >= 2) and two_labels:
                why = 'numbers from two printed rows' if numeric_multi >= 2 else 'header words above numbers'
                u = a['cells'].get((r, 1)) or first
                findings.append(finding(7, f"page {n}: table grid row {r} holds {why} in "
                                           f"{max(numeric_multi, header_mixed)} cells (printed rows merged): {u['text'][:50]!r}",
                                        page=n, unit=u['id'], offset=u['span'][0], kind='merged rows'))
        # (b) a cell printed entirely on other rows' lines: none of its words
        # share a printed row band with the rest of its grid row
        moved = []
        for (r, c), lst in (cl.items() if one_line else []):
            words = [(i, t) for i, t in lst if t in a['unique']]
            if not words or len(words) < len(lst): continue
            mine = {band[i] for i, t in lst}
            rest = {band[i] for (rr, cc), l2 in cl.items() if rr == r and cc != c for i, t in l2}
            others = {band[i] for (rr, cc), l2 in cl.items() if rr != r for i, t in l2}
            # data rows only (header tiers share lines by design), and outside the
            # vertical span of its own row (a short cell centred in a tall row is fine)
            if not any(re.search(r'\d', t) for (rr, cc), l2 in cl.items() if rr == r for i, t in l2): continue
            if rest and not (mine & rest) and mine <= others and all(b < min(rest) or b > max(rest) for b in mine):
                moved.append((r, c, lst[0][1]))
        for r, c, t in moved[:3]:
            u = a['cells'].get((r, c)) or first
            findings.append(finding(7, f"page {n}: table cell {u['text'][:40]!r} (grid row {r}, column {c}) is printed on "
                                       f"another row's line", page=n, unit=u['id'], offset=u['span'][0], kind='moved between rows'))
        # (c) one printed line cut across columns
        colx = defaultdict(list)
        for i, cells_of in where.items():
            if len({c for r, c in cells_of}) == 1:
                b = a['box'](a['lines'][i]); colx[cells_of[0][1]].append(b)
        bands_x = {c: (min(b[0] for b in bs), max(b[2] for b in bs)) for c, bs in colx.items() if len(bs) >= 2}
        for i, cells_of in where.items():
            cols = sorted({c for r, c in cells_of})
            if len(cols) < 2: continue
            if not all(t in a['unique'] for (ii, t) in [(i, t) for rc in set(cells_of) for (ii, t) in cl[rc] if ii == i]): continue
            b = a['box'](a['lines'][i])
            inside_cols = [c for c, (x0, x1) in bands_x.items() if min(x1, b[2]) - max(x0, b[0]) > .3*(b[2]-b[0])]
            if len(inside_cols) == 1:
                u = a['cells'].get(cells_of[-1]) or first
                findings.append(finding(7, f"page {n}: the printed cell {a['lines'][i]['text'][:40]!r} (column {inside_cols[0]}) "
                                           f"is split across grid columns {cols}", page=n, unit=u['id'], offset=u['span'][0],
                                        kind='cell split across columns'))
        # (d) printed body lines in no cell
        if row_band:
            top, bottom = min(row_band.values()), max(row_band.values())
            loose = []
            for i, l in a['lines'].items():
                if i in where: continue
                t = l['text'].strip()
                if re.match(r'(note|notes|key|abbreviation|source|[a-z*†‡§¶#]\s|[a-z]\b|\W)', t, re.I) and band[i] > bottom - 1: continue
                below = band[i] == bottom + 1
                if below and (len(toks(t)) > 8 or not re.search(r'\d', t) or t.endswith('.')): continue   # a note, not a row
                if top <= band[i] <= bottom + 1 and len(toks(t)) >= 2 and not t[:1].islower():
                    loose.append(l)
            if loose:
                findings.append(finding(7, f"page {n}: {len(loose)} printed line(s) of the table body are in no grid cell, "
                                           f"e.g. {loose[0]['text'][:40]!r}", page=n, unit=first['id'], offset=first['span'][0],
                                        kind='printed rows outside the grid', lines=[l['export_id'] for l in loose][:20]))
    # (e) a table caption holding the table's body or running text
    tables = load_json(paper.folder/'copy.tables.json', {}) or {}
    for t in tables.get('tables', []):
        cap = t.get('caption') or ''
        if len(cap.split()) > CAPTION_WORDS:
            head = cap.split('\n')[0][:30]
            u = next((x for x in paper.content_units if x['kind'] in ('caption', 'table_line', 'paragraph') and head and x['text'].startswith(head[:20])), None)
            findings.append(finding(7, f"page {t['page']}: the caption of {cap[:12]!r} holds {len(cap.split())} words: the table's "
                                       f"lines or running text were taken into it", page=t['page'], unit=u['id'] if u else None,
                                    offset=u['span'][0] if u else None, kind='caption holds the table'))
    return findings, dict(stats)
