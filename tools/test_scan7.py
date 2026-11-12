"""Scan regressions (scan7): footnote zones, running heads by folio, captions to
their own end, figure text never body prose, table gates never body lines."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_scan7',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def run(text,x,y,w=240,size=12,h=None):
    return dict(text=text,box_px=[x,y,x+w,y+(size if h is None else h)],size_px=size)


def numbered(rs):
    return [dict(r,_scan_id=i) for i,r in enumerate(rs)]


def page(number,runs,width=800,height=1200):
    return dict(page=number,region_box_px=[0,0,width,height],elements=[],
                scan_evidence=dict(ocr_layer=True,ocr_runs=list(runs)))


def body(x=60,top=150,rows=20,w=300,size=18,text='Ordinary body prose with several printed words here'):
    return [run(text,x,top+i*22,w,size) for i in range(rows)]


class ScanSeven(unittest.TestCase):
    def test_running_head_with_moving_or_lost_folio_recurs(self):
        # AH05 geometry: "LISTGARTEN" alone, "50 LISTGARTEN", "52 LISTGARTEN".
        pages=[page(3,[run('LiSTGARTEN',370,87,110,16),*body()]),
               page(5,[run('50',52,88,16,16),run('LISTGARTEN',343,88,110,16),*body()]),
               page(7,[run('52',81,88,16,16),run('LISTGARTEN',372,90,110,16),*body()]),
               *[page(n,body()) for n in (2,4,6,8)]]
        furniture=copy.scan_furniture(pages)
        for n,ids in ((3,{0}),(5,{0,1}),(7,{0,1})):
            self.assertEqual(set(furniture[n]),ids,n)

    def test_header_band_with_agreeing_folio_is_furniture(self):
        # AH09 geometry: the only odd text page's head shares no words with
        # the even heads; its folio agrees with the folios of three pages.
        def head(number,left):
            return [run(str(854+number),1130 if left is None else 80,120,26,14),
                    *([] if left is None else [run(left,130,118,400,17)])]
        pages=[page(1,[*head(1,None),*body()],1220,1620),
               page(2,[*head(2,'EFFECTS OF FLAP PLACEMENT'),*body()],1220,1620),
               page(3,[run('Volume 65',104,100,74,15),run('Number 9',104,118,66,15),
                       run('MACHTEI, BEN-YEHOUDA',883,118,215,17),run('857',1123,118,25,15),
                       *body(top=162)],1220,1620),
               page(4,[*head(4,'EFFECTS OF FLAP PLACEMENT'),*body()],1220,1620)]
        self.assertEqual(set(copy.scan_furniture(pages)[3]),{0,1,2,3})
        # Without agreeing folios the unique band is not removed.
        pages[3]['scan_evidence']['ocr_runs'][0]['text']='999'
        pages[1]['scan_evidence']['ocr_runs'][0]['text']='998'
        self.assertFalse(set(copy.scan_furniture(pages)[3])&{0,1,2,3})

    def test_unmarked_small_type_page_foot_band_is_one_note_across_columns(self):
        # AH05 geometry: a funding note under both columns, read across.
        rs=numbered([*body(84,630,20,333,18.6),*body(441,630,20,333,18.6),
                     run('This investigation was supported by Grant DA-136',107,1089,325,14),
                     run('from the National Research Council of Canada,',440,1089,308,14),
                     run('Associate Committee on Dental Research,',107,1107,266,14)])
        notes=copy.scan_notes(rs,835,1237,[430])
        self.assertEqual(len(notes),1)
        self.assertEqual([copy.scan_line(row) for row in copy.scan_rows(notes[0]['runs'])],
            ['This investigation was supported by Grant DA-136 from the National Research Council of Canada,',
             'Associate Committee on Dental Research,'])

    def test_small_type_table_or_heading_under_its_caption_is_no_note(self):
        base=[*body(60,630,18,330,18.6)]
        table=numbered([*base,run('Average depth of the cases by graft material',60,1050,330,13),
                        run('Bone blend',60,1080,70,13),run('Less than 4.0',200,1080,80,13),run('0.3',360,1080,20,13),
                        run('Iliac marrow',60,1098,70,13),run('Greater than 4.0',200,1098,90,13),run('1.7',360,1098,20,13)])
        self.assertEqual(copy.scan_notes(table,800,1237,[]),[])
        heading=numbered([*base,run('Zusammenfassung',60,1050,120,13),
                          run('Die Topographie der ersten Molaren des Ober- und Unterkiefers',60,1068,330,13)])
        self.assertEqual(copy.scan_notes(heading,800,1237,[]),[])

    def test_marked_note_measures_its_letters_not_a_lone_marker(self):
        # AH09: the "*" marker row is set in a tiny OCR em.
        rs=numbered([*body(106,1281,8,494,18.6),run('*',105,1493,4,10,9),
                     run('* Periodontal Disease Research Center, Department of',106,1512,493,14.6),
                     run('University of New York, Buffalo, NY.',104,1533,263,15.6)])
        notes=copy.scan_notes(rs,1222,1620,[625])
        self.assertEqual(len(notes),1)
        self.assertEqual({r['_scan_id'] for r in notes[0]['runs']},{8,9,10})

    def test_body_size_sentence_opening_with_figure_reference_is_body(self):
        # AH05: "Fig. 3 resembles the type B cuticle which is" in body type.
        rs=numbered([*body(427,128,10,318,18.6),
                     run('Fig. 3 resembles the type B cuticle which is',427,400,318,18.6),
                     *body(427,422,10,318,18.6)])
        self.assertEqual(copy.scan_figure_regions(rs,800,gutters=[400])[0],[])
        # A caption in a smaller type still opens a figure block.
        rs=numbered([*body(427,128,10,318,18.6),
                     run('Fig. 3 Dense cuticular structure between the lamina',427,400,318,14),
                     run('and the cementum surface.',427,416,200,14)])
        self.assertEqual(len(copy.scan_figure_regions(rs,800,gutters=[400])[0]),1)

    def test_caption_owns_the_end_of_its_last_line(self):
        # AH09: OCR lost "(<=3" and grouped "mm) pockets." with a line of
        # the other column; the caption still owns it.
        rs=numbered([run('Figure 1. An overall positive correlation existed between',103,517,498,15.5,20),
                     run('postoperative sounding and pocket depth 2 years later.',102,539,498,15.1,21),
                     run('sites where flaps were positioned apically to the bone',103,559,496,15,20),
                     run('Table 2. Immediate Postsurgical Flap Placement',650,571,472,16.2,21),
                     run('shallow',103,579,51,15.4,16),run('mm) pockets.',189,580,87,14.2,19),
                     run('Level Changes After 2 Years',650,590,209,15.5,21)])
        figures,owned=copy.scan_figure_regions(rs,1222,gutters=[625])
        self.assertEqual(owned,{0,1,2,4,5})

    def test_table_beside_a_figure_keeps_to_its_column_and_body_lines(self):
        # AH09 page 3: a right-column table beside a left-column chart, the
        # end of the Results sentence and the DISCUSSION heading below it.
        fig=dict(kind='figure',runs=[],box_px=[103,1017,599,1100])
        rs=[run('Table 2. Immediate Postsurgical Flap Placement and Attachment',650,571,472,16,21),
            run('Level Changes After 2 Years',650,590,209,15,21)]
        for i in range(12):
            rs+=[run('_ %d'%i,692,671+i*20,22,14),run('-0.%d0 1.%d'%(i,i),863,671+i*20,98,14),
                 run('0.%d497'%i,1084,671+i*20,46,14)]
        rs+=[run('oo o',417,688,59,15),run('-4-',360,829,20,16),run('|R = 0.27;p=0.012]',134,989,96,11),
             run('(-0.56 mm) for those sites with sounding depth s 3 mm;',650,1004,497,18.3,26),
             run('however, none of these differences were statistically sig-',650,1029,497,18.6,25),
             run('nificant (P >0.05).',650,1053,160,19.4,26),
             run('DISCUSSION',650,1112,127,20.2,19),
             run('Marginal flap placement at or near the alveolar bone crest',651,1135,498,18.2,27),
             run('resulted in significantly shallower pockets (after 2 years)',651,1160,497,18.9,27),
             run('compared with sites where flaps were repositioned further',650,1185,499,18.4,26),
             run('away from the alveolar crest. These findings are in agree-',651,1210,497,18,26),
             run('tachment loss and/or some attachment gain but with deeper',103,1159,497,18.2,27),
             run('residual pockets 2 years later. We dichotomized sites',104,1183,497,18.1,25),
             run('operative sounding to explore the ideal or maximal values',103,1234,496,18.6,26),
             run('ment gain (0.28 mm) compared to a slight attachment loss',103,1532,497,18.2,27)]
        rs=numbered(rs)
        regions,owned=copy.scan_table_regions(rs,1222,[625],[fig],captioned_only=True)
        self.assertEqual(len(regions),1)
        texts={rs[i]['text'] for i in owned}
        self.assertFalse(any(t.startswith(('oo o','-4-','|R','(-0.56','however','nificant','DISCUSSION')) for t in texts))
        self.assertIn('Level Changes After 2 Years',texts)

    def test_display_title_owns_its_adjacent_display_lines(self):
        rs=[run('The Effect of Post-Surgical Flap',116,174,579,39.4,50),
            run('Placement on Probing Depth and',116,223,598,38.7,50),
            run('Attachment Level: A 2-Year',114,273,513,40.5,40),
            run('Longitudinal Study',115,324,344,42.1,48),
            run('Eli E. Machtei and Amos Ben-Yehouda',113,378,349,18.4,21),
            *body(114,465,10,742,18.4)]
        title=copy.scan_title_lines([rs[3]],rs,1222)
        self.assertEqual(sorted(r['text'] for r in title),sorted(r['text'] for r in rs[:4]))


if __name__=='__main__':
    unittest.main()
