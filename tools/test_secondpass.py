"""Second pass (tools/secondpass): each rule on small synthetic copies, the list writer and the program."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/secondpass'))
import common  # noqa: E402
import r01_ink  # noqa: E402
import r02_continuity  # noqa: E402
import r03_foreign  # noqa: E402
import r04_order  # noqa: E402
import r05_headings  # noqa: E402
import r06_references  # noqa: E402
import r07_tables  # noqa: E402
import r08_duplicates  # noqa: E402
import r10_page1  # noqa: E402
import r11_kind  # noqa: E402
import secondpass  # noqa: E402

EM = 21.0          # body size in 150-dpi pixels
LINE = 25.0        # line pitch in 150-dpi pixels


def make_paper(folder, units, notes=None, extra_lines=(), page_size=(1275, 1650)):
    """Write copy.md, copy.trace.json and page JSON for synthetic units.

    units: dicts with kind, text and lines [(page, x0, top, x1, text)] (150-dpi px);
    each line becomes one trace line with one run; units get own claims in line order.
    """
    folder = pathlib.Path(folder); body = []; pos = 0
    lines, rows, recs = [], [], []
    pages = {}
    counter = {}
    def add_line(page, x0, top, x1, text, status='unit', reason=None, size=EM):
        counter[page] = counter.get(page, 0) + 1
        k = counter[page]; run = f'run:{k}'
        lid = f'p{page}.l{k:03}'
        box110 = [v*110/150 for v in (x0, top, x1, top+EM)]
        lines.append(dict(id=lid, export_id=lid, page=page, page_line=k, text=text, box_110dpi=box110,
                          runs=[run], status=status, furniture_reason=reason, units=[], groups=[]))
        pages.setdefault(page, []).append(dict(id=run, kind='text', text=text, box_px=[x0, top, x1, top+EM], size_px=size))
        return lid, run
    for u in units:
        text = u['text']
        start = pos; body.append(text); pos += len(text) + 2
        claims = []
        for ln in u.get('lines', []):
            page, x0, top, x1, t = ln[:5]
            size = ln[5] if len(ln) > 5 else EM
            lid, run = add_line(page, x0, top, x1, t, size=size)
            rows.append(dict(row=len(rows), page=page, runs=[run], text=t))
            claims.append([len(rows)-1, 0, len(t)])
        recs.append(dict(id=f'u{len(recs)+1:05}', kind=u['kind'], group=u.get('group', f'#{len(recs)}'), span=[start, start+len(text)],
                         text=text, status='traced', source_basis='own claims' if claims else 'group claims',
                         sources=[dict(export_id=l['export_id'], page=l['page'], box_110dpi=l['box_110dpi'])
                                  for l in lines[len(lines)-len(claims):]] if claims else u.get('sources', []),
                         claims=dict(rows=claims, runs=[]), row=u.get('row'), column=u.get('column')))
    for page, x0, top, x1, text, status, reason in extra_lines:
        add_line(page, x0, top, x1, text, status, reason)
    text = '\n\n'.join(body) + '\n\n---\n' + common.UNCERTAINTY + '\n' + '\n'.join('- '+n for n in (notes or ['none'])) + '\n'
    (folder/'copy.md').write_text(text, encoding='utf-8')
    trace = dict(schema='copy-trace/2 (native)', pdf=dict(path=None, sha256=None, pages=[]),
                 copy=dict(path='copy.md', sha256=hashlib.sha256(text.encode()).hexdigest(), characters=len(text)),
                 units=recs, lines=lines, rows=rows, furniture_runs=[], uncertainty_runs=[])
    (folder/'copy.trace.json').write_text(json.dumps(trace), encoding='utf-8')
    for page, els in pages.items():
        (folder/f'page-{page:02}.json').write_text(json.dumps(dict(page=page, elements=els, floats=[], art=[], region_box_px=[0, 0, *page_size],
                                                                   main_text=dict(body_size_px=EM, columns=[]))), encoding='utf-8')
    return common.Paper(folder)


def column(page, x0, x1, top, texts):
    return [(page, x0, top + k*LINE, x1, t) for k, t in enumerate(texts)]


class Sentences(unittest.TestCase):
    def test_ends_mid_and_continues(self):
        self.assertTrue(common.ends_mid('the results of the'))
        self.assertTrue(common.ends_mid('measured in the periodon-'))
        self.assertTrue(common.ends_mid('values were, as expected,'))
        self.assertFalse(common.ends_mid('This is a sentence.'))
        self.assertFalse(common.ends_mid('see doi:10.1111/j.1600-0757.x'))
        self.assertTrue(common.continues('tal patients were'))
        self.assertTrue(common.continues('(95% CI) was'))
        self.assertFalse(common.continues('Table 2. Summary'))
        self.assertFalse(common.continues('12. Smith AB, Jones CD.'))


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rule2_and_rule3_float_between_sentence_halves(self):
        p = make_paper(self.dir, [
            dict(kind='paragraph', text='The patients were treated with scaling and root planing in the periodon-',
                 lines=column(2, 100, 600, 200, ['The patients were treated with scaling', 'and root planing in the periodon-'])),
            dict(kind='caption', text='Table 3. Summary of the studies', lines=[(2, 700, 200, 1100, 'Table 3. Summary of the studies')]),
            dict(kind='paragraph', text='tal pockets of all subjects.', lines=[(3, 100, 200, 600, 'tal pockets of all subjects.')])])
        f2, _ = r02_continuity.check(p); f3, _ = r03_foreign.check(p)
        self.assertEqual(len(f2), 1); self.assertIn('only after caption', f2[0]['message'])
        self.assertEqual(len(f3), 1); self.assertIn('caption', f3[0]['message'])

    def test_rule2_adjacent_split_is_not_a_stop(self):
        p = make_paper(self.dir, [
            dict(kind='paragraph', text='We studied the effect of scaling on the attachment of',
                 lines=column(1, 100, 600, 200, ['We studied the effect of scaling on the', 'attachment of'])),
            dict(kind='paragraph', text='Porphyromonas gingivalis to the root.', lines=[(1, 100, 250, 600, 'Porphyromonas gingivalis to the root.')])])
        self.assertEqual(r02_continuity.check(p)[0], [])

    def test_rule3_running_head_inside_a_paragraph(self):
        heads = [(n, 100, 40, 500, 'JOURNAL OF EXAMPLE STUDIES', 'unit', None) for n in (1, 2, 3)]
        p = make_paper(self.dir, [dict(kind='paragraph', text='the cells of the epithelium were JOURNAL OF EXAMPLE STUDIES counted and',
                                       lines=[(3, 100, 1500, 600, 'the cells of the epithelium were'),
                                              (4, 100, 40, 500, 'JOURNAL OF EXAMPLE STUDIES'),
                                              (4, 100, 200, 600, 'counted and')])], extra_lines=heads)
        f, _ = r03_foreign.check(p)
        self.assertTrue(any('running head' in x['message'] for x in f))

    def test_rule4_interleaved_columns(self):
        left = column(2, 100, 600, 200, [f'left column line number {k} of the text' for k in range(6)])
        right = column(2, 650, 1150, 200, [f'right column line number {k} of the text' for k in range(6)])
        mixed = [l for pair in zip(left, right) for l in pair]
        p = make_paper(self.dir, [dict(kind='paragraph', text=' '.join(l[4] for l in mixed), lines=mixed)])
        f, s = r04_order.check(p)
        self.assertTrue(f); self.assertGreater(s['jumps'], 3)
        q = make_paper(self.dir, [dict(kind='paragraph', text='x '*40, lines=left+right)])
        self.assertEqual(r04_order.check(q)[0], [])

    def test_rule4_short_column_beside_the_only_column(self):
        # two prose lines left of the only clustered column (too few to cluster) are read before it
        # on a page with front matter (a title line)
        title = dict(kind='title', text='An invented title', lines=[(1, 300, 60, 900, 'An invented title')])
        left = column(1, 100, 600, 260, ['the short column opens the paragraph here and', 'continues on its second line before the'])
        right = column(1, 650, 1150, 200, [f'right column line number {k} of the text' for k in range(6)])
        p = make_paper(self.dir, [title, dict(kind='paragraph', text='x '*40, lines=left+right)])
        self.assertEqual(r04_order.check(p)[0], [])
        q = make_paper(self.dir, [title, dict(kind='paragraph', text='x '*40, lines=right+left)])
        self.assertTrue(r04_order.check(q)[0])
        # list bullets beside the column (no line of column width) stay with their items
        items = column(1, 650, 1150, 200, [f'list item number {k} of the text runs on' for k in range(6)])
        bullets = [(1, 620, top, 627, '•') for _, _, top, _, _ in items]
        mixed = [l for pair in zip(bullets, items) for l in pair]
        r = make_paper(self.dir, [dict(kind='list', text='x '*40, lines=mixed)])
        self.assertEqual(r04_order.check(r)[0], [])

    def test_rule4_short_column_rule_only_on_front_pages(self):
        # the same lines on a page without front matter (title on page 1, lines on page 2) keep the nearest column
        title = dict(kind='title', text='An invented title', lines=[(1, 300, 60, 900, 'An invented title')])
        left = column(2, 100, 600, 260, ['the short column opens the paragraph here and', 'continues on its second line before the'])
        right = column(2, 650, 1150, 200, [f'right column line number {k} of the text' for k in range(6)])
        for units, side in (([title], 0), ([], 0)):
            p = make_paper(self.dir, units + [dict(kind='paragraph', text='x '*40, lines=left+right)])
            lay = common.Layout(p); lay.page_lines.get(2)
            cols = {lay.key[l['export_id']][1] for l in p.trace['lines'] if l['page'] == 2 and l['text'].startswith(('the short', 'continues'))}
            self.assertEqual(cols, {side})
        front = make_paper(self.dir, [dict(title, lines=[(2, 300, 60, 900, 'An invented title')]),
                                      dict(kind='paragraph', text='x '*40, lines=left+right)])
        lay = common.Layout(front)
        cols = {lay.key[l['export_id']][1] for l in front.trace['lines'] if l['text'].startswith(('the short', 'continues'))}
        self.assertEqual(cols, {-.5})

    def test_rule5_heading_after_its_text_and_references(self):
        p = make_paper(self.dir, [
            dict(kind='paragraph', text='Treatment consisted of scaling.', lines=[(3, 100, 250, 600, 'Treatment consisted of scaling.')]),
            dict(kind='heading', text='Treatment', lines=[(3, 100, 220, 300, 'Treatment')]),
            dict(kind='paragraph', text='1. Smith AB, Jones CD. A study. J Dent 2001;3:1-5.', lines=[(4, 100, 200, 600, '1. Smith AB, Jones CD. A study.')]),
            dict(kind='heading', text='References', lines=[(4, 100, 170, 300, 'References')])])
        msgs = ' '.join(x['message'] for x in r05_headings.check(p)[0])
        self.assertIn('copied after the text printed below it', msgs)
        self.assertIn('entries before the heading', msgs)

    def test_rule5_numbered_heading_sequence(self):
        p = make_paper(self.dir, [dict(kind='heading', text=t, lines=[(1, 100, 200+40*k, 400, t)])
                                  for k, t in enumerate(['1. Introduction', '2. Methods', '2.1. Design', '2.3. Analysis'])])
        f, _ = r05_headings.check(p)
        self.assertEqual(len(f), 1); self.assertIn('2.3 follows 2.1', f[0]['message'])

    def test_rule6_gap_fused_and_citations(self):
        refs = [dict(kind='reference', text='1 Young T, Palta M. Sleep. N Engl J Med 1993;328:1230-5.', lines=[(5, 100, 200, 600, 'r1')]),
                dict(kind='reference', text='2 Piper AJ. Obesity. Am J Respir 2011;183:292-8. Peppard PE. Hypertension. N Engl J Med 2000;342:1378-84.',
                     lines=[(5, 100, 230, 600, 'r2')]),
                dict(kind='reference', text='9 Gotsopoulos H. Oral appliance. Sleep 2002;25:1-5.', lines=[(5, 100, 260, 600, 'r9')])]
        body = dict(kind='paragraph', text='As shown before [3-5], and later [7].', lines=[(1, 100, 200, 600, 'x')])
        f, _ = r06_references.check(make_paper(self.dir, [body] + refs))
        msgs = ' '.join(x['message'] for x in f)
        self.assertIn('3-8 missing', msgs); self.assertIn('fused', msgs); self.assertIn('no reference entry', msgs)

    def test_rule7_merged_rows(self):
        src = [(3, 100, 300, 180, 'CEJ-aJE'), (3, 300, 300, 380, '0.07'), (3, 500, 300, 580, '0.2'),
               (3, 100, 325, 180, 'CEJ-BC'), (3, 300, 325, 380, '0.7'), (3, 500, 325, 580, '1.0')]
        p = make_paper(self.dir, [dict(kind='paragraph', text='source lines', lines=src)])
        sources = [dict(export_id=l['export_id'], page=3, box_110dpi=l['box_110dpi']) for l in p.trace['lines']]
        cells = [dict(kind='table_cell', text=t, group='g1', row=1, column=c, sources=sources)
                 for c, t in enumerate(['CEJ-aJE CEJ-BC', '0.07 0.7', '0.2 1.0'])]
        q = make_paper(self.dir, [dict(kind='paragraph', text='source lines', lines=src)] + cells)
        f, _ = r07_tables.check(q)
        self.assertTrue(any('printed rows merged' in x['message'] for x in f))

    def test_rule8_duplicate_needs_shared_source(self):
        text = 'the same eight words appear again in this block of text here today'
        line = [(2, 100, 200, 600, text)]
        p = make_paper(self.dir, [dict(kind='caption', text=text, lines=line), dict(kind='table_line', text=text, group='g9',
                                                                                     sources=[dict(export_id='p2.l001', page=2)])])
        p._pdf_words = set(); p._pdf_text = text
        self.assertEqual(len(r08_duplicates.check(p)[0]), 1)
        q = make_paper(self.dir, [dict(kind='caption', text=text, lines=line), dict(kind='paragraph', text=text, lines=[(3, 100, 200, 600, text)])])
        q._pdf_words = set(); q._pdf_text = text
        self.assertEqual(r08_duplicates.check(q)[0], [])

    def test_rule10_markers_and_listed_lines(self):
        self.assertEqual(r10_page1.markers('E. Name 1,\\*'), {'1', '*'})
        self.assertEqual(r10_page1.markers('Anna Smith'), set())
        p = make_paper(self.dir, [dict(kind='title', text='A Title', lines=[(1, 100, 100, 600, 'A Title', 40)]),
                                  dict(kind='author', text='Anna Smith 1', lines=[(1, 100, 200, 600, 'Anna Smith,1 Bo Jones,1 Cy Lee,2')]),
                                  dict(kind='affiliation', text='1 Dept A', lines=[(1, 100, 260, 600, '1 Dept A')]),
                                  dict(kind='affiliation', text='2 Dept B', lines=[(1, 100, 290, 600, '2 Dept B')])],
                       extra_lines=[(1, 100, 225, 400, 'Dee Last', 'uncertainty', None)])
        msgs = ' '.join(x['message'] for x in r10_page1.check(p)[0])
        self.assertIn('print 3 names', msgs); self.assertIn("['2'] belong to no author", msgs)
        self.assertIn('held only in the uncertainty list', msgs)

    def test_rule11_line_numbers(self):
        extra = [(1, 20, 100+k*LINE, 40, str(k+1), 'furniture', 'consecutive manuscript line numbers in the margin') for k in range(25)]
        p = make_paper(self.dir, [dict(kind='paragraph', text='x', lines=[(1, 100, 100, 600, 'x')])], extra_lines=extra)
        f, _ = r11_kind.check(p)
        self.assertEqual(len(f), 1); self.assertIn('line numbers', f[0]['message'])


class Ink(unittest.TestCase):
    def image(self, w, h, blobs):
        px = bytearray(b'\xff'*(w*h))
        for x0, y0, x1, y1 in blobs:
            for y in range(y0, y1):
                px[y*w+x0:y*w+x1] = b'\x00'*(x1-x0)
        return w, h, bytes(px)

    def test_components_and_words(self):
        w, h, px = self.image(200, 60, [(10, 10, 16, 25), (18, 10, 24, 25), (60, 10, 66, 25), (100, 40, 104, 44)])
        comps = r01_ink.components(w, h, px)
        self.assertEqual(len(comps), 4)
        words = r01_ink.group([c for c in comps if c[3]-c[1] > 10], 20)
        self.assertEqual(len(words), 2)       # a word space (36 px) splits, a letter gap (2 px) joins

    def test_vertical_stack(self):
        comps = [[10, 10+k*14, 22, 20+k*14, 60] for k in range(8)]
        self.assertEqual(len(r01_ink.vertical_stacks(comps, 20)), 8)

    def test_photo_tiles(self):
        w, h = 240, 240
        px = bytearray(b'\xff'*(w*h))
        for y in range(0, 144):
            px[y*w:y*w+144] = b'\x80'*144     # a mid-grey picture of 6x6 tiles
        tiles = r01_ink.photo_tiles(w, h, bytes(px))
        self.assertIn((2, 2), tiles); self.assertNotIn((9, 9), tiles)


class Program(unittest.TestCase):
    def test_write_list_is_idempotent_and_rebinds_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            make_paper(d, [dict(kind='paragraph', text='Body.', lines=[(1, 100, 100, 600, 'Body.')])], notes=['page 1: an earlier note'])
            folder = pathlib.Path(d)
            (folder/'copy.checks.json').write_text(json.dumps(dict(copy_sha256=json.loads((folder/'copy.trace.json').read_text())['copy']['sha256'])))
            self.assertTrue(secondpass.write_list(folder, ['second pass, rule 1: page 1: ink']))
            text = (folder/'copy.md').read_text()
            self.assertIn('- page 1: an earlier note', text); self.assertEqual(text.count('second pass, rule 1'), 1)
            digest = hashlib.sha256(text.encode()).hexdigest()
            self.assertEqual(json.loads((folder/'copy.trace.json').read_text())['copy']['sha256'], digest)
            self.assertEqual(json.loads((folder/'copy.checks.json').read_text())['copy_sha256'], digest)
            secondpass.write_list(folder, ['second pass, rule 3: other'])
            text = (folder/'copy.md').read_text()
            self.assertNotIn('rule 1', text); self.assertIn('rule 3: other', text)
            self.assertNotIn('second pass', common.Paper(folder).notes_text)
            secondpass.write_list(folder, [])
            self.assertTrue((folder/'copy.md').read_text().rstrip().endswith('- page 1: an earlier note'))

    def test_rule_list_names_every_module(self):
        rules = secondpass.rule_list()
        self.assertEqual([r['rule'] for r in rules], list(range(1, 12)))
        for r in rules:
            self.assertIn(r['mode'], ('list', 'report'))
            self.assertTrue((ROOT/'tools/secondpass'/(r['module']+'.py')).is_file())


if __name__ == '__main__':
    unittest.main()
