"""Scan regressions (iss-12): page margin rows and column-foot notes never
stand inside a sentence (scan_sentence_interruptions)."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scaninterrupt',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)

IDS=iter(range(10**6))


def run(text,x,y,w,size=18.6,h=17):
    return dict(text=text,box_px=[x,y,x+w,y+h],size_px=size,_scan_id=next(IDS))


def line(page,*runs):
    return dict(kind='line',runs=list(runs),box_px=copy.hull(r['box_px'] for r in runs),page=page)


def geometry(stream,heights):
    out={}
    for it in stream:
        out.setdefault(it['page'],(heights[it['page']],[]))[1].extend((r['_scan_id'],r['box_px']) for r in it['runs'])
    return out


def texts(stream):
    return [(it['kind'],copy.scan_line(it['runs'])) for it in stream]


class ThreeColumnPage:
    """AP21 page 2 geometry (1133 x 1554 px, 18.6 px type, line pitch 21.5 px):
    the middle column ends mid-sentence at y 1388, a starred note stands 34 px
    lower with one wrapped line, the right column opens with a detached
    running head 27 px above its first body line, which continues the
    sentence."""
    def build(self,before='the measured level changed only a little as a',
              after='result of the treatment. Between the two visits',
              note_gap=34,head_gap=27,below_note=False,above_head=False):
        s=[]
        s.append(line(2,run('first column prose that is ordinary body text',69,1371,316)))
        s.append(line(2,run('in the first column and ends its sentence here.',69,1393,316)))
        s.append(line(2,run('middle column body prose with printed words in',418,1367,315)))
        s.append(line(2,run(before,418,1388,315)))
        top=1405+note_gap
        s.append(line(2,run('* Product name; maker and town of origin,',419,top,316)))
        s.append(line(2,run('Country.',418,top+20,35)))
        if below_note:
            s.append(line(2,run('more middle column prose under the note',418,top+60,315)))
            s.append(line(2,run('and its next line at the usual pitch',418,top+81,315)))
        head=91-17-head_gap
        if above_head:s.append(line(2,run('a line printed over the head',782,head-30,200)))
        s.append(line(2,run('Short running title words',782,head,217),run('211',1037,head,30)))
        s.append(line(2,run(after,752,91,315)))
        s.append(line(2,run('and later the values were lower in each group',752,113,314)))
        return s


class Interruptions(unittest.TestCase,ThreeColumnPage):
    def test_note_and_running_head_inside_a_sentence_leave_it(self):
        s=self.build()
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{2:1554}))
        self.assertEqual([m['edge'] for m in moved],['top'])
        self.assertEqual(copy.scan_line(moved[0]['runs']),'Short running title words 211')
        self.assertEqual([k for k,_ in texts(out)],['line']*4+['note','line','line'])
        self.assertEqual(len(out[4]['runs']),2)
        arranged=copy.scan_arrange_floats(out)
        self.assertEqual(texts(arranged)[3:6],[('line','the measured level changed only a little as a'),
            ('line','result of the treatment. Between the two visits'),
            ('line','and later the values were lower in each group')])
        self.assertEqual(arranged[-1]['kind'],'note')

    def test_running_foot_across_a_page_turn_leaves_the_sentence(self):
        # AP19 page 1/2 geometry (1150 x 1575 px): the page's last body line
        # ends at y 1472 unfinished; the journal foot stands 33 px lower, its
        # folio read in a taller 22 px box; page 2 opens with the continuation.
        s=[line(1,run('the earlier work gave the first account of the new appliance,',599,1453,475,21.7,19)),
           line(1,run('JOURNAL 10/6/ MONTH, 1990',829,1505,187,15.6,13),run('14n',1043,1505,33,22.2,11)),
           line(2,run('which was described two years later in a report at the',74,62,473,21.7,21)),
           line(2,run('meeting of the society for research and was',74,85,473,21.7,21))]
        s.insert(0,line(1,run('sleep studies were ordinary body prose here and',599,1431,475,21.7,19)))
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1575,2:1575}))
        self.assertEqual([m['edge'] for m in moved],['bottom'])
        self.assertEqual([it['page'] for it in out],[1,1,2,2])

    def test_finished_or_capitalised_neighbours_keep_the_rows_in_place(self):
        for kwargs in (dict(before='the measured level changed only a little.'),
                       dict(before='in s 2'),
                       dict(after='Results of the treatment. Between the two visits')):
            s=self.build(**kwargs)
            out,moved=copy.scan_sentence_interruptions(s,geometry(s,{2:1554}))
            self.assertEqual(moved,[],kwargs)
            self.assertEqual(texts(out),texts(s),kwargs)

    def test_a_head_that_is_not_detached_or_not_outermost_is_body(self):
        for kwargs in (dict(head_gap=10),dict(above_head=True)):
            s=self.build(**kwargs)
            out,moved=copy.scan_sentence_interruptions(s,geometry(s,{2:1554}))
            self.assertEqual(moved,[],kwargs)
            self.assertIn(('line','Short running title words 211'),texts(out),kwargs)

    def test_a_note_needs_a_blank_above_and_the_column_foot(self):
        for kwargs in (dict(note_gap=8),dict(below_note=True)):
            s=self.build(**kwargs)
            out,moved=copy.scan_sentence_interruptions(s,geometry(s,{2:1554}))
            # The note stays a body line; the detached head may still move.
            self.assertNotIn('note',[it['kind'] for it in out],kwargs)
            self.assertIn(('line','* Product name; maker and town of origin,'),texts(out),kwargs)

    def test_a_last_body_line_with_overlapping_ocr_boxes_is_not_detached(self):
        # AL10 page 1 geometry (1250 x 1650 px): the right column's lines are
        # 25 px apart in 26-29 px boxes; the last one's box overlaps the box
        # above, and the next line wholly above it is 23 px away (> 0.8 em).
        s=[line(1,run('may be viewed as similar to that used in any',626,1459,498,19.0,25)),
           line(1,run('local infection. Initially, potential periodontal',626,1482,497,19.0,29)),
           line(1,run('pathogens encounter plasma factors, such as these,',625,1507,498,18.2,28)),
           line(2,run('which is printed at the head of the next page and',80,80,480,18.2,26)),
           line(2,run('goes on as ordinary body prose in the column',80,105,480,18.2,26))]
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1650,2:1650}))
        self.assertEqual(moved,[])
        self.assertEqual(texts(out),texts(s))


class MarginBand(unittest.TestCase):
    """The margin row is its whole band: kept pieces in the same outer zone
    that overlap it in height belong to it (invented two-column page, 1200 x
    1600 px, 15 px type)."""
    def page(self,foot_pieces,last='the patients who smoked had more loss than those who did',
             body_gap=60):
        y=1395-21*3
        s=[line(1,run('the first column carries ordinary prose in plain words',80,y,500,15,21)),
           line(1,run('and its lines run at the usual pitch down the page as',80,y+21,500,15,21)),
           line(1,run('in any scanned journal article set in two columns and',80,y+42,500,15,21)),
           line(1,run(last,80,y+63,500,15,21))]
        foot_top=y+84+body_gap
        s+=[line(1,*[run(t,x,foot_top+dy,w,size,h)]) for t,x,dy,w,size,h in foot_pieces]
        s+=[line(1,run('not smoke, with higher odds for the heavy smokers in it',660,120,500,15,21)),
            line(1,run('and the second column goes on with more ordinary prose.',660,141,500,15,21)),
            line(1,run('The second column ends its last sentence at the foot.',660,y+63,500,15,21))]
        return s

    def test_a_foot_read_as_several_lines_moves_as_one_band(self):
        # The folio's box is tall; two more pieces of the same foot sit higher
        # in it (their centres inward of the folio row's centre), far to the
        # right, and the reading order puts them after the second column.
        pieces=[('101',82,0,32,17.7,23),('Journal Name Words',540,1,160,12.2,16),('(1999)',1110,1,45,12.6,3)]
        s=self.page(pieces)
        # Reading order: the folio between the halves of the sentence, the far
        # pieces after the second column's finished last line.
        order=[0,1,2,3,4,7,8,9,5,6]
        s=[s[i] for i in order]
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1600}))
        self.assertEqual(sorted(copy.scan_line(m['runs']) for m in moved),['(1999)','101','Journal Name Words'])
        self.assertEqual({m['edge'] for m in moved},{'bottom'})
        self.assertEqual([copy.scan_line(it['runs']) for it in out][3:5],
            ['the patients who smoked had more loss than those who did',
             'not smoke, with higher odds for the heavy smokers in it'])

    def test_a_speck_inside_the_foot_box_moves_with_it(self):
        pieces=[('0000-0000/99/000000-00$00.00/0 Publisher Town',137,0,460,15,16),("'",93,1,1,16.7,5)]
        s=self.page(pieces)
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1600}))
        self.assertEqual([copy.scan_line(m['runs']) for m in moved],
                         ['0000-0000/99/000000-00$00.00/0 Publisher Town',"'"])
        self.assertEqual(len(out),len(s)-2)

    def test_a_band_close_under_the_body_stays(self):
        # The band's inner edge, not its tallest piece, is 6 px under the body.
        pieces=[('101',82,8,32,17.7,23),('(1999)',1110,0,45,12.6,10)]
        s=self.page(pieces,body_gap=6)
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1600}))
        self.assertEqual(moved,[])
        self.assertEqual(texts(out),texts(s))

    def test_a_band_after_a_finished_sentence_stays(self):
        pieces=[('101',82,0,32,17.7,23),("'",93,1,1,16.7,5)]
        s=self.page(pieces,last='the patients who smoked had more loss than the others.')
        s[-3:-1]=[line(1,run('Not smoking was linked with less loss in the second',660,120,500,15,21)),
                  line(1,run('column, and it goes on with more ordinary prose.',660,141,500,15,21))]
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1600}))
        self.assertEqual(moved,[])

    def page_turn(self,first='measured.'):
        # Page 1 ends unfinished over a foot of two pieces; page 2 opens with
        # a one-word paragraph close set off by a paragraph blank (1 em), so
        # it passes the margin row test as well.
        return [line(1,run('the first column carries ordinary prose in plain words',80,1500,500,15,21)),
                line(1,run('and the last line of the page ends while it is still a',80,1521,500,15,21)),
                line(1,run('Invented Journal of Mimic Studies',480,1650,240,12.1,15)),
                line(1,run('101',94,1655,37,20.8,21)),
                line(2,run(first,94,154,79,14.7,17)),
                line(2,run('Gentle words open the next paragraph on the new page',94,186,490,15,17)),
                line(2,run('and its lines run at the usual pitch down the page.',94,207,490,15,17))]

    def test_a_one_word_close_on_the_next_page_is_the_continuation(self):
        s=self.page_turn()
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1754,2:1754}))
        self.assertEqual([copy.scan_line(m['runs']) for m in moved],['Invented Journal of Mimic Studies','101'])
        self.assertEqual([copy.scan_line(it['runs']) for it in out][1:3],
            ['and the last line of the page ends while it is still a','measured.'])

    def test_a_capitalised_first_line_is_no_continuation(self):
        s=self.page_turn(first='Measured.')
        out,moved=copy.scan_sentence_interruptions(s,geometry(s,{1:1754,2:1754}))
        self.assertEqual(moved,[])
        self.assertEqual(texts(out),texts(s))

if __name__=='__main__':
    unittest.main()
