#!/usr/bin/env python3
"""Evaluate the second pass against audited faults.

usage: evaluate.py --copies DIR --faults F.json [F.json ...] --clean P1,P2,... [--papers P1,...]
                   [--out OUT_DIR] [--rerun] [--pdfs MAP.json ...]

DIR holds one folder per paper (copy.md, copy.trace.json, page-NN.json). Fault
files are lists of {"id", "paper", "pages", "copy_line", "expected_rules", ...}.
Each paper is run once (secondpass.run, nothing written into DIR); the report
goes to OUT_DIR/<paper>.secondpass.json (reused unless --rerun).

A fault is caught by a rule when an item of that rule on the same paper names
one of the fault's pages ("page" match); it is also "located" when the item's
copy line is within three lines of the fault's copy line (faults without a
copy line are located by page). Every item on a paper listed in --clean is a
false alarm of its rule. Items on failing papers that match no fault are
counted as unmatched (they may be real errors the audit did not list).
Writes OUT_DIR/evaluation.json and prints a summary.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import secondpass  # noqa: E402

NEAR = 3


def load_report(folder, out, rerun, pdf=None):
    path = out/f'{folder.name}.secondpass.json'
    if path.is_file() and not rerun:
        return json.loads(path.read_text(encoding='utf-8'))
    _, report = secondpass.run(folder, pdf)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    return report


def matches(fault, item):
    if not set(item.get('pages') or []) & set(fault['pages']): return None
    if fault.get('copy_line') and item.get('copy_line'):
        return 'located' if abs(item['copy_line']-fault['copy_line']) <= NEAR else 'page'
    return 'located' if not fault.get('copy_line') else 'page'


def evaluate(copies, faults, clean, papers, out, rerun=False, pdfs=None):
    out.mkdir(parents=True, exist_ok=True)
    reports = {}
    for p in papers:
        folder = copies/p
        if not (folder/'copy.md').is_file(): continue
        reports[p] = load_report(folder, out, rerun, (pdfs or {}).get(p))
    rules = sorted({r['rule'] for rep in reports.values() for r in rep['rules']})
    per_fault = []
    for f in faults:
        rep = reports.get(f['paper'])
        if rep is None: continue
        caught = defaultdict(lambda: None)
        for item in rep['findings']:
            m = matches(f, item)
            if m and caught[item['rule']] != 'located': caught[item['rule']] = m
        per_fault.append(dict(id=f['id'], paper=f['paper'], pages=f['pages'], family=f.get('family'),
                              borderline=f.get('borderline', False), expected=f.get('expected_rules', []),
                              description=f.get('description', '')[:120],
                              caught={r: v for r, v in caught.items() if v}))
    used = defaultdict(set)
    for f in faults:
        rep = reports.get(f['paper'])
        if not rep: continue
        for k, item in enumerate(rep['findings']):
            if matches(f, item): used[f['paper']].add(k)
    false_alarms = {p: Counter(i['rule'] for i in reports[p]['findings']) for p in clean if p in reports}
    unmatched = {p: Counter(i['rule'] for k, i in enumerate(rep['findings']) if k not in used[p])
                 for p, rep in reports.items() if p not in clean}
    recall = {}
    for r in rules:
        exp = [x for x in per_fault if r in x['expected']]
        recall[r] = dict(expected=len(exp), caught_page=sum(1 for x in exp if r in x['caught']),
                         caught_located=sum(1 for x in exp if x['caught'].get(r) == 'located'),
                         caught_any_fault=sum(1 for x in per_fault if r in x['caught']),
                         false_alarms=sum(c[r] for c in false_alarms.values()),
                         false_alarm_papers=sum(1 for c in false_alarms.values() if c[r]),
                         unmatched_on_failing=sum(c[r] for c in unmatched.values()))
    errors = {p: [f"rule {r['rule']}: {r['error']}" for r in rep['rules'] if r.get('error')] for p, rep in reports.items()}
    result = dict(per_fault=per_fault, recall=recall, false_alarms={p: dict(c) for p, c in false_alarms.items()},
                  unmatched={p: dict(c) for p, c in unmatched.items()}, errors={p: e for p, e in errors.items() if e},
                  faults=len(per_fault), caught_any=sum(1 for x in per_fault if x['caught']),
                  located_any=sum(1 for x in per_fault if 'located' in x['caught'].values()))
    (out/'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    return result


def main(argv):
    args = list(argv)

    def take(flag, many=False):
        if flag not in args: return None
        i = args.index(flag); j = i+1
        while j < len(args) and not args[j].startswith('--'): j += 1
        vals = args[i+1:j]; del args[i:j]
        return vals if many else (vals[0] if vals else None)
    copies = Path(take('--copies')); fault_files = take('--faults', True) or []
    clean = (take('--clean') or '').split(','); papers = take('--papers')
    out = Path(take('--out') or (copies/'secondpass-eval')); rerun = '--rerun' in args
    pdf_maps = take('--pdfs', True) or []
    pdfs = {}
    for m in pdf_maps: pdfs.update(json.loads(Path(m).read_text()))
    faults = [f for path in fault_files for f in json.loads(Path(path).read_text(encoding='utf-8'))]
    papers = papers.split(',') if papers else sorted({f['paper'] for f in faults} | set(c for c in clean if c))
    res = evaluate(copies, faults, [c for c in clean if c], papers, out, rerun, pdfs)
    print(f"faults {res['faults']}: caught at the right page {res['caught_any']}, located {res['located_any']}")
    for r, v in res['recall'].items():
        print(f"rule {r:2}: expected {v['expected']:3} caught {v['caught_page']:3} (located {v['caught_located']:3}); "
              f"catches {v['caught_any_fault']:3} faults in all; false alarms {v['false_alarms']} on {v['false_alarm_papers']} clean paper(s); "
              f"unmatched on failing papers {v['unmatched_on_failing']}")
    for p, e in res['errors'].items(): print('ERROR', p, e)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
