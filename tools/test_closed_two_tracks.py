"""Rule 3: a closed label/value grid of two tracks (boxer), and the copier's re-proof of it, which takes
its cells as an exact captionless table placed after the paragraph above it in its own column; run with
/usr/bin/python3 -I tools/test_closed_two_tracks.py. Fixtures are synthetic; no paper text."""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("boxer", pathlib.Path(__file__).resolve().parents[1] / "standalone/element_boxer_sc.py")
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)
spec = importlib.util.spec_from_file_location("copy_paper", pathlib.Path(__file__).resolve().parents[1] / "copy_paper.py")
copier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copier)


def text(name, line, box, value="value", size=16):
    return dict(id=name, kind="text", line=line, angle=0, box_px=box,
                text=value, size_px=size, run_size_px=size, char_ids=[])


def rule(name, box):
    return dict(id=name, kind="rule", box_px=box)


def grid(rows=4, top=100, label_w=80, value_x=440, value_w=48, pitch=23, after=True):
    """a label at the left of a 485 px column and a right-aligned value, one row per line; with after, a
    line of the column's prose follows the lower rule (it crosses the white between the tracks)"""
    cells = []
    for r in range(rows):
        y = top + 11 + r * pitch
        cells.append(text(f"label:{r}", r + 10, [0, y, label_w, y + 12], f"Label {r}"))
        cells.append(text(f"value:{r}", r + 10, [value_x, y, value_x + value_w, y + 12], f"{r} items"))
    bottom = top + 11 + rows * pitch + 1
    if after:
        cells.append(text("after", 40, [0, bottom + 14, 480, bottom + 26], "A line of the column's prose after the rule."))
    return cells, [rule("top", [0, top, 485, top + 1.5]), rule("bottom", [0, bottom, 485, bottom + 1.5])]


def cell_ids(cells): return [c["id"] for c in cells if c["id"] != "after"]


class ClosedTwoTracks(unittest.TestCase):
    def test_closed_label_value_grid_is_a_table_in_row_order(self):
        cells, rules = grid()
        out = boxer.closed_two_track_tables(cells, rules, [])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["tracks"], 2); self.assertEqual(out[0]["grid_lines"], 4)
        self.assertEqual(out[0]["members"], cell_ids(cells) + ["top", "bottom"])
        self.assertEqual(out[0]["witness"], ["top", "bottom"])

    def test_tables_from_grid_finds_it(self):
        cells, rules = grid()
        out = boxer.tables_from_grid(cells + rules, boxer.larger_boxes(cells + rules))
        self.assertEqual([t["tracks"] for t in out], [2])
        self.assertTrue(set(cell_ids(cells)) <= set(out[0]["members"]))
        self.assertNotIn("after", out[0]["members"])

    def test_a_column_pair_between_rules_is_not_a_table(self):
        # two prose columns closed by rules: the lines beside the rules have one run on each side of the
        # gutter, so neither crosses the white between the tracks
        cells, rules = grid(label_w=230, value_x=255, value_w=230, after=False)
        cells += [text("above:l", 9, [0, 80, 230, 92]), text("above:r", 9, [255, 80, 485, 92]),
                  text("below:l", 40, [0, 216, 230, 228]), text("below:r", 40, [255, 216, 485, 228])]
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])
        self.assertEqual(boxer.tables_from_grid(cells + rules, boxer.larger_boxes(cells + rules)), [])

    def test_a_grid_with_no_line_beside_its_rules_is_not_proved(self):
        cells, rules = grid(after=False)
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_labels_wider_than_the_white_are_still_a_table(self):
        # the label track (300 px) is wider than the white between the tracks (140 px)
        cells, rules = grid(label_w=300, value_x=440, value_w=40)
        out = boxer.closed_two_track_tables(cells, rules, [])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["members"], cell_ids(cells) + ["top", "bottom"])
        t = out[0]
        self.assertTrue(copier.closed_two_track_grid(dict(elements=cells + rules), t))

    def test_the_line_above_may_be_the_crossing_one(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40, after=False)
        cells.append(text("before", 9, [0, 80, 470, 92], "A line of the column's prose before the rule."))
        self.assertEqual(len(boxer.closed_two_track_tables(cells, rules, [])), 1)

    def test_a_short_neighbour_that_stops_in_the_white_does_not_prove_it(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40, after=False)
        cells.append(text("before", 9, [0, 80, 360, 92], "An introducing line."))
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_a_paragraph_block_above_a_short_introduction_proves_it(self):
        # the grid ends its column: a short last line above, nothing below, but that line's paragraph is
        # as wide as the column, so the white lies inside the column
        cells, rules = grid(label_w=300, value_x=440, value_w=40, after=False)
        cells.append(text("before", 9, [0, 80, 360, 92], "An introducing line."))
        blocks = [dict(id="block:1", members=["para", "before"], box_px=[0, 20, 482, 92])]
        out = boxer.closed_two_track_tables(cells, rules, [], blocks)
        self.assertEqual(len(out), 1)
        self.assertTrue(copier.closed_two_track_grid(dict(elements=cells + rules, blocks=blocks), out[0]))
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules), out[0]))

    def test_column_blocks_beside_a_gutter_do_not_prove_it(self):
        cells, rules = grid(label_w=230, value_x=255, value_w=230, after=False)
        blocks = [dict(id="b:l", members=["x"], box_px=[0, 20, 230, 92]), dict(id="b:r", members=["y"], box_px=[255, 20, 485, 92]),
                  dict(id="b:l2", members=["z"], box_px=[0, 216, 230, 300]), dict(id="b:r2", members=["w"], box_px=[255, 216, 485, 300])]
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, [], blocks), [])

    def test_a_block_holding_the_grid_is_not_its_neighbour(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40, after=False)
        blocks = [dict(id="b:all", members=["label:0", "value:0"], box_px=[0, 20, 485, 300])]
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, [], blocks), [])

    def test_a_drawn_cell_border_between_the_rules_is_another_tables(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40)
        border = rule("border", [400, 101.5, 401.5, 204])
        self.assertEqual(boxer.closed_two_track_tables(cells, rules + [border], []), [])
        t = boxer.closed_two_track_tables(cells, rules, [])[0]
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules + [border]), t))

    def test_a_caption_line_directly_above_is_another_tables(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40)
        cap = text("cap", 9, [0, 80, 470, 92], "Table 7. Counts of the invented things by kind")
        self.assertEqual(boxer.closed_two_track_tables(cells + [cap], rules, []), [])
        t = boxer.closed_two_track_tables(cells, rules, [])[0]
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules + [cap]), t))

    def test_a_caption_block_directly_above_is_another_tables(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40)
        cap = text("cap", 8, [0, 60, 120, 72], "Table 7.")
        sub = text("sub", 9, [0, 80, 300, 92], "Counts of the invented things")
        blocks = [dict(id="b:cap", members=["cap", "sub"], box_px=[0, 60, 300, 92])]
        self.assertEqual(boxer.closed_two_track_tables(cells + [cap, sub], rules, [], blocks), [])
        t = boxer.closed_two_track_tables(cells, rules, [])[0]
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules + [cap, sub], blocks=blocks), t))

    def test_a_prose_line_above_is_not_a_caption(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40)
        intro = text("intro", 9, [0, 80, 470, 92], "The tables below count the invented things.")
        self.assertEqual(len(boxer.closed_two_track_tables(cells + [intro], rules, [])), 1)

    def test_a_header_row_under_its_own_rule_stays_in_the_table(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40, top=123)
        cells += [text("head:l", 9, [0, 106, 120, 118], "Label"), text("head:r", 9, [430, 106, 480, 118], "Count")]
        rules.append(rule("outer", [0, 100, 485, 101.5]))
        out = boxer.closed_two_track_tables(cells, rules, [])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["grid_lines"], 5)
        self.assertEqual(out[0]["witness"], ["outer", "bottom"])

    def test_a_ruled_first_row_under_a_caption_is_another_tables(self):
        # a captioned table whose first row is ruled off: the pair below that row is the table's, the
        # caption stands above the table's top rule
        cells, rules = grid(label_w=300, value_x=440, value_w=40, top=123)
        cells += [text("first:l", 9, [0, 106, 120, 118], "Label first"), text("first:r", 9, [430, 106, 480, 118], "7 items")]
        cap = text("cap", 8, [0, 80, 470, 92], "Table 7. Counts of the invented things by kind")
        rules.append(rule("outer", [0, 100, 485, 101.5]))
        self.assertEqual(boxer.closed_two_track_tables(cells + [cap], rules, []), [])
        nested = dict(tracks=2, angle=0, members=cell_ids(cells)[:8] + ["top", "bottom"])
        self.assertTrue(copier.closed_two_track_grid(dict(elements=cells + rules), nested))
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules + [cap]), nested))

    def test_a_ruled_first_row_without_a_caption_stays_one_table(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40, top=123)
        cells += [text("first:l", 9, [0, 106, 120, 118], "Label first"), text("first:r", 9, [430, 106, 480, 118], "7 items")]
        rules.append(rule("outer", [0, 100, 485, 101.5]))
        out = boxer.closed_two_track_tables(cells, rules, [])
        self.assertEqual([t["grid_lines"] for t in out], [5])

    def test_the_head_rule_walk_stops_at_a_line_across_the_white(self):
        # a prose line between two rules is not a ruled row: the caption above it is not the pair's
        cells, rules = grid(label_w=300, value_x=440, value_w=40, top=123)
        cells.append(text("prose", 9, [0, 106, 480, 118], "A line of the column's prose between the rules."))
        cap = text("cap", 8, [0, 80, 470, 92], "Table 7. Counts of the invented things by kind")
        rules.append(rule("outer", [0, 100, 485, 101.5]))
        out = boxer.closed_two_track_tables(cells + [cap], rules, [])
        self.assertEqual([t["witness"] for t in out], [["top", "bottom"]])

    def test_the_head_rule_walk_needs_the_same_ends(self):
        cells, rules = grid(label_w=300, value_x=440, value_w=40, top=123)
        cells += [text("first:l", 9, [0, 106, 120, 118], "Label first"), text("first:r", 9, [430, 106, 480, 118], "7 items")]
        cap = text("cap", 8, [0, 80, 470, 92], "Table 7. Counts of the invented things by kind")
        rules.append(rule("outer", [0, 100, 300, 101.5]))
        out = boxer.closed_two_track_tables(cells + [cap], rules, [])
        self.assertEqual([t["witness"] for t in out], [["top", "bottom"]])

    def test_tracks_that_overlap_are_not_two_tracks(self):
        cells, rules = grid(label_w=300, value_x=280, value_w=100)
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_one_rule_is_not_enough(self):
        cells, rules = grid()
        self.assertEqual(boxer.closed_two_track_tables(cells, rules[:1], []), [])

    def test_rules_with_different_ends_are_not_a_pair(self):
        cells, rules = grid()
        rules[1]["box_px"] = [0, rules[1]["box_px"][1], 300, rules[1]["box_px"][3]]
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_a_line_with_one_run_between_the_rules_blocks_it(self):
        cells, rules = grid()
        cells = [c for c in cells if c["id"] != "value:2"]
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_a_line_with_three_runs_blocks_it(self):
        cells, rules = grid()
        cells.append(text("extra", 11, [200, 134, 260, 146], "middle"))
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_rules_that_do_not_close_the_lines_are_not_enough(self):
        # more than a letter height of white between the upper rule and the first line
        cells, rules = grid()
        rules[0]["box_px"] = [0, 60, 485, 61.5]
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_a_single_row_is_not_a_grid(self):
        cells, rules = grid(rows=1)
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, []), [])

    def test_runs_or_rules_already_in_a_table_are_left_alone(self):
        cells, rules = grid()
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, [dict(members=["label:0"])]), [])
        self.assertEqual(boxer.closed_two_track_tables(cells, rules, [dict(members=["top"])]), [])

    def test_text_beside_the_rules_is_not_counted(self):
        # the other page column's prose on the same lines lies outside the rules' width
        cells, rules = grid()
        beside = [text(f"prose:{r}", r + 10, [-520, 111 + r * 23, -35, 123 + r * 23], "A line of prose in the other column.")
                  for r in range(4)]
        out = boxer.closed_two_track_tables(cells + beside, rules, [])
        self.assertEqual(len(out), 1)
        self.assertFalse(any(m.startswith("prose") for m in out[0]["members"]))


class CopierProof(unittest.TestCase):
    def table(self, cells, rules):
        return boxer.closed_two_track_tables(cells, rules, [])[0]

    def test_the_boxer_table_is_re_proved(self):
        cells, rules = grid()
        t = self.table(cells, rules)
        self.assertTrue(copier.closed_two_track_grid(dict(elements=cells + rules), t))

    def test_three_tracks_are_not_this_rule(self):
        cells, rules = grid()
        t = dict(self.table(cells, rules), tracks=3)
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules), t))

    def test_text_added_between_the_rules_breaks_the_proof(self):
        cells, rules = grid()
        t = self.table(cells, rules)
        extra = text("note", 30, [200, 150, 260, 162], "note")
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules + [extra]), t))

    def test_overlapping_tracks_break_the_proof(self):
        cells, rules = grid()
        t = self.table(cells, rules)
        moved = [dict(e, box_px=[60, e["box_px"][1], 108, e["box_px"][3]]) if e["id"].startswith("value") else e for e in cells]
        self.assertFalse(copier.closed_two_track_grid(dict(elements=moved + rules), t))

    def test_a_neighbour_that_no_longer_crosses_the_white_breaks_the_proof(self):
        cells, rules = grid()
        t = self.table(cells, rules)
        short = [dict(e, box_px=[0, e["box_px"][1], 200, e["box_px"][3]]) if e["id"] == "after" else e for e in cells]
        self.assertFalse(copier.closed_two_track_grid(dict(elements=short + rules), t))

    def test_a_far_rule_breaks_the_proof(self):
        cells, rules = grid()
        t = self.table(cells, rules)
        rules[1]["box_px"] = [0, 260, 485, 261.5]
        self.assertFalse(copier.closed_two_track_grid(dict(elements=cells + rules), t))

    def test_rows_are_label_and_value(self):
        cells, rules = grid()
        cells = [c for c in cells if c["id"] != "after"]
        rows, notes = copier.table_rows(cells, 16, dict(page=1, elements=cells + rules, main_text=dict(blocks=[], columns=[[0, 485]], body_size_px=16)))
        self.assertEqual([[" ".join(c) for c in r] for r in rows], [[f"Label {i}", f"{i} items"] for i in range(4)])


def frame_page(caption_inside=True, note=True, first="Table 9"):
    """a closed frame (two side rules, top, header and bottom rules) holding two columns; the caption is
    the frame's first line (caption_inside) or sits above it; a source line in the table's type follows"""
    es = []
    for x in (0, 400):
        es.append(dict(id=f"side:{x}", kind="rule", box_px=[x, 20, x + 1.5, 200]))
    for y in (20, 70, 200):
        es.append(dict(id=f"bar:{y}", kind="rule", box_px=[0, y, 401.5, y + 1.5]))
    def t(i, txt, x, y, w, size=8):
        return dict(id=f"run:{i}", kind="text", angle=0, line=i, box_px=[x, y, x + w, y + 9], text=txt,
                    size_px=size, run_size_px=size, char_ids=[])
    cap_y = 26 if caption_inside else 4
    es.append(t(1, first, 10, cap_y, 40))
    es.append(t(2, "Invented things by kind", 10, cap_y + 14, 150))
    rows = [("Kind", "Description")] + [(str(k), f"An invented description number {k}") for k in range(4)]
    for k, (a, b) in enumerate(rows):
        y = 76 + k * 24
        es.append(t(10 + 2 * k, a, 10, y, 30)); es.append(t(11 + 2 * k, b, 120, y, 220))
    if note:
        es.append(t(40, "Drawn from an invented source volume, with permission.", 0, 206, 300))
    es.append(t(50, "A paragraph of the page's body text in its larger face follows the table here.", 0, 240, 400, size=10))
    return dict(page=1, elements=es, tables=[], floats=[], blocks=[], art=[],
                region_box_px=[0, 0, 600, 600], main_text=dict(blocks=[], columns=[[0, 600]]))


class FrameCaption(unittest.TestCase):
    def caps(self, p):
        return [e for e in p["elements"] if e["kind"] == "text" and e["text"].startswith("Table")]

    def test_a_caption_opening_the_frame_is_its_caption(self):
        p = frame_page()
        copier.recover_bordered_table_regions(p, self.caps(p), 10)
        self.assertEqual(len(p["floats"]), 1)
        self.assertEqual(p["floats"][0]["_caption_ids"][:1], ["run:1"])
        self.assertNotIn("no caption", p["floats"][0]["caption"])
        members = set(p["tables"][0]["members"])
        self.assertNotIn("run:1", members)
        self.assertIn("run:40", members)        # the source line under the frame is its note
        self.assertNotIn("run:50", members)     # body text in the larger face is not

    def test_a_frame_whose_first_line_is_not_a_caption_stays_captionless(self):
        p = frame_page(first="Kinds")
        copier.recover_bordered_table_regions(p, self.caps(p), 10)
        self.assertEqual([f["caption"] for f in p["floats"]], ["Table (no caption on page 1; boxed)"])
        self.assertNotIn("run:40", p["tables"][0]["members"])   # unmarked line under a captionless frame

    def test_a_caption_after_other_text_in_the_frame_does_not_open_it(self):
        p = frame_page()
        p["elements"].append(dict(id="run:60", kind="text", angle=0, line=60, box_px=[200, 22, 260, 31], text="Panel",
                                  size_px=8, run_size_px=8, char_ids=[]))
        p["elements"] = [dict(e, box_px=[e["box_px"][0], 34, e["box_px"][2], 43]) if e["id"] == "run:1" else e for e in p["elements"]]
        copier.recover_bordered_table_regions(p, self.caps(p), 10)
        self.assertTrue(all("no caption" in f["caption"] for f in p["floats"]))

    def test_a_caption_above_the_frame_is_read_as_before(self):
        p = frame_page(caption_inside=False)
        copier.recover_bordered_table_regions(p, self.caps(p), 10)
        self.assertEqual(p["floats"][0]["_caption_ids"][:1], ["run:1"])


if __name__ == "__main__":
    unittest.main()
