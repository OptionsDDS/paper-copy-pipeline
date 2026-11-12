"""Geometry regressions for table columns and study continuations."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('table_tests',Path(__file__).with_name('test_copy_tables.py'))
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
paper,text,drawing=helpers.paper,helpers.text,helpers.drawing

class Subcolumns(unittest.TestCase):
    def test_wrapped_design_labels_complete_the_reference_cell(self):
        for design in [('Case series',),('Comparative',)]:
            runs=[text(label,x,0,70) for label,x in [('Authors',0),('Patients',100),('Result',200)]]
            runs += [text('Alpha (2020)',0,30,70),text('12',100,30,20),text('1.25',200,30,30)]
            for i,label in enumerate(design):
                runs += [text(label,0,45+15*i,70),text('15',100,45+15*i,20),text('2.50',200,45+15*i,30)]
            runs += [text('Beta (2021)',0,100,70),text('18',100,100,20),text('3.75',200,100,30)]
            rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,280,18],'fill')]))
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[1][0],['Alpha (2020)',*design])
            self.assertEqual(rows[-1][0],['Beta (2021)'])

    def test_repeated_arm_prefixes_keep_numeric_observations_separate(self):
        runs=[text(label,x,0,70) for label,x in [('Author',0),('Count',100),('Age',200)]]
        runs += [text('Alpha (2020)',0,30,70),text('A + B: 12',100,30,70),text('A + B: 15',200,30,70),
                 text('A: 11',100,45,60),text('A: 14',200,45,60)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,280,18],'fill')]))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1],[[],['A: 11'],['A: 14']])

    def test_adjacent_author_year_entries_remain_separate_in_a_filled_band(self):
        runs=[text(label,x,0,70) for label,x in [('Author',0),('First',100),('Second',200)]]
        for y,name in [(30,'Alpha (2020)'),(45,'Beta (2021)'),(60,'Gamma (2022)')]:
            runs += [text(name,0,y,70),text('1.25',100,y,40),text('2.50',200,y,40)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[
            drawing([0,0,280,18],'fill'),drawing([0,20,280,75],'fill')]))
        self.assertEqual(len(rows),4)
        self.assertEqual([r[0] for r in rows[1:]],[['Alpha (2020)'],['Beta (2021)'],['Gamma (2022)']])

    def test_wrapped_study_word_in_matrix_header_is_not_a_reference_column(self):
        runs=[text('Phase of the',0,0,70),text('study',0,15,40)]
        runs += [text(label,x,15,50) for label,x in [('Item',100),('First',200),('Second',300)]]
        runs += [text('Registration',0,40,70),text('Ethics',100,40,50),text('0',200,40,10),text('1',300,40,10),
                 text('Consent',100,55,50),text('1',200,55,10),text('0',300,55,10)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,370,30],'fill')]))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1],[[],['Consent'],['1'],['0']])

    def test_staggered_cells_do_not_shorten_the_wrapping_pitch(self):
        runs=[text(label,x,0,60) for label,x in [('Reference',0),('First',110),('Second',220),('Short',330)]]
        runs += [text('Alpha (2020)',0,25,70),text('Brief cell',330,32,60)]
        for y in [25,40,55,70]:runs += [text('More prose',110,y,60),text('Other prose',220,y,60)]
        runs += [text('Beta (2021)',0,110,70),text('Next result',110,110,60)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,400,18],'fill')]))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1][1],['More prose']*4)
        self.assertEqual(rows[-1][0],['Beta (2021)'])

    def test_alternating_subcolumns_beneath_spanning_header(self):
        runs=[text('Name',0,20,35),text('Estimate',100,0,80),
              text('First',100,20,30),text('Second',160,20,30),text('Total',230,20,35)]
        for y,label,x in [(50,'Alpha',100),(70,'Beta',160),(90,'Gamma',100),(110,'Delta',160)]:
            runs += [text(label,0,y,35),text('1.25',x,y,30),text('20',230,y,20)]
        # Notes crossing the channel are outside the table's body evidence.
        runs += [text('Abbreviations: each estimate uses a different model.',0,140,270)]
        page=dict(elements=runs+[drawing([0,0,280,38],'fill'),drawing([100,15,195,15.2]),
                                 drawing([0,130,280,130.2])])
        rows,notes=paper.table_rows(runs,10,page)
        self.assertEqual(rows[1],[['Name'],['First'],['Second'],['Total']])
        self.assertEqual(rows[2],[['Alpha'],['1.25'],[],['20']])
        self.assertEqual(rows[3],[['Beta'],[],['1.25'],['20']])
        self.assertTrue(notes)

    def test_closing_border_retains_full_height_hierarchy_dividers(self):
        runs=[text('Group A',5,40,60),text('First cause',105,20,70),
              text('Detail one',205,20,70),text('Detail two',205,60,70),
              text('Group B',5,125,60),text('Second cause',105,125,70),
              text('Detail three',205,100,70),text('Detail four',205,140,70)]
        graphics=[drawing([x,0,x+.2,180]) for x in [0,100,200,300]]
        graphics += [drawing([0,y,300,y+.2]) for y in [0,90,180]]
        graphics += [drawing([200,y,300,y+.2]) for y in [45,130]]
        rows,notes=paper.table_rows(runs,10,dict(elements=runs+graphics))
        self.assertFalse(notes)
        self.assertEqual(len(rows),4)
        self.assertEqual(rows[0],[['Group A'],['First cause'],['Detail one']])
        self.assertEqual(rows[-1],[['Group B'],['Second cause'],['Detail four']])

    def test_auxiliary_reference_line_stays_inside_drawn_study_band(self):
        runs=[text(label,x,5,70) for label,x in [('Reference',5),('Design',105),('Result',205)]]
        runs += [text('Alpha (2020)',5,30,70),text('Survey',105,30,70),text('First result',205,30,70),
                 text('Population A',5,45,70),text('Adult sample',105,45,70),text('More results',205,45,70),
                 text('Final results',205,75,70),text('Beta (2021)',5,110,70),
                 text('Trial',105,110,70),text('Second result',205,110,70)]
        graphics=[drawing([0,0,300,22],'fill'),drawing([0,25,300,100],'fill')]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+graphics))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1][0],['Alpha (2020)','Population A'])
        self.assertEqual(rows[-1][0],['Beta (2021)'])

    def test_numeric_tail_of_wrapped_cell_keeps_left_edge_owner(self):
        runs=[text(label,x,0,55) for label,x in [('Reference',0),('Design',110),('Result',220)]]
        runs += [text('Alpha (2020)',0,25,70),text('Survey',110,25,50),text('Result',220,25,50),
                 text('Cohort 2011–',0,40,102),text('2013',0,55,28),
                 text('Adults',110,40,50),text('Long result',220,40,65),text('Final result',220,80,65)]
        chars=[]
        for run in runs:
            label=run['text'];x,y,end,bot=run['box_px'];run['char_ids']=[]
            for i,ch in enumerate(label):
                run['char_ids'].append(len(chars))
                chars.append(dict(text=ch,x0=x+i*(end-x)/len(label),x1=x+(i+1)*(end-x)/len(label),y0=y,y1=bot))
        page=dict(elements=runs+[drawing([0,0,300,18],'fill'),drawing([0,20,300,95],'fill')],_table_chars=chars)
        for angle in [0,90,180,270]:
            p=copy.deepcopy(page)
            for e in p['elements']:
                e['box_px']=paper.frame(-angle)(e['box_px'])
                if e['kind']=='text':e['angle']=angle
            for c in p['_table_chars']:
                c['x0'],c['y0'],c['x1'],c['y1']=paper.frame(-angle)([c['x0'],c['y0'],c['x1'],c['y1']])
            rows,_=paper.table_rows(p['elements'][:-2],10,p)
            self.assertEqual(rows[1][0],['Alpha (2020)','Cohort 2011–','2013'])
            self.assertEqual(rows[1][1],['Survey','Adults'])

if __name__=='__main__':unittest.main()
