# Landslides direction, data requirements

Owner: A4. Keyed to `research/data/REGISTRY.yaml`, which A4 does not own and has
not edited. Companion to
`research/landslides/PREREG_landslides_2026-09-16_v0.1.md`.

For each dataset: what it is for, what happens if it never arrives, and the
fallback. Two entries at the end are **not in the registry** and are requested.

**The summary in section 5 is the short version.** Three of the fourteen
sources this direction needs are at status `verified`, and **none of the three
supplies a covariate or a unit**. One of them supplies the outcome and two supply fire dates. Every
covariate in the model, and the unit itself, is behind a gate.

---

## 1. On disk and verified

### `kfs_landslide_history`

**For.** The outcome. 5,118 records, 2021 to 2025, CP949, KOGL Type 1,
address-level with no coordinates. Loader
`research/shared/loaders/landslide.py`.

**If it never arrives.** It has arrived. The question is what it can support, and
`research/landslides/design/address_precision.py` answers part of it: zero of the
5,118 records carry a lot number in the finest address field, so
`GeocodePrecision.PARCEL` is unreachable for the whole file and the finest
confusion set available is a 리 polygon.

**What it cannot do.** It cannot place a landslide on a slope. It cannot
enumerate storms, because `재난구분` lists only storm windows that produced a
recorded landslide. It cannot tell a failure that was not reported from a failure
that did not happen.

**Fallback.** None, and none is needed. It is the only Korean landslide
occurrence record this program has. What changes with a better record is the
question, not the method: a record with coordinates would make the slope unit
viable, and a record covering more years would make the recovery window
observable.

### `kfs_fire_stats_csv`

**For.** Fire dates and burned areas, which give the exposure cohorts of
pre-registration section 7 and the fire list. 2,020 rows, report years 2022 to
2025.

**If it never arrives.** It has arrived. Its limitation is the one that decides
the direction: report years run 2022 to 2025 only, the 2024 cohort contains one
fire of at least 10 ha and none at all above 30 ha, so **three usable fire-year
cohorts exist, not four**, and years since fire is observable only at zero, one,
two and three.

**What it cannot do.** It has no coordinates and no perimeter. It is
address-level, like the occurrence record. So it cannot say **where** a fire
burned beyond a 읍면동, which is why fire perimeters have to come from
Sentinel-2.

**Fallback.** For perimeters, `sentinel2_l2a_dnbr`. There is no fallback for the
temporal reach; see the request for a longer record below.

### `kfs_fire_state_history_csv`

**For.** A timing cross-check on the fire list, and the Uiseong 2025 duplicate
pair that the complex rule collapses. 2,030 rows, 2022-01-01 to 2025-11-10.

**Never use its sunrise and sunset columns.** The registry records, and A1
independently confirmed, that they are a single national value per calendar date,
identical for every row on that date. Local solar times come from
`research/shared/geo/solar.py` and from nowhere else. This direction has no solar
covariate, so the trap does not bite here, but the note travels with the dataset.

**If it never arrives.** It has arrived.

---

## 2. Blocked, and the direction cannot start without them

### `dem_korea` (WJ-011, and the fallback behind WJ-001)

**For.** Everything spatial. The unit partition of pre-registration section 5,
slope, curvature, the topographic wetness index, the catchment delineation, the
steepness stratification of assignability measurement M2, and the unit centroids
that the split call needs.

**If it never arrives.** The direction has **no unit**, so it has no rows, so it
has nothing to fit. Sections 5, 8, 12 and 19 of the pre-registration all have
nothing to run on. This is a hard stop, not a degradation.

**Fallback, and what it costs.** NGII 5 m is the target and returned HTTP 400 to
automated fetch on two separate attempts, so it is WJ-011. Copernicus GLO-30 at
30 m posting is the working fallback and needs `COPERNICUS_USER` and
`COPERNICUS_PASS`, which is WJ-001.

The cost of 30 m, stated in pre-registration section 5.2: a shallow Korean
landslide initiates in a convergent hollow commonly of the order of tens of
metres across, which at 30 m posting spans of the order of one cell, so **the
fallback DEM cannot resolve the initiation site at all**. Slope at 30 m is a
smoothed slope and its steep tail is attenuated. A catchment at the scale gate U1
is likely to choose spans many tens of cells and is resolvable; a slope unit is
not. This is one of the two independent arguments that moved the primary unit to
the catchment.

**Never mosaic two DEM providers**, per `docs/HANDOFF_ROUND3.md` section 5 rule
17. If the 5 m product arrives later, the unit partition is re-derived at 5 m and
that is a new version of the pre-registration, not a tweak.

### `kma_radar_qpe` (WJ-001)

**For.** The storm enumeration itself, and `rain_max_1h`, `rain_total` and
`rain_ante_7d`. Also the rainfall correlation range that pre-registration section
12.4 needs in order to justify the registered 5,000 m block size.

**If it never arrives.** There is **no risk set**. The discrete-time design needs
an enumeration of storms, the enumeration cannot come from the occurrence
record's `재난구분` field without conditioning the sample on the outcome, and
rainfall is the only other source. **This is the single most important blocked
dataset for this direction** and it is behind one environment variable.

It is also the mitigation that leakage item C2 demands: including the triggering
rainfall explicitly at the event level is what stops the years-since-fire term
carrying the weather, and it is what converts the exact calendar aliasing into an
assumption rather than an identity. Without it there is no escape from the
aliasing at all.

**Fallback.** `kma_asos_aws` station observations, interpolated. Same API key, so
it is not a fallback for the key, only for the product. What it costs: station
spacing is far coarser than convective storm structure in Korean mountain
terrain, so an interpolated field would smooth away exactly the intense
short-duration cells that trigger shallow failures, and the measurement error
would be worst in the steep remote terrain where the units are. That is classical
measurement error on the model's most important covariate, and it attenuates the
rainfall response, which in turn pushes unexplained variation into the fire term.
**A fitted fire term under interpolated gauge rainfall is biased in the direction
that flatters the hypothesis**, and the pre-registration would have to carry that
reading rule before any such fit.

### `kma_asos_aws` (WJ-001)

**For.** A gauge-versus-radar cross-check on the rainfall covariates, and the
fallback above.

**If it never arrives.** The radar product goes unchecked against ground truth.
Same key as the radar, so the two clear together or not at all.

### `sentinel2_l2a_dnbr` (WJ-001)

**For.** Fire perimeters, which are the `burned` covariate; `severity_dnbr`; and
the phenological species fallback of pre-registration section 11.3.

**If it never arrives.** There is **no exposure**. The fire record is
address-level, so without imagery the direction cannot say which units burned,
only which 읍면동 contained a fire. Assigning a whole 읍면동 as burned would put
unburned units into the burned arm and would attenuate the fire term toward zero.

**Fallback.** None that this program can reach. A Korean burned-area product at
the needed resolution is not in the registry. If Sentinel-2 never arrives, the
direction reports the assignability and aliasing tables of pre-registration
sections 7 and 8 and fits nothing, per gate U3 and per section 24.2.

### `vworld_geocoder` (WJ-001)

**For.** Resolving the occurrence record's addresses. Precision levels are never
mixed silently, per `research/shared/geo/geocode.py`.

**If it never arrives.** A 리 name plus its parent 읍면동 and 시군구 can be
matched directly against an administrative boundary layer without a geocoding
API, because the address is a name lookup rather than a coordinate lookup once
the parcel rung is off the table. **Since no record carries a lot number, the
geocoder's parcel path is unreachable anyway**, so the practical loss from losing
the API is small for this direction. That is an unusual case of a blocked
dependency mattering less than it looks, and it is worth saying so rather than
listing it as a blocker.

**Fallback.** `kr_admin_boundaries_ri`, requested below, plus a string match. The
match rule, its tie-break for duplicate 리 names inside one 시군구, and its
unmatched class go into the next pre-registration version if this path is taken.

### `naas_soil_map`

**For.** `soil_depth_class` and `soil_texture_class`, and the soil depth grid of
the physics link in pre-registration section 10.8.

**If it never arrives.** Soil drops out of the linear predictor and out of the
propensity model of section 10.6, so the matched secondary loses the covariate
most likely to be confounded with species. Pre-registration section 11.5 already
says soil depth is a class rather than a depth and that residual confounding
survives the conditioning; losing the class entirely makes the species arm
uninterpretable rather than weak, and the pre-registered consequence is that the
species arm is withdrawn under section 11.3 fallback 2.

The physics link of section 10.8 already reports a range over an assumed soil
depth grid rather than a fitted depth, so it survives the loss with a wider grid
and a louder caveat.

**Fallback.** Access is by application form at soil.rda.go.kr, which is a human
gate. There is no bulk download. A coarser national soil association map, if one
exists as an open layer, would be a partial substitute and is not currently in
the registry.

### `kigam_geology_map`

**For.** `geology_class`.

**If it never arrives.** Lithology drops out. The spatial block random intercept
absorbs part of it, because lithology varies at a regional scale, so the loss is
less severe than the soil loss. The pre-registered consequence is that
`geology_class` is reported as unavailable and the block random effect is
described as carrying regional lithology, which weakens the claim that terrain
and geology were conditioned on.

**Fallback.** The block random intercept, as above. The licence terms on the
KIGAM platform were not stated on the page A1 reached and need confirming before
any use.

### `kfs_forest_type_map` (WJ-018 for access, WJ-012 for the licence)

**For.** `species_pine_frac`, which is the entire secondary hypothesis.

**If it never arrives.** The recovery-window arm is unaffected. The species arm
does not survive in its pre-registered form. Pre-registration section 11.3 gives
the ordered fallbacks and section 11.4 gives the catch: a phenological classifier
built from Sentinel-2 can separate needleleaf from broadleaf canopy, but **the
only Korean reference layer against which its error rate could be measured is the
forest type map it exists to replace**, so in the case where it is needed it
cannot be validated on Korean data. The pre-registered consequence is a permanent
demotion to secondary, a declared misclassification sensitivity grid, the words
unvalidated classifier on every sentence, and withdrawal under failing condition
F5 rather than a weak report.

**Two gates, not one.** WJ-018 is the download, which is a named application with
a stated purpose on the Korea Forest Service spatial information service. WJ-012
is the licence: KOGL Type 3 is attribution with **no modification**, and whether
a derived pine-or-broadleaf covariate is permitted is an open question. A4's
recommendation is in `OPEN_QUESTIONS.md` Q4 and in pre-registration section 11.2:
derive the covariate, publish only coefficients, never publish a derived layer,
and ask the licensor. The pre-registration fixes the never-publish-a-layer rule
now so it is not decided under deadline later.

### `base_map_linear_features`

**For.** `dist_road_m` and `dist_builtup_m`, which live inside the **reporting**
term of pre-registration section 6.5, not inside the hazard term.

**If it never arrives.** The reporting term loses its two spatial covariates and
keeps only ownership class and the per-storm intercept. Since the reporting term
and the hazard term are not separately identified even with them, the loss
worsens a problem that is already unresolved rather than creating a new one.
Pre-registration section 21.1 item 5 already forbids any sentence attributing a
landslide to a road.

**Fallback.** OpenStreetMap South Korea, ODbL 1.0, confirmed working at
Geofabrik. It is a genuine fallback here because the covariate is a distance to
the nearest mapped road, and OSM road coverage in Korean mountain districts is
uneven in a way that correlates with remoteness, which is itself a reporting
determinant. So the OSM version of the covariate is closer to a reporting proxy
and further from a mechanism, which for this direction's purpose is the right
direction to err in. That should be stated wherever it is used.

---

## 3. Not in the registry, and requested

A4 does not own `research/data/REGISTRY.yaml` and has not edited it. These are
requests, with the proposed ids used throughout the pre-registration so that the
eventual entries match.

### `kr_admin_boundaries_ri` (proposed id)

**What.** Korean statutory administrative boundary polygons at 리 level
(법정리), with 읍면동 and 시군구 as parent levels, in a projected CRS or with a
stated CRS.

**For.** The confusion polygons on which the entire unit decision rests.
Assignability measurements M1, M2, M3 and M4 of pre-registration section 8.4 all
take a 리 polygon as input, gate U1 selects the unit scale from them, and the
label rule of section 6.3 resolves every occurrence record through them.

**Why it is the highest-value missing item after the DEM and the rainfall.**
Measurements M1, M2 and M3 are **outcome free**, run entirely on geometry, and
can be computed the day this layer and a DEM land. They answer A6's item C10
directly and with a number rather than an argument, and gate U3 lets a bad answer
stop the direction before any outcome is touched. The pre-registration's own
estimate, section 24.2, is that this table is the most likely useful output of
the whole direction.

**If it never arrives.** There is no confusion set, so there is no assignability
measurement, so there is no defensible unit at any scale, so nothing can be
fitted. The direction stops.

**Fallback.** A 읍면동 boundary layer alone would let the analysis run at a
coarser scale, losing the distinction between the 95.64 per cent of records that
reach a 리 and the 4.28 per cent that stop at a 읍면동, which is the distinction
that makes the finer scales worth testing at all. It would foreclose gate U1's
finer rungs by assumption rather than by measurement, which is exactly the move
this design exists to avoid.

**Where to look.** Korean statutory boundary layers are published through the
national spatial data portal and through Statistics Korea's census boundary
service. A1 owns the acquisition check, the licence confirmation and the registry
entry. A4 has not attempted a download, has created no account and has accepted
no terms.

### `kfs_salvage_logging` (proposed id)

**What.** The spatial extent and date of post-fire salvage logging of burned
timber, for the fires in scope.

**For.** `salvage_frac`, and for the third identification problem of
pre-registration section 11.6.

**Why it matters more than its position in the covariate table suggests.** Korean
post-fire salvage happens in the first years after a fire, which is **the same
window as the steep part of the root-decay curve**, and it operates in the same
direction: it removes stumps and disturbs soil, lowering root reinforcement
exactly when the fitted `g(t)` says reinforcement is falling anyway. So salvage
and years since fire are confounded by construction.

**If it never arrives.** `salvage_frac` cannot be built and the pre-registered
consequence is that `g(t)` is reported as a combined root-decay and
post-fire-management term, named that way in the abstract and not in a
limitations paragraph. That is the same remedy the pre-registration applies to
the unidentified decay-versus-regrowth split, applied for the same reason: when a
fitted quantity is a sum of two things the design cannot separate, the honest fix
is to rename the quantity, not to caveat it.

**Fallback.** None known. Post-fire erosion control works, which
`research/eval/LEAKAGE.md` item C7 names as a treatment applied in response to
risk, have the same problem and the same absence, and would be covered by the
same request.

---

## 4. Requests that change the question rather than the precision

### A longer Korea Forest Service fire record (WJ-006, and WJ-001 for the API)

**What.** Fire occurrence records reaching back well before 2022, with dates and
locations.

**Why this is different from every other item on this page.** Every other blocked
dataset limits how precisely this direction can answer its question. This one
limits **what question it can answer at all**.

`research/landslides/design/aliasing_separation.py` measures it. With the
committed 2022 to 2025 record, years since fire is observable at zero, one, two
and three, and the value three comes from one cohort in one calendar year. Prior
art, Sidle 1992, puts the analogous post-harvest effect strongest in years one to
ten and tapering to about twenty-five. **The design is right-censored below the
quantity it is meant to estimate.**

The same script measures what a longer record buys. Adding one pre-2022 cohort
takes the maximum observable years since fire from three to six and gives a
second calendar year at years since fire of two. With cohorts back to 2011, the
exposure-weighted `R^2` of years since fire on calendar year falls from 0.4769 to
0.033 and every value from zero to ten is observed in five distinct calendar
years.

**If it never arrives.** The direction can report a right-censored lower bound
over years zero to three, under the reading rule of pre-registration section 7.6,
and can never report the end of the window. That is a defensible result and the
pre-registration is built to produce it honestly. It is not the result the
question asks for.

### The Sancheong 2025 inventory (WJ-005)

**What.** The Nguyen, Song and Kim 2026 inventory, reported as containing 568
initiation points. A drafted request awaiting John.

**For.** The stress test of pre-registration section 15.6, and a possible second
outcome source with coordinates rather than addresses.

**The reading rule that already applies.** Leakage item C8 says Sancheong is held
out only if nobody read the paper first, and that reading the results counts.
Pre-registration section 3.3 is the record: A4 has read the count of 568 and
nothing else, and it has set no prior, covariate, threshold or gate. **If its
numbers are ever used to set a prior, Sancheong stops being a valid held-out fire
and another fire has to take that role.**

**What it cannot do, which the brief's framing does not anticipate.** The
Sancheong fire is dated 2025-03-21 in the committed fire record and the storm of
interest is the following July, so Sancheong contributes years since fire of zero
and nothing else. A held-out fire contributing a single value of years since fire
cannot test the shape of the recovery curve. It tests the level of the fire term
at year zero under an extreme storm, and pre-registration section 15.6 fixes that
reading in both directions in advance.

**Fallback.** Mapping scars from Sentinel-2 delta MSAVI following Lee et al.
2025. That method is **not verified** by A7 and is not used in v0.1. If it is
ever used, it needs its own label rule with an unlabelable class, its own
disagreement-rate pass, and the revegetation correction that pre-registration
section 6.5 scopes to the imagery arm and to nothing else.

---

## 5. Summary table

| registry id | status | what it supplies | what happens without it |
|---|---|---|---|
| `kfs_landslide_history` | verified | the outcome | it is here |
| `kfs_fire_stats_csv` | verified | fire dates, the exposure cohorts | it is here, and it reaches only to years since fire of three |
| `kfs_fire_state_history_csv` | verified | timing cross-check, the Uiseong duplicate | minor |
| `dem_korea` | pending | the unit, all terrain | **no unit, no rows, hard stop** |
| `kma_radar_qpe` | pending | the storm enumeration, all rainfall | **no risk set, hard stop, and no escape from the calendar aliasing** |
| `sentinel2_l2a_dnbr` | pending | perimeters, severity, species fallback | **no exposure, hard stop** |
| `kr_admin_boundaries_ri` | **not registered** | the confusion polygons | **no assignability measurement, no defensible unit** |
| `kma_asos_aws` | pending | gauge cross-check | radar goes unchecked |
| `naas_soil_map` | pending | soil class | species arm becomes uninterpretable, physics grid widens |
| `kigam_geology_map` | pending | lithology | absorbed into the block random effect, weakly |
| `kfs_forest_type_map` | pending | the species covariate | the species arm falls back, then withdraws |
| `base_map_linear_features` | pending | reporting-term distances | worsens an already unresolved identification |
| `vworld_geocoder` | pending | address resolution | small, because the parcel rung is unreachable regardless |
| `kfs_salvage_logging` | **not registered** | salvage extent | `g(t)` is renamed a combined root-decay and management term |
