"""Rule 8: duplicates.

The same block printed twice: eight-word runs (normalised words) that the copy
holds in two different units (outside the flagged "Front matter as printed"
block, which repeats the parsed front matter on purpose), covering at least
half of the shorter unit, more often than the PDF's own text layer prints them,
where the two units were copied from the same printed lines (units copied from
different printed lines repeat what the PDF prints twice, such as a continued
table's header). Each such pair of units is one item.
"""
import re
from collections import defaultdict

from common import finding, norm, pdf_words

NAME = 'duplicates'
N = 8
SKIP = {'front_matter_printed', 'notice', 'image_file', 'title', 'article_information', 'author', 'affiliation'}


def sources(paper, u):
    ls = paper.unit_lines(u) or [paper.lines[x['export_id']] for x in u.get('sources', []) if x.get('export_id') in paper.lines]
    return {l['export_id'] for l in ls}


def check(paper):
    """Duplicates: a block (8+ normalised words) printed twice that the PDF prints once."""
    pdf_words(paper)
    text = paper._pdf_text
    for a, b in (('\ufb00', 'ff'), ('\ufb01', 'fi'), ('\ufb02', 'fl'), ('\ufb03', 'ffi'), ('\ufb04', 'ffl'), ('\u00ad', '')):
        text = text.replace(a, b)
    text = re.sub(r'(\w)[-\u2010]\s*\n\s*(\w)', r'\1\2', text)   # rejoin words hyphenated at line ends
    pdf_norm = ' ' + norm(text) + ' '
    pdf_loose = ' ' + norm(re.sub(r'[-\u2010]', '', text)) + ' '
    where = defaultdict(list); grams = {}
    for u in paper.content_units:
        if u['kind'] in SKIP: continue
        t = u['text']
        for a, b in (('\ufb00', 'ff'), ('\ufb01', 'fi'), ('\ufb02', 'fl'), ('\ufb03', 'ffi'), ('\ufb04', 'ffl')): t = t.replace(a, b)
        ws = norm(t).split()
        grams[u['id']] = max(0, len(ws)-N+1)
        for k in range(0, max(0, len(ws)-N+1)):
            where[' '.join(ws[k:k+N])].append(u)
    pairs = defaultdict(int)
    for gram, us in where.items():
        groups = {u['group'] for u in us}
        if len(groups) < 2: continue
        if max(pdf_norm.count(' '+gram+' '), pdf_loose.count(' '+gram+' ')) >= len(groups): continue
        a, b = us[0], next(u for u in us if u['group'] != us[0]['group'])
        pairs[a['id'], b['id']] += 1
    units = {u['id']: u for u in paper.content_units}
    findings = []
    for (a, b), n in pairs.items():
        ua, ub = units[a], units[b]
        # a repeated block, not a repeated phrase: half the shorter unit's runs
        if n < max(3, .5*min(grams[a], grams[b])): continue
        # Two units copied from different printed lines repeat what the PDF prints
        # twice (a continued table's header, a repeated title): only a block whose
        # source lines are shared, or that has no source line, is a duplicate.
        sa, sb = sources(paper, ua), sources(paper, ub)
        if sa and sb and not (sa & sb): continue
        pages = [l['page'] for l in paper.unit_lines(ub)][:1] or [s['page'] for s in ub.get('sources', [])][:1]
        findings.append(finding(8, f"{n} eight-word run(s) printed twice: {ua['kind']} {ua['text'][:40]!r} and again in "
                                   f"{ub['kind']} {ub['text'][:40]!r}", pages=pages, unit=b, offset=ub['span'][0], runs=n))
    return findings, dict(pairs=len(findings))
