# Second pass: evaluation against the audited AG, AH and AI faults (2026-10-25)

`tools/secondpass/secondpass.py PAPER_DIR [PDF] [--write-list]` runs the eleven rules in `rules.txt` over a
finished copy. `copy_pdf.sh` runs it after the final copy (`COPY_SECONDPASS=0` skips it). It writes
`copy.secondpass.json` and adds the items of the "list" rules to the copy's uncertainty list. The copy text
is not changed. A run takes 1-4 s per paper. No AI models are used.

`tools/secondpass/evaluate.py` produced the numbers below.

## Truth

The truth is every MAJOR fault in AUDIT-AG/AH/AI, enumerated with paper, page and copy line from the audited
copies. It has 130 entries, grouped into 93 audit items on 23 failing papers. The audit's own counts differ in
four places:
- AH07: one systematic fault, 33 places;
- AH05: 10 entries for the audit's 5;
- AI03: 11 entries for the audit's 9;
- AH06: 13 entries for the audit's 14.

AI08 is excluded. AI07 is the fixed copy.

The error-free papers are AG10, AH03, AH10, AH11, AI05, AI07 and AI11.

A fault is **caught** when an item of a rule meant for its error family names one of the fault's pages. It is
**located** when the item's copy line is within three lines of the fault's line. Rule 1 has no copy line, so
for rule 1 the page is the location.

## Audited copies, per rule (audit items: expected / caught at the right page / located)

| Rule | Expected | Caught | Located | Items on error-free papers | Mode |
|---|---|---|---|---|---|
| 1 ink accounting | 20 | 15 | 4 | 0 | list |
| 2 sentence continuity | 37 | 16 | 6 | 1 (AI05: the PDF's own unfinished line before a heading) | report |
| 3 foreign text in a sentence | 36 | 13 | 5 | 0 | list |
| 4 reading order | 21 | 15 | 7 | 0 | list |
| 5 headings | 7 | 3 | 2 | 1 (AI11: "4. Discussion" run into its paragraph, a real minor defect) | report |
| 6 references | 4 | 1 | 1 | 0 | list |
| 7 tables | 22 | 12 | 4 | 0 | list |
| 8 duplicates | 1 | 1 | 0 | 0 | list |
| 9 characters | 4 (36 places) | 3 (35) | 1 (18) | 1 (AI11: alpha printed as "a", the audit's own minor note) | list |
| 10 page 1 | 17 | 7 | 1 | 0 | list |
| 11 document kind | 0 | - | - | 0 (fires on the excluded packet AI08: form, line numbers, tracked changes, several articles) | list |

Over all rules:
- **72 of 93 audit items** (106 of 130 entries) are caught at the right page by a rule meant for them.
- 36 items are located.
- 22 of the 23 failing papers have at least one MAJOR caught. AG06 is the exception: its only fault is a
  borderline citation line.
- The seven error-free papers carry 3 items in all: AG10, AH03, AH10, AH11 and AI07 have none, AI05 has 1 and
  AI11 has 2.

## Current program (this branch, readers off) on the same 30 papers

- The audited loss families are gone in the current program, and the second pass is silent there too:
  - AI03 right-edge loss: rule 1 finds nothing, and "de-epithelialized" is copied.
  - AH06 page-sized images: the pages are copied.
  - AH07 private-use codes: none are left.
- For 35 of the 130 fault entries, the copy quote still stands word for word. This is a weak signal: a quote
  can be legitimate text.
- 16 entries are still flagged at their page by a rule meant for them:
  - AG02 Tables 4 and 8 (an OCR scan);
  - AG08's title;
  - AG09's missing fifth author;
  - AH04's byline and its three-column box;
  - AH05's footnote, running head and Discussion paragraphs (an OCR scan);
  - AI01's "(B2)" cell and its alpha;
  - AI02's references before their heading;
  - AI04's Table 3 caption inside Table 1, and its fused references;
  - AI10's page 7/8 join.
- Items on the error-free papers are unchanged (the same 3).

Per-fault tables are in `out-secondpass/REPORT.md` of the secondpass lane.
