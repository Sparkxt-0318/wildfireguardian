# PROTOCOL — reach margin R(h) for 5 h and 8 h (kcf-margin)

Frozen 2026-11-16, committed before any reach score was computed. Changes after this commit go in an "Amendments" section with a reason.

**Question.** At an hourly issue time, how far beyond the known perimeter can the fire get in the next h hours (h = 5, 8, the Korean evacuation thresholds), and how often is a reach margin R(h) wrong on fires not used to set it?

**Data.** (1) GOFER v0.2 `GOFERC_fireProg.shp`, 28 California fires 2019–21, hourly cumulative GOES perimeters (sha256 96eca2e1…). This is the only data used to set R. (2) NIROPS 2020–24, only incidents in `S-D9/cohort/PART_A_ALLOWLIST_FINAL.csv` (12–48 h external check, never used to set R). No sealed S-D9 part is read. (3) Gyeongbuk 2025, 25 March KST (FIRMS VIIRS plus Himawari AHI): stress test of the frozen R only.

**Grid.** EPSG:3310, 375 m cells, cell-centre inclusion (as in `s-d1/gofer_cap.py`). Arrival hour A(c) = first perimeter hour containing cell c. Known burned set at issue hour t: K_t = {A ≤ t}.

**Score.** For issue hour t and horizon h, new cells N = {t < A ≤ t+h}. Reach S_h(t) = max over spread cells in N of the Euclidean distance (km, cell centre to nearest cell centre of K_t). S = 0 if there is no spread cell. Issue hours: every GOFER hour with non-empty K_t and t+h ≤ the fire's last perimeter hour.

**Spread or separate fire (one rule, fixed now).** Split N into 8-connected components. A component whose nearest cell is more than **5 km** from K_t is a **separate new fire** and is left out of S. Every other component is spread, including spot fires up to 5 km out. Sensitivity runs (not headline): 2 km and no exclusion.

**Unit of independence: the fire.** The worst hour per fire is never used. Calibration is **per issue time**. For each calibration fire, draw one issue hour uniformly at random (within the class), then apply split conformal to those n scores: R = the ⌈(n+1)(1−α)⌉-th smallest. Repeat for 2,000 draws (seed 20261116) and freeze the **median** R across draws. The claim reads: "for a randomly chosen hour of a randomly chosen fire like these, the fire's h-hour reach exceeds R with probability about α, on average over fires like these". It is not a per-hour or per-fire guarantee.

**Miss targets.** α = 0.10 and 0.20.

**Evaluation.** Leave-one-fire-out (LOFO). R is set on 27 fires and applied to every eligible hour of the held-out fire. That fire's miss fraction m_f is the share of its hours with S > R. The LOFO miss rate is the mean of m_f over fires (fire-weighted). Interval: Clopper–Pearson 95% on k = Σ m_f out of n fires (beta quantiles allow fractional k; conservative for [0,1] means by Hoeffding's convex-order bound). The miss rate is also reported separately for the fastest 10% of hours, defined two ways: (i) top decile of the observable prior-3 h spread; (ii) top decile of the realised reach S itself (pooled across fires).

**Classes.** Each is calibrated and evaluated separately; n fires per class is reported.
- (a) All issue hours.
- (b) Spread over the last 3 h, i.e. the reach from K_{t−3} to cells with t−3 < A ≤ t (same 5 km rule; needs t−3 ≥ first hour). **quiet** < 1 km; **slow** 1–3 km; **running** ≥ 3 km.
- (c) Max 10 m wind gust over (t, t+h] at the fire's final-perimeter centroid, from ERA5 hourly `wind_gusts_10m` via the Open-Meteo archive. This is reanalysis used as a perfect-forecast proxy (ASSUMED stand-in for a forecast). Classes: < 10, 10–20, ≥ 20 m/s.

**Complex fires.** All results are reported with all 28 fires and again without the 11 fires whose GOFER name contains "Complex".

**Prior expectations (ASSUMED, from a rough pass; to confirm or correct).** 5 h R at 90%: about 5 km for all hours, 2 km for quiet, 9 km for running.

**Pixel vs route (if time allows).** Per-pixel R_pix(h) is the fire-weighted 90% quantile of the distances of all spread cells to K_t, pooled over each fire's hours, set by LOFO. Zone Z = K_t dilated by R_pix. For each held-out fire, sample up to 40 issue hours with spread. Over the box around K_{t+h} (padded 5 km), lay a 4-neighbour road lattice with 1.5 km spacing (every 4th cell). Roads with a node inside Z are closed. Pick random node pairs outside Z whose straight segment crosses Z, and find the shortest path on the open lattice. A route **fails** if any cell it passes through burns in (t, t+h] outside Z (a missed pixel). Report the pixel miss rate and the route failure rate. Do the same for the per-issue-time R.

**NIROPS 12–48 h check.** For allowlist incidents, take consecutive survey pairs with gap g in [12, 48] h on the same 375 m grid (UTM). Score each pair with the same reach rule. Compare with GOFER-frozen R at h = round(g), fire-weighted by incident, with a Clopper–Pearson interval. Survey gaps are irregular and the earlier survey is the "known perimeter".

**Gyeongbuk stress test.** For 25 March 2025 KST, issue hours 00–23 KST. The known set at t is the union of FIRMS VIIRS detections (confidence not 'l', 375 m cells) and AHI B07/B14 hotspots up to t. An AHI pixel counts as a hotspot when B07 ≥ 320 K and B07 − B14 ≥ 25 K in at least 2 scans within the hour; both thresholds exceed the max of all four pre-ignition baseline windows. Each AHI pixel is drawn as a square of its pixel spacing on an EPSG:5179 375 m grid. The score and 5 km rule are the same as above. Apply frozen GOFER R(5), R(8) for all hours and for the prior-3 h class, and report every hour that failed. The AHI grid covers only the KFS_01 rectangle, so this is an approximation of perimeters, not perimeters.

**Labels.** Every number is MEASURED (computed here from data) or ASSUMED (an input or proxy). The word "guarantee" only appears with "on average over fires like these", and n is always stated.
