# Roads direction, data requirements

**Status: written 2026-09-16 by A3, revised the same day against A1's acquisition
round. Nothing here has been downloaded by A3.** Every entry is keyed to an id in
`research/data/REGISTRY.yaml`, which A3 reads and does not edit. Where this
direction needs something that has no registry entry, it is flagged as a gap for
A1 rather than invented here.

The companion document is `research/roads/PREREGISTRATION.md`; section numbers
below refer to it.

---

## 0. The standing blocker

**All six data API keys are unset in this sandbox.** `DATA_GO_KR_KEY`,
`KMA_APIHUB_KEY`, `VWORLD_KEY`, `FIRMS_MAP_KEY`, `EARTHDATA_TOKEN` and
`COPERNICUS_USER` with `COPERNICUS_PASS` are all missing, which is human gate
WJ-001 on `research/TASKBOARD.md`. Nothing behind a key can be fetched, including
Sentinel-2 and the active-fire archive, which are the two datasets the labels are
made of. Until WJ-001 clears, this direction can write design and code and
nothing else.

Two further access routes are now blocked and are a human gate, **WJ-011**,
reported by A1: the NGII national base map and the NGII 5 m DEM both returned HTTP
400 on two automated attempts, so their access terms are unconfirmed.

The orthoimagery that the width covariate depends on is **WJ-009**, and the
suppression records of section 12.4 are **WJ-010**.

---

## 1. Summary table

Priority is this direction's, not the program's. **Critical** means the design
cannot produce its primary output without it.

| id | priority | what it is for | status as A1 left it |
|---|---|---|---|
| `sentinel2_l2a_dnbr` | critical | the label itself, section 5 | pending, behind WJ-001 |
| `firms_active_fire_korea` | critical | arrival, timing, spread rate, intensity, spots | pending, behind WJ-001 |
| `kfs_forest_roads` | critical | the road barrier layer | resolved: data.go.kr id 3045621, SHP, no usage restriction. **No width attribute** |
| high-resolution pre-fire orthoimagery | critical | **the width covariate itself** | **no registry entry. This is the gap that matters most** |
| `dem_korea` | critical | slope, ridges, spread geometry | NGII 5 m blocked. Copernicus GLO-30 confirmed, behind registration and WJ-001 |
| `kfs_forest_type_map` | high | lee-side fuel class, fuel load for intensity | pending |
| `base_map_linear_features` | high | rivers | NGII blocked, OpenStreetMap Geofabrik confirmed, ODbL 1.0 |
| `kma_asos_aws` | medium | weather at the hour of arrival | pending, behind WJ-001 |
| `kfs_fire_state_history_csv` | medium | containment time for scene selection | pending, coverage unknown |
| `kfs_fire_stats_csv` | low | cross-check of fire dates | verified, **2022 to 2025 only** |
| `vworld_geocoder` | low | address to coordinate for cross-checks | pending, behind WJ-001 |
| suppression resource placement | not held | the confound of section 12.4 | **no registry entry, and obtaining it is an information-disclosure request** |

---

## 2. The critical four, one at a time

### 2.1 `sentinel2_l2a_dnbr`

**What the design needs.** A pre-fire and a post-fire L2A scene pair per fire,
covering the whole burn plus a 2 km margin, satisfying the windows of section 5.2
(post scene at or after containment and within 30 days of it, pre scene within 60
days before ignition). Bands B8A and B12 for NBR, and the scene classification
layer for the usable-pixel rule. Reprojected to EPSG:5186 per decision D-005.

**What it is for.** Everything. It is the label (section 5.5), the arrival
evidence (section 4.1), the burned mask that the attribution test walks (section
5.6) and the spot patches of the ember arm (section 7.3).

**If it does not arrive.** The direction does not exist. There is no label.

**Fallback.** Microsoft Planetary Computer hosts Sentinel-2 L2A without a
Copernicus account, which is already noted as the provider alternative in the
registry entry. If the Copernicus credential of WJ-001 does not arrive, the
Planetary Computer route is the fallback and A1 should confirm it. A Landsat 8 and
9 fallback exists at 30 m, and it would be a real degradation: at 30 m the 10 m to
50 m analysis band of section 5.3 is one pixel per side, which is not enough to
compute a burned fraction, so the buffer geometry would have to be rewritten and
the segment length raised. That is a version bump, not a substitution.

**Known risk that is not an access risk.** Cloud and smoke. The post-fire scene is
taken as early as possible and Korean spring fires smoulder, so `CLOUD` is
expected to be the largest single indeterminate category. The count is a reported
result (section 10.5) and not a footnote.

### 2.2 `firms_active_fire_korea`

**What the design needs.** The full VIIRS active-fire archive over each fire's
bounding box and active window, with acquisition timestamp, platform, confidence,
and the scan and track dimensions where the product carries them. Suomi NPP and
NOAA-20 for all five fires, NOAA-21 additionally for the 2025 fires. MODIS is
requested as well, as the one sensor with a uniform record across 2019 to 2025,
for the common-cadence run of section 2.3.

**What it is for.** Arrival (section 4.3), the arrival-time surface and therefore
approach angle and rate of spread (section 6.4), the intensity covariate (section
6.6), spot timing (section 7.3) and the cadence covariate (section 2.3).

**If it does not arrive.** No encounter can be timed, condition C4 fails
everywhere, and every segment is `TIMING` indeterminate. The direction stops.

**Fallback.** The archive is downloadable from the FIRMS archive download page
without an API key, as a manual request. That is a human action, so it becomes a
human-gate item if WJ-001 stalls.

**Carried caveat, from the registry and from the brief.** 375 m fire radiative
power saturates at intense fronts, which is where the interesting encounters are.
Fire radiative power is therefore not an intensity covariate anywhere in this
design. Section 6.6 says what is used instead: Byram intensity from the detection
derived rate of spread and a pre-fire fuel load, plus detection persistence as an
ordinal proxy.

### 2.3 `kfs_forest_roads`, and the width problem

**What A1 confirmed.** data.go.kr id 3045621, SHP, no usage restriction, and
**the width attribute is confirmed absent**. This is a finding, not a worry.

**What the design needs from the file anyway.** Geometry, and three attributes it
may or may not have:

1. a **road class** field (간선임도, 지선임도, 작업임도), which would supply the
   class-level width prior of section 6.3.5 for segments the automatic extraction
   fails on;
2. a **construction or survey year**, which is what lets section 3.1 exclude roads
   built after a fire. Without it, a road built in 2023 would be scored as a
   barrier that was present at Uljin in 2022, and the segment would be labelled
   `held` for the excellent reason that it did not exist;
3. the **coordinate reference system** of the SHP, to reproject to EPSG:5186.

Item 2 is the one A3 would most like an answer on, and it is not about width.

**If the file does not arrive.** Roads fall back to the OpenStreetMap
`highway=track` and `highway=unclassified` classes inside forest land cover. That
is a poor substitute: OpenStreetMap track coverage in Korean mountain forest is
uneven and it carries no forest road class at all, so the barrier layer would be
of unknown completeness and the ineligible counts of section 4.5 would become
uninterpretable.

**The consequence of the missing width attribute, which is the main point of this
document.** See section 3 below. It is large enough to have its own section.

### 2.4 `dem_korea`, at 30 m rather than 5 m

**What A1 confirmed.** NGII 5 m is blocked by HTTP 400, the same failure as the
base map, so it is a human gate. Copernicus GLO-30 is available under a free
licence, with a DOI citation required and registration required, so it is still
behind WJ-001.

**What the design needs.** A single-provider DEM covering all five fires. The
registry already carries the rule that two DEM providers are never mosaicked
(`docs/HANDOFF_ROUND3.md` section 5 rule 17), and this direction keeps it: one
provider for all five fires, or the fires that use a different one are reported
separately and never pooled.

**What it is for.** The signed slope covariate, the ridge barrier class, and
nothing else. In particular it is **not** used for the approach angle.

**What 30 m costs, in three separate currencies.** Section 6.7 of the
pre-registration is the full treatment. In brief:

- **approach angle: nothing.** The angle is the barrier vector bearing against the
  detection-derived spread direction. Neither input is terrain. This is worth
  saying because a 30 m DEM sounds like it should ruin the geometry, and it does
  not touch it;
- **signed slope: it becomes a hillslope quantity.** A 3 by 3 gradient window at 30
  m posting measures slope over about 90 m, so the covariate is redefined as the
  hillslope gradient in the direction of spread over the windward 90 m, and is
  reported under that name rather than as "the slope at the road". The smoothing
  attenuates the slope coefficient in the same direction that measurement error
  attenuates the width coefficient;
- **ridges: the class becomes incomplete and skewed.** The smallest reliably
  detected ridge spacing at 30 m posting is near 90 m, so narrow secondary spurs
  are missed, and those are exactly the small ridges a front crosses easily. The
  retained ridge sample is therefore biased toward large ridges, which are the ones
  most likely to have held. Every ridge result is reported as describing detectable
  ridges only.

**Fallback.** SRTM 30 m or ALOS AW3D30, both open, both 30 m, so neither improves
anything. The only meaningful upgrade is NGII 5 m, which is a human gate.

---

## 3. The width covariate, which now has no source at all

This is the section A1's finding forces, and it is the one A6 should read hardest.

### 3.1 What is missing

The claim under test is about a width. The road layer has no width. There is no
second Korean road dataset in the registry that carries one. So the primary
covariate of the primary hypothesis has to be **created by measurement**, and its
quality is a design parameter rather than an inherited property of a file.

### 3.2 The primary path

Pre-registration section 6.3.2: a semi-automatic extraction of the canopy gap from
**pre-fire high-resolution orthoimagery**, five perpendicular transects per 100 m
segment, median across transects, for every segment; plus a hand-measured
stratified subsample used to estimate the automatic method's bias and error.

### 3.3 The dependency this creates, which has no registry entry

**High-resolution pre-fire orthoimagery for Korea, with per-tile vintage, is not
in `research/data/REGISTRY.yaml`.** It is now the most load-bearing undelivered
input in the direction, more so than any of the entries that do have ids.

What is needed of it:

1. resolution fine enough to measure a gap of a few metres, which means about 50 cm
   or better;
2. **a vintage that predates each fire**, and a per-tile vintage that can be read
   programmatically, because section 6.3.5 carries the imagery-to-fire gap as a
   covariate and runs a sensitivity analysis on it;
3. terms that permit programmatic tile access and derived measurements.

The candidate A3 would put first is the VWorld orthoimagery service, since
`vworld_geocoder` already establishes that the program expects a VWorld key under
WJ-001, and the 국토정보플랫폼 archive is the candidate for historical vintages.
**A3 has verified neither.** This is a request to A1 for a registry entry, not an
assertion that either will work.

### 3.4 What it costs the design, stated quantitatively

Classical measurement error in a covariate attenuates its slope toward zero by
about `kappa = sigma_x^2 / (sigma_x^2 + sigma_u^2)`, where `sigma_x` is the true
width spread in the sample and `sigma_u` is the measurement error standard
deviation.

**The direction of that bias is the bad one.** It pushes the width slope toward
zero, which pushes the study toward reporting that width does not matter, which is
precisely the conclusion F1 in section 1.5 exists to detect. An uncorrected
analysis would be biased toward its own most quotable negative finding, and that
is not a risk this design is willing to carry silently.

It gets worse in combination with section 11.2 of the pre-registration. Korean
forest roads have little width variation to begin with, so `sigma_x` is small, and
a small `sigma_x` is exactly the condition under which a given `sigma_u` does the
most damage. The two problems multiply rather than add.

### 3.5 What is done about it

1. **An errors-in-variables term inside the Bayesian model** (section 6.3.4). The
   true width is latent, the observed measurement carries an estimated bias and an
   estimated error standard deviation, and both are estimated jointly from the
   hand-measured subsample in the same fit. The reported width posterior is
   disattenuated, with honestly wider intervals, and the naive posterior is
   published beside it so the size of the correction is visible.
2. **`kappa` is a headline diagnostic**, reported with its interval next to the
   breach curve.
3. **Gate M1** (section 11.3): if `kappa` falls below 0.70, or fewer than 60
   hand-measured segments support the error model, no breach curve against width is
   published at all, and the outcome is written as **not resolvable at the achieved
   measurement precision**. That sentence is not a synonym for "width does not
   matter" and the pre-registration says so explicitly.
4. **F1 is judged only on the errors-in-variables posterior**, never on the naive
   one.
5. **A pre-registered reading rule for a flat curve**, pre-registration section
   11.5. A flat curve is what a true null and a badly measured covariate both
   produce, so the discrimination between them is fixed before the fit and rests on
   five instruments, three of which (the repeat study, the design-stage
   recoverability simulation, and the measurement validity checks) run before any
   label is computed. A flat curve is reported as an **informative null** only when
   all four conditions of section 11.5.6 hold; otherwise the outcome is **not
   resolvable at the achieved measurement precision**.

### 3.6 How many hand-measured segments are needed

**At least 60**, and the arithmetic is in pre-registration section 6.3.3:
estimating `sigma_u` to within about 10 per cent relative needs about 50 paired
differences, and detecting a systematic bias of 0.4 `sigma_u` at 80 per cent power
needs about 49. Sixty covers both with a margin.

They are drawn 4 per cell from a 5 by 3 stratification of fire complex by
automatic-width tercile, so the error is estimated across the whole width range
rather than only where roads are typical. **At least 30 of the 60** get a second
independent measurement pass, giving 30 repeat pairs from which the error variance
is estimated directly. Thirty is A6's number, adopted over an earlier 20: it gives
`sigma_u` to about 13 per cent relative against about 16 per cent at 20, and it is
where the error estimate stops being the weakest link in the attenuation
correction. Segments are presented in randomised order with the burn footprint and
the label withheld.

**The repeat study is not contingent on anything.** It runs on pre-fire imagery
and can be completed before a single label exists, which is what makes instruments
1 and 2 of pre-registration section 11.5 available at design stage rather than
after the fit.

Sixty segments at a few minutes each is a few hours of work, which is inside scope
rule 2 (computation and public data only, no field work). None of it requires
anyone to visit a road.

---

## 4. The supporting inputs

### 4.1 `kfs_forest_type_map`

**Needed for.** The lee-side fuel class covariate, the fuel-discordance flag of
section 5.4, and the fuel load `w` in the Byram intensity of section 6.6. It has to
be the **pre-fire** edition, and the edition year is the thing to verify.

**If it does not arrive.** Fuel class falls back to the Ministry of Environment
land cover map at its forest classes, which distinguishes coniferous, broadleaf and
mixed but not stand age or density, so the intensity fuel load loses most of its
resolution and enters as a wide class prior. The fuel-discordance flag survives in
weakened form.

**Note on the claims rules.** This covariate is a categorical contrast with
non-stocked forest as the reference level. No comparative statement about conifer
against broadleaf behaviour is made anywhere in this direction, which keeps it
clear of the landslide direction's `RC-004` territory as well as being the honest
thing to do.

### 4.2 `base_map_linear_features`

**What A1 confirmed.** NGII returned HTTP 400 twice and is a human gate. The
OpenStreetMap Geofabrik South Korea extract is confirmed working, under ODbL 1.0,
current.

**What the design does.** Plans on OpenStreetMap for rivers. The ODbL attribution
obligation is recorded and carried into any published output.

**What that costs.** OpenStreetMap hydrography completeness in Korean mountain
catchments is uneven and channel polygons are sparse, so most rivers arrive as
centrelines and their width is measured from imagery exactly as road width is,
inheriting section 3 in full. A completeness audit against the DEM-derived channel
network at a matched flow-accumulation threshold is pre-registered before
labelling, and the audit is reported.

**Ridges are not in either source.** They are DEM-derived, the derivation is
documented in pre-registration sections 3.1 and 6.7, and the script and its
thresholds are committed before labelling.

### 4.3 `kma_asos_aws`

**Needed for.** Wind speed, relative humidity and temperature at the hour of
arrival, which are the covariates that stop the model attributing to width what was
actually a humid night.

**If it does not arrive.** These covariates are dropped, and the pre-registration
says so in advance: the specification without them is the G2 reduced specification
of section 11.3. Dropping them weakens the design in a known direction, since a
fire that stopped at a road at 03:00 in high humidity then looks like a barrier
success.

**Fallback.** The 산악기상관측망 mountain weather network, which the repository
already uses elsewhere, if its access is cheaper than the API Hub key.

**Carried caveat from the registry.** Times are KST, and the time zone is recorded
on every loader output.

### 4.4 `kfs_fire_state_history_csv` and `kfs_fire_stats_csv`

**Needed for.** The containment time that section 5.2 uses to pick the post-fire
scene. That is the whole role. The arrival clock of this direction is the detection
record, not a KFS report time, so a dirty timestamp in these files cannot corrupt a
label.

**What A1 confirmed.** `kfs_fire_stats_csv` is verified and covers report years
**2022 to 2025 only**, so it does not reach Goseong 2019. The coverage of
`kfs_fire_state_history_csv` is still unknown and is a question for A1.

**If neither covers a fire.** Pre-registration section 5.2 now carries the
substitution: the containment time is the last detection inside the fire's
acquisition box plus a 24 hour margin, and the source of the containment time is
recorded as a column per fire. This is pre-registered rather than improvised, and
it applies to Goseong 2019 by default.

**Carried caveats from the registry**, which this direction inherits and does not
re-litigate: 12 negative durations, 2 impossible end years, report time is not
observed ignition, CP949 encoding, and the address nulls. A2 owns the
dirty-timestamp quality control (task T1.5) and this direction consumes it.

### 4.5 `vworld_geocoder`

**Needed for.** Cross-checking a fire's reported address against its detection
footprint, and nothing in the label path.

**If it does not arrive.** Nothing critical is lost. Note that if VWorld also turns
out to be the orthoimagery source of section 3.3, its priority changes from low to
critical, which is a reason to answer that question early.

---

## 5. What this direction needs that the registry does not have

Three gaps, all of them requests to A1 or to John rather than things A3 will
create.

| gap | why it matters | who |
|---|---|---|
| **high-resolution pre-fire orthoimagery with per-tile vintage** | the width covariate has no other source; section 3 | A1 for the registry entry, John for access as **WJ-009** |
| **forest road SHP attribute schema**, specifically a class field and a construction or survey year | the year is what excludes roads built after a fire; without it a post-fire road is scored as a barrier that held | A1 |
| **suppression resource placement during the five fires** | the confound of section 12.4, which A6 names as the strongest objection to this direction: a road that held partly measures that a crew was anchored on it, and no covariate in the planned set separates the two. There is no data fix in this round | John, **WJ-010** on the taskboard |

---

## 6. Standing rules this document inherits

1. **Korea only.** Every dataset listed is Korean in coverage. Foreign work is
   cited as prior art or as the source of a method; foreign fire, road or landslide
   records are not used for fitting (scope rule 1, and `RC-010`).
2. **EPSG:5186 for analysis, EPSG:4326 for exchange** (decision D-005).
3. **Never mosaic two DEM providers** (`docs/HANDOFF_ROUND3.md` section 5 rule 17).
4. **A3 does not edit `research/data/REGISTRY.yaml`.** Every correction above is a
   request to A1.
5. **Raw downloads are immutable** and are registered with URL, checksum and access
   date so a stranger can re-download them exactly.
