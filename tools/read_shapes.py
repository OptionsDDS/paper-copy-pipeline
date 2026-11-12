#!/usr/bin/env python3
"""Optionally read vector-outline table labels with installed, offline OCR.

Run with /usr/bin/python3 -I; Tesseract and pdftoppm need no Python packages.
Inventory every outline, but OCR only those inside a table float. Other outlines
are figure lettering/furniture, not candidate table labels. Join overlapping or
nearby fragments on the same line, within one letter height, in the same float.
The first element owns the reading and joined box; the rest get ocr_joined_to
only after success. Original boxes and counts are preserved.

Boxer coordinates are pixels at params.dpi (normally 150), not PDF points.
Render the joined box at 300 dpi with at most two pixels of margin, then whiten
every intersecting native text-run box, including superscripts. PPM permits
masking with the standard library. Delete each crop after recognition.

Try Tesseract first, then GLM and Paddle workers for any remaining failures.
Only model workers need torch, transformers and Pillow in their own environment.
Nothing is downloaded. Results return before any page changes. Failed reads
leave elements unchanged. Successful reads add ocr_text and ocr_model, and
Tesseract's minimum word confidence as ocr_conf (0–100, not a probability).
Generative workers do not supply confidence; none is fabricated from logits.
Preserve existing OCR. All OCR is provisional, not a verified reading.

Usage:
  /usr/bin/python3 -I tools/read_shapes.py PAPER_DIR PAPER.pdf --report reads.json
  /usr/bin/python3 -I tools/read_shapes.py BATCH_DIR --pdf-map pdfs.json --report reads.json
The PDF map has paper-directory basenames as keys and local PDF paths as values.
Exit 0: all eligible reads available (including skipped non-table outlines).
Exit 1: one or more reads unavailable, safely left unchanged. Exit 2: bad input.
Use --python and --model together to select a repaired/local Transformers env.
"""

import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


MODEL_ROOT = Path('/mnt/ai/models/paper')
ENV_ROOT = Path('/mnt/ai/projects/optionsdds/tools')
DEFAULTS = (
    ('glm', ENV_ROOT / 'paper-glm-ocr-transformers-5.9.0/bin/python',
     MODEL_ROOT / 'GLM-OCR-ca5d8b3e'),
    ('paddle', ENV_ROOT / 'paper-paddleocr-vl-1.6-transformers/bin/python',
     MODEL_ROOT / 'PaddleOCR-VL-1.6-c5630aba'),
)
RENDER_DPI = 300
TESSERACT = ENV_ROOT / 'paper-tesseract-5.3.4/usr/bin/tesseract'
TESSDATA = ENV_ROOT / 'paper-tesseract-5.3.4-tessdata-best-e12c65a91594'
TESS_LIBS = ENV_ROOT / 'paper-tesseract-5.3.4-runtime-libs'


def crop_rectangle(box, dpi, margin=2):
    """Convert absolute boxer pixels to pdftoppm's 300-dpi x/y/width/height."""
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        raise ValueError('outline box must contain four finite coordinates')
    if not math.isfinite(dpi) or dpi <= 0 or not 0 <= margin <= 2:
        raise ValueError('dpi must be positive and margin between zero and two pixels')
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0 or x1 <= 0 or y1 <= 0:
        raise ValueError('outline box is empty or outside the page')
    scale = RENDER_DPI / dpi
    x, y = max(0, math.floor(x0 * scale) - margin), max(0, math.floor(y0 * scale) - margin)
    right, bottom = math.ceil(x1 * scale) + margin, math.ceil(y1 * scale) + margin
    return x, y, right - x, bottom - y


def render_crop(task, prefix):
    x, y, width, height = task['crop_xywh']
    command = ['pdftoppm', '-f', str(task['page']), '-l', str(task['page']),
               '-singlefile', '-r', str(RENDER_DPI), '-x', str(x), '-y', str(y),
               '-W', str(width), '-H', str(height), task['pdf'], str(prefix)]
    subprocess.run(command, check=True, capture_output=True, timeout=30)
    path = prefix.with_suffix('.ppm')
    if task.get('mask_boxes_px'):
        mask_native_text(path, task)
    return path


def mask_native_text(path, task):
    """Whiten native text boxes in pdftoppm's binary, 8-bit RGB PPM crop."""
    data = path.read_bytes()
    header = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255(?:\r\n|\s)', data)
    if not header:
        raise ValueError('pdftoppm did not produce an 8-bit RGB PPM')
    width, height = map(int, header.groups())
    pixels = bytearray(data[header.end():])
    if len(pixels) != width * height * 3:
        raise ValueError('incomplete PPM crop')
    x, y = task['crop_xywh'][:2]
    scale = RENDER_DPI / task['boxer_dpi']
    for b in task['mask_boxes_px']:
        left, top = max(0, math.floor(b[0] * scale) - x), max(0, math.floor(b[1] * scale) - y)
        right, bottom = min(width, math.ceil(b[2] * scale) - x), min(height, math.ceil(b[3] * scale) - y)
        if right <= left or bottom <= top:
            continue
        white = b'\xff' * ((right - left) * 3)
        for row in range(top, bottom):
            pixels[(row * width + left) * 3:(row * width + right) * 3] = white
    path.write_bytes(data[:header.end()] + pixels)


def contains(outer, inner, tolerance=2):
    return (outer[0] - tolerance <= inner[0] and inner[2] <= outer[2] + tolerance and
            outer[1] - tolerance <= inner[1] and inner[3] <= outer[3] + tolerance)


def same_label(a, b):
    """Allow a descender or overlapping glyph, but not a neighboring text line."""
    ah, bh = a[3] - a[1], b[3] - b[1]
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    gap = max(a[0], b[0]) - min(a[2], b[2])
    return (overlap >= .35 * min(ah, bh) and
            abs((a[1] + a[3]) - (b[1] + b[3])) <= max(ah, bh) and
            gap <= min(ah, bh))


def group_fragments(records, page, margin):
    """Join connected fragments only within one table float; defer JSON writes."""
    pending = [r for r in records if r['status'] == 'pending']
    while pending:
        group = [pending.pop(0)]
        for member in group:
            for other in pending[:]:
                if (member['table_float'] == other['table_float'] and
                        same_label(member['box_px'], other['box_px'])):
                    group.append(other)
                    pending.remove(other)
        group.sort(key=lambda r: r['index'])
        first = group[0]
        boxes = [r['box_px'] for r in group]
        box = [min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes)]
        first['ocr_box_px'] = box
        first['joined_indices'] = [r['index'] for r in group[1:]]
        first['crop_xywh'] = crop_rectangle(box, first['boxer_dpi'], margin)
        x, y, w, h = first['crop_xywh']
        scale = first['boxer_dpi'] / RENDER_DPI
        crop_box = [x * scale, y * scale, (x + w) * scale, (y + h) * scale]
        first['mask_boxes_px'] = [e['box_px'] for e in page['elements'] if e.get('kind') == 'text'
                                and min(e['box_px'][2], crop_box[2]) > max(e['box_px'][0], crop_box[0])
                                and min(e['box_px'][3], crop_box[3]) > max(e['box_px'][1], crop_box[1])]
        for member in group[1:]:
            member.update(status='fragment', joined_to=first['id'])


def collect(papers, margin):
    """Snapshot source bytes; never change the source while discovering work."""
    pages, records = {}, []
    for folder, pdf in papers:
        if not folder.is_dir() or not pdf.is_file():
            raise ValueError(f'missing paper folder or PDF: {folder}, {pdf}')
        files = sorted(folder.glob('page-*.json'))
        if not files:
            raise ValueError(f'no page-NN.json files in {folder}')
        for path in files:
            raw = path.read_bytes()
            page = json.loads(raw)
            page_records = []
            tables = {t['id'] for t in page.get('tables', [])}
            floats = [f for f in page.get('floats', [])
                      if re.match(r'^Table\b', f.get('caption', ''), re.I) or
                      (not re.match(r'^(?:Figure|Fig)\b', f.get('caption', ''), re.I) and
                       tables.intersection(f.get('blocks', [])))]
            elements = {e['id']: e for e in page.get('elements', [])}
            for index, element in enumerate(page.get('elements', [])):
                if element.get('kind') != 'outline':
                    continue
                dpi = page.get('params', {}).get('dpi', 150)
                record = dict(paper=folder.name, file=str(path), pdf=str(pdf),
                              page=page['page'], index=index, id=element['id'],
                              count=element.get('count'), box_px=element['box_px'],
                              boxer_dpi=dpi, status='pending')
                try:
                    record['crop_xywh'] = crop_rectangle(element['box_px'], dpi, margin)
                    if not isinstance(page['page'], int) or page['page'] < 1:
                        raise ValueError('page must be a positive integer')
                except (TypeError, ValueError) as exc:
                    record.update(status='error', reason=str(exc))
                if record['status'] == 'pending':
                    owners = [f for f in floats if contains(f['box_px'], element['box_px'])]
                    if owners:
                        record['table_float'] = owners[0]['id']
                    else:
                        record.update(status='skipped', reason='outside table floats: figure lettering or furniture')
                if isinstance(element.get('ocr_text'), str) and element['ocr_text'].strip():
                    record.update(status='existing', text=element['ocr_text'],
                                  model=element.get('ocr_model'), ocr_conf=element.get('ocr_conf'))
                elif elements.get(element.get('ocr_joined_to'), {}).get('ocr_text'):
                    record.update(status='joined', joined_to=element['ocr_joined_to'])
                records.append(record)
                page_records.append(record)
                pages[str(path)] = (raw, page)
            group_fragments(page_records, page, margin)
    return pages, records


def parse_tsv(tsv):
    """Use only nonempty word rows; preserve the minimum reported confidence."""
    words, confidences = [], []
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        if row.get('level') != '5' or not row.get('text', '').strip():
            continue
        confidence = float(row['conf'])
        if not math.isfinite(confidence) or not 0 <= confidence <= 100:
            raise ValueError('invalid Tesseract word confidence')
        words.append(row['text'].strip())
        confidences.append(confidence)
    if not words:
        raise ValueError('Tesseract returned no words')
    return ' '.join(words), min(confidences)


def run_tesseract(tasks, scratch, binary=TESSERACT, data=TESSDATA, libs=TESS_LIBS):
    attempt = dict(backend='tesseract', binary=str(binary), tessdata=str(data), libraries=str(libs))
    if not binary.is_file() or not (data / 'eng.traineddata').is_file():
        attempt['error'] = 'local Tesseract executable or English data missing'
        return [], [attempt]
    results = []
    started = time.perf_counter()
    env = dict(os.environ, OMP_THREAD_LIMIT='1')
    env['LD_LIBRARY_PATH'] = str(libs) + (os.pathsep + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    for task in tasks:
        tick = time.perf_counter()
        crop_path = scratch / 'crop.ppm'
        result = dict(file=task['file'], index=task['index'], status='error')
        try:
            crop_path = render_crop(task, crop_path.with_suffix(''))
            result['render_seconds'] = time.perf_counter() - tick
            command = [str(binary), str(crop_path), 'stdout', '--tessdata-dir', str(data),
                       '-l', 'eng', '--psm', '7', '-c', 'tessedit_create_tsv=1']
            reply = subprocess.run(command, check=True, capture_output=True, text=True, env=env, timeout=30)
            text, confidence = parse_tsv(reply.stdout)
            result.update(status='read', text=text, ocr_conf=confidence, model=str(binary))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result['reason'] = f'{type(exc).__name__}: {exc}'
        finally:
            crop_path.unlink(missing_ok=True)
        result['seconds'] = time.perf_counter() - tick
        results.append(result)
    attempt.update(seconds=time.perf_counter() - started,
                   read=sum(r['status'] == 'read' for r in results))
    if not attempt['read']:
        attempt['error'] = 'Tesseract could not read any eligible labels'
    return results, [attempt]


def worker(request_path):
    """Run only with the OCR environment's Python; the parent owns JSON writes."""
    request = json.loads(Path(request_path).read_text())
    output = Path(request['output'])
    started = time.perf_counter()
    try:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        from PIL import Image
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable; CPU cannot meet the crop latency requirement')
        torch.set_num_threads(2)
        model_path = request['model']
        # Native model implementations only; no Hub calls or downloaded code.
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True,
                                                  trust_remote_code=False)
        model = AutoModelForImageTextToText.from_pretrained(
            model_path, local_files_only=True, trust_remote_code=False,
            dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    except Exception as exc:
        output.write_text(json.dumps(dict(error=f'{type(exc).__name__}: {exc}',
                                         load_seconds=time.perf_counter() - started)))
        return 1
    load_seconds = time.perf_counter() - started
    results = []
    for task in request['tasks']:
        tick = time.perf_counter()
        crop_path = output.parent / 'crop.ppm'
        result = dict(file=task['file'], index=task['index'], status='error')
        try:
            crop_path = render_crop(task, crop_path.with_suffix(''))
            render_seconds = time.perf_counter() - tick
            with Image.open(crop_path) as source:
                crop = source.convert('RGB')
            messages = [{'role': 'user', 'content': [
                {'type': 'image', 'image': crop},
                {'type': 'text', 'text': 'Text Recognition:' if request['backend'] == 'glm' else 'OCR:'},
            ]}]
            inputs = processor.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                return_dict=True, return_tensors='pt').to(model.device)
            inputs.pop('token_type_ids', None)
            with torch.inference_mode():
                generated = model.generate(**inputs, do_sample=False, use_cache=True, max_new_tokens=128)
            tokens = generated[0][inputs['input_ids'].shape[1]:]
            text = ' '.join(processor.decode(tokens, skip_special_tokens=True).split())
            eos = model.generation_config.eos_token_id
            eos = eos if isinstance(eos, list) else [eos]
            if len(tokens) >= 128 and tokens[-1].item() not in eos:
                raise ValueError('OCR reached the token limit; truncated text not stored')
            if not text:
                raise ValueError('OCR returned no text')
            result.update(status='read', text=text, model=model_path,
                          render_seconds=render_seconds)
        except Exception as exc:
            result['reason'] = f'{type(exc).__name__}: {exc}'
        finally:
            crop_path.unlink(missing_ok=True)
        result['seconds'] = time.perf_counter() - tick
        results.append(result)
    output.write_text(json.dumps(dict(load_seconds=load_seconds, results=results)))
    return 0


def run_worker(tasks, candidates, scratch):
    """Try installed environments in order; startup errors never touch pages."""
    attempts, readings = [], []
    for backend, python, model in candidates:
        attempt = dict(backend=backend, python=str(python), model=str(model))
        attempts.append(attempt)
        if not python.is_file() or not model.is_dir():
            attempt['error'] = 'local Python executable or model directory missing'
            continue
        output = scratch / 'results.json'
        output.unlink(missing_ok=True)
        request = scratch / 'request.json'
        request.write_text(json.dumps(dict(backend=backend, model=str(model),
                                           output=str(output), tasks=tasks)))
        command = [str(python), '-I', '-B', str(Path(__file__).resolve()), '--worker', str(request)]
        attempt['command'] = command
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                   HF_HUB_DISABLE_TELEMETRY='1', HF_HOME=str(scratch / 'hf'),
                   HF_MODULES_CACHE=str(scratch / 'modules'),
                   XDG_CACHE_HOME=str(scratch / 'cache'), TMPDIR=str(scratch),
                   CUDA_CACHE_PATH=str(scratch / 'cuda'), TORCHINDUCTOR_CACHE_DIR=str(scratch / 'torch'))
        tick = time.perf_counter()
        try:
            completed = subprocess.run(command, capture_output=True, text=True, env=env,
                                       timeout=120 + 30 * len(tasks))
            attempt['seconds'] = time.perf_counter() - tick
            attempt['returncode'] = completed.returncode
            # Keep the full startup error (not weights/loading progress) in the report.
            if completed.returncode:
                attempt['stderr'] = completed.stderr[-8000:]
            reply = json.loads(output.read_text()) if output.is_file() else {}
            if 'load_seconds' in reply:
                attempt['load_seconds'] = reply['load_seconds']
            if completed.returncode == 0 and 'results' in reply:
                expected = {(t['file'], t['index']) for t in tasks}
                got = [(r['file'], r['index']) for r in reply['results']]
                if len(got) != len(expected) or set(got) != expected:
                    raise ValueError('worker returned a mismatched element inventory')
                if any(r['status'] == 'read' for r in reply['results']):
                    successes = [r for r in reply['results'] if r['status'] == 'read']
                    readings.extend(successes)
                    done = {(r['file'], r['index']) for r in successes}
                    tasks = [t for t in tasks if (t['file'], t['index']) not in done]
                    if not tasks:
                        break
                    continue
                attempt['error'] = 'model loaded but no crop could be read'
                attempt['crop_errors'] = reply['results']
                continue
            attempt['error'] = reply.get('error') or 'worker could not start; see stderr'
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            attempt.update(error=f'{type(exc).__name__}: {exc}', seconds=time.perf_counter() - tick)
    return readings, attempts


def run_backends(tasks, candidates, scratch, binary=TESSERACT, data=TESSDATA, libs=TESS_LIBS):
    """Keep successful reads; send only unresolved labels to later backends."""
    results, attempts = run_tesseract(tasks, scratch, binary, data, libs)
    by_key = {(r['file'], r['index']): r for r in results}
    pending = [t for t in tasks if by_key.get((t['file'], t['index']), {}).get('status') != 'read']
    if pending:
        fallback, tried = run_worker(pending, candidates, scratch)
        attempts.extend(tried)
        by_key.update({(r['file'], r['index']): r for r in fallback})
    return [by_key.get((t['file'], t['index']),
                       dict(file=t['file'], index=t['index'], status='no_backend',
                            reason='no local OCR backend ran; see attempts')) for t in tasks], attempts


def apply_results(pages, records, results):
    """Only successful, nonempty readings may change a JSON element."""
    by_key = {(r['file'], r['index']): r for r in records}
    changed = set()
    for result in results:
        record = by_key[result['file'], result['index']]
        if record['status'] != 'pending':
            continue
        if result['status'] == 'read':
            if not isinstance(result.get('text'), str) or not result['text'].strip() or not result.get('model'):
                record.update(status='error', reason='worker returned invalid OCR metadata')
                continue
            confidence = result.get('ocr_conf')
            if confidence is not None and (not isinstance(confidence, (int, float)) or
                                           not math.isfinite(confidence) or not 0 <= confidence <= 100):
                record.update(status='error', reason='worker returned invalid OCR confidence')
                continue
            element = pages[record['file']][1]['elements'][record['index']]
            element.update(ocr_text=result['text'], ocr_model=result['model'])
            if confidence is not None:
                element['ocr_conf'] = confidence
            if record.get('joined_indices'):
                element['ocr_box_px'] = record['ocr_box_px']
                for index in record['joined_indices']:
                    pages[record['file']][1]['elements'][index]['ocr_joined_to'] = record['id']
                    by_key[record['file'], index].update(status='joined', joined_to=record['id'])
            changed.add(record['file'])
        record.update(result)
    for record in records:
        if record['status'] == 'fragment':
            record.update(status='unavailable', reason='joined label could not be read; element unchanged')
    # Detect any concurrent edit before writing any page.
    for filename in changed:
        if Path(filename).read_bytes() != pages[filename][0]:
            raise ValueError(f'page changed during OCR; refusing to overwrite: {filename}')
    for filename in sorted(changed):
        path = Path(filename)
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.ocr-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(pages[filename][1], stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            temporary.chmod(path.stat().st_mode & 0o777)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return len(changed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('folder', type=Path)
    parser.add_argument('pdf', type=Path, nargs='?')
    parser.add_argument('--pdf-map', type=Path)
    parser.add_argument('--python', type=Path, help='local model-environment Python (requires --model)')
    parser.add_argument('--model', type=Path, help='local Transformers model directory (requires --python)')
    parser.add_argument('--backend', choices=('glm', 'paddle'), default='glm')
    parser.add_argument('--tesseract', type=Path, default=TESSERACT, help='local Tesseract executable, tried first')
    parser.add_argument('--tessdata', type=Path, default=TESSDATA, help='folder containing eng.traineddata')
    parser.add_argument('--tesseract-libs', type=Path, default=TESS_LIBS, help='Tesseract shared library directory')
    parser.add_argument('--margin', type=int, default=2, choices=range(3), help='crop margin at 300 dpi, at most 2 pixels')
    parser.add_argument('--report', type=Path, help='JSON inventory, attempts, readings and timings')
    args = parser.parse_args(argv)
    if bool(args.python) != bool(args.model) or bool(args.pdf) == bool(args.pdf_map):
        parser.error('supply a PDF or --pdf-map, and both --python/--model if overriding')
    started = time.perf_counter()
    try:
        if args.pdf_map:
            mapping = json.loads(args.pdf_map.read_text())
            papers = [(args.folder.resolve() / name, Path(pdf).resolve()) for name, pdf in sorted(mapping.items())]
        else:
            papers = [(args.folder.resolve(), args.pdf.resolve())]
        pages, records = collect(papers, args.margin)
        pending = [r for r in records if r['status'] == 'pending']
        attempts, changed = [], 0
        if pending:
            candidates = [(args.backend, args.python.absolute(), args.model.resolve())] if args.python else DEFAULTS
            with tempfile.TemporaryDirectory(prefix='.read-shapes-', dir=args.folder) as scratch:
                results, attempts = run_backends(pending, candidates, Path(scratch),
                                                args.tesseract, args.tessdata, args.tesseract_libs)
                changed = apply_results(pages, records, results)
        counts = {status: sum(r['status'] == status for r in records)
                  for status in sorted({r['status'] for r in records})}
        report = dict(papers=len(papers), outlines=len(records), statuses=counts,
                      changed_pages=changed, seconds=time.perf_counter() - started,
                      attempts=attempts, elements=records)
        if args.report:
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: v for k, v in report.items() if k not in ('elements', 'attempts')}))
        for attempt in attempts:
            if attempt.get('error'):
                print(f"{attempt['backend']}: {attempt['error']}\n{attempt.get('stderr', '').strip()}", file=sys.stderr)
        return int(any(r['status'] not in ('read', 'existing', 'joined', 'skipped') for r in records))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'read_shapes: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        raise SystemExit(worker(sys.argv[2]))
    raise SystemExit(main())
