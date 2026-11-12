#!/usr/bin/env python3
"""candidate-nov2 merge rules (lane f5stream onto the sixteen single-issue lanes).

The shared boundary witness decides every join; a single-issue rule that decides the same join
remains an additional witness that may refuse it, never force it:
- rejoin_paragraphs: a piece reached by iss-16's pass-over joins only on the witness, not on the
  bare column-turn rule; a size step refuses a join the witness allows.
- witness_slots and lift_inserted_blocks refuse a resume across a size step.
- lift_inserted_blocks: the halves of a small-type stream that already stand together (rule 7
  read an abstract's columns before the body, iss-04) join on f5stream's witnesses.
All texts are invented; no literal from any paper.
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(ROOT))
import copy_paper as copy


def J(): return copy.Joiner([])


def para(text, page=1, col=0, top=100, bottom=200, full=True, flush=True, size=20.0, face='ABCDEF+Serif-Roman', **kw):
    left = 100 + col*500
    return dict(kind='para', text=text, page=page, box=[left, top, left+450, bottom], flow_parts=[(page, [left, top, left+450, bottom])],
                flow_start=(page, col, flush), flow_end=(page, col, full), style=(size, face), size=size, **kw)


class SmallTypeHalvesTogether(unittest.TestCase):
    small = dict(size=18.0, face='ABCDEF+Serif-Bold', barrier=True)

    def test_adjacent_halves_join(self):
        items = [para('SUMMARY Of these reviews, two were based on case–', col=0, top=500, bottom=1000, **self.small),
                 para('control studies, and the rest were mixed designs.', col=1, top=500, bottom=900, full=False, **self.small),
                 dict(kind='heading', text='Background', page=1),
                 para('Earlier surveys were rare and covered few subjects in all.', col=0, top=1100, bottom=1300, full=False)]
        out = copy.lift_inserted_blocks(items, [dict(page=1, elements=[], unpaired=[])], 20.0, J())
        self.assertEqual(out[0]['text'], 'SUMMARY Of these reviews, two were based on case–control studies, and the rest were mixed designs.')
        self.assertEqual([x.get('text', '')[:10] for x in out[1:]], ['Background', 'Earlier su'])

    def test_capital_start_or_other_style_stays(self):
        for second in (para('Control studies were the rest.', col=1, top=500, bottom=900, full=False, **self.small),
                       para('control studies, and the rest.', col=1, top=500, bottom=900, full=False,
                            size=18.0, face='GHIJKL+Sans-Roman', barrier=True)):
            items = [para('SUMMARY Of these reviews, two were based on case–', col=0, top=500, bottom=1000, **self.small), second]
            out = copy.lift_inserted_blocks(items, [dict(page=1, elements=[], unpaired=[])], 20.0, J())
            self.assertEqual(len(out), 2)


class SizeStepRefuses(unittest.TestCase):
    def test_slot_join_refused_across_a_size_step(self):
        items = [para('the measurements were repeated in all of the', col=0, top=900, bottom=1500),
                 dict(kind='table', caption='Table 1. Values', page=1, top=100),
                 para('remaining samples one week later.', page=2, col=0, top=80, bottom=200, size=15.0)]
        out = copy.witness_slots(items, J(), [dict(page=1), dict(page=2)], [], None)
        self.assertEqual([x['kind'] for x in out], ['para', 'table', 'para'])

    def test_slot_join_in_one_size_still_joins(self):
        items = [para('the measurements were repeated in all of the', col=0, top=900, bottom=1500),
                 dict(kind='table', caption='Table 1. Values', page=1, top=100),
                 para('remaining samples one week later.', page=2, col=0, top=80, bottom=200)]
        out = copy.witness_slots(items, J(), [dict(page=1), dict(page=2)], [], None)
        self.assertEqual([x['kind'] for x in out], ['para', 'table'])

    def test_witnessed_join_refused_by_size_step(self):
        items = [para('can be found in the online version at:', size=25.0),
                 para('example.org/a/b/c/d', top=210, bottom=230, size=20.8)]
        self.assertEqual(len(copy.rejoin_paragraphs(items, J(), 20.0)), 2)


class PassOverNeedsTheWitness(unittest.TestCase):
    def items(self, resume):
        return [para('Overall, the study sample of the trial included predominantly', col=0, top=900, bottom=1500),
                para('Note in another size.', col=0, top=1510, bottom=1530, size=15.0, full=False),
                para(resume, col=1, top=80, bottom=300)]

    def test_passed_over_piece_joins_on_the_witness(self):
        out = copy.rejoin_paragraphs(self.items('men, who were middle aged and obese.'), J(), 20.0)
        self.assertIn('predominantly men, who', out[0]['text'])
        self.assertEqual(out[1]['text'], 'Note in another size.')

    def test_capital_resume_is_not_joined_across_the_note(self):
        self.assertEqual(len(copy.rejoin_paragraphs(self.items('Most were middle aged and obese.'), J(), 20.0)), 3)


if __name__ == '__main__':
    unittest.main()
