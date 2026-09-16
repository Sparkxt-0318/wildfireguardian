# Suppression direction, data requirements

Owner: A5. Keyed to `research/data/REGISTRY.yaml`, which A5 does not own and has
not edited. Companion to
`research/suppression/PREREG_suppression_2026-09-16_v0.1.md`.

For each dataset: what it is for, what happens if it never arrives, and the
fallback. One entry at the end is **not in the registry** and is requested.

**The short version is section 5.** Two of the ten sources this direction needs
are at status `verified`. Those two supply the outcome, the clock, the address
and the calendar, and **not one covariate that varies within a fire**. The
containment hazard of pre-registration section 11.2 is a model of time-varying
covariates, and today it has none.

**One requirement is different in kind from all the others and is stated first.**
Everything below is about precision. `kfs_fire_stats_api` is about whether the
direction exists, because the registered evaluation refuses a four-year record.

---

## 0. The one that decides the direction

### `kfs_fire_stats_api` (WJ-001 for the key, then WJ-006)

**For.** Depth. The registered split, `forward_chaining_by_year` with
`min_train_years: 10` and `horizon: 1`, yields `max(0, Y - 10)` folds on `Y`
distinct report years. The committed CSV supplies four. The API is the only
route to more.

**How much depth is needed, exactly.** Pre-registration section 4.3 has the
table. The short form:

| if the API reaches back to | distinct report years | folds |
|---|---|---|
| 2022 (no better than the CSV) | 4 | none, the call refuses |
| 2016 | 10 | none, the call refuses |
| 2015 | 11 | 1 |
| 2010 | 16 | 6 |
| 2001 | 25 | 15 |
| 1991 | 35 | 25 |

**So the probe has a threshold and it is 2015.** A record that stops at 2016 is
worth no more to this direction than the CSV already on disk. That is the single
most useful sentence in this file for whoever clears WJ-001, and it was not
obvious before the arithmetic was run.

**If it never arrives.** Failing condition F2 of the pre-registration. This
direction reports no held-out number, makes no claim about discrimination, does
not substitute a descriptive four-year fit, and does not use the phrase
"preliminary result". Its deliverable becomes the accounting: the clock and
address measurements under `design/`, the fold arithmetic, the cause-field
finding, and this file.

**Fallback.** WJ-006, the drafted records request to the Korea Forest Service or
NIFoS, which is itself blocked behind WJ-001 because the probe decides whether
the request is needed. There is no third route. A longer record cannot be
reconstructed from anything else on this list.

**The probe is one command** and it is written and waiting:
`research/data/checks/probe_kfs_api.py`. It reads `DATA_GO_KR_KEY` from the
environment only, never prints it, and makes no request without it.

---

## 1. On disk and verified

### `kfs_fire_stats_csv`

**For.** The outcome (피해면적_합계), the report clock (발생일시), the
containment timestamp (진화종료시간), the address, the administrative office and
the calendar covariates. It is also the source of the concurrent-load covariate
of pre-registration section 10.5, computed from report times and provinces only.

**If it never arrives.** It has arrived: 2,020 rows, report years 2022 to 2025,
CP949.

**What it cannot do, measured rather than assumed.**
`research/suppression/design/clock_and_address.py` and its committed output:

- **It cannot place a fire.** Zero of the 2,019 rows carrying a finest address
  field carry a lot number in it. The finest reachable geocoding rung is a 리 or
  동 polygon. Every spatial covariate and the local solar phase inherit that
  ceiling.
- **It cannot be joined on the finest name alone.** Among the 1,703 fully
  addressed rows there are 1,250 distinct finest names and 191 of them occur
  under more than one parent path.
- **It carries 18 raw province spellings for 17 provinces**, one row spelling
  충남 with a trailing space.
- **Its cause field is not a first-hours observation.** 73.22 per cent of rows
  carry the free-text escape value in the coded detail column, and 34.75 per
  cent of rows carry 조사중, 추정 or 미상 in the free-text field. Some say
  조사중 verbatim.
- **Its clock is minute-resolved**, which is the one thing on this list that
  came back better than feared: 2.48 per cent of report times fall on the hour,
  so an hourly hazard has a clock that can carry it.

**Fallback.** None needed and none possible; it is the record.

### `kfs_fire_state_history_csv`

**For.** A second clock (진화시작시간 and 진화완료시간, which are suppression
start and completion rather than report and containment), the Uiseong 2025
duplicate pair, and the 관할기관명 as a cross-check on 발생장소_관서.

**Never use its sunrise and sunset columns.** They are a single national value
per calendar date, confirmed independently by A1. This direction is the one with
a solar covariate and therefore the one most tempted by them. Local solar times
come from `research/shared/geo/solar.py` and from nowhere else.

**A distinction this direction depends on.** 진화시작시간 is when suppression
began, not when the fire began. The difference between it and the report time is
a **dispatch lag**, which is observable, and it is not the **report offset** of
pre-registration section 5, which is the gap between ignition and report and is
not observable. Conflating the two would look like a measurement of the very
thing that cannot be measured. The two files' identifier spaces are not
confirmed to be the same, per the registry, so any join between them is checked
before it is used.

**If it never arrives.** It has arrived: 2,030 rows, 2022-01-01 to 2025-11-10.

**Fallback.** For the dispatch lag, none. For the duplicate pair, the complex
rule of `research/shared/qc/complexes.py`.

---

## 2. Blocked, and the direction's covariates do not exist without them

### `vworld_geocoder` (WJ-001)

**For.** Turning an address into coordinates. Everything spatial in this
direction hangs off it: the local solar phase that the entire night arm is
defined on, the nearest-weather-station match, the access distance, and the
terrain covariates.

**If it never arrives.** The containment hazard fits with calendar and
administrative covariates only, **there is no night arm at all**, and
pre-registration section 24 item 4 requires the direction to say so rather than
to substitute a national solar proxy. Substituting one would be the same error
as using the state-history file's national sunrise column, one step further
removed.

**Fallback, and what it costs.** A 리-level centroid table built from an
administrative boundary layer would reach the same precision ceiling the record
already imposes, so the fallback loses nothing to the geocoder in precision. It
loses the precision **class**, which pre-registration section 9.3 carries as a
covariate, and it needs the boundary layer of section 3 below, which is not a
registry entry.

### `kma_asos_aws` (WJ-001)

**For.** Every time-varying meteorological covariate: wind speed, gust,
relative humidity, temperature and days since rain. These are the covariates the
brief's "matched weather" night comparison is matched on, and they are the
covariates that give baseline B1 anything to say.

**If it never arrives.** The containment hazard has no weather. The night
contrast then confounds the solar phase with the diurnal wind and humidity cycle
with nothing separating them, so the calm-night stratum of pre-registration
section 12.2 cannot be constructed and the arm's only discriminating test is
gone. Baseline B1 does not exist. The direction reports the B0 comparison alone.

**Fallback.** None that is Korean, public and hourly. A reanalysis product at a
coarse grid would not resolve the valley-scale wind that matters, and importing
one would put a modelled field where an observation belongs.

### `firms_active_fire_korea` (WJ-001)

**For.** Measurement M-R of pre-registration section 5.4: the only route this
program has to any Korean evidence about the report offset. A satellite
detection timestamped before a fire's reported start time is direct evidence
that the fire was burning before it was reported, and the difference is a lower
bound on that fire's offset.

**If it never arrives.** The sixteen-cell offset grid keeps the endpoints
declared in section 5.4, which are assumptions and not Korean measurements, and
the pre-registration's output says so. A5's recommendation in section 25.3 is
that the night arm and the access-distance coefficient are then demoted to
permanently secondary status rather than reported with an unbounded nuisance
parameter.

**What it cannot do even when it arrives.** The 375 m sensor detects fires
already large at overpass, so the bound is available on a size-selected
subsample; overpasses are a few per day, so the bound is coarse; and a fire with
no pre-report detection yields no bound rather than a bound of zero. The
selection runs toward the large fires, which is where the offset matters most to
the tail and least to generality.

### `kfs_forest_roads` (WJ-017) and `base_map_linear_features`

**For.** The access-distance covariate, which the escape score is expected to
lean on hardest.

**If they never arrive.** Access distance does not exist. The score is fitted on
weather, calendar and terrain, and the direction does not claim anything about
access.

**What they cannot do.** A1 confirmed against the portal that the Korea Forest
Service forest road dataset carries **no width attribute**. This direction does
not need width; it needs presence and position, which the geometry supplies. The
binding limitation is on this side of the join and not that one: the fire's own
position is a 리 centroid, so the distance being computed is the distance from a
polygon centroid to the nearest road, and the error is largest in the largest
and most mountainous 리, which is where access distance is largest. That is
proposed leakage item D13 in pre-registration section 18.3, and no better road
layer fixes it.

### `dem_korea` (WJ-011, fallback behind WJ-001)

**For.** Slope and elevation at the fire's resolved location.

**If it never arrives.** Two covariates are absent. This is the least damaging
absence on the list, because terrain at a 리 centroid is a weak proxy for
terrain at the fire in any case, and the day-province random effect absorbs some
of it.

**Fallback.** A coarser global elevation product would be adequate at the
precision the address ceiling already imposes.

### `kfs_forest_type_map` (WJ-018 for access, WJ-012 for the licence)

**For.** The fuel covariate: pine, broadleaf or mixed at the resolved location.

**If it never arrives.** The fuel covariate is absent and season plus province
carry what they can of it, which is not the same thing and the direction says
so.

**Fallback.** None this direction would defend. A fuel class inferred from
satellite imagery would be a derived layer validated against nothing Korean, and
the landslides direction has already reached the same conclusion about the same
map.

---

## 3. Not in the registry, and requested

### `kr_admin_boundaries_ri` (proposed id, already requested by A4)

**For.** Three things this direction needs and cannot get elsewhere: the 리 and
동 polygons that the address ceiling of section 1 resolves to; the 시군구
adjacency relation that the supplementary complex rule of pre-registration
section 9.4 is defined on; and the parent-path resolution that section 9.3
requires, since 191 finest names occur under more than one parent.

**If it never arrives.** The supplementary complex rule cannot run, so multi-county
events other than the one the K-SPREAD table names are counted as separate
fires, which inflates the row count, deflates the effective sample size estimate
in the wrong direction, and puts pieces of one event on both sides of a fold
boundary. That last one is leakage item D8 in its direct form.

**Fallback.** For adjacency only, a hand-written adjacency table for the
counties that actually appear in multi-county events, committed and reviewed.
That is feasible and is A5's recommendation if the layer is slow, because the
number of counties involved is small. It is not a fallback for the polygons.

**Note.** A4 has already requested this id for the landslides direction. A5 is
not duplicating the request, and records here only that this direction needs the
same layer for a different reason, so that the case for it is not weaker than it
should be.

---

## 4. Requests that change the question rather than the precision

### A Korean suppression-resource record

**What it would be.** Per-fire counts of engines, ground crew and rotary-wing
sorties, with their dispatch times.

**Why it matters more than anything else on this list except depth.**
Pre-registration section 11.4 item 3 states that suppression effort is not in
the model at all, so every coefficient this direction produces is an association
under whatever regime operated. A resource record would move the direction from
"which fires got large" toward "which fires got large given what was sent", and
it is the only thing that would make assumption A-NI of section 3.2 even
partially checkable at the fire level rather than through the concurrent-load
instrument.

**Status.** Not in the registry, not known to be public, and not requested here,
because A5 does not know that it exists in a releasable form and a request for a
dataset that may not exist is a way of making a gate look answerable. It is
recorded as the thing that would change the question, so that if anyone
discovers such a record, the reason to want it is already written down.

### A separate ignition-time field

**What it would be.** Any KFS field distinguishing the time a fire was reported
from the time it was judged to have started.

**Why.** Pre-registration section 5 in full. It would collapse the sixteen-cell
grid to a covariate.

**Status.** The committed CSV has one time field, 발생일시, and the registry
records it as a reported start. **Whether the Open API returns a richer time
schema is unknown and is part of what the probe would answer.** That is a second
reason to run the probe beyond the depth question, and it is not in the probe
script's current output description, so `OPEN_QUESTIONS.md` Q1 asks A1 to record
the API's field list when the probe runs.

---

## 5. Summary table

| registry id | status | what it supplies | what happens without it |
|---|---|---|---|
| `kfs_fire_stats_api` | pending | **depth, and therefore the evaluation** | **no held-out number at all, failing condition F2, hard stop for every claim** |
| `kfs_fire_stats_csv` | verified | the outcome, the clock, the address, the calendar | it is here, and it reaches only four report years |
| `kfs_fire_state_history_csv` | verified | the dispatch lag, the duplicate pair | minor |
| `vworld_geocoder` | pending | coordinates | **no night arm, no access distance, no terrain, no weather match** |
| `kma_asos_aws` | pending | every time-varying weather covariate | no matched weather, no calm-night stratum, no baseline B1 |
| `firms_active_fire_korea` | pending | the only Korean bound on the report offset | the offset grid stays an assumption; A5 recommends demoting the night and access arms |
| `kfs_forest_roads` | pending | access distance | the covariate the score would lean on hardest does not exist |
| `base_map_linear_features` | pending | access distance fallback | same |
| `dem_korea` | pending | slope and elevation | two weak covariates absent, least damaging on this list |
| `kfs_forest_type_map` | pending | the fuel covariate | season and province carry what they can, which is not the same |
| `kr_admin_boundaries_ri` | **not registered** | 리 polygons, 시군구 adjacency, parent-path resolution | the supplementary complex rule cannot run, and event pieces straddle folds |

**Read the first row against the rest.** Nine of these change what the direction
can measure. The first decides whether it measures anything.
