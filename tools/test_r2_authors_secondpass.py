"""r2-authors, second pass rule 10: a comma part made only of academic titles and degrees after a
name ("Dr Habil", "Dr Med Dent/Dr Habil", "Dipl-Ing") is not counted as a printed name; a surname
that looks like a degree token still is. (Separate file: the boxer's import guard blocks this import.)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'secondpass'))
import r10_page1  # noqa: E402


class SecondPassNameCount(unittest.TestCase):
    """The second pass's independent byline count: a comma part made only of titles and degrees is no name."""
    def test_title_parts_are_not_names(self):
        self.assertEqual(r10_page1.name_count('Ada Example, Dr Habil; Ben Sample, Dr Med Dent; Cora Test, DDS'), 3)
        self.assertEqual(r10_page1.name_count('Ada Example, Dr Med Dent/Dr Habil; Ben Sample, Dipl-Ing, PhD;'), 2)

    def test_address_on_the_byline_row_holds_no_names(self):
        self.assertEqual(r10_page1.name_count('ADA EXAMPLE* & BEN SAMPLE† *Department of Testing, Faculty of Trials, Northfield University, Northfield and'), 2)

    def test_degree_like_surnames_still_count(self):
        self.assertEqual(r10_page1.name_count('Wen Ma1, Arthur Dent2, Rosa Med1, Thanh Ba2 and Kofi Mensah1'), 5)



if __name__ == '__main__':
    unittest.main()
