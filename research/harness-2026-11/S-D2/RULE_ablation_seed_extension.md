# RULE: feature-ablation seed extension (Iris follow-up), fixed before running

Committed before any run of the extension (2026-11-13, ~02:57 UTC). This is a follow-up with its own rule. The verdicts of
TOLERANCE_feature_ablation.md (results/feature_ablation.json, RESULTS §3h) **stand as recorded** and are not re-read.

**Question.** Is "a rate that varies between intervals" a stable explanation of the mean-field NLL far-share gap, or
were two seeds lucky? The 5-seed mean-based rule hides the seed distribution, so this rule reads the distribution.

**Runs.**
- Arms: `baseline`, `time_varying`, `baseline_contig`, `time_varying_contig`.
- Seeds 0–29. Code and generator are unchanged (feature_ablation.py 2b65ef05; guard per addendum 3, fitguard.py 50d4bf4f).
- Command: `feature_ablation.py --seeds 30 --arms baseline time_varying baseline_contig time_varying_contig --ckpt <guarded ckpt> --out results/feature_ablation_seeds30.json`
- Seeds 0–4 are the jobs already reported; they are reused from the guarded checkpoints. Every number is reported for seeds 0–29 and again for the fresh seeds 5–29 alone.
- Read by ablation_seed_reading.py (committed with this rule).

**Reported per arm** (NLL and MCEM far share; truth 0.0718):
- NLL: median, IQR, mean, and the share of seeds above 0.40;
- MCEM: median, mean, SD, and the share of seeds within tolerance per seed (|far − 0.0718| ≤ 0.05);
- guard: fits failed and restart triggers. A guard failure in NLL or MCEM voids that seed for that arm, and the count is reported.

The reference for size is the real data: NLL above 0.40 on 18 of 25 per-fire fits (0.72; median 0.679), and MCEM
within 0.05 of 0.0718 on 22 of 25 (0.88) (results/real_far_share.json). The comparison is descriptive.

*Wording clarification (Iris, 2026-11-13 ~03:05 UTC, during the run; reporting only, no change to any reading):*
- Real fires have no known kernel, so there is no truth to be within. "MCEM within 0.05 of 0.0718" means within 0.05 of the
  synthetic generator's reference value. It is a comparison with that setting, not evidence that 0.072 is right for real fires.
- The INTERMITTENT margin of 0.10 is 3 seeds out of 30, so shares are reported with their counts (k of 30).
  ablation_seed_reading.py was edited during the run to add these counts and this note. Its readings are unchanged.

**Reading, fixed now.** For each time-varying arm against its matching baseline (time_varying vs baseline, and
time_varying_contig vs baseline_contig), using seeds 0–29:
- **STABLE**: NLL median > 0.40, AND share above 0.40 ≥ 0.50, AND MCEM per-seed within-tolerance share ≥ 0.80.
- **INTERMITTENT**: not STABLE, AND share above 0.40 exceeds the baseline's share by at least 0.10.
  (Reported as "unstable, occasional large values", which is the hypothesis in RESULTS §3h.)
- **NOT REPRODUCED**: share above 0.40 exceeds the baseline's share by less than 0.10.

The same reading is also given for seeds 5–29 alone. If the two disagree, both are reported, and the 0–29 reading is
the headline. No further kernel diagnostics follow this extension, whatever the outcome (Iris). Whether the variation is
weather is a separate question that needs the real covariates.

Scope: synthetic generator only (low_far truth, 64×64, T = 240 h, 24 h brackets). This rule makes no claim on part b or on real covariates.

*Disclosed addition (Iris, 2026-11-13 ~03:40 UTC, while the run was under way, before any extension output was read; it adds a condition and loosens nothing):*
- If Owen reruns the extension on his host, MCEM's far-share SD and the per-seed within-tolerance results are reported from both hosts.
- A tolerance check that passes on one host and fails on the other counts as **not within tolerance**. This applies both to the per-seed check |far − 0.0718| ≤ 0.05 and to any SD ≤ 0.05 statement.
- The STABLE/INTERMITTENT/NOT REPRODUCED reading is then taken with those per-seed results. Reason: on the 5-seed run, a host change moved time_varying_contig's MCEM SD from 0.0435 to 0.0480 (Owen, row 54).
