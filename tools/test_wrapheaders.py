"""Two-line header cells under group labels, and caption title lines over a ruled table (lane
r3-wrapheaders). Synthetic fixtures with invented words; no corpus strings or IDs.

Group labels over repeated header blocks: a header line holding only labels, all different, over
column headers that repeat as identical blocks (a header wrapped over two lines is one cell), each
label centred on its block, repeats each label over every column of its block on a row of its own;
the wrapped header stays one cell. A wrapped header's first line repeats with its block (identical
texts), so it is never a group label. A units row under one-line headers, or labels over blocks that
differ, keep their reading. A caption title read with a ruled table (its label alone on the line
above) is a title row the caption takes; without the title state nothing changes.
"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width=None):
    width=width if width is not None else 6*len(text)
    return dict(id=f'{x}:{y}:{text}',kind='text',text=text,angle=0,line=y,box_px=[x,y,x+width,y+10],char_ids=[])


def centred(text,a,b,y):
    w=6*len(text); return run(text,(a+b-w)/2,y,w)


# Stub | three columns per block, two blocks.
BLOCKS=[[(120,170),(180,240),(250,280)],[(310,360),(370,430),(440,470)]]
ROWS=[('Alpha','1.21','0.9-1.4','0.01','1.17','0.8-1.3','0.04'),('Beta','0.94','0.7-1.2','0.66','0.97','0.7-1.3','0.84'),
      ('Gamma','2.63','1.9-3.7','0.02','2.41','1.7-3.4','0.03'),('Delta','1.48','1.1-2.0','0.01','1.36','0.9-1.9','0.06'),
      ('Epsilon','1.12','0.8-1.6','0.51','1.05','0.7-1.5','0.78')]


def grouped(labels=('Model one','Model two'),heads=(('Rate','ratio'),('','Interval'),('','P')),second=None,units=False):
    """labels centred over each block at y=0; header lines at y=13 (first lines of wrapped headers)
    and y=24 (one-line headers and second lines); a rule under the header; five value rows."""
    rs=[]
    for lab,blk in zip(labels,BLOCKS): rs.append(centred(lab,blk[0][0],blk[-1][1],0))
    for g,blk in enumerate(BLOCKS):
        hs=second if (second and g==1) else heads
        for (a,b),(l1,l2) in zip(blk,hs):
            if l1: rs.append(centred(l1,a,b,13))
            rs.append(centred(l2,a,b,24))
    rs.append(run('Item',0,24))
    y=44
    for r in ROWS:
        rs.append(run(r[0],0,y))
        for (a,b),v in zip(BLOCKS[0]+BLOCKS[1],r[1:]): rs.append(centred(v,a,b,y))
        y+=16
    page=dict(elements=rs+[dict(kind='rule',box_px=[0,-6,480,-5]),dict(kind='rule',box_px=[0,37,480,38]),dict(kind='rule',box_px=[0,y,480,y+1])])
    return rs,page


def texts(rows):
    return [[' '.join(x) for x in r] for r in rows if r]


class RepeatedBlockLabels(unittest.TestCase):
    def test_labels_repeat_over_their_blocks_and_the_wrapped_header_is_one_cell(self):
        rs,page=grouped()
        t=texts(c.table_rows(rs,10,page)[0])
        self.assertIn(['Model one']*3+['Model two']*3,[r[1:] for r in t])
        self.assertIn(['Rate ratio','Interval','P','Rate ratio','Interval','P'],[r[1:] for r in t])
        self.assertFalse(any('Model one' in x and x!='Model one' for r in t for x in r))

    def test_a_wrapped_middle_header_stays_one_cell(self):
        rs,page=grouped(heads=(('','Beta'),('Standard','error'),('','P')))
        t=texts(c.table_rows(rs,10,page)[0])
        self.assertIn(['Model one']*3+['Model two']*3,[r[1:] for r in t])
        self.assertIn(['Beta','Standard error','P','Beta','Standard error','P'],[r[1:] for r in t])
        self.assertFalse(any(r[1:]==['Standard']*6 for r in t))

    def test_identical_labels_are_wrapped_header_lines_not_group_labels(self):
        rs,page=grouped(labels=('Model','Model'))
        t=texts(c.table_rows(rs,10,page)[0])
        self.assertNotIn(['Model']*6,[r[1:] for r in t])

    def test_labels_over_different_blocks_keep_their_reading(self):
        rs,page=grouped(second=(('Rate','ratio'),('','Interval'),('','Count')))
        base=texts(c.table_rows(rs,10,page)[0])
        self.assertNotIn(['Model one']*3+['Model two']*3,[r[1:] for r in base])

    def test_units_row_under_one_line_headers_stays_with_its_header(self):
        rs=[run('Item',0,24)]
        cols=[(120,190),(200,270),(280,350),(360,430)]
        for (a,b),h in zip(cols,['Depth','Level','Width','Height']): rs.append(centred(h,a,b,13)); rs.append(centred('(mm)',a,b,24))
        y=44
        for r in ROWS:
            rs.append(run(r[0],0,y))
            for (a,b),v in zip(cols,r[1:5]): rs.append(centred(v,a,b,y))
            y+=16
        page=dict(elements=rs+[dict(kind='rule',box_px=[0,6,440,7]),dict(kind='rule',box_px=[0,37,440,38]),dict(kind='rule',box_px=[0,y,440,y+1])])
        t=texts(c.table_rows(rs,10,page)[0])
        self.assertEqual(t[0],['Item','Depth (mm)','Level (mm)','Width (mm)','Height (mm)'])


def gline(y,cells):
    items=[]
    for x,text in cells:
        for word in text.split():
            items.append(dict(box=[x,y,x+6*len(word),y+10],text=word,id=f'run:{y}:{x}'))
            x+=6*len(word)+4
    return dict(text=' '.join(w['text'] for w in items),items=items)


class LayoutGridBlocks(unittest.TestCase):
    def test_layout_grid_spans_group_labels_over_repeated_sub_header_blocks(self):
        cols=[0,80,140,200,280,340,400]
        lines=[gline(0,[(106,'Left arm cohort'),(303,'Right arm cohort')]),
               gline(15,[(cols[3],'Area'),(cols[6],'Area')]),
               gline(28,[(0,'Item'),(cols[1],'Mean'),(cols[2],'Count'),(cols[3],'under'),(cols[4],'Mean'),(cols[5],'Count'),(cols[6],'under')])]
        for i,y in enumerate((50,66,82)):
            lines.append(gline(y,[(0,'Row'+'abc'[i]),(cols[1],'1.5'),(cols[2],'12'),(cols[3],'0.8'),(cols[4],'2.5'),(cols[5],'14'),(cols[6],'0.9')]))
        rows,notes,ev=c.layout_grid(dict(lines=lines,graphics=[dict(kind='rule',box=[0,42,460,42.5])],angle=0),[])
        self.assertIsNotNone(rows,ev)
        g=[[' '.join(p) for p in r] for r in rows]
        self.assertEqual(g[0],['','Left arm cohort','Left arm cohort','Left arm cohort','Right arm cohort','Right arm cohort','Right arm cohort'])
        self.assertEqual(g[1],['Item','Mean','Count','Area under','Mean','Count','Area under'])


class RuledTitleRows(unittest.TestCase):
    def ruled(self):
        xs=[0,90,180,270]
        rs=[run('Wear outcome by block',2,0)]
        rs+=[run(t,x+3,22) for x,t in zip(xs,['Study','Design','Substrate'])]
        y=44
        for i in range(4):
            rs+=[run(t,x+3,y) for x,t in zip(xs,[f'Study {i+1}','Parallel','Enamel'])]
            y+=22
        g=[dict(kind='rule',box_px=[0,yy,270,yy+.5]) for yy in range(16,y+1,22)]+[dict(kind='rule',box_px=[x,16,x+.5,y-6]) for x in xs]
        return rs,dict(elements=rs+g)

    def test_title_band_above_a_ruled_table_is_a_title_row(self):
        rs,page=self.ruled()
        state=dict(ids={rs[0]['id']},dropped=False)
        rows=c.table_rows(rs,10,dict(page,_table_title=state))[0]
        self.assertTrue(state['dropped'])
        self.assertTrue(getattr(rows[0],'title',False))
        self.assertFalse(any(getattr(r,'title',False) for r in rows[1:]))
        self.assertEqual([' '.join(x) for x in rows[1]],['Study','Design','Substrate'])

    def test_without_title_state_the_ruled_rows_are_unchanged(self):
        rs,page=self.ruled()
        rows=c.table_rows(rs,10,page)[0]
        self.assertFalse(any(getattr(r,'title',False) for r in rows))


if __name__=='__main__':
    unittest.main()


class LayoutGridUnruledHeader(unittest.TestCase):
    """No rule under the header: an interval's coverage label is a header and a reference marker a
    value, so the header ends above the first row; a right-aligned estimate header wrapped over two
    lines joins its second line; group labels over the repeated blocks span them."""
    def table(self,labels=('Left arm cohort','Right arm cohort')):
        cols=[0,80,140,220,280,340,420]
        lines=[gline(0,[(122,labels[0]),(319,labels[1])]),
               gline(14,[(cols[1]+30-24,'Rate'),(cols[4]+30-24,'Rate')]),
               gline(28,[(0,'Item'),(cols[1],'ratio'),(cols[2],'(95% CI)'),(cols[3],'P'),(cols[4],'ratio'),(cols[5],'(95% CI)'),(cols[6],'P')]),
               gline(44,[(0,'Rowz'),(cols[1]+6,'Ref.'),(cols[4]+6,'Ref.')])]
        for i,y in enumerate((60,76,92)):
            lines.append(gline(y,[(0,'Row'+'abc'[i]),(cols[1]+6,'1.5'),(cols[2],'(1.1-2.0)'),(cols[3],'0.04'),(cols[4]+6,'2.5'),(cols[5],'(1.9-3.1)'),(cols[6],'0.01')]))
        return lines

    def test_header_ends_above_the_reference_row_and_labels_span_their_blocks(self):
        rows,notes,ev=c.layout_grid(dict(lines=self.table(),graphics=[],angle=0),[])
        self.assertIsNotNone(rows,ev)
        g=[[' '.join(p) for p in r] for r in rows]
        self.assertEqual(ev['header_lines'],3)
        self.assertEqual(g[0][1:],['Left arm cohort']*3+['Right arm cohort']*3)
        self.assertEqual(g[1],['Item','Rate ratio','(95% CI)','P','Rate ratio','(95% CI)','P'])
        self.assertEqual(g[2],['Rowz','Ref.','','','Ref.','',''])


class CentredTitleRuns(unittest.TestCase):
    """A label alone centred over its table with the title centred under it: the title lines are the
    caption's (centred caption style); a line neither flush with nor centred under the label is not."""
    def runs(self,title_x):
        lab=dict(run('Table 4.',170,0),size_px=12,run_size_px=12)
        t1=dict(run('Outcome of the trial blocks by arm',title_x,16),size_px=12,run_size_px=12)
        t2=dict(run('and season of planting',title_x+36,30),size_px=12,run_size_px=12)
        cells=[dict(run(t,x,y),size_px=10,run_size_px=10) for y in (52,66,80) for x,t in ((0,'Block'),(120,'Arm'),(240,'Yield'))]
        return lab,[t1,t2]+cells

    def test_centred_title_lines_are_title_runs(self):
        lab,cells=self.runs(95)   # centre of 'Outcome ...' (204 px wide) = 197 = label centre
        got=c.table_title_runs(lab,[lab],cells)
        self.assertEqual([e['text'] for e in got],['Outcome of the trial blocks by arm','and season of planting'])

    def test_off_centre_line_is_not_a_title_run(self):
        lab,cells=self.runs(10)
        self.assertEqual(c.table_title_runs(lab,[lab],cells),[])
