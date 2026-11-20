#!/bin/bash
# kcf-bench orchestration (PLAN.md 7). Run from the repository root, one phase at a time, strictly in sequence:
#   bash research/kcf-bench-mac/run_all.sh PHASE
# PHASE: jobs | smoke | b | synth | a | arep | compare | host
# Every measured command runs as a child of a fresh measure.py process (same measurement for both methods).
set -euo pipefail
PY=${KCF_BENCH_PY:-/Users/jp/miniforge3/bin/python3}
B=research/kcf-bench-mac
R=$B/runs
CACHES="UA0323 UA0324 UA0325 YD0325T19 YD0325T23 YD0326"
OTHERS="UA0323 UA0325 YD0325T19 YD0325T23 YD0326"
export PYTHONHASHSEED=0
mkdir -p $R
m() { local out=$1; shift; $PY $B/measure.py "$out" -- "$@"; }

case "$1" in
jobs)   # frozen job lists from the sampling rule (common.sample_jobs)
  mkdir -p $R/jobs
  $PY - <<'EOF'
import json, sys
sys.path.insert(0, "research/kcf-bench-mac")
from common import CACHES, load_cache, job_ids, sample_jobs
for name, _ in CACHES:
    s = sample_jobs(name, job_ids(load_cache(name)))
    for k, v in s.items():
        json.dump(v, open("research/kcf-bench-mac/runs/jobs/%s.%s.json" % (name, k), "w"))
    print(name, {k: len(v) for k, v in s.items()})
EOF
  ;;
smoke)  # PLAN.md 7 phase 0: crash test only, results EXCLUDED from every reported number
  mkdir -p $R/smoke
  $PY -c 'import json;json.dump(json.load(open("'$R'/jobs/UA0324.repeat.json"))[:3],open("'$R'/smoke/jobs3.json","w"))'
  m $R/smoke/a.measure.json $PY $B/run_a.py UA0324 $R/smoke/jobs3.json $R/smoke/a.jsonl $TMPDIR/kcfbench_work_smoke
  m $R/smoke/b.measure.json $PY $B/run_b.py UA0324 $R/smoke/b.json $R/smoke/jobs3.json
  $PY $B/compare.py UA0324 $R/smoke/a.jsonl $R/smoke/b.json $R/smoke/compare.json
  m $R/smoke/synth.measure.json $PY $B/synth.py 30 $R/smoke/synth30.json
  ;;
b)      # PLAN.md 7 phase 1: method B, 3 repeats; full cache, the A pass-1 job set, the 50-job repeat set
  mkdir -p $R/b
  for rep in 1 2 3; do
    if [ $rep -gt 1 ]; then export KCF_BENCH_B_SLIM=1; fi
    for c in $CACHES; do
      m $R/b/$c.full.r$rep.measure.json $PY $B/run_b.py $c $R/b/$c.full.r$rep.json
      if [ "$c" != UA0324 ]; then
        m $R/b/$c.pass1.r$rep.measure.json $PY $B/run_b.py $c $R/b/$c.pass1.r$rep.json $R/jobs/$c.pass1.json
      fi
      m $R/b/$c.repeat.r$rep.measure.json $PY $B/run_b.py $c $R/b/$c.repeat.r$rep.json $R/jobs/$c.repeat.json
    done
  done
  ;;
synth)  # PLAN.md 7 phase 2: scaling of B on three larger synthetic grids
  mkdir -p $R/synth
  for s in 250 354 500; do
    m $R/synth/side$s.measure.json $PY $B/synth.py $s $R/synth/side$s.json || true
  done
  ;;
a)      # PLAN.md 7 phase 3: method A pass 1 (UA0324 first 500, five 500-job samples, then UA0324's other 1,018)
  mkdir -p $R/a
  W=$TMPDIR/kcfbench_work
  m $R/a/UA0324.head.measure.json $PY $B/run_a.py UA0324 $R/jobs/UA0324.pass1_head.json $R/a/UA0324.pass1.jsonl $W
  for c in $OTHERS; do
    m $R/a/$c.pass1.measure.json $PY $B/run_a.py $c $R/jobs/$c.pass1.json $R/a/$c.pass1.jsonl $W
  done
  m $R/a/UA0324.tail.measure.json $PY $B/run_a.py UA0324 $R/jobs/UA0324.pass1_tail.json $R/a/UA0324.pass1.jsonl $W
  ;;
aresume) # Amendment 2: rest of YD0326's sample (disk-failed rows set aside), then UA0324's other 1,018
  W=$TMPDIR/kcfbench_work
  m $R/a/YD0326.pass1_resume2.measure.json $PY $B/run_a.py YD0326 $R/jobs/YD0326.pass1_resume2.json $R/a/YD0326.pass1.jsonl $W
  m $R/a/UA0324.tail.measure.json $PY $B/run_a.py UA0324 $R/jobs/UA0324.pass1_tail.json $R/a/UA0324.pass1.jsonl $W
  ;;
arep)   # PLAN.md 7 phase 4: method A repeats 2 and 3 on the 50-job repeat set of every cache
  W=$TMPDIR/kcfbench_work
  for rep in 2 3; do
    for c in $CACHES; do
      m $R/a/$c.repeat.r$rep.measure.json $PY $B/run_a.py $c $R/jobs/$c.repeat.json $R/a/$c.repeat.r$rep.jsonl $W
    done
  done
  ;;
compare) # PLAN.md 7 phase 5: accuracy, untimed (A pass 1 against B full repeat 1)
  mkdir -p $R/compare
  for c in $CACHES; do
    [ -s $R/a/$c.pass1.jsonl ] && $PY $B/compare.py $c $R/a/$c.pass1.jsonl $R/b/$c.full.r1.json $R/compare/$c.json
  done
  ;;
host)
  $PY -c 'import json,sys;sys.path.insert(0,"research/kcf-bench-mac");from common import host_info;print(json.dumps(host_info(),indent=1))' > $R/HOST.json
  { echo "method_A_last_commit_api: $(git log -1 --format=%H -- api)"; echo "method_A_last_commit_integration: $(git log -1 --format=%H -- integration)";
    echo "method_B_last_commit_deadline_field: $(git log -1 --format=%H -- research/harness-2026-11/F-3.1/deadline_field)";
    echo "head: $(git rev-parse HEAD)"; } > $R/COMMITS.txt
  cat $R/HOST.json $R/COMMITS.txt
  ;;
esac
