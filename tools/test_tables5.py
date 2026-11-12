"""Caption intervals, sparse sideways continuations and two-column lists."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('test_table_recovery.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
c,run,page=f.c,f.run,f.page


class CaptionIntervals(unittest.TestCase):
    def test_two_column_caption_keeps_paired_lines_before_body(self):
        cap=run('Table 9 Observations',0,0,130);cap['label_font']=True
        cells=[run(t,x,y,90) for y in range(25,166,20)
               for x,t in ((0,'Reference'),(180,'Description'))]
        prose=[run('This following body paragraph remains outside the table.',0,200,300)]
        p=page([cap]+cells+prose)
        for e in cells:e['run_size_px']=8
        q=c.table_float_regions(p,10)
        self.assertEqual(set(q['tables'][0]['members']),{e['id'] for e in cells})
        self.assertTrue(q['tables'][0]['_copy_exact'])
        source=c.table_source(cells,p,preserve_run_lines=True)
        self.assertEqual([r['text'] for r in source['lines']],['Reference Description']*8)

    def test_two_body_columns_are_not_a_small_type_table(self):
        cap=run('Table 9 describes these findings',0,0,130);cap['label_font']=True
        cells=[run(t,x,y,90) for y in range(25,166,20)
               for x,t in ((0,'First paragraph'),(180,'Second paragraph'))]
        p=page([cap]+cells)
        self.assertFalse(c.table_float_regions(p,10)['tables'])

    def test_another_caption_ends_a_paired_table(self):
        cap=run('TABLE 9',0,0,70)
        cells=[run(t,x,y,90) for y in range(25,166,20)
               for x,t in ((0,'Reference'),(180,'Description'))]
        other=run('TABLE 10',0,185,80)
        p=page([cap]+cells+[other,run('Unrelated caption text',180,185,120)])
        for e in cells:e['run_size_px']=8
        c.recover_ruleless_table_regions(p,[cap,other],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})

    def test_matching_rules_recognise_an_italic_caption(self):
        cap=run('Table 9 Observations',0,0,190)
        cells=[run(t,x,y,50) for y in (40,60,80) for x,t in ((0,'Label'),(140,'Result'))]
        bars=[dict(id='bar'+str(y),kind='rule',box_px=[0,y,200,y+.2]) for y in (25,35,95)]
        p=page([cap]+cells+bars)
        p['tables']=[dict(id='grid',angle=0,box_px=[0,25,200,95],members=[e['id'] for e in cells])]
        q=c.table_float_regions(p,10)
        self.assertTrue(any(x['caption'].startswith('Table 9') for x in q['floats']))

    def test_one_shaded_header_is_not_repeated_side_caption_bands(self):
        cap=run('TABLE 9',300,0,80)
        cells=[run(t,x,y,40) for y in (5,25,40,55)
               for x,t in ((50,'First'),(140,'Second'),(220,'Third'))]
        p=page([cap]+cells+[dict(id='shade',kind='fill',box_px=[50,0,280,15])])
        c.recover_side_caption_regions(p,[cap],10)
        self.assertFalse(p['tables'])

    def test_side_caption_note_marker_does_not_match_ordinary_words(self):
        for text,kept in [('The following paragraph is body text.',False),
                          ('the following paragraph is body text.',False),
                          ('a Significant findings.',True)]:
            cap=run('TABLE 9',230,0,80)
            cells=[run(t,x,y,40) for y in (5,35,65) for x,t in ((0,'Label'),(100,'Value'))]
            bands=[dict(id='shade'+str(y),kind='fill',box_px=[0,y,200,y+15]) for y in (0,30,60)]
            following=run(text,0,85,180);following['run_size_px']=9
            p=page([cap]+cells+bands+[dict(id='bottom',kind='rule',box_px=[0,78,200,78.2]),following])
            c.recover_side_caption_regions(p,[cap],10)
            self.assertEqual(following['id'] in p['tables'][0]['members'],kept)

    def test_caption_lower_bound_does_not_borrow_an_earlier_orphan(self):
        cap=run('TABLE 9',0,100,70)
        old=[run(t,x,y,40) for y in (25,45,65) for x,t in ((0,'Earlier'),(140,'Other'))]
        cells=[run(t,x,y,40) for y in (130,150,170) for x,t in ((0,'Label'),(140,'Value'))]
        p=page([cap]+old+cells)
        p['tables']=[dict(id='old',angle=0,box_px=[0,20,200,80],members=[e['id'] for e in old]),
                     dict(id='new',angle=0,box_px=[0,125,200,185],members=[e['id'] for e in cells])]
        p['blocks']=[dict(id='cap',members=[cap['id']],box_px=cap['box_px'])]
        p['floats']=[dict(caption=cap['text'],blocks=['cap','new'],box_px=[0,100,200,185])]
        _,floats,_=c.read_page(p,10,[])
        target=next(t for t in floats if t[2].startswith('Table 9'))
        ids={x['id'] for l in target[5]['table_source']['lines'] for x in l['items']}
        self.assertEqual(ids,{e['id'] for e in cells})

    def test_preserved_grid_only_separates_wrapped_definition_lists(self):
        for texts,separate in [(['N = 50 observations'],False),
                               (['V = one measure'],False),
                               (['V = one measure;', 'W = another measure.'],True)]:
            cap=run('TABLE 9',0,0,80)
            cells=[run(t,x,y,40) for y in (45,65,85) for x,t in ((0,'Label'),(140,'Value'))]
            notes=[run(t,0,110+13*i,190) for i,t in enumerate(texts)]
            for e in cells+notes:e['run_size_px']=8
            bars=[dict(id='bar'+str(y),kind='rule',box_px=[0,y,200,y+.2]) for y in (25,35,105)]
            p=page([cap]+cells+notes+bars)
            p['tables']=[dict(id='grid',angle=0,box_px=[0,25,200,140],members=[e['id'] for e in cells+notes])]
            p['floats']=[dict(caption='Table 9. Findings',blocks=['grid'],box_px=[0,0,200,140])]
            c.recover_bordered_table_regions(p,[cap],10)
            self.assertEqual('_copy_notes_top' in p['tables'][0],separate)


class RotatedContinuations(unittest.TestCase):
    def pages(self,angle=90):
        result=[]
        for n in range(1,5):
            cap=run('Table 9: Findings.' if n==1 else 'Table 9: Continued.',100,0,80)
            cells=[run(t,x,y,45) for y in (35,55,75)
                   for x,t in ((0,'Label'),(100,'Finding'),(220,'Value'))]
            bars=[dict(id='bar'+str(y),kind='rule',box_px=[0,y,280,y+.2]) for y in (25,90)]
            p=page([cap]+cells+bars,n)
            for e in p['elements']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e['kind']=='text':e['angle']=angle
            if n==1:
                p['tables']=[dict(id='t',angle=angle,members=[e['id'] for e in cells],
                                 box_px=c.frame(-angle)([0,25,280,90]))]
                p['floats']=[dict(caption=cap['text'],blocks=['t'],box_px=c.frame(-angle)([0,0,280,90]))]
            result.append(p)
        return result

    def test_centred_caption_and_sparse_first_column_continue_in_both_rotations(self):
        for angle in (90,270):
            pages=self.pages(angle)
            c.recover_rotated_continuations(pages,10)
            self.assertEqual([len(p['tables']) for p in pages],[1,1,1,1])
            for p in pages[1:]:
                self.assertEqual(len(p['tables'][0]['members']),9)
                self.assertEqual(p['tables'][0]['layout'],'unstructured')

    def test_different_number_does_not_inherit_a_table_width(self):
        pages=self.pages();pages[1]['elements'][0]['text']='Table 8: Continued.'
        c.recover_rotated_continuations(pages,10)
        self.assertEqual([len(p['tables']) for p in pages],[1,0,0,0])

    def test_missing_closing_border_does_not_claim_unbounded_text(self):
        pages=self.pages();pages[1]['elements']=[e for e in pages[1]['elements'] if e['id']!='bar90']
        c.recover_rotated_continuations(pages,10)
        self.assertEqual([len(p['tables']) for p in pages],[1,0,0,0])

    def test_continuation_inside_another_named_seed_is_not_duplicated(self):
        pages=self.pages();p=pages[1]
        cells=[e['id'] for e in p['elements'] if e['kind']=='text' and e['id']!=p['elements'][0]['id']]
        p['tables']=[dict(id='broad',angle=90,members=cells,box_px=c.frame(-90)([0,25,280,90]))]
        p['floats']=[dict(caption='Table 10. Other findings',blocks=['broad'],box_px=p['tables'][0]['box_px'])]
        c.recover_rotated_continuations(pages,10)
        self.assertEqual([len(p['tables']) for p in pages],[1,1,1,1])
        self.assertEqual(p['tables'][0]['id'],'broad')


if __name__=='__main__':unittest.main()
