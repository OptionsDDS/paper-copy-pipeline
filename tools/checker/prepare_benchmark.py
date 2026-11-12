#!/usr/bin/env python3
"""Select audited positives/negatives and build full-paper question bundles.

Selection is deterministic: greedy coverage of supported fault families, then
confirmed-present faults, located faults, and paper ID. Negatives require zero
MAJORs AS AUDITED, never just a later 'fixed' status. No fault text or labels go
to build_questions or run_model. Missing inputs and negative shortages are
recorded explicitly; --regenerate-missing uses the unchanged local boxer.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import digest, file_hash, load, save

ROOT = Path(__file__).resolve().parents[2]
# These are screening capabilities, not a claim to diagnose every cause instance.
CAUSE_TYPES = {
    'FLOAT': ['Q1', 'Q2'], 'LETT': ['Q1', 'Q2'], 'HEAD': ['Q1', 'Q2', 'Q3'],
    'COLS': ['Q2'], 'FRONT': ['Q1', 'Q3', 'Q4'], 'GATE': ['Q1', 'Q3', 'Q5'],
    'TUND': ['Q1', 'Q3', 'Q5'], 'FLOW': ['Q2'], 'CAPT': ['Q1', 'Q5'],
    'LOST': ['Q3'],
}


def page_numbers(value):
    """Parse explicit page lists/ranges only; never turn unknown pages into all pages."""
    if isinstance(value, int) and value > 0:
        return [value]
    if not isinstance(value, str) or not re.fullmatch(r'\s*\d+(?:\s*(?:[-–,;/]|and)\s*\d+)*\s*', value):
        return []
    parts = re.split(r'\s*(?:[,;/]|and)\s*', value.strip())
    pages = set()
    for part in parts:
        pair = re.split(r'\s*[-–]\s*', part)
        a, b = int(pair[0]), int(pair[-1])
        if not 0 < a <= b < 1000:
            return []
        pages.update(range(a, b + 1))
    return sorted(pages)


def select(pool, sets, positives, negatives, extra_negative=None):
    available = [p for p in pool['papers'] if p['set'] in sets]
    negative = sorted([p for p in available if p['majors_listed'] == 0], key=lambda p: p['paper'])[:negatives]
    if extra_negative and len(negative) < negatives:
        extra = next(p for p in pool['papers'] if p['paper'] == extra_negative)
        if extra['majors_listed'] != 0 or extra in negative:
            raise ValueError('extra negative is not a distinct audited error-free paper')
        negative.append(extra)
    candidates = [p for p in available if p['majors_listed'] > 0 and any(
        f['paper'] == p['paper'] and f['cause'] in CAUSE_TYPES and f['r25_status'] != 'fixed' for f in pool['faults'])]
    chosen, covered = [], set()
    while candidates and len(chosen) < positives:
        def priority(p):
            fs = [f for f in pool['faults'] if f['paper'] == p['paper'] and f['cause'] in CAUSE_TYPES and f['r25_status'] != 'fixed']
            return (-len({f['cause'] for f in fs} - covered),
                    -sum(f['r25_status'] == 'still present' for f in fs),
                    -sum(bool(page_numbers(f.get('page'))) for f in fs), p['paper'])
        p = min(candidates, key=priority)
        candidates.remove(p); chosen.append(p)
        covered.update(f['cause'] for f in pool['faults'] if f['paper'] == p['paper'] and f['cause'] in CAUSE_TYPES)
    return chosen, negative


def truth(pool, selected):
    names = {p['paper']: p for p in selected}
    faults = []
    for f in pool['faults']:
        if f['paper'] not in names:
            continue
        record = dict(f, pages=page_numbers(f.get('page')), types=CAUSE_TYPES.get(f['cause'], []),
                      question_ids=[], truth_status='historical_audit_not_revalidated_on_checker_input')
        record['exclusions'] = []
        if f['r25_status'] == 'fixed':
            record['exclusions'].append('already_marked_fixed')
        if not record['pages']:
            record['exclusions'].append('audit_has_no_explicit_page')
        if not record['types']:
            record['exclusions'].append('outside_sort_order_checker_scope')
        faults.append(record)
    return dict(version=1, source_population=pool['summary'], faults=faults,
                negative_papers=[p['paper'] for p in selected if p['majors_listed'] == 0],
                warning='Audit truth is about historical copies; checker sees boxer records. Page/type screening is a proxy, '
                        'not verified fault recall. Exact recall requires question_ids and current-input revalidation.')


def prepare(args):
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise ValueError('benchmark manifest exists; use a fresh output directory')
    pool = load(args.fault_pool)
    pos, neg = select(pool, args.sets, args.positives, args.negatives, args.extra_negative)
    selected = pos + neg
    maps = {}
    for path in args.pdf_maps:
        maps.update(load(path))
    issues = []
    if len(pos) != args.positives:
        issues.append(f'requested {args.positives} positives; eligible papers: {len(pos)}')
    if len(neg) != args.negatives:
        issues.append(f'requested {args.negatives} audited negatives; available: {len(neg)}')
    save(output / 'truth.json', truth(pool, selected))
    manifest = dict(version=1, fault_pool_sha256=file_hash(args.fault_pool), sets=args.sets,
                    requested=dict(positives=args.positives, negatives=args.negatives),
                    selected=dict(positives=len(pos), negatives=len(neg)), issues=issues, papers=[],
                    boxer_sha256=file_hash(ROOT / 'standalone/element_boxer_sc.py'),
                    complete=False, max_output_bytes=args.max_output_bytes)
    sources = [Path(p) for p in args.records_roots]
    for paper in selected:
        name = paper['paper']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError('invalid paper identifier')
        records = next((root / name for root in sources if (root / name / 'main-text.json').is_file()), None)
        manifest['papers'].append(dict(paper=name, label='negative' if paper['majors_listed'] == 0 else 'positive',
                                       pdf=maps.get(name), source_records=str(records) if records else None,
                                       input_kind='supplied_records' if records else 'missing'))
    save(output / 'manifest.json', manifest)
    def task(entry):
        name = entry['paper']
        pdf = Path(entry['pdf']) if entry['pdf'] else None
        if pdf is None or not pdf.is_file():
            return dict(entry, error='PDF unavailable')
        records = Path(entry['source_records']) if entry['source_records'] else None
        log = output / 'logs' / f'{name}.log'
        log.parent.mkdir(exist_ok=True)
        env = dict(os.environ, BOXER_SC_BACKGROUND='white', PYTHONDONTWRITEBYTECODE='1')
        with log.open('w') as stream:
            if records is None:
                if not args.regenerate_missing:
                    return dict(entry, error='boxer records missing; regeneration not requested')
                records = output / 'regenerated' / name
                boxer = str(ROOT / 'standalone/element_boxer_sc.py')
                for flags in [ ['--pdf', str(pdf), '--all-pages', '--out', str(records), '--no-draw'],
                               ['--paper', str(records), '--no-draw'] ]:
                    subprocess.run(['/usr/bin/python3', '-I', boxer, *flags], stdout=stream, stderr=stream,
                                   check=True, timeout=1800, env=env, cwd=ROOT)
                entry = dict(entry, source_records=str(records), input_kind='regenerated_with_unchanged_boxer')
            relative = 'bundles/' + name
            subprocess.run(['/usr/bin/python3', '-I', str(Path(__file__).with_name('build_questions.py')),
                            str(records), str(pdf), str(output / relative), '--paper', name],
                           stdout=stream, stderr=stream, check=True, timeout=1800, env=env, cwd=ROOT)
            bundle = load(output / relative / 'bundle.json')
            return dict(entry, bundle=relative, bundle_sha256=bundle['bundle_sha256'],
                        pages=len(bundle['document']['pages']),
                        questions=dict(Counter(q['type'] for q in bundle['questions'])))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        jobs = {executor.submit(task, item): i for i, item in enumerate(manifest['papers'])}
        for job in as_completed(jobs):
            i = jobs[job]
            try:
                manifest['papers'][i] = job.result()
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                manifest['papers'][i]['error'] = str(exc)
            save(output / 'manifest.json', manifest)
            entry = manifest['papers'][i]
            print(entry['paper'], entry.get('error', entry.get('questions')), flush=True)
            size = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
            if size > args.max_output_bytes:
                raise RuntimeError('benchmark exceeded configured size limit')
    manifest['complete'] = not issues and all('bundle' in item for item in manifest['papers'])
    manifest['bundles_complete'] = all('bundle' in item for item in manifest['papers'])
    manifest['bytes'] = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    save(output / 'manifest.json', manifest)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fault-pool', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--pdf-maps', nargs='+', required=True)
    ap.add_argument('--records-roots', nargs='+', required=True)
    ap.add_argument('--sets', nargs='+', default=['AC', 'AD', 'AE', 'AF'])
    ap.add_argument('--positives', type=int, default=10); ap.add_argument('--negatives', type=int, default=10)
    ap.add_argument('--extra-negative', help='explicitly authorized paper from outside the requested sets')
    ap.add_argument('--regenerate-missing', action='store_true')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--max-output-bytes', type=int, default=2_000_000_000)
    a = ap.parse_args()
    if min(a.workers, a.positives, a.negatives, a.max_output_bytes) < 1:
        ap.error('counts and limits must be positive')
    prepare(a)


if __name__ == '__main__':
    main()
