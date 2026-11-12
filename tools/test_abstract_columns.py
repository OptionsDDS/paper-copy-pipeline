"""Rule 7: a labelled abstract that runs on into the next column is read before the body below it."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('abstract_columns_boxer', ROOT / 'standalone/element_boxer_sc.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

BODY = 20

def blk(name, text, box, size=19):
    return dict(id=name, cls='main', text=text, box_px=list(box), size=size, lines=text.count('\n') + 1)

def order(blocks, floats=()):
    result, cut = b.reading_order_abstract_columns(list(blocks), BODY, lambda q: q['text'], floats)
    return [q['id'] for q in result], cut

def page(left_end='three were based on case-', right_start='control studies, and nine were',
         label='SUMMARY This review synthesises\nrecent evidence on the', right_box=(655, 500, 1140, 970)):
    """Two abstract columns over two body columns, read column by column by rule 7's bands."""
    abs_left = blk('abs_left', label + '\n' + left_end, (132, 500, 618, 1027))
    abs_right = blk('abs_right', right_start + '\nprimary studies made conclusions impossible.', right_box)
    head = blk('head', 'Background', (132, 1100, 270, 1122), size=23)
    body_left = blk('body_left', 'Population-based studies report\nthat he would need to', (132, 1144, 617, 1460), size=20)
    body_right = blk('body_right', 'read about twenty articles daily.\nSystematic reviews are', (655, 1092, 1140, 1460), size=20)
    return [abs_left, head, body_left, abs_right, body_right]


class AbstractColumns(unittest.TestCase):
    def test_unfinished_abstract_continues_in_next_column_before_body(self):
        ids, cut = order(page())
        self.assertEqual(ids, ['abs_left', 'abs_right', 'head', 'body_left', 'body_right'])
        self.assertTrue(1027 < cut < 1092)

    def test_abstract_ending_with_a_sentence_keeps_the_column_order(self):
        ids, cut = order(page(left_end='three were based on case series.'))
        self.assertEqual(ids, ['abs_left', 'head', 'body_left', 'abs_right', 'body_right'])
        self.assertIsNone(cut)

    def test_capitalised_next_column_is_not_a_witnessed_continuation(self):
        ids, cut = order(page(right_start='Control studies, and nine were'))
        self.assertEqual(ids[1], 'head')
        self.assertIsNone(cut)

    def test_body_heading_named_summary_is_not_an_abstract_label(self):
        ids, cut = order(page(label='Summary of the selected studies\nThe included studies report'))
        self.assertIsNone(cut)

    def test_lowercase_run_in_word_is_not_a_label(self):
        ids, cut = order(page(label='Summary data were pooled\nacross the studies and'))
        self.assertIsNone(cut)

    def test_block_crossing_the_channel_stops_the_cut(self):
        # the right column runs on past the abstract's end into the body band: no channel crosses the frame
        ids, cut = order(page(right_box=(655, 500, 1140, 1080)))
        self.assertIsNone(cut)

    def test_float_crossing_the_channel_stops_the_cut(self):
        ids, cut = order(page(), floats=[(655, 1000, 1140, 1100)])
        self.assertIsNone(cut)

    def test_top_must_align_with_the_label(self):
        ids, cut = order(page(right_box=(655, 560, 1140, 970)))
        self.assertIsNone(cut)

    def test_continuation_in_another_size_is_not_the_abstract(self):
        blocks = page()
        blocks[3]['size'] = 22
        self.assertIsNone(order(blocks)[1])

    def test_label_on_its_own_line_above_the_abstract_text(self):
        label = blk('label', 'Abstract', (132, 470, 240, 490), size=23)
        blocks = page(label='Periodontal therapy was\nreviewed in thirty')
        blocks[3]['box_px'][1] = 470
        ids, cut = order([label] + blocks)
        self.assertEqual(ids, ['label', 'abs_left', 'abs_right', 'head', 'body_left', 'body_right'])

    def test_no_label_no_change(self):
        blocks = page(label='Periodontal therapy was\nreviewed in thirty')
        self.assertIsNone(order(blocks)[1])


if __name__ == '__main__':
    unittest.main()
