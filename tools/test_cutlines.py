"""Body characters at a page edge: the visible-page region (rule 1) and the trace's partly excluded body lines.

Run: /usr/bin/python3 -I tools/test_cutlines.py
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


boxer = load('_copy_table_reader', ROOT/'standalone/element_boxer_sc.py')
tracer = load('cutlines_trace', ROOT/'tools/copy_trace.py')
validator = load('cutlines_validator', ROOT/'tools/trace.py')
conserve = load('cutlines_conserve', ROOT/'tools/conserve.py')
# 2009 Int J Periodontics Restorative Dent (AI03): MediaBox 864 x 849, CropBox from (43.2, 21.6).
AI03 = Path('/mnt/ai/projects/optionsdds/trials/element-boxer-batch32-inputs/papers/AI03/paper.pdf')
# 1999 J Periodontol (AH06): CropBox from (43.2, 36); "†Department" set apart beside the body column.
AH06 = Path('/mnt/ai/projects/optionsdds/trials/element-boxer-batch31-inputs/papers/AH06/paper.pdf')


class VisiblePage(unittest.TestCase):
    def doc(self, crop, rotate=0):
        w, h = crop[2]-crop[0], crop[3]-crop[1]
        page = types.SimpleNamespace(rotate=rotate)
        size = (h, w, crop) if rotate % 180 == 90 else (w, h, crop)
        return types.SimpleNamespace(pages=[page], page_size=lambda n: size)

    def test_offset_cropbox_is_the_visible_page_in_the_reading_frame(self):
        with patch.object(boxer, 'sc_doc', return_value=self.doc((43.2, 21.6, 626.4, 827.4))):
            box = boxer.sc_page_box_px('unused.pdf', 1)
        want = [boxer.px(v) for v in (43.2, -21.6, 626.4, 784.2)]
        self.assertTrue(all(abs(a-b) < 1e-9 for a, b in zip(box, want)), box)

    def test_zero_origin_and_rotated_pages_keep_the_old_box(self):
        with patch.object(boxer, 'sc_doc', return_value=self.doc((0, 0, 612, 792))):
            self.assertEqual(boxer.sc_page_box_px('unused.pdf', 1), [0, 0, boxer.px(612), boxer.px(792)])
        with patch.object(boxer, 'sc_doc', return_value=self.doc((15, 20, 615, 800), rotate=90)):
            self.assertEqual(boxer.sc_page_box_px('unused.pdf', 1), [0, 0, boxer.px(780), boxer.px(600)])

    @unittest.skipUnless(AI03.is_file(), 'AI03 PDF not on this machine')
    def test_right_column_edge_keeps_its_letters(self):
        # The last 43 pt of the right column were outside the zero-based page box.
        part = dict(page=2, box_px=boxer.sc_page_box_px(str(AI03), 2), caption_boxes_px=[])
        res = boxer.box_elements(str(AI03), part, 'page 2')
        text = ' '.join(e['text'] for e in res['elements'] if e['kind'] == 'text')
        for word in ('analysis.', 'palatal', 'edges'):
            self.assertIn(word, text)
        self.assertEqual(res['counts']['characters_in_region'],
                         sum(1 for c in boxer.pdfium_characters(str(AI03), 2)
                             if part['box_px'][0] <= (c['x0']+c['x1'])/2 <= part['box_px'][2]))


class AddressLineMark(unittest.TestCase):
    @unittest.skipUnless(AH06.is_file(), 'AH06 PDF not on this machine')
    def test_mark_led_address_beside_the_body_column_keeps_its_mark(self):
        # Once the visible-page region aligned AH06's character ids, rule 8 read the
        # small "†Department" line against the body column's size and lost its mark.
        boxer_py = str(ROOT/'standalone/element_boxer_sc.py'); env = dict(PATH='/usr/bin', BOXER_SC_BACKGROUND='white')
        with tempfile.TemporaryDirectory(prefix='.cutlines-', dir=ROOT) as tmp:
            for args in (['--pdf', str(AH06), '--all-pages', '--out', tmp, '--no-draw'], ['--paper', tmp, '--no-draw'],
                         ['--authors', '--pdf', str(AH06), '--paper', tmp]):
                subprocess.run([sys.executable, '-I', '-S', boxer_py, *args], env=env, capture_output=True, check=True)
            authors = json.loads(Path(tmp, 'authors.json').read_text())
        self.assertEqual(authors['checks']['status'], 'verified')
        self.assertEqual(sorted(a['marker'] for a in authors['affiliations']), ['*', '†'])


def char(text, x, base=100, size=10, angle=0, hidden=False):
    return dict(text=text, x0=x, x1=x+4, y0=base-8, y1=base, origin=(x, base), size=size, angle=angle, hidden=hidden)


class PartlyExcluded(unittest.TestCase):
    def setUp(self):
        body = [char(t, 10+5*i) for i, t in enumerate('abcd')]          # ids 0-3, the body run (to x 29)
        furniture = [char('f', 31), char('g', 36)]                         # ids 4-5, a run counted as furniture
        extras = [char('W', 30, angle=90),                                 # id 6: a rotated watermark letter
                  char('2', 41, base=96, size=6),                          # id 7: a superscript
                  char('b', 15.2),                                         # id 8: an overprinted 'b'
                  char('z', 20, base=200)]                                 # id 9: another line's letter
        self.chars = body + furniture + extras + [char('e', 44), char('x', 300)]   # outside the region
        self.reader = types.SimpleNamespace(PARAMS=dict(dpi=150), sc_read_page=lambda pdf, n: (self.chars, [], {}))
        self.page = dict(page=1, region_box_px=[0, 0, 45, 800], params=dict(dpi=150), elements=[
            dict(id='run:1', kind='text', text='abcd', char_ids=[0, 1, 2, 3], box_px=[10, 92, 29, 100]),
            dict(id='run:2', kind='text', text='fg', char_ids=[4, 5], box_px=[31, 92, 40, 100])])
        self.lines = [dict(page=1, runs=['run:1']), dict(page=1, runs=['run:2'])]
        self.records = [dict(status='unit', runs=[dict(run='run:1', status='unit')]),
                        dict(status='furniture', runs=[dict(run='run:2', status='furniture')])]

    def test_lists_unboxed_and_furniture_letters_on_the_line_only(self):
        found = tracer.excluded_body_characters('unused.pdf', [self.page], self.lines, self.records,
                                                {(1, 'run:2'): 'running head'}, reader=self.reader)
        self.assertEqual(list(found), [0])
        self.assertEqual({e['reason']: e['text'] for e in found[0]},
                         {'counted as furniture: running head': 'fg',
                          'in no rule-1 text element (outside the page region)': 'e'})

    def test_far_letters_and_other_lines_do_not_fail(self):
        self.page['elements'][1]['char_ids'] = []
        self.chars[-2].update(x0=200, x1=204, origin=(200, 100))
        found = tracer.excluded_body_characters('unused.pdf', [self.page], self.lines, self.records, {}, reader=self.reader)
        self.assertEqual(found.get(0, []) and [e['text'] for e in found[0]], ['fg'])   # unboxed, chained to the line
        self.chars[4].update(x0=100, x1=104, origin=(100, 100)); self.chars[5].update(x0=105, x1=109, origin=(105, 100))
        found = tracer.excluded_body_characters('unused.pdf', [self.page], self.lines, self.records, {}, reader=self.reader)
        self.assertEqual(found, {})

    def test_margin_number_set_off_by_a_word_gap_is_not_the_lines(self):
        # proof line numbers counted as furniture, within an em of the text (W07)
        self.chars[4].update(text='2', x0=33, x1=37, origin=(33, 100)); self.chars[5].update(text='4', x0=37.5, x1=41.5, origin=(37.5, 100))
        self.page['elements'][1].update(text='24', box_px=[33, 92, 41.5, 100])
        self.chars[-2].update(x0=300, x1=304, origin=(300, 100))
        found = tracer.excluded_body_characters('unused.pdf', [self.page], self.lines, self.records,
                                                {(1, 'run:2'): 'margin numbers'}, reader=self.reader)
        self.assertEqual(found, {})
        self.chars[4].update(x0=29.5, x1=33.5, origin=(29.5, 100))   # touching the last letter: part of a word
        found = tracer.excluded_body_characters('unused.pdf', [self.page], self.lines, self.records,
                                                {(1, 'run:2'): 'margin numbers'}, reader=self.reader)
        self.assertEqual([e['text'] for e in found[0]], ['24'])

    def test_validator_fails_a_recorded_partly_excluded_line(self):
        line = dict(page=1, runs=['run:1'], status='partly_excluded', excluded_body_characters=[dict(text='e')])
        status, _ = validator.recompute_line(line, {(1, 'run:1'): [dict(group='g', unit=0, row=0, start=0, end=4, partial=False)]},
                                             {0: 'paragraph'}, set(), set())
        self.assertEqual(status, 'unit')                       # the claims alone account for it
        self.assertIn('partly_excluded', validator.LINE_FAIL)   # validate() applies the recorded evidence
        self.assertIn('partly_excluded', tracer.LINE_FAIL)


class ConservationCover(unittest.TestCase):
    def test_a_sideways_watermark_box_holds_only_its_own_words(self):
        word = dict(text='analysis.', box=[100, 100, 140, 110], native_box=[100, 100, 140, 110])
        mark = dict(text='Downloaded from https://example.org', box=[90, 0, 150, 800], reason='watermark', angle=90)
        self.assertIsNone(conserve.covered(word, [mark], 1, 1))
        self.assertEqual(conserve.covered(dict(word, text='Downloaded'), [mark], 1, 1), 'watermark')
        self.assertEqual(conserve.covered(word, [dict(mark, angle=0)], 1, 1), 'watermark')


if __name__ == '__main__':
    unittest.main()
