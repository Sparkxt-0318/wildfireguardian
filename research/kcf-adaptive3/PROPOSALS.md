# PROPOSALS: the bounded agent loop (PROTOCOL section 4)

Scored on the 16 CA-DEV fires only, 4-fold by-fire cross-validation. **M1** = flagged area read at exactly 10% cross-validated miss (km2, lower is better). **M2** = run fire-days warned at their first run hour, of 72, with the threshold set so that at most 10% of fire-days without a run alarm (higher is better). Kept if M1 falls by at least 1% and M2 does not fall, or M2 rises and M1 does not rise by more than 1%; each proposal is the kept version plus one change. The proposals were written by the agent from CA-DEV diagnostics. 20 of 20 used.

Reference points on the same folds: FIXED M1 356.2; QUANTILE M1 329.3; version 0 with the update off 320.2 (M2 21 of 72); version 0 with the forecast off 351.5 (M2 15 of 72). (The two ablations were scored for version 0 only, before the loop.)

| # | Change | Reason | M1 (km2) | M2 (of 72) | Kept | Rule |
|---|---|---|---|---|---|---|
| 0 | `version 0` | version 0 (PROTOCOL section 2) | 342.7 | 19 | **kept** | version 0 |
| 1 | `{"temper": 0.5}` | Dev diagnostic: p is over-confident (bin p=0.92 has 36% run hours) because hourly growth observations are autocorrelated but multiplied as independent. Temper the emission likelihood with exponent 0.5. | 333.4 | 21 | **kept** | M1 down >= 1%, M2 not down |
| 2 | `{"temper": 0.25}` | Same reason, stronger tempering (exponent 0.25). | 325.4 | 27 | **kept** | M1 down >= 1%, M2 not down |
| 3 | `{"mix": "quantile"}` | Mix the two state margins as the exact tau-quantile of the two-state mixture instead of a linear blend; a linear blend over-issues when p is small. | 345.0 | 27 | no | neither |
| 4 | `{"temper": 0.12}` | Tempering helped twice; try exponent 0.12 to see whether the trend continues toward no update. | 321.2 | 26 | no | neither |
| 5 | `{"obs": "g3"}` | Use the 3 h growth g3 as the observation (dev AUC for the run label 0.863 against 0.834 for g1), same bins. | 328.1 | 27 | no | neither |
| 6 | `{"trans": ["gust_ms", "w850_ms", "rhmin_pct", "sin_h", "cos_h", "arch", "g3", "g6"]}` | Let the transition see the recent trend: add g3 and g6 to the enter/stay inputs, so the forecast and the last hours' growth act together. | 328.9 | 26 | no | neither |
| 7 | `{"mix": "max"}` | Mixing rule max(m0, p*m1): the run margin only takes over when the run probability is material; avoids adding a small share of a large margin to every quiet hour. | 325.4 | 27 | no | neither |
| 8 | `{"mix": "geometric"}` | Geometric mixing (blend in log distance), since reach is roughly log-scaled. | 325.4 | 27 | no | neither |
| 9 | `{"depth": 3, "iters": 300}` | More capacity in the state margins: depth 3, 300 iterations (the QUANTILE grid's largest setting). | 326.2 | 27 | no | neither |
| 10 | `{"trans": ["gust_ms", "w850_ms", "rhmin_pct", "sin_h", "cos_h", "arch", "hdw"]}` | Add the Hot-Dry-Windy value (hdw) to the transition inputs; dev AUC 0.72 for the run label. | 325.7 | 27 | no | neither |
| 11 | `{"trans_model": "gbm"}` | Non-linear transition: boosted-tree classifiers (depth 2) for enter and stay, so wind, humidity and hour can interact. | 331.9 | 20 | no | neither |
| 12 | `{"mfeat": ["g1", "g3", "g6", "g12", "g24", "log_area", "log_age", "sin_h", "cos_h"]}` | Division of labour: state margins on own-past features only, so the forecast acts through the state probability alone. | 328.5 | 27 | no | neither |
| 13 | `{"tau": 0.95}` | State margins at tau 0.95 (kappa rescales); the run state's upper tail may be better ordered at a higher quantile. | 326.8 | 27 | no | neither |
| 14 | `{"tau": 0.8}` | State margins at tau 0.8. | 336.8 | 27 | no | neither |
| 15 | `{"leaf1": 25}` | Smaller leaves for the run-state margin (25) to use the few run hours (about 460 on dev) better. | 327.2 | 27 | no | neither |
| 16 | `{"trans": ["gust_ms", "w850_ms", "rhmin_pct", "sin_h", "cos_h", "arch", "d6_gust_ms", "d6_w850_ms"]}` | Forecast ramp: add the 6 h change of forecast gust and 850 hPa wind to the transition, so a rising forecast can move the state before the level is high. | 328.4 | 24 | no | neither |
| 17 | `{"bins": [0.0, 1.5]}` | Coarser observation table (no growth; up to 1.5 km; above), fewer cells to estimate for the run state. | 324.5 | 28 | **kept** | M2 up, M1 not up > 1% |
| 18 | `{"temper": 0.35}` | Tempering exponent 0.35, between the two kept steps, in case 0.25 overshot for M2. | 328.9 | 28 | no | neither |
| 19 | `{"C": 0.1}` | Stronger regularisation of the transition regressions (C = 0.1); 81 dev onsets is little data for six inputs. | 324.0 | 30 | **kept** | M2 up, M1 not up > 1% |
| 20 | `{"C": 10.0}` | Weaker regularisation (C = 10) as the opposite check. | 324.6 | 28 | no | neither |

**Kept version** (proposal 19): version 0 plus {"temper": 0.5}, {"temper": 0.25}, {"bins": [0.0, 1.5]}, {"C": 0.1}. M1 324.0 km2, M2 30 of 72.

Read with care: 20 tries on 16 fires. The kept changes each moved M1 by 0.2% to 3% and M2 by 1 to 6 days of 72; the last two were kept on M2 gains of one and two run-days, which is within noise. No proposal failed to run.
