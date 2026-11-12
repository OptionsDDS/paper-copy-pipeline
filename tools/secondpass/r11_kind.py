"""Rule 11: document kind.

A copy made as if from one published article, when the PDF is something else:
  - a submission form: three or more distinct field labels (Manuscript ID,
    Manuscript Type, Date Submitted, Complete List of Authors, Journal, For
    Peer Review, ...);
  - a manuscript with margin line numbers: twenty or more lines the trace
    holds as consecutive margin line numbers;
  - tracked changes: three or more change balloons (Deleted:, Formatted:,
    Inserted:, Comment [..], Commented [..]);
  - several articles: two or more "Abstract" headings three or more pages
    apart, or a numbered reference list that starts again at 1.
Each kind found is one item naming its pages.
"""
import re

from common import finding

NAME = 'document kind'
FIELDS = re.compile(r'^\s*(manuscript id|manuscript type|manuscript number|date submitted|complete list of authors|'
                    r'journal:|article type|for peer review|keywords:|corresponding author:|submitted to|'
                    r'wiley - manuscript type|confidential)', re.I)
BALLOON = re.compile(r'\b(deleted|formatted|inserted|moved \(insertion\)|moved \(deletion\)):|\bcomment(?:ed)? \[', re.I)


def check(paper):
    """Document kind: submission form fields, margin line numbers, tracked-changes balloons, several articles."""
    findings = []; lines = paper.trace['lines']
    fields = {}
    for l in lines:
        m = FIELDS.match(l['text'])
        if m: fields.setdefault(m.group(1).lower(), l['page'])
    if len(fields) >= 3:
        findings.append(finding(11, f"submission form: field labels {sorted(fields)[:6]}", pages=sorted(set(fields.values()))))
    numbers = [l for l in lines if l['status'] == 'furniture' and 'line number' in (l.get('furniture_reason') or '')]
    if len(numbers) >= 20:
        findings.append(finding(11, f"manuscript with margin line numbers ({len(numbers)} numbered lines on "
                                    f"{len({l['page'] for l in numbers})} pages)", pages=sorted({l['page'] for l in numbers})[:3]))
    balloons = [l for l in lines if BALLOON.search(l['text'])]
    if len(balloons) >= 3:
        findings.append(finding(11, f"tracked changes: {len(balloons)} change balloon(s), e.g. {balloons[0]['text'][:40]!r}",
                                pages=sorted({l['page'] for l in balloons})[:3]))
    abstracts = sorted({l['page'] for u in paper.content_units if re.fullmatch(r'[>#*\s]*abstract[*:.\s]*', u['text'], re.I)
                        for l in paper.unit_lines(u)})
    if len(abstracts) >= 2 and abstracts[-1] - abstracts[0] >= 3:
        findings.append(finding(11, f"several articles: 'Abstract' headings on pages {abstracts}", pages=abstracts))
    refs = [u for u in paper.content_units if u['kind'] == 'reference']
    starts = [u for u in refs if re.match(r'\s*\[?1[.\])]?\s', u['text'])]
    if len(starts) >= 2:
        pages = sorted({l['page'] for u in starts for l in paper.unit_lines(u)})
        findings.append(finding(11, f"several articles: the numbered references start again at 1 ({len(starts)} times)", pages=pages))
    return findings, dict(field_labels=len(fields), line_numbers=len(numbers), balloons=len(balloons))
