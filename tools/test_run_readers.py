"""CPU-only runner checks, including real Poppler rendering of a tiny PDF."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('run_readers', Path(__file__).with_name('run_readers.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def tiny_pdf(path):
    content = b'BT /F1 12 Tf 20 60 Td (CPU renderer test) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 144 144] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream']
    data, offsets = b'%PDF-1.4\n', [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data)); data += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
    start = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets[1:])
    data += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()
    path.write_bytes(data)


class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf, self.out = self.root / 'input.pdf', self.root / 'out'
        tiny_pdf(self.pdf)

    def test_page_arguments(self):
        self.assertEqual(r.page_selection('3,1'), [1, 3])
        for bad in ('0', '-1', '', '1,1', 'a', '1-3', '1,'):
            with self.assertRaises(argparse.ArgumentTypeError): r.page_selection(bad)

    def test_render_and_manifest(self):
        self.assertEqual(r.main([str(self.pdf), str(self.out), '--render-only', '--pages', '1']), 0)
        img = (self.out / 'pages/p001.png').read_bytes()
        self.assertEqual(img[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', img[16:24]), (300, 300))
        manifest = json.loads((self.out / 'readers.manifest.json').read_text())
        self.assertEqual(manifest['dpi'], 150)
        self.assertEqual(manifest['pdf_sha256'], r.digest(self.pdf))
        self.assertFalse((self.out / r.MODELS.keys().__iter__().__next__()).exists())

    def test_out_of_range(self):
        with self.assertRaises(SystemExit): r.main([str(self.pdf), str(self.out), '--pages', '2', '--render-only'])

    def test_wrong_pdf_directory_is_rejected(self):
        self.out.mkdir()
        r.atomic_json(self.out / 'readers.manifest.json', {'pdf_sha256': 'wrong'})
        with self.assertRaises(SystemExit): r.main([str(self.pdf), str(self.out), '--render-only'])

    def test_layout_and_resume_require_both_hashes(self):
        model = next(iter(r.MODELS))
        md, js = r.output_paths(self.out, model, 9)
        md.parent.mkdir(parents=True)
        md.write_text('read result')
        self.assertEqual(md.name, 'p009.md')
        self.assertFalse(r.complete(self.out, model, 9, 'pdf'))
        r.atomic_json(js, {'input_sha256': 'pdf', 'markdown_sha256': r.digest(md)})
        self.assertTrue(r.complete(self.out, model, 9, 'pdf'))
        md.write_text('changed')
        self.assertFalse(r.complete(self.out, model, 9, 'pdf'))

    def test_environment_is_offline_and_caches_are_local(self):
        env = r.environment(self.out, 'ovisocr2')
        self.assertEqual(env['HF_HUB_OFFLINE'], '1')
        self.assertEqual(env['GPU_UTIL'], '0.30')
        self.assertEqual(env['VLLM_USE_FLASHINFER_SAMPLER'], '0')
        for name in ('HF_HOME', 'TMPDIR', 'TRITON_CACHE_DIR', 'VLLM_CACHE_ROOT'):
            self.assertTrue(Path(env[name]).is_relative_to(self.out))

    def test_worker_adapts_only_io_and_keeps_model_script(self):
        self.out.mkdir()
        r.atomic_json(self.out / 'readers.manifest.json', {'pdf_sha256': 'pdf', 'pages': [2, 7]})
        saved = sys.modules.get('common')
        argv = sys.argv[:]
        try:
            with patch.object(r.runpy, 'run_path') as run:
                r.worker(self.out, 'ovisocr2', r.TRIAL / 'scripts', 16)
                run.assert_called_once_with(str(r.TRIAL / 'scripts/run_page_vllm.py'), run_name='__main__')
                common = sys.modules['common']
                self.assertEqual([i['page'] for i in common.items(None)], [2, 7])
                self.assertEqual(common.paths(None, {'page': 2}), tuple(map(str, r.output_paths(self.out, 'ovisocr2', 2))))
                self.assertEqual(common.args().batch, 16)
                self.assertEqual(sys.argv[-2:], ['--cfg', 'ovisocr2'])
        finally:
            sys.argv = argv
            if saved is None: sys.modules.pop('common', None)
            else: sys.modules['common'] = saved


    def test_engine_never_exceeds_the_gpu_cap(self):
        total = 97887
        for model in r.MODELS:
            self.assertLessEqual(r.utilisation(model, total, 45) * total / 1024, 45)
            self.assertEqual(r.utilisation(model, total, 45), float(r.MODELS[model][2]))
        self.assertAlmostEqual(r.utilisation('ovisocr2', total, 10) * total / 1024, 10)

    def test_no_gpu_is_status_75_and_reads_nothing(self):
        python = self.root / 'python'; python.write_text('')
        with patch.object(r, 'gpu_memory', return_value=None):
            code = r.main([str(self.pdf), str(self.out), '--pages', '1', '--python', str(python)])
        self.assertEqual(code, r.UNAVAILABLE)
        self.assertFalse(any((self.out / m).exists() for m in r.MODELS))
        self.assertFalse((self.out / 'pages').exists())  # nothing rendered without readers
        with patch.object(r, 'gpu_memory', return_value=(1000, 1000)):
            code = r.main([str(self.pdf), str(self.out), '--pages', '1',
                           '--python', str(self.root / 'absent')])
        self.assertEqual(code, r.UNAVAILABLE)

    def test_too_little_free_memory_gives_up(self):
        with patch.object(r, 'gpu_memory', return_value=(97887, 2000)):
            with self.assertRaises(r.Unavailable): r.wait_for_memory('ovisocr2', 45, 0)
        with patch.object(r, 'gpu_memory', return_value=(97887, 60000)):
            self.assertEqual(r.wait_for_memory('ovisocr2', 45, 0), 0.30)

    def test_ipc_path_is_short(self):
        deep = self.root / ('x' * 80) / 'cache'
        with patch.dict(r.os.environ, {}, clear=False):
            r.os.environ.pop('COPY_READERS_RPC_DIR', None)
            with r.rpc_directory(deep) as rpc:
                self.assertLessEqual(len(str(rpc)), r.RPC_MAX)
                self.assertTrue(rpc.is_dir())
            self.assertFalse(rpc.exists())
        env = r.environment(self.out, 'mineru2.5-pro-2605', 0.15, Path('/short'))
        self.assertEqual(env['VLLM_RPC_BASE_PATH'], '/short')

    def test_plan_worker_reads_many_pdfs_with_one_engine(self):
        a, b = self.root / 'a', self.root / 'b'
        plan = self.root / 'plan.json'
        r.atomic_json(plan, [dict(out=str(a), pdf_sha256='h1', pages=[1, 4]), dict(out=str(b), pdf_sha256='h2', pages=[2])])
        saved = sys.modules.get('common')
        argv = sys.argv[:]
        try:
            with patch.object(r.runpy, 'run_path') as run:
                r.worker(self.out, 'ovisocr2', r.TRIAL / 'scripts', 8, plan)
                self.assertEqual(run.call_count, 1)
                common = sys.modules['common']
                items = common.items(None)
                self.assertEqual([(i['paper'], i['page']) for i in items], [('0', 1), ('0', 4), ('1', 2)])
                self.assertEqual(items[2]['image'], str(b / 'pages/p002.png'))
                self.assertEqual(common.paths(None, items[2]), tuple(map(str, r.output_paths(b, 'ovisocr2', 2))))
        finally:
            sys.argv = argv
            if saved is None: sys.modules.pop('common', None)
            else: sys.modules['common'] = saved

    def test_jobs_render_only(self):
        jobs = self.root / 'jobs.json'
        r.atomic_json(jobs, [dict(pdf=str(self.pdf), out=str(self.out), pages=[1])])
        self.assertEqual(r.main(['--jobs', str(jobs), '--render-only']), 0)
        self.assertTrue((self.out / 'pages/p001.png').is_file())


if __name__ == '__main__':
    unittest.main()
