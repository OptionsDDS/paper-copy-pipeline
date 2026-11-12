"""Rule-3 region contracts; run with /usr/bin/python3 -I tools/test_table_regions.py."""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("boxer", pathlib.Path(__file__).resolve().parents[1] / "standalone/element_boxer_sc.py")
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)


def text(name, line, box, value="value", size=10):
    return dict(id=name, kind="text", line=line, angle=0, box_px=box,
                text=value, size_px=size, run_size_px=size, char_ids=[])


def rule(name, box):
    return dict(id=name, kind="rule", box_px=box)


class TableRegions(unittest.TestCase):
    def test_shaded_caption_bounds_small_alternating_rows_before_chart(self):
        cap=text('cap',0,[5,2,105,12],'Table 8 Observations',size=14)
        cells=[text(f'c{r}{c}',r+1,[5+70*c,22+20*r,35+70*c,32+20*r]) for r in range(3) for c in range(2)]
        fills=[dict(id=f'f{i}',kind='fill',box_px=b) for i,b in enumerate([[0,0,140,15],[0,15,140,35],[0,55,140,75],[0,90,140,200]])]
        blocks=[dict(id='original',members=['cap'],box_px=cap['box_px'],text_lines=1,text=cap['text'])]
        old=[dict(id='table:1',box_px=[0,0,140,200],members=[e['id'] for e in cells])]
        result=boxer.tables_from_caption_bands([cap]+cells+fills,blocks,old)
        self.assertEqual(len(result),1);self.assertEqual(result[0]['box_px'],[0,15,140,75])
        self.assertEqual(old,[]);self.assertTrue(boxer.is_caption_run(cap))
        floats=boxer.floats_with_captions([cap]+cells+fills,blocks,result)
        self.assertTrue(any(f['caption']==cap['text'] and result[0]['id'] in f['blocks'] for f in floats))
        self.assertEqual(set(result[0]['members']) & {e['id'] for e in cells},{e['id'] for e in cells})

    def test_shaded_body_reference_is_not_enough(self):
        cap=text('cap',0,[5,2,105,12],'Table 8 explains these results')
        prose=[text(f'p{i}',i+1,[5,22+20*i,135,32+20*i],'A complete body sentence continues here.') for i in range(3)]
        fills=[dict(id=f'f{i}',kind='fill',box_px=[0,y,140,y+20]) for i,y in enumerate([0,20,40,60])]
        self.assertFalse(boxer.tables_from_caption_bands([cap]+prose+fills,[],[]))

    def setUp(self):
        self.cells = [text(f"cell:{r}:{c}", r, [10 + c * 50, 20 + r * 20, 40 + c * 50, 30 + r * 20])
                      for r in range(3) for c in range(3)]
        self.table = dict(box_px=[0, 0, 160, 100], angle=0, members=[e["id"] for e in self.cells])

    def test_prose_gutters_and_header_do_not_make_a_grid(self):
        drawings = [rule("top", [0, 0, 160, 1]), rule("gutter1", [50, 15, 51, 100]), rule("gutter2", [100, 15, 101, 100])]
        self.assertFalse(boxer.table_grid_supported(self.table, self.cells + drawings))

    def test_two_boundaries_enclose_real_rows(self):
        drawings = [rule("top", [0, 10, 160, 11]), rule("bottom", [0, 90, 160, 91])]
        self.assertTrue(boxer.table_grid_supported(self.table, self.cells + drawings))

    def test_footer_rules_enclosing_only_one_line_are_not_a_grid(self):
        drawings = [rule("top", [0, 32, 160, 33]), rule("bottom", [0, 58, 160, 59])]
        self.assertFalse(boxer.table_grid_supported(self.table, self.cells + drawings))

    def test_boundary_with_joined_interior_divider(self):
        drawings = [rule("top", [0, 10, 160, 11]), rule("divider", [51, 11, 52, 90])]
        self.assertTrue(boxer.table_grid_supported(self.table, self.cells + drawings))

    def test_caption_can_anchor_a_partial_grid(self):
        caption = text("caption", -1, [0, -20, 50, -10], "TABLE 1")
        self.assertTrue(boxer.table_grid_supported(self.table, self.cells + [caption]))

    def test_repeated_shaded_rows_keep_continued_tables(self):
        cells = [text(f"cell:{r}:{c}", r, [10+c*50, 20+r*15, 40+c*50, 30+r*15])
                 for r in range(6) for c in range(3)]
        table = dict(self.table, box_px=[0, 10, 160, 115], members=[e["id"] for e in cells])
        bands = [dict(id=f"band:{i}", kind="fill", box_px=[0, y, 160, y+35]) for i,y in enumerate([15, 75])]
        self.assertTrue(boxer.table_grid_supported(table, cells + bands))
        self.assertFalse(boxer.table_grid_supported(table, cells + bands[:1]))

    def test_split_caption_and_two_column_list_preserve_characters(self):
        es = [text("label", 0, [0, 0, 35, 10], "TABLE"), text("number", 0, [40, 0, 45, 10], "1"),
              text("title", 0, [55, 0, 250, 10], "Clinical indicators")]
        es += [text(f"item:{r}:{c}", r+1, [c*140+5, 30+r*20, c*140+100, 40+r*20], f"{r+1+c*3}. Entry")
               for r in range(3) for c in range(2)]
        es += [text("prose", 5, [0, 110, 250, 120], "An ordinary following paragraph.")]
        blocks = boxer.larger_boxes(es)
        original = [(e["id"], e["text"], list(e["char_ids"])) for e in es]
        decisions = []
        tables = boxer.tables_from_caption_list(es, [], blocks, decisions)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["tracks"], 2)
        self.assertEqual({m for m in tables[0]["members"]}, {e["id"] for e in es if e["id"].startswith("item:")})
        self.assertEqual([(e["id"], e["text"], e["char_ids"]) for e in es], original)
        self.assertTrue(boxer.is_caption_run(es[0]))
        self.assertTrue(decisions)

    def test_list_without_caption_is_not_a_table(self):
        es = [text(str(r), r, [0, r*20, 200, r*20+10], f"{r+1}. Entry") for r in range(4)]
        self.assertEqual(boxer.tables_from_caption_list(es, []), [])

    def test_refused_candidate_has_a_reason_and_box(self):
        es = self.cells + [rule("header", [0, 15, 160, 16]), rule("gutter1", [50, 25, 51, 90]), rule("gutter2", [100, 25, 101, 90])]
        decisions = []
        tables = boxer.tables_from_grid(es, boxer.larger_boxes(es), decisions)
        self.assertEqual(tables, [])
        self.assertTrue(any(d["why"].startswith("refused:") and len(d["box_px"]) == 4 for d in decisions))


if __name__ == "__main__":
    unittest.main()
