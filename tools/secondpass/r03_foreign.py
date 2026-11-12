"""Rule 3: foreign text inside a sentence.

Text that does not belong to a sentence but sits between its two halves: a
running head or foot (text recurring near the top or bottom of three or more
pages), a page number, a caption, a footnote, figure lettering, a table or a
heading. Three forms are listed:
  (a) between units: a paragraph stops mid-sentence and its lowercase
      continuation follows only after other units (rule 2's breaks); each unit
      between is named by its kind or what it looks like;
  (b) inside one unit: a source line of the paragraph that is a running head,
      a page number in the margin band, a line inside a figure on the page, or
      a line clearly smaller than its neighbours (footnote or
      caption type) with body lines on both sides;
  (c) inside a word: a line-end hyphen whose word continues only after a
      capitalised insertion ("epide- References miological"), checked against
      the PDF's own vocabulary;
  (d) merged inside one unit (lane f5stream R4): at a join of two source lines
      that are not next to each other on the page, the earlier line is full
      and stops inside a sentence, the next opens a capitalised block, and the
      sentence resumes with a lowercase word at the unit's next join (or the next
      body unit) -- the shared boundary witness (rule 9's) confirming that resume
      and calling the capitalised opening undecided -- while the block differs
      from the line before it in type size (over 6 per cent) or opens with a float
      label (a caption in body size, AP08; a pull quote across the gutter).
"""
import re
import statistics

from common import BODY_KINDS, adjacent, area, boundary_functions, boundary_witness, finding, inside, margin_band, pdf_words, recurring_lines
import r02_continuity

NAME = 'foreign text inside a sentence'


def what(paper, u):
    t = u['text'].strip(); key = re.sub(r'[^a-z]', '', t.lower())
    if u['kind'] in ('caption',): return 'caption'
    if u['kind'] in ('table_cell', 'table_line', 'table_note'): return 'table'
    if u['kind'] == 'footnote': return 'footnote'
    if u['kind'] == 'heading': return 'heading'
    if u['kind'] in ('figure_text', 'image_file'): return 'figure'
    if re.fullmatch(r'[\d\s]{1,6}', t): return 'page number'
    if key and key in recurring_lines(paper): return 'running head'
    if re.match(r'(fig\.?|figure|table)\s*\d', t, re.I): return 'caption'
    if len(t.split()) < 6: return 'short line'
    return u['kind']


def figure_boxes(paper, n):
    page = paper.page(n) or {}
    return [paper.moved(f['box_px'], n) for f in page.get('floats', []) if f.get('box_px')]


def inner(paper):
    """(unit, line, reason) for foreign source lines inside one body unit."""
    out = []
    rec = recurring_lines(paper)
    for u in paper.content_units:
        if u['kind'] not in BODY_KINDS: continue
        ls = paper.unit_lines(u)
        if len(ls) < 3: continue
        sizes = [paper.line_size(l) or 0 for l in ls]
        med = statistics.median(sizes) if sizes else 0
        for k in range(1, len(ls)-1):
            l = ls[k]; t = l['text'].strip(); key = re.sub(r'[^a-z]', '', t.lower())
            reason = None
            if key and key in rec and margin_band(paper, l): reason = 'running head'
            elif re.fullmatch(r'[\d\s]{1,6}', t) and margin_band(paper, l, .1): reason = 'page number'
            else:
                b = paper.line_box(l)
                if b and any(inside(((b[0]+b[2])/2, (b[1]+b[3])/2), fb, 0) for fb in figure_boxes(paper, l['page'])):
                    # lines inside a figure's box (a caption's own box also counts)
                    nb = [paper.line_box(x) for x in (ls[k-1], ls[k+1])]
                    if not all(nbx and any(inside(((nbx[0]+nbx[2])/2, (nbx[1]+nbx[3])/2), fb, 0)
                                           for fb in figure_boxes(paper, l['page'])) for nbx in nb):
                        reason = 'text inside a figure'
                elif med and sizes[k] and med-sizes[k] > .15*med and abs(sizes[k-1]-med) <= .1*med \
                        and abs(sizes[k+1]-med) <= .1*med and len(t.split()) >= 3:
                    # smaller only: a symbol from a larger face can raise a body line's size
                    reason = 'a smaller line (footnote, caption or lettering)'
            if reason: out.append((u, l, reason))
    return out


def word_insertions(paper):
    """'epide- References miological': a hyphenated word continued after a capitalised insertion."""
    vocab = pdf_words(paper); out = []
    for u in paper.content_units:
        if u['kind'] not in BODY_KINDS: continue
        for m in re.finditer(r"\b([A-Za-z]{2,})- ((?:[A-Z][\w.,:()]*\s+){1,8}?)([a-z]{2,})\b", u['text']):
            whole = (m.group(1)+m.group(3)).lower()
            if whole in vocab and m.group(2).strip().lower() not in vocab - {whole}:
                out.append((u, m))
            elif whole in vocab:
                out.append((u, m))
    return out


LABEL = re.compile(r'^\s*(?:Fig(?:ure)?s?\.?|Table|Box|Scheme|Chart|Plate)\s*[A-Z]?\d+', re.I)


def open_end(text):
    return boundary_functions()['boundary_open_end'](text)


def resumes(text):
    return boundary_functions()['boundary_resumes'](text)


def merged(paper):
    """(unit, opening line, resume line or None, reason) for blocks merged inside one unit."""
    out = []
    units = paper.content_units
    for k, u in enumerate(units):
        if u['kind'] not in BODY_KINDS: continue
        ls = paper.unit_lines(u)
        if len(ls) < 3: continue
        widths = sorted(b[2]-b[0] for b in (paper.line_box(l) for l in ls) if b)
        if not widths: continue
        measure = widths[len(widths)//2]
        joins = [i for i in range(1, len(ls)) if not adjacent(paper, ls[i-1], ls[i])]
        for n, i in enumerate(joins):
            a, b = ls[i-1], ls[i]; ta, tb = a['text'].strip(), b['text'].strip()
            ba = paper.line_box(a)
            if not (ba and ba[2]-ba[0] >= .8*measure and open_end(ta) and len(tb.split()) >= 3 and tb[:1].isupper()): continue
            if boundary_witness(ta, tb)['verdict'] != 'undecided': continue
            stop = joins[n+1] if n+1 < len(joins) else None
            if stop is not None:
                resume = ls[stop]['text']; segment = ls[i:stop]
            else:
                later = next((v for v in units[k+1:] if v['kind'] in BODY_KINDS), None)
                resume = later['text'] if later else ''; segment = ls[i:]
            if not resume or not resumes(resume) or boundary_witness(ta, resume)['verdict'] != 'continuation': continue
            sa = paper.line_size(a) or 0
            sizes = sorted(paper.line_size(l) or 0 for l in segment)
            size = sizes[len(sizes)//2] if sizes else 0
            reason = None
            if LABEL.match(tb): reason = 'a float label'
            elif sa and size and abs(size-sa) > .06*sa: reason = 'another type size'
            if reason: out.append((u, b, ls[stop] if stop is not None else None, reason))
    return out


def check(paper):
    """Foreign text inside a sentence: running head, folio, caption, footnote, lettering, table or heading between its halves."""
    units = paper.content_units; findings = []
    for k, cont in r02_continuity.breaks(paper):
        if cont is None: continue
        u = units[k]; between = units[k+1:cont]
        kinds = [what(paper, v) for v in between]
        pages = r02_continuity.unit_pages(paper, u)[-1:] + [p for v in between for p in r02_continuity.unit_pages(paper, v)[:1]]
        findings.append(finding(3, f"{', '.join(dict.fromkeys(kinds))} between the halves of a sentence: "
                                   f"{u['text'][-35:]!r} ... {units[cont]['text'][:30]!r}; inserted: "
                                   + '; '.join(repr(v['text'][:40]) for v in between[:3]),
                                pages=pages, unit=between[0]['id'], offset=between[0]['span'][0], form='between units', kinds=kinds))
    for u, l, reason in inner(paper):
        off = u['span'][0] + max(0, u['text'].find(l['text'].strip()[:15]))
        findings.append(finding(3, f"page {l['page']}: {reason} inside a paragraph: {l['export_id']} {l['text'][:50]!r}",
                                page=l['page'], unit=u['id'], offset=off, form='inside a unit', line=l['export_id']))
    for u, b, r, reason in merged(paper):
        off = u['span'][0] + max(0, u['text'].find(b['text'].strip()[:15]))
        findings.append(finding(3, f"page {b['page']}: a block in {reason} merged inside a sentence: {b['export_id']} {b['text'][:50]!r}"
                                   + (f" ... resumes {r['text'][:30]!r}" if r else ''),
                                page=b['page'], unit=u['id'], offset=off, form='merged inside a unit', line=b['export_id']))
    for u, m in word_insertions(paper):
        ls = paper.unit_lines(u)
        findings.append(finding(3, f"{m.group(2).strip()!r} inside the word {m.group(1)}-{m.group(3)}",
                                pages=[l['page'] for l in ls][:1], unit=u['id'], offset=u['span'][0]+m.start(), form='inside a word'))
    return findings, dict(items=len(findings))
