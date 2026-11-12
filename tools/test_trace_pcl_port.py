"""Run all original keyless PCL conformance cases in an isolated process."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    raise SystemExit(subprocess.call(['/usr/bin/python3', '-I', '-B',
        str(Path(__file__).resolve().parent/'trace_port/tests/run_tests.py')]))
