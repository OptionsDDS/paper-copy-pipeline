"""Study-table entries: a wrapped following citation does not take the open entry's last line."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('cellblocks',Path(__file__).with_name('test_cellblocks.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c,run=m.c,m.run


def starts(texts):
    rs=[run(t,5,y,130) for y,t in texts]
    lines=c.table_lines([(e['box_px'],e['text'],e) for e in rs])
    return [lo for lo,hi in c.table_entry_bands(lines,[160],18,10,study=True)]


class WrappedCitation(unittest.TestCase):
    def test_last_wrapped_line_stays_in_its_entry(self):
        # The next citation wraps over three lines ("Name," / "Name, Name," / "(year):")
        # directly below the open entry's last line, with no blank band between them.
        texts=[(25,'Alpha,'),(40,'Beta, (1991):'),(55,'Registry +'),(70,'Second Place'),
               (85,'Gamma,'),(100,'Delta, Eps,'),(115,'(1992):'),(130,'Registry')]
        self.assertEqual(starts(texts),[18,23,83])

    def test_coauthor_comma_keeps_the_wrapped_citation_on_its_first_author_line(self):
        texts=[(25,'Alpha et al (1990)'),(40,'Registry'),(55,'Delta,'),(70,'Eps, Zeta,'),(85,'(1992):')]
        self.assertEqual(starts(texts),[18,23,53])

    def test_one_line_following_citation_still_refuses_the_open_line(self):
        texts=[(25,'Alpha et al (1990)'),(40,'Country'),(55,'Beta et al (1991)')]
        self.assertEqual(starts(texts),[18,23,53])


if __name__=='__main__':
    unittest.main()
