"""Lane tablesub, re-ladder round 3 (tablesub6): a stacked multi-line cell stays in its row; a stack of values beside
the label column keeps its gutter; values set between the lines of their label leave the label whole; a labelled
value is a value in the checks. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule=t.c,t.run,t.page,t.grid,t.rule


def study_table(teeth_neighbour):
    """Ref | Sample | Teeth | Care: one study whose Teeth cell stacks labelled counts; the Care cell either wraps
    as prose or stacks one-word items beside it."""
    rs=[run('Ref',5,0,20),run('Sample',90,0,40),run('Teeth',170,0,30),run('Care',280,0,30)]
    teeth=['Front: 5','Side: 8','Back: 11','Third: 2']
    care=['Rinse and','gel with a','printed sheet'] if teeth_neighbour=='prose' else ['Rinse','Gel','Floss','tape']
    rs+=[run('Ames 2016',5,15,55),run('a. 33',90,15,30),run('b. 27',90,27,30)]
    rs+=[run(x,170,15+12*i,6*len(x)) for i,x in enumerate(teeth)]
    rs+=[run(x,280,15+12*i,6*len(x)) for i,x in enumerate(care)]
    return rs


class StackedCells(unittest.TestCase):
    def test_a_stacked_labelled_list_beside_wrapping_prose_stays_in_its_row(self):
        rs=study_table('prose');g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,380),rule(12,0,380),rule(66,0,380)]))[0])
        self.assertEqual(g[1:],[['Ames 2016','a. 33 b. 27','Front: 5 Side: 8 Back: 11 Third: 2','Rinse and gel with a printed sheet']])

    def test_a_stacked_labelled_list_beside_another_stacked_list_stays_in_its_row(self):
        rs=study_table('items');g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,380),rule(12,0,380),rule(66,0,380)]))[0])
        self.assertEqual(g[1:],[['Ames 2016','a. 33 b. 27','Front: 5 Side: 8 Back: 11 Third: 2','Rinse Gel Floss tape']])

    def test_a_bare_parallel_value_beside_its_own_group_label_is_still_a_sub_row(self):
        # the round-2 witness: the group label beside the value is the entry's own
        rs=[run('Author',5,0,40),run('Design',90,0,40),run('Groups',190,0,40),run('n',290,0,10)]
        for k,(a,d) in enumerate([('Ames 2016','parallel'),('Baird 2017','parallel')]):
            y=15+30*k
            rs+=[run(a,5,y,55),run(d,90,y,50),run('Inflamed sites',190,y,85),run('17/30',290,y,30),
                 run('Calm sites',190,y+12,60),run('6/11',290,y+12,24)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,330),rule(12,0,330),rule(70,0,330)]))[0])
        self.assertEqual([r[2] for r in g[1:]],['Inflamed sites','Calm sites','Inflamed sites','Calm sites'])
        self.assertEqual([r[0] for r in g[1:]],['Ames 2016','','Baird 2017',''])

    def test_a_label_ending_in_its_colon_waits_for_its_value(self):
        # "Arm 2:" above "4.1" is a label and its value, not two values (no sub-row beside a stacked list)
        rs=[run('Ref',5,0,20),run('Teeth',90,0,30),run('Arms',200,0,30),run('Visits',300,0,30)]
        rs+=[run('Ames 2016',5,15,55),run('Front: 5',90,15,48),run('a. Rinse',200,15,48),run('a. 5.6',300,15,36),
             run('Side: 8',90,27,42),run('b. Arm 2:',200,27,54),run('b. Arm 2:',300,27,54),
             run('Back: 11',90,39,48),run('4.1',300,39,18)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,380),rule(12,0,380),rule(54,0,380)]))[0])
        self.assertEqual(len(g),2)
        self.assertEqual(g[1][3],'a. 5.6 b. Arm 2: 4.1')


class SlotRestart(unittest.TestCase):
    def test_values_restarting_after_an_empty_slot_beside_a_hung_arm_name_make_a_sub_row(self):
        # an arm's name wraps over three lines with a hanging indent; the next arm's values restart in the
        # value columns after those empty line slots: the next arm is a sub-row with its own name
        rs=[run('Ref',5,0,20),run('Arm',40,0,30),run('Baseline',200,0,45),run('Final',270,0,30),run('Change',330,0,40)]
        rs+=[run('7',5,15,12),run('a. Rinse only (n = 15)',40,15,126),run('7.4 ± 1.1',200,15,50),run('6.2 ± 1.3',270,15,50),run('+1.2 ± 0.8',330,15,55),
             run('b. Arm 1: Gel with a',40,29,116),run('7.7 ± 1.4',200,29,50),run('3.9 ± 1.0',270,29,50),run('+3.8 ± 1.2',330,29,55),
             run('daily rinse and a',52,41,96),run('night tray (n = 15)',52,53,108),
             run('Arm 2: Rinse with',52,67,98),run('8.1 ± 1.6',200,67,50),run('5.3 ± 1.1',270,67,50),run('+2.8 ± 1.4',330,67,55),
             run('a weekly gel (n = 15)',52,79,120)]
        for k,(r,a,v) in enumerate([('8','a. Rinse only (n = 12)','6.6 ± 1.2'),('','b. Gel only (n = 12)','6.1 ± 0.9'),
                                    ('9','a. Rinse only (n = 9)','7.0 ± 1.5'),('','b. Gel only (n = 9)','6.4 ± 1.3')]):
            y=95+14*k
            if r: rs.append(run(r,5,y,12))
            rs+=[run(a,40,y,6*len(a)),run(v,200,y,50),run(v,270,y,50),run(v,330,y,50)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,400),rule(12,0,400),rule(152,0,400)]))[0])
        self.assertEqual([r[1] for r in g[1:4]],['a. Rinse only (n = 15)','b. Arm 1: Gel with a daily rinse and a night tray (n = 15)',
                                                'Arm 2: Rinse with a weekly gel (n = 15)'])
        self.assertEqual(g[3][2:],['8.1 ± 1.6','5.3 ± 1.1','+2.8 ± 1.4'])


class LabelColumn(unittest.TestCase):
    def centred(self,between_lines):
        """An empty header over the label column, a two-line header over the first value column, values centred
        on their decimal point; the second row's label wraps with its values set between its two lines (or
        sharing its first line)."""
        rs=[run('Total of',130,0,40),run('ranks',135,10,30),run('df',210,10,10),run('Mean',260,10,25),run('p',330,10,6)]
        rs+=[run('Plaque',5,25,36),run('2214.50',130,25,40),run('2',212,25,6),run('1107.25',255,25,40),run('0.004',325,25,30)]
        if between_lines:
            rs+=[run('Probing',5,38,42),run('981.00',133,44,34),run('2',212,44,6),run('490.50',258,44,34),run('0.120',325,44,30),
                 run('depth',5,50,30)]
        else:
            rs+=[run('Probing',5,38,42),run('981.00',133,41,34),run('2',212,41,6),run('490.50',258,41,34),run('0.120',325,41,30),
                 run('depth',5,47,30)]
        return rs

    def test_values_beside_the_label_column_keep_their_gutter(self):
        rs=self.centred(True);g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,360),rule(21,0,360),rule(62,0,360)]))[0])
        self.assertEqual(g[-2],['Plaque','2214.50','2','1107.25','0.004'])

    def test_values_set_between_the_lines_of_their_label_leave_it_whole(self):
        for between in (True,False):
            rs=self.centred(between);g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,360),rule(21,0,360),rule(62,0,360)]))[0])
            self.assertEqual(g[-1],['Probing depth','981.00','2','490.50','0.120'],between)

    def test_a_label_only_line_after_a_row_with_level_values_is_still_its_own_row(self):
        # values on the label's own line: nothing stands below it, so a following label line is not its tail
        rs=[run('Score',130,0,30),run('p',210,0,6)]
        rs+=[run('Plaque',5,15,36),run('2.1',132,15,18),run('0.04',205,15,24),run('Bleeding sites',5,27,80),
             run('upper jaw',15,39,54),run('1.4',132,39,18),run('0.20',205,39,24)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,240),rule(12,0,240),rule(54,0,240)]))[0])
        self.assertNotIn('Plaque Bleeding sites',[r[0] for r in g])


class Checks(unittest.TestCase):
    def test_blank_label_rows_of_labelled_values_are_witnessed_sub_rows(self):
        # a label on the middle line of three stacked labelled counts: the rows above and below it have blank labels
        rs=[run('Test',150,0,40),run('Control',300,0,50)]
        rows_=[(15,'Age','31-62','27-58'),(27,'Sex','12 men','9 men'),(42,'','Narrow: 7 (35%)','Narrow: 12 (60%)'),
               (54,'Sites','Mid: 9 (45%)','Mid: 5 (25%)'),(66,'','Wide: 4 (20%)','Wide: 3 (15%)'),(81,'Plaque','22.6%','24.1')]
        for y,a,b,d in rows_:
            if a: rs.append(run(a,5,y,6*len(a)))
            rs+=[run(b,150,y,6*len(b)),run(d,300,y,6*len(d))]
        p=page(rs+[rule(-4,0,420),rule(12,0,420),rule(95,0,420)])
        rows,notes=c.table_rows(rs,10,p)
        self.assertEqual([r[0] for r in grid(rows)],['','Age','Sex','','Sites','','Plaque'])
        checks=c.table_structure_checks(rows,c.table_source(rs,p),'Table 1. Baseline',notes)
        self.assertFalse(checks['row_count']['fired'],checks['row_count'])


if __name__=='__main__':
    unittest.main()
