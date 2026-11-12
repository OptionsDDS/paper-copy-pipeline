"""Document float identity, independent pairing, crops and reader provenance."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('copy_floats',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def page(n=1):
    return dict(page=n,elements=[],blocks=[],floats=[],tables=[],art=[],unpaired=[],
                region_box_px=[0,0,300,400],params=dict(dpi=150))


def item(n=1,caption='Table 1. Measurements',kind='table',**kw):
    return dict(kind=kind,page=n,id='float:1',caption=caption,box=[20,30,250,300],
                rows=[[['Name'],['Value']],[['A'],['17']]],notes=[],**kw)


class FloatRecords(unittest.TestCase):
    def test_fifteen_pages_form_one_record_with_independent_gate_decisions(self):
        items=[item(n,caption='Table 1. Measurements' if n==3 else 'Table 1 (continued)',
                    table_source=dict(angle=90 if n==5 else 0,lines=[dict(text='A 17')])) for n in range(3,18)]
        items[-1]['notes']=['Note: values are counts.']
        decisions=[dict(page=n,id='float:1',caption=it['caption'],decision='grid' if n==3 else 'printed_lines')
                   for n,it in zip(range(3,18),items)]
        result,_=c.gather_floats(list(reversed(items)),[page(n) for n in range(3,18)],decisions)
        self.assertEqual(len(result['floats']),1)
        record=result['floats'][0]
        self.assertEqual(record['id'],'Table 1')
        self.assertEqual([p['page'] for p in record['parts']],list(range(3,18)))
        self.assertEqual(record['parts'][2]['angle'],90)
        self.assertEqual(record['caption'],'Table 1. Measurements')
        self.assertEqual(record['parts'][0]['table']['representation'],'grid')
        self.assertEqual(record['parts'][1]['table']['representation'],'gated_lines')
        self.assertEqual(record['notes'],[])
        self.assertEqual(record['parts'][-1]['unassigned_notes'][0]['text'],'Note: values are counts.')

    def test_figure_panels_and_continuations_share_identity(self):
        items=[item(1,'Fig. 3a. First panel.',kind='figure',graphic_box=[20,30,250,280]),
               item(2,'Figure 3B. Second panel.',kind='figure',graphic_box=[20,30,250,280])]
        result,_=c.gather_floats(items,[page(1),page(2)],[])
        record=result['floats'][0]
        self.assertEqual(len(result['floats']),1)
        self.assertEqual(record['id'],'Figure 3')
        self.assertEqual([p['panel'] for p in record['parts']],['A','B'])
        self.assertIn('Second panel.',record['caption'])

    def test_other_labels_supplements_and_roman_numbers_remain_distinct(self):
        for caption,want in [('Table IV. Results','Table IV'),('Box 2. Advice','Box 2'),
                             ('Scheme 1. Reaction','Scheme 1'),('Table S1. More','Table S1'),
                             ('Figure A1. Appendix','Figure A1'),('Table B2. Appendix','Table B2'),
                             ('Supplemental Table 1. More','Supplementary Table 1')]:
            self.assertEqual(c.float_label(caption)['id'],want)
        self.assertIsNone(c.float_label('Table of contents'))
        self.assertNotEqual(c.float_label('Table 1A')['id'],c.float_label('Table 1B')['id'])

    def test_captionless_tables_are_not_merged_by_kind_or_page(self):
        a=item(caption='Table (no caption on page 1)');b=dict(a,id='table:2',box=[20,310,250,380])
        result,_=c.gather_floats([a,b],[page()],[])
        self.assertEqual(len(result['floats']),2)
        self.assertEqual(len(result['check']['unpaired_floats']),2)

    def test_caption_only_record_is_flagged_until_another_page_supplies_content(self):
        a=item(caption='Figure 4. Image legend',kind='figure');a['rows']=[]
        result,_=c.gather_floats([a],[page()],[])
        self.assertEqual(result['check']['unpaired_captions'],['Figure 4'])
        b=dict(a,page=2,caption='Figure 4. Cont.',graphic_box=[20,30,250,280])
        result,_=c.gather_floats([a,b],[page(1),page(2)],[])
        self.assertTrue(result['check']['every_caption_has_float'])

    def test_independent_orphan_caption_is_retained_not_satisfied_by_other_float(self):
        p=page();p['unpaired']=[dict(kind='caption without a graphic on this page',
                                  caption='Figure 9. Missing image',box_px=[0,10,100,20],block='caption')]
        result,_=c.gather_floats([item()],[p],[])
        self.assertEqual(result['check']['unpaired_captions'],['Figure 9'])
        self.assertEqual(len(result['floats']),2)

    def test_isolated_appendix_label_pairs_one_graphic_without_widening_its_region(self):
        p=page();p['elements']=[dict(id='ink',kind='image',box_px=[20,30,250,180]),
            dict(id='label',kind='text',text='FIGURE A1',box_px=[20,190,100,205],angle=0),
            dict(id='description',kind='text',text='An appendix diagram.',box_px=[110,190,240,205],angle=0)]
        p['blocks']=[dict(id='graphic',members=['ink']),dict(id='caption',members=['label'])]
        p['unpaired']=[dict(kind='graphic without a caption on this page',block='graphic',box_px=[20,30,250,180])]
        catalog,_=c.gather_floats([],[p],[])
        record=catalog['floats'][0];part=record['parts'][0]
        self.assertEqual(record['id'],'Figure A1')
        self.assertEqual(record['caption'],'FIGURE A1 An appendix diagram.')
        self.assertEqual(record['check']['status'],'paired')
        self.assertEqual(part['box'],[20,30,250,180])
        self.assertTrue(part['crop_check']['accepted'])
        with tempfile.TemporaryDirectory() as directory,patch.object(c,'table_pdf_path',return_value=None):
            original='## FIGURE A1\n\nAn appendix diagram.\n\nFollowing prose.'
            text=c.render_float_files(original,[],[p],[],directory)
            self.assertLess(text.index('[Image unavailable:'),text.index('Following prose.'))
            self.assertEqual(text.count('An appendix diagram.'),1)

    def test_recovered_continuation_satisfies_rule_four_orphan(self):
        p=page();p['unpaired']=[dict(kind='caption without a graphic on this page',
                                  caption='Table 1 (continued)',box_px=[0,10,100,20],block='caption')]
        result,_=c.gather_floats([item(caption='Table 1 (continued)')],[p],[])
        self.assertEqual(len(result['floats']),1)
        self.assertTrue(result['check']['every_caption_has_float'])

    def test_earlier_orphan_caption_is_sorted_before_later_graphic(self):
        p=page();p['unpaired']=[dict(kind='caption without a graphic on this page',
                                  caption='Figure 4. First caption',box_px=[0,10,100,20],block='caption')]
        result,parts=c.gather_floats([item(2,'Figure 4. Cont.',kind='figure',graphic_box=[20,30,250,280])],[p,page(2)],[])
        self.assertEqual([p['page'] for p in result['floats'][0]['parts']],[1,2])
        self.assertEqual([p['page'] for r,p,it in parts],[1,2])

    def test_graphic_crop_excludes_caption_and_includes_lettering(self):
        p=page();p['elements']=[dict(id='image',kind='image',box_px=[20,30,200,150]),
            dict(id='caption',kind='text',box_px=[20,160,200,190]),
            dict(id='panel',kind='text',box_px=[20,25,30,35]),
            dict(id='body',kind='text',box_px=[20,200,200,300])]
        f=dict(box_px=[20,25,200,190],members=['image','caption','panel'],lettering=['panel'])
        self.assertEqual(c.float_graphic_box(p,f,['caption']),[20,25,200,150])

    def test_recovered_graphic_lettering_keeps_axes_in_the_owned_ink_hull(self):
        p=page();p['elements']=[dict(id='graph',kind='outline',box_px=[40,50,200,150]),
            dict(id='axis',kind='text',text='Values',box_px=[25,50,35,150]),
            dict(id='cap',kind='text',text='Figure 1. Results',box_px=[25,160,220,180])]
        ids=[];box=c.caption_graphic_region(p,[25,160,220,180],['cap'],ids)
        self.assertIn('axis',ids)
        it=item(kind='figure',caption='Figure 1. Results',graphic_box=box,graphic_run_ids=ids,caption_ids=['cap'])
        result,_=c.gather_floats([it],[p],[])
        part=result['floats'][0]['parts'][0]
        self.assertEqual(part['graphic_box'][0],25)
        self.assertTrue(part['crop_check']['accepted'])

    def test_graphic_region_covered_by_table_is_not_a_second_orphan(self):
        p=page();p['elements']=[dict(id='rule',kind='outline',box_px=[20,30,250,300])]
        p['unpaired']=[dict(kind='graphic without a caption on this page',box_px=[20,30,250,300],block='graphic')]
        result,_=c.gather_floats([item()],[p],[])
        self.assertEqual(len(result['floats']),1)

    def test_nested_printed_caption_id_is_recorded_without_guessing_its_graphic(self):
        p=page();p['elements']=[dict(id='a',kind='text',text='Figure 2. A plot.',region='caption1',box_px=[20,160,200,180]),
            dict(id='b',kind='text',text='Scheme 1. Reaction.',region='caption2',box_px=[20,190,200,210]),
            dict(id='c',kind='text',text='Second caption line.',region='caption2',box_px=[20,210,200,230]),
            dict(id='ink',kind='image',box_px=[20,30,200,150])]
        for e in p['elements']:e['angle']=0
        f=item(kind='figure',caption='Figure 2. A plot. Scheme 1. Reaction. Second caption line.',
               graphic_box=[20,30,200,150],caption_ids=['a','b','c'])
        catalog,_=c.gather_floats([f],[p],[])
        self.assertEqual([r['id'] for r in catalog['floats']],['Figure 2','Scheme 1'])
        self.assertEqual(catalog['check']['unpaired_captions'],['Scheme 1'])
        self.assertFalse(catalog['floats'][0]['parts'][0]['crop_check']['accepted'])
        self.assertEqual(catalog['floats'][1]['caption'],'Scheme 1. Reaction. Second caption line.')

    def test_wrapped_caption_references_are_not_nested_float_identifiers(self):
        for reference,region in [('Fig 2, with more details.', 'other'),
                                 ('Fig. 2D); another panel.', 'other'),
                                 ('Figure 2. The cited example.', 'caption')]:
            with self.subTest(reference=reference):
                p=page();p['elements']=[
                    dict(id='a',kind='text',text='Figure 4. Compare the example in',region='caption',box_px=[20,160,200,180]),
                    dict(id='b',kind='text',text=reference,region=region,box_px=[20,180,200,200]),
                    dict(id='ink',kind='image',box_px=[20,30,200,150])]
                f=item(kind='figure',caption='Figure 4. Compare the example in '+reference,
                       graphic_box=[20,30,200,150],caption_ids=['a','b'])
                catalog,_=c.gather_floats([f],[p],[])
                self.assertEqual([r['id'] for r in catalog['floats']],['Figure 4'])
                self.assertTrue(catalog['floats'][0]['parts'][0]['crop_check']['accepted'])


class ImageOutput(unittest.TestCase):
    def test_float_diagnostics_cannot_satisfy_source_token_conservation(self):
        p=page();p['unpaired']=[dict(kind='caption without a graphic on this page',
            caption='Figure 9. Detached legend.',box_px=[0,10,100,20],block='caption')]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'copy.md'
            path.write_text('Body words.\n\n## Places the program is not sure of\n- none\n')
            observed=[]
            def audit(folder,target):
                text=Path(target).read_text();observed.append(text)
                self.assertNotIn('Figure 9',text)
                Path(target).write_text(text.replace('- none','- source token not verified: "9"'))
                return target
            with patch.object(c,'conserve_pdf_copy',side_effect=audit),patch.object(c,'table_pdf_path',return_value=None):
                c.finalize_float_files(directory,str(path),[],[p],[])
            text=path.read_text()
            self.assertEqual(len(observed),1)
            self.assertIn('[Float check: Figure 9',text)
            self.assertIn('source token not verified: "9"',text)

    def test_unpaired_check_does_not_duplicate_a_caption_already_in_copy(self):
        caption='Figure 9. A complete legend already emitted in a side block.'
        p=page();p['unpaired']=[dict(kind='caption without a graphic on this page',
            caption=caption,box_px=[0,10,100,20],block='caption')]
        with tempfile.TemporaryDirectory() as directory,patch.object(c,'table_pdf_path',return_value=None):
            text=c.render_float_files('> '+caption,[],[p],[],directory)
            self.assertEqual(text.count(caption),1)
            self.assertIn('[Float check: Figure 9',text)

    def test_unclaimed_crossing_graphics_cannot_make_a_partial_crop_look_complete(self):
        p=page();p['elements']=[dict(id='left',kind='image',box_px=[20,30,100,100]),
            dict(id='right',kind='image',box_px=[200,30,280,100])]
        f=item(kind='figure',caption='Figure 1. Panels',graphic_box=[20,30,250,100])
        result,_=c.gather_floats([f],[p],[])
        part=result['floats'][0]['parts'][0]
        self.assertFalse(part['crop_check']['accepted'])
        self.assertEqual(part['crop_check']['unresolved_crossing_objects'],['elements:right'])

    def test_failed_crop_is_flagged_without_a_false_file_link(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(c,'table_pdf_path',return_value=None):
            f=item(kind='figure',caption='Figure 1. Test',graphic_box=[20,30,100,100])
            marker=c.float_marker(f,0)
            text=c.render_float_files('**Figure 1. Test**\n'+marker,[f],[page()],[],directory)
            self.assertIn('Image unavailable',text)
            self.assertNotIn('Image file:',text)
            data=json.loads((Path(directory)/'copy.floats.json').read_text())
            self.assertEqual(data['floats'][0]['parts'][0]['image']['status'],'failed')

    def test_multipage_crops_are_real_200dpi_pngs_and_old_assets_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);pdf=root/'paper.pdf'
            # Minimal two-page PDF, with a solid rectangular illustration.
            objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 144 192] /Contents 5 0 R >>',
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 144 192] /Rotate 90 /Contents 5 0 R >>']
            stream=b'1 0 0 rg 10 40 100 120 re f\n';objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'endstream')
            data=b'%PDF-1.4\n';offsets=[]
            for n,obj in enumerate(objects,1):offsets.append(len(data));data+=str(n).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
            xref=len(data);data+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
            data+=f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode();pdf.write_bytes(data)
            items=[item(n,caption='Figure 1. Test',kind='figure',graphic_box=[20,30,200,150]) for n in (1,2)]
            pages=[page(1),page(2)]
            for p in pages:p['elements']=[dict(id='paint',kind='fill',box_px=[20,30,200,150])]
            markers=[c.float_marker(it,n) for n,it in enumerate(items)]
            with patch.dict(os.environ,{'COPY_PAPER_PDF':str(pdf)}):
                text=c.render_float_files('\n'.join(markers),items,pages,[],directory)
                self.assertIn('figures/figure-1.png (page 1)',text)
                self.assertIn('figures/figure-1-part2.png (page 2)',text)
                record=json.loads((root/'copy.floats.json').read_text())['floats'][0]
                for part in record['parts']:
                    self.assertEqual(part['image']['dpi'],200)
                    self.assertEqual(part['image']['width'],246 if part['page']==1 else 166)
                    self.assertEqual(part['image']['height'],166 if part['page']==1 else 246)
                c.render_float_files(markers[0],items[:1],pages[:1],[],directory)
                self.assertFalse((root/'figures/figure-1-part2.png').exists())
                # Separately captioned panels on one page share one PNG. The
                # second-page file is still part2, never part3.
                first=dict(items[0],caption='Figure 1A. First',box=[20,30,200,150])
                second=dict(items[0],id='float:2',caption='Figure 1B. Second',
                            box=[20,200,200,300],graphic_box=[20,200,200,300])
                pages[0]['elements'].append(dict(id='paint2',kind='fill',box_px=[20,200,200,300]))
                together=[first,second,items[1]]
                text=c.render_float_files('\n'.join(c.float_marker(it,n) for n,it in enumerate(together)),
                                          together,pages,[],directory)
                record=json.loads((root/'copy.floats.json').read_text())['floats'][0]
                self.assertEqual([p['image']['file'] for p in record['parts']],
                                 ['figures/figure-1.png']*2+['figures/figure-1-part2.png'])
                self.assertEqual(record['parts'][0]['image']['height'],366)
                self.assertEqual(len(list((root/'figures').glob('*.png'))),2)

    def test_same_page_panels_cannot_enclose_unowned_body_text(self):
        p=page();p['elements']=[dict(id='a',kind='fill',box_px=[20,30,200,100]),
            dict(id='b',kind='fill',box_px=[20,200,200,300]),
            dict(id='body',kind='text',text='A body paragraph.',box_px=[20,130,200,160])]
        first=item(kind='figure',caption='Figure 1A. First',graphic_box=[20,30,200,100])
        first['box']=[20,30,200,110]
        second=dict(first,id='float:2',caption='Figure 1B. Second',box=[20,190,200,300],graphic_box=[20,200,200,300])
        catalog,_=c.gather_floats([first,second],[p],[])
        group=c.float_page_images(catalog['floats'][0],p)
        self.assertFalse(group['crop_check']['accepted'])
        self.assertEqual(group['crop_check']['between_panel_text'],['body'])

    def test_reader_acceptance_requires_current_copy_and_updates_one_matching_part(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'COPY_READERS_DIR':''}):
            root=Path(directory);text='A checked copy\n';(root/'copy.md').write_text(text)
            items=[item(1),item(2,'Table 1 (continued)')]
            catalog,_=c.gather_floats(items,[page(1),page(2)],[])
            for r in catalog['floats']:
                for part in r['parts']:part.pop('marker')
            (root/'copy.floats.json').write_text(json.dumps(catalog))
            log=dict(output_sha256=c.hashlib.sha256(text.encode()).hexdigest(),tables=[dict(page=1,caption=items[0]['caption'],accepted=True)])
            (root/'copy.agree.json').write_text(json.dumps(log))
            c.finish_float_copy(directory,str(root/'copy.md'))
            parts=json.loads((root/'copy.floats.json').read_text())['floats'][0]['parts']
            self.assertTrue(parts[0]['table']['reader_verified'])
            self.assertFalse(parts[1]['table']['reader_verified'])
            (root/'copy.floats.json').write_text(json.dumps(catalog));(root/'copy.md').write_text('Changed')
            c.finish_float_copy(directory,str(root/'copy.md'))
            self.assertFalse(json.loads((root/'copy.floats.json').read_text())['floats'][0]['parts'][0]['table']['reader_verified'])

    def test_reader_environment_applies_real_agreement_before_recording_provenance(self):
        # The same keyless printed-line fixture as test_agree.Integration,
        # exercised through the copy pipeline's environment entry point.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);readers=root/'readers';pdf=root/'paper.pdf';pdf.write_bytes(b'pdf fixture')
            text='**Table 1. Measurements**\n\n[table structure not recovered: 3 printed lines follow as printed, left to right, top to bottom]\n\n- Name Value\n- A 1\n- B 2\n\nBody stays.\n<!-- end of page 1 -->\n'
            (root/'copy.md').write_text(text)
            for model in ('mineru2.5-pro-2605','ovisocr2'):
                d=readers/model;d.mkdir(parents=True)
                (d/'p001.json').write_text('{"finish_reason":"stop"}')
                (d/'p001.md').write_text('Table 1. Measurements\n\n<table><tr><td>Name</td><td>Value</td></tr><tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr></table>')
            catalog,_=c.gather_floats([item()],[page()],[])
            (root/'copy.floats.json').write_text(json.dumps(catalog))
            with patch.dict(os.environ,{'COPY_READERS_DIR':str(readers),'COPY_PAPER_PDF':str(pdf)}):
                c.finish_float_copy(directory,str(root/'copy.md'))
            after=(root/'copy.md').read_text();self.assertIn('| A | 1 |',after)
            self.assertIn('Body stays.',after)
            table=json.loads((root/'copy.floats.json').read_text())['floats'][0]['parts'][0]['table']
            self.assertTrue(table['reader_verified'])
            self.assertEqual(table['agreement_output_sha256'],c.hashlib.sha256(after.encode()).hexdigest())
            self.assertEqual((root/'copy.agree-before.md').read_text(),text)


class PortWitnesses(unittest.TestCase):
    """Keyless ports: witness.py F-007/F-008; emission.py C-041/043/044;
    caption_roles.py D-586/588; float_extent.py D-525.
    """
    def glyph(self,text='x',box=(11,9,16,19)):
        return dict(text=text,box_px=list(box))

    def test_c041_centres_not_hulls_and_nonink(self):
        box=[10,10,20,20]
        self.assertTrue(c.float_note_centres([self.glyph()],box)['accepted'])
        result=c.float_note_centres([self.glyph(box=(18,9,23,19))],box)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['outside'][0]['outside_distances_px'],[0,0,.5,0])
        self.assertTrue(c.float_note_centres([self.glyph(),self.glyph(' ',(0,0,5,5))],box)['accepted'])
        for glyph in [self.glyph(' '),self.glyph('\u200b'),self.glyph(box=(11,9,11,19))]:
            self.assertFalse(c.float_note_centres([glyph],box)['accepted'])

    def test_strict_crossings_all_edges_no_absorption_or_growth(self):
        for box,side in [([5,20,20,30],'left'),([20,5,30,20],'top'),
                         ([90,20,105,30],'right'),([20,90,30,105],'bottom')]:
            p=page();p['elements']=[dict(id='cross',kind='image',box_px=box)]
            it=item(kind='figure',caption='Figure 1',graphic_box=[10,10,100,100]);it['box']=[10,10,100,100]
            result,_=c.gather_floats([it],[p],[]);part=result['floats'][0]['parts'][0]
            self.assertEqual(part['box'],[10,10,100,100])
            self.assertEqual(part['objects'][0]['edge_crossings'][0]['side'],side)
            self.assertEqual(part['objects'][0]['assignment']['role'],'unassigned')
            self.assertEqual(part['accounting']['unaccounted'],0)
        self.assertFalse(c.float_edge_crossings([10,10,100,100],[10,10,100,100]))

    def test_multiple_part_owners_fail_closed(self):
        p=page();p['elements']=[dict(id='img',kind='image',box_px=[30,40,50,60])]
        result,_=c.gather_floats([item(),item(caption='Table 2')],[p],[])
        self.assertEqual(len(result['check']['ownership_conflicts']),1)
        self.assertTrue(all(f['parts'][0]['objects'][0]['assignment']['role']=='unassigned' for f in result['floats']))

    def test_journal_art_ids_are_not_element_ids(self):
        p=page();p['elements']=[dict(id='same',kind='image',box_px=[30,40,50,60])]
        p['art']=[dict(id='same',kind='image',box_px=[70,40,90,60])]
        result,_=c.gather_floats([item()],[p],[])
        objects=result['floats'][0]['parts'][0]['objects']
        self.assertEqual(len({o['id'] for o in objects}),2)
        self.assertEqual(objects[1]['assignment']['role'],'unassigned')

    def test_crops_use_containment_and_catch_missing_axis_ink(self):
        self.assertFalse(c.float_crop_check(dict(objects=[]),[0,0,200,200])['accepted'])
        part=dict(objects=[dict(id='axis',box=[10,20,20,90],edge_crossings=[],
                                assignment=dict(role='structure'))])
        self.assertTrue(c.float_crop_check(part,[0,0,200,200])['accepted'])
        result=c.float_crop_check(part,[15,0,200,200])
        self.assertFalse(result['accepted']);self.assertEqual(result['missing_owned_objects'],['axis'])

    def test_crop_coordinates_follow_rotated_and_shifted_cropbox(self):
        # Native units are 72 dpi here; all four rotations cover the same
        # entire displayed page after the explicit coordinate transform.
        crop=[10,20,110,220]
        for angle in (0,90,180,270):
            width,height=(200,100) if angle%180 else (100,200)
            native=[10,height-220,110,height-20]
            actual=c.float_render_transform(native,72,height,crop,angle)
            expected=[0,0,width*200/72,height*200/72]
            for a,b in zip(actual,expected):self.assertAlmostEqual(a,b)

    def test_page_clipping_retains_visible_ink_without_changing_float_box(self):
        p=page();p['elements']=[dict(id='image',kind='image',box_px=[20,30,100,450])]
        it=item(kind='figure',caption='Figure 1',graphic_box=[20,30,100,450]);it['box']=[20,30,100,450]
        result,_=c.gather_floats([it],[p],[]);part=result['floats'][0]['parts'][0]
        self.assertEqual(part['box'],[20,30,100,450])
        self.assertEqual(part['objects'][0]['box'],[20,30,100,400])
        self.assertTrue(c.float_crop_check(part,[20,30,100,400])['accepted'])

    def test_d588_seven_windows_and_rotation(self):
        # D-588 reports seven strips on six parts; two strips on the Table 3
        # end carry the same direction. These fixtures need no protected map.
        for text,field,position in [('Continues','continues_forward','end'),
            ('(Continued)','continued_from','start'),('(Continues)','continues_forward','end'),
            ('(Continues)','continues_forward','end'),('(Continued)','continued_from','start'),
            ('(Continues)','continues_forward','end'),('(Continued)','continued_from','start')]:
            self.assertEqual(c.float_direction(text),(field,position))
            for angle in (0,90,180,270):
                box=[10,20,90,100];window=box.copy()
                self.assertTrue(c.float_at_edge(window,box,angle,position))
                self.assertFalse(c.float_at_edge([11,21,89,99],box,angle,position))
        self.assertEqual(c.float_direction('The effect continues in both groups.'),(None,None))

    def test_direction_needs_start_or_end_and_joins_unlabelled_part(self):
        p=page();q=page(2)
        p['elements']=[dict(id='cap',kind='text',text='Table 1. Results',box_px=[20,30,200,40]),
                       dict(id='end',kind='text',text='(Continues)',box_px=[30,280,100,295])]
        q['elements']=[dict(id='start',kind='text',text='(Continued)',box_px=[20,30,100,40])]
        a=item(caption_ids=['cap'],table_source=dict(lines=[dict(text='(Continues)',items=[dict(id='end',box=[30,280,100,295])])]))
        b=item(2,caption='Table (no caption on page 2)',caption_ids=['start'])
        result,_=c.gather_floats([a,b],[p,q],[])
        self.assertEqual(len(result['floats']),1)
        parts=result['floats'][0]['parts'];self.assertTrue(parts[0]['continues_forward']);self.assertTrue(parts[1]['continued_from'])
        p['elements'].append(dict(id='later',kind='text',text='another cell',box_px=[30,296,100,300]))
        a['table_source']['lines'].append(dict(text='another cell',items=[dict(id='later',box=[30,296,100,300])]))
        self.assertFalse(c.float_directions(a,p)[0]['accepted'])

    def test_direction_chain_propagates_one_label_without_guessing_a_merge(self):
        items=[];pages=[]
        for n in range(1,5):
            p=page(n);p['elements']=[dict(id='s',kind='text',text='(Continued)',box_px=[20,30,100,40]),
                                    dict(id='e',kind='text',text='(Continues)',box_px=[20,290,100,300])]
            it=item(n,caption='Table 7. Results' if n==1 else f'Table (no caption on page {n})',
                    table_source=dict(owned_run_ids=['s','e'],lines=[]))
            items.append(it);pages.append(p)
        result,_=c.gather_floats(items,pages,[])
        self.assertEqual([(r['id'],len(r['parts'])) for r in result['floats']],[('Table 7',4)])
        # Two printed labels disagree across the chain: no anonymous middle
        # part is silently assigned to either table.
        for it in items:it.pop('_float_join_label',None);it.pop('_float_join_witness',None)
        items[-1]['caption']='Table 8. Results'
        result,_=c.gather_floats(items,pages,[])
        self.assertEqual(len(result['floats']),4)

    def test_c043_overlap_and_c041_other_owner_rejected(self):
        p=page();run=dict(id='n',kind='text',text='Note: x',box_px=[20,40,80,50],
                         _chars=[dict(text='x',x0=20,y0=40,x1=80,y1=50)])
        p['elements']=[run]
        it=item(table_source=dict(lines=[dict(text='Note: x',items=[dict(id='n',box=[20,40,80,50])])]))
        it['notes']=['Note: x'];roles,checks=c.float_segregate(it,p)
        self.assertEqual(roles['n'],'note')
        it['notes']*=2;roles,checks=c.float_segregate(it,p)
        self.assertEqual(roles['n'],'note');self.assertEqual(checks[0]['duplicate_count'],2)
        other=dict(run,id='n2',text='Note: y')
        p['elements'].append(other)
        it['notes']=['Note: x','Note: y']
        it['table_source']['lines'].append(dict(text='Note: y',items=[dict(id='n2',box=[20,40,80,50])]))
        roles,checks=c.float_segregate(it,p)
        self.assertFalse(roles);self.assertTrue(all(r['outcome']=='flagged' for r in checks))
        it['notes']=['Note: x'];it['caption_ids']=['n'];roles,checks=c.float_segregate(it,p)
        self.assertEqual(roles['n'],'caption');self.assertEqual(checks[0]['reason'],'note line is owned by a caption')


if __name__=='__main__':unittest.main()
