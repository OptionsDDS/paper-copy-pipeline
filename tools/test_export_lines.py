"""Line ownership, glyph runs, typography, rotated pixels and renderer contract."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('export_lines_tests', ROOT/'tools/export_lines.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def run(mid, text, box, angle=0, font='Example-Regular'):
    return dict(id=mid, kind='text', text=text, box_px=box, angle=angle, size_px=10, run_size_px=10, font=font)


class Export(unittest.TestCase):
    def test_words_are_a_multiset_preserving_values_and_case(self):
        result = e.difference(e.words('Value 1 1 μm'), e.words('value 1 μm'))
        self.assertEqual(result['missing'], {'1': 1, 'Value': 1})
        self.assertEqual(result['extra'], {'value': 1})
        self.assertFalse(result['equal'])
        self.assertEqual(e.words('ﬁve'), e.words('five'))

    def test_two_columns_and_rotated_text_are_owned_once(self):
        rs = [run('a', 'left', [10, 10, 30, 20]), run('b', 'right', [100, 10, 140, 20]),
              run('c', 'rotated', [150, 50, 160, 100], 90), run('d', 'bold', [31, 10, 50, 20], font='Face-Bold')]
        groups = e.source_rows(dict(elements=rs), {})
        self.assertEqual([[r['id'] for r in row] for row in groups], [['a', 'd'], ['b'], ['c']])
        self.assertEqual(len({r['id'] for row in groups for r in row}), 4)

    def test_role_boundary_and_raster_image(self):
        page = dict(elements=[run('a', 'body', [1, 1, 20, 10]), run('b', 'folio', [21, 1, 30, 10]),
                              dict(kind='image', id='raster', box_px=[0, 0, 100, 100])])
        groups = e.source_rows(page, {'b': 'furniture'})
        self.assertEqual([[r['id'] for r in row] for row in groups], [['a'], ['b']])

    def test_narrow_two_column_gutter_never_interleaves_lines(self):
        left=run('a','A sentence ending in Fig-',[10,10,100,20]);left['region']='left'
        right=run('b','unrelated right column',[107,10,197,20]);right['region']='right'
        page=dict(elements=[left,right],main_text=dict(columns=[[10,100],[107,197]]))
        self.assertEqual([[r['id'] for r in row] for row in e.source_rows(page,{})],[['a'],['b']])

    def test_style_uses_weighted_majority_and_subset_fonts(self):
        self.assertTrue(e.style([run('a', 'bold text', [0, 0, 1, 1], font='ABCDEF+Face-Bold')], r'bold'))
        self.assertFalse(e.style([run('a', 'regular text', [0, 0, 1, 1]),
                                 run('b', 'x', [0, 0, 1, 1], font='Face-Bold')], r'bold'))
        self.assertFalse(e.style([run('a', 'unknown face', [0, 0, 1, 1], font=None)], r'bold'))

    def test_image_box_inverts_all_native_rotations_and_shifted_media(self):
        box = [12, 23, 42, 55]
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                geometry = dict(media=[20, 30, 620, 830], width=600, height=800, rotation=rotation)
                native = e.conserve.native_box(box, geometry, 150/72, 150/72)
                actual = e.image_box(native, 150, geometry)
                for a, b in zip(actual, box): self.assertAlmostEqual(a, b*110/72)

    def test_shifted_rotated_pdf_agrees_with_poppler_word_coordinates(self):
        # A real PDF gives an independent Poppler witness, rather than just
        # testing the forward and inverse of the same coordinate formula.
        content=b'BT /F1 14 Tf 50 100 Td (TEST) Tj ET'
        objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
                 b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                 b'<< /Type /Page /Parent 2 0 R /MediaBox [20 30 220 330] /Rotate 90 '
                 b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                 b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                 b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream']
        data=bytearray(b'%PDF-1.4\n');offsets=[]
        for i,obj in enumerate(objects,1):
            offsets.append(len(data));data.extend(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
        xref=len(data);data.extend(b'xref\n0 6\n0000000000 65535 f \n')
        data.extend(b''.join(f'{off:010} 00000 n \n'.encode() for off in offsets))
        data.extend(b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n')
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            pdf=Path(tmp)/'rotation.pdf';pdf.write_bytes(data)
            geometry=e.conserve.page_geometry(pdf)
            reader=sys.modules.get('_copy_table_reader') or sys.modules['_conserve_geometry']
            chars=reader.sc_read_page(str(pdf),1)[0]
            native=e.copy.hull([c[k] for k in ('x0','y0','x1','y1')] for c in chars)
            box=e.image_box(native,150,geometry[1])
            poppler=next(e.conserve.pdf_lines(pdf))[3][0]['box']
            for actual, expected in zip(box,poppler):self.assertAlmostEqual(actual,expected*110/72,places=2)

    def test_render_command_uses_110_dpi_and_exact_page_name(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            out = Path(tmp); path = out/'p03.png'
            path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + struct.pack('>II', 935, 1210))
            with patch.object(e.subprocess, 'run') as call:
                image, size = e.render_page(Path('source.pdf'), 3, out)
            self.assertEqual(image, path)
            self.assertEqual(size, (935, 1210))
            args = call.call_args.args[0]
            self.assertEqual(args[args.index('-r')+1], '110')
            self.assertEqual(args[args.index('-f')+1], '3')
            self.assertIn('-singlefile', args)
            self.assertNotIn('-cropbox', args)

    def test_invalid_png_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp)/'bad.png'; path.write_bytes(b'not a png')
            with self.assertRaisesRegex(ValueError, 'invalid PNG'): e.png_size(path)

    def test_no_export_inside_source_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            with self.assertRaisesRegex(ValueError, 'outside COPY_DIR'):
                e.export(tmp, Path(tmp)/'paper.pdf', Path(tmp)/'export')
            with self.assertRaisesRegex(ValueError, 'outside COPY_DIR'):
                e.export(Path(tmp)/'pages', Path(tmp)/'paper.pdf', tmp)

    def test_current_output_chunks_keep_offsets(self):
        text = '# Title\n\n**Authors:** Ada\n\n## Body\n\nA paragraph.\n\n<!-- end of page 1 -->\n\n## Places the program is not sure of\n- none'
        chunks = e.markdown_chunks(text)
        self.assertEqual([c['kind'] for c in chunks], ['title', 'authors', 'heading', 'paragraph'])
        for c in chunks: self.assertEqual(text[c['start']:c['end']], c['text'])

    def test_full_line_witness_overrides_a_misallocated_common_word(self):
        text = 'Earlier common word.\n\nThe common word belongs here.'
        chunks = e.markdown_chunks(text)
        i, order = e.locate_line('The common word belongs here.', [0, 3, 5, 8], chunks)
        self.assertEqual(i, 1)
        self.assertEqual(order, text.index('The common'))

    def test_capitalized_heading_does_not_match_lowercase_body_phrase(self):
        chunks=e.markdown_chunks('## BONE SOUNDING\n\nBone sounding is a clinical measurement.')
        self.assertEqual([i for i,pos in e.line_locations('BONE SOUNDING',chunks)],[0])

    def test_author_affiliation_and_reference_chunks_remain_separate(self):
        text = '**Authors:** Ada\n- 1 University\n- 2 Institute\n\n## References\n\n- First study\n- Second study'
        self.assertEqual([c['kind'] for c in e.markdown_chunks(text)],
                         ['authors', 'affiliation', 'affiliation', 'heading', 'reference', 'reference'])

    def mapping_fixture(self, texts, roles=None):
        lines=[dict(id=f'p1.l{i:03}',text=text,box=[10,10+i*15,180,20+i*15],size=10,
                    bold=False,italic=False,program_role=(roles or ['body']*len(texts))[i-1])
               for i,text in enumerate(texts,1)]
        document=dict(paper='example',pages=[dict(page=1,width_px=200,height_px=300,image='pages/p01.png',lines=lines)])
        audit=dict(lines={line['id']:dict(page=1,source_box=line['box'],angle=0,order=0,
                                       source_role=line['program_role']) for line in lines})
        return document,audit

    def test_repeated_tail_follows_its_unique_geometric_neighbor(self):
        texts=['A phrase repeated here.','Unique neighboring continuation.','A phrase repeated here.']
        document,audit=self.mapping_fixture(texts)
        mapping=e.refresh_program_map(document,audit,' '.join(texts))
        self.assertEqual(mapping['body'][0]['lines'],['p1.l001','p1.l002','p1.l003'])
        self.assertGreater(audit['lines']['p1.l003']['order'],audit['lines']['p1.l002']['order'])

    def test_recovered_doi_outranks_furniture_but_a_logo_does_not(self):
        document,audit=self.mapping_fixture(['DOI: 10.1234/example','Journal','Journal Example'],
                                          ['furniture','furniture','body'])
        mapping=e.refresh_program_map(document,audit,'## Article information\n\n- DOI: 10.1234/example\n- Journal Example')
        self.assertIn(['p1.l001'],mapping['front']['article_info'])
        self.assertIn('p1.l002',mapping['furniture']['other'])

    def test_byline_conjunction_uses_legal_conserved_splits(self):
        document,audit=self.mapping_fixture(['Ada and Bob'],['front'])
        mapping=e.refresh_program_map(document,audit,'**Authors:** Ada; Bob')
        assembler=e.module('split_byline_test',ROOT/'tools/assemble_map.py')
        text,proof=assembler.render(document,mapping)
        self.assertIn('**Authors:** Ada Bob',text)
        self.assertEqual(proof['conservation']['leaf_lines'],3)
        self.assertEqual(proof['furniture']['other'],1)
        self.assertEqual(mapping['front']['authors'],['p1.l001a','p1.l001bb'])

    def test_export_exact_coverage_and_source_immutability(self):
        page = dict(page=1, params=dict(dpi=150), elements=[run('a', 'Alpha beta', [10, 10, 80, 20]),
                    run('b', '7', [10, 100, 20, 110])], region_box_px=[0, 0, 200, 300])
        state = dict(source_pages=[page], copy_text='Alpha beta\n\n## Places the program is not sure of\n- none',
                     saved_conservation=dict(pages=[dict(page=1, copy_conservation=dict(excluded=[dict(id='b', reason='folio')]))]),
                     pages=[page])
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp); source=root/'source'; source.mkdir(); (source/'main-text.json').write_text('{}')
            (source/'page-01.json').write_text(json.dumps(page)); pdf=root/'paper.pdf'; pdf.touch()
            before=(source/'page-01.json').read_bytes()
            with patch.object(e, 'snapshot', return_value=state), patch.object(e.conserve, 'page_geometry',
                return_value={1:dict(media=[0,0,96,144],width=96,height=144,rotation=0)}), \
                patch.object(e, 'render_page', return_value=(root/'image.png',(147,220))), \
                patch.object(e.subprocess, 'run') as process:
                process.return_value.stdout='Alpha beta 7'
                document, audit=e.export(source,pdf,root/'output')
            self.assertEqual(audit['decoded_source_words']['missing'], {})
            self.assertEqual(audit['pdf_text_layer_words']['extra'], {})
            self.assertEqual(len(document['pages'][0]['lines']),2)
            self.assertEqual(document['pages'][0]['lines'][1]['program_role'],'furniture')
            self.assertEqual(before,(source/'page-01.json').read_bytes())
            self.assertEqual(sorted(source.iterdir()),sorted([source/'main-text.json',source/'page-01.json']))


if __name__ == '__main__': unittest.main()
