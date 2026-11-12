"""Lane tablesub, re-ladder round 4 (tablesub9): a label-only line over a stack of sub-items, each with a value
row of its own, is a group label (a row of its own, its values empty) and each sub-item stays its own row beside
its own values, also when the group label's line carries the block's row label in the first column (tablesub9b);
a label wrapped over lines beside ONE value row still joins. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule=t.c,t.run,t.page,t.grid,t.rule

VX=(170,230,290)


def head():
    # the second column's name wrapped over two head lines at the column's margin
    rs=[run('Model',5,0,30),run('Change',80,0,36),run('in dose',80,11,42),run('Odds',170,0,24),run('CI',230,0,12),run('p',290,0,6)]
    return rs,[rule(-4),rule(23)]


def stacked(indent=8,items=(('Upper half','Lower half'),('Upper part','Lower part')),mark='',label_on_group=False):
    """Each block: a header line ruled under, a group label alone on its line in the second column, then two
    sub-items set in under it, each with three values of its own."""
    rs,gr=head();y=27
    for k,(group,subs) in enumerate(zip(('Crude'+mark,'Weighted'+mark),items)):
        if k==0 and not label_on_group: rs.append(run('First model',5,y,60))
        rs+=[run('Ratio',170,y,30),run('Interval',230,y,42)]
        gr.append(rule(y+12));y+=16
        if label_on_group: rs.append(run(('First model','Second model')[k],5,y,66))   # the block's row label on the group line
        rs.append(run(group,80,y,6*len(group)));y+=12
        for j,s in enumerate(subs):
            rs+=[run(s,80+indent,y,6*len(s)),run(f'1.{k}{j}',VX[0],y,18),run(f'0.{j}-2.{k}',VX[1],y,30),run(f'0.0{j+1}',VX[2],y,24)]
            y+=12
        y+=2
    gr.append(rule(y))
    return rs,gr


def wrapped(at_foot=False,n=2):
    """Second-column labels wrapped over two lines (the second set in) beside one value row each."""
    rs,gr=head();y=27
    rs+=[run('First model',5,y,60),run('Ratio',170,y,30),run('Interval',230,y,42)]
    gr.append(rule(y+12));y+=16
    for k,(a,b) in enumerate([('Cut by a half','of the dose'),('Cut by a whole','of the dose')][:n]):
        rs+=[run(a,80,y,6*len(a)),run(b,88,y+12,6*len(b))]
        vy=y+12 if at_foot else y
        rs+=[run(f'1.{k}',VX[0],vy,18),run(f'0.{k}-2.0',VX[1],vy,30),run(f'0.0{k+1}',VX[2],vy,24)]
        y+=26
    gr.append(rule(y))
    return rs,gr


def rows(rs,gr):
    return grid(c.table_rows(rs,10,page(rs+gr))[0])


class GroupStacks(unittest.TestCase):
    def check(self,g,mark=''):
        labels=[r[1] for r in g]
        for group in ('Crude'+mark,'Weighted'+mark):
            self.assertIn(group,labels)
            row=g[labels.index(group)]
            self.assertEqual(row[2:],['']*(len(row)-2))
        for s in ('Upper half','Lower half','Upper part','Lower part'):
            self.assertIn(s,labels)
            self.assertNotEqual(g[labels.index(s)][2],'')

    def test_a_group_label_over_set_in_sub_items_is_a_row_of_its_own(self):
        self.check(rows(*stacked()))

    def test_sub_items_flush_under_the_group_label(self):
        self.check(rows(*stacked(indent=0)))

    def test_a_group_label_with_a_footnote_mark(self):
        self.check(rows(*stacked(mark='*')),'*')

    def test_a_group_label_beside_the_block_row_label_is_a_row_of_its_own(self):
        g=rows(*stacked(label_on_group=True))
        self.check(g)
        labels=[r[1] for r in g]
        self.assertEqual(g[labels.index('Crude')][0],'First model')
        self.assertEqual(g[labels.index('Weighted')][0],'Second model')
        self.assertEqual(g[labels.index('Upper half')][0],'')

    def test_a_group_label_beside_the_block_row_label_flush_sub_items(self):
        self.check(rows(*stacked(indent=0,label_on_group=True)))

    def test_no_value_row_is_left_without_its_label(self):
        g=rows(*stacked())
        for r in g:
            if any(r[2:]) and r[2] not in ('Odds','Ratio'): self.assertNotEqual(r[1],'',r)


class WrappedLabels(unittest.TestCase):
    def test_a_label_wrapped_beside_one_value_row_stays_whole(self):
        labels=[r[1] for r in rows(*wrapped())]
        self.assertIn('Cut by a half of the dose',labels)
        self.assertIn('Cut by a whole of the dose',labels)

    def test_a_lone_label_wrapped_with_its_values_on_its_last_line_stays_whole(self):
        labels=[r[1] for r in rows(*wrapped(at_foot=True,n=1))]
        self.assertIn('Cut by a half of the dose',labels)


if __name__=='__main__':
    unittest.main()
