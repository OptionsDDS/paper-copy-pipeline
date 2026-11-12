"""A definition crossing row labels is one cell or an explicit gate failure."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width=100):
    return dict(id=f'{x}:{y}:{text}',kind='text',text=text,angle=0,line=y,
                box_px=[x,y,x+width,y+10],char_ids=[])


def example():
    rs=[run('Item',0,0,30),run('Definition',100,0),
        run('1',0,25,10),run('A component includes the following',100,25),
        run('2',0,40,10),run('parts and related fittings',115,40),
        run('3',0,55,10),run('4',0,70,10),run('Another group',100,70)]
    rows=[c.TableRow([['Item'],['Definition']]),
          c.TableRow([['1'],['A component includes the following']]),
          c.TableRow([['2'],['parts and related fittings']]),
          c.TableRow([['3'],[]]),c.TableRow([['4'],['Another group']])]
    return rows,rs


class SpanningCells(unittest.TestCase):
    def test_row_assembly_preserves_a_definition_across_numbered_entries(self):
        rs=[run('Item',5,0,40),run('Description',100,0),run('Definition',300,0,220)]
        for i,y in enumerate([25,45,65,85,105],1):
            rs.extend([run(str(i),5,y,10),run('Entry '+str(i),100,y,90)])
        rs.extend([run('A component includes the following',300,25,220),
                   run('parts and related fittings',315,40,200),
                   run('Another separate definition',300,105,220)])
        page=dict(elements=rs+[dict(kind='fill',box_px=[0,-5,550,18]),
                               dict(kind='rule',box_px=[0,125,550,125])])
        rows,notes=c.table_rows(rs,10,page)
        self.assertFalse(notes)
        self.assertEqual(rows[1][2],['A component includes the following','parts and related fittings'])
        self.assertEqual(rows[1].row_spans,{2:dict(start=1,end=4)})
        self.assertTrue(all(not r[2] for r in rows[2:5]))
        self.assertFalse(c.table_structure_checks(rows,c.table_source(rs,page),
                         'Table 1. Components',notes)['sentence_span']['fired'])

    def test_populated_first_column_cannot_hide_a_cut_sentence(self):
        rows,rs=example()
        checks=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),'Table 1. Components',[])
        self.assertTrue(checks['sentence_span']['fired'])

    def test_complete_span_once_with_empty_following_cells_at_all_angles(self):
        rows,rs=example()
        for angle in (0,90,180,270):
            grid=copy.deepcopy(rows)
            turned=[dict(r,angle=angle,box_px=c.frame(-angle)(r['box_px'])) for r in rs]
            source=c.table_source(turned,dict(elements=turned))
            c.restore_table_row_spans(grid,source)
            self.assertEqual(grid[1][1],rows[1][1]+rows[2][1])
            self.assertEqual(grid[2][1],[])
            self.assertEqual(grid[1].row_spans,{1:dict(start=1,end=3)})
            self.assertFalse(c.table_structure_checks(grid,source,'Table 1. Components',[])['sentence_span']['fired'])
            class Joiner:
                def lines(self,parts):return ' '.join(parts)
            text='\n'.join(c.table_markdown(grid,Joiner()))
            self.assertEqual(text.count('(spans rows 1-3)'),1)
            self.assertEqual(text.count('parts and related fittings'),1)

    def test_unknown_geometry_must_gate_instead_of_guessing_a_span(self):
        rows,rs=example();rs[5]['text']='Unrelated source fragment'
        source=c.table_source(rs,dict(elements=rs));c.restore_table_row_spans(rows,source)
        self.assertFalse(rows[1].row_spans)
        item=dict(kind='table',page=1,caption='Table 1. Components',rows=rows,notes=[],table_source=source)
        record=c.gate_tables([item],[dict(page=1,elements=rs)],[])[0]
        self.assertIn('sentence_span',record['fired'])
        self.assertEqual(record['decision'],'printed_lines')

    def test_borders_and_nonhanging_entries_veto_repair(self):
        for border in (False,True):
            rows,rs=example()
            graphics=[dict(kind='rule',box_px=[90,38,220,38])] if border else []
            if not border:rs[5]['box_px']=[100,40,200,50]
            source=c.table_source(rs,dict(elements=rs+graphics))
            c.restore_table_row_spans(rows,source)
            self.assertFalse(rows[1].row_spans)
            self.assertEqual(c.table_structure_checks(rows,source,'Table 1. Components',[])['sentence_span']['fired'],not border)

    def test_punctuation_capitals_bullets_and_short_values_are_entries(self):
        for previous,current in [('A component includes the following.','parts and related fittings'),
                                 ('A component includes the following','Parts and related fittings'),
                                 ('A component includes the following','• parts and related fittings'),
                                 ('A component includes the following','a) parts and related fittings'),
                                 ('A component includes the following','xABC membrane for another intervention'),
                                 ('A component includes the following','x'),
                                 ('red','light blue')]:
            rows,rs=example();rows[1][1]=[previous];rows[2][1]=[current]
            self.assertEqual(c.table_sentence_spans(rows,c.table_source(rs,dict(elements=rs))),[])

    def test_separated_lowercase_observations_are_not_a_sentence(self):
        rows,rs=example();rs[5]['box_px']=[115,65,215,75]
        self.assertEqual(c.table_sentence_spans(rows,c.table_source(rs,dict(elements=rs))),[])
        rows[1][1]=['buccal (40%), lingual (60%)'];rows[2][1]=['buccal (80%), lingual (20%)']
        self.assertEqual(c.table_sentence_spans(rows,c.table_source(rs,dict(elements=rs))),[])
        rows[1][1]=['An observation has several descriptive words'];rows[2][1]=['na']
        self.assertEqual(c.table_sentence_spans(rows,c.table_source(rs,dict(elements=rs))),[])

    def test_shaded_header_edge_establishes_a_new_cell(self):
        rows,rs=example()
        source=c.table_source(rs,dict(elements=rs+[dict(kind='fill',box_px=[90,20,220,38])]))
        self.assertEqual(c.table_sentence_spans(rows,source),[])

    def test_multilevel_header_is_not_a_data_entry_or_a_span_row_number(self):
        rows,rs=example()
        rows.insert(1,c.TableRow([['Subheading'],['A description of the result']],header=True))
        rs.extend([run('Subheading',0,12,40),run('A description of the result',100,12)])
        source=c.table_source(rs,dict(elements=rs));c.restore_table_row_spans(rows,source)
        self.assertEqual(rows[2].row_spans,{1:dict(start=1,end=3)})
        rows[2][1]=['an independent lowercase entry']
        self.assertFalse(c.table_sentence_spans(rows,source))

    def test_identifiers_and_repeated_category_values_are_not_sentences(self):
        rows,rs=example()
        for above,current in [('id123 id234 id345','id456 id567 id678'),
                              ('a recurrent category value','a recurrent category value')]:
            rows[1][1]=[above];rows[2][1]=[current]
            self.assertEqual(c.table_sentence_spans(rows,c.table_source(rs,dict(elements=rs))),[])

    def test_all_locations_of_repeated_phrases_respect_the_source_gap(self):
        rows,rs=example();rs[5]['box_px']=[115,100,215,110]
        rs.append(run('parts and related fittings',115,200))
        self.assertEqual(c.table_sentence_spans(rows,c.table_source(rs,dict(elements=rs))),[])
        rs[5]['box_px']=[115,40,215,50]
        source=c.table_source(rs,dict(elements=rs))
        self.assertEqual(len(c.table_sentence_spans(rows,source)),1)
        c.restore_table_row_spans(rows,source)
        self.assertEqual(rows[1].row_spans,{1:dict(start=1,end=3)})

    def test_group_boundary_and_new_entry_stop_empty_tail(self):
        rows,rs=example();rows[3]=c.TableRow([['Next section'],[]],group=True)
        rs[6]['text']='Next section'
        c.restore_table_row_spans(rows,c.table_source(rs,dict(elements=rs)))
        self.assertEqual(rows[1].row_spans,{1:dict(start=1,end=2)})

    def test_chain_of_three_fragments_is_joined_once(self):
        rows,rs=example();rows[3][1]=['and all their accessories']
        rs.append(run('and all their accessories',115,55))
        c.restore_table_row_spans(rows,c.table_source(rs,dict(elements=rs)))
        self.assertEqual(len(rows[1][1]),3)
        self.assertEqual(rows[1].row_spans,{1:dict(start=1,end=3)})
        self.assertFalse(rows[2][1] or rows[3][1] or rows[2].row_spans)

    def test_panel_boundary_cannot_extend_the_span(self):
        rows,rs=example();rows=rows[:3]+[None]+rows[3:]
        c.restore_table_row_spans(rows,c.table_source(rs,dict(elements=rs)))
        self.assertEqual(rows[1].row_spans,{1:dict(start=1,end=2)})


if __name__=='__main__':unittest.main()
