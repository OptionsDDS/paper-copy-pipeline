"""One output row per printed row band: synthetic counterexamples, no corpus strings or IDs.

Two baselines that each carry their own first-column entry and value are two
printed rows (row_bands); a header row cannot hold a labelled baseline of
measurements; bottom rows proven to be notes leave the grid; sub-headers set
side by side above one partial rule keep their own columns.
"""
import importlib.util, unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


def line(y, cells):
    """cells: [(x, 'text of one printed run'), ...]; words 6 px per character, 4 px apart."""
    items = []
    for x, text in cells:
        for word in text.split():
            items.append(dict(box=[x, y, x+6*len(word), y+10], text=word, id=f'run:{y}:{x}'))
            x += 6*len(word)+4
    return dict(text=' '.join(w['text'] for w in items), items=items)


def source(lines, graphics=()):
    return dict(lines=lines, graphics=list(graphics), angle=0)


def bands(rows, lines, notes=()):
    return c.table_structure_checks(rows, source(lines), 'Table 1. Measurements', list(notes))['row_bands']


HEAD = line(0, [(0, 'Group'), (100, 'Mean'), (200, 'Count')])


class RowBands(unittest.TestCase):
    def test_two_labelled_value_baselines_in_one_row_fire(self):
        lines = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5 (0.2)'), (200, '12')]),
                 line(40, [(0, 'Beta'), (100, '2.5 (0.3)'), (200, '14')])]
        rows = [[['Group'], ['Mean'], ['Count']], [['Alpha', 'Beta'], ['1.5 (0.2)', '2.5 (0.3)'], ['12', '14']]]
        result = bands(rows, lines)
        self.assertTrue(result['fired'])
        self.assertEqual(result['evidence'][0]['printed_lines'], [2, 3])

    def test_group_label_with_two_merged_children_fires(self):
        lines = [HEAD, line(20, [(0, 'Cycle')]), line(40, [(10, '2001–2002'), (100, '10 (50%)'), (200, '3')]),
                 line(60, [(10, '2003–2004'), (100, '10 (50%)'), (200, '4')])]
        rows = [[['Group'], ['Mean'], ['Count']],
                [['Cycle', '2001–2002', '2003–2004'], ['10 (50%)', '10 (50%)'], ['3', '4']]]
        self.assertTrue(bands(rows, lines)['fired'])

    def test_separate_rows_pass(self):
        lines = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]), line(40, [(0, 'Beta'), (100, '2.5'), (200, '14')])]
        rows = [[['Group'], ['Mean'], ['Count']], [['Alpha'], ['1.5'], ['12']], [['Beta'], ['2.5'], ['14']]]
        self.assertFalse(bands(rows, lines)['fired'])

    def test_wrapped_label_is_one_multiline_cell(self):
        lines = [HEAD, line(20, [(0, 'Weight of'), (100, '1.5'), (200, '12')]),
                 line(40, [(0, 'samples'), (100, '2.5'), (200, '14')])]
        rows = [[['Group'], ['Mean'], ['Count']], [['Weight of', 'samples'], ['1.5', '2.5'], ['12', '14']]]
        self.assertFalse(bands(rows, lines)['fired'])

    def test_bracketed_qualifier_under_a_value_is_one_cell(self):
        lines = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]),
                 line(40, [(0, 'Beta'), (100, '(0.2)'), (200, '(3)')])]
        rows = [[['Group'], ['Mean'], ['Count']], [['Alpha', 'Beta'], ['1.5', '(0.2)'], ['12', '(3)']]]
        self.assertFalse(bands(rows, lines)['fired'])

    def test_header_row_holding_a_measurement_baseline_fires(self):
        lines = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5 (0.2)'), (200, '12.0')]),
                 line(40, [(0, 'Beta'), (100, '2.5'), (200, '14')])]
        rows = [[['Group', 'Alpha'], ['Mean', '1.5 (0.2)'], ['Count', '12.0']], [['Beta'], ['2.5'], ['14']]]
        result = bands(rows, lines)
        self.assertTrue(result['fired'])
        self.assertIn('header row', result['evidence'][0]['reason'])

    def test_numeric_header_labels_are_not_data(self):
        lines = [line(0, [(0, 'Region'), (100, 'Year'), (200, 'Year')]), line(20, [(100, '2019'), (200, '2020')]),
                 line(40, [(0, 'North'), (100, '1.5'), (200, '2.5')])]
        rows = [[['Region'], ['Year', '2019'], ['Year', '2020']], [['North'], ['1.5'], ['2.5']]]
        self.assertFalse(bands(rows, lines)['fired'])

    def test_bracketed_header_annotations_are_not_data(self):
        lines = [line(0, [(100, 'A'), (200, 'B')]), line(20, [(0, 'Study'), (100, '(0–2)'), (200, '(0–1)')]),
                 line(40, [(0, 'North'), (100, '2'), (200, '1')])]
        rows = [[['Study'], ['A', '(0–2)'], ['B', '(0–1)']], [['North'], ['2'], ['1']]]
        self.assertFalse(bands(rows, lines)['fired'])

    def test_drawn_study_band_is_a_witnessed_cell_group(self):
        lines = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]), line(40, [(0, 'Beta'), (100, '2.5'), (200, '14')])]
        row = c.TableRow([['Alpha', 'Beta'], ['1.5', '2.5'], ['12', '14']], study_band=True)
        self.assertFalse(bands([[['Group'], ['Mean'], ['Count']], row], lines)['fired'])

    def test_unit_after_a_value_is_not_a_note_marker(self):
        lines = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5 mm'), (200, '12')]), line(40, [(0, 'Beta'), (100, '2.5 mm'), (200, '14')])]
        rows = [[['Group'], ['Mean'], ['Count']], [['Alpha', 'Beta'], ['1.5 mm', '2.5 mm'], ['12', '14']]]
        self.assertEqual([e['column'] for e in bands(rows, lines)['evidence']], [3])

    def test_row_bands_is_answered_by_the_layout_grid(self):
        self.assertIn('row_bands', c.LAYOUT_GRID_CHECKS)


class NoteRows(unittest.TestCase):
    LINES = [HEAD, line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]), line(40, [(0, 'Beta'), (100, '2.5'), (200, '14')])]
    ROWS = [[['Group'], ['Mean'], ['Count']], [['Alpha'], ['1.5'], ['12']], [['Beta'], ['2.5'], ['14']]]

    def test_marker_note_row_leaves_the_grid(self):
        note = line(60, [(0, '*P < 0.05.')])
        rows, notes, ev = c.grid_note_rows(self.ROWS+[[['*P < 0.05.'], [], []]], source(self.LINES+[note]), ['Later note.'])
        self.assertEqual(rows, self.ROWS)
        self.assertEqual(notes, ['*P < 0.05.', 'Later note.'])
        self.assertEqual(ev['witness'], 'note marker')

    def test_note_below_the_closing_rule_leaves_the_grid(self):
        note = line(64, [(0, 'Values from the survey.')])
        rule = dict(kind='rule', box=[0, 57, 240, 57.5])
        rows, notes, ev = c.grid_note_rows(self.ROWS+[[['Values from the survey.'], [], []]],
                                           source(self.LINES+[note], [rule]), [])
        self.assertEqual(rows, self.ROWS)
        self.assertEqual(ev['witness'], 'closing rule')

    def test_long_note_line_crossing_the_gutter_leaves_the_grid(self):
        note = line(60, [(0, 'Values are reported for every group')])
        rows, notes, ev = c.grid_note_rows(self.ROWS+[[[note['text']], [], []]], source(self.LINES+[note]), [])
        self.assertEqual(rows, self.ROWS)
        self.assertEqual(ev['witness'], 'crosses the first gutter')

    def test_ruled_template_rows_and_divided_rows_stay_rows(self):
        rows = self.ROWS+[[['Gamma'], [], []], [['Delta'], [], []]]
        lines = self.LINES+[line(60, [(0, 'Gamma')]), line(80, [(0, 'Delta')])]
        rules = [dict(kind='rule', box=[0, y, 240, y+.5]) for y in (57, 77, 95)]
        self.assertEqual(c.grid_note_rows(rows, source(lines, rules), [])[0], rows)
        divider = dict(kind='rule', box=[90, 0, 90.5, 100])
        rows = self.ROWS+[[['*Gamma'], [], []]]
        self.assertEqual(c.grid_note_rows(rows, source(self.LINES+[line(60, [(0, '*Gamma')])], [divider]), [])[0], rows)

    def test_empty_bottom_row_is_left_alone(self):
        rows = self.ROWS+[c.TableRow([])]
        self.assertIs(c.grid_note_rows(rows, source(self.LINES), [])[0], rows)

    def test_unwitnessed_label_row_stays_a_row(self):
        label = line(60, [(0, 'Gamma')])
        rows = self.ROWS+[[['Gamma'], [], []]]
        self.assertEqual(c.grid_note_rows(rows, source(self.LINES+[label]), [])[0], rows)


class SideBySideSubHeaders(unittest.TestCase):
    def test_sub_headers_over_one_partial_rule_keep_their_columns(self):
        lines = [line(0, [(100, 'Upper')]), line(20, [(100, 'Left'), (200, 'Right')]),
                 line(40, [(0, 'Alpha'), (100, '1.5'), (200, '12')]), line(60, [(0, 'Beta'), (100, '2.5'), (200, '14')]),
                 line(80, [(0, 'Gamma'), (100, '3.5'), (200, '16')])]
        # The full-width rule under the sub-headers is drawn in two segments;
        # the right one lies under both sub-headers.
        graphics = [dict(kind='rule', box=[100, 13, 240, 13.5]), dict(kind='rule', box=[0, 33, 95, 33.5]),
                    dict(kind='rule', box=[95, 33, 240, 33.5])]
        rows, notes, ev = c.layout_grid(source(lines, graphics), [])
        self.assertTrue(ev.get('accepted'), ev)
        cells = [[' '.join(p) for p in r] for r in rows if r is not None]
        self.assertEqual(cells[0], ['', 'Upper', 'Upper'])
        self.assertEqual(cells[1], ['', 'Left', 'Right'])
        self.assertEqual(cells[2], ['Alpha', '1.5', '12'])


if __name__ == '__main__':
    unittest.main()
