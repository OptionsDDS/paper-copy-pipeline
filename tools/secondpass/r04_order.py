"""Rule 4: reading order against the page.

The copy's body lines (paragraph, list, abstract and heading units, in copy
order) must visit each page's lines in the page's own order (common.Layout:
column-major within bands), and a new page must continue at its first body
line not yet copied; steps of three or more lines are judged. A backward step on a page, a skipped body line at a page
turn, a jump over a page that still has uncopied body lines, or a return to
an earlier page is listed (columns read across, interleaved boxes, text moved
to another page). Consecutive jumps on one page form one item. Lines printed
as running text but copied as footnotes, table lines or figure text (two or
more on a page) are listed too: body text taken out of the flow.
"""
import re

from common import Layout, finding

NAME = 'reading order'
MIN_STEP = 2   # a displacement of one or two lines (a line or a run-in label moved by one) is not listed


def line_offset(paper):
    """First copy offset of every trace line (own claims, or the group's span for group claims)."""
    if getattr(paper, '_line_offset', None) is None:
        off, kind = {}, {}
        for u in paper.content_units:
            ls = paper.unit_lines(u) or [paper.lines[s['export_id']] for s in u.get('sources', []) if s.get('export_id') in paper.lines]
            for l in ls:
                if l['export_id'] not in off or u['span'][0] < off[l['export_id']]:
                    off[l['export_id']] = u['span'][0]; kind[l['export_id']] = u['kind']
        paper._line_offset, paper._line_kind = off, kind
    return paper._line_offset


def line_kind(paper):
    line_offset(paper)
    return paper._line_kind


def prose_lines(paper, n):
    """Lines of page n that read as running prose: six or more words, mostly lowercase words."""
    out = []
    for l in paper.trace['lines']:
        if l['page'] != n: continue
        ws = l['text'].split()
        alpha = [w for w in ws if w[:1].isalpha()]
        if len(ws) >= 6 and len(alpha) >= 4 and sum(w[0].islower() for w in alpha) >= .6*len(alpha): out.append(l)
    return out


def jumps(paper, layout=None):
    layout = layout or Layout(paper)
    seq = [l for _, l in layout.seq if l['export_id'] in layout.rank]
    done = set(); out = []
    order = {n: ids for n, ids in layout.page_lines.items()}
    prev = None
    for k, l in enumerate(seq):
        i = l['export_id']; n, r = layout.rank[i]
        if prev is not None:
            pn, pr = layout.rank[prev['export_id']]
            why = None
            if n == pn and r < pr - MIN_STEP:
                why = 'goes back up the page'
            elif n == pn and r > pr+1 and any(j not in done for j in order[n][pr+1:r]):
                skipped = [j for j in order[n][pr+1:r] if j not in done]
                # lines skipped here and copied later
                if len(skipped) > MIN_STEP and any(j in {x['export_id'] for x in seq[k:]} for j in skipped):
                    why = f'skips {len(skipped)} line(s) copied later'
            elif n == pn+1:
                waiting = [j for j in order[n][:r] if j not in done]
                if len(waiting) > MIN_STEP: why = f'starts the page at its line {r+1}, {len(waiting)} earlier line(s) not yet copied'
            elif n > pn+1:
                between = [j for m in range(pn+1, n) for j in order.get(m, []) if j not in done]
                pos = paper.content_units[layout.unit_of[i]]['span'][0]
                later = [l2 for m in range(pn+1, n) for l2 in prose_lines(paper, m) if line_offset(paper).get(l2['export_id'], -1) > pos
                         and line_kind(paper).get(l2['export_id']) not in ('caption', 'footnote', 'table_note', 'table_cell', 'reference')]
                if between: why = f'jumps from page {pn} to page {n} over {len(between)} uncopied body line(s)'
                elif len(later) >= 4:
                    kinds = sorted({line_kind(paper).get(l2['export_id'], '?') for l2 in later})
                    why = (f'jumps from page {pn} to page {n}; {len(later)} prose line(s) of the page(s) between '
                           f'are copied later (as {", ".join(kinds)})')
            elif n < pn:
                why = f'returns from page {pn} to page {n}'
            # Page 1 holds front-matter boxes (keywords, abstract panels, article
            # information) whose printed place differs from their reading place;
            # there only paragraph-to-paragraph steps and steps inside one unit are judged.
            same_unit = layout.unit_of.get(prev['export_id']) == layout.unit_of.get(i)
            if why and n == 1 and pn == 1 and not same_unit and not (layout.kind(prev) == layout.kind(l) == 'paragraph'):
                why = None
            # a one-line paragraph (a chart title or label copied as text) placed
            # after the text is a float's place, not a reading-order step
            if why and n == pn and len(paper.unit_lines(paper.content_units[layout.unit_of[i]])) == 1 \
                    and len(l['text'].split()) < 12:
                why = None
            # a heading out of place is rule 5's finding (heading after its text)
            if why and 'heading' in (layout.kind(prev), layout.kind(l)) and n == pn:
                why = None
            if why:
                front = n == 1 and pn == 1 and not (layout.kind(prev) == layout.kind(l) == 'paragraph')
                out.append(dict(prev=prev, line=l, why=why, front=front))
        done.add(i); prev = l
    return out


def check(paper):
    """Reading order: consecutive copy lines that do not follow the page's column order."""
    layout = Layout(paper)
    js = jumps(paper, layout)
    findings = []
    groups = []
    for j in js:
        n = j['line']['page']
        if groups and groups[-1][-1]['line']['page'] == n and j['prev']['page'] == groups[-1][-1]['line']['page']:
            groups[-1].append(j)
        else: groups.append([j])
    for g in groups:
        # inside a page-1 front unit (an abstract box with its citation or
        # copyright line) one or two steps are layout; interleaving repeats
        if all(j['front'] for j in g) and len(g) < 4: continue
        first = g[0]
        units = paper.content_units
        k = layout.unit_of.get(first['line']['export_id'])
        off = units[k]['span'][0] if k is not None else None
        findings.append(finding(4, f"page {first['line']['page']}: after {first['prev']['export_id']} "
                                   f"{first['prev']['text'][-40:]!r} the copy reads {first['line']['export_id']} "
                                   f"{first['line']['text'][:40]!r}, which {first['why']}"
                                   + (f' (and {len(g)-1} more jump(s) on this page)' if len(g) > 1 else ''),
                                pages=[first['prev']['page'], first['line']['page']], unit=units[k]['id'] if k is not None else None,
                                offset=off, jumps=len(g)))
    seen = set()
    for (n, kind), hits in sorted(body_lines_elsewhere(paper, layout).items()):
        if len(hits) < 2: continue
        u, l = hits[0]
        findings.append(finding(4, f"page {n}: {len(hits)} line(s) printed as running text are copied as {kind}, "
                                   f"e.g. {l['export_id']} {l['text'][:50]!r}", page=n, unit=u['id'], offset=u['span'][0],
                                kind='body text out of the flow', lines=[x['export_id'] for _, x in hits][:20]))
    return findings, dict(body_lines=len(layout.seq), jumps=len(js))


OUT_OF_FLOW = {'footnote', 'table_line', 'table_cell', 'figure_text', 'table_note'}


def body_lines_elsewhere(paper, layout):
    """Body-text lines copied as footnotes, table lines or figure text.

    A line printed like the page's running text (within 6% of the body size,
    at least 85% of the median width of the page's body lines, seven or more
    words, mostly lowercase words) that the copy holds in a footnote, table or
    figure unit has left the text flow (a table gate or float that took body
    text). Pages are listed with their count.
    """
    widths = {}; every = []
    for n, ids in layout.page_lines.items():
        ws = sorted(paper.line_box(paper.lines[i])[2]-paper.line_box(paper.lines[i])[0] for i in ids
                    if len(paper.lines[i]['text'].split()) >= 6)
        every += ws
        if len(ws) >= 5: widths[n] = ws[len(ws)//2]
    every.sort()
    if not every: return {}
    found = {}; done = set()
    for u in paper.content_units:
        if u['kind'] not in OUT_OF_FLOW: continue
        ls = paper.unit_lines(u) or [paper.lines[s['export_id']] for s in u.get('sources', []) if s.get('export_id') in paper.lines]
        for l in ls:
            if l['export_id'] in done: continue
            done.add(l['export_id'])
            n = l['page']; b = paper.line_box(l)
            if not b: continue
            t = l['text'].strip()
            # table notes, abbreviation lists and captions are not running text
            if re.match(r'(note|notes|abbreviations?|key|source|fig\.?|figure|table)\b|[*†‡§¶#]|[a-z]\s', t, re.I) or \
                    len(re.findall(r'\b[A-Z][A-Za-z]*[A-Z]\w*\s*[,=:]\s', t)) >= 2:
                continue
            width = widths.get(n, every[len(every)//2])
            ws = l['text'].split(); alpha = [w for w in ws if w[:1].isalpha()]
            size = paper.line_size(l) or 0; body = paper.body_size(n)
            if (len(ws) >= 7 and abs(size-body) <= .06*body and b[2]-b[0] >= .85*width
                    and len(alpha) >= 5 and sum(w[0].islower() for w in alpha) >= .7*len(alpha)):
                found.setdefault((n, u['kind']), []).append((u, l))
    return found
