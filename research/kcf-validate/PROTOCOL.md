# kcf-validate: comparison rules, frozen before any comparison was computed

Frozen 2026-11-18, ~16:00 UTC. Hard stop: Fri 20 Nov 2026, 18:00 Shanghai (10:00 UTC). Deliverables: this file, `RESULTS.md`
(one validation table), `SKIPPED.md`, `numbers.json`, plus `PROSPECTIVE_LOG.md`.

Nothing in §2-§4 changes after the first outcome is computed. A mistake found later is corrected by a dated **amendment** at
the bottom, with the reason, never by editing this text.

**Every number here is model output compared with a record or with a simulator's truth. None of it is what happened to
people.** Every table says so.

## 0 What had been looked at when this was written

* The committed outputs of `research/kcf-roadcut` and `research/kcf-replay` (structure, `validation_table.csv`, `numbers.json`
  keys) and their frozen rules (`PROTOCOL.md`, `HOTSPOT_RULE.md`, `MEASURED_RULE.md`).
* Sentinel-2 STAC *metadata only* (`research/kcf-roadcut/s2_scene_metadata.txt`: dates, cloud cover, no-data percentage). No
  reflectance, SCL or dNBR value of any 22-27 March scene had been read.
* The header of `choi2026_kfs01/KFS_01_pswt_ok_toa.tif` (grid, `t0_utc` = 2025-03-22 02:24, units hours). No value had been
  compared with anything.
* `product/wfg-roadlayer`: its interface, one run of its own worked example (to measure run time), the CSV column names.
* A plumbing check of the twin simulator alone (`twin/twin_lib.py`, seeds 0-2): that it runs, takes 0.2 s, and that the
  simulated fire reaches the 영덕 columns after roughly 24-40 h at the stated speeds. No detection, system raster or
  roadlayer output of the twin existed. This check is why the twin's issue times are ignition + 24 h and + 36 h.

## 1 Sources, time box, and what "blocked" means

Order: 1 KEC traffic, 2 재난문자, 3 independent satellite record, 4 NIST Camp Fire, 5 twin experiment, 6 prospective log. Each
gets at most 90 minutes to obtain data. A source that cannot be obtained, or does not cover the dates, gets one line in
`SKIPPED.md` stating why, and nothing is compared for it. **No workaround**: no mirror, no third-party copy, no cached or
aggregator copy of an official dataset, no key or login that the user did not give, no change of the network policy by me.
A probe is a plain request to the source's own host.

Facts known when this was frozen (all before any comparison): from this container, a TLS CONNECT to `data.ex.co.kr`,
`www.data.go.kr`, `apis.data.go.kr`, `www.safekorea.go.kr`, `www.mois.go.kr`, `nvlpubs.nist.gov`, `www.nist.gov`,
`tsapps.nist.gov` is refused by the environment's proxy (HTTP 403 on CONNECT). The separate fetch tool failed on
`data.ex.co.kr`, `www.safekorea.go.kr`, `www.data.go.kr`, `nvlpubs.nist.gov` with "getaddrinfo ENOTFOUND" (host outside the
session's allowed domains). Sources 1, 2 and 4 are therefore not obtained; whether those sites also require a key or login
was not determined and is not claimed.

## 2 Source 3: independent satellite record of fire extent (Sentinel-2, 24 March 2025)

**Independence.** The replay's inputs are FIRMS (VIIRS SNPP, VIIRS NOAA-20, MODIS Terra, MODIS Aqua), Himawari-9 AHI, the Choi
2026 kriged time of arrival, KMA/ERA5 gusts. Sentinel-2 L2A is none of these. Whether the Choi reconstruction itself used
Sentinel-2 is **not known to me**; it is stated in every table that uses Choi. GK-2A (KMA NMSC) is not reachable (§1 class of
host, not probed beyond one request; `nmsc.kma.go.kr` CONNECT refused). Landsat 8/9 sits in a requester-pays bucket and is
not used. The only Sentinel-2 scenes of 22-27 March over the lattice (from STAC metadata, `s2_scene_metadata.txt`):
52SDF 22 Mar (32.5 % no-data, partial), **52SDF 24 Mar 02:17:30 UTC** (cloud 10.96 %, no-data 1.9 %), 52SDF 27 Mar (cloud
99.99 %, unusable); 52SEF 24 Mar 02:17:27 UTC (cloud 55.7 %, no-data 0). Rule fixed now: use the two 24 March scenes
`S2B_52SDF_20250324_0_L2A` and `S2B_52SEF_20250324_0_L2A`; pre-fire references are the scenes already fixed in
`research/kcf-roadcut` amendment 1 (`S2B_52SDF_20250314_0_L2A`, `S2B_52SEF_20250314_0_L2A`). The 22 March and 27 March scenes
are not used (partial / cloud). t_S = 2025-03-24 02:17:30 UTC (the 52SDF sensing time; the 52SEF scene differs by seconds).

**Satellite state of a cell.** Lattice = the Choi KFS_01 grid (EPSG:5179, 375 m, x0 1,085,250, y0 1,845,375, 79 × 237). Bands
B8A and B12 (20 m) and SCL from the two scenes, read from the open bucket `sentinel-cogs`. Pixel invalid if SCL ∈ {0, 1, 3, 6,
8, 9, 10, 11} in either scene or a band is 0. NBR = (B8A − B12)/(B8A + B12), dNBR = NBR_pre − NBR_post. A pixel is assigned to
the lattice cell containing its centre. Burned pixel: dNBR ≥ 0.10 (**primary**), ≥ 0.27 (sensitivity). Cell **burned** if
≥ 25 % of its valid pixels are burned, **unburned** otherwise, **not assessable** if < 50 % of its pixels are valid or it lies
outside both tiles. (Same thresholds as `research/kcf-roadcut` §5.3, not re-tuned.) The image shows burned-or-burning ground at
t_S, since 14 March; it does not show when a cell burned. Other fires in the tile would count as false alarms of the model;
this is stated and not corrected.

**Model states compared at t_S** (a cell is *model-reached*):
* **V1 Choi:** kriged time of arrival ≤ (t_S − t0_utc) = 47.875 h. (Input of the pipeline, not independent of it.)
* **V2 Known area:** the cell centre lies inside the union of the discs of `research/kcf-replay/fire_discs.json` with
  `t_utc` < t_S (FIRMS + AHI, radii as frozen in HOTSPOT_RULE). This is the replay's own "known fire area", evaluated at a time
  the replay did not issue for.
* **V3 / V4 MEASURED forecast zone:** the replay's MEASURED arm applied unchanged at an issue time T with T + H ≤ t_S:
  H = 8 h, T = 2025-03-23 18:00 UTC; H = 5 h, T = 2025-03-23 21:00 UTC (the zone is for T + H = 02:00 / 02:00 UTC, 17.5 minutes
  before t_S: stated). Zone = cells with distance d ≤ R(H) from the known area at T (discs with t < T), R from
  `measured_arms.curve("MEASURED", discs, T, H)` (class by prior-3 h spread, R5/R8 as frozen). `kcf-replay` issued only on
  25 March; these two issue times are an extension of its rule to earlier times, not a re-run of its outputs.

**Measures (all counts, with n).** Domain D1 = all assessable lattice cells (**primary**); D2 = D1 ∩ cells within 10 km of the
Choi finite-arrival footprint (secondary). For V1, V2 (and V3, V4): hits (model-reached and burned), misses (burned, not
reached), false alarms (reached, unburned), correct negatives, not assessable; POD = hits/(hits + misses), FAR =
FA/(hits + FA), CSI = hits/(hits + misses + FA). For V3/V4 additionally **coverage of newly burned cells**: among assessable burned
cells NOT in the known area at T (n reported), the fraction inside the zone, and the quantiles (10/50/90/max) of their distance to
the known area at T (km) next to R(H). Burned cells that burned before T but were never detected are in this count (they cannot
be separated from new burn) and are stated as such. Nothing is imputed; cells not assessable are counted, not dropped silently.

The roadcut/replay records this is compared with (the REPORTED rows of `research/kcf-roadcut/validation_table.csv`) are not
replaced by this source: it gives extent at one time, not closure times (stated in RESULTS.md).

## 3 Source 5: twin experiment (simulator = truth; the system sees only detections)

Code: `twin/twin_lib.py` (truth, detections), `twin/run_twin.py` (system, roadlayer runs, scoring). Region `yeongdeok_2025`, the
lattice of `product/wfg-roadlayer/examples/build_example_raster.py` (x0 1,093,875, y0 1,815,750, 214 × 67, 375 m).

**Truth.** `twin_lib.simulate(seed, t_ign)` with `PARAMS` exactly as in the file at the freeze commit; ignition 2025-03-24 12:00
UTC; seeds 0-11 (12 fires, fixed in advance, none dropped); issue times T = ignition + 24 h and + 36 h (2025-03-25 12:00 UTC
and 2025-03-26 00:00 UTC), horizon 8 h. A repetition is (seed, issue time): 24 pairs, **not independent** (one road graph, one
place set, seeds share the lattice). The simulator is not FARSITE and was not fitted to the 2025 fire.

**Detections the system may use** (generated from the truth only; ASSUMED values, fixed now):
* Burning cell at time s: arrival a ≤ s < a + 2 h.
* Polar-orbit passes: per sensor family the daytime and night-time centre time-of-day taken from `fire_discs.json`
  (SNPP, NOAA-20, Terra, Aqua; times in the committed file's clusters), repeated every day; at a pass, a pass is lost to cloud with
  probability 0.20; otherwise each burning cell is detected independently with probability 0.70 (VIIRS) / 0.35 (MODIS); detection
  = disc at the cell centre, radius 375 m (VIIRS) / 1000 m (MODIS).
* Geostationary (AHI-like): scans every 10 min; 2 km blocks (blocks of 5 × 5 cells aligned to the lattice origin); a block is
  *flagged* at a scan when ≥ 4 of its cells are burning and the block is not cloud-obscured (per block and hour, probability
  0.20); a hotspot (disc of radius 2000 m at the block centre) enters the known area one scan after the first flag (persistence).
* Delivery latency 0 (same optimistic choice as HOTSPOT_RULE).

**System under test.** The research pipeline unchanged: known area at T = discs with t < T; MEASURED arm class and R5/R8
(`measured_arms.curve`), closure time of a cell = `measured_arms.closure_s` of its distance to the known area, as built by
`build_example_raster.py` (the twin's re-implementation is asserted equal to that script's committed example raster on the real
discs, before use); arrival raster in minutes → `product/wfg-roadlayer run --as-of <issue time>`.
**Truth reference.** roadlayer on the *true* arrival raster at the same T (minutes from T to true arrival; ≤ 0 already burning; +inf
beyond 8 h). This is the same road-closure rule fed with the true arrival field, so it measures the loss from not knowing the fire,
not the validity of the road rule against real roads. **Control** (second arm): the same system fed *perfect detections* (every burning
cell detected at every pass, no cloud, every flagged block, same schedule and radii), to separate detection loss from the margin rule.

**Primary outcomes (per (seed, T) and pooled, with n and spread across seeds):**
1. *Cells* (lattice cells not burning at T): among cells with true arrival ≤ T + 8 h ("true-reach cells"): number whose system
   closure time is later than true arrival or absent (**late = system unsafe**), and the signed error (system − true, minutes) over
   cells where the system gives a finite time; **false-reach** = system finite ≤ 8 h, truth later or none.
2. *Places* (those with numbers in both roadlayer runs; refused places excluded and counted): state true / system ∈ {CUT inside the
   horizon, NOT CUT}. **Missed cut-off** = truth CUT, system NOT CUT, or both CUT with system cut time later than the true one.
   Reported at > 0, ≥ 15 and ≥ 60 min; signed error of the last-road cut-off (system − true) over places CUT in both; same for the fire
   arrival at the village; **false cut-off** = system CUT, truth NOT CUT.
3. Counts of places by true state, so that pairs in which the fire never reaches the road network are visible, not hidden.
Uncertainty: per-seed values are listed; the pooled rate is accompanied by a seed-level bootstrap interval (2000 resamples of the 12
seeds; descriptive only, 12 seeds of one simulator and one region). No claim beyond this simulator.

## 4 Source 6: prospective log

`PROSPECTIVE_LOG.md` fixes a procedure to commit a prediction before the outcome is known and to score it against the same
frozen rules. A first entry is made only if a fire is **active** and its detections can be read from an allowed source. Rule: an
entry is committed and **pushed to the remote** (server-side receipt time) before the outcome time it predicts; the entry holds the
SHA-256 of the prediction file; later edits are new entries, never changes.

## 5 Reporting

* Errors as measured, including misses; signed; n with every number.
* One validation table in `RESULTS.md`; sources skipped have a row saying NOT OBTAINED and why, so a reader cannot take absence for a pass.
* REPORTED rows: a REPORTED row is replaced only by an official record read at the source. None could be (§1); the count of
  replaced rows is 0 and is stated.
* No statement about what any official should have done.

## Amendments
