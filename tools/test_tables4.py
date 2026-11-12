"""Printed table frames, neighbouring prose and native rotated-page notes."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('test_table_recovery.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
c,run,page=fixture.c,fixture.run,fixture.page


def rules(left,top,right,bottom,closed=True):
    boxes=[[left,y,right,y+.2] for y in (top,top+20,bottom)]
    if closed:boxes += [[x,top,x+.2,bottom+.2] for x in (left,right)]
    return [dict(id='border:'+str(b),kind='rule',box_px=b) for b in boxes]


class TableEdges(unittest.TestCase):
    def test_art_frame_with_two_columns_recovers_captionless_table(self):
        cells=[run(text,x,y,50) for y in (35,55,75) for x,text in [(10,'First'),(160,'Value')]]
        prose=run('An ordinary paragraph outside the framed table continues here.',0,120,230)
        p=page(cells+[prose]);p['art']=rules(0,20,240,100)
        c.recover_bordered_table_regions(p,[],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})
        self.assertTrue(p['tables'][0]['_copy_exact'])
        self.assertNotIn(prose['id'],p['tables'][0]['members'])

    def test_single_column_box_is_not_a_table(self):
        p=page([run('A sentence inside a boxed paragraph.',10,y,210) for y in (35,55,75)])
        p['art']=rules(0,20,240,100)
        c.recover_bordered_table_regions(p,[],10)
        self.assertFalse(p['tables'])

    def test_two_bottom_captions_partition_a_broad_seed(self):
        cells=[];caps=[];borders=[]
        for i,top in enumerate((20,160)):
            cells += [run(text,x,y,50) for y in (top+15,top+35,top+55)
                      for x,text in [(10,'Label'),(160,str(i+5))]]
            caps.append(run('Table '+str(i+1)+'. Results',0,top+90,220))
            borders += rules(0,top,240,top+80)
        p=page(cells+caps+borders)
        p['tables']=[dict(id='broad',angle=0,box_px=[0,20,240,270],members=[e['id'] for e in cells+caps])]
        p['floats']=[dict(caption=caps[0]['text'],blocks=['broad'],box_px=[0,20,240,270])]
        c.recover_bordered_table_regions(p,caps,10)
        self.assertEqual(len(p['tables']),2)
        self.assertEqual({m for t in p['tables'] for m in t['members']},{e['id'] for e in cells})
        for t,f in zip(p['tables'],p['floats']):
            self.assertEqual(len(t['members']),6)
            self.assertEqual(len(f['_caption_ids']),1)

    def test_open_table_does_not_take_the_side_body_column(self):
        cap=run('Table 3.',100,0,60)
        cells=[run(text,x,y,45) for y in (35,55,75) for x,text in [(110,'Label'),(260,'Value')]]
        side=[run('A neighbouring body line',0,y,80) for y in (35,55,75)]
        p=page([cap]+cells+side+rules(100,20,340,100,False))
        for e in cells:e['run_size_px']=8
        p['tables']=[dict(id='t',angle=0,box_px=[0,20,340,100],members=[e['id'] for e in cells+side])]
        p['floats']=[dict(caption='Table 3.',blocks=['t'],box_px=[0,0,340,100])]
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})

    def test_body_below_removed_rules_is_not_a_caption_gate_line(self):
        cap=run('Table 3. Results',0,0,200)
        cells=[run(text,x,y,60) for y in (35,55,75) for x,text in [(10,'Label'),(160,'Value')]]
        prose=run('The following paragraph starts with this complete ordinary sentence.',0,120,230)
        p=page([cap]+cells+[prose]);p['art']=rules(0,20,240,100,False)
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})

    def test_open_table_final_questions_remain_rows_before_closing_rule(self):
        cells=[run(text,x,y,100) for y in (25,45,65) for x,text in [(10,'Question'),(180,'Result')]]
        cells += [run('Was the outcome clearly described?',10,85,150),run('Were the findings useful?',10,105,150)]
        p=page(cells+rules(0,15,300,120,False))
        rows,notes=c.table_rows(cells,10,p)
        self.assertFalse(notes)
        self.assertEqual(rows[-2][0],['Was the outcome clearly described?'])
        self.assertEqual(rows[-1][0],['Were the findings useful?'])

    def test_rotated_display_bounds_do_not_clip_native_values_or_notes(self):
        chars=[];es=[]
        def text(value,x,y):
            cs=[]
            for ch in value:
                if ch==' ':
                    if cs:cs[-1]['space_after']=True
                    x+=3;continue
                cs.append(dict(text=ch,x0=y,y0=200-x-3,x1=y+5,y1=200-x,
                    origin=(y+5,200-x),adv_x1=y+5,adv_y1=200-x-3,
                    hidden=False,angle=90,size=5,font='Regular'));x+=3
            chars.extend(cs)
            kept=[ch for ch in cs if ch['y1']>=0]
            if kept:
                es.append(dict(id='r'+str(len(es)),kind='text',text=value[:len(kept)] if len(kept)<len(cs) else value,
                    _chars=kept,box_px=c.hull([ch['x0'],ch['y0'],ch['x1'],ch['y1']] for ch in kept),
                    angle=90,line=len(es),size_px=5,run_size_px=5))
        text('Table 3',30,65)
        for y in (90,110,130):text('Label',30,y);text('Value',240,y)
        text('Complete note',210,180)
        saved=[ch for ch in chars if ch['y1']>=0]
        for e in es:e['char_ids']=[saved.index(ch) for ch in e['_chars']]
        p=dict(page=1,elements=es,tables=[],floats=[],blocks=[],main_text={},
               region_box_px=[0,0,300,200],params=dict(dpi=72),_table_pdf='fixture',_table_chars=saved,
               art=rules(20,60,280,170))
        doc=SimpleNamespace(pages=[SimpleNamespace(rotate=90,mediabox=(0,0,200,300))],
                            page_size=lambda n:(300,200,(0,0,200,300)))
        reader=SimpleNamespace(sc_doc=lambda path:doc,sc_read_page=lambda path,n:(chars,[],{}))
        with patch.dict(c.sys.modules,{'_copy_table_reader':reader}):
            c.recover_page_rotated_tables([p],5)
        self.assertEqual(len(p['tables']),1)
        selected=[e for e in p['elements'] if e.get('id') in p['tables'][0]['members']]
        source=c.table_source(selected,p)
        self.assertEqual([line['text'] for line in source['lines']],['Label Value']*3+['Complete note'])
        self.assertGreater(p['copy_table_parts'][0]['added_characters'],0)

    def test_neighbouring_prose_does_not_shorten_table_frame(self):
        cap=run('Table 3. Results',0,0,200)
        cells=[run(text,x,y,50) for y in range(35,176,20) for x,text in [(10,'Label'),(160,'Value')]]
        prose=run('The following paragraph continues in the adjacent column beyond this table.',280,100,230)
        prose['run_size_px']=10
        p=page([cap]+cells+[prose]+rules(0,20,240,200,False))
        for e in cells:e['run_size_px']=8
        p['main_text']['columns']=[(0,240),(280,520)]
        p['tables']=[dict(id='broad',angle=0,box_px=[0,20,520,200],members=[e['id'] for e in cells+[prose]])]
        p['floats']=[dict(id='f',caption=cap['text'],blocks=['broad'],box_px=[0,0,520,200])]
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})
        self.assertTrue(p['tables'][0]['_copy_exact'])
    def test_side_by_side_frames_have_distinct_ids(self):
        caps=[run('Table '+str(i+1)+'. Results',x,0,220) for i,x in enumerate((0,280))]
        sets=[[run(text,x+dx,y,50) for y in (35,55,75) for dx,text in [(10,'Label'),(160,'Value')]] for x in (0,280)]
        cells=sets[0]+sets[1]
        p=page(caps+cells+rules(0,20,240,100,False)+rules(280,20,520,100,False))
        p['tables']=[dict(id='broad',angle=0,box_px=[0,0,520,100],members=[e['id'] for e in caps+cells])]
        p['tables'] += [dict(id='t'+str(i),angle=0,box_px=[x,20,x+240,100],members=[e['id'] for e in es]) for i,(x,es) in enumerate(zip((0,280),sets))]
        p['floats']=[dict(id='f',caption=caps[0]['text'],blocks=[t['id'] for t in p['tables']],box_px=[0,0,520,100])]
        c.recover_bordered_table_regions(p,caps,10)
        self.assertEqual(len(p['tables']),2)
        self.assertEqual(len({t['id'] for t in p['tables']}),2)
        self.assertEqual({f['caption'] for f in p['floats']},{e['text'] for e in caps})
        for f in p['floats']:
            self.assertEqual(len([t for t in p['tables'] if t['id'] in f['blocks']]),1)
    def test_header_above_first_rule_stays_with_recovered_rows(self):
        cap=run('Table 3. Results',0,0,200)
        headers=[run('Heading',10,15,80),run('Value heading',160,15,70)]
        cells=[run(text,x,y,50) for y in (45,65,85) for x,text in [(10,'Label'),(160,'Value')]]
        side=run('A neighbouring body paragraph continues in another column.',280,45,230)
        p=page([cap]+headers+cells+[side]+rules(0,30,240,100,False))
        side['run_size_px']=12
        for e in cells:e['run_size_px']=8
        p['tables']=[dict(id='seed',angle=0,box_px=[0,15,510,100],members=[e['id'] for e in cells+[side]])]
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in headers+cells})
        self.assertTrue(p['tables'][0]['_copy_exact'])

    def test_complete_unfloated_seed_keeps_its_grid(self):
        cap=run('Table 3. Results',0,0,200)
        cells=[run(text,x,y,50) for y in (35,55,75) for x,text in [(10,'Label'),(160,'Value')]]
        p=page([cap]+cells+rules(0,20,240,100,False))
        seed=dict(id='seed',angle=0,box_px=[0,20,240,100],members=[e['id'] for e in cells])
        p['tables']=[copy.deepcopy(seed)]
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(p['tables'],[seed])
        self.assertFalse(p['floats'])

    def test_closing_rule_does_not_turn_a_wrapped_note_into_rows(self):
        cells=[run(text,x,y,100) for y in (25,45,65) for x,text in [(10,'Question'),(180,'Result')]]
        cells += [run('Notes: the explanatory text spans the entire table width.',10,85,270),
                  run('continued here.',10,105,80)]
        p=page(cells+rules(0,15,300,120,False))
        rows,notes=c.table_rows(cells,10,p)
        self.assertEqual(notes,['Notes: the explanatory text spans the entire table width.','continued here.'])
        self.assertEqual(len(rows),3)

    def test_overlapping_frame_evidence_is_not_a_second_table(self):
        cap=run('Table 3. Results',0,0,200)
        cells=[run(text,x,y,50) for y in (75,95,115) for x,text in [(10,'Label'),(160,'Value')]]
        p=page([cap]+cells+rules(0,60,240,140))
        seed=dict(id='seed',angle=0,box_px=[0,60,240,140],members=[e['id'] for e in cells])
        floated=dict(id='f',caption=cap['text'],blocks=['seed'],box_px=[0,0,240,140])
        p['tables']=[copy.deepcopy(seed)];p['floats']=[copy.deepcopy(floated)]
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(p['tables'],[seed])
        self.assertEqual(p['floats'],[floated])
    def test_footer_outside_open_frame_does_not_replace_a_grid(self):
        cap=run('Table 3. Results',0,0,200)
        cells=[run(text,x,y,50) for y in (35,55,75) for x,text in [(10,'Label'),(160,'Value')]]
        footer=run('Journal footer',280,120,220)
        p=page([cap]+cells+[footer]+rules(0,20,240,100,False))
        footer['run_size_px']=12
        p['main_text']['furniture']=[dict(members=[footer['id']])]
        seed=dict(id='seed',angle=0,box_px=[0,20,240,130],members=[e['id'] for e in cells+[footer]])
        p['tables']=[copy.deepcopy(seed)]
        p['floats']=[dict(caption=cap['text'],blocks=['seed'],box_px=[0,0,240,130])]
        c.recover_bordered_table_regions(p,[cap],10)
        self.assertEqual(p['tables'],[seed])

    def test_body_release_precedes_exact_border_recovery(self):
        cap=run('Table 3. Results',0,0,200)
        cells=[run(text,x,y,50) for y in (35,55,75) for x,text in [(10,'Label'),(160,'Value')]]
        prose=run('The following paragraph continues with ordinary words below the table.',0,120,230)
        p=page([cap]+cells+[prose]+rules(0,20,240,100,False))
        for e in cells:e['run_size_px']=8
        p['main_text']['columns']=[(0,240)]
        p['tables']=[dict(id='seed',angle=0,box_px=[0,20,240,130],members=[e['id'] for e in cells+[prose]])]
        p['floats']=[dict(caption=cap['text'],blocks=['seed'],box_px=[0,0,240,130])]
        result=c.table_float_regions(p,10)
        self.assertFalse(result['tables'][0].get('_copy_exact'))
        self.assertNotIn(prose['id'],result['tables'][0]['members'])
        self.assertTrue(any(prose['id'] in b['members'] and b['id'].startswith('copy:released:') for b in result['blocks']))

    def test_closed_frame_reclaims_cells_and_bare_caption_from_furniture(self):
        cells=[run(text,x,y,50) for y in (35,55,75) for x,text in [(10,'Label'),(160,'Value')]]
        cap=run('Table 3',0,110,80)
        p=page(cells+[cap]+rules(0,20,240,100))
        hidden=[cells[0]['id'],cells[2]['id'],cap['id']]
        p['main_text']['furniture']=[dict(members=hidden,why='recurring manuscript block')]
        p['tables']=[dict(id='seed',angle=0,box_px=[0,20,240,120],members=[e['id'] for e in cells+[cap]])]
        p['floats']=[dict(id='f',caption=cap['text'],blocks=['seed'],box_px=[0,20,240,120])]
        c.recover_bordered_table_regions(p,[],10)
        self.assertEqual(p['floats'][0]['caption'],'Table 3.')
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})
        self.assertFalse(set(hidden).intersection(c.table_furniture(p)))


if __name__=='__main__':unittest.main()
