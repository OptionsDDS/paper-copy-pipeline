#!/usr/bin/env python3
"""Replay additive rule 9 from saved pages, including compact validation runs.

Usage: python3 -I tools/replay_body_order.py RUN_ROOT [RUN_ROOT ...]
Only body-order.json is written. Gzip pages are read without unpacking to disk.
"""
import gzip
import importlib.util
import json
from pathlib import Path
import sys


def main():
    spec=importlib.util.spec_from_file_location('boxer',Path(__file__).resolve().parents[1]/'standalone/element_boxer_sc.py')
    boxer=importlib.util.module_from_spec(spec);spec.loader.exec_module(boxer)
    counts={'papers':0,'boxes':0,'unplaced':0,'flagged_edges':0,'no_pages':[]}
    for name in sys.argv[1:]:
        for d in sorted(Path(name).iterdir()):
            if not d.is_dir():continue
            packed=d/'pages.json.gz'
            if packed.exists():
                with gzip.open(packed,'rt') as f:pages=json.load(f)
                result=boxer.body_reading_order(pages)
                (d/'body-order.json').write_text(json.dumps(result,indent=1,ensure_ascii=False)+'\n')
            elif list(d.glob('page-*.json')) or (d/'main-text.txt').exists():
                result=boxer.write_body_order(d)
            else:continue
            counts['papers']+=1;counts['boxes']+=result['counts']['placed']
            counts['unplaced']+=result['counts']['unplaced'];counts['flagged_edges']+=result['counts']['flagged_edges']
            if not result['pages']:counts['no_pages'].append(str(d))
    print(json.dumps(counts,indent=2))


if __name__=='__main__':main()
