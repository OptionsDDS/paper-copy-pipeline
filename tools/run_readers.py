#!/usr/bin/env python3
"""Render PDF pages at 150 dpi and run the two audited local readers, offline.

Usage: /usr/bin/python3 -I tools/run_readers.py PDF OUT_DIR [--pages 1,3]
       /usr/bin/python3 -I tools/run_readers.py --jobs JOBS.json
JOBS.json is a list of {"pdf": PATH, "out": DIR, "pages": [N, ...]}: every job
shares one load of each engine, so a folder of papers costs two model loads.
Use --render-only for a CPU smoke test; --keep-images retains the page PNGs.
Outputs are OUT_DIR/{mineru2.5-pro-2605,ovisocr2}/pNNN.{md,json}.

The GPU subprocess uses the trial's original inference scripts, without editing
them. Only their page/output/timing adapter is replaced. Consequently prompts,
two-step crops, rotations, sampling, OTSL conversion and vLLM options are exactly
those of REPORT-INFERENCE.md, including the absent MinerU logits processor.
The GPU caps are the trial's 0.15 (MinerU) and 0.30 (Ovis), each lowered when
needed so that one engine never reserves more than --gpu-max-gb (default 45 GB,
because another GPU job may hold about 40 GB). Each engine exits before the
next starts, and an inter-process lock (COPY_READERS_LOCK) admits one engine
of this program at a time, so parallel copies never stack engines. No model is
downloaded. CPU imports use stdlib.

COPY_READERS_PYTHON names the vLLM interpreter (default: the trial's env).
Exit status 75 means the readers are unavailable here (no GPU, no reader
interpreter or model scripts, or not enough free GPU memory within
--gpu-wait seconds): nothing was read, and a caller keeps its copy without
readers. Any other nonzero status is a reader failure; completed page pairs are
kept and still hash-checked by their consumer.

A manifest binds an output directory to one PDF hash. Completed page pairs are
resumed only when their JSON carries that hash. Failures exit nonzero, even
though the original trial loop catches inference errors. Images are removed
after success unless requested. Engine logs go to --home (default OUT_DIR);
engine caches go to COPY_READERS_ENGINE_CACHE when set, else to a cache folder
in --home that is deleted after the run (the disk is small). vLLM's
IPC sockets need a path under 108 bytes, so they go to COPY_READERS_RPC_DIR, or
OUT_DIR's cache when that is short enough, or else a private system temporary
directory that is removed afterwards.
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time

TRIAL = Path('/mnt/ai/projects/optionsdds/trials/vlm-trial')
PYTHON = Path(os.environ.get('COPY_READERS_PYTHON', TRIAL / 'envs/monkeyocrv2-vllm-0.25.1/bin/python'))
MODELS = {'mineru2.5-pro-2605': ('run_twostep_vllm.py', 'mineru', '0.15'),
          'ovisocr2': ('run_page_vllm.py', 'ovisocr2', '0.30')}
UNAVAILABLE = 75
LOCK = Path(__file__).resolve().with_name('.readers-gpu.lock')
RPC_MAX = 64  # base path + '/' + uuid4 (36) must stay below sun_path's 108 bytes


class Unavailable(Exception):
    """The readers cannot run on this machine now; nothing was attempted."""


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def page_selection(value):
    try:
        pages = [int(p) for p in value.split(',')]
    except ValueError:
        raise argparse.ArgumentTypeError('pages must be comma-separated positive integers')
    if not pages or any(p < 1 for p in pages) or len(set(pages)) != len(pages):
        raise argparse.ArgumentTypeError('pages must be positive and unique')
    return sorted(pages)


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def output_paths(out, model, page):
    stem = Path(out) / model / f'p{page:03d}'
    return stem.with_suffix('.md'), stem.with_suffix('.json')


def complete(out, model, page, pdf_hash):
    md, js = output_paths(out, model, page)
    try:
        obj = json.loads(js.read_text())
        return md.is_file() and obj.get('input_sha256') == pdf_hash and \
            obj.get('markdown_sha256') == digest(md)
    except (OSError, ValueError, AttributeError):
        return False


def gpu_memory():
    """(total MiB, free MiB) of GPU 0, or None when no NVIDIA GPU answers."""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total,memory.free',
                                 '--format=csv,noheader,nounits', '-i', '0'],
                                capture_output=True, text=True, timeout=60)
        total, free = (int(v) for v in result.stdout.split(',')[:2])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return (total, free) if result.returncode == 0 and total > 0 else None


def utilisation(model, total_mib, max_gb):
    """The trial's engine fraction, lowered so the engine stays under max_gb."""
    return min(float(MODELS[model][2]), max_gb * 1024 / total_mib)


def environment(out, model, util=None, rpc=None, cache=None):
    env = os.environ.copy()
    cache = Path(cache) if cache else Path(out) / 'cache'
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
               VLLM_NO_USAGE_STATS='1', DO_NOT_TRACK='1', PYTHONDONTWRITEBYTECODE='1',
               VLLM_USE_FLASHINFER_SAMPLER='0', OMP_NUM_THREADS='4',
               GPU_UTIL=MODELS[model][2] if util is None else f'{util:.4f}')
    for key, subdir in {'HF_HOME': 'hf', 'XDG_CACHE_HOME': 'xdg',
                        'VLLM_CACHE_ROOT': 'vllm', 'TRITON_CACHE_DIR': 'triton',
                        'TORCHINDUCTOR_CACHE_DIR': 'inductor', 'CUDA_CACHE_PATH': 'cuda',
                        'TMPDIR': 'tmp', 'MPLCONFIGDIR': 'mpl',
                        'NUMBA_CACHE_DIR': 'numba'}.items():
        directory = cache / subdir
        directory.mkdir(parents=True, exist_ok=True)
        env[key] = str(directory)
    env['VLLM_RPC_BASE_PATH'] = str(rpc or env['TMPDIR'])
    return env


@contextlib.contextmanager
def rpc_directory(cache):
    chosen = os.environ.get('COPY_READERS_RPC_DIR')
    if chosen:
        Path(chosen).mkdir(parents=True, exist_ok=True)
        yield Path(chosen)
    elif len(str(cache)) <= RPC_MAX:
        Path(cache).mkdir(parents=True, exist_ok=True)
        yield Path(cache)
    else:
        private = Path(tempfile.mkdtemp(prefix='readers-'))
        try:
            yield private
        finally:
            shutil.rmtree(private, ignore_errors=True)


@contextlib.contextmanager
def gpu_lock(path):
    path = Path(path)
    try:
        handle = path.open('a')
    except OSError:  # a read-only program folder: a lock all users can share
        handle = (Path(tempfile.gettempdir()) / 'copy-readers-gpu.lock').open('a')
    with handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def wait_for_memory(model, max_gb, wait):
    """Return the engine fraction once enough GPU memory is free, else raise."""
    deadline = time.monotonic() + wait
    while True:
        status = gpu_memory()
        if status is None:
            raise Unavailable('no NVIDIA GPU answers nvidia-smi')
        total, free = status
        util = utilisation(model, total, max_gb)
        # vLLM refuses to start when the requested fraction exceeds free memory;
        # keep 1 GiB for the CUDA context outside the reservation.
        if free >= util * total + 1024:
            return util
        if time.monotonic() >= deadline:
            raise Unavailable(f'{model}: needs {util * total / 1024:.1f} GiB, '
                              f'{free / 1024:.1f} GiB free')
        time.sleep(15)


def render(pdf, out, pages):
    directory = Path(out) / 'pages'
    directory.mkdir(parents=True, exist_ok=True)
    for page in pages:
        prefix = directory / f'p{page:03d}'
        if not prefix.with_suffix('.png').is_file():
            subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-r', '150',
                            '-singlefile', '-png', str(pdf), str(prefix)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if not prefix.with_suffix('.png').is_file():
            raise RuntimeError(f'page {page}: renderer produced no image')


def worker(out, model, scripts, batch, plan=None):
    """Execute the audited engine verbatim with a private output adapter.

    plan: a JSON list of {"out", "pdf_sha256", "pages"}; without it the one
    manifest in out is the plan. Timings go to out/model/timings.tsv.
    """
    if plan is None:
        manifest = json.loads((out / 'readers.manifest.json').read_text())
        jobs = [dict(out=str(out), pdf_sha256=manifest['pdf_sha256'], pages=manifest['pages'])]
    else:
        jobs = json.loads(Path(plan).read_text())
    spec = importlib.util.spec_from_file_location('common', scripts / 'common.py')
    common = importlib.util.module_from_spec(spec)
    sys.modules['common'] = common
    spec.loader.exec_module(common)
    common.T = str(out)
    common.args = lambda: argparse.Namespace(model=model, batch=batch)
    # Absolute image paths: os.path.join(common.T, image) keeps them unchanged.
    common.items = lambda a: [dict(paper=str(i), page=p,
                                   image=str(Path(job['out']) / 'pages' / f'p{p:03d}.png'))
                              for i, job in enumerate(jobs) for p in job['pages']
                              if not complete(job['out'], model, p, job['pdf_sha256'])]
    for job in jobs:
        (Path(job['out']) / model).mkdir(parents=True, exist_ok=True)
    destination = out / model
    destination.mkdir(parents=True, exist_ok=True)
    common.outdir = lambda a: str(destination)
    common.done_set = lambda d: set()  # hash-checked above, not timing-log checked
    common.paths = lambda d, it: tuple(str(p) for p in output_paths(
        jobs[int(it['paper'])]['out'] if 'paper' in it else out, model, it['page']))
    script, cfg, _ = MODELS[model]
    sys.argv = [str(scripts / script), '--cfg', cfg]
    runpy.run_path(str(scripts / script), run_name='__main__')


def prepare(pdf, out, pages, scripts, batch):
    """Bind out to the PDF, list its pages and return (hash, pages)."""
    if not Path(pdf).is_file():
        raise ValueError(f'{pdf}: PDF does not exist')
    pdf, out = Path(pdf).resolve(), Path(out).resolve()
    content = subprocess.run(['pdftotext', str(pdf), '-'], check=True,
                             capture_output=True).stdout
    count = content.count(b'\f')
    if not count:
        raise ValueError(f'{pdf}: PDF has no readable pages')
    pages = sorted(pages) if pages else list(range(1, count + 1))
    if pages[-1] > count:
        raise ValueError(f'{pdf}: PDF has only {count} pages')
    out.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(pdf)
    path = out / 'readers.manifest.json'
    if path.exists() and json.loads(path.read_text()).get('pdf_sha256') != fingerprint:
        raise ValueError(f'{out}: output directory belongs to a different PDF')
    hashes = {name: digest(scripts / name) for name in
              ('common.py', 'otsl.py', 'run_twostep_vllm.py', 'run_page_vllm.py')
              if (scripts / name).is_file()}
    atomic_json(path, dict(version=1, pdf=str(pdf), pdf_sha256=fingerprint, pages=pages,
                           dpi=150, batch=batch, scripts=str(scripts), script_sha256=hashes))
    return fingerprint, pages


def run_jobs(jobs, args):
    """jobs: [(pdf, out, pages)]. Returns the number of failed page pairs."""
    scripts = args.scripts.resolve()
    prepared = []
    for pdf, out, pages in jobs:
        fingerprint, pages = prepare(pdf, out, pages, scripts, args.batch)
        out = Path(out).resolve()
        prepared.append((Path(pdf).resolve(), out, fingerprint, pages))
    pending = {m: [(job, p) for job in prepared for p in job[3] if not complete(job[1], m, p, job[2])]
               for m in MODELS}
    if any(pending.values()) and not args.render_only:
        # Before any rendering: a machine without the readers costs nothing.
        if not args.python.is_file():
            raise Unavailable(f'reader interpreter {args.python} is absent')
        if not all((scripts / MODELS[m][0]).is_file() for m in MODELS):
            raise Unavailable(f'reader scripts are absent from {scripts}')
        if gpu_memory() is None:
            raise Unavailable('no NVIDIA GPU answers nvidia-smi')
    for pdf, out, fingerprint, pages in prepared:
        render(pdf, out, [p for p in pages if args.render_only or
                          any(not complete(out, m, p, fingerprint) for m in MODELS)])
    if args.render_only:
        print(f'Rendered {sum(len(j[3]) for j in prepared)} pages; inference not run.')
        return 0
    failed = 0
    home = Path(args.home).resolve() if args.home else prepared[0][1]
    home.mkdir(parents=True, exist_ok=True)
    shared = os.environ.get('COPY_READERS_ENGINE_CACHE')
    cache = Path(shared) if shared else home / 'cache'
    for model, todo in pending.items():
        if not todo:
            continue
        # Remove incomplete pairs so a caught worker error cannot reuse stale text.
        for (pdf, out, fingerprint, _), p in todo:
            for f in output_paths(out, model, p):
                f.unlink(missing_ok=True)
        plan = home / f'readers.{model}.plan.json'
        groups = {}
        for (pdf, out, fingerprint, _), p in todo:
            groups.setdefault((str(out), fingerprint), []).append(p)
        atomic_json(plan, [dict(out=o, pdf_sha256=h, pages=ps) for (o, h), ps in groups.items()])
        with gpu_lock(os.environ.get('COPY_READERS_LOCK', LOCK)), \
                rpc_directory(cache / 'rpc') as rpc:
            # vLLM sizes its cache from device-wide free memory while it profiles,
            # so another job loading at that moment can make an engine fail to
            # start. A worker that produced no page is started again (twice).
            for attempt in range(3):
                util = wait_for_memory(model, args.gpu_max_gb, args.gpu_wait)
                with (home / f'{model}.log').open('a') as log:
                    log.write(f'\n# {time.strftime("%Y-%m-%d %H:%M:%S")} {len(todo)} pages, '
                              f'gpu_memory_utilization {util:.4f}, attempt {attempt + 1}\n')
                    log.flush()
                    code = subprocess.run([str(args.python), '-I', '-B', str(Path(__file__).resolve()),
                                           '--worker', model, '--plan', str(plan),
                                           '--scripts', str(scripts), '--batch', str(args.batch),
                                           str(home), str(home)],
                                          env=environment(home, model, util, rpc, cache),
                                          stdout=log, stderr=log).returncode
                produced = any(output_paths(out, model, p)[1].is_file() for (_, out, _, _), p in todo)
                if produced or attempt == 2:
                    break
                time.sleep(30)
        plan.unlink(missing_ok=True)
        for (pdf, out, fingerprint, _), page in todo:
            md, js = output_paths(out, model, page)
            if not md.is_file() or not js.is_file():
                failed += 1
                for f in (md, js):
                    f.unlink(missing_ok=True)
                continue
            obj = json.loads(js.read_text())
            obj.update(input_sha256=fingerprint, page=page, markdown_sha256=digest(md))
            atomic_json(js, obj)
    if not shared and cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)  # engine caches are rebuilt per run
    if not args.keep_images:
        for _, out, _, pages in prepared:
            for page in pages:
                (out / 'pages' / f'p{page:03d}.png').unlink(missing_ok=True)
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', type=Path, nargs='?')
    ap.add_argument('out_dir', type=Path, nargs='?')
    ap.add_argument('--pages', type=page_selection)
    ap.add_argument('--jobs', type=Path, help='JSON list of {"pdf", "out", "pages"}')
    ap.add_argument('--home', type=Path, help='plans and engine logs (default: the first OUT_DIR)')
    ap.add_argument('--render-only', action='store_true')
    ap.add_argument('--keep-images', action='store_true')
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--gpu-max-gb', type=float, default=float(os.environ.get('COPY_READERS_GPU_MAX_GB', 45)),
                    help='largest GPU reservation of one engine, GB (default 45)')
    ap.add_argument('--gpu-wait', type=float, default=600,
                    help='seconds to wait for free GPU memory before giving up (status 75)')
    ap.add_argument('--python', type=Path, default=PYTHON, help='vLLM 0.25.1 interpreter')
    ap.add_argument('--scripts', type=Path, default=TRIAL / 'scripts')
    ap.add_argument('--worker', choices=MODELS, help=argparse.SUPPRESS)
    ap.add_argument('--plan', type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.batch < 1:
        ap.error('--batch must be positive')
    if args.gpu_max_gb <= 0:
        ap.error('--gpu-max-gb must be positive')
    if args.worker:
        worker(args.out_dir.resolve(), args.worker, args.scripts.resolve(), args.batch, args.plan)
        return 0
    if args.jobs:
        if args.pdf or args.pages:
            ap.error('--jobs replaces PDF, OUT_DIR and --pages')
        jobs = [(Path(j['pdf']), Path(j['out']), j.get('pages')) for j in json.loads(args.jobs.read_text())]
        jobs = [j for j in jobs if j[2] is None or j[2]]
        if not jobs:
            print('No pages to read.')
            return 0
    elif args.pdf and args.out_dir:
        jobs = [(args.pdf, args.out_dir, args.pages)]
    else:
        ap.error('PDF and OUT_DIR, or --jobs, are required')
    try:
        failed = run_jobs(jobs, args)
    except ValueError as error:
        ap.error(str(error))
    except Unavailable as error:
        print(f'readers unavailable: {error}', file=sys.stderr)
        return UNAVAILABLE
    if failed:
        print(f'{failed} reader page(s) failed; see the model logs', file=sys.stderr)
        return 1
    if not args.render_only:
        print(f'Both readers completed {sum(len(j[2] or []) for j in jobs) or "all"} pages '
              f'in {len(jobs)} PDF(s)')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
