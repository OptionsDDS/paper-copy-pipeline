"""Scan column boundaries must conserve characters and separate printed regions."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scancols',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(text,x,y,width=250,size=12):
    return dict(text=text,box_px=[x,y,x+width,y+size],size_px=size,baseline=y+size)


def glyph(text,x,y,end,angle=0):
    # An OCR fallback font has much wider glyph hulls than its advances.
    return dict(text=text,x0=x,y0=y,x1=end+70,y1=y+12,origin=[x,y+10],
                size=12,adv_x1=end,space_after=True,angle=angle)


def fixture():
    chars=[];runs=[]
    for i in range(6):
        left=f'Left column sentence with several printed words {i}.'
        right=f'Right column sentence with several printed words {i}.'
        y=120+20*i
        chars.extend([glyph(left,20,y,270),glyph(right,330,y+2,580)])
        runs.append(run(left+' '+right,20,y,630,14))
        runs[-1]['baseline']=y+10
    return chars,runs


class ScanColumns(unittest.TestCase):
    def prepare(self,chars,runs):
        p=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=runs))
        reader=types.SimpleNamespace(sc_read_page=lambda *args:(chars,[],{}),sc_ocr_runs=lambda cs:runs)
        with patch.dict(sys.modules,{'_copy_scan_reader':reader}):
            copy.scan_prepare_geometry([p],'verified-test.pdf')
        return p

    def test_oversized_hulls_split_using_advances_and_keep_source_ownership(self):
        chars,runs=fixture();p=self.prepare(chars,runs)
        result=copy.scan_source_runs(p)
        self.assertEqual(len(result),12)
        self.assertEqual([r['text'] for r in result], [c['text'] for c in chars])
        self.assertEqual(p['_scan_geometry']['source_run_ids'],[i for i in range(6) for _ in range(2)])
        self.assertTrue(270<p['_scan_geometry']['gutter']<330)
        for i in range(0,12,2):
            self.assertLess(result[i]['box_px'][2],result[i+1]['box_px'][0])

    def test_full_width_caption_with_letters_in_gutter_stays_whole(self):
        chars,runs=fixture()
        cap='FIGURE 1. A caption spans the entire page and stays together.'
        chars.append(glyph(cap,20,290,580));runs.append(run(cap,20,290,630))
        p=self.prepare(chars,runs)
        result=copy.scan_source_runs(p)
        self.assertEqual(result[-1]['text'],cap)
        self.assertEqual(len(result),13)
        self.assertGreater(result[-1]['box_px'][2],p['_scan_geometry']['gutter'])

    def test_rotated_letters_inside_caption_are_recorded_furniture(self):
        chars,runs=fixture()
        cap='FIGURE 2. The caption ends in a word'
        chars.extend([glyph(cap,20,290,580),glyph('xy',585,290,590,90)])
        runs.append(run(cap+' xy',20,290,640))
        p=self.prepare(chars,runs)
        result=copy.scan_source_runs(p)
        self.assertEqual(result[-2]['text'],cap)
        self.assertEqual(result[-1]['text'],'xy')
        self.assertIn(result[-1]['_scan_id'],copy.scan_furniture([p])[1])
        self.assertNotIn(result[-2]['_scan_id'],copy.scan_furniture([p])[1])

    def test_mismatching_pdf_cannot_change_saved_text(self):
        chars,runs=fixture();p=dict(page=1,region_box_px=[0,0,600,800],elements=[],
                                  scan_evidence=dict(ocr_runs=runs))
        reader=types.SimpleNamespace(sc_read_page=lambda *args:(chars,[],{}),sc_ocr_runs=lambda cs:[])
        with patch.dict(sys.modules,{'_copy_scan_reader':reader}):copy.scan_prepare_geometry([p],'wrong.pdf')
        self.assertNotIn('_scan_runs',p)

    def test_tall_title_does_not_merge_successive_neighboring_lines(self):
        rs=[run('Tall title',20,100,230,32),run('First right line',330,100),
            run('Second right line',330,120),run('Third right line',330,140)]
        rs=[dict(r,_scan_exact_geometry=True) for r in rs]
        rows=copy.scan_rows(rs)
        self.assertEqual(len(rows),3)
        self.assertFalse(any('First right line' in copy.scan_line(row) and 'Second right line' in copy.scan_line(row) for row in rows))

    def test_already_separated_scan_keeps_its_original_line_boxes(self):
        chars,runs=fixture()
        # Separate baselines leave the source columns intact even though the
        # fallback glyph boxes still overestimate each line's right edge.
        for i,c in enumerate(chars):
            c['y0']=100+20*i;c['y1']=c['y0']+12;c['origin'][1]=c['y0']+10
        runs=[run(c['text'],c['x0'],c['y0'],c['x1']-c['x0']) for c in chars]
        p=self.prepare(chars,runs)
        self.assertNotIn('_scan_runs',p)
        self.assertEqual([r['box_px'] for r in copy.scan_source_runs(p)],[r['box_px'] for r in runs])

    def test_companion_reference_page_uses_verified_geometry_after_a_split(self):
        first_chars,first_runs=fixture()
        chars=[glyph('A complete bibliographic line with several words.',20,100,270),
               glyph('The next printed line follows beneath it.',20,120,270)]
        runs=[run(c['text'],c['x0'],c['y0'],c['x1']-c['x0']) for c in chars]
        pages=[dict(page=n,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
               for n,rs in [(1,first_runs),(2,runs)]]
        reader=types.SimpleNamespace(sc_read_page=lambda pdf,n:([first_chars,chars][n-1],[],{}),
                                    sc_ocr_runs=lambda cs:first_runs if cs is first_chars else runs)
        with patch.dict(sys.modules,{'_copy_scan_reader':reader}):copy.scan_prepare_geometry(pages,'verified-test.pdf')
        self.assertEqual(pages[1]['_scan_geometry']['splits'],[])
        self.assertTrue(all(r['_scan_exact_geometry'] for r in copy.scan_source_runs(pages[1])))
        self.assertEqual(len(copy.scan_rows(copy.scan_source_runs(pages[1]))),2)

    def test_full_width_band_interrupts_columns_at_its_height(self):
        items=[dict(box_px=b,tag=t) for t,b in [('left top',[20,50,270,65]),
          ('left bottom',[20,200,270,215]),('right top',[330,50,580,65]),
          ('right bottom',[330,200,580,215]),('title',[180,100,420,125])]]
        self.assertEqual([r['tag'] for r in copy.scan_order(items,300)],
                         ['left top','right top','title','left bottom','right bottom'])

    def test_unpunctuated_figure_label_and_continuation_remain_atomic(self):
        rs=[run('Fig 1 A printed caption starts here',20,100,560),
            run('and continues on its second line.',20,116,560),
            run('Larger body text begins here.',20,145,260,16)]
        rs=[dict(r,_scan_id=i) for i,r in enumerate(rs)]
        regions,owned=copy.scan_figure_regions(rs,600)
        self.assertEqual(owned,{0,1})
        self.assertEqual(len(regions),1)

    def test_wrapped_panel_reference_is_not_a_new_caption(self):
        rs=[run('The areas circled above are shown at greater magnification in',20,100,560),
            run('Fig. 4a and 4b, with the same structures marked.',20,116,560),
            run('The labels identify the newly formed tissue.',20,132,560)]
        rs=[dict(r,_scan_id=i) for i,r in enumerate(rs)]
        regions,owned=copy.scan_figure_regions(rs,600)
        self.assertEqual(regions,[])
        self.assertEqual(owned,set())

    def test_narrative_figure_reference_remains_body_prose(self):
        rs=[run('Figure 2b shows the result of the experiment.',20,100,260),
            run('Further observations confirm the result.',20,116,260)]
        rs=[dict(r,_scan_id=i) for i,r in enumerate(rs)]
        regions,owned=copy.scan_figure_regions(rs,600)
        self.assertEqual(regions,[])
        self.assertEqual(owned,set())

    def test_each_reference_gets_a_paragraph(self):
        rs=[run(f'{n}. Author, A.: A printed bibliographic entry.',20,100+20*n,500) for n in range(1,4)]
        p=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            with patch.object(copy,'table_pdf_path',return_value=None):
                text=Path(copy.copy_ocr_scan(temp,[p],{})).read_text()
        for n in range(1,4):self.assertIn(f'\n\n{n}. Author',text)


if __name__=='__main__':unittest.main()
