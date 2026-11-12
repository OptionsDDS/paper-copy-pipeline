"""Rule 6: references.

Numbered reference lists must run 1, 2, 3 ... without gaps, repeats or steps
back; an entry holding two or more complete citation tails (year;volume:pages
or year, volume, pages) is fused; numeric citations in the body ([12], [3-5],
or a superscript run after a word such as "visits.23,24") must name entries
that exist. Each gap, fused entry, and the set of cited numbers with no entry
are listed.
"""
import re

from common import BODY_KINDS, finding

NAME = 'references'
NUM = re.compile(r'^\s*\[?(\d{1,3})[.\])]?\s+\S')
TAIL = re.compile(r'\b(?:19|20)\d\d\s*[;,]\s*\d+\s*(?:\(\s*[\dS-]+\s*\))?\s*[:,]\s*[A-Za-z]?\d+(?:\s*[-–]\s*[A-Za-z]?\d+)?')
BRACKET = re.compile(r'\[(\d{1,3}(?:\s*[-–,]\s*\d{1,3})*)\]')
SUPER = re.compile(r'(?<=[a-z\)\]][.,])(\d{1,3}(?:[-–,]\d{1,3})*)(?=\s+[A-Z(]|\s*$)')


def expand(s):
    out = set()
    for part in re.split(r'\s*,\s*', s):
        m = re.match(r'(\d+)\s*[-–]\s*(\d+)$', part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < b-a < 60: out.update(range(a, b+1))
        elif part.strip().isdigit(): out.add(int(part))
    return out


def entries(paper):
    return [u for u in paper.content_units if u['kind'] == 'reference']


def check(paper):
    """References: numbering gaps or fused entries, citations without a reference."""
    findings = []
    refs = entries(paper)
    numbered = [(int(NUM.match(u['text']).group(1)), u) for u in refs if NUM.match(u['text'])]
    def pages(u): return [l['page'] for l in paper.unit_lines(u)][:1]
    if len(numbered) >= 3 and len(numbered) >= .6*len(refs):
        prev = None
        for n, u in numbered:
            if prev is not None and n != prev+1:
                what = f'{prev+1}-{n-1} missing' if n > prev+1 else f'{n} after {prev}'
                findings.append(finding(6, f"reference numbering {what}: {u['text'][:50]!r}", pages=pages(u),
                                        unit=u['id'], offset=u['span'][0]))
            prev = n
    for u in refs:
        tails = TAIL.findall(u['text'])
        if len(tails) >= 2:
            findings.append(finding(6, f"one reference entry holds {len(tails)} citations (fused entries): {u['text'][:60]!r}",
                                    pages=pages(u), unit=u['id'], offset=u['span'][0], tails=len(tails)))
    if len(numbered) >= 3:
        have = {n for n, _ in numbered}
        cited = {}
        for u in paper.content_units:
            if u['kind'] not in BODY_KINDS: continue
            for rx in (BRACKET, SUPER):
                for m in rx.finditer(u['text']):
                    for n in expand(m.group(1)):
                        cited.setdefault(n, u)
        top = max(have)
        missing = sorted(n for n in cited if n not in have and n < 400)
        if missing and len(missing) >= 2:
            u = cited[missing[0]]
            findings.append(finding(6, f"{len(missing)} cited number(s) have no reference entry (entries run to {top}; "
                                       f"cited {missing[0]}..{missing[-1]})", pages=[l['page'] for r in refs[-1:] for l in paper.unit_lines(r)][:1],
                                    unit=refs[-1]['id'], offset=refs[-1]['span'][0], missing=missing[:50]))
    return findings, dict(references=len(refs), numbered=len(numbered))
