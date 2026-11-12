"""Fixed-choice checker contracts, real pixels, truth accounting and CPU vLLM adapter."""
import argparse
import base64
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'checker'))
import common as c
import raster
import build_questions as build
import run_model as runner
import apply_decisions as applier
import prepare_benchmark as prep
import score


def fixture():
    pages = []
    for n in (1, 2):
        boxes = [dict(id=f'p{n}.b{i}', page=n, box=[10, 10 + i * 20, 90, 25 + i * 20],
                      lines=[f'p{n}.l{i}'], expected=['main header'] if n == 1 and i == 0 else ['body'],
                      header_role='title' if n == 1 and i == 0 else None) for i in range(3)]
        lines = [dict(id=f'p{n}.l{i}', page=n, box=b['box'], text=f'Source {i}') for i, b in enumerate(boxes)]
        pages.append(dict(page=n, width=100, height=100, image=f'pages/p{n}.png', boxes=boxes, lines=lines,
                          body_order=[b['id'] for b in boxes if b['expected'] == ['body']],
                          floats=[], captions=[]))
    document = dict(paper='sample', pages=pages)
    bundle = dict(version=1, document=document, questions=build.questions(document))
    bundle['bundle_sha256'] = c.digest(bundle)
    return bundle


def response(bundle, q, answer=None):
    if answer is None:
        answer = dict(answer=q['expected'][0] if q['expected'] else 'no' if q['type'] == 'Q3' else 'yes', confidence=.95)
        if q['type'] in ('Q3', 'Q5'):
            answer['regions'] = []
        if q['type'] == 'Q5':
            answer['affected'] = []
    return dict(question_id=q['id'], question_sha256=c.digest(q), bundle_sha256=bundle['bundle_sha256'], status='ok', answer=answer)


def materialize(root, bundle):
    b = copy.deepcopy(bundle)
    for p in b['document']['pages']:
        path = root / p['image']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raster.encode(100, 100, bytes([255, 255, 255]) * 10000))
        p['image_sha256'] = c.file_hash(path)
    b.pop('bundle_sha256', None); b['bundle_sha256'] = c.digest(b)
    c.save(root / 'bundle.json', b)
    return b


class Contracts(unittest.TestCase):
    def test_no_free_text_or_extra_keys(self):
        b = fixture()
        q = b['questions'][0]
        a = response(b, q)['answer']
        for invalid in [dict(a, text='replacement prose'), dict(a, answer='made up'), dict(a, confidence=float('nan')),
                        dict(a, confidence=True), dict(a, confidence=1.01)]:
            with self.assertRaises(ValueError): c.validate_answer(q, invalid)
        for raw in ['{"answer":"yes","answer":"no"}', '{"confidence":NaN}']:
            with self.assertRaises(ValueError): c.parse(raw)

    def test_completeness_yes_requires_real_region(self):
        q = next(q for q in fixture()['questions'] if q['type'] == 'Q3')
        c.validate_answer(q, dict(answer='yes', confidence=.9, regions=[[10, 20, 100, 200]]))
        for regions in [[], [[20, 20, 10, 100]], [[0, 0, 1001, 20]], [[True, 0, 10, 20]], [[0.1, 0, 10, 20]]]:
            with self.assertRaises(ValueError): c.validate_answer(q, dict(answer='yes', confidence=.9, regions=regions))
        with self.assertRaises(ValueError): c.validate_answer(q, dict(answer='no', confidence=.9, regions=[[0, 0, 10, 20]]))

    def test_float_choices_and_missing_detections(self):
        q = dict(type='Q5', choices=['f1', 'c1'])
        c.validate_answer(q, dict(answer='no', confidence=.9, affected=['f1'], regions=[]))
        c.validate_answer(q, dict(answer='no', confidence=.9, affected=['unboxed'], regions=[[1, 2, 10, 20]]))
        for ids, regions in [(['unknown'], []), (['f1', 'f1'], []), (['unboxed'], []), ([], [])]:
            with self.assertRaises(ValueError): c.validate_answer(q, dict(answer='no', confidence=.9, affected=ids, regions=regions))

    def test_stale_duplicate_unknown_response_rejected(self):
        b = fixture(); r = response(b, b['questions'][0])
        for records in [[r, r], [dict(r, question_id='unknown')], [dict(r, question_sha256='stale')], [dict(r, bundle_sha256='stale')]]:
            with self.assertRaises(ValueError): c.answer_records(b, records)

    def test_bundle_and_images_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); b = materialize(root, fixture())
            c.verify_images(root, c.load_bundle(root))
            (root / b['document']['pages'][0]['image']).write_bytes(b'changed')
            with self.assertRaises(ValueError): c.verify_images(root, b)
            b['questions'][0]['expected'] = ['other']; c.save(root / 'bundle.json', b)
            with self.assertRaises(ValueError): c.load_bundle(root)
            with self.assertRaises(ValueError): c.safe_asset(root, '../escape')


class PixelsAndBuilder(unittest.TestCase):
    def test_rgb_roundtrip_crops_and_no_source_mutation(self):
        source = (100, 100, bytearray([255] * 30000))
        self.assertEqual(raster.decode(raster.encode(*source)), source)
        marked = raster.outlined(source, [dict(box=[10, 20, 60, 50], label='A')])
        self.assertEqual(source[2], bytearray([255] * 30000))
        self.assertEqual(marked[2][3 * (20 * 100 + 10):3 * (20 * 100 + 10) + 3], bytes([220, 20, 30]))
        w, h, pixels = raster.crop(marked, [-10, 15, 40, 50])
        self.assertEqual((w, h, len(pixels)), (40, 35, 4200))

    def test_all_five_types_and_cross_page_edges(self):
        b = fixture(); qs = b['questions']
        self.assertEqual(set(q['type'] for q in qs), set(c.TYPES))
        cross = [q for q in qs if q['type'] == 'Q2' and len(q['pages']) == 2]
        self.assertEqual(len(cross), 1)
        self.assertEqual(len(cross[0]['views']), 4)
        self.assertEqual(cross[0]['targets'], ['p1.b2', 'p2.b0'])
        self.assertEqual(qs, build.questions(b['document']))

    def test_empty_page_gets_completeness_and_float_questions(self):
        d = dict(paper='empty', pages=[dict(page=1, image='p.png', boxes=[], lines=[], body_order=[], floats=[], captions=[])])
        self.assertEqual([q['type'] for q in build.questions(d)], ['Q3', 'Q5'])

    def test_internal_order_is_questioned(self):
        b = fixture(); p = b['document']['pages'][0]
        p['boxes'][1]['lines'] = ['p1.l1', 'p1.l2']
        qs = build.questions(b['document'])
        self.assertTrue(any(q['type'] == 'Q2' and q['level'] == 'line' for q in qs))

    def test_caption_owner_not_present_in_main_text(self):
        # Rule 4 removes paired caption blocks from rule 6's body classification.
        page = dict(page=1, params=dict(dpi=110), elements=[dict(id='r', kind='text', angle=0, line=1,
            text='Figure 1. A caption', box_px=[10, 20, 90, 30], size_px=10)],
            blocks=[dict(id='b', box_px=[10, 20, 90, 30], members=['r'], kinds=['text'])],
            main_text=dict(blocks=[], reading_order=[]),
            floats=[dict(id='f', caption='Figure 1. A caption', box_px=[10, 5, 90, 30], blocks=['b'])])
        geo = dict(media=[0, 0, 100 * 72 / 110, 100 * 72 / 110], height=100 * 72 / 110, rotation=0)
        p = build.normalize(page, geo, 100, 100)
        self.assertEqual(p['boxes'][0]['expected'], ['caption'])
        self.assertEqual(len(p['captions']), 1)

    def test_rotated_and_shifted_frames_use_export_transform(self):
        for rotation in (0, 90, 180, 270):
            geo = dict(media=[20, 30, 620, 830], width=600, height=800, rotation=rotation)
            expected = [12, 23, 42, 55]
            native = build.exporter.conserve.native_box(expected, geo, 150 / 72, 150 / 72)
            actual = build.exporter.image_box(native, 150, geo)
            for a, b in zip(actual, expected): self.assertAlmostEqual(a, b * 110 / 72)

    def test_broad_other_role_refinement_is_not_a_false_alarm(self):
        page = dict(page=1, params=dict(dpi=110), elements=[dict(id='r', kind='text', angle=0, line=1,
            text='A note', box_px=[10, 20, 90, 30], size_px=10)],
            blocks=[dict(id='b', box_px=[10, 20, 90, 30], members=['r'], kinds=['text'])],
            main_text=dict(blocks=[dict(id='b', cls='aside')], reading_order=[]))
        geo = dict(media=[0, 0, 100 * 72 / 110, 100 * 72 / 110], height=100 * 72 / 110, rotation=0)
        p = build.normalize(page, geo, 100, 100); p['image'] = 'page.png'
        q = build.questions(dict(paper='note', pages=[p]))[0]
        self.assertIn('footnote', q['expected'])
        self.assertNotIn('body', q['expected'])
        self.assertEqual(c.decision(q, dict(status='ok', answer=dict(answer='footnote', confidence=.99))), 'agree')

    def test_real_pdf_render_matches_crop_frame(self):
        # Real Poppler rendering, not a mocked image, on a self-contained 72pt PDF.
        content = b'0 0 0 rg 10 20 20 10 re f'
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] /Contents 4 0 R >>',
                   b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream']
        data = bytearray(b'%PDF-1.4\n'); offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(data)); data.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
        xref = len(data); data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
        for offset in offsets[1:]: data.extend(f'{offset:010} 00000 n \n'.encode())
        data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / 'example.pdf'; pdf.write_bytes(data)
            w, h, pixels = raster.render(pdf, 1, dpi=72)
            self.assertEqual((w, h), (72, 72))
            self.assertEqual(pixels[3 * (47 * w + 20):3 * (47 * w + 20) + 3], bytes([0, 0, 0]))
            self.assertEqual(pixels[:3], bytes([255, 255, 255]))


class Decisions(unittest.TestCase):
    def test_high_confidence_classes_and_rejected_edges_only(self):
        b = fixture(); before = copy.deepcopy(b)
        qs = b['questions']; rs = [response(b, q) for q in qs]
        q1 = next(q for q in qs if q['type'] == 'Q1' and q['expected'] == ['body'])
        q2 = next(q for q in qs if q['type'] == 'Q2')
        for r in rs:
            if r['question_id'] == q1['id']: r['answer']['answer'] = 'caption'
            if r['question_id'] == q2['id']: r['answer']['answer'] = 'no'
        out = applier.apply(b, rs)
        self.assertEqual(b, before)
        self.assertEqual(out['overlay']['classes'][q1['targets'][0]], 'caption')
        self.assertEqual(out['overlay']['rejected_edges'][0]['targets'], q2['targets'])
        self.assertFalse(out['ready_for_automatic_copy'])
        self.assertTrue(any(f['reason'] == 'body_membership_changed_order_requires_review' for f in out['flags']))

    def test_low_confidence_agreement_still_flags_and_never_applies(self):
        b = fixture(); q = b['questions'][0]; r = response(b, q); r['answer']['confidence'] = .84
        out = applier.apply(b, [r])
        self.assertEqual(out['decisions'][0]['state'], 'uncertain')
        self.assertEqual(out['overlay']['classes'], {})
        self.assertFalse(out['complete'])
        self.assertTrue(any(f['reason'] == 'missing' for f in out['flags']))

    def test_conflicting_header_does_not_override_class(self):
        b = fixture(); rs = [response(b, q) for q in b['questions']]
        rs[0]['answer']['answer'] = 'body'
        out = applier.apply(b, rs)
        self.assertNotIn('p1.b0', out['overlay']['header_roles'])
        self.assertTrue(any(f['reason'] == 'header_subtype_conflicts_with_class' for f in out['flags']))


class Truth(unittest.TestCase):
    def truth(self, b):
        q = next(q for q in b['questions'] if q['type'] == 'Q2' and q['pages'] == [1])
        return dict(negative_papers=[], faults=[dict(id='fault', paper='sample', types=['Q2'], pages=[1],
                    exclusions=[], question_ids=[q['id']], truth_status='verified', bundle_sha256=b['bundle_sha256'])])

    def test_exact_truth_requires_current_bundle_hash(self):
        b = fixture(); t = self.truth(b); t['faults'][0]['bundle_sha256'] = 'stale'
        with self.assertRaises(ValueError): score.evaluate({'sample': b}, t, {'sample': []})

    def test_exact_recall_and_no_double_credit(self):
        b = fixture(); t = self.truth(b); rs = [response(b, q) for q in b['questions']]
        qid = t['faults'][0]['question_ids'][0]
        for r in rs:
            if r['question_id'] == qid: r['answer']['answer'] = 'no'
        out = score.evaluate({'sample': b}, t, {'sample': rs})
        self.assertEqual(out['exact']['recall'], 1)
        self.assertEqual(out['exact']['positives'], 1)
        self.assertEqual(out['per_type']['Q2']['exact']['recall'], 1)

    def test_wrong_page_type_does_not_catch_fault(self):
        b = fixture(); t = self.truth(b); t['faults'][0].update(question_ids=[], truth_status='historical')
        rs = [response(b, q) for q in b['questions']]
        qid = next(q['id'] for q in b['questions'] if q['type'] == 'Q3' and q['pages'] == [2])
        for r in rs:
            if r['question_id'] == qid: r['answer'] = dict(answer='yes', confidence=.99, regions=[[1, 2, 3, 4]])
        out = score.evaluate({'sample': b}, t, {'sample': rs})
        self.assertEqual(out['historical_page_type_screen']['recall'], 0)
        self.assertIsNone(out['exact']['recall'])

    def test_missing_pages_are_excluded_not_wildcard(self):
        b = fixture(); t = self.truth(b)
        t['faults'][0].update(pages=[], question_ids=[], truth_status='historical', exclusions=['audit_has_no_explicit_page'])
        out = score.evaluate({'sample': b}, t, {'sample': []})
        self.assertEqual(out['historical_page_type_screen']['positives'], 0)
        self.assertIsNone(out['historical_page_type_screen']['recall'])

    def test_partial_negative_is_not_a_clean_paper(self):
        b = fixture(); t = dict(negative_papers=['sample'], faults=[])
        out = score.evaluate({'sample': b}, t, {'sample': []})
        self.assertIsNone(out['negative_paper_false_alarm_rate'])
        self.assertFalse(out['complete'])
        self.assertGreater(out['negatives'][0]['operational_flags'], 0)

    def test_uncertainty_is_false_alarm_but_runtime_error_is_separate(self):
        b = fixture(); t = dict(negative_papers=['sample'], faults=[])
        rs = [response(b, q) for q in b['questions']]; rs[0]['answer']['confidence'] = .1
        out = score.evaluate({'sample': b}, t, {'sample': rs})
        self.assertEqual(out['negative_paper_false_alarm_rate'], 1)
        self.assertEqual(out['per_type']['Q1']['false_alarms'], 1)
        rs[0].pop('answer'); rs[0]['status'] = 'error'
        out = score.evaluate({'sample': b}, t, {'sample': rs})
        self.assertEqual(out['per_type']['Q1']['false_alarms'], 0)
        self.assertIsNone(out['negative_paper_false_alarm_rate'])

    def test_selection_does_not_invent_tenth_negative_or_relabel_fixed(self):
        papers = [dict(paper=f'sample{i}', set='group', majors_listed=0) for i in range(9)]
        papers.append(dict(paper='fixed', set='group', majors_listed=1))
        pool = dict(papers=papers, faults=[dict(paper='fixed', cause='HEAD', r25_status='fixed')])
        pos, neg = prep.select(pool, ['group'], 10, 10)
        self.assertEqual(len(neg), 9); self.assertEqual(pos, [])

    def test_page_parser_ranges_and_unknowns(self):
        self.assertEqual(prep.page_numbers('2-4, 8 and 10'), [2, 3, 4, 8, 10])
        for value in (None, 'Table 4', 'all pages', '4-2', '0', 'p4 uncertain'):
            self.assertEqual(prep.page_numbers(value), [])


class Runner(unittest.TestCase):
    def test_request_contains_real_images_and_no_audit_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); b = materialize(root, fixture())
            q = next(q for q in b['questions'] if q['type'] == 'Q2' and len(q['pages']) == 2)
            request = runner.messages(root, q)
            images = [x['image_url']['url'] for x in request[1]['content'] if x['type'] == 'image_url']
            self.assertEqual(len(images), 4)
            for url in images: raster.decode(base64.b64decode(url.split(',')[1]))
            self.assertNotIn('source_population', c.canonical(request))
            self.assertNotIn('expected', c.canonical(request))

    def test_truncation_and_invalid_output_become_errors(self):
        b = fixture(); q = b['questions'][0]
        for text, finish in [('{}', 'stop'), ('{"answer":"body","confidence":1}', 'length'), ('replacement prose', 'stop')]:
            output = types.SimpleNamespace(outputs=[types.SimpleNamespace(text=text, finish_reason=finish, token_ids=[1])])
            result = runner.postprocess(b, q, output)
            self.assertEqual(result['status'], 'error'); self.assertNotIn('answer', result)
            self.assertNotIn('raw', result)

    def test_fake_vllm_full_runner_offline_guidance_and_resume(self):
        # Exercise the actual runner API with a CPU fake, never claim GPU validation.
        captured = []
        class Params:
            def __init__(self, **kw): self.__dict__.update(kw)
        class FakeLLM:
            def __init__(self, **kw):
                self.kw = kw
                self.assert_offline = os.environ['HF_HUB_OFFLINE']
                captured.append(kw)
            def chat(self, requests, sampling_params, use_tqdm):
                outputs = []
                for p in sampling_params:
                    schema = p.structured_outputs.json
                    self_schema = schema['properties']['answer']['enum']
                    value = dict(answer=self_schema[0], confidence=.95)
                    if 'regions' in schema['properties']:
                        value['answer'] = 'no' if 'affected' not in schema['properties'] else 'yes'
                        value['regions'] = []
                    if 'affected' in schema['properties']: value['affected'] = []
                    outputs.append(types.SimpleNamespace(outputs=[types.SimpleNamespace(text=json.dumps(value), finish_reason='stop', token_ids=[1])]))
                return outputs
        vllm = types.ModuleType('vllm'); vllm.LLM = FakeLLM; vllm.SamplingParams = Params
        sp = types.ModuleType('vllm.sampling_params'); sp.StructuredOutputsParams = Params
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'vllm': vllm, 'vllm.sampling_params': sp}), patch.dict(os.environ):
            root = Path(tmp); b = materialize(root / 'bundle', fixture()); (root / 'model').mkdir()
            args = argparse.Namespace(input=str(root / 'bundle'), out=str(root / 'responses'), model=str(root / 'model'),
                max_model_len=32768, max_tokens=1024, tensor_parallel_size=1, gpu_memory_utilization=.18,
                batch_size=3, types=None, max_questions=None, dry_run=False, resume=False)
            runner.run(args)
            path = root / 'responses/sample.jsonl'; records = c.read_jsonl(path)
            self.assertEqual(len(records), len(b['questions']))
            c.answer_records(b, records)
            before = path.read_bytes(); args.resume = True; runner.run(args)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(captured[0]['limit_mm_per_prompt']['image'], 4)
            args.model = str(root / 'different')
            with self.assertRaises(ValueError): runner.run(args)


if __name__ == '__main__':
    unittest.main()
