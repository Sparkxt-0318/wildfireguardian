# Why the frozen logistic beats d4_wind (DEVELOPMENT-ONLY, cohort R)

**Scope:** US2024 (R, already exposed). The 4 km band holds 596,719 entries. Leave-one-fire-out (LOFO) fits on R. This is not a confirmatory result and not an untouched cohort. Reproduce with `derive_dist.py` → `logistic_dev.py` (about 10 s); full numbers are in `LOGISTIC_DEV.json`.

| predictor (4 km band) | pooled Brier | minus logistic [whole-fire 95%] | fires better than logistic | AP |
|---|---|---|---|---|
| frozen logistic | 0.013312 | reference | — | 0.0443 |
| d4_wind_seed0 | 0.013507 | +0.000194 [+0.000012, +0.000327] | 2 of 6 | **0.0561** |
| persistence | 0.013707 | +0.000394 [+0.000087, +0.000667] | 2 of 6 | 0.0137 |
| LOFO distance+hours logistic (3 features) | 0.013436 | +0.000124 [−0.000074, +0.000353] | 4 of 6 | 0.0386 |
| **LOFO recalibrated d4** (logit p_d4 only) | **0.013283** | **−0.000029** [−0.000129, +0.000117] | 5 of 6 | 0.0502 |
| LOFO hybrid (logit p_d4 + distance + hours) | 0.013452 | +0.000140 [−0.000072, +0.000521] | 3 of 6 | 0.0489 |

## Reading

1. **d4_wind is not missing information. It is miscalibrated.** d4 ranks better than logistic (AP 0.056 against 0.044). A one-feature recalibration of d4's own output, which adds no information, removes the whole Brier deficit (−0.000029, interval spans 0).
2. **The miscalibration is at the low end.** In the band, d4 gives p ≈ 1e-6 to 345,167 entries whose observed frequency is 0.38%, and they contain 1,310 positives. Its whole [0, 0.1) bin predicts 0.0022 against 0.0133 observed. Logistic never goes below 1e-4 in the band (1,877 entries in [1e-4, 1e-3), everything else ≥ 1e-3), which is where it gains. This is the preprint's zero- and near-zero-probability-positives problem, seen on 6 fires.
3. **The frozen logistic's edge is mostly distance to the front plus horizon.** Its largest standardized coefficient is log1p(distance), at −1.57. A three-feature LOFO distance+hours logistic gets within +0.000124 of it. Wind, slope and biome add at most the remainder; that is unverified, because those covariates are not in git.
4. **The hybrid does not beat recalibration alone** across fires. Adding distance features to d4's logit costs more out of fold than it gains. Under LOFO with 6 fires, the extra degrees of freedom do not transfer.

## Implications for D1 (Marcus) and D2 (Elena) — hypotheses

- The bar that matters is logistic. The quickest way past it is to **fix the low-probability tail**, so that cells with no near-term spread path in the model still get a calibrated small probability. The kernel's ranking information is already better than logistic's.
- A refit that improves ranking but leaves the tail near zero will probably still lose on Brier. Report the low-probability bins (sd9bench `low_probability_bins`) and `positives_below_1_over_1024` for every candidate.
- A post-hoc recalibration layer fit on part a only is a legitimate, cheap candidate component. If it is used, it must be frozen with the candidate's SHA.

## Not verified

- These are LOFO fits on 6 exposed fires; the transfer to untouched fires is unknown.
- The frozen logistic was fit on the 23 fit fires, but the LOFO models are fit on R, so their training data differ.
- An ablation of the frozen logistic's wind, slope and biome terms needs per-cell covariates. Requested from Daniel (rebuilt), or the owner archive.

## Follow-up: are the tail misses beyond d4's structural reach? (`reach.py` → `REACH.json`, about 1 s)

d4's kernel is 9×9 (forecast-v2 RUN_PROTOCOL `kernel_size` 9), so its reach is at most 4 cells per hourly step: 1,500 m/h along an axis and 2,121 m/h diagonally. The reach ratio is r = dist_m / (1,500 m/h × hours). The tail is the entries with d4 p < 1e-5.

| r (axis) | tail entries (4 km band) | positives | burn rate | d4 mean p | recalibrated d4 mean p |
|---|---|---|---|---|---|
| [0, 0.05) | 71,156 | 281 | 0.0039 | 1.9e-6 | 0.0016 |
| [0.05, 0.1) | 215,830 | 677 | 0.0031 | 4.3e-7 | 0.0014 |
| [0.1, 0.25) | 57,196 | 345 | 0.0060 | 5.5e-8 | 0.0013 |
| [0.25, 0.5) | 702 | 7 | 0.0100 | 2.3e-7 | 0.0012 |
| [0.5, 1) | 283 | 0 | 0 | 3.8e-10 | 0.0011 |
| ≥ 1 (beyond reach) | **0** | **0** | — | — | — |

- **None of the 1,310 band tail positives is beyond reach.** 958 of them (73%) lie within 10% of the reach distance for their interval. The largest r anywhere in the 4 km band is 0.61. In the full domain, the 1,651 tail positives are also all within reach (r < 0.5).
- **Reading (hypothesis):** on this cohort, the hourly reach cap does **not** explain the tail. The cells are reachable many times over, yet d4 assigns them about 1e-6 to 1e-8. The cause is spread magnitude: rates too low, or probability decaying too fast with distance. That is consistent with Elena's plug-in bias (her synthetic fitted rate is about half of truth). Prediction: a D2 refit should shrink the tail without a recalibration layer. D1's continuous-time step is not the limiting factor here, unless it also changes rate magnitude.
- **The recalibrated d4 is still about 2–4× too low in the tail** (about 0.0013–0.0016 against 0.003–0.006 observed), so recalibration only partly fixes it.
- **Integration caution (Iris).** Recalibrated marginals must not feed the per-cell independent member draws used for routing. Lifting the floor everywhere would scatter isolated ignitions.

## Follow-up 2: structural zeros? Enclosure of tail positives (`enclosure.py` → `ENCLOSURE.json`, about 5 s)

Iris's competing explanation: the tail may come from structural zeros rather than slow rates, either input gating (non-burnable or missing covariates) or label filling (unburned islands inside a NIROPS polygon). The endpoint union is the cutoff union ∪ the interval's positives. A positive is "enclosed" if at least 6 of its 8 neighbours are in the endpoint union, and an "island" if all 8 are.

| 4 km band, R | positives | enclosed (≥ 6/8) | island (8/8) |
|---|---|---|---|
| d4 tail (p < 1e-5) | 1,310 | 872 (**66.6%**) | 590 (**45.0%**) |
| d4 non-tail | 6,869 | 3,443 (50.1%) | 1,889 (27.5%) |

**Reading (hypothesis).**
- Enclosed and island cells are clearly **over-represented** in the tail: 1.33× the enclosed share and 1.64× the island share.
- 590 tail positives sit with every neighbour burned at the endpoint, yet d4 gives them about 1e-6. A merely slow kernel would not do that next to a fully burning neighbourhood. That points to **gating** (a covariate switching the cell off) or **label filling** (an unburnable cell counted as burned inside the mapped polygon).
- A third of the tail positives (438) are not enclosed, so structural zeros are at most part of the story.
- The gating and labelling explanations cannot be separated without per-cell fuel, land-cover and covariate-missing flags. Those are requested from Daniel (rebuilt covariates for the 6 US2024 fires).

**Consequence for A1, if gating or label filling is confirmed.** An enclosed-cell scoring rule changes the scoring population, so it would have to be pre-declared before the freeze. Example: report the band score with and without enclosed non-burnable cells. Nothing is changed yet.

**Island neighbour check (Iris; added to `enclosure.py`).** This looks at the 590 tail island positives, cells with all 8 neighbours burned at the endpoint and d4 p < 1e-5:
- **None** (0 of 590) has any neighbour inside the **cutoff** union. They are not next to the burning edge.
- Their scored neighbours are also near zero: the median neighbour p across islands is 4.8e-8 (IQR 2.2e-10 to 9.8e-7), and the median of the neighbourhood maximum is 1.2e-6. **No island has a neighbour with p ≥ 0.1.** The centre's median p is 4.4e-8.

**Reading (hypothesis).** These are interiors of **whole newly burned patches** that d4 rates near zero throughout. That is not a per-cell gate, which would show a near-zero centre among high-probability neighbours. It points back to **spread rates too low, or spotting or long runs** into patches some distance from the front, all still within reach (r < 0.25). Gating is not supported by this test. The fuel/land-cover split (Iris's part a) is still to be done for completeness. Label filling can still contribute to individual cells inside these patches.
