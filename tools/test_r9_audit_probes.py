"""Lane r9-rowclues, audit 2 (AUDIT2-69a87ad.md): the auditor's made-up pages as unit tests of the step-2 switches.

Each switch is tested off (the built clue form as it was) and on. Pages are the auditor's probes (out-r9-audit/audit2/
probes), synthetic, no paper text; 150 dpi pixels, as in the page records.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_paper', ROOT / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
ov = c.overlay_module()
K = 150 / 72
CH = 5.0 * K
CLUES = ('label', 'a2', 'hspan', 'shade2', 'cent', 'PROC', 'RG', 'RGN', 'RGK2', 'RGG200', 'B8', 'B7', 'D9', 'D8', 'D7')


def line(y, cells, h=8):
    items = []
    for x, text in cells:
        x = x * K
        for w in text.split():
            run = dict(id=f'{x:.0f}:{y}:{w}', text=w, angle=0, box_px=[x, y * K, x + CH * len(w), (y + h) * K])
            items.append(([x, y * K, x + CH * len(w), (y + h) * K], w, run)); x += CH * (len(w) + 1)
    return dict(items=items, top=y * K, bot=(y + h) * K, vc=(y + h / 2) * K, h=h * K)


def rule(y, x0=40, x1=480):
    return ([x0 * K, y * K, x1 * K, (y + .5) * K], 'rule')


def grid(t, flags=(), G=()):
    old = c.R8_CLUE_FLAGS
    try:
        c.R8_CLUE_FLAGS = frozenset(flags) | (old & {'NOTES_LOWEST'})
        g = c.overlay_grid(ov.fit(t, list(G), K), t, [0], list(G), K, frozenset(CLUES))
    finally:
        c.R8_CLUE_FLAGS = old
    return g


def rows(g):
    return [[' '.join(x) for x in r['cells']] for r in g['rows']]


TW17A = [line(100, [(50, 'Study'), (200, 'Outcome'), (400, 'N')]),
         line(114, [(50, 'Smith'), (200, 'pain was reduced in'), (400, '40')]),
         line(124, [(50, 'Note'), (200, 'most of the patients')]),
         line(148, [(50, 'Jones'), (200, 'Swelling was reduced in'), (400, '52')]),
         line(158, [(50, 'Remark'), (200, 'some of the patients')]),
         line(182, [(50, 'Brown'), (200, 'No change'), (400, '12')]),
         line(192, [(50, 'Comment'), (200, 'none')])]

TW5 = [line(100, [(50, 'Item'), (200, 'Finding'), (350, 'Grade')]),
       line(112, [(200, 'lesions seen on'), (350, 'mild')]), line(118.5, [(50, 'Gingiva')]), line(125, [(200, 'both arches')]),
       line(142, [(200, 'no lesions on'), (350, 'none')]), line(148.5, [(50, 'Palate')]), line(155, [(200, 'either side')]),
       line(172, [(200, 'ulcers on'), (350, 'severe')]), line(178.5, [(50, 'Tongue')]), line(185, [(200, 'the tip')])]

TW7B = [line(100, [(50, 'Marker'), (200, 'Test'), (300, 'Control')]),
        line(112, [(50, 'Interleukin'), (200, '1.20'), (300, '2.30')]), line(124, [(200, '(0.40)'), (300, '(0.50)')]),
        line(136, [(50, 'Albumin'), (200, '3.20'), (300, '4.30')]), line(148, [(200, '(0.60)'), (300, '(0.70)')]),
        line(160, [(50, 'Ferritin'), (200, '4.20'), (300, '5.30')]), line(172, [(200, '(0.80)'), (300, '(0.90)')])]

TW1C = [line(100, [(50, 'Marker'), (150, 'Time'), (250, 'Test')]),
        line(112, [(50, 'Interleukin'), (150, 'Baseline'), (250, '1.20')]), line(124, [(150, 'Day seven'), (250, '1.50')]),
        line(136, [(50, '(pg/ml)')]), line(148, [(50, 'Albumin'), (150, 'Baseline'), (250, '3.20')]),
        line(160, [(50, 'Ferritin'), (150, 'Baseline'), (250, '4.20')])]

B7 = [line(100, [(50, 'Item'), (200, 'Note'), (330, 'P')]), line(112, [(50, 'Alpha'), (200, 'first visit'), (330, 'ns')]),
      line(124, [(50, 'Beta'), (200, 'second visit'), (330, '0.02')]), line(140, [(50, 'Gamma'), (200, 'third visit'), (330, 'na')]),
      line(152, [(50, 'Delta'), (200, 'Fourth visit'), (330, '0.04')])]
B7G = [rule(109.5), rule(133), rule(161)]


SLW = [line(100, [(50, 'Parameter'), (200, 'Mean'), (330, 'SD')]), line(112, [(50, 'Recession')]),
       line(124, [(58, 'Test'), (200, '2.68'), (330, '1.63')]), line(136, [(58, 'Control'), (200, '2.31'), (330, '1.52')]),
       line(148, [(58, 't'), (265, '0.692')]), line(160, [(58, 'P'), (265, '0.25')]), line(176, [(50, 'Gingiva')]),
       line(188, [(58, 'Test'), (200, '3.81'), (330, '1.95')]), line(200, [(58, 'Control'), (200, '3.31'), (330, '1.81')]),
       line(212, [(58, 't'), (265, '0.856')]), line(224, [(58, 'P'), (265, '0.10')])]
SLWG = [rule(109), rule(171), rule(233)]

D7L = [line(100, [(50, 'Interventions'), (200, 'Outcomes'), (350, 'Ranking')]),
       line(112, [(50, 'Control: flap'), (200, 'Depth reduction'), (350, '3')]),
       line(124, [(50, 'Test: flap and acid'), (200, 'C: 3.07')]), line(136, [(200, 'T: 3.15')]),
       line(148, [(200, 'Attachment gain')]), line(160, [(200, 'C: 1.30')]), line(172, [(200, 'T: 1.32')]),
       line(188, [(50, 'Control: graft'), (200, 'Coverage'), (350, '4')])]
D7LG = [rule(109), rule(183), rule(197)]


class AuditProbes(unittest.TestCase):
    def test_2d_small_letter_leftmost_text_with_values_stays_in_its_row_under_slw3(self):
        """2d (TW3): off, 't' joins the leftmost cell above; with SLW3 it is its own row's leftmost text"""
        self.assertIn('Control t', [r[0] for r in rows(grid(SLW, G=SLWG))])
        r = rows(grid(SLW, ('SLW3',), G=SLWG))
        self.assertNotIn('Control t', [x[0] for x in r])
        self.assertIn('t', [x[0] for x in r])

    def test_2d_label_line_under_a_d7_value_line_is_its_own_line_under_d7l(self):
        """2d (TW7): off, the label line is glued to the value line above it; with D7L it is a line of its own"""
        self.assertIn('T: 3.15 Attachment gain', [x[1] for x in rows(grid(D7L, G=D7LG))])
        self.assertIn('Attachment gain', [x[1] for x in rows(grid(D7L, ('D7L',), G=D7LG))])

    def test_p_tw17a_two_line_entries_are_no_text_region_under_tw17k3(self):
        """P-TW17a (2a): off, each entry is a 'TW17 text region'; with TW17K3 no boundary is decided by the region check"""
        off = [x['marks'] for x in grid(TW17A)['cellrows']]
        on = [x['marks'] for x in grid(TW17A, ('TW17K3',))['cellrows']]
        self.assertIn(['TW17 text region'], off)
        self.assertNotIn(['TW17 text region'], on)

    def test_p_tw5_centre_set_label_takes_the_line_above_under_tw5c(self):
        """P-TW5 (2c): the centre-set label's row holds the line above it and the line below it"""
        self.assertEqual(rows(grid(TW5))[1], ['', 'lesions seen on', 'mild'])
        self.assertEqual(rows(grid(TW5, ('TW5C',)))[1:], [['Gingiva', 'lesions seen on both arches', 'mild'],
                                                         ['Palate', 'no lesions on either side', 'none'],
                                                         ['Tongue', 'ulcers on the tip', 'severe']])

    def test_p_tw7b_bracketed_value_lines_are_decided_under_tw7b(self):
        """P-TW7b (2c): off, a boundary stays undecided; on, every boundary is decided and the spreads keep their values"""
        self.assertFalse(grid(TW7B)['decided'])
        g = grid(TW7B, ('TW7B',))
        self.assertTrue(g['decided'])
        self.assertEqual(rows(g)[1], ['Interleukin', '1.20 (0.40)', '2.30 (0.50)'])

    def test_p_tw1c_bracket_line_joins_the_entry_leftmost_text_under_tw1e(self):
        """P-TW1c (2c): the bracket line joins 'Interleukin', not the sub-row's empty leftmost cell"""
        self.assertEqual(rows(grid(TW1C))[2][0], '(pg/ml)')
        r = rows(grid(TW1C, ('TW1E',)))
        self.assertEqual(r[1][0], 'Interleukin (pg/ml)')
        self.assertEqual(r[2], ['', 'Day seven', '1.50'])

    def test_p_b7_line_holding_its_own_number_opens_a_row_under_b7any(self):
        """P-B7 (2c): 'Delta | Fourth visit | 0.04' holds its own number: a row of its own"""
        self.assertEqual(rows(grid(B7, G=B7G))[-1][0], 'Gamma Delta')
        self.assertEqual(rows(grid(B7, ('B7ANY',), G=B7G))[-1], ['Delta', 'Fourth visit', '0.04'])



CI = [line(100, [(50, 'Stage'), (150, 'OR [95% CI]'), (300, 'P')])] + [
    line(112 + 12 * i, [(50, a), (150, v), (300, q)]) for i, (a, v, q) in enumerate(
        [('First', '1.46 [1.20-1.79]', '0.01'), ('Second', '0.70 [0.48-1.03]', '0.07'), ('Third', '1.29 [1.09-1.51]', '0.02'),
         ('Fourth', '1.39 [1.10-1.76]', '0.01'), ('Fifth', '1.35 [1.05-1.74]', '0.02')])]
AUTH = [line(100, [(50, 'Study'), (200, 'Design'), (330, 'N')])] + [
    line(112 + 12 * i, [(50, a), (200, d), (330, q)]) for i, (a, d, q) in enumerate(
        [('16. Hickman et al.,', 'RCT', '40'), ('17. McCracken et al.,', 'cohort', '52'), ('18. McCracken et al.,', 'RCT', '12'),
         ('19. Brown and Smith,', 'series', '30'), ('20. Green et al.,', 'RCT', '22')])]
DENMARK = [line(100, [(50, 'Study'), (200, 'Findings')]), line(112, [(50, 'Nielsen et al.'), (200, 'Adult patients presenting for')]),
           line(124, [(50, 'Denmark'), (200, 'treatment were examined')]), line(136, [(50, 'Olsen et al.'), (200, 'Children were examined')]),
           line(148, [(50, 'Norway'), (200, 'at school by dentists')])]
GENDER = [line(100, [(50, 'Variable'), (200, 'Test'), (300, 'Control')]), line(112, [(50, 'Age'), (200, '41.2'), (300, '40.8')]),
          line(124, [(50, 'Gender')]), line(136, [(58, 'Female'), (200, '10'), (300, '12')]), line(148, [(58, 'Male'), (200, '20'), (300, '18')]),
          line(160, [(50, 'Smokers'), (200, '5'), (300, '6')])]


class TW21TW22TW23(unittest.TestCase):
    def test_picture_42_kind_value_and_bracketed_range_one_cell_under_tw22(self):
        """TW21/TW22: a value and its bracketed range, a word space apart, are one cell; the line between is dropped"""
        self.assertEqual(rows(grid(CI))[1][1:3], ['1.46', '[1.20-1.79]'])
        r = rows(grid(CI, ('TW22', 'TW22D')))
        self.assertEqual(r[1], ['First', '1.46 [1.20-1.79]', '0.01'])
        self.assertEqual(r[0], ['Stage', 'OR [95% CI]', 'P'])

    def test_picture_64_kind_author_names_stay_one_cell_under_tw22(self):
        """TW22: a numbered author entry cut at a word space by a column line stays one cell"""
        r = rows(grid(AUTH, ('TW22', 'TW22D')))
        self.assertEqual(r[2], ['17. McCracken et al.,', 'cohort', '52'])

    def test_clear_gap_columns_kept_under_tw22(self):
        """TW22: lines that stand in clear gaps stay (the Stage, OR and P columns are kept)"""
        self.assertEqual(len(rows(grid(CI, ('TW22', 'TW22D')))[0]), 3)

    def test_denmark_table_of_tw16_with_d5(self):
        """TW16/TW23: with the sentence check (form D5) the Denmark lines stay in their entries"""
        g = c.overlay_grid(ov.fit(DENMARK, [], K), DENMARK, [0], [], K, frozenset(CLUES + ('D5',)))
        self.assertEqual(rows(g)[1:], [['Nielsen et al. Denmark', 'Adult patients presenting for treatment were examined'],
                                       ['Olsen et al. Norway', 'Children were examined at school by dentists']])

    def test_group_label_with_two_indented_value_lines_stays_two_rows(self):
        """TW23: 'Female' and 'Male', indented under 'Gender' with values of their own, are two rows (also with D5)"""
        for extra in ((), ('D5',)):
            g = c.overlay_grid(ov.fit(GENDER, [], K), GENDER, [0], [], K, frozenset(CLUES + extra))
            self.assertIn(['Female', '10', '12'], rows(g)); self.assertIn(['Male', '20', '18'], rows(g))


AR20 = [line(100, [(50, 'Property'), (250, 'Dental plaque example')]),
        line(112, [(50, 'Protection from host,'), (250, 'Production of polymers; protection from')]),
        line(122, [(50, 'dessication, etc.'), (250, 'phagocytosis')]),
        line(132, [(50, 'Neutralization'), (250, '\u03b2-lactamase production by cells')]),
        line(142, [(50, 'Cell signalling'), (250, 'Production of CSP, AI-2, etc.;')]),
        line(152, [(50, 'Heterogeneity'), (250, 'pH and O2 gradients; co-adhesion')]),
        line(162, [(50, 'Habitat range'), (250, 'Obligate anaerobes in plaque')])]
COUNTRY = [line(100, [(50, 'Country'), (200, 'N'), (300, 'Mean')]), line(112, [(50, 'Denmark'), (200, '40'), (300, '1.2')]),
           line(124, [(50, 'Norway'), (200, '52'), (300, '1.4')]), line(136, [(50, 'Sweden'), (200, '33'), (300, '1.1')]),
           line(148, [(50, 'Finland'), (200, '28'), (300, '1.3')])]


def grid_d5(t, flags):
    old = c.R8_CLUE_FLAGS
    try:
        c.R8_CLUE_FLAGS = frozenset(flags)
        return c.overlay_grid(ov.fit(t, [], K), t, [0], [], K, frozenset(CLUES + ('D5',)))
    finally:
        c.R8_CLUE_FLAGS = old


class TW24TW25(unittest.TestCase):
    WANT = [['Protection from host, dessication, etc.', 'Production of polymers; protection from phagocytosis'],
            ['Neutralization', '\u03b2-lactamase production by cells'], ['Cell signalling', 'Production of CSP, AI-2, etc.;'],
            ['Heterogeneity', 'pH and O2 gradients; co-adhesion'], ['Habitat range', 'Obligate anaerobes in plaque']]

    def test_ar20_two_lines_as_drawn_under_ph24_and_tw25s(self):
        """TW24/TW25: with D5, "pH" and the Greek letter are no small-letter starts: a row per entry as the user drew it"""
        self.assertNotEqual(rows(grid_d5(AR20, ()))[1:], self.WANT)
        for fl in (('PH24',), ('TW25S',), ('TW25S', 'TW25C')):
            self.assertEqual(rows(grid_d5(AR20, fl))[1:], self.WANT)

    def test_denmark_table_unchanged_under_tw25(self):
        for fl in ((), ('TW25S',), ('TW25C',), ('TW25S', 'TW25C')):
            self.assertEqual(rows(grid_d5(DENMARK, fl))[1][0], 'Nielsen et al. Denmark')

    def test_tw25c_author_line_stays_under_the_capital_rule(self):
        """TW25 (countries and places only): an author line keeps its capital rule: rows stay as without TW25C"""
        AUTH2 = [line(100, [(50, 'Author'), (200, 'Design'), (330, 'N')]), line(112, [(50, 'Chung et al.'), (200, 'RCT'), (330, '40')]),
                 line(124, [(50, 'Kim et al.'), (200, 'cohort'), (330, '52')]), line(136, [(50, 'Ross and Becker'), (200, 'RCT'), (330, '12')])]
        self.assertEqual(rows(grid_d5(AUTH2, ('TW25C',))), rows(grid_d5(AUTH2, ())))
        self.assertFalse(c.tw25_place('Chung et al.')); self.assertTrue(c.tw25_place('Denmark'))

    def test_d5l_named_pages(self):
        """D5L (reads only how the lower line starts) with PH24: AR20 p7 as drawn, the Denmark table, the Gender page"""
        self.assertEqual(rows(grid_d5(AR20, ('PH24', 'D5L')))[1:], self.WANT)
        self.assertEqual(rows(grid_d5(DENMARK, ('PH24', 'D5L')))[1][0], 'Nielsen et al. Denmark')
        r = rows(grid_d5(GENDER, ('PH24', 'D5L')))
        self.assertIn(['Female', '10', '12'], r); self.assertIn(['Male', '20', '18'], r)

    def test_country_rows_with_values_stay_rows_under_tw25c(self):
        """TW25C: a row that starts with a country name and has values of its own stays a row"""
        for fl in ((), ('TW25C',), ('TW25S', 'TW25C')):
            self.assertEqual(rows(grid_d5(COUNTRY, fl))[1:], [['Denmark', '40', '1.2'], ['Norway', '52', '1.4'], ['Sweden', '33', '1.1'], ['Finland', '28', '1.3']])


if __name__ == '__main__':
    unittest.main()
