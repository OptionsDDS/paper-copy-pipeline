"""Round-trip checks must report losses, not normalize them away."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec=importlib.util.spec_from_file_location(name, ROOT/'tools'/path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
r = module('roundtrip_tests', 'roundtrip_linemap.py')
fixture = module('roundtrip_fixtures', 'test_assemble_map.py')


class RoundTrip(unittest.TestCase):
    def test_layout_only_fixture_and_real_extra_word(self):
        document = fixture.document('A title', 'One printed', 'paragraph.', '9')
        mapping = dict(paper='example', front=dict(title=['p1.l001']),
                       body=[dict(kind='paragraph', lines=['p1.l002', 'p1.l003'])],
                       furniture=dict(page_number=['p1.l004']))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            source = Path(tmp)/'source'; source.mkdir(); out=Path(tmp)/'out'
            for name, value in [('lines.json', document), ('program.map.json', mapping)]:
                (source/name).write_text(json.dumps(value))
            (source/'program.copy.md').write_text('# A title\n\nOne printed paragraph.\n\n<!-- end of page 1 -->\n\n## Places the program is not sure of\n- none\n')
            result=r.run(source, out)
            self.assertTrue(result['layout_only'])
            self.assertFalse(result['full_markdown_words']['equal'])
            self.assertTrue((out/'map.json').exists())
            self.assertTrue((out/'copy.linemap.json').exists())
            (source/'program.copy.md').write_text('# A title\n\nOne printed paragraph. DUPLICATE\n')
            result=r.run(source, out)
            self.assertFalse(result['layout_only'])
            self.assertEqual(result['reading_words']['missing'], {'DUPLICATE': 1})


if __name__ == '__main__': unittest.main()
