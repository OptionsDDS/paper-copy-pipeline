"""Raised table citations use the printed frame; citation boxes own their feet."""
import unittest
from test_marks import copy, glyphs


def rotated(chars, angle):
    result=[]
    f=copy.frame(-angle)
    for c in chars:
        x,y=c['origin'];box=f([c['x0'],y-c['size'],c['x1'],y])
        origin=f([x,y,x,y])[:2];advance=f([c['adv_x1'],y,c['adv_x1'],y])[:2]
        result.append(dict(c,x0=box[0],y0=box[1],x1=box[2],y1=box[3],origin=origin,
                           adv_x1=advance[0],adv_y1=advance[1],angle=angle))
    return result


class TableCitations(unittest.TestCase):
    def test_cells_and_gate_lines_in_all_reading_directions(self):
        text='Author 201712';cs=glyphs(text,range(11,13))
        for angle in (0,90,180,270):
            e=dict(id='study',kind='text',angle=angle,text=text,box_px=[0,0,100,20],
                   _chars=rotated(cs,angle))
            p=dict(elements=[e],_citation_numbers={12},_raised_marks=[])
            item=dict(table_source=dict(lines=[dict(items=[dict(id='study')])]))
            lines=['| Author 201712 | 109 |','- Author 201712 109']
            self.assertEqual(copy.table_raised_marks(lines,item,p),
                             ['| Author 2017[12] | 109 |','- Author 2017[12] 109'])
            self.assertEqual(e['_chars'],rotated(cs,angle),'native geometry is immutable')

    def test_parenthesized_publication_year_and_equation(self):
        for text,table,want in [('(1988)12.',True,'(1988)[12].'),
                                ('Author et al (1988)12.',False,'Author et al (1988)[12].'),
                                ('(1988)12.',False,'(1988)12.'),
                                ('x = (1988)12.',True,'x = (1988)12.')]:
            start=text.index(')')+1
            self.assertEqual(copy.raised_mark_text(text,glyphs(text,range(start,start+2)),{12},table=table),want)

    def test_incomplete_rotated_geometry_is_left_unmarked(self):
        text='Author 201712'
        for angle in (90,180,270):
            for key in ('adv_x1','adv_y1','x0','origin'):
                cs=rotated(glyphs(text,range(11,13)),angle)
                cs[-1][key]=None
                e=dict(id='study',kind='text',angle=angle,text=text,box_px=[0,0,100,20],_chars=cs)
                p=dict(elements=[e],_citation_numbers={12},_raised_marks=[])
                item=dict(table_source=dict(lines=[dict(items=[dict(id='study')])]))
                self.assertEqual(copy.table_raised_marks([text],item,p),[text])
                self.assertEqual(p['_raised_marks'],[])

    def test_detached_table_mark_in_rotated_and_upright_frames(self):
        for angle in (0,90,180,270):
            cs=rotated(glyphs('Author 201712',range(11,13)),angle)
            es=[dict(id='author',kind='text',angle=angle,text='Author 2017',box_px=[0,0,60,20],_chars=cs[:11]),
                dict(id='mark',kind='text',angle=angle,text='12',box_px=[60,0,70,10],_chars=cs[11:])]
            p=dict(elements=es,_citation_numbers={12},_raised_marks=[])
            item=dict(table_source=dict(lines=[dict(items=[dict(id=e['id']) for e in es])]))
            self.assertEqual(copy.table_raised_marks(['| Author 2017 12 |','- Author 201712'],item,p),
                             ['| Author 2017[12] |','- Author 2017[12]'])

    def test_rotated_numbered_table_note_stays_a_note(self):
        texts=['systems1','1 A definition']
        es=[dict(id=str(i),kind='text',angle=90,text=t,box_px=[0,0,100,20],
                 _chars=rotated(glyphs(t,[7] if not i else [0]),90)) for i,t in enumerate(texts)]
        p=dict(page=1,elements=es,_citation_numbers={1,2},_raised_marks=[])
        item=dict(kind='table',page=1,caption='Table 1. Results',
                  table_source=dict(lines=[dict(items=[dict(id=e['id']) for e in es])]))
        copy.prepare_table_mark_notes([item],[p])
        self.assertEqual(copy.table_raised_marks(['systems1'],item,p),['systems1'])

    def test_rotated_citation_support_preserves_footnotes_and_marks_powers(self):
        for text,raised,numbers in [('18,200a',[6],{1}),('103',[2],{3}),
                                    ('Year 201712 18,200a',[9,10,18],{12})]:
            cs=rotated(glyphs(text,raised),90)
            e=dict(id='study',kind='text',angle=90,text=text,box_px=[0,0,100,20],_chars=cs)
            p=dict(elements=[e],_citation_numbers=numbers,_raised_marks=[])
            item=dict(table_source=dict(lines=[dict(items=[dict(id='study')])]))
            want=text.replace('201712','2017[12]')
            if text=='103':want='10^3'
            self.assertEqual(copy.table_raised_marks([text],item,p),[want])

    def test_table_powers_in_cells_and_gates_in_all_frames(self):
        for text,indices,want in [('3.4 × 106', [8], '3.4 × 10^6'),
                                   ('≥106', [3], '≥10^6'),
                                   ('10−3', [2,3], '10^−3')]:
            for angle in (0,90,180,270):
                for detached in (False,True):
                    cs=rotated(glyphs(text,indices),angle)
                    chunks=[(text,cs)] if not detached else [(text[:indices[0]],cs[:indices[0]]),
                                                            (text[indices[0]:],cs[indices[0]:])]
                    es=[dict(id=str(i),kind='text',angle=angle,text=t,box_px=[0,0,100,20],_chars=c)
                        for i,(t,c) in enumerate(chunks)]
                    p=dict(elements=es,_citation_numbers={3,6},_raised_marks=[])
                    item=dict(table_source=dict(lines=[dict(items=[dict(id=e['id']) for e in es])]))
                    self.assertEqual(copy.table_raised_marks(['| '+text+' |','- '+text],item,p),
                                     ['| '+want+' |','- '+want])

    def test_ambiguous_table_number_retains_baseline_value(self):
        es=[dict(id=str(i),kind='text',angle=90,text='106',box_px=[0,0,100,20],
                 _chars=rotated(glyphs('106',raised),90)) for i,raised in enumerate(([2],[]))]
        p=dict(elements=es,_citation_numbers={6},_raised_marks=[])
        item=dict(table_source=dict(lines=[dict(items=[dict(id=e['id']) for e in es])]))
        self.assertEqual(copy.table_raised_marks(['| 106 |'],item,p),['| 106 |'])

    def test_table_word_matching_retains_equation_context(self):
        text='x = (1988)12.';start=text.index(')')+1
        e=dict(id='equation',kind='text',angle=0,text=text,box_px=[0,0,100,20],
               _chars=glyphs(text,range(start,start+2)))
        p=dict(elements=[e],_citation_numbers={12},_raised_marks=[])
        item=dict(table_source=dict(lines=[dict(items=[dict(id=e['id'])])]))
        self.assertEqual(copy.table_raised_marks([text],item,p),[text])


if __name__=='__main__':unittest.main()
