#!/usr/bin/env python3
"""Build Q1-Q5 from unchanged boxer page records; no truth enters prompts.

Usage: /usr/bin/python3 -I tools/checker/build_questions.py RECORDS PDF OUT
Every large box gets Q1, every body block edge (including across pages) gets
Q2, and every page gets Q3/Q5 even if the boxer found no body or floats.
Internal body-line edges are included by default to expose column interleaving.
Source IDs, source hashes, lines and displayed coordinates remain traceable.
"""
import argparse
from collections import defaultdict
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import VERSION, digest, file_hash, save
import raster

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('_checker_export', ROOT / 'tools/export_lines.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def hull(boxes):
    boxes = list(boxes)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def pad(box, amount=6):
    return [box[0] - amount, box[1] - amount, box[2] + amount, box[3] + amount]


def normalize(page, geometry, width, height):
    """Read stages 2/3 as supplied, without executing or repairing the copier."""
    n = page['page']
    dpi = page.get('params', {}).get('dpi', 150)
    def mapped(box):
        b = exporter.image_box(box, dpi, geometry)
        b = [round(max(0, min(v, width if i % 2 == 0 else height)), 3) for i, v in enumerate(b)]
        if b[0] >= b[2] or b[1] >= b[3]:
            raise ValueError(f'page {n}: source box outside image: {box}')
        return b
    main = page.get('main_text')
    if main is None:
        raise ValueError(f'page {n}: rules 6-7 main_text record missing')
    blocks = page.get('blocks', [])
    by_id = {b['id']: b for b in blocks}
    if len(by_id) != len(blocks):
        raise ValueError(f'page {n}: duplicate block IDs')
    classified = {b['id']: b for b in main.get('blocks', [])}
    if any(k not in by_id for k in classified):
        raise ValueError(f'page {n}: classified block absent from source')
    table_runs = {mid for t in page.get('tables', []) for mid in t.get('members', [])}
    float_blocks = {bid for f in page.get('floats', []) for bid in f.get('blocks', [])}
    caption_runs = {e['id'] for e in page.get('elements', []) if e.get('band') == 'caption'}
    elements = {e['id']: e for e in page.get('elements', [])}
    caption_groups = []
    for f in page.get('floats', []):
        ids = set(f.get('caption_members', []))
        # Rule 4 also represents a caption by its owning block or by a label
        # inside a table; not every caption is in rule 6's main_text.blocks.
        labels = {e['id'] for e in elements.values() if e.get('text') and f.get('caption') and
                  (e['text'].startswith(f['caption']) or f['caption'].startswith(e['text'])) and
                  len(e['text'].strip()) >= 4 and
                  f['box_px'][0] - 1 <= e['box_px'][0] <= e['box_px'][2] <= f['box_px'][2] + 1 and
                  f['box_px'][1] - 1 <= e['box_px'][1] <= e['box_px'][3] <= f['box_px'][3] + 1}
        ids.update(labels)
        for b in blocks:
            if labels & set(b.get('members', [])) and set(b.get('kinds', [])) == {'text'}:
                ids.update(b['members'])
        ids = {mid for mid in ids if mid in elements and elements[mid].get('text')}
        if ids:
            caption_runs.update(ids)
            caption_groups.append(dict(id=f'p{n}.caption:{f["id"]}', page=n,
                                       box=mapped(hull(elements[mid]['box_px'] for mid in ids))))
    line_ids = defaultdict(list)
    lines = []
    # Use the line export's physical row splitter, retaining column/region seams.
    roles = {mid: b['id'] for b in blocks for mid in b.get('members', [])}
    rows = exporter.source_rows(page, roles)
    for i, row in enumerate(rows, 1):
        lid = f'p{n}.l{i:04}'
        for e in row:
            line_ids[e['id']].append(lid)
        lines.append(dict(id=lid, page=n, box=mapped(hull(e['box_px'] for e in row)),
                          runs=[e['id'] for e in row], text=' '.join(e.get('text', '') for e in row)))
    lmap = {l['id']: l for l in lines}
    result = []
    for b in blocks:
        c = classified.get(b['id'], {})
        cls, why = c.get('cls', 'other'), c.get('why') or ''
        ids = list(dict.fromkeys(lid for mid in b.get('members', []) for lid in line_ids[mid]))
        # This is the boxer's within-block row order, not a newly predicted order.
        ids.sort(key=lambda lid: next(i for i, l in enumerate(lines) if l['id'] == lid))
        text_members = {mid for lid in ids for mid in lmap[lid]['runs']} & set(b.get('members', []))
        # The supplied boxer has a broad "other/aside" destination. Refining an
        # already excluded footnote or running head is not a classification fault.
        expected = ['footnote', 'running head', 'page number', 'figure lettering', 'other'] if ids else ['other']
        header = None
        if cls in ('main', 'heading', 'reference', 'body'):
            expected = ['body']
        elif cls in ('title', 'authors', 'main header', 'main_header'):
            expected = ['main header']
            header = cls if cls in ('title', 'authors') else None
        elif 'front matter' in why or 'above the title' in why:
            expected = ['main header']
        elif cls == 'caption' or text_members and text_members <= caption_runs:
            expected = ['caption']
        elif cls == 'furniture':
            # Rule 6 has a broad furniture class, so a subtype is not a disagreement.
            expected = ['running head', 'page number', 'other']
        elif text_members and text_members <= table_runs:
            expected = ['table']
        elif b['id'] in float_blocks and text_members:
            expected = ['figure lettering', 'caption']
        if c.get('abstract') or c.get('side_abstract'):
            # Abstract prose is legitimately in the body in this boxer version.
            expected = ['body', 'main header']
            header = 'abstract'
        result.append(dict(id=f'p{n}.{b["id"]}', page=n, source_id=b['id'],
                           box=mapped(b['box_px']), lines=ids, members=b.get('members', []),
                           original_class=cls, expected=expected, header_role=header))
    # Expose table gates and unpaired graphical regions even when they are not blocks.
    for t in page.get('tables', []):
        result.append(dict(id=f'p{n}.{t["id"]}', page=n, source_id=t['id'], box=mapped(t['box_px']),
                           lines=list(dict.fromkeys(lid for mid in t.get('members', []) for lid in line_ids[mid])),
                           members=t.get('members', []), original_class='table', expected=['table'], header_role=None))
    bmap = {b['id']: b for b in result}
    order = [f'p{n}.{bid}' for bid in main.get('reading_order', [])]
    if len(order) != len(set(order)) or any(bid not in bmap for bid in order):
        raise ValueError(f'page {n}: invalid body order')
    # Include only the recorded body stream, never infer order for an unplaced block.
    floats = [dict(id=f'p{n}.{f["id"]}', page=n, box=mapped(f['box_px']),
                   blocks=[f'p{n}.{bid}' for bid in f.get('blocks', [])]) for f in page.get('floats', [])]
    captions = caption_groups
    for b in result:
        if 'caption' in b['expected'] and not any(c['box'] == b['box'] for c in captions):
            captions.append(dict(id=b['id'], page=n, box=b['box']))
    known_caps = {c['id'] for c in captions}
    for i, item in enumerate(page.get('unpaired', []), 1):
        bid = f'p{n}.{item["block"]}' if item.get('block') else f'p{n}.unpaired:{i}'
        if item.get('kind', '').startswith('caption'):
            if bid not in known_caps:
                captions.append(dict(id=bid, page=n, box=mapped(item['box_px'])))
                known_caps.add(bid)
        elif not any(bid in f['blocks'] for f in floats):
            floats.append(dict(id=f'p{n}.unpaired:{i}', page=n, box=mapped(item['box_px']), blocks=[bid]))
    return dict(page=n, width=width, height=height, boxes=result, lines=lines,
                body_order=order, floats=floats, captions=captions)


def questions(document, line_edges=True):
    qs = []
    pages = {p['page']: p for p in document['pages']}
    boxes = {b['id']: b for p in pages.values() for b in p['boxes']}
    lines = {l['id']: l for p in pages.values() for l in p['lines']}
    def view(n, marks=(), crop=None, label='page'):
        return dict(page=n, image=pages[n]['image'], marks=list(marks), crop=crop, label=label)
    def add(kind, targets, ns, prompt, views, expected=(), **extra):
        identity = dict(type=kind, targets=targets, pages=ns)
        qid = f'{document["paper"]}.{kind}.{digest(identity)[:16]}'
        qs.append(dict(id=qid, **identity, prompt=prompt, views=views, expected=list(expected), **extra))
    for p in pages.values():
        n = p['page']
        for b in p['boxes']:
            marks = [dict(box=b['box'])]
            add('Q1', [b['id']], [n],
                'Classify the single red outlined box: body / caption / footnote / running head / page number / '
                'figure lettering / main header / table / other. Body includes section headings and references. '
                'Main header means article front matter, not section headings. Choose its actual role from the image. '
                'If the box mixes roles, choose the predominant role with low confidence.', [view(n, marks)], b['expected'])
            if 'main header' in b['expected']:
                add('Q4', [b['id']], [n],
                    'Classify the red outlined main-header box: title / subtitle / authors / affiliation / '
                    'correspondence / dates / journal information / abstract / keywords / other. '
                    'If it contains several roles, use low confidence.', [view(n, marks)],
                    [b['header_role']] if b['header_role'] else [])
        body_marks = [dict(box=boxes[bid]['box'], color=[20, 80, 220]) for bid in p['body_order']]
        add('Q3', [], [n],
            'Is any main-body text on this page outside EVERY blue body box? yes / no. '
            'Section headings and references count as body; captions, footnotes, running heads and article '
            'front matter do not. A page with no body text is no. For yes, outline each uncovered body region '
            'as [left,top,right,bottom] in full-page coordinates normalized to integers 0..1000. '
            'For no use an empty regions list. Inspect the whole page, including areas with no detected boxes.',
            [view(n, body_marks)])
        marks, labels = [], []
        for prefix, collection, color in [('F', p['floats'], [20, 80, 220]), ('C', p['captions'], [220, 20, 30])]:
            for i, item in enumerate(collection, 1):
                label = f'{prefix}{i}'
                marks.append(dict(box=item['box'], label=label, color=color))
                labels.append(dict(label=label, id=item['id']))
        add('Q5', [x['id'] for x in labels], [n],
            'Does every float on this page have its caption box, and does every caption have its float? yes / no. '
            'Blue F outlines are detected floats and red C outlines are detected captions. Inspect unoutlined areas too. '
            'Check that each caption covers the full printed caption, with its correct float; shared panel captions '
            'are valid. For no select the affected IDs from the label map; use unboxed plus full-page normalized '
            '0..1000 outlines for missing detections. A page with neither floats nor captions is yes. '
            'For yes affected and regions are empty. Label map: ' + str(labels),
            [view(n, marks)], choices=[x['id'] for x in labels])
    body = [bid for p in pages.values() for bid in p['body_order']]
    def edge(a, b, level):
        la = [lines[lid] for lid in a.get('lines', [])]
        lb = [lines[lid] for lid in b.get('lines', [])]
        ca = hull(l['box'] for l in la[-2:]) if la else a['box']
        cb = hull(l['box'] for l in lb[:2]) if lb else b['box']
        am = dict(box=a['box'], color=[20, 80, 220], label='A')
        bm = dict(box=b['box'], color=[220, 20, 30], label='B')
        ns = list(dict.fromkeys([a['page'], b['page']]))
        views = [view(a['page'], [am], pad(ca), 'A last lines'), view(b['page'], [bm], pad(cb), 'B first lines')]
        views += [view(n, [m for x, m in [(a, am), (b, bm)] if x['page'] == n]) for n in ns]
        add('Q2', [a['id'], b['id']], ns,
            'B continues directly after A in the main-body reading order: yes / no. '
            'The first image is A\'s last lines and the second is B\'s first lines, followed by full page images. '
            'A is blue; B is red. This asks reading adjacency, not whether they are the same sentence: '
            'a paragraph/section boundary or column/page break can be yes. Ignore intervening floats and furniture. '
            'Choose no if body text was skipped, reversed or interleaved, or if either endpoint is not body.',
            views, level=level)
    for aid, bid in zip(body, body[1:]):
        edge(boxes[aid], boxes[bid], 'block')
    if line_edges:
        seen = set()
        for bid in body:
            ids = boxes[bid]['lines']
            for aid, lid in zip(ids, ids[1:]):
                if (aid, lid) not in seen:
                    edge(lines[aid], lines[lid], 'line')
                    seen.add((aid, lid))
    return qs


def build(records, pdf, output, paper=None, line_edges=True):
    import json
    records, pdf, output = Path(records).resolve(), Path(pdf).resolve(), Path(output).resolve()
    if output == records or output in records.parents or records in output.parents:
        raise ValueError('OUT and source records must be separate directories, neither containing the other')
    if output.exists() and any(output.iterdir()):
        raise ValueError('OUT must be empty; refusing to mix bundle versions')
    sources = sorted(records.glob('page-*.json'))
    if not sources:
        raise ValueError('no boxer page records')
    geometries = exporter.conserve.page_geometry(pdf)
    raw = [json.loads(path.read_text()) for path in sources]
    raw.sort(key=lambda p: p['page'])
    if [p['page'] for p in raw] != sorted(geometries):
        raise ValueError('records must cover every PDF page once')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'pages').mkdir()
    document = dict(paper=paper or records.name, coordinate_frame='110 dpi rendered page, top-left origin', pages=[])
    for p in raw:
        n = p['page']
        w, h, pixels = raster.render(pdf, n)
        relative = f'pages/p{n:03}.png'
        (output / relative).write_bytes(raster.encode(w, h, pixels))
        page = normalize(p, geometries[n], w, h)
        page.update(image=relative, image_sha256=file_hash(output / relative))
        document['pages'].append(page)
    bundle = dict(version=VERSION, document=document, questions=questions(document, line_edges),
                  provenance=dict(pdf=str(pdf), pdf_sha256=file_hash(pdf), records=str(records),
                                  records_sha256={s.name: file_hash(s) for s in sources},
                                  builder_sha256=file_hash(__file__), line_edges=line_edges,
                                  source_stage='boxer rules 6-7; no copy postprocessing'))
    bundle['bundle_sha256'] = digest(bundle)
    save(output / 'bundle.json', bundle)
    return bundle


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('records'); ap.add_argument('pdf'); ap.add_argument('out')
    ap.add_argument('--paper'); ap.add_argument('--block-edges-only', action='store_true')
    a = ap.parse_args()
    b = build(a.records, a.pdf, a.out, a.paper, not a.block_edges_only)
    print(f'{b["document"]["paper"]}: {len(b["document"]["pages"])} pages; {len(b["questions"])} questions')


if __name__ == '__main__':
    main()
