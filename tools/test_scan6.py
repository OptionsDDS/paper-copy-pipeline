"""Scan regressions (scan6): caption lines read whole, spaced folios, outsized glyph boxes."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scan6',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(text,x,y,w=240,size=12,h=None):
    return dict(text=text,box_px=[x,y,x+w,y+(size if h is None else h)],size_px=size)


def numbered(rs):
    return [dict(r,_scan_id=i) for i,r in enumerate(rs)]


class ScanSix(unittest.TestCase):
    def test_justified_caption_word_pieces_form_one_line(self):
        # OCR splits each justified caption line at wide spaces; the next
        # caption lines put ink across those gaps (AG01 geometry, scaled).
        rs=numbered([run('FIGURE 1. A histological',20,300,150),run('section and',200,300,80),
                     run('specimen',300,300,60),
                     run('cut through a',20,316,90),run('procedure with',140,316,110),run('ink.',280,316,80),
                     run('Granulation tissue is',20,332,160),run('present at the',200,332,160),
                     run('Ordinary body prose in the next column.',420,300,250,16),
                     *[run('Ordinary body prose in the next column.',420,y,250,16) for y in (100,125,150)],
                     *[run('Ordinary body prose in the first column.',20,y,340,16) for y in (100,125,150)]])
        fs,owned=copy.scan_figure_regions(rs,700,gutters=[390])
        self.assertEqual(len(fs),1)
        self.assertEqual({r['_scan_id'] for r in fs[0]['runs']},set(range(8)))
        self.assertEqual(copy.scan_line(copy.scan_rows(fs[0]['runs'])[0]),
                         'FIGURE 1. A histological section and specimen')

    def test_white_channel_through_caption_lines_keeps_blocks_apart(self):
        rs=numbered([run('Figure 2. A caption',20,300,150),run('a neighboring block',230,300,150),
                     run('caption continues',20,316,150),run('neighbor continues',230,316,150),
                     run('caption ends here.',20,332,140),run('neighbor ends.',230,332,140)])
        fs,owned=copy.scan_figure_regions(rs,600,gutters=[])
        self.assertEqual({r['_scan_id'] for f in fs for r in f['runs']},{0,2,4})
        # A narrower common river is a word space, not a channel.
        rs=numbered([run('Figure 2. A caption',20,300,150),run('word',178,300,40),
                     run('caption continues',20,316,154),run('more',180,316,40),
                     run('caption ends here',20,332,152),run('last.',179,332,40)])
        fs,owned=copy.scan_figure_regions(rs,600,gutters=[])
        self.assertEqual(owned,set(range(6)))

    def test_body_lines_on_other_baselines_beside_a_caption_stay_body(self):
        # A caption beside body lines a third of a line lower, across a
        # gutter narrower than an em (Z11 geometry): the body is not caption.
        rs=numbered([run('FIGURE 1. (a) Gross appearance of a sample.',87,949,510,23),
                     run('the flap tissue. After thorough planing and re-',615,936,505,23),
                     run('(b) Microscopic appearance of the sample. Note',86,971,521,23),
                     run('moval of all granulation tissue within the de-',616,961,504,23),
                     run('the varying sizes of the particles. Numerous red',87,992,515,23),
                     run('fect, perforations were made into the bone to in-',615,986,505,23)])
        fs,owned=copy.scan_figure_regions(rs,1275,gutters=[608])
        self.assertEqual(owned,{0,2,4})

    def test_dash_closes_a_caption_label_but_not_a_range(self):
        rs=numbered([run('Fig. 1—The diagram depicts a relationship',20,300,300),
                     run('between the plaque and the host.',20,316,300)])
        fs,owned=copy.scan_figure_regions(rs,600,gutters=[])
        self.assertEqual(owned,{0,1})
        rs=numbered([run('Fig. 1–3 show the measured values in',20,300,300),
                     run('each of the three groups.',20,316,300)])
        self.assertEqual(copy.scan_figure_regions(rs,600,gutters=[])[1],set())

    def test_ocr_spaced_folio_needs_page_offset_agreement(self):
        pages=[]
        for i in range(1,6):
            rs=[run(f'Body text continues on page {i} of this article.',20,200,450),
                run(f'and more body text on page {i} of this article.',20,216,450),
                run(str(200+i),20,760,30)]
            pages.append(dict(page=i,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs)))
        pages[2]['scan_evidence']['ocr_runs'][2]['text']='20 3'
        self.assertIn(2,copy.scan_furniture(pages)[3])
        pages[2]['scan_evidence']['ocr_runs'][2]['text']='20 9'
        self.assertNotIn(2,copy.scan_furniture(pages)[3])

    def test_outsized_glyph_box_does_not_merge_two_lines(self):
        a=run('gingival tissue. Cultures of peripheral blood mono-',658,386,476,23,h=27)
        b=run('cytes exposed to lipopolysaccharide produce IL- 1 s',658,395,476,23,h=50)
        c=run('and matrix metalloproteinases, and cells from indi-',658,440,476,23,h=27)
        rows=copy.scan_rows([dict(r,_scan_exact_geometry=True) for r in (b,a,c)])
        self.assertEqual([copy.scan_line(r) for r in rows],[a['text'],b['text'],c['text']])
        # Rule ink with a small nominal size keeps its own ink height.
        t=run('tumor necrosis factor a.',182,1551,190,18.5,h=23)
        d=run('__ ~ . ~~',195,1562,65,9.3,h=20)
        rows=copy.scan_rows([dict(r,_scan_exact_geometry=True) for r in (t,d)])
        self.assertEqual(len(rows),2)

    def test_unhyphenated_two_column_caption_continues_level_with_its_label(self):
        rs=numbered([run('Fig. 1. The first half of a caption',20,300,260),
                     run('bind to the second half of it,',320,300,260),
                     run('continues without a hyphen',20,316,260),run('which ends in this column.',320,316,260),
                     run('and its last line ends with IL-1',20,332,260),
                     run('Ordinary body text resumes after a gap.',20,380,260,13),
                     run('Ordinary body text resumes after a gap.',320,380,260,13)])
        fs,owned=copy.scan_figure_regions(rs,600,gutters=[300])
        self.assertEqual({r['_scan_id'] for r in fs[0]['runs']},{0,1,2,3,4})
        # A lowercase body column that runs on below the caption is not its tail.
        rs[5]['box_px']=[320,332,580,344];rs[6]['box_px']=[320,348,580,360]
        fs,owned=copy.scan_figure_regions(rs,600,gutters=[300])
        self.assertEqual({r['_scan_id'] for r in fs[0]['runs']},{0,2,4})

    def test_reference_abbreviation_does_not_end_a_sentence(self):
        def line(text,y,page=1):
            r=run(text,20,y)
            return dict(kind='line',runs=[r],box_px=r['box_px'],page=page)
        a=line('cells had migrated from the adjacent gingiva (Fig.',700)
        b=line('7A). Heavy infiltration was seen.',100,page=2)
        fig=dict(kind='figure',runs=[run('FIGURE 5. A caption.',20,40)],box_px=[20,40,260,52],page=2)
        self.assertEqual(copy.scan_arrange_floats([a,fig,b]),[a,b,fig])
        c=line('the next line starts in lowercase here.',100,page=2)
        a2=line('A sentence that seems to end.',700)
        self.assertEqual(copy.scan_arrange_floats([a2,fig,c]),[a2,c,fig])


if __name__=='__main__':unittest.main()
