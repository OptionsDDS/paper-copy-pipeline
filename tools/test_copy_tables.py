"""Geometry-only table regressions. Run: /usr/bin/python3 -I tools/test_copy_tables.py"""
import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def text(label, x, y, width=35, face='Sans'):
    return dict(id=f'{label}:{x}:{y}', kind='text', text=label, angle=0, line=int(y),
                box_px=[x, y, x + width, y + 10], char_ids=[], _faces={face: len(label)})


def drawing(box, kind='rule'):
    return dict(kind=kind, box_px=box)


class Tables(unittest.TestCase):
    def test_side_caption_recovers_header_and_body_classified_column_at_every_angle(self):
        runs=[text(label,x,y,60) for y,labels in [(5,['Study','Arm','Result']),
              (35,['Alpha','A','12']),(65,['Beta','B','24']),(95,['Gamma','C','36'])]
              for x,label in zip([5,105,205],labels)]
        cap=text('TABLE 8',320,5,60);title=text('A title',390,5,60)
        runs += [cap,title,text('Following prose.',0,190,250)]
        fills=[drawing([x,y,x+100,y+20],'fill') for y in [0,60] for x in [0,100,200]]
        for i,e in enumerate(fills):e['id']=f'fill:{i}'
        table=dict(id='table:1',box_px=[0,60,300,120],angle=0,
                   members=[e['id'] for e in runs[:12] if e['box_px'][1]>=60])
        blocks=[dict(id=e['id']+':block',members=[e['id']],box_px=e['box_px']) for e in runs]
        meta=[dict(b,cls='main',order=i+1,lines=1,size_px=10,text=runs[i]['text'])
              for i,b in enumerate(blocks)]
        page=dict(page=1,elements=runs+fills,tables=[table],blocks=blocks,floats=[],
                  region_box_px=[0,0,500,250],main_text=dict(blocks=meta,columns=[[0,300],[320,500]]))
        for angle in [0,90,180,270]:
            rotated=copy.deepcopy(page)
            for e in rotated['elements']+rotated['tables']+rotated['blocks']+rotated['main_text']['blocks']:
                e['box_px']=paper.frame(-angle)(e['box_px'])
                if 'angle' in e:e['angle']=angle
            recovered=paper.table_float_regions(rotated,10)
            self.assertEqual(len(recovered['floats']),1)
            self.assertEqual(recovered['tables'][0]['_copy_region'],[0,0,300,120])
            body,floats,side=paper.read_page(rotated,10,[])
            self.assertEqual(floats[0][2],'Table 8. A title')
            self.assertIn('36',str(floats[0][3]))
            self.assertEqual([b['lines'] for b in body],[['Following prose.']])

    def test_repeated_shaded_list_captions_keep_their_own_columns(self):
        runs=[];fills=[]
        for x in [0,400]:
            runs += [text('TABLE 2',x,0,60),text('A list' if x==0 else '(Continued)',x+70,0,110)]
            runs += [text('A citation line',x+5,y,220) for y in [40,60,80,100,120,140]]
            fills += [drawing([x,y,x+300,y+20],'fill') for y in [35,75,115]]
        page=dict(elements=runs+fills,tables=[],floats=[],blocks=[])
        result=paper.table_float_regions(page,10)
        self.assertEqual(len(result['tables']),2)
        self.assertEqual(len(result['floats']),2)
        first,second=result['tables']
        self.assertFalse(set(first['members']) & set(second['members']))
        self.assertEqual([t['layout'] for t in result['tables']],['banded list','banded list'])

    def test_narrow_header_channels_keep_adjacent_columns(self):
        runs=[text(label,x,y,37) for y,labels in [(0,['Name','Source','Action','Result']),
              (25,['Alpha','First','Choice','12']),(40,['Beta','Other','Method','24'])]
              for x,label in zip([0,40,80,120],labels)]
        page=dict(elements=runs+[drawing([0,0,160,16],'fill')])
        rows,_=paper.table_rows(runs,10,page)
        self.assertEqual(rows[0],[['Name'],['Source'],['Action'],['Result']])
        self.assertEqual(rows[1],[['Alpha'],['First'],['Choice'],['12']])
        for angle in [90,180,270]:
            rotated=copy.deepcopy(page)
            for e in rotated['elements']:
                e['box_px']=paper.frame(-angle)(e['box_px'])
                if e['kind']=='text': e['angle']=angle
            self.assertEqual(paper.table_rows(rotated['elements'][:-1],10,rotated)[0],rows)

    def test_sparse_header_columns_and_right_aligned_overhang(self):
        runs=[text(label,x,0,30) for x,label in zip([0,60,120,180],['Type','Empty','Count','Other'])]
        runs += [text('Alpha',0,25,30),text('123456789',70,25,60),text('1',180,25,10),
                 text('Beta',0,45,30),text('2',120,45,10),
                 text('Gamma',0,65,30),text('3',120,65,10)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,220,16],'fill')]))
        self.assertEqual(rows[0],[['Type'],['Empty'],['Count'],['Other']])
        self.assertEqual(rows[1],[['Alpha'],[],['123456789'],['1']])

    def test_year_starts_entry_after_previous_label_ended(self):
        runs=[text(label,x,0,70) for x,label in zip([0,100,200],['Period','Concept','Remarks'])]
        runs += [text('Earlier',0,25),text('First idea',100,25,70),text('Explanation',200,25,70),
                 text('continued remarks',200,40,75),text('more remarks',200,55,70),
                 text('2001',0,70),text('Next idea',100,70,70),text('New remarks',200,70,70)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,280,16],'fill')]))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1][0],['2001'])

    def test_raised_matrix_label_owns_wrapped_values_until_next_label(self):
        runs=[text(label,x,0) for x,label in zip([0,100,200],['Process','Type A','Type B'])]
        runs += [text('Attachment',0,25,80),text('1',100,40),text('2',200,40),
                 text('Proliferation',0,55,80),text('3',100,70),text('4',200,70),
                 text('5',100,85),text('6',200,85),text('Factors',0,100,80),
                 text('First',0,115),text('7',100,115),text('Empty',0,130),
                 text('Next',0,145),text('8',200,145)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,250,16],'fill')]))
        self.assertEqual(rows[2],[['Proliferation'],['3','5'],['4','6']])
        self.assertIn([['Factors'],[],[]],rows)
        self.assertIn([['Empty'],[],[]],rows)

    def test_single_ruled_study_keeps_all_prose_cells_whole(self):
        runs=[text(label,x,0,70) for x,label in zip([0,100,200],['Studies','Objectives','Results'])]
        runs += [text('Jones et al.',0,25,70),text('First aim',100,25,70),text('First finding',200,25,70),
                 text('2020',0,40),text('continued aim',100,40,70),text('more findings',200,40,70),
                 text('Another aim',100,65,70),text('Another result',200,65,70)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,280,16],'fill'),drawing([0,82,280,82.2])]))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[-1][1],['First aim','continued aim','Another aim'])

    def test_drawn_study_band_is_not_reported_as_row_collapse(self):
        runs=[text(label,x,0,70) for x,label in zip([0,100,200],['Studies','Objectives','Results'])]
        runs += [text('Jones et al.',0,25,70),text('2020',0,40)]
        runs += [text('continued cell',x,25+i*15,70) for i in range(24) for x in [100,200]]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,280,16],'fill'),drawing([0,385,280,385.2])]))
        self.assertEqual(len(rows),2)
        self.assertFalse(paper.table_warnings(rows,runs))

    def test_indented_prose_after_bottom_border_stays_outside_cells(self):
        runs=[text(label,x,y) for y,labels in [(5,['Name','Type','Count']),
              (25,['Alpha','One','12']),(45,['Beta','Two','24']),(65,['Gamma','Three','36'])]
              for x,label in zip([5,105,205],labels)]
        runs += [text('Following indented paragraph after the table',100,95,200)]
        graphics=[drawing([x,0,x+.2,80]) for x in [0,100,200,300]]
        graphics += [drawing([0,y,300,y+.2]) for y in [0,20,40,60,80]]
        rows,notes=paper.table_rows(runs,10,dict(elements=runs+graphics))
        self.assertEqual(len(rows),4)
        self.assertEqual(notes,['Following indented paragraph after the table'])

    def test_comma_continuation_keeps_multicell_prose_in_one_row(self):
        runs=[text(label,x,5) for x,label in zip([5,105,205,305],['Product','Source','Action','Use'])]
        runs += [text('First',5,25),text('One source',105,25),text('One action',205,25),text('One use',305,25),
                 text('continued action',205,40),text('Second',5,65),text('Cloned from human',105,65),
                 text('First action',205,65),text('A sponge,',305,65),text('a carrier',305,85),
                 text('FGF gene',105,85),text('Second action',205,85)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,400,20],'fill')]))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[-1][-1],['A sponge,','a carrier'])

    def test_wide_wrapped_last_column_is_not_a_footnote(self):
        runs=[text('Name',0,0),text('Common',100,0),text('Properties',200,0,190)]
        for i in range(3):
            y=25+i*45
            runs += [text(f'Entry {i}',0,y),text('Label',100,y),
                     text('A descriptive cell filling the right column',200,y,190),
                     text('continued properties',205,y+15,180)]
        rows,notes=paper.table_rows(runs,10,dict(elements=runs+[drawing([0,0,400,20],'fill')]))
        self.assertEqual(len(rows),4)
        self.assertFalse(notes)
        self.assertEqual(rows[-1][2][-1],'continued properties')

    def test_study_bands_keep_wrapped_names_and_observations_together(self):
        runs=[text(label,x,5) for x,label in zip([5,105,205],['Study','Time','Result'])]
        runs += [text('Smith and',5,35),text('3 mo',105,35),text('12',205,35),
                 text('Jones',10,50),text('6 mo',105,50),text('24',205,50),
                 text('Country',10,65),text('9 mo',105,65),text('36',205,65),
                 text('Other study',5,95),text('Other method',105,95),text('Elsewhere',205,95)]
        page=dict(elements=runs+[drawing([0,0,300,20],'fill'),drawing([0,30,300,80],'fill')])
        rows,_=paper.table_rows(runs,10,page)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1],[['Smith and','Jones','Country'],['3 mo','6 mo','9 mo'],['12','24','36']])

    def test_group_rows_are_marked_and_rendered_once(self):
        runs=[text('Category',5,25,100,'Sans-B'),text('An item',5,45,100)]
        rows,_=paper.table_rows(runs,10,dict(elements=runs,_table_layout='banded list'))
        self.assertTrue(rows[0].group)
        markdown=paper.table_markdown(rows,paper.Joiner([r['text'] for r in runs]))
        self.assertIn('| **Category** |',markdown)
        self.assertIn('| An item |',markdown)

    def test_captioned_banded_list_stops_before_following_prose(self):
        spec=importlib.util.spec_from_file_location('table_boxer',Path(__file__).resolve().parents[1]/'standalone/element_boxer_sc.py')
        boxer=importlib.util.module_from_spec(spec);spec.loader.exec_module(boxer)
        runs=[text('TABLE 1',0,0,60,'Sans-B'),text('A caption title',70,0,140),
              text('continued title',0,14,100),text('Category',5,30,120,'Sans-B')]
        runs += [text(f'Entry {i}',5,50+i*20,120) for i in range(6)]
        runs += [text('Following body paragraph',0,200,210)]
        chars=[]
        for i,r in enumerate(runs):
            r.update(char_ids=[i],run_size_px=10,size_px=10)
            chars.append(dict(id=i,font=next(iter(r['_faces'])),text=r['text']))
        fills=[dict(drawing([0,y,210,y+20],'fill'),id=f'fill:{y}') for y in (44,84,124)]
        tables=boxer.tables_from_banded_list(runs+fills,[],chars)
        self.assertEqual(len(tables),1)
        self.assertEqual(tables[0]['layout'],'banded list')
        self.assertEqual(set(tables[0]['members']),{r['id'] for r in runs[3:-1]+fills})
        self.assertFalse(boxer.tables_from_banded_list(runs+fills,tables,chars))

    def test_short_border_segments_keep_three_columns_and_wrapped_cells(self):
        runs = [text(label, x, y) for y, labels in [(5, ['Product', 'Material', 'Months']),
                (25, ['Alpha', 'Type one', '2']), (65, ['Beta', 'Type two', '4'])]
                for x, label in zip([5, 105, 205], labels)]
        runs.append(text('(Company)', 5, 40))
        graphics = [([x, y, x + .2, y + 20], 'rule') for x in [100, 200] for y in range(0, 80, 20)]
        graphics += [([0, y, 300, y + .2], 'rule') for y in [0, 20, 60, 80]]
        rows = paper.ruled_table_rows(paper.table_lines([(r['box_px'], r['text'], r) for r in runs]), graphics, 10)
        self.assertEqual(rows, [[['Product'], ['Material'], ['Months']],
                               [['Alpha', '(Company)'], ['Type one'], ['2']],
                               [['Beta'], ['Type two'], ['4']]])

    def test_rotated_and_upright_wrapped_tables_are_equivalent(self):
        runs = [text(label, x, y) for y, labels in [(5, ['Study', 'Method', 'Count']),
                (25, ['Alpha', 'First line', '12']), (65, ['Beta', 'Other method', '24'])]
                for x, label in zip([5, 105, 205], labels)]
        runs += [text('(2020)', 5, 40), text('second line', 105, 40)]
        page = dict(elements=runs + [drawing([0, 0, 300, 20], 'fill')])
        expected = paper.table_rows(runs, 10, page)
        self.assertEqual(len(expected[0]), 3)
        self.assertEqual(expected[0][1][0], ['Alpha', '(2020)'])
        for angle in [90, 180, 270]:
            rotated = copy.deepcopy(page)
            for element in rotated['elements']:
                element['box_px'] = paper.frame(-angle)(element['box_px'])
                if element['kind'] == 'text': element['angle'] = angle
            self.assertEqual(paper.table_rows(rotated['elements'][:-1], 10, rotated), expected)

    def test_merged_data_cell_is_not_repeated_across_columns(self):
        runs = [text(label, x, y) for y, labels in [(5, ['Group', 'Type', 'Details']),
                (85, ['Beta', 'Two', 'Other'])] for x, label in zip([5, 105, 205], labels)]
        runs += [text('Alpha', 5, 45), text('Shared description', 105, 45, 120)]
        graphics = [([100, 0, 100.2, 120], 'rule'), ([200, 0, 200.2, 40], 'rule'),
                    ([200, 80, 200.2, 120], 'rule')]
        graphics += [([0, y, 300, y + .2], 'rule') for y in [0, 40, 80, 120]]
        rows = paper.ruled_table_rows(paper.table_lines([(r['box_px'], r['text'], r) for r in runs]), graphics, 10)
        self.assertEqual(rows[1], [['Alpha'], ['Shared description'], []])

    def test_variable_length_labels_keep_the_percentage_column(self):
        runs = [text('Occupation', 0, 0, 70), text('Agreement', 210, 0, 75),
                text('Correlation', 355, 0, 75), text('Significance', 500, 0, 80)]
        for i, (label, width) in enumerate([('Research fellows', 130), ('Nurses', 75),
                                           ('Clinical staff', 150), ('Surgeons', 95), ('Other staff', 110)]):
            y = 30 + 20 * i
            runs += [text(label, 0, y, width), text('72.4%', 250, y),
                     text('0.52', 380, y), text('0.35', 530, y)]
        rows, _ = paper.table_rows(runs, 10, dict(elements=runs + [drawing([0, 0, 600, 20], 'fill')]))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[1], [['Research fellows'], ['72.4%'], ['0.52'], ['0.35']])

    def test_italic_group_header_does_not_join_previous_label(self):
        runs = [text(label, x, y) for y, labels in [(5, ['Group', 'Value', 'Count']),
                (25, ['Alpha', '1', '2']), (55, ['(a) No', '3', '4']), (70, ['(b) Yes', '5', '6'])]
                for x, label in zip([5, 105, 205], labels)]
        runs.append(text('Category', 5, 40, face='Sans-I'))
        rows, _ = paper.table_rows(runs, 10, dict(elements=runs + [drawing([0, 0, 300, 20], 'fill')]))
        self.assertIn([['Category'], [], []], rows)
        self.assertIn([['(a) No'], ['3'], ['4']], rows)

    def test_caption_continuation_stops_at_header_font(self):
        runs = [text('T A B L E 1', 0, 0, 60, 'Sans-B'), text('Results', 70, 0, 60, 'Sans-B'),
                text('across visits', 0, 14, 100, 'Sans-B'), text('Group', 0, 28), text('Count', 110, 28)]
        self.assertEqual(paper.table_caption_members(dict(elements=runs), runs[0]), [r['id'] for r in runs[:3]])

    def test_caption_can_overhang_a_narrower_table(self):
        runs=[text('TABLE 1',0,0,60,'Sans-B'),text('A caption title',70,0,70),
              text('continued title',0,14,100),text('Group',0,35,100,'Sans-B')]
        self.assertEqual(paper.table_caption_members(dict(elements=runs),runs[0],[0,35,108,200]),
                         [r['id'] for r in runs[:3]])

    def test_indented_prose_wrap_is_not_a_group_header(self):
        runs = [text(label, x, y) for y, labels in [(5, ['Treatment', 'Value', 'Count']),
                (25, ['Treatment with', '1', '2']), (80, ['Other', '3', '4'])]
                for x, label in zip([5, 105, 205], labels)]
        runs += [text('Local material', 5, 40, 70), text('and a carrier', 15, 55, 65)]
        rows, _ = paper.table_rows(runs, 10, dict(elements=runs + [drawing([0, 0, 300, 20], 'fill')]))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][0], ['Treatment with', 'Local material', 'and a carrier'])

    def test_self_checks_reject_collapse_and_repeated_prose(self):
        runs = [text(f'Line {i}', 0, i * 15) for i in range(30)]
        self.assertTrue(any('printed lines' in w for w in paper.table_warnings([[['all text']]], runs)))
        phrase = ['One entire descriptive cell repeated in several columns']
        self.assertTrue(any('repeats' in w for w in paper.table_warnings([[['Header']], [['Subheader']], [phrase, phrase]], [])))
        self.assertFalse(paper.table_warnings([[['Header']], [['Subheader']], [['Yes'], ['Yes']]], []))
        separated = [text('Value', x, y) for y in [0, 20, 40] for x in [0, 100]]
        self.assertTrue(any('one column' in w for w in paper.table_warnings([[['Values']]] * 3, separated)))

    def continued(self, closing=False, columns=3, next_page=2, spread=False):
        first = dict(kind='table', page=1, top=0, caption='Table 1. Results', rows=[[['a']] * 3] * 3, notes=[])
        second = dict(kind='table', page=next_page, top=0, caption=f'Table (no caption on page {next_page})',
                      rows=[[['b']] * columns] * 3, notes=[])
        pages = [dict(page=n, region_box_px=[0, 0, 300, 500], elements=[],
                      tables=[dict(box_px=[0, 0, 300, 100], angle=0)]) for n in [1, next_page]]
        if closing: pages[0]['elements'].append(drawing([0, 100, 300, 101]))
        if spread:
            for page in pages:
                page['elements'] += [drawing([x, y, x + 100, y + 20], 'fill') for y in [0, 40, 80] for x in [0, 100, 200]]
        paper.arrange_floats([first, second], pages, [])
        return second['caption']

    def test_matching_open_grid_alone_does_not_witness_continuation(self):
        # D-586/D-588 replaces the old open-grid guess with an edge notice.
        # Positive direction and rotation cases live in test_floats3.py.
        self.assertIn('no caption', self.continued())
        self.assertIn('no caption', self.continued(closing=True))
        self.assertIn('no caption', self.continued(columns=4))
        self.assertIn('no caption', self.continued(next_page=3))

    def test_facing_page_columns_have_distinct_caption(self):
        self.assertEqual(self.continued(closing=True, columns=4, spread=True), 'Table 1 (additional columns)')


if __name__ == '__main__':
    unittest.main()
