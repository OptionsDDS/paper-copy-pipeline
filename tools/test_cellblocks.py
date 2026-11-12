"""Printed row bands keep independent lists and wrapped prose cells together."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width=60,bold=False):
    return dict(id=f'{x}:{y}',kind='text',text=text,angle=0,line=int(y),
                box_px=[x,y,x+width,y+10],char_ids=[],_faces={'Sans-Bold' if bold else 'Sans':len(text)})


def fill(y,bottom,width=320):
    return dict(kind='fill',box_px=[0,y,width,bottom])


class CellBlocks(unittest.TestCase):
    def test_independent_bullet_lists_make_one_row_at_every_angle(self):
        rs=[run('First list',5,0),run('Second list',165,0)]
        rs += [run(t,5 if t.startswith('•') else 15,y) for y,t in
               [(25,'• First item'),(40,'continued here'),(55,'• Next item'),(70,'continues')]]
        rs += [run(t,165 if t.startswith('•') else 175,y) for y,t in
               [(25,'• Other item'),(40,'more text'),(55,'still continues'),(70,'• Last item')]]
        page=dict(elements=rs+[fill(-5,18),dict(kind='rule',box_px=[0,90,320,90])])
        for angle in (0,90,180,270):
            p=copy.deepcopy(page)
            for e in p['elements']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e['kind']=='text':e['angle']=angle
            rows,notes=c.table_rows([e for e in p['elements'] if e['kind']=='text'],10,p)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[1][0],['• First item','continued here','• Next item','continues'])
            self.assertEqual(rows[1][1],['• Other item','more text','still continues','• Last item'])
            self.assertFalse(notes)
            checks=c.table_structure_checks(rows,c.table_source(p['elements'][:-2],p),'Table 1. Lists',notes)
            self.assertFalse(any(check['fired'] for check in checks.values()),checks)

    def test_synchronized_bullet_entries_remain_separate(self):
        rs=[run('Group',5,0),run('Action',165,0)]
        for y,t in [(25,'• First'),(45,'• Second'),(65,'• Third')]:
            rs.extend([run(t,5,y),run(t+' action',165,y)])
        rows,_=c.table_rows(rs,10,dict(elements=rs+[fill(-5,18)]))
        self.assertEqual(len(rows),4)

    def test_column_gap_separates_rows_even_with_internal_bullets(self):
        rs=[run('Group',5,0),run('Action',165,0)]
        for y,label in [(25,'First'),(100,'Second')]:
            rs += [run('• '+label,5,y),run('continued label',15,y+15),
                   run('• An action',165,y),run('• Another action',165,y+15),
                   run('continued action',175,y+30)]
        rows,_=c.table_rows(rs,10,dict(elements=rs+[fill(-5,18)]))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1][0],['• First','continued label'])
        self.assertEqual(rows[2][0],['• Second','continued label'])

    def test_bold_labels_and_shading_bound_prose_blocks(self):
        rs=[run('Approach',5,0),run('Examples',165,0)]
        for top,label in [(25,'First'),(85,'Second')]:
            rs += [run(label,5,top,bold=True),run('Patient benefits',5,top+15),
                   run('Allows expression',5,top+30),run('Provider benefits',5,top+45),
                   run('“An example that',165,top,100),run('continues here.”',175,top+15,100)]
        page=dict(elements=rs+[fill(-5,18),fill(80,140)])
        rows,notes=c.table_rows(rs,10,page)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1][0],['First','Patient benefits','Allows expression','Provider benefits'])
        self.assertEqual(rows[1][1],['“An example that','continues here.”'])
        checks=c.table_structure_checks(rows,c.table_source(rs,page),'Table 1. Examples',notes)
        self.assertFalse(any(check['fired'] for check in checks.values()),checks)

    def test_two_bold_starts_inside_shading_are_independent(self):
        rs=[run('Measure',5,0),run('Value',165,0)]
        for y,label in [(25,'First'),(45,'Second'),(85,'Third'),(105,'Fourth')]:
            rs.extend([run(label,5,y,bold=True),run('12',165,y)])
        rows,_=c.table_rows(rs,10,dict(elements=rs+[fill(-5,18),fill(80,125)]))
        self.assertEqual(len(rows),5)

    def test_banded_list_joins_wrapping_and_retains_entries(self):
        rs=[run('Effects',5,0,bold=True),run('An effect on',5,25),run('the tissue',15,40),
            run('Another effect',5,60),run('(including examples)',15,75),
            run('Independent item.',5,95),run('a separate entry',5,115),run('• A bullet',5,135),
            run('continued here',15,150),run('Next heading',5,170,bold=True)]
        rows,_=c.table_rows(rs,10,dict(elements=rs,_table_layout='banded list'))
        self.assertEqual(rows,[[['Effects']],[['An effect on','the tissue']],
            [['Another effect','(including examples)']],[['Independent item.']],
            [['a separate entry']],[['• A bullet','continued here']],[['Next heading']]])

    def test_gate_uses_printed_order_and_counts_the_payload(self):
        rs=[run('Approach',5,0),run('Action',165,0),run('Alpha',5,25),
            run('• First action',165,25),run('continued here',175,40),
            run('Beta',5,70),run('• Next action',165,70),run('continued there',175,85)]
        # Saved reading blocks may put all the labels after the right column.
        rs=rs[1::2]+rs[::2]
        source=c.table_source(rs,dict(elements=rs))
        it=dict(kind='table',page=1,caption='Table 1. Actions',rows=[],notes=[],table_source=source)
        record=c.gate_tables([it],[dict(page=1,elements=rs)],[])[0]
        self.assertEqual(record['printed_lines'],['Approach Action','Alpha • First action',
            'continued here','Beta • Next action','continued there'])
        self.assertEqual(record['source_line_count'],len(record['printed_lines']))
        self.assertEqual(record['region_coverage']['missing_output_line_count'],0)
        markdown=c.table_gate_markdown(record['printed_lines'])
        self.assertIn('5 printed lines follow',markdown[1])
        self.assertEqual(len([s for s in markdown if s.startswith('- ')]),5)

    def test_empty_gate_does_not_promise_a_zero_line_table(self):
        markdown=c.table_gate_markdown([])
        self.assertIn('no printed lines located',markdown[1])
        self.assertNotIn('lines follow',markdown[1])

    def test_following_reference_list_cannot_extend_the_table_payload(self):
        import re
        lines=c.table_gate_markdown(['First row','Last row'],following_list=True)
        lines += ['', '- 1. A reference outside the table.']
        rendered='\n'.join(lines)
        for _ in range(2):
            rendered=re.sub(r'(\n- [^\n]*)\n\n(?=- )',r'\1\n',rendered)
        payload,following=rendered.split('<!-- end of table -->')
        self.assertEqual(sum(line.startswith('- ') for line in payload.splitlines()),2)
        self.assertIn('- 1. A reference outside the table.',following)


if __name__=='__main__':unittest.main()
