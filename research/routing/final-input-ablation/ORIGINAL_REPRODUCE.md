# Reproduce the final-input routing constraint ablation

## Inspect recorded evidence without rerunning

1. Read `PROTOCOL.md`, `REPORT.md` and `review/INDEPENDENT_FINAL_REVIEW.md`.
2. Read `analysis/ROWS.csv` or `ROWS.json` (200 executions), `SUMMARY.json` (stable two-repetition outcomes) and `STABLE_MISSIONS.json`.
3. Each row points to its unique own/full-policy grade under `analysis/grades/`. Its exact native input job, result, stage records, process receipt, logs and publication boundary are under `study/raw/ABLATION/<label>/`.
4. The final receipt-bound decision is under `analysis/decisions/`. A0–A3 raw decision names containing FULL refer only to that selected ablation policy; use `full_policy_pass` for the unchanged complete hazard policy.
5. `FREEZE.json` pins the complete scientific source/input/queue set; `GRADING_FREEZE.json` pins the final offline grader. `POLICY_TRANSFORMS.json` documents exactly what was disabled and proves the finite sentinel nonbinding. `FINAL_SOURCE_AND_FULL_ARM_COMPARISON.json` checks the untouched parent scientific outcomes.

## Native runtime

Exact campaign runtime: native macOS arm64, CPython3.12.14, NumPy1.26.4. Only NumPy is a third-party routing/grading dependency; the remaining code is standard library or included project source. The controller requires `/bin/ps`, `/usr/bin/time` and `/usr/bin/caffeinate`. No CUDA, PyTorch, pyproj, pandas or SciPy is used in this routing ablation.

The original interpreter was an existing owner-local environment; it is not copied into the packet. Create an isolated Python3.12 environment and install NumPy1.26.4 for a fresh run. Different hardware/software/OS/cache conditions can change timings, which must be reported separately.

## Fresh execution (new labelled output only)

Do not delete or overwrite completed native evidence to rerun. Use the packaged preparation helper supplied with the repository to copy frozen scientific files and the final grader into a new `WORKSPACE/outputs/<new-labelled-study>/` directory. The new study must preserve every frozen source/input hash and its queue. Keep the prior final results unchanged. Copy the matching pre-run review receipt as provided; no thresholds or mission selection may change.

With `STUDY` set to that NEW labelled directory and `WFG_PYTHON` set to the absolute native Python3.12 interpreter, run:

```bash
/usr/bin/caffeinate -i -s "$WFG_PYTHON" -I -B "$STUDY/study/runner/run_ablation.py" --stage preflight --python "$WFG_PYTHON"
/usr/bin/caffeinate -i -s "$WFG_PYTHON" -I -B "$STUDY/study/runner/run_ablation.py" --stage primary --python "$WFG_PYTHON"
/usr/bin/caffeinate -i -s "$WFG_PYTHON" -I -B "$STUDY/run_grading.py" "$WFG_PYTHON"
"$WFG_PYTHON" -I -B "$STUDY/write_report.py"
```

Use the pre-existing shared timing lease protocol in `WORKSPACE/outputs/SHARED_HEAVY_TIMING_LOCK.json` and local advisory lock `/tmp/wfg/HEAVY.lock`. A missing or foreign busy lease causes a stop; do not override another active study. The launcher preserves prior attempt receipts and never silently retries a scored slot. Keep AC power attached and the lid open.

The original campaign's preflight comprised six lifecycle controls plus five unscored real policy attempts. Their result is not included in the200 slots. An interrupted/failed scored slot must remain recorded, not erased. Independent review of the resulting exact records and refusal scopes is required before reporting a new campaign as verified.

## Interpretation

Own-policy feasibility and unchanged full-policy feasibility are separate. A route accepted in travel-only or contact-only mode can fail the complete hazard model. Deadline failures, label limits, rejections and unresolved checking are not infeasibility proofs. Scoped refusal certificates and independent corroboration are kept distinct. Project adaptive road-radiation certificates are not an independent mathematical radiation-enclosure proof or real-fire validation. Historical300-run ablation and previous80-run final benchmark are separate cohorts.
