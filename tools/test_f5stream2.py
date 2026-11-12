#!/usr/bin/env python3
"""Lane f5stream2: the general stage must not lose printed lines.

inset_box_runs (lane f5stream R1 inside a block) lifts a boxed inset out of a body block and leaves
its runs to the side-text pass. A column of list markers beside the items they open is not such an
inset: the markers belong to their items' units, and the side-text pass would drop a letter-free
column as a fragment, so the printed lines would be in no unit. All texts are invented.
"""
import os
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(HERE).parent
sys.path.insert(0, str(ROOT))
import copy_paper as copy


def run_(rid, text, x, y, w, size=20.8, face='ABCDEF+Serif-Roman'):
    return dict(id=rid, kind='text', text=text, angle=0, box_px=[x, y, x+w, y+size*.9], size_px=size,
                run_size_px=size, _faces={face: len(text)})


def list_block(marker, marker_face='GHIJKL+Symbol', marker_size=19.0):
    """Four one-row items, each opened by a marker run 1.5 em left of its text, above two prose rows."""
    runs = {}
    for i in range(4):
        y = 100 + 26*i
        runs[f'm{i}'] = run_(f'm{i}', marker(i), 120, y+6, 8, size=marker_size, face=marker_face)
        runs[f't{i}'] = run_(f't{i}', 'an item of the list in body type', 160, y, 300)
    for i in range(4):
        runs[f'p{i}'] = run_(f'p{i}', 'a paragraph line of ordinary prose set in the body face', 120, 220+26*i, 420)
    return runs


class ListMarkersAreNotAnInset(unittest.TestCase):
    def test_bullet_glyph_column_stays_with_its_items(self):
        for glyph in ('', '•', '▪'):
            runs = list_block(lambda i: glyph)
            self.assertEqual(copy.inset_box_runs(list(runs), runs, 20.8), set(), glyph)

    def test_number_and_letter_labels_stay_with_their_items(self):
        for label in (lambda i: f'{i+1}.', lambda i: f'({"abcd"[i]})', lambda i: f'{"abcd"[i]})'):
            runs = list_block(label, marker_face='GHIJKL+Serif-Bold')
            self.assertEqual(copy.inset_box_runs(list(runs), runs, 20.8), set())

    def test_letter_free_column_is_never_lifted(self):
        # a column of signs in another face beside the rows: nothing the side pass could place
        runs = list_block(lambda i: '*†‡§'[i] * 2)
        self.assertEqual(copy.inset_box_runs(list(runs), runs, 20.8), set())

    def test_list_marker_run(self):
        for t in ('', '•', ' ▪ ', '1.', '12)', 'a)', '(iv)', '(b)'):
            self.assertTrue(copy.list_marker_run(t), t)
        for t in ('', 'a boxed note', '123.', '1.5', 'Fig.', '••• •'):
            self.assertFalse(copy.list_marker_run(t), t)

    def test_boxed_notice_with_words_is_still_an_inset(self):
        # the lane's own rule stands: a small-type notice the body rows wrap around leaves the block
        runs = {}
        for i in range(10):
            x = 350 if 2 <= i <= 7 else 120
            runs[f'b{i}'] = run_(f'b{i}', 'body text of the paragraph runs on here', x, 100+25*i, 540-x)
        for i in range(5):
            runs[f'i{i}'] = run_(f'i{i}', 'a boxed notice line', 120, 152+20*i, 180, size=14.6, face='GHIJKL+Sans-Regular')
        runs['k0'] = run_('k0', '•', 112, 152, 6, size=14.6, face='GHIJKL+Sans-Regular')
        self.assertEqual(copy.inset_box_runs(list(runs), runs, 20.8), {f'i{i}' for i in range(5)})


if __name__ == '__main__':
    unittest.main()
