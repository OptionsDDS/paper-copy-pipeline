# Paper copy pipeline

Turns a research paper PDF into one clean text file that an AI model can read, with every line traceable back to its place on the page.

**Status: stuck, and asking for help.** The program copies about one fresh paper in three without a serious error. The goal is 95 in 100. The last three rounds of fixes did not move that number. The details are below, with the measured results and the open problems.

## What it is for

A local AI model needs to read a personal library of research papers. Raw PDF text is not good enough for that. Columns get interleaved, tables turn into loose numbers, captions land in the middle of sentences, and running heads repeat on every page.

The pipeline makes a copy with these properties:

- Every word comes from the PDF's own text layer. Nothing is rewritten or summarised.
- Title, authors, affiliations, abstract, headings, body, tables, captions and references are each in their place and in reading order.
- Running heads, page numbers and watermarks are left out.
- Every piece of the copy can be traced to a page and a box on that page.
- Anything the program is not sure of is listed at the end of the copy.

The papers used so far are dental and medical journal articles. Most are two-column layouts from many publishers and decades.

## How the pipeline works

| Step | File | What it does |
|---|---|---|
| 1. Element boxer | `standalone/element_boxer_sc.py` | Reads the PDF and boxes each page: text lines and blocks, floats, tables, page furniture. A paper pass joins the pages. Rule 8 reads authors and affiliations. |
| 2. Shape and sign reading | `tools/read_shapes.py`, `tools/read_signs.py` | Optional. Reads text drawn as outlines and signs with broken encodings. Skipped when no local model is present. |
| 3. Copier | `copy_paper.py` | Builds `copy.md` from the boxer's page files. Writes the trace, the table records and the float records beside it. |
| 4. Page readers | `tools/run_readers.py`, `tools/agree.py` | Optional, GPU. Two local page-reading models read doubtful tables. A reading is used only when both agree cell by cell and every value matches the PDF text. |
| 5. Second pass | `tools/secondpass/` | A separate rule-based check of the finished copy. It adds its findings to the list of doubtful places. It does not change the copy. |
| 6. Check stage | `tools/checkstage/` | Optional, GPU. A local vision model answers narrow fixed-choice questions about boxed regions of the page image. Its answers can only move text. They cannot add, drop or change a word. |

Other parts:

- `layout/` is a second, smaller sorter based on font counts, a page frame, gutters and columns. Its rules are written out in `layout/README.md`.
- `tools/pcl/` writes the copy in a small markup language for italic, bold, superscript and similar marks.
- `tools/trace.py` and `tools/trace_show.py` check and show where each copied line came from.
- `standalone/vendor/` holds third-party PDF and font libraries with their own licences.

The core path uses only the Python standard library and the vendored libraries. Nothing is downloaded.

## Run it

Linux with Python 3 at `/usr/bin/python3`.

```bash
COPY_READERS=off COPY_CHECK=off ./copy_pdf.sh paper.pdf out/paper
```

The copy is `out/paper/copy.md`. Exit status 0 means the copy was written. Status 3 means it was written but the trace found lost or doubled lines. Status 1 means it failed.

A folder of papers:

```bash
./copy_folder.sh IN OUT
```

Tests:

```bash
TMPDIR=/tmp /usr/bin/python3 -I tools/checker/run_tests.py /tmp/copy-tests
```

Expected today: 162 test files, 2341 tests, 2 failing files. The two are `test_run_readers.py` and `test_trace_pcl_port.py`. Both failures are known and are not yet fixed.

## How it is measured

- A set of 25 papers is drawn at random and sealed. Nobody who writes fixes sees it.
- Each paper is copied. A frontier model then compares the copy with the page images, page by page.
- A **major** error is missing, doubled or misordered text, a wrong value, a table cell in the wrong row, or a missing author or caption.
- A paper is **error-free** when it has no major error.
- Two versions are compared as blinded pairs. The auditor does not know which copy came from which version.

Each fix goes up a ladder before it is combined with others:

1. It repairs the paper it was built from.
2. It changes nothing it should not on about 100 other papers.
3. It works on fresh papers or on made-up pages with the same layout.
4. It is scored on hidden papers before it joins the combined version.

## Results

Sealed exam, 25 papers:

| Version | Error-free papers | Major errors |
|---|---|---|
| Start of November 2026 | 6 of 25 | 87 |
| After the first round of repairs | 9 of 25 | 56 |
| After 13 more fixes | 9 of 25 | 59 |
| After 10 more fixes | 9 of 25 | 59 |

The same nine papers were error-free each time. The last 23 fixes changed nothing on the exam. The first two rows and the last two rows come from separate audits, so their error counts differ slightly by auditor.

Count of error kinds on 75 papers copied by the current version:

| Group | Papers | Error-free | Major errors |
|---|---|---|---|
| Scanned papers | 13 | 2 | 55 |
| Papers with a text layer | 62 | 21 | 99 |

Where the 99 major errors on text-layer papers fall:

| Kind | Papers | Major errors |
|---|---|---|
| Tables | 21 | 31 |
| Figures and captions cutting into sentences | 14 | 19 |
| Front page: title, authors, affiliations, abstract | 13 | 18 |
| Reading order | 8 | 11 |
| References | 4 | 10 |
| Lost text | 3 | 4 |
| Signs and symbols | 1 | 5 |

The latest round built six fixes for the most common kinds. Each was then scored on 25 hidden papers:

- The hidden papers held 44 known errors of those kinds.
- The six fixes repaired 1 of them.
- They flagged 3 more as doubtful.
- One fix broke two hidden papers. That was caught and repaired before it was combined.

Every fix worked on the papers it was built from. Almost none carried over. About 50 errors of these kinds trace back to about 25 separate causes, so a fix for one cause is worth one or two papers.

Two older results matter here:

- In October 2026 a frontier model read the page images and moved misplaced text. It could not add or change words. One set of 10 papers went from 3 error-free to 7 in a single pass.
- A local 27-billion-parameter vision model, asked fixed-choice questions, repaired about half of the same errors. It did not fully clear any faulty paper.

One comparison with an existing tool, on one set of 11 papers in October 2026: this program 2 error-free, Docling 0. That is a small sample from an older version of both.

## Where help is wanted

Ideas, criticism, pointers to papers or tools, and code are all welcome. Please open an issue.

1. **Fixes that carry over.** Hand-written layout rules fit the papers they were written on and little else. What approach generalises to layouts not yet seen?
2. **Table rows.** The core table problem is deciding which printed lines form one row. A wrapped cell and two short rows can have the same geometry. What signal separates them?
3. **A small local model as the checker.** The plan is for a local vision model to choose among fixed options at doubtful places, and never to write text. Which models, prompts and page markings work for this? How should doubtful places be found so that few are missed?
4. **Floats and captions.** A figure, table or caption that sits inside a column often lands in the middle of a sentence in the copy.
5. **Front pages.** Titles, bylines, affiliation marks and abstracts vary widely between publishers.
6. **Scanned papers.** About one paper in six is a scan and almost all of them fail. Should scans go through a separate OCR path, and which one?
7. **Cheaper measurement.** Scoring now needs a frontier model to compare each copy with its page images. Is there a sound automatic score for whole-paper copies?
8. **Use of existing tools.** If part of this should be replaced by an existing extractor or layout model, say which part and why.

## What this repository does not hold

- No papers. The test papers are under copyright.
- No audit reports, since they quote the papers.
- No development history. This is a snapshot of the current version.

## Things to know before reading the code

- Most of the code was written by AI coding agents under supervision, following the owner's rules. It has not had a full human code review.
- The two main files are very large. `copy_paper.py` and `standalone/element_boxer_sc.py` hold most of the rules.
- A few files hold paths to local models and data on the development machine: `layout/run.py`, `tools/checker/run_model.py`, `tools/checkstage/run.py`, `tools/run_readers.py`, `tools/read_shapes.py`, `tools/run_plos.sh` and `tools/copy_plos.sh`. The optional GPU steps will not run elsewhere without changing them.
- Two test files, `tools/test_cutlines.py` and `tools/test_symbolpua.py`, read test papers that are not in this repository. Their paper-based tests will not run elsewhere.
- Code comments and tests name internal paper labels such as `AT16` or `PL40`. They refer to test papers that are not in this repository.

## Licence

The project's own code is under the MIT licence. See `LICENSE`. The libraries under `standalone/vendor/` keep their own licences, which are included there.
