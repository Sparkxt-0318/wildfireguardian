# S-D9 fire-exposure ledger

This ledger records every fire and interval in this repository that any forecast lineage has fit on, selected on, scored or inspected. It is committed **before** any new S-D9 score, pre-registration or harness. A later S-D9 claim that a fire is "untouched" is only valid if the fire is absent from this ledger, or appears here as UNTOUCHED.

## How to reproduce

The builder needs a full, non-shallow clone and refuses to run on a shallow one: the evidence commits are found from file-addition history, and a shallow clone would report its boundary commit instead of the real one.

```sh
git fetch --unshallow origin Main   # only if the clone is shallow
python3 research/harness-2026-11/S-D9/ledger/build_ledger.py
sha256sum research/harness-2026-11/S-D9/ledger/*.csv   # must match LEDGER_SUMMARY.json
```

The builder reads only committed evidence, takes under 1 s, and writes three files:
- `EXPOSURE_LEDGER.csv`: one row per fire. Each exposure carries `lineage:CLASS: what [evidence path @ first-adding commit]`.
- `INTERVAL_LEDGER.csv`: every interval that can be enumerated from committed evidence. That is 273 US2024 forecast-v2, 33 KR2025 forecast-v2, 28 M548 observed (25 complete, 2 failed, 1 running) and 30 stored FARSITE intervals.
- `LEDGER_SUMMARY.json`: counts, the SHA-256 of both CSVs, and the evidence-to-commit map.

## Classes

The classes, in order of exposure:
- **FIT**: outcomes fit parameters.
- **SELECTED_ON**: outcomes chose a model, variant or hyperparameter, or were inspected before such a choice.
- **SCORED**: outcomes were scored and reported.
- **INSPECTED**: outputs or perimeters were viewed or used, without a score.
- **UNTOUCHED**: none of the above.

A fire's overall class is its most exposed class across all lineages. The lineages are:
- `c651`: the M548/c651 integration checkpoint.
- `cellhour_benchmark_20261010`: the mixed 3/5/7/9 checkpoint, split by cell-hour.
- `forecast_v2`: the seven final variants, the logistic baseline and dilation.
- `farsite_scenarios`
- `routing_panels`
- `d4_experimental`
- `november_readiness`

## Result: no untouched fire remains in this repository

Measured with the builder at the branch head:

| overall class | fires |
|---|---|
| FIT | 34: all 23 US 2020–22 fires and all 11 Korean 2022–23 fires |
| SELECTED_ON | 1: Wapiti, inspected before c651 selection (SPLIT.json `c651_training_overlap`) |
| SCORED | 11: the 5 other US2024 fires, the 4 KR2025 fires, and HUNT and LEVELOCK 2019 |
| INSPECTED | 3: Caldor 2021 and Rim 2013 (routing perimeters; no c651 forecast run), and the GOFER archive |
| UNTOUCHED | **0** |

Every one of the 44 catalog events has been fit or scored by at least one lineage. The US2024 and KR2025 held-out sets were scored with predictions committed (commits `e9259dac`, `6a3265a0`, 2026-10-30/31), and US2024 was also scored by M548 and by stored FARSITE scenarios. They can serve as **frozen descriptive references** for regression testing the harness, not as an untouched test for any new selection.

## Accounting for the 324 planned intervals

The six US2024 fires have 330 surveys and 324 consecutive intervals; this is the M548 plan (`forecast/documents/observed_combined_evaluation.md`).
- **273** intervals of 48 h or less were scored by forecast-v2 for 16 predictors, with predictions in git.
- **51** were not scored by forecast-v2 because they are longer than 48 h, a timestamp-only rule frozen before scoring. Some of them were scored by M548 or FARSITE: M548 completed one Wapiti interval of 74.8 h, and FARSITE has one case over 48 h, retained as unavailable. Their survey timestamps are **not** in git; they live in the NIROPS archive. Only 32 of the 51 can be derived as gaps between consecutive eligible intervals, so they are counted but not individually enumerated.
- Of the 28 M548 cases, 27 coincide exactly with forecast-v2 eligible intervals.

## Limits of this ledger (not verified)

- **Prose-only exposures.** HUNT, LEVELOCK and GOFER appear only in `research/november-20261111/README.md`, whose numerical artifacts are held locally. Their fire identity, country, interval set and exactly what was scored are unknown here. GOFER's 28 member fires are not listed in git, so their overlap with the FIT set is unresolved. Dixie, August Complex, Creek, Monument and others are plausible overlaps (hypothesis).
- **c651 selection.** SPLIT.json says c651's selection "followed inspection of Wapiti and other test events". Only Wapiti is named, so only Wapiti is marked SELECTED_ON; the other US2024 fires may deserve the same class.
- **Local-only work.** Any exposure that happened only on owner or agent machines without committed evidence cannot be detected. The ledger is a lower bound on exposure.
- **Archive-level exposure.** It is not recorded. The NIROPS archive was extracted, and the 29-fire US selection table `us_selection_29.csv` was built from it. Fires in the archive but not selected were seen at metadata level only, and no outcome inspection is evidenced.

## Where untouched fires can come from (proposals; requests out to Daniel and Sofia)

1. **NIROPS 2020–2024 fires not among the 29 selected US events.** They are in the same archive (DOI 10.17632/95rj5d379g.1) and use the same label definition as the US2024 reference, which avoids Iris's label-heterogeneity concern. How many exist, and whether they pass the alignment rules, is unknown and needs the archive's member list. Their covariates must be rebuilt from public sources.
2. **The 2026 prospective NIROPS cohort** under the existing frozen protocol (`forecast/documents/preregistration_blind_test.md`). It is cleanly blind, but blocked on publisher release and owner registration.
3. **Korean events absent from the catalog.** SPLIT.json pins a 21-row `kr_events_21.csv`, while the catalog has 15 Korean events, so up to 6 Korean events with the same kriged label may exist. Korean events from 2026 onward are another source.
4. **GOFER (hourly) and FEDS (12-hourly).** These have a different label definition and latency, so they must be scored as a **separate stratum**, never pooled with NIROPS. GOFER needs overlap exclusion against the FIT set.

At this point the honest statement is that **untouched data in this repository is zero fires**. Any confirmatory S-D9 result depends on new data from items 1–4 above.
