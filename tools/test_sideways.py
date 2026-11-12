"""Sideways table pages in scans (iss-14): a page printed sideways whose
publisher OCR holds only fragments is declared as a table not read, and its
fragments never print as body lines."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_sideways', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)


def run(text, x, y, w=240, size=12):
    return dict(text=text, box_px=[x, y, x+w, y+size], size_px=size)


def pdf_with_bars(path, bars, width=300, height=400, tilt_deg=0, texts=()):
    """A one-page PDF of filled rectangles (x, y, w, h in points, bottom-left origin)
    and Helvetica text (x, y, size, turn, string; turn 'up', 'down' or None for
    upright), optionally all turned by tilt_deg about the page centre (scan skew)."""
    import math
    content = ''.join(f'{x} {y} {w} {h} re f\n' for x, y, w, h in bars)
    turns = {None: '1 0 0 1', 'up': '0 1 -1 0', 'down': '0 -1 1 0'}
    content += ''.join(f'BT /F1 {size} Tf {turns[turn]} {x} {y} Tm ({text}) Tj ET\n'
                       for x, y, size, turn, text in texts)
    if tilt_deg:
        c, s = math.cos(math.radians(tilt_deg)), math.sin(math.radians(tilt_deg))
        cx, cy = width/2, height/2
        content = (f'q {c:.6f} {s:.6f} {-s:.6f} {c:.6f} {cx-c*cx+s*cy:.4f} {cy-s*cx-c*cy:.4f} cm\n'
                   + content + 'Q\n')
    content = content.encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Contents 4 0 R '
               '/Resources << /Font << /F1 5 0 R >> >> >>'.encode(),
               b'<< /Length %d >>\nstream\n' % len(content) + content + b'endstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    data = b'%PDF-1.4\n'; offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(data)); data += b'%d 0 obj\n' % i + body + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects)+1)
    data += b''.join(b'%010d 00000 n \n' % o for o in offsets)
    data += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects)+1, xref)
    Path(path).write_bytes(data)


def cells(row, k):
    """Invented table cells: a label and values."""
    return ['R%02d' % (row+1), '%d.%d' % (10+3*row, row % 10), '%d' % (40+7*row), '%d.%d' % (k+2, row % 7),
            '%d' % (5+row*k % 30)][k]


# A sideways table: 14 text lines of 5 cells, turned to run up (or down) the page; cell gaps line up.
def sideways_table(turn='up'):
    if turn == 'up':
        return [(40+16*i, 40+60*k, 8, 'up', cells(i, k)) for i in range(14) for k in range(5)]
    return [(40+16*i, 360-60*k, 8, 'down', cells(i, k)) for i in range(14) for k in range(5)]
# Its column rules, turned with the table: thin lines across the page between the cells.
COLUMN_RULES = [(24, 34+60*k, 240, .8) for k in range(6)]
# An upright table and its rules: 24 lines of the same cells.
UPRIGHT = [(30+52*k, 370-14*i, 8, None, cells(i, k)) for i in range(24) for k in range(5)]
UPRIGHT_RULES = [(24, 380-14*i, 250, .8) for i in range(0, 25, 4)]
DEBRIS = ['II', 'II.', 'I', '.1 "5', '«j', 'o', '3', 'I?', '1 CL', '<', '-J r"', 'a- t> r^ Qo u-i \\C',
          't-', 'se', 'c', '^ £', 'Ec', 'S g', 'Q S', 'Is', 'ill', "'3^", 'tio', '1^1']


class SidewaysTable(unittest.TestCase):
    def test_fragments_without_words_are_unreadable_prose_is_not(self):
        self.assertTrue(copy.scan_ocr_unreadable([run(t, 10, 10) for t in DEBRIS]))
        prose = [run('The chewing forces were measured in each subject', 10, 10)]*3
        self.assertFalse(copy.scan_ocr_unreadable(prose))
        # A table of values keeps its labels and notes: one word per four runs is enough.
        values = [run(v, 10, 10) for v in ['12.5', '3.1', '44', 'Total']]
        self.assertFalse(copy.scan_ocr_unreadable(values))
        self.assertFalse(copy.scan_ocr_unreadable([]))

    def test_sideways_text_lines_are_measured_upright_lines_and_pictures_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            sideways, upright, picture = (os.path.join(tmp, n+'.pdf') for n in ('s', 'u', 'p'))
            pdf_with_bars(sideways, [], texts=sideways_table()); pdf_with_bars(upright, [], texts=UPRIGHT)
            pdf_with_bars(picture, [(30, 50, 240, 300)])
            found = copy.scan_sideways_lines(sideways, 1)
            self.assertIsNotNone(found)
            self.assertGreaterEqual(found['line_bands'], 10)
            # Turned glyphs: their strokes run along the rows, so rows hold fewer ink runs than columns.
            self.assertLess(found['stroke_runs_rows_per_column'], 1)
            # The table's lined-up cell gaps leave more blank rows than its line gaps leave blank
            # columns; the page is still read as sideways.
            self.assertGreater(found['blank_row_share'], found['blank_column_share'])
            self.assertIsNone(copy.scan_sideways_lines(upright, 1))
            self.assertIsNone(copy.scan_sideways_lines(picture, 1))
            self.assertIsNone(copy.scan_sideways_lines(None, 1))
            self.assertIsNone(copy.scan_sideways_lines(os.path.join(tmp, 'missing.pdf'), 1))

    def test_drawn_rules_are_cleared_type_is_kept(self):
        w, h = 300, 50
        ink = bytearray(w*h)
        for x in range(10, 290): ink[20*w+x] = 1                 # a rule, 2.8 in long
        for x in range(10, 290): ink[30*w+x+0] = (x//20) % 2     # dashes of type-sized ink
        for y in range(5, 45): ink[y*w+150] = 1                  # a short upright stroke
        cleared = copy.scan_mask_rules(w, h, ink)
        self.assertEqual(cleared, 279)                           # all but the crossing with the stroke
        self.assertEqual(sum(ink[20*w:21*w]), 1)
        self.assertEqual(sum(ink[30*w:31*w]), 140)
        self.assertEqual(sum(ink[y*w+150] for y in range(5, 45)), 40)
        # Solid ink thicker than a rule (a bar, a picture) is kept.
        bar = bytearray(w*h)
        for y in range(10, 18):
            for x in range(10, 290): bar[y*w+x] = 1
        self.assertEqual(copy.scan_mask_rules(w, h, bar), 0)

    def test_sideways_table_with_column_rules_is_measured(self):
        """The rules of a sideways table cross every page column; they are not text lines."""
        with tempfile.TemporaryDirectory() as tmp:
            ruled, upright = os.path.join(tmp, 'r.pdf'), os.path.join(tmp, 'u.pdf')
            pdf_with_bars(ruled, COLUMN_RULES, texts=sideways_table('down'))
            pdf_with_bars(upright, UPRIGHT_RULES, texts=UPRIGHT)
            found = copy.scan_sideways_lines(ruled, 1)
            self.assertIsNotNone(found)
            self.assertGreater(found['rule_pixels_cleared'], 0)
            self.assertGreaterEqual(found['line_bands'], 10)
            self.assertIsNone(copy.scan_sideways_lines(upright, 1))

    def test_skewed_sideways_page_is_measured_along_its_text_angle(self):
        with tempfile.TemporaryDirectory() as tmp:
            for tilt in (1.5, -2.5):
                skewed, ruled, upright = (os.path.join(tmp, n+'.pdf') for n in ('s', 'r', 'u'))
                pdf_with_bars(skewed, [], tilt_deg=tilt, texts=sideways_table())
                pdf_with_bars(ruled, COLUMN_RULES, tilt_deg=tilt, texts=sideways_table('down'))
                pdf_with_bars(upright, UPRIGHT_RULES, tilt_deg=tilt, texts=UPRIGHT)
                for path in (skewed, ruled):
                    found = copy.scan_sideways_lines(path, 1)
                    self.assertIsNotNone(found, (tilt, path))
                    # A turn counterclockwise on the PDF page is a negative angle on the raster (y down).
                    self.assertLessEqual(abs(found['text_angle_deg']+tilt), .5)
                self.assertIsNone(copy.scan_sideways_lines(upright, 1))

    def test_both_tests_must_pass(self):
        p = dict(page=4)
        debris = [run(t, 10, 10) for t in DEBRIS]
        evidence = dict(dpi=100, blank_column_share=.4, blank_row_share=.07, line_bands=40, widest_line_band_in=.09)
        with patch.object(copy, 'scan_sideways_lines', return_value=evidence) as lines:
            self.assertEqual(copy.scan_sideways_table(p, debris, 'x.pdf')['ocr_runs'], len(debris))
            prose = [run('The chewing forces were measured in each subject', 10, 10)]*5
            self.assertIsNone(copy.scan_sideways_table(p, prose, 'x.pdf'))
            self.assertEqual(lines.call_count, 1)   # no render unless the OCR test passes
        with patch.object(copy, 'scan_sideways_lines', return_value=None):
            self.assertIsNone(copy.scan_sideways_table(p, debris, 'x.pdf'))

    def test_page_is_declared_and_fragments_never_print(self):
        body = [run('Ordinary body prose with several printed words, and the following', 60, 150+22*i, 300, 18)
                for i in range(12)]
        pages = [dict(page=1, region_box_px=[0, 0, 800, 1200], elements=[], scan_evidence=dict(ocr_layer=True, ocr_runs=body)),
                 dict(page=2, region_box_px=[0, 0, 800, 1200], elements=[], scan_evidence=dict(ocr_layer=True,
                      ocr_runs=[run(t, 480+(i % 4)*40, 150+30*i, 30, 12) for i, t in enumerate(DEBRIS)])),
                 dict(page=3, region_box_px=[0, 0, 800, 1200], elements=[], scan_evidence=dict(ocr_layer=True,
                      ocr_runs=[run('correlation analyses were performed.', 60, 150, 300, 18),
                                *[run('A new paragraph of body prose with printed words', 60, 200+22*i, 300, 18)
                                  for i in range(10)]]))]
        evidence = dict(dpi=100, blank_column_share=.4, blank_row_share=.07, line_bands=40, widest_line_band_in=.09)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(copy, 'table_pdf_path', return_value=None), \
             patch.object(copy, 'scan_sideways_lines', side_effect=lambda pdf, page: evidence if page == 2 else None):
            text = Path(copy.copy_ocr_scan(tmp, pages, {})).read_text()
            scan = json.loads(Path(tmp, 'copy.scan.json').read_text())
            tables = json.loads(Path(tmp, 'copy.tables.json').read_text())['tables']
            conservation = json.loads(Path(tmp, 'copy.conservation.json').read_text())
        body_text = text.split('## Places the program is not sure of')[0]
        for fragment in ('a- t> r^ Qo', '1^1', "'3^"):
            self.assertNotIn(fragment, text)
        self.assertIn(copy.SCAN_SIDEWAYS_CAPTION, body_text)
        self.assertIn('[table not read: page 2 is printed sideways', body_text)
        # The notice holds for text running up or down the page.
        self.assertIn('its text lines run along the length of the page', body_text)
        self.assertNotIn('run up the page', text)
        self.assertIn(f'({len(DEBRIS)} runs, withheld', body_text)
        # The declaration waits for the sentence running over the page break.
        self.assertLess(body_text.index('correlation analyses were performed.'), body_text.index(copy.SCAN_SIDEWAYS_CAPTION))
        notes = text.split('## Places the program is not sure of')[1]
        self.assertIn('- page 2: a table printed sideways was not read', notes)
        self.assertIn('garbled', notes)   # tools/agree.py proposes the page to the page readers
        page2 = next(a for a in scan['pages'] if a['page'] == 2)
        self.assertEqual(len(page2['sideways_table']['withheld']), len(DEBRIS))
        self.assertEqual(set(page2['destinations'].values()), {'sideways table not read'})
        self.assertEqual([t['decision'] for t in tables], ['image_not_read'])
        excluded = next(p for p in conservation['pages'] if p['page'] == 2)['copy_conservation']['excluded']
        self.assertEqual(len(excluded), len(DEBRIS))
        self.assertFalse([t for t in conservation['token_ledger']['tokens'] if t['page'] == 2])

    def test_embedded_scan_section_returns_its_declaration_and_exclusions(self):
        pages = [dict(page=5, region_box_px=[0, 0, 800, 1200], elements=[], scan_evidence=dict(ocr_layer=True,
                      ocr_runs=[run(t, 480+(i % 4)*40, 150+30*i, 30, 12) for i, t in enumerate(DEBRIS)]))]
        evidence = dict(dpi=100, blank_column_share=.4, blank_row_share=.07, line_bands=40, widest_line_band_in=.09)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(copy, 'table_pdf_path', return_value=None), \
             patch.object(copy, 'scan_sideways_lines', return_value=evidence):
            record = copy.copy_ocr_scan(tmp, pages, {}, embedded=True)
        self.assertNotIn('a- t> r^ Qo', record['text'])
        self.assertIn('[table not read: page 5 is printed sideways', record['text'])
        self.assertEqual(len(record['sideways_notes']), 1)
        self.assertTrue(record['sideways_notes'][0].startswith('page 5: a table printed sideways was not read'))
        self.assertEqual(len(record['conservation'][0]['copy_conservation']['excluded']), len(DEBRIS))


if __name__ == '__main__':
    unittest.main()
