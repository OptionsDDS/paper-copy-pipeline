"""Lane iss-13: a printed row that a gutter splits into pieces (a boxed block's
centred heading) is read with the spanning block it touches, never with the
columns beside it; the second pass's page order agrees. Geometry only (150 dpi,
two columns about a 630 px gutter, as on the scanned page that showed it); no
paper's text."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_spanrows', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)
sys.path.insert(0, str(ROOT/'tools'))
import test_secondpass as sp  # noqa: E402
import r04_order  # noqa: E402
import common  # noqa: E402

SIZE = 13.3; PITCH = 17


def run(text, x0, y, x1, size=SIZE):
    return dict(text=text, box_px=[x0, y, x1, y+size+1.5], size_px=size)


def columns(top=200, rows=8):
    rs = []
    for side, x0, x1 in (('left', 104, 604), ('right', 655, 1155)):
        for k in range(rows):
            end = '.' if k == rows-1 else ''
            rs.append(run(f'{side} column line {k} reads on with several more words here{end}', x0, top+k*PITCH, x1))
    return rs


def box(top, rows=4):
    return [run(f'box text line {k} runs across both of the columns with many words in it'+('.' if k == rows-1 else ''),
                310, top+k*23, 945, 15.8) for k in range(rows)]


def heading(y):
    return [run('FIRSTNAME', 523, y, 618, 15.8), run('M. LASTNAME', 639, y, 730, 15.8)]


def numbered(rs):
    return [dict(r, _scan_id=i) for i, r in enumerate(rs)]


def copied(rs):
    page = dict(page=2, region_box_px=[0, 0, 1275, 1650], elements=[], scan_evidence=dict(ocr_runs=rs))
    with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(copy, 'table_pdf_path', return_value=None):
        copy.copy_ocr_scan(folder, [page], {})
        return (pathlib.Path(folder)/'copy.md').read_text()


class Copier(unittest.TestCase):
    def test_split_heading_above_a_box_is_read_whole_after_both_columns(self):
        text = copied(columns() + heading(400) + box(436))
        self.assertIn('left column line 7 reads on with several more words here.\n\nright column line 0', text)
        self.assertRegex(text, r'right column line 7 reads on with several more words here\.\n+FIRSTNAME M\. LASTNAME\n+box text line 0')
        self.assertEqual(text.count('FIRSTNAME'), 1)

    def test_rule_returns_the_block_span_for_each_piece(self):
        rs = numbered(columns() + heading(400) + box(436))
        joined = copy.scan_spanning_rows(rs, [630])
        self.assertEqual(joined, {16: (0, 1), 17: (0, 1)})

    def test_row_under_a_box_is_read_before_the_columns_below_it(self):
        rs = box(200) + heading(200+3*23+18+8) + columns(top=360)
        text = copied(rs)
        self.assertRegex(text, r'box text line 3 runs across both of the columns with many words in it\.\n+'
                               r'FIRSTNAME M\. LASTNAME\n+left column line 0')

    def test_piece_attached_to_its_column_keeps_the_column(self):
        # the left piece sits one line under the left column's text
        rs = numbered(columns() + [run('FIRSTNAME', 523, 200+8*PITCH, 618, 15.8), run('M. LASTNAME', 639, 400, 730, 15.8)] + box(436))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {})
        rs = numbered(columns(rows=8) + heading(200+8*PITCH+4) + box(200+8*PITCH+40))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {})

    def test_no_spanning_block_near_or_wide_enough_no_join(self):
        self.assertEqual(copy.scan_spanning_rows(numbered(columns() + heading(400)), [630]), {})
        self.assertEqual(copy.scan_spanning_rows(numbered(columns() + heading(400) + box(520)), [630]), {})
        narrow = [run(f'box text line {k} runs across the gutter', 600, 436+k*23, 700, 15.8) for k in range(3)]
        self.assertEqual(copy.scan_spanning_rows(numbered(columns() + heading(400) + narrow), [630]), {})

    def test_element_far_right_of_a_line_end_keeps_its_place(self):
        # a citation set at the right end of a spanning block's last line
        rs = numbered(box(200) + [run('last line of the block.', 310, 292, 560, 15.8),
                                  run('(JOURNAL 1990; 1:2-3)', 790, 292, 945, 15.8)] + columns(top=400))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {})

    def test_ordinary_two_column_rows_and_no_gutter_are_untouched(self):
        self.assertEqual(copy.scan_spanning_rows(numbered(columns() + box(400)), [630]), {})
        self.assertEqual(copy.scan_spanning_rows(numbered(heading(400) + box(436)), []), {})


def heading2(y, lines=2, lead=21):
    """A heading of several lines, each split at the gutter into two pieces."""
    words = [('FIRSTWORD', 'SECONDWORD'), ('THIRDWORD', 'FOURTHWORD'), ('FIFTHWORD', 'SIXTHWORD'), ('SEVENTH', 'EIGHTH')]
    rs = []
    for k in range(lines):
        rs += [run(words[k][0], 515, y+k*lead, 618, 15.8), run(words[k][1], 639, y+k*lead, 742, 15.8)]
    return rs


class Stack(unittest.TestCase):
    def test_two_line_split_heading_above_a_box_joins_as_a_whole(self):
        rs = numbered(columns() + heading2(390) + box(390+21+15.8+18))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {16: (0, 1), 17: (0, 1), 18: (0, 1), 19: (0, 1)})
        text = copied(columns() + heading2(390) + box(390+21+15.8+18))
        self.assertRegex(text, r'right column line 7 reads on with several more words here\.\n+'
                               r'FIRSTWORD SECONDWORD\n+THIRDWORD FOURTHWORD\n+box text line 0')

    def test_two_line_split_heading_under_a_box_at_the_top(self):
        rs = heading2(150) + box(150+21+15.8+18) + columns(top=330)
        text = copied(rs)
        self.assertRegex(text, r'FIRSTWORD SECONDWORD\n+THIRDWORD FOURTHWORD\n+box text line 0')
        self.assertEqual(text.count('FIRSTWORD'), 1)

    def test_three_line_stack_joins_four_never(self):
        rs = numbered(columns() + heading2(380, 3) + box(380+42+15.8+18))
        self.assertEqual(sorted(copy.scan_spanning_rows(rs, [630])), list(range(16, 22)))
        rs = numbered(columns() + heading2(370, 4) + box(370+63+15.8+18))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {})

    def test_piece_reaching_past_the_gutter_line_inside_the_white_band(self):
        # the heading's word spaces fall right of the gutter's centre line, inside the band
        hd = [run('FIRSTWORD', 520, 390, 641, 15.8), run('SECONDWORD', 662, 390, 760, 15.8),
              run('THIRDWORD', 535, 411, 648, 15.8), run('FOURTHWORD', 668, 411, 770, 15.8)]
        rs = numbered(columns() + hd + box(390+21+15.8+18))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {})
        self.assertEqual(sorted(copy.scan_spanning_rows(rs, [630], 1275)), [16, 17, 18, 19])
        text = copied(columns() + hd + box(390+21+15.8+18))
        self.assertRegex(text, r'FIRSTWORD SECONDWORD\n+THIRDWORD FOURTHWORD\n+box text line 0')
        # a piece reaching the other column's text crosses the gutter: no join
        hd[0] = run('FIRSTWORD', 520, 390, 660, 15.8)
        self.assertEqual(copy.scan_spanning_rows(numbered(columns() + hd + box(390+21+15.8+18)), [630], 1275), {})

    def test_stack_with_column_text_beside_one_row_joins_nowhere(self):
        # the left column runs on beside the heading's first line: no row of the stack joins
        rs = numbered(columns(top=390-8*PITCH+PITCH) + heading2(390) + box(390+21+15.8+18))
        self.assertEqual(copy.scan_spanning_rows(rs, [630]), {})


class SecondPass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def paper(self, order):
        em, pitch = sp.EM, sp.LINE
        left = [(3, 100, 200+k*pitch, 600, f'left column line number {k} of the reference text') for k in range(6)]
        right = [(3, 660, 200+k*pitch, 1160, f'right column line number {k} of the reference text') for k in range(6)]
        head = [(3, 523, 200+6*pitch+8*em, 618, 'FIRSTNAME'), (3, 639, 200+6*pitch+8*em, 730, 'M. LASTNAME')]
        top = 200+6*pitch+9*em+em
        boxed = [(3, 310, top+k*pitch, 945, f'box text line {k} runs across both of the columns here') for k in range(4)]
        parts = dict(left=left, right=right, head=head, box=boxed)
        units = [dict(kind='paragraph', text=' '.join(l[4] for l in parts[name]), lines=parts[name]) for name in order]
        return sp.make_paper(self.dir, units)

    def test_heading_read_after_both_columns_is_in_page_order(self):
        p = self.paper(['left', 'right', 'head', 'box'])
        layout = common.Layout(p)
        order = [p.lines[i]['text'] for i in layout.page_lines[3]]
        self.assertEqual(order[12:14], ['FIRSTNAME', 'M. LASTNAME'])
        self.assertEqual(r04_order.check(p)[0], [])

    def test_two_line_heading_read_after_both_columns_is_in_page_order(self):
        em, pitch = sp.EM, sp.LINE
        left = [(3, 100, 200+k*pitch, 600, f'left column line number {k} of the reference text') for k in range(6)]
        right = [(3, 660, 200+k*pitch, 1160, f'right column line number {k} of the reference text') for k in range(6)]
        y = 200+6*pitch+8*em
        head = [(3, 515, y, 618, 'FIRSTWORD'), (3, 639, y, 742, 'SECONDWORD'),
                (3, 515, y+1.3*em, 618, 'THIRDWORD'), (3, 639, y+1.3*em, 742, 'FOURTHWORD')]
        top = y+2.3*em+em
        boxed = [(3, 310, top+k*pitch, 945, f'box text line {k} runs across both of the columns here') for k in range(4)]
        units = [dict(kind='paragraph', text=' '.join(l[4] for l in ls), lines=ls) for ls in (left, right, head, boxed)]
        p = sp.make_paper(self.dir, units)
        order = [p.lines[i]['text'] for i in common.Layout(p).page_lines[3]]
        self.assertEqual(order[12:16], ['FIRSTWORD', 'SECONDWORD', 'THIRDWORD', 'FOURTHWORD'])
        self.assertEqual(r04_order.check(p)[0], [])

    def test_heading_pieces_just_left_of_the_right_column_after_a_short_box_line(self):
        # the box's short last line widens the left column's extent into the right column;
        # the heading's right pieces start just left of the right column's left edge
        em, pitch = sp.EM, sp.LINE
        left = [(3, 100, 200+k*pitch, 600, f'left column line number {k} of the reference text') for k in range(6)]
        right = [(3, 660, 200+k*pitch, 1160, f'right column line number {k} of the reference text') for k in range(6)]
        y = 200+6*pitch+8*em
        head = [(3, 515, y, 618, 'FIRSTWORD'), (3, 655, y, 715, 'SECONDWORD'),
                (3, 515, y+1.3*em, 618, 'THIRDWORD'), (3, 655, y+1.3*em, 712, 'FOURTHWORD')]
        top = y+2.3*em+em
        boxed = [(3, 310, top+k*pitch, 945, f'box text line {k} runs across both of the columns here') for k in range(4)]
        boxed.append((3, 200, top+4*pitch, 720, 'box text short last line ends here'))
        units = [dict(kind='paragraph', text=' '.join(l[4] for l in ls), lines=ls) for ls in (left, right, head, boxed)]
        p = sp.make_paper(self.dir, units)
        order = [p.lines[i]['text'] for i in common.Layout(p).page_lines[3]]
        self.assertEqual(order[12:16], ['FIRSTWORD', 'SECONDWORD', 'THIRDWORD', 'FOURTHWORD'])
        self.assertEqual(r04_order.check(p)[0], [])

    def test_heading_piece_between_the_columns_is_out_of_order(self):
        p = self.paper(['left', 'head', 'right', 'box'])
        self.assertTrue(r04_order.check(p)[0])


if __name__ == '__main__':
    unittest.main()
