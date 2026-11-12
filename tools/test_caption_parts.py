"""Caption attachment and independent ownership across facing-page spreads."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('test_table_gate.py'))
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
c,run=gate.c,gate.run


class CaptionParts(unittest.TestCase):
    def test_caption_faces_accept_case_spacing_and_roman_numbers(self):
        for label,number in [('table 2','2'),('Table IV','IV'),('t a b l e ix','IX'),('TABLE 3','3')]:
            e=run(label+' Measurements',0,0,120)
            e['font_spans']=[dict(font='Sample-Bold',start=0,end=len(label)),
                             dict(font='Sample-Regular',start=len(label),end=len(e['text']))]
            self.assertTrue(c.styled_table_label(e))
            self.assertEqual(c.label_fix(e['text']),'Table '+number+'. Measurements')
            p=dict(elements=[e],tables=[],floats=[],blocks=[],main_text={})
            self.assertEqual(len(c.table_float_regions(p,10)['floats']),1)

    def test_body_reference_and_later_emphasis_do_not_supply_caption_style(self):
        e=run('Table IV describes the measurements used below.',0,0,200)
        e['font_spans']=[dict(font='Sample-Regular',start=0,end=30),dict(font='Sample-Bold',start=30,end=45)]
        self.assertFalse(c.styled_table_label(e))
        p=dict(elements=[e],tables=[],floats=[],blocks=[],main_text={})
        self.assertEqual(c.table_float_regions(p,10)['floats'],[])

    def test_wrapped_bold_reference_is_not_an_independent_caption(self):
        previous=run('Supporting data for the preceding figures and',0,0,300)
        label=run('Table 7.',0,16,50)
        for e in (previous,label):e['font_spans']=[dict(font='Sample-Bold',start=0,end=len(e['text']))]
        p=dict(elements=[previous,label],tables=[],floats=[],main_text={},
               blocks=[dict(id='paragraph',members=[previous['id'],label['id']])])
        self.assertFalse(c.styled_table_label(label,p))
        self.assertEqual(c.table_float_regions(p,10)['floats'],[])
        # A completed preceding sentence does not veto a new caption.
        previous['text']='A completed preceding paragraph.'
        self.assertTrue(c.styled_table_label(label,p))

    def test_styled_labels_preserve_named_tables_but_split_merged_captions(self):
        left=run('Table 2',10,10,60);right=run('Table 3',210,10,60)
        for e in (left,right):e['font_spans']=[dict(font='Sample-Demi',start=0,end=len(e['text']))]
        p=dict(elements=[left],tables=[dict(id='seed')],blocks=[],
               floats=[dict(caption='Table 2',blocks=['seed'],box_px=[0,0,400,150])])
        self.assertEqual(c.unregistered_table_labels(p),set())
        p['tables']=[]  # An already captioned printed-line gate is also retained.
        self.assertEqual(c.unregistered_table_labels(p),set())
        p['elements'].append(right)
        self.assertEqual(c.unregistered_table_labels(p),{left['id'],right['id']})
        p['floats'][0]['box_px']=[0,0,150,150]
        self.assertEqual(c.unregistered_table_labels(p),{right['id']})

    def test_short_label_uses_side_header_to_keep_wrapped_caption(self):
        cap=run('TABLE 2',0,10,40);title=run('Reported events',50,10,60)
        tail=run('In the experimental population',0,26,150)
        fill=dict(kind='fill',box_px=[180,10,400,50])
        header=run('Column header',190,15,100)
        p=dict(elements=[cap,title,tail,header,fill])
        self.assertEqual(c.table_caption_members(p,cap),[cap['id'],title['id'],tail['id']])

    def test_wide_title_does_not_reclassify_small_drawing_rules_as_missing_grid(self):
        cap=run('TABLE 2',0,0,40);title=run('A long title beside the short label',50,0,250)
        tail=run('A caption continuation with no readable cells below it',0,20,250)
        rules=[dict(kind='rule',box_px=[0,y,90,y]) for y in (30,50)]
        p=dict(elements=[cap,title,tail]+rules,tables=[],floats=[],blocks=[],main_text={})
        self.assertEqual(c.table_float_regions(p,10)['floats'],[])

    def spread(self):
        cap=run('TABLE 4 Treatment options',0,110,180)
        left=[run(t,x,y,70) for y in (145,170,230,285)
              for x,t in ((5,'Modality'),(210,'Benefit'))]
        right=[run(t,x,y,90) for y in (145,170,230,285)
               for x,t in ((5,'Risk'),(160,'Advice'))]
        pages=[]
        for side,rs in enumerate((left,right)):
            width=300 if side==0 else 280
            fills=[dict(kind='fill',box_px=[x,lo,x+width/2,hi])
                   for lo,hi in ((140,160),(220,270)) for x in (0,width/2)]
            page=dict(page=side+1,elements=rs+fills,tables=[],floats=[],blocks=[],
                      region_box_px=[0,0,300,400],main_text={})
            pages.append(page)
        pages[0]['elements'].insert(0,cap)
        pages[0]['tables']=[dict(id='partial',angle=0,box_px=[0,140,300,195],
                                members=[e['id'] for e in left[:4]])]
        pages[0]['floats']=[dict(caption=cap['text'],blocks=['partial'],box_px=[0,110,300,195])]
        pages[1]['elements'].append(dict(kind='rule',box_px=[0,330,280,330]))
        return pages,left,right

    def test_tall_rows_and_two_column_half_keep_all_runs_in_each_reading_frame(self):
        for angle in (0,90,180,270):
            pages,left,right=self.spread()
            for p in pages:
                p['region_box_px']=c.frame(-angle)(p['region_box_px'])
                for e in p['elements']+p['tables']+p['floats']:
                    e['box_px']=c.frame(-angle)(e['box_px'])
                    if e.get('kind')=='text' or e in p['tables']:e['angle']=angle
            c.recover_facing_table_regions(pages,10)
            for p,rs in zip(pages,(left,right)):
                self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in rs})
                self.assertEqual(p['tables'][0]['layout'],'unstructured')
                self.assertEqual(len(p['copy_table_parts'][0]['row_bands']),3)
            self.assertEqual(pages[1]['floats'][0]['caption'],'Table 4 (additional columns)')

    def test_different_bands_missing_border_or_new_caption_cannot_prove_a_half(self):
        for alteration in ('bands','border','caption'):
            pages,_,_=self.spread()
            if alteration=='bands':
                for e in pages[1]['elements']:
                    if e['kind']=='fill' and e['box_px'][1]==220:e['box_px'][3]+=5
            elif alteration=='border':pages[1]['elements']=[e for e in pages[1]['elements'] if e['kind']!='rule']
            else:pages[1]['elements'].append(run('TABLE 5 Separate experiment',0,125,180))
            before=copy.deepcopy(pages)
            c.recover_facing_table_regions(pages,10)
            self.assertEqual(pages,before)

    def test_partition_preserves_an_independent_broad_seed(self):
        pages,_,right=self.spread()
        other=run('Unrelated earlier table',0,50,100)
        pages[1]['elements'].append(other)
        pages[1]['tables']=[dict(id='broad',angle=0,box_px=[0,40,300,350],
                                members=[other['id'],right[0]['id']])]
        c.recover_facing_table_regions(pages,10)
        self.assertEqual(pages[1]['tables'][0]['members'],[other['id']])
        self.assertEqual(set(pages[1]['tables'][1]['members']),{e['id'] for e in right})

    def test_parts_group_by_table_and_do_not_cross_prose(self):
        a=dict(kind='table',page=1,caption='Table 2. First')
        b=dict(kind='table',page=1,caption='Table 3. Second')
        aa=dict(kind='table',page=2,caption='Table 2 (continued)')
        bb=dict(kind='table',page=2,caption='Table 3 (additional columns)')
        marks=[dict(kind='page',page=n) for n in (1,2)]
        source=[a,b,marks[0],aa,bb,marks[1]]
        self.assertEqual(c.group_table_parts(source),[a,aa,b,marks[0],bb,marks[1]])
        para=dict(kind='para',page=1,text='An intervening body paragraph.')
        self.assertEqual(c.group_table_parts([a,b,para,aa,bb]),[a,b,para,aa,bb])
        aa=dict(aa,caption='Table 2. Separate caption')
        self.assertEqual(c.group_table_parts([a,b,aa,bb]),[a,b,aa,bb])


if __name__=='__main__':unittest.main()
