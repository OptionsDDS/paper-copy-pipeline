"""A side box is its own block; a paragraph is continued only by text of its own type size (iss-16).

Rules: framed_side_box takes the rows of a shaded box that rule 2 put inside a
column block, when the column's rows beside the fill all stand on one side of
it and a column row above or below reaches over it; the box is read after the
column as side text, never interleaved line by line. rejoin_paragraphs does
not join an unfinished paragraph to a fragment whose median row size differs
by more than 8% (a printed size step). Fixtures are synthetic geometry
modelled on the measured AQ17 p3 (box beside a narrowed column) and AQ09 p1
(an 8.5 pt abbreviation note between a 9.5 pt abstract and a 10.5 pt body).
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_iss16', ROOT / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)


def run(i, text, x0, y, x1, size=20.8):
    return dict(id=f'run:{i}', kind='text', text=text, box_px=[x0, y, x1, y+size-2], size_px=size,
                run_size_px=size, angle=0)


def wrapped_column(fills):
    """A column (x 120-545) narrowing to x 353 beside a box at x 102-330, y 718-932."""
    runs = {}; i = 0
    for k in range(10):
        r = run(i, 'which heroic efforts to salvage extensively and more words here', 121, 458+25*k, 540); runs[r['id']] = r; i += 1
    for k in range(9):
        r = run(i, 'waning. This, how-', 354, 733+25*k, 535); runs[r['id']] = r; i += 1
        r = run(i, 'This article is a preview', 121, 734+19*k, 300, 18.75); runs[r['id']] = r; i += 1
    for k in range(6):
        r = run(i, 'sible concomitant endodontic therapy and more', 121, 958+25*k, 540); runs[r['id']] = r; i += 1
    page = dict(elements=list(runs.values()) + [dict(id=f'fill:{n}', kind='fill', box_px=b) for n, b in enumerate(fills)])
    return runs, page


class SideBox(unittest.TestCase):
    def test_box_beside_a_narrowed_column_is_its_own_block(self):
        runs, page = wrapped_column([[121, 449, 546, 1523], [102, 718, 330, 932]])
        box = copy.framed_side_box(list(runs), runs, page, 20.8)
        self.assertEqual(sorted(box), sorted(m for m, r in runs.items() if r['size_px'] == 18.75))

    def test_no_fill_no_box(self):
        runs, page = wrapped_column([[121, 449, 546, 1523]])
        self.assertEqual(copy.framed_side_box(list(runs), runs, page, 20.8), [])

    def test_full_width_shading_is_not_a_side_box(self):
        runs = {}
        for k in range(8):
            r = run(k, 'an ordinary sentence of the column goes on here', 121, 458+25*k, 540); runs[r['id']] = r
        page = dict(elements=list(runs.values()) + [dict(id='fill:0', kind='fill', box_px=[110, 530, 550, 610])])
        self.assertEqual(copy.framed_side_box(list(runs), runs, page, 20.8), [])

    def test_fill_crossed_by_a_column_row_is_not_a_side_box(self):
        runs, page = wrapped_column([[102, 718, 360, 932]])   # the narrowed rows (x 354) reach into it
        self.assertEqual(copy.framed_side_box(list(runs), runs, page, 20.8), [])


class SizeStep(unittest.TestCase):
    def para(self, text, size, y, **kw):
        return dict(kind='para', text=text, page=1, box=[160, y, 1036, y+60], size=size, **kw)

    def test_smaller_note_is_not_joined_to_the_body(self):
        abstract = self.para('Conclusions: further research is warranted. CHEST 2011; 139(6):1331-1339', 19.8, 911, abstract=True)
        note = self.para('Abbreviations: AHI = apnea-hypopnea index; % AHI = index changes with treatment', 17.7, 1048)
        body = self.para('Obstructive sleep apnea (OSA) is a common sleep-related breathing disorder', 21.9, 1213)
        out = copy.rejoin_paragraphs([abstract, note, body], copy.Joiner([]))
        self.assertEqual(len(out), 3)

    def test_same_size_continuation_still_joins(self):
        first = self.para('The results of the trial were', 20.8, 1400)
        rest = self.para('confirmed in a second cohort.', 20.8, 100)
        out = copy.rejoin_paragraphs([first, rest], copy.Joiner([]))
        self.assertEqual(len(out), 1)
        self.assertIn('were confirmed', out[0]['text'])

    def test_half_point_difference_is_not_a_step(self):
        first = self.para('The results of the trial were', 19.8, 1400)   # 9.5 pt
        rest = self.para('confirmed in a second cohort.', 20.8, 100)     # 10 pt: within 8%
        self.assertEqual(len(copy.rejoin_paragraphs([first, rest], copy.Joiner([]))), 1)

    def test_size_of_the_last_joined_part_decides(self):
        a = self.para('The results of the trial were', 20.8, 1400)
        b = self.para('confirmed in a second cohort and', 20.8, 100)
        note = self.para('Abbreviations: AHI = apnea-hypopnea index', 17.7, 300)
        out = copy.rejoin_paragraphs([a, b, note], copy.Joiner([]))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['size_end'], 20.8)

    def test_caption_inside_a_sentence_follows_the_paragraph(self):
        body = self.para('Overall, the study sample of the trial included predominantly', 20.8, 1400)
        caption = self.para('Figure 1. Study flow chart: randomization, treatment, and follow-up.', 22.9, 100)
        rest = self.para('men, who were middle aged and obese.', 20.8, 300)
        out = copy.rejoin_paragraphs([body, caption, rest], copy.Joiner([]))
        self.assertEqual([it['text'][:6] for it in out], ['Overal', 'Figure'])
        self.assertIn('predominantly men, who', out[0]['text'])

    def test_no_pass_over_to_a_capital_start(self):
        body = self.para('Overall, the study sample included predominantly', 20.8, 1400)
        caption = self.para('Figure 1. Study flow chart.', 22.9, 100)
        rest = self.para('Men were middle aged and obese.', 20.8, 300)
        self.assertEqual(len(copy.rejoin_paragraphs([body, caption, rest], copy.Joiner([]))), 3)

    def test_no_pass_over_three_pieces(self):
        body = self.para('Overall, the study sample included predominantly', 20.8, 1400)
        others = [self.para('Note %d in another size.' % k, s, 100+50*k) for k, s in enumerate((17.7, 24.0, 27.0))]
        rest = self.para('men, who were middle aged and obese.', 20.8, 300)
        self.assertEqual(len(copy.rejoin_paragraphs([body] + others + [rest], copy.Joiner([]))), 5)


class LayoutBreak(unittest.TestCase):
    """layout_break (re-ladder): kind and column measure end a sentence; sizes play no part."""
    COL0, COL1 = (118, 591), (650, 1123)

    def para(self, text, y, x0, x1, col, size=20.75, **kw):
        return dict(kind='para', text=text, page=1, box=[x0, y, x1, y+60], size=size, col=col, **kw)

    def test_labelled_abstract_without_size_or_box_is_not_joined_to_the_body(self):
        parts = [dict(kind='para', text=t, page=1, abstract=True) for t in
                 ('Methods: depths were measured on forty sites.', 'Conclusions: the depth follows the dew. Field Letters 2019; 4(2):11-19')]
        body = self.para('Walls of loose stone are among the oldest habitats in farmland, and their', 520, 125, 605, self.COL0, 21.9)
        out = copy.rejoin_paragraphs(parts + [body], copy.Joiner([]))
        self.assertEqual(len(out), 3)

    def test_abstract_keeps_an_unplaced_fragment(self):
        a = dict(kind='para', text='Results: the follow-up lasted', page=1, abstract=True)
        b = dict(kind='para', text='5.6 years on average.', page=1)
        self.assertEqual(len(copy.rejoin_paragraphs([a, b], copy.Joiner([]))), 1)

    def test_abstract_joins_its_witnessed_continuation(self):
        a = dict(kind='para', text='Results: the depth tracked the number of days', page=1, abstract=True)
        b = self.para('with dew over both years.', 100, 650, 1123, self.COL1, abstract_continuation=True)
        self.assertEqual(len(copy.rejoin_paragraphs([a, b], copy.Joiner([]))), 1)

    def test_wide_block_above_a_column_is_not_joined_in_the_same_size(self):
        wide = self.para('Abstract text of the paper. Key Words: stones; walls; moss; dew; survival rate', 564, 325, 1123, (325, 1123))
        body = self.para('Walls of loose stone are among the oldest habitats in farmland, and', 953, 118, 591, self.COL0)
        self.assertEqual(len(copy.rejoin_paragraphs([wide, body], copy.Joiner([]))), 2)

    def test_keyword_line_is_not_joined_to_the_body_far_below_in_its_column(self):
        keys = self.para('Keywords: moths; light; farm gates; night counts', 368, 127, 583, self.COL0, 18.75)
        body = self.para('counts of moths at farm gates have seldom been compared between gates', 520, 125, 591, self.COL0, 18.75)
        self.assertEqual(len(copy.rejoin_paragraphs([keys, body], copy.Joiner([]))), 2)

    def test_keyword_line_continued_in_the_next_column_still_joins(self):
        keys = self.para('Keywords: moths; light; farm gates; night', 1500, 127, 583, self.COL0, 18.75)
        rest = self.para('counts; lamps', 183, 650, 800, self.COL1, 18.75)
        self.assertEqual(len(copy.rejoin_paragraphs([keys, rest], copy.Joiner([]))), 1)

    def test_next_column_narrowed_by_a_float_still_joins(self):
        a = self.para('the measured width re-establishes itself at', 1383, 165, 591, self.COL0)
        b = self.para('an apical level after the healing time.', 183, 867, 1123, self.COL1)
        out = copy.rejoin_paragraphs([a, b], copy.Joiner([]))
        self.assertEqual(len(out), 1)
        self.assertIn('at an apical', out[0]['text'])

    def test_pieces_far_apart_in_one_column_still_join(self):
        a = self.para('Unloaded titanium versus machined and', 1010, 297, 495, self.COL0, 13.8)
        b = self.para('sandblasted implants of the second group', 1367, 297, 481, self.COL0, 13.8)
        self.assertEqual(len(copy.rejoin_paragraphs([a, b], copy.Joiner([]))), 1)

    def test_measure_of_the_last_joined_part_decides(self):
        a = self.para('The first column text runs on to the', 1400, 118, 591, self.COL0)
        b = self.para('next column where the sentence goes on and', 183, 650, 1123, self.COL1)
        c = self.para('ends in the same column below the gap.', 400, 650, 1123, self.COL1)
        out = copy.rejoin_paragraphs([a, b, c], copy.Joiner([]))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['col_end'], self.COL1)


if __name__ == '__main__':
    unittest.main()
