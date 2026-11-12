#!/usr/bin/env python3
"""Apply confident fixed choices to an ID-only overlay; never edit source text.

Q1 updates class assignments; Q4 updates known header subtype assignments.
Q2 no rejects an existing edge (it never guesses the replacement). Q3 and Q5
create located review flags. Missing/invalid answers and every low-confidence
choice are flags. A class promotion/demotion involving body requires review of
order, and conflicting Q1/Q4 decisions are quarantined. Output is a separate
reviewable overlay, not an automatically repaired Markdown copy.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import answer_records, decision, digest, load, load_bundle, read_jsonl, safe_asset, save


def apply(bundle, responses, threshold=0.85):
    if not 0 <= threshold <= 1:
        raise ValueError('confidence threshold outside 0..1')
    records = answer_records(bundle, responses)
    items, flags, classes, headers, rejected = [], [], {}, {}, []
    boxes = {b['id']: b for p in bundle['document']['pages'] for b in p['boxes']}
    by_target = {}
    for q in bundle['questions']:
        r = records.get(q['id'])
        state = decision(q, r, threshold)
        item = dict(question_id=q['id'], type=q['type'], targets=q['targets'], pages=q['pages'], state=state)
        if r and r['status'] == 'ok':
            item['answer'] = r['answer']
        items.append(item)
        if state in ('missing', 'invalid', 'uncertain', 'disagree'):
            flags.append(dict(item, reason=state))
        if state not in ('agree', 'disagree', 'annotation'):
            continue
        value = r['answer']['answer']
        if q['type'] == 'Q1':
            bid = q['targets'][0]
            classes[bid] = value
            by_target[bid] = item
            before_body = bid in {x for p in bundle['document']['pages'] for x in p['body_order']}
            if before_body != (value == 'body'):
                flags.append(dict(item, reason='body_membership_changed_order_requires_review'))
        elif q['type'] == 'Q4':
            headers[q['targets'][0]] = value
        elif q['type'] == 'Q2' and value == 'no':
            rejected.append(dict(targets=q['targets'], level=q['level'], question_id=q['id']))
    for bid in list(headers):
        if bid in classes and classes[bid] != 'main header':
            # The header classifier cannot override a contradictory general class.
            del headers[bid]
            if classes[bid] not in boxes[bid]['expected']:
                flags.append(dict(by_target[bid], reason='header_subtype_conflicts_with_class'))
    return dict(version=1, paper=bundle['document']['paper'], bundle_sha256=bundle['bundle_sha256'],
                responses_sha256=digest(responses), threshold=threshold, decisions=items, flags=flags,
                overlay=dict(classes=classes, header_roles=headers, rejected_edges=rejected,
                             original_body_order=[x for p in bundle['document']['pages'] for x in p['body_order']]),
                complete=len(records) == len(bundle['questions']),
                ready_for_automatic_copy=False,
                policy='ID-only review overlay; source text and source files unchanged; no inferred replacement order')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('bundle'); ap.add_argument('responses'); ap.add_argument('out')
    ap.add_argument('--threshold', type=float, default=0.85)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if Path(a.bundle).is_file():
        manifest = Path(a.bundle).resolve()
        response_root = Path(a.responses).resolve()
        if out == response_root or response_root in out.parents or out in response_root.parents:
            raise ValueError('overlay directory must be separate from responses')
        entries = load(manifest)['papers']
        for entry in entries:
            if not entry.get('bundle'):
                continue
            root = safe_asset(manifest.parent, entry['bundle'])
            if root == out or root in out.parents or out in root.parents:
                raise ValueError('overlay directory must be separate from bundles')
            bundle = load_bundle(root)
            paper = bundle['document']['paper']
            path = safe_asset(response_root, paper + '.jsonl')
            result = apply(bundle, read_jsonl(path) if path.exists() else [], a.threshold)
            save(safe_asset(out, paper + '.json'), result)
            print(f'{paper}: {len(result["flags"])} flags; complete={result["complete"]}')
        return
    if out == Path(a.responses).resolve() or Path(a.bundle).resolve() in out.parents:
        raise ValueError('overlay must not overwrite responses or bundle files')
    result = apply(load_bundle(a.bundle), read_jsonl(a.responses), a.threshold)
    save(out, result)
    print(f'{result["paper"]}: {len(result["flags"])} flags; complete={result["complete"]}')


if __name__ == '__main__':
    main()
