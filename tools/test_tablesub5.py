"""Lane tablesub, re-ladder (tablesub5): row boundaries are read from per-column witnesses, never from
the case of a letter; a title line between caption and rows stays in the table; a table page's tail
rows join the table; tables side by side in the page columns are cut apart. Fixtures are synthetic."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule=t.c,t.run,t.page,t.grid,t.rule


def labels(rows,x1=150,x2=250,w=None):
    rs=[run('Group A',x1,0,60),run('Group B',x2,0,60)]
    for i,(label,a,b) in enumerate(rows):
        y=15+12*i
        rs+=[run(label,5,y,w or 6*len(label)),run(a,x1,y,6*len(a)),run(b,x2,y,6*len(b))]
    return rs


class RowWitnesses(unittest.TestCase):
    rows=[('participants','28','64'),('withdrawals','5','12'),('teeth present','26.1','25.3'),('smokers','4','9')]

    def test_a_label_that_would_have_fitted_beside_the_label_above_starts_a_row(self):
        rs=labels(self.rows);g=grid(c.table_rows(rs,10,page(rs))[0])
        self.assertEqual([r[0] for r in g[1:]],['participants','withdrawals','teeth present','smokers'])
        self.assertEqual(g[-1][1:],['4','9'])

    def test_the_case_of_a_letter_changes_nothing(self):
        lower=grid(c.table_rows(labels(self.rows),10,page(labels(self.rows)))[0])
        upper_rows=[(a[0].upper()+a[1:],b,d) for a,b,d in self.rows]
        upper=grid(c.table_rows(labels(upper_rows),10,page(labels(upper_rows)))[0])
        self.assertEqual([[x.lower() for x in r] for r in upper],[[x.lower() for x in r] for r in lower])

    def test_a_blank_label_line_beside_a_wrapped_cell_and_one_stacked_value_stays_in_its_row(self):
        rs=[run('Study',5,0,40),run('Patients',100,0,50),run('Finding',200,0,50)]
        rs+=[run('Ash et al. (2019)',5,15,85),run('24',100,15,12),run('The rinsing group kept a lower score',200,15,190),
             run('41.5',100,27,22),run('after the routine was stopped',200,27,150)]
        g=grid(c.table_rows(rs,10,page(rs))[0])
        self.assertEqual(len(g),2)
        self.assertEqual(g[1],['Ash et al. (2019)','24 41.5','The rinsing group kept a lower score after the routine was stopped'])

    def test_values_restarting_in_three_columns_beside_an_arm_make_a_sub_row(self):
        rs=[run('Study',5,0,40),run('Arm',120,0,30),run('n',260,0,10),run('Mean',310,0,30),run('SD',370,0,20)]
        for i,(arm,n,m,sd) in enumerate([('brushing only','14','2.31','0.40'),('brushing and floss','14','2.02','0.37'),('floss only','13','2.45','0.52')]):
            y=15+12*i
            if i==0: rs.append(run('Dorsey et al. (2020)',5,y,100))
            rs+=[run(arm,120,y,6*len(arm)),run(n,260,y,12),run(m,310,y,24),run(sd,370,y,24)]
        g=grid(c.table_rows(rs,10,page(rs))[0])
        self.assertEqual([r[1] for r in g[1:]],['brushing only','brushing and floss','floss only'])
        self.assertEqual([r[0] for r in g[1:]],['Dorsey et al. (2020)','',''])

    def test_value_lines_restarting_in_two_columns_are_sub_rows_of_their_study(self):
        rs=[run('Study',5,0,40),run('Depth',150,0,40),run('Gain',250,0,40)]
        y=20
        for name,a,b,d,e in [('Ames et al. (2016)','3.1 (C)','4.0 (T)','1.2 (C)','2.0 (T)'),('Baird et al. (2017)','2.9 (C)','3.8 (T)','1.1 (C)','1.9 (T)'),
                             ('Crane et al. (2018)','3.3 (C)','4.4 (T)','1.0 (C)','2.2 (T)')]:
            rs+=[run(name,5,y,95),run(a,150,y,45),run(d,250,y,45),run(b,150,y+11,45),run(e,250,y+11,45)];y+=36
        p=page(rs+[rule(-4,0,300),rule(13,0,300),rule(y,0,300)])
        g=grid(c.table_rows(rs,10,p)[0])
        # each study's second value line restarts its values: a sub-row of the study
        self.assertEqual(g[1:],[['Ames et al. (2016)','3.1 (C)','1.2 (C)'],['','4.0 (T)','2.0 (T)'],
                                ['Baird et al. (2017)','2.9 (C)','1.1 (C)'],['','3.8 (T)','1.9 (T)'],
                                ['Crane et al. (2018)','3.3 (C)','1.0 (C)'],['','4.4 (T)','2.2 (T)']])

    def test_a_wrapped_device_name_beside_restarting_values_joins_its_cell(self):
        rs=[run('Study',5,0,40),run('Depth',150,0,40),run('Gain',250,0,40),run('Device',340,0,40)]
        rs+=[run('Ames et al. (2016)',5,15,95),run('3.1 (C)',150,15,45),run('1.2 (C)',250,15,45),run('R-4C (REMI,',340,15,70),
             run('4.0 (T)',150,27,45),run('2.0 (T)',250,27,45),run('Mumbai, India)',340,27,80)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,430),rule(12,0,430),rule(40,0,430)]))[0])
        self.assertEqual(g[1:],[['Ames et al. (2016)','3.1 (C)','1.2 (C)','R-4C (REMI, Mumbai, India)'],['','4.0 (T)','2.0 (T)','']])

    def test_lettered_items_stacked_in_a_cell_are_a_list_not_a_sub_row(self):
        rs=[run('Ref',5,0,20),run('Sample',150,0,40),run('Ages',250,0,30)]
        rs+=[run('Ames 2016',5,15,55),run('a. 45',150,15,30),run('a. 41',250,15,30),run('b. 41',150,27,30),run('b. 40',250,27,30)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,300),rule(12,0,300),rule(40,0,300)]))[0])
        self.assertEqual(g[1:],[['Ames 2016','a. 45 b. 41','a. 41 b. 40']])

    def test_an_indented_label_with_values_of_its_own_is_a_sub_item_not_a_wrap(self):
        rs=[run('Variable',5,0,50),run('Group A',150,0,40),run('Group B',250,0,40),run('P',340,0,10)]
        rs+=[run('Hygiene habits, n (%)',5,15,110),run('<0.001',340,15,30),
             run('twice a day',15,27,60),run('7 (33.3)',150,27,45),run('16 (25.8)',250,27,50),
             run('once a day',15,39,55),run('8 (13.1)',150,39,45),run('2 (5.6)',250,39,40)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,380),rule(12,0,380),rule(52,0,380)]))[0])
        self.assertEqual([r[0] for r in g[1:]],['Hygiene habits, n (%)','twice a day','once a day'])

    def test_a_numbered_group_label_is_not_a_bracket_continuation(self):
        rs=[run('Study',5,0,40),run('Depth',150,0,40),run('Gain',250,0,40),
            run('Ames et al.',5,15,55),run('3.1',150,15,20),run('1.2',250,15,20),run('(2016)',5,27,35),
            run('(2) brushing vs. rinsing',5,45,110),
            run('Baird et al.',5,60,55),run('2.9',150,60,20),run('1.1',250,60,20),run('(2017)',5,72,35)]
        g=grid(c.table_rows(rs,10,page(rs))[0])
        self.assertEqual([r[0] for r in g[1:]],['Ames et al. (2016)','(2) brushing vs. rinsing','Baird et al. (2017)'])

    def test_a_label_line_in_another_face_under_values_is_a_row_of_its_own(self):
        rs=[run('Outcome',5,0,50),run('Week 4',150,0,40),run('Week 12',250,0,40),
            run('p-value',15,15,40),run('0.01',150,15,24),run('0.02',250,15,24),
            run('effect size',15,27,60),run('0.21',150,27,24),run('0.35',250,27,24),
            run('Bleeding score',5,39,80,bold=True),
            run('p-value',15,51,40),run('0.03',150,51,24),run('0.04',250,51,24)]
        g=grid(c.table_rows(rs,10,page(rs))[0])
        self.assertIn(['Bleeding score','',''],g)
        self.assertIn(['effect size','0.21','0.35'],g)


class TitleLine(unittest.TestCase):
    def test_a_sentence_title_between_caption_and_rows_stays_in_the_table(self):
        cap=run('Table 3.',5,0,50,bold=True)
        title=run('These are the outcomes of every arm at the end of the trial.',5,16,300)   # body size, a sentence
        header=[run('Study',5,34,40),run('Arm',120,34,30),run('n',260,34,10)]
        rows=[]
        for i,(s,a,n) in enumerate([('Ames 2016','brushing','14'),('Baird 2017','rinsing','20'),('Crane 2018','floss','13')]):
            rows+=[run(s,5,49+13*i,55),run(a,120,49+13*i,45),run(n,260,49+13*i,12)]
        for e in header+rows:e['run_size_px']=8;e['size_px']=8
        es=[cap,title]+header+rows;p=page(es,((0,320),))
        cells=header+rows
        tb=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[tb];p['blocks']=[dict(id='block:cap',members=[cap['id']],box_px=cap['box_px'])]
        p['floats']=[dict(id='float:1',caption=cap['text'],blocks=['block:cap','table:1'],box_px=c.hull([tb['box_px'],cap['box_px']]))]
        self.assertTrue(c.body_prose_line(p,title,10,[0,30,320,100]))   # the prose test alone would release it
        body,floats,side=c.read_page(p,10,[])
        owned={x['id'] for l in floats[0][5]['table_source']['lines'] for x in l['items']}
        # Never dropped nor released: the title is the caption's or a table line.
        self.assertTrue(title['id'] in owned or title['text'] in floats[0][2])
        self.assertFalse(any(title['text'] in str(b) for b in body))
        self.assertEqual(side,[])


class TablePage(unittest.TestCase):
    def test_tail_rows_join_when_the_page_columns_are_the_tables_own_tracks(self):
        cells=[]
        for i,(a,b,d) in enumerate([('Ames','In vitro','Cells grew on every disk'),('Baird','In vitro','No change was seen'),
                                    ('Cole','In vitro','Cells grew on two disks')]):
            cells+=[run(a,5,i*12,60),run(b,100,i*12,60),run(d,220,i*12,150)]
        tail=[run('Animal studies',5,52,80),
              run('Crane',5,66,60),run('Animal',100,66,60),run('The bone contact was larger after twelve weeks than before',220,66,160),
              run('Dunn',5,90,60),run('Animal',100,90,60),run('Similar apposition around both implant types was found',220,90,160)]
        for e in cells+tail:e['run_size_px']=10;e['size_px']=10   # the table is set in the body size
        p=page(cells+tail,((0,90),(100,210),(220,380)))
        tb=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[tb];p['floats']=[dict(id='float:1',caption='Table 3',blocks=['table:1'],box_px=list(tb['box_px']))]
        c.recover_table_aligned_tail(p,10)
        self.assertEqual(sorted(p['tables'][0]['members']),sorted(e['id'] for e in cells+tail))

    def test_body_columns_that_are_not_the_tables_tracks_still_stop_the_tail(self):
        cells=[]
        for i,(a,b,d) in enumerate([('Ames','In vitro','grew'),('Baird','In vitro','none'),('Cole','In vitro','grew')]):
            cells+=[run(a,5,i*12,60),run(b,100,i*12,60),run(d,220,i*12,60)]
        body=[run('The cells of every group were counted again after the second week of the trial',5,40,300)]
        for e in cells+body:e['run_size_px']=10;e['size_px']=10
        p=page(cells+body,((0,320),))
        tb=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[tb];p['floats']=[dict(id='float:1',caption='Table 3',blocks=['table:1'],box_px=list(tb['box_px']))]
        c.recover_table_aligned_tail(p,10)
        self.assertNotIn(body[0]['id'],p['tables'][0]['members'])


class SideBySide(unittest.TestCase):
    def two_tables(self,second_row_in_right=True):
        caps=[run('Table 6A.',0,0,60),run('Table 7A.',250,0,60)]
        titles=[run('Scores of the first group',0,14,200),run('Scores of the second group',250,14,200)]
        left=[run(t,x,y,40) for y in [40,55,70] for x,t in [(0,'plaque'),(120,'1.2')]]
        right=[run(t,x,y,40) for y in [40,55,70] for x,t in [(250,'bleeding'),(370,'0.4')]]
        for e in left+right:e['run_size_px']=8;e['size_px']=8
        es=caps+titles+left+right
        p=page(es,((0,230),(250,480)))
        p['blocks']=[dict(id='block:a',members=[caps[0]['id'],titles[0]['id']],box_px=c.hull([caps[0]['box_px'],titles[0]['box_px']])),
                     dict(id='block:b',members=[caps[1]['id'],titles[1]['id']],box_px=c.hull([caps[1]['box_px'],titles[1]['box_px']]))]
        wide=dict(id='table:1',angle=0,members=[e['id'] for e in left+right],box_px=c.hull(e['box_px'] for e in left+right))
        p['tables']=[wide]
        p['floats']=[dict(id='float:1',caption='Table 7A.',blocks=['block:b','table:1'],box_px=c.hull([wide['box_px'],caps[1]['box_px']]))]
        return p,caps,left,right

    def test_a_seed_across_the_gutter_with_a_caption_in_each_column_is_two_tables(self):
        p,caps,left,right=self.two_tables()
        c.split_gutter_tables(p,caps,10)
        self.assertEqual(sorted(sorted(x['members']) for x in p['tables']),sorted([sorted(e['id'] for e in left),sorted(e['id'] for e in right)]))
        self.assertEqual(sorted(f['caption'] for f in p['floats']),['Table 6A. Scores of the first group','Table 7A. Scores of the second group'])

    def test_one_caption_leaves_the_seed_alone(self):
        p,caps,left,right=self.two_tables()
        c.split_gutter_tables(p,caps[1:],10)
        self.assertEqual([x['id'] for x in p['tables']],['table:1'])


class NotesBelowTheBorder(unittest.TestCase):
    def test_an_equation_in_a_note_under_the_bottom_border_is_note_text(self):
        rs=[run('Reason',5,0,40),run('Early',150,0,30),run('Late',250,0,30)]
        for i,(a,b,d) in enumerate([('Fracture','4','2'),('Caries','1','3')]):
            rs+=[run(a,5,15+12*i,50),run(b,150,15+12*i,8),run(d,250,15+12*i,8)]
        notes=[run('Rates were compared with a corrected test (alpha =',5,52,290),run('0.05/5 = 0.01).',5,64,80)]
        p=page(rs+notes+[rule(-4,0,300),rule(12,0,300),rule(41,0,300)])
        rows,out=c.table_rows(rs+notes,10,p)
        self.assertEqual([r[0] for r in grid(rows)],['Reason','Fracture','Caries'])
        self.assertEqual(out,[n['text'] for n in notes])

    def test_a_missing_value_sign_under_a_sign_is_a_value_not_a_tail(self):
        rs=[run('Factor',5,0,40),run('P',150,0,10),run('HR',250,0,20),run('Resection',5,15,60)]
        for i,(a,b,d) in enumerate([('reason for resection','0.0097','–'),('reason versus failure','0.2651','–')]):
            rs+=[run(a,15,27+12*i,6*len(a)),run(b,150,27+12*i,30),run(d,250,27+12*i,6)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,300),rule(12,0,300),rule(55,0,300)]))[0])
        self.assertIn(['reason versus failure','0.2651','–'],[r for r in g])


if __name__ == '__main__':
    unittest.main()
