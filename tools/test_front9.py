"""front9: a rebuilt author note claims all its printed rows (its marker's row included), the
copier traces it to them or does not emit it; a labelled later panel is read in its own column
and ends at a dated publication record."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('front9_helpers', ROOT/'tools/test_front8.py')
helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
page, parse, paper = helpers.page, helpers.parse, helpers.paper


def raised(text, chars='0123456789*†'):
    return {i: (12, True) for i, ch in enumerate(text) if ch in chars}


BYLINE = 'Ada Example1*† and Ben Sample2† and Cy Toll1'
TITLE = ('Periodontal regeneration with a new material: a systematic review', 100, 30, 'title', 't', {})


class NoteRows(unittest.TestCase):
    """Rule 8 records every run an author note was read from."""
    def first(self, note_rows):
        return page(1, [TITLE, (BYLINE, 150, 20, 'authors', 'b', raised(BYLINE)),
                        ('1Department of Surgical Sciences, Some University, Somewhere', 190, 12, 'other', 'a', {0: (8, True)}),
                        ('2Institute of Materials, Other University, Elsewhere', 206, 12, 'other', 'a', {0: (8, True)})] + note_rows)

    def test_two_row_note_claims_both_rows(self):
        rows = [('†Ada Example and Ben Sample contributed equally', 1200, 12, 'other', 'n', {0: (12, True)}),
                ('to this work.', 1216, 12, 'other', 'n', {})]
        a = parse([self.first(rows)])
        notes = a.get('author_notes', [])
        self.assertEqual([n['marker'] for n in notes], ['†'])
        self.assertEqual(notes[0]['text'], 'Ada Example and Ben Sample contributed equally to this work.')
        self.assertEqual(notes[0]['run_ids'], ['run:4', 'run:5'])
        self.assertEqual(notes[0]['page'], 1)
        self.assertEqual(a['checks']['status'], 'verified')

    def test_symbol_on_its_own_row_is_one_of_the_note_rows(self):
        rows = [('†', 1196, 12, 'other', 'n', {0: (12, True)}),
                ('Ada Example and Ben Sample contributed equally', 1212, 12, 'other', 'n', {}),
                ('to this work.', 1228, 12, 'other', 'n', {})]
        a = parse([self.first(rows)])
        notes = a.get('author_notes', [])
        self.assertEqual([n['marker'] for n in notes], ['†'])
        self.assertEqual(notes[0]['run_ids'], ['run:4', 'run:5', 'run:6'])

    def test_note_ends_before_a_correspondence_row(self):
        byline = 'Ada Example1† and Ben Sample2† and Cy Toll1'
        first = page(1, [TITLE, (byline, 150, 20, 'authors', 'b', raised(byline)),
                         ('1Department of Surgical Sciences, Some University, Somewhere', 190, 12, 'other', 'a', {0: (8, True)}),
                         ('2Institute of Materials, Other University, Elsewhere', 206, 12, 'other', 'a', {0: (8, True)}),
                         ('†', 1196, 12, 'other', 'n', {0: (12, True)}),
                         ('Ada Example and Ben Sample contributed equally', 1212, 12, 'other', 'n', {}),
                         ('to this work.', 1228, 12, 'other', 'n', {}),
                         ('*Correspondence:', 1244, 12, 'other', 'n', {}),
                         ('Ada Example', 1260, 12, 'other', 'n', {})])
        notes = parse([first]).get('author_notes', [])
        self.assertEqual(notes[0]['text'], 'Ada Example and Ben Sample contributed equally to this work.')
        self.assertEqual(notes[0]['run_ids'], ['run:4', 'run:5', 'run:6'])


class CopierNoteRows(unittest.TestCase):
    """The copier claims every printed row of a note, or emits nothing."""
    def front(self):
        runs = [dict(id='run:1', kind='text', angle=0, text='†Ada Example and Ben Sample contributed equally', box_px=[0, 100, 400, 112], run_size_px=12),
                dict(id='run:2', kind='text', angle=0, text='to this work.', box_px=[0, 116, 100, 128], run_size_px=12),
                dict(id='run:3', kind='text', angle=0, text='*Correspondence: someone', box_px=[0, 140, 200, 152], run_size_px=12)]
        return dict(page=1, elements=runs)

    def test_recorded_runs_give_every_row(self):
        paper.trace_reset()
        note = dict(marker='†', text='Ada Example and Ben Sample contributed equally to this work.', page=1, run_ids=['run:1', 'run:2'])
        lines = paper.author_note_rows(self.front(), note, note['marker'] + ' ' + note['text'])
        self.assertEqual([str(l) for l in lines], ['†Ada Example and Ben Sample contributed equally', 'to this work.'])
        rows = [paper._TRACE['rows'][r]['runs'] for r, a, b in paper.trace_segs(lines)]
        self.assertEqual(rows, [['run:1'], ['run:2']])

    def test_without_runs_consecutive_rows_holding_the_note(self):
        paper.trace_reset()
        note = dict(marker='†', text='Ada Example and Ben Sample contributed equally to this work.')
        lines = paper.author_note_rows(self.front(), note, note['marker'] + ' ' + note['text'])
        self.assertEqual(len(paper.trace_segs(lines)), 2)

    def test_note_no_row_holds_is_not_emitted(self):
        paper.trace_reset()
        note = dict(marker='‡', text='Present address: nowhere in particular.')
        self.assertEqual(paper.author_note_rows(self.front(), note, '‡ Present address: nowhere in particular.'), [])


class PanelColumn(unittest.TestCase):
    """A labelled later panel is read in the label's column; a dated record ends it."""
    def first(self):
        byline = 'Ada Example1 and Ben Sample2'
        return page(1, [TITLE, (byline, 150, 20, 'authors', 'b', raised(byline)),
                        ('Full list of author information is available at the end of the article', 1300, 12, 'other', 'f', {})])

    def last(self, received=True):
        L, R = 20, 520
        specs = [('left column body text, larger', 400, 20, 'main', 'm', {}, L),
                 ('Author details', 405, 14, 'other', 'p', {}, R),
                 ('more left column body text', 425, 20, 'main', 'm', {}, L),
                 ('1Department of Surgical Sciences, Some University', 425, 14, 'other', 'p', {0: (9, True)}, R),
                 ('2Institute of Materials, Other University, Elsewhere', 445, 14, 'other', 'p', {0: (9, True)}, R),
                 ('Conclusion', 470, 22, 'main', 'h', {}, L)]
        if received: specs.append(('Received: 25 September 2022 / Accepted: 20 March 2023', 470, 14, 'other', 'r', {}, R))
        p, chars = page(3, specs, body=20)
        p['main_text']['columns'] = [[L, 480], [R, 980]]
        return p, chars

    def filler(self):
        return page(2, [('Body text of page two continues at length here.', 200, 16, 'main', 'm', {})])

    def test_panel_beside_a_body_column(self):
        a = parse([self.first(), self.filler(), self.last()])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['1', '2'])
        self.assertEqual(a['affiliations'][0]['text'], 'Department of Surgical Sciences, Some University')
        src = a['affiliation_sources'][0]
        self.assertEqual(src['label'], 'Author details')
        self.assertEqual(sorted(src['run_ids']), ['run:1', 'run:3', 'run:4'])
        self.assertEqual(a['checks']['status'], 'verified')

    def test_rows_of_the_other_column_alone_never_end_the_panel_and_received_ends_it(self):
        a = parse([self.first(), self.filler(), self.last(received=True)])
        self.assertNotIn('run:6', a['affiliation_sources'][0]['run_ids'])   # the Received row
        self.assertNotIn('run:0', a['affiliation_sources'][0]['run_ids'])   # left-column body


    def test_panel_continued_in_the_next_column_in_its_own_size(self):
        L, R = 20, 520
        specs = [('Authors and Affiliations', 400, 14, 'other', 'p', {}, L),
                 ('1Department of Surgical Sciences, Some University', 425, 14, 'other', 'p', {0: (9, True)}, L),
                 ('2Institute of Materials, Other University, Elsewhere', 425, 14, 'other', 'q', {0: (9, True)}, R)]
        p, chars = page(3, specs)
        p['main_text']['columns'] = [[L, 480], [R, 980]]
        a = parse([self.first(), self.filler(), (p, chars)])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['1', '2'])
        self.assertEqual(a['checks']['status'], 'verified')


if __name__ == '__main__':
    unittest.main()
