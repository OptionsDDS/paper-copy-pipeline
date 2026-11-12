#!/bin/bash
# usage: copy_all.sh COPY_PAPER_PY BOXER_RUN_DIR OUTDIR -> OUTDIR/NXX/copy.md for N01-N22, from element boxer outputs in BOXER_RUN_DIR/NXX (copied first; the run dir is not written)
C=$(readlink -f "$1"); B=$(readlink -f "$2"); O=$(readlink -f -m "$3"); mkdir -p "$O"
H=$(dirname "$C")
for i in $(seq -w 1 22); do n=N$i; rm -rf "$O/$n"; cp -r "$B/$n" "$O/$n"; rm -f "$O/$n/copy.md"
  pdf=$([ -n "$COPY_PAPER_PDF_MAP" ] && /usr/bin/python3 -I -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$COPY_PAPER_PDF_MAP" "$n")
  if [ -n "$pdf" ]; then   # the two OCR steps copy_pdf.sh runs: shape-drawn labels, then unmapped signs
    [ -f "$H/tools/read_shapes.py" ] && { /usr/bin/python3 -I "$H/tools/read_shapes.py" "$O/$n" "$pdf" > "$O/$n.ocr.log" 2>&1 || true; }
    [ -f "$H/tools/read_signs.py" ] && { /usr/bin/python3 -I "$H/tools/read_signs.py" "$O/$n" "$pdf" >> "$O/$n.ocr.log" 2>&1 || true; }
  fi
  /usr/bin/python3 -I "$C" "$O/$n" > /dev/null 2> "$O/$n.err"; rc=$?
  # 3: copy written; its native trace lists lost/duplicated lines (copy.trace.json)
  if [ $rc -eq 3 ]; then echo "TRACE FINDINGS $n (see $O/$n/copy.checks.json)"; elif [ $rc -ne 0 ]; then echo "FAILED $n (see $O/$n.err)"; fi; done
