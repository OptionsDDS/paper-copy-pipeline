"""Lane iss-09 (B2): a boxed two-column list is read row by row, or printed line by line with a notice.
Synthetic, keyless.

Run: /usr/bin/python3 -I tools/test_boxgrid.py
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boxgrid_copy', ROOT / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)

BODY = 10


def run(i, x, y, text, bold=False, width=None):
    w = width if width is not None else 5 * len(text)
    return dict(id=f'r{i}', kind='text', text=text, angle=0, line=y, box_px=[x, y, x + w, y + 9],
                run_size_px=BODY, size_px=BODY, font='AB+Serif-Bold' if bold else 'AB+Serif-Roman')


def grid_runs(header_bold=True, extra=()):
    """A shaded box: a prose line, a bold header, wrapped cells, a spanning bold label and two more rows."""
    rows = [
        [(100, 'Treatment is chosen for each patient and has to be evaluated again later', False, 380)],
        [(100, 'Finding', header_bold), (250, 'Aim', header_bold)],
        [(100, 'Pain at night', False), (250, 'Relieve pain and protect the', False)],
        [(250, 'teeth', False)],
        [(100, 'Loud grinding', False), (250, 'Remove the noise', False)],
        [(100, 'sounds', False)],
        [(100, 'Poor sleep', False), (250, 'Improve sleep', False)],
        [(100, 'Kind of treatment (single or combined)', True, 200)],
        [(100, 'Dental', False), (250, 'Splint', False)],
        [(100, 'Drugs', False), (250, 'Relaxant, antidepressant,', False)],
        [(250, 'muscle relaxant', False)],
    ] + list(extra)
    runs, i = [], 0
    for k, row in enumerate(rows):
        for cell in row:
            i += 1; runs.append(run(i, cell[0], 100 + 12 * k, cell[1], cell[2], cell[3] if len(cell) > 3 else None))
    return runs


FILL = [[90, 95, 500, 260]]


class BoxedTwoColumnGrid(unittest.TestCase):
    def texts(self, cells):
        return [' / '.join(e['text'] for e in c) for c in cells]

    def test_rows_wraps_and_spanning_label(self):
        g = copy.boxed_two_column_grid(grid_runs(), BODY, FILL)
        self.assertIsNotNone(g); self.assertIsNone(g['reason'])
        self.assertEqual(self.texts(g['header']), ['Finding', 'Aim'])
        self.assertEqual([(r['group'], self.texts(r['cells'])) for r in g['rows']], [
            (False, ['Pain at night', 'Relieve pain and protect the / teeth']),
            (False, ['Loud grinding / sounds', 'Remove the noise']),
            (False, ['Poor sleep', 'Improve sleep']),
            (True, ['Kind of treatment (single or combined)', '']),
            (False, ['Dental', 'Splint']),
            (False, ['Drugs', 'Relaxant, antidepressant, / muscle relaxant'])])

    def test_prose_above_is_not_a_cell(self):
        g = copy.boxed_two_column_grid(grid_runs(), BODY, FILL)
        self.assertNotIn('r1', g['ids'])
        self.assertEqual(len(g['printed']), 10)

    def test_no_frame_no_grid(self):
        self.assertIsNone(copy.boxed_two_column_grid(grid_runs(), BODY, []))
        self.assertIsNone(copy.boxed_two_column_grid(grid_runs(), BODY, [[90, 95, 500, 150]]))   # frame holds part only

    def test_headless_columns_are_left_to_other_rules(self):
        self.assertIsNone(copy.boxed_two_column_grid(grid_runs(header_bold=False), BODY, FILL))

    def test_unreadable_row_is_printed_line_by_line(self):
        # a capitalised line alone in the right column may wrap the cell above or open a row: printed, not guessed
        g = copy.boxed_two_column_grid(grid_runs(extra=[[(250, 'Behavioural therapy', False)]]), BODY, [[90, 95, 500, 270]])
        self.assertIsNotNone(g); self.assertIn('may wrap a cell or open a row', g['reason'])
        self.assertEqual(len(g['printed']), 11)

    def test_row_starting_in_one_column_only_is_unreadable(self):
        g = copy.boxed_two_column_grid(grid_runs(extra=[[(100, 'Stress', False), (250, 'and relaxation', False)]]),
                                       BODY, [[90, 95, 500, 270]])
        self.assertIn('begins in one column while the other wraps', g['reason'])

    def test_prose_columns_are_flagged_not_tabled(self):
        # two columns of wrapped prose under bold column heads: no line opens a table row, so the lines are printed
        # under the notice (read left to right they would interleave the columns)
        runs = [run(1, 100, 100, 'Methods', True), run(2, 250, 100, 'Results', True)]
        for k in range(1, 6):
            runs += [run(2*k+1, 100, 100+12*k, 'and the text goes on', False), run(2*k+2, 250, 100+12*k, 'while this goes on', False)]
        g = copy.boxed_two_column_grid(runs, BODY, FILL)
        self.assertEqual(g['rows'], []); self.assertIn('a line wraps a cell before any row opens', g['reason'])

    def test_out_block(self):
        g = copy.boxed_two_column_grid(grid_runs(), BODY, FILL)
        p = dict(page=3, region_box_px=[0, 0, 600, 800], elements=[])
        b = copy.grid_out_block(g, dict(order=7, in_refs=False), 'block:2', p, BODY)
        self.assertEqual((b['_box_kind'], b['order'], b['panel']), ('grid', 7, True))
        self.assertEqual([str(x) for x in b['_grid']['header'][1]], ['Aim'])
        self.assertEqual([str(x) for x in b['_grid']['rows'][1]['cells'][0]], ['Loud grinding', 'sounds'])
        self.assertEqual(b['_grid']['printed'], [])
        self.assertEqual(b['lines'][1], 'Pain at night Relieve pain and protect the')


def routed_page(page_no=2, fill=True, front=False, below=False):
    """A page whose shaded box no body rule placed (main_text cls 'other'): a body line above it and, with below,
    a body line printed under it. Page 1 with front=True is the front page (its side text: article information)."""
    gr = grid_runs()
    def text(i, y, t):
        return dict(id=i, kind='text', text=t, angle=0, line=y, box_px=[100, y, 480, y + 9], run_size_px=BODY,
                    size_px=BODY, font='AB+Serif-Roman')
    lines = [text('above', 40, 'A paragraph of the body text that runs across the page and ends here.')]
    if below: lines.append(text('below', 300, 'Another paragraph of the body text printed under the shaded box.'))
    es = lines + gr + ([dict(id='f1', kind='fill', box_px=FILL[0])] if fill else [])
    for e in es:
        if e['kind'] == 'text': e.update(char_ids=[], _faces={e['font']: len(e['text'])})
    hull = lambda xs: [min(e['box_px'][0] for e in xs), min(e['box_px'][1] for e in xs),
                       max(e['box_px'][2] for e in xs), max(e['box_px'][3] for e in xs)]
    blocks = [dict(id='b-'+e['id'], members=[e['id']], box_px=e['box_px']) for e in lines]
    blocks.append(dict(id='box', members=[e['id'] for e in gr], box_px=hull(gr)))
    mt = [dict(id='b-'+e['id'], cls='main', order=k, lines=1, size_px=BODY, box_px=e['box_px']) for k, e in enumerate(lines)]
    mt.append(dict(id='box', cls='other', lines=11, size_px=BODY, box_px=hull(gr)))
    p = dict(page=page_no, elements=es, blocks=blocks, tables=[], floats=[], region_box_px=[0, 0, 600, 800],
             main_text=dict(blocks=mt, columns=[[90, 500]]))
    if front: p['_copy_front'] = True
    return p


class BoxedListWhereverRead(unittest.TestCase):
    """Re-ladder (step 3, out-step3-iss-09): a box no body rule placed was given as side text (a "> " side quote,
    page-1 article information) with its cells interleaved; the grid rule applies to such a group too."""
    def read(self, p):
        unc = []
        out, _, side = copy.read_page(p, BODY, unc)
        return out, side, unc

    def test_side_box_is_read_as_grid_in_the_body(self):
        out, side, unc = self.read(routed_page())
        self.assertEqual(side, [])
        self.assertEqual([b.get('_box_kind') for b in out], [None, None, 'grid'])
        self.assertEqual(out[1]['lines'], ['Treatment is chosen for each patient and has to be evaluated again later'])
        self.assertTrue(out[1]['panel'] and out[2]['panel'])
        self.assertEqual([str(x) for x in out[2]['_grid']['header'][0]], ['Finding'])
        self.assertIsNone(out[2]['_grid']['reason']); self.assertEqual(unc, [])

    def test_front_page_box_is_not_article_information(self):
        out, side, _ = self.read(routed_page(page_no=1, front=True))
        self.assertEqual(side, [])
        self.assertIn('grid', [b.get('_box_kind') for b in out])

    def test_box_stands_before_the_block_printed_under_it(self):
        out, side, _ = self.read(routed_page(below=True))
        self.assertEqual([b.get('_box_kind') or b['lines'][0][:7] for b in out],
                         ['A parag', 'Treatme', 'grid', 'Another'])
        self.assertEqual(out[2]['order'], out[3]['order'])

    def test_unframed_side_group_stays_side_text(self):
        out, side, _ = self.read(routed_page(fill=False))
        self.assertNotIn('grid', [b.get('_box_kind') for b in out])
        self.assertEqual(len(side), 1)

    def test_unreadable_side_box_is_flagged(self):
        p = routed_page()
        p['elements'].insert(1, dict(id='x1', kind='text', text='Behavioural therapy', angle=0, line=232,
                                     box_px=[250, 232, 345, 241], run_size_px=BODY, size_px=BODY,
                                     font='AB+Serif-Roman', char_ids=[], _faces={'AB+Serif-Roman': 19}))
        p['blocks'][-1]['members'].append('x1')
        out, side, unc = self.read(p)
        grid = next(b for b in out if b.get('_box_kind') == 'grid')
        self.assertIn('may wrap a cell or open a row', grid['_grid']['reason'])
        self.assertEqual(len(grid['_grid']['printed']), 11); self.assertEqual(side, [])
        self.assertTrue(any('could not be read row by row' in u for u in unc))
    def test_labelled_box_holding_the_list_is_not_printed_as_items(self):
        # a "Box n" frame (labelled_box_regions) printed its rows as items, each row's two cells joined
        p = routed_page()
        gr = [e for e in p['elements'] if e['id'].startswith('r')]
        for e in gr: e['box_px'] = [e['box_px'][0], e['box_px'][1]+12, e['box_px'][2], e['box_px'][3]+12]
        label = dict(id='lab', kind='text', text='Box 2. Choosing a treatment', angle=0, line=97, box_px=[100, 97, 260, 106],
                     run_size_px=BODY, size_px=BODY, font='AB+Serif-Bold', char_ids=[], _faces={'AB+Serif-Bold': 27})
        p['elements'].insert(1, label); p['blocks'][-1]['members'].insert(0, 'lab')
        next(e for e in p['elements'] if e['kind'] == 'fill')['box_px'] = [90, 90, 500, 275]
        self.assertEqual(len(copy.labelled_box_regions(p, {e['id']: e for e in p['elements'] if e['kind'] == 'text'}, BODY)), 1)
        out, floats, side = copy.read_page(p, BODY, [])
        self.assertIn('grid', [b.get('_box_kind') for b in out])
        self.assertFalse(any(f[1] == 'box' for f in floats)); self.assertEqual(side, [])

    def test_labelled_box_of_items_stays_a_box(self):
        p = routed_page(fill=False)
        es = [dict(id='lab', kind='text', text='Box 3. Points to remember', angle=0, line=400, box_px=[100, 400, 250, 409]),
              dict(id='i1', kind='text', text='Keep the record sheet dry', angle=0, line=416, box_px=[100, 416, 260, 425]),
              dict(id='i2', kind='text', text='Hand it in within a week', angle=0, line=428, box_px=[100, 428, 250, 437]),
              dict(id='i3', kind='text', text='Note any missed step', angle=0, line=440, box_px=[100, 440, 230, 449])]
        for e in es: e.update(run_size_px=BODY, size_px=BODY, font='AB+Serif-Roman', char_ids=[], _faces={'AB+Serif-Roman': 9})
        p['elements'] += es + [dict(id='f2', kind='fill', box_px=[90, 392, 500, 460])]
        p['blocks'].append(dict(id='bx3', members=[e['id'] for e in es], box_px=[100, 400, 260, 449]))
        _, floats, _ = copy.read_page(p, BODY, [])
        self.assertEqual([f[1] for f in floats], ['box'])


if __name__ == '__main__':
    unittest.main()
