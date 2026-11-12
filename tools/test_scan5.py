"""Scan layout regressions: local caption columns, OCR ink rows and notes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scan5',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(text,x,y,w=240,size=12):
    return dict(text=text,box_px=[x,y,x+w,y+size],size_px=size)


def numbered(rs):
    return [dict(r,_scan_id=i) for i,r in enumerate(rs)]


class ScanFive(unittest.TestCase):
    def test_disjoint_ink_rows_survive_a_stretched_folio(self):
        chars=[dict(text='9',x0=20,y0=10,y1=20,size=200),
               dict(text='First',x0=20,y0=40,y1=60,size=24),
               dict(text='title',x0=90,y0=40,y1=60,size=24),
               dict(text='Second',x0=20,y0=70,y1=90,size=24)]
        self.assertEqual([[c['text'] for c in b] for b in copy.scan_vertical_pieces(chars)],
                         [['9'],['First','title'],['Second']])
        # An overlapping raised citation remains part of its line.
        chars=[dict(text='Word',x0=20,y0=30,y1=50),dict(text='2',x0=80,y0=25,y1=35)]
        self.assertEqual(len(copy.scan_vertical_pieces(chars)),1)

    def test_two_captions_crossing_body_gutters_stay_independent(self):
        rs=numbered([run('Figure 4. The left caption begins.',20,100,320),
            run('Figure 5. The right caption begins.',370,100,320),
            run('The left caption ends here.',20,116,310),
            run('The right caption ends here.',370,116,310)])
        fs,owned=copy.scan_figure_regions(rs,900,gutters=[300,600])
        self.assertEqual([{r['_scan_id'] for r in f['runs']} for f in fs],[{0,2},{1,3}])
        self.assertEqual(owned,set(range(4)))
        self.assertEqual(copy.scan_order(fs,[300,600]),fs)

    def test_caption_does_not_consume_narrow_wrapped_body_column(self):
        rs=numbered([run('Figure 2. A wide caption beneath an image.',20,300,330),
            run('a narrow body line',390,300,130),
            run('The caption continues beneath the image.',20,316,335),
            run('continues here',390,316,130),
            *[run('A narrow continuation',390,y,130) for y in (100,120,140,160)]])
        fs,owned=copy.scan_figure_regions(rs,900,gutters=[300,600])
        copy.scan_figure_lettering(fs,rs,900,[300,600])
        self.assertEqual({r['_scan_id'] for f in fs for r in f['runs']},{0,2})
        body=dict(kind='line',runs=[run('Earlier column finishes here.',20,700)],box_px=[20,700,260,712])
        continuation=dict(kind='line',runs=[rs[4]],box_px=rs[4]['box_px'])
        ordered=copy.scan_order([fs[0],body,continuation],[300,600])
        self.assertLess(ordered.index(body),ordered.index(continuation))

    def test_existing_gutter_allows_wider_caption_translation(self):
        rs=numbered([run('Fig. 1. Caption in the first language.',20,300,400),
            run('Adjacent ordinary body prose.',620,300,250),
            run('A wider translation remains with the figure.',20,322,560)])
        fs,owned=copy.scan_figure_regions(rs,900,gutters=[300,600])
        self.assertEqual(owned,{0,2})

    def test_unread_figure_number_is_flagged_without_inventing_it(self):
        rs=numbered([run('x',200,100,10),run('Figure . The printed caption.',20,300,500),
                      run('Continuation of the caption.',20,316,500)])
        fs,owned=copy.scan_figure_regions(rs,600)
        self.assertTrue(fs[0]['incomplete_label'])
        self.assertEqual(owned,{1,2})
        rs=numbered([run('Fig. IV. A numbered caption.',20,300,500)])
        self.assertFalse(copy.scan_figure_regions(rs,600)[0][0]['incomplete_label'])

    def test_small_column_footnote_waits_for_sentence_continuation(self):
        rs=numbered([*[run('Ordinary body prose with several printed words',20,y,250,16)
                      for y in (560,580,600)],run('* A department address',20,650,240,12),
                     run('at the university.',20,665,200,12)])
        notes=copy.scan_notes(rs,600,800,[300]);self.assertEqual(len(notes),1)
        a=dict(kind='line',runs=[run('The current sentence',20,600)],box_px=[20,600,260,612],page=1)
        b=dict(kind='line',runs=[run('continues in this column.',330,100)],box_px=[330,100,570,112],page=1)
        notes[0]['page']=1
        self.assertEqual(copy.scan_arrange_floats([a,notes[0],b]),[a,b,notes[0]])
        rs[-2]['text']='An ordinary smaller paragraph'
        self.assertEqual(copy.scan_notes(rs,600,800,[300]),[])

    def test_paired_nested_blocks_stop_before_reference_continuations(self):
        rs=numbered([run('A biography line',x,y,110,10)
                      for x in (620,770) for y in (100,115,130,145,160,175)] +
                     [run('1999;12:34-56.',770,210,100,10),
                      run('Next bibliography entry continues.',620,250,260,10)])
        blocks=copy.scan_side_blocks(rs,900,[300,600])
        self.assertEqual(len(blocks),2)
        self.assertEqual({r['_scan_id'] for b in blocks for r in b['runs']},set(range(12)))

    def test_chart_axes_cannot_make_neighboring_numeric_prose_a_table(self):
        rs=[run('Ordinary prose continues in the right column.',330,y,240,12) for y in (300,320,340)]
        for y in (400,430,460):
            rs += [run('10',30,y,15),run('at',330,y,15),run('0.25',355,y,30),
                   run('mm for this visit.',395,y,175)]
        rs += [run('Figure 8. The measured distribution.',20,600,250)]
        p=dict(page=2,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[p],{})).read_text()
        self.assertNotIn('Table-like region',text)
        self.assertEqual(text.count('at 0.25 mm for this visit.'),3)

    def test_terminal_uppercase_abbreviation_does_not_release_a_note(self):
        def line(text,y):
            r=run(text,20,y)
            return dict(kind='line',runs=[r],box_px=r['box_px'],page=1)
        a=line('The measured depth was 8 mm',100);b=line('PD.',116)
        note=dict(kind='note',runs=[run('* Product address',20,700)],box_px=[20,700,260,712],page=1)
        self.assertEqual(copy.scan_arrange_floats([a,note,b]),[a,b,note])

    def test_inferred_title_and_names_precede_the_side_abstract(self):
        rs=[run('AN UPPERCASE DISPLAY TITLE',260,100,300,24),
            run('WITH ANOTHER DISPLAY LINE',260,134,300,24),
            run('A. WRITER; B. WRITER',260,175,300,12),
            *[run('The side abstract contains printed words.',20,y,210,12) for y in (210,230,250)],
            *[run('The body has ordinary printed words here.',260,y,300,12) for y in (210,230,250)]]
        p=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[p],{})).read_text()
            evidence=json.loads((Path(folder)/'copy.conservation.json').read_text())
        self.assertLess(text.index('# AN UPPERCASE'),text.index('The side abstract'))
        self.assertLess(text.index('A. WRITER'),text.index('The side abstract'))
        self.assertEqual(evidence['token_ledger']['missing_tokens'],0)


if __name__=='__main__':unittest.main()
