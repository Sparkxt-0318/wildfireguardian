# PROTOCOL: a forecast margin that attributes its own misses, corrects one term, and reports its expected error (kcf-adaptive4)

Committed before any result of this folder was computed. What had been seen when this was written: the RESULTS.md
files of `kcf-adaptive2` and `kcf-adaptive3` (including their per-hour 25 March tables), the column names and first
rows of the committed tables in `kcf-abstain/derived`, `kcf-aloft/derived`, `kcf-margin/derived`, and the file lists
of the two Zenodo records. No number of this folder existed. Later changes are logged in section 10 as amendments,
each with what had been seen.

Labels used in RESULTS.md: MEASURED, ORACLE (uses the fire's future; never a result for a method), ASSUMED, NOT RUN.

## 1. Data and splits (by fire, always)

| set | fires | role |
|---|---|---|
| CA-DEV | the 16 GOFER v0.2 fires of kcf-adaptive3 (kcf-adaptive2 outer folds 0 to 3) | every fit, every choice (wind term, correction settings), attribution |
| CA-HELD | the 12 GOFER fires of kcf-adaptive3 (folds 4 to 6) | scored once per model after all choices are frozen |
| KR | 12 Korean fires with Choi et al. 2026 arrival rasters (756 issue hours at 5 h in the earlier folders) | leave-one-fire-out: the scored fire is out of every fit; models are fitted on the 28 California fires plus the 11 other Korean fires |
| DET | detection product (FIRMS VIIRS + Himawari AHI) for KFS_01 on 25 March 2025 KST, built by `kcf-margin/score_gyeongbuk.py` | target A; KFS_01 is out of every fit |

Fold assignment is the kcf-adaptive2 hash; not chosen here. **Not a first look:** all 28 California fires were scored
in kcf-adaptive2, CA-HELD in kcf-adaptive3, the Korean fires and 25 March in kcf-adaptive2, kcf-adaptive3 and
kcf-aloft. "Held out" below means held out of every fit and choice in this folder.

Geometry is rebuilt from the same Zenodo files (GOFER 14642378, Choi 21788344) with kcf-adaptive2's reach rule
(kcf-margin `component_reach`, 5 km separate-fire rule), extended to every lead h = 1..8 h. Eligible issue hour:
reach at that lead defined, fire age at least 3 h, forecast features present (as in kcf-adaptive2). Reach S(t,h) in
km; flagged area A_t(q) from the exact area curve, cap 60 km. Miss at (t,h): S(t,h) > q(t,h).

Forecast inputs: kcf-abstain `derived/hours.csv.gz`, unchanged: surface gust and 850 hPa wind speed as issued
(GFS or HRRR, 5 h availability delay ASSUMED there), each the maximum over the next 8 h at the fire location.
**The same 8 h window value is used for every lead 1..8** (hourly as-issued fields are not in the repo; re-fetching
them is about 200 GB). This is a stated limit, not a choice made after results.

Truth wind ("observed or reanalysis"): ERA5 hourly 10 m gust at the fire location (Open-Meteo archive API), reduced
exactly like the forecast (maximum over t+1..t+8). For the 850 hPa variant the truth is the Open-Meteo
historical-forecast archive value of 850 hPa wind (short-lead model analysis proxy; ERA5 pressure levels are not
served there). Secondary truth for Korea: KMA station gusts within 50 km (kcf-aloft `gobs_fire_hours`), reported
beside ERA5, not used for verdicts.

## 2. Models

All margins are per lead h. Every model ends with one scale factor kappa_h calibrated so that the fire-weighted miss
rate on its training fires is 10% (the kcf-adaptive2 rule), so models are compared at the same target.

- **BASE-gust, BASE-850**: q(t,h) = k_h x W(t) x h, W in km/h (m/s x 3.6), k_h dimensionless. k_h minimises the
  fire-weighted pinball loss at tau = 0.9 of S against k x W x h on training fires, then kappa_h as above.
  Also reported: one k for all leads (k calibrated on leads 1..8 pooled).
  **Choice of wind term**: the variant with the lower fire-weighted area at 5 h on CA-DEV (cross-validated by fire,
  4 folds) is the primary BASE; the other is reported. Made once, before CA-HELD or Korea is scored.
- **FIXED**: q = c_h, a constant per lead, calibrated to 10%.
- **QUANTILE**: gradient-boosted 0.9-quantile on the kcf-adaptive2 feature list (own-past and issued forecast),
  settings fixed at the ones its inner cross-validation chose in all seven folds (depth 3, 100 iterations,
  learning rate 0.05, leaf 200), one model per lead, then kappa_h. For leads other than 5 and 8 the own-past features
  are the same g1..g24.
- **RULE**: k = 0.10 applied to the issued surface gust, no calibration (Cruz and Alexander's rule is stated for the
  10 m open wind speed; the issued 10 m mean wind is not in the committed features, so the gust stands in and RULE
  is an upper version of the rule). RULE is reported at its own miss rate and, separately, rescaled to 10%.

## 3. Attribution (step 3)

Population: every missed (t,h) of the primary BASE on development fires, with the fire held out of the fit of k
(CA-DEV: 4-fold by fire; Korea: leave-one-fire-out, DET hours for 25 March KST and Choi hours otherwise). Lead 5 h is
the headline; all leads are tabulated. California and Korea separately.

Four terms, each with a truth that can be swapped in alone or together:

1. **Wind input.** W(t) from the issued forecast is replaced by the truth wind of section 1.
2. **Coefficient k.** k_h is replaced by the fire-day's own coefficient: the 0.9-quantile of S/(W x h) over the
   issue hours of the same fire and local day whose outcome windows do not overlap (t, t+h] (leave-window-out, so the
   scored hour cannot set its own truth); if fewer than 6 such hours exist, over all non-overlapping hours of the
   fire. Local day = solar day at the fire.
3. **Starting fire area.** The reach is measured from the union of the product's burned set at t and independent
   evidence of fire already present at t: S_start(t,h) = largest distance from (K_t union E_t) of the cells that
   arrive in (t, t+h]. E_t is: for California (GOFER, from GOES) the FIRMS VIIRS S-NPP and NOAA-20 detections up to t
   (confidence not low); for 25 March (detection product) the Choi arrival raster of KFS_01 up to t (the later
   perimeter). On the Korean Choi hours the product is itself the later perimeter, so this term is **not measurable
   there** and is reported as such, not as zero.
4. **Timing.** The wind term is read at t + d instead of t, where d (one integer per fire and local day, -6..+6 h) is
   the lag that maximises the Spearman correlation between W(t+d) and S(t,h) over that fire-day's issue hours
   (ties: smallest |d|; undefined correlation: d = 0). A positive d means the run came later than modelled.

For a set T of swapped terms, v(T) = 1 if S (with the start swap if in T) is at most k (own if in T) x W (truth if in
T, lagged if in T) x h. Reported per region: (a) single-swap fix rate of each term (not exclusive); (b) the exact
Shapley share of each term over the 16 subsets, averaged over misses (share of misses) and weighted by missed area
A_t(S) - A_t(q) (share of missed area); the part of v(all four) that is 0 is reported as **unexplained**. Shares are
descriptive; intervals are fire bootstraps.

## 4. Targeted correction (step 4)

At issue hour t, using only what is known at t for the scored fire: outcomes of earlier issues (t', h') with
t' + h' <= t, truth wind for hours up to t (ASSUMED available in real time, as station observations would be), and
evidence E up to t. Three arms, identical except for what they update:

- **NONE**: the primary BASE.
- **TARGETED**: for the matured (t', h') of the last L hours, each miss is attributed with the section 3 swaps
  computed from data up to t only (online truths: observed wind over the matured window; realised coefficient
  S/(W x h'); start deficit from E; lag from the matured hours). The term with the largest summed Shapley share is
  blamed, and only it is updated: wind -> multiplicative bias (observed/forecast over the matured hours);
  k -> multiplied up to the 0.9-quantile of the matured realised coefficients, floor at the pooled k; start -> the
  observed start deficit (km) added to the margin; timing -> the wind term held at its maximum over the last |d| hours.
  With no matured miss in the window, every correction decays toward the pooled model with half-life H.
- **ALL**: the same four updates, all applied every hour (the approach that failed before).

Settings (L in {6, 12, 24} h, H in {3, 6, 12} h) are chosen once on CA-DEV by fire-weighted pinball loss at 5 h,
cross-validated by fire, shared by TARGETED and ALL (each arm gets its own best pair). After correction each arm is
recalibrated with its own kappa_h on training fires, so arms are compared at a 10% target. Leakage test: scrambling
every outcome and truth value after t leaves the margin at t bitwise identical.

## 5. Metrics

- **Miss rate** (fire-weighted, per lead) with a fire-cluster bootstrap interval (2,000 resamples, seed 20261119).
- **Flagged area** (fire-weighted mean km2 per issue hour) at the calibrated margin, and read at exactly 10%
  held-out miss by sweeping kappa (descriptive). Ratios to FIXED by paired fire bootstrap.
- **Reach error (km)**: the pinball loss at tau = 0.9 of the issued margin against the realised reach,
  fire-weighted. This is the proper score of a 10%-miss margin: it charges 0.9 km per km of shortfall on a miss and
  0.1 km per km of excess on a hold. Reported beside it: mean shortfall on misses (km) and mean excess on holds (km).
- **Error growth**: slope (km per hour of lead) of the reach error against lead 1..8 by least squares on the eight
  fire-weighted means, per model, with and without correction; its change is (slope corrected - slope uncorrected) /
  slope uncorrected, with a paired fire bootstrap interval.

## 6. Expected error handed to research/kcf-robust (step 5)

File `derived/expected_error.csv.gz`, one row per (fire, issue hour, lead 1..8), format documented in
`EXPECTED_ERROR_FORMAT.md` (written with the code, before the file is scored). It carries the issued margin and the
model's own expected reach error: calibrated quantiles (0.5, 0.8, 0.9) of the shortfall S - q that the model expects
at that hour and lead, obtained by split-conformal scaling on training fires (scale = k x W x h; the quantile of
(S - q)/scale conditional on the model's state: corrected or not). Calibration is checked on held-out fires: the
share of held-out (t,h) with S - q above the reported 0.9 quantile should be 10%, and is reported per lead with a
fire-bootstrap interval. The scored fire is never in the calibration set.

## 7. Targets (all at a 10% miss rate, checked on held-out fires)

- **A.** 25 March 2025, issue hours 09 to 20 KST, 5 h lead, detection product, KFS_01 out of every fit: the final
  model (primary BASE with TARGETED correction) holds **more than 1 of 12** hours. Counts only.
- **B.** 12 Korean fires, leave-one-fire-out, 5 h lead: achieved miss rate of the final model **at or under 10%**
  (point estimate; interval reported).
- **C.** TARGETED lowers the 5 h reach error against NONE: paired difference (TARGETED - NONE) of the fire-weighted
  pinball loss over the 24 held-out fires (12 CA-HELD and 12 Korean leave-one-fire-out), fire bootstrap 95%
  interval **entirely below zero**. Regions are also reported separately; ALL - NONE and TARGETED - ALL likewise.
- **D.** Report flagged area of every model in Korea and California against FIXED, and on the 34 Korean fire-days
  without a run (kcf-adaptive3's list: fire-days with no issue hour whose 5 h reach exceeds 3.75 km). D is a
  reporting requirement; it fails if any of these is missing. A model that holds 25 March by flagging everything is
  not a success: A is read together with the area on 25 March and on the no-run fire-days.

A target that fails is reported as failed. The closing sentence of RESULTS.md is filled only from measured numbers,
and any clause without support is deleted.

## 8. Order of work and what may be looked at

1. This file. 2. LITERATURE.md. 3. Data build and tests. 4. CA-DEV: base models, wind-term choice, attribution,
correction settings. 5. Freeze (commit) the choices. 6. CA-HELD, Korea and 25 March, once. 7. RESULTS.md.
Nothing is tuned after step 6. If a bug is found after step 6, the fix and both results are reported.

## 9. Limits known in advance

- One 8 h wind window for all leads (section 1). The timing term can only shift that window.
- Start-area evidence is a lower bound in California (VIIRS overpasses are about 12 h apart per satellite) and is
  not measurable on the Korean Choi hours.
- Truth wind is a 0.25 degree reanalysis, not a station at the fire.
- 28 + 12 fires, one 25 March. Intervals are fire bootstraps, with no correction for the number of comparisons.

## 10. Amendments

**Amendment 1** (2026-11-19, before any model result). Seen so far: the rebuilt geometry reproduces the committed
5 h and 8 h reach to 1e-6 km; the 24 rows of the 25 March detection product with their reach and start-swapped
reach (identical at 5 h on every hour, so the starting-area term will be near zero that day); coverage of the truth
wind fetch. No margin, miss rate or area of any model had been computed.

1. The 850 hPa truth wind is missing for every 2019 and 2020 fire (the archive that serves it starts in 2021).
   If BASE-850 is the primary model, wind attribution in California covers the 2021 fires only and says so.
2. Start evidence in California keeps only VIIRS detections within 5 km of K_t (the separate-fire rule). On 25 March
   the Choi raster is the same fire by construction and no distance rule is applied.
3. The expected-error file also carries the 0.95 and 0.99 quantiles (the tail beyond the margin is what a robust
   router needs); calibration is checked for each.
4. Online versions of the truths used by TARGETED and ALL (section 4 named them only): truth wind is the maximum over
   the hours of the 8 h window that have already passed; the fire's own coefficient is the 0.9-quantile of
   reach / pooled margin over matured issues of all leads in the window (for attributing one miss, over the matured
   issues whose outcome windows do not overlap it; all of them if fewer than 6); the lag maximises the Spearman
   correlation between the wind term and the matured mean spread rate per issue hour; the start deficit is the
   largest distance of evidence from K_t at t. The Choi raster is not available in real time, so on 25 March the
   start term has no online truth and cannot be blamed online. Multipliers: wind bias clipped to 0.5..3; ALL sets
   the wind bias to the window value (it may be below 1), TARGETED only raises it. Decay: every correction moves
   toward the pooled model by a factor 0.5^(1/H) per hour and is refreshed by the window value when its term is
   updated. Attribution inside the loop is always of the pooled (uncorrected) margin, so corrections do not compound.
5. On 25 March the detection product has 24 hourly rows (from 00 KST). The correction starts cold there; the Choi
   hours of 22 to 24 March are not used to warm it.
6. Process pools are not available in this environment; the build is serial. No effect on results.

**Amendment 2** (2026-11-19, after the first development results). Seen: the CA-DEV base table (FIXED, QUANTILE,
RULE, BASE-gust, BASE-850 at every lead; gust chosen, 375.8 against 377.4 km2); the first CA-DEV attribution
(wind 41% of misses, k 12%, start 20%, timing 12%, unexplained 15% at 5 h; single-swap fix rate of wind 70%); six
of the eighteen grid cells (kept in `derived/before_amendment2/`); and the reason for this amendment: the truth gust
(ERA5 at the fire) is on a different scale from the issued gust (median ratio 1.74 on CA-DEV, 1.18 on Korea), so
swapping it in under the forecast-fitted k inflates every margin and "fixes" misses that have nothing to do with
forecast error. No held-out fire, Korean fire or 25 March margin had been computed.

Change: the wind swap, offline and online, multiplies the truth wind by s_h = k_h fitted on the truth wind /
k_h fitted on the forecast wind (both on the same training fires, both calibrated to a 10% miss). The swapped
model is then the same kind of model, at the same miss rate, with the truth wind in place of the forecast wind,
which is what "swapping in the truth" was meant to be. The online wind bias uses the same scaled ratio. Nothing
else changes; the attribution and the grid are rerun from scratch and the superseded outputs are kept.
