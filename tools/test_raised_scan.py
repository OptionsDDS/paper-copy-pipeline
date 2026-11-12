"""Scan OCR runs: a raised small group stays attached to the word the PDF text order puts it in (iss-11)."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


boxer = module('raised_boxer', ROOT/'standalone/element_boxer_sc.py')
copy = module('raised_copy', ROOT/'copy_paper.py')


def line(words, x, baseline, size, serial):
    """Characters of one OCR text line; each word is its own text show, in reading order."""
    chars = []
    for n, word in enumerate(words):
        for i, t in enumerate(word):
            w = .5*size
            chars.append(dict(text=t, x0=x, x1=x+w, adv_x1=x+w, y0=baseline-.8*size, y1=baseline,
                              origin=[x, baseline], size=size, paint_order=(serial+n, i)))
            x += w
        x += .4*size
    return chars


def fixture(raised_size=13, order='inline', end=False, rise=9.7, between=False, box_shift=0):
    """A left-column line 'area mm ) here' with a raised '2' after 'mm' and a right-column line on the
    raised digit's baseline; order says where the OCR layer's text order puts the '2'."""
    host = 100.0
    words = ['area', 'mm'] if end else ['area', 'mm', ')', 'here']
    left = line(words, 20, host, 20, 10)
    if between:  # the next word is a separate run, more than an em right of 'mm'
        left = line(['area', 'mm'], 20, host, 20, 10)+line(['here'], 20+12*20*.5+.4*20+30, host, 20, 12)
    mm = [c for c in left if c['paint_order'][0] == 11][-1]
    right = line(['Right', 'column', 'line'], 400, host-rise, 20, 100)
    serial = {'inline': 11.5, 'after_right': 200, 'none': None}[order]
    two = dict(text='2', x0=mm['x1']+.2, x1=mm['x1']+.2+.5*raised_size, adv_x1=mm['x1']+.2+.5*raised_size,
               y0=host-rise-.8*raised_size-box_shift, y1=host-rise-box_shift, origin=[mm['x1']+.2, host-rise], size=raised_size,
               paint_order=None if serial is None else (serial, 0))
    if end: right = line(['Next', 'line'], 20, host+25, 20, 50)
    return left+[two]+right


def texts(chars):
    return [r['text'] for r in boxer.sc_ocr_runs(chars)]


class RaisedScan(unittest.TestCase):
    def test_superscript_in_text_order_stays_in_its_word(self):
        result = texts(fixture())
        # The space after the digit is the reader's ordinary advance-gap rule.
        self.assertTrue(any(t in ('area mm2) here', 'area mm2 ) here') for t in result), result)
        self.assertIn('Right column line', result)
        self.assertNotIn('2', result)

    def test_superscript_ending_its_line_stays_on_it(self):
        self.assertIn('area mm2', texts(fixture(end=True)))

    def test_text_order_elsewhere_moves_nothing(self):
        result = texts(fixture(order='after_right'))
        self.assertIn('area mm ) here', result)
        self.assertIn('2', result)

    def test_full_size_or_unordered_group_moves_nothing(self):
        for chars in (fixture(raised_size=20), fixture(order='none')):
            self.assertIn('area mm ) here', texts(chars))

    def test_group_between_two_runs_stays_its_own_run(self):
        result = texts(fixture(between=True))
        self.assertIn('2', result)
        self.assertIn('area mm', result)
        self.assertIn('here', result)

    def test_box_a_line_away_moves_nothing(self):
        # A table sign whose OCR origin is the top of its box: origin within an em,
        # box clear of the characters it would sit between.
        self.assertIn('area mm ) here', texts(fixture(box_shift=15)))

    def test_rise_of_an_em_or_more_moves_nothing(self):
        self.assertIn('area mm ) here', texts(fixture(rise=21)))

    def test_copier_reproduces_reader_membership(self):
        for chars in (fixture(), fixture(end=True), fixture(order='after_right'), fixture(raised_size=20),
                      fixture(order='none'), fixture(rise=21), fixture(between=True), fixture(box_shift=15)):
            runs = boxer.sc_ocr_runs(chars)
            groups = copy.scan_character_groups(chars)
            self.assertEqual(len(groups), len(runs))
            self.assertEqual([copy.scan_character_text(g) for g in groups], [r['text'] for r in runs])


if __name__ == '__main__':
    unittest.main()
