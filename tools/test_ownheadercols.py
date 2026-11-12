"""Adjacent header cells with their own data columns stay separate columns (lane iss-05).

When every data row fills only one of two neighbouring columns, no data line pairs across
their gutter. The header cells above, a clear channel from them down and values centred
under each header on at least two lines keep the gutter; without that evidence it is not kept.
"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width):
    return dict(id=f'{x}:{y}:{text}',kind='text',text=text,angle=0,line=y,
                box_px=[x,y,x+width,y+10],char_ids=[])


def alternating_table(sides='ABAABBABABAABABBAB',stray=None):
    """A spanning label over two header baselines; the values of the two variant columns alternate
    row by row. The spanning label joins the header cells beneath it, so the header-column count
    cannot restore the gutter between the variant columns."""
    rs=[run('Targeted variants analysed',140,-14,217),run('Study',0,0,50),run('Gene (-1)',140,0,60),run('Gene (+2)',225,0,60),run('Other',310,0,40),run('Group',400,0,50),
        run('rs100',145,13,45),run('rs200',232,13,45),run('rs300',312,13,45)]
    for i,s in enumerate(sides):
        y=35+16*i
        rs+=[run(f'Author {i+1}',0,y,70),run('Yes',160 if s=='A' else 245,y,22),run('Yes',325,y,22),run(f'Group {i+1}',400,y,60)]
    if stray: rs.append(run(stray[0],stray[1],35,stray[2]))
    end=35+16*len(sides)
    page=dict(elements=rs+[dict(kind='rule',box_px=[0,-20,470,-19]),dict(kind='rule',box_px=[140,-3,357,-2]),dict(kind='rule',box_px=[0,27,470,28]),
                           dict(kind='rule',box_px=[0,end,470,end+1])])
    return rs,page


class OwnHeaderColumns(unittest.TestCase):
    def test_alternating_values_keep_both_header_columns(self):
        rs,page=alternating_table()
        rows,notes=c.table_rows(rs,10,page)
        self.assertFalse(notes)
        self.assertEqual(len(rows[0]),5)
        self.assertEqual([r[1:3] for r in rows[:2]],[[['Targeted variants analysed'],['Targeted variants analysed']],[['Gene (-1)','rs100'],['Gene (+2)','rs200']]])
        self.assertEqual([(bool(r[1]),bool(r[2])) for r in rows[2:]],[(s=='A',s=='B') for s in 'ABAABBABABAABABBAB'])

    def lines_of(self,rs):
        f=c.frame(0);items=c.table_words(rs,None,f)
        return c.table_lines(items)

    def test_rule_needs_values_under_both_headers(self):
        # Gutters at 100 and 297 bound the two variant columns, as the caller passes them.
        # One value on the right is a stray, not a column (two is the paired-line recurrence).
        rs,page=alternating_table('AAAAAAAAAAAAAAAAAB')
        self.assertFalse(c.own_header_columns(self.lines_of(rs),212,100,297))
        rs,page=alternating_table('AAAAAAAAAAAAAAAABB')
        self.assertTrue(c.own_header_columns(self.lines_of(rs),212,100,297))

    def test_one_row_filled_on_both_sides_does_not_stop_alternating_columns(self):
        # A row marked under both headers is a pair; the columns still alternate on the other rows.
        rs,page=alternating_table()
        rs.append(run('Yes',245,35,22))
        self.assertTrue(c.own_header_columns(self.lines_of(rs),212,100,297))

    def test_lone_values_on_one_side_only_are_not_alternation(self):
        # Every row is marked on the left; the right is marked only on rows that also hold a left
        # mark. No value stands alone on the right, so the columns do not alternate.
        rs,page=alternating_table('AAAAAAAAAAAAAAAAAA')
        rs+=[run('Yes',245,35+16*i,22) for i in (2,5,9)]
        self.assertFalse(c.own_header_columns(self.lines_of(rs),212,100,297))

    def test_text_crossing_the_channel_below_the_headers_vetoes(self):
        rs,page=alternating_table(stray=('a long remark across both',150,120))
        self.assertFalse(c.own_header_columns(self.lines_of(rs),212,100,297))

    def test_one_run_on_both_sides_is_not_a_header_pair(self):
        rs=[run('Gene',140,0,30),run('(+2)',250,0,30)]
        rs[1]=dict(rs[0],text='Gene (+2)',box_px=[140,0,280,10])
        lines=[dict(items=[([140,0,170,10],'Gene',rs[1]),([250,0,280,10],'(+2)',rs[1])])]
        for i,x in enumerate([150,255,150,255]):
            e=run('Yes',x,20+15*i,22);lines.append(dict(items=[(e['box_px'],'Yes',e)]))
        self.assertFalse(c.own_header_columns(lines,212))


def one_header_line_table(group=True):
    """A group label without an underline over ONE line of leaf headers; the marks of the two leaf
    columns alternate. Only the leaf header line pairs across their gutter, and the marks, narrower
    than the leaf headers, open word-gap channels beside them."""
    rs=[run('Boat',0,0,40),run('Probe A',150,0,58),run('Probe B',260,0,58),run('Hauls',380,0,45),run('Bay',470,0,30)]
    if group: rs.append(run('Probe Carried',200,-14,70))
    for i,s in enumerate('ABBABAABAB'):
        y=20+16*i
        rs+=[run(f'Boat {i+1}',0,y,55),run('x',175 if s=='A' else 285,y,8),run(str(i+2),395,y,10),run(f'Bay {i%3+1}',470,y,40)]
    end=20+16*10
    page=dict(elements=rs+[dict(kind='rule',box_px=[0,-20,520,-19]),dict(kind='rule',box_px=[0,13,520,14]),dict(kind='rule',box_px=[0,end,520,end+1])])
    return rs,page


def label_row_table():
    """One header line; each group label line holds only the test column (P), each item line only
    the estimate column: the two neighbouring header cells never share a data line. A title line
    in the table's frame stands above the header line, so the header is not the first line."""
    rs=[run('Ratios of the trial groups by level',0,-16,330),run('Item',0,0,40),run('Count',150,0,45),run('Ratio (range)',250,0,110),run('P',430,0,10)]
    y=20
    for g in range(3):
        rs+=[run(f'Group {g+1}',0,y,60),run(f'0.{g+2}1',420,y,30)];y+=16
        for k in range(3):
            rs+=[run(f'level {k+1}',10,y,50),run(f'{k+10} (3.{k})',150,y,50),run(f'1.{k}0 (0.{k+1} to 2.{k})',255,y,100)];y+=16
    page=dict(elements=rs+[dict(kind='rule',box_px=[0,-22,470,-21]),dict(kind='rule',box_px=[0,13,470,14]),dict(kind='rule',box_px=[0,y,470,y+1])])
    return rs,page


class OneHeaderLine(unittest.TestCase):
    def test_one_leaf_header_line_keeps_both_columns(self):
        for group in (True,False):
            rs,page=one_header_line_table(group)
            rows,notes=c.table_rows(rs,10,page)
            self.assertEqual(len(rows[0]),5,group)
            body=[r for r in rows if r and r[0] and r[0][0].startswith('Boat ')]
            self.assertEqual([(bool(r[1]),bool(r[2])) for r in body],[(s=='A',s=='B') for s in 'ABBABAABAB'])

    def test_label_lines_and_item_lines_fill_neighbouring_columns(self):
        rs,page=label_row_table()
        rows,notes=c.table_rows(rs,10,page)
        head=next(r for r in rows if r[0]==['Item'])
        # The title line's own placement is not this rule's concern.
        self.assertEqual((len(head),head[2][-1:],head[3]),(4,['Ratio (range)'],['P']))
        rows=rows[rows.index(head):]
        # Row grouping is not this rule's concern; each column holds only its own header's values.
        self.assertEqual([t for r in rows[1:] for t in r[3]],[f'0.{g+2}1' for g in range(3)])
        self.assertEqual(sum(len(r[2]) for r in rows[1:]),9)
        self.assertTrue(all(' to ' in t for r in rows[1:] for t in r[2]))

    def test_rows_filled_on_both_sides_are_left_to_the_vote(self):
        # An estimate beside its interval: the header cells are separate runs, but every data line
        # after the reference level holds cells on both sides, so the values do not alternate and
        # the rule does not apply.
        rs=[run('Ratio',250,0,40),run('(range)',330,0,55),run('1.00',255,20,30)]
        for i in range(1,6):
            rs+=[run(f'1.{i}0',255,20+16*i,30),run(f'(0.{i} to 2.{i})',330,20+16*i,70)]
        f=c.frame(0);lines=c.table_lines(c.table_words(rs,None,f))
        self.assertFalse(c.own_header_columns(lines,310))


if __name__=='__main__':
    unittest.main()
