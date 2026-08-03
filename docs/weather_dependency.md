# How much of this model's skill comes from instantaneous weather?

PHASE 14, 2026-08-03. `scripts/measure_weather_dependency.py` →
[`weather_dependency.json`](../data/processed/weather_dependency.json).

**This measurement ended PHASE 14 before any forecast data was acquired.** The
question was whether ERA5 (~5-day publication lag) could be replaced by forecast
data and what that would cost in accuracy. Rather than acquire GFS and find out,
we first measured the **ceiling** on that cost: if the swappable weather features
carried *no* information at all, how far would the leave-one-fire-out AUC fall? A
real forecast still carries some information about those quantities, so its
degradation cannot exceed the ceiling.

---

## 1. What the model is made of

The sixteen features do not divide the way the phrase "a weather-driven spread
model" suggests. Grouped by what they measure, with the committed leave-one-out
permutation importance from [`spread_v2_lofo.json`](../data/processed/spread_v2_lofo.json):

| group | n | Σ importance | features |
|---|---:|---:|---|
| **fire geometry / state** | **5** | **+0.09965** | `dist_to_fire_m` +0.06005, `active_frac_1500m` +0.01742, `active_frac_3000m` +0.01258, `dt_hours` +0.00908, `n_active_adjacent` +0.00052 |
| **weather — antecedent dryness** | **1** | **+0.07726** | `days_since_rain` |
| **weather — instantaneous** | **6** | **+0.02684** | `wind_speed_ms` +0.02090, `wind_alignment` +0.00233, `temp_c` +0.00206, `vpd_kpa` +0.00097, `rh_pct` +0.00031, `precip_24h_mm` +0.00026 |
| **static terrain + fuel** | **4** | **+0.00735** | `burnable_frac` +0.00371, `elev_above_source_m` +0.00253, `elevation_m` +0.00199, `slope_deg` −0.00088 |

⚠ **Seven of sixteen are weather-derived, not three.** `wind_alignment` is
included above as instantaneous weather because it is computed from the wind
vector, even though it also carries geometry.

The six **instantaneous** weather features are the ones a forecast source would
replace. `days_since_rain` is not among them: a forecast carries no precipitation
history before its initialisation time, so that feature would have to stay on
reanalysis regardless. That split is what the experiment measures.

## 2. The measurement

Six arms, leave-one-fire-out over the same six fires, same seed (`20250603`),
same dataset. The dataset reproduces the committed `(151904, 2989)` exactly — the
script builds it with the identical call `scripts/build_canonical_hazard.py:117-118`
makes.

| arm | features | mean-of-folds | Δ | **far band** | **Δ** | pooled | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| **A0** all sixteen | 16 | 0.8943 | — | 0.8408 | — | 0.9036 | — |
| **A1** drop the 6 instantaneous | 10 | 0.8622 | −0.0321 | **0.7281** | **−0.1127** | 0.8953 | −0.0084 |
| **A2** shuffle the 6 instantaneous | 16 | 0.8739 | −0.0204 | **0.8065** | **−0.0344** | 0.8981 | −0.0055 |
| **A3** drop all 7 weather | 9 | 0.9027 | **+0.0084** | **0.6124** | **−0.2285** | 0.8721 | −0.0316 |
| **A4** drop `days_since_rain` only | 15 | **0.9213** | **+0.0270** | **0.8941** | **+0.0533** | 0.8894 | −0.0143 |
| **A5** drop `wind_speed_ms` only | 15 | 0.9017 | +0.0074 | 0.8049 | −0.0359 | 0.9008 | −0.0029 |

**A1 is the ceiling** (the feature is gone). **A2 is the like-for-like ceiling**
(the column is still there, its association destroyed) and is the number to quote
when the question is "what if this source told us nothing useful".

## 3. What it says

**① The ceiling is NOT noise, and where you look decides what you see.**

* On **pooled** AUC the effect is small: **−0.0055** shuffled, −0.0084 dropped.
  Pooled AUC has no resolving power for this question.
* On the **far band** it is large: **−0.0344** shuffled, **−0.1127** dropped.
  This is the band where a spread model is actually being asked something hard,
  and it is where the instantaneous weather earns its place.
* Removing weather *entirely* collapses the far band to **0.6124** (−0.2285),
  which is the strongest statement in the table: **without weather this model
  cannot do far-field prediction at all.**

So a forecast-source swap **is** measurable — in the far band, with roughly
0.034–0.113 of headroom. Reporting it on pooled AUC would have shown nothing and
that would have been an instrument failure, not a finding.

**② The most important feature by permutation importance makes the model
WORSE out-of-fold.**

Dropping `days_since_rain` — ranked **first** at +0.07726 — *raises* mean-of-folds
AUC by **+0.0270** and far-band AUC by **+0.0533**, while lowering pooled by
−0.0143. Per fold:

| fire | A0 | A4 (dropped) | Δ |
|---|---:|---:|---:|
| **gangneung_2023** | 0.7184 | **0.8889** | **+0.1705** |
| uljin_samcheok_2022 | 0.9159 | 0.9308 | +0.0149 |
| miryang_2022 | 0.9768 | 0.9834 | +0.0066 |
| hongseong_2023 | 0.9393 | 0.9454 | +0.0061 |
| yeongdeok_2025 | 0.9403 | 0.9307 | −0.0096 |
| uiseong_andong_2025 | 0.8751 | 0.8484 | −0.0267 |

That is the signature of a feature that helps *within* a fire and hurts *across*
fires. The mechanism is visible in the data: `days_since_rain` counts from the
last sampled 3-hourly step exceeding 1 mm, and where no such step exists it
counts from the **start of the ERA5 window**. For three of the six fires it
equals the window length exactly — gangneung_2023 **2.88 d**, uiseong_andong and
yeongdeok **6.88 d** each — because those windows contain **zero** wet samples.
Uljin-Samcheok has 3 wet steps out of 88.

So for half the training set the top-ranked feature is a **per-fire constant
equal to an acquisition parameter**. Inside a fold it separates nothing; across
folds it is a fire fingerprint, which raises pooled AUC and damages transfer.
Pooled up, mean-of-folds and far band down, is what leakage looks like.

**③ Every weather ablation moves mean-of-folds and the far band in opposite
directions.** A3 +0.0084 / −0.2285. A5 +0.0074 / −0.0359. A4 +0.0270 / +0.0533
is the sole exception, and it is the feature identified in ② as an artifact.
"Is weather important to this model?" has opposite answers on the two metrics,
and both answers are real.

## 4. ⚠ What this does NOT say

**It does not say weather is unimportant to wildfire spread.** It is a statement
about *this model's measured dependence on these features on this dataset*, and
three limits bound it:

1. **`days_since_rain` was not shuffled in A1/A2, and it is weather-derived.**
   The contribution of antecedent dryness is not measured by the ceiling arms —
   it was held out because a forecast source cannot supply it. A3 and A4 probe
   it separately, and ② argues that what it actually carries here is partly an
   acquisition artifact rather than a dryness signal. **The physical importance
   of dryness is not measured by this experiment either way.**
2. **ERA5's grid cannot resolve local terrain-driven wind.** The domain mean is
   taken over **2 to 9 cells** — gangneung_2023 is a degenerate 1×2 = **two
   cells** — spanning at most ~50 km, on a product whose effective resolution is
   ~31 km. Whether `wind_alignment`'s small contribution (+0.00233) means wind
   *direction* is physically unimportant, or means **this data source cannot see
   the wind that matters**, is not separable here. The Korean spring fires are
   driven by 양강지풍 downslope wind, which is precisely a sub-grid phenomenon.
3. **The configuration bounds the claim.** Six Korean fires, a 12-hour forward
   horizon, a 500 m analysis grid, 3-hourly ERA5 sampling, one model family and
   one seed. Nothing here transfers to a different horizon, a finer grid, a
   different fuel regime, or more fires without being re-measured.

⚠ **And a fourth limit, on the precipitation features specifically.** The ERA5
request samples **8 of 24 hours** per day and `tp` is a *one-hour* accumulation,
so `precip_24h_mm` sums nine one-hour accumulations and calls the result a
24-hour total — at most **0.375×** the true figure, and phase-dependent. A 12-hour
0.5 mm/h event (6 mm total) never trips the 1 mm threshold in any phase. Both
precipitation features are miscalibrated against their own docstrings, and that
is independent of any forecast migration.

## 5. What it means for a real-time claim

**Say this, and not more:**

> 순간 기상 자료원을 예보 자료로 교체했을 때의 성능 저하 상한은 측정되었습니다 —
> 폴드 평균 AUC에서 **−0.020**, 원거리대에서 **−0.0344** (특징을 완전히 셔플한
> 경우). 실제 예보는 그 양들에 대해 일부 정보를 보유하므로 실제 저하는 이보다
> 작습니다. **다만 전환은 실측되지 않았습니다** — GFS 자료는 취득하지 않았고,
> 저하의 실제 크기는 알려져 있지 않습니다.
>
> 그리고 `days_since_rain`은 예보 자료로 재구성할 수 없습니다. 예보는 초기화
> 이전의 강수 이력을 갖고 있지 않으므로, 이 특징을 유지하는 한 재분석
> 아카이브 접근이 계속 필요하며 **완전한 실시간 운영이 아닙니다.**

⚠ **Never write "we switched to forecast data" or "the switch costs nothing."**
Neither was done and neither is known. What was established is a bound on the
cost, and the bound is not zero.

## 6. Why PHASE 14 stopped here

Acquisition was stopped by the user on 2026-08-03 after this measurement, before
any GFS data was retrieved. The retrospective archive question had already been
settled in the affirmative — AWS `noaa-gfs-bdp-pds` carries GFS 0.25 ° with full
forecasts from 2021-01-02, covering all six fires, at a measured publication lag
of **+3 h 34 m to +3 h 51 m** (against ERA5's ~5 days). So the experiment was
runnable; it was not run.

**The resume condition, and what changed:** finding ② has to be resolved first.
If `days_since_rain` is largely an acquisition artifact, then the "keep it on
ERA5" design that PHASE 14 had agreed on preserves the artifact while paying the
mixed-source cost — and the A4 configuration (drop it) is both cleaner and
better-performing. Any resumed experiment should settle that before choosing the
feature set, and should pre-declare the **far band** as the primary metric, since
pooled AUC was shown here to have no resolving power for this contrast.

`docs/HANDOFF_ROUND3.md` §14 carries the phase record.

## 7. Reproducing, and one caveat about the harness

```bash
python scripts/measure_weather_dependency.py
```

~3.5 minutes; writes `data/processed/weather_dependency.json` only.

⚠ **The arm-to-arm deltas are the result; the absolute AUCs are not directly
comparable to `spread_v2_lofo.json`.** This script runs its own leave-one-out
loop so it can vary the feature set, and it does not compute permutation
importance inside the fold loop as `model.leave_one_fire_out` does. Five of six
folds reproduce the committed per-fire AUC to within ±0.006; **`gangneung_2023`
differs by +0.0364** (0.6820 → 0.7184), which accounts for essentially the whole
mean-of-folds difference (0.8895 committed → 0.8943 here). That fold is the
smallest and noisiest in the set — 17 detections, 2 overpass clusters, a 1×2
two-cell ERA5 domain — and the likely mechanism is the random validation split
inside `HistGradientBoostingClassifier(early_stopping=True,
validation_fraction=0.15)` seeing a different RNG state. **Every arm ran through
the identical harness, so the Δ columns are valid.** Do not quote an absolute
figure from this table beside a committed one.
