#!/usr/bin/env python3
"""Run every tools/test_*.py in its own isolated Python unittest process.

unittest discovery adds only this repository's explicit tools directory for
sibling test fixtures; unlike direct script execution under -I, it also invokes
test_regions.load_tests. No tests are skipped or combined into a shared process.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import subprocess
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('out'); ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    if a.workers < 1:
        ap.error('workers must be positive')
    root = Path(__file__).resolve().parents[2]
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    temporary = out / 'tmp'; temporary.mkdir(exist_ok=True)
    def run(path):
        start = time.monotonic()
        cmd = ['/usr/bin/python3', '-I', '-m', 'unittest', 'discover', '-s', str(root / 'tools'), '-p', path.name]
        with (out / (path.stem + '.log')).open('w') as log:
            result = subprocess.run(cmd, stdout=log, stderr=log, cwd=root,
                                    env=dict(os.environ, TMPDIR=str(temporary)), timeout=600)
        text = (out / (path.stem + '.log')).read_text()
        count = re.search(r'Ran (\d+) test', text)
        return dict(test=path.name, exit_code=result.returncode,
                    tests=int(count[1]) if count else None, seconds=round(time.monotonic() - start, 2))
    results = []
    with ThreadPoolExecutor(max_workers=a.workers) as executor:
        jobs = [executor.submit(run, p) for p in sorted((root / 'tools').glob('test_*.py'))]
        for job in as_completed(jobs):
            result = job.result(); results.append(result)
            if result['exit_code']:
                print(result, flush=True)
    (out / 'results.json').write_text(json.dumps(sorted(results, key=lambda r: r['test']), indent=2) + '\n')
    print(f'{len(results)} test files; {sum(r["tests"] or 0 for r in results)} tests; '
          f'{sum(r["exit_code"] != 0 for r in results)} failed files', flush=True)
    raise SystemExit(any(r['exit_code'] or not r['tests'] for r in results))


if __name__ == '__main__':
    main()
