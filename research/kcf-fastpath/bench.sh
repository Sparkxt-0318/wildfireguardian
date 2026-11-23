#!/bin/bash
# kcf-fastpath timing (PROTOCOL.md 4). Run from the repository root, one phase at a time:
#   bash research/kcf-fastpath/bench.sh PHASE
# PHASE: host | time | memory
# Every timed run is a child of a fresh, unchanged research/kcf-bench-mac/measure.py process, strictly one at a time.
set -euo pipefail
PY=${KCF_BENCH_PY:-/Users/jp/miniforge3/bin/python3}
F=research/kcf-fastpath
M=research/kcf-bench-mac/measure.py
JOBS=research/kcf-bench-mac/runs/jobs
R=$F/runs
ANS=${KCF_FAST_ANSWERS:-$TMPDIR/kcf-fastpath-answers}     # repeat-1 per-job answers (large; digests are committed)
CACHES=(UA0323 UA0324 UA0325 YD0325T19 YD0325T23 YD0326)
SOLVERS=(baseline scalar prune both)
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p $R $ANS

jobfile() {   # cache, job set -> jobs json ("" for the full cache)
  case "$2" in
    full) echo "" ;;
    pass1) if [ "$1" = UA0324 ]; then echo $JOBS/UA0324.pass1_ran.json; else echo $JOBS/$1.pass1.json; fi ;;
    repeat) echo $JOBS/$1.repeat.json ;;
  esac
}

case "$1" in
host)
  $PY -c 'import json,sys;sys.path.insert(0,"research/kcf-bench-mac");from common import host_info;print(json.dumps(host_info(),indent=1))' > $R/HOST.json
  { echo "head: $(git rev-parse HEAD)"; echo "core.py: $(git log -1 --format=%H -- research/harness-2026-11/F-3.1/deadline_field/core.py)";
    echo "fastfield.py sha256: $(shasum -a 256 $F/fastfield.py | cut -d' ' -f1)"; } > $R/COMMITS.txt
  cat $R/HOST.json $R/COMMITS.txt
  ;;
time)
  START=${KCF_FAST_START_REPEAT:-1}
  for rep in $(seq $START 5); do
    if [ $rep -gt 1 ]; then export KCF_BENCH_B_SLIM=1; else unset KCF_BENCH_B_SLIM; fi
    for k in 0 1 2 3 4 5; do
      ci=$(( (k + rep - 1) % 6 )); c=${CACHES[$ci]}
      for js in full pass1 repeat; do
        mkdir -p $R/$js
        jf=$(jobfile $c $js)
        for s in 0 1 2 3; do
          sv=${SOLVERS[$(( (s + rep - 1 + ci) % 4 ))]}
          tag=$c.$sv.r$rep
          [ -s $R/$js/$tag.measure.json ] && continue          # resume after an interruption: never re-run a finished run
          if [ $rep -eq 1 ]; then out=$ANS/$js.$tag.json; else out=$R/$js/$tag.json; fi
          echo "$(date -u +%FT%TZ) $js $tag" >> $R/LEDGER.txt
          $PY $M $R/$js/$tag.measure.json -- $PY $F/run_fast.py $sv $c $out $jf
          if [ $rep -eq 1 ]; then
            $PY - "$out" "$R/$js/$tag.json" <<'EOF'
import hashlib, json, sys
d = json.load(open(sys.argv[1]))
res = d.pop("results")
d["results"] = None
d["results_sha256"] = hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest()
d["results_jobs"] = len(res)
json.dump(d, open(sys.argv[2], "w"))
EOF
          fi
        done
      done
    done
  done
  ;;
memory)
  mkdir -p $R/memory
  export KCF_BENCH_B_SLIM=1 KCF_FAST_TRACEMALLOC=1
  for c in "${CACHES[@]}"; do
    for sv in "${SOLVERS[@]}"; do
      [ -s $R/memory/$c.$sv.json ] && continue
      $PY $F/run_fast.py $sv $c $R/memory/$c.$sv.json
    done
  done
  ;;
esac
