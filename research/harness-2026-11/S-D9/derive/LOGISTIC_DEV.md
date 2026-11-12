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
2. **The miscalibration is at the low end.** In the band, d4 gives p ≈ 1e-6 to 345,167 entries whose observed frequency is 0.38%, and they contain 1,310 positives. Its whole [0, 0.1) bin predicts 0.0022 against 0.0133 observed. Logistic's floor is about 1e-3, which is where it gains. This is the preprint's zero- and near-zero-probability-positives problem, seen on 6 fires.
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
