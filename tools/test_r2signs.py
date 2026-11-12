"""Lane r2-signs: a sign printed as a wrong letter with no flag.
(1) A glyph whose text layer claims several letters (a ligature such as 'fl') but whose embedded outline's
strokes prove a sign is printed as that sign (first letter replaced, the others removed) and listed once;
no letter silhouette is proven a sign. (2) A glyph claimed as a space whose embedded outline draws ink is
no space: it is recovered from its glyph name or encoding, else shown as U+FFFD (flagged), never dropped;
a blank space glyph stays a space.
/usr/bin/python3 -I tools/test_r2signs.py"""
import importlib.util
import io
import json
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


fonts = module('r2signs_fonts', TOOLS/'check_fonts.py')
SANS = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')


FACES = [Path('/usr/share/fonts/truetype/dejavu/DejaVu%s.ttf' % n)
         for n in ('Sans', 'Serif', 'Sans-Bold', 'Serif-Bold', 'Sans-Oblique', 'Serif-Italic')]
boxer = module('r2signs_boxer', ROOT/'standalone/element_boxer_sc.py')


def real_shapes(characters):
    """{(face, character): silhouette} from the installed DejaVu faces' own outlines (outline_shape)."""
    from fontTools.ttLib import TTFont
    result = {}
    for path in FACES:
        if not path.exists(): continue
        program = boxer.SCFontProgram('truetype', path.read_bytes())
        cmap = TTFont(str(path)).getBestCmap()
        for ch in characters:
            if ord(ch) not in cmap: continue
            gid = program.order.index(cmap[ord(ch)])
            font = SimpleNamespace(prog=program, cid=False, gmap={1: gid}, cid2gid=None)
            result[path.stem, ch] = fonts.outline_shape(font, 1)
    return result


def reference(ch):
    return next(r for r in fonts.sign_references()[ch] if fonts.outline_sign_strokes(r) == ch)


def scores(shape):
    return {ch: max(fonts.outline_similarity(shape, r) for r in refs) for ch, refs in fonts.sign_references().items()}


@unittest.skipUnless(FACES[0].exists(), 'needs DejaVu Sans')
class LigatureDecision(unittest.TestCase):
    def test_comparison_outlines_replace_a_ligature_claim(self):
        shapes = real_shapes('≥≤')
        self.assertGreaterEqual(len(shapes), 6)
        for (face, sign), shape in shapes.items():
            with self.subTest(face=face, sign=sign):
                self.assertEqual(fonts.ligature_outline_decision('fl', scores(shape), shape=shape), ('replaced', sign))
                self.assertEqual(fonts.ligature_outline_decision('ffi', scores(shape), shape=shape), ('replaced', sign))

    def test_no_letter_digit_or_real_ligature_outline_is_proven_a_sign(self):
        letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ﬁﬂﬀﬃﬄ'
        shapes = real_shapes(letters)
        self.assertGreater(len(shapes), 300)
        for (face, ch), shape in shapes.items():
            with self.subTest(face=face, ch=ch):
                self.assertEqual(fonts.ligature_outline_decision('fl', scores(shape), shape=shape)[0], 'unchanged')

    def test_single_letter_and_non_letter_claims_are_not_ligatures(self):
        shape = reference('≥')
        for claim in ('f', '9', 'f9', '', None):
            self.assertEqual(fonts.ligature_outline_decision(claim, scores(shape), shape=shape)[0], 'unchanged')

    def test_groups_need_one_glyph(self):
        g = lambda o, cid, box, code=7, font='F': dict(offset=o, char_id=cid, box_px=box, source_code=code, font=font, before='x')
        same = [g(3, 10, [1, 1, 5, 5]), g(4, 11, [1, 1, 5, 5]), g(5, 12, [6, 1, 9, 5])]
        self.assertEqual([[c['offset'] for c in grp] for grp in fonts.ligature_glyphs(same)], [[3, 4]])
        apart = [g(3, 10, [1, 1, 5, 5]), g(4, 11, [6, 1, 9, 5])]                       # two glyphs of one code ('ll')
        self.assertEqual(fonts.ligature_glyphs(apart), [])
        other_code = [g(3, 10, [1, 1, 5, 5]), g(4, 11, [1, 1, 5, 5], code=8)]
        self.assertEqual(fonts.ligature_glyphs(other_code), [])
        gap = [g(3, 10, [1, 1, 5, 5]), g(4, 12, [1, 1, 5, 5])]
        self.assertEqual(fonts.ligature_glyphs(gap), [])


class LigatureEndToEnd(unittest.TestCase):
    """verify_outlines -> apply_results (on disk) -> apply_copy, with the outline of the code mocked."""
    def run_copy(self, text, offset, code_shape, mutate=None):
        chars = [dict(text=t, font='F', source_code=ord(t)) for t in text]
        chars[offset]['source_code'] = chars[offset+1]['source_code'] = 900
        glyphs = [dict(offset=i, char_id=i, before=t, font='F', source_code=chars[i]['source_code'],
                       box_px=[i*10, 0, i*10+8, 10] if i not in (offset, offset+1) else [offset*10, 0, offset*10+14, 10])
                  for i, t in enumerate(text)]
        run = dict(page=1, id='run:1', source=text, crop_xywh=[0, 0, 100, 10], font_glyphs=glyphs)
        doc = SimpleNamespace(fonts={1: SimpleNamespace(basefont='F', bbox=lambda c: (0, 600, 500, 0), width=lambda c: 500)})
        def shape(font, code):
            if code == 900: return code_shape
            raise ValueError('no outline in this test')
        with patch.object(fonts, 'outline_shape', side_effect=shape):
            result = fonts.verify_outlines(doc, [run])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'page-01.json'
            saved = dict(page=1, fonts={'F': {}}, elements=[dict(id='run:1', kind='text', text=text, char_ids=list(range(len(text))))])
            path.write_text(json.dumps(saved))
            fonts.apply_results({str(path): (path.read_bytes(), json.loads(path.read_text()))},
                                [dict(run, file=str(path), index=0, candidates=[])], {})
            page = json.loads(path.read_text())
        page['_table_chars'] = chars
        if mutate: mutate(page)
        warnings = []; fonts.apply_copy([page], warnings)
        return result, page, warnings

    def test_fl_over_a_comparison_outline_becomes_the_sign(self):
        result, page, warnings = self.run_copy('aged fl9 months', 5, reference('≥'))
        record = [r for r in result['records'] if r.get('ligature')][0]
        self.assertEqual((record['before'], record['after'], record['status']), ('fl', '≥', 'replaced'))
        self.assertEqual(page['elements'][0]['text'], 'aged ≥9 months')
        self.assertEqual([c['text'] for c in page['_table_chars']][5:7], ['≥', ''])
        self.assertEqual(len([w for w in warnings if "'fl' printed as '≥'" in w]), 1)

    def test_real_ligature_outline_keeps_its_letters(self):
        result, page, warnings = self.run_copy('the flow rate', 4, real_shapes('ﬂ')['DejaVuSerif', 'ﬂ'])
        self.assertFalse([r for r in result['records'] if r.get('ligature')])
        self.assertEqual(page['elements'][0]['text'], 'the flow rate')
        self.assertEqual(warnings, [])

    def test_a_changed_claim_is_not_replaced(self):
        def mutate(page):
            page['elements'][0]['text'] = 'aged fi9 months'; page['_table_chars'][6]['text'] = 'i'
        result, page, warnings = self.run_copy('aged fl9 months', 5, reference('≥'), mutate)
        self.assertEqual(page['elements'][0]['text'], 'aged fi9 months')
        self.assertFalse([w for w in warnings if 'printed as' in w])


class InkedSpaceIsNoFaceCode(unittest.TestCase):
    def test_small_face_count_leaves_out_inked_space_claims(self):
        def run(i, text, font, codes, inked=()):
            glyphs = [dict(offset=k, char_id=100*i+k, before=t, font=font, source_code=c, box_px=[10*k, 0, 10*k+8, 10],
                           **({'inked_space': True} if k in inked else {})) for k, (t, c) in enumerate(zip(text, codes))]
            return dict(page=1, id='run:%d' % i, source=text, crop_xywh=[0, 0, 100, 10], font_glyphs=glyphs)
        body = run(0, 'abcdefghij', 'Body', [ord(t) for t in 'abcdefghij'])
        sym = run(1, 'abklm\ufffd', 'Sym', [97, 98, 107, 108, 109, 32], inked=(5,))
        doc = SimpleNamespace(fonts={1: SimpleNamespace(basefont='Body'), 2: SimpleNamespace(basefont='Sym')})
        seen = []
        def decide(before, scores, **kw):
            seen.append(kw.get('small')); return 'confirmed', before
        with patch.object(fonts, 'outline_shape', return_value=reference('≥')), \
             patch.object(fonts, 'sign_outline_decision', side_effect=decide):
            fonts.verify_outlines(doc, [body, sym])
        self.assertTrue(seen and all(seen))   # five text codes: still a small face


@unittest.skipUnless(SANS.exists(), 'needs DejaVu Sans')
class InkedSpaceClaim(unittest.TestCase):
    """A one-page PDF: a CID TrueType face whose ToUnicode maps beta's glyph to a space."""
    @classmethod
    def setUpClass(cls):
        cls.boxer = boxer
        from fontTools.ttLib import TTFont
        tt = TTFont(str(SANS)); cmap = tt.getBestCmap()
        cls.gids = {ch: tt.getGlyphID(cmap[ord(ch)]) for ch in 'TGF-1 β'}
        data = SANS.read_bytes()
        claims = {g: ('0020' if ch in ' β' else '%04X' % ord(ch)) for ch, g in cls.gids.items()}
        tu = ('/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /T def /CMapType 2 def '
              '1 begincodespacerange <0000> <FFFF> endcodespacerange %d beginbfchar %s endbfchar endcmap '
              'CMapName currentdict /CMap defineresource pop end end' %
              (len(claims), ' '.join('<%04X> <%s>' % kv for kv in claims.items()))).encode()
        text = ''.join('%04X' % cls.gids[ch] for ch in 'TGF-β1 1')
        content = ('BT /F1 12 Tf 72 700 Td <%s> Tj ET' % text).encode()
        objs = [b'<< /Type /Catalog /Pages 2 0 R >>',
                b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                b'<< /Type /Font /Subtype /Type0 /BaseFont /AAAAAA+Face /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>',
                b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream',
                b'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /AAAAAA+Face /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 8 0 R /CIDToGIDMap /Identity /DW 600 >>',
                b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(zlib.compress(tu)) + zlib.compress(tu) + b'\nendstream',
                b'<< /Type /FontDescriptor /FontName /AAAAAA+Face /Flags 32 /FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile2 9 0 R >>',
                b'<< /Length %d /Length1 %d >>\nstream\n' % (len(data), len(data)) + data + b'\nendstream']
        out = io.BytesIO(); out.write(b'%PDF-1.5\n'); offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(out.tell()); out.write(b'%d 0 obj\n' % i + body + b'\nendobj\n')
        xref = out.tell()
        out.write(b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs)+1) + b''.join(b'%010d 00000 n \n' % o for o in offsets))
        out.write(b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs)+1, xref))
        cls.folder = tempfile.TemporaryDirectory(); cls.pdf = Path(cls.folder.name)/'inked.pdf'
        cls.pdf.write_bytes(out.getvalue())

    @classmethod
    def tearDownClass(cls): cls.folder.cleanup()

    def test_inked_space_claim_is_flagged_and_blank_space_stays_a_space(self):
        chars, _, counts = self.boxer.sc_read_page(str(self.pdf), 1)
        self.assertEqual(''.join(c['text'] + (' ' if c.get('space_after') else '') for c in chars).strip(), 'TGF-�1 1')
        flagged = [c for c in chars if c['text'] == '�']
        self.assertEqual(len(flagged), 1); self.assertTrue(flagged[0]['dropped_control'])
        self.assertEqual(counts['inked_space_claims'], 1)

    def test_flag_keeps_a_space_footprint(self):
        chars, _, _ = self.boxer.sc_read_page(str(self.pdf), 1)
        i = next(k for k, c in enumerate(chars) if c['text'] == '\ufffd')
        c, prev = chars[i], chars[i-1]
        self.assertTrue(c['inked_space_claim'])
        self.assertEqual((c['y0'], c['y1']), (prev['y0'], prev['y1']))         # the line's own extent, not the ink's
        self.assertEqual(c['x0'], c['origin'][0]); self.assertEqual(c['x1'], c['adv_x1'])
        self.assertNotEqual(c['ink_box'], [c['x0'], c['y0'], c['x1'], c['y1']])

    def test_inked_needs_an_outline_with_ink(self):
        d = self.boxer.sc_doc(str(self.pdf)); self.boxer.sc_read_page(str(self.pdf), 1)
        font = next(f for f in d.fonts.values() if f.basefont.endswith('Face'))
        self.assertTrue(font.inked(self.gids['β']))
        self.assertFalse(font.inked(self.gids[' ']))


if __name__ == '__main__':
    unittest.main()
