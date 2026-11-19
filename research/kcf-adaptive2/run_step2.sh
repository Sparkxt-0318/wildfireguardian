#!/usr/bin/env bash
# Step 2 dev sweep (h = 5). Each method: 7 outer folds, nested inner CV. Skips methods already done (restart-safe).
cd "$(dirname "$0")"
H=${H:-5}
for m in QUANTILE REGIME REGIME+own KALMAN KALMAN-twin EVT EVT-twin PRETRAIN-archive PRETRAIN-sim PRETRAIN-both META-pooled META-init META; do
  [ -f derived/step2/${m}_h${H}.npz ] && continue
  python3 -W ignore step2_run.py --method $m --h $H 2>&1 | grep -v "Warning\|res = sm" ; echo "done $m $(date -u +%H:%M)"
done
