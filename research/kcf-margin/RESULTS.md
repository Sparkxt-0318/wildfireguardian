# RESULTS: how far can a fire get in 5 h and 8 h, and how often is that wrong? (kcf-margin)

**Headline (MEASURED, n = 28 California fires, GOFER hourly).** Set per issue time at a 10% miss target, the reach margin beyond the known perimeter is 3.8 km for 5 h and 5.0 km for 8 h. It was exceeded at 6.2% and 6.6% of held-out issue hours (leave-one-fire-out, fire-weighted, 95% CI 0.6–22% and 0.7–23%). These are averages over fires like these, not a promise for any one fire or hour. In running hours the margin has to grow to 7.6 km / 10.0 km. On 25 March 2025 in Gyeongbuk, every frozen margin failed for 11 consecutive issue hours (10–20 KST), when the fire's 5 h reach went up to 40 km.

Protocol: `PROTOCOL.md`, committed before any score (746d005). All numbers are in `numbers.json` and are MEASURED unless marked ASSUMED.

## The table

R = km beyond the known (cumulative GOFER) perimeter. It is set by split conformal over fires, using one random issue hour per fire, as the median over 2,000 draws. "LOFO miss" = the share of the held-out fire's issue hours with reach > R, where R is set on the other fires. It is averaged over fires, with a Clopper–Pearson 95% interval in brackets. n = number of fires with hours in the class. All values MEASURED; class edges ASSUMED (protocol).

| class (last 3 h spread / max gust next h) | n fires | R 5 h @10% | LOFO miss 5 h | R 8 h @10% | LOFO miss 8 h | R 5 h @20% | LOFO miss 5 h | R 8 h @20% | LOFO miss 8 h |
|---|---|---|---|---|---|---|---|---|---|
| **all hours** | 28 | **3.8** | 6.2% (0.6–22) | **5.0** | 6.6% (0.7–23) | 2.2 | 16.4% (5.2–35) | 2.7 | 16.3% (5.1–35) |
| quiet (< 1 km) | 28 | 2.6 | 5.7% (0.5–22) | 3.5 | 5.9% (0.5–22) | 1.5 | 16.1% | 2.2 | 16.5% |
| slow (1–3 km) | 28 | 5.0 | 6.1% (0.6–22) | 6.4 | 5.9% (0.5–22) | 3.0 | 16.7% | 3.9 | 17.2% |
| running (≥ 3 km) | 27 | 7.6 | 6.6% (0.7–23) | 10.0 | 6.6% (0.7–23) | 5.2 | 17.7% | 6.8 | 17.9% |
| gust < 10 m/s | 28 | 2.6 | 5.9% | 3.0 | 5.9% | 1.5 | 16.5% | 1.9 | 16.0% |
| gust 10–20 m/s | 28 | 4.7 | 6.3% | 5.9 | 6.2% | 3.0 | 16.6% | 3.4 | 16.9% |
| gust ≥ 20 m/s | **9** | 8.6 | 0.0% (0–34) | 12.0 | 0.0% (0–34) | 7.2 | 9.9% (0.2–47) | 8.1 | 13.9% (0.7–51) |
| *without "Complex" fires:* all hours | 17 | 4.6 | 4.6% (0.0–27) | 5.8 | 4.2% (0.0–26) | 2.3 | 15.5% (2.9–41) | 2.9 | 15.9% (3.0–41) |
| *without "Complex" fires:* running | 16 | 7.9 | 4.4% (0.0–28) | 9.9 | 5.0% (0.1–28) | 5.7 | 17.0% | 6.9 | 17.0% |

The full table, including without-Complex rows for every class, is in `numbers.json` → `table`.

## What this says

1. **Rough numbers, confirmed or corrected (ASSUMED priors → MEASURED).** For 5 h at 90%: all hours 5 → **3.8 km**; quiet 2 → **2.6 km**; running 9 → **7.6 km** (10.0 km for 8 h). The draw-to-draw spread of R is wide. For all hours at 5 h, the interquartile range over draws is 3.0–4.8 km, because each draw rests on 28 hours.
2. **Calibration holds on average and is conservative.** At both targets, the LOFO miss rate sits below target on every class with n ≥ 27 (Fig. 1): 6% at the 10% target and 16–18% at the 20% target. The intervals are wide (n = 28 fires) and include the target. With 9 fires, the gust ≥ 20 m/s class can say almost nothing (0/9 fires missed, CI 0–34%).
3. **The fastest hours are where the all-hours margin fails.** Take the all-hours R at the 10% target and the fastest 10% of hours by observed last-3 h spread (≥ 2.0 km). The 5 h miss rate there is **17.5%** fire-weighted (95% CI 5.8–36%, n = 28 fires, 2,063 hours); for 8 h it is 17.1%. The per-class R fixes most of this: running hours miss 6.6% with R = 7.6 km. Ranked by realised reach (top decile ≥ 2.4 km) the miss rate is 36%; at the 20% target it is 100% by construction (R = 2.25 km < 2.4 km), so that row only shows that the misses are the big hours.
4. **The worst hour per fire would be useless, as expected.** The 90th percentile over fires of each fire's worst 5 h reach is 14.4 km under the 5 km separate-fire rule and 33.9 km without it (lightning complexes merging). The committed 1 h table (`s-d1`, chessboard) gives 31.6 km. I could not reproduce the "about 51 km" rough figure; the closest single fire is LNU at 57 km with no separation rule. The per-issue-time R is 3.8 km.
5. **Separation rule barely matters for R.** For all hours at 10%, R(5 h) is 3.7 km with a 2 km rule, 3.8 km with the 5 km rule and 4.1 km with no rule. LOFO miss rates are 6.0%, 6.2% and 6.2%.
6. **Complex fires.** Dropping the 11 "Complex" fires raises R slightly (5 h: 3.8 → 4.6 km) and the miss rate stays under target (4.6%, n = 17). The result does not hinge on them.

## NIROPS 12–48 h check (MEASURED; R interpolation ASSUMED)

There are 3,683 consecutive survey pairs with gaps of 12–48 h (median 24 h) from **488** S-D9 part-A allowlist incidents. No other S-D9 part was read. The frozen GOFER R (all hours; for example 9.4 km at 24 h at 10%), linearly interpolated in h, is exceeded on **0.26%** of pairs fire-weighted (95% CI 0.01–1.2%) at the 10% target and **1.6%** (0.7–3.2%) at the 20% target. That is far below target. The NIROPS incidents are mostly smaller and slower (median 24 h reach 0.4 km, 90th percentile 2.1 km), and airborne-IR perimeters are sharper than GOES. So the GOFER R is **over-wide for this population**. This check shows the margin does not transfer as a calibrated number to a different population; it does not show the margin is safe for big fires.

## Gyeongbuk 25 March 2025 stress test (MEASURED on detections; perimeter proxy ASSUMED)

The frozen R (28 fires) was applied hour by hour to FIRMS VIIRS plus Himawari AHI hotspots. These are detections, not perimeters, and come from one fire on one day, so no rate is claimed.

- **00–09 KST:** reach 0–2.2 km in 5 h (up to 12 km in 8 h by 09 KST). At the 10% target, R(5 h) held in every hour; the 20% class R (1.5 km quiet) failed at 07–09 KST. R(8 h) held for the all-hours margin through 07 KST and failed from 08 KST, as the 8 h window reached into the afternoon run.
- **10–20 KST: failed every hour at both targets, all-hours and per-class.** The 5 h reach was 4.9, 6.6, 12.4, 23.9, 34.7, 32.9, 40.1, 38.6, 27.3, 20.3, 15.7 km, against R = 3.8 (all hours) or 2.6 / 5.0 / 7.6 km (class). The class rule failed for two reasons:
  - At 10–11 KST the fire looked *quiet* (0 km spread in the previous 3 h, from detections) just before a 35–50 km run. Prior spread gave no warning.
  - From 15 KST it was correctly *running*, but the reach was 4–5 times the running R.
- **21–22 KST:** the per-class R held again (reach 6.5 and 4.9 km < 7.6 km). The all-hours R still failed.
- **Counts:** 5 h, 11 of 23 complete issue hours missed with the class R and 13 of 23 with the all-hours R at 10%. 8 h, 13 of 20 complete hours missed with the class R and 12 of 20 with the all-hours R.
- **Gust class not applied:** there was no gust series for Korea in this run. That leaves a gap: an observed or forecast gust ≥ 20 m/s may be the only signal available in the quiet-before-the-run hours. UNVERIFIED.

The Gyeongbuk 25 March run is outside the GOFER distribution. Under the 5 km rule, the largest 5 h reach of any of the 20,161 GOFER issue hours is 17.3 km (North Complex; 29.8 km for 8 h), against Gyeongbuk's 40.1 km. No margin calibrated on these 28 fires could have covered it.

## Pixel-valid vs route-valid (MEASURED; grid road network ASSUMED; Fig. 3)

The setup is 5 h, held-out fire (LOFO), 40 spread hours per fire, a 1.5 km 4-neighbour lattice, and about 33,500 random detours around the zone, n = 28 fires. It is calibrated per pixel at 90% (R_pix ≈ 3.2–3.4 km).
- **8.7%** of spread pixels fall outside the zone.
- **15.8%** of spread hours have at least one missed pixel. A road network experiences a failure whenever any detour can hit a missed pixel, so at the hour level the zone fails about twice as often as the pixel rate suggests.
- Within those hours, **22%** of shortest detours cross a missed pixel. Shortest detours hug the zone edge, and that edge is where the misses are.
- Over all spread hours, only **3.3%** of random detours fail. That is lower than the pixel rate, because most random origin–destination pairs never come near the missed sector.

So the statement "pixel-valid is not route-valid" holds **per hour** (16% vs 9%) and **for the routes that matter in a missed hour** (22%). It does **not** hold for a uniformly random route (3%). The per-issue-time zone gives similar numbers: 7.3% pixels, 13% hours, 23% of detours in those hours, 2.8% overall. The two hour-level measures were added after the first route run. They are post hoc (see PROTOCOL Amendments).

## Limits

- GOFER is 28 fires, all large California fires from 2019–21, mapped with GOES at about 2 km. Hours are not independent within a fire; the fire is the unit. Clopper–Pearson with fractional k treats the 28 LOFO folds as independent, which they are not exactly.
- The class (c) gust is ERA5 reanalysis at one point per fire, used as a perfect forecast (ASSUMED). A real forecast would be worse.
- The Gyeongbuk "perimeter" is a union of detections: 375 m VIIRS at overpasses, plus 2 km AHI pixels without parallax correction, inside the KFS_01 rectangle only. Reach can be inflated by pixel size (about ±1 km) or deflated by smoke and coverage limits.

## Reproduce

```bash
research/kcf-margin/run_all.sh DATA_DIR WORK_DIR
```

DATA_DIR holds the unzipped GOFER v0.2 and NIROPS 2020–2024 archives (`research/harness-2026-11/data-fetch/fetch.py`; checksums verified). The full run takes about 8 minutes.

- **Tests:** `python3 -m pytest -q research/kcf-margin/tests` gives 10 passed.
- **Independent vector cross-check:** `tests/crosscheck_vector.py` covers 40 random fire-hours. Raster vs shapely-polygon reach differs by a median of 0.03 km and at most 0.37 km (under one cell).

Figures: `fig/fig1_miss_vs_target.png`, `fig/fig2_zone_by_class.png`, `fig/fig3_pixel_vs_route.png`.
