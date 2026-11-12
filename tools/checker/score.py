#!/usr/bin/env python3
"""Score responses without conflating page/type screening with exact fault recall.

Exact recall requires manually localized question_ids and truth_status=verified
on these input records. Historical faults with explicit pages can additionally
be screened by page and question type; this deliberately weaker proxy is named
as such. Unknown pages, already-fixed faults and unsupported causes are listed,
never wildcard-matched. Unanswered work does not become a successful negative.
Low confidence counts as a review alarm; runtime failures are reported apart.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TYPES, answer_records, decision, load, load_bundle, read_jsonl, safe_asset, save


def rate(hits, total):
    return hits / total if total else None


def evaluate(bundles, truth, responses, threshold=0.85):
    if not 0 <= threshold <= 1:
        raise ValueError('invalid threshold')
    questions, states = {}, {}
    paper_qs = {}
    negatives = set(truth['negative_papers'])
    for paper, bundle in bundles.items():
        if paper != bundle['document']['paper']:
            raise ValueError('paper/bundle mismatch')
        records = answer_records(bundle, responses.get(paper, []))
        paper_qs[paper] = bundle['questions']
        for q in bundle['questions']:
            if q['id'] in questions:
                raise ValueError('duplicate question identity across papers')
            questions[q['id']] = dict(q, paper=paper)
            states[q['id']] = decision(q, records.get(q['id']), threshold)
    alarms = {qid for qid, state in states.items() if state in ('disagree', 'uncertain')}
    disagreements = {qid for qid, state in states.items() if state == 'disagree'}
    valid_states = {'agree', 'disagree', 'uncertain', 'annotation'}
    complete = all(s in valid_states for s in states.values()) and bool(questions)
    faults = []
    for fault in truth['faults']:
        row = dict(id=fault['id'], paper=fault['paper'], types=fault['types'],
                   exclusions=list(fault.get('exclusions', [])))
        if fault['paper'] not in paper_qs:
            row['exclusions'].append('no_question_bundle')
        exact_ids = fault.get('question_ids', [])
        if any(qid not in questions or questions[qid]['paper'] != fault['paper'] for qid in exact_ids):
            raise ValueError(f'invalid truth question IDs for {fault["id"]}')
        exact = bool(exact_ids) and fault.get('truth_status') == 'verified'
        if exact:
            if fault.get('bundle_sha256') != bundles[fault['paper']]['bundle_sha256']:
                raise ValueError(f'stale exact truth for {fault["id"]}: bundle hash required')
            row['exclusions'] = [e for e in row['exclusions'] if e == 'no_question_bundle']
            row['types'] = sorted({questions[qid]['type'] for qid in exact_ids})
        candidates = exact_ids if exact else [q['id'] for q in paper_qs.get(fault['paper'], [])
            if q['type'] in fault['types'] and set(q['pages']) & set(fault.get('pages', []))]
        if not row['exclusions'] and not candidates:
            row['exclusions'].append('no_matching_questions')
        row.update(mode='exact' if exact else 'historical_page_type_screen', candidates=candidates,
                   caught=bool(alarms & set(candidates)) if not row['exclusions'] else None,
                   disagreement_caught=bool(disagreements & set(candidates)) if not row['exclusions'] else None,
                   answered=bool(candidates) and all(states[qid] in valid_states for qid in candidates))
        faults.append(row)
    def recalls(mode, kind=None):
        eligible = [f for f in faults if not f['exclusions'] and f['mode'] == mode and
                    (kind is None or kind in f['types'])]
        hits, strong = 0, 0
        for f in eligible:
            ids = {qid for qid in f['candidates'] if kind is None or questions[qid]['type'] == kind}
            hits += bool(ids & alarms)
            strong += bool(ids & disagreements)
        done = bool(eligible) and all(f['answered'] for f in eligible)
        return dict(positives=len(eligible), caught=hits, confident_disagreement_caught=strong,
                    recall=rate(hits, len(eligible)) if done else None,
                    confident_disagreement_recall=rate(strong, len(eligible)) if done else None,
                    complete=done)
    per_type = {}
    for kind in TYPES:
        ids = {qid for qid, q in questions.items() if q['paper'] in negatives and q['type'] == kind}
        answered = {qid for qid in ids if states[qid] in valid_states}
        per_type[kind] = dict(exact=recalls('exact', kind),
            historical_page_type_screen=recalls('historical_page_type_screen', kind),
            negative_questions=len(ids), answered_negative_questions=len(answered),
            false_alarms=len(answered & alarms), confident_false_alarms=len(answered & disagreements),
            false_alarm_rate=rate(len(answered & alarms), len(ids)) if answered == ids else None,
            observed_false_alarm_rate=rate(len(answered & alarms), len(answered)))
    negative_rows = []
    for paper in sorted(negatives):
        ids = {q['id'] for q in paper_qs.get(paper, [])}
        negative_rows.append(dict(paper=paper, questions=len(ids),
            complete=bool(ids) and all(states[qid] in valid_states for qid in ids),
            false_alarm=bool(ids & alarms), alarm_count=len(ids & alarms),
            operational_flags=sum(states[qid] in ('invalid', 'missing') for qid in ids)))
    return dict(version=1, threshold=threshold, complete=complete,
        exact=recalls('exact'), historical_page_type_screen=recalls('historical_page_type_screen'),
        per_type=per_type, negatives=negative_rows,
        negative_paper_false_alarm_rate=rate(sum(p['false_alarm'] for p in negative_rows), len(negative_rows))
            if negative_rows and all(p['complete'] for p in negative_rows) else None,
        question_states=dict(Counter(states.values())), faults=faults,
        exclusions=dict(Counter(e for f in faults for e in f['exclusions'])),
        limitation=truth.get('warning', 'Historical truth requires current-input verification.'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest'); ap.add_argument('responses'); ap.add_argument('out')
    ap.add_argument('--truth', help='optional manually localized and revalidated truth JSON')
    ap.add_argument('--threshold', type=float, default=0.85)
    a = ap.parse_args()
    manifest_path = Path(a.manifest).resolve()
    manifest = load(manifest_path)
    bundles = {p['paper']: load_bundle(safe_asset(manifest_path.parent, p['bundle']))
               for p in manifest['papers'] if p.get('bundle')}
    responses = {paper: read_jsonl(path) if path.exists() else [] for paper in bundles
                 for path in [Path(a.responses) / (paper + '.jsonl')]}
    result = evaluate(bundles, load(a.truth or manifest_path.parent / 'truth.json'), responses, a.threshold)
    result['benchmark_issues'] = manifest['issues']
    result['complete'] = result['complete'] and manifest['complete']
    save(a.out, result)
    print(f'{len(bundles)} papers; complete={result["complete"]}; states={result["question_states"]}')


if __name__ == '__main__':
    main()
