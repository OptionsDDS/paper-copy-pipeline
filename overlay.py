"""overlay.py -- the spreadsheet grid laid over a table (rules TG1-TG7, lane r8-overlay, round 8).

The fit is the one measured by lane r7-gridfit (out-r7-gridfit/gridfit.py, RULES-OF-THE-FIT.md), brought into the
program. It reads the table as the copy program has it: the printed lines of the table's box (copy_paper.table_lines,
the program's own baselines), their words with their PDF positions, and the drawn rules and fills of the page record.
Where the page record cannot tell a shade (its fills carry no colour), the page render is read (G9b), so shading drawn
as a picture counts too.

All tolerances are in points and the same on every paper; the caller passes the scale (pixels per point).

fit(lines, graphics, k, render=None) -> the grid:
  col_lines   column lines (pixels, table frame), TG1/TG2;
  groups      every group of words: its line, its words, its box, its first and last column (TG3);
  counts      rows, columns, own cells, shared cells, merged cells, set columns, ... (gridfit's counts);
  clean       TG3 holds without a shared cell, every column keeps one setting on every line, few merged cells;
  drawn       per pair of successive printed lines: a drawn line or a change of shading between them (TG7);
  cell_row    per pair: a row line of the overlay's cell rows (G9: drawn, or cells starting level in 2+ columns).
"""
import collections
import math

# T1 limits of the table test, as fixed by lane r7-gridfit on its fixing half (LIMITS-v2.json)
LIMITS = dict(rows_min=2, cols_min=2, own_share_min=0.349, merged_share_max=0.075, empty_share_max=0.493,
              set_columns_min=1)


def _hull(bs):
    bs = list(bs)
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def setting_share(cells):
    """G7: the largest share of lines keeping one left edge, centre or right edge (within 2 pt); a line running the
    column's width (both edges within 2 pt of the column's outer edges) counts with any setting."""
    if not cells:
        return 0.0
    cx0 = min(c[0] for c in cells); cx1 = max(c[2] for c in cells)
    full = sum(1 for c in cells if c[0] - cx0 <= 2 and cx1 - c[2] <= 2)
    rest = [c for c in cells if not (c[0] - cx0 <= 2 and cx1 - c[2] <= 2)]
    if not rest:
        return 1.0
    best = 0
    for kind in range(3):
        v = sorted(c[0] if kind == 0 else (c[2] if kind == 2 else (c[0] + c[2]) / 2) for c in rest)
        j = 0
        for i in range(len(v)):
            while v[i] - v[j] > 4:
                j += 1
            best = max(best, i - j + 1)
    return (best + full) / (len(rest) + full)


def nested_share(cells):
    """the share of lines whose left edge stands on a left edge that two or more lines of the column share (within
    2 pt), and the number of such edges: a column of labels nested by indents keeps its edges on every line"""
    if not cells:
        return 0.0, 0
    xs = sorted(c[0] for c in cells)
    levels = []
    for x in xs:
        if levels and x - levels[-1][-1] <= 2:
            levels[-1].append(x)
        else:
            levels.append([x])
    rec = [lv for lv in levels if len(lv) >= 2]
    return sum(len(lv) for lv in rec) / len(cells), len(rec)


def complete_value(text):
    """a group that is a value: digits with signs and brackets, at most one word of letters (a unit or a mark)"""
    import re
    t = text.strip()
    return bool(re.search(r'\d', t)) and not re.search(r'[^\W\d_]{3,}', t) and not re.search(r'[-‐–—/(\[,±+]$', t)


def _split_group(g, lines):
    """W4: a group whose word gap holds a column line is parted there (a word is never cut)."""
    cuts = [x for x in lines if g['box'][0] + 1 < x < g['box'][2] - 1 and not any(w[0] < x < w[1] for w in g['wx'])]
    if not cuts:
        return [g]
    out = []; cur = []
    for w in g['wx']:
        if cur and any(cur[-1][1] <= x <= w[0] for x in cuts):
            out.append(cur); cur = []
        cur.append(w)
    out.append(cur)
    res = []
    for ws in out:
        h = dict(g)
        h['box'] = [ws[0][0], g['box'][1], ws[-1][1], g['box'][3]]
        h['wx'] = ws; h['fw'] = ws[0][1] - ws[0][0]; h['part'] = len(res)
        h['items'] = [w[3] for w in ws]
        res.append(h)
    return res


def groups_of(lines, vlines, size_of):
    """W3: a printed line is cut into groups at a white gap wider than max(1.2 em, 6 pt) and at a drawn vertical line
    that crosses it. lines: [[(box_pt, item_index)]] per printed line, sorted left to right; size_of(item) in pt."""
    out = []
    for li, L in enumerate(lines):
        cur = []
        for b, ii in L:
            if cur:
                pb = cur[-1][0]
                gap = b[0] - pb[2]
                cy = (b[1] + b[3]) / 2
                cut = gap > max(1.2 * max(size_of(ii), size_of(cur[-1][1])), 6)
                if not cut:
                    cut = any(pb[2] - 0.5 <= (v[0] + v[2]) / 2 <= b[0] + 0.5 and v[1] <= cy <= v[3] for v in vlines)
                if cut:
                    out.append(_make(li, cur, size_of)); cur = []
            cur.append((b, ii))
        if cur:
            out.append(_make(li, cur, size_of))
    for i, g in enumerate(out):
        g['i'] = i
    return out


def _make(li, cur, size_of):
    sizes = collections.Counter(round(size_of(ii) * 4) / 4 for b, ii in cur)
    return {'line': li, 'box': _hull(b for b, ii in cur), 'size': sizes.most_common(1)[0][0],
            'fw': cur[0][0][2] - cur[0][0][0], 'wx': [[b[0], b[2], b, ii] for b, ii in cur], 'items': [ii for b, ii in cur]}


def fit(lines, graphics, k, render=None, size_of=None):
    """lines: the program's printed lines of the table (dicts with 'items' [(box_px, text, run)], in the table frame);
    graphics: [(box_px, kind)] the page record's rules and fills in that frame; k: pixels per point;
    render: None, or page_render()'s readers: shade_change(ya, yb, x0, x1, holes) and line(y0, y1, x0, x1) -> the
    share of the width a dark line covers (G9b); with a render, the render alone decides the drawn row borders.
    Returns the grid in pixels (see the module text) or None."""
    if not lines:
        return None
    P = lambda b: [v / k for v in b]
    items = [it for L in lines for it in L['items']]
    if size_of is None:
        size_of = lambda ii: (items[ii][0][3] - items[ii][0][1]) / k * 0.75
    idx = 0; plines = []
    for L in lines:
        row = []
        for it in L['items']:
            row.append((P(it[0]), idx)); idx += 1
        plines.append(sorted(row, key=lambda t: t[0][0]))
    objs = []
    for b, kind in graphics:
        q = P(b)
        if kind == 'rule':
            objs.append({'kind': 'hline' if (q[2] - q[0]) >= (q[3] - q[1]) else 'vline', 'box': q})
        else:
            objs.append({'kind': 'rect', 'box': q})
    vls_all = [o['box'] for o in objs if o['kind'] == 'vline' and (o['box'][3] - o['box'][1]) >= 6]
    G = groups_of(plines, vls_all, size_of)
    text_of = lambda g: ' '.join(items[ii][1] for ii in g['items'])
    if not G:
        return None
    nr = len(plines)
    rows = [{'g': [g for g in G if g['line'] == r]} for r in range(nr)]
    rows = [r for r in rows if r['g']]
    if len(rows) < 2:
        return None
    for r in rows:
        r['core'] = (min(g['box'][1] for g in r['g']), max(g['box'][3] for g in r['g']))
    hs = sorted(g['box'][3] - g['box'][1] for g in G)
    hmed = hs[len(hs) // 2]

    def columns(rws):
        X0 = min(g['box'][0] for r in rws for g in r['g']); X1 = max(g['box'][2] for r in rws for g in r['g'])
        multi = [r for r in rws if len(r['g']) >= 2]
        n = len(multi)
        lim = max(1, int(0.15 * n)) if n >= 4 else 0
        lo = math.floor(X0 * 2); hi = math.ceil(X1 * 2)
        cov = [0] * (hi - lo + 1)
        for r in multi:
            seen = set()
            for g in r['g']:
                for w in g['wx']:
                    for x in range(int(w[0] * 2) - lo, int(math.ceil(w[1] * 2)) - lo + 1):
                        if 0 <= x < len(cov):
                            seen.add(x)
            for x in seen:
                cov[x] += 1
        ry0 = rws[0]['core'][0]; ry1 = rws[-1]['core'][1]
        vls = [(o['box'][0] + o['box'][2]) / 2 for o in objs if o['kind'] == 'vline' and X0 + 1 < (o['box'][0] + o['box'][2]) / 2 < X1 - 1 and
               min(o['box'][3], ry1) - max(o['box'][1], ry0) >= 0.5 * (ry1 - ry0)]
        shade = sorted(set(x for o in objs if o['kind'] == 'rect' and (o['box'][3] - o['box'][1]) >= 0.6 * hmed
                           for x in (o['box'][0], o['box'][2])))
        out = []
        i = 0
        while i < len(cov):
            if cov[i] <= lim and i > 0:
                j = i
                while j < len(cov) and cov[j] <= lim:
                    j += 1
                if j < len(cov) and (j - i) >= 6:   # G2: 3 pt or wider, closed on both sides
                    a, b = (i + lo) / 2, (j + lo) / 2
                    m = min(cov[i:j])
                    best = None; q = i
                    while q < j:
                        if cov[q] == m:
                            e = q
                            while e < j and cov[e] == m:
                                e += 1
                            if best is None or e - q > best[1] - best[0]:
                                best = (q, e)
                            q = e
                        else:
                            q += 1
                    sa, sb = (best[0] + lo) / 2, (best[1] + lo) / 2
                    x = next((v for v in vls if a - 0.5 <= v <= b + 0.5), None)
                    if x is None:
                        x = next((s for s in shade if sa + 0.5 <= s <= sb - 0.5), None)
                    if x is None:
                        x = (sa + sb) / 2
                    out.append(round(x, 2))
                i = j
            else:
                i += 1

        # G2c: a strip 0.5 to 3 pt wide is a column line when the words on each side keep one setting in 60% of 3+ rows
        # and a header cell (a whole group) stands over each side in one of the top 5 rows
        def side_ok(es):
            return len(es) >= 3 and setting_share([[e[0], 0, e[1], 0] for e in es]) >= 0.6
        i = 0
        while i < len(cov):
            if cov[i] <= lim and i > 0:
                j = i
                while j < len(cov) and cov[j] <= lim:
                    j += 1
                if j < len(cov) and 1 <= (j - i) < 6:
                    a, b = (i + lo) / 2, (j + lo) / 2
                    L_, R_ = [], []
                    for r in multi:
                        wl = [w for g in r['g'] for w in g['wx'] if w[1] <= a + 0.5 and a - w[1] <= 30]
                        wr = [w for g in r['g'] for w in g['wx'] if w[0] >= b - 0.5 and w[0] - b <= 30]
                        if wl and wr:
                            L_.append(max(wl, key=lambda w: w[1])); R_.append(min(wr, key=lambda w: w[0]))
                    head = False
                    if L_:
                        lx0 = min(w[0] for w in L_); lx1 = max(w[1] for w in L_); rx0 = min(w[0] for w in R_); rx1 = max(w[1] for w in R_)
                        for r in rws[:5]:
                            gb_ = [g['box'] for g in r['g']]
                            if any(w[2] <= a + 0.5 and min(w[2], lx1) - max(w[0], lx0) > 0 for w in gb_) and \
                               any(w[0] >= b - 0.5 and min(w[2], rx1) - max(w[0], rx0) > 0 for w in gb_) and r not in multi[len(multi) // 2:]:
                                head = True; break
                    if len(L_) >= 3 and side_ok(L_) and side_ok(R_) and head:
                        out.append(round((a + b) / 2, 2))
                i = j
            else:
                i += 1
        for v in vls:   # a drawn vertical line past half the height always parts columns
            if all(abs(v - x) > 2 for x in out):
                out.append(round(v, 2))
        out.sort()
        # G2b: a white strip leaving a column of fewer than 2 printed lines beside it is no column line (drawn lines stay)
        while True:
            ed = [X0] + out + [X1]
            sg = [h for r in rws for g in r['g'] for h in _split_group(g, out)]
            cnt = [sum(1 for g in sg if ed[c] - 1 <= g['box'][0] and g['box'][2] <= ed[c + 1] + 1) for c in range(len(ed) - 1)]
            weak = [li for li in range(len(out)) if (cnt[li] < 2 or cnt[li + 1] < 2) and all(abs(out[li] - v) > 2 for v in vls)]
            if not weak:
                break
            li = min(weak, key=lambda li: min(cnt[li], cnt[li + 1]))
            out.pop(li)
        # TG2: a column line never cuts a group of words; a drawn vertical line may part one (W3), a white strip not
        free = [x for x in out if all(abs(x - v) > 2 for v in vls)]
        cut = sum(1 for r in rws for g in r['g'] if len(_split_group(g, free)) > 1)
        for r in rws:
            r['g'] = [h for g in r['g'] for h in _split_group(g, out)]
        return out, X0, X1, cut

    lines_pt, X0, X1, groups_cut = columns(rows)
    nc = len(lines_pt) + 1
    cells = []
    for ri, r in enumerate(rows):
        for g in r['g']:
            c0 = sum(1 for x in lines_pt if x < g['box'][0] + 1)
            c1 = max(c0, sum(1 for x in lines_pt if x < g['box'][2] - 1))
            cells.append((ri, c0, c1, g))
    occ = collections.defaultdict(list); merged = []
    for ri, c0, c1, g in cells:
        (occ[(ri, c0)].append(g) if c0 == c1 else merged.append((ri, c0, c1, g)))
    covered = set(occ)
    for ri, c0, c1, g in merged:
        covered.update((ri, c) for c in range(c0, c1 + 1))
    own = sum(1 for v in occ.values() if len(v) == 1)
    shared = sum(1 for v in occ.values() if len(v) >= 2)
    nrows = len(rows)
    setc = 0; colinfo = []
    edges = [X0] + lines_pt + [X1]
    for c in range(nc):
        cs = [g['box'] for key, v in occ.items() if key[1] == c for g in v]
        sh = setting_share(cs)
        st = len(cs) >= 3 and sh >= 0.5
        setc += int(st)
        ns, nlev = nested_share(cs)
        colinfo.append({'x0': edges[c], 'x1': edges[c + 1], 'cells': len(cs), 'set_share': round(sh, 3), 'set': st,
                        'one_setting': sh >= 1.0 or (ns >= 1.0 and nlev <= 3)})
    box = _hull(g['box'] for r in rows for g in r['g'])
    Wb = box[2] - box[0]
    # G9: row borders between successive printed lines: a drawn line over 30% of the width, or a change of shading
    hedges = [((o['box'][1] + o['box'][3]) / 2, o['box'][0], o['box'][2]) for o in objs if o['kind'] == 'hline']
    drawn = []; drawn_why = []
    drawn_cover = []; shade2 = []
    for q in range(nrows - 1):
        ya = rows[q]['core'][1]; yb = rows[q + 1]['core'][0]
        lo_, hi_ = min(ya, yb) - 1, max(ya, yb) + 1
        why = []; cover = 0.0
        if render:
            # the page as printed: a dark line across the white between the two lines, or a change of shading read at
            # the same places of both lines (outside the words of either), so that cell-wise shading is compared
            # column by column; a rule of the record may be drawn white, so the render decides
            cover = render['line'](lo_ * k, hi_ * k, box[0] * k, box[2] * k)
            if cover >= 0.3:
                why.append('ink')
            # TG13: a white gap line between two shaded cells is a border like a drawn line
            if 'ink' not in why and render['gap'](lo_ * k, hi_ * k, box[0] * k, box[2] * k):
                why.append('gap')
            holes = [[v * k for v in g['box']] for g in rows[q]['g'] + rows[q + 1]['g']]
            if render['shade_change']((rows[q]['core'][0] + rows[q]['core'][1]) / 2 * k,
                                      (rows[q + 1]['core'][0] + rows[q + 1]['core'][1]) / 2 * k, box[0] * k, box[2] * k, holes):
                why.append('shade')
        else:
            ln = sum(max(0, min(x1, box[2]) - max(x0, box[0])) for y, x0, x1 in hedges if lo_ <= y <= hi_)
            cover = ln / Wb if Wb else 0
            if cover >= 0.3:
                why.append('rule')
        drawn.append(bool(why)); drawn_why.append(why); drawn_cover.append(round(min(cover, 1.0), 3))
        if render and 'shade_change2' in render:
            holes2 = [[v * k for v in g['box']] for g in rows[q]['g'] + rows[q + 1]['g']]
            shade2.append(render['shade_change2']((rows[q]['core'][0] + rows[q]['core'][1]) / 2 * k,
                                                  (rows[q + 1]['core'][0] + rows[q + 1]['core'][1]) / 2 * k, box[0] * k, box[2] * k, holes2))
        else:
            shade2.append(False)
    # TG10: row groups by shading: the shade of each row, and the bands (runs of rows under one shade, shaded)
    row_tint = [None] * nrows; bands = []
    if render:
        row_tint = [render['tint']((r['core'][0] + r['core'][1]) / 2 * k, box[0] * k, box[2] * k, [[v * k for v in g['box']] for g in r['g']])
                    for r in rows]
        q = 0
        while q < nrows:
            if row_tint[q] is None:
                q += 1; continue
            e = q
            while e + 1 < nrows and row_tint[e + 1] is not None and not drawn[e] and abs(row_tint[e + 1] - row_tint[q]) < 12:
                e += 1
            bands.append([q, e]); q = e + 1
    # TG10: a drawn line under a header label marks the columns it stands over: per group, the drawn horizontal line
    # in the white below it (to the next printed line's top) that overlaps it, with that line's x range
    underlines = {}
    if render:
        for q in range(nrows - 1):
            y0 = max(g['box'][3] for g in rows[q]['g']); y1 = min(g['box'][1] for g in rows[q + 1]['g'])
            if y1 <= y0:
                continue
            rs = render['runs'](y0 * k, y1 * k, box[0] * k, box[2] * k)
            for g in rows[q]['g']:
                hit = [r_ for r_ in rs if min(r_[1], g['box'][2] * k) - max(r_[0], g['box'][0] * k) > 0.5 * (g['box'][2] - g['box'][0]) * k
                       and (r_[1] - r_[0]) < 0.95 * Wb * k]
                if hit:
                    underlines[g['i'], g.get('part', 0)] = [round(hit[0][0], 1), round(hit[0][1], 1)]
    # TG14: the coarse grid: the row borders that run the full width (a drawn line over 90% of it, a white gap line or a
    # change of shading) and the column lines that run the full height (a drawn vertical line over 90% of it); the
    # other borders are divisions inside a coarse cell
    full_rows = [q for q in range(nrows - 1) if drawn[q] and (drawn_cover[q] >= 0.9 or 'shade' in drawn_why[q] or 'gap' in drawn_why[q])]
    full_cols = []
    if render:
        full_cols = [ci for ci, x in enumerate(lines_pt) if render['vline'](x * k, box[1] * k, box[3] * k) >= 0.9]
    else:
        full_cols = [ci for ci, x in enumerate(lines_pt) if any(abs((o['box'][0] + o['box'][2]) / 2 - x) <= 2 and o['box'][3] - o['box'][1] >= 0.9 * (box[3] - box[1])
                                                           for o in objs if o['kind'] == 'vline')]
    # cell rows: a row line also stands where the next printed line has groups starting a cell in two or more columns
    colR = {}
    for ri, c0, c1, g in cells:
        if c0 == c1:
            colR[c0] = max(colR.get(c0, -1e9), g['box'][2])

    def starts(q, c0, g):
        above = [h for r2, a0, a1, h in cells if r2 == q - 1 and a0 <= c0 <= a1]
        if not above:
            return True
        a = max(above, key=lambda h: h['box'][2])
        # a value under a value starts a cell: a complete value never goes on in the line below
        if text_of and complete_value(text_of(g)) and complete_value(text_of(a)):
            return True
        return a['box'][2] + 0.3 * g['size'] + g.get('fw', 0) < colR.get(c0, a['box'][2]) - 1
    startcols = [set(c0 for r2, c0, c1, g in cells if r2 == q and starts(q, c0, g)) for q in range(nrows)]
    cell_row = [drawn[q] or len(startcols[q + 1]) >= 2 for q in range(nrows - 1)]
    crow = [0]
    for q in range(nrows - 1):
        crow.append(crow[-1] + int(cell_row[q]))
    nrb = crow[-1] + 1
    cov_b = set((crow[ri], c) for ri, c0, c1, g in cells for c in range(c0, c1 + 1))
    ng = len(cells)
    counts = {'rows': nrows, 'cols': nc, 'groups': ng, 'own_cell': own, 'own_share': round(own / ng, 3) if ng else 0,
              'shared_cells': shared, 'merged': len(merged), 'merged_share': round(len(merged) / ng, 3) if ng else 0,
              'set_columns': setc, 'cell_rows': nrb, 'empty_share_b': round((nrb * nc - len(cov_b)) / (nrb * nc), 3),
              'drawn_row_borders': sum(drawn), 'groups_cut': groups_cut}
    test = (counts['rows'] >= LIMITS['rows_min'] and counts['cols'] >= LIMITS['cols_min'] and
            counts['own_share'] >= LIMITS['own_share_min'] and counts['merged_share'] <= LIMITS['merged_share_max'] and
            counts['empty_share_b'] <= LIMITS['empty_share_max'] and counts['set_columns'] >= LIMITS['set_columns_min'])
    # clean (the brief's fit): every group in one cell of its own or a merged cell, few merged cells, and every
    # column of two or more lines keeping one setting on every line
    # TF5: neighbouring columns stand level: each pair of neighbouring columns holds cells side by side on two rows
    level = all(sum(1 for ri in range(nrows) if (ri, c) in occ and (ri, c + 1) in occ) >= 2 for c in range(nc - 1))
    counts['columns_level'] = level
    clean = (test and shared == 0 and groups_cut == 0 and level and all(c['one_setting'] for c in colinfo if c['cells'] >= 2)
             and all(c['cells'] >= 2 for c in colinfo))
    line_of_row = [r['g'][0]['line'] for r in rows]
    groups_out = [{'line': g['line'], 'gi': g['i'], 'row': ri, 'col': c0, 'col_end': c1, 'items': g['items'],
                   'box': [v * k for v in g['box']], 'underline': underlines.get((g['i'], g.get('part', 0)))} for ri, c0, c1, g in cells]
    return {'col_lines': [x * k for x in lines_pt], 'x0': X0 * k, 'x1': X1 * k, 'box': [v * k for v in box],
            'groups': groups_out, 'counts': counts, 'test': test, 'clean': clean, 'columns': colinfo,
            'row_y': [(rows[q]['core'][1] + rows[q + 1]['core'][0]) / 2 * k for q in range(nrows - 1)],
            'line_of_row': line_of_row, 'drawn': drawn, 'drawn_cover': drawn_cover, 'drawn_why': drawn_why, 'cell_row': cell_row,
            'shade2': shade2,
            'row_rgb': [render['tint_rgb']((r['core'][0] + r['core'][1]) / 2 * k, box[0] * k, box[2] * k, [[v * k for v in g['box']] for g in r['g']])
                        for r in rows] if (render and 'tint_rgb' in render) else [None] * nrows,
            'coarse_rows': full_rows, 'coarse_cols': full_cols, 'rendered': bool(render), 'row_tint': row_tint, 'bands': bands, 'underlines': underlines}


def page_render(pdf, page_no, dpi, crop_x0_pt, crop_dy_pt, to_render=None):
    """G9b: the page rendered grey at the record's dpi; returns {'shade_change', 'line', 'ink'} readers in page pixels.
    crop_x0_pt, crop_dy_pt: the shift from the record's frame to the render's (CropBox) frame, in points.
    to_render (lane r8-turned): where given, a map from the reader's point (x, y) to the render's pixel (X, Y), so that
    the readers work in a turned table's upright frame on a page turned by its flag or set sideways (the shift is then
    not used)."""
    import re
    import subprocess
    try:
        res = subprocess.run(['pdftoppm', '-f', str(page_no), '-l', str(page_no), '-singlefile', '-gray', '-cropbox',
                              '-r', str(dpi), pdf], capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.match(rb'P5\s+(\d+)\s+(\d+)\s+255\s', res.stdout)
    if res.returncode or not m:
        return None
    W, H = map(int, m.groups())
    px = res.stdout[m.end():]
    if len(px) != W * H:
        return None
    s = dpi / 72.0
    dx, dy = -crop_x0_pt * s, crop_dy_pt * s

    def at(x, y):
        if to_render is not None:
            X, Y = to_render(x, y); X, Y = int(X), int(Y)
        else:
            X, Y = int(x + dx), int(y + dy)
        return px[Y * W + X] if 0 <= X < W and 0 <= Y < H else None

    colour = {}

    def rgb_at(x, y):
        """(pass 3) the page in colour, rendered once on first use: the colour of a place, or None"""
        if 'px' not in colour:
            try:
                r_ = subprocess.run(['pdftoppm', '-f', str(page_no), '-l', str(page_no), '-singlefile', '-cropbox',
                                     '-r', str(dpi), pdf], capture_output=True, timeout=120)
                m_ = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255\s', r_.stdout)
                colour['px'] = r_.stdout[m_.end():] if (m_ and not r_.returncode and tuple(map(int, m_.groups())) == (W, H)) else None
            except (OSError, subprocess.SubprocessError):
                colour['px'] = None
        cp = colour['px']
        if cp is None:
            return None
        if to_render is not None:
            X, Y = to_render(x, y); X, Y = int(X), int(Y)
        else:
            X, Y = int(x + dx), int(y + dy)
        if not (0 <= X < W and 0 <= Y < H):
            return None
        o = (Y * W + X) * 3
        return tuple(cp[o:o + 3])

    def flat_rgb(x, y):
        """the colour of a place with no ink within 2 pixels (grey 140 or lighter all round), else None"""
        for ddx in (-2, 0, 2):
            for ddy in (-2, 0, 2):
                v = at(x + ddx, y + ddy)
                if v is None or v < 140:
                    return None
        return rgb_at(x, y)

    def shade_change2(ya, yb, x0, x1, holes):
        """(pass 3) a change of shading whatever its strength: along both lines' centres, at the same flat places
        outside the words of either line, the colours differ (6 levels or more in some channel) at half the places or
        more, and the places are tinted (some channel under 243) on at least one line. Colour, not grey: a pale yellow
        band beside a deeper yellow one differs by 9 grey levels only (AQ18 p4)"""
        diff = n = tinted = 0
        x = x0
        while x <= x1:
            if not any(b[0] - s <= x <= b[2] + s for b in holes):
                a, b = flat_rgb(x, ya), flat_rgb(x, yb)
                if a is not None and b is not None:
                    n += 1
                    if max(abs(a[i] - b[i]) for i in range(3)) >= 6:
                        diff += 1
                    if min(min(a), min(b)) < 243:
                        tinted += 1
            x += 2 * s
        return n >= 5 and diff >= 0.5 * n and tinted >= 0.5 * n

    def tint_rgb(y, x0, x1, holes):
        """(pass 3) the colour of a row: the median colour of its flat places outside its words when half of them or
        more are tinted (some channel under 243), else None"""
        vals = []
        x = x0
        while x <= x1:
            if not any(b[0] - s <= x <= b[2] + s for b in holes):
                v = flat_rgb(x, y)
                if v is not None:
                    vals.append(v)
            x += 2 * s
        if len(vals) < 5:
            return None
        t = [v for v in vals if min(v) < 243]
        if len(t) < 0.5 * len(vals):
            return None
        return tuple(sorted(v[i] for v in t)[len(t) // 2] for i in range(3))

    def shade_change(ya, yb, x0, x1, holes):
        """a change of shading between two printed lines: along both lines' centres, at the same places outside the
        words of either line and off ink (pixels under 140 on either line are left out), the tints differ (by 12 grey
        levels or more) at half the places or more, and the places are tinted (under 243) on at least one line"""
        diff = n = tinted = 0
        x = x0
        while x <= x1:
            if not any(b[0] - s <= x <= b[2] + s for b in holes):
                a, b = at(x, ya), at(x, yb)
                if a is not None and b is not None and min(a, b) >= 140:   # ink (a rule, a letter) is no shade
                    n += 1
                    if abs(a - b) >= 12:
                        diff += 1
                    if min(a, b) < 243:
                        tinted += 1
            x += 2 * s
        return n >= 5 and diff >= 0.5 * n and tinted >= 0.5 * n

    def line(y0, y1, x0, x1):
        """a drawn line across the white between two printed lines: on one pixel row, dark pixels (under 128) in runs
        of 5 pt or longer (letters never make such runs); returns the largest share of the width so covered"""
        n = max(1, int((x1 - x0) / s))
        best = 0.0
        for Y in range(int(math.floor(y0)), int(math.ceil(y1)) + 1):
            dark = run = 0
            for q in range(n + 1):
                v = at(x0 + q * s, Y) if q < n else None
                if v is not None and v < 128:
                    run += 1
                else:
                    if run >= 5:
                        dark += run
                    run = 0
            best = max(best, dark / n)
        return best

    def ink(box):
        """the darkest pixel in a box (the alignment witness: a word's box holds ink)"""
        vals = [at(x, y) for y in range(int(box[1]), int(box[3]) + 1, max(1, int(s)))
                for x in range(int(box[0]), int(box[2]) + 1, max(1, int(s)))]
        vals = [v for v in vals if v is not None]
        return min(vals) if vals else 255
    def tint(y, x0, x1, holes):
        """the shade of a row (TG10): along its centre, outside its words and off ink, the median grey; shaded when
        half the places or more are tinted (under 243). Returns the median grey when shaded, else None."""
        vals = []
        x = x0
        while x <= x1:
            if not any(b[0] - s <= x <= b[2] + s for b in holes):
                v = at(x, y)
                if v is not None and v >= 140:
                    vals.append(v)
            x += 2 * s
        if len(vals) < 5:
            return None
        t = sorted(v for v in vals if v < 243)
        return t[len(t) // 2] if len(t) >= 0.5 * len(vals) else None

    def gap(y0, y1, x0, x1):
        """a white gap line between shaded cells: on one pixel row of the band, white (243 or lighter) over 30% of the
        width at places where the pixel rows 2 pt above and 2 pt below the band are both tinted (140..242)"""
        n = max(1, int((x1 - x0) / s)); best = 0
        for Y in range(int(math.floor(y0)), int(math.ceil(y1)) + 1):
            w = 0
            for q in range(n):
                x = x0 + q * s
                v, a, b = at(x, Y), at(x, y0 - 2 * s), at(x, y1 + 2 * s)
                if v is not None and a is not None and b is not None and v >= 243 and 140 <= a <= 242 and 140 <= b <= 242:
                    w += 1
            best = max(best, w)
        return best >= 0.3 * n

    def vline(x, y0, y1):
        """a drawn vertical line at x (within 2 pt): the share of the band's height a dark column of pixels covers"""
        best = 0.0; H = max(1, int((y1 - y0) / s))
        for dx in range(-2, 3):
            d = sum(1 for q in range(H) if (lambda v: v is not None and v < 128)(at(x + dx * s, y0 + q * s)))
            best = max(best, d / H)
        return best

    def runs(y0, y1, x0, x1):
        """the drawn horizontal lines in a band: on each pixel row, runs of dark pixels (under 128) of 5 pt or more;
        returns their x ranges (merged over the band's rows)"""
        out = []
        n = max(1, int((x1 - x0) / s))
        for Y in range(int(math.floor(y0)), int(math.ceil(y1)) + 1):
            run = 0
            for q in range(n + 1):
                v = at(x0 + q * s, Y) if q < n else None
                if v is not None and v < 128:
                    run += 1
                else:
                    if run >= 5:
                        out.append((x0 + (q - run) * s, x0 + q * s))
                    run = 0
        out.sort(); merged = []
        for a, b in out:
            if merged and a <= merged[-1][1] + s:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        return merged
    return {'shade_change': shade_change, 'line': line, 'ink': ink, 'tint': tint, 'runs': runs, 'gap': gap, 'vline': vline,
            'shade_change2': shade_change2, 'tint_rgb': tint_rgb}
