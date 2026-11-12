"""A front-page body opener above footnote-size rows returns to the body alone (lane iss-02)."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1]/'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)

BODY = 20
ASIDE = dict(id='block:6', cls='aside', why='outside every text column')


def row(text, y, size=BODY, face='Body', x=100):
    return [dict(id=f'run:{y}', text=text, angle=0, box_px=[x, y, x+500, y+size],
                 run_size_px=size, _faces={face: len(text)})]


class FrontOpenerAboveFootnotes(unittest.TestCase):
    def setUp(self):
        self.page = dict(page=1, region_box_px=[0, 0, 1200, 1600], _body_face='Body', floats=[], elements=[],
                         _copy_front=[[100, 80, 900, 300]], main_text=dict(columns=[[650, 1150]], blocks=[]))
        self.anchor = dict(order=1, meta=dict(box_px=[650, 845, 1150, 1500], size_px=BODY), panel=False, page=1,
                           lines=['continues the opening sentence in the next column'])
        self.rows = [row('Opening', 848, 27, 'Head.B'),
                     row('The first body line of the opening paragraph runs to the', 880),
                     row('column edge and stops in the middle of its sentence', 905),
                     row('* Department of Examples, Example University, Example City.', 941, 16, 'Note.I'),
                     row('† Department of Samples, Sample University, Sample Town.', 992, 16, 'Note.I')]

    def opener(self, rows, meta=ASIDE):
        return paper.front_body_opener(rows, self.page, meta, [self.anchor], BODY)

    def test_tail_of_smaller_rows_is_found(self):
        self.assertEqual(paper.smaller_tail_start(self.rows, BODY), 3)
        self.assertIsNone(paper.smaller_tail_start(self.rows[:3], BODY))      # no smaller rows: nothing to split
        self.assertIsNone(paper.smaller_tail_start([self.rows[0]] + self.rows[3:], BODY))   # heading alone above them

    def test_whole_block_is_not_an_opener_but_its_head_is(self):
        self.assertIsNone(self.opener(self.rows))
        anchor, block = self.opener(self.rows[:3])
        self.assertIs(anchor, self.anchor)
        self.assertEqual(block['lines'][0], 'Opening')
        self.assertEqual(len(block['lines']), 3)
        self.assertTrue(block['meta']['front_body_opener'])

    def test_other_aside_kinds_stay_side_text(self):
        self.assertIsNone(self.opener(self.rows[:3], dict(ASIDE, why='beside the text column')))
        self.assertIsNone(self.opener(self.rows[:3], dict(ASIDE, cls='footnote')))

    def test_finished_sentence_or_publication_signal_is_not_moved(self):
        finished = self.rows[:2] + [row('column edge and ends its sentence here.', 905)]
        self.assertIsNone(self.opener(finished))
        dated = self.rows[:2] + [row('column edge and was received in 2014 with the', 905)]
        self.assertIsNone(self.opener(dated))

    def test_front_boxes_must_not_meet_the_opener(self):
        # affiliations set as footnotes wholly below the opener do not precede it
        self.page['_copy_front'] = [[100, 80, 900, 300], [100, 941, 600, 1476]]
        self.assertIsNotNone(self.opener(self.rows[:3]))
        self.page['_copy_front'] = [[100, 80, 900, 300], [100, 900, 600, 1476]]    # reaches into its rows
        self.assertIsNone(self.opener(self.rows[:3]))
        self.page['_copy_front'] = [[100, 941, 600, 1476]]                          # nothing printed above it
        self.assertIsNone(self.opener(self.rows[:3]))

    def test_uppercase_neighbour_does_not_continue_the_sentence(self):
        self.anchor['lines'] = ['A new paragraph in the next column']
        self.assertIsNone(self.opener(self.rows[:3]))


class HeadingBlockAboveOpener(FrontOpenerAboveFootnotes):
    """A numbered heading the boxer set in its own block, above the body rows (iss-02 re-ladder)."""
    def setUp(self):
        super().setUp()
        self.head = [row('1. Opening', 836, 22, 'Head.B')]
        self.body = self.rows[1:]

    def test_heading_block_directly_above_joins(self):
        self.assertTrue(paper.heading_block_over(self.head, self.body, ASIDE, BODY))
        self.assertIsNone(self.opener(self.body))                        # body rows alone have no heading
        k = paper.smaller_tail_start(self.body, BODY)
        self.assertEqual(k, 2)
        self.assertIsNone(self.opener(self.body[:k]))                     # the rows above the tail have no heading either
        anchor, block = self.opener(self.head + self.body[:2])
        self.assertIs(anchor, self.anchor)
        self.assertEqual(block['lines'][0], '1. Opening')
        self.assertEqual(len(block['lines']), 3)
        self.assertIsNone(self.opener(self.head + self.body))            # the footnote rows never join

    def test_unnumbered_heading_block_joins_the_same_way(self):
        head = [row('Opening', 836, 22, 'Head.B')]
        self.assertTrue(paper.heading_block_over(head, self.body, ASIDE, BODY))
        self.assertIsNotNone(self.opener(head + self.body[:2]))

    def test_far_offset_or_other_class_heading_block_does_not_join(self):
        far = [row('1. Opening', 760, 22, 'Head.B')]                      # 4 body heights above
        self.assertFalse(paper.heading_block_over(far, self.body, ASIDE, BODY))
        shifted = [row('1. Opening', 836, 22, 'Head.B', x=160)]          # another left edge
        self.assertFalse(paper.heading_block_over(shifted, self.body, ASIDE, BODY))
        self.assertFalse(paper.heading_block_over(self.head, self.body, dict(ASIDE, why='beside the text column'), BODY))
        below = [row('1. Opening', 1100, 22, 'Head.B')]                   # under the rows, not above
        self.assertFalse(paper.heading_block_over(below, self.body, ASIDE, BODY))
        four = [row(f'Line {k}', 740+22*k, 22, 'Head.B') for k in range(4)]
        self.assertFalse(paper.heading_block_over(four, self.body, ASIDE, BODY))


if __name__ == '__main__': unittest.main()
