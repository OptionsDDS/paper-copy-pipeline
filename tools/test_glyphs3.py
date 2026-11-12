"""Font/code repairs preserve honest letters and require native glyph evidence."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
fonts=module('_glyphs3_fonts',ROOT/'tools/check_fonts.py')
export=fonts.signs.copy

def shape(points, aspect):
    return (sum(1<<((y+4)*40+x+4) for x,y in points),aspect,len(points)/1024)

def arrow():
    points={(x,y) for y in range(32) for x in (15,16)}
    for y in range(22,31):
        left=round((y-22)*15/8)
        points.update((x,y) for x in range(left,min(left+3,17)))
        points.update((31-x,y) for x in range(left,min(left+3,17)))
    return points

class GlyphRepairs(unittest.TestCase):
    def test_dash_requires_solid_midline_bar_and_font_length(self):
        bar=shape({(x,y) for x in range(32) for y in range(32)},12.5)
        metrics=dict(bounds_em=[.05,.326,.7,.274],advance_em=.75)
        for before in 'edz':
            self.assertEqual(fonts.outline_decision(before,{before:.48},shape=bar,geometry=metrics),('replaced','–'))
        em=shape({(x,y) for x in range(32) for y in range(32)},.9/.052)
        self.assertEqual(fonts.outline_dash(em,dict(bounds_em=[.05,.326,.95,.274],advance_em=1)), '—')
        for bounds,advance in [([.05,-.05,.7,-.102],.75),([.05,.326,.35,.274],.4),([.05,.326,.7,.274],.85)]:
            self.assertIsNone(fonts.outline_dash(bar,dict(bounds_em=bounds,advance_em=advance)))
        self.assertEqual(fonts.outline_decision('_',{'_':.48},shape=bar,geometry=metrics),('unchanged','_'))
        self.assertIsNone(fonts.outline_dash(bar,dict(metrics,advance_em=float('nan'))))
        self.assertIsNone(fonts.outline_dash((hex(bar[0]),12.5,.5),metrics))

    def test_honest_letters_with_same_code_keep_their_reading(self):
        for before in 'ed':
            sh=fonts.outline_references()[before][0]
            self.assertEqual(fonts.outline_decision(before,{before:1},shape=sh,
                geometry=dict(bounds_em=[.05,.326,.7,.274],advance_em=.75)),('confirmed',before))

    def test_each_code_in_one_font_is_decided_separately(self):
        bar=shape({(x,y) for x in range(32) for y in range(32)},12.5)
        letter=fonts.outline_references()['e'][0]
        font=SimpleNamespace(basefont='F',bbox=lambda code:(50,326,700,274),width=lambda code:750)
        runs=[dict(page=1,id='run:1',source='ee',crop_xywh=[0,0,20,10],font_glyphs=[
            dict(font='F',source_code=code,before='e',offset=i,char_id=i,box_px=[0,0,10,10])
            for i,code in enumerate((1,2))])]
        with patch.object(fonts,'outline_shape',side_effect=lambda f,c:letter if c==1 else bar):
            report=fonts.verify_outlines(SimpleNamespace(fonts={1:font}),runs)
        self.assertEqual([(r['source_code'],r['after']) for r in report['records']],[(2,'–')])
        self.assertEqual(report['measured'],2)

    def test_arrow_topology_accepts_four_directions(self):
        points=arrow()
        for ch,pts,ratio in [('↓',points,.52),('↑',{(x,31-y) for x,y in points},.52),
                            ('→',{(y,x) for x,y in points},1/.52),('←',{(31-y,x) for x,y in points},1/.52)]:
            sh=shape(pts,ratio)
            self.assertEqual(fonts.outline_arrow(sh),ch)
            self.assertEqual(fonts.outline_decision('#',{'#':.12,ch:.49,'†':.46},shape=sh,symbol=True),('replaced',ch))
            self.assertNotEqual(fonts.outline_decision('#',{'#':.12,ch:.49},shape=sh),('replaced',ch))

    def test_arrow_abstains_and_flags_unproved_symbol_punctuation(self):
        points=arrow()
        points.update((x,6) for x in range(32))
        self.assertIsNone(fonts.outline_arrow(shape(points,.52)))
        self.assertEqual(fonts.outline_decision('"',{'"':.1,'↑':.49},shape=shape(points,.52),symbol=True),('uncertain','"'))
        for ch in '#"†‡':
            for sh in fonts.outline_references()[ch]:self.assertIsNone(fonts.outline_arrow(sh))

    def test_honest_thin_punctuation_is_not_flagged_by_native_failure_alone(self):
        self.assertEqual(fonts.outline_decision('#',{'#':.396,'→':.202,'←':.201},symbol=True),('unchanged','#'))
        # A recognizable shaft and head with weak template evidence remains
        # unresolved; the code's punctuation label cannot silently survive.
        self.assertEqual(fonts.outline_decision('"',{'"':.1,'↓':.4},shape=shape(arrow(),.52),symbol=True),('uncertain','"'))
        self.assertEqual(fonts.outline_decision('"',{'"':.1},shape=shape(arrow(),.52),symbol=True),('uncertain','"'))

    def test_arrow_warning_preserves_existing_stronger_decisions(self):
        self.assertEqual(fonts.outline_decision('~',{'~':.1,'→':.86,'←':.2},symbol=True),('replaced','→'))
        self.assertEqual(fonts.outline_decision('1',{'1':.1,'→':.75,'←':.65},symbol=True),('rejected','\ufffd'))

    def test_dash_proof_survives_copy_handoff_but_not_stale_metrics(self):
        bar=shape({(x,y) for x in range(32) for y in range(32)},12.5)
        sub=dict(model=fonts.OUTLINE_MODEL,font='F',source_code=1,before='e',after='–',status='replaced',offset=1,char_id=1)
        proof=dict(sub,scores={'e':.48},outline=[hex(bar[0]),*bar[1:]],geometry=dict(bounds_em=[.05,.326,.7,.274],advance_em=.75))
        page=dict(page=1,fonts={'F':{'outline_verification':{'1':proof}}},elements=[
            dict(kind='text',id='run:0',text='3e7',char_ids=[0,1,2],font_subs=[sub])],
            _table_chars=[dict(text=t,font='F',source_code=i) for i,t in enumerate('3e7')])
        wrong=copy.deepcopy(page);wrong['fonts']['F']['outline_verification']['1']['geometry']['advance_em']=.4
        notices=[];fonts.apply_copy([wrong],notices)
        self.assertEqual(wrong['elements'][0]['text'],'3e7');self.assertEqual(notices,[])
        notices=[];fonts.apply_copy([page],notices)
        self.assertEqual(page['elements'][0]['text'],'3–7');self.assertEqual(page['_table_chars'][1]['text'],'–')

    def font(self, **kw):
        return SimpleNamespace(prog=object(),_tounicode=lambda code:'',
            selected_glyph_name=lambda code:'T_h',adobe_name=lambda code:'T_h',unicode=lambda code:'T',**kw)

    def test_ligature_respects_explicit_mappings_and_outline_identity(self):
        decode=lambda name:{'T_h':'Th','f_f_i':'ffi'}.get(name,'')
        font=self.font()
        self.assertEqual(export.ligature_reading(font,40,'T',decode),'Th')
        for field,value in [('prog',None),('_tounicode',lambda c:'T'),('adobe_name',lambda c:'T'),
                            ('selected_glyph_name',lambda c:None),('unicode',lambda c:'Th')]:
            bad=copy.copy(font);setattr(bad,field,value)
            self.assertIsNone(export.ligature_reading(bad,40,'T',decode))
        self.assertIsNone(export.ligature_reading(font,None,'T',decode))
        self.assertIsNone(export.ligature_reading(font,40,'Th',decode))

    def test_ligature_expands_private_run_and_table_once(self):
        font=self.font(basefont='F')
        reader=SimpleNamespace(sc_doc=lambda pdf:SimpleNamespace(fonts={1:font}),sc_uni=lambda name:'Th')
        chars=[dict(text=ch,font='F',source_code=40 if ch=='T' else None) for ch in 'Tis']
        page=dict(page=1,_table_pdf='test',_table_chars=chars,elements=[
            dict(id='run:1',kind='text',text='Tis',char_ids=[0,1,2],_chars=chars)])
        with patch.dict(sys.modules,{'_copy_table_reader':reader}):
            warnings=[];export.restore_ligature_text([page],warnings)
            export.restore_ligature_text([page],warnings)
        self.assertEqual(page['elements'][0]['text'],'This')
        self.assertEqual([c['text'] for c in page['_table_chars']],['Th','i','s'])
        self.assertEqual([c['text'] for c in chars],list('Tis'))
        self.assertEqual(page['elements'][0]['char_ids'],[0,1,2]);self.assertEqual(len(warnings),1)

if __name__=='__main__':unittest.main()
