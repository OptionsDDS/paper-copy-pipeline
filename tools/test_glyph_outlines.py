"""Cached outline decisions, identity guards, and conservative ambiguity handling."""
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fonts', Path(__file__).with_name('check_fonts.py'))
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)


class OutlineTests(unittest.TestCase):
    def test_digit_with_moderate_native_score_still_tests_symbol_outline(self):
        ink={(x,y) for x in range(32) for y in range(32)
             if 14<=x<18 and y<26 or 12<=y<14 or y>=29}
        shape=(sum(1<<((y+4)*40+x+4) for x,y in ink),.82,len(ink)/1024)
        refs={'1':[('digit',)],'±':[('symbol',)],'+':[('plus',)]}
        scores={'digit':.54,'symbol':.735,'plus':.46}
        runs=[dict(page=1,id='run:1',source='mean 1 SD',crop_xywh=[0,0,60,10],font_glyphs=[
            dict(font='f',source_code=49,before='1',offset=5,char_id=0,box_px=[0,0,10,10])])]
        doc=SimpleNamespace(fonts={1:SimpleNamespace(basefont='f')})
        with patch.object(fonts,'outline_references',return_value=refs), \
             patch.object(fonts,'outline_shape',return_value=shape), \
             patch.object(fonts,'outline_similarity',side_effect=lambda a,b:scores[b[0]]):
            result=fonts.verify_outlines(doc,runs)
        record=result['records'][0]
        self.assertEqual((record['before'],record['after'],record['status']),('1','�','rejected'))
        sub=dict(record,offset=5,char_id=0)
        p=dict(page=1,fonts={'f':{'outline_verification':{'49':record}}},
            elements=[dict(id='run:1',kind='text',text='mean 1 SD',char_ids=[0],font_subs=[sub])],
            _table_chars=[dict(text='1',font='f',source_code=49)])
        # The real run needs all original characters to revalidate offsets.
        p['elements'][0].update(text='1',font_subs=[dict(sub,offset=0)])
        # Exercise the on-disk handoff too: scores alone cannot revalidate
        # the new topology-based rejection after the OCR process exits.
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'page-01.json';path.write_text('{}')
            candidate=dict(font='f',source_code=49,before='1',offset=0,char_id=0)
            saved=dict(page=1,fonts={'f':{}},elements=[dict(id='run:1',kind='text',text='1',char_ids=[0])])
            fonts.apply_results({str(path):(path.read_bytes(),saved)},[
                dict(file=str(path),index=0,page=1,id='run:1',source='1',candidates=[],
                     outline_records=[(candidate,record)])],{})
            loaded=json.loads(path.read_text());loaded['_table_chars']=p['_table_chars']
            p=loaded
        warnings=[];fonts.apply_copy([p],warnings)
        self.assertEqual(p['elements'][0]['text'],'�')
        self.assertIn('non-digit outline',warnings[0])
        self.assertEqual(fonts.outline_decision('1',{'1':.54,'±':.735}),('unchanged','1'))
        self.assertFalse(fonts.outline_plus_minus(fonts.outline_references()['1'][0]))

    def test_addresses_include_every_character(self):
        for token in ('https://example.org/w/media/x.pdf?la5en', 'ftp://example.org/file', '10.1234/AB56', 'person+5@example.org'):
            text = 'See '+token+' now'
            self.assertEqual(fonts.address_offsets(text), set(range(4, 4+len(token))))
        self.assertFalse(fonts.address_offsets('five patients were 10.5 years old'))

    def test_decision_needs_native_and_runner_up_margins(self):
        self.assertEqual(fonts.outline_decision('5', {'5': .35, '=': .96, ':': .63}), ('replaced', '='))
        self.assertEqual(fonts.outline_decision('w', {'w': .35, '~': .75, '∼': .73}), ('uncertain', 'w'))
        self.assertEqual(fonts.outline_decision('l', {'l': .52, '1': .82, 'I': .81}), ('unchanged', 'l'))
        self.assertEqual(fonts.outline_decision('w', {'w': .8, '~': .9}), ('confirmed', 'w'))
        self.assertEqual(fonts.outline_decision('5', {'5': .1, '=': .6}), ('unchanged', '5'))

    def page(self, status='replaced'):
        before, after, scores = ('5', '=', {'5': .35, '=': .96, ':': .63}) if status == 'replaced' else ('w', 'w', {'w': .35, '~': .75, '∼': .73})
        sub = dict(model=fonts.OUTLINE_MODEL, font='subset+face', source_code=53, before=before,
                   after=after, status=status, offset=0, char_id=0)
        proof = dict(sub, scores=scores)
        return dict(page=2, fonts={'subset+face': {'outline_verification': {'53': proof}}},
                    elements=[dict(id='run:7', kind='text', text=before, char_ids=[0],
                                   **{'font_subs' if status == 'replaced' else 'outline_warnings': [sub]})],
                    _table_chars=[dict(text=before, font='subset+face', source_code=53)])

    def test_applies_to_prose_and_cells_with_place(self):
        p = self.page(); warnings = []; fonts.apply_copy([p], warnings)
        self.assertEqual(p['elements'][0]['text'], '=')
        self.assertEqual(p['_table_chars'][0]['text'], '=')
        self.assertIn('page 2, run:7', warnings[0])
        self.assertIn("'5' corrected to '='", warnings[0])

    def test_uncertain_keeps_text_and_identifies_place(self):
        p = self.page('uncertain'); warnings = []; fonts.apply_copy([p], warnings)
        self.assertEqual(p['elements'][0]['text'], 'w')
        self.assertEqual(p['_table_chars'][0]['text'], 'w')
        self.assertIn('retained, unresolved', warnings[0])
        self.assertIn('page 2, run:7', warnings[0])

    def test_digit_with_ambiguous_non_digit_outline_is_not_a_value(self):
        p=self.page();e=p['elements'][0];sub=e['font_subs'][0]
        scores={'5':.2,'′':.74,',':.75}
        sub.update(status='rejected',after='�')
        p['fonts']['subset+face']['outline_verification']['53'].update(sub,scores=scores)
        warnings=[];fonts.apply_copy([p],warnings)
        self.assertEqual(e['text'],'�')
        self.assertEqual(p['_table_chars'][0]['text'],'�')
        self.assertIn('non-digit outline; shown as �',warnings[0])
        self.assertEqual(fonts.outline_decision('5',{'5':.2,'′':.91,',':.7}),('replaced','′'))
        self.assertEqual(fonts.outline_decision('5',{'5':.2,'3':.75,'′':.65}),('uncertain','5'))

    def test_saved_retained_digit_warning_uses_the_current_copy_policy(self):
        p=self.page();e=p['elements'][0];sub=e.pop('font_subs')[0]
        sub.update(status='uncertain',after='5')
        e['outline_warnings']=[sub]
        p['fonts']['subset+face']['outline_verification']['53'].update(sub,scores={'5':.2,'′':.74,',':.75})
        original=copy.deepcopy(p);warnings=[];fonts.apply_copy([p],warnings)
        self.assertEqual(e['text'],'�');self.assertEqual(p['_table_chars'][0]['text'],'�')
        self.assertEqual(len(warnings),1)
        original['_table_chars'][0]['source_code']=54
        warnings=[];fonts.apply_copy([original],warnings)
        self.assertEqual(original['elements'][0]['text'],'5');self.assertEqual(warnings,[])

    def test_non_digit_ocr_is_revalidated_before_ambiguous_outline_rejection(self):
        p=self.page();e=p['elements'][0];sub=e['font_subs'][0]
        sub.update(status='rejected',after='�',previous=[dict(offset=0,char_id=0,before='5',
                   after='−',font='subset+face')])
        p['fonts']['subset+face']['outline_verification']['53'].update(sub,scores={'5':.2,'−':.75,'–':.74})
        p['fonts']['subset+face']['checks']={'5':dict(after='−',wins=3,samples=3,status='untrusted')}
        original=copy.deepcopy(p);warnings=[];fonts.apply_copy([p],warnings)
        self.assertEqual(e['text'],'−');self.assertEqual(p['_table_chars'][0]['text'],'−')
        original['fonts']['subset+face']['checks']['5']['wins']=2
        warnings=[];fonts.apply_copy([original],warnings)
        self.assertEqual(original['elements'][0]['text'],'�')
        self.assertIn('non-digit outline',warnings[0])

    def test_stale_or_invalid_evidence_is_rejected(self):
        for key, value in [('char_id', 1), ('font', 'another'), ('source_code', 54), ('after', '~'), ('status', 'confirmed')]:
            p = self.page(); p['elements'][0]['font_subs'][0][key] = value
            warnings = []; fonts.apply_copy([p], warnings)
            self.assertEqual(p['elements'][0]['text'], '5'); self.assertEqual(warnings, [])
        p = self.page(); p['fonts']['subset+face']['outline_verification']['53']['scores']['='] = float('nan')
        warnings = []; fonts.apply_copy([p], warnings)
        self.assertEqual(p['elements'][0]['text'], '5'); self.assertEqual(warnings, [])

    def test_table_source_code_must_match_even_when_offsets_do(self):
        p = self.page(); p['_table_chars'][0]['source_code'] = 999
        warnings = []; fonts.apply_copy([p], warnings)
        self.assertEqual(p['elements'][0]['text'], '5'); self.assertEqual(warnings, [])

    def test_reference_shapes_are_finite_and_match_themselves(self):
        refs = fonts.outline_references()
        self.assertTrue(all(ch in refs for ch in 'w5~=abcdefghijklmnopqrstuvwxyz0123456789'))
        for ch, shapes in refs.items():
            for shape in shapes:
                self.assertAlmostEqual(fonts.outline_similarity(shape, shape), 1, places=6)

    def test_two_codes_one_claim_are_decided_and_cached_separately(self):
        refs = fonts.outline_references()
        glyphs = [dict(font='f', source_code=code, before='5', offset=i, char_id=i, box_px=[0, 0, 1, 1])
                  for i, code in enumerate([53]*200+[153])]
        runs = [dict(page=1, id='run:1', source='5'*201, crop_xywh=[0, 0, 201, 10], font_glyphs=glyphs)]
        doc = SimpleNamespace(fonts={1: SimpleNamespace(basefont='f')})
        with patch.object(fonts, 'outline_shape', side_effect=lambda f, c: refs['5'][0] if c == 53 else refs['='][0]) as measure:
            report = fonts.verify_outlines(doc, runs)
        self.assertEqual(measure.call_count, 2)
        self.assertEqual(len(report['records']), 1)
        record = report['records'][0]
        self.assertEqual((record['source_code'], record['before'], record['after']), (153, '5', '='))
        self.assertIn('duplicate claim', record['reasons'])
        self.assertEqual(len(record['places']), 1)

    def test_colliding_subset_names_with_different_outlines_abstain(self):
        refs = fonts.outline_references()
        runs = [dict(page=1, id='run:1', source='5', crop_xywh=[0, 0, 10, 10], font_glyphs=[
            dict(font='f', source_code=53, before='5', offset=0, char_id=0, box_px=[0, 0, 1, 1])])]
        doc = SimpleNamespace(fonts={i: SimpleNamespace(basefont='f') for i in (1, 2)})
        with patch.object(fonts, 'outline_shape', side_effect=[refs['5'][0], refs['='][0]]):
            self.assertEqual(fonts.verify_outlines(doc, runs)['records'], [])

    def test_small_caps_and_plain_stems_are_supported_native_designs(self):
        refs = fonts.outline_references()
        for lower, upper in [('a', 'A'), ('n', 'N'), ('t', 'T')]:
            self.assertEqual(max(fonts.outline_similarity(refs[upper][0], r) for r in refs[lower]), 1)
        for ch in '1Il|':
            self.assertEqual(max(fonts.outline_similarity(refs['/'][0], r) for r in refs[ch]), 1)

    def test_truetype_contours_do_not_require_advance_metrics(self):
        if 'fontTools.pens.basePen' not in sys.modules:
            spec = importlib.util.spec_from_file_location('_outline_reader', fonts.ROOT/'standalone/element_boxer_sc.py')
            reader = importlib.util.module_from_spec(spec); sys.modules[spec.name] = reader; spec.loader.exec_module(reader)
        class Rectangle:
            def draw(self, pen, glyf):
                pen.moveTo((0, 0)); pen.lineTo((600, 0)); pen.lineTo((600, 100)); pen.lineTo((0, 100)); pen.closePath()
        class Composite:
            def draw(self, pen, glyf):
                pen.addComponent('bar', (1, 0, 0, 1, 0, 0))
                pen.addComponent('bar', (1, 0, 0, 1, 0, 250))
        class FontTables:
            def __getitem__(self, name):
                if name != 'glyf': raise AssertionError('advance metrics must not be loaded')
                return {'bar': Rectangle(), 'equal': Composite()}
        prog = SimpleNamespace(kind='truetype', tt=FontTables(), order=['.notdef', 'bar', 'equal'])
        font = SimpleNamespace(prog=prog, cid=False, gmap={53: 2})
        shape = fonts.outline_shape(font, 53)
        self.assertAlmostEqual(shape[1], 600/350)
        self.assertTrue(.5 < shape[2] < .65)
        refs = fonts.outline_references()
        self.assertGreater(max(fonts.outline_similarity(shape, ref) for ref in refs['=']), .75)


if __name__ == '__main__': unittest.main()
