# What we went over: the layout method (2026-10-25)

Sections A and B are your rules and corrections, in the order you gave them. Section C lists what I
added in the program to make those rules work on more papers; you have not ruled on those yet.

## A. Your rules, in order

1. **Word boxes.** Box every group of characters between white-space gaps (for example, "de-" is its
   own box). Draw the boxes on the PDF itself. No box may overlap another. Then count font and size from
   majority to minority. (Shown on AI11.)
2. **Big boxes.** Draw one big box around each grouping of the same font and size.
3. **Black box per page.** Draw a box around the main text, the majority font and size. It starts at
   the top-left pixel of the main text and takes in all of the main text. It may overlap other boxes.
4. **One shared black box.** Use the largest black box on every page and remove the per-page boxes.
5. **Shift it so no word is cut.** Move the shared box per page as needed. On AI11 the odd pages moved
   right by about 30 px, and you set page 7 to 30 px too.
6. **Crop and line up.** Make a PDF with everything outside the black boxes removed, the boxes lined up
   page to page.
7. **The gap.**
   - Find the largest white gap that is not an edge: the one seen on a majority of pages.
   - Mark it, but it may not go through a large box still on the page.
   - Do this on the cropped, lined-up pages with the coloured font boxes.
8. **Columns.**
   - If the gap is full height, it stays.
   - If it isn't, make a box to the left and to the right of it that takes in all the main-font boxes
     without crossing other boxes.
   - On three columns, the two boxes that overlap a middle column join into one combined shape.
9. **Main text includes bold and italic.** "Introduction" is the bold face of the body font at the same
   size, so it is main text. Main text is the body size in its regular, italic and bold faces. Redo the
   big boxes and the columns with that.
10. **Box everything else.** Box everything not yet boxed and not a full-page column:
    - each figure is its own box (Fig. 1 and Fig. 2 separately);
    - everything above the Introduction columns is one box;
    - the material at the bottom left of page 1 is one box.
11. **Classes.**
    - Boxed material on page 1 that is not main text is the **main header**.
    - What was cropped off (page numbers, header, footer) is **other**.
    - Figures are **floats**.
    - What remains is main text or non-main text. Box the non-main text (Table 1, the references).
12. **Pictures.** The search for non-main text also looks for float-like images or vector drawings, so
    float material left inside the columns is caught.
13. **Reading order.** Read the left column down, then the next column down, and so on.
14. **References.**
    - They are the non-main boxes at the end of the paper.
    - Their format repeats; on AI11, every line below an entry's first line is indented.
    - The word "References" (or similar) comes just before them.
15. **Everything else is a float.** Everything except main text and references is boxed and placed in
    floats.
16. **References, refined.**
    - "References" may be the first word inside the non-main box, or the line just before it.
    - References sit on the last couple of pages, and "how to cite this article" comes at the end.
    - Reference formats are standardised (MLA and the like), so the style gives them away.
17. **Alt main text.** As the last step after non-main text becomes floats, a float of one to five words
    is not a float. It is relabelled **alt main text**.
18. **Program.** Write the program that does all of this correctly, and keep it in a permanent place,
    not a scratch folder.

## B. Your corrections

- **AI05:** the middle gap is seen on a majority of pages when they are lined up. I had wrongly required
  it to run full height.
- **The three-column paper (AI06):** I had not kept the larger boxes, so boxes crossed into things that
  should be one box.
- **Visuals (AH04 bullets, the AI05 table):** large boxing was wrong again.
- **Column boxes:** when the gap is not full height, the boxes beside it take in only main text.
- **AI11 shift direction:** you said the odd pages move left; on AI11 they move right, which keeps every
  word inside.

## C. What I added in the program (your ruling needed)

**Words and font counting**
- The boxer is run fresh on every paper. Its character numbering must match the reading layer, and older
  page files did not.
- A gap wider than 0.9 em inside a line is not a word space.
- Text set at another angle, such as a sideways margin line, is never main text.

**Frame and gutters**
- Only pages whose main text fills at least 40% of the frame's height vote on the gap. A page votes for a
  strip that is white through 90% of its main-text rows, or through one unbroken run of at least half of
  them (the two-column part under a full-width abstract, as on AF08 page 1).
- The minimum gap width follows the type size.
- Strips a hairline apart count as one gap.
- On a page where main text runs through the paper's gap, that page uses its own white strip instead.
- A line outside the frame that is not repeated on other pages is kept: main header on page 1, a float
  elsewhere.
- A block repeated in the same place on many pages is **other**.

**Boxes**
- The boxer's own tables and floats are large boxes: each is one float. The gap's mark cannot pass through
  one, but large boxes do not decide whether the gap exists (rule 7).
- A boxer box that reaches over running body text (three or more long lines of main text, outside any
  caption) does not own those lines: they stay main text.
- A main-text word is main text wherever it sits (your rule 11): no header or float box takes it.
- A panel the boxer drew (a tinted or framed box: "Clinical Relevance", "How to cite this article") holds float
  material whatever its font (on page 1: main header); so is body-font text inside a frame drawn as lines;
  neither is ever references.
- A text float's box is its words' box.
- On page 1, short body-font lines above the first full paragraph of their column (a keywords line) are main
  header; a heading directly on top of that paragraph stays main text.
- A line that opens with a float label set apart ("FIGURE 6 …", "Table 3:") is a caption, never main text.
- A main-text piece of three words or fewer on the line of a bigger main-text box in the same column joins it.
- A page drops a paper gap where main text runs through its middle for half the text rows or three lines.
- Lines inside a box are cut like a page (its own full-height gaps with three lines or more on each side, then
  wide white bands), then follow the boxer's runs; a table or figure box keeps its rows; a lifted accent ("~") joins the
  line of the letter under it.
- Material outside the column boxes stays within its column, unless it runs through the gap itself (a
  figure or header across the page).
- A text block holding two columns of its own (a reference page set in other columns) is split at its
  white strip.
- A short non-main piece (a bullet, a symbol, a run-in word) with main text on its line in its column
  stays with that line.
- A caption set in the body font ("FIGURE 1", "Fig. 2.", "Table 3:") goes to its float.

**Reading order**
- A section break across all columns, with only non-main text below it, is read after the text above
  it.
- Only blocks that cross a gap divide a page into bands.

**References**
- The search starts at 40% of the paper, because in an author manuscript the tables come after the
  references.
- A "References" line inside a box splits the box.
- A heading is still found when a stray piece of one or two words sits between it and the references.
- A note under the last entry (a correspondence address, "Accepted for publication…") is split off as a
  float.
- Entries may start at either indent level.
- Names with old-style accents count; a name opens with a capital letter, or with a particle (van, de…).
- "References and Notes" counts as a heading.
- A reference box holding two columns of its own is split.
- The end of an entry cut off at a column break (it starts mid-sentence) stays in the list.

**Scope**
- Scanned papers are detected and not sorted.

## D. Checks the program makes

- **Every run:** every word is placed exactly once, no main-text word is outside the frame, no block
  joins two columns, no word boxes overlap, and every line's characters spell its text.
- **References, against the PDF:** numbered lists must run 1, 2, 3…; author–year lists must be
  alphabetical (Ø filed as O; "van Charante" under either convention).
- **Against existing copies:** only papers whose copies were audited error-free (AG10, AH10, AH11, AI05,
  AI07, AI11) count as a measure.
