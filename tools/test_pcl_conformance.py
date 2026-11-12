"""Port: paper-copy-language/tests/run_tests.py; inventory C3, Revision (1).

Retain the upstream validator, 63 positive fixtures (including printed,
reading and annotation expectations), and 92 exact negative error cases.
The runner's only adaptation is isolated Python subprocesses (-I).
"""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent/'pcl'


class Conformance(unittest.TestCase):
    def test_upstream_validator_and_fixtures_unchanged(self):
        source = json.loads((ROOT/'UPSTREAM.json').read_text())
        for name, digest in source['files'].items():
            if name in source['adaptations']:
                continue
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)

    def test_all_upstream_conformance_cases(self):
        result = subprocess.run(['/usr/bin/python3', '-I', '-B', str(ROOT/'tests/run_tests.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('positive cases: 63 passed, negative cases: 92 passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
