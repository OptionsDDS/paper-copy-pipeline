"""Scan furniture, reference ownership and atomic float placement."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_scanmargin', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


def run(text, x, y, width=100, size=12):
    return dict(text=text, box_px=[x,y,x+width,y+size], size_px=size)


def numbered(runs):
    return [dict(r,_scan_id=i) for i,r in enumerate(runs)]


class ScanMargin(unittest.TestCase):
    def test_rotated_word_is_accounted_for_by_excluded_glyph_strip(self):
        spec=importlib.util.spec_from_file_location('scan_conserve',ROOT/'tools/conserve.py')
        conserve=importlib.util.module_from_spec(spec);spec.loader.exec_module(conserve)
        furniture=[dict(source_run_id=i,text=ch,box_px=[585,20+5*i,595,25+5*i],
                        why='one-glyph-wide text strip in the outer page margin') for i,ch in enumerate('Publisher')]
        excluded=copy.scan_exclusion_evidence(furniture)
        self.assertIsNotNone(conserve.covered(dict(text='Publisher',box=[585,20,595,65]),excluded,1,1))
        self.assertIsNone(conserve.covered(dict(text='Body',box=[540,20,570,65]),excluded,1,1))

    def test_vertical_fragments_and_rotated_strip_leave_body_alone(self):
        rs=[run('a',585,y,8,10) for y in range(25,700,15)]
        rs += [run('Rotated publisher text',4,50,10,10)]
        rs[-1]['box_px'][3]=600
        rs += [run('7',530,y,8,10) for y in range(100,500,30)]
        rs += [run('This is the first ordinary body sentence.',40,100,450)]
        p=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        excluded=copy.scan_furniture([p])[1]
        self.assertEqual(set(excluded),set(range(46)))

    def test_stacked_heads_with_small_ocr_differences(self):
        pages=[]
        for n,name in enumerate(('Alpha','Alpba','Alpha','Alpha'),1):
            rs=[run(f'{100+n} {name}, Beta, Gamma, Delta, Epsilon',20,20,250),
                run('Journal of Observations',450,15,130,10),run('July, 1964',500,27,80,10)]
            for x in (20,330):
                rs += [run('A continuous ordinary body line with several words.',x,y,250) for y in range(70,230,20)]
            pages.append(dict(page=n,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs)))
        for ids in copy.scan_furniture(pages).values():self.assertEqual(set(ids),{0,1,2})

    def test_roman_caption_owns_headers_and_distant_total(self):
        rs=[run('TABLE XIV. Measurements at follow-up',20,30,500),
            run('Group',20,60),run('Mean',200,60),run('SD',350,60)]
        for y,label in [(90,'First'),(120,'Second'),(150,'Third'),(220,'TOTAL')]:
            rs += [run(label,20,y),run('12',200,y,30),run('0.3',350,y,30)]
        rs += [run('Ordinary prose begins here and continues below.',20,y,500) for y in (270,290,310)]
        regions,owned=copy.scan_table_regions(numbered(rs),600)
        self.assertEqual(len(regions),1)
        self.assertEqual(owned,set(range(16)))
        self.assertEqual(copy.scan_line(copy.scan_rows(regions[0]['runs'])[-1]),'TOTAL 12 0.3')

    def test_smaller_wrapped_first_cell_is_not_caption_continuation(self):
        rs=numbered([run('TABLE IV',180,30,100,18),
            run('OBSERVATION SCORES',80,50,400,18),
            run('Healthy tissue with no bleeding',120,89,250,12),
            run('Grade 0',20,107,70),run('upon probing at the margin',120,107,250),
            run('Grade 1',20,137,70),run('Bleeding on probing',120,137,250)])
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0]['caption'],'TABLE IV OBSERVATION SCORES')
        self.assertEqual(owned,set(range(len(rs))))

    def test_numbered_reference_columns_cannot_be_a_grid(self):
        rs=[]
        for x,offset in [(20,0),(330,3)]:
            for i,y in enumerate((100,130,160),1):
                rs += [run(f'{i+offset}. Author, A.:',x,y,100),run('Journal 12: 34, 1970.',x+105,y,145)]
        regions,owned=copy.scan_table_regions(numbered(rs),600)
        self.assertEqual(regions,[]);self.assertEqual(owned,set())

    def test_single_word_wrapped_caption_keeps_its_alignment_and_size(self):
        rs=numbered([run('Table 3B. Measurements in Cases and',20,30,500),
            run('Controls',20,45,60),run('Group',20,80,100),run('Mean',200,80,100)])
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(regions[0]['caption'],'Table 3B. Measurements in Cases and Controls')

    def test_numbered_first_row_is_not_wrapped_caption(self):
        rs=numbered([run('TABLE 3 PREVENTION STRATEGIES',20,30,500),
            run('1. Reduced sugar or acid challenge',20,54,500),
            run('(a) A first proposed intervention',20,80,500)])
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(regions[0]['caption'],'TABLE 3 PREVENTION STRATEGIES')

    def test_wrapped_caption_can_contain_mixed_case_counts(self):
        rs=numbered([run('TABLE II. Response after treating 12 Cases,',20,30,550),
            run('14 Further Cases and 8 Controls',20,50,550),
            run('After 10 treatment pulses:',300,70,270),
            run('Group',20,100,100),run('Mean',300,100,100)])
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(regions[0]['caption'],
            'TABLE II. Response after treating 12 Cases, 14 Further Cases and 8 Controls')

    def test_wide_table_note_travels_with_table_above_body_columns(self):
        rs=[run('TABLE 1. Experimental measurements',20,30,550),
            run('Group',20,60),run('Mean',300,60),run('First',20,90),run('12.3',300,90)]
        rs += [run(t,20,y,550) for t,y in [
            ('The experimental cultures were treated on successive days.',120),
            ('and maintained in the stated conditions during the experiment.',138),
            ('The remaining cultures received no experimental treatment.',156)]]
        rs += [run('Ordinary body prose continues in this column.',x,y,250) for x in (20,330) for y in (210,228,246)]
        regions,owned=copy.scan_table_regions(numbered(rs),600)
        self.assertEqual(owned,set(range(8)))

    def test_caption_removal_preserves_short_body_column(self):
        rs=[run('Left column has a continuous ordinary sentence.',20,y,250) for y in (100,120,140,160)]
        rs += [run('Figure 1. This caption supplies a third column line.',330,100,250),
               run('Right column starts its continuous ordinary sentence',330,140,250),
               run('and finishes with another continuous ordinary line.',330,160,250)]
        page=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text=Path(copy.copy_ocr_scan(tmp,[page],{})).read_text()
        self.assertNotIn('sentence. Right column',text)
        self.assertLess(text.rindex('Left column'),text.index('Right column'))
        self.assertIn('\nRight column starts',text)

    def test_figure_caption_does_not_take_larger_body_lines(self):
        rs=numbered([run('FIGURE 3. A complete caption begins',20,100,560),
            run('and continues along its second printed line.',20,116,560),
            run('The body starts here and continues below.',20,145,260,16)])
        regions,owned=copy.scan_figure_regions(rs,600)
        self.assertEqual(len(regions),1);self.assertEqual(owned,{0,1})

    def test_roman_figure_label_keeps_adjacent_translation(self):
        rs=numbered([run('Fig. II. Caption with a Roman label.',20,100,560),
            run('Translation in another language.',20,122,560),
            run('The body resumes its earlier sentence here.',20,170,560,16)])
        regions,owned=copy.scan_figure_regions(rs,600)
        self.assertEqual(len(regions),1);self.assertEqual(owned,{0,1})

    def test_floats_wait_across_columns_and_pages_for_paragraph_end(self):
        def line(text,page,x,y):
            r=run(text,x,y,250)
            return dict(kind='line',page=page,runs=[r],box_px=r['box_px'])
        first=line('A sentence interrupted by the printed',1,20,700)
        mid=line('float continues on the next page.',2,20,100)
        more=line('The same paragraph has another sentence.',2,20,118)
        new=line('A new indented paragraph begins here.',2,40,136)
        floats=[dict(kind=k,page=1,runs=[]) for k in ('table','figure')]
        self.assertEqual(copy.scan_arrange_floats([first,*floats,mid,more,new]),
                         [first,mid,more,*floats,new])

    def test_byline_is_separate_but_abbreviated_numeric_continuation_is_not(self):
        def line(text,y):
            r=run(text,20,y,250)
            return dict(kind='line',page=1,runs=[r],box_px=r['box_px'])
        self.assertTrue(copy.scan_paragraph_start(line('A. B. EXAMPLE*',40),line('The opening body line.',80)))
        self.assertFalse(copy.scan_paragraph_start(line('The measurement was 1.10 mm,',100),line('S.D. 0.66.',118)))

    def test_unknown_caption_or_note_keeps_its_printed_gap(self):
        rs=[run('An unfinished sentence at the column foot',20,200,500),
            run('Unclassified text below the illustration.',20,400,500)]
        page=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text=Path(copy.copy_ocr_scan(tmp,[page],{})).read_text()
        self.assertIn('column foot\n\nUnclassified text',text)


if __name__=='__main__':unittest.main()
