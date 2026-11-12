"""Two neighbouring columns filled on the same lines stay two columns (lane r2-cells).

The vote joins a gutter that most lines cross from a number to a bracket (an estimate beside
its interval is normally one cell). A header pair above the two sides, a channel wider than a
line height on every line filled on both sides, and each side aligned with its own header cell
keep the gutter, with or without reference-level lines filled on one side only. A header printed
as one run over both sides, or values set with a word space, stay one column.
"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width):
    return dict(id=f'{x}:{y}:{text}',kind='text',text=text,angle=0,line=y,
                box_px=[x,y,x+width,y+10],char_ids=[])


ROWS=[('Dose',None,0),('Placebo','ref',10),('Low dose',('2.4','(1.1 to 3.9)','0.02'),10),('High dose',('3.1','(1.8 to 5.2)','<0.001'),10),
      ('Season',None,0),('Wet season','ref',10),('Dry season',('0.8','(0.5 to 1.3)','0.41'),10),
      ('Plots',None,0),('Older plots',('1.6','(0.9 to 2.8)','0.09'),10),('Newer plots',('1.2','(0.7 to 2.0)','0.48'),10),
      ('Field edge',('4.0','(2.2 to 7.3)','0.003'),0)]


def paired_table(reference=True,header_one_run=False,word_space=False):
    """Item | estimate | interval | P, grouped under unindented group labels. The estimates are
    centred under their header, the intervals share the left edge of theirs; a channel of about
    four line heights separates them. A reference level stands under the interval header on its
    own lines when reference is set (otherwise those lines hold an estimate pair too)."""
    rs=[run('Item',0,0,40),run('P',330,0,12)]
    if header_one_run: rs.append(run('Ratio (95% CI)',140,0,130))
    else: rs+=[run('Ratio',140,0,40),run('(95% CI)',210,0,60)]
    y=22
    for label,vals,indent in ROWS:
        rs.append(run(label,indent,y,70))
        if vals=='ref':
            vals=None if reference else ('1.0','(0.6 to 1.7)','0.95')
            if reference: rs.append(run('Ref.',240,y,28))
        if vals is None: pass
        elif word_space:
            rs.append(run(f'{vals[0]} {vals[1]}',140,y,105)); rs.append(run(vals[2],330,y,30))
        else:
            rs+=[run(vals[0],149,y,22),run(vals[1],210,y,75),run(vals[2],330,y,30)]
        y+=18
    page=dict(elements=rs+[dict(kind='rule',box_px=[0,-6,380,-5]),dict(kind='rule',box_px=[0,14,380,15]),dict(kind='rule',box_px=[0,y,380,y+1])])
    return rs,page


def body(rows):
    return [[' '.join(cell) for cell in r] for r in rows if r and r[0] and r[0][0] not in ('Item',)]


class PairedCells(unittest.TestCase):
    def test_header_pair_with_reference_rows_keeps_two_columns(self):
        rows=c.table_rows(*paired_table())[0]
        self.assertEqual(len(rows[0]),4)
        self.assertEqual([' '.join(x) for x in rows[0]],['Item','Ratio','(95% CI)','P'])
        b=body(rows)
        self.assertIn(['Placebo','','Ref.',''],b)
        self.assertIn(['Low dose','2.4','(1.1 to 3.9)','0.02'],b)
        self.assertIn(['Field edge','4.0','(2.2 to 7.3)','0.003'],b)

    def test_header_pair_without_reference_rows_keeps_two_columns(self):
        rows=c.table_rows(*paired_table(reference=False))[0]
        self.assertEqual(len(rows[0]),4)
        self.assertIn(['High dose','3.1','(1.8 to 5.2)','<0.001'],body(rows))

    def test_header_pair_starts_its_own_row_under_a_group_label(self):
        # A short group label over the interval header (sharing no edge or centre with it): the
        # bracketed header '(95% CI)' below it is no qualifier of the label; the header row stays.
        rs,page=paired_table(reference=False)
        rs.append(run('Group',216,-16,20))
        rows=c.table_rows(rs,10,page)[0]
        texts=[[' '.join(x) for x in r] for r in rows if r]
        self.assertIn(['Item','Ratio','(95% CI)','P'],texts)
        self.assertTrue(any('Group' in r and '(95% CI)' not in ' '.join(r) for r in (' | '.join(t) for t in texts)))

    def test_one_run_header_over_both_sides_stays_one_column(self):
        # The estimate and its interval stand apart, but one header cell covers them: one column.
        rows=c.table_rows(*paired_table(header_one_run=True))[0]
        self.assertEqual(len(rows[0]),3)
        self.assertIn(['Low dose','2.4 (1.1 to 3.9)','0.02'],body(rows))

    def test_value_with_interval_in_one_run_stays_one_column(self):
        rows=c.table_rows(*paired_table(header_one_run=True,word_space=True))[0]
        self.assertEqual(len(rows[0]),3)
        self.assertIn(['Low dose','2.4 (1.1 to 3.9)','0.02'],body(rows))

    def lines_of(self,rs):
        return c.table_lines(c.table_words(rs,None,c.frame(0)))

    def test_rule_needs_alignment_with_each_header(self):
        rs,page=paired_table()
        self.assertTrue(c.paired_header_columns(self.lines_of(rs),190,10,100,310))
        # Move one interval off the shared left edge of its header: the right side has no alignment.
        moved=[dict(e,box_px=[e['box_px'][0]+10]+e['box_px'][1:3]+[e['box_px'][3]]) if e['text']=='(0.5 to 1.3)' else e for e in rs]
        moved=[dict(e,box_px=[e['box_px'][0],e['box_px'][1],e['box_px'][2]+10,e['box_px'][3]]) if e['text']=='(0.5 to 1.3)' else e for e in moved]
        self.assertFalse(c.paired_header_columns(self.lines_of(moved),190,10,100,310))

    def test_narrow_channel_between_aligned_sides_in_one_run_is_a_pair(self):
        # Right-aligned estimates beside left-aligned intervals: the channel (8) is narrower than a
        # line height (10 here is the run height; the channel is still well over two word spaces),
        # and the producer saved each estimate with its interval as ONE run.
        rs=[run('Item',0,0,40),run('Beta',150,0,22),run('(95% CI)',180,0,60),run('P',330,0,12)]
        y=22
        for i,(e,iv) in enumerate([('-0.42','(-0.71 to -0.13)'),('0.08','(0.02 to 0.14)'),('0.21','(-0.04 to 0.46)'),('-0.03','(-0.09 to 0.03)')]):
            one=dict(run(e+' '+iv,172-6*len(e),y,0),char_ids=[])
            words=[([172-6*len(e),y,172,y+10],e,one),([180,y,180+5*len(iv.split()[0]),y+10],iv.split()[0],one)]
            x0=words[-1][0][2]
            for w in iv.split()[1:]:
                words.append(([x0+3,y,x0+3+5*len(w),y+10],w,one)); x0=x0+3+5*len(w)
            rs.append((f'Row {i}',y,words)); y+=18
        lines=[dict(items=[([0,0,40,10],'Item',rs[0]),([150,0,172,10],'Beta',rs[1]),([180,0,210,10],'(95%',rs[2]),([213,0,228,10],'CI)',rs[2])])]
        for label,yy,words in rs[4:]:
            lab=run(label,0,yy,40); lines.append(dict(items=[([0,yy,40,yy+10],label,lab)]+words))
        self.assertTrue(c.paired_header_columns(lines,176,10,100,310))
        # The same values set a word space from their estimates are one phrase: no pair.
        for L in lines[1:]:
            its=L['items']; shift=its[2][0][0]-its[1][0][2]-3
            L['items']=its[:2]+[([b[0]-shift,b[1],b[2]-shift,b[3]],t,e) for b,t,e in its[2:]]
        self.assertFalse(c.paired_header_columns(lines,175,10,100,310))

    def test_short_label_centred_over_the_pair_is_a_group_label(self):
        rs,page=paired_table()
        rs.append(run('All',192,-16,16))   # centred over Ratio (140-180) and (95% CI) (210-270)
        self.assertTrue(c.paired_header_columns(self.lines_of(rs),190,10,100,310))

    def test_rule_needs_a_column_channel_not_a_word_space(self):
        rs,page=paired_table()
        near=[dict(e,box_px=[e['box_px'][0]+30,e['box_px'][1],e['box_px'][2]+30,e['box_px'][3]]) if e['text'] in ('Ratio',) or e['text'][:1].isdigit() and e['box_px'][0]<200 else e for e in rs]
        self.assertFalse(c.paired_header_columns(self.lines_of(near),205,10,100,310))

    def test_group_label_over_both_sides_does_not_stop_the_pair(self):
        # A group label centred over the estimate and interval headers spans the channel; the
        # header pair below it still proves the two columns.
        rs,page=paired_table()
        rs.append(run('Treated orchards',150,-16,110))
        self.assertTrue(c.paired_header_columns(self.lines_of(rs),190,10,100,310))
        # A lone label over one side set at the header's leading is that cell's wrapped first line:
        # no proof; set further up it is a group label and the pair stands (w1 form).
        rs,page=paired_table()
        rs.append(run('Cohort',140,-12,40))
        self.assertFalse(c.paired_header_columns(self.lines_of(rs),190,10,100,310))
        rs,page=paired_table()
        rs.append(run('Cohort',140,-20,40))
        self.assertTrue(c.paired_header_columns(self.lines_of(rs),190,10,100,310))

    def test_label_over_one_side_only_is_no_group_label(self):
        # A label aligned with the interval header only: it could be the first line of that
        # header cell, so the pair is not proven.
        rs,page=paired_table()
        rs.append(run('Treated',210,-12,40))   # shares the left edge of '(95% CI)', at the header's leading
        self.assertFalse(c.paired_header_columns(self.lines_of(rs),190,10,100,310))

    def test_symbol_header_cell_counts(self):
        # '%' over right-aligned percentages beside '(95% CI)' over intervals: a header pair.
        rs=[run('Item',0,0,40),run('%',165,0,7),run('(95% CI)',184,0,60)]
        for i,(p,iv) in enumerate([('18.3','(13.5 to 23.9)'),('12.6','(8.6 to 17.6)'),('23.9','(18.6 to 29.9)')]):
            y=20+16*i; rs+=[run(f'Row {i}',0,y,40),run(p,152,y,20),run(iv,184,y,70)]
        self.assertTrue(c.paired_header_columns(self.lines_of(rs),178,10,100,310))
        # A bare number is no header cell.
        rs[1]=run('12',160,0,12)
        self.assertFalse(c.paired_header_columns(self.lines_of(rs),178,10,100,310))

    def test_repeated_group_label_row_is_no_repeated_text_warning(self):
        label=['Maximum tensile stress of the seasoned timbers']
        rows=[c.TableRow([['Title'],[],[]]),c.TableRow([['Sub'],[],[]]),c.TableRow([[],label,label]),c.TableRow([['Oak'],['61.2'],['(4.1)']])]
        self.assertTrue(c.table_warnings(rows,[]))
        rows[2].paired_label=True
        self.assertFalse(c.table_warnings(rows,[]))

    def test_subgroup_heading_row_neither_proves_nor_refutes(self):
        # A heading set from the stub across the channel, between the rows, does not stop the pair.
        rs,page=paired_table(reference=False)
        rs.append(run('Treated plots of the northern orchard',0,22+18*4+8,240))
        self.assertTrue(c.paired_header_columns(self.lines_of(rs),190,10,100,310))

    def test_empty_group_cell_is_written_empty(self):
        row=c.TableRow([[],['Dry'],['Wet']],group=True)
        class J:
            lines=staticmethod(lambda parts: ' '.join(parts))
        md=c.table_markdown([c.TableRow([['Timber'],['A'],['B']]),row],J())
        self.assertNotIn('****','\n'.join(md))

    def test_repeated_label_is_no_header(self):
        # 'Level' followed by a level on every line: the first line is a row like the others.
        rs=[]
        for i,lv in enumerate(['I–II','I–III','II','II–III','III']):
            y=16*i; rs+=[run('Level',0,y,30),run(lv,45,y,25),run(f'{i+1} SRs',120,y,30)]
        self.assertFalse(c.paired_header_columns(self.lines_of(rs),38,10,None,100))

    def test_one_run_header_is_not_a_pair(self):
        rs,page=paired_table(header_one_run=True)
        self.assertFalse(c.paired_header_columns(self.lines_of(rs),190,10,100,310))


if __name__=='__main__':
    unittest.main()
