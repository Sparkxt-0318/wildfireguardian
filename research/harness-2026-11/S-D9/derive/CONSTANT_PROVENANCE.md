# Numeric constants in A1 and sd9bench: provenance (draft for Hannah's survey-timing audit)

**Purpose (Iris, item 2; adopted by the orchestrator).** List every numeric constant in A1 (revision 30) and `sd9bench`, with the data it was set on. The question for each is whether it could depend on the survey timing of a sealed incident (b, c, d or H-test): `last_utc`, `days`, or cadence derived from them.

**Status.** This is my own reading of the A1 text and the code. It is **not yet verified**. Rows marked ⚠ are ones where I cannot show provenance from the record and ask Hannah to audit. "A priori" means the value was written without reference to any data. The code locations are on Main.

## Scoring (sd9bench and the base conventions)

| constant | value | where | set on | sealed timing? |
|---|---|---|---|---|
| interval rule | 0 < Δ ≤ 48 h, consecutive observation times | A1 §2; base protocol | forecast-v2 base protocol (fit fires), before A1 | no |
| lead and horizon bins | 0/12/24/36/48 h | `score.py` `DEFAULT_HORIZON_EDGES_H`; A1 §5 | follows from the 48 h rule | no |
| distance bands | 0/1/2/4/8 km; cumulative 1/2/4/8 km | `score.py` | a priori, powers of 2 | no |
| primary band | 4 km | A1 §4; `derive/BAND_RULE.json` | rule committed at 3eb31a38, applied on **R** (US2024, exposed) | no |
| low-p bins | 0, 1e-5, 1e-4, 1e-3, 1e-2, 0.1 | `score.py` `LOW_P_EDGES` | a priori, decades | no |
| MC floor | 1/1024 | `score.py` `MC_FLOOR` | c651_mc's 1,024-member Monte Carlo (archive) | no |
| calibration bins | 10 equal-width; lowest [0, 0.1) | base protocol (`wildfire.baselines.BINS`) | base protocol | no |
| NLL floor | `B.LOG_FLOOR` | base protocol | base protocol | no |
| bootstrap | B = 10,000, seed 20261030 | `score.py` `DRAWS`, `SEED`; `ensemble.py` `RANK_SEED` | a priori (date seed) | no |
| tested-cell minimum | ≥ 10 positives per fire × horizon | A1 §6.2 | a priori | no |
| arrival RPS bins | the observation times within 48 h of the cutoff | A1 §5.2; `arrival.py` | defined by each fire's own survey times **at scoring**; no constant | see note 1 |
| RPS propriety test | seed 20261112; 200k cells; ±12 h shifts; SE multiplier 3; patterns | `derive/rps_propriety.py` | synthetic, plus survey gaps of 3 **part-a** pilot fires (Line, ThreeNine, Blue2) | no |

## Cohort and decision rules

| constant | value | where | set on | sealed timing? |
|---|---|---|---|---|
| eligibility | `surveys >= 20` | A1 §1.2 item 2; `select_cohort.py` | a priori. It uses the declared **count** field, not timing. | no (count only) ⚠ — see note 2 |
| part sizes | 30 / 30; d floor 30 | A1 §1.2 items 4, 5, 12 | power calculation on **R** (`derive/POWER.json`) | no |
| analysable minimum | ≥ 20 fires | A1 §6.1 item 6 | power calculation on R | no |
| order | u = sha256 hash | A1 §1.2 item 3 | a priori | no |
| independence | 50 km and 30 days | A1 §1.3, item 9 | a priori (base protocol convention) | the **rule uses** discovery date for b/c/d; the constant itself does not depend on it. See note 3 |
| duplicates | 5 km plus survey-window overlap | A1 §1.2 item 10 | a priori | the **rule uses** first_utc/last_utc of all parts (membership only); the constant itself does not depend on them. See note 3 |
| CRC α | 0.2 and 0.3; feasibility 0.067 and 0.183 | A1 §6.2; `derive/CRC_DEV.json` | **R** (n = 6) | no |
| superiority tests | each interval < 0 | A1 §6.1 | a priori | no |

## Strata and candidates

| constant | value | where | set on | sealed timing? |
|---|---|---|---|---|
| GOFER/FEDS sampling cadence | 12 h from each fire's first observation | A1 §2 | "to keep cadence comparable to NIROPS". **Q5 is still open.** | ⚠ **audit**: did any NIROPS cadence figure behind "12 h" come from b/c/d timing? Under the new rule (c), anything not yet frozen is set from part a only |
| H leads | 1, 2, 3, 6, 12 h | A1 §2.1 | a priori | no |
| H reach | r = d_cheb / (4 × lead) | A1 §2.1 | the kernel geometry (4 cells/h) | no |
| H tolerance | 4 × lead + 6 | A1 §2.1 | Marcus's label inspection of **all 28 GOFER fires** (disclosed; H descriptive) | GOFER labels, not NIROPS timing |
| refit recipe | epochs 3, lr 0.003, hidden 16, kernel 9, etc. | A1 §3.1 | forecast-v2 RUN_PROTOCOL (fit fires) | no |
| rate-mixture multipliers | 1, 2, 4, 8, 16 | A1 §3.1 | a priori, powers of 2 | no; weights fit on training data |
| d2_bracket | sweeps 2, step 0.25 h | stage-2 queue | synthetic timing and step check | no |
| far-offset set | Chebyshev distance ≥ 2 | stage-2 queue | a priori, on the 9 × 9 stencil | no |
| Elena's part-a fits | ≥ 20 surveys, first 240 h | A1 §3.1 (evidence) | **part a** | no |
| c651 configuration | candidate `mixed_3_5_7_9_02_lr0.1_warmup_cosine` | A1 §3.2 | archive benchmark | no |
| leak-bound plan | 5 folds, B = 2,000, "material" = interval < 0 | `derive/LEAK_BOUND_PLAN.md` | a priori, part a only | no |
| WSTS tolerance | 0.005 / 0.020 | `external/WSTS_DESIGN.md` §6 | the published AP 0.105 | no |

## Notes

1. **Arrival RPS bins** are each scored fire's own observation times, after the cutoff and within 48 h. Using a part-c fire's survey times at scoring is how the labels are defined. It is not a design choice made from leaked data. No constant here was set from sealed timing.
2. **`surveys >= 20`.** `surveys` is a declared field and a count. Combined with `last_utc − first_utc`, it would give cadence. The threshold was written in A1 revision 3 before the split was generated. I know of no analysis of the survey-span distribution behind it. Hannah: please confirm no one computed b/c/d span or cadence before revision 3.
3. **Membership filters.** §1.3 and items 9 and 10 **by design** read discovery date (b/c/d) and first_utc/last_utc (all parts). They decided **membership only**: exclusions, drops and duplicates (logged in `cohort/COHORT_FINAL.csv`). They set no constant and tuned no model. The amendment reconciles this with §1.2's statement that the split uses five fields: the **ordering and part assignment** (items 1–4) use those five fields; the **filters** (items 9–11, §1.3) use point of origin, discovery date and survey window, as items 9–11 themselves say. `cohort/GOFER_MATCH.csv` commits discovery_utc for 10 b/c/d incidents. It is a disclosed file.
