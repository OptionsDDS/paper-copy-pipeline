#!/usr/bin/env python3
"""Second pass: an independent run of general rules that look for likely errors in a finished copy.

usage: secondpass.py PAPER_DIR [PDF] [--rules 1,3,...] [--write-list] [--json PATH]

After the first run (element boxer + copy_paper.py) has written copy.md and its
native trace, this program reads the copy, the trace, the boxer's page files
and the PDF, and applies the fixed rule list in rules.txt (one module per
rule; each module's check() names the error family it catches). It never
changes the copy text. It writes PAPER_DIR/copy.secondpass.json with every item
(rule, page, box, copy line, message, evidence) and, with --write-list, adds the
items of the rules whose mode is "list" to the copy's "Places the program is not
sure of" list (earlier second-pass items are replaced), then rebinds the
sidecars that record the copy hash (copy.trace.json, copy.checks.json,
copy.pcl.audit.json). A rule that fails is recorded as an error and abstains.
No AI models; standard library plus pdftoppm/pdftotext.

Exit status: 0 ran (items or not), 2 missing input.
"""
import hashlib
import importlib
import json
import re
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402

SCHEMA = 'copy-secondpass/1'
LIST_PREFIX = 'second pass, rule '


def rule_list(path=HERE/'rules.txt'):
    out = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'): continue
        number, module, mode, description = line.split(None, 3)
        out.append(dict(rule=int(number), module=module, mode=mode, description=description.strip()))
    return out


def run(folder, pdf=None, only=None):
    paper = common.Paper(folder, pdf)
    rules, findings = [], []
    # Import every rule first: rule 9 loads the boxer's reader, whose import guard
    # admits only the standard library and vendored modules afterwards.
    modules = {}
    for r in rule_list():
        try: modules[r['module']] = importlib.import_module(r['module'])
        except Exception as exc: modules[r['module']] = exc
    for r in rule_list():
        if only and r['rule'] not in only: continue
        started = time.perf_counter(); record = dict(r)
        try:
            module = modules[r['module']]
            if isinstance(module, Exception): raise module
            items, stats = module.check(paper)
            record.update(name=getattr(module, 'NAME', r['module']), items=len(items), stats=stats)
            for item in items:
                item['mode'] = r['mode']
                if item.get('offset') is not None: item['copy_line'] = paper.copy_line(item['offset'])
                findings.append(item)
        except Exception as exc:  # a failing rule abstains; the copy stands
            record.update(items=0, error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc()[-2000:])
        record['seconds'] = round(time.perf_counter()-started, 2)
        rules.append(record)
    return paper, dict(schema=SCHEMA, copy_sha256=hashlib.sha256(paper.text.encode('utf-8')).hexdigest(),
                       pdf=paper.pdf, rules=rules, findings=findings)


def list_items(report):
    out = []
    for f in report['findings']:
        if f.get('mode') != 'list': continue
        msg = re.sub(r'\s+', ' ', f['message']).strip()
        out.append(f"{LIST_PREFIX}{f['rule']}: {msg}")
    return out


def write_list(folder, items):
    """Replace earlier second-pass items in the uncertainty list; rebind hash-bound sidecars."""
    folder = Path(folder); path = folder/'copy.md'
    text = path.read_text(encoding='utf-8')
    old_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    body, mark, rest = text.partition(common.UNCERTAINTY)
    kept = [l for l in rest.split('\n') if not l.startswith('- '+LIST_PREFIX)] if mark else []
    if mark:
        rest = '\n'.join(kept).rstrip('\n')
        if items:
            rest = re.sub(r'\n- none\s*$', '', rest)
            rest += '\n' + '\n'.join('- '+i for i in items)
        elif not re.search(r'\n- ', rest):
            rest += '\n- none'
        new = body + mark + rest + '\n'
    elif items:
        new = text.rstrip('\n') + '\n\n---\n' + common.UNCERTAINTY + '\n' + '\n'.join('- '+i for i in items) + '\n'
    else:
        new = text
    if new == text: return False
    path.write_text(new, encoding='utf-8')
    digest = hashlib.sha256(new.encode('utf-8')).hexdigest()
    # The list follows every unit, so unit spans are unchanged; only the copy hash moves.
    for name, update in (('copy.trace.json', lambda d: d.get('copy', {}).get('sha256') == old_hash and
                          d['copy'].update(sha256=digest, characters=len(new))),
                         ('copy.checks.json', lambda d: d.get('copy_sha256') == old_hash and d.update(copy_sha256=digest)),
                         ('copy.pcl.audit.json', lambda d: (d.get('trace') or {}).get('copy_sha256') == old_hash and
                          d['trace'].update(copy_sha256=digest))):
        p = folder/name
        if not p.is_file(): continue
        data = json.loads(p.read_text(encoding='utf-8'))
        if update(data) is None:
            tmp = p.with_suffix(p.suffix+'.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
            tmp.replace(p)
    return True


def main(argv):
    args = list(argv); only = None; write = False; out = None
    if '--rules' in args:
        i = args.index('--rules'); only = {int(v) for v in args[i+1].split(',')}; del args[i:i+2]
    if '--json' in args:
        i = args.index('--json'); out = args[i+1]; del args[i:i+2]
    if '--write-list' in args: args.remove('--write-list'); write = True
    if not args or not (Path(args[0])/'copy.md').is_file() or not (Path(args[0])/'copy.trace.json').is_file():
        print(__doc__); return 2
    folder = Path(args[0]); pdf = args[1] if len(args) > 1 else None
    paper, report = run(folder, pdf, only)
    if write:
        write_list(folder, list_items(report))
        report['copy_sha256_with_list'] = hashlib.sha256((folder/'copy.md').read_bytes()).hexdigest()
        report['listed'] = len(list_items(report))
    target = Path(out) if out else folder/'copy.secondpass.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    counts = {r['rule']: r.get('items', 0) for r in report['rules']}
    errors = [f"rule {r['rule']}: {r['error']}" for r in report['rules'] if r.get('error')]
    print(f"second pass: {len(report['findings'])} item(s) {counts}" + (f"; errors: {errors}" if errors else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
