"""Lane r3-wraplabels: a wrapped row label is one cell. In a table without bands, a label-only line set like
the label above, one line step below it and inside the label column's measure, is that label's next line
(divider rows found by the r2-divider rules stay rows); a label wrapped over lines above the values on its last
line (its lines at the table's leading, tighter than the row step; no room left on a line for the next line's
first word) joins the row whose values it shares; a stacked cell whose items wrap at other lines than its
neighbours' is dealt one item per sub-row. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('dividers',Path(__file__).with_name('test_divider_rows.py'))
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
c,run,page,grid,rule,banded=d.c,d.run,d.page,d.grid,d.rule,d.banded


def lab(t,x,y,w=None):
    r=run(t,x,y,w or 6*len(t)); r['_faces']={'Sans':len(t)}; r['run_size_px']=10; return r


def table(body,steps=None,head=('Group','n','Mean','p')):
    """body: list of (label, values or None); steps: the step to each body line (default 12)."""
    rs=[lab(head[0],5,0)]+[run(t,x,0,24) for t,x in zip(head[1:],(100,170,250))]
    gr=[rule(-4,0,320),rule(12,0,320)]
    y=16
    for k,(l,vs) in enumerate(body):
        if k: y+=(steps[k-1] if steps else 12)
        if l: rs.append(lab(l,5,y) if isinstance(l,str) else lab(l[0],5,y,l[1]))
        for v,x in zip(vs or (),(100,170,250)):
            if v: rs.append(run(v,x,y,24))
    gr.append(rule(y+12,0,320))
    return grid(c.table_rows(rs,10,page(rs+gr))[0])


class UnbandedWrappedLabels(unittest.TestCase):
    def test_a_second_label_line_without_bands_joins_its_label(self):
        g=grid(c.table_rows(*(lambda rs,gr:(rs,10,page(rs+gr)))(*banded(divider='Shore',bands=False)))[0])
        self.assertIn(['Beta Shore','12','38.7','0.48'],g)
        self.assertNotIn(['Shore','','',''],g)

    def test_two_wrapped_labels_with_a_divider_row_between(self):
        # a divider set apart (capitals) stays a row; a lone word inside a group joins its label; a lone word
        # closing a group (the divider follows) stays a row: it may be a category without values (r3 re-ladder)
        g=table([('Alpha boats',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),('quay',None),('UPPER GROUP',None),
                 ('Gamma',('9','44.0','0.09')),('Delta',('7','36.1','0.62')),('reach',None),('Omega',('5','30.2','0.33'))])
        self.assertIn(['quay','','',''],g)
        self.assertIn(['UPPER GROUP','','',''],g)
        self.assertIn(['Delta reach','7','36.1','0.62'],g)
        self.assertIn(['Omega','5','30.2','0.33'],g)

    def test_a_three_line_label_with_values_on_its_first_line(self):
        g=table([('Alpha boats',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),('of the',None),('bay',None),
                 ('Gamma',('9','44.0','0.09'))])
        self.assertIn(['Beta of the bay','12','38.7','0.48'],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_divider_set_like_the_labels_binding_to_the_row_below_stays_a_row(self):
        # set like the labels, closer to the row below, and leaving room for that row's first word
        g=grid(c.table_rows(*(lambda rs,gr:(rs,10,page(rs+gr)))(*banded(divider='Upper',step_below=9,bands=False)))[0])
        self.assertIn(['Upper','','',''],g)
        self.assertIn(['Beta','12','38.7','0.48'],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_label_line_wider_than_the_labels_stays_a_row(self):
        g=table([('Alpha',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),(('Broader heading',80),None),
                 ('Gamma',('9','44.0','0.09'))])
        self.assertIn(['Broader heading','','',''],g)
        self.assertIn(['Beta','12','38.7','0.48'],g)

    def test_one_line_labels_are_unchanged(self):
        g=table([('Alpha',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),('Gamma',('9','44.0','0.09'))])
        self.assertEqual(g[1:],[['Alpha','14','41.2','0.21'],['Beta','12','38.7','0.48'],['Gamma','9','44.0','0.09']])


class HeadingsStayRows(unittest.TestCase):
    def test_a_line_set_like_an_opening_divider_is_no_wrapped_label(self):
        # the body opens with a label-only line; a later label-only line in the same setting and at the same
        # edge, with room above, is a heading of the same kind, not the label above's next line
        g=table([('Opening part',None),('Alpha',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),
                 ('Later part',None),('Gamma',('9','44.0','0.09'))])
        self.assertIn(['Later part','','',''],g)
        self.assertIn(['Beta','12','38.7','0.48'],g)

    def test_a_group_label_over_indented_member_rows_is_not_joined(self):
        rs=[lab('Group',5,0)]+[run(t,x,0,24) for t,x in zip(('n','Mean','p'),(100,170,250))]
        gr=[rule(-4,0,320),rule(12,0,320)]
        rs+=[lab('Alpha',5,16)]+[run(v,x,16,24) for v,x in zip(('14','41.2','0.21'),(100,170,250))]
        rs+=[lab('Long heading wording',5,28,84)]
        for k,(l,vs) in enumerate([('first',('12','38.7','0.48')),('second',('9','44.0','0.09'))]):
            rs+=[lab(l,15,38+12*k)]+[run(v,x,38+12*k,24) for v,x in zip(vs,(100,170,250))]
        gr.append(rule(74,0,320))
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['Long heading wording','','',''],g)
        self.assertIn(['first','12','38.7','0.48'],g)


class GroupsAndCategories(unittest.TestCase):
    """Gate memo forms (r3 re-ladder): a heading set off by a group gap over its members; categories under a heading."""
    def test_a_heading_after_a_group_gap_stays_over_its_member_rows(self):
        g=table([('Alpha',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),(('Second group heading',70),None),
                 ('Gamma',('9','44.0','0.09')),('Delta',('7','36.1','0.62'))],steps=[12,17,12,12])
        self.assertIn(['Second group heading','','',''],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_heading_as_long_as_the_longest_label_stays_over_its_members(self):
        # a long label beside values ends where the heading ends; the heading, set off by a group gap, is
        # followed by two members at the tight step: a heading group, not a wrapped label (r3 re-ladder 2)
        g=table([(('Long row label',60),('14','41.2','0.21')),('Short',None),('Alpha',('12','38.7','0.48')),
                 ('Beta',('11','37.0','0.40')),(('Group of stages',61),None),('Gamma',('9','44.0','0.09')),
                 ('Delta',('7','36.1','0.62'))],steps=[16,11,11,16,11,11])
        self.assertIn(['Group of stages','','',''],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_reference_category_without_values_stays_a_row(self):
        rs=[lab('Variable',5,0)]+[run(t,x,0,24) for t,x in zip(('OR','p','q'),(100,170,250))]
        gr=[rule(-4,0,320),rule(12,0,320)]
        rs+=[lab('Age',5,16)]+[run(v,x,16,24) for v,x in zip(('1.4','0.04','0.08'),(100,170,250))]
        rs+=[lab('Heading',5,28)]
        rs+=[lab('No = 1',8,40)]+[run(v,x,40,24) for v,x in zip(('3.0','0.01','0.14'),(100,170,250))]
        rs+=[lab('Yes = 2',8,52,30)]
        gr.append(rule(64,0,320))
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['No = 1','3.0','0.01','0.14'],g)
        self.assertIn(['Yes = 2','','',''],g)

    def test_a_heading_of_several_words_between_two_rows_stays_a_row(self):
        g=table([('Alpha',('14','41.2','0.21')),('Beta',('12','38.7','0.48')),(('Wet sites',28),None),
                 ('Gamma',('9','44.0','0.09')),('Delta',('7','36.1','0.62'))])
        self.assertIn(['Wet sites','','',''],g)
        self.assertIn(['Beta','12','38.7','0.48'],g)


class ValuesOnTheLastLabelLine(unittest.TestCase):
    def test_a_label_wrapped_above_its_values_joins_their_row(self):
        # rows 16 apart, a wrapped label's lines 11 apart; the first line leaves no room for the next word
        g=table([('Alpha',('14','41.2','0.21')),(('Long count of lone units',88),None),('per crew',('12','38.7','0.48')),
                 ('Gamma',('9','44.0','0.09')),(('Wide stretch of open sea',88),None),(('and the',40),None),
                 ('bay',('7','36.1','0.62'))],steps=[16,11,16,16,11,11])
        self.assertIn(['Long count of lone units per crew','12','38.7','0.48'],g)
        self.assertIn(['Wide stretch of open sea and the bay','7','36.1','0.62'],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_label_only_line_at_the_row_step_stays_a_row(self):
        # the same first line at the full row step: no witness that it binds to the line below
        g=table([('Alpha',('14','41.2','0.21')),(('Long count of lone units',88),None),('per crew',('12','38.7','0.48'))],
                steps=[16,16])
        self.assertIn(['Long count of lone units','','',''],g)


class StackedSubRows(unittest.TestCase):
    def test_a_stacked_cell_wrapped_at_other_lines_is_dealt_per_item(self):
        head=('Arm','Start','End','Change')
        rs=[lab(head[0],5,0)]+[run(t,x,0,40) for t,x in zip(head[1:],(100,170,250))]
        gr=[rule(-4,0,320),rule(12,0,320)]
        cols={100:['p1: 1.0 ±','0.1','p2: 2.0 ±','0.2'],170:['p1: 3.0 ±','0.3','p2: 4.0 ±','0.4'],
              250:['p1: 5.0 ± 0.5','p2: 6.0 ±','0.6']}
        rs.append(lab('a. Alpha',5,16))
        for x,ts in cols.items():
            for k,t in enumerate(ts): rs.append(run(t,x,16+12*k,6*len(t)))
        gr.append(rule(16+12*4,0,320))
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['a. Alpha','p1: 1.0 ± 0.1','p1: 3.0 ± 0.3','p1: 5.0 ± 0.5'],g)
        self.assertIn(['','p2: 2.0 ± 0.2','p2: 4.0 ± 0.4','p2: 6.0 ± 0.6'],g)


if __name__=='__main__':
    unittest.main()
