# Line export and assembly

These tools implement `LINEMAP-SCHEMA.md` and leave `copy_paper.py` unchanged.
Run them with the system Python in isolated mode; dependencies are the standard
library, this repository's copy program and vendored reader, `pdftoppm`, and
`pdftotext`. No model call, network request or additional OCR is performed.

```sh
/usr/bin/python3 -I tools/export_lines.py COPY_DIR PDF OUT
/usr/bin/python3 -I tools/assemble_map.py OUT/lines.json MAP.json ASSEMBLED
/usr/bin/python3 -I tools/roundtrip_linemap.py OUT ROUNDTRIP
```

`COPY_DIR` must contain a complete copy run's page records and `main-text.json`.
`authors.json`, saved glyph decisions, and OCR-layer evidence are used when
present. `OUT` must be outside `COPY_DIR`. Input JSON and the PDF are read-only.
The export runs the existing copy program on temporary JSON copies under OUT,
observes decoded text and placement using Python's profile hook, and deletes
that temporary run even on failure. It restores the previous hook and PDF
environment variables. The copy implementation is not monkey-patched. Run batch
exports in separate processes, not threads sharing process environment state.

The exporter writes:

- `lines.json`, exactly the fields in the schema;
- `pages/pNN.png`, full MediaBox renders at 110 dpi; `image` paths are relative
  to the directory containing `lines.json`;
- `lines.audit.json`, source-run ownership, exact word differences, source
  boxes, clipping flags, and the copy program's SHA-256;
- `program.copy.md`, the unchanged program's result on these inputs;
- `program.map.json`, an automatic, conservative mapping of the current
  program's roles and reading order. This is a starting map for review.

IDs are deterministic for the same decoded input and exporter version, sorted
by source top, left, then source run IDs. A line is a baseline segment: wide
gutters, distinct text angles and distinct ownership roles separate segments.
Font fragments on that segment share one ID. A source line spanning several
table cells remains whole until a mapper supplies a legal split. Source-run
IDs in the audit provide provenance independent of the exported numbering.
IDs are not promised to survive edits to source geometry or decoding.

The copy's OCR source runs are used on scans; native text underneath the same
scan is not exported a second time. No text is invented for an image that has
no OCR layer. For native text the source universe is captured immediately
after the copy's glyph decoding; invisible text already removed by that copy
is not a printed line. The exporter proves that every nonempty source run in
that universe is owned once. Missing/duplicate run ownership is a fatal error.

Text uses the copy's glyph spacing, native row composition, citation/subscript
notation and accent composition. Paragraph hyphenation is deferred to the
assembler. Font size is the largest nominal font size on a line, converted to
110-dpi pixels. Bold and italic require a majority of characters with matching
font-face names; an unavailable face gives false. Mixed styles cannot be
represented in the schema. Boxes are transformed from the reader's native
frame to Poppler's rendered frame, including rotation and shifted MediaBoxes.
Partial off-page boxes are clipped and reported; wholly off-page boxes fail.

Completeness comparisons are case-sensitive NFKC Unicode alphanumeric word
**multisets**, preserving repeated values. Both decoded source-run and
`pdftotext -layout` differences are saved in full. Typography can change word
boundaries (a raised citation separates from its host word, or touching font
fragments join), and accents can compose. Such changes remain visible in the
audit; a nonzero difference is never labelled exact word equality. An additional
alphanumeric character comparison helps distinguish boundaries from glyph
changes but does not replace the word comparison. PDF/source differences also
include differences between text extractors, unpainted text and OCR segmentation.

## Map validation and assembly decisions

All source and map shapes, ID ownership, paper names, geometry and splits are
validated before any output is opened. Every leaf ID after splits must occur
exactly once in a content location or furniture. IDs in `split_lines` declare
a transformation, not a second content use. Unknown fields are errors, so a
cell cannot secretly provide replacement text. Invalid maps leave any previous
successful output intact and exit 2; callers must inspect the exit status.

Splits are sequential and may split a previously created part. The anchor must
occur once, start immediately after whitespace, and produce two nonempty parts.
New IDs must extend the parent's ID and must never have been used. The parent
is retired. Only boundary whitespace is trimmed; no letters are changed.
Because the schema supplies no per-character boxes, split parts retain the
parent's box in internal audit data. Splitting inside a word is rejected.

Paragraphs, title, headings, references and footnotes use `copy_paper.Joiner`.
Tables and captions use its non-prose mode. Formula baselines are fenced as
plain text, without pretending the PDF supplied LaTeX. List markers already
present in source text are preserved. Furniture is omitted and counted by
category in `copy.linemap.json`; its full ID ownership remains auditable.

Tables must contain whole-line ID lists. An empty cell, missing body column,
empty row or ambiguous header span causes a `table_lines` fallback with all
available IDs retained once, notes below, and a reason in the uncertainty list.
The mapper should use explicit `table_lines` when no reliable grid exists.
Only a single-cell header spanning all columns is inferred; other header rows
must have the table's full column count. Multiple header rows are combined with
`<br>`, repeating a whole-width spanning heading above each column. Header
repetition is presentation, not a second ownership claim. Zero header rows
produce an empty Markdown header followed by the data. The schema has no
colspan metadata for uneven multi-cell spans; those tables fall back.

The assembler writes `copy.md` and `copy.linemap.json`, including conservation,
furniture, table decisions, split declarations and hyphen decisions. The final
uncertainty section always exists, contains mapper and fallback notes, and
says `none` when there are no notes. Outputs are staged before replacement.

## Automatic maps and round trips

Automatic maps locate complete source lines in the current output first, then
use its token-occurrence ledger as a fallback. Current Markdown structures
separate front matter, body, captions, tables and references. Table cells are
not guessed from flattened Markdown: automatic table maps use printed lines.
Unlocated source lines are retained with explicit uncertainty, not dropped.
`program_role` is current program placement, not a claim that the placement is
correct. `refresh_program_map` can recompute roles/order from saved provenance
without rerunning decoding or changing source text.

The physical grouping never crosses distinct saved columns; distinct regions
and one-em gaps also separate baseline segments. Repeated bibliographic tails
are placed using their nearest uniquely located neighbor in the same physical
column, with its preceding/following direction. This also distinguishes two
identical phrases inside one output paragraph. Case distinguishes an uppercase
heading from the same phrase in ordinary prose. Publisher citation notes follow
references as end matter, and printed end-matter labels are emitted once.
A uniquely witnessed first-page
DOI under Article information outranks the copy's older furniture label.

If the current author formatter replaces a standalone byline `and` with
semicolons, the automatic map may isolate that conjunction using two legal
word-boundary splits and assign it to furniture.other. This happens only for
one unambiguous conjunction on a byline and when no author output retains that
word. The omission is explicitly noted, and every split leaf remains owned.

`roundtrip_linemap.py` builds `map.json`, assembles it, and writes `comparison.json`
and `copy.diff`. It compares both all Markdown words and reading-copy words.
The latter excludes HTML page comments, fence language markers, the uncertainty
section, and the table fallback notice; all remaining words are compared
exactly. It exits **1** for any reading-word difference, **0** only for equality.
It never silently calls lexical differences layout differences.

Exact round trips are not always representable by this schema: legacy output
can duplicate a printed source, generate textual status panels, reformat author
markers, expand glyphs in context, or split source lines inside words. The map
cannot provide literal replacement text, reuse a source ID, or split a word.
These cases need a documented failed comparison, not fabricated IDs or text.

Unit checks are `test_export_lines.py`, `test_assemble_map.py`, and
`test_roundtrip_linemap.py`. Existing tests that import sibling fixtures need
their tools directory explicitly added to `sys.path` under `-I`;
`test_regions.py` uses `--unit` for its unit suite. Each test file must run in
its own Python process.
