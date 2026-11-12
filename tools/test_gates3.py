"""Native rotated gate baselines and capitalized wrapped labels."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

spec = importlib.util.spec_from_file_location('rows', Path(__file__).with_name('test_rows2.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
c, run = m.c, m.run


class Gates(unittest.TestCase):
    def test_invisible_clip_only_and_fully_clipped_text_never_reach_copy(self):
        spec = importlib.util.spec_from_file_location('gate_pdf', Path(__file__).with_name('test_ocrscan.py'))
        fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
        content = ('BT /F 8 Tf 10 80 Td (Printed) Tj ET '
                   'q BT /F 8 Tf 3 Tr 10 60 Td (Ghost) Tj ET Q '
                   'q BT /F 8 Tf 7 Tr 10 40 Td (ClipOnly) Tj ET Q '
                   'q 0 0 2 2 re W n BT /F 8 Tf 10 20 Td (Clipped) Tj ET Q')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            pdf = Path(temp)/'paint.pdf'; fixture.pdf(pdf,content)
            p = dict(page=1, region_box_px=[0,0,209,209], _table_pdf=str(pdf), elements=[])
            chars = c.table_characters(p); groups = {}
            for i,ch in enumerate(chars): groups.setdefault(ch['paint_order'][0],[]).append(i)
            for key,ids in groups.items():
                cs = [chars[i] for i in ids]
                p['elements'].append(dict(id=str(key),kind='text',text=''.join(ch['text'] for ch in cs),
                                          char_ids=ids,_chars=cs))
            c.omit_unpainted_text([p])
            self.assertEqual([e['text'] for e in p['elements'] if e['text']], ['Printed'])

    def labels(self, new_reference=False, new_list=False, gap=15):
        rs = [run('Material', 5, 0, 130), run('Advantages', 180, 0, 120), run('Sources', 350, 0)]
        rs += [run('Synthetic membrane,', 5, 25, 130), run('- First property', 180, 25, 120), run('[12]', 350, 25)]
        rs += [run('expanded form, dense', 5, 40, 130), run('- Second property', 180, 40, 120)]
        rs += [run('ABC film', 5, 40+gap, 130), run('- Third property', 180, 40+gap, 120)]
        if new_reference: rs.append(run('[13]', 350, 40+gap))
        if new_list: rs[-1]['text'] = 'Independent observation'
        rs += [run('Another material', 5, 100, 130), run('- Another property', 180, 100, 120), run('[14]', 350, 100)]
        return rs

    def test_capital_finishes_wrapped_label_in_each_frame(self):
        for angle in (0, 90, 270):
            rs = self.labels()
            for e in rs: e.update(angle=angle, box_px=c.frame(-angle)(e['box_px']))
            rows, _ = c.table_rows(rs, 10)
            self.assertTrue(any(row[0] == ['Synthetic membrane,', 'expanded form, dense', 'ABC film'] for row in rows))
            self.assertTrue(any(row[0] == ['Another material'] for row in rows))

    def test_new_reference_value_or_gap_still_opens_row(self):
        for kwargs in (dict(new_reference=True), dict(new_list=True), dict(gap=35)):
            rows, _ = c.table_rows(self.labels(**kwargs), 10)
            self.assertTrue(any(row[0] == ['ABC film'] for row in rows), kwargs)

    def glyph(self, text, u, v, angle):
        box = c.frame(-angle)([u, v, u+5, v+10])
        origin = c.frame(-angle)([u, v+10, u, v+10])[:2]
        advance = c.frame(-angle)([u+5, v+10, u+5, v+10])[:2]
        return dict(text=text, x0=box[0], y0=box[1], x1=box[2], y1=box[3],
                    origin=origin, adv_x1=advance[0], adv_y1=advance[1], size=10, hidden=False)

    def test_scrambled_runs_and_split_decimal_use_native_positions(self):
        for angle in (90, 270):
            # A saved run mixes two baselines; the final decimal digit is in
            # the other run. Native glyph positions, not strings, prove order.
            a = [self.glyph(t, u, v, angle) for t,u,v in [('B',0,20),('7',20,0),('2',25,0),('.',30,0),('A',0,0)]]
            b = [self.glyph('8',35,0,angle), self.glyph('2',20,20,angle)]
            rs = [dict(id=str(i), text=''.join(x['text'] for x in cs), _chars=cs) for i,cs in enumerate((a,b))]
            lines = c.native_table_lines(rs, dict(_table_native_angles={angle}), angle)
            self.assertEqual([line['text'] for line in lines], ['A 72.8', 'B 2'])
            rs[0]['text'] = 'unverified'
            self.assertIsNone(c.native_table_lines(rs, dict(_table_native_angles={angle}), angle))

    def test_native_reordering_requires_proven_overlay(self):
        self.assertIsNone(c.native_table_lines([], {}, 90))

    def test_small_dark_or_noncollinear_labels_are_not_watermarks(self):
        for change in ({}, dict(size=15), dict(fill_color=0, render_mode=0), dict(wobble=True)):
            ordinary = [dict(size=10, angle=90) for i in range(30)]
            large = [dict(text=chr(65+i), size=60, angle=142, fill_color=.9,
                          render_mode=0, origin=(i*10, i*10+(20 if change.get('wobble') and i==3 else 0)),
                          font='Display', **{k:v for k,v in change.items() if k not in ('wobble','size','fill_color','render_mode')}) for i in range(8)]
            for glyph in large: glyph.update({k:v for k,v in change.items() if k!='wobble'})
            chars = ordinary+large
            p = dict(_table_chars=chars, tables=[dict(angle=90)], region_box_px=[0,0,100,100], elements=[])
            c.omit_rotated_table_watermarks(p)
            self.assertEqual(bool(p.get('_table_native_angles')), not bool(change))


    def test_gate_coverage_counts_native_lines_and_ignores_empty_omissions(self):
        angle = 90
        a = [self.glyph(t, u, v, angle) for t,u,v in [('B',0,20),('7',20,0),('2',25,0),('.',30,0),('A',0,0)]]
        b = [self.glyph('8',35,0,angle), self.glyph('2',20,20,angle)]
        rs = [dict(id=str(i), kind='text', text=''.join(x['text'] for x in cs), _chars=cs,
                   angle=angle, run_size_px=10, char_ids=[],
                   box_px=c.hull([x['x0'],x['y0'],x['x1'],x['y1']] for x in cs))
              for i,cs in enumerate((a,b))]
        rs.append(dict(id='omitted', kind='text', text='', _chars=[], angle=angle,
                       box_px=c.frame(-angle)([5,5,10,15]), run_size_px=60, char_ids=[]))
        p = dict(page=1, elements=rs, tables=[], floats=[], blocks=[], main_text={},
                 _table_chars=[], _table_native_angles={angle})
        source = c.table_source(rs, p)
        items = [dict(kind='table', page=1, id='table', caption='Table 1. Example',
                      table_source=source, rows=[], notes=[], box=c.hull(e['box_px'] for e in rs))]
        rec = c.gate_tables(items, [p], [])[0]
        self.assertEqual(rec['printed_lines'], ['A 72.8', 'B 2'])
        self.assertEqual(rec['region_coverage']['page_line_count'], 2)
        self.assertEqual(rec['region_coverage']['missing_frame_line_count'], 0)
        self.assertEqual(rec['region_coverage']['missing_output_line_count'], 0)

    def test_reordered_run_needs_every_replacement_line_for_conservation(self):
        spec = importlib.util.spec_from_file_location('gate_conserve', Path(__file__).with_name('conserve.py'))
        conserve = importlib.util.module_from_spec(spec); spec.loader.exec_module(conserve)
        cs = [self.glyph('B',0,20,90), self.glyph('A',0,0,90)]
        rs = [dict(id='mixed', text='BA', _chars=cs)]
        page = dict(_table_native_angles={90})
        self.assertEqual([line['text'] for line in c.native_table_lines(rs,page,90)], ['A','B'])
        self.assertTrue(c.positioned_run_placed(rs[0],page,conserve.CopyIndex('A\nB')))
        self.assertFalse(c.positioned_run_placed(rs[0],page,conserve.CopyIndex('A')))

    def test_overlay_boxes_do_not_exempt_underlying_values_from_conservation(self):
        spec = importlib.util.spec_from_file_location('gate_conserve', Path(__file__).with_name('conserve.py'))
        conserve = importlib.util.module_from_spec(spec); spec.loader.exec_module(conserve)
        box = [0,0,100,100]
        page = dict(copy_conservation=dict(excluded=[]), copy_omitted=[
            dict(run='overlay', before='X', after='', invisible=[dict(text='X',box=box)],
                 overlay=True, why='diagonal watermark'),
            dict(run='white', before='Ghost', after='', invisible=[], why='white text')])
        c.record_copy_omissions(page, [dict(id='overlay',box_px=box),dict(id='white',box_px=[200,0,240,10])])
        evidence = page['copy_conservation']
        self.assertEqual([e['text'] for e in evidence['omitted_overlays']], ['X'])
        self.assertEqual([e['text'] for e in evidence['excluded']], ['Ghost'])
        self.assertIsNone(conserve.covered(dict(text='72.8',box=[10,10,20,20]), evidence['excluded'],1,1))

    def test_native_word_order_uses_origins_not_italic_overhang(self):
        for angle in (90,270):
            cs = [self.glyph('A',0,0,angle), self.glyph('B',5,0,angle)]
            box = c.frame(-angle)([-1,0,10,10])
            cs[1].update(x0=box[0],y0=box[1],x1=box[2],y1=box[3])
            lines = c.native_table_lines([dict(id='word',text='AB',_chars=cs)],
                                         dict(_table_native_angles={angle}),angle)
            self.assertEqual([line['text'] for line in lines], ['AB'])


if __name__ == '__main__': unittest.main()
