"""One line per paper from layout run folders: usage: python3 -I layout/summary.py RUN_ROOT [TRUTH_IDS...]
TRUTH_IDS: papers whose copy was audited error-free (only their comparison is a measure)."""
import json, os, sys
root, truth = sys.argv[1], set(sys.argv[2:])
for name in sorted(os.listdir(root)):
    f = os.path.join(root, name, 'report.json')
    if not os.path.exists(f): print(f'{name}: no report'); continue
    r = json.load(open(f)); c = r.get('compare', {}); ch = r.get('checks', {}); ref = r.get('references', {})
    if r.get('scanned'): print(f'{name}: scanned, not sorted'); continue
    print(f"{name}{' *' if name in truth else ''}: gutters {len(r.get('gutters', []))} | main in copy order {c.get('main_in_copy_order')}% | "
          f"refs {'yes' if ref.get('found') else 'NO'} ({ref.get('style')}), words in order {c.get('reference_words_in_order')} | "
          f"checks failed {ch.get('failed')} | flags {len(r.get('flags', []))}")
