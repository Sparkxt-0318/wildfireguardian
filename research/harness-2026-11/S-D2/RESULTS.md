# S-D2: a likelihood on what the sensors observed — verified results

Stream S-D2 of the November 2026 harness, for the SMOKE fire-arrival forecast (`forecast/`). This file holds **only
results an independent verifier has passed**. Each section carries the verifier's notes as limits. Later, unverified
work stays on the development branch `claude/s-d2-interval-censored-likelihood`.

**Scope.**
* No neural refit has run.
* Nothing was scored on sealed fires (S-D9 parts b, c, d or H-test).
* No existing code, checkpoint or frozen result is changed.
* Everything here is development evidence, not a forecast-skill claim.

## Verdicts

| Claim | Commit | Verifier | Verdict |
|---|---|---|---|
| Kriging SD calibration against NIROPS brackets | 6d125bd | Hannah | PASS WITH NOTES |
| Synthetic known-kernel study (soft labels, MCEM, hourly arms) | c7f7df3 | Hannah | PASS WITH NOTES |
| Block-CV standardized residuals of kriging variance | b8aeafb | Owen | PASS WITH NOTES |
| NIROPS part-a bracket extraction (access and construction) | 4d09067 | Owen | PASS WITH NOTES |
| Robustness study (bracket width, misspecification, kriged inputs) | 4bb7933 | Owen | PASS WITH NOTES |
| Composite shape + simulated scalar rate (negative result) | d68d790 | Owen | PASS WITH NOTES |

## 1. The kriging SD is too small against survey brackets (6d125bd)

`python calibrate_kriging_sd.py --rasters <zenodo>/rasters_us --out results/kriging_sd_calibration.json` (about 3 s)

* **Data.** The Choi et al. 2026 product (Zenodo 10.5281/zenodo.21788344, PSwt-OK) is tested against per-cell NIROPS
  brackets from the forecast-v2 held-out rows of the six US 2024 fires. That use is evaluation-only and recorded in
  S-D9's ledger.
* **Method.** Fit a scale c by interval-censored likelihood on `N(mu, (c·sd)^2)`.
* **Result.**
  * Pooled c = **1.747** (13,324 cells, 8,520 mapped; NLL 26,763 vs 31,143 at c = 1).
  * Per fire, c runs from 1.07 (Pioneer) to 2.21 (RedRock).
  * With a free shift, per-fire mean shifts run from −11 to +57 h.
  * Median product SD is 27–96 h.
* **Limits (Hannah):**
  * What is verified is "the kriging SD understates uncertainty *relative to the NIROPS bracket reference*". c also
    absorbs NIROPS survey-time and mapping error, and mapped extent is not flame arrival.
  * The central-interval "hit" rates count intersection, so they are conservative.
  * row/col orientation was checked by correlation.

## 2. Synthetic known-kernel study (c7f7df3)

`python run_synthetic.py --replicates 16 --workers 4 --out results/synthetic.json` (about 10 min); tests `python -m pytest -q tests`.

* **Truth.** A continuous-time lattice with a 5×5 kernel; arrivals are simulated exactly. Held-out excess NLL is
  scored on the true arrivals of fresh fields.
* **Survey brackets every 12 h.** MCEM over latent arrival times beats the first-observation plug-in on held-out NLL
  in **16/16** replicates (0.091 vs 0.275). Rate ratio 1.01 vs 0.88.
* **Soft hourly labels as first specified** (hard risk set) halve the fitted rate (0.53) and have the worst NLL. A
  soft risk set fixes most of this.
* **Small calibrated Gaussian kriging error:** MCEM is worse than hard hourly labels on NLL (3/16). This is a
  negative result for MCEM in that regime.
* **Limits (Hannah):**
  * MCEM rows are Monte Carlo estimates and differ across numpy/scipy builds by up to 34% per replicate. The paired
    directions hold, but close counts such as 3/16 are not decision inputs.
  * The "oracle" row is the complete-data MLE on one training field, not a lower bound.

## 3. Block-CV standardized residuals of the kriging variance (b8aeafb)

`python blockcv_kriging_sd.py --choi <zenodo> --firms firms_us2024_heldout6.csv.gz --out results/kriging_sd_blockcv.json` (about 100–150 s)

* **Method.** VIIRS cells are held out by spatial block, following Choi et al.'s U.S. design, and
  `z = (obs − pred)/kriging SD` is computed for each. `choi_kriging.py` is our port of the published algorithm; the
  downloaded code is not executed. The configuration is P-OK without GOES points, with detections selected by the
  raster mask.
* **Result.**
  * All 6 fires (12,905 cells): z SD 1.08; |z| > 1.645 in 10.2% (nominal 10%); |z| > 1.96 in 7.8%; robust SD 0.36.
  * The 3 fires that replicate Choi's published CV (Wapiti, Goat, Lava; 6,951 cells): |z| > 1.96 in 5.4%,
    |z| > 1.645 in 6.8%.
* **Limits (Owen):**
  * The z values use the port's **block-CV kriging SD (median 116–326 h), not the product SD raster** behind §1.
  * The "core too narrow" reading is robust (robust SD 0.10–0.46 on every fire except Pioneer).
  * **"Heavy tails" rests on the three poorly replicated fires** (Pioneer alone has 25% beyond 1.96) and is not
    established.
  * Replication of Choi's CV is good for Goat and poor for Pioneer, FishCreek and RedRock.

## 4. NIROPS part-a bracket extraction (4d09067)

`python nirops_brackets.py --shp <NIROPS .shp> --allowlist PART_A_ALLOWLIST_FINAL.csv --source-ref <commit> --out DIR` (about 90 s)

* **Access.** Part a only, by construction.
  * Allowlist: S-D9 `PART_A_ALLOWLIST_FINAL.csv`, sha256 7db3cc0e at 2d40d170. Rule: surveys ≥ 20, giving 42
    incidents.
  * Each incident is read through an `Incident_C` attribute filter.
  * **Access log:** `results/nirops_part_a_index.json` (allowlist sha, commit, rule, every incident read).
* **Construction.** Rasterize on a 375 m EPSG:5070 grid with the cell-centre rule, apply a cumulative union, and
  record each cell's first-mapped survey. No arrival raster is read.
* **Verified (Owen).**
  * Access by construction.
  * The logic on a synthetic shapefile with out-of-order and duplicate timestamps, a shrinking survey, a decoy
    incident and a below-threshold incident.
  * An independent extraction on two non-GOFER part-a fires (Bridge, Line), which matches cell for cell.
* **Ledger.** Five of the 42 are GOFER fires: Bobcat, CZU, KNP, LNU-Meyers and Slater. **Per A1 item 25** they are
  H-dev, not H-test, and may be used in part-a development.
* **One change from the verified file:** the docstring's allowlist sha is updated from 801acdd8 (superseded) to
  7db3cc0e.

## 5. Robustness study (4bb7933)

`python run_robust.py --replicates 8 --workers 4 --out results/robust.json` (about 32 min); tables in `results/robust.md`.

**Total-rate ratio Σk̂/Σk against bracket width** (Markov truth, median cell-crossing time 6.6 h; mean of 8 replicates):

| Bracket | Plug-in | Composite | MCEM | MCEM beats plug-in on held-out NLL |
|---|---:|---:|---:|---:|
| 3 h | 1.014 | 0.861 | 1.025 | 3/8 |
| 6 h | 0.989 | 1.000 | 1.028 | 5/8 |
| 12 h | 0.905 | 0.894 | 1.039 | 8/8 |
| 24 h | 0.665 | 0.647 | 1.040 | 8/8 |

* **Limits (Owen):**
  * The full latent-time method (MCEM) **wins on total rate and held-out likelihood with perimeter brackets, but not
    on kernel shape**: the composite has lower rel-L2 at 12 h (0.546 vs 0.625) and 24 h (0.620 vs 0.670).
  * MCEM's rate carries a small, consistent **+2.5–4% upward bias** (2–3 SE).
  * **On kriged inputs** (calibrated, spatially correlated, or SD understated 1.75×) MCEM is worse than the simple
    arms on held-out NLL. The perimeter result does not carry over to kriged inputs.
  * "Deterministic" estimators are deterministic only up to optimizer tolerance.
  * Disclosed failures: `meanfield_brier` converges to the floor at 3 h, and under non-exponential (gamma) truth
    every estimator gives about 0.3 because the Markov kernel is misspecified.

## 6. Composite shape + simulated scalar rate is a negative result (d68d790)

`python run_composite_scale.py --replicates 8 --workers 4 --out results/composite_scale.json` (about 70–100 s)

* **Method.** The candidate came from Iris. The composite kernel shape is rescaled by one multiplier, chosen so
  that exact forward simulation from the known survey states matches the observed total new-burn count.
* **Result.** It overshoots the total rate: about **1.08 / 1.18 / 1.37** at 6 / 12 / 24 h and 1.30 with spotting,
  against MCEM's 1.03–1.10. It beats MCEM on held-out NLL in 1/8, 0/8, 0/8 and 0/8.
* **Limits (Owen):**
  * The estimator is not bit-reproducible: means vary by about ±0.01 on rerun, and per replicate by up to ±0.06.
  * The recovery test band is loose (it would not catch a 15% bias). That is adequate only for a negative result.
* This estimator is excluded from A1. S-D9's `rate_composite` fits the scale by bracket likelihood instead.

## Not verified (not in this PR)

* Covariate-free rate comparison on 25 part-a NIROPS fires (plug-in 0.454, mean-field NLL 0.587 and composite 0.967
  of MCEM). Owen's check is in progress.
* Profile-likelihood intervals for the SD scale, and peak-memory figures.
* Missed-detection arm, `rate_composite` (A1 §3.2) test, detection-probability identifiability.
* Any neural refit (D2 candidates in A1 item 21), the AHI pixel constraint, and Korean SD calibration.

## Reproduce

Environment used: Python 3.13, NumPy 2.1.3, SciPy 1.14.1, pandas 2.2.3, rasterio 1.4.3, pyproj 3.7.0, pyogrio 0.10.0,
shapely 2.0.6, 4 CPUs. The verifiers used Python 3.12 with newer numpy and scipy (MCEM digits differ; see §2).

* **Inputs.** Each is fetched with `research/harness-2026-11/data-fetch/fetch.py` from branch `daniel/data-fetch`:
  * Zenodo 10.5281/zenodo.21788344 (zip sha256 612edf5f…);
  * FIRMS `firms_us2024_heldout6.csv.gz` (971f825d);
  * NIROPS 2020–2024 (zip sha256 b19fb16c…).
* **Allowlist:** S-D9 `cohort/PART_A_ALLOWLIST_FINAL.csv` at 2d40d170.
* **Tests:** `python -m pytest -q research/harness-2026-11/S-D2/tests` (24 passed).

| File | Purpose |
|---|---|
| `soft_labels.py` | soft and hard window labels |
| `synthetic.py`, `run_synthetic.py` | generator, likelihoods, hourly fits, soft risk set, Gibbs sampler, MCEM |
| `synthetic_robust.py`, `run_robust.py`, `run_composite_scale.py` | robustness study and the negative result |
| `calibrate_kriging_sd.py` | §1 |
| `blockcv_kriging_sd.py`, `choi_kriging.py` | §3 |
| `nirops_brackets.py` | §4 |
| `results/` | committed outputs and the part-a access log |
