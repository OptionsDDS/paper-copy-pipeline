"""Scan reading order (lane scanorder): row building with small runs (S1),
caption vetoes for table citations and bare labels (S2), and blocks printed
between the halves of a sentence (S3). Geometry only; no paper's text."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scanorder',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(text,x,y,w=240,size=12,h=None):
    return dict(text=text,box_px=[x,y,x+w,y+(size if h is None else h)],size_px=size)


def numbered(rs):
    return [dict(r,_scan_id=i) for i,r in enumerate(rs)]


def texts(rows):
    return [copy.scan_line(row) for row in rows]


class RowBuilding(unittest.TestCase):
    """S1: body-height runs first; small runs attach by band; centre order."""

    def column(self):
        # AN04 page-1 geometry (150 dpi): 23.5 px type, 28.8 px line boxes,
        # a 7.8 px superscript between two pieces of its own line, and the
        # neighbouring column's line 7.6 px lower than the line above.
        return [run('plasma values, cell counts, and the first di-',618,1282.0,450,23.5,28.8),
                run('4',797.8,1307.9,6.3,12.6,7.8),
                run('visions of the data,3',617.9,1308.2,173,23.4,21.0),
                run('all of which are also at-',815.9,1306.5,252.5,23.5,17.4),
                run('tributed to the same cause with the',617.3,1331.7,452,23.8,26.5),
                run('these readings at present and clearly more',91,1291,450,24.6,26),
                run('research is needed on both of these processes',92,1315,449,25.8,25)]

    def test_torn_superscript_stays_on_its_own_line(self):
        # The copier builds rows per column; the page-wide rows must agree.
        rows=texts(copy.scan_rows(self.column()[:5]))
        self.assertIn('plasma values, cell counts, and the first di-',rows)
        self.assertIn('visions of the data,3 4 all of which are also at-',rows)
        page=texts(copy.scan_rows(self.column()))
        self.assertTrue(any(t.endswith('visions of the data,3 4 all of which are also at-') for t in page))
        self.assertTrue(any(t.endswith('the first di-') for t in page))

    def test_lines_print_in_centre_order(self):
        rows=copy.scan_rows(self.column())
        centres=[sum((r['box_px'][1]+r['box_px'][3])/2 for r in row)/len(row) for row in rows]
        self.assertEqual(centres,sorted(centres))

    def test_small_run_never_seeds_a_row_or_moves_its_centre(self):
        a=run('a continuous line of body text here',20,100,400,20,24)
        b=run('another continuous line of body text',20,126,400,20,24)
        mark=run('*',150,96,6,10,8)
        rows=copy.scan_rows([mark,a,b])
        self.assertEqual(len(rows),2)
        self.assertEqual([len(row) for row in rows],[2,1])
        self.assertIs(rows[0][0],a)

    def test_two_line_stub_cell_is_not_small(self):
        # AN09 page 3, the table column alone (the copier builds rows per
        # column): a stub "1-3" over "mm", ink 0.59 of the 19 px type.
        stub=run('1-3',477,502,19,18,12)
        cells=run('mm 87 75 22.2 5 1.5',472,521,646,19,16)
        total=run('total 338 217 54 42',472,545,586,19,16)
        rows=texts(copy.scan_rows([stub,cells,total]))
        self.assertEqual(rows,['1-3','mm 87 75 22.2 5 1.5','total 338 217 54 42'])

    def test_raised_citation_of_its_own_type_still_joins(self):
        body=run('A continuous printed sentence with a raised citation.',20,100,500,12,20)
        citation=run('19',150,94,15,12,14)
        self.assertEqual(len(copy.scan_rows([body,citation])),1)


class CaptionVetoes(unittest.TestCase):
    """S2: a table citation opening a paragraph is body; a bare label needs its table."""

    def test_caption_shape(self):
        shaped=['Table 2. Counts by group','TABLE 3','Table 4: Values','Table 2 (continued)',
                'Table I. % of the sites','Table 2—The counts','Table 5, Counts']
        prose=['Table 2 covers the counts for','Table 4 relates to','Table 3 (see the figure) covers']
        for t in shaped:self.assertTrue(copy.scan_caption_shaped(t),t)
        for t in prose:self.assertFalse(copy.scan_caption_shaped(t),t)

    def layout(self,citation):
        # AN09 page 3: a two-column scan, the right column a numeric table
        # under its caption, the left column prose with an indented
        # paragraph start that cites a table.
        left=[run('the pocket depth values and the scores',107,700+i*24,330,20.4,18) for i in range(3)]
        left.append(run(citation,130,772,311,20.4,18))
        left+=[run('for the three groups analysed. Results show the',107,796+i*24,333,20.4,18) for i in range(6)]
        right=[run('Table 2. Counts and shares of the sites in the groups',470,690,690,17.1,16),
               run('Site',471,719,60,17,15),run('Share',700,719,70,17,15),
               *[run(v,x,749+i*22,50,17,14) for i in range(4) for v,x in ((str(10+i),471),(str(20+i)+'%',600),(str(30+i),760),(str(40+i)+'%',900))]]
        return numbered(left+right)

    def test_table_citation_opening_a_paragraph_is_body(self):
        rs=self.layout('Table 3 covers the counts of sites')
        regions,owned=copy.scan_table_regions(rs,1213,[454])
        self.assertEqual(len(regions),1)
        self.assertNotIn(3,owned)
        self.assertTrue(regions[0]['caption'].startswith('Table 2.'))

    def test_shaped_caption_in_the_same_place_is_still_a_caption(self):
        rs=self.layout('Table 3. Counts of sites')
        regions,owned=copy.scan_table_regions(rs,1213,[454])
        self.assertEqual(len(regions),2)

    def test_bare_label_ending_a_sentence_is_body(self):
        # "... are shown in" / "Table 1." at the column's left edge, then a
        # new paragraph; the right column holds a real table.
        rs=self.layout('x')
        rs=[r for r in rs if r['text']!='x']
        rs[3]=dict(run('Table 1.',108,772,68,20.4,14),_scan_id=3)
        regions,owned=copy.scan_table_regions(rs,1213,[454])
        self.assertEqual(len(regions),1)
        self.assertNotIn(3,owned)

    def test_bare_label_with_cells_in_reach_is_a_caption(self):
        rs=numbered([run('TABLE 2',20,100,70,12),
            run('Group',20,130,60,12),run('Value',200,130,60,12),
            *[run(str(i),x,160+i*30,30,12) for i in range(3) for x in (20,200)]])
        regions,owned=copy.scan_table_regions(rs,600,[])
        self.assertEqual(len(regions),1)
        self.assertIn(0,owned)

    def test_bare_label_with_a_title_in_reach_is_a_caption(self):
        rs=numbered([run('TABLE 1',20,20,100,12),run('Measured and reported readings',20,60,300,12),
                     run('Other article content.',20,200,300,12)])
        regions,owned=copy.scan_table_regions(rs,600,[])
        self.assertEqual(len(regions),1)

    def test_bare_figure_label_under_an_unfinished_line_is_the_sentence_tail(self):
        # AM05 page 8: "is shown in" / "Fig. 7E." at line pitch, then an
        # indented paragraph; the label's OCR size is 0.85 of the body's.
        rs=numbered([run('the position of the margin stayed stable while',105,1408,503,18.2,15),
            run('the margin followed the movement of the tooth',105,1432,503,18.2,15),
            run('of the tooth. The later radiograph is shown in',105,1457,503,18.2,15),
            run('Fig. 7E.',106,1481,72,15.5,15),
            run('Surgery consisted of a full thickness flap which',128,1507,481,18.2,15),
            run('revealed that the osseous crest followed the',105,1531,503,18.2,15)])
        regions,owned=copy.scan_figure_regions(rs,1275,gutters=[633])
        self.assertEqual(regions,[])
        rs[2]['text']='of the tooth. The later radiograph is shown.'
        rs[3]['box_px'][1]+=30;rs[3]['box_px'][3]+=30
        regions,owned=copy.scan_figure_regions(rs,1275,gutters=[633])
        self.assertEqual(len(regions),1)


class InsertedBlocks(unittest.TestCase):
    """S3: letter-spaced labels are labels; a block between sentence halves leaves it."""

    def test_letter_spaced_label_reads_as_a_label(self):
        self.assertEqual(copy.scan_label_text('F I G U R E 7F. The flap'),'FIGURE 7F. The flap')
        self.assertEqual(copy.scan_label_text('T A B L E 2'),'TABLE 2')
        self.assertEqual(copy.scan_label_text('F I G . 3'),'FIG. 3')
        for same in ('Figure 7','FIG. 3. A chart','Fig ures of merit','F I G U R E S of the past'):
            self.assertEqual(copy.scan_label_text(same),same)
        self.assertEqual(copy.float_label(copy.scan_label_text('F I G U R E 7F. The flap'))['id'],'Figure 7')

    def test_letter_spaced_caption_is_a_figure_block(self):
        # AM05 page 12: a five-line caption at the column head under the
        # picture, 2 em above the sentence that continues from the last page.
        rs=numbered([run('F I G U R E 7F. The elevated flap showing the altered bone',112,1142,499,18,15),
            run('crests. The coronal shift of the facial and interproximal bone is',111,1163,500,18,15),
            run('clearly visible. G . Healing after surgery. H . The provi-',111,1184,500,18,15),
            run('sional restoration.',110,1205,147,18,15),
            run('normal function or parafunctional habits by reducing',110,1277,501,18,15),
            run('heavy contacts in maximum intercuspation and excur-',109,1302,502,18,15),
            run('sions.',109,1327,48,17.9,15)])
        regions,owned=copy.scan_figure_regions(rs,1275,gutters=[633])
        self.assertEqual(len(regions),1)
        self.assertEqual(sorted(owned),[0,1,2,3])

    def stream(self,first,after,gap=37,after_page=12,above=None):
        # Page 11 ends mid-sentence; page 12's left column opens with a
        # three-line block at line pitch (25 px), then a gap, then the line
        # that continues the sentence. ABOVE puts a line 563 px over the block.
        def line(text,x,y,w,page):
            return dict(kind='line',runs=[run(text,x,y,w,18,15)],box_px=[x,y,x+w,y+15],page=page)
        items=[line('should minimise the influence of trauma associated '+('with' if first else 'with.'),657,828,500,11)]
        if above:items.append(line(above,112,1142-563,500,12))
        y=1142
        for text in ('Tooth preparation at the level of the crest: the','diameter of the preparation is proportionate to the','fixed amount of space. This relationship is constant.'):
            items.append(line(text,112,y,499,12));y+=25
        items.append(line(after,110,y-10+gap,501,after_page))
        items.append(line('heavy contacts in maximum intercuspation and excur-',109,y+15+gap,502,after_page))
        return items

    def test_block_between_sentence_halves_is_printed_after_the_paragraph(self):
        items=self.stream(True,'normal function or parafunctional habits by reducing')
        out=copy.scan_inserted_blocks(items)
        self.assertEqual([it['kind'] for it in out],['line','side','line','line'])
        self.assertEqual(len(out[1]['runs']),3)
        arranged=copy.scan_arrange_floats(out)
        self.assertEqual([it['kind'] for it in arranged],['line','line','line','side'])

    def test_block_at_a_column_foot_under_a_blank_leaves_the_sentence(self):
        # AM05 page 12, right column: the sentence stops at y 843, the
        # picture follows, the caption block stands at y 1406, and the
        # sentence goes on at the head of page 14.
        items=self.stream(True,'lining. This tissue remains red for a long time',after_page=14,
                          above='in this case may be due to an inversion of the pocket')
        del items[0]
        out=copy.scan_inserted_blocks(items)
        self.assertEqual([it['kind'] for it in out],['line','side','line','line'])

    def test_a_continuing_or_new_paragraph_is_not_a_block(self):
        lower=self.stream(True,'normal function or parafunctional habits by reducing')
        lower[1]['runs'][0]['text']='tooth preparation at the level of the crest: the'
        self.assertTrue(all(it['kind']=='line' for it in copy.scan_inserted_blocks(lower)))
        finished=self.stream(False,'normal function or parafunctional habits by reducing')
        self.assertTrue(all(it['kind']=='line' for it in copy.scan_inserted_blocks(finished)))
        capital=self.stream(True,'Normal function or parafunctional habits by reducing')
        self.assertTrue(all(it['kind']=='line' for it in copy.scan_inserted_blocks(capital)))
        tight=self.stream(True,'normal function or parafunctional habits by reducing',gap=10)
        self.assertTrue(all(it['kind']=='line' for it in copy.scan_inserted_blocks(tight)))

    def test_sentence_goes_on_across_a_column_change_without_a_break(self):
        # AN09 page 4: the first half ends a column, the second starts the
        # next; AM05 page 8: a bare label in a smaller OCR type 9.5 px under
        # its line. Neither gets a paragraph break; a finished line does.
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        rs=[run('free of calculus for each group at the given',20,1276,300,20,18),
            run('the given levels of probing depths. The second chart',20,1300,300,20,18),
            run('demonstrates the share of total surfaces for',20,1324,300,20,18),
            run('each experimental group according to',360,100,300,20,18),
            run('the level of remaining calculus. The next',360,124,300,20,18),
            run('sentence is shown in',360,148,200,18.2,15),
            run('Fig. 3E.',360,172.5,72,15.5,15),
            run('Later work consisted of a full thickness flap',382,198,280,18.2,15)]
        page=dict(page=1,region_box_px=[0,0,700,1400],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            copy.copy_ocr_scan(folder,[page],{})
            text=(Path(folder)/'copy.md').read_text()
        self.assertIn('demonstrates the share of total surfaces for\neach experimental group',text)
        self.assertIn('sentence is shown in\nFig. 3E.\n\nLater work',text)

    def test_reference_column_is_not_a_block(self):
        def line(text,y,page,x=112):
            return dict(kind='line',runs=[run(text,x,y,480,18,15)],box_px=[x,y,x+480,y+15],page=page)
        items=[line('9. Author, A. B.: A study of the tissue during movement',1500,5)]
        items+=[line(t,100+i*22,6) for i,t in enumerate(('10. Author, C.: A method of treating the one and two wall',
            'defects. J Dent 45: 100, 1970.','11. Author, D., and Author, E.: Tissue changes resulting',
            'from tipping and extrusion. J Dent 46: 200, 1974.'))]
        items.append(line('cisors in monkeys. J Dent 45: 660, 1974.',100,7))
        self.assertTrue(all(it['kind']=='line' for it in copy.scan_inserted_blocks(items)))



class SentenceWitness(unittest.TestCase):
    """Output rule: a lower-case start joins the line before it only when the
    page shows the two lines as one sentence (invented text, geometry only)."""

    @staticmethod
    def line(text,x,y,w=300,size=20,h=18):
        r=run(text,x,y,w,size,h)
        return dict(kind='line',runs=[r],box_px=list(r['box_px']),page=1)

    def column1(self,last='and the crews counted the nets by'):
        return [self.line(t,20,100+24*i) for i,t in enumerate((
            'The nets were hung from the old posts along the',
            'harbour wall and each crew counted the fish that',
            'came up in them before the tide turned, and the',last))]

    def witness(self,prev,it,stream):
        why=[]
        ok=copy.scan_sentence_witness(prev,it,copy.scan_page_text(stream)[1],why)
        return ok,why

    def test_column_foot_to_column_head_is_one_sentence(self):
        c1=self.column1();head=self.line('both teams on the same evening at the',360,100)
        below=self.line('quay, where the counts were read aloud.',360,124)
        ok,why=self.witness(c1[-1],head,c1+[head,below])
        self.assertTrue(ok,why)

    def test_spanning_band_above_the_column_heads_does_not_stand_in_a_column(self):
        band=self.line('A summary of the whole survey set across both columns of the page here',20,40,640)
        c1=self.column1();head=self.line('both teams on the same evening at the',360,100)
        self.assertTrue(self.witness(c1[-1],head,[band]+c1+[head])[0])

    def test_number_row_at_the_column_foot_is_not_a_sentence(self):
        c1=self.column1('The second evening count was made when it')
        row=self.line('Net 12.4 8.1 0.33 14.0 9.2',20,200,240)
        head=self.line('lifted early because of the wind from the',360,100)
        ok,why=self.witness(row,head,c1+[row,head])
        self.assertFalse(ok);self.assertEqual(why,['letters'])

    def test_capital_label_in_a_smaller_type_is_not_a_sentence(self):
        c1=self.column1('On the third morning the crews moved the')
        label=self.line('DISTANCE',140,330,60,15,13)
        body=self.line('wall, where the water was deeper and the',20,346)
        self.assertFalse(self.witness(label,body,c1+[label,body])[0])

    def test_body_prose_above_the_other_line_is_a_misorder(self):
        c1=self.column1()
        top=[self.line(t,360,100+24*i) for i,t in enumerate((
            'Each post was given a short painted code, and',
            'the codes were written on cards that the crews'))]
        mid=self.line('kept dry in a tin box through the season.',360,700)
        ok,why=self.witness(c1[-1],mid,c1+top+[mid])
        self.assertFalse(ok);self.assertTrue(why[0].startswith('prose above it'))

    def test_body_prose_below_prev_in_its_column_is_a_misorder(self):
        c1=self.column1()
        more=self.line('Small boats came in from the outer banks through',20,220)
        head=self.line('both teams on the same evening at the',360,100)
        self.assertFalse(self.witness(c1[-1],head,c1+[more,head])[0])

    def test_text_tied_above_the_column_head_is_its_line(self):
        c1=self.column1()
        front=dict(kind='front',runs=[run('a situation that was long sought by the',360,76,300,20,18)],page=1,
                   box_px=[360,76,660,94])
        head=self.line('both teams on the same evening at the',360,100)
        ok,why=self.witness(c1[-1],head,c1+[front,head])
        self.assertFalse(ok);self.assertTrue(why[0].startswith('piece tied above it'))

    def test_block_set_apart_under_which_the_column_goes_on_in_lower_case(self):
        c1=self.column1()
        tail=[self.line('of the larger nets compared with the small',360,700),
              self.line('ones. Grey bars show the evening counts.',360,724)]
        rest=self.line('both teams on the same evening at the',360,800)
        ok,why=self.witness(c1[-1],tail[0],c1+tail+[rest])
        self.assertFalse(ok);self.assertTrue(why[0].startswith('it is a block set apart'))
        self.assertTrue(self.witness(c1[-1],rest,c1+[rest])[0])

    def test_gap_in_one_column(self):
        c1=self.column1()
        # a float printed after the paragraph left the gap: one sentence
        fig=dict(kind='figure',runs=[run('Figure 2. Nets',20,220,200,16,14)],box_px=[20,200,320,300],page=1)
        after=self.line('both teams on the same evening at the',20,330)
        self.assertTrue(self.witness(c1[-1],after,c1+[fig,after])[0])
        # a raster panel without OCR text: a blank of 3 em or more
        self.assertTrue(self.witness(c1[-1],after,c1+[after])[0])
        # a blank of under 3 em with nothing in it: a printed space, no sentence
        near=self.line('both teams on the same evening at the',20,220)
        ok,why=self.witness(c1[-1],near,c1+[near])
        self.assertFalse(ok);self.assertEqual(why,['blank without a float'])
        # body prose between the two lines in the column
        mid=self.line('Small boats came in from the outer banks through',20,260)
        self.assertFalse(self.witness(c1[-1],after,c1+[mid,after])[0])

    def upper_band(self):
        """Two columns of list items over a centred heading that reaches over
        the gutter; a lower band of two columns starts under it."""
        left=[self.line(t,20,100+24*i) for i,t in enumerate((
            'Each post was given a short painted code, and',
            'the codes were written on cards that the crews'))]
        right=[self.line(t,360,100+24*i) for i,t in enumerate((
            'kept dry in a tin box through the long season,',
            'and the cards were read out at the end of it.'))]
        return left+right

    def test_heading_over_the_gutter_bounds_the_band_above_both_lines(self):
        band=self.upper_band()
        heading=self.line('Notes',290,200,100,30,26)
        c1=[self.line(t,20,260+24*i) for i,t in enumerate((
            'The nets were hung from the old posts along the',
            'harbour wall and each crew counted the fish by'))]
        head=self.line('both teams on the same evening at the',360,260)
        ok,why=self.witness(c1[-1],head,band+[heading]+c1+[head])
        self.assertTrue(ok,why)
        # without the heading the column above IT is read before it
        ok,why=self.witness(c1[-1],head,band+c1+[head])
        self.assertFalse(ok);self.assertTrue(why[0].startswith('prose above it'))

    def test_piece_inside_one_column_or_below_prev_is_no_band_bound(self):
        band=self.upper_band()
        c1=[self.line(t,20,260+24*i) for i,t in enumerate((
            'The nets were hung from the old posts along the',
            'harbour wall and each crew counted the fish by'))]
        head=self.line('both teams on the same evening at the',360,260)
        # a heading inside IT's column only does not reach over the gutter
        inside=self.line('Notes',420,200,100,30,26)
        self.assertFalse(self.witness(c1[-1],head,band+[inside]+c1+[head])[0])
        # a piece over the gutter below PREV's top does not bound PREV's band
        low=self.line('Notes',290,262,100,30,26)
        self.assertFalse(self.witness(c1[-1],head,band+[low]+c1+[head])[0])

    def test_line_over_the_gutter_at_line_pitch_inside_the_column_is_no_band_bound(self):
        c1=[self.line(t,20,100+24*i) for i,t in enumerate((
            'The nets were hung from the old posts along the',
            'harbour wall and each crew counted the fish that',
            'came up in them before the tide turned, and the'))]
        c1+=[self.line(t,20,196+24*i) for i,t in enumerate((
            'second evening count was made when the crews',
            'had hung the spare nets and counted the fish by'))]
        right=[self.line(t,360,100+24*i) for i,t in enumerate((
            'kept dry in a tin box through the long season,',
            'and the cards were read out at the end of it.',
            'Each post was given a short painted code, and'))]
        # two columns' lines read as one, one pitch under column 2's last line
        merged=self.line('the codes were written on cards that the crews and the',20,172,640)
        head=self.line('both teams on the same evening at the',360,196)
        ok,why=self.witness(c1[-1],head,c1+right+[merged,head])
        self.assertFalse(ok);self.assertTrue(why[0].startswith('prose above it'))
        # the same piece set apart (column 2 ends two pitches above it) bounds the band
        ok,why=self.witness(c1[-1],head,c1+right[:2]+[merged,head])
        self.assertTrue(ok,why)

    def test_one_word_line_does_not_wrap_a_sentence(self):
        c1=self.column1()
        label=self.line('Sources',20,200,90)
        head=self.line('both teams on the same evening at the',360,100)
        ok,why=self.witness(label,head,c1+[label,head])
        self.assertFalse(ok);self.assertEqual(why,['one word'])

    def test_number_row_keeps_its_paragraph_break_in_the_copy(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        rs=[run('The nets were hung from the old posts along the',20,100,300,20,18),
            run('harbour wall and each crew counted the fish that',20,124,300,20,18),
            run('came up in them before the tide turned, and the',20,148,300,20,18),
            run('second evening count was made when the nets were',20,172,300,20,18),
            run('Net 12.4 8.1 0.33 14.0 9.2',20,198,240,20,18),
            run('lifted early because of the wind from the north.',360,100,300,20,18),
            run('Small boats came in from the outer banks through',360,124,300,20,18),
            run('the morning, and the crews kept to the same posts',360,148,300,20,18),
            run('for every count so that the numbers could be set',360,172,300,20,18)]
        page=dict(page=1,region_box_px=[0,0,700,1400],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            copy.copy_ocr_scan(folder,[page],{})
            text=(Path(folder)/'copy.md').read_text()
        self.assertIn('Net 12.4 8.1 0.33 14.0 9.2\n\nlifted early',text)

if __name__=='__main__':
    unittest.main()
