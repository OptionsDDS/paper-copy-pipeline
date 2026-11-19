"""Lane r5-line (round 5): O20 left-edge order inside a line, O21 raised and lowered characters stacked on one letter.

Synthetic characters only (no paper text): the boxer's line and run builder (lines_and_runs) is given glyph boxes,
origins, sizes, fonts and paint order as the reading layer gives them."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r5line_boxer', ROOT / 'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)


class Glyphs:
    def __init__(self):
        self.cs = []

    def put(self, text, x, base, size=10.0, font='Roman', width=None, adv=None, top=None, bottom=None):
        """one glyph per character, left to right from x; returns the pen position after the last one"""
        for ch in text:
            w = width if width is not None else (0.25 * size if ch == ' ' else 0.5 * size)
            if ch != ' ':
                n = len(self.cs)
                self.cs.append(dict(text=ch, x0=x, x1=x + w, y0=base - 0.7 * size if top is None else top,
                                    y1=base + 0.2 * size if bottom is None else bottom, origin=(x, base),
                                    size=size, font=font, angle=0, paint_order=(n, 0), id=n,
                                    adv_x1=x + (adv if adv is not None else w), adv_y1=base))
            x += w
        return x

    def runs(self, bars=None):
        to_read, baseline_v = boxer.frame(0)
        lines, runs, _ = boxer.lines_and_runs([dict(c) for c in self.cs], 0, [], to_read, baseline_v, bars=bars)
        return [''.join(c['text'] for c in cs) for _, cs in runs]


class LeftEdgeOrder(unittest.TestCase):
    def test_italic_overhang_over_a_roman_bracket_stays_in_place(self):
        g = Glyphs()
        x = g.put('grown (', 0, 100)
        x = g.put('vitro', x, 100, font='Italic')
        x = g.put(')', x - 2.0, 100, width=3.0)          # the bracket set under the lean of the italic o
        x = g.put(' for two days', x, 100)
        runs = g.runs()
        self.assertEqual(len(runs), 1, runs)
        self.assertEqual(runs[0], 'grown(vitro)fortwodays')

    def test_two_texts_drawn_over_one_another_keep_their_font_layers(self):
        g = Glyphs()
        x = g.put('value was ', 0, 100)
        g.put('lower', x, 100, font='Roman', width=4.0)
        g.put('upper', x + 0.3, 100, font='Bold', width=4.0)   # a second word over the first, offset a little
        runs = g.runs()
        self.assertNotIn('lluoppweerr', ''.join(runs))
        self.assertTrue(any('upper' in r for r in runs), runs)

    def test_circumflex_over_its_letter_stays_between_its_neighbours(self):
        # (the run text built in _box_elements then joins it without a word space on either side)
        g = Glyphs()
        x = g.put('Ho', 0, 100)
        g.put('ˆ', x - 4.0, 100, font='Accent', width=3.0, adv=3.0, top=91.0, bottom=93.5)   # drawn back over the o
        g.put('te and more words here', x + 1.5, 100)
        runs = g.runs()
        self.assertTrue(runs[0].startswith('Hoˆte'), runs)


class StackedScripts(unittest.TestCase):
    def line(self):
        g = Glyphs()
        x = g.put('component ', 0, 100)
        x = g.put('y', x, 100, font='Greek')
        g.put('LW', x, 96.0, size=7.0)       # raised group on y
        g.put('s', x, 103.0, size=7.0)       # lowered group under it, same left edge
        g.put(' and the next words', x + 7.5, 100)
        return g

    def test_lowered_and_raised_groups_are_each_whole_after_their_letter(self):
        runs = self.line().runs()
        text = ''.join(runs)
        self.assertIn('ysLWandthe', text)
        self.assertNotIn('yLsW', text)

    def test_one_tier_only_keeps_left_edge_order(self):
        g = Glyphs()
        x = g.put('earlier work', 0, 100)
        x = g.put('12', x, 96.0, size=7.0)
        x = g.put(' and the gas CO', x, 100)
        x = g.put('2', x, 103.0, size=7.0)
        g.put(' was low', x, 100)
        self.assertEqual(''.join(g.runs()), 'earlierwork12andthegasCO2waslow')

    def test_a_small_type_line_beside_large_type_does_not_fold_as_a_script(self):
        # a column of small type at the left, a larger line at the right on nearly the same baseline: not a script
        g = Glyphs()
        g.put('Sao Paulo, Brazil', 0, 103.0, size=7.0)
        g.put('mechanical debridement of the sites', 150, 100, size=10.0)
        g.put('more small words', 300, 96.0, size=7.0)
        runs = g.runs()
        self.assertIn('SaoPaulo,Brazil', ''.join(runs).replace(' ', ''))


class HoldBackShapes(unittest.TestCase):
    def test_a_fraction_with_a_drawn_bar_is_not_stacked(self):
        g = Glyphs()
        x = g.put('a change of ', 0, 100)
        g.put('12', x, 96.0, size=7.0)
        g.put('25', x, 103.0, size=7.0)
        g.put(' of the base value', x + 8.0, 100)
        bar = [{'kind': 'rule', 'box_px': [x, 98.0, x + 7.5, 98.4]}]
        self.assertNotIn('2512', ''.join(g.runs(bars=bar)))      # without the bar the tiers would be written 25 then 12
        self.assertIn('2512', ''.join(g.runs(bars=[])))

    def test_a_short_line_in_the_line_size_is_not_folded_as_a_script(self):
        # the short last line of a reference entry (digits, a dash, a full stop), on its own baseline, in the same size
        g = Glyphs()
        g.put('the readings and the method', 0, 100, size=7.0)
        g.put('123-130.', 8, 108, size=7.0)
        g.put('3. Grey F, Stone G. A third study of the readings', 0, 116, size=7.0)
        runs = g.runs()
        self.assertIn('123-130.', runs)


    def test_a_smaller_short_line_a_full_pitch_away_is_not_folded(self):
        # memo line-holdback-2: digits at 0.74 of the line size, on their own baseline a full line spacing from the next
        # line, no height overlap with it: a line, not a script
        g = Glyphs()
        g.put('in a larger group of samples kept for two days', 0, 100, size=9.5)
        g.put('123-130.', 8, 108.6, size=7.0)
        g.put('13. Grey F, Stone G. A third study of the readings', 0, 117.2, size=9.5)
        self.assertIn('123-130.', g.runs())


class FirstPageCheck(unittest.TestCase):
    def run_check(self, lane, base):
        import json, os, tempfile
        spec2 = importlib.util.spec_from_file_location('r5front', ROOT / 'tools/r5_frontcheck.py')
        mod = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'r5base'))
            for where, a in ((d, lane), (os.path.join(d, 'r5base'), base)):
                json.dump(a, open(os.path.join(where, 'authors.json'), 'w'))
                json.dump({'who': where == d and 'lane' or 'base'}, open(os.path.join(where, 'page-01.json'), 'w'))
            open(os.path.join(d, 'r5base-page-01.json'), 'w').write('{}')
            mod.main(d)
            kept = json.load(open(os.path.join(d, 'page-01.json')))['who']
            self.assertFalse(os.path.exists(os.path.join(d, 'r5base')) or os.path.exists(os.path.join(d, 'r5base-page-01.json')))
            return kept

    def test_fewer_authors_keeps_the_build_without_the_lane(self):
        a = {'title': {'text': 'T'}, 'authors': [1, 2, 3], 'affiliations': [1]}
        b = {'title': {'text': 'T'}, 'authors': [1, 2, 3, 4], 'affiliations': [1]}
        self.assertEqual(self.run_check(a, b), 'base')

    def test_same_front_matter_keeps_the_lane_build(self):
        a = {'title': {'text': 'T'}, 'authors': [1, 2], 'affiliations': [1]}
        self.assertEqual(self.run_check(a, dict(a)), 'lane')


if __name__ == '__main__':
    unittest.main()
