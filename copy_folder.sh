#!/bin/bash
# usage: copy_folder.sh IN_DIR OUT_DIR  -> OUT_DIR/<name>.md for every PDF in IN_DIR (4 at a time)
# A paper whose copy says "NO COPY" at the top is a scan; one with a "Places the program is not sure of" list has spots to check.
# COPY_READERS as in copy_pdf.sh (default auto). With auto, every paper is copied first (COPY_READERS=defer), then the
# local page readers read the listed pages of all papers in one batch (one load of each engine), then
# only the papers with pages are copied again with their readings (copy_pdf.sh --copy-only).
# COPY_CHECK=auto: after the copies, one check-stage batch over the written papers -> OUT_DIR/<name>.checked.md.
# jobs -rp: one line per job (jobs -r prints a multi-line subshell body over several lines)
H=$(cd "$(dirname "$0")" && pwd); in=$1; out=$2; mkdir -p "$out/work"
mode=${COPY_READERS:-auto}
case "$mode" in off|auto) ;; *) echo "COPY_READERS must be off or auto for a folder, not '$mode'"; exit 2;; esac
first=$mode; [ "$mode" = auto ] && first=defer
for pdf in "$in"/*.pdf; do
  [ -e "$pdf" ] || continue
  name=$(basename "$pdf" .pdf)
  # copy_pdf.sh status 3: copy written, its native trace lists lost/duplicated lines
  ( COPY_CHECK=off COPY_READERS=$first "$H/copy_pdf.sh" "$pdf" "$out/work/$name" > "$out/work/$name.log" 2>&1; echo $? > "$out/work/$name.rc" ) &
  if (( $(jobs -rp | wc -l) >= 4 )); then wait -n; fi
done; wait
if [ "$mode" = auto ]; then
  # One reader batch over every paper's listed pages; caches as copy_pdf.sh names them.
  /usr/bin/python3 -I - "$in" "$out/work" "${COPY_READERS_CACHE:-}" > "$out/work/readers-jobs.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
src, work, shared = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
jobs = []
for pdf in sorted(src.glob('*.pdf')):
    paper = work / pdf.stem
    try:
        rc = int((work / (pdf.stem + '.rc')).read_text())
        needed = json.loads((paper / 'copy.readers-needed.json').read_text())['pages']
    except (OSError, ValueError, KeyError):
        continue
    if rc not in (0, 3) or not needed:
        continue
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    cache = Path(shared) / digest if shared else paper / 'readers'
    jobs.append(dict(pdf=str(pdf.resolve()), out=str(cache), pages=sorted(map(int, needed)), paper=str(paper)))
print(json.dumps(jobs, indent=1))
PY
  if [ "$(head -c 2 "$out/work/readers-jobs.json")" != "[]" ]; then
    /usr/bin/python3 -I "$H/tools/run_readers.py" --jobs "$out/work/readers-jobs.json" --home "$out/work/readers-batch" > "$out/work/readers.log" 2>&1; rc=$?
    if [ "$rc" -eq 75 ]; then echo "page readers unavailable; copies stand without readers (see $out/work/readers.log)"
    else
      [ "$rc" -eq 0 ] || echo "some reader pages failed; unread pages stay as copied (see $out/work/readers.log)"
      /usr/bin/python3 -I -c 'import json,sys; [print(j["paper"]+"\t"+j["out"]) for j in json.load(open(sys.argv[1]))]' "$out/work/readers-jobs.json" |
      while IFS=$'\t' read -r paper cache; do
        name=$(basename "$paper")
        ( COPY_CHECK=off COPY_READERS_DIR=$cache "$H/copy_pdf.sh" "$in/$name.pdf" "$paper" --copy-only >> "$out/work/$name.log" 2>&1; rc=$?
          if [ $rc -ne 0 ] && [ $rc -ne 3 ]; then  # keep a copy: again without readers
            echo "copy with readers failed (status $rc); copying again without readers" >> "$out/work/$name.log"
            COPY_CHECK=off COPY_READERS=off "$H/copy_pdf.sh" "$in/$name.pdf" "$paper" --copy-only >> "$out/work/$name.log" 2>&1; rc=$?
          fi; echo $rc > "$out/work/$name.rc" ) &
        if (( $(jobs -rp | wc -l) >= 4 )); then wait -n; fi
      done; wait
    fi
  fi
fi
for pdf in "$in"/*.pdf; do
  [ -e "$pdf" ] || continue
  name=$(basename "$pdf" .pdf); rc=$(cat "$out/work/$name.rc" 2>/dev/null || echo 1)
  # a deferred copy that was not copied again (no reader pages ran) still gets its second pass
  if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ "${COPY_SECONDPASS:-1}" != 0 ] && [ ! "$out/work/$name/copy.secondpass.json" -nt "$out/work/$name/copy.md" ]; then
    /usr/bin/python3 -I "$H/tools/secondpass/secondpass.py" "$out/work/$name" "$(readlink -f "$pdf")" --write-list > "$out/work/$name/secondpass.log" 2>&1 \
      || echo "second pass failed for $name (copy stands without it)"
  fi
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then cp "$out/work/$name/copy.md" "$out/$name.md" && echo "done  $name$([ "$rc" -eq 3 ] && echo ' (trace findings listed)')"
  else echo "FAILED $name (see $out/work/$name.log)"; fi
done
# COPY_CHECK=auto: one check-stage batch for the folder (the model loads once), OUT_DIR/<name>.checked.md
if [ "${COPY_CHECK:-off}" = auto ]; then
  list="$out/work/check-list.txt"; : > "$list"
  for pdf in "$in"/*.pdf; do name=$(basename "$pdf" .pdf)
    rc=$(cat "$out/work/$name.rc" 2>/dev/null || echo 1)
    { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && printf '%s\t%s\n' "$out/work/$name" "$(readlink -f "$pdf")" >> "$list"; done
  if [ -s "$list" ]; then
    /usr/bin/python3 -I "$H/tools/checkstage/run.py" --batch "$list" > "$out/work/check.log" 2>&1 || echo "check stage: some papers failed (see $out/work/check.log)"
    for pdf in "$in"/*.pdf; do name=$(basename "$pdf" .pdf)
      [ -f "$out/work/$name/copy.checked.md" ] && cp "$out/work/$name/copy.checked.md" "$out/$name.checked.md" && echo "checked $name"; done
  fi
fi
