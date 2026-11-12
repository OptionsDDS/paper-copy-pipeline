"""PDF-evidence and lossless OCR-mode regressions; run in its own process."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


boxer = module('scan_boxer', ROOT/'standalone/element_boxer_sc.py')
copy = module('scan_copy', ROOT/'copy_paper.py')


def pdf(path, content, metadata='', image_extra='', graphics_state=''):
    """A real tiny PDF: standard font, opaque page image, optional metadata."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] '
        b'/Resources << /Font << /F 4 0 R >> /XObject << /I 5 0 R >> '+
        ('/ExtGState << /G << '+graphics_state+' >> >> >> /Contents 6 0 R >>').encode(),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        ('<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray '
         '/BitsPerComponent 8 /Length 1 '+image_extra+' >>\nstream\n').encode()+b'\xff\nendstream',
        ('<< /Length '+str(len(content))+' >>\nstream\n'+content+'\nendstream').encode(),
        ('<< /Producer ('+metadata+') >>').encode()]
    data=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data)); data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data)
    data+=b'xref\n0 8\n0000000000 65535 f \n'
    data+=b''.join(f'{n:010d} 00000 n \n'.encode() for n in offsets[1:])
    data+=f'trailer << /Size 8 /Root 1 0 R /Info 7 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    path.write_bytes(data)


TEXT='BT /F 3 Tf 5 50 Td (Recognised letters and values) Tj ET'
IMAGE='q 100 0 0 100 0 0 cm /I Do Q'


def run(text,x,y,width=150,size=12):
    return dict(text=text,box_px=[x,y,x+width,y+size],size_px=size)


class Evidence(unittest.TestCase):
    def evidence(self, content, metadata='', image_extra='', graphics_state=''):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path=Path(tmp)/'test.pdf';pdf(path,content,metadata,image_extra,graphics_state)
            d=boxer.sc_doc(str(path));sink=boxer.SCSink()
            interp=boxer.SCInterpreter(d.rsrc,boxer.PDFDevice(d.rsrc),sink,d,0)
            interp.render_contents(d.pages[0].resources,d.pages[0].contents,ctm=boxer.MATRIX_IDENTITY)
            return boxer.sc_scan_evidence(d,1,sink)

    def test_text_under_later_opaque_page_image(self):
        e=self.evidence(TEXT+' '+IMAGE)
        self.assertTrue(e['ocr_layer']);self.assertEqual(e['invisible_share'],1)
        self.assertEqual(e['render_mode_3'],0)

    def test_visible_text_over_page_background_is_not_ocr(self):
        e=self.evidence(IMAGE+' '+TEXT)
        self.assertFalse(e['ocr_layer']);self.assertEqual(e['invisible_share'],0)

    def test_invisible_render_mode_over_image(self):
        e=self.evidence(IMAGE+' 3 Tr '+TEXT)
        self.assertTrue(e['ocr_layer']);self.assertGreater(e['render_mode_3'],20)

    def test_visible_footer_does_not_hide_a_short_ocr_page(self):
        footer='0 Tr BT /F 1 Tf 5 2 Td (Visible publisher download footer with many characters) Tj ET'
        e=self.evidence(IMAGE+' 3 Tr '+TEXT+' '+footer)
        self.assertLess(e['invisible_share'],.95)
        self.assertEqual(e['content_invisible_share'],1)
        self.assertTrue(e['ocr_layer'])

    def test_explicit_ocr_producer_requires_page_coverage(self):
        self.assertTrue(self.evidence(IMAGE+' '+TEXT,'ABBYY FineReader')['ocr_layer'])
        self.assertFalse(self.evidence(TEXT,'ABBYY FineReader')['ocr_layer'])

    def test_overlapping_images_cannot_fake_page_coverage(self):
        im='q 50 0 0 100 0 0 cm /I Do Q'
        self.assertFalse(self.evidence(TEXT+' '+im+' '+im)['ocr_layer'])

    def test_two_tiles_cover_the_page(self):
        im='q 50 0 0 100 0 0 cm /I Do Q q 50 0 0 100 50 0 cm /I Do Q'
        self.assertTrue(self.evidence(TEXT+' '+im)['ocr_layer'])

    def test_masked_image_does_not_prove_occlusion(self):
        self.assertFalse(self.evidence(TEXT+' '+IMAGE,image_extra='/Mask [0 0]')['ocr_layer'])

    def test_nonrectangular_clip_cannot_prove_coverage(self):
        self.assertFalse(self.evidence(TEXT+' 0 0 m 100 0 l 100 100 l h W n '+IMAGE)['ocr_layer'])

    def test_blending_does_not_prove_occlusion(self):
        self.assertFalse(self.evidence(TEXT+' /G gs '+IMAGE,graphics_state='/BM /Multiply')['ocr_layer'])

    def test_graphics_soft_mask_does_not_prove_occlusion(self):
        self.assertFalse(self.evidence(TEXT+' /G gs '+IMAGE,graphics_state='/SMask << /S /Alpha >>')['ocr_layer'])

    def test_restored_graphics_state_can_prove_occlusion(self):
        self.assertTrue(self.evidence(TEXT+' q /G gs Q '+IMAGE,graphics_state='/BM /Multiply')['ocr_layer'])


class ScanCopy(unittest.TestCase):
    def test_folio_beside_footnote_requires_other_page_number_witnesses(self):
        pages=[]
        for i in range(1,5):
            rs=[run(f'Body text from section {i}.',20,200,450),run('Funding note.',20,733,400),
                run(str(100+i),20,749,30)] if i==1 else [
                run(str(100+i),20,30,30),run('Journal running head',100,30,250),
                run(f'Other body text from section {i}.',20,150,400)]
            pages.append(dict(page=i,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs)))
        self.assertIn(2,copy.scan_furniture(pages)[1])
        pages[0]['scan_evidence']['ocr_runs'][2]['text']='999'
        self.assertNotIn(2,copy.scan_furniture(pages)[1])

    def test_alternate_margin_patterns_and_downloads_leave_flow(self):
        pages=[]
        for i in range(1,11):
            rs=[run(str(i+8),20,30,20),run('Sample et al.' if i%2 else 'General journal',200,32,140),
                run(f'The paragraph on this page continues with source value {i}.',20,100,450),
                run('Downloaded from journal.example.org for personal use.',80,770,400)]
            pages.append(dict(page=i,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs)))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text=Path(copy.copy_ocr_scan(tmp,pages,{})).read_text()
            self.assertNotIn('Sample et al.',text);self.assertNotIn('General journal',text)
            self.assertNotIn('Downloaded from',text);self.assertNotIn('[Page header as printed]',text)
            audit=json.loads((Path(tmp)/'copy.scan.json').read_text())
            for p in audit['pages']:
                self.assertEqual(len(p['destinations']),4)
                self.assertEqual(len(p['furniture']),3)
                self.assertIn(f'source value {p["page"]}',text)

    def test_margin_numbers_do_not_remove_table_values_or_title(self):
        pages=[]
        for i in range(1,5):
            rs=[run('Repeated study title',20,20,400,30),run('Table heading',20,80,180),
                run('123',20,100,25),run('Measured cell',70,100,100),
                run('Table continued value',20,120,180),run('Other content.',20,500,300),
                run(str(98+i),550,750,30)]
            pages.append(dict(page=i,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=rs)))
        # A larger title differs from the small running title on later pages.
        for p in pages[1:]:p['scan_evidence']['ocr_runs'][0]['size_px']=10
        excluded=copy.scan_furniture(pages)
        self.assertNotIn(0,excluded[1])
        for ids in excluded.values():
            self.assertNotIn(1,ids);self.assertNotIn(2,ids);self.assertNotIn(3,ids)
            self.assertIn(6,ids)

    def test_recurring_caption_labels_are_content_even_with_a_gap(self):
        pages=[dict(page=i,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=[
            run(f'TABLE {i}',20,20,100),run('Measurements and reported values',20,60,300),
            run('Other article content.',20,200,300)])) for i in range(1,5)]
        for ids in copy.scan_furniture(pages).values():self.assertNotIn(0,ids)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            copy.copy_ocr_scan(tmp,pages,{})
            audit=json.loads((Path(tmp)/'copy.scan.json').read_text())
            for p in audit['pages']:self.assertEqual(p['destinations']['0'],'table')

    def test_unconfirmed_header_is_once_at_end_not_at_page_break(self):
        pages=[dict(page=i,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_runs=[
            run('An isolated unconfirmed title',20,20,300),run('continues the preceding sentence.',20,110,400)]))
            for i in (1,2)]
        # One occurrence cannot prove recurrence.
        pages[0]['scan_evidence']['ocr_runs'][0]['text']='Opening document title'
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text=Path(copy.copy_ocr_scan(tmp,pages,{})).read_text()
            self.assertGreater(text.index('An isolated unconfirmed title'),text.index('## Places'))
            self.assertEqual(text.count('An isolated unconfirmed title'),1)
            self.assertNotIn('[Page header as printed]',text)

    def test_figure_text_cannot_split_column_prose(self):
        prose='These ordinary words continue the same printed paragraph'
        rs=[run(prose,20,y,260) for y in (100,120,140)]
        rs += [run('Figure 2. Caption belonging to a graphic.',350,75,260)]
        rs += [run(prose,350,y,260) for y in (100,120)]
        p=dict(page=2,region_box_px=[0,0,650,800],elements=[],
               scan_evidence=dict(ocr_layer=True,ocr_runs=rs),
               floats=[dict(caption='Figure 2. Caption belonging to a graphic.',box_px=[350,20,610,90])])
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text=Path(copy.copy_ocr_scan(tmp,[p],{})).read_text()
            self.assertLess(text.index('Figure 2.'),text.index(prose))
            self.assertEqual(text.splitlines().count(prose),5)
            self.assertEqual(text.count('Figure 2.'),1)

    def test_skewed_columns_do_not_detach_a_word(self):
        rs=[run('Left column line',20,100,200,16),run('A separate',350,104,90,17),
            run('word',450,108,40,20),run('finishes this line',500,104,130,24),
            run('Next left line',20,125,200,16),run('Next right line',350,129,280,24)]
        rows=copy.scan_rows(rs)
        self.assertEqual(len(rows),2)
        self.assertEqual(copy.scan_line(rows[0]),'Left column line A separate word finishes this line')

    def test_left_table_does_not_claim_adjacent_prose(self):
        rs=[run('TABLE 8',80,30,80),run('EFFECT OF 0.5% SOLUTION',20,45,240),
            run('IN ADULTS (12 subjects)',20,60,240)]
        for y in (85,100,115):
            rs += [run('Sample',20,y,60),run('12',150,y,25),run('0.5',240,y,25)]
        prose='These ordinary words continue a printed body paragraph.'
        rs += [run(prose,350,y,240) for y in range(30,251,20)]
        rs += [run(prose,20,y,240) for y in range(180,251,20)]
        for i,r in enumerate(rs):r['_scan_id']=i
        regions,owned=copy.scan_table_regions(rs,650)
        self.assertEqual(len(regions),1)
        self.assertTrue(all(r['box_px'][2]<320 for r in regions[0]['runs']))
        self.assertNotIn(prose,regions[0]['caption'])
        self.assertIn('IN ADULTS (12 subjects)',regions[0]['caption'])
        self.assertEqual(len(owned),12)

    def test_table_is_complete_and_body_does_not_enter_gate(self):
        rs=[run('Table 7. Experimental measurements',20,30,350)]
        for y,label,value in [(55,'First','12'),(70,'Second','34'),(85,'Third','56')]:
            rs += [run(label,20,y,100),run(value,200,y,30),run('0.25',300,y,30)]
        rs += [run('This is a sufficiently long opening line of the body paragraph.',20,120,350),
               run('The next printed line continues that same ordinary paragraph.',20,135,350),
               run('Its final short continuation.',20,150,180)]
        for i,r in enumerate(rs):r['_scan_id']=i
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(len(regions),1)
        self.assertEqual(owned,set(range(10)))
        self.assertEqual([copy.scan_line(row) for row in copy.scan_rows(regions[0]['runs'])][-1],'Third 56 0.25')

    def test_captionless_numeric_grid_is_gated(self):
        rs=[run(str(k),x,30+20*y,30) for y in range(3) for k,x in [(10,20),(20,150),(30,250)]]
        for i,r in enumerate(rs):r['_scan_id']=i
        regions,owned=copy.scan_table_regions(rs,600)
        self.assertEqual(len(regions),1);self.assertEqual(len(owned),9)

    def test_front_matter_and_ocr_symbols_survive_once(self):
        rs=[run('Example paper',20,20,300,20),run('Ada Sample, Ben Example',20,60,300),
            run('Abstract: these are the source letters IL-lß and (xmol.',20,100,400),
            run('The measurements were stated as &2,500 g in the source.',20,118,400),
            run('A further line completes this abstract in printed order.',20,136,400)]
        p=dict(page=1,region_box_px=[0,0,600,800],elements=[],scan_evidence=dict(ocr_layer=True,ocr_runs=rs))
        au=dict(title=dict(box_px=[20,20,320,40]),checks=dict(status='not verified'),authors=[dict(name='Bad guess')])
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text=Path(copy.copy_ocr_scan(tmp,[p],au)).read_text()
            self.assertIn('Front matter as printed',text);self.assertEqual(text.count('Ada Sample, Ben Example'),1)
            self.assertNotIn('Bad guess',text)
            self.assertIn('IL-lß and (xmol.',text);self.assertIn('&2,500 g',text)
            audit=json.loads((Path(tmp)/'copy.scan.json').read_text())['pages'][0]
            self.assertEqual(len(audit['destinations']),len(rs))


if __name__=='__main__':unittest.main()
