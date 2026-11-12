"""Mixed font overhangs preserve reading order; accents need native shape and place."""
import importlib.util
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
copy=module('lineorder_copy','copy_paper.py')

def char(t,x,font='Body',width=5,serial=0):
    return dict(text=t,x0=x,y0=10,x1=x+width,y1=20,origin=(x,20),
                size=10,font=font,id=serial,paint_order=(serial,0),angle=0,
                adv_x1=x+5,adv_y1=20)

class LineOrder(unittest.TestCase):
    def run_piece(self,text,cs):
        return dict(id=text,kind='text',text=text,angle=0,_chars=cs,char_ids=[c['id'] for c in cs],
                    box_px=[min(c['x0'] for c in cs),min(c['y0'] for c in cs),max(c['x1'] for c in cs),max(c['y1'] for c in cs)])

    def test_overhang_does_not_partition_the_line_by_font(self):
        # The narrow italic overlaps its neighbor without covering it.
        cs=[char('e',-10,serial=0),char('x',-5,serial=1),char('a',0,width=7,serial=2),
            char('f',4,'Italic',width=4,serial=3),char('l',4,'Italic',width=4,serial=4),
            char('b',8,serial=5),char('8',13,'Bold',serial=6),char(':',18,serial=7)]
        row=[self.run_piece('exab:',cs[:3]+[cs[5],cs[7]]),self.run_piece('fl',cs[3:5]),self.run_piece('8',[cs[6]])]
        self.assertEqual(copy.positioned_prose_text(row,{}),'exaflb8:')
        self.assertEqual(sorted(i for e in row for i in e['char_ids']),list(range(8)))

    def test_true_overprint_is_not_interleaved(self):
        cs=[char('a',0,serial=0),char('b',0,'Other',serial=1),char('c',5,serial=2),char('d',10,serial=3)]
        row=[self.run_piece('acd',[cs[0],cs[2],cs[3]]),self.run_piece('b',[cs[1]])]
        self.assertIsNone(copy.positioned_prose_text(row,{}))

    def test_stacked_scripts_and_unverified_characters_abstain(self):
        a,b,c,d=char('a',0),char('2',2,serial=1),char('b',5,serial=2),char('c',10,serial=3)
        b['origin']=(2,15)
        row=[self.run_piece('abc',[a,c,d]),self.run_piece('2',[b])]
        self.assertIsNone(copy.positioned_prose_text(row,{}))
        b['origin']=(2,20);row[0]['text']='adc'
        self.assertIsNone(copy.positioned_prose_text(row,{}))

    def test_new_boundaries_join_dash_and_volume_without_inventing_spaces(self):
        cs=[char(t,i*5,serial=i) for i,t in enumerate('8:12–15')]
        row=[self.run_piece(':12 15',[cs[i] for i in [1,2,3,5,6]]),
             self.run_piece('8',[cs[0]]),self.run_piece('–',[cs[4]])]
        self.assertEqual(copy.positioned_prose_text(row,{}),'8:12–15')

    def test_unresolved_signs_do_not_enter_words_or_damaged_equations(self):
        cs=[char(t,i*5,serial=i) for i,t in enumerate('a�b')]
        row=[self.run_piece('ab',[cs[0],cs[2]]),self.run_piece('�',[cs[1]])]
        self.assertIsNone(copy.positioned_prose_text(row,{}))

    def test_italic_overhang_does_not_precede_its_opening_parenthesis(self):
        a=char('(',0,width=2,serial=0);a['adv_x1']=2
        f=char('f',-.5,'Italic',width=4.5,serial=1);f['origin']=(2,20);f['adv_x1']=5
        b=char(')',5,width=2,serial=2)
        prefix=[char(t,-25+i*5,serial=i+3) for i,t in enumerate('Test')]
        row=[self.run_piece('Test ()',prefix+[a,b]),self.run_piece('f',[f])]
        self.assertEqual(copy.positioned_prose_text(row,{}),'Test (f)')

    def test_same_baseline_math_fragments_abstain(self):
        cs=[char(t,i*5,serial=i) for i,t in enumerate('ijD')]
        self.assertIsNone(copy.positioned_prose_text([
            self.run_piece('ij',cs[:2]),self.run_piece('D',[cs[2]])],{}))
        cs=[char(t,i*5,serial=i) for i,t in enumerate('xdt^')]
        self.assertIsNone(copy.positioned_prose_text([
            self.run_piece('xdt',cs[:3]),self.run_piece('^',[cs[3]])],{}))

    def test_reordered_run_requires_its_whole_row_in_the_output(self):
        page={'copy_line_order':[dict(runs=['r1','r2'],after='The complete printed row.')]}
        placed=SimpleNamespace(contains=lambda s:s=='The complete printed row.')
        absent=SimpleNamespace(contains=lambda s:False)
        self.assertTrue(copy.positioned_run_placed({'id':'r1'},page,placed))
        self.assertFalse(copy.positioned_run_placed({'id':'other'},page,placed))
        self.assertFalse(copy.positioned_run_placed({'id':'r1'},page,absent))

    def test_raised_letter_claims_and_slash_identifiers_abstain(self):
        cs=[char(t,i*5,serial=i) for i,t in enumerate('The sample') if not t.isspace()]
        mark=dict(char('u',23,width=3,serial=10),y0=9,y1=12)
        self.assertIsNone(copy.positioned_prose_text([
            self.run_piece('The sample',cs),self.run_piece('u',[mark])],{}))
        cs=[char(t,i*5,serial=i) for i,t in enumerate('abc/defX')]
        self.assertIsNone(copy.positioned_prose_text([
            self.run_piece('abc/def',cs[:-1]),self.run_piece('X',cs[-1:])],{}))

    def test_detached_accent_cannot_strand_a_lowercase_word_on_another_row(self):
        a,n=char('a',0),char('n',6,serial=1)
        accent=dict(char('´',2,'Sign',2,2),y0=6,y1=8)
        word=self.run_piece('an',[a,n]);mark=self.run_piece('´',[accent])
        following=self.run_piece('as',[char('a',18,serial=3),char('s',24,serial=4)])
        page=dict(elements=[word,mark,following])
        copy.restore_prose_glyphs([page])
        rows=copy.text_rows(page['elements'])
        self.assertEqual(len(rows),1)
        self.assertEqual(copy.prose_row(rows[0],page)[0],'án as')
        self.assertEqual(page['copy_prose_glyphs'][0]['source_char_ids'],[2])

    def accent(self,contours,above=True,sign='�'):
        class Glyph:
            def draw(self,pen):
                for points in contours:
                    pen.moveTo(points[0])
                    for point in points[1:]:pen.lineTo(point)
                    pen.closePath()
        font=SimpleNamespace(basefont='Sign',cid=False,gmap={1:0},
            prog=SimpleNamespace(kind='cff',order=['unknown'],glyphs={'unknown':Glyph()}))
        reader=SimpleNamespace(sc_doc=lambda _:SimpleNamespace(fonts={'sign':font}))
        base=dict(char('a',0),size=15,adv_x1=6)
        accent=dict(char(sign,1,'Sign',2,1),size=15,y0=6 if above else 16,
                    y1=8 if above else 18,source_code=1)
        following=dict(char('n',6,serial=2),size=15)
        e=dict(id='r',kind='text',angle=0,text='a'+sign+' n',_chars=[base,accent,following],
               char_ids=[0,1,2],box_px=[0,6,11,20])
        p=dict(elements=[e],_table_pdf='fixture')
        with patch.dict(sys.modules,{'_copy_table_reader':reader}):copy.restore_prose_glyphs([p])
        return e['text']

    def circle(self,r,reverse=False):
        points=[(r*math.cos(i*math.pi/16),r*math.sin(i*math.pi/16)) for i in range(32)]
        return points[::-1] if reverse else points

    def test_hollow_ring_and_diagonal_accents_compose(self):
        self.assertEqual(self.accent([self.circle(10),self.circle(7,True)]),'ån')
        self.assertEqual(self.accent([[(0,0),(2,0),(10,10),(8,10)]]),'án')
        self.assertEqual(self.accent([[(0,10),(2,10),(10,0),(8,0)]]),'àn')

    def test_mapped_sign_diaeresis_still_composes_inside_a_mixed_run(self):
        dot=self.circle(1)
        self.assertEqual(self.accent([dot,[(x+3,y) for x,y in dot]],sign='€'),'än')

    def test_filled_disks_square_holes_and_baseline_slashes_are_not_accents(self):
        self.assertEqual(self.accent([self.circle(10)]),'a� n')
        self.assertEqual(self.accent([self.circle(10),self.circle(7)]),'a� n')
        self.assertEqual(self.accent([[(-10,-10),(10,-10),(10,10),(-10,10)],
                                     [(-7,-7),(-7,7),(7,7),(7,-7)]]),'a� n')
        self.assertEqual(self.accent([[(0,0),(2,0),(10,10),(8,10)]],False),'a� n')

if __name__=='__main__':unittest.main()
