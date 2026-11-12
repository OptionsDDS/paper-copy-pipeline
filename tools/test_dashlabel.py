"""A figure caption label joined to its words by an en or em dash (lane iss-01), independent of any paper text.

Rule 1 marks a run label_font when its label is set in a font of its own; rule 4 then reads the
run as a caption label although no . or : follows the number. A dash before a digit is a range.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashlabel_boxer', ROOT / 'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec); spec.loader.exec_module(boxer)


def chars(*parts):
    """characters of a run without spaces, as rule 1 holds them: (text, font) pieces"""
    return [dict(text=ch, font=font) for text, font in parts for ch in text.replace(' ', '')]


class DashLabel(unittest.TestCase):
    def test_bold_label_then_dash_in_caption_face(self):
        self.assertTrue(boxer.label_in_own_font(chars(('Figure 1', 'Sans-Bold'), ('—Flow chart of the trial', 'Sans'))))
        self.assertTrue(boxer.label_in_own_font(chars(('Fig. 2', 'Sans-Bold'), ('\u2013Outcomes by arm', 'Sans'))))

    def test_dash_joined_table_label_keeps_the_existing_rules(self):
        self.assertFalse(boxer.label_in_own_font(chars(('Table 2', 'Sans-Bold'), ('\u2014Outcomes', 'Sans'))))
        self.assertFalse(boxer.is_caption_label('Table 2\u2014Outcomes of treatment', label_font=True))

    def test_dash_in_label_face_then_words(self):
        self.assertTrue(boxer.label_in_own_font(chars(('Fig. 3—', 'Sans-Bold'), ('Panels of the device', 'Sans'))))

    def test_one_face_throughout_is_not_a_label_font(self):
        self.assertFalse(boxer.label_in_own_font(chars(('Figure 1—Flow chart of the trial', 'Serif'))))

    def test_range_is_never_a_label(self):
        self.assertFalse(boxer.label_in_own_font(chars(('Figures', 'Serif-Bold'), (' 1–3 show the arms', 'Serif'))))
        self.assertFalse(boxer.label_in_own_font(chars(('Figure 1', 'Serif-Bold'), ('–3 show the arms', 'Serif'))))
        self.assertFalse(boxer.is_caption_label('Figure 1–3 show the arms', label_font=True))

    def test_label_run_straight_into_words_is_unchanged(self):
        self.assertTrue(boxer.label_in_own_font(chars(('Table 1', 'Serif-Bold'), ('Results', 'Serif'))))
        self.assertFalse(boxer.label_in_own_font(chars(('Table 1', 'Serif-Bold'), ('.', 'Serif-Bold'))))

    def test_caption_label_needs_the_font_witness(self):
        self.assertTrue(boxer.is_caption_label('Figure 1—Study flow chart: randomization', label_font=True))
        self.assertFalse(boxer.is_caption_label('Figure 1—Study flow chart: randomization', label_font=False))
        self.assertTrue(boxer.is_caption_run(dict(text='Figure 3—Scores at baseline', label_font=True)))
        self.assertFalse(boxer.is_caption_run(dict(text='Figure 3—Scores at baseline')))

    def test_sub_figure_letter_in_label_face_then_dash(self):
        # re-ladder: the letter is part of the label, set in the label's face; the change comes at the dash
        self.assertTrue(boxer.label_in_own_font(chars(('Figure 4b', 'Sans-Bold'), ('—Readings at the site', 'Sans'))))
        self.assertTrue(boxer.label_in_own_font(chars(('Fig. 2c', 'Serif-Bold'), ('\u2013Counts per plot', 'Serif'))))
        self.assertTrue(boxer.label_in_own_font(chars(('Figure 5a—', 'Sans-Bold'), ('Map of the area', 'Sans'))))
        self.assertTrue(boxer.is_caption_label('Figure 4b\u2014Readings at the site', label_font=True))

    def test_sub_figure_letter_in_caption_face_is_unchanged(self):
        self.assertTrue(boxer.label_in_own_font(chars(('Figure 4', 'Sans-Bold'), ('b—Readings at the site', 'Sans'))))

    def test_sub_figure_letter_without_font_change_or_as_range_is_not_a_label(self):
        self.assertFalse(boxer.label_in_own_font(chars(('Figure 4b—Readings at the site', 'Serif'))))
        self.assertFalse(boxer.label_in_own_font(chars(('Figure 4b', 'Serif-Bold'), ('–5 show the plots', 'Serif'))))
        self.assertFalse(boxer.label_in_own_font(chars(('Table 2b', 'Sans-Bold'), ('\u2014Outcomes', 'Sans'))))


if __name__ == '__main__':
    unittest.main()
