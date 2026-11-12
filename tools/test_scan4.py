"""Inset OCR scans, mixed documents, caption continuity and prior-article ownership."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_scan4', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)


def run(text, x=30, y=100, width=250, size=12):
    return dict(text=text, box_px=[x,y,x+width,y+size], size_px=size)


def page(number=1, runs=()):
    return dict(page=number, region_box_px=[0,0,600,800], elements=[],
                scan_evidence=dict(ocr_layer=True, ocr_runs=list(runs)))


class ScanFour(unittest.TestCase):
    def test_inset_raster_requires_independent_invisibility_evidence(self):
        for hidden, expected in [(1,True),(.94,False),(0,False)]:
            p = dict(page=1,region_box_px=[0,0,600,800],
                     elements=[dict(kind='image',box_px=[20,20,580,780])])
            evidence = dict(image_coverage=.887,text_characters=500,
                            content_invisible_share=hidden,ocr_engine=True)
            reader = types.SimpleNamespace(sc_read_page=lambda *a:([],[],dict(scan_evidence=evidence)),
                                           sc_ocr_runs=lambda cs:[run('Recovered OCR sentence.')])
            with patch.object(copy,'scan_reader',return_value=reader):copy.scan_detect([p],'test.pdf')
            self.assertEqual(bool(p.get('scan_evidence')),expected)

    def test_ocr_page_is_never_declared_unread(self):
        self.assertFalse(copy.image_only_page(page(runs=[run('Recovered text')])) )

    def test_colon_continuation_stays_before_caption(self):
        a = dict(kind='line',page=2,runs=[run('The sequence on this side:',y=700)],box_px=[30,700,280,712])
        b = dict(kind='line',page=3,runs=[run('mesial surface and distal surface.',x=330)],box_px=[330,100,580,112])
        f = dict(kind='figure',page=3,runs=[run('Fig. 4. A caption.')],box_px=[330,30,580,42])
        self.assertEqual(copy.scan_arrange_floats([a,f,b]),[a,b,f])

    def test_labelled_folio_requires_detached_margin_position(self):
        for y, dropped in [(760,True),(450,False)]:
            p=page(runs=[run('An ordinary complete sentence.',y=400),run('Page 12/345',y=y)])
            self.assertEqual(1 in copy.scan_furniture([p])[1],dropped)

    def test_previous_article_reference_band_keeps_column_order(self):
        rs=[run('REFERENCES',y=40),run('1. One, A. First reference.',y=70),
            run('2. Two, B. Second reference.',y=90),run('3. Three, C. Third reference.',x=330,y=70),
            run('An Independent Article Title',y=250,width=540,size=24),
            run('A. Writer',y=290),run('INTRODUCTION',y=350),
            *[run('A body sentence with several ordinary printed words.',x=x,y=y)
              for x in (30,330) for y in (380,400,420)]]
        au=dict(title=dict(box_px=[30,250,570,274]),author_box_px=[30,290,280,302])
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            text=Path(copy.copy_ocr_scan(folder,[page(runs=rs)],au)).read_text()
            audit=json.loads((Path(folder)/'copy.scan.json').read_text())['pages'][0]
        self.assertIn('references belonging to the previous article',text)
        self.assertLess(text.index('2. Two'),text.index('3. Three'))
        self.assertEqual(audit['destinations']['6'],'text')
        self.assertEqual(audit['destinations']['0'],'previous_article')

    def test_embedded_scan_returns_evidence_without_overwriting_native_copy(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            path=Path(folder)/'copy.md';path.write_text('Existing native article')
            record=copy.copy_ocr_scan(folder,[page(13,[run('OCR content as recognised.')])],{},embedded=True)
            self.assertEqual(path.read_text(),'Existing native article')
            self.assertIn('OCR content as recognised.',record['text'])
            self.assertEqual(record['audit'][0]['page'],13)
            self.assertEqual(record['conservation'][0]['page'],13)

    def test_compilation_needs_distinct_article_opening_headers(self):
        def opening(n,doi):
            p=page(n);p['elements']=[dict(kind='text',**run(doi,y=30,size=10)),
                dict(kind='text',**run('An Independent Study Title',y=80,size=24)),
                dict(kind='text',**run('Abstract',y=180,size=12))]
            return p
        self.assertIn('compilation',copy.document_kind([opening(1,'10.1000/alpha'),opening(9,'10.1000/beta')])[0])
        self.assertIsNone(copy.document_kind([opening(1,'10.1000/alpha'),opening(9,'10.1000/alpha')]))
        same_page=opening(1,'10.1000/alpha')
        same_page['elements'].insert(0,dict(kind='text',**run('10.1000/beta',y=50,size=10)))
        self.assertIsNone(copy.document_kind([same_page]))
        references=opening(9,'10.1000/beta');references['elements'][-1]['text']='References'
        self.assertIsNone(copy.document_kind([opening(1,'10.1000/alpha'),references]))

    def test_first_page_of_embedded_section_owns_front_and_keywords(self):
        rs=[run('A Display Title',y=40,size=24),run('A. Writer',x=330,y=40),
            run('Department of Research',x=330,y=60),run('Abstract. A printed abstract.',y=120),
            run('Key words: first; second',x=330,y=200),
            *[run('The ordinary body sentence continues across its columns.',x=x,y=y)
              for x in (30,330) for y in (260,280,300)]]
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(copy,'table_pdf_path',return_value=None):
            record=copy.copy_ocr_scan(folder,[page(13,rs)],{},embedded=True)
        self.assertEqual(record['audit'][0]['destinations'][1],'front')
        self.assertEqual(record['audit'][0]['destinations'][4],'metadata')
        self.assertLess(record['text'].index('Key words:'),record['text'].index('The ordinary body'))

    def test_coincident_ocr_initial_over_figure_label_is_audited(self):
        chars=[]
        for i,ch in enumerate('fFig. 4.'):
            x=30+6*max(0,i-1)
            chars.append(dict(text=ch,x0=x,x1=x+6,y0=100,y1=112,
                              origin=[x,110],adv_x1=x+6,size=12,
                              paint_order=(1 if i==0 else 2,i)))
        source=[run(copy.scan_character_text(chars),y=100,width=42)]
        p=page(runs=source)
        reader=types.SimpleNamespace(sc_read_page=lambda *a:(chars,[],{}),sc_ocr_runs=lambda cs:source)
        with patch.object(copy,'scan_reader',return_value=reader):copy.scan_prepare_geometry([p],'test.pdf')
        recovered=copy.scan_source_runs(p)
        self.assertEqual([r['text'] for r in recovered],['Fig. 4.','f'])
        self.assertEqual(p['_scan_geometry']['splits'][0]['before'],'fFig. 4.')
        self.assertIn('duplicate',copy.scan_furniture([p])[1][1])

    def test_native_paragraphs_cannot_join_across_scan_section(self):
        items=[dict(kind='para',page=1,text='Unfinished native sentence'),
               dict(kind='ocr_scan',page=2,text='Scan section'),
               dict(kind='para',page=3,text='A different article.')]
        self.assertEqual(len(copy.rejoin_paragraphs(items,copy.Joiner([]))),3)


if __name__=='__main__':unittest.main()
