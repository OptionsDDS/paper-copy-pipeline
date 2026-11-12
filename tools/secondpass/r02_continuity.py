"""Rule 2: sentence continuity.

A copy paragraph (or list item, abstract part) of eight or more words that
ends inside a sentence (a lowercase last letter, a comma, a line-end hyphen,
or an article/preposition/conjunction) must be followed directly by its
continuation: the next unit is body text that starts in lowercase (or a digit,
bracket or sign). Anything else between them (a table, caption, heading,
list, running head, footnote) is listed. When a continuation follows within a
few units, the item names what came between (the foreign text is also judged
by rule 3); when none follows, the sentence stops and the item says so (text
lost or moved). Inside one unit, a join across a page or column turn where
the earlier line stops mid-sentence and the next starts a capitalised
sentence, or a hyphenated word continued by a capitalised word, is listed too
(two texts spliced).
"""
import re

from common import BODY_KINDS, adjacent, continues, ends_hyphen, ends_mid, finding, proper_nouns

NAME = 'sentence continuity'
LOOKAHEAD = 8


def describe(u):
    return f"{u['kind']} {u['text'][:50]!r}"


def breaks(paper):
    """(index of the stopped unit, index of its continuation or None) for every broken sentence."""
    units = paper.content_units; out = []
    for k, u in enumerate(units):
        if u['kind'] not in BODY_KINDS | {'reference'} or not ends_mid(u['text']): continue
        if len(u['text'].split()) < (3 if ends_hyphen(u['text']) else 8): continue
        if k+1 < len(units) and units[k+1]['kind'] in BODY_KINDS | {'reference'} and continues(units[k+1]['text']): continue
        # A paragraph split before a capitalised word, with the next part on the
        # very next printed line, is a split, not a stop.
        if k+1 < len(units) and units[k+1]['kind'] in BODY_KINDS:
            la, lb = paper.unit_lines(u), paper.unit_lines(units[k+1])
            if la and lb and adjacent(paper, la[-1], lb[0]): continue
            w = re.match(r"[A-Z][a-z]+", units[k+1]['text'].lstrip())
            if w and w.group(0) in proper_nouns(paper): continue
        cont = None; blocks = 0; j = k+1; group = None
        while j < len(units) and blocks < LOOKAHEAD:
            v = units[j]
            if v['kind'] in BODY_KINDS | {'reference'} and continues(v['text']) and len(v['text'].split()) >= 2:
                cont = j; break
            if v['kind'] in BODY_KINDS and len(v['text'].split()) >= 12: break  # a new paragraph: no continuation
            # the cells or lines of one table (one unit group) count as one block
            if v.get('group') != group or v['kind'] in BODY_KINDS: blocks += 1
            group = v.get('group'); j += 1
        # A reference may end without a stop; between references only a float or
        # heading counts as an insertion.
        if u['kind'] == 'reference' and (cont is None or all(units[x]['kind'] in BODY_KINDS | {'reference'} for x in range(k+1, cont))):
            continue
        out.append((k, cont))
    return out


def unit_pages(paper, u):
    ls = paper.unit_lines(u)
    return [l['page'] for l in ls] or [s['page'] for s in u.get('sources', [])]


def splices(paper):
    """Joins inside one unit where a page or column turn meets a new capitalised sentence."""
    out = []
    for u in paper.content_units:
        if u['kind'] not in BODY_KINDS: continue
        ls = paper.unit_lines(u)
        for a, b in zip(ls, ls[1:]):
            ba, bb = paper.line_box(a), paper.line_box(b)
            if not ba or not bb: continue
            turn = a['page'] != b['page'] or bb[1] < ba[1] - 2*paper.body_size(a['page'])
            if not turn: continue
            ta, tb = a['text'].rstrip(), b['text'].lstrip()
            first = re.match(r"[A-Z][a-z]+\b", tb)
            if not first or not tb: continue
            if first.group(0) in proper_nouns(paper): continue
            if (ends_hyphen(ta) or (ends_mid(ta) and ta[-1:].islower())) and first.group(0).lower() not in ('i',):
                out.append((u, a, b))
    return out


def check(paper):
    """Sentence continuity: a paragraph ending mid-sentence not followed by its continuation."""
    units = paper.content_units; findings = []
    for k, cont in breaks(paper):
        u = units[k]
        pages = unit_pages(paper, u)[-1:]
        if cont is not None:
            between = units[k+1:cont]
            pages += [p for v in between for p in unit_pages(paper, v)[:1]] + unit_pages(paper, units[cont])[:1]
            msg = (f"a sentence ending {u['text'][-40:]!r} continues {units[cont]['text'][:30]!r} only after "
                   + '; '.join(describe(v) for v in between[:3]) + (' ...' if len(between) > 3 else ''))
        else:
            nxt = units[k+1] if k+1 < len(units) else None
            pages += unit_pages(paper, nxt)[:1] if nxt else []
            msg = (f"a sentence stops at {u['text'][-40:]!r}; next comes " + (describe(nxt) if nxt else 'the end of the copy')
                   + ' (text lost or moved)')
        findings.append(finding(2, msg, pages=pages, unit=u['id'], offset=u['span'][1], continuation=cont is not None))
    for u, a, b in splices(paper):
        findings.append(finding(2, f"page {a['page']}->{b['page']}: {a['text'][-35:]!r} is joined to {b['text'][:35]!r} "
                                   f"at a page or column turn (a capitalised sentence after an unfinished one)",
                                pages=[a['page'], b['page']], unit=u['id'], offset=u['span'][0] + max(0, u['text'].find(b['text'][:20])),
                                splice=True))
    return findings, dict(breaks=len(findings))
