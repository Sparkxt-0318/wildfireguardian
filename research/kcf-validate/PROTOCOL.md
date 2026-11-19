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

1. **2026-11-18 ~15:35 UTC, after the freeze commit `1a6a5a7` and after the four scenes were downloaded, before any band value was
   read.** (a) Timestamp correction: the freeze was at 15:29 UTC (commit time), not "~16:00 UTC" as written in the header.
   (b) Reflectance offset. The scenes are processing baseline 05.11, which adds a BOA offset of −1000 DN. `research/kcf-roadcut/
   burned_area.py` (whose thresholds §2 reuses) computed NBR on raw DN, and §2's formula is written on raw DN. Rule: the
   **primary** map stays on raw DN (identical definition to roadcut's map, so the two are comparable); a **sensitivity** map
   applies (DN − 1000)/10000 to both bands in both scenes (pixel valid only if the corrected value stays > 0 in B12 and B8A) and
   is reported next to the primary at the same two dNBR thresholds. No other change.

2. **2026-11-18 ~15:45 UTC, after the 24 truth-arm roadlayer runs finished, before any system-arm or control-arm output was read.** Only the
   truth arm's status vocabulary and counts were looked at: statuses are "cut", "not cut within the horizon", "already cut at the issue time
   (fire at the village)", "already cut at the issue time", and blank (refused). Truth place-pairs: 221 CUT (118 cut inside the horizon, 103
   already cut at issue), 1,939 NOT CUT, 24 refused (one place per pair). §3 item 2 is clarified, no outcome rule changes: a place is CUT
   whenever `road cut (s after issue)` is numeric, which includes the two "already cut at the issue time" statuses (cut time 0 or earlier).
   Because "already cut at issue" is decided by what the detections already show, not by forecasting, **every place-level number is reported
   three times**: all CUT places; only places whose truth status is "cut" (cut inside the horizon, the forecast part); only places whose
   truth status is "already cut at the issue time…". NOT CUT places enter all three for the false-cut-off count. No region was added (the
   truth reaches the 영덕 roads in 20 of 24 pairs).

3. **2026-11-18 ~22:48 UTC (the user allowed the blocked hosts; this session now runs on environment `wildfireguardian-kcf-validate`),
   before any NIST row was parsed or compared.** What was read after the hosts opened (portal pages and the NIST PDFs only; no outcome):
   * **Source 1.** `data.ex.co.kr` lists the needed data: API 0305 "노선별 방향별 일별 15분 구간교통량" (`/openapi/trafficapi/
     sectionTrafficRouteDirection`), which answers a request without a key with `인증키값이 없습니다`; the file datasets (e.g. 148 "구간 교통량",
     5/15/60 min, from 2010) need `goLoginCheck()` and five declarations (소속, 지역, 성별, 나이, 활용목적) before download. **Needs an API key
     or a portal login that I do not hold.** Not created and not guessed. No data read.
   * **Source 2.** `safekorea.go.kr` (국민안전24) has a public 재난문자 list with date/region filters, but its date picker offers only the last 7
     days (`startDate: "-7d"`); I did not send dates outside it without the user's say-so. The history route is the `data.go.kr` OpenAPI
     "행정안전부_긴급재난문자" (usage application / service key). No county publishes a file. No data read.
   * **Source 3, GK-2A.** NMSC's download link points to `data.kma.go.kr` (not allowed; login). Not attempted. Sentinel-2 stands as the satellite record.
   * **Source 4 rule (frozen now).** Data = table rows of the two PDFs (downloaded from `nvlpubs.nist.gov`), parsed by text, never digitised from
     figures: (a) TN 2135 Table 33 (19 burnovers: id, place, time); (b) TN 2135 progression tables 11-32: each row's date and start time, and its
     table title (area/road); (c) TN 2252 per-road traffic tables 18-28: rows (time range, description). **Comparison, not involving the model's
     inputs:** for each road named in both reports, F = earliest 11/8 row time of that road's TN 2135 table(s); C = earliest TN 2252 row whose text
     matches `clos(ed|ure)|blocked|impassable` and a fire word (`fire|burn|flame|smoke|BO`); B = Table 33 burnover time(s) on that road. Reported:
     C − F and B − F per road (minutes, window starts, ±15-30 min resolution), n roads, every matched row listed. This measures the lag between
     recorded fire at a road and recorded closure, i.e. the roadlayer's assumption that a cell closes when the fire reaches it; it is **not** a
     run of `product/wfg-roadlayer`. **The Paradise run is not made:** the tables give times at named places, not an arrival field, no polygon
     dataset was found (the reports say the tables are "excerpted and condensed from the full dataset"; the NIST data portal search returned 0
     records), and the repository has no Paradise road graph, places or shelters in `wfg_roadlayer` format. Interpolating a field would be my
     reconstruction, not "the true progression". Stated, not done.

4. **2026-11-18 ~23:20 UTC, before any 재난문자 time was compared with any model value or REPORTED time.** The user supplied
   `ccf78023-…20261014.csv` (62,192 rows, 재난문자생성일시 2023-10-23 … 2026-10-14, SHA-256 `6545d26f…ea344`; the same bytes were uploaded
   twice). What was looked at: the 312 messages for 22-27 March 2025 whose 수신지역명 names 의성군, 안동시, 청송군, 영양군 or 영덕군, or
   경상북도 전체 (extracted to `inputs/jaenan_munja_5counties_20250322_27.csv`), and the text of the 21 영덕군 messages. Records only, no model
   value. Provenance (which portal) was not stated by the user; structure and hash verified, authenticity not independently verified.
   * **Send time = 재난문자생성일시** (the record's own creation time; 등록일 follows it by about 20-30 s; handset delivery time is not in the file).
   * **Replacement rule for the REPORTED rows of `research/kcf-roadcut/validation_table.csv`** (RD1-RD13, VA1-VA3, EV1-EV13). A row is replaced by
     an official time only if a candidate exists: official messages whose 수신지역명 contains the row's county, created within **±6 h** of the
     REPORTED time, whose text contains (EV rows) `대피` and, if the row names a town or village, that name; (RD rows) `통제|차단|통행금지|통행제한`
     and a route or place keyword of the row (황장재, 국도34호선, 서산영덕선, 중앙선, 911호선, 화매리, 도계 …); (VA3) the text time itself. The official time
     is the **earliest** candidate; every candidate is listed. No candidate → the row stays REPORTED. Same-section official messages **outside**
     the ±6 h window are listed as context and never replace a row.
   * **Recomputation.** RD rows with a model time: error = model − official (minutes); "closed at issue" rows: bound = issue time − official.
     EV rows: the published value "order − median T_road" is shifted by (official − reported); if the shift moves the order across the issue
     hour used, the row is flagged "not recomputed". No other number is changed; the model values are those already published.
   * Also reported (context, no model): the first official `대피` message per county in the window.
5. **2026-11-18 ~23:20 UTC, before any KEC volume was compared with anything.** The user supplied six KEC files named `.zip` that are gzip
   (`TCS_67_04_01_*.csv`, cp949; one per day 22-27 March; SHA-256 prefixes in `inputs/kec_tcs_daily_SOURCE.txt`), plus one **0-byte** monthly
   ZIP that was not used. They are dataset 512 "구간단면 교통량(TCS) (전노선)": **daily** volume per section, direction and TCS vehicle class.
   **They cannot give closure times or outbound surges (15-minute resolution was asked for); only whole-day volumes.** The route in the file is named
   `당진상주선` (route 030); I identify it with the news name 서산영덕선 by its interchanges (동상주, 서의성, 안동JC, 북의성, 동안동, 청송, 동청송영양, 영덕):
   an identification from names, stated. Disclosure: while listing section names I printed the 25 March class-1 volumes of those sections, so I have
   seen a few volumes before this rule. **Rule (descriptive only, no pass/fail prediction):** V(section, direction, day) = sum over classes; baseline
   B = mean of V(22 Mar) and V(23 Mar) (the days before the earliest closure record, 24 Mar 17:02; the fire had started on 22 Mar 11:25, 22 is a
   Saturday and 23 a Sunday: **a weekend baseline, possibly already affected**); r = V/B. Groups: G1 route 030 between 북의성 and 영덕 (both directions;
   official closure text 24 Mar 17:02); G2 route 030 between 동상주 and 북의성 (REPORTED closures 25 Mar 15:30-22:00); G3 route 055 중앙선 의성→예천
   sections (REPORTED closures 25 Mar 17:00-18:00 and 26 Mar 07:55); G0 control: route 055 군위/가산JC sections, route 045, route 301, route 030 west of 동상주.
   Reported: V, r per section-direction-day, group medians of r, next to the closure statements. Classes for reading only: r < 0.15, 0.15-0.60, ≥ 0.60.
   A better baseline (weekdays 17-21 March) can be downloaded from the same portal page; not supplied.

6. **2026-11-18 ~23:21 UTC (commit 367e375), after the first run of `jaenan_compare.py` printed candidate times and after I listed the highway-related and
   whole-county official messages (records only), before any recomputed model error was viewed** (the `*_new` columns were written to
   `out/jaenan_replacement.csv` but not opened). The first run showed that amendment 4's rule was too loose or too narrow in four places; each is
   fixed here, and the first run's output is kept in git history (commit before this amendment's code change):
   * **Region.** The expressway closures were broadcast by 한국도로공사 as messages to **경상북도 전체**, which the county rule excluded (RD1-RD8 found
     nothing). RD rows now accept 경상북도 전체 messages as well as the row's counties.
   * **Names and times.** The official route names are `서산영덕선` and, on 22-23 March, `청주영덕선`; the road messages state an **effective time**
     ("금일 15:30부로"). Official time for an RD row = the stated effective time (message date + HH:MM) if present, else the creation time. A
     candidate must be a closure (text has `차단|통제|통행금지|통행제한`, not `재개`), name the row's route and at least one interchange of the row's
     section (RD1 안동JC|청송IC; RD2 서의성IC|영덕; RD3 의성IC|서안동|남안동; RD4 의성IC|예천IC; RD5/RD6 동상주IC|영덕; RD7 의성IC|풍기IC; RD8 의성IC|예천IC),
     and have its official time within ±6 h of the REPORTED time. Earliest candidate wins; all are listed.
   * **Whole-county EV rows** ("whole county" in the row) were matched to village-level and a dam-release message. Now the candidate must be a
     county-specific message that addresses everyone (`전 ?(시민|군민)|모든 .{0,6}군민|군민께서는|전지역|전 지역`) and contains `대피` and a fire word
     (`산불|화재|확산`). All EV candidates must contain a fire word.
   * **RD12** keyword `영양` matched the signature "[영양군]"; keyword is now `도계` only (RD9: 911호선|화매리|황장리; RD10: 황장재; RD11: 국도34호선;
     RD13: 국도7호선|지경삼거리, unchanged otherwise).
   Also reported (context, no model): the official timeline of every 한국도로공사 expressway closure and reopening message of 22-27 March, as
   `out/kec_official_closure_events.csv`, parsed by regex from the 312 messages (effective time as stated; "created time" where none is stated).

7. **2026-11-18 ~23:23 UTC, after the amendment-6 run (kept as `out/jaenan_replacement_amend6_run.csv`) printed its official times, before any recomputed model
   error was viewed.** Reading the candidates showed three defects of amendment 6; fixed, with the reason:
   * The fire-word requirement was meant for whole-county rows (it excluded a dam-release notice). Applied to all EV rows it made EV3 and EV7 choose the 18:26
     황장재 road-ban text over the 18:21 지품면·달산면 evacuation message (which has no fire word). **Fire word is now required for whole-county rows only.**
   * The interchange token `영덕` matched the route name 서산영덕선 (RD2, RD5 matched a 안동JC~청송IC closure). Tokens are now `영덕IC` and `영덕TG`.
   * "Earliest candidate" let a looser section beat the exact one (RD7 chose the 18:00 의성IC~예천IC closure over the 21:26 의성IC~풍기IC closure). **Specificity
     first:** a candidate naming both ends of the row's section (RD1 안동JC+청송IC; RD2 서의성IC+영덕IC|TG; RD3 의성IC+서안동|남안동; RD4 의성IC+예천IC; RD5/RD6 동상주IC+영덕IC|TG;
     RD7 의성IC+풍기IC; RD8 의성IC+예천IC) beats one naming a single end; ties → earliest official time. Window ±6 h unchanged.

8. **2026-11-18 ~23:26 UTC, after the third-pass results.** Clerical (and the times first written for amendments 6-8, 23:40, 23:55 and "00:20 on 19 Nov", were estimates and are corrected here to the commit/clock times above): §5's sentence "the count of replaced rows is 0" is superseded by amendments 4, 6 and 7:
   **23 of the 29 REPORTED rows** carry an official 재난문자 time (RESULTS.md rows 2a-2c); 6 stay REPORTED. Nothing else in §1-§5 changes.

9. **2026-11-18 ~23:5x UTC (user asked for the Paradise run; before any Paradise graph, field or comparison was built).** What was read: Overture release
   2026-10-21.0 *schema and counts only* for the bbox lon −121.95…−121.45, lat 39.65…39.95 (22,094 transportation segments; 8,503 places), the class
   histogram of the segments, and `product/wfg-roadlayer`'s `RoadModel`/`engine` code. Facts that shape the rule: the CLI's raster reader hard-codes EPSG:5179
   (Korean TM), so a Paradise raster cannot go through `roadlayer run`; the **engine** (vendored F-3.1 `deadline_field`, `engine.build_instance/run_passes`)
   and `RoadModel` are generic. The Paradise run therefore calls those directly from `research/kcf-validate/paradise/`, with no change to the product.
   * **Road graph (ASSUMED, fixed now).** Overture segments, subtype road, classes motorway, trunk, primary, secondary, tertiary, unclassified, residential,
     living_street (no service, track, path, footway). Present-day network as a proxy for 2018 (rebuilt since; stated). All roads two-way (no one-way data
     used). Free-flow speeds, km/h: motorway 100, trunk 80, primary 70, secondary 60, tertiary 50, unclassified 40, residential 30, living_street 15; no congestion.
     CRS EPSG:32610, grid 375 m (the replay's cell size) over the bbox; nodes = Overture connectors; one directed edge pair per segment piece between consecutive
     connectors; `travel_ticks = max(1, ceil(length_m / speed_m_per_s))`; forbidden turns = U-turn (edge to its reverse).
   * **Fire field = a reconstruction from records, not NIST's own map.** Observations O = rows of TN 2135 fire-progression tables 11-32 (date, start time,
     Location column text) whose Location geocodes to a point on the Overture road network (rule: "X and/at/near Y" → the point where the two named roads
     come closest, ≤ 150 m; a single road + a named place → the named Overture place within 300 m; otherwise not geocoded). Times: minutes after 2018-11-08 00:00
     PST. Field: thin-plate-spline RBF (`scipy.interpolate.RBFInterpolator`, smoothing 1.0 min², K = all observations) of arrival time at the 375 m cell centres;
     a cell is "not reached" if farther than 2 km from every observation; arrival is capped to be ≥ the earliest observation time and monotone repair is NOT applied.
     Leave-one-out error of the field is reported. Coverage (rows geocoded / rows) is reported, not hidden.
   * **Closure and run (as roadlayer).** A cell closes at its arrival second after the issue time T (ceil), for the rest of the horizon (no reopening); H = 8 h; the
     engine builds the instance exactly as `engine.build_instance`; origins = residential-road intersections (connectors with ≥ 2 residential/tertiary segments) thinned to
     ≥ 750 m spacing inside the observation hull ∪ 2 km; shelters = Overture places of basic_category in {school, hospital, community_center/place_of_worship, emergency
     shelter} outside the field's reached area at all issue times and within the bbox (the replay's k = 3 nearest by straight line, distinct entry nodes). Issue times
     T = 07:30, 08:00, 08:30, 09:00 PST on 8 Nov 2018 (all reported; none dropped).
   * **Comparison with the record (frozen).** Records R = (a) TN 2135 Table 33 burnovers (19: place, time) and (b) TN 2252 per-road closure rows (the 15 matched in
     amendment 3) whose place geocodes by the same rule. Model value at a record = the field's arrival time at the road cell(s) of that point (min over cells within 150 m).
     Error = model − record (minutes; negative = model earlier). Reported: n geocoded of n, median and quartiles of the error, count within ±30 and ±60 min, misses
     (record exists, cell "not reached"). Also reported: per-origin last safe departure (engine) as a distribution, with no record to compare. **Leakage stated:**
     the field's observations and the records come from the same NIST dataset, so agreement is a consistency check of "closure at arrival" plus the interpolation, not an
     independent validation; leave-one-out error of the field is the measure of the interpolation alone.

10. **2026-11-18 ~23:58 UTC, after `extract_nist_locations.py` recovered 392 progression rows with their Location text (word positions of the PDF), before any
    geocoding or field.** Two additions to amendment 9's geocoding rule, nothing else: (a) "X **between** Y and Z" → the midpoint of the two points where X comes
    closest to Y and to Z (each ≤ 150 m), else not geocoded; (b) name matching normalises street types on both sides (road→rd, lane→ln, drive→dr, court→ct, circle→cir,
    avenue→ave, street→st, boulevard→blvd, highway→hwy, place→pl, trail→trl, way→way) and case, strips source tokens such as `PPD-02,`, and takes a road name from the text
    only if it equals a normalised Overture primary name; texts with more than two names and no "between" use the first two names in reading order. Rows with only one
    road name and no place, or none, are not geocoded.

11. **2026-11-19 ~00:05 UTC, after the first geocoding run (coverage: progression 255 of 392, burnovers 5 of 19, traffic rows 71 of 132; no field and no comparison built),
    before the second.** The first run's output showed two defects, fixed here: (a) road names must be **distinct** (a road mentioned twice counted as two names and sent the
    "between" rule to the road's own geometry; the 12:00 Clark Rd closure row landed near the airport); (b) the TN 2252 closure rows are multi-clause narrative, so a closure
    row is geocoded on **its first sentence that contains `clos|block|impass`** (not on the whole row). Everything else in amendments 9-10 is unchanged. Burnover rows with one
    road name only (Hoffman Rd, Concow Rd, Chapman Ln, Windermere Ln, Pentz Rd, Pearson Rd, Bille Rd, Wagstaff Rd, Coutolenc Rd, Chestnut Cir, Ponderosa Way, Rattlesnake Flats Rd,
    Jordan Hill Rd/Granite Hill Rd, Concow Fire Station 37) stay not geocoded: the record gives no position along the road.

12. **2026-11-19 ~00:18 UTC, after the one Paradise run (17 min, 4 workers; no re-run, no tuning), recording what the code did where amendments 9-11 left room.** Not rule changes:
    * Shelters: Overture places whose `basic_category` contains `school`, `hospital`, `place_of_worship`, `community` or `shelter` (this also admits "social_or_community_service"), snapped to a graph node
      within 500 m, outside the field's reached area, one per entry node: 322 shelters. Origins: graph nodes with ≥ 3 incident edges, ≥ 2 of them residential or tertiary, inside the Delaunay hull of the
      observations or within 2 km of one, thinned greedily in node-id order to ≥ 750 m spacing: 147 origins. Waiting allowed at origin and shelter nodes only; dwell 120 s (roadlayer default).
    * Field: 132 unique-location observations (50 m rounding, earliest time kept) from 255 geocoded rows, 10 of them dated 9 Nov (time = minutes after 2018-11-08 00:00 PST, up to 11/9 07:20).
    * Record semantics (read before the comparison, not used to choose anything): burnover times are initiations; the TN 2252 closure rows state that a road **is closed or blocked at that time**, so they bound
      the closure onset from above and negative errors (model earlier) are expected for them. The graph file (14 MB, sha256 in `out/paradise/graph_sha256.txt`) is not committed; `build_graph.py` rebuilds it
      from the Overture segments (release 2026-10-21.0).

13. **2026-11-19 ~00:29 UTC, user supplied KEC dataset 148 (15-minute VDS volumes, March 2025); before any closure onset, reopening or surge was derived.** What was looked at: the header and first rows,
    that all 31 days × 96 slots are present, 14 % of readings are −1 (missing), conzone IDs per route (route 0300: 33, 0550: 62), and, to place conzones on named sections, the **daily**
    VDS sums against the daily TCS section totals of 22-27 Mar (a mapping check; no slot-level value, onset or surge was looked at). The file has no conzone names.
    * **Mapping (frozen).** Conzones are aligned to TCS sections by order within route and direction (ascending conzone ID ↔ ascending TCS 순번 for S, descending for E) at the offset that
      maximises the mean daily-total correlation; a conzone is **accepted** only if its Pearson r with the aligned TCS section over the six days is ≥ 0.85 and the median VDS/TCS ratio is within 0.5-2.0.
      **Result:** route 0550 (중앙선): accepted for the 군위-의성-안동JC-남안동-서안동-예천-영주-풍기 sections in both directions (r 0.89-1.00). Route 0300 (서산영덕선, named 당진상주선 in TCS): **not
      mapped** (negative r for several conzones, repeated TCS section numbers); nothing is derived for it until a conzone reference table (KEC dataset "콘존") is supplied.
    * **Volume** V(conzone, slot) = sum over lane types of readings ≥ 0; a slot with only −1 is missing. Baseline B(slot) = median of V at the same slot of day over 1-21 March (before the fire);
      a slot is informative if B ≥ 15 vehicles per 15 min.
    * **Closure run** = ≥ 4 consecutive informative slots with 0 ≤ V ≤ max(2, 0.05·B); a missing slot breaks a run. **Onset** = start of the first slot of the first run on or after 22 Mar 00:00;
      **reopening** = start of the first slot after the run with V ≥ 0.25·B. Times KST. A conzone with no such run has no derived closure.
    * **Surge** per conzone and direction = max of V/B over the six hours before the onset (before the official time where no onset exists); reported as a ratio, no threshold. Both directions are reported;
      which one is "outbound" is not assumed.
    * **Comparison (frozen).** (a) With the official events of `out/kec_official_closure_events.csv` for 중앙선: for each event, the conzones of the sections it names (의성IC~남안동JC: 의성→안동JC,
      안동JC→남안동; 의성IC~안동JC: 의성→안동JC; 의성IC~예천IC: + 남안동→서안동, 서안동→예천; 의성IC~풍기IC: + 예천→영주, 영주→풍기; 풍기IC~영주IC: 영주→풍기), both directions;
      error = derived onset (or reopening) − official effective time, per conzone-direction, summarised by median and range with n; events with no stated effective time (26 Mar 10:00, created time) are
      flagged. (b) With the model: for the published RD3, RD4, RD7, RD8 values ("closed at issue" at hour Ti), bound = Ti − derived onset of the section's conzones (negative: the model's
      closure precedes the volume drop by at least that much). The REPORTED/official times of those rows are as in amendments 4-7. Records and volume come from different systems; neither is "truth".

14. **2026-11-19 ~00:32 UTC, after the one run of `vds_closures.py` (rule of amendment 13 unchanged).** The first run's runs table showed that only 6 of the 12 mapped conzones had a closure run, and the ones nearest 의성 had none; I then looked at
    their slot values (e.g., 의성→안동JC at 282-303 vehicles per 15 min right after the official 18:00 closure) and added an **exploratory** table of median V/B in four windows
    (`vds_diagnostic.py`, `out/vds/vds_diagnostic_V_over_B.csv`). Result: the conzones mapped to 서안동→예천, 예천→영주 and 영주→풍기 fall to 1-3 % of baseline after 25 Mar 18:00 (both directions); those mapped to 의성→안동JC and
    안동JC→남안동 stay at 0.7-1.2 (25 Mar evening) and 0.5-0.75 (26-27 Mar daytime). **No mapping or detection rule was changed after seeing this** (it would be circular to tune the mapping to the official times); the
    section identity of the conzones is reported as **uncertain** until a conzone reference table (KEC dataset 157 "콘존": 콘존ID, 콘존명, start/end node) is supplied.

15. **2026-11-19 ~10:12 UTC, user supplied KEC dataset 157 (conzone reference table; six identical copies), before any closure onset was re-derived.** Reading the table showed that amendment 13's **TCS-correlation mapping was wrong**:
    e.g. `0550CZS160` is "군위JC-가산IC" (I had it as 의성→안동JC), `0550CZE180` is "의성IC-안동JC" (I had it as 예천→서안동). The conzone names are now authoritative; **amendment 13's mapping rule is
    withdrawn**, its detection rule is unchanged, and rows 1a-1c of the previous RESULTS.md (including the "inconsistency" I reported in amendment 14, which came from the mislabelled conzones) are superseded.
    Only the table's names were read (route 0300: E130-E290/S130-S290 with names; route 0550 likewise); no slot value, onset or surge was re-derived before this rule.
    * **Chain and base names.** For a route, the E conzones in 노선구성순번 order define a chain of nodes (A1, A2=B1, ...); a node's **base name** drops a trailing IC, JCT, JC, TG, Hi or 분기점 (so 남안동JCT = 남안동IC, 안동분기점 = 안동JC,
      영덕TG = 영덕IC). Conzones with 종점 or 시점 in the name are excluded. A conzone (either direction) covers the node interval of its two base names.
    * **Official sections.** An official event "route A~B" (route 서산영덕선 or 청주영덕선 → 0300, 중앙선 → 0550; other routes ignored) selects every conzone, both directions, whose interval lies inside [A, B] on that route's chain.
      Events with a stated effective time use it; events with only a creation time (22 Mar 20:38, 26 Mar 10:00, 10:31) are flagged. Detection (closure run, onset, reopening, baseline from 1-21 March, informative slots, surge) is exactly amendment 13's.
    * **Comparison (a):** for each official closure or reopening event, per selected conzone-direction, the derived onset (closure) or reopening time within ±6 h of the official time; error = derived − official (min); median, range, n with a time, n without. Night-time events with
      an uninformative baseline are reported as not testable. **(b) Model bounds:** for the published RD1-RD8 rows, the row's own section (RD1 안동JC~청송IC, RD2 서의성IC~영덕IC, RD3 의성IC~서안동IC, RD4 의성IC~예천IC, RD5 and RD6 동상주IC~영덕IC, RD7 의성IC~풍기IC,
      RD8 의성IC~예천IC) with reference time = the official time of amendments 6-7 (RD1 15:30, RD2 15:58, RD3 18:00, RD4 18:00, RD7 21:26, RD8 26 Mar 10:00) or, where no official match exists, the REPORTED time (RD5 18:00, RD6 22:00); onset window ±12 h; bound = published issue hour (RD1 14:00, RD2 16:00,
      RD3 16:00, RD4 17:00, RD5 17:00, RD6 21:00, RD7 21:00, RD8 26 Mar 00:00) − median onset. **(c) Controls:** all other conzone-directions of routes 0300 and 0550, reported as the share with any closure run in 22-27 March.
