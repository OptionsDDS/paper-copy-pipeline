"""Lane r5-signs (round 5): rules O22, O23 and O28.
(O23) A standard sign face (Symbol, ZapfDingbats) drawn from the reader's own font, whose PDF encoding names no base
encoding, is read through the face's published table, with its AFM width: never as StandardEncoding's Latin letter
or a zero-width (dropped) glyph.  An explicit base encoding, an embedded program or another face is read as before.
(O22) The program's reading of a line and poppler's are compared token by token; only tokens one reader holds more
often are doubtful places; order differences, folded forms and a line-end hyphen are not.
(O26) The same glyph (font object and code) is the same sign: a sign settled at one place is written at the places that
still hold the bare claim; a claim found wrong (U+FFFD) and settled nowhere is shown as U+FFFD everywhere; accented
letters, dashes, ligatures and tables are left as they are.
(O28) Every unread mark the copy prints on a prose line is listed with its glyph and the fixed choices, never more
places than the copy line prints.
/usr/bin/python3 -I tools/test_r5_signs.py"""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


boxer = module('r5signs_boxer', ROOT / 'standalone/element_boxer_sc.py')
rules = module('r5signs_rules', TOOLS / 'sign_rules.py')
doubts = module('r5signs_doubts', ROOT / 'doubts.py')


def pdf_bytes(sign_font, runs):
    """a one-page PDF: Times-Roman (F1) and a second font (F2, its dictionary given) set in text runs [(font, bytes)]"""
    content = b'BT /F1 10 Tf 72 700 Td ' + b' '.join(
        b'/%s 10 Tf (%s) Tj' % (f.encode(), s.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)'))
        for f, s in runs) + b' ET'
    objs = [b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>',
            b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>',
            sign_font]
    out = io.BytesIO()
    out.write(b'%PDF-1.4\n')
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b'%d 0 obj\n' % i + body + b'\nendobj\n')
    xref = out.tell()
    out.write(b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offsets))
    out.write(b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, xref))
    return out.getvalue()


class StandardSignFaces(unittest.TestCase):
    def read(self, font, runs):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.pdf')
            Path(p).write_bytes(pdf_bytes(font, runs))
            chars = boxer.sc_read_page(p, 1)[0]
        return chars, ''.join(c['text'] + (' ' if c.get('space_after') else '') for c in chars)

    def test_symbol_with_differences_only_reads_its_table(self):
        font = b'<< /Type /Font /Subtype /Type1 /BaseFont /Symbol /Encoding << /Type /Encoding /Differences [240 /apple] >> >>'
        chars, text = self.read(font, [('F1', b'TGF-'), ('F2', b'b'), ('F1', b'1 and '), ('F2', b'a\xb4')])
        self.assertIn('TGF-β1', text)
        self.assertIn('α×', text)
        beta = next(c for c in chars if c['text'] == 'β')
        self.assertGreater(beta['x1'] - beta['x0'], 1.0)          # its AFM advance, not a dropped zero-width glyph

    def test_symbol_without_encoding_reads_its_table(self):
        font = b'<< /Type /Font /Subtype /Type1 /BaseFont /Symbol >>'
        _, text = self.read(font, [('F1', b'p '), ('F2', b'\xa3'), ('F1', b' 0.05')])
        self.assertIn('p ≤ 0.05', text)

    def test_zapf_dingbats_reads_its_table(self):
        font = b'<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats /Encoding << /Type /Encoding /Differences [128 /a89] >> >>'
        chars, text = self.read(font, [('F1', b'mail '), ('F2', b')'), ('F1', b' done '), ('F2', b'4')])
        self.assertIn('✉', text)
        self.assertIn('✔', text)
        self.assertTrue(all(c['x1'] > c['x0'] for c in chars if c['font'] == 'ZapfDingbats'))

    def test_a_named_base_encoding_and_other_faces_read_as_before(self):
        font = b'<< /Type /Font /Subtype /Type1 /BaseFont /Symbol /Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding >> >>'
        _, text = self.read(font, [('F1', b'x '), ('F2', b'b')])
        self.assertNotIn('β', text)
        font = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding /Differences [240 /apple] >> >>'
        _, text = self.read(font, [('F1', b'x '), ('F2', b'b')])
        self.assertIn('x b', text)


def toks(s):
    return rules.tokens(s), [(i, 0, i + 1, 1) for i, _ in enumerate(rules.tokens(s))]


class TwoReadings(unittest.TestCase):
    def diff(self, a, b):
        ta, ba = toks(a)
        tb, bb = toks(b)
        return rules.differences(ta, ba, tb, bb)

    def test_agreeing_readings_have_no_place(self):
        self.assertEqual(self.diff('p < 0.05 – a “quote”', 'p<0.05 - a "quote"'), [])

    def test_accent_forms_and_a_soft_hyphen_are_one_reading(self):
        self.assertEqual(self.diff('Zu\u00a8rich 632\u00ad\u2013641', 'Z\u00fcrich 632-641'), [])
        self.assertEqual(self.diff('doi.org/10.1111/j.1600-051X', 'doi.org/10.1111/j.1600-0\u200b51X'), [])
        self.assertEqual(self.diff('Krc\u02c7mova\u0301', 'Kr\u010dmov\u00e1'), [])

    def test_order_differences_are_not_readings(self):
        self.assertEqual(self.diff('cells2 were', 'cells were2'), [])

    def test_line_end_hyphen_is_not_a_sign(self):
        self.assertEqual(self.diff('perio', 'perio-'), [])
        # a line-end dash the second reader reads as another sign is a reading difference
        self.assertEqual([x[1] for x in self.diff('149:905\u2013', '149:905\u00b1')], ['readers_differ'])

    def test_a_sign_one_reader_lacks_is_a_place(self):
        d = self.diff('mean 43.6±8 years', 'mean 43.68 years')
        self.assertEqual([x[1] for x in d], ['second_reader_none'])
        d = self.diff('TGF-β1', 'TGF-b1')
        self.assertEqual([x[1] for x in d], ['readers_differ'])

    def test_unreadable_codes_are_one_unread_token(self):
        self.assertEqual(rules.tokens('a\x02b'), ['a', '�', 'b', '�'])


class NeverSilent(unittest.TestCase):
    def run_rules(self, copy_text, run_text, kind='paragraph', second=None, words=None, ids=None, ebox=(150, 187, 400, 210)):
        doubts.reset()
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'copy.md').write_text(copy_text, encoding='utf-8')
            span = [0, len(copy_text.split('\n')[0])]
            trace = {'units': [{'id': 'u1', 'kind': kind}, {'id': 'u2', 'kind': 'front_matter_printed'}],
                     'pdf': {'pages': [{'page': 1, 'media_box_pdf_points': [0, 0, 612, 792]}]},
                     'lines': [{'page': 1, 'box_pdf_points': [72, 690, 300, 702], 'runs': ['run:1'],
                                'units': [{'unit_id': 'u1', 'copy_span': span}] +
                                         ([{'unit_id': 'u2', 'copy_span': second}] if second else [])}]}
            Path(d, 'copy.trace.json').write_text(json.dumps(trace), encoding='utf-8')
            chars = [{'text': ch, 'x0': 150 + 10 * i, 'y0': 187, 'x1': 158 + 10 * i, 'y1': 210, 'font': 'ABCDEF+AdvPSMP1',
                      'source_code': 2} for i, ch in enumerate(run_text.replace(' ', ''))]
            page = {'page': 1, 'params': {'dpi': 150}, 'elements': [
                {'id': 'run:1', 'kind': 'text', 'text': run_text, 'char_ids': ids if ids is not None else list(range(len(chars))),
                 'box_px': list(ebox)}]}
            saved = rules.poppler_words
            if words is not None:   # the second reader's words, in points on the line (top 90, bottom 102)
                rules.poppler_words = lambda pdf: {1: [w if isinstance(w, tuple) else (72 + 30 * n, 91, 72 + 30 * n + 25, 101, w)
                                                       for n, w in enumerate(words)]}
            try:
                rules.run(d, [page], 'x.pdf' if words is not None else None, lambda p: chars, doubts)
            finally:
                rules.poppler_words = saved
        return doubts.items()

    def test_each_printed_mark_is_listed_with_its_glyph_and_choices(self):
        got = self.run_rules('to �buy time� until\n', 'to �buy time� until')
        self.assertEqual([d['rule'] for d in got], ['O28', 'O28'])
        self.assertEqual(got[0]['reason'], 'unread_sign:AdvPSMP1:2')
        self.assertEqual(got[0]['line'], 1)
        self.assertEqual(got[0]['options'][-1], 'none of these')
        self.assertIn('α', got[0]['options'])

    def test_never_more_places_than_the_copy_prints(self):
        got = self.run_rules('to �buy time" until\n', 'to �buy time� until')
        self.assertEqual(len(got), 1)

    def test_a_line_printed_twice_is_listed_on_both_copy_lines(self):
        got = self.run_rules('Ann Lee,\ufffd Bo Ng\n\nAnn Lee,\ufffd Bo Ng\n', 'Ann Lee,\ufffd Bo Ng', kind='author', second=[22, 38])
        self.assertEqual(sorted(d['line'] for d in got), [1, 3])

    def test_two_readings_listed_at_the_differing_sign(self):
        got = self.run_rules('mean 43.6±8 years here\n', 'mean 43.6±8 years here', words=['mean', '43.68', 'years', 'here'])
        self.assertEqual([(d['rule'], d['reason']) for d in got], [('O22', 'second_reader_none')])

    def test_a_token_the_copy_prints_is_not_lacking(self):
        # the second reader holds a word the program's line lacks, but the copy line prints it: not listed
        got = self.run_rules('the cells were counted\n', 'the cells counted', words=['the', 'cells', 'were', 'counted'])
        self.assertEqual(got, [])
        got = self.run_rules('the cells counted\n', 'the cells counted', words=['the', 'cells', '\u2022', 'counted'])
        self.assertEqual([d['reason'] for d in got], ['program_reader_none'])

    def test_a_line_without_its_first_reading_is_one_entry(self):
        # the run's character records lie elsewhere on the page than the run (records of another run)
        got = self.run_rules('alpha beta gamma delta\n', 'alpha beta gamma delta', ebox=(900, 187, 1100, 210),
                             words=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta'])
        self.assertEqual([d['reason'] for d in got], ['not_compared:no_first_reading'])

    def test_a_row_no_line_holds_is_not_given_to_its_neighbour(self):
        # words of a smaller-type row just under the line (no trace line of its own) are not read with the line
        under = [(72 + 30 * n, 98, 72 + 30 * n + 25, 107, w) for n, w in enumerate(['Author', 'details', 'moved', 'away'])]
        got = self.run_rules('alpha beta gamma\n', 'alpha beta gamma', words=['alpha', 'beta', 'gamma'] + under)
        self.assertEqual(got, [])

    def test_a_twin_word_layer_is_one_reading(self):
        got = self.run_rules('alpha beta gamma\n', 'alpha beta gamma',
                             words=['alpha', 'beta', 'gamma', (102, 91.5, 127, 101.5, 'beta')])
        self.assertEqual(got, [])

    def test_a_drop_cap_is_not_read_with_one_line(self):
        got = self.run_rules('Molar teeth\n', 'olar teeth', words=[(60, 70, 71, 110, 'M'), 'olar', 'teeth'])
        self.assertEqual(got, [])

    def test_readings_that_share_little_are_one_entry(self):
        got = self.run_rules('ab cd\n', 'ab cd', words=['ab', 'cd', 'ab', 'cd', 'ef', 'gh', 'ij', 'kl'])
        self.assertEqual([d['reason'] for d in got], ['not_compared:readings_apart'])

    def test_table_cells_and_captions_are_not_listed(self):
        self.assertEqual(self.run_rules('a � b\n', 'a � b', kind='table_cell'), [])
        self.assertEqual(self.run_rules('a � b\n', 'a � b', kind='caption'), [])


class SameGlyphSameSign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        import types
        cls.copy = module('r5signs_copy', ROOT / 'copy_paper.py')
        cls.sys = sys
        cls.fake = types.ModuleType('_copy_table_reader')
        cls.fake.PARAMS = {'dpi': 150}

    def run_pages(self, runs, tables=()):
        """runs: [(claims, finals, codes)] on one page, one font object; returns the final run texts and the list"""
        raw, elements = [], []
        for n, (claims, finals, codes) in enumerate(runs):
            ids = []
            for k, (ch, code) in enumerate(zip(claims, codes)):
                ids.append(len(raw))
                raw.append({'text': ch, 'x0': 10 * len(raw), 'x1': 10 * len(raw) + 8, 'y0': 100, 'y1': 110, 'hidden': False,
                            'source_code': code, 'font_key': 7, 'font': 'ABCDEF+Face', 'origin': (10 * len(raw), 110)})
            elements.append({'id': 'run:%d' % (n + 1), 'kind': 'text', 'text': finals, 'char_ids': ids, 'box_px': [0, 90, 50, 120]})
        page = {'page': 1, '_table_pdf': 'x.pdf', '_table_chars': [dict(c) for c in raw], 'region_box_px': [0, 0, 10 ** 6, 10 ** 6],
                'params': {'dpi': 150}, 'elements': elements, 'tables': [{'members': list(tables), 'box_px': [0, 0, 0, 0]}], 'floats': []}
        self.fake.sc_read_page = lambda pdf, page_no: (raw, None, None)
        self.sys.modules['_copy_table_reader'] = self.fake
        try:
            uncertain = []
            self.copy.same_glyph_same_sign([page], uncertain)
        finally:
            del self.sys.modules['_copy_table_reader']
        return [e['text'] for e in elements], uncertain

    def test_a_settled_sign_is_written_at_every_place(self):
        texts, notes = self.run_pages([('95\ufffdC', '95°C', (1, 2, 9, 3)), ('50\ufffdC', '50\ufffdC', (4, 1, 9, 3))])
        self.assertEqual(texts, ['95°C', '50°C'])
        self.assertEqual(len(notes), 1)

    def test_a_claim_found_wrong_somewhere_is_unread_everywhere(self):
        texts, _ = self.run_pages([('5mL', '5\ufffdL', (1, 9, 3)), ('2mL', '2mL', (4, 9, 3))])
        self.assertEqual(texts, ['5\ufffdL', '2\ufffdL'])

    def test_accents_dashes_ligatures_and_tables_stay(self):
        texts, notes = self.run_pages([('na', 'ña', (9, 1)), ('na', 'na', (9, 1))])
        self.assertEqual(texts, ['ña', 'na'])
        texts, _ = self.run_pages([('-2', '−2', (9, 1)), ('a-b', 'a-b', (2, 9, 3))])
        self.assertEqual(texts, ['−2', 'a-b'])
        texts, _ = self.run_pages([('95\ufffdC', '95°C', (1, 2, 9, 3)), ('50\ufffdC', '50\ufffdC', (4, 1, 9, 3))], tables=['run:2'])
        self.assertEqual(texts, ['95°C', '50\ufffdC'])


if __name__ == '__main__':
    unittest.main()
