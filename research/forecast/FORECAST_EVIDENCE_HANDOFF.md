# Final forecast evidence handoff

**Frozen forecasting ablation COMPLETE. Shared numerical resources released at 2026-10-14T15:10:39.682809+00:00 (23:12 Asia/Shanghai observation), before the 00:40 target.**

The integration checkpoint remains `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`. Do not replace it with a fitted ablation checkpoint.

- Completed: **17 variants × three seeds = 51 fits**; all original-scoring and custody checks. Independent raw-prediction verification recomputed **459 Brier scores with zero discrepancy**. Fresh relocation replay reproduced **7 scoring CSV tables byte-for-byte**.
- Completed optional frozen work: **72 recursive forecasts**, **six fixed forecasts** (five new, one authenticated reuse), and **32 thermal scenarios**. All 234 independent coverage comparisons matched. No scientific arms remain unfinished.
- Main result: four-scale superiority is **not established**. Single9 mean Korean Brier was **0.129552 vs full 0.138679** (6.58% lower); pooled Brier **0.032759 vs 0.034290** (4.46% lower), but the eight-fire paired interval includes zero.
- Cost: single9 fitting phase **37.18 vs 92.76 s**, **50.64% fewer parameters**. Saved-prediction export latency did not improve. These are training/export scopes, not operational map latency.
- Negative evidence: full-seed17 exact log loss is infinite; simpler controls can outperform the full model. Recursive feedback made small, inconsistent descriptive score changes. More trajectories reduced numerical variation, not established forecast accuracy.
- Population: primary Korean hourly results use **two held-out fires, 12,030 sampled contact-9 cell-hours**. Dynamics uses two different Korean incidents. Labels are retrospective reconstructed hourly burning; do not report the cell-hour counts as independent fires or equate ordinary accuracy with useful prediction.

The original dynamics scorer failure and its missing final original-queue scoring command are preserved. The separately reviewed V2 continuation repairs only prediction-axis handling and reuses the saved first forecast without favorable resimulation; its unavailable latency remains null. No new experiments, checkpoint promotion, source-package changes, Git publication or deployment occurred.

## Read first

1. `ABLATION_RESULTS.md` — complete results, costs, failures and scope.
2. `FORECAST_ABLATION_METHODS.md` and `FORECAST_ABLATION_RESULTS_PAPER.md` — paper-ready English companions.
3. `review/MAIN_RESULTS_CLAIM_REVIEW.md` and `review/DYNAMICS_FINAL_CLAIM_REVIEW.md` — independent interpretation review.
4. `RESOURCE_RELEASE_RECEIPT.json` — exact resource, exit and completion evidence.
5. `REPRODUCE.md`, `DELIVERY_MANIFEST.json`, `FORECAST_ABLATION_EVIDENCE.zip` — portable evidence and commands.

Raw scientific records remain in `campaign/jobs/`, `independent_scoring/`, `dynamics_v2/`, and `review/dynamics_common_mask_v2/`. Original failed attempts are retained in `preflight/`, `native_execution/053_dynamics_and_thermal/`, and `dynamics/`.

Absolute handoff: `/Users/jp/Documents/Codex/2026-09-24/fu/outputs/final_forecast_ablation_20261014_v1/FORECAST_EVIDENCE_HANDOFF.md`

Absolute release receipt: `/Users/jp/Documents/Codex/2026-09-24/fu/outputs/final_forecast_ablation_20261014_v1/RESOURCE_RELEASE_RECEIPT.json`
