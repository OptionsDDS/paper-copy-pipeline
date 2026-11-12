# Line map: Claude maps a paper by line IDs; the program assembles the copy

## lines.json (written by tools/export_lines.py from a copy run's page records)
{"paper": "AF02", "pages": [{"page": 1, "width_px": W, "height_px": H, "image": "<path of the page image the mapper sees>",
  "lines": [{"id": "p1.l017", "text": "<the line's text after the program's glyph decoding, exactly as the copy would print it>", "box": [x0,y0,x1,y1], "size": <font px>, "bold": true|false, "italic": true|false, "program_role": "<the role the program currently gives it: body, heading, caption, table, furniture, front, reference, figure_text, footnote, ...>"}]}]}
Every printed text line of the PDF's text layer (or OCR layer on scans) appears exactly once with a stable id. Text inside raster images is not a line.

## map.json (written by the mapper; refers to line ids only, never writes text)
{"paper": "AF02", "front": {"title": [ids], "subtitle": [ids], "authors": [ids], "affiliations": [[ids], ...], "article_info": [[ids], ...], "abstract": [ids], "keywords": [ids]},
 "body": [ {"kind": "heading", "level": 2|3, "lines": [ids]},
           {"kind": "paragraph", "lines": [ids]},
           {"kind": "list_item", "lines": [ids]},
           {"kind": "caption", "of": "Figure 2"|"Table 1", "lines": [ids]},
           {"kind": "table", "caption": [ids], "rows": [[[ids of cell 1], [ids of cell 2], ...], ...], "header_rows": n, "notes": [[ids], ...]},
           {"kind": "table_lines", "caption": [ids], "lines": [ids], "reason": "<why rows cannot be given>"},
           {"kind": "formula", "lines": [ids]},
           {"kind": "footnote", "lines": [ids]},
           {"kind": "box", "title": [ids], "items": [[ids], ...]} ],
 "references": [[ids], ...],
 "end_matter": [{"label": "<e.g. Acknowledgments>", "lines": [ids]}],
 "furniture": {"running_head": [ids], "page_number": [ids], "figure_text": [ids], "watermark": [ids], "licence": [ids], "other": [ids]},
 "split_lines": [{"id": "p3.l040", "at": "<exact text where the second part starts>", "new_ids": ["p3.l040a", "p3.l040b"]}],
 "notes": ["<anything the mapper could not decide, with page>"]}
Order: body items in reading order across the whole paper; a paragraph that continues over a column or page lists all its lines in order. A line that holds two things printed side by side (two columns merged by the text layer) is split first with split_lines (at a word boundary; the two parts then get the new ids). Every line id is used exactly once in front, body, references, end_matter or furniture.

## Assembly (tools/assemble_map.py)
Writes copy.md from lines.json + map.json with the copy program's existing conventions (title "# ", headings "## "/"### ", captions bold, Markdown tables with spanning headers repeated, notes below, references one per line, Article information, the "Places the program is not sure of" list including the mapper's notes); paragraph lines joined with the program's hyphen policy; furniture omitted and listed by count in copy.linemap.json. Conservation: every line id used exactly once (after splits); unused or twice-used ids are an error and the copy is not written. Tables: cell text is the cells' line texts joined; a "table" whose cells cannot be filled from whole lines is printed as table_lines.
