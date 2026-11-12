"""Rule 10: the first page of the article (the page of the title, else page 1).

  (a) the title is the largest text block on its page: a line of two or more
      words printed at least 15% larger than the title's lines (outside the
      top and bottom margin bands) is listed, naming it; no title is listed
      (except on an OCR scan, whose copy has no parsed title);
  (b) authors agree with the printed byline and the affiliation markers: the
      byline lines the authors were read from must not print more names than
      the copy lists; every affiliation marker must belong to an author and
      every author marker to an affiliation; a page with name-and-degree lines
      ("Name Surname, DDS*") on the first three pages but no author list is
      listed (byline not found);
  (c) every line of the page is accounted for in the copy: lines lost, and
      lines of two or more words from the title down that only the
      uncertainty list holds (not the copy text), are listed.
"""
import re
import statistics

from common import finding, margin_band

NAME = 'page 1'
DEGREE = r'(?:DDS|DMD|MDS|MD|PhD|MS|MSc|MSD|BDS|BSc|MPH|DrMedDent|Dr\.?\s?med\.?\s?dent\.?|RDH|FRCD|DMSc|Odont\.?\s?Dr)'
NAME_LINE = re.compile(r"^[A-Z][a-zA-Z'’.\-]+(?:\s+[A-Z][a-zA-Z'’.\-]*){1,4},?\s+" + DEGREE + r'\b')
MARK = re.compile(r'(\*+|[†‡§¶#⁎]+|\d{1,2}|[a-h])$')


# Academic titles and degrees that follow a name as their own comma part ("Name, Dr Habil",
# "Name, Dr Med Dent/Dr Habil", "Name, Dipl-Ing"): such a part is the name's degree, not a name.
# Only a part made wholly of these tokens is dropped, so a surname such as Dent stays a name.
TITLE_PART = re.compile(r'(?:(?:Dr|Prof|Habil|Med|Dent|Dipl\.?(?:-[A-Z][a-z]+\.?)*|' + DEGREE + r')\.?[\s/]*)+')


ADDRESS_PART = re.compile(r'(?:Department|Dept|Division|Faculty|School|Universit|Institut|Centre|Center|Laborator|Hospital|College|Clinic)', re.I)


def name_count(text):
    t = re.sub(r'[*†‡§¶#⁎\d]+', '', text)
    parts = [p.strip() for p in re.split(r',|;|\band\b|&', t) if p.strip()]
    # An address that starts on the byline row ends the names: parts from the first part that
    # opens with an institution word on are address text.
    cut = next((i for i, p in enumerate(parts) if i and ADDRESS_PART.match(p)), len(parts))
    parts = [re.sub(r'\b' + DEGREE + r'\b', '', p).strip() for p in parts[:cut] if not TITLE_PART.fullmatch(p)]
    return sum(1 for p in parts if len(re.findall(r"[A-Z][a-zA-Z'’\-]+", p)) >= 2)


ONE = r'(?:\d{1,2}|[a-h]|\*+|[†‡§¶#⁎]+)'


def markers(text):
    """Trailing affiliation markers of an author ("Name 1,*" -> {"1", "*"})."""
    t = text.replace('\\', '').strip().rstrip(',;')
    m = (re.search(r'(?<=\s)(' + ONE + r'(?:\s*,\s*' + ONE + r')*)$', t)
         or re.search(r'(?<=[A-Za-z.])((?:\d{1,2}|\*+|[†‡§¶#⁎]+)(?:\s*,\s*' + ONE + r')*)$', t))
    if not m: return set()
    out = set()
    for x in m.group(1).split(','):
        x = x.strip()
        # a run of different signs (††‡‡) names several affiliations
        out.update(r.group(0) for r in re.finditer(r'(.)\1*', x)) if x and not x[0].isalnum() else out.add(x)
    return {x for x in out if x}


def lead_marker(text):
    m = re.match(r'\s*(' + ONE + r')\s', text.replace('\\', ''))
    return m.group(1) if m else None


def check(paper):
    """Page 1: title not the largest text, authors and affiliation markers disagree, page-1 lines unaccounted."""
    findings = []
    units = paper.content_units
    titles = [u for u in units if u['kind'] == 'title']
    tlines = [l for u in titles for l in paper.unit_lines(u)]
    page = tlines[0]['page'] if tlines else 1
    lines = [l for l in paper.trace['lines'] if l['page'] == page]
    if not titles:
        # an OCR scan's copy prints its text as recognised, without a parsed title
        if page not in paper.scan_pages:
            findings.append(finding(10, f'no title in the copy', page=page))
    elif tlines:
        tsize = statistics.median([paper.line_size(l) or 0 for l in tlines])
        tids = {l['export_id'] for l in tlines}
        bigger = [l for l in lines if l['export_id'] not in tids and len(l['text'].split()) >= 2 and l['status'] != 'furniture'
                  and (paper.line_size(l) or 0) > 1.15*tsize and not margin_band(paper, l, .07)]
        if bigger:
            l = max(bigger, key=lambda x: paper.line_size(x) or 0)
            findings.append(finding(10, f"page {page}: {l['export_id']} {l['text'][:50]!r} is printed larger than the title "
                                        f"{titles[0]['text'][:40]!r} ({paper.line_size(l):.0f} px against {tsize:.0f})",
                                    page=page, unit=titles[0]['id'], offset=titles[0]['span'][0]))
    authors = [u for u in units if u['kind'] == 'author']
    affs = [u for u in units if u['kind'] == 'affiliation']
    if authors:
        blines = {l['export_id']: l for u in authors for l in paper.unit_lines(u)}
        printed = sum(name_count(l['text']) for l in blines.values())
        if printed > len(authors):
            findings.append(finding(10, f"page {page}: the byline lines print {printed} names but the copy lists "
                                        f"{len(authors)} authors", page=page, unit=authors[0]['id'], offset=authors[0]['span'][0]))
        amarks = set().union(*(markers(u['text']) for u in authors))
        fmarks = {lead_marker(u['text']) for u in affs} - {None}
        if amarks and fmarks:
            # a star alone usually marks the corresponding author, not an affiliation
            lonely = sorted(fmarks - amarks); orphan = sorted(amarks - fmarks - {'*', '⁎'})
            if lonely or orphan:
                findings.append(finding(10, f"page {page}: affiliation marker(s) {lonely} belong to no author; author "
                                            f"marker(s) {orphan} have no affiliation", page=page,
                                        unit=authors[0]['id'], offset=authors[0]['span'][0]))
    else:
        # a cover page can come first: look at the first three pages
        named = [l for l in paper.trace['lines'] if l['page'] <= max(3, page) and NAME_LINE.match(l['text'].strip())]
        if named:
            findings.append(finding(10, f"page {named[0]['page']}: no author list, but the page prints a byline such as "
                                        f"{named[0]['text'][:40]!r} ({len(named)} name line(s))", page=named[0]['page']))
    lost = [l for l in lines if l['status'] in ('lost', 'partly_lost')]
    # below the title's top: the publisher's header box above the title is not article text
    ttop = min((paper.line_box(l)[1] for l in tlines), default=0)
    only_listed = [l for l in lines if l['status'] == 'uncertainty' and len(l['text'].split()) >= 2
                   and (paper.line_box(l) or [0, 0])[1] >= ttop - 2]
    for what, ls in (('lost', lost), ('held only in the uncertainty list, not in the copy text', only_listed)):
        if ls:
            findings.append(finding(10, f"page {page}: {len(ls)} line(s) {what}, e.g. {ls[0]['export_id']} {ls[0]['text'][:50]!r}",
                                    page=page, lines=[l['export_id'] for l in ls][:20]))
    return findings, dict(authors=len(authors), affiliations=len(affs))
