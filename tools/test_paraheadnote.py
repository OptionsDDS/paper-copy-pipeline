"""A line belongs to one unit (lane r2-dup): lines below a drawn table that head the
body paragraph under it leave the table (no table note), real table notes stay.
Invented geometry only; no paper's text."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_paraheadnote',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)

BODY=20.0


def run(i,x0,y,x1,size=BODY,h=None):
    return dict(id=f'run:{i}',kind='text',text='word '*8,angle=0,run_size_px=size,
                box_px=[x0,y,x1,y+(h if h is not None else size)])


def page(lines,block_of):
    runs={e['id']:e for e in lines}
    return runs,block_of


class ParagraphHead(unittest.TestCase):
    rule=[[80,300,580,302]]

    def column(self,head,head_pitch=25,head_size=BODY,head_right=580,gap=0,head_left=80):
        """`head` lines under the rule (table seed), then four body lines of the same block."""
        rs=[];y=340
        for i in range(head):
            rs.append(run(i,head_left if i==0 else 80,y,head_right if i==head-1 else 580,size=head_size));y+=head_pitch
        y+=gap-head_pitch+25
        for i in range(4):
            rs.append(run(100+i,80,y,580));y+=25
        runs={e['id']:e for e in rs}
        block_of={e['id']:'block:body' for e in rs}
        region={e['id'] for e in rs[:head]}
        return runs,block_of,region

    def test_paragraph_head_leaves_table(self):
        runs,block_of,region=self.column(2)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),region)

    def test_small_measured_size_at_body_pitch_leaves(self):
        # superscript-heavy lines measure small; the pitch and edges decide
        runs,block_of,region=self.column(2,head_size=.75*BODY)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),region)

    def test_indented_first_line_opens_paragraph(self):
        runs,block_of,region=self.column(3,head_left=110)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),region)

    def test_small_first_line_outside_table(self):
        # the table took only the paragraph's indented first line; its next line also measures small
        runs,block_of,region=self.column(2,head_size=.75*BODY,head_left=110)
        first_out=sorted(region,key=lambda m:runs[m]['box_px'][1])[-1]
        region.discard(first_out)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),region)

    def test_paragraph_below_not_body_size_stays(self):
        runs,block_of,region=self.column(2)
        for m,e in runs.items():
            if m not in region:e['run_size_px']=.7*BODY
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),set())

    def test_note_in_smaller_pitch_stays(self):
        runs,block_of,region=self.column(2,head_pitch=17,head_size=14)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),set())

    def test_note_with_short_last_line_stays(self):
        runs,block_of,region=self.column(2,head_right=400)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),set())

    def test_note_separated_by_gap_stays(self):
        runs,block_of,region=self.column(2,gap=15)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),set())

    def test_other_block_stays(self):
        runs,block_of,region=self.column(2)
        for m in region:block_of[m]='block:note'
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,self.rule,BODY),set())

    def test_no_drawn_structure_no_release(self):
        runs,block_of,region=self.column(2)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,[],BODY),set())

    def test_lines_above_the_rule_stay(self):
        runs,block_of,region=self.column(2)
        self.assertEqual(copy.paragraph_head_lines(region,runs,block_of,[[80,600,580,602]],BODY),set())


if __name__=='__main__':
    unittest.main()
