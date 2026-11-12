#!/bin/bash
# usage: run_plos.sh BOXER_PY OUTDIR   -> rules 1-8 on the 100 PLOS truth articles, 6 at a time; score with: python3 -I tools/score_jats.py OUTDIR /mnt/ai/datasets/grobid-evaluation/PLOS_1000-sample100
P=$(readlink -f "$1"); O=$(readlink -f -m "$2"); D=/mnt/ai/datasets/grobid-evaluation/PLOS_1000-sample100; mkdir -p $O; : > $O/rc.txt
for a in $(ls $D | grep -v MANIFEST); do
  pdf=$(ls $D/$a/*.pdf 2>/dev/null | head -1); [ -n "$pdf" ] || continue
  ( s=$(date +%s); env -i BOXER_SC_BACKGROUND=white /usr/bin/python3 -I -S $P --pdf $pdf --all-pages --out $O/$a --no-draw > $O/$a.log 2>&1; r1=$?; env -i /usr/bin/python3 -I -S $P --paper $O/$a --no-draw >> $O/$a.log 2>&1; r2=$?; env -i /usr/bin/python3 -I -S $P --authors --pdf $pdf --paper $O/$a >> $O/$a.log 2>&1; r3=$?; echo "$a rc $r1 $r2 $r3 $(( $(date +%s) - s ))s" >> $O/rc.txt ) &
  if (( $(jobs -r | wc -l) >= 6 )); then wait -n; fi
done; wait
