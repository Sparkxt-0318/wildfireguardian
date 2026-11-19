#!/usr/bin/env bash
# Step 2 dev sweep (h = 5). Each method: 7 outer folds, nested inner CV.
cd "$(dirname "$0")"
for m in QUANTILE-own QUANTILE-fc QUANTILE REGIME REGIME+own KALMAN KALMAN-twin EVT EVT-twin PRETRAIN-archive META-pooled META-init META; do
  python3 step2_run.py --method $m --h ${H:-5} 2>&1 | grep -v "^\[" ; echo "done $m $(date -u +%H:%M)"
done
