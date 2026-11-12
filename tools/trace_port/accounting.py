"""Ports of the PCL source-address, annotation and single-owner rules.

Source: paper-copy-language/converter/convert_page.py::load_paper (D-020),
converter/stages_baseline.py::order_streams/assert_stream_membership (C-006),
and pcl.py::_analyse12 (C-006/C-010). No prototype imports or truth inputs.
The adapter supplies decoded line records and exact character witnesses.
"""
from collections import Counter, defaultdict


def source_id(digest, page, index):
    """D-020 address; index belongs to the declared extraction substrate."""
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid source SHA-256')
    if not isinstance(page, int) or page < 1 or not isinstance(index, int) or index < 0:
        raise ValueError('invalid source page or character index')
    return f'pdf:{digest}:p{page}:c{index}'


def account(lines, units, mapping=()):
    """Exact C-006 membership rule, adapted from streams to copy units.

    Do not port the truth runner's remaining-lines-as-furniture fallback:
    runtime exclusions require independent evidence. Partial text is lost too.
    Multiple units fail even when they use disjoint pieces of the same line.
    """
    memberships = defaultdict(list)
    known = {line['id'] for line in lines}
    unknown = []
    for unit in units:
        for lid in dict.fromkeys(s['line_id'] for s in unit['sources']):
            memberships[lid].append(unit['id'])
            if lid not in known:
                unknown.append({'line_id': lid, 'unit_id': unit['id']})
    lost, multiple, incomplete = [], [], []
    for line in lines:
        owners = memberships[line['id']]
        record = {'line_id': line['id'], 'page': line['page'], 'units': owners}
        if not owners and not line.get('furniture_evidence'):
            lost.append(record)
        elif len(owners) > 1:
            multiple.append(record)
        if line['status'] == 'not placed' and owners:
            incomplete.append(record)
    uses = defaultdict(set)
    for entry in mapping:
        if 'line_id' in entry:
            uses[entry['line_id'], entry['column']].add(entry['offset'])
    repeated = defaultdict(list)
    for (lid, column), offsets in uses.items():
        if len(offsets) > 1:
            repeated[lid].append(dict(column=column,copy_offsets=sorted(offsets)))
    failures = dict(lines_in_no_unit=lost, lines_in_multiple_units=multiple,
                    partially_placed_lines=incomplete, unknown_line_references=unknown,
                    repeated_source_characters=[dict(line_id=lid,characters=characters) for lid,characters in repeated.items()],
                    duplicate_source_ids=[lid for lid, count in Counter(l['id'] for l in lines).items() if count > 1])
    return dict(ok=not any(failures.values()), **failures)


def annotations(text, units, lines, normalise):
    """Adapt pcl.py::_analyse12's per-character (offset,line,column) map.

    Explicit copy syntax/whitespace is derived. An unresolved printed character
    is unresolved, never derived. Overlapping exact witnesses are deduplicated
    only at the identical source address, never by choosing a winner.
    """
    by_line = {line['id']: line for line in lines}
    mapping = [{'offset': i, 'char': char, 'derived': 'copy layout or structural markup'}
               for i, char in enumerate(text)]
    for unit in units:
        begin, end = unit['span']
        unit_key, significant = normalise(unit['text'], begin)
        unit_characters = dict(zip(significant, unit_key))
        significant = set(significant)
        for i in range(begin, end):
            mapping[i] = dict(offset=i, char=text[i], unit=unit['id'])
            if unit.get('generated_reason'):
                mapping[i]['derived'] = unit['generated_reason']
            elif i not in significant:
                mapping[i]['derived'] = 'copy whitespace or markup'
            else:
                mapping[i]['unresolved'] = 'no unique exact source witness'
        candidates = defaultdict(set)
        for source in unit['sources']:
            line = by_line[source['line_id']]
            for witness in source['witnesses']:
                a, b = witness['copy_span']; c, d = witness['line_span']
                line_key, line_positions = normalise(line['text'], source=True)
                line_characters = dict(zip(line_positions, line_key))
                positions = [p for p in sorted(significant) if a <= p < b]
                columns = [p for p in line_positions if c <= p < d]
                key = ''.join(unit_characters[p] for p in positions)
                other = ''.join(line_characters[p] for p in columns)
                if key != other:
                    raise ValueError('non-exact character witness')
                for offset, column in zip(positions, columns):
                    candidates[offset].add((line['id'], line['page'], line['number'], column))
        for offset, addresses in candidates.items():
            entry = mapping[offset]
            if len(addresses) == 1:
                lid, page, number, column = next(iter(addresses))
                entry.pop('unresolved', None)
                entry.update(line_id=lid, page=page, line=number, column=column)
            else:
                entry['unresolved'] = 'multiple exact source addresses'
                entry['candidates'] = [dict(line_id=lid, page=p, line=n, column=c)
                                       for lid, p, n, c in sorted(addresses)]
    return mapping
