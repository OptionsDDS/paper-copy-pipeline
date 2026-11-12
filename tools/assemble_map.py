#!/usr/bin/env python3
"""Assemble LINEMAP-SCHEMA.md without accepting replacement source text.

Usage: /usr/bin/python3 -I tools/assemble_map.py LINES MAP OUT_DIR

Validation finishes before either output is opened. Splits must start after
whitespace, have an unambiguous exact anchor, and preserve both nonempty parts.
Empty table cells or an ambiguous header span downgrade the entire table to
printed lines; they never invent a value. See tools/LINEMAP.md for decisions.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_linemap_copy', ROOT / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)
ID = re.compile(r'p[1-9]\d*\.l\d+[a-z]*\Z')
FRONT = {'title', 'subtitle', 'authors', 'affiliations', 'article_info', 'abstract', 'keywords'}
FURNITURE = {'running_head', 'page_number', 'figure_text', 'watermark', 'licence', 'other'}


class MapError(ValueError):
    """Invalid schema, ownership or source geometry."""


def require(ok, message):
    if not ok:
        raise MapError(message)


def fields(value, allowed, required=(), path='map'):
    require(isinstance(value, dict), f'{path}: expected object')
    require(not (set(value) - set(allowed)), f'{path}: unknown fields {sorted(set(value)-set(allowed))}')
    require(set(required) <= set(value), f'{path}: missing fields {sorted(set(required)-set(value))}')


def array(value, path):
    require(isinstance(value, list), f'{path}: expected array')
    return value


def string(value, path, nonempty=False):
    require(isinstance(value, str) and (not nonempty or value.strip()), f'{path}: expected text')


def line_index(document):
    fields(document, {'paper', 'pages'}, {'paper', 'pages'}, 'lines')
    string(document['paper'], 'lines.paper', True)
    result = {}
    page_numbers = set()
    for page in array(document['pages'], 'lines.pages'):
        fields(page, {'page', 'width_px', 'height_px', 'image', 'lines'},
               {'page', 'width_px', 'height_px', 'image', 'lines'}, 'page')
        n = page['page']
        require(type(n) is int and n > 0 and n not in page_numbers, 'duplicate/invalid page number')
        page_numbers.add(n)
        for dimension in ('width_px', 'height_px'):
            require(type(page[dimension]) is int and page[dimension] > 0, f'page: invalid {dimension}')
        string(page['image'], 'page.image', True)
        for line in array(page['lines'], 'page.lines'):
            keys = {'id', 'text', 'box', 'size', 'bold', 'italic', 'program_role'}
            fields(line, keys, keys, 'line')
            mid = line['id']
            require(isinstance(mid, str) and ID.fullmatch(mid) and mid.startswith(f'p{n}.l'), 'invalid line id')
            require(mid not in result, f'duplicate source id: {mid}')
            string(line['text'], mid + '.text', True)
            string(line['program_role'], mid + '.program_role', True)
            require(type(line['bold']) is bool and type(line['italic']) is bool, f'{mid}: invalid style')
            require(type(line['size']) in (float, int) and math.isfinite(line['size']) and line['size'] > 0,
                    f'{mid}: invalid size')
            box = array(line['box'], mid + '.box')
            require(len(box) == 4 and all(type(v) in (float, int) and math.isfinite(v) for v in box),
                    f'{mid}: invalid box')
            require(0 <= box[0] < box[2] <= page['width_px'] and
                    0 <= box[1] < box[3] <= page['height_px'], f'{mid}: box outside image')
            result[mid] = dict(line, page=n)
    return result


def validate(document, mapping):
    """Return split leaf records and their ownership paths; no writes occur here."""
    index = line_index(document)
    fields(mapping, {'paper', 'front', 'body', 'references', 'end_matter', 'furniture', 'split_lines', 'notes'},
           {'paper'}, 'map')
    require(mapping['paper'] == document['paper'], 'paper does not match lines.json')
    all_ids = set(index)
    for split in array(mapping.get('split_lines', []), 'split_lines'):
        fields(split, {'id', 'at', 'new_ids'}, {'id', 'at', 'new_ids'}, 'split')
        old, anchor = split['id'], split['at']
        require(isinstance(old, str) and old in index, f'split: unknown or already split id {old!r}')
        string(anchor, 'split.at', True)
        text = index[old]['text']
        starts = [m.start() for m in re.finditer(re.escape(anchor), text)]
        require(len(starts) == 1, f'{old}: split anchor must occur exactly once')
        at = starts[0]
        require(at > 0 and text[at-1].isspace() and not text[at].isspace(),
                f'{old}: split must be at a word boundary after whitespace')
        parts = [text[:at].rstrip(), text[at:]]
        require(all(parts), f'{old}: split creates an empty part')
        ids = array(split['new_ids'], 'split.new_ids')
        require(len(ids) == 2 and all(isinstance(mid, str) and ID.fullmatch(mid) and
                mid.startswith(old) and mid != old for mid in ids), f'{old}: invalid split ids')
        require(len(set(ids)) == 2 and not (set(ids) & all_ids), f'{old}: split id collision')
        source = index.pop(old)
        for mid, part in zip(ids, parts):
            index[mid] = dict(source, id=mid, text=part)
        all_ids.update(ids)

    owners = {}

    def ids(value, path):
        for mid in array(value, path):
            require(isinstance(mid, str) and mid in index, f'{path}: unknown line id {mid!r}')
            require(mid not in owners, f'{mid}: used twice ({owners.get(mid)} and {path})')
            owners[mid] = path

    def groups(value, path):
        for i, group in enumerate(array(value, path)):
            ids(group, f'{path}[{i}]')

    front = mapping.get('front', {})
    fields(front, FRONT, path='front')
    for key, value in front.items():
        (groups if key in ('affiliations', 'article_info') else ids)(value, 'front.' + key)
    for i, item in enumerate(array(mapping.get('body', []), 'body')):
        path = f'body[{i}]'
        require(isinstance(item, dict), f'{path}: expected object')
        kind = item.get('kind')
        if kind in ('heading', 'paragraph', 'list_item', 'caption', 'formula', 'footnote'):
            extra = {'heading': {'level'}, 'caption': {'of'}}.get(kind, set())
            fields(item, {'kind', 'lines'} | extra, {'kind', 'lines'} | extra, path)
            if kind == 'heading':
                require(type(item['level']) is int and item['level'] in (2, 3), f'{path}: heading level must be 2 or 3')
            if kind == 'caption':
                require(isinstance(item['of'], str) and re.fullmatch(r'(?:Figure|Table) \S+', item['of']), f'{path}: invalid caption of')
            ids(item['lines'], path + '.lines')
        elif kind == 'table':
            fields(item, {'kind', 'caption', 'rows', 'header_rows', 'notes'},
                   {'kind', 'caption', 'rows', 'header_rows', 'notes'}, path)
            ids(item['caption'], path + '.caption')
            rows = array(item['rows'], path + '.rows')
            require(type(item['header_rows']) is int and 0 <= item['header_rows'] <= len(rows), f'{path}: invalid header_rows')
            for j, row in enumerate(rows):
                groups(row, f'{path}.rows[{j}]')
            groups(item['notes'], path + '.notes')
        elif kind == 'table_lines':
            fields(item, {'kind', 'caption', 'lines', 'reason'}, {'kind', 'caption', 'lines', 'reason'}, path)
            ids(item['caption'], path + '.caption')
            ids(item['lines'], path + '.lines')
            string(item['reason'], path + '.reason', True)
        elif kind == 'box':
            fields(item, {'kind', 'title', 'items'}, {'kind', 'title', 'items'}, path)
            ids(item['title'], path + '.title')
            groups(item['items'], path + '.items')
        else:
            raise MapError(f'{path}: unknown kind {kind!r}')
    groups(mapping.get('references', []), 'references')
    for i, item in enumerate(array(mapping.get('end_matter', []), 'end_matter')):
        fields(item, {'label', 'lines'}, {'label', 'lines'}, 'end_matter')
        string(item['label'], 'end_matter.label', True)
        ids(item['lines'], f'end_matter[{i}].lines')
    furniture = mapping.get('furniture', {})
    fields(furniture, FURNITURE, path='furniture')
    for key, value in furniture.items():
        ids(value, 'furniture.' + key)
    for note in array(mapping.get('notes', []), 'notes'):
        string(note, 'notes[]')
    missing = sorted(set(index) - set(owners))
    require(not missing, 'unused line ids: ' + ', '.join(missing))
    return index, owners


def render(document, mapping):
    index, owners = validate(document, mapping)
    sources = [(line['page'], dict(id=mid, text=line['text'], box_px=line['box'],
                                  size_px=line['size'], angle=0)) for mid, line in index.items()]
    joiner = copy.Joiner([line['text'] for line in index.values()], sources)
    notes = list(mapping.get('notes', []))
    tables = []
    out = []

    def joined(ids, prose=True):
        joiner.prose = prose
        return copy.compose_accents(joiner.lines([index[mid]['text'] for mid in ids]), joiner.vocab)

    def block(text):
        if text:
            out.append(text)

    def heading(label, ids):
        text = joined(ids)
        if text:
            # A printed label is not inserted a second time.
            block('## ' + label)
            prefix = re.match(re.escape(label) + r'(?:\s*:\s*|\s+|$)', text, re.I)
            if prefix:
                block(text[prefix.end():].strip())
            elif re.sub(r'\W', '', text).casefold() != re.sub(r'\W', '', label).casefold():
                block(text)

    def printed_table(ids, reason):
        lines = [index[mid]['text'] for mid in ids]
        block('\n'.join(copy.table_gate_markdown(lines, following_list=True)).strip())
        notes.append(reason)

    front = mapping.get('front', {})
    if front.get('title'): block('# ' + joined(front['title']))
    if front.get('subtitle'): block(joined(front['subtitle']))
    if front.get('authors'): block('**Authors:** ' + joined(front['authors']))
    for ids in front.get('affiliations', []): block('- ' + joined(ids))
    if front.get('article_info'):
        block('## Article information')
        block('\n'.join('- ' + joined(ids) for ids in front['article_info'] if ids))
    for key in ('abstract', 'keywords'):
        if front.get(key): heading(key.capitalize(), front[key])
    for i, item in enumerate(mapping.get('body', [])):
        kind = item['kind']
        ids = item.get('lines', [])
        if kind == 'heading': block('#' * item['level'] + ' ' + joined(ids))
        elif kind == 'paragraph': block(joined(ids))
        elif kind == 'list_item':
            text = joined(ids)
            block(text if re.match(r'^\s*(?:[-*]|\d+[.)])\s', text) else '- ' + text)
        elif kind == 'caption': block('**' + copy.label_fix(joined(ids, False)) + '**')
        elif kind == 'formula':
            # Keep exact printed baselines; fenced text does not assert LaTeX.
            text = '\n'.join(index[mid]['text'] for mid in ids)
            fence = '`' * max(3, max((len(m[0])+1 for m in re.finditer(r'`+', text)), default=3))
            block(fence + 'text\n' + text + '\n' + fence)
        elif kind == 'footnote': block('> ' + joined(ids))
        elif kind == 'box':
            block('> **' + joined(item['title']) + '**\n' +
                  '\n'.join('> - ' + joined(group) for group in item['items']))
        elif kind in ('table', 'table_lines'):
            if item['caption']: block('**' + copy.label_fix(joined(item['caption'], False)) + '**')
            if kind == 'table_lines':
                printed_table(ids, item['reason'])
                tables.append(dict(item=i, decision='table_lines', reason=item['reason']))
                continue
            rows, nhead = item['rows'], item['header_rows']
            width = max(map(len, rows), default=0)
            reason = None
            if not width or any(not cell for row in rows for cell in row) or any(not row for row in rows):
                reason = 'a table cell has no whole line ids'
            elif any(len(row) != width for row in rows[nhead:]):
                reason = 'body rows have different column counts'
            elif any(len(row) not in (1, width) for row in rows[:nhead]):
                reason = 'header span is ambiguous without column-span metadata'
            if reason:
                printed_table([mid for row in rows for cell in row for mid in cell], f'body[{i}]: {reason}')
                tables.append(dict(item=i, decision='table_lines', reason=reason))
            else:
                cells = [[joined(cell, False).replace('|', r'\|') for cell in row] for row in rows]
                headers = [sum(([cell] * (width // len(row)) for cell in row), []) for row in cells[:nhead]]
                header = ['<br>'.join(row[c] for row in headers) for c in range(width)] if nhead else [''] * width
                grid = ['| ' + ' | '.join(header) + ' |', '| ' + ' | '.join(['---'] * width) + ' |']
                grid += ['| ' + ' | '.join(row) + ' |' for row in cells[nhead:]]
                block('\n'.join(grid))
                tables.append(dict(item=i, decision='table', header_rows=nhead, columns=width))
            for group in item['notes']: block(joined(group, False))
    if mapping.get('references'):
        if not any(re.fullmatch(r'##+\s+(?:References|Bibliography)', text, re.I) for text in out):
            block('## References')
        block('\n'.join('- ' + joined(ids) for ids in mapping['references'] if ids))
    for item in mapping.get('end_matter', []): heading(item['label'], item['lines'])
    block('---\n## Places the program is not sure of\n' + ('\n'.join('- ' + n for n in notes) if notes else '- none'))
    omitted = {key: len(mapping.get('furniture', {}).get(key, [])) for key in sorted(FURNITURE)}
    audit = dict(paper=document['paper'], conservation=dict(source_lines=sum(len(p['lines']) for p in document['pages']),
                 leaf_lines=len(index), used_once=len(owners), missing=[], duplicates=[]),
                 furniture=omitted, furniture_total=sum(omitted.values()), ownership=owners,
                 splits=mapping.get('split_lines', []), tables=tables, hyphens=joiner.decisions)
    return '\n\n'.join(out).strip() + '\n', audit


def assemble(lines_path, map_path, output):
    document = json.loads(Path(lines_path).read_text(encoding='utf-8'))
    mapping = json.loads(Path(map_path).read_text(encoding='utf-8'))
    text, audit = render(document, mapping)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Staging avoids truncation on serialization errors. Invalid maps do not
    # touch an existing successful copy, whose previous audit remains valid.
    payload = json.dumps(audit, ensure_ascii=True, indent=2) + '\n'
    for name, content in [('copy.md', text), ('copy.linemap.json', payload)]:
        temporary = output / (name + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(output / name)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lines')
    parser.add_argument('map')
    parser.add_argument('out_dir')
    args = parser.parse_args()
    try:
        audit = assemble(args.lines, args.map, args.out_dir)
    except (MapError, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'assemble_map: {exc}\n')
    print(json.dumps(audit['conservation']))


if __name__ == '__main__':
    main()
