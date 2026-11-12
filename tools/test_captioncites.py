"""A figure cited inside a running OCR caption sentence does not start a new caption (lane iss-15)."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_captioncites',ROOT/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def run(text,x,y,width=200,size=10,i=0):
    return dict(id=str(i),_scan_id=i,kind='text',text=text,angle=0,line=y,
                size_px=size,run_size_px=size,box_px=[x,y,x+width,y+size])


def caption(texts,pitch=10):
    return [run(t,10,100+pitch*i,i=i) for i,t in enumerate(texts)]


def starts(regions):
    return sorted(c.scan_line(c.scan_rows(f['runs'])[0]) for f in regions)


class CitedFigureInCaption(unittest.TestCase):
    def test_punctuated_cited_label_continues_the_caption(self):
        rs=caption(['Fig. 3. Higher power of the space','left of the tooth (center) shown in',
                    'Fig. 2. The fibers extend horizontally','across the crest of the bone.'])
        regions,owned=c.scan_figure_regions(rs,450,gutters=[])
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0]['runs'],rs)
        self.assertEqual(owned,set(range(4)))

    def test_unpunctuated_cited_label_continues_the_caption(self):
        rs=caption(['Fig. 14. Higher power of the surface of','Fig. 13 showing ligament fibers ex',
                    'tending to the cementum. Orig. mag. x 35.'])
        regions,_=c.scan_figure_regions(rs,450,gutters=[])
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0]['runs'],rs)

    def test_label_split_into_its_own_piece_still_reads_the_whole_line(self):
        rs=[run('Fig. 14.',10,100,width=30,i=0),run('Higher power of the surface of',50,100,width=160,i=1),
            run('Fig. 13 showing ligament fibers.',10,110,i=2)]
        regions,_=c.scan_figure_regions(rs,450,gutters=[])
        self.assertEqual(len(regions),1)
        self.assertEqual(len(regions[0]['runs']),3)

    def test_finished_line_gap_later_number_value_or_table_keeps_the_new_caption(self):
        cases={'sentence':(['Fig. 3. Higher power of the space shown.','Fig. 2. The fibers extend.'],10),
               'gap':(['Fig. 3. Higher power of the space shown in','Fig. 2. The fibers extend.'],16),
               'later':(['Fig. 3. Higher power of the space shown in','Fig. 4. The fibers extend.'],10),
               'bracket':(['Fig. 3. Higher power of the space (left)','Fig. 2. The fibers extend.'],10),
               'symbol':(['Fig. 3. Higher power of the space %','Fig. 2. The fibers extend.'],10),
               'hyphen':(['Fig. 3. Higher power of the peri-','Fig. 2. The fibers extend.'],10),
               'table':(['Fig. 3. Higher power of the space shown in','Table 2. The fibers extend.'],10)}
        for name,(texts,pitch) in cases.items():
            with self.subTest(name):
                regions,_=c.scan_figure_regions(caption(texts,pitch),450,gutters=[])
                first=next(f for f in regions if c.scan_line(f['runs']).startswith('Fig. 3.'))
                self.assertEqual(len(first['runs']),1)

    def test_helper_states_each_condition(self):
        f=c.scan_caption_cites_figure
        self.assertTrue(f('Fig. 3. Higher','shown in','Fig. 2. The',0,10))
        self.assertTrue(f('Figure 3 Higher','as in,','Figure 3 left',5,10))
        self.assertFalse(f('Fig. 3. Higher','shown in','Fig. 2. The',5.1,10))
        self.assertFalse(f('Fig. 3. Higher','shown in','Fig. 12. The',0,10))
        self.assertFalse(f('Fig. III. Higher','shown in','Fig. 2. The',0,10))
        self.assertFalse(f('Fig. 3. Higher','shown here.','Fig. 2. The',0,10))
        self.assertFalse(f('Fig. 3. Higher','shown at right;','Fig. 2. The',0,10))
        self.assertFalse(f('Fig. 3. Higher','shown at (right)','Fig. 2. The',0,10))
        self.assertFalse(f('Fig. 3. Higher','shown at right:','Fig. 2. The',0,10))
        self.assertFalse(f('Fig. 3. Higher','shown in','Table 2. The',0,10))


class OpenLineOfEitherCase(unittest.TestCase):
    """Re-ladder: the line above is open unless it ends a sentence; letter case carries no witness."""
    def test_helper_continues_after_capital_digit_or_comma(self):
        f=c.scan_caption_cites_figure
        for last in ('larger than in part B,','larger than in part B','set at level 4','set at level 4,',
                     'compare (left),','lower than in part b,','compare with'):
            with self.subTest(last):
                self.assertTrue(f('Fig. 12. Higher',last,'Fig. 2 inset',0,10))

    def test_helper_keeps_the_stop_after_a_sentence_end_of_either_case(self):
        f=c.scan_caption_cites_figure
        for last in ('larger than in part B.','set at level 4.','see part B?','larger in part B:','set at level 4)'):
            with self.subTest(last):
                self.assertFalse(f('Fig. 12. Higher',last,'Fig. 2 inset',0,10))

    def test_capital_letter_before_comma_continues_the_caption(self):
        rs=caption(['Figure 12. Wider field than in part B,','Figure 2 inset; the layers thin out',
                    'toward the right margin.'])
        regions,_=c.scan_figure_regions(rs,450,gutters=[])
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0]['runs'],rs)

    def test_digit_ending_continues_and_new_caption_after_a_gap_stays(self):
        rs=caption(['Fig. 9. Section cut at level 4','Fig. 3 with the layers marked.'])
        regions,_=c.scan_figure_regions(rs,450,gutters=[])
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0]['runs'],rs)
        rs=caption(['Fig. 9. Section cut at level B','Fig. 3. The layers marked.'],16)
        regions,_=c.scan_figure_regions(rs,450,gutters=[])
        first=next(f for f in regions if c.scan_line(f['runs']).startswith('Fig. 9.'))
        self.assertEqual(len(first['runs']),1)


if __name__=='__main__':unittest.main()
