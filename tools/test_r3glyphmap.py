"""Lane r3-glyphmap: symbol-face codes printed as the letters their glyph names say.
A face whose encoding names a letter (any script, ordinals included) for a code whose outline is a sign keeps
sign treatment for every code, whatever the claimed character's class and whatever touches it; a claim with no
reference silhouette is decided by its outline against the sign set (a dot by its place on the line), and an
unmatched letter claim there is flagged, never printed as the letter. Honest faces are unchanged.
/usr/bin/python3 -I tools/test_r3glyphmap.py"""
import importlib.util
import io
import json
import sys
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


sys.path.insert(0, str(TOOLS/'secondpass'))   # rule 9 imports its folder's common module (before the reader's import guard)
r09 = importlib.import_module('r09_glyphs')
fonts = module('r3glyphmap_fonts', TOOLS/'check_fonts.py')
boxer = module('r3glyphmap_boxer', ROOT/'standalone/element_boxer_sc.py')
SYMBOLS = Path('/usr/share/fonts/opentype/urw-base35/StandardSymbolsPS.otf')
SANS = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')

RAISED_DOT = dict(bounds_em=[.058, .398, .167, .290], advance_em=.25)
BASELINE_DOT = dict(bounds_em=[.06, .11, .17, 0.0], advance_em=.25)
BULLET = dict(bounds_em=[.06, .52, .40, .20], advance_em=.46)


def scores(shape):
    return {ch: max(fonts.outline_similarity(shape, r) for r in refs) for ch, refs in fonts.sign_references().items()}


def ref(ch, k=0): return fonts.sign_references()[ch][k]


def real_shape(ch, path=SANS):
    from fontTools.ttLib import TTFont
    program = boxer.SCFontProgram('truetype', path.read_bytes())
    gid = program.order.index(TTFont(str(path)).getBestCmap()[ord(ch)])
    return fonts.outline_shape(SimpleNamespace(prog=program, cid=False, gmap={1: gid}, cid2gid=None), 1)


class DotPlace(unittest.TestCase):
    def test_dot_is_the_dot_whose_place_it_takes(self):
        self.assertEqual(fonts.dot_by_place(RAISED_DOT), '·')
        self.assertEqual(fonts.dot_by_place(BASELINE_DOT), '.')
        self.assertEqual(fonts.dot_by_place(BULLET), '•')
        self.assertIsNone(fonts.dot_by_place(None))
        self.assertIsNone(fonts.dot_by_place(dict(bounds_em=[0, 0, 0, 0])))


@unittest.skipUnless(SANS.exists(), 'needs DejaVu Sans')
class NamedDecision(unittest.TestCase):
    def test_raised_dot_named_as_a_letter_is_a_middle_dot(self):
        dot = real_shape('·'); s = scores(dot)
        self.assertEqual(fonts.sign_outline_decision('Æ', s, shape=dot, geometry=RAISED_DOT, named=True), ('replaced', '·'))
        self.assertEqual(fonts.sign_outline_decision('Æ', s, shape=dot, geometry=BASELINE_DOT, named=True), ('replaced', '.'))
        # without the face property the decision is the one before this lane (never the placed dot)
        self.assertNotEqual(fonts.sign_outline_decision('Æ', s, shape=dot, geometry=RAISED_DOT)[1], '·')

    def test_bar_and_double_bar_named_as_letters_are_minus_and_equals(self):
        bar = dict(bounds_em=[.05, .28, .55, .23], advance_em=.6)
        minus = real_shape('−'); eq = real_shape('=')
        self.assertEqual(fonts.sign_outline_decision('ª', scores(minus), shape=minus, geometry=bar, named=True), ('replaced', '−'))
        self.assertEqual(fonts.sign_outline_decision('Ω', scores(eq), shape=eq, named=True), ('replaced', '='))

    @unittest.skipUnless(SANS.exists(), 'needs DejaVu Sans')
    def test_unmatched_letter_without_reference_is_flagged_only_in_a_named_face(self):
        omega = real_shape('Ω')
        self.assertEqual(fonts.sign_outline_decision('Ω', scores(omega), shape=omega, named=True), ('rejected', '�'))
        self.assertEqual(fonts.sign_outline_decision('Ω', scores(omega), shape=omega), ('unchanged', 'Ω'))
        # a letter with its own reference silhouette is still confirmed by it
        alpha = real_shape('α')
        self.assertEqual(fonts.sign_outline_decision('α', scores(alpha), shape=alpha, named=True), ('confirmed', 'α'))


def cff_face(name, glyphs):
    """A CFF program from StandardSymbolsPS: {code: (new glyph name, source glyph name)}."""
    sys.path.insert(0, str(ROOT/'standalone'/'vendor'))
    from fontTools.ttLib import TTFont
    from fontTools.cffLib import CharStrings
    tt = TTFont(str(SYMBOLS)); cff = tt['CFF '].cff; top = cff.topDictIndex[0]; old = top.CharStrings
    new = CharStrings(None, None, cff.GlobalSubrs, top.Private, None, None); new['.notdef'] = old['.notdef']
    names = ['.notdef']; widths = {}
    for code, (gname, sname) in sorted(glyphs.items()):
        names.append(gname); new[gname] = old[sname]; widths[code] = tt['hmtx'][sname][0]
    top.charset = names; top.CharStrings = new
    enc = ['.notdef']*256
    for code, (gname, _) in glyphs.items(): enc[code] = gname
    top.Encoding = enc; cff.fontNames = [name]
    b = io.BytesIO(); cff.compile(b, tt); return b.getvalue(), widths


def one_page_pdf(faces, content):
    """faces: [(resource, basefont, glyphs)] as Type 1C simple fonts with WinAnsi + Differences, no ToUnicode."""
    objs = [None, None, None]
    font_refs = []
    for res, base, glyphs in faces:
        data, widths = cff_face(base, glyphs)
        objs.append(b'<< /Length %d /Subtype /Type1C >>\nstream\n' % len(data) + data + b'\nendstream'); ff = len(objs)
        objs.append(b'<< /Type /FontDescriptor /FontName /AAAAAA+%s /Flags 4 /FontBBox [0 -200 1000 900] /ItalicAngle 0 '
                    b'/Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile3 %d 0 R >>' % (base.encode(), ff)); fd = len(objs)
        first, last = min(widths), max(widths)
        w = b' '.join(b'%d' % widths.get(c, 0) for c in range(first, last+1))
        diffs = b' '.join(b'%d /%s' % (c, g.encode()) for c, (g, _) in sorted(glyphs.items()))
        objs.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /AAAAAA+%s /FirstChar %d /LastChar %d /Widths [%s] '
                    b'/Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [%s] >> /FontDescriptor %d 0 R >>'
                    % (base.encode(), first, last, w, diffs, fd))
        font_refs.append(b'/%s %d 0 R' % (res.encode(), len(objs)))
    objs.append(b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream'); cs = len(objs)
    objs[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objs[1] = b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'
    objs[2] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << %s >> >> /Contents %d 0 R >>'
               % (b' '.join(font_refs), cs))
    out = io.BytesIO(); out.write(b'%PDF-1.5\n'); offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell()); out.write(b'%d 0 obj\n' % i + body + b'\nendobj\n')
    xref = out.tell()
    out.write(b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs)+1) + b''.join(b'%010d 00000 n \n' % o for o in offsets))
    out.write(b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs)+1, xref))
    return out.getvalue()


@unittest.skipUnless(SYMBOLS.exists(), 'needs URW StandardSymbolsPS')
class NamesContradictedOnRealOutlines(unittest.TestCase):
    """A one-page PDF with two embedded Type 1C faces: one names a minus /ordfeminine, an equals sign /Omega and a
    plus /pi; the other's names are honest (alpha, beta, Omega, minus drawn as themselves)."""
    @classmethod
    def setUpClass(cls):
        lying = {187: ('ordfeminine', 'minus'), 189: ('Omega', 'equal'), 185: ('pi', 'plus'), 176: ('infinity', 'infinity')}
        honest = {97: ('alpha', 'alpha'), 98: ('beta', 'beta'), 87: ('Omega', 'Omega'), 45: ('minus', 'minus')}
        content = b'BT /L 10 Tf 72 700 Td <BBBDB9B0> Tj ET BT /H 10 Tf 72 680 Td <6162572D> Tj ET'
        cls.folder = tempfile.TemporaryDirectory(); cls.pdf = Path(cls.folder.name)/'named.pdf'
        cls.pdf.write_bytes(one_page_pdf([('L', 'LabGreekSF-One', lying), ('H', 'LabSymbolPi', honest)], content))
        cls.saved = sys.modules.get('_copy_table_reader'); sys.modules['_copy_table_reader'] = boxer
        boxer.sc_read_page(str(cls.pdf), 1)
        cls.faces = {f.basefont.split('+')[-1]: f for f in boxer.sc_doc(str(cls.pdf)).fonts.values()}

    @classmethod
    def tearDownClass(cls):
        if cls.saved is None: sys.modules.pop('_copy_table_reader', None)
        else: sys.modules['_copy_table_reader'] = cls.saved
        cls.folder.cleanup()

    def test_lying_names_are_detected(self):
        f = self.faces['LabGreekSF-One']
        self.assertEqual(f.unicode(187), 'ª')
        self.assertTrue(fonts.names_contradicted(f, 187, f.unicode(187)))
        self.assertTrue(fonts.names_contradicted(f, 189, f.unicode(189)))
        self.assertTrue(fonts.names_contradicted(f, 185, f.unicode(185)))
        self.assertFalse(fonts.names_contradicted(f, 176, f.unicode(176)))   # infinity drawn as infinity: no letter
        self.assertFalse(fonts.names_contradicted(f, 189, '='))              # a claim the name does not give

    def test_honest_names_are_not(self):
        f = self.faces['LabSymbolPi']
        for code in (97, 98, 87, 45):
            self.assertFalse(fonts.names_contradicted(f, code, f.unicode(code)), code)


@unittest.skipUnless(SANS.exists(), 'needs DejaVu Sans')
class NamedFaceEndToEnd(unittest.TestCase):
    """verify_outlines -> apply_results (on disk) -> apply_copy for 'label=-0.47' set as body letters, then a
    Greek-named face's /Omega (an equals outline) and /ordfeminine (a minus outline), touching the word."""
    BARS = {189: (50, 350, 550, 150), 187: (50, 280, 550, 230)}

    def run_copy(self, text, sign_offsets, codes, shapes, names, basefont='AAAAAA+LabGreekSF-One'):
        chars = [dict(text=t, font='B', source_code=ord(t)) for t in text]
        for k, code in zip(sign_offsets, codes): chars[k].update(font=basefont, source_code=code)
        glyphs = [dict(offset=i, char_id=i, before=t, font=c['font'], source_code=c['source_code'], box_px=[i*10, 0, i*10+8, 10])
                  for i, (t, c) in enumerate(zip(text, chars))]
        run = dict(page=1, id='run:1', source=text, crop_xywh=[0, 0, 300, 10], font_glyphs=glyphs)
        face = SimpleNamespace(basefont=basefont, bbox=lambda c: self.BARS.get(c, (0, 600, 500, 0)), width=lambda c: 600,
                               selected_glyph_name=lambda c: names.get(c))
        face.width = lambda c: 1000 if c == 100 else 600
        body = SimpleNamespace(basefont='B', bbox=lambda c: (0, 600, 500, 0), width=lambda c: 500, selected_glyph_name=lambda c: None)
        doc = SimpleNamespace(fonts={1: body, 2: face})
        def shape(font, code):
            if font is face and code in shapes: return shapes[code]
            raise ValueError('no outline in this test')
        saved = sys.modules.get('_copy_table_reader'); sys.modules['_copy_table_reader'] = boxer
        try:
            with patch.object(fonts, 'outline_shape', side_effect=shape):
                result = fonts.verify_outlines(doc, [run])
        finally:
            if saved is None: sys.modules.pop('_copy_table_reader', None)
            else: sys.modules['_copy_table_reader'] = saved
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'page-01.json'
            page = dict(page=1, fonts={'B': {}, basefont: {}},
                        elements=[dict(id='run:1', kind='text', text=text, char_ids=list(range(len(text))))])
            path.write_text(json.dumps(page))
            fonts.apply_results({str(path): (path.read_bytes(), json.loads(path.read_text()))},
                                [dict(run, file=str(path), index=0, candidates=[])], {})
            page = json.loads(path.read_text())
        page['_table_chars'] = chars
        warnings = []; fonts.apply_copy([page], warnings)
        return result, page, warnings

    def shapes(self):
        return {189: real_shape('='), 187: real_shape('−')}

    def test_lying_face_signs_inside_a_word_are_printed_as_signs(self):
        result, page, warnings = self.run_copy('the labelΩª0.47 mm', [9, 10], [189, 187], self.shapes(),
                                               {189: 'Omega', 187: 'ordfeminine'})
        decided = {(r['before'], r['after'], r['status']) for r in result['records']}
        self.assertEqual(decided, {('Ω', '=', 'replaced'), ('ª', '−', 'replaced')})
        self.assertTrue(all(r.get('named_mismatch') for r in result['records']))
        self.assertEqual(page['elements'][0]['text'], 'the label=−0.47 mm')
        self.assertEqual(len([w for w in warnings if "printed as '='" in w]), 1)
        self.assertEqual(len([w for w in warnings if "printed as '−'" in w]), 1)

    def test_honest_names_keep_the_rule_before_this_lane(self):
        # the same outlines under names that give no letter: no face property, the inside-word rule stands
        result, page, warnings = self.run_copy('the labelΩª0.47 mm', [9, 10], [189, 187], self.shapes(),
                                               {189: 'equal', 187: 'minus'})
        self.assertFalse([r for r in result['records'] if r.get('named_mismatch')])
        self.assertEqual(page['elements'][0]['text'], 'the labelΩª0.47 mm')


    def test_a_face_selected_only_by_its_names_keeps_the_ordinary_replacement_first(self):
        # a dash face (no sign face by name or encoding) whose /d draws an em dash: the em dash stays an em dash,
        # not the sign set's minus, as for a small face that is no sign face
        # (six codes: no small face; the bar's box keeps the outline's own proportions)
        self.BARS = {**self.BARS, 100: (0, 294, 1000, 216)}
        text = 'in 1990d2000 only ( ) [ ] ;'
        marks = [k for k, ch in enumerate(text) if ch in '()[];']
        result, page, warnings = self.run_copy(text, [7] + marks, [100] + [ord(text[k]) for k in marks],
                                               {100: real_shape('—')}, {100: 'd'}, basefont='AAAAAA+DashFaceA')
        self.assertEqual(page['elements'][0]['text'], 'in 1990—2000 only ( ) [ ] ;')


class RuleNine(unittest.TestCase):
    def test_letter_pattern_covers_every_letter_and_ordinal(self):
        for ch in 'aZΩªºÆαß':
            self.assertTrue(r09.CLAIMS.match(ch), ch)
        for ch in ';:~':
            self.assertTrue(r09.CLAIMS.match(ch), ch)
        for ch in '1=−_ .':
            self.assertFalse(r09.CLAIMS.match(ch), ch)

    def test_named_faces_follow_the_first_pass_selection(self):
        calls = []
        def contradicted(font, code, claim):
            calls.append((code, claim)); return code == 189
        cf = SimpleNamespace(names_contradicted=contradicted)
        chars = [dict(text='Ω', font='G', source_code=189), dict(text='ª', font='G', source_code=187),
                 dict(text='Ω', font='G', source_code=189), dict(text='α', font='S', source_code=97),
                 dict(text='Ω', font='T', source_code=189), dict(text='=', font='U', source_code=61)]
        fonts_map = {'G': [object()], 'S': [object()], 'T': [object()], 'U': [object()]}
        self.assertEqual(r09.named_faces(cf, fonts_map, [(1, chars)], text_set={'T'}), {'G'})
        self.assertNotIn((61, '='), calls)          # only letter claims are tested
        self.assertNotIn((189, 'Ω'), calls[1:])     # one test per face, code and claim


if __name__ == '__main__':
    unittest.main()
