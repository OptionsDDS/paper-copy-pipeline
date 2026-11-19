"""Lane r5-wrap: text on both sides of a picture (O32), which way its lines run (O33), doubt on a wrap (O34).
Synthetic geometry and words only; no text of any paper."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boxer', ROOT/'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)

BODY = 20


def run(rid, x0, x1, row, text, size=BODY):
    y = 100 + row * 25
    return dict(id=rid, kind='text', text=text, angle=0, line=row, box_px=[x0, y, x1, y + 18], run_size_px=size, size_px=size)


def wrap_rows(left_texts, right_texts, x0=100, px0=400, px1=600, x1=900, start=0):
    """runs for rows beside a picture at x px0-px1: a left piece ending one letter height before it, a right piece
    starting one letter height after it"""
    rs = []
    for k, (a, b) in enumerate(zip(left_texts, right_texts)):
        rs.append(run(f'L{k}', x0, px0 - BODY, start + k, a))
        if b is not None:
            rs.append(run(f'R{k}', px1 + BODY, x1, start + k, b))
    return rs


class Continues(unittest.TestCase):
    def test_hyphen_and_case(self):
        v = {'standard': 3}
        self.assertEqual(boxer.wrap_continues('the stan-', 'dard value', v), 2)
        self.assertEqual(boxer.wrap_continues('the stan-', 'other value', v), 1)
        self.assertEqual(boxer.wrap_continues('the stan-', 'Other value', v), -1)
        self.assertEqual(boxer.wrap_continues('an open line', 'Capital start', v), -1)
        self.assertEqual(boxer.wrap_continues('an open line', 'small start', v), 0)
        self.assertEqual(boxer.wrap_continues('a closed line.', 'Capital start', v), 1)
        self.assertEqual(boxer.wrap_continues('a closed line.', 'small start', v), -1)
        self.assertEqual(boxer.wrap_continues('a closed line [12].', 'Capital start', v), 1)


class Direction(unittest.TestCase):
    def rows(self, left, right):
        tops = [100 + 25 * k for k in range(len(left))]
        return [(a, b, t) for a, b, t in zip(left, right, tops)], [(a, t) for a, t in zip(left, tops)]

    def test_across(self):
        left = ['one line ends here.', 'the second stan-', 'Third line is open', 'four parts here.']
        right = ['Then a capital', 'dard words go on', 'and more words.', 'Fine at last.']
        rows, lefts = self.rows(left, right)
        self.assertEqual(boxer.wrap_direction(rows, lefts, {'standard': 2})[0], 'across')

    def test_down(self):
        left = ['the left side stan-', 'dard goes on here.', 'Second sentence ends.', 'Third one']
        right = ['Right side starts', 'and goes on down', 'with its own words', 'to the end.']
        rows, lefts = self.rows(left, right)
        self.assertEqual(boxer.wrap_direction(rows, lefts, {'standard': 2})[0], 'down')

    def test_no_evidence_is_unclear(self):
        left = ['words go on', 'words go on', 'words go on']
        right = ['more words', 'more words', 'more words']
        rows, lefts = self.rows(left, right)
        self.assertEqual(boxer.wrap_direction(rows, lefts, {})[0], 'unclear')

    def test_one_deciding_row_is_unclear(self):
        left = ['a closed line.', 'words go on', 'words go on']
        right = ['Capital start', 'more words', 'more words']
        rows, lefts = self.rows(left, right)
        self.assertEqual(boxer.wrap_direction(rows, lefts, {})[0], 'unclear')


class Places(unittest.TestCase):
    def test_both_sides_make_a_wrap(self):
        rs = wrap_rows(['a', 'b', 'c'], ['d', 'e', 'f'])
        ws = boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05)
        self.assertEqual(len(ws), 1)
        self.assertEqual(len(ws[0]['rows']), 3)

    def test_one_side_is_no_wrap(self):
        rs = wrap_rows(['a', 'b', 'c'], [None, None, None])
        self.assertEqual(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05), [])

    def test_one_row_is_no_wrap(self):
        rs = wrap_rows(['a', 'b', 'c'], ['d', None, None])
        self.assertEqual(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05), [])

    def test_other_size_is_no_wrap(self):
        rs = [dict(r, run_size_px=12, size_px=12) for r in wrap_rows(['a', 'b', 'c'], ['d', 'e', 'f'])]
        self.assertEqual(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05), [])

    def test_far_column_is_not_a_side(self):
        # text of another column far right of the picture is not beside it
        rs = wrap_rows(['a', 'b', 'c'], [None, None, None]) + [run(f'C{k}', 700, 900, k, 'x') for k in range(3)]
        self.assertEqual(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05), [])

    def test_right_piece_stops_at_another_block(self):
        rs = wrap_rows(['a', 'b'], ['d', 'e'], x1=650) + [run(f'C{k}', 660, 900, k, 'col') for k in range(2)]
        block_of = {r['id']: ('B2' if r['id'][0] == 'C' else 'B1') for r in rs}
        ws = boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05, block_of)
        self.assertEqual([[e['id'] for e in r] for _, r in ws[0]['rows']], [['R0'], ['R1']])

    def test_text_across_a_column_gutter_is_not_a_side(self):
        rs = wrap_rows(['a', 'b'], ['d', 'e'])
        self.assertEqual(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05, gutters=[(605, 615)]), [])
        self.assertEqual(len(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05, gutters=[(495, 505)])), 1)

    def test_object_in_a_gutter_is_a_column_rule(self):
        rs = wrap_rows(['a', 'b'], ['d', 'e'], px0=480, px1=520)
        self.assertEqual(boxer.wrap_places(rs, [[480, 0, 520, 900]], BODY, 0.05, gutters=[(470, 530)]), [])

    def test_split_row_in_the_runaround_margin_counts_and_a_full_line_there_does_not_spoil_the_wrap(self):
        rs = wrap_rows(['a', 'b', 'c'], ['d', 'e', 'f'])
        rs += [run('M', 100, 900, 3, 'full line below')]            # row 3 at y 175-193, just under the picture
        ws = boxer.wrap_places(rs, [[400, 90, 600, 165]], BODY, 0.05)
        self.assertEqual(len(ws), 1)
        self.assertEqual(len(ws[0]['rows']), 3)

    def test_line_through_the_picture_is_no_wrap(self):
        rs = wrap_rows(['a', 'b', 'c'], ['d', 'e', 'f']) + [run('T', 100, 900, 1, 'through')]
        self.assertEqual(boxer.wrap_places(rs, [[400, 90, 600, 190]], BODY, 0.05), [])


class Pictures(unittest.TestCase):
    def test_touching_pieces_join_and_inner_boxes_drop(self):
        els = [dict(kind='fill', box_px=[400, 100, 500, 200]), dict(kind='rule', box_px=[500, 100, 600, 101]),
               dict(kind='text', box_px=[0, 0, 900, 10])]
        floats = [dict(box_px=[390, 90, 610, 260])]
        self.assertEqual(boxer.wrap_pictures(els, [], floats, 1000, BODY), [[390, 90, 610, 260]])

    def test_small_and_frame_wide_objects_are_not_pictures(self):
        els = [dict(kind='fill', box_px=[400, 100, 420, 110]), dict(kind='fill', box_px=[0, 100, 950, 400])]
        self.assertEqual(boxer.wrap_pictures(els, [], [], 1000, BODY), [])


if __name__ == '__main__':
    unittest.main()
