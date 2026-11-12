"""Native trace: provenance carried by the copy's strings, unit spans, accounting and checks.

Run from tools/: /usr/bin/python3 -I -m unittest -q test_native_trace
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


copy = load('native_trace_copy', ROOT/'copy_paper.py')
tracer = load('native_trace_builder', ROOT/'tools/copy_trace.py')
validator = load('native_trace_validator', ROOT/'tools/trace.py')


def row(page, ids, text):
    return copy.trace_row(page, [dict(id=m) for m in ids], text)


class Provenance(unittest.TestCase):
    def setUp(self): copy.trace_reset()

    def test_src_value_is_plain_text_and_keeps_rows_through_joins(self):
        a, b = row(1, ['run:1'], 'A hyphen-'), row(1, ['run:2'], 'ated word ends.')
        joined = copy.Joiner(['A hyphenated word ends.']).lines([a, b])
        self.assertEqual(joined, 'A hyphenated word ends.')
        self.assertEqual(str(joined), joined)
        self.assertEqual({r for r, _, _ in joined.segs}, {a.segs[0][0], b.segs[0][0]})
        self.assertEqual(json.dumps(joined), json.dumps('A hyphenated word ends.'))
        self.assertEqual(hash(joined), hash('A hyphenated word ends.'))
        self.assertTrue(('x ' + a).segs and (a + ' y').segs and a.strip().segs)

    def test_slice_of_one_row_keeps_exact_range_and_joined_slice_is_partial(self):
        a = row(2, ['run:5'], 'Methods. We measured.')
        head, rest = a[:8], a[9:]
        self.assertEqual(head.segs, ((a.segs[0][0], 0, 8),))
        self.assertEqual(rest.segs, ((a.segs[0][0], 9, 21),))
        joined = a + ' ' + row(2, ['run:6'], 'More text.')
        self.assertTrue(all(start == -1 for _, start, _ in joined[3:12].segs))

    def test_sentinels_give_spans_and_leave_no_trace_in_text(self):
        out = ['# ' + 'Title', '', '- ' + 'item text', '| a | b |']
        copy.trace_lines(out, 0, 'title', stop=1)
        copy.trace_lines(out, 2, 'list_item', stop=3)
        out[3] = copy.trace_cells(out[3], 'table_cell', 'g1', row=1)
        text, spans = copy.trace_strip('\n'.join(out))
        self.assertEqual(text, '# Title\n\n- item text\n| a | b |')
        self.assertEqual([text[slice(*spans[k])] for k in sorted(spans)], ['Title', 'item text', 'a', 'b'])
        self.assertEqual([u.get('column') for u in copy._TRACE['units'][2:]], [1, 2])

    def test_uncertainty_runs_and_groups_are_recorded(self):
        copy.trace_note_runs(3, ['run:9'], 'read text not placed')
        self.assertIn((3, 'run:9'), copy._TRACE['uncertain'])
        self.assertNotEqual(copy.trace_group(), copy.trace_group())

    def test_rule6_header_rows_and_deferred_key_words_keep_their_rows(self):
        # Rule 6 header text (correspondence, dates, key words) is read by
        # prepare_front_matter, not prose_row: its rows must still carry runs.
        def run(i, text, y):
            return dict(id=i, kind='text', text=text, line=y, angle=0, box_px=[0, y, 200, y+10],
                        size_px=10, run_size_px=10, char_ids=[])
        es = [run('r1', 'Correspondence: A. Author,', 600), run('r2', 'Example Street 1', 612),
              run('r3', 'Accepted for publication 1 May 2006', 630), run('k1', 'Key words: one; two', 650)]
        blocks = [dict(id='h', members=['r1', 'r2', 'r3'], box_px=[0, 600, 200, 640]),
                  dict(id='k', members=['k1'], box_px=[0, 650, 200, 660])]
        mt = dict(body_size_px=10, blocks=[
            dict(id='h', cls='other', role='header', header_from_body=True, box_px=[0, 600, 200, 640]),
            dict(id='k', cls='other', role='header', header_from_body=True, header_after='abs', box_px=[0, 650, 200, 660])])
        p = dict(page=1, elements=es, blocks=blocks, main_text=mt, region_box_px=[0, 0, 500, 800])
        copy.prepare_front_matter([p], {})
        rows = copy._TRACE['rows']
        self.assertEqual(p['_owned_header_info'], [['Correspondence: A. Author,', 'Example Street 1'],
                                                   ['Accepted for publication 1 May 2006']])
        self.assertEqual([[rows[x.segs[0][0]]['runs'] for x in g] for g in p['_owned_header_info']],
                         [[['r1'], ['r2']], [['r3']]])
        items = copy.place_deferred_keywords([dict(kind='para', page=1, text='Abstract.', abstract=True)], p, copy.Joiner([]))
        self.assertEqual(items[1]['text'], 'Key words: one; two')
        self.assertEqual([rows[r]['runs'] for r, _, _ in items[1]['text'].segs], [['k1']])

    def test_copyright_row_dropped_after_an_abstract_records_its_reason(self):
        # The journal record is article information; the copyright row above
        # it is dropped as furniture and must carry that reason for the trace.
        def run(i, text, y):
            return dict(id=i, kind='text', text=text, line=y, angle=0, box_px=[0, y, 400, y+10],
                        size_px=10, run_size_px=10, char_ids=[])
        es = [run('a1', 'Purpose: The purpose of this study was to measure.', 300),
              run('a2', 'Conclusions: Accuracy was achieved.', 312),
              run('c1', '© 2017 Example Association of Surgeons', 324),
              run('j1', 'J Example Surg 75:1377-1386, 2017', 336)]
        p = dict(page=1, elements=es, blocks=[dict(id='abs', members=['a1', 'a2', 'c1', 'j1'], box_px=[0, 300, 400, 346])],
                 main_text=dict(body_size_px=10, blocks=[]), region_box_px=[0, 0, 500, 800])
        copy.prepare_front_matter([p], {})
        self.assertEqual(p['_front_info'], [['J Example Surg 75:1377-1386, 2017']])
        self.assertEqual(set(p['_front_excluded']), {'c1'})


class Accounting(unittest.TestCase):
    def claims(self, units, rows):
        return tracer.claims_of(units, rows)

    def test_line_destinations(self):
        rows = [dict(page=1, runs=['r1'], text='abcdef'), dict(page=1, runs=['r2'], text='xyz')]
        units = [dict(group='g1', segs=[(0, 0, 3)], runs=[]), dict(group='g2', segs=[(0, 3, 6)], runs=[]),
                 dict(group='g3', segs=[(1, 0, 3)], runs=[]), dict(group='g4', segs=[(1, 0, 3)], runs=[])]
        lines = [dict(page=1, runs=['r1']), dict(page=1, runs=['r2']), dict(page=1, runs=['r3']),
                 dict(page=1, runs=['r4']), dict(page=1, runs=['r5']), dict(page=1, runs=['r1', 'r3'])]
        records, unknown = tracer.account(lines, self.claims(units, rows), {(1, 'r4'): 'running head'},
                                          {(1, 'r5'): 'read text not placed'}, {(1, f'r{i}'): i for i in range(1, 6)})
        self.assertEqual([r['status'] for r in records], ['split', 'duplicate', 'lost', 'furniture', 'uncertainty', 'partly_lost'])
        self.assertEqual(unknown, [])

    def test_partial_and_flagged_front_repeat_are_listed_not_duplicates(self):
        rows = [dict(page=1, runs=['r1'], text='Ana One, Bea Two')]
        kinds = ['author', 'front_matter_printed', 'paragraph']
        units = [dict(group='g1', segs=[], runs=[(1, 'r1', False)]), dict(group='g2', segs=[(0, 0, 16)], runs=[]),
                 dict(group='g3', segs=[(0, -1, -1)], runs=[])]
        claims = self.claims(units[:2], rows)
        self.assertEqual(tracer.run_status(claims[1, 'r1'], kinds), 'flagged_repeat')
        claims = self.claims([units[0], units[2]], rows)
        self.assertEqual(tracer.run_status(claims[1, 'r1'], ['author', 'paragraph']), 'split_unverified')
        claims = self.claims([units[1], dict(group='g9', segs=[(0, 0, 16)], runs=[])], rows)
        self.assertEqual(tracer.run_status(claims[1, 'r1'], ['front_matter_printed', 'paragraph']), 'duplicate')

    def test_span_map_survives_inserted_float_lines(self):
        pre = 'Intro text.\n\n<!-- copy-float 1:3 -->\n\nAfter text.'
        final = 'Intro text.\n\nImage file: figures/f.png (page 1)\n\nAfter text.\n'
        spans, inserted, starts = tracer.map_spans(pre, {0: [0, 11], 1: [pre.index('After'), len(pre)]}, final)
        self.assertEqual(final[slice(*spans[0])], 'Intro text.')
        self.assertEqual(final[slice(*spans[1])], 'After text.')
        late = tracer.locate_late([dict(text='Image file: figures/f.png (page 1)')], final, inserted, starts, [])
        self.assertEqual(final[slice(*late[0])], 'Image file: figures/f.png (page 1)')


class Checks(unittest.TestCase):
    def test_body_order_skips_page_and_column(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            Path(tmp, 'body-order.json').write_text(json.dumps(dict(blocks=[dict(page=1, id='b1')], unplaced=[])))
            main = lambda bid, x: dict(id=bid, cls='main', order=1, box_px=[x, 0, x+90, 50], text='words here')
            pages = [dict(page=1, main_text=dict(columns=[[0, 100], [110, 200]], blocks=[main('b1', 0), main('b2', 110)])),
                     dict(page=2, main_text=dict(columns=[[0, 100]], blocks=[main('b3', 0)]))]
            findings = tracer.check_body_order(tmp, pages)['findings']
        self.assertEqual([(f['kind'], f['page']) for f in findings], [('column_skipped', 1), ('page_skipped', 2)])

    def test_float_pairing(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            Path(tmp, 'copy.floats.json').write_text(json.dumps(dict(floats=[
                dict(id='Figure 1', check=dict(status='paired'), parts=[dict(page=1)]),
                dict(id='Figure 2', check=dict(status='caption_without_float'), parts=[dict(page=3)]),
                dict(id='Unlabelled figure p4-1', check=dict(status='float_without_caption'), parts=[dict(page=4)])])))
            findings = tracer.check_floats(tmp)['findings']
        self.assertEqual([(f['id'], f['kind']) for f in findings],
                         [('Figure 2', 'caption_without_float'), ('Unlabelled figure p4-1', 'float_without_caption')])


class Validator(unittest.TestCase):
    def test_recompute_matches_and_detects_tampering(self):
        line = dict(page=1, runs=['r1'], status='unit', groups=['g1'])
        claims = {(1, 'r1'): [dict(group='g1', unit=0, row=0, start=0, end=4, partial=False)]}
        self.assertEqual(validator.recompute_line(line, claims, {0: 'paragraph'}, set(), set()), ('unit', ['g1']))
        claims[1, 'r1'].append(dict(group='g2', unit=1, row=0, start=0, end=4, partial=False))
        self.assertEqual(validator.recompute_line(line, claims, {0: 'paragraph', 1: 'paragraph'}, set(), set())[0], 'duplicate')
        self.assertEqual(validator.recompute_line(dict(line, runs=['r9']), {}, {}, {(1, 'r9')}, set())[0], 'furniture')
        self.assertEqual(validator.recompute_line(dict(line, runs=['r9']), {}, {}, set(), set())[0], 'lost')

    def test_validate_refuses_a_changed_copy(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder = Path(tmp)
            (folder/'copy.md').write_text('Hello world.\n')
            trace = dict(schema='copy-trace/2 (native)', copy=dict(sha256='0'*64), pdf=dict(path=None, sha256=None),
                         units=[dict(id='u00001', kind='paragraph', group='g', span=[0, 12], text='Hello world.', status='traced',
                                     claims=dict(rows=[[0, 0, 12]], runs=[]))],
                         rows=[dict(row=0, page=1, runs=['r1'], text='Hello world.')],
                         lines=[dict(id='l1', export_id='p1.l001', page=1, text='Hello world.', runs=['r1'], status='unit', groups=['g'])],
                         furniture_runs=[], uncertainty_runs=[])
            (folder/'copy.trace.json').write_text(json.dumps(trace))
            report = validator.validate(folder)
            self.assertFalse(report['valid'])
            self.assertIn('copy.md does not match the trace hash', report['problems'])
            trace['copy']['sha256'] = validator.sha(folder/'copy.md')
            (folder/'copy.trace.json').write_text(json.dumps(trace))
            report = validator.validate(folder)
            self.assertTrue(report['ok'], report)
            trace['units'][0]['text'] = 'Hello'
            (folder/'copy.trace.json').write_text(json.dumps(trace))
            self.assertFalse(validator.validate(folder)['valid'])


if __name__ == '__main__': unittest.main()
