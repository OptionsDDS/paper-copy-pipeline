#!/bin/bash
# Usage: copy_plos.sh PLOS_RUN_DIR OUTDIR
# COPY_PLOS_TRUTH overrides the dataset; COPY_PLOS_WORKERS (default 6) bounds
# concurrency. Only copied JSON is mutated. Keep copies/logs, discard scratch.
# COPY_PLOS_RESUME=1 reuses completed articles only when PDF, inputs, scripts
# and every retained artifact still match their saved hashes. Each completed
# article gets an atomic record, so an interrupted batch can resume safely.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo "usage: $0 PLOS_RUN_DIR OUTDIR" >&2
  exit 2
fi
exec /usr/bin/python3 -I - "$0" "$1" "$2" <<'PY'
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

started = time.monotonic()
home = Path(sys.argv[1]).resolve().parents[1]
source, output = (Path(p).resolve() for p in sys.argv[2:])
truth = Path(os.environ.get('COPY_PLOS_TRUTH',
    '/mnt/ai/datasets/grobid-evaluation/PLOS_1000-sample100')).resolve()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

try:
    workers = int(os.environ.get('COPY_PLOS_WORKERS', '6'))
    if not 1 <= workers <= 16:
        raise ValueError('COPY_PLOS_WORKERS must be between 1 and 16')
    if not source.is_dir() or not truth.is_dir():
        raise ValueError('missing run directory or truth directory')
    if any(a == b or a in b.parents or b in a.parents
           for a, b in ((source, output), (truth, output))):
        raise ValueError('output must be separate from the source and truth trees')
    papers = []
    for folder in sorted(truth.iterdir()):
        if not folder.is_dir() or not list(folder.glob('*.xml')):
            continue
        pdfs = sorted(folder.glob('*.pdf'))
        inputs = sorted((source / folder.name).glob('*.json'))
        if len(pdfs) != 1 or not (source / folder.name / 'main-text.json').is_file():
            raise ValueError(f'{folder.name}: need one PDF and main-text.json')
        papers.append((folder.name, pdfs[0], inputs))
    if not papers:
        raise ValueError('no articles with XML in truth directory')
    scripts = [home / 'tools/read_shapes.py', home / 'tools/read_signs.py',
               home / 'copy_paper.py']
    code_hashes = {str(p.relative_to(home)): digest(p) for p in scripts}
    output.mkdir(parents=True, exist_ok=True)
except (OSError, ValueError) as exc:
    sys.exit(f'copy_plos: {exc}')

def copy_one(paper):
    name, pdf, inputs = paper
    begin = time.monotonic()
    destination = output / name
    destination.mkdir(exist_ok=True)
    result = dict(id=name, pdf=str(pdf), steps={}, ok=False,
                  source_pages=sum(p.name.startswith('page-') for p in inputs))
    result['input_sha256'] = {p.name: digest(p) for p in inputs}
    result['pdf_sha256'] = digest(pdf)
    result['script_sha256'] = code_hashes
    record = destination / 'COPY-RECORD.json'
    try:
        if os.environ.get('COPY_PLOS_RESUME') == '1' and record.is_file():
            try:
                saved = json.loads(record.read_text())
                if (saved.get('ok') and saved.get('source_unchanged') and
                    all(saved.get(key) == result[key] for key in
                        ('input_sha256', 'pdf_sha256', 'script_sha256')) and
                    saved.get('artifact_sha256') and
                    all((destination / name).is_file() and digest(destination / name) == value
                        for name, value in saved['artifact_sha256'].items())):
                    return dict(saved, reused=True)
            except (OSError, ValueError):
                pass  # an incomplete/corrupt record cannot certify a copy
        with tempfile.TemporaryDirectory(prefix='.copy-plos-', dir=output) as temp:
            work = Path(temp) / name
            work.mkdir()
            for path in inputs:
                shutil.copy2(path, work / path.name)
            env = dict(os.environ, COPY_PAPER_PDF=str(pdf), TMPDIR=temp,
                       PYTHONDONTWRITEBYTECODE='1')
            # OCR failure is nonfatal, matching copy_all.sh / copy_pdf.sh, but
            # every return code is retained in the manifest and per-paper log.
            with (destination / 'ocr.log').open('w') as log:
                for script in scripts[:2]:
                    log.write(f'\n{script.name}\n')
                    log.flush()
                    rc = subprocess.run(['/usr/bin/python3', '-I', '-B',
                        str(script), str(work), str(pdf)], env=env,
                        stdout=log, stderr=subprocess.STDOUT).returncode
                    result['steps'][script.stem] = rc
            with (destination / 'copy.log').open('w') as log:
                rc = subprocess.run(['/usr/bin/python3', '-I', '-B',
                    str(scripts[2]), str(work)], env=env,
                    stdout=log, stderr=subprocess.STDOUT).returncode
            result['steps']['copy_paper'] = rc
            # Status 3: the copy is written; its native trace lists lost or
            # duplicated lines (copy.md uncertainty list, copy.trace.json).
            result['trace_failed'] = rc == 3
            if rc not in (0, 3) or not (work / 'copy.md').is_file():
                raise ValueError('copy failed; see copy.log')
            result['source_unchanged'] = all(digest(p) == result['input_sha256'][p.name] for p in inputs)
            if not result['source_unchanged']:
                raise ValueError('source JSON changed during this run')
            if any(digest(p) != code_hashes[str(p.relative_to(home))] for p in scripts):
                raise ValueError('copy scripts changed during this run; rerun the batch')
            os.replace(work / 'copy.md', destination / 'copy.md')
            if (work / 'copy.tables.json').is_file():
                os.replace(work / 'copy.tables.json', destination / 'copy.tables.json')
            if (work / 'copy.conservation.json').is_file():
                os.replace(work / 'copy.conservation.json', destination / 'copy.conservation.json')
            if (work / 'copy.audit.json').is_file():
                os.replace(work / 'copy.audit.json', destination / 'copy.audit.json')
            if (work / 'copy.checks.json').is_file():
                os.replace(work / 'copy.checks.json', destination / 'copy.checks.json')
            result['copy_sha256'] = digest(destination / 'copy.md')
            result['artifact_sha256'] = {name: digest(destination / name)
                for name in ('copy.md', 'copy.tables.json', 'copy.conservation.json', 'copy.audit.json', 'copy.checks.json')
                if (destination / name).is_file()}
            result['ok'] = True
    except (OSError, ValueError) as exc:
        result['error'] = str(exc)
        (destination / 'copy.md').unlink(missing_ok=True)  # no stale success
    result['seconds'] = round(time.monotonic() - begin, 3)
    temporary = record.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    os.replace(temporary, record)
    return result

results = []
with ThreadPoolExecutor(max_workers=workers) as pool:
    futures = [pool.submit(copy_one, paper) for paper in papers]
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        warning = any(result['steps'].get(k, 1) for k in ('read_shapes', 'read_signs'))
        print(f"{len(results)}/{len(papers)} {result['id']}: "
              f"{'reused' if result.get('reused') else 'copied' if result['ok'] else 'FAILED'}"
              f"{' (OCR warning)' if warning else ''}", flush=True)
manifest = dict(source=str(source), truth=str(truth), workers=workers,
                script_sha256=code_hashes,
                seconds=round(time.monotonic() - started, 3),
                articles=sorted(results, key=lambda r: r['id']))
(output / 'COPY-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
failed = sum(not r['ok'] for r in results)
warnings = sum(any(r['steps'].get(k, 1) for k in ('read_shapes', 'read_signs'))
               for r in results)
print(f"{len(results) - failed}/{len(papers)} copies; {warnings} OCR warnings; "
      f"{manifest['seconds']:.1f}s; "
      f"{sum(r.get('source_unchanged', False) for r in results)}/{len(results)} "
      'source JSON sets hash-verified unchanged')
sys.exit(bool(failed))
PY
