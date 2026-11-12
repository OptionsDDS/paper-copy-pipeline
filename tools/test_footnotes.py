"""Printed-row, marker-column and caption-continuation regression cases."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
paper=importlib.util.module_from_spec(spec);spec.loader.exec_module(paper)


def run(text,x,y,width,size=10,face='Example-Regular'):
    return dict(id=f'{x}:{y}:{text}',kind='text',text=text,angle=0,
                box_px=[x,y,x+width,y+size],run_size_px=size,char_ids=[],_faces={face:len(text)})


class Footnotes(unittest.TestCase):
    def notes(self):
        rs=[run(mark,10,y,8) for mark,y in [('**',120),('††',150),('§§',180),('iii',195)]]
        rs += [run(text,40,y,120) for text,y in [('First supplier,',120),('another city.',135),
                                              ('Second supplier.',150),('Third supplier.',180),('Fourth supplier.',195)]]
        return dict(elements=rs,region_box_px=[0,0,300,215])

    def test_detached_markers_keep_wrapped_notes_and_source_order(self):
        p=self.notes();p['elements'][0]['box_px'][3]=124  # raised asterisk has short ink bounds
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes,[['** First supplier,','another city.'],['†† Second supplier.'],
                                ['§§ Third supplier.'],['iii Fourth supplier.']])
        self.assertEqual(ids,{e['id'] for e in p['elements']})

    def long_last_note(self, indent=22, tail_text='fifth line.'):
        # three one-line notes, then a last note wrapped over four rows at a 12-unit leading
        rs=[run(f'{mark} Supplier {i}.',10,120+12*i,90) for i,mark in enumerate(('**','††','‡‡'))]
        rs.append(run('§§ Mixture: first part,',10,156,140))
        rs += [run(text,indent,156+12*k,120) for k,text in
               [(1,'second part,'),(2,'third part; and'),(3,'fourth part.')]]
        rs.append(run(tail_text,indent,204,60))
        return dict(elements=rs,region_box_px=[0,0,300,215])

    def test_last_note_keeps_every_wrapped_line(self):
        p=self.long_last_note()
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes[-1],['§§ Mixture: first part,','second part,','third part; and','fourth part.',
                                    'fifth line.'])
        self.assertEqual(ids,{e['id'] for e in p['elements']})

    def test_last_note_tail_stops_at_marker_gap_flush_row_and_other_indent(self):
        # the fixed window under the last marker reaches 'third part; and'; 'fourth part.' is the tail
        # a row that starts with a marker is a new note, not this note's tail
        p=self.long_last_note(tail_text='¶ Another')
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes[-1][-1],'fourth part.')
        self.assertNotIn(p['elements'][-1]['id'],ids)
        # a gap wider than the 1.5-size allowance under the lowest row ends the note
        p=self.long_last_note()
        for e in p['elements'][-2:]:e['box_px'][1]+=16;e['box_px'][3]+=16
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes[-1][-1],'third part; and')
        self.assertNotIn(p['elements'][-2]['id'],ids)
        # continuation flush with the marker gives no hanging indent: the fixed window stands
        notes,_=paper.marked_footnotes(self.long_last_note(indent=10),16,set())
        self.assertEqual(notes[-1][-1],'third part; and')
        # a row at another left edge is not the note's wrapped line, and nothing below it joins
        p=self.long_last_note();p['elements'][-2]['box_px'][0]=60
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes[-1][-1],'third part; and')
        self.assertFalse({e['id'] for e in p['elements'][-2:]}&ids)

    def test_ragged_right_wrapped_rows_past_the_marker_rows_stay_with_their_note(self):
        # the marker rows end at 150; the last note's wrapped rows end at 182, past the column's bound
        p=self.long_last_note()
        for e in p['elements'][4:]:e['box_px'][2]=e['box_px'][0]+160
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes[-1],['§§ Mixture: first part,','second part,','third part; and','fourth part.',
                                    'fifth line.'])
        self.assertEqual(ids,{e['id'] for e in p['elements']})
        # an earlier note keeps a wrapped row that ends past the marker rows as well
        p=self.long_last_note();p['elements'].insert(1,run('a wider wrapped row',22,132,160))
        for e in p['elements'][2:]:e['box_px'][1]+=12;e['box_px'][3]+=12
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertEqual(notes[0],['** Supplier 0.','a wider wrapped row'])
        self.assertEqual(ids,{e['id'] for e in p['elements']})

    def test_own_right_edge_needs_a_hanging_row_inside_the_column(self):
        # a wide unmarked row flush with the markers gets the column's bound, not the note's
        p=self.long_last_note()
        p['elements'][4]['box_px'][0]=10;p['elements'][4]['box_px'][2]=200
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertNotIn(p['elements'][4]['id'],ids)
        # a run that starts past the column's right edge is not a row of the note
        p=self.long_last_note();p['elements'].append(run('other column',170,168,100))
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertNotIn(p['elements'][-1]['id'],ids)
        self.assertEqual(notes[-1][-1],'fifth line.')
        # a marked row past the bound starts no own row: its note ends at the column's bound
        p=self.long_last_note(tail_text='¶ Another note that runs wide')
        p['elements'][-1]['box_px'][2]=300
        notes,ids=paper.marked_footnotes(p,16,set())
        self.assertNotIn(p['elements'][-1]['id'],ids)

    def test_prose_and_owned_table_notes_cannot_establish_a_note_column(self):
        p=self.notes()
        self.assertEqual(paper.marked_footnotes(p,10,set()),([],set()))
        self.assertEqual(paper.marked_footnotes(p,16,{e['id'] for e in p['elements'][:2]}),([],set()))
        for e in p['elements']:e['box_px'][1]-=100;e['box_px'][3]-=100
        self.assertEqual(paper.marked_footnotes(p,16,set()),([],set()))

    def test_markers_never_become_headings_despite_stale_style(self):
        for mark in ('*','***','††','‡','§§','‖','¶','#','###'):
            for meta in (dict(font_heading=True),dict(why='heading before main text in its column')):
                self.assertFalse(paper.is_heading(mark,meta,10,1))

    def test_repeated_label_pairs_retain_two_printed_value_rows(self):
        rs=[run(t,x,0,w) for t,x,w in [('Target',0,40),('Direction',70,50),('Sequence',150,80),('ID',280,20)]]
        for i,name in enumerate(('Alpha','Beta')):
            y=25+40*i
            rs += [run(name,0,y,40),run('F',90,y,5),run('ACG TAC',150,y,70),run(str(i+20),280,y,20),
                   run('R',90,y+14,5),run('GCA ATG',150,y+14,70)]
        page=dict(elements=rs+[dict(kind='fill',box_px=[0,-2,310,14])])
        rows,notes=paper.table_rows(rs,10,page)
        self.assertEqual(len(rows),5)
        self.assertEqual(rows[1],[['Alpha'],['F'],['ACG TAC'],['20']])
        self.assertEqual(rows[2],[[],['R'],['GCA ATG'],[]])
        self.assertFalse(notes)
        checks=paper.table_structure_checks(rows,paper.table_source(rs,page),'Table 2. Sequences',notes)
        self.assertFalse(checks['row_count']['fired'],checks['row_count'])

    def test_wrapped_value_without_an_independent_label_stays_one_cell(self):
        rows=[dict(header=False,cells={0:['Alpha'],1:['F'],2:['ACG','TAC']},
                   segments=[{0:['Alpha'],1:['F'],2:['ACG']},{2:['TAC']}])]
        self.assertEqual(paper.table_subrows(copy.deepcopy(rows)),rows)

    def test_italic_caption_continuation_and_smaller_header_boundary(self):
        cap=run('TABLE 2',0,0,45);title=run('Observations of',55,0,90)
        tail=run('a named organism',0,15,130,face='Example-Italic')
        header=run('Smaller table header',0,30,130,size=8,face='Example-Bold')
        p=dict(elements=[cap,title,tail,header])
        self.assertEqual(paper.table_caption_members(p,cap),[cap['id'],title['id'],tail['id']])
        for e in (cap,title):e['_faces']={'Example-Italic':len(e['text'])}
        tail['_faces']={'Example-Regular':len(tail['text'])}
        self.assertEqual(paper.table_caption_members(p,cap),[cap['id'],title['id'],tail['id']])
        p['elements'].insert(3,dict(kind='rule',box_px=[0,13,150,13]))
        self.assertEqual(paper.table_caption_members(p,cap),[cap['id'],title['id']])


if __name__=='__main__':unittest.main()
