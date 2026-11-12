"""OCR debris in a detached outer page band (lane r2-ocr)."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_r2ocr', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)

BODY = 'An ordinary body line of invented prose with several words.'


def run(text, x, y, width=100, size=12):
    return dict(text=text, box_px=[x, y, x+width, y+size], size_px=size)


def page(n, runs):
    return dict(page=n, region_box_px=[0, 0, 600, 800], elements=[], scan_evidence=dict(ocr_runs=runs))


def body(top=60, bottom=680, n=1):
    """Body lines whose words differ line by line (no recurring margin pattern)."""
    return [run(f'{BODY} Page {chr(64+n)*3} line {chr(97+k%26)*2}', x, y, 250)
            for k, (x, y) in enumerate((x, y) for x in (20, 320) for y in range(top, bottom, 14))]


class Debris(unittest.TestCase):
    def test_debris_property(self):
        for text in ('qx0Rb e 417 3', '22447-3(m0kTe', '((447471( Lo', 'e Ua', 'Dlx', '12(4):512-519 (2001)'):
            self.assertTrue(copy.scan_debris_run(dict(text=text)), text)
        for text in ('417', 'Annals of Invented Studies', 'non-users (Smith et al., 2001).', '7 Abc Defgh Ijklmn'):
            self.assertFalse(copy.scan_debris_run(dict(text=text)), text)

    def footer_pages(self, debris_page):
        """Four pages with a clean running foot; one page's foot is double struck and read as debris."""
        pages = []
        for n in range(1, 5):
            rs = body(n=n)
            if n == debris_page:
                rs += [run('22447-3(m0kTe', 20, 735, 250, 40), run('qx0Rb', 300, 736, 60, 14), run('e', 365, 736, 6, 10),
                       run('7', 560, 731, 6, 5),
                       run('Annals of Invented Studies', 240, 748, 140, 12),
                       run('12(4):512-519 (2001)', 20, 752, 120, 12), run(str(500+n), 560, 746, 20, 12),
                       run('33221(447471)011) Annals of Invented Studies', 20, 768, 400, 12)]
            else:
                rs += [run('Annals of Invented Studies', 240, 750, 140, 12),
                       run('12(4):512-519 (2001)', 20, 752, 120, 12), run(str(500+n), 560, 752, 20, 12)]
            pages.append(page(n, rs))
        return pages

    def test_debris_band_is_furniture_and_body_is_kept(self):
        pages = self.footer_pages(3)
        result = copy.scan_furniture(pages)
        nbody = len(body())
        foot = list(range(nbody, len(pages[2]['scan_evidence']['ocr_runs'])))
        self.assertEqual(sorted(result[3]), foot)
        whys = {result[3][i] for i in foot}
        self.assertIn('OCR non-word run in the detached outer page band', whys)
        self.assertIn('words of a confirmed repeated margin run in the detached outer page band', whys)
        for n in (1, 2, 4):
            self.assertTrue(all(i >= nbody for i in result[n]))

    def test_digit_runs_stay_folio_candidates(self):
        self.assertFalse(copy.scan_debris_run(dict(text='20 9')))
        self.assertFalse(copy.scan_debris_run(dict(text='447471')))

    def test_display_title_words_do_not_match_a_small_running_title(self):
        # Words of a confirmed running head printed much larger on page 1 (a title) are not furniture.
        pages = []
        for n in range(1, 5):
            rs = body(120, 680, n) + [run('Invented Running Title Here', 20, 20, 300, 30 if n == 1 else 10)]
            if n == 1:
                rs.append(run('((447471( Lo', 20, 56, 120, 10))
            pages.append(page(n, rs))
        result = copy.scan_furniture(pages)
        self.assertNotIn(len(body(120, 680)), result[1])

    def test_without_detaching_blank_nothing_changes(self):
        # The same debris directly under the body (less than one em of blank): not a detached band.
        rs = body(60, 740) + [run('22447-3(m0kTe', 20, 742, 250, 12), run('qx0Rb', 300, 742, 60, 12)]
        result = copy.scan_furniture([page(1, rs)])
        self.assertEqual(result[1], {})

    def test_words_in_a_debris_band_are_kept(self):
        # A footnote line of words shares the detached band with debris: the band stays as it is.
        rs = body() + [run('* Invented footnote about the sample of this study.', 20, 730, 300),
                       run('((447471( Lo', 20, 748, 120, 14)]
        self.assertEqual(copy.scan_furniture([page(1, rs)])[1], {})

    def test_table_note_values_in_a_proven_band_are_kept(self):
        # Four pages with a confirmed running foot; on page 2 a table note "Significant change, < 0.05"
        # shares the detached foot band: the note's "< 0.05" piece is not debris furniture.
        pages = []
        for n in range(1, 5):
            rs = body(n=n) + [run('Annals of Invented Studies', 240, 760, 140, 12)]
            if n == 2:
                rs += [run('Significant change from baseline,', 20, 744, 200, 12), run('< 0.05', 230, 744, 40, 12)]
            pages.append(page(n, rs))
        result = copy.scan_furniture(pages)
        nbody = len(body())
        self.assertNotIn(nbody+1, result[2]); self.assertNotIn(nbody+2, result[2])

    def test_debris_alone_without_a_running_band_is_kept(self):
        # Debris in a detached foot band with no confirmed running head or foot: no proof, kept.
        rs = body() + [run('22447-3(m0kTe', 20, 735, 250, 14), run('qx0Rb', 300, 736, 60, 14)]
        self.assertEqual(copy.scan_furniture([page(1, rs)])[1], {})

    def test_isolated_page_number_keeps_its_own_reason(self):
        rs = body() + [run('417', 290, 760, 20, 12)]
        result = copy.scan_furniture([page(1, rs)])
        self.assertEqual(result[1], {len(body()): 'isolated page number in the margin'})

    def test_numeric_table_row_at_page_foot_is_kept(self):
        # A table's last row at line pitch under the rows above it is not a detached band.
        rs = body(60, 600) + [run(f'{a} {b} ({c})', x, y, 80) for y in range(610, 760, 20)
                              for x, (a, b, c) in zip((20, 200, 400), ((1, 2, 3), (4, 5, 6), (7, 8, 9)))]
        result = copy.scan_furniture([page(1, rs)])
        self.assertEqual(result[1], {})


class DropCap(unittest.TestCase):
    def line(self, text, x, top, width=300, size=15):
        return dict(text=text, box_px=[x, top, x+width, top+size], size_px=size, baseline=top+.8*size)

    def test_initial_captured_with_its_own_last_line(self):
        # A two-line initial "W" read with the second line's first word; the first line holds "E report".
        first = self.line('E report here an invented finding that', 30, 100)
        donor = dict(text='W colleagues', box_px=[5, 99, 90, 141], size_px=15, baseline=137)
        rest = self.line('noted in earlier invented work', 100, 125, 230)
        rest['baseline'] = 137
        below = self.line('and the third line runs under the initial', 5, 148)
        out = copy.scan_drop_caps([first, donor, rest, below])
        self.assertEqual(out[0]['text'], 'WE report here an invented finding that')
        self.assertEqual(out[1]['text'], 'colleagues')
        rows = [copy.scan_line(r) for r in copy.scan_rows(out)]
        self.assertEqual(rows, ['WE report here an invented finding that', 'colleagues noted in earlier invented work',
                                'and the third line runs under the initial'])

    def test_tall_capital_without_a_continued_line_stays(self):
        # Negative: a tall "A" run with nothing continuing its baseline is left as read.
        first = self.line('Report of an invented finding', 30, 100)
        donor = dict(text='A Heading', box_px=[5, 99, 90, 141], size_px=15, baseline=137)
        out = copy.scan_drop_caps([first, donor])
        self.assertEqual([r['text'] for r in out], ['Report of an invented finding', 'A Heading'])


if __name__ == '__main__':
    unittest.main()
