"""Check stage: apply ops while keeping the copy's native trace (copy.trace.json) true.

Tracker applies one op at a time with the safe applier (repair_apply.apply_operations)
and mirrors each accepted op on a character map: for every character of the current
text, the offset of the copy.md character it came from (or -1 for characters the op
wrote: paragraph breaks, a joining space, Markdown prefixes, a flag line). The mirror
repeats the applier's own cut/insert arithmetic and must produce exactly the applier's
text; if it ever does not, the op is refused.

Trace gate (when copy.md has a native trace): an op is refused when
- it would cut a traced unit apart (a unit's characters no longer contiguous, apart from
  whitespace the op wrote), or
- after it, any printed line would be lost (in no unit, no furniture, no uncertainty
  run) that was not lost before, or a line would be printed twice that was not before.
remove_duplicate drops a unit whose characters are all removed; when it removes only part
of a unit, the unit keeps its claims except those of printed lines whose text lies wholly
in the removed part and nowhere in what is left of the unit (the gate then proves another
unit still holds those lines). Source lines, rows, runs and claims are never invented.

checked_trace() returns copy.checked.trace.json: the same schema (copy-trace/2), units'
spans and texts in copy.checked.md, lines' destinations recomputed, accounting and
statistics recomputed; tools/trace.py --copy copy.checked.md --trace
copy.checked.trace.json validates it.
"""
import copy as _copy
import hashlib
import importlib.util
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def _module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


RA = _module('checkstage_repair_apply', os.path.join(HERE, 'repair_apply.py'))
KEEP_WHOLE = {'caption', 'heading', 'title'}


def _trace_module():
    return _module('checkstage_trace_validator', os.path.join(os.path.dirname(HERE), 'trace.py'))


class T:
    """A string with the origin offset of each character (-1: written by an op)."""
    __slots__ = ('s', 'o')

    def __init__(self, s, o=None):
        self.s = s
        self.o = list(o) if o is not None else [-1] * len(s)

    def __len__(self):
        return len(self.s)

    def __getitem__(self, k):
        return T(self.s[k], self.o[k])

    def __add__(self, other):
        if isinstance(other, str):
            other = T(other)
        return T(self.s + other.s, self.o + other.o)

    def rstrip(self):
        n = len(self.s.rstrip())
        return self[:n]

    def strip_bounds(self, a, b):
        piece = self.s[a:b]
        lead = len(piece) - len(piece.lstrip())
        return a + lead, a + lead + len(piece.strip())


def _with_tail(body, tail):
    if tail.s and body.s and not re.search(r'\r?\n[ \t]*\r?\n\Z', body.s):
        body = body + ('\n' if body.s.endswith('\n') else '\n\n')
    return body + tail


def _insert_paragraph(text, position, content):
    left, right = text[:position], text[position:]
    lead = '' if not left.s or re.search(r'\r?\n[ \t]*\r?\n\Z', left.s) else ('\n' if left.s.endswith('\n') else '\n\n')
    trail = '' if not right.s or re.match(r'\r?\n[ \t]*\r?\n', right.s) else ('\n' if right.s.startswith('\n') else '\n\n')
    return left + lead + content + trail + right


def _split_body(t):
    start = RA.section_start(t.s)
    return (t, T('')) if start is None else (t[:start], t[start:])


def mirror(before, op, entry):
    """The applier's result for one accepted op, with character origins."""
    name = op['op']
    b = entry['before']
    if name == 'move':
        body, tail = _split_body(before)
        start, end = b['span']
        cs, ce = b['removed']
        destination = b['destination'][0]
        sa, sb = body.strip_bounds(start, end)
        span = body[sa:sb]
        remainder = body[:cs] + body[ce:]
        if cs < destination < ce:
            destination = cs
        elif destination >= ce:
            destination -= ce - cs
        if op['as'] == 'paragraph':
            result = _insert_paragraph(remainder, destination, span)
        else:
            left, right = remainder[:destination].rstrip(), remainder[destination:]
            result = left + ' ' + span + (' ' if right.s and not right.s[0].isspace() else '') + right
        return _with_tail(result, tail)
    if name == 'join':
        body, tail = _split_body(before)
        left_end, right_start = b['gap']
        gap = body.s[left_end:right_start]
        markers = [ln.rstrip('\r\n') for ln in gap.splitlines(keepends=True)
                   if ln.strip() and not RA.JOIN_PREFIXES.fullmatch(ln.rstrip('\r\n'))]
        result = body[:left_end] + ' ' + body[right_start:]
        if markers:
            right_end = left_end + 1 + (b['right'][1] - b['right'][0])
            destination = RA.paragraph_end(result.s, right_end)
            result = _insert_paragraph(result, destination, T('\n'.join(markers)))
        return _with_tail(result, tail)
    if name == 'split':
        at = b['insertion'][0]
        sep = '\n\n' if op['as'] == 'paragraph' else '\n'
        return before[:at] + sep + before[at:]
    if name == 'markup':
        body, tail = _split_body(before)
        start, end = b['text']
        quote = body.s[start:end]
        q = body[start:end]
        # the applier keeps the indent and the trailing blanks, drops the old prefix and
        # outer **, and writes the new prefix: follow the content's position in the quote
        p0 = len(quote) - len(RA.strip_prefixes(quote))
        rest = quote[p0:]
        ind = len(rest) - len(rest.lstrip(' \t'))
        c0 = p0 + ind
        trailing = len(rest) - len(rest.rstrip(' \t')) if rest.strip(' \t') else 0
        c1 = len(quote) - trailing
        while c1 - c0 >= 4 and quote.startswith('**', c0) and quote[:c1].endswith('**'):
            inner = quote[c0 + 2:c1 - 2]
            c0 += 2 + (len(inner) - len(RA.strip_prefixes(inner)))
            c1 -= 2
        style = op['as']
        pre, post = ('**', '**') if style == 'caption' else (
            {'heading2': '## ', 'heading3': '### ', 'paragraph': '', 'list_item': '- '}[style], '')
        replacement = q[p0:p0 + ind] + pre + q[c0:c1] + post + q[len(quote) - trailing:]
        return _with_tail(body[:start] + replacement + body[end:], tail)
    if name == 'remove_duplicate':
        body, tail = _split_body(before)
        cs, ce = b['removed']
        return _with_tail(body[:cs] + body[ce:], tail)
    raise ValueError(name)


class Tracker:
    def __init__(self, text, trace=None):
        self.text = text
        self.orig = text
        self.origin = list(range(len(text)))
        self.trace = trace
        self.removed_units = set()
        self.dropped_claims = defaultdict(set)  # unit index -> line ids whose claims were dropped
        if trace is not None:
            self._index_trace()
            self.base_status = self._line_statuses()

    # ------------------------------------------------------------------ trace bookkeeping
    def _index_trace(self):
        tr = self.trace
        self.units = tr['units']
        self.unit_index = {u['id']: k for k, u in enumerate(self.units)}
        self.char_unit = [-1] * len(self.orig)
        for k, u in enumerate(self.units):
            if u.get('status') == 'span_unresolved':
                continue
            a, b = u['span']
            for i in range(a, b):
                self.char_unit[i] = k
        self.rows = {r['row']: r for r in tr['rows']}
        self.unit_lines = defaultdict(set)
        self.line_by_id = {}
        self.run_line = {}
        for line in tr['lines']:
            self.line_by_id[line['id']] = line
            for m in line['runs']:
                self.run_line[(line['page'], str(m))] = line['id']
            for d in line.get('units') or []:
                if d['unit_id'] in self.unit_index:
                    self.unit_lines[self.unit_index[d['unit_id']]].add(line['id'])
        self.run_reason = {(e['page'], str(e['run'])) for e in tr.get('furniture_runs', [])}
        self.uncertain = set()
        for e in tr.get('uncertainty_runs', []):
            self.uncertain.add((e['page'], str(e['run'])))
            if str(e['run']).startswith('scan:'):
                self.uncertain.add((e['page'], 'ocr:' + str(e['run'])[5:]))

    def _claims(self):
        claims = defaultdict(list)
        kinds = {}
        for k, unit in enumerate(self.units):
            kinds[k] = unit['kind']
            if k in self.removed_units:
                continue
            drop = self.dropped_claims.get(k, set())
            for row, a, b in unit['claims']['rows']:
                if row not in self.rows:
                    continue
                for m in self.rows[row]['runs']:
                    if self.run_line.get((self.rows[row]['page'], str(m))) in drop:
                        continue
                    claims[self.rows[row]['page'], str(m)].append(dict(group=unit['group'], unit=k, row=row, start=a, end=b, partial=a < 0))
            for page, m, partial in unit['claims']['runs']:
                if self.run_line.get((page, str(m))) in drop:
                    continue
                claims[page, str(m)].append(dict(group=unit['group'], unit=k, row=None, start=None, end=None, partial=bool(partial)))
        return claims, kinds

    def _line_statuses(self):
        tv = _trace_module()
        claims, kinds = self._claims()
        out = {}
        for line in self.trace['lines']:
            out[line['id']] = tv.recompute_line(line, claims, kinds, self.run_reason, self.uncertain)
        return out

    def units_in(self, span):
        """Trace units holding characters of a span of the current text."""
        a, b = span
        ks = set()
        for i in range(a, b):
            o = self.origin[i]
            if o >= 0 and self.char_unit[o] >= 0:
                ks.add(self.char_unit[o])
        return ks

    def confirm_duplicate(self, earlier, later, partial=False):
        """The trace says the later copy repeats printed runs the earlier copy holds: units of
        different groups whose own claims name the same printed run (partial: the later copy is
        only part of its unit)."""
        if self.trace is None:
            return True
        ue, ul = self.units_in(earlier), self.units_in(later)
        if not ue or not ul or ue & ul:
            return False
        if any(self.units[k]['kind'] == 'front_matter_printed' for k in ue | ul):
            return False
        if partial and any(self.units[k]['kind'] in KEEP_WHOLE for k in ul):
            return False  # never cut words out of a caption, heading or title
        ge = {self.units[k]['group'] for k in ue}
        gl = {self.units[k]['group'] for k in ul}
        if ge & gl:
            return False  # one unit group (a table, a byline): the trace cannot call it a repeat
        return bool(set().union(*(self.unit_runs(k) for k in ue)) & set().union(*(self.unit_runs(k) for k in ul)))

    def unit_runs(self, k):
        """The printed runs a unit's own claims name (rows resolved to their runs)."""
        unit = self.units[k]
        out = set()
        for row, a, b in unit['claims']['rows']:
            if row in self.rows:
                out |= {(self.rows[row]['page'], str(m)) for m in self.rows[row]['runs']}
        out |= {(page, str(m)) for page, m, _ in unit['claims']['runs']}
        return out

    # ------------------------------------------------------------------ apply
    def apply(self, text, op):
        if text != self.text:
            raise ValueError('tracker: text differs from the tracked copy')
        new, log = RA.apply_operations(text, [op])
        entry = log[0]
        if entry['status'] != 'accepted':
            return new, entry
        if op['op'] == 'flag':
            origin = self.origin + [-1] * (len(new) - len(text))
            if not new.startswith(text):
                return text, dict(entry, status='rejected', reason='tracker: flag did not append')
        else:
            m = mirror(T(text, self.origin), op, entry)
            if m.s != new:
                return text, dict(entry, status='rejected', reason='tracker: character map does not reproduce the applier result')
            origin = m.o
        if self.trace is not None:
            why = self._gate(text, new, origin, op)
            if why:
                return text, dict(entry, status='rejected', reason='trace gate: ' + why, after=dict(entry['before']))
        self.text, self.origin = new, origin
        return new, entry

    def _unit_positions(self, origin):
        pos = defaultdict(list)
        for j, o in enumerate(origin):
            if o >= 0:
                k = self.char_unit[o]
                if k >= 0:
                    pos[k].append(j)
        return pos

    def _gate(self, old, new, origin, op):
        pos = self._unit_positions(origin)
        for k, js in pos.items():
            a, b = js[0], js[-1] + 1
            if b - a != len(js):
                # only whitespace the op wrote may sit inside a unit
                inside = set(js)
                for j in range(a, b):
                    if j not in inside and not (origin[j] < 0 and new[j].isspace()):
                        return f"{self.units[k]['id']} would be cut apart"
        if op['op'] != 'remove_duplicate':
            return None
        prev_removed, prev_dropped = set(self.removed_units), {k: set(v) for k, v in self.dropped_claims.items()}
        old_pos = self._unit_positions(self.origin)
        for k in list(old_pos):
            if k in self.removed_units:
                continue
            if k not in pos:
                self.removed_units.add(k)
                continue
            if len(pos[k]) < len(old_pos[k]):
                kept_n = _norm(new[pos[k][0]:pos[k][-1] + 1])
                was_n = _norm(''.join(old[j] for j in old_pos[k]))
                for lid in self.unit_lines[k]:
                    lt = _norm(self.line_by_id[lid]['text'])
                    if lt and lt in was_n and lt not in kept_n:
                        self.dropped_claims[k].add(lid)
        status = self._line_statuses()
        bad = []
        for lid, (st, _) in status.items():
            was = self.base_status[lid][0]
            if st in ('lost', 'partly_lost') and was not in ('lost', 'partly_lost'):
                bad.append(f"{self.line_by_id[lid]['export_id']} would be lost")
            if st == 'duplicate' and was != 'duplicate':
                bad.append(f"{self.line_by_id[lid]['export_id']} would be printed twice")
        if bad:
            self.removed_units, self.dropped_claims = prev_removed, defaultdict(set, prev_dropped)
            return '; '.join(bad[:3])
        return None

    # ------------------------------------------------------------------ output
    def checked_trace(self, copy_name='copy.checked.md'):
        if self.trace is None:
            return None
        tv = _trace_module()
        tr = _copy.deepcopy(self.trace)
        pos = self._unit_positions(self.origin)
        new_units = []
        id_span = {}
        for k, u in enumerate(tr['units']):
            if k in self.removed_units:
                continue
            if u.get('status') == 'span_unresolved' or u['span'][0] == u['span'][1]:
                if u['span'][0] == u['span'][1]:
                    # an empty unit: place it at the new position of the character it preceded
                    a = u['span'][0]
                    j = next((jj for jj, o in enumerate(self.origin) if o >= a), len(self.text))
                    u['span'] = [j, j]
                new_units.append(u)
                continue
            js = pos.get(k)
            if not js:
                continue
            a, b = js[0], js[-1] + 1
            u['span'] = [a, b]
            u['text'] = self.text[a:b]
            if k in self.dropped_claims:
                drop = self.dropped_claims[k]
                runs_drop = {(self.line_by_id[l]['page'], str(m)) for l in drop for m in self.line_by_id[l]['runs']}
                u['claims'] = {'rows': [c for c in u['claims']['rows']
                                        if not any((self.rows[c[0]]['page'], str(m)) in runs_drop for m in self.rows[c[0]]['runs'])],
                               'runs': [c for c in u['claims']['runs'] if (c[0], str(c[1])) not in runs_drop]}
                u['sources'] = [s for s in u.get('sources', []) if s.get('line_id') not in drop]
            id_span[u['id']] = (a, b)
            new_units.append(u)
        kept_ids = {u['id'] for u in new_units}
        for u in new_units:
            u['group_units'] = [x for x in u.get('group_units', []) if x in kept_ids]
        tr['units'] = new_units
        # line destinations
        self.units = tr['units']
        claims, kinds = defaultdict(list), {}
        rows = {r['row']: r for r in tr['rows']}
        for k, unit in enumerate(new_units):
            kinds[k] = unit['kind']
            for row, a, b in unit['claims']['rows']:
                if row in rows:
                    for m in rows[row]['runs']:
                        claims[rows[row]['page'], str(m)].append(dict(group=unit['group'], unit=k, row=row, start=a, end=b, partial=a < 0))
            for page, m, partial in unit['claims']['runs']:
                claims[page, str(m)].append(dict(group=unit['group'], unit=k, row=None, start=None, end=None, partial=bool(partial)))
        inv = {}
        for j, o in enumerate(self.origin):
            if o >= 0:
                inv[o] = j
        for line in tr['lines']:
            dests = []
            for d in line.get('units') or []:
                if d['unit_id'] not in kept_ids:
                    continue
                if line['id'] in self.dropped_claims.get(self.unit_index[d['unit_id']], set()):
                    continue
                cs = d.get('copy_span')
                if cs:
                    js = [inv[o] for o in range(cs[0], cs[1]) if o in inv]
                    d = dict(d, copy_span=[js[0], js[-1] + 1] if js else list(id_span.get(d['unit_id'], cs)))
                dests.append(d)
            line['units'] = dests
            status, groups = tv.recompute_line(line, claims, kinds, self.run_reason, self.uncertain)
            if line['status'] in ('split', 'split_unverified') and status in ('split', 'split_unverified', 'unit'):
                status = line['status']
            line['status'] = status
            if status not in ('furniture', 'uncertainty'):
                line['groups'] = groups
        self.units = self.trace['units']
        tr['copy'] = {'path': copy_name, 'sha256': hashlib.sha256(self.text.encode('utf-8')).hexdigest(),
                      'characters': len(self.text)}
        tr['checked_from'] = {'path': 'copy.md', 'sha256': self.trace['copy']['sha256'],
                              'removed_units': sorted(self.trace['units'][k]['id'] for k in self.removed_units),
                              'method': 'tools/checkstage/tracemap.py: units carried through every accepted op by a character map'}
        return tr


def _norm(s):
    return re.sub(r'[\W_]+', '', s.lower())


def finish_statistics(tr, report):
    """Copy the validator's recomputed statistics and accounting into the checked trace."""
    tr['statistics'] = report['statistics']
    acc = report['accounting']
    tr['accounting'] = {'lost_lines': acc['lost_lines'], 'duplicate_lines': acc['duplicate_lines'],
                        'split_lines': acc['split_lines'], 'untraced_units': acc['untraced_units'],
                        'unknown_source_runs': tr.get('accounting', {}).get('unknown_source_runs', [])}
    tr['failed'] = bool(acc['lost_lines'] or acc['duplicate_lines'] or acc['untraced_units'])
    return tr
