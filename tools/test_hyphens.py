"""Line-joining and DOI ownership checks: /usr/bin/python3 -I tools/test_hyphens.py."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


class Hyphens(unittest.TestCase):
    def test_unbroken_compound_wins_even_when_closed_form_is_more_frequent(self):
        j = paper.Joiner(['The high-level result. highlevel highlevel'])
        self.assertEqual(j.lines(['high-', 'level']), 'high-level')
        self.assertEqual(j.decisions[-1]['reason'], 'unbroken compound in paper')

    def test_each_boundary_of_a_long_compound_is_evidence(self):
        j = paper.Joiner(['A word-for-word account.'])
        self.assertEqual(j.lines(['word-for-', 'word']), 'word-for-word')

    def test_identifiers_ranges_and_en_dash_have_no_added_space(self):
        for a, b in [('IL-', '8'), ('X7-', 'driven'), ('δ-', 'response'), ('a-', 'wave'),
                     ('12-', '18'), ('NON–', 'SPECIFIC')]:
            with self.subTest(a=a):
                j = paper.Joiner([])
                self.assertEqual(j.lines([a, b]), a + b)
                self.assertEqual(len(j.decisions), 1)

    def test_closed_words_guard_prefixes_and_capitalized_syllables(self):
        j = paper.Joiner(['The international study used semiconductors.'])
        self.assertEqual(j.lines(['inter-', 'national']), 'international')
        self.assertEqual(j.lines(['Semi-', 'conductors']), 'Semiconductors')
        self.assertEqual(j.lines(['Gene-', 'ral']), 'General')
        self.assertEqual(j.lines(['multi-', 'ple']), 'multiple')
        self.assertEqual(j.lines(['TRUN-', 'CATED']), 'TRUNCATED')
        self.assertEqual(j.lines(['2Depart-', 'ment']), '2Department')

    def test_prefix_and_component_evidence(self):
        j = paper.Joiner(['The authors examined cells and tissues.'])
        self.assertEqual(j.lines(['well-', 'defined']), 'well-defined')
        self.assertEqual(j.lines(['cell-', 'tissue']), 'cell-tissue')
        self.assertEqual(j.lines(['field-', 'based']), 'field-based')
        self.assertEqual(j.lines(['frag-', 'ment']), 'fragment')

    def test_url_and_suspended_compound(self):
        j = paper.Joiner([])
        self.assertEqual(j.lines(['https://example.org/a-', 'b']), 'https://example.org/a-b')
        self.assertEqual(j.lines(['single-', 'and double-blind']), 'single- and double-blind')

    def test_spacing_accent_does_not_hide_a_word_break(self):
        j = paper.Joiner([])
        result = j.lines(['Mu¨l-', 'ler'])
        self.assertEqual(paper.compose_accents(result, j.vocab), 'Müller')

    def test_separate_line_numbers_do_not_become_identifier_suffixes(self):
        runs = []
        for i in range(1, 5):
            runs.extend([(1, dict(id=f'n{i}', text=str(i), angle=0, size_px=16,
                                  box_px=[10, i*20, 20, i*20+12])),
                         (1, dict(id=f't{i}', text='term text', angle=0, size_px=16,
                                  box_px=[100, i*20, 300, i*20+12]))])
        j = paper.Joiner([e['text'] for _, e in runs], runs)
        self.assertEqual(j.lines(['long-', '3 term text']), 'long- 3 term text')
        self.assertEqual(j.lines(['IL-', '3 concentrations']), 'IL-3 concentrations')

    def test_title_uses_only_matching_original_rows(self):
        runs = [dict(id=str(i), text=t, angle=0, box_px=[0, i*20, 100, i*20+10])
                for i, t in enumerate(['A Long-', 'Term Study'])]
        j = paper.Joiner([r['text'] for r in runs])
        self.assertEqual(j.title('A Long- Term Study', runs), 'A Long-Term Study')
        self.assertEqual(j.title('A different title', runs), 'A different title')

    def test_doi_label_and_bare_header_are_recovered_without_body_citations(self):
        def run(text, y, angle=0):
            return dict(text=text, kind='text', angle=angle, box_px=[10, y, 200, y+10])
        page = dict(region_box_px=[0, 0, 500, 800], elements=[
            run('DOI: 10.1234/article.1', 30), run('10.1234/article.2', 780),
            run('10.1234/cited.3', 300), run('DOI: 10.1234/watermark', 50, 270)])
        self.assertEqual(paper.article_doi_lines(page), [['DOI: 10.1234/article.1'], ['10.1234/article.2']])


if __name__ == '__main__': unittest.main()
