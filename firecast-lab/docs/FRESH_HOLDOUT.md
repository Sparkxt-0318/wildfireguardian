# Fresh holdout: a truth source for 2025 US fires (proposal)

Written 2026-11-01 on the cloud host for `program/DECISIONS.md` (2026-11-01, item 8). This is a proposal only. Nothing was
downloaded, no 2025 fire data was opened, and `SPLITS.json` is unchanged. Every choice here waits for Siyeong (§5). The
Korean 2026 part of `fresh_holdout` is not covered.

Revised 2026-11-01 after the batch-1 review (findings D3-D6; main changes say "batch-1 review"): MTBS counts and faster
extent products (§2, §2.5, §3.1, §3.6, §4); every amendment of the frozen membership rule, with E4 flagged as
outcome-based (§3.3, §3.6, §5); no download of a release that also holds 2026 surveys before the owner's OSF registration
(§3.1, §3.3-§3.6, §5); FTP folder names vary by geographic area (§2.1, §3.4, §3.6). Still a proposal: nothing was
downloaded and `SPLITS.json` is unchanged.

**How claims are marked**
- `[R: path:line]`: checked in this repository (paths from the repo root).
- `[Wn]`: read in a WebSearch result summary on 2026-11-01 (URLs in §6). WebFetch failed on the three hosts tried
  (data.mendeley.com, www.fs.usda.gov, ftp.wildfire.gov do not resolve from this session), so no page was read in full.
  Re-check these on the Mac.
- `[G]`: general knowledge, not checked here. `[A]`: my assumption or estimate.

## Summary

| Role | Proposed source | Independent of c651's training labels? | Independent of NIROPS? |
|---|---|---|---|
| Timing truth (headline) | NIROPS nightly airborne-infrared survey perimeters, 2025 | yes | (it is NIROPS) |
| Extent truth (scoring domain) | Final burned perimeter: MTBS, else RAVG, else BAER/BARC, else WFIGS final | yes | yes, except WFIGS |
| Cross-check (QA and a labelled secondary score) | FIRMS VIIRS 375 m detections as arrival maps; NASA FEDS 12-hourly perimeters | **no** | yes |

- A web search found no NIROPS compilation with 2025 surveys. The only one returned is v1 (2020-2024) [W1]. The fallback is to
  harvest the 2025 "IR" folders of the NIFC FTP, where v1 itself came from [R: forecast/data/sources/nirops_95rj5d379g_v1/
  publisher_snapshot.json, field `method`]. That is scraping, so it needs Siyeong's approval (ground rule 7).
- Cohort size: probably tens of fires under the rules of §3.3, but only a handful if the cohort must look like the catalog's
  29 large US fires. Both numbers are estimates, not counts.

## 1. What a fresh-holdout truth source must provide

| Need | Why | Test |
|---|---|---|
| Timing | Headline lead 24 h, 12 h diagnostic only [R: firecast-lab/docs/DATA_NOTES.md:16]. US windows are consecutive survey pairs of 20-28 h; continuity pairs (0, 48] h [R: firecast-lab/SPLITS.json `window_rule`] | UTC times good to an hour or two; at least one 20-28 h pair per fire |
| Extent | Headline domain = final perimeter + 3 km. Outside the mapped extent is `0`; never-mapped is unknown, not unburned [R: firecast-lab/METRICS.md:24-57] | a final perimeter per fire |
| Independence | c651's labels are Choi et al. arrival maps kriged from VIIRS 375 m (S-NPP VNP14IMG, NOAA-20 VJ114IMG, NOAA-21 VJ214IMG) plus GOES ABI fire points [R: DATA_NOTES.md:136; forecast/documents/wildfire_references.bib:296-353]. Truth from those products shares the detection latency and pixel footprint the model learned to reproduce [A] | different sensor or process |
| Stacks | c651 reads 2 m temperature, 10 m wind u/v, slope, tree cover and biome on a 375 m grid [R: forecast/documents/wildfire_methods.tex:799-814] | inputs complete at every cutoff |
| Number | Under 10 US fires made the forecast-v2 blind test exploratory [R: forecast/documents/preregistration_blind_test.md:135-137] | at least 10 fires |
| Terms | Open for research use with attribution; raw data never committed (ground rule 7) | licence known |

**Can the stacks be built on the Mac?** Probably, with new code. Every input covers 2025 or is static: Open-Meteo's archive has
hourly IFS 9 km from 2017 [W36]; terrain, land cover 2019, canopy 2019 and biome are static [R: wildfire_methods.tex:439-453].
The frozen builder cannot run unchanged on a fire without a Choi raster, though:
- every stage reads its grid from the reconstruction raster: `grid()` opens `arrival_path`
  [R: forecast/wildfire/environment.py:97-99], called by weather, land cover, terrain, canopy, gridMET and LANDFIRE
  (`environment.py:242, 435, 451, 521, 546, 583`);
- its data root is fixed inside `forecast/` [R: forecast/wildfire/paths.py:11-12], part of the frozen release (ground rule 1);
- `validate` checks files against the Choi deposit [R: environment.py:611-617, 657-658].

A thin wrapper in `firecast-lab/` must supply the 2025 grids and redirect the root, importing the stages, never copying them.
This is untested. gridMET and LANDFIRE, which c651 does not read, cover CONUS only [G]. I did not check whether the LANDFIRE
2016 service the builder calls is still online [A].

## 2. Candidates

| Candidate | Measures | Cadence | Resolution | 2025 status | Terms | Indep. of labels / of NIROPS |
|---|---|---|---|---|---|---|
| NIROPS IR perimeters | timing + extent | nightly, on flown fires | airborne, vector [G] | no compilation found [W1]; FTP folders likely online [W5, A] | v1 CC BY 4.0 [R]; FTP files US federal [G] | yes / - |
| WFIGS / NIFS perimeters | extent; timing only via the NIFS archive | irregular, about daily on large fires [G] | vector, mixed methods [W14] | perimeters since 2021 [W9]; 2025 NIFS export not seen [W13] | public, no login [W16]; no explicit licence seen [W9] | mostly / no |
| FIRMS VIIRS 375 m | timing (active burning) | 2 clusters of passes a day [G] | 375 m at nadir, larger off nadir [W19] | archived; NRT replaced by standard data after months [W18] | NASA open, acknowledgement asked [W20] | **no** / yes |
| NASA FEDS | timing + extent | 12 h | from 375 m VIIRS | NRT layer holds the current year only [W21]; 2025 archive unconfirmed [A] | NASA, credit line [W21] | **no** / yes |
| GOES-R ABI fire (FDC) | timing, coarse | 5-10 min [W38, W25] | 2 km nominal, larger in the West [W24, W26] | GOES-19 operational East from 2025-04-07 [W25] | NOAA open data [W24] | **no** / yes |
| MTBS, RAVG, BAER, own dNBR | final extent only | once | 10-30 m [G] | MTBS: at least 21 fires of 2025 by 2026-05-27 (16 on 2026-04-07, 5 on 2026-05-27) [W39, W27], re-count at the freeze; Provisional IA for large fires 3-6 weeks after containment [W40]; RAVG 30-45 days after containment [W29] | US government [G]; Sentinel-2 free with attribution [W31] | yes / yes |

### 2.1 NIROPS nightly IR perimeters (2025)
- **What.** Heat perimeters digitized by infrared interpreters from airborne thermal imagery [R: publisher_snapshot.json
  `description`; W8], flown mostly at night [G].
- **Cadence.** On the six US-2024 test fires: median spacing 24.0-26.2 h; 195 of 324 pairs at 20-28 h; 273 at most 48 h
  [R: DATA_NOTES.md:53-58].
- **2025.** The program runs (its 2026 FAQ says maps are posted on ftp.wildfire.gov) [W6]. Per-incident `IR/<YYYYMMDD>`
  folders are common [W4, W5, W42], but season and archive folder names vary by geographic area (batch-1 review): pacific_nw
  moves old seasons to `Z_<year>_HISTORIC` [W5], n_rockies to `Historic_archived NIROPS/<year>_fires/<year>_<Name>/IR/<YYYYMMDD>/`
  [W42]; southwest keeps `GACC_Incidents/<year>/` and great_basin `pre2015-great_basin_w/<year>/` [W43]. Older seasons stay
  online in several areas, so the 2025 folders likely remain [A]; see §3.6 risk 1 for a 2022 purge notice. v1's script is
  meant for "future dataset updates" [R: publisher_snapshot.json `description`]. A related USFS dataset, RDS-2025-0054
  (reconciled daily growth of Fires of Unusual Size, partly from NIROPS), covers 2020-2023 only [W2].
- **Independence.** Airborne infrared with manual interpretation: independent of the VIIRS and GOES detections behind the
  labels [R: DATA_NOTES.md:116-147]. c651 saw NIROPS only as the US training mask, on other fires [R: DATA_NOTES.md:142-145].
- **Biases.** Flown fires are moderate to large, and surveys start after ignition [R: publisher_snapshot.json]. Flights follow
  incident requests; some go unfilled (150 in 2019) [W7]. A heat perimeter is not a burn perimeter. v1 estimated missing times
  and did not flag them [R: forecast/data/sources/nirops_95rj5d379g_v1/provenance.json `timestamp_caveat`]. In older guidance,
  FTP folders are named by the morning-briefing date, not the flight date [W3], so a naive harvest misdates surveys by up to a
  day [A]. Some nights cover only part of a fire [A].
- **Access.** A NIROPS release with 2025 surveys, if one appears. Otherwise the v1 code (`NIROPS_Code.zip`, 19.5 KB
  [R: forecast/data/sources/nirops_95rj5d379g_v1/files.json]) run on the 2025 folders only.
- **Plug-in.** The planned US truth: survey rings go to `decision.truth_from_perimeters`, then `hazard_contract.from_perimeters`
  (`envelope`, K = 1, all-touched, horizon = endpoint survey) [R: firecast-lab/src/firecast_lab/decision.py:350-367]. Cell labels
  follow METRICS §1. Nothing is interpolated between surveys [R: METRICS.md:54-57].

### 2.2 NIFC / WFIGS interagency perimeters
- **Public layers.** WFIGS keeps "the most current or most authoritative shape": certified perimeters and those captured since
  2021, with no fall-off rules [W9]. A year-to-date service exists [W10]. This gives a final (or latest) extent, not a
  progression; that it holds exactly one shape per incident is my reading [A]. The Interagency Fire Perimeter History holds the
  final or last daily perimeter, through 2024 in the copies seen [W11].
- **Timing.** Every NIFS edit is archived and exported once a year to the NIFC Open Data site [W12]. Mirrors show exports for
  2018-2022 only [W13]. Edits carry `PolygonDateTime` (UTC), `FeatureCategory` (e.g. "Wildfire Daily Fire Perimeter",
  "IR Heat Perimeter") and `MapMethod` [W14, W15].
- **Independence.** Many daily perimeters are drawn from the night's infrared map, so they are not independent of NIROPS [A].
- **Biases.** Edit time is not observation time unless `PolygonDateTime` is right; smoothing and lag; mixed methods.
- **Access.** ArcGIS REST queries by year, state or IRWIN id; the NIFS annual export, if published.
- **Plug-in.** Last fallback for the extent truth. Incident metadata for eligibility: IRWIN id, discovery time, final acres
  (e.g. `attr_FinalAcresReported` [W37]). The 2025 daily edits, if exported, as a second timing check filtered by `MapMethod`.

### 2.3 VIIRS-derived progression (FIRMS detections, NASA FEDS)
- **FIRMS.** Active-fire points with acquisition times: S-NPP since 2012-01-20, NOAA-20 since 2018-04-01, NOAA-21 since
  2024-01-17, as CSV, SHP or JSON by e-mailed request [W18]. The three satellites pass close together (one example: 17:53, 18:45
  and 19:06 UTC) [W17], near 01:30 and 13:30 local [G], so an arrival map dates a cell to about 12 h. The pixel grows toward the
  edge of the 3,060 km swath [W19].
- **FEDS.** 12-hourly perimeters and active fronts from 375 m VIIRS; events over 4 km²; CONUS, Alaska and Canada. Sensors are
  listed as S-NPP + NOAA-20 or NOAA-20 alone; latency about 4 h or 9-12 h. NASA says it is coarser and less accurate than airborne
  perimeters, may merge or split agency fires, and underestimates under cloud or smoke [W21]. Method: Chen et al. 2022 [W22].
  Final perimeters agree with CAL FIRE's FRAP at mean IoU 0.83, as reported by the GOFER paper [W23]. Access: the ArcGIS
  service [W21]; an OpenVEDA features API was named in a search result but not confirmed [A].
- **Independence.** Not independent of the training labels: the same VIIRS products [R: wildfire_references.bib:296-330].
  Independent of NIROPS.
- **Biases.** Misses under cloud or thick smoke, and low-intensity or brief burning between passes. First detection lags arrival
  by up to a revisit gap. Large off-nadir pixels inflate extent [W19, W21].
- **Plug-in.** Masks `arrival <= t` at each pass, or FEDS polygons, as a perimeter series in `from_perimeters` (`envelope`).
  Cells inside the extent truth that were never detected are unknown, not unburned.

### 2.4 GOES-R ABI fire detections
- A 2 km nominal fire mask with temperature, area and FRP, CONUS and full disk [W24]; CONUS every 5 min in a 2019 briefing
  [W38], every 10 min in an Earth Engine listing [W25]. Pixels grow off nadir (about 2.4 x 3.2 km over Kansas from GOES-16), and
  detection degrades with view angle, which is large in the West [W26]. GOES-19 replaced GOES-16 as operational East on
  2025-04-07 [W25]: a sensor change inside the season.
- Access: NOAA's open buckets on AWS [W24]. Not independent: geostationary points are in the labels [R: DATA_NOTES.md:136].
  At most an "active between surveys" flag. GOFER's hourly GOES perimeters cover 28 California fires of 2019-2021, none of
  2025 [W23].

### 2.5 Final-extent products (extent only)
- **MTBS:** Landsat-based perimeters and severity for fires of at least 1,000 acres in the West (500 in the East); some fires are
  not mapped when imagery fails [W28]. It typically releases data 6-12 months after a fire [W40] and maps the 2023-2025 seasons
  side by side [W39]. The 2026-04-07 release added 16 fires of 2025 [W39] and the 2026-05-27 release 5 more [W27], so at least
  21 were out by 2026-05-27. The 2026-07-15 release (315 fires from several seasons) had no season breakdown in the summaries
  seen [W39], and later releases were not checked: re-count at the freeze. (Batch-1 review: this said "about a year" and gave
  only the 5 fires of 2026-05-27.)
- **Faster extent for large 2025 fires (batch-1 review):** the USGS Provisional IA (provisional initial assessment) posts
  burn-severity maps 3-6 weeks after containment for fires reported over 40,000 acres or judged significant, seasons 2020-2025;
  from 2026 such fires get MTBS initial assessments instead [W40]. MTBS's own initial assessments use the first post-fire
  imagery (grass and low-biomass shrub fires), while its extended assessments wait for the next growing season (forests)
  [W41], so initial assessments can come out sooner [A].
- **RAVG:** forested National Forest fires, typically 30-45 days after containment, with a perimeter shapefile [W29].
- **BAER/BARC:** preliminary dNBR maps from Landsat and Sentinel-2 with analyst-set thresholds [W30].
- **Own dNBR:** Sentinel-2 (free; "Contains modified Copernicus Sentinel data") [W31] or Landsat [G]. Large downloads.
- **California:** CAL FIRE's perimeter layer lists 516 fires of the 2025 season [W32].
- Optical reflectance change: independent of VIIRS, GOES and NIROPS [G]. Analysts may consult agency perimeters [A].
- **Access:** the MTBS and RAVG download pages [W27, W29]. **Plug-in:** a polygon for the domain (final perimeter + 3 km). It
  never supplies a time.

### 2.6 Other sources
- **MODIS MCD64A1:** 500 m daily burn date, independent of the label detections, listed to mid-2025 [W33]. Day-level timing is too
  coarse for 24 h windows, and Terra and Aqua are drifting toward end of life [W33].
- **FIRIS** (California airborne infrared): a public perimeter view exists [W34]; a timed archive was not confirmed.
- **Commercial imagery** (Planet and others): licences restrict sharing [A]. Not considered.

## 3. Recommendation

### 3.1 Choice
1. **Timing truth: NIROPS 2025.** Use the first public NIROPS release with 2025 surveys if one appears by a fixed deadline
   (proposed: 2027-03-31). Otherwise harvest the 2025 IR folders with the v1 code. Reasons: independent of the label detections;
   the same instrument and processing as the US test truth, so scores compare; nightly cadence fits the 24 h lead. Fallback
   without scraping: the 2025 NIFS export filtered to infrared perimeters, if it is published [W12, A].
   **2026 guard (batch-1 review).** If the first release with 2025 surveys also contains 2026 surveys (judged from its title,
   description and file list only), it is not downloaded until the owner's OSF registration of the blind test is confirmed,
   unless the publisher offers per-year files (then only the 2025 file is taken). Until then: the 2025 FTP harvest, if
   approved (§5 item 2), or wait (§5 item 9). US 2026 is reserved with "no access before the owner's OSF registration"
   [R: SPLITS.json `splits.fresh_holdout.not_included.us_2026`]. The blind test uses the first public release with 2026
   surveys and is blocked for good if that release "is already accessible or inspected before external registration"
   [R: preregistration_blind_test.md:92-93, 104-106]; registration had not happened by 2026-10-30
   [R: docs/NEXT_PLAN.md:203]. v1 shipped the perimeters of all five seasons as one shapefile in one zip [R: files.json;
   publisher_snapshot.json], so a bundled 2026 part could not be left unopened.
2. **Extent truth: final burned perimeter,** the first available at the freeze among MTBS (else the USGS Provisional IA
   for a large fire [W40]; batch-1 review), RAVG and BAER/BARC, then the WFIGS final perimeter (flagged "not independent
   of NIROPS"). The source used is recorded per fire.
3. **Cross-check: FIRMS VIIRS arrival maps (FEDS for convenience).** Independent of NIROPS, not of the labels. Two uses only:
   (a) pre-declared QA flags, such as survey dates more than 12 h from the VIIRS timing or a wrong incident match, reported as
   counts; (b) a labelled secondary score, "satellite truth". The gap between a model's skill against NIROPS and against VIIRS
   shows how much it gains from sharing the labels' sensor. Never a headline score; never used to select fires.

### 3.2 How the fresh windows are built
- **Windows:** consecutive survey pairs of 20-28 h (headline), and every pair in (0, 48] h as the continuity diagnostic
  [R: SPLITS.json `window_rule`]. Longer gaps are not scored: the envelope keeps every newly burned cell burning for the whole
  gap [R: METRICS.md:260], so over a long gap most crossings become hits.
- **Cutoff state (decision needed).** Track A builds cutoff states from the Choi reconstruction
  [R: firecast-lab/src/firecast_lab/data.py:14-16], which does not exist for 2025. Proposal: the cumulative NIROPS union at the
  cutoff survey, at cell centres (the label rule), with ages from survey times. forecast-v2 used survey unions this way
  [R: preregistration_blind_test.md:103, 112]. The state itself has no hindsight leak (the grid still does, as everywhere),
  but it is not the input c651 trained on, so fresh scores do not compare directly with US test scores.
- **Domain:** (NIROPS final union ∪ extent truth) + 3 km, clipped to the grid.
- **Burned at an unknown time (decision needed).** Cells inside the extent truth but never inside a NIROPS union take the existing
  `unknown` state [R: METRICS.md:57]: left out of cell scores, unsupported in truth sets (so `unresolved`). Sensitivity row: the
  US-test convention, where they count as `0`. Counts are reported per fire.
- **Grid:** EPSG:5070 at 375 m, covering the extent truth and the NIROPS final union plus 5 km (the 3 km ring plus 1.5 km for a
  9x9 context), so the ring is never clipped. US test grids have only 2 km [R: DATA_NOTES.md:194].
- **Decision metric:** truth sets as in §2.1. US road graphs must be built from OSM on the Mac, from a pre-ignition snapshot
  like the Korean graphs [R: firecast-lab/README.md:110-112].

### 3.3 Eligibility rules (fixed before any 2025 file is opened)
- **E1** In the timing truth of §3.1, USFS Regions 1-6 as in v1 [R: publisher_snapshot.json], wildfires only.
- **E2** First published survey in 2025 (UTC) and discovery in 2025. Surveys after 2025-12-31 are dropped unopened. In a
  release, "unopened" is possible only with per-year files; a release that bundles 2026 surveys waits (§3.1 item 1; batch-1
  review).
- **E3** The publisher's rule (at least three collection days, one consecutive daily pair) and at least one 20-28 h pair, as in
  the current `us_2025_membership_rule` [R: SPLITS.json].
- **E4** Final reported size of at least 1,000 acres, from incident metadata, never from perimeters. This is MTBS's western
  threshold, so an independent extent can exist; it is about 29 cells of 375 m [A]. **E4 is an outcome-based exclusion**
  (batch-1 review): final size is the fire's cumulative growth. Neither the frozen rule, which fixes membership "never by
  looking at outcomes" [R: SPLITS.json `splits.fresh_holdout.us_2025_membership_rule`], nor the forecast-v2 preregistration
  [R: preregistration_blind_test.md:92-110] has a size threshold. Non-outcome alternative: no size threshold; keep every
  fire and record which extent source exists (as §3.4 step 4 does).
- **E5** c651's six inputs (which include the baselines' slope and wind) present on the whole grid at every cutoff, judged
  from input availability only.
- **E6** Recorded, not excluded: overlap with catalog fires or 2020-2024 scars (fuels are the 2019 epoch
  [R: DATA_NOTES.md:256-258]), complexes, estimated timestamps.
- Fires leave only by these rules, windows only by the timing rules: never by growth measured on perimeters or by any model
  output. E4 is the only size rule, and it selects on an outcome (above; §5 item 3).

**How many might qualify.** v1 holds 737 incidents over five seasons [R: publisher_snapshot.json], about 150 a season [A]. 2025
burned about 5.1 million acres nationally, 43% less than 2024 [W35], so fewer fires may have been flown [A]. Under E1-E5 my guess
is 30-80 fires [A], above the 10-fire bar; more without E4 [A]. The catalog's US fires are much larger (at least 1,062 burned
cells, about 37,000 acres) and number 3-13 a season, 29 over four seasons [R: SPLITS.json `fires`]. A cohort like that might
give 3-6 fires in 2025 [A], below the bar.

### 3.4 Freezing the list before any scoring (ground rule 5)
1. Siyeong decides on this proposal (§5), recorded in DECISIONS.md. No 2025 file is touched before that.
2. Write and test on SYNTHETIC fixtures: the harvester (2025 allow-list, listing-only dry run, every URL logged), the loader,
   the eligibility checker, the grid builder and the stack wrapper. Record the commit. The allow-list and the listing pass
   match on the year and on `IR` folders, not on one area's folder names, which vary (§2.1; batch-1 review).
3. Mac, listing pass: file count and bytes of the 2025 IR folders; over 1 GB goes to Siyeong. No 2026 folder is ever listed or
   opened: US 2026 is reserved for the forecast-v2 blind test, which inspection would block
   [R: SPLITS.json `splits.fresh_holdout.not_included.us_2026`; preregistration_blind_test.md:104-106]. On the release path,
   only the release's title, description and file list are read first; a release that also holds 2026 surveys stops here
   unless it offers per-year files (§3.1 item 1; batch-1 review).
4. Mac, download and manifest: SHA-256 per file; per incident the IRWIN id, region, UTC survey times (estimated ones flagged),
   final acres, which extent source exists, and input availability. No plots and no geometry statistics beyond validity checks.
5. Run E1-E5 on the manifest: a candidate list with every incident and the rule it failed.
6. Siyeong reviews names, counts and reasons (no perimeters) and approves.
7. Only then, one commit writes `fresh_holdout.fires`, the rule text, the manifest hash and the harvester commit into
   SPLITS.json, with a DECISIONS.md entry. `locked` stays true. The list never changes again: later failures are reported as
   exclusions, never replaced.
8. Truth and inputs are then built by the frozen code, hashed, and left unread until a final claim that Siyeong approves.

### 3.5 What to download on the Mac (after approval)

| Item | Approx. size | Terms | Approval needed |
|---|---|---|---|
| v1 code, `NIROPS_Code.zip` (Mendeley 10.17632/95rj5d379g.1) | 19.5 KB [R: files.json] | CC BY 4.0 [R: provenance.json] | no |
| NIROPS 2025 perimeters and IR logs: a release (before the owner's OSF registration only one without 2026 surveys, or its 2025 file; §3.1 item 1), or FTP 2025 IR folders (vector files and logs only) | unknown. v1's five seasons are 1.39 GB zipped [R: files.json]; one season of vectors is likely well under 1 GB, imagery far more [A] | release: likely CC BY 4.0 [A]; FTP: US federal [G] | **yes: scraping**; over 1 GB too |
| WFIGS 2025 perimeters and incident attributes (REST queries) | tens of MB [A] | public, no login [W16]; no explicit licence [W9] | no |
| NIFS 2025 annual export (optional) | unknown; every national edit, may pass 1 GB [A] | as WFIGS | if over 1 GB |
| MTBS, RAVG, BAER perimeters of eligible fires | under 100 MB of vectors [A] | US government [G] | no |
| FIRMS VIIRS 375 m, 2025, western states, three satellites | 100-500 MB of CSV, less if clipped to fires [A] | NASA open; acknowledgement [W20] | no |
| FEDS 2025 perimeters (optional) | under 100 MB [A] | NASA; credit line [W21] | no |
| Environment stacks (same sources as the catalog [R: wildfire_methods.tex:439-453]) | unknown; time and size one fire first; 30-80 fires may pass 1 GB [A] | as the existing stacks; Open-Meteo says CC BY 4.0, but a forum comment says IFS 9 km needs an ECMWF licence [W36] | likely, in total |
| OSM road graphs, pre-ignition snapshots | small [A] | ODbL, keep attribution [R: firecast-lab/CLAUDE.md rule 7] | no |
| GOES FDC or Sentinel-2/Landsat scenes (only if needed) | several GB per fire [A] | open [W24, W31] | yes |

### 3.6 Open risks
1. No 2025 NIROPS release: the harvest is scraping, the FTP layout can change and differs by area (§2.1), and survey times may
   have to be rebuilt from briefing-date folders (older guidance [W3]; a 2021 naming file is listed but was not read [W45]),
   local times and missing times. Search summaries (batch-1 review) say the site is for short-term sharing, not a file
   archive, and that a 2022 notice announced a purge of files unchanged for 5 or more years [W44]; summaries also mentioned
   a move of the incident folders from /public to /protected, which a follow-up search did not confirm. Check both on the
   Mac before §5 item 2.
2. Opening any 2026 file by accident would block the forecast-v2 blind test [R: preregistration_blind_test.md:104-106]. A
   release that bundles 2026 with 2025 has no separate 2026 file: downloading it is the access (§3.1 item 1; batch-1 review).
3. Selection: NIROPS flies requested, mostly large fires after ignition [R: publisher_snapshot.json; W7]. Results hold for that
   population only.
4. Late or patchy extent truth: MTBS had released at least 21 fires of 2025 by 2026-05-27 [W39, W27] (later releases not
   counted; batch-1 review), the Provisional IA covers only fires over 40,000 acres or judged significant [W40], RAVG covers
   forested National Forest fires only [W29], and the WFIGS fallback is not independent of NIROPS.
5. Cutoff states from NIROPS unions differ from c651's training inputs; record it next to every fresh score.
6. The stack wrapper is new code; fuels are the 2019 epoch [R: DATA_NOTES.md:256-258]; LANDFIRE 2016 availability is unchecked.
7. Weather stays archived IFS repeated from the cutoff [R: DATA_NOTES.md:19]; its licence wording is unresolved [W36].
8. Cohort size depends mostly on E4 and on whether it is kept (§3.3, §5 item 3).
9. Whoever runs the harvest sees the fires. The manifest stays metadata-only and the QA flags are declared in advance.

## 4. Limits of the recommended sources
- **NIROPS 2025 (timing).** Requested, mostly large fires, surveyed after ignition. Gaps from unfilled requests and bad nights.
  A heat perimeter, not a burn perimeter. Partial nights. Estimated or briefing-date times. Interpretation varies between
  interpreters [A]. No coverage footprint, so `0` means outside the mapped extent, never unburned
  [R: preregistration_blind_test.md:132-133]. About a day of timing ambiguity between surveys, so false-safe is an upper bound with
  respect to timing [R: METRICS.md:266-267].
- **Final-extent truth.** No timing. Definitions differ (dNBR thresholds versus agency perimeters; unburned islands kept or
  filled) [A]. MTBS typically lags 6-12 months, the USGS Provisional IA 3-6 weeks for large fires only [W40]; RAVG is forest-only
  [W29]; BARC is preliminary [W30]; the WFIGS fallback mixes methods and often comes from NIROPS itself.
- **VIIRS / FEDS (cross-check).** Not independent of c651's labels. Dates cells to about 12 h. Misses under cloud, thick smoke
  and low intensity; off-nadir pixels inflate extent [W19]. FEDS is experimental and may merge or split fires [W21]; a 2025 FEDS
  archive is unconfirmed.

## 5. Decisions for Siyeong
1. The three sources (§3.1), the 2027-03-31 deadline, and an amended `us_2025_membership_rule`. Every amendment of the frozen
   rule [R: SPLITS.json `splits.fresh_holdout.us_2025_membership_rule`] (listed by the batch-1 review; this item named only
   the FTP harvest):
   - source: the FTP harvest of the 2025 IR folders, or the NIFS fallback of §3.1 item 1, if no release with 2025 surveys
     appears by the deadline (the frozen rule names only "the first NIROPS release covering 2025");
   - E1: wildfires only (the publisher's own scope);
   - E2: a 2025 incident has its first published survey (UTC) and its discovery in 2025; surveys after 2025-12-31 are dropped
     unopened;
   - E4: final reported size of at least 1,000 acres, an outcome-based exclusion (item 3);
   - E5: c651's six inputs present on the whole grid at every cutoff (as in the preregistration's six-channel rule
     [R: preregistration_blind_test.md:99-103]);
   - the 2026 guard of item 9.
   Regions 1-6 and E3 are in the frozen rule already.
2. Permission to scrape the NIFC FTP: 2025 IR folders only, listing pass first.
3. Rule E4, an outcome-based exclusion (final size is cumulative growth; §3.3): 1,000 acres; a larger threshold for a
   catalog-like cohort (fewer fires); or no size threshold, the non-outcome option (keep every fire and record which extent
   source exists; batch-1 review). And Regions 1-6 only.
4. Cutoff state for fresh windows: the NIROPS union at the cutoff survey.
5. "Burned at an unknown time" cells as unknown, with the `0` convention as a sensitivity row.
6. The 5 km grid margin.
7. Downloads over 1 GB (environment stacks in total; any GOES or Sentinel-2 pulls).
8. Whether US 2023 NIROPS fires should also become a fresh set now [R: DATA_NOTES.md:286-287].
9. The 2026 guard (§3.1 item 1; batch-1 review): a public NIROPS release with 2025 surveys that also contains 2026 surveys is
   not downloaded until the owner's OSF registration is confirmed, unless the publisher offers per-year files. Until then,
   the FTP harvest (item 2) or waiting [R: SPLITS.json `splits.fresh_holdout.not_included.us_2026`;
   preregistration_blind_test.md:92-93, 104-106].

## 6. Sources (all accessed 2026-11-01, through WebSearch result summaries; pages not opened)
- W1 NIROPS v1, Mendeley (only v1 returned): https://data.mendeley.com/datasets/95rj5d379g
- W2 USFS RDS-2025-0054, Fires of Unusual Size 2020-2023: https://www.fs.usda.gov/rds/archive/catalog/RDS-2025-0054
- W3 NIROPS IR product naming conventions: https://ftp.wildfire.gov/public/nirops/AC3_Admin/Sharepoint_document_review/IR_product_naming_conventions.pdf
- W4 2024 Pioneer IR log: https://ftp.wildfire.gov/public/incident_specific_data/pacific_nw/2024_Incidents_Washington/2024_Pioneer_WASES000173/IR/20240703/20240703_Pioneer_IR_Log.pdf
- W5 2022 folder under Z_2022_HISTORIC: https://ftp.wildfire.gov/public/incident_specific_data/pacific_nw/Z_2022_HISTORIC/2022_Incidents_Oregon/2022_Potter_ORWIF220170/IR/20220827/20220827_Potter_IRIN_Daily_Log.pdf
- W6 2026 IAA and NIROPS FAQs: https://gacc.nifc.gov/oscc/docs/2026/2026_IAA-and-NIROPS_FAQs.pdf
- W7 2019 NIROPS national summary: https://fsapps.nwcg.gov/nirops/docs/upload/2019_NIROPS_National_Summary.pdf
- W8 Infrared interpreter position description: https://www-nwcg.fs2c.usda.gov/positions/infrared-interpreter/incident-position-description
- W9 WFIGS Interagency Fire Perimeters metadata (copy): https://www.datacommons.psu.edu/metadata/WFIGS%20Interagency%20Fire%20Perimeters-metadata.html
- W10 WFIGS year-to-date service: https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0
- W11 Interagency Fire Perimeter History (copy): https://data.amerigeoss.org/dataset/interagencyfireperimeterhistory-all-years-view
- W12 NWCG PMS 936, NIFS archive: https://www-nwcg.fs2c.usda.gov/publications/pms936/national-incident-feature-services/archive
- W13 Operational Data Archive mirrors (2018-2022): https://wifire-data.sdsc.edu/dataset/operational-data-archive-2022
- W14 NWCG Event Polygon standard and an example schema: https://www.nwcg.gov/sites/default/files/data-standards/pdf/NWCGWildlandFireEventPolygon.pdf ; https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/Arapaho_Roosevelt_National_Forest_Closure/FeatureServer/5
- W15 IRIN guide to NIFS perimeters: https://ftp.wildfire.gov/public/nirops/Documents/Obtaining_Current_Fire_Perimeters_from_NIFS_in_AGOL_for_IRINs.pdf
- W16 NWCG PMS 936, public distribution: https://nwcg.gov/publications/pms936/national-incident-feature-services/public-distribution
- W17 FIRMS, NOAA-21 detections available: https://wiki.earthdata.nasa.gov/spaces/FIRMS/blog/2024/02/08/343475617/NOAA-21+VIIRS+Active+Fire+Detection+Data+Now+Available
- W18 FIRMS Archive Download: https://firms.modaps.eosdis.nasa.gov/download/
- W19 VIIRS C2 375 m active fire user guide v1.2: https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf ; Schroeder et al. 2014: https://doi.org/10.1016/j.rse.2013.12.008
- W20 FIRMS terms and acknowledgement: https://www.earthdata.nasa.gov/learn/find-data/near-real-time/firms
- W21 FEDS NRT perimeter service: https://gis.earthdata.nasa.gov/image/rest/services/FireTracking/Fire_Events_Data_Suite_Fire_Perimeters_NRT/MapServer/0
- W22 Chen et al. 2022, Sci. Data 9:249: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9151742/
- W23 GOFER, Liu et al. 2024, ESSD 16:1395: https://essd.copernicus.org/articles/16/1395/2024/
- W24 NOAA GOES-R FDC catalog entry: https://catalog.data.gov/dataset/noaa-goes-r-series-advanced-baseline-imager-abi-level-2-fire-hot-spot-characterization-fdc
- W25 GOES-19 FDCC, Earth Engine: https://developers.google.com/earth-engine/datasets/catalog/NOAA_GOES_19_FDCC
- W26 GOES fire quick guide; pixel size example: https://cimss.ssec.wisc.edu/goes/OCLOFactSheetPDFs/QuickGuide_GOESR_FireHotSpot_v2.pdf ; https://rammb2.cira.colostate.edu/?p=19234
- W27 MTBS quarterly release, 2026-05-27: https://mtbs.gov/articles/announcement/mtbs-2023-2024-2025-fire-quarterly-release-may-27-2026
- W28 MTBS product description: https://catalog.data.gov/dataset/monitoring-trends-in-burn-severity-ver-12-0-april-2025
- W29 RAVG: https://burnseverity.cr.usgs.gov/ravg
- W30 BARC for BAER teams: https://digitalcommons.unl.edu/usdafsfacpub/220 ; https://data.usgs.gov/datacatalog/data/USGS:62e28516d34e394b65364cd6
- W31 Copernicus Sentinel data licence: https://ads.atmosphere.copernicus.eu/licences/ec-sentinel
- W32 CAL FIRE 2025 perimeters layer: https://ferix.water.ca.gov/arcgis/rest/services/FERIX/Fire_History/MapServer/12
- W33 MODIS MCD64A1 v061; Terra/Aqua end of life: https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD64A1 ; https://gofcgold.org/sites/default/files/2024-11/Giglio_GOFC_2024_NASA_Fire.pdf
- W34 CA perimeters CAL FIRE NIFC FIRIS public view: https://lab.data.ca.gov/dataset/ca-perimeters-cal-fire-nifc-firis-public-view
- W35 2025 US area burned: https://usafacts.org/articles/how-much-damage-do-wildfires-do-in-the-us
- W36 Open-Meteo historical API; licence comment: https://open-meteo.com/en/docs/historical-weather-api ; https://openmeteo.substack.com/p/ecmwf-ifs-upgraded-to-025-resolution/comments
- W37 WFIGS 2023 perimeters to date (field list): https://wifire-data.sdsc.edu/dataset/wfigs-2023-interagency-fire-perimeters-to-date
- W38 NOAA GOES fire status briefing, 2019: https://fsapps.nwcg.gov/nirops/docs/upload/3_3_Schmidt_TFRSAC_29May2019.pdf
- W39-W45 were added by the batch-1 review, also from WebSearch result summaries on 2026-11-01 (mtbs.gov does not resolve from
  this session either).
- W39 MTBS releases: 2026-04-07 (645 fires: 2023 482, 2024 147, 2025 16); the announcements list (2026-07-15: 315 fires from
  several seasons; 2023-2025 mapped side by side): https://mtbs.gov/articles/announcement/mtbs-2023-2024-2025-fire-quarterly-release-april-7-2026 ; https://www.mtbs.gov/announcements
- W40 USGS Provisional IA (3-6 weeks after containment; over 40,000 acres or significant; seasons 2020-2025; MTBS typically 6-12
  months): https://burnseverity.cr.usgs.gov/products/provisionalIA
- W41 MTBS initial and extended assessments: https://mtbs.gov/faq/fire-mapping
- W42 n_rockies archived IR folder, 2016: https://ftp.wildfire.gov/public/incident_specific_data/n_rockies/Historic_archived%20NIROPS/2016_fires/2016_JohnDoe/IR/20160901/20160901_JohnDoe_IR_Map_topo_11x17_land.pdf
- W43 southwest and great_basin season folders: https://ftp.wildfire.gov/public/incident_specific_data/southwest/GACC_Incidents/2018/ ; https://ftp.wildfire.gov/public/incident_specific_data/great_basin/pre2015-great_basin_w/2013/Bison/products/July_09_2013/
- W44 ftp.wildfire.gov root page and notices: https://ftp.wildfire.gov
- W45 NIROPS end-product folder listing "IR product naming conventions 2021.pdf": https://ftp.wildfire.gov/public/nirops/End_Product_vendors
