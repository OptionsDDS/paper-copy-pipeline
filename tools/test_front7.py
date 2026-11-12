"""front7: series labels, repeated symbol labels, white surplus markers, repository covers, trailing labels."""
import importlib.util
import statistics
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


boxer = module('front7_boxer', ROOT/'standalone/element_boxer_sc.py')
paper = module('front7_copy', ROOT/'copy_paper.py')


def page(specs):
    """specs: (text, y, size, cls, block, font, white character offsets)."""
    chars = []; runs = []; blocks = []; classes = []
    for i, (text, y, size, cls, bid, font, white) in enumerate(specs):
        x = 20; ids = []
        for j, ch in enumerate(text):
            if not ch.isspace():
                ids.append(len(chars))
                chars.append(dict(text=ch, x0=x, x1=x+.45*size, y0=y, y1=y+.7*size, size=size, font=font,
                                  origin=(x, y+.7*size), adv_x1=x+.5*size, page=1, render_mode=0,
                                  fill_color=1.0 if j in white else 0.0, fill_space='DeviceGray'))
            x += .5*size
        e = dict(id=f'run:{i}', text=text, kind='text', line=i, angle=0, size_px=size, font=font,
                 run_size_px=size, char_ids=ids, box_px=[20, y, x, y+.7*size])
        runs.append(e)
        b = next((b for b in blocks if b['id'] == bid), None)
        if b: b['members'].append(e['id']); b['box_px'] = paper.hull([b['box_px'], e['box_px']])
        else:
            blocks.append(dict(id=bid, members=[e['id']], box_px=e['box_px']))
            classes.append(dict(id=bid, cls=cls, box_px=e['box_px']))
    return dict(page=1, elements=runs, blocks=blocks, art=[], region_box_px=[0, 0, 1000, 1400],
                main_text=dict(body_size_px=16, blocks=classes)), chars


def parse(fixture):
    with patch.object(boxer, 'page_files', return_value=['page-01.json']), \
         patch.object(boxer, 'read_json', return_value=fixture[0]), \
         patch.object(boxer, 'pdfium_characters', return_value=fixture[1]), \
         patch.object(boxer, 'front_backgrounds', return_value=[]), \
         patch.object(boxer, 'write_json'):
        return boxer.authors_and_affiliations('unused', 'unused')


class SeriesLabel(unittest.TestCase):
    def fixture(self, label_font='Light'):
        return page([('Commissioned Review', 100, 40, 'title', 'b1', label_font, ()),
                     ('Lasers in Periodontics: A Review of the Literature', 160, 30, 'authors', 'b2', 'Bold', ()),
                     ('Charles M. Cobb', 210, 20, 'main', 'b3', 'Bold', ()),
                     ('Background: the body of the abstract follows here and continues.', 300, 16, 'main', 'b4', 'Regular', ())])

    def test_label_in_another_face_is_article_information(self):
        a = parse(self.fixture())
        self.assertEqual(a['title']['text'], 'Lasers in Periodontics: A Review of the Literature')
        self.assertEqual([x['text'] for x in a.get('article_info', [])], ['Commissioned Review'])
        self.assertEqual(a['article_info'][0]['role'], 'series label')

    def test_same_face_opening_row_stays_title(self):
        a = parse(self.fixture(label_font='Bold'))
        self.assertEqual(a['title']['text'], 'Commissioned Review')


class SymbolLabels(unittest.TestCase):
    def test_repeated_stars_are_distinct_and_white_stars_are_not_printed(self):
        # The address rows print "****" in the text layer; the surplus stars are white.
        a = parse(page([('Properties of novel dental surfaces', 100, 30, 'title', 't', 'Bold', ()),
                        ('Ada Example, DDS*', 150, 20, 'authors', 'a', 'Regular', ()),
                        ('Ben Sample, DDS**', 172, 20, 'authors', 'a', 'Regular', ()),
                        ('****Professor, Department of Science,', 400, 12, 'other', 'f', 'Regular', (0, 1, 2)),
                        ('North University.', 416, 12, 'other', 'f', 'Regular', ()),
                        ('****Associate Professor, Department of Art,', 432, 12, 'other', 'f', 'Regular', (0, 1)),
                        ('Department of Art, South College.', 448, 12, 'other', 'f', 'Regular', ()),
                        ('****Reprint requests: Dr Ada Example, 1 Main Street.', 464, 12, 'other', 'f', 'Regular', (0, 1, 2, 3))]))
        self.assertEqual([(x['marker'], x['text'][:20]) for x in a['affiliations']],
                         [('*', 'Professor, Departmen'), ('**', 'Associate Professor,')])
        self.assertEqual(a['checks']['status'], 'verified')
        self.assertTrue(any(x['text'].startswith('****Reprint') for x in a.get('article_info', [])))


class Cover(unittest.TestCase):
    def leaf(self, *rows, size=16):
        return dict(elements=[dict(kind='text', text=t, run_size_px=size) for t in rows])

    def test_repeated_title_corroborates_a_wrapper(self):
        wrapper = dict(elements=[dict(kind='text', text='See discussions, stats, and author profiles', run_size_px=10),
                                 dict(kind='text', text='The Use of Enamel Matrix Derivative in Osseous Defects', run_size_px=28),
                                 dict(kind='text', text='CITATIONS 47 READS 1,587 SEE PROFILE ResearchGate', run_size_px=10)])
        article = self.leaf('The Use of Enamel Matrix Derivative in', 'Osseous Defects', 'Since Melcher first advanced')
        self.assertTrue(boxer.repository_cover(wrapper, [self.leaf('picture page'), article]))
        self.assertFalse(boxer.repository_cover(wrapper, [self.leaf('picture page'), self.leaf('Another article entirely')]))


class TrailingLabel(unittest.TestCase):
    def test_trailing_record_takes_its_symbol_label(self):
        J = paper.Joiner([])
        text = paper.without_front_text(['**Associate Professor, Department of Art.', '***Lecturer, Department of Law.'],
                                        ['***Lecturer, Department of Law.', '**Associate Professor, Department of Art.'], J)
        self.assertEqual(text, '')


if __name__ == '__main__':
    unittest.main()
