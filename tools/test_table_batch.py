"""A resumed table benchmark must never reuse stale input or output artifacts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class Resume(unittest.TestCase):
    def test_reuse_requires_matching_sources_code_and_every_artifact(self):
        home=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='.table-batch-test-',dir=home) as tmp:
            root=Path(tmp);(root/'tools').mkdir()
            shutil.copy2(home/'tools/copy_plos.sh',root/'tools/copy_plos.sh')
            for name in ('read_shapes.py','read_signs.py'):
                (root/'tools'/name).write_text('pass\n')
            script=root/'copy_paper.py'
            script.write_text('''import json,sys
from pathlib import Path
p=Path(sys.argv[1])
(p/'copy.md').write_text((p/'main-text.json').read_text())
for name in ('tables','conservation','audit'):
 (p/('copy.'+name+'.json')).write_text('{}')
''')
            source=root/'source/article';source.mkdir(parents=True)
            (source/'main-text.json').write_text('{"value": 1}')
            truth=root/'truth/article';truth.mkdir(parents=True)
            (truth/'paper.pdf').write_bytes(b'fixture PDF bytes')
            (truth/'truth.xml').write_text('<article/>')
            output=root/'output'
            env=dict(os.environ,COPY_PLOS_TRUTH=str(truth.parent),COPY_PLOS_WORKERS='1',COPY_PLOS_RESUME='1')
            def run():
                p=subprocess.run(['bash',str(root/'tools/copy_plos.sh'),str(source.parent),str(output)],
                    env=env,capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                return json.loads((output/'COPY-MANIFEST.json').read_text())['articles'][0]
            self.assertFalse(run().get('reused',False))
            self.assertTrue(run()['reused'])
            for change in ('input','pdf','code','table','copy','record'):
                if change=='input':(source/'main-text.json').write_text('{"value": 2}')
                elif change=='pdf':(truth/'paper.pdf').write_bytes(b'new PDF bytes')
                elif change=='code':script.write_text(script.read_text()+'\n# new code\n')
                elif change=='table':(output/'article/copy.tables.json').write_text('{"stale": true}')
                elif change=='copy':(output/'article/copy.md').unlink()
                else:(output/'article/COPY-RECORD.json').write_text('{truncated')
                self.assertFalse(run().get('reused',False),change)
                self.assertTrue(run()['reused'],change)


if __name__=='__main__':unittest.main()
