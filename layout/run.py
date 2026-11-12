#!/usr/bin/env python3
"""Layout sort of a paper: main header, main text, floats, references and other, in reading order.

usage: /usr/bin/python3 -I layout/run.py PDF OUT_DIR [--copy COPY_MD] [--python PATH]
       /usr/bin/python3 -I layout/run.py --batch LIST OUT_ROOT [--python PATH]
         (LIST: one line per paper: NAME<TAB>PDF[<TAB>ignored<TAB>COPY_MD])

The element boxer (rules 1-5) is run on the PDF into OUT_DIR/boxer first, so that its page JSON and
the reading layer read by layout/words.py come from the same code (character numbers must agree).
Steps and rules: layout/rules.py. The pixel steps run in a Python with numpy and Pillow: --python,
else LAYOUT_PYTHON, else the local vLLM environment.
Outputs in OUT_DIR: boxer/, words.json, layout.json, layout.txt, sorted.pdf, report.json.
Exit status: 0; 3 when a built-in check failed (report.json "checks"); 4 for a scanned paper (not sorted);
2 on a usage or input error.
"""
import glob, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
DEFAULT_PY = '/mnt/ai/projects/optionsdds/trials/vlm-trial/envs/monkeyocrv2-vllm-0.25.1/bin/python'


def one(pdf, out, copy=None, py=None):
    os.makedirs(out, exist_ok=True); paper = os.path.join(out, 'boxer')
    if not glob.glob(os.path.join(paper, 'page-*.json')):
        os.makedirs(paper, exist_ok=True)
        r = subprocess.run(['/usr/bin/python3', '-I', os.path.join(REPO, 'standalone', 'element_boxer_sc.py'), '--pdf', pdf, '--all-pages', '--out', paper, '--no-draw'],
                           stdout=open(os.path.join(out, 'boxer.log'), 'w'), stderr=subprocess.STDOUT)
        if r.returncode != 0 or not glob.glob(os.path.join(paper, 'page-*.json')): print(f'boxer failed: {out}/boxer.log'); return 2
    with open(os.path.join(out, 'words.log'), 'w') as log:
        r = subprocess.run(['/usr/bin/python3', '-I', os.path.join(HERE, 'words.py'), pdf, paper, os.path.join(out, 'words.json')], stdout=log, stderr=subprocess.STDOUT)
    if r.returncode not in (0, 1): print(f'word boxes failed: {out}/words.log'); return 2
    cmd = [py or os.environ.get('LAYOUT_PYTHON') or DEFAULT_PY, '-I', os.path.join(HERE, 'worker.py'), os.path.join(out, 'words.json'), pdf, out]
    if copy: cmd += ['--copy', copy]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=open(os.path.join(out, 'worker.log'), 'w'), text=True)
    print(r.stdout.strip() or f'worker failed: {out}/worker.log')
    return r.returncode


def main(argv):
    py = None
    if '--python' in argv: i = argv.index('--python'); py = argv[i + 1]; del argv[i:i + 2]
    if argv[:1] == ['--batch'] and len(argv) == 3:
        worst = 0
        for line in open(argv[1]):
            f = line.rstrip('\n').split('\t')
            if len(f) < 2: continue
            print(f[0], end=': ', flush=True)
            rc = one(f[1], os.path.join(argv[2], f[0]), f[3] if len(f) > 3 and f[3] else None, py); worst = max(worst, rc)
        return worst
    copy = None
    if '--copy' in argv: i = argv.index('--copy'); copy = argv[i + 1]; del argv[i:i + 2]
    if len(argv) != 2: print(__doc__); return 2
    return one(argv[0], argv[1], copy, py)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
