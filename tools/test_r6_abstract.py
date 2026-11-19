"""Lane r6-abstract (round 6): the abstract rules B1, B4, B10 and S1, independent of any paper text."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


boxer = module('r6abs_boxer', ROOT / 'standalone/element_boxer_sc.py')
paper = module('r6abs_copy', ROOT / 'copy_paper.py')


def run(i, text, x, y, w=180, size=10):
    return dict(id=f'run:{i}', kind='text', line=i, angle=0, text=text,
                box_px=[x, y, x + w, y + size], size_px=size, run_size_px=size)


def page_of(es, blocks):
    lines = {}
    for e in es:
        lines.setdefault(e['line'], {'runs': []})['runs'].append(e)
    return dict(runs=es, blocks=blocks, d=dict(blocks=[b.copy() for b in blocks]),
                run_line={e['id']: lines[e['line']] for e in es})


def block(name, lines, box):
    return dict(lines=lines, meta=dict(id=name, box_px=box, size_px=10, cls='main'), page=1)


class LabelledAbstract(unittest.TestCase):
    def front(self, label='Abstract'):
        return [run(1, 'A scientific title of the work', 10, 10, size=18), run(2, 'Ada Example, Ben Sample', 10, 35),
                run(3, '1 Department of Examples, University of Example', 10, 50), run(4, label, 10, 70),
                run(5, 'The work measures a quantity in a sample.', 10, 85), run(6, 'It ends with a result.', 10, 100)]

    def test_label_row_alone_starts_the_abstract(self):
        es = self.front()
        b = dict(id='block:1', members=[e['id'] for e in es], box_px=[10, 10, 190, 110])
        page = page_of(es, [b])
        boxer.split_labelled_abstract(page, 10)
        parts = {p['id']: p for p in page['blocks']}
        self.assertEqual(sorted(parts), ['block:1:abstract', 'block:1:front'])
        self.assertEqual(parts['block:1:abstract']['members'], ['run:4', 'run:5', 'run:6'])
        self.assertTrue(parts['block:1:abstract']['labelled_abstract'])
        self.assertIs(parts['block:1:front']['labelled_abstract'], False)
        self.assertEqual(parts['block:1:front']['main_text_source'], 'block:1')

    def test_label_in_any_case_and_run_in(self):
        for label in ('ABSTRACT', 'summary:', 'SUMMARY This trial compared two devices.', 'Abstract: The work.'):
            es = self.front(label)
            b = dict(id='block:1', members=[e['id'] for e in es], box_px=[10, 10, 190, 110])
            page = page_of(es, [b])
            boxer.split_labelled_abstract(page, 10)
            self.assertEqual(len(page['blocks']), 2, label)

    def test_label_first_or_heading_words_do_not_cut(self):
        # the label opening its own block, a body heading that only starts with the word, and a lone label
        # with nothing under it leave the block whole
        es = [run(1, 'Abstract', 10, 10), run(2, 'The work measures a quantity.', 10, 25)]
        b = dict(id='block:1', members=['run:1', 'run:2'], box_px=[10, 10, 190, 35])
        page = page_of(es, [b])
        boxer.split_labelled_abstract(page, 10)
        self.assertEqual(page['blocks'], [b])
        for label in ('Summary of the studies', 'Abstracts were screened by two readers'):
            es = self.front(label)
            b = dict(id='block:1', members=[e['id'] for e in es], box_px=[10, 10, 190, 110])
            page = page_of(es, [b])
            boxer.split_labelled_abstract(page, 10)
            self.assertEqual(page['blocks'], [b], label)
        es = self.front()[:4]
        b = dict(id='block:1', members=[e['id'] for e in es], box_px=[10, 10, 190, 80])
        page = page_of(es, [b])
        boxer.split_labelled_abstract(page, 10)
        self.assertEqual(page['blocks'], [b])

    def test_label_sharing_its_printed_line_with_another_block_does_not_cut(self):
        es = self.front()
        side = run(9, 'Received 1 May', 300, 70)
        side['line'] = 4
        b = dict(id='block:1', members=[e['id'] for e in es], box_px=[10, 10, 190, 110])
        page = page_of(es + [side], [b, dict(id='block:2', members=['run:9'], box_px=[300, 70, 480, 80])])
        boxer.split_labelled_abstract(page, 10)
        self.assertEqual(len(page['blocks']), 2)
        self.assertNotIn('block:1:abstract', [p['id'] for p in page['blocks']])

    def test_runin_summary_parts_are_not_cut_again(self):
        es = self.front()
        b = dict(id='block:1:abstract', members=[e['id'] for e in es], box_px=[10, 10, 190, 110], runin_abstract=True)
        page = page_of(es, [b])
        boxer.split_labelled_abstract(page, 10)
        self.assertEqual(page['blocks'], [b])


class AbstractBeforeBody(unittest.TestCase):
    def test_label_first_row_block_moves_before_body_printed_below_it(self):
        intro = block('intro', ['Introduction', 'The body starts here.', 'It continues.'], [0, 200, 90, 260])
        abstract = block('abs', ['Abstract', 'The abstract describes the work.', 'It ends here.'], [0, 60, 200, 120])
        other = block('col2', ['of the body in the next column.', 'More body.'], [110, 200, 200, 260])
        result = paper.abstract_before_body([intro, abstract, other], 10)
        self.assertEqual([b['meta']['id'] for b in result], ['abs', 'intro', 'col2'])

    def test_label_first_row_block_in_order_is_unchanged(self):
        abstract = block('abs', ['Abstract', 'The abstract describes the work.', 'It ends here.'], [0, 60, 200, 120])
        intro = block('intro', ['Introduction', 'The body starts here.', 'It continues.'], [0, 200, 90, 260])
        blocks = [abstract, intro]
        self.assertIs(paper.abstract_before_body(blocks, 10), blocks)

    def test_body_beside_the_abstract_is_not_moved(self):
        # body text in a column beside the abstract, starting above its end, stays where the flow put it
        side = block('side', ['The body begins in a side column.', 'It continues.'], [210, 70, 300, 300])
        abstract = block('abs', ['Abstract', 'The abstract describes the work.', 'It ends here.'], [0, 60, 200, 120])
        blocks = [side, abstract]
        self.assertIs(paper.abstract_before_body(blocks, 10), blocks)


class Memo1(unittest.TestCase):
    def test_abstract_never_goes_between_a_sentence_and_its_continuation(self):
        # M1: the left column's last paragraph is open; its continuation (lowercase) is printed under the panel
        left = block('left', ['The left column runs down the page and its last', 'paragraph is open at the foot of the'], [0, 60, 90, 600])
        cont = block('cont', ['same examiner one week later, and the readings', 'agreed within one millimetre.'], [100, 400, 200, 460])
        panel = block('abs', ['ABSTRACT', 'The abstract describes the work.', 'It ends here.'], [100, 60, 300, 300])
        rest = block('rest', ['Radiographs were taken at baseline.', 'And at one year.'], [100, 470, 200, 520])
        blocks = [left, cont, panel, rest]
        self.assertIs(paper.abstract_before_body(blocks, 10), blocks)

    def test_keyword_list_open_with_a_comma_keeps_its_last_row(self):
        # M3: the second row holds only the last keyword, a token with a colon inside it
        items = []
        tail = dict(lines=['Keywords: periodontitis, laser therapy, root planing,', 'Nd:YAG laser'],
                    meta=dict(box_px=[0, 0, 100, 20]))
        J = type('J', (), {'lines': staticmethod(lambda rows: ' '.join(str(r) for r in rows))})
        paper.emit_keyword_record(items, tail, 1, 10, J)
        self.assertEqual([it['kind'] for it in items], ['para'])
        self.assertTrue(items[0]['text'].endswith('Nd:YAG laser'))

    def test_a_labelled_record_after_a_closed_list_is_set_apart(self):
        items = []
        tail = dict(lines=['Keywords: periodontitis; laser therapy.', 'Citation: Example A. A trial. J Ex 2020;1:1-2.'],
                    meta=dict(box_px=[0, 0, 100, 20]))
        J = type('J', (), {'lines': staticmethod(lambda rows: ' '.join(str(r) for r in rows))})
        paper.emit_keyword_record(items, tail, 1, 10, J)
        self.assertEqual([it['kind'] for it in items], ['para', 'side'])


class KeywordRowNote(unittest.TestCase):
    def test_the_label_row_test_wants_a_capital(self):
        # main() cuts at a keyword row only when it opens with a capital under a closed row; the regex alone
        # also matches a lower-case "key words:" run inside a sentence, which the caller rejects
        self.assertTrue(paper.KEYWORDS_ROW.match('key words: case series, trials'))
        self.assertNotIn('key words: case series'.lstrip()[:1], 'KI')


class KeywordRow(unittest.TestCase):
    def test_keyword_labels(self):
        for t in ('KEY WORDS', 'Key Words: : Implant treatment', 'Key Words. Adults; surveys.', 'Keywords: one; two',
                  'KEY WORDS Genetics; review.', 'Index terms: one'):
            self.assertTrue(paper.KEYWORDS_ROW.match(t), t)

    def test_sentences_starting_with_the_word_are_not_labels(self):
        for t in ('Keywords were combined with Boolean operators.', 'Keyword-based searches found 12 trials.',
                  'Key words in the title'):
            self.assertFalse(paper.KEYWORDS_ROW.match(t), t)


class PartAndBoxRows(unittest.TestCase):
    def test_box_label_rows(self):
        for t in ('Clinical Relevance', 'Plain language summary', 'Highlights', 'Clinical significance:', 'What is known',
                  'What this study adds'):
            self.assertTrue(paper.OTHER_BOX_LABEL.fullmatch(t), t)
        for t in ('Clinical relevance of the findings', 'Highlights of the study were'):
            self.assertFalse(paper.OTHER_BOX_LABEL.fullmatch(t), t)


class RunInAbstractEntry(unittest.TestCase):
    def test_two_runin_labels_with_a_results_part_make_the_abstract(self):
        self.assertTrue(paper.runin_labelled_abstract('Study Objectives: The aim was set. Methods: Forty subjects. '
                                                      'Results: A change. Conclusions: It works.'))
        self.assertTrue(paper.runin_labelled_abstract('Study aim: To compare. Results: Similar gain.'))

    def test_other_runin_labels_are_not_the_abstract(self):
        self.assertFalse(paper.runin_labelled_abstract('Current Knowledge/Study Rationale: Some. Study Impact: The impact.'))
        self.assertFalse(paper.runin_labelled_abstract('Received: 1 May 2017. Accepted: 2 June 2017. Published: 3 July 2017.'))
        self.assertFalse(paper.runin_labelled_abstract('The trial compared two devices. Results: similar.'))


class ColumnTopContinuation(unittest.TestCase):
    def test_held_rows_at_a_column_top_continue_the_paragraph_of_the_column_left(self):
        items = [dict(kind='para', page=1, text='The first column stops before a quote and the', box=[0, 400, 100, 600]),
                 dict(kind='para', page=1, text='The second column paragraph ends open on the', box=[110, 300, 210, 700])]
        held = dict(text='rest of the sentence in the next column.', box=[220, 100, 320, 120])
        self.assertEqual(paper.place_front_resume(items, held, 1, 10), 1)

    def test_held_rows_under_their_paragraph_still_win(self):
        items = [dict(kind='para', page=1, text='One paragraph ends open with the', box=[0, 100, 100, 200]),
                 dict(kind='para', page=1, text='Another paragraph ends open with the', box=[110, 100, 210, 200])]
        held = dict(text='words that close the sentence.', box=[0, 210, 100, 230])
        self.assertEqual(paper.place_front_resume(items, held, 1, 10), 0)


class TallInitial(unittest.TestCase):
    def chars(self, cap, rest, gap=8):
        def char(text, x, y, size=10):
            return dict(text=text, x0=x, y0=y - size * .7, x1=x + 5, y1=y, origin=(x, y), adv_x1=x + 5, size=size, font='Example')
        c = char(cap, 0, 30, 30)
        first = [char(t, 5 + gap + i * 5, 10) for i, t in enumerate(rest)]
        second = [char(t, 5 + gap + i * 5, 22) for i, t in enumerate('next')]
        e = run(1, cap + ' ' + rest + ' next', 0, 0, 60)
        e['_chars'] = [c] + first + second
        return e

    def test_initial_joins_a_small_letter_after_its_margin(self):
        page = {}
        rows = paper.prose_text_rows([self.chars('D', 'espite')], page)
        self.assertEqual(paper.prose_row(rows[0], {})[0], 'Despite')
        self.assertNotIn('_r6_initial_doubts', page)

    def test_one_letter_word_initials_keep_the_space_and_are_listed(self):
        page = {}
        rows = paper.prose_text_rows([self.chars('A', 'study')], page)
        self.assertEqual(paper.prose_row(rows[0], {})[0], 'A study')
        self.assertEqual(len(page['_r6_initial_doubts']), 1)


if __name__ == '__main__':
    unittest.main()
