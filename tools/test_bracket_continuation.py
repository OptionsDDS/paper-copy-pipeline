#!/usr/bin/env python3
"""An unclosed bracket at a paragraph's end is a witness that its sentence continues (D-520).

rejoin_paragraphs joins the two halves across pages holding only floats, even when the
first half ends with a period (an abbreviation inside the bracket) and the second half was
read as a list marker (the bracket's closing half, "6)"). Finished sentences, real
enumerations and a next paragraph opening its own bracket are untouched.
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import copy_paper as copy


def J(): return copy.Joiner([])


class BracketWitness(unittest.TestCase):
    def test_unclosed_bracket_closed_by_next_text(self):
        self.assertTrue(copy.bracket_continuation('The defect should be filled (Fig.', '6) to maximize regeneration.'))
        self.assertTrue(copy.bracket_continuation('A standardized technique (precision of 0.1', 'mm) was determined.'))
        self.assertTrue(copy.bracket_continuation('as reported before [12,', '13] and later.'))

    def test_balanced_or_finished_text_is_no_witness(self):
        self.assertFalse(copy.bracket_continuation('The steps are as follows:', '1) first step.'))
        self.assertFalse(copy.bracket_continuation('It was shown (Fig. 2).', '3) a third item.'))
        # Only the last sentence counts: an earlier unbalanced bracket does not reach across a sentence end.
        self.assertFalse(copy.bracket_continuation('Values (see below. The next sentence ends here.', '2) item'))

    def test_next_text_opening_its_own_bracket_is_no_witness(self):
        self.assertFalse(copy.bracket_continuation('The defect should be filled (Fig.', '(see Table 2) 6) to maximize.'))
        self.assertFalse(copy.bracket_continuation('The defect should be filled (Fig.', 'A new paragraph with no bracket.'))


class RejoinAcrossFloatPages(unittest.TestCase):
    def items(self, second_list=True):
        return [dict(kind='para', text='The defect should be filled or slightly overfilled (Fig.', page=2),
                dict(kind='page', page=2),
                dict(kind='figure', caption='Fig. 1. Preoperative view.', page=3, top=100),
                dict(kind='page', page=3),
                dict(kind='figure', caption='Fig. 7. A suture.', page=4, top=100),
                dict(kind='page', page=4),
                dict(kind='para', text='6) to maximize regeneration while not compromising flap closure.', page=5,
                     **({'list': True} if second_list else {})),
                dict(kind='para', text='A new paragraph follows.', page=5)]

    def test_marker_shaped_closing_half_joins_and_loses_its_list_flag(self):
        joined = copy.rejoin_paragraphs(self.items(), J())
        self.assertEqual(joined[0]['text'],
                         'The defect should be filled or slightly overfilled (Fig. 6) to maximize regeneration while not compromising flap closure.')
        self.assertFalse(joined[0].get('list'))
        self.assertEqual(joined[0]['pages'], {2, 5})
        # The float pages follow the whole paragraph (carried in order), the next paragraph stays separate.
        self.assertEqual([x['kind'] for x in joined[1:]], ['page', 'figure', 'page', 'figure', 'page', 'para'])
        self.assertEqual(joined[-1]['text'], 'A new paragraph follows.')

    def test_plain_closing_half_joins_too(self):
        joined = copy.rejoin_paragraphs(self.items(second_list=False), J())
        self.assertTrue(joined[0]['text'].endswith('(Fig. 6) to maximize regeneration while not compromising flap closure.'))

    def test_real_enumeration_after_a_finished_sentence_stays_a_list(self):
        items = [dict(kind='para', text='The protocol has three steps:', page=2),
                 dict(kind='page', page=2),
                 dict(kind='para', text='1) scaling of every surface.', page=3, list=True),
                 dict(kind='para', text='2) root planing.', page=3, list=True)]
        joined = copy.rejoin_paragraphs(items, J())
        self.assertEqual([x.get('text') for x in joined if x['kind'] == 'para'],
                         ['The protocol has three steps:', '1) scaling of every surface.', '2) root planing.'])
        self.assertTrue(joined[2].get('list'))

    def test_finished_bracketed_sentence_does_not_swallow_a_marker(self):
        items = [dict(kind='para', text='The lesion was measured (Fig. 2).', page=2),
                 dict(kind='page', page=2),
                 dict(kind='para', text='3) a separate enumerated item.', page=3, list=True)]
        joined = copy.rejoin_paragraphs(items, J())
        self.assertEqual(len([x for x in joined if x['kind'] == 'para']), 2)
        self.assertTrue(joined[-1].get('list'))


class WholeUnfinishedSentence(unittest.TestCase):
    """The witness counts brackets over the whole unfinished sentence: a period inside a
    bracket is no sentence end (the text after it closes a bracket it never opened)."""
    def test_period_inside_an_earlier_closed_bracket_is_passed_over(self):
        prev = 'Earlier work ended. The basins filled in spring (Fig. 2B) and the dry pans (Fig.'
        self.assertEqual(copy.unfinished_sentence(prev),
                         'The basins filled in spring (Fig. 2B) and the dry pans (Fig.')
        self.assertTrue(copy.bracket_continuation(prev, '2C) were cleared by hand.'))

    def test_real_sentence_end_still_bounds_the_sentence(self):
        self.assertEqual(copy.unfinished_sentence('Values (see below. The next sentence ends here.'),
                         'The next sentence ends here.')
        self.assertEqual(copy.unfinished_sentence('No cut at all here'), 'No cut at all here')

    def test_citation_list_cut_at_a_comma_or_a_hyphen(self):
        self.assertTrue(copy.bracket_continuation('was read with a gauge (Brook et al, 1970, Lane & Moss 1981, Hale et al,',
                                                  '1988. Rowe et al, 1990), whereas others used'))
        self.assertTrue(copy.bracket_continuation('cells spread over coated plates (Wen-', 'dell & Marsh 1979), it was'))

    def test_stray_bracket_before_a_closed_citation_at_the_paragraph_end(self):
        # The paragraph does not end inside the bracket: its last bracket closes a citation.
        self.assertFalse(copy.bracket_continuation(
            'in those with at least 2(0 plots at the start, gravel was a predictor of loss (Rowe, 1980), and '
            'later beds were at risk (Hale et al., 1991).', 'A further study of the beds, smaller plots excluded) was read.'))

    def test_a_finished_sentence_with_a_stray_bracket_before_a_new_section(self):
        # A stray opening bracket (recognition noise) before a sentence end, then a heading with no bracket.
        self.assertFalse(copy.bracket_continuation('entered when p<(o.x and removed at p>0.2.', 'Findings'))


def line(text, x, y, page, w=240, size=12):
    r = dict(text=text, box_px=[x, y, x+w, y+size], size_px=size)
    return dict(kind='line', runs=[r], box_px=r['box_px'], page=page)


class ScanRoute(unittest.TestCase):
    """The scan route keeps a sentence whose bracket is closed after a page turn, a column
    change or a printed gap in one printed paragraph."""
    def test_witness_across_a_page_turn_with_the_closer_on_a_later_line(self):
        arranged = [line('of the samples showed residue (41.2% of the', 20, 700, 2),
                    line('samples with visible residue were scored', 20, 40, 3),
                    line('as clean) and few were missed.', 20, 56, 3)]
        self.assertTrue(copy.scan_printed_break(arranged[0], arranged[1]))
        self.assertTrue(copy.scan_bracket_witness(arranged, 1, [arranged[0]['runs'][0]['text']]))

    def test_witness_needs_the_closer_inside_the_next_printed_paragraph(self):
        arranged = [line('entered when p<(o.x and removed at p>0.2.', 20, 300, 4),
                    line('Findings', 20, 340, 4, w=80),
                    line('The readings were close {r= 0.9, /) and', 20, 380, 4)]
        self.assertTrue(copy.scan_printed_break(arranged[1], arranged[2]))
        self.assertFalse(copy.scan_bracket_witness(arranged, 1, [arranged[0]['runs'][0]['text']]))

    def test_column_change_after_a_comma_inside_a_citation(self):
        arranged = [line('a gauge (Brook et al, 1970, Hale et al,', 20, 900, 1),
                    line('1988. Rowe et al, 1990), whereas', 330, 100, 1)]
        self.assertTrue(copy.scan_printed_break(arranged[0], arranged[1]))
        self.assertTrue(copy.scan_bracket_witness(arranged, 1, ['was read with', arranged[0]['runs'][0]['text']]))
        self.assertFalse(copy.scan_bracket_witness(arranged, 1, []))


if __name__ == '__main__':
    unittest.main()
