"""Private-use codes: Symbol-encoding readings, outline checks and the copy's no-private-use guard.

Run: /usr/bin/python3 -I tools/test_symbolpua.py
"""
import collections
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('font_checks', ROOT / 'tools/check_fonts.py')
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)
copy = fonts.signs.copy
if '_copy_table_reader' not in sys.modules:
    spec = importlib.util.spec_from_file_location('_copy_table_reader', ROOT / 'standalone/element_boxer_sc.py')
    module = importlib.util.module_from_spec(spec); sys.modules['_copy_table_reader'] = module
    spec.loader.exec_module(module)
reader = sys.modules['_copy_table_reader']
# Sci Adv 2019 (AH07): body Greek set in SymbolGreek with U+F0xx text codes.
AH07 = Path('/mnt/ai/projects/optionsdds/trials/element-boxer-batch31-inputs/papers/AH07/paper.pdf')


def proof(before='', marks=('font name',), verdict='neutral', scores=None, outline=None):
    code = fonts.symbol_code(before)
    return dict(model=fonts.PRIVATE_MODEL, font='ABCDEF+SymbolGreek', source_code=code, before=before,
                symbol_code=code, reading=fonts.SYMBOL_ENCODING.get(code) if code is not None else None,
                marks=list(marks), glyph_names=[None], glyph_name_verdict=verdict, scores=scores,
                outline=outline, outline_reason=None)


class SymbolEncodingTests(unittest.TestCase):
    def test_table_matches_reader_symbol_names(self):
        # Unicode's published Adobe Symbol mapping, which differs from the AGL
        # only where the AGL chose compatibility or private-use characters.
        overrides = {'Delta': 'Δ', 'Omega': 'Ω', 'mu': 'μ'}
        for code, name in reader.SC_SYMBOL_NAMES.items():
            if code == 0x20: continue
            agl = reader.sc_uni(name)
            expected = overrides.get(name, agl)
            if fonts.private_use(agl):
                # Adobe's private values: a published Unicode reading, except radicalex.
                if name == 'radicalex': self.assertNotIn(code, fonts.SYMBOL_ENCODING)
                else: self.assertIn(code, fonts.SYMBOL_ENCODING, name)
                self.assertEqual(fonts.ADOBE_SYMBOL_PRIVATE[ord(agl)], code, name)
            else: self.assertEqual(fonts.SYMBOL_ENCODING[code], expected, name)
        self.assertFalse(any(fonts.private_use(ch) for ch in fonts.SYMBOL_ENCODING.values()))
        self.assertEqual(set(fonts.SYMBOL_ENCODING), set(reader.SC_SYMBOL_NAMES)-{0x20, 0x60})

    def test_symbol_codes(self):
        self.assertEqual(fonts.symbol_code(''), 0x62)
        self.assertEqual(fonts.symbol_code(''), 0xE6)
        for ch in ('b', 'β', '', '', '', '\U000f0001'):
            self.assertIsNone(fonts.symbol_code(ch), ch)
        self.assertTrue(fonts.private_use('\U000f0001') and fonts.private_use(''))
        self.assertFalse(fonts.private_use('�'))

    def test_glyph_name_verdicts(self):
        self.assertEqual(fonts.glyph_name_verdict(['beta'], 0x62, 'β', reader), 'agrees')
        self.assertEqual(fonts.glyph_name_verdict(['b', None, 'uniF062', 'g12'], 0x62, 'β', reader), 'neutral')
        self.assertEqual(fonts.glyph_name_verdict(['alpha'], 0x62, 'β', reader), 'contradicts')
        self.assertEqual(fonts.glyph_name_verdict(['beta', 'H'], 0x62, 'β', reader), 'contradicts')


class DecisionTests(unittest.TestCase):
    def test_marks_and_mapping(self):
        self.assertEqual(fonts.private_decision(proof()), ('mapped-unchecked', 'β'))
        self.assertEqual(fonts.private_decision(proof(marks=())), ('unmapped', '�'))
        self.assertEqual(fonts.private_decision(proof(verdict='contradicts')), ('unmapped', '�'))
        self.assertEqual(fonts.private_decision(proof(before='')), ('unmapped', '�'))
        self.assertEqual(fonts.private_decision(proof(before='')), ('unmapped', '�'))

    def test_outline_outcomes(self):
        self.assertEqual(fonts.private_decision(proof(scores={'β': .80, 'μ': .57})), ('mapped', 'β'))
        self.assertEqual(fonts.private_decision(proof(scores={'β': .52, 'Y': .60})), ('mapped-unconfirmed', 'β'))
        self.assertEqual(fonts.private_decision(proof(scores={'β': .20, 'H': .90, 'x': .10})), ('contradicted', '�'))
        self.assertEqual(fonts.private_decision(proof(scores={'β': .30, 'H': .75})), ('contradicted', '�'))

    def test_tampered_proofs_are_invalid(self):
        bad = proof(); bad['reading'] = 'b'
        self.assertEqual(fonts.private_decision(bad)[0], 'invalid')
        self.assertEqual(fonts.private_decision(proof(marks=('embedded glyph name',)))[0], 'invalid')
        self.assertEqual(fonts.private_decision(proof(marks=('guess',)))[0], 'invalid')
        self.assertEqual(fonts.private_decision(proof(scores={'β': float('nan')}))[0], 'invalid')
        self.assertEqual(fonts.private_decision(proof(scores={'α': .9}))[0], 'invalid')
        self.assertEqual(fonts.private_decision(dict(proof(), before='b'))[0], 'invalid')

    def test_symbol_references_stay_separate(self):
        base = fonts.outline_references(); extra = fonts.symbol_references()
        self.assertNotIn('Δ', base); self.assertIn('Δ', extra); self.assertIn('τ', extra)
        self.assertTrue(all(extra[ch] == rows for ch, rows in base.items()))

    def test_notices(self):
        rows = collections.Counter({('F', 98, '', 'β', 'mapped'): 3, ('F', 109, '', 'μ', 'mapped-unconfirmed'): 2,
                                    ('G', 42, '', '�', 'unmapped'): 1})
        proofs = {('F', 98, ''): proof(scores={'β': .8}), ('F', 109, ''): proof('', scores={'μ': .53}),
                  ('G', 42, ''): proof('', marks=())}
        notices = fonts.private_notices(rows, proofs)
        self.assertTrue(notices[0].startswith('3 private-use Symbol-font codes') and 'U+F062→β 3' in notices[0])
        self.assertIn("read as 'μ'", notices[1]); self.assertIn('0.530', notices[1])
        self.assertIn('not marked as a Symbol font; shown as � in 1 places', notices[2])


class CopyGuardTests(unittest.TestCase):
    def test_every_private_code_leaves_run_table_and_rule8_text(self):
        chars = [dict(text=t, font='F') for t in ('A', '', 'x', '')]
        e = dict(kind='text', id='run:1', text='A x', char_ids=[0, 1, 2, 3],
                 font_spans=[dict(font='F', start=0, end=6)])
        e['_chars'] = list(chars)
        page = dict(page=3, elements=[e], _table_chars=chars, _private_readings=[('', 'χ')])
        authors = dict(title=dict(text='A and '), authors=[dict(name='N')])
        uncertain = []
        copy.replace_private_codes([page], authors, uncertain)
        self.assertEqual(e['text'], 'A� x�')
        self.assertEqual([c['text'] for c in page['_table_chars']], ['A', '�', 'x', '�'])
        self.assertEqual([c['text'] for c in e['_chars']], ['A', '�', 'x', '�'])
        self.assertEqual(chars[1]['text'], '')   # reader characters stay native
        self.assertEqual(authors['title']['text'], 'Aχ and �'); self.assertEqual(authors['authors'][0]['name'], 'Nχ')
        self.assertEqual(len(uncertain), 1); self.assertIn('U+E001 1, U+F062 1', uncertain[0])
        self.assertNotIn('_private_readings', page)

    def test_conflicting_readings_become_replacement_characters(self):
        pages = [dict(page=1, elements=[], _private_readings=[('', 'β')]),
                 dict(page=2, elements=[], _private_readings=[('', '�')])]
        authors = dict(title=dict(text=''))
        copy.replace_private_codes(pages, authors, [])
        self.assertEqual(authors['title']['text'], '�')


@unittest.skipUnless(AH07.is_file(), 'AH07 PDF not available')
class RealOutlineTests(unittest.TestCase):
    def test_symbolgreek_outlines(self):
        chars = reader.sc_read_page(str(AH07), 1)[0]
        doc = reader.sc_doc(str(AH07))
        glyphs = [dict(offset=i, char_id=i, before=c['text'], font=c['font'], source_code=c.get('source_code'))
                  for i, c in enumerate(chars) if fonts.private_use(c['text'])]
        self.assertTrue(glyphs)
        run = dict(page=1, id='run:test', font_glyphs=glyphs)
        report = fonts.verify_private_codes(doc, [run])
        decisions = {r['reading']: r['status'] for r in report['records']}
        self.assertEqual(decisions.get('β'), 'mapped')
        self.assertTrue(all(r['marks'] == ['font name'] and r['after'] == r['reading'] for r in report['records']))


if __name__ == '__main__':
    unittest.main()
