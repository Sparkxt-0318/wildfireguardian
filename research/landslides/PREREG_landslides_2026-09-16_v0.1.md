# Landslides direction, pre-registration, v0.1

```yaml
prereg:
  direction: landslides
  version: 1
  date: 2026-09-16
  author: A4
  items_present: [P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, P15, P16]
  result_artifact: "research/landslides/results/landslides_v0.1.json"
  primary_metric_json_path: "held_out.primary_metric.value"
  split_call: "spatial_block_cv(xs, ys, fire_ids=fire_ids, **PRIMARY_SPLITS['landslides']['kwargs'])"
  split_fingerprint: "not pinnable at v0.1, see section 12.2"
  primary_metric: "held-out mean log predictive density per storm-unit cell"
  baseline: "B1, rainfall and terrain with no fire term"
  datasets: [kfs_landslide_history, kfs_fire_stats_csv, kfs_fire_state_history_csv,
             dem_korea, kma_radar_qpe, kma_asos_aws, sentinel2_l2a_dnbr,
             naas_soil_map, kigam_geology_map, kfs_forest_type_map,
             vworld_geocoder, kr_admin_boundaries_ri, kfs_salvage_logging]
  outcome_seen: false
  signoff: unsigned
  signoff_record: null
```

**Nothing in this direction has been fitted. No outcome value has been looked
at.** Section 3.2 lists every quantity A4 has computed and every file A4 has
read, so that section 4 of `research/eval/SIGNOFF.md` has nothing to find later.

**This document recommends against the design it was asked to pre-register, in
two of its three load-bearing choices, and says so in section 1.6 rather than in
a limitations paragraph.** The unit is changed from the slope unit to the
catchment, and the likelihood is changed from a unit-level binary hazard to an
areal count hazard, both for reasons that are measured in section 3 and not
argued from taste. The recovery-window question itself is reported in section 7
as not answerable in the form it was asked, with the committed data, and section
7.6 fixes in advance what is reported instead.

---

## 0. Where each required item lives

| item | section |
|---|---|
| P1 hypothesis in falsifiable form | 1 |
| P2 unit of analysis | 4, 5 |
| P3 label rule | 6 |
| P4 covariates and sources | 9 |
| P5 model form | 10 |
| P6 held-out sets named in advance | 12 |
| P7 primary metric | 13 |
| P8 simple baseline | 14 |
| P9 what would count as failing | 15 |
| P10 stopping rule and multiplicity | 16 |
| P11 leakage self-audit | 17 |
| P12 data provenance | 18 |
| P13 compute and feasibility | 19 |
| P14 scope declaration | 20 |
| P15 what the result will not say | 21 |
| P16 shape of the result artifact | 22 |

The three objections this direction was told to confront rather than file are in
sections 7 (aliasing), 8 (the unit) and 11 (the species arm). Each ends with a
pre-registered reading rule rather than with an acknowledgement.

---

## 1. The hypothesis, in falsifiable form (P1)

### 1.1 The question

How long does a burned Korean slope stay more landslide-prone than it would have
been unburned, and does that window differ between pine-dominated and
broadleaf-dominated stands.

### 1.2 The hypothesis

*Hypothesis:* conditional on the triggering storm's rainfall, on terrain, on soil
and on geology, the rate at which recorded landslides occur on Korean forest land
is elevated on ground burned within the preceding few years relative to
comparable unburned ground, the elevation is largest in the first year or two
after the fire, and it declines thereafter. A secondary hypothesis is that the
rate of that decline differs between pine-dominated and broadleaf-dominated
stands.

*Direction of the predicted effect.* The fire term is positive at zero years
since fire and its increments are negative thereafter.

*Value under the null.* The fire term is zero at every value of years since fire,
so that after conditioning on rainfall and terrain, burned and unburned ground
carry the same rate.

### 1.3 "This hypothesis is wrong if ..."

This hypothesis is wrong if, with the storm rainfall term in the model and the
reporting-probability term in the model, the posterior for the fire term at zero
years since fire has its 90 per cent interval covering zero, or if that interval
lies below zero, on the pre-registered held-out blocks. It is also wrong, in its
secondary arm, if the pine and broadleaf decline parameters have overlapping
90 per cent intervals wide enough to contain each other's point estimates.

### 1.4 The estimand, and what it is not

The estimand is **the association between recorded landslide rate on Korean
forest land and years since fire, conditional on the covariates in section 9, in
a record whose reporting probability is not observed.**

It is not the physical rate of slope failure. The occurrence record is an
administrative record of reported landslides on forest land, not a mapped
inventory, so what is modelled is the product of a failure rate and a reporting
probability. Section 6.5 pre-registers how the two are separated, and section 21
pre-registers that where they cannot be, the reported quantity keeps the word
recorded in its name.

It is also not a causal effect of fire. Fires do not burn at random across Korean
terrain, and the matching design of section 10.6 balances what it can measure and
nothing else.

### 1.5 The five failing conditions, fixed now

Each is written so it cannot be re-read as a success. Section 15 gives the
threshold and the reading for each.

- **F1.** The fire term at zero years since fire does not clear zero.
- **F2.** The years-since-fire term reverses sign or reorders across the three
  calendar-effect specifications of section 7.6.
- **F3.** Fewer than a declared floor of records are assignable to a unit at the
  primary scale, which means the direction has no unit.
- **F4.** The held-out primary metric does not beat baseline B1 by the declared
  margin.
- **F5.** The species arm's two decline parameters are not separated, in which
  case the species arm is withdrawn rather than reported weakly.

### 1.6 Where this document departs from the design it was handed

Recorded here, at the top, because a departure buried in section 10 is a
departure that a reader can miss.

| the design as handed | what this document pre-registers | why, and where |
|---|---|---|
| unit is a DEM-derived slope unit | unit is a catchment at a scale chosen by a measured assignability rule, with the slope unit demoted to a conditional secondary that runs only if a declared gate passes | section 8. No record in the occurrence file carries a lot number, so parcel-level geocoding is unreachable for all of it, and the smallest honest confusion set is a 리 polygon, which is much larger than a slope unit |
| discrete-time hazard on the probability a slope unit fails in a storm | discrete-time **areal count** hazard on the number of recorded landslides attributed to a unit in a storm, with an exposure offset | section 10.2. Address-level data does not say which slope failed, so a unit-level binary label would be manufactured. The unit failure probability remains recoverable from the fitted intensity and is reported as a derived quantity |
| correct for scars that revegetate before mapping | that correction is pre-registered only for the imagery-derived inventory arm; for the occurrence record the analogous correction is a reporting-probability model | section 6.5. The occurrence record is dated at report time, so a scar that revegetates before an imagery campaign is still in it. The two corrections are not the same correction and pooling them would hide the one that bites |
| report the recovery window | report a right-censored lower bound and the identified curvature, under three declared calendar specifications | section 7.6. The committed exposure record supports at most four annual steps of years since fire |

---

## 2. Scope: what Korea supplies, and what it does not (P14 in brief, full text in section 20)

Korea only. Every dataset in section 18 is Korean in coverage. Two non-Korean
sources appear and each supplies a functional form or a mechanism, never data:
Sidle 1992 supplies the shape of the root-cohesion curve, and DeBano 2000
supplies the mechanism of post-fire soil water repellency. Neither contributes a
number to any fit. Section 20 carries the sentence each requires.

---

## 3. What has been read, and what has been computed

### 3.1 Why this section exists before the design

Section 4 of `research/eval/SIGNOFF.md` says an amendment after any look at data
is a new pre-registration with a mandatory account of what was seen. The cheapest
way to make that section unnecessary is to write the account at v0.1. Leakage
item A6 says the held-out set is not held out from the person, and the honest
mitigation is the record, not a claim of innocence.

### 3.2 Everything A4 has computed from committed data

Three scripts, all committed under `research/landslides/design/`, all writing to
`research/landslides/design/design_numbers.json`. A6 can re-run each.

| script | what it reads | what it returns | outcome exposure |
|---|---|---|---|
| `aliasing_separation.py` | `kfs_fire_stats_csv`, the year and the burned area of each fire | the age, period and cohort geometry of section 7 | **none.** The fire record is the exposure side |
| `address_precision.py` | `kfs_landslide_history`, the four address columns only | the geocoding precision ceiling of section 8 | **address text only.** No year, no storm window, no damaged area, no cross-tabulation of any of them |
| `split_demonstration.py` | `research/eval/splits.py` and a declared synthetic geometry | the P6 call, the fingerprint mechanism, and the control-identifier defect of section 12.3 | **none** |

In addition, A4 read the column list and the value counts of
`시설구분_등급` in the occurrence record, which is a forest ownership
classification with eight values, all of the form `산사태_<ownership>`. That is a
metadata field and it is carried as a covariate in section 9, so reading it is
covered by P4. A4 also read the distinct-value counts of the four address columns
and the count of distinct values in `재난구분`, which is twenty-four storm
windows across the record. The `재난구분` count is outcome adjacent, because a
storm appears in that field only if it produced a recorded landslide, and it is
declared here for that reason. It is used in section 4.3 as a clustering count
and nowhere else.

**What A4 has deliberately not looked at, and will not before the sign-off:** the
per-year count of landslide records, the per-place count of landslide records,
the damaged-area column, and any cross-tabulation of the outcome against
anything. The per-year count is the exact quantity that leakage item C3 turns on
and seeing it would shape the detection model that is supposed to be blind to it.

### 3.3 What A4 has read of the Sancheong literature, for item C8

Leakage item C8 says Sancheong 2025 is held out only if nobody read the paper
first, and that reading the results counts. The record, in full:

- A4 has read, from the program brief and from `research/TASKBOARD.md`, that
  Nguyen, Song and Kim 2026 report a Sancheong inventory containing 568
  initiation points. That count is a result from that paper.
- A4 has read nothing else from it. It has not been obtained. It is a drafted
  request awaiting John as WJ-005, and `research/lit/landslides_prior_art.md` is
  a stub that A7 has not swept.
- The count of 568 has set no prior, no covariate, no model form, no threshold
  and no gate in this document. It appears here and in section 18 and nowhere
  else.

**The consequence for the stress test, which is not the one the brief assumes.**
The Sancheong fire is recorded in `kfs_fire_stats_csv` at 2025-03-21 in 경남 산청
at 3397.52 ha, and the storm of interest is the following July. Sancheong
therefore contributes years since fire of zero and nothing else. A held-out fire
that contributes a single value of years since fire cannot test the shape of the
recovery curve at all. It tests the level of the fire term at zero years since
fire, under an extreme storm, and that is what section 15.6 pre-registers it as
testing. Calling it a stress test of the window would be a category error, and it
is better to say so now than to discover it when the number arrives.

---

## 4. The unit of analysis (P2)

### 4.1 One row

**One row is one unit in one storm.** The unit is a catchment, defined in section
5. The storm is a triggering rainfall event, defined in section 6.2. A unit
contributes a row for every storm in which it is in the risk set, whether or not
a landslide is recorded in it.

The outcome on that row is the count of occurrence records assignable to that
unit and that storm, which is zero for most rows. Section 10.2 gives the
likelihood.

### 4.2 Expected row count

Not knowable yet, and the honest statement is why. The row count is the number of
units in the risk set times the number of storms. The number of units is a
function of a DEM that is not on disk, and the number of storms is a function of
a rainfall product behind an unset key. Both are named in section 18 with their
Waiting-on-John items.

What is bounded now: the occurrence record has 5,118 rows, of which some share a
unit and a storm, so the number of non-zero cells is at most 5,118 and is
strictly less. The number of units with a recorded landslide is at most the 1,427
distinct 리 values in the record, and is at most 154 if the assignability rule of <!-- forbidden-ok: 154 -->
section 8.4 forces the 시군구 scale.

**Section 22 requires the realised row count, the non-zero cell count and the
effective sample size to be reported at named key paths, whichever way they come
out, before any coefficient is quoted.**

### 4.3 The clustering structure, stated explicitly

Rows share, and are therefore not independent along, four axes.

1. **The storm.** Every unit hit by one storm shares that storm's rainfall field,
   its synoptic setting and its reporting campaign. The committed record carries
   **twenty-four** distinct storm windows across five years. This is the binding
   constraint and it is small.
2. **The fire.** Every burned unit inside one fire perimeter shares the fire's
   date, its weather, its severity field and its salvage-logging history.
3. **Space.** Neighbouring units share geology, soil map unit, aspect and the
   same radar pixel.
4. **The 리.** Every unit inside one 리 polygon shares the same confusion set, so
   an occurrence record's assignment error is common to them.

### 4.4 The effective sample size, and the method

P2 requires a number smaller than the row count and the method used to get it.
The method is fixed now.

The effective sample size is computed as the number of **storm by spatial-block**
clusters, which is the resampling unit of section 13.3, and separately as a
design-effect estimate `n_eff = n_rows / (1 + (m_bar - 1) * rho)` where `m_bar`
is the mean cluster size and `rho` is the intra-cluster correlation of the Pearson
residuals of baseline B1, computed inside the training fold only so that item A1
does not fire. Both are reported at named key paths.

The ceiling on the first quantity is stated now, from committed exposure data and
without touching the outcome: **twenty-four storms times five spatial folds is
120 clusters, and the realised number is smaller because not every fold is hit by
every storm.** No interval in this direction may be computed on a resampling unit
finer than that, and section 13.3 fixes the resampler accordingly.

---

## 5. The unit, derived (P2 continued)

### 5.1 The derivation method

Units are derived from the DEM by a documented, deterministic procedure, run once,
committed, and never re-derived after any outcome is seen.

1. Reproject the DEM to EPSG:5186 per `research/shared/geo/crs.py`.
2. Fill sinks by the Wang and Liu priority-flood method, recording the filled
   volume so a mis-filled basin is visible.
3. Compute D8 flow direction and flow accumulation.
4. Extract a channel network at a declared accumulation threshold `A_c`.
5. Delineate the sub-catchment draining to each channel link. That partition is
   the unit set. It tiles the study area with no gaps and no overlaps, which a
   slope-unit partition does not always do.
6. Merge any sub-catchment below a declared minimum area `A_min` into its
   downstream neighbour, so the partition carries no slivers.

`A_c` and `A_min` are set by the assignability rule of section 8.4, not by eye,
and the grid over which they are chosen is declared in section 8.5.

**Why a catchment partition and not slope units.** Section 8 gives the measured
reason. The procedural reason is that the catchment partition is a function of
flow accumulation alone, has one free parameter, and degrades gracefully as the
DEM coarsens, whereas a slope-unit partition depends on a half-basin subdivision
whose parameters are usually tuned against a landslide inventory, which would be
tuning the unit against the outcome and would fire leakage item A3.

### 5.2 What a 30 m DEM can and cannot resolve

The DEM on the fallback path is Copernicus GLO-30 at 30 m posting, because the
NGII 5 m product returned HTTP 400 on two attempts and is human gate WJ-011.

What this costs, stated before the unit is chosen rather than after:

- A shallow landslide initiation zone in Korean mountain terrain is commonly a
  convergent hollow of the order of tens of metres across. At 30 m posting such a
  hollow spans of the order of one cell. **The DEM cannot resolve the initiation
  site.** This is the strongest terrain argument against the slope unit and it is
  independent of the geocoding argument in section 8.
- Slope computed from a 30 m DEM is a smoothed slope, and smoothing attenuates
  the steep tail. A slope covariate at 30 m is therefore biased toward the middle
  of its range where the model needs the tail, which pushes in the same direction
  as the measurement-error attenuation the roads direction documents.
- A catchment at the scale section 8.4 is likely to select spans many tens of
  cells, so the partition itself is resolvable at 30 m even though the initiation
  site is not. That asymmetry is the argument for the areal count likelihood of
  section 10.2: aggregate quantities survive the coarse DEM, point quantities do
  not.

**Pre-registered consequence.** Slope enters as a distribution summary of the
unit, not as a point value: the area fraction of the unit above a declared slope
threshold, and the area-weighted mean slope of that steep fraction. The threshold
is declared in section 9 and does not move.

**If the 5 m DEM arrives** (WJ-011 clears), the unit derivation is re-run at 5 m
and the partition changes. That is a change to the unit, so it is section 4 of the
protocol, a new version, not a tweak. It is cheaper to say that now than to be
asked later.

---

## 6. The label rule (P3)

The protocol's acceptance test is that A6 draws ten units and labels them from the
written rule alone. So the rule is written as an ordered procedure with a
tie-break at every branch and an explicit unlabelable class.

### 6.1 What is being labelled

Two things, and they are separate procedures.

- **L-A, the outcome.** For a given unit and a given storm, the count of
  occurrence records assigned to that cell, or the class `UNASSIGNABLE`.
- **L-B, the exposure.** For a given unit and a given storm, whether the unit is
  burned, and if so with what years since fire and what burn severity, or the
  class `UNKNOWN_EXPOSURE`.

### 6.2 The storm, defined before any outcome is read

A storm is a maximal run of consecutive hours at a unit's location in which
hourly rainfall from `kma_radar_qpe` is at or above `r_wet`, allowing gaps of up
to `g_max` consecutive hours below `r_wet`, and whose total accumulated rainfall
reaches `R_min`. Declared values: `r_wet` at 1 mm per hour, `g_max` at six hours,
`R_min` at 30 mm. The declared sensitivity grid is `R_min` in {20, 30, 50} mm and
`g_max` in {3, 6, 12} hours, and every cell of that grid is reported, not only the
chosen one.

**The risk set is every storm, not every storm that caused a landslide.** The
`재난구분` field of the occurrence record enumerates only storm windows that
produced a recorded landslide, twenty-four of them. Building the risk set from
that field would condition the sample on the outcome, which is the same defect as
leakage item B3 in the roads direction. So the storm enumeration comes from the
rainfall product alone, and `재난구분` is used only to attach a record to an
already-enumerated storm.

**Tie-break.** A record whose `재난구분` window overlaps two enumerated storms is
attached to the storm with the larger accumulated rainfall at the record's
assigned unit, and the count of records requiring that tie-break is reported.
A record whose window overlaps no enumerated storm is `UNASSIGNABLE_TIME`, and its
count is reported per year.

### 6.3 L-A, the outcome assignment procedure

For each occurrence record, in this order.

1. **Resolve the address to its finest administrative polygon.** Use the 리
   polygon when the 리 field is present and resolves in
   `kr_admin_boundaries_ri`; else the 읍면동 polygon; else the 시군구 polygon;
   else `UNASSIGNABLE_ADDRESS`. Record the rung reached as a column. Rungs are
   never mixed silently, per `research/shared/geo/geocode.py`.
2. **Restrict the polygon to forest land**, because every value of
   `시설구분_등급` is a forest ownership class, so the record cannot have
   occurred outside forest land. The restricted polygon `S_i` is the confusion
   set. If the restriction is empty, the record is `UNASSIGNABLE_LANDCOVER` and
   the count is reported.
3. **Compute the concentration** `c_i = max_u area(S_i ∩ u) / area(S_i)` over
   units `u` of the partition.
4. **Assign** the record to `argmax_u area(S_i ∩ u)` if `c_i >= q`; else the
   record is `UNASSIGNABLE_UNIT`. `q` is declared at 0.50 with a sensitivity grid
   of {0.35, 0.50, 0.70}, every cell reported.
5. **Tie-break.** If two units tie on intersected area to within one DEM cell,
   the record is `UNASSIGNABLE_UNIT`, not assigned to either. Ties are counted.

**The unlabelable class is real and it is four classes:**
`UNASSIGNABLE_ADDRESS`, `UNASSIGNABLE_LANDCOVER`, `UNASSIGNABLE_TIME` and
`UNASSIGNABLE_UNIT`. Their counts are reported per year and per rung at named key
paths, whichever way they come out. Unassignable records are never forced into a
unit and are never silently dropped: they are carried in the accounting and their
share is a pre-registered gate, F3.

**The soft-assignment alternative, declared now so it cannot be introduced
later.** A record could contribute `area(S_i ∩ u) / area(S_i)` to every
intersecting unit instead of being assigned to one. That is pre-registered as the
declared sensitivity analysis S-SOFT of section 16.1, not as the primary, because
a soft assignment spreads a real landslide over flat units that did not fail, and
that pushes the fitted terrain coefficients toward zero in a way a reader cannot
see. Both are reported.

### 6.4 L-B, the exposure assignment procedure

For each unit and each storm, in this order.

1. Take the set of fire perimeters whose fire date precedes the storm by at least
   one day and by at most `T_max` years. `T_max` is declared at 10 years, which is
   larger than anything the committed record can support and is set from the Sidle
   1992 functional form rather than from the data.
2. A unit is **burned** in that storm if the burned area inside it, taken from the
   Sentinel-2 dNBR perimeter of the most recent qualifying fire, covers at least
   `f_burn` of the unit's forest area. `f_burn` is declared at 0.10 with a
   sensitivity grid of {0.05, 0.10, 0.25}.
3. Years since fire `t` is the floor of the interval in years between that fire's
   date and the storm's start.
4. Burn severity is the area-weighted mean dNBR over the burned part of the unit,
   taken from the pixels of that perimeter, and is carried as a covariate with the
   contamination paragraph of section 9.3.
5. If no Sentinel-2 perimeter can be built for a fire that the fire record says
   burned inside the unit, the unit is `UNKNOWN_EXPOSURE` for that storm and is
   removed from the risk set for that storm, with a reported count. It is not
   scored as unburned, because scoring an unmapped burn as unburned would move a
   positive into the control arm.
6. **Tie-break.** If two fire perimeters both qualify, the unit takes the most
   recent, and the count of units with more than one qualifying fire is reported.

### 6.5 The reporting-probability model, which is not a revegetation model

Leakage item C3 is written for a mapped inventory whose completeness falls with
mapping effort. The committed record is not that. It is an administrative
occurrence record of landslides on forest land, dated at report time and
classified by ownership. Three consequences, and they point in different
directions from the ones C3 anticipates.

1. **Revegetation before mapping does not remove a record from this file**,
   because the record is created at report time, not at imagery-interpretation
   time. The revegetation correction the brief asks for is pre-registered for the
   imagery-derived inventory arm of section 11.4 and for the Sancheong inventory,
   and nowhere else. Applying it to the occurrence record would be correcting for
   a mechanism that does not operate on it.
2. **What does vary is the probability that a failure is reported at all.** A
   landslide on remote state forest with nothing below it is less likely to be
   reported than one that reaches a road, a field or a structure. So the record's
   reporting probability is a function of proximity to assets, of ownership, and
   of administrative attention after a named disaster.
3. **And that puts the road covariate in an impossible position.** The brief asks
   for roads to be handled as a separate exposure. In this record a road is
   simultaneously a plausible cause of failure, through cut slopes and drainage
   interception, and a determinant of whether a failure is reported. Nothing in
   the covariate set separates the two. This is the same shape as leakage item B2
   in the roads direction and it has the same remedy, which is a scope cut rather
   than a control.

**The pre-registered treatment.** The model carries a reporting term
`log p_report` as an additive offset-like component with its own covariates:
ownership class, distance to the nearest mapped road, distance to the nearest
built-up polygon, and a per-storm reporting intercept. The reporting term and the
hazard term are not separately identified from this record alone; section 10.5
says so under P5 and section 21 fixes the vocabulary. The road coefficient is
reported inside the reporting term and is **never** interpreted as a landslide
mechanism. If a reader wants a road effect on failure, this design cannot supply
it and says so.

### 6.6 The second pass P3 requires

At least thirty units are labelled a second time by an agent that is neither A4
nor A6, from the text of sections 6.2 to 6.4 alone, with the request text
committed alongside the script. The disagreement rate enters the pre-registration
at the next version, in the amendment record, not in a later footnote. Until it
has run, P3 is passed on the text and not on the test.

---

## 7. The aliasing problem, confronted (leakage item C2)

A6 calls this the strongest objection to the direction. This section states it as
an identification problem, measures how much separation the available Korean fires
actually give, and fixes in advance what is reported if the two cannot be
separated.

### 7.1 The identity

Write `F` for a fire's calendar year, `Y` for an observation calendar year and
`t = Y - F` for years since fire. Inside the observation window these are bound
by `t = Y - F` **exactly**. This is the age, period and cohort identity, and the
consequence is the standard one: with a free calendar-year effect and a free
fire-cohort effect in the same model, **the linear component of the years-since-
fire term is not identified**, while its curvature is. It is not a noise problem
and no amount of data inside a fixed set of cohorts fixes it.

`research/landslides/design/aliasing_separation.py` checks this by rank rather
than asserting it. On every cohort set tested, the design matrix
`[1, t, year dummies, cohort dummies]` carries a rank deficiency of three, which
is two ordinary dummy traps plus the identity, and adding a `t^2` column raises
the rank by one. So the curvature is identified where the linear term is not.
This holds for the committed record and for every counterfactual record tested,
which is the point: the longer record improves precision, not identifiability.

### 7.2 How much separation the available Korean fires actually give

From `kfs_fire_stats_csv`, status `verified`, report years 2022 to 2025 across
2,020 rows. The landslide occurrence record covers 2021 to 2025.

**Fires by report year and size floor:**

| burned area floor | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| at least 1 ha | 128 | 111 | 32 | 72 |
| at least 10 ha | 26 | 32 | 1 | 19 |
| at least 30 ha | 14 | 19 | 0 | 15 |
| at least 100 ha | 11 | 8 | 0 | 6 |

**So the first fact is that there are not four usable cohorts, there are three.**
The 2024 fire year contains exactly one fire of at least 10 ha, at 19.79 ha, and
none at all above 30 ha. Total burned area by year runs 24,797 ha in 2022, 4,988
ha in 2023, 131.93 ha in 2024 and 105,011 ha in 2025, the last dominated by the
Uiseong pair that the registry records as a known duplicate. A cohort that
contributes 131.93 ha nationally cannot carry a contrast.

**The second fact is the reach.** At the 100 ha floor the populated cells are:

| fire year | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| 2022 | t=0 | t=1 | t=2 | t=3 |
| 2023 | | t=0 | t=1 | t=2 |
| 2025 | | | | t=0 |

Eight populated cells, and the observable values of years since fire are
**0, 1, 2 and 3**. The number of distinct calendar years in which each is
observed is three for `t=0`, two for `t=1`, two for `t=2` and **one** for `t=3`.
That last row is the whole of the evidence at three years since fire: one cohort,
one calendar year.

**The third fact is the summary.** The exposure-weighted `R^2` of `t` on calendar
year dummies over the cell grid is 0.4769 weighted by fire count and 0.2124
weighted by burned area, so the share of `t`'s variation that survives a free
calendar-year effect is 0.5231 and 0.7876 respectively, and the variance inflation
on the `t` coefficient is 1.9 and 1.3.

**Those last numbers look reassuring and they are a ceiling, not an estimate.**
The cell grid gives every cohort equal weight in every later year, as though every
burned hectare stayed in the risk set with equal exposure for the rest of the
window. The realised design is weighted by storms, of which the record carries
twenty-four, and by assignable units, of which the count is not yet known. Every
separation figure in this section is therefore an upper bound on the separation
the fit will have, and section 22 requires the realised figure to be recomputed on
the fitted design matrix and reported beside it.

### 7.3 What would separate them, stated precisely

Fires that started in different calendar years give overlapping years-since-fire
values at different calendar times, so the design leans entirely on having several
fire years. The table in 7.2 is the entire separation available. Adding one
pre-2022 cohort helps materially: with a 2019 cohort added, the same script returns
thirteen populated cells, a maximum `t` of six, and `t=2` observed in three
distinct calendar years instead of two. With cohorts back to 2011 the `R^2` of `t`
on calendar year falls to 0.033 and every `t` from zero to ten is observed in five
distinct calendar years.

**So the single thing that most improves this direction is a longer exposure
record, and it is already a human gate.** WJ-006 is the drafted request for the
longer Korea Forest Service record, and WJ-001 unblocks the statistics API that
may reach back on its own. Section 18 makes the dependency explicit.

### 7.4 The mitigation the checklist asks for, and its limit

Item C2's mitigation is to include the triggering rainfall explicitly at the event
level so the time term is not carrying the weather. This design does that, and it
does something the checklist does not ask for, which is worth stating because it is
where the design's only real escape lies.

**The calendar-year effect need not be a national year factor.** Storm rainfall
is measured at the unit, from radar, so it varies within a year and across space.
Once the period effect is replaced by measured, spatially varying storm rainfall,
the exact `t = Y - F` identity no longer binds the design matrix, because the
rainfall at fire A's location in 2023 is not the rainfall at fire B's location in
2023. The identity binds the **residual** calendar effect only.

**The limit, stated plainly.** That residual calendar effect is exactly the
reporting-attention term of section 6.5, and it is the part nobody can measure.
So the escape converts an exact aliasing into an assumption: that after
conditioning on measured storm rainfall and on the measured reporting covariates,
the remaining calendar-year variation is exchangeable across cohorts. **That
assumption is not testable inside this design.** Section 21 forbids any sentence
that implies it was tested.

### 7.5 The maximum observable window, which is the harder problem

Separation is the objection A6 raised. Underneath it sits a support problem that
this document rates worse, and it is put here so it is not mistaken for a
limitation.

The question asks how long the elevated period lasts. Sidle 1992 puts the analogous
post-harvest effect as strongest in years one to ten and tapering to about
twenty-five years, and that is prior art for the functional shape only, from a
post-harvest model with no Korean data. **The committed exposure record observes
years since fire of zero, one, two and three, and the value three from a single
cohort in a single calendar year.** If the true elevated period is longer than
three years, this design cannot see its end. The estimate is right-censored below
the quantity being estimated.

This is not fixed by better units, better rainfall, better severity or more
storms. It is fixed only by a longer record.

### 7.6 What is reported if the two cannot be separated, fixed now

Three calendar specifications are fitted, all three are reported, and no one of
them may be promoted after the fact.

- **M-A, free calendar.** A free calendar-year factor alongside the years-since-
  fire term, with a sum-to-zero constraint on the year factor and a declared
  sensitivity over that constraint. The linear component of `t` is not identified
  here, so what is read from M-A is the **curvature only**, and the constraint's
  influence is reported as the spread of the `t` term across the declared
  constraint grid.
- **M-B, measured period.** The calendar factor replaced by measured storm
  rainfall and the measured reporting covariates of section 6.5, with no free
  year term. This is the **primary** specification.
- **M-C, no period term.** Neither a year factor nor reporting covariates. This is
  the specification that would produce the most attractive recovery curve and it
  is reported so that a reader can see how much of any curve is an artefact of
  leaving the calendar out.

**The reading rule, fixed before any fit.**

1. If the sign of the years-since-fire term at `t=0` differs across M-A, M-B and
   M-C, or if the ordering of the fitted values at `t=0,1,2,3` differs across
   them, **failing condition F2 fires and the direction reports no clock.** What
   it reports instead is the three specifications side by side and the statement
   that the Korean fires available do not separate the recovery curve from the
   calendar.
2. If the sign and ordering agree across all three, the reported quantity is
   **not a recovery window**. It is (a) the identified curvature of the fire term
   with its interval, (b) the fitted fire term at each of `t=0,1,2,3` with its
   interval, and (c) an explicit statement that `t=3` is the largest value
   observed and that the design cannot bound the window above.
3. The hedged sentence template that any such result may use is fixed in section
   21.2, and rule RC-003 of `research/FORBIDDEN_CLAIMS.md` governs it.

---

## 8. The unit of analysis, confronted (leakage item C10)

A6 has stated it will not sign a slope-unit model whose unit-assignment error has
not been quantified. This section quantifies the part that can be quantified
today, decides, and pre-registers the measurement that decides the rest.

### 8.1 The measured ceiling on geocoding precision

`research/landslides/design/address_precision.py`, over all 5,118 records, reading
only the four address columns.

| address fields present | records | share | finest rung available |
|---|---|---|---|
| 시도, 시군구, 읍면도, 리 | 4,895 | 95.64 per cent | a 리 |
| 시도, 시군구, 읍면도 | 219 | 4.28 per cent | a 읍면동 |
| 시도, 시군구, 리 | 3 | 0.06 per cent | a 리, with no 읍면동 |
| 시도, 시군구 | 1 | 0.02 per cent | a 시군구 |

**And the decisive number: zero of 5,118 records carry a lot number in the finest
address field.** Not a low share. Zero. The finest field holds a 리 name, and 1,427
distinct such names appear.

`GeocodePrecision.PARCEL` is defined in `research/shared/geo/geocode.py` as a 산
lot number resolved to a specific parcel. **That rung is unreachable for the
entire record, and no geocoder can change that, because the lot number is not in
the string.** This is a property of the data, measurable today, with no API key
and no DEM. It is the single most useful fact this document contains about the
unit question.

### 8.2 A gap in the committed precision ladder

The ladder is `PARCEL`, `EUPMYEONDONG_CENTROID`, `SIGUNGU_CENTROID`,
`UNRESOLVED`. The modal record in this file bottoms out at a **리**, which is
finer than a 읍면동 and coarser than a parcel, and the ladder has no rung for it.

Carrying these records at `EUPMYEONDONG_CENTROID` would understate their precision
for 95.64 per cent of the file, and the rule that levels are never mixed silently
would then be satisfied in letter while throwing away the one thing that makes the
record spatially usable.

**Recommendation, which A4 does not own and therefore only recommends.** Add a
`RI_CENTROID` rung between `PARCEL` and `EUPMYEONDONG_CENTROID` in
`research/shared/geo/geocode.py`. That file is A1's. It is raised as open question
Q1 in `research/landslides/OPEN_QUESTIONS.md` and as a request in the round report,
not edited here.

### 8.3 Why that kills the slope unit, and why the terrain argument kills it twice

The confusion set of a record is the polygon of the finest unit its address
resolves to, restricted to forest land. For 95.64 per cent of the record that is a
법정리 polygon. A slope unit is very much smaller than a 법정리. So assigning a
record to a slope unit is not a measurement, it is a draw from a distribution over
many slope units inside the 리, and the argmax has no claim to be the right one.

The independent terrain argument of section 5.2 reaches the same place from the
other side: at 30 m posting, the DEM cannot resolve the convergent hollow where a
shallow Korean landslide initiates, so even a perfect coordinate would be assigned
to a unit whose defining terrain the DEM has smoothed away.

A6's checklist names the escape and this document takes it. **The primary unit is
the catchment.** The slope unit is demoted to a conditional secondary, and section
8.5 gives the gate that decides whether it runs at all.

### 8.4 The assignability measurement, pre-registered before it is used

The point of this subsection is that the assignment error is **measured**, not
assumed, and measured without needing any ground truth and without touching the
outcome.

For a unit partition at scale `s`, and for a confusion polygon `S`, define the
concentration `c(S, s) = max_u area(S ∩ u) / area(S)` over units `u`. Define `S`
assignable at scale `s` if `c(S, s) >= q`, with `q` declared at 0.50.

**Measurement M1, the assignable share, computed outcome free.** Run the
concentration over the **full enumeration of Korean 법정리 polygons restricted to
forest land**, not over the record's realised 리. That makes M1 a property of the
geometry of Korean administrative units against the geometry of the catchment
partition, with no landslide data in it at all. Report `A(s)`, the share of 리
polygons assignable at scale `s`, for every scale in the ladder of section 8.5.

**Measurement M2, the terrain dependence, which is what item C10 actually
alleges.** C10's claim is that the assignment error is worst where the terrain is
steepest. That claim is testable: stratify the 법정리 enumeration by the steep-area
fraction of each polygon computed from the DEM, and report `A(s)` within each
stratum. If `A(s)` falls monotonically with steepness, C10 is confirmed on Korean
geometry and the number is in the artifact. If it does not, that is also reported.
Either way the allegation stops being a worry and becomes a measurement. M2 is
outcome free.

**Measurement M3, covariate destruction.** Assignment error only matters to the
extent that it destroys a covariate. For each covariate of section 9, compute the
share of its total variance that lies **between** units at scale `s` rather than
within them, over the full national forest-land partition. A covariate whose
between-unit share falls below a declared floor of 0.30 at the chosen scale is
**dropped from the primary model**, because at that scale the unit no longer
carries the covariate. M3 is outcome free and it is the measurement that decides
which covariates survive coarsening.

**Measurement M4, the realised assignable share.** The same concentration computed
over the record's own confusion sets, reported per year and per rung. M4 touches
the outcome's addresses, so it runs once, after the primary scale has already been
fixed by M1 to M3, and it can only shrink the sample, never change the scale.
Fixing the order this way is deliberate: it stops the scale being chosen to
maximise the number of records retained, which would be selecting the unit against
the outcome.

### 8.5 The scale ladder, the gates, and what happens at each outcome

The scale ladder, declared now, from fine to coarse: the slope unit; the catchment
at `A_min` of 0.25 square kilometres; at 1 square kilometre; at 4 square
kilometres; the 리; the 읍면동; the 시군구.

**Gate U1.** The primary scale is the **finest** scale on the ladder at which
`A(s) >= 0.60` in measurement M1 **and** at least six of the covariates of section
9 clear the M3 floor of 0.30. Both numbers are fixed now and do not move.

**Gate U2, the slope-unit secondary.** The slope-unit analysis runs only if the
slope unit itself passes U1. Given section 8.1, A4's expectation, recorded here so
it can be scored later, is that it will not, and the pre-registered consequence is
that the slope-unit arm is simply not run and is reported as not run, with its
`A(s)` value quoted.

**Gate U3, failing condition F3.** If no scale finer than the 시군구 passes U1,
the direction does not fit a unit-level hazard model at all. What it reports
instead is the assignability table itself, which is a real and publishable
finding about what Korean address-level landslide records can and cannot support,
together with the statement that the recovery-window question is not answerable
from this record at any spatial resolution.

### 8.6 Precision classes are a covariate, not a filter

Per item C10 and item A9, the rung reached is carried as a covariate on every
assigned record and is never used to drop rows by inspection. Records excluded at
step 4 of section 6.3 are excluded by the declared `q`, which is a function of
geometry, not of the outcome. The exclusion counts are reported per rung and per
year, and the same enrichment check the roads direction pre-registers in its
condition C3 is run here: the distribution of the excluded records' steep-area
fraction is compared against the retained records', and both readings are written
in advance. Enrichment of the excluded set in the steep stratum means the
censoring runs against the units the model is about, which attenuates the terrain
coefficients and is reported as such.

---

## 9. Covariates and their sources (P4)

`knowable at` is the moment the value could have been written down. For a storm
starting at time `T`, a covariate is admissible if its value is fixed before `T`.

| name | definition | unit | registry id | knowable at | derived from anything touching the label |
|---|---|---|---|---|---|
| `rain_max_1h` | maximum hourly rainfall at the unit during the storm | mm per hour | `kma_radar_qpe` | storm end | no |
| `rain_total` | accumulated rainfall at the unit during the storm | mm | `kma_radar_qpe` | storm end | no |
| `rain_ante_7d` | accumulated rainfall in the seven days before the storm | mm | `kma_radar_qpe` | storm start | no |
| `rain_station_check` | the same three from the nearest gauge, for a radar-versus-gauge check | mm | `kma_asos_aws` | storm end | no |
| `slope_steep_frac` | area fraction of the unit's forest land above 25 degrees | fraction | `dem_korea` | static | no |
| `slope_steep_mean` | area-weighted mean slope of that steep fraction | degrees | `dem_korea` | static | no |
| `curvature_conv_frac` | area fraction with negative plan curvature | fraction | `dem_korea` | static | no |
| `twi_p90` | ninetieth percentile topographic wetness index in the unit | index | `dem_korea` | static | no |
| `area_forest` | forest area of the unit, the exposure offset | square kilometres | `dem_korea`, land cover | static | no |
| `soil_depth_class` | modal soil depth class | class | `naas_soil_map` | static | no |
| `soil_texture_class` | modal texture class | class | `naas_soil_map` | static | no |
| `geology_class` | modal lithology class | class | `kigam_geology_map` | static | no |
| `burned` | the unit is burned for this storm, section 6.4 | binary | `sentinel2_l2a_dnbr`, `kfs_fire_stats_csv` | fire date | no |
| `t_since_fire` | years since the most recent qualifying fire | years | `kfs_fire_stats_csv` | fire date | no |
| `severity_dnbr` | area-weighted mean dNBR over the burned part | index | `sentinel2_l2a_dnbr` | fire end | **yes, see 9.3** |
| `species_pine_frac` | pre-fire pine-dominated area fraction | fraction | `kfs_forest_type_map` | pre-fire | no |
| `ownership_class` | modal `시설구분_등급` ownership class of the unit's forest land | class | `kfs_landslide_history` metadata, and the forest ownership layer | static | **yes, see 9.4** |
| `dist_road_m` | distance from the unit centroid to the nearest mapped road | metres | `base_map_linear_features` | static | no |
| `dist_builtup_m` | distance to the nearest built-up polygon | metres | `base_map_linear_features` | static | no |
| `salvage_frac` | area fraction salvage-logged since the fire | fraction | `kfs_salvage_logging` | logging date | no |
| `geocode_rung` | the precision rung the assigned record reached | ordinal | `vworld_geocoder`, `kr_admin_boundaries_ri` | at assignment | no |
| `storm_index` | the enumerated storm identifier, a grouping variable | id | `kma_radar_qpe` | storm end | no |

Two registry ids in that table do not exist yet, `kr_admin_boundaries_ri` and
`kfs_salvage_logging`. A4 does not own `research/data/REGISTRY.yaml` and has not
edited it. Both are requested in `research/landslides/DATA_REQUIREMENTS.md` and in
the round report, with the proposed ids used here so the eventual entries match.

### 9.3 The severity covariate's paragraph

`severity_dnbr` is derived from the same Sentinel-2 scene pair that defines the
burn perimeter, and the perimeter defines the `burned` covariate. So severity and
the exposure share a source, in the family of leakage item C4. Unlike the roads
direction's item B1, severity here does not touch the **outcome**: the outcome is
the occurrence record, which is an administrative file with no imagery in it. What
severity does share is a **search prior** in the weaker sense, because
administrative attention after a fire is greater where the fire burned hot.

Pre-registered treatment: `severity_dnbr` is in the primary model, its coefficient
is reported inside the fire term and never as a separate mechanism, and a declared
sensitivity run drops it entirely. If the years-since-fire term moves materially
when severity is dropped, the direction reports both and says which is which.

### 9.4 The ownership covariate's paragraph

`시설구분_등급` is a field of the occurrence record, so an ownership covariate
built from that field alone would be defined only on rows that have a record,
which is definitionally outcome-derived. It is therefore **not** built from that
field. It is built from the national forest ownership layer, which covers every
unit including those with no record, and the occurrence record's field is used
only to confirm that the record's own ownership class matches the unit it was
assigned to. That check is a diagnostic reported at a key path and is never a
covariate.

### 9.5 The covariate firewall

A single committed audit script enumerates every column entering the design matrix
and asserts that none of them was computed from the outcome column, from
`재난구분`, or from `피해물량(ha)`. It runs before each fit and fails the fit on a
violation. Its whitelist is `ownership_check` and `storm_index`, both of which are
grouping or diagnostic quantities and neither of which is a predictor.

---

## 10. The model form (P5)

### 10.1 Software, seeds and convergence, fixed in advance

PyMC on one laptop, CPU only. Four chains, 1,000 tuning draws and 1,000 sampling
draws per chain, target acceptance 0.9, seed 20260916. Convergence gates, fixed
now: R-hat at or below 1.01 for every parameter, bulk and tail effective sample
size at or above 400 for every parameter, and zero divergent transitions after
reparameterisation. **If a gate is not met**, the ordered remedy is
non-centred reparameterisation of the hierarchical terms, then raising target
acceptance to 0.95, then raising tuning draws to 2,000. If all three fail, the fit
is recorded as non-converged in the fit log and the model is **not** simplified to
make it converge, because simplifying a model until it converges selects the model
on a diagnostic that depends on the outcome, which is leakage item A8.

### 10.2 The likelihood

For unit `u` and storm `s`, let `y_{u,s}` be the count of occurrence records
assigned to that cell. Then

```
y_{u,s} ~ NegativeBinomial(mu_{u,s}, phi)
log mu_{u,s} = log(area_forest_u) + log p_report_{u,s} + eta_{u,s}
```

`log(area_forest_u)` is a fixed offset. `log p_report_{u,s}` is the reporting term
of section 6.5, with coefficients estimated rather than fixed. `eta_{u,s}` is the
hazard linear predictor of section 10.3.

**Why a count and not a Bernoulli.** Address-level data does not identify which
slope inside the confusion set failed, so a unit-level binary label would be
manufactured from the assignment rather than observed. A count with an area offset
is exactly what an areal record supports. The quantity the brief asks for, the
probability that a unit fails in a storm, is recovered as `1 - exp(-mu_{u,s})` and
is reported as a derived quantity at its own key path, with the note that it is a
transformation of the fitted intensity and not a separately estimated probability.

**Why negative binomial and not Poisson.** Reported landslides cluster within a
unit and a storm, so a Poisson would understate the variance and narrow every
interval. `phi` is estimated. A Poisson fit is a declared sensitivity run and both
are reported.

### 10.3 The linear predictor and the root-strength term

```
eta = beta_0
    + f_rain(rain_max_1h, rain_total, rain_ante_7d)
    + f_terrain(slope_steep_frac, slope_steep_mean, curvature_conv_frac, twi_p90)
    + soil + geology
    + burned * [ alpha_sev * severity_dnbr + g(t) ]
    + gamma_salvage * salvage_frac
    + calendar term, per the specification M-A, M-B or M-C of section 7.6
    + b_block + b_storm
```

`g(t)` is the root-reinforcement term. Following Sidle 1992 **for its functional
shape only**, it is the loss of net root cohesion relative to the unburned state,
written as an exponential decay of the old root network plus a sigmoid recovery of
the new one:

```
g(t) = kappa * [ D * exp(-lambda_decay * t)
                 - R / (1 + exp(-k_grow * (t - t_mid))) ]
```

`kappa` scales root cohesion loss into the log rate. `D` is the decaying old-root
contribution, `R` the recovering new-root contribution, `lambda_decay` the decay
rate, `k_grow` the regrowth steepness and `t_mid` the regrowth midpoint. In the
species arm, `lambda_decay`, `k_grow` and `t_mid` each take a pine value and a
broadleaf value, and the unit's value is the pine-fraction-weighted combination.

**Sidle 1992 supplies the shape and nothing else.** It is a post-harvest model,
not a post-fire model, and it uses no Korean data. Its published constants are
not imported. Every parameter above is estimated. Where a prior is needed it is
weak, per item A12 and item C9, and every one carries the flat-prior sensitivity
run of section 16.

### 10.4 Priors, each with its justification

| parameter | prior | why |
|---|---|---|
| `beta_0` | Normal(-8, 2) on the log rate per square kilometre per storm | recorded landslides per forest square kilometre per storm are rare; this puts most mass between about one in 30,000 and one in 20 without excluding either |
| rainfall spline coefficients | Normal(0, 1), second-difference penalty | a smooth, monotone-tending response without imposing monotonicity |
| terrain and soil coefficients | Normal(0, 1) on standardised covariates | a unit change of one standard deviation rarely moves a log rate by more than about two |
| `kappa` | HalfNormal(1) | sign is fixed by the physics, root loss cannot increase strength; magnitude is left free |
| `D`, `R` | Dirichlet-like on the simplex, `D + R <= 1` | both are fractions of the pre-fire root contribution and cannot exceed it |
| `lambda_decay` | LogNormal(log(0.5), 0.75) | a weak prior centred on a half-life of the order of a year, wide enough to cover a half-life from a few months to several years. Sidle 1992 motivates the scale and supplies no number |
| `k_grow` | LogNormal(log(1.0), 0.75) | as above, on the regrowth steepness |
| `t_mid` | LogNormal(log(5), 0.6) | a weak prior on a regrowth midpoint of a few years. **This prior is doing more work than the data can check**, see section 10.5 |
| `phi` | Gamma(2, 0.5) | keeps the negative binomial away from both the Poisson limit and a degenerate over-dispersion |
| `sigma_block`, `sigma_storm` | HalfNormal(0.5) | random-effect scales on the log rate; 0.5 keeps the prior predictive from producing implausible order-of-magnitude swings between blocks |

### 10.5 Identifiability, and the parameters this design cannot pin down

P5's acceptance test says a model form where everything is identified is a model
form nobody has thought about hard enough. Four parameters are named.

1. **`t_mid`, the regrowth midpoint, is not identified.** Its prior is centred at
   five years and the data reach `t = 3`. The posterior for `t_mid` will be a
   restatement of its prior. Pre-registered consequence: `t_mid` is **not
   reported** as an estimate, its prior-to-posterior contraction is reported as a
   diagnostic at a key path, and any sentence about when regrowth reaches its
   midpoint is forbidden by section 21.

2. **`D` and `R` are not separately identified from a single decline.** A decline
   in the fire term over `t=0..3` is consistent with fast old-root decay and slow
   regrowth, or with slow decay and fast regrowth. There is one observed decline
   and two latent components, which is the same shape as item B8 in the roads
   direction. **There is no second observable in this design that separates
   them.** Pre-registered consequence: only the composite `g(t)` is reported, the
   decomposition into `D` and `R` is presented as a structural assumption and not
   as an estimate, and the coefficients are named as coefficients of a combined
   root-strength term in the abstract, not only in a limitations paragraph.

3. **The linear component of `g(t)` against the calendar**, per section 7. Fixed
   in advance by section 7.6.

4. **The hazard rate and the reporting probability are not separately
   identified.** Both enter `log mu` additively and the record observes only their
   product. The reporting term is identified only to the extent that its
   covariates, ownership and distance to roads and built-up land, are not also
   hazard covariates, and distance to roads is both. Pre-registered consequence:
   the road coefficient is reported inside the reporting term, is never given a
   mechanism, and section 21 forbids any sentence attributing failure to roads.

### 10.6 The control units, and the matching design declared in advance

Leakage item C5: unburned controls are not comparable because fires do not burn at
random.

The primary design is **not** a matched design. It is a regression over all forest
units in the risk set, burned and unburned, with the terrain, soil and geology
covariates of section 9 entering directly. The matched design is a declared
secondary, specified now so it cannot be introduced as a rescue.

The secondary matches each burned unit to unburned units on a propensity score
built from `slope_steep_frac`, `slope_steep_mean`, `curvature_conv_frac`,
`twi_p90`, `soil_depth_class`, `geology_class`, elevation, aspect and
`dist_road_m`, within the same province and the same storm. **The balance
statistic reported, whichever way it comes out, is the standardised mean
difference on every one of those covariates before and after matching, with a
declared threshold of 0.10 above which balance is reported as not achieved.** The
propensity model is fitted inside the training fold, per item A1.

Control units inside the fire perimeter but unburned are **not** used, because
they are inside the fire's own weather and drainage, and using them would
understate the contrast. That choice is declared now.

### 10.7 Random effects and what they absorb

`b_block` is a spatial-block random intercept and absorbs the regional part of
geology, soil mapping quality and administrative practice that the covariates
miss. `b_storm` is a storm random intercept and absorbs the synoptic setting and
the storm's national reporting attention.

**The held-out prediction rule, which P5 and item B7's argument require to be
fixed before the fit.** A held-out block has no fitted `b_block`. The **primary**
prediction rule draws `b_block` from its hyperprior, which is the honest version.
Setting it to zero is a different model and predicts better. Both are reported and
the primary is the hyperprior draw. This is fixed now.

### 10.8 The physics link, and why it is reported as a range

The fitted `g(t)` is fed into a one-dimensional infinite-slope factor of safety

```
FS = [ c_soil + c_root(t) + (gamma - m * gamma_w) * z * cos^2(beta) * tan(phi) ]
     / [ gamma * z * sin(beta) * cos(beta) ]
```

and the critical rainfall, meaning the rainfall at which the factor of
safety reaches unity, is computed by years since fire.

**This is a model-implied quantity, not an estimate, and it is reported as a range
over a declared grid.** The reason is that soil depth `z`, friction angle `phi`
and the wetness ratio `m` are not measured at the unit anywhere in this design.
`naas_soil_map` supplies a depth class, not a depth. So the implied critical
rainfall is far more sensitive to the assumed `z` than to the fitted `g(t)`, and
reporting a single number would present an assumption as a result.

Declared grid: `z` in {0.5, 1.0, 1.5, 2.0} metres, `phi` in {28, 32, 36} degrees,
`beta` at the unit's `slope_steep_mean`, `m` in {0.5, 0.8, 1.0}. Every cell is
reported. **DeBano 2000 enters here and only here**: post-fire soil water
repellency plausibly raises `m` in the first year or two, and it is a non-Korean
source supplying a mechanism, not a number, so it enters as the declared
sensitivity of `m` at `t=0` and `t=1` across the grid above, never as a fitted
term. There is no Korean repellency dataset in the registry and this design does
not pretend to one.

Rule RC-005 governs every sentence in this subsection's outputs.

---

## 11. The species arm, confronted

### 11.1 The data does not exist and may never

`kfs_forest_type_map`, data.go.kr id 15093362, is registry status `pending`. It is
not downloadable: the portal bounces to a Korea Forest Service application form
requiring a stated purpose, which this program's scope rules treat as a human gate,
WJ-018. Its licence is KOGL Type 3, attribution with **no modification**, and
whether a derived pine-or-broadleaf covariate is permitted is an open licence
question, WJ-012.

### 11.2 The licence question, with A4's recommendation

A4 is not a lawyer and does not own this decision. The recommendation, for John:

- Computing a covariate from the layer, using it inside a model, and publishing
  only fitted coefficients is analytical use of the work and does not redistribute
  or alter it.
- Publishing a derived raster or vector layer that others could use in place of
  the original is the case a no-modification term most plausibly reaches.
- So the safe design is: derive the covariate, never publish a derived layer,
  publish coefficients and attribute the source. And ask the licensor, because the
  safe design costs nothing to declare and a wrong reading is not repairable after
  publication.

**Pre-registered consequence.** No derived forest-type layer is published from this
direction under any outcome. That is fixed now, so it is not a decision made under
deadline pressure later.

### 11.3 What survives if the map never arrives

The recovery-window arm survives intact. It needs fire perimeters, fire dates,
severity, terrain, soil, geology and rainfall. It does not need species. So the
loss of the forest type map costs the direction its secondary hypothesis and
nothing else.

The species arm does not survive in its pre-registered form. The fallbacks, in the
declared order in which they are tried:

1. **A Sentinel-2 phenological discriminator.** Korean broadleaf stands green up
   sharply in spring and senesce in autumn; pine does not. A pre-fire winter and
   summer composite of a vegetation index separates needleleaf from broadleaf
   canopy over the same pixels the perimeter comes from. It needs
   `sentinel2_l2a_dnbr`, which is blocked on WJ-001, but not the forest type map.
2. **Withdrawal.** If neither the map nor a validated discriminator exists, the
   species arm is withdrawn and reported as withdrawn, with the reason.

### 11.4 The catch in the fallback, stated rather than discovered

A phenological classifier has its own misclassification rate, and **the only
Korean reference layer against which that rate could be measured is the forest
type map that the fallback exists to replace.** So the fallback covariate cannot
be validated on Korean data in the case where it is needed.

Pre-registered consequence, fixed now: if the species arm runs on the phenological
classifier with no Korean validation, then

- it is reported as a **secondary** analysis, never as a primary result;
- a misclassification sensitivity is run over a declared grid of classifier error
  rates, 5, 10 and 20 per cent symmetric, and the species contrast is reported at
  every cell of that grid, because non-differential misclassification of a binary
  covariate attenuates its contrast toward zero and a null is therefore weak
  evidence against a difference;
- every sentence about the species contrast carries the words unvalidated
  classifier, and rule RC-004 governs it;
- **failing condition F5 applies**: if the two decline parameters are not
  separated at the declared threshold of section 15.5, the arm is withdrawn rather
  than reported weakly.

### 11.5 The confounding that does not go away with better data

Leakage item C6: in Korea pine occupies dry ridges and thin soils, broadleaf
deeper and moister soils. A species contrast in landslide timing may be a soil
depth contrast, a slope contrast or a management contrast.

The design conditions on `soil_depth_class`, `soil_texture_class`,
`slope_steep_frac`, `slope_steep_mean` and elevation, and reports the standardised
mean difference of each between pine-dominated and broadleaf-dominated units,
whichever way it comes out. But soil depth is a **class**, not a depth, so the
conditioning is coarse, and residual confounding by depth is not removed by it.
Section 21 scopes the species claim accordingly. A6 has already advised demoting
this arm to a secondary; this document demotes it, and section 11.4 does so
permanently rather than conditionally.

### 11.6 Salvage logging, a third identification problem

The brief asks for salvage logging to be handled as a separate exposure. In Korea
post-fire salvage of burned timber is carried out in the first years after a fire,
which is **the same window as the steep part of the root-decay curve**. So salvage
extent and years since fire are confounded by construction, and the confounding
runs in the same direction: salvage removes stumps and disturbs soil, which lowers
root reinforcement, at exactly the times `g(t)` says root reinforcement is falling
anyway.

**There is no salvage-logging spatial dataset in `research/data/REGISTRY.yaml`.**
It is requested as `kfs_salvage_logging` in `DATA_REQUIREMENTS.md`. If it never
arrives, `salvage_frac` cannot be built, and the pre-registered consequence is
that `g(t)` is reported as a combined root-decay and post-fire-management term and
is named that way in the abstract, not in a limitations paragraph. That is the
same remedy as section 10.5 item 2 and it is applied for the same reason.

---

## 12. Held-out sets, named in advance (P6)

### 12.1 The call

```python
from research.eval.splits import spatial_block_cv, primary_split_spec, splits_fingerprint

spec = primary_split_spec("landslides")      # not retyped, read from PRIMARY_SPLITS
splits = spatial_block_cv(xs, ys, fire_ids=fire_ids, **spec["kwargs"])
fingerprint = splits_fingerprint(splits)
```

The keyword arguments are read from `PRIMARY_SPLITS["landslides"]` and are
`block_size_m=5000.0`, `n_folds=5`, `buffer_m=1000.0`, `seed=20260916`,
`require_fire_disjoint=True`. They are not retyped in any fitting script, so a
divergence between the registered spec and the fit is impossible rather than
merely discouraged. `xs` and `ys` are unit centroids in EPSG:5186 metres; the
splitter refuses degrees and section 12.4 shows that refusal firing.

Random splits are forbidden, per item C1. No random split appears anywhere in this
design, including inside any inner loop.

### 12.2 The fingerprint, and why it cannot be pinned at v0.1

The fingerprint is a function of the unit coordinates. There is no DEM, so there
are no units, so there are no coordinates. The roads direction hit the same wall
and A6 accepted a fingerprint pinned at a later version as condition C8 of
`research/eval/signoffs/roads_v0.2.md`.

The same undertaking is made here, in the same shape: **the fingerprint is
computed by running the call above over the committed unit layout in its committed
row order, immediately after the layout is committed and before any outcome is
assigned to any unit, and is written into the `prereg:` block of the version that
does so.** A mismatch at verification is a refusal with no discussion, per P6.

The row order matters and is therefore fixed now: units are ordered by their
integer identifier, which is assigned by ascending `(block_row, block_col,
centroid_x, centroid_y)` in EPSG:5186, and that ordering is committed with the
layout.

### 12.3 A defect in the registered keyword arguments, found before it bit

`require_fire_disjoint=True` welds every block sharing a fire identifier into one
group. Unburned control units do not belong to a fire.
`research/landslides/design/split_demonstration.py` shows what happens on a
declared synthetic geometry of six fire clusters and 1,200 controls:

- giving every control the same sentinel identifier welds every control block in
  the country into a single group, and the splitter raises `LeakageRefusal` with
  the message that one spatial group cannot fill five folds;
- giving each control unit its own identifier yields five folds of equal size and
  a reproducible fingerprint.

**Pre-registered rule.** Every unit that is unburned for a given storm carries a
`fire_id` unique to that unit. Burned units carry the canonical identifier of the
fire that burned them. This is fixed now, and the demonstration is committed so
A6 can see the refusal fire.

A second observation from the same demonstration: with `require_fire_disjoint` on,
whole fires move between folds together, so the 1,000 m buffer rarely drops a row
in the fire-only geometry. The buffer still matters for control units, which are
not welded. `dropped_to_buffer` is reported per fold whichever way it comes out.

### 12.4 The sensitivity grid, declared now

Block size in {2000, 5000, 10000} metres, per the `why` field of
`PRIMARY_SPLITS["landslides"]`. Every cell is reported, not only the registered
5000 m. The buffer stays at 1,000 m across the grid.

**The justification item C1 demands, and its honest state.** C1 requires the block
to be larger than the correlation range of the triggering rainfall, which is a
property of the radar product. That product is behind an unset key, so the range
is **not yet measured**. The pre-registered procedure is to fit an empirical
variogram of storm accumulated rainfall over the enumerated storms, once the
product is in hand, report the range, and confirm that the registered 5,000 m
block exceeds it. **If it does not, the block size is raised to the next cell of
the declared grid that does, and that is a change to the split, so it is a new
version under section 4 of the protocol, not a tweak.** Saying so now is what
stops it being a tweak later.

### 12.5 The statement P6 asks for

No outcome value from any block has been looked at, by A4 or by anyone on A4's
behalf. Section 3.2 is the full record of what has been computed, and none of it
is an outcome. Sancheong 2025's held-out status is governed by section 3.3 and by
section 15.6.

---

## 13. The primary metric (P7)

### 13.1 One metric, one number

**The primary metric is the held-out mean log predictive density per storm-unit
cell**, averaged over the five spatial blocks, under specification M-B with the
primary held-out prediction rule of section 10.7.

It is a proper scoring rule, it is defined for a count outcome, and it does not
require a threshold, which matters because a threshold on a rare count is a
researcher degree of freedom.

### 13.2 The evaluation frame quoted beside it, per RC-008

Every quotation of the primary metric carries: the split scheme and its keyword
arguments, the fingerprint, the number of blocks, the number of storms, the number
of units, the number of non-zero cells, and the calendar specification. A number
quoted without that frame is not a result, and section 22 puts every one of those
at a key path so the frame is machine-readable rather than a promise.

### 13.3 The uncertainty, and the resampling unit

The interval is a block bootstrap **over storm by spatial-block clusters**, which
is the cluster of section 4.3, resampled with replacement, 2,000 resamples, seed
20260916. **Rows are never resampled.** Per item A11, resampling rows when rows are
clustered by storm gives an interval that is far too narrow, and in this design the
cluster count has a ceiling of 120 while the row count is in the hundreds of
thousands, so the error would be three orders of magnitude in the wrong direction.

### 13.4 Secondary metrics, labelled secondary and unpromotable

Held-out ROC-AUC of the binarised outcome; held-out Brier score of the derived per
cell failure probability; the balance statistics of section 10.6; the calibration
slope of predicted against observed counts by decile; and a **leave-one-fire-out
diagnostic**, which is labelled secondary for a specific reason: with three usable
cohorts, removing one removes a third of the information about the shape of the
curve, so it is a stability check and not an evaluation. None of these may be
promoted to primary after the fact under any outcome.

---

## 14. The baseline it must beat (P8)

**B0, intercept and exposure only.** Rate constant across all units and storms.

**B1, the primary baseline: rainfall and terrain, with no fire term.**
`rain_max_1h`, `rain_total`, `rain_ante_7d`, `slope_steep_frac`,
`slope_steep_mean`, soil class and geology class, negative binomial with the same
offset and the same reporting term, and **no `burned`, no `t_since_fire`, no
`severity_dnbr`**. Its own code path. Implementable in well under an hour.

B1 is the right baseline because it is the null of the hypothesis made into a
model: if a post-fire window exists, the fire terms must buy something over
rainfall and terrain alone, and if they do not, there is nothing to report.

**The margin, fixed now.** The full model beats B1 if its held-out mean log
predictive density exceeds B1's by at least **0.01 nats per cell** in at least
**four of the five** blocks, with the block bootstrap interval of the paired
difference excluding zero. Both parts must hold. The margin is a number, it is
fixed before any fit, and it can fire against the author.

---

## 15. What would count as the hypothesis failing (P9)

Written so it cannot be re-read as a success. A6 writes the same sentences in the
kill-shot file before the fit and A4 agrees to them.

**F1. The fire term at zero years since fire does not clear zero.** Threshold: the
90 per cent posterior interval of the fire term at `t=0` under specification M-B
covers zero, or lies below it. Reading: on Korean forest land, with this record,
conditional on rainfall, terrain and reporting, burned ground did not carry a
higher recorded landslide rate than comparable unburned ground. That is the
hypothesis failing, and it is reported as the result.

**F2. Instability across calendar specifications.** Threshold and reading fixed in
section 7.6. If it fires, the direction reports no clock.

**F3. The unit does not exist.** Threshold and reading fixed in section 8.5, gate
U3. If it fires, the direction reports the assignability table as its result and
fits nothing.

**F4. The baseline is not beaten.** Threshold fixed in section 14. Reading: the
fire terms buy nothing over rainfall and terrain on held-out blocks, so no window
is reported regardless of what any coefficient looks like in sample.

**F5. The species arm is not separated.** Threshold: the 90 per cent intervals of
the pine and broadleaf `lambda_decay` overlap and each contains the other's
posterior median. Reading: the species contrast is withdrawn, not reported as
suggestive. Given section 11.4's attenuation argument, a failure here is weak
evidence against a difference and the report says so in both directions.

### 15.6 Sancheong 2025, what it can and cannot test

Sancheong contributes years since fire of zero only, per section 3.3. So it is
held out as a test of the **level** of the fire term at `t=0` under an extreme
storm, and not as a test of the curve.

The reading is fixed now, in both directions. If the model under-predicts
Sancheong's recorded counts, that is consistent with the burn effect being real
and larger than the fitted level, and also with the storm being far outside the
rainfall range the model was fitted on, and the design cannot separate those two.
**So an under-prediction at Sancheong is reported and is not read as support for
the hypothesis.** If the model predicts Sancheong adequately, that is reported as
adequate and is not read as validation of the recovery curve, which Sancheong
contains no information about. The storm has been described to this program as
approximately a 145-year event; that return period is taken from the brief, is not
verified by A4, and is reported with that provenance or not at all.

---

## 16. Stopping rule and multiplicity (P10)

### 16.1 The enumeration of fits, fixed now

Primary fits, three: M-A, M-B, M-C of section 7.6. Baselines, two: B0 and B1.
Declared sensitivity runs, each reported whichever way it comes out:

| id | what varies |
|---|---|
| S-Q | assignability `q` in {0.35, 0.50, 0.70} |
| S-BLOCK | block size in {2000, 5000, 10000} m |
| S-STORM | `R_min` in {20, 30, 50} mm, `g_max` in {3, 6, 12} h |
| S-BURN | `f_burn` in {0.05, 0.10, 0.25} |
| S-SEV | severity dropped from the model |
| S-POIS | Poisson in place of negative binomial |
| S-FLAT | flat priors on `lambda_decay`, `k_grow` and `t_mid`, per item A12 |
| S-SOFT | soft assignment in place of argmax, per section 6.3 |
| S-RE | held-out random effect set to zero rather than drawn |
| S-SPEC | species misclassification grid, per section 11.4 |

That is the complete list. A fit not on it is a new version of this document.

### 16.2 The fit log, which is the mechanism

Every fit appends a row to `research/landslides/results/fit_log.jsonl`: the
timestamp, the model id, the split fingerprint, the seeds, the convergence
diagnostics, and whether the held-out primary metric was computed. **The count of
fits run before the reported one is reported**, per item A7, at a key path. The
held-out primary metric may be computed **once** per pre-registered model. A
second computation is a finding and is recorded as one.

### 16.3 Multiplicity

The family is three calendar specifications of one pre-registered fire term and
one pre-registered baseline comparison, each with a threshold fixed before any
data exists and none substitutable for another. That is a fixed table, not a
search, so no correction is applied. What protects the reading is the fixed table
plus the reported fit count, not a p-value adjustment. The sensitivity runs are
reported in full rather than summarised by their best cell, which is what stops
them becoming a search.

---

## 17. The leakage self-audit (P11)

Filled in by A4 **before** A6's independent pass begins, per condition C10 of
`research/eval/signoffs/roads_v0.2.md`. The difference between the two lists is
the finding.

### 17.1 Part A, cross-cutting

| id | severity | verdict | one line |
|---|---|---|---|
| A1 preprocessing inside the fold | CRITICAL | `mitigated` | every transform with parameters, including standardisation, the propensity model and the intra-cluster correlation, is constructed inside the fold loop; the rest are pure functions of constants declared here |
| A2 hyper-parameters and priors on the held-out set | CRITICAL | `mitigated` | every prior, threshold and grid is fixed in this document; the held-out primary metric is computed once per model and the count is reported |
| A3 feature selection before splitting | CRITICAL | `clean` | no screening step exists; the covariate list is section 9 and is fixed. The M3 covariate drop is a function of covariate geometry only, is outcome free, and runs before any fit |
| A4 feature support crossing the boundary | CRITICAL | `mitigated` | terrain covariates are unit-internal by construction; rainfall is unit-local; the 1,000 m buffer covers the residual. No per-county rate, no national mean, no kriged surface enters |
| A5 duplicates and near-duplicates | MAJOR | `present, scoped` | the registry records Uiseong 2025 as two same-day records with different areas; the complex rule collapses them and the count is reported. Near-duplicate occurrence records within one 리 and one storm cannot be distinguished from two real failures in an address-level file, and that is stated rather than fixed |
| A6 the analyst's memory | MAJOR | `present, scoped` | A4 knows Uiseong and Sancheong 2025 happened and knows Sancheong's inventory size. Section 3.3 is the record. No clean fix exists and the paper says so |
| A7 undocumented fits | MAJOR | `mitigated` | section 16.2, the fit log, and the reported count |
| A8 outcome-driven cleaning or stopping | MAJOR | `mitigated` | the convergence remedy ladder of section 10.1 forbids simplifying the model to make it converge; no outlier rule depends on residuals |
| A9 geocoder drift | MINOR | `mitigated` | the geocoder, its version and its date are recorded; the rung is a covariate, never a filter; and section 8.1 shows the ceiling is set by the address text, which no gazetteer edition changes |
| A10 outcome-dependent missingness | MAJOR | `present, scoped` | records unassignable to a unit are excluded by a geometric rule declared in advance, but the exclusion is enriched where terrain is steep, which is where the model is about. Section 8.6 pre-registers the enrichment check and its reading in both directions |
| A11 resampling unit | MAJOR | `mitigated` | section 13.3 resamples storm by block clusters, never rows, and the cluster ceiling of 120 is stated |
| A12 foreign quantity entering through a prior | MINOR | `mitigated` | Sidle 1992 supplies shape only; every rate is estimated; S-FLAT is the flat-prior sensitivity and is reported |

### 17.2 Part C, landslides

| id | severity | verdict | one line |
|---|---|---|---|
| C1 random splits forbidden | CRITICAL | `mitigated` | `spatial_block_cv` through `PRIMARY_SPLITS`, no random split anywhere. **One residual**: the block size is justified against a rainfall correlation range that cannot be measured until the radar product arrives; section 12.4 makes a re-registration mandatory if the registered block is too small |
| C2 time since fire aliased with calendar year | CRITICAL | `present, scoped` | section 7. The identity is exact, the rank deficiency is measured, the separation available is quantified and is a ceiling, and section 7.6 fixes what is reported when the two do not separate. **This is not resolved and this document does not claim it is** |
| C3 inventory completeness varies with time and campaign | CRITICAL | `present, scoped` | the record is administrative, not a mapped inventory, so the mechanism is reporting rather than mapping, section 6.5. The reporting term is not separately identified from the hazard term, section 10.5 item 4, and the vocabulary in section 21 carries the word recorded |
| C4 burn severity is both covariate and search prior | MAJOR | `mitigated` | severity does not touch the outcome, which is administrative; the attention mechanism remains and is handled by the S-SEV sensitivity and by reporting severity inside the fire term |
| C5 the unburned control is not comparable | MAJOR | `mitigated` | section 10.6: the primary is a regression, the matched design is a declared secondary with its balance statistic and threshold fixed, and in-perimeter unburned units are excluded by a declared rule |
| C6 species confounded with terrain and management | MAJOR | `present, scoped` | section 11.5. Soil depth is a class, not a depth, so residual confounding is not removed. The arm is demoted permanently, not conditionally |
| C7 the risk set in discrete time | MAJOR | `mitigated` | a unit does **not** leave the risk set after a recorded landslide, because an areal count over a unit admits repeat events and the record is not per-slope. Units with post-fire erosion control works are a treatment applied in response to risk; **there is no erosion-control dataset in the registry**, so this is stated as unmeasured and is requested in `DATA_REQUIREMENTS.md`. A unit whose recorded count exceeds one in a storm is reported as such rather than truncated |
| C8 Sancheong as a held-out stress test | CRITICAL | `mitigated` | section 3.3 is the full reading record, written before any fit. The count of 568 initiation points has set no prior, covariate, threshold or gate. Section 15.6 fixes what Sancheong can test, which is less than the brief assumed |
| C9 root curve parameters imported | MAJOR | `mitigated` | no Sidle constant is imported; every rate is estimated under a weak prior; S-FLAT reports the flat-prior run beside it |
| C10 address-level records and slope units | CRITICAL | `mitigated by scope cut` | section 8. Parcel precision is unreachable for 100 per cent of the record, measured. The primary unit is the catchment, the slope unit runs only behind gate U2, the assignment error is measured by M1 to M4 before it is used, and M2 tests C10's own steepness allegation directly |

### 17.3 Where A4 reads an item differently from A6

One item, recorded so the comparison in section 6 of the protocol has something to
land on. **C3.** The checklist's mechanism is mapping effort after a campaign. A4's
reading is that the committed record has no mapping campaign in it at all: it is
an administrative occurrence file classified by forest ownership, so the
completeness mechanism is reporting, which is driven by proximity to assets rather
than by imagery interpretation. A4 rates this **worse** than the checklist's
version, because reporting probability correlates with the road covariate that the
brief asks the direction to treat as a separate exposure, and nothing separates
them. If A6 reads C3 as satisfied by a detection model, A4's position is that no
detection model in this design is identified and section 21 must carry the
vocabulary instead.

---

## 18. Data provenance (P12)

| registry id | status | on disk | sha256 | what it supplies here | gate |
|---|---|---|---|---|---|
| `kfs_landslide_history` | **verified** | yes, 5,118 rows | `b7413e72b18b84c9c379a97111aef1f5794efb6590974679567e7d0c61c8211f` | the outcome | none |
| `kfs_fire_stats_csv` | **verified** | yes, 2,020 rows | `ae3e8426702168cb288761735dabe5b8a45f429ba7bc13e9f0318e838a92c153` | fire dates and sizes, the exposure cohorts of section 7 | none |
| `kfs_fire_state_history_csv` | **verified** | yes, 2,030 rows | `2e94ab963feeb9ad998761537a397e4d5912ac7f90e147487ef43aafc1512c00` | fire timing cross-check, the Uiseong duplicate | none |
| `dem_korea` | pending | no | none | the unit, all terrain covariates | WJ-011, WJ-001 |
| `kma_radar_qpe` | pending | no | none | the storm enumeration, all rainfall covariates | WJ-001 |
| `kma_asos_aws` | pending | no | none | the gauge cross-check | WJ-001 |
| `sentinel2_l2a_dnbr` | pending | no | none | fire perimeters, severity, the species fallback | WJ-001 |
| `naas_soil_map` | pending | no | none | soil depth and texture class | application gate |
| `kigam_geology_map` | pending | no | none | lithology class | request gate |
| `kfs_forest_type_map` | pending | no | none | the species covariate | WJ-018, WJ-012 |
| `vworld_geocoder` | pending | no | none | address resolution | WJ-001 |
| `base_map_linear_features` | pending | no | none | roads and built-up distance | WJ-011 |
| `kr_admin_boundaries_ri` | **not in the registry** | no | none | the 리 confusion polygons, which the whole unit decision rests on | new, see `DATA_REQUIREMENTS.md` |
| `kfs_salvage_logging` | **not in the registry** | no | none | `salvage_frac` | new, see `DATA_REQUIREMENTS.md` |

**Three of fourteen are verified, and none of the three carries a covariate or a
unit.** The sign-off state this document can reach at best is `signed with
conditions`, and the condition that holds everything shut is that eleven datasets
are pending and two do not exist as registry entries. A4 states that plainly
rather than presenting the direction as ready.

**Known defects designed against.** The Uiseong 2025 duplicate pair is collapsed
by the complex rule and the count is reported. The occurrence record's 220 nulls
in `상세주소_리` and four in `상세주소_읍면도` are carried as the rung column of
section 6.3, never imputed and never silently dropped. The `재난구분` field is a
multi-day window and is never parsed as a single date. Encoding is CP949 for both
Korea Forest Service files and the loaders handle it.

---

## 19. Compute and feasibility (P13)

One Apple M4 Pro laptop, CPU only, no HPC, no GPU training, no WRF. PyMC for the
Bayesian fits, scikit-learn for the propensity model of section 10.6.

Expected wall-clock, as an estimate to be checked rather than a promise. The
binding cost is the row count, which is units times storms. At an order of 20,000
units in the risk set and twenty-four storms the design matrix is of order half a
million rows, which a negative binomial hierarchical model in PyMC fits on a
laptop in a few hours per chain. The cross-validated fit is five folds times three
specifications, so of the order of fifteen fits.

**What gets cut if it does not fit, decided now and in this order.** First, the
rainfall spline is replaced by a quadratic. Second, the storm random intercept is
replaced by fixed storm effects, which is cheaper and is defensible with a small
storm count. Third, the sensitivity runs S-STORM and S-BURN are reduced to their
end cells. **The split, the primary metric, the baseline and the calendar
specifications are never cut**, because cutting any of those changes what the
result means.

Geometric preprocessing, the flow routing and the assignability measurements M1
to M4, is a one-off cost of the order of a day over a national 30 m DEM and is not
in the fitting loop.

---

## 20. Scope declaration (P14)

**Korea only.** Every dataset in section 18 is Korean in coverage. No foreign
dataset is pooled into any fit, and none appears as a fitting input.

Non-Korean sources used, each with the sentence rule RC-010 and P14 require:

- **Sidle 1992**, DOI 10.1029/92WR00804. Supplies the functional form of the root
  cohesion curve, an exponential decay of old roots combined with a sigmoid
  recovery of new roots. It is a post-harvest model, not a post-fire model, and it
  uses no Korean data. **Its data is not used for fitting and its published
  constants are not imported.** Every parameter in section 10.3 is estimated from
  Korean data.
- **DeBano 2000.** Supplies the mechanism of post-fire soil water repellency. It
  is not Korean. **Its data is not used for fitting.** It enters only as the
  declared sensitivity on the wetness ratio in section 10.8 and contributes no
  fitted term.
- **Lee et al. 2025**, named in the brief as the source of a Sentinel-2 delta
  MSAVI scar-mapping method, is **not verified** by A7 and is not used in this
  version. If the fallback inventory arm of section 11.4 is ever run, the method
  is cited and no non-Korean scar data is pooled.

Any foreign coefficient that ever entered as a prior mean would be foreign data
entering the fit, per item A12. None does. S-FLAT is the check.

---

## 21. What the result will not say (P15)

This is the section the poster and the paper quote. It is written now so it does
not have to be written under deadline.

### 21.1 The claims this direction will not make under any outcome

1. **No recovery window is stated as a fact.** Rule RC-003. Even under the most
   favourable outcome the design observes years since fire of zero to three and
   the largest value from one cohort in one calendar year, so no sentence of the
   form "burned Korean slopes return to baseline after N years" is written. The
   permitted shape is a hedged, right-censored lower bound.
2. **No pine-versus-oak difference is stated as established.** Rule RC-004. Under <!-- research-claim-ok: RC-004 -->
   every fallback in section 11 the species arm is a secondary, and under the
   phenological fallback it additionally carries the words unvalidated classifier.
3. **No hazard ratio or critical-rainfall shift is presented as measured.** Rule
   RC-005. The critical-rainfall quantity of section 10.8 is model-implied, is
   reported as a range over a declared grid of unmeasured soil parameters, and is
   never quoted as a single number.
4. **Nothing is called causal.** Fires do not burn at random and section 10.6
   balances only what it measures.
5. **No sentence attributes a landslide to a road.** The road coefficient lives
   inside the reporting term, per sections 6.5 and 10.5, and this design cannot
   distinguish a road that caused a failure from a road that caused a failure to
   be noticed.
6. **No sentence claims the calendar confound was removed.** Section 7.4 converts
   it into an untestable exchangeability assumption and that is what is reported.
7. **No sentence about the regrowth midpoint is written**, because `t_mid` is not
   identified, per section 10.5 item 1.
8. **No derived forest-type layer is published**, per section 11.2.
9. **No novelty claim.** Rule RC-009. A7 has not swept this direction and
   `research/lit/landslides_prior_art.md` is a stub.

### 21.2 The permitted vocabulary

The estimand is **the association between recorded landslide rate and years since
fire on Korean forest land, under the reporting practice of the Korea Forest
Service occurrence record**. Permitted: recorded landslide rate, the association
between years since fire and recorded rate, the fitted root-strength term, the
model-implied critical rainfall. Forbidden: landslide risk, the effect of fire on
slope stability, the recovery period, post-fire landslide susceptibility as a
measured quantity.

Every sentence carrying a number carries its interval and its evaluation frame, per
rule RC-008 and section 13.2.

**The enforcement gap, declared rather than promised.** A fixed vocabulary that
nothing checks lasts until the first hurried figure caption. The roads direction
was given condition C7 for exactly this and answered it with a local detector,
`research/roads/check_vocabulary.py`. This direction does not yet have one.
Building one is open question Q7, and until it exists the vocabulary here is a
promise and should be read as one.

---

## 22. The shape of the result artifact (P16)

### 22.1 The artifact

`research/landslides/results/landslides_v0.1.json`, a committed JSON file whose
keys are addressable by the registrar's dotted-path `dig()` helper. The staging
file is `research/landslides/numbers_staged.json`, written in `entry()` shape with
`git_commit` left empty for the orchestrator.

The design-side artifact already exists and is committed:
`research/landslides/design/design_numbers.json`, with key paths `aliasing`,
`address_precision` and `split_demo`. It contains no outcome quantity.

### 22.2 The key paths, named before the fit exists

| quantity | key path |
|---|---|
| primary metric | `held_out.primary_metric.value` |
| its interval | `held_out.primary_metric.ci_low`, `.ci_high` |
| its resampling unit | `held_out.primary_metric.resampling_unit` |
| baseline B1 metric | `baselines.B1.primary_metric.value` |
| the paired difference and its interval | `held_out.vs_B1.delta`, `.ci_low`, `.ci_high`, `.blocks_won` |
| evaluation frame | `held_out.frame.split_scheme`, `.kwargs`, `.fingerprint`, `.n_blocks`, `.n_storms`, `.n_units`, `.n_nonzero_cells`, `.calendar_specification` |
| fire term by years since fire | `fire_term.by_t.t0` ... `.t3`, each with `.median`, `.ci_low`, `.ci_high` |
| identified curvature | `fire_term.curvature.median`, `.ci_low`, `.ci_high` |
| across calendar specifications | `fire_term.by_specification.M_A`, `.M_B`, `.M_C` |
| F2 reading | `gates.F2.sign_stable`, `.ordering_stable`, `.fired` |
| root-strength parameters | `root_term.kappa`, `.lambda_decay`, `.k_grow`, `.t_mid_prior_contraction` |
| species arm | `species.lambda_decay_pine`, `.lambda_decay_broadleaf`, `.intervals_overlap`, `.classifier_source`, `.misclassification_grid` |
| model-implied critical rainfall | `physics.critical_rainfall.grid` (a list of cells, each with `z`, `phi`, `m`, `t`, `value`) |
| row and cluster counts | `counts.n_rows`, `.n_units`, `.n_storms`, `.n_clusters`, `.n_eff_design_effect`, `.rho` |
| label accounting | `labels.unassignable.by_reason`, `.by_year`, `.by_rung`, `.ties` |
| assignability measurements | `unit.M1_assignable_share_by_scale`, `.M2_by_steepness_stratum`, `.M3_between_unit_variance_share`, `.M4_realised_share`, `.chosen_scale`, `.U1_passed`, `.U2_passed` |
| aliasing, recomputed on the fitted design | `aliasing.realised.r2_t_on_calendar_year`, `.rank_deficiency`, `.calendar_years_per_t` |
| exclusion enrichment check | `labels.exclusion_enrichment.steep_fraction_excluded`, `.steep_fraction_retained` |
| balance statistics | `matching.smd_before`, `.smd_after`, `.max_smd_after`, `.balance_achieved` |
| convergence | `diagnostics.max_rhat`, `.min_ess_bulk`, `.min_ess_tail`, `.divergences` |
| fit accounting | `fits.count_before_reported`, `.log_path`, `.holdout_metric_computations` |
| Sancheong | `stress_test.sancheong.predicted`, `.observed`, `.reading` |
| sensitivity runs | `sensitivity.<id>.cells` for each id of section 16.1 |

**Every count in that table is reported whichever way it comes out**, including the
ones that would embarrass the direction, and specifically
`unit.M1_assignable_share_by_scale`, `labels.unassignable.by_reason`,
`aliasing.realised.*` and `fits.count_before_reported`.

### 22.3 The registrar gap

`scripts/build_numbers.py`'s `entry()` reads a reproducibility record keyed by
`source_file`, so a new research artifact needs a record added there. That is a
change outside `research/` and therefore a human gate. It is already logged by A6
as NH-A6-04 in `research/eval/NUMBERS_PROTOCOL.md` and is not re-raised here as a
new item.

---

## 23. What must be true before fitting starts

In the order the gates actually fire.

1. **WJ-001, the six API keys.** Without `KMA_APIHUB_KEY` there is no rainfall, so
   there is no storm, so there is **no risk set and no rows at all**. This is not
   one dependency among several; it is the one that decides whether the direction
   has a design. Without `COPERNICUS_USER` there is no Sentinel-2, so no fire
   perimeter, so no exposure. Without `VWORLD_KEY` there is no address resolution.
2. **A DEM.** WJ-011, or the Copernicus fallback behind WJ-001. Without it there
   is no unit, so sections 5, 8 and 12 have nothing to run on.
3. **`kr_admin_boundaries_ri`**, a new registry entry. The whole unit decision
   rests on the 리 polygon and it is not in the registry today.
4. **Measurements M1, M2 and M3 and gate U1**, which choose the unit scale. All
   three are outcome free and all three can run as soon as items 2 and 3 land.
   This is the cheapest true thing the direction can produce and it is available
   before any outcome is touched: it can tell the program that Korean address-level
   landslide records cannot support a unit-level hazard model at any useful
   resolution, and gate U3 lets that finding stop the work rather than caveat it.
5. **The rainfall variogram range** of section 12.4, which decides whether the
   registered 5,000 m block survives.
6. **The split fingerprint** pinned per section 12.2, before any outcome is
   assigned.
7. **The second label pass** of section 6.6, and A6's own ten-unit blind pass.
8. **Soil and geology**, which are application-gated.
9. **The species arm's data**, WJ-018 and WJ-012, or the fallback of section 11.3.
10. **A longer exposure record**, WJ-006 and WJ-001. This is the only thing that
    changes what the direction can answer rather than how precisely it answers it.

---

## 24. Statement for the signing agent

### 24.1 What has and has not happened

No fit has been run. No outcome value has been looked at. Section 3.2 records every
computation A4 has performed, section 3.3 records everything A4 has read about
Sancheong, and section 17 is A4's leakage checklist, written and committed before
A6's independent pass begins, per condition C10 of the roads v0.2 record.

### 24.2 What A4 thinks the most likely outcome of this direction is

Recorded so it can be scored later.

A4 expects gate U1 to select a coarse unit, of the order of the 리 or larger, and
expects the slope-unit arm never to run. A4 expects the fire term at `t=0` to be
estimable and positive, because a burned-versus-unburned contrast at year zero is
the part of the design with the most support. A4 expects the **shape** of `g(t)`
to be poorly determined, because the support runs only to three years and one of
those years rests on a single cohort. A4 expects the species arm not to run at all,
because the forest type map is behind two human gates and the phenological fallback
is behind a third.

The most likely useful output of this direction, on A4's own estimate, is **not a
recovery curve**. It is the assignability table of section 8.4 and the aliasing
table of section 7.2: a measured statement about what Korean address-level
landslide records plus a 30 m DEM plus a five-year occurrence window can and cannot
identify. That is a real finding and this design is built to reach it before any
outcome is touched.

### 24.3 The single weakest point, in A4's own judgement

Not the aliasing, which is the objection A6 raised and which section 7 at least
partially answers, because the curvature is identified and the rainfall term is
measured. The weakest point is **support**: the committed exposure record observes
years since fire of zero, one, two and three, and the question asks how long the
elevated period lasts. Prior art puts the analogous effect running to about
twenty-five years. **The design is right-censored below the quantity it is meant to
estimate**, and no improvement to the units, the rainfall, the severity or the
storm count repairs that. Only a longer record does.

The near-equal second is the reporting problem of section 6.5, and A4 rates it
second rather than first only because it biases visibly while the support problem
is fatal silently. A reader who sees "years zero to three" knows what they are
looking at. A reader who sees a road coefficient does not automatically know it is
a reporting coefficient, which is why section 21.1 item 5 exists.

### 24.4 What this version does not fix

- The split fingerprint is not pinned, because there are no units. Section 12.2.
- The block size is not justified against a measured rainfall correlation range,
  because the radar product is behind an unset key. Section 12.4.
- The second label pass has not run, so P3 is passed on the text, not on the test.
  Section 6.6.
- There is no vocabulary detector for this direction. Section 21.2.
- The expected row count and effective sample size are bounds, not numbers,
  because they depend on a DEM that does not exist. Section 4.2.
- Two datasets the design depends on are not registry entries yet. Section 18.

Each is an open item rather than a hidden one, and each names what would close it.
