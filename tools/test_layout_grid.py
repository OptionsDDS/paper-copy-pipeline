"""Layout grid (float-mapper table port): synthetic counterexamples, no corpus strings or IDs.

A gated table is offered one independent grid from its printed layout. It is
written only when every printed word is owned by exactly one cell, caption or
note; every undecidable position keeps the gate.
"""
import importlib.util, unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


def line(y, cells, run=None):
    """cells: [(x, 'text of one printed run'), ...]; words 6 px per character, 4 px apart."""
    items = []
    for x, text in cells:
        for word in text.split():
            items.append(dict(box=[x, y, x+6*len(word), y+10], text=word, id=run or f'run:{y}:{x}'))
            x += 6*len(word)+4
    return dict(text=' '.join(w['text'] for w in items), items=items)


def rule(y, x0=0, x1=300):
    return dict(kind='rule', box=[x0, y, x1, y+.5])


def source(lines, graphics=()):
    return dict(lines=lines, graphics=list(graphics), angle=0)


def grid(rows):
    return [[' '.join(parts) for parts in row] for row in rows]


NUMERIC = [line(0, [(0, 'Group'), (100, 'Mean'), (200, 'Count')]),
           line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]),
           line(40, [(0, 'Beta'), (100, '2.5'), (200, '14')]),
           line(60, [(0, 'Gamma'), (100, '3.5'), (200, '16')])]


class LayoutGrid(unittest.TestCase):
    def test_clean_table_is_a_grid_and_every_word_is_owned_once(self):
        rows, notes, ev = c.layout_grid(source(NUMERIC, [rule(15)]), [])
        self.assertEqual(grid(rows), [['Group', 'Mean', 'Count'], ['Alpha', '1.5', '12'],
                                      ['Beta', '2.5', '14'], ['Gamma', '3.5', '16']])
        self.assertTrue(ev['accepted']); self.assertEqual(ev['header_basis'], 'full-width rule')
        self.assertTrue(rows[0].header)

    def test_header_from_first_value_baseline_without_rule(self):
        rows, notes, ev = c.layout_grid(source(NUMERIC), [])
        self.assertEqual(ev['header_basis'], 'first numeric baseline'); self.assertEqual(len(rows), 4)

    def test_header_words_with_digits_are_not_values(self):
        lines = [line(0, [(0, 'Item'), (100, '2.0 Gy/sham'), (200, '0.2 Gy/sham')])] + NUMERIC[1:]
        rows, notes, ev = c.layout_grid(source(lines), [])
        self.assertEqual(grid(rows)[0], ['Item', '2.0 Gy/sham', '0.2 Gy/sham'])

    def test_closing_rule_and_marker_lines_are_notes(self):
        lines = NUMERIC + [line(85, [(0, 'Values are means of three runs.')]), line(98, [(0, '*Significant.')])]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15), rule(78)]), [])
        self.assertEqual(notes, ['Values are means of three runs.', '*Significant.']); self.assertEqual(len(rows), 4)

    def test_spanning_header_repeats_over_its_sub_headers(self):
        lines = [line(0, [(100, 'Measured value set')]), line(15, [(0, 'Group'), (100, 'Mean'), (200, 'Count')])] + \
                [dict(l, items=[dict(w, box=[w['box'][0], w['box'][1]+15, w['box'][2], w['box'][3]+15]) for w in l['items']])
                 for l in NUMERIC[1:]]
        rows, notes, ev = c.layout_grid(source(lines, [rule(30)]), [])
        self.assertEqual(grid(rows)[:2], [['', 'Measured value set', 'Measured value set'], ['Group', 'Mean', 'Count']])

    def test_spanning_header_without_sub_headers_keeps_the_gate(self):
        lines = [line(0, [(0, 'Group'), (100, 'Measured value set')])] + NUMERIC[1:]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertIsNone(rows)

    def test_label_centred_across_blank_first_cells_keeps_the_gate(self):
        lines = NUMERIC[:1] + [line(20, [(100, '1.5'), (200, '12')]), line(40, [(0, 'Alpha'), (100, '2.5'), (200, '14')]),
                               line(60, [(100, '3.5'), (200, '16')])]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertIsNone(rows)

    def test_unwitnessed_continuation_keeps_the_gate(self):
        lines = NUMERIC[:2] + [line(40, [(100, 'extra')])] + NUMERIC[2:]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertIsNone(rows); self.assertIn('witness', ev['reason'])

    def test_text_confirmed_continuation_joins_its_cell(self):
        lines = [line(0, [(0, 'Group'), (100, 'Note'), (200, 'Count')]),
                 line(20, [(0, 'Alpha'), (100, 'mild and'), (200, '12')]), line(40, [(100, 'brief')]),
                 line(60, [(0, 'Beta'), (100, 'none'), (200, '14')]), line(80, [(0, 'Gamma'), (100, 'none'), (200, '16')])]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertEqual(grid(rows)[1], ['Alpha', 'mild and brief', '12'])

    def test_row_spacing_witnesses_wrapped_cells(self):
        lines = [line(0, [(0, 'Group'), (100, 'Note'), (200, 'Count')]),
                 line(20, [(0, 'Alpha'), (100, 'first'), (200, '12')]), line(32, [(100, 'Second')]),
                 line(55, [(0, 'Beta'), (100, 'third'), (200, '14')]), line(67, [(100, 'Fourth')]),
                 line(90, [(0, 'Gamma'), (100, 'fifth'), (200, '16')])]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertEqual(ev['row_style'], 'spaced')
        self.assertEqual(grid(rows)[1:3], [['Alpha', 'first Second', '12'], ['Beta', 'third Fourth', '14']])

    def test_group_label_needs_a_break_witness(self):
        lines = NUMERIC[:1] + [line(20, [(0, 'Cohort')])] + [dict(l, items=[dict(w, box=[w['box'][0]+10, w['box'][1]+20, w['box'][2]+10, w['box'][3]+20])
                                                                          if w['box'][0] < 50 else dict(w, box=[w['box'][0], w['box'][1]+20, w['box'][2], w['box'][3]+20])
                                                                          for w in l['items']]) for l in NUMERIC[1:]]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertTrue(rows[1].group); self.assertIn('outdent', ev.get('reason', '') or 'outdent')
        flat = NUMERIC[:1] + [line(20, [(0, 'Cohort')])] + [dict(l, items=[dict(w, box=[w['box'][0], w['box'][1]+20, w['box'][2], w['box'][3]+20]) for w in l['items']]) for l in NUMERIC[1:]]
        self.assertIsNone(c.layout_grid(source(flat, [rule(15)]), [])[0])

    def test_top_aligned_labels_span_rows_with_repeated_sub_labels(self):
        lines = [line(0, [(0, 'Site'), (60, 'Arm'), (120, 'Mean'), (200, 'SD')])]
        y = 20
        for site in ('North', 'South'):
            for k, arm in enumerate(('Test', 'Control')):
                lines.append(line(y, ([(0, site)] if k == 0 else []) + [(60, arm), (120, f'{y/10:.1f}'), (200, '0.4')])); y += 20
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertEqual(ev['row_span_witness'], ['repeated labels'])
        self.assertEqual(rows[1].row_spans, {0: dict(start=1, end=2)}); self.assertEqual(grid(rows)[2][0], '')

    def test_top_aligned_labels_without_group_witness_keep_the_gate(self):
        lines = [line(0, [(0, 'Site'), (60, 'Arm'), (120, 'Mean'), (200, 'SD')]),
                 line(20, [(0, 'North'), (60, 'Test'), (120, '1.0'), (200, '0.4')]), line(40, [(60, 'Control'), (120, '2.0'), (200, '0.4')]),
                 line(60, [(0, 'South'), (60, 'Other'), (120, '3.0'), (200, '0.4')]), line(80, [(60, 'Placebo'), (120, '4.0'), (200, '0.4')])]
        self.assertIsNone(c.layout_grid(source(lines, [rule(15)]), [])[0])

    def test_caption_repeated_as_first_line_is_owned_by_the_caption(self):
        lines = [line(-20, [(0, 'Table 4 Measured counts by group')])] + NUMERIC
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [], caption='Table 4. Measured counts by group')
        self.assertEqual(ev['caption_lines'], ['Table 4 Measured counts by group']); self.assertEqual(len(rows), 4)

    def test_bullet_stays_with_its_item(self):
        lines = [line(0, [(0, 'Group'), (100, 'Finding'), (200, 'Count')])] + \
                [line(20+20*i, [(0, g), (100, '•'), (112, 'item text'), (200, str(i))]) for i, g in enumerate(['Alpha', 'Beta', 'Gamma'])]
        rows, notes, ev = c.layout_grid(source(lines, [rule(15)]), [])
        self.assertEqual(ev['columns'], 3); self.assertEqual(grid(rows)[1][1], '• item text')

    def test_two_runs_in_one_column_keep_the_gate(self):
        lines = NUMERIC[:1] + [line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]), line(40, [(0, 'Beta'), (100, '2.5'), (200, '14')]),
                               line(60, [(0, 'Gamma'), (100, '3.5'), (150, 'x'), (200, '16')])]
        self.assertIsNone(c.layout_grid(source(lines, [rule(15)]), [])[0])

    def test_centred_upper_header_spans_its_sub_headers(self):
        lines = [line(0, [(0, 'Group'), (130, 'Arm')]),
                 line(15, [(100, 'Mean'), (160, 'SD')])] + \
                [line(35+20*i, [(0, g), (100, '1.0'), (160, '0.5')]) for i, g in enumerate(['Alpha', 'Beta', 'Gamma'])]
        rows, notes, ev = c.layout_grid(source(lines, [rule(30)]), [])
        self.assertEqual(grid(rows)[0], ['Group', 'Arm', 'Arm']); self.assertEqual(grid(rows)[1], ['', 'Mean', 'SD'])

    def test_shaded_band_over_two_rows_keeps_the_gate(self):
        lines = NUMERIC[:1] + [line(20, [(0, 'Alpha'), (100, '1.5'), (200, '12')]), line(32, [(0, 'later'), (100, '2.5'), (200, '14')]),
                               line(55, [(0, 'Gamma'), (100, '3.5'), (200, '16')])]
        band = dict(kind='fill', box=[0, 18, 300, 44])
        self.assertIsNone(c.layout_grid(source(lines, [rule(15), band]), [])[0])
        self.assertIsNotNone(c.layout_grid(source(lines, [rule(15)]), [])[0])


if __name__ == '__main__':
    unittest.main()
