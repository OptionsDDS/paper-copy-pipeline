"""Multi-column OCR ordering, ownership, and furniture boundaries."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scan3',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(text,x,y,width=240,size=12):
    return dict(text=text,box_px=[x,y,x+width,y+size],size_px=size)


def numbered(rs):
    return [dict(r,_scan_id=i) for i,r in enumerate(rs)]


class ScanThreeColumns(unittest.TestCase):
    def test_two_gutters_split_each_source_run_without_losing_characters(self):
        chars=[];source=[]
        for y in range(100,220,20):
            row=[]
            for i,x in enumerate((30,330,630)):
                text=f'Column {i} has a continuous sentence with several words.'
                row.append(text)
                chars.append(dict(text=text,x0=x,x1=x+310,y0=y,y1=y+12,
                    origin=[x,y+10],adv_x1=x+240,size=12,space_after=True))
            source.append(run(' '.join(row),30,y,910))
        page=dict(page=1,region_box_px=[0,0,900,1200],elements=[],scan_evidence=dict(ocr_runs=source))
        reader=types.SimpleNamespace(sc_read_page=lambda *a:(chars,[],{}),sc_ocr_runs=lambda cs:source)
        with patch.dict(sys.modules,{'_copy_scan_reader':reader}):copy.scan_prepare_geometry([page],'test.pdf')
        self.assertEqual(len(page['_scan_geometry']['gutters']),2)
        self.assertEqual([r['text'] for r in copy.scan_source_runs(page)],[c['text'] for c in chars])
        self.assertEqual(page['_scan_geometry']['source_run_ids'],[i for i in range(6) for _ in range(3)])

    def test_partial_spanning_float_does_not_interrupt_independent_column(self):
        items=[dict(tag=t,box_px=b) for t,b in [('left-top',[20,20,270,35]),
            ('left-bottom',[20,200,270,215]),('middle-top',[320,20,570,35]),
            ('middle-bottom',[320,200,570,215]),('right-top',[620,20,870,35]),
            ('right-bottom',[620,200,870,215]),('two-column-table',[320,100,870,150])]]
        self.assertEqual([i['tag'] for i in copy.scan_order(items,[300,600])],
            ['left-top','left-bottom','middle-top','right-top','two-column-table','middle-bottom','right-bottom'])

    def test_numeric_age_column_is_not_a_vertical_margin_notice(self):
        rs=[run(str(i),30,100+20*i,20) for i in range(12,45)]
        p=dict(page=1,region_box_px=[0,0,900,1200],elements=[],scan_evidence=dict(ocr_runs=rs))
        self.assertEqual(copy.scan_furniture([p])[1],{})

    def test_repeated_top_figure_labels_do_not_become_running_heads(self):
        pages=[]
        for n in range(1,5):
            rs=[run(f'{300+n} Authors',20,20),run(f'Panel L{n}',630,50,100),
                run('The ordinary body sentence begins much further below.',20,300)]
            pages.append(dict(page=n,region_box_px=[0,0,900,1200],elements=[],scan_evidence=dict(ocr_runs=rs)))
        for dropped in copy.scan_furniture(pages).values():self.assertNotIn(1,dropped)

    def test_folio_title_beside_stacked_journal_head_is_furniture(self):
        pages=[]
        for n in range(1,5):
            rs=[run('Journal',650,20,160),run('Issue and month',650,36,160),
                run(f'{1200+n} A RECURRING ARTICLE TITLE',20,36,550),
                run('The ordinary body sentence starts after a clear gap.',20,85)]
            pages.append(dict(page=n,region_box_px=[0,0,900,1200],elements=[],scan_evidence=dict(ocr_runs=rs)))
        for dropped in copy.scan_furniture(pages).values():self.assertIn(2,dropped)

    def test_reference_hanging_indent_does_not_move_gutter_into_entry_labels(self):
        rs=[run('A continuous sentence with several ordinary printed words.',x,y,width)
            for x,width in [(20,260),(350,240)] for y in range(120,260,20)]
        rs += [run('27. A., B.; C., D.; E., F.; G., H.; I., J.',310,105,280)]
        gutter=copy.scan_gutters(rs,600)
        self.assertEqual(len(gutter),1)
        self.assertLess(gutter[0],310)

    def test_table_caption_fragments_follow_printed_rows_and_horizontal_positions(self):
        rs=numbered([run('Table 1. A caption',20,100,240),
            run('second phrase',90,116,120),run('First',20,117,60),
            run('Last',220,117,40),
            run('Heading',20,155,150),run('1.4',200,175,40)])
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(regions[0]['caption'],'Table 1. A caption First second phrase Last')

    def test_title_does_not_take_prose_in_other_column(self):
        rs=[run('A Printed Study Title',20,20,250,24),run('Second Title Line',20,55,250,24)]
        for x in (20,330):
            rs += [run('This continuous body sentence contains several ordinary words.',x,y,250) for y in range(120 if x==20 else 20,241,20)]
        p=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[p],dict(title=dict(box_px=[20,20,270,79])))).read_text()
        title=next(line for line in text.splitlines() if line.startswith('# '))
        self.assertEqual(title,'# A Printed Study Title Second Title Line')

    def test_sparse_chart_lettering_follows_continuing_paragraph_with_caption(self):
        rs=numbered([run('20',200,30,20),run('10',200,90,20),run('0',200,150,20),
            run('Figure 1. The measured response.',20,200,560),
            *[run('The continued body sentence contains several printed words.',x,y,250)
              for x in (20,330) for y in (240,260,280)]])
        figures,owned=copy.scan_figure_regions(rs,600,gutters=[300])
        owned=copy.scan_figure_lettering(figures,rs,600,[300])
        self.assertEqual(owned,{0,1,2,3})

    def test_sustained_columns_survive_overlapping_fragment_start_clusters(self):
        rs=[run('A continuous body sentence with several printed words.',x,y,250)
            for x in (20,330) for y in (100,120,140,160)]
        rs += [run('An indented fragment with several printed words.',100,y,230) for y in (200,220,240)]
        self.assertEqual(len(copy.scan_gutters(rs,600)),1)

    def test_wide_captions_sharing_left_edge_do_not_hide_narrow_columns(self):
        rs=[run('A continuous body sentence with several printed words.',x,y,240)
            for x in (30,330,630) for y in (500,520,540,560)]
        rs += [run('This longer caption line spans the first two columns of the page.',30,y,410)
               for y in range(100,400,20)]
        self.assertEqual(len(copy.scan_gutters(rs,900)),2)

    def test_two_column_table_beside_only_one_prose_column(self):
        rs=[run('Table 1. A printed table extending over two columns.',30,100,540)]
        rs += [run('Measured item',30,y,180) for y in range(140,400,20)]
        rs += [run('12.5',520,y,50) for y in range(140,400,20)]
        rs += [run('The separate prose column continues with several words.',630,y,240)
               for y in range(100,400,20)]
        rs=numbered(rs);gutters=copy.scan_gutters(rs,900)
        self.assertEqual(len(gutters),1)
        regions,owned=copy.scan_table_regions(rs,900,gutters)
        self.assertEqual(len(regions),1)
        self.assertTrue(all(r['box_px'][2]<600 for r in regions[0]['runs']))

    def test_caption_label_after_chart_word_starts_its_own_caption(self):
        rs=numbered([run('Chart label',20,100,150),
            run('Figure 3. A caption beside the chart.',330,100,250),
            run('Its second line belongs to the caption.',330,116,250)])
        figures,owned=copy.scan_figure_regions(rs,600)
        self.assertEqual(owned,{1,2})

    def test_table_column_above_neighboring_chart_keeps_table_ownership(self):
        rs=[run('Table 1. Measured values',20,100,500),
            run('Variable',20,130,150),run('Controls',420,130,80),
            *[run(str(i),420,y,40) for i,y in enumerate((160,180,200),1)],
            *[run('The continuous body sentence has several ordinary words.',20,y,240)
              for y in (260,280,300)],
            *[run(str(i),420,y,30) for i,y in enumerate((320,340,360),4)],
            run('Figure 1. A neighboring chart.',330,400,250),
            *[run('The following right column has several ordinary words.',330,y,250)
              for y in (450,470,490)]]
        page=dict(page=2,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            copy.copy_ocr_scan(folder,[page],{})
            import json
            audit=json.loads((Path(folder)/'copy.scan.json').read_text())['pages'][0]
        self.assertEqual([audit['destinations'][str(i)] for i in (3,4,5)],['table']*3)
        self.assertEqual([audit['destinations'][str(i)] for i in (9,10,11)],['figure']*3)

    def test_narrow_superscript_stays_on_its_overlapping_body_line(self):
        body=run('A continuous printed sentence with a raised citation.',20,100,500)
        body['box_px'][3]=120
        citation=run('19',150,94,15)
        citation['box_px'][3]=108
        rows=copy.scan_rows([body,citation])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]),2)

    def test_stacked_short_running_head_stays_outside_body(self):
        rs=[run('Journal volume',20,20,150),run('Number 4',20,36,100),
            run('Running title 302',330,36,250),
            *[run('The continuous body sentence has several ordinary words.',x,y,250)
              for x in (20,330) for y in (100,120,140)]]
        page=dict(page=2,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[page],{})).read_text()
        body,uncertain=text.split('## Places the program is not sure of')
        self.assertNotIn('Running title',body)
        self.assertIn('Running title',uncertain)

    def test_fragmented_keywords_and_acceptance_date_remain_together(self):
        rs=[run('Key words: roots;',330,100,120),run('geometry',460,100,100),
            run('Accepted for publication',330,120,150),run('10 May 1987',490,120,90),
            *[run('The body follows the abstract and its metadata band.',x,y,250)
              for x in (20,330) for y in (200,220,240)]]
        page=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[page],{})).read_text()
        self.assertIn('Key words: roots; geometry',text)
        self.assertIn('Accepted for publication 10 May 1987',text)
        self.assertLess(text.index('**Article information**'),text.index('geometry'))

    def test_remaining_labels_above_prose_use_existing_caption_witness(self):
        rs=numbered([run('Panel B',330,100,80),run('mm',420,250,30),
            *[run('The ordinary body sentence continues down the printed column.',x,y,250)
              for x in (20,330) for y in (400,414,428)]])
        caption=dict(box_px=[20,330,250,345])
        figures=copy.scan_top_graphic(rs,600,[300],[caption])
        self.assertEqual({r['_scan_id'] for r in figures[0]['runs']},{0,1})

    def test_table_restart_uses_prose_size_inside_its_own_columns(self):
        rs=[run('Table 1. A two-column table',30,100,540,10),
            *[run(str(i),x,y,30,10) for i,y in enumerate((140,160,180),1) for x in (30,500)],
            *[run('The smaller body text resumes below the printed table.',x,y,240,12)
              for x in (30,330) for y in (300,314,328)],
            *[run('The larger independent right column continues throughout.',630,y,240,16)
              for y in range(100,800,20)]]
        rs=numbered(rs)
        regions,owned=copy.scan_table_regions(rs,900,[300,600])
        self.assertLess(regions[0]['box_px'][3],300)
        self.assertTrue(all(r['box_px'][1]<300 for r in regions[0]['runs']))

    def test_axis_label_slightly_inside_gutter_stays_with_figure(self):
        rs=numbered([run('Scale',295,30,70),run('13',295,60,20),run('0',330,150,20),
            run('Figure 1. A chart.',330,200,240),
            *[run('The independent left column contains ordinary prose.',20,y,250)
              for y in (100,114,128)]])
        figures,owned=copy.scan_figure_regions(rs,600,gutters=[300])
        owned=copy.scan_figure_lettering(figures,rs,600,[300])
        self.assertEqual(owned,{0,1,2,3})

    def test_keyword_hyphen_continuation_is_metadata_even_when_prose_length(self):
        rs=[run('Key words: sample dis-',330,100,240),
            run('ease - loss of support - tooth loss.',330,114,240),
            *[run('The ordinary body sentence continues below the metadata.',x,y,250)
              for x in (20,330) for y in (240,254,268)]]
        page=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[page],{})).read_text()
        self.assertIn('Key words: sample dis-\nease - loss of support - tooth loss.',text)

    def test_two_bottom_axis_lines_after_large_blank_gap_join_caption(self):
        rs=numbered([*[run('The ordinary body sentence continues above the plot.',20,y,250)
                      for y in (100,114,128)],
            run('10 20 30 40 50',80,400,160),run('Age in years',100,416,120),
            run('Figure 1. A measured response.',20,440,250)])
        figures,owned=copy.scan_figure_regions(rs,600,gutters=[300])
        owned=copy.scan_figure_lettering(figures,rs,600,[300])
        self.assertEqual(owned,{3,4,5})

    def test_comma_caption_beside_two_column_table_stays_separate(self):
        rs=numbered([run('Table 1. A two-column measured table.',20,100,550),
            *[run(str(i),x,y,30) for i,y in enumerate((150,180,210),1) for x in (20,520)],
            run('Axis',650,120,70),run('10',650,180,30),run('0',650,240,30),
            run('Fig. 2, A neighboring chart caption.',630,280,250)])
        figures,figure_ids=copy.scan_figure_regions(rs,900,gutters=[300,600])
        self.assertEqual(len(figures),1)
        tables,owned=copy.scan_table_regions([r for r in rs if r['_scan_id'] not in figure_ids],900,[300,600],figures)
        self.assertTrue(all(r['box_px'][2]<600 for r in tables[0]['runs']))
        figure_ids=copy.scan_figure_lettering(figures,[r for r in rs if r['_scan_id'] not in owned],900,[300,600])
        self.assertEqual(figure_ids,{7,8,9,10})

    def test_narrow_gutter_after_paragraph_indent_uses_neighboring_edges(self):
        chars=[];source=[]
        for i,y in enumerate(range(100,260,30)):
            left='An indented paragraph continues with ordinary printed words.'
            right='The independent column has a separate continuous sentence.'
            x=52 if i==2 else 30;end=374 if i==2 else 350
            chars.extend([dict(text=left,x0=x,x1=390,y0=y,y1=y+20,origin=[x,y+18],adv_x1=end,size=20,space_after=True),
                          dict(text=right,x0=380,x1=710,y0=y,y1=y+20,origin=[380,y+18],adv_x1=710,size=20,space_after=True)])
            source.append(run(left+' '+right,x,y,710-x,20))
        page=dict(page=1,region_box_px=[0,0,1100,1400],elements=[],scan_evidence=dict(ocr_runs=source))
        reader=types.SimpleNamespace(sc_read_page=lambda *a:(chars,[],{}),sc_ocr_runs=lambda cs:source)
        with patch.dict(sys.modules,{'_copy_scan_reader':reader}):copy.scan_prepare_geometry([page],'test.pdf')
        self.assertEqual(len(copy.scan_source_runs(page)),12)

    def test_split_line_overhanging_gutter_does_not_pull_next_column_forward(self):
        rs=[run('The first left paragraph line.',52,100,322,20),
            run('Its following line stays in the left column.',30,124,320,20),
            run('The right column starts here.',381,90,320,20)]
        rs[0]['_scan_split_piece']=True
        items=[dict(kind='line',runs=[r],box_px=r['box_px']) for r in rs]
        self.assertEqual(copy.scan_order(items,[364]),items)

    def test_spanning_reference_heading_waits_for_last_prose_column(self):
        def item(text,x,y,width):
            r=run(text,x,y,width)
            return dict(kind='line',runs=[r],box_px=r['box_px'])
        tail=item('The translation ends in the right column.',630,200,240)
        heading=item('References',330,240,80)
        reference=item('An author and a long reference spanning two columns.',330,260,540)
        left=item('The first column ends here.',30,300,240)
        self.assertEqual(copy.scan_order([heading,reference,tail,left],[300,600]),
                         [left,tail,heading,reference])


if __name__=='__main__':unittest.main()
