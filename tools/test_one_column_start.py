"""Lane r9-rowclues (F1, AP11 crash): table_rows on a part with one column start (a numbered list with hanging lines,
read as a table by a recovery path) must not fail where it asks for the right edge of column 0: with no second column
start, column 0 has no right edge. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid=t.c,t.run,t.page,t.grid


def r(text,x,y,w):
    e=run(text,x,y,w); e['box_px']=[x,y,x+w,y+17]; return e


LIST=[r('Group heading of the first kind of entry',0,0,390),r('continued heading words go on here',0,25,450),
      r('1. first numbered item with words that run on',3,57,420),r('and go on in the next line here',24,82,418),
      r('2. second numbered item with words that run',0,113,452),r('short end',25,138,240),
      r('3. third numbered item with words that run on',0,169,453),r('a further line of words',24,194,429)]


class OneColumnStart(unittest.TestCase):
    def test_a_one_column_list_gets_rows_without_failing(self):
        rows,notes=c.table_rows(LIST,21.0,dict(page(LIST),_table_layout='unstructured'))
        words=sum(len(cell.split()) for row in grid(rows) for cell in row)+sum(len(n.split()) for n in notes)
        self.assertEqual(words,sum(len(e['text'].split()) for e in LIST))


if __name__=='__main__':
    unittest.main()
