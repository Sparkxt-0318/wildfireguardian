# RESULTS: lee-slope bypass, tested as frozen (kcf-idea-forecast)

**Verdict: NEW BUT NOT TESTABLE WITH THIS DATA.**

The closed form (embers clear a lee slope when U·tan θ_l / w_t > 1; advance then rises by up to 1 + U·tan θ_l / w_t) was not found in print, though the mechanism is known in words (`IDEA.md` §8). With the frozen parameters it predicts almost nothing different from the baseline on either dataset: no California hour reaches the threshold, and on 25 March 2025 in Gyeongbuk it adds at most 7% to the predicted rate. **It did not explain the Gyeongbuk run: the Korean test failed** (8 of 23 issue hours missed, the same as the baseline).

Protocol: `TEST.md`, committed at 8e83122 before any score. California results committed at e1531d5 before any Korean predictor was built. Stage reached: 5 of 5, on 18 November 2026.

## 1. Power precondition (inputs only)

| parameter set | 5 h issue hours with F ≥ 1.2 | fires | largest F |
|---|---|---|---|
| **primary** (w_t 5 m/s, t_i 300 s, crest wind = ERA5 100 m) | **0 of 20,161** | 0 | 1.08 |
| t_i = 0 | 46 | 2 | 1.43 |
| t_i = 900 s | 0 | 0 | 1.01 |
| w_t = 2.5 m/s | 198 | 9 | 1.42 |
| w_t = 8 m/s | 0 | 0 | 1.01 |
| crest wind = ERA5 gust | 1,355 | 14 | 2.12 |

The rule needed 300 hours from 6 fires under `primary`. It got none. **The California arm is NOT INFORMATIVE.** Reason: ERA5 100 m wind at these fires never exceeds 13.8 m/s, and the mean lee-slope tangent along the wind on the 90 m DEM is 0.04–0.28 across the 28 boxes (median 0.16), which puts the threshold wind U_c = w_t / tan θ_l at 18 m/s or more for a mean slope.

## 2. P1, California: exponent β of reach on F (reported; cannot pass or fail)

0.9-quantile fit q(S) = κ·X1^γ·F^β, 28 fires, fire-level bootstrap 95% intervals (1,000 resamples for `primary`, 300 for the others).

| set | h | β | 95% interval | γ | κ | reading |
|---|---|---|---|---|---|---|
| primary | 5 | 13.5 | −1.7 to 34.2 | 0.57 (0.46–0.78) | 1.43 (1.13–1.61) | F spans 1.00–1.08; β is not identified |
| primary | 8 | 14.0 | −1.5 to 40.7 | 0.72 | 1.09 | same |
| gust | 5 | 0.35 | −1.17 to 2.44 | 0.64 | 1.30 | indeterminate: includes 0 and 1 |
| gust | 8 | −0.23 | −1.66 to 2.10 | 0.85 | 0.90 | indeterminate |
| w_t = 2.5 | 5 | 3.76 | 2.16 to 5.50 | 0.41 | 1.57 | above 0, but also above the predicted 1 |
| w_t = 2.5 | 8 | 4.70 | 2.67 to 6.57 | 0.45 | 1.48 | same |
| t_i = 0 | 5 | 3.0 | −0.9 to 12.4 | 0.58 | 1.40 | indeterminate |

Only `primary` counts. The one set with enough hours to say anything (`gust`, 1,355 hours, 14 fires) is indeterminate. The `w_t = 2.5` exponent of 4–5 is too large to be the predicted effect; with F never above 1.42 it more likely stands in for something else that varies with wind and terrain. I do not read it as support.

A by-product that does not depend on the idea: γ is 0.57 (0.46–0.78) at 5 h, so the upper tail of reach grows less than linearly with the ERA5 wind run on these fires.

**Share of hours where reach exceeded the prediction (fire-weighted, 5 h):** S > X1 in 8.6% of hours with F < 1.2 (28 fires; all hours, under `primary`). Under `gust`: 8.7% for F < 1.2 against 4.9% for F ≥ 1.2 (14 fires). The idea predicted more exceedance of the baseline in high-F hours; the `gust` set shows less.

## 3. P2, California: margins (descriptive)

Leave-one-fire-out, 10% target.

| margin | 5 h miss | 5 h mean margin | 8 h miss | 8 h mean margin |
|---|---|---|---|---|
| constant (kcf-margin) | 6.2% | 3.7 km | 6.6% | 5.0 km |
| κ·max(X1, 1 km) | 6.2% | 3.9 km | 6.1% | 4.8 km |
| κ·max(X2, 1 km), primary | 6.2% | 3.9 km | 6.1% | 4.8 km |

Scaling the margin by wind run, with or without the bypass factor, neither tightens nor loosens it on these fires. The 5 h figure for the constant margin reproduces kcf-margin's 6.2%.

## 4. P3, Gyeongbuk 25 March 2025 (test-only; one fire, one day; no rate claimed)

Nothing fitted. ERA5 maximum over the five county cells; 60 km DEM box.

| | 5 h (23 issue hours) | 8 h (20 issue hours) |
|---|---|---|
| misses of X1 (10% rule) | 8 | 10 |
| misses of X2, **primary** | **8** | 9 |
| misses of X2, t_i = 0 | 7 | 7 |
| misses of X2, t_i = 900 s | 8 | 10 |
| misses of X2, w_t = 2.5 | 7 | 7 |
| misses of X2, w_t = 8 | 8 | 10 |
| misses of X2, gust | 7 | 8 |
| for comparison: constant 3.8 km / 5.0 km (kcf-margin) | 13 | 12 |

**P3 fails:** it needed misses(X2) ≤ 2 and three fewer than the baseline. It got 8 and 8.

Hour by hour, 5 h (km):

| KST | reach | X1 | X2 primary | X2, t_i = 0 |
|---|---|---|---|---|
| 10 | 4.9 | 12.0 | 12.2 | 13.9 |
| 11 | 6.6 | 13.6 | 14.0 | 17.1 |
| 12 | 12.4 | 15.0 | 15.6 | 20.1 |
| 13 | 23.9 | 16.2 | 16.8 | 23.0 |
| 14 | 34.7 | 16.2 | 16.9 | 23.4 |
| 15 | 32.9 | 15.5 | 16.3 | 22.5 |
| 16 | 40.1 | 14.7 | 15.5 | 20.9 |
| 17 | 38.6 | 14.2 | 14.9 | 20.1 |
| 18 | 27.3 | 13.7 | 14.4 | 19.1 |
| 19 | 20.3 | 13.8 | 14.6 | 19.4 |
| 20 | 15.7 | 13.7 | 14.4 | 19.1 |
| 21 | 6.5 | 13.1 | 13.7 | 18.0 |

Hours 00–09 and 22: reach 0–4.9 km, all below X1 (4.5–11.7 km). Full table: `results_kr.json`.

- Largest predicted hourly rate: baseline 3.5 km/h, `primary` 3.6 km/h, t_i = 0 5.4 km/h. The briefing figure is 8.2 km/h (news-sourced). The reach implies about 8 km/h over 16–21 KST.
- Largest hourly F on the day: 1.07 (`primary`), 1.56 (t_i = 0), 1.00 (t_i = 900 s).
- Even the most favourable sensitivity case covers one more hour and reaches 23 km where the fire reached 40 km.

## 5. Why the idea predicted so little (measured; the last item is post hoc)

1. **The slopes are gentler than I assumed.** My worked example in `IDEA.md` §6 used 22° lee slopes (tangent 0.40). On the 90 m DEM the mean lee-slope tangent along a 250° wind in the Gyeongbuk box is 0.17 (median 0.14, 90th percentile 0.35). A mean slope needs a crest wind of 30 m/s to clear at w_t = 5 m/s; only the steepest tenth clears at 14 m/s.
2. **The crest wind proxy is weak.** ERA5 100 m wind peaked at 15.4 m/s on the day. KMA stations recorded gusts of 25 m/s (`kcf-gust`).
3. **The ignition delay eats the gain** (post hoc, `terrain_stats.json`, right panel of the figure). On the Gyeongbuk terrain with t_i = 300 s the factor stays below 1.17 at any wind up to 40 m/s, because real lee slopes are short and each hop costs five minutes. With t_i = 0 it would be 1.5 at 15 m/s and 2.6 at 25 m/s. The idea matters only if a spot line establishes in well under five minutes, which I cannot test here.

## 6. Two things the test did show

- **The 10% rule with ERA5 wind, nothing fitted, misses fewer Gyeongbuk hours than the calibrated constant margin** (8 against 13 of 23 at 5 h), because it rises with the afternoon wind. It still fell short by a factor of up to 2.7 at 16 KST (14.7 km against 40.1 km).
- **It gave warning in the hours where prior spread gave none.** At 10 and 11 KST, when the fire looked quiet, X1 was 12.0 and 13.6 km against a reach of 4.9 and 6.6 km. This is one day and uses the realised wind as a perfect forecast (ASSUMED).

## 7. What would make it testable

- Wind at ridge height from a kilometre-scale model or ridge-top stations, not ERA5.
- A DEM read at 30 m; slopes at 90 m are smoothed.
- Fire arrival times at slope scale (airborne infrared or drone video), to check the direct signature: the next windward slope ignites before the lee slope behind it.
- A measured time from ember landing to a spreading line.

## 8. Limits

- GOFER is 28 large California fires on about 2 km pixels. The Gyeongbuk reach is from detections, one fire, one day.
- ERA5 is used as a perfect forecast (ASSUMED). One weather point per California fire; a 60 km terrain box around it.
- The primary t_i was not chosen blind (`TEST.md`, first section). The bracket 0–900 s is reported throughout and does not change the verdict.
- The flow over the valley is taken as horizontal and uniform. Lee eddies and crest speed-up are ignored.
- `analyze.py` was written after the freeze commit and before any reach was read; it implements `TEST.md` without change.
- PyroSim was not used. The folder is an unpacked Windows installer and does not run on this Mac; its solver, FDS, is open source and was not needed for this test.

## Reproduce

```bash
python3 fetch_era5.py ca data/era5_ca.csv.gz
python3 fetch_dem.py ca TILES DEM_CA
python3 build_predictors.py data/era5_ca.csv.gz DEM_CA data/pred_ca.csv.gz
python3 analyze.py power
python3 analyze.py ca
python3 fetch_era5.py kr data/era5_kr.csv.gz
python3 fetch_dem.py kr TILES DEM_KR
python3 build_predictors.py data/era5_kr.csv.gz DEM_KR data/pred_kr.csv.gz --kr
python3 analyze.py kr
```

Figure: `fig1_bypass_test.png`. Left: Gyeongbuk reach against the frozen predictions. Right (post hoc): the predicted factor on Gyeongbuk terrain against crest wind for three ignition delays.
