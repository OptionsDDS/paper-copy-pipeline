# Copy trace

## Native trace (written by copy_paper.py)

```sh
COPY_PAPER_PDF=paper.pdf /usr/bin/python3 -I copy_paper.py PAPER_DIR   # writes copy.md, copy.trace.json, copy.checks.json
/usr/bin/python3 -I tools/trace.py PAPER_DIR [PDF] [--lines] [--json REPORT]   # validator
/usr/bin/python3 -I tools/trace_show.py PAPER_DIR u00001 --out unit.png
/usr/bin/python3 -I tools/trace_show.py PAPER_DIR p3.l012
```

Provenance is recorded when a unit is written, never by matching text later.
`copy_paper.Src` is a `str` whose value is unchanged but which carries the
source rows it was read from: `trace_row` registers a printed row (page, run
ids, read text) where the copy reads runs (`prose_row`, front-matter rows,
side text, DOI lines, rule 8 records, rule-6 header rows and the key words
deferred to their printed place); joins, concatenation, stripping and
slicing keep the rows (a slice of one row keeps exact character offsets; any
other cut keeps an unknown part, a *partial* claim). Front units also claim
rule 8's run ids or the runs inside its boxes; floats claim their caption ids
and table source/owned run ids; OCR items claim their `ocr:N` runs. At each
emission site the writer wraps the unit's text in two private-use sentinel
characters (removed before any check reads the copy) and records its kind,
claims and group: the cells/lines of one table, the authors of one byline, the
addresses of one source block and parts cut from one joined text share a
group. Generated labels and notices carry a `generated_reason`. Rows the copier
drops on purpose record their reason in the page's conservation exclusions
(for example a copyright row below an abstract, removed as article-information
furniture), so the trace reads them as furniture, not lost.

`tools/copy_trace.py` then builds the printed-line universe exactly as
`tools/export_lines.py` does (`pN.lNNN`; ids are D-020 addresses
`pdf:<sha256>:p<page>:c<first boxer character index>`), resolves claims to
runs and lines, and gives each line one status:

| status | meaning | fails the copy |
| --- | --- | --- |
| unit | all its runs in one unit group | no |
| furniture | every run has a recorded exclusion reason | no |
| uncertainty | its runs are named by an uncertainty-list statement | no |
| split | disjoint parts of the row in different groups, or part furniture/uncertainty | no (listed) |
| split_unverified | shared through a partial claim, so a repeat cannot be proved | no (listed) |
| flagged_repeat | parsed title/byline/address and the flagged "Front matter as printed" block | no (listed) |
| lost / partly_lost | runs in no unit, without furniture or uncertainty evidence | yes |
| duplicate | the same source characters in two unit groups | yes |
| partly_excluded | a body line (otherwise unit/split) whose own letters on its baseline were left in no rule-1 box or taken as furniture (check e) | yes |

A unit without any source claim (and not generated) also fails. Failures are
listed in the copy's uncertainty list and `copy.trace.json` (`accounting`), and
`copy_paper.py` exits with status 3 (copy written). `COPY_TRACE=0` skips it.

Code checks (`copy.checks.json`, each also listed under uncertainty):
(a) PDF text-layer words (`pdftotext -bbox-layout`) whose printed area lies
outside every text box of the sort, by page; (b) rule-6 main boxes, columns
or pages absent from `body-order.json`, and its unplaced boxes; (c) float
records without a caption or captions without a float (`copy.floats.json`);
(d) lines in no unit or in two units, and units without a source; (e)
`body_lines_partly_excluded`: for every body line, the upright reading-layer
letters on its baseline at its size, reaching it within one em (chained), that
are outside the page region, in no rule-1 text element, or in a run the copy
leaves out as furniture. Rotated or oblique letters (watermarks),
superscripts, other baselines, free-standing accents, small marks over one of
the line's letters, overprints and letters the copier omitted on paint
evidence (`copy_omitted`) are not the line's letters. Each failing line lists
the missing letters and why (`excluded_body_characters`); the copy exits 3.
`tools/cut_scan.py` is an independent scan (Poppler words) for words cut at a
line edge and body-font text counted as furniture.

`trace.py` checks the copy and PDF hashes and every unit span, recomputes each
line's status from the recorded claims, furniture and uncertainty runs with an
independent implementation (a line with recorded excluded body letters is
partly_excluded), and with `--lines` reruns `export_lines.py` to
compare line ids and run membership. It prints the same statistics and
accounting; exit 0 ok, 1 findings or an inconsistent trace, 2 missing input.

## Legacy matcher (`trace.py --legacy COPY_DIR PDF`)

```sh
/usr/bin/python3 -I tools/trace.py --legacy COPY_DIR PDF
/usr/bin/python3 -I tools/trace_show.py COPY_DIR u00001 --out title.png
/usr/bin/python3 -I tools/trace_show.py COPY_DIR p1.l006
```

The directory needs `copy.md`, `main-text.json`, page JSON and the decoding
artifacts used by the copier. The legacy tracer writes `copy.trace.legacy.json` and a
`.trace/source.json` extraction cache. It never rewrites the copy or its inputs.
The unchanged copier runs on disposable JSON copies to expose decoded source
runs, exactly as in `export_lines.py`; the temporary directory is removed.

Exit **0** means all non-generated units have unique exact character witnesses,
all decoded lines are accounted for, the strict ownership checks pass, and any
PCL file validates and maps. Exit **1** means the report was written but these
checks failed. Exit **2** means an input or extraction error prevented a new
report. There is no warning-only mode. An old report can survive an extraction
error; compare its recorded hashes before using it (the viewer does this).

## Ports and identity

`trace_port/pcl.py` is the complete standard-library reference parser from
`paper-copy-language/pcl.py`, with its original `parse`, `render_lines`,
`analyse` and character annotations. Its 63 positive and 92 negative keyless
fixtures and conformance runner are retained. The wrapper test runs them with
isolated Python. The parser source hash is in its header.

`trace_port/accounting.py` ports the exact rules from:

- `converter/convert_page.py::load_paper`, D-020: source SHA-256, page and
  character-index addresses, `pdf:<sha256>:p<page>:c<index>`.
- `converter/stages_baseline.py::order_streams/assert_stream_membership`,
  C-006: memberships are explicit; zero and multiple owners fail. Its truth
  runner's remaining-lines-as-furniture fallback is deliberately omitted.
- `pcl.py::_analyse12`, C-006/C-010: every reading character has an offset,
  source line and column, or an explicit derived reason. The Markdown adapter
  additionally records unresolved characters and competing exact addresses.

The line address uses its lowest boxer `char_ids` index. All original indices
are retained in `source_character_indices`. This is an explicit adaptation to
**the boxer's visible-character enumeration**, not a claim that its character
indices equal the prototype's pdfplumber enumeration. Each line also retains
`export_id` (`pN.lNNN`) and a document-wide `number`, starting at 1 (C-027).
Both the canonical address and exporter alias work in the viewer.

OCR lines have no native glyph indices. They carry a deterministic offset in
the page's decoded OCR character stream and an explicit `source_id_basis`
warning. Those addresses are not native PDF glyph identities. Source identities
are stable for the same source extraction; changing segmentation/decoding can
change them. The cache fingerprints input hashes and extraction code.

## Report contract

- `pdf`: path, SHA-256, page sizes, MediaBoxes and rotations.
- `copy`: relative path, SHA-256 and Unicode character count.
- `units`: kind, exact `span` and `text`, ordered source witnesses, status and
  unmatched spans. Table cells retain table, row and column numbers, including
  empty cells. Generated labels/notices have explicit reasons.
- `lines`: canonical and exporter IDs, document-wide line number, text, runs,
  source contexts, boxes, destination units and unmatched spans. Furniture
  exemptions require existing classification/exclusion evidence.
- `annotations.reading_map`: one entry per copy character. An exact source
  entry has `line_id`, `page`, `line` (document-wide) and `column` (zero-based
  index into the exported line text). Copy whitespace, markup and generated
  content are `derived`; missing or competing source addresses are unresolved.
- `accounting`: lost lines, multiple-unit lines, partially placed lines,
  unknown source references, duplicate source IDs and repeated source
  characters, including repeated use inside one unit. Every list must be empty.
- `statistics`: fully traced unit shares, accounted line share and the stricter
  exclusively accounted line share. Merely having some exact witnesses does
  not make a unit fully traced. Multiple-unit lines are counted in the ordinary
  coverage statistic but excluded from exclusive coverage and fail accounting.
- `layout`: characters outside units (blank lines, separators, page comments,
  fences and byline delimiters).
- `pcl`, if present: file hash, validated page/line marker offsets, source
  addresses and boxes, reference-parser reading text and annotations. Original
  PCL annotations gain source addresses only where the printed text matches.

Offsets are zero-based, half-open Python Unicode character offsets, not UTF-8
bytes. Native boxes use unrotated PDF user space, bottom-left origin, absolute
MediaBox offsets, and 1/72-inch points. Display boxes use the rotated MediaBox,
110 dpi and top-left origin, matching `pdftoppm -r 110`.

## Matching, failure and review

The earlier span parser, exact matcher and raster renderer are retained.
Matching preserves case, punctuation, accents, signs and values. Normalization
removes whitespace, known copy/exporter markup and optional line-end hyphens.
Unique exact anchors and complete matches supply witnesses; exact adjacent-line
context handles wrapped text. Saved table run membership constrains table-cell
matches, so an identical body phrase cannot stand in for a wrapped table cell.
No fuzzy edit distance, token-ledger allocation or arbitrary repeated-value
choice establishes provenance. Competing exact witnesses remain unresolved.

A source line can physically contain two authors or several table cells. The
revision's literal rule still fails it when those pieces reach multiple copy
units, even if their source character spans are disjoint. Such failures must
not be described as proven duplicated ink. This is a known mismatch between
physical line granularity and the requested author/cell unit granularity.

The printed-line universe is the exporter's decoded source universe. It does
not independently prove that every visible glyph was decoded. OCR is
unverified; unrecognized vector-outline text has no invented line. The tracer
cannot safely make missing or changed upstream copy text traceable, repair
upstream classifications, or remove the line-versus-unit granularity mismatch.
It reports and fails those conditions, preserving all evidence for review.

`trace_show.py` prints the exact copy text/spans and sources. A unit also renders
its source lines outlined in red; a line prints its destination spans and
renders with `--out`. Multiple pages become separate panels in source-use
order. A cell outlines the complete exported line, not an invented cell box.
For partly traced units these are candidate exact witnesses: a red outline is
not an assertion of unique provenance. Always inspect `status`, `unmatched`
and the character annotations. Units with no source witness cannot honestly
be rendered. `--pdf` accepts a relocated PDF only with the same SHA-256.
