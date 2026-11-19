#!/usr/bin/python3 -I
"""r5_frontcheck.py OUTDIR -- lane r5-line: the first-page check of the front matter.

Where the lane changed lines of page 1, copy_pdf.sh ran rules 6-8 twice: on the pages as built (OUTDIR) and with page 1
as built without the lane (OUTDIR/r5base). If the front-matter reading (authors.json) finds another title text, or
another number of authors or of affiliations, the build without the lane is kept: every file rules 6-8 wrote in
OUTDIR/r5base replaces its copy in OUTDIR. The decision goes to OUTDIR/r5-frontcheck.json; OUTDIR/r5base and
OUTDIR/r5base-page-01.json are removed."""
import json
import os
import shutil
import sys


def summary(d):
    try:
        a = json.load(open(os.path.join(d, 'authors.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return None
    t = a.get('title')
    title = t.get('text') if isinstance(t, dict) else t
    return {'title': title, 'authors': len(a.get('authors') or []), 'affiliations': len(a.get('affiliations') or [])}


def main(out):
    base_dir = os.path.join(out, 'r5base')
    record = {'lane': 'r5-line', 'check': 'first page: title text, authors and affiliations against the build without the lane'}
    if os.path.isdir(base_dir):
        lane, base = summary(out), summary(base_dir)
        record.update(lane=lane, base=base)
        if lane != base and base is not None:
            record['kept'] = 'build without the lane'
            for f in sorted(os.listdir(base_dir)):
                src = os.path.join(base_dir, f)
                if os.path.isfile(src) and f != 'boxer.log':
                    shutil.copyfile(src, os.path.join(out, f))
        else:
            record['kept'] = 'lane build'
        shutil.rmtree(base_dir)
    p = os.path.join(out, 'r5base-page-01.json')
    if os.path.exists(p):
        os.remove(p)
    with open(os.path.join(out, 'r5-frontcheck.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=1, ensure_ascii=False)
    print('r5 first-page check:', record.get('kept'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
