"""Body text at page and column joins never enters a table gate (joins2).

Rules: rule 9's text-cue witness makes a line continuing an unfinished body
sentence body, never table content; a table's indented smaller entries
(bullet columns) are table lines, not caption text; "Table N" printed in the
body flow is a sentence, not a caption. Fixtures are synthetic geometry
modelled on the measured AG02 (scan) and AG08 (native) pages.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_joins2',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(i,text,x,y,width,size):
    return dict(_scan_id=i,text=text,box_px=[x,y,x+width,y+size+4],size_px=size)


def boxed_table_page(tail=True):
    """A left-column boxed table: caption in body size, indented smaller bullets,
    then the body tail of the previous page's sentence and a heading."""
    rs=[run(0,'Table 1. The pathogenesis of periodontitis:',148,174,394,22.7),
        run(1,'new findings and new perspectives on the',148,196,388,22.7),
        run(2,'bacterial challenge',148,219,173,22.7)]
    y=260;i=3
    for k in range(6):
        for text in ('A limited number of specific bacteria are essential',
                     'to initiate disease and fuel progression but',
                     'periodontitis.'):
            rs.append(run(i,text,180,y,390 if len(text)>20 else 105,19.8));i+=1;y+=18
    if tail:
        rs+=[run(i,'lations and for possible treatment of recalcitrant',138,y+70,478,22.7),
             run(i+1,'cases.',138,y+97,54,22.7)];i+=2
    rs.append(run(i,'Subgingival microbial plaque is a biofilm',139,y+150,384,22.7));i+=1
    for k in range(4):
        rs.append(run(i,'Costerton et al. have defined biofilm as matrix enclosed',139,y+205+27*k,482,22.7));i+=1
    return rs


class TextCue(unittest.TestCase):
    def test_ported_text_cue_rule(self):
        self.assertTrue(copy.text_continues('families and popu-','lations and for'))
        self.assertTrue(copy.text_continues('cohort or longitudinal studies,','case-controlled studies'))
        self.assertTrue(copy.text_continues('soft\xad','ware'))
        # Text never witnesses a break, and a capital start is not confirmed.
        self.assertFalse(copy.text_continues('the study ended.','then we'))
        self.assertFalse(copy.text_continues('are summarized in','Table 7. In this volume'))
        self.assertFalse(copy.text_continues('x -','lowercase'))


class ScanCaptionEntries(unittest.TestCase):
    def test_indented_smaller_bullets_are_table_lines_not_caption(self):
        rs=boxed_table_page(tail=False)
        regions,owned=copy.scan_table_regions(rs,1275,[639],captioned_only=True)
        self.assertEqual(len(regions),1)
        t=regions[0]
        self.assertEqual(t['caption'],'Table 1. The pathogenesis of periodontitis: new findings and new '
                         'perspectives on the bacterial challenge')
        lines=[r['text'] for r in t['runs'] if r['_scan_id'] not in t['caption_ids']]
        # Every bullet line, including each bullet's last word, stays in order.
        self.assertEqual(len(lines),18)
        self.assertEqual(lines[2],'periodontitis.')

    def test_body_tail_continuing_previous_page_ends_the_table(self):
        rs=boxed_table_page()
        regions,owned=copy.scan_table_regions(rs,1275,[639],captioned_only=True,
                                              previous_line='vention in high-risk individuals, families and popu-')
        texts={r['text'] for r in regions[0]['runs']}
        self.assertNotIn('lations and for possible treatment of recalcitrant',texts)
        self.assertNotIn('cases.',texts)
        self.assertIn('periodontitis.',texts)

    def test_without_an_unfinished_sentence_the_old_restart_rule_stands(self):
        rs=boxed_table_page()
        regions,owned=copy.scan_table_regions(rs,1275,[639],captioned_only=True,
                                              previous_line='the paragraph ended here.')
        texts={r['text'] for r in regions[0]['runs']}
        self.assertIn('lations and for possible treatment of recalcitrant',texts)

    def test_table_label_in_the_body_flow_is_a_sentence(self):
        rs=[run(0,'influence the shared common events. Important',137,168,479,22.7),
            run(1,'new findings and perspectives are summarized in',137,195,479,22.7),
            run(2,'Table 7. In this volume, Salvi et al. (60) discuss fac-',137,223,480,22.7),
            run(3,'tors that can affect shared events in the pathogenesis',137,250,479,22.7),
            run(4,'Diabetes mellitus',138,667,161,22.7)]
        regions,owned=copy.scan_table_regions(rs,1275,[639],captioned_only=True)
        self.assertEqual(regions,[])
        # The same label after a printed gap stays a caption.
        rs[2]=run(2,'Table 7. In this volume, Salvi et al. (60) discuss fac-',137,262,480,22.7)
        rs[3]=run(3,'1.2 3.4 5.6',137,300,80,22.7)
        regions,owned=copy.scan_table_regions(rs,1275,[639],captioned_only=True)
        self.assertEqual(len(regions),1)


class NativeContinuation(unittest.TestCase):
    def page(self):
        def e(i,text,x,y,w):
            return dict(id=f'run:{i}',kind='text',text=text,angle=0,box_px=[x,y,x+w,y+18])
        els=[e(1,'Total number of articles 278 100.0',106,724,460),
             e(2,'case-controlled studies, non-controlled case studies,',94,784,502),
             e(3,'descriptive studies, in vivo animal studies, and in vitro',94,809,503)]
        return dict(page=3,elements=els,blocks=[dict(id='block:32',members=['run:2','run:3'])],
                    main_text=dict(columns=[[93,598],[635,1140]]))

    def test_confirmed_join_marks_first_target_row(self):
        p=self.page()
        order=dict(edges=[dict(source=dict(page=2,id='block:4'),target=dict(page=3,id='block:32'),
                               continuation='continue',grammar=dict(confirms_continuation=True,
                               reason='no terminal punctuation + lowercase'))])
        with tempfile.TemporaryDirectory() as d:
            Path(d,'body-order.json').write_text(json.dumps(order))
            copy.mark_body_continuations(d,[p])
        self.assertEqual(p['_copy_continuation_runs'],['run:2'])

    def test_table_cells_classed_main_are_not_body_continuations(self):
        # Y08: rule 6 classed a continued table's cells as main blocks and
        # rule 9 confirmed "AUG" -> "ePTFE, ABG" by text alone.
        p=dict(page=7,elements=[dict(id='run:1',kind='text',text='ePTFE, ABG',angle=0,box_px=[465,446,550,460])],
               blocks=[dict(id='block:27',members=['run:1'])],main_text=dict(columns=[[132,603],[634,1106]]))
        order=dict(edges=[dict(source=dict(page=7,id='block:26'),target=dict(page=7,id='block:27'),
                               continuation='continue',grammar=dict(confirms_continuation=True))])
        with tempfile.TemporaryDirectory() as d:
            Path(d,'body-order.json').write_text(json.dumps(order))
            copy.mark_body_continuations(d,[p])
        self.assertNotIn('_copy_continuation_runs',p)

    def test_unconfirmed_or_undecided_join_marks_nothing(self):
        for continuation,confirmed in (('continue',False),('undecided',True),('break',False)):
            p=self.page()
            order=dict(edges=[dict(source=dict(page=2,id='block:4'),target=dict(page=3,id='block:32'),
                                   continuation=continuation,grammar=dict(confirms_continuation=confirmed))])
            with tempfile.TemporaryDirectory() as d:
                Path(d,'body-order.json').write_text(json.dumps(order))
                copy.mark_body_continuations(d,[p])
            self.assertNotIn('_copy_continuation_runs',p)

    def test_shaded_island_stops_at_continuing_body_row(self):
        def t(i,text,x,y,w):
            return dict(id=f'run:{i}',kind='text',text=text,angle=0,box_px=[x,y,x+w,y+16],run_size_px=16)
        els=[];i=0
        for k in range(4):
            y=300+40*k
            for j,(a,b) in enumerate(((93,300),(300,450),(450,598))):
                els.append(dict(id=f'fill:{k}{j}',kind='fill',angle=0,box_px=[a,y,b,y+38]))
            for text,x,w in ((f'Studies group {k}',106,150),(str(10+k),388,26),(f'{k}.5',529,30)):
                els.append(t(i,text,x,y+10,w));i+=1
        els.append(t(i,'case-controlled studies, non-controlled case studies,',94,484,502))
        p=dict(page=3,elements=els,main_text=dict(columns=[[93,598],[635,1140]]),floats=[])
        taken=lambda:[e['id'] for _,_,sel in copy.shaded_cell_regions(p,16) for e in sel]
        self.assertIn(f'run:{i}',taken())      # an unshaded final row joins without the witness
        p['_copy_continuation_runs']=[f'run:{i}']
        self.assertNotIn(f'run:{i}',taken())
        self.assertEqual(len(taken()),12)

    def test_missing_rule9_output_is_neutral(self):
        p=self.page()
        with tempfile.TemporaryDirectory() as d:copy.mark_body_continuations(d,[p])
        self.assertNotIn('_copy_continuation_runs',p)


if __name__=='__main__':
    unittest.main()
