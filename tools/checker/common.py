"""Versioned, text-free answer contract shared by the CPU and GPU tools."""
import hashlib
import json
import math
from pathlib import Path

VERSION = 1
CLASSES = ['body', 'caption', 'footnote', 'running head', 'page number',
           'figure lettering', 'main header', 'table', 'other']
HEADERS = ['title', 'subtitle', 'authors', 'affiliation', 'correspondence',
           'dates', 'journal information', 'abstract', 'keywords', 'other']
TYPES = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def load(path):
    return parse(Path(path).read_text(encoding='utf-8'))


def parse(text):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError(f'duplicate JSON key: {k}')
            out[k] = v
        return out
    def constant(value):
        raise ValueError(f'non-finite JSON number: {value}')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def read_jsonl(path):
    return [parse(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def safe_asset(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError(f'asset escapes bundle: {relative}')
    return path


def response_schema(question):
    """No arbitrary string fields: answers, confidence, IDs and outline coordinates."""
    kind = question['type']
    answer = dict(type='string', enum=CLASSES if kind == 'Q1' else HEADERS if kind == 'Q4' else ['yes', 'no'])
    properties = dict(answer=answer, confidence=dict(type='number', minimum=0, maximum=1))
    if kind in ('Q3', 'Q5'):
        properties['regions'] = dict(type='array', maxItems=16, items=dict(
            type='array', minItems=4, maxItems=4,
            items=dict(type='integer', minimum=0, maximum=1000)))
    if kind == 'Q5':
        properties['affected'] = dict(type='array', maxItems=len(question['choices']) + 1,
                                      items=dict(type='string', enum=question['choices'] + ['unboxed']))
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def validate_answer(question, answer):
    schema = response_schema(question)
    if not isinstance(answer, dict) or set(answer) != set(schema['required']):
        raise ValueError('answer fields do not match fixed schema')
    if answer['answer'] not in schema['properties']['answer']['enum']:
        raise ValueError('answer is not an allowed choice')
    c = answer['confidence']
    if type(c) not in (int, float) or not math.isfinite(c) or not 0 <= c <= 1:
        raise ValueError('confidence must be a finite number from 0 to 1')
    if question['type'] in ('Q3', 'Q5'):
        boxes = answer['regions']
        if not isinstance(boxes, list) or len(boxes) > 16:
            raise ValueError('invalid region list')
        for b in boxes:
            if (not isinstance(b, list) or len(b) != 4 or
                any(type(x) is not int or not 0 <= x <= 1000 for x in b) or
                b[0] >= b[2] or b[1] >= b[3]):
                raise ValueError('invalid normalized outline')
        if question['type'] == 'Q3' and bool(boxes) != (answer['answer'] == 'yes'):
            raise ValueError('Q3 yes requires outlines; no requires none')
    if question['type'] == 'Q5':
        ids = answer['affected']
        if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids) or
            len(ids) != len(set(ids)) or any(x not in question['choices'] + ['unboxed'] for x in ids)):
            raise ValueError('unknown or repeated float/caption choice')
        if bool(ids) != (answer['answer'] == 'no'):
            raise ValueError('Q5 no requires affected IDs; yes requires none')
        if bool(answer['regions']) != ('unboxed' in ids):
            raise ValueError('unboxed Q5 content requires outlines, and only unboxed content takes outlines')
    return answer


def load_bundle(path):
    path = Path(path)
    bundle = load(path / 'bundle.json')
    expected = bundle.pop('bundle_sha256')
    if digest(bundle) != expected or bundle.get('version') != VERSION:
        raise ValueError('bundle hash or version mismatch')
    bundle['bundle_sha256'] = expected
    qs = bundle['questions']
    if len({q['id'] for q in qs}) != len(qs):
        raise ValueError('duplicate question IDs')
    return bundle


def verify_images(path, bundle):
    for page in bundle['document']['pages']:
        if file_hash(safe_asset(path, page['image'])) != page['image_sha256']:
            raise ValueError(f'page image changed: {page["image"]}')


def answer_records(bundle, records):
    by_id = {q['id']: q for q in bundle['questions']}
    result = {}
    for r in records:
        qid = r.get('question_id')
        if qid not in by_id or qid in result:
            raise ValueError(f'unknown or duplicate question ID: {qid}')
        if r.get('bundle_sha256') != bundle['bundle_sha256'] or r.get('question_sha256') != digest(by_id[qid]):
            raise ValueError(f'stale answer: {qid}')
        if r.get('status') == 'ok':
            validate_answer(by_id[qid], r['answer'])
        elif r.get('status') != 'error' or 'answer' in r:
            raise ValueError(f'invalid response status: {qid}')
        result[qid] = r
    return result


def decision(question, record, threshold=0.85):
    """Distinguish model disagreement, uncertainty, missing work and annotations."""
    if record is None:
        return 'missing'
    if record['status'] != 'ok':
        return 'invalid'
    a = validate_answer(question, record['answer'])
    if a['confidence'] < threshold:
        return 'uncertain'
    k, value = question['type'], a['answer']
    if k in ('Q1', 'Q4'):
        expected = question.get('expected', [])
        return ('agree' if value in expected else 'disagree') if expected else 'annotation'
    if k in ('Q2', 'Q5'):
        return 'agree' if value == 'yes' else 'disagree'
    return 'disagree' if value == 'yes' else 'agree'
