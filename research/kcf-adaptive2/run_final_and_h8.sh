#!/usr/bin/env bash
# 1) sealed transfer test (KR + MAR25) at h=5 for every method; 2) h=8 replication of the dev sweep. Restart-safe.
cd "$(dirname "$0")"
ALL="META META-init META-pooled QUANTILE QUANTILE-own QUANTILE-fc EVT EVT-twin REGIME REGIME+own KALMAN KALMAN-twin PRETRAIN-archive PRETRAIN-sim PRETRAIN-both M_ref PERSIST FIXED"
python3 -W ignore step2_final.py --h 5 --methods $ALL 2>&1 | grep -v "Warning\|res = sm"
echo "done final5 $(date -u +%H:%M)"
for m in FIXED PERSIST M_ref QUANTILE QUANTILE-own QUANTILE-fc REGIME REGIME+own KALMAN KALMAN-twin EVT EVT-twin PRETRAIN-archive PRETRAIN-sim PRETRAIN-both META-pooled META-init META; do
  [ -f derived/step2/${m}_h8.npz ] && continue
  python3 -W ignore step2_run.py --method $m --h 8 2>&1 | grep -v "^\[\|Warning\|res = sm"; echo "done h8 $m $(date -u +%H:%M)"
done
