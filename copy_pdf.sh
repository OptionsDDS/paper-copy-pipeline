#!/bin/bash
# usage: copy_pdf.sh PAPER.pdf OUTDIR [--copy-only]  -> OUTDIR/copy.md (element boxer rules 1-8, then the copy)
# --copy-only skips the element boxer and OCR steps (they ran before into OUTDIR).
#
# Local page readers (MinerU2.5-Pro and OvisOCR2, tools/run_readers.py on the GPU):
#   COPY_READERS=auto  (the default) copy once without readers; tools/agree.py --needed lists the pages an
#                      agreement could repair (gated or uncertain tables, formula placeholders,
#                      flagged scan pages); only those pages are read, and the copy is made again
#                      with COPY_READERS_DIR, where tools/agree.py accepts a reading only when both
#                      readers agree and every token matches the PDF's printed text. No pages, no
#                      GPU (status 75 from the runner) or a failed second copy: the first copy stands.
#   COPY_READERS=off   one copy, no readers.
#   COPY_READERS=defer the first copy and the page list only (copy_folder.sh reads all papers in one batch).
#   COPY_READERS_DIR=DIR (set by the caller) one copy that uses readings already in DIR.
# Reader outputs are cached per paper in OUTDIR/readers, or in COPY_READERS_CACHE/<PDF sha256>.
#
# Second pass (tools/secondpass, after the final copy; COPY_SECONDPASS=0 skips it): an independent
# run of the general rules in tools/secondpass/rules.txt writes OUTDIR/copy.secondpass.json and adds
# the items of its "list" rules to the copy's uncertainty list (the copy text is not changed). It
# never changes the exit status; a failure is noted in OUTDIR/secondpass.log.
H=$(cd "$(dirname "$0")" && pwd); P=$H/standalone/element_boxer_sc.py; pdf=$1; out=$2; mkdir -p "$out"
if [ "$3" != --copy-only ]; then
env -i PATH=/usr/bin BOXER_SC_BACKGROUND=white /usr/bin/python3 -I -S $P --pdf "$pdf" --all-pages --out "$out" --no-draw > "$out/boxer.log" 2>&1 || { echo "rules 1-7 pages failed: $out/boxer.log"; exit 1; }
# lane r5-line: where the lane changed lines of page 1, rules 6-8 also run on the page as built without the lane (in
# $out/r5base); tools/r5_frontcheck.py keeps that build when the title or the number of authors or affiliations differ
if [ -f "$out/r5base-page-01.json" ]; then
  mkdir -p "$out/r5base" && cp "$out"/page-[0-9]*.json "$out/r5base/" && cp "$out/r5base-page-01.json" "$out/r5base/page-01.json"
  env -i PATH=/usr/bin /usr/bin/python3 -I -S $P --paper "$out/r5base" --no-draw > "$out/r5base/boxer.log" 2>&1
  env -i PATH=/usr/bin /usr/bin/python3 -I -S $P --authors --pdf "$pdf" --paper "$out/r5base" >> "$out/r5base/boxer.log" 2>&1
fi
env -i PATH=/usr/bin /usr/bin/python3 -I -S $P --paper "$out" --no-draw >> "$out/boxer.log" 2>&1 || { echo "paper pass failed: $out/boxer.log"; exit 1; }
env -i PATH=/usr/bin /usr/bin/python3 -I -S $P --authors --pdf "$pdf" --paper "$out" >> "$out/boxer.log" 2>&1 || echo "rule 8 failed (copy goes on without authors): $out/boxer.log"
if [ -f "$out/r5base-page-01.json" ]; then /usr/bin/python3 -I $H/tools/r5_frontcheck.py "$out" >> "$out/boxer.log" 2>&1 || echo "first-page check failed: $out/boxer.log"; fi
/usr/bin/python3 -I $H/tools/read_shapes.py "$out" "$(readlink -f "$pdf")" >> "$out/boxer.log" 2>&1 || echo "shape-text OCR step failed or unavailable (copy goes on with [unreadable] cells): $out/boxer.log"
/usr/bin/python3 -I $H/tools/read_signs.py "$out" "$(readlink -f "$pdf")" >> "$out/boxer.log" 2>&1 || echo "sign OCR step failed or unavailable (copy keeps unresolved glyphs): $out/boxer.log"
fi
# copy_paper.py applies COPY_READERS_DIR once, then binds copy.floats.json to the
# agreement output hash. Each copy here is a fresh copy from the boxer files, so the
# previous run's agreement records are removed first (agree.py refuses to re-apply
# over a changed copy that still has them).
# After a written copy (status 0 or 3): the rule-based second pass (on by default; COPY_SECONDPASS=0 skips it)
# adds its findings to the copy's uncertainty list, then the optional check stage, off by default
# (COPY_CHECK=auto: a local page-reading model (Qwen3.6-27B, GPU) answers narrow questions and a code
# duplicate finder looks for blocks printed twice; the safe applier writes copy.checked.md beside copy.md).
# Neither changes the exit status. See tools/secondpass/secondpass.py and tools/checkstage/run.py.
finish() {  # finish STATUS: second pass and check stage on a written copy, then exit with STATUS
  st=$1
  if { [ "$st" -eq 0 ] || [ "$st" -eq 3 ]; } && [ -f "$out/copy.md" ]; then
    if [ "${COPY_SECONDPASS:-1}" != 0 ]; then
      /usr/bin/python3 -I $H/tools/secondpass/secondpass.py "$out" "$(readlink -f "$pdf")" --write-list > "$out/secondpass.log" 2>&1 \
        || echo "second pass failed (copy stands without it): $out/secondpass.log"
    fi
    if [ "${COPY_CHECK:-off}" = auto ]; then
      /usr/bin/python3 -I $H/tools/checkstage/run.py "$out" "$(readlink -f "$pdf")" > "$out/check.log" 2>&1 || echo "check stage failed (copy.md unchanged): $out/check.log"
    fi
  fi
  exit "$st"
}
copy() {  # copy READERS_DIR (empty: no readers); 3 = copy.md written, its native trace lists lost or duplicated lines
  rm -f "$out/copy.agree.json" "$out/copy.agree-before.md" "$out/copy.readers-page.json"
  COPY_READERS_DIR="$1" COPY_PAPER_PDF="$(readlink -f "$pdf")" /usr/bin/python3 -I $H/copy_paper.py "$out"   # the PDF lets the copy split table cells by character positions
}
if [ -n "$COPY_READERS_DIR" ]; then copy "$COPY_READERS_DIR"; finish $?; fi
mode=${COPY_READERS:-auto}
case "$mode" in off|auto|defer) ;; *) echo "COPY_READERS must be off, auto or defer, not '$mode'"; exit 2;; esac
copy ""; status=$?
if [ "$mode" = off ] || { [ "$status" -ne 0 ] && [ "$status" -ne 3 ]; }; then finish "$status"; fi
pages=$(/usr/bin/python3 -I $H/tools/agree.py --needed "$out" 2>> "$out/readers.log") || { echo "reader page list failed (copy stands without readers): $out/readers.log"; finish "$status"; }
if [ -z "$pages" ]; then finish "$status"; fi
if [ "$mode" = defer ]; then exit "$status"; fi   # the deferred second copy (COPY_READERS_DIR) runs the second pass and check stage
if [ -n "$COPY_READERS_CACHE" ]; then cache=$COPY_READERS_CACHE/$(sha256sum < "$pdf" | cut -c1-64); else cache=$out/readers; fi
/usr/bin/python3 -I $H/tools/run_readers.py "$pdf" "$cache" --pages "$pages" >> "$out/readers.log" 2>&1; rc=$?
if [ "$rc" -eq 75 ]; then echo "page readers unavailable (copy stands without readers): $out/readers.log"; finish "$status"; fi
[ "$rc" -eq 0 ] || echo "some reader pages failed (unread pages stay as copied): $out/readers.log"
copy "$cache"; second=$?
if [ "$second" -ne 0 ] && [ "$second" -ne 3 ]; then
  echo "copy with readers failed (status $second); copying again without readers: $out/readers.log"
  copy "" >> "$out/readers.log" 2>&1; finish $?
fi
finish "$second"
