"""Lane r2-frontfusion: front-page furniture stays out of body text; the abstract flag stays on the front page;
a numbered body heading is not an affiliation.

Rules: (1) rejoin_paragraphs: after a piece ending in a closed web address, a next piece opening in lower case or
with an opening bracket keeps the ordinary decision; one opening with a capital is not joined after a labelled or lone
address row (whatever its width), nor after prose when its layout opens a paragraph: a first-line indent (first row
inset, second at the column edge; one row inset on the left with a free right end) or a block inset with only white
space above it in its own column and extra leading against the page's other columns (a block under a float is level). (2) A 'Summary'/'Abstract' block heading on a later page, after the body has begun, opens a
body section: its text is not an abstract part. (3) Rule 8: a text after a byline marker set at heading size
(heading_size_ratio of the body size or more) outside the byline's address band is a body heading, never an
address. Fixtures are invented (no paper's text): synthetic geometry and one small pycairo PDF.
"""
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); mod.__dict__['__file__'] = str(path); spec.loader.exec_module(mod)
    return mod


boxer = module('frontfusion_boxer', ROOT/'standalone/element_boxer_sc.py')
copy = module('frontfusion_copy', ROOT/'copy_paper.py')


class WebAddressTail(unittest.TestCase):
    """(1) A web-address row at a column or page foot does not run on into the next body head."""
    def items(self, tail, head, full=False, same_page=False, flush=True, rows=None, top=300, column_top=None):
        """ROWS: the head piece's first rows as (left inset, right inset) from its column's edges."""
        a = dict(kind='para', text=tail, page=1, box=[200, 1200, 700, 1222], size=20.8, col=(200, 1060),
                 flow_start=(1, 0, True), flow_end=(1, 0, full))
        l, r = (1100, 1560) if same_page else (120, 545)
        if rows is None: rows = [(0, 0), (0, 0)] if flush else [(25, 0), (0, 0)]
        geom = dict(rows=[[l + li, top + 25 * k, r - ri, top + 25 * k + 20] for k, (li, ri) in enumerate(rows)], col=(l, r))
        b = dict(kind='para', text=head, page=1 if same_page else 2, box=[l, top, r, 900],
                 size=20.8, col=(l, r), flow_start=(1 if same_page else 2, 1 if same_page else 0, rows[0][0] <= 4),
                 flow_end=(1 if same_page else 2, 1 if same_page else 0, True), start_rows=geom)
        out = [a, dict(kind='page', page=1), b]
        if column_top is not None:   # an earlier body paragraph heading the first column
            out.insert(0, dict(kind='para', text='An earlier paragraph ends here.', page=1, box=[200, column_top, 1060, 1100],
                               size=20.8, col=(200, 1060), flow_start=(1, 0, True), flow_end=(1, 0, False)))
        return out

    def join(self, items):
        return [it for it in copy.rejoin_paragraphs(items, copy.Joiner([]), 20.8) if it['kind'] == 'para']

    def test_address_row_at_a_page_foot_is_not_joined_to_the_next_page_body(self):
        out = self.join(self.items('Reprint permissions are listed at: http://www.example-press.org/rights/permissions',
                                   'In the coastal survey the plates were read at each visit.'))
        self.assertEqual(len(out), 2)

    def test_address_row_at_a_column_foot_is_not_joined_to_the_next_column(self):
        out = self.join(self.items('Data online: https://www.example-press.org/data/flats',
                                   'Station records were checked before each visit.', same_page=True))
        self.assertEqual(len(out), 2)

    def test_address_row_filling_the_measure_at_a_page_foot_is_not_joined(self):
        out = self.join(self.items('Permissions for this article: www.example-press.org/rights/permission.asp',
                                   'Survey teams kept a log of every visit.', full=True))
        self.assertEqual(len(out), 2)

    def test_address_row_filling_the_measure_with_a_lowercase_continuation_joins(self):
        out = self.join(self.items('the station records are listed at www.example-press.org/data/stations/all',
                                   'and in the appendix, where each is named.', full=True))
        self.assertEqual(len(out), 1)

    def test_full_prose_row_at_a_page_foot_keeps_its_join(self):
        out = self.join(self.items('the plates were compared with the stakes laid out by the', 'Harbour Board in an earlier survey.', full=True))
        self.assertEqual(len(out), 1)

    def test_access_date_bracket_after_an_address_in_prose_joins(self):
        out = self.join(self.items('Hourly heights were taken from https://www.example-tides.org/hourly',
                                   '(retrieved 12 June 2024) and checked against the crew log.'))
        self.assertEqual(len(out), 1)

    def test_flush_proper_noun_after_an_address_in_prose_joins(self):
        out = self.join(self.items('the tide records were drawn from https://www.example-tides.net/records',
                                   'Harbour Authority logs were added for the winter.'))
        self.assertEqual(len(out), 1)

    def test_indented_capital_after_an_address_in_prose_is_a_new_paragraph(self):
        out = self.join(self.items('The survey data are archived at https://www.example-press.org/archive',
                                   'Results of the first season are given in the tables.', flush=False))
        self.assertEqual(len(out), 2)

    def test_block_inset_continuation_after_an_address_joins(self):
        # every row 30 px in on both sides, level with the head of the other column: a block continuing the sentence
        out = self.join(self.items('Water levels were drawn from https://www.example-levels.org/hourly',
                                   'Harbour Authority logs, and the two records were merged.', same_page=True,
                                   rows=[(30, 30), (30, 30)], column_top=300))
        self.assertEqual(len(out), 2)   # the earlier paragraph and the joined piece
        self.assertIn('hourly Harbour Authority', out[1]['text'])

    def test_one_row_block_inset_continuation_joins(self):
        out = self.join(self.items('Water levels were drawn from https://www.example-levels.org/hourly',
                                   'Harbour Authority logs.', rows=[(30, 30)]))
        self.assertEqual(len(out), 1)

    def test_one_row_first_line_indent_reaching_the_right_edge_is_a_new_paragraph(self):
        out = self.join(self.items('The survey data are archived at https://www.example-press.org/archive',
                                   'Results of the first season are given in the tables below.', rows=[(25, 0)]))
        self.assertEqual(len(out), 2)

    def test_hanging_indent_continuation_joins(self):
        out = self.join(self.items('Water levels were drawn from https://www.example-levels.org/hourly',
                                   'Harbour Authority logs, and the two records were merged.', rows=[(0, 0), (30, 0)]))
        self.assertEqual(len(out), 1)

    def test_block_inset_with_extra_leading_above_is_a_new_paragraph(self):
        out = self.join(self.items('The survey data are archived at https://www.example-press.org/archive',
                                   'Results of the first season are quoted here.', same_page=True,
                                   rows=[(30, 30), (30, 30)], top=340, column_top=300))
        self.assertEqual(len(out), 3)

    def test_short_one_row_paragraph_inset_on_the_left_only_is_a_new_paragraph(self):
        out = self.join(self.items('The survey data are archived at https://www.example-press.org/archive',
                                   'Results are listed in the table.', rows=[(25, 260)]))
        self.assertEqual(len(out), 2)

    def test_block_inset_under_a_float_is_level_and_joins(self):
        items = self.items('Water levels were drawn from https://www.example-levels.org/hourly',
                           'Harbour Authority logs, and the two records were merged.', same_page=True,
                           rows=[(30, 30), (30, 30)], top=560, column_top=300)
        items.insert(2, dict(kind='figure', page=1, caption='Figure 1. Gauge stations.', box=[1100, 300, 1560, 530]))
        out = self.join(items)
        self.assertEqual(len(out), 2)
        self.assertIn('hourly Harbour Authority', out[1]['text'])

    def test_lone_address_row_before_a_capital_is_not_joined(self):
        out = self.join(self.items('https://www.example-press.org/rights/permissions', 'In the coastal survey the plates were read.'))
        self.assertEqual(len(out), 2)

    def test_lowercase_continuation_after_an_address_still_joins(self):
        out = self.join(self.items('the stations are listed at https://www.example-press.org/data/flats',
                                   'and in the appendix, where each is named.'))
        self.assertEqual(len(out), 1)
        self.assertIn('flats and in the appendix', out[0]['text'])

    def test_unterminated_prose_at_a_page_foot_keeps_its_layout_join(self):
        out = self.join(self.items('the plates were compared with the stakes laid by the',
                                   'Harbour Board in an earlier survey of the flats.'))
        self.assertEqual(len(out), 1)

    def test_open_address_broken_at_a_slash_keeps_its_join(self):
        out = self.join(self.items('see https://www.example-press.org/rights/', 'Permissions for each figure.'))
        self.assertEqual(len(out), 1)


def page(number, specs, body=16, height=1400):
    """specs: (text, y, size, cls, block, special[, x]); special maps character offsets to (size, raised)."""
    chars = []; runs = []; blocks = []; classes = []; lines = {}
    for i, spec in enumerate(specs):
        text, y, size, cls, bid, special = spec[:6]
        x = spec[6] if len(spec) > 6 else 20; font = 'Regular'
        x0 = x; ids = []; sizes = []
        for j, ch in enumerate(text):
            em, raised = special.get(j, (size, False))
            if not ch.isspace():
                ids.append(len(chars)); sizes.append(em)
                chars.append(dict(text=ch, x0=x, x1=x+.45*em, y0=y-(5 if raised else 0), y1=y+.7*em-(5 if raised else 0),
                                  size=em, font=font, origin=(x, y+.7*em), adv_x1=x+.5*em))
            x += .5*em
        line = lines.setdefault(round(y), len(lines))
        e = dict(id=f'run:{i}', text=text, kind='text', line=line, angle=0, size_px=size, font=font,
                 run_size_px=statistics.median(sizes), char_ids=ids, box_px=[x0, y, x, y+.7*size])
        runs.append(e)
        b = next((b for b in blocks if b['id'] == bid), None)
        if b:
            b['members'].append(e['id']); b['box_px'] = copy.hull([b['box_px'], e['box_px']])
        else:
            blocks.append(dict(id=bid, members=[e['id']], box_px=e['box_px'])); classes.append(dict(id=bid, cls=cls, box_px=e['box_px']))
    return dict(page=number, elements=runs, blocks=blocks, art=[], region_box_px=[0, 0, 1000, height],
                main_text=dict(body_size_px=body, blocks=classes)), chars


def parse(fixtures):
    paths = [f'page-{i+1:02}.json' for i in range(len(fixtures))]
    with patch.object(boxer, 'page_files', return_value=paths), \
         patch.object(boxer, 'read_json', side_effect=lambda p: fixtures[paths.index(p)][0]), \
         patch.object(boxer, 'pdfium_characters', side_effect=lambda p, n: fixtures[n-1][1]), \
         patch.object(boxer, 'front_backgrounds', return_value=[]), \
         patch.object(boxer, 'write_json'):
        return boxer.authors_and_affiliations('unused', 'unused')


def raised_digits(text, size=10):
    return {i: (size, True) for i, ch in enumerate(text) if ch.isdigit()}


BYLINE = 'Orla Fenwick1, Teodor Vasse2 and Mira Calloway3'


class HeadingNumberIsNoMarker(unittest.TestCase):
    """(3) A body heading whose number equals a byline marker is not that marker's address."""
    def first(self, heading=True, address2=True, heading_size=22, cls='aside'):
        specs = [('Paired plates for tidal flat sediment records', 100, 30, 'title', 't', {}),
                 (BYLINE, 150, 17, 'authors', 'b', raised_digits(BYLINE)),
                 ('Abstract The paired plates were read together at many stations.', 220, 16, 'main', 'a', {})]
        if heading: specs.append(('2 Study Area and Aims', 400, heading_size, cls, 'h', {}))
        specs.append(('Fine flats along sheltered coasts store sediment at each tide.', 440, 16, 'main', 'm', {}, 520))
        rows = ['1Department of Marine Sciences, Kestrel University, Kestrel', '3Institute of Field Botany, Lowmoor University']
        if address2: rows.insert(1, '2Harbour Survey Trust, Port Avel')
        for k, r in enumerate(rows): specs.append((r, 1200 + 18*k, 12, 'other', 'f', {0: (8, True)}))
        return page(1, specs, body=16)

    def affiliations(self, a):
        return {x['marker']: x['text'] for x in a['affiliations']}

    def test_heading_size_heading_loses_to_the_footnote_address(self):
        a = parse([self.first()])
        self.assertEqual(self.affiliations(a)['2'], 'Harbour Survey Trust, Port Avel')

    def test_heading_alone_supplies_no_address(self):
        a = parse([self.first(address2=False)])
        self.assertNotIn('Study Area', ' '.join(self.affiliations(a).values()))

    def test_body_size_text_after_a_marker_is_still_a_candidate(self):
        # not set at heading size: the rule does not apply (the earlier choice stands)
        a = parse([self.first(heading_size=16)])
        self.assertIn('2', self.affiliations(a))

    def test_large_address_band_under_the_byline_stays_an_address(self):
        specs = [('Paired plates for tidal flat sediment records', 100, 30, 'title', 't', {}),
                 (BYLINE, 150, 17, 'authors', 'b', raised_digits(BYLINE))]
        for k, r in enumerate(['1Department of Marine Sciences, Kestrel University', '2Department of Geography, Avel University',
                               '3Institute of Field Botany, Lowmoor University']):
            specs.append((r, 175 + 22*k, 19, 'other', 'ab', {0: (12, True)}))
        specs.append(('Abstract The paired plates were read together at many stations.', 300, 16, 'main', 'a', {}))
        a = parse([page(1, specs, body=16)])
        self.assertEqual(self.affiliations(a).get('2'), 'Department of Geography, Avel University')


PDF_SCRIPT = r'''
import sys, cairo
out, closing = sys.argv[1], sys.argv[2] == 'closing'
s = cairo.PDFSurface(out, 612, 792); c = cairo.Context(s)
def f(bold=False, size=9.3): c.select_font_face('DejaVu Serif', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL); c.set_font_size(size)
def para(text, x, y, w=246):
    words = text.split(); cur = []
    for wd in words:
        if cur and c.text_extents(' '.join(cur + [wd])).x_advance > w: c.move_to(x, y); c.show_text(' '.join(cur)); y += 12; cur = [wd]
        else: cur.append(wd)
    if cur: c.move_to(x, y); c.show_text(' '.join(cur)); y += 12
    return y
TXT = ('Plates were buried in each zone and read with a thin rod at every visit, and the readings were set against the '
       'stakes laid out years before on the same flats. ') * 4
f(True, 15); c.move_to(120, 90); c.show_text('Paired Plates for Tidal Flat Records')
f(False, 9); c.move_to(220, 115); c.show_text('Orla N. Fenwick and Teodor J. Vasse')
f(True, 9.5); c.move_to(50, 150); c.show_text('Abstract' if closing else 'Summary')
f(); y = para('Background: Stakes drift when they are not relevelled. Methods: Plates and markers were read together '
              'at many stations for two years. Results: The readings agreed within a millimetre a year.', 50, 165, 510)
f(True, 11); c.move_to(50, y + 20); c.show_text('Introduction')
f(); para(TXT, 50, y + 36); para(TXT, 316, y + 36)
c.show_page()
f(); y = para(TXT, 50, 60); para(TXT, 316, 60)
if closing:
    f(True, 11); c.move_to(50, y + 20); c.show_text('Methods')
    f(); y = para(TXT, 50, y + 36) + 10
    f(); c.move_to(50, y); c.show_text('Summary'); y += 12
    para('The plates agreed with the markers at most stations, and the stakes drifted at half of them. '
         'Paired readings suit records that must last for decades.', 50, y)
s.finish()
'''


class SummaryFlag(unittest.TestCase):
    """(2) End to end on a small invented PDF: only the front page's abstract carries the abstract flag."""
    def copy_units(self, closing):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp, 'paper.pdf'); out = Path(tmp, 'out')
            subprocess.run(['/usr/bin/python3', '-I', '-c', PDF_SCRIPT, str(pdf), 'closing' if closing else 'front'], check=True)
            env = dict(os.environ, COPY_READERS='off', COPY_CHECK='off', COPY_SECONDPASS='0')
            subprocess.run([str(ROOT/'copy_pdf.sh'), str(pdf), str(out)], env=env, capture_output=True, cwd=tmp)
            trace = json.loads(Path(out, 'copy.trace.json').read_text())
            return [u['text'] for u in trace['units'] if u['kind'] == 'abstract_part']

    def test_closing_summary_on_a_later_page_is_no_abstract_part(self):
        parts = self.copy_units(closing=True)
        self.assertTrue(any(t.startswith('Background') for t in parts), parts)
        self.assertFalse(any('agreed with the markers' in t for t in parts), parts)

    def test_front_page_summary_abstract_keeps_the_flag(self):
        parts = self.copy_units(closing=False)
        self.assertTrue(any(t.startswith('Background') for t in parts), parts)


if __name__ == '__main__':
    unittest.main()
