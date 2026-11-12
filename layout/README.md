# Layout sort

Sorts a born-digital paper into **main header, main text, floats, references and other**, in reading
order. Every unit keeps its page, its box in PDF points, its words and their character ids, so each one
traces back to the page.

The method is the user's, worked out step by step on AI11 on 2026-10-25. The rules are written out in
`rules.py`:

1. **Word boxes.** A word box is a run of characters between white spaces, taken from the boxer's
   reading layer. No two boxes overlap.
2. **Font census.** Characters are counted by font and size. Main text is the most common size, together
   with every letter font set at that size and at the body's reading angle (regular, italic and bold).
3. **Font groups.** Neighbouring words of one font and size form a group. A gap wider than 0.9 em
   inside a line is not a word space. A group never crosses a gutter.
4. **Frame.** The frame is the largest page's main-text box. It keeps that size on every page and moves
   only as far as needed so that no main-text word is cut.
   - Outside the frame is **other**: running heads, page numbers, footers.
   - A line outside the frame that is not repeated on other pages is kept: on page 1 as main header,
     on later pages as a float, with a flag.
5. **Gutters.**
   - A gutter is a strip of x that stays white through the main-text rows of a majority of the pages.
     Only pages where main text fills at least 40% of the frame vote.
   - On each page, a gutter that main text runs through is dropped. A page set in its own columns uses
     its own white strip, if it has main text on both sides.
   - After the gutters are found, the font groups are rebuilt so that none crosses one.
5b. **The boxer's floats and tables are large boxes.** Each float or table the element boxer found
    (rules 3–4) is one float. Its words take no part in the font census or the font groups, and no gutter
    passes through it.
6. **Columns.**
   - A page where every gutter runs full height keeps them.
   - On other pages, one box per column holds the main text. Material outside the column boxes is main
     header on page 1 and a float on later pages.
7. **Inside the columns.**
   - A non-main block becomes a float. Inline pieces stay with the main text: at most two lines tall,
     with main text on the same line in the same column (a bullet, a symbol, a run-in word).
   - Pictures (ink outside every text group) become floats.
   - A caption in the body font ("FIGURE 1", "Fig. 2.", "Table 3:") goes to its float.
   - A block repeated in the same place on many pages is other.
8. **Reading order.** The user's rule is: left column down, then the next column. It is applied as a
   series of cuts, each part cut again:
   - First, a section break: a white line across the region below which there is no main text, with
     main text directly above it in every column. The part above is read first.
   - Then a gutter that no unit crosses splits the region into left and right.
   - Otherwise, units that cross a gutter divide the region into bands, read top down.
9. **References.**
   - The heading is a "References" line (or similar) in the later part of the paper. It may be the
     first line of a non-main block, the line just before one, or a line inside one (the block is split
     there).
   - The reference blocks are the blocks after it whose entries read like a standard citation style:
     numbered, author–year (APA/Harvard), Vancouver, MLA/Chicago or organisation, each with a year.
   - Entries start at the block's own indent level, whether hanging or the reverse. Entries cut at a
     column break count.
   - A short note between blocks is passed over. The list ends at the first longer block that is not
     references.
   - A reference block with two columns of its own is split. The reference blocks of a page are read
     after the text above them.
   - Every other non-main block is a float.
10. **Alt main text.** As the last step of the floats, a text float of one to five words is not a float.
    It is relabelled **alt main text**. A picture, or a float the boxer found, stays a float.

Scanned papers are detected from the boxer's OCR-layer evidence and are **not sorted**, with exit
status 4: their font sizes come from OCR, not from the typesetting.

## Running

```
/usr/bin/python3 -I layout/run.py PDF OUT_DIR [--copy COPY_MD]
/usr/bin/python3 -I layout/run.py --batch LIST OUT_ROOT        # LIST: NAME<TAB>PDF[<TAB><TAB>COPY_MD]
/usr/bin/python3 -I layout/summary.py OUT_ROOT [IDS_WITH_ERROR_FREE_COPIES...]
/usr/bin/python3 -I layout/check_references.py OUT_ROOT           # numbered lists run 1, 2, 3 ...; author-year lists are alphabetical
/usr/bin/python3 -I tools/test_layout.py                          # the rules' tests
```

`run.py` always runs the element boxer on the PDF first (into `OUT_DIR/boxer`). The boxer's character
ids must agree with the reading layer that `words.py` reads, and page JSON from an older boxer does not.

The pixel steps (`worker.py`) need numpy and Pillow. They use `--python`, else `LAYOUT_PYTHON`, else
the local vLLM environment.

Outputs:
- `layout.json`: units in reading order, with kind, `box_pt`, text and words (text, box in pt, char ids).
- `layout.txt`: the same as plain text.
- `sorted.pdf`: the pages with the frame, the gutters and the numbered units drawn.
- `report.json`: census, frame, gutters, references details, flags and checks. With `--copy`, also a
  comparison with an existing copy.

## Built-in checks (exit status 3 when one fails)

- every word is in exactly one unit, or is other
- no main-text word lies outside the frame
- no main-text unit joins two columns, i.e. holds text on both sides of a gutter with none in it
- no two word boxes overlap
- every boxer run's characters spell its text
- at least 70% of word boxes have ink under them

## Measured (2026-10-25, 31 papers from the AG, AH and AI sets; outputs in `LANES/layout-runs/v5`)

- **Copies audited error-free** (AG10, AH10, AH11, AI05, AI07, AI11): main text is 99.0–99.9% in the
  copy's order, and reference words are 96.8–100%.
- **Numbered reference lists** (20 papers): every list runs unbroken from 1 to its last entry, checked
  on the PDF.
- **References found** on 25 of the 26 text papers. AI08 is a submission packet.
- **Scans:** 5 detected and not sorted (AG01, AG02, AH03, AH05, AH09).
- **Not yet verified:**
  - AI06 and AI10 are compared only with copies that have audited order errors.
  - AH06, a figure-heavy case series, has an incomplete copy.
  - Headings set in a font of their own are floats under these rules.
  - Author–year reference lists cannot be checked by numbering.
