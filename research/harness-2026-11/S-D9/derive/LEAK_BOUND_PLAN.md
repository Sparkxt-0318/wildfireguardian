# Survey-timing leak bound: plan and "material" threshold (S-D9). NOT RUN

**Status.** This file was written and committed before any run. It is a part-a-only measurement and is descriptive. The orchestrator approved it on 2026-11-12, adopting Iris's item 5.
- Marcus runs it with the part-a refits, on part-a fire folds, and not before them.
- Owen verifies it.
- It reads nothing from parts b, c or d, and no H-test fire.

## Why
Two files on Main carry survey timing for every NIROPS incident, including the sealed parts: `data-fetch/nirops_incidents_v2.csv` and `data-fetch/incident_metadata.csv`. The fields are `first_utc`, `last_utc`, `days` and `discovery_utc`.
- At any cutoff, `last_utc` (and `days`) is **future information**. It tells how much longer the fire was surveyed, which is a proxy for how long and how far it kept growing.
- This measurement bounds how much a model could gain from that information. If even a model handed the information directly gains little, a design choice that leaked it indirectly could have gained no more.

## The forbidden features
They are computed per training interval, from **part-a** metadata only:
- **F1, remaining survey days.** `r = max(0, last_utc − cutoff) / 24 h`, entered as `log1p(r)`.
- **F2, cadence**, for the secondary run only: `surveys / max(1, (last_utc − first_utc)/24 h)`, entered as `log1p`.

## Arms
Each arm fits a model **with and without** the feature on identical folds and entries. The comparison is paired.

| arm | base model | augmented model |
|---|---|---|
| L (primary) | `logistic_rebuilt`: its frozen feature set and fit settings (A1 §3.1) | the same model plus F1 |
| R (primary) | `d4_wind_recal`: one-feature logistic on logit(p) of `d4_wind_rebuilt`, using each fold's held-out-safe refit predictions | logit(p) plus F1 |
| L2 (secondary) | `logistic_rebuilt` | the same model plus F1 and F2 |

**Arm R** is only as available as the `d4_wind_rebuilt` fold predictions. If the refits produce no fold-held-out predictions, arm R is reported as NOT RUN. In that case a recalibration fitted on its own training predictions is **not** substituted.

## Folds and population
- **Folds.** 5 folds grouped by fire over PART_A_ALLOWLIST_FINAL (7db3cc0e…). A fire goes to fold `int(sha256(Incident_C).hexdigest(), 16) mod 5`. It is fixed now.
- **Entries.** The same intervals, cells and band as the part-a training data of the base model (A1 §3.1 rules). The primary population is the 4 km band (A1 §4); the full domain is secondary.
- **Score.** Out-of-fold pooled Brier. ΔBrier is augmented minus base, so a negative value means the leak helps.
- **Interval.** A 95% whole-fire bootstrap of ΔBrier: B = 2,000 fire resamples, seed 20261030 (the A1 seed).

## "Material" (fixed now)
For an arm, the leak is **material** if the 95% interval of the paired ΔBrier lies **entirely below 0** in the 4 km band. This is the same test the §6.1 criteria apply ("the interval lies below 0"), so "material" means: detectable by the protocol's own decision test on part a.

Also reported, without bearing on the label:
- the relative Brier change;
- the per-fire ΔBrier distribution;
- the lowest-bin [0, 0.1) calibration gap with and without the feature;
- the fitted coefficient on F1.

## Consequence (fixed now)
- **Not material in arms L and R:** the limitations paragraph cites the measured bound (the interval and the relative change).
- **Material in either primary arm:** the result is reported in the limitations together with Hannah's audit result.
  - Any A1 design constant whose provenance table entry is not shown to be independent of b/c/d survey timing is flagged.
  - Criteria that depend on a flagged constant become descriptive, per Iris's assessment.
- In either case, part-c results are also reported by tercile of survey span (amendment rule g).

## Outputs
- `derive/LEAK_BOUND.json` and `.md`, with input hashes, code SHA, fold assignment hash and receipts.
- No cell-level data is committed.

## Not decided here
None. Any change to this plan before the run is made by a committed revision of this file, with a reason.
