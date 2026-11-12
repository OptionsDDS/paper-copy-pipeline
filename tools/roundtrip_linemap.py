#!/usr/bin/env python3
"""Assemble an automatic program-role map and report exact word differences.

Usage: /usr/bin/python3 -I tools/roundtrip_linemap.py EXPORT_DIR OUT_DIR

Exit 0 means the reading-copy word multisets match; 1 means a measured
difference (all artifacts are still written); 2 means invalid input. This
check never rewrites text or reuses an id to make a legacy copy match.
"""
import argparse
import difflib
import importlib.util
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/filename)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


exporter = load('_roundtrip_export', 'export_lines.py')
assembler = load('_roundtrip_assemble', 'assemble_map.py')


def reading_text(text):
    """Remove declared Markdown/diagnostic scaffolding, never source words."""
    text = text.split('## Places the program is not sure of', 1)[0]
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'^```\w*\s*$', '', text, flags=re.M)
    text = re.sub(r'^\[table structure not recovered:[^\n]*\]\s*$', '', text, flags=re.M)
    return text


def run(source, output):
    source, output = Path(source), Path(output)
    document = json.loads((source/'lines.json').read_text())
    before = (source/'program.copy.md').read_text()
    if (source/'lines.audit.json').exists():
        audit = json.loads((source/'lines.audit.json').read_text())
        mapping = exporter.refresh_program_map(document, audit, before)
    else:
        mapping = json.loads((source/'program.map.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    (output/'map.json').write_text(json.dumps(mapping, ensure_ascii=True, indent=2)+'\n')
    assembler.assemble(source/'lines.json', output/'map.json', output)
    after = (output/'copy.md').read_text()
    full = exporter.difference(exporter.words(before), exporter.words(after))
    reading = exporter.difference(exporter.words(reading_text(before)), exporter.words(reading_text(after)))
    report = dict(paper=document['paper'], reading_words=reading, full_markdown_words=full,
                  layout_only=reading['equal'], automatic_map='program roles and output order; whole-line tables only')
    (output/'comparison.json').write_text(json.dumps(report, ensure_ascii=True, indent=2)+'\n')
    (output/'copy.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                            fromfile='program.copy.md', tofile='copy.md')))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_dir'); parser.add_argument('out_dir')
    args = parser.parse_args()
    try: report = run(args.export_dir, args.out_dir)
    except (OSError, ValueError) as exc: parser.exit(2, f'roundtrip_linemap: {exc}\n')
    print(json.dumps(report))
    raise SystemExit(0 if report['layout_only'] else 1)


if __name__ == '__main__': main()
