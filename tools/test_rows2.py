"""First-column entries and complete source regions, independent of paper names."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('cellblocks',Path(__file__).with_name('test_cellblocks.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c,run,fill=m.c,m.run,m.fill


def page(es):
    for i,e in enumerate(es):
        e.setdefault('id',str(i))
        if e['kind']=='text':e.update(size_px=10,run_size_px=10)
    return dict(page=1,elements=es,tables=[],floats=[],blocks=[],
                region_box_px=[0,0,600,700],main_text=dict(blocks=[],columns=[[0,600]]))


class Rows(unittest.TestCase):
    def publication(self, second=True):
        rs=[run('Publication (authors, year, title)',5,0,140),run('Results',180,0)]
        rs += [run(t,5,y,130) for y,t in [(25,'Alpha et al12'),(40,'Country'),(55,'A title that'),(70,'continues here')]]
        rs += [run(t,180,y,100) for y,t in [(25,'Three studies'),(40,'12 (40%)'),(55,'Two trials'),(70,'OR 1.7'),(85,'95% CI 1.2–2.5')]]
        if second:
            rs += [run(t,5,y,130) for y,t in [(105,'Beta and Gamma13'),(120,'Country'),(135,'Another title')]]
            rs += [run('Four studies',180,105,100),run('OR 1.4',180,120,100)]
        return rs,dict(elements=rs+[fill(-5,18)])

    def test_publications_define_whole_row_bands_in_all_frames(self):
        for angle in (0,90,180,270):
            rs,p=self.publication()
            for e in p['elements']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e['kind']=='text':e['angle']=angle
            rows,notes=c.table_rows(rs,10,p)
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[1][0],['Alpha et al12','Country','A title that','continues here'])
            self.assertEqual(rows[1][1][-1],'95% CI 1.2–2.5')
            self.assertEqual(rows[2][0][0],'Beta and Gamma13')
            self.assertFalse(notes)

    def test_single_publication_continuation_is_one_entry(self):
        rs,p=self.publication(False)
        rows,_=c.table_rows(rs,10,p)
        self.assertEqual(len(rows),2)
        self.assertEqual(len(rows[1][0]),4)

    def test_slash_joined_wrapped_references_do_not_open_a_row(self):
        rs=[run(t,5,y,130) for y,t in [(25,'Alpha et'),(40,'al12/van'),(55,'Beta'),(70,'et al13'),(120,'Gamma et al14')]]
        lines=c.table_lines([(e['box_px'],e['text'],e) for e in rs])
        bands=c.table_entry_bands(lines,[160],18,10,True)
        self.assertEqual(len(bands),3)  # empty lead-in, then two entries
        self.assertEqual(bands[-1][0],118)

    def test_combining_accent_and_parenthesized_year_start_entries(self):
        rs=[run(t,5,y,130) for y,t in [(25,'Alpha et al12'),(70,'Be\u0302ta et al13'),
                                      (120,'Gamma et al (2014)')]]
        lines=c.table_lines([(e['box_px'],e['text'],e) for e in rs])
        bands=c.table_entry_bands(lines,[160],18,10,True)
        self.assertEqual(len(bands),4)

    def test_wrapped_coauthors_and_lowercase_name_particles(self):
        rs=[run(t,5,y,130) for y,t in [(25,'Alpha'),(40,'and'),(55,'Beta'),(70,'(2016)'),
                                      (120,'Gamma et al (2014)'),(170,'de Delta et al (2015)')]]
        lines=c.table_lines([(e['box_px'],e['text'],e) for e in rs])
        bands=c.table_entry_bands(lines,[160],18,10,True)
        self.assertEqual([lo for lo,hi in bands],[18,23,118,168])

    def test_comma_separated_coauthors_and_followup_references_stay_in_one_entry(self):
        rs=[run(t,5,y,130) for y,t in [(25,'Alpha, Beta, and'),(40,'Gamma (2016)'),
             (110,'Delta et al12'),(125,'Subsample from'),(140,'Epsilon et al13'),
             (200,'Zeta and Eta (2010) (F-up'),(215,'Theta et al (2003))'),(280,'Iota et al14')]]
        lines=c.table_lines([(e['box_px'],e['text'],e) for e in rs])
        bands=c.table_entry_bands(lines,[160],18,10,True)
        self.assertEqual([lo for lo,hi in bands],[18,23,108,198,278])

    def test_study_recovery_requires_multiple_citations_inside_one_drawn_band(self):
        rs=[run('Alpha et al12',5,25,130),run('Beta et al13',5,120,130)]
        lines=c.table_lines([(e['box_px'],e['text'],e) for e in rs])
        self.assertFalse(c.table_entry_bands(lines,[160],18,10,regions=[(20,80),(100,160)]))
        self.assertTrue(c.table_entry_bands(lines,[160],18,10,regions=[(20,160)]))

    def test_multiple_studies_in_the_unshaded_band_remain_separate(self):
        rs,p=self.publication()
        rs[0]['text']='Authors (year)'
        added=[run('Gamma et al14',5,205,130),run('Five studies',180,205,100),run('OR 1.5',180,240,100)]
        rs.extend(added);p['elements'].extend(added+[fill(190,250)])
        rows,_=c.table_rows(rs,10,p)
        self.assertEqual(len(rows),4)
        self.assertEqual([row[0][0] for row in rows[1:]],['Alpha et al12','Beta and Gamma13','Gamma et al14'])

    def test_side_caption_with_tall_rows_and_final_wrapping(self):
        cap=run('TABLE 3',350,0,60)
        rs=[run('Approach',5,5),run('Actions',120,5)]
        for y,label in [(35,'Alpha'),(155,'Beta'),(275,'Gamma'),(405,'Delta')]:
            rs += [run(label,5,y),run('• Action',120,y),run('continued action',130,y+15,140)]
        rs += [run('last wrapped line',130,435,140)]
        notes=[run('Note: Adapted from a source.',0,460,290),run('Source continuation.',0,475,180)]
        prose=run('The next body paragraph starts here.',0,520,310)
        p=page([cap]+rs+notes+[prose,fill(0,25),fill(145,260),fill(370,430),
                        dict(kind='rule',box_px=[0,455,320,455])])
        prose['run_size_px']=14
        for has_rule in (True,False):
            q=c.table_float_regions(p,10)
            ids={m for t in q['tables'] for m in t['members']}
            self.assertEqual(ids,{e['id'] for e in rs+notes})
            self.assertEqual(q['tables'][0]['_copy_notes_top'],460)
            p['elements']=[e for e in p['elements'] if e['kind']!='rule']

    def test_split_height_header_retains_far_subcolumns(self):
        cap=run('TABLE 1',0,0,60)
        cells=[dict(kind='fill',box_px=b) for b in ([0,20,100,60],[100,20,200,60],
                     [200,20,300,60],[300,20,400,40],[300,40,350,60],[350,40,400,60])]
        p=page([cap]+cells)
        for angle in (0,90,270):
            q=copy.deepcopy(p)
            for e in q['elements']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e['kind']=='text':e['angle']=angle
            fills=c.caption_header_fills(q,q['elements'][0],10)
            self.assertEqual(c.hull(fills),[0,20,400,60])

    def test_next_side_caption_excludes_its_header_band_from_previous_table(self):
        cap=run('TABLE 1',350,0,60);nxt=run('TABLE 2',350,150,60)
        rs=[run(t,x,y,100) for y in (5,50,95) for x,t in [(5,'Label'),(180,'Value')]]
        later=[run('Next label',5,150,100),run('Next value',180,150,100)]
        p=page([cap,nxt]+rs+later+[fill(0,20),fill(45,65),fill(90,110),fill(145,165)])
        c.recover_side_caption_regions(p,[cap,nxt],10)
        self.assertEqual(len(p['tables']),1)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in rs})

    def test_header_recovery_stops_at_larger_body_prose(self):
        cap=run('TABLE 1',0,0,60)
        heads=[run(t,x,30,70) for x,t in [(5,'Author'),(105,'Design'),(205,'Results')]]
        cells=[run(t,x,y,60) for y in (80,150,220,290) for x,t in [(5,'Name'),(105,'Test'),(205,'Value')]]
        prose=run('The following prose is outside the table.',0,340,280)
        p=page([cap]+heads+cells+[prose]+[dict(kind='fill',box_px=[x,20,x+100,60]) for x in (0,100,200)])
        prose['run_size_px']=10.7
        c.recover_header_table_regions(p,[cap],10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in heads+cells})
        self.assertEqual(p['tables'][0]['layout'],'unstructured')

    def test_existing_shaded_expansion_keeps_its_grid(self):
        cap=run('TABLE 1',0,0,60)
        heads=[run(t,x,30,70) for x,t in [(5,'Author'),(105,'Design'),(205,'Results')]]
        cells=[run(t,x,y,60) for y in (80,150,220,290) for x,t in [(5,'Name'),(105,'Test'),(205,'Value')]]
        p=page([cap]+heads+cells+[dict(kind='fill',box_px=[x,20,x+100,60]) for x in (0,100,200)]
               +[dict(kind='fill',box_px=[0,70,300,310])])
        p['tables']=[dict(id='grid',angle=0,box_px=[0,70,300,310],members=[e['id'] for e in cells])]
        c.recover_header_table_regions(p,[cap],10)
        self.assertEqual([t['id'] for t in p['tables']],['grid'])
        self.assertNotIn('layout',p['tables'][0])

    def test_lower_totals_tail_does_not_replace_a_complete_header_grid(self):
        cap=run('TABLE 1',0,0,60)
        heads=[run(t,x,30,70) for x,t in [(5,'Group'),(105,'Count'),(205,'Results')]]
        cells=[run(t,x,y,60) for y in (80,150,220,290) for x,t in [(5,'Name'),(105,'Test'),(205,'Value')]]
        tail=[run(t,x,350,60) for x,t in [(5,'TOTAL'),(105,'25'),(205,'75')]]
        p=page([cap]+heads+cells+tail+[dict(kind='fill',box_px=[x,20,x+100,60]) for x in (0,100,200)])
        p['tables']=[dict(id='grid',angle=0,box_px=[0,20,300,310],members=[e['id'] for e in heads+cells])]
        c.recover_header_table_regions(p,[cap],10)
        self.assertEqual([t['id'] for t in p['tables']],['grid'])
        self.assertNotIn('layout',p['tables'][0])

    def test_uniform_rotated_header_keeps_existing_grid_extension_path(self):
        cap=run('TABLE 1',0,0,60)
        heads=[run(t,x,30,70) for x,t in [(5,'Group'),(105,'Count'),(205,'Results')]]
        cells=[run(t,x,y,60) for y in (80,150,220,290) for x,t in [(5,'Name'),(105,'Test'),(205,'Value')]]
        p=page([cap]+heads+cells+[dict(kind='fill',box_px=[x,20,x+100,60]) for x in (0,100,200)])
        p['tables']=[dict(id='grid',angle=90,box_px=c.frame(-90)([0,200,300,310]),
                          members=[e['id'] for e in cells if e['box_px'][1]>=200])]
        for e in p['elements']:
            e['box_px']=c.frame(-90)(e['box_px'])
            if e['kind']=='text':e['angle']=90
        for split in (False,True):
            q=copy.deepcopy(p)
            if split:
                f=next(e for e in reversed(q['elements']) if e['kind']=='fill')
                b=list(c.frame(90)(f['box_px']));b[3]-=20;f['box_px']=c.frame(-90)(b)
            c.recover_header_table_regions(q,[q['elements'][0]],10)
            self.assertEqual([t['id'] for t in q['tables']],['grid'])
            self.assertNotIn('layout',q['tables'][0])


if __name__=='__main__':unittest.main()
