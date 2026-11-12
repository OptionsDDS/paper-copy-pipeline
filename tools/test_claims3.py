"""Lane claims3: a text typeface is not a symbol face because of its name.
The SIGN_FACE name is only a prior: a face named like a sign face whose used codes form running text (distinct
Latin letters inside words set wholly in it, or distinct digits inside numbers set wholly in it) keeps the
ordinary checks; a claim a sign clearly beats is still replaced; real sign faces are decided as before.
All faces, names and texts here are synthetic.
/usr/bin/python3 -I tools/test_claims3.py"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fonts', TOOLS/'check_fonts.py')
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)


def faces_of(text, spans):
    """(text, {offset: face}) from (start, end, face) spans."""
    return text, {i: face for start, end, face in spans for i in range(start, end) if not text[i].isspace()}


class Measure(unittest.TestCase):
    def test_text_face_named_symbol_sets_running_text(self):
        line = 'Smith JA, Jones B. Bone fill 12 months. 1998;45:301'
        use = fonts.face_text_use([faces_of(line, [(0, len(line), 'XYZABC+HouseSymbol-Book')])])
        letters, digits = use['XYZABC+HouseSymbol-Book']
        self.assertGreaterEqual(letters, fonts.TEXT_USE_LETTERS)
        self.assertGreaterEqual(digits, fonts.TEXT_USE_DIGITS)
        self.assertTrue(fonts.running_text(use['XYZABC+HouseSymbol-Book']))

    def test_digits_only_text_face_is_running_text(self):
        # reference numbers and page numbers alone, set in the text face
        line = '10. 11. 12. 23 345 46'
        use = fonts.face_text_use([faces_of(line, [(0, len(line), 'HouseSymbol')])])
        self.assertTrue(fonts.running_text(use['HouseSymbol']))

    def test_pi_face_codes_between_body_glyphs_are_no_running_text(self):
        # a Pi face claiming '5' for '=', ',' for '<', 'A' and 'C' for signs, beside body digits and letters
        line = 'n 5 20, P , 0.05; A C; Fiii'
        spans = [(0, len(line), 'BODY'), (2, 3, 'HousePi-One'), (8, 9, 'HousePi-One'), (17, 18, 'HousePi-One'), (19, 20, 'HousePi-One'),
                 (23, 26, 'HousePi-One')]   # 'iii' after a body 'F': one distinct letter in a word, not wholly the face's
        use = fonts.face_text_use([faces_of(line, spans)])
        self.assertFalse(fonts.running_text(use.get('HousePi-One')))
        # a word wholly in the Pi face but of one repeated letter (AQ14-like 'i'): one distinct letter
        use = fonts.face_text_use([faces_of('xiii', [(0, 1, 'BODY'), (1, 4, 'HousePi-One')])])
        self.assertFalse(fonts.running_text(use.get('HousePi-One')))
        # adjacent Pi digits claimed for signs ("+=" claimed "15") are two distinct digits, not four
        use = fonts.face_text_use([faces_of('a 15 b 15', [(0, 9, 'BODY'), (2, 4, 'HousePi-One'), (7, 9, 'HousePi-One')])])
        self.assertFalse(fonts.running_text(use.get('HousePi-One')))

    def test_greek_words_do_not_count_as_latin_letters(self):
        use = fonts.face_text_use([faces_of('αβγδ', [(0, 4, 'GreekPi')])])
        self.assertFalse(fonts.running_text(use.get('GreekPi')))


class Decision(unittest.TestCase):
    DIGIT = {'4': .30, 'A': .33, '1': .28, '<': .20}          # a digit of another design: low everywhere

    def test_a_failing_digit_no_sign_beats_is_not_rejected_in_a_text_face(self):
        self.assertEqual(fonts.sign_outline_decision('4', self.DIGIT), ('rejected', '�'))
        self.assertEqual(fonts.sign_outline_decision('4', self.DIGIT, text=True), ('unchanged', '4'))

    def test_a_sign_that_clearly_beats_the_claim_still_replaces(self):
        scores = {'5': .20, '=': .70, '-': .40}
        self.assertEqual(fonts.sign_outline_decision('5', scores, text=True), ('replaced', '='))

    def test_saved_proof_carries_the_text_face(self):
        proof = dict(before='4', scores=self.DIGIT, sign_claim='sign face', text_face=True)
        self.assertEqual(fonts.saved_outline_decision(proof), ('unchanged', '4'))


def glyph(font, code, before, offset, char_id, box):
    return dict(font=font, source_code=code, before=before, offset=offset, char_id=char_id, box_px=box)


def runs_of(lines):
    """Runs from [(text, [(start, end, face)])]; source code = the claimed character's code point."""
    runs = []; cid = 0
    for n, (text, spans) in enumerate(lines):
        gs = []
        for start, end, face in spans:
            for i in range(start, end):
                if text[i].isspace(): continue
                gs.append(glyph(face, ord(text[i]), text[i], i, cid, [i*10, n*20, i*10+9, n*20+10])); cid += 1
        runs.append(dict(page=1+n//4, id=f'run:{n}', source=text, crop_xywh=[0, n*20, 600, 10], font_glyphs=gs))
    return runs


class FirstPass(unittest.TestCase):
    """verify_outlines on synthetic runs: a body face, a Latin text face named like a Symbol face whose digits
    (another design) score low against their references, and a real Pi face claiming '5' for '='."""
    CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=.,;:'

    def run_first_pass(self, lines):
        refs = {ch: [(ch,)] for ch in self.CHARS}
        shapes = {}

        def shape(font, code):
            return shapes.setdefault((font.basefont, code), (0, 1.0 + len(shapes)*1e-6, 0.0))

        def similarity(shape_, ref):
            font, code = next(k for k, v in shapes.items() if v == shape_)
            claim = chr(code)
            if font == 'HousePi-One' and claim == '5': return .70 if ref[0] == '=' else .15   # drawn '='
            if font.endswith('Symbol-Book') and claim.isdigit(): return .30 if ref[0] == claim else .12
            return .90 if ref[0] == claim else .10
        doc = SimpleNamespace(fonts={i: SimpleNamespace(basefont=name, base='StandardEncoding', cid=False, prog=None)
                                     for i, name in enumerate(('BODY', 'XYZABC+HouseSymbol-Book', 'HousePi-One'))})
        with patch.object(fonts, 'outline_references', return_value=refs), \
             patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', side_effect=shape), \
             patch.object(fonts, 'outline_similarity', side_effect=similarity):
            return fonts.verify_outlines(doc, runs_of(lines))

    def test_text_face_named_symbol_prints_its_digits(self):
        sym = 'XYZABC+HouseSymbol-Book'
        body = 'the results were measured in each group and compared'
        refs1 = '12. Smith JA, Jones B. Bone fill at 36 months. J Dent 1998;45:301-7'
        refs2 = '4. Brown C. Healing. 2004;7:20'
        result = self.run_first_pass([(body, [(0, len(body), 'BODY')]),
                                      (refs1, [(0, len(refs1), sym)]), (refs2, [(0, len(refs2), sym)]),
                                      ('n 5 20', [(0, 6, 'BODY'), (2, 3, 'HousePi-One')])])
        digits = [r for r in result['records'] if r['font'] == sym and r['before'].isdigit()]
        self.assertEqual(digits, [])                                   # printed as claimed, never flagged
        # every code of the text face that keeps the name's sign reason (not a letter inside a word) is marked
        # running text; the Pi face's one code is not
        self.assertGreater(result['selected'].get('running text', 0), 0)
        self.assertEqual(result['selected']['sign face'], result['selected']['running text'] + 1)
        pi = [(r['before'], r['after'], r['status'], r['sign_claim']) for r in result['records'] if r['font'] == 'HousePi-One']
        self.assertEqual(pi, [('5', '=', 'replaced', 'sign face')])     # the real Pi face is decided as before

    def test_same_face_without_running_text_is_still_a_sign_face(self):
        sym = 'XYZABC+HouseSymbol-Book'
        body = 'the results were measured in each group and compared'
        result = self.run_first_pass([(body, [(0, len(body), 'BODY')]), ('a 4 b', [(0, 5, 'BODY'), (2, 3, sym)])])
        self.assertEqual([(r['before'], r['after'], r['status']) for r in result['records'] if r['font'] == sym],
                         [('4', '�', 'rejected')])
        self.assertNotIn('running text', result['selected'])


class SecondPass(unittest.TestCase):
    def test_rule9_measures_running_text_like_the_first_pass(self):
        import sys
        sys.path.insert(0, str(TOOLS/'secondpass'))
        spec9 = importlib.util.spec_from_file_location('r09_test', TOOLS/'secondpass'/'r09_glyphs.py')
        r09 = importlib.util.module_from_spec(spec9); spec9.loader.exec_module(r09)
        line = '12. Smith JA, Jones B. 1998;45:301'
        chars = [dict(text=ch, font='HouseSymbol-Book') for ch in line] + [dict(text='5', font='HousePi-One')]
        self.assertEqual(r09.text_faces(fonts, [(1, chars)]), {'HouseSymbol-Book'})


if __name__ == '__main__':
    unittest.main()
