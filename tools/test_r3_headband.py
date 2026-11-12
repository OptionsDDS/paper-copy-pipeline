"""Lane r3-headband: in-column headings in fake small capitals, a heading at the top of a column witnessed only
by body text kept outside the furniture band, and a one-line bold subheading above a paragraph broken across a
page. All texts and geometry are invented; no literal from any paper.

R1 rule 1: a run of capitals whose first letter is set larger than the rest (a section number before it allowed)
   records lead_size_px (that letter's size); a run of ordinary words, or of capitals at one size, records nothing.
R2 rule 6: a short bold line of fake small capitals directly above body text in its column is a heading at its
   position, measured at its first letter's size; the same line without the larger first letter (true small type)
   keeps its class.
R3 rule 6: a short bold heading directly above body text kept outside the furniture band (the only witness of its
   column on the title page) opens that column.
R4 copier: a one-line block wholly in a bold or bold-italic face (names ending -B / -BI included) never opens a
   lifted sentence; a two-line paragraph in the body face still does.
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


paper = module('copy_paper', 'copy_paper.py')
boxer = module('element_boxer_sc', 'standalone/element_boxer_sc.py')
import sys
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__name__ != 'SCImportGuard']   # the boxer's guard is for the boxer


def run(name, text, x, y, width=220, size=10, height=10, font='Regular', **kw):
    return dict(id=name, kind='text', text=text, box_px=[x, y, x + width, y + height], angle=0, line=y,
                run_size_px=size, size_px=size, font=font, flags=[], **kw)


def page(number, groups):
    es = [e for _, members in groups for e in members]
    blocks = [dict(id=name, members=[e['id'] for e in members], kinds=['text'],
                   box_px=paper.hull(e['box_px'] for e in members), text_lines=len(members),
                   text=' '.join(e['text'] for e in members)) for name, members in groups]
    return dict(page=number, elements=es, blocks=blocks, tables=[], floats=[], art=[], unpaired=[],
                region_box_px=[0, 0, 600, 1000], reading_angle=0)


def body(prefix, word, x, top, n, width=240):
    return [run(f'{prefix}{j}', f'{word} paragraph line has several ordinary words and goes on', x, top + 15 * j, width=width)
            for j in range(n)]


def classify(pages):
    with tempfile.TemporaryDirectory(dir=ROOT) as folder:
        for p in pages:
            Path(folder, f"page-{p['page']:02d}.json").write_text(json.dumps(p))
        boxer.main_text(folder, draw=False)
        return [json.loads(Path(folder, f"page-{p['page']:02d}.json").read_text()) for p in pages]


class SmallCapsHeading(unittest.TestCase):
    def pages(self, lead):
        out = []
        for i, word in enumerate(['Red', 'Green', 'Blue'], 1):
            groups = [('left-a', body('la', word, 40, 100, 12)), ('right', body('r', word, 320, 100, 40))]
            if i == 2:
                extra = dict(lead_size_px=9.6) if lead else {}
                groups += [('heading', [run('heading', 'MATERIALS AND METHODS', 105, 310, width=110, size=6.9,
                                            height=7, font='ABCDEF+Sans-B', **extra)]),
                           ('left-b', body('lb', word, 40, 330, 30))]
            else:
                groups += [('left-b', body('lb', word, 40, 310, 31))]
            out.append(page(i, groups))
        return out

    def test_fake_small_caps_heading_is_main_at_its_position(self):
        blocks = {b['id']: b for b in classify(self.pages(True))[1]['main_text']['blocks']}
        self.assertEqual((blocks['heading']['cls'], blocks['heading']['why']), ('main', 'heading before main text in its column'))
        self.assertLess(blocks['left-a']['order'], blocks['heading']['order'])
        self.assertLess(blocks['heading']['order'], blocks['left-b']['order'])

    def test_true_small_type_line_keeps_its_class(self):
        blocks = {b['id']: b for b in classify(self.pages(False))[1]['main_text']['blocks']}
        self.assertEqual(blocks['heading']['cls'], 'other')


class TopOfLateColumn(unittest.TestCase):
    def pages(self, bold=True):
        out = []
        for i, word in enumerate(['Red', 'Green', 'Blue'], 1):
            foot = run(f'foot{i}', 'Journal of invented results volume one', 40, 960, width=300, size=8)
            folio = run(f'folio{i}', str(10 + i), 560, 975, width=12, size=8)
            if i == 1:
                head = run('heading', 'Introduction', 40, 600, width=90, size=12, height=12,
                           font='ABCDEF+Arial-Bold' if bold else 'ABCDEF+Arial')
                groups = [('title', [run('title', 'An invented title for a test paper', 40, 60, width=500, size=24, height=24)]),
                          ('authors', [run('authors', 'Ann Example, Bo Sample', 40, 110, width=200, size=12, height=12)]),
                          ('heading', [head]),
                          ('left', body('l', word, 40, 640, 20) + [foot]),
                          ('right', body('r', word, 320, 600, 24)),
                          ('folio', [folio])]
            else:
                groups = [('left', body('l', word, 40, 80, 50) + [foot]), ('right', body('r', word, 320, 80, 50)),
                          ('folio', [folio])]
            out.append(page(i, groups))
        return out

    def test_heading_above_recovered_body_opens_the_column(self):
        res = classify(self.pages())[0]['main_text']
        blocks = {b['id']: b for b in res['blocks']}
        left = next(b for k, b in blocks.items() if k.startswith('left') and b['cls'] == 'main')
        self.assertEqual(left['why'], 'body text retained outside the furniture band')
        self.assertEqual((blocks['heading']['cls'], blocks['heading']['why']), ('main', 'heading before main text in its column'))
        self.assertLess(blocks['heading']['order'], left['order'])

    def test_plain_line_above_recovered_body_stays_outside(self):
        res = classify(self.pages(bold=False))[0]['main_text']
        blocks = {b['id']: b for b in res['blocks']}
        self.assertEqual(blocks['authors']['cls'], 'authors')
        self.assertNotEqual(blocks['heading']['cls'], 'main')


class LeadSize(unittest.TestCase):
    def test_rule1_records_first_letter_of_fake_small_caps(self):
        try:
            import cairo
        except ImportError:
            self.skipTest('pycairo unavailable')
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            pdf = os.path.join(folder, 'p.pdf')
            sf = cairo.PDFSurface(pdf, 300, 300); ctx = cairo.Context(sf)
            ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            x = 40
            for t, z in (('M', 9), ('ETHODS', 6.5)):
                ctx.set_font_size(z); ctx.move_to(x, 60); ctx.show_text(t); x += ctx.text_extents(t).x_advance
            x = 40
            for t, z in (('2. ', 6.5), ('R', 9), ('ESULTS', 6.5)):
                ctx.set_font_size(z); ctx.move_to(x, 90); ctx.show_text(t); x += ctx.text_extents(t).x_advance
            ctx.select_font_face('sans'); ctx.set_font_size(9)
            ctx.move_to(40, 120); ctx.show_text('Ordinary words at one size')
            ctx.move_to(40, 160); ctx.show_text('CAPITALS AT ONE SIZE')
            sf.finish()
            out = os.path.join(folder, 'out')
            r = subprocess.run(['/usr/bin/python3', '-I', '-S', str(ROOT / 'standalone/element_boxer_sc.py'), '--pdf', pdf,
                                '--page', '1', '--out', out, '--no-draw'], env={'PATH': '/usr/bin'},
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            files = sorted(Path(out).glob('*.json')) or sorted(Path(out).parent.glob('out*.json'))
            d = json.loads(files[0].read_text())
            runs = {e['text']: e for e in d['elements'] if e['kind'] == 'text'}
            self.assertAlmostEqual(runs['METHODS']['lead_size_px'], 9 * 150 / 72, places=1)
            self.assertAlmostEqual(runs['2. RESULTS']['lead_size_px'], 9 * 150 / 72, places=1)
            self.assertNotIn('lead_size_px', runs['Ordinary words at one size'])
            self.assertNotIn('lead_size_px', runs['CAPITALS AT ONE SIZE'])


def para(text, page=1, col=0, top=100, bottom=200, full=True, flush=True, size=20.0, face='ABCDEF+Sans-Regular', rows=2, **kw):
    left = 100 + col * 500
    item = dict(kind='para', text=text, page=page, box=[left, top, left + 450, bottom], flow_parts=[(page, [left, top, left + 450, bottom])],
                flow_start=(page, col, flush), flow_end=(page, col, full), style=(size, face), **kw)
    item['start_rows'] = dict(rows=[[left, top + 25 * k, left + 450, top + 25 * k + 20] for k in range(rows)], col=(left, left + 450))
    return item


class StyledSubheading(unittest.TestCase):
    def pages(self): return [dict(page=1), dict(page=2)]

    def items(self, face, rows):
        return [para('Gain in attachment after a graft over a deep recession at the site', col=1, top=1300, bottom=1320, face=face, rows=rows),
                para('Each site was measured at baseline and at six months by one examiner who', col=1, top=1340, bottom=1440),
                dict(kind='page', page=2),
                para('was blinded to the group, and the readings were averaged for every site.', page=2, col=0, top=80, bottom=300)]

    def test_one_line_bold_italic_subheading_moves_nothing(self):
        for face in ('ABCDEF+Sans-BI', 'ABCDEF+Sans-B', 'ABCDEF+Sans-BoldItalic'):
            items = self.items(face, 1)
            out = paper.lift_inserted_blocks(list(items), self.pages(), 20.0, paper.Joiner([]))
            self.assertEqual([x.get('text', '')[:12] for x in out], [x.get('text', '')[:12] for x in items], face)
            self.assertTrue(paper.stream_styled_heading(items[0]))

    def test_body_face_open_paragraph_still_lifts_the_foreign_block(self):
        items = self.items('ABCDEF+Sans-Regular', 2)
        items[1]['style'] = (20.0, 'GHIJKL+Serif-Italic')
        out = paper.lift_inserted_blocks(list(items), self.pages(), 20.0, paper.Joiner([]))
        self.assertFalse(paper.stream_styled_heading(items[0]))
        self.assertEqual(out[-1]['kind'], 'side')

    def test_two_line_bold_block_is_not_a_subheading(self):
        self.assertFalse(paper.stream_styled_heading(self.items('ABCDEF+Sans-B', 2)[0]))


if __name__ == '__main__':
    unittest.main()
