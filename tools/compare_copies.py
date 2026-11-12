#!/usr/bin/env python3
"""Compare two copies of one paper: body words in the same order, reference words in the same order,
and the front matter (title, authors, affiliations).

usage: /usr/bin/python3 -I tools/compare_copies.py OLD_DIR NEW_DIR [--json OUT]

OLD_DIR and NEW_DIR hold copy.md and (when the copier wrote it) copy.trace.json. With the trace, the
body is the copy's paragraph, heading, list_item, abstract_part and footnote (side text) units in copy order, the references
its reference units, and the front matter its title, author and affiliation units; without a trace the
copy text is cut as layout/worker.py --copy cuts it (lines before the references heading, without table
rows, captions, page marks and notes). Words are lowercased, stripped to letters and digits, line-end
hyphens joined (layout/worker.py norm). The measure is the longest common subsequence of the old copy's
words found in the new copy in the same order, over the old copy's words (difflib, no autojunk): 100
means every old body word is in the new copy in the old order. Prints one line and, with --json, writes
the numbers and the differing stretches (up to 20 words each).
"""
import collections, difflib, json, os, re, sys

BODY_KINDS = ('paragraph', 'heading', 'list_item', 'abstract_part', 'footnote')   # footnote: side text, printed as a quote in the body stream (as the worker's measure counts it)
FRONT_KINDS = ('title', 'author', 'affiliation')


def norm(tokens):
    out = []; carry = ''
    for t in tokens:
        if carry: t = carry + t; carry = ''
        if t.endswith('-') and len(t) > 1: carry = t[:-1]; continue
        t = re.sub(r'[^0-9a-z]', '', t.lower())
        if t: out.append(t)
    if carry: out.append(re.sub(r'[^0-9a-z]', '', carry.lower()))
    return out


def units_of(folder):
    """(body text, references text, front units) from the trace, else from the copy text."""
    trace = os.path.join(folder, 'copy.trace.json'); copy = os.path.join(folder, 'copy.md')
    if os.path.isfile(trace):
        try:
            units = json.load(open(trace, encoding='utf-8'))['units']
            body = [u['text'] for u in units if u['kind'] in BODY_KINDS]
            refs = [u['text'] for u in units if u['kind'] == 'reference']
            front = [(u['kind'], ' '.join(u['text'].split())) for u in units if u['kind'] in FRONT_KINDS]
            return body, refs, front, 'trace'
        except (OSError, ValueError, KeyError): pass
    cp = open(copy, encoding='utf-8').read().splitlines()
    end = next((i for i, l in enumerate(cp) if re.match(r'^#+ .*(references|bibliography|literature cited)', l, re.I)), None)
    stop = next((i for i, l in enumerate(cp) if l.startswith(('## Unpaired floats', '## Places the program'))), len(cp))
    body = [re.sub(r'^#+ ', '', l) for l in cp[:end if end is not None else stop] if l.strip() and not l.startswith(('|', '**Fig', '**Table', '**Box', '<!--', '---', '> ['))]
    refs = [l[2:] for l in cp[(end or 0) + 1:stop] if l.startswith('- ')] if end is not None else []
    front = [('title', l[2:].strip()) for l in cp if l.startswith('# ')][:1]
    return body, refs, front, 'text'


def in_order(old, new):
    """(share of old words found in new in the same order, differing stretches)."""
    if not old: return None, []
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    same = sum(b.size for b in sm.get_matching_blocks())
    diffs = [dict(op=tag, old=' '.join(old[i1:i1 + 20]), old_words=i2 - i1, new=' '.join(new[j1:j1 + 20]), new_words=j2 - j1)
             for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal' and (i2 - i1 >= 3 or j2 - j1 >= 3)]
    return round(100 * same / len(old), 2), diffs


def compare(old_dir, new_dir):
    ob, orf, ofr, osrc = units_of(old_dir); nb, nrf, nfr, nsrc = units_of(new_dir)
    body_old, body_new = norm(' '.join(ob).split()), norm(' '.join(nb).split())
    refs_old, refs_new = norm(' '.join(orf).split()), norm(' '.join(nrf).split())
    body, body_diffs = in_order(body_old, body_new); refs, ref_diffs = in_order(refs_old, refs_new)
    front_missing = [f for f in ofr if f not in nfr]; front_added = [f for f in nfr if f not in ofr]
    return dict(old=os.path.abspath(old_dir), new=os.path.abspath(new_dir), source=dict(old=osrc, new=nsrc),
                body=dict(old_words=len(body_old), new_words=len(body_new), in_order=body, differences=body_diffs),
                references=dict(old_entries=len(orf), new_entries=len(nrf), old_words=len(refs_old), new_words=len(refs_new), in_order=refs, differences=ref_diffs),
                front=dict(unchanged=not front_missing and not front_added, old=len(ofr), new=len(nfr), missing=front_missing, added=front_added))


def main(argv):
    out = None
    if '--json' in argv: i = argv.index('--json'); out = argv[i + 1]; del argv[i:i + 2]
    if len(argv) != 2: print(__doc__); return 2
    r = compare(argv[0], argv[1])
    if out: json.dump(r, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f"body {r['body']['in_order']}% of {r['body']['old_words']} words in order (new {r['body']['new_words']}) | "
          f"references {r['references']['in_order']}% of {r['references']['old_words']} words ({r['references']['old_entries']} -> {r['references']['new_entries']} entries) | "
          f"front matter {'unchanged' if r['front']['unchanged'] else 'CHANGED: missing ' + str(r['front']['missing'])[:200] + ' added ' + str(r['front']['added'])[:200]} ({r['source']['old']}/{r['source']['new']})")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
