"""Caption gutters, scan continuations and paragraph placement without paper fixtures."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_captions3',ROOT/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width=200,size=10,i=0):
    return dict(id=str(i),_scan_id=i,kind='text',text=text,angle=0,line=y,
                size_px=size,run_size_px=size,box_px=[x,y,x+width,y+size])


class CaptionColumns(unittest.TestCase):
    def columns(self):
        return [run(text,x,100+14*j,i=3*k+j) for k,(x,texts) in enumerate([
            (10,['Fig. 2. A detailed description','continues down the left column','then its final panel (B)']),
            (230,['The next panel begins here','and continues down this column','to its conclusion.'])])
            for j,text in enumerate(texts)]

    def test_owned_caption_reads_whole_columns_even_at_capitalized_panel(self):
        runs=self.columns()
        rows=c.figure_caption_rows(runs[::-1])
        self.assertEqual([r['id'] for row in rows for r in row],[str(i) for i in range(6)])
        self.assertEqual({r['id'] for row in rows for r in row},{r['id'] for r in runs})

    def test_full_width_line_vetoes_gutter(self):
        runs=self.columns()+[run('A spanning line joins the two sides.',10,142,420,i=6)]
        self.assertEqual(c.figure_caption_rows(runs),c.text_rows(runs))

    def test_short_side_labels_or_different_sizes_are_not_prose_columns(self):
        for kind in ('short','size','top'):
            runs=self.columns()
            for r in runs[3:]:
                if kind=='short':r['box_px'][2]=r['box_px'][0]+30
                if kind=='size':r['run_size_px']=r['size_px']=14
                if kind=='top':r['box_px'][1]+=28;r['box_px'][3]+=28
            self.assertEqual(c.figure_caption_rows(runs),c.text_rows(runs))


class ScanCaptionCarry(unittest.TestCase):
    def band(self):
        specs=[('Fig. 1. An earlier caption.',10,100,10),
               ('The earlier caption finishes.',10,114,10),
               ('Fig. 2. A caption ends in a split',10,132,10),
               ('word at this column break: inter-',10,146,10),
               ('nal continuation starts at band top',230,100,10),
               ('and finishes the caption.',230,114,10),
               ('Fig. 3. A separate caption.',230,132,10),
               ('The separate caption finishes.',230,146,10),
               ('Body heading',10,190,16),
               ('The following ordinary body paragraph.',230,190,12)]
        return [run(t,x,y,size=s,i=i) for i,(t,x,y,s) in enumerate(specs)]

    def test_tail_joins_last_caption_in_band_and_keeps_entry_anchor(self):
        rs=self.band();regions,owned=c.scan_figure_regions(rs,450,gutters=[220])
        middle=next(f for f in regions if rs[2] in f['runs'])
        self.assertEqual(middle['runs'],[rs[i] for i in (2,3,4,5)])
        self.assertEqual(middle['caption_tail_ids'],[4,5])
        self.assertEqual(middle['box_px'],[10,132,210,156])
        self.assertEqual(owned,set(range(8)))
        self.assertEqual(sum(len(f['runs']) for f in regions),8)

    def test_complete_sentence_size_change_or_new_label_vetoes_tail(self):
        for kind in ('complete','size','label'):
            rs=self.band()
            if kind=='complete':rs[3]['text']='The caption is complete.'
            if kind=='size':rs[4]['size_px']=14
            if kind=='label':rs[4]['text']='Fig. 4. Another caption.'
            regions,owned=c.scan_figure_regions(rs,450,gutters=[220])
            middle=next(f for f in regions if rs[2] in f['runs'])
            self.assertNotIn('caption_tail_ids',middle)

    def test_caption_after_split_sentence_waits_for_whole_paragraph(self):
        def line(text,page,x,y):
            r=run(text,x,y)
            return dict(kind='line',page=page,runs=[r],box_px=r['box_px'])
        first=line('It is necessary to combine',1,230,100)
        nextline=line('several approaches in treatment.',2,10,100)
        last=line('The same paragraph continues.',2,10,114)
        new=line('A new paragraph begins.',2,20,128)
        figure=dict(kind='figure',page=1,runs=[])
        self.assertEqual(c.scan_arrange_floats([first,figure,nextline,last,new]),
                         [first,nextline,last,figure,new])


if __name__=='__main__':unittest.main()
