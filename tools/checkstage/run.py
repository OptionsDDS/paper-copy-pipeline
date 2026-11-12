#!/usr/bin/env python3
"""Check stage of the paper copy program: a local page-reading model answers narrow
questions about the copy, a code duplicate finder looks for blocks printed twice, and
the safe applier makes the placement-only repairs they support.

  /usr/bin/python3 -I tools/checkstage/run.py PAPER_DIR PDF [options]
  /usr/bin/python3 -I tools/checkstage/run.py --batch LIST [options]
      LIST: one "PAPER_DIR<TAB>PDF" per line, or a JSON object {PAPER_DIR: PDF}

Reads PAPER_DIR/copy.md (and copy.trace.json when it belongs to that copy). Writes beside
it, never changing copy.md:
  copy.checked.md          the copy after the accepted ops
  check.ops.json           {"paper", "ops": OPS-SCHEMA-v2 ops in order, "op_sources": why each op}
  check.apply-log.json     the applier's log for those ops (repair_apply.py format)
  copy.checked.trace.json  the native trace carried to copy.checked.md (when copy.md has one),
                           validated with tools/trace.py --copy copy.checked.md --trace ...
  check.answers.json       the model's scored answers (when the model ran)

Model (design "B+ with (ii) veto" of the local-checker trial, 2026-10-25): Qwen3.6-27B-FP8
through vLLM, offline, one load per batch, in the vLLM environment's Python (worker.py);
only scored choices are used (token log-probabilities), never free text. Without the model
(--no-model, or the GPU, environment or weights unavailable) only the code duplicate
finder runs, and the stage says why in check.ops.json "model".

Options: --model PATH, --python PATH (vLLM env python), --cache DIR (vLLM/torch caches and
the GPU lock; default PAPER_DIR/../.checkstage-cache), --need-mib N (free GPU memory needed
before loading, default 46000), --wait S (seconds to wait for it, default 0), --no-model,
--no-dups, --answers FILE (reuse saved answers: a check.answers.json or a worker batch
file; 'saved' reuses each paper's own check.answers.json), --keep-work (keep page images and set-of-marks images in PAPER_DIR/check.work).
Exit status: 0 done (also when the model was skipped), 2 bad input, 1 a paper failed.
"""
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_ops  # noqa: E402
import dupfind  # noqa: E402
import prep  # noqa: E402
import tracemap  # noqa: E402

RA = tracemap.RA
MODEL = '/mnt/ai/models/AI_MODELS/huggingface/Qwen__Qwen3.6-27B-FP8'
VLLM_PY = '/mnt/ai/projects/optionsdds/trials/vlm-trial/envs/monkeyocrv2-vllm-0.25.1/bin/python'
OUTPUTS = ('copy.checked.md', 'check.ops.json', 'check.apply-log.json', 'copy.checked.trace.json', 'check.answers.json')


def log(*a):
    print('checkstage:', *a, file=sys.stderr, flush=True)


def write_atomic(path, content):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    os.replace(tmp, path)


def write_json(path, value, compact=False):
    write_atomic(path, json.dumps(value, ensure_ascii=False, indent=None if compact else 1,
                                  separators=(',', ':') if compact else None) + '\n')


# ------------------------------------------------------------------ the model step
def gpu_free_mib():
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=memory.total,memory.used', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
        total, used = (int(x) for x in out.split(','))
        return total - used
    except Exception:
        return None


def model_unavailable(a):
    if not os.path.isfile(a.python) or not os.access(a.python, os.X_OK):
        return f'vLLM environment python not found: {a.python}'
    if not os.path.isfile(os.path.join(a.model, 'config.json')):
        return f'model weights not found: {a.model}'
    if shutil.which('nvidia-smi') is None:
        return 'no GPU (nvidia-smi not found)'
    return None


def worker_env(cache):
    env = dict(os.environ)
    for k, sub in (('HF_HOME', 'hf'), ('XDG_CACHE_HOME', 'xdg'), ('VLLM_CACHE_ROOT', 'vllm'), ('TRITON_CACHE_DIR', 'triton'),
                   ('TORCHINDUCTOR_CACHE_DIR', 'inductor'), ('MPLCONFIGDIR', 'mpl'), ('NUMBA_CACHE_DIR', 'numba'),
                   ('CUDA_CACHE_PATH', 'nv'), ('TMPDIR', 't')):
        d = os.path.join(cache, sub)
        os.makedirs(d, exist_ok=True)
        env[k] = d
    # vLLM's engine sockets live in TMPDIR: a Unix socket path holds at most 107 bytes (a uuid name is 37)
    if len(env['TMPDIR'].encode()) > 70:
        short = os.environ.get('TMPDIR', '/tmp')
        env['TMPDIR'] = short if len(short.encode()) <= 70 else '/tmp'
        log(f"cache path too long for vLLM's sockets; temporary files go to {env['TMPDIR']}")
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1', VLLM_NO_USAGE_STATS='1',
               DO_NOT_TRACK='1', VLLM_USE_FLASHINFER_SAMPLER='0', OMP_NUM_THREADS=env.get('OMP_NUM_THREADS', '4'),
               CUDA_VISIBLE_DEVICES=env.get('CUDA_VISIBLE_DEVICES', '0'), GPU_UTIL=env.get('GPU_UTIL', '0.46'),
               KV_GIB=env.get('KV_GIB', '8'))
    return env


def run_model(a, specs, cache):
    """Answers for every paper of the batch, or (None, reason)."""
    why = model_unavailable(a)
    if why:
        return None, why, None
    os.makedirs(cache, exist_ok=True)
    lock = open(os.path.join(cache, 'gpu.lock'), 'w')
    fcntl.flock(lock, fcntl.LOCK_EX)  # one model process per cache at a time
    try:
        deadline = time.time() + a.wait
        while True:
            free = gpu_free_mib()
            if free is None:
                return None, 'nvidia-smi gave no memory reading', None
            if free >= a.need_mib:
                break
            if time.time() >= deadline:
                return None, f'GPU busy: {free} MiB free, {a.need_mib} MiB needed', None
            time.sleep(30)
        spec_path = os.path.join(cache, f'specs-{os.getpid()}.json')
        ans_path = os.path.join(cache, f'answers-{os.getpid()}.json')
        write_json(spec_path, {'model': a.model, 'papers': specs}, compact=True)
        log_path = os.path.join(cache, f'worker-{os.getpid()}.log')
        t0 = time.time()
        with open(log_path, 'w') as lf:
            r = subprocess.run([a.python, '-I', '-B', os.path.join(HERE, 'worker.py'), spec_path, ans_path],
                               env=worker_env(cache), stdout=lf, stderr=subprocess.STDOUT, cwd=cache)
        if r.returncode != 0 or not os.path.isfile(ans_path):
            tail = open(log_path, errors='replace').read()[-600:].replace('\n', ' | ')
            return None, f'worker exit {r.returncode} (log {log_path}): {tail}', None
        answers = json.load(open(ans_path, encoding='utf-8'))
        answers['meta']['wall_seconds'] = round(time.time() - t0, 1)
        os.remove(spec_path)
        os.remove(ans_path)
        return answers, None, log_path
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


# ------------------------------------------------------------------ one paper's ops and outputs
def finish_paper(paper_dir, text, recs, trace, answers, model_info, do_dups=True):
    name = os.path.basename(os.path.normpath(paper_dir))
    tracker = tracemap.Tracker(text, trace)
    ops, sources, notes = [], [], []
    cur = text
    if answers is not None:
        m_ops, m_src, m_notes, cur = build_ops.build(text, recs, answers, tracker.apply)
        ops += m_ops
        sources += [dict(s, stage='model') for s in m_src]
        notes += m_notes
    if do_dups:
        factory = (lambda _cur: tracker.confirm_duplicate) if trace is not None else None
        d_ops, d_ev, d_notes, cur = dupfind.find_all(cur, tracker.apply, factory)
        ops += d_ops
        sources += [dict(e, stage='code', by='duplicate', trace_confirmed=trace is not None) for e in d_ev]
        notes += d_notes
    final, entries = RA.apply_operations(text, ops)
    if final != cur or any(e['status'] != 'accepted' for e in entries):
        raise RuntimeError('ops do not replay to the simulated copy')
    for i, s in enumerate(sources):
        s['index'] = i
    write_atomic(os.path.join(paper_dir, 'copy.checked.md'), final)
    stage = {'model': model_info, 'duplicate_finder': 'on' if do_dups else 'off',
             'regions': 'trace' if trace is not None else 'pdftotext', 'ops': len(ops),
             'by': {k: sum(1 for s in sources if s['by'] == k) for k in sorted({s['by'] for s in sources})},
             'not_applied': notes}
    trace_summary = None
    if trace is not None:
        tr = tracker.checked_trace('copy.checked.md')
        tpath = os.path.join(paper_dir, 'copy.checked.trace.json')
        write_json(tpath, tr, compact=True)
        tv = tracemap._trace_module()
        rep = tv.validate(paper_dir, None, False, 'copy.checked.md', 'copy.checked.trace.json')
        tracemap.finish_statistics(tr, rep)
        write_json(tpath, tr, compact=True)
        base = trace.get('accounting', {})
        trace_summary = {'valid': rep['valid'], 'problems': rep['problems'],
                         'lost_lines': [len(base.get('lost_lines', [])), len(rep['accounting']['lost_lines'])],
                         'duplicate_lines': [len(base.get('duplicate_lines', [])), len(rep['accounting']['duplicate_lines'])],
                         'untraced_units': [len(base.get('untraced_units', [])), len(rep['accounting']['untraced_units'])],
                         'removed_units': tr['checked_from']['removed_units']}
        stage['trace'] = trace_summary
    else:
        try:
            os.remove(os.path.join(paper_dir, 'copy.checked.trace.json'))
        except FileNotFoundError:
            pass
    write_json(os.path.join(paper_dir, 'check.ops.json'), {'paper': name, 'ops': ops, 'op_sources': sources, 'stage': stage})
    write_json(os.path.join(paper_dir, 'check.apply-log.json'),
               {'paper': name, 'offsets': 'zero-based, half-open Unicode character ranges', 'ops': entries})
    return stage


def read_list(path):
    if path.endswith('.json'):
        d = json.load(open(path, encoding='utf-8'))
        return list(d.items())
    out = []
    for ln in open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if ln.strip() and not ln.startswith('#'):
            a, b = ln.split('\t')
            out.append((a, b))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paper_dir', nargs='?')
    ap.add_argument('pdf', nargs='?')
    ap.add_argument('--batch')
    ap.add_argument('--model', default=os.environ.get('CHECK_MODEL', MODEL))
    ap.add_argument('--python', default=os.environ.get('CHECK_PYTHON', VLLM_PY))
    ap.add_argument('--cache', default=os.environ.get('CHECK_CACHE'))
    ap.add_argument('--need-mib', type=int, default=int(os.environ.get('CHECK_NEED_MIB', '46000')))
    ap.add_argument('--wait', type=float, default=float(os.environ.get('CHECK_WAIT', '0')))
    ap.add_argument('--no-model', action='store_true')
    ap.add_argument('--no-dups', action='store_true')
    ap.add_argument('--answers')
    ap.add_argument('--keep-work', action='store_true')
    a = ap.parse_args()
    if a.batch:
        items = read_list(a.batch)
    elif a.paper_dir and a.pdf:
        items = [(a.paper_dir, a.pdf)]
    else:
        ap.error('give PAPER_DIR PDF or --batch LIST')
    for d, p in items:
        if not os.path.isfile(os.path.join(d, 'copy.md')) or not os.path.isfile(p):
            log(f'missing copy.md or PDF: {d} {p}')
            return 2
    cache = a.cache or os.path.join(os.path.dirname(os.path.abspath(items[0][0])), '.checkstage-cache')
    t0 = time.time()
    papers = []
    items = [(os.path.abspath(d), os.path.abspath(p)) for d, p in items]  # the worker runs in the cache folder
    for d, p in items:
        work = os.path.join(d, 'check.work')
        text, recs, spec = prep.prepare(d, p, work, render=not (a.no_model or a.answers))
        spec['work'] = os.path.abspath(work)
        papers.append((d, p, text, recs, spec, prep.load_trace(d, text)))
    prep_s = time.time() - t0
    answers_by_dir, model_info = {}, None
    if a.answers == 'saved':  # each paper's own check.answers.json from an earlier run
        for d, *_ in papers:
            f = os.path.join(d, 'check.answers.json')
            if os.path.isfile(f):
                answers_by_dir[os.path.abspath(d)] = json.load(open(f, encoding='utf-8'))
        model_info = {'status': 'answers reused', 'file': 'PAPER_DIR/check.answers.json'}
    elif a.answers:
        got = json.load(open(a.answers, encoding='utf-8'))
        if 'papers' in got and 'meta' in got:
            for x in got['papers']:
                answers_by_dir[os.path.abspath(x['paper_dir'])] = x
        else:
            answers_by_dir[os.path.abspath(items[0][0])] = got
        model_info = {'status': 'answers reused', 'file': os.path.abspath(a.answers)}
    elif a.no_model:
        model_info = {'status': 'off', 'reason': '--no-model'}
    else:
        got, why, wlog = run_model(a, [s for *_, s, _ in papers], cache)
        if got is None:
            model_info = {'status': 'skipped', 'reason': why}
            log('model skipped:', why)
        else:
            model_info = dict(status='ran', **got['meta'], worker_log=wlog)
            for x in got['papers']:
                answers_by_dir[os.path.abspath(x['paper_dir'])] = x
    rc = 0
    for d, p, text, recs, spec, trace in papers:
        ans = answers_by_dir.get(os.path.abspath(d))
        info = dict(model_info or {}, prep_seconds_batch=round(prep_s, 1))
        if model_info and model_info.get('status') in ('ran', 'answers reused') and ans is None:
            info = dict(info, status='no answers for this paper')
        try:
            if ans is not None and model_info.get('status') == 'ran':
                write_json(os.path.join(d, 'check.answers.json'), ans, compact=True)
            stage = finish_paper(d, text, recs, trace, ans, info, not a.no_dups)
            log(os.path.basename(os.path.normpath(d)), f"{stage['ops']} op(s)", json.dumps(stage['by']),
                ('trace ' + json.dumps({k: v for k, v in stage['trace'].items() if k in ('valid', 'lost_lines', 'duplicate_lines')}))
                if stage.get('trace') else '')
        except Exception as exc:  # one paper's failure never stops the batch
            rc = 1
            log(f'{d}: failed: {type(exc).__name__}: {exc}')
        if not a.keep_work:
            shutil.rmtree(os.path.join(d, 'check.work'), ignore_errors=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
