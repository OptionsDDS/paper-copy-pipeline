"""Geometry and source-ownership regressions for front matter and reference rows."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def run(name, text, box, size=10):
    return dict(id=name, kind='text', text=text, box_px=box, line=1, angle=0,
                size_px=size, run_size_px=size)


def block(name, lines, box):
    return dict(lines=lines, meta=dict(id=name, box_px=box, size_px=10, cls='main'), page=1)


class FrontMatter(unittest.TestCase):
    def test_trailing_affiliation_is_emitted_once_beside_correspondence(self):
        joiner = SimpleNamespace(lines=lambda lines: ' '.join(lines))
        address = '1 Present Address: Department of Biology, Example University.'
        correspondence = 'Corresponding author. E-mail: ada@example.edu.'
        self.assertEqual(paper.without_front_text([correspondence, address], [address], joiner), correspondence)
        self.assertEqual(paper.without_front_text([address, correspondence], [address], joiner), correspondence)
        # A partial word match is not an independently printed record.
        self.assertEqual(paper.without_front_text(['biology'], ['ology'], joiner), 'biology')

    def test_abstract_column_precedes_body_and_keeps_article_info_separate(self):
        h = block('abstract', ['A B S T R A C T'], [80, 10, 120, 20])
        intro = block('intro', ['1. Introduction'], [0, 100, 70, 110])
        body = block('body', ['The main text starts here.', 'It continues.'], [0, 120, 70, 160])
        abstract = block('text', ['The abstract describes the research.', 'It ends here.'], [80, 35, 200, 80])
        blocks = [h, intro, body, abstract]
        result = paper.abstract_before_body(blocks, 10)
        self.assertEqual([b['meta']['id'] for b in result], ['abstract', 'text', 'intro', 'body'])
        self.assertEqual(result[0]['lines'], ['ABSTRACT'])
        self.assertTrue(result[1]['_abstract'])

    def test_correct_abstract_order_is_unchanged(self):
        blocks = [block('head', ['Abstract'], [0, 0, 100, 10]),
                  block('text', ['The research is described.', 'The abstract ends.'], [0, 20, 200, 50]),
                  block('intro', ['1. Introduction'], [0, 65, 100, 75])]
        self.assertIs(paper.abstract_before_body(blocks, 10), blocks)
        self.assertNotIn('_abstract', blocks[1])

    def test_float_caption_cannot_also_be_body_prose(self):
        cap = run('cap', 'Fig 1. A caption.', [0, 100, 200, 110])
        body = run('body', 'The body continues.', [0, 140, 200, 150])
        p = dict(page=1, elements=[cap, body], region_box_px=[0, 0, 220, 300], tables=[],
                 blocks=[dict(id=e['id'], members=[e['id']], box_px=e['box_px']) for e in (cap,body)],
                 floats=[dict(id='float', caption=cap['text'], blocks=['cap'], box_px=cap['box_px'])],
                 main_text=dict(columns=[[0,200]], blocks=[dict(id=e['id'], cls='main', order=i,
                    lines=1, size_px=10, box_px=e['box_px']) for i,e in enumerate((cap,body))]))
        with patch.object(paper, 'table_float_regions', lambda p, body: p):
            prose, floats, side = paper.read_page(p, 10, [])
        self.assertEqual([b['lines'] for b in prose], [[body['text']]])
        self.assertEqual(floats[0][2], cap['text'])
        self.assertEqual(side, [])

    def test_reference_accent_does_not_strand_initials(self):
        surname = run('surname', 'Muller', [0, 10, 36, 21], 16)
        surname['char_ids'] = list(range(6))
        surname['_chars'] = [dict(text=c,x0=i*6,y0=14 if c=='u' else 10,x1=i*6+5,y1=21,size=16)
                             for i,c in enumerate('Muller')]
        accent = run('accent', '¨', [7, 10, 11, 12], 16)
        accent['char_ids'] = [6]
        first = run('initials', 'HP,', [50,10.5,75,23.5], 16)
        second = run('other', 'Baker', [90,10,120,21], 16)
        last = run('last', 'J.', [135,10.5,145,23.5], 16)
        p = {}
        rows = paper.reference_text_rows([surname,first,second,last,accent], p)
        self.assertEqual(len(rows), 1)
        self.assertEqual(paper.prose_row(rows[0],p)[0], 'Müller HP, Baker J.')
        self.assertEqual(surname['text'], 'Muller')
        self.assertEqual(p['copy_reference_joins'][0]['target_char_id'],1)

    def test_currency_label_requires_two_dot_outline(self):
        class Glyph:
            def __init__(self, count): self.count=count
            def draw(self, pen):
                for x in range(self.count):
                    pen.moveTo((x*200,0)); pen.lineTo((x*200+100,0))
                    pen.lineTo((x*200+100,100)); pen.lineTo((x*200,100)); pen.closePath()
        e = run('accent', '€', [0, 0, 4.8, 1.6], 16)
        e['_chars'] = [dict(size=16, font='Synthetic', source_code=8)]
        prog = SimpleNamespace(kind='cff', order=['dots'], glyphs={'dots':Glyph(2)})
        font = SimpleNamespace(basefont='Synthetic', cid=False, prog=prog, gmap={8:0})
        reader = SimpleNamespace(sc_doc=lambda path: SimpleNamespace(fonts={1:font}))
        with patch.dict(paper.sys.modules, {'_copy_table_reader':reader}):
            self.assertEqual(paper.reference_accent_mark(e, {'_table_pdf':'unused'}), '\u0308')
            prog.glyphs['dots'] = Glyph(1)
            self.assertEqual(paper.reference_accent_mark(e, {'_table_pdf':'unused'}), '')


class TitleSelection(unittest.TestCase):
    def select(self, margin=False, rule=False, gap=0, lower=True, upper_author=False, wrapped=False):
        spec = importlib.util.spec_from_file_location('boxer', Path(__file__).resolve().parents[1] / 'standalone/element_boxer_sc.py')
        boxer = importlib.util.module_from_spec(spec); spec.loader.exec_module(boxer)
        texts = [('banner', 'Materials', 400, 140, 30, 'title')]
        if lower:
            texts += [('title', 'How surfaces affect microbial attachment', 60, 250+gap, 28, 'main'),
                      ('authors', 'Ada Lovelace, Alan Turing', 60, 310+gap, 18, 'main')]
        if wrapped: texts += [('title-tail', 'Properties of engineered interfaces', 400, 180, 30, 'title'),
                              ('same-size-byline', 'Jane Austen', 400, 220, 30, 'authors')]
        if upper_author: texts += [('first-byline', 'Jane Austen', 400, 180, 18, 'authors')]
        if margin: texts += [('header', 'Materials 42 (2024) 12345', 400, 50, 12, 'furniture')]
        chars=[]; runs=[]; blocks=[]; classes=[]
        for i,(name,text,x,y,size,cls) in enumerate(texts):
            ids=[];start=x
            for ch in text:
                if not ch.isspace():
                    ids.append(len(chars));chars.append(dict(text=ch,x0=x,y0=y,x1=x+.45*size,y1=y+.7*size,
                        size=size,font='Regular',origin=(x,y+.7*size),adv_x1=x+.5*size))
                x+=.5*size
            e=run(name,text,[start,y,x,y+.7*size],size);e.update(char_ids=ids,line=i+1)
            runs.append(e);blocks.append(dict(id=name,members=[name],box_px=e['box_px']))
            classes.append(dict(id=name,cls=cls,box_px=e['box_px'],size_px=size,order=None,lines=1))
        p=dict(elements=runs,blocks=blocks,main_text=dict(blocks=classes,body_size_px=16),
               region_box_px=[0,0,1200,1600],art=[])
        if rule:p['art']=[dict(kind='rule',box_px=[50,220,1150,222])]
        with patch.object(boxer,'page_files',return_value=['page-01.json']), \
             patch.object(boxer,'read_json',return_value=p), \
             patch.object(boxer,'pdfium_characters',return_value=chars), \
             patch.object(boxer,'write_json'):
            return boxer.authors_and_affiliations('unused','unused')

    def test_masthead_matching_margin_citation(self):
        self.assertTrue(self.select(margin=True).get('title_reselected'))

    def test_masthead_separated_by_rule_or_gap(self):
        self.assertTrue(self.select(rule=True).get('title_reselected'))
        self.assertTrue(self.select(gap=80).get('title_reselected'))

    def test_title_with_own_byline_survives_another_article_below(self):
        self.assertFalse(self.select(rule=True,gap=80,upper_author=True).get('title_reselected'))

    def test_wrapped_title_with_same_size_byline_is_preserved(self):
        self.assertFalse(self.select(rule=True,gap=80,wrapped=True).get('title_reselected'))

    def test_running_title_without_lower_byline_is_not_a_banner(self):
        self.assertFalse(self.select(margin=True,lower=False).get('title_reselected'))
        self.assertFalse(self.select().get('title_reselected'))


if __name__ == '__main__': unittest.main()
