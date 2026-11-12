"""Article labels, prefix markers, and headings sharing their paragraph's column."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('front4_boxer', ROOT / 'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)
spec = importlib.util.spec_from_file_location('front4_copy', ROOT / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def front(kicker='', prefix=True, shared_title=False, title_tail=False):
    specs = []
    if kicker: specs.append(('label', kicker, 50, 30 if shared_title else 40, 'title'))
    specs += [('title', 'Effects of material on surface structure', 110, 30, 'authors' if kicker and not shared_title else 'title'),
              ('byline', '1,2Ada Example and 3Ben Sample' if prefix else 'Ada Example1,2 and Ben Sample3', 155, 20, 'authors'),
              ('address', '1Department of Science', 195, 14, 'other'),
              ('address2', '2Department of Engineering', 220, 14, 'other'),
              ('address3', '3Department of Mathematics', 245, 14, 'other')]
    if title_tail:
        specs = [(bid,text,top+30 if bid not in ('label','title') else top,size,cls)
                 for bid,text,top,size,cls in specs]
        specs.append(('tail', 'Review', 140, 30, 'title'))
    chars = []; runs = []; blocks = []; classes = []
    for i, (bid, text, top, size, cls) in enumerate(specs):
        x = 30; ids = []
        for c in text:
            raised = bid == 'byline' and (c.isdigit() or c == ',')
            em = size * .6 if raised else size
            y = top - 3 if raised else top
            if not c.isspace():
                ids.append(len(chars))
                chars.append(dict(text=c, x0=x, x1=x+.45*em, y0=y, y1=y+.7*em,
                                  size=em, font='Regular', origin=(x,y+.7*em), adv_x1=x+.5*em))
            x += .5*em
        e = dict(id=bid, kind='text', text=text, box_px=[30,top-3,x,top+.7*size],
                 line=i, angle=0, size_px=size, run_size_px=size, char_ids=ids)
        runs.append(e); blocks.append(dict(id=bid, members=[bid], box_px=e['box_px']))
        classes.append(dict(id=bid, cls=cls, order=None, lines=1, size_px=size, box_px=e['box_px']))
    p = dict(page=1, elements=runs, blocks=blocks, art=[], region_box_px=[0,0,1200,1600],
             main_text=dict(body_size_px=16, blocks=classes))
    with patch.object(boxer, 'page_files', return_value=['page-01.json']), \
         patch.object(boxer, 'read_json', return_value=p), \
         patch.object(boxer, 'pdfium_characters', return_value=chars), \
         patch.object(boxer, 'write_json'):
        return boxer.authors_and_affiliations('unused', 'unused')


class FrontMatter(unittest.TestCase):
    def test_wrapped_title_can_end_in_the_word_review(self):
        self.assertEqual(front(title_tail=True)['title']['text'],
                         'Effects of material on surface structure Review')

    def test_same_size_label_cannot_discard_real_title_candidates(self):
        self.assertEqual(front('Original Article', shared_title=True)['title']['text'],
                         'Effects of material on surface structure')

    def test_larger_or_spaced_article_type_is_not_the_title(self):
        for label in ('Review', 'O R I G I N A L  A R T I C L E', 'Case Report'):
            with self.subTest(label=label):
                result = front(label)
                self.assertEqual(result['title']['text'], 'Effects of material on surface structure')
                self.assertEqual([a['name'] for a in result['authors']], ['Ada Example', 'Ben Sample'])

    def test_prefix_markers_belong_to_whole_names(self):
        result = front()
        self.assertEqual([(a['name'], a['markers']) for a in result['authors']],
                         [('Ada Example', ['1','2']), ('Ben Sample', ['3'])])
        self.assertEqual(result['checks']['status'], 'verified')

    def test_suffix_markers_still_end_names(self):
        self.assertEqual([(a['name'], a['markers']) for a in front(prefix=False)['authors']],
                         [('Ada Example', ['1','2']), ('Ben Sample', ['3'])])


def block(name, box, size=10, lines=5):
    return dict(id=name, text='Section heading' if size>10 else 'Ordinary paragraph text.',
                box_px=box, size=size, lines=lines)


class HeadingColumns(unittest.TestCase):
    def test_larger_supplement_body_is_not_a_display_heading(self):
        blocks = [block('short', [1,0,40,12], 13, 1),
                  block('long', [0,30,100,100], 13), block('next', [120,0,220,100])]
        normal, _ = boxer.reading_order_bands(blocks, [[0,100],[120,220],[2,45]], 10)
        # Removing the misleading document-wide size contrast must not change
        # the geometric order of a page whose text all uses the larger type.
        actual, _ = boxer.reading_order_bands(blocks, [[0,100],[120,220],[2,45]], 13)
        self.assertEqual([b['id'] for b in normal], [b['id'] for b in actual])

    def test_stacked_headings_share_the_smaller_paragraph_column(self):
        blocks = [block('section', [1,0,40,12], 13, 1),
                  block('subsection', [0,25,90,37], 13, 1),
                  block('opening', [0,50,100,100]), block('next', [120,0,220,100])]
        result, _ = boxer.reading_order_bands(blocks, [[0,100],[120,220],[2,45]], 10)
        self.assertEqual([b['id'] for b in result], ['section','subsection','opening','next'])

    def test_short_run_at_the_same_size_can_complete_a_longer_block(self):
        runs = [dict(id=str(i), text=t, box_px=[0,10+20*i,100,20+20*i], kind='text',
                     line=i, angle=0, size_px=13, run_size_px=13)
                for i,t in enumerate(['ORCID','Ada Example','https://orcid.org/0000-0001-',
                                      'Ben Sample','https://orcid.org/0000-0002-'])]
        runs.append(dict(id='tail',text='1234-5678',box_px=[102,50,180,60],kind='text',
                         line=2,angle=0,size_px=13,run_size_px=13))
        blocks=[dict(id='names',members=[str(i) for i in range(5)],box_px=[0,10,100,100]),
                dict(id='tail',members=['tail'],box_px=[102,50,180,60])]
        p=dict(page=2,elements=runs,blocks=blocks,floats=[],tables=[],region_box_px=[0,0,220,400],
               main_text=dict(columns=[[0,200]],blocks=[
                   dict(id='names',cls='main',order=1,lines=5,size_px=13,box_px=[0,10,100,100]),
                   dict(id='tail',cls='main',order=2,lines=1,size_px=13,box_px=[102,50,180,60])]))
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            prose,_,_=paper.read_page(p,10,[])
        self.assertEqual(len(prose),1)
        self.assertIn('1234-5678',prose[0]['lines'][2])

    def test_table_width_column_cannot_join_heading_into_adjacent_sentence(self):
        specs = [('body', 'The sentence continues with', [0,10,100,20], 10),
                 ('tail', 'ordinary words.', [0,30,100,40], 10),
                 ('head', '3.2 | A new section', [120,10,195,22], 13)]
        runs = [dict(id=n, text=t, box_px=box, kind='text', line=i, angle=0,
                     size_px=size, run_size_px=size) for i,(n,t,box,size) in enumerate(specs)]
        blocks = [dict(id='para', members=['body','tail'], box_px=[0,10,100,40]),
                  dict(id='heading', members=['head'], box_px=[120,10,195,22])]
        p = dict(page=2, elements=runs, blocks=blocks, floats=[], tables=[], region_box_px=[0,0,240,400],
                 main_text=dict(columns=[[0,100],[120,220],[0,220]], blocks=[
                     dict(id='para', cls='main', order=1, lines=2, size_px=10, box_px=[0,10,100,40]),
                     dict(id='heading', cls='main', order=2, lines=1, size_px=13, box_px=[120,10,195,22])]))
        with patch.object(paper, 'table_float_regions', lambda p, body: p):
            prose, _, _ = paper.read_page(p, 10, [])
        self.assertEqual([b['lines'] for b in prose],
                         [['The sentence continues with','ordinary words.'], ['3.2 | A new section']])

    def test_narrow_column_from_another_page_cannot_capture_heading(self):
        blocks = [block('heading', [1,0,40,12], 13, 1),
                  block('opening', [0,30,100,100]), block('next', [120,0,220,100])]
        result, cuts = boxer.reading_order_bands(blocks, [[0,100],[120,220],[2,45]], 10)
        self.assertEqual([b['id'] for b in result], ['heading','opening','next'])
        self.assertEqual(cuts, [])

    def test_short_opening_stays_below_heading_in_wider_paper_column(self):
        blocks = [block('heading', [2,0,80,30], 13, 3),
                  block('opening', [2,50,100,70], 10, 2), block('next', [120,0,220,70])]
        result, _ = boxer.reading_order_bands(blocks, [[2,80],[0,100],[120,220]], 10)
        self.assertEqual([b['id'] for b in result], ['heading','opening','next'])

    def test_spanning_heading_keeps_its_own_band(self):
        blocks = [block('heading', [0,0,220,12], 13, 1),
                  block('opening', [0,30,100,100]), block('next', [120,30,220,100])]
        result, cuts = boxer.reading_order_bands(blocks, [[0,100],[120,220],[0,220]], 10)
        self.assertEqual([b['id'] for b in result], ['heading','opening','next'])
        self.assertTrue(cuts)


if __name__ == '__main__': unittest.main()
