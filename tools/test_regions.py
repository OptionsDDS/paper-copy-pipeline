#!/usr/bin/env python3
"""Hand-labelled reading sequences, from rendered PDF pages (21 October 2026).

Usage: /usr/bin/python3 -I tools/test_regions.py RUN_ROOT [--json REPORT.json]
RUN_ROOT contains FXX/GXX folders, or fresh/FXX and next/GXX folders.
The short anchors identify printed paragraph/section starts, with additional
sentence starts on pages having fewer than eight paragraphs. Group labels are
human-labelled flow regions, independent of the candidate's inferred regions.
Normalization permits line wraps, line-end hyphenation, case and PDF ligatures;
it does not permit words from another column inside an anchor.
"""
import argparse
import collections
import json
import pathlib
import re
import unicodedata
import unittest

FIXTURES = {
    ('N13', 3): [
        ('list', 'poor agreement: o0.00'),
        ('list', 'slight agreement: 0.00–0.20'),
        ('list', 'fair agreement: 0.21–0.40'),
        ('list', 'moderate agreement: 0.41–0.60'),
        ('list', 'substantial agreement: 0.61–0.80'),
        ('list', 'almost perfect agreement: 0.81–'),
        ('list', 'In order to explore the predictive value of RT1'),
    ],
    ('G01', 1): [
        ('abstract', 'Introduction: The forces applied during orthodontic'),
        ('abstract', 'Methods: The sample consisted of'),
        ('abstract', 'Results: The paired Fisher exact'),
        ('abstract', 'Conclusions: The orthodontic'),
        ('body', 'There is no conclusive evidence'),
        ('body', 'The early detectable signs'),
        ('body', 'The presence of macrophages'),
        ('body', 'The pulp calcifications are common'),
        ('body', 'Ethical Considerations'),
        ('body', 'This study was approved'),
        ('body', 'The sample consisted of 34'),
    ],
    ('G06', 1): [
        ('summary', 'Background Chronic inflammation is believed'),
        ('summary', 'Methods In this 12 month'),
        ('summary', 'Findings Between Oct 1'),
        ('summary', 'Interpretation Compared with CPT'),
        ('summary', 'Funding Diabetes UK'),
        ('left', 'The worldwide epidemic of type 2'),
        ('left', 'Periodontitis is a chronic inflammatory'),
        ('right', 'immune-inflammatory response'),
        ('right', 'Periodontal therapy is usually delivered'),
    ],
    ('G06', 2): [
        ('panel_left', 'Research in context'),
        ('panel_left', 'Evidence before this study'),
        ('panel_left', 'To identify intervention trials'),
        ('panel_left', 'Added value of this study'),
        ('panel_left', 'Our aim was to show'),
        ('panel_right', 'vascular and renal functions'),
        ('panel_right', 'Implications of all the available evidence'),
        ('panel_right', 'A 2015 Cochrane systematic review'),
        ('left', 'done. At least 8 weeks'),
        ('left', 'We have previously shown'),
        ('right', 'drugs.'),
        ('right', 'Our group previously showed'),
        ('right', 'Study design and participants'),
    ],
    ('G09', 1): [
        ('abstract', 'Aims: This paper describes'),
        ('abstract', 'Material and Methods: Twenty deep'),
        ('abstract', 'The M-MIST consisted of'),
        ('abstract', 'Results: The surgical chair-time'),
        ('abstract', 'Conclusions: M-MIST was applicable'),
        ('left', 'Conflict of interest and sources of'),
        ('left', 'This study has been self-supported'),
        ('middle', 'In the last decade'),
        ('right', 'ling of the soft and hard tissues'),
        ('right', 'microscopes and microsurgical'),
    ],
    ('G02', 4): [
        ('left', 'connective tissue capsule around'),
        ('left', 'Inflammatory cells could still'),
        ('left', 'adjacent to the external surface'),
        ('left', 'single multinucleated giant cells'),
        ('middle', 'be identified in the membrane body'),
        ('middle', 'Eight-week specimens'),
        ('middle', 'After 8 weeks, the entire organization'),
        ('right', 'complete biodegradation of the membrane'),
        ('right', 'revealed a vascularization of approximately'),
        ('right', 'There were still no signs'),
    ],
    ('G04', 16): [
        ('refs_left', 'Silvestri, M., Ricci, G.'),
        ('refs_left', 'Sipos, P. M.'),
        ('refs_left', 'Spahr, A., Haegewald'),
        ('refs_middle', 'intrabony defects. Journal of Clinical Periodontology 29, 433'),
        ('refs_middle', 'Trombelli, L. & Farina'),
        ('refs_middle', 'Zetterstrom, O., Andersson'),
        ('refs_right', 'B., Lundgren, T., Nilveus'),
        ('refs_right', 'Supporting Information'),
        ('panel_left', 'Clinical Relevance'),
        ('panel_left', 'Scientific rationale for the study'),
        ('panel_left', 'Principal findings'),
        ('panel_middle', 'clinical studies have shown'),
        ('panel_middle', 'Practical implications'),
        ('panel_right', 'matrix proteins for the'),
    ],
    ('F03', 2): [
        ('left', 'pressure of overhanging gingiva'),
        ('left', 'Barrier membranes are designed'),
        ('left', 'Search methodology'),
        ('left', 'A search at PubMed/MEDLINE'),
        ('right', 'articles to identify relevant'),
        ('right', 'Nonbiodegradable membranes'),
        ('right', 'Barrier membranes composed of nonbiodegradable'),
        ('right', 'Nonbiodegradable synthetic polymers'),
        ('right', 'Polytetrafluoroethylene (PTFE) is an example'),
        ('right', 'PTFE only membranes can be used'),
    ],
    ('F06', 4): [
        ('left', 'Disadvantages of non-resorbable membranes'),
        ('left', 'Although PTFE'),
        ('left', 'Resorbable synthetic barrier membranes'),
        ('left', 'In an effort to overcome'),
        ('left', 'Advantages of resorbable membranes'),
        ('left', 'The need for developing'),
        ('left', 'Mechanical and chemical properties'),
        ('left', 'Resorbable synthetic membranes have'),
        ('right', 'synthetic membranes such as e-PTFE'),
        ('right', 'Biologically resorbable membranes'),
        ('right', 'Resorbable natural barrier membranes'),
        ('right', 'The majority of natural resorbable'),
        ('right', 'Clinical effectiveness of collagen membranes'),
        ('right', 'Since the late'),
    ],
    ('F07', 1): [
        ('abstract', 'ABSTRACT: Bone regeneration'),
        ('abstract', 'Introduction: Radiation therapy'),
        ('abstract', 'Materials and Methods: An isolated'),
        ('abstract', 'Results: Histological analyses'),
        ('abstract', 'Conclusions: Our findings show'),
        ('left', 'IT IS ESTIMATED that survivors'),
        ('left', 'Even if radiation treatment'),
        ('right', 'cessful in eradicating all damaged'),
        ('right', 'Radiation treatment induces vascular'),
        ('right', 'In the treatment of head'),
    ],
}

# Additional element-level anchors: front matter need not be main text, but must
# not share an active block with the neighboring summary. Panels must retain their
# column order even though their drawn backing is one atomic region.
REGION_ANCHORS = {
    ('G06', 1): [('margin', '*Contributed equally'), ('summary', 'smoking status')],
    ('G06', 2): [('panel_left', 'Evidence before this study'),
                ('panel_right', 'vascular and renal functions')],
    ('G04', 16): [('left', 'Silvestri, M., Ricci'), ('middle', 'Trombelli, L. & Farina'),
                 ('right', 'B., Lundgren, T., Nilveus'),
                 ('panel_left', 'Scientific rationale for the study'),
                 ('panel_middle', 'clinical studies have shown'),
                 ('panel_right', 'matrix proteins for the')],
    ('G09', 1): [('disclosure', 'Conflict of interest and sources of'),
                ('disclosure', 'This study has been self-supported'),
                ('body', 'In the last decade'), ('third_column', 'ling of the soft and hard tissues')],
}


def normalize(text):
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'(?<=\w)[-\u00ad]\s*\n\s*(?=\w)', '', text)
    return re.sub(r'\s+', ' ', text).strip().casefold()


def check(root):
    results = []
    for (name, page), anchors in FIXTURES.items():
        folder = root / name
        if not folder.exists():
            folder = root / ('all' if name.startswith('N') else 'next' if name.startswith('G') else 'fresh4') / name
        failures = []
        path = folder / f'page-{page:02d}.json'
        if not path.exists():
            results.append(dict(paper=name, page=page, passed=False, failures=['missing page JSON']))
            continue
        data = json.loads(path.read_text())
        text = (folder / 'main-text.txt').read_text()
        match = re.search(rf'^## page {page}\s*\n(.*?)(?=^## page |\Z)', text, re.M | re.S)
        raw_page_text = match[1] if match else ''
        page_text = normalize(raw_page_text)
        if (name, page) == ('N13', 3):
            # The PDF stores these bullets as unmapped glyphs. Each must stay
            # on its item's line, before the following prose sentence.
            for _, anchor in anchors[:6]:
                rows = [row for row in raw_page_text.splitlines() if normalize(anchor) in normalize(row)]
                if not rows or not re.search(r'[�•●·]\s*' + re.escape(anchor.split(':')[0]), rows[0]):
                    failures.append(f'detached bullet: {anchor}')
            # A disclosure box below the first column must not newly interrupt
            # the word continued at the top of the second column on page one.
            flow = re.sub(r'^\[\d+\]\s*', '', text, flags=re.M)
            if 'soft tissue margin apical to the cemento-enamel' not in normalize(flow):
                failures.append('page-one sidebar interrupts the column continuation')
        elements = {e['id']: e for e in data['elements'] if e['kind'] == 'text'}
        region_ids = {r['id'] for r in data.get('regions', [])}
        if not region_ids:
            failures.append('missing Poppler region metadata')
        elif any(e.get('region') not in region_ids for e in data['elements']):
            failures.append('element has no valid region')
        for bad in ('Threearcetiiosnno', 'G ianna', '*Contributed equally smoking status',
                    'Clinical Relevance clinical studies have shown'):
            if normalize(bad) in page_text or any(normalize(bad) in normalize(e.get('text', '')) for e in data['elements']):
                failures.append(f'garbled text remains: {bad}')
        region_memberships = collections.defaultdict(set)
        # Rule 6 retains source rule-2 blocks for repeatable --paper passes.
        # Test the exporter view: a retained source is not emitted beside its parts.
        sources = {b.get('main_text_source') for b in data['blocks'] if b.get('main_text_source')}
        for label, anchor in REGION_ANCHORS.get((name, page), []):
            matched = []
            for b in data['blocks']:
                if b['id'] in sources: continue
                rows = collections.defaultdict(list)
                for mid in b['members']:
                    if mid in elements: rows[elements[mid]['line']].append(elements[mid])
                text = '\n'.join(' '.join(e['text'] for e in sorted(row, key=lambda e: e['box_px'][0]))
                                 for _, row in sorted(rows.items()))
                if normalize(anchor) in normalize(text): matched.append(b['id'])
            if not matched: failures.append(f'missing explicit region anchor: {anchor}')
            for bid in matched: region_memberships[bid].add(label)
        for bid, labels in region_memberships.items():
            if len(labels) > 1: failures.append(f'explicit region anchors share {bid}: {sorted(labels)}')
        mt = data.get('main_text', {})
        by_id = {b['id']: b for b in mt.get('blocks', [])}
        reading = mt.get('reading_order', [])
        for panel in mt.get('panels', []):
            members = panel['blocks']
            positions = [reading.index(bid) for bid in members if bid in reading]
            if len(positions) != len(members) or positions != list(range(min(positions, default=0), min(positions, default=0) + len(members))):
                failures.append(f'non-atomic panel {panel["id"]}')
            if not members or any(by_id[bid]['cls'] != 'main' for bid in members):
                failures.append(f'non-main panel member {panel["id"]}')
            elif panel['order'] != by_id[members[0]]['order']:
                failures.append(f'wrong panel order {panel["id"]}')
        expected_columns = {('G06', 2): 2, ('G04', 16): 3, ('G09', 1): 1}.get((name, page))
        if expected_columns and not any(len(p['columns']) == expected_columns for p in mt.get('panels', [])):
            failures.append('missing atomic panel with expected internal columns')
        blocks = []
        active = {b['id'] for b in data.get('main_text', {}).get('blocks', [])}
        for block in data['blocks']:
            if block['id'] not in active: continue
            rows = collections.defaultdict(list)
            for member in block['members']:
                if member in elements:
                    e = elements[member]
                    rows[e['line']].append(e)
            ordered = sorted(rows.values(), key=lambda row: min(e['box_px'][1] for e in row))
            full_text = '\n'.join(' '.join(e['text'] for e in sorted(row, key=lambda e: e['box_px'][0])) for row in ordered)
            blocks.append(dict(block, text=full_text))
        memberships = collections.defaultdict(set)
        last = -1
        for region, anchor in anchors:
            needle = normalize(anchor)
            pos = page_text.find(needle)
            if pos < 0:
                failures.append(f'missing/interleaved anchor: {anchor}')
            elif pos < last:
                failures.append(f'out-of-order anchor: {anchor}')
            else:
                last = pos
            matched = [b for b in blocks if needle in normalize(b.get('text', ''))]
            if not matched:
                failures.append(f'anchor not whole in a block: {anchor}')
            for block in matched:
                memberships[block['id']].add(region)
        for bid, regions in memberships.items():
            if len(regions) > 1:
                failures.append(f'cross-region block {bid}: {sorted(regions)}')
        coverage = []
        for f in sorted(folder.glob('page-[0-9]*.json')):
            d = json.loads(f.read_text()); c = d['counts']
            if c['characters_in_elements'] != c['characters_in_region']:
                coverage.append(f"p{d['page']}: {c['characters_in_elements']} != {c['characters_in_region']}")
            ids = [cid for e in d['elements'] if e['kind'] == 'text' for cid in e['char_ids']]
            if len(ids) != len(set(ids)):
                coverage.append(f"p{d['page']}: duplicate character ids")
            for e in d['elements']:
                if 'region_parts' in e:
                    part_ids = [cid for part in e['region_parts'] for cid in part['char_ids']]
                    if part_ids != e['char_ids']:
                        coverage.append(f"p{d['page']}: region index changes characters in {e['id']}")
        failures += ['coverage ' + s for s in coverage]
        results.append(dict(paper=name, page=page, anchors=len(anchors), passed=not failures, failures=failures))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=pathlib.Path, nargs='?')
    parser.add_argument('--json', type=pathlib.Path)
    parser.add_argument('--unit', action='store_true', help='check fallbacks, coordinate frames and inline blocks')
    args = parser.parse_args()
    if args.unit:
        unit_checks()
        if args.root is None: return
    if args.root is None: parser.error('RUN_ROOT is required unless --unit is used')
    results = check(args.root)
    for r in results:
        print(f"{r['paper']} p{r['page']}: {'PASS' if r['passed'] else 'FAIL'}")
        for failure in r['failures']:
            print('  ' + failure)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + '\n')
    raise SystemExit(not all(r['passed'] for r in results))


def unit_checks():
    import importlib.util
    import types
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location('_regions_boxer', pathlib.Path(__file__).resolve().parents[1] / 'standalone/element_boxer_sc.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    box = [0, 0, 1250, 1625]
    xml = b'<doc><block xMin="10" yMin="20" xMax="40" yMax="50"><line><word>\x06</word></line></block></doc>'
    page = types.SimpleNamespace(mediabox=[15, 20, 615, 800], rotate=0)
    doc = types.SimpleNamespace(pages=[page], page_size=lambda n: (600, 780, (15, 20, 615, 800)))
    with patch.object(m, 'sc_doc', return_value=doc):
        for failure in (FileNotFoundError(), m.subprocess.TimeoutExpired('pdftotext', 30)):
            with patch.object(m.subprocess, 'run', side_effect=failure):
                regions = m.poppler_regions('unused.pdf', 1, box, [])
                assert len(regions) == 1 and regions[0]['box_px'] == box and regions[0]['fallback']
        for stdout, rc in ((b'bad xml', 0), (b'<doc/>', 0), (xml, 1)):
            with patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(stdout=stdout, returncode=rc)):
                assert m.poppler_regions('unused.pdf', 1, box, [])[0]['fallback']
        with patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(stdout=xml, returncode=0)):
            # Nonzero MediaBox origin; Boxer y is flipped against the cropped height.
            r = m.poppler_regions('unused.pdf', 1, box, [])[0]
            assert all(abs(a-b) < 1e-8 for a,b in zip(r['box_px'], map(m.px, [25, 0, 55, 30])))
            page.rotate = 90
            doc.page_size = lambda n: (780, 600, (15, 20, 615, 800))
            r = m.poppler_regions('unused.pdf', 1, box, [])[0]
            assert all(abs(a-b) < 1e-8 for a,b in zip(r['box_px'], map(m.px, [35, 540, 65, 570])))
    regions = [dict(id='left', box_px=[0, 0, 100, 100], lines=5),
               dict(id='right', box_px=[120, 0, 300, 100], lines=5),
               dict(id='margin', box_px=[20, 110, 100, 120], lines=1),
               dict(id='inline', box_px=[140, 110, 180, 120], lines=1),
               dict(id='inline2', box_px=[190, 110, 300, 120], lines=1)]
    separated = m.region_separations(regions, [dict(kind='text', run_size_px=10)])
    assert frozenset(('left', 'right')) in separated
    assert frozenset(('margin', 'right')) in separated
    assert frozenset(('inline', 'inline2')) not in separated
    def element(i, region, b, line):
        return dict(id=str(i), kind='text', region=region, box_px=b, line=line,
                    angle=0, size_px=10, run_size_px=10, text='ordinary text')
    els = [element(1, 'left', [0, 10, 140, 20], 1), element(2, 'right', [120, 25, 300, 35], 2)]
    assert len(m.larger_boxes(els)) == 1
    plain = [{k:v for k,v in e.items() if k != 'region'} for e in els]
    assert m.larger_boxes(els) == m.larger_boxes(plain)
    els = [dict(id='fill', kind='fill', region='left', box_px=[0, 0, 300, 100]),
           element(1, 'left', [0, 10, 100, 20], 1), element(2, 'right', [120, 10, 300, 20], 1)]
    # This fixture tests a local container, not a page-sized background.
    # A separate rule witnesses the page extent and adds no returned block.
    els.append(dict(id='page-rule',kind='rule',box_px=[0,400,400,400]))
    assert len(m.larger_boxes(els)) == 1
    # Direct and indirect unions across a supported boundary are both forbidden.
    assert len(m.larger_boxes(els, regions)) == 2
    bridge = dict(id='fill', kind='fill', box_px=[0, 0, 300, 100])
    assert len(m.larger_boxes([bridge] + els[1:], regions)) == 2
    one_sided = [dict(r, lines=1) if r['id'] == 'right' else r for r in regions]
    assert frozenset(('left', 'right')) not in m.region_separations(one_sided, els)
    far = [dict(id='a', box_px=[0, 0, 100, 30], lines=3),
           dict(id='b', box_px=[120, 61, 300, 91], lines=3)]
    assert not m.region_separations(far, els)
    far[1]['box_px'] = [120, 60, 300, 90]
    assert m.region_separations(far, els) == {frozenset(('a', 'b'))}
    assert m.region_at([0, 0, 10, 10], [dict(id='panel', box_px=[0, 0, 100, 100]),
                      dict(id='child', box_px=[0, 0, 20, 20], deferred='ordering')]) == 'panel'
    # Empty/control-only marker lines are not stacked text witnesses.
    page.rotate = 0
    doc.page_size = lambda n: (600, 780, (15, 20, 615, 800))
    with patch.object(m, 'sc_doc', return_value=doc):
        marker_xml = xml.replace(b'<line><word>\x06</word></line>', b'<line><word>\x06</word></line>' * 6)
        with patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(stdout=marker_xml, returncode=0)):
            assert m.poppler_regions('unused.pdf', 1, box, [])[0]['lines'] == 0
    print('PASS: fallbacks, origins/rotation, control markers, two-sided support, vertical limit, inline protection, component/fill gating, deferred panel ownership')
    def block(name, box): return dict(id=name, box_px=box)
    cols = [[0, 100], [120, 220]]
    children = [block('panel-left', [5, 120, 95, 180]), block('panel-right', [125, 120, 215, 180])]
    panel = dict(id='panel', box_px=[0, 110, 220, 190], blocks=[b['id'] for b in children], columns=cols)
    top = [block('left', [0, 0, 100, 100]), block('right', [120, 0, 220, 100])]
    bottom = [block('below-left', [0, 200, 100, 300]), block('below-right', [120, 200, 220, 300])]
    ordered, _ = m.reading_order_bands(children + top + bottom, cols, 10, panels=[panel])
    assert [b['id'] for b in ordered] == ['left', 'right', 'panel-left', 'panel-right', 'below-left', 'below-right']
    # A panel beside a tall paragraph stays in its own column, after the
    # paragraph starting above it, without cutting the other page column.
    small = dict(id='small', box_px=[0, 80, 100, 150], blocks=['a', 'b'], columns=[[5, 45], [55, 95]])
    items = [block('before', [0, 0, 100, 90]), block('a', [5, 85, 45, 145]),
             block('b', [55, 85, 95, 145]), block('after', [0, 160, 100, 200]),
             block('neighbor', [120, 0, 220, 200])]
    ordered, _ = m.reading_order_bands(items, cols, 10, panels=[small])
    assert [b['id'] for b in ordered] == ['before', 'a', 'b', 'after', 'neighbor']
    ordered, _ = m.reading_order_bands(items, cols, 10, panels=[dict(small, blocks=['absent'])])
    assert {b['id'] for b in ordered} == {b['id'] for b in items}
    print('PASS: spanning panels, internal columns, adjacent paragraphs, uninterrupted neighbors, absent members')


def load_tests(loader, tests, pattern):
    """Expose the existing synthetic checks to per-file unittest runs too."""
    import unittest
    tests.addTest(unittest.FunctionTestCase(unit_checks))
    return tests


if __name__ == '__main__':
    main()
