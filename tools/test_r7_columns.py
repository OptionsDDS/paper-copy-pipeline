"""Round 7, lane r7-columns: the column rules TC4 to TC7 in table_rows.

TC4: a header cell (words on one header line set under two word spaces apart) goes whole to the body column
whose ink it overlaps. TC5: a header cell over two or more columns is a spanning header, repeated over its
columns, never cut at its word gaps. TC6: no column holds no word of the page. TC7: where the marks do not
settle a place, the grid stays as the placement made it and the place is listed as doubtful.
Every table here is made up; words are saved one run per word, as some producers save them.
"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

W=6.0   # width of one character in these made-up tables


def words(text,x,y,space=3):
    """one run per word, set from x with one character's width between words"""
    out=[]
    for w in text.split():
        out.append(dict(id=f'{x:.0f}:{y}:{w}',kind='text',text=w,angle=0,line=y,box_px=[x,y,x+W*len(w),y+12],char_ids=[]))
        x+=W*len(w)+space
    return out


def cell(text,x,y):
    """one run for a whole cell (a body cell saved as one run)"""
    return [dict(id=f'{x:.0f}:{y}:{text}',kind='text',text=text,angle=0,line=y,box_px=[x,y,x+W*len(text),y+12],char_ids=[])]


def texts(rows):
    return [[' '.join(cell) for cell in r] for r in rows]


def doubts(rows):
    return sorted({(rule,reason) for r in rows for rule,box,reason in getattr(r,'r7_doubts',())})


class ColumnRules(unittest.TestCase):
    def one_line_header(self):
        """A one-line header over five columns, the count header wider than its narrow count column (AX13 form),
        standing above the first line with two values; no drawn header band."""
        rs=cell('No.',0,0)+cell('Problem areas',60,0)+words('Number of cases',230,0)+cell('Remedial measures',330,0)+cell('Days',520,0)
        labels=['Wrong needle position','Aspiration of blood','Inadequate depth','Pain on injection','Trismus','Broken tip']
        remedies=['Needle withdrawn','Direction changed','Repeat administration','Slow injection','Warm compress','Surgical removal']
        for i in range(6):
            y=30+20*i
            rs+=cell(f'{i+1}.',0,y)+cell(labels[i],60,y)+cell(f'0{i+1}',230,y)+cell(remedies[i],330,y)+cell(f'{3+i}',520,y)
        return rs,dict(elements=rs)

    def test_tc4_header_cell_goes_whole_to_its_ink_column(self):
        rs,page=self.one_line_header()
        rows,notes=c.table_rows(rs,10,page)
        self.assertEqual(texts(rows)[0],['No.','Problem areas','Number of cases','Remedial measures','Days'])
        self.assertEqual(texts(rows)[1],['1.','Wrong needle position','01','Needle withdrawn','3'])

    def spanning_table(self,centred_names=False):
        """A stub header and one group header on the top line over three value columns; the group header is
        narrower than its three columns and reaches past the middle gutters only (AT06 form)."""
        rs=words('Variable',0,0)+words('Control-Treatment Group',224,0)
        rs+=words('Baseline',170,20)+words('2 Months',270,20)+words('6 Months',370,20)
        for i in range(4):
            y=45+20*i
            rs+=cell(f'Measure {chr(65+i)}',0,y)+cell(f'{20+i}±3',180,y)+cell(f'{30+i}±4',280,y)+cell(f'{40+i}±5',380,y)
        page=dict(elements=rs+[dict(kind='rule',box_px=[0,-4,430,-3]),dict(kind='rule',box_px=[0,37,430,38]),dict(kind='rule',box_px=[0,130,430,131])])
        return rs,page

    def test_tc5_spanning_header_repeated_over_its_reach(self):
        rs,page=self.spanning_table()
        rows,notes=c.table_rows(rs,10,page)
        t=texts(rows)
        self.assertEqual(t[0],['Variable']+['Control-Treatment Group '+s for s in ('Baseline','2 Months','6 Months')])
        self.assertEqual(t[1],['Measure A','20±3','30±4','40±5'])

    def wide_spanning_table(self):
        """A spanning header saved word by word over four value columns, its words standing over the gutters
        (AV06 form): the word-by-word placement opened empty columns for its pieces."""
        rs=words('CHARACTERISTIC',0,0)+words('AGE GROUP, Y (STANDARD ERROR)',180,0,space=4)+words('TEST',450,0)
        rs+=words('30-44',150,20)+words('45-64',220,20)+words('65-79',290,20)+words('All',360,20)+words('(P)',450,20)
        for i in range(5):
            y=45+20*i
            rs+=cell(f'Row {i}',0,y)+cell(f'{10+i}.1',150,y)+cell(f'{20+i}.2',220,y)+cell(f'{30+i}.3',290,y)+cell(f'{40+i}.4',360,y)+cell('<.001',450,y)
        page=dict(elements=rs+[dict(kind='rule',box_px=[0,-4,490,-3]),dict(kind='rule',box_px=[0,37,490,38]),dict(kind='rule',box_px=[0,150,490,151])])
        return rs,page

    def test_tc5_tc6_wide_spanning_header_never_cut_and_no_empty_column(self):
        rs,page=self.wide_spanning_table()
        rows,notes=c.table_rows(rs,10,page)
        t=texts(rows)
        self.assertEqual(len(t[0]),6)
        self.assertTrue(all(cell.startswith('AGE GROUP, Y (STANDARD ERROR)') for cell in t[0][1:5]),t[0])
        self.assertEqual(t[1],['Row 0','10.1','20.2','30.3','40.4','<.001'])
        self.assertTrue(all(all(cell.strip() for cell in r) for r in t[1:]))

    def test_tc5_negative_cells_set_close_each_centred_over_its_column_stay(self):
        """Nearest look-alike: author cells set closer than two word spaces, each centred over its own column.
        The word gaps say one cell, the columns say several: the cut stays and the place is listed (TC7)."""
        rs=words('Aspects',0,20)
        names=['1. Dentino','2. Dorfer','3. Danser','4. Rosema']
        x=110; centres=[]
        for n in names:
            ws=words(n,x,0,space=4); rs+=ws
            centres.append((ws[0]['box_px'][0]+ws[-1]['box_px'][2])/2); x=ws[-1]['box_px'][2]+5
        for i in range(5):
            y=45+20*i
            rs+=cell(f'Item {i}',0,y)
            for cx in centres: rs+=cell('+',cx-W/2,y)
        page=dict(elements=rs+[dict(kind='rule',box_px=[0,-4,400,-3]),dict(kind='rule',box_px=[0,37,400,38]),dict(kind='rule',box_px=[0,150,400,151])])
        rows,notes=c.table_rows(rs,10,page)
        t=texts(rows)
        self.assertNotIn('1. Dentino 2. Dorfer 3. Danser 4. Rosema',[cell_ for r in t for cell_ in r])
        self.assertTrue({('TC7','header_cell_pieces_over_own_columns'),('TC7','header_cells_by_column_edges')}&set(doubts(rows)))

    def test_tc7_columns_not_strips_plus_one_is_listed_and_the_grid_kept(self):
        """A body label running across the first gutter leaves fewer strips than columns: the place is listed
        and every printed word stays in the grid."""
        rs,page=self.spanning_table()
        rs=rs+cell('Measure E with a label run far',0,125)+cell('34±4',280,125)+cell('44±5',380,125)
        page=dict(elements=rs+[dict(kind='rule',box_px=[0,-4,430,-3]),dict(kind='rule',box_px=[0,37,430,38]),dict(kind='rule',box_px=[0,150,430,151])])
        rows,notes=c.table_rows(rs,10,page)
        self.assertIn(('TC7','columns_not_strips_plus_one'),doubts(rows))
        printed={w for r in texts(rows) for cell_ in r for w in cell_.split()}|{w for n in notes for w in n.split()}
        self.assertEqual(printed,{w for e in rs for w in e['text'].split()})

    def shaded_continuation(self,title_words):
        """a one-row table part under four shaded header cells (a fill edge between each two), with a title line
        read with it (AU03 Table 2 form)"""
        title='Evidence for the treatment of the root surface'
        rs=(words(title,0,-30) if title_words else cell(title,0,-30))
        rs+=cell('Reference',4,0)+cell('Study Description',260,0)+cell('Subjects',520,0)+cell('Defects',640,0)
        rs+=cell('Author et al. 1993',4,20)+cell('Two groups, surgical flap,',170,20)+cell('N = 6',480,20)+cell('Eighteen teeth,',600,20)
        rs+=cell('split mouth, six months',186,34)+cell('age 37 to 58',492,34)+cell('healthy, mirror',612,34)
        fills=[dict(kind='fill',box_px=b) for b in ([0,-6,160,14],[160,-6,470,14],[470,-6,590,14],[590,-6,760,14],[0,14,760,60])]
        return rs,dict(elements=rs+fills+[dict(kind='rule',box_px=[0,-8,760,-7]),dict(kind='rule',box_px=[0,60,760,61])]),title

    def test_tc1_tc3_one_row_part_under_shaded_header_keeps_its_columns(self):
        rs,page,title=self.shaded_continuation(False)
        rows,notes=c.table_rows(rs,10,page)
        t=[r for r in texts(rows) if title not in r]
        self.assertEqual(t[0],['Reference','Study Description','Subjects','Defects'])
        self.assertEqual(t[1][0],'Author et al. 1993')

    def test_tc7_one_cell_title_line_from_the_stub_is_not_spread(self):
        """the one cell of a line, reaching from the stub column over the next column, is a title: not repeated"""
        rs,page,title=self.shaded_continuation(True)
        rows,notes=c.table_rows(rs,10,page)
        self.assertLessEqual([cell_ for r in texts(rows) for cell_ in r].count(title),1)

    def test_memo1_h1_one_word_headers_set_close_stay_in_their_columns(self):
        """Memo 1, H1: one-word header cells, each ending on its column's right edge, set about one type size
        apart, in a font whose boxes are tall (line box near three times the type size); no cell holds two words.
        The word space comes from the type size, never from the white between two cells: each header stays whole
        in its own column."""
        tall=lambda text,x,y: [dict(id=f'{x:.0f}:{y}:{text}',kind='text',text=text,angle=0,line=y,box_px=[x,y,x+W*len(text),y+28],char_ids=[])]
        heads=['Ulna','Molars','Joint','Incisor','Canine']; edges=[160,210,250,300,345]
        rs=tall('Region',0,0)
        for w_,e in zip(heads,edges): rs+=tall(w_,e-W*len(w_),0)
        for i in range(6):
            y=34+30*i
            rs+=tall(['North','South','East','West','Coast','Hills'][i],0,y)
            for j,e in enumerate(edges): rs+=tall(f'{10+i+j}.{j}',e-24,y)
        rows,notes=c.table_rows(rs,10,dict(elements=rs))
        self.assertEqual(texts(rows)[0],['Region']+heads)

    def test_memo1_h2_tier_label_not_centred_over_a_span_keeps_the_cut(self):
        """Memo 1, H2: a label over a lower tier of labels, not centred over the columns it reaches, has no settled
        span: it is not spread over one column or several; the place is listed (TC7)."""
        rs,page=self.spanning_table()
        rs=[e for e in rs if e['text'] not in ('Control-Treatment','Group')]+words('Control-Treatment Group',262,0)
        rows,notes=c.table_rows(rs,10,dict(page,elements=[e for e in page['elements'] if e.get('kind')!='text']+rs))
        self.assertNotIn('Control-Treatment Group',[cell_ for r in texts(rows) for cell_ in r])
        self.assertIn(('TC7','tier_label_span_not_settled'),doubts(rows))

    def edge_set_table(self,align,body=26):
        """Memo 2: one-word header cells about 12.7 px apart, each set to the same edge of its own column's value
        cells (right, left or centre); the type size handed in (body, with no character sizes) is large enough
        that the white between cells counts as a word space, so the run of words reads as one header cell."""
        heads=['Guba','Samopa','Kaden','Lonana','Ermier']; vals_w=10
        rs=cell('Lotopa',0,0); x=110; col_spans=[]
        for w_ in heads:
            hw=W*len(w_); span=(x,x+max(hw,vals_w)); col_spans.append(span)
            hx={'right':span[1]-hw,'left':span[0],'centre':(span[0]+span[1]-hw)/2}[align]
            rs+=words(w_,hx,0); x=span[1]+12.7
        for i in range(4):
            y=24+20*i
            rs+=cell(['Nord','Sud','Ost','Rest'][i],0,y)
            for a,b in col_spans:
                vx={'right':b-vals_w,'left':a,'centre':(a+b-vals_w)/2}[align]
                rs+=[dict(id=f'{vx:.0f}:{y}',kind='text',text='%d.%d'%(1+i,i),angle=0,line=y,box_px=[vx,y,vx+vals_w,y+12],char_ids=[])]
        return rs,heads

    def test_memo2_header_cells_by_column_edges(self):
        for align in ('right','left','centre'):
            rs,heads=self.edge_set_table(align)
            rows,notes=c.table_rows(rs,26,dict(elements=rs))
            self.assertEqual(texts(rows)[0],['Lotopa']+heads,align)

    def test_header_cells_split_at_two_word_spaces(self):
        f=c.frame(0)
        rs=words('Mean SD',0,0,space=6)+words('Range',100,0)
        lines=c.table_lines(c.table_words(rs,None,f))
        cells=c.table_header_cells(lines[0]['items'],6)
        self.assertEqual([[t for b,t,e in cell] for cell in cells],[['Mean','SD'],['Range']])


if __name__ == '__main__':
    unittest.main()
