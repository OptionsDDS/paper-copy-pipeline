"""Scan page 1: a key-word side strip beside a one-column abstract (lane r2-sidekw).

The strip is set in a smaller type than the page's running text. Its wrapped lines can be as long as
prose lines; they stay the strip's. The strip's band closes the block it stands beside, so that block
reads whole first. Invented text only.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_sidekw', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)

PROSE = 'the measured layer was thinner in each group while older sites kept a band'


def run(text, x, y, width, size):
    return dict(text=text, box_px=[x, y, x+width, y+size], size_px=size)


def copied(runs):
    page = dict(page=1, region_box_px=[0, 0, 1200, 1600], elements=[], scan_evidence=dict(ocr_runs=runs))
    with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(copy, 'table_pdf_path', return_value=None):
        return Path(copy.copy_ocr_scan(folder, [page], {})).read_text()


def abstract(x, top, n, width=640, size=20):
    lines = [run(('Abstract. ' if i == 0 else '')+PROSE+f' line {i}', x, top+24*i, width, size) for i in range(n)]
    lines[-1]['text'] = 'the abstract ends here with its last line.'
    return lines


def body(top, rows=8):
    return [run(PROSE+f' body {k} {i}', x, top+24*i, 330, 20) for k, x in enumerate((100, 460, 820))
            for i in range(rows)]


def strip(x, top, lines, size=15):
    return [run(t, x, top+19*i, w, size) for i, (t, w) in enumerate(lines)]


LONG = [('Key words: soft layer thickness; probe', 290), ('readings; sound device measurement; method;', 330),
        ('group comparison between younger sites', 300), ('Accepted for publication 3 March 1996', 280)]


class SideKeyWordStrip(unittest.TestCase):
    def test_long_strip_lines_beside_abstract_stay_in_strip_right(self):
        # strip on the right, its long wrapped lines prose-length, ending below the abstract
        text = copied([*abstract(100, 300, 14), *strip(820, 300+24*11, LONG), *body(800)])
        info = text.index('**Article information**')
        for t, _ in LONG: self.assertGreater(text.index(t), info)
        self.assertLess(text.index('the abstract ends here'), info)
        self.assertLess(info, text.index('body 2 0'))

    def test_strip_ending_above_abstract_end_waits_for_the_abstract_left(self):
        # strip on the left, ending level with the abstract's third line from the end
        text = copied([*abstract(460, 300, 14), *strip(100, 300+24*8, LONG), *body(800)])
        info = text.index('**Article information**')
        self.assertLess(text.index('line 12'), info)
        self.assertLess(text.index('the abstract ends here'), info)
        self.assertLess(info, text.index('body 0 0'))
        for t, _ in LONG: self.assertGreater(text.index(t), info)

    def test_finished_list_does_not_take_text_set_beneath_it(self):
        lines = [('Key words: soft layer; thickness; probe.', 290), ('readings of the sound device were repeatable', 330)]
        text = copied([*abstract(100, 300, 14), *strip(820, 300+24*11, lines), *body(800)])
        info = text.index('**Article information**')
        block = text[info:text.index('\n\n', info+len('**Article information**')+2)]
        self.assertNotIn('readings of the sound device', block)

    def test_strip_in_running_type_keeps_its_prose_break(self):
        # the same layout in the running type: a prose line under the key line is not the strip's
        lines = [('Key words: soft layer thickness; probe', 290), ('readings; sound device measurement; method;', 330)]
        text = copied([*abstract(100, 300, 14), *strip(820, 300+24*11, lines, size=20), *body(800)])
        info = text.index('**Article information**')
        block = text[info:text.index('\n\n', info+len('**Article information**')+2)]
        self.assertNotIn('readings; sound device', block)

    def test_band_never_passes_text_beneath_the_strip_in_its_column(self):
        # body text starts in the strip's column one line under the strip, while the abstract runs on
        rs = [*abstract(100, 300, 14), *strip(820, 300+24*6, LONG[:2]),
              *[run(PROSE+f' side column {i}', 820, 300+24*6+19*2+6+24*i, 330, 20) for i in range(12)]]
        text = copied(rs)
        self.assertLess(text.index('**Article information**'), text.index('side column 0'))

    def test_long_strip_lines_still_witness_their_column_edge(self):
        # the third body column holds short lines only; the strip's two long lines are among the few
        # prose-length lines printed at that column's left edge, and still witness it
        short = [run(f'short {i} words here', 820, 800+24*i, 200, 20) for i in range(8)]
        rs = [*abstract(100, 300, 14), *strip(820, 300+24*11, LONG[:3]),
              *[run(PROSE+f' body {k} {i}', x, 800+24*i, 330, 20) for k, x in enumerate((100, 460)) for i in range(8)],
              run(PROSE+' third column long', 820, 800+24*8, 330, 20), *short]
        text = copied(rs)
        for line in text.splitlines():
            if 'body 1 ' in line: self.assertNotIn('short', line)


if __name__ == '__main__':
    unittest.main()
