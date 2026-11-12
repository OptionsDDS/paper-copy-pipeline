"""Lane r2-fills: headerless two-column text inside a fill is read column by column; a two-column table or a
list of short cells inside a fill keeps its row order. Synthetic, keyless, invented text.

Run: /usr/bin/python3 -I tools/test_fillcolumns.py
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fillcolumns_copy', ROOT / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)

BODY = 10
LEFT = ['Walkers count the birds of the hedge', 'every winter along one fixed route.', 'They note each bird heard or seen',
        'and write the time beside it. The', 'leader adds the totals at the gate', 'before the group goes home for the']
RIGHT = ['evening. Wet days are left out of', 'the record, because fewer birds call', 'and the totals fall for that reason',
         'alone. The route is mapped once and', 'the map is kept with the sheets for', 'the next winter. Each walk ends here.']


def run(i, x, y, text, bold=False, width=None):
    w = width if width is not None else 5 * len(text)
    return dict(id=f'r{i}', kind='text', text=text, angle=0, line=y, box_px=[x, y, x + w, y + 9],
                run_size_px=BODY, size_px=BODY, font='AB+Serif-Bold' if bold else 'AB+Serif-Roman')


def runs_of(rows, top=100, pitch=12):
    out, i = [], 0
    for k, row in enumerate(rows):
        for cell in row:
            if cell is None: continue
            i += 1; out.append(run(i, cell[0], top + pitch * k, cell[1], *cell[2:]))
    return out


def two_columns(heading=None, right_x=300, left=LEFT, right=RIGHT):
    rows = [[(100, heading, True, 420)]] if heading else []
    n = max(len(left), len(right))
    for k in range(n):
        rows.append([(100, left[k], False, 180) if k < len(left) else None,
                     (right_x, right[k], False, 180) if k < len(right) else None])
    return runs_of(rows)


FILL = [[90, 90, 500, 300]]


def order(runs, fills=FILL):
    cols = copy.fill_text_columns(runs, BODY, fills)
    if cols is None: return None
    return [' '.join(e['text'] for e in row) for row in copy.fill_column_rows(copy.text_rows(runs), cols)]


class FillColumns(unittest.TestCase):
    def test_two_columns_read_in_turn(self):
        self.assertEqual(order(two_columns()), LEFT + RIGHT)

    def test_heading_spanning_the_gutter_stays_first(self):
        self.assertEqual(order(two_columns('How the winter count is made by every walking group')),
                         ['How the winter count is made by every walking group'] + LEFT + RIGHT)

    def test_columns_of_unequal_length(self):
        self.assertEqual(order(two_columns(left=LEFT, right=RIGHT[:4])), LEFT + RIGHT[:4])

    def test_paragraph_indent_keeps_the_left_edge(self):
        left = list(LEFT)
        runs = two_columns(left=left)
        runs[6]['box_px'][0] += 10; runs[6]['box_px'][2] += 10   # an indented first line in the left column
        self.assertEqual(order(runs), LEFT + RIGHT)

    def test_outside_any_fill_is_left_alone(self):
        self.assertIsNone(order(two_columns(), fills=[[400, 400, 600, 600]]))
        self.assertIsNone(order(two_columns(), fills=[]))

    def test_short_cells_are_a_list_not_columns(self):
        rows = [[(100, a, False), (300, b, False)] for a, b in
                (('Hedge', 'A row of shrubs'), ('Track', 'Unpaved farm road'), ('Gate', 'Start of the walk'),
                 ('Stream', 'End of the walk'), ('Sheet', 'Record of one walk'), ('Leader', 'Checks every sheet'))]
        self.assertIsNone(order(runs_of(rows)))

    def test_table_rows_with_white_bands_keep_row_order(self):
        rows = []
        for k in range(4):
            rows += [[(100, LEFT[k], False, 180), (300, RIGHT[k], False, 180)],
                     [(100, LEFT[k+1], False, 180), (300, RIGHT[k+1], False, 180)],
                     [None, (300, RIGHT[k+2], False, 180)], []]
        self.assertIsNone(order(runs_of(rows)))

    def test_bold_header_grid_is_not_columns_here(self):
        # a boxed two-column list with a bold header is boxed_two_column_grid's; its short cells fail the measure
        rows = [[(100, 'Finding', True), (300, 'Aim', True)]] + [[(100, a, False), (300, b, False)] for a, b in
                (('Pain at night', 'Relieve the pain'), ('Loud grinding', 'Remove the noise'), ('Poor sleep', 'Improve sleep'))]
        self.assertIsNone(order(runs_of(rows)))

    def test_wide_strip_through_every_row_is_still_a_gutter(self):
        # coordinator ruling (re-ladder 3): widths and strip widths are no evidence against columns
        self.assertEqual(order(two_columns(right_x=400), fills=[[90, 90, 700, 300]]), LEFT + RIGHT)

    def test_heading_over_the_left_column_only(self):
        # a short bold heading above the left column alone: its row is the heading, the columns start level below it
        runs = runs_of([[(100, 'Tide log', True, 40)]]) + [dict(e, id='c' + e['id'], box_px=[e['box_px'][0], e['box_px'][1] + 12,
                       e['box_px'][2], e['box_px'][3] + 12]) for e in two_columns()]
        self.assertEqual(order(runs), ['Tide log'] + LEFT + RIGHT)

    def test_justified_lines_split_into_runs(self):
        # justified narrow columns: wide word spaces split a printed line into two runs at varying places
        runs, i = [], 0
        for k in range(6):
            for x0, text in ((100, LEFT[k]), (300, RIGHT[k])):
                words = text.split(); cut = 2 + k % 3
                for part, x, w in ((' '.join(words[:cut]), x0, 70 + 8 * (k % 3)), (' '.join(words[cut:]), x0 + 90 + 8 * (k % 3), 90 - 8 * (k % 3))):
                    i += 1; runs.append(run(i, x, 100 + 12 * k, part, False, w))
        self.assertEqual(order(runs), LEFT + RIGHT)
        self.assertFalse(copy.prose_side_group(runs))   # why the side loop must ask fill_text_columns first

    def test_three_columns_read_in_turn(self):
        third = ['Gulls wait on the old crane until the', 'boats come back with the catch. Then', 'they circle the deck and call. Ropes',
                 'are coiled again before the light goes.']
        rows = [[(100, LEFT[k], False, 150), (270, RIGHT[k], False, 150), (440, third[k], False, 150) if k < len(third) else None]
                for k in range(6)]
        self.assertEqual(order(runs_of(rows), fills=[[90, 90, 620, 300]]), LEFT + RIGHT + third)

    def test_four_columns_with_heading_and_one_line_paragraph(self):
        cols = [LEFT, ['Wet days are left out of', 'the record, as fewer birds', 'call on such mornings.', 'The pilot rang.',
                       'Then the walkers met at', 'the gate before the count.'],
                RIGHT, ['The map is kept with', 'the sheets for the next', 'winter. Each walk ends', 'at the stream gate where',
                        'the leader adds totals', 'and the group goes home.']]
        rows = [[(100, 'Signals used at the harbour mouth through the year', True, 400)]]
        for k in range(6):
            rows.append([(100 + 125 * c + (8 if c == 1 and k in (3, 4) else 0), cols[c][k], False, 100 if c == 1 and k in (3, 4) else 110) for c in range(4)])
        self.assertEqual(order(runs_of(rows), fills=[[90, 90, 620, 300]]),
                         ['Signals used at the harbour mouth through the year'] + [t for c in cols for t in c])

    def test_three_column_table_of_short_cells_keeps_row_order(self):
        rows = [[(100, 'Site', True), (270, 'Count', True), (440, 'Note', True)]] + [
            [(100, a, False), (270, b, False), (440, c, False)] for a, b, c in
            (('North jetty', '14', 'Calm water'), ('Old dock', '9', 'Gulls on the crane'), ('Channel buoy', '22', 'Strong tide'),
             ('Ferry steps', '5', 'Fog at dawn'), ('Beacon', '31', 'Lamp lit'), ('Estuary', '17', 'Brine on deck'))]
        self.assertIsNone(order(runs_of(rows), fills=[[90, 90, 620, 300]]))

    def order_parts(self, runs, fills):
        cols = copy.fill_text_columns(runs, BODY, fills)
        return None if cols is None else [' '.join(e['text'] for e in r) for r in copy.fill_column_rows(copy.text_rows(runs), cols)]

    def test_two_row_last_column_is_a_column_not_a_heading(self):
        # four columns, the last one paragraph of two rows: the first printed row is the columns' first row
        last = ['Item 900 the yard bell rang at', 'dawn.']
        rows = [[(100 + 125 * c, (LEFT, RIGHT, LEFT, last)[c][k], False, 110 if c < 3 or k == 0 else 25)
                 for c in range(4) if c < 3 or k < 2] for k in range(6)]
        got = self.order_parts(runs_of(rows), [[90, 90, 620, 300]])
        self.assertEqual(got, LEFT + RIGHT + LEFT + last)

    def test_list_column_between_prose_columns(self):
        terms = ['granite slab', 'keystone', 'plumbline', 'mortar trowel', 'pulley rope', 'lintel stone']
        rows = [[(100, LEFT[k], False, 180), (300, terms[k], False, 60), (420, RIGHT[k], False, 180)] for k in range(6)]
        self.assertEqual(self.order_parts(runs_of(rows), [[90, 90, 620, 300]]), LEFT + terms + RIGHT)

    def test_columns_of_widths_two_to_one(self):
        wide = [a + ' ' + b for a, b in zip(LEFT, RIGHT)]
        rows = [[(100, wide[k], False, 360), (480, RIGHT[k], False, 180)] for k in range(6)]
        self.assertEqual(self.order_parts(runs_of(rows), [[90, 90, 680, 300]]), wide + RIGHT)

    def test_table_above_prose_columns_in_one_fill(self):
        table = [[(100, 'Reach', True, 40), (300, 'Depth', True, 40), (420, 'Flow', True, 40)]] + [
            [(100, f'R-0{i}', False, 25), (300, f'{i}.5', False, 15), (420, f'{140 + i}', False, 15)] for i in range(1, 6)]
        prose = [[], []] + [[(100, LEFT[k], False, 180), (300, RIGHT[k], False, 180)] for k in range(6)]
        got = self.order_parts(runs_of(table + prose), [[90, 90, 620, 400]])
        self.assertEqual(got[:6], ['Reach Depth Flow'] + [f'R-0{i} {i}.5 {140 + i}' for i in range(1, 6)])
        self.assertEqual(got[6:], LEFT + RIGHT)

    def test_true_heading_over_the_first_column_stays_first(self):
        runs = runs_of([[(100, 'Lock notes', True, 50)]]) + [dict(e, id='c' + e['id'], box_px=[e['box_px'][0], e['box_px'][1] + 22,
                       e['box_px'][2], e['box_px'][3] + 22]) for e in two_columns()]
        self.assertEqual(self.order_parts(runs, FILL), ['Lock notes'] + LEFT + RIGHT)

    def test_numbers_set_flush_right_are_no_text_column(self):
        terms = ['reed bed', 'otter holt', 'willow', 'sluice gate', 'silt trap', 'eel pass', 'punt pole']
        vals = ['3.5', '40.5', '77.5', '114.5', '151.5', '188.5', '225.5']
        rows = [[(100, t, False), (330 - 5 * len(v), v, False)] for t, v in zip(terms, vals)]
        self.assertIsNone(order(runs_of(rows)))

    def subheaded(self, heads, gap=2):
        top = [[(100, LEFT[k], False, 180), (300, RIGHT[k], False, 180)] for k in range(6)]
        mid = [[]] * gap + [[(100, a, True, 90), (300, b, True, 90)] for a, b in heads]
        low = [[(100, RIGHT[k], False, 180), (300, LEFT[k], False, 180)] for k in range(6)]
        return runs_of(top + mid + low)

    def test_column_subheadings_after_a_white_band_continue_the_columns(self):
        got = self.order_parts(self.subheaded([('Winter work', 'Summer work')]), [[90, 90, 620, 400]])
        self.assertEqual(got, LEFT + ['Winter work'] + RIGHT + RIGHT + ['Summer work'] + LEFT)

    def test_two_row_column_subheadings(self):
        got = self.order_parts(self.subheaded([('Work on the lock', 'Work on the weir'), ('in a dry season', 'after floods')]),
                               [[90, 90, 620, 420]])
        self.assertEqual(got, LEFT + ['Work on the lock', 'in a dry season'] + RIGHT + RIGHT + ['Work on the weir', 'after floods'] + LEFT)

    def test_subheading_rows_are_no_grid_header_inside_columns(self):
        runs = self.subheaded([('Winter work', 'Summer work')])
        grid = copy.boxed_two_column_grid(runs, BODY, [[90, 90, 620, 400]])
        self.assertIsNotNone(grid)   # the B2 witness alone takes the bold pair for a header
        self.assertIsNone(copy.fill_grid_check(grid, runs, BODY, [[90, 90, 620, 400]]))

    def test_headerless_numeric_table_above_prose_is_a_part_of_its_own(self):
        table = [[(100, f'Q-0{i} north face', False, 80), (420, f'{1200 + 85 * i}', False, 20), (520, f'{i}.5', False, 15)]
                 for i in range(1, 7)]
        prose = [[], []] + [[(100, LEFT[k], False, 180), (300, RIGHT[k], False, 180)] for k in range(6)]
        got = self.order_parts(runs_of(table + prose), [[90, 90, 620, 400]])
        self.assertEqual(got[:6], [f'Q-0{i} north face {1200 + 85 * i} {i}.5' for i in range(1, 7)])
        self.assertEqual(got[6:], LEFT + RIGHT)

    def test_bold_header_over_numbers_stays_a_table_below_prose(self):
        prose = [[(100, LEFT[k], False, 180), (300, RIGHT[k], False, 180)] for k in range(6)]
        table = [[], [], [(100, 'Reach', True, 30), (300, 'Flow', True, 25)]] + [[(100, f'R-0{i}', False, 25), (300, f'{140 + 17 * i}', False, 15)]
                                                                               for i in range(1, 7)]
        runs = runs_of(prose + table)
        got = self.order_parts(runs, [[90, 90, 620, 400]])
        self.assertEqual(got[:12], LEFT + RIGHT)
        self.assertEqual(got[12:], ['Reach Flow'] + [f'R-0{i} {140 + 17 * i}' for i in range(1, 7)])
        grid = copy.boxed_two_column_grid(runs, BODY, [[90, 90, 620, 400]])
        self.assertIs(copy.fill_grid_check(grid, runs, BODY, [[90, 90, 620, 400]]), grid)

    def keypoints(self, mark, cols=2):
        rows = [[(100, 'Key points', True, 60)], [(100, 'What earlier surveys found', True, 130)] +
                ([(330, 'What this survey adds', True, 110)] if cols == 2 else [])]
        for i in range(3):
            for j, (a, b) in enumerate(((LEFT[2*i], RIGHT[2*i]), (LEFT[2*i+1], RIGHT[2*i+1]))):
                row = [(100 if j == 0 else 112, (mark(i) + ' ' if j == 0 else '') + a, False, 190 if j == 0 else 120)]
                if cols == 2: row.append((330 if j == 0 else 342, (mark(i) + ' ' if j == 0 else '') + b, False, 190 if j == 0 else 120))
                rows.append(row)
        return runs_of(rows)

    def test_bulleted_columns_with_hanging_indents(self):
        got = self.order_parts(self.keypoints(lambda i: '\u2022'), [[90, 90, 620, 300]])
        self.assertEqual(got[0], 'Key points')
        self.assertEqual(got[1], 'What earlier surveys found')
        self.assertEqual(got[2:8], ['\u2022 ' + LEFT[0], LEFT[1], '\u2022 ' + LEFT[2], LEFT[3], '\u2022 ' + LEFT[4], LEFT[5]])
        self.assertEqual(got[8], 'What this survey adds')

    def test_numbered_columns_with_hanging_indents(self):
        got = self.order_parts(self.keypoints(lambda i: f'{i + 1}.'), [[90, 90, 620, 300]])
        self.assertEqual(got[2], '1. ' + LEFT[0]); self.assertEqual(got[8], 'What this survey adds')

    def test_one_column_key_points_box_is_left_alone(self):
        self.assertIsNone(copy.fill_text_columns(self.keypoints(lambda i: '\u2022', cols=1), BODY, [[90, 90, 620, 300]]))

    def test_second_edge_without_list_markers_is_no_column(self):
        runs = self.keypoints(lambda i: 'Then')   # rows at the column edge do not open list items
        self.assertIsNone(copy.fill_text_columns(runs, BODY, [[90, 90, 620, 300]]))

    def test_bulleted_checklist_table_keeps_row_order(self):
        tasks = ['Gates closed on the upper side', 'Paddles wound down', 'Weir boards in place', 'Towpath clear of boats',
                 'Lamp lit at the bridge', 'Keeper on the lock side']
        rows = [[(100, 'Check before the lock opens', True, 130)]] + [
            [(100, '\u2022', False, 5), (112, t, False, 5 * len(t)), (400, ('done', 'open')[k % 2], False, 20)] for k, t in enumerate(tasks)]
        self.assertIsNone(copy.fill_text_columns(runs_of(rows), BODY, [[90, 90, 620, 300]]))

    def test_subheading_rows_are_groups_of_their_own(self):
        runs = self.keypoints(lambda i: '\u2022'); byid = {e['id']: e for e in runs}
        cols = copy.fill_text_columns(runs, BODY, [[90, 90, 620, 300]])
        groups = copy.fill_column_groups([e['id'] for e in runs], byid, cols)
        self.assertEqual([' '.join(byid[m]['text'] for m in g)[:20] for g in groups[:3]],
                         ['Key points', 'What earlier surveys', '\u2022 Walkers count the '])

    def test_rows_are_split_never_remembered(self):
        runs = two_columns()
        rows = copy.fill_column_rows(copy.text_rows(runs), copy.fill_text_columns(runs, BODY, FILL))
        self.assertEqual(sorted(e['id'] for r in rows for e in r), sorted(e['id'] for e in runs))


if __name__ == '__main__':
    unittest.main()
