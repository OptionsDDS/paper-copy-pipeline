"""Rule 5: headings.

(i) Numbered headings ("2", "2.1", "4.1 |") must follow in sequence: each next
number is a child (2 -> 2.1), the next sibling (2.1 -> 2.2) or the next of an
ancestor (2.2 -> 3); a step back or a gap is listed.
(ii) A heading comes before the text printed below it: the body line that
follows the heading on the page (the nearest line below it in its column) must
not be copied before the heading (headings collected at a page end, a heading
moved after its paragraph).
(iii) "References" comes before the first reference, and what follows the
heading is reference entries: a numbered entry "1. Name AB, ..." copied before
the heading, prose (not entries) directly after it, or another section
(acknowledgments, appendix) between the heading and the last entry is listed.
Heading-like units are heading units, or short title-like units (six words at
most, capitalised, no final stop or comma, not a number) printed at body size
or larger.
"""
import re

from common import BODY_KINDS, Layout, finding

NAME = 'headings'
REF_HEAD = re.compile(r'^(references?|bibliography|literature cited|literature|works cited|reference list|references and notes)$', re.I)
SECTION = re.compile(r'^(acknowledg|appendix|funding|conflicts? of interest|competing interests|author contributions|'
                     r'supplementary|abbreviations|disclosure|data availability)', re.I)
NUMBERED = re.compile(r'^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s*(?:\||\s)\s*[A-Z]')
ENTRY = re.compile(r'^\s*\[?(\d{1,3})[.\])]?\s+(?:[A-Z][A-Za-z\'’\-]+\s+[A-Z]{1,4}\b|[A-Z][A-Za-z\'’\-]+,\s+[A-Z])')


def plain(text):
    return re.sub(r'^[>#*\s]+|[*\s:.]+$', '', text).strip()


def heading_like(u, paper=None):
    """Heading units, or short title-like units (six words at most, capitalised, no
    final stop, not a number) printed at body size or larger."""
    if u['kind'] == 'heading': return True
    if u['kind'] not in BODY_KINDS | {'footnote'}: return False
    p = plain(u['text'])
    if not (0 < len(p.split()) <= 6 and p[:1].isupper() and not re.search(r'[.,;]$', u['text'].strip())): return False
    if re.fullmatch(r'[\d\s.]+', p): return False
    if paper is not None:
        ls = paper.unit_lines(u)
        if not ls: return False
        size = paper.line_size(ls[0]) or 0
        if size < .95*paper.body_size(ls[0]['page']): return False
    return True


def sequence(paper):
    out = []; prev = None
    for u in paper.content_units:
        if u['kind'] != 'heading': continue
        m = NUMBERED.match(plain(u['text']))
        if not m: continue
        num = tuple(int(x) for x in m.group(1).split('.'))
        if prev is not None:
            ok = num == prev + (1,) or any(num == prev[:j] + (prev[j]+1,) for j in range(len(prev)))
            # a parent heading printed in another style (not a heading unit): 2.3 -> 3.1
            ok = ok or (len(num) > 1 and num[-1] == 1 and any(num[:-1] == prev[:j] + (prev[j]+1,) for j in range(len(prev))))
            if not ok: out.append((u, prev, num))
        prev = num
    return out


def heading_after_text(paper, layout):
    """Headings whose following printed line was copied before them."""
    out = []
    from r04_order import line_offset
    offs = line_offset(paper)
    for k, u in enumerate(paper.content_units):
        if not heading_like(u, paper): continue
        ls = paper.unit_lines(u)
        if not ls: continue
        h = ls[-1]; hb = paper.line_box(h)
        if not hb: continue
        em = paper.body_size(h['page'])
        below = []
        for i in layout.page_lines.get(h['page'], []):
            l = paper.lines[i]; b = paper.line_box(l)
            if i == h['export_id'] or not b: continue
            if 0 <= b[1] - hb[3] <= 6*em and min(b[2], hb[2]) - max(b[0], hb[0]) > 0:
                below.append((b[1], l))
        # the first text line below, past at most two sub-headings directly under it
        below.sort(key=lambda t: t[0]); nxt = None; last = hb[3]
        for y, l in below:
            if y - last > 2.5*em: break
            k2 = layout.unit_of.get(l['export_id'])
            if k2 is not None and heading_like(paper.content_units[k2], paper):
                last = paper.line_box(l)[3]; continue
            nxt = l; break
        if nxt is None: continue
        off = offs.get(nxt['export_id'])
        if off is not None and off < u['span'][0]:
            out.append((u, h, nxt))
    return out


def references(paper):
    units = paper.content_units; out = []
    heads = [k for k, u in enumerate(units) if heading_like(u) or u['kind'] in BODY_KINDS | {'footnote'}
             and len(plain(u['text']).split()) <= 3 and REF_HEAD.match(plain(u['text']) or '-')]
    heads = [k for k in heads if REF_HEAD.match(plain(units[k]['text']) or '-')]
    if not heads: return out
    h = heads[-1] if len(heads) > 1 and all(units[x]['kind'] != 'heading' for x in heads[:-1]) else heads[0]
    entries = [k for k, u in enumerate(units) if u['kind'] == 'reference' or (u['kind'] in BODY_KINDS and ENTRY.match(u['text']))]
    before = [k for k in entries if k < h and ENTRY.match(units[k]['text'])]
    # only entries in the run directly before the heading (not in-text numbered lists far earlier)
    run = []
    for k in reversed(before):
        if run and run[-1] - k > 6: break
        run.append(k)
    if run:
        out.append(('entries before the heading', units[min(run)], units[h], len(run)))
    after = [k for k in range(h+1, min(len(units), h+4)) if units[k]['text'].strip()]
    if after and not any(k in entries for k in after) and all(units[k]['kind'] in BODY_KINDS for k in after):
        out.append(('prose after the heading', units[after[0]], units[h], len(after)))
    if entries:
        last = max(entries)
        for k in range(h+1, last):
            name = plain(units[k]['text'])
            if (units[k]['kind'] == 'heading' or SECTION.match(name)) and len(name.split()) <= 6 \
                    and not REF_HEAD.match(name or '-'):
                out.append(('a section inside the references', units[k], units[h], 1)); break
    return out


def check(paper):
    """Headings: numbering out of sequence, a heading after its text, references before their heading."""
    findings = []
    layout = Layout(paper)
    for u, prev, num in sequence(paper):
        ls = paper.unit_lines(u)
        findings.append(finding(5, f"heading number {'.'.join(map(str, num))} follows {'.'.join(map(str, prev))}: "
                                   f"{u['text'][:50]!r}", pages=[l['page'] for l in ls][:1], unit=u['id'], offset=u['span'][0]))
    for u, h, nxt in heading_after_text(paper, layout):
        findings.append(finding(5, f"page {h['page']}: heading {plain(u['text'])[:40]!r} is copied after the text printed "
                                   f"below it ({nxt['export_id']} {nxt['text'][:40]!r})", page=h['page'], unit=u['id'],
                                offset=u['span'][0]))
    for why, u, h, n in references(paper):
        pages = [l['page'] for l in paper.unit_lines(u)][:1] + [l['page'] for l in paper.unit_lines(h)][:1]
        findings.append(finding(5, f"references heading {plain(h['text'])!r}: {why} ({n} unit(s)), e.g. {u['text'][:50]!r}",
                                pages=pages, unit=u['id'], offset=u['span'][0]))
    return findings, dict(items=len(findings))
