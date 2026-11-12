"""Lane r3-panels: captioned list panels are floats owned by their caption; subfigure panel captions are caption lines."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1]/'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

N=[0]
def run(text,x,y,width=None,size=10):
    N[0]+=1
    return dict(id=f'run:{N[0]}',kind='text',text=text,angle=0,line=N[0],run_size_px=size,size_px=size,
                box_px=[x,y,x+(width or 6*len(text)),y+size],char_ids=[])

def fill(box): return dict(id=f'fill:{box[0]}:{box[1]}',kind='fill',box_px=list(box))
def image(box): return dict(id=f'image:{box[0]}:{box[1]}',kind='image',box_px=list(box))

WORDS='Crew cliff record moss count which have ridge dune and signal plot shale season'.split()
def item(k): return ' '.join(WORDS[(k+i)%len(WORDS)] for i in range(7))

def panel_page(caption_side='above', marker='- ', cells=False, caption=True):
    """a 300 x 200 panel at (400, 100) with six list rows; its caption above or below at the panel's width"""
    es=[fill([400,100,700,300])]
    for k in range(6):
        if cells: es += [run('Station', 410, 110+25*k, 60), run(str(100+k), 600, 110+25*k, 30)]
        else: es.append(run(marker+item(k), 410, 110+25*k, 270))
    if caption: es.append(run('Table 2. Points for field crews', 400, 80 if caption_side=='above' else 310, 200))
    # body columns beside the panel
    es += [run(item(k)+' '+item(k+1), 40, 100+15*k, 330) for k in range(10)]
    return dict(page=2, elements=es, tables=[], floats=[], blocks=[])

def runs_of(p): return {e['id']:e for e in p['elements'] if e['kind']=='text'}


class CaptionedPanels(unittest.TestCase):
    def test_caption_above_owns_the_bulleted_panel(self):
        p=panel_page('above'); found=c.captioned_panel_regions(p,runs_of(p),10)
        self.assertEqual(len(found),1); bx=found[0]
        self.assertEqual(bx['side'],'above'); self.assertEqual(bx['label'],'Table 2')
        self.assertEqual(len(bx['item_rows']),6)
        self.assertEqual([e['text'] for row in bx['caption_rows'] for e in row],['Table 2. Points for field crews'])

    def test_caption_below_and_numbered_items(self):
        p=panel_page('below', marker='1. '); found=c.captioned_panel_regions(p,runs_of(p),10)
        self.assertEqual([bx['side'] for bx in found],['below'])

    def test_box_label_is_a_panel_caption(self):
        p=panel_page('above')
        next(e for e in p['elements'] if e.get('text','').startswith('Table'))['text']='Box 1. Practice points'
        self.assertEqual([bx['label'] for bx in c.captioned_panel_regions(p,runs_of(p),10)],['Box 1'])

    def test_boxed_table_with_caption_stays_a_table(self):
        p=panel_page('above', cells=True)
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_uncaptioned_side_box_is_not_a_float(self):
        p=panel_page(caption=False)
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_caption_away_from_the_panel_does_not_link(self):
        p=panel_page('above')
        cap=next(e for e in p['elements'] if e.get('text','').startswith('Table'))
        cap['box_px']=[400,20,600,30]   # seven letter heights above the panel
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_caption_in_another_column_does_not_link(self):
        p=panel_page('above')
        cap=next(e for e in p['elements'] if e.get('text','').startswith('Table'))
        cap['box_px']=[40,80,240,90]
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_rule3_table_over_the_panel_wins(self):
        p=panel_page('above')
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10,drawn_tables=[[400,100,700,300]]),[])


def hung_page(markers, hang, cells=False):
    """a panel of items in a hanging marker column: marker at 410, text and continuations at 410 + hang"""
    es=[fill([400,100,700,330]), run('Box 1. Criteria used to accept a count', 400, 80, 220)]
    y=110
    for k,m in enumerate(markers):
        es.append(run(m, 410, y, 6*len(m)))
        es.append(run(str(100+k) if cells else item(k), 410+hang, y, 40 if cells else 250-hang)); y+=15
        if not cells: es.append(run(item(k+3), 410+hang, y, 200)); y+=15
    return dict(page=2, elements=es, tables=[], floats=[], blocks=[])


class HangingPanels(unittest.TestCase):
    def test_roman_markers_hung_a_quarter_inch(self):
        p=hung_page(['(i)','(ii)','(iii)','(iv)'], 40)
        self.assertEqual(len(c.captioned_panel_regions(p,runs_of(p),10)),1)

    def test_bullets_hung_half_an_inch(self):
        p=hung_page(['•']*4, 75)
        self.assertEqual(len(c.captioned_panel_regions(p,runs_of(p),10)),1)

    def test_hanging_list_under_an_inner_rule3_table(self):
        p=hung_page(['(i)','(ii)','(iii)'], 40)
        self.assertEqual(len(c.captioned_panel_regions(p,runs_of(p),10,drawn_tables=[[405,105,690,320]])),1)

    def test_values_after_the_markers_are_cells(self):
        p=hung_page(['(i)','(ii)','(iii)','(iv)'], 200, cells=True)
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_text_at_different_edges_is_not_a_hanging_list(self):
        p=hung_page(['(i)','(ii)','(iii)'], 40)
        texts=[e for e in p['elements'] if e.get('text','').startswith(('Crew','cliff','record','moss','count','which','have','ridge','dune','and','signal','plot','shale','season'))]
        for k,e in enumerate(texts[::2]): e['box_px'][0]+=30*k; e['box_px'][2]+=30*k
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_word_terms_beside_definitions_stay_a_table(self):
        p=hung_page(['Kiln','Slope','Ferry','Basin'], 60)
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])


def nested_page(sub_marker_x, sub_text_x, sub_markers=True):
    """bullets with text at 430, and sub-rows under the first item at sub_marker_x / sub_text_x"""
    es=[fill([400,100,700,330]), run('Box 2. Steps of the protocol', 400, 80, 200)]
    y=110
    for k in range(3):
        es += [run('•', 410, y, 5), run(item(k), 430, y, 240)]; y+=15
        if k==0:
            for j in range(2):
                if sub_markers: es.append(run('–', sub_marker_x, y, 6))
                es.append(run(item(j+5), sub_text_x, y, 200)); y+=15
    return dict(page=2, elements=es, tables=[], floats=[], blocks=[])


class NestedPanels(unittest.TestCase):
    def test_second_level_at_the_first_level_text_edge(self):
        p=nested_page(430, 450); found=c.captioned_panel_regions(p,runs_of(p),10)
        self.assertEqual(len(found),1); self.assertEqual([lv['text'] for lv in found[0]['levels']],[430,450])

    def test_second_level_markers_left_of_the_first_text_edge_are_cells(self):
        p=nested_page(380+30, 470)   # sub markers at the level-1 marker edge, text far right: not a nested level
        p['elements']=[e for e in p['elements'] if not (e.get('text')=='–')]+[run('–', 412, 125, 6), run('–', 412, 140, 6)]
        self.assertEqual(c.captioned_panel_regions(p,runs_of(p),10),[])

    def test_indented_continuation_without_marker_is_not_a_level(self):
        p=nested_page(0, 445, sub_markers=False); found=c.captioned_panel_regions(p,runs_of(p),10)
        self.assertEqual(len(found),1); self.assertEqual(len(found[0]['levels']),1)


def figure_page(captions, letters=None):
    """two pictures side by side over panel captions and a main caption"""
    es=[image([100,100,400,300]),image([450,100,750,300])]
    for x,t in zip((150,500),captions): es.append(run(t,x,312,len(t)*6,size=9))
    es.append(run('Figure 3. Two post types in the ninth month.',100,350,400,size=9))
    return dict(page=2,elements=es,tables=[],floats=[],blocks=[],region_box_px=[0,0,850,1100],
                main_text=dict(body_size_px=10,columns=[]))


class SubfigureCaptions(unittest.TestCase):
    def caption_ids(self,p): return [e['id'] for e in p['elements'] if e.get('text','').startswith('Figure')]

    def test_two_panel_captions_in_order(self):
        p=figure_page(['(a) Slate posts at dusk','(b) Cedar posts at dawn'])
        found=c.subfigure_captions(p,runs_of(p),self.caption_ids(p),[100,100,750,360],10)
        self.assertEqual([' '.join(e['text'] for r in rows for e in r) for rows,_ in found],
                         ['(a) Slate posts at dusk','(b) Cedar posts at dawn'])

    def test_bare_panel_letters_are_lettering(self):
        p=figure_page(['(a)','(b)'])
        self.assertEqual(c.subfigure_captions(p,runs_of(p),self.caption_ids(p),[100,100,750,360],10),[])

    def test_letters_must_run_without_a_gap(self):
        p=figure_page(['(a) Slate posts at dusk','(c) Cedar posts at dawn'])
        self.assertEqual(c.subfigure_captions(p,runs_of(p),self.caption_ids(p),[100,100,750,360],10),[])

    def test_panel_caption_does_not_close_the_graphic_search(self):
        p=figure_page(['(a) Slate posts at dusk counted from the north transect row','(b) Cedar posts'])
        ids=self.caption_ids(p); cb=c.hull(runs_of(p)[m]['box_px'] for m in ids)
        self.assertIsNotNone(c.caption_graphic_region(p,cb,ids,graphics_only=True))
        # a sustained prose line in the same place still closes it
        p['elements'][2]['text']='Slate posts at dusk counted from the north transect row'
        self.assertIsNone(c.caption_graphic_region(p,cb,ids,graphics_only=True))


if __name__=='__main__':
    unittest.main()
