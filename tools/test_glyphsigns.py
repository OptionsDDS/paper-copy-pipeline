"""Lane glyphsigns: sign faces, quote marks in numbers, stroke checks, the sign decision, its copy notice, rule 9."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fonts', Path(__file__).with_name('check_fonts.py'))
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)


def silhouette(ink, aspect=1.0):
    """A shape tuple from a set of (x, y) pixels on the 32-pixel grid."""
    ink = set(ink)
    return sum(1 << ((y+4)*40+x+4) for x, y in ink), aspect, len(ink)/1024


def reference_ink(ch):
    mask = fonts.outline_references()[ch][0][0]
    return {(x, y) for y in range(32) for x in range(32) if mask >> ((y+4)*40+x+4) & 1}


def font(name, base='StandardEncoding', order=None, kind='cff'):
    return SimpleNamespace(basefont=name, base=base, cid=False,
                           prog=None if order is None else SimpleNamespace(kind=kind, order=order))


class StrokeTests(unittest.TestCase):
    def test_plus_cross_equals_bar(self):
        plus = silhouette({(x, y) for x in range(32) for y in range(32) if 14 <= x <= 17 or 14 <= y <= 17})
        self.assertTrue(fonts.outline_plus(plus)); self.assertFalse(fonts.outline_cross(plus))
        cross = silhouette({(x, y) for x in range(32) for y in range(32) if abs(x-y) <= 1 or abs(x+y-31) <= 1})
        self.assertTrue(fonts.outline_cross(cross)); self.assertFalse(fonts.outline_plus(cross))
        equals = silhouette({(x, y) for x in range(32) for y in range(32) if 8 <= y <= 11 or 20 <= y <= 23}, 2.5)
        self.assertTrue(fonts.outline_equals(equals)); self.assertFalse(fonts.outline_equals(plus))
        # a dagger's bar sits too high to be a plus
        dagger = silhouette({(x, y) for x in range(32) for y in range(32) if 14 <= x <= 17 or 5 <= y <= 8})
        self.assertFalse(fonts.outline_plus(dagger))
        bar = silhouette({(x, y) for x in range(32) for y in range(32)}, 8.0)
        self.assertEqual(fonts.outline_bar(bar, dict(bounds_em=[.1, .35, .6, .30], advance_em=.7)), '−')
        self.assertIsNone(fonts.outline_bar(bar, dict(bounds_em=[.1, -.03, .6, -.08], advance_em=.7)))   # an underscore
        self.assertIsNone(fonts.outline_bar(bar, None))

    def test_chevron_over_a_straight_or_slanted_stroke(self):
        chevron = reference_ink('<')
        upper = {(x, int(y*21/31)) for x, y in chevron}
        straight = upper | {(x, y) for x in range(32) for y in (27, 28, 29)}
        self.assertEqual(fonts.outline_comparison(silhouette(straight), fonts.outline_references()), '≤')
        slanted = upper | {(x, 24+x//8) for x in range(32)} | {(x, 25+x//8) for x in range(32)}
        self.assertEqual(fonts.outline_comparison(silhouette(slanted), fonts.outline_references()), '≤')
        mirrored = {(31-x, y) for x, y in straight}
        self.assertEqual(fonts.outline_comparison(silhouette(mirrored), fonts.outline_references()), '≥')
        # a plus over a bar is not a comparison sign, nor is a lone chevron
        self.assertIsNone(fonts.outline_comparison(silhouette(upper), fonts.outline_references()))
        self.assertIsNone(fonts.outline_comparison(silhouette({(x, y) for x in range(32) for y in range(32)
                                                               if 14 <= x <= 17 or 10 <= y <= 13 or y >= 27}),
                                                   fonts.outline_references()))


class SelectionTests(unittest.TestCase):
    def test_sign_faces_by_name_and_by_symbolic_glyph_names(self):
        for name in ('KELELH+WPi-One', 'MathematicalPi-One', 'SymbolMT', 'WTimesGreekSF-Two', 'AdvPi3', 'MT-Extra'):
            self.assertEqual(fonts.sign_face(font(name)), 'sign face', name)
        for name in ('MLFPLA+Utopia-Italic', 'Utopia-Regular', 'Pilgrim', 'TimesNRMT', 'Capitals'):
            self.assertIsNone(fonts.sign_face(font(name)), name)
        symbolic = font('ABCDEF+HouseSF-Two', base='builtin', order=['.notdef', 'infinity', 'plusminus', 'pi', 'integral', 'ordfeminine', 'Omega', 'questiondown'])
        self.assertEqual(fonts.sign_face(symbolic), 'symbolic encoding')
        self.assertIsNone(fonts.sign_face(font('ABCDEF+HouseSF-One', base='builtin', order=['.notdef', 'm', 'plusminus'])))
        self.assertIsNone(fonts.sign_face(font('ABCDEF+HouseSF-Two', base='StandardEncoding', order=['.notdef', 'plusminus'])))
        self.assertIsNone(fonts.sign_face(font('ABCDEF+HouseSF-Two', base='builtin', order=['.notdef', 'plusminus'], kind='truetype')))
        self.assertIsNone(fonts.sign_face(font('ABCDEF+HouseSF-Two', base='builtin', order=['.notdef'])))

    def test_quote_marks_in_numbers(self):
        for text, offset in (('25”4', 2), ('»26', 0), ('4¿ per', 1), ('(„0.25', 1), ('x¿2', 1), ('in 2001” now', 7)):   # selection only: a real quote keeps its own silhouette
            self.assertTrue(fonts.quote_in_number(text, offset), text)
        for text, offset in (('25.4', 2), ('the ”gold”', 4), ('a ‘b’ c', 2), ('2,000', 1)):
            self.assertFalse(fonts.quote_in_number(text, offset), text)


class DecisionTests(unittest.TestCase):
    def test_signs_by_strokes_and_by_templates(self):
        pm = {(x, y) for x in range(32) for y in range(32) if 14 <= x <= 17 and y < 23 or 10 <= y <= 13 or y >= 29}
        self.assertTrue(fonts.outline_plus_minus(silhouette(pm, .9)))
        self.assertEqual(fonts.sign_outline_decision('”', {'±': .53, '†': .46}, silhouette(pm, .9)), ('replaced', '±'))
        self.assertEqual(fonts.sign_outline_decision('”', {'±': .53, '†': .46}), ('rejected', '�'))   # no strokes: below the floor
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .53, '†': .46}, silhouette(pm, .9)), ('confirmed', '±'))
        self.assertEqual(fonts.sign_outline_decision('.', {'#': .66, '¶': .41, '.': .33}), ('replaced', '#'))
        self.assertEqual(fonts.sign_outline_decision('O', {'.': .98, '•': .97, 'O': .71}), ('replaced', '•'))
        self.assertEqual(fonts.sign_outline_decision('.', {'.': .98, '•': .97, 'O': .71}), ('confirmed', '.'))   # inside the family
        self.assertEqual(fonts.sign_outline_decision('x', {'×': .60, 'x': .45}), ('confirmed', 'x'))
        self.assertEqual(fonts.sign_outline_decision('¿', {'×': .60, 'x': .45, '|': .41}), ('replaced', '×'))
        self.assertEqual(fonts.sign_outline_decision('a', {'α': .60, 'a': .40, 'b': .30}), ('replaced', 'α'))
        self.assertEqual(fonts.sign_outline_decision('a', {'α': .60, 'a': .45}), ('confirmed', 'a'))   # margin under .20, own shape kept
        self.assertEqual(fonts.sign_outline_decision(',', {'<': .59, '(': .52, ',': .11}), ('rejected', '�'))   # runner-up too close
        self.assertEqual(fonts.sign_outline_decision(',', {'<': .59, '(': .31, ',': .11}), ('replaced', '<'))
        self.assertEqual(fonts.sign_outline_decision('/', {'@': .53, '®': .40, '/': .09}), ('rejected', '�'))   # @ is no sign of the set
        self.assertEqual(fonts.sign_outline_decision('C', {'©': .77, '®': .56, 'C': .41}), ('replaced', '©'))
        self.assertEqual(fonts.sign_outline_decision('m', {'μ': .66, 'µ': .65, 'g': .54, 'm': .36}), ('replaced', 'μ'))
        # a claimed sign or Greek letter that no sign replaces stays as claimed (AI05 Δ, AG10 ⁎, AH10 ∥ and ∙)
        self.assertEqual(fonts.sign_outline_decision('Δ', {'A': .50, '±': .30}), ('unchanged', 'Δ'))
        self.assertEqual(fonts.sign_outline_decision('∥', {'‖': .70, '|': .40}), ('confirmed', '∥'))
        self.assertEqual(fonts.sign_outline_decision('⁎', {'*': .60, '•': .40}), ('confirmed', '⁎'))
        self.assertEqual(fonts.sign_outline_decision('∙', {'.': .98, '•': .97}), ('confirmed', '∙'))
        bar = silhouette({(x, y) for x in range(32) for y in range(32)}, 8.0); geometry = dict(bounds_em=[.1, .35, .6, .30], advance_em=.7)
        self.assertEqual(fonts.sign_outline_decision('–', {'_': .98, '−': .90, '-': .82}, bar, geometry), ('confirmed', '–'))   # an en dash stays
        self.assertEqual(fonts.sign_outline_decision('»', {'_': .98, '−': .90, '-': .82}, bar, geometry), ('replaced', '−'))

    def test_first_pass_decides_sign_faces_and_lists_once_per_paper(self):
        shape = silhouette({(x, y) for x in range(32) for y in range(32) if 2 <= y < 10}, .67)
        refs = {'#': [('hash',)], '.': [('dot',)], '¶': [('pilcrow',)]}
        scores = {'hash': .66, 'dot': .33, 'pilcrow': .41}
        runs = [dict(page=1, id='run:1', source='.17 explorer', crop_xywh=[0, 0, 60, 10], font_glyphs=[
                     dict(font='ABCDEF+WPi-One', source_code=46, before='.', offset=0, char_id=0, box_px=[0, 0, 10, 10])]),
                dict(page=1, id='run:2', source='Study . teeth', crop_xywh=[0, 20, 60, 10], font_glyphs=[
                     dict(font='ABCDEF+WPi-One', source_code=46, before='.', offset=6, char_id=1, box_px=[0, 0, 10, 10])])]
        doc = SimpleNamespace(fonts={1: font('ABCDEF+WPi-One', base='builtin', order=['.notdef', 'period'])})
        with patch.object(fonts, 'outline_references', return_value=refs), \
             patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', return_value=shape), \
             patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: scores[b[0]]):
            result = fonts.verify_outlines(doc, runs)
        self.assertEqual(result['selected'], {'sign face': 1})
        record = result['records'][0]
        self.assertEqual((record['before'], record['after'], record['status'], record['sign_claim']), ('.', '#', 'replaced', 'sign face'))
        self.assertEqual(len(record['places']), 2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'page-01.json'; path.write_text('{}')
            saved = dict(page=1, fonts={'ABCDEF+WPi-One': {}}, elements=[
                dict(id='run:1', kind='text', text='.17 explorer', char_ids=[0]+list(range(2, 13))),
                dict(id='run:2', kind='text', text='Study . teeth', char_ids=[13, 14, 15, 16, 17, 18, 1, 19, 20, 21, 22, 23, 24])])
            chars = [dict(text='.', font='ABCDEF+WPi-One', source_code=46), dict(text='.', font='ABCDEF+WPi-One', source_code=46)]
            chars += [dict(text=ch, font='T', source_code=65) for ch in '17 explorer'] + [dict(text=ch, font='T', source_code=65) for ch in 'Study  teeth']
            fonts.apply_results({str(path): (path.read_bytes(), saved)}, [
                dict(file=str(path), index=0, page=1, id='run:1', source='.17 explorer', candidates=[],
                     outline_records=[(runs[0]['font_glyphs'][0], record)]),
                dict(file=str(path), index=1, page=1, id='run:2', source='Study . teeth', candidates=[],
                     outline_records=[(runs[1]['font_glyphs'][0], record)])], {})
            page = json.loads(path.read_text())
        self.assertEqual(page['fonts']['ABCDEF+WPi-One']['outline_verification']['46']['sign_claim'], 'sign face')
        page['_table_chars'] = chars
        uncertain = []
        with patch.object(fonts, 'sign_references', return_value=refs):
            fonts.apply_copy([page], uncertain)
        self.assertEqual([e['text'] for e in page['elements']], ['#17 explorer', 'Study # teeth'])
        self.assertEqual(len(uncertain), 1)
        self.assertIn("font ABCDEF+WPi-One, glyph 46 (sign face): text layer '.' printed as '#' by its embedded outline in 2 places on page 1", uncertain[0])

    def test_rejected_quote_mark_is_flagged_not_printed(self):
        shape = silhouette({(x, y) for x in range(32) for y in range(32) if (x+y) % 7 == 0}, 1.0)
        refs = {'±': [('pm',)], '"': [('quote',)]}
        scores = {'pm': .30, 'quote': .20}
        runs = [dict(page=2, id='run:5', source='25”4 teeth', crop_xywh=[0, 0, 60, 10], font_glyphs=[
                     dict(font='ABCDEF+Serif', source_code=186, before='”', offset=2, char_id=2, box_px=[0, 0, 10, 10])])]
        doc = SimpleNamespace(fonts={1: font('ABCDEF+Serif')})
        with patch.object(fonts, 'outline_references', return_value=refs), \
             patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', return_value=shape), \
             patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: scores[b[0]]):
            result = fonts.verify_outlines(doc, runs)
        self.assertEqual(result['selected'], {'quote mark in a number': 1})
        # letters and digits of an opaque-named face, and letters inside words, keep the ordinary checks
        opaque = [dict(page=1, id='run:7', source='x and 5 trials', crop_xywh=[0, 0, 60, 10], font_glyphs=[
            dict(font='ABCDEF+AdvOT1234+20', source_code=3, before='x', offset=0, char_id=0, box_px=[0, 0, 10, 10]),
            dict(font='ABCDEF+AdvOT1234+20', source_code=4, before='5', offset=6, char_id=6, box_px=[0, 0, 10, 10]),
            dict(font='ABCDEF+WPi-One', source_code=9, before='n', offset=3, char_id=3, box_px=[0, 0, 10, 10])])]
        doc = SimpleNamespace(fonts={1: font('ABCDEF+AdvOT1234+20', base='builtin', order=['.notdef', 'C3', 'C4']), 2: font('ABCDEF+WPi-One')})
        with patch.object(fonts, 'outline_references', return_value=refs), patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', return_value=shape), patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: scores[b[0]]):
            self.assertEqual(fonts.verify_outlines(doc, opaque)['selected'], {})

        record = result['records'][0]
        self.assertEqual((record['status'], record['after'], record['sign_claim']), ('rejected', '�', 'quote mark in a number'))
        page = dict(page=2, fonts={'ABCDEF+Serif': {'outline_verification': {'186': dict(
            {k: record[k] for k in ('model', 'font', 'source_code', 'before', 'after', 'status', 'scores', 'outline', 'sign_claim')})}}},
            elements=[dict(id='run:5', kind='text', text='25”4 teeth', char_ids=list(range(10)),
                           font_subs=[dict(offset=2, char_id=2, before='”', font='ABCDEF+Serif', source_code=186,
                                           model=fonts.OUTLINE_MODEL, after='�', status='rejected')])],
            _table_chars=[dict(text=ch, font='ABCDEF+Serif', source_code=186 if ch == '”' else 50) for ch in '25”4 teeth'])
        uncertain = []
        with patch.object(fonts, 'sign_references', return_value=refs):
            fonts.apply_copy([page], uncertain)
        self.assertEqual(page['elements'][0]['text'], '25�4 teeth')
        self.assertIn("glyph 186 (quote mark in a number): text layer '”' is neither that character nor a known sign", uncertain[0])
        self.assertIn('shown as � in 1 place on page 2', uncertain[0])
        # a quote mark whose own silhouette (or its family's) holds is kept
        self.assertEqual(fonts.sign_outline_decision('”', {'"': .62, '±': .30}), ('confirmed', '”'))
        self.assertEqual(fonts.sign_outline_decision('’', {',': .67, '·': .63, "'": .50}), ('confirmed', '’'))   # AI11 "4’-methyl"
        self.assertEqual(fonts.sign_outline_decision('’', {',': .30, '·': .25, "'": .20}), ('rejected', '\ufffd'))



    def test_the_printed_sign_is_the_outline_own_match(self):
        # A filled square whose nearest references are a period and a middle dot is no
        # bullet: the claimed symbol stays as claimed.
        square = {'·': .99, '.': .985, '-': .86, "'": .86, '•': .75, 'O': .55}
        self.assertEqual(fonts.sign_outline_decision('■', square), ('unchanged', '■'))
        # A letter claim whose outline is nearest a Greek letter of the cross family is
        # no multiplication sign: the claim is rejected and flagged.
        chi = {'χ': .76, 'X': .61, 'x': .61, '7': .59, '/': .57, '×': .37, 'w': .24}
        self.assertEqual(fonts.sign_outline_decision('w', chi), ('rejected', '\ufffd'))
        self.assertEqual(fonts.sign_outline_decision('χ', chi), ('confirmed', 'χ'))
        # A sign that clears the floors by its own silhouette is still printed.
        self.assertEqual(fonts.sign_outline_decision('w', dict(chi, **{'×': .78})), ('replaced', '×'))
        self.assertEqual(fonts.sign_outline_decision('O', {'.': .98, '•': .97, '·': .94, 'O': .71}), ('replaced', '•'))
        # A Latin-encoding reading the outline does not confirm is flagged, not kept, and
        # no lookalike's score prints the family sign for it.
        prime = {',': .80, '′': .75, 'I': .69, 'i': .69}
        self.assertEqual(fonts.sign_outline_decision('¢', prime), ('rejected', '\ufffd'))
        self.assertEqual(fonts.sign_outline_decision('¢', dict(prime, I=.60, i=.60)), ('replaced', '′'))

    def test_a_double_quote_drawn_as_two_commas_is_confirmed(self):
        comma = reference_ink(',')
        def squeeze(ink, x0):   # a comma at a third of the width, placed at x0
            return {(x0+x//3, y//2) for x, y in ink}
        pair = silhouette(squeeze(comma, 2) | squeeze(comma, 18), 1.4)
        self.assertTrue(fonts.outline_quote_pair(pair, fonts.sign_references()))
        turned = silhouette({(31-x, 31-y) for x, y in squeeze(comma, 2) | squeeze(comma, 18)}, 1.4)
        self.assertTrue(fonts.outline_quote_pair(turned, fonts.sign_references()))
        low = {'µ': .54, 'H': .53, '"': .30}
        self.assertEqual(fonts.sign_outline_decision('“', low, pair), ('confirmed', '“'))
        self.assertEqual(fonts.sign_outline_decision('“', low), ('rejected', '\ufffd'))   # no outline: as before
        # stacked marks (a plus over a bar, two bars) and one mark are no quote pair
        stacked = silhouette({(x, y) for x in range(32) for y in range(32) if 14 <= x <= 17 and y < 20 or 8 <= y <= 11 or y >= 28})
        self.assertFalse(fonts.outline_quote_pair(stacked, fonts.sign_references()))
        bars = silhouette({(x, y) for x in range(32) for y in range(32) if 8 <= y <= 11 or 20 <= y <= 23}, 2.5)
        self.assertFalse(fonts.outline_quote_pair(bars, fonts.sign_references()))
        self.assertFalse(fonts.outline_quote_pair(silhouette(squeeze(comma, 2)), fonts.sign_references()))
        # two upright strokes side by side: a straight double quote when wide, a parallel sign when tall
        posts = {(x, y) for x in range(32) for y in range(32) if 2 <= x <= 7 or 24 <= x <= 29}
        self.assertTrue(fonts.outline_quote_pair(silhouette(posts, 1.2), fonts.sign_references()))
        self.assertFalse(fonts.outline_quote_pair(silhouette(posts, .4), fonts.sign_references()))
        self.assertFalse(fonts.outline_quote_pair(silhouette(squeeze(comma, 2) | squeeze(comma, 18), .8), fonts.sign_references()))

    def test_text_claims_include_latin_encoding_readings(self):
        for ch in ('a', '.', '”', '„', '¢', '£', '¼', 'þ', '‡', '–'):
            self.assertTrue(fonts.text_claim(ch), ch)
        for ch in ('■', 'χ', 'Δ', '±', '×', '°', '∞', '≤', '∥', '⁎', '∙', '®'):
            self.assertFalse(fonts.text_claim(ch), ch)

    def test_ordinary_decision_still_names_an_arrow_in_a_pi_face(self):
        # AL01: AdvPi2 claims '?' for a thin arrow; the sign set has no arrow, the arrow check does.
        shape = silhouette({(x, y) for x in range(32) for y in range(32) if 15 <= x <= 16}, .5)
        refs = {'?': [('q',)], '↓': [('down',)], '•': [('dot',)]}; scores = {'q': .20, 'down': .50, 'dot': .25}
        runs = [dict(page=2, id='run:60', source='flow ? site', crop_xywh=[0, 0, 60, 10], font_glyphs=[
                     dict(font='ABCDEF+AdvPi2', source_code=63, before='?', offset=5, char_id=5, box_px=[0, 0, 10, 10])])]
        doc = SimpleNamespace(fonts={1: font('ABCDEF+AdvPi2')})
        with patch.object(fonts, 'outline_references', return_value=refs), patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', return_value=shape), patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: scores[b[0]]), \
             patch.object(fonts, 'outline_arrow', return_value='↓'):
            result = fonts.verify_outlines(doc, runs)
            record = result['records'][0]
            self.assertEqual((record['status'], record['after']), ('replaced', '↓'))
            self.assertNotIn('sign_claim', record)
            self.assertEqual(fonts.saved_outline_decision(record), ('replaced', '↓'))

class BlackSquareTests(unittest.TestCase):
    """A solid block a third of an em or more on each side is a black square, whatever the text layer claims."""
    block = silhouette({(x, y) for x in range(32) for y in range(32)}, 1.0)
    large = dict(bounds_em=[.04, .70, .74, .0], advance_em=.78)    # a 0.7-em box on the baseline
    dot = dict(bounds_em=[.08, .11, .19, .0], advance_em=.28)      # a square period

    def test_the_block_is_read_by_its_size(self):
        self.assertEqual(fonts.outline_square(self.block, self.large), '■')
        self.assertIsNone(fonts.outline_square(self.block, self.dot))
        self.assertIsNone(fonts.outline_square(self.block, None))
        self.assertIsNone(fonts.outline_square(silhouette({(x, y) for x in range(32) for y in range(32)}, .2),
                                               dict(bounds_em=[.1, .70, .24, .0], advance_em=.3)))   # a tall bar
        disc = silhouette({(x, y) for x in range(32) for y in range(32) if (x-15.5)**2+(y-15.5)**2 <= 256}, 1.0)
        self.assertIsNone(fonts.outline_square(disc, self.large))   # a bullet is no solid block
        self.assertIsNone(fonts.outline_square(self.block, dict(bounds_em=[.04, .35, .74, .0], advance_em=.78)))   # silhouette and bounds disagree

    def test_letter_claims_become_the_square_in_both_decisions(self):
        scores = {'·': .99, '.': .985, '-': .86, "'": .86, '•': .75, 'n': .64}
        self.assertEqual(fonts.sign_outline_decision('n', scores, self.block, self.large), ('replaced', '■'))
        self.assertEqual(fonts.outline_decision('n', {'n': .64}, shape=self.block, geometry=self.large), ('replaced', '■'))
        self.assertEqual(fonts.outline_decision('7', {'7': .50}, shape=self.block, geometry=self.large), ('replaced', '■'))
        # a bullet or a claimed symbol keeps its claim; a dot-size block is still a period
        self.assertEqual(fonts.sign_outline_decision('•', scores, self.block, self.large), ('confirmed', '•'))
        self.assertEqual(fonts.sign_outline_decision('■', scores, self.block, self.large), ('confirmed', '■'))
        self.assertEqual(fonts.sign_outline_decision('.', scores, self.block, self.dot), ('confirmed', '.'))
        self.assertEqual(fonts.outline_decision('n', {'n': .64}, shape=self.block, geometry=self.dot), ('confirmed', 'n'))
        # a real letter in the same box keeps its claim
        letter = silhouette(reference_ink('n'))
        self.assertEqual(fonts.outline_decision('n', {'n': .95}, shape=letter, geometry=self.large), ('confirmed', 'n'))

    def test_first_pass_replaces_a_one_glyph_face_letter_and_revalidates(self):
        refs = {'n': [('n',)], '.': [('dot',)], '•': [('bullet',)]}; scores = {'n': .64, 'dot': .98, 'bullet': .75}
        face = SimpleNamespace(basefont='ABCDEF+OpaqueOne', base='WinAnsiEncoding', cid=False,
                               prog=SimpleNamespace(kind='cff', order=['.notdef', 'n']),
                               bbox=lambda code: (40, 700, 740, 0), width=lambda code: 780)
        runs = [dict(page=8, id='run:9', source='providers. n', crop_xywh=[0, 0, 60, 10], font_glyphs=[
                     dict(font='ABCDEF+OpaqueOne', source_code=110, before='n', offset=11, char_id=11, box_px=[0, 0, 10, 10])])]
        doc = SimpleNamespace(fonts={1: face})
        with patch.object(fonts, 'outline_references', return_value=refs), patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', return_value=self.block), \
             patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: scores[b[0]]):
            record = fonts.verify_outlines(doc, runs)['records'][0]
            self.assertEqual((record['status'], record['after']), ('replaced', '■'))
            self.assertEqual(record['geometry']['bounds_em'], [.04, .7, .74, 0])
            self.assertEqual(fonts.saved_outline_decision(record), ('replaced', '■'))
            self.assertIn("text layer 'n' corrected to '■' by embedded outline",
                          fonts.outline_notice(dict(page=8), dict(id='run:9', text='providers. n'),
                                               dict(record, font='ABCDEF+OpaqueOne', offset=11)))


class RuleNineTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).with_name('secondpass')
        sys.path.insert(0, str(folder))
        self.r09 = importlib.import_module('r09_glyphs')

    def tearDown(self):
        sys.path.pop(0)

    def test_rule_nine_sizes_solid_blocks_like_the_first_pass(self):
        face = SimpleNamespace(bbox=lambda code: (40, 700, 740, 0), width=lambda code: 780)
        with patch.object(fonts, 'outline_shape', return_value=BlackSquareTests.block):
            status, after, native, best = self.r09.sign_decision(fonts, {'F': [face]}, dict(font='F', source_code=110), 'n')
        self.assertEqual((status, after), ('replaced', '■'))

    def test_sign_claims_are_selected_and_listed_with_counts(self):
        wpi = font('ABCDEF+WPi-One'); serif = font('ABCDEF+Serif')
        table = {'ABCDEF+WPi-One': [wpi], 'ABCDEF+Serif': [serif]}
        chars = [dict(text='2', font='ABCDEF+Serif', source_code=50), dict(text='”', font='ABCDEF+Serif', source_code=186),
                 dict(text='4', font='ABCDEF+Serif', source_code=52), dict(text='.', font='ABCDEF+WPi-One', source_code=46),
                 dict(text='a', font='ABCDEF+Serif', source_code=97), dict(text='’', font='ABCDEF+Serif', source_code=39)]
        self.assertTrue(self.r09.sign_claim(fonts, table, chars, 1, chars[1], '”'))
        self.assertTrue(self.r09.sign_claim(fonts, table, chars, 3, chars[3], '.'))
        self.assertFalse(self.r09.sign_claim(fonts, table, chars, 4, chars[4], 'a'))
        self.assertFalse(self.r09.sign_claim(fonts, table, chars, 5, chars[5], '’'))
        # The character list holds no word spaces: the element text decides adjacency.
        quote = font('ABCDEF+Serif'); table = {'ABCDEF+Serif': [quote]}
        cs = [dict(text=ch, font='ABCDEF+Serif', source_code=ord(ch)) for ch in 'in19“word”'] + \
             [dict(text=ch, font='ABCDEF+Serif', source_code=ord(ch)) for ch in 'end.”19']
        page = dict(elements=[dict(kind='text', text='in 19 “word”', char_ids=list(range(10))),
                              dict(kind='text', text='end.”', char_ids=list(range(10, 15))),
                              dict(kind='text', text='19', char_ids=[15, 16])])
        texts = self.r09.element_texts(fonts, page, cs)
        self.assertEqual(texts[4], ('in 19 “word”', 6))
        self.assertTrue(self.r09.sign_claim(fonts, table, cs, 4, cs[4], '“'))            # the bare list would select it
        self.assertFalse(self.r09.sign_claim(fonts, table, cs, 4, cs[4], '“', texts[4]))
        self.assertFalse(self.r09.sign_claim(fonts, table, cs, 14, cs[14], '”', texts[14]))
        number = [dict(text=ch, font='ABCDEF+Serif', source_code=ord(ch)) for ch in '25”4']
        texts = self.r09.element_texts(fonts, dict(elements=[dict(kind='text', text='25”4', char_ids=[0, 1, 2, 3])]), number)
        self.assertTrue(self.r09.sign_claim(fonts, table, number, 2, number[2], '”', texts[2]))
        paper = SimpleNamespace(pdf='x.pdf', notes_text='- font ABCDEF+WPi-One, glyph 46 (sign face): text layer')
        places = {('ABCDEF+WPi-One', 46, '.'): [(2, 'rephine, .8 round', '#', .33, .66)],
                  ('ABCDEF+Serif', 186, '”'): [(3, '25”4', '�', None, .53), (4, '33”34', '�', None, .53)]}
        with patch.object(self.r09, 'private_use', return_value=[]), patch.object(self.r09, 'outlines', return_value=places):
            findings, stats = self.r09.check(paper)
        self.assertEqual(len(findings), 1)
        self.assertIn("font ABCDEF+Serif, glyph 186: claimed '”' but its outline is neither that nor a known sign (similarity unmeasured, best 0.53) in 2 place(s)", findings[0]['message'])


if __name__ == '__main__':
    unittest.main()
