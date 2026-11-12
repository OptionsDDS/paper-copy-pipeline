"""Word boxes of a paper (system Python; imports the element boxer).

usage: /usr/bin/python3 -I layout/words.py PDF PAPER_DIR OUT_JSON

PAPER_DIR holds the boxer's page-NN.json (rules 1-5). Each text run of a page is cut at its white
spaces (the boxer's own word spaces, rule 1); a word box is the union of its characters' boxes from the
boxer's reading layer. Where two word boxes overlap (stacked lines whose glyph boxes touch), the
overlap is split at its middle, so no two boxes overlap. Furniture runs the boxer proved (watermarks,
margin numbering) are left out. Coordinates: pixels at 150 dpi from the top left of the page as the
boxer reads it (the MediaBox; pdftoppm renders the same area by default).
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'standalone'))
import element_boxer_sc as B   # noqa: E402


def font_name(f):
    return f[7:] if len(f) > 7 and f[6] == '+' else f     # drop the subset prefix "ABCDEF+"


def page_words(pdf, page_json):
    d = json.load(open(page_json)); n = d['page']
    # the boxer's own character numbering (rule 1): characters whose centre lies in the page region,
    # without the hidden ones; char_ids index this list
    bx = d['region_box_px']
    chars = [c for c in B.pdfium_characters(pdf, n) if bx[0] <= (c['x0'] + c['x1']) / 2 <= bx[2] and bx[1] <= (c['y0'] + c['y1']) / 2 <= bx[3]]
    chars = [c for c in chars if not c['hidden']]
    words, skipped, unspelled = [], 0, 0
    for e in d['elements']:
        if e['kind'] != 'text' or e.get('furniture_reason'): continue
        ids = list(e['char_ids']); text = e['text']
        if len(ids) != sum(1 for c in text if not c.isspace()): skipped += 1; continue
        # the run's characters in the order that spells its text: as numbered, or left to right; a run
        # that no order spells is counted (report check "runs_unspelled")
        bare = ''.join(c for c in text if not c.isspace())
        for cand in (ids, sorted(ids, key=lambda i: (chars[i]['x0'], chars[i]['y0'])), sorted(ids, key=lambda i: (chars[i]['y0'], chars[i]['x0']))):
            if ''.join(chars[i]['text'] for i in cand) == bare: ids = cand; break
        else: unspelled += 1
        k = 0; cur = []
        def close():
            if not cur: return
            cs = [chars[i] for i in cur]
            fonts = collections.Counter((font_name(c['font']), round(c['size'] * 72 / 150, 1)) for c in cs)
            words.append(dict(text=''.join(c['text'] for c in cs), run=e['id'], line=e['line'], angle=e['angle'],
                              chars=list(cur),
                              box=[min(c['x0'] for c in cs), min(c['y0'] for c in cs), max(c['x1'] for c in cs), max(c['y1'] for c in cs)],
                              fonts=[[f, s, m] for (f, s), m in fonts.most_common()]))
        for ch in text:
            if ch.isspace(): close(); cur = []
            else: cur.append(ids[k]); k += 1
        close()
    # no overlaps: split each overlap at its middle along its thinner side
    def ov(a, b): return min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    for _ in range(20):
        changed = 0
        order = sorted(range(len(words)), key=lambda i: words[i]['box'][0])
        for ii, i in enumerate(order):
            a = words[i]['box']
            for j in order[ii + 1:]:
                b = words[j]['box']
                if b[0] >= a[2]: break
                w, h = ov(a, b)
                if w <= 0 or h <= 0: continue
                changed += 1
                if h <= w:
                    top, bot = (a, b) if a[1] < b[1] else (b, a)
                    m = (max(top[1], bot[1]) + min(top[3], bot[3])) / 2; top[3] = m; bot[1] = m
                else:
                    lef, rig = (a, b) if a[0] < b[0] else (b, a)
                    m = (max(lef[0], rig[0]) + min(lef[2], rig[2])) / 2; lef[2] = m; rig[0] = m
        if not changed: break
    left = sum(1 for i in range(len(words)) for j in range(i + 1, len(words)) if min(ov(words[i]['box'], words[j]['box'])) > 0)
    scan = bool((d.get('scan_evidence') or {}).get('ocr_layer'))   # the boxer's proof of a scanned page with an OCR text layer
    return dict(page=n, region_box_px=d['region_box_px'], words=words, overlaps_left=left, runs_skipped=skipped, runs_unspelled=unspelled, scanned=scan)


def main():
    pdf, paper_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pages = [page_words(pdf, pj) for pj in sorted(glob.glob(os.path.join(paper_dir, 'page-*.json')))]
    json.dump(dict(pdf=os.path.abspath(pdf), dpi=150, pages=pages), open(out, 'w'))
    bad = [p['page'] for p in pages if p['overlaps_left']]
    print(f"words: {sum(len(p['words']) for p in pages)} on {len(pages)} pages; overlaps left on pages {bad or 'none'}; "
          f"runs skipped {sum(p['runs_skipped'] for p in pages)}; runs whose characters spell no order of their text {sum(p['runs_unspelled'] for p in pages)}")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
