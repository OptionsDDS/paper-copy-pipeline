"""Table/body ownership, caption panels, page furniture and facing-page parts."""
import importlib.util
import copy
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('recovery',Path(__file__).with_name('test_table_recovery.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
c,run,page=r.c,r.run,r.page


class TableBody(unittest.TestCase):
    def test_gate_rejects_repeated_author_year_splits_across_data_rows(self):
        labels=['Study','Smith et al.','(2017)','Jones et al.','(2019)']
        rs=[run(t,x,i*20,80) for i,label in enumerate(labels)
            for x,t in [(0,label),(120,'Arm'+str(i)),(240,str(i))]]
        grid=[[[label],['Arm'+str(i)],[str(i)]] for i,label in enumerate(labels)]
        checks=c.table_structure_checks(grid,c.table_source(rs,page(rs)),'Table 3',[])
        self.assertTrue(checks['cell_contiguity']['fired'])

    def test_unshaded_header_does_not_absorb_the_first_shaded_data_row(self):
        header=[run('Cool',120,0,30),run('Warm',220,0,35)]
        cells=[run(t,x,y,50) for y,values in [(20,('First','120','105')),(40,('Second','62','115')),(60,('Third','394','119'))]
               for x,t in zip([0,120,220],values)]
        fills=[dict(id='band',kind='fill',box_px=[0,15,280,35]),
               dict(id='white_header',kind='fill',box_px=[0,-5,280,15])]
        rules=[dict(id='line',kind='rule',box_px=[0,15,280,15.2])]
        p=page(header+cells+fills+rules);rows,notes=c.table_rows(header+cells,10,p)
        self.assertEqual(rows[0],[[],['Cool'],['Warm']])
        self.assertEqual(rows[1],[['First'],['120'],['105']])

    def test_short_marked_note_after_closing_rule_stays_out_of_cells(self):
        cells=[run(t,x,y,45) for y,values in [(0,('Label','Value')),(20,('First','12')),(40,('Second','15'))]
               for x,t in zip([0,300],values)]
        note=run('*No observations were collected in this interval.',0,65,150)
        tail=run('The observations were collected during all other intervals.',0,80,340)
        doi=run('doi:10.1234/example.0001234.t001',0,95,200)
        p=page(cells+[note,tail,doi,dict(id='rule',kind='rule',box_px=[0,55,350,55.2]),
                      dict(id='header',kind='rule',box_px=[0,15,350,15.2])])
        rows,notes=c.table_rows(cells+[note,tail,doi],10,p)
        self.assertEqual(len(rows),3)
        self.assertIn(note['text'],notes)

    def test_ruled_cells_survive_watermark_classification_with_caption_below(self):
        for angle in (0,90,270):
            head=run('Page head',0,-30,90);cell=run('First cell',10,30,60)
            cap=run('TABLE 3',0,100,60)
            rules=[dict(id='rule'+str(i),kind='rule',box_px=b) for i,b in enumerate(
                [[0,20,150,21],[0,80,150,81],[0,20,1,81],[149,20,150,81]])]
            p=page([head,cell,cap]+rules)
            p['tables']=[dict(id='t',angle=angle,box_px=[0,20,150,110],members=[cell['id'],cap['id']])]
            p['floats']=[dict(caption='Table 3',blocks=['t'])]
            p['main_text']['furniture']=[dict(members=[head['id'],cell['id']])]
            for e in p['elements']+p['tables']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e.get('kind')=='text':e['angle']=angle
            c.recover_drawn_table_content(p,10)
            self.assertEqual(c.table_furniture(p),{head['id']})

    def test_joined_border_releases_a_slightly_larger_sentence_tail(self):
        cells=[run(t,x,y,45) for y in [30,50,70] for x,t in [(0,'Label'),(150,'Value')]]
        prose=run('This ordinary sentence continues the preceding page in a body column.',0,110,210)
        borders=[dict(id='border'+str(i),kind='rule',box_px=[i*55,82,(i+1)*55,82.2]) for i in range(4)]
        p=page(cells+[prose]+borders);p['main_text']['columns']=[[0,220]]
        for e in cells:e['run_size_px']=9.4
        p['tables']=[dict(id='t',angle=0,box_px=[0,20,220,130],members=[e['id'] for e in cells+[prose]])]
        p['floats']=[dict(caption='Table 3',blocks=['t'])]
        c.bound_table_before_body(p,10)
        self.assertNotIn(prose['id'],p['tables'][0]['members'])
        self.assertEqual(p['tables'][0]['_copy_body_bottom'],110)

    def test_alternating_table_bands_reclaim_cells_from_adjacent_figure(self):
        cap=run('TABLE 7',0,0,45);title=run('A printed caption',55,0,140)
        cells=[run(t,x,y,35) for y in [30,50,70,90,110] for x,t in [(5,'Year'),(150,'Value')]]
        bands=[dict(id='band'+str(y),kind='fill',box_px=[0,y,210,y+20]) for y in [25,65,105]]
        image=dict(id='image',kind='image',box_px=[250,65,450,125])
        figcap=run('FIGURE 4',250,135,100)
        p=page([cap,title,*cells,*bands,image,figcap])
        owned=[e['id'] for e in cells[4:]]+['image']
        p['blocks']=[dict(id='lettering',members=owned,box_px=[0,65,450,125]),
                     dict(id='figcap',members=[figcap['id']],box_px=figcap['box_px'])]
        p['floats']=[dict(caption='FIGURE 4',blocks=['lettering','figcap'],members=owned,
                         lettering=[e['id'] for e in cells[4:]],box_px=[0,65,450,145])]
        c.recover_shaded_table_ownership(p,[cap,figcap],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells})
        figure=next(f for f in p['floats'] if f['caption']=='FIGURE 4')
        self.assertEqual(figure['lettering'],[])
        self.assertEqual(figure['box_px'][0],250)
        self.assertEqual(p['floats'][-1]['_caption_ids'],[cap['id'],title['id']])

    def test_closing_rule_releases_body_but_retains_smaller_notes(self):
        cells=[run(t,x,y,45) for y in [30,50,70] for x,t in [(0,'Label'),(150,'Value')]]
        note=run('The smaller printed note is retained with the table.',0,90,210)
        prose=run('This larger ordinary sentence belongs in the body column.',0,110,210)
        p=page(cells+[note,prose,dict(id='border',kind='rule',box_px=[0,82,220,82.5])])
        p['main_text']['columns']=[[0,220]]
        for e in cells+[note]:e['run_size_px']=8
        t=dict(id='t',angle=0,box_px=[0,20,220,130],members=[e['id'] for e in cells+[note,prose]])
        p['tables']=[t];p['floats']=[dict(caption='Table 3',blocks=['t'])]
        c.bound_table_before_body(p,10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells+[note]})
        self.assertIn(prose['id'],t['members'])
        cap=run('TABLE 3',0,0,60);header=run('An omitted header',0,15,180)
        cap.update(size_px=10,run_size_px=10);header.update(size_px=8,run_size_px=8)
        p['elements'].extend([cap,header])
        p['floats'][0].update(_caption_ids=[cap['id']],box_px=[0,0,220,130])
        _,fs,_=c.read_page(p,10,[])
        table=next(f for f in fs if f[1]=='table')
        self.assertIn(note['text'],table[4])
        ids={x['id'] for line in table[5]['table_source']['lines'] for x in line['items']}
        self.assertIn(header['id'],ids)
        self.assertNotIn(prose['id'],ids)

    def test_drawn_header_disproves_recurrence_without_restoring_page_head(self):
        for angle in (0,90,270):
            head=run('A running head',0,-30,90);cap=run('TABLE 3',0,0,60)
            header=run('Number of',0,30,60);cell=run('12 patients',0,60,70)
            fill=dict(id='fill',kind='fill',box_px=[0,20,150,90])
            p=page([head,cap,header,cell,fill])
            p['tables']=[dict(id='t',angle=angle,box_px=[0,20,150,90],members=[header['id'],cell['id']])]
            p['floats']=[dict(caption='Table 3',blocks=['t'],_caption_ids=[cap['id']])]
            p['main_text']['furniture']=[dict(members=[head['id'],header['id']])]
            for e in p['elements']+p['tables']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e.get('kind')=='text':e['angle']=angle
            c.recover_drawn_table_content(p,10)
            self.assertEqual(c.table_furniture(p),{head['id']})

    def test_shaded_footer_below_data_does_not_become_a_table_header(self):
        cap=run('TABLE 3',0,0,60);header=run('Column',0,30,60)
        footer=run('Journal footer',0,150,90)
        fills=[dict(id='h',kind='fill',box_px=[0,20,150,50]),
               dict(id='f',kind='fill',box_px=[0,140,150,170])]
        p=page([cap,header,footer]+fills)
        p['tables']=[dict(id='t',angle=0,box_px=[0,20,150,170],members=[header['id']])]
        p['floats']=[dict(caption='Table 3',blocks=['t'],_caption_ids=[cap['id']])]
        p['main_text']['furniture']=[dict(members=[header['id'],footer['id']])]
        c.recover_drawn_table_content(p,10)
        self.assertEqual(c.table_furniture(p),{footer['id']})

    def test_only_repeated_page_furniture_above_caption_is_rejected(self):
        pages=[]
        for i in range(3):
            head=run('A running head',0,0,90);cap=run('TABLE 3',0,40,60)
            cells=[run(t,x,y,30) for y in [70,90] for x,t in [(0,'Label'),(100,'Value')]]
            p=page([head,cap]+cells,i+1)
            if i<2:p['main_text']['furniture']=[dict(members=[head['id']])]
            else:p['tables']=[dict(id='t',angle=0,box_px=[0,0,200,100],members=[e['id'] for e in cells])]
            pages.append(p)
        c.recover_table_frame_furniture(pages)
        self.assertEqual(c.table_furniture(pages[-1]),{head['id']})
        self.assertNotIn(cap['id'],c.table_furniture(pages[-1]))

    def test_detected_right_half_with_group_gaps_and_strain_names_is_a_part(self):
        caps=[run('TABLE 3',0,0,80),run('An entire caption',90,0,150)]
        bands=[dict(id='band'+str(y),kind='fill',box_px=[0,y,300,y+20]) for y in [20,60,100]]
        cells=[run(t,x,y,55) for y in [25,65,105] for x,t in [(0,'Label'),(120,'YIT 12345'),(230,'Result')]]
        p=page(caps+cells+bands)
        p['blocks']=[dict(id='cap',members=[e['id'] for e in caps],box_px=[0,0,240,10])]
        p['tables']=[dict(id='t',angle=0,box_px=[0,20,300,120],members=[e['id'] for e in cells])]
        p['floats']=[dict(caption='TABLE 3',blocks=['cap','t'],box_px=[0,0,300,120])]
        q=page(copy.deepcopy(cells+bands),2)
        q['tables']=[dict(id='incomplete',angle=0,box_px=[0,0,300,120],members=[e['id'] for e in cells])]
        q['blocks']=[dict(id='escaped',members=[e['id'] for e in cells])]
        q['main_text']['blocks']=[dict(id='escaped',order=1)]
        complete=copy.deepcopy(q)
        complete['main_text']['blocks']=[]
        c.recover_table_column_parts([copy.deepcopy(p),complete],10)
        self.assertEqual(complete['tables'][0]['id'],'incomplete')
        self.assertNotIn('layout',complete['tables'][0])
        marker=run('(Continues)',230,115,60)
        complete['elements'].append(marker)
        complete['blocks']=[dict(id='marker',members=[marker['id']])]
        complete['main_text']['blocks']=[dict(id='marker',order=1)]
        c.recover_table_column_parts([copy.deepcopy(p),complete],10)
        self.assertNotIn('layout',complete['tables'][0])
        c.recover_table_column_parts([p,q],10)
        self.assertEqual(len(q['tables']),1)
        self.assertEqual(q['tables'][0]['layout'],'unstructured')
        self.assertEqual(set(q['tables'][0]['members']),{e['id'] for e in cells})

    def test_full_width_table_stops_at_two_body_columns(self):
        cap=run('Table 3 Results',0,0,160);cap['label_font']=True
        cells=[run(t,x,y,70) for y in [30,50,70] for x,t in [(0,'First cell'),(150,'Second cell')]]
        prose=[run('This ordinary sentence fills the following body column.',x,y,130)
               for y in [100,115,130] for x in [0,150]]
        fills=[dict(id='cap',kind='fill',box_px=[0,-5,290,20])]+[
            dict(id='header'+str(x),kind='fill',box_px=[x,20,x+145,45]) for x in [0,145]]
        p=page([cap]+cells+prose+fills);p['main_text']['columns']=[[0,130],[150,290]]
        for e in cells:e['run_size_px']=8
        for e in prose:e['_faces']={'Regular':20}
        p['_body_face']='Regular'
        result=c.table_float_regions(p,10)
        self.assertEqual(set(result['tables'][0]['members']),{e['id'] for e in cells})

    def test_panel_caption_keeps_deeply_indented_continuations(self):
        cap=run('Table 3 A title',0,0,180)
        tail=run('continued title',60,15,90)
        header=run('Header',60,40,60)
        panel=dict(id='panel',kind='fill',box_px=[0,-5,200,30])
        p=page([cap,tail,header,panel])
        self.assertEqual(c.table_caption_members(p,cap),[cap['id'],tail['id']])

    def test_inline_emphasis_does_not_truncate_a_wrapped_caption(self):
        cap=run('Table 3 The complete caption',0,0,200)
        tail=run('with one emphasized word in this continuation',0,15,200)
        header=run('A different header',0,35,130)
        p=page([cap,tail,header])
        cap['_faces']={'Regular':28};tail['_faces']={'Regular':35,'Italic':10}
        header['_faces']={'Bold':18}
        self.assertEqual(c.table_caption_members(p,cap),[cap['id'],tail['id']])

    def test_caption_panel_stops_before_a_following_figure(self):
        cap=run('Table 3 Results',0,0,160)
        cells=[run(t,x,y,50) for y in [30,50,70] for x,t in [(0,'First'),(150,'Second')]]
        note=run('A note beneath the closing row.',0,90,220)
        art=[run('20',0,110,20),run('10',0,130,20),run('Figure 2 Results',0,150,180)]
        fills=[dict(id='cap',kind='fill',box_px=[0,-5,290,20])]+[
            dict(id='header'+str(x),kind='fill',box_px=[x,20,x+145,45]) for x in [0,145]]
        p=page([cap]+cells+[note]+art+fills)
        p['floats']=[dict(caption='Figure 2',blocks=[],box_px=[0,105,290,170])]
        c.recover_caption_panel_regions(p,[cap,art[-1]],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in cells+[note]})

    def test_conflicting_seed_stops_before_body_below_table_notes(self):
        caps=[run('TABLE '+str(i+1)+'. Results',x,0,180) for i,x in enumerate([0,240])]
        cells=[run(t,x+dx,y,45) for x in [0,240] for y in [30,50,70]
               for dx,t in [(0,'Label'),(100,'Value')]]
        prose=run('The following ordinary sentence belongs in the body column.',0,100,210)
        p=page(caps+cells+[prose]);p['main_text']['columns']=[[0,210],[240,450]]
        for e in cells:e['run_size_px']=8
        p['tables']=[dict(id='wide',angle=0,box_px=[0,0,450,120],members=[e['id'] for e in caps+cells+[prose]])]+[
            dict(id='narrow'+str(i),angle=0,box_px=[x,20,x+210,80],members=[e['id'] for e in cells if x<=e['box_px'][0]<x+210]) for i,x in enumerate([0,240])]
        p['floats']=[dict(caption=caps[0]['text'],blocks=['wide','narrow0','narrow1'],box_px=[0,0,450,120])]
        result=c.table_float_regions(p,10)
        self.assertEqual(len(result['tables']),2)
        self.assertNotIn(prose['id'],{m for t in result['tables'] for m in t['members']})
        self.assertEqual({m for t in result['tables'] for m in t['members']},{e['id'] for e in cells})

    def test_furniture_is_excluded_even_when_seeded_in_an_exact_region(self):
        cap=run('TABLE 3',0,0,60)
        cells=[run(t,x,y,30) for y in [30,50] for x,t in [(0,'Alpha'),(100,'12')]]
        footer=run('Journal 100',0,70,100)
        p=page([cap]+cells+[footer])
        p['tables']=[dict(id='t',angle=0,box_px=[0,25,150,85],
                         members=[e['id'] for e in cells+[footer]],_copy_exact=True,layout='unstructured')]
        p['floats']=[dict(id='f',caption='Table 3',blocks=['t'],_caption_ids=[cap['id']],box_px=[0,0,150,85])]
        p['main_text']['furniture']=[dict(members=[footer['id']])]
        _,fs,_=c.read_page(p,10,[])
        ids={x['id'] for line in fs[0][5]['table_source']['lines'] for x in line['items']}
        self.assertEqual(ids,{e['id'] for e in cells})

    def test_caption_header_boundary_excludes_running_head_in_every_frame(self):
        for angle in (0,90,270):
            head=run('AUTHOR et al.',0,-40,90)
            cap=run('TABLE 3',0,0,60)
            cells=[run(t,x,y,30) for y in [30,50,70] for x,t in [(0,'Label'),(100,'Value')]]
            fills=[dict(id='fill'+str(x),kind='fill',box_px=[x,20,x+100,45]) for x in [0,100]]
            p=page([head,cap]+cells+fills)
            p['tables']=[dict(id='t',angle=angle,box_px=[0,-45,200,80],members=[e['id'] for e in cells])]
            p['floats']=[dict(caption='TABLE 3',blocks=['t'],box_px=[0,-45,200,80])]
            for e in p['elements']+p['tables']+p['floats']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e.get('kind')=='text':e['angle']=angle
            _,fs,_=c.read_page(p,10,[])
            ids={x['id'] for line in fs[0][5]['table_source']['lines'] for x in line['items']}
            self.assertNotIn(head['id'],ids)
            self.assertTrue({e['id'] for e in cells}<=ids)

    def test_sidecar_reports_lost_caption_tail_and_body_intrusion(self):
        cap=run('TABLE 3',0,0,60);tail=run('The complete title',0,15,120)
        cells=[run(t,x,y,30) for y in [40,55,70] for x,t in [(0,'Alpha'),(100,'12')]]
        prose=run('This ordinary body sentence was wrongly placed inside the table.',0,90,200)
        p=page([cap,tail]+cells+[prose]);p['main_text']['columns']=[[0,200]]
        p['main_text']['body_size_px']=10
        for e in cells:e['run_size_px']=8
        source=c.table_source(cells+[prose],p,[cap['id']])
        item=dict(kind='table',page=1,caption='Table 3',rows=[],notes=[],table_source=source)
        rec=c.gate_tables([item],[p],[])[0]
        self.assertTrue(rec['checks']['caption_whole']['fired'])
        self.assertEqual(rec['region_coverage']['body_sentence_line_count'],1)

    def test_caption_check_uses_caption_margin_when_cells_are_indented(self):
        cap=run('TABLE 3',0,0,50);title=run('A title',60,0,140)
        tail=run('with a continuation',0,15,130)
        adjacent=run('An independent sentence in the adjacent body column.',230,0,200)
        cells=[run(t,x,y,30) for y in [40,55,70] for x,t in [(30,'Alpha'),(100,'12')]]
        p=page([cap,title,tail,adjacent]+cells)
        source=c.table_source(cells,p,[e['id'] for e in [cap,title,tail]])
        item=dict(kind='table',page=1,caption='Table 3 A title with a continuation',rows=[],notes=[],table_source=source)
        rec=c.gate_tables([item],[p],[])[0]
        self.assertFalse(rec['checks']['caption_whole']['fired'])


if __name__=='__main__':unittest.main()
