"""Rule 1: ink accounting from the page image (independent of the text layer and the boxer).

Each page is rendered at 150 dpi (pdftoppm, annotations hidden) in the MediaBox
frame. Dark pixels (grey < 150) are joined into connected components; specks,
rules, sparse line art and graphics larger than letters are dropped, and so is
ink outside the crop box, inside figure images, small figure floats, journal
art, figure graphics (images, outlines, fills and rules within an em of each
other) and continuous-tone or halftone picture tiles. Letter components are
grouped into word boxes by white space (a gap under about half an em joins
letters; letters stacked on one vertical axis are rotated text and set aside).

Every letter must lie on a source run of a line the trace places in the copy,
or on furniture the page justifies: a line in the top 12% or bottom 14% of the
page, beside the text columns, figure lettering within two ems of a figure, or
a recurring head/foot, folio, licence or journal line (other furniture inside
the text area is not trusted). On OCR pages a placed word explains its whole
printed row, because OCR boxes drift. Word boxes left over, on lines outside
the header and footer bands (inside a float only lines of four or more words
over ten ems), are listed per page with their boxes: the copy lost or never
placed that ink (the right edge of a column cut by a wrong page frame, a page
whose text became the lettering of a page-sized figure, text with no text
layer).
"""
import re
import subprocess

from common import DPI, GOOD_LINE, area, finding, inside, overlap

NAME = 'ink accounting'
THRESHOLD = 150           # grey level below which a pixel is ink
TRUSTED_FURNITURE = re.compile(r'same text|recurring|repeated margin|margin|page number|folio|line numbers|'
                               r'licen[cs]e|copyright|publication footer|DOI|journal|download|rotated sidebar|'
                               r'outside the page text frame|divider', re.I)
LETTERING = re.compile(r'letter|figure', re.I)


def render(pdf, page):
    """Grey PGM of one page at 150 dpi: (width, height, bytes)."""
    data = subprocess.run(['pdftoppm', '-r', str(DPI), '-gray', '-hide-annotations', '-f', str(page), '-l', str(page), pdf],
                          capture_output=True, timeout=180).stdout
    m = re.match(rb'P5\s+(\d+)\s+(\d+)\s+(\d+)\s', data)
    if not m: return None
    w, h = int(m.group(1)), int(m.group(2))
    return w, h, data[m.end():m.end()+w*h]


def components(w, h, pixels):
    """Connected ink components (8-neighbour) as [x0, y0, x1, y1, ink pixels]."""
    table = bytes(1 if i < THRESHOLD else 0 for i in range(256))
    ink = pixels.translate(table)
    parent = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    runs = []  # (y, x0, x1)
    prev = []  # indices of runs on previous row
    one = re.compile(b'\x01+')
    for y in range(h):
        row = ink[y*w:(y+1)*w]
        cur = []
        if 1 in row:
            j = 0
            for m in one.finditer(row):
                x0, x1 = m.start(), m.end()-1
                k = len(runs); runs.append((y, x0, x1)); parent.append(k); cur.append(k)
                while j < len(prev) and runs[prev[j]][2] < x0-1: j += 1
                t = j
                while t < len(prev) and runs[prev[t]][1] <= x1+1:
                    a, b = find(k), find(prev[t])
                    if a != b: parent[a] = b
                    t += 1
        prev = cur
    comps = {}
    for k, (y, x0, x1) in enumerate(runs):
        r = find(k); c = comps.get(r)
        if c is None: comps[r] = [x0, y, x1+1, y+1, x1-x0+1]
        else:
            if x0 < c[0]: c[0] = x0
            if x1+1 > c[2]: c[2] = x1+1
            c[3] = y+1; c[4] += x1-x0+1
    return list(comps.values())


def graphic_regions(paper, n, em):
    """Figure graphics drawn on the page: images, outlines, rules and fills joined
    when they lie within one em of each other. A region is a graphic when it holds
    an image or an outline, three fills, or twenty rules (axes and ticks), is at
    least six ems on a side, is under half the page, and is not mostly a table float.
    """
    page = paper.page(n) or {}
    page_area = area(paper.crop_px(n) or paper.media_px(n) or [0, 0, 1e9, 1e9])
    items = [(e['kind'], e['box_px']) for e in paper.elements(n).values()
             if e.get('kind') in ('image', 'outline', 'rule', 'fill') and e.get('box_px') and area(e['box_px']) < .5*page_area]
    regions = []  # [box, kinds Counter]
    for kind, b in sorted(items, key=lambda kb: (kb[1][1], kb[1][0])):
        hit = None
        for r in regions:
            rb = r[0]
            if b[0] <= rb[2]+em and rb[0] <= b[2]+em and b[1] <= rb[3]+em and rb[1] <= b[3]+em:
                hit = r; break
        if hit is None: regions.append([list(b), {kind: 1}])
        else:
            rb = hit[0]; rb[0] = min(rb[0], b[0]); rb[1] = min(rb[1], b[1]); rb[2] = max(rb[2], b[2]); rb[3] = max(rb[3], b[3])
            hit[1][kind] = hit[1].get(kind, 0) + 1
    # regions grown by later members can now touch: merge to a fixed point
    merged = True
    while merged:
        merged = False
        for i in range(len(regions)):
            for j in range(i+1, len(regions)):
                a, b = regions[i][0], regions[j][0]
                if b[0] <= a[2]+em and a[0] <= b[2]+em and b[1] <= a[3]+em and a[1] <= b[3]+em:
                    a[0] = min(a[0], b[0]); a[1] = min(a[1], b[1]); a[2] = max(a[2], b[2]); a[3] = max(a[3], b[3])
                    for k, v in regions[j][1].items(): regions[i][1][k] = regions[i][1].get(k, 0) + v
                    del regions[j]; merged = True; break
            if merged: break
    tables = [paper.moved(f['box_px'], n) for f in page.get('floats', []) if f.get('box_px')
              and str(f.get('caption', '')).lower().startswith('tab')]
    out = []
    for b, kinds in regions:
        if not (kinds.get('image') or kinds.get('outline') or kinds.get('fill', 0) >= 3 or kinds.get('rule', 0) >= 20): continue
        if b[2]-b[0] < 6*em or b[3]-b[1] < 6*em or area(b) >= .5*page_area: continue
        if any(overlap(b, t) > .5*area(b) for t in tables): continue
        out.append(b)
    return out


TILE = 24


def photo_tiles(w, h, pixels):
    """Tiles of continuous-tone or dense halftone pictures (scanned figures).

    A 24-pixel tile is pictorial when over a quarter of its pixels are mid-grey
    (60-200) or over 45% are ink; printed text has crisp letters on white.
    Only regions of at least twelve touching pictorial tiles count, grown by one
    tile, so bold headings and rules never become pictures.
    """
    mid_t = bytes(1 if 60 <= i < 200 else 0 for i in range(256))
    ink_t = bytes(1 if i < THRESHOLD else 0 for i in range(256))
    mid, ink = pixels.translate(mid_t), pixels.translate(ink_t)
    tw, th = (w+TILE-1)//TILE, (h+TILE-1)//TILE
    flag = set()
    for ty in range(th):
        y0, y1 = ty*TILE, min(h, (ty+1)*TILE)
        for tx in range(tw):
            x0, x1 = tx*TILE, min(w, (tx+1)*TILE)
            m = k = 0
            for y in range(y0, y1):
                a = y*w
                m += mid.count(1, a+x0, a+x1); k += ink.count(1, a+x0, a+x1)
            n = (y1-y0)*(x1-x0)
            if m > .25*n or k > .45*n: flag.add((tx, ty))
    keep, seen = set(), set()
    for t in flag:
        if t in seen: continue
        stack, region = [t], []
        seen.add(t)
        while stack:
            a = stack.pop(); region.append(a)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    b = (a[0]+dx, a[1]+dy)
                    if b in flag and b not in seen: seen.add(b); stack.append(b)
        if len(region) >= 12: keep.update(region)
    grown = {(x+dx, y+dy) for x, y in keep for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return grown


def drawn_graphics(comps, em, tables=()):
    """Charts drawn on the page without a recorded graphic (the image's own evidence).

    Components larger than letters (bars, axes, frames) within one em of each
    other form a region; a region of six ems or more on each side holding a
    solid fill (ink over half its box, half an em thick), three drawn shapes
    (more than an em in both directions, not straight rules) or twelve such
    components is a chart or drawing. Regions mostly over a table float are left out, so
    ruled tables keep their letters.
    """
    big = [c for c in comps if (c[3]-c[1] > 2.2*em or c[2]-c[0] > 4*em)]
    regions = []
    for c in sorted(big, key=lambda c: (c[1], c[0])):
        solid = (c[4] > .5*(c[2]-c[0])*(c[3]-c[1]) and min(c[2]-c[0], c[3]-c[1]) > .5*em)
        drawn = min(c[2]-c[0], c[3]-c[1]) > em        # a curve or outline, not a straight rule
        for r in regions:
            b = r[0]
            if c[0] <= b[2]+em and b[0] <= c[2]+em and c[1] <= b[3]+em and b[1] <= c[3]+em:
                b[0] = min(b[0], c[0]); b[1] = min(b[1], c[1]); b[2] = max(b[2], c[2]); b[3] = max(b[3], c[3])
                r[1] += 1; r[2] |= solid; r[3] += drawn; break
        else:
            regions.append([list(c[:4]), 1, solid, int(drawn)])
    out = []
    for b, count, solid, curves in regions:
        if b[2]-b[0] < 6*em or b[3]-b[1] < 6*em or not (solid or count >= 12 or curves >= 3): continue
        if any(overlap(b, t) > .5*area(b) for t in tables): continue
        out.append(b)
    return out


def explaining_boxes(paper, n):
    """Runs the copy placed or the page justifies as furniture; and figure masks.

    Returns (boxes, masks, doubtful): doubtful are furniture lines in the text
    area that the page does not justify (listed in the finding's evidence).
    """
    page = paper.page(n) or {}
    media = paper.media_px(n) or [0, 0, 1e9, 1e9]
    height = media[3]; page_area = area(paper.crop_px(n) or media)
    els = paper.elements(n)
    images = [e['box_px'] for e in els.values() if e.get('kind') == 'image'
              and area(e['box_px']) < .6*page_area]
    small_floats = [paper.moved(f['box_px'], n) for f in page.get('floats', []) if f.get('box_px')
                    and area(f['box_px']) < .45*page_area and not str(f.get('caption', '')).lower().startswith('table')]
    small_floats += graphic_regions(paper, n, paper.body_size(n))
    figure_masks = images + small_floats
    art = [paper.moved(a['box_px'], n) for a in page.get('art', []) if a.get('box_px') and area(a['box_px']) < .05*page_area]
    cols = paper.columns(n)
    left = min((c[0] for c in cols), default=None); right = max((c[1] for c in cols), default=None)
    boxes, doubtful = [], []
    for line in paper.trace['lines']:
        if line['page'] != n: continue
        status = line['status']
        rb = paper.run_boxes(line)
        if status in GOOD_LINE:
            boxes.extend(rb); continue
        if status != 'furniture': continue
        reason = line.get('furniture_reason') or ''
        lb = paper.line_box(line) or (rb[0] if rb else None)
        if not lb: continue
        cy = (lb[1]+lb[3])/2; cx = (lb[0]+lb[2])/2
        margin_band = cy < .12*height or cy > .86*height
        side = left is not None and (lb[2] < left+5 or lb[0] > right-5)
        in_figure = any(inside((cx, cy), b, 2*paper.body_size(n)) for b in images + small_floats)
        if margin_band or side or (LETTERING.search(reason) and in_figure) or (
                TRUSTED_FURNITURE.search(reason) and not LETTERING.search(reason) and len(line['text']) < 140):
            boxes.extend(rb)
        else:
            doubtful.append(line)
    if n in paper.scan_pages:
        # An OCR layer places its words only approximately (italic captions drift
        # by an em or more), so on scanned pages a placed word explains the ink of
        # its whole printed row: words on one baseline, joined across gaps under
        # four ems, widened by one em.
        em = paper.body_size(n); rows = []
        for b in sorted(boxes, key=lambda b: (b[1]+b[3])/2):
            cy = (b[1]+b[3])/2
            for r in rows:
                if abs(cy-(r[1]+r[3])/2) < .45*em and b[0] <= r[2]+4*em and r[0] <= b[2]+4*em:
                    r[0] = min(r[0], b[0]); r[1] = min(r[1], b[1]); r[2] = max(r[2], b[2]); r[3] = max(r[3], b[3]); break
            else: rows.append(list(b))
        boxes = [[r[0]-em, r[1]-.35*(r[3]-r[1]), r[2]+em, r[3]+.35*(r[3]-r[1])] for r in rows]
    return boxes, figure_masks + art, doubtful


def box_of(items):
    return [min(x[0] for x in items), min(x[1] for x in items), max(x[2] for x in items), max(x[3] for x in items)]


def group(comps, em, horizontal=True):
    """Join components into word boxes along a line (gap < .55 em, shared band)."""
    comps = sorted(comps, key=lambda c: (c[0], c[1]))
    words = []
    for c in comps:
        for w in words:
            vo = min(w[3], c[3]) - max(w[1], c[1])
            if vo >= .4*min(w[3]-w[1], c[3]-c[1]) and -2 <= c[0]-w[2] <= .55*em:
                w[0] = min(w[0], c[0]); w[1] = min(w[1], c[1]); w[2] = max(w[2], c[2]); w[3] = max(w[3], c[3])
                w[4] += 1; w[5] += c[4]
                break
        else:
            words.append([c[0], c[1], c[2], c[3], 1, c[4]])
    return words


def vertical_stacks(comps, em):
    """Letters stacked on one vertical axis (rotated text): returns the set of component indices."""
    order = sorted(range(len(comps)), key=lambda i: (comps[i][1]))
    stacks = []
    for i in order:
        c = comps[i]
        for s in stacks:
            b = s['box']
            xo = min(b[2], c[2]) - max(b[0], c[0])
            if xo >= .5*min(b[2]-b[0], c[2]-c[0]) and 0 <= c[1]-b[3] <= .6*em and c[2]-c[0] <= 1.6*em:
                s['members'].append(i); b[0] = min(b[0], c[0]); b[2] = max(b[2], c[2]); b[3] = max(b[3], c[3])
                break
        else:
            stacks.append(dict(box=list(c[:4]), members=[i]))
    out = set()
    for s in stacks:
        b = s['box']
        if len(s['members']) >= 4 and b[3]-b[1] >= 4*em and b[2]-b[0] <= 1.8*em: out.update(s['members'])
    return out


def check_page(paper, n, image=None):
    image = image or render(paper.pdf, n)
    if not image: return [], {}
    w, h, pixels = image
    em = paper.body_size(n)
    crop = paper.crop_px(n) or [0, 0, w, h]
    boxes, masks, doubtful = explaining_boxes(paper, n)
    pad = max(3.0, .2*em)
    comps = components(w, h, pixels)
    photos = photo_tiles(w, h, pixels)
    tables = [paper.moved(f['box_px'], n) for f in (paper.page(n) or {}).get('floats', []) if f.get('box_px')
              and str(f.get('caption', '')).lower().startswith('tab')]
    drawn = drawn_graphics(comps, em, tables)
    masks = masks + drawn
    letters = []
    for c in comps:
        cw, ch = c[2]-c[0], c[3]-c[1]
        if c[4] < 4 or ch < .18*em: continue                       # specks, rules' ends, dots
        if ch > 2.2*em or cw > 4*em: continue                     # graphics, rules, boxes, photos
        if ch < .3*em and cw > 1.5*em: continue                   # horizontal rules and bars
        if cw <= .2*em and ch >= .95*em: continue                  # vertical rules beside folios
        if max(cw, ch) > em and c[4] < .12*cw*ch: continue         # sparse line art (rule corners, brackets)
        cx, cy = (c[0]+c[2])/2, (c[1]+c[3])/2
        if not inside((cx, cy), crop, -2): continue
        if any(inside((cx, cy), m, 2) for m in masks): continue
        if (int(cx)//TILE, int(cy)//TILE) in photos: continue
        letters.append(c)
    # Dense non-text areas (halftone, hatching) never form words: a cell of the
    # page with very many tiny components is a graphic.
    unexplained = []
    for c in letters:
        cx, cy = (c[0]+c[2])/2, (c[1]+c[3])/2
        if any(inside((cx, cy), b, pad) for b in boxes): continue
        if any(overlap(c[:4], b) >= .5*area(c[:4]) for b in boxes): continue
        unexplained.append(c)
    rotated = vertical_stacks(unexplained, em)
    flat = [c for i, c in enumerate(unexplained) if i not in rotated]
    words = [wd for wd in group(flat, em) if wd[3]-wd[1] >= .35*em and (wd[2]-wd[0] >= .45*em or wd[4] >= 2)]
    # A word is reported only when it looks like text: letters of a line's
    # height, at least two letters or one letter-sized glyph of body height.
    words = [wd for wd in words if wd[3]-wd[1] <= 2.2*em and (wd[4] >= 2 or wd[3]-wd[1] >= .5*em)]
    stats = dict(components=len(comps), letters=len(letters), explained=len(letters)-len(unexplained),
                 unexplained_words=len(words), rotated_letters=len(rotated), doubtful_furniture=len(doubtful))
    findings = []
    words.sort(key=lambda wd: (wd[1], wd[0]))
    bands = []
    for wd in words:
        if bands and abs((wd[1]+wd[3])/2 - (bands[-1][-1][1]+bands[-1][-1][3])/2) < .6*em: bands[-1].append(wd)
        else: bands.append([wd])
    floats = [paper.moved(f['box_px'], n) for f in (paper.page(n) or {}).get('floats', []) if f.get('box_px')]
    graphics = graphic_regions(paper, n, em) + drawn
    kept = []; in_float = {}
    for band in bands:
        # The header and footer bands hold journal art and folios, not text the
        # copy must carry: ink there is left to the furniture rules.
        mid = (box_of(band)[1] + box_of(band)[3]) / 2
        if mid < crop[1] + .07*(crop[3]-crop[1]) or mid > crop[3] - .07*(crop[3]-crop[1]): continue
        # Lettering-sized words (under .55 em, axis labels and indices) alone on a
        # line are not running text.
        if all(x[3]-x[1] < .55*em for x in band): continue
        # Inside a figure or table float (or within three ems of a figure graphic),
        # only running text counts: lines of at least four words reaching ten
        # ems, three or more of them in one float (a chart title or axis
        # lettering drawn without a text layer is figure lettering).
        span = max(x[2] for x in band) - min(x[0] for x in band)
        holder = None
        for k, fb in enumerate(floats + graphics):
            if all(inside(((x[0]+x[2])/2, (x[1]+x[3])/2), fb, 3*em if k >= len(floats) else 2) for x in band):
                holder = k; break
        # Ink on lines the trace calls figure lettering counts only when those
        # lines read as running text (six words or more on average): a flow
        # chart's boxes are lettering even outside a recognised figure.
        bb = box_of(band)
        near = [l for l in doubtful if paper.line_box(l) and overlap(paper.line_box(l), [bb[0]-5, bb[1]-5, bb[2]+5, bb[3]+5])]
        if near and sum(len(l['text'].split()) for l in near) < 6*len(near): continue
        if holder is not None:
            if len(band) >= 4 and span >= 10*em: in_float.setdefault(holder, []).append(band)
            continue
        kept.append(band)
    for k, bs in in_float.items():
        if len(bs) >= 3: kept.extend(bs)
    kept.sort(key=lambda b: box_of(b)[1])
    stats['unexplained_lines'] = len(kept)
    if kept:
        boxes_out = [box_of(b) for b in kept]
        nwords = sum(len(b) for b in kept)
        near = [l for l in doubtful if paper.line_box(l) and any(overlap(paper.line_box(l), [b[0]-5, b[1]-5, b[2]+5, b[3]+5]) for b in boxes_out)]
        why = (f"{len(near)} of its lines are furniture ({near[0].get('furniture_reason')}) inside the text area, e.g. "
               + repr(near[0]['text'][:50]) if near else 'no source run covers it')
        listed = ', '.join(str([round(v) for v in b]) for b in boxes_out[:6]) + (' ...' if len(boxes_out) > 6 else '')
        findings.append(finding(1, f'page {n}: printed ink of {nwords} word(s) on {len(kept)} line(s) is in no copied '
                                   f'or furniture line; {why}; boxes (150 dpi px) {listed}',
                                page=n, box=box_of(boxes_out), words=nwords, lines=len(kept),
                                boxes=[[round(v) for v in b] for b in boxes_out],
                                doubtful_lines=[l['export_id'] for l in near][:20]))
    return findings, stats


def turned(paper, n):
    """Share of the page's text runs set at 90 or 270 degrees (rotated tables or pages)."""
    runs = [e for e in paper.elements(n).values() if e.get('kind') == 'text']
    if not runs: return 0.0
    return sum(1 for e in runs if round(e.get('angle') or 0) % 180 == 90) / len(runs)


def check(paper):
    """Text loss: printed word boxes (white-space segmentation of the page image) on no copied source run."""
    out, stats = [], {}
    if not paper.pdf: return out, dict(skipped='no PDF')
    for n in paper.page_numbers:
        # a rotated page, or a page of mostly turned text, is outside this
        # rule's upright word segmentation: it abstains there
        if (paper.geometry.get(n) or {}).get('rotation', 0) % 360 or turned(paper, n) > .3:
            stats[n] = dict(skipped='rotated page or turned text'); continue
        f, s = check_page(paper, n)
        out.extend(f); stats[n] = s
    return out, stats
