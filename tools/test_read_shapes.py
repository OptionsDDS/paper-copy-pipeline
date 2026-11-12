"""Standard-library checks for OCR geometry, failure isolation and the copy hook.

Run: /usr/bin/python3 -I tools/test_read_shapes.py
These checks do not assert OCR accuracy or performance; those need live crops.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ocr = module('read_shapes', ROOT / 'tools/read_shapes.py')
copy = module('copy_paper', ROOT / 'copy_paper.py')
signs = module('read_signs', ROOT / 'tools/read_signs.py')


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.pdf = self.folder / 'paper.pdf'
        self.pdf.touch()
        self.path = self.folder / 'page-01.json'
        self.page = dict(page=1, params={'dpi': 150}, elements=[
            dict(id='outline:1', kind='outline', count=4, box_px=[10, 20, 40, 30]),
            dict(id='outline:2', kind='outline', count=3, box_px=[10, 35, 40, 45]),
            dict(id='text:1', kind='text', text='Native text', angle=0, box_px=[1, 1, 9, 10]),
        ], floats=[dict(id='float:1', caption='TABLE 1', box_px=[0, 0, 100, 100], blocks=[])])
        self.raw = json.dumps(self.page, separators=(',', ':')).encode()
        self.path.write_bytes(self.raw)

    def collect(self):
        return ocr.collect([(self.folder, self.pdf)], 2)

    def save(self):
        self.raw = json.dumps(self.page, separators=(',', ':')).encode()
        self.path.write_bytes(self.raw)

    def test_crop_frame_margin_and_origin(self):
        self.assertEqual(ocr.crop_rectangle([10.25, 20.25, 40.25, 30.25], 150), (18, 38, 65, 25))
        self.assertEqual(ocr.crop_rectangle([0, 0, 3, 4], 300), (0, 0, 5, 6))
        with self.assertRaises(ValueError):
            ocr.crop_rectangle([0, 0, float('nan'), 4], 150)
        with self.assertRaises(ValueError):
            ocr.crop_rectangle([4, 0, 3, 4], 150)
        with self.assertRaises(ValueError):
            ocr.crop_rectangle([0, 0, 3, 4], 300, margin=3)

    def test_renderer_uses_page_pixel_coordinates(self):
        _, records = self.collect()
        with patch.object(ocr.subprocess, 'run') as run:
            ocr.render_crop(records[0], self.folder / 'crop')
        args = run.call_args.args[0]
        for key, value in (('-r', '300'), ('-f', '1'), ('-l', '1'), ('-x', '18'), ('-y', '38'), ('-W', '64'), ('-H', '24')):
            self.assertEqual(args[args.index(key) + 1], value)

    def test_all_outlines_collected_without_table_membership(self):
        self.page['floats'] = []
        self.save()
        _, records = self.collect()
        self.assertEqual([r['id'] for r in records], ['outline:1', 'outline:2'])
        self.assertEqual([r['status'] for r in records], ['skipped', 'skipped'])
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_success_adds_only_ocr_fields_failed_crop_untouched(self):
        pages, records = self.collect()
        results = [dict(file=str(self.path), index=0, status='read', text='Test label', model='local-model', ocr_conf=80),
                   dict(file=str(self.path), index=1, status='error', reason='empty crop')]
        self.assertEqual(ocr.apply_results(pages, records, results), 1)
        actual = json.loads(self.path.read_text())
        expected = json.loads(self.raw)
        expected['elements'][0].update(ocr_text='Test label', ocr_model='local-model', ocr_conf=80)
        self.assertEqual(actual, expected)
        _, again = self.collect()
        self.assertEqual([r['status'] for r in again], ['existing', 'pending'])

    def test_failed_and_empty_results_do_not_rewrite_json(self):
        pages, records = self.collect()
        results = [dict(file=str(self.path), index=0, status='read', text='  ', model='model'),
                   dict(file=str(self.path), index=1, status='error', reason='error')]
        self.assertEqual(ocr.apply_results(pages, records, results), 0)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_concurrent_edits_are_preserved(self):
        pages, records = self.collect()
        self.path.write_bytes(self.raw + b'\n')
        with self.assertRaisesRegex(ValueError, 'changed during OCR'):
            ocr.apply_results(pages, records, [dict(file=str(self.path), index=0, status='read', text='x', model='model')])
        self.assertEqual(self.path.read_bytes(), self.raw + b'\n')

    def test_missing_runtime_cli_is_soft_and_reports_every_outline(self):
        report = self.folder / 'report.json'
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'tools/read_shapes.py'),
                                 str(self.folder), str(self.pdf), '--python', str(self.folder / 'absent-python'),
                                 '--model', str(self.folder), '--tesseract', str(self.folder / 'absent-tesseract'),
                                 '--report', str(report)], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.path.read_bytes(), self.raw)
        data = json.loads(report.read_text())
        self.assertEqual(data['statuses'], {'no_backend': 2})
        self.assertEqual(data['changed_pages'], 0)
        self.assertFalse(list(self.folder.glob('.read-shapes-*')))

    def test_bad_page_does_not_change_previous_pages(self):
        (self.folder / 'page-02.json').write_text('{')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_copy_hook_marks_ocr_and_keeps_unreadable_warning(self):
        self.page['elements'][0]['ocr_text'] = ' Test\nlabel '
        self.page['elements'][0]['ocr_conf'] = 83.125
        members = [dict(box_px=[0, 0, 100, 100], angle=0)]
        runs, warning = copy.shape_text_runs(self.page, members)
        self.assertEqual(runs[0]['text'], 'Test label [ocr]')
        self.assertEqual(runs[1]['text'], '[unreadable:3-letters-drawn-as-shapes]')
        self.assertIn('1 label(s) read by OCR; lowest confidence 83.12/100; check them', warning)
        self.assertIn('1 label(s) are drawn as shapes', warning)
        self.assertEqual(runs[0]['box_px'], [10, 20, 40, 30])
        self.page['elements'][1]['ocr_text'] = 'Second label'
        self.assertIn('confidence unavailable for 1 label(s)', copy.shape_text_runs(self.page, members)[1])
        self.page['elements'][1]['ocr_conf'] = 75
        self.assertEqual(copy.shape_text_runs(self.page, members)[1],
                         '2 label(s) read by OCR; lowest confidence 75.00/100; check them')

    def test_copy_hook_without_ocr_is_unchanged_and_ignores_outside(self):
        members = [dict(box_px=[0, 0, 100, 33], angle=0)]
        runs, warning = copy.shape_text_runs(self.page, members)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['text'], '[unreadable:4-letters-drawn-as-shapes]')
        self.assertEqual(warning, '1 label(s) are drawn as shapes, not text, and could not be read; they are marked [unreadable] in their cells')

    def test_fragments_join_but_neighboring_lines_and_cells_do_not(self):
        self.page['elements'][1]['box_px'] = [40.75, 23, 48, 33]
        self.page['elements'].extend([
            dict(id='outline:3', kind='outline', box_px=[12, 22, 15, 27]),
            dict(id='outline:4', kind='outline', box_px=[10, 35, 40, 45]),
            dict(id='outline:5', kind='outline', box_px=[65, 20, 90, 30]),
        ])
        self.save()
        _, records = self.collect()
        self.assertEqual(records[0]['ocr_box_px'], [10, 20, 48, 33])
        self.assertEqual(records[0]['joined_indices'], [1, 3])
        self.assertEqual([r['status'] for r in records], ['pending', 'fragment', 'fragment', 'pending', 'pending'])
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_adjacent_fragments_in_different_floats_do_not_join(self):
        self.page['elements'][1]['box_px'] = [41, 20, 51, 30]
        self.page['floats'][0]['box_px'] = [0, 0, 40, 100]
        self.page['floats'].append(dict(id='float:2', caption='Table 2', box_px=[41, 0, 100, 100]))
        self.save()
        _, records = self.collect()
        self.assertEqual([r['status'] for r in records], ['pending', 'pending'])
        self.assertTrue(all(not r['joined_indices'] for r in records))

    def test_join_only_committed_after_success_and_rerun_is_stable(self):
        self.page['elements'][1]['box_px'] = [38, 20, 48, 30]
        self.save()
        pages, records = self.collect()
        ocr.apply_results(pages, records, [dict(file=str(self.path), index=0, status='error', reason='empty')])
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(records[1]['status'], 'unavailable')
        pages, records = self.collect()
        result = dict(file=str(self.path), index=0, status='read', text='Complete', model='test', ocr_conf=89)
        ocr.apply_results(pages, records, [result])
        actual = json.loads(self.path.read_text())
        self.assertEqual(actual['elements'][0]['box_px'], [10, 20, 40, 30])
        self.assertEqual(actual['elements'][0]['ocr_box_px'], [10, 20, 48, 30])
        self.assertEqual(actual['elements'][1]['ocr_joined_to'], 'outline:1')
        self.assertEqual([r['status'] for r in self.collect()[1]], ['existing', 'joined'])
        runs, warning = copy.shape_text_runs(actual, [dict(box_px=[0, 0, 100, 100], angle=0)])
        self.assertEqual([r['text'] for r in runs], ['Complete [ocr]'])
        self.assertEqual(runs[0]['box_px'], [10, 20, 48, 30])
        self.assertIn('1 label(s) read by OCR', warning)

    def test_native_boxes_masked_including_raster_whitespace_at_origin(self):
        path = self.folder / 'crop.ppm'
        # First pixel starts with a whitespace byte; never strip raster bytes.
        pixels = bytes([10, 20, 30]) * 16
        header = b'P6\n4 4\n255\n'
        path.write_bytes(header + pixels)
        task = dict(crop_xywh=[10, 20, 4, 4], boxer_dpi=300,
                    mask_boxes_px=[[11, 21, 13, 23], [20, 20, 21, 21]])
        ocr.mask_native_text(path, task)
        actual = path.read_bytes()[len(header):]
        for y in range(4):
            for x in range(4):
                self.assertEqual(actual[(y*4+x)*3:(y*4+x+1)*3],
                                 b'\xff\xff\xff' if 1 <= x < 3 and 1 <= y < 3 else bytes([10, 20, 30]))

    def test_collect_masks_native_text_only_where_crop_intersects(self):
        self.page['elements'][2]['box_px'] = [40.8, 20, 50, 24]
        self.save()
        _, records = self.collect()
        self.assertEqual(records[0]['mask_boxes_px'], [[40.8, 20, 50, 24]])
        self.assertEqual(records[1]['mask_boxes_px'], [])

    def test_tsv_uses_minimum_nonempty_word_confidence(self):
        tsv = 'level\tconf\ttext\n1\t-1\t\n5\t96.5\tTwo\n5\t82.25\twords\n5\t-1\t \n'
        self.assertEqual(ocr.parse_tsv(tsv), ('Two words', 82.25))
        for invalid in ('', 'level\tconf\ttext\n5\tnan\tword\n', 'level\tconf\ttext\n5\t-1\tword\n'):
            with self.assertRaises(ValueError):
                ocr.parse_tsv(invalid)

    def test_tesseract_subprocess_uses_tsv_psm7_and_cleans_crop(self):
        binary = self.folder / 'tesseract'
        binary.touch()
        (self.folder / 'eng.traineddata').touch()
        crop = self.folder / 'crop.ppm'
        crop.touch()
        _, records = self.collect()
        reply = subprocess.CompletedProcess([], 0, 'level\tconf\ttext\n5\t92.75\tLabel\n', '')
        with patch.object(ocr, 'render_crop', return_value=crop), patch.object(ocr.subprocess, 'run', return_value=reply) as run:
            results, _ = ocr.run_tesseract(records[:1], self.folder, binary, self.folder, self.folder)
        self.assertEqual(results[0]['ocr_conf'], 92.75)
        self.assertEqual(run.call_args.args[0][-4:], ['--psm', '7', '-c', 'tessedit_create_tsv=1'])
        self.assertIn(str(self.folder), run.call_args.kwargs['env']['LD_LIBRARY_PATH'])
        self.assertFalse(crop.exists())

    def test_missing_tesseract_data_is_soft(self):
        binary = self.folder / 'tesseract'
        binary.touch()
        results, attempts = ocr.run_tesseract([], self.folder, binary, self.folder, self.folder)
        self.assertEqual(results, [])
        self.assertIn('missing', attempts[0]['error'])

    def test_only_failed_tesseract_labels_reach_model_fallback(self):
        _, records = self.collect()
        success = dict(file=str(self.path), index=0, status='read', text='First', model='tesseract', ocr_conf=93)
        failure = dict(file=str(self.path), index=1, status='error', reason='empty')
        fallback = dict(file=str(self.path), index=1, status='read', text='Second', model='glm')
        with patch.object(ocr, 'run_tesseract', return_value=([success, failure], [{'backend':'tesseract'}])), \
                patch.object(ocr, 'run_worker', return_value=([fallback], [{'backend':'glm'}])) as worker:
            results, attempts = ocr.run_backends(records, [], self.folder)
        self.assertEqual([t['index'] for t in worker.call_args.args[0]], [1])
        self.assertEqual(results, [success, fallback])
        self.assertEqual([a['backend'] for a in attempts], ['tesseract', 'glm'])

    def test_successful_tesseract_does_not_start_models(self):
        _, records = self.collect()
        result = dict(file=str(self.path), index=0, status='read', text='First', model='tesseract', ocr_conf=93)
        with patch.object(ocr, 'run_tesseract', return_value=([result], [])), patch.object(ocr, 'run_worker') as worker:
            ocr.run_backends(records[:1], [], self.folder)
        worker.assert_not_called()

    def test_model_fallback_preserves_partial_reads_and_retries_failures(self):
        _, records = self.collect()
        python = self.folder / 'python'
        python.touch()
        inventories = []
        def reply(command, **kwargs):
            request = json.loads(Path(command[-1]).read_text())
            inventories.append((request['backend'], [t['index'] for t in request['tasks']]))
            results = []
            for task in request['tasks']:
                result = dict(file=task['file'], index=task['index'])
                if request['backend'] == 'glm' and task['index'] == 1:
                    result.update(status='error', reason='unreadable')
                else:
                    result.update(status='read', text='Label', model=request['backend'])
                results.append(result)
            Path(request['output']).write_text(json.dumps(dict(results=results)))
            return subprocess.CompletedProcess(command, 0, '', '')
        with patch.object(ocr.subprocess, 'run', side_effect=reply):
            results, _ = ocr.run_worker(records, [('glm', python, self.folder), ('paddle', python, self.folder)], self.folder)
        self.assertEqual(inventories, [('glm', [0, 1]), ('paddle', [1])])
        self.assertEqual([r['model'] for r in results], ['glm', 'paddle'])

    def test_failed_tesseract_process_leaves_page_and_cleans_crop(self):
        binary = self.folder / 'tesseract'
        binary.touch()
        (self.folder / 'eng.traineddata').touch()
        crop = self.folder / 'crop.ppm'
        crop.touch()
        _, records = self.collect()
        with patch.object(ocr, 'render_crop', return_value=crop), \
                patch.object(ocr.subprocess, 'run', side_effect=subprocess.TimeoutExpired('tesseract', 30)):
            results, _ = ocr.run_tesseract(records[:1], self.folder, binary, self.folder, self.folder)
        self.assertEqual(results[0]['status'], 'error')
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertFalse(crop.exists())

    def test_copy_attaches_native_punctuation_suffix_once(self):
        self.page['elements'][0].update(ocr_text='ABC', ocr_conf=95)
        suffix = dict(id='text:2', kind='text', text='+/DEF', box_px=[41, 20, 65, 30], angle=0)
        ordinary = dict(id='text:3', kind='text', text='Neighbor', box_px=[41, 35, 75, 45], angle=0)
        members = [dict(box_px=[0, 0, 100, 100], angle=0), suffix, ordinary]
        runs, _ = copy.shape_text_runs(self.page, members)
        self.assertEqual(runs[0]['text'], 'ABC+/DEF [ocr]')
        self.assertNotIn(suffix, members)
        self.assertIn(ordinary, members)

    def test_invalid_confidence_does_not_write(self):
        pages, records = self.collect()
        ocr.apply_results(pages, records, [dict(file=str(self.path), index=0, status='read', text='x', model='test', ocr_conf=float('nan'))])
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_figure_float_with_table_members_is_still_skipped(self):
        self.page['tables'] = [dict(id='table:1')]
        self.page['floats'][0].update(caption='Figure 1', blocks=['table:1'])
        self.save()
        self.assertEqual([r['status'] for r in self.collect()[1]], ['skipped', 'skipped'])


class SignTests(unittest.TestCase):
    def test_only_unknown_positions_change_despite_unrelated_ocr_errors(self):
        text = 'score = �8.63 cm; 42% XY'
        subs = signs.align(text, [('score', 98), ('=', 99), ('—8.63', 84), ('cm;', 95), ('42%', 91), ('XV', 20)])
        self.assertEqual([(s['offset'],s['after'],s['confidence']) for s in subs], [(8,'−',84)])
        self.assertEqual(signs.align('8.63 cm', [('8.61',99),('cm',99)]), [])
        self.assertEqual(signs.align('�8.63 cm', [('—7.63',99),('cm',99)]), [])

    def test_multiple_signs_whitespace_and_word_confidences(self):
        subs = signs.align('�7.4 � 8.2', [('—7.4',87),('±',75),('8.2',98)])
        self.assertEqual([(s['offset'],s['after']) for s in subs], [(0,'−'),(5,'±')])
        self.assertEqual(min(s['confidence'] for s in subs),75)
        self.assertEqual(signs.align('x � 2', [('x',99),('=',59),('2',99)]), [])
        self.assertEqual(signs.align('all �', [('all',99),('!',99)]), [])

    def test_letters_require_complete_anchored_word_and_high_confidence(self):
        self.assertEqual(signs.align('�ZX', [('wZX',99)]), [])
        self.assertEqual(signs.align('�m', [('pm',99)]), [])
        self.assertEqual(signs.align('���', [('cat',99)]), [])
        self.assertEqual(signs.align('hel�o', [('hello',94)]), [])
        self.assertEqual(signs.align('hel�o', [('hallo',99)]), [])
        self.assertEqual(signs.align('hel�o', [('hello',98)])[0]['after'],'l')
        self.assertEqual(signs.align('�ZX', [('μZX',92)])[0]['after'],'µ')

    def test_no_filling_deleted_or_ambiguous_unknowns(self):
        self.assertEqual(signs.align('�1.2', [('1.2',99)]), [])
        self.assertEqual(signs.align('�1.2', [('—-1.2',99)]), [])
        self.assertEqual(signs.align('�', [('+',99)]), [])

    def test_tsv_keeps_each_word_confidence_and_rejects_nan(self):
        tsv='level\tconf\ttext\n1\t-1\t\n5\t92\t−2\n5\t45\tword\n'
        self.assertEqual(signs.tsv_words(tsv), [('−2',92),('word',45)])
        with self.assertRaises(ValueError): signs.tsv_words('level\tconf\ttext\n5\tnan\tx\n')

    def test_shifted_page_origin_and_quarter_turns(self):
        class Page: rotate=0
        class Doc:
            pages=[Page()]
            def page_size(self, page):return 600,800,(15,20,615,820)
        doc=Doc()
        transform,angle=signs.page_transform(doc,1,144)
        self.assertEqual(transform([60,80,100,100]),[30,120,70,140])
        doc.pages[0].rotate=90
        transform,angle=signs.page_transform(doc,1,144)
        self.assertEqual(angle,90)
        self.assertEqual(transform([60,80,100,100]),[1460,30,1480,70])

    def test_upright_raster_turns_preserve_pixels(self):
        pixels=b''.join(bytes([i,i,i]) for i in range(6))
        w,h,p=signs.upright(2,3,pixels,90)
        self.assertEqual((w,h),(3,2))
        self.assertEqual(list(p[::3]),[4,2,0,5,3,1])
        self.assertEqual(signs.upright(w,h,p,270),(2,3,pixels))

    @staticmethod
    def raster(rows):
        return len(rows[0]),len(rows),b''.join(b'\0\0\0' if ch=='#' else b'\xff\xff\xff' for row in rows for ch in row)

    def test_arithmetic_pixels_veto_plus_read_as_plus_minus(self):
        cases=[(['#######'],'−'),(['...#...','...#...','#######','...#...','...#...'],'+'),
               (['#######','.......','.......','#######'],'='),
               (['...#...','...#...','#######','...#...','...#...','.......','#######'],'±')]
        for rows,expected in cases:
            image=self.raster(rows);w,h,_=image
            self.assertEqual(signs.arithmetic_shape(image,[0,0,w,h],[0,0,w,h],300,0),expected)

    def test_copy_keeps_table_word_boxes_and_native_cache(self):
        chars=[dict(text=t,x0=i*10,y0=0,x1=i*10+8,y1=10) for i,t in enumerate('�2�3')]
        e=dict(id='run:1',kind='text',text='�2 �3',ocr_text='−2 −3',char_ids=[0,1,2,3],
               box_px=[0,0,38,10],_chars=chars,angle=0,
               ocr_subs=[dict(offset=0,after='−',char_id=0,confidence=90),dict(offset=3,after='−',char_id=2,confidence=80)])
        page=dict(page=2,elements=[e],_table_chars=chars)
        before=copy.table_words([e],page,copy.frame(0));warning=[]
        copy.sign_text_runs([page],warning)
        after=copy.table_words([e],page,copy.frame(0))
        self.assertEqual([b for b,t,r in before],[b for b,t,r in after])
        self.assertEqual([t for b,t,r in after],['−2','−3'])
        self.assertEqual(''.join(c['text'] for c in chars),'�2�3')
        self.assertIn('page 2: 2 signs read by OCR (−): check them; lowest confidence 80.00/100',warning)
        self.assertNotIn('[ocr]',e['text'])

    def test_copy_refuses_known_character_changes_and_bad_metadata(self):
        for new,subs in [('−3',[dict(offset=0,after='−',confidence=90)]),
                         ('−2',[dict(offset=1,after='−',confidence=90)]),
                         ('−2',[dict(offset=0,after='−',confidence=float('nan'))])]:
            e=dict(kind='text',text='�2',ocr_text=new,ocr_subs=subs)
            warnings=[];copy.sign_text_runs([dict(page=1,elements=[e])],warnings)
            self.assertEqual(e['text'],'�2');self.assertEqual(warnings,[])

    def test_failed_ocr_does_not_rewrite_page_and_detects_concurrent_edit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            path=Path(temp)/'page-01.json';raw=b'{"elements":[{"text":"x"}]}';path.write_bytes(raw)
            pages={str(path):(raw,json.loads(raw))};records=[dict(file=str(path),index=0,status='pending')]
            failure=dict(file=str(path),index=0,status='unresolved')
            self.assertEqual(signs.apply_results(pages,records,[failure]),0)
            self.assertEqual(path.read_bytes(),raw)
            success=dict(file=str(path),index=0,status='read',ocr_text='−',ocr_conf=90,
                         ocr_subs=[dict(offset=0,after='−')],ocr_model='test')
            path.write_bytes(raw+b'\n')
            with self.assertRaisesRegex(ValueError,'changed during sign OCR'):
                signs.apply_results(pages,records,[success])
            self.assertEqual(path.read_bytes(),raw+b'\n')

    def test_tesseract_failure_cleans_crop_and_leaves_source_intact(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            task=dict(file='page.json',index=0,page=1,pdf='paper.pdf',crop_xywh=[0,0,20,20],source='�2')
            with patch.object(signs.subprocess,'run',side_effect=subprocess.TimeoutExpired('pdftoppm',15)):
                result=signs.recognize(task,temp,Path('tesseract'),Path('data'),Path('libs'))
            self.assertEqual(result['status'],'error')
            self.assertNotIn('ocr_text',result)
            self.assertEqual(list(Path(temp).iterdir()),[])


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    unittest.main()
