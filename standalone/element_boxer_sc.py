#!/usr/bin/env python3
"""Element boxer, self-contained (element_boxer_sc.py): rules 1-8 and an additive rule 9
body-order ledger, on a reading layer that needs no installed package.

What differs from element_boxer.py is only where the page comes from:
  - the drawn objects (rules, fills, curves, images) come from pdfplumber 0.11.10 on pdfminer.six
    20260107, as before, but from copies vendored under standalone/vendor/ (with their licences,
    VERSIONS.txt and SHA256SUMS), loaded through this program's own import path; two patches
    (vendor/patches/) are applied in memory at import, the copied files stay byte-identical;
  - the characters, their tight glyph boxes, origins, sizes, angles, fonts and the unpainted verdict,
    which PDFium gave, come from this program's reading layer: pdfminer's content-stream
    interpreter, subclassed to keep the clip paths (rectangular hulls, inherited through forms with
    their matrices), the fill alpha, the text render mode, marked content and each text-showing
    operator as one text object; PDFium's text-page conventions (object order along a line,
    duplicate-object and duplicate-letter removal, box formula) re-implemented; and the glyph
    ink boxes read from the embedded font program with fontTools 4.67.0 (vendored subset):
    TrueType glyf control boxes, CFF and Type 1 charstring control boxes;
  - the shading bounds of each sh painting come from the same interpreter;
  - pictures are standard-library PNGs: the page background is pdftoppm's rendering when pdftoppm
    is on the PATH (BOXER_SC_BACKGROUND=white forces a white page), else a white page; the clean
    copy is that background with the art boxes painted white (no object is removed from a render).
    The carried drawing code (paint_elements, main_text) calls "PIL"; that name is this program's
    own standard-library drawing shim, never Pillow.
No package outside standalone/vendor/ is imported: a guard on the import path refuses any module
that is neither standard library nor vendored. The JSON and text outputs never depend on the
pictures. Known differences from PDFium are listed in standalone/REPORT.md.

The original program's docstring follows with the reading-layer differences
(rule 1's "by PDFium" now names this reading layer) and the additive rule-9 contract.

Element boxer: nine rules, applied in order, to the pages and then the paper.

Input : the page mapper's document.map.json and the paper PDF; a page, and optionally a float label.

Running it:
  one page,   rules 1-5:  element_boxer_sc.py --pdf P --page N --out DIR/page-NN
  all pages,  rules 1-5:  element_boxer_sc.py --pdf P --all-pages --out DIR      (writes DIR/page-NN.*)
  the paper,  rules 6-7:  element_boxer_sc.py --paper DIR                        (after rules 1-5 on every page)
  the paper,  rule 8:     element_boxer_sc.py --authors --pdf P --paper DIR      (after rules 6-7; writes DIR/authors.json)
                         also writes rule 9's DIR/body-order.json after rule 8.
  the paper,  rule 9:     element_boxer_sc.py --body-order --paper DIR          (replay saved classifications; no PDF needed)
  --map M is optional and used only in float-label mode (--label), which is not exercised here.
  --no-draw writes the JSON and text outputs only, no PNGs (for --page, --all-pages and --paper).
  --page N must lie within the PDF (1 to its page count); a paper of 100 pages or more is read whole.
  --draw-only redraws the PNGs from an existing page JSON; --print-lines prints every text run
  of the page after the summary line (off by default: the paper's text stays out of the terminal).

Output of a page (rules 1-5), DIR/page-NN.json, top-level fields:
  label, page, region_box_px, reading_angle, params, counts
  regions    rule 1: id, box_px in the page frame, source (poppler | grid | panel),
             promoted (active atomic region or supported page-level candidate), supported;
             parent identifies a panel's child candidates. Child boundaries are deferred
             until rule 7 can order the parent atomically. fallback marks a single page
             region when Poppler layout is unavailable.
  marker_moves  rule 1: run (receiving element id), from_line (one-based line before
             marker repair, within its angle), to_line (final page line), angle,
             text and char_ids for each re-homed marker or citation fragment;
             kind "sub" identifies a lowered run (absent for raised markers).
  hidden_layers  rule 1, present only when glyphs are excluded: dropped colour
             signature, glyph count, fonts, text, bounds, source_ranges (half-open
             indices before visible char_ids), and PDF visibility evidence.
             Duplicate-colour decisions also record the kept signature and text
             similarity. counts.characters_hidden_layers sums these records.
  scan_evidence  rule 1, only on confirmed OCR raster pages: clipped union coverage of the four
             largest images, text render-mode/opacity/paint-order counts, Creator/Producer,
             and the OCR-layer decision. >=90% image coverage plus >=95% invisible content text
             (or an explicit OCR engine) qualifies; the reader and audit_scans.py also
             expose >=80% coverage candidates for review without changing their page records.
             Content needs >=20 characters and excludes visible text wholly in the outer
             8% header/footer bands from its denominator; the copy retains those margins.
             Qualified pages also retain uncorrected OCR runs separately from visible
             elements. This record changes none of rules 2-8 or their memberships.
      counts: characters_in_region, characters_in_elements, characters_unpainted, characters_unmapped, characters_recovered_from_unmapped, characters_recovered_from_code,
              characters_recovered_by_route, unmapped_glyphs (font/code/name/count),
              characters_corrected_from_glyph_names, characters_covered, lines,
      text_runs, rules, fills, outlined_text_runs, images, full_width_rules
  elements   rule 1: one record per element: id, kind (text | rule | fill | image | background | outline |
             clipped), box_px, and for text: line, angle, text, char_ids, size_px (the line's),
             font (full PDF name, or names for mixed runs), font_spans (native-text offsets).
             furniture_reason, when present, records a PDF-proven diagonal watermark,
             proof margin numbering or query. Those runs retain their characters but
             are isolated before word/line building and never enter rules 2-5.
             Their standalone blocks exist only to record the furniture in rule 6.
             The page's fonts summary counts assigned characters by full font name.
             glyph_corrections lists glyph-name overrides with run, zero-based offset,
             from, to, font, glyph_name, source_code and char_id; unassigned characters
             have null run/offset and a box. The per-page count covers distinct IDs.
             run_size_px (the run's own), lead_size_px (present only for a run of capitals whose first letter is set
             larger than the run's size: fake small capitals; that letter's size), band, flags, line_end_hyphen (true when present), and label_font (true, present only when
             the run opens with a caption label set in a font of its own, rule 4); for a drawn
             object, source (line | rect | curve | image | shading); drawn objects share the
             reading layer's frame (plumber_shift_px). A fill or image under the page's text area
             (text_area_background) is kind background with a basis, like a blank page backing.
             ink_parts, when present: a compact character-backed index of gaps wider than the
             run's median letter size; each part has text, char_ids, box_px and run_size_px.
             This index changes no rule 1-5 grouping; rule 6 alone may use it at a known gutter.
             region identifies the owning region. A run divided at a supported page-level
             boundary carries region_source (the original run id) and region_parts with its
             fragment's char_ids. Every fragment retains the original rule-1 line id.
  blocks     rule 2: id, box_px, members (element ids), kinds, text_lines, text
  tables     rule 3: id, box_px, angle, grid_lines, tracks, lines, members, witness, own_fills,
             and anchored (present when the table was found from its caption)
  tables_rule3  the same before rule 4 demoted grids inside figure floats
  table_candidates  refused/bounded rule-3 candidates: box_px, why, and bounded_box_px when available
  floats     rule 4: id, box_px, caption, blocks (rule 2 box ids; table:N; chart:N for a chart drawn in pieces), basis
             caption_members (explicit caption text ids when separated from drawing labels or justified fragments),
             lettering (text element ids joined to a figure), members (caption and graphic element ids),
             demoted_tables (unlabelled grids belonging to the drawing), when present.
             lettering:block:N names an exported graphic block. Blocks from which text moved retain
             their original members, box, kinds, line count and text in before_lettering.
  unpaired   rule 4: caption labels without a graphic on the page and graphics without a caption
  art        rule 5: id, kind, box_px, basis
  caption_boxes_px, flags, pass (2 = after the art-free rerun), first_pass (counts of pass 1)
  A page with no printed characters (blank, or pictures only) is still a record: its drawn objects
  are its elements, it has no blocks, tables, floats or art, and its flags say so.
  PNGs: page-NN.png (pass 1 boxes), -no-floats.png, -floats-only.png, -clean.png (art-free)

Output of the paper (rules 6-7), written by --paper:
  each page-NN.json gains main_text:
      body_size_px, header_bottom, footer_top, columns
      blocks: id, cls (main | furniture | title | authors | other | aside | caption | rotated),
              why, order (rule 7, None when not main), size_px, lines, box_px, text
      counts: blocks per class;  reading_order: block ids in rule 7 order (a margin label rides
      with its block and is listed after the page's blocks only when it stands beside none);
      band_boundaries_y: rule 7 cut positions
      furniture: each excluded line's text, member runs, box and reason; furniture_sources
                 retains table/block membership before removing a furniture run from a float
      page_top_check: lowest upright header bottom, first main top, gap in pixels,
                      first column top, warning flag and band-excluded text evidence
      splits: source block id, derived part ids, empty gutters_px, why, and any divided runs
              (the complete source run plus part ids, so --paper can be repeated). The original
              rule 2 block remains; derived blocks in blocks carry main_text_source. Only runs
              of a successfully split main block may be divided, retaining all their characters.
  PNGs: page-NN-main-text.png, -other.png, -reading-order.png
  DIR/main-text.json: body size, bands, title and author boxes, flags, per page columns, counts and
                     splits (source/part ids and gutters, without the source run payload)
  DIR/main-text.txt:  the main text in rule 7 order, "[n]" before each block, "## page N" per page

Output of rule 9: DIR/body-order.json, schema body-order/1. Its blocks list contains
  every placed rule-6 main box once, with page/id, box_px, first_words, last_words,
  page-local column, heading decision, level and review flags. Numbered heading
  evidence retains observed/inferred numbers, sequence state and list precedence.
  Edges connect consecutive boxes and record
  same_column, next_column, across_float and next_page transitions, layout and
  grammatical evidence, continuation and conflicts. Pages retain column witnesses,
  pitch and band cuts; start_classes retains the measured first/later intervals
  and their samples. End classes exclude column/page ends and the tested edge.
  Unplaced main boxes are explicit, flagged records. Rule 9
  never changes rules 1-8, their classifications, or the copy program's output.

Rule 1 (elements): box every element inside the float or page; a whole page's region is the visible
        page, its CropBox within its MediaBox in the reading frame (sc_page_box_px), so no printed
        character at a page edge is outside it because the CropBox starts away from the origin. Every character is in exactly
        one text box or recorded as unpainted (outside its clip path, by the reading layer's
        PDFium-convention verdict); every drawn object is a rule, fill, image or outlined-text box.
        A large edge image whose decoded gray/RGB samples are all white and whose
        optional soft mask is uniformly opaque is retained as background evidence;
        it cannot contain text, merge Poppler regions or become a figure.
        Without an embedded font program, a positive PDF character width supplies
        the horizontal box. The whole-font hull supplies only its vertical extent,
        never evidence that neighboring font pieces cover each other.
        Before clustering, oblique text snapping to the upright body frame with light fill
        or outline rendering,
        eight collinear letters, and a span of 40% of both page axes is recorded as
        watermark furniture. Its size is at least three body em. On those pages dense
        consecutive outer-margin digit lanes are isolated too; proven lanes cover
        sparse later pages, and six consecutive tN.row labels identify table proof
        numbering. Editorial query glyphs in those same lanes remain furniture.
        Their original glyph IDs and boxes survive, without influencing words,
        overprint removal, blocks, tables or reading order.
        The PDF's own space glyph ends a word. A font's space glyphs are trusted when they mark
        at least four in five of its word-sized gaps over 20 or more such gaps on the page;
        without a glyph, a trusted font breaks only beyond wordspace_max_em. For an untrusted
        font, a word break is an advance gap beyond text_space_em, using ink only when advance
        is unknown. The reader exposes each glyph's advance end in page and reading frames.
        An oversized paragraph initial spanning at least two neighboring normal-sized
        rows is detached before baseline clustering and attached once to the first row;
        its actual glyph box is retained but normal letters set the line tolerance.
        A large letter beside other large letters is a word or logo, not an initial.
        Poppler layout blocks supply page regions, converted from points to PARAMS dpi.
        Drawn grids, caption-anchored tables and backed panels merge overlapping blocks
        into atomic regions. Panel child candidates are retained but not activated: rule 7
        does not yet preserve their parent as one reading unit. At page level, candidates
        with x overlap below 20% of the narrower need support on both sides from at least
        column_min_lines stacked nonempty text lines. Each witness spans at least 80% of
        its candidate's width; witnesses are vertically co-extensive within that many em.
        A bridging run splits only at such a boundary and a word gap of wordspace_min_em
        or more, retaining every character and line id in character-backed region_parts.
        If Poppler is unavailable or has no blocks, the page stays a single region.
        A text element ends at a gap wider
        than one letter height, or wider than three of its line's own word spaces, or at a rule
        that spans the line. Each text orientation is boxed in its own frame. Letters of one
        size on one line share a baseline: when much larger type (1.5 times or more) widened a
        line's tolerance, a group of two or more same-size letters whose baseline lies more than
        line_tolerance_em of their size from the largest group of that size moves to the line at
        its own baseline (or starts one) before runs are built, so a byline beside a display
        title is never interleaved with its next row. A raised run
        smaller than superscript_em of nearby body text and ending above its baseline
        belongs to the line whose x-height band it overlaps most, or, without overlap,
        the nearest baseline below its bottom. Candidates must be within superscript_shift_em
        of its baseline and beside it within a word space, with room for its ink horizontally.
        Adjacent small glyphs on the same baseline are considered together even if earlier
        clustering split them between lines. The repaired line's characters and runs stay in
        x order; a repaired marker within a word space of the preceding text is glued to it.
        Body anchors contain a word or multi-digit value on one baseline, not only an
        isolated variable or punctuation. Stacked raised scripts, raised words and alphanumeric
        identifiers are left in their existing layout: flattening them needs a mathematical
        representation to preserve their tiers and word boundaries.
        Lowered runs smaller than superscript_em use the descender band, from the body
        baseline to 0.2 em below it. Their baseline is lowered by 0.1 to
        superscript_shift_em; their ink starts below the baseline minus 0.25 em,
        overlaps the descender band and ends below it. (Subscript ink may straddle
        the baseline.) The greatest overlap wins. A preceding full-size letter
        within a word space must also immediately precede the run in the PDF's
        character sequence without a space glyph: independent small lines, footnote marks and cells
        are not inline scripts. Repaired subscripts stay in x order and glue
        through the same marker path as raised runs.
        Page marker_moves records every changed attachment. A caption label ("TABLE 4") is its own
        element. A line-end U+0002 is printed as "-" and marked on its run, without joining words; missing text maps through the Adobe Glyph List, the standard Symbol names or the embedded encoding. An unresolved glyph is printed as U+FFFD (the replacement character), flagged and counted in characters_unmapped; its code is never guessed as a letter. Page counts and the reading log record recoveries by route and unresolved font/code/name counts. A selected glyph's exact name in SC_GLYPH_SYMBOLS overrides a conflicting single Latin letter or digit (asterisks: letters only); existing symbols, ActualText, hidden text and generic glyph names are unchanged. These corrections preserve boxes and advances and are recorded as glyph_corrections. At a two-font overprint where both glyphs share the place (overlap beyond overlap_share of the wider, one baseline, like sizes) the last painted character remains and the covered one increments characters_covered; an italic overhang onto a narrow neighbour is flagged only.
        Before boxing, visible-layer/1.1 compares the two largest fill-colour groups
        (each at least eight glyphs and 5% of visible glyphs), with text similarity
        at least 0.7 and overlapping bounds. The later-painted group is kept only
        when every discarded glyph has an identical opaque later-painted twin
        in the same font, size and place. Clips, zero alpha and render modes 3/7
        independently exclude unpainted text. Different clip/visibility twins
        cannot suppress one another in the reader's earlier duplicate filters.
        Every excluded layer is recorded in hidden_layers; existing OCR scan
        runs remain available. No layer record is added to unaffected pages.
Rule 2 (larger boxes): group the element boxes. Two elements belong to one larger box when
        they are stacked with at most one letter height of white between them (measured on the
        smaller of the two) and overlap sideways, or when both sit inside one drawn frame
        (fill or image). No union, including a containment union or a transitive path
        through another element, may cross a corroborated page-level region boundary.
        The larger boxes are built from the element boxes alone. Before stacking,
        a numbered heading set larger than the page's
        character-weighted median text joins its number, optional separator and words on the
        same line, then its directly stacked continuation at that size. Its runs cannot stack
        with the smaller paragraph below or enter the column opened by another heading
        beside it. Corroborated region boundaries constrain heading growth before
        membership is reserved. Each baseline shared by separate heading blocks is
        recorded in their line_splits, with the runs belonging to that column.
        A detached paragraph initial uses its
        receiving line's size for stacking. Unpainted text is not a box.
Rule 3 (tables from the grid): a candidate is a run of consecutive text lines whose runs fall
        into the same column tracks, line after line (at least two lines), together with a
        drawn witness: a rule or fill spanning two or more of those tracks across, or two or more
        of the grid lines down (a shaded column band), lying within the grid and covering mostly
        grid lines. A rule drawn in pieces end to end (a table ruled cell edge by cell edge) is one
        rule: pieces whose ends meet within rule_join_pt are joined before this test. For this test
        the grid's band includes the header lines directly stacked above its data rows (each run
        within the grid and narrower than header_cell_share of its width, at most header_max_lines,
        stopping at a caption line); the prose-beside test below keeps the data rows' band.
        Without a Table caption on the page, the candidate needs drawn boundaries enclosing
        at least two cell rows: matching horizontal rules, a boundary joined to an interior
        divider with cells on both sides, or repeated shaded row bands with matching edges.
        Column gutter rules and a distant page separator do not witness such a grid.
        Three or more tracks, since two tracks alone can be a two-column layout. The tracks
        are the merged sideways extents of the runs; a header spanning two columns is allowed. A
        single-run line inside the grid (a group label) belongs to it. A run on a table baseline
        whose rule-2 box lies clear of the drawn grid sideways and holds a line outside the grid
        band is prose beside the table, not a cell; so is one with nothing drawn within a letter
        height of it across the grid's band (a heading in the next column on a table baseline).
        The grid's lines end where its drawing ends: lines at either end lying beyond its witnesses
        by more than note_gap_em letter heights are not the table's (a page footer whose runs
        happen to sit in the tracks). Two grid boxes that overlap are one table (a
        header block over its body). The box extends to the table's own fills and rules: a drawn
        object overlapping the box on both axes whose every covered text line is a line of the
        table (cell fills, row bands, side rules), so the box edge is the drawn edge, not the
        text's, and the gaps below are measured from it; a drawn object that would carry the box
        over a caption line (one frame drawn round the table and its caption) is not the table's
        own. The box then runs outward over directly stacked lines and
        rules no wider than the table, to the table's outermost spanning rule, so headers and
        footers inside the rules are included; below the last rule it also takes the note: text
        lines directly stacked under it, no wider than the table (a line's runs clear of the table
        sideways are the other column's text on the same baseline, not part of it), up to the first white gap wider
        than one and a half letter heights (note_gap_em; on the development papers notes sit at
        most 1.12 letter heights below the table's drawn edge and body text at least 1.95). The
        note also ends before two consecutive body-sized lines filling a text block at least two
        thirds of the table width beyond its drawn extent when their type is larger than the cells
        and ordinary caption type. A display caption (heading_size_ratio or more of the larger of
        the page median and cell size) is not a note-size witness. Only spanning objects starting
        within a letter height of the lower edge can extend that drawn extent; a page background
        or distant footer cannot protect prose. Narrower columns need separate table boxes first:
        two aligned independent captions above a combined grid, separated by an empty drawing
        gutter, cause each side to be re-measured independently. Without that size change
        the note stays: a page dominated by table cells cannot establish body size reliably. The
        box never takes a caption line; that is rule 4's. The box is
        the whole table; rows and columns are not decided here. A "Table n" caption with no grid
        table beside it anchors one (tables_from_caption): the lines directly under it, or over
        it, to a white gap of caption_gap_em letter heights no drawn object bridges, a line of prose
        (prose_share), a heading or the next caption, within the caption's width or that of the
        table's own rules and shading. Two consecutive body-sized lines larger than the cells and
        ordinary caption type, filling a rule-2 column outside the connected drawn extent, also trim a supported candidate,
        even on shared column baselines; that column must occupy at least a third of the candidate
        table's width. Its columns are the white channels (channel_em wide, ink in
        at most channel_ink_rows of the cell rows) down its cell rows. Body-sized prose crossing
        channels established by the first four cell rows also ends the table, even at the cell size.
        Drawn objects covering rejected prose cannot grow the box back over it. Two or more cell rows and
        two or more columns make it a table, and its drawn objects are its own, never art.
        Touching header fills establish the whole table width. A fill bounds the caption's
        panel only when it actually contains the caption, not when it merely starts below it.
        A label inside a shallow caption band followed by connected, sometimes alternating,
        shaded rows and two baselines of separated cells also anchors a small table. The bands
        bound its region before a neighbouring chart; they may replace an overgrown grid only
        if none of that grid's text lies outside the recovered cells and caption. The caption's
        own fill is removed from separate graphic blocks so it cannot compete with the grid for pairing.
        Prose below the cells is trimmed before the final column test. A captioned one-column
        list is also a table when repeated separated row bands and aligned entries witness it;
        its caption follows the title's face across wrapped lines, and its final unshaded row
        must end within two letter heights of the last band. Such a table is marked "banded list".
        A captioned numbered or bulleted list also qualifies with three entries in one or two
        aligned columns (at least two per column), ending before prose or a large gap. A smaller
        definition note immediately below is retained. Its caption can have a separately typeset
        number; rule 3 records that label and separates its caption block from the list cells,
        preserving the native text and character ids. Three or more sentence-like, column-width
        lines beside a drawn table, larger than its cells, stay outside it even if rule 2 merged
        their blocks. Smaller table notes are not prose witnesses. A run starting near the outer
        caption/drawing edge and extending into the next column is excluded. Refused grids and
        bounded candidates are recorded in table_candidates with their boxes and reasons.
Rule 4 (floats with captions): a caption label is "Fig.", "Figure" or "Table" followed by a
        number and then . or : or nothing, standing first in its block; a label word in capitals
        ("TABLE 1") may run straight on into the caption's text, and so may a label set in a font
        of its own (a bold "Table 1"; a figure label so set may be joined to the words by an en or em
        dash; rule 1 marks the run label_font). A float is a larger box
        holding a graphic together with a caption label; a rule-3 table holding a Table label;
        or a caption-label box directly adjacent to a graphic or table, stacked or side by side,
        with no other block between them, in the caption's own reading frame; each caption and
        each graphic is paired once, the nearest pairs first. A Table label
        pairs with a table, a Figure label with a graphic (an image, outlined text, or a drawn
        chart holding its own lettering). A figure float absorbs an image block that touches
        it (a picture stored as strips) and a graphic block beside it, sharing at least half the
        shorter one's height with nothing between (a panel of the same figure), never a table or
        a block with its own caption. A grid box inside a figure float, or holding a Figure label
        and no Table label, is the figure's lettering, not a table. A caption left without a
        graphic, or an image or table without a caption, is recorded as unpaired (a figure whose
        caption is on another page). The page is then split into two copies: the paper without
        its floats, and the floats alone, each keeping the boxes of rules 1 to 3.
        A stacked image panel within one letter height also joins when its only text is panel
        letters inside its images. An unpaired Table label can recover a ruled table whose
        merged cells defeated rule 3: matching top and bottom rules joined by an interior
        column divider, with text on both sides, enclose the cells. Drawing and lettering
        ownership is then resolved before trimming: a figure expands to the supported
        graphic/label grid, records its lettering and members, and removes those runs
        from mixed body blocks (the original block is saved in before_lettering).
        Nearby captions, prose, labelled tables and header separators bound the join.
        A Figure label among graphic labels is split into its own caption
        block before pairing, following consecutive lines aligned by left edge or center in its text face and size.
        A face change already present within a caption line allows that face to continue below it.
        Mixed-case labels also require numbered punctuation (or a distinct label face) and a drawing in the
        source block; long preceding labels must differ in face and be smaller than the caption
        (unless they lie inside an image or drawn shape that ends above the caption label, or, outside the
        page's body face, touch a shape beginning above the label that carries no body prose above it),
        and a larger prose face bounds the split.
        Unlabelled grids already proved to be figures do not block this split. Separated words
        on a justified caption baseline join across successive gaps in that same face and size.
        These recovered captions retain explicit text membership for the copy reader. Paired
        thin-arrow diagrams can seed lettering too. A preceding caption cannot
        claim labels beyond its own graphic band. Table-owned blocks stay intact.
        The copy reader honors lettering ids before inline recovery and keeps
        figure captions out of independently classified body columns.

Rule 5 (journal art): on the float-free copy, remove what is neither the paper's text nor its
        floats. Outside every float and table box: every unpainted (clipped) text run; every
        drawn object (rule, fill, outlined text); and every image that lies wholly above or below
        the text frame (a logo in the header or footer band). An image or drawn object inside a
        text line (an ORCID icon, drawn or as a picture: no taller than the line, and beside a
        text run, and standing alone: every drawn object near it is also inside a text line) is part
        of the line and is never art; nor is a fill that holds a text run (a panel drawn around
        the abstract). The text frame is the hull of the text blocks with two or more lines in
        the page's main orientation together with the page's floats and tables. An image alone inside the frame with no caption is kept and
        stays flagged as unpaired (a figure whose caption is on another page). The result is a
        third copy: the paper without floats and without art. Rules 1 to 4 then run again with the
        art's drawn objects left out, so an element the art had split (a name printed over a
        sidebar) is boxed whole; the clean copy carries those boxes. A drawn object touching a
        float or table is that float's or table's, never art.

Elements:
  text run   a maximal run of characters on one baseline with no gap wider
             than the run's own letter height (one em) and no rule between
  rule       a drawn line or a filled rectangle thinner than rule_max_pt
  fill       any other filled rectangle or curve inside the region
  caption    text runs on lines above the first full-width rule
  note       text runs on lines below the last full-width rule
  body       everything between (header band and data; not split further here)
Settings: every tuned threshold is in PARAMS, in one place, printed with every page result as params;
each key's meaning is the comment beside it there. The fixed proportions that define a test (half a
width, one letter height) stand in the code beside the sentence that states them. Environment:
BOXER_ORDER (an experiment: 15234 runs rule 5 before rules 2-4; the default 12345 is the rule order;
when set it is recorded as order in the page JSON) and BOXER_SC_BACKGROUND=white (pictures only: a white
page under the boxes instead of pdftoppm's rendering). The reading layer's own settings are READ_PARAMS,
fixed with this program's hash. The keys of PARAMS:
        dpi, line_tolerance_em, dropcap_ratio, run_gap_em, run_gap_wordspaces, wordspace_max_em, wordspace_min_em,
        rule_max_pt, full_width, superscript_em, superscript_shift_em, overlap_share, rule_join_pt,
        header_max_lines, header_cell_share, table_min_tracks, stack_gap_em, furniture_min_pages,
        furniture_pos_px, band_tolerance_em, body_size_tolerance, column_min_lines, flow_gap_em,
        same_line_em, column_indent_em, chart_label_chars, note_gap_em, side_overlap_px, strip_touch_px, icon_max_em, outline_max_em,
        caption_gap_em, channel_em, channel_ink_rows, prose_share, furniture_min_share,
        band_edge_share, author_gap_em, author_stack_em, author_size_tol, superscript_raise_em,
        advance_space_em, text_space_em, zero_size_px, heading_size_ratio, title_size_share, orcid_letter_share,
        orcid_name_share.
Rule 6 (main text): furniture is classified per line; mixed blocks are partitioned
        before classification and each split recorded, retaining text outside a band. On the float-free, art-free copy of every page, the main text is separated
        from everything else. Body size = character-weighted median size outside floats.
        A repository download cover with service controls/counters, no abstract,
        and an article abstract on the following page is wholly furniture. The
        following article supplies the title/byline; the cover supplies no bands
        or column witnesses. Explicit rule-1 proof furniture is always excluded.
        Page furniture = lines whose text, digits masked, recurs at one position on furniture_min_pages
        (two for papers under eight pages)
        pages and on furniture_min_share of the paper's pages, plus every line inside the header and
        footer bands set by such lines within band_edge_share of the page's top and bottom,
        only where they overlap that page's text columns. Margin furniture never sets a band.
        Table continuation labels never set a band either. A nonrecurring line attached
        to its preceding line in the same substantial body block is protected from the footer band.
        A drawn publisher citation box keeps all enclosed lines, including journal/year/DOI
        text, outside recurrence, band and first-sight furniture matching.
        The header band and its tolerance stop before that page's first body/heading
        column line (allowing the column's normal indent), spanning heading or caption.
        A numbered display heading includes its separate number and divider runs
        when locating the column edge; its same-size wrapped lines stay together.
        On the title page, publication mastheads above the largest type cannot supply
        this limit. Connected table headers are not recurrence furniture; numeric
        group labels between table headers and cells are not first-sight folios.
        A single narrow rotated run spanning most of the page height in the outer
        side margin is furniture, never a band witness. A diagnostic records the
        header-to-main gap and warns about five or more body-size words lost by band.
        Explicit publication notices and folios outside the page's text frame need no recurrence;
        isolated continuation labels at a column/table foot are furniture too. These local
        decisions do not widen the paper's bands. Each decision is recorded, and any affected
        table retains its original membership for a repeated paper pass. Title = the lines at
        the largest size on the first page; authors = the band stacked under it, or the lines under
        the title-size text inside the title's own block. Text columns =
        extents of column_min_lines-line blocks at body size or larger (the page's own, plus the
        paper's after the title page). Main = in a column at body size or larger, or smaller and
        within flow_gap_em under main text, or opening a column after a full one (references, back
        matter), or sentence-like smaller sections of ten or more lines following main text
        or a heading in their column, excluding captions, table notes and footnotes;
        the abstract (from its heading) and the reference list (from its heading to the end
        of the paper) come in whole; on the title page smaller text and anything above the title is
        front matter.
        After classification, a main block spanning known text columns splits only at a gutter
        empty of its own ink on every line. Each part either needs column_min_lines lines
        with median width at least half its column, or starts at a known column's left
        edge (including short headings). Tables, floats, captions and furniture keep
        their ownership. Every divided baseline is recorded with its run membership.
        Output: -main-text.png, -other.png per page; main-text.txt and main-text.json per paper, in
        rule 7's reading order.
        With no page records, write an empty flagged record and one stderr line, exit 0.
        Run with --paper <dir> after rules 1-5. Full statement in main_text().
Rule 7 (reading order): the main text of rule 6 read top left to bottom right, the count running
        on across pages. Each page is cut into bands at a white channel across the text frame
        where the stretches above and below use different columns, neither set within the other, and
        a column on one side lies across a different column on the other (the floats of rule 4
        hold their places, unread); within a band the rule 6 columns read left to right, blocks
        top to bottom, same-line blocks left to right, a margin label riding with its block. Never a
        cut at the widest white gap. Output: order numbers in main-text.txt and the page JSON,
        and -reading-order.png per page. Atomic panels and captioned lists wait until an
        interrupted paragraph or introduced list finishes, including a continuation from
        the preceding page. Captioned lists retain their caption membership for the copy;
        this does not change detected tables or floats. Full statements in reading_order_bands(),
        reading_order_captioned_lists() and reading_order_defer_panels(). A title-page front
        panel beside an introduction is bounded by name rows, an italic summary and a
        justified column matching the next page's prose face, size and width. Rule 7 corrects
        that panel's export ownership, orders its abstract first, and records front_columns
        so rule 8 and front-matter fallbacks cannot cross the body gutter.
        An unfinished abstract ending the page's reading order continues on the next
        page with its first aligned text in the same face and size, ahead of the body columns. Its keyword
        suffix stays attached even when it uses smaller type. This ownership is recorded
        as abstract_continuation; a completed abstract cannot claim the following body.
Rule 8 (title, authors and affiliations): on the first text page, after rules 6-7, the title, the
        author box and the affiliation box are found and checked against each other; it reads
        page records and the front page's characters, leaving rules 1-7's data unchanged. Explicit
        later author-detail panels can supply missing marked affiliations. Joined
        author accents and initials are recorded in page-01.json's rule8.author_joins. Output,
        DIR/authors.json: title (text, box_px, lines, size_px, left_out); authors (name, markers,
        notes, degrees when printed, orcid, name_ok); group_authors (only when the byline has one: parts, markers, orcid,
        text); affiliations (marker, text, block, institution_word, page when later); title_rows and
        title_exclusions when mixed-size runs contain a badge or tiny production text;
        article_info and affiliation_sources when rows move to front matter; author_box_px,
        affiliation_box_px, orcid_icons; marker_glyphs (paired sign-font author/address labels:
        run, char_id, font, before, after); unmarked_affiliation_candidates (only when no author
        carries a marker); checks (title_found, title_lines, authors_found, names_ok,
        authors_with_orcid, markers_used, affiliations_found, markers_without_affiliation,
        affiliations_not_used, authors_without_marker, markers_consecutive, byline_name_groups, group_authors when
        present, status: verified | not verified | authors found, no affiliation markers: not
        linked); flags. Settings author_gap_em, author_stack_em, author_size_tol,
        superscript_raise_em. With no page records, write an empty flagged record and one
        stderr line, exit 0. byline_lines retains each selected source row and its run IDs even
        when parsing fails. Full statement in authors_and_affiliations().
"""
import json, sys, argparse, statistics, math, collections, os, subprocess, string

# ---------------------------------------------------------------------------------------------
# Self-contained bootstrap: standard library plus standalone/vendor only, vendored files patched
# in memory (the copies on disk stay byte-identical to the staged sources), Pillow replaced by a
# standard-library drawing shim. Nothing here touches the rules.
# ---------------------------------------------------------------------------------------------
import importlib.abc, importlib.util, types, zlib, struct, io, shutil, bisect, unicodedata

SC_HERE = os.path.dirname(os.path.abspath(__file__))
SC_VENDOR = os.path.join(SC_HERE, "vendor")
SC_VENDORED = ("pdfminer", "pdfplumber", "fontTools", "pyaes")
SC_PATCHES = {"pdfminer.utils": "pdfminer-utils.patch", "pdfminer.pdfdocument": "pdfminer-pdfdocument.patch"}
SC_PATCH_SHA256 = {"pdfminer-utils.patch": "de994cb2888c414e408a3b68e8a596b73be2ab5fa2948f40421db3e05ad89b2f",
                   "pdfminer-pdfdocument.patch": "b91de0d816e5373b3ba458413c85390e9af281bfb5a1b643051a950301e1dc71"}
SC_SUMS = {}


def sc_checked_bytes(path, expected=None):
    """A vendored file's bytes, refused unless its sha256 is the one vendor/SHA256SUMS (or, for a patch,
    SC_PATCH_SHA256) records for it: no changed vendored file is ever run."""
    import hashlib
    if not SC_SUMS:
        with open(os.path.join(SC_VENDOR, "SHA256SUMS"), encoding="utf-8") as f:
            for line in f:
                if line.strip(): h_, rel = line.split(None, 1); SC_SUMS[os.path.normpath(rel.strip())] = h_
    data = sc_read_bytes(path)
    want = expected or SC_SUMS.get(os.path.normpath(os.path.relpath(path, SC_VENDOR)))
    if want is None or hashlib.sha256(data).hexdigest() != want:
        raise ImportError(f"element_boxer_sc: {os.path.relpath(path, SC_VENDOR)} does not match its recorded sha256; refused")
    return data
sys.dont_write_bytecode = True   # nothing is written into vendor/


def sc_apply_patch(text, patch_text):
    """Apply a unified diff to a source text: every hunk's old block must occur exactly once."""
    hunks, cur = [], None
    for line in patch_text.splitlines(keepends=True):
        if line.startswith("@@"):
            cur = ([], []); hunks.append(cur); continue
        if cur is None or line.startswith("\\"): continue
        tag, body = line[:1], line[1:]
        if tag in (" ", "-"): cur[0].append(body)
        if tag in (" ", "+"): cur[1].append(body)
    for old, new in hunks:
        old, new = "".join(old), "".join(new)
        if text.count(old) != 1: raise ImportError("element_boxer_sc: a vendor patch does not apply")
        text = text.replace(old, new, 1)
    return text


def sc_read_bytes(path):
    with open(path, "rb") as f: return f.read()


class SCVendorLoader(importlib.abc.Loader):
    """Loads a vendored module from its source file, with its patch applied in memory."""
    def __init__(self, path, patch):
        self.path, self.patch = path, patch
    def create_module(self, spec): return None
    def exec_module(self, module):
        src = sc_checked_bytes(self.path).decode("utf-8")
        if self.patch: src = sc_apply_patch(src, sc_checked_bytes(os.path.join(SC_VENDOR, "patches", self.patch), SC_PATCH_SHA256[self.patch]).decode("utf-8"))
        exec(compile(src, self.path, "exec", dont_inherit=True), module.__dict__)


class SCImportGuard(importlib.abc.MetaPathFinder):
    """Vendored packages from standalone/vendor only; standard library as usual; anything else refused."""
    def find_spec(self, name, path=None, target=None):
        top = name.partition(".")[0]
        if top in SC_VENDORED:
            base = os.path.join(SC_VENDOR, *name.split("."))
            if os.path.isfile(os.path.join(base, "__init__.py")):
                f = os.path.join(base, "__init__.py")
                return importlib.util.spec_from_file_location(name, f, loader=SCVendorLoader(f, SC_PATCHES.get(name)), submodule_search_locations=[base])
            if os.path.isfile(base + ".py"):
                return importlib.util.spec_from_file_location(name, base + ".py", loader=SCVendorLoader(base + ".py", SC_PATCHES.get(name)))
            raise ModuleNotFoundError(f"element_boxer_sc: {name} is not in standalone/vendor", name=name)
        if top in sys.stdlib_module_names or top in sys.builtin_module_names: return None
        raise ModuleNotFoundError(f"element_boxer_sc: {name} is neither standard library nor vendored", name=name)


sys.meta_path.insert(0, SCImportGuard())
for _m in [m for m in sys.modules if m.partition(".")[0] in SC_VENDORED + ("PIL",)]: del sys.modules[_m]


# --- the drawing shim: the subset of Pillow's Image / ImageDraw / ImageFont the carried code calls ---
SC_FONT5X7 = {   # 5x7 bitmap letters, one row per 5-bit number, top row first; lower case drawn as upper case
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14), "2": (14, 17, 1, 2, 4, 8, 31), "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2), "5": (31, 16, 30, 1, 1, 17, 14), "6": (6, 8, 16, 30, 17, 17, 14), "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14), "9": (14, 17, 17, 15, 1, 2, 12), "A": (14, 17, 17, 31, 17, 17, 17), "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14), "D": (28, 18, 17, 17, 17, 18, 28), "E": (31, 16, 16, 30, 16, 16, 31), "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15), "H": (17, 17, 17, 31, 17, 17, 17), "I": (14, 4, 4, 4, 4, 4, 14), "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17), "L": (16, 16, 16, 16, 16, 16, 31), "M": (17, 27, 21, 21, 17, 17, 17), "N": (17, 17, 25, 21, 19, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14), "P": (30, 17, 17, 30, 16, 16, 16), "Q": (14, 17, 17, 17, 21, 18, 13), "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30), "T": (31, 4, 4, 4, 4, 4, 4), "U": (17, 17, 17, 17, 17, 17, 14), "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10), "X": (17, 17, 10, 4, 10, 17, 17), "Y": (17, 17, 10, 4, 4, 4, 4), "Z": (31, 1, 2, 4, 8, 16, 31),
    ":": (0, 12, 12, 0, 12, 12, 0), ".": (0, 0, 0, 0, 0, 12, 12), ",": (0, 0, 0, 0, 12, 4, 8), "-": (0, 0, 0, 31, 0, 0, 0),
    "(": (2, 4, 8, 8, 8, 4, 2), ")": (8, 4, 2, 2, 2, 4, 8), "/": (1, 1, 2, 4, 8, 16, 16), "=": (0, 0, 31, 0, 31, 0, 0),
    "+": (0, 4, 4, 31, 4, 4, 0), "#": (10, 10, 31, 10, 31, 10, 10), "'": (4, 4, 8, 0, 0, 0, 0), "[": (14, 8, 8, 8, 8, 8, 14),
    "]": (14, 2, 2, 2, 2, 2, 14), ";": (0, 12, 12, 0, 12, 4, 8), "%": (24, 25, 2, 4, 8, 19, 3), "*": (0, 4, 21, 14, 21, 4, 0),
    "?": (14, 17, 1, 2, 4, 0, 4), "!": (4, 4, 4, 4, 4, 0, 4), "_": (0, 0, 0, 0, 0, 0, 31), '"': (10, 10, 0, 0, 0, 0, 0),
}


class SCImage:
    """An RGB image held as three byte planes (row-major), so a rectangle is a few slice assignments."""
    def __init__(self, w, h, colour=(255, 255, 255)):
        if isinstance(colour, int): colour = (colour, colour, colour)
        self.width, self.height = int(w), int(h)
        self.planes = [bytearray([c & 255]) * (self.width * self.height) for c in colour[:3]]
    @property
    def size(self): return (self.width, self.height)
    def copy(self):
        im = SCImage(0, 0); im.width, im.height = self.width, self.height; im.planes = [bytearray(p) for p in self.planes]; return im
    def convert(self, mode="RGB"): return self.copy()
    def crop(self, box):
        x0, y0, x1, y1 = [int(v) for v in box]
        out = SCImage(max(0, x1 - x0), max(0, y1 - y0), (0, 0, 0)); out.paste(self, (-x0, -y0)); return out
    def paste(self, im, xy):
        dx, dy = int(xy[0]), int(xy[1])
        sx0, sx1 = max(0, -dx), min(im.width, self.width - dx)
        if sx1 <= sx0: return
        for sy in range(max(0, -dy), min(im.height, self.height - dy)):
            ty = sy + dy
            for p, q in zip(self.planes, im.planes):
                p[ty * self.width + sx0 + dx: ty * self.width + sx1 + dx] = q[sy * im.width + sx0: sy * im.width + sx1]
    def save(self, path):
        raw = bytearray(3 * self.width * self.height)
        for k, p in enumerate(self.planes): raw[k::3] = p
        stride = 3 * self.width
        rows = b"".join(b"\x00" + bytes(raw[i:i + stride]) for i in range(0, len(raw), stride))
        def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def sc_image_from_rgb(w, h, raw):
    im = SCImage(0, 0); im.width, im.height = w, h; im.planes = [bytearray(raw[k::3]) for k in range(3)]; return im


def sc_image_open(path):
    """Reads the PNGs this program writes (8-bit RGB) and binary PPM (pdftoppm's default output)."""
    data = sc_read_bytes(path)
    if data[:2] == b"P6":
        parts, pos = [], 2
        while len(parts) < 3:
            while data[pos:pos + 1].isspace(): pos += 1
            if data[pos:pos + 1] == b"#":
                pos = data.index(b"\n", pos); continue
            end = pos
            while not data[end:end + 1].isspace(): end += 1
            parts.append(int(data[pos:end])); pos = end
        w, h, _ = parts
        return sc_image_from_rgb(w, h, data[pos + 1: pos + 1 + 3 * w * h])
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]; t = data[pos + 4:pos + 8]; d = data[pos + 8:pos + 8 + n]; pos += 12 + n
        if t == b"IHDR": w, h, depth, ctype = struct.unpack(">IIBB", d[:10])
        elif t == b"IDAT": idat += d
    if (depth, ctype) != (8, 2): raise ValueError("element_boxer_sc: only 8-bit RGB PNG is read")
    raw, stride, out, prev = zlib.decompress(idat), 3 * w, bytearray(), bytearray(3 * w)
    for r in range(h):
        ft, row = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        for i in range(stride if ft else 0):   # PNG filters 1-4 (not written by this program)
            a = row[i - 3] if i >= 3 else 0; b = prev[i]; c = prev[i - 3] if i >= 3 else 0
            if ft == 1: row[i] = (row[i] + a) & 255
            elif ft == 2: row[i] = (row[i] + b) & 255
            elif ft == 3: row[i] = (row[i] + (a + b) // 2) & 255
            elif ft == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += row; prev = row
    return sc_image_from_rgb(w, h, out)


class SCDraw:
    """ImageDraw.Draw: rectangle, line and text, with alpha blending when the draw mode is RGBA."""
    def __init__(self, im, mode=None):
        self.im, self.blend = im, (mode == "RGBA")
    def _rect(self, x0, y0, x1, y1, colour):
        im = self.im
        x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(im.width - 1, int(x1)), min(im.height - 1, int(y1))
        if x1 < x0 or y1 < y0: return
        alpha = colour[3] if (self.blend and len(colour) > 3) else 255
        for p, c in zip(im.planes, colour[:3]):
            if alpha >= 255: seg = bytes([c]) * (x1 - x0 + 1)
            else: table = bytes((v * (255 - alpha) + c * alpha + 127) // 255 for v in range(256))
            for y in range(y0, y1 + 1):
                a = y * im.width + x0
                p[a:a + x1 - x0 + 1] = seg if alpha >= 255 else p[a:a + x1 - x0 + 1].translate(table)
    def rectangle(self, xy, fill=None, outline=None, width=1):
        if isinstance(xy[0], (tuple, list)): xy = [xy[0][0], xy[0][1], xy[1][0], xy[1][1]]
        x0, y0, x1, y1 = min(xy[0], xy[2]), min(xy[1], xy[3]), max(xy[0], xy[2]), max(xy[1], xy[3])
        if fill is not None: self._rect(x0, y0, x1, y1, fill)
        if outline is not None and width > 0:
            w = width - 1
            for r in ((x0, y0, x1, y0 + w), (x0, y1 - w, x1, y1), (x0, y0 + width, x0 + w, y1 - width), (x1 - w, y0 + width, x1, y1 - width)):
                self._rect(*r, outline)
    def line(self, xy, fill=None, width=1):
        pts = [tuple(p) for p in xy] if isinstance(xy[0], (tuple, list)) else [(xy[k], xy[k + 1]) for k in range(0, len(xy), 2)]
        h = max(0, (width - 1) / 2)
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(by - ay))) + 1
            if ax == bx or ay == by: self._rect(min(ax, bx) - h, min(ay, by) - h, max(ax, bx) + h, max(ay, by) + h, fill); continue
            for k in range(n + 1):
                x, y = ax + (bx - ax) * k / n, ay + (by - ay) * k / n; self._rect(x - h, y - h, x + h, y + h, fill)
    def text(self, xy, text, fill=None, font=None, **kw):
        x0, y0 = int(xy[0]), int(xy[1]) + 2
        for k, ch in enumerate(str(text)):
            rows = SC_FONT5X7.get(ch.upper(), None if ch == " " else (31, 17, 17, 17, 17, 17, 31))
            if rows is None: continue
            for r, bits in enumerate(rows):
                for c in range(5):
                    if bits & (16 >> c): self._rect(x0 + 6 * k + c, y0 + r, x0 + 6 * k + c, y0 + r, fill)


class SCPilFont: pass


sc_pil = types.ModuleType("PIL"); sc_pil.__path__ = []; sc_pil.__doc__ = "element_boxer_sc's standard-library drawing shim (not Pillow)"
sc_pil.Image = types.ModuleType("PIL.Image"); sc_pil.Image.new = lambda mode, size, color=0: SCImage(size[0], size[1], color); sc_pil.Image.open = sc_image_open; sc_pil.Image.Image = SCImage
sc_pil.ImageDraw = types.ModuleType("PIL.ImageDraw"); sc_pil.ImageDraw.Draw = SCDraw
sc_pil.ImageFont = types.ModuleType("PIL.ImageFont"); sc_pil.ImageFont.load_default = lambda *a, **k: SCPilFont()
sys.modules.update({"PIL": sc_pil, "PIL.Image": sc_pil.Image, "PIL.ImageDraw": sc_pil.ImageDraw, "PIL.ImageFont": sc_pil.ImageFont})


PARAMS = {
    "dpi": 150,                 # the mapper's page-pixel frame
    "line_tolerance_em": 0.5,
    "background_share": 0.9,          # rule 2: a fill or image covering this share of the page's content extent in both directions is a background, not a container
    "curve_box_share": 0.8,      # rule 1: a curve frames text only when this share of its path points lie on its bounding box (measured: rounded panels and boxes 1.0 on AN05 p1, AL03 p2; the AN08 p1 swoosh 0.45)
    "curve_min_em": 10,          # rule 1: ... or when its shorter side is under this many letter heights (a flow-diagram shape or chart element with its lettering: AN01 p5, 3-7 em; the AN08 p1 swoosh is 40 em)
    "background_text_share": 0.8,     # rule 1: a fill or image under this share of the page's upright text characters ... (measured: AH06, J Periodontol 2000, a tinted text area under every page)
    "background_area_share": 0.5,     # ... spanning this share of the page in both directions is the text area's background
    "background_repeat_px": 8,        # ... when the same box (within this on every edge) is drawn on most of the paper's pages
    "background_prose_chars": 25,     # ... and at least half the characters it holds are in runs of this many characters or more: prose lines, not figure lettering
    "assemble_overlap": 0.6,          # rule 4 table assembly: shared sideways span (of the narrower, or of the block's own width inside the table)
    "assemble_table_gap_em": 4,       # ... an uncaptioned table joins within this many body letter heights
    "assemble_stack_em": 1.5,         # ... a block of cells under or over the table joins within this
    "assemble_beside_em": 3,          # ... a block of cells beside the table joins within this
    "assemble_cell_share": 0.55,      # ... cells: lines whose median width is under this share of the column width   # baseline difference below this (times letter size) = same line
    "dropcap_ratio": 2.0,       # initial spanning more than one normal-sized row
    "run_gap_em": 1.0,          # gap wider than one letter height = new element
    "run_gap_wordspaces": 3.0,  # ... or wider than three of the line's own word spaces (measured 2026-10-16: word gaps <= 2.6x, cell gaps >= 3.7x)
    "wordspace_max_em": 0.75,   # a gap counts as a candidate word space only below this share of the letter height
    "wordspace_min_em": 0.2,    # ... and above this share (measured 2026-10-16: word spaces sit at 0.20-0.40; letter-spacing in "T A B L E" labels at 0.08-0.16)
    "rule_max_pt": 1.5,         # drawn object thinner than this = rule, else fill
    "full_width": 0.8,          # a rule spanning this share of the body width is full-width
    "superscript_em": 0.8,      # a letter smaller than this share of its line's size may be a super/subscript
    "superscript_shift_em": 0.6,# ... and may sit this far (in line sizes) off the line's baseline
    "overlap_share": 0.5,       # two letters overlapping by this share of the narrower = overprinted text
    "display_gap_em": 0.4,      # lane r3-pullquote: a face change across a gap wider than this share of the letter height may part a display-face piece from its line (word spaces 0.20-0.40; AO05 p1 quote-to-body gap 0.67)
    "frame_reach_em": 25,       # ... a rule pair framing the piece stands within this many letter heights above and below it (AO05 p1: a 14-line quote, rules 2.7 and 0.4 em from its outer lines)
    "pitch_drift_em": 0.15,     # ... stacked pieces whose baseline offset to their lines varies by more than this keep their own pitch (one pitch: a constant offset)
    "shared_baseline_em": 0.05, # ... a piece within this of its neighbours' baseline is an inline word of their line (not a piece at another pitch)
    "runaround_reach_em": 4,    # ... a pull quote's column has a line reaching over the frame's width within this many letter heights above or below it
    "pull_quote_max_words": 50, # ... a pull quote is one sentence of at most this many words (the lane's quotes: 6-29; AQ17: 18 and 22)
    "rule_join_pt": 1.5,        # rule 3: drawn rule pieces whose ends meet within this are one line (measured 2026-10-18 on batch 1: table rules drawn per cell edge meet at 0.0-1.0 px)
    "header_max_lines": 4,      # rule 3: header lines taken into the grid band above the data rows, at most this many
    "header_cell_share": 0.6,   # rule 3: a header line's every run is narrower than this share of the grid's width (a prose line spans it)
    "table_min_tracks": 3,      # rule 3: a grid of two tracks is a two-column layout, not a table (measured 2026-10-16: every development table has 3 or more)
    "stack_gap_em": 1.0,        # rule 2: white between stacked elements, in letter heights of the smaller one
    "furniture_min_pages": 3,   # rule 6: recurrence threshold at one position; two for papers under eight pages
    "furniture_pos_px": 20,     # rule 6: position bin for the recurrence test
    "band_tolerance_em": 0.5,   # rule 6: a line this close inside the header/footer band is in it
    "body_size_tolerance": 0.05,# rule 6: a size within this share of the body size is the body size
    "column_min_lines": 3,      # rule 6: a body-size block with this many lines sets a text column
    "flow_gap_em": 2.5,         # rule 6: a smaller-size block this close under main text continues it; measured: in-flow gaps reach 2.25 (slots references under their heading), 2.19 (medicina back matter)
    "same_line_em": 0.5,        # rule 7: blocks whose tops lie this close share one line and read left to right
    "chart_label_chars": 24,    # rule 4: a chart's label is one line of at most this many characters, no larger than the page's median text (tick values, group names, a legend, an axis title); measured: the JPIS 2012 charts' longest, "Surface energy (dyne/cm)", 22
    "column_indent_em": 2.0,    # rule 7: a paper column with both edges this close to a page column's is that column (an indented stretch); measured: indents 1.34 (T03 right column), 1.37 (P2 p10); a structured abstract's column 12.3 from the body's
    "note_gap_em": 1.5,         # rule 3: white under a table before its note ends; measured on the development papers: notes and continuation lines at most 1.12, nearest body text 1.95
    "side_overlap_px": 1.0,     # rule 2: sideways overlap required for stacking
    "strip_touch_px": 2.0,      # rule 4: strips of one picture touch; an image this close to a figure float is part of it
    "icon_max_em": 2.0,         # rule 5: an icon in a text line is at most this many line heights tall and wide (measured 2026-10-17: ORCID icons 1.5-1.8)
    "outline_max_em": 1.6,      # a fill no bigger than this many letter heights may be a glyph drawn as an outline
    "caption_gap_em": 2.5,      # rule 3 (from the caption): white under a row before the table ends, unless a drawn object bridges it
    "channel_em": 0.5,          # rule 3 (from the caption): a column channel is at least this wide, in letter heights
    "channel_ink_rows": 0.1,    # rule 3 (from the caption): ... and at most this share of the cell rows have ink in it (a header cell spanning two columns)
    "prose_share": 0.75,        # rule 3 (from the caption): a prose line has one run across this share of the width or more
    "furniture_min_share": 0.25,# rule 6: furniture recurs on this share of the paper's pages at least, besides furniture_min_pages (measured 2026-10-18: a label on 3 of 68 pages is not furniture)
    "band_edge_share": 0.15,    # rule 6: the header and footer bands come from furniture within this share of the page's top and bottom
    "author_gap_em": 3.0,       # rule 8: the first author line lies this close under the title, in its own letter heights (measured 2026-10-18: 1.0-2.5 on ten papers)
    "author_stack_em": 1.5,     # rule 8: later author lines are stacked this close (measured: 0.1-0.7)
    "author_size_tol": 0.05,    # rule 8: an author line keeps the first author line's size within this share
    "superscript_raise_em": 0.15,# rule 8: a superscript's foot stands this far above the line's baseline, in line sizes
    "advance_space_em": 0.1,    # rule 1: a gap between one letter's advance end and the next letter's origin wider than this share of the letter height is a word space, measured above the run's own tracking (the median of its advance gaps) (Poppler's minWordBreakSpace); measured: T02 p9 word space 0.147
    "text_space_em": 0.15,      # rule 1: a gap wider than this share of the letter height puts a space in a text run's text
    "zero_size_px": 1.0,        # rule 2: a drawn object with no height or no width counts as this size in the stacking test (a hairline rule)
    "heading_size_ratio": 1.15, # rule 3 (from the caption): a line with a run this many times the body size is a heading and ends the table
    "title_size_share": 0.98,   # rules 6 and 8: the title's lines are within this share of the largest size on the first page
    "orcid_letter_share": 0.9,  # rule 8: printed "iD" letters are smaller than this share of the author line's size ...
    "orcid_name_share": 0.95,   # rule 8: ... and follow a name letter at this share of it at least
}

def read_json(path):
    """A JSON record read with its file closed, as UTF-8."""
    with open(path, encoding="utf-8") as f: return json.load(f)
def write_text(path, text):
    """An output written whole or not at all: to a temporary file beside it, then renamed over it, so an
    interrupted run never leaves a truncated record. The temporary file is created owner-only, given the
    destination's own mode (or, for a new file, the mode the umask gives) just before the rename, and
    removed if the write fails."""
    tmp = path + ".tmp"
    if os.path.exists(path): mode = os.stat(path).st_mode & 0o777
    else:
        um = os.umask(0); os.umask(um); mode = 0o666 & ~um
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(text)
        os.chmod(tmp, mode); os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp): os.remove(tmp)
        raise
def write_json(path, obj, **kw):
    write_text(path, json.dumps(obj, **kw))
def page_files(paper_dir):
    """A paper's page records in page order, of any number of pages (page-01.json ... page-100.json)."""
    import glob
    fs = [f for f in glob.glob(os.path.join(paper_dir, "page-*.json")) if re.fullmatch(r"page-(\d{2,})\.json", os.path.basename(f))]
    return sorted(fs, key=lambda f: int(re.fullmatch(r"page-(\d+)\.json", os.path.basename(f)).group(1)))

def px(v): return v * PARAMS["dpi"] / 72.0

def caption_boxes(stage2_output, box_px):
    """The page mapper's own caption boxes for the region whose box equals box_px."""
    found = []
    def walk(o):
        if isinstance(o, dict):
            if o.get("box_px") == box_px and "caption_read_boxes_px" in o:
                found.extend(o["caption_read_boxes_px"] or [])
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(stage2_output)
    return found

def load_float(map_path, label, page):
    m = read_json(map_path)
    for f in m["stages"]["3-floats"]["output"]["floats"]:
        if f["label"]["label"] == label:
            for p in f["parts"]:
                if p["page"] == page:
                    p = dict(p); p["caption_boxes_px"] = caption_boxes(m["stages"]["2"]["output"], p["box_px"])
                    return f, p
    raise SystemExit(f"no float {label} on page {page}")

def frame(angle):
    return _frame(angle)

def _frame(angle):
    """page (x,y top-left px) -> reading (u along line, v across lines), and baseline v."""
    if angle == 0:
        return (lambda x0,y0,x1,y1: (x0, y0, x1, y1)), (lambda c: c["origin"][1])
    if angle == 90:   # text reads bottom-to-top; lines advance left-to-right; baseline on the right
        return (lambda x0,y0,x1,y1: (-y1, x0, -y0, x1)), (lambda c: c["origin"][0])
    return (lambda x0,y0,x1,y1: (y0, -x1, y1, -x0)), (lambda c: -c["origin"][0])  # 270

# ---------------------------------------------------------------------------------------------
# The reading layer: what PDFium gave the rules (characters with tight glyph boxes, origins,
# sizes, angles, fonts and the unpainted verdict; shading bounds; page facts), produced from
# pdfminer's content-stream interpreter (vendored) and the embedded font programs read with
# fontTools (vendored). Written for exactly what pdfium_characters and pdfium_shadings returned.
# Coordinates follow PDFium: PDF user space of the page (no MediaBox offset, no /Rotate applied to
# objects), y flipped against the page height for the pixel frame.
# ---------------------------------------------------------------------------------------------
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager, LITERAL_FORM
from pdfminer.pdfdevice import PDFDevice
from pdfminer.pdftypes import resolve1, stream_value, dict_value, list_value, int_value, PDFStream, PDFObjRef
from pdfminer.psparser import literal_name, PSLiteral
from pdfminer.utils import mult_matrix, apply_matrix_pt, MATRIX_IDENTITY
from pdfminer.encodingdb import name2unicode as sc_name2unicode
from pdfminer.latin_enc import ENCODING as SC_LATIN_ENC
from pdfminer.fontmetrics import FONT_METRICS as SC_FONT_METRICS

READ_PARAMS = {
    "zero_width_text_pt": 0.01,     # PDFium kSizeEpsilon: a text object or glyph box narrower than this is empty
    "dup_letter_em": 0.07,          # PDFium kTextCharRatioGapDelta: a repeated letter within this share of the font size is one letter
    "dup_letter_window": 7,         # PDFium: the repeated-letter test looks back over this many letters
    "dup_object_window": 5,         # PDFium: the repeated-object test looks back over this many text objects
    "standard14_box": "advance",    # a font with no program (standard 14): the letter's box is its AFM advance across and the face's
                                    # descent to ascent up ("fontbbox": the FontBBox for every letter); PDFium uses its own substitute
                                    # font's outlines, which are not in the file (montero margin notice: see REPORT.md)
}

SC_ENCODINGS = {}
for _name, _std, _mac, _win, _pdf in SC_LATIN_ENC:
    for _enc, _code in (("StandardEncoding", _std), ("MacRomanEncoding", _mac), ("WinAnsiEncoding", _win), ("PDFDocEncoding", _pdf)):
        if _code is not None: SC_ENCODINGS.setdefault(_enc, {})[_code] = _name
SC_ENCODINGS["MacExpertEncoding"] = SC_ENCODINGS["WinAnsiEncoding"]   # PDFium reads MacExpert as WinAnsi
# Adobe Symbol's standard character names. This is a text fallback only: the outline/width
# mapper above retains its own encoding, and a PDF Differences entry always takes precedence.
SC_SYMBOL_NAMES = {}
for _start, _names in (
    (32, "space exclam universal numbersign existential percent ampersand suchthat parenleft parenright asteriskmath plus comma minus period slash"),
    (48, "zero one two three four five six seven eight nine colon semicolon less equal greater question"),
    (64, "congruent Alpha Beta Chi Delta Epsilon Phi Gamma Eta Iota theta1 Kappa Lambda Mu Nu Omicron Pi Theta Rho Sigma Tau Upsilon sigma1 Omega Xi Psi Zeta bracketleft therefore bracketright perpendicular underscore"),
    (96, "radicalex alpha beta chi delta epsilon phi gamma eta iota phi1 kappa lambda mu nu omicron pi theta rho sigma tau upsilon omega1 omega xi psi zeta braceleft bar braceright similar"),
    (160, "Euro Upsilon1 minute lessequal fraction infinity florin club diamond heart spade arrowboth arrowleft arrowup arrowright arrowdown degree plusminus second greaterequal multiply proportional partialdiff bullet divide notequal equivalence approxequal ellipsis arrowvertex arrowhorizex carriagereturn"),
    (192, "aleph Ifraktur Rfraktur weierstrass circlemultiply circleplus emptyset intersection union propersuperset reflexsuperset notsubset propersubset reflexsubset element notelement angle gradient registerserif copyrightserif trademarkserif product radical dotmath logicalnot logicaland logicalor arrowdblboth arrowdblleft arrowdblup arrowdblright arrowdbldown"),
    (224, "lozenge angleleft registersans copyrightsans trademarksans summation parenlefttp parenleftex parenleftbt bracketlefttp bracketleftex bracketleftbt bracelefttp braceleftmid braceleftbt braceex"),
    (241, "angleright integral integraltp integralex integralbt parenrighttp parenrightex parenrightbt bracketrighttp bracketrightex bracketrightbt bracerighttp bracerightmid bracerightbt"),
):
    SC_SYMBOL_NAMES.update(enumerate(_names.split(), _start))
# The ZapfDingbats encoding, codes to Unicode, as Unicode publishes it (MAPPINGS/VENDORS/ADOBE/zdingbat.txt); its
# glyph names (a1 ... a191) are not in the Adobe Glyph List, so the code is the published witness.
SC_ZAPF_UNICODE = {}
for _start, _row in (
    (0x20, " ✁✂✃✄☎✆✇✈✉☛☞✌✍✎✏✐✑✒✓✔✕✖✗✘✙✚✛✜✝✞✟"), (0x40, "✠✡✢✣✤✥✦✧★✩✪✫✬✭✮✯✰✱✲✳✴✵✶✷✸✹✺✻✼✽✾✿"),
    (0x60, "❀❁❂❃❄❅❆❇❈❉❊❋●❍■❏❐❑❒▲▼◆❖◗❘❙❚❛❜❝❞"), (0xa1, "❡❢❣❤❥❦❧♣♦♥♠①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿"),
    (0xc0, "➀➁➂➃➄➅➆➇➈➉➊➋➌➍➎➏➐➑➒➓➔→↔↕➘➙➚➛➜➝➞➟"), (0xe0, "➠➡➢➣➤➥➦➧➨➩➪➫➬➭➮➯"), (0xf1, "➱➲➳➴➵➶➷➸➹➺➻➼➽➾"),
):
    SC_ZAPF_UNICODE.update(enumerate(_row, _start))
# Rule O23 (lane r5-signs): the two standard sign faces have fixed published tables. A face of that name drawn from
# the reader's own font (no embedded program) whose PDF encoding names no base encoding is read through its own
# table, as PDFium reads base-14 Symbol and ZapfDingbats: never through StandardEncoding's Latin letters.
SC_SIGN_FACES = ("Symbol", "ZapfDingbats")
SC_STATS = collections.Counter()   # reading-layer counts for the report (fallbacks, limits met)

# Only semantic names of the selected glyph can contradict a usable text layer.
# Do not decode uniXXXX, strip suffixes or infer a symbol from a pi font's name:
# some embedded pi fonts call their micro glyph /m.
SC_GLYPH_SYMBOLS = {
    "mu": "µ", "micro": "µ", "lessequal": "≤", "greaterequal": "≥",
    "degree": "°", "asteriskmath": "*", "asterisk": "*", "registered": "®",
    "plusminus": "±", "minus": "−", "multiply": "×", "bullet": "•",
    "notequal": "≠", "approxequal": "≈", "Delta": "Δ", "beta": "β", "alpha": "α",
}


def sc_uni(name):
    """Adobe Glyph List, including its uniXXXX/uXXXXX and suffix rules; opaque names stay unknown."""
    try: return sc_name2unicode(name)
    except Exception: return ""


def sc_tt2pdf(m, upm):
    """PDFium's TT2PDF: font units to 1/1000 em, (m * 1000 + upm / 2) / upm truncated toward zero."""
    if not upm: return int(m)
    return int((m * 1000.0 + upm // 2) / upm)


def sc_hull(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def sc_transform_rect(m, r):
    """CFX_Matrix::TransformRect: the hull of the four transformed corners."""
    return sc_hull([apply_matrix_pt(m, (x, y)) for x in (r[0], r[2]) for y in (r[1], r[3])])


def sc_invert(m):
    a, b, c, d, e, f = m; det = a * d - b * c
    if not det: return MATRIX_IDENTITY
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


class SCFontProgram:
    """The embedded font program, read with fontTools: glyph lookup by id or name, and each glyph's
    control box in font units (the hull of every outline point, off-curve points included, which is
    what FreeType's unscaled glyph metrics report and PDFium turns into its tight box)."""
    def __init__(self, kind, data):
        import fontTools.ttLib, fontTools.cffLib, fontTools.t1Lib
        from fontTools.pens.boundsPen import ControlBoundsPen
        self.kind, self.cache, self.Pen = kind, {}, ControlBoundsPen
        self.cmaps, self.names, self.order, self.builtin = {}, {}, [], {}
        if kind == "truetype":
            self.tt = fontTools.ttLib.TTFont(io.BytesIO(data), lazy=True, recalcBBoxes=False, recalcTimestamp=False, checkChecksums=0)
            self.upm = self.tt["head"].unitsPerEm
            self.order = self.tt.getGlyphOrder()
            if "cmap" in self.tt:
                for t in self.tt["cmap"].tables:
                    try: self.cmaps.setdefault((t.platformID, t.platEncID), {k: self.tt.getGlyphID(v) for k, v in t.cmap.items()})
                    except Exception: sc_swallowed()
            self.has_names = "post" in self.tt and self.tt["post"].formatType in (1.0, 2.0)
            if self.has_names: self.names = {n: i for i, n in enumerate(self.order)}
        elif kind in ("cff", "cidcff"):
            cs = fontTools.cffLib.CFFFontSet(); cs.decompile(io.BytesIO(data), otFont=None)
            self.top = cs[cs.fontNames[0]]; self.glyphs = self.top.CharStrings
            self.order = list(self.top.charset); self.names = {n: i for i, n in enumerate(self.order)}
            fm = getattr(self.top, "FontMatrix", [0.001, 0, 0, 0.001, 0, 0])
            self.upm = int(round(1.0 / abs(fm[3]))) if fm[3] else 1000
            enc = getattr(self.top, "Encoding", "StandardEncoding")
            names = SC_ENCODINGS["StandardEncoding"] if enc == "StandardEncoding" else ({} if isinstance(enc, str) else {i: n for i, n in enumerate(enc) if n != ".notdef"})
            self.builtin = {k: v for k, v in names.items() if v in self.names}
        elif kind == "type1":
            chunks = fontTools.t1Lib.findEncryptedChunks(data if b"cleartomark" in data[-600:] else data + b"\n" + b"0" * 512 + b"\ncleartomark\n")
            f = fontTools.t1Lib.T1Font.__new__(fontTools.t1Lib.T1Font); f.encoding = "ascii"
            f.data = b"".join(fontTools.t1Lib.deHexString(c) if e and fontTools.t1Lib.isHex(c[:4]) else c for e, c in chunks)
            # fontTools' T1Font.parse requires Private/Subrs, which a Type 1 font may omit: parse here with an
            # empty array in that case (the same steps as T1Font.parse otherwise)
            from fontTools.misc import psLib, psCharStrings, eexec
            f.font = psLib.suckfont(f.data, f.encoding)
            priv = f.font["Private"]; lenIV = priv.get("lenIV", 4); subrs = priv.setdefault("Subrs", [])
            if lenIV < 0: raise ValueError("lenIV < 0")   # as fontTools' parse asserts: the font falls back
            for gname, cstr in f.font["CharStrings"].items():
                cstr, _ = eexec.decrypt(cstr, 4330); f.font["CharStrings"][gname] = psCharStrings.T1CharString(cstr[lenIV:], subrs=subrs)
            for i in range(len(subrs)):
                cstr, _ = eexec.decrypt(subrs[i], 4330); subrs[i] = psCharStrings.T1CharString(cstr[lenIV:], subrs=subrs)
            self.glyphs = f["CharStrings"]; self.order = sorted(self.glyphs.keys(), key=lambda n: (n != ".notdef", n)); self.names = {n: i for i, n in enumerate(self.order)}
            fm = f.font.get("FontMatrix", [0.001, 0, 0, 0.001, 0, 0])
            self.upm = int(round(1.0 / abs(fm[3]))) if fm[3] else 1000
            enc = f.font.get("Encoding", "StandardEncoding")
            names = SC_ENCODINGS["StandardEncoding"] if isinstance(enc, str) else {i: n for i, n in enumerate(enc) if n and n != ".notdef"}
            self.builtin = {k: v for k, v in names.items() if v in self.names}
        self.unicode_glyph = {}   # FreeType's synthesised Unicode charmap of a Type 1 / CFF font, from its glyph names
        if kind != "truetype":
            for n, i in self.names.items():
                u = sc_uni(n)
                if len(u) == 1: self.unicode_glyph.setdefault(ord(u), i)

    def hmetric(self, gid):
        """(advance, left side bearing) from the raw hmtx table, as FreeType reads it: a glyph past the
        long metrics takes the last advance, and a side bearing missing from a short table is 0
        (fontTools refuses a truncated hmtx, which PDF subsets carry)."""
        if not hasattr(self, "_hm"):
            try:
                n = struct.unpack(">H", self.tt.reader["hhea"][34:36])[0]; self._hm = (n, self.tt.reader["hmtx"])
            except Exception:
                self._hm = (0, b"")
        n, raw = self._hm
        if n == 0: return (0, 0)
        if gid < n and 4 * gid + 4 <= len(raw): return struct.unpack(">Hh", raw[4 * gid:4 * gid + 4])
        k = min(gid, n) - 1
        adv = struct.unpack(">H", raw[4 * k:4 * k + 2])[0] if 4 * k + 2 <= len(raw) else 0
        off = 4 * n + 2 * (gid - n)
        if gid >= n and off + 2 <= len(raw): return (adv, struct.unpack(">h", raw[off:off + 2])[0])
        SC_STATS["hmtx_short_side_bearing_0"] += 1
        return (adv, 0)

    def cbox(self, gid):
        """(xMin, yMin, xMax, yMax) in font units, or None when the glyph cannot be loaded."""
        if gid in self.cache: return self.cache[gid]
        box = None
        try:
            if self.kind == "truetype":
                if 0 <= gid < len(self.order):
                    name = self.order[gid]; glyf = self.tt["glyf"]; g = glyf[name]
                    if g.numberOfContours == 0: box = (0, 0, 0, 0)
                    else:
                        coords = g.getCoordinates(glyf)[0]
                        if len(coords) == 0: box = (0, 0, 0, 0)
                        else:
                            xs = [p[0] for p in coords]; ys = [p[1] for p in coords]
                            lsb = self.hmetric(gid)[1]
                            shift = getattr(g, "xMin", min(xs)) - lsb   # FreeType moves the outline so its xMin is the hmtx side bearing
                            box = (min(xs) - shift, min(ys), max(xs) - shift, max(ys))
            else:
                if 0 <= gid < len(self.order):
                    pen = self.Pen(self.glyphs, ignoreSinglePoints=True)
                    self.glyphs[self.order[gid]].draw(pen)
                    b = pen.bounds or (0, 0, 0, 0)
                    box = tuple(math.floor(v) for v in b)   # FreeType keeps whole font units
        except Exception:
            SC_STATS["glyph_load_errors"] += 1; box = None
        self.cache[gid] = box
        return box


class SCFont:
    """One font dictionary: its codes, widths, Unicode text and glyph boxes, as PDFium reads them."""
    def __init__(self, spec, pdffont, doc):
        self.spec, self.pf = spec, pdffont
        self.sign_face_table = None
        self.subtype = literal_name(resolve1(spec.get("Subtype"))) if spec.get("Subtype") else ""
        self.basefont = literal_name(resolve1(spec.get("BaseFont"))) if spec.get("BaseFont") is not None else ""
        if not isinstance(self.basefont, str): self.basefont = str(self.basefont)
        self.cid = self.subtype == "Type0"
        self.dfont = dict_value(list_value(resolve1(spec.get("DescendantFonts", [])))[0]) if self.cid else None
        desc = resolve1((self.dfont or spec).get("FontDescriptor"))
        self.desc = dict_value(desc) if desc else {}
        self.flags = int(resolve1(self.desc.get("Flags", 0)) or 0)
        self.bboxes, self.widths = {}, {}
        self.tounicode = spec.get("ToUnicode") is not None and isinstance(resolve1(spec.get("ToUnicode")), PDFStream)
        self.prog, self.prog_kind = None, None
        for key, kind in (("FontFile2", "truetype"), ("FontFile", "type1"), ("FontFile3", None)):
            s = resolve1(self.desc.get(key))
            if not isinstance(s, PDFStream): continue
            if kind is None:
                st = literal_name(s.get("Subtype")) if s.get("Subtype") else ""
                kind = {"Type1C": "cff", "CIDFontType0C": "cidcff", "OpenType": "opentype"}.get(st)
            try:
                data = s.get_data()
                if kind == "opentype":
                    import fontTools.ttLib
                    tt = fontTools.ttLib.TTFont(io.BytesIO(data), lazy=True)
                    kind = "truetype" if "glyf" in tt else "cff"
                    if kind == "cff": data = tt.reader["CFF "]
                self.prog, self.prog_kind = SCFontProgram(kind, data), kind
            except Exception:
                SC_STATS["font_program_unreadable"] += 1
            break
        if self.prog is None: SC_STATS["fonts_without_program"] += 1
        # widths, as PDFium stores them: whole numbers (GetIntegerAt truncates)
        if self.cid:
            self.dw = int(resolve1(self.dfont.get("DW", 1000)))
            self.wmap, self.wranges = {}, []
            w = list_value(resolve1(self.dfont.get("W", [])))
            i = 0
            while i + 1 < len(w):
                first = int(resolve1(w[i])); nxt = resolve1(w[i + 1])
                if isinstance(nxt, list):
                    for k, v in enumerate(nxt): self.wmap.setdefault(first + k, int(resolve1(v)))
                    i += 2
                else:
                    if i + 2 < len(w): self.wranges.append((first, int(nxt), int(resolve1(w[i + 2]))))
                    i += 3
            m = resolve1(self.dfont.get("CIDToGIDMap"))
            self.cid2gid = m.get_data() if isinstance(m, PDFStream) else None
        else:
            self.cw = {}
            wa = resolve1(spec.get("Widths"))
            self.use_font_width = wa is None
            if wa is not None:
                if "MissingWidth" in self.desc: self.cw = {c: int(resolve1(self.desc["MissingWidth"])) for c in range(256)}
                first = int(resolve1(spec.get("FirstChar", 0)) or 0); wa = list_value(wa)
                for k, v in enumerate(wa):
                    if 0 <= first + k <= 255: self.cw[first + k] = int(resolve1(v))
            self._encoding()
            if wa is None and self.prog is None:   # a standard-14 font without Widths: its AFM widths, by the encoding's letter
                fm = SC_FONT_METRICS.get(self.basefont.split("+")[-1])
                if fm: self.cw = {c: int(fm[1][u]) for c, u in self.euni.items() if u in fm[1]}
                if fm and self.sign_face_table == "ZapfDingbats":   # the library keys this face's widths by code
                    self.cw = {c: int(fm[1][chr(c)]) for c in range(256) if chr(c) in fm[1]}
                SC_STATS["standard14_widths:" + self.basefont] += 1
        self.uni_cache = {}

    # --- simple fonts: the encoding as PDFium's LoadPDFEncoding builds it ---
    def _encoding(self):
        embedded = self.prog is not None; truetype = self.subtype == "TrueType" or self.prog_kind == "truetype"
        symbolic = bool(self.flags & 4)
        base = "builtin"
        if self.subtype == "Type1" and not truetype and not symbolic: base = "StandardEncoding"
        if self.subtype in ("Type1", "MMType1") and not symbolic: base = "StandardEncoding"
        self.diff = {}
        enc = resolve1(self.spec.get("Encoding"))
        face = re.sub(r"^[A-Z]{6}\+", "", self.basefont)
        # O23: a standard sign face without its own program and without a named base encoding reads its own table
        self.sign_face_table = face if (face in SC_SIGN_FACES and not embedded and self.subtype in ("Type1", "MMType1") and
                                        (enc is None or isinstance(enc, dict) and enc.get("BaseEncoding") is None)) else None
        if enc is None:
            if self.basefont == "Symbol": base = "Symbol"
            elif not embedded and base == "builtin": base = "WinAnsiEncoding"
        elif isinstance(enc, PSLiteral):
            n = literal_name(enc); base = SC_ENCODINGS.get(n) and n or base
        elif isinstance(enc, dict):
            be = enc.get("BaseEncoding")
            if be is not None:
                n = literal_name(resolve1(be))
                if truetype and n == "MacExpertEncoding": n = "WinAnsiEncoding"
                if n in SC_ENCODINGS: base = n
            if (not embedded or truetype) and base == "builtin": base = "StandardEncoding"
            code = 0
            for v in list_value(resolve1(enc.get("Differences", []))):
                v = resolve1(v)
                if isinstance(v, int): code = v
                elif isinstance(v, PSLiteral):
                    if 0 <= code <= 255: self.diff[code] = literal_name(v)
                    code += 1
        if self.sign_face_table: base = self.sign_face_table
        self.base = base
        self.gmap, self.euni = {}, {}   # code -> glyph id; code -> Unicode from the encoding (PDFium's m_Encoding)
        for code in range(256):
            n = self.adobe_name(code)
            if n: self.euni[code] = sc_uni(n)[:1]
            if self.sign_face_table and code not in self.euni:   # O23: the face's published table
                u = (sc_uni(SC_SYMBOL_NAMES[code]) if code in SC_SYMBOL_NAMES and code not in self.diff else "")[:1] \
                    if self.sign_face_table == "Symbol" else (SC_ZAPF_UNICODE.get(code, "") if code not in self.diff else "")
                if u: self.euni[code] = u
        if self.prog is not None: (self._tt_map if self.prog_kind == "truetype" else self._t1_map)()

    def adobe_name(self, code):
        if code in self.diff: return self.diff[code]
        return SC_ENCODINGS.get(self.base, {}).get(code)

    def _tt_map(self):
        p = self.prog; c31, c30, c10 = p.cmaps.get((3, 1)), p.cmaps.get((3, 0)), p.cmaps.get((1, 0))
        if c31 is None: c31 = p.cmaps.get((0, 3)) or p.cmaps.get((0, 4))
        def sym(code):
            for pre in (0x00, 0xF0, 0xF1, 0xF2):
                g = c30.get(pre * 256 + code, 0)
                if g: return g
            return 0
        if not p.cmaps and not p.has_names:   # SetGlyphIndicesFromFirstChar
            first = int(resolve1(self.spec.get("FirstChar", 0)) or 0)
            self.gmap = {c: (c - first + 3 if c >= first else 0) for c in range(256)}; return
        if (self.base in ("WinAnsiEncoding", "MacRomanEncoding") and not self.diff) or (self.flags & 32):
            ctype = "unicode" if c31 is not None else "symbol" if c30 is not None else "mac" if c10 is not None else None
            current = c31 if c31 is not None else (c10 if ctype == "mac" else {})
            for code in range(256):
                name = self.adobe_name(code)
                if not name: self.gmap[code] = current.get(code, 0); continue
                u = sc_uni(name); self.euni[code] = u[:1]
                g = 0
                if ctype == "symbol": g = sym(code)
                elif u:
                    if ctype == "unicode": g = c31.get(ord(u[0]), 0)
                    elif ctype == "mac":
                        try: mac = u[0].encode("mac_roman")[0]
                        except Exception: mac = 0
                        g = c10.get(mac, 0) if mac else p.names.get(name, 0)
                if not g:
                    if name == ".notdef": g = current.get(32, 0)
                    else:
                        g = p.names.get(name, 0)
                        if not g and self.tounicode:
                            t = self._tounicode(code)
                            if t: g = current.get(ord(t[0]), 0); self.euni[code] = t[0]
                self.gmap[code] = g
            return
        if c30 is not None:
            m = {c: sym(c) for c in range(256)}
            if any(m.values()):
                self.gmap = m
                if self.base != "builtin":
                    for c in range(256):
                        n = self.adobe_name(c)
                        if n: self.euni[c] = sc_uni(n)[:1]
                return
        if c10 is not None:
            self.gmap = {c: c10.get(c, 0) for c in range(256)}
            for c in range(256):
                try: self.euni[c] = bytes([c]).decode("mac_roman")
                except Exception: sc_swallowed()
            return
        if c31 is not None:
            for c in range(256):
                n = None if self.prog else self.adobe_name(c)
                u = chr(c) if self.prog else (sc_uni(n)[:1] if n else "")
                self.euni[c] = u; self.gmap[c] = c31.get(ord(u), 0) if u else 0
            if any(self.gmap.values()): return
        self.gmap = {c: c for c in range(256)}

    def _t1_map(self):
        p = self.prog
        if self.flags & 4:   # symbolic: names from the PDF encoding, else the font's built-in encoding
            for code in range(256):
                name = self.adobe_name(code)
                if name:
                    self.euni[code] = sc_uni(name)[:1]; self.gmap[code] = p.names.get(name, 0)
                else:
                    bn = p.builtin.get(code)
                    self.gmap[code] = p.names.get(bn, 0) if bn else 0
                    if bn:
                        std = SC_ENCODINGS["StandardEncoding"].get(code)
                        self.euni[code] = (sc_uni(std) if std else "")[:1] or sc_uni(bn)[:1]
            return
        if self.base == "builtin": self.base = "StandardEncoding"
        for code in range(256):
            name = self.adobe_name(code)
            if not name: continue
            u = sc_uni(name); self.euni[code] = u[:1]
            g = p.names.get(name, 0)
            if not g:
                g = (p.unicode_glyph.get(ord(u[0]), 0) if u else 0) if name not in (".notdef", "space") else None
            self.gmap[code] = g

    # --- per character ---
    def decode(self, s):
        return list(self.pf.decode(s))

    def width(self, code):
        """PDFium GetCharWidthF, in 1/1000 em."""
        if self.cid:
            if code in self.wmap: return self.wmap[code]
            for a, b, w in self.wranges:
                if a <= code <= b: return w
            return self.dw
        code = code if code <= 255 else 0
        if code in self.cw: return self.cw[code]
        if self.use_font_width and self.prog is not None and self.prog_kind == "truetype":
            g = self.gmap.get(code)
            try: return sc_tt2pdf(self.prog.hmetric(g)[0], self.prog.upm)
            except Exception: return 0
        return 0

    def single_byte_space(self, code):
        return code == 32 and not self.cid

    def _tounicode(self, code):
        if not hasattr(self, "_tu"): self._tu = sc_parse_tounicode(resolve1(self.spec.get("ToUnicode")))
        return self._tu.get(code, "")

    def unicode(self, code):
        """PDFium UnicodeFromCharCode: the ToUnicode map, else the encoding's glyph name; '' when neither."""
        if code in self.uni_cache: return self.uni_cache[code]
        u = self._tounicode(code) if self.tounicode else ""
        if not u and not self.cid: u = self.euni.get(code & 255, "") if code <= 255 else ""
        self.uni_cache[code] = u
        return u

    def recover_unicode(self, code):
        """Recover missing text from named glyphs, then a known font encoding, never a code's
        numeric resemblance to Unicode. Explicit Differences cannot fall through to an unrelated
        built-in glyph. Symbol means the standard face (optionally subset), not any pi/math font.
        This does not change glyph selection, advances or boxes, or override usable ToUnicode.
        A custom name such as C0 or H9262 carries no Unicode meaning by itself."""
        if self.cid or not isinstance(code, int) or not 0 <= code <= 255: return "", ""
        def named(name):
            u = sc_uni(name) if name else ""
            return u if u and all(ord(c) >= 32 and c != "\ufffd" for c in u) else ""
        name = self.adobe_name(code)
        u = named(name)
        if u: return u, "glyph_name"
        p = self.prog
        gid = self.gmap.get(code)
        if p is not None and (self.prog_kind != "truetype" or p.has_names):
            actual = p.order[gid] if gid is not None and 0 < gid < len(p.order) else None
            u = named(actual)
            if u: return u, "glyph_name"
        if code in self.diff: return "", ""
        face = re.sub(r"^[A-Z]{6}\+", "", self.basefont)
        if self.base == "Symbol" or (self.base == "builtin" and face == "Symbol"):
            u = named(SC_SYMBOL_NAMES.get(code))
            if u: return u, "symbol_encoding"
        # PDF's WinAnsiEncoding assigns /bullet to these otherwise unassigned positions;
        # the vendored Latin encoding table omits them. This is not Windows CP1252 decoding.
        if self.base == "WinAnsiEncoding" and code in (127, 129, 141, 143, 144, 157):
            return sc_uni("bullet"), "standard_encoding"
        if p is not None and self.base == "builtin":
            u = named(p.builtin.get(code))
            if u: return u, "builtin_encoding"
        return "", ""

    def selected_glyph_name(self, code):
        """Name of the selected outline, independently of ToUnicode.

        Embedded programs are authoritative, including opaque or misleading names:
        never fall through from an embedded /C0 or /m to another encoding's symbol.
        TrueType names synthesized from cmap are not original glyph-name evidence.
        Without a program, only a known standard face supplies an encoding witness.
        """
        if not isinstance(code, int) or code < 0: return None
        p = self.prog
        if p is not None:
            if self.prog_kind == "truetype" and not p.has_names: return None
            if self.cid:
                if self.prog_kind == "truetype":
                    gid = code
                    if self.cid2gid is not None:
                        gid = int.from_bytes(self.cid2gid[2*code:2*code+2], "big") if 2*code+1 < len(self.cid2gid) else 0
                else:
                    gid = code if self.prog_kind == "cidcff" and getattr(p.top, "ROS", None) is None else p.names.get("cid%05d" % code, code if self.prog_kind != "cidcff" else 0)
            else:
                gid = self.gmap.get(code) if code <= 255 else None
            return p.order[gid] if gid is not None and 0 < gid < len(p.order) else None
        if self.cid or code > 255: return None
        face = re.sub(r"^[A-Z]{6}\+", "", self.basefont)
        if face not in SC_FONT_METRICS or self.subtype not in ("Type1", "MMType1"): return None
        if code in self.diff: return self.diff[code]
        if face == "Symbol" and self.base in ("Symbol", "builtin"):
            return SC_SYMBOL_NAMES.get(code)
        return self.adobe_name(code)

    def glyph_correction(self, code, text):
        """A fixed symbol name beats a single Latin letter/digit, never a symbol.

        Asterisk names override letters only. Multi-character mappings, generic
        names and absent outline names are not evidence for a substitution.
        ActualText is excluded by the caller before this helper is consulted.
        """
        import unicodedata
        if len(text) != 1: return None
        letter = text.isalpha() and "LATIN" in unicodedata.name(text, "")
        if not letter and not text.isdecimal(): return None
        name = self.selected_glyph_name(code)
        symbol = SC_GLYPH_SYMBOLS.get(name)
        if not symbol or symbol == text or (symbol == "*" and not letter): return None
        return {"from": text, "to": symbol, "font": self.basefont, "glyph_name": name,
                "source_code": code}

    def char_code_for(self, ch):
        """PDFium CharCodeFromUnicode, enough for the ActualText test: some code whose text is ch."""
        if not hasattr(self, "_rev"):
            self._rev = {}
            if self.tounicode:
                self._tounicode(0)
                for c, u in self._tu.items():
                    if u: self._rev.setdefault(u[0], c)
            for c, u in (getattr(self, "euni", {}) or {}).items():   # then the encoding (CPDF_SimpleFont::CharCodeFromUnicode)
                if u: self._rev.setdefault(u[0], c)
        if self.cid: return self._rev.get(ch, 0)   # CPDF_CIDFont::CharCodeFromUnicode never answers "invalid" (0 or the letter itself)
        return self._rev.get(ch)

    def inked(self, code):
        """The embedded outline selected for code draws ink: a box of positive width and height
        (an empty space glyph has none; without an embedded program nothing is known)."""
        if self.prog is None: return False
        try: left, top, right, bottom = self.bbox(code)
        except Exception:
            sc_swallowed(); return False
        return right > left and top > bottom and (left, top, right, bottom) != (-1, -1, -1, -1)

    def bbox(self, code):
        """PDFium GetCharBBox: (left, top, right, bottom) in 1/1000 em, whole numbers."""
        if code in self.bboxes: return self.bboxes[code]
        if self.prog is None:
            fm = SC_FONT_METRICS.get(self.basefont.split("+")[-1])
            if fm and READ_PARAMS["standard14_box"] == "advance":   # the letter's advance across, the face's descent to ascent up
                r = (0, int(fm[0].get("Ascent", 0)), self.width(code), int(fm[0].get("Descent", 0)))
                SC_STATS["fallback_advance_box:" + self.basefont] += 1
            else:
                fb = resolve1(self.desc.get("FontBBox")) if self.desc else None
                if fb is None: fb = fm[0].get("FontBBox") if fm else None
                fb = [int(resolve1(v)) for v in list_value(fb)] if fb is not None else [0, 0, 0, 0]
                SC_STATS["fallback_fontbbox:" + self.basefont] += 1
                r = (fb[0], fb[3], fb[2], fb[1])
                # FontBBox encloses the entire face, not this character. Without
                # an embedded outline, only the PDF advance witnesses its width.
                # Treating that face hull as ink falsely covers adjacent fonts.
                if self.width(code) > 0:
                    r = (0, fb[3], self.width(code), fb[1])
        elif self.cid:
            if self.prog_kind == "truetype":
                gid = code
                if self.cid2gid is not None: gid = int.from_bytes(self.cid2gid[2 * code:2 * code + 2], "big") if 2 * code + 1 < len(self.cid2gid) else 0
            else:
                gid = code if self.prog_kind == "cidcff" and getattr(self.prog.top, "ROS", None) is None else self.prog.names.get("cid%05d" % code, code if self.prog_kind != "cidcff" else 0)
            b = self.prog.cbox(gid)
            if b is None: r = (0, 0, 0, 0)
            else:
                u = self.prog.upm
                r = [sc_tt2pdf(b[0], u), sc_tt2pdf(b[3], u), sc_tt2pdf(b[2], u), sc_tt2pdf(b[1], u)]
                r[1] += int(r[1] / 64)   # PDFium CPDF_CIDFont::GetCharBBox: rect.top += rect.top / 64
                r = tuple(r)
        else:
            g = self.gmap.get(code & 255 if code <= 255 else 0)
            b = None if g is None else self.prog.cbox(g)
            if b is None: r = (-1, -1, -1, -1)   # PDFium's unloaded marker stays: an empty box at the origin
            else:
                u = self.prog.upm
                r = (sc_tt2pdf(b[0], u), sc_tt2pdf(b[3], u), sc_tt2pdf(b[2], u), sc_tt2pdf(b[1], u))
        self.bboxes[code] = r
        return r


class SCDoc:
    def __init__(self, path):
        self.fp = open(path, "rb")
        self.doc = PDFDocument(PDFParser(self.fp))
        self.rsrc = PDFResourceManager(caching=True)
        self.pages = list(PDFPage.create_pages(self.doc))
        self.fonts = {}

    def page_size(self, page_no):
        """PDFium's page width and height in points: CropBox within MediaBox, swapped when rotated a quarter turn."""
        pg = self.pages[page_no - 1]; mb = pg.mediabox; cb = pg.cropbox or mb
        x0, y0, x1, y1 = max(mb[0], cb[0]), max(mb[1], cb[1]), min(mb[2], cb[2]), min(mb[3], cb[3])
        if x1 <= x0 or y1 <= y0: x0, y0, x1, y1 = mb
        w, h = x1 - x0, y1 - y0
        return (h, w, (x0, y0, x1, y1)) if pg.rotate % 180 == 90 else (w, h, (x0, y0, x1, y1))

    def font(self, objid, spec, pdffont):
        key = objid if objid is not None else id(spec)
        if key not in self.fonts: self.fonts[key] = SCFont(spec, pdffont, self)
        return self.fonts[key]


SC_DOCS = {}
def sc_doc(path):
    path = os.path.abspath(path)
    if path not in SC_DOCS: SC_DOCS[path] = SCDoc(path)
    return SC_DOCS[path]


class SCSink:
    def __init__(self):
        self.texts, self.shadings, self.holders = [], [], 0
        self.images, self.paint_serial = [], 0
        self.fills = []   # filled paths: page-space hull, fill colour and space, painted after serial `after`
    def new_holder(self):
        self.holders += 1; return self.holders


class SCInterpreter(PDFPageInterpreter):
    """pdfminer's interpreter, keeping what PDFium keeps and pdfminer drops: the clip paths (each a
    rectangular hull, page-space and holder-local, inherited into forms with their matrices and the
    form's BBox), the fill alpha (ExtGState ca), marked content, the text state a form inherits, each
    text-showing operator as one text object positioned as the PDF specifies, and each sh painting."""
    def __init__(self, rsrcmgr, device, sink=None, doc=None, holder=0):
        super().__init__(rsrcmgr, device)
        self.sink, self.doc_sc, self.holder, self.sc_start = sink, doc, holder, None

    def dup(self):
        return self.__class__(self.rsrcmgr, self.device, self.sink, self.doc_sc, self.holder)

    def init_resources(self, resources):
        super().init_resources(resources)
        self.sc_fontspec = {}
        fonts = dict_value(resolve1(resources.get("Font"))) if resources and resources.get("Font") is not None else {}
        for fid, spec in fonts.items():
            self.sc_fontspec[fid] = (spec.objid if isinstance(spec, PDFObjRef) else None, dict_value(spec))

    def init_state(self, ctm):
        super().init_state(ctm)
        st = self.sc_start or {}
        self.sc_clip = list(st.get("clip", [])); self.sc_alpha = st.get("alpha", 1.0); self.sc_font = st.get("font")
        self.sc_rectangular_clip = st.get('rectangular_clip', True)
        self.sc_image_compositing = st.get('image_compositing', (False, True, True))
        self.sc_outer = st.get("outer", MATRIX_IDENTITY); self.sc_outer_inv = sc_invert(self.sc_outer)
        self.sc_bbox_local = st.get("bbox_local", (0, 0, 0, 0)); self.sc_pending = False; self.sc_marks = []
        # PDFium's own text and transformation state, in single precision as PDFium keeps it
        self.sc_ctm32 = st.get("ctm32", SC_ID32); self.sc_form32 = st.get("form32", SC_ID32)
        self.sc_t = {"tm": SC_ID32, "h": 1.0, "line": (0.0, 0.0), "pos": (0.0, 0.0), "lead": 0.0, "rise": 0.0, "tmat": SC_ID32}
        if "text" in st:
            ts = self.textstate; ts.font, ts.fontsize, ts.charspace, ts.wordspace, ts.render = st["text"]

    def get_current_state(self):
        return super().get_current_state() + (list(self.sc_clip), self.sc_alpha, self.sc_font, self.sc_ctm32, dict(self.sc_t), self.sc_rectangular_clip, self.sc_image_compositing)

    def set_current_state(self, state):
        super().set_current_state(state[:3])
        if len(state) > 3: self.sc_clip, self.sc_alpha, self.sc_font, self.sc_ctm32, self.sc_t = state[3], state[4], state[5], state[6], state[7]
        if len(state) > 8: self.sc_rectangular_clip = state[8]
        if len(state) > 9: self.sc_image_compositing = state[9]

    # --- PDFium's text positioning (CPDF_AllStates), float32 ---
    def sc_text_matrix(self):   # OnChangeTextMatrix: Tz x Tm x CTM (BT, Tm and Tz only, as PDFium)
        t = self.sc_t; t["tmat"] = sc_mul32(sc_mul32((t["h"], 0.0, 0.0, 1.0, 0.0, 0.0), t["tm"]), self.sc_ctm32)
    def do_cm(self, a1, b1, c1, d1, e1, f1):
        args = (a1, b1, c1, d1, e1, f1); super().do_cm(*args)
        try: self.sc_ctm32 = sc_mul32(tuple(sc_f32(float(v)) for v in args), self.sc_ctm32)
        except Exception: sc_swallowed()
    def do_BT(self):
        super().do_BT(); t = self.sc_t; t["tm"] = SC_ID32; self.sc_text_matrix(); t["line"] = t["pos"] = (0.0, 0.0)
    def do_Tm(self, a, b, c, d, e, f):
        args = (a, b, c, d, e, f); super().do_Tm(*args); t = self.sc_t
        try: t["tm"] = tuple(sc_f32(float(v)) for v in args)
        except Exception: return
        self.sc_text_matrix(); t["line"] = t["pos"] = (0.0, 0.0)
    def do_Tz(self, scale):
        super().do_Tz(scale)
        try: self.sc_t["h"] = sc_f32(sc_f32(float(scale)) / 100)
        except Exception: return
        self.sc_text_matrix()
    def do_Ts(self, rise):
        super().do_Ts(rise)
        try: self.sc_t["rise"] = sc_f32(float(rise))
        except Exception: sc_swallowed()
    def do_TL(self, leading):
        super().do_TL(leading)
        try: self.sc_t["lead"] = sc_f32(float(leading))
        except Exception: sc_swallowed()
    def sc_move(self, tx, ty):
        t = self.sc_t; lx, ly = t["line"]; t["line"] = t["pos"] = (sc_f32(lx + tx), sc_f32(ly + ty))
    def do_Td(self, tx, ty):
        super().do_Td(tx, ty)
        try: self.sc_move(sc_f32(float(tx)), sc_f32(float(ty)))
        except Exception: sc_swallowed()
    def do_TD(self, tx, ty):
        super().do_TD(tx, ty)
        try: self.sc_move(sc_f32(float(tx)), sc_f32(float(ty))); self.sc_t["lead"] = sc_f32(-float(ty))
        except Exception: sc_swallowed()
    def do_T_a(self):
        super().do_T_a(); self.sc_move(0.0, sc_f32(-self.sc_t["lead"]))

    # clipping: W / W* take effect at the path's painting operator
    def do_W(self): self.sc_pending = True
    def do_W_a(self): self.sc_pending = True

    def _paint(self, base, fill=False):
        path = list(self.curpath)
        if fill and path and self.sink is not None:
            # Lane claims R3: a filled path's hull and colour, in paint order between the text objects and
            # images painted before and after it (the serials of those objects are left unchanged).
            pts = [(seg[k], seg[k + 1]) for seg in path for k in range(1, len(seg) - 1, 2)]
            if pts:
                loc = [sc_apply32(self.sc_ctm32, (sc_f32(x), sc_f32(y))) for x, y in pts]
                self.sink.fills.append(dict(box=sc_hull([apply_matrix_pt(self.sc_form32, q) for q in loc]),
                                            after=self.sink.paint_serial, fill_color=self.graphicstate.ncolor,
                                            fill_space=getattr(self.graphicstate.ncs, "name", None)))
        base()
        if self.sc_pending:
            self.sc_pending = False
            pts = [(seg[k], seg[k + 1]) for seg in path for k in range(1, len(seg) - 1, 2)]
            # The hull of a curved or compound clip is not proof of coverage.
            rectangular = (len(pts)==4 and len({p[0] for p in pts})==2 and len({p[1] for p in pts})==2
                           and all(seg[0] in ('m','l','h') for seg in path))
            self.sc_rectangular_clip &= rectangular
            if pts:
                loc = [sc_apply32(self.sc_ctm32, (sc_f32(x), sc_f32(y))) for x, y in pts]
                self.sc_clip.append((sc_hull([apply_matrix_pt(self.sc_form32, p) for p in loc]), sc_hull(loc), self.holder))
    def do_n(self): self._paint(super().do_n)
    def do_S(self): self._paint(super().do_S)
    def do_f(self): self._paint(super().do_f, True)
    def do_F(self):
        def f(): self.curpath = []
        self._paint(f, True)
    def do_f_a(self): self._paint(super().do_f_a, True)
    def do_B(self): self._paint(super().do_B, True)
    def do_B_a(self): self._paint(super().do_B_a, True)

    def do_gs(self, name):
        try:
            gs = dict_value(resolve1(dict_value(resolve1(self.resources.get("ExtGState")))[literal_name(name)]))
        except Exception:
            return
        if "ca" in gs:
            try: self.sc_alpha = float(resolve1(gs["ca"]))
            except Exception: sc_swallowed()
        masked, normal, group_safe = self.sc_image_compositing
        if 'SMask' in gs: masked = literal_name(resolve1(gs['SMask'])) != 'None'
        if 'BM' in gs: normal = literal_name(resolve1(gs['BM'])) == 'Normal'
        self.sc_image_compositing = masked, normal, group_safe

    def do_sh(self, name):
        """PDFium CPDF_ShadingObject: bounds = the clip box of the holder's own clip paths, else the holder's box."""
        try:
            sh = resolve1(dict_value(resolve1(self.resources.get("Shading")))[literal_name(name)])
        except Exception:
            return
        d = sh.attrs if isinstance(sh, PDFStream) else dict_value(sh)
        st = int(resolve1(d.get("ShadingType", 0)) or 0)
        if not 1 <= st <= 7: return
        own = [c[1] for c in self.sc_clip if c[2] == self.holder]
        if own:
            b = [max(c[0] for c in own), max(c[1] for c in own), min(c[2] for c in own), min(c[3] for c in own)]
            if b[0] > b[2] or b[1] > b[3]: b = [0, 0, 0, 0]
        else: b = list(self.sc_bbox_local)
        if st >= 4: SC_STATS["mesh_shadings_unbounded_by_mesh"] += 1
        self.sink.shadings.append(tuple(b))

    def do_BMC(self, tag):
        self.sc_marks.append(None); super().do_BMC(tag)
    def do_BDC(self, tag, props):
        p = resolve1(props)
        if isinstance(p, PSLiteral):
            try: p = resolve1(dict_value(resolve1(self.resources.get("Properties")))[literal_name(p)])
            except Exception: p = None
        self.sc_marks.append(p if isinstance(p, dict) else None); super().do_BDC(tag, props)
    def do_EMC(self):
        if self.sc_marks: self.sc_marks.pop()
        super().do_EMC()

    def do_Tf(self, fontid, fontsize):
        super().do_Tf(fontid, fontsize)
        spec = self.sc_fontspec.get(literal_name(fontid))
        self.sc_font = self.doc_sc.font(spec[0], spec[1], self.textstate.font) if spec and self.textstate.font is not None else None

    def do__w(self, aw, ac, s):
        """The " operator: Tw, Tc, then ' (move to the next line and show), as the PDF specifies."""
        self.do_Tw(aw); self.do_Tc(ac); self.do_T_a(); self.do_TJ([s])

    def do_TJ(self, seq):
        """One PDFium text object per showing operator: leading numbers move the start, the strings'
        letters are placed by CPDF_TextObject::CalcPositionData (float32), numbers between strings
        are kerning items, trailing numbers move the next start."""
        ts, f, t = self.textstate, self.sc_font, self.sc_t
        if ts.font is None or f is None: return
        fs = sc_f32(ts.fontsize); h = t["h"]; tc = sc_f32(ts.charspace); tw = sc_f32(ts.wordspace)
        segs, kern, init = [], [], 0.0
        for obj in seq:
            if isinstance(obj, (int, float)):
                if not segs: init += obj
                else: kern[-1] += obj
            elif isinstance(obj, bytes): segs.append(obj); kern.append(0.0)
        def hsize(k): return sc_f32(sc_f32(sc_f32(sc_f32(k) * fs) / 1000) * h)
        px_, py_ = t["pos"]
        if init: px_ = sc_f32(px_ - hsize(init))
        t["pos"] = (px_, py_)
        if not segs: return
        items, curpos = [], 0.0
        for si, s in enumerate(segs):
            for code in f.decode(s):
                items.append((code, curpos))
                curpos = sc_f32(curpos + sc_f32(sc_f32(f.width(code) * fs) / 1000))
                if f.single_byte_space(code): curpos = sc_f32(curpos + tw)
                curpos = sc_f32(curpos + tc)
            if si < len(segs) - 1 and kern[si]: curpos = sc_f32(curpos - sc_f32(sc_f32(sc_f32(kern[si]) * fs) / 1000))
        if items:
            tm = t["tm"]
            p = sc_apply32(tm, (px_, sc_f32(py_ + t["rise"])))
            p = sc_apply32(self.sc_ctm32, p)
            local = t["tmat"][:4] + p
            M = sc_mul32(local, self.sc_form32)
            self.sink.paint_serial += 1
            self.sink.texts.append({"font": f, "fs": fs, "M": M, "items": items,
                                    "paint_serial": self.sink.paint_serial,
                                    "fill_color": self.graphicstate.ncolor,
                                    "fill_space": getattr(self.graphicstate.ncs, "name", None),
                                    "render": ts.render, "alpha": self.sc_alpha, "clips": [cl[0] for cl in self.sc_clip], "holder": self.holder,
                                    "marks": [m for m in self.sc_marks if m is not None]})
        px_ = sc_f32(px_ + sc_f32(curpos * h))
        if kern[-1]: px_ = sc_f32(px_ - hsize(kern[-1]))
        t["pos"] = (px_, py_)
        lx, ly = ts.linematrix; ts.linematrix = (lx + curpos * h, ly)

    def do_Do(self, xobjid_arg):
        xobjid = literal_name(xobjid_arg)
        try: xobj = stream_value(self.xobjmap[xobjid])
        except Exception: return
        if literal_name(xobj.get("Subtype")) == "Image":
            self.sc_image(xobj)
        if xobj.get("Subtype") is LITERAL_FORM and "BBox" in xobj:
            interp = self.subinterp(); interp.holder = self.sink.new_holder()
            bbox = [float(resolve1(v)) for v in list_value(xobj["BBox"])]
            matrix = tuple(float(resolve1(v)) for v in list_value(xobj.get("Matrix", MATRIX_IDENTITY)))
            full = mult_matrix(matrix, self.ctm)
            bl = sc_transform_rect(matrix, bbox)
            ts = self.textstate
            m32 = tuple(sc_f32(v) for v in matrix)
            interp.sc_start = {"clip": self.sc_clip + [(sc_transform_rect(full, bbox), bl, interp.holder)], "alpha": self.sc_alpha, "font": self.sc_font,
                               "rectangular_clip": self.sc_rectangular_clip,
                               "image_compositing": (self.sc_image_compositing[0], self.sc_image_compositing[1],
                                   self.sc_image_compositing[2] and not xobj.get('Group')),
                               "text": (ts.font, ts.fontsize, ts.charspace, ts.wordspace, ts.render), "outer": self.ctm, "bbox_local": bl,
                               "ctm32": m32, "form32": sc_mul32(self.sc_ctm32, self.sc_form32)}
            xobjres = xobj.get("Resources")
            resources = dict_value(xobjres) if xobjres else self.resources.copy()
            interp.render_contents(resources, [xobj], ctm=full)

    def sc_image(self, obj):
        """Record image coverage and paint order without changing the reading layer.

        Only opaque, unmasked, axis-aligned images prove that earlier text has
        no visible ink. A transparent image or a rotated image's bounding box
        cannot prove occlusion. Soft masks, non-normal blending and transparency
        groups also veto occlusion evidence. Form and rectangular clips bound coverage.
        """
        box = list(sc_transform_rect(self.ctm, (0, 0, 1, 1)))
        for clip, _, _ in self.sc_clip:
            box = [max(box[0], clip[0]), max(box[1], clip[1]),
                   min(box[2], clip[2]), min(box[3], clip[3])]
        a, b, c, d, _, _ = self.ctm
        aligned = (abs(b) < 1e-7 and abs(c) < 1e-7) or (abs(a) < 1e-7 and abs(d) < 1e-7)
        self.sink.paint_serial += 1
        self.sink.images.append(dict(box=box, paint_serial=self.sink.paint_serial,
            rectangular=aligned and self.sc_rectangular_clip,
            opaque=aligned and self.sc_rectangular_clip and self.sc_alpha == 1
                and self.sc_image_compositing == (False, True, True) and not any(obj.get(k) for k in
                ("Mask", "SMask", "ImageMask", "IM"))))

    def do_EI(self, obj):
        self.sc_image(obj)
        super().do_EI(obj)


_SC_F32 = struct.Struct("<f")
_SC_F32_PACK = _SC_F32.pack
_SC_F32_UNPACK = _SC_F32.unpack

def sc_f32(x):
    """x rounded to single precision, as PDFium's float arithmetic leaves it."""
    return _SC_F32_UNPACK(_SC_F32_PACK(x))[0]


SC_ID32 = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def sc_mul32(m, r):
    """CFX_Matrix m * r (apply m, then r), every product and sum rounded to float."""
    F = sc_f32; a, b, c, d, e, f = m; ra, rb, rc, rd, re_, rf = r
    return (F(F(a * ra) + F(b * rc)), F(F(a * rb) + F(b * rd)), F(F(c * ra) + F(d * rc)), F(F(c * rb) + F(d * rd)),
            F(F(F(e * ra) + F(f * rc)) + re_), F(F(F(e * rb) + F(f * rd)) + rf))


def sc_apply32(m, p):
    """CFX_Matrix::Transform: (a x + c y + e, b x + d y + f) in float."""
    F = sc_f32; a, b, c, d, e, f = m; x, y = p
    return (F(F(F(a * x) + F(c * y)) + e), F(F(F(b * x) + F(d * y)) + f))


def sc_rect32(m, r):
    """CFX_Matrix::TransformRect in float: the hull of the four transformed corners."""
    return sc_hull([sc_apply32(m, (x, y)) for x in (r[0], r[2]) for y in (r[3], r[1])])


def sc_text_rect(o):
    """PDFium CPDF_TextObject::CalcPositionData: the object's box from its glyph boxes, in page space."""
    F = sc_f32; f, fs = o["font"], o["fs"]
    min_x, max_x, min_y, max_y = 10000.0, -10000.0, 10000.0, -10000.0
    for code, x in o["items"]:
        l, t, r, b = f.bbox(code)
        min_y = min(min_y, min(t, b)); max_y = max(max_y, max(t, b))
        cl = F(x + F(F(l * fs) / 1000)); cr = F(x + F(F(r * fs) / 1000))
        min_x = min(min_x, cl, cr); max_x = max(max_x, cl, cr)
    return sc_rect32(o["M"], (min_x, F(F(min_y * fs) / 1000), max_x, F(F(max_y * fs) / 1000)))


def sc_parse_tounicode(stream):
    """A ToUnicode CMap: bfchar and bfrange entries (a range's destination string counts up in its last
    letter; an array destination gives one string per code). Source codes are read as numbers,
    whatever their length against the codespace ranges, as PDFium reads them."""
    import re as _re
    out = {}
    if not isinstance(stream, PDFStream): return out
    try: data = stream.get_data().decode("latin-1")
    except Exception: return out
    data = _re.sub(r"%[^\r\n]*", "", data)
    def hx(s): return _re.sub(r"\s", "", s)
    def dst(s):
        b = bytes.fromhex(hx(s))
        try: return b.decode("utf-16-be")
        except Exception: return b.decode("latin-1")
    for blk in _re.findall(r"beginbfchar(.*?)endbfchar", data, _re.S):
        for src, d in _re.findall(r"<([0-9A-Fa-f\s]*)>\s*<([0-9A-Fa-f\s]*)>", blk):
            out[int(hx(src) or "0", 16)] = dst(d)
    for blk in _re.findall(r"beginbfrange(.*?)endbfrange", data, _re.S):
        for a, b, d in _re.findall(r"<([0-9A-Fa-f\s]*)>\s*<([0-9A-Fa-f\s]*)>\s*(<[0-9A-Fa-f\s]*>|\[[^\]]*\])", blk):
            lo, hi = int(hx(a) or "0", 16), int(hx(b) or "0", 16)
            if d.startswith("["):
                for k, s in enumerate(_re.findall(r"<([0-9A-Fa-f\s]*)>", d)):
                    if lo + k <= hi: out[lo + k] = dst(s)
            else:
                base = dst(d[1:-1])
                for k in range(hi - lo + 1):
                    out[lo + k] = base[:-1] + chr(min(ord(base[-1]) + k, 0x10FFFF)) if base else ""
    return out


def sc_text_string(s):
    """A PDF text string: UTF-16 with its byte order mark, else PDFDocEncoding."""
    if isinstance(s, str): return s
    if not isinstance(s, bytes): return ""
    from pdfminer.utils import decode_text
    try: return decode_text(s)
    except Exception: return s.decode("latin-1")


def sc_char_width(code, f):
    """PDFium text page GetCharWidth: the width, else the glyph box width."""
    w = f.width(code)
    if w > 0: return w
    l, _, r, _ = f.bbox(code)
    return max(r - l, 0)


def sc_unpainted_reason(o, box):
    """PDF visibility, before duplicate suppression can discard a painted twin."""
    if int(o["alpha"] * 255 + 0.5) == 0: return "zero fill alpha"
    if o["render"] in (3, 7): return "invisible or clip-only text render mode"
    for clip in o["clips"]:
        if box[0] >= clip[2] or box[2] <= clip[0] or box[1] >= clip[3] or box[3] <= clip[1]:
            return "outside text clip"
    return None


def sc_text_page(texts):
    """PDFium CPDF_TextPage: text objects gathered line by line (same baseline within a quarter of
    the larger letter width, twice), ordered along the line by position, an object repeating one of
    the five before it in its holder dropped, a letter repeating one of the seven before it at the
    same place dropped; each letter boxed by its glyph box and carrying its advance end when known.
    Returns character records with their objects, source codes and PDF painting order."""
    hist = collections.defaultdict(list); line = []; out = []; temp = []; temp_clips = set()
    prev_obj = [None]
    for paint_order, o in enumerate(texts): o["paint_order"] = paint_order; o["rect"] = sc_text_rect(o)
    def pos(o): return (o["M"][4], -o["M"][5])
    def same(o1, o2):   # IsSameTextObject(o1 = an earlier object, o2 = this one)
        r2, r1 = o2["rect"], o1["rect"]
        # Different visibility signatures must reach the visible-layer decision.
        # In particular, an earlier invisible twin cannot swallow printed ink.
        if (o1["clips"] != o2["clips"] or
                bool(sc_unpainted_reason(o1, r1)) != bool(sc_unpainted_reason(o2, r2))): return False
        e2 = r2[2] <= r2[0] or r2[3] <= r2[1]; e1 = r1[2] <= r1[0] or r1[3] <= r1[1]
        inter = r2
        if not (e2 and e1):
            inter = (max(r2[0], r1[0]), max(r2[1], r1[1]), min(r2[2], r1[2]), min(r2[3], r1[3]))
            if inter[2] <= inter[0] or inter[3] <= inter[1]: return False
            if abs((inter[2] - inter[0]) - (r1[2] - r1[0])) > (r1[2] - r1[0]) / 2: return False
            if o2["fs"] != o1["fs"]: return False
        if len(o2["items"]) != len(o1["items"]): return False
        if any(a[0] != b[0] for a, b in zip(o2["items"], o1["items"])): return False
        dx = o1["M"][4] - o2["M"][4]; dy = o1["M"][5] - o2["M"][5]
        cw = sc_char_width(o2["items"][-1][0], o2["font"])
        mx = max(inter[3] - inter[1], inter[2] - inter[0], o2["fs"])
        return abs(dx) <= 0.9 * cw * o2["fs"] / 1000 and abs(dy) <= mx / 8
    def width_on_page(o, code):
        return sc_char_width(code, o["font"]) * o["fs"] / 1000 * math.hypot(o["M"][0], o["M"][1])
    def marked(o):
        """PDFium PreMarkedContent: 'pass' (no ActualText to use), 'done' (the ActualText of this span was
        already given by the object before), 'delay' (give the ActualText in place of the object's letters)"""
        if not o["marks"]: return "pass", None
        act, pd = None, None
        for m in o["marks"]:
            pd = m
            if m.get("ActualText") is not None: act = m.get("ActualText")
        if act is None: return "pass", None
        p = prev_obj[0]
        if p is not None and len(p["marks"]) == len(o["marks"]) and p["marks"][-1] is pd: return "done", None
        t = sc_text_string(resolve1(act))
        if not t: return "pass", None
        if not any(o["font"].char_code_for(ch) is not None for ch in t): return "pass", None
        if not any((0x80 < ord(ch) < 0xFFFD) or (ord(ch) <= 0x80 and 32 <= ord(ch) < 127) for ch in t): return "done", None
        return "delay", t
    def process(o):
        state, act = marked(o)
        if state == "done":
            SC_STATS["actualtext_objects_skipped"] += 1; return
        prev_obj[0] = o
        f, M, fs = o["font"], o["M"], o["fs"]
        if state == "delay":
            SC_STATS["actualtext_objects_replaced"] += 1
            for glyph_order, ch in enumerate(act):
                if ord(ch) <= 0x80 and not (32 <= ord(ch) < 127): ch = " "
                if ord(ch) >= 0xFFFD: continue
                out.append((ch, o["rect"], (M[4], M[5]), o, True, None, None, (o["paint_order"], glyph_order))); temp.append((None, f, (M[4], M[5]), None))
            return
        F = sc_f32; k = F(fs / 1000); thr = READ_PARAMS["dup_letter_em"] * fs * math.hypot(M[0], M[1])
        for glyph_order, (code, x) in enumerate(o["items"]):
            u = f.unicode(code)
            if not u and code: u = chr(code) if code < 0x110000 else ""
            org = sc_apply32(M, (x, 0.0))
            l, t, r, b = f.bbox(code)
            top, left, right, bottom = F(t * k), F(F(l * k) + x), F(F(r * k) + x), F(b * k)
            if abs(top - bottom) < READ_PARAMS["zero_width_text_pt"]: top = F(bottom + k)
            if abs(right - left) < READ_PARAMS["zero_width_text_pt"]: right = F(left + F(f.width(code) * k))
            box = sc_rect32(M, (left, bottom, right, top))
            signature = (str(o.get("fill_color")), bool(sc_unpainted_reason(o, box)), tuple(map(tuple, o["clips"])))
            temp_clips.add(signature[2])
            if not u: temp.append((code, f, org, signature)); continue
            previous = temp[-READ_PARAMS["dup_letter_window"]:]
            if len(temp_clips) > 1:
                # A partial clip can leave a prefix more than seven letters
                # behind its fully painted twin. Compare the rest of this line
                # only across different clips; invisible letters never match ink.
                previous += [row for row in temp[:-READ_PARAMS["dup_letter_window"]]
                             if row[3] and row[3][2] != signature[2]]
            if any(c == code and ff is f and sig[1] == signature[1] and abs(ox - org[0]) < thr and abs(oy - org[1]) < thr for c, ff, (ox, oy), sig in previous):
                SC_STATS["duplicate_letters_dropped"] += 1; continue
            width = f.width(code)
            advance = sc_apply32(M, (F(x + F(width * k)), 0.0)) if width > 0 else None
            for ch in u:
                temp.append((code, f, org, signature)); out.append((ch, box, org, o, False, advance, code, (o["paint_order"], glyph_order)))
    def hyphen(o):
        """GenerateCharacter::kHyphen: a new line starts with a letter or digit while the text so far ends,
        spaces aside, in a hyphen after a letter; the hyphen is then reported as U+0002"""
        k = len(out) - 1
        while k >= 0 and out[k][0] == " ": k -= 1
        if k < 0 or out[k][0] not in ("-", "\xad"): return
        code = o["items"][0][0]; u = o["font"].unicode(code) or (chr(code) if code else "")
        piece = k == len(out) - 1 and out[k][4]   # IsHyphen's second clause: the last letter is an ActualText hyphen
        if not piece and (k < 1 or not out[k - 1][0].isalpha() or not u or not u[0].isalnum()): return
        out[k] = ("\x02",) + out[k][1:6] + ("line-end-hyphen",) + out[k][7:]; SC_STATS["line_end_hyphens_marked"] += 1   # tagged: only this U+0002 is a printed hyphen
    def vertical(o):
        """GetTextObjectWritingMode: the first and last letters' origins run along y"""
        if len(o["items"]) < 2: return None
        M = o["M"]; a = sc_apply32(M, (o["items"][0][1], 0.0)); b = sc_apply32(M, (o["items"][-1][1], 0.0))
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1]); n = math.hypot(dx, dy)
        if n <= 0.0001: return None
        if dy / n <= 0.0872: return False if dx / n > 0.0872 else None
        return True if dx / n <= 0.0872 else None
    def new_line(o, p):
        """the line-end test between consecutive objects; for vertical writing (EndVerticalLine) a new
        line needs the two objects clear of each other across the line"""
        v = vertical(o)
        if v is None: v = vertical(p)
        if not v: return True
        r, q = o["rect"], p["rect"]
        if (r[2] - r[0]) <= o["fs"] * 0.1 or (q[2] - q[0]) <= p["fs"] * 0.1: return False
        return min(r[2], q[2]) - max(r[0], q[0]) <= 0
    def flush():
        for i, o in enumerate(line):
            if i == 0 and out and prev_obj[0] is not None and new_line(o, prev_obj[0]): hyphen(o)
            process(o)
        line.clear(); temp.clear(); temp_clips.clear()
    for o in texts:
        prevs = hist[o["holder"]][-READ_PARAMS["dup_object_window"]:]; hist[o["holder"]].append(o)
        r = o["rect"]
        if abs(r[2] - r[0]) < READ_PARAMS["zero_width_text_pt"]: continue
        if not line: line.append(o); continue
        if any(same(p, o) for p in prevs):
            SC_STATS["duplicate_objects_dropped"] += 1; continue
        prev = line[-1]
        thr = max(width_on_page(prev, prev["items"][-1][0]), width_on_page(o, o["items"][0][0])) / 4
        pp, tp = pos(prev), pos(o)
        if abs(tp[1] - pp[1]) > thr * 2:
            flush(); line.append(o); continue
        for i in range(len(line), 0, -1):
            if tp[0] >= pos(line[i - 1])[0]:
                line.insert(i, o); break
        else:
            line.insert(0, o)
    flush()
    return out


def sc_normalise(ch):
    """PDFium's text page normalisation, as the recorded output shows it: a ligature of the Alphabetic
    Presentation Forms block is reported as the letters it stands for."""
    import unicodedata
    if ord(ch) > 0xFFFF:   # PDFium hands out UTF-16 units: a letter past U+FFFF is two surrogates (measured: montero p4)
        v = ord(ch) - 0x10000; SC_STATS["letters_as_surrogate_pairs"] += 1
        return chr(0xD800 + (v >> 10)) + chr(0xDC00 + (v & 0x3FF))
    if 0xFB00 <= ord(ch) <= 0xFB06:   # measured: the ligatures are split; U+00B4, U+00B5, U+2026, U+2122, U+1D705 are kept
        SC_STATS["letters_normalised"] += 1
        return unicodedata.normalize("NFKD", ch)
    return ch


SC_PAGES = {}
SC_SWALLOWED = {"n": 0}
def sc_font_metadata(page, chars=None, pdf_path=None):
    """Export reading-layer font identity and glyph-name corrections without changing layout.

    A run's font is its full PDF name (including the subset prefix), or a list
    for a mixed-font run. font_spans gives exact native-text offsets for each
    face. The page's fonts summary counts distinct assigned character IDs per
    face. Ink/region parts carry their own metadata so later layout splits keep
    the correct identity. Unverifiable IDs get no asserted font. Old page JSON
    can be annotated by the OCR checker with the same verified characters. Each
    glyph correction carries its run ID and zero-based offset in the saved text,
    plus font, source code and selected name. Unassigned characters have null run
    and offset and retain their box; no offset is invented for unverifiable IDs.
    counts.characters_corrected_from_glyph_names counts distinct character IDs.
    """
    if "elements" not in page: return page   # preserve the boxer's existing error result
    if chars is None:
        chars = sc_read_page(pdf_path, page["page"])[0]
        scale = page.get("params", {}).get("dpi", PARAMS["dpi"]) / PARAMS["dpi"]
        b = page["region_box_px"]
        chars = [c for c in chars if
                 b[0] <= scale*(c["x0"]+c["x1"])/2 <= b[2] and
                 b[1] <= scale*(c["y0"]+c["y1"])/2 <= b[3]]
        records = sc_hidden_layer_records(chars)
        if records:
            page["hidden_layers"] = records
            page.setdefault("counts", {})["characters_hidden_layers"] = sum(r["dropped_glyphs"] for r in records)
        chars = [c for c in chars if not c["hidden"]]
    used = collections.defaultdict(set)
    corrections = []; recorded = set()
    def annotate(e, count=False):
        e["font"], e["font_spans"] = None, []
        ids = e.get("char_ids", [])
        if not ids or any(not isinstance(i, int) or not 0 <= i < len(chars) for i in ids): return
        indexed = [(i, ch) for i in ids for ch in chars[i]["text"] if not ch.isspace()]
        positions = [(j, ch) for j, ch in enumerate(e["text"]) if not ch.isspace()]
        if [ch for _, ch in indexed] != [ch for _, ch in positions]: return
        spans = e["font_spans"]
        for (offset, _), (i, _) in zip(positions, indexed):
            font = chars[i]["font"]
            if spans and spans[-1]["font"] == font: spans[-1]["end"] = offset + 1
            else: spans.append({"font": font, "start": offset, "end": offset + 1})
            if count: used[font].add(i)
            if count and i not in recorded and chars[i].get("glyph_correction"):
                corrections.append(dict(chars[i]["glyph_correction"], run=e["id"], offset=offset, char_id=i))
                recorded.add(i)
        names = list(dict.fromkeys(s["font"] for s in spans))
        e["font"] = names[0] if len(names) == 1 else names
        for key in ("ink_parts", "region_parts"):
            for part in e.get(key, []): annotate(part)
    for e in page.get("elements", []):
        if e.get("kind") == "text": annotate(e, True)
    page["fonts"] = {font: {"characters": len(ids)} for font, ids in sorted(used.items())}
    for i, c in enumerate(chars):
        if i not in recorded and c.get("glyph_correction"):
            corrections.append(dict(c["glyph_correction"], run=None, offset=None, char_id=i,
                                    box_px=[c[k] for k in ("x0", "y0", "x1", "y1")]))
    page["glyph_corrections"] = corrections
    page.setdefault("counts", {})["characters_corrected_from_glyph_names"] = len(corrections)
    return page


def sc_glyph_correction_notices(pages):
    """Paper-level notices for a copy consumer; the reader never edits copy.md itself."""
    counts = collections.defaultdict(collections.Counter)
    for page in pages:
        for c in page.get("glyph_corrections", []):
            counts[c["font"]][c["from"], c["to"]] += 1
    return [f"font {font}: {sum(pairs.values())} characters read from glyph names (" +
            ", ".join(f"{a}→{b}: {n}" for (a, b), n in sorted(pairs.items())) + ")"
            for font, pairs in sorted(counts.items())]


def sc_swallowed():
    """an operand the reading layer could not parse (a malformed number, a font table it cannot read): left
    out as before, now counted, and reported on stderr for the page being read"""
    SC_SWALLOWED["n"] += 1


def sc_union_area(boxes, clip):
    """Rectangle union clipped to a page: overlapping images never add coverage twice."""
    boxes = [(max(a, clip[0]), max(b, clip[1]), min(c, clip[2]), min(d, clip[3]))
             for a, b, c, d in boxes]
    boxes = [b for b in boxes if b[2] > b[0] and b[3] > b[1]]
    xs = sorted({x for b in boxes for x in (b[0], b[2])})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((b[1], b[3]) for b in boxes if b[0] < right and b[2] > left)
        end = -float("inf"); height = 0.0
        for lo, hi in intervals:
            height += max(0, hi - max(lo, end)); end = max(end, hi)
        area += (right-left)*height
    return area


def sc_scan_evidence(doc, page_no, sink, full=False):
    """A raster page plus independent PDF evidence of an OCR layer.

    Up to four largest images must cover >=90% of the cropped page (union,
    not summed areas). At least 95% of text-showing characters must be mode 3,
    transparent, or entirely occluded by later opaque images, after excluding
    visible text wholly within the outer 8% header/footer bands; alternatively
    Creator/Producer must explicitly name an OCR engine. Coverage of >=80%
    or an OCR producer is retained as near-trigger evidence. Visible text over
    a page-sized background alone never qualifies. No layout classes change.
    """
    _, _, crop = doc.page_size(page_no)
    area = (crop[2]-crop[0])*(crop[3]-crop[1])
    images = sorted((im for im in sink.images if im.get('rectangular',True)),
                    key=lambda im: sc_union_area([im['box']], crop), reverse=True)[:4]
    coverage = sc_union_area([im['box'] for im in images], crop)/area if area else 0
    metadata = {}
    for info in doc.doc.info:
        for key in ('Creator', 'Producer'):
            value = resolve1(info.get(key, ''))
            if isinstance(value, bytes):
                value = value.decode('utf-16' if value.startswith((b'\xfe\xff', b'\xff\xfe')) else 'latin1', errors='replace')
            if value: metadata[key] = str(value)
    engine = bool(re.search(r'\b(?:ABBYY|FineReader|OmniPage|Tesseract|OCR|Paper Capture|Readiris|IRIS OCR)\b',
                            ' '.join(metadata.values()), re.I))
    if coverage < .8 and not engine and not full:
        return dict(candidate=False,ocr_layer=False,image_coverage=round(coverage,6),metadata=metadata,
                    image_count=len(sink.images),ocr_engine=False,visibility_checked=False)
    counts = collections.Counter()
    for obj in sink.texts:
        n = len(obj['items']); counts['text_characters'] += n
        mode3 = obj['render'] == 3
        transparent = obj['alpha'] <= 0 and obj['render'] in (0, 4)
        box = sc_text_rect(obj)
        a = (box[2]-box[0])*(box[3]-box[1])
        later = [im['box'] for im in images if im['opaque'] and im['paint_serial'] > obj['paint_serial']]
        under = bool(a > 0 and sc_union_area(later, box) >= a * .99999)
        counts['render_mode_3'] += n * mode3
        counts['transparent'] += n * transparent
        counts['under_later_opaque_image'] += n * under
        counts['invisible_characters'] += n * (mode3 or transparent or under)
        margin = box[3] <= crop[1]+.08*(crop[3]-crop[1]) or box[1] >= crop[3]-.08*(crop[3]-crop[1])
        counts['visible_margin_characters'] += n * (margin and not (mode3 or transparent or under))
    total = counts['text_characters']
    share = counts['invisible_characters']/total if total else 0
    content_total=total-counts['visible_margin_characters']
    content_share=counts['invisible_characters']/content_total if content_total else 0
    return dict(version=1, image_coverage=round(coverage, 6), image_count=len(sink.images),
                visibility_checked=True,
                covering_images=len(images), **counts, invisible_share=round(share, 6),
                content_invisible_share=round(content_share,6),
                metadata=metadata, ocr_engine=engine,
                candidate=coverage >= .8 or engine,
                ocr_layer=bool(coverage >= .9 and content_total >= 20 and (content_share >= .95 or engine)))


def sc_ocr_attach_raised(rows):
    """Return a raised small OCR group to the word the PDF's own text order puts it in.

    A superscript (the 2 of mm2, a citation) sits about half an em above its
    word's baseline, just outside the row tolerance (0.45 em), and can join a
    row of the other column that shares its baseline. Move it back only when
    the OCR layer itself witnesses the place: its characters (at most 3, the
    copier's small-run limit) are contiguous in PDF text order, directly after
    a character of another row and directly before that row's next character
    by x in the same run (no run gap between them), or that character ends its
    row; it is at most 0.82 of the host's
    size (the copier's superscript ratio); it lies right of that character
    within the row's own word-group gap (one em); its baseline is above the
    host baseline by less than one host em and its box overlaps the boxes of
    the characters it sits between. Without paint order nothing moves.
    """
    chars = [c for row in rows for c in row['chars']]
    if not chars or any(c.get('paint_order') is None for c in chars): return rows
    order = sorted(chars, key=lambda c: tuple(c['paint_order']))
    pos = {id(c): i for i, c in enumerate(order)}
    row_of = {id(c): row for row in rows for c in row['chars']}
    moves = []
    for row in rows:
        groups = [[]]
        for c in sorted(row['chars'], key=lambda c: c['x0']):
            if groups[-1] and c['x0']-groups[-1][-1]['x1'] > max(c['size'], groups[-1][-1]['size']):
                groups.append([])
            groups[-1].append(c)
        for g in groups:
            if not g or len(g) > 3: continue
            first = min(pos[id(c)] for c in g); last = max(pos[id(c)] for c in g)
            if last-first != len(g)-1 or first == 0: continue
            left = order[first-1]; host = row_of[id(left)]
            if host is row: continue
            line = sorted(host['chars'], key=lambda c: c['x0'])
            k = next(i for i, c in enumerate(line) if c is left)
            after = line[k+1] if k+1 < len(line) else None
            successor = order[last+1] if last+1 < len(order) else None
            if after is not None and successor is not after: continue
            if after is None and successor is not None and row_of[id(successor)] is host: continue
            # Between two of the host's runs the group is already its own run, and
            # the copier's left-edge order places it; joining the runs would also
            # change their word-space tracking. Only a group inside a run moves.
            if after is not None and after['x0']-left['x1'] > max(after['size'], left['size']): continue
            em = statistics.median(c['size'] for c in host['chars'])
            g = sorted(g, key=lambda c: c['x0'])
            base = statistics.median(c['origin'][1] for c in g)
            if (max(c['size'] for c in g) <= .82*em and
                left['x0'] <= g[0]['x0'] and g[0]['x0']-left['x1'] <= max(em, left['size']) and
                (after is None or g[-1]['x1'] <= after['x1']) and
                host['baseline']-em < base < host['baseline'] and
                # Its box must touch the boxes of the characters it sits between:
                # OCR origins can disagree with the ink (a table sign whose origin
                # is the top of its box), the boxes cannot be a line apart.
                min(max(c['y1'] for c in g), max(c['y1'] for c in (left, after) if c)) >
                max(min(c['y0'] for c in g), min(c['y0'] for c in (left, after) if c))):
                moves.append((g, row, host))
    for g, row, host in moves:
        row['chars'] = [c for c in row['chars'] if all(c is not d for d in g)]
        host['chars'].extend(g)
    return [row for row in rows if row['chars']]


def sc_ocr_runs(chars):
    """Raw OCR baselines, split at wide gaps; no spelling, symbol or name repair.

    Kept separately from visible rule-1 elements so invisible OCR never alters
    born-digital layout. Each source character belongs to exactly one run.
    """
    rows = []
    for c in sorted(chars, key=lambda c: (c['origin'][1], c['x0'])):
        if not c['text'].strip(): continue
        row = next((r for r in reversed(rows[-3:]) if
                    abs(r['baseline']-c['origin'][1]) <= .45*max(r['size'], c['size'])), None)
        if row is None:
            row = dict(baseline=c['origin'][1], size=c['size'], chars=[]); rows.append(row)
        row['chars'].append(c)
    rows = sc_ocr_attach_raised(rows)
    runs = []
    for row in rows:
        groups = [[]]
        for c in sorted(row['chars'], key=lambda c: c['x0']):
            if groups[-1] and c['x0']-groups[-1][-1]['x1'] > max(c['size'], groups[-1][-1]['size']):
                groups.append([])
            groups[-1].append(c)
        for cs in groups:
            text = ''
            gaps = sorted(c['origin'][0]-p['adv_x1'] for p, c in zip(cs, cs[1:]) if p.get('adv_x1') is not None)
            tracking = max(0, statistics.median(gaps)) if gaps else 0
            for i, c in enumerate(cs):
                if i:
                    prev = cs[i-1]
                    gap = c['origin'][0]-prev['adv_x1']-tracking if prev.get('adv_x1') is not None else c['x0']-prev['x1']
                    if prev.get('space_after') or gap > PARAMS['advance_space_em']*min(c['size'], prev['size']): text += ' '
                text += c['text']
            runs.append(dict(text=text, box_px=[min(c['x0'] for c in cs), min(c['y0'] for c in cs),
                max(c['x1'] for c in cs), max(c['y1'] for c in cs)], baseline=row['baseline'],
                size_px=statistics.median(c['size'] for c in cs)))
    return runs


# Port: paper-copy-language/converter/convert_page.py, dedupe_hidden_layers,
# visible-layer/1.1. DECISIONS.md C-010 requires the reading text to match the
# painted page; C-011 requires measured evidence, not hard-coded outcomes.
# That log has no separate numbered ruling for this function. The source's
# signature is fill colour (despite the inventory calling it a font signature).
def sc_dedupe_hidden_layers(chars, body_signature=None):
    """Port the two-largest-colour-groups, 8 glyph / 5%, 0.7 similarity rule.

    Known unpainted glyphs are excluded before choosing candidates. Text is in
    PDF painting order, as in the source's pdfplumber glyph list. With no paper
    body signature, the source keeps the later-drawn group. Its aggregate-box
    overlap test alone can erase independent repeated text in overlapping
    columns or panels. Here every discarded glyph must additionally have an
    identical, opaque, later-painted twin at the same place. Unwitnessed groups
    remain intact; the existing per-line overprint rule still handles them.
    Return retained glyphs and the source's decision record without mutating
    callers. The reader marks discarded twins hidden to preserve accounting.
    """
    import difflib
    groups = {}
    visible = [c for c in chars if not c.get("hidden")]
    for c in sorted(visible, key=lambda c: c["paint_order"]):
        groups.setdefault(str(c.get("fill_color")), []).append(c)
    large = [(sig, items) for sig, items in groups.items()
             if len(items) >= max(8, 0.05 * len(visible))]
    if len(large) < 2: return chars, []
    large.sort(key=lambda pair: -len(pair[1]))
    (sig_a, group_a), (sig_b, group_b) = large[:2]
    similarity = difflib.SequenceMatcher(
        a="".join(c["text"] for c in group_a if c["text"].strip()),
        b="".join(c["text"] for c in group_b if c["text"].strip())).ratio()
    if similarity < 0.7: return chars, []
    def box_of(items):
        return [min(c["x0"] for c in items), min(c["y0"] for c in items),
                max(c["x1"] for c in items), max(c["y1"] for c in items)]
    a, b = box_of(group_a), box_of(group_b)
    if min(a[2], b[2]) <= max(a[0], b[0]) or min(a[3], b[3]) <= max(a[1], b[1]): return chars, []
    kept = body_signature if body_signature in (sig_a, sig_b) else (
        sig_a if max(c["paint_order"] for c in group_a) > max(c["paint_order"] for c in group_b) else sig_b)
    dropped = sig_b if kept == sig_a else sig_a
    twins = collections.defaultdict(list)
    for c in groups[kept]: twins[(c["text"], c["font"])].append(c)
    used = set()
    for c in groups[dropped]:
        match = next((d for d in twins[(c["text"], c["font"])] if id(d) not in used
            and d["paint_order"] > c["paint_order"] and d.get("fill_alpha", 1) == 1
            and d.get("render_mode", 0) in (0, 4)
            and abs(d["size"] - c["size"]) <= 0.01 * c["size"]
            and all(abs(d[k] - c[k]) <= 0.01 * c["size"] for k in ("x0", "y0", "x1", "y1"))), None)
        if match is None: return chars, []
        used.add(id(match))
    ids = {id(c) for c in groups[dropped]}
    record = {"dropped_signature": dropped, "kept_signature": kept,
              "similarity": round(similarity, 3), "dropped_glyphs": len(ids),
              "evidence": "visible-layer/1.1: overlapping colour groups; every dropped glyph has an identical opaque later-painted twin"}
    return [c for c in chars if id(c) not in ids], [record]


SC_OVERPRINT_REASON = "white text object overprinted by later glyphs on a white background"


def sc_white_fill(color, space):
    """A fill colour that is white in its space: gray 1, RGB 1 1 1, CMYK 0 0 0 0, in the device spaces or in an
    ICC-based space of that many components (AP07's link is ICCBased 1 1 1); other spaces are not proven white."""
    v = (color,) if isinstance(color, (int, float)) else tuple(color or ())
    try: v = tuple(float(x) for x in v)
    except (TypeError, ValueError): return False
    icc = space == "ICCBased"
    return (((space == "DeviceGray" or icc) and v == (1.0,)) or ((space == "DeviceRGB" or icc) and v == (1.0, 1.0, 1.0))
            or ((space == "DeviceCMYK" or icc) and v == (0.0, 0.0, 0.0, 0.0)))


def sc_overprinted_layers(chars, texts, backgrounds):
    """Lane claims R3: an earlier text object that later glyphs paint over, in the background's colour.

    A text object is a hidden layer when both hold: (1) at least half of its glyphs are overlapped, by at
    least 30 % of their own box, by glyphs of later text objects (any font) that paint opaque ink in a
    colour that is not white, on the same line (baselines within line_tolerance_em of the smaller size);
    (2) it is filled white (render mode 0 or 4) and no non-white fill, shading or image painted before it
    lies under any of its glyphs (`backgrounds`: (box_px, serial) pairs, serial None for shadings). AP07 p1
    (DIAGNOSIS-AP E2): a white "https://doi.org/..." link object under the black "DOI: ..." line, same
    font, so neither the twin rule nor the two-font overprint rule applies. Of about 40,000 white glyphs on
    the 24 AP and gate papers, 27 are overprinted, all on that line; white text that nothing overprints
    (banners on colour) and white text on a drawn background stay. Returns the object indices (paint
    order) to hide; callers mark their glyphs hidden with SC_OVERPRINT_REASON.
    """
    objects = collections.defaultdict(list)
    for c in chars:
        if not c.get("hidden") and c["text"].strip(): objects[c["paint_order"][0]].append(c)
    def white(c): return sc_white_fill(c.get("fill_color"), c.get("fill_space")) and c.get("render_mode", 0) in (0, 4)
    def ink(d): return (not sc_white_fill(d.get("fill_color"), d.get("fill_space")) and d.get("fill_alpha", 1) == 1
                        and d.get("render_mode", 0) in (0, 2, 4, 6))
    def area(b): return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    hide = []
    for order, cs in objects.items():
        if not all(white(c) for c in cs): continue
        bx = (min(c["x0"] for c in cs), min(c["y0"] for c in cs), max(c["x1"] for c in cs), max(c["y1"] for c in cs))
        later = [d for k, ds in objects.items() if k > order for d in ds
                 if d["x0"] < bx[2] and d["x1"] > bx[0] and d["y0"] < bx[3] and d["y1"] > bx[1] and ink(d)]
        if not later: continue
        covered = 0
        for c in cs:
            box = (c["x0"], c["y0"], c["x1"], c["y1"]); a = area(box)
            if a <= 0: continue
            if any(abs(c["origin"][1] - d["origin"][1]) <= PARAMS["line_tolerance_em"] * min(c["size"], d["size"])
                   and area((max(box[0], d["x0"]), max(box[1], d["y0"]), min(box[2], d["x1"]), min(box[3], d["y1"])))
                   >= 0.3 * a for d in later):
                covered += 1
        if covered < 0.5 * len(cs): continue
        serial = texts[order].get("paint_serial") if 0 <= order < len(texts) else None
        if serial is None: continue
        under = [b for b, sb in backgrounds if sb is None or sb < serial]
        if any(b[0] <= (c["x0"] + c["x1"]) / 2 <= b[2] and b[1] <= (c["y0"] + c["y1"]) / 2 <= b[3]
               for c in cs for b in under): continue
        hide.append(order)
    return hide


def sc_hidden_layer_records(chars):
    """Lossless per-page accounting, including layers already excluded by clips.

    source_ranges are half-open indices in the reader's pre-filter character
    list, not the visible char_ids assigned by boxing. Text keeps PDF word
    spaces; fonts, bounds and the PDF visibility witness identify each layer.
    """
    groups = {}
    for c in chars:
        if not c.get("hidden"): continue
        key = (c.get("hidden_reason", "unpainted PDF text"), str(c.get("fill_color")))
        groups.setdefault(key, []).append(c)
    records = []
    for (why, signature), cs in groups.items():
        ranges = []
        for i in sorted(c["source_index"] for c in cs):
            if ranges and ranges[-1][1] == i: ranges[-1][1] = i + 1
            else: ranges.append([i, i + 1])
        records.append(dict(dropped_signature=signature, dropped_glyphs=len(cs), evidence=why,
            source_ranges=ranges, fonts=dict(sorted(collections.Counter(c["font"] for c in cs).items())),
            box_px=[min(c["x0"] for c in cs), min(c["y0"] for c in cs), max(c["x1"] for c in cs), max(c["y1"] for c in cs)],
            text="".join(c["text"] + (" " if c.get("space_after") else "")
                         for c in sorted(cs, key=lambda c: c["paint_order"])).rstrip()))
        if cs[0].get("hidden_layer_decision"): records[-1].update(cs[0]["hidden_layer_decision"])
    return records


def sc_read_page(pdf_path, page_no):
    """Read once per run: printable line-end hyphens, AGL/encoding recovery of missing glyph text,
    PDF space markers, advance ends, painting order and shading bounds. Unknown glyphs retain
    their boxes as flagged U+FFFD; raw character codes are not Unicode evidence. Recovery counts
    distinguish formerly unmapped controls from formerly raw code fallbacks, with routes and
    unresolved font/code/name counts in the page record and stderr. A selected glyph's
    exact name in SC_GLYPH_SYMBOLS overrides a conflicting single Latin letter/digit;
    symbols, generic names, multi-character mappings and ActualText stay authoritative.
    Corrections preserve geometry and carry their original text/name to sc_font_metadata,
    which exports run offsets and per-page counts. Hidden characters are not corrected.
    The visible-layer/1.1 port runs before boxing. Excluded glyphs remain in the
    reader with hidden=True; per-page hidden_layers records retain their text,
    source ranges, signatures, fonts, bounds and visibility evidence. Existing
    scan OCR runs remain available independently of the native visible layer."""
    key = (os.path.abspath(pdf_path), page_no)
    if key in SC_PAGES: return SC_PAGES[key]
    swallowed = SC_SWALLOWED["n"]
    d = sc_doc(pdf_path); page = d.pages[page_no - 1]
    _, h, bbox = d.page_size(page_no)
    sink = SCSink(); interp = SCInterpreter(d.rsrc, PDFDevice(d.rsrc), sink, d, 0)
    interp.sc_start = {"bbox_local": bbox}
    interp.render_contents(page.resources, page.contents, ctm=MATRIX_IDENTITY)
    scan = sc_scan_evidence(d, page_no, sink)
    chars = []
    controls = collections.Counter()
    routes = collections.Counter(); unknown = collections.Counter()
    for ch0, (l, b, r_, t), org, o, _piece, advance, code, paint_order in sc_text_page(sink.texts):
      f = o["font"]
      correction = None; inked_space = False
      raw_code = isinstance(code, int) and not _piece and not f.unicode(code)
      if ch0 == "\x02" and code == "line-end-hyphen":   # the reader's own mark, not a font's unmapped code 2
        replacements = [("-", True, False)]
      elif ord(ch0) < 32 or ch0 == "\ufffd" or raw_code:
        mapped, route = f.recover_unicode(code) if not _piece else ("", "")
        if mapped:
            replacements = [(ch, False, False) for c in mapped for ch in sc_normalise(c)]
            controls["mapped"] += 1
            routes[route] += 1
            controls["recovered_from_unmapped" if ord(ch0) < 32 or ch0 == "\ufffd" else "recovered_from_code"] += 1
        else:
            replacements = [("\ufffd", False, True)]
            controls["unmapped"] += 1
            name = f.adobe_name(code) if isinstance(code, int) and not f.cid else None
            unknown[(f.basefont, str(code), name or "")] += 1
      else:
        if not scan['ocr_layer'] and not _piece and isinstance(code, int) and f.unicode(code) == ch0:
            correction = f.glyph_correction(code, ch0)
        replacements = [(ch, False, False) for ch in sc_normalise(correction["to"] if correction else ch0)]
        # A text-layer space over an embedded outline that draws ink is no space (lane r2-signs): the
        # glyph is printed, so its text is recovered from its own glyph name or encoding, else flagged
        # as U+FFFD like any unmapped glyph; never dropped as a word break.
        if (not _piece and isinstance(code, int) and replacements and all(not ch.strip() for ch, _, _ in replacements)
                and f.inked(code)):
            mapped, route = f.recover_unicode(code)
            if mapped and mapped.strip():
                replacements = [(ch, False, False) for c in mapped for ch in sc_normalise(c)]
                controls["mapped"] += 1; routes[route] += 1; controls["recovered_from_space"] += 1
            else:
                replacements = [("\ufffd", False, True)]; inked_space = True
                controls["unmapped"] += 1; controls["inked_space_claims"] += 1
                name = f.adobe_name(code) if not f.cid else None
                unknown[(f.basefont, str(code), name or "")] += 1
      for ch, line_end_hyphen, dropped_control in replacements:
        if ch and not ch.strip():   # a space glyph of the PDF's own: the character before it ends a word
            if chars: chars[-1]["space_after"] = True
            continue
        ob = o["rect"]
        hidden_reason = sc_unpainted_reason(o, ob) or sc_unpainted_reason(o, (l, b, r_, t))
        hidden = bool(hidden_reason)
        M = o["M"]; scale = math.hypot(M[0], M[1])
        ang = math.atan2(M[2], M[0])
        if ang < 0: ang += 2 * math.pi
        chars.append({"text": ch, "x0": px(l), "y0": px(h - t), "x1": px(r_), "y1": px(h - b), "origin": (px(org[0]), px(h - org[1])),
                      "size": px(o["fs"] * (scale if scale > 0 else 1.0)), "angle": round(-math.degrees(ang)) % 360,
                      "font": o["font"].basefont, "font_key": id(o["font"]), "hidden": hidden, "page": page_no,
                      "source_code": code, "paint_order": paint_order,
                      "render_mode": o["render"], "fill_alpha": o["alpha"], "fill_color": o.get("fill_color"),
                      "fill_space": o.get("fill_space"), "line_end_hyphen": line_end_hyphen, "dropped_control": dropped_control,
                       "adv_x1": px(advance[0]) if advance is not None else None,
                       "adv_y1": px(h - advance[1]) if advance is not None else None})
        if hidden_reason: chars[-1]["hidden_reason"] = hidden_reason
        if inked_space:
            # Flagged in place (lane r2-signs): the text layer set a space here, so the character keeps a
            # space's footprint for line grouping: its advance across, and the vertical extent of the
            # character before it on the same baseline (else the em above the baseline). Its ink box is
            # kept as evidence only, so a large drawn glyph cannot grow its run or regroup lines.
            c = chars[-1]; c["inked_space_claim"] = True; c["ink_box"] = [c["x0"], c["y0"], c["x1"], c["y1"]]
            prev = chars[-2] if len(chars) > 1 else None
            ox, oy = c["origin"]
            right = c["adv_x1"] if c["adv_x1"] is not None and c["adv_x1"] > ox else ox
            if prev is not None and not prev["hidden"] and abs(prev["origin"][1] - oy) <= PARAMS["line_tolerance_em"] * min(prev["size"], c["size"]):
                top, bottom = prev["y0"], prev["y1"]
            else: top, bottom = oy - c["size"], oy
            c.update(x0=ox, x1=right, y0=top, y1=bottom)
        if correction:
            if hidden: chars[-1]["text"] = ch0   # no printed glyph to correct
            else:
                chars[-1]["glyph_correction"] = correction
                controls["corrected_from_glyph_names"] += 1
    for i, c in enumerate(chars): c["source_index"] = i
    shadings = [(px(l), px(h - t), px(r_), px(h - b)) for l, b, r_, t in sink.shadings]
    if not scan['ocr_layer']:
        retained, duplicates = sc_dedupe_hidden_layers(chars)
        retained_ids = {id(c) for c in retained}
        for c in chars:
            if id(c) not in retained_ids:
                c.update(hidden=True, hidden_reason=duplicates[0]["evidence"], hidden_layer_decision=duplicates[0])
        backgrounds = [((px(f["box"][0]), px(h - f["box"][3]), px(f["box"][2]), px(h - f["box"][1])), f["after"] + 0.5)
                       for f in sink.fills if not sc_white_fill(f["fill_color"], f["fill_space"])]
        backgrounds += [((px(im["box"][0]), px(h - im["box"][3]), px(im["box"][2]), px(h - im["box"][1])), im["paint_serial"])
                        for im in sink.images]
        backgrounds += [(b, None) for b in shadings]
        covered = set(sc_overprinted_layers(chars, sink.texts, backgrounds))
        for c in chars:
            if not c.get("hidden") and c["paint_order"][0] in covered:
                c.update(hidden=True, hidden_reason=SC_OVERPRINT_REASON)
    counts = dict(controls)
    if scan['candidate']:
        counts['scan_evidence'] = scan
        if scan['ocr_layer']: scan['ocr_runs'] = sc_ocr_runs(chars)
    counts["glyph_recovery"] = {
        "characters_corrected_from_glyph_names": controls["corrected_from_glyph_names"],
        "characters_recovered_from_unmapped": controls["recovered_from_unmapped"],
        "characters_recovered_from_code": controls["recovered_from_code"],
        "characters_recovered_by_route": dict(sorted(routes.items())),
        "unmapped_glyphs": [{"font": font, "code": code, "glyph_name": name, "count": n}
                           for (font, code, name), n in sorted(unknown.items())]}
    SC_PAGES[key] = (chars, shadings, counts)
    print(f"reading layer, page {page_no}: glyph recovery " + json.dumps(counts["glyph_recovery"], ensure_ascii=True, sort_keys=True), file=sys.stderr)
    read_pages = [v[2] for (path, _), v in SC_PAGES.items() if path == key[0]]
    if len(read_pages) == len(d.pages):
        total = collections.Counter(); total_routes = collections.Counter()
        for pc in read_pages:
            total.update({k: pc.get(k, 0) for k in ("unmapped", "recovered_from_unmapped", "recovered_from_code", "corrected_from_glyph_names")})
            total_routes.update(pc["glyph_recovery"]["characters_recovered_by_route"])
        print("reading layer, paper glyph totals: " + json.dumps({"pages": len(read_pages), **total,
              "recovered_by_route": dict(total_routes)}, sort_keys=True), file=sys.stderr)
    if SC_SWALLOWED["n"] > swallowed:
        print(f"reading layer, page {page_no}: {SC_SWALLOWED['n'] - swallowed} operand(s) could not be parsed and were left out", file=sys.stderr)
    return SC_PAGES[key]


def sc_page_count(pdf_path):
    return len(sc_doc(pdf_path).pages)


def sc_page_size(pdf_path, page_no):
    w, h, _ = sc_doc(pdf_path).page_size(page_no)
    return w, h


def sc_page_box_px(pdf_path, page_no):
    """Rule 1: the whole page's region is the visible page (CropBox within MediaBox) in the reading frame.

    The reading layer keeps PDF user x and flips y against the CropBox height, so the visible page is
    [crop x0, -crop y0, crop x1, height - crop y0], not [0, 0, width, height]. Where the CropBox (or the
    MediaBox) does not start at the user-space origin, the zero-based box cut off a band of the visible
    page at its right and top edges, and every character there was dropped silently before rule 1
    (measured: AI03, MediaBox 864 x 849, CropBox from (43.2, 21.6): the last 43 pt of the right column
    lost "de-", "38%" -> "3", "statistical analy[sis]", Table 1 total digits; AH06 and AB05 alike, their
    page numbers and running heads). Characters and drawn objects keep their coordinates; only the
    region that admits them is the page as printed. Unrotated pages only, like plumber_shift_px: the
    rotated frames are left as they were."""
    d = sc_doc(pdf_path); w, h, (x0, y0, x1, _) = d.page_size(page_no)
    if d.pages[page_no - 1].rotate % 360 or (x0, y0) == (0, 0): return [0, 0, px(w), px(h)]
    return [px(x0), px(-y0), px(x1), px(h - y0)]


def pdfium_shadings(pdf_path, page_no):
    """Shading (gradient) objects on the page, in the mapper's page-pixel frame: each sh painting's
    bounds as PDFium gives them (its holder's clip box), from the reading layer."""
    return [tuple(s) for s in sc_read_page(pdf_path, page_no)[1]]


def pdfium_characters(pdf_path, page_no):
    """Every character on the page, in the mapper's page-pixel frame, with the page's own verdict on
    whether it is painted: outside its text object's clip path, fully transparent, or in invisible
    render mode = unpainted. The reading layer's PDFium-convention replacement (same records)."""
    return [dict(c) for c in sc_read_page(pdf_path, page_no)[0]]


def rehome_raised_markers(lines):
    """Resolve small raised/lowered runs against body bands, after baseline clustering.

    A marker can share a provisional line with the other column, or be split at a
    narrow dash. Reconstruct its baseline run independently of those memberships.
    Compare the run's ink with the x-height band of nearby larger letters, then
    use the closest baseline below its bottom if no band overlaps. Requiring a
    horizontal insertion gap keeps a small line of prose from becoming a marker.
    Lowered ink overlaps the descender band and extends below it; its top may
    straddle the body baseline by up to a quarter em. Require native-character
    adjacency without a space glyph to the preceding body letter as well as geometric adjacency, so
    an independent small line or cell cannot attach just because it is nearby.
    Snapshot all candidates before moving anything: one repair cannot change the
    evidence for another. Source line numbers refer to this snapshot, per angle.
    """
    owners = {id(c): i for i, ln in enumerate(lines) for c in ln["chars"]}
    chars = [c for ln in lines for c in ln["chars"] if not c.get("dropcap")]
    for c in chars:
        c.pop("marker_from_line", None); c.pop("marker_glue", None); c.pop("marker_kind", None)
    rows = []
    for c in sorted(chars, key=lambda c: (c["vb"], c["u0"])):
        row = next((r for r in reversed(rows[-3:])
                    if abs(r[0]["vb"] - c["vb"]) <= 0.1 * c["size"]
                    and abs(r[0]["size"] - c["size"]) <= 0.1 * c["size"]), None)
        if row is None: rows.append([c])
        else: row.append(c)
    groups = []
    for row in rows:
        row.sort(key=lambda c: c["u0"])
        group = []
        for c in row:
            if group and c["u0"] - group[-1]["u1"] > PARAMS["wordspace_max_em"] * c["size"]:
                groups.append(group); group = []
            group.append(c)
        if group: groups.append(group)
    changes = []
    for group in groups:
        # Raised words (strain names, mathematical labels) need an explicit
        # script representation to preserve their word boundaries. Flattening
        # them into prose would erase vocabulary tokens; leave that to a math reader.
        text = "".join(c["text"] for c in group)
        if re.search(r"[A-Za-z]{3,}", text) or (any(t.isalpha() for t in text) and any(t.isdigit() for t in text)): continue
        size = max(c["size"] for c in group)
        left, right = min(c["u0"] for c in group), max(c["u1"] for c in group)
        top, bottom = min(c["v0"] for c in group), max(c["v1"] for c in group)
        base = statistics.median(c["vb"] for c in group)
        candidates = []
        for i, ln in enumerate(lines):
            if size >= PARAMS["superscript_em"] * ln["size"]: continue
            if abs(base - ln["vb"]) > 2 * PARAMS["superscript_shift_em"] * ln["size"]: continue
            near = [d for d in ln["chars"] if not d.get("dropcap")
                    and size < PARAMS["superscript_em"] * d["size"]
                    and max(left - d["u1"], d["u0"] - right) <= 3 * d["size"]]
            if not near: continue
            body = statistics.median(d["size"] for d in near)
            full = [d for d in near if d["size"] >= PARAMS["superscript_em"] * body
                    and d["text"].isalnum() and d["v1"] <= d["vb"] + 0.3 * body]
            if not full: continue
            baseline = statistics.median(d["vb"] for d in full)
            raised = bottom < baseline and 0 < baseline - base <= PARAMS["superscript_shift_em"] * body
            descender = baseline + 0.2 * body
            lowered = (0.1 * body < base - baseline <= PARAMS["superscript_shift_em"] * body
                       and baseline - 0.25 * body < top < descender < bottom)
            if not (raised or lowered): continue
            # A body anchor has a word or a multi-digit value on one baseline.
            # Isolated variables, operators and punctuation are not evidence of
            # a body line: folding scripts into them can rearrange an equation.
            aligned = sorted((d for d in full if abs(d["vb"] - baseline) <= PARAMS["line_tolerance_em"] * body), key=lambda d: d["u0"])
            words = ""
            for j, d in enumerate(aligned):
                if j and d["u0"] - aligned[j-1]["u1"] > PARAMS["wordspace_min_em"] * body: words += " "
                words += d["text"]
            if not re.search(r"[A-Za-z]{3,}|\d{2,}", words): continue
            if raised and any(d["size"] < PARAMS["superscript_em"] * body
                   and 0.1 * body < d["vb"] - baseline < 0.5 * body
                   and max(left - d["u1"], d["u0"] - right) <= 3 * body
                   for d in ln["chars"]): continue
            if min(max(left - d["u1"], d["u0"] - right) for d in full) > PARAMS["wordspace_max_em"] * body: continue
            if any(min(c["u1"], d["u1"]) - max(c["u0"], d["u0"]) >
                   0.34 * min(c["u1"] - c["u0"], d["u1"] - d["u0"])
                   for c in group for d in full): continue
            if lowered:
                preceding = [d for d in full if d["u1"] <= left]
                if not preceding: continue
                prev = max(preceding, key=lambda d: d["u1"])
                if (not prev["text"].isalpha() or prev.get("space_after")
                    or left - prev["u1"] > PARAMS["wordspace_max_em"] * body
                    or prev["id"] + 1 != group[0]["id"]): continue
                overlap = min(bottom, descender) - max(top, baseline)
                if overlap > 0: candidates.append((-overlap, base - baseline, i, "sub"))
                continue
            # Lowercase letters without ascenders estimate the font's x height;
            # a capital-only label falls back to half an em.
            tops = [d["v0"] for d in full if d["text"] in "acemnorsuvwxz"]
            x_top = statistics.median(tops) if tops else baseline - 0.5 * body
            overlap = max(0, min(bottom, baseline) - max(top, x_top))
            candidates.append((-overlap, baseline - bottom, i, "sup"))
        if not candidates: continue
        _, _, target, kind = min(candidates)
        # An upper and lower script can occupy the same x position. Re-homing
        # only the upper tier cannot express that stack in a flat run sequence.
        # Keep the existing equation layout instead of interleaving its tiers.
        if kind == "sup" and any(d not in group and d["size"] < PARAMS["superscript_em"] * lines[target]["size"]
               and 0.1 * size < d["vb"] - base < lines[target]["size"]
               and any(min(c["u1"], d["u1"]) - max(c["u0"], d["u0"]) >
                       0.34 * min(c["u1"] - c["u0"], d["u1"] - d["u0"])
                       for c in group) for d in chars): continue
        if any(owners[id(c)] != target for c in group):
            changes.append((group, target, kind))
    for group, target, kind in changes:
        for c in group:
            c["marker_glue"] = True
            source = owners[id(c)]
            if source == target: continue
            c["marker_from_line"] = source + 1
            if kind == "sub": c["marker_kind"] = kind
            lines[source]["chars"].remove(c)
            lines[target]["chars"].append(c)
    return [ln for ln in lines if ln["chars"]]


def split_display_face_lines(lines, objs, to_read):
    """A display-face line beside a body line stays its own line (lane r3-pullquote).

    A pull quote set at the body's nominal size in another face stands beside the body text, which runs
    around it; where a quote baseline and a body baseline fall within the line tolerance, baseline
    clustering puts both on one line and the run builder joins them across the narrow gap between them,
    weaving the quote word by word into the paragraph (measured: AO05 p1, an ultra-black quote at a
    29 px pitch beside 25 px body lines, 14 px apart). A line is parted into pieces where the face
    changes across a gap wider than word spacing (display_gap_em letter heights). A piece leaves the
    line when the run builder would join it to a neighbour (one of its gaps under run_gap_em and
    run_gap_wordspaces of the line's word spaces), it is set wholly in one face that the rest of the
    line does not use, it and the rest carry two or more letters each, and either
      - stands in its own frame: a drawn fill holding it whose edges lie between it and its neighbours
        on the line, or a pair of horizontal rules of one width above and below it within frame_reach_em
        letter heights that cover it and stop short of its neighbours; or
      - keeps its own pitch: three or more such pieces in one face on one side, stacked within
        3 letter heights of each other, off the baseline of the letters they would be joined to (by more
        than shared_baseline_em), forming one column of their own (a shared x band and one aligned edge,
        left, right or centre, within 1 em), whose offsets to those letters drift by more than
        pitch_drift_em letter heights (two line pitches; one pitch gives a constant offset, and a run-in
        name before its sentence or an italic journal name inside a reference none).
    Run-in labels, inline bold or italic words and drop caps have no such frame or drift, or carry under
    two letters, and stay in their lines."""
    hrules = []; fills = []
    for o in objs:
        u0, v0, u1, v1 = to_read(*o["box_px"])
        if o["kind"] == "rule" and (u1 - u0) > (v1 - v0): hrules.append((u0, v0, u1, v1))
        elif o["kind"] == "fill" and not o.get("overlay"): fills.append((u0, v0, u1, v1))
    def box(cs): return (min(c["u0"] for c in cs), min(c["v0"] for c in cs), max(c["u1"] for c in cs), max(c["v1"] for c in cs))
    cands = []   # (line, piece chars, joined neighbour chars, face, side, piece box, (left neighbour u1, right neighbour u0))
    for ln in lines:
        cs = sorted((c for c in ln["chars"] if not c.get("dropcap")), key=lambda c: c["u0"])
        if len(cs) < 4 or len({c["font"] for c in cs}) < 2: continue
        size = ln["size"]
        small = [b["u0"] - a["u1"] for a, b in zip(cs, cs[1:]) if PARAMS["wordspace_min_em"] * size <= b["u0"] - a["u1"] < PARAMS["wordspace_max_em"] * size]
        wordspace = statistics.median(small) if small else None
        def joins(i):   # the run builder would join across this gap
            g = cs[i]["u0"] - cs[i - 1]["u1"]
            return g <= PARAMS["run_gap_em"] * size and not (wordspace is not None and g > PARAMS["run_gap_wordspaces"] * wordspace)
        cuts = [i for i in range(1, len(cs)) if cs[i]["font"] != cs[i - 1]["font"] and cs[i]["u0"] - cs[i - 1]["u1"] > PARAMS["display_gap_em"] * size]
        if not any(joins(i) for i in cuts): continue
        bounds = [0] + cuts + [len(cs)]
        for k in range(len(bounds) - 1):
            lo, hi = bounds[k], bounds[k + 1]
            if not ((lo and joins(lo)) or (hi < len(cs) and joins(hi))): continue   # only a piece the run builder would weave
            piece = cs[lo:hi]; rest = cs[:lo] + cs[hi:]
            faces = {c["font"] for c in piece}
            if len(faces) != 1 or not rest: continue
            face = next(iter(faces))
            if any(c["font"] == face for c in rest) or sum(c["text"].isalpha() for c in piece) < 2: continue
            if sum(c["text"].isalpha() for c in rest) < 2: continue
            side = "left" if lo == 0 else "right" if hi == len(cs) else "middle"
            # the neighbouring pieces it would be joined to: the pitch test compares its baseline with theirs
            # only the letters the run builder would join to it, across gaps it would not cut
            joined = []
            if lo and joins(lo):
                j = lo - 1
                while j > bounds[k - 1] and joins(j): j -= 1
                joined += cs[j:lo]
            if hi < len(cs) and joins(hi):
                j = hi + 1
                while j < bounds[k + 2] and joins(j): j += 1
                joined += cs[hi:j]
            cands.append((ln, piece, joined, face, side, box(piece), (cs[lo - 1]["u1"] if lo else None, cs[hi]["u0"] if hi < len(cs) else None)))
    def framed(pb, nb, size):
        def apart(u0, u1):   # the frame's edges stand between the piece and its neighbours on the line
            return (nb[0] is None or u0 >= nb[0] - 2) and (nb[1] is None or u1 <= nb[1] + 2)
        for f in fills:
            if f[0] - 2 <= pb[0] and pb[2] <= f[2] + 2 and f[1] - 2 <= pb[1] and pb[3] <= f[3] + 2 and apart(f[0], f[2]): return True
        cover = [r for r in hrules if r[0] <= pb[0] + 2 and r[2] >= pb[2] - 2 and apart(r[0], r[2])]
        above = [r for r in cover if r[3] <= pb[1] + 2 and pb[1] - r[3] <= PARAMS["frame_reach_em"] * size]
        below = [r for r in cover if r[1] >= pb[3] - 2 and r[1] - pb[3] <= PARAMS["frame_reach_em"] * size]
        return any(abs(a[0] - b[0]) <= size and abs(a[2] - b[2]) <= size for a in above for b in below)
    accepted = set()
    for i, (ln, piece, rest, face, side, pb, nb) in enumerate(cands):
        if framed(pb, nb, ln["size"]): accepted.add(i)
    # pitch: stacks of pieces in one face on one side
    order = sorted(range(len(cands)), key=lambda i: cands[i][5][1])
    seen = set()
    for i in order:
        if i in seen: continue
        stack = [i]; seen.add(i)
        for j in order:
            if j in seen: continue
            a, b = cands[stack[-1]], cands[j]
            if b[3] != a[3] or b[4] != a[4] or min(a[5][2], b[5][2]) <= max(a[5][0], b[5][0]): continue
            if b[5][1] - a[5][3] > 3 * a[0]["size"]: break
            stack.append(j); seen.add(j)
        em = cands[i][0]["size"]
        offset = {k: statistics.median(c["vb"] for c in cands[k][1]) - statistics.median(c["vb"] for c in cands[k][2]) for k in stack}
        # a piece on its neighbours' own baseline is an inline word of that line (an italic journal name in a
        # reference), whatever the lines around it do
        stack = [k for k in stack if abs(offset[k]) > PARAMS["shared_baseline_em"] * em]
        if len(stack) < 3: continue
        # the pieces form one column of their own: they share an x band and one aligned edge (left, right or centre)
        bx = [cands[k][5] for k in stack]
        if max(b[0] for b in bx) >= min(b[2] for b in bx): continue
        if not any(max(v) - min(v) <= em for v in ([b[0] for b in bx], [b[2] for b in bx], [(b[0] + b[2]) / 2 for b in bx])): continue
        drift = [offset[k] for k in stack]
        if max(drift) - min(drift) > PARAMS["pitch_drift_em"] * em: accepted.update(stack)
    if not accepted: return lines
    for i in sorted(accepted):
        ln, piece = cands[i][0], cands[i][1]
        if not all(c in ln["chars"] for c in piece): continue
        for c in piece: ln["chars"].remove(c)
        lines.append({"vb": statistics.median(c["vb"] for c in piece), "size": max(c["size"] for c in piece), "chars": list(piece)})
    lines = [ln for ln in lines if ln["chars"]]
    for ln in lines: ln["vb"] = statistics.median(c["vb"] for c in ln["chars"]); ln["size"] = max(c["size"] for c in ln["chars"])
    lines.sort(key=lambda L: L["vb"])
    return lines

def stacked_script_order(cs, size, barred=None):
    """O20/O21 (lane r5-line): a lowered and a raised group stacked on one letter are each written whole, right after
    that letter: the lowered group first, then the raised one (a choice; the rules name no order for two tiers).
    Left-edge order alone would interleave their characters ("γLsW" for a γ carrying s below and LW above).
    A script is a character smaller than superscript_em of the line's size whose baseline lies more than a tenth of
    the size above or below the median baseline of the line's full-size characters; a group is a run of one tier's
    characters with no full-size character and no gap over 0.3 of the size between them. Lines without two
    overlapping groups of opposite tiers keep their left-edge order unchanged."""
    full = [c for c in cs if c["size"] >= PARAMS["superscript_em"] * size]
    small = [c for c in cs if c["size"] < PARAMS["superscript_em"] * size]
    if len(full) < 2 or len(small) < 2: return cs
    base = statistics.median(c["vb"] for c in full)
    def tier(c):
        if c["size"] >= PARAMS["superscript_em"] * size: return None
        if c["vb"] < base - 0.1 * size: return "up"
        if c["vb"] > base + 0.1 * size: return "down"
        return None
    groups = []
    for t in ("down", "up"):
        cur = []
        for c in cs:   # cs is in left-edge order
            k = tier(c)
            if k is None and c["size"] >= PARAMS["superscript_em"] * size:
                if cur: groups.append((t, cur)); cur = []
                continue
            if k != t: continue
            if cur and c["u0"] - max(d["u1"] for d in cur) > 0.3 * size:
                groups.append((t, cur)); cur = []
            cur.append(c)
        if cur: groups.append((t, cur))
    def span(g): return min(c["u0"] for c in g), max(c["u1"] for c in g)
    key = {}
    for td, gd in groups:
        if td != "down": continue
        for tu, gu in groups:
            if tu != "up": continue
            (a0, a1), (b0, b1) = span(gd), span(gu)
            if min(a1, b1) <= max(a0, b0): continue
            if barred is not None and barred(gu, gd): continue   # a fraction (a drawn bar between the tiers) stays as it was
            start = min(a0, b0)
            for rank, g in ((0, gd), (1, gu)):
                for i, c in enumerate(sorted(g, key=lambda c: c["u0"])): key[id(c)] = (start, rank, i)
    if not key: return cs
    return sorted(cs, key=lambda c: key.get(id(c), (c["u0"], -1, 0)))


def lines_and_runs(chars, angle, objs, to_read, baseline_v, keep_zones=(), bars=None):
    """Lines and x-ordered runs, with small markers re-homed by their body band.
    Each two-font overlap keeps its last painted character; covered characters leave run text.
    keep_zones (page px boxes; lane r5-line): inside a table or figure found on a first build of the page, the
    lane's O20/O21 changes are not applied (the inside of a float is out of the lane's scope); characters whose
    centre lies in a zone keep the earlier behaviour. Characters the lane's changes touched are marked "r5_line".
    """
    # horizontal drawn rules (reading frame): a short bar between a raised and a lowered tier is a fraction bar
    # (a stacked formula, O30): the lane's O21 stacking leaves such a place as it was
    hbars = []
    for o in (objs if bars is None else bars):   # bars: every thin drawn object, art included (lane r5-line)
        if o["kind"] != "rule": continue
        u0_, v0_, u1_, v1_ = to_read(*o["box_px"])
        if (u1_ - u0_) > (v1_ - v0_): hbars.append((u0_, v0_, u1_, v1_))
    def barred(up, down):
        """a drawn bar lies between the two groups of characters (one above it, one below it) and spans them"""
        if not hbars or not up or not down: return False
        a0 = min(c["u0"] for c in up + down); a1 = max(c["u1"] for c in up + down)
        top = max(c["v1"] for c in up); bottom = min(c["v0"] for c in down)
        lo_, hi_ = min(top, bottom), max(top, bottom)
        return any(b[0] <= a1 and b[2] >= a0 and lo_ - 0.5 * max(c["size"] for c in up + down) <= (b[1] + b[3]) / 2 <= hi_ + 0.5 * max(c["size"] for c in up + down)
                   for b in hbars)
    def kept(c):
        if not keep_zones: return False
        cx, cy = (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2
        return any(z[0] <= cx <= z[2] and z[1] <= cy <= z[3] for z in keep_zones)
    for c in chars:
        c["u0"], c["v0"], c["u1"], c["v1"] = to_read(c["x0"], c["y0"], c["x1"], c["y1"])
        c["vb"] = baseline_v(c)
        c["orig_u"] = c["origin"][0] if angle == 0 else (-c["origin"][1] if angle == 90 else c["origin"][1])
        c["adv_u1"] = (c["adv_x1"] if angle == 0 else (-c["adv_y1"] if angle == 90 else c["adv_y1"])) if c.get("adv_x1") is not None else None
    # Oversized paragraph initials must not enlarge the baseline tolerance. A cap
    # spans two or more normal rows to its right; a large heading has no such rows.
    # Keep the actual glyph box and attach it once, after ordinary line refinement.
    initials = []
    if angle == 0:
        for c in chars:
            if not c["text"].isalpha() or not c["text"].isupper(): continue
            near = [d for d in chars if d is not c and c["u1"] - 0.2 * c["size"] <= d["u0"] <= c["u1"] + 3 * c["size"]
                    and c["v0"] <= d["vb"] <= c["v1"] + 0.2 * c["size"] and d["text"].isalpha()]
            if len(near) < 6: continue
            normal = statistics.median(d["size"] for d in near)
            if c["size"] < PARAMS["dropcap_ratio"] * normal: continue
            # Large letters beside other large letters are a word/logo, not an
            # initial. Small nearby subtitle lines must not turn a logo into a cap.
            if any(d["size"] >= 0.75 * c["size"] and d["u0"] <= c["u1"] + normal
                   for d in near): continue
            normal_chars = [d for d in near if abs(d["size"] - normal) <= 0.2 * normal]
            if not normal_chars or max(d["vb"] for d in normal_chars) - min(d["vb"] for d in normal_chars) < 0.8 * normal: continue
            c["dropcap"] = True
            initials.append(c)
    ordinary = [c for c in chars if not c.get("dropcap")]
    # lines: cluster by baseline
    ordinary.sort(key=lambda c: (c["vb"], c["u0"]))
    lines = []
    for c in ordinary:
        placed = False
        for ln in lines[-3:]:   # recent lines only; chars arrive sorted by baseline
            # the line's size where c is: its letters within a few letter heights of c (a large title at the
            # left of the page does not widen the tolerance for smaller text at the right; measured N13 p1)
            lsize = ln["size"]
            if lsize > 1.5 * c["size"]:   # only where much larger text elsewhere on the line would set the tolerance
                reach = 3 * c["size"]
                near = [d["size"] for d in ln["chars"] if d["u0"] - c["u1"] <= reach and c["u0"] - d["u1"] <= reach]
                lsize = max(near) if near else c["size"]
            ref = max(lsize, c["size"])
            tol = PARAMS["line_tolerance_em"] * ref
            if c["size"] < PARAMS["superscript_em"] * lsize: tol = PARAMS["superscript_shift_em"] * lsize
            if abs(c["vb"] - ln["vb"]) <= tol:
                ln["chars"].append(c); placed = True
                ln["size"] = max(ln["size"], c["size"])   # the baseline stays where the line started: no drift
                break
        if not placed: lines.append({"vb": c["vb"], "size": c["size"], "chars": [c]})
    # Much larger type on a line (a display title beside a byline) widens its
    # baseline tolerance and can take letters of the next printed line, whose
    # x order then interleaves the two rows (AH04 p1 "Joaf nGLindhe"). Letters
    # of one size on one printed line share a baseline: a group of two or more
    # same-size letters whose baseline is more than line_tolerance_em of their
    # own size from the largest group of that size on this line belongs to
    # another line.
    # It joins the line at its own baseline, or starts one, before runs are
    # built; superscripts (smaller type) and single glyphs are untouched.
    moved = []
    for ln in lines:
        if len(ln["chars"]) < 3 or max(c["size"] for c in ln["chars"]) < 1.5 * min(c["size"] for c in ln["chars"]): continue
        classes = []
        for c in sorted(ln["chars"], key=lambda c: c["size"]):
            if classes and c["size"] <= 1.05 * classes[-1][0]["size"]: classes[-1].append(c)
            else: classes.append([c])
        for cls in classes:
            size = statistics.median(c["size"] for c in cls)
            groups = []
            for c in sorted(cls, key=lambda c: c["vb"]):
                if groups and c["vb"] - groups[-1][-1]["vb"] <= PARAMS["line_tolerance_em"] * size: groups[-1].append(c)
                else: groups.append([c])
            if len(groups) < 2: continue
            home = max(groups, key=lambda g: (len(g), -abs(statistics.median(c["vb"] for c in g) - ln["vb"])))
            for g in groups:
                if g is home or sum(c["text"].isalnum() for c in g) < 2: continue
                for c in g: ln["chars"].remove(c)
                moved.append((size, g))
    for size, g in moved:
        vb = statistics.median(c["vb"] for c in g)
        near = [ln for ln in lines if ln["chars"] and abs(ln["vb"] - vb) <= PARAMS["line_tolerance_em"] * size
                and any(abs(c["size"] - size) <= .05 * size for c in ln["chars"])]
        if near: min(near, key=lambda ln: abs(ln["vb"] - vb))["chars"].extend(g)
        else: lines.append({"vb": vb, "size": max(c["size"] for c in g), "chars": list(g)})
    if moved:
        lines = [ln for ln in lines if ln["chars"]]
        for ln in lines: ln["size"] = max(c["size"] for c in ln["chars"])
        lines.sort(key=lambda L: L["vb"])
    # refinement: a raised or lowered letter (superscript, exponent) sits beside the letters of its
    # own line and inside their vertical extent; if a letter touches no letter on its line but touches
    # one on another line whose box overlaps it vertically, it belongs there
    def touches(c, d):
        gap = max(d["u0"] - c["u1"], c["u0"] - d["u1"])
        vo = min(c["v1"], d["v1"]) - max(c["v0"], d["v0"])
        return gap <= 0.5 * c["size"] and vo >= 0.5 * (c["v1"] - c["v0"])
    # A touching letter must start by c's right edge plus half c's size.
    # Rebuild only the two affected line indexes when a letter moves.
    touch_index = {}
    def index_line(ln):
        ordered = sorted(ln["chars"], key=lambda d: d["u0"])
        touch_index[id(ln)] = ([d["u0"] for d in ordered], ordered)
    for ln in lines: index_line(ln)
    def touches_any(c, ln, skip_self=False):
        # the bounds carry a margin of 1e-6 px over touches()'s own test, which is written as a subtraction
        # and rounds differently: the filter passes a superset of the letters touches() accepts, and
        # touches() alone decides
        starts, ordered = touch_index[id(ln)]
        limit = c["u1"] + 0.5 * c["size"] + 1e-6
        for d in ordered[:bisect.bisect_right(starts, limit)]:
            if skip_self and d is c: continue
            if d["u1"] < c["u0"] - 0.5 * c["size"] - 1e-6: continue
            if touches(c, d): return True
        return False
    for ln in lines:
        for c in list(ln["chars"]):
            if touches_any(c, ln, True): continue
            for other in lines:
                if other is ln: continue
                if abs(c["vb"] - other["vb"]) <= PARAMS["superscript_shift_em"] * max(c["size"], other["size"]) and touches_any(c, other):
                    ln["chars"].remove(c); other["chars"].append(c)
                    index_line(ln); index_line(other)
                    break
    lines = [ln for ln in lines if ln["chars"]]
    for ln in lines: ln["vb"] = statistics.median(c["vb"] for c in ln["chars"]); ln["size"] = max(c["size"] for c in ln["chars"])
    lines.sort(key=lambda L: L["vb"])
    # raised or lowered pieces (superscripts, exponents) form a line of their own close to a real line
    # and never overlap it horizontally: fold such a line into its neighbour
    def u_overlap(a, b):   # substantial: more than a third of the narrower letter
        return any(min(ca["u1"], cb["u1"]) - max(ca["u0"], cb["u0"]) > 0.34 * min(ca["u1"] - ca["u0"], cb["u1"] - cb["u0"]) for ca in a["chars"] for cb in b["chars"])
    def script_tier_free(a, b):
        """O21 (lane r5-line): a lowered piece under a raised one (or a raised piece over a lowered one) on the same
        letter of b stacks with it; the other tier's small characters of b do not bar the fold. Only for a script
        piece: at most eight characters, no word of three letters, every character small (by superscript_em), on one
        side of b's baseline, and each of its characters under or over a small character of b of the other tier
        (measured: AT16 p2, a subscript under a superscript on one Greek letter left its word and went to the next
        sentence)."""
        cs_ = a["chars"]
        if any(kept(c) for c in cs_): return b
        if not cs_ or len(cs_) > 8 or re.search(r"[^\W\d_]{3,}", "".join(c["text"] for c in sorted(cs_, key=lambda c: c["u0"]))): return b
        # small against the letters of b (the median size of its letters and digits, not its largest character:
        # a short last line of a reference entry is in the size of the line it would join and stays a line)
        body = [d["size"] for d in b["chars"] if d["text"].isalnum()]
        ref = statistics.median(body) if body else b["size"]
        if not all(c["size"] < PARAMS["superscript_em"] * ref for c in cs_): return b
        side = statistics.median(c["vb"] for c in cs_) - b["vb"]
        if abs(side) <= 0.1 * b["size"]: return b
        other = [d for d in b["chars"] if d["size"] < PARAMS["superscript_em"] * b["size"] and (d["vb"] - b["vb"]) * side < 0 and abs(d["vb"] - b["vb"]) > 0.1 * b["size"]]
        if not other or not all(any(min(c["u1"], d["u1"]) > max(c["u0"], d["u0"]) for d in other) for c in cs_): return b
        if barred(*((other, cs_) if side > 0 else (cs_, other))): return b
        # a script overlaps the height of the line it joins and stands next to or over a full letter of it (memo
        # line-holdback-2: a short line of digits a full line spacing away, on its own baseline, is a line)
        full_b = [d for d in b["chars"] if id(d) not in {id(o) for o in other} and d["size"] >= PARAMS["superscript_em"] * ref]
        if not full_b: return b
        top_b, bot_b = min(d["v0"] for d in full_b), max(d["v1"] for d in full_b)
        if min(c["v1"] for c in cs_) <= top_b or max(c["v0"] for c in cs_) >= bot_b: return b
        if not all(any(max(d["u0"] - c["u1"], c["u0"] - d["u1"]) <= 0.5 * ref for d in full_b) for c in cs_): return b
        ids = {id(d) for d in other}
        for c in cs_: c["r5_line"] = True
        return {"chars": [d for d in b["chars"] if id(d) not in ids]}
    merged = True
    while merged:
        merged = False
        for i, ln in enumerate(lines):
            # the smaller line folds into the NEARER of its two neighbours, when close enough and not overlapping
            # a raised piece belongs to the line whose letters it touches (within half a letter height
            # along the line), not to the line whose baseline happens to be nearer
            def abut(a, b):
                return sum(1 for ca in a["chars"] if any(-0.5 * ca["size"] <= cb["u0"] - ca["u1"] <= 0.5 * ca["size"] or -0.5 * ca["size"] <= ca["u0"] - cb["u1"] <= 0.5 * ca["size"] for cb in b["chars"]))
            cands = []
            for j in (i - 1, i + 1):
                if 0 <= j < len(lines):
                    nb = lines[j]
                    if len(nb["chars"]) >= len(ln["chars"]) and abs(ln["vb"] - nb["vb"]) <= PARAMS["superscript_shift_em"] * max(ln["size"], nb["size"]) and not u_overlap(ln, script_tier_free(ln, nb)):
                        cands.append((-abut(ln, nb), abs(ln["vb"] - nb["vb"]), j))
            if cands and min(cands)[0] < 0:
                j = min(cands)[2]; nb = lines[j]
                nb["chars"].extend(ln["chars"]); nb["size"] = max(nb["size"], ln["size"])
                lines.pop(i); merged = True; break
    for c in initials:
        hosts = [(min(d["v0"] for d in ln["chars"] if d["u0"] >= c["u1"] - 1), ln)
                 for ln in lines if any(c["u1"] - 1 <= d["u0"] <= c["u1"] + c["size"]
                     and c["v0"] <= d["vb"] <= c["v1"] for d in ln["chars"])]
        if hosts:
            min(hosts, key=lambda pair: abs(pair[0] - c["v0"]))[1]["chars"].append(c)
        else:
            lines.append({"vb": c["vb"], "size": c["size"], "chars": [c]})
    lines = rehome_raised_markers(lines)
    if angle == 0: lines = split_display_face_lines(lines, objs, to_read)
    # vertical rules in reading frame, used to split runs that straddle one
    vrules = []   # (u position, v0, v1): a rule only separates letters on lines it actually crosses
    for o in objs:
        if o["kind"] != "rule": continue
        u0, v0, u1, v1 = to_read(*o["box_px"])
        if (u1 - u0) < (v1 - v0): vrules.append(((u0 + u1) / 2, v0, v1))
    # runs
    runs = []
    overprint_lines = set()
    for li, ln in enumerate(lines):
        cs = sorted(ln["chars"], key=lambda c: c["u0"])
        # The existing two-font horizontal-overlap test decides membership; source painting order decides visibility.
        def overlap(c, d):
            # lane r5-line: a script folded under or over the other tier (O21) shares no place with it when their
            # boxes do not meet in height (one above the other is not overprinting)
            if (c.get("r5_line") or d.get("r5_line")) and min(c["v1"], d["v1"]) <= max(c["v0"], d["v0"]): return False
            return c["font"] != d["font"] and min(c["u1"], d["u1"]) - max(c["u0"], d["u0"]) > PARAMS["overlap_share"] * min(c["u1"] - c["u0"], d["u1"] - d["u0"])
        pairs = []; base_layers = None
        if any(overlap(c, d) for c, d in zip(cs, cs[1:])):
            for i, c in enumerate(cs):
                for d in cs[i + 1:]:
                    if d["u0"] >= c["u1"]: break
                    if overlap(c, d): pairs.append((c, d))
        if pairs:
            overprint_lines.add(li)
            for c, d in pairs:
                earlier, later = sorted((c, d), key=lambda x: x["paint_order"])
                c["overprint"] = d["overprint"] = True
                # covered only where the two glyphs share the place: overlap beyond overlap_share of the wider one, on one
                # baseline, at like sizes (an italic letter's overhang onto a narrow neighbour covers nothing)
                wide = max(c["u1"] - c["u0"], d["u1"] - d["u0"]); sz = max(c["size"], d["size"])
                if not later.get("dropped_control") and min(c["v1"], d["v1"]) - max(c["v0"], d["v0"]) >= 0.5 * min(c["v1"] - c["v0"], d["v1"] - d["v0"]) and (min(c["u1"], d["u1"]) - max(c["u0"], d["u0"]) > PARAMS["overlap_share"] * wide and abs(c["vb"] - d["vb"]) <= PARAMS["line_tolerance_em"] * sz
                        and min(c["size"], d["size"]) >= PARAMS["superscript_em"] * sz):
                    earlier["covered"] = True
            cs = [c for c in cs if not c.get("covered")]
            # O20 (lane r5-line): the characters of a line are written in the order of their left edges, and a
            # character in another typeface keeps its place between its neighbours. A ligature, an italic overhang,
            # a sign or an accent in another font that overlaps a neighbour is one such character: one layer, in
            # left-edge order (measured: AP05 p3 a ligature in its own font left the word, "Modi ed ... fi"; AP22
            # p21 italic names and their roman commas set apart, "Pg Tf , and Td"). Only two texts drawn over
            # one another are read as separate layers, one per font (as before): a font whose characters on the line,
            # three or more and at least half of them, each overlap a character of another font (covered or not).
            hit = set(); count = collections.Counter(c["font"] for c in ln["chars"])
            for c, d in pairs: hit.update((id(c), id(d)))
            overlaid = [f for f in count if count[f] >= 3 and sum(id(c) in hit for c in ln["chars"] if c["font"] == f) >= max(3, 0.5 * count[f])]
            if overlaid or any(kept(c) for c in cs):
                byfont = collections.OrderedDict()
                for c in cs: byfont.setdefault(c["font"], []).append(c)
                layers = list(byfont.values())
            else:
                layers = [cs]
                for c in cs: c["r5_line"] = True
                if not any(c.get("marker_glue") for c in cs):
                    byfont = collections.OrderedDict()
                    for c in cs: byfont.setdefault(c["font"], []).append(c)
                    base_layers = list(byfont.values())
            # A repaired marker must stay between its neighbours even when an
            # unrelated font overhang elsewhere on this line was flagged.
            if any(c.get("marker_glue") for c in cs): layers = [cs]
        else:
            layers = [cs]
        def split(cs):
            # the line's own word space: the median of its small gaps (between a tenth and three quarters of a letter height)
            small = [b["u0"] - a["u1"] for a, b in zip(cs, cs[1:]) if PARAMS["wordspace_min_em"] * ln["size"] <= b["u0"] - a["u1"] < PARAMS["wordspace_max_em"] * ln["size"]]
            wordspace = statistics.median(small) if small else None
            out = []; cur = [cs[0]]
            for prev, c in zip(cs, cs[1:]):
                gap = c["u0"] - prev["u1"]
                crosses = any(prev["u1"] < vr < c["u0"] and rv0 <= ln["vb"] <= rv1 + ln["size"] for vr, rv0, rv1 in vrules)
                wide = wordspace is not None and gap > PARAMS["run_gap_wordspaces"] * wordspace
                if gap > PARAMS["run_gap_em"] * ln["size"] or wide or crosses:
                    out.append(cur); cur = [c]
                else:
                    cur.append(c)
            out.append(cur)
            return out
        if base_layers is not None:
            # lane r5-line: the copy's note counts the runs that hold overprinted characters; where this line is now one
            # layer, each run the per-font layers would have made with an overprinted character is recorded on its
            # characters, so the copy can count those runs as before (the runs are fewer, the places the same)
            for bcs in base_layers:
                for r in split(bcs):
                    if any(c.get("overprint") for c in r):
                        tag = (li, id(r[0]))
                        for c in r: c["op_base"] = tag
            for c in ln["chars"]: c["op_line"] = True
        for cs in layers:
            if not any(kept(c) for c in cs):
                before = [id(c) for c in cs]
                cs = stacked_script_order(cs, ln["size"], barred)
                if [id(c) for c in cs] != before:
                    for c in cs: c["r5_line"] = True
            for r in split(cs): runs.append((li, r))
    return lines, runs, overprint_lines

def op_layers(ids, chars):
    """lane r5-line: the character ids of each per-font run (with an overprinted character) inside these characters"""
    groups = collections.OrderedDict()
    for i in ids:
        tag = chars[i].get("op_base")
        if tag is not None: groups.setdefault(tag, []).append(i)
    return list(groups.values())


def regions_beside(a, b):
    """Different columns share less than one fifth of the narrower x extent."""
    width = min(a[2] - a[0], b[2] - b[0])
    return width > 0 and min(a[2], b[2]) - max(a[0], b[0]) < 0.2 * width


def poppler_regions(pdf_path, page_no, box, elements, chars=()):
    """Rule 1: Poppler layout blocks, in the page's dpi frame, with drawn regions atomic.

    Poppler supplies candidate geometry; corroborated boundaries constrain rule 2.
    The reading layer remains the source of every character.
    A missing executable, unsuccessful command, malformed output or empty page falls back
    to the original single region. Control glyphs in Poppler's XHTML are removed before
    parsing because they can be legal PDF text but illegal XML characters.
    Drawn grids use the existing joined-rule/spanning-fill detector, before any split.
    A panel is atomic at page level and retains Poppler candidates as children.
    Its children undergo the same support test, but remain explicitly deferred until
    rule 7 supports atomic parent ordering. Activating them now interleaves a panel
    with surrounding body columns (measured on G06 p2 and G04 p16).
    """
    import xml.etree.ElementTree as ET
    fallback = [{"id": "region:1", "box_px": list(box), "source": "poppler", "fallback": True, "promoted": True}]
    try:
        result = subprocess.run(["pdftotext", "-f", str(page_no), "-l", str(page_no),
                                 "-bbox-layout", str(pdf_path), "-"], capture_output=True, timeout=30)
        if result.returncode: return fallback
        xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", result.stdout.decode("utf-8"))
        root = ET.fromstring(xml)
        doc = sc_doc(pdf_path); page = doc.pages[page_no - 1]
        x0, y0, x1, y1 = page.mediabox
        _, height, _ = doc.page_size(page_no)
        def page_point(x, y):
            # Poppler uses the rotated MediaBox origin. The reading layer retains
            # PDF user coordinates, with y flipped against its CropBox height.
            if page.rotate % 360 == 90: u, v = x0 + y, y0 + x
            elif page.rotate % 360 == 180: u, v = x1 - x, y0 + y
            elif page.rotate % 360 == 270: u, v = x1 - y, y1 - x
            else: u, v = x0 + x, y1 - y
            return px(u), px(height - v)
        boxes = []
        for block in root.iter():
            if block.tag.rsplit("}", 1)[-1] != "block": continue
            a, c, z, d = [float(block.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax")]
            points = [page_point(x, y) for x, y in ((a, c), (a, d), (z, c), (z, d))]
            b = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
            if not all(math.isfinite(v) for v in b) or b[2] <= b[0] or b[3] <= b[1]: continue
            if min(b[2], box[2]) <= max(b[0], box[0]) or min(b[3], box[3]) <= max(b[1], box[1]): continue
            line_boxes = []
            for c in block:
                if c.tag.rsplit("}", 1)[-1] != "line" or not any(t.isalnum() for t in "".join(c.itertext())): continue
                la, lc, lz, ld = [float(c.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax")]
                pts = [page_point(x, y) for x, y in ((la, lc), (la, ld), (lz, lc), (lz, ld))]
                line_boxes.append([min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)])
            boxes.append({"box_px": b, "source": "poppler", "lines": len(line_boxes), "line_boxes": line_boxes,
                          "poppler_blocks": 1})
        if not boxes: return fallback
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.TimeoutExpired):
        return fallback
    def overlaps(a, b):
        return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])
    texts = [e for e in elements if e["kind"] == "text"]
    em = statistics.median(e["run_size_px"] for e in texts) if texts else 0
    initial_blocks = larger_boxes(elements)
    grids = tables_from_grid(elements, initial_blocks)
    # Caption-anchored ruled tables also have internal valleys. Preserve the
    # existing detector's cells before using any valley as a prose boundary.
    grids += tables_from_caption(elements, initial_blocks, grids, chars)
    atomic = [{"box_px": t["box_px"], "source": "grid"} for t in grids]
    for e in elements:
        if e["kind"] not in ("fill", "image"): continue
        b = e["box_px"]
        if min(b[2] - b[0], b[3] - b[1]) < 2 * em: continue
        # A drawn object frames text only when the text stays inside it (rule 1, part 1): a Poppler block of
        # column_min_lines or more lines each running past the object's edge by more than a letter height
        # is a text column the object lies under, not text the object holds. The object is a background
        # (never a panel, a container or a figure); the columns it covered keep their own regions.
        # A curve never frames text (part 2): a decorative swoosh is one filled curve
        # (measured: AN08 p1, a grey curve under three body columns, 931x806 px, read as one panel).
        if not boxlike(e, em):
            e.update(kind="background", basis="a free-form drawn curve of page scale: never a frame for text"); continue
        overrun = frames_overrun(b, boxes, em)
        if overrun:
            e.update(kind="background", basis=f"a text block of {overrun} lines runs past its edge: not a frame for text"); continue
        inside = [t for t in texts if b[0] <= (t["box_px"][0] + t["box_px"][2]) / 2 <= b[2]
                  and b[1] <= (t["box_px"][1] + t["box_px"][3]) / 2 <= b[3]]
        # Outlined lettering is text geometry too, even when Poppler has no
        # words inside a graphic. Its backing must not inherit distant columns.
        outlines = [o for o in elements if o["kind"] == "outline"
                    and b[0] <= o["box_px"][0] and o["box_px"][2] <= b[2]
                    and b[1] <= o["box_px"][1] and o["box_px"][3] <= b[3]]
        rows = {round(o["box_px"][1] / max(em, 1)) for o in outlines}
        if len({t["line"] for t in inside}) >= 2 or len(rows) >= 2:
            atomic.append({"box_px": list(b), "source": "panel"})
    candidates = list(boxes)
    children = []
    for region in atomic:
        b = region["box_px"]
        hits = [r for r in boxes if overlaps(b, r["box_px"])]
        if not hits:
            boxes.append(region)
            continue
        bs = [b] + [r["box_px"] for r in hits]
        region["box_px"] = [min(t[0] for t in bs), min(t[1] for t in bs), max(t[2] for t in bs), max(t[3] for t in bs)]
        region["poppler_blocks"] = sum(r.get("poppler_blocks", 0) for r in hits)
        if region["source"] == "panel":
            children.append((region, [dict(r) for r in candidates if overlaps(b, r["box_px"])]))
        boxes = [r for r in boxes if r not in hits] + [region]
    for i, r in enumerate(boxes): r["id"] = f"region:{i+1}"
    for parent, hits in children:
        if parent not in boxes: continue
        for i, r in enumerate(hits):
            r.update(id=parent["id"] + f":{i+1}", parent=parent["id"])
            boxes.append(r)
    separated = region_separations(boxes, elements)
    promoted = set().union(*separated) if separated else set()
    for r in boxes:
        r["supported"] = r["id"] in promoted
        r["promoted"] = not r.get("parent") and (r["supported"] or r["source"] in ("grid", "panel"))
        if r.get("parent"):
            r["deferred"] = "panel child ordering requires an atomic parent in rule 7"
    return boxes


def frames_overrun(box, poppler_blocks, em):
    """Rule 1, part 1: the number of lines running past the drawn box in the first Poppler block that lies on
    it: at least half of the block's lines are centred inside the box (the object lies under that text) and
    at least column_min_lines of them run past the box by more than one letter height; 0 otherwise. A
    page-wide Poppler block that merely touches a figure at its corner (a few lettering lines inside, the
    body columns outside) is not text the object lies under (measured: AI07 p2, a 93-line block over a
    figure holding 13 lettering lines; AH06 pp4-6; AN08 p1's columns lie 61-100% on the swoosh)."""
    for r in poppler_blocks:
        if r.get("source") != "poppler" or r.get("lines", 0) < PARAMS["column_min_lines"]: continue
        rb = r["box_px"]
        if min(rb[2], box[2]) <= max(rb[0], box[0]) or min(rb[3], box[3]) <= max(rb[1], box[1]): continue
        lines = r.get("line_boxes", [])
        inside = [lb for lb in lines if box[0] <= (lb[0] + lb[2]) / 2 <= box[2] and box[1] <= (lb[1] + lb[3]) / 2 <= box[3]]
        if not lines or len(inside) < 0.5 * len(lines): continue
        past = [lb for lb in lines if lb[0] < box[0] - em or lb[2] > box[2] + em or lb[1] < box[1] - em or lb[3] > box[3] + em]
        if len(past) >= PARAMS["column_min_lines"]: return len(past)
    return 0


def region_separations(regions, elements):
    """Corroborate a side-by-side layout with nearby multi-line Poppler blocks.

    Poppler also emits separate inline blocks at font changes and superscripts.
    Those are not columns. Each side needs a nearby block of at least column_min_lines
    lines spanning its width and remaining beside the other side. The witnesses
    themselves must be co-extensive within column_min_lines em. Empty/control-only
    lines do not witness a column (N13 p3's detached bullet markers). Atomic grids
    and panels are protected; deferred child candidates impose no constraint.
    """
    regions = [r for r in regions if not r.get("deferred")]
    sizes = [e["run_size_px"] for e in elements if e["kind"] == "text"]
    em = statistics.median(sizes) if sizes else 0
    witnesses = [r for r in regions if r.get("lines", 0) >= PARAMS["column_min_lines"]]
    def near(a, b):
        return max(a[1] - b[3], b[1] - a[3]) <= PARAMS["column_min_lines"] * em
    def support(a, b):
        A, B = a["box_px"], b["box_px"]
        return [w for w in witnesses if w.get("parent") == a.get("parent")
                and min(A[2], w["box_px"][2]) - max(A[0], w["box_px"][0]) >= 0.8 * (A[2] - A[0])
                and near(A, w["box_px"]) and regions_beside(w["box_px"], B)]
    return {frozenset((a["id"], b["id"])) for i, a in enumerate(regions) for b in regions[i+1:]
            if a.get("parent") == b.get("parent") and regions_beside(a["box_px"], b["box_px"])
            and any(near(u["box_px"], v["box_px"]) and regions_beside(u["box_px"], v["box_px"])
                    for u in support(a, b) for v in support(b, a))}


def region_at(box, regions):
    """The region containing a box centre; nearest box handles font-box discrepancies."""
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    def distance(r):
        b = r["box_px"]
        return (max(b[0] - x, 0, x - b[2]) ** 2 + max(b[1] - y, 0, y - b[3]) ** 2,
                (b[2] - b[0]) * (b[3] - b[1]))
    # Deferred panel children retain their geometry without changing ownership.
    candidates = [r for r in regions if not r.get("deferred")]
    return min(candidates, key=distance)["id"]


def larger_boxes(elements, regions=()):
    """Rule 2: stack overlapping elements, except across a numbered heading's size boundary.
    A numbered heading at heading_size_ratio or more of the character-weighted median upright
    text size first joins same-size runs to its right on its line, across at most flow_gap_em
    letter heights (including a separator), and directly stacked same-size continuation lines.
    Continuations overlap the heading sideways and never start another numbered heading.
    Numbered headings starting beside each other on one baseline own separate
    columns: continuation runs cannot cross the next heading's left edge. Region
    boundaries constrain heading growth itself, not only the final block union.
    Section-number components have at most three digits; a four-digit year at a prose line
    start is not a section label. A candidate directly continuing same-size non-heading text
    is prose too: a page dominated by smaller captions must not turn body quantities into headings.
    The heading then forms its own block; its number cannot attach to a wrapped last word
    and drag that word ahead of the first line. Text inside a fill or image is left to the
    ordinary containment rule (table cells and figure lettering). A detached paragraph
    initial uses its receiving line's size for stacking. A corroborated page-level
    boundary vetoes unions between entire components, including heading and fill/image
    containment unions; an unconstrained intermediate element cannot reconnect columns.
    A figure caption set in its own shaded box (a fill or image holding two or more lines, a
    Figure label topmost) ends at the box's edge: text outside it never stacks onto text inside it. A text-area
    background (rule 1, kind background) is not an element here at all."""
    def overlap(a, b, axis):
        i, j = (0, 2) if axis == 0 else (1, 3)
        return min(a[j], b[j]) - max(a[i], b[i])
    els = [e for e in elements if e["kind"] in ("text", "outline", "image", "fill", "rule")]
    n = len(els); parent = list(range(n))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    separated = region_separations(regions, elements)
    memberships = [{e.get("region")} for e in els]
    # a page-sized fill or image is a background (a scan under an OCR text layer, a coloured page), not a
    # container: it never joins the text it covers (measured: I01, Pediatric Dentistry 2017, every page one image)
    H = [min(e["box_px"][0] for e in els), min(e["box_px"][1] for e in els), max(e["box_px"][2] for e in els), max(e["box_px"][3] for e in els)] if els else [0, 0, 1, 1]
    def background(o):
        b = o["box_px"]
        return o["kind"] in ("fill", "image") and (b[2] - b[0]) >= PARAMS["background_share"] * (H[2] - H[0]) and (b[3] - b[1]) >= PARAMS["background_share"] * (H[3] - H[1])
    def union(i, j):
        a, b = find(i), find(j)
        if a == b: return
        # Test entire components: a fill or spanning run must not provide an
        # indirect path between two incompatible column regions.
        if any(frozenset((u, v)) in separated for u in memberships[a] for v in memberships[b]): return
        parent[a] = b; memberships[b].update(memberships[a])
    def size(e):
        if e["kind"] == "text": return e["size_px"]
        b = e["box_px"]; return min(b[3] - b[1], b[2] - b[0]) or PARAMS["zero_size_px"]
    texts = [(i, e) for i, e in enumerate(els) if e["kind"] == "text" and e["angle"] == 0]
    sizes = [e["run_size_px"] for _, e in texts for _ in e["text"].strip()]
    body = statistics.median(sizes) if sizes else 0
    numbered = re.compile(r"^\d{1,3}(?:\.\d{1,3})*\.?(?:$|\s+(?:[A-Z]|\|))")
    seeds = {i for i, e in texts if e["run_size_px"] >= PARAMS["heading_size_ratio"] * body and numbered.match(e["text"].strip())}
    heading = {}
    for i, e in texts:
        if i not in seeds or i in heading: continue
        A = e["box_px"]; em = e["run_size_px"]
        if any(o["kind"] in ("fill", "image") and not background(o) and o["box_px"][0] <= A[0] and A[2] <= o["box_px"][2]
               and o["box_px"][1] <= A[1] and A[3] <= o["box_px"][3] for o in els): continue
        group = {i}; box = list(A); lines = {e["line"]}
        next_heading = min((s["box_px"][0] for k, s in texts if k in seeds
                            and s["line"] == e["line"] and s["box_px"][0] > A[0]), default=float("inf"))
        grew = True
        while grew:
            grew = False
            for j, other in texts:
                if j in group or j in heading or j in seeds: continue
                if abs(other["run_size_px"] - em) > PARAMS["body_size_tolerance"] * em: continue
                B = other["box_px"]
                if B[0] >= next_heading: continue
                if any(frozenset((els[k].get("region"), other.get("region"))) in separated for k in group): continue
                # Words beside another number start that heading, even when it is stacked
                # close enough to look like a continuation of this one.
                if any(k != i and s["line"] == other["line"] and 0 <= B[0] - s["box_px"][2] <= PARAMS["flow_gap_em"] * em for k, s in texts if k in seeds): continue
                same = other["line"] in lines and 0 <= B[0] - box[2] <= PARAMS["flow_gap_em"] * em
                under = other["line"] not in lines and 0 <= B[1] - box[3] <= PARAMS["stack_gap_em"] * em and overlap(box, B, 0) >= PARAMS["side_overlap_px"]
                if same or under:
                    group.add(j); lines.add(other["line"])
                    box = [min(box[0], B[0]), min(box[1], B[1]), max(box[2], B[2]), max(box[3], B[3])]; grew = True
        if not any(re.search(r"[A-Za-z]{3,}", els[j]["text"]) for j in group): continue
        for j in group: heading[j] = i
    changed = True
    while changed:
        changed = False
        for i in sorted(set(heading.values())):
            e = els[i]; A = e["box_px"]; em = e["run_size_px"]
            if any(j not in heading and abs(other["run_size_px"] - em) <= PARAMS["body_size_tolerance"] * em
                   and overlap(A, other["box_px"], 0) >= PARAMS["side_overlap_px"]
                   and 0 <= A[1] - other["box_px"][3] <= PARAMS["stack_gap_em"] * em for j, other in texts):
                heading = {j: h for j, h in heading.items() if h != i}; changed = True
    for j, i in heading.items(): union(i, j)
    # A caption set in its own shaded box ends at the box's edge: text outside the box never stacks onto
    # the caption inside it, however tight the leading (the float accounting rule: an object crossing a
    # region's edge is flagged, never absorbed; measured: AH06, body text directly under each tinted
    # caption box became caption text). A caption box holds two or more lines, an upright Figure label topmost.
    # held by centre: a last line's descenders may cross the box's lower edge (measured: AA04 p9)
    def held(F, e): return F[0] <= (e["box_px"][0] + e["box_px"][2]) / 2 <= F[2] and F[1] <= (e["box_px"][1] + e["box_px"][3]) / 2 <= F[3]
    caption_frames = []
    for o in els:
        if o["kind"] not in ("fill", "image") or background(o) or not boxlike(o, body): continue
        inner = [e for _, e in texts if held(o["box_px"], e)]
        # the box holds the caption's lines, not a single row's strip (O03: one fill under every
        # manuscript row; a label-row strip is no caption box)
        top = min(inner, key=lambda e: (e["box_px"][1], e["box_px"][0])) if inner else None
        if top and len({e["line"] for e in inner}) >= 2 and is_caption_run(top) and not re.sub(r"\s+", "", top["text"]).lower().startswith("table"):
            caption_frames.append(o["box_px"])   # figure captions only: a table under its caption box stays as before
    def frames(e): return frozenset(k for k, F in enumerate(caption_frames) if held(F, e))
    for i, a in enumerate(els):
        A = a["box_px"]
        for j in range(i + 1, n):
            b = els[j]; B = b["box_px"]
            if (i in heading or j in heading) and heading.get(i) != heading.get(j): continue
            if a["kind"] == "rule" and b["kind"] == "rule": continue
            if (a["kind"] in ("fill", "image") and not background(a) and boxlike(a, body) and B[0] >= A[0] - 1 and B[2] <= A[2] + 1 and B[1] >= A[1] - 1 and B[3] <= A[3] + 1) or \
               (b["kind"] in ("fill", "image") and not background(b) and boxlike(b, body) and A[0] >= B[0] - 1 and A[2] <= B[2] + 1 and A[1] >= B[1] - 1 and A[3] <= B[3] + 1):
                union(i, j); continue
            if a["kind"] in ("rule", "fill", "image") or b["kind"] in ("rule", "fill", "image"): continue
            if overlap(A, B, 0) >= PARAMS["side_overlap_px"]:
                gap = max(B[1] - A[3], A[1] - B[3])
                if gap <= PARAMS["stack_gap_em"] * min(size(a), size(b)) and (not caption_frames or frames(a) == frames(b)): union(i, j)
    groups = {}
    for i in range(n): groups.setdefault(find(i), []).append(i)
    boxes = []
    for members in groups.values():
        ms = [els[i] for i in members]
        if all(m["kind"] == "rule" for m in ms): continue
        hull = [min(m["box_px"][0] for m in ms), min(m["box_px"][1] for m in ms), max(m["box_px"][2] for m in ms), max(m["box_px"][3] for m in ms)]
        boxes.append({"box_px": hull, "members": [m["id"] for m in ms], "kinds": sorted({m["kind"] for m in ms}),
                      "text_lines": len({m["line"] for m in ms if m["kind"] == "text"}),
                      "text": " ".join(m["text"] for m in ms if m["kind"] == "text")[:80]})
    boxes.sort(key=lambda b: (b["box_px"][1], b["box_px"][0]))
    for i, b in enumerate(boxes): b["id"] = f"block:{i+1}"
    # A baseline is not a reading line across two independent headings. Keep
    # the original baseline ids for table geometry, and record the column-local
    # lines explicitly. The block's run membership is the reading-line boundary.
    heading_rows = collections.defaultdict(list)
    for b in boxes:
        rows = collections.defaultdict(list)
        for i, e in texts:
            if i in heading and e["id"] in b["members"]: rows[e["line"]].append(e["id"])
        for line, members in rows.items(): heading_rows[line].append((b, members))
    for line, parts in heading_rows.items():
        if len(parts) < 2: continue
        for b, members in parts:
            b.setdefault("line_splits", []).append(dict(source_line=line, members=members,
                parts=[part["id"] for part, _ in parts], why="separate heading columns on one baseline"))
    return boxes

import re
CAPTION_LABEL = re.compile(r"^(Fig\.?|Figure|Table)(?:\d+[a-z]?|[IVXLCDM]+)([.:|]|$)", re.I)
CAPTION_LABEL_CAPS = re.compile(r"^(FIG\.?|FIGURE|TABLE)\d+")
LABEL_LEAD = re.compile(r"^(Fig\.?|Figure|Table)\d+(?=[A-Za-z])", re.I)
FIGURE_DASH_LEAD = re.compile(r"^(Fig\.?|Figure)\d+[a-z]?(?=[\u2013\u2014][A-Za-z])", re.I)
def label_in_own_font(cs):
    """Rule 1: the run's characters cs open with a caption label ("Table 1", "Fig. 2") set in a font of its
    own: the character after the number is set in a font none of the label's characters use. A figure label
    may instead be joined to its words by an en or em dash; then the dash or the letter after it carries the
    font change (measured: AP08, "Figure 1—Study flow chart", the label in ArialNarrow-Bold, the dash and the
    words in ArialNarrow; without it rule 4 found no caption and the caption was read into the body's
    sentences). A dash before a digit is a range ("Figure 1–3"), never a label. A dash-joined Table label is
    left to the existing rules (the copier reads it with its own table-label rule): taking it here
    assembled the caption's second line into the grid as a header row (measured: AM03 Table 1). A figure
    label may carry a sub-figure letter, as CAPTION_LABEL accepts ("Figure 4b—"); the letter is part of the
    label and is set in the label's face, so the font change is looked for after it, at the dash: each lead
    (LABEL_LEAD, FIGURE_DASH_LEAD) is tried on its own and either one witnessing the font change suffices
    (without it the letter, in the label's bold, hid the change and the caption was read into the body)."""
    text = "".join(c["text"] for c in cs)
    for lead in (LABEL_LEAD.match(text), FIGURE_DASH_LEAD.match(text)):
        if not lead or lead.end() >= len(cs): continue
        fonts = {c.get("font") for c in cs[:lead.end()]}
        after = cs[lead.end():lead.end() + (2 if cs[lead.end()]["text"] in ("\u2013", "\u2014") else 1)]
        if any(c.get("font") not in fonts for c in after): return True
    return False
def is_caption_label(text, label_font=False):
    """Spaces removed first, so a letter-spaced label ("T A B L E 1") matches too. A body reference
    ("Table 1 presents") does not: the number must end the run or be followed by . or :. A label
    word in capitals ("TABLE 1") may be followed by the caption's own text in the same run (a
    journal that sets the label and caption with only a word space between them); running text
    writes "Table 1", not "TABLE 1". A label set in a font of its own ahead of the caption's words (a bold
    "Table 1" or "Fig. 1") needs no . or : either, and a figure label so set may be joined to the words by
    an en or em dash ("Figure 1—Study"); rule 1 marks such a run label_font (label_in_own_font). Running text that
    mentions a table sets "Table 1" in the sentence's own font. Punctuated Roman
    numerals follow the same label rule and retain their printed numbering."""
    s = re.sub(r"\s+", "", text)
    return bool(CAPTION_LABEL.match(s) or CAPTION_LABEL_CAPS.match(s) or (label_font and (LABEL_LEAD.match(s) or FIGURE_DASH_LEAD.match(s))))
def is_caption_run(e):
    """a text run that opens with a caption label; a run marked label_font by rule 1 has its label set in
    a font of its own (a bold "Table 1" before the caption's words), and needs no . or : after the number.
    Rule 3 can also witness a split label above an aligned list, in table_caption_label."""
    return is_caption_label(e.get("table_caption_label", e["text"]), e.get("label_font", False))

def joined_rules(objs):
    """Rule 3: thin rule pieces drawn end to end on one line (a table ruled cell edge by cell edge)
    joined into whole lines; each joined line names its pieces. Pieces of one horizontal line share
    their centre height within the rule thickness, and the next piece starts within rule_join_pt of
    where the last one ended; likewise for vertical lines."""
    thin = px(PARAMS["rule_max_pt"]); gap = px(PARAMS["rule_join_pt"]); out = []
    for horiz in (True, False):
        segs = []
        for o in objs:
            if o["kind"] != "rule": continue
            x0, y0, x1, y1 = o["box_px"]
            if horiz and (y1 - y0) <= thin and (x1 - x0) > (y1 - y0): segs.append(((y0 + y1) / 2, x0, x1, o))
            if not horiz and (x1 - x0) <= thin and (y1 - y0) > (x1 - x0): segs.append(((x0 + x1) / 2, y0, y1, o))
        segs.sort(key=lambda s: (round(s[0] / thin), s[1]))
        chain = []
        def flush():
            if len(chain) >= 2:
                bs = [c[3]["box_px"] for c in chain]
                out.append({"id": "join:" + chain[0][3]["id"], "kind": "rule", "parts": [c[3]["id"] for c in chain],
                            "box_px": [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]})
        for sg in segs:
            if chain and abs(sg[0] - chain[-1][0]) <= thin and sg[1] <= max(c[2] for c in chain) + gap: chain.append(sg)
            else: flush(); chain = [sg]
        flush()
    return out

def prose_column_blocks(texts, blocks, body):
    """Rule 3: the rule-2 blocks that are columns of body prose (T7.1, body text by document statistics):
    column_min_lines or more lines at the body size whose width is the page's modal body line width (the most
    common width of body-size runs in blocks of that many lines, in half-letter-height bins, within half a
    letter height), with 25 or more words and sentence punctuation. Cells of a table never fill the body
    column's width line after line; a wrapped long-text cell column is narrower or wider than the modal line
    (measured: AM02 pp6-7, two body columns under and over a Table caption read as 2-track tables)."""
    block_of = {m: b for b in blocks for m in b["members"]}
    tall = {b["id"] for b in blocks if b.get("text_lines", 0) >= PARAMS["column_min_lines"]}
    bin_ = 0.5 * body
    widths = [round((e["box_px"][2] - e["box_px"][0]) / bin_) for e in texts
              if e["run_size_px"] >= 0.97 * body and block_of.get(e["id"], {}).get("id") in tall]
    if not widths: return set()
    modal = collections.Counter(widths).most_common(1)[0][0] * bin_
    out = set()
    for b in blocks:
        if b["id"] not in tall: continue
        es = [e for e in texts if block_of.get(e["id"]) is b]
        full = [e for e in es if e["run_size_px"] >= 0.97 * body and abs((e["box_px"][2] - e["box_px"][0]) - modal) <= bin_]
        if len({e["line"] for e in full}) < PARAMS["column_min_lines"]: continue
        text = " ".join(e["text"] for e in es)
        if len(re.findall(r"[A-Za-z]{2,}", text)) >= 25 and re.search(r"[.!?](?:\s|$)", text): out.add(b["id"])
    return out


def run_face(e):
    """The font that sets most of a run's characters, without its subset prefix."""
    spans = e.get("font_spans") or []
    f = max(spans, key=lambda sp: sp.get("end", 0) - sp.get("start", 0)).get("font") if spans else e.get("font")
    if isinstance(f, (list, tuple)): f = f[0] if f else None
    return re.sub(r"^[A-Z]{6}\+", "", f) if isinstance(f, str) else None


def paper_column_pattern(own_by_page, body):
    """R3 (lane stream): the paper's column pattern when its column extents do not recur at fixed positions.
    Each page's own columns (an extent holding two others is a spanning block, left out) form a pattern of
    widths and gutters relative to its first column; two pages share a pattern when every relative edge agrees
    within a letter height. The pattern of most pages (two or more, the title page included) is the paper's:
    alternate pages mirror their margins, so it recurs at a per-page offset (measured: AP18, pages 1 and 3 at
    x 131, page 4 at x 150, widths within 17 px of each other at a 17.5 px body; page 5's references, set
    smaller than the body, gave no column of their own and were read row by row). Returns
    {"pattern": [(x0, x1)...], "pages": {page: offset}, "patterned": pages with a pattern of their own} or None."""
    patterned = {}
    for n, cs in own_by_page.items():
        cs = sorted(cs)
        cs = [c for c in cs if sum(1 for d in cs if d is not c and c[0] - body <= d[0] and d[1] <= c[1] + body) < 2]
        if len(cs) >= 2: patterned[n] = ([(c[0] - cs[0][0], c[1] - cs[0][0]) for c in cs], cs[0][0])
    def same(a, b): return len(a) == len(b) and all(abs(x[0] - y[0]) <= body and abs(x[1] - y[1]) <= body for x, y in zip(a, b))
    groups = []
    for n, (pat, off) in sorted(patterned.items()):
        g = next((g for g in groups if same(g["pattern"], pat)), None)
        if g: g["pages"][n] = off
        else: groups.append({"pattern": pat, "pages": {n: off}})
    groups = [g for g in groups if len(g["pages"]) >= 2]
    if not groups: return None
    return dict(max(groups, key=lambda g: (len(g["pages"]), len(g["pattern"]))), patterned=set(patterned))


def place_column_pattern(pattern, page_no, rules, blocks, body):
    """R3 (lane stream): the paper's column pattern on a page without columns of its own, at the offset of the
    nearest patterned page of the same parity (else the nearest patterned page). Drawn vertical rules (thinner
    than rule_max_pt, at least column_min_lines letter heights tall, between the first and last column) are
    gutter witnesses: each must fall in a gutter; no block (boxes of blocks of column_min_lines lines or more)
    may cross a gutter by more than a letter height on both sides. Otherwise the page gets no pattern ([])."""
    if not pattern or page_no in pattern["patterned"]: return []
    pages = pattern["pages"]
    same = [n for n in pages if n % 2 == page_no % 2]
    n = min(same or pages, key=lambda n: (abs(n - page_no), n))
    cols = [[pages[n] + a, pages[n] + b] for a, b in pattern["pattern"]]
    gutters = [(a[1], b[0]) for a, b in zip(cols, cols[1:])]
    for r in rules:
        if r[2] - r[0] > px(PARAMS["rule_max_pt"]) or r[3] - r[1] < PARAMS["column_min_lines"] * body: continue
        x = (r[0] + r[2]) / 2
        if cols[0][0] < x < cols[-1][1] and not any(g0 <= x <= g1 for g0, g1 in gutters): return []
    for b in blocks:
        if any(b[0] < g0 - body and b[2] > g1 + body for g0, g1 in gutters): return []
    return cols


def main_text_runs(texts, blocks):
    """R1 (lane stream): the page's main-text runs. Body evidence is the page's columns of body prose
    (prose_column_blocks); without one the page has no main-text evidence and nothing is returned. Body face:
    the face setting most characters of those columns; body size: their median size; pitch: the median step
    between successive line centres inside them. Every run of such a column is main text, and so is any upright
    run in the body face within 3 % of the body size whose line lies 0.85 to 1.2 pitches from another such
    run's line overlapping it by half the narrower width (a body line cut off its paragraph: DIAGNOSIS-AP E5,
    AP22 p20, two body lines under pen marks beside a figure caption)."""
    up = [e for e in texts if e.get("angle", 0) == 0]
    if not up or not blocks: return set()
    em = statistics.median(e["run_size_px"] for e in up)
    pids = prose_column_blocks(up, blocks, em)
    prose = {b["id"] for b in blocks if b["id"] in pids and b["box_px"][2] - b["box_px"][0] >= 12 * em}
    if not prose: return set()
    in_prose = {m for b in blocks if b["id"] in prose for m in b["members"]}
    col = [e for e in up if e["id"] in in_prose]
    faces = collections.Counter()
    for e in col: faces[run_face(e)] += len(e["text"])
    face = faces.most_common(1)[0][0]
    size = statistics.median(e["size_px"] for e in col if run_face(e) == face)
    steps = []
    for b in blocks:
        if b["id"] not in prose: continue
        cs = sorted({round((e["box_px"][1] + e["box_px"][3]) / 2, 1) for e in col if e["id"] in b["members"]})
        steps += [y - x for x, y in zip(cs, cs[1:]) if y - x > 0.5 * size]
    if not steps: return in_prose
    pitch = statistics.median(steps)
    cand = [e for e in up if run_face(e) == face and abs(e["size_px"] - size) <= 0.03 * size]
    out = set(in_prose)
    for e in cand:
        if e["id"] in out: continue
        a = e["box_px"]; ca = (a[1] + a[3]) / 2
        for f in cand:
            if f is e or f["line"] == e["line"]: continue
            b = f["box_px"]
            if min(a[2], b[2]) - max(a[0], b[0]) < 0.5 * min(a[2] - a[0], b[2] - b[0]): continue
            if 0.85 * pitch <= abs((b[1] + b[3]) / 2 - ca) <= 1.2 * pitch: out.add(e["id"]); break
    return out


def prose_witnesses(texts, blocks, prose_blocks, span, structure_boxes, rules, captions, edge, direction, em, column_share=1/3):
    """Rule 3 (tablesub R2 contract): the prose-column blocks (prose_column_blocks) that may end a captioned table
    beyond its connected drawn structure. A block is no witness, and its lines stay with the table (rows of the
    table or lines of its declared block), when
    (gate) it lies inside the table's own drawing: the table's rules continue past the connected structure (a
    rule whose two ends lie within a letter height of a structure line's ends, before any other caption in
    the span) and the block lies between the structure and the farthest such rule; or
    (cells) one of its lines shares its baseline with a run beside it in the span (wholly outside the block's
    width, past the structure and before the next caption, not itself a caption) whose block is narrower than
    column_share of the span, and that side of the line (left or right of the block) holds no run whose block
    is that wide: a column of body prose stands alone or beside another column, a wrapped cell column stands
    beside the row's other cells (a body column beside the NEXT table's cells is beside cells of another
    caption, and stays a witness; a list marker beside the neighbouring body column's line is a piece of that
    column, whose wide run shares the line, and is no cell).
    span = (s0, s1); edge = the connected structure's far edge in the reading direction."""
    if not prose_blocks: return prose_blocks
    s0, s1 = span
    def ov(a0, a1, b0, b1): return min(a1, b1) - max(a0, b0)
    ends = [(b[0], b[2]) for b in structure_boxes]
    beyond = (lambda y0, y1: y0 >= edge - 1) if direction > 0 else (lambda y0, y1: y1 <= edge + 1)
    stops = [c["box_px"] for c in captions if ov(c["box_px"][0], c["box_px"][2], s0, s1) > 0 and beyond(c["box_px"][1], c["box_px"][3])]
    stop = (min((c[1] for c in stops), default=float("inf")) if direction > 0 else max((c[3] for c in stops), default=float("-inf")))
    own = [r for r in rules if beyond(r[1], r[3]) and any(abs(r[0] - a) <= em and abs(r[2] - b) <= em for a, b in ends)
           and (r[3] <= stop if direction > 0 else r[1] >= stop)]
    gate = (max((r[3] for r in own), default=None) if direction > 0 else min((r[1] for r in own), default=None))
    block_of = {m: b for b in blocks for m in b["members"]}
    by_line = collections.defaultdict(list)
    for e in texts: by_line[e["line"]].append(e)
    capids = {c["id"] for c in captions}
    def before(r):   # a run of this table's extent: past its structure, before the next caption, not a caption
        R = r["box_px"]
        return r["id"] not in capids and beyond(R[1], R[3]) and (R[3] <= stop if direction > 0 else R[1] >= stop)
    out = set()
    for b in blocks:
        if b["id"] not in prose_blocks: continue
        B = b["box_px"]
        if gate is not None and ((direction > 0 and B[1] >= edge - 1 and B[3] <= gate + em)
                                 or (direction < 0 and B[3] <= edge + 1 and B[1] >= gate - em)):
            continue
        lines = {e["line"] for e in texts if block_of.get(e["id"]) is b and beyond(e["box_px"][1], e["box_px"][3])}
        def narrow(r):
            o = block_of.get(r["id"]); X = o["box_px"] if o else r["box_px"]
            return X[2] - X[0] < column_share * (s1 - s0)
        def beside(r):
            return (block_of.get(r["id"]) is not b and ov(r["box_px"][0], r["box_px"][2], s0, s1) > 0
                    and ov(r["box_px"][0], r["box_px"][2], B[0], B[2]) <= 0 and before(r))
        def left(r): return r["box_px"][2] <= B[0]
        def cell(r, li):   # a narrow run beside the block on a side of the line that holds no run of a wide block:
            # a list marker or a heading number beside a body column's line is a piece of that column, not a cell
            return beside(r) and narrow(r) and not any(beside(q) and left(q) == left(r) and not narrow(q) for q in by_line[li])
        if any(cell(r, li) for li in lines for r in by_line[li]):
            continue
        out.add(b["id"])
    return frozenset(out)

def note_before_main_text(pending, part, note_size, main_size):
    """R1 (lane stream2): when main text ends a table's downward walk, the note under the table ends at its
    first line set at the size of that main text (main_size, within body_size_tolerance) and larger than the
    note size. That line and every line after it belong to
    the main text that ended the walk (its paragraph's first lines in each column, a section heading among them),
    which a column of fewer than column_min_lines lines does not prove as prose by itself (measured: AQ08 p4,
    two-line and four-line column openings between Table 2's note and the next column paragraphs; kept as note,
    their lines were held by a paragraph and by the table at once). A note set no larger than the note size (the
    cells' size, or a caption's) is kept whole, and a walk ended any other way is unchanged. pending: the walk's ("line", box, line) items
    in reading order; part: line -> [(box, run)] over the table."""
    tol = PARAMS["body_size_tolerance"]
    for k, it in enumerate(pending):
        sizes = [r[1]["run_size_px"] for r in part[it[2]]]
        if any(s > note_size * (1 + tol) and abs(s - main_size) <= tol * main_size for s in sizes): return pending[:k]
    return pending


def table_prose_lines(texts, blocks, box, body, note_size, angle=0, direction=1, column_share=1/3, channels=(), prose_blocks=frozenset()):
    """Two consecutive body-sized lines filling a text column beyond a table's drawn
    rows are prose when larger than its cells/notes or crossing established cell channels, or when their block
    is a column of body prose (prose_column_blocks). Work in the table's reading frame,
    group by column block (shared baselines are allowed), and ignore narrow cell blocks.
    A large caption heading is not a note-size witness. Return the first line of each pair.
    """
    to_read, _ = frame(angle)
    def rd(b):
        u0, v0, u1, v1 = to_read(*b)
        return min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1)
    owner = {m: b for b in blocks for m in b["members"]}
    prose = collections.defaultdict(list)
    for e in texts:
        if e["angle"] != angle: continue
        R = rd(e["box_px"]); b = owner.get(e["id"])
        if not b or b.get("text_lines", 0) < 2: continue
        if not (R[1] > box[3] if direction > 0 else R[3] < box[1]): continue
        if min(R[2], box[2]) <= max(R[0], box[0]): continue
        B = rd(b["box_px"]); width = min(B[2] - B[0], box[2] - box[0])
        if width < column_share * (box[2] - box[0]): continue
        crosses = any(R[0] + body <= a and b <= R[2] - body for a, b in channels)
        if (R[2] - R[0] >= PARAMS["prose_share"] * width and e["run_size_px"] >= 0.97 * body
                and (crosses or b["id"] in prose_blocks or e["run_size_px"] > note_size * (1 + PARAMS["body_size_tolerance"]))):
            prose[b["id"]].append((R, e))
    starts = set()
    for rs in prose.values():
        rs.sort(key=lambda r: direction * r[0][1])
        for (A, a), (B, b) in zip(rs, rs[1:]):
            gap = B[1] - A[3] if direction > 0 else A[1] - B[3]
            if a["line"] != b["line"] and 0 <= gap <= PARAMS["note_gap_em"] * body:
                starts.add(a["line"])
    return starts


def table_caption_runs(elements):
    """Table labels, including a separately typeset number on the same baseline.
    Return virtual labels without changing rule 1's text or character ownership.
    """
    texts = [e for e in elements if e["kind"] == "text"]
    for e in texts:
        if is_caption_run(e) and re.sub(r"\s+", "", e["text"]).lower().startswith("table"):
            yield e
        elif re.sub(r"\s+", "", e["text"]).lower() == "table":
            B = e["box_px"]; em = e["run_size_px"]
            ns = [n for n in texts if n["angle"] == e["angle"] == 0 and n["line"] == e["line"]
                  and 0 <= n["box_px"][0] - B[2] <= 2 * em and re.fullmatch(r"\d+[.:]?", n["text"].strip())]
            if ns:
                n = min(ns, key=lambda n: n["box_px"][0])
                yield dict(e, text=e["text"] + " " + n["text"], box_px=[B[0], min(B[1], n["box_px"][1]), n["box_px"][2], max(B[3], n["box_px"][3])])


def prose_column_tracks(runs, main_runs, size, context=(), block_of=None, drawn=()):
    """Rule 3 (lane r2-prosetable): the tracks of a candidate table that are columns of body prose, not cells.
    A track is a prose column when
      - most of its runs are body text: at the page's body size (within the 0.97 margin prose_column_blocks
        uses) in the page's body face, both character-weighted over the page, or runs of main-text blocks;
      - it has column_min_lines lines or more (a shorter running-text track of the same measure joins two found
        columns: a page's short last column), most of them starting at one left edge (within a letter height,
        or indented by at most two: a paragraph's first line), set as running text: three words or more on most
        lines, sentence punctuation, and letters, not values (digits under a fifth of its characters);
      - another such track of the same measure (widths within a letter height) stands in the same candidate,
        beside it, across a panel between them, or elsewhere on the page (another main-text block's column,
        such as a short column ending above the candidate's lines), and the two are not rows of one table: the units the two
        tracks open (a line after extra white or an indented first line) do not start on shared baselines.
        A table's cells open together at each row; the paragraphs and headings of two text columns do not; and
        over their shared height two text columns hold about as many lines (prose_share), where a table's shorter
        cells leave one track far fewer lines than its neighbour; and a table's rows are rule-2 blocks side by
        side, so three or more blocks of the two tracks starting on one line are rows, not columns.
      - it is not a column of cells: three or more whole blank lines (white of two line pitches or more) inside it
        are the rows its shorter cells leave empty; a text column's white is a heading's space, under two lines.
    Ragged or justified right edges are both prose: the right edge is never measured.
    Tracks of different measures are partners too when each opens its own units (indented paragraph starts,
    headings after white) at two lines or more and fewer than half of them on the other's opening lines.
    A drawn panel between two prose tracks (a fill, a frame side or a rule standing in the white between them and
    beside both, column_min_lines letter heights tall or more; drawn: boxes in the same frame) makes them partners
    whatever their measures: a panel set between columns parts two columns of text, never two cells of a row.
    The test runs on the whole column: with context (the page's (box, run) pairs) and block_of, a track's lines
    are those of every run in the rule-2 blocks its runs belong to, within the track, so a candidate holding only a
    column's last lines is judged by its column.
    runs are (reading-frame box, run) pairs; returns the qualifying tracks as (u0, u1) intervals."""
    ivs = sorted((R[0], R[2]) for R, e in runs)
    tracks = []
    for a, b in ivs:
        if tracks and a <= tracks[-1][1]: tracks[-1] = (tracks[-1][0], max(tracks[-1][1], b))
        else: tracks.append((a, b))
    # body text: the page's body size and face (character-weighted over the page), or a run of a main-text block
    page = [e for R, e in (context or runs)]
    sizes = [e["run_size_px"] for e in page if e.get("run_size_px")]
    body_sz = statistics.median(sizes) if sizes else 0
    faces = collections.Counter()
    for e in page: faces[run_face(e)] += len(e["text"].strip())
    body_face = faces.most_common(1)[0][0] if faces else None
    def body_text(e): return e["id"] in main_runs or (e.get("run_size_px", 0) >= 0.97 * body_sz and run_face(e) == body_face)
    own_tracks = list(tracks)
    if context and block_of is not None:
        # the page's other prose columns can be the partner: a short column ending above the candidate's lines,
        # or one across a panel; each main-text block clear of the candidate's tracks adds its own extent
        blocks = {}
        for R, e in context:
            if body_text(e) and e["id"] in block_of:
                b = blocks.setdefault(id(block_of[e["id"]]), [R[0], R[2]]); b[0] = min(b[0], R[0]); b[1] = max(b[1], R[2])
        for x0, x1 in sorted(blocks.values()):
            if any(min(x1, t[1]) - max(x0, t[0]) > 0 for t in tracks): continue
            hit = next((t for t in tracks if t not in own_tracks and min(x1, t[1]) - max(x0, t[0]) > -size), None)
            if hit: tracks[tracks.index(hit)] = (min(hit[0], x0), max(hit[1], x1))
            else: tracks.append((x0, x1))
    cols = {}
    for t0, t1 in tracks:
        rs = [(R, e) for R, e in runs if t0 <= R[0] and R[2] <= t1]
        if (t0, t1) not in own_tracks: rs = [(R, e) for R, e in context if t0 <= R[0] and R[2] <= t1]
        main = sum(1 for R, e in rs if body_text(e)) >= PARAMS["prose_share"] * len(rs)
        if context and block_of is not None:
            own = {id(block_of[e["id"]]) for R, e in rs if e["id"] in block_of}
            seen = {e["id"] for R, e in rs}
            rs = rs + [(R, e) for R, e in context if e["id"] not in seen and t0 <= R[0] and R[2] <= t1
                       and e["id"] in block_of and id(block_of[e["id"]]) in own]
        lines = collections.defaultdict(list)   # a justified line can hold several runs (wide word spaces)
        for R, e in rs: lines[e["line"]].append((R, e))
        boxes = sorted(([min(R[0] for R, _ in v), min(R[1] for R, _ in v), max(R[2] for R, _ in v), max(R[3] for R, _ in v),
                         " ".join(e["text"] for _, e in sorted(v, key=lambda x: x[0][0]))] for v in lines.values()), key=lambda b: b[1])
        left = collections.Counter(round(b[0] / size) for b in boxes).most_common(1)[0][0] * size
        aligned = [b for b in boxes if left - size <= b[0] <= left + 2 * size]
        if len(aligned) < PARAMS["prose_share"] * len(boxes): continue
        text = " ".join(b[4] for b in boxes)
        letters = sum(ch.isalpha() for ch in text); digits = sum(ch.isdigit() for ch in text)
        if letters == 0 or digits > 0.2 * (letters + digits) or not re.search(r"[.!?;:](?:\s|$)", text): continue
        if 2 * sum(1 for b in boxes if len(re.findall(r"[^\W\d_]{2,}", b[4])) >= 3) <= len(boxes): continue
        pitch = statistics.median([y[1] - x[1] for x, y in zip(boxes, boxes[1:])] or [size])
        starts = [y[1] for x, y in zip(boxes, boxes[1:]) if y[1] - x[1] >= pitch + 0.25 * size or y[0] >= left + 0.5 * size]
        if sum(1 for x, y in zip(boxes, boxes[1:]) if y[1] - x[1] >= 2 * pitch + 0.5 * size) >= 3: continue
        core = main and len(lines) >= PARAMS["column_min_lines"]
        tops = {}   # every rule-2 block of the page lying in the track, not only the candidate's
        for R, e in (list(context) if context else rs):
            if not (t0 <= R[0] and R[2] <= t1): continue
            k = id(block_of[e["id"]]) if block_of is not None and e["id"] in block_of else None
            if k is not None: tops[k] = min(tops.get(k, R[1]), R[1])
        cols[(t0, t1)] = (max(b[2] for b in boxes) - min(b[0] for b in boxes), starts, (boxes[0][1], boxes[-1][3]), core,
                          [b[1] for b in boxes], sorted(tops.values()))
    def rows_of_one_table(a, b):
        (_, sa, va, _, ya, ta), (_, sb, vb, _, yb, tb) = cols[a], cols[b]
        # a table's rows are rule-2 blocks side by side: cells of one row start on one line in every track
        if sum(1 for y in ta if any(abs(y - z) <= 0.5 * size for z in tb)) >= 3: return True
        lo, hi = max(va[0], vb[0]), min(va[1], vb[1])
        # over their shared height two text columns hold about as many lines each; a table's shorter cells leave
        # one track's lines far fewer than its neighbour's
        na = sum(1 for y in ya if lo <= y <= hi); nb = sum(1 for y in yb if lo <= y <= hi)
        if max(na, nb) >= PARAMS["column_min_lines"] and min(na, nb) < PARAMS["prose_share"] * max(na, nb): return True
        sa = [y for y in sa if lo <= y <= hi]; sb = [y for y in sb if lo <= y <= hi]
        if min(len(sa), len(sb)) < 3: return False   # rows need three openings on each side to be shown
        shared = sum(1 for y in sa if any(abs(y - z) <= 0.5 * size for z in sb))
        return shared >= 2 and 2 * shared >= min(len(sa), len(sb))
    def panel_between(a, b):
        (l0, l1), (r0, r1) = sorted((a, b))
        va, vb = cols[a][2], cols[b][2]
        return any(D[0] >= l1 - size and D[2] <= r0 + size and D[3] - D[1] >= PARAMS["column_min_lines"] * size
                   and min(D[3], va[1]) > max(D[1], va[0]) and min(D[3], vb[1]) > max(D[1], vb[0]) for D in drawn)
    def independent(a, b):
        """each track opens its own units (paragraph indents, headings after white) at two lines or more within
        their shared height, and fewer than half of them on a line where the other opens one: the openings of
        two text columns, not the rows of one table"""
        (_, sa, va, *_), (_, sb, vb, *_) = cols[a], cols[b]
        lo, hi = max(va[0], vb[0]), min(va[1], vb[1])
        sa = [y for y in sa if lo <= y <= hi]; sb = [y for y in sb if lo <= y <= hi]
        if min(len(sa), len(sb)) < 2: return False
        shared = sum(1 for y in sa if any(abs(y - z) <= 0.5 * size for z in sb))
        return 2 * shared < min(len(sa), len(sb))
    def partners(t, o): return abs(cols[o][0] - cols[t][0]) <= size or panel_between(t, o) or independent(t, o)
    found = [t for t in cols if cols[t][3] and any(o != t and cols[o][3] and partners(t, o)
                                                   and not rows_of_one_table(t, o) for o in cols)]
    # a column of the same measure set as running text joins them even when it is short (the last column of the
    # page, a few lines under a heading) and so not main text on its own
    prose = found + [t for t in cols if t not in found and found and any(abs(cols[o][0] - cols[t][0]) <= size
                                                                       and not rows_of_one_table(t, o) for o in found)]
    return [t for t in prose if t in own_tracks]


def main_prose_run_ids(texts, blocks):
    """The runs of columns of body prose (tables_from_grid's main_runs): members of prose_column_blocks blocks at
    least 12 body letter heights wide (a table-only page's modal line is a cell's)."""
    upright = [e["run_size_px"] for e in texts if e["angle"] == 0]
    if not upright or not blocks: return set()
    body_px = statistics.median(upright)
    prose_ids = prose_column_blocks(texts, blocks, body_px)
    return {m for b in blocks if b["id"] in prose_ids and b["box_px"][2] - b["box_px"][0] >= 12 * body_px for m in b["members"]}


def table_grid_supported(t, elements):
    """An uncaptioned alignment needs two drawn boundaries enclosing cell rows,
    or a boundary meeting an interior divider. Gutter rules and page separators
    alone are not a grid. Work in the table's reading frame, including rotation.
    """
    to_read, _ = frame(t["angle"])
    def rd(b):
        a, b, c, d = to_read(*b)
        return min(a, c), min(b, d), max(a, c), max(b, d)
    texts = [e for e in elements if e["kind"] == "text" and e["angle"] == t["angle"]]
    cells = [e for e in texts if e["id"] in t["members"]]
    if not cells: return False
    em = statistics.median(e["run_size_px"] for e in cells)
    T = rd(t["box_px"])
    for cap in table_caption_runs(elements):
        if cap["angle"] != t["angle"]: continue
        C = rd(cap["box_px"])
        # A grid seed can start well inside a table, after spanning headers
        # or a wide label column. The page's caption can anchor those fragments;
        # rule 4 will join them to the caption's table.
        if C[3] <= T[3] + 3 * em:
            return True
    rules = [e for e in elements if e["kind"] == "rule" and not e.get("overlay")]
    rules += joined_rules(rules)
    rules = [rd(o["box_px"]) for o in rules if min(rd(o["box_px"])[2], T[2]) >= max(rd(o["box_px"])[0], T[0])
             and min(rd(o["box_px"])[3], T[3]) >= max(rd(o["box_px"])[1], T[1])]
    hs = [b for b in rules if b[2] - b[0] > 4 * em and b[3] - b[1] < px(PARAMS["rule_max_pt"])]
    vs = [b for b in rules if b[3] - b[1] > 2 * em and b[2] - b[0] < px(PARAMS["rule_max_pt"])]
    # Repeated shaded rows draw the same boundaries without stroking a rule.
    # Join touching cell fills across a row before testing their common sides.
    bands = []
    for o in sorted((rd(e["box_px"]) for e in elements if e["kind"] == "fill" and not e.get("overlay")), key=lambda b: (b[1], b[0])):
        if o[3] - o[1] < em or min(o[3], T[3]) <= max(o[1], T[1]): continue
        target = next((b for b in bands if abs(b[1] - o[1]) <= 1 and abs(b[3] - o[3]) <= 1 and o[0] <= b[2] + 1), None)
        if target is None: bands.append(list(o))
        else: target[0] = min(target[0], o[0]); target[2] = max(target[2], o[2])
    for a in bands:
        for b in bands:
            if b[1] < a[3] + em or abs(a[0] - b[0]) > em or abs(a[2] - b[2]) > em: continue
            if a[2] - a[0] < .6 * (T[2] - T[0]): continue
            if all(len({e["line"] for e in cells if band[0] - em <= rd(e["box_px"])[0] and rd(e["box_px"])[2] <= band[2] + em
                        and band[1] <= (rd(e["box_px"])[1] + rd(e["box_px"])[3]) / 2 <= band[3]}) >= 2 for band in (a, b)):
                return True
    for a in hs:
        for b in hs:
            if b[1] <= a[3] + em or abs(a[0] - b[0]) > em or abs(a[2] - b[2]) > em: continue
            inside = [e for e in cells if a[0] - em <= rd(e["box_px"])[0] and rd(e["box_px"])[2] <= a[2] + em
                      and a[3] <= rd(e["box_px"])[1] and rd(e["box_px"])[3] <= b[1]]
            if len({e["line"] for e in inside}) >= 2: return True
        for v in vs:
            x = (v[0] + v[2]) / 2
            if not (a[0] + em < x < a[2] - em and min(abs(v[1] - a[3]), abs(v[3] - a[1])) <= px(PARAMS["rule_join_pt"])): continue
            inside = [rd(e["box_px"]) for e in cells if v[1] - em <= rd(e["box_px"])[1] and rd(e["box_px"])[3] <= v[3] + em]
            if sum(b[2] <= x for b in inside) >= 2 and sum(b[0] >= x for b in inside) >= 2: return True
    return False


def white_inside_column(runs, inside, top, bottom, w0, w1, blocks=(), rd=None):
    """Rule 3 (closed two-track grid): the white from w0 to w1 between two tracks lies inside a text column
    when the page's text next to the rules spans it: the line directly above the upper rule or directly
    below the lower one (its runs within the rules' width) has a run spanning that white, or the text block
    directly above or below (rule 2's boxes within the rules' width) does (a one-line introduction above a
    grid that ends its column belongs to a paragraph as wide as the column). A gutter between a page's
    columns is spanned by neither: each neighbouring line and block lies on one side of it. Boxes are in
    reading frame (rd maps a block's page box into it)."""
    ids = {e["id"] for _, e in inside}
    x0, x1 = max(top[0], bottom[0]), min(top[2], bottom[2])
    near = [(R, e) for R, e in runs if e["id"] not in ids and min(R[2], x1) > max(R[0], x0)]
    above = [(R, e) for R, e in near if (R[1] + R[3]) / 2 < top[1]]
    below = [(R, e) for R, e in near if (R[1] + R[3]) / 2 > bottom[3]]
    for side, key in ((above, lambda r: -r[0][3]), (below, lambda r: r[0][1])):
        if not side: continue
        line = min(side, key=key)[1]["line"]
        if any(e["line"] == line and R[0] <= w0 and R[2] >= w1 for R, e in side): return True
    boxes = [rd(o["box_px"]) if rd else o["box_px"] for o in blocks if not ids & set(o.get("members", ()))]
    boxes = [B for B in boxes if min(B[2], x1) > max(B[0], x0)]
    for side, key in (([B for B in boxes if B[3] <= top[3]], lambda B: -B[3]), ([B for B in boxes if B[1] >= bottom[1]], lambda B: B[1])):
        if side and (lambda B: B[0] <= w0 and B[2] >= w1)(min(side, key=key)): return True
    return False


def closed_pair_head_rule(runs, top, objs, rd=None, size=0, white=None):
    """Rule 3 (closed two-track grid): the rule that heads the table a closed pair belongs to. A table's
    first row can sit under a rule of its own (a header row ruled above and below, a first data row set
    off), so the pair's upper rule is not always the table's top: walk up while the next horizontal rule
    above has the same ends (within a letter height) and every line between the two rules lies in the
    pair's two tracks (at most two runs, none spanning the white between the tracks). Returns the top box
    (reading frame), the pair's own upper rule when nothing heads it."""
    if not white: return top
    def box(b): return rd(b) if rd else b
    hs = [box(o["box_px"]) for o in objs if o["kind"] == "rule"]
    hs = [h for h in hs if h[3] - h[1] < px(PARAMS["rule_max_pt"]) < h[2] - h[0]]
    while True:
        ups = [h for h in hs if h[3] <= top[1] + 1 and h[1] < top[1] - 1 and abs(h[0] - top[0]) <= size and abs(h[2] - top[2]) <= size]
        if not ups: return top
        h = max(ups, key=lambda h: h[3])
        between = [(R, e) for R, e in runs if min(R[2], top[2]) > max(R[0], top[0]) and h[3] < (R[1] + R[3]) / 2 < top[1]]
        lines = collections.Counter(e["line"] for _, e in between)
        if not between or max(lines.values()) > 2 or any(R[0] <= white[0] and R[2] >= white[1] for R, _ in between): return top
        top = h


def closed_pair_is_other_table(runs, inside, top, bottom, objs, blocks=(), rd=None, size=0, white=None):
    """Rule 3 (closed two-track grid): the pair of rules closes a captionless label/value grid, not part of
    another table. It is another table's when a drawn vertical rule (a cell border) stands between the
    rules across their width (a drawn grid: rule 3's grid and caption rules read it), or when the text
    block or line directly above the upper rule (within the rules' width) holds a caption label (a
    captioned table: the caption rules read it). The upper rule here is the one heading the pair's table
    (closed_pair_head_rule, given the white between the tracks): a captioned table whose first row is ruled
    off holds a closed pair below that row, and its caption stands above the table's top rule, not above
    the pair. Boxes are in reading frame (rd maps page boxes into it)."""
    def box(b): return rd(b) if rd else b
    top = closed_pair_head_rule(runs, top, objs, rd, size, white)
    x0, x1 = min(top[0], bottom[0]) - size, max(top[2], bottom[2]) + size
    for o in objs:
        if o["kind"] != "rule": continue
        R = box(o["box_px"])
        if R[3] - R[1] > R[2] - R[0] and x0 <= (R[0] + R[2]) / 2 <= x1 and top[3] <= (R[1] + R[3]) / 2 <= bottom[1]: return True
    ids = {e["id"] for _, e in inside}
    near = [(R, e) for R, e in runs if e["id"] not in ids and min(R[2], x1) > max(R[0], x0) and (R[1] + R[3]) / 2 < top[1]]
    if near:
        line = min(near, key=lambda r: -r[0][3])[1]["line"]
        if any(e["line"] == line and is_caption_run(e) for _, e in near): return True
    above = [(box(o["box_px"]), o) for o in blocks if not ids & set(o.get("members", ()))]
    above = [(B, o) for B, o in above if min(B[2], x1) > max(B[0], x0) and B[3] <= top[3]]
    if above:
        members = set(min(above, key=lambda b: -b[0][3])[1].get("members", ()))
        if any(e["id"] in members and is_caption_run(e) for _, e in runs): return True
    return False


def closed_two_track_tables(texts, objs, tables, blocks=()):
    """Rule 3: a closed label/value grid of two tracks. Two tracks alone are a page's column pair
    (table_min_tracks), so this table needs all of: a pair of horizontal rules with the same ends (within
    a letter height), the upper directly above the first line and the lower directly below the last
    (rule 2's stack_gap_em); every text line with a run between the rules, across their width, holds
    exactly two runs, one in each track; at least two such lines. The rules and the two runs per line are
    the witness; how wide the white between the tracks is, against the tracks, is not (a label track may be
    wider than that white). What tells such a grid from a page's column pair closed by rules is a property
    of the page: the white between the tracks lies inside a text column, so the page's line or text block
    directly above the upper rule or directly below the lower one (within the rules' width) spans that
    white; a gutter between two columns is spanned by neither (white_inside_column). A pair inside a drawn
    cell grid or under a caption is another table's (closed_pair_is_other_table).
    Runs already in a table and rules already a table's are left alone."""
    out = []
    def ids(o): return o.get("parts") or [o["id"]]
    taken = {m for t in tables for m in t["members"]}
    for ang in sorted({e["angle"] for e in texts}):
        to_read, _ = frame(ang)
        def rd(b):
            u0, v0, u1, v1 = to_read(*b); return (min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))
        runs = [(rd(e["box_px"]), e) for e in texts if e["angle"] == ang]
        hs = [(rd(o["box_px"]), o) for o in objs if o["kind"] == "rule" and not any(i in taken for i in ids(o))]
        hs = [(h, o) for h, o in hs if h[3] - h[1] < px(PARAMS["rule_max_pt"]) < h[2] - h[0]]
        # the widest enclosing pair first: a rule under a header row lies inside the outer pair
        for (t, ot), (b, ob) in sorted(((x, y) for x in hs for y in hs if y[0][1] > x[0][3]), key=lambda p: p[0][0][1] - p[1][0][3]):
                inside = [(R, e) for R, e in runs if min(R[2], b[2]) > max(R[0], b[0]) and t[3] < (R[1] + R[3]) / 2 < b[1]]
                if len(inside) < 4 or any(e["id"] in taken for _, e in inside): continue
                size = statistics.median(e["size_px"] for _, e in inside)
                if abs(t[0] - b[0]) > size or abs(t[2] - b[2]) > size: continue
                if any(R[0] < t[0] - size or R[2] > t[2] + size for R, _ in inside): continue
                lines = collections.defaultdict(list)
                for R, e in inside: lines[e["line"]].append((R, e))
                if len(lines) < 2 or any(len(rs) != 2 for rs in lines.values()): continue
                pairs = [sorted(rs, key=lambda r: r[0][0]) for rs in lines.values()]
                left = (min(p[0][0][0] for p in pairs), max(p[0][0][2] for p in pairs))
                right = (min(p[1][0][0] for p in pairs), max(p[1][0][2] for p in pairs))
                if right[0] <= left[1] or not white_inside_column(runs, inside, t, b, left[1], right[0], blocks, rd): continue
                if closed_pair_is_other_table(runs, inside, t, b, objs, blocks, rd, size, (left[1], right[0])): continue
                v_top = min(R[1] for R, _ in inside); v_bot = max(R[3] for R, _ in inside)
                gap = PARAMS["stack_gap_em"] * size
                if not (0 <= v_top - t[3] <= gap and 0 <= b[1] - v_bot <= gap): continue
                hull = [min(t[0], b[0]), t[1], max(t[2], b[2]), b[3]]
                inv = {0: lambda u, v: (u, v), 90: lambda u, v: (v, -u), 270: lambda u, v: (-v, u)}[ang]
                pts = [inv(hull[0], hull[1]), inv(hull[2], hull[3]), inv(hull[0], hull[3]), inv(hull[2], hull[1])]
                box = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
                order = sorted(lines, key=lambda li: min(R[1] for R, _ in lines[li]))
                wit = ids(ot) + ids(ob)
                out.append({"box_px": box, "angle": ang, "lines": len(lines), "grid_lines": len(lines), "tracks": 2,
                            "members": [e["id"] for li in order for _, e in sorted(lines[li], key=lambda r: r[0][0])] + wit,
                            "witness": wit[:6], "own_fills": 0})
                taken.update(out[-1]["members"])
    return out


def tables_from_grid(elements, blocks=(), decisions=None):
    """Rule 3: repeating text tracks, witnessed by a caption or a drawn grid.
    Captionless candidates require paired boundaries, a joined boundary/divider,
    or repeated shaded row bands; a gutter or footer separator alone is insufficient.
    The note walk stops before two consecutive body-sized lines filling a text block at least two
    thirds of the table width outside its local drawn extent and set larger than its cells and
    ordinary caption type: close leading alone does not make
    a body paragraph a table note. Without that size change, keep the note; a table-only page cannot
    establish body size. Display-sized captions do not determine note size, nor do page backgrounds
    or distant footer rules extend the drawn table. Independent captions above a shared grid and
    an empty drawing gutter allow its sides to be re-measured as separate tables, with every
    enclosed cell retained. This keeps a short table's prose separate from its taller neighbour."""
    tables = []
    block_of = {m: b for b in blocks for m in b["members"]}
    texts = [e for e in elements if e["kind"] == "text"]
    objs = [e for e in elements if e["kind"] in ("rule", "fill") and not e.get("overlay")]
    objs = objs + joined_rules(objs)
    def ids(o): return o.get("parts") or [o["id"]]
    # R1 (lane stream): runs of a column of body prose (prose_column_blocks: body size, the page's modal body
    # line width, 25 words and sentence punctuation) are main text; the table's outward walk never takes
    # one and its own fills never grow the box over one (TABLE-ASSEMBLY guard: cut back, never grown).
    upright = [e["run_size_px"] for e in texts if e["angle"] == 0]
    body_px = statistics.median(upright) if upright else 0
    prose_ids = prose_column_blocks(texts, blocks, body_px) if upright and blocks else set()
    # a column of prose is at least 12 body letter heights wide (the copier's table_body_sentence measure): a
    # table-only page's modal line is a cell's (measured: AP07 p4, a 101 px cell column of 31 lines)
    main_runs = {m for b in blocks if b["id"] in prose_ids and b["box_px"][2] - b["box_px"][0] >= 12 * body_px for m in b["members"]}
    main_boxes = [e["box_px"] for e in texts if e["id"] in main_runs]
    for ang in sorted({e["angle"] for e in texts}):
        to_read, _ = frame(ang)
        def rd(b): 
            u0, v0, u1, v1 = to_read(*b); return (min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))
        by_line = collections.defaultdict(list)
        for e in texts:
            if e["angle"] == ang: by_line[e["line"]].append((rd(e["box_px"]), e))
        order = sorted(by_line, key=lambda li: statistics.median(r[0][1] for r in by_line[li]))
        def merge(ivs):
            ivs = sorted(ivs); out = []
            for a, b in ivs:
                if out and a <= out[-1][1]: out[-1] = (out[-1][0], max(out[-1][1], b))
                else: out.append((a, b))
            return out
        def fits(tracks, runs):
            """at least half the runs, and at least two, each sit in exactly one track; a run that hits
            no track is allowed (a data column under a header that spans two columns)"""
            def in_track(u0, u1, t): return min(u1, t[1]) - max(u0, t[0]) >= 0.5 * (u1 - u0)
            single = sum(1 for (u0, v0, u1, v1), e in runs if len([t for t in tracks if in_track(u0, u1, t)]) == 1)
            return single >= 2 and 2 * single >= len(runs)
        taken = set()
        i = 0
        while i < len(order):
            runs = by_line[order[i]]
            if len(runs) < 2 or order[i] in taken: i += 1; continue
            tracks = merge([(r[0][0], r[0][2]) for r in runs]); members = [order[i]]; core = 1; pending = []; grid_runs = []; grid_lines = [order[i]]
            size_i = statistics.median(e["size_px"] for _, e in runs)
            j = i + 1
            while j < len(order):
                rj = by_line[order[j]]
                if len(rj) >= 2 and fits(tracks, rj):
                    members.extend(pending); pending = []; members.append(order[j]); grid_lines.append(order[j]); core += 1
                    tracks = merge(tracks + [(r[0][0], r[0][2]) for r in rj])
                elif len(rj) == 1 and tracks[0][0] - size_i <= rj[0][0][0] and rj[0][0][2] <= tracks[-1][1] + size_i:
                    pending.append(order[j])        # a group label: kept only if a grid line follows
                else: break
                j += 1
            witnesses = []
            if core >= 2 and len(tracks) >= PARAMS["table_min_tracks"]:
                all_runs = [r for li in members for r in by_line[li]]
                band = (min(r[0][1] for r in all_runs), max(r[0][3] for r in all_runs))
                size0 = statistics.median(e["size_px"] for _, e in all_runs)
                hull = [min(r[0][0] for r in all_runs), band[0], max(r[0][2] for r in all_runs), band[1]]
                # header lines directly stacked above the data rows (column heads, group heads): each run
                # within the grid's width and narrower than a prose line; the band, and so the witness
                # test, includes them. A caption line ends the header.
                core_band = band    # the data rows alone: the prose-beside test below keeps this band
                k = i - 1; wdt = hull[2] - hull[0]
                while k >= 0 and i - k <= PARAMS["header_max_lines"]:
                    hr = by_line[order[k]]
                    hv0, hv1 = min(r[0][1] for r in hr), max(r[0][3] for r in hr)
                    if band[0] - hv1 > PARAMS["stack_gap_em"] * size0: break
                    if any(r[0][0] < hull[0] - size0 or r[0][2] > hull[2] + size0 or (r[0][2] - r[0][0]) > PARAMS["header_cell_share"] * wdt for r in hr): break
                    if is_caption_run(min(hr, key=lambda r: r[0][0])[1]): break
                    band = (hv0, band[1]); hull[1] = hv0; k -= 1
                grid_runs = all_runs
                line_v = [(min(r[0][1] for r in by_line[li]), max(r[0][3] for r in by_line[li])) for li in members]
                def spanning(o):
                    """drawn grid structure: a rule or fill across two or more tracks, or down two or more grid lines"""
                    u0, v0, u1, v1 = rd(o["box_px"])
                    across = sum(1 for t in tracks if min(u1, t[1]) - max(u0, t[0]) > 0) >= 2
                    down = sum(1 for a, b in line_v if min(v1, b) - max(v0, a) > 0) >= 2
                    return across or down
                size_px = statistics.median(e["size_px"] for li in members for _, e in by_line[li])
                def straddles(u0, u1):
                    """a run lying across two or more tracks without sitting in any one: prose, not a cell"""
                    hits = [t for t in tracks if min(u1, t[1]) - max(u0, t[0]) > 0]
                    return len(hits) >= 2 and not any(min(u1, t[1]) - max(u0, t[0]) >= 0.5 * (u1 - u0) for t in hits)
                def belongs(o):
                    """the witness belongs to the grid: it overlaps the grid band, and every text line it
                    covers is made of cells (no run straddles the tracks), so a box of prose does not count"""
                    u0, v0, u1, v1 = rd(o["box_px"])
                    if v1 < hull[1] - size_px or v0 > hull[3] + size_px: return False
                    if u1 < hull[0] - size_px or u0 > hull[2] + size_px: return False   # beside the grid, not in it
                    for li in order:
                        for (a0, b0, a1, b1), e in by_line[li]:
                            if min(b1, v1) - max(b0, v0) > 0 and straddles(a0, a1): return False
                    return True
                witnesses = [o for o in objs if spanning(o) and belongs(o)]
                if witnesses:
                    # the grid's lines end where its drawing ends: lines at either end of the walk lying
                    # wholly beyond the witnesses' extent by more than note_gap_em letter heights (a page
                    # footer whose runs happen to sit in the tracks) are dropped; the outward walk below
                    # takes back any note directly under the last rule
                    wit_v = (min(rd(o["box_px"])[1] for o in witnesses), max(rd(o["box_px"])[3] for o in witnesses))
                    reach = PARAMS["note_gap_em"] * size_px
                    def line_span(li): return (min(r[0][1] for r in by_line[li]), max(r[0][3] for r in by_line[li]))
                    n_before = len(members)
                    while members and line_span(members[-1])[0] > wit_v[1] + reach: members.pop()
                    while members and line_span(members[0])[1] < wit_v[0] - reach: members.pop(0)
                    if members and len(members) < n_before and order.index(members[-1]) + 1 < j: j = order.index(members[-1]) + 1
                    core = len([li for li in members if li in grid_lines])
                    all_runs = [r for li in members for r in by_line[li]]
                    tracks = merge([(r[0][0], r[0][2]) for li in members if li in grid_lines for r in by_line[li]]) if core else []
                if witnesses and core >= 2:
                    wit_u = (min(rd(o["box_px"])[0] for o in witnesses), max(rd(o["box_px"])[2] for o in witnesses))
                    line_of = {e["id"]: li for li in by_line for _, e in by_line[li]}
                    line_vv = {li: (min(r[0][1] for r in by_line[li]), max(r[0][3] for r in by_line[li])) for li in by_line}
                    drawn_cell_size = statistics.median([e["run_size_px"] for R, e in all_runs
                                                        if wit_u[0] <= R[0] and R[2] <= wit_u[1]] or [size0])
                    prose_columns = {}
                    def beside(run):
                        """prose beside the table: its rule-2 box lies clear of the drawn grid sideways and
                        holds a text line wholly outside the grid band; or it lies clear of the drawn grid
                        sideways by more than a letter height and no fill in the grid's band spans the run's
                        column (a column of shaded cells beyond the rules is the table's): a neighbouring
                        figure's labels or column on the same lines"""
                        R = run[0]
                        # R1 (lane stream, re-ladder 3): a main-text run (a run of a column of body prose,
                        # main_runs) lying beyond the drawn grid sideways is the neighbouring column's text on
                        # the grid's baselines, never a cell, whatever its size against the cells and whether
                        # or not a line of its column ends a sentence near the grid (a paragraph tail carried
                        # over from the previous page beside a framed chart whose axis numbers share its
                        # baselines took three body lines as cells and the chart from its caption).
                        if run[1]["id"] in main_runs and (R[2] < wit_u[0] + size0 or R[0] > wit_u[1] - size0):
                            if decisions is not None:
                                decision = dict(box_px=list(run[1]["box_px"]), why="bounded: main text beside the drawn grid")
                                if decision not in decisions: decisions.append(decision)
                            return True
                        # Rule-2 containment can already have merged a table with
                        # neighbouring prose. A column-width run outside the
                        # drawn band is independent of that merged block.
                        key = round(R[0] / size0)
                        if key not in prose_columns:
                            column = [r for li in order for r in by_line[li]
                                      if abs(r[0][0] - key * size0) < size0 and r[0][2] - r[0][0] >= 12 * size0
                                      and core_band[0] - 3 * size0 <= r[0][1] <= core_band[1] + 3 * size0]
                            prose_columns[key] = len(column) >= 3 and any(r[1]["text"].rstrip().endswith(".") for r in column)
                        prose_column = prose_columns[key]
                        if (prose_column and run[1]["run_size_px"] > drawn_cell_size * (1 + PARAMS["body_size_tolerance"])
                                and (R[2] < wit_u[0] + size0 or R[0] > wit_u[1] - size0)):
                            if decisions is not None:
                                decision = dict(box_px=list(run[1]["box_px"]), why="bounded: prose column beside the drawn table")
                                if decision not in decisions: decisions.append(decision)
                            return True
                        blk = block_of.get(run[1]["id"])
                        if not blk: return False
                        bu0, _, bu1, _ = rd(blk["box_px"])
                        if min(bu1, wit_u[1]) - max(bu0, wit_u[0]) > 0: return False
                        if bu0 > wit_u[1] + size0 or bu1 < wit_u[0] - size0:
                            ru0, _, ru1, _ = run[0]
                            if not any(o["kind"] == "fill" and rd(o["box_px"])[0] - 1 <= ru0 and ru1 <= rd(o["box_px"])[2] + 1
                                       and min(rd(o["box_px"])[3], core_band[1] + size0) - max(rd(o["box_px"])[1], core_band[0] - size0) > 0 for o in objs):
                                return True
                        if not any(min(bu1 + size0, rd(o["box_px"])[2]) - max(bu0 - size0, rd(o["box_px"])[0]) > 0 and
                                   min(rd(o["box_px"])[3], core_band[1]) - max(rd(o["box_px"])[1], core_band[0]) > 0 for o in objs):
                            return True   # nothing drawn beside it within a letter height across the grid's band: a heading or line of prose, not a cell
                        for m in blk["members"]:
                            li = line_of.get(m)
                            if li is None: continue
                            v0, v1 = line_vv[li]
                            if v1 < core_band[0] - size0 or v0 > core_band[1] + size0: return True
                        return False
                    grid_runs = [r for r in all_runs if not beside(r)]
                    # lane r2-prosetable: two or more equal columns of filled body-prose lines inside the drawn
                    # extent are the page's text columns (a rule across the column band or a boxed side panel
                    # witnessed them as one grid; its lines spliced the columns and took their headings); their
                    # runs are never cells, and what remains must stand as a table on its own
                    prose_tracks = prose_column_tracks(grid_runs, main_runs, size0, [r for li in by_line for r in by_line[li]], block_of,
                                                       [rd(o["box_px"]) for o in objs])
                    if len(prose_tracks) >= 2:
                        if decisions is not None:
                            decision = dict(box_px=list(hull[:4]), why="refused cells: equal columns of body prose are the page's columns")
                            if decision not in decisions: decisions.append(decision)
                        grid_runs = [r for r in grid_runs if not any(t0 <= r[0][0] and r[0][2] <= t1 for t0, t1 in prose_tracks)]
                    # R1 (lane stream, re-ladder 3): a grid whose every cell is a bare number, a single letter or a
                    # sign is a chart's axis numbers, panel letters and asterisks, not a table (a framed line chart's
                    # x-axis labels of two panels formed a 4-track grid once the body lines beside it were no cells);
                    # a table has a cell of some other kind: a word, a label, a value with its unit or code
                    if grid_runs and all(re.fullmatch(r"[-+\u2212\u00b1]?\d+(?:[.,]\d+)?%?|[^\W\d_]|[*\u2020\u2021]+", r[1]["text"].strip())
                                         for r in grid_runs):
                        if decisions is not None:
                            decision = dict(box_px=list(hull[:4]), why="refused: every cell a bare number, letter or sign (a chart's lettering)")
                            if decision not in decisions: decisions.append(decision)
                        grid_runs = []
                    tracks = merge([(r[0][0], r[0][2]) for r in grid_runs])
                    if len(tracks) < PARAMS["table_min_tracks"]: witnesses = []; grid_runs = []
                else: witnesses = []; grid_runs = []
                if witnesses:
                    hull = [min(r[0][0] for r in grid_runs), min(r[0][1] for r in grid_runs), max(r[0][2] for r in grid_runs), max(r[0][3] for r in grid_runs)]
                    for o in witnesses:
                        u0, v0, u1, v1 = rd(o["box_px"]); hull = [min(hull[0], u0), min(hull[1], v0), max(hull[2], u1), max(hull[3], v1)]
                    own_fills = []
                    # caption lines: rule 4's; the box never grows over one (a frame drawn round table and caption)
                    cap_lines = [(min(r[0][0] for r in by_line[li]), min(r[0][1] for r in by_line[li]), max(r[0][2] for r in by_line[li]), max(r[0][3] for r in by_line[li]))
                                 for li in order if li not in members and is_caption_run(min(by_line[li], key=lambda r: r[0][0])[1])]
                    def meets_caption(h):
                        return any(min(h[2], c[2]) - max(h[0], c[0]) > 0 and min(h[3], c[3]) - max(h[1], c[1]) > 0 for c in cap_lines)
                    def absorb_own_fills():
                        """the table's own fills and rules: a drawn object overlapping the table box on both
                        axes whose every covered text line is a line of the table (a cell fill, a row band, a
                        side rule); the box extends to them, so its edge is the drawn edge, not the text's"""
                        nonlocal hull
                        grew = True
                        while grew:
                            grew = False
                            for o in objs:
                                if any(o is w for w in witnesses) or any(o is w for w in own_fills): continue
                                u0, v0, u1, v1 = rd(o["box_px"])
                                if min(u1, hull[2]) - max(u0, hull[0]) <= 0 or min(v1, hull[3]) - max(v0, hull[1]) <= 0: continue
                                covered = [li for li in by_line if any(min(b1, v1) - max(b0, v0) > 0 and min(a1, u1) - max(a0, u0) > 0 for (a0, b0, a1, b1), e in by_line[li])]
                                if any(li not in members for li in covered): continue
                                grown = [min(hull[0], u0), min(hull[1], v0), max(hull[2], u1), max(hull[3], v1)]
                                if meets_caption(grown) and not meets_caption(hull): continue   # the frame round table and caption: not the table's own
                                if any(min(grown[2], m[2]) - max(grown[0], m[0]) > 1 and min(grown[3], m[3]) - max(grown[1], m[1]) > 1
                                       and not (min(hull[2], m[2]) - max(hull[0], m[0]) > 1 and min(hull[3], m[3]) - max(hull[1], m[1]) > 1)
                                       for m in (rd(b) for b in main_boxes)): continue   # R1: never grown over main text
                                own_fills.append(o); grew = True
                                hull = [min(hull[0], u0), min(hull[1], v0), max(hull[2], u1), max(hull[3], v1)]
                    absorb_own_fills()
                    # the whole table: walk outward from the grid, in both directions, over items that are
                    # directly stacked (rule 2's gap test); text lines are taken only when a spanning rule
                    # lies beyond them, so the table ends at its outermost rule
                    members_core = set(members)
                    span_rules = [o for o in objs if spanning(o) and not any(o is w for w in witnesses)]
                    def over(li):
                        """the line's runs over the table: a run clear of the table sideways by more than a
                        letter height is the other column's text on the same baseline"""
                        return [r for r in by_line[li] if not (r[0][0] > hull[2] + size_px or r[0][2] < hull[0] - size_px)]
                    part = {li: over(li) for li in order if li not in members}
                    body = statistics.median(e["run_size_px"] for e in texts if e["angle"] == ang)
                    cell_size = statistics.median(e["run_size_px"] for _, e in grid_runs)
                    captions = [e["run_size_px"] for e in texts if e["angle"] == ang and is_caption_run(e)
                                and re.sub(r"\s+", "", e["text"]).lower().startswith("table")
                                and min(rd(e["box_px"])[2], hull[2]) > max(rd(e["box_px"])[0], hull[0])
                                and 0 <= hull[1] - rd(e["box_px"])[3] <= 3 * body]
                    # A display-sized caption is a heading, not the type size of a note.
                    note_size = max([cell_size] + [s for s in captions if s < PARAMS["heading_size_ratio"] * max(body, cell_size)])
                    drawn_bottom = max([hull[3]] + [rd(o["box_px"])[3] for o in span_rules
                                       if hull[0] - size_px <= rd(o["box_px"])[0] and rd(o["box_px"])[2] <= hull[2] + size_px
                                       and hull[3] - size_px <= rd(o["box_px"])[1] <= hull[3] + PARAMS["stack_gap_em"] * size_px
                                       and rd(o["box_px"])[2] - rd(o["box_px"])[0] >= PARAMS["prose_share"] * (hull[2] - hull[0])])
                    # Only beyond the drawn table: a full-width cell inside its rules stays a cell.
                    # Look ahead to a second line, so a short note or a spanning label alone is safe.
                    prose_starts = table_prose_lines([r[1] for rs in part.values() for r in rs], blocks,
                                                    [hull[0], hull[1], hull[2], drawn_bottom], body, note_size, ang,
                                                    column_share=2/3)
                    items = [("rule", rd(o["box_px"]), o) for o in span_rules] + \
                            [("line", (min(r[0][0] for r in part[li]), min(r[0][1] for r in part[li]), max(r[0][2] for r in part[li]), max(r[0][3] for r in part[li])), li) for li in order if li not in members and part[li]]
                    for direction in (-1, +1):
                        pending = []; edge = hull[1] if direction < 0 else hull[3]; main_stop = None
                        while True:
                            if direction < 0: cands = [it for it in items if it[1][3] <= edge + 1 and it[1][0] < hull[2] and it[1][2] > hull[0]]
                            else: cands = [it for it in items if it[1][1] >= edge - 1 and it[1][0] < hull[2] and it[1][2] > hull[0]]
                            if not cands: break
                            nxt = max(cands, key=lambda it: it[1][3]) if direction < 0 else min(cands, key=lambda it: it[1][1])
                            gap = (edge - nxt[1][3]) if direction < 0 else (nxt[1][1] - edge)
                            if gap > (PARAMS["note_gap_em"] if direction > 0 and nxt[0] == "line" else PARAMS["stack_gap_em"]) * size_px: break   # the wider note gap is for text lines; a rule must be directly stacked
                            if not (hull[0] - size_px <= nxt[1][0] and nxt[1][2] <= hull[2] + size_px): break   # wider than the table: not its own
                            if nxt[0] == "line" and is_caption_run(min(part[nxt[2]], key=lambda r: r[0][0])[1]): break   # the caption: rule 4's
                            if direction > 0 and nxt[0] == "line" and nxt[2] in prose_starts: break
                            if nxt[0] == "line" and any(r[1]["id"] in main_runs for r in part[nxt[2]]):   # R1: main text ends the walk
                                main_stop = statistics.median(r[1]["run_size_px"] for r in part[nxt[2]] if r[1]["id"] in main_runs); break
                            items.remove(nxt)
                            if nxt[0] == "rule":
                                for it in pending + [nxt]:
                                    hull = [min(hull[0], it[1][0]), min(hull[1], it[1][1]), max(hull[2], it[1][2]), max(hull[3], it[1][3])]
                                    if it[0] == "line": members.append(it[2])
                                    else: witnesses.append(it[2])
                                pending = []
                            else: pending.append(nxt)
                            edge = nxt[1][1] if direction < 0 else nxt[1][3]
                        # the note under the table: text lines directly stacked below the last rule, up to
                        # the first white gap wider than note_gap_em letter heights, each no wider than the table
                        if direction > 0:
                            if main_stop: pending = note_before_main_text(pending, part, note_size, main_stop)
                            for it in pending:
                                hull = [min(hull[0], it[1][0]), min(hull[1], it[1][1]), max(hull[2], it[1][2]), max(hull[3], it[1][3])]
                                members.append(it[2])
                    absorb_own_fills()   # fills under lines the walk added
                    # back to page frame: the four corners of the reading-frame hull
                    inv = {0: lambda u, v: (u, v), 90: lambda u, v: (v, -u), 270: lambda u, v: (-v, u)}[ang]
                    pts = [inv(hull[0], hull[1]), inv(hull[2], hull[3]), inv(hull[0], hull[3]), inv(hull[2], hull[1])]
                    box = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
                    tables.append({"box_px": box, "angle": ang, "lines": core + len([m for m in members if len(part.get(m, by_line[m])) == 1]), "grid_lines": core,
                                   "tracks": len(tracks), "members": [e["id"] for _, e in grid_runs] + [e["id"] for li in members for _, e in part.get(li, by_line[li]) if li not in members_core] + [x for o in witnesses for x in ids(o)] + [x for o in own_fills for x in ids(o)],
                                   "witness": [x for o in witnesses for x in ids(o)][:6], "own_fills": len(own_fills)})
            found = core >= 2 and len(tracks) >= PARAMS["table_min_tracks"] and witnesses and grid_runs
            i = j if found else i + 1
    tables += closed_two_track_tables(texts, objs, tables, blocks)
    # two grid boxes that overlap are one table (a header block over its body, a grid found twice)
    def meets(a, b):
        A, B = a["box_px"], b["box_px"]; return min(A[2], B[2]) - max(A[0], B[0]) > -2 and min(A[3], B[3]) - max(A[1], B[1]) > -2
    merged = True
    while merged:
        merged = False
        for a in tables:
            for b in tables:
                if a is b or a["angle"] != b["angle"] or not meets(a, b): continue
                A, B = a["box_px"], b["box_px"]
                a["box_px"] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])]
                a["members"] = a["members"] + [m for m in b["members"] if m not in a["members"]]; a["witness"] = (a["witness"] + b["witness"])[:6]
                a["grid_lines"] += b["grid_lines"]; a["lines"] += b["lines"]; a["tracks"] = max(a["tracks"], b["tracks"])
                tables.remove(b); merged = True; break
            if merged: break
    # Independent captions on the same level bound independent tables, even when their
    # cells share baselines. Re-measure each side of a clear drawing gutter; otherwise
    # the note walk across the combined width can swallow the two body columns below.
    separated = []
    for t in tables:
        T = t["box_px"]
        caps = sorted([b for b in blocks if b.get("text") and is_caption_label(b["text"])
                       and re.sub(r"\s+", "", b["text"]).lower().startswith("table")
                       and T[0] - 1 <= b["box_px"][0] < T[2]
                       and 0 <= T[1] - b["box_px"][1] <= 3 * statistics.median(e["size_px"] for e in texts)],
                      key=lambda b: b["box_px"][0]) if t["angle"] == 0 else []
        parts = None
        for a, b in zip(caps, caps[1:]):
            A, B = a["box_px"], b["box_px"]
            em = statistics.median(e["size_px"] for e in texts)
            if abs(A[1] - B[1]) > em or B[0] - A[2] < em: continue
            cut = (A[2] + B[0]) / 2
            if any(o["box_px"][0] < cut < o["box_px"][2] and
                   min(o["box_px"][3], T[3]) > max(o["box_px"][1], T[1])
                   for o in elements if o["kind"] in ("rule", "fill") and not o.get("overlay")): continue
            sides = []
            for lo, hi in ((T[0] - em, cut), (cut, T[2] + em)):
                es = [e for e in elements if lo <= e["box_px"][0] and e["box_px"][2] <= hi
                      and min(A[1], B[1]) - 1 <= e["box_px"][1]]
                side = [s for s in tables_from_grid(es, larger_boxes(es))
                        if min(s["box_px"][3], T[3]) > max(s["box_px"][1], T[1])]
                if not side: break
                for s in side:
                    S = s["box_px"]
                    s["members"] += [e["id"] for e in es if e["kind"] == "text" and e["id"] not in s["members"]
                                     and S[0] <= e["box_px"][0] and e["box_px"][2] <= S[2]
                                     and S[1] <= e["box_px"][1] and e["box_px"][3] <= S[3]]
                sides.extend(side)
            else:
                parts = sides; break
        separated.extend(parts or [t])
    tables = []
    for t in separated:
        if not table_grid_supported(t, elements):
            if decisions is not None:
                decisions.append(dict(box_px=t["box_px"], why="refused: no table caption or drawn grid enclosing at least two cell rows"))
            continue
        tables.append(t)
    for k, t in enumerate(tables): t["id"] = f"table:{k+1}"
    return tables

def tables_from_banded_list(elements, tables, chars):
    """A caption and repeated full-width shading identify a one-column table.
    Follow caption typography across two lines; keep the list's aligned entries
    through at most one unshaded row after its final band. This is distinct from
    prose in a shaded panel, which has no repeated, separated row bands.
    """
    texts = [e for e in elements if e["kind"] == "text" and e["angle"] == 0]
    drawn = [e for e in elements if e["kind"] in ("rule", "fill") and not e.get("overlay")]
    char_at = {c["id"]: c for c in chars}
    by_line = collections.defaultdict(list)
    for e in texts: by_line[e["line"]].append(e)
    def lbox(rs): return [min(r["box_px"][0] for r in rs), min(r["box_px"][1] for r in rs), max(r["box_px"][2] for r in rs), max(r["box_px"][3] for r in rs)]
    def ov(a0, a1, b0, b1): return min(a1, b1) - max(a0, b0)
    out = []
    for cap in texts:
        if not (is_caption_run(cap) and re.sub(r"\s+", "", cap["text"]).lower().startswith("table")): continue
        em = cap["run_size_px"]
        # A block may contain an entire one-column table. Follow the caption's
        # typography and nearby lines, not that block's membership. The title
        # beside a separately drawn label supplies the continuation's face.
        kept = [cap]; cb = cap["box_px"]
        for r in sorted(by_line[cap["line"]], key=lambda r: r["box_px"][0]):
            B = r["box_px"]
            if r is not cap and 0 <= B[0] - cb[2] <= 4 * em and abs(r["run_size_px"] - cap["run_size_px"]) < .08 * em:
                kept.append(r); cb = lbox(kept)
        def faces(rs):
            return {char_at[c]["font"] for r in rs for c in r["char_ids"] if c in char_at and char_at[c]["text"].isalpha()}
        capfaces = faces(kept[1:] or kept)
        for rs in sorted(by_line.values(), key=lambda rs: min(r["box_px"][1] for r in rs)):
            rs = [r for r in rs if cb[0] - 1 <= r["box_px"][0] and r["box_px"][2] <= cb[2] + em and r["box_px"][1] > cb[3]]
            if not rs: continue
            B = lbox(rs)
            if B[1] - cb[3] > .85 * em or (faces(rs) - capfaces): break
            if any(cb[3] <= o["box_px"][1] <= B[1] and ov(o["box_px"][0], o["box_px"][2], B[0], B[2]) > .5 * (B[2] - B[0]) for o in drawn): break
            if any(b["box_px"][0] - a["box_px"][2] > em for a, b in zip(rs, rs[1:])): break
            kept += rs; cb = lbox(kept)
        capset = {r["id"] for r in kept}
        bands = [o for o in drawn if o["kind"] == "fill" and abs(o["box_px"][0] - cb[0]) < em
                 and o["box_px"][2] <= cb[2] + em and o["box_px"][2] - o["box_px"][0] > .7 * (cb[2] - cb[0])
                 and o["box_px"][1] >= cb[3] and em < o["box_px"][3] - o["box_px"][1] < 3 * em]
        if len(bands) < 3 or min(o["box_px"][1] for o in bands) - cb[3] > 3 * em: continue
        bandbox = lbox(bands)
        if any(ov(t["box_px"][0],t["box_px"][2],bandbox[0],bandbox[2]) > em and ov(t["box_px"][1],t["box_px"][3],bandbox[1],bandbox[3]) > 0 for t in tables + out): continue
        cells = [r for r in texts if r["id"] not in capset and bandbox[0] <= r["box_px"][0] <= bandbox[0] + em
                 and r["box_px"][2] <= cb[2] + em and cb[3] < r["box_px"][1] and r["box_px"][3] <= bandbox[3] + 2 * em]
        if len(cells) < 2 * len(bands) - 1: continue
        box = lbox(cells + bands)
        out.append(dict(id=f"table:{len(tables)+len(out)+1}",box_px=box,angle=0,lines=len(cells),grid_lines=len(cells),tracks=1,
                        members=[e["id"] for e in cells + bands],witness=[],own_fills=len(bands),anchored="caption above repeated row bands",layout="banded list"))
    return out

def tables_from_caption_list(elements, tables, blocks=(), decisions=None):
    """A captioned numbered/bulleted list with repeated aligned entries is a
    one- or two-column table, even without ruling. Read the caption separately
    from its block: shading may join its label to the first list column. Stop
    at prose or the first large gap; a short definition note can follow the list.
    """
    texts = [e for e in elements if e["kind"] == "text" and e["angle"] == 0]
    def hull(es):
        bs = [e["box_px"] for e in es]
        return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    def marker(e): return re.match(r"^\s*(?:\d+[.)]|[•●▪◦‣–])\s+\S", unicodedata.normalize("NFKC", e["text"]))
    out = []
    for cap in table_caption_runs(texts):
        if cap["angle"]: continue
        em = cap["run_size_px"]; C = cap["box_px"]
        caps = [e for e in texts if e["line"] == cap["line"] and e["box_px"][0] >= C[0] - 1]
        caps.sort(key=lambda e: e["box_px"][0])
        kept = []; edge = C[2]
        for e in caps:
            if e["box_px"][0] - edge > 4 * em: break
            kept.append(e); edge = e["box_px"][2]
        if not kept: continue
        C = hull(kept)
        # Follow caption continuations only before the first marked entry.
        below = sorted([e for e in texts if C[0] - 1 <= e["box_px"][0] and e["box_px"][2] <= C[2] + em
                        and e["box_px"][1] >= C[3]], key=lambda e: (e["box_px"][1], e["box_px"][0]))
        cells = []; last = C[3]
        for e in below:
            B = e["box_px"]
            if B[1] - last > PARAMS["caption_gap_em"] * em: break
            if not cells and not marker(e):
                if B[1] - last > em: break
                kept.append(e); C = hull(kept); last = C[3]; continue
            if not marker(e): break
            cells.append(e); last = max(last, B[3])
        if len(cells) < 3: continue
        starts = []
        for e in sorted(cells, key=lambda e: e["box_px"][0]):
            x = e["box_px"][0]
            if not starts or x - starts[-1][0] > em: starts.append([x, []])
            starts[-1][1].append(e)
        if not 1 <= len(starts) <= 2 or any(len(rs) < 2 for _, rs in starts): continue
        B = hull(cells)
        if any(min(t["box_px"][2], B[2]) > max(t["box_px"][0], B[0]) and min(t["box_px"][3], B[3]) > max(t["box_px"][1], B[1]) for t in list(tables) + out): continue
        own = [e for e in elements if e["kind"] in ("rule", "fill") and not e.get("overlay") and C[0] - em <= e["box_px"][0]
               and e["box_px"][2] <= C[2] + em and C[3] <= e["box_px"][1] and e["box_px"][3] <= B[3] + em]
        notes = [e for e in below if e not in cells and B[3] <= e["box_px"][1] <= B[3] + 1.5 * em
                 and e["run_size_px"] < .95 * statistics.median(c["run_size_px"] for c in cells)]
        out.append(dict(id=f"table:{len(tables)+len(out)+1}", box_px=hull(cells + own + notes), angle=0,
                        lines=len({e["line"] for e in cells}), grid_lines=len({e["line"] for e in cells}), tracks=len(starts),
                        members=[e["id"] for e in cells + own + notes], witness=[], own_fills=len(own), anchored="caption above aligned list entries"))
        # Expose the witnessed split label to the existing float predicate,
        # without changing its native text or character ids. Bound its caption
        # block too: shading must not make the first list column a caption.
        source = next(e for e in texts if e["id"] == cap["id"])
        if not is_caption_run(source): source["table_caption_label"] = cap["text"]
        caption_block = next((b for b in blocks if cap["id"] in b["members"]), None)
        if caption_block is not None:
            capids = {e["id"] for e in kept}
            caption_block.update(box_px=hull(kept), members=[e["id"] for e in kept],
                                 kinds=["text"], text_lines=len({e["line"] for e in kept}),
                                 text=" ".join(e["text"] for e in kept)[:80])
            for b in blocks:
                if b is not caption_block: b["members"] = [m for m in b["members"] if m not in capids]
            if isinstance(blocks, list): blocks[:] = [b for b in blocks if b["members"]]
        if decisions is not None:
            decisions.append(dict(box_px=out[-1]["box_px"], why="bounded: captioned list ends after its aligned entries and note"))
    return out


def tables_from_caption_bands(elements, blocks, tables, decisions=None):
    """Rule 3: a Table label inside a shallow shaded band anchors connected row bands.
    The fill is independent caption evidence even without a colon, period or font change.
    Require at least two baselines of separated cells beneath it; stop where the connected
    shading stops (one unshaded row may separate alternating bands). Replace an overlapping grid only when its drawing has grown outside
    these bands. This prevents a small table from absorbing a neighbouring chart.
    """
    texts=[e for e in elements if e['kind']=='text' and e['angle']==0]
    fills=[e for e in elements if e['kind']=='fill']
    out=[]
    def hull(es):
        bs=[e['box_px'] for e in es]
        return [min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)]
    for cap in texts:
        match=re.match(r'^Table\s+(\d+[A-Za-z]?)\b\s+\S',cap['text'],re.I)
        if not match: continue
        C=cap['box_px'];em=cap['run_size_px']
        bands=[f for f in fills if (b:=f['box_px'])[0]<=C[0] and C[2]<=b[2]
               and b[1]<=C[1] and C[3]<=b[3] and b[3]-b[1]<3*em]
        if not bands: continue
        seed=min(bands,key=lambda f:f['box_px'][2]-f['box_px'][0]);B=list(seed['box_px']);owned=[seed]
        while True:
            more=[f for f in fills if f not in owned and (b:=f['box_px'])[0]>=B[0]-1
                  and b[2]<=B[2]+1 and B[3]-1<=b[1]<=B[3]+1.5*em and b[3]>B[3]
                  and .5*em<b[3]-b[1]<5*em and b[2]-b[0]>.1*(B[2]-B[0])]
            if not more: break
            owned+=more;B[3]=max(f['box_px'][3] for f in more)
        cells=[e for e in texts if B[0]<=e['box_px'][0] and e['box_px'][2]<=B[2]
               and seed['box_px'][3]<=e['box_px'][1] and e['box_px'][3]<=B[3]]
        byline=collections.defaultdict(list)
        for e in cells: byline[e['line']].append(e)
        separated=[rs for rs in byline.values() if any(b['box_px'][0]-a['box_px'][2]>em
                   for a,b in zip(sorted(rs,key=lambda e:e['box_px'][0]),sorted(rs,key=lambda e:e['box_px'][0])[1:]))]
        if len(separated)<2: continue
        overlapping=[t for t in tables if min(t['box_px'][2],B[2])>max(t['box_px'][0],B[0])
                     and min(t['box_px'][3],B[3])>max(t['box_px'][1],B[1])]
        if any(t['box_px'][1]>=seed['box_px'][3]-1 and t['box_px'][3]<=B[3]+1 for t in overlapping): continue
        if any(set(t['members']) & {e['id'] for e in texts if e not in cells and e is not cap}
               for t in overlapping): continue
        for t in overlapping: tables.remove(t)
        cap['table_caption_label']='Table '+match[1]+'.'
        # The caption's own background is not a separate graphic competing with
        # the actual grid for rule 4's nearest-graphic pairing.
        for b in blocks: b['members']=[m for m in b['members'] if m not in (cap['id'],seed['id'])]
        blocks[:]=[b for b in blocks if b['members']]
        blocks.append(dict(id='table-caption:'+cap['id'],box_px=C,members=[cap['id']],
                           kinds=['text'],text_lines=1,text=cap['text']))
        B[1]=seed['box_px'][3]
        own=[e for e in elements if e['kind'] in ('rule','fill') and B[0]-1<=e['box_px'][0]
             and e['box_px'][2]<=B[2]+1 and B[1]-1<=e['box_px'][1] and e['box_px'][3]<=B[3]+1]
        out.append(dict(id=f'table:band:{cap["id"]}',box_px=B,angle=0,lines=len(byline),grid_lines=len(separated),
                        tracks=max(map(len,separated)),members=[e['id'] for e in cells+own],
                        witness=[seed['id']],own_fills=len(own),anchored='caption above connected shaded rows'))
        if decisions is not None: decisions.append(dict(box_px=B,why='bounded: caption band and connected shaded rows'))
    return out


def bounded_caption_tables(elements, blocks, tables, decisions=None, fallback=False):
    """Rule 3: horizontal table borders own the complete intervening lettering.

    A punctuated caption, a border immediately below it, and a later border
    with the same endpoints bound a table without requiring a ruled cell grid.
    The next caption ends the search. Split saved ink islands at this boundary
    so justified prose beside the table cannot become a cell or a caption.
    Newly recognized Roman captions take precedence over unlabelled grid seeds.
    For Arabic captions this is a fallback after normal detection, only where
    no existing table owns the lettering. Recovered regions are explicitly
    unstructured; established cell grids keep their existing recovery path.
    """
    def hull(es):
        bs=[e['box_px'] for e in es]
        return [min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)]
    # A caption may itself have been merged across the adjacent prose gutter.
    split={}
    for e in elements:
        if e['kind']!='text' or not e.get('ink_parts'): continue
        if not fallback and any(re.match(r'^Table\s+[IVXLCDM]+[.:](?:\s|$)',v['text'],re.I) for v in e['ink_parts']):
            split[e['id']]=[dict(e,**v,id=e['id'] if i==0 else e['id']+f':tablepart:{i}') for i,v in enumerate(e['ink_parts'])]
    def replace(parts):
        for es in parts.values():
            for e in es:
                e.pop('ink_parts',None)
                if 'region_parts' in e:
                    e['region_parts']=[{k:e[k] for k in ('id','box_px','text','char_ids','run_size_px','region') if k in e}]
        elements[:]=[v for e in elements for v in parts.get(e['id'],[e])]
        for b in blocks: b['members']=[v['id'] for m in b['members'] for v in parts.get(m,[{'id':m}])]
        for t in tables: t['members']=[v['id'] for m in t['members'] for v in parts.get(m,[{'id':m}])]
    replace(split)
    texts=[e for e in elements if e['kind']=='text' and e['angle']==0]
    caps=[e for e in texts if re.match(r'^Table\s+(?:\d+[A-Za-z]?|[IVXLCDM]+)[.:](?:\s|$)',e['text'],re.I)]
    borders=[e for e in elements if e['kind'] in ('rule','fill')]
    out=[]
    for cap in caps:
        roman=bool(re.match(r'^Table\s+[IVXLCDM]+[.:]',cap['text'],re.I))
        if roman==fallback: continue
        C=cap['box_px'];em=cap['run_size_px']
        near=[e for e in borders if (b:=e['box_px'])[3]-b[1]<.25*em and b[2]-b[0]>8*em
              and abs(b[0]-C[0])<em and b[2]>=C[2]-em and 0<=b[1]-C[3]<6*em]
        if not near: continue
        top=min(near,key=lambda e:e['box_px'][1]);T=top['box_px']
        end=min((e['box_px'][1] for e in caps if e is not cap and e['box_px'][1]>T[1]
                 and T[0]-em<=e['box_px'][0]<T[2]),default=float('inf'))
        aligned=[e for e in borders if (b:=e['box_px'])[3]-b[1]<.25*em
                 and abs(b[0]-T[0])<1 and abs(b[2]-T[2])<1 and T[3]+em<b[1]<end]
        if not aligned: continue
        bottom=max(aligned,key=lambda e:e['box_px'][3])
        R=[T[0],C[3],T[2],bottom['box_px'][3]]
        if fallback and any(min(t['box_px'][2],R[2])>max(t['box_px'][0],R[0]) and
                            min(t['box_px'][3],R[3])>max(t['box_px'][1],R[1]) for t in tables): continue
        # Some PDFs position lettering above their drawing coordinates. The
        # caption's typography, not the first border alone, separates its last
        # line from the header. A separated cell row is never a continuation.
        above=[e for e in texts if R[0]-em<=e['box_px'][0] and e['box_px'][2]<=R[2]+em
               and C[1]-.3*em<=e['box_px'][1] and e['box_px'][3]<T[1]]
        byline=collections.defaultdict(list)
        for e in above:byline[e['line']].append(e)
        separated={li for li,rs in byline.items() if len(rs)>1 and
                   any(b['box_px'][0]-a['box_px'][2]>em for a,b in
                       zip(sorted(rs,key=lambda e:e['box_px'][0]),sorted(rs,key=lambda e:e['box_px'][0])[1:]))}
        cm=[e for e in above if e['line'] not in separated and e['run_size_px']>=.95*em]
        if cap not in cm:cm.append(cap)
        capids={e['id'] for e in cm}
        R[1]=max(e['box_px'][3] for e in cm)
        # A distant same-width page rule cannot bridge a prose restart: larger
        # continuous lines filling this span are a boundary outside the table.
        inside=lambda b: R[0]-1<=b[0] and b[2]<=R[2]+1 and R[1]-1<=b[1] and b[3]<=R[3]+1
        parts={}
        for e in texts:
            if not e.get('ink_parts'): continue
            own=[inside(v['box_px']) for v in e['ink_parts']]
            if any(own) and not all(own):
                parts[e['id']]=[dict(e,**v,id=e['id'] if i==0 else e['id']+f':tablepart:{i}') for i,v in enumerate(e['ink_parts'])]
        replace(parts);texts=[e for e in elements if e['kind']=='text' and e['angle']==0]
        cells=[e for e in texts if e['id'] not in capids and inside(e['box_px'])]
        # lane r2-prosetable: page-wide borders round a column band own no prose columns: two or more equal
        # columns of filled body-prose lines between them are the page's text, never the table's lettering;
        # the table keeps what remains, within its own width
        prose_tracks=prose_column_tracks([(e['box_px'],e) for e in cells],main_prose_run_ids(texts,blocks),em,
                                         [(e['box_px'],e) for e in texts],{m:b for b in blocks for m in b['members']},
                                         [e['box_px'] for e in borders])
        if len(prose_tracks)>=2:
            cells=[e for e in cells if not any(t0<=e['box_px'][0] and e['box_px'][2]<=t1 for t0,t1 in prose_tracks)]
            if decisions is not None:decisions.append(dict(box_px=list(R),why="bounded: equal columns of body prose between the borders are the page's columns"))
            if len({e['line'] for e in cells})<2: continue
            R=[min(e['box_px'][0] for e in cells),R[1],max(e['box_px'][2] for e in cells),R[3]]
        if len({e['line'] for e in cells})<2: continue
        size=statistics.median(e['run_size_px'] for e in cells)
        prose=[e for e in cells if e['run_size_px']>1.1*size and len(e['text'].split())>=6
               and e['box_px'][2]-e['box_px'][0]>.7*(R[2]-R[0])]
        if len(prose)>=2: continue
        ids={e['id'] for e in cells}
        overlaps=[t for t in tables if ids.intersection(t['members'])]
        existing=set(m for t in overlaps for m in t['members'] if m.startswith('run:'))
        notes=[e for e in texts if e['run_size_px']<.95*em and R[0]-1<=e['box_px'][0]
               and e['box_px'][2]<=R[2]+1 and R[3]<=e['box_px'][1] and e['box_px'][3]<=R[3]+3*em
               and e['box_px'][3]<end]
        cells += notes
        if notes:R[3]=max(e['box_px'][3] for e in notes)
        for t in overlaps: tables.remove(t)
        for b in blocks: b['members']=[m for m in b['members'] if m not in capids]
        blocks[:]=[b for b in blocks if b['members']]
        blocks.append(dict(id='table-caption:'+cap['id'],box_px=hull(cm),members=[e['id'] for e in cm],
            kinds=['text'],text_lines=len({e['line'] for e in cm}),text=' '.join(e['text'] for e in sorted(cm,key=lambda e:(e['box_px'][1],e['box_px'][0])))[:80]))
        own=[e for e in borders if inside(e['box_px'])]
        t=dict(id='table:bounded:'+cap['id'],box_px=R,angle=0,members=[e['id'] for e in cells+own],
            lines=len({e['line'] for e in cells}),grid_lines=0,tracks=0,witness=[top['id'],bottom['id']],
            own_fills=len(own),layout='unstructured',_copy_exact=True,anchored='caption and matching outer borders')
        out.append(t)
        if decisions is not None:decisions.append(dict(box_px=R,why='bounded: complete captioned lettering between matching outer borders'))
    return out


def tables_from_caption(elements, blocks, tables, chars, decisions=None):
    """Rule 3, from the caption: matching outer borders first bound newly recognized Roman
    captions, including every header and note line but excluding adjacent prose. Regions
    without proven cells are unstructured. Existing Arabic-caption grids keep their
    reconstruction path; missing tables get the same border fallback after detection.
    Then recover small shaded tables with tables_from_caption_bands.
    A label inside a caption band followed by two separated cell rows is sufficient caption
    evidence even without punctuation or a font change; alternating row shading bounds it.
    Then a "Table n" caption (rule 4's label test) that has no table of the grid
    test beside it anchors one (a table beside it with another Table caption at its top edge is that
    caption's). The table is the stack of lines directly under the caption (or, failing
    that, directly over it), within the caption's width or the width of the table's own drawn lines and
    shading next to the caption, down to a white gap wider than caption_gap_em letter heights that no drawn
    object bridges, a line of prose (one run across most of the width at the body size or larger), a
    heading, or the next caption. Its columns are the white channels that run down it: an x interval at
    least half a letter wide where at most a few rows have ink, with rows inked on both sides of it (two at
    least); it is a
    table when it has two or more rows and two or more columns. The caption is what keeps a two-column
    page of prose from being taken for a table: running text does not open with "Table 3". Upright
    captions only. The drawn lines and shading inside the box are the table's own, not journal art.
    The caption's block is the caption only down to its first line of separate cells (ink in two or more
    pieces a letter height apart): where the caption and its table share one block (a table set in a
    shaded panel), the table starts under the caption's own lines. A table whose caption lies inside a
    shaded panel ends where the panel ends: the fills holding the caption, with those starting within a
    letter height of it on the table's side. Two consecutive body-sized lines, larger than the cells
    and ordinary caption type, filling a text column outside the connected drawn table trim an otherwise supported table even
    when another column shares their baselines; the column is their rule-2 block's width, at least
    a third of the candidate table's width. The first four cell rows also establish channels:
    body-sized lines crossing them end the table even at the cells' size. Trim these prose lines
    before the final channel count: following body columns must not erase a table's channels.
    Touching header fills establish its entire width; a fill must contain the caption vertically
    to count as its enclosing panel. Lines enclosed by
    the table's connected spanning rules or fills remain cells. A distant footer cannot extend
    that protection, and a drawn object covering rejected prose cannot regrow the box."""
    tables.extend(bounded_caption_tables(elements, blocks, tables, decisions))
    tables.extend(tables_from_caption_bands(elements, blocks, tables, decisions))
    GAP_EM, CHANNEL_EM, INK_ROWS, PROSE_SHARE = PARAMS["caption_gap_em"], PARAMS["channel_em"], PARAMS["channel_ink_rows"], PARAMS["prose_share"]
    texts = [e for e in elements if e["kind"] == "text" and e["angle"] == 0]
    if not texts: return []
    drawn = [e for e in elements if e["kind"] in ("rule", "fill") and not e.get("overlay")]
    body = statistics.median(e["run_size_px"] for e in texts)
    char_at = {c["id"]: c for c in chars}
    block_of = {m: b for b in blocks for m in b["members"]}
    by_line = collections.defaultdict(list)
    for e in texts: by_line[e["line"]].append(e)
    def lbox(rs): return [min(r["box_px"][0] for r in rs), min(r["box_px"][1] for r in rs), max(r["box_px"][2] for r in rs), max(r["box_px"][3] for r in rs)]
    def ov(a0, a1, b0, b1): return min(a1, b1) - max(a0, b0)
    prose_blocks = prose_column_blocks(texts, blocks, body)
    main_runs = None
    out = []
    for cap in texts:
        if not (is_caption_run(cap) and re.sub(r"\s+", "", cap["text"]).lower().startswith("table")): continue
        blk = block_of.get(cap["id"])
        em = cap["size_px"]
        capset = set(blk["members"]) if blk else set()
        cb = blk["box_px"] if blk and blk["box_px"][1] >= cap["box_px"][1] - 1 else cap["box_px"]
        if blk:
            # the caption's own lines: the block's lines from the caption's down to the first line of separate
            # cells; the block's runs from that line on are the table's rows, not the caption
            mine = collections.defaultdict(list)
            for r in texts:
                if r["id"] in capset and r["box_px"][1] >= cap["box_px"][1] - 1: mine[r["line"]].append(r)
            kept, rest = [], []
            for li in sorted(mine, key=lambda li: min(r["box_px"][1] for r in mine[li])):
                rs = sorted(mine[li], key=lambda r: r["box_px"][0])
                if not rest and (li == cap["line"] or not any(b_["box_px"][0] - a_["box_px"][2] >= em for a_, b_ in zip(rs, rs[1:]))): kept += rs
                else: rest += rs
            if rest and kept:
                capset -= {r["id"] for r in rest}; cb = lbox(kept)
        holding = [o["box_px"] for o in drawn if o["kind"] == "fill" and o["box_px"][0] - em <= cb[0] and cb[2] <= o["box_px"][2] + em
                   and o["box_px"][1] <= cb[1] and cb[3] <= o["box_px"][3]]
        def captioned(t):   # another Table caption stands at t's top edge (within three letter heights of it, above or inside): t is that caption's
            T = t["box_px"]
            return any(o is not cap and is_caption_run(o) and re.sub(r"\s+", "", o["text"]).lower().startswith("table") and ov(o["box_px"][0], o["box_px"][2], T[0], T[2]) > 0
                       and ov(o["box_px"][1], o["box_px"][3], T[1] - 3 * em, T[1] + 3 * em) > 0 for o in texts)
        if any(ov(t["box_px"][0], t["box_px"][2], cb[0], cb[2]) > 0 and (ov(t["box_px"][1], t["box_px"][3], cb[1] - 3 * em, cb[3] + 3 * em) > 0) and not captioned(t) for t in list(tables) + out): continue
        for direction in (+1, -1):
            edge = cb[3] if direction > 0 else cb[1]
            near = [o for o in drawn if o["box_px"][0] >= cb[0] - 2 * em and o["box_px"][0] <= cb[0] + 2 * em
                    and ((direction > 0 and -em <= o["box_px"][1] - edge <= 3 * em) or (direction < 0 and -em <= edge - o["box_px"][3] <= 3 * em))]
            # Cell-by-cell header shading defines the full width, including
            # touching cells whose left edges are far from the caption.
            for _ in drawn:
                extra = [o for o in drawn if o not in near and any(abs(o["box_px"][1] - n["box_px"][1]) <= 1 and abs(o["box_px"][3] - n["box_px"][3]) <= 1 and ov(o["box_px"][0], o["box_px"][2], n["box_px"][0] - 1, n["box_px"][2] + 1) >= 0 for n in near)]
                if not extra: break
                near.extend(extra)
            s0 = cb[0] - em; s1 = max([cb[2]] + [o["box_px"][2] for o in near]) + em
            # the caption's panel: the fills holding the caption and those that start within a letter height of it on this side
            panel = None
            if holding:
                side = holding + [o["box_px"] for o in drawn if o["kind"] == "fill" and ov(o["box_px"][0], o["box_px"][2], cb[0], cb[2]) > 0
                                  and ((direction > 0 and abs(o["box_px"][1] - cb[3]) <= em) or (direction < 0 and abs(o["box_px"][3] - cb[1]) <= em))]
                panel = [min(x[0] for x in side), min(x[1] for x in side), max(x[2] for x in side), max(x[3] for x in side)]
            cand = []
            for rs in by_line.values():
                # a run reaching past the span that belongs to a column of body prose centred beyond it is the
                # neighbouring text column, not a cell (AM02 p6: the right column starts inside the caption's
                # drawn width and runs 12 letter heights past it)
                inside = [r for r in rs if s0 <= r["box_px"][0] <= s1
                          and not (r["box_px"][0] >= s1 - em and r["box_px"][2] > s1 + em)
                          and not (r["box_px"][2] > s1 + em and block_of.get(r["id"], {}).get("id") in prose_blocks
                                   and (block_of[r["id"]]["box_px"][0] + block_of[r["id"]]["box_px"][2]) / 2 > s1)
                          and r["id"] != cap["id"] and r["id"] not in capset]
                if not inside: continue
                b = lbox(inside)
                if (direction > 0 and b[1] >= edge - 1) or (direction < 0 and b[3] <= edge + 1): cand.append((b, inside))
            cand.sort(key=lambda x: x[0][1] * direction)
            # A page-wide table can be followed by two columns on one baseline. Neither run fills
            # the table width, so test each column's block and require two consecutive prose lines.
            structure = [o["box_px"] for o in near
                         if ov(o["box_px"][0], o["box_px"][2], s0, s1) >= PROSE_SHARE * (s1 - s0)]
            # Only connected drawing belongs to this table; a distant footer rule cannot
            # protect an intervening paragraph from the prose boundary test.
            for _ in drawn:
                extra = [o["box_px"] for o in drawn if o["box_px"] not in structure
                         and ov(o["box_px"][0], o["box_px"][2], s0, s1) >= PROSE_SHARE * (s1 - s0)
                         and any(ov(o["box_px"][1], o["box_px"][3], b[1] - em, b[3] + em) >= 0 for b in structure)]
                if not extra: break
                structure.extend(extra)
            drawn_top = min((b[1] for b in structure), default=edge)
            drawn_bottom = max((b[3] for b in structure), default=edge)
            cell_sizes = [r["run_size_px"] for b, rs in cand for r in rs
                          if drawn_top <= (r["box_px"][1] + r["box_px"][3]) / 2 <= drawn_bottom]
            cell_size = statistics.median(cell_sizes or [r["run_size_px"] for _, rs in cand[:1] for r in rs] or [body])
            note_size = max(cell_size, cap["run_size_px"] if cap["run_size_px"] < PARAMS["heading_size_ratio"] * max(body, cell_size) else cell_size)
            witnesses = prose_witnesses(texts, blocks, prose_blocks, (s0, s1), structure,
                                        [o["box_px"] for o in drawn if o["kind"] == "rule"],
                                        [t for t in texts if t is not cap and is_caption_run(t)],
                                        drawn_bottom if direction > 0 else drawn_top, direction, em)
            prose_starts = table_prose_lines([r for _, rs in cand for r in rs], blocks,
                                            [s0, drawn_top, s1, drawn_bottom], body, note_size, direction=direction, prose_blocks=witnesses)
            rows = []; last = edge
            for b, inside in cand:
                gap = (b[1] - last) if direction > 0 else (last - b[3])
                lo, hi = (last, b[1]) if direction > 0 else (b[3], last)
                bridged = any(ov(o["box_px"][0], o["box_px"][2], s0, s1) > 0 and lo - 1 <= (o["box_px"][1] + o["box_px"][3]) / 2 <= hi + 1 for o in drawn)
                if gap > GAP_EM * em and not bridged: break
                if panel and ((direction > 0 and b[3] > panel[3] + em) or (direction < 0 and b[1] < panel[1] - em)): break   # out of the caption's panel
                first = min(inside, key=lambda r: r["box_px"][0])
                if is_caption_run(first): break
                if any(r["run_size_px"] >= PARAMS["heading_size_ratio"] * body for r in inside): break
                if len(inside) == 1 and inside[0]["box_px"][2] - inside[0]["box_px"][0] >= PROSE_SHARE * (s1 - s0) and inside[0]["run_size_px"] >= 0.97 * body: break
                rows.append((b, inside)); last = b[3] if direction > 0 else b[1]
            if len(rows) < 2: continue
            # lane r2-prosetable: a page-wide rule under the caption widens the span over the page's text columns;
            # two or more equal columns of filled body-prose lines under it are the page's columns, not rows of
            # the table: their runs leave the rows, and the table is what remains
            if main_runs is None: main_runs = main_prose_run_ids(texts, blocks)
            prose_tracks = prose_column_tracks([(r["box_px"], r) for _, rs in rows for r in rs], main_runs, em, [(r["box_px"], r) for r in texts], block_of,
                                               [o["box_px"] for o in drawn])
            if len(prose_tracks) >= 2:
                if decisions is not None:
                    decisions.append(dict(box_px=lbox([r for _, rs in rows for r in rs]), why="bounded: equal columns of body prose under the caption are the page's columns"))
                rows = [(lbox(k), k) for _, rs in rows if (k := [r for r in rs if not any(t0 <= r["box_px"][0] and r["box_px"][2] <= t1 for t0, t1 in prose_tracks)])]
                if len(rows) < 2: continue
            # columns: white channels down the rows, from the characters themselves
            x0 = int(min(b[0] for b, _ in rows)); x1 = int(max(b[2] for b, _ in rows)) + 1
            ink = []
            for b, inside in rows:
                row = bytearray(x1 - x0 + 1)
                for r in inside:
                    for cid in r["char_ids"]:
                        c = char_at.get(cid)
                        if c is None or not c["text"].strip(): continue
                        for x in range(max(x0, int(c["x0"])), min(x1, int(c["x1"])) + 1): row[x - x0] = 1
                ink.append(row)
            # the columns come from the rows that have separate cells: ink in two or more pieces with a white
            # gap of a letter height or more between them; a note line across the table, or a row with one
            # cell only, says nothing about where the columns are
            def pieces(rw):
                segs = 0; gap = 10 ** 9
                for i, v in enumerate(rw):
                    if v:
                        if gap >= em: segs += 1
                        gap = 0
                    else: gap += 1
                return segs
            def channels(ink):
                cells = [rw for rw in ink if pieces(rw) >= 2]
                n = len(cells); gaps = []; x = 0; width = x1 - x0 + 1
                if n < 2: return []
                share = [sum(rw[i] for rw in cells) / n for i in range(width)]
                while x < width:
                    if share[x] <= INK_ROWS:
                        y = x
                        while y < width and share[y] <= INK_ROWS: y += 1
                        if (y - x) >= CHANNEL_EM * em and x > 0 and y < width:
                            both = sum(1 for rw in cells if any(rw[:x]) and any(rw[y:]))
                            if both >= 2: gaps.append((x0 + x, x0 + y))
                        x = y
                    else: x += 1
                return gaps
            def columns(ink): return len(channels(ink)) + 1 if sum(pieces(rw) >= 2 for rw in ink) >= 2 else 0
            cols = columns(ink)
            # The first cell rows establish the column channels. Later body-sized lines
            # crossing those channels cannot turn two prose columns into new table tracks,
            # even when the prose uses the same type size as the cells.
            seed = [rw for rw in ink if pieces(rw) >= 2][:4]
            prose_starts |= table_prose_lines([r for _, rs in rows for r in rs], blocks,
                                             [s0, drawn_top, s1, drawn_bottom], body, note_size,
                                             direction=direction, channels=channels(seed), prose_blocks=witnesses)
            # Remove following prose before the final channel test; otherwise
            # its long lines can erase the channels through a real table above.
            cut = next((i for i, (_, rs) in enumerate(rows) if any(r["line"] in prose_starts for r in rs)), len(rows))
            if cut < len(rows):
                if decisions is not None:
                    decisions.append(dict(box_px=lbox([r for _, rs in rows for r in rs]), why="bounded: following text-column prose"))
                rows = rows[:cut]; cols = columns(ink[:cut])
            if cols < 2: continue
            box = lbox([r for _, inside in rows for r in inside])
            excluded = [r for _, rs in cand for r in rs if r["line"] in prose_starts]
            own = [o for o in drawn if ov(o["box_px"][0], o["box_px"][2], box[0], box[2]) > 0
                   and box[1] - em <= (o["box_px"][1] + o["box_px"][3]) / 2 <= box[3] + em
                   and not any(ov(o["box_px"][0], o["box_px"][2], r["box_px"][0], r["box_px"][2]) > 0
                               and ov(o["box_px"][1], o["box_px"][3], r["box_px"][1], r["box_px"][3]) > 0 for r in excluded)]
            for o in own: box = [min(box[0], o["box_px"][0]), min(box[1], o["box_px"][1]), max(box[2], o["box_px"][2]), max(box[3], o["box_px"][3])]
            if decisions is not None:
                outside = [r for r in texts if s1 - em <= r["box_px"][0] <= s1 and r["box_px"][2] > s1 + em
                           and min(r["box_px"][3], box[3]) > max(r["box_px"][1], box[1])]
                if outside:
                    decisions.append(dict(box_px=lbox(outside + [dict(box_px=box)]), bounded_box_px=list(box),
                                          why="bounded: caption and drawing width exclude the neighbouring column"))
            out.append({"id": f"table:{len(tables) + len(out) + 1}", "box_px": box, "angle": 0, "lines": len(rows), "grid_lines": len(rows), "tracks": cols,
                        "members": [r["id"] for _, inside in rows for r in inside] + [x for o in own for x in (o.get("parts") or [o["id"]])],
                        "witness": [], "own_fills": len(own), "anchored": "caption " + ("above" if direction > 0 else "below") + " the table"})
            break
    out += tables_from_banded_list(elements, list(tables) + out, chars)
    out += tables_from_caption_list(elements, list(tables) + out, blocks, decisions)
    out += bounded_caption_tables(elements, blocks, list(tables)+out, decisions, fallback=True)
    return out

def tables_from_caption_rules(elements, tables):
    """Rule 4: recover a captioned ruled table with vertically merged cells.
    An upright Table label immediately above a horizontal rule anchors a table when a second
    rule has matching ends and an interior vertical divider joins both. At least two text
    lines must lie on each side of that divider, no run may cross it, and another horizontal
    rule inside must reach it. All cells fit inside the ruled rectangle; another caption or
    an existing table inside it prevents recovery. This drawn witness does not require cells
    in different columns to share baselines. The caption and cells remain separate elements.
    """
    rules = [e for e in elements if e["kind"] == "rule" and not e.get("overlay")]
    rules += joined_rules(rules)
    horizontal = sorted([e for e in rules if e["box_px"][2] - e["box_px"][0] > e["box_px"][3] - e["box_px"][1]], key=lambda e: e["box_px"][1])
    vertical = [e for e in rules if e not in horizontal]
    texts = [e for e in elements if e["kind"] == "text" and e["angle"] == 0]
    gap = px(PARAMS["rule_join_pt"])
    out = []
    for cap in texts:
        if not is_caption_run(cap) or not re.sub(r"\s+", "", cap["text"]).lower().startswith("table"): continue
        C = cap["box_px"]; em = cap["run_size_px"]
        for top in horizontal:
            T = top["box_px"]
            if not (T[0] - gap <= C[0] and C[2] <= T[2] + gap and 0 <= T[1] - C[3] <= PARAMS["caption_gap_em"] * em): continue
            found = False
            for bottom in horizontal:
                B = bottom["box_px"]
                if B[1] <= T[3] + 2 * em or abs(T[0] - B[0]) > gap or abs(T[2] - B[2]) > gap: continue
                box = [min(T[0], B[0]), T[1], max(T[2], B[2]), B[3]]
                if any(min(t["box_px"][2], box[2]) > max(t["box_px"][0], box[0]) and min(t["box_px"][3], box[3]) > max(t["box_px"][1], box[1]) for t in list(tables) + out): continue
                cells = [e for e in texts if box[0] - gap <= e["box_px"][0] and e["box_px"][2] <= box[2] + gap and box[1] <= e["box_px"][1] and e["box_px"][3] <= box[3]]
                if any(is_caption_run(e) for e in cells): continue
                dividers = []
                for v in vertical:
                    V = v["box_px"]; x = (V[0] + V[2]) / 2
                    if not (T[0] + em < x < T[2] - em and abs(V[1] - T[3]) <= gap and abs(V[3] - B[1]) <= gap): continue
                    left = [e for e in cells if e["box_px"][2] <= x]; right = [e for e in cells if e["box_px"][0] >= x]
                    if len(left) + len(right) != len(cells) or min(len({e["line"] for e in left}), len({e["line"] for e in right})) < 2: continue
                    if any(T[3] < h["box_px"][1] < B[1] and h["box_px"][0] - gap <= x <= h["box_px"][2] + gap for h in horizontal): dividers.append(v)
                if not dividers: continue
                own = [e for e in elements if e["kind"] in ("rule", "fill") and not e.get("overlay") and box[0] - gap <= e["box_px"][0] and e["box_px"][2] <= box[2] + gap and box[1] - gap <= e["box_px"][1] and e["box_px"][3] <= box[3] + gap]
                out.append({"id": f"table:{len(tables) + len(out) + 1}", "box_px": box, "angle": 0,
                            "lines": len({e["line"] for e in cells}), "grid_lines": len({e["line"] for e in cells}), "tracks": len(dividers) + 1,
                            "members": [e["id"] for e in cells + own], "witness": [top["id"], bottom["id"]] + [v["id"] for v in dividers],
                            "own_fills": len(own), "anchored": "caption above a ruled table with merged cells"})
                found = True; break
            if found: break
    return out

def figure_caption_face(e):
    """The caption text's face, excluding a separately typeset Figure label."""
    label = re.match(r'^\s*(?:Figure|Fig\.?)\s*\d+[A-Za-z]?[.:]?\s*', e['text'], re.I)
    start = label.end() if label else 0
    spans = e.get('font_spans', [])
    weights = collections.Counter()
    for span in spans:
        weights[span['font']] += max(0, span['end'] - max(start, span['start']))
    if weights and max(weights.values()) > 0: return weights.most_common(1)[0][0]
    fonts = e.get('font', '')
    return fonts[-1] if isinstance(fonts, list) and fonts else fonts


def split_figure_caption_blocks(elements, blocks, tables=()):
    """Expose a Figure label buried below short drawing labels in a rule-2 block.

    Upright labels preceded by short drawing labels qualify. Mixed-case
    labels additionally need numbered punctuation or a distinct label face,
    and a substantial drawing in the source block to distinguish a caption
    from a figure mention. The
    caption begins at its label, including when drawing labels share its baseline.
    Only consecutive lines aligned by left edge or center in the caption text's
    face and size continue it. A face introduced within an accepted caption line can continue below,
    preserving a bold title followed by regular caption text. A larger prose
    face ends it. Long preceding labels qualify only in a
    different face and below 95% of caption size, with the same drawing evidence
    as a mixed-case label. This keeps a page-sized backing from turning a body
    column into drawing labels. A long label in a different face may be larger
    than the caption when it lies inside an image or drawn shape that ends above
    the caption label (text written in the picture), or when it is not in the
    page's body face (the face carrying most characters of the page's long
    upright runs) and touches an image or drawn shape that begins above the
    caption label (lettering running past a picture's edge, or set on a backing
    with no picture). A shape carrying body-face prose above the caption label
    witnesses nothing: a backing behind body columns also covers the caption
    below them. Preserve
    the source membership for inspection and leave the drawing labels in place
    for rule 4 to claim. Ordinary prose and table blocks are not split here.
    """
    by_id = {e['id']: e for e in elements}
    def size(e): return e.get('run_size_px', e['size_px'])
    def text_faces(e):
        label = re.match(r'^\s*(?:Figure|Fig\.?)\s*\d+[A-Za-z]?[.:]?\s*', e['text'], re.I)
        start = label.end() if label else 0
        return {s['font'] for s in e.get('font_spans', [])
                if s['end'] - max(start, s['start']) >= 2} | {figure_caption_face(e)}
    def update(b, ms):
        es = [by_id[m] for m in ms]
        b.update(members=ms, box_px=[min(e['box_px'][0] for e in es), min(e['box_px'][1] for e in es),
                                   max(e['box_px'][2] for e in es), max(e['box_px'][3] for e in es)],
                 kinds=sorted({e['kind'] for e in es}),
                 text_lines=len({(e['angle'], e['line']) for e in es if e['kind'] == 'text'}),
                 text=' '.join(e['text'] for e in es if e['kind'] == 'text')[:80])
    table_members = {m for t in tables for m in t.get('members', [])}
    body_face = None  # the face carrying most characters of the page's long upright runs
    for b in list(blocks):
        # Table ownership is handled by the table reader, including a chart
        # already represented as a grid. This pass must not change that grid.
        if table_members.intersection(b['members']): continue
        ts = sorted((by_id[m] for m in b['members'] if by_id[m]['kind'] == 'text'),
                    key=lambda e: (e['line'], e['box_px'][0]))
        labels = [e for e in ts if e['angle'] == 0 and is_caption_run(e) and
                  re.match(r'^(?:FIGURE|FIG\.?)(?:\s|\d)', e['text'], re.I)]
        if len(labels) != 1 or labels[0] is ts[0]: continue
        cap = labels[0]
        drawing = any(by_id[m]['kind'] in ('image', 'fill', 'outline') and
                       by_id[m]['box_px'][2]-by_id[m]['box_px'][0] > 2*size(cap) and
                       by_id[m]['box_px'][3]-by_id[m]['box_px'][1] > size(cap) and
                       by_id[m]['box_px'][1] < cap['box_px'][1] for m in b['members'])
        if not re.match(r'^(?:FIGURE|FIG\.?)(?:\s|\d)', cap['text']):
            if not re.match(r'^(?:Figure|Fig\.?)\s*\d+[A-Za-z]?[.:]', cap['text']) and not cap.get('label_font'): continue
            if not drawing: continue
        before = ts[:ts.index(cap)]
        face = figure_caption_face(cap)
        # Pictures that end above the caption label: a backing that also covers the
        # caption (and the body columns beside it) is no witness of lettering.
        pictures = [by_id[m]['box_px'] for m in b['members']
                    if by_id[m]['kind'] in ('image', 'fill', 'outline') and
                    by_id[m]['box_px'][2]-by_id[m]['box_px'][0] > 2*size(cap) and
                    by_id[m]['box_px'][3]-by_id[m]['box_px'][1] > size(cap) and
                    by_id[m]['box_px'][3] <= cap['box_px'][1]]
        def in_picture(e):
            # a quarter letter height of slack for glyph boxes overhanging the picture edge
            E, g = e['box_px'], .25*size(cap)
            return any(P[0]-g <= E[0] and E[2] <= P[2]+g and P[1]-g <= E[1] and E[3] <= P[3]+g
                       for P in pictures)
        # Text on a drawing: a picture's lettering may run past the picture's edge, and
        # lettering may sit on a backing with no picture at all. Either counts when the
        # text is not in the page's body face and the shape it touches begins above the
        # caption label and carries no body prose above it: a backing behind body
        # columns (also covering the caption below them) never witnesses lettering.
        if body_face is None:
            runs = collections.Counter()
            for t in elements:
                if t['kind'] == 'text' and t['angle'] == 0 and len(t['text'].strip()) >= 45:
                    runs[figure_caption_face(t)] += len(t['text'].strip())
            body_face = runs.most_common(1)[0][0] if runs else ''
        def overlaps(E, P): return min(E[2], P[2]) > max(E[0], P[0]) and min(E[3], P[3]) > max(E[1], P[1])
        def bears_prose(P):
            return any(t['kind'] == 'text' and t['angle'] == 0 and len(t['text'].strip()) >= 45 and
                       figure_caption_face(t) == body_face and size(t) >= .95*size(cap) and
                       t['box_px'][3] <= cap['box_px'][1] and
                       P[0] <= (t['box_px'][0]+t['box_px'][2])/2 <= P[2] and
                       P[1] <= (t['box_px'][1]+t['box_px'][3])/2 <= P[3] for t in elements)
        drawn = [P for P in (by_id[m]['box_px'] for m in b['members']
                             if by_id[m]['kind'] in ('image', 'fill', 'outline'))
                 if P[2]-P[0] > 2*size(cap) and P[3]-P[1] > size(cap) and P[1] < cap['box_px'][1]]
        drawn = [P for P in drawn if not bears_prose(P)]
        def on_drawing(e):
            return figure_caption_face(e) != body_face and any(overlaps(e['box_px'], P) for P in drawn)
        if not before or any(len(e['text'].strip()) >= 45 and
                             (not drawing or figure_caption_face(e) == face or
                              size(e) >= .95*size(cap) and not in_picture(e) and not on_drawing(e))
                             for e in before): continue
        after = [e for e in ts if e['angle'] == 0 and e['line'] >= cap['line']]
        stop = min((e['line'] for e in after if len(e['text'].strip()) >= 35 and size(e) > 1.1*size(cap)), default=float('inf'))
        ms = [cap['id']]
        faces = text_faces(cap)
        bottom = cap['box_px'][3]
        # The caption's band (lane r2-figlet): the smallest drawn fill or outline enclosing the label that
        # holds no other drawing and no text above the label. Every line wholly inside it at the caption's
        # size continues the caption whatever its face (a bold caption title over a regular caption body).
        g = .25*size(cap)
        def inside(E, P): return P[0]-g <= E[0] and E[2] <= P[2]+g and P[1]-g <= E[1] and E[3] <= P[3]+g
        bands = [o['box_px'] for o in elements if o['kind'] in ('fill', 'outline') and inside(cap['box_px'], o['box_px'])
                 and not any(d is not o and d['kind'] in ('image', 'fill', 'outline', 'curve') and
                             d['box_px'][2]-d['box_px'][0] > size(cap) and d['box_px'][3]-d['box_px'][1] > size(cap) and
                             inside(d['box_px'], o['box_px']) for d in elements)
                 and not any(t['kind'] == 'text' and t is not cap and inside(t['box_px'], o['box_px']) and
                             t['box_px'][3] <= cap['box_px'][1] for t in elements)]
        band = min(bands, key=lambda P: (P[2]-P[0])*(P[3]-P[1])) if bands else None
        for e in after:
            if e is cap or e['line'] >= stop: continue
            E, C = e['box_px'], cap['box_px']
            if is_caption_run(e): break
            if band and inside(E, band) and abs(size(e)-size(cap)) <= .1*size(cap):
                ms.append(e['id']); bottom = max(bottom, E[3]); faces.update(text_faces(e)); continue
            if (figure_caption_face(e) not in faces or abs(size(e)-size(cap)) > .1*size(cap)
                    or (E[0] < C[0]-.5*size(cap) and abs(E[0]+E[2]-C[0]-C[2]) > size(cap))
                    or E[1] > bottom+size(cap)): continue
            ms.append(e['id']); bottom = max(bottom, E[3])
            faces.update(text_faces(e))
        if cap['id'] not in ms: continue
        b['before_caption'] = {k: b[k] for k in ('members', 'box_px', 'text_lines', 'kinds', 'text') if k in b}
        part = {'id': 'caption:' + b['id'], 'caption_from_lettering': True}
        update(part, ms)
        update(b, [m for m in b['members'] if m not in set(ms)])
        blocks.append(part)


def join_figure_lettering(elements, blocks, tables, floats, unpaired):
    """Rule 4: join graphic lettering before trimming floats or assembling tables.

    An image, frame or drawn shape wider than two body letter heights and taller
    than one seeds a graphic beside a caption. Drawing pieces within eight body
    letter heights in the same clear band extend it; lettering within one body
    letter height joins it. The larger drawing gap joins separated chart panels,
    never through a caption, labelled table, header separator or prose column.
    The seed is at most twelve body letter heights from an unpaired caption.
    Existing panel ownership takes precedence over a competing nearer caption.
    Prose is witnessed by several long lines on a common grid;
    long means 45 characters at at least 90% of body size, or three rows with
    median width at least twelve body letter heights. A frame enclosing all its
    text exempts that block from the row-width test. Within an already paired
    graphic frame, display-size titles are lettering too; body-size long prose
    remains protected. A short upright display title (one to four words) directly
    above the growing graphic, within two of its printed line heights, also
    joins before trimming. Numbered or sentence-ended lines, caption members,
    and lines in the body grid cannot be titles; other prose in the intervening
    band prevents the join. The title extends the frame upward and is recorded
    as lettering, so it cannot strand another panel or interrupt a sentence.
    A single panel letter can use the same two-line-height band at any size.
    A side caption does not cut off panels already owned by
    its figure merely because their combined rectangle encloses another column.
    Body size is the median
    size of the page's long upright runs (all runs if there are none). Labels
    smaller than 95% of body size, shorter than 45 characters, or rotated can
    join; DOI/URL identifiers and isolated long hairlines cannot bridge a join.
    A number or URL in the outer 6% at the top or 3% at the bottom witnesses
    running furniture on its baseline, unless enclosed by a substantial drawing.
    A caption's width supplies the horizontal extent of a graphic's label grid,
    only over the graphic's vertical band, with one body letter height of slack.
    A side caption can sit outside the graphic rectangle when their hull would
    enclose body text; it stays caption-classified through the unpaired record. Every new envelope is checked against
    prose before it is used. Lettering is recorded by element id and exported in
    a separate graphic block so readers need not infer ownership from the box.
    Unlabelled grids whose drawing belongs to that figure are demoted, including
    overgrown rule-3 grids that accidentally encompass neighbouring body text.
    Original block membership/geometry is retained in before_lettering when
    lettering moves to its own block. Several thin labelled fills can seed an
    already paired diagram.
    Ambiguous caption/body mixtures and numeric labels immediately beside prose
    remain conservative boundaries.
    Captions sharing a baseline and anchors already paired with a rotated URL
    watermark also stay unchanged; their copy ordering needs a consumer repair.
    """
    texts = [e for e in elements if e["kind"] == "text"]
    if not texts: return
    by_id = {e["id"]: e for e in elements}
    def hull(bs):
        return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    def near(a, b, gap=0):
        return a[0] <= b[2] + gap and a[2] >= b[0] - gap and a[1] <= b[3] + gap and a[3] >= b[1] - gap
    def centre(b, a):
        return a[0] <= (b[0]+b[2])/2 <= a[2] and a[1] <= (b[1]+b[3])/2 <= a[3]
    def within(b, a, gap=0):
        return a[0]-gap <= b[0] and b[2] <= a[2]+gap and a[1]-gap <= b[1] and b[3] <= a[3]+gap
    def size(e): return e.get("run_size_px", e["size_px"])
    long = [e for e in texts if len(e["text"].strip()) >= 45 and e["angle"] == 0]
    body = statistics.median(size(e) for e in (long or texts))
    labels = [e for e in texts if is_caption_run(e)]
    identifiers = [e for e in texts if re.search(r"https?://|\bwww\.|\bdoi\s*:", e["text"], re.I)]
    def table_label(e): return re.sub(r"\s+", "", e["text"]).lower().startswith("table")
    caption_blocks = {b["id"] for b in blocks if any(e["id"] in b["members"] for e in labels)}
    caption_members = {m for b in blocks if b["id"] in caption_blocks for m in b["members"]}
    # A separately typeset caption title on the label baseline is caption text,
    # provided it has the caption's size and is not part of a prose column.
    continuations = collections.defaultdict(list)
    extended_captions = set()
    for cap in labels:
        if table_label(cap): continue
        C = cap['box_px']; ch = C[3]-C[1]
        for e in texts:
            E = e['box_px']
            if e['id'] in caption_members or e['angle'] != cap['angle']: continue
            if (abs((E[1]+E[3]-C[1]-C[3])/2) <= .4*ch and 0 <= E[0]-C[2] <= 4*ch and
                size(e) <= 1.1*size(cap) and not any(e['id'] in b['members'] and b['text_lines'] >= 3 for b in blocks)):
                continuations[cap['id']].append(e)
        # Justified caption lines can be split into several distant runs.
        # Follow successive gaps in the same face/size, rather than measuring
        # every fragment from the label (which can lose the last word).
        right = max([C[2]] + [e['box_px'][2] for e in continuations[cap['id']]])
        for e in sorted(texts, key=lambda e: e['box_px'][0]):
            E = e['box_px']
            if e['id'] in caption_members or e in continuations[cap['id']] or e['angle'] != cap['angle']: continue
            if (abs((E[1]+E[3]-C[1]-C[3])/2) <= .4*ch and 0 <= E[0]-right <= 2*ch and
                abs(size(e)-size(cap)) <= .05*size(cap) and figure_caption_face(e) == figure_caption_face(cap) and
                not is_caption_run(e) and not any(e['id'] in b['members'] and b['text_lines'] >= 3 for b in blocks)):
                continuations[cap['id']].append(e); right = E[2]
                extended_captions.add(cap['id'])
    caption_members.update(e['id'] for es in continuations.values() for e in es)
    # The grid of long prose lines, not the number of lines in a drawing's block,
    # separates body paragraphs from multiline flowchart boxes and chart keys.
    prose = []
    framed_labels = set()
    paired_graphics = {bid for f in floats if not table_label({'text': f['caption']})
                       for bid in f['blocks'] if bid not in caption_blocks}
    for b in blocks:
        if b["id"] in caption_blocks: continue
        ts = [by_id[m] for m in b["members"] if m in by_id and by_id[m]["kind"] == "text"]
        wide = [e for e in ts if len(e["text"].strip()) >= 45 and size(e) >= .9 * body]
        rows = collections.defaultdict(list)
        for e in ts: rows[(e["angle"],e["line"])].append(e["box_px"])
        widths = [hull(row)[2]-hull(row)[0] for row in rows.values()]
        framed = any(by_id[m]["kind"] in ("fill","image") and
                     all(within(e["box_px"],by_id[m]["box_px"],1) for e in ts)
                     for m in b["members"] if m in by_id) if ts else False
        if framed and b['id'] in paired_graphics:
            framed_labels.update(e['id'] for e in ts
                                 if len(e['text'].strip()) < 45 or size(e) < .9*body or size(e) > 1.15*body)
        if not framed and (len(wide) >= 2 or len(rows) >= 3 and
                           statistics.median(widths) >= 12*body):
            prose.extend(ts)
    body_grid = {e['id'] for e in prose}
    prose += [e for e in texts if e["id"] not in caption_members and e['id'] not in framed_labels and
              (len(e["text"].strip()) >= 45 and size(e) >= .9*body or
               len(e["text"].strip()) >= 10 and size(e) > 1.15*body)]
    prose.extend(identifiers)
    # A spanning rule in the page's top margin separates the journal header
    # (including decorative image strips) from a figure immediately below it.
    page_height = max(e["box_px"][3] for e in elements)
    # A page number or URL on an outer-margin baseline witnesses running
    # furniture. Keep the whole baseline and its decorations out of the join.
    # Numbers enclosed by a substantial drawing remain eligible axis labels.
    margin_rows = [e["box_px"] for e in texts if e["angle"] == 0 and
                   (e["box_px"][3] < .06*page_height or e["box_px"][1] > .97*page_height) and
                   (re.fullmatch(r"[A-Za-z]?\d{1,4}", e["text"].strip()) or e in identifiers) and
                   not any(o["kind"] in ("image","fill","outline") and
                           o["box_px"][3]-o["box_px"][1] > 3*body and
                           within(e["box_px"],o["box_px"]) for o in elements)]
    def margin_row(B):
        return any(abs((B[1]+B[3]-M[1]-M[3])/2) <= body for M in margin_rows)
    prose.extend(e for e in texts if margin_row(e["box_px"]))
    # The page's head band (lane r3-stackfig, step-3 mimic u1): when the topmost printed row holds a
    # page number or a web address and stands above every picture, rule and drawn shape, that row is running furniture, and so is any line standing within
    # two body letter heights under it (a section label such as a journal's article-type word) that is
    # neither a panel letter nor set on a picture or drawn shape. Neither
    # is a figure's title or lettering, whatever the page's length (the outer-6% witness above measures
    # from the page's last text, which a short page puts high).
    upright = [e for e in texts if e["angle"] == 0]
    head_ids = set()
    # Scope (ruling 2026-11-12): the head band applies only on a page whose figure or table caption label is
    # bar-separated ("Fig. N |", "Figure N |", "Table N |"), the captions this lane makes floats of; every
    # other page keeps the boxer's earlier path line for line.
    bar_caption = any(re.match(r"^(Fig\.?|Figure|Table)(?:\d+[a-z]?|[IVXLCDM]+)\|", re.sub(r"\s+", "", e["text"]), re.I)
                      for e in labels)
    if upright and bar_caption:
        top = min(upright, key=lambda e: e["box_px"][1])
        row = [e for e in upright if abs((e["box_px"][1]+e["box_px"][3]-top["box_px"][1]-top["box_px"][3])/2) <= body]
        row_bottom = max(e["box_px"][3] for e in row)
        # ... and stands above every picture or drawn shape of the page (a tick number at a chart's top
        # or a label inside a frame is the drawing's own)
        if (any(re.fullmatch(r"[A-Za-z]?\d{1,4}", e["text"].strip()) or e in identifiers for e in row) and
                all(o["box_px"][1] >= row_bottom for o in elements if o["kind"] in ("image", "fill", "outline", "rule"))):
            # A panel letter (one letter, bracketed or not) and a line whose centre lies on a picture or drawn
            # shape belong to the figure, not the head band (gate memo gate-stackfig-headband: photographs at
            # the page top with letters A-C at their corners within two body heights of the running-head row).
            drawn = [o["box_px"] for o in elements if o["kind"] in ("image", "fill", "outline")]
            def figure_own(e):
                return (bool(re.fullmatch(r"\(?[A-Za-z]\)?", e["text"].strip())) or
                        any(centre(e["box_px"], D) for D in drawn))
            head_ids = {e["id"] for e in row} | {e["id"] for e in upright if 0 <= e["box_px"][1]-row_bottom <= 2*body
                                                 and not figure_own(e)}
    def head_band(B):
        return any(e["box_px"] is B for e in upright if e["id"] in head_ids)
    prose.extend(e for e in texts if e["id"] in head_ids and e not in prose)
    text_width = max(e["box_px"][2] for e in texts)-min(e["box_px"][0] for e in texts)
    header_rules = [e["box_px"][3] for e in elements if e["kind"] in ("rule","fill") and
                    e["box_px"][2]-e["box_px"][0] >= .7*text_width and
                    e["box_px"][3]-e["box_px"][1] <= .3*body and
                    e["box_px"][3] < .1*page_height]
    header = max(header_rules, default=-1)
    prose.extend(e for e in texts if e["box_px"][3] <= header)
    table_labels = [e for e in labels if table_label(e)]
    protected_tables = [t["box_px"] for t in tables if any(centre(e["box_px"], t["box_px"]) for e in table_labels)]
    protected_tables += [f["box_px"] for f in floats if table_label({"text":f["caption"]})]
    drawings = [e for e in elements if e["kind"] in ("image", "fill", "outline", "rule")
                and e["box_px"][1] > header
                and not margin_row(e["box_px"])
                and not any(centre(e["box_px"], T) for T in protected_tables)
                and not any(centre(p["box_px"], e["box_px"]) for p in prose)]
    # Isolated long hairlines are page separators. Chart axes and frame edges
    # touch another drawing; a header rule must not bridge a figure to its header.
    drawings = [e for e in drawings if not (e["kind"] == "rule" and
                e["box_px"][2]-e["box_px"][0] > 10*body and
                e["box_px"][3]-e["box_px"][1] < .2*body and
                not any(o is not e and near(e["box_px"],o["box_px"],1) for o in drawings))]
    title_ids = set()
    def safe(box, cap_members, title=()):
        return not any(e['id'] not in title_ids and e['id'] not in title and
                       centre(e["box_px"], box) for e in prose) and not any(
            e["id"] not in cap_members and centre(e["box_px"], box) for e in labels)
    title_candidates = []
    for e in texts:
        if (e['angle'] != 0 or e['id'] in body_grid or e['id'] in caption_members or
            e in identifiers or (size(e) <= 1.15*body and
                                 not re.fullmatch(r'\(?[A-Za-z]\)?', e['text'].strip())) or
            margin_row(e['box_px']) or head_band(e['box_px']) or
            e['box_px'][3] <= header): continue
        # Include detached numbering and other runs on the same printed line:
        # a short fragment of a numbered heading is still a numbered heading.
        row = sorted((r for r in texts if r['angle'] == 0 and r['line'] == e['line']),
                     key=lambda r: r['box_px'][0])
        line = ' '.join(r['text'].strip() for r in row)
        if (not 1 <= len(line.split()) <= 4 or
            re.match(r'^\s*\d+(?:[.\d]*)(?:\s|[|.)])', line) or
            re.search(r'[.!?:;]\s*$', line)): continue
        title_candidates.append(e)
    # An exhibit drawn round its own caption ends at that drawing (lane r2-figlet). When drawn shapes (an
    # outline, a fill: a frame or a caption band) enclose a figure's caption label, the outermost of them is
    # the exhibit's border. A frame that also holds a drawing of the figure (a chart's fills or axes, an
    # image) bounds the exhibit above and below; a band holding the caption alone bounds it on its side away
    # from the figure's drawing only: at its bottom edge when a drawing of the figure stands directly above
    # it (within twelve body letter heights) and none below, at its top edge in the opposite case.
    # A run set in the page's body face (a small-caps heading's capitals at any size), lying wholly beyond
    # such an edge within the border's width, is the page's text (a section heading printed under the
    # frame), never the figure's lettering. Runs inside the border (an axis title just inside the frame's
    # bottom) and runs in other faces are unaffected; a display title above a figure keeps its own rule.
    faces = collections.Counter()
    for e in (long or texts): faces[run_face(e)] += len(e["text"])
    body_face = faces.most_common(1)[0][0] if faces else None
    shapes = [e for e in elements if e["kind"] in ("outline", "fill")]
    def exhibit_beyond(cap):
        L = cap["box_px"]
        around = [o["box_px"] for o in shapes if within(L, o["box_px"], 1)]
        if not around or body_face is None: return lambda e: False
        O = max(around, key=lambda B: (B[2]-B[0])*(B[3]-B[1]))
        frame = any(d["kind"] in ("image", "fill", "outline") and not within(L, d["box_px"], 1) and
                    d["box_px"][2]-d["box_px"][0] > 2*body and d["box_px"][3]-d["box_px"][1] > body and
                    within(d["box_px"], O, 1) for d in elements)
        def drawn(d):
            D = d["box_px"]
            return (d["kind"] in ("image", "fill", "outline") and not within(L, D, 1) and
                    D[2]-D[0] > 2*body and D[3]-D[1] > body and min(D[2], O[2]) > max(D[0], O[0]))
        over = any(drawn(d) and -body <= O[1]-d["box_px"][3] <= 12*body for d in elements)
        under = any(drawn(d) and -body <= d["box_px"][1]-O[3] <= 12*body for d in elements)
        if not frame and over == under: return lambda e: False
        foot = over
        def beyond(e):
            if run_face(e) != body_face or e["angle"] != 0: return False
            E = e["box_px"]
            if not (O[0]-body <= (E[0]+E[2])/2 <= O[2]+body): return False
            below, above = E[1] >= O[3] - 1, E[3] <= O[1] + 1
            return below or above if frame else below if foot else above
        return beyond
    # A heading band (lane r2-figlet round 2b): a drawn fill, or a pair of horizontal rules of one extent,
    # one to four letter heights tall and over four wide, that holds nothing but one line of text (no other
    # drawing inside it), centred in it (within a letter height or a tenth of its width), its largest run at
    # least 0.8 of body size and no smaller than the figure's caption (lettering is set smaller than the
    # caption; a heading is not), and no caption label. Rules lying along a fill's top and
    # bottom edges belong to it. A band that follows a figure's caption on the caption's far side, with no
    # substantial drawing of the figure between them (the frame's thin edge rules may lie between), is a
    # section heading's band: neither it nor its text joins the figure.
    hrules = [e for e in elements if e["kind"] == "rule" and e["box_px"][3]-e["box_px"][1] <= .3*body
              and e["box_px"][2]-e["box_px"][0] > 4*body]
    band_shapes = [(o["box_px"], [o]) for o in elements if o["kind"] == "fill"]
    for a in hrules:
        for c in hrules:
            A, C = a["box_px"], c["box_px"]
            if (c is not a and abs(A[0]-C[0]) <= body and abs(A[2]-C[2]) <= body and
                    .8*body <= C[1]-A[3] <= 4*body):
                band_shapes.append(([min(A[0], C[0]), A[1], max(A[2], C[2]), C[3]], [a, c]))
    heading_bands = []
    for B, parts in band_shapes:
        if not (4*body < B[2]-B[0] and .8*body <= B[3]-B[1] <= 4*body): continue
        parts = parts + [r for r in hrules if r not in parts and B[0]-body <= r["box_px"][0] and
                         r["box_px"][2] <= B[2]+body and (abs(r["box_px"][1]-B[1]) <= .3*body or abs(r["box_px"][3]-B[3]) <= .3*body)]
        inside = [e for e in texts if within(e["box_px"], B, 1)]
        if not inside or len({(e["angle"], e["line"]) for e in inside}) != 1: continue
        if any(is_caption_run(e) for e in inside) or max(size(e) for e in inside) < .8*body: continue
        T = hull([e["box_px"] for e in inside])
        if abs((T[0]+T[2])/2-(B[0]+B[2])/2) > max(body, .1*(B[2]-B[0])): continue
        if any(d["kind"] in ("image", "fill", "outline", "rule", "curve") and not any(d is q for q in parts) and
               within(d["box_px"], B, 1) for d in elements): continue
        heading_bands.append((B, {e["id"] for e in parts} | {e["id"] for e in inside}, max(size(e) for e in inside)))
    def heading_band_ids(cb, cap):
        out = set()
        for B, ids, top in heading_bands:
            if top < .95*size(cap): continue
            if B[1] >= cb[3]-1: lo, hi = cb[3], B[1]
            elif B[3] <= cb[1]+1: lo, hi = B[3], cb[1]
            else: continue
            if any(d["kind"] in ("image", "fill", "outline") and d["id"] not in ids and
                   d["box_px"][2]-d["box_px"][0] > 2*body and d["box_px"][3]-d["box_px"][1] > body and
                   d["box_px"][1] >= lo-1 and d["box_px"][3] <= hi+1 and
                   min(d["box_px"][2], B[2]) > max(d["box_px"][0], B[0]) for d in elements): continue
            out |= ids
        return out
    figures = []
    for b in blocks:
        ts = [by_id[m] for m in b["members"] if m in by_id and by_id[m]["kind"] == "text"]
        if not ts: continue
        first = min(ts, key=lambda e: (e["line"], e["box_px"][0]))
        if first not in labels or table_label(first) or first["angle"] != 0: continue
        cb = hull([e["box_px"] for e in ts if e["line"] >= first["line"]])
        figures.append((b, first, cb))
    claimed = set()
    # Existing panel pairing takes precedence over distance to a side caption:
    # the first row of the next figure can be nearer the preceding side caption.
    owners = collections.defaultdict(set)
    for f in floats:
        if table_label({"text":f["caption"]}): continue
        for original in blocks:
            if original["id"] in f["blocks"]:
                for m in original["members"]: owners[m].add(id(f))
    for b, cap, cb in figures:
        title_ids = set()
        cm = set(b["members"]) | {e['id'] for e in continuations[cap['id']]}
        lb = cap["box_px"]; lh = lb[3]-lb[1]
        if any(other is not b and abs((lab["box_px"][1]+lab["box_px"][3]-lb[1]-lb[3])/2)
               <= .4*lh for other, lab, C in figures): continue
        # A smaller caption merged with larger body lines is not a clean anchor.
        # Its block must be split by the caption reader before ownership grows.
        if any(e["id"] in cm and e["kind"] == "text" and
               len(e["text"].strip()) >= 35 and size(e) > 1.1*size(cap) and
               size(e) >= .9*body for e in texts): continue
        f = next((f for f in floats if b["id"] in f["blocks"]), None)
        # A nearby image supports extending a paired figure beside prose. A
        # vector plot can still be a provisional float that trimming would
        # discard; keep its old prose boundary unless its caption was split
        # from graphic labels explicitly.
        image_anchor = f is not None and any(
            e['kind'] == 'image' and (not owners[e['id']] or id(f) in owners[e['id']]) and
            near(e['box_px'], cb, 12*body) and safe(hull([e['box_px'],cb]),cm)
            for e in elements)
        if not image_anchor and not b.get('caption_from_lettering') and any(
                e['id'] not in b['members'] and
                (e in prose or e in continuations[cap['id']] and
                 (len(e['text'].strip()) >= 45 and size(e) >= .9*body or
                  len(e['text'].strip()) >= 10 and size(e) > 1.15*body)) and
                abs((e['box_px'][1]+e['box_px'][3]-lb[1]-lb[3])/2) <= .4*lh and
                0 <= e['box_px'][0]-lb[2] <= 4*lh for e in texts): continue
        if f and any(id(f) in owners[e["id"]] and e["angle"] != 0
                     for e in identifiers): continue
        banded = heading_band_ids(cb, cap)
        def available(e):
            return (e["id"] not in claimed and e["id"] not in banded and
                    (not owners[e["id"]] or id(f) in owners[e["id"]]))
        # A seed must be visibly substantial; isolated rules or glyph-sized
        # decoration cannot create a new figure by themselves.
        eligible = [e for e in drawings if available(e) and e["id"] not in cm
                    and (safe(hull([cb, e["box_px"]]), cm) or
                         f is not None and id(f) in owners[e['id']] and safe(e['box_px'], cm))]
        def gap(e):
            B=e["box_px"]
            return max(0, B[0]-cb[2], cb[0]-B[2]) + max(0, B[1]-cb[3], cb[1]-B[3])
        seeds = [e for e in eligible if ((e["box_px"][2]-e["box_px"][0]) > 2*body
                 and (e["box_px"][3]-e["box_px"][1]) > body)
                 and (min(e["box_px"][2],cb[2]) > max(e["box_px"][0],cb[0])
                      or min(e["box_px"][3],cb[3]) > max(e["box_px"][1],cb[1]))]
        # A paired diagram may consist entirely of thin filled arrows. Several
        # such shapes with their own labels are enough to seed its existing float.
        if not seeds and f:
            thin = [e for e in eligible if e['kind'] == 'fill' and
                    e['box_px'][2]-e['box_px'][0] > 2*body and
                    e['box_px'][3]-e['box_px'][1] > .5*body and
                    any(within(t['box_px'], e['box_px'], body) for t in texts if t['id'] not in caption_members)]
            if len(thin) >= 3: seeds = thin
        if not seeds: continue
        seed = min(seeds, key=gap)
        if gap(seed) > 12 * body and f is None: continue
        S = seed["box_px"]
        # A caption is also a boundary: panels belonging to a figure above it
        # cannot expand through that caption into the next figure below it.
        if S[3] <= cb[1]: same_side = lambda E: E[3] <= cb[1] + body
        elif S[1] >= cb[3]: same_side = lambda E: E[1] >= cb[3] - body
        elif S[2] <= cb[0]: same_side = lambda E: E[2] <= cb[0] + body
        elif S[0] >= cb[2]: same_side = lambda E: E[0] >= cb[2] - body
        else: same_side = lambda E: True
        def nearer_caption(e):
            if id(f) in owners[e["id"]]: return False
            E = e["box_px"]
            for other, lab, C in figures:
                if other is b: continue
                other_float = next((o for o in floats if other['id'] in o['blocks']), None)
                if other_float:
                    graphics = [by_id[m]['box_px'] for block in blocks if block['id'] in other_float['blocks']
                                for m in block['members'] if by_id[m]['kind'] in ('image', 'fill', 'outline')]
                    # A caption separates its drawing from the next figure.
                    # Distance to the preceding caption cannot claim panels on
                    # the opposite side from that caption's paired graphic.
                    if graphics:
                        O = hull(graphics)
                        if (O[3] <= C[3] and E[1] >= C[3] + body or
                            O[1] >= C[1] and E[3] <= C[1] - body): continue
                if min(E[2],C[2]) <= max(E[0],C[0]) and min(E[3],C[3]) <= max(E[1],C[1]): continue
                d = max(0,E[0]-C[2],C[0]-E[2]) + max(0,E[1]-C[3],C[1]-E[3])
                if d < gap(e) and safe(hull([E,C]),set(other["members"])): return True
            return False
        eligible = [e for e in eligible if same_side(e["box_px"]) and not nearer_caption(e)]
        if seed not in eligible: continue
        beyond = exhibit_beyond(cap)
        links = [e for e in texts if available(e) and e["id"] not in caption_members and e not in prose
                 and same_side(e["box_px"]) and not nearer_caption(e) and not beyond(e)
                 # A short continuation on the label's own baseline is caption
                 # text even when rule 2 put it in a separate block.
                 and not (cb[1] <= (e["box_px"][1]+e["box_px"][3])/2 <= cb[3] and
                          0 <= e["box_px"][0]-cb[2] <= 2*body)
                 and not any(centre(e["box_px"], T) for T in protected_tables)
                 and (size(e) < .95*body or len(e["text"].strip()) < 45 or e["angle"] != 0)]
        chosen = [seed]; taken = {seed["id"]}; G = seed["box_px"]
        grew = True
        while grew:
            grew = False
            # A title outside the current frame must have a graphic immediately
            # below it. Exempt only that supported title from the prose barrier;
            # all other prose and competing captions still veto the envelope.
            for e in title_candidates:
                if e['id'] in taken or not available(e) or not same_side(e['box_px']) or nearer_caption(e): continue
                E = e['box_px']; height = max(1, E[3]-E[1])
                # A title held by a drawn box of its own that does not reach the graphic is that
                # box's text (measured: AH06, the journal's section banner above each figure).
                if any(o['kind'] in ('fill', 'image') and within(E, o['box_px'], 1) and not near(o['box_px'], G)
                       for o in elements): continue
                # The ordinary one-height join already owns these labels;
                # retain its membership order when no wider band is needed.
                if e not in prose and near(E, G, body): continue
                if not (E[1] < G[1] and -height <= G[1]-E[3] <= 2*height and
                        G[0]-height <= E[0] and E[2] <= G[2]+height): continue
                H = hull([G, E])
                if not safe(H, cm, {e['id']}): continue
                title_ids.add(e['id']); chosen.append(e); taken.add(e['id']); G = H; grew = True
            if grew:
                # Removing a supported title's prose barrier can expose an
                # upper image panel that was initially unreachable from the caption.
                eligible = [e for e in drawings if available(e) and e['id'] not in cm
                            and same_side(e['box_px']) and not nearer_caption(e)
                            and (safe(hull([cb, e['box_px']]), cm) or
                                 f is not None and id(f) in owners[e['id']] and safe(e['box_px'], cm))]
            for e in eligible + links:
                if e["id"] in taken or not near(e["box_px"], G, body if e["kind"] == "text" else 8*body): continue
                H = hull([G, e["box_px"]])
                if not safe(H, cm): continue
                # Do not connect pictures over the intervening caption of
                # another float, or over a paragraph hidden inside its block.
                chosen.append(e); taken.add(e["id"]); G = H; grew = True
        # The caption and drawing share a label grid. Only its graphic band
        # extends sideways; it never extends the caption into a body column.
        field = [min(G[0],cb[0])-body, G[1]-body, max(G[2],cb[2])+body, G[3]+body]
        if not safe(hull([cb, field]), cm): field = [G[0]-body,G[1]-body,G[2]+body,G[3]+body]
        candidates = [e for e in links if within(e["box_px"],field)]
        if not candidates and not any(e["kind"] == "text" for e in chosen): continue
        letter_text = {e["id"]: e for e in chosen + candidates if e["kind"] == "text"}
        # A number directly beside prose can be a detached body marker. Keep
        # that ambiguous geometry unchanged even though the reader honors ids.
        unsafe_number = False
        for e in letter_text.values():
            if len(e["text"].strip()) > 6 or re.search(r"[A-Za-z]{2}",e["text"]): continue
            E = e["box_px"]; eh = max(4,E[3]-E[1])
            if any(abs((p["box_px"][1]+p["box_px"][3]-E[1]-E[3])/2) <= .4*eh and
                   0 <= p["box_px"][0]-E[2] <= 4*eh for p in prose):
                unsafe_number = True; break
        if unsafe_number: continue
        G = hull([G] + [e["box_px"] for e in candidates])
        F = hull([cb,G])
        if not safe(F,cm): F = G
        # A labelled table is never demoted. An unlabelled false grid can be
        # wider than its drawing; use drawing overlap rather than its text hull.
        demoted = []
        for t in tables:
            if t.get("demoted") or t["box_px"] in protected_tables: continue
            own_draw = [e for e in chosen if near(e["box_px"],t["box_px"]) and
                        (e["box_px"][2]-e["box_px"][0])*(e["box_px"][3]-e["box_px"][1]) > body*body]
            if own_draw and (within(t["box_px"],G,body) or any(
                    m in taken for m in t.get("members",[]) + t.get("witness",[]))):
                t["demoted"] = "drawing belongs to a Figure caption: figure lettering, not a table"
                demoted.append(t["id"])
        bid = "lettering:" + b["id"]
        candidates = list({e["id"]:e for e in chosen + candidates if e["kind"] == "text"}.values())
        chosen = [e for e in chosen if e["kind"] != "text"]
        members = [e["id"] for e in chosen + candidates]
        blocks.append({"id":bid,"box_px":G,"members":members,
                       "text_lines":len({e["line"] for e in candidates}),
                       "kinds":sorted({e["kind"] for e in chosen+candidates}),
                       "figure_lettering":True, "text":" ".join(e["text"] for e in candidates)[:80]})
        if f is None:
            f = {"caption":cap["text"][:80],"blocks":[b["id"]],
                 "basis":"Figure caption beside a drawing and its lettering"}
            floats.append(f)
        f["box_px"] = F
        f["blocks"].append(bid)
        f["lettering"] = [e["id"] for e in candidates]
        f["members"] = list(dict.fromkeys(list(b["members"]) + members))
        if b.get('caption_from_lettering') or cap['id'] in extended_captions:
            f['caption_members'] = [m for m in b['members'] if by_id[m]['kind'] == 'text'] + [e['id'] for e in continuations[cap['id']]]
            f['members'] = list(dict.fromkeys(f['members'] + f['caption_members']))
        if demoted: f["demoted_tables"] = demoted
        # Transfer the lettering out of its old blocks. Exporters use those
        # memberships too; leaving an axis value in a mixed body block would
        # reinsert it even though the float-free page classified it correctly.
        letter_ids = set(f["lettering"])
        for original in blocks:
            if original.get("figure_lettering"): continue
            keep = [m for m in original["members"] if m not in letter_ids]
            if len(keep) == len(original["members"]): continue
            original.setdefault("before_lettering", {k:original[k] for k in
                                ("members","box_px","text_lines","kinds","text") if k in original})
            original["members"] = keep
            remaining = [by_id[m] for m in keep]
            if remaining: original["box_px"] = hull([e["box_px"] for e in remaining])
            original["kinds"] = sorted({e["kind"] for e in remaining})
            original["text_lines"] = len({(e["angle"],e["line"]) for e in remaining if e["kind"] == "text"})
            original["text"] = " ".join(e["text"] for e in remaining if e["kind"] == "text")[:80]
        claimed.update(members)
        unpaired[:] = [u for u in unpaired if u.get("block") != b["id"] and u.get("block") not in demoted]
        if F == G and F != hull([cb,G]):
            unpaired.append({"kind":"caption outside graphic rectangle", "caption":cap["text"][:80],
                             "box_px":cb, "block":b["id"]})


def caption_label_line_blocks(elements, blocks):
    """Rule 4, caption extent on the label's line (lane r4-captionextent; round 5, lane captionside: figure captions,
    the side caption of rule F13 among them): a caption is its label's line
    plus the lines in the caption's own type. Rules 1-2 can set the caption text that follows the label
    on the label's own line, after a wide gap (a tab), in a block of its own; that block then stands
    between the caption and its picture and keeps them apart in pairing, and rule 6 reads it as body
    text. Such a block joins the caption's block before pairing when, in the label's reading frame:
      - the caption's block opens with the label (caption label first on its first line);
      - every member of the block is a text run on the label's own line, to the right of the label;
      - its runs are in the caption's type: the caption block's size (within a tenth), and, when the
        caption block holds text of its own after the label, one of that text's faces;
      - nothing lies between: no text run of another block on that line between the label and it;
      - it is not a column's text: its left edge is not the left edge of a block of
        column_min_lines or more lines (a body column whose first line is level with a side caption);
      - it is not lettering: no drawn object (image, fill, outline, curve) that leaves the label outside
        holds any of its runs or lies between the label and it.
    The block is removed from the page's blocks and its runs become the caption block's members."""
    by_id = {e["id"]: e for e in elements}
    def size(e): return e.get("run_size_px", e["size_px"])
    def texts(b): return [by_id[m] for m in b["members"] if m in by_id and by_id[m]["kind"] == "text"]
    for b in list(blocks):
        if b not in blocks or b.get("is_table"): continue
        ts = texts(b)
        if not ts: continue
        first_line = min(e["line"] for e in ts)
        line_runs = [e for e in ts if e["line"] == first_line]
        to_read, _ = frame(line_runs[0]["angle"])
        def rd(B):
            u0, v0, u1, v1 = to_read(*B); return (min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))
        c = min(line_runs, key=lambda e: rd(e["box_px"])[0])
        if not is_caption_run(c) or any(e["angle"] != c["angle"] for e in ts): continue
        # round 5 (lane captionside, rule F13): figure captions only; a table caption's label line is left as before
        if re.sub(r"\s+", "", c["text"]).lower().startswith("table"): continue
        C = rd(c["box_px"]); em = size(c)
        csize = statistics.median(size(e) for e in ts)
        own_faces = {figure_caption_face(e) for e in ts if e is not c}
        # Rule F13 (round 5): only a caption with no picture directly above or below it (a side caption) is read
        # sideways; a drawn object across a third of the width of the caption with its label-line block, within three
        # letter heights above or below it, is its picture, and its label line is left as before.
        def ink0(D): return D[2] - D[0] > em and D[3] - D[1] > em
        pictures0 = [D for D in (rd(d["box_px"]) for d in elements if d["kind"] in ("image", "fill", "outline", "curve")) if ink0(D)]
        for o in list(blocks):
            if o is b or o.get("is_table") or o.get("is_chart") or not o["members"]: continue
            os_ = texts(o)
            if len(os_) != len(o["members"]): continue
            if not all(e["line"] == c["line"] and e["angle"] == c["angle"] for e in os_): continue
            O = [rd(e["box_px"]) for e in os_]
            B0 = [min([rd(b["box_px"])[0]] + [B[0] for B in O]), min([rd(b["box_px"])[1]] + [B[1] for B in O]),
                  max([rd(b["box_px"])[2]] + [B[2] for B in O]), max([rd(b["box_px"])[3]] + [B[3] for B in O])]
            if any(min(D[2], B0[2]) - max(D[0], B0[0]) > .3 * (B0[2] - B0[0]) and (0 <= B0[1] - D[3] <= 3 * em or 0 <= D[1] - B0[3] <= 3 * em)
                   for D in pictures0): continue   # F13: the caption with its line has a picture directly above or below
            x0 = min(B[0] for B in O)
            if x0 < max(rd(e["box_px"])[2] for e in line_runs) - 1: continue
            if any(abs(size(e) - csize) > .1 * csize for e in os_): continue
            if own_faces and not all(figure_caption_face(e) in own_faces for e in os_): continue
            gap = (C[2], x0)
            def ink(D): return D[2] - D[0] > em and D[3] - D[1] > em
            drawn = [rd(d["box_px"]) for d in elements if d["kind"] in ("image", "fill", "outline", "curve") and ink(rd(d["box_px"]))
                     and not (rd(d["box_px"])[0] <= C[0] and C[2] <= rd(d["box_px"])[2] and rd(d["box_px"])[1] <= C[1] and C[3] <= rd(d["box_px"])[3])]
            if any(min(D[2], B[2]) > max(D[0], B[0]) and min(D[3], B[3]) > max(D[1], B[1]) for D in drawn for B in O): continue
            if any(D[0] < gap[1] and D[2] > gap[0] and min(D[3], C[3]) > max(D[1], C[1]) for D in drawn): continue
            if any(t["kind"] == "text" and t["id"] not in o["members"] and t["id"] not in b["members"]
                   and min(rd(t["box_px"])[3], C[3]) > max(rd(t["box_px"])[1], C[1])
                   and rd(t["box_px"])[0] < gap[1] and rd(t["box_px"])[2] > gap[0] for t in elements): continue
            if any(k is not o and k is not b and not k.get("is_table") and k.get("text_lines", 0) >= PARAMS["column_min_lines"]
                   and texts(k) and abs(min(rd(e["box_px"])[0] for e in texts(k)) - x0) <= em for k in blocks): continue
            b["members"] = b["members"] + o["members"]
            es = [by_id[m] for m in b["members"] if m in by_id]
            b["box_px"] = [min(e["box_px"][0] for e in es), min(e["box_px"][1] for e in es), max(e["box_px"][2] for e in es), max(e["box_px"][3] for e in es)]
            b["kinds"] = sorted({e["kind"] for e in es})
            b.setdefault("label_line_joined", []).append(o["id"])
            if "text" in b: b["text"] = " ".join(e["text"] for e in sorted(texts(b), key=lambda e: (e["line"], rd(e["box_px"])[0])))[:80]
            blocks.remove(o)

def floats_with_captions(elements, blocks, tables=(), chars=None):
    """Rule 4: floats = larger boxes holding a graphic and a caption label, or a caption-label
    box stacked against a graphic box. Each caption and each graphic is paired once, the nearest
    pairs first: of two captions against one graphic, the nearer is its own. A chart drawn in pieces
    (bars, axes, ticks and error bars, in drawn-only boxes or in none, and their short labels of one line,
    at most chart_label_chars characters and no larger than the page's median text) is one graphic: the
    pieces within a letter height of each other join, when three or more of them are drawn and two or
    more are labels, and neither a piece nor the whole lies within a letter height of, or over, a graphic
    of another kind (an image, lettering in one fill: a frame round a picture is not a chart), and then its
    outer labels (a title, a legend and its swatches, an axis title: short labels and swatch-only boxes)
    within two letter heights of it; a drawn object under prose, an image, a caption and a table never
    join. Its float names it chart:N among its blocks. Before pairing, a Table caption can
    recover a ruled table with merged cells (tables_from_caption_rules). Stacked image panels
    within one letter height join a figure too when all their text consists of single panel
    letters, optionally parenthesized, wholly inside the images; that lettering joins with
    its panel and cannot be left in main text. Before trimming, join_figure_lettering
    grows the figure over its supported drawing/label grid, records lettering and
    member ids, and transfers the lettering from mixed blocks. The trimmer must
    preserve those explicit members. Native character font metadata is attached
    at entry, after rules 2-3, so caption faces are available before final export.
    assemble_tables must keep a side caption's
    classification when its rectangle lies outside the graphic rectangle. A figure caption's own
    shaded box (a fill fitting a block that opens with a Figure label) is not a graphic, and a
    text-area background (kind background) is never one."""
    if chars is not None: sc_font_metadata({'elements': elements}, chars=chars)
    source_blocks = blocks
    if isinstance(tables, list): tables.extend(tables_from_caption_rules(elements, tables))
    def holds(t, kind):
        T = t["box_px"]
        return any(e["kind"] == "text" and is_caption_run(e) and (re.sub(r"\s+", "", e["text"]).lower().startswith("table") == (kind == "table"))
                   and T[0] - 1 <= e["box_px"][0] and e["box_px"][2] <= T[2] + 1 and T[1] - 1 <= e["box_px"][1] and e["box_px"][3] <= T[3] + 1 for e in elements)
    demoted = [t for t in tables if holds(t, "figure") and not holds(t, "table")]
    tables = [t for t in tables if t not in demoted]
    for t in demoted: t["demoted"] = "holds a Figure label and no Table label: a figure's lettering, not a table"
    split_figure_caption_blocks(elements, blocks, tables)
    caption_label_line_blocks(elements, blocks)
    blocks = list(blocks) + [{"id": t["id"], "box_px": t["box_px"], "members": [], "text_lines": 0, "kinds": ["table"], "is_table": True} for t in tables]
    # blocks swallowed by a table are not separate blocks for rule 4
    def inside(b, t): B, T = b["box_px"], t["box_px"]; return B[0] >= T[0] - 1 and B[2] <= T[2] + 1 and B[1] >= T[1] - 1 and B[3] <= T[3] + 1
    blocks = [b for b in blocks if b.get("is_table") or not any(inside(b, t) for t in tables)]
    by_id = {e["id"]: e for e in elements}
    def rd_for(angle):
        to_read, _ = frame(angle)
        def rd(b):
            u0, v0, u1, v1 = to_read(*b); return (min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))
        return rd
    def block_angle(b):
        ts = [by_id[m]["angle"] for m in b["members"] if by_id[m]["kind"] == "text"]
        return collections.Counter(ts).most_common(1)[0][0] if ts else 0
    def nothing_between(a, b, blocks, rd=lambda x: tuple(x)):
        """Directly adjacent: the boxes overlap on one axis, and no other block lies in the band between
        them on the other axis (stacked, or side by side). Needs no distance threshold. Another block
        lies in the band when one of its own elements does: a text column that narrows beside a
        figure and widens under it has a hull reaching into the figure's band, but no text there
        (measured: AH06 p4 and p6, the column beside each chart kept the chart from its caption)."""
        A, B = rd(a["box_px"]), rd(b["box_px"])
        def clear(ax):   # ax 0: overlap along u, between along v; ax 1: the reverse
            i, j = (0, 2) if ax == 0 else (1, 3); k, l = (1, 3) if ax == 0 else (0, 2)
            p0, p1 = max(A[i], B[i]), min(A[j], B[j])
            if p1 - p0 <= 0: return False
            if min(A[l], B[l]) > max(A[k], B[k]): return True
            q0, q1 = (A[l], B[k]) if B[k] >= A[l] else (B[l], A[k])
            for o in blocks:
                if o is a or o is b: continue
                for O in [rd(by_id[m]["box_px"]) for m in o["members"] if m in by_id] or [rd(o["box_px"])]:
                    if min(O[j], p1) - max(O[i], p0) > 0 and min(O[l], q1) - max(O[k], q0) > 0: return False
            return True
        return clear(0) or clear(1)
    def distance(A, B):
        return max(0, max(B[1] - A[3], A[1] - B[3])) + max(0, max(B[0] - A[2], A[0] - B[2]))
    def label_kind(c): return "table" if re.sub(r"\s+", "", c["text"]).lower().startswith("table") else "figure"
    def has_graphic(b):
        if b.get("is_table") or b.get("is_chart") or any(by_id[m]["kind"] in ("image", "outline") for m in b["members"]): return True
        fills = [by_id[m]["box_px"] for m in b["members"] if by_id[m]["kind"] == "fill"]
        texts = [by_id[m]["box_px"] for m in b["members"] if by_id[m]["kind"] == "text"]
        if not fills: return False
        if not texts: return True
        # A figure caption's own shaded box is not a graphic: the block opens with a Figure label and the
        # fill fits its text within one and a half letter heights at the top, the bottom and the
        # left (a ragged last line leaves the right free; measured: AH06, each tinted caption box
        # became the figure, and the picture above it was left unpaired). A frame round a drawing
        # and its caption is taller than the text it holds.
        hull = [min(T[0] for T in texts), min(T[1] for T in texts), max(T[2] for T in texts), max(T[3] for T in texts)]
        pad = 1.5 * statistics.median(T[3] - T[1] for T in texts)
        def caption_box_fill(F): return all(abs(F[k] - hull[k]) <= pad for k in (0, 1, 3))
        # Figure captions only: a shaded Table caption keeps pairing as before, and assemble_tables
        # joins its grid (L10 p4: pairing the grid instead reordered the columns beside it).
        cap = caption_el(b); captioned = cap is not None and label_kind(cap) == "figure"
        # a drawn chart: one fill holds every text run of the block (its own lettering)
        return any(all(F[0] - 1 <= T[0] and T[2] <= F[2] + 1 and F[1] - 1 <= T[1] and T[3] <= F[3] + 1 for T in texts)
                   and not (captioned and caption_box_fill(F)) for F in fills)
    def caption_el(b):
        """a caption label begins its block: it is on the block's first text line, and first on that
        line in reading order; a reference that ends a sentence inside a paragraph is not one"""
        texts = [by_id[m] for m in b["members"] if by_id[m]["kind"] == "text"]
        if not texts: return None
        first_line = min(e["line"] for e in texts)
        rd = rd_for(block_angle(b))
        first = min((e for e in texts if e["line"] == first_line), key=lambda e: rd(e["box_px"])[0])
        return first if is_caption_run(first) else None
    def caption_box(b, c):
        """the caption: the label's line and the lines after it in the same block, with the caption's
        own shaded box when the block holds one round a Figure label (its edge is the caption's edge)"""
        ms = [by_id[m] for m in b["members"] if by_id[m]["kind"] == "text" and by_id[m]["line"] >= c["line"]]
        L = c["box_px"]
        ms += [by_id[m] for m in b["members"] if label_kind(c) == "figure" and by_id[m]["kind"] == "fill" and
               by_id[m]["box_px"][0] - 1 <= L[0] and L[2] <= by_id[m]["box_px"][2] + 1 and by_id[m]["box_px"][1] - 1 <= L[1] and L[3] <= by_id[m]["box_px"][3] + 1]
        return [min(e["box_px"][0] for e in ms), min(e["box_px"][1] for e in ms), max(e["box_px"][2] for e in ms), max(e["box_px"][3] for e in ms)]
    # a chart drawn in pieces: bars, axes, ticks and error bars (drawn-only blocks and drawn objects in no
    # block) and their short labels (one line of at most chart_label_chars characters, set no larger than
    # the page's median text, no caption) that lie within a letter height of each other join into one
    # graphic, when three or more of them are drawn and two or more are labels, and neither a piece nor the
    # whole lies within a letter height of, or over, a graphic of another kind (an image, lettering in one
    # fill: a frame or rules around a picture are not a chart); then its outer labels (a title, a legend and its
    # swatches, an axis title) within two letter heights of it join it too. A drawn object under text of
    # two or more lines (a panel behind prose), an image, a caption and a table never join.
    texts_all = [e for e in elements if e["kind"] == "text"]
    letter = statistics.median(e["size_px"] for e in texts_all) if texts_all else 0
    in_block = {m for b in blocks for m in b["members"]}
    tbl_boxes = [t["box_px"] for t in tables]
    prose = [by_id[m]["box_px"] for b in blocks if b["text_lines"] >= 2 or caption_el(b) for m in b["members"] if by_id[m]["kind"] == "text"]
    def under_prose(B): return any(min(B[2], T[2]) > max(B[0], T[0]) and min(B[3], T[3]) > max(B[1], T[1]) for T in prose)
    def in_tbl(B): return any(B[0] >= T[0] - 1 and B[2] <= T[2] + 1 and B[1] >= T[1] - 1 and B[3] <= T[3] + 1 for T in tbl_boxes)
    def drawn_only(b): return bool(b["members"]) and all(by_id[m]["kind"] in ("rule", "fill") for m in b["members"])
    def chart_label(b):
        ts = [by_id[m] for m in b["members"] if by_id[m]["kind"] == "text"]
        return bool(ts) and b["text_lines"] <= 1 and all(by_id[m]["kind"] in ("text", "rule", "fill") for m in b["members"]) \
            and len("".join(e["text"] for e in ts).replace(" ", "")) <= PARAMS["chart_label_chars"] and max(e["run_size_px"] for e in ts) <= letter and not caption_el(b)
    def near(A, B, d): return B[0] <= A[2] + d and B[2] >= A[0] - d and B[1] <= A[3] + d and B[3] >= A[1] - d
    pieces = [{"id": b["id"], "box_px": b["box_px"], "members": list(b["members"]), "drawn": drawn_only(b)} for b in blocks
              if not b.get("is_table") and ((drawn_only(b) and not under_prose(b["box_px"])) or chart_label(b))]
    pieces += [{"id": e["id"], "box_px": e["box_px"], "members": [e["id"]], "drawn": True} for e in elements
               if e["kind"] in ("rule", "fill") and e["id"] not in in_block and not in_tbl(e["box_px"]) and not under_prose(e["box_px"])]
    root = list(range(len(pieces)))
    def find(i):
        while root[i] != i: root[i] = root[root[i]]; i = root[i]
        return i
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            if near(pieces[i]["box_px"], pieces[j]["box_px"], letter): root[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i in range(len(pieces)): groups[find(i)].append(pieces[i])
    piece_ids = {x["id"] for x in pieces}
    graphics = [b["box_px"] for b in blocks if b["id"] not in piece_ids and not b.get("is_table") and has_graphic(b) and not all(by_id[m]["kind"] == "outline" for m in b["members"])]   # a legend swatch is the chart's own
    def hull_of(g): return [min(x["box_px"][0] for x in g), min(x["box_px"][1] for x in g), max(x["box_px"][2] for x in g), max(x["box_px"][3] for x in g)]
    charts = [g for g in groups.values() if sum(1 for x in g if x["drawn"]) >= 3 and sum(1 for x in g if not x["drawn"]) >= 2
              and not any(near(x["box_px"], G, letter) for x in g for G in graphics) and not any(near(hull_of(g), G, 0) for G in graphics)]
    taken = {x["id"] for g in charts for x in g}
    outer = [{"id": b["id"], "box_px": b["box_px"], "members": list(b["members"]), "drawn": False} for b in blocks
             if b["id"] not in taken and not b.get("is_table") and (chart_label(b) or (b["members"] and all(by_id[m]["kind"] == "outline" for m in b["members"])))]
    for g in charts:
        grew = True
        while grew:
            grew = False
            H = [min(x["box_px"][0] for x in g), min(x["box_px"][1] for x in g), max(x["box_px"][2] for x in g), max(x["box_px"][3] for x in g)]
            for o in outer:
                if o["id"] not in taken and near(H, o["box_px"], 2 * letter): g.append(o); taken.add(o["id"]); grew = True
    blocks = [b for b in blocks if b["id"] not in taken]
    for k, g in enumerate(sorted(charts, key=lambda g: (min(x["box_px"][1] for x in g), min(x["box_px"][0] for x in g)))):
        blocks.append({"id": f"chart:{k + 1}", "box_px": [min(x["box_px"][0] for x in g), min(x["box_px"][1] for x in g), max(x["box_px"][2] for x in g), max(x["box_px"][3] for x in g)],
                       "members": [m for x in g for m in x["members"]], "text_lines": 0, "kinds": ["chart"], "is_chart": True})
    floats = []; used = set(); unpaired = []
    for t in [b for b in blocks if b.get("is_table")]:
        T = t["box_px"]
        inside = [e for e in elements if e["kind"] == "text" and is_caption_run(e) and T[0] - 1 <= e["box_px"][0] and e["box_px"][2] <= T[2] + 1 and T[1] - 1 <= e["box_px"][1] and e["box_px"][3] <= T[3] + 1]
        if inside:
            floats.append({"box_px": T, "caption": inside[0]["text"][:80], "blocks": [t["id"]], "basis": "caption label inside the table box"}); used.add(t["id"])
    for b in blocks:
        c = caption_el(b)
        if c and has_graphic(b):
            floats.append({"box_px": b["box_px"], "caption": c["text"][:80], "blocks": [b["id"]], "basis": "graphic and caption label in one larger box"}); used.add(b["id"])
    # each caption and each graphic is paired once, the nearest pairs first: where two captions stand
    # against one graphic (a legend carried over from the page before, above it; the graphic's own
    # caption, below it), the nearer caption is the graphic's and the other is left unpaired
    cand = []; caps = []
    for b in blocks:
        if b["id"] in used: continue
        c = caption_el(b)
        if not c: continue
        caps.append((b, c)); rd = rd_for(block_angle(b)); want = label_kind(c)
        for g in blocks:
            if g["id"] in used or g is b or not has_graphic(g): continue
            if (want == "table") != bool(g.get("is_table")): continue
            A, B = rd(b["box_px"]), rd(g["box_px"])
            gap = distance(A, B)
            def intersects(o, t): O, T = o["box_px"], t["box_px"]; return min(O[2], T[2]) > max(O[0], T[0]) and min(O[3], T[3]) > max(O[1], T[1])
            others = [o for o in blocks if not (g.get("is_table") and intersects(o, g))]   # blocks touching a table are its own
            if nothing_between(b, g, others, rd): cand.append((gap, len(cand), b["id"], g))
    match = {}; matched = set()
    for gap, _, bid, g in sorted(cand, key=lambda x: (x[0], x[1])):
        if bid in match or g["id"] in matched: continue
        match[bid] = g; matched.add(g["id"])
    for b, c in caps:   # in the blocks' own order, so the floats keep their numbering
        g = match.get(b["id"])
        if g is not None:
            A, B = caption_box(b, c), g["box_px"]
            floats.append({"box_px": [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])], "caption": c["text"][:80],
                           "blocks": [b["id"], g["id"]], "basis": "caption-label box directly adjacent to a " + ("chart drawn in pieces" if g.get("is_chart") else "graphic box")}); used.update((b["id"], g["id"]))
        else:
            unpaired.append({"kind": "caption without a graphic on this page", "caption": c["text"][:80], "box_px": caption_box(b, c), "block": b["id"]})
    # a figure stored as several strips: absorb graphic-only blocks stacked against the float,
    # within one caption letter height, repeated until nothing more joins
    main_runs = main_text_runs([e for e in elements if e["kind"] == "text"], blocks)
    def chain_barred(g):
        """R1/R2 (lane stream): a block holding a main-text run never joins a float by the strip chain, and
        neither does a block whose drawn members are all overlay ink (pen marks: overlay_ink)."""
        drawn = [by_id[m] for m in g["members"] if by_id[m]["kind"] != "text"]
        return any(m in main_runs for m in g["members"]) or (bool(drawn) and all(d.get("overlay") for d in drawn))
    for f in floats:
        if any(bid.startswith("table:") for bid in f["blocks"]): continue
        grew = True
        while grew:
            grew = False
            for g in blocks:
                if g["id"] in used or g.get("is_table") or not has_graphic(g) or caption_el(g) or chain_barred(g): continue
                A, B = f["box_px"], g["box_px"]
                touching = min(A[2], B[2]) - max(A[0], B[0]) >= PARAMS["side_overlap_px"] and max(B[1] - A[3], A[1] - B[3]) <= PARAMS["strip_touch_px"] and "image" in g["kinds"] and g["text_lines"] == 0
                images = [by_id[m]["box_px"] for m in g["members"] if by_id[m]["kind"] == "image"]
                lettering = [by_id[m] for m in g["members"] if by_id[m]["kind"] == "text"]
                panel = bool(images) and bool(lettering) and all(re.fullmatch(r"\(?[A-Za-z]\)?", e["text"].strip()) and any(I[0] <= e["box_px"][0] and e["box_px"][2] <= I[2] and I[1] <= e["box_px"][1] and e["box_px"][3] <= I[3] for I in images) for e in lettering)
                stacked = panel and min(A[2], B[2]) - max(A[0], B[0]) >= PARAMS["side_overlap_px"] and 0 <= max(B[1] - A[3], A[1] - B[3]) <= letter and nothing_between({"box_px": A}, g, [o for o in blocks if o["id"] not in f["blocks"]])
                # a panel beside the float: side by side, sharing at least half the shorter one's height, nothing between
                yo = min(A[3], B[3]) - max(A[1], B[1])
                beside = yo >= 0.5 * min(A[3] - A[1], B[3] - B[1]) and nothing_between({"box_px": f["box_px"]}, g, [o for o in blocks if o["id"] not in f["blocks"] and o["id"] != g["id"]])
                if touching or beside or stacked:
                    f["box_px"] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])]
                    f["blocks"].append(g["id"]); used.add(g["id"]); grew = True
    join_figure_lettering(elements, source_blocks, tables, floats, unpaired)
    blocks += [b for b in source_blocks if b.get("figure_lettering")]
    # an image object's bounds can run past its picture into a neighbouring text line: the float box
    # is trimmed so that no text run of another block lies inside it
    for f in floats:
        if any(bid.startswith("table:") for bid in f["blocks"]): continue   # a table's cells are its own text; only figures are trimmed
        own = set(f.get("members", []))
        for b in blocks:
            if b["id"] in f["blocks"]: own.update(b["members"])
        cap = next((e for e in elements if e["id"] in own and e["kind"] == "text" and is_caption_run(e)), None)   # in element order: a set's order depends on the hash seed
        if cap:   # the caption text beside the label, on the label's line, is the caption's too
            cy0, cy1 = cap["box_px"][1], cap["box_px"][3]
            for e in elements:
                if e["kind"] == "text" and e["box_px"][1] < cy1 and e["box_px"][3] > cy0: own.add(e["id"])
        changed = True
        while changed:
            changed = False
            for e in elements:
                if e["kind"] != "text" or e["id"] in own: continue
                B, F = e["box_px"], f["box_px"]
                if min(B[2], F[2]) - max(B[0], F[0]) <= 0 or min(B[3], F[3]) - max(B[1], F[1]) <= 0: continue
                cy = (B[1] + B[3]) / 2; cx = (B[0] + B[2]) / 2
                # trim on the side the run is nearest to
                d = {"top": cy - F[1], "bottom": F[3] - cy, "left": cx - F[0], "right": F[2] - cx}
                side = min(d, key=d.get)
                if side == "top": f["box_px"] = [F[0], B[3] + 1, F[2], F[3]]
                elif side == "bottom": f["box_px"] = [F[0], F[1], F[2], B[1] - 1]
                elif side == "left": f["box_px"] = [B[2] + 1, F[1], F[2], F[3]]
                else: f["box_px"] = [F[0], F[1], B[0] - 1, F[3]]
                f.setdefault("trimmed", []).append({"run": e["id"], "text": e["text"][:40], "side": side}); changed = True; break
    fig_boxes = [f["box_px"] for f in floats if label_kind({"text": f["caption"]}) == "figure"]
    def within(b, F): return b[0] >= F[0] - 2 and b[1] >= F[1] - 2 and b[2] <= F[2] + 2 and b[3] <= F[3] + 2
    for t in [b for b in blocks if b.get("is_table")]:
        if any(within(t["box_px"], F) for F in fig_boxes):
            for tt in tables:
                if tt["id"] == t["id"]: tt["demoted"] = "inside a figure float: the figure's lettering, not a table"
            floats = [f for f in floats if t["id"] not in f["blocks"]]; used.add(t["id"])
    for i, f in enumerate(floats): f["id"] = f"float:{i+1}"
    for g in blocks:   # graphics and tables left without a caption on this page
        if g["id"] in used or not has_graphic(g) or g["text_lines"] > 0: continue
        if any(by_id[m]["kind"] == "image" for m in g["members"]) or g.get("is_table"):
            unpaired.append({"kind": "graphic without a caption on this page", "box_px": g["box_px"], "block": g["id"]})
    floats_with_captions.unpaired = unpaired
    return floats

def assemble_tables(elements, blocks, tables, floats, unpaired):
    """Rule 4, last step: a table's float takes in the pieces of its table that rules 2 and 3 left outside
    it. In the table's own reading frame, and repeated until nothing more joins:
      - a table no caption claimed, under or over it (its sideways span shares assemble_overlap of the
        narrower) within assemble_table_gap_em body letter heights, or anywhere on a page whose only
        captioned table this is;
      - a block of table cells, set at the table's angle, lying within its box (assemble_overlap of the
        block's width inside its sideways span), or of two or more runs beside it (within
        assemble_beside_em, inside its vertical span) or under or over it (within assemble_stack_em).
        Table cells means its lines are short: their median width is under assemble_cell_share of the
        page's column width (the median width of blocks of three lines or more; for a table set sideways,
        0.45 of the extent of the page's text at its angle), and it is set no larger
        than the body (body_size_tolerance).
    Taken only if the grown box covers no running text: when a run of a block of two or more lines that are
    not table cells would lie in the grown box (its centre) outside the float's box before, nothing joins and
    the float is flagged; other blocks inside the grown box (a "(Continues)" note) join it. A joined block
    or table is listed in the float's "assembled" and no longer recorded as unpaired. (Measured: N08 p6
    Table 5 split into a captioned table, an uncaptioned table and its label column in the body; N17 p6 a
    sideways table whose body rule 3 found apart from its caption.)"""
    by_id = {e["id"]: e for e in elements}
    texts = [e for e in elements if e["kind"] == "text"]
    assemble_tables.unpaired = unpaired
    if not texts or not floats: return floats
    body = statistics.median(e["size_px"] for e in texts)
    wides = sorted(b["box_px"][2] - b["box_px"][0] for b in blocks if b.get("text_lines", 0) >= 3)
    colw = wides[len(wides) // 2] if wides else 0.45 * (max(e["box_px"][2] for e in texts) - min(e["box_px"][0] for e in texts))
    tab = {t["id"]: t for t in tables if not t.get("demoted")}
    claimed = {b for f in floats for b in f["blocks"]}
    table_floats = [f for f in floats if any(b in tab for b in f["blocks"])]
    def tm(ms): return [m for m in ms if m in by_id and by_id[m]["kind"] == "text"]
    def hull(bs): bs = list(bs); return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    def x_overlap(a, b): return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) / max(1e-6, min(a[2] - a[0], b[2] - b[0]))
    def x_share(b, r): return max(0.0, min(b[2], r[2]) - max(b[0], r[0])) / max(1e-6, b[2] - b[0])
    tol = PARAMS["body_size_tolerance"]
    def layout_box(b):
        """R2 (lane stream): a block's extent without its overlay ink (pen marks never extend a table piece)"""
        ms = [by_id[m]["box_px"] for m in b["members"] if m in by_id and not by_id[m].get("overlay")]
        return hull(ms) if ms else b["box_px"]
    for f in table_floats:
        own_tabs = [b for b in f["blocks"] if b in tab]
        angs = [by_id[m]["angle"] for t in own_tabs for m in tm(tab[t]["members"])]
        ang = collections.Counter(angs).most_common(1)[0][0] if angs else 0
        to_read, _ = frame(ang)
        def rd(b):
            u0, v0, u1, v1 = to_read(*b); return (min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))
        def b_angle(b):
            ms = tm(b["members"]); return collections.Counter(by_id[m]["angle"] for m in ms).most_common(1)[0][0] if ms else None
        if ang == 0: colw_f = colw
        else:   # a table set sideways: its page's text runs that way, so a column is a share of that text's extent
            us = [rd(e["box_px"]) for e in texts if e["angle"] == ang]
            colw_f = 0.45 * (max(u[2] for u in us) - min(u[0] for u in us))
        def cells(b):
            ms = tm(b["members"])
            if not ms: return False
            if statistics.median(by_id[m]["size_px"] for m in ms) > body * (1 + tol): return False
            lines = collections.defaultdict(list)
            for m in ms: lines[by_id[m]["line"]].append(rd(by_id[m]["box_px"]))
            ws = sorted(hull(v)[2] - hull(v)[0] for v in lines.values())
            return ws[len(ws) // 2] < PARAMS["assemble_cell_share"] * colw_f
        F0 = list(f["box_px"]); R = rd(F0); added = []; boxes = [F0]
        changed = True
        while changed:
            changed = False
            for tid, t in tab.items():
                if tid in claimed or tid in added: continue
                T = rd(t["box_px"])
                near = T[1] - R[3] <= PARAMS["assemble_table_gap_em"] * body and R[1] - T[3] <= PARAMS["assemble_table_gap_em"] * body
                if x_overlap(T, R) >= PARAMS["assemble_overlap"] and (near or len(table_floats) == 1):
                    added.append(tid); boxes.append(t["box_px"]); R = rd(hull(boxes)); changed = True
            for b in blocks:
                if b["id"] in claimed or b["id"] in added or b.get("is_table") or not tm(b["members"]): continue
                B = rd(layout_box(b))
                if B[0] >= rd(F0)[0] - 1 and B[2] <= rd(F0)[2] + 1 and B[1] >= rd(F0)[1] - 1 and B[3] <= rd(F0)[3] + 1: continue   # already within the float
                inside = x_share(B, R) >= PARAMS["assemble_overlap"] and B[1] >= R[1] - 1 and B[3] <= R[3] + 1
                stacked = x_overlap(B, R) >= PARAMS["assemble_overlap"] and R[1] - PARAMS["assemble_stack_em"] * body <= B[3] and B[1] <= R[3] + PARAMS["assemble_stack_em"] * body
                beside = B[1] >= R[1] - 0.5 * body and B[3] <= R[3] + 0.5 * body and B[0] - R[2] <= PARAMS["assemble_beside_em"] * body and R[0] - B[2] <= PARAMS["assemble_beside_em"] * body
                ms = tm(b["members"])
                if collections.Counter(by_id[m]["angle"] for m in ms).most_common(1)[0][0] != ang: continue   # set at another angle (a margin notice)
                if not cells(b): continue
                if (stacked or beside) and not inside and len(ms) < 2: continue   # a lone piece next to it (a page number, a running head) is not a row of cells
                if inside or stacked or beside:
                    added.append(b["id"]); boxes.append(layout_box(b)); R = rd(hull(boxes)); changed = True
        if not added: continue
        H = hull(boxes)
        mine = set()
        for bid in list(f["blocks"]) + added:
            src = tab.get(bid) or next((b for b in blocks if b["id"] == bid), None)
            if src: mine.update(src["members"])
        def centre_in(b, B): cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; return B[0] <= cx <= B[2] and B[1] <= cy <= B[3]
        inner = [e for e in texts if e["id"] not in mine and centre_in(e["box_px"], H) and not centre_in(e["box_px"], F0)]
        owner = {m: b for b in blocks if not b.get("is_table") for m in b["members"]}
        prose = [e for e in inner if owner.get(e["id"]) and owner[e["id"]].get("text_lines", 0) >= 2 and not cells(owner[e["id"]])]
        if prose:   # the grown box would cover running text: nothing joins
            f.setdefault("flags", []).append(f"table pieces not joined: {len(prose)} run(s) of running text would lie in the grown box: " + "; ".join(e["id"] + " " + repr(e["text"][:30]) for e in prose[:3]))
            continue
        for e in inner:   # short pieces inside the grown box (a "(Continued)" note) are the table's
            o = owner.get(e["id"])
            if o and o["id"] not in added and o["id"] not in claimed: added.append(o["id"])
        f["box_px"] = H; f["blocks"] = list(f["blocks"]) + added; f["assembled"] = added; claimed.update(added)
    assemble_tables.unpaired = [u for u in unpaired if u.get("block") not in claimed or u.get("kind") == "caption outside graphic rectangle"]
    return floats

def journal_art(elements, blocks, floats, tables, angle):
    """Rule 5: the elements that are journal art on the float-free copy."""
    by_id = {e["id"]: e for e in elements}
    block_of = {m: b for b in blocks for m in b["members"]}
    def inside(b, F): return b[0] >= F[0] - 2 and b[1] >= F[1] - 2 and b[2] <= F[2] + 2 and b[3] <= F[3] + 2
    keep_boxes = [f["box_px"] for f in floats] + [t["box_px"] for t in tables]
    def touches(b, F): return min(b[2] + 0.5, F[2]) - max(b[0] - 0.5, F[0]) > 0 and min(b[3] + 0.5, F[3]) - max(b[1] - 0.5, F[1]) > 0   # a hairline rule has no height of its own
    def block_angle(b):
        ts = [by_id[m]["angle"] for m in b["members"] if by_id[m]["kind"] == "text"]
        return collections.Counter(ts).most_common(1)[0][0] if ts else None
    multi = [b for b in blocks if b["text_lines"] >= 2 and block_angle(b) == angle and not any(inside(b["box_px"], F) for F in keep_boxes)]
    # the text frame: the paper's own matter on the page, its multi-line text blocks together with
    # its floats and tables (a page holding only a table still has a frame)
    frame_boxes = [b["box_px"] for b in multi] + keep_boxes
    if not blocks:   # rule 5 run straight after rule 1: the frame is the hull of the text runs in the main orientation
        frame_boxes = [e["box_px"] for e in elements if e["kind"] == "text" and e["angle"] == angle]
    frame = [min(b[0] for b in frame_boxes), min(b[1] for b in frame_boxes), max(b[2] for b in frame_boxes), max(b[3] for b in frame_boxes)] if frame_boxes else None
    # a drawn object inside a text line (an ORCID icon drawn as paths) is part of the line, never art:
    # it lies within the vertical extent of a text run on its line and its block holds text
    text_runs = [e for e in elements if e["kind"] == "text"]
    line_runs = [e for e in text_runs if e["angle"] == angle]   # lines in the reading orientation only: a rotated margin notice is not a line an icon sits in
    def in_text_line(b):
        blk = block_of.get(b["id"]) if "id" in b else None
        for t in line_runs:
            T = t["box_px"]; B = b["box_px"]
            h = T[3] - T[1]; cy = (B[1] + B[3]) / 2
            if T[1] <= cy <= T[3] and (B[3] - B[1]) <= PARAMS["icon_max_em"] * h and (B[2] - B[0]) <= PARAMS["icon_max_em"] * h and (abs(B[0] - T[2]) <= PARAMS["icon_max_em"] * h or abs(T[0] - B[2]) <= PARAMS["icon_max_em"] * h):
                return True   # beside a run on its line, icon-sized (an ORCID icon, a heading separator)
            if b["kind"] == "rule" and (B[3] - B[1]) <= px(PARAMS["rule_max_pt"]) and T[3] - 0.1 * h <= cy <= T[3] + 0.5 * h and B[0] >= T[0] - 0.5 * h and B[2] <= T[2] + 0.5 * h:
                return True   # a rule just under a run and no wider than it: an underline
        return False
    # ... and it stands alone: every other drawn object within a line height of it is also inside a
    # text line, so a fragment of a larger piece of art that happens to cross a line is not an icon
    drawn = [e for e in elements if e["kind"] in ("image", "outline", "fill", "rule") and not any(touches(e["box_px"], F) for F in keep_boxes)]
    in_line = {e["id"] for e in drawn if in_text_line(e)}
    def near(a, b, d):
        A, B = a["box_px"], b["box_px"]; return B[0] <= A[2] + d and B[2] >= A[0] - d and B[1] <= A[3] + d and B[3] >= A[1] - d
    # the pieces of an icon are the drawn objects inside its box; an icon stands alone when every
    # other drawn object near it is itself in a text line or a piece of one that is
    cand = [e for e in drawn if e["id"] in in_line]
    # The x-start bounds below are necessary for inside and near. Their
    # prefixes are supersets; the original predicates still make each decision.
    cand_by_x = sorted(cand, key=lambda e: e["box_px"][0])
    cand_x0 = [e["box_px"][0] for e in cand_by_x]
    drawn_by_x = sorted(drawn, key=lambda e: e["box_px"][0])
    drawn_x0 = [e["box_px"][0] for e in drawn_by_x]
    parts = {o["id"] for o in drawn if any(o is not c and inside(o["box_px"], c["box_px"])
             for c in cand_by_x[:bisect.bisect_right(cand_x0, o["box_px"][0] + 2)])}
    def drawn_candidates(e, d):
        A = e["box_px"]
        return (o for o in drawn_by_x[:bisect.bisect_right(drawn_x0, A[2] + d)]
                if o["box_px"][2] >= A[0] - d)
    icons = set()
    for e in cand:
        h = e["box_px"][3] - e["box_px"][1]
        if all(o["id"] in in_line or o["id"] in parts for o in drawn_candidates(e, max(h, 4)) if o is not e and near(e, o, max(h, 4))):
            icons.add(e["id"]); icons |= {o["id"] for o in drawn_candidates(e, 2) if inside(o["box_px"], e["box_px"])}
    images = [e["box_px"] for e in elements if e["kind"] == "image"]
    def holds_image(b): return any(I[0] >= b[0] - 1 and I[2] <= b[2] + 1 and I[1] >= b[1] - 1 and I[3] <= b[3] + 1 for I in images)
    def holds_text(b): return any(t["box_px"][0] >= b[0] - 1 and t["box_px"][2] <= b[2] + 1 and t["box_px"][1] >= b[1] - 1 and t["box_px"][3] <= b[3] + 1 for t in text_runs)
    art = []
    for e in elements:
        if e["kind"] == "text": continue
        if any(touches(e["box_px"], F) for F in keep_boxes): continue
        if e["id"] in icons: continue
        if e["kind"] == "fill" and (holds_text(e["box_px"]) or holds_image(e["box_px"])): continue   # a box drawn around the paper's own text or picture is not art
        if e["kind"] in ("clipped", "rule", "fill", "outline"):
            art.append({"id": e["id"], "kind": e["kind"], "box_px": e["box_px"], "basis": "unpainted text" if e["kind"] == "clipped" else "drawn object outside every float and table"}); continue
        if e["kind"] == "image":
            blk = block_of.get(e["id"])
            if blk and blk["text_lines"] > 0:   # an image inside a text line (an ORCID icon) stays: it is part of the line, not art (user ruling 2026-10-17); it is icon-sized, so a masthead logo with glyph text in it is not exempt
                mem = set(blk["members"]); hs = [x["size_px"] for x in elements if x["kind"] == "text" and x["id"] in mem]
                h = statistics.median(hs) if hs else 0
                if (e["box_px"][3] - e["box_px"][1]) <= PARAMS["icon_max_em"] * h and (e["box_px"][2] - e["box_px"][0]) <= PARAMS["icon_max_em"] * h: continue
            elif not blocks and in_text_line(e): continue
            if frame and (e["box_px"][3] <= frame[1] or e["box_px"][1] >= frame[3]):
                art.append({"id": e["id"], "kind": "image", "box_px": e["box_px"], "basis": "image above or below the text frame: a logo"}); continue
    return art

ORDER = os.environ.get("BOXER_ORDER", "12345")

def r5_line_failures(new, base):
    """Lane r5-line output check: for each line the lane's changes touched, compared with the page built without
    them (the earlier behaviour): (1) the line holds one earlier line, plus only whole earlier lines of at most eight
    small characters (scripts, under superscript_em of that line's size); no full-size character of the earlier
    line went to another line; (2) its characters are in no more blocks than before, and in the block of the earlier
    line's neighbours above and below in its block; (3) a word space stands between two adjacent characters only
    where the earlier build had one between them, and none was taken away. Returns the boxes of the failing lines."""
    info = new["_r5_char_info"]
    def maps(res):
        line, elem, block, order, spaced = {}, {}, {}, {}, set()
        bl = {}
        for b in res.get("blocks", []):
            for m in b.get("members", []): bl[m] = b["id"]
        for e in res["elements"]:
            if e.get("kind") != "text" or "char_ids" not in e: continue
            for k, i in enumerate(e["char_ids"]):
                line[i] = e["line"]; elem[i] = e["id"]; block[i] = bl.get(e["id"]); order[i] = (e["id"], k)
            spaced.update(e.get("_spaced", []))
        return line, elem, block, order, spaced
    nl, ne, nb, no, ns = maps(new); bl_, be, bb, bo, bs = maps(base)
    nlines, blines = collections.defaultdict(list), collections.defaultdict(list)
    for i, l in nl.items(): nlines[l].append(i)
    for i, l in bl_.items(): blines[l].append(i)
    belem = collections.defaultdict(list)
    for i, (e, k) in bo.items(): belem[e].append((k, i))
    nelem = collections.defaultdict(list)
    for i, (e, k) in no.items(): nelem[e].append((k, i))
    touched = {nl[i] for i in new.get("_r5_line_ids", []) if i in nl}
    # and every line whose characters are not exactly one earlier line's, whatever changed it (memo line-holdback-2)
    bsets = {frozenset(v) for v in blines.values()}
    touched |= {l for l, v in nlines.items() if frozenset(v) not in bsets}
    fails = []
    for l in touched:
        C = set(nlines[l]); bad = False
        counts = collections.Counter(bl_[i] for i in C if i in bl_)
        if not counts: continue
        home = counts.most_common(1)[0][0]
        hsizes = sorted(info[i][0] for i in blines[home])
        hsize = hsizes[len(hsizes) // 2]
        for h in counts:
            if h == home: continue
            hs = blines[h]
            if not (set(hs) <= C and len(hs) <= 8 and all(info[i][0] < PARAMS["superscript_em"] * hsize for i in hs)): bad = True
            else:
                # (memo line-holdback-2) the earlier line joins only if it overlaps the height of the line it joins and
                # each of its characters stands within half a letter of a character of that line, beside or over it
                own = [i for i in blines[home] if i in C]
                if own:
                    top, bot = min(info[i][1][1] for i in own), max(info[i][1][3] for i in own)
                    if min(info[i][1][3] for i in hs) <= top or max(info[i][1][1] for i in hs) >= bot: bad = True
                    if not all(any(max(info[j][1][0] - info[i][1][2], info[i][1][0] - info[j][1][2]) <= 0.5 * hsize for j in own) for i in hs): bad = True
        if any(i not in C and info[i][0] >= PARAMS["superscript_em"] * hsize for i in blines[home]): bad = True
        if not bad:
            nbs = {nb.get(i) for i in C}; bbs = {bb.get(i) for i in C}
            if len(nbs) > len(bbs): bad = True
            else:
                # per earlier block on the line (a row may cross two columns): its characters and their block-mates on the
                # earlier lines above and below share one block in this build too
                for hb in {bb.get(i) for i in blines[home]} - {None}:
                    own = [i for i in blines[home] if bb.get(i) == hb]
                    main = collections.Counter(nb.get(i) for i in own).most_common(1)[0][0]
                    for other in (home - 1, home + 1):
                        mates = [i for i in blines.get(other, []) if bb.get(i) == hb and i not in C]
                        if mates and collections.Counter(nb.get(i) for i in mates).most_common(1)[0][0] != main: bad = True
        if not bad:
            for e in {ne[i] for i in C}:
                seq = [i for k, i in sorted(nelem[e])]
                for a_, b_ in zip(seq, seq[1:]):
                    same = be.get(a_) is not None and be.get(a_) == be.get(b_) and bo[b_][1] == bo[a_][1] + 1
                    if b_ in ns and same and b_ not in bs: bad = True     # a space where the earlier build had none
                    if b_ not in ns and same and b_ in bs: bad = True     # a space taken away
                # a space inside a word: the earlier neighbour of b_ is still left of it in this element, with no space then
                for k, b_ in enumerate(seq):
                    if b_ not in ns or b_ not in bo or bo[b_][1] == 0: continue
                    pb = sorted(belem[bo[b_][0]])[bo[b_][1] - 1][1]
                    if pb in seq[:k] and b_ not in bs: bad = True
        if bad: fails.extend(info[i][1] for i in C)
    return fails


R5_BASE = {}   # lane r5-line: page -> the page built without the lane's changes, where the lane touched it


def _r5_clean(res):
    for k in ("_r5_line_boxes", "_r5_line_ids", "_r5_char_info"): res.pop(k, None)
    for e in res.get("elements", []): e.pop("_spaced", None)
    return res


def _box_elements_scoped(pdf_path, part, label, drop_boxes=()):
    """Lane r5-line: the page is built once. If no line was touched by the lane's O20/O21 changes, that build stands.
    Otherwise the page is also built without them (the earlier behaviour, the whole page a keep zone); lines that fail
    the output check (r5_line_failures) and lines inside a table or a float become keep zones, and the page is built
    again with those zones, where the earlier behaviour holds."""
    R5_BASE.pop(part["page"], None)
    result = _box_elements(pdf_path, part, label, drop_boxes=drop_boxes)
    if "error" in result or not result.get("_r5_line_ids"): return _r5_clean(result)
    touched = result.get("_r5_line_boxes", [])
    zones = [t["box_px"] for t in result.get("tables", []) if t.get("box_px")] + [f["box_px"] for f in result.get("floats", []) if f.get("box_px")]
    def inside(b):
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return any(z[0] <= cx <= z[2] and z[1] <= cy <= z[3] for z in zones)
    zones = zones if any(inside(b) for b in touched) else []
    base = _box_elements(pdf_path, part, label, drop_boxes=drop_boxes, keep_zones=[[-1e9, -1e9, 1e9, 1e9]])
    R5_BASE[part["page"]] = _r5_clean(dict(base, elements=[dict(e) for e in base.get("elements", [])]))   # for the first-page check
    fails = r5_line_failures(result, base) if "error" not in base else []
    if not zones and not fails: return _r5_clean(result)
    again = _box_elements(pdf_path, part, label, drop_boxes=drop_boxes, keep_zones=zones + [[b[0] - 0.5, b[1] - 0.5, b[2] + 0.5, b[3] + 0.5] for b in fails])
    return _r5_clean(again)


def box_elements(pdf_path, part, label, out_prefix=None, second_pass=False):
    result = _box_elements_scoped(pdf_path, part, label)
    if ORDER == "15234" and not second_pass and "error" not in result:
        # rule 5 straight after rule 1: art from the elements alone, no floats, tables or blocks known
        art = journal_art(result["elements"], [], [], [], result["reading_angle"])
        if not art: result["pass"] = 1; result["art"] = []; return result
        second = _box_elements_scoped(pdf_path, part, label, drop_boxes=[a["box_px"] for a in art])
        second["pass"] = 2; second["art"] = art; second["order"] = ORDER
        second["first_pass"] = {"elements": len(result["elements"]), "blocks": len(result["blocks"]), "tables": len(result["tables"]), "floats": len(result["floats"])}
        second["first_pass_result"] = result
        return second
    if second_pass or "error" in result or not result.get("art"): 
        result["pass"] = 2 if second_pass else 1; return result
    # rule 5, second half: remove the art from the page and run rules 1 to 4 again on what remains,
    # so an element the art had split is boxed whole
    art = result["art"]
    second = _box_elements_scoped(pdf_path, part, label, drop_boxes=[a["box_px"] for a in art])
    second["pass"] = 2; second["art"] = art
    second["first_pass"] = {"elements": len(result["elements"]), "blocks": len(result["blocks"]), "tables": len(result["tables"]), "floats": len(result["floats"])}
    second["first_pass_result"] = result
    return second

def diagonal_watermarks(chars, box):
    """Large oblique display text crossing the body is furniture before clustering.

    Use the PDF's unsnapped angle, font and size. Only overlays that would snap
    into the upright dominant body frame need this early isolation; text in a separate
    reading frame keeps the existing rule-6 recurrent-watermark handling.
    At least eight letters on one
    straight baseline must span 40% of both page axes, with a size at least
    three times the character-weighted body median, with light/transparent fill
    or outline rendering. Small diagonal plot labels,
    sideways tables, ordinary display headings and paragraph initials survive.
    Retain the original character IDs and geometry for a furniture audit.
    """
    if not chars: return []
    body = statistics.median(c['size'] for c in chars)
    snapped = lambda angle: min((0, 90, 270, 360), key=lambda a:abs(a-angle)) % 360
    dominant = collections.Counter(snapped(c['angle']) for c in chars).most_common(1)[0][0]
    # Sideways tables need their existing orientation/row ownership retained.
    # Removing an overlay before that layout is normalized can reorder cells.
    if dominant != 0: return []
    groups = collections.defaultdict(list)
    for c in chars:
        color = c.get('fill_color')
        light = (isinstance(color, (int, float)) and color >= .65 or
                 isinstance(color, (list, tuple)) and
                 (len(color)==3 and all(isinstance(v,(int,float)) and v>=.65 for v in color) or
                  len(color)==4 and all(isinstance(v,(int,float)) for v in color) and sum(color)<=.35))
        if (min(abs(c['angle'] - a) for a in (0, 90, 180, 270, 360)) >= 15
                and snapped(c['angle']) == dominant
                and c['size'] >= 3 * body and
                (light or c.get('render_mode') in (1, 2, 5, 6) or c.get('fill_alpha', 1) <= .5)):
            groups[(c['angle'], c.get('font'), round(c['size']))].append(c)
    found = []
    for group in groups.values():
        if sum(c['text'].isalpha() for c in group) < 8: continue
        # Test the actual origins, rather than the rounded reading angle. Some
        # PDFs use an anisotropic matrix, so its reported angle is approximate.
        a, z = min(group, key=lambda c:c['origin'][0]), max(group, key=lambda c:c['origin'][0])
        dx, dy = z['origin'][0]-a['origin'][0], z['origin'][1]-a['origin'][1]
        if abs(dx) < .4*(box[2]-box[0]) or abs(dy) < .4*(box[3]-box[1]): continue
        length = math.hypot(dx, dy)
        if any(abs(dx*(c['origin'][1]-a['origin'][1])-dy*(c['origin'][0]-a['origin'][0]))/length
               > .2*body for c in group): continue
        found.append(sorted(group, key=lambda c:c['paint_order']))
    return found


def repository_cover(page, following):
    """A download wrapper needs service metadata, no abstract, and a following article.

    Repository names alone (for example in an affiliation) are insufficient.
    Counters/profile controls or an explicit library download/cover notice must
    accompany the service identity. A following abstract corroborates the wrapper, as does
    the cover's display title repeated (five or more of its words, most of them) on one of
    the following pages.
    A thesis deposit instead needs an access/inclusion notice, a download URL and
    a matching uppercase submitted title after only optional rights-only leaves.
    """
    rows = [e['text'] for e in page['elements'] if e['kind']=='text']
    text = ' '.join(rows)
    heading = lambda s: re.search(r'\babstract\b|\bsummary\b', re.sub(r'(?<=\b[A-Za-z])\s+(?=[A-Za-z]\b)', '', s), re.I)
    if (heading(text) or len(text.split()) > 450 or
            any(re.match(r'^\s*(?:Introduction|Materials and methods|Results|Discussion)\b', r, re.I) for r in rows)):
        return False
    service = re.search(r'researchgate|academia\.edu|\blibrary\b|\brepository\b', text, re.I)
    controls = re.search(r'see discussions,?\s*stats|see profile|view project|download(?:ed|s)?|cover sheet', text, re.I)
    metadata = re.search(r'\bcitations\b|\breads\b|\bviews\b|\buploaded\b|\bretrieved\b|\bdownloaded\b', text, re.I)
    following = following if isinstance(following, list) else [following]
    next_text = ' '.join(e['text'] for e in following[0]['elements'] if e['kind']=='text') if following else ''
    # The article itself also corroborates the wrapper when it repeats the
    # cover's display title on one of the following pages (AG05: an unlabelled
    # abstract after a picture page; measured 2026-10-24). The repeat must
    # carry at least five of the title's words and most of them.
    def repeated_title():
        texts = [e for e in page['elements'] if e['kind'] == 'text' and len(e['text'].split()) >= 3]
        if not texts: return False
        top = max(e.get('run_size_px', 0) for e in texts)
        title = set(re.findall(r'[a-z]{4,}', ' '.join(e['text'] for e in texts
                                                     if e.get('run_size_px', 0) >= .95*top).lower()))
        if len(title) < 5: return False
        return any(len(title & set(re.findall(r'[a-z]{4,}', ' '.join(e['text'] for e in q['elements']
                                                                     if e['kind'] == 'text').lower()))) >= .8*len(title)
                   for q in following)
    if service and controls and metadata and (heading(next_text) or repeated_title()): return True
    # Thesis repositories insert a copyright leaf before the submitted title
    # page. Require both an explicit deposit notice and the matching thesis
    # title there; a repository affiliation or a URL alone proves nothing.
    deposit = (re.search(r'free and open access', text, re.I) and
               re.search(r'accepted for inclusion|authorized administrator', text, re.I) and
               re.search(r'https?://\S+', text) and metadata)
    if not deposit: return False
    words = lambda s: set(re.findall(r'[a-z]{4,}', s.lower()))
    for candidate in following:
        candidate_rows = [e['text'] for e in candidate['elements'] if e['kind']=='text']
        content = ' '.join(candidate_rows)
        if re.search(r'\b(?:thesis|dissertation)\s+submitted\b', content, re.I) and re.search(r'\bdegree of\b', content, re.I):
            return any(len(words(row) & words(text)) >= 5 for row in candidate_rows
                       if row.upper() == row and len(words(row)) >= 5)
        if not copyright_leaf(candidate): break
    return False


def copyright_leaf(page):
    """A sparse rights-only leaf may intervene between a wrapper and thesis title."""
    text = ' '.join(e['text'] for e in page['elements'] if e['kind']=='text')
    return bool(len(text.split()) <= 35 and re.search(r'©|\bcopyright\b', text, re.I)
                and re.search(r'all rights reserved', text, re.I))


def thesis_title_runs(page):
    """Uppercase title rows before an explicit thesis submission statement.

    This is evidence for a same-size title, not a largest-font guess. Callers
    must also prove the preceding repository wrapper. The title rows are
    centered together and remain above the submission statement.
    """
    runs = sorted((e for e in page['elements'] if e['kind']=='text' and not e.get('angle')),
                  key=lambda e:(e['box_px'][1],e['box_px'][0]))
    statement = next((e for e in runs if re.search(r'\b(?:thesis|dissertation) submitted\b',e['text'],re.I)), None)
    if not statement: return []
    title = [e for e in runs if e['box_px'][3] < statement['box_px'][1]]
    if not title or not all(e['text'].upper()==e['text'] and re.search(r'[A-Z]',e['text']) for e in title): return []
    centre = (title[0]['box_px'][0]+title[0]['box_px'][2])/2
    if any(abs((e['box_px'][0]+e['box_px'][2])/2-centre)>e['run_size_px'] for e in title): return []
    return title


SC_PROOF_LANES = {}


def proof_margin_numbers(chars, box, established=None):
    """Isolate dense margin sequences before words on a watermarked proof.

    The watermark is the independent proof witness; ordinary manuscripts keep
    rule 6's existing run-level detector. Both margin edges may carry separate
    increasing sequences. Gaps from captions and occasional overprinted labels
    are allowed, but at least twelve labels, 80% unit steps and a third-page
    span establish a lane. Later watermarked pages with increasing values may
    have as few as three labels there. Table proof labels tN.row need six labels
    with unit steps. Only glyphs in the proven narrow numeric lane leave text.
    """
    established = established if established is not None else []
    body = statistics.median(c['size'] for c in chars)
    w, h = box[2]-box[0], box[3]-box[1]
    removed = []
    for side in ('left', 'right'):
        margin = [c for c in chars if c['angle']==0 and c['size'] <= 1.2*body and
                  (c['x1'] < box[0]+.075*w if side=='left' else c['x0'] > box[2]-.075*w)]
        rows = []
        for c in sorted(margin, key=lambda c:c['origin'][1]):
            if not rows or abs(c['origin'][1]-rows[-1][0]['origin'][1]) > .2*body: rows.append([])
            rows[-1].append(c)
        candidates = []; table_labels = []
        for row in rows:
            row.sort(key=lambda c:c['x0'])
            parts = [[]]
            for c in row:
                if parts[-1] and c['x0']-parts[-1][-1]['x1'] > .5*body: parts.append([])
                parts[-1].append(c)
            for part in parts:
                text = ''.join(c['text'] for c in part)
                if text.isdigit() and len(text)<=6 and max(c['x1'] for c in part)-part[0]['x0']<3*body:
                    candidates.append(part)
                match = re.fullmatch(r't(\d+)[.:](\d+)', text, re.I)
                if match: table_labels.append((match[1],int(match[2]),part))
        for prefix in sorted({p for p,_,_ in table_labels}):
            labels = [(n,cs) for p,n,cs in table_labels if p==prefix]
            if (len(labels)>=6 and all(b[0]==a[0]+1 for a,b in zip(labels,labels[1:]))
                    and max(cs[0]['x0'] for _,cs in labels)-min(cs[0]['x0'] for _,cs in labels)<body):
                removed.extend((cs,'consecutive proof table line numbers in the margin') for _,cs in labels)
        lanes = []
        for row in candidates:
            edge = min(c['x0'] for c in row) if side=='left' else max(c['x1'] for c in row)
            lane = next((g for x,g in lanes if abs(x-edge)<.35*body), None)
            if lane is None: lanes.append((edge,[row]))
            else: lane.append(row)
        for edge, rows in lanes:
            rows.sort(key=lambda row:row[0]['origin'][1])
            values = [int(''.join(c['text'] for c in row)) for row in rows]
            steps = [b-a for a,b in zip(values,values[1:])]
            size = statistics.median(c['size'] for row in rows for c in row)
            known = any(s==side and abs(x-edge/w)<.025 and abs(em-size)<.1*size
                        and values[-1] > last for s,x,em,last in established)
            dense = len(rows)>=12 and rows[-1][0]['y0']-rows[0][0]['y0']>=.33*h
            if (not dense and not (known and len(rows)>=3)) or sum(s==1 for s in steps)<.8*len(steps): continue
            if dense: established.append((side,edge/w,size,values[0]))
            # Include overwritten labels and a query occupying a numeric row,
            # but never borrow a nearby letter from the article's text frame.
            left = min(c['x0'] for row in rows for c in row)-.3*size
            right = max(c['x1'] for row in rows for c in row)+size
            lane_chars = [c for c in margin if left<=c['x0'] and c['x1']<=right
                          and abs(c['size']-size)<.1*size and (c['text'].isdigit() or c['text']=='Q')]
            for c in lane_chars:
                reason = ('proof editorial query in the numbered margin' if c['text']=='Q' else
                          'consecutive proof line numbers in the margin')
                removed.append(([c],reason))
    return removed


def plumber_shift_px(pdf_path, page_no, page):
    """Rule 1: the vertical offset (px) that puts pdfplumber's drawn objects in the reading layer's frame.

    The reading layer keeps PDF user x and flips y against the CropBox height (within the
    MediaBox); pdfplumber flips y against the MediaBox height. Where a CropBox is shorter than
    its MediaBox (a printer's proof with crop marks and a slug line), every rule, fill and image
    otherwise sits lower than the text it was drawn with by the difference (measured: AH06,
    MediaBox 849 pt high, CropBox 784.2 pt: each figure image covered its own caption and the
    caption's box the text under it; V09 and AB05 alike). Unrotated pages only: the corpus has
    no rotated page with a short CropBox, and the rotated frames are left as they were."""
    if page.rotation % 360: return 0
    _, h, _ = sc_doc(pdf_path).page_size(page_no)
    return px(h - float(page.height))


SC_PAGE_BOXES = {}
def repeated_on_pages(pdf_path, page_no, box, page_box):
    """Rule 1: a page template's background is drawn on most pages of the paper: the same fill or image
    box, within background_repeat_px on every edge, on at least half the paper's pages and on one page
    besides this one (measured: AH06, the tinted text area on all 8 pages). A one-page box that happens
    to fill the text area is a panel of its own and stays one (pmed.1000278 p11, the Editors' Summary:
    its atomic panel ends the reference list above it). Large drawn boxes are read once per paper."""
    import pdfplumber
    key = os.path.abspath(pdf_path)
    if key not in SC_PAGE_BOXES:
        found = {}
        with pdfplumber.open(pdf_path) as pdf:
            for n, page in enumerate(pdf.pages, 1):
                dy = plumber_shift_px(pdf_path, n, page); boxes = []
                for o in list(page.rects) + list(page.curves) + list(page.images):
                    b = [px(o["x0"]), px(o["top"]) + dy, px(o["x1"]), px(o["bottom"]) + dy]
                    if (b[2] - b[0]) >= PARAMS["background_area_share"] * (page_box[2] - page_box[0]) and \
                       (b[3] - b[1]) >= PARAMS["background_area_share"] * (page_box[3] - page_box[1]): boxes.append(b)
                found[n] = boxes
        SC_PAGE_BOXES[key] = found
    pages = SC_PAGE_BOXES[key]
    hits = [n for n, boxes in pages.items() if any(all(abs(b[k] - box[k]) <= PARAMS["background_repeat_px"] for k in range(4)) for b in boxes)]
    return len(hits) >= max(2, len(pages) / 2) and any(n != page_no for n in hits)


def curve_box_share(o):
    """Rule 1: the share of a curve's path points lying on its bounding box (within 5% of its shorter side,
    at least 2 pt). A rounded or plain box drawn as a path keeps every point on its edges (an abstract
    panel, a boxed figure: 1.0); a decorative swoosh keeps under half of them there (measured: AN08 p1,
    0.45). Only a box-like curve can frame text; see PARAMS curve_box_share."""
    pts = o.get("pts") or []
    if not pts: return 1.0
    tol = max(2.0, 0.05 * min(o["x1"] - o["x0"], o["bottom"] - o["top"]))
    near = sum(1 for x, y in pts if abs(x - o["x0"]) <= tol or abs(x - o["x1"]) <= tol
               or abs(y - o["top"]) <= tol or abs(y - o["bottom"]) <= tol)
    return round(near / len(pts), 3)


def boxlike(e, em):
    """A drawn object that can frame text: a rect, an image, a shading, a curve whose path points lie on its
    bounding box (curve_box_share), or a small curve (shorter side under curve_min_em letter heights: a
    flow-diagram shape or chart element holding its own lettering, measured AN01 p5, 3-7 em). A free-form
    curve of page scale is decoration and never frames text (rule 1, part 2; measured AN08 p1, 40 em)."""
    if e.get("source") != "curve" or e.get("curve_box_share", 1.0) >= PARAMS["curve_box_share"]: return True
    b = e["box_px"]
    return min(b[2] - b[0], b[3] - b[1]) < PARAMS["curve_min_em"] * em


def text_area_background(o, elements, page_box):
    """Rule 1: a fill or image under the page's text area is a background, not a container or a graphic.

    It spans at least background_area_share of the page in both directions, holds (by run centre)
    at least background_text_share of the page's upright text characters, and at least half of
    what it holds is set in prose runs (background_prose_chars characters or more), not figure
    lettering or table cells. A caption's own shaded box is too small to qualify (measured: N12
    p6, a caption box holding 83% of its page's text). Page-sized objects (background_share of
    the page in both directions: scans under an OCR layer) keep their own rules. The object
    becomes kind background: rules 2-4 never let it contain text or become a figure, so the text
    on it is read normally and no float owns it (measured: AH06, J Periodontol 2000, every page a
    tinted text area under its header band: the figure on it owned the whole page's text, and
    page 1's two columns were read as one; pmed.1000278 p11, a tinted two-column summary that
    fills the page, stays a panel: repeated_on_pages)."""
    if o["kind"] not in ("fill", "image"): return None
    b, P = o["box_px"], page_box
    w, h, W, H = b[2] - b[0], b[3] - b[1], P[2] - P[0], P[3] - P[1]
    if w >= PARAMS["background_share"] * W and h >= PARAMS["background_share"] * H: return None
    if w < PARAMS["background_area_share"] * W or h < PARAMS["background_area_share"] * H: return None
    texts = [e for e in elements if e["kind"] == "text" and e.get("angle", 0) == 0 and e["text"].strip()]
    if not texts: return None
    def n(e): return len(e["text"].replace(" ", ""))
    def holds(e): return b[0] - 1 <= (e["box_px"][0] + e["box_px"][2]) / 2 <= b[2] + 1 and b[1] - 1 <= (e["box_px"][1] + e["box_px"][3]) / 2 <= b[3] + 1
    held = [e for e in texts if holds(e)]
    chars = sum(n(e) for e in held)
    if chars < PARAMS["background_text_share"] * sum(n(e) for e in texts): return None
    if 2 * sum(n(e) for e in held if n(e) >= PARAMS["background_prose_chars"]) < chars: return None
    return "under the page's text area: spans most of the page and holds most of its prose"


def blank_background_image(image, box, page_box):
    """A large edge tile with constant white samples is page backing, not a panel.

    Decode only bounded, 8-bit gray/RGB streams with the default sample mapping;
    a soft mask must be constant opaque too. Compressed JPEG/JPX bytes, colored
    samples and variable masks cannot establish a blank background. Retain the
    object as background evidence without letting it contain text or figures.
    """
    if (min(box[2]-box[0], box[3]-box[1]) < .4*min(page_box[2]-page_box[0], page_box[3]-page_box[1])
            or not (box[0] <= page_box[0]+1 or box[1] <= page_box[1]+1
                    or box[2] >= page_box[2]-1 or box[3] >= page_box[3]-1)):
        return False
    stream = image.get('stream')
    if not isinstance(stream, PDFStream): return False
    def white(s, components):
        width, height = int_value(s.get('Width')), int_value(s.get('Height'))
        length = width*height*components
        if (int_value(s.get('BitsPerComponent')) != 8 or s.get('Decode') is not None
                or s.get('ImageMask') or not 0 < length <= 16*1024*1024): return False
        data = s.get_data()
        return len(data) == length and data.count(255) == length
    try:
        color = resolve1(stream.get('ColorSpace'))
        if isinstance(color, list) and color and literal_name(resolve1(color[0])) == 'ICCBased':
            profile = resolve1(color[1])
            components = int_value(profile.get('N'))
        else:
            components = {'DeviceGray': 1, 'DeviceRGB': 3}.get(literal_name(color), 0)
        if components not in (1, 3) or stream.get('Mask') is not None or not white(stream, components): return False
        mask = resolve1(stream.get('SMask'))
        return mask is None or (isinstance(mask, PDFStream) and white(mask, 1))
    except (ValueError, TypeError, KeyError, OSError):
        return False


def ink_colour(o, stroke=False):
    """The colour an object paints with (its stroking colour when asked, else its fill colour), as a tuple of
    components rounded to 3 places (the tuple length keeps grey, RGB and CMYK apart); None for a pattern or an
    unset colour (the default black is layout ink)."""
    v = o.get("stroking_color" if stroke else "non_stroking_color")
    if v is None: return None
    if isinstance(v, (int, float)): v = (v,)
    try: return tuple(round(float(x), 3) for x in v)
    except (TypeError, ValueError): return None


def layout_palette(page):
    """R2 (lane stream): the page's layout ink, the colours its printed characters and its straight-edged
    drawing (rects and lines, filled or stroked) paint with."""
    pal = {ink_colour(c) for c in page.chars}
    for o in list(page.rects) + list(page.lines):
        if o.get("fill") or o.get("non_stroking_color") is not None: pal.add(ink_colour(o))
        if o.get("stroke") or o.get("stroking_color") is not None: pal.add(ink_colour(o, stroke=True))
    pal.discard(None)
    return pal


def overlay_ink(o, palette):
    """R2 (lane stream): a free-form drawn path (pdfplumber kind curve) painted in a colour that no printed
    character and no rect or line of the page uses is not ink of the page's layout: a pen highlight or
    handwriting laid over a page (measured: AP22 pp1-6 and 20-22, 786 such paths, red, yellow, orange and
    green over a CMYK layout; AP22 p5's table grew over the page through them). Such a path never acts as a
    table rule, cell fill or witness (rule 3) and never chains a block into a float (rule 4). Off-palette
    curves also draw figures (AN08 p2, 453); figures keep them: only those two roles are withdrawn."""
    c = ink_colour(o, stroke=not o.get("fill"))
    return c is not None and c not in palette


def _box_elements(pdf_path, part, label, drop_boxes=(), keep_zones=()):
    def dropped(box, exact=False):   # a drawn object the first pass found to be art, or a piece of one (an outlined letter)
        if exact: return any(all(abs(box[k] - d[k]) <= 1 for k in range(4)) for d in drop_boxes)
        return any(box[0] >= d[0] - 1 and box[1] >= d[1] - 1 and box[2] <= d[2] + 1 and box[3] <= d[3] + 1 for d in drop_boxes)
    import pdfplumber
    page_no = part["page"]
    bx = part["box_px"]
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_no - 1]
        dy = plumber_shift_px(pdf_path, page_no, page)
        chars, objs = [], []; all_rules = []
        palette = layout_palette(page)
        for c in pdfium_characters(pdf_path, page_no):
            cx, cy = (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2
            if not (bx[0] <= cx <= bx[2] and bx[1] <= cy <= bx[3]): continue
            chars.append(c)
        for kind, lst in (("line", page.lines), ("rect", page.rects), ("curve", page.curves)):
            for o in lst:
                x0, y0, x1, y1 = px(o["x0"]), px(o["top"]) + dy, px(o["x1"]), px(o["bottom"]) + dy
                lw = px(o.get("linewidth") or 0)
                if kind == "line" and lw:   # a stroked line's ink is centreline +/- half its width
                    if (x1 - x0) >= (y1 - y0): y0, y1 = y0 - lw / 2, y1 + lw / 2
                    else: x0, x1 = x0 - lw / 2, x1 + lw / 2
                if x1 < bx[0] or x0 > bx[2] or y1 < bx[1] or y0 > bx[3]: continue
                thin = min(x1 - x0, y1 - y0) <= px(PARAMS["rule_max_pt"])
                if thin: all_rules.append({"kind": "rule", "box_px": [x0, y0, x1, y1]})
                if dropped([x0, y0, x1, y1]): continue
                objs.append({"kind": "rule" if thin else "fill", "source": kind,
                             "box_px": [x0, y0, x1, y1], "linewidth_pt": o.get("linewidth"),
                             **({"curve_box_share": curve_box_share(o)} if kind == "curve" else {}),
                             **({"overlay": True} if kind == "curve" and overlay_ink(o, palette) else {})})
        for o in page.images:
            x0, y0, x1, y1 = px(o["x0"]), px(o["top"]) + dy, px(o["x1"]), px(o["bottom"]) + dy
            if x1 < bx[0] or x0 > bx[2] or y1 < bx[1] or y0 > bx[3] or dropped([x0, y0, x1, y1], exact=True): continue
            image_box = [x0, y0, x1, y1]
            objs.append({"kind": "background" if blank_background_image(o, image_box, bx) else "image",
                         "source": "image", "box_px": image_box})
        for x0, y0, x1, y1 in pdfium_shadings(pdf_path, page_no):   # gradients: drawn objects pdfplumber does not report
            if x1 < bx[0] or x0 > bx[2] or y1 < bx[1] or y0 > bx[3] or dropped([x0, y0, x1, y1]): continue
            objs.append({"kind": "fill", "source": "shading", "box_px": [x0, y0, x1, y1]})
    read_counts = sc_read_page(pdf_path, page_no)[2]
    control_unmapped = read_counts.get("unmapped", 0)
    if not chars or all(c["hidden"] for c in chars):   # a blank page, or a page of pictures only: its drawn objects are its elements
        why = "no characters inside region" if not chars else "no printed characters inside region"
        regions = poppler_regions(pdf_path, page_no, bx, [])
        return {"label": label, "page": page_no, "region_box_px": bx, "reading_angle": 0, "params": PARAMS, "regions": regions,
                **({'scan_evidence': read_counts['scan_evidence']} if read_counts.get('scan_evidence',{}).get('ocr_layer') else {}),
                "counts": {"characters_in_region": len(chars), "characters_in_elements": 0, "characters_unpainted": len(chars), "characters_unmapped": control_unmapped, **read_counts["glyph_recovery"], "characters_covered": 0, "lines": 0, "text_runs": 0,
                           "rules": sum(1 for o in objs if o["kind"] == "rule"), "fills": sum(1 for o in objs if o["kind"] == "fill"), "outlined_text_runs": 0,
                           "images": sum(1 for o in objs if o["kind"] == "image"), "full_width_rules": 0},
                "blocks": [], "tables_rule3": [], "floats": [], "unpaired": [], "tables": [], "art": [], "caption_boxes_px": part.get("caption_boxes_px", []),
                "flags": [why + ": rules 2-5 not applied; the page's drawn objects are its elements"] + (["unmapped glyphs retained as U+FFFD"] if control_unmapped else []),
                "elements": [{"id": f'{o["kind"]}:{oi+1}', "kind": o["kind"], "box_px": o["box_px"], "source": o["source"], "region": region_at(o["box_px"], regions)} for oi, o in enumerate(objs)]}
    hidden_boxes = [c for c in chars if c["hidden"]]
    chars = [c for c in chars if not c["hidden"]]
    watermarks = diagonal_watermarks(chars, bx)
    early_furniture = [(cs, 'large diagonal watermark crossing the page body') for cs in watermarks]
    if watermarks: early_furniture += proof_margin_numbers(chars, bx, SC_PROOF_LANES.setdefault(os.path.abspath(pdf_path), []))
    watermark_ids = {id(c) for group, _ in early_furniture for c in group}
    groups = collections.defaultdict(list)   # one reading orientation per character group
    for i, c in enumerate(chars):
        c["id"] = i
        if id(c) in watermark_ids: continue
        groups[min((0, 90, 270, 360), key=lambda a: abs(a - c["angle"])) % 360].append(c)
    angle = max(groups, key=lambda a: len(groups[a]))   # the float's main orientation, for the record
    lines, runs, overprint_lines, line_angle = [], [], set(), []
    for ang, gchars in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        to_read, baseline_v = frame(ang)
        gl, gr, go = lines_and_runs(gchars, ang, objs, to_read, baseline_v, keep_zones, bars=all_rules)
        off = len(lines); line_angle.extend([ang] * len(gl))
        lines.extend(gl); runs.extend((li + off, cs) for li, cs in gr); overprint_lines.update(li + off for li in go)
    def hull(cs):
        return [min(c["x0"] for c in cs), min(c["y0"] for c in cs), max(c["x1"] for c in cs), max(c["y1"] for c in cs)]
    def hull_boxes(os_):
        return [min(o["box_px"][0] for o in os_), min(o["box_px"][1] for o in os_), max(o["box_px"][2] for o in os_), max(o["box_px"][3] for o in os_)]
    # word spaces: where the PDF sets its own space glyphs (the reading layer marks the character before one,
    # space_after), they are the word breaks, and for a font whose space glyphs mark its word gaps a gap with none
    # is a break only beyond wordspace_max_em; elsewhere a gap wider than text_space_em letter heights is one
    # a font's space glyphs are trusted where they mark its word-sized gaps (wider than wordspace_min_em): at
    # least four in five of them, over twenty or more such gaps on the page
    wordlike = collections.Counter(); marked = collections.Counter()
    for _, cs in runs:
        for prev, c in zip(cs, cs[1:]):
            if c["u0"] - prev["u1"] > PARAMS["wordspace_min_em"] * prev["size"] or prev.get("space_after"):
                wordlike[prev.get("font")] += 1; marked[prev.get("font")] += bool(prev.get("space_after"))
    spaced_fonts = {f for f, n in wordlike.items() if n >= 20 and marked[f] >= 0.8 * n}
    elements = []; text_offsets = {}
    for ri, (li, cs) in enumerate(runs):
        txt = cs[0]["text"]
        marker_space = False
        starts = [0]   # exact text offsets for the optional ink index; no early line/run split
        # the run's tracking: the median of its advance gaps (letters far outnumber word breaks), never below 0
        ag = sorted(c["orig_u"] - prev["adv_u1"] for prev, c in zip(cs, cs[1:]) if prev.get("adv_u1") is not None)
        track = max(0.0, ag[len(ag) // 2]) if ag else 0.0
        for prev, c in zip(cs, cs[1:]):
            ink_gap = c["u0"] - prev["u1"]
            starts.append(len(txt))
            if c.get("marker_glue") and ink_gap <= PARAMS["wordspace_max_em"] * lines[li]["size"]:
                # PDF object order can leave the following word's space on the
                # body letter before its separately painted marker. Carry that
                # space across the marker, without putting one before punctuation.
                marker_space = marker_space or prev.get("space_after", False)
                txt += c["text"]; continue
            # O20 (lane r5-line): a mark drawn over a letter of another font (now kept in its place on the line) belongs
            # to that letter: no word space before it, and the space after it is judged from that letter's edge
            # (measured: AS14 p11 a caron read as a digit over c, "Krc9 mova" with a space; AQ23 p1 a circumflex,
            # "Hoˆ te"). A mark: a character flagged as overprinting whose box overlaps an adjacent letter of another
            # font by more than half its own width; the circumflex and caron (modifier letters, not Sk) as well.
            def host(x, i):
                # a letter or digit as a mark only when its box is much shorter than the letter's (an accent's ink)
                short = not x["text"].isalnum() or x["text"] in ("\u02c6", "\u02c7")
                for j in (i - 1, i + 1):
                    if 0 <= j < len(cs) and cs[j]["text"].isalpha() and cs[j].get("font") != x.get("font"):
                        y = cs[j]
                        if not short and (x["v1"] - x["v0"]) >= 0.6 * (y["v1"] - y["v0"]): continue
                        if min(x["u1"], y["u1"]) - max(x["u0"], y["u0"]) > 0.5 * (x["u1"] - x["u0"]): return y
                return None
            k = len(starts) - 1   # the index of c in cs (starts gains one entry per character)
            # (ASCII punctuation is never a mark: a bracket or comma set under an italic letter keeps the usual spacing)
            def markish(x): return (x.get("overprint") or x["text"] in ("\u02c6", "\u02c7")) and not (len(x["text"]) == 1 and x["text"] in string.punctuation)
            pmark = host(prev, k - 1) if markish(prev) else None
            cmark = host(c, k) if markish(c) else None
            if cmark is not None and cmark is prev:
                txt += c["text"]; continue
            before_host = cmark is not None and k + 1 < len(cs) and cmark is cs[k + 1]
            if before_host:
                # a mark set just left of the letter it overprints: the word space before it is the one before that letter
                c = dict(c, orig_u=cmark["orig_u"], u0=cmark["u0"])
            elif (unicodedata.category(prev["text"][:1] or " ") == "Sk" or unicodedata.category(c["text"][:1] or " ") == "Sk") and not (
                    c.get("r5_line") and unicodedata.category(c["text"][:1] or " ") == "Sk" and prev.get("space_after")) and not (
                    prev.get("r5_line") and unicodedata.category(prev["text"][:1] or " ") == "Sk" and min(prev["u1"], c["u1"]) <= max(prev["u0"], c["u0"])):   # a free-standing accent belongs to its letter
                # (lane r5-line: an accent now kept on its line after a word that ends in a PDF space glyph keeps that
                # space; one that stands over no letter after it, its letter not drawn, is not joined to the next word)
                txt += c["text"]; continue
            if pmark is not None and pmark is not c:
                gap = c["u0"] - max(pmark["u1"], prev["u1"])
                txt += (" " if gap > PARAMS["text_space_em"] * c["size"] else "") + c["text"]; continue
            if prev.get("font") in spaced_fonts:
                sp = prev.get("space_after") or ink_gap > PARAMS["wordspace_max_em"] * prev["size"]
                # a space glyph the reading layer lost (set in a text object of its own): the advance gap, above
                # the run's tracking, as wide as a word space (measured: N08 "6 months", "Table 2", "al., 2017" at 0.30-0.35 em; "Lindhe, 2005" in a tight line at 0.19 em)
                if not sp and prev.get("adv_u1") is not None: sp = c["orig_u"] - prev["adv_u1"] - track > PARAMS["text_space_em"] * prev["size"]
            else:
                if prev.get("adv_u1") is not None: sp = prev.get("space_after") or c["orig_u"] - prev["adv_u1"] - track > PARAMS["advance_space_em"] * prev["size"]
                else: sp = prev.get("space_after") or ink_gap > PARAMS["text_space_em"] * prev["size"]
            sp = sp or (marker_space and c["text"][:1].isalnum())
            marker_space = False
            txt += (" " if sp else "") + c["text"]
        spaced = [cs[i]["id"] for i in range(1, len(cs)) if txt[starts[i]:starts[i] + 1] == " "]
        elements.append({"_spaced": spaced, "id": f"run:{ri+1}", "kind": "text", "line": li + 1, "angle": line_angle[li], "box_px": hull(cs),
                         "text": txt, "char_ids": [c["id"] for c in cs], "size_px": lines[li]["size"], "run_size_px": statistics.median(c["size"] for c in cs),
                         "flags": (["overprinted text: two fonts share one place; last painted layer retained"] if any(c.get("overprint") for c in cs) else [])})
        if any(c.get("line_end_hyphen") for c in cs): elements[-1]["line_end_hyphen"] = True
        if any(c.get("op_line") for c in cs): elements[-1]["overprint_layers"] = op_layers([c["id"] for c in cs], chars)
        # lane r3-headband: fake small capitals (a capital letter set larger than the capitals after it, the run's
        # letters all capitals, a section number before it allowed) record the first letter's size; rule 6
        # measures a heading line at that size
        letters = [c for c in cs if c["text"].isalpha()]
        if (len(letters) >= 2 and all(c["text"].isupper() for c in letters)
                and letters[0]["size"] > (1 + PARAMS["body_size_tolerance"]) * elements[-1]["run_size_px"]):
            elements[-1]["lead_size_px"] = letters[0]["size"]
        if label_in_own_font(cs):
            elements[-1]["label_font"] = True   # the label in a font of its own: a caption label (rule 4)
        # A drop cap can make rule 1's line-sized gap test bridge a real gutter. Keep a
        # compact index of the run's ink, without changing any input to rules 2-5. Only
        # rule 6 may use it, after proving a gutter through the entire main-text block.
        em = elements[-1]["run_size_px"]
        edges = [0]; reach = cs[0]["u1"]
        for i in range(1, len(cs)):
            if cs[i]["u0"] - reach > PARAMS["run_gap_em"] * em: edges.append(i)
            reach = max(reach, cs[i]["u1"])
        edges.append(len(cs))
        if len(edges) > 2 and line_angle[li] == 0:
            starts.append(len(txt))
            elements[-1]["ink_parts"] = [{"box_px": hull(cs[a:z]), "text": txt[starts[a]:starts[z]].strip(),
                "char_ids": [c["id"] for c in cs[a:z]], "run_size_px": statistics.median(c["size"] for c in cs[a:z])}
                for a, z in zip(edges, edges[1:])]
        text_offsets[elements[-1]["id"]] = starts[:len(cs)] + [len(txt)]
    # full-width rules decide caption / body / note bands (in the main orientation's reading frame)
    to_read, baseline_v = frame(angle)
    main = groups[angle]
    body_u0 = min(c["u0"] for c in main); body_u1 = max(c["u1"] for c in main)
    hrules = []
    for o in objs:
        if o["kind"] != "rule": continue
        u0, v0, u1, v1 = to_read(*o["box_px"])
        if (u1 - u0) >= PARAMS["full_width"] * (body_u1 - body_u0): hrules.append((v0 + v1) / 2)
    flags = []
    cboxes = part.get("caption_boxes_px") or []
    if not cboxes: flags.append("mapper gave no caption box: caption band not assigned")
    if not hrules: flags.append("no full-width rule: note band not assigned")
    def in_caption(b):
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return any(c[0] <= cx <= c[2] and c[1] <= cy <= c[3] for c in cboxes)
    bot = max(hrules) if hrules else None
    for e in elements:
        v = statistics.median(chars[i]["vb"] for i in e["char_ids"])
        if chars[e["char_ids"][0]]["angle"] != angle: e["band"] = "body"   # other orientations: no band
        elif cboxes and in_caption(e["box_px"]): e["band"] = "caption"
        elif bot is not None and v > bot: e["band"] = "note"
        else: e["band"] = "body"
    # text drawn as outlines (figures from drawing programs): fills no taller than a large letter,
    # grouped along a common bottom edge with the same gap rule as letters
    letter = statistics.median(c["size"] for c in chars) if chars else 0
    glyphish = [o for o in objs if o["kind"] == "fill" and (o["box_px"][3] - o["box_px"][1]) <= PARAMS["outline_max_em"] * letter and (o["box_px"][2] - o["box_px"][0]) <= PARAMS["outline_max_em"] * letter]
    others = [o for o in objs if o not in glyphish]
    glyphish.sort(key=lambda o: (round(o["box_px"][3]), o["box_px"][0]))
    glines = []
    for o in glyphish:
        h = o["box_px"][3] - o["box_px"][1]
        for gl in glines[-3:]:
            if abs(o["box_px"][3] - gl["vb"]) <= PARAMS["line_tolerance_em"] * max(gl["h"], h): gl["fills"].append(o); gl["h"] = max(gl["h"], h); break
        else: glines.append({"vb": o["box_px"][3], "h": h, "fills": [o]})
    oi = 0
    for gl in glines:
        fs = sorted(gl["fills"], key=lambda o: o["box_px"][0]); cur = [fs[0]]
        for prev, o in zip(fs, fs[1:]):
            if o["box_px"][0] - prev["box_px"][2] > PARAMS["run_gap_em"] * gl["h"]: 
                oi += 1; elements.append({"id": f"outline:{oi}", "kind": "outline", "box_px": hull_boxes(cur), "count": len(cur), "basis": "glyph-sized fills on one bottom edge, gaps under one glyph height", **({"overlay": True} if all(f.get("overlay") for f in cur) else {})}); cur = [o]
            else: cur.append(o)
        oi += 1; elements.append({"id": f"outline:{oi}", "kind": "outline", "box_px": hull_boxes(cur), "count": len(cur), "basis": "glyph-sized fills on one bottom edge, gaps under one glyph height", **({"overlay": True} if all(f.get("overlay") for f in cur) else {})})
    # dots of i and j, accents: a tiny outlined run just above a run that spans it folds into that run
    outl = [e for e in elements if e["kind"] == "outline"]
    for e in list(outl):
        b_ = e["box_px"]; h = b_[3] - b_[1]
        for host in outl:
            if host is e: continue
            hb = host["box_px"]; hh = hb[3] - hb[1]
            if hb[0] - 2 <= b_[0] and b_[2] <= hb[2] + 2 and 0 <= hb[1] - b_[3] <= hh and h < 0.5 * hh:
                host["box_px"] = [min(hb[0], b_[0]), min(hb[1], b_[1]), max(hb[2], b_[2]), max(hb[3], b_[3])]; host["count"] += e["count"]
                elements.remove(e); outl.remove(e); break
    for oi, o in enumerate(others):
        elements.append({"id": f'{o["kind"]}:{oi+1}', "kind": o["kind"], "box_px": o["box_px"], "source": o["source"],
                         **({"curve_box_share": o["curve_box_share"]} if "curve_box_share" in o else {}),
                         **({"overlay": True} if o.get("overlay") else {})})
    # a raster page under an OCR layer (or one near that evidence) keeps the scan rules: its page image
    # repeats on every page too, but it is the page itself (measured: AE03, a 1965 scan)
    scanned = bool(read_counts.get("scan_evidence", {}).get("candidate"))
    for e in elements:
        why = None if scanned else text_area_background(e, elements, bx)
        if why and repeated_on_pages(pdf_path, page_no, e["box_px"], bx):
            e.update(kind="background", basis=why + "; the same box is drawn on most of the paper's pages")
    if hidden_boxes:   # unpainted characters: accounted for as one element per line, never boxed as text
        hb = sorted(hidden_boxes, key=lambda c: (round(c["y1"]), c["x0"]))
        groups = []
        for c in hb:
            if groups and abs(c["y1"] - groups[-1][-1]["y1"]) <= 2: groups[-1].append(c)
            else: groups.append([c])
        for gi, g in enumerate(groups):
            elements.append({"id": f"clipped:{gi+1}", "kind": "clipped", "box_px": hull(g), "text": "".join(c["text"] for c in g),
                             "count": len(g), "basis": "outside the text object's clip path, inactive, transparent or invisible render mode (PDFium)"})
    regions = poppler_regions(pdf_path, page_no, bx, elements, chars)
    separated = region_separations(regions, elements)
    split_elements = []
    for e in elements:
        e["region"] = region_at(e["box_px"], regions)
        split_elements.append(e)
        if e["kind"] != "text" or e["angle"] != 0:
            continue
        b = e["box_px"]
        touched = [r for r in regions if not r.get("deferred") and min(b[2], r["box_px"][2]) > max(b[0], r["box_px"][0])
                   and min(b[3], r["box_px"][3]) > max(b[1], r["box_px"][1])]
        if not any(frozenset((a["id"], z["id"])) in separated for i, a in enumerate(touched) for z in touched[i+1:]):
            continue
        cs = [chars[i] for i in e["char_ids"]]
        tagged = [region_at([c["x0"], c["y0"], c["x1"], c["y1"]], touched) for c in cs]
        edges = [0]
        for i in range(1, len(cs)):
            # An embedded superscript can be a separate Poppler block. It is not
            # a column boundary through a word; keep the reading layer's attachment.
            gap = cs[i]["u0"] - cs[i-1]["u1"]
            if (frozenset((tagged[i], tagged[i-1])) in separated
                    and gap >= PARAMS["wordspace_min_em"] * max(cs[i]["size"], cs[i-1]["size"])): edges.append(i)
        edges.append(len(cs))
        if len(edges) == 2:
            continue
        offsets = text_offsets[e["id"]]
        parts = [{"id": e["id"] if n == 0 else e["id"] + f":region:{n+1}", "box_px": hull(cs[a:z]),
                  "text": e["text"][offsets[a]:offsets[z]].strip(), "char_ids": [c["id"] for c in cs[a:z]],
                  "run_size_px": statistics.median(c["size"] for c in cs[a:z]), "region": region_at(hull(cs[a:z]), regions)}
                 for n, (a, z) in enumerate(zip(edges, edges[1:]))]
        split_elements.pop()
        for n, part_ in enumerate(parts):
            frag = dict(e, **part_); frag.pop("ink_parts", None)
            if not any(chars[i].get("line_end_hyphen") for i in frag["char_ids"]): frag.pop("line_end_hyphen", None)
            if n: frag.pop("label_font", None)
            if "overprint_layers" in frag: frag["overprint_layers"] = op_layers(frag["char_ids"], chars)
            frag["region_parts"] = [part_]
            frag["region_source"] = e["id"]
            split_elements.append(frag)
    elements = split_elements
    marker_moves = []
    for e in elements:
        moved = []
        for ci in e.get("char_ids", []):
            c = chars[ci]
            if "marker_from_line" not in c:
                if moved and moved[-1]: moved.append([])
                continue
            if (not moved or not moved[-1] or moved[-1][-1]["marker_from_line"] != c["marker_from_line"]
                or moved[-1][-1].get("marker_kind") != c.get("marker_kind")):
                moved.append([c])
            else: moved[-1].append(c)
        for cs in moved:
            if not cs: continue
            source = cs[0]["marker_from_line"]
            marker_moves.append({"run": e["id"], "from_line": source, "to_line": e["line"],
                                 "angle": e["angle"], "text": "".join(c["text"] for c in cs),
                                 "char_ids": [c["id"] for c in cs]})
            if cs[0].get("marker_kind"): marker_moves[-1]["kind"] = cs[0]["marker_kind"]
    # A wide single-line banner is not a two-line panel. Its backing belongs
    # to the text it actually contains, rather than a distant candidate at the
    # backing's centre. Otherwise containment can detach the label (pmed.0020278).
    for e in elements:
        if e["kind"] not in ("fill", "image"): continue
        B = e["box_px"]
        owners = {t["region"] for t in elements if t["kind"] == "text"
                  and B[0] - 1 <= t["box_px"][0] and t["box_px"][2] <= B[2] + 1
                  and B[1] - 1 <= t["box_px"][1] and t["box_px"][3] <= B[3] + 1}
        if len(owners) == 1: e["region"] = owners.pop()
    assigned = sum(len(e["char_ids"]) for e in elements if e["kind"] == "text")
    result = {"label": label, "page": page_no, "region_box_px": bx, "reading_angle": angle,
            **({'scan_evidence': read_counts['scan_evidence']} if read_counts.get('scan_evidence',{}).get('ocr_layer') else {}),
            "params": PARAMS, "regions": regions, "marker_moves": marker_moves, "counts": {"characters_in_region": len(chars) + len(hidden_boxes), "characters_in_elements": assigned, "characters_unpainted": len(hidden_boxes), "characters_unmapped": control_unmapped, **read_counts["glyph_recovery"],
            "characters_covered": sum(bool(c.get("covered")) for c in chars), "lines": len(lines), "text_runs": len(runs), "rules": sum(1 for o in objs if o["kind"] == "rule"),
            "fills": sum(1 for e in elements if e["kind"] == "fill"), "outlined_text_runs": sum(1 for e in elements if e["kind"] == "outline"), "images": sum(1 for o in objs if o["kind"] == "image"), "full_width_rules": len(hrules)},
            "blocks": (blocks := larger_boxes(elements, regions)), "tables_rule3": (tables := (lambda grid: grid + tables_from_caption(elements, blocks, grid, chars, table_decisions))(tables_from_grid(elements, blocks, table_decisions := []))),
            "table_candidates": table_decisions,
            "floats": (floats := assemble_tables(elements, blocks, tables, floats_with_captions(elements, blocks, tables, chars), floats_with_captions.unpaired)), "unpaired": assemble_tables.unpaired, "tables": [t for t in tables if not t.get("demoted")],
            "art": journal_art(elements, blocks, floats, [t for t in tables if not t.get("demoted")], angle),
            "caption_boxes_px": cboxes, "flags": flags + ([f"{len(overprint_lines)} line(s) with overprinted text"] if overprint_lines else []) + (["unmapped glyphs retained as U+FFFD"] if control_unmapped else []), "elements": elements}
    result["_r5_line_boxes"] = [[c["x0"], c["y0"], c["x1"], c["y1"]] for c in chars if c.get("r5_line")]
    result["_r5_line_ids"] = [c["id"] for c in chars if c.get("r5_line")]
    result["_r5_char_info"] = {c["id"]: (c["size"], [c["x0"], c["y0"], c["x1"], c["y1"]]) for c in chars}
    for i, (cs, why) in enumerate(early_furniture):
        e = dict(id=f'proof-furniture:{i+1}', kind='text', line=len(lines)+i+1,
                 angle=cs[0]['angle'], box_px=hull(cs), text=''.join(c['text'] for c in cs),
                 char_ids=[c['id'] for c in cs], size_px=cs[0]['size'], run_size_px=cs[0]['size'],
                 band='body', flags=[why], furniture_reason=why,
                 source_paint={k:cs[0].get(k) for k in ('render_mode','fill_alpha','fill_color')})
        elements.append(e)
        result['blocks'].append(dict(id=e['id'], members=[e['id']], box_px=e['box_px'],
            kinds=['text'], text_lines=1, text=e['text']))
        result['counts']['characters_in_elements'] += len(cs)
        result['counts']['text_runs'] += 1
    return result

def paint_elements(dr, elements, caption_boxes):
    from PIL import ImageFont
    font = ImageFont.load_default()
    col = {"caption": (150, 40, 200), "body": (220, 40, 40), "note": (0, 120, 60), None: (120, 120, 120)}
    for e in elements:
        b = e["box_px"]
        if e["kind"] == "text":
            c = col[e.get("band")] if caption_boxes else (220, 40, 40)   # whole page: bands mean nothing, one colour
            if e.get("flags"): c = (150, 40, 200)
            dr.rectangle([b[0]-2, b[1]-2, b[2]+2, b[3]+2], outline=c + (255,), width=2, fill=c + (28,))
        elif e["kind"] == "rule":
            dr.rectangle([b[0]-1, b[1]-1, b[2]+1, b[3]+1], outline=(30, 110, 230, 255), width=2)
        elif e["kind"] == "fill":
            dr.rectangle(b, outline=(230, 150, 0, 255), width=2)
        elif e["kind"] == "outline":
            dr.rectangle([b[0]-2, b[1]-2, b[2]+2, b[3]+2], outline=(200, 90, 0, 255), width=2, fill=(230, 150, 0, 40))
        elif e["kind"] == "clipped":
            for x in range(int(b[0]), int(b[2]), 8): dr.line([x, b[1], min(x + 4, b[2]), b[1]], fill=(140, 140, 140, 255), width=1); dr.line([x, b[3], min(x + 4, b[2]), b[3]], fill=(140, 140, 140, 255), width=1)
            dr.text((b[0], b[3] + 1), f'unpainted ({e["count"]} chars)', fill=(140, 140, 140, 255), font=font)
        else:
            dr.rectangle(b, outline=(0, 160, 160, 255), width=2)

def sc_background(pdf_path, page_no):
    """The page picture under the boxes: pdftoppm's rendering at the frame's 150 dpi when pdftoppm is
    on the PATH (and BOXER_SC_BACKGROUND is not "white"), else a white page of the page's size."""
    if os.environ.get("BOXER_SC_BACKGROUND", "") != "white" and shutil.which("pdftoppm"):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "page")
            r = subprocess.run(["pdftoppm", "-r", str(PARAMS["dpi"]), "-f", str(page_no), "-l", str(page_no), "-singlefile", pdf_path, base], capture_output=True)
            if r.returncode == 0 and os.path.exists(base + ".ppm"):
                SC_STATS["background_pdftoppm"] += 1
                im = sc_image_open(base + ".ppm"); im.sc_kind = "pdftoppm"; return im
            SC_STATS["background_pdftoppm_failed"] += 1
            print(f"pictures, page {page_no}: pdftoppm failed (rc {r.returncode}); a white page is used under the boxes (the JSON and text outputs do not depend on it)", file=sys.stderr)
    w, h = sc_page_size(pdf_path, page_no)
    SC_STATS["background_white"] += 1
    im = SCImage(math.ceil(px(w)), math.ceil(px(h))); im.sc_kind = "white"; return im


def clean_render(pdf_path, page_no, art_boxes, kept_boxes, kept_text=()):
    """The page with its art removed, as a picture: no renderer here, so the background is painted
    white over every art box that touches no kept text run; an art box over kept text is returned as
    not removed (it stays visible). On a white background nothing was drawn, so nothing is left."""
    im = sc_background(pdf_path, page_no)
    if getattr(im, "sc_kind", "white") == "white": return im, []
    dr = SCDraw(im); left = []
    for a in art_boxes:
        if any(min(a[2], T[2]) - max(a[0], T[0]) > 0 and min(a[3], T[3]) - max(a[1], T[1]) > 0 for T in kept_text):
            left.append(a); continue
        x = [int(v) for v in a]; dr.rectangle([x[0] - 3, x[1] - 3, x[2] + 3, x[3] + 3], fill=(255, 255, 255))
    return im, left


def draw(result, pdf_path, out_png):
    """The original drawing, with the page picture from sc_background and the clean copy from clean_render."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default()
    first = result.get("first_pass_result", result)
    def render(path, page):
        return sc_background(path, page)
    def paint_all(im, res, with_floats=True):
        dr = ImageDraw.Draw(im, "RGBA")
        els = res["elements"] if with_floats else [e for e in res["elements"] if e["kind"] != "clipped"]   # the clean copy: unpainted text is removed, not drawn
        paint_elements(dr, els, res.get("caption_boxes_px"))
        for blk in res.get("blocks", []):
            x = blk["box_px"]; dr.rectangle([x[0]-4, x[1]-4, x[2]+4, x[3]+4], outline=(0, 130, 60, 255), width=3)
        for tb in res.get("tables", []):
            x = tb["box_px"]; dr.rectangle([x[0]-6, x[1]-6, x[2]+6, x[3]+6], outline=(0, 60, 200, 255), width=4)
            dr.text((x[0]-4, x[3]+8), f'{tb["id"]}: {tb["grid_lines"]} grid lines x {tb["tracks"]} tracks', fill=(0, 60, 200, 255), font=font)
        if with_floats:
            for fl in res.get("floats", []):
                x = fl["box_px"]; dr.rectangle([x[0]-8, x[1]-8, x[2]+8, x[3]+8], outline=(160, 0, 200, 255), width=4)
                dr.text((x[0]-6, x[1]-20), f'{fl["id"]}: {fl["caption"][:40]}', fill=(160, 0, 200, 255), font=font)
        return im
    # 1. the original page with the first pass's boxes, art included
    im = paint_all(render(pdf_path, result["page"]), first)
    bx = result["region_box_px"]; dr = ImageDraw.Draw(im, "RGBA"); dr.rectangle(bx, outline=(0, 0, 0, 255), width=3)
    pad = 30; crop = im.crop((max(0, bx[0]-pad), max(0, bx[1]-pad), min(im.width, bx[2]+pad), min(im.height, bx[3]+pad)))
    k = result["counts"]
    leg = Image.new("RGB", (crop.width, 34), (255, 255, 255)); ld = ImageDraw.Draw(leg)
    ld.text((6, 4), (f'{result["label"]}: one box per element. red=text run (purple=flagged overprint), blue=rule, orange=fill, dark orange=outlined text, teal=image. angle {result["reading_angle"]}'), fill=(0,0,0), font=font)
    ld.text((6, 18), f'rule 2: {len(result.get("blocks", []))} larger boxes (green); rule 3: {len(result.get("tables", []))} tables (dark blue); rule 4: {len(result.get("floats", []))} floats (purple); rule 5: {len(result.get("art", []))} art elements removed, rules 1-4 rerun on the clean page: {k["text_runs"]} text runs (was {first["counts"]["text_runs"]}).', fill=(0,0,0), font=font)
    out = Image.new("RGB", (crop.width, crop.height + 34), (255, 255, 255)); out.paste(leg, (0, 0)); out.paste(crop, (0, 34)); out.save(out_png)
    # 2. the floats alone, from the original page
    only = Image.new("RGB", im.size, (255, 255, 255))
    for fl in first.get("floats", []):
        x = [int(v) for v in fl["box_px"]]; x = [x[0]-3, x[1]-3, x[2]+3, x[3]+3]   # the box itself, nothing beside it
        only.paste(im.crop(x), (x[0], x[1]))
    only.save(out_png[:-4] + "-floats-only.png")
    # 3. the clean copy: the art-free page with the second pass's boxes, floats blanked
    art = result.get("art", []); art_ids = {ae["id"] for ae in art}
    kept_drawn = [e["box_px"] for e in first["elements"] if e["kind"] in ("rule", "fill", "image", "outline") and e["id"] not in art_ids]
    drawn_art = [ae["box_px"] for ae in art if ae["kind"] != "clipped"]
    kept_text_boxes = [e["box_px"] for e in first["elements"] if e["kind"] == "text"]
    base_im, left = clean_render(pdf_path, result["page"], drawn_art, kept_drawn, kept_text_boxes) if drawn_art else (render(pdf_path, result["page"]), [])
    result["art_unremovable"] = len(left)
    clean = paint_all(base_im, result, with_floats=False); d2 = ImageDraw.Draw(clean, "RGBA")
    kept_text = [e["box_px"] for e in result["elements"] if e["kind"] == "text"]
    not_blanked = []
    for a_ in left:
        if any(min(a_[2], T[2]) - max(a_[0], T[0]) > 0 and min(a_[3], T[3]) - max(a_[1], T[1]) > 0 for T in kept_text):
            not_blanked.append([round(v) for v in a_]); continue   # art the picture could not remove, lying over kept text: left visible, never blanked
        x = [int(v) for v in a_]; d2.rectangle([x[0]-4, x[1]-4, x[2]+4, x[3]+4], fill=(255, 255, 255, 255))
    result["art_left_visible"] = not_blanked
    for fl in result.get("floats", []):
        x = [int(v) for v in fl["box_px"]]; d2.rectangle([x[0]-3, x[1]-3, x[2]+3, x[3]+3], fill=(255, 255, 255, 255))
    clean.save(out_png[:-4] + "-clean.png"); clean.save(out_png[:-4] + "-no-floats.png")


def reference_heading(text):
    """A bibliography heading or a separately titled list of included/excluded studies."""
    text = re.sub(r"\s+", "", text).lower()
    return bool(re.fullmatch(r"(?:\d+(?:\.\d+)*\.?)?(?:references?(?:andnotes)?|bibliography|"
                             r"literaturecited|workscited|citedliterature|"
                             r"listof(?:included|excluded)(?:full[-‐]?text)?(?:articles|studies)"
                             r"(?:andthereasons?forexclusion)?)[.:]?", text))


def mark_header_row_references(blocks, text_of):
    """A reference word set as a table's column header is not a bibliography heading.

    A references heading stands alone on its line in its column. A one-line
    "Reference(s)" block whose line is shared by at least two other short
    blocks (three lines or fewer, six words or fewer on their first line) of
    its own type size, side by side and not overlapping it, is a cell of a
    header row (measured: AI09 Table 8, "Genetic variant | Association with
    cardiovascular diseases | Reference", which opened a false reference
    list over the rest of the paper's body). Body columns beside a real
    heading are long blocks, so they never witness a header row. The block
    keeps its classes; it records table_header_cell=True, and no reference
    rule (section state, section cuts, reference columns) treats it as a
    heading. Exporters read the same field."""
    for b in blocks:
        text = text_of(b)
        lines = [line for line in text.split("\n") if line.strip()]
        if len(lines) != 1 or not reference_heading(lines[0]): continue
        x0, y0, x1, y1 = b["box_px"]; size = b.get("size") or b.get("size_px") or 0
        cells = []
        for a in blocks:
            if a is b: continue
            A = a["box_px"]; first = (text_of(a).split("\n") or [""])[0]
            if A[2] > x0 and A[0] < x1: continue
            if min(A[3], y1) - max(A[1], y0) < .5 * (y1 - y0): continue
            asize = a.get("size") or a.get("size_px") or 0
            if not size or abs(asize - size) > .08 * size: continue
            if a.get("lines", 1) > 3 or len(first.split()) > 6 or not re.search(r"[A-Za-z]", first): continue
            cells.append(a)
        if len(cells) >= 2: b["table_header_cell"] = True


def appendix_heading(text):
    """A standalone appendix label, including a letter/number and optional short title."""
    return bool(re.fullmatch(r"appendi(?:x|ces)(?:\s+[A-Z0-9IVX]+)?(?:\s*[:.\u2014\u2013-]\s*[^\n]{1,80})?",
                             text.strip(), re.I))


def reference_section_cuts(blocks, cols, body, floats=(), panels=()):
    """A reference heading above aligned columns opens a new horizontal section.

    The heading must start at the left edge of the text frame, have a clear
    channel across the page, and have text starting together in at least two
    nonoverlapping columns below it. A heading inside one continuing column
    therefore does not split the other columns. Floats and panels veto cuts
    through their outer boundaries. A standalone appendix label at the frame's
    left edge also starts a section when its whole horizontal band is clear.
    Its short ink width does not make it part of the preceding left column.
    """
    cuts = []
    for h in blocks:
        appendix = appendix_heading(h.get("text", ""))
        if not appendix and (h.get("table_header_cell") or not reference_heading(h.get("text", ""))): continue
        x0, y0, _, y1 = h["box_px"]
        if not cols or abs(x0 - min(c[0] for c in cols)) > body: continue
        if any(b is not h and b["box_px"][1] < y1 and b["box_px"][3] > y0 for b in blocks): continue
        if any(b[1] < y1 and b[3] > y0 for b in list(floats) + [p["box_px"] for p in panels]): continue
        if appendix:
            cuts.append(y0)
            continue
        starts = []
        for c0, c1 in sorted(cols):
            below = [b for b in blocks if b["box_px"][1] >= y1 and
                     c0 - body <= b["box_px"][0] and b["box_px"][2] <= c1 + body]
            if not below: continue
            top = min(b["box_px"][1] for b in below)
            if top - y1 <= 3 * body and not any(c0 < r and l < c1 for l, r, _ in starts):
                starts.append((c0, c1, top))
        if len(starts) >= 2 and max(s[2] for s in starts) - min(s[2] for s in starts) <= body:
            cuts.append(y0)
    return sorted(set(cuts))


def reading_order_opening_headings(blocks, cols, body, occupied=()):
    """Rule 7: a small-cap section heading opens the prose column below it.

    Named section headings may use smaller roman capitals rather than a bold
    face. Admit an otherwise unplaced, single-line heading only at the top of
    a known column, directly above sustained main prose within three body ems.
    Table/float frames and any intervening text veto recovery. Furniture is
    never eligible. The opening paragraph supplies the heading's column.
    """
    named = re.compile(r"(?:INTRODUCTION|BACKGROUND|MATERIALS(?: AND METHODS)?|METHODS|"
                       r"RESULTS(?: AND DISCUSSION)?|DISCUSSION|CONCLUSIONS?)")
    for b in blocks:
        if (b.get("cls") != "other" or b.get("lines") != 1 or
                not .65 * body <= b.get("size", 0) <= body or
                not named.fullmatch(b.get("text", "").strip())): continue
        x0, y0, x1, y1 = b["box_px"]
        fits = [c for c in cols if abs(x0-c[0]) <= .5*body and x1 <= c[1]+body]
        if not fits: continue
        col = min(fits, key=lambda c:c[1]-c[0])
        local = [a for a in blocks if a is not b and a.get("cls") != "furniture"
                 and min(a["box_px"][2],col[1])-max(a["box_px"][0],col[0]) > body]
        if any(a["box_px"][1] < y1 for a in local): continue
        nxt = min(local, key=lambda a:a["box_px"][1], default=None)
        if (not nxt or nxt.get("cls") != "main" or nxt.get("lines",0) < 3 or
                nxt["box_px"][1]-y1 > 3*body): continue
        if any(f[1] < nxt["box_px"][1] and f[3] > y0 and
               min(f[2],col[1]) > max(f[0],col[0]) for f in occupied): continue
        b.update(cls="main", why="heading before main text in its column", list_column=list(col))


def reading_order_bands(mains, cols, body, floats=(), panels=()):
    """Rule 7 (reading order): the main text of rule 6 is read from the top left of each page to
    the bottom right, and the count runs on from page to page.

    The page is first cut into bands, then read band by band. The cut falls in a white channel
    that crosses the whole text frame, and only where the layout changes there. The channels
    divide the page into stretches; each stretch uses the set of columns its occupants lie in;
    a channel cuts when the stretch above it and the stretch below it use different columns and
    neither set lies within the other. A stretch using only some of its neighbours' columns (a
    heading alone in one column while the other column's gap spans it, a column that ends early)
    is a gap, not a new layout, and the columns are still read whole; so are two stretches whose
    columns lie side by side without crossing (a heading alone in the left column, then one alone
    in the right, set at staggered heights): the cut needs a column on one side lying across a
    different column on the other. The occupants are the
    main-text blocks and the floats of rule 4: a float is not
    read, but it holds its place, so a figure in the top left keeps the page two-column and the
    left column is read first, while a table across both columns splits the page above and
    below itself; a float over some columns beside a column that runs past it on both sides
    does not cut (column-major around floats, D-017; see float_beside). Within a band the columns of rule 6 are read left to right and the blocks of
    a column top to bottom; blocks whose tops lie within same_line_em letter heights of each
    other are one line and read left to right (a heading's number, separator and words); a
    margin label (a reference number in the margin) rides with the block it stands beside, at its
    own line, and has no order number of its own. The columns are the page's own and
    the paper's together, each block keyed to the narrowest column holding the whole of it, so on
    the title page the abstract's wide column and the body's columns stay distinct. A paper column
    whose two edges both lie within column_indent_em letter heights of one of the page's columns
    is that column, not another, so an indented stretch of a column is read with its column.
    After geometric ordering, main_text places explicitly owned side-abstract regions
    before body prose, and author-labelled translation bands in language order,
    with each band's author column preceding its title and abstract column.
    Before ordering, reading_order_opening_headings also admits named small-cap
    section headings at the start of a prose column, even in smaller roman type.

    What is not done: no cut at the widest white gap. On a two-column page the gap between
    paragraphs is wider than the gutter, so that cut reads the two columns as alternating rows.
    Here the gutter is already known from rule 6 and a channel cuts only when the layout changes.

    A prose panel is one occupant at its outer boundary. Its children are ordered
    recursively using only its own columns, then expanded after the page has been
    ordered. A spanning panel therefore separates the bands above and below it;
    a panel within one column starts at its geometric position. The subsequent
    reading_order_defer_panels pass moves it past an interrupted paragraph.
    Neither its child columns nor their gaps can interrupt another page column.
    A bibliography or study-list heading above aligned column starts also opens
    a new band, even when its short text occupies only the leftmost column.
    Each section is read column by column before the next section begins.
    A standalone appendix heading at the left frame edge and in a clear
    horizontal band likewise follows every preceding column, regardless of
    the heading's short ink width.
    A short display heading takes the column of the immediately following,
    left-aligned block below it. Narrow columns witnessed elsewhere in the paper
    must not capture a heading independently of its opening paragraph. Stacked
    headings inherit the same column. The following prose must be smaller than
    the heading: a supplement's larger body or table type is not a heading.
    A spanning heading or intervening float cannot use this rule.

    Returns the ordered blocks and the cut positions (y) for the drawing."""
    if not mains: return [], []
    sections = reference_section_cuts(mains, cols, body, floats, panels)
    if sections:
        ordered = []; bounds = list(sections)
        edges = [-1e9] + sections + [1e9]
        for lo, hi in zip(edges, edges[1:]):
            band = [b for b in mains if lo <= b["box_px"][1] < hi]
            heads = [b for b in band if b["box_px"][1] == lo and
                     (reference_heading(b.get("text", "")) and not b.get("table_header_cell") or appendix_heading(b.get("text", "")))]
            children, inner = reading_order_bands([b for b in band if b not in heads], cols, body,
                [f for f in floats if lo <= f[1] < hi], [p for p in panels if lo <= p["box_px"][1] < hi])
            ordered.extend(heads + children); bounds.extend(inner)
        return ordered, sorted(bounds)
    if panels:
        by_id = {b["id"]: b for b in mains}
        taken = set(); units = []
        for panel in panels:
            members = [by_id[bid] for bid in panel["blocks"] if bid in by_id]
            if not members: continue
            children, _ = reading_order_bands(members, panel["columns"], body)
            units.append(dict(id=panel["id"], box_px=panel["box_px"], panel_members=children))
            taken.update(b["id"] for b in members)
        outer, bounds = reading_order_bands([b for b in mains if b["id"] not in taken] + units, cols, body, floats)
        return [child for b in outer for child in b.get("panel_members", [b])], bounds
    labels = [b for b in mains if b.get("why") == "label beside main text of its size"]
    blocks = [b for b in mains if b not in labels]
    occupants = blocks + [{"box_px": F, "float": True} for F in floats]
    def geometric_column(b):
        """the narrowest column holding the whole block (within a letter height), else the narrowest
        holding half its width, else the block's own extent: an abstract spanning the gutter is not
        a block of the right-hand body column"""
        if b.get("list_column"): return tuple(b["list_column"])
        x0, x1 = b["box_px"][0], b["box_px"][2]
        whole = [c for c in cols if x0 >= c[0] - body and x1 <= c[1] + body]
        half = [c for c in cols if min(x1, c[1]) - max(x0, c[0]) >= 0.5 * (x1 - x0)]
        pick = whole or ([] if "panel_members" in b else half)
        return tuple(min(pick, key=lambda c: c[1] - c[0])) if pick else (round(x0), round(x1))
    heading_columns = {}
    for b in sorted(blocks, key=lambda b: b["box_px"][1], reverse=True):
        size = b.get("size", b.get("size_px", 0))
        if b.get("lines", 99) > 3 or size <= 1.08 * body or not re.search(r"[A-Za-z]", b.get("text", "")): continue
        x0, y0, x1, y1 = b["box_px"]
        below = [a for a in blocks if a is not b and a["box_px"][1] >= y1
                 and abs(a["box_px"][0] - x0) <= body
                 and x1 <= a["box_px"][2] + body]
        if not below: continue
        nxt = min(below, key=lambda a: a["box_px"][1]); nb = nxt["box_px"]
        if nb[1] - y1 > 4 * size: continue
        next_size = nxt.get("size", nxt.get("size_px", 0))
        if size <= 1.08 * next_size and nxt["id"] not in heading_columns: continue
        if any(f[1] < nb[1] and f[3] > y1 and min(f[2], nb[2]) > max(f[0], x0) for f in floats): continue
        heading_columns[b["id"]] = heading_columns.get(nxt["id"], geometric_column(nxt))
    def column_key(b):
        return heading_columns.get(b.get("id"), geometric_column(b))
    # the white channels across the frame: y intervals no occupant covers
    spans = sorted((o["box_px"][1], o["box_px"][3]) for o in occupants)
    channels = []; reach = spans[0][1]
    for top, bottom in spans[1:]:
        if top > reach: channels.append((reach, top))
        reach = max(reach, bottom)
    edges = [-1e9] + [y for ch in channels for y in ch] + [1e9]
    stretches = [(edges[k], edges[k + 1]) for k in range(0, len(edges), 2)]   # page top to first channel, channel to channel, last channel to page bottom
    def used(stretch): return {column_key(o) for o in occupants if min(o["box_px"][3], stretch[1]) - max(o["box_px"][1], stretch[0]) > 0}
    def crossed(a, b):
        """a column on one side lies across a different column on the other (a float or a wide block
        over the body's columns): the layout changes; a left column above and a right column below do not"""
        return any(ca != cb and min(ca[1], cb[1]) - max(ca[0], cb[0]) > 0 for ca in a for cb in b)
    def present(stretch): return [o for o in occupants if min(o["box_px"][3], stretch[1]) - max(o["box_px"][1], stretch[0]) > 0]
    def float_beside(up, down):
        """Column-major reading around a float set beside a running column (D-017): a float
        over some columns, with another column running past it on both sides of the channel,
        is not a layout change when the body columns are the same on both sides and every
        column the float crosses has body text on one side only (the float at the top or foot
        of its columns). Measured: AI06 p8, a figure over columns 1-2 at the top of a
        three-column page, whose third column was read before the first. A float over every
        column (a table across the page) still cuts; so does a float with body text above and
        below it in the columns it crosses. Short small blocks (figure lettering that rule 6
        kept) are not body text."""
        floats_here = [o for o in present(up) + present(down) if o.get("float")]
        if not floats_here: return False
        def body_key(o):
            return not o.get("float") and (o.get("lines", 99) >= 3 or o.get("size", o.get("size_px", body)) >= .95 * body)
        ut = {column_key(o) for o in present(up) if body_key(o)}
        dt = {column_key(o) for o in present(down) if body_key(o)}
        if not ut or not dt or not (ut <= dt or dt <= ut): return False
        def crosses(c): return any(min(c[1], f["box_px"][2]) - max(c[0], f["box_px"][0]) > 0 for f in floats_here)
        page_cols = {tuple(c) for c in cols}
        if not any(c in page_cols and not crosses(c) for c in ut & dt): return False
        return not any(crosses(c) and c in ut and c in dt for c in page_cols)
    cuts = [(y0 + y1) / 2 for (y0, y1), up, down in zip(channels, stretches, stretches[1:])
            if not (used(up) <= used(down) or used(down) <= used(up)) and crossed(used(up), used(down))
            and not float_beside(up, down)]
    bands = []; start = -1e9
    for y in cuts + [1e9]:
        band = [b for b in blocks if start <= b["box_px"][1] < y]
        if band: bands.append(band)
        start = y
    def label_of(b):
        return [lb for lb in labels if b["box_px"][1] - 0.5 * body <= lb["box_px"][1] and lb["box_px"][3] <= b["box_px"][3] + 0.5 * body]
    for b in blocks: b["labels"] = label_of(b)
    ordered = []
    for band in bands:
        by_col = collections.defaultdict(list)
        for b in band: by_col[column_key(b)].append(b)
        for key in sorted(by_col):
            rows = []
            for b in sorted(by_col[key], key=lambda b: b["box_px"][1]):
                if rows and b["box_px"][1] - rows[-1][0]["box_px"][1] <= PARAMS["same_line_em"] * body: rows[-1].append(b)
                else: rows.append([b])
            for row in rows:
                ordered += sorted(row, key=lambda b: b["box_px"][0])
    stray = [lb for lb in labels if not any(lb in b["labels"] for b in blocks)]
    return ordered + stray, cuts


def reading_order_abstract_columns(ordered, body, text_of, floats=()):
    """Rule 7: a labelled abstract that runs on into the next column is read whole before the body.

    An abstract may be set in the body's own columns above the body (one band of
    two columns over another band of the same two columns). Rule 7's bands cut
    only where the column set changes, so such a page is read column by column
    down the whole page, and the body below the abstract's first column
    interrupts the abstract. The abstract band is cut off only when all of these
    witness it: the abstract's first block opens with its label (Abstract or
    Summary, alone, with a colon or stop, or run in in capitals); its column's stacked blocks (gaps within flow_gap_em, the same
    size within body_size_tolerance) end without sentence punctuation; exactly
    one block in the next column to the right starts at the label's top or its
    text's top (within same_line_em) in that size, with a lowercase word, so it continues the
    unfinished sentence (a capitalised start could be a heading or a new
    paragraph and does not fire); and a white channel crosses the whole frame
    below both columns of the abstract (no main block or float spans it, and
    main text follows below it). The blocks above the channel are then read
    before those below, each part keeping its own column-by-column order.
    Any missing witness leaves the geometric order unchanged.
    Returns the ordered blocks and the channel's y (None when it does not fire)."""
    tol = PARAMS["body_size_tolerance"]
    def size(b): return b.get("size", b.get("size_px", 0)) or 0
    def same_size(a, b): return abs(size(a) - size(b)) <= tol * max(size(a), size(b), 1e-9)
    def x_share(a, b):
        A, B = a["box_px"], b["box_px"]
        return (min(A[2], B[2]) - max(A[0], B[0])) / max(1e-9, min(A[2] - A[0], B[2] - B[0]))
    def stack(first, label=False):
        """first and the blocks stacked under it in its column; a label alone on its line may
        differ in size from the text under it"""
        chain = [first]
        for b in sorted(ordered, key=lambda b: b["box_px"][1]):
            last = chain[-1]["box_px"]
            if b in chain or b["box_px"][1] < last[3] or x_share(b, first) < .5: continue
            if (b["box_px"][1] - last[3] > PARAMS["flow_gap_em"] * body or
                    not (label and len(chain) == 1 or same_size(b, chain[-1]))): break
            chain.append(b)
        return chain
    def labelled(b):
        """the abstract's label: an identified abstract, the label alone or with a colon/stop, or a
        run-in label in capitals (a body heading such as "Summary of the studies" is none of these)"""
        text = text_of(b).strip(); first = text.split("\n", 1)[0]
        return bool(b.get("abstract") or re.fullmatch(r"(?:abstract|summary)\s*[:.]?", first, re.I)
                    or re.match(r"^(?:abstract|summary)\s*[:.]\s+\S", text, re.I)
                    or re.match(r"^(?:ABSTRACT|SUMMARY)\b(?!\s+OF\b)\s*\S", text))
    head = next((b for b in ordered if labelled(b)), None)
    if head is None: return ordered, None
    alone = len(text_of(head).strip().split("\n")) == 1
    left = stack(head, alone)
    if alone and len(left) < 2: return ordered, None
    size_ref = left[1] if alone else head
    if not re.search(r"\w", text_of(left[-1])) or re.search(r"[.!?:;][\"'\u2019\u201d)\]]*\s*$", text_of(left[-1])): return ordered, None
    hx1 = max(b["box_px"][2] for b in left); tops = [head["box_px"][1], size_ref["box_px"][1]]
    nexts = [b for b in ordered if b not in left and b["box_px"][0] >= hx1 - .5 * body
             and min(abs(b["box_px"][1] - top) for top in tops) <= PARAMS["same_line_em"] * body]
    if len(nexts) != 1: return ordered, None
    cont = nexts[0]
    if not same_size(cont, size_ref) or not re.match(r"^[a-z]", text_of(cont).strip()): return ordered, None
    band = left + stack(cont)
    cut = max(b["box_px"][3] for b in band)
    above = [b for b in ordered if b["box_px"][1] < cut]
    below = [b for b in ordered if b["box_px"][1] >= cut]
    if not below or any(b["box_px"][3] > cut for b in above): return ordered, None
    if any(f[1] < cut < f[3] for f in floats): return ordered, None
    channel = (cut + min(b["box_px"][1] for b in below)) / 2
    result = above + below
    if result == ordered: return ordered, None
    return result, channel


def split_runin_abstract(page, body):
    """Rule 6: reserve a structured summary inside a mixed title/byline block.

    An opening problem/background/purpose label and two further run-in labels,
    including Results or Conclusions, witness the summary. Its aligned, equally
    sized lines continue until a gap, a size change or a new horizontal extent.
    A larger title run before the summary must share its block; an existing
    Abstract panel remains intact, including its trailing keywords.
    Split ownership before the title/byline pass; retain the original block for
    an idempotent --paper rerun. No author or institution line is abstract text.
    """
    opening = re.compile(r'^(?:Statement of (?:the )?problem|Background|Objectives?|Aims?|Purpose)\s*[.:]', re.I)
    label = re.compile(r'^(?:Statement of (?:the )?problem|Background|Objectives?|Aims?|Purpose|Materials?(?: and methods)?|Methods|Results|Conclusions?)\s*[.:]', re.I)
    runs = [e for e in page['runs'] if e['angle'] == 0]
    for first in sorted(runs, key=lambda e:e['box_px'][1]):
        if not opening.match(first['text']): continue
        B = first['box_px']; size = first['run_size_px']; group = [first]
        for e in sorted(runs, key=lambda e:e['box_px'][1]):
            b = e['box_px']
            if e is first or b[1] < B[3] or b[2] < B[0] or b[0] > B[2]: continue
            if (abs(b[0]-B[0]) > size or b[2] > B[2]+size or
                    abs(e['run_size_px']-size) > .1*size or
                    b[1]-group[-1]['box_px'][3] > 2*size): break
            group.append(e)
        heads = [e for e in group if label.match(e['text'])]
        if len(heads) < 3 or not any(re.match(r'^(Results|Conclusions?)\s*[.:]', e['text'], re.I) for e in heads): continue
        ids = {e['id'] for e in group}
        # Split only a mixed title/summary block. An ordinary abstract panel
        # may also contain its heading and keywords, which must keep their order.
        if not any(ids.intersection(b['members']) and any(e['id'] in b['members']
                   and e['box_px'][3] < B[1] and e['run_size_px'] >= 1.3*size
                   and len(e['text'].split()) >= 3 for e in runs) for b in page['blocks']): continue
        result = []
        for b in page['blocks']:
            if not ids.intersection(b['members']): result.append(b); continue
            for suffix, ms in [('front', [m for m in b['members'] if m not in ids]),
                               ('abstract', [m for m in b['members'] if m in ids])]:
                if not ms: continue
                es = [e for e in runs if e['id'] in ms]; bs = [e['box_px'] for e in es]
                part = dict(b, id=b['id']+':'+suffix, members=ms, main_text_source=b['id'],
                    box_px=[min(x[0] for x in bs),min(x[1] for x in bs),max(x[2] for x in bs),max(x[3] for x in bs)],
                    text_lines=len({e['line'] for e in es}), text=' '.join(e['text'] for e in es)[:80],
                    runin_abstract=suffix=='abstract')
                result.append(part); page['d']['blocks'].append(part.copy())
        page['blocks'] = result
        return


ABSTRACT_LABEL_ROW = re.compile(r'^\s*(?:abstract|summary)\s*[:.\-–—]?\s*$', re.I)
ABSTRACT_RUNIN_ROW = re.compile(r'^\s*(?i:abstract|summary)\s*[:.\-–—]\s*\S|^\s*(?:ABSTRACT|SUMMARY)\s+(?!OF\b)\S')


def split_labelled_abstract(page, body):
    """Rule 6 (lane r6-abstract, rules B1, B3, B10): the abstract starts at its label.

    On the front page, a block whose rows above hold other front text (the title, the
    names, the affiliations) and which goes on with a row that opens with the label
    "Abstract" or "Summary" (any case; alone on its printed line, or run in with a
    colon, a stop or a dash, or in capitals before the text) is cut at that row: the
    label row and every row below it in the block are the abstract, a block of their
    own; the rows above stay the front block. The label must stand alone on its printed
    line (no run of another block shares the line) and, when it is alone, have a row
    under it. Nothing is decided by size or face (B7). The structured summary set with
    the byline is split_runin_abstract's (it runs first; its parts are not cut again).
    The original block is retained for an idempotent --paper rerun.
    """
    runs = {e['id']: e for e in page['runs'] if e['angle'] == 0}
    result, changed = [], False
    for b in page['blocks']:
        if b.get('runin_abstract') is not None or b.get('labelled_abstract') is not None:
            result.append(b); continue
        members = set(b['members'])
        rows = collections.OrderedDict()
        for e in sorted((runs[m] for m in b['members'] if m in runs and runs[m]['text'].strip()),
                        key=lambda e: (e['box_px'][1], e['box_px'][0])):
            ln = page['run_line'].get(e['id'])
            rows.setdefault(id(ln) if ln is not None else e['id'], []).append(e)
        rows = list(rows.values())
        cut = None
        for i, row in enumerate(rows):
            if i == 0: continue
            ln = page['run_line'].get(row[0]['id'])
            if ln is None or any(x['id'] not in members for x in ln['runs'] if x['text'].strip()): continue
            text = ' '.join(e['text'].strip() for e in sorted(row, key=lambda e: e['box_px'][0]))
            if ABSTRACT_LABEL_ROW.match(text) and i + 1 < len(rows) or ABSTRACT_RUNIN_ROW.match(text):
                cut = i; break
        if cut is None:
            result.append(b); continue
        ids = {e['id'] for r in rows[cut:] for e in r}
        for suffix, ms in [('front', [m for m in b['members'] if m not in ids]),
                           ('abstract', [m for m in b['members'] if m in ids])]:
            if not ms: continue
            es = [runs[m] for m in ms if m in runs]
            if not es: continue
            bs = [e['box_px'] for e in es]
            part = dict(b, id=b['id'] + ':' + suffix, members=ms, main_text_source=b['id'],
                        box_px=[min(x[0] for x in bs), min(x[1] for x in bs), max(x[2] for x in bs), max(x[3] for x in bs)],
                        text_lines=len({e['line'] for e in es}), text=' '.join(e['text'] for e in es)[:80],
                        labelled_abstract=suffix == 'abstract')
            result.append(part); page['d']['blocks'].append(part.copy())
        changed = True
    if changed: page['blocks'] = result


def reading_order_abstract_flow(ordered, blocks, previous, rows_of, text_of, allow_open=True):
    """Keep an unfinished abstract and its keywords ahead of next-page body columns.

    The last ordered block must be an identified abstract or open with its explicit
    label, and end without sentence punctuation. The next page's first aligned
    block must start in the same face and size. Check its prose rows individually:
    a smaller keyword suffix must not change the continuation's measured style.
    Separate, adjacent keyword blocks travel with the continuation. Furniture,
    captions, intervening column text and a different prose style stop the match.
    Only front flow can open an abstract; a witnessed continuation can carry on
    across further pages. A body heading such as Summary of findings is not an
    abstract label. No source runs or detector floats change ownership.
    """
    def faces(row):
        return {f for e in row for f in (e.get('font', []) if isinstance(e.get('font'), list)
                                        else [e.get('font')]) if f}
    def size(row):
        return max(e.get('run_size_px', e.get('size_px', 0)) for e in row)
    def keywords(text):
        return bool(re.match(r'^Key\s*words\b', text.strip(), re.I))
    selected = []
    if previous:
        em = previous['size']; left, right = previous['column']
        aligned = sorted((b for b in blocks if b['cls'] != 'furniture'
                          and abs(b['box_px'][0]-left) <= em
                          and b['box_px'][2] <= right+em), key=lambda b:b['box_px'][1])
        if aligned:
            first = aligned[0]; rows = rows_of(first)
            prose = []
            for row in rows:
                if keywords(' '.join(e['text'] for e in row)): break
                prose.append(row)
            matching = (first['cls'] in ('main', 'other', 'aside') and prose
                        and not re.match(r'^(?:Abstract|Summary|Key\s*words)\b', text_of(first), re.I)
                        and all(abs(size(row)-em) <= .05*em and faces(row) == previous['faces']
                                for row in prose))
            if matching:
                selected = [first]
                # A detached keyword strip has its own block. Do not walk past
                # other prose to find it, even if it happens to share the column.
                for b in aligned[1:]:
                    if (b['cls'] not in ('main','other','aside') or not keywords(text_of(b))
                            or b['box_px'][1]-selected[-1]['box_px'][3] > 3*em): break
                    selected.append(b)
                for b in selected:
                    b.update(cls='main', abstract=True, abstract_continuation=True,
                             why='same-style continuation of the unfinished abstract before body text')
                ordered = selected + [b for b in ordered if b not in selected]
    pending = None
    if ordered:
        last = ordered[-1]; text = text_of(last).strip(); rows = rows_of(last)
        labelled = (re.fullmatch(r'(?:Abstract|Summary)\s*:?', text.split('\n', 1)[0], re.I)
                    or re.match(r'^(?:Abstract|Summary)\s*:\s+\S', text, re.I))
        if (rows and (allow_open or last.get('abstract_continuation'))
                and (last.get('abstract') or labelled)
                and not any(keywords(' '.join(e['text'] for e in row)) for row in rows)
                and not re.search(r'[.!?][\"\'’”)\]]*$', text)):
            pending = dict(size=size(rows[-1]), faces=faces(rows[-1]), column=last['box_px'][::2])
    return ordered, pending


def structured_abstract_blocks(blocks, body, text_of):
    """Own a title-page structured abstract without an Abstract/Summary heading.

    At least two labelled paragraphs must stack in the same column at the same
    size. The opening must be Background, Objective, Aim, Purpose or Statement
    of problem, followed by a colon or period; a later
    Methods/Results/Conclusion/Clinical implications label corroborates it.
    A gap, a different column, an unlabelled block or a size change ends it.
    Whole blocks are owned, including all wrapped lines after the final label.
    A Clinical implications/relevance/significance heading with its paragraph, as two blocks or
    as one framed block, is main text too.
    """
    for b in blocks:
        if b.get('runin_abstract'): b.update(cls='main', abstract=True, why='run-in structured abstract separated from front matter')
        if b.get('labelled_abstract'): b.update(cls='main', abstract=True, why='labelled abstract separated from the front block (B1)')
    if any(b.get('runin_abstract') for b in blocks):
        for h in blocks:
            head, *rest = text_of(h).strip().split("\n")
            # The heading and its paragraph in one framed block (their frame drawn round both; V09,
            # once the frame sits in the text's frame) are that summary too.
            if rest and h['lines'] >= 2 and re.fullmatch(r'Clinical (?:implications|relevance|significance)', head.strip(), re.I):
                h.update(cls='main', why='clinical summary heading and its paragraph'); continue
            if not re.fullmatch(r'Clinical (?:implications|relevance|significance)', text_of(h).strip(), re.I): continue
            below=sorted((b for b in blocks if b['box_px'][1]>=h['box_px'][3]
                          and abs(b['box_px'][0]-h['box_px'][0])<body),key=lambda b:b['box_px'][1])
            if below and below[0]['box_px'][1]-h['box_px'][3]<2*body and below[0]['lines']>=2:
                for b in (h,below[0]):b.update(cls='main',why='clinical summary heading and its paragraph')
    opening = re.compile(r"^(?:Statement of (?:the )?problem|Background|Objectives?|Aims?|Purpose)\s*[.:]", re.I)
    label = re.compile(r"^(?:Statement of (?:the )?problem|Background|Objectives?|Aims?|Purpose|Materials?(?: and Methods)?|"
                       r"Methods|Results|Conclusions?|Clinical (?:implications|relevance|significance))\s*[.:]", re.I)
    eligible = [b for b in blocks if b["cls"] in ("main", "other", "aside") and b["lines"] >= 2]
    for first in sorted(eligible, key=lambda b: b["box_px"][1]):
        if not opening.match(text_of(first).strip()): continue
        fb = first["box_px"]; group = [first]
        for b in sorted(eligible, key=lambda b: b["box_px"][1]):
            bb = b["box_px"]
            if b is first or bb[1] < fb[3] or abs(bb[0] - fb[0]) > body: continue
            if (abs(bb[2] - fb[2]) > 2 * body or bb[1] - group[-1]["box_px"][3] > 2 * body
                    or abs(b["size"] - first["size"]) > .1 * first["size"]
                    or not label.match(text_of(b).strip())): break
            group.append(b)
        if len(group) >= 2:
            for b in group: b.update(cls="main", abstract=True, why="labelled paragraph in the structured abstract")
            return


def side_abstract_blocks(blocks, elements, body, text_of):
    """Reserve a narrow title-page abstract beside ordinary body columns.

    A key-word label witnesses the end of a smaller or italic prose column.
    Each column is under 40% of the text width and has at least three lines;
    columns of the same face/size with the same top can precede the labelled
    column, which may end up to a few lines short of them (it ends the text).
    Ordinary body prose must stand beside the group. A heading-led smaller
    column is also explicit abstract evidence. Existing region gutters remain
    intact: neither shared line ids nor shared baselines join these columns.
    """
    runs = {e['id']: e for e in elements if e['kind'] == 'text'}
    eligible = [b for b in blocks if b['cls'] in ('main', 'aside', 'other')]
    if not eligible: return []
    width = max(b['box_px'][2] for b in eligible) - min(b['box_px'][0] for b in eligible)
    def italic(b):
        es = [runs[m] for m in b['members'] if m in runs]
        total = sum(len(e['text']) for e in es)
        return total and sum(len(e['text']) for e in es if re.search(
            r'italic|oblique|(?:^|[-,])it(?:$|[-,])', str(e.get('font', '')), re.I)) >= .9*total
    candidates = [b for b in eligible if b['lines'] >= 3 and
                  b['box_px'][2]-b['box_px'][0] < .4*width and
                  (b['size'] < .96*body or italic(b))]
    for end in candidates:
        text = text_of(end).strip()
        if not (re.search(r'(?:^|\n)Key\s*words\s*:', text, re.I) or
                re.match(r'^(?:Abstract|Summary)\b', text, re.I)): continue
        group = [end]
        # The unlabelled opening can occupy the adjacent column at the same
        # vertical extent, ending mid-sentence before the labelled column.
        for b in sorted(candidates, key=lambda b: b['box_px'][0], reverse=True):
            bb, eb = b['box_px'], group[0]['box_px']
            if b in group or not 0 < eb[0]-bb[2] < 3*body: continue
            # The labelled column ends the text, so it may stop up to a few
            # lines short of the column before it (AG11: one line shorter).
            if (abs(bb[1]-eb[1]) < body and -body < bb[3]-eb[3] < 4*body and
                    abs(b['size']-end['size']) < .1*body and italic(b) == italic(end)):
                group.insert(0, b)
        combined = '\n'.join(text_of(b) for b in group)
        keyword = re.search(r'(?:^|\n)Key\s*words\s*:', combined, re.I)
        # A key-word strip alone is publication metadata, not an abstract.
        # It witnesses ownership only with substantial preceding prose.
        if keyword and len(combined[:keyword.start()].split()) < 30: continue
        gb = [min(b['box_px'][0] for b in group), min(b['box_px'][1] for b in group),
              max(b['box_px'][2] for b in group), max(b['box_px'][3] for b in group)]
        # The paper's body size can be smaller than this page's opening prose
        # (AG11: body 19.0 px, page-one columns 21.9 px).
        beside = [b for b in eligible if b not in group and b['lines'] >= 3 and
                  .96*body <= b['size'] <= 1.2*body and not italic(b) and
                  (b['box_px'][2] < gb[0] or b['box_px'][0] > gb[2]) and
                  min(b['box_px'][3],gb[3])-max(b['box_px'][1],gb[1]) > 2*body]
        if not beside: continue
        for b in group:
            b.update(cls='main', abstract=True, side_abstract=True,
                     why='separate abstract column witnessed by its label and face')
        return [dict(box_px=gb, blocks=[b['id'] for b in group],
                     columns=[b['box_px'][::2] for b in group])]
    return []


def translated_abstract_blocks(blocks, elements, text_of):
    """A labelled translation page reads in language bands, authors then title/text.

    Require an Abstract Translations heading and repeated author-labelled left
    columns paired with right-column titles. Split only between whole runs at
    those author starts. Retain original rule-2 blocks and expose derived
    membership, so rerunning rule 6 is lossless and idempotent.
    """
    heads = [b for b in blocks if b['cls'] != 'furniture' and
             re.match(r'^Abstract\s+Translations\b', text_of(b).strip(), re.I)]
    if len(heads) != 1: return blocks, [], []
    head = heads[0]; hb = head['box_px']
    runs = {e['id']: e for e in elements if e['kind'] == 'text' and e['angle'] == 0}
    below = [b for b in blocks if b['cls'] in ('main', 'aside', 'other') and b is not head
             and b['box_px'][1] >= hb[3]]
    ids = {m for b in below for m in b['members']}
    starts = sorted((e for m,e in runs.items() if m in ids and
                     re.match(r'^AUTOR(?:\(E[NS]\)|ES|EN)?\s*:', e['text'].strip(), re.I)),
                    key=lambda e:e['box_px'][1])
    if len(starts) < 2: return blocks, [], []
    # Pair the author's first row with a title to its right; the gap between
    # the two is the language band's gutter, not a change of language.
    titles = []
    for start in starts:
        sb = start['box_px']; size = start.get('run_size_px', 16)
        ts = [b for b in below if b['lines'] <= 2 and b['box_px'][0] > sb[2] and
              abs(b['box_px'][1]-sb[1]) < size]
        if len(ts) != 1: return blocks, [], []
        titles.append(ts[0])
    ys = [e['box_px'][1] for e in starts]
    size = starts[0].get('run_size_px', 16)
    head.update(cls='main', in_refs=False, translation_role='heading')
    result = [b for b in blocks if b not in below]; sections = [[] for _ in starts]; splits = []
    for b in below:
        groups = [[] for _ in starts]
        for m in b['members']:
            if m not in runs: continue
            cy = (runs[m]['box_px'][1]+runs[m]['box_px'][3])/2
            i = max((i for i,y in enumerate(ys) if cy >= y-.5*size), default=0)
            groups[i].append(m)
        parts = []
        for i, ms in enumerate(groups):
            if not ms: continue
            boxes = [runs[m]['box_px'] for m in ms]
            box = [min(x[0] for x in boxes), min(x[1] for x in boxes),
                   max(x[2] for x in boxes), max(x[3] for x in boxes)]
            part = dict(b, members=ms, box_px=box, cls='main', in_refs=False,
                        translation=i+1, translation_role=('authors' if box[2] < titles[i]['box_px'][0]
                                                          else 'title' if b is titles[i] else 'text'))
            if len([g for g in groups if g]) > 1:
                part.update(id=b['id']+f':translation:{i+1}', main_text_source=b['id'])
            parts.append(part); sections[i].append(part)
        result.extend(parts)
        if any(p.get('main_text_source') == b['id'] for p in parts):
            splits.append(dict(source=b['id'], parts=[p['id'] for p in parts], runs=[],
                               why='author-labelled language bands below Abstract Translations'))
    ordered = [head]
    for section in sections:
        ordered.extend(sorted(section, key=lambda b:(b['translation_role'] != 'authors', b['box_px'][1], b['box_px'][0])))
    return result, ordered, splits


def introduced_list_columns(blocks, cols, body, text_of):
    """A short list introduced by a colon uses its lead-in's column, not a new narrow column.

    Require two printed item markers, aligned left edges, a small vertical gap,
    and no intervening text in the lead-in's column. Table/reference lists and
    captions cannot supply the lead-in. Only reading order changes.
    """
    marker = re.compile(r"^\s*(?:[•●◦]|\d{1,2}[.)]|[a-z][.)])\s", re.M)
    for b in blocks:
        if b["cls"] != "main" or b.get("in_refs") or len(marker.findall(text_of(b))) < 2: continue
        bb = b["box_px"]
        above = [a for a in blocks if a is not b and a["cls"] == "main" and not a.get("in_refs")
                 and abs(a["box_px"][0] - bb[0]) <= body
                 and 0 <= bb[1] - a["box_px"][3] <= 3 * body]
        if not above: continue
        a = max(above, key=lambda a: a["box_px"][3])
        if not text_of(a).rstrip().endswith(":"): continue
        ab = a["box_px"]
        fits = [c for c in cols if c[0] - body <= min(ab[0], bb[0]) and max(ab[2], bb[2]) <= c[1] + body]
        own = [c for c in cols if c[0] - body <= bb[0] and bb[2] <= c[1] + body]
        if fits and own:
            wanted = min(fits, key=lambda c: c[1] - c[0])
            current = min(own, key=lambda c: c[1] - c[0])
            if wanted != current: b["list_column"] = list(wanted)


def column_footnotes(blocks, elements, body, height, excluded=()):
    """Identify small marker-led notes at column feet, even inside a body block.

    A note is a suffix of at most five rows in a main block, under the last body
    row or a short rule, in the bottom quarter of the page. Its face must be at
    most 82% of the body. A separated note may use a single letter/digit marker
    (including a misencoded symbol); ordinary body-sized lists do not qualify.
    A separate block may instead have a gap from the last body block in its
    column. Table members are excluded. Rule 6 gives the selected runs their
    own other/footnote class; exporters defer them past paragraph continuation.
    """
    runs = {e["id"]: e for e in elements if e["kind"] == "text"}
    notes = []
    for b in blocks:
        if b["cls"] not in ("main", "other") or b.get("in_refs"): continue
        rows = collections.defaultdict(list)
        for m in b["members"]:
            if m in runs and runs[m]["angle"] == 0: rows[runs[m]["line"]].append(runs[m])
        rows = sorted(rows.values(), key=lambda row: min(e["box_px"][1] for e in row))
        for i, row in enumerate(rows):
            if len(rows) - i > 5: continue
            row = sorted(row, key=lambda e: e["box_px"][0])
            text = " ".join(e["text"].strip() for e in row)
            if not re.match(r"^(?:[*†‡§¶#‖|]+|[a-z]|\d{1,2})\s+\S", text): continue
            tail = [e for r in rows[i:] for e in r]
            # Formula indices can also look like a tiny numbered footer.
            # A prose/supplier note must contain at least one alphabetic word.
            if not re.search(r'[^\W\d_]{3,}', ' '.join(e['text'] for e in tail)): continue
            if any(e['id'] in excluded for e in tail): continue
            if any(e.get("run_size_px", e["size_px"]) > .82 * body for e in tail): continue
            x0 = min(e["box_px"][0] for e in tail); x1 = max(e["box_px"][2] for e in tail)
            y0 = min(e["box_px"][1] for e in tail); y1 = max(e["box_px"][3] for e in tail)
            if y0 < .75 * height: continue
            separated = bool(i and y0 - max(e["box_px"][3] for e in rows[i-1]) >= .35 * body
                             and max(e.get("run_size_px", e["size_px"]) for e in rows[i-1]) >= .95 * body)
            if not i:
                above = [a for a in blocks if a is not b and a['cls'] == 'main'
                         and a.get('size', a.get('size_px', 0)) >= .95 * body
                         and 0 <= y0-a['box_px'][3] <= 8*body
                         and min(x1,a['box_px'][2])-max(x0,a['box_px'][0]) >= .6*(x1-x0)]
                separated = bool(above and y0-max(a['box_px'][3] for a in above) >= .35*body)
            ruled = any(e["kind"] in ("rule", "fill") and e["box_px"][3] - e["box_px"][1] < .2 * body
                        and 0 <= y0 - e["box_px"][3] <= 2 * body
                        and min(x1, e["box_px"][2]) - max(x0, e["box_px"][0]) >= .6 * (x1-x0)
                        for e in elements)
            if not (separated or ruled): continue
            if any(e["id"] not in {r["id"] for r in tail} and e["box_px"][1] >= y0
                   and x0 <= (e["box_px"][0]+e["box_px"][2])/2 <= x1
                   and e.get("run_size_px", e["size_px"]) >= .95 * body
                   and e["box_px"][3] < .95 * height for e in runs.values()): continue
            notes.append(dict(block=b["id"], members=[e["id"] for e in tail], box_px=[x0,y0,x1,y1],
                              why="small marker-led note set apart at the column foot"))
            break
    return notes

def reading_order_captioned_lists(blocks, cols, body, text_of, floats=(), panels=()):
    """Keep a printed table caption and its undetected numbered list atomic in rule 7.

    This is ownership for reading order, not a new rule-3 table or rule-4 float.
    An explicit uppercase table label starts a group within one known column.
    Adjacent blocks of its text size belong to it until a large vertical gap or
    a larger body/heading font. Require at least three numbered entries; a prose
    sentence mentioning a table is not a captioned list. Existing floats and
    panels own their contents first. Unordered caption blocks stay classified
    as captions; their membership is saved for the exporter to place with the list.
    """
    excluded = {bid for f in list(floats) + list(panels) for bid in f.get("blocks", [])}
    groups = []; taken = set(excluded)
    candidates = [b for b in blocks if b["cls"] in ("main", "caption") and b["id"] not in excluded]
    def hull(boxes):
        return [min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes)]
    label = r"^\s*T\s*A\s*B\s*L\s*E\s+\d+[A-Za-z]?\b"
    for cap in sorted(candidates, key=lambda b: (b["box_px"][0], b["box_px"][1])):
        if cap["id"] in taken or not re.match(label, text_of(cap)): continue
        cb = cap["box_px"]
        columns = [c for c in cols if c[0] - 2 * body <= cb[0] < c[1] and cb[2] <= c[1] + 2 * body]
        if not columns: continue
        col = min(columns, key=lambda c: c[1] - c[0])
        near = sorted((b for b in candidates if b["id"] not in taken and
                       col[0] - 2 * body <= b["box_px"][0] and b["box_px"][2] <= col[1] + 2 * body and
                       b["box_px"][1] >= cb[1] - .5 * body), key=lambda b: b["box_px"][1])
        members = []; bottom = cb[1]
        for b in near:
            if b["box_px"][1] - bottom > 3 * body or b["size"] > 1.12 * cap["size"]: break
            if members and b is not cap and re.match(label, text_of(b)): break
            members.append(b); bottom = max(bottom, b["box_px"][3])
        lines = "\n".join(text_of(b) for b in members)
        if len(re.findall(r"(?m)^\s*\d+(?:\.\d+)*[.)]?\s+\S", lines)) < 3: continue
        mains = [b["id"] for b in members if b["cls"] == "main"]
        if not mains: continue
        groups.append(dict(id="captioned-list:" + cap["id"], kind="table", blocks=mains,
                           caption_blocks=[b["id"] for b in members if b["cls"] == "caption"],
                           members=[m for b in members for m in b["members"]],
                           label_block=cap["id"], box_px=hull([b["box_px"] for b in members]), columns=[col]))
        taken.update(b["id"] for b in members)
    return groups


def reading_order_front_columns(blocks, elements, following, title_box):
    """Rule 7: bound a front panel beside a continuing introduction column.

    Require three independent witnesses: a substantial justified column whose
    face, size and width recur in prose on the following page; adjacent short
    name rows; and a smaller, mostly italic summary below those names. The
    summary and names must be wholly across the gutter from the body. This
    distinguishes an unlabelled abstract from ordinary first-page prose, even
    when the paper-wide median size is dominated by references. Floats, tables,
    captions, furniture and title membership are never reassigned.

    Correct only the reading/export ownership: the summary precedes the body,
    the name block is authors, and the other front-column blocks remain front
    matter. Record these bounds for rule 8 and the copy's fallback; a shared
    baseline cannot make an introduction line part of the byline. Rules 1-5
    and all run/character memberships remain unchanged.
    """
    if not following or not title_box: return None
    def details(block, runs):
        es = [runs[m] for m in block['members'] if m in runs]
        rows = collections.defaultdict(list)
        for e in es: rows[e['line']].append(e)
        rows = sorted(rows.values(), key=lambda row:min(e['box_px'][1] for e in row))
        text = [' '.join(e['text'] for e in sorted(row, key=lambda e:e['box_px'][0])) for row in rows]
        sizes = [e.get('run_size_px', e['size_px']) for e in es for _ in e['text'].strip()]
        faces = collections.Counter()
        italic = total = 0
        for e in es:
            fonts = e.get('font', [])
            if isinstance(fonts, str): fonts = [fonts]
            for font in fonts: faces[re.sub(r'^[A-Z]{6}\+', '', font)] += len(e['text'])
            total += len(e['text'])
            if any(re.search(r'Italic|Oblique', font, re.I) for font in fonts): italic += len(e['text'])
        width = block['box_px'][2]-block['box_px'][0]
        justified = bool(rows) and sum(max(e['box_px'][2] for e in row)-min(e['box_px'][0] for e in row)
                                      >= .7*width for row in rows) >= .6*len(rows)
        prose = (len(rows) >= 6 and len(' '.join(text).split()) >= 30 and justified
                 and bool(re.search(r'[a-z][.!?](?:\d|\s|$)', ' '.join(text)))
                 and not re.match(r'^(?:Abstract|Summary|References|Correspondence|\d*\s*(?:Department|University))\b',
                                  ' '.join(text), re.I))
        return dict(rows=text, size=statistics.median(sizes) if sizes else 0, width=width,
                    face=faces.most_common(1)[0][0] if faces else '', prose=prose,
                    italic=italic/max(1,total))
    runs = {e['id']:e for e in elements if e['kind']=='text' and not e.get('angle', 0)}
    next_runs = {e['id']:e for e in following['elements'] if e['kind']=='text' and not e.get('angle', 0)}
    excluded = {m for t in following.get('tables', []) for m in t.get('members', [])}
    float_blocks = {bid for f in following.get('floats', []) for bid in f['blocks']}
    witnesses = [details(b,next_runs) for b in following['blocks'] if b['id'] not in float_blocks
                 and not excluded.intersection(b['members'])]
    witnesses = [d for d in witnesses if d['prose']]
    eligible = [b for b in blocks if b['cls'] in ('main','authors','aside','other')
                and b['box_px'][1] >= title_box[3]-1]
    info = {b['id']:details(b,runs) for b in eligible}
    for body_block in eligible:
        d = info[body_block['id']]; bx = body_block['box_px']
        if not d['prose'] or len(d['rows']) < 10: continue
        if not any(w['face']==d['face'] and abs(w['size']-d['size']) <= .05*d['size']
                   and abs(w['width']-d['width']) <= .15*d['width'] for w in witnesses): continue
        def beside(b):
            x = b['box_px']
            return max(bx[0]-x[2], x[0]-bx[2]) >= d['size']
        names = [b for b in eligible if beside(b) and 1 <= len(info[b['id']]['rows']) <= 8
                 and abs(b['box_px'][1]-bx[1]) <= 2*d['size']
                 and all(byline_name_groups([row]) for row in info[b['id']]['rows'])]
        if len(names) != 1: continue
        name = names[0]; nb = name['box_px']
        summaries = [b for b in eligible if beside(b) and info[b['id']]['prose']
                     and info[b['id']]['italic'] >= .6 and .7*d['size'] <= info[b['id']]['size'] < .96*d['size']
                     and b['box_px'][1] > nb[3] and b['box_px'][3] < bx[3]
                     and min(b['box_px'][2],nb[2])-max(b['box_px'][0],nb[0]) > .5*(nb[2]-nb[0])]
        if len(summaries) != 1: continue
        summary = summaries[0]
        body_block.update(cls='main', in_refs=False, why='introduction column continues in the next page body face')
        summary.update(cls='main', abstract=True, side_abstract=True, in_refs=False,
                       why='italic summary in the front column beside the introduction')
        name.update(cls='authors', why='name rows in the bounded front column')
        front = [name['id']]
        for b in eligible:
            if b in (name,summary) or not beside(b): continue
            sb = summary['box_px']; bb = b['box_px']
            if sb[0]-d['size'] <= bb[0] and bb[2] <= sb[2]+d['size']:
                b.update(cls='other', why='front-column information beside the introduction')
                front.append(b['id'])
        return dict(body_blocks=[body_block['id']], abstract_blocks=[summary['id']],
                    author_blocks=[name['id']], front_blocks=front,
                    body_box_px=list(bx), front_box_px=[summary['box_px'][0],nb[1],summary['box_px'][2],bx[3]])
    return None


def reading_order_defer_panels(ordered, panels, body, text_of, rows_of, previous_text="", order_start=0):
    """Rule 7: an atomic panel or captioned list belongs between paragraphs.

    Keep the geometric order unless the preceding prose is unfinished and the
    next ordinary block continues it, or that block starts lowercase despite
    apparent terminal punctuation (for example an abbreviation). A capitalized
    continuation filling its column is prose even with fewer than eight words;
    word count alone does not identify a heading. Headings,
    reference entries and indented new paragraphs are not continuations. A colon
    followed by list markers, or successive list items, instead waits for the
    last contiguous list block. At the
    page's top, use the preceding page's last ordinary block as the predecessor;
    a panel continuing from that page is not ordinary prose.

    Move only the panel, keeping its children together and all other text in its
    original sequence. Stop at the first paragraph boundary: a sentence ending
    followed by a first-line indent or an enlarged line gap, or a complete block.
    If that boundary is inside a block, expose two derived blocks with unchanged
    run membership, geometry and classification. Do not move to a block's end
    when its last sentence is itself unfinished. If no safe boundary exists on
    this page, leave the panel in place; crossing page ownership is an exporter
    concern. Rule-4 floats here are unread geometric occupants, not flow items;
    their placement in exported prose is likewise owned by the exporter.

    Captioned lists use the same atomic boundary as panels; captions outside
    main text are retained in their group's metadata for the exporter.
    Each moved group records its original and final paper-wide order and why.
    Return the ordered blocks and any paragraph splits for the page record.
    """
    if not panels: return ordered, []
    owner = {bid: p for p in panels for bid in p["blocks"]}
    units = []; seen = set(); original = {}
    for i, b in enumerate(ordered):
        panel = owner.get(b["id"])
        if panel:
            if panel["id"] in seen: continue
            seen.add(panel["id"]); original[panel["id"]] = order_start + i + 1
            units.append({"panel": panel, "blocks": [m for m in ordered if m["id"] in panel["blocks"]]})
        else: units.append({"blocks": [b]})

    def sentence_end(text):
        # Citations may follow the stop, either bracketed or flattened superscripts.
        text = re.sub(r"(?:\s*\[\d[\d,;\s–—-]*\]|(?<=[.!?])\d[\d,–—-]*)\s*$", "", text.rstrip())
        return bool(re.search(r"[.!?][\"'’”\)\]]*\s*$", text))

    def row_text(row): return " ".join(e["text"] for e in row)
    def list_text(text): return bool(re.match(r"^\s*(?:[-•●◦]|\d{1,2}[.)]|[a-z][.)])\s", text))
    def list_continues(before, after):
        return list_text(after) and (before.rstrip().endswith(":") or list_text(before))
    def hull(boxes): return [min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes)]

    def continues(before, b):
        text = text_of(b).strip(); rows = rows_of(b)
        if not before or not text or b.get("in_refs") or b.get("labels"): return False
        if list_continues(before, text): return True
        if len(rows) < 2: return False
        if len(re.findall(r"\w+", before)) < 8 or b.get("size", body) > 1.12 * body: return False
        first = row_text(rows[0]).lstrip("\"'‘“(")
        # A short standalone heading and a first-line indent both start a new paragraph.
        lower = bool(first and first[0].islower())
        first_box = hull([e["box_px"] for e in rows[0]])
        short = len(first.split()) < 8 and first_box[2] - first_box[0] < .8 * (b["box_px"][2] - b["box_px"][0])
        if not lower and (short or first_box[0] > b["box_px"][0] + .5 * body): return False
        return lower or not sentence_end(before)

    def paragraph_cut(b):
        rows = rows_of(b)
        if len(rows) < 2 or b.get("in_refs") or b.get("labels"): return None
        boxes = [hull([e["box_px"] for e in row]) for row in rows]
        gaps = [max(0, z[1] - a[3]) for a, z in zip(boxes, boxes[1:])]
        gap = max(.6 * body, 1.6 * statistics.median(gaps))
        for i in range(1, len(rows)):
            indent = boxes[i][0] - b["box_px"][0]
            first = row_text(rows[i]).lstrip("\"'‘“(")
            if (sentence_end(row_text(rows[i - 1])) and first and first[0].isupper() and
                (.5 * body < indent < .25 * (b["box_px"][2] - b["box_px"][0]) or gaps[i - 1] > gap)):
                return rows[:i], rows[i:]
        return None

    splits = []; moved = []
    for panel in sorted(panels, key=lambda p: original.get(p["id"], 0)):
        if panel["id"] in moved: continue
        i = next((i for i, u in enumerate(units) if u.get("panel") is panel), None)
        if i is None: continue
        # Panels already moved to this boundary do not become the prose predecessor.
        before = next((text_of(u["blocks"][-1]) for u in reversed(units[:i]) if "panel" not in u), previous_text)
        j = i + 1
        while j < len(units) and "panel" in units[j]: j += 1
        if j == len(units) or not continues(before, units[j]["blocks"][0]): continue
        group_end = j
        noun = "captioned list" if panel.get("kind") == "table" else "panel"
        list_flow = list_continues(before, text_of(units[j]["blocks"][0]))
        reason = ("preceding page's paragraph continues below the " + noun if not any("panel" not in u for u in units[:i])
                  else "preceding paragraph continues after the " + noun)
        if list_flow: reason = "introduced list continues after the " + noun
        target = None; cut = None
        while j < len(units):
            if "panel" in units[j]: j += 1; continue
            b = units[j]["blocks"][0]
            cut = paragraph_cut(b)
            if list_flow:
                following = next((u["blocks"][0] for u in units[j + 1:] if "panel" not in u), None)
                if cut or following is None or not list_text(text_of(following)):
                    target = j; break
                j += 1; continue
            if cut or sentence_end(text_of(b)): target = j; break
            following = next((u["blocks"][0] for u in units[j + 1:] if "panel" not in u), None)
            if following is None or not continues(text_of(b), following): break
            j += 1
        if target is None: continue
        if cut:
            b = units[target]["blocks"][0]; parts = []
            for k, rows in enumerate(cut, 1):
                es = [e for row in rows for e in row]
                part = dict(b, id=b["id"] + f":paragraph:{k}", members=[e["id"] for e in es],
                            box_px=hull([e["box_px"] for e in es]), lines=len(rows),
                            text="\n".join(row_text(row) for row in rows), main_text_source=b["id"])
                parts.append(part)
            units[target:target + 1] = [{"blocks": [b]} for b in parts]
            splits.append({"source": b["id"], "parts": [p["id"] for p in parts], "runs": [],
                           "why": "paragraph boundary for a deferred " + noun})
        group = units[i:group_end]; del units[i:group_end]; target -= len(group)
        # Multiple panels sharing a destination keep their original relative order.
        while target + 1 < len(units) and units[target + 1].get("panel", {}).get("id") in moved: target += 1
        units[target + 1:target + 1] = group
        for unit in group:
            member = unit["panel"]; moved.append(member["id"])
            member["move"] = {"id": member["id"], "from_order": original[member["id"]], "why": reason}
    result = [b for u in units for b in u["blocks"]]
    positions = {b["id"]: order_start + i + 1 for i, b in enumerate(result)}
    for p in panels:
        if p["id"] in moved: p["move"]["to_order"] = min(positions[bid] for bid in p["blocks"])
    return result, splits

def page_top_check(page):
    """Audit rule 6's header exclusions, also on older saved page records.

    Measure the gap from upright header furniture to the first main block.
    Group band-excluded runs by their furniture block so split font runs or
    short wrapped lines still count toward the five-word warning. Rotated
    sidebars and footer furniture cannot supply header evidence. No header or
    no main block gives a null gap, not a fabricated zero or a warning.
    """
    mt = page.get("main_text") or {}; body = mt.get("body_size_px") or 0
    runs = {e["id"]: e for e in page.get("elements", []) if e["kind"] == "text"}
    height = page["region_box_px"][3]
    header = [f for f in mt.get("furniture", [])
              if f["box_px"][3] < PARAMS["band_edge_share"] * height
              and all(runs[m]["angle"] == 0 for m in f["members"] if m in runs)]
    bottom = max((f["box_px"][3] for f in header), default=None)
    first = min((b["box_px"][1] for b in mt.get("blocks", []) if b["cls"] == "main"), default=None)
    band_ids = {m for f in header if f.get("why") == "inside the recurring header band" for m in f["members"]}
    source = {b["id"]: b for b in page.get("blocks", [])}
    evidence = []; seen = set()
    groups = [(b["id"], source.get(b["id"], {}).get("members", []))
              for b in mt.get("blocks", []) if b["cls"] == "furniture"]
    groups += [(None, f["members"]) for f in header]
    for bid, members in groups:
        es = [runs[m] for m in members if m in band_ids and m not in seen and m in runs
              and runs[m].get("run_size_px", runs[m]["size_px"]) >= (1 - PARAMS["body_size_tolerance"]) * body]
        text = " ".join(e["text"] for e in es)
        if len(text.split()) < 5: continue
        seen.update(e["id"] for e in es)
        evidence.append({"block": bid, "members": [e["id"] for e in es], "text": text,
                         "why": "inside the recurring header band"})
    return {"lowest_header_bottom_px": bottom, "first_main_top_px": first,
            "gap_px": round(first - bottom, 3) if first is not None and bottom is not None else None,
            "flag": "page top may be dropped" if evidence else None, "evidence": evidence}


def citation_box_runs(page):
    """A drawn publisher citation box owns its lines, including its year/DOI.

    Require the citation heading and an enclosing drawing in the original
    block. A nearby running footer outside that drawing is not protected.
    """
    elements = {e['id']: e for e in page['elements']}
    protected = set()
    for block in page['blocks']:
        if block.get('main_text_source'): continue
        members = [elements[m] for m in block['members'] if m in elements]
        text = [e for e in members if e['kind'] == 'text' and e.get('angle', 0) == 0]
        if not any(re.match(r'^\s*How to cite\b', e['text'], re.I) for e in text): continue
        for drawing in members:
            if drawing['kind'] not in ('fill', 'path'): continue
            b = drawing['box_px']
            enclosed = [e for e in text if b[0]-1 <= e['box_px'][0] and e['box_px'][2] <= b[2]+1
                        and b[1]-1 <= e['box_px'][1] and e['box_px'][3] <= b[3]+1]
            if (len({e['line'] for e in enclosed}) >= 2
                    and any(re.match(r'^\s*How to cite\b', e['text'], re.I) for e in enclosed)):
                protected.update(e['id'] for e in enclosed)
    return protected


# Port: paper-float-mapper/floatmapper/witness.py::{assign, accounting,
# edge_crossings}, F-006/F-007/F-008. The adapter enumerates boxer text runs,
# uses explicit table membership as the structure nomination, and refuses
# competing owners or edge crossings. It never enlarges a detected region.
def ownership_contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def ownership_edge_crossings(box, bounds):
    result = []
    for side, dim, lower in [('top',1,True),('left',0,True),('right',0,False),('bottom',1,False)]:
        edge = box[dim if lower else dim+2]; other = 1-dim
        if bounds[dim] < edge < bounds[dim+2] and bounds[other] < box[other+2] and bounds[other+2] > box[other]:
            result.append(dict(side=side, extent_px=edge-bounds[dim] if lower else bounds[dim+2]-edge,
                               basis='Strict straddling with positive orthogonal overlap; zero tolerance'))
    return result


def ownership_assign(obj, nominations):
    if len(nominations) != 1:
        return dict(role='unassigned', reason='no unique explicit table owner', links=[t['id'] for t in nominations])
    t = nominations[0]
    if not ownership_contains(t['box_px'], obj['box_px']):
        return dict(role='unassigned', reason='object crosses table edge; region not enlarged', links=[t['id']])
    if obj['id'] not in t['members']:
        return dict(role='unassigned', reason='inside region without a structure nomination', links=[t['id']])
    return dict(role='structure', reason='explicit member contained by one table', links=[t['id']])


def ownership_accounting(objects):
    counts = collections.Counter(o['assignment']['role'] for o in objects)
    ids = collections.Counter(o['id'] for o in objects)
    return dict(enumerated=len(objects), accounted=sum(counts.values()),
                assigned=sum(v for k,v in counts.items() if k != 'unassigned'),
                by_assignment=dict(counts), unaccounted=len(objects)-sum(counts.values()),
                duplicate_ids=sorted(k for k,v in ids.items() if v > 1),
                edge_crossing_objects=sum(bool(o['edge_crossings']) for o in objects))


# Port: paper-float-mapper/floatmapper/table_layout.py::note_marker.
# This is a role hint inside an already owned table, never a region detector.
def ownership_note_marker(text):
    return bool(re.match(r'^\s*(?:notes?[\s.:]|abbreviations[\s.:]|[*†‡])', text, re.I))


def ownership_rows(members, runs):
    rows = collections.defaultdict(list)
    for m in members:
        if m in runs: rows[(runs[m].get('angle',0), runs[m]['line'])].append(runs[m])
    return [sorted(row,key=lambda e:e['box_px'][0]) for row in
            sorted(rows.values(),key=lambda row:min(e['box_px'][1] for e in row))]


def sort_main_ownership(page, blocks, ordered, body, front=False):
    """Finalize rule-6 ownership without deleting text or guessing table extents.

    Smaller main boxes made entirely of one table's contained members belong
    to that table. Body-sized prose, crossing boxes, overlapping tables and
    unclaimed interior runs remain main with an explicit review flag. Every
    intersecting text run has one accounting record, including unassigned.
    An unpaired table caption with at least three aligned shading bands and
    six continuous smaller-type rows can nominate its fixed drawn region;
    this supplies ownership only, not a new table grid or a widened extent.
    Footnote suffixes become other/footnote blocks. Front-page contact panels
    and explicitly labelled metadata become other/header (D-637), not body.
    A key-word block, or a header block read after an abstract, records the
    block read just before it (header_after): the copy keeps that printed place.
    A detached inline run inside a multirow main box witnesses a row split:
    join just that baseline, retain the surrounding rows as separate boxes.
    No cut is made below the top of another unabsorbed main block inside the
    host box, so a split never lets that block fall between the parts.
    Original boxes and source memberships remain available for paper replay.
    """
    runs = {e['id']:e for e in page['elements'] if e['kind']=='text'}
    tables = list(page.get('tables',[])); objects = []; roles = {}; splits = []; regions = []
    def hull(es):
        bs = [e['box_px'] for e in es]
        return [min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)]
    def row_text(row): return ' '.join(e['text'].strip() for e in row)
    # A missed single-column table can still have an explicit caption and
    # repeated drawn row bands. Those fixed bands nominate an ownership
    # region, without inventing a grid or enlarging any detected table.
    # Require three aligned bands, six small-type rows, continuous row pitch,
    # and no body-sized ink inside. A shaded prose panel cannot satisfy this.
    for cap in page.get('unpaired',[]):
        if not re.match(r'^Table\s+\d+',cap.get('caption',''),re.I): continue
        cb=cap['box_px']
        bands=[e for e in page['elements'] if e['kind']=='fill'
               and abs(e['box_px'][0]-cb[0])<.5*body
               and cb[3]<=e['box_px'][1]
               and body<e['box_px'][3]-e['box_px'][1]<6*body
               and e['box_px'][2]>=cb[2] and e['box_px'][2]-cb[0]>8*body]
        if not bands: continue
        first=min(bands,key=lambda e:e['box_px'][1]);fb=first['box_px']
        if fb[1]-cb[3]>3*body: continue
        bands=[e for e in bands if abs(e['box_px'][2]-fb[2])<.2*body]
        if len(bands)<3: continue
        region=hull(bands)
        if any(min(region[2],t['box_px'][2])>max(region[0],t['box_px'][0])
               and min(region[3],t['box_px'][3])>max(region[1],t['box_px'][1])
               for t in tables+page.get('floats',[])): continue
        cells=[e for e in runs.values() if ownership_contains(region,e['box_px'])]
        if not cells or any(e.get('angle',0) or e.get('run_size_px',e['size_px'])>.98*body for e in cells): continue
        rows=ownership_rows([e['id'] for e in cells],runs)
        if len(rows)<6 or any(hull(b)[1]-hull(a)[3]>3*body for a,b in zip(rows,rows[1:])): continue
        t=dict(id='table-region:'+cap['block'],box_px=region,members=[e['id'] for e in cells],
               caption_block=cap['block'],bands=[e['id'] for e in bands],
               why='explicit table caption above repeated aligned row fills')
        regions.append(t);tables.append(t)
        for b in blocks:
            bb=b['box_px']
            if (b['cls']=='main' and b['lines']==1 and abs(bb[1]-cb[1])<.3*body
                    and cb[2]<=bb[0] and bb[2]<=region[2] and b['size']<=1.1*body):
                roles[b['id']]=('table',t['id'])
    for e in runs.values():
        eb=e['box_px']
        hits=[t for t in tables if min(eb[2],t['box_px'][2])>max(eb[0],t['box_px'][0])
              and min(eb[3],t['box_px'][3])>max(eb[1],t['box_px'][1])]
        if not hits: continue
        assignment=ownership_assign(e,hits)
        crossings=[dict(table=t['id'],**c) for t in hits for c in ownership_edge_crossings(t['box_px'],eb)]
        objects.append(dict(id=e['id'],assignment=assignment,edge_crossings=crossings))
    assigned={o['id']:o['assignment'] for o in objects}
    # A small cell block can include a missed spanning header or note run.
    # Its existing majority membership nominates those remaining runs only
    # inside the SAME unchanged region. A crossing run still fails closed.
    for b in blocks:
        ms=[m for m in b['members'] if m in runs]
        if b['cls']!='main' or not ms or b['size']>.95*body: continue
        owners=[t for t in tables if sum(m in t['members'] for m in ms)>=max(1,len(ms)/2)
                and all(ownership_contains(t['box_px'],runs[m]['box_px']) for m in ms)]
        if len(owners)!=1: continue
        t=owners[0]
        if any(len(assigned.get(m,{}).get('links',[]))!=1 for m in ms): continue
        for m in ms:
            assigned[m].update(role='structure',reason='contained cell block with majority explicit table membership')
    for b in blocks:
        if b['cls']!='main': continue
        ms=[m for m in b['members'] if m in runs]
        claims=[assigned[m] for m in ms if m in assigned]
        if not claims:
            # A detector can start below its header/first row. Do not expand
            # that region to take nearby small text: expose the possible
            # missing part, leaving its source words and class untouched.
            bb=b['box_px']
            if b['size']<=.95*body and any(t['box_px'][0]<=bb[0] and bb[2]<=t['box_px'][2]
                    and 0<=t['box_px'][1]-bb[3]<=6*body for t in tables):
                b.setdefault('ownership_flags',[]).append('small text above table extent; possible unowned header or row')
            continue
        owner={a['links'][0] for a in claims if a['role']=='structure'}
        if (len(claims)==len(ms) and all(a['role']=='structure' for a in claims) and len(owner)==1
                and b['size'] <= .95*body):
            roles[b['id']]=('table',next(iter(owner)))
        else:
            b.setdefault('ownership_flags',[]).append('main text intersects table; ownership unresolved')
    excluded={m for t in tables for m in t['members']}
    notes=column_footnotes(blocks,page['elements'],body,page['region_box_px'][3],excluded)
    note_members={m for n in notes for m in n['members']}
    # D-637: correspondence/funding/equal contribution belong to the author
    # header; licence/editor/dates are furniture. Retain their words in other
    # with an explicit role, so the copier's article-information policy decides
    # presentation without losing a mixed author/furniture panel.
    labels=re.compile(r'^(?:Correspond(?:ence|ing author)|E-?mail\s*:|Tel(?:ephone)?\s*:|Fax\s*:|Key\s*words\b|'
                      r'Funding(?: information)?\s*:|Received\s*:?\s*(?:\d|[A-Z][a-z]+ \d)|'
                      r'Accepted(?: for publication)?\s*:?\s*(?:\d|[A-Z][a-z]+ \d)|'
                      r'Revised\s*:?\s*(?:\d|[A-Z][a-z]+ \d)|Academic Editor\s*:|Editor\s*:|'
                      r'Copyright\b|©|This is an open.access article)',re.I)
    if front:
        # A key-word block that rule 7 read in the body, or a header block read
        # after an abstract, records the block read just before it, so the
        # copier keeps the printed sequence (e.g. abstract, then key words)
        # instead of hoisting the words above it (X07, Y11: unlabelled abstracts).
        abstract_like=lambda a: bool(a.get('abstract') or a.get('side_abstract') or a.get('abstract_continuation')
                                     or re.match(r'^(?:Abstract|Summary)\b',a.get('text',''),re.I))
        previous={b['id']:(a,ordered[:i+1]) for i,(a,b) in enumerate(zip(ordered,ordered[1:]))}
        saved={}
        for b in blocks:
            if b['cls'] not in ('main','other'): continue
            rows=ownership_rows(b['members'],runs); texts=[row_text(row) for row in rows]
            if not texts: continue
            contact=(b['size'] < .9*body and any(re.match(r'^(?:E-?mail|Tel|Fax)\s*:',t,re.I) for t in texts)
                     and any(re.search(r'\b(?:Department|University|Hospital|Institute|College)\b',t) for t in texts)
                     and not re.match(r'^(?:Abstract|Summary|Background|Objectives?|Methods|Results|Conclusions?)\b',texts[0],re.I))
            if contact or labels.match(texts[0]):
                roles[b['id']]=('header',None)
                b['header_from_body'] = b['cls']=='main' or bool(b.get('abstract') or b.get('side_abstract'))
                a,before=previous.get(b['id'],(None,[]))
                if (b['cls']=='main' and a is not None and a['id'] not in roles and
                        (any(map(abstract_like,before)) or re.match(r'^Key\s*words\b',texts[0],re.I))):
                    b['header_after']=a['id']
                saved[b['id']]={key:b.pop(key) for key in ('abstract','side_abstract','abstract_continuation') if key in b}
        # A standalone keyword label owns its immediately following small
        # comma/semicolon list, provided there is one unambiguous aligned box.
        # Without one the label stays where it was, with its words (a label
        # never leaves its list behind; measured on M10, body-size words).
        for b in blocks:
            if roles.get(b['id'],(None,))[0]!='header' or not re.fullmatch(r'Key\s*words\s*:?\s*',b['text'],re.I): continue
            bb=b['box_px']
            candidates=[a for a in blocks if a is not b and a['cls']=='main' and a['lines']<=3
                        and a['size']<=.95*body and abs(a['box_px'][0]-bb[0])<body
                        and 0<=a['box_px'][1]-bb[3]<=2*body and re.search(r'[,;]',a['text'])
                        and not re.search(r'[.!?]\s+[A-Z]',a['text'])]
            if len(candidates)==1:
                a=candidates[0];roles[a['id']]=('header',None)
                a.update(header_from_body=True,header_group=b['id'])
                if b.get('header_after'): a['header_after']=b['header_after']
            else:
                del roles[b['id']]
                for key in ('header_from_body','header_after'): b.pop(key,None)
                b.update(saved.get(b['id'],{}))
    def part(b, ms, suffix, role=None, owner=None):
        es=[runs[m] for m in ms]; rows=ownership_rows(ms,runs)
        bb=dict(b,id=b['id']+':'+suffix,members=ms,box_px=hull(es),lines=len(rows),
                text='\n'.join(row_text(r) for r in rows),main_text_source=b['id'])
        if role: bb.update(cls='caption' if role=='table' else 'other',role=role,owner=owner,
                           why='owned '+role+'; excluded from body order',order=None)
        page['blocks'].append(dict(id=bb['id'],members=ms,box_px=bb['box_px'],text=bb['text'],
                                   text_lines=bb['lines'],kinds=['text'],main_text_source=b['id']))
        return bb
    replacement={}
    for b in blocks:
        ms=[m for m in b['members'] if m in runs]
        if b['id'] in roles:
            role,owner=roles[b['id']]
            b.update(cls='caption' if role=='table' else 'other',role=role,owner=owner,
                     why='owned '+role+'; excluded from body order',order=None)
        elif any(m in note_members for m in ms):
            keep=[m for m in ms if m not in note_members]; foot=[m for m in ms if m in note_members]
            if keep:
                replacement[b['id']]=[part(b,keep,'body'),part(b,foot,'note','footnote')]
                splits.append(dict(source=b['id'],parts=[p['id'] for p in replacement[b['id']]],
                                   why='column-foot note separated by its own rows'))
            else: b.update(cls='other',role='footnote',why='small marker-led column-foot note',order=None)
    if replacement:
        blocks=[p for b in blocks for p in replacement.get(b['id'],[b])]
        ordered=[p for b in ordered for p in replacement.get(b['id'],[b])]
    # A baseline neighbour is evidence for an inline fragment, not for a new
    # column. Require a unique host, same size, disjoint ink and a short gap.
    inline={}; consumed=set()
    for b in blocks:
        if b['cls']!='main' or b['lines']!=1 or b.get('in_refs'): continue
        br=ownership_rows(b['members'],runs)
        if not br or any(e.get('angle',0) for e in br[0]): continue
        bb=b['box_px']; hits=[]
        for a in blocks:
            if a is b or a['cls']!='main' or a['lines']<3 or a.get('in_refs'): continue
            ab=a['box_px']
            if not ownership_contains(ab,bb) or abs(a['size']-b['size'])>.1*body: continue
            rows=ownership_rows(a['members'],runs)
            for i,row in enumerate(rows):
                rb=hull(row)
                if (abs(rb[1]-bb[1])<.25*body and abs(rb[3]-bb[3])<.4*body
                    and 0<=bb[0]-rb[2]<=4*body): hits.append((a,i))
        if len(hits)==1:
            a,i=hits[0]; inline.setdefault(a['id'],{}).setdefault(i,[]).append(b);consumed.add(b['id'])
    replacement={}
    for b in blocks:
        if b['id'] not in inline: continue
        rows=ownership_rows(b['members'],runs); chunks=[]; pending=[]; top=None
        # A cut must not let another, unabsorbed main block inside the host's
        # box fall between two parts: below such a block's top, rows stay with
        # the part above (measured on PLOS pone.0002780 p13, Table S4).
        holes=[a['box_px'][1] for a in blocks if a is not b and a['cls']=='main'
               and a['id'] not in consumed and ownership_contains(b['box_px'],a['box_px'])]
        for i,row in enumerate(rows):
            ids=[e['id'] for e in row]; y=hull(row)[1]
            if top is None: top=y
            if i not in inline[b['id']]: pending.extend(ids); continue
            fragment=[m for q in inline[b['id']][i] for m in q['members'] if m in runs]
            if pending and any(top < h < y for h in holes):
                pending.extend(ids+fragment); continue
            if pending: chunks.append(pending)
            # Keep following rows with their new opening, including short
            # wrapped URL tails. The cut precedes the repaired baseline.
            pending=ids+fragment; top=y
        if pending: chunks.append(pending)
        replacement[b['id']]=[part(b,ms,'row'+str(i+1)) for i,ms in enumerate(chunks)]
        splits.append(dict(source=b['id'],parts=[p['id'] for p in replacement[b['id']]],
                           absorbed=[q['id'] for qs in inline[b['id']].values() for q in qs],
                           why='detached inline fragment; split host at shared baseline'))
    if replacement:
        blocks=[p for b in blocks if b['id'] not in consumed for p in replacement.get(b['id'],[b])]
        ordered=[p for b in ordered if b['id'] not in consumed for p in replacement.get(b['id'],[b])]
    retained=[b for b in ordered if b['cls']!='main']
    ordered=[b for b in ordered if b['cls']=='main']
    for o in objects:
        e=runs[o['id']]
        if o['assignment']['role']=='structure' and ownership_note_marker(e['text']):
            o['assignment']['role']='note'
    return blocks,ordered,dict(schema='body-ownership/2',objects=objects,
                              accounting=ownership_accounting(objects),regions=regions),notes,splits,retained


SENTENCE_BREAK = re.compile(r'[.!?]["\u201d\u2019)\]]*\s+(?=["\u201c\u2018(]?[A-Z])')

def pull_quote_groups(runs, drawn, body_face):
    """Pull quotes on a page -> list of sets of run ids (lane r3-pullquote).

    A pull quote repeats a sentence of the article in a display face beside the body text, which runs
    around it, inside one column or straddling the gutter between two (AO05 p1; British Dental Journal
    opinion pages, Nature news-feature inset quotes); read as body text it prints as a paragraph, inside
    a sentence, or woven into a column. The test starts from the frame:
      - a frame is a drawn fill, or a pair of horizontal rules of one width (ends within 1 em) one above
        the other, between 2 and frame_reach_em letter heights apart; its inside is the fill, or the band
        between the rules over their common width;
      - the upright text runs standing inside it (within its width, centred between its top and bottom; a
        line of a column that crosses its edge is not inside) span two or more lines and are all set in
        one face that is not the paper's body face, at the body's size or larger (the page's median run
        size, within body_size_tolerance; AQ17 p3's boxed notice in smaller type is a side box);
      - its text is one sentence of at most pull_quote_max_words words: no sentence end inside it followed by
        a capital (measured over the lane's cases: every pull quote 6-29 words and one sentence; every framed
        panel of the article with text beside it, the abstract panel with runaround and the wrapped key-points
        box included, two sentences or more);
      - body-face runs outside it stand level with it within 2 em of one of its sides (measured from the
        frame, not from the quote's widest line), and the body text runs around it: within
        runaround_reach_em letter heights above or below the frame a body-face line of that same column
        reaches over the frame's width (more than 1 em) with the same far edge as a line beside it (within
        1 em). The column narrows beside a pull quote; a panel of the article (an abstract panel, a
        Clinical Relevance or Key Points panel between rules, a summary box, a boxed notice) fills its
        own column or the page width, and the text beside it, if any, is the next column, which never
        reaches over the panel.
    drawn: the page's rule and fill elements, its art included (a rule pair outside every float is art).
    A boxed note in the body face, a caption or heading in another face with no body text beside its
    frame, and display text alone on its page are not pull quotes."""
    ups = [e for e in runs if e.get("kind") == "text" and not round(e.get("angle", 0)) % 360 and e["text"].strip()]
    if not ups: return []
    size = statistics.median(e.get("run_size_px", e["size_px"]) for e in ups)
    hr = [o["box_px"] for o in drawn if o.get("kind") == "rule" and o["box_px"][2] - o["box_px"][0] > o["box_px"][3] - o["box_px"][1]]
    frames = [o["box_px"] for o in drawn if o.get("kind") == "fill" and not o.get("overlay")]
    for a in hr:
        for c in hr:
            if c is a or abs(a[0] - c[0]) > size or abs(a[2] - c[2]) > size: continue
            if 2 * size <= c[1] - a[3] <= PARAMS["frame_reach_em"] * size:
                frames.append([max(a[0], c[0]), a[3], min(a[2], c[2]), c[1]])
    def centre(e): return ((e["box_px"][0] + e["box_px"][2]) / 2, (e["box_px"][1] + e["box_px"][3]) / 2)
    found = []
    for f in frames:
        inside = [e for e in ups if f[0] - 3 <= e["box_px"][0] and e["box_px"][2] <= f[2] + 3 and f[1] <= centre(e)[1] <= f[3]]
        if len({e["line"] for e in inside}) < 2: continue
        faces = {run_face(e) for e in inside}
        if len(faces) != 1 or None in faces or body_face in faces: continue
        # display type: at the body's size or larger (a boxed notice in smaller type is a side box, not a quote)
        if statistics.median(e.get("run_size_px", e["size_px"]) for e in inside) < (1 - PARAMS["body_size_tolerance"]) * size: continue
        # one sentence: a pull quote repeats a sentence of the article; an abstract, a key-points or relevance
        # panel, a summary or a notice holds several (a sentence end inside it, followed by a capital, parts them)
        said = " ".join(e["text"].strip() for e in sorted(inside, key=lambda e: (e["box_px"][1], e["box_px"][0])))
        if len(said.split()) > PARAMS["pull_quote_max_words"] or SENTENCE_BREAK.search(said): continue
        ids = {e["id"] for e in inside}
        beside = [e for e in ups if e["id"] not in ids and run_face(e) == body_face
                  and min(e["box_px"][3], f[3]) - max(e["box_px"][1], f[1]) > 0
                  and (-size <= e["box_px"][0] - f[2] <= 2 * size or -size <= f[0] - e["box_px"][2] <= 2 * size)]
        # runaround: the column beside it is wider above or below the frame, its lines reaching over the
        # frame's width with the same far edge (the column narrows beside the quote). A panel that fills its
        # own column has only the next column beside it, which never reaches over the panel.
        level = [e for e in ups if e["id"] not in ids and run_face(e) == body_face
                 and (0 <= f[1] - e["box_px"][3] <= PARAMS["runaround_reach_em"] * size or 0 <= e["box_px"][1] - f[3] <= PARAMS["runaround_reach_em"] * size)
                 and min(e["box_px"][2], f[2]) - max(e["box_px"][0], f[0]) > size]
        def around(b):
            right = b["box_px"][0] >= (f[0] + f[2]) / 2
            return any(abs(w["box_px"][2] - b["box_px"][2]) <= size if right else abs(w["box_px"][0] - b["box_px"][0]) <= size for w in level)
        if any(around(e) for e in beside) and ids not in found: found.append(ids)
    return found

# lane r5-wrap: text on both sides of a picture (rules O32, O33, O34 of the round-5 rules)
WRAP_OPTIONS = ("across: read each row's left piece, then its right piece", "down: read the left side down, then the right side")


def wrap_vocabulary(pages_runs):
    """the paper's words (three or more letters, lower case) with their counts: a hyphen join that makes one of them is
    a witness that the two pieces belong together (O33)"""
    v = collections.Counter()
    for runs in pages_runs:
        for e in runs:
            for w in re.findall(r"[^\W\d_]{3,}", e.get("text", "").lower()): v[w] += 1
    return v


def wrap_continues(a, b, vocab):
    """O33 evidence that piece text b continues piece text a: 2 or 1 for, -1 against, 0 none.  A hyphen end followed by
    a small letter is for (twice when the joined word is a word of the paper), by a capital against; an open sentence
    followed by a capital is against; a closed sentence followed by a capital is for, by a small letter against."""
    a, b = a.strip(), b.strip()
    if not a or not b: return 0
    m = re.match(r"[\"'(\[“‘]?([^\W\d_]+)", b)
    first = m.group(1) if m else ""
    lower, upper = first[:1].islower(), first[:1].isupper()
    frag = re.search(r"([^\W\d_]+)[-­]$", a)
    if frag:
        if upper: return -1
        if lower: return 2 if vocab.get((frag.group(1) + first).lower(), 0) else 1
        return 0
    t = re.sub(r"(?:[\s,–\-]*(?:\[[\d,\s–\-]+\]|\(\d[\d,\s–\-]*\)|\d{1,3}(?:[,–\-]\d{1,3})*))+$", "", a) \
        if re.search(r"[.!?:]", a[-12:]) else a
    closed = t.rstrip("\"')]”’*†‡§ ").endswith((".", "?", "!", ":"))
    if not closed: return -1 if upper else 0
    return 1 if upper else (-1 if lower else 0)


def wrap_direction(rows, left, vocab):
    """O33: for each left piece with a left piece below it on the next row of the wrap: does it continue in that piece
    (down) or in the right piece of its own row (across)?  Most deciding rows, two or more, settle the order; otherwise
    it is unclear (O34).  rows: [(left text, right text, top)], left: [(text, top)] of every left piece, top to bottom."""
    vd = va = 0
    tops = [r[2] for r in rows]
    for lt, rt, top in rows:
        below = next((t for t, y in left if y > top), None)
        nxt = next((y for t, y in left if y > top), None)
        if below is None or nxt not in tops: continue
        d, a = wrap_continues(lt, below, vocab), wrap_continues(lt, rt, vocab)
        if d > a: vd += 1
        elif a > d: va += 1
    n = vd + va
    if n >= 2 and vd > n / 2: return "down", vd, va
    if n >= 2 and va > n / 2: return "across", vd, va
    return "unclear", vd, va


def wrap_places(runs, pictures, body, tol, block_of=None, gutters=()):
    """O32: a picture with body text on its left and on its right at the same heights (two or more rows), inside one
    band.  runs: the page's upright main-text runs; pictures: boxes of drawn objects and floats.  Rows beside the
    picture overlap its height by half a row, or its runaround margin (one letter height above and below).  A row's left piece is
    its runs left of the picture nearest to it (a gap over 2.5 letter heights, or a run of another block, parts it from
    another column's text),
    ending within three letter heights of the picture or starting on the left edge of the pieces that do (a paragraph's
    last line); its right piece the runs right of the picture, starting within three letter heights of it.  A piece
    with a column gutter of the page (gutters: (left, right) x of each) between it and the picture is the next
    column's text, not beside the picture; a drawn object lying within a gutter is a column rule, not a picture."""
    def size(e): return e.get("run_size_px", e["size_px"])
    body_runs = [e for e in runs if e["angle"] == 0 and e.get("text", "").strip() and abs(size(e) - body) <= 2 * tol * body]
    rows = []
    for e in sorted(body_runs, key=lambda e: (e["box_px"][1] + e["box_px"][3]) / 2):
        cy = (e["box_px"][1] + e["box_px"][3]) / 2; h = max(4.0, e["box_px"][3] - e["box_px"][1])
        if rows and abs(cy - rows[-1]["cy"]) <= 0.45 * max(h, rows[-1]["h"]): rows[-1]["runs"].append(e)
        else: rows.append({"cy": cy, "h": h, "runs": [e]})
    out = []
    mids = [(lo + hi) / 2 for lo, hi in gutters]
    for B in pictures:
        x0, y0, x1, y1 = B
        if any(lo - body <= x0 and x1 <= hi + body for lo, hi in gutters): continue
        pieces = []
        for r in rows:
            top = min(e["box_px"][1] for e in r["runs"]); bot = max(e["box_px"][3] for e in r["runs"])
            core = min(bot, y1) - max(top, y0) > 0.5 * (bot - top)
            # a row within a letter height above or below the picture (its runaround margin) may be split too
            if not core and min(bot, y1 + body) - max(top, y0 - body) <= 0.5 * (bot - top): continue
            rs = sorted(r["runs"], key=lambda e: e["box_px"][0])
            if any(e["box_px"][0] < x0 and e["box_px"][2] > x1 for e in rs):
                if core: pieces = None; break   # a line runs through the picture: no wrap
                continue
            lw = [e for e in rs if (e["box_px"][0] + e["box_px"][2]) / 2 < x0]
            rw = [e for e in rs if (e["box_px"][0] + e["box_px"][2]) / 2 > x1]
            bo = block_of or {}
            for k in range(len(lw) - 1, 0, -1):
                if lw[k]["box_px"][0] - lw[k - 1]["box_px"][2] > 2.5 * body or bo.get(lw[k]["id"]) != bo.get(lw[k - 1]["id"]): lw = lw[k:]; break
            for k in range(1, len(rw)):
                if rw[k]["box_px"][0] - rw[k - 1]["box_px"][2] > 2.5 * body or bo.get(rw[k]["id"]) != bo.get(rw[k - 1]["id"]): rw = rw[:k]; break
            if lw and any(lw[-1]["box_px"][2] < g < x0 for g in mids): lw = []
            if rw and any(x1 < g < rw[0]["box_px"][0] for g in mids): rw = []
            pieces.append((r, lw, rw if rw and rw[0]["box_px"][0] - x1 <= 3 * body else []))
        if not pieces: continue
        near = [lw for _, lw, _ in pieces if lw and x0 - lw[-1]["box_px"][2] <= 3 * body]
        if not near: continue
        edge = sorted(lw[0]["box_px"][0] for lw in near)[len(near) // 2]
        pieces = [(r, lw if lw and (x0 - lw[-1]["box_px"][2] <= 3 * body or abs(lw[0]["box_px"][0] - edge) <= body) else [], rw)
                  for r, lw, rw in pieces]
        both = [(lw, rw) for _, lw, rw in pieces if lw and rw]
        if len(both) < 2: continue
        out.append({"box_px": [round(v, 1) for v in B], "rows": both, "left": [lw for _, lw, _ in pieces if lw],
                    "right": [rw for _, _, rw in pieces if rw]})
    return out


def wrap_pictures(elements, art, floats, frame_w, body):
    """the page's pictures for O32: drawn objects (image, fill, outline, rule; rule 5's journal art too) joined where
    they touch, and floats; a picture is at least two letter heights wide and tall and narrower than nine tenths of the
    text frame; a picture inside another is part of it"""
    boxes = [list(e["box_px"]) for e in list(elements) + list(art) if e.get("kind") in ("image", "fill", "outline", "rule")]
    merged = []
    for b in sorted(boxes, key=lambda b: (b[1], b[0])):
        grown = True
        while grown:
            grown = False
            for o in merged:
                if o[0] - 2 <= b[2] and b[0] <= o[2] + 2 and o[1] - 2 <= b[3] and b[1] <= o[3] + 2:
                    b = [min(b[0], o[0]), min(b[1], o[1]), max(b[2], o[2]), max(b[3], o[3])]; merged.remove(o); grown = True; break
        merged.append(b)
    merged += [list(f["box_px"]) for f in floats]
    pics = [b for b in merged if b[2] - b[0] >= 2 * body and b[3] - b[1] >= 2 * body and b[2] - b[0] < 0.9 * frame_w]
    def inside(a, b): return a is not b and b[0] - 2 <= a[0] and b[1] - 2 <= a[1] and a[2] <= b[2] + 2 and a[3] <= b[3] + 2
    return [a for i, a in enumerate(pics) if not any(inside(a, b) and (a != b or j < i) for j, b in enumerate(pics))]


def main_text(paper_dir, draw=True):
    """Rule 6 (main text): on the float-free, art-free copy of every page, the main text of the
    paper is separated from everything else. The body size is the character-weighted median size
    of all text outside floats. A block mixing furniture lines with other text is
    partitioned into furniture and retained text before block classification;
    each split is recorded. Bands classify lines, never a whole mixed block.
    When a header limit restores an opening, its already-retained remainder
    keeps its fragment identity; the restored opening is a second prose fragment.
    Recovered columns retain their own extents. When recovery exposes different
    layouts separated by a large spanning heading at a clear horizontal gap,
    rule 7 receives column witnesses local to each layout, keeping the recovered
    prose with its section rather than interleaving it with the next section. Derived blocks are rebuilt
    from the original membership on every --paper pass.
    Page furniture is every line whose text, digits masked, recurs at
    one position on furniture_min_pages pages (two for papers under eight pages),
    and on a quarter of the paper's pages at least
    (including alternating left/right running heads, feet, page numbers, margin
    notices). In the top and bottom 15%, an upright line also matches with each
    whole-number prefix or suffix masked by one placeholder, so a folio gaining
    a digit remains the same pattern. Decimal measurements retain their digit
    widths. This extra match never applies to interior data rows.
    Only upright furniture in these bands that overlaps a
    text column on its page sets the header or footer band. The column witnesses
    are the nonrecurring parts of body-size blocks, and substantial sentence-like
    smaller paragraphs after the title page. Margin furniture beside all columns
    never sets a band. A rotated sidebar spanning the page height is furniture
    by itself and cannot set either band. Standalone table continuation labels
    cannot set a band even when they recur. The footer band cannot remove a
    nonrecurring line stacked with the preceding text in the same substantial body block.
    A repeated table heading connected to
    table members in its block is content, not a running head. On each page the
    header band, including its tolerance, stops before the first upright body-
    or heading-size line aligned to a text column's left edge (within its normal
    column_indent_em indent) and fitting its width; a larger spanning heading
    or caption label also stops it. Numbered display headings include detached
    number/divider runs when locating that edge, and restoring their opening
    retains same-size wrapped lines in one reading-order block.
    On the title page masthead lines above the
    largest type cannot supply this limit. Only lines wholly above that limit
    can become furniture by band. Independently, an
    isolated folio, journal/volume citation, DOI/URL, download or copyright notice
    in the outer margin above/below the text frame is furniture on first sight.
    A reference's tightly stacked citation lines or separated pieces on the
    same baseline are not margin evidence, even in different blocks. A
    drawn publisher citation box owns every enclosed line: its journal,
    year and DOI cannot become recurrence, band or first-sight furniture. A
    lone numeric group label between an aligned table header and its first row
    is not a folio. Runs
    sharing a baseline with prose are separated before block classification.
    Standalone Continued/(Continued) labels below a table's last text row or at
    a column foot are furniture, including typographic Unicode variants. Float
    ownership cannot hide these notices: their memberships are removed from
    the exporter view, with the originals saved and restored on another pass.
    In the page's dominant reading frame, consecutive integer columns in the outer margin, with at least twelve
    labels over a third of the page and a median step under two body lines,
    are manuscript line numbers; a proven margin column also covers sparsely
    spaced labels on later pages. Recurrent rotated text with a large footprint
    in both page axes outside the matching table frame is watermark furniture;
    narrow sideways table headings and the page's dominant reading angle are
    preserved. Figure upload dimensions followed by a parenthesized DPI pair
    below an image are furniture too. These local decisions do not set a paper-wide band. Every furniture line's
    text, member ids, box and reason are recorded in main_text.furniture.
    main_text.page_top_check records the lowest upright header furniture,
    first main-block top and their gap (null when either is absent). A furniture
    block with at least five body-size-or-larger words removed by the header
    band flags "page top may be dropped", with its evidence. This diagnostic
    also appears in the paper summary and the copy's uncertainty list.
    A repository wrapper with download/profile counters, no abstract and a
    following article abstract is recorded as repository_cover and furniture.
    It supplies no bands or columns; behind it a picture leaf (under 30 upright words) is
    not the article's first page either. On the first non-cover page the title is the run of lines at the
    largest size, and the author band is the first block stacked below it with every block
    sharing its vertical span, continued down through stacked blocks of the same size; where the
    author lines are set so close under the title that they share its block (a block holding
    title-size text with lines under it), those lines are the authors and no block below is. Rule 1's
    lines run across the page, so the title and author classes go to their own runs only: a title line
    keeps its runs in the title's column (within a letter height of the title's size around its
    title-size runs), an author line the runs of the author band, and a sidebar sharing their lines is
    split off and is front matter (other), never main text. Where the authors are set in a sidebar beside the title (a block of two or more lines
    sharing the title's vertical span, beside it, larger than the body), that block is the author band.
    The text
    columns of a page are the sideways extents of its blocks of column_min_lines or more lines at
    the body size or larger, merged when two extents overlap by half of the wider; after the
    title page the paper's columns count too (the extents recurring on two or more pages), so a
    references column or a references page has its columns. A block belongs to the narrowest column holding half its
    width. On the title page nothing above the title is main text. A block is main text when it lies in a column and is at the body
    size or larger, or is smaller but directly stacked (flow_gap_em) under main text in its
    column, or opens a column whose preceding column's main text reached its bottom, once the
    paper's first body-size block has been seen; so the references and back matter come in.
    A smaller sentence-like block of ten or more lines also continues a main block
    or a heading in its column, including a heading at its own start, without the
    short-gap restriction. Its why is "smaller section in the flow". Such paragraphs
    may establish narrower columns inside the known text frame. Captions, table
    members/notes, marked footnotes and text below a full-width rule at the column
    foot cannot supply this evidence. The
    reference list comes in whole: from a block whose first line is a references heading
    ("References", "Bibliography", "Literature cited", "Works cited", numbered or not,
    or a list of included/excluded articles or studies), every block after it in rule 7's
    bands and columns is main text whatever its size or gap. Earlier column text on
    that page is body, also whatever its size. A body heading (Acknowledgement,
    Conclusions, Appendix) resumes body text; another bibliography heading resumes
    references. The in_refs field records this state for exporters. A short styled
    heading directly above main text in its column is main even at a smaller size; a line in
    fake small capitals (lead_size_px) is measured at its first letter's size, and a short styled
    heading directly above body text kept outside the furniture band (that column's only
    witness), nothing between them, opens that column (lane r3-headband).
    A narrow block directly left of a
    reference block of its size is that entry's hanging number and rides with it. The abstract
    comes in whole too: before the paper's first body-size block, a block outside the main
    text whose first line opens with "Abstract" or "Summary" starts it, and the heading and the
    blocks under it (the first starting at the heading's left edge) at the abstract's own size (or one-line subheadings no larger than its heading: a structured abstract's Objective, Methods, Results), in its column and directly stacked, are main text (a block of two or more lines whose first line opens with the heading, run in with its text, is the abstract itself) even where the
    abstract is set smaller than the body or stands outside the body's columns; when it fills its
    column to the foot it runs on at the top of the next page, at that size and in that column. A
    caption that rule 4 left unpaired (its graphic is on another page) is the float's, never main. On
    the title page smaller text is front matter (affiliations, correspondence, licence) and never
    main. After these decisions, a main block spanning two or more known columns (the page's
    and the paper's recurring columns, including on the title page) splits only at a gutter
    containing none of that block's own ink on any line. The empty interval inside the known
    gutter must be at least channel_em body letter heights wide. Each part must fit a known
    column and either hold column_min_lines lines with median line width at least half
    the column, or start within a body letter height of that column's left edge.
    The latter allows short headings without treating arbitrary word gaps in a
    centered or full-width heading as columns. Internal panel columns still need
    the multi-line witnesses. A full-width paragraph with any ink crossing the gutter
    stays whole. A run's ink_parts can prove a gap even when a drop cap caused rule 1
    to join runs across it; the late division retains the exact text and character ids, and
    does not rerun rules 1-5. Tables, float members, captions and all non-main classes are
    protected. The new blocks join their respective columns in rule 7, and page main_text.splits
    and the per-page main-text.json summary record every split, including each original
    baseline's run membership on each side. The original rule 2 block
    remains alongside derived blocks marked main_text_source for exporters. The split record
    retains any divided source run, so a repeated --paper restores rules 1-5 before classifying.
    Shaded prose panels retain their outer boundary as one reading-order item.
    Rule 1's deferred child candidates are corroborated here, without changing
    rules 1-5: internal columns split the exporter view using the same ink-safe
    division as other main text. A panel must have a substantial filled backing,
    at least three lines of prose and text near the body size. If its saved region
    grew over neighboring text, a named panel uses the actual filled backing and
    only the children inside it. Two or three internal columns are corroborated
    independently. Recognizable prose
    headings (including disclosures) admit slightly smaller type; other panels
    retain the ordinary classification. Captions, graphics and float-owned panels
    are excluded. An uncaptioned table candidate may be a framed prose panel only
    when its heading identifies prose. Panel members share their classification;
    main_text.panels records each id, outer box, child columns, member blocks and
    first reading-order number. Rule 7 orders the children inside that item. A
    previously non-main sidebar is not inserted after an unfinished paragraph
    on its page: the exporter must learn to defer such panels before that change
    can preserve cross-column sentence continuity. Rule 7 defers accepted panels
    past continued paragraphs, including those from the preceding page, and
    records each move in main_text.panels. Exporters must preserve that order.
    A title-page sequence of aligned labelled paragraphs also establishes a structured
    abstract without a heading; its complete blocks are reserved from rule 8. Period-ended
    run-in labels also identify a summary sharing a title/byline block, split before
    front-matter classification. Successive numbered entries under a References heading
    establish their own column when body-size text never occupied that lane.
    Narrow smaller/italic abstract columns beside the body, witnessed by an abstract
    or key-word label, are reserved as side_abstract regions and precede the body.
    An Abstract Translations page is ordered by author-labelled language bands,
    authors then title/abstract/key words; these blocks are outside the references.
    Colon-introduced lists inherit their lead-in's column. Small marker-led column-foot
    notes are recorded by run membership in footnotes for deferred export and
    classified other/footnote. Contained small table-member blocks become caption/table;
    unresolved table intersections remain main with ownership flags. D-637 front
    roles become other/header. Detached inline fragments split their host at the
    shared baseline. The text export retains reclassified words in a labelled
    nonbody inventory for vocabulary conservation; only main enters rule 9.
    Everything else is other: furniture, title, authors, rotated text, front matter,
    asides. Output per page: a main-text copy and an other copy, both with the rule 1-5 boxes
    kept, and a main-text.txt in rule 7's reading order (reading_order_bands). With no page
    records it writes flagged empty records, emits one stderr line and exits 0."""
    import glob, os, re
    from PIL import Image, ImageDraw, ImageFont
    files = page_files(paper_dir)
    pages = [read_json(f) for f in files]
    if not pages: print("rules 6-7: no page records", file=sys.stderr)
    def inside(b, B, t=1): return b[0] >= B[0] - t and b[2] <= B[2] + t and b[1] >= B[1] - t and b[3] <= B[3] + t
    def hull(bs): return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    def rsize(e): return e.get("run_size_px", e["size_px"])
    def ov(a0, a1, b0, b1): return min(a1, b1) - max(a0, b0)
    P = []
    for d, f in zip(pages, files):
        # Rebuild from the rule 1-5 records when --paper is run again. Derived blocks
        # are an exporter view; the original block and each divided run are retained.
        old_main = d.get("main_text") or {}
        for kind, originals in old_main.get("furniture_sources", {}).items():
            restore = {b["id"]: b for b in originals}
            d[kind] = [restore.get(b["id"], b) for b in d[kind]]
        previous = old_main.get("splits", [])
        restored = {r["source"]["id"]: r["source"] for s in previous for r in s.get("runs", [])}
        derived = {rid for s in previous for r in s.get("runs", []) for rid in r["parts"] if rid != r["source"]["id"]}
        d["elements"] = [restored.get(e["id"], e) for e in d["elements"] if e["id"] not in derived]
        d["blocks"] = [b for b in d["blocks"] if not b.get("main_text_source")]
        fl = [x["box_px"] for x in d["floats"]]
        def in_float(b): return any(F[0] <= (b[0] + b[2]) / 2 <= F[2] and F[1] <= (b[1] + b[3]) / 2 <= F[3] for F in fl)
        runs = [e for e in d["elements"] if e["kind"] == "text" and (e.get("furniture_reason") or not in_float(e["box_px"]))]
        boxed_end_runs = citation_box_runs(d)
        by_line = {}
        for e in runs: by_line.setdefault((e["angle"], e["line"], e['id'] in boxed_end_runs), []).append(e)
        L = []
        for (ang, _, boxed), es in by_line.items():
            es.sort(key=lambda e: e["box_px"][0])
            L.append({"angle": ang, "box": hull([e["box_px"] for e in es]), "text": "".join(e["text"] for e in es), "runs": es, "size": max(rsize(e) for e in es), "cls": None, "boxed_end": boxed})
        rid = {e["id"]: e for e in runs}
        blocks = [dict(b, box_px=hull([rid[m]["box_px"] for m in b["members"] if m in rid]), members=[m for m in b["members"] if m in rid]) for b in d["blocks"] if any(m in rid for m in b["members"])]
        P.append({"page": d["page"], "file": f, "d": d, "H": d["region_box_px"][3], "lines": L, "runs": runs, "blocks": blocks, "boxed_end_runs": boxed_end_runs, "run_line": {e["id"]: ln for ln in L for e in ln["runs"]}})
    for p in P: p['d'].pop('repository_cover', None)
    if len(P) > 1 and repository_cover(P[0]['d'], [p['d'] for p in P[1:4]]):
        P[0]['d']['repository_cover'] = True
        for p in P[1:4]:
            if not copyright_leaf(p['d']): break
            p['d']['repository_cover'] = True
    front = next((p for p in P if not p['d'].get('repository_cover')), P[0] if P else None)
    if P and P[0]['d'].get('repository_cover'):
        # Behind a wrapper, a picture leaf (an opening figure with only a footer
        # or a sideways rights line) is not the article's first page (AG05). The
        # first leaf with upright prose is; without one the first leaf stays.
        words = lambda q: sum(len(e['text'].split()) for e in q['runs'] if e['angle'] == 0)
        front = next((q for q in P if not q['d'].get('repository_cover') and words(q) >= 30), front)
    for p in P:
        for ln in p['lines']:
            reason = ('repository download cover sheet' if p['d'].get('repository_cover') else
                      next((e.get('furniture_reason') for e in ln['runs'] if e.get('furniture_reason')), None))
            if reason: ln.update(cls='furniture', furniture_why=reason, local_furniture=True)
    sizes = []
    for p in P:
        for e in p["runs"]:
            if p["d"].get("repository_cover") or e.get("furniture_reason"): continue
            sizes += [round(rsize(e) * 2) / 2] * len(e["text"].strip())
    tol = PARAMS["body_size_tolerance"]
    if not sizes:   # no text outside floats on any page (a scanned paper, a paper of figures): nothing to classify
        empty = {"body_size_px": 0, "header_bottom": None, "footer_top": None, "columns": [], "blocks": [], "counts": {}, "reading_order": [], "band_boundaries_y": [], "splits": [], "panels": []}
        for p in P:
            p["d"]["main_text"] = dict(empty)
            p["d"]["main_text"]["page_top_check"] = page_top_check(p["d"])
            write_json(p["file"], p["d"], indent=1)
        summary = {"body_size_px": 0, "header_bottom": None, "footer_top": None, "title_box_px": None, "author_box_px": None,
                   "flags": ["no page records: nothing to classify" if not pages else "no text outside floats on any page: nothing to classify"], "pages": [{"page": p["page"], "columns": [], "counts": {}, "splits": [], "page_top_check": p["d"]["main_text"]["page_top_check"]} for p in P]}
        write_text(os.path.join(paper_dir, "main-text.txt"), "# rule 6 main text in rule 7 reading order: none (no text outside floats)\n")
        write_json(os.path.join(paper_dir, "main-text.json"), summary, indent=1)
        return summary
    body = statistics.median(sizes)
    wrap_vocab = wrap_vocabulary([p["runs"] for p in P])   # lane r5-wrap (O33)
    # Table headers can lie just outside rule 3's member set. Their connection
    # to actual cells is stronger evidence than recurrence at a page top.
    for p in P:
        es = {e["id"]: e for e in p["d"]["elements"] if e["kind"] == "text"}
        cells = {m for t in p["d"]["tables"] for m in t["members"] if m in es}
        p["table_header_runs"] = set()
        for b in p["blocks"]:
            peers = [es[m] for m in b["members"] if m in cells and es[m]["angle"] == 0]
            if not peers: continue
            top = min(e["box_px"][1] for e in peers)
            for m in b["members"]:
                e = es.get(m)
                if (e and m not in cells and e["angle"] == 0
                        and 0 <= top - e["box_px"][3] <= 3 * body
                        and any(ov(e["box_px"][0], e["box_px"][2], x["box_px"][0], x["box_px"][2]) > 0
                                and abs(rsize(e) - rsize(x)) <= tol * max(rsize(e), rsize(x)) for x in peers)):
                    p["table_header_runs"].add(m)
    def bsize(b, p):
        ss = []
        for m in b["members"]:
            ln = p["run_line"].get(m)
            if ln is None: continue
            e = next(x for x in ln["runs"] if x["id"] == m); ss += [rsize(e)] * max(1, len(e["text"].strip()))
        return statistics.median(ss) if ss else 0
    def blines(b, p): return len({p["run_line"][m]["angle"] * 100000 + id(p["run_line"][m]) for m in b["members"] if m in p["run_line"]})
    # lane r2-prosetable: the paper's body face (character-weighted over every page's non-furniture runs)
    face_count = collections.Counter()
    for p_ in P:
        for e in p_["runs"]:
            if not p_["d"].get("repository_cover") and not e.get("furniture_reason"): face_count[run_face(e)] += len(e["text"].strip())
    body_face = face_count.most_common(1)[0][0] if face_count else None
    for p_ in P:   # lane r3-pullquote: framed display-face blocks beside the body are pull quotes, not columns
        # a quote's runs that rule 2 put into a column's block are lifted into a block of their own
        p_["pull_quotes"] = set()
        for ids in pull_quote_groups(p_["runs"], [e for e in p_["d"]["elements"] + p_["d"].get("art", []) if e["kind"] in ("rule", "fill")], body_face):
            touched = [b for b in p_["blocks"] if ids.intersection(b["members"])]
            if not touched or not ids <= {m for b in touched for m in b["members"]}: continue
            if len(touched) == 1 and set(touched[0]["members"]) == ids:
                p_["pull_quotes"].add(touched[0]["id"]); continue
            kept = []
            for b in p_["blocks"]:
                if b not in touched: kept.append(b); continue
                rest = [m for m in b["members"] if m not in ids]
                if rest:
                    part = dict(b, id=b["id"] + ":body", members=rest, main_text_source=b["id"],
                                box_px=hull([e["box_px"] for e in p_["runs"] if e["id"] in rest]))
                    part["text"] = " ".join(e["text"] for e in p_["runs"] if e["id"] in rest)[:80]
                    kept.append(part); p_["d"]["blocks"].append(part.copy())
            src = touched[0]["id"]; members = [m for b in touched for m in b["members"] if m in ids]
            quote = dict(touched[0], id=src + ":pullquote", members=members, main_text_source=src,
                         box_px=hull([e["box_px"] for e in p_["runs"] if e["id"] in ids]))
            quote["text"] = " ".join(e["text"] for e in p_["runs"] if e["id"] in ids)[:80]
            kept.append(quote); p_["d"]["blocks"].append(quote.copy())
            p_["blocks"] = kept; p_["pull_quotes"].add(quote["id"])
    sized_pages = {}
    # reference lists keep their classes: from the first page holding a references heading (reference_heading on
    # a block's first line) on, no page is read as set in its own size
    def first_line(x, p_):
        return " ".join(e["text"] for m in x["members"] if m in p_["run_line"] for e in p_["run_line"][m]["runs"]
                        if e["id"] == m and p_["run_line"][m] is p_["run_line"][x["members"][0]]) if x["members"] and x["members"][0] in p_["run_line"] else ""
    refs_from = next((i for i, p_ in enumerate(P) if any(reference_heading(first_line(x, p_)) for x in p_["blocks"])), len(P))
    def body_face_prose(b, p):
        """a page's long prose set in the paper's body face, within twice the size tolerance below the body size,
        on a page that has no paragraph text at the body size other than an abstract: the page's own paragraph
        text (one page set a little smaller than the paper's larger pages), not a smaller section, note,
        abstract or reference list (those keep their classes: no page from the references heading's page on)"""
        if body_face is None or P.index(p) >= refs_from or bsize(b, p) < (1 - 2 * tol) * body or not long_prose(b, p): return False
        # nor a list of numbered entries (a reference list without its heading on this page)
        starts = {}   # the block's own leftmost run on each of its lines
        for m in b["members"]:
            ln = p["run_line"].get(m)
            if ln is None: continue
            e = next(x for x in ln["runs"] if x["id"] == m)
            if id(ln) not in starts or e["box_px"][0] < starts[id(ln)][0]: starts[id(ln)] = (e["box_px"][0], e["text"])
        starts = {k: t for k, (_, t) in starts.items()}
        if sum(1 for t in starts.values() if re.match(r"\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s", t)) >= PARAMS["column_min_lines"]: return False
        if id(p) not in sized_pages:   # the page's paragraph text at the body size, an abstract apart
            sized_pages[id(p)] = any(bsize(x, p) >= (1 - tol) * body and blines(x, p) >= PARAMS["column_min_lines"]
                                     and not re.match(r"\s*(?:abstract|summary)\b", " ".join(e["text"] for m in x["members"][:3] if m in p["run_line"] for e in p["run_line"][m]["runs"] if e["id"] == m), re.I)
                                     for x in p["blocks"])
        if sized_pages[id(p)]: return False
        faces = collections.Counter()
        for m in b["members"]:
            ln = p["run_line"].get(m)
            if ln is None: continue
            e = next(x for x in ln["runs"] if x["id"] == m); faces[run_face(e)] += len(e["text"].strip())
        return bool(faces) and faces.most_common(1)[0][0] == body_face
    def section_note(b, p):
        """Keep caption/table ownership and marked or ruled footnotes out of section flow."""
        es = sorted([e for m in b["members"] for e in p["run_line"][m]["runs"] if e["id"] == m],
                    key=lambda e: (e["line"], e["box_px"][0]))
        if not es: return True
        first = es[0]["text"].lstrip()
        if re.match(r"^[*†‡§¶#⁰¹²³⁴⁵⁶⁷⁸⁹]", first): return True
        if re.match(r"^(?:\d+|[a-z])\b", first) and rsize(es[0]) < PARAMS["superscript_em"] * bsize(b, p): return True
        x0, y0, x1, _ = b["box_px"]
        if y0 > .65 * p["H"]:
            for e in p["d"]["elements"] + p["d"].get("art", []):
                if e["kind"] not in ("rule", "fill"): continue
                a, top, z, bottom = e["box_px"]
                if (bottom - top <= px(PARAMS["rule_max_pt"]) and .65 * p["H"] <= bottom <= y0
                        and ov(a, z, x0, x1) >= PARAMS["full_width"] * (x1 - x0)): return True
        return False
    def long_prose(b, p):
        """A substantial paragraph is column evidence even at a section's smaller size."""
        es = [e for m in b["members"] for e in p["run_line"][m]["runs"] if e["id"] == m]
        text = " ".join(e["text"] for e in es)
        return (blines(b, p) >= 10 and len(text.split()) >= 3 * blines(b, p) and not section_note(b, p)
                and bool(re.search(r"[a-z][.!?](?:\s|$)", text))
                and not any(is_caption_run(e) for e in es)
                and not any(set(b["members"]).intersection(t["members"]) for t in p["d"]["tables"])
                and not any(u.get("block") == b["id"] for u in p["d"].get("unpaired", [])))
    def own_columns(p, without_panels=(), for_bands=False):
        """the page's own text columns: the extents of its blocks of column_min_lines or more lines at
        the body size or larger, two extents merged when they overlap by half of the wider"""
        cols = []
        if p["d"].get("repository_cover"): return cols
        for b in sorted(p["blocks"], key=lambda b: b["box_px"][0]):
            if b["id"] in without_panels or b["id"] in p.get("pull_quotes", ()): continue
            if for_bands:
                # Infer the frame before bands exist, from the nonrecurring part
                # of mixed blocks. Smaller prose also witnesses the frame on a
                # page entirely set in a smaller section size (measured J05).
                members = [m for m in b["members"] if p["run_line"][m]["cls"] is None]
                if not members: continue
                b = dict(b, members=members, box_px=hull([e["box_px"] for m in members
                         for e in p["run_line"][m]["runs"] if e["id"] == m]))
            if blines(b, p) < PARAMS["column_min_lines"] or not all(p["run_line"][m]["cls"] is None for m in b["members"] if m in p["run_line"]): continue
            if bsize(b, p) < (1 - tol) * body and not (for_bands and p is not front and long_prose(b, p)) and not body_face_prose(b, p): continue
            x0, x1 = b["box_px"][0], b["box_px"][2]
            if not for_bands and b["id"] in p.get("band_recovered", set()): continue
            hit = next((c for c in cols if ov(x0, x1, c[0], c[1]) >= 0.5 * max(x1 - x0, c[1] - c[0])), None)
            if hit: hit[0] = min(hit[0], x0); hit[1] = max(hit[1], x1)
            else: cols.append([x0, x1])
        return sorted(cols)
    # furniture by recurrence
    def sig(ln):
        pos = ln["box"][1] if ln["angle"] in (0, 180) else ln["box"][0]
        t = re.sub(r"\s", "", ln["text"]); t = "#" if re.fullmatch(r"\d{1,4}", t) else re.sub(r"\d", "#", t)
        return (ln["angle"], t, round(pos / PARAMS["furniture_pos_px"]))
    def edge_line(ln, p):
        return ln["angle"] == 0 and (ln["box"][3] < PARAMS["band_edge_share"] * p["H"]
                                     or ln["box"][1] > (1 - PARAMS["band_edge_share"]) * p["H"])
    def number_pattern(ln):
        angle, _, position = sig(ln)
        t = re.sub(r"\s", "", ln["text"])
        # A folio is a whole number at either end of the running line;
        # changing widths inside decimal measurements do not supply evidence.
        t = re.sub(r"^\d+(?![\d.,])|(?<![\d.,])\d+$", "#", t)
        return angle, re.sub(r"\d", "#", t), position
    occ = collections.defaultdict(set); edge_occ = collections.defaultdict(set)
    for p in P:
        for ln in p["lines"]:
            if ln.get('boxed_end'): continue
            occ[sig(ln)].add(p["page"])
            if edge_line(ln, p): edge_occ[number_pattern(ln)].add(p["page"])
    # furniture recurs on furniture_min_pages pages and on a quarter of the paper's pages at least: running
    # heads and page numbers stand on nearly every page, a label repeated in the text (a structured
    # recommendation's "PICOS question addressed by a SR" on 3 of 68 pages) does not
    FURNITURE_MIN_SHARE, EDGE_SHARE = PARAMS["furniture_min_share"], PARAMS["band_edge_share"]
    need = max(2 if len(P) < 8 else PARAMS["furniture_min_pages"], math.ceil(FURNITURE_MIN_SHARE * len(P)))
    def furniture(ln, why):
        ln["cls"] = "furniture"
        ln.setdefault("furniture_why", why)
    for p in P:
        for ln in p["lines"]:
            if ln.get('boxed_end'): continue
            if any(e["id"] in p["table_header_runs"] for e in ln["runs"]): continue
            width = p["d"]["region_box_px"][2]
            if (ln["angle"] not in (0, 180)
                    and all(e["box_px"][3] - e["box_px"][1] > .75 * p["H"]
                            and e["box_px"][2] - e["box_px"][0] < 2 * body
                            and (e["box_px"][2] < .075 * width or e["box_px"][0] > .925 * width) for e in ln["runs"])
                    and not any(is_caption_run(e) for e in ln["runs"])):
                furniture(ln, "rotated sidebar spanning the page height")
            elif len(occ[sig(ln)]) >= need: furniture(ln, "same text up to digits at the same position on %d pages" % len(occ[sig(ln)]))
            elif edge_line(ln, p) and len(edge_occ[number_pattern(ln)]) >= need:
                furniture(ln, "same margin text with varying page-number width on %d pages" % len(edge_occ[number_pattern(ln)]))
    # Only furniture overlapping this page's text columns sets a horizontal
    # band. A recurring margin foot beside the text must not cut across it.
    for p in P: p["band_columns"] = own_columns(p, for_bands=True)
    # Rule 1 shares a baseline across columns. Test margin runs on their own,
    # so body text on that baseline cannot hide a recurring margin foot.
    margin_occ = collections.defaultdict(set)
    def margin_line(e):
        return dict(angle=e["angle"], box=e["box_px"], text=e["text"], runs=[e], size=rsize(e), cls=None)
    def in_margin(e, p):
        return p["band_columns"] and not any(ov(e["box_px"][0], e["box_px"][2], c0, c1) > 0 for c0, c1 in p["band_columns"])
    for p in P:
        for e in p["runs"]:
            if in_margin(e, p): margin_occ[sig(margin_line(e))].add(p["page"])
    for p in P:
        for ln in list(p["lines"]):
            recurring = [e for e in ln["runs"] if e['id'] not in p['boxed_end_runs'] and in_margin(e, p) and len(margin_occ[sig(margin_line(e))]) >= need]
            if not recurring: continue
            kept = [e for e in ln["runs"] if e not in recurring]
            if not kept: furniture(ln, "recurring run beside the text columns"); continue
            ln.update(runs=kept, box=hull([e["box_px"] for e in kept]), text="".join(e["text"] for e in kept), size=max(rsize(e) for e in kept))
            for e in recurring:
                separate = margin_line(e); furniture(separate, "recurring run beside the text columns")
                p["lines"].append(separate); p["run_line"][e["id"]] = separate
    def band_witness(ln, p):
        return (not p["d"].get("repository_cover") and not ln.get("local_furniture")
                and ln["cls"] == "furniture" and ln["angle"] == 0
                and not re.fullmatch(r"\(?\s*Continue[ds]\s*\)?\.?", unicodedata.normalize("NFKC", ln["text"]).strip(), re.I)
                and any(ov(e["box_px"][0], e["box_px"][2], c0, c1) > 0
                        for e in ln["runs"] for c0, c1 in p["band_columns"]))
    tops = [ln["box"][3] for p in P for ln in p["lines"] if band_witness(ln, p) and ln["box"][1] < EDGE_SHARE * p["H"]]
    bots = [ln["box"][1] for p in P for ln in p["lines"] if band_witness(ln, p) and ln["box"][3] > (1 - EDGE_SHARE) * p["H"]]
    header_bottom = max(tops) if tops else None; footer_top = min(bots) if bots else None
    def header_family(ln):
        angle, text, position = sig(ln)
        return angle, re.sub(r"#+", "#", text), position
    known_headers = {header_family(ln) for p in P for ln in p["lines"]
                     if band_witness(ln, p) and ln["box"][3] < EDGE_SHARE * p["H"]}
    # Lane r6-artinfo, rule I8 (page-1 notes are content; prior art lane r4-frontblock): on the
    # front page the footer band's position alone does not make a line furniture. It is furniture
    # when its letters (digits, spaces and signs ignored) stand in the footer band of another page
    # (a running footer shifted on the front page), or when it has no letters (a folio). A
    # front-page-only note set in that band (a supplementary-material note, the second row of a
    # how-to-cite note) is page content. A line rule 1 joined on one baseline is decided run by
    # run: its recurring runs (a footer, a folio) stay furniture as a line of their own, its other
    # runs stay page text.
    def band_letters(text):
        return "".join(ch for ch in unicodedata.normalize("NFKC", text) if ch.isalpha()).lower()
    other_band = ["".join(band_letters(ln["text"]) for ln in sorted(q["lines"], key=lambda ln: (ln["box"][1], ln["box"][0]))
                          if footer_top is not None and ln["angle"] == 0
                          and ln["box"][1] >= footer_top - PARAMS["band_tolerance_em"] * ln["size"])
                  for q in P if q is not front]
    def band_recurs(text):
        letters = band_letters(text)
        return not letters or any(letters in band for band in other_band)
    def front_band_furniture(p, ln):
        if band_recurs(ln["text"]): return True
        rec = [e for e in ln["runs"] if band_recurs(e["text"])]
        if not rec: return False
        kept = [e for e in ln["runs"] if e not in rec]
        if not kept: return True   # every run recurs on its own: the line is furniture as a whole
        ln.update(runs=kept, box=hull([e["box_px"] for e in kept]), text="".join(e["text"] for e in kept), size=max(rsize(e) for e in kept))
        separate = {"angle": ln["angle"], "box": hull([e["box_px"] for e in rec]), "text": "".join(e["text"] for e in rec),
                    "runs": rec, "size": max(rsize(e) for e in rec), "cls": None}
        furniture(separate, "inside the recurring footer band")
        p["lines"].append(separate)
        for e in rec: p["run_line"][e["id"]] = separate
        return False
    for p in P:
        column_tops = []
        upright = [ln for ln in p["lines"] if ln["cls"] is None and ln["angle"] == 0]
        # The title page's publication masthead is above its largest type.
        # It cannot masquerade as a body-column opening merely by sharing x.
        title_start = None
        if p is front and upright:
            largest = max(ln["size"] for ln in upright)
            title_start = min(ln["box"][1] for ln in upright if ln["size"] >= largest - 1e-6)
        for ln in p["lines"]:
            if ln["cls"] is not None or ln["angle"] != 0: continue
            # A running head does not become a body opening when its folio
            # acquires another digit. Keep that established band's exclusion.
            if header_family(ln) in known_headers: continue
            if title_start is not None and ln["box"][3] < title_start: continue
            if any(is_caption_run(e) for e in ln["runs"]): column_tops.append(ln["box"][1])
            for c0, c1 in p["band_columns"]:
                es = [e for e in ln["runs"] if c0 - body <= e["box_px"][0] and e["box_px"][2] <= c1 + body]
                # A detached section number supplies the heading's left edge.
                # Looking only at letters mistakes the indented title for a
                # running head and drops it before the paragraph below.
                numbered = re.match(r"^\d+(?:\.\d+)*\.?\s+(?:[|]\s*)?[A-Z]",
                                    " ".join(e["text"].strip() for e in sorted(es, key=lambda e: e["box_px"][0])))
                if not (numbered and es and min(rsize(e) for e in es) >= PARAMS["heading_size_ratio"] * body):
                    es = [e for e in es if re.search(r"[^\W\d_]", e["text"])]
                if not es: continue
                box = hull([e["box_px"] for e in es])
                if abs(box[0] - c0) <= PARAMS["column_indent_em"] * body and max(rsize(e) for e in es) >= (1 - tol) * body:
                    column_tops.append(box[1])
            # A heading can span several columns while sharing the left edge
            # of the first. It still establishes where article content starts.
            if (p["band_columns"] and ln["size"] > (1 + tol) * body
                    and any(abs(e["box_px"][0] - p["band_columns"][0][0]) <= 2 * body
                            and e["box_px"][2] <= max(c1 for _, c1 in p["band_columns"]) + body
                            and sum(ov(e["box_px"][0], e["box_px"][2], c0, c1) > body
                                    for c0, c1 in p["band_columns"]) >= 2 for e in ln["runs"])):
                column_tops.append(ln["box"][1])
        p["first_column_top"] = min(column_tops, default=None)
        p["header_bottom"] = (min(header_bottom, p["first_column_top"]) if header_bottom is not None
                              and p["first_column_top"] is not None else header_bottom)
        p["header_protected"] = set()
        tail_owners = collections.defaultdict(set)
        tail_runs = {e['id']:e for e in p['runs']}
        for b in p["blocks"]:
            size=bsize(b,p)
            if blines(b,p) >= PARAMS["column_min_lines"] and (size >= (1-tol)*body or long_prose(b,p)):
                for m in b["members"]:
                    e=tail_runs[m]
                    if (abs(rsize(e)-size)<=tol*max(rsize(e),size)
                            and re.search(r'[^\W\d_]',e['text'])):tail_owners[m].add(b["id"])
        def column_tail(ln):
            # A footer elsewhere in the paper cannot erase this column's
            # final line. Require the same substantial text block: a folio
            # or publication footer near the column is not its final line.
            # Recurring furniture has already been classified.
            return any(prev is not ln and prev["cls"] is None and prev["angle"] == 0
                       and 0 <= ln["box"][1] - prev["box"][3] < body
                       and abs(prev["size"] - ln["size"]) <= tol * max(prev["size"], ln["size"])
                       and any(ov(e["box_px"][0], e["box_px"][2], x["box_px"][0], x["box_px"][2]) > body
                               and tail_owners[e["id"]].intersection(tail_owners[x["id"]])
                               for e in ln["runs"] for x in prev["runs"])
                       for prev in p["lines"])
        for ln in p["lines"]:
            if ln["cls"] is None and ln["angle"] == 0 and not ln.get('boxed_end'):
                if (p["header_bottom"] is not None
                        and ln["box"][3] <= p["header_bottom"] + PARAMS["band_tolerance_em"] * ln["size"]
                        and (p["first_column_top"] is None or ln["box"][3] < p["first_column_top"])):
                    furniture(ln, "inside the recurring header band")
                elif (footer_top is not None and ln["box"][1] >= footer_top - PARAMS["band_tolerance_em"] * ln["size"]
                      and not column_tail(ln) and (p is not front or front_band_furniture(p, ln))):
                    furniture(ln, "inside the recurring footer band")
                elif header_bottom is not None and ln["box"][3] <= header_bottom + PARAMS["band_tolerance_em"] * ln["size"]:
                    p["header_protected"].update(e["id"] for e in ln["runs"])
            if ln["cls"] is None and ln["angle"] != 0: ln["cls"] = "rotated"
        # Restoring a numbered heading's opening must not split its wrapped
        # continuation into a second reading-order block. Ordinary paragraphs
        # still use the existing opening/remainder split to preserve columns.
        for b in p["blocks"]:
            if not p["header_protected"].intersection(b["members"]): continue
            es = [tail_runs[m] for m in b["members"]]
            if (es and min(rsize(e) for e in es) >= PARAMS["heading_size_ratio"] * body
                    and max(rsize(e) for e in es) - min(rsize(e) for e in es) <= tol * body
                    and blines(b, p) <= 5
                    and re.match(r"^\d+(?:\.\d+)*\.?\s+(?:[|]\s*)?[A-Z]", b.get("text", ""))):
                p["header_protected"].update(b["members"])
    # First-sight furniture is local to its page. It must not widen the existing
    # bands: a title-page copyright foot can be above later pages' body text.
    def notice(text):
        t = unicodedata.normalize("NFKC", text).strip()
        if re.search(r"\borcid\.org/", t, re.I): return None   # author identifiers are article content
        if re.search(r"©|\bcopyright\b|\bDownloaded from\b|\bReproduced with permission\b", t, re.I): return "copyright or download notice"
        if re.fullmatch(r"[SE]?\d{1,5}\s*[|]?", t): return "page number"
        if re.match(r"(?:https?://|www\.|[\w.-]+\.(?:com|org|net|edu)/|doi\s*[: ]|10\.\d{4,9}/)", t, re.I): return "DOI or URL"
        if re.search(r"\b(?:Volume|Vol\.|Issue)\s*\d|\b(?:19|20)\d{2}\s*[;/,]\s*(?:\d|[A-Z]?\d+\s*[–-])", t): return "journal volume/year/pages"
        if re.match(r"(?:Journal\b|J\.?\s+[A-Z])", t): return "journal name"
        return None
    def continuation(text):
        return bool(re.fullmatch(r"\(?\s*Continued\s*\)?\.?", unicodedata.normalize("NFKC", text).strip(), re.I))
    rotated_occ = collections.defaultdict(set)
    for p in P:
        for e in p["d"]["elements"]:
            if e["kind"] == "text" and e["angle"] != 0:
                rotated_occ[sig(margin_line(e))].add(p["page"])
    manuscript_columns = []
    for p in P:
        all_runs = {e["id"]: e for e in p["d"]["elements"] if e["kind"] == "text"}
        upright = [e for e in all_runs.values() if e["angle"] == 0]
        owners = collections.defaultdict(list)
        for b in p["d"]["blocks"]:
            for m in b["members"]: owners[m].append(b)
        def already(e):
            return p["run_line"].get(e["id"], {}).get("cls") == "furniture"
        def edge(e):
            return e["box_px"][1] < EDGE_SHARE * p["H"] or e["box_px"][3] > (1 - EDGE_SHARE) * p["H"]
        def attached(e):
            # A year/DOI at a reference's end belongs to that paragraph, even
            # when it is the final printed line in a column.
            if e['id'] in p['boxed_end_runs']: return True
            b = e["box_px"]
            # Justification can split a reference into different rule-1
            # blocks. Its nearby words still establish a content baseline.
            if notice(e["text"]) == "DOI or URL" and p is not P[0] and any(x["id"] != e["id"] and not already(x)
                   and abs((x["box_px"][1]+x["box_px"][3]-b[1]-b[3])/2) < .4*rsize(e)
                   and 0 <= max(b[0]-x["box_px"][2], x["box_px"][0]-b[2]) < 4*rsize(e)
                   and abs(rsize(e)-rsize(x)) <= tol*max(rsize(e),rsize(x))
                   and (notice(x["text"]) is None and re.search(r"[A-Za-z]", x["text"])
                        or p is not P[0] and notice(e["text"]) == "DOI or URL"
                        and notice(x["text"]) == "journal volume/year/pages")
                   for x in upright): return True
            return any(x["id"] != e["id"] and x["angle"] == 0 and not already(x)
                       and not re.fullmatch(r"\s*DOI\s*:\s*", x["text"], re.I)
                       and not (re.fullmatch(r"\s*DOI\s*:\s*", e["text"], re.I) and notice(x["text"]) == "DOI or URL")
                       and ov(x["box_px"][0], x["box_px"][2], b[0], b[2]) > 0
                       and 0 <= max(b[1] - x["box_px"][3], x["box_px"][1] - b[3]) < .85 * max(rsize(e), rsize(x))
                       and abs(rsize(e) - rsize(x)) <= tol * max(rsize(e), rsize(x))
                       for block in owners[e["id"]] for m in block["members"]
                       if (x := all_runs.get(m)) is not None)
        # Substantial blocks witness the vertical frame; exclude explicit
        # candidate feet before measuring it, including feet inside a table.
        frame_ids = {m for b in p["blocks"] if blines(b, p) >= PARAMS["column_min_lines"]
                     and (bsize(b, p) >= (1 - tol) * body or long_prose(b, p)) for m in b["members"]}
        frame_ids |= {m for t in p["d"]["tables"] for m in t["members"]}
        frame = [e for e in upright if e["id"] in frame_ids and not already(e)
                 and not (edge(e) and notice(e["text"]) and not attached(e)) and not continuation(e["text"])]
        def outside(e):
            b = e["box_px"]
            peers = [x for x in frame if x["id"] != e["id"]
                     and ov(x["box_px"][0], x["box_px"][2], b[0], b[2]) > 0]
            if not peers: return False
            return (b[3] + .8 * body < min(x["box_px"][1] for x in peers)
                    or b[1] - .8 * body > max(x["box_px"][3] for x in peers))
        chosen = {}
        def unfinished_above():
            """D4 rule 3: the previous page's lowest body-size text row (not furniture) ends without sentence
            punctuation, so an entry runs on to this page's top (measured: AN10, a web print whose reference
            source lines fall at the top of the next page)."""
            i = P.index(p)
            if i == 0: return False
            rows = [ln for ln in P[i - 1]["lines"] if ln["angle"] == 0 and ln.get("cls") != "furniture" and ln["runs"]
                    and abs(statistics.median(rsize(x) for x in ln["runs"]) - body) <= tol * body]
            if not rows: return False
            return not re.search(r"[.!?][\"'\u2019\u201d)\]]*\s*$", max(rows, key=lambda ln: ln["box"][3])["text"])
        def continues_entry(e):
            """D4 rule 3: at the page top, the previous page ends an unfinished entry; at the page foot, the body-size
            row just above the line in its column (within three letter heights) is unfinished."""
            b = e["box_px"]
            if b[1] < EDGE_SHARE * p["H"]: return unfinished_above()
            if b[3] <= (1 - EDGE_SHARE) * p["H"]: return False
            rows = [ln for ln in p["lines"] if ln["angle"] == 0 and ln.get("cls") != "furniture" and ln["runs"]
                    and all(x["id"] != e["id"] for x in ln["runs"]) and ln["box"][3] <= b[1] + 0.2 * body
                    and b[1] - ln["box"][3] <= 3 * body and ov(ln["box"][0], ln["box"][2], b[0], b[2]) > 0
                    and abs(statistics.median(rsize(x) for x in ln["runs"]) - body) <= tol * body]
            if not rows: return False
            return not re.search(r"[.!?][\"'\u2019\u201d)\]]*\s*$", max(rows, key=lambda ln: ln["box"][3])["text"])
        # A numbered manuscript has a dense, consecutive margin column. Test
        # individual runs in the page's reading frame, including landscape
        # supplements, since the line builder shares baselines with prose.
        angles = collections.Counter()
        for e in all_runs.values(): angles[e["angle"]] += len(e["text"].strip())
        dominant = angles.most_common(1)[0][0] if angles else 0
        transform, _ = _frame(dominant)
        extent = transform(*p["d"]["region_box_px"])
        def number_box(e):
            b = transform(*e["box_px"])
            return [b[0]-extent[0], b[1]-extent[1], b[2]-extent[0], b[3]-extent[1]]
        reading_runs = [e for e in all_runs.values() if e["angle"] == dominant]
        table_ids = {m for t in p["d"]["tables"] for m in t["members"]}
        width, height = extent[2]-extent[0], extent[3]-extent[1]
        prose_runs = [e for e in reading_runs if len(re.findall(r"[A-Za-z]", e["text"])) >= 35]
        number_cols = []
        for e in reading_runs:
            if e["id"] in table_ids or not re.fullmatch(r"\s*\d{1,4}\s*", e["text"]): continue
            x0, y0, x1, y1 = number_box(e)
            if not (x1 < .13 * width or x0 > .87 * width): continue
            if not any((x1 + .75 * body < number_box(x)[0] or x0 - .75 * body > number_box(x)[2])
                       for x in prose_runs): continue
            # A margin column may align either edge; single-digit labels must
            # stay with its two-digit labels in a rotated reading frame too.
            group = next((g for g in number_cols if min(abs(number_box(g[0])[0] - x0),
                                                       abs(number_box(g[0])[2] - x1)) < .3 * body), None)
            if group is None: number_cols.append([e])
            else: group.append(e)
        for group in number_cols:
            group.sort(key=lambda e: number_box(e)[1])
            if len(group) < 12 or number_box(group[-1])[1] - number_box(group[0])[1] < .35 * height: continue
            steps = [int(b["text"]) - int(a["text"]) for a, b in zip(group, group[1:])]
            gaps = [number_box(b)[1] - number_box(a)[1] for a, b in zip(group, group[1:])]
            dense = 0 < statistics.median(gaps) < 2 * body
            established = any(abs(number_box(group[0])[2] - x) < .3 * body for x in manuscript_columns)
            if sum(s == 1 for s in steps) >= .9 * len(steps) and (dense or established):
                if dense: manuscript_columns.append(number_box(group[0])[2])
                for e in group: chosen[e["id"]] = "consecutive manuscript line numbers in the margin"
        p["manuscript_numbers"] = set(chosen)
        for e in all_runs.values():
            if (e["angle"] != dominant and e["angle"] != 0 and
                    min(e["box_px"][2]-e["box_px"][0], e["box_px"][3]-e["box_px"][1]) > 2 * body and
                    len(rotated_occ[sig(margin_line(e))]) >= need and not any(
                    t.get("angle", 0) == e["angle"] and
                    t["box_px"][0] <= (e["box_px"][0] + e["box_px"][2]) / 2 <= t["box_px"][2] and
                    t["box_px"][1] <= (e["box_px"][1] + e["box_px"][3]) / 2 <= t["box_px"][3]
                    for t in p["d"]["tables"])):
                chosen[e["id"]] = "recurrent rotated watermark outside the table reading frame"
        for e in upright:
            if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*mm\s*\(\s*\d+\s*[x×]\s*\d+\s*DPI\s*\)\s*", e["text"], re.I):
                if any(x["kind"] == "image" and x["box_px"][3] <= e["box_px"][1] and
                       ov(x["box_px"][0], x["box_px"][2], e["box_px"][0], e["box_px"][2]) > 0
                       for x in p["d"]["elements"]):
                    chosen[e["id"]] = "figure upload dimensions and resolution"
        for e in upright:
            if already(e) or e['id'] in p['boxed_end_runs']: continue
            why = notice(e["text"])
            if why == "page number":
                # A table group label may be a separate block above the first
                # row, with a wider gap than an ordinary paragraph line.
                b = e["box_px"]
                below = [all_runs[m] for t in p["d"]["tables"] for m in t["members"]
                         if m in all_runs and all_runs[m]["angle"] == 0
                         and 0 <= all_runs[m]["box_px"][1] - b[3] <= 3 * body
                         and abs(all_runs[m]["box_px"][0] - b[0]) <= body]
                above = [x for x in upright if not already(x) and x["id"] != e["id"]
                         and 0 <= b[1] - x["box_px"][3] <= 3 * body
                         and abs(x["box_px"][0] - b[0]) <= body
                         and abs(rsize(x) - rsize(e)) <= tol * max(rsize(x), rsize(e))]
                if below and above: why = None
            if why == "DOI or URL" and (e["id"] not in p["run_line"]
                    or re.search(r"\.[gts]\d{3}\b", e["text"])):
                why = None   # a figure/table/supplement identifier belongs to its caption
            if why == "page number" and any(x["id"] != e["id"] and x["line"] == e["line"]
                    and not already(x) and not notice(x["text"]) for x in upright):
                why = None   # a table/caption number or equation shares its printed line
            if (why in ("journal name", "journal volume/year/pages") and p is not P[0]
                    and abs(rsize(e) - body) <= tol * body and continues_entry(e)):
                why = None   # D4 rule 3: a journal line is furniture when it recurs (caught above); a unique page-top
                             # body-size line after a page ending an unfinished entry is that entry's source line
            if why and edge(e) and outside(e) and not attached(e): chosen[e["id"]] = why + " outside the page text frame"
            if continuation(e["text"]):
                for t in p["d"]["tables"]:
                    cells = [all_runs[m] for m in t["members"] if m in all_runs and m != e["id"]
                             and not continuation(all_runs[m]["text"]) and not already(all_runs[m])]
                    if (cells and t.get("angle", 0) == 0 and e["id"] in t["members"]
                            and e["box_px"][1] >= max(x["box_px"][3] for x in cells)):
                        chosen[e["id"]] = "standalone continuation at the table foot"
                if e["box_px"][1] > (1 - EDGE_SHARE) * p["H"] and outside(e):
                    chosen[e["id"]] = "standalone continuation at the column foot"
        # A reproduction-only page has no body frame. Keep the full notice,
        # including its wrapped final line, together as recorded furniture.
        for b in p["d"]["blocks"]:
            es = [all_runs[m] for m in b["members"] if m in all_runs]
            if (es and len(es) <= 4 and min(e["box_px"][1] for e in es) < EDGE_SHARE * p["H"]
                    and re.match(r"\s*Reproduced with permission\b", " ".join(e["text"] for e in es), re.I)):
                for e in es: chosen[e["id"]] = "reproduction permission notice"
        # A folio or divider can have its own run, just outside the column's
        # horizontal extent. Keep it with a proven publication footer, provided
        # that baseline contains no unexplained prose or table-cell text.
        for e in upright:
            if e["id"] in chosen or already(e) or not re.fullmatch(r"(?:[SE]?\d{1,5}|[|])", e["text"].strip()): continue
            row = [x for x in upright if x["line"] == e["line"]]
            if (e["box_px"][1] > (1 - EDGE_SHARE) * p["H"] and any(x["id"] in chosen for x in row)
                    and all(x["id"] in chosen or already(x) or re.fullmatch(r"(?:[SE]?\d{1,5}|[|])", x["text"].strip()) for x in row)):
                chosen[e["id"]] = "folio or divider on a publication footer baseline"
        # Separate only the matching runs. A shared baseline is not evidence
        # that the neighboring column's prose is furniture.
        for ln in list(p["lines"]):
            take = [e for e in ln["runs"] if e["id"] in chosen]
            if not take: continue
            kept = [e for e in ln["runs"] if e["id"] not in chosen]
            if not kept:
                furniture(ln, "; ".join(sorted({chosen[e["id"]] for e in take})))
                ln["local_furniture"] = True
                continue
            ln.update(runs=kept, box=hull([e["box_px"] for e in kept]), text="".join(e["text"] for e in kept), size=max(rsize(e) for e in kept))
            for e in take:
                separate = margin_line(e); furniture(separate, chosen[e["id"]])
                separate["local_furniture"] = True
                p["lines"].append(separate); p["run_line"][e["id"]] = separate
        p["furniture_sources"] = {}
        floated = [all_runs[m] for m in chosen if m not in p["run_line"]]
        if floated:
            ids = {e["id"] for e in floated}
            for kind in ("tables", "blocks"):
                originals = []
                for b in p["d"][kind]:
                    if ids.intersection(b["members"]):
                        originals.append(dict(b))
                        b["members"] = [m for m in b["members"] if m not in ids]
                if originals: p["furniture_sources"][kind] = originals
            for e in floated:
                ln = margin_line(e); furniture(ln, chosen[e["id"]])
                p["lines"].append(ln); p["runs"].append(e); p["run_line"][e["id"]] = ln
                b = dict(id="furniture:" + e["id"], box_px=e["box_px"], members=[e["id"]], kinds=["text"],
                         text_lines=1, text=e["text"], main_text_source="float furniture")
                p["blocks"].append(b); p["d"]["blocks"].append(b.copy())
    # Classify local lines, never a whole mixed block: a recurring page number
    # beside/below prose does not make that prose furniture. Derived blocks are
    # rebuilt on every --paper pass from the original rule-2 membership.
    for p in P:
        separated = []; p["furniture_splits"] = []; p["band_recovered"] = set()
        for b in p["blocks"]:
            furniture = [m for m in b["members"] if p["run_line"][m]["cls"] == "furniture"]
            prose = [m for m in b["members"] if m not in furniture]
            if p["header_protected"].intersection(prose):
                # Retaining an opening must not change the established flow
                # classification of later captions or smaller paragraphs.
                # Recovered blocks already have a separate admission path and
                # supply their column extents to reading order afterwards.
                p["band_recovered"].add(b["id"] + (":text" if furniture else ""))
                opening = [m for m in prose if m in p["header_protected"]]
                remainder = [m for m in prose if m not in p["header_protected"]]
                if not furniture and remainder:
                    # Preserve the established retained fragment and its column
                    # ownership when restoring its opening. The two pieces are
                    # both prose; the recovery metadata also preserves layout
                    # boundaries already used for mixed furniture/prose blocks.
                    p["furniture_splits"].append({"source": b["id"],
                        "parts": [b["id"] + ":opening", b["id"] + ":text"],
                        "why": "header opening restored beside retained text"})
                    for suffix, members in (("opening", opening), ("text", remainder)):
                        part = dict(b, id=b["id"] + ":" + suffix, members=members, main_text_source=b["id"],
                            box_px=hull([e["box_px"] for m in members for e in p["run_line"][m]["runs"] if e["id"] == m]))
                        part["text"] = " ".join(e["text"] for m in members for e in p["run_line"][m]["runs"] if e["id"] == m)[:80]
                        p["band_recovered"].add(part["id"])
                        separated.append(part); p["d"]["blocks"].append(part.copy())
                    continue
            if not furniture or not prose:
                separated.append(b); continue
            furniture_text = "".join(e["text"] for m in furniture for e in p["run_line"][m]["runs"] if e["id"] == m)
            # Removing rotated overlay ink does not expose a new horizontal
            # header/footer band. The surviving prose still witnesses columns.
            overlay = all(p["run_line"][m]["angle"] != 0 or m in p["manuscript_numbers"] for m in furniture)
            if not overlay and not re.fullmatch(r"\s*\d{1,4}\s*", furniture_text): p["band_recovered"].add(b["id"] + ":text")
            p["furniture_splits"].append({"source": b["id"],
                "parts": [b["id"] + ":text", b["id"] + ":furniture"],
                "why": "furniture lines separated from retained text"})
            for suffix, members in (("text", prose), ("furniture", furniture)):
                part = dict(b, id=b["id"] + ":" + suffix, members=members, main_text_source=b["id"],
                    box_px=hull([e["box_px"] for m in members for e in p["run_line"][m]["runs"] if e["id"] == m]))
                part["text"] = " ".join(e["text"] for m in members for e in p["run_line"][m]["runs"] if e["id"] == m)[:80]
                separated.append(part)
                p["d"]["blocks"].append(part.copy())
        p["blocks"] = separated
    split_runin_abstract(front, body)
    split_labelled_abstract(front, body)
    # title and authors on the first page
    flags = []
    p1 = front; cand = [ln for ln in p1["lines"] if ln["cls"] is None]
    title_box = None; author_box = None
    def split_line(ln, keep):
        """rule 1's lines run across the page: the runs of ln not in keep become a line of their own (a sidebar)"""
        off = [e for e in ln["runs"] if e["id"] not in keep]
        if not off or len(off) == len(ln["runs"]): return
        kept = [e for e in ln["runs"] if e["id"] in keep]
        ln.update(runs=kept, box=hull([e["box_px"] for e in kept]), text="".join(e["text"] for e in kept), size=max(rsize(e) for e in kept))
        new = {"angle": ln["angle"], "box": hull([e["box_px"] for e in off]), "text": "".join(e["text"] for e in off), "runs": off, "size": max(rsize(e) for e in off), "cls": "sidebar"}
        p1["lines"].append(new)
        for e in off: p1["run_line"][e["id"]] = new
    if cand:
        big = max(ln["size"] for ln in cand)
        if big < (1 + 2 * tol) * body: flags.append("first page: no text size stands above the body; title not assigned")
        else:
            tl = sorted([ln for ln in cand if ln["size"] >= PARAMS["title_size_share"] * big], key=lambda ln: ln["box"][1])
            title = [tl[0]]
            for ln in tl[1:]:
                if ln["box"][1] - title[-1]["box"][3] <= PARAMS["stack_gap_em"] * big: title.append(ln)
            tr_all = [e for ln in title for e in ln["runs"] if rsize(e) >= PARAMS["title_size_share"] * big]
            X0 = min(e["box_px"][0] for e in tr_all) - big; X1 = max(e["box_px"][2] for e in tr_all) + big
            for ln in title: split_line(ln, {e["id"] for e in ln["runs"] if X0 <= e["box_px"][0] and e["box_px"][2] <= X1})
            for ln in title: ln["cls"] = "title"
            title_box = hull([ln["box"] for ln in title])
            below = [b for b in p1["blocks"] if b["box_px"][1] >= title_box[3] - 1 and ov(b["box_px"][0], b["box_px"][2], title_box[0], title_box[2]) > 0
                     and all(p1["run_line"][m]["cls"] is None for m in b["members"] if m in p1["run_line"])]
            # the author lines set close under the title fall into the title's own block: a block holding
            # title-size text, and lines under that text, has the authors in those lines, and the block
            # below is not searched (it is the abstract or the body)
            tsize = {e["id"] for ln in title for e in ln["runs"] if rsize(e) >= PARAMS["title_size_share"] * big}
            inner = []
            if tsize:
                tbot = max(e["box_px"][3] for ln in title for e in ln["runs"] if e["id"] in tsize)
                for b in p1["blocks"]:
                    if not any(m in tsize for m in b["members"]): continue
                    for m in b["members"]:
                        ln = p1["run_line"].get(m)
                        if ln is not None and ln["cls"] is None and ln["angle"] == 0 and ln["box"][1] >= tbot - 1 and not any(ln is x for x in inner): inner.append(ln)
            # authors in a sidebar beside the title: two or more lines sharing its vertical span, larger than the body
            beside = [b for b in p1["blocks"] if ov(b["box_px"][1], b["box_px"][3], title_box[1], title_box[3]) > 0 and ov(b["box_px"][0], b["box_px"][2], title_box[0], title_box[2]) <= 0
                      and all(p1["run_line"][m]["cls"] in (None, "sidebar") for m in b["members"] if m in p1["run_line"]) and blines(b, p1) >= 2 and bsize(b, p1) >= (1 + 2 * tol) * body]
            def mark_band(bs):
                ids = {m for b in bs for m in b["members"] if m in p1["run_line"]}
                lines = []
                for m in ids:
                    if not any(p1["run_line"][m] is x for x in lines): lines.append(p1["run_line"][m])
                for ln in lines: split_line(ln, ids)
                for m in ids: p1["run_line"][m]["cls"] = "authors"
            if inner:
                tblocks = [b for b in p1["blocks"] if any(m in tsize for m in b["members"])]
                for ln in inner: split_line(ln, {m for b in tblocks for m in b["members"]})
                for ln in inner: ln["cls"] = "authors"
                author_box = hull([ln["box"] for ln in inner])
            elif beside:
                mark_band(beside)
                author_box = hull([b["box_px"] for b in beside])
            elif below:
                first = min(below, key=lambda b: b["box_px"][1]); band = [b for b in below if ov(b["box_px"][1], b["box_px"][3], first["box_px"][1], first["box_px"][3]) > 0]
                s0 = bsize(first, p1); grew = True
                while grew:
                    grew = False; bb = hull([b["box_px"] for b in band])
                    nxt = [b for b in below if b not in band and b["box_px"][1] >= bb[3] - 1 and b["box_px"][1] - bb[3] <= PARAMS["stack_gap_em"] * s0 and abs(bsize(b, p1) - s0) <= tol * s0]
                    if nxt: band.extend(nxt); grew = True
                mark_band(band)
                author_box = hull([b["box_px"] for b in band])
    def block_text(b, p):
        """the block's own runs, line by line (rule 1 lines run across columns; only this block's runs are taken)"""
        by = collections.defaultdict(list)
        for m in b["members"]:
            ln = p["run_line"].get(m)
            if ln is not None: by[id(ln)].append((ln["box"][1], next(e for e in ln["runs"] if e["id"] == m)))
        rows = sorted(by.values(), key=lambda rs: rs[0][0])
        texts = [" ".join(e["text"] for _, e in sorted(rs, key=lambda r: r[1]["box_px"][0])) for rs in rows]
        for lb in b.get("labels", []):   # a margin label's text opens the line it stands beside
            for lm in lb["members"]:
                ln = p["run_line"].get(lm)
                if ln is None or not rows: continue
                k = min(range(len(rows)), key=lambda i: abs(rows[i][0][0] - ln["box"][1]))
                texts[k] = next(e for e in ln["runs"] if e["id"] == lm)["text"] + " " + texts[k]   # the label's own run, not the whole page line
        return "\n".join(texts)
    # columns and the main text, page by page
    first_body_seen = False; prev_reaches_bottom = False; out_pages = []; text_out = []; order_n = 0
    refs_seen = False   # reference section active, until a body heading resumes prose
    abstract = None   # the abstract, while it may still run on at the top of the next page: its column and size
    abstract_tail = None   # rule 7's unfinished abstract, including already-main panels
    ABS_HEAD = re.compile(r"^(abstract|summary)\b", re.I)
    BODY_HEAD = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?(?:acknowledg(?:e)?ments?|conclusions?|"
                           r"appendi(?:x|ces)(?:\s+[A-Z0-9]+)?)(?:\s*[:.]|\s*$)", re.I)
    def prose_panels(p):
        """Resolve panel ownership before page columns, using the saved two-level geometry.

        A region expanded over neighboring text is not a panel boundary. Use its
        actual filled backing; a smaller backing needs an explicit prose heading.
        Every owned block must fit inside. Two or three child columns are allowed.
        Font-change fragments cannot supply columns; the existing two-sided,
        three-line witness test is applied to local copies of the child candidates.
        Nothing is promoted in the rule-1 records or passed back to rules 2-5.
        """
        heading = re.compile(r"^(?:research in context|clinical relevance|key (?:points|messages)|"
                             r"highlights|author summary|conflicts? of interest|disclosures?)\b", re.I)
        panels = []
        for region in p["d"].get("regions", []):
            if region["source"] != "panel": continue
            box = region["box_px"]
            area = (box[2] - box[0]) * (box[3] - box[1])
            fills = [e["box_px"] for e in p["d"]["elements"] if e["kind"] == "fill" and inside(e["box_px"], box, 2)]
            if not fills: continue
            backing = max(fills, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
            expanded = (backing[2] - backing[0]) * (backing[3] - backing[1]) < .7 * area
            if expanded: box = backing
            def overlaps_box(b): return ov(box[0], box[2], b[0], b[2]) > 1 and ov(box[1], box[3], b[1], b[3]) > 1
            if any(overlaps_box(f["box_px"]) for f in p["d"]["floats"]): continue
            if any(e["kind"] == "image" and overlaps_box(e["box_px"]) for e in p["d"]["elements"]): continue
            blocks = [b for b in p["blocks"] if inside(b["box_px"], box, 2)]
            ids = {m for b in blocks for m in b["members"]}
            runs = [e for e in p["runs"] if e["id"] in ids]
            if not runs or any(p["run_line"][e["id"]]["cls"] is not None for e in runs): continue
            if any(is_caption_run(e) for e in runs): continue
            rows = {e["line"] for e in runs}
            if len(rows) < PARAMS["column_min_lines"] or sum(len(e["text"].split()) for e in runs) < 4 * len(rows): continue
            first = " ".join(e["text"] for e in sorted(runs, key=lambda e: (e["line"], e["box_px"][0])))
            named = bool(heading.match(first))
            if expanded and not named: continue
            if re.match(r"^How to cite\b", first, re.I): continue
            if not named and not re.search(r"[A-Za-z][.!?](?:\s|$)", first): continue
            size = bsize({"members": list(ids)}, p)
            if size < (1 - (3 if named else 1) * tol) * body: continue
            # A boxed narrative can resemble a one-row table to rule 3. Only an
            # explicit prose heading permits that ambiguity; captions still veto it.
            if any(overlaps_box(t["box_px"]) for t in p["d"]["tables"]) and not named: continue
            if any(u.get("block") in {b["id"] for b in blocks} for u in p["d"].get("unpaired", [])): continue
            children = [{k: v for k, v in r.items() if k != "deferred"}
                        for r in p["d"].get("regions", []) if r.get("parent") == region["id"] and inside(r["box_px"], box, 2)]
            pairs = region_separations(children, runs)
            supported = set().union(*pairs) if pairs else set()
            columns = []
            for r in sorted(children, key=lambda r: r["box_px"][0]):
                if r["id"] not in supported or r.get("lines", 0) < PARAMS["column_min_lines"]: continue
                x0, _, x1, _ = r["box_px"]
                hit = next((c for c in columns if ov(x0, x1, *c) >= .5 * max(x1 - x0, c[1] - c[0])), None)
                if hit: hit[0] = min(hit[0], x0); hit[1] = max(hit[1], x1)
                else: columns.append([x0, x1])
            if not columns: columns = [[min(e["box_px"][0] for e in runs), max(e["box_px"][2] for e in runs)]]
            panels.append(dict(id=region["id"], box_px=list(box), blocks=[b["id"] for b in blocks],
                               columns=columns, named=named, size_px=size))
        return panels
    for p in P: p["panels"] = prose_panels(p)
    def split_columns(tb, p, cols, panel=False):
        """Split only classified main text at known column gutters empty on every line.

        Each side must fit a known column, with either column_min_lines lines of
        median width at least half the column, or a left edge aligned to the column.
        Short headings therefore need no body-size or line-count exception.
        Numbered display headings with a printed bar separator stay atomic: their
        internal spaces are heading punctuation, not evidence of text columns.
        Panels still require the multi-line witnesses. Runs crossing a gutter veto it, unless their saved
        ink index proves a character-free gap. Tables, float members and captions
        are protected even when an earlier rule also called their block main text.
        The rule 2 blocks remain; derived blocks expose the exact run membership to
        exporters, and the split record retains any divided run for repeatability.
        """
        rid = {e["id"]: e for e in p["runs"]}
        protected = {m for t in p["d"]["tables"] for m in t["members"]}
        protected_blocks = {bid for f in p["d"]["floats"] for bid in f["blocks"]}
        protected_blocks |= {u.get("block") for u in p["d"].get("unpaired", [])}
        gutters = sorted({(a[1], z[0]) for a in cols for z in cols if a[1] < z[0]
                          and not any(a[1] <= c[0] and c[1] <= z[0] for c in cols)})
        result = []; splits = []
        for b in tb:
            if b["cls"] != "main" or b["id"] in protected_blocks or (not panel and protected.intersection(b["members"])):
                result.append(b); continue
            es = [rid[m] for m in b["members"] if m in rid]
            ink = [part for e in es for part in e.get("ink_parts", [e])]
            cuts = []
            for lo, hi in gutters:
                x = (lo + hi) / 2
                if not b["box_px"][0] < x < b["box_px"][2]: continue
                if any(v["box_px"][0] < x < v["box_px"][2] for v in ink): continue
                left = [v["box_px"][2] for v in ink if v["box_px"][2] <= x]
                right = [v["box_px"][0] for v in ink if v["box_px"][0] >= x]
                if not left or not right: continue
                gap = [max(lo, max(left)), min(hi, min(right))]
                if gap[1] - gap[0] >= PARAMS["channel_em"] * body:
                    if not any(gap[0] <= old[1] and old[0] <= gap[1] for old in cuts): cuts.append(gap)
            if not cuts: result.append(b); continue
            if (b["lines"] <= 3 and b["size"] > 1.08 * body and
                re.match(r"^\d+(?:\.\d+)*\s*\|\s*\S", block_text(b, p))):
                # Keep the column evidence available to exporters even though
                # this heading does not split at its internal punctuation.
                p["heading_gutter_veto"] = True
                result.append(b); continue
            xs = sorted((lo + hi) / 2 for lo, hi in cuts)
            groups = [[] for _ in range(len(xs) + 1)]
            divided = []
            for e in es:
                if any(e["box_px"][0] < x < e["box_px"][2] for x in xs):
                    parts = [dict(e, **v, id=e["id"] if i == 0 else e["id"] + f":column:{i+1}")
                             for i, v in enumerate(e["ink_parts"])]
                    for part in parts: part.pop("ink_parts", None)
                    divided.append({"source": e, "parts": [part["id"] for part in parts]})
                else: parts = [e]
                for part in parts:
                    groups[bisect.bisect_right(xs, (part["box_px"][0] + part["box_px"][2]) / 2)].append(part)
            valid = True
            for group in groups:
                if not group: valid = False; break
                box = hull([e["box_px"] for e in group])
                fits = [c for c in cols if c[0] - body <= box[0] and box[2] <= c[1] + body]
                rows = collections.defaultdict(list)
                for e in group: rows[e["line"]].append(e["box_px"])
                if not fits: valid = False; break
                width = min(c[1] - c[0] for c in fits)
                supported = (len(rows) >= PARAMS["column_min_lines"] and
                             statistics.median(hull(row)[2] - hull(row)[0] for row in rows.values()) >= 0.5 * width)
                aligned = not panel and any(abs(box[0] - c[0]) <= body for c in fits)
                if not (supported or aligned): valid = False; break
            if not valid: result.append(b); continue
            replacements = {r["source"]["id"]: [e for g in groups for e in g if e["id"] in r["parts"]] for r in divided}
            p["d"]["elements"] = [v for e in p["d"]["elements"] for v in replacements.get(e["id"], [e])]
            parts = []
            for i, group in enumerate(groups):
                rows = collections.defaultdict(list)
                for e in group: rows[e["line"]].append(e)
                for row in rows.values():
                    ln = dict(angle=0, box=hull([e["box_px"] for e in row]), runs=row, cls=None,
                              size=max(rsize(e) for e in row), text=" ".join(e["text"] for e in row))
                    for e in row: p["run_line"][e["id"]] = ln
                part = dict(b, id=b["id"] + f":column:{i+1}", members=[e["id"] for e in group],
                            box_px=hull([e["box_px"] for e in group]), main_text_source=b["id"])
                part.update(size=bsize(part, p), lines=blines(part, p), text=block_text(part, p))
                p["d"]["blocks"].append(dict(id=part["id"], box_px=part["box_px"], members=part["members"],
                    kinds=["text"], text_lines=part["lines"], text=part["text"], main_text_source=b["id"]))
                parts.append(part)
            result.extend(parts)
            line_parts = collections.defaultdict(list)
            for part, group in zip(parts, groups):
                rows = collections.defaultdict(list)
                for e in group: rows[e["line"]].append(e["id"])
                for line, members in rows.items():
                    line_parts[line].append(dict(block=part["id"], members=members))
            splits.append({"source": b["id"], "parts": [part["id"] for part in parts], "gutters_px": cuts,
                           "runs": divided, "lines": [{"source_line": line, "parts": parts}
                               for line, parts in sorted(line_parts.items()) if len(parts) > 1],
                           "why": "known text columns with no block ink in the gutter on any line"})
        return result, splits
    # the paper's columns: the column extents that recur, within a letter height at both edges, on
    # two or more pages after the title page; a one-page layout (a summary panel) is not the paper's
    clusters = []
    for p in P[1:]:
        for x0, x1 in own_columns(p):
            hit = next((c for c in clusters if abs(c["x0"] - x0) <= body and abs(c["x1"] - x1) <= body), None)
            if hit: hit["n"] += 1; hit["x0"] = (hit["x0"] * (hit["n"] - 1) + x0) / hit["n"]; hit["x1"] = (hit["x1"] * (hit["n"] - 1) + x1) / hit["n"]
            else: clusters.append({"x0": x0, "x1": x1, "n": 1})
    paper_cols = sorted([[c["x0"], c["x1"]] for c in clusters if c["n"] >= 2])
    # R3 (lane stream): when no extent recurs at fixed positions, the columns recur as a pattern at a
    # per-page offset (paper_column_pattern, place_column_pattern).
    paper_pattern = None if paper_cols else paper_column_pattern({p["page"]: own_columns(p) for p in P}, body)
    def pattern_cols(p):
        """the paper's column pattern placed on page p, [] when it does not fit the page"""
        if not paper_pattern: return []
        rules = [e["box_px"] for e in p["d"]["elements"] + p["d"].get("art", []) if e["kind"] == "rule"]
        return place_column_pattern(paper_pattern, p["page"], rules,
                                    [b["box_px"] for b in p["blocks"] if blines(b, p) >= PARAMS["column_min_lines"]], body)
    for p in P:
        body_before = first_body_seen
        page_paper_cols = paper_cols or pattern_cols(p)
        def bcls(b):
            cs = {p["run_line"][m]["cls"] for m in b["members"] if m in p["run_line"]}
            for c in ("title", "authors", "furniture", "rotated", "sidebar"):
                if c in cs: return c
            return None
        tb = [dict(b, size=bsize(b, p), cls=bcls(b), lines=blines(b, p)) for b in p["blocks"]]
        for b in tb:
            if b["cls"] is None and b["id"] in p.get("pull_quotes", ()):
                b["cls"] = "aside"; b["why"] = "pull quote: display-face lines in their own frame beside the body text"
        mark_header_row_references(tb, lambda b: block_text(b, p))
        for b in tb:   # a sidebar split off the title or author lines (rule 6, the title page): front matter
            if b["cls"] == "sidebar": b["cls"] = "other"; b["why"] = "beside the title or authors on the title page"
        for u in p["d"].get("unpaired", []):   # rule 4's caption without its graphic on this page: the float's text, not the body's
            for b in tb:
                if b["cls"] is None and b["id"] == u.get("block"): b["cls"] = "caption"; b["why"] = "rule 4 caption without its graphic on this page"
        # A figure caption set in two columns under its picture (lane r4-captionextent): when the caption's
        # last line ends without closing punctuation, a block in the caption's type (its size within the size
        # tolerance and its face) whose top is level with the caption's top within one line, beside the
        # caption to its right and under the same drawing row (the float's drawing spans it), is the
        # caption's second column: never body text, whatever column it opens. The copier joins it
        # to the caption (caption_column_tail) as a block out of the flow.
        # (the rule 1-5 runs: a float's box can hide part of a block from the lines rule 6 reads)
        el = {e["id"]: e for e in p["d"]["elements"] if e["kind"] == "text"}
        whole = {b["id"]: b for b in p["d"]["blocks"]}
        def own_runs(b): return [el[m] for m in whole.get(b["id"], b)["members"] if m in el]
        def runs_box(es): return [min(e["box_px"][0] for e in es), min(e["box_px"][1] for e in es), max(e["box_px"][2] for e in es), max(e["box_px"][3] for e in es)]
        def runs_size(es):
            ss = [rsize(e) for e in es for _ in e["text"].strip()]
            return statistics.median(ss) if ss else 0
        for f in p["d"].get("floats", []):
            fb = [b for b in tb if b["id"] in f.get("blocks", [])]
            caps = []
            for b in fb:
                es = own_runs(b)
                if not es or any(e["angle"] for e in es): continue
                top = min(e["line"] for e in es)
                first = min((e for e in es if e["line"] == top), key=lambda e: e["box_px"][0])
                if is_caption_run(first) and not re.sub(r"\s+", "", first["text"]).lower().startswith("table"): caps.append((b, es))
            if len(caps) != 1: continue
            cb, ces = caps[0]
            drawn = [b["box_px"] for b in p["d"].get("blocks", []) if b["id"] in f.get("blocks", []) and b["id"] != cb["id"]]
            if not drawn: continue
            G = [min(B[0] for B in drawn), min(B[1] for B in drawn), max(B[2] for B in drawn), max(B[3] for B in drawn)]
            C = runs_box(ces); cs = runs_size(ces)
            last = max(ces, key=lambda e: (e["line"], e["box_px"][0]))
            if re.search(r"[.!?][\])\u201d\u2019'\"]*$", last["text"].strip()) or G[3] > C[1]: continue
            cfaces = collections.Counter(figure_caption_face(e) for e in ces for _ in e["text"].strip())
            for b in tb:
                if b["cls"] is not None or b is cb or b["id"] in f.get("blocks", []): continue
                es = own_runs(b)
                if not es: continue
                B = runs_box(es)
                if any(e["angle"] for e in es) or B[0] <= C[2] or abs(B[1] - C[1]) > cs or abs(runs_size(es) - cs) > tol * cs: continue
                if not (G[0] - cs <= B[0] and B[2] <= G[2] + cs and G[3] <= B[1]): continue
                bfaces = collections.Counter(figure_caption_face(e) for e in es for _ in e["text"].strip())
                if not cfaces or not bfaces or bfaces.most_common(1)[0][0] != cfaces.most_common(1)[0][0]: continue
                b["cls"] = "other"; b["why"] = "a figure caption's second column, beside a caption that ends open"
        cols = own_columns(p)
        # A references heading and successive numbered entries establish their
        # own column even when no body-size paragraph ever occupied that lane.
        for head in tb:
            if head.get("table_header_cell") or not reference_heading(block_text(head, p).split('\n')[0]): continue
            H = head['box_px']
            for b in tb:
                B = b['box_px']
                if b['cls'] is not None or B[1] < H[3] or B[1]-H[3] > 3*body or not B[0]-body <= H[0] <= B[2]: continue
                nums = [int(m[1]) for line in block_text(b, p).split('\n')
                        if (m := re.match(r'^\s*(\d{1,3})[.)]\s+[A-Z]', line))]
                if len(nums) < 3 or any(y != x+1 for x,y in zip(nums,nums[1:])): continue
                if not any(c0-body <= B[0] and B[2] <= c1+body for c0,c1 in cols): cols.append([B[0],B[2]])
        # A tall initial can start a short first column above footnotes. The
        # normal-size lines beside it, followed horizontally by a body column,
        # witness prose even when it has too few lines to infer a column alone.
        if p is front:
            for b in tb:
                es = [e for e in p['runs'] if e['id'] in b['members']]
                if (b['cls'] is None and 2 <= b['lines'] <= 3 and abs(b['size']-body) <= tol*body
                    and any(e.get('size_px',0) >= 1.8*body and e['box_px'][3]-e['box_px'][1] >= 1.8*body for e in es)
                    and any(b['box_px'][2] < c0 and c1-c0 > 10*body for c0,c1 in cols)):
                    cols.append([b['box_px'][0],b['box_px'][2]])
        if p is not front:   # after the title page the paper's columns count too (a references column beside the last body column)
            for c in page_paper_cols:
                if not any(ov(c[0], c[1], x0, x1) >= 0.5 * min(c[1] - c[0], x1 - x0) for x0, x1 in cols): cols.append(list(c))
            cols.sort()
        # A smaller body section can switch from one wide column to two narrow
        # ones. Its long prose witnesses those extents inside the known text
        # frame; admitting the text without its columns would interleave it.
        section_cols = []
        if p is not front:
            for b in tb:
                if b["cls"] is not None or b["size"] >= (1 - tol) * body or not long_prose(b, p): continue
                x0, _, x1, _ = b["box_px"]
                if not any(c0 - body <= x0 and x1 <= c1 + body and x1 - x0 < .75 * (c1 - c0)
                           for c0, c1 in cols + page_paper_cols): continue
                hit = next((c for c in section_cols if ov(x0, x1, *c) >= .5 * max(x1 - x0, c[1] - c[0])), None)
                if hit: hit[0] = min(hit[0], x0); hit[1] = max(hit[1], x1)
                else: section_cols.append([x0, x1])
            section_cols = [c for c in section_cols if not any(abs(c[0] - c0) <= body and abs(c[1] - c1) <= body for c0, c1 in cols)]
            cols.extend(section_cols); cols.sort()
        def section_heading(b):
            first = block_text(b, p).split("\n")[0]
            es = [e for m in b["members"] for e in p["run_line"][m]["runs"] if e["id"] == m]
            top = min((e["line"] for e in es), default=None)
            return (len(first) < 100 and not re.search(r"[.!?]$", first)
                    and any(re.search(r"bold|italic|oblique|[-_,](?:b|bi|i)$", str(e.get("font", "")), re.I)
                            for e in es if e["line"] == top))
        page_top = p["header_bottom"] if p["header_bottom"] is not None else min((ln["box"][1] for ln in p["lines"] if ln["cls"] is None), default=0)
        def col_of(b):
            fits = [c for c in cols if ov(b["box_px"][0], b["box_px"][2], c[0], c[1]) >= 0.5 * (b["box_px"][2] - b["box_px"][0])]
            return min(fits, key=lambda c: c[1] - c[0]) if fits else None
        for b in tb:
            if b["cls"] is None and p is front and title_box is not None and b["box_px"][3] <= title_box[3]: b["cls"] = "other"; b["why"] = "above the title on the title page"
        for ci, (c0, c1) in enumerate(cols):
            inb = sorted([b for b in tb if b["cls"] is None and b["id"] not in p["band_recovered"] and col_of(b) == [c0, c1]], key=lambda b: b["box_px"][1])
            if not inb and section_cols: continue   # an unused wider column does not break the smaller section
            # Local footer cleanup must not create new cross-page body-flow
            # evidence (for example, admitting diagram labels on the next page).
            col_bottom = max((ln["box"][3] for ln in p["lines"] if (ln["cls"] != "furniture" or ln.get("local_furniture")) and ln["angle"] == 0 and ov(ln["box"][0], ln["box"][2], c0, c1) > 0), default=page_top)
            last = None
            for k, b in enumerate(inb):
                s = b["size"]
                def mark(v): return v if last is None else max(last, v)
                if s >= (1 - tol) * body: b["cls"] = "main"; first_body_seen = True; last = mark(b["box_px"][3]); b["why"] = "body size in a column"
                elif body_face_prose(b, p): b["cls"] = "main"; first_body_seen = True; last = mark(b["box_px"][3]); b["why"] = "body face prose in a column"
                elif p is front: b["cls"] = "other"; b["why"] = "smaller text on the title page: front matter"
                elif first_body_seen and long_prose(b, p) and (last is not None or section_heading(b)
                        or (k and section_heading(inb[k - 1])) or (k == 0 and prev_reaches_bottom)):
                    b["cls"] = "main"; last = mark(b["box_px"][3]); b["why"] = "smaller section in the flow"
                    if k and inb[k - 1]["cls"] == "other" and section_heading(inb[k - 1]):
                        inb[k - 1].update(cls="main", why="heading of a smaller section in the flow")
                elif first_body_seen and last is not None and b["box_px"][1] - last <= PARAMS["flow_gap_em"] * s: b["cls"] = "main"; last = mark(b["box_px"][3]); b["why"] = "smaller, stacked under main text"
                elif first_body_seen and last is None and k == 0 and prev_reaches_bottom: b["cls"] = "main"; last = mark(b["box_px"][3]); b["why"] = "smaller, opens the column after a full one"
                else: b["cls"] = "other"; b["why"] = "smaller, not in the flow"
            prev_reaches_bottom = last is not None and last >= col_bottom - PARAMS["flow_gap_em"] * body
        # Classify newly retained fragments after the established columns have
        # flowed. An earlier layout's recovered prose must not reset the flow
        # of a later column (and drop lines it already admitted). These extents
        # join the reading-order view below, without displacing column evidence.
        for b in tb:
            if b["cls"] is not None or b["id"] not in p["band_recovered"]: continue
            kept_heading = (p["header_protected"].intersection(b["members"])
                            and any(ov(b["box_px"][0], b["box_px"][2], c0, c1) >= .5 * (b["box_px"][2] - b["box_px"][0])
                                    for c0, c1 in p["band_columns"]))
            if b["size"] >= (1 - tol) * body and (col_of(b) is not None or b["lines"] >= PARAMS["column_min_lines"] or kept_heading):
                b.update(cls="main", why="body text retained outside the furniture band"); first_body_seen = True
            elif p is not front and long_prose(b, p) and col_of(b) is not None:
                before = [m for m in tb if m["cls"] == "main" and col_of(m) == col_of(b) and m["box_px"][3] <= b["box_px"][1]]
                if before or section_heading(b): b.update(cls="main", why="smaller section in the flow")
            if b["cls"] is None: b.update(cls="other", why="smaller text retained outside the furniture band")
        # A short styled heading belongs with the main paragraph directly below
        # it in the same column, even when the heading uses smaller type.
        protected = {m for t in p["d"]["tables"] for m in t["members"]}
        def heading_size(b):
            # lane r3-headband: a line in fake small capitals (rule 1's lead_size_px) is measured at its first letter
            es = [e for m in b["members"] if m in p["run_line"] for e in p["run_line"][m]["runs"] if e["id"] == m]
            return max([b["size"]] + [e["lead_size_px"] for e in es if e.get("lead_size_px")])
        # lane r3-headband: a heading at the top of a body column is in that column. Body text kept outside the
        # furniture band can be the only witness of its column, whose extent joins the page's columns only after
        # classification (below); a short styled block left unclassified directly above that text, inside its
        # extent with nothing between them, opens the column.
        late = [m for m in tb if m["id"] in p["band_recovered"] and m["cls"] == "main" and m["lines"] >= PARAMS["column_min_lines"]
                and not any(abs(m["box_px"][0] - c0) <= body and abs(m["box_px"][2] - c1) <= body for c0, c1 in cols)]
        for b in tb:
            if not late or b["cls"] is not None or b["lines"] > 3 or heading_size(b) < .7 * body or not section_heading(b): continue
            if re.search(r"[.!?]\s*$", block_text(b, p)) or len(block_text(b, p).split()) > 30 or protected.intersection(b["members"]): continue
            x0, _, x1, y1 = b["box_px"]
            for m in late:
                M = m["box_px"]
                if ov(x0, x1, M[0], M[2]) < .5 * (x1 - x0) or M[1] < y1 or M[1] - y1 > PARAMS["flow_gap_em"] * max(b["size"], m["size"]): continue
                if any(o is not b and o is not m and o["cls"] != "furniture" and ov(o["box_px"][0], o["box_px"][2], M[0], M[2]) > 0
                       and o["box_px"][1] >= y1 - 1 and o["box_px"][3] <= M[1] + 1 for o in tb): continue
                b.update(cls="main", why="heading before main text in its column"); break
        for b in tb:
            if b["cls"] != "other" or b["lines"] > 3 or heading_size(b) < .7 * body or not section_heading(b): continue
            if re.search(r"[.!?]\s*$", block_text(b, p)) or len(block_text(b, p).split()) > 30: continue
            if protected.intersection(b["members"]) or col_of(b) is None: continue
            below = sorted([m for m in tb if m is not b and col_of(m) == col_of(b)
                            and m["box_px"][1] >= b["box_px"][3]], key=lambda m: m["box_px"][1])
            if below and below[0]["cls"] == "main" and below[0]["box_px"][1] - b["box_px"][3] <= 2 * body:
                b.update(cls="main", why="heading before main text in its column")
        # Section state follows the same bands and columns as rule 7. A reference
        # heading can start a page-wide section below body columns, or begin in a
        # single column. Earlier blocks on that page remain body at any size.
        def in_list(b): return b["cls"] in ("main", "other") and (b["cls"] == "main" or (b.get("why") or "").startswith("smaller")) and col_of(b) is not None
        body_top = min((b["box_px"][1] for b in tb if b["cls"] == "main"), default=0)
        def section_text(b):
            if not in_list(b): return False
            if b["cls"] == "main": return True
            text = block_text(b, p).split("\n")[0]
            if reference_heading(text) and not b.get("table_header_cell"): return True
            # Publication metadata and page-margin labels are not body sections.
            if b["box_px"][3] < body_top or b["box_px"][1] > .94 * p["H"]: return False
            return not re.match(r"^(?:citation|copyright|doi|received|accepted|published|competing interests)\s*[:©]", text, re.I)
        candidates = [b for b in tb if in_list(b)]
        has_head = first_body_seen and any(reference_heading(block_text(b, p).split("\n")[0]) and not b.get("table_header_cell") for b in candidates)
        if has_head or refs_seen:
            sequence, _ = reading_order_bands(candidates, cols, body, [f["box_px"] for f in p["d"]["floats"]])
            for b in sequence:
                first_line = block_text(b, p).split("\n")[0]
                if reference_heading(first_line) and not b.get("table_header_cell"): refs_seen = True
                elif BODY_HEAD.match(first_line): refs_seen = False
                if not refs_seen and not section_text(b): continue
                b["in_refs"] = refs_seen
                if b["cls"] != "main":
                    b.update(cls="main", why="the reference section" if refs_seen else "body section beside the reference list")
            if refs_seen: prev_reaches_bottom = True
        for b in tb:
            if b["cls"] is None: b["cls"] = "aside"; b["why"] = "outside every text column"
        # the abstract: before the body has begun, a block whose first line opens with the abstract heading
        # starts it; the heading and the blocks under it at the abstract's own size, in its column and
        # directly stacked (flow_gap_em), are main text, and while it reaches the last of them it runs on at
        # the top of the next page at that size and in that column
        def loose(b): return b["cls"] in ("aside", "other") and (b.get("why") or "") in ("outside every text column", "smaller text on the title page: front matter", "smaller, not in the flow")
        def in_abs_col(b, a): return ov(b["box_px"][0], b["box_px"][2], a["x0"], a["x1"]) >= 0.5 * (b["box_px"][2] - b["box_px"][0])
        def take(b, why): b["cls"] = "main"; b["why"] = why
        if abstract is not None:   # its continuation at the top of this page
            a = abstract; abstract = None; lastb = None
            for b in sorted([b for b in tb if b["cls"] not in ("furniture",) and in_abs_col(b, a)], key=lambda b: b["box_px"][1]):
                sub = blines(b, p) == 1 and (1 - tol) * a["size"] <= b["size"] <= (1 + tol) * a.get("head", a["size"])   # a subheading of a structured abstract
                if not (loose(b) and (abs(b["size"] - a["size"]) <= tol * a["size"] or sub)): break
                if lastb is not None and b["box_px"][1] - lastb > PARAMS["flow_gap_em"] * max(b["size"], a["size"]): break
                take(b, "the abstract, run on from the page before"); lastb = b["box_px"][3]
        elif not body_before:
            for h in sorted([b for b in tb if loose(b) or b["cls"] == "main"], key=lambda b: b["box_px"][1]):
                if not ABS_HEAD.match(block_text(h, p).split("\n")[0].strip()): continue
                proof_front = p is front and any(e.get('furniture_reason') ==
                    'large diagonal watermark crossing the page body' for e in p['runs'])
                if h["cls"] == "main" and not proof_front: break
                # Proof front matter may set only the heading in body-sized
                # type. Its aligned smaller paragraph still needs admission.
                under = sorted([b for b in tb if loose(b) and b is not h and b["box_px"][1] >= h["box_px"][3] - 1
                                and ov(b["box_px"][0], b["box_px"][2], h["box_px"][0], h["box_px"][2]) > 0], key=lambda b: b["box_px"][1])
                if not under or abs(under[0]["box_px"][0] - h["box_px"][0]) > h["size"]:   # its text starts at the heading's left edge
                    if not (loose(h) and blines(h, p) >= 2): break
                    # the heading runs in with the text in one block: that block is the abstract
                    a = {"x0": h["box_px"][0], "x1": h["box_px"][2], "size": h["size"], "head": h["size"]}; take(h, "the abstract (its heading runs in)")
                    under = []
                else:
                    a = {"x0": min(h["box_px"][0], under[0]["box_px"][0]), "x1": max(h["box_px"][2], under[0]["box_px"][2]), "size": under[0]["size"], "head": h["size"]}
                    if loose(h): take(h, "the abstract heading")
                lastb = h["box_px"][3]; lasts = h["size"]; reached = True   # the gap under a block is measured in the larger of its size and the next one's
                for b in sorted([b for b in tb if loose(b) and b is not h and b["box_px"][1] >= h["box_px"][3] - 1 and in_abs_col(b, a)], key=lambda b: b["box_px"][1]):
                    sub = blines(b, p) == 1 and (1 - tol) * a["size"] <= b["size"] <= (1 + tol) * a["head"]   # a subheading of a structured abstract (Methods, Results ...)
                    if (abs(b["size"] - a["size"]) > tol * a["size"] and not sub) or b["box_px"][1] - lastb > PARAMS["flow_gap_em"] * max(lasts, b["size"]): reached = False; break
                    take(b, "the abstract subheading" if sub and abs(b["size"] - a["size"]) > tol * a["size"] else "the abstract"); lastb = b["box_px"][3]; lasts = b["size"]
                below = [b for b in tb if b["cls"] not in ("furniture",) and in_abs_col(b, a) and b["box_px"][1] > lastb]
                if reached and not below: abstract = a   # the abstract reaches the foot of its column: it may run on
                break
        abstract_regions = []
        if p is front:
            structured_abstract_blocks(tb, body, lambda b: block_text(b, p))
            abstract_regions = side_abstract_blocks(tb, p['d']['elements'], body, lambda b: block_text(b, p))
        if p is front:   # drawn-only blocks inside the title or author band (an ORCID icon beside a name) go with the band
            for b in p["d"]["blocks"]:
                if any(m in p["run_line"] for m in b["members"]) or not any(m.split(":")[0] in ("image", "outline", "fill", "rule") for m in b["members"]): continue
                for box, cls in ((title_box, "title"), (author_box, "authors")):
                    if box and inside(b["box_px"], box, PARAMS["band_tolerance_em"] * body): tb.append(dict(b, size=0, cls=cls, lines=0, why="drawn object inside the " + cls + " band", text="")); break
        for b in tb:
            if b["id"] in p["band_recovered"] and b["cls"] == "main" and b["lines"] >= PARAMS["column_min_lines"]:
                x0, _, x1, _ = b["box_px"]
                if not any(abs(x0 - c0) <= body and abs(x1 - c1) <= body for c0, c1 in cols): cols.append([x0, x1])
        cols.sort()
        near = PARAMS["column_indent_em"] * body
        order_cols = [list(c) for c in cols] + [list(c) for c in page_paper_cols if not any(abs(c[0] - x0) <= near and abs(c[1] - x1) <= near for x0, x1 in cols)]
        panels = []; panel_splits = []; panel_blocks = []
        for candidate in p["panels"]:
            members = [b for b in tb if b["id"] in candidate["blocks"]]
            if not members or any(b["cls"] not in ("main", "aside", "other") for b in members): continue
            if not candidate["named"] and not all(b["cls"] == "main" for b in members): continue
            if not any(b["cls"] == "main" for b in members):
                # Do not newly insert a sidebar between a paragraph and its
                # continuation in the next column. Such notes retain their
                # ordinary class until the exporter can defer text panels.
                before, _ = reading_order_bands([b for b in tb if b["cls"] == "main"] + members, order_cols, body)
                index = next(i for i, b in enumerate(before) if b in members)
                if index and not re.search(r"[.!?:][\"'’”)]*\s*$", block_text(before[index - 1], p)): continue
            for b in members:
                b.update(cls="main", why="body prose in an atomic panel")
                b["in_refs"] = False
            parts, divided = split_columns(members, p, candidate["columns"], panel=True)
            panel_splits.extend(divided); panel_blocks.extend(parts)
            panels.append({k: v for k, v in dict(candidate, blocks=[b["id"] for b in parts]).items() if k not in ("named", "size_px")})
        panel_ids = {bid for panel in p["panels"] if any(pan["id"] == panel["id"] for pan in panels) for bid in panel["blocks"]}
        multicolumn_ids = {bid for candidate in p["panels"] if len(candidate["columns"]) > 1
                           and any(panel["id"] == candidate["id"] for panel in panels) for bid in candidate["blocks"]}
        if multicolumn_ids:
            # Panels may establish their prose classification at the page's
            # body size, but their child columns never establish page columns.
            page_cols = own_columns(p, multicolumn_ids)
            order_cols = [list(c) for c in page_cols] + [list(c) for c in page_paper_cols
                          if not any(abs(c[0] - x0) <= near and abs(c[1] - x1) <= near for x0, x1 in page_cols)]
        tb, splits = split_columns([b for b in tb if b["id"] not in panel_ids], p, order_cols)
        tb += panel_blocks; splits += panel_splits
        if splits or p.get("heading_gutter_veto"): cols = sorted(order_cols)   # exporters need the same column evidence as rule 7
        mains = [m for m in tb if m["cls"] == "main"]
        for b in tb:   # hanging reference numbers and detached symbols beside the body on a reference-section page
            label = b.get("in_refs") or (b.get("in_refs") is False and not re.search(r"\w", block_text(b, p)))
            if label and b["box_px"][2] - b["box_px"][0] <= PARAMS["flow_gap_em"] * b["size"]:
                for m in mains:
                    if m is b or abs(m["size"] - b["size"]) > tol * body or m["box_px"][2] - m["box_px"][0] <= PARAMS["flow_gap_em"] * m["size"]: continue
                    if m["box_px"][1] - 0.5 * b["size"] <= b["box_px"][1] and b["box_px"][3] <= m["box_px"][3] + 0.5 * b["size"] and \
                       (0 <= m["box_px"][0] - b["box_px"][2] <= PARAMS["flow_gap_em"] * b["size"] or
                        (m["box_px"][0] - PARAMS["flow_gap_em"] * b["size"] <= b["box_px"][0] and b["box_px"][2] <= m["box_px"][0] + PARAMS["flow_gap_em"] * b["size"])):
                        b["why"] = "label beside main text of its size"; break
        for b in tb:   # a hanging label beside main text of its size (reference numbers in the margin)
            if b["cls"] != "aside": continue
            for m in mains:
                if abs(m["size"] - b["size"]) <= tol * body and m["box_px"][1] - 0.5 * b["size"] <= b["box_px"][1] and b["box_px"][3] <= m["box_px"][3] + 0.5 * b["size"] and m["box_px"][0] - PARAMS["flow_gap_em"] * b["size"] <= b["box_px"][0] and b["box_px"][2] <= m["box_px"][0] + PARAMS["flow_gap_em"] * b["size"]:
                    b["cls"] = "main"; b["why"] = "label beside main text of its size"; break
        # Margin labels are a column property (D4 rules 1-2): three or more one-line bare-number blocks (at most
        # three digits) sharing a left edge within half a letter height, each level with the first row of a
        # wider main block of its size to its right, establish a label column, and every member is its block's
        # label whatever its distance from the text (measured: AN10, a web print whose one-digit labels stand
        # 3.0-3.5 em from the entries, past flow_gap_em, and whose two-digit labels formed a column of their own).
        # Nearly every member must pair with a first row: manuscript line numbers sit beside every row and fail.
        # A label is never ordered alone: rule 7 leaves these blocks out of the reading order and the copier
        # prefixes each to its block's first row.
        bare = [b for b in tb if b["cls"] in ("main", "aside", "other") and b["lines"] == 1
                and re.fullmatch(r"\d{1,3}\.?", block_text(b, p).strip())]
        stacks = []
        for b in sorted(bare, key=lambda b: b["box_px"][0]):
            s = next((s for s in stacks if abs(s[0]["box_px"][0] - b["box_px"][0]) <= 0.5 * b["size"]), None)
            if s is None: stacks.append([b])
            else: s.append(b)
        for stack in stacks:
            if len(stack) < PARAMS["column_min_lines"]: continue
            pairs = []
            for b in stack:
                hosts = [m for m in mains if m is not b and m.get("why") != "label beside main text of its size"
                         and m["box_px"][2] - m["box_px"][0] > PARAMS["flow_gap_em"] * m["size"]
                         and m["box_px"][0] >= b["box_px"][2] and abs(m["box_px"][1] - b["box_px"][1]) <= 0.5 * b["size"]
                         and abs(m["size"] - b["size"]) <= tol * body]
                if len(hosts) == 1: pairs.append((b, hosts[0]))
            if len(pairs) < PARAMS["column_min_lines"] or len(pairs) < 0.8 * len(stack): continue
            # once the column is established, a member level with a later row of a wider main block of its size
            # (two entries stacked into one block) labels that block at that row
            paired = {id(b) for b, _ in pairs}
            for b in stack:
                if id(b) in paired: continue
                hosts = [m for m in mains if m is not b and m.get("why") != "label beside main text of its size"
                         and m["box_px"][2] - m["box_px"][0] > PARAMS["flow_gap_em"] * m["size"]
                         and m["box_px"][0] >= b["box_px"][2] and m["box_px"][1] - 0.5 * b["size"] <= b["box_px"][1]
                         and b["box_px"][3] <= m["box_px"][3] + 0.5 * b["size"] and abs(m["size"] - b["size"]) <= tol * body]
                if len(hosts) == 1: pairs.append((b, hosts[0]))
            for b, m in pairs:
                b.update(cls="main", why="label beside main text of its size", label_of=m["id"])
                if "in_refs" in m: b["in_refs"] = m["in_refs"]
        introduced_list_columns(tb, order_cols, body, lambda b: block_text(b, p))
        # rule 7: the page's main text in reading order, continuing the paper's count
        front_columns = None
        if p is front:
            following = next((q['d'] for q in P if q['page'] > p['page']), None)
            front_columns = reading_order_front_columns(tb, p['d']['elements'], following, title_box)
            if front_columns:
                for bid in front_columns['body_blocks'] + front_columns['abstract_blocks']:
                    b = next(b for b in tb if b['id']==bid)
                    col = [b['box_px'][0],b['box_px'][2]]
                    if col not in cols: cols.append(col)
                    if col not in order_cols: order_cols.append(col)
                cols.sort(); order_cols.sort()
                summary_box = next(b['box_px'] for b in tb if b['id'] in front_columns['abstract_blocks'])
                abstract_regions.append(dict(blocks=front_columns['abstract_blocks'],
                                             box_px=summary_box, columns=[summary_box[::2]]))
                author_box = hull([b['box_px'] for b in tb if b['id'] in front_columns['author_blocks']])
                first_body_seen = True
        reading_order_opening_headings(tb, order_cols, body,
            [f["box_px"] for f in p["d"]["floats"] + p["d"]["tables"]] + [q["box_px"] for q in panels])
        ordered, bounds = reading_order_bands([m for m in tb if m["cls"] == "main"], order_cols, body, [f["box_px"] for f in p["d"]["floats"]], panels)
        if p["furniture_splits"] and any(b.get("main_text_source") and b["cls"] == "main" for b in tb) and not panels:
            # A recovered column can belong to a different layout above a wide
            # heading. Supply rule 7 with each layout's own column witnesses;
            # otherwise a narrow column below can capture a short line above.
            # Only a large spanning heading at a completely clear horizontal
            # gap separates these layouts; a gap alone is never a boundary.
            mains = [b for b in tb if b["cls"] == "main"]
            floats = [f["box_px"] for f in p["d"]["floats"]]
            starts = sorted({b["box_px"][1] for b in mains if b["lines"] <= 3 and b["size"] > (1 + 2 * tol) * body
                and any(b["box_px"][2] - b["box_px"][0] > c1 - c0 + body
                        and ov(b["box_px"][0], b["box_px"][2], c0, c1) > body for c0, c1 in order_cols)
                and not any(x[1] < b["box_px"][1] < x[3] for x in [m["box_px"] for m in mains if m is not b] + floats)})
            edges = [-1e9] + starts + [1e9]; ordered = []; bounds = list(starts)
            for lo, hi in zip(edges, edges[1:]):
                band = [b for b in mains if lo <= b["box_px"][1] < hi]
                if not band: continue
                heads = [b for b in band if b["box_px"][1] == lo and b["lines"] <= 3 and b["size"] > (1 + 2 * tol) * body]
                witnesses = [b for b in band if b not in heads and b["lines"] >= PARAMS["column_min_lines"]]
                local_cols = []
                for b in sorted(witnesses, key=lambda b: b["box_px"][0]):
                    x0, _, x1, _ = b["box_px"]
                    hit = next((c for c in local_cols if ov(x0, x1, *c) >= .5 * max(x1 - x0, c[1] - c[0])), None)
                    if hit: hit[0] = min(hit[0], x0); hit[1] = max(hit[1], x1)
                    else: local_cols.append([x0, x1])
                children, inner = reading_order_bands([b for b in band if b not in heads], local_cols or order_cols, body,
                    [f for f in floats if lo <= f[1] < hi])
                ordered.extend(sorted(heads, key=lambda b: b["box_px"][0]) + children); bounds.extend(inner)
            bounds.sort()
        if not body_before:
            ordered, abstract_cut = reading_order_abstract_columns(ordered, body, lambda b: block_text(b, p),
                                                                   [f["box_px"] for f in p["d"]["floats"]])
            if abstract_cut is not None: bounds = sorted(bounds + [abstract_cut])
        def order_rows(b):
            by = collections.defaultdict(list)
            for m in b["members"]:
                ln = p["run_line"].get(m)
                if ln is not None: by[id(ln)].append(next(e for e in ln["runs"] if e["id"] == m))
            return [sorted(row, key=lambda e: e["box_px"][0]) for row in
                    sorted(by.values(), key=lambda row: min(e["box_px"][1] for e in row))]
        previous_text = "" if not out_pages else previous_order_text
        captioned_lists = reading_order_captioned_lists(tb, order_cols, body, lambda b: block_text(b, p),
                                                       p["d"]["floats"], panels)
        flow_groups = panels + captioned_lists
        ordered, flow_splits = reading_order_defer_panels(ordered, flow_groups, body, lambda b: block_text(b, p),
                                                        order_rows, previous_text, order_n)
        if flow_splits:
            replaced = {s["source"] for s in flow_splits}; parts = {bid for s in flow_splits for bid in s["parts"]}
            tb = [b for b in tb if b["id"] not in replaced] + [b for b in ordered if b["id"] in parts]
            for b in ordered:
                if b["id"] in parts:
                    p["d"]["blocks"].append(dict(id=b["id"], box_px=b["box_px"], members=b["members"],
                        kinds=["text"], text_lines=b["lines"], text=b["text"], main_text_source=b["main_text_source"]))
            splits += flow_splits
        if abstract_regions:
            abstract_order = {bid:i for region in abstract_regions for i,bid in enumerate(region['blocks'])}
            ordered = sorted((b for b in ordered if b.get('side_abstract')), key=lambda b:abstract_order[b['id']]) + [b for b in ordered if not b.get('side_abstract')]
        ordered, abstract_tail = reading_order_abstract_flow(ordered, tb, abstract_tail,
                                                            order_rows, lambda b:block_text(b,p),
                                                            allow_open=p is front or not body_before)
        tb, translations, translation_splits = translated_abstract_blocks(tb, p['d']['elements'], lambda b:block_text(b,p))
        if translations:
            retained = {b['id'] for b in tb if b['cls']=='main' and not b.get('translation_role')}
            ordered = [b for b in ordered if b['id'] in retained] + translations
            refs_seen = False
            for b in translations:
                b.update(size=bsize(b,p), lines=blines(b,p), text=block_text(b,p))
                if b.get('main_text_source'):
                    p['d']['blocks'].append(dict(id=b['id'], box_px=b['box_px'], members=b['members'],
                        kinds=['text'], text_lines=b['lines'], text=b['text'], main_text_source=b['main_text_source']))
            splits += translation_splits
        tb, ordered, ownership, notes, ownership_splits, retained = sort_main_ownership(
            p['d'], tb, ordered, body, front=p is front)
        splits += ownership_splits
        # lane r5-wrap: text on both sides of a picture (O32), which way its lines run (O33), doubt (O34).  Across a
        # picture set inside one measure, each row's left piece is followed by its right piece: the copier reads a
        # block's rows left to right, so the blocks holding the pieces become one block.  Each side read down is
        # left to the column order where the picture stands between two columns; elsewhere the place is listed as
        # doubtful and the printed order is kept.
        wrap_recs = []
        wrap_mains = [b for b in tb if b["cls"] == "main"]
        wrap_block = {m: b for b in wrap_mains for m in b["members"]}
        wrap_runs = [e for e in p["runs"] if e["id"] in wrap_block]
        wrap_frame = (max(b["box_px"][2] for b in wrap_mains) - min(b["box_px"][0] for b in wrap_mains)) if wrap_mains else 0
        for w in wrap_places(wrap_runs, wrap_pictures(p["d"]["elements"], p["d"].get("art", []), p["d"]["floats"], wrap_frame, body), body, tol,
                                {m: b["id"] for m, b in wrap_block.items()},
                                [(a[1], z[0]) for a in order_cols for z in order_cols if a[1] < z[0]
                                 and not any(a[1] <= c[0] and c[1] <= z[0] for c in order_cols)]):
            def wtext(rs): return " ".join(e["text"].strip() for e in rs)
            def wtop(rs): return min(e["box_px"][1] for e in rs)
            direction, vd, va = wrap_direction([(wtext(l), wtext(r), wtop(l)) for l, r in w["rows"]],
                                               [(wtext(l), wtop(l)) for l in w["left"]], wrap_vocab)
            B = w["box_px"]; cx = (B[0] + B[2]) / 2
            wt = min(e["box_px"][1] for l, r in w["rows"] for e in l + r)
            wb = max(e["box_px"][3] for l, r in w["rows"] for e in l + r)
            # inside one measure: a main-text line just above or below the wrap runs across the picture's middle
            measure = any(e["box_px"][0] < cx < e["box_px"][2] and (0 <= wt - e["box_px"][3] <= 2.5 * body or 0 <= e["box_px"][1] - wb <= 2.5 * body)
                          for e in wrap_runs)
            left_ids = {e["id"] for l in w["left"] for e in l}
            piece_ids = left_ids | {e["id"] for r in w["right"] for e in r}
            S = [b for b in ordered if piece_ids.intersection(b["members"])]
            wrec = dict(box_px=B, rows=len(w["rows"]), direction=direction, votes=[vd, va],
                       layout="measure" if measure else "columns", blocks=[b["id"] for b in S], action="none", doubt=None)
            if direction == "unclear":
                wrec["doubt"] = ["O34", "wrap_order_unclear"]
            elif direction == "across" and not measure:
                wrec["doubt"] = ["O34", "wrap_across_against_columns"]
            elif direction == "down" and measure:
                wrec["doubt"] = ["O33", "wrap_down_in_measure_kept"]
            elif direction == "across" and len(S) > 1:
                lead = max(S, key=lambda b: len(left_ids.intersection(b["members"])))
                # every other block holds wrap pieces only, so taking it into the lead block moves no other text
                if all(set(b["members"]) <= piece_ids for b in S if b is not lead):
                    members = [m for b in S for m in b["members"]]
                    merged = dict(lead, id=lead["id"] + ":wrap:1", members=members, main_text_source=lead["id"],
                                  box_px=hull([b["box_px"] for b in S]), why="wrap: rows read across the picture (O33)")
                    merged.update(size=bsize(merged, p), lines=blines(merged, p), text=block_text(merged, p))
                    p["d"]["blocks"].append(dict(id=merged["id"], box_px=merged["box_px"], members=merged["members"],
                        kinds=["text"], text_lines=merged["lines"], text=merged["text"], main_text_source=lead["id"]))
                    ordered = [merged if b is lead else b for b in ordered if b is lead or b not in S]
                    tb = [b for b in tb if b not in S] + [merged]
                    wrec["action"] = "merged"
                else:
                    wrec["doubt"] = ["O33", "wrap_blocks_apart"]
            wrap_recs.append(wrec)
        for b in ordered: order_n += 1; b["order"] = order_n
        for panel in panels:
            panel["blocks"] = [b["id"] for b in ordered if b["id"] in panel["blocks"]]
            panel["order"] = min(b["order"] for b in ordered if b["id"] in panel["blocks"])
        grouped = {bid for group in flow_groups for bid in group["blocks"]}
        for group in captioned_lists:
            start = next(i for i, b in enumerate(ordered) if b["id"] in group["blocks"])
            group["after_block"] = next((b["id"] for b in reversed(ordered[:start]) if b["id"] not in grouped), None)
            if group.get("move"):
                group["move"].update({"from": group["move"]["from_order"], "to": group["move"]["to_order"]})
        previous_order_text = (block_text(ordered[-1], p) if ordered and
                               ordered[-1]["id"] not in grouped else "")
        text_out.append(f"\n## page {p['page']}\n"); text_out += [f"[{b['order']}] " + block_text(b, p) + "\n" for b in ordered]
        # Keep nonbody words in a separately labelled source inventory. This
        # text export is also the vocabulary-conservation input; body order is
        # only the cls=main stream recorded above and in body-order.json.
        if retained:
            text_out.append('## owned notes, tables and article information (outside body order)\n')
            text_out += [block_text(b, p) + '\n' for b in retained]
        # the copies
        clean = p["file"][:-5] + "-clean.png"
        if draw and os.path.exists(clean):
            font = ImageFont.load_default()
            im = Image.open(clean).convert("RGB"); mt = im.copy(); ot = im.copy(); dm = ImageDraw.Draw(mt, "RGBA"); do = ImageDraw.Draw(ot, "RGBA")
            colour = {"main": (0, 110, 0), "furniture": (120, 120, 120), "title": (200, 0, 120), "authors": (200, 100, 0), "rotated": (120, 120, 120), "other": (0, 90, 180), "aside": (0, 90, 180), "caption": (160, 0, 200)}
            for b in tb:
                x = [int(v) for v in b["box_px"]]
                if b["cls"] == "main":
                    dm.rectangle([x[0]-5, x[1]-5, x[2]+5, x[3]+5], outline=colour["main"] + (255,), width=4)
                    do.rectangle([x[0]-2, x[1]-2, x[2]+2, x[3]+2], fill=(255, 255, 255, 255))
                else:
                    do.rectangle([x[0]-5, x[1]-5, x[2]+5, x[3]+5], outline=colour[b["cls"]] + (255,), width=4); do.text((x[0]-3, x[1]-16), b["cls"], fill=colour[b["cls"]] + (255,), font=font)
                    dm.rectangle([x[0]-2, x[1]-2, x[2]+2, x[3]+2], fill=(255, 255, 255, 255))
            for ln in p["lines"]:   # lines outside every block (none expected) and rotated lines
                if ln["cls"] in ("furniture", "rotated") and not any(ln["runs"][0]["id"] in b["members"] for b in tb):
                    x = [int(v) for v in ln["box"]]; dm.rectangle([x[0]-2, x[1]-2, x[2]+2, x[3]+2], fill=(255, 255, 255, 255)); do.rectangle([x[0]-5, x[1]-5, x[2]+5, x[3]+5], outline=colour["furniture"] + (255,), width=4)
            for c0, c1 in cols: dm.line([(c0, page_top), (c0, p["H"])], fill=(0, 110, 0, 90), width=2); dm.line([(c1, page_top), (c1, p["H"])], fill=(0, 110, 0, 90), width=2)
            mt.save(p["file"][:-5] + "-main-text.png"); ot.save(p["file"][:-5] + "-other.png")
            ro = mt.copy(); dr = ImageDraw.Draw(ro, "RGBA")   # rule 7: order numbers and band boundaries
            for y in bounds:
                for x in range(0, ro.width, 24): dr.line([(x, y), (x + 12, y)], fill=(200, 0, 0, 255), width=3)
            prev = None
            for b in ordered:
                x = [int(v) for v in b["box_px"]]; label = str(b["order"])
                dr.rectangle([x[0]-30, x[1]-6, x[0]-30 + 9 * len(label) + 8, x[1]+14], fill=(200, 0, 0, 255)); dr.text((x[0]-26, x[1]-3), label, fill=(255, 255, 255, 255), font=font)
                if prev is not None: dr.line([prev, (x[0]-26, x[1]+4)], fill=(200, 0, 0, 120), width=2)
                prev = (x[0]-26, x[3])
            ro.save(p["file"][:-5] + "-reading-order.png")
        splits = p["furniture_splits"] + splits
        rec = {"body_size_px": body, "header_bottom": p["header_bottom"], "footer_top": footer_top, "columns": cols,
               "furniture": [{"text": ln["text"], "why": ln["furniture_why"], "box_px": ln["box"],
                              "members": [e["id"] for e in ln["runs"]]} for ln in p["lines"] if ln["cls"] == "furniture"],
               "furniture_sources": p["furniture_sources"],
               "blocks": [{"id": b["id"], "cls": b["cls"], "why": b.get("why"), "order": b.get("order"), "size_px": round(b["size"], 1), "lines": b["lines"], "box_px": b["box_px"], "text": b["text"],
                           **({"in_refs": b["in_refs"]} if "in_refs" in b else {}),
                           **({"abstract": True} if b.get("abstract") else {}),
                           **({"abstract_continuation": True} if b.get("abstract_continuation") else {}),
                           **({"side_abstract": True} if b.get("side_abstract") else {}),
                           **({k:b[k] for k in ('translation','translation_role') if k in b}),
                           **({"list_column": b["list_column"]} if b.get("list_column") else {}),
                           **({"label_of": b["label_of"]} if b.get("label_of") else {}),
                           **{k:b[k] for k in ('role','owner','ownership_flags','header_from_body','header_group','header_after','table_header_cell') if k in b}} for b in tb],
               "counts": collections.Counter(b["cls"] for b in tb), "reading_order": [b["id"] for b in ordered], "band_boundaries_y": bounds, "splits": splits, "panels": panels}
        if captioned_lists: rec["captioned_lists"] = captioned_lists
        if wrap_recs: rec["wraps"] = wrap_recs
        if front_columns: rec['front_columns'] = front_columns
        if abstract_regions: rec['abstract_regions'] = abstract_regions
        rec["ownership"] = ownership
        if notes: rec["footnotes"] = notes
        rec["page_top_check"] = page_top_check(dict(p["d"], main_text=rec))
        rec["page_top_check"]["first_column_top_px"] = p["first_column_top"]
        p["d"]["main_text"] = rec; write_json(p["file"], p["d"], indent=1); out_pages.append(rec)
    write_text(os.path.join(paper_dir, "main-text.txt"), "# rule 6 main text in rule 7 reading order (bands, then column by column, top left to bottom right; [n] = block order over the paper)\n" + "".join(text_out))
    summary = {"body_size_px": body, "header_bottom": header_bottom, "footer_top": footer_top, "title_box_px": title_box, "author_box_px": author_box, "flags": flags,
               "pages": [{"page": p["page"], "columns": r["columns"], "counts": dict(r["counts"]),
                          "splits": [{k: v for k, v in s.items() if k != "runs"} for s in r["splits"]], "panels": r["panels"],
                          "page_top_check": r["page_top_check"]} for p, r in zip(P, out_pages)]}
    write_json(os.path.join(paper_dir, "main-text.json"), summary, indent=1)
    return summary

# rule 8's vocabularies, in one place: note symbols, name particles, institution words, group-author
# openings and words, month names (a date after a marker is not an affiliation)
NOTE_SYMBOLS = set("*∗⁎†‡§¶#✉")
PARTICLES = {"de", "da", "do", "dos", "das", "del", "della", "di", "du", "van", "von", "der", "den", "la", "le", "y", "e", "bin", "al", "el", "ter", "ten"}
INSTITUTION = re.compile(r"^(Department|Dept|Division|Faculty|School|University|Universidad|Universit|Institute|Instituto|Centre|Center|Laborator|Hospital|Unit|College|Clinic\b|Private practice|Graduate)", re.I)
GROUP_OPEN = re.compile(r"^(on behalf of|for the)\b", re.I)
GROUP_WORD = re.compile(r"\b(Group|Groups|Consortium|Collaborators?|Collaboration|Collaborative|Investigators|Committee|Panel|Participants|Network|Society|Federation|Association|Workshop|Consultants?|Members|Taskforce|Task Force)\b")
MONTH = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December)")
ADDRESS_OPEN = re.compile(r"^(?:Prosthodontist|General Dentist|(?:(?:Associate|Assistant|Adjunct|Clinical|Visiting|Emeritus)\s+)*Professor|(?:(?:Senior|Chief|Former)\s+)?(?:Resident|Lecturer|Fellow|Postgraduate|Director|Dean)|Research|Department|Division|Private Practice|(?:\w+\s+)?Engineer)\b", re.I)
# An affiliation footnote opening "From the ..." (AM03 "*From the Centre for Sleep Health and Research, ...")
FROM_THE = re.compile(r"^[*∗†‡§¶#\s]*From\s+(?:the\s+)?", re.I)
# A degree or academic title set after a name belongs to it: "Dr Habil" (habilitation) and the
# German diploma degrees "Dipl-Ing", "Dipl.-Psych." read as degrees, never as an author.
AUTHOR_DEGREE = re.compile(r"(?:(?:(?i:PROF|DR|MED|DENT|MD|DDS|DMD|PHD|MSC|MDS|MSD|DMSC|M\.S\.C|BDS|MPH|FRCS|FDS|HABIL|DIPL\.?(?:-[A-Z][a-z]+\.?)*)|MS|BS|MA|BA)\.?\s*)+")


# A leading affiliation marker: digits or note symbols, or a single lowercase letter set
# directly before a capital, a comma or a spaced capital ("1,2Department", "bInstitute", "a,b University").
AFFILIATION_MARK_LEAD = re.compile(r"^(?:[\d*∗†‡§¶#]+|[a-z](?=,|\s*[A-Z]))(?:\s*,\s*(?:[\d*∗†‡§¶#]+|[a-z](?=,|\s*[A-Z])))*\s*")


INSTITUTION_WORD = re.compile(r"\b(?:Department|Dept|Division|Faculty|School|Universit(?:y|ies|ät|at|é|e|à|a)|Universidad|Institut(?:e|o|es)?|Centre|Center|Laboratory|Laboratories|Hospital|College|Clinic)\b", re.I)


# A number-led institution phrase opening an address: an ordinal ("1st Faculty", "2nd Department",
# also "1 st" with the reading layer's space inside it) or a number before a capitalised word ("3 Hospitals").
NUMBER_LED = re.compile(r"\d+\s?(?:st|nd|rd|th)\b|\d+\s+[A-Z][a-z]")


# A labelled form field opening a row ("Short Title: ...", "Corresponding Author: ...", "Order of Authors: ...").
FIELD_ROW = re.compile(r"^[A-Z][A-Za-z'’]*(?:\s+[A-Za-z'’]+){0,4}\s*:\s")
# The author-list fields of a manuscript cover sheet (Editorial Manager and similar submission systems):
# "Order of Authors:" is the whole list, "First Author:" its first name. Exactly these labels: the
# sheet's "Order of Authors Secondary Information:" and "First Author Secondary Information:" are other fields.
# Round 6 rule A6: the labels that end an author list (the abstract, its keywords, the introduction).
FRONT_LABEL = re.compile(r"^(?:Abstract|Summary|Key\s*words?|(?:\d+\.?\s+)?Introduction)\b", re.I)
# Round 6 rule A9: a publication-history (date) line or an "Edited by" line is not an author line.
DATE_ROW = re.compile(r"^(?:Received|Accepted|Revised|Submitted|Published(?: online)?|Edited by)\b", re.I)
AUTHOR_FIELD = re.compile(r"^(Order of Authors|First Author)\s*:\s*(.*)$", re.I)
# A cover sheet's institution field ("Corresponding Author's Institution:"); its value is an affiliation.
INSTITUTION_FIELD = re.compile(r"^(?:[A-Z][A-Za-z'’]*\s+){0,3}Institution\s*:\s*(.*)$")
# Academic titles set before a name, recognised by their printed form, not by a list of titles:
# German and Austrian "Univ.-Prof. DDr.", "Ass.-Prof. Dr. med. dent.", "OA Dr.", "PD Dr med"; Czech
# "Doc. MUDr."; Polish "prof. dr hab. n. med.", "lek. dent.". A title token is an abbreviation ending in
# a period, or a hyphenated compound of such ("Univ.-Prof."); a capitalised abbreviation without a period
# made of two or more capitals or of no vowel (DDr, MUDr, OA, PD, Dr); a lower-case abbreviation without a
# period and without a vowel (dr, mgr); and, after a title token, its lower-case faculty qualifiers
# (med, dent, rer, nat). The titles end where the name starts: at a given name, or at an initial or run of
# initials that a surname follows (see prenominal_rest). A given name is a capitalised
# word with lower-case letters, no period, two letters or more. They belong to the name after them.
_TITLE_PERIOD = re.compile(r"(?:[^\W\d_]{1,6}\.-)*[^\W\d_]{1,6}\.|(?:[a-z]\.){2,3}|(?:[^\W\d_]{1,6}\.-)+[^\W\d_]{1,6}")
_TITLE_CAPS = re.compile(r"[A-Z][A-Za-z]{1,4}")
_LOWER_ABBR = re.compile(r"[a-z]{1,5}")
_GIVEN = re.compile(r"[A-ZÀ-Þ][a-zß-ÿ'’\-]+[a-zß-ÿ]|[A-ZÀ-Þ][a-zß-ÿ]")


_INITIALS = re.compile(r"[A-ZÀ-Þ]\.(?:-?[A-ZÀ-Þ]\.)*")


def prenominal_rest(text):
    """The name after a leading run of pre-nominal title tokens, or None when the text opens with none
    or no name follows them.

    The name starts at the first initial or run of initials ("K.", "A. M.", "G.A.", "H.-J.") that a surname
    follows (name particles, then a capitalised name word without a final period), else at the first token that is
    no title token and reads as a given name. A capital letter with a period that no surname follows
    ("M. Sc.") is a title token."""
    words = text.split()
    def initials_start(k):
        # The surname after the initials is what the plain name test reads as one: name particles
        # (PARTICLES: van der, de, ter, von, du, della ...) then a capitalised name word (also in capitals,
        # hyphenated or with an apostrophe), not an abbreviation ending in a period.
        j = k
        while j < len(words) and _INITIALS.fullmatch(words[j]): j += 1
        if j == k: return False
        while j < len(words) and words[j].islower() and words[j] in PARTICLES: j += 1
        return j < len(words) and bool(re.fullmatch(r"[A-ZÀ-ɏ][\wÀ-ɏ'’´`¸¨.\-]*", words[j])) and not words[j].endswith(".")
    def title(k):
        w = words[k]
        return bool(_TITLE_PERIOD.fullmatch(w) or
                    (_TITLE_CAPS.fullmatch(w) and (sum(ch.isupper() for ch in w) >= 2 or not re.search(r"[aeiouy]", w))) or
                    (_LOWER_ABBR.fullmatch(w) and (not re.search(r"[aeiouy]", w) or k > 0)) or
                    re.fullmatch(r"(?:Prof|Doz)", w))   # the period-less forms of the two common titles
    k = 0
    while k < len(words) and not initials_start(k) and title(k): k += 1
    if k == 0 or k >= len(words) - 1: return None
    if not (initials_start(k) or _GIVEN.fullmatch(words[k])): return None
    return " ".join(words[k:])


def form_name_row(text):
    """A printed row that reads as names only: its comma or semicolon parts (markers removed) are
    personal names (two to eight capitalised words or particles, pre-nominal titles allowed) or
    post-nominal degrees, at least one a name, none naming an institution."""
    t = re.sub(r"[\d*∗†‡§¶#]+", " ", text)
    parts = [x.strip(" .") for x in re.split(r"[,;]|\band\b", t) if x.strip(" .")]
    names = 0
    for part in parts:
        if INSTITUTION_WORD.search(part) or GROUP_WORD.search(part): return False
        words = (prenominal_rest(part) or part).split()
        if AUTHOR_DEGREE.fullmatch(part) or (len(words) == 1 and re.fullmatch(r"[A-Z][A-Za-z.]{1,6}", words[0]) and not re.search(r"[a-z]{3}", words[0])):
            continue
        if not (2 <= len(words) <= 8 and all(w.lower() in PARTICLES or re.fullmatch(r"[A-ZÀ-ɏ][\wÀ-ɏ'’´`¸¨.\-]*", w) for w in words)):
            return False
        names += 1
    return names > 0


def institution_row(text):
    """A printed row under a byline that is an address: it opens with an institution, also behind
    its leading affiliation marker ("1Department of ...", "bInstitute for ..."), or it names an
    institution anywhere ("Northfield University Dental Hospital, ..." opening with a place word).
    A byline row's markers follow its names; an affiliation row's marker opens it. A group name
    (Study Group, Consortium) stays in the byline. Such a row ends a byline."""
    t = text.strip()
    if INSTITUTION.match(AFFILIATION_MARK_LEAD.sub("", t, count=1)): return True
    return bool(INSTITUTION_WORD.search(t)) and not GROUP_WORD.search(t) and not GROUP_OPEN.match(t)


# Round 6 (lane affiliations), rule A19: a marked line that opens with these words is an author note
# (correspondence, equal contribution, present address, deceased), tied to its mark and never an
# affiliation, even when it names an institution. A support or funding statement after a mark is no
# address either (it is not an author note: it stays where the page puts it).
AUTHOR_NOTE_OPEN = re.compile(
    r"^(?:(?:(?:Address(?:es)?|Send|Please\s+address)\s+(?:all\s+)?(?:for\s+)?)?correspond\w*|(?:Reprint requests?|Requests? for reprints)\b|"
    r"(?:Author|Authors)\s+(?:for|of)\s+correspondence\b|To whom correspondence\b|"
    r"(?:These|The|Both|All)\b[^.!?]*\bauthors?\b[^.!?]*\b(?:contribute[ds]?|share)\b|(?:[^.!?]|(?<=[A-Z])\.)*\b(?:contribute[ds]?\s+equally|equal(?:ly)?\s+contribut\w+)\b|"
    r"(?:Current|Present|Permanent|New)\s+address\b|Deceased\b)", re.I)
SUPPORT_OPEN = re.compile(
    r"^(?:(?:This|The)\s+(?:work|study|research|project|trial|article|paper)\s+(?:was|is|has been)\s+)?(?:(?:partly|partially|financially|generously)\s+)?"
    r"(?:supported|funded|sponsored|financed)\s+(?:in\s+part\s+)?by\b|Funding\b|Financial\s+support\b|Grant\s+support\b", re.I)
E_MAIL = re.compile(r"\bE-?mail\b|[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)


def symbol_address(body):
    """Rule A11 with A10 (round 6; first written by lane r4-symboladdr): the text after a byline symbol is an
    address when it names an institution anywhere in the row (institution_row: "Primary Healthcare Center
    ...", "Previously, Department of ...", a place before a college name) and is not an author note
    (AUTHOR_NOTE_OPEN), a support statement or a row giving an e-mail address (a correspondence form printed
    without its label)."""
    t = body.strip()
    return bool(institution_row(t) and not AUTHOR_NOTE_OPEN.match(t) and not SUPPORT_OPEN.match(t) and not E_MAIL.search(t))


# Round 6 rule A16: an affiliation ends at a label (a section label opening a printed run) or at a
# correspondence opening; it never holds a section label or abstract text.
AFFILIATION_END_LABEL = re.compile(r"(?:Abstract|ABSTRACT|Summary|SUMMARY|Key\s*words|KEY\s*WORDS|Introduction|INTRODUCTION)(?![\w-])")
AFFILIATION_END_NOTE = re.compile(
    r"\s[*∗⁎†‡§¶#✉]?\s*(?:(?:(?:Address(?:es)?|Send|Direct|Please\s+(?:address|send|direct))\s+(?:all\s+)?(?:for\s+)?)?"
    r"(?:Correspond(?:ence|ance|ing authors?)\b|Reprint requests?\b|Requests? for reprints\b)|Full list of author information\b)", re.I)


def marked_row_after_marked_byline(above, text):
    """As printed text: a row opening with a digit or note-symbol marker directly before a capital,
    under a byline row that sets such markers directly after its names (anywhere in the row, also
    when a degree follows the last one), is an affiliation row: that byline's markers follow names."""
    return bool(re.search(r"[A-Za-z.][\d*∗†‡§¶#]", above.strip()) and
                re.match(r"[\d*∗†‡§¶#][\d,*∗†‡§¶#]*\s?[A-Z]", text.strip()))


def block_of_page(page, run_id):
    """The id of the block holding run_id on this page (None when unboxed)."""
    return next((b["id"] for b in page.get("blocks", []) if run_id in b["members"]), None)


# The byline joiners the author parse consumes between names (rule 8): these never reach a name; the copy
# writes the parsed names joined by "; " (the conservation ledger reads these two constants).
NAME_SEPARATORS = ",/;|&·•"
NAME_CONJUNCTIONS = ("and", "AND")


def byline_name_groups(lines):
    """An independent count of printed name-like groups, not parsed authors.

    Degree-only groups and institutional prose are not names. A whole name on
    each separate row is also a group; a lone given name continues across rows.
    """
    # Names are also separated by a printed middle dot or bullet (AM10 "Laura Benyei1,2 · Anton Friedmann1").
    text = re.sub(r'^by\s+', '', " ".join(lines).strip(), flags=re.I)
    # Round 6 rule A4: a number in brackets after a name is a marker, like a raised number.
    text = re.sub(r"\s*[(\[]\d{1,3}(?:\s*,\s*\d{1,3})*[)\]]", ",", text)
    groups = re.split(r"[,/;|&\d*∗†‡§¶#·•]+|\band\b", text)
    names = []
    for group in groups:
        name = group.strip(" .")
        words = name.split()
        # An address that starts on the byline row ends the names there: the groups after the
        # first institution-led group are address text (a group author's name excepted).
        if INSTITUTION.match(name) and not GROUP_WORD.search(name) and names: break
        def plain(words):
            return (2 <= len(words) <= 8 and not AUTHOR_DEGREE.fullmatch(name)
                    and not INSTITUTION.match(name) and not GROUP_WORD.search(name)
                    and all(w.lower() in PARTICLES or re.fullmatch(r"[A-ZÀ-ɏ][\wÀ-ɏ'’´`¸¨.\-]*", w) for w in words))
        # Pre-nominal titles ("Prof. Dr. med. dent. Name") belong to the name after them.
        rest = prenominal_rest(name)
        if plain(words) or (rest is not None and plain(rest.split())):
            names.append(name)
    if len(lines) > 1:
        separate = [name for line in lines for name in byline_name_groups([line])]
        if len(separate) > len(names): return separate
    return names


def title_display_runs(runs, aligned, proposed):
    """Separate display letters from a tiny production tag or a smaller access badge.

    Rule 1 can put both in one run. Its median size then hides a short final
    title row. Inspect character sizes within the proposed title's vertical
    band, including one following row, without changing the page's runs.
    Ordinary smaller title words and superscripts remain intact.
    """
    size = max((e['run_size_px'] for e in proposed), default=0)
    if not size: return runs, []
    top = min(e['box_px'][1] for e in proposed)
    bottom = max(e['box_px'][3] for e in proposed)
    result = []; excluded = []
    for e in runs:
        cs = aligned[e['id']]
        large = [c for c in cs if not c.get('space') and c['t'].isalpha()
                 and abs(c['size']-size) <= .02*size]
        if len(large) < 2 or not top-1 <= e['box_px'][1] <= bottom+size:
            result.append(e); continue
        small = [c for c in cs if not c.get('space') and c['size'] < .25*size]
        prefix = []
        for c in cs:
            if not c.get('space') and c['size'] >= .98*size: break
            prefix.append(c)
        badge = ''.join(c['t'] for c in prefix).strip()
        is_badge = (re.sub(r'\s+', '', badge).casefold() in ('open', 'openaccess') and
                    max((c['box'][2] for c in prefix if not c.get('space')), default=0)
                    < min(c['box'][0] for c in large))
        removed = {id(c) for c in small + (prefix if is_badge else [])}
        # Unprinted (white) production text is already absent from the aligned
        # characters; its run median still needs the display letters' size (AC09).
        if not removed and abs(e['run_size_px'] - size) <= .02 * size:
            result.append(e); continue
        kept = [c for c in cs if id(c) not in removed]
        boxes = [c['box'] for c in kept if not c.get('space')]
        view = dict(e, text=''.join(c['t'] for c in kept).strip(), run_size_px=size,
                    box_px=[min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes)])
        result.append(view)
        for part, reason in ((prefix if is_badge else [], 'access badge'), (small, 'tiny production text')):
            if part:
                excluded.append(dict(run=e['id'], text=''.join(c['t'] for c in part).strip(),
                                     reason=reason, char_ids=[c['char_id'] for c in part if 'char_id' in c]))
    return result, excluded


def front_backgrounds(pdf_path, page_no):
    """Boxes (px) of the page's images and its filled paths in a colour other than white.

    Rule 8 keeps a white glyph that stands on one of these (reversed text) and
    drops a white glyph on the bare page or on a white frame background. Page
    records carry no fill colours, so they are read here from the drawing.
    """
    import pdfplumber
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        if not 0 < page_no <= len(pdf.pages): return out
        page = pdf.pages[page_no - 1]
        dy = plumber_shift_px(pdf_path, page_no, page)
        for o in list(page.rects) + list(page.curves):
            if not o.get("fill"): continue
            v = o.get("non_stroking_color"); v = (v,) if isinstance(v, (int, float)) else tuple(v or ())
            if tuple(float(x) for x in v) in ((1.0,), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0)): continue
            out.append([px(o["x0"]), px(o["top"]) + dy, px(o["x1"]), px(o["bottom"]) + dy])
        out += [[px(o["x0"]), px(o["top"]) + dy, px(o["x1"]), px(o["bottom"]) + dy] for o in page.images]
    return out


def authors_and_affiliations(pdf_path, paper_dir):
    """Rule 8 (authors and affiliations): on the first text page, the title, the authors under it and
    the affiliations their markers point to are found and checked against each other. The rule reads
    the page records of rules 1-7 (as rule 6 left them, including later-page furniture) and the
    first text page's characters, and writes authors.json beside them. It leaves rules 1-7's data unchanged;
    that page's JSON additionally records each joined accent or initial in rule8.author_joins, with source
    and target runs, character IDs and the fragment's box (accents also record the composed letter).

    The title starts with the largest runs in rule 6's title blocks; a smaller badge or sidebar
    sharing a title line is left out, even within the same run. Character sizes recover
    a final display row whose run median was dominated by tiny production text; that text
    and access badges are recorded separately in title_exclusions. A journal/repository banner or text recurring on later pages
    at the same type size is rejected (a smaller running-title version is distinct). A top-band
    masthead also matches a journal citation in a running head/footer, or is separated from a
    lower title and byline by a horizontal rule or a wide gap. Those tests require a lower
    multiword title followed by names, so a running version of the actual title is not enough.
    A title with its own directly following byline stays: another article below a separator
    on the same page does not make the first article's title a masthead.
    An article-type label (Review, Original Article, Case Report and similar
    generic labels, including letter-spaced forms) is also excluded from title
    candidates, even when its type is larger than the article title. A lone "by"
    is a byline introducer, never a title. Reselection seeds a multiword title,
    then keeps directly stacked same-size continuation rows, including a single
    final word that rule 6 classified as main text.
    Within a proposed title it must be an opening row; a wrapped title ending
    in the word Review keeps that final word.
    In that case the
    largest remaining text in the first half-page supplies the title, taking its stacked lines. This
    correction is recorded only here, never in rules 1-7's files. Directly stacked display lines
    below that title, larger than the body (outside the size tolerance) and no larger than the
    title, are its subtitle when left-aligned or centred with it. They stop at a name row, an
    institution, a banner, the first main-text block or a gap larger than one smaller line's em;
    the search never skips an intervening row. A smaller subtitle starts after a colon unless
    the title already ends in punctuation; its wrapped lines are joined with spaces. When the subtitle
    leads directly into body-sized prose, with no independent author band or name/group row,
    the title record reports no authors rather than treating that prose as a byline.
    The authors are the lines directly
    under the title, inside the title's column (a line set wider than the title, across half its width
    or more, is in it too): the first within author_gap_em letter heights of the
    title, then every line stacked under it (author_stack_em) at the same size. All rule 6 author
    blocks under the title are candidates, including those outside the title's width. On each
    selected row, every author block and same-size run reading as names is included, with
    baselines within half a line height, regardless of its block or rule 1 line number. Rows read
    top to bottom and their runs left to right. For an existing
    rule 6 author band whose words read as names, the first gap can use the title's em, allowing
    small-capital bylines. An
    institution opening ends the byline even if it is set at the authors' size.
    An explicit "by" followed immediately by names also establishes a detached
    author panel below the title, before or beside the abstract opening. An
    existing nearby author band takes precedence over a later prose "by" phrase.
    Its compact same-size address rows stay with
    that panel, bounded by its column, gap and front-matter labels. The introducer
    stays in the printed evidence, and generational suffixes stay with the name.
    A sidebar beside
    a continuing body column uses rule 7's bounded name block, even across a wide gap
    below the title. Its abstract and introduction runs are excluded before grouping rows.
    A sidebar beside
    the title can supply the author lines. Such a sidebar takes
    precedence over a tail selected below the title or a citation there: it is either rule 6's author
    band or a name opening near the title's top followed by institution text. All its same-size rows
    are taken until a gap, size change or institution opening; the end of a row ends a complete name,
    but a lone given name continues on the next row. Sidebar
    superscripts use the run's own size, not a larger title's size on the shared rule 1 line.
    An overprinted combining or spacing accent belongs to the letter whose ink it overlaps most,
    and is composed with that letter in Unicode (using i for an accented dotless i); a detached
    accent never ends the author rows. The composed letter's ink also recovers a following word gap
    hidden by the spacing accent.
    A one- or two-letter initial fragment touching a lowercase word joins that word by x position
    and vertical overlap, including a fragment swept into the preceding row by its large line box.
    A touching lowercase continuation across a run boundary stays in the same word. A superscript is a
    character smaller than superscript_em of its line and raised above the line's baseline; digits and
    letters set that way after a name, and digits at either size, are its markers. A multi-digit
    number is one marker: narrow digit ink must not invent a space inside a contiguous number.
    Commas and printed gaps separate markers; space-separated numbers must each have an
    affiliation for the result to be verified. A comma before
    a marker does not detach it from the preceding name. Symbols (*, ∗, †, ‡, §, ¶, #, an envelope glyph) are
    notes unless they label an address; explicit equal-contribution definitions make numeric
    markers notes too. A degree suffix is kept as degrees on its preceding name, never a new author.
    An all-capital acronym continuing an established degree list is a further
    credential, including its following markers; a standalone acronym is not
    sufficient evidence for a degree.
    Names are separated by a
    comma, slash, semicolon, bar, ampersand, the word "and" at the line's own size, or a run boundary before
    a capitalised name; degree lists remain with the preceding name, including markers following
    the last degree. Academic titles (including Prof Dr med dent) in a suffix list are degrees,
    so a slash after them still separates names, including across a printed line break.
    A marker ends before the next name's initial, never inside that name.
    Markers before a name belong to that whole name; they cannot terminate it
    as soon as its given name and surname initial form a plausible name.
    The legacy y/z/x codes in a distinct sign face denote dagger/double dagger/section markers
    only when the same font/code also labels an address below the byline. A name may run on to the
    next line. A group author is not a name: an entry opening "On behalf of" or "for the" begins one and
    every entry after it is part of it, and an entry naming a body (a Group, Committee, Consortium,
    Workshop Participants ...) is one on its own; group authors are listed apart and kept out of the
    name checks. An ORCID icon is a drawn object (image or outline) about one letter height square
    standing on an author line; it marks the name it follows, and letters printed on it ("iD") are the
    icon's, not the name's. An affiliation is a marker, on the first page outside the title and author
    lines: a superscript, a small run of its own beside the text, or baseline digits set against
    a capital, at the start of an address line, or in a distinct marker font. Raised markers end
    at the change of typography,
    whatever character follows, including a baseline digit. Baseline street numbers inside an
    address do not start an affiliation. After the abstract starts, body-sized main-text blocks cannot supply affiliations;
    without an abstract label, an institution-led address band directly below the byline remains eligible.
    citation superscripts inside their sentences are not address labels. A publication header
    above the title, identified by its DOI or journal citation, supplies article information,
    never an affiliation. Explicitly labelled later Author details/affiliation panels can
    supply missing links: raised numeric labels must match the complete set of byline
    markers. Their source page and runs are recorded; their boxes never enlarge the
    first-page affiliation box. Each address ends before
    the next marker, a disclosure heading, a supplemental-material note opening
    (including correspondence following that note), or at its block
    end. An institution-led prefix before the first marked address on the affiliation rows is kept
    first as affiliation 0 when the byline has an unmarked author, including a separate block
    immediately to the left on that row or above it in the same column; no printed marker or author link
    is invented. An unmarked address sharing the author/abstract block is recovered from contiguous
    institution-led lines, stopping at a size change, gap or front-matter heading.
    Runs owned by a structured or side-column abstract in rule 6 are never title, authors or
    affiliations. Clinic is an institution word; Clinical alone is not.

    The checks: each name reads as a name (two to eight words, letters and name punctuation, no digits);
    every affiliation marker an author carries has its affiliation; every affiliation found is carried
    by an author; the markers run 1, 2, 3 ... with no gap. Where the authors carry no markers, the
    authors are not linked to an affiliation and the paper says so (not verified, not failed).
    Independently, byline_name_groups counts capitalised name-like groups delimited by digits,
    note symbols, commas, bars, slashes or "and", excluding degrees and institutions. It is a
    count of name-like groups, not an identity check; whole names on separate rows count too.
    byline_lines retains every selected printed row and
    its run IDs even when the parser cannot verify it; the copy uses this evidence for its flag.

    Lane front8 (2026-11-03): a masthead in the top band (upper 15% of the page) can be far larger
    than the title; below it a display row of at least 1.3 body sizes with at least as many words
    as the band, followed by a byline, is the title when a rule, a journal citation, a wide gap or
    the band's recurrence on other pages at any size parts them. A row set in capitals in type
    smaller than the body in the top band is a banner and never counts as a byline. Names are also
    separated by a middle dot or bullet; a raised marker glued to "and" is a word boundary; a
    tracked initial's detached period rejoins it. A comma-separated credential (three or more
    letters, two capitals, no lowercase run of three, not period-separated initials) is a degree.
    A byline row continuing with the affiliation in another size, opening with an academic role
    or institution word right of a name run, is cut there; that run and the same-size rows
    stacked under it are the unmarked affiliation. A row in another size lying wholly beside the
    byline rows (another column) is passed over. In a byline with no printed separator, the end of
    a row ends a complete name. A full-size lowercase letter opening an address run, in a face
    other than the address's or raised above its baseline, is a marker when the byline uses it;
    a run alone on its rule-1 line with no full-size letters at the line's size is measured by
    its own size. Equal-contribution statements in any wording, and current/present-address
    notes, are notes. The low asterisk is a note symbol. A footnote opening "From the" or a
    note symbol before an institution word is the unmarked affiliation (its first sentence for
    "From the"). Later pages: under a label reading Author(s) [and] details/affiliations/
    information anywhere in the paper, the runs stacked below it (to a gap of three label
    heights or a larger heading) are read row by row within their blocks: a raised marker group
    opening a row or following a space, or a small run of its own left of the row, marks an
    address; rows with an e-mail, a note symbol, a correspondence opening or a byline name are
    not addresses. The panel is accepted when its markers are exactly the byline's; its label
    and every run below it are recorded in affiliation_sources (label). Without a label, the
    page after the front page may hold rows marked with exactly the markers the first page left
    unresolved, outside body prose or in smaller type, each with an institution word
    (affiliation_sources with continuation). Markers in a later marked address before "and"
    drop that conjunction.

    Lane masthead (2026-11-04): in the banner tests, a display row (1.3 body sizes or more)
    with no name separator (comma, semicolon, slash, bar, ampersand, middle dot, bullet,
    "and", a note symbol, a raised marker or a digit glued to a word) is never a byline.
    Recurrence on later pages is also tested on joined rows: same-size runs on one rule-1
    line, each within two letter heights of the next. The title is chosen by adjacency: a
    lower display block (three words or more) followed within three rows by a smaller
    byline-shaped row or an abstract label is a title-plus-byline pair, and a proposed title
    above it with fewer words and no byline of its own is a masthead when its left edge and
    centre are both more than one em off the pair's, or when it stands in the top band in a
    face used on no other page and on page 1 only above the pair across its width. With no
    such pair nothing is rejected, and the program reports a missing byline as before.
    Directly below the byline (within author_gap_em), a block whose first row opens with a
    raised label the byline uses is an address band, like an institution-led one, even when
    it is body-sized main text and no abstract label precedes it.

    What is not done: no name is looked up anywhere, and no affiliation is matched to an author by
    position or guess. The title is checked against printed lines, sizes and repeated furniture;
    no external title or author database is consulted.
    A series or section label (one short opening row of the proposed title, alone in its face
    there, directly above a longer display row in another face that does not read as names and
    is followed by a smaller name row) is rejected alone, like an article type, even when larger.
    Rejected rows of rule 6's title are recorded in article_info (role series label or rejected
    title row). A sidebar address beside a name row, institution-led and in another size, does
    not join that row. Rule 7's front-column name block supplies the byline when it lies beyond
    the ordinary gap below the title. Fill-only white glyphs (DeviceGray/RGB/CMYK white, fill
    render mode) that stand on no image or coloured fill are not printed and are not read;
    repeated symbols (*, **, ***) are distinct labels, and a symbol address may open with an
    academic role (Professor, Resident, Lecturer ...). A reprint or correspondence request after
    the addresses ends the last one and is article information. A word space inside a run must
    also exceed 1.6 times the run's median letter gap (tracked small capitals).
    Picture-only opening pages with only furniture are skipped. The first text page supplies
    the title/byline, with its page number recorded when later than page one. On that page,
    stacked display-sized upper text and a separate block of marked names can establish
    the front matter despite a wide gap and an adjacent body column.
    With no page records it writes a flagged empty record, emits one stderr line and exits 0."""
    import os, re
    AUTHOR_GAP_EM, AUTHOR_STACK_EM, SIZE_TOL, RAISE_EM = PARAMS["author_gap_em"], PARAMS["author_stack_em"], PARAMS["author_size_tol"], PARAMS["superscript_raise_em"]
    if not page_files(paper_dir):
        result = {"rule": 8, "title": None, "authors": [], "affiliations": [], "orcid_icons": 0,
                  "checks": {"title_found": False}, "flags": ["no page records: authors not searched"]}
        write_json(os.path.join(paper_dir, "authors.json"), result, indent=1, ensure_ascii=False)
        print("rule 8: no page records", file=sys.stderr)
        return result
    paths = page_files(paper_dir)
    p = read_json(paths[0]); front_path = paths[0]
    # A picture-only opening may contain journal furniture, but no article
    # text. Search the first page with non-furniture words, never past prose.
    for path in paths:
        candidate = read_json(path)
        furniture = {m for b in (candidate.get("main_text") or {}).get("blocks", [])
                     if b["cls"] == "furniture" for b0 in candidate["blocks"]
                     if b0["id"] == b["id"] for m in b0["members"]}
        if any(e["kind"] == "text" and e["id"] not in furniture and
               len(re.findall(r"[^\W\d_]+", e["text"])) >= 3 for e in candidate["elements"]):
            p = candidate; front_path = path; break
    front_page = p.get("page", 1)
    chars = pdfium_characters(pdf_path, front_page)
    flags = []
    abstract_blocks = {b["id"] for b in (p.get("main_text") or {}).get("blocks", []) if b.get("abstract")}
    front_columns = (p.get('main_text') or {}).get('front_columns', {})
    abstract_blocks.update(front_columns.get('body_blocks', []))
    abstract_ids = {m for b in p["blocks"] if b["id"] in abstract_blocks for m in b["members"]}
    runs = [e for e in p["elements"] if e["kind"] == "text" and e["angle"] == 0
            and not e.get("furniture_reason") and e["id"] not in abstract_ids]
    def is_private(t): return any(0xE000 <= ord(c) <= 0xF8FF for c in t)
    # Fill-only white glyphs on the bare page are not printed. AG05 sets every
    # address footnote as "****" and paints the surplus stars white, so markers
    # are counted from the printed glyphs. A white glyph over a drawn fill, image
    # or art box (reversed text) stays; so does any other colour space.
    drawn = {}
    def white_on_page(c, box):
        v = c.get("fill_color"); v = (v,) if isinstance(v, (int, float)) else tuple(v or ())
        white = ((c.get("fill_space") == "DeviceGray" and v == (1,)) or (c.get("fill_space") == "DeviceRGB" and v == (1, 1, 1))
                 or (c.get("fill_space") == "DeviceCMYK" and v == (0, 0, 0, 0)))
        if not white or c.get("render_mode", 0) not in (0, 4): return False
        page_no = c.get("page", front_page)
        if page_no not in drawn:
            try: drawn[page_no] = front_backgrounds(pdf_path, page_no)
            except (OSError, ValueError): drawn[page_no] = None
        if drawn[page_no] is None: return False   # no drawing to test: keep the glyph
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        return not any(g[0] <= cx <= g[2] and g[1] <= cy <= g[3] for g in drawn[page_no])
    # characters of each run, aligned to its text; a space wherever the white between two characters
    # exceeds a word space (wordspace_min_em of the larger), so letter-spaced words are not split
    def letter_gap(e):
        # Letter-spaced (tracked) small capitals separate every letter by a third of
        # a small letter or more (AG06 byline: 2.3-4.9 px at 20 px). A word space
        # must then also stand clear of the run's own median letter gap.
        ids = [i for i in e["char_ids"] if 0 <= i < len(chars)]
        cs = [chars[i] for i in ids]; gaps = []; j = 0
        words = e["text"].split()
        for w in words:
            seg = cs[j:j + len(w)]; j += len(w)
            gaps += [q["x0"] - o["x1"] for o, q in zip(seg, seg[1:]) if o["text"].isalpha() and q["text"].isalpha()]
        return 1.6 * statistics.median(gaps) if len(gaps) >= 4 else 0
    def run_chars(e):
        out = []; ids = list(e["char_ids"]); k = 0; text_space = False
        tracked = letter_gap(e)
        for t in e["text"]:
            if t.isspace(): text_space = True; continue
            if k >= len(ids) or ids[k] >= len(chars): return None
            c = chars[ids[k]]; k += 1
            if c["text"] != t and not (is_private(c["text"]) and is_private(t)): return None
            box = [c["x0"], c["y0"], c["x1"], c["y1"]]
            if white_on_page(c, box): continue
            prev = next((q for q in reversed(out) if not q.get("space")), None)
            # the run's own word spaces (rule 1) stand; narrow ones in tight lines are below the ink-gap test (N18 "University of Michigan")
            accent = lambda ch: unicodedata.category(ch) == "Sk" or 0x2B0 <= ord(ch) <= 0x2FF   # a free-standing accent (U+02C7 caron is a modifier letter)
            # Narrow digits (especially 1) have large side bearings. For a
            # same-face, same-baseline number, use advance spacing rather than
            # the ink gap; an actual space in the run remains a separator.
            digit_pair = (prev is not None and t.isdigit() and prev["t"].isdigit() and
                          c.get("font", "") == prev["font"] and
                          abs(c["size"] - prev["size"]) <= SIZE_TOL * c["size"] and
                          abs(c["origin"][1] - chars[prev["char_id"]]["origin"][1]) <= RAISE_EM * c["size"])
            gap = box[0] - prev["box"][2] if prev is not None else 0
            if digit_pair and chars[prev["char_id"]].get("adv_x1") is not None:
                gap = c["origin"][0] - chars[prev["char_id"]]["adv_x1"]
            # (lane r5-line: an accent set after a PDF space glyph, before the letter it stands over, keeps that space)
            if prev is not None and (text_space or gap > max(PARAMS["wordspace_min_em"] * max(c["size"], prev["size"]), tracked)) and not (accent(t) and not text_space) and not accent(prev["t"]): out.append({"t": " ", "space": True})
            text_space = False
            out.append({"t": t, "size": c["size"], "box": box, "font": c.get("font", ""), "char_id": ids[k - 1], "run": e["id"]})
        return out if k == len(ids) else None
    def mark_raised(e, cs, line_full, own_size=False):
        size = e["run_size_px"] if own_size else e["size_px"]
        full = [c for c in cs if not c.get("space") and c["t"].isalnum() and c["size"] >= PARAMS["superscript_em"] * size] or line_full.get(e["id"], [])   # letters and digits set the baseline (a full-size raised * does not)
        if not full and not own_size and re.search(r"[^\W\d_]{3,}", e["text"]):
            # An address line alone on a page-wide rule-1 line (no full-size letters of its own
            # at the line's size, no neighbour within two letter heights) is smaller type set
            # apart, such as an address footnote under the abstract beside the body column: it is
            # measured by its own size, so the letters after its mark are not read as part of a
            # raised label (AH06 "†Department", once its character ids matched the reading layer;
            # AL05 "bDepartment of Pathology" on a line whose size came from the citation column).
            size = e["run_size_px"]
            full = [c for c in cs if not c.get("space") and c["t"].isalnum() and c["size"] >= PARAMS["superscript_em"] * size]
        base = statistics.median(c["box"][3] for c in full) if full else e["box_px"][3]
        for c in cs:
            if c.get("space"): continue
            c["sup"] = c["size"] < PARAMS["superscript_em"] * size and c["box"][3] < base - RAISE_EM * size
        return cs
    aligned = {}
    for e in runs:
        cs = run_chars(e)
        if cs is None: flags.append(f"run {e['id']}: characters do not match its text; read without superscripts"); cs = [{"t": t, "space": t.isspace(), "size": e["size_px"], "box": e["box_px"]} for t in e["text"]]
        aligned[e["id"]] = cs
    # a run with no full-size letters of its own (markers alone, after an ORCID mark) takes its line's baseline
    # a run with no full-size letters of its own takes the baseline of its neighbours on the line (runs within two
    # letter heights of it sideways; page-wide lines carry other columns' runs, which stay out)
    line_full = {}
    for e in runs:
        nb = [o for o in runs if o is not e and o["line"] == e["line"] and max(o["box_px"][0] - e["box_px"][2], e["box_px"][0] - o["box_px"][2]) <= 2 * e["size_px"]]
        line_full[e["id"]] = [c for o in nb for c in aligned[o["id"]] if not c.get("space") and c["t"].isalnum() and c["size"] >= PARAMS["superscript_em"] * e["size_px"]]
    for e in runs: aligned[e["id"]] = mark_raised(e, aligned[e["id"]], line_full)
    if front_page != 1:
        # Wide front panels share rule-1 lines with the body column. Their
        # smaller affiliations need their own baseline and size, just as
        # sidebar bylines do; body text cannot turn an address into markers.
        for e in runs: mark_raised(e, aligned[e["id"]], line_full, own_size=True)
    spacing_accents = {"^": "\u0302", "~": "\u0303", "`": "\u0300", "´": "\u0301", "ˇ": "\u030c"}
    def accent_mark(t):
        mark = spacing_accents.get(t, unicodedata.normalize("NFKD", t).strip())
        return mark if mark and all(unicodedata.category(c).startswith("M") for c in mark) else ""
    def accent_overlap(c, letter):
        a, b = c["box"], letter["box"]; accent = accent_mark(c["t"])
        below_accent = all(unicodedata.combining(t) in (202, 216, 220) for t in accent)
        vertical = (b[1] <= a[1] <= b[3] + .4 * letter["size"] if below_accent else
                    b[1] - .6 * letter["size"] <= a[1] and a[3] < b[3] - .2 * letter["size"])
        return min(a[2], b[2]) - max(a[0], b[0]) if vertical else 0
    # A detached accent is part of the overprinted word's row, never a new row
    # that can terminate the byline. The same holds for a touching drop initial.
    attached = {}
    for e in runs:
        cs = [c for c in aligned[e["id"]] if not c.get("space")]
        if not 0 < len(cs) <= 2: continue
        accent = all(accent_mark(c["t"]) for c in cs)
        initial = cs[0]["t"].isupper() and all(c["t"].isalpha() for c in cs)
        if not (accent or initial): continue
        matches = []
        for other in runs:
            if other is e: continue
            letters = [c for c in aligned[other["id"]] if not c.get("space") and c["t"].isalpha()]
            if len(letters) < 3: continue
            if accent:
                overlap = max((min(accent_overlap(c, l) for c in cs) for l in letters), default=0)
                if overlap > 0: matches.append((-overlap, other))
            else:
                first = next((c for c in aligned[other["id"]] if not c.get("space")), None)
                if first is None or not first["t"].islower(): continue
                gap = first["box"][0] - max(c["box"][2] for c in cs)
                overlap = min(max(c["box"][3] for c in cs), first["box"][3]) - max(min(c["box"][1] for c in cs), first["box"][1])
                if -.1 * first["size"] <= gap <= PARAMS["wordspace_min_em"] * first["size"] and overlap >= .3 * (first["box"][3] - first["box"][1]):
                    matches.append((abs(gap), other))
        if matches: attached[e["id"]] = min(matches, key=lambda t: t[0])[1]
    # Rule 6's proposed title is only a starting point. Repeated page furniture and
    # journal/repository banners cannot be a title, even when their type is largest.
    mt = p.get("main_text") or {}
    title_ids = {m for b in mt.get("blocks", []) if b["cls"] == "title" for b0 in p["blocks"] if b0["id"] == b["id"] for m in b0["members"]}
    trs = [e for e in runs if e["id"] in title_ids]
    runs, title_exclusions = title_display_runs(runs, aligned, trs)
    trs = [e for e in runs if e['id'] in title_ids]
    thesis_title = []
    if not trs and front_page != 1 and any(read_json(path).get('repository_cover') for path in paths if path != front_path):
        thesis_title = thesis_title_runs(p)
        trs = thesis_title
    result = {"rule": 8, "title": None, "authors": [], "affiliations": [], "orcid_icons": 0, "checks": {}, "flags": flags}
    if front_page != 1: result["page"] = front_page
    def normalized(t): return re.sub(r"\W+", "", t).casefold()
    repeated = collections.defaultdict(list)
    margins = [e for e in runs if e["box_px"][3] < .1 * p["region_box_px"][3]
               or e["box_px"][1] > .9 * p["region_box_px"][3]]
    # Lane masthead R2 (2026-11-04): recurrence is also tested on joined rows. A running
    # head can be set as several runs on one printed row (AP03 pp 2-7: "PRACTICAL" and
    # "APPLICATIONS", 19 px apart at 14.5 px), so a single-run banner on page 1 never
    # matched it run by run. Same-size runs on one rule-1 line, each within two of its
    # letter heights of the next, are joined into one row text (repeated_rows).
    repeated_rows = collections.defaultdict(list)
    def font_faces(e):
        fs = e.get("font"); fs = fs if isinstance(fs, list) else [fs]
        return {re.sub(r"^[A-Z]{6}\+", "", str(f)) for f in fs if f}
    faces_elsewhere = collections.Counter()   # R3: faces used on the paper's other pages
    for path in paths:
        if path == front_path: continue
        other = read_json(path)
        for e in other["elements"]:
            if e["kind"] == "text":
                repeated[normalized(e["text"])].append(e["run_size_px"])
                faces_elsewhere.update(font_faces(e))
                if e["box_px"][3] < .1 * other["region_box_px"][3] or e["box_px"][1] > .9 * other["region_box_px"][3]: margins.append(e)
        by_line = collections.defaultdict(list)
        for e in other["elements"]:
            if e["kind"] == "text" and e.get("angle", 0) == 0: by_line[e["line"]].append(e)
        for line_runs in by_line.values():
            line_runs.sort(key=lambda e: e["box_px"][0]); segment = [line_runs[0]]
            for e in line_runs[1:] + [None]:
                prev = segment[-1]
                if (e is not None and abs(e["run_size_px"] - prev["run_size_px"]) <= SIZE_TOL * prev["run_size_px"]
                        and e["box_px"][0] - prev["box_px"][2] <= 2 * prev["run_size_px"]):
                    segment.append(e); continue
                if len(segment) >= 2:
                    repeated_rows[normalized(" ".join(r["text"] for r in segment))].append(max(r["run_size_px"] for r in segment))
                segment = [e]
    def recurrences(t):
        return repeated[normalized(t)] + repeated_rows[normalized(t)]
    def name_run(e):
        cs = mark_raised(e, [dict(c) for c in aligned[e["id"]]], line_full, own_size=True)
        text = "".join(c["t"] for c in cs if not c.get("sup"))
        initials = [r for r in runs if attached.get(r["id"]) is e and r["text"].strip().isalpha()]
        if initials: text = "".join(r["text"].strip() for r in sorted(initials, key=lambda r: r["box_px"][0])) + text
        words = re.findall(r"[^\W\d_]+", text)
        return (not INSTITUTION.match(text.strip()) and len(words) >= 2 and
                all(w[0].isupper() or w.lower() in PARTICLES or w == "and" for w in words))
    def top_band(box):
        # The page's top band: the upper 15% of the page region.
        return box[3] <= p["region_box_px"][1] + .15 * (p["region_box_px"][3] - p["region_box_px"][1])
    def caps_banner_row(r):
        # A row set in capitals, in type smaller than the body, in the page's top
        # band is a section or series banner, never a byline (AM03 "CONTEMPORARY
        # REVIEWS IN SLEEP MEDICINE" under the journal masthead, measured 2026-11-03).
        t = r["text"].strip(); body = mt.get("body_size_px") or 0
        return (bool(body) and len(t.split()) >= 2 and not any(ch.islower() for ch in t)
                and r["run_size_px"] < .95 * body and top_band(r["box_px"]))
    def display_unseparated(r):
        # Lane masthead R1 (2026-11-04): a display row (1.3 body sizes or more) with no
        # name separator (comma, semicolon, slash, bar, ampersand, middle dot or bullet,
        # the word "and", a note symbol, a raised marker or a digit glued to a word) is
        # never a byline. AP03's 31.1-px subtitle "... Through Regenerative Approaches"
        # (body 21 px) passed as names and vetoed the banner test (DIAGNOSIS-AP E3). One
        # personal name needs no separator, so the row must hold five words or more (AP03:
        # six; a lone same-size author name, two to four words, stays a byline:
        # test_front_matter's wrapped-title fixture).
        body = mt.get("body_size_px") or 0
        if not body or r["run_size_px"] < 1.3 * body: return False
        t = r["text"]
        if len(re.findall(r"[^\W\d_]+", t)) < 5: return False
        if re.search(r"[,;/|&·•]|\band\b|[^\W\d_]\d|\d[^\W\d_]", t) or any(ch in NOTE_SYMBOLS for ch in t): return False
        return not any(c.get("sup") and not c.get("space") for c in aligned.get(r["id"], []))
    def byline_shaped(r):
        return name_run(r) and not caps_banner_row(r) and not display_unseparated(r)
    def separated_masthead(e):
        eb = e["box_px"]; size = e["run_size_px"]
        # Test the whole proposed title, not an opening line of a wrapped title.
        # Cover sheets can set the title and byline at exactly the same size.
        band = proposed if e in proposed else [e]
        bb = [min(r["box_px"][0] for r in band), min(r["box_px"][1] for r in band),
              max(r["box_px"][2] for r in band), max(r["box_px"][3] for r in band)]
        if bb[3] > .22 * p["region_box_px"][3]: return False
        if any(r not in band and bb[3] < r["box_px"][1] <= bb[3]+AUTHOR_GAP_EM*r["run_size_px"]
               and r["run_size_px"] <= (1+SIZE_TOL)*size and byline_shaped(r)
               and min(bb[2],r["box_px"][2])-max(bb[0],r["box_px"][0]) >= .5*min(bb[2]-bb[0],r["box_px"][2]-r["box_px"][0])
               for r in runs): return False
        # A journal name in a citation is followed by a volume and year. Require
        # the complete name, not a substring in a running article title.
        citation = any(re.search(r"(?<!\w)" + re.escape(e["text"].strip()) +
                      r"\s+\d+\s*\((?:19|20)\d{2}\)", m["text"], re.I) for m in margins)
        # A masthead in the top band can be set far larger than the article's
        # title (AM03: the journal name at 75 px over a 38 px title). Below such
        # a band, a display row at least 1.3 times the body size with at least
        # as many words as the band is a title candidate too; a running section
        # label recurring on other pages at any size is further banner evidence.
        body = mt.get("body_size_px") or 0
        band_words = len(re.findall(r"[^\W\d_]+", " ".join(r["text"] for r in band)))
        in_top_band = top_band(bb)
        recurs = in_top_band and len(normalized(e["text"])) >= 12 and bool(recurrences(e["text"]))
        lower = [r for r in runs if r["id"] not in title_ids and eb[3] < r["box_px"][1] < .5*p["region_box_px"][3]
                 and len(r["text"].split()) >= 3
                 and (.7*size <= r["run_size_px"] <= 1.2*size or
                      in_top_band and body and 1.3*body <= r["run_size_px"] <= 1.2*size
                      and len(re.findall(r"[^\W\d_]+", r["text"])) >= band_words)]
        for title in lower:
            tb = title["box_px"]; ts = title["run_size_px"]
            tail = [r for r in lower if abs(r["run_size_px"]-ts) <= SIZE_TOL*ts
                    and tb[1] <= r["box_px"][1] <= tb[3]+PARAMS["stack_gap_em"]*ts]
            bottom = max(r["box_px"][3] for r in tail)
            byline = any(bottom < r["box_px"][1] <= bottom+AUTHOR_GAP_EM*r["run_size_px"]
                         and r["run_size_px"] < (1-SIZE_TOL)*ts and byline_shaped(r) for r in runs)
            if not byline: continue
            rule = any(g["kind"] in ("rule", "fill") and eb[3] < g["box_px"][1] < tb[1]
                       and g["box_px"][3]-g["box_px"][1] < .3*size
                       and g["box_px"][2]-g["box_px"][0] > .5*(p["region_box_px"][2]-p["region_box_px"][0])
                       for g in p["elements"] + p.get("art", []))
            if citation or rule or recurs or tb[1]-eb[3] > 4*size: return True
        return False
    def article_type(e):
        return (normalized(e["text"]) in {"review", "reviewarticle", "originalarticle", "originalresearch",
                                          "researcharticle", "casereport", "clinicalreport", "shortcommunication"}
                and (e not in proposed or e["box_px"][1] <=
                     min(r["box_px"][1] for r in proposed) + .5 * e["run_size_px"]))
    def face(e):
        return re.sub(r"^[A-Z]{6}\+", "", e["font"] if isinstance(e.get("font"), str) else str(e.get("font")))
    def series_label(e):
        # Only the opening row of the proposed title, and only a row standing alone in
        # its face there, can be a label; the row below must not read as names (Z04,
        # U01: a title's last word above the byline is no label).
        if proposed and (e is not min(proposed, key=lambda r: (r["box_px"][1], r["box_px"][0])) or
                         any(r is not e and face(r) == face(e) for r in proposed)): return False
        # A series or section label (AG08 "AAP-Commissioned Review", measured 2026-10-24)
        # is article information, never the title, even when its type is larger: one
        # short row (at most four words) directly above a longer display row set in
        # another face, which a byline in smaller type then follows.
        words = re.findall(r"[^\W\d_]+", e["text"])
        if not 1 <= len(words) <= 4 or e["text"].strip().endswith(":"): return False
        eb = e["box_px"]; body = mt.get("body_size_px") or 0
        for t in sorted(runs, key=lambda r: r["box_px"][1]):
            tb = t["box_px"]
            if t is e or not eb[3] - 1 <= tb[1] <= eb[3] + 3 * e["run_size_px"]: continue
            if min(eb[2], tb[2]) - max(eb[0], tb[0]) <= 0: continue
            if (face(t) == face(e) or not body or t["run_size_px"] < 1.3 * body or name_run(t) or
                    len(re.findall(r"[^\W\d_]+", t["text"])) < max(4, 2 * len(words))): return False
            if any(r is not t and eb[3] - 1 <= r["box_px"][1] < tb[1] and
                   min(eb[2], r["box_px"][2]) - max(eb[0], r["box_px"][0]) > 0 for r in runs): return False
            rows = [t]
            for r in sorted(runs, key=lambda r: r["box_px"][1]):
                if (r is not t and face(r) == face(t) and abs(r["run_size_px"] - t["run_size_px"]) <= SIZE_TOL * t["run_size_px"]
                        and 0 <= r["box_px"][1] - max(x["box_px"][3] for x in rows) <= PARAMS["stack_gap_em"] * t["run_size_px"]):
                    rows.append(r)
            bottom = max(r["box_px"][3] for r in rows)
            return any(r not in rows and bottom < r["box_px"][1] <= bottom + AUTHOR_GAP_EM * r["run_size_px"]
                       and r["run_size_px"] < (1 - SIZE_TOL) * t["run_size_px"] and byline_shaped(r) for r in runs)
        return False
    def words_of(rs): return len(re.findall(r"[^\W\d_]+", " ".join(r["text"] for r in rs)))
    def followed_by_byline(block, ts, own=False, labels=True, title_rows=(), rows=3):
        # Within the three printed rows under the block (rows that overlap its width,
        # the first within author_gap_em of its letter heights), a byline-shaped row in
        # smaller type (for a proposed title's own byline, at most its size, as cover
        # sheets set it) or an abstract label (labels=False: the byline row only; rows=1:
        # the first row under the block only). Rows in title_rows are another pair's
        # title text, never this block's byline.
        bottom = max(r["box_px"][3] for r in block); x0 = min(r["box_px"][0] for r in block); x1 = max(r["box_px"][2] for r in block)
        under = sorted((r for r in runs if r not in block and r["box_px"][1] >= bottom - 1
                        and min(x1, r["box_px"][2]) - max(x0, r["box_px"][0]) > 0), key=lambda r: (r["box_px"][1], r["box_px"][0]))
        if not under or under[0]["box_px"][1] > bottom + AUTHOR_GAP_EM * ts: return False
        lines = []
        for r in under:
            if r["line"] not in lines: lines.append(r["line"])
        limit = (1 + SIZE_TOL) * ts if own else (1 - SIZE_TOL) * ts
        return any(r["line"] in lines[:rows] and (((r["run_size_px"] <= limit if own else r["run_size_px"] < limit) and
                                                 r["id"] not in title_rows and byline_shaped(r)) or
                   labels and re.match(r"^(?:Abstract|Summary|(?:\d+\.?\s+)?Introduction)\b", r["text"].strip(), re.I)) for r in under)
    title_chains = None
    def offaxis_masthead(e):
        # Lane masthead R3 (2026-11-04): the title is chosen by adjacency. A lower
        # display block (1.3 body sizes or more, three words or more, its stacked
        # same-size rows) followed within three rows by a byline-shaped row or an
        # abstract label is a title-plus-byline pair. A proposed title above such a
        # pair, with fewer words and no byline of its own, is a masthead when its left
        # edge and its centre are both more than one em off the pair's (AP03 banner:
        # left 96 vs 154, centre 320 vs 640; AP10 logo: left 883 vs 221, centre 948 vs
        # 546; em the larger of the two sizes), or when it stands in the top band in a
        # face used nowhere else on the paper. Two seen papers carry the measurements;
        # with no such pair (no byline-shaped row) nothing is rejected (R4).
        nonlocal title_chains
        if e not in proposed: return False
        body = mt.get("body_size_px") or 0
        if not body: return False
        if title_chains is None:
            title_chains = []
            for t in sorted(runs, key=lambda r: (r["box_px"][1], r["box_px"][0])):
                ts = t["run_size_px"]
                if ts < 1.3 * body or t["box_px"][1] >= .5 * p["region_box_px"][3] or words_of([t]) < 3: continue
                same = lambda r: abs(r["run_size_px"] - ts) <= SIZE_TOL * ts
                overlaps = lambda a, b: min(a["box_px"][2], b["box_px"][2]) - max(a["box_px"][0], b["box_px"][0]) > 0
                if any(r is not t and same(r) and overlaps(r, t) and 0 <= t["box_px"][1] - r["box_px"][3] <= PARAMS["stack_gap_em"] * ts
                       for r in runs): continue   # not the block's top row
                block = [t]
                for r in sorted(runs, key=lambda r: r["box_px"][1]):
                    if (r not in block and same(r) and any(overlaps(r, b) for b in block)
                            and 0 <= r["box_px"][1] - max(b["box_px"][3] for b in block) <= PARAMS["stack_gap_em"] * ts):
                        block.append(r)
                if followed_by_byline(block, ts): title_chains.append((block, ts, followed_by_byline(block, ts, labels=False, rows=1)))
        band = proposed
        bb = [min(r["box_px"][0] for r in band), min(r["box_px"][1] for r in band),
              max(r["box_px"][2] for r in band), max(r["box_px"][3] for r in band)]
        size = max(r["run_size_px"] for r in band)
        # Re-ladder (2026-11-05): the rows of a display block whose first row under it is a
        # smaller byline of its own are that pair's title, never the proposed title's own byline, even when
        # they read as names (a title-case title row holding "and" or ";") and lie under it.
        paired_title_rows = {r["id"] for block, ts, named in title_chains if named
                             and not any(r in band for r in block) for r in block}
        if followed_by_byline(band, size, own=True, title_rows=paired_title_rows): return False   # a title with its own byline stays
        band_faces = {f for r in band for f in font_faces(r)}
        unique_face = bool(band_faces) and all(faces_elsewhere[f] == 0 for f in band_faces)
        lone_face = top_band(bb) and unique_face
        for block, ts, named in title_chains:
            tb = [min(r["box_px"][0] for r in block), min(r["box_px"][1] for r in block),
                  max(r["box_px"][2] for r in block), max(r["box_px"][3] for r in block)]
            if tb[1] < bb[3] - 1 or any(r in band for r in block) or words_of(band) >= words_of(block): continue
            em = max(size, ts)
            # off the pair's axis: left edge and centre both more than an em away, and the
            # block standing out of the pair's width by more than an em on one side (AP03
            # 58 px left of it, AP10 143 px right of it; a short row inside the pair's
            # width, test_front_matter's "Materials" fixture, is not rejected this way)
            axis_off = abs(bb[0] - tb[0]) > em and abs((bb[0] + bb[2]) / 2 - (tb[0] + tb[2]) / 2) > em
            off = axis_off and (tb[0] - bb[0] > em or bb[2] - tb[2] > em)
            # the logo's face: on page 1 only in runs above the pair and across the band's width.
            # Re-ladder (2026-11-05): off the pair's axis, a band in a face used on no other page
            # is a logo wherever it stands (one overlapping the title's right end and lying
            # below the top band, MIMIC2); in the top band the face alone suffices, as before.
            alone = (lone_face or (axis_off and unique_face)) and not any(r not in band and font_faces(r) & band_faces and
                                          (r["box_px"][1] >= tb[1] or min(bb[2], r["box_px"][2]) - max(bb[0], r["box_px"][0]) <= 0) for r in runs)
            if off or alone: return True
        return False
    def apart_label(e):
        # Round 6 rule T3: an article label is short and stands above the title. The opening row of
        # a proposed title of several rows, of one to three words, that shares no width with any
        # other row of it (a wrapped title's rows always overlap: left-set or centred) and lies
        # wholly above them is a label set apart, never the title, even in the title's type.
        if e not in proposed or not 1 <= len(re.findall(r"[^\W\d_]+", e["text"])) <= 3: return False
        others = [r for r in proposed if r["line"] != e["line"]]
        if not others or any(r["box_px"][1] < e["box_px"][1] for r in others): return False
        return all(min(e["box_px"][2], r["box_px"][2]) - max(e["box_px"][0], r["box_px"][0]) <= 0
                   and e["box_px"][3] <= r["box_px"][1] + 1 for r in others)
    def single_label(e):
        # Round 6 rule T6: one word ("Abstract", "Primer", "Editorial", also letter-spaced) is not the
        # title when a longer block in large type (two words or more, 1.3 body sizes or more, not
        # recurring at its size on other pages) starts in the top half of the page (rule T1).
        body = mt.get("body_size_px") or 0
        tokens = e["text"].split()
        word = "".join(tokens) if len(tokens) > 1 and all(len(t) == 1 for t in tokens) else e["text"].strip()
        if not body or e not in proposed or not re.fullmatch(r"[^\W\d_]{3,}", word): return False
        # only a row standing apart: the opening row of the proposed title, with no row of its own type stacked
        # directly under it (a wrapped title's last word, "... of Scientific / Perspectives", is title: T4)
        if any(r["box_px"][1] < e["box_px"][1] - 1 for r in proposed if r["line"] != e["line"]): return False
        # rule C1: a one-word title confirmed by its own author line directly under it stays the title
        # (directly under it: no display row of the page, in any column, stands between the word and that line)
        if followed_by_byline([e], e["run_size_px"], own=True, labels=False, rows=1):
            under = [r for r in runs if r is not e and r["box_px"][1] >= e["box_px"][3] - 1 and byline_shaped(r)
                     and min(e["box_px"][2], r["box_px"][2]) - max(e["box_px"][0], r["box_px"][0]) > 0]
            first = min(under, key=lambda r: r["box_px"][1]) if under else None
            if first is None or not any(r is not e and e["box_px"][3] - 1 <= r["box_px"][1] < first["box_px"][1]
                                        and r["run_size_px"] >= 1.3 * body for r in runs): return False
        if any(r["line"] != e["line"] and font_faces(r) == font_faces(e) and abs(r["run_size_px"] - e["run_size_px"]) <= SIZE_TOL * e["run_size_px"]
               and -1 <= r["box_px"][1] - e["box_px"][3] <= PARAMS["stack_gap_em"] * e["run_size_px"] for r in proposed): return False
        return any(r is not e and r["line"] != e["line"] and r not in proposed
                   and len(re.findall(r"[^\W\d_]+", r["text"])) >= 2 and r["run_size_px"] >= 1.3 * body
                   and r["box_px"][1] < .5 * p["region_box_px"][3]
                   and not any(abs(z - r["run_size_px"]) <= SIZE_TOL * r["run_size_px"] for z in recurrences(r["text"])) for r in runs)
    def banner(e, labels=True, t6=True):
        t = e["text"].strip()
        return (len(normalized(t)) >= 12 and any(abs(size - e["run_size_px"]) <= SIZE_TOL * e["run_size_px"] for size in recurrences(t)) or
                t.casefold() == 'by' or
                (labels and article_type(e)) or series_label(e) or (labels and (apart_label(e) or (t6 and single_label(e)))) or
                bool(re.fullmatch(r"(?:[\w&.-]+\s+){0,3}Journal of [\w &-]+|[\w .-]*Public Access|Author Manuscript", t, re.I)) or
                separated_masthead(e) or offaxis_masthead(e))
    proposed = [e for e in trs if e["run_size_px"] >= PARAMS["title_size_share"] * max((r["run_size_px"] for r in trs), default=0)]
    if not trs and front_page != 1:
        # Rule 6's title search is page-one only. A later first-text page
        # requires display-sized, nonrepeated words in its upper half.
        body_size = mt.get("body_size_px") or 16
        candidates = [e for e in runs if e["run_size_px"] >= 1.4 * body_size
                      and e["box_px"][1] < .5 * p["region_box_px"][3]
                      and len(re.findall(r"[^\W\d_]+", e["text"])) >= 3
                      and not repeated[normalized(e["text"])]]
        if candidates:
            size = max(e["run_size_px"] for e in candidates)
            for e in sorted(candidates, key=lambda e: (e["box_px"][1], e["box_px"][0])):
                if e["run_size_px"] < PARAMS["title_size_share"] * size: continue
                if trs and e["box_px"][1] - max(r["box_px"][3] for r in trs) > PARAMS["stack_gap_em"] * size: break
                trs.append(e)
    if proposed and not thesis_title and any(banner(e) for e in proposed):
        # An article label can share rule 6's title block and type size with the
        # real title. Only the label is rejected in that case.
        # A series label (X09 "ORAL MEDICINE" over its title) is rejected alone, like an article type.
        label = lambda e: article_type(e) or series_label(e) or apart_label(e)
        # Rule T6 alone (no other banner reason): only the one-word label leaves the title. It is no
        # article-information record (memo 1, M2): it and the other rows of its rule-6 block stay for the copy,
        # which quotes rows it cannot place under its flagged "not placed" block and lists them as doubtful.
        t6_only = not any(banner(e, t6=False) for e in proposed)
        old_ids = ({e["id"] for e in trs if single_label(e)} if t6_only else
                   {e["id"] for e in trs if label(e)} if any(label(e) for e in proposed)
                   else set(title_ids)); trs = []
        if t6_only: result["t6_label_run_ids"] = sorted(old_ids)
        # (rule T6: after a one-word label, the longer block in large type may hold two words)
        min_words = 2 if t6_only else 3
        candidates = [e for e in runs if e["id"] not in old_ids and not banner(e)
                      and e["box_px"][1] < .5 * p["region_box_px"][3]
                      and len(re.findall(r"[^\W\d_]+", e["text"])) >= min_words]
        if candidates:
            size = max(e["run_size_px"] for e in candidates)
            large = sorted([e for e in candidates if e["run_size_px"] >= PARAMS["title_size_share"] * size], key=lambda e: (e["box_px"][1], e["box_px"][0]))
            trs = [large[0]]
            for e in large[1:]:
                if e["box_px"][1] - max(r["box_px"][3] for r in trs) > PARAMS["stack_gap_em"] * size: break
                trs.append(e)
            result["title_reselected"] = True
            # The rejected rows of rule 6's title (a series label, a journal masthead,
            # a banner) are printed front matter: article information, never unplaced
            # (AG08 series label; AG10 "Contents lists available at ScienceDirect").
            for e in sorted((e for e in runs if e["id"] in old_ids and e not in trs and e["text"].strip() and not t6_only),
                            key=lambda e: (e["box_px"][1], e["box_px"][0])):
                result.setdefault("article_info", []).append(dict(page=front_page, run_ids=[e["id"]], text=e["text"].strip(),
                                                                  role="series label" if series_label(e) else "rejected title row"))
    if not trs:
        flags.append("no title from rule 6: authors not searched"); result["checks"] = {"title_found": False}
        write_json(os.path.join(paper_dir, "authors.json"), result, indent=1, ensure_ascii=False); return result
    big = max(e["run_size_px"] for e in trs)
    trs = sorted([e for e in trs if e["run_size_px"] >= PARAMS["title_size_share"] * big], key=lambda e: (e["box_px"][1], e["box_px"][0]))
    title_ids = {e["id"] for e in trs}   # badges beside the title stay out of the author search too
    tx0 = min(e["box_px"][0] for e in trs); tx1 = max(e["box_px"][2] for e in trs); ty0 = min(e["box_px"][1] for e in trs); ty1 = max(e["box_px"][3] for e in trs)
    lefts = collections.Counter(round(min(e["box_px"][0] for e in trs if e["line"] == li) / big) for li in {e["line"] for e in trs})
    col0 = max(lefts, key=lambda k: (lefts[k], -k)) * big   # the title's own left edge: the commonest line start
    beside = [e for e in trs if e["box_px"][2] < col0 - 0.5 * big]
    trs = [e for e in trs if e not in beside]
    tx0 = min(e["box_px"][0] for e in trs); tx1 = max(e["box_px"][2] for e in trs)
    # The largest-size filter establishes the title, not its lower size limit.
    # A smaller display row immediately below it can be a subtitle (T11), even
    # when rule 6 put that row in a separate block. Never hop over names or prose.
    classes = {m: b["cls"] for b in mt.get("blocks", []) for b0 in p["blocks"]
               if b0["id"] == b["id"] for m in b0["members"]}
    subtitle_start = None
    body = mt.get("body_size_px") or 0
    title_faces = {f for e in trs if abs(e["run_size_px"] - big) <= SIZE_TOL * big for f in font_faces(e)}
    def subtitle_block(row, size):
        # Round 6 rule T7: a display row under the title that reads as names is still a subtitle when
        # its own block (the rows stacked under it in its type) is no series of names (a row of figures
        # alone, such as a span of years: rule A2, no digits in a name) and a smaller row that reads as
        # names stands under that block, inside the author gap (rule A1: the authors under the subtitle).
        faces = {f for e in row for f in font_faces(e)}
        same = lambda r: abs(r["run_size_px"] - size) <= SIZE_TOL * size and font_faces(r) and font_faces(r) <= faces
        block = list(row); x0 = min(e["box_px"][0] for e in row); x1 = max(e["box_px"][2] for e in row)
        for r in sorted(runs, key=lambda r: (r["box_px"][1], r["box_px"][0])):
            if (r not in block and r["id"] not in title_ids and same(r) and min(x1, r["box_px"][2]) - max(x0, r["box_px"][0]) > 0
                    and 0 <= r["box_px"][1] - max(b["box_px"][3] for b in block) <= PARAMS["stack_gap_em"] * size):
                block.append(r)
        figures = any(re.search(r"\d", r["text"]) and not re.search(r"[^\W\d_]{2,}", r["text"]) for r in block if r not in row)
        if not figures: return False
        bottom = max(b["box_px"][3] for b in block)
        return any(r not in block and r["id"] not in title_ids and bottom < r["box_px"][1] <= bottom + AUTHOR_GAP_EM * r["run_size_px"]
                   and r["run_size_px"] < (1 - SIZE_TOL) * size and min(x1, r["box_px"][2]) - max(x0, r["box_px"][0]) > 0
                   and byline_shaped(r) for r in runs)
    while body:
        below_title = [e for e in runs if e["id"] not in title_ids and e["box_px"][1] >= ty1 - 1
                       and min(tx1, e["box_px"][2]) - max(tx0, e["box_px"][0]) >=
                       .5 * min(tx1 - tx0, e["box_px"][2] - e["box_px"][0])]
        if not below_title: break
        first = min(below_title, key=lambda e: (e["box_px"][1], e["box_px"][0]))
        row = sorted([e for e in below_title if e["line"] == first["line"]], key=lambda e: e["box_px"][0])
        size = max(e["run_size_px"] for e in row)
        bx = [min(e["box_px"][0] for e in row), min(e["box_px"][1] for e in row),
              max(e["box_px"][2] for e in row), max(e["box_px"][3] for e in row)]
        aligned_title = abs(bx[0] - tx0) <= .5 * big or abs((bx[0] + bx[2] - tx0 - tx1) / 2) <= .5 * big
        continuation = abs(size-big) <= SIZE_TOL*big and bx[1]-ty1 <= PARAMS['stack_gap_em']*size
        # Round 6 rules T4/T5: a directly stacked row in the title's exact type (its faces and its
        # size) is title, never an author line, even when its words read as names (a wrapped
        # title's last words: "... in Vitro Study of" over two capitalised words).
        title_type = continuation and all(font_faces(e) and font_faces(e) <= title_faces
                                          and abs(e["run_size_px"] - big) <= SIZE_TOL * big for e in row)
        # (a cover form can set its names in the title's type; a row holding a personal initial, "J.", is names)
        if title_type and any(re.search(r"(?<![\w.])[A-Z]\.(?=[\s\-A-Z]|$)", e["text"]) for e in row): title_type = False
        if (not (body * (1 + SIZE_TOL) < size <= big * (1 + SIZE_TOL)) or
            bx[1] - ty1 > PARAMS["stack_gap_em"] * size or not aligned_title or
            # Re-ladder (2026-11-05): an article-type word is a label only as a title's
            # opening row; a continuation row (the title's size, directly stacked, aligned)
            # reading "review" is the wrapped title's last word (AS14), whatever its count of words.
            any((classes.get(e["id"]) == "main" and not continuation) or banner(e, labels=not continuation) or
                (name_run(e) and not title_type and not subtitle_block(row, size)) or
                INSTITUTION.match(e["text"].strip()) or GROUP_OPEN.match(e["text"].strip()) for e in row)):
            break
        if subtitle_start is None and size < PARAMS["title_size_share"] * big:
            subtitle_start = first["line"]
        trs += row; title_ids.update(e["id"] for e in row)
        ty1 = bx[3]
    tlines = sorted({e["line"] for e in trs}, key=lambda li: min(e["box_px"][1] for e in trs if e["line"] == li))
    title_text = ""
    for li in tlines:
        separator = (": " if li == subtitle_start and title_text and title_text[-1] not in ":;.!?–—-" else " ") if title_text else ""
        title_text += separator + " ".join(e["text"] for e in sorted([x for x in trs if x["line"] == li], key=lambda x: x["box_px"][0]))
    tx0 = min(e["box_px"][0] for e in trs); tx1 = max(e["box_px"][2] for e in trs)
    result["title"] = {"text": title_text,
                       "box_px": [tx0, ty0, tx1, ty1], "lines": len(tlines), "size_px": round(big, 1), "left_out": [e["text"] for e in beside]}
    title_exclusions = [c for c in title_exclusions if c['run'] in title_ids]
    source_text = {o['id']: o['text'] for o in p['elements'] if o['kind'] == 'text'}
    if title_exclusions or any(e['text'] != source_text.get(e['id'], e['text']) for e in trs):
        # A title row read without its unprinted characters keeps its own row text too.
        if title_exclusions: result['title_exclusions'] = title_exclusions
        result['title_rows'] = [dict(run=e['id'], text=e['text'], box_px=e['box_px']) for e in trs]
    if (subtitle_start is not None and below_title and size <= body * (1 + SIZE_TOL) and
        not any(classes.get(e["id"]) == "authors" and e["id"] not in title_ids for e in runs) and
        not any(name_run(e) or GROUP_OPEN.match(e["text"].strip()) or GROUP_WORD.search(e["text"]) for e in row) and
        (any(classes.get(e["id"]) == "main" for e in row) or sum(len(e["text"].split()) for e in row) >= 10)):
        # A subtitle can precede a report's introductory paragraph without a
        # byline. Moving the title's bottom must not manufacture authors there.
        result["title_run_ids"] = [e["id"] for e in trs]
        result["checks"] = {"title_found": True, "title_lines": len(tlines), "authors_found": 0,
                            "names_ok": 0, "authors_with_orcid": 0, "markers_used": [], "status": "no authors"}
        result["author_box_px"] = result["affiliation_box_px"] = None
        write_json(os.path.join(paper_dir, "authors.json"), result, indent=1, ensure_ascii=False)
        return result
    # the author lines: under the title, in its column, stacked, at one size
    def in_column(e): return min(e["box_px"][2], tx1) - max(e["box_px"][0], tx0) >= 0.5 * (e["box_px"][2] - e["box_px"][0]) and (e["box_px"][0] >= tx0 - big or min(e["box_px"][2], tx1) - max(e["box_px"][0], tx0) >= 0.5 * (tx1 - tx0))
    author_ids = {m for b in mt.get("blocks", []) if b["cls"] == "authors" for b0 in p["blocks"] if b0["id"] == b["id"] for m in b0["members"]}
    detached_byline = []
    by_introducer = None
    # A printed "by" is independent evidence for a portrait/sidebar panel.
    # Require the very next nearby row to contain a personal name, not prose.
    known_byline = any(e['id'] in author_ids and name_run(e) and ty1 <= e['box_px'][1] <=
                      ty1+AUTHOR_GAP_EM*max(big,e['run_size_px']) for e in runs)
    front_limit = min((e['box_px'][1] for e in p['elements'] if e['kind']=='text' and
        e['box_px'][1] >= ty1 and re.match(r'^(?:Abstract|Summary|(?:\d+\.?\s+)?Introduction)\b',e['text'],re.I)),
        default=.5*p['region_box_px'][3])
    for by in sorted(runs if not known_byline else [], key=lambda e: (e['box_px'][1], e['box_px'][0])):
        if by['box_px'][1] < ty1 or not re.match(r'^by(?:\s|$)', by['text'].strip(), re.I): continue
        if by['box_px'][1] > front_limit+by['run_size_px']: continue
        text = re.sub(r'^by\s*', '', by['text'].strip(), flags=re.I)
        following = sorted((e for e in runs if e is not by and
            by['box_px'][1] <= e['box_px'][1] <= by['box_px'][3]+by['run_size_px'] and
            abs(e['box_px'][0]-by['box_px'][2]) <= 2*by['run_size_px']),
            key=lambda e: (e['box_px'][1], e['box_px'][0]))
        name = by if text and byline_name_groups([text]) else (
            following[0] if not text and following and byline_name_groups([following[0]['text']]) else None)
        if name is not None:
            by_introducer = by; detached_byline = [name]; break
    if thesis_title:
        by = next((e for e in runs if e['text'].strip().lower()=='by' and e['box_px'][1]>ty1), None)
        if by:
            following = sorted((e for e in runs if e['box_px'][1]>by['box_px'][3]), key=lambda e:e['box_px'][1])
            if following and name_run(following[0]): detached_byline = [following[0]]
    if not detached_byline and front_columns and front_columns.get("author_blocks"):
        # Rule 7's bounded name block in a front column beside the introduction is
        # the byline even across a picture or wide gap below the title (AG05).
        named = sorted((e for e in runs if e["box_px"][1] >= ty1 and e["id"] not in title_ids and
                        any(e["id"] in b["members"] for b in p["blocks"] if b["id"] in front_columns['author_blocks'])),
                       key=lambda e: (e["box_px"][1], e["box_px"][0]))
        # Only where the ordinary search under the title cannot reach it.
        if (named and name_run(named[0]) and
                named[0]["box_px"][1] - ty1 > AUTHOR_GAP_EM * max(big, named[0]["run_size_px"])): detached_byline = named
    if not detached_byline and (front_page != 1 or front_columns):
        # A wide front panel can put several separately marked names far
        # below the title beside a body column. The whole name block, not
        # nearby body rows on shared baselines, establishes this byline.
        for b in p["blocks"]:
            mem = [e for e in runs if e["id"] in b["members"]]
            if (len(mem) >= 2 and all(in_column(e) and e["box_px"][1] >= ty1 and name_run(e)
                                     and re.search(r"\d\s*$", e["text"]) for e in mem)):
                detached_byline = mem; break
    below = [e for e in runs if e["box_px"][1] >= ty1 - 1 and (in_column(e) or e["id"] in author_ids) and e["id"] not in title_ids]
    if detached_byline: below = detached_byline
    address_open = ADDRESS_OPEN
    def row_address(e, row):
        # A byline row can continue with the author's affiliation in another
        # size (AL03 "B. E. CAIRNS Associate Professor, Canada Research Chair
        # ..." in smaller italics, measured 2026-11-03): the row is cut at the
        # run that opens with an academic role or institution word, set right of
        # a name run in a size outside its tolerance. That run starts the address.
        left = [o for o in row if o is not e and o["line"] == e["line"] and o["box_px"][2] <= e["box_px"][0] + e["size_px"]]
        return bool(left) and (address_open.match(e["text"].strip()) or INSTITUTION.match(e["text"].strip())) and all(
            name_run(o) and abs(e["run_size_px"] - o["run_size_px"]) > SIZE_TOL * o["run_size_px"] for o in left)
    row_addresses = [e for e in below if row_address(e, below)]
    below = [e for e in below if e not in row_addresses]
    grew = True
    while grew:   # a contiguous run on either side (initial, marker or address prefix) belongs to the row too
        grew = False; ids = {e["id"] for e in below}
        for e in runs:
            if e["id"] in ids or e["id"] in title_ids or e["box_px"][1] < ty1 - 1 or e in row_addresses: continue
            # An address column beside the byline can share a rule 1 line with a name row
            # (AG09: a sidebar "Department of" beside the fifth author's row). An
            # institution-led run outside the title's column, set in another size, is
            # not part of that row and must not end the byline there.
            if (not in_column(e) and e["id"] not in author_ids and INSTITUTION.match(e["text"].strip()) and
                    all(abs(e["run_size_px"] - o["run_size_px"]) > SIZE_TOL * o["run_size_px"]
                        for o in below if o["line"] == e["line"])): continue
            beside = [o for o in below if o["line"] == e["line"] and 0 <= max(e["box_px"][0] - o["box_px"][2], o["box_px"][0] - e["box_px"][2]) <= 2 * e["size_px"]]
            if beside and row_address(e, beside): row_addresses.append(e); continue
            if beside: below.append(e); grew = True
    by_line = collections.defaultdict(list)
    below_ids = {e["id"] for e in below}
    below += [e for e in runs if e["id"] not in below_ids and e["id"] in attached and attached[e["id"]]["id"] in below_ids]
    for e in below: by_line[attached.get(e["id"], e)["line"]].append(e)
    order = sorted(by_line, key=lambda li: min(e["box_px"][1] for e in by_line[li]))
    def lsize(li):
        cs = [c for e in by_line[li] if e["id"] not in attached for c in aligned[e["id"]] if not c.get("space") and not c.get("sup")]
        return statistics.median(c["size"] for c in cs) if cs else 0
    alines = []; sup_lines = []; field_rows = []; released = []
    for li in order:
        top = min(e["box_px"][1] for e in by_line[li]); s = lsize(li)
        if not alines:
            # Small capitals can sit farther away in their own em units. A rule 6
            # author band is independent evidence for accepting that first line.
            line_text = " ".join(e["text"] for e in sorted(by_line[li], key=lambda e: e["box_px"][0]))
            words = re.findall(r"[^\W\d_]+", line_text)
            name_line = bool(words) and all(w[0].isupper() or w.lower() in PARTICLES or w == "and" for w in words)
            known_band = name_line and any(e["id"] in author_ids for e in by_line[li])
            if s <= 0 or not detached_byline and top - ty1 > AUTHOR_GAP_EM * (max(s, big) if known_band else s): break
            if FRONT_LABEL.match(line_text.strip()) or DATE_ROW.match(line_text.strip()):
                # round 6 rules A6 and A9: a front label or a date or "Edited by" line is never an author row; its
                # runs are recorded as released, so the copy keeps them printed (memo 1: nothing is lost)
                released.extend(e["id"] for e in by_line[li]); break
            alines.append(li); s0 = s; last = max(e["box_px"][3] for e in by_line[li]); continue
        row_text = " ".join(e["text"] for e in sorted(by_line[li], key=lambda e: e["box_px"][0]))
        if FRONT_LABEL.match(row_text.strip()):   # round 6 rule A6: the author list ends at a label such as "Abstract"
            released.extend(e["id"] for e in by_line[li]); break
        # A form sheet (a submission cover page: rows "Short Title: ...", "Corresponding Author: ...")
        # is no byline of names; the address-row tests below do not cut it, only an institution
        # opening ends it, as before.
        # The field label can stand in its own run on the printed row, left of the value.
        def printed_row(a):
            lines = {e["line"] for e in by_line[a]}
            return " ".join(e["text"] for e in sorted((r for r in runs if r["line"] in lines), key=lambda e: e["box_px"][0]))
        form = any(FIELD_ROW.match(printed_row(a).strip()) for a in alines + [li])
        # A labelled field row under the byline ("Designation: Senior Lecturer, ...", "Department: ...",
        # "Corresponding author: ...") is a field of the form, never a row of names, whatever its value
        # names: it is passed over at the byline's size and stacking distance. Under such a row the byline
        # goes on only with a row that reads as names alone (a form title page sets each author's name
        # row above that author's fields); any other row ends it.
        # The field belongs to the byline's own block family: none of its runs is in a block rule 6 classes as
        # body or abstract text. A label followed on its row by a sentence (a run of three lower-case words:
        # an abstract's "Background: Most microorganisms in the oral ...") is a run-in heading, not a field.
        label_row = FIELD_ROW.match(printed_row(li).strip())
        value = printed_row(li).strip()[label_row.end():] if label_row else ""
        field_row = (label_row and not AUTHOR_FIELD.match(printed_row(li).strip()) and
                     not any(classes.get(e["id"]) in ("main", "abstract") or e["id"] in abstract_ids for e in by_line[li]) and
                     not re.search(r"(?:\b[a-z][a-z'’\-]*\b[\s,]+){2}\b[a-z][a-z'’\-]*\b", value))
        if field_row:
            if abs(s - s0) > SIZE_TOL * s0 or top - last > AUTHOR_STACK_EM * s0: break
            field_rows.append(li); last = max(e["box_px"][3] for e in by_line[li]); continue
        if INSTITUTION.match(row_text.strip()) or (not form and institution_row(row_text)): break
        # A row opening with a raised marker before a capital, under a byline row that sets raised
        # markers directly after its names (anywhere in the row), is an affiliation row even when it
        # opens with the institution's own name or a place: names in that byline carry their markers after them.
        def row_chars(line):
            return [c for e in sorted(by_line[line], key=lambda e: e["box_px"][0]) for c in aligned[e["id"]] if not c.get("space")]
        here, above = row_chars(li), row_chars(alines[-1])
        lead = next((i for i, c in enumerate(here) if not c.get("sup")), None)
        postfix = any(c.get("sup") and i and not above[i - 1].get("sup") and above[i - 1]["t"][:1].isalpha() for i, c in enumerate(above))
        if (not form and postfix and lead and here[lead]["t"][:1].isupper() and
                all(not c["t"].isalpha() or len(c["t"]) == 1 and c["t"].islower() for c in here[:lead])): break
        nch = sum(1 for e in by_line[li] for c in aligned[e["id"]] if not c.get("space"))
        if 0 < s < PARAMS["superscript_em"] * s0 and nch <= 12 and top - last <= AUTHOR_STACK_EM * s0: sup_lines.append(li); continue
        if field_rows and not form_name_row(row_text): break
        if abs(s - s0) > SIZE_TOL * s0:
            # A row in another size lying wholly beside the byline rows (a
            # citation column left of a right-hand byline, AL05 "K.S. Kornman a and
            # P.J." over "Polverini b", measured 2026-11-03) is another column's
            # text: it is passed over, and the byline's own next row still has to
            # stand within the stacking distance of the last byline row.
            ax0 = min(e["box_px"][0] for a in alines for e in by_line[a]); ax1 = max(e["box_px"][2] for a in alines for e in by_line[a])
            if top - last <= AUTHOR_STACK_EM * s0 and all(min(e["box_px"][2], ax1) - max(e["box_px"][0], ax0) <= 0 for e in by_line[li]): continue
            break
        if top - last > AUTHOR_STACK_EM * s0: break
        alines.append(li); last = max(e["box_px"][3] for e in by_line[li])
    a9_cleared = False
    if alines:
        # Round 6 rule A9: a reference entry is not an author line. Rows under the title that carry a year and a
        # journal's volume and pages ("2005; 32 (Suppl. 6): 7-15", "2010;141;647-655") are the article's own
        # citation; the author line is then looked for beside or above the title.
        cited = " ".join(e["text"] for li in alines for e in sorted(by_line[li], key=lambda e: e["box_px"][0]))
        # (a reference entry: at most three rows, opening with a surname and initials, "Marsh PD.", "Smith AB,")
        if (len(alines) <= 3 and re.match(r"[A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?\s+[A-Z]{1,3}[.,](?:\s|$)", cited)
                and re.search(r"\b(?:19|20)\d{2}\b\s*[;,]\s*\d+\s*(?:\([^)]{1,20}\)\s*)?[:;(]\s*[\dA-Z]", cited)):
            released.extend(e["id"] for li in alines for e in by_line[li])
            alines = []; sup_lines = []; a9_cleared = True
    a_bottom = max(e["box_px"][3] for e in by_line[alines[-1]]) if alines else 0
    sup_lines = [li for li in sup_lines if min(e["box_px"][1] for e in by_line[li]) <= a_bottom]   # beside an author line, not under the last
    for li in sup_lines:   # its runs join the author line nearest it, as superscripts
        y = min(e["box_px"][1] for e in by_line[li])
        tgt = min(alines, key=lambda a: abs(min(e["box_px"][1] for e in by_line[a]) - y)) if alines else None
        if tgt is None: continue
        for e in by_line[li]:
            for c in aligned[e["id"]]:
                if not c.get("space"): c["sup"] = True
        by_line[tgt] += by_line[li]
    sidebar = False
    # A sidebar starts beside the title even if its last names extend below it. It
    # takes precedence over a tail-only selection or a citation under the title.
    # When rule 6 combined names and addresses, require both a name opening near
    # the title's top and a subsequent institution, then stop at the size change.
    side = []; side_rest = []; side_text = []
    for b in p["blocks"]:
        bx = b["box_px"]
        if not ((bx[2] < tx0 or bx[0] > tx1) and min(bx[3], ty1) > max(bx[1], ty0)): continue
        mem = sorted([e for e in runs if e["id"] in b["members"] and e["id"] not in title_ids and e["id"] not in attached], key=lambda e: (e["box_px"][1], e["box_px"][0]))
        if not mem: continue
        known = any(e["id"] in author_ids for e in mem)
        # (round 6 rule A1, beside the title: the institution may also be named inside the next rows, "Leeds Dental
        # Institute, ...", when the beside block opens with the name in a type of its own)
        old_side = known or (abs(mem[0]["box_px"][1] - ty0) <= big and name_run(mem[0]) and
                             any(INSTITUTION.match(re.sub(r"^[\d\s]+", "", e["text"])) for e in mem[1:]))
        new_side = (not old_side and not alines and abs(mem[0]["box_px"][1] - ty0) <= big and name_run(mem[0]) and
                    len(mem) > 1 and font_faces(mem[0]) != font_faces(mem[1]) and
                    any(INSTITUTION_WORD.search(e["text"]) for e in mem[1:3]))
        if not (old_side or new_side): continue
        size = mem[0]["run_size_px"]; band = []
        for e in mem:
            if (abs(e["run_size_px"] - size) > SIZE_TOL * size or
                INSTITUTION.match(re.sub(r"^[\d\s]+", "", e["text"])) or
                # (round 6 rule A2: a row naming an institution is no row of names; in a beside block found by rule A1)
                (new_side or a9_cleared) and band and INSTITUTION_WORD.search(e["text"]) or
                (band and e["box_px"][1] - max(r["box_px"][3] for r in band) > AUTHOR_STACK_EM * size)): break
            band.append(e)
        if band and (new_side or a9_cleared):
            # (memo 1, M1) the rows stacked under the names in the beside block name the authors' institution: they
            # are the unmarked affiliation, so they stay printed (never left out of the copy text)
            bottom = max(r["box_px"][3] for r in band)
            # Read by printed rows, not runs (memo 2): a row can be cut into runs where its first letters fall on
            # the title's line ("Wes" + "tmoor Oral Health Institute,"); touching runs join without a space.
            rest_rows = []
            for e in mem[len(band):]:
                h = e["box_px"][3] - e["box_px"][1]
                row = next((r for r in rest_rows if min(r[-1]["box_px"][3], e["box_px"][3]) - max(r[-1]["box_px"][1], e["box_px"][1]) >= .5 * h), None)
                if row is None: rest_rows.append([e])
                else: row.append(e)
            for row in rest_rows:
                row.sort(key=lambda r: r["box_px"][0])
                text = row[0]["text"].strip()
                for a_, b_ in zip(row, row[1:]):
                    text += ("" if b_["box_px"][0] - a_["box_px"][2] <= .15 * b_["run_size_px"] else " ") + b_["text"].strip()
                # (the first row names the institution; the rows after it continue it in its own type)
                cont = side_rest and font_faces(row[-1]) == font_faces(side_rest[0]) and abs(row[-1]["run_size_px"] - side_rest[0]["run_size_px"]) <= SIZE_TOL * side_rest[0]["run_size_px"]
                if (min(r["box_px"][1] for r in row) - bottom > AUTHOR_STACK_EM * row[0]["run_size_px"] or FRONT_LABEL.match(text)
                        or not cont and not INSTITUTION_WORD.search(text)): break
                side_rest.extend(row); side_text.append(text); bottom = max(bottom, max(r["box_px"][3] for r in row))
        if band:
            side += band
            # The shared rule 1 line may be sized for the title across the gutter.
            # Use this sidebar's typography for both its names and its addresses.
            for e in mem: mark_raised(e, aligned[e["id"]], line_full, own_size=True)
    if side:
        side_ids = {e["id"] for e in side}
        side += [e for e in runs if e["id"] in attached and attached[e["id"]]["id"] in side_ids]
        by_line = collections.defaultdict(list)
        for e in side: by_line[attached.get(e["id"], e)["line"]].append(e)
        alines = sorted(by_line, key=lambda li: min(e["box_px"][1] for e in by_line[li]))
        s0 = statistics.median(lsize(li) for li in alines); sidebar = True
        flags.append("authors read from a sidebar beside the title")
    if not alines:
        # Round 6 rule A1: under the title first, then beside it, then above it. With nothing under or
        # beside the title, the row directly above it (inside the author gap of its own letter heights,
        # in the title's column, in smaller type: rule A3) is the author line when it reads as names
        # and does not come back on other pages (a running head "Smith et al." does).
        over = [e for e in runs if e["id"] not in title_ids and e["box_px"][3] <= ty0 + 1 and in_column(e)
                and ty0 - e["box_px"][3] <= AUTHOR_GAP_EM * e["run_size_px"] and e["run_size_px"] < (1 - SIZE_TOL) * big]
        if over:
            nearest = max(over, key=lambda e: e["box_px"][3])
            row = [e for e in over if e["line"] == nearest["line"]]
            text = " ".join(e["text"] for e in sorted(row, key=lambda e: e["box_px"][0]))
            if (all(byline_shaped(e) and not banner(e) for e in row) and not recurrences(text)
                    and not any(recurrences(e["text"]) for e in row)):
                by_line = collections.defaultdict(list)
                for e in row + [r for r in runs if r["id"] in attached and attached[r["id"]] in row]: by_line[nearest["line"]].append(e)
                alines = [nearest["line"]]; s0 = lsize(nearest["line"])
                flags.append("authors read from the row above the title")
    if not alines:
        flags.append("no author line under the title"); result["checks"] = {"title_found": True, "authors_found": 0}
        if released: result["released_run_ids"] = sorted(set(released))
        # (memo 2) when rule A9 took the reference entry away and nothing else stands in the author place, the title's
        # rows are recorded, so the copy places the other rows of the title's rule-6 block as before, never drops them
        if a9_cleared: result["title_run_ids"] = [e["id"] for e in trs]
        write_json(os.path.join(paper_dir, "authors.json"), result, indent=1, ensure_ascii=False); return result
    # A short title does not bound the byline's width. Separators can be drawn bars,
    # leaving arbitrarily many independent name runs beyond rule 6's author band.
    # Match full-size letter baselines, not line IDs or tops (raised markers move tops).
    def baseline(e):
        letters = [c for c in aligned[e["id"]] if not c.get("space") and not c.get("sup")
                   and c["t"].isalpha() and c["size"] >= PARAMS["superscript_em"] * s0]
        return statistics.median(c["box"][3] for c in letters) if letters else e["box_px"][3]
    rows = []
    for li in alines:
        full = [baseline(e) for e in by_line[li] if e["id"] not in attached and e["run_size_px"] >= PARAMS["superscript_em"] * s0]
        base = statistics.median(full or [baseline(e) for e in by_line[li]])
        same = next((row for row in rows if abs(row[1] - base) <= .5 * s0), None)
        if same is None: rows.append((li, base))
        else: by_line[same[0]] += by_line[li]
    alines = [li for li, base in sorted(rows, key=lambda row: row[1])]
    selected = {e["id"] for li in alines for e in by_line[li]}
    for e in runs:
        if e["id"] in selected or e["id"] in title_ids: continue
        if abs(e["run_size_px"] - s0) > SIZE_TOL * s0: continue
        if e["id"] not in author_ids and not name_run(e): continue
        li, base = min(rows, key=lambda row: abs(row[1] - baseline(e)))
        if abs(base - baseline(e)) <= .5 * s0:
            by_line[li].append(e); selected.add(e["id"])
    for e in runs:
        target = attached.get(e["id"])
        if e["id"] in selected or target is None or target["id"] not in selected: continue
        li = next(li for li in alines if target in by_line[li])
        by_line[li].append(e); selected.add(e["id"])
    # Affiliations that start on a byline row, after the names: a run that opens with a raised
    # marker or note symbol followed by an institution ("T. NAME* & S. NAME† *Department of ...")
    # begins the affiliations. It, the runs right of it on that row and every later row are
    # address text, not names; they are left to the affiliation reader.
    # The marker may also stand inside the names' run, after a word space: its character is
    # flagged, the names stop before it and the affiliation reader reads the run from it.
    def opens_address(text):
        rest = AFFILIATION_MARK_LEAD.sub("", text.strip(), count=1)
        return rest != text.strip() and bool(INSTITUTION.match(rest) or INSTITUTION_WORD.search(rest.split(",")[0]))
    for n_line, li in enumerate(alines):
        row = sorted(by_line[li], key=lambda e: e["box_px"][0])
        cut = None
        for i, e in enumerate(row):
            cs = aligned[e["id"]]
            for k, c in enumerate(cs):
                if c.get("space") or not (c.get("sup") or c["t"] in NOTE_SYMBOLS): continue
                before = [q for q in cs[:k]]
                if i == 0 and not any(not q.get("space") for q in before): continue   # the row's own first character
                if before and not before[-1].get("space") and not (k == 0): continue   # glued to a name: a name's marker
                if opens_address("".join(q["t"] for q in cs[k:])):
                    cut = (i, k); break
            if cut: break
        if cut is not None:
            i, k = cut
            if k == 0: by_line[li] = row[:i]
            else:
                aligned[row[i]["id"]][k]["_aff_cut"] = True; by_line[li] = row[:i + 1]
            alines = alines[:n_line + 1]; break
    # A manuscript cover sheet (Editorial Manager and similar submission systems) prints the front
    # matter as labelled fields, a label column beside a value column. Its author list is the value
    # of the "Order of Authors:" field (else of "First Author:"): the value on the label's row and the
    # rows stacked under it that start at the value's left edge, at its size, with nothing in the
    # label column beside them; one name per row. The other fields (title, keywords, corresponding
    # author and institution) are no byline, and field labels are never names.
    def field_value(lab, m):
        """The value runs on a field label's row, right of the label (the label's own run when the
        value follows the colon in it, its label characters left out)."""
        if m.groups()[-1].strip():
            cs = aligned[lab["id"]]; colon = next(i for i, c in enumerate(cs) if c["t"] == ":")
            rest = cs[colon + 1:]
            while rest and rest[0].get("space"): rest = rest[1:]
            return [(lab, rest)]
        h = lab["box_px"][3] - lab["box_px"][1]
        return [(e, aligned[e["id"]]) for e in sorted(runs, key=lambda e: e["box_px"][0]) if e is not lab and
                e["box_px"][0] >= lab["box_px"][2] - .25 * h and min(e["box_px"][3], lab["box_px"][3]) - max(e["box_px"][1], lab["box_px"][1]) >= .5 * h]
    def author_field_rows():
        heads = []
        for e in runs:
            if e["box_px"][1] < ty1 - 1 or e["id"] in title_ids: continue
            m = AUTHOR_FIELD.match(e["text"].strip())
            if m: heads.append((0 if m.group(1).lower().startswith("order") else 1, e["box_px"][1], e["id"], e, m))
        if not heads: return []
        _, _, _, lab, m = min(heads, key=lambda h: h[:3])
        first = [(e, cs) for e, cs in field_value(lab, m) if any(not c.get("space") for c in cs)]
        if not first: return []
        size = statistics.median(e["run_size_px"] for e, _ in first)
        x0 = min(c["box"][0] for _, cs in first for c in cs if not c.get("space"))
        if not form_name_row("".join(c["t"] for _, cs in first for c in cs)): return []
        rows = [first]; bottom = max(e["box_px"][3] for e, _ in first); used_ids = {e["id"] for e, _ in first} | {lab["id"]}
        while True:
            later = sorted((e for e in runs if e["id"] not in used_ids and e["box_px"][1] >= bottom - .25 * size), key=lambda e: (e["box_px"][1], e["box_px"][0]))
            if not later: break
            r0 = later[0]; h = r0["box_px"][3] - r0["box_px"][1]
            row = [e for e in later if min(e["box_px"][3], r0["box_px"][3]) - max(e["box_px"][1], r0["box_px"][1]) >= .5 * min(h, e["box_px"][3] - e["box_px"][1])]
            left = min(e["box_px"][0] for e in row)
            if (r0["box_px"][1] - bottom > AUTHOR_STACK_EM * size or left < x0 - size or abs(left - x0) > size or
                    any(abs(e["run_size_px"] - size) > SIZE_TOL * size for e in row)): break
            rows.append([(e, aligned[e["id"]]) for e in sorted(row, key=lambda e: e["box_px"][0])])
            used_ids |= {e["id"] for e in row}; bottom = max(e["box_px"][3] for e in row)
        return rows
    one_per_row = False
    form_rows = author_field_rows()
    if form_rows:
        one_per_row = True; sidebar = False; row_addresses = []
        by_line = collections.defaultdict(list); alines = []
        for row in form_rows:
            li = row[0][0]["line"]
            while li in by_line: li = (li, "form")
            for e, cs in row:
                aligned[e["id"]] = cs; by_line[li].append(e)
            alines.append(li)
        s0 = statistics.median(e["run_size_px"] for li in alines for e in by_line[li])
    selected = {e["id"] for li in alines for e in by_line[li]}
    # Repair only selected author characters. A short initial fragment can be a
    # separate run, or be swept into the previous row by a large shared line box.
    # It must touch the lowercase start of a word on its own physical baseline.
    joins = []
    aruns = [e for e in runs if e["id"] in selected]
    if by_introducer is not None:
        if by_introducer['id'] in selected:
            cs = aligned[by_introducer['id']]
            prefix = re.match(r'\s*by\s+', ''.join(c['t'] for c in cs), re.I)
            if prefix: aligned[by_introducer['id']] = cs[prefix.end():]
        result['byline_introducer_ids'] = [by_introducer['id']]
    # Legacy sign fonts can claim ordinary letters. Require both a distinct sign
    # face in the byline and the same code at the start of a smaller address row.
    # Ordinary y in a surname, or an alphabetical marker in a text face, stays y.
    aliases = {"y": "†", "z": "‡", "x": "§"}
    sign_face = re.compile(r"Symbol|AdvP4C4E|AdvPi|AdvMPi|Dingbat|Special", re.I)
    label_codes = set()
    for e in runs:
        if e["id"] in selected or e["box_px"][1] < ty1 or e["run_size_px"] >= .95 * s0: continue
        cs = [c for c in aligned[e["id"]] if not c.get("space")]
        if cs and cs[0]["t"] in aliases and sign_face.search(cs[0].get("font", "")):
            if len(cs) > 1 and cs[1]["t"].isupper() and cs[1].get("font") != cs[0].get("font"):
                label_codes.add((cs[0]["font"], cs[0]["t"]))
    marker_codes = {(c.get("font"), c["t"]) for e in aruns for c in aligned[e["id"]]
                    if (c.get("font"), c["t"]) in label_codes}
    marker_glyphs = []
    for e in runs:
        cs = aligned[e["id"]]
        first = next((c for c in cs if not c.get("space")), None)
        for c in cs:
            if (c.get("font"), c["t"]) not in marker_codes or not (e in aruns or c is first): continue
            marker_glyphs.append({"run": e["id"], "char_id": c["char_id"], "font": c["font"], "before": c["t"], "after": aliases[c["t"]]})
            c["t"] = aliases[c["t"]]
    if marker_glyphs: result["marker_glyphs"] = marker_glyphs
    bases = {e["id"]: baseline(e) for e in aruns}
    for e in aruns:
        cs = [c for c in aligned[e["id"]] if not c.get("space")]
        letters = [c for c in cs if c["t"].isalpha() and not c.get("sup")]
        fragments = []
        if 0 < len(cs) <= 2 and len(letters) == len(cs): fragments.append(letters)
        else:
            displaced = [c for c in letters if abs(c["box"][3] - bases[e["id"]]) > .6 * s0]
            if 0 < len(displaced) <= 2: fragments.append(displaced)
        for frag in fragments:
            frag.sort(key=lambda c: c["box"][0])
            if not frag[0]["t"].isupper(): continue
            right = max(c["box"][2] for c in frag); top = min(c["box"][1] for c in frag); bottom = max(c["box"][3] for c in frag)
            targets = []
            for other in aruns:
                if other is e: continue
                first = next((c for c in aligned[other["id"]] if not c.get("space")), None)
                if first is None or not first["t"].islower() or first.get("sup"): continue
                gap = first["box"][0] - right
                overlap = min(bottom, first["box"][3]) - max(top, first["box"][1])
                if (-.1 * s0 <= gap <= PARAMS["wordspace_min_em"] * s0 and overlap >= .3 * min(bottom - top, first["box"][3] - first["box"][1]) and
                    (attached.get(e["id"]) is other or abs(first["size"] - frag[0]["size"]) <= SIZE_TOL * s0)): targets.append((abs(gap), other, first))
            if not targets: continue
            _, other, first = min(targets, key=lambda t: t[0])
            prefix = "".join(c["t"] for c in frag)
            joins.append({"kind": "initial", "text": prefix, "source_run": e["id"], "target_run": other["id"],
                          "char_ids": [c.get("char_id") for c in frag], "target_char_id": first.get("char_id"),
                          "box_px": [min(c["box"][0] for c in frag), top, right, bottom]})
            aligned[e["id"]] = [c for c in aligned[e["id"]] if all(c is not f for f in frag)]
            aligned[other["id"]] = frag + aligned[other["id"]]
    # Spacing accents have their own ink boxes, often above an adjacent letter.
    # Use overlap, not stream order or superscript status, to identify that letter.
    # Unicode compatibility decomposition supplies the combining accent; common
    # ASCII spacing forms require an explicit equivalent.
    author_chars = [c for e in aruns for c in aligned[e["id"]] if not c.get("space")]
    removed = set()
    for c in author_chars:
        accent = accent_mark(c["t"])
        if not accent: continue
        targets = []
        for letter in author_chars:
            if letter is c or not letter["t"].isalpha(): continue
            a, b = c["box"], letter["box"]
            overlap = accent_overlap(c, letter)
            if overlap > 0:
                targets.append((overlap, -abs((a[0] + a[2]) - (b[0] + b[2])), letter))
        if not targets: continue
        letter = max(targets, key=lambda t: t[:2])[2]
        before = letter["t"]
        # Typesetters use dotless i as the base of an accented i; Unicode's
        # composed accented letters use ordinary i as their decomposition base.
        base = "i" if before == "ı" and any(unicodedata.combining(t) == 230 for t in accent) else before
        letter["t"] = unicodedata.normalize("NFC", base + accent); letter["joined_accent"] = True
        joins.append({"kind": "accent", "text": c["t"], "before": before, "after": letter["t"],
                      "source_run": c.get("run"), "target_run": letter.get("run"),
                      "char_ids": [c.get("char_id")], "target_char_id": letter.get("char_id"), "box_px": c["box"]})
        removed.add(id(c))
    for e in aruns:
        cs = []
        for c in aligned[e["id"]]:
            if id(c) in removed: continue
            prev = cs[-1] if cs else {}
            # The spacing accent may have hidden the gap to the next word.
            # Recheck that gap using the composed letter's ink box.
            if (prev.get("joined_accent") and not c.get("space") and
                c["box"][0] - prev["box"][2] > PARAMS["wordspace_min_em"] * max(c["size"], prev["size"])):
                cs.append({"t": " ", "space": True})
            cs.append(c)
        aligned[e["id"]] = cs
    # icons standing on the author lines (ORCID): drawn objects about one letter height square
    icons = []
    for e in p["elements"]:
        if e["kind"] not in ("image", "outline"): continue
        x0, y0, x1, y1 = e["box_px"]
        if not (0.5 * s0 <= x1 - x0 <= PARAMS["icon_max_em"] * s0 and 0.5 * s0 <= y1 - y0 <= PARAMS["icon_max_em"] * s0): continue
        for li in alines:
            ly0 = min(r["box_px"][1] for r in by_line[li]); ly1 = max(r["box_px"][3] for r in by_line[li])
            if min(y1, ly1) - max(y0, ly0) >= 0.5 * (y1 - y0):
                hit = next((ic for ic in icons if min(ic["box"][2], x1) - max(ic["box"][0], x0) > 0 and min(ic["box"][3], y1) - max(ic["box"][1], y0) > 0), None)
                if hit: hit["box"] = [min(hit["box"][0], x0), min(hit["box"][1], y0), max(hit["box"][2], x1), max(hit["box"][3], y1)]
                else: icons.append({"box": [x0, y0, x1, y1], "line": li})
                break
    def on_icon(c): return any(ic["box"][0] - 1 <= (c["box"][0] + c["box"][2]) / 2 <= ic["box"][2] + 1 and ic["box"][1] - 1 <= (c["box"][1] + c["box"][3]) / 2 <= ic["box"][3] + 1 for ic in icons)
    # the token stream over the author lines, left to right, line by line, icons in their places
    # A byline with no printed separator (names parted only by their runs, ORCID icons
    # and row ends: AL06 "Jad Majzoub [iD] Shayan ... ... Chin-Wei Wang / Sunčica
    # Travan", measured 2026-11-03) ends a complete name at the end of a row.
    separator_free = not re.search(r"[,;|&·•/]|\band\b", " ".join(e["text"] for li in alines for e in by_line[li]))
    stream = []
    for li in alines:
        items = []
        for n_run, e in enumerate(sorted(by_line[li], key=lambda e: e["box_px"][0])):
            if not any(not c.get("space") for c in aligned[e["id"]]): continue
            first = next(c for c in aligned[e["id"]] if not c.get("space"))
            prev = next((c for x, c in reversed(items) if not c.get("space")), None)
            continuation = (prev is not None and prev["t"].isalpha() and first["t"].islower() and
                            -.1 * s0 <= first["box"][0] - prev["box"][2] <= PARAMS["wordspace_min_em"] * s0)
            if items and not continuation: items.append((None, {"t": " ", "space": True, "runbreak": True}))
            for c in aligned[e["id"]]:
                if c.get("_aff_cut"): break   # affiliation text begins inside this run
                if c.get("space"): items.append((None, {"t": " ", "space": True}))
                elif not on_icon(c): items.append((c["box"][0], c))
        items += [(ic["box"][0], {"icon": ic}) for ic in icons if ic["line"] == li]
        # icons go in by x among the characters; spaces keep their places in the text
        out = []; pend = sorted([it for it in items if "icon" in it[1]], key=lambda it: it[0])
        for x, c in items:
            if "icon" in c: continue
            while pend and x is not None and pend[0][0] <= x: out.append(pend.pop(0)[1])
            out.append(c)
        out += [it[1] for it in pend]
        stream += out + [{"t": " ", "space": True, "eol": True}]
    # each name reads as a name
    def name_ok(n):
        def plain(n):
            words = n.split()
            if not (2 <= len(words) <= 8) or re.search(r"\d", n) or len(n) > 80: return False
            return all(w.lower() in PARTICLES or re.fullmatch(r"[A-ZÀ-ɏ][\wÀ-ɏ'´`¸¨\-.]*\.?|[A-Z]\.(-?[A-Z]\.)*", w) for w in words)
        # Titles set before the name ("Prof. Dr. med. dent. Name") are the name's own: the name
        # after them reads as a name (lower-case faculty qualifiers included).
        rest = prenominal_rest(n)
        return plain(n) or (rest is not None and len(n) <= 80 and plain(rest))
    authors = []; cur = {"name": "", "markers": [], "notes": [], "orcid": False, "boxes": [], "prefix_markers": False}
    degree = AUTHOR_DEGREE
    def credential(word):
        # A degree set after a comma (AM03 "Andrew S. L. Chan, MBBS; ... MBBS, PhD, FCCP",
        # measured 2026-11-03): three or more letters with at least two capitals and
        # no lowercase run longer than two letters (PhD, MSc, MBBS, FCCP, DrPH), with
        # optional periods or a parenthesised qualifier; never period-separated
        # initials (J.R.), a particle, a group word or a name-cased word.
        w = re.sub(r"\((?:[A-Za-z]{1,6})\)$", "", word).rstrip(".")
        letters = re.sub(r"[^A-Za-z]", "", w)
        return (bool(re.fullmatch(r"[A-Za-z.]+", w)) and len(letters) >= 3 and sum(ch.isupper() for ch in letters) >= 2
                and not re.search(r"[a-z]{3}", letters) and not re.fullmatch(r"(?:[A-Z]\.)+", w)
                and not GROUP_WORD.search(w))
    def degree_token(word):
        # A post-nominal token as printed: capital-led letters with optional periods, hyphens or a
        # parenthesised qualifier, and no lower-case run of three letters (PT, MPT, RN, BSN, PhD, MSc, M.S.).
        w = re.sub(r"\((?:[A-Za-z]{1,6})\)$", "", word)
        return bool(re.fullmatch(r"[A-Z][A-Za-z.\-]*", w)) and not re.search(r"[a-z]{3}", w) and not GROUP_WORD.search(w)
    def degree_suffix(name):
        # A bracketed qualifier after a degree ("FDS (RCS)", "MS (Perio)") is part of that degree.
        name = re.sub(r"\s*\([A-Za-z]{1,8}\)", "", name).strip()
        # The byline's own structure decides: an author's name has two or more words, so a one-word
        # comma part set after a complete name is that name's degree group when it reads as a
        # post-nominal token. A part of several words is a degree only when it holds a listed degree
        # and every word is one; a part set wholly in capitals then needs every word listed, since
        # a byline set in capitals prints its names that way ("IDA ODUYA" is the next author).
        words = name.split()
        if not words: return False
        if degree.fullmatch(name): return True
        if len(words) == 1:
            # A credential (ScB, MBBS) or a capitals token after an author with degrees is one wherever
            # it stands, so a name whose letters the reading layer split still keeps its degree.
            return bool(credential(name) or (authors and authors[-1].get('degrees') and
                        re.fullmatch(r'[A-Z]{2,12}', name) and not GROUP_WORD.search(name)) or
                        (authors and name_ok(authors[-1]["name"]) and degree_token(name)))
        if not all(degree.fullmatch(w) or credential(w) for w in words): return False
        listed = [w for w in words if degree.fullmatch(w)]
        return bool(listed) and (len(listed) == len(words) or bool(re.search(r"[a-z]", name)))
    def finish():
        nonlocal cur
        name = re.sub(r"\s+", " ", cur["name"]).strip(" ,;")
        # A tracked initial's period stands apart from its letter ("B . E . CAIRNS", AL03).
        name = re.sub(r"(?<![\w.])([A-Z]) \.", r"\1.", name)
        if authors and re.fullmatch(r'(?:Jr\.?|Sr\.?|II|III|IV)', name):
            authors[-1]['name'] += ' ' + name
            for key in ('markers', 'notes'): authors[-1][key].extend(cur[key])
        elif (name and degree_suffix(name) and authors and not (
                # A one-word part carrying its own marker, after an author whose markers already
                # followed the name, is the next author (a one-word surname), unless it is a listed degree.
                len(name.split()) == 1 and cur["markers"] and authors[-1]["markers"] and not degree.fullmatch(name))):
            authors[-1].setdefault("degrees", []).append(name)
            for key in ("markers", "notes"): authors[-1][key].extend(cur[key])
            authors[-1]["orcid"] |= cur["orcid"]
        elif name:
            words = name.split(); degrees = []
            for i in range(2, len(words)):
                suffix = " ".join(words[i:])
                if degree.fullmatch(suffix):
                    name = " ".join(words[:i]); degrees = [suffix]; break
            author = {"name": name, "markers": cur["markers"], "notes": cur["notes"], "orcid": cur["orcid"]}
            if degrees: author["degrees"] = degrees
            authors.append(author)
        elif cur["orcid"] and authors: authors[-1]["orcid"] = True
        cur = {"name": "", "markers": [], "notes": [], "orcid": False, "boxes": [], "prefix_markers": False}
    marker_buf = ""
    def flush_marker():
        nonlocal marker_buf
        for m in re.split(r"[,\s]+", marker_buf):
            if not m: continue
            if all(ch in NOTE_SYMBOLS or is_private(ch) for ch in m):
                # Round 6 rules A11 and A12: symbols set together after a name are one mark per symbol in the
                # usual order ("†‡" is † and ‡; "††‡‡" is †† and ‡‡); a repeated symbol is one mark ("**").
                for part in (x.group(0) for x in re.finditer(r"(.)\1*", m)):
                    cur["notes"].append("envelope" if is_private(part) else part)
            else:
                # (memo 1 M6: a sign repeated is one mark of that count, "‖‖" is not two "‖")
                for part in (x.group(0) for x in re.finditer(r"\d+|[a-z]|([^\w\s])\1*", m)):
                    if part in NOTE_SYMBOLS: cur["notes"].append(part)
                    elif is_private(part): cur["notes"].append("envelope")
                    else: cur["markers"].append(part)
        marker_buf = ""
    k = 0
    while k < len(stream):
        c = stream[k]
        if "icon" in c:
            flush_marker()
            if cur["name"].strip(): cur["orcid"] = True
            elif authors: authors[-1]["orcid"] = True
            k += 1; continue
        if c.get("runbreak"):   # a new run on the line: the name ends unless its markers follow
            j = k + 1
            while j < len(stream) and (stream[j].get("space") or "icon" in stream[j]): j += 1
            nxt = stream[j] if j < len(stream) else None
            if nxt is not None and not (nxt.get("sup") or nxt["t"].isdigit() or nxt["t"] in NOTE_SYMBOLS or is_private(nxt["t"]) or nxt["t"] in ",;|&·•"):
                flush_marker()
                if cur["name"].strip(): finish()
        if c.get("eol"):
            flush_marker()
            if cur["name"].strip() and (cur["markers"] or cur["notes"] or cur["orcid"] or one_per_row or (sidebar or separator_free) and name_ok(cur["name"].strip())): finish()
        if c.get("space"):
            # (round 6, memo 2 M6: unread signs repeated with a space between them are one mark of that count)
            nx = next((q for q in stream[k + 1:] if not q.get("space")), None)
            if marker_buf.endswith("\ufffd") and nx is not None and nx.get("t") == "\ufffd":
                k += 1; continue
            if marker_buf: flush_marker()
            cur["name"] += " " if cur["name"] and not cur["name"].endswith(" ") else ""
            k += 1; continue
        t = c["t"]
        # Round 6 rule A4: a number in brackets after a plausible name ("Name (1), Name (2)") is a
        # marker, like a raised number; the brackets are not part of the name.
        if t in "([" and name_ok(cur["name"].strip()):
            j = k + 1; digits = ""
            while j < len(stream) and not stream[j].get("space") and (stream[j].get("t", "").isdigit() or (digits and stream[j].get("t") == ",")):
                digits += stream[j]["t"]; j += 1
            if digits[:1].isdigit() and len(digits) <= 7 and j < len(stream) and stream[j].get("t") == (")" if t == "(" else "]"):
                marker_buf += digits.rstrip(","); k = j + 1; continue
        # Baseline digits are markers only after a plausible personal name. Digits
        # in a group name, DOI, citation or misidentified prose must remain text.
        baseline_marker = t.isdigit() and (marker_buf.isdigit() or name_ok(cur["name"].strip()) or
                                           (authors and degree_suffix(cur["name"].strip())))
        # (round 6, memo 1 M6: a sign the text layer cannot read, set directly after a plausible name, is a mark too)
        unread_mark = t == "\ufffd" and (marker_buf or name_ok(cur["name"].strip()))
        if c.get("sup") or baseline_marker or (t in NOTE_SYMBOLS or is_private(t)) or unread_mark:
            if not cur["name"].strip(): cur["prefix_markers"] = True
            marker_buf += t; k += 1; continue
        jd = k + 1
        while jd < len(stream) and stream[jd].get("runbreak"): jd += 1   # the i and the D of an ORCID mark may stand in two runs
        if t in "iI" and jd < len(stream) and stream[jd].get("t") == "D" and not stream[jd].get("space"):
            d = stream[jd]; prev = next((q for q in reversed(stream[:k]) if not q.get("space") and "icon" not in q and not q.get("sup")), None)
            if c["size"] < PARAMS["orcid_letter_share"] * s0 and d["size"] < PARAMS["orcid_letter_share"] * s0 and prev is not None and prev["size"] >= PARAMS["orcid_name_share"] * s0:
                flush_marker()
                if cur["name"].strip(): cur["orcid"] = True
                elif authors: authors[-1]["orcid"] = True
                k = jd + 1; continue
        if marker_buf: flush_marker()
        word = "".join(x["t"] for x in stream[k:k + 4] if not x.get("space") and "icon" not in x)
        j = k - 1
        while j >= 0 and "icon" in stream[j]: j -= 1
        # A raised marker glued to the conjunction ("Kornman a and P.J.", AL05) is a word boundary too.
        prev_space = j < 0 or stream[j].get("space") or "icon" in stream[k - 1] or bool(stream[j].get("sup"))
        if t in NAME_SEPARATORS:   # names are separated by a comma, slash, semicolon, bar, ampersand, middle dot or bullet (AM10)
            j = k + 1
            while j < len(stream) and stream[j].get("space"): j += 1
            nxt = stream[j] if j < len(stream) else {}
            if t == "/" and not (nxt.get("t", "").isupper() and
                                  (name_ok(cur["name"].strip()) or (authors and degree_suffix(cur["name"].strip())))):
                cur["name"] += t; k += 1; continue
            # A separator before a marker still belongs to the preceding name.
            if t == "," and (nxt.get("sup") or nxt.get("t", "").isdigit() or nxt.get("t") in NOTE_SYMBOLS):
                k += 1; continue
            if cur["name"].strip() or cur["markers"]: finish()
            k += 1; continue
        # The conjunction in either case ("and", or "AND" in a byline set in capitals).
        if prev_space and word[:3] in NAME_CONJUNCTIONS and (k + 3 >= len(stream) or stream[k + 3].get("space")):
            if cur["name"].strip(): finish()
            k += 3; continue
        if not cur["prefix_markers"] and (name_ok(cur["name"].strip()) or (authors and degree_suffix(cur["name"].strip()))) and (cur["markers"] or cur["notes"]): finish()
        cur["name"] += t; cur["boxes"].append(c["box"]); k += 1
    flush_marker(); finish()
    # group authors: an entry opening "On behalf of" or "for the" begins one, and every entry after it is
    # part of it ("... Workshop Participants" then "and Methodological Consultant"); an entry naming a body
    # (a Group, Committee, Consortium ...) is one on its own; neither is a person's name
    persons = []; gauthors = []; open_group = False
    for a in authors:
        if open_group: gauthors[-1]["parts"].append(a["name"]); gauthors[-1]["markers"] += a["markers"]; continue
        if GROUP_OPEN.match(a["name"]) or GROUP_WORD.search(a["name"]):
            gauthors.append({"parts": [a["name"]], "markers": list(a["markers"]), "orcid": a["orcid"]}); open_group = bool(GROUP_OPEN.match(a["name"])); continue
        persons.append(a)
    authors = persons
    for g in gauthors: g["text"] = g["parts"][0] if len(g["parts"]) == 1 else ", ".join(g["parts"][:-1]) + " and " + g["parts"][-1]
    for a in authors: a["name_ok"] = bool(name_ok(a["name"]))
    result["authors"] = authors; result["orcid_icons"] = len(icons)
    if gauthors: result["group_authors"] = gauthors   # written only when the byline has one
    # Symbols may identify an address as well as a correspondence/equal-contribution note.
    used = sorted({m for a in authors + gauthors for m in a["markers"]}, key=lambda m: (len(m), m))
    # Repeated symbols (*, **, ***) are distinct labels; a label's characters are its symbols.
    symbols = {m for a in authors for m in a["notes"] if m and all(ch in NOTE_SYMBOLS for ch in m)}
    symbol_chars = set("".join(symbols))
    # Round 6 rule A11 (A20): a mark the byline sets after a name that is neither a letter, a digit nor a note
    # symbol is an unread sign (a sign-font glyph coded as "{"); the same code opening an address row pairs
    # with it like a symbol.
    # A sign set directly before a letter label on a name ("¤a", "¤b": one mark of the form sign-and-letter) is not
    # such a mark.
    # (memo 1 M4: a dash or a punctuation mark is never such a mark)
    symbol_chars |= {ch for a in authors + gauthors for k, m in enumerate(a["markers"]) for ch in m
                     if not ch.isalnum() and not ch.isspace() and ch not in ",;.:/()[]'\"" and unicodedata.category(ch) != "Pd"
                     and not (k + 1 < len(a["markers"]) and re.fullmatch(r"[a-z]", a["markers"][k + 1]))}
    named_markers = {m for a in authors if a["name_ok"] for m in a["markers"] + a["notes"]}
    taken = title_ids | {e["id"] for li in alines for e in by_line[li]}
    affs = {}; cands = {}; note_defs = {}; note_runs = {}; unmarked_prefixes = []; symbol_rest = []; cut_rest = set(); note_forms = {}
    run_box = {e["id"]: e["box_px"] for e in runs}
    # a marker set as a run of its own: up to three letters or digits, or (round 6, memo 1 M6) up to three of the
    # signs the byline sets as marks (an unread sign in a font of its own)
    def small(e):
        t = e["text"].strip()
        return len(t) <= 3 and (t.isalnum() or (bool(t) and all(ch in symbol_chars and ch not in NOTE_SYMBOLS for ch in t)))
    block_of = {m: b["id"] for b in p["blocks"] for m in b["members"]}
    for b in p["blocks"]:   # a marker set as a block of its own: its runs join the block of the run directly right of it
        mem = [e for e in runs if e["id"] in set(b["members"])]
        if not mem or not all(small(e) for e in mem): continue
        for e in mem:
            right = [r for r in runs if r is not e and r["id"] not in taken and min(r["box_px"][3], e["box_px"][3]) - max(r["box_px"][1], e["box_px"][1]) > 0.3 * e["size_px"]
                     and 0 <= r["box_px"][0] - e["box_px"][2] <= 2 * e["size_px"]]
            if right: block_of[e["id"]] = block_of.get(min(right, key=lambda r: r["box_px"][0])["id"], block_of.get(e["id"]))
    groups = collections.defaultdict(list)
    for e in runs:
        if e["id"] in block_of and e["id"] not in taken: groups[block_of[e["id"]]].append(e)
        elif e["id"] in block_of and any(c.get("_aff_cut") for c in aligned[e["id"]]):
            # a byline run whose tail is affiliation text: the reader takes the tail only
            k = next(i for i, c in enumerate(aligned[e["id"]]) if c.get("_aff_cut"))
            groups[block_of[e["id"]]].append(dict(e, text="".join(c["t"] for c in aligned[e["id"]][k:]), _cut=k))
    abstract_top = min((e["box_px"][1] for e in p['elements'] if e['kind'] == 'text' and e["id"] not in taken and
                       re.match(r"^(?:Abstract|Summary)\b|^(?:Purpose|Objectives?|Background|Aims?)\s*:", e["text"], re.I)), default=ty1)
    author_bottom = max(e["box_px"][3] for li in alines for e in by_line[li])
    if used or symbols:
        for bid, mem in groups.items():
            b = {"id": bid}
            if not mem: continue
            ordered_mem = sorted(mem, key=lambda e: (e['box_px'][1], e['box_px'][0]))
            for i, e in enumerate(ordered_mem):
                # A reprint/correspondence request after the addresses also ends the last
                # address (AG05 "Reprint requests:"); it is article information.
                printed = "".join(c["t"] for c in aligned[e["id"]]).strip()
                if (i and (re.match(r'^(?:An?\s+)?supplement(?:al|ary)\s+(?:appendix|material|data|information)\b', e['text'], re.I) or
                           re.match(r'^(?:Reprint requests?|Requests? for reprints|Address (?:for )?correspondence|Correspondence)\s*(?:to\s*)?:', printed, re.I))
                    and any(INSTITUTION.match(re.sub(r'^[\d\s*∗†‡§¶#]+', '', r['text'])) for r in ordered_mem[:i])):
                    note = ordered_mem[i:]
                    result.setdefault('article_info', []).append(dict(page=front_page, block=bid,
                        run_ids=[r['id'] for r in note], text=' '.join(r['text'] for r in note)))
                    mem = ordered_mem[:i]
                    break
            seq = []
            ms = statistics.median(e["run_size_px"] for e in mem)
            classification = next((b for b in mt.get("blocks", []) if b["id"] == bid), {})
            leading = " ".join(e["text"] for e in sorted(mem, key=lambda e: (e["box_px"][1], e["box_px"][0])))
            if (max(e['box_px'][3] for e in mem) < ty0 and
                re.search(r'https?\s*:\s*//\s*(?:dx\.)?doi\.|\b10\.\d{4,9}/|\b(?:19|20)\d{2}\)?\s*;?\s*\d+\s*:', leading, re.I)):
                if any(re.search(r'(?<!\w)' + re.escape(m) + r'\s*(?=[A-Z])', leading) for m in used):
                    result.setdefault('article_info', []).append(dict(page=front_page, block=bid,
                        run_ids=[e['id'] for e in mem], text=leading))
                continue
            if classification.get('cls') == 'furniture': continue
            # Lane masthead (2026-11-04): directly below the byline, a block whose first row
            # opens with a raised label the byline uses is an address band too, whatever
            # word follows (AP10 "1Sleep Unit, ...": its first word names no institution).
            first_run = min(mem, key=lambda e: (e["box_px"][1], e["box_px"][0]))
            opening = ""
            for c in aligned[first_run["id"]][first_run.get("_cut", 0):]:
                if c.get("space") or not c.get("sup") or not c["t"].isalnum(): break
                opening += c["t"]
            address_band = (0 <= min(e["box_px"][1] for e in mem) - author_bottom <= AUTHOR_GAP_EM * ms and
                            (INSTITUTION.match(re.sub(r"^[\d\s*∗†‡§¶#]+", "", leading)) or (bool(opening) and opening in set(used))))
            body_column = (classification.get("cls") == "main" and ms >= .95 * mt.get("body_size_px", ms) and
                           min(e["box_px"][1] for e in mem) >= abstract_top and not address_band)
            # Lane r2-frontfusion: a block set at heading size (heading_size_ratio of the page's body size or
            # more) below the byline's address band is a body heading; its number is a section number, never
            # an address marker (mimic-g: '2 Study Area and Aims ...' taken as affiliation 2).
            heading_size = bool(mt.get("body_size_px")) and ms >= PARAMS["heading_size_ratio"] * mt["body_size_px"] and not address_band
            for e in sorted(mem, key=lambda e: (round(e["box_px"][3] / (0.6 * ms)), e["box_px"][0])):
                seq += [dict(c, run=e["id"], small_run=small(e)) for c in aligned[e["id"]][e.get("_cut", 0):]] + [{"t": " ", "space": True}]
            text = ""; marks = []; at = []   # the text, the markers by position, each position's box
            at_run = []; mark_runs = {}   # each position's run, each marker's own runs (a note claims both)
            k = 0
            while k < len(seq):
                c = seq[k]
                if c.get("space"): text += " "; at.append(None); at_run.append(None); k += 1; continue
                boundary = k == 0 or seq[k - 1].get("space") or seq[k - 1].get("t") in ",;"
                # A byline letter marker can open an address row at full size, in the
                # byline's face against the address's italic face, or raised above the
                # address baseline (AL09 "a Department of Oral Rehabilitation", measured
                # 2026-11-03): one lowercase letter before a space or capital, opening its run.
                following = next((q for q in seq[k + 1:] if not q.get("space")), None)
                letter_marker = (c["t"].isalpha() and c["t"].islower() and c["t"] in set(used) and following is not None
                                 and (seq[k + 1].get("space") or following["t"].isupper() or
                                      bool(NUMBER_LED.match("".join(q["t"] for q in seq[k + 1:k + 25]).lstrip())))
                                 and not any(q.get("run") == c.get("run") and not q.get("space") for q in seq[:k])
                                 and (c.get("font") != following.get("font") or c["box"][3] < following["box"][3] - RAISE_EM * c["size"]))
                strong = c.get("sup") or c.get("small_run") or c["t"] in symbol_chars or letter_marker
                if boundary and (strong or c["t"].isdigit()):
                    j = k; m = ""
                    while j < len(seq) and not seq[j].get("space"):
                        q = seq[j]
                        if strong:
                            # The baseline digit in a digit-leading name is not part of
                            # its raised label (e.g. a numbered centre).
                            if not (q.get("sup") or q.get("small_run") or q["t"] in symbol_chars or (j == k and letter_marker)): break
                        elif not q["t"].isdigit(): break
                        if not (q["t"].isalnum() or q["t"] in symbol_chars): break
                        m += q["t"]; j += 1
                    nxt = j
                    while nxt < len(seq) and seq[nxt].get("space"): nxt += 1
                    after = "".join(q["t"] for q in seq[nxt:] if q.get("run") == c.get("run") or q.get("space"))
                    at_start = not any(q.get("run") == c.get("run") and not q.get("space") for q in seq[:k])
                    distinct_font = nxt < len(seq) and c.get("font") and c["font"] != seq[nxt].get("font")
                    # An address opens with a word, with an opening bracket or quote before one, or with
                    # a number-led institution phrase (an ordinal "4th Division", "2nd Department", also
                    # with the reading layer's space inside it, "1 st"; or a number before a capitalised
                    # word "3 Hospitals"), after a digit, letter or symbol label: a raised number followed by a
                    # period, comma or closing bracket ("...inflammation)1,2. The ...") is a citation,
                    # never an address label.
                    opening = "".join(q["t"] for q in seq[nxt:nxt + 24])
                    plausible = nxt < len(seq) and (seq[nxt]["t"][:1].isalpha() or seq[nxt]["t"][:1] in "([“‘\"'" or
                                                    bool(NUMBER_LED.match(opening))) and (
                                (strong and (seq[nxt]["t"].isupper() or m in named_markers)) or
                                (seq[nxt]["t"].isupper() and (j == nxt or at_start or distinct_font)))
                    # A compound label set ("1,2Department", "a,b University", "1-3 Institute"): raised
                    # labels joined by commas or a hyphen before one address name all of them.
                    if m and strong and nxt < len(seq) and seq[nxt]["t"] in ",-–" and not plausible:
                        tail = "".join(q["t"] for q in seq[nxt:nxt + 40])
                        cm = re.match(r"(?:\s*[,\-–]\s*(?:\d+|[a-z]|[*∗†‡§¶#]+))+\s*", tail)
                        rest = tail[cm.end():] if cm else ""
                        part = seq[nxt:nxt + cm.end()] if cm else []
                        if (cm and (rest[:1].isupper() or bool(NUMBER_LED.match(rest))) and
                                all(q.get("space") or q["t"] in ",-–" or q.get("sup") or q.get("small_run") or q["t"] in symbol_chars for q in part)):
                            labels = [m]; prev_sep = None
                            for sep, lab in re.findall(r"([,\-–])\s*(\d+|[a-z]|[*∗†‡§¶#]+)", cm.group(0)):
                                if sep != "," and labels[-1].isdigit() and lab.isdigit() and int(labels[-1]) < int(lab) <= int(labels[-1]) + 20:
                                    labels += [str(x) for x in range(int(labels[-1]) + 1, int(lab) + 1)]
                                else: labels.append(lab)
                            if all(x in set(used) | symbols for x in labels):
                                for x in labels:
                                    mark_runs[(len(text), x)] = [q.get("run") for q in seq[k:nxt + cm.end()] if q.get("run")]
                                    marks.append((len(text), x))
                                k = nxt + cm.end(); continue
                    if m and m in set(used) | symbols and nxt < len(seq) and plausible and not MONTH.match(after):
                        mark_runs[(len(text), m)] = [q.get("run") for q in seq[k:j] if q.get("run")]
                        marks.append((len(text), m)); k = nxt; continue
                text += c["t"]; at.append(c["box"]); at_run.append(c.get("run")); k += 1
            # The institution-led prefix on the same address rows is the
            # unmarked first affiliation. Do not discard it at the first label.
            prefix = re.sub(r"\s+", " ", text[:marks[0][0]]).strip(" ,;") if marks else ""
            if prefix and INSTITUTION.match(prefix) and any(not a["markers"] for a in authors):
                marks.insert(0, (0, "0"))
            if not body_column and not marks and INSTITUTION.match(text.strip()) and any(not a["markers"] for a in authors):
                bx = [c for c in at if c]
                if bx:
                    unmarked_prefixes.append(({"marker": "0", "text": re.sub(r"\s+", " ", text).strip(" ,;"),
                                               "block": bid, "institution_word": True,
                                               "box_px": [min(q[0] for q in bx), min(q[1] for q in bx), max(q[2] for q in bx), max(q[3] for q in bx)]}, ms))
            # Round 6 rule A16, a gap (memo 1): a step between printed rows clearly wider than the block's usual one
            # (its median row gap plus a third of the type size); rows set at an even pitch never part
            order = [r for r in dict.fromkeys(x for x in at_run if x) if r in run_box]
            steps = sorted(g for g in (run_box[b][1] - run_box[a][3] for a, b in zip(order, order[1:])) if g > 0)
            gap_limit = (steps[(len(steps) - 1) // 2] if steps else 0) + .35 * ms
            for i, (pos, m) in enumerate(marks):
                # labels of one compound set share one position and one address
                end = next((q for q, _ in marks[i + 1:] if q > pos), len(text))
                disclosure = re.search(r"\bConflict of Interest Disclosures\b", text[pos:end], re.I)
                if disclosure: end = pos + disclosure.start()
                # A correspondence note or the pointer to the full author list under a
                # note is not part of it (a "*Correspondence:" row whose star the byline
                # does not use, measured on a mimic page, out-front9/mimic).
                # Round 6 rule A16: also at "Address all correspondence ..." and a reprint request.
                following = AFFILIATION_END_NOTE.search(text[pos:end])
                if following and following.start() > 0: end = pos + following.start()
                # Round 6 rule A16: the affiliation ends at a printed run that opens with a section label
                # ("Abstract", "SUMMARY", "Key words") or that stands a blank line (one type size) below the
                # run before it: abstract text under the addresses is never part of the last one.
                # (memo 1: the gap is measured between the printed rows' run boxes, never between glyph boxes: a
                # line-end hyphen or dash has a glyph box far above its row's foot)
                prev_run = None
                for q in range(pos, end):
                    r = at_run[q]
                    if r is None or at[q] is None: continue
                    if prev_run is not None and r != prev_run and q > pos and r in run_box and prev_run in run_box and (
                            AFFILIATION_END_LABEL.match(text, q) or run_box[r][1] - run_box[prev_run][3] > gap_limit):
                        # the runs left out are recorded: the copy keeps them printed (rule C3, never dropped)
                        cut_rest.update(x for x in at_run[q:end] if x and x not in set(at_run[pos:q]) | set(at_run[end:]))
                        end = q; break
                    prev_run = r
                body = re.sub(r"\s+", " ", text[pos:end]).strip(" ,;")
                # The conjunction before the next marked address is not part of this one (AL05 "..., USA, and bDepartment").
                if i + 1 < len(marks): body = re.sub(r"[,;\s]+and$", "", body)
                if re.match(r"^(?:(?:These|The|Both|All)\b[^.!?]*\bauthors?\b[^.!?]*\bcontribute[ds]? equally|(?:denotes?\s+)?equal contribution|(?:Corporate|Joint|Co[- ]?)\s*first authors)\b", body, re.I) or (
                        # an equal-contribution statement in any wording (AL09 "Aranka Ilea and
                        # Anida-Maria Băbţan have equal contributions as first authors"), or a
                        # current/present address note, is a note, never an affiliation
                        re.match(r"^[^.!?]*\b(?:contribute[ds]?\s+equally|equal(?:ly)?\s+contribut\w+)\b", body, re.I) or
                        re.match(r"^(?:Current|Present|Permanent|New)\s+address\s*:", body, re.I)):
                    if m not in note_defs:
                        # The note's printed runs: its marker's (a symbol set on a row of its own
                        # included) and every run its text was read from, in reading order.
                        note_defs[m] = body
                        note_runs[m] = list(dict.fromkeys(r for r in mark_runs.get((pos, m), []) + at_run[pos:end] if r))
                    continue
                if m in symbols and (AUTHOR_NOTE_OPEN.match(body) or SUPPORT_OPEN.match(body)):
                    # Round 6 rule A19: after a byline symbol, a line opening with author-note words (correspondence,
                    # present address, deceased, a contribution or support statement) is that mark's author note,
                    # never its affiliation; recorded apart (the copy prints such lines where it did before)
                    note_forms.setdefault(m, body)
                    continue
                # A symbol label is an address when its text opens with an institution, or when it
                # continues a list of addresses: the address before it in the same text ends with
                # "and" or a semicolon ("..., Malmö and †The ... Council, Stockholm, Sweden").
                # The continued address opens with a capital; a lower-case note ("corresponding
                # author, ...") or a correspondence line is not an address.
                continues = (i > 0 and bool(re.search(r"(?:\band|;)\s*$", text[:pos])) and body[:1].isupper()
                             and not re.match(r"correspond", body, re.I))
                # A number-led institution phrase ("1st Faculty of ...", "2nd Department of ...") opens
                # an institution too.
                lead_body = re.sub(r"^\d+\s?(?:st|nd|rd|th)?\s+", "", body) if NUMBER_LED.match(body) else body
                bx = [q for q in at[pos:end] if q]
                # Round 6 rules A10 and A11: a symbol address may name its institution anywhere in the row.
                if m in symbols and not (INSTITUTION.match(lead_body) or address_open.match(body) or continues or symbol_address(lead_body)):
                    if bx: symbol_rest.append((m, body, b["id"], body_column or heading_size,
                                               [min(q[0] for q in bx), min(q[1] for q in bx), max(q[2] for q in bx), max(q[3] for q in bx)]))
                    continue
                cands.setdefault(m, []).append({"marker": m, "text": body, "block": b["id"], "institution_word": bool(INSTITUTION.match(body)), "_body_column": body_column or heading_size,
                                                "box_px": [min(q[0] for q in bx), min(q[1] for q in bx), max(q[2] for q in bx), max(q[3] for q in bx)] if bx else None})
        # Round 6 rule A11 (the mark pairs): a byline symbol with no address yet pairs with the text after the
        # same symbol inside a block that already holds another mark's address (the address band or the
        # footnote of addresses), when that text is no author note, no support statement and no e-mail row,
        # and opens with a capital ("**Royal Brompton and Harefield NHS Trust" between two addresses).
        address_blocks = {c["block"] for cs in cands.values() for c in cs if not c["_body_column"]}
        for m, body, bid, column, box in symbol_rest:
            if (m in cands or column or bid not in address_blocks or not body[:1].isupper() or len(body.split()) < 2
                    or AUTHOR_NOTE_OPEN.match(body) or SUPPORT_OPEN.match(body) or E_MAIL.search(body)): continue
            cands[m] = [{"marker": m, "text": body, "block": bid, "institution_word": False, "_body_column": False, "box_px": box}]
        for m, cs in cands.items():   # one per marker: the first whose text opens with an institution word, else the first
            # Keep the existing ambiguity diagnostic for all texts following a code,
            # but a body-column citation is never eligible to supply its address.
            eligible = [c for c in cs if not c.pop("_body_column")]
            if not eligible: continue
            affs[m] = next((c for c in eligible if c["institution_word"]), eligible[0])
            if len(cs) > 1: flags.append(f"marker {m}: {len(cs)} texts follow it on the page; kept the one in block {affs[m]['block']}")
        # A block boundary must not erase the same unmarked prefix. It has to
        # sit after the byline and immediately before the first marked address,
        # either to its left on that row or stacked above it in the same column.
        if affs and "0" not in affs:
            first = min((a["box_px"] for a in affs.values() if a["box_px"]), key=lambda b: (b[1], b[0]), default=None)
            bottom = max(e["box_px"][3] for li in alines for e in by_line[li])
            for candidate, size in unmarked_prefixes:
                bx = candidate["box_px"]
                if first is None or bx[1] < bottom - 1: continue
                beside = abs(first[1] - bx[1]) <= .5 * size and 0 <= first[0] - bx[2] <= 2 * size
                above = (-.5 * size <= first[1] - bx[3] <= AUTHOR_STACK_EM * size and
                         min(first[2], bx[2]) - max(first[0], bx[0]) >= .5 * min(first[2] - first[0], bx[2] - bx[0]))
                if beside or above: affs["0"] = candidate; break
    else:
        cands = [b for b in p["blocks"] if not (set(b["members"]) & taken)]
        for b in cands:
            t = " ".join("".join(c["t"] for c in aligned[e["id"]]) for e in sorted([e for e in runs if e["id"] in set(b["members"])], key=lambda e: (e["box_px"][3], e["box_px"][0])))
            # A note symbol can lead the address when the title carries it (AL07
            # "Long-Term Results*" over "* University of Ege, School of Dentistry, ...").
            if INSTITUTION.match(re.sub(r"^[*∗⁎†‡§¶#\s]+", "", t.strip())): result["unmarked_affiliation_candidates"] = result.get("unmarked_affiliation_candidates", []) + [{"block": b["id"], "text": t.strip()[:200], "box_px": b["box_px"]}]
    inner_fields = [li for li in field_rows if alines and not form_rows and
                    min(e["box_px"][1] for e in by_line[li]) < min(e["box_px"][1] for e in by_line[alines[-1]])]
    if inner_fields and not affs:
        # A field row passed over between two name rows of a form title page ("Designation: Senior
        # Lecturer, Department of ...") is the role and affiliation line of the author above it: an
        # unmarked affiliation, its row as printed, label included. On such a page the field rows
        # under the last name row are that author's fields in the same way.
        rows = []
        for li in field_rows:
            lines = {e["line"] for e in by_line[li]}
            row = sorted((e for e in runs if e["line"] in lines and e["id"] not in taken), key=lambda e: e["box_px"][0])
            if not row: continue
            rows.append({"block": block_of.get(row[0]["id"]), "text": " ".join(e["text"].strip() for e in row),
                         "box_px": [min(e["box_px"][0] for e in row), min(e["box_px"][1] for e in row),
                                    max(e["box_px"][2] for e in row), max(e["box_px"][3] for e in row)],
                         "run_ids": [e["id"] for e in row]})
        if rows: result["unmarked_affiliation_candidates"] = rows
    if field_rows and not form_rows and not result.get("unmarked_affiliation_candidates"):
        # Field rows passed over under an ordinary byline ("Corresponding author: ...") are article
        # information, printed as such; never names, never dropped.
        held = {m for source in result.get("article_info", []) for m in source.get("run_ids", [])}
        for li in field_rows:
            lines = {e["line"] for e in by_line[li]}
            row = sorted((e for e in runs if e["line"] in lines and e["id"] not in taken and e["id"] not in held), key=lambda e: e["box_px"][0])
            if row:
                result.setdefault("article_info", []).append(dict(page=front_page, block=block_of.get(row[0]["id"]),
                    run_ids=[e["id"] for e in row], text=" ".join(e["text"].strip() for e in row), role="field row under the byline"))
    if form_rows and not used:
        # On a cover sheet the affiliations are the values of its institution fields
        # ("Corresponding Author's Institution: ..."), each distinct value once.
        insts = []
        for e in sorted(runs, key=lambda e: (e["box_px"][1], e["box_px"][0])):
            if e["box_px"][1] < ty1 - 1 or e["id"] in taken: continue
            m = INSTITUTION_FIELD.match(e["text"].strip())
            if not m: continue
            value = [(r, cs) for r, cs in field_value(e, m) if r["id"] not in taken and any(not c.get("space") for c in cs)]
            text = re.sub(r"\s+", " ", " ".join("".join(c["t"] for c in cs) for _, cs in value)).strip()
            if not text or any(text == c["text"] for c in insts): continue
            insts.append({"block": block_of.get(value[0][0]["id"]), "text": text, "box_px": [min(r["box_px"][0] for r, _ in value), min(r["box_px"][1] for r, _ in value),
                                                                    max(r["box_px"][2] for r, _ in value), max(r["box_px"][3] for r, _ in value)],
                          "run_ids": [r["id"] for r, _ in value]})
        # Nothing else on the sheet is an address: with no institution value there is no affiliation.
        if insts: result["unmarked_affiliation_candidates"] = insts
        else: result.pop("unmarked_affiliation_candidates", None)
    # Affiliations printed after the first page: under an explicit author-information
    # label anywhere in the paper (AM10 "Authors and Affiliations" on the last page), or,
    # for markers the first page leaves unresolved, marked small-type rows on the next
    # page (AL02 affiliations 25 and 26 in a side column of page 2, measured 2026-11-03).
    first_chars = chars
    def panel_addresses(later, members, names):
        """Marked addresses among a later page's runs: (addresses by marker, rows read).

        Rows are rule-1 lines within a block, top to bottom. A marker is a raised
        digit/letter group opening a row, or a run of its own of at most three
        characters, under 0.8 of the panel's type size, standing directly left of
        the row. A row holding an e-mail address, opening with a note symbol or a
        byline name, or opening a correspondence note is not an address and ends
        an open one; so does a row gap wider than author_stack_em. An address is
        its marked row and the rows stacked under it in the same block.
        """
        nonlocal chars
        texts = [e for e in members if len(e["text"].strip()) > 3]
        if not texts: return {}, []
        size = statistics.median(e["run_size_px"] for e in texts)
        marker_runs = [e for e in members if small(e) and e["run_size_px"] < PARAMS["superscript_em"] * size]
        block_of_later = {m: b["id"] for b in later["blocks"] for m in b["members"]}
        chars = pdfium_characters(pdf_path, later["page"])
        addresses = {}; rows_read = []
        by_block = collections.defaultdict(list)
        for e in texts: by_block[block_of_later.get(e["id"], e["id"])].append(e)
        for bid in sorted(by_block, key=lambda b: (min(e["box_px"][1] for e in by_block[b]), min(e["box_px"][0] for e in by_block[b]))):
            lines = collections.defaultdict(list)
            for e in by_block[bid]: lines[e["line"]].append(e)
            current = None; bottom = None
            for li in sorted(lines, key=lambda li: min(e["box_px"][1] for e in lines[li])):
                row = sorted(lines[li], key=lambda e: e["box_px"][0])
                top = min(e["box_px"][1] for e in row); rb = max(e["box_px"][3] for e in row)
                seq = []; valid = True
                for e in row:
                    cs = run_chars(e)
                    if cs is None: valid = False; break
                    seq += mark_raised(e, cs, {}, own_size=True) + [dict(t=" ", space=True)]
                if not valid: current = None; continue
                # Segments: a raised digit/letter group at the row start or after a space
                # opens a marked segment; a raised letter opening a word is no marker.
                segments = []; marker = ""; text = ""; k = 0
                while k < len(seq):
                    c = seq[k]
                    if (c.get("sup") and c["t"].isalnum() and (k == 0 or seq[k - 1].get("space"))):
                        m = ""; j = k
                        while j < len(seq) and seq[j].get("sup") and seq[j]["t"].isalnum(): m += seq[j]["t"]; j += 1
                        glued_word = j < len(seq) and not seq[j].get("space") and seq[j]["t"].isalnum() and m.isalpha()
                        if not glued_word:
                            if text.strip() or marker: segments.append((marker, text))
                            marker = m; text = ""; k = j; continue
                    text += c["t"]; k += 1
                segments.append((marker, text))
                marker_run = None
                if not segments[0][0]:
                    left = row[0]["box_px"]
                    beside = [m for m in marker_runs if m["text"].strip() and 0 <= left[0] - m["box_px"][2] <= 2 * size
                              and min(m["box_px"][3], left[3]) - max(m["box_px"][1], left[1]) > 0]
                    if len(beside) == 1: marker_run = beside[0]; segments[0] = (marker_run["text"].strip(), segments[0][1])
                for marker, text in segments:
                    text = re.sub(r"\s+", " ", text).strip()
                    bad = (re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\bE[-‐]?mail\b", text, re.I) or
                           (text[:1] in NOTE_SYMBOLS or is_private(text[:1])) or
                           re.match(r"^(?:Correspond(?:ence|ing author)|Address(?:es)? for correspondence|Present address)\b", text, re.I) or
                           any(re.sub(r"\W+", "", text).casefold().startswith(n) for n in names))
                    if marker and not bad:
                        addresses[marker] = dict(marker=marker, text=text, block=bid, page=later["page"],
                                                 institution_word=bool(INSTITUTION.match(text)), _runs=[e["id"] for e in row] + ([marker_run["id"]] if marker_run else []))
                        current = marker; bottom = rb; rows_read.append(row)
                    elif current and not bad and text and bottom is not None and top - bottom <= AUTHOR_STACK_EM * size:
                        # A row ending in a slash or hyphen continues its word on the next row ("Witten/" "Herdecke").
                        joint = "" if addresses[current]["text"].endswith(("/", "-", "‐")) else " "
                        addresses[current]["text"] += joint + text; addresses[current]["_runs"] += [e["id"] for e in row]; bottom = rb; rows_read.append(row)
                    else: current = None
        chars = first_chars
        return addresses, rows_read
    byline_names = [re.sub(r"\W+", "", a["name"]).casefold() for a in authors if a.get("name") and len(a["name"].split()) >= 2]
    label_re = re.compile(r"Authors?(?:['’]s?)?\s+(?:and\s+)?(?:details|affiliations?|information)\s*:?", re.I)
    if used and set(used) - set(affs):
        for path in paths:
            if path == front_path: continue
            later = read_json(path)
            upright = [e for e in later["elements"] if e["kind"] == "text" and not e.get("angle") and not e.get("furniture_reason")]
            for label in sorted((e for e in upright if label_re.fullmatch(e["text"].strip())), key=lambda e: e["box_px"][1]):
                # The panel: the runs stacked below the label down to a gap of three label heights
                # or a larger heading; its addresses must account for every byline marker.
                # On a page of several columns, a run lying wholly in another column than the
                # label's, set in the body size or larger and in another size than the panel read
                # so far (the label's while none is read), is that column's body text (beside the
                # PL44 "Author details" panel): it is passed over, neither a member nor a heading
                # that ends the panel. A panel continued in the next column in its own smaller
                # type is still read (AM10).
                lx = (label["box_px"][0] + label["box_px"][2]) / 2
                cols = (later.get("main_text") or {}).get("columns") or []
                later_body = (later.get("main_text") or {}).get("body_size_px") or 0
                col = next((c for c in cols if c[0] - label["run_size_px"] <= lx <= c[1] + label["run_size_px"]), None) if len(cols) > 1 else None
                members = []; bottom = label["box_px"][3]
                for e in sorted((e for e in upright if e is not label and e["box_px"][1] >= label["box_px"][3] - 1), key=lambda e: (e["box_px"][1], e["box_px"][0])):
                    ref = statistics.median(m["run_size_px"] for m in members) if members else label["run_size_px"]
                    if (col and (e["box_px"][2] <= col[0] or e["box_px"][0] >= col[1])
                            and e["run_size_px"] >= (1 - SIZE_TOL) * (later_body or e["run_size_px"] + 1)
                            and abs(e["run_size_px"] - ref) > SIZE_TOL * ref): continue
                    if e["box_px"][1] - bottom > 3 * label["run_size_px"]: break
                    # A dated publication record under the panel (PL44 "Received: ... / Accepted: ...")
                    # is article history, not author information: it ends the panel.
                    if re.match(r"^(?:Received|Accepted|Revised|Published(?: online)?)\s*:|^(?:Publisher[’']?s?\s+Note|Copyright)\b|^©", e["text"].strip(), re.I): break
                    if e["run_size_px"] >= 1.3 * label["run_size_px"] and len(e["text"].split()) >= 2: break
                    members.append(e); bottom = max(bottom, e["box_px"][3])
                if not members: continue
                addresses, rows_read = panel_addresses(later, members, byline_names)
                # (round 6 rule A14: a panel address may be a place alone, "City, Country")
                if set(addresses) != set(used) or any(len(a["text"].split()) < 3 and not re.fullmatch(r"[A-Z][\w’'.-]+,\s+[A-Z][\w’'.-]+\.?", a["text"])
                                                      for a in addresses.values()): continue
                run_ids = [label["id"]] + [e["id"] for e in members]
                for a in addresses.values(): a.pop("_runs", None)
                affs.update(addresses)
                result["affiliation_sources"] = [dict(page=later["page"], block=block_of_page(later, label["id"]), run_ids=run_ids, label=label["text"].strip())]
                break
            if result.get("affiliation_sources"): break
    if used and set(used) - set(affs) and not result.get("affiliation_sources"):
        # Unlabelled continuation on the page after the front page: rows marked with
        # exactly the missing markers, in a block that is not body prose, each holding
        # an institution word (AL02). Any other marker there, or a missing one, refuses it.
        missing = set(used) - set(affs)
        index = paths.index(front_path) + 1
        if index < len(paths):
            later = read_json(paths[index])
            classes_later = {m: b["cls"] for b in (later.get("main_text") or {}).get("blocks", []) for b0 in later["blocks"] if b0["id"] == b["id"] for m in b0["members"]}
            upright = [e for e in later["elements"] if e["kind"] == "text" and not e.get("angle") and not e.get("furniture_reason")]
            candidates = [e for e in upright if classes_later.get(e["id"]) != "main" or e["run_size_px"] < .95 * (mt.get("body_size_px") or e["run_size_px"])]
            addresses, rows_read = panel_addresses(later, candidates, byline_names)
            found = {m: a for m, a in addresses.items() if m in missing}
            institution = re.compile(r"\b(?:Universit|Institut|Department|Dept|School|Faculty|Hospital|Centre|Center|College|Clinic|Laborator|Division|Academy|Practice)", re.I)
            if (found and set(found) == missing and all(len(a["text"].split()) >= 3 and institution.search(a["text"]) for a in found.values())
                    and not any(m.isdigit() and m not in used for m in addresses)):
                run_ids = [m for a in found.values() for m in a["_runs"]]
                for a in found.values(): a.pop("_runs", None)
                affs.update(found)
                result["affiliation_sources"] = [dict(page=later["page"], block=next(iter(found.values()))["block"], run_ids=run_ids, continuation=True)]
    for a in authors:
        for m in list(a["markers"]):
            if m in note_defs and m not in affs: a["markers"].remove(m); a["notes"].append(m)
        for m in list(a["notes"]):
            if m in affs: a["markers"].append(m); a["notes"].remove(m)
    used = sorted({m for a in authors + gauthors for m in a["markers"]}, key=lambda m: (len(m), m))
    # Round 6 rule A12: the affiliations run in mark order: 1, 2, 3 or a, b, c, and note symbols in their usual order
    # (* † ‡ § ‖ ¶ #, then doubled), not in character-code order.
    symbol_rank = {ch: 0x2020 + k for k, ch in enumerate("†‡§‖¶#")}
    result["affiliations"] = [affs[m] for m in sorted(affs, key=lambda m: (len(m), symbol_rank.get(m[:1], ord(m[:1]) if m else 0), m))]
    if marker_glyphs:
        result["affiliations"].sort(key=lambda a: (a["box_px"][1], a["box_px"][0]))
    def hull(bs):
        bs = [b for b in bs if b]
        return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)] if bs else None
    result["author_box_px"] = hull([e["box_px"] for li in alines for e in by_line[li]])
    result["affiliation_box_px"] = hull([a.get("box_px") for a in result["affiliations"] if a.get('page', front_page) == front_page] or [c["box_px"] for c in result.get("unmarked_affiliation_candidates", [])])
    if by_introducer is not None and not used:
        # A by-introduced personal panel can give a professional membership
        # and city rather than an institution. Its same-size, aligned stack
        # is the address evidence; neighbouring abstract/prose columns stay out.
        ab = result['author_box_px']; size = s0
        tail = sorted((e for e in runs if e['id'] not in taken and
            e['box_px'][1] >= ab[3]-1 and abs(e['box_px'][0]-ab[0]) <= .5*size),
            key=lambda e: (e['box_px'][1], e['box_px'][0]))
        address = []; bottom = ab[3]
        for e in tail:
            if (e['box_px'][1]-bottom > AUTHOR_STACK_EM*size or
                abs(e['run_size_px']-size) > SIZE_TOL*size or
                re.match(r'^(?:Abstract|Summary|Introduction|Key\s*words)\b', e['text'], re.I)): break
            address.append(e); bottom = e['box_px'][3]
        if address:
            result['unmarked_affiliation_candidates'] = [dict(block=block_of.get(address[0]['id']),
                text=' '.join(e['text'] for e in address), box_px=hull([e['box_px'] for e in address]),
                run_ids=[e['id'] for e in address])]
            result['affiliation_box_px'] = result['unmarked_affiliation_candidates'][0]['box_px']
    if row_addresses and not used:
        # The affiliation cut from the byline row (AL03): that run and the rows stacked
        # under it in the same size, within the byline's column, down to an abstract,
        # summary, key-word or correspondence opening.
        band = sorted(row_addresses, key=lambda e: (e["box_px"][1], e["box_px"][0]))
        size = band[0]["run_size_px"]; bottom = max(e["box_px"][3] for e in band); band_ids = {e["id"] for e in band}
        for e in sorted((e for e in runs if e["id"] not in taken and e["id"] not in band_ids and in_column(e) and e["box_px"][1] >= bottom - 1),
                        key=lambda e: (e["box_px"][1], e["box_px"][0])):
            if (e["box_px"][1] - bottom > AUTHOR_STACK_EM * size or abs(e["run_size_px"] - size) > SIZE_TOL * size or
                    re.match(r"^(?:Abstract|Summary|Introduction|Key\s*words|Correspondence)\b", e["text"], re.I)): break
            band.append(e); bottom = max(bottom, e["box_px"][3])
        result["unmarked_affiliation_candidates"] = [dict(block=block_of.get(band[0]["id"]), text=" ".join(e["text"].strip() for e in band),
                                                        box_px=hull([e["box_px"] for e in band]), run_ids=[e["id"] for e in band])]
        result["affiliation_box_px"] = result["unmarked_affiliation_candidates"][0]["box_px"]
    if not used and not result.get("unmarked_affiliation_candidates") and not form_rows:
        # An affiliation footnote opening "From the ..." (AM03, where the title's
        # star points to it) is an unmarked address: its first sentence.
        for b in p["blocks"]:
            mem = sorted((e for e in runs if e["id"] in set(b["members"]) and e["id"] not in taken), key=lambda e: (e["box_px"][1], e["box_px"][0]))
            if not mem or len(mem) != len(b["members"]): continue
            t = " ".join(e["text"].strip() for e in mem)
            if not (FROM_THE.match(t) and INSTITUTION.match(FROM_THE.sub("", t, count=1))): continue
            sentence = re.split(r"(?<=[a-z]{3}\.)\s+(?=[A-Z])", t)[0]
            result["unmarked_affiliation_candidates"] = [dict(block=b["id"], text=sentence, box_px=b["box_px"])]
            result["affiliation_box_px"] = b["box_px"]
            break
    if not used and not result.get("unmarked_affiliation_candidates") and not form_rows:
        ab = result["author_box_px"]
        tail = sorted([e for e in runs if e["id"] not in taken and in_column(e) and e["box_px"][1] >= ab[3] - 1], key=lambda e: (e["box_px"][1], e["box_px"][0]))
        address = []
        for e in tail:
            if not address:
                if e["box_px"][1] - ab[3] > AUTHOR_GAP_EM * e["run_size_px"] or not INSTITUTION.match(e["text"].strip()): break
            elif (abs(e["run_size_px"] - address[0]["run_size_px"]) > SIZE_TOL * address[0]["run_size_px"] or
                  e["box_px"][1] - address[-1]["box_px"][3] > AUTHOR_STACK_EM * e["run_size_px"] or
                  re.match(r"^(?:Abstract|Summary|Keywords|Correspondence)\b", e["text"], re.I)): break
            address.append(e)
        if address:
            result["unmarked_affiliation_candidates"] = [{"block": block_of.get(address[0]["id"]), "text": " ".join(e["text"] for e in address), "box_px": hull([e["box_px"] for e in address]), "run_ids": [e["id"] for e in address]}]
            result["affiliation_box_px"] = result["unmarked_affiliation_candidates"][0]["box_px"]
    if side_rest and not result.get("affiliations") and not result.get("unmarked_affiliation_candidates"):
        result["unmarked_affiliation_candidates"] = [{"block": block_of.get(side_rest[0]["id"]), "text": " ".join(side_text),
                                                      "box_px": hull([e["box_px"] for e in side_rest]), "run_ids": [e["id"] for e in side_rest]}]
        result["affiliation_box_px"] = result["unmarked_affiliation_candidates"][0]["box_px"]
    released += sorted(cut_rest)   # round 6 rule A16: rows cut from the end of an affiliation
    if released: result["released_run_ids"] = sorted(set(released))
    if note_defs: result["author_notes"] = [{"marker": m, "text": t, "page": front_page, "run_ids": note_runs.get(m, [])} for m, t in note_defs.items()]
    if note_forms: result["author_note_marks"] = sorted(m for m in note_forms if m not in note_defs)   # round 6 rule A19
    result["title_run_ids"] = [e["id"] for e in trs]
    # Keep the evidence even when parsing fails. The copy can quote every row
    # under a flag without trusting the author parser's ownership decision.
    result["byline_lines"] = [dict(text=" ".join(e["text"] for e in sorted(by_line[li], key=lambda e: e["box_px"][0])),
                                   run_ids=[e["id"] for e in by_line[li]]) for li in alines]
    if by_introducer is not None and by_introducer['id'] not in selected:
        result['byline_lines'].insert(0, dict(text=by_introducer['text'], run_ids=[by_introducer['id']]))
    if authors and all(a["name_ok"] for a in authors):
        result["author_run_ids"] = list(dict.fromkeys([e["id"] for li in alines for e in by_line[li]] + result.get('byline_introducer_ids', [])))
    for a in result["affiliations"]: a.pop("box_px", None)
    # the checks
    ch = {"title_found": True, "title_lines": len(tlines), "authors_found": len(authors), "names_ok": sum(a["name_ok"] for a in authors),
          "authors_with_orcid": sum(a["orcid"] for a in authors), "markers_used": used}
    ch["byline_name_groups"] = len(byline_name_groups([line["text"] for line in result["byline_lines"]]))
    if used:
        missing = [m for m in used if m not in affs]; unused = [m for m in affs if m not in used and m != "0"]
        nums = sorted(int(m) for m in used if m.isdigit())
        ch.update({"affiliations_found": len(affs), "markers_without_affiliation": missing, "affiliations_not_used": unused,
                   "authors_without_marker": [a["name"] for a in authors if not a["markers"]],
                   "markers_consecutive": bool(nums) and nums == list(range(1, len(nums) + 1))})
        ok = not missing and not unused and not ch["authors_without_marker"] and ch["names_ok"] == len(authors) and (ch["markers_consecutive"] or not nums)
        ch["status"] = "verified" if ok else "not verified"
    else:
        ch["status"] = "authors found, no affiliation markers: not linked" if authors else "no authors"
    if gauthors: ch["group_authors"] = len(gauthors)
    result["checks"] = ch
    if joins:
        p["rule8"] = {"author_joins": joins}
        write_json(front_path, p, indent=1)
    elif "rule8" in p:
        del p["rule8"]
        write_json(front_path, p, indent=1)
    write_json(os.path.join(paper_dir, "authors.json"), result, indent=1, ensure_ascii=False)
    return result


def body_order_rows(page, block):
    """Read a classified box's own runs, never a page-wide rule-1 line.

    Derived rule-6 boxes keep their members in page.blocks. Missing members are
    not replaced with the abbreviated metadata text: that would fabricate the
    last words and the grammatical check. Such a box is unplaced with a flag.
    """
    source = next((b for b in page.get('blocks', []) if b['id'] == block['id']), None)
    if source is None: return []
    ids = set(source.get('members', []))
    groups = collections.defaultdict(list)
    for e in page.get('elements', []):
        if e['id'] in ids and e.get('kind') == 'text' and e.get('text', '').strip():
            groups[(e.get('angle', 0), e.get('line', e['box_px'][1]))].append(e)
    rows = []
    for es in groups.values():
        es.sort(key=lambda e: (e['box_px'][0], e['id']))
        rows.append(dict(text=' '.join(e['text'] for e in es),
                         box_px=[min(e['box_px'][0] for e in es), min(e['box_px'][1] for e in es),
                                 max(e['box_px'][2] for e in es), max(e['box_px'][3] for e in es)],
                         members=[e['id'] for e in es],
                         size_px=statistics.median(e.get('run_size_px', e.get('size_px', 0)) for e in es),
                         fonts=' '.join(str(e.get('font', '')) for e in es)))
    return sorted(rows, key=lambda r: (r['box_px'][1], r['box_px'][0]))


def body_order_columns(blocks, body, floats=()):
    """Page-local body-size paragraph extents; never borrow another page's columns.

    At least three lines witness a column. Overlapping widths merge only when
    both edges agree within one em, or either outer edge agrees and the narrower
    is at least 80% of the wider. This includes indented list paragraphs sharing
    the column's right edge. A wide abstract therefore cannot erase the
    narrower body columns beneath it. A column narrowed by an adjacent float
    inherits the wider paragraph extent sharing its opposite edge; the float
    must occupy the missing width beside that narrow paragraph. The same shape
    can be witnessed within one wider paragraph by three consecutive body-size
    rows matching the narrow extent (AD11); no missing float is invented.
    A page wholly in a different text size
    (e.g. references) uses its own dominant paragraph size, recorded by caller.
    An inset quotation bracketed above and below by one wider column inherits
    that column, unless a disjoint peer column also sits within the wider span.
    This last exclusion keeps a page-wide abstract/conclusion from absorbing
    the parallel body columns between them.
    """
    cols = []
    for b in sorted(blocks, key=lambda b: (b['box_px'][0], b['box_px'][2], b['id'])):
        if len(b['_rows']) < PARAMS['column_min_lines'] or b['size_px'] < .9 * body: continue
        x0, _, x1, _ = b['box_px']
        if x1 - x0 < 4 * body: continue
        match = next((c for c in cols if
                      (abs(c['box'][0] - x0) <= body and abs(c['box'][1] - x1) <= body) or
                      (min(abs(c['box'][0] - x0), abs(c['box'][1] - x1)) <= body and
                       min(c['box'][1] - c['box'][0], x1 - x0) >= .8 * max(c['box'][1] - c['box'][0], x1 - x0))), None)
        if match:
            match['box'] = [min(match['box'][0], x0), max(match['box'][1], x1)]
            match['witnesses'].append(b['id'])
        else: cols.append(dict(box=[x0, x1], witnesses=[b['id']]))
    by_id = {b['id']: b for b in blocks}
    for narrow in list(cols):
        if narrow not in cols: continue
        n0,n1 = narrow['box']
        enclosing = [c for c in cols if c is not narrow and c['box'][0] < n0 and n1 < c['box'][1]]
        for wide in sorted(enclosing, key=lambda c:c['box'][1]-c['box'][0]):
            w0,w1 = wide['box']
            if any(c is not narrow and c is not wide and w0 <= c['box'][0] and c['box'][1] <= w1 and
                   (c['box'][1] <= n0 or c['box'][0] >= n1) for c in cols):
                continue
            outer = [by_id[bid]['box_px'] for bid in wide['witnesses']]
            if all(any(A[3] <= by_id[bid]['box_px'][1] for A in outer) and
                   any(A[1] >= by_id[bid]['box_px'][3] for A in outer) for bid in narrow['witnesses']):
                wide.setdefault('inset_witnesses', []).extend(narrow['witnesses'])
                wide['witnesses'].extend(narrow['witnesses']); cols.remove(narrow); break
    for narrow in list(cols):
        if narrow not in cols: continue
        n0,n1 = narrow['box']
        wider = [c for c in cols if c is not narrow and c['box'][1]-c['box'][0] > n1-n0+body
                 and c['box'][0]-body <= n0 and n1 <= c['box'][1]+body
                 and min(abs(n0-c['box'][0]),abs(n1-c['box'][1])) <= body]
        for wide in sorted(wider,key=lambda c:c['box'][1]-c['box'][0]):
            w0,w1 = wide['box']; narrowed = False
            shapes = []
            for bid in wide['witnesses']:
                parent = by_id[bid]
                if parent['box_px'][2]-parent['box_px'][0] <= n1-n0+body: continue
                run = []
                for i,row in enumerate(parent['_rows']):
                    if (abs(row['box_px'][0]-n0) <= body and abs(row['box_px'][2]-n1) <= body and
                            abs(row['size_px']-body) <= PARAMS['body_size_tolerance']*body):
                        run.append(i)
                    else: run = []
                    if len(run) >= PARAMS['column_min_lines']:
                        shapes.append(dict(block_id=bid, rows=list(run), narrow_extent=[n0,n1]))
                        narrowed = True; break
            for bid in narrow['witnesses']:
                B=by_id[bid]['box_px']
                for f in floats:
                    F=f['box_px']
                    if min(F[3],B[3])-max(F[1],B[1]) <= body: continue
                    if ((n0-w0 > body and F[0] <= w0+body and n0-2*body <= F[2] <= n0+body) or
                        (w1-n1 > body and n1-body <= F[0] <= n1+2*body and F[2] >= w1-body)):
                        narrowed=True
            if narrowed:
                if shapes: wide.setdefault('shaped_column_witnesses', []).extend(shapes)
                wide['witnesses'].extend(narrow['witnesses']); cols.remove(narrow); break
    return sorted(cols, key=lambda c: c['box'])


# Port: paper-mapper/mapper/stage3_markers.py, parse_marker, heading_number,
# outline_sequence_step, next_missing, section_sequence and _pair_list_systems.
# D-522/D-555: list precedence, strict section succession and flagged resync;
# D-561: numbered level is number depth. Pure rules retained verbatim, namespaced.
BODY_ORDER_BULLETS = '•◦▪–-∙·⋅‣⁃●○◉‧'

def body_order_parse_marker(text):
    leading = len(text)-len(text.lstrip())
    text = text.lstrip()
    if not text:
        return None
    if text[0] in BODY_ORDER_BULLETS:
        return {'marker':text[0], 'syntax':'bullet', 'span':[leading,leading+1], 'ordinal':None}
    hit = re.match(r'(\d+|[ivxlcdmIVXLCDM]+|[a-z])([.)])\s+', text)
    if not hit:
        return None
    if re.match(r'(?:https?\b|doi\b|\d)',text[hit.end():],re.I):
        return None
    token = hit.group(1)
    syntax = 'decimal' if token.isdigit() else 'roman' if re.fullmatch('[ivxlcdm]+',token,re.I) else 'alphabetic'
    ordinal = int(token) if token.isdigit() else None
    return {'marker':hit.group(1)+hit.group(2), 'syntax':syntax,
            'span':[leading,leading+len(hit.group(1)+hit.group(2))], 'ordinal':ordinal}

def body_order_heading_number(text):
    """D-530: the sealed grammar's heading-only syntax, without a role guess."""
    match = re.match(r'^\s*(\d+(?:\.\d+)*\.?)(?=\s)', text)
    return tuple(int(value) for value in match[1].rstrip('.').split('.')) if match else None

def body_order_outline_sequence_step(current, number):
    """D-522/D-530 strict child/sibling relation; depth three is operator scope."""
    depth_limit = 3
    if number is None:
        return current, False, 'no heading-number prefix'
    if not 1 <= len(number) <= depth_limit:
        return current, False, 'outside ruling depth bound'
    if any(value < 1 for value in number):
        return current, False, 'not positive section numbering'
    if current is None:
        if len(number) == 1:
            return number, False, 'first plain number initializes sequence; no predecessor witness'
        return current, False, 'no observed parent/root; cannot initialize from dotted number'
    if len(current) < depth_limit and number == current + (1,):
        return number, True, 'first child of current section'
    if (len(number) <= len(current) and number[:-1] == current[:len(number)-1]
            and number[-1] == current[len(number)-1] + 1):
        return number, True, 'next sibling at current or enclosing open section depth'
    return current, False, 'not next child or sibling; state unchanged'

def body_order_ordinal(token):
    if token is None: return None
    if token['syntax']=='decimal': return token['ordinal']
    marker=token['marker'].lstrip('(')
    if token['syntax']=='alphabetic': return ord(marker[0])-ord('a')+1
    if token['syntax']=='roman':
        values={'i':1,'v':5,'x':10,'l':50,'c':100,'d':500,'m':1000}
        seq=[values[c] for c in marker[:-1].lower()]
        return sum(-v if i+1<len(seq) and v<seq[i+1] else v for i,v in enumerate(seq))
    return None

def body_order_pair_list_systems(lines,intervals=()):
    alignment="additive";numbered_only=True
    tokens={l['ref']:body_order_parse_marker(l['text']) for l in lines}
    # A lane is one actual saved interval; identical bounds share a witness list.
    bybounds={}
    assert alignment in {'exact','interval','additive'}
    if alignment in {'interval','additive'}:
        for iv in intervals:
            if iv['bounds'] is not None:bybounds.setdefault(tuple(iv['bounds']),[]).append(iv['id'])
    exact_x={l['x'] for l in lines if tokens[l['ref']]} if alignment in {'exact','additive'} else set()
    for x in exact_x:bybounds.setdefault((x,x),[])
    lanes=sorted({(t['syntax'],bounds) for l in lines if (t:=tokens[l['ref']]) for bounds in bybounds if bounds[0]<=l['x']<=bounds[1]})
    systems=[];unattached=[];runs_by_signature={}
    for syntax,bounds in lanes:
        stream=[l for l in lines if bounds[0]<=l['x']<=bounds[1]]
        run=[]
        def flush():
            if sum(not r['inferred'] for r in run)>=2:
                # Multiple intervals witnessing the identical run are one system,
                # with every witness retained. No union or transitive closure.
                signature=(syntax,tuple((r['ref'],r['ordinal'],r['inferred']) for r in run))
                witness={'bounds':list(bounds),'interval_ids':bybounds[bounds],'exact_equality':bounds[0]==bounds[1] and bounds[0] in exact_x}
                if signature in runs_by_signature:
                    systems[runs_by_signature[signature]]['alignment']['supports'].append(witness)
                else:
                    runs_by_signature[signature]=len(systems)
                    systems.append({'id':'list-system-'+str(len(systems)+1),'syntax':syntax,
                        'alignment':{'predicate':alignment+' alignment; exact equality and/or one saved D-462 interval, inclusive','supports':[witness]},'members':[dict(r) for r in run]})
        def member(l,t):return {'ref':l['ref'],'ordinal':body_order_ordinal(t),'marker':t['marker'],'inferred':False,'flag':None}
        i=0
        while i<len(stream):
            first=stream[i];token=tokens[first['ref']]
            if not token or token['syntax']!=syntax:i+=1;continue
            run=[member(first,token)];last=body_order_ordinal(token);i+=1
            while i<len(stream):
                line=stream[i];token=tokens[line['ref']]
                same=token is not None and token['syntax']==syntax
                value=body_order_ordinal(token) if same else None
                if same and (syntax=='bullet' or value==last+1):
                    run.append(member(line,token));last=value;i+=1;continue
                nxt=stream[i+1] if i+1<len(stream) else None
                nt=tokens[nxt['ref']] if nxt else None
                if (not numbered_only or syntax in {'decimal','roman','alphabetic'}) and nt and nt['syntax']==syntax and (syntax=='bullet' or body_order_ordinal(nt)==last+2):
                    run.append({'ref':line['ref'],'ordinal':None if syntax=='bullet' else last+1,'marker':'inferred from sequence','inferred':True,'flag':'inferred from sequence','observed_token':token,'confirming_next':nxt['ref']})
                    run.append(member(nxt,nt));last=body_order_ordinal(nt);i+=2;continue
                if same and syntax!='bullet' and value==last+2:
                    unattached.append({'syntax':syntax,'bounds':list(bounds),'after':run[-1]['ref'],'before':line['ref'],'missing_ordinal':last+1,'reason':'no unique aligned intervening line'})
                break
            flush()
    return systems,unattached,[]

def body_order_next_missing(current,number):
    if current is None or not number or len(number)>len(current)+1:return None
    missing=number[:-1]+(number[-1]-1,)
    mid,ok,_=body_order_outline_sequence_step(current,missing)
    _,ok2,_=body_order_outline_sequence_step(mid,number)
    return missing if ok and ok2 else None

def body_order_section_sequence(blocks,excluded):
    current=None;pending=[];rows=[];resync=[]
    for block in blocks:
        first=block['lines'][0] if block['lines'] else None
        if first is None:continue
        number=body_order_heading_number(first['text']);before=current
        row={'block':block['ref'],'line':first['ref'],'text':first['text'],'observed_number':number,'number':number,'current_before':before,'sequence':False,'inferred':False,'flag':None}
        if first['ref'] in excluded:
            row.update(reason='confirmed list system has precedence',current_after=current);rows.append(row);continue
        updated,ok,reason=body_order_outline_sequence_step(current,number)
        missing=body_order_next_missing(current,number) if number is not None and not ok else None
        if missing is not None:
            candidates=[r for r in pending if r['text'].lstrip() and r['text'].lstrip()[0].isdigit()]
            attached=candidates[0] if len(candidates)==1 else None
            event={'before':before,'missing_number':missing,'resynchronized_on':number,'resynchronized_line':first['ref'],'attached_line':attached['line'] if attached else None,'flag':'inferred from sequence','candidate_lines':[r['line'] for r in candidates]}
            if attached:
                attached.update(number=missing,sequence=True,inferred=True,flag='inferred from sequence',reason='single malformed/misread number bridged by the next well-formed number',current_after=missing)
            resync.append(event);updated=number;ok=True;reason='resynchronized after one missing or malformed number'
        row.update(sequence=ok,reason=reason,current_after=updated)
        if updated!=current:
            pending=[];current=updated
        else:pending.append(row)
        rows.append(row)
    return rows,resync

# Port: paper-mapper/mapper/stage3_text_body.py::_textcue_rule (D-488, D-520).
# Soft hyphen is sufficient; other text cues only confirm, never assert a break.
BODY_ORDER_HYPHENS = "-\u2010\u2011"
BODY_ORDER_TERMINAL = ".!?"

def body_order_textcue_rule(last, nxt):
    a, b = (last.strip().replace('\x02', '\xad'), nxt.strip().replace('\x02', '\xad'))
    assert a and b
    if a[-1] == '\xad':
        return ('continuation', 'soft hyphen')
    if a[-1] in BODY_ORDER_HYPHENS:
        if len(a) >= 2 and a[-2].isalnum() and b[0].islower():
            return ('continuation', 'attached hyphen + lowercase')
        return ('undecided', 'none (literal or nonqualifying hyphen)')
    if a[-1] not in BODY_ORDER_TERMINAL and b[0].islower():
        return ('continuation', 'no terminal punctuation + lowercase')
    return ('undecided', 'none')

def body_order_grammar(last, first):
    """Expose the shared boundary witness's text verdict, with absent text explicitly neutral."""
    a, b = last.strip().replace('\x02', '\xad'), first.strip().replace('\x02', '\xad')
    w = boundary_witness(a, b) if a and b else dict(verdict='undecided', reason='no text')
    confirms = w['verdict'] == 'continuation' and w['reason'] not in ('number after an open end', 'bracket after an open end')   # rule 9's cue is the text cue
    reason = w['reason'] if confirms or not (a and b) else body_order_textcue_rule(a, b)[1]
    return dict(unterminated_end=bool(a and a[-1] not in BODY_ORDER_TERMINAL),
                lowercase_start=bool(b and b[0].islower()),
                hyphen_completing_start=reason in ('soft hyphen', 'attached hyphen + lowercase'),
                confirms_continuation=confirms, reason=reason,
                verdict='continuation confirmed' if confirms else 'inconclusive; text is not a break witness')


# Shared boundary witness (D-488, D-520; mapper stage3_text_body _textcue_rule as
# ported above, plus the copier's bracket witness and rule 9's layout witnesses).
# One function decides every stream boundary: rule 9's grammar, the copier's
# paragraph joins, its float/note/front-matter slots and its sandwich pass, and
# the second pass's rule 3 all call it, so the four checks can no longer drift.
BOUNDARY_TERMINAL = re.compile(r"[.?!:]['\")\]’”]*$|[.?!]['\")\]’”]*\d+(?:[,–-]\d+)*$")
BOUNDARY_OPENING = re.compile(r"^[\"“‘'(\[]*\s*(?:[A-ZÀ-ÞΑ-Ω]|\d|[•●◦▪]|[-–—]\s|"
                              r"\(?[a-z]{1,2}[.)]\s|\(?[ivx]{1,4}[.)]\s)")


BOUNDARY_SENTENCE_CUT = re.compile(r'(?<=[.?!])\s+(?=[A-Z0-9(\[])')


def boundary_unfinished_sentence(text):
    """The last sentence of TEXT, from its last sentence end that lies outside every bracket
    (the copier's unfinished_sentence, D-520): a cut whose following text closes a bracket it
    never opened lies inside a bracket ("(Fig. 4G)") and is passed over."""
    text = (text or '').rstrip()
    for m in reversed(list(BOUNDARY_SENTENCE_CUT.finditer(text))):
        tail = text[m.end():]
        def balanced(o, c):
            depth = 0
            for ch in tail:
                depth += (ch == o) - (ch == c)
                if depth < 0: return False
            return True
        if balanced('(', ')') and balanced('[', ']'):
            return tail
    return text


def boundary_bracket(last, nxt):
    """An unclosed bracket in LAST's unfinished sentence (boundary_unfinished_sentence) that
    NXT closes before opening its own (the copier's bracket_continuation, moved here: "(Fig. /
    6)" at a column turn). LAST must end inside the bracket: its last opener stands after its
    last closer (a stray bracket before a citation closed at the end is a finished sentence)."""
    tail = boundary_unfinished_sentence(last)
    head = (nxt or '').lstrip()
    for o, c in ('()', '[]'):
        if tail.count(o) > tail.count(c) and tail.rfind(o) > tail.rfind(c):
            m = re.search('[%s%s]' % (re.escape(o), re.escape(c)), head)
            if m and m[0] == c: return True
    return False


BOUNDARY_OPEN_WORD = re.compile(r"(?:^|\s)[(\[\"“‘]*[^\W\d_]*[a-z\u00DF-\u00FF\u0101-\u017F](?:[-\u2010\u2011\u00AD]|[,;])?$")
BOUNDARY_RESUME = re.compile(r"[a-z\u00DF-\u00FF]+(?:[-\u2010\u2011][a-z\u00DF-\u00FF]+)*[\s,;:.)]")


def boundary_open_end(text):
    """A text end that only a sentence can continue: a last word of letters ending in a
    lowercase letter, optionally followed by a comma, semicolon or attached hyphen; a bare
    dash; or an acronym after a lowercase word ("...items for the CPAP"). Addresses, URLs, codes and numbers ("ege.edu.tr", "10.1902/x", "p < 0.05",
    "[12]") end otherwise: their punctuation can be printed raised or not at all."""
    t = (text or '').rstrip()
    return bool(t) and (bool(BOUNDARY_OPEN_WORD.search(t)) or bool(re.search(r"[^\W\d_]\s*[\u2013\u2014]$", t)) or
                        bool(re.search(r"(?:^|\s)[a-z]{2,}\s+[A-Z][A-Z0-9]{1,5}$", t)))


def boundary_resumes(text):
    """A start that resumes a sentence: an ordinary lowercase word, not a mixed-case token
    such as "mRNA", "iNOS" or "p53", which also open sentences."""
    return bool(BOUNDARY_RESUME.match((text or '').lstrip() + ' '))


def boundary_witness(last, nxt, terminal=None, layout=None):
    """Witness for the boundary between text LAST and the text NXT that would follow it.

    Verdicts, in this order:
      continuation  the text confirms one sentence: a soft hyphen; an attached hyphen
                    before a lowercase start; no terminal punctuation before a lowercase
                    start (body_order_textcue_rule); an unclosed bracket of the last
                    sentence that NXT closes (boundary_bracket); or a number that is not
                    a list or section marker after a word-open end (boundary_open_end).
      layout        LAYOUT (a dict from the caller's geometry) says NXT's first line is
                    LAST's next printed line: 'next_line' (same column, at line pitch,
                    after a full line, flush start) or 'column_turn' (a full last line at
                    a column or page foot and a flush first line at the next column head),
                    or 'foot_to_head' (LAST is the lowest body text of its column and NXT the
                    highest of another column or page: B2, the break is the column's end).
      sentence      B1: LAST ends in terminal punctuation (TERMINAL, the caller's test,
                    which knows raised citations; default . ? ! : and closing marks) and
                    NXT opens with a capital, digit, list marker or opening bracket.
      undecided     anything else: an unterminated end before a capital, or a terminal
                    end before a lowercase word. Text never witnesses a break; an
                    undecided boundary is neither joined nor used as a slot.
    """
    a = (last or '').strip().replace('\x02', '\xad'); b = (nxt or '').strip().replace('\x02', '\xad')
    unterminated = bool(a) and not (terminal(a) if terminal else BOUNDARY_TERMINAL.search(a))
    base = dict(unterminated=unterminated, lowercase=bool(b) and b[0].islower())
    if not a or not b: return dict(base, verdict='undecided', reason='no text')
    verdict, reason = body_order_textcue_rule(a, b)
    if verdict == 'continuation': return dict(base, verdict='continuation', reason=reason)
    if boundary_bracket(a, b): return dict(base, verdict='continuation', reason='unclosed bracket closed by the next text')
    # A number after a word-open end continues the sentence ("lasted / 5.6 years"), unless it is
    # shaped like a list or section marker ("2. Methods", "3) The").
    if boundary_open_end(a) and re.match(r'\d', b) and not re.match(r'\d+(?:\.\d+)*[.)]?\s+[A-Z]', b):
        return dict(base, verdict='continuation', reason='number after an open end')
    # An opening bracket after a word-open end ("such as plaque / (the biofilm)", an inline
    # enumeration "lesions, / (b) relevant") continues it too.
    if boundary_open_end(a) and b[0] in '([':
        return dict(base, verdict='continuation', reason='bracket after an open end')
    layout = layout or {}
    if layout.get('next_line'): return dict(base, verdict='layout', reason='next printed line at pitch after a full line')
    if layout.get('column_turn'): return dict(base, verdict='layout', reason='full last line at a column foot, flush head of the next column')
    if layout.get('foot_to_head'): return dict(base, verdict='layout', reason='last body text at a column foot, first body text at the next column head')
    if not unterminated and BOUNDARY_OPENING.match(b): return dict(base, verdict='sentence', reason='terminal punctuation before a capital, digit or list start')
    return dict(base, verdict='undecided', reason='none (unterminated + capital)' if unterminated else 'none (terminal + lowercase)')


def body_order_interval(values):
    values = list(values)
    return [min(values), max(values)] if values else None


def body_order_overlap(a, b):
    return [max(a[0], b[0]), min(a[1], b[1])] if a and b and max(a[0], b[0]) <= min(a[1], b[1]) else None


def body_order_preserve_panel_moves(ordered, panels):
    """Retain boundaries already exposed by rule 7 reading_order_defer_panels.

    Rule 7 records a panel move and, when needed, splits the interrupted body
    paragraph into explicit boxes. Rebuilding geometric bands must not undo
    that working placement (observed on Y05). Reuse only this recorded boundary:
    its ordinary neighbors must still be adjacent in rule 9's own order. Never
    rerun rule 7's text heuristics, split boxes, or copy its entire body order.
    A stale or conflicting boundary leaves geometry in place with a review flag.
    """
    grouped = {bid for p in panels for bid in p['blocks']}
    ordinary = [b for b in ordered if b['id'] not in grouped]
    records = []
    for panel in sorted(panels, key=lambda p:p.get('order', 0)):
        if not panel.get('move'): continue
        members = [b for b in ordered if b['id'] in panel['blocks']]
        record = dict(panel=panel['id'], members=[b['id'] for b in members], source_move=panel['move'])
        valid = len(members) == len(panel['blocks']) and all(isinstance(b.get('order'), int) for b in members+ordinary)
        before = after = None
        if valid:
            low, high = min(b['order'] for b in members), max(b['order'] for b in members)
            before = max((b for b in ordinary if b['order'] < low), key=lambda b:b['order'], default=None)
            after = min((b for b in ordinary if b['order'] > high), key=lambda b:b['order'], default=None)
            left = ordinary.index(before) if before else -1
            right = ordinary.index(after) if after else len(ordinary)
            valid = (low == panel['move'].get('to_order') and right == left+1 and
                     not any(low <= b['order'] <= high for b in ordinary))
        record.update(after=before['id'] if before else None, before=after['id'] if after else None)
        if valid:
            ordered = [b for b in ordered if b['id'] not in panel['blocks']]
            # Insert just before the succeeding ordinary block. Panels sharing
            # this boundary retain their recorded relative order.
            at = ordered.index(after) if after else len(ordered)
            ordered[at:at] = members
            record['status'] = 'recorded paragraph boundary preserved'
        else:
            record['status'] = 'recorded panel boundary conflicts with body order; review'
            for b in members: b['_flags'].append(record['status'])
        records.append(record)
    return ordered, records


def body_order_start_intervals(block, blocks, body):
    """Port stage3_text_body.start_intervals, D-462: two observed start classes.

    Boxer body-size member rows replace the mapper's sustained normal runs;
    column membership is the page-local assignment already witnessed above.
    First and later rows retain distinct min/max intervals, including overlap.
    No nearest-class assignment, em-sized indent threshold or cross-paper pool.
    """
    first, later = [], []
    for b in blocks:
        if b['page'] != block['page'] or b['_column'] != block['_column'] or b['_heading']:
            continue
        if len(b['_rows']) < PARAMS['column_min_lines']:
            continue
        for i, row in enumerate(b['_rows']):
            if abs(row['size_px'] - body) > PARAMS['body_size_tolerance'] * body:
                continue
            sample = dict(block_id=b['id'], row=i, members=row['members'], start_px=row['box_px'][0])
            (first if i == 0 else later).append(sample)
    a = body_order_interval(s['start_px'] for s in first)
    b = body_order_interval(s['start_px'] for s in later)
    return dict(first_line_starts=a, continuation_line_starts=b, overlap=body_order_overlap(a, b),
                first_line_samples=first, continuation_line_samples=later)


def body_order_end_intervals(block, blocks, body):
    """Port stage3_text_body.end_intervals, D-463/D-464, as retained by D-520.

    A column/page/document end cannot train the paragraph-end class. Nor can
    the tested block's own end. Interval overlap is evidence, never a break.
    Samples are addressed by box/row so every exclusion can be inspected.
    """
    last, continuing, boundary, own = [], [], [], []
    for i, b in enumerate(blocks):
        if b['page'] != block['page'] or b['_column'] != block['_column'] or b['_heading']:
            continue
        if len(b['_rows']) < PARAMS['column_min_lines']:
            continue
        nxt = blocks[i+1] if i+1 < len(blocks) else None
        reason = ('document-end' if nxt is None else 'page-break' if nxt['page'] != b['page'] else
                  'column-break' if nxt['_column'] != b['_column'] else None)
        for j, row in enumerate(b['_rows']):
            if abs(row['size_px'] - body) > PARAMS['body_size_tolerance'] * body:
                continue
            sample = dict(block_id=b['id'], row=j, end_px=row['box_px'][2])
            if j != len(b['_rows'])-1:
                continuing.append(sample)
            elif reason:
                boundary.append(dict(sample, reason=reason))
            elif b['id'] == block['id']:
                own.append(dict(sample, reason='evaluated-block-own-break'))
            else:
                last.append(sample)
    a = body_order_interval(s['end_px'] for s in last)
    b = body_order_interval(s['end_px'] for s in continuing)
    return dict(paragraph_last_ends=a, continuing_line_ends=b, overlap=body_order_overlap(a, b),
                paragraph_last_samples=last, continuing_line_samples=continuing,
                boundary_exclusions=boundary, own_break_exclusions=own)


def body_order_layout_break_witnesses(a, b, starts, paper_indents, pitch, between):
    """Port stage3_text_body.layout_break_witnesses, D-520 (with D-462).

    Indent uses the paper's observed first/later classes. Gaps and intervening
    units apply only within one column, as in the source. The boxer has no
    saved mapper pitch tolerance: use the upper observed normal-run pitch,
    the source continuation() paragraph_gap test, with no new multiplier.
    Only units strictly between endpoints witness a heading/float break;
    an endpoint heading or a float crossed on a column move is not one.
    """
    first = b['_rows'][0]['box_px']; last = a['_rows'][-1]['box_px']
    witnesses = []
    f, c = starts['first_line_starts'], starts['continuation_line_starts']
    if paper_indents and f and c and f[0] <= first[0] <= f[1] and first[0] > c[1]:
        witnesses.append(dict(kind='indent', first_line_class=f, continuation_class=c,
                              next_x=first[0], sample_count=len(starts['first_line_samples'])))
    if a['page'] != b['page'] or a['_column'] != b['_column']:
        return witnesses
    if pitch and first[1] - last[1] > pitch[1]:
        witnesses.append(dict(kind='vertical-gap', top_delta_px=first[1]-last[1], allowed_pitch_px=pitch[1]))
    for unit in between:
        box = unit['box_px']
        if (box[1] >= last[3] and box[3] <= first[1] and
                min(box[2], first[2], last[2]) > max(box[0], first[0], last[0])):
            witnesses.append(dict(kind=unit['kind'], unit_id=unit['id'], between_blocks=True))
    return witnesses


def body_order_heading_sequence(blocks):
    """Adapt stage3_markers.section_sequence, D-522/D-555/D-561, to main boxes.

    Aligned marker runs take precedence. Every row is offered to that list
    test, so a list contained in a large box cannot advance section state.
    Numbered candidates need sequence, short unterminated text and a body box
    below in their column; two witnesses flag, all three decide. Initial root
    numbers and inferred/misprinted numbers remain flagged. Appearance levels
    are learned from accepted numbered headings of the same size/bold style;
    an unknown unnumbered level stays null, never an invented hierarchy.
    """
    lines_by_page = collections.defaultdict(list)
    candidates = []; detached = {}; sequence_text = {}
    # Data adaptation: rule 6 can keep a margin section number in its own box.
    # Offer number + uniquely adjacent typographic heading to the ported grammar
    # as one witness, while retaining both source boxes in the order ledger.
    # A number beside ordinary prose/reference text is not such a witness.
    for b in blocks:
        if not re.fullmatch(r'\s*\d+(?:\.\d+)*\.?\s*', b['text']):
            continue
        peers = [c for c in blocks if c is not b and c['page'] == b['page'] and c['_appearance_heading'] and
                 c['_column'] == b['_column'] and
                 abs(c['box_px'][1]-b['box_px'][1]) <= PARAMS['same_line_em']*c['size_px'] and
                 0 <= c['box_px'][0]-b['box_px'][2] <= PARAMS['flow_gap_em']*c['size_px']]
        if len(peers) == 1:
            detached[(b['page'], b['id'])] = peers[0]
            sequence_text[(b['page'], b['id'])] = b['text'].strip()+' '+peers[0]['text']
    for b in blocks:
        ref = (b['page'], b['id'])
        for i, row in enumerate(b['_rows']):
            text = sequence_text.get(ref, row['text']) if i == 0 else row['text']
            lines_by_page[b['page']].append(dict(ref=ref+(i,), text=text, x=row['box_px'][0]))
        candidates.append(dict(ref=ref, lines=[dict(ref=ref+(0,), text=sequence_text.get(ref, b['text']))]))
    excluded = set()
    systems = []
    for pn, lines in lines_by_page.items():
        found, _, _ = body_order_pair_list_systems(lines)
        for system in found:
            system['page'] = pn
            excluded.update(m['ref'] for m in system['members'])
        systems.extend(found)
    rows, resync = body_order_section_sequence(candidates, excluded)
    by_ref = {tuple(row['block']): row for row in rows}
    for b in blocks:
        row = by_ref[(b['page'], b['id'])]
        numbered = row['observed_number'] is not None
        candidate_text = sequence_text.get((b['page'], b['id']), b['text'])
        short = b['lines'] <= 3 and len(candidate_text.split()) <= 30 and not re.search(r'[.!?]$', candidate_text.strip())
        below = any(c['page'] == b['page'] and c is not b and not c['_heading'] and
                    c['_column'] == b['_column'] and c['box_px'][1] >= b['box_px'][3] for c in blocks)
        witnesses = dict(sequence=row['sequence'], short_unterminated=short, body_below=below)
        if (b['page'], b['id'], 0) in excluded:
            b['_heading'] = False
        elif numbered:
            b['_heading'] = row['sequence'] and short and below
            if not b['_heading'] and (sum(witnesses.values()) >= 2 or b.get('_appearance_heading')):
                b['_flags'].append('numbered heading unconfirmed: '+row['reason'])
            if row['inferred'] or 'resynchronized' in row['reason']:
                b['_flags'].append('heading number inferred from sequence')
        b['_heading_evidence'] = dict(row, witnesses=witnesses,
                                     candidate_level=len(row['number']) if row['number'] else None)
        b['_level'] = len(row['number']) if b['_heading'] and row['number'] else None
        if not b['_heading']:
            b.pop('_heading_to', None)
        else:
            following = [c for c in blocks if c['page'] == b['page'] and c is not b and
                         c['_column'] == b['_column'] and c['box_px'][1] >= b['box_px'][3]]
            if following:
                b['_heading_to'] = min(following, key=lambda c:(c['box_px'][1],c['box_px'][0]))['id']
    for b in blocks:
        peer = detached.get((b['page'], b['id']))
        if peer is None:
            continue
        peer['_heading'] = b['_heading']; peer['_level'] = b['_level']
        peer['_flags'].extend(b['_flags'])
        peer['_heading_evidence'] = dict(b['_heading_evidence'], number_source=dict(page=b['page'],id=b['id']))
        b['_heading_evidence']['text_source'] = dict(page=peer['page'],id=peer['id'])
        if b['_heading']:
            b['_heading_to'] = peer['id']
        else:
            peer.pop('_heading_to', None)
    styles = collections.defaultdict(set)
    def style(b):
        return (round(b['size_px'], 1), bool(re.search(r'bold|black|demi', b['_rows'][0]['fonts'], re.I)))
    for b in blocks:
        if b['_heading'] and b['_level'] and not b['_flags']:
            styles[style(b)].add(b['_level'])
    for b in blocks:
        if not b['_heading']:
            continue
        levels = styles[style(b)]
        b['_heading_evidence']['appearance_levels'] = sorted(levels)
        if b['_level'] is None and len(levels) == 1:
            b['_level'] = next(iter(levels))
        elif b['_level'] is not None and levels and levels != {b['_level']}:
            b['_flags'].append('heading appearance level conflicts with number depth')
    return dict(sequence=rows, resynchronizations=resync, list_systems=systems)


# Port: paper-mapper/mapper/stage3_text_body.py::continuation, with its
# layout_break_witnesses/start_intervals/end_intervals/_textcue_rule contracts
# (D-017, D-462, D-488, D-520). The adapter uses boxer member rows and measured
# page-local pitch in place of mapper units/fingerprints. Default continuation,
# witnessed breaks, text-only confirmation and undecided conflicts are retained.
def body_reading_order(pages):
    """Rule 9: explicit body reading order, after rules 1-8; no upstream mutation.

    The input is the final rule-6 classification. Only cls=main enters this
    stream; title/authors, furniture, floats, captions, asides and other never
    enter it. Every main box is placed once or appears flagged in unplaced.
    A box remains indivisible; ambiguous overlapping boxes and missing run
    geometry are reported rather than split or silently omitted.

    Page-local, body-size paragraph boxes establish columns. The dominant
    paragraph size is measured on each page; no earlier/later page supplies
    a missing column. With no paragraph witnesses the box extents supply a
    provisional geometric order, flagged for review. The rule-7 geometric
    band primitive is reused on private copies with these local columns:
    column-major around floats, changing bands only at a witnessed layout
    change. Prose panels stay atomic using their own local paragraph columns.
    Recorded rule-7 panel moves retain their exposed paragraph boundary when
    its ordinary neighbors agree with this order; conflicts are flagged.
    Numbered headings use the ported section sequence after list precedence,
    with level from number depth and inferred numbers flagged (D-555/D-561).
    A short typographic or named heading takes the column of the nearest
    aligned block below it; stacked headings inherit that assignment. Margin
    labels remain explicit boxes instead of disappearing into another box.

    Every adjacent pair records its actual page/column/float transitions,
    last-line fullness, next first-line indent, and measured line pitch.
    The mapper's D-462 first/later start intervals establish whether the paper
    indents; the next start must lie in the first class beyond the later class.
    A break requires such an indent, a vertical gap exceeding the observed
    normal pitch interval, or a heading/float strictly between same-column endpoints. Last-line fullness predicts flow but
    a short/terminal line is not by itself a break witness. Across columns or
    pages without a witness: 'stream continues, no break witnessed'. Grammar
    checks every join using the ported _textcue_rule: a soft hyphen suffices;
    an attached hard hyphen or nonterminal ending needs a lowercase start. It can confirm continuation, never demand a paragraph break. A
    layout break against that confirmation is undecided and flagged, keeping
    both witnesses. Order ambiguity is separately flagged; grammar never
    reorders boxes. This is the D-017 design under D-520's continuation ruling.

    The ledger is additive. In particular it does not fix a rule-6 ownership
    error or change copy.md; consumers must inspect flags before adopting it.
    """
    result = dict(schema='body-order/1', rule=9, blocks=[], edges=[], pages=[], unplaced=[], flags=[])
    if not pages:
        result['flags'].append('no page records: body order cannot be assessed')
    all_blocks = []; page_data = {}
    for page in sorted(pages, key=lambda p: p['page']):
        pn = page['page']; mt = page.get('main_text', {}); blocks = []; seen = set()
        for meta in mt.get('blocks', []):
            if meta.get('cls') != 'main': continue
            key = dict(page=pn, id=meta['id'], box_px=meta.get('box_px'))
            rows = body_order_rows(page, meta)
            reason = None
            if meta['id'] in seen: reason = 'duplicate main box id'
            elif not rows: reason = 'main box has no nonempty member text runs'
            elif not meta.get('box_px') or len(meta['box_px']) != 4: reason = 'main box has no valid box'
            seen.add(meta['id'])
            if reason:
                result['unplaced'].append(dict(key, flagged=True, reason=reason)); continue
            b = dict(meta, page=pn, _rows=rows, _flags=list(meta.get('ownership_flags', [])))
            b.pop('list_column', None)   # must be re-witnessed on this page
            b['text'] = '\n'.join(r['text'] for r in rows)
            b['size_px'] = statistics.median(r['size_px'] for r in rows) or mt.get('body_size_px', 1)
            b['lines'] = len(rows)
            # Rule 7 absorbs margin labels; rule 9 lists every large box once.
            if b.get('why') == 'label beside main text of its size': b['why'] = 'explicit margin label'
            blocks.append(b)
        sizes = collections.Counter()
        panel_ids = {bid for p in mt.get('panels', []) for bid in p['blocks']}
        body_blocks = [b for b in blocks if b['id'] not in panel_ids and not b.get('abstract') and b['lines'] >= 3]
        for b in body_blocks or blocks:
            if b['lines'] >= PARAMS['column_min_lines']:
                sizes[round(b['size_px'], 1)] += b['lines']
        body = max(sizes, key=sizes.get) if sizes else (mt.get('body_size_px') or 1)
        panels = []
        for panel in mt.get('panels', []):
            children = [b for b in blocks if b['id'] in panel['blocks']]
            if not children: continue
            local = body_order_columns(children, panel.get('size_px') or body)
            panels.append(dict(panel, columns=[c['box'] for c in local] or [panel['box_px'][::2]]))
        panel_ids = {bid for p in panels for bid in p['blocks']}
        cols = body_order_columns([b for b in blocks if b['id'] not in panel_ids], body, page.get('floats', []))
        if not cols:
            # No borrowing: use the local ink extents and expose the uncertainty.
            for b in blocks: b['_flags'].append('no page-local body paragraph column witness')
        extents = [c['box'] for c in cols]
        def column(b):
            box = b['box_px']
            fits = [c for c in extents if c[0] - body <= box[0] and box[2] <= c[1] + body]
            return list(min(fits, key=lambda c: c[1] - c[0])) if fits else [box[0], box[2]]
        floats = page.get('floats', [])
        named = re.compile(r'^(?:\d+(?:\.\d+)*\.?\s+)?(?:abstract|summary|introduction|background|'
                           r'materials?(?:\s+and\s+methods)?|methods|results(?:\s+and\s+discussion)?|'
                           r'discussion|conclusions?|references|acknowledg(?:e)?ments?|appendi(?:x|ces))\s*[:.]?$', re.I)
        for b in blocks:
            rows = b['_rows']; b['_column'] = column(b)
            bold = bool(re.search(r'bold|black|demi', rows[0]['fonts'], re.I))
            b['_heading'] = (b['lines'] <= 3 and len(b['text'].split()) <= 30 and
                             (b['size_px'] > 1.08 * body or named.fullmatch(b['text'].strip()) is not None or
                              bold and not re.search(r'[.!?;:]$', b['text'].strip())))
            if b['id'] in panel_ids:
                panel = next(p for p in panels if b['id'] in p['blocks'])
                fits = [c for c in panel['columns'] if c[0]-body <= b['box_px'][0] and b['box_px'][2] <= c[1]+body]
                if fits: b['_column'] = list(min(fits, key=lambda c:c[1]-c[0]))
            b['_appearance_heading'] = b['_heading']
        for b in sorted(blocks, key=lambda b:b['box_px'][1], reverse=True):
            if not b['_heading']: continue
            x0,y0,x1,y1 = b['box_px']
            below = [a for a in blocks if a is not b and a['box_px'][1] >= y1 and
                     a['box_px'][0]-body <= x0 and x1 <= a['box_px'][2]+body]
            nxt = min(below, key=lambda a:a['box_px'][1], default=None)
            if nxt and nxt['box_px'][1]-y1 <= 4*body and not any(
                    f['box_px'][1] < nxt['box_px'][1] and f['box_px'][3] > y1 and
                    min(f['box_px'][2],x1) > max(f['box_px'][0],x0) for f in floats):
                b['_column'] = list(nxt['_column']); b['_heading_to'] = nxt['id']
        # A detached heading/reference marker belongs with its same-line box.
        for b in blocks:
            if b.get('why') != 'explicit margin label': continue
            peers = [a for a in blocks if a is not b and abs(a['box_px'][1]-b['box_px'][1]) <= .5*body
                     and 0 <= a['box_px'][0]-b['box_px'][2] <= 3*body]
            if peers: b['_column'] = list(min(peers, key=lambda a:a['box_px'][0])['_column'])
        for b in blocks: b['list_column'] = b['_column']
        ordered, cuts = reading_order_bands(blocks, extents, body, [f['box_px'] for f in floats], panels)
        ordered, panel_placements = body_order_preserve_panel_moves(ordered, panels)
        # Positive-area box overlaps can mean a fused multi-column box or an
        # embedded label. Keep all boxes, but never certify that order silently.
        for i,a in enumerate(blocks):
            for b in blocks[i+1:]:
                A,B = a['box_px'],b['box_px']
                if min(A[2],B[2])-max(A[0],B[0]) > body and min(A[3],B[3])-max(A[1],B[1]) > .5*body:
                    a['_flags'].append('overlapping main box: '+b['id']); b['_flags'].append('overlapping main box: '+a['id'])
        # The mapper fingerprint's sustained normal-run pitch becomes the
        # interval of adjacent body-size rows joined by rule 2's own gap rule.
        pitches = [s['box_px'][1]-r['box_px'][1] for b in blocks if not b['_heading']
                   for r,s in zip(b['_rows'],b['_rows'][1:])
                   if all(abs(q['size_px']-body) <= PARAMS['body_size_tolerance']*body for q in (r,s))
                   and 0 <= s['box_px'][1]-r['box_px'][3] <= PARAMS['stack_gap_em']*body]
        pitch = body_order_interval(pitches)
        rec = dict(page=pn, body_size_px=body, columns=cols, pitch_px=pitch, band_boundaries_y=cuts,
                   panel_placements=panel_placements)
        result['pages'].append(rec)
        page_data[pn] = dict(page=page, body=body, pitch=pitch, floats=floats)
        all_blocks.extend(ordered)
    result['headings'] = body_order_heading_sequence(all_blocks)
    # Rule 9 cannot repair rule-6 ownership. A smaller main box (for example
    # a footnote or a missed table cell) stays in the ledger with a review flag;
    # it must not silently interrupt body prose as if it shared the body face.
    # Explicit prose panels have their own size model and are exempt here.
    for b in all_blocks:
        pd = page_data[b['page']]
        in_panel = any(b['id'] in p['blocks'] for p in pd['page'].get('main_text', {}).get('panels', []))
        if not b['_heading'] and not in_panel and b['size_px'] < (1-PARAMS['body_size_tolerance'])*pd['body']:
            b['_flags'].append('main box smaller than page body; ownership requires review')
    models = {}; indent_witnesses = []
    for b in all_blocks:
        key = (b['page'], tuple(b['_column']))
        if key not in models:
            classes = body_order_start_intervals(b, all_blocks, page_data[b['page']]['body'])
            classes.update(id='start-classes:'+str(len(models)+1), page=b['page'], column=b['_column'])
            models[key] = classes
            rest = classes['continuation_line_starts']
            if rest:
                indent_witnesses.extend(dict(sample, page=b['page'], model=classes['id'])
                    for sample in classes['first_line_samples'] if sample['start_px'] > rest[1])
        b['_starts'] = models[key]
    uses_indents = bool(indent_witnesses)
    result['indent_model'] = dict(uses_indents=uses_indents, witnesses=indent_witnesses)
    result['start_classes'] = list(models.values())
    for b in all_blocks:
        words = b['text'].split()
        result['blocks'].append(dict(page=b['page'], id=b['id'], box_px=b['box_px'],
            first_words=' '.join(words[:8]), last_words=' '.join(words[-8:]),
            column=b['_column'], heading=b['_heading'], heading_before=b.get('_heading_to'),
            level=b['_level'], heading_evidence=b['_heading_evidence'],
            order=len(result['blocks'])+1, flagged=bool(b['_flags']), flags=sorted(set(b['_flags']))))
    for a,b in zip(all_blocks, all_blocks[1:]):
        pa,pb = page_data[a['page']],page_data[b['page']]
        body = pb['body']; last,first = a['_rows'][-1],b['_rows'][0]
        same_page = a['page'] == b['page']; same_col = same_page and a['_column'] == b['_column']
        transitions = ['same_column' if same_col else 'next_column' if same_page else 'next_page']
        crossed = []
        for pn in range(a['page'],b['page']+1):
            pd = page_data.get(pn)
            if pd is None: continue
            for f in pd['floats']:
                F=f['box_px']
                if same_page:
                    between = a['box_px'][3] <= F[1] and F[3] <= b['box_px'][1]
                    across = all(min(F[2],c[1]) > max(F[0],c[0]) for c in (a['_column'],b['_column']))
                else:
                    between = (pn != a['page'] or F[1] >= a['box_px'][3]) and (pn != b['page'] or F[3] <= b['box_px'][1])
                    col = a['_column'] if pn == a['page'] else b['_column']
                    across = min(F[2],col[1]) > max(F[0],col[0])
                if between and across: crossed.append(dict(page=pn, id=f['id'], box_px=F))
        if crossed: transitions.append('across_float')
        indent = (first['box_px'][0]-b['_column'][0])/body
        fullness = (last['box_px'][2]-a['_column'][0])/max(1,a['_column'][1]-a['_column'][0])
        distance = first['box_px'][1]-last['box_px'][1] if same_col else None
        between = [dict(f, kind='float') for f in pb['floats']]
        between.extend(dict(id=h['id'], box_px=h['box_px'], kind='heading') for h in all_blocks
                       if h['page'] == b['page'] and h is not a and h is not b and h['_heading'] and not h['_flags'])
        witnesses = body_order_layout_break_witnesses(a, b, b['_starts'], uses_indents, pb['pitch'], between)
        ends = body_order_end_intervals(a, all_blocks, pa['body'])
        # Sample ids/values remain auditable without repeating every row in each edge.
        end_summary = {k:v for k,v in ends.items() if not k.endswith('_samples')}
        end_summary['paragraph_last_count'] = len(ends['paragraph_last_samples'])
        end_summary['continuing_line_count'] = len(ends['continuing_line_samples'])
        full_interval = ends['continuing_line_ends']
        full = bool(full_interval and full_interval[0] <= last['box_px'][2] <= full_interval[1])
        grammar = body_order_grammar(last['text'],first['text'])
        conflict = bool(witnesses and grammar['confirms_continuation'])
        flags = sorted(set(a['_flags']+b['_flags']))
        if conflict: flags.append('layout break witness conflicts with grammatical continuation')
        # A full last line ending inside a sentence before a capital start across a witnessed break: the
        # sentence's continuation is not the next box (AP14 p1: "case-" before a heading,
        # its continuation at the next column head). The copier must find that
        # continuation or flag the stop (lane f5stream R4). Headings end unterminated.
        stop = boundary_witness(last['text'], first['text'])
        if (witnesses and full and not a['_heading'] and boundary_open_end(last['text']) and
                stop['unterminated'] and stop['verdict'] == 'undecided'):
            flags.append('unterminated end at a layout break: continuation not found in the next box')
        geometry = dict(last_line_fullness=fullness, last_line_full=full,
                        next_start_classes=b['_starts']['id'], previous_end_classes=end_summary,
                        next_first_line_indent_em=indent, paper_uses_indents=uses_indents,
                        baseline_gap_px=distance, pitch_px=pb['pitch'], break_witnesses=witnesses,
                        prediction='break' if witnesses else 'continue')
        continuation = 'undecided' if conflict else 'break' if witnesses else 'continue'
        result['edges'].append(dict(source=dict(page=a['page'],id=a['id']), target=dict(page=b['page'],id=b['id']),
            kind='next_page' if not same_page else 'across_float' if crossed else transitions[0],
            transitions=transitions, geometry=geometry, grammar=grammar,
            evidence='both' if grammar['confirms_continuation'] else 'geometry',
            continuation=continuation, statement='layout and grammar disagree; review' if conflict else
                'layout break witnessed' if witnesses else 'stream continues, no break witnessed',
            flagged=bool(flags), flags=flags, order_flagged=bool(a['_flags'] or b['_flags'])))
    result['counts'] = dict(main_boxes=sum(b.get('cls')=='main' for p in pages for b in p.get('main_text',{}).get('blocks',[])),
                           placed=len(result['blocks']), unplaced=len(result['unplaced']), edges=len(result['edges']),
                           flagged_edges=sum(e['flagged'] for e in result['edges']))
    return result


def write_body_order(paper_dir):
    """Replay rule 9 only; do not write to any rules 1-8 record."""
    files = [os.path.join(paper_dir, f) for f in sorted(os.listdir(paper_dir))
             if re.fullmatch(r'page-\d+\.json', f)]
    pages = []
    for f in files:
        with open(f, encoding='utf-8') as stream: pages.append(json.load(stream))
    if any('main_text' not in p for p in pages):
        raise ValueError('rule 9 needs page JSON with rule-6 classifications')
    result = body_reading_order(pages)
    write_json(os.path.join(paper_dir, 'body-order.json'), result, indent=1)
    return result


def sc_main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", help="the page mapper's document map; used only with --label (float-label mode)"); ap.add_argument("--pdf")
    ap.add_argument("--label", default=None, help="float label; omit for the whole page"); ap.add_argument("--page", type=int)
    ap.add_argument("--out", help="output prefix")
    ap.add_argument("--draw-only", action="store_true")
    ap.add_argument("--no-draw", action="store_true", help="write the JSON only, no PNGs")
    ap.add_argument("--paper", default=None, help="rules 6-7: directory of a paper's page-NN.json files; runs the main-text and reading-order rules over them")
    ap.add_argument("--all-pages", action="store_true", help="rules 1-5 on every page of the PDF; --out is then a directory, pages written as page-NN")
    ap.add_argument("--print-lines", action="store_true", help="after the summary line, print every text run of the page")
    ap.add_argument("--authors", action="store_true", help="rule 8: with --pdf and --paper (after rules 6-7), the first text page's title, authors and affiliations, written to authors.json")
    ap.add_argument("--body-order", action="store_true", help="rule 9: replay main-body order from --paper; writes body-order.json only")
    a = ap.parse_args()
    if a.body_order:
        if not a.paper: ap.error("--body-order requires --paper")
        r = write_body_order(a.paper)
        print("rule 9:", r["counts"])
        return 0
    if a.authors:
        r = authors_and_affiliations(a.pdf, a.paper); c = r["checks"]
        order = write_body_order(a.paper)
        print("rule 9:", order["counts"])
        print(f'rule 8: title {"found" if c.get("title_found") else "not found"}; authors {c.get("authors_found", 0)}; affiliations {c.get("affiliations_found", 0)}; ORCID {c.get("authors_with_orcid", 0)}; {c.get("status", "")}; flags {len(r["flags"])}')
        return 0
    if a.paper:
        s = main_text(a.paper, draw=not a.no_draw)
        print(f'body size {s["body_size_px"]}; header band to {s["header_bottom"]}; footer band from {s["footer_top"]}; title {s["title_box_px"]}; authors {s["author_box_px"]}; flags {s["flags"]}')
        for pg in s["pages"]: print(f'  page {pg["page"]:>2}: columns {[[round(x) for x in c] for c in pg["columns"]]}  {dict(pg["counts"])}')
        return 0
    if a.all_pages:   # in one process (the original ran itself per page); each page as --page N, then its drawing
        os.makedirs(a.out, exist_ok=True)
        for n_page in range(1, sc_page_count(a.pdf) + 1):
            rc = sc_page_run(a, n_page, os.path.join(a.out, f"page-{n_page:02d}"), summary_only=True)
            if rc: print(f"page {n_page} failed (rc {rc})"); return rc
        return 0
    n_pages = sc_page_count(a.pdf)
    if a.page is None or not 1 <= a.page <= n_pages: print(f"--page must be 1 to {n_pages} for this PDF (got {a.page})", file=sys.stderr); return 2
    return sc_page_run(a, a.page, a.out)


def sc_page_run(a, page, out, summary_only=False):
    if a.draw_only:
        res = read_json(out + ".json")
        if res.get("pass") == 2:   # the first pass is recomputed for the drawing
            _, part = (load_float(a.map, a.label, page) if a.label else (None, {"page": page, "box_px": res["region_box_px"], "caption_boxes_px": []}))
            res["first_pass_result"] = _box_elements(a.pdf, part, a.label or f"page {page}")
        draw(res, a.pdf, out + ".png"); return 0
    if a.label:
        _, part = load_float(a.map, a.label, page); label = a.label
    else:   # whole page: the region is the page itself, no caption box from the mapper
        part = {"page": page, "box_px": sc_page_box_px(a.pdf, page), "caption_boxes_px": []}; label = f"page {page}"
    R5_BASE.clear()
    res = box_elements(a.pdf, part, label, out_prefix=out)
    fp = res.pop("first_pass_result", None)
    sc_font_metadata(res, pdf_path=a.pdf)
    write_json(out + ".json", res, indent=1)
    if page == 1 and page in R5_BASE:
        # lane r5-line: the first page as built without the lane, for tools/r5_frontcheck.py (title and front matter)
        base = R5_BASE[page]
        for k in ("pass", "art", "order", "first_pass"):
            if k in res: base[k] = res[k]
        sc_font_metadata(base, pdf_path=a.pdf)
        write_json(os.path.join(os.path.dirname(out), "r5base-page-01.json"), base, indent=1)
    if fp is not None: res["first_pass_result"] = fp
    if "error" in res: print(res); return 1
    k = res["counts"]
    print(f'{label} p{page}: angle {res["reading_angle"]}; chars {k["characters_in_region"]} -> in elements {k["characters_in_elements"]} + unpainted {k["characters_unpainted"]}; larger boxes {len(res["blocks"])}; tables {len(res["tables"])}; floats {len(res["floats"])}; lines {k["lines"]}; runs {k["text_runs"]}; rules {k["rules"]}; fills {k["fills"]}; flags {res["flags"]}')
    if a.print_lines and not summary_only:
        for e in res["elements"]:
            if e["kind"] == "text": print(f'  L{e["line"]:>2} {str(e.get("band")):8} {e["text"]!r}')
    if not a.no_draw:
        if res.get("pass") == 2 and fp is None: res["first_pass_result"] = _box_elements(a.pdf, part, label)
        draw(res, a.pdf, out + ".png")
    return 0


if __name__ == "__main__":
    sys.exit(sc_main())
