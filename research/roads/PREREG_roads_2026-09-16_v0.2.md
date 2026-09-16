# Roads direction, pre-registration, v0.2

```yaml
prereg:
  direction: roads
  version: 2
  date: 2026-09-16
  author: A3
  supersedes: research/roads/PREREGISTRATION.md    # v0.1b, kept unedited
  answers_signoff: research/eval/signoffs/roads_v0.1b.md
  items_present: [P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, P15, P16]
  result_artifact: "research/roads/results/roads_prereg_v0_2_results.json"
  staging_file: "research/roads/numbers_staged.json"
  primary_metric: "mean out-of-complex log predictive score per labelled segment"
  primary_metric_json_path: "held_out.primary_metric.value"
  baseline: "B1, width-only logistic regression on W_cleared"
  baseline_metric_json_path: "baselines.B1.primary_metric.value"
  split_call: "leave_one_complex_out(fire_ids)"
  split_kwargs: {}
  split_fingerprint_complex_level: "844e82d06b534901590bc660f62cb49bb2b57279be055e112c93d801098d2cd5"
  split_fingerprint_segment_level: null   # pinned by section 6A when the layout is committed
  split_row_order: "committed segment layout order, section 3.2 item 4"
  datasets: [kfs_forest_roads, korea_prefire_orthoimagery, sentinel2_l2a_dnbr,
             firms_active_fire_korea, dem_korea, kfs_forest_type_map,
             base_map_linear_features, kma_asos_aws, kfs_fire_state_history_csv,
             kfs_fire_stats_csv]
  smallest_effect_of_interest: 0.05        # probability, W_cleared 3 m to 6 m, median approach angle
  smallest_effect_reported_alongside: 0.10
  outcome_seen: false
  data_seen: false
  signoff: unsigned         # written by A6 only
  signoff_record: null      # written by A6 only
```

**Status: v0.2, written 2026-09-16 by A3, answering `research/eval/signoffs/roads_v0.1b.md`
by number (R1 to R7). Nothing is fitted. No dataset has been downloaded by A3. No
label has been computed. No number below is a measurement.**

**Section 4 of `research/eval/SIGNOFF.md` does not apply to this version, and this
sentence is here so the reader does not have to infer it.** That section governs a
pre-registration amended after a look at data. No data was looked at before v0.1b
was written, none has been looked at since, and none was looked at while this
version was written. There is therefore no "what was seen before this amendment"
section, and its absence is not an omission. The only quantities A3 has read since
v0.1b are dataset-level acquisition facts recorded by A1 in
`research/data/REGISTRY.yaml` (coverage ranges, row counts, defect counts, access
status), which carry no outcome and no covariate value for any segment. They are
listed in section 21.

v0.1b remains at `research/roads/PREREGISTRATION.md`, unedited, as the superseded
record. This file is the one under review. Once it is signed it is frozen; changes
after the signature are a new version with a new file, and every later output names
the version it was produced under. See section 16.

Direction 1 of the research program (`research/README.md`). The hypothesis is
`H-ROADS` in `research/FORBIDDEN_CLAIMS.md`, and the claims discipline of that
file governs every sentence here.

---

## 0. Where each required item lives, and what changed since v0.1b

### 0.1 The sixteen items

| item | section | state in v0.1b | state here |
|---|---|---|---|
| P1 hypothesis in falsifiable form | 1 | pass | unchanged except F3 and F4 (section 1.5) |
| P2 unit of analysis | 3.2, 10.6, 11.1, 20 | conditional pass | the numbers requirement is now a pre-fit artifact key (section 22) |
| P3 label rule | 4, 5, 5.7, 5.8 | **fail** | rewritten as an ordered procedure; second pass built (5.8) |
| P4 covariates and sources | 6.1, 6.2 | conditional pass | knowable-at and label-touching columns added |
| P5 model form | 7, 10.7 | pass | held-out random-effect rule added (10.7); ridge errors-in-variables settled (6.3.4) |
| P6 held-out sets named in advance | 10.1, 18 | **fail** | call, keyword arguments, both fingerprints, row-order convention |
| P7 primary metric | 10.2, 10.3 | conditional pass | uncertainty and resampling unit stated |
| P8 simple baseline | 9, 10.4 | pass | unchanged |
| P9 failing condition | 1.5 | pass | F3 restated in cleared width, F4 by symbol |
| P10 stopping rule and multiplicity | 19 | **fail** | written |
| P11 leakage self-audit | 20 | **fail** | written, with the order defect declared |
| P12 data provenance | 21 | **fail** | written |
| P13 compute and feasibility | 22.4 | **fail** | written |
| P14 scope declaration | 14 | pass | unchanged |
| P15 what the result will not say | 12.4.4, 1.4, 6.7, 7.7.1 | pass | vocabulary now has a detector (12.4.6) |
| P16 shape of the result artifact | 22 | **fail** | written |

### 0.2 The seven reasons, answered by number

| reason | where it is answered |
|---|---|
| R1 label rule not executable | 5.1 (`SIDE`), 5.2 (smoke, Q5), 5.4 (index and threshold), 5.5 and 5.6 and 5.7 (the ordered procedure, the reason codes, the no-detection branch), 4.5 (eligibility against indeterminacy, the 0.60 against 0.70 conflict, the non-burnable fraction), 3.3 (overlapping barriers), 6.3.4 (ridges and errors-in-variables), 5.8 (the second pass) |
| R2 two CRITICAL leakage items | 12.8 (the sensitivity register, B4) and 12.9 (the arrival rule's grid and the exclusion-clustering check, B3) |
| R3 the reading rule's two repairs | 11.5.1 (`kappa_v` on the model's scale, gated on an interval) and 11.5.2b (the exclusion-power arm, gate M2) |
| R4 the smallest effect of interest | 11.5.3, and F3 in 1.5 |
| R5 six absent items | 18 (P6), 19 (P10), 20 (P11), 21 (P12), 22 (P16 and P13), plus the `prereg:` block above and this file's name |
| R6 two smaller items | 1.5 and 7.3 (F4 by symbol), 12.4.6 (the vocabulary detector), 12.4.7 (the day-against-night contrast) |
| R7 three MAJOR leakage conditions | 12.10 (B5, per-side illumination), 10.7 (B7, the held-out random effect), 12.11 (B9, the arrival hour and its uncertainty) |

### 0.3 Where A3 disagrees with the refusal

Three places, all recorded in section 17.3 rather than argued here, and none of
them changes what this version does. A3 complies with every ruling, including the
two it thinks are imprecise, because the path for a disagreement is
`SIGNOFF.md` section 5 and not a revision that quietly does something else.

---


## 1. The hypothesis, in falsifiable form

### 1.1 The question

When a real Korean fire front reached a forest road, a river or a ridge, did the
fire appear on the other side, and what distinguishes the encounters where it did
from the encounters where it did not?

### 1.2 The claim under test

The National Institute of Forest Science press release of 2025-04-25 and its
attachment 2-2 state that forest roads of 6 m or wider show the most effective firebreak function under Korea-like conditions; this is the claim under test, and it is prior art rather than a result.

**A7's prior-art sweep has corrected how this document must characterise that
claim, and the correction matters.** In its actual wording the claim is
**relative**, not absolute: it ranks forest roads of that width above the other
options considered. It is not a statement that such a road will hold a front. The
reachable page gives **no authors, no sample size and no breach rate**. So:

- the design tests a **comparative** proposition, and section 1.5's F3 is written
  as a contrast between widths rather than as a threshold test;
- nothing in this direction may characterise the claim as stronger than a relative
  ranking, and nothing may characterise it as weaker either;
- whether attachment 2-2 carries the sample and the rate that the public page does
  not is question 6 in section 15.1, and it is the main reason WJ-004 matters.

Whether that width is enough under Korean approach angles, slope directions and
lee-side fuels is the hypothesis, not the finding.

### 1.3 The hypothesis

`H-ROADS`. The probability that a Korean fire front produces a lee-side burn at a
linear barrier falls with the barrier's effective width, after conditioning on
approach angle, slope direction relative to spread, fire intensity at arrival,
lee-side fuel class and the weather at the hour of arrival.

### 1.4 What the estimand is, and what it is not

The quantity estimated is the conditional probability of a lee-side burn **given
that the front arrived**, in the observed Korean record, under the covariates
listed. It is an associational quantity. It is not the causal effect of widening
a road, and no counterfactual statement about building a wider road follows from
it. The reason is stated at length in section 12.4: a barrier that stopped a fire
is, by construction, part of that fire's perimeter, and everything else that
decides where a fire stops (a wind drop, nightfall, rain, a crew anchored on that
road) is bundled into the same encounter.

### 1.5 What would count as the hypothesis failing

These are declared before any fit, and a failure is reported as a finding, never
repaired.

| id | the pre-registered failure condition | what is reported if it fires |
|---|---|---|
| F1 | under the primary specification, and with the width gates W1 and M1 of section 11 met, the posterior mass `P(beta_width < 0)` does not reach 0.90 **in the errors-in-variables fit of section 6.3.4** | the width term is reported as not distinguishable from zero on this record, with its interval and with the attenuation factor `kappa_v`, and the breach curve is published flat |
| F2 | the width-only logistic baseline B1 (section 9) equals or beats the structured model in mean out-of-complex log score in 2 or more of the 5 folds, or the mean difference falls below the margin of section 10.4 | B1 is reported as the model of record, and the finding is that the added physics structure buys nothing measurable on this record |
| F3 | the posterior contrast in lee-side-burn probability between **`W_cleared` of 6 m and `W_cleared` of 3 m**, at the sample median approach angle and every other covariate at its sample median, has a 90 per cent credible interval that spans both directions | the study reports that this record does not separate the two cleared widths, which is a legitimate outcome and is not evidence for either side of the claim under test |
| F4 | **`lambda`**, the Poisson spotting rate of section 7.3, has a posterior standard deviation above 0.8 times its prior standard deviation; **or** either of **`mu_jump`** and **`sigma_jump`** does | the ember arm is reported as not identified, the distance distribution is published descriptively only, and the combined breach model is withdrawn in favour of the flame-crossing arm alone, under the renaming of 7.7.1 item 3 |
| F5 | the feasibility gates of section 11.3 are not met | the round delivers the labelled dataset, the descriptive tables and the bounding analysis, and records the design as untestable on this record |

**F3's unit, fixed here because v0.1b got it wrong.** A6 ruled that the effect
under test must be stated in the width a planner builds. `W_eff` is a composite of
cleared width and approach angle, so a contrast in `W_eff` is not a contrast any
county office can act on. F3 and the smallest effect of interest (section 11.5.3)
now use **one** width variable, `W_cleared`, and **one** contrast, 3 m to 6 m, so
that the failure condition and the equivalence threshold cannot drift apart. The
corresponding `W_eff` contrast at the sample median approach angle is reported
beside it so the two are legible together; it is a reported quantity and not a
pre-specified number, because the sample median approach angle is not known before
the data exists. v0.1b's second contrast, 3 m to 9 m, is withdrawn.

**F4's parameters, named by symbol, because the wording mattered.** A6 found that
"the ember jump parameters" reads naturally as `mu_jump` and `sigma_jump`, which
are the two parameters most likely to be adequately identified if any spots exist
at all, while section 7.3 expects `lambda` to be the one that fails. F4 as worded
in v0.1b could therefore have failed to fire in the exact case it exists for. The
rate is now named first and explicitly, and the condition is disjunctive so that
any of the three failing withdraws the arm.

F1 and F2 are the two that matter. If the honest answer is that a width-only
logistic regression does as well as the structured model, that is the result, and
section 9 exists so that it cannot be rewritten afterwards.

**F1 is deliberately asymmetric, and this is the most important qualification in
the document.** The width covariate is measured from imagery and carries
measurement error (section 6.3), and classical measurement error attenuates a
slope toward zero. A design that reads an attenuated slope as "width does not
matter" would be manufacturing its own negative result. So F1 is judged on the
errors-in-variables posterior, never on the naive one, and it is reported as
evidence bearing on the hypothesis only when the measurement gate M1 of section
11.3 is met. When M1 is not met, the outcome reported is **not resolvable at the
achieved measurement precision**, which is a different sentence from "width does
not matter" and must never be written as if it were the same one.

**Section 11.5 is the procedure that decides between those two sentences**, and it
is pre-registered in full because a flat curve is what a true null and a badly
measured covariate both produce. A6 rates that procedure the most important thing
in this document, and A3 agrees: without it a null result is uninterpretable
rather than informative.

---

## 2. Scope: fires, and the complex rule

### 2.1 The five fires

| fire | approximate date | why it is in |
|---|---|---|
| Goseong 2019 | 2019-04 | burn severity and satellite timing both plausibly available |
| Uljin and Samcheok 2022 | 2022-03 | as above |
| Gangneung 2023 | 2023-04 | as above |
| Uiseong and Andong 2025 | 2025-03 | as above |
| Sancheong 2025 | 2025-03 | as above |

No fire is added unless both a Sentinel-2 pre and post scene pair passing
section 5.2 and an active-fire detection record passing section 4.3 exist for it.
Any fire added after the signature is a version bump.

### 2.2 The complex rule, taken verbatim from the repository

`docs/benchmark/K_SPREAD_2025.md` section 2 declares that 영덕 2025 and
의성 and 안동 2025 are one complex and are never split across an entrant's
training and scoring sets. This direction adopts that rule without modification,
so that the two programs cannot disagree about what a fire is.

Consequences, stated explicitly:

1. **The unit of the fold is the complex, not the fire.** "Uiseong 2025" in this
   document means the 의성 and 안동 complex.
2. **영덕 2025 is not in the five fires above, but its fold is already decided.**
   If it is added in a later version it joins the 의성 and 안동 fold. It never
   becomes a sixth held-out set.
3. `research/data/REGISTRY.yaml` records that the KFS state-history file carries
   Uiseong 2025 as two same-day records of 52,707 ha and 46,575 ha. Those two
   records are one complex for every purpose in this direction: one fold, one
   level of the fire random effect, one arrival-time surface. A3 does not own the
   complex rule implementation; A2 does (task T1.5), and this direction consumes
   whatever A2 publishes rather than writing its own.

### 2.3 A confound that the fire list creates by itself

Active-fire detection cadence improves across the five fires. Suomi NPP and
NOAA-20 cover all of them; NOAA-21 only reaches the 2025 fires. So arrival
timing, spread rate and therefore the intensity covariate are measured more
finely in 2025 than in 2019, and the fire that supplies the cadence is also the
fold unit and the random-effect level. Any apparent difference between fires
could be a sensor-availability artefact.

Pre-registered mitigation, decided now rather than after seeing the result:

- the number of usable overpasses per day during each fire is recorded per fire
  and reported in the results table;
- a **common-cadence robustness run** is pre-registered, in which the detection
  record for every fire is degraded to Suomi NPP plus NOAA-20 only, and the whole
  pipeline is re-run. The width posterior from that run is reported beside the
  primary one. If the two disagree in sign or in whether F1 fires, the
  common-cadence run is the one that is believed.

---

## 3. The barrier layer and the encounter unit

### 3.1 What counts as a barrier

Three classes, each entering the model with its own intercept (section 7.2).

**Roads.** Forest roads (임도) from `kfs_forest_roads`, with
`base_map_linear_features` (NGII, or OpenStreetMap as the fallback) supplying
public roads that cross forest. **The rule that a barrier must predate its fire is
kept, and section 3.4 replaces the unexecutable version of it that v0.1b carried.**

**Rivers.** Hydrography from `base_map_linear_features`. A1 has confirmed that
the NGII national base map route is blocked (two automated attempts returned HTTP
400, so the access terms are unconfirmed and it is now a human gate), and that the
OpenStreetMap Geofabrik extract is available under ODbL 1.0. **The design
therefore plans on OpenStreetMap for rivers**, with NGII as an upgrade if John
clears it. What that costs: OpenStreetMap hydrography in Korean mountain
catchments is of uneven completeness and its channel polygons are sparse, so most
rivers will arrive as centrelines and their width will come from the same
image-derived measurement as roads (section 6.3). Completeness is audited before
labelling by comparing the OpenStreetMap channel count against the DEM-derived
channel network at a matched flow-accumulation threshold, and the audit is
reported.

**Ridges.** Not a base-map layer in either NGII or OpenStreetMap, so they are
derived, and the derivation is documented because it is the only thing that makes
the ridge class reproducible. Ridges are the channel network of the inverted
`dem_korea`, at a pre-registered flow-accumulation threshold, retained only where
local prominence over the 200 m neighbourhood exceeds 20 m. The derivation script,
its threshold, its DEM source and its resolution are committed before any
labelling, and section 6.7 records what the available DEM resolution does to it.

Ridges deserve a note, because they are what keeps the design honest. A Korean
forest ridge normally has no fuel gap at all. Ridges therefore enter with barrier
width **defined** as zero, and act purely through the slope reversal at the crest.
That is the point: ridges identify the slope-direction term separately from the
width term, which roads on their own cannot do. **The zero is a definition, not a
measurement**, and section 6.3.4 now states the consequence for the
errors-in-variables layer, which A6's scenario S5 correctly found undefined in
v0.1b.

### 3.2 The encounter unit, and why the suggested 100 m survives

The suggestion was 100 m. The suggestion is adopted, but for reasons that had to
be checked, and with two changes that the bare suggestion does not carry.

1. **Sensor support.** The Sentinel-2 bands that build NBR are 20 m after
   resampling. With the 40 m analysis band of section 5.3, a 100 m segment yields
   about 10 NBR pixels per side. At 50 m it yields about 5, which is too few for a
   stable burned fraction. At 200 m the within-segment variation in width, bearing
   and slope becomes large enough that the covariates stop describing the segment.
2. **Grid compatibility.** The repository's own benchmark truth grid is 100 m
   (`docs/benchmark/K_SPREAD_2025.md` section 4), so a 100 m encounter unit joins
   to it without resampling.
3. **Change 1, a bearing constraint.** A Korean mountain forest road can turn
   through 90 degrees inside 100 m, which would make a single approach angle
   meaningless. A segment is therefore **at most 100 m long and at most 30 degrees
   of bearing change**, whichever binds first. Remnants shorter than 40 m are
   merged into the previous segment rather than kept.
4. **Change 2, a deterministic layout.** Segments are cut by chainage from each
   barrier line's start vertex, with lines ordered by a stable hash of their
   geometry, in EPSG:5186 (decision D-005). The layout is produced by a committed
   script **before any label is computed**, so no segment can be drawn around an
   interesting event.

A sensitivity analysis at 50 m and at 200 m is pre-registered. It is a
sensitivity analysis and not a model-selection step: the 100 m result is the one
reported in the abstract regardless of how the other two come out.

---


### 3.3 When two barriers' bands overlap

A Korean mountain forest road often runs along a stream in a valley bottom. Both
are mapped, both are segmented, and their 40 m analysis bands (section 5.3) then
overlap. v0.1b said nothing about this, and A6's scenario S9 is correct that the
configuration is common and that the barrier-line random effect of section 10.6
does not catch it, because the two segments sit on different barrier lines. The
rule is fixed here.

Let `d_sep` be the perpendicular distance between two barrier lines' **edges**
(centrelines offset by half the measured width, section 5.3).

- **`d_sep` below 100 m: one composite barrier.** The two lines are merged into a
  single composite barrier line for every purpose in this document. Its windward
  edge is the outer edge of whichever member the front reaches first under section
  5.1, its lee edge is the outer edge of the other, and its `W_cleared` is the
  **whole** distance between those two edges, including the strip of untouched
  ground between the two members. A fire front approaching a road that runs beside
  a stream meets one gap, not two, and scoring it as two barriers both
  double-counts one event and understates the gap. The composite carries the
  barrier type of the member with the larger `W_cleared`, plus a `composite` flag
  which enters as a covariate, and it carries a single composite barrier-line id,
  so the barrier-line random intercept of section 10.6 absorbs it correctly. A
  pre-registered sensitivity analysis refits with every composite dropped.
- **`d_sep` between 100 m and 200 m: two barriers, with a shared strip removed.**
  Each line keeps its own segments, but pixels lying between the two lines are
  removed from **both** lee bands, because a burn there cannot be attributed to
  either barrier. The affected segments carry an `adjacent_barrier` flag, and if
  the removal takes the usable-and-burnable pixel count below the minimum of
  section 4.4, the segment exits as `CLOUD` at step 3 of section 5.7 like any
  other pixel shortfall.
- **`d_sep` at or above 200 m: two independent barriers**, no interaction, no flag.

`d_sep` is computed from the committed layout before any label exists, so no
composite can be formed or dissolved because of what happened to it. The counts of
composite segments, of `adjacent_barrier` segments and of segments lost to the
shared-strip removal are reported per fire in the label accounting table.

**What this costs and why it is still right.** A composite's `W_cleared` includes
ground that is neither road nor river and may carry fuel, so a composite is a
worse instance of "a cleared gap" than a road on its own. That is why the flag is
a covariate and why the drop-composites refit is pre-registered. The alternative,
excluding every road that runs near a stream, would remove a large and
non-random part of the Korean forest road network, which is a worse bias than the
one it avoids.

### 3.4 Whether a barrier existed when the fire burned, which is not yet answerable

This is the hardest open dependency in the document and it is not a covariate
problem. **A road built in 2023 scored as a barrier that held at Uljin in 2022 is
a fabricated observation, not a noisy one**, so a design that cannot date its
barriers cannot use them at all.

**What is known as of 2026-09-16.** The forest road SHP has not been downloaded.
A1's round-2 attempt failed: data.go.kr id 3045621 is a
`기관자체에서 다운로드` listing whose URL points at forest.go.kr, whose nationwide
zip is served only behind a server-enforced personal-information consent
checkbox, and a direct GET of the static zip returns HTTP 307 to an error page.
This is human gate **WJ-017**, and it is ahead of WJ-009 in priority. So the
question A3 asked in round 1, whether the layer carries a construction or survey
year, **cannot be answered yet**. On the portal's own description it leans toward
absent: the categories named there are route line, coordinate position, section
and connection structure, none of which is temporal, and the only dates on the
page are dataset-level (a filename dated 2020-09-14 and a most-recent-update field
showing 2025-11-20). The design must therefore work under both answers, and this
section fixes both branches now so that neither can be chosen after seeing which
one leaves more segments.

**Branch A: a per-road construction or survey year exists.** It is used. A road
whose year postdates its fire's ignition date is excluded with reason `POSTDATE`
and counted. A road whose year is null is `UNDATED` and is handled under branch B
for that subset only. The count of roads in each of the three states is reported
per fire.

**Branch B: no per-road date.** Then the only datable fact about a road is the
edition date of the layer it came from, and the logic runs one way only:

> If the layer's edition date `E` is **earlier** than a fire's ignition date, then
> every road in the layer existed at `E`, therefore before that fire. That fire's
> roads are safe.
> If `E` is **later** than a fire's ignition date, roads may have been built
> between the fire and `E`, and nothing in the layer says which.

Four consequences, all pre-registered:

1. **The edition date is established from the file, not from the portal.** `E` is
   read from the downloaded artifact itself (any date field in the DBF, the
   shapefile's internal metadata, or the zip members' timestamps, in that order of
   preference), and the source of `E` is recorded. The portal's
   most-recent-update field is not used, because it describes the catalogue entry
   and not the geometry.
2. **The earliest usable edition is preferred.** If more than one edition of the
   layer is obtainable, the study uses the **earliest** edition that covers the
   study area, because an older edition cannot contain a newer road. This costs
   nothing and it is the only free move available here.
3. **Fires that postdate `E` are primary; fires that predate `E` are conditional**,
   and enter only through the per-segment existence check of item 4.
4. **The existence check comes free with the width measurement.** Width is measured
   for every segment from **pre-fire** orthoimagery (section 6.3.2), so the same
   imagery answers whether the road was there: a segment whose automatic extraction
   finds no canopy gap at the mapped centreline in pre-fire imagery is a road that
   did not exist, or was not visible, before the fire. It exits with reason
   `NOEXIST` and is counted. This makes the orthoimagery gate WJ-009 load-bearing
   twice, which is worth saying plainly, because it means WJ-009 decides more than
   the width covariate.

**The bounding case, stated now.** If the only obtainable edition is the one the
portal's update field suggests, `E` is later than all five fires, and **no fire is
safe on the edition test**. In that case the roads arm exists only through the
`NOEXIST` check of item 4, which needs WJ-009. If WJ-009 also does not clear, the
roads arm of this study is not executable, and that is the reported finding: the
encounter dataset is then built from rivers and ridges only, the width slope is
reported for rivers only, and no statement of any kind is made about forest roads.
Gate **E1** in section 11.3 is the rule that fires this branch.

**Rivers and ridges do not have this problem.** A river channel and a ridge crest
are not built between 2019 and 2025. Channel migration and landslide-driven crest
change exist and are rare at the scale of a 100 m segment over six years; they are
not checked, and that is stated as an accepted assumption rather than as a
verified fact.

---

## 4. What "the fire front reached it" means

This is the definition that separates an encounter from "the fire was somewhere
in the neighbourhood". A segment is an **encounter** only when all four
conditions C1 to C4 below hold. Anything less is not an encounter, and the segment
leaves the study before it is ever labelled.

**The order of evaluation is fixed and it matters.** v0.1b left it implicit, and
A6's scenario S2 found the consequence: a segment at a 0.65 usable fraction fell
under an eligibility clause and an indeterminacy clause at once, and the two put
it in different accounting classes. Section 5.7 is the full ordered procedure.
What section 4 fixes is the principle that decides which list a condition belongs
to:

> **Ineligible** means the unit cannot carry the question: the front never arrived,
> or the lee side could not have burned whatever the barrier did, or the barrier
> may not have existed. **Indeterminate** means the unit is a genuine encounter
> whose label cannot be read from the scenes available. Nothing appears on both
> lists, and section 5.7 reaches exactly one of them for every candidate segment.

### 4.0 The analysis pixel set, defined once

Every count in sections 4 and 5 is over the same set, so it is defined here rather
than three times. For each side of a segment, the **analysis pixel set** is the
20 m pixels whose centres fall inside that side's analysis band (section 5.3) and
which are

- **usable** in both the pre-fire and the post-fire scene under section 5.2,
  which now includes the smoke mask, and
- **burnable**, meaning their pre-fire land-cover and 임상도 class is not open
  water, bare rock, built-up area or actively cultivated land.

A 100 m segment's 40 m band holds about 10 such pixels per side when nothing is
lost. **At least 7 analysis pixels are required on each side.** That single number
replaces both the 0.60 usable fraction of v0.1b section 4.5 and the 0.70 usable
fraction of v0.1b section 5.5, which contradicted each other. Seven of a nominal
ten is the 0.70 figure expressed in the unit that actually matters at this segment
length, and expressing it as a count rather than a fraction removes the second
defect A6's scenario S6 found: **non-burnable pixels are not burned pixels**, so
leaving them in a fraction's denominator would silently lower every burned
fraction on rocky and cultivated ground. They are out of the denominator entirely.

A segment with fewer than 7 analysis pixels on either side is **indeterminate**
with reason `CLOUD`, which now covers cloud, shadow, snow, smoke, no-data and
non-burnable loss together, with the dominant cause recorded per segment so the
accounting table can separate them.

### 4.1 C1, the windward side is burned right up to the barrier

The fraction of **analysis pixels** in the windward band (section 4.0) at or above
the burned threshold of section 5.4 is at least 0.80. The front has to have
consumed the fuel up to the barrier edge, not merely passed within sight of it.
The 0.80 carries a declared sensitivity grid in section 12.9.

### 4.2 C2, the windward burn is part of the main fire

The windward burned pixels are 8-connected, within the burned mask, to the fire's
main burned polygon. This excludes an isolated spot fire on the windward side
being mistaken for the arriving front.

### 4.3 C3, an active-fire detection places the front there

At least one VIIRS active-fire detection whose reconstructed pixel footprint
intersects the windward analysis band, inside the fire's active window. Footprints
are reconstructed from the scan and track dimensions of the product; where those
are absent, a 400 m radius around the detection centroid is used instead, which is
the 375 m nominal pixel plus a geolocation allowance. Suomi NPP, NOAA-20 and, for
the 2025 fires, NOAA-21 are all used, with the platform recorded per detection so
the common-cadence run of section 2.3 can subset them. The 400 m fallback carries
a declared sensitivity grid in section 12.9.

### 4.4 C4, the encounter can be timed

A local arrival-time fit (section 6.4) succeeds at the segment: at least 5
detections within 1 km spanning at least 2 distinct acquisition times. Without
this there is no approach angle, no spread rate and therefore no intensity, and
the encounter cannot carry the model's covariates. Both numbers carry a declared
sensitivity grid in section 12.9.

**C4 is necessary for the encounter and not sufficient for the side assignment.**
Section 5.1 imposes a second, stricter requirement on the same fit, and section
5.1.3 shows that at the C4 minimum of 5 detections the side assignment resolves
only for near-perpendicular approaches. The two requirements are kept separate
deliberately: C4 decides whether a segment is an encounter at all, and the section
5.1 test decides whether its two sides can be told apart. A segment that passes C4
and fails section 5.1 is an encounter with no readable label, which is what the
`SIDE` reason code is for.

### 4.5 Eligibility, applied before labelling

A segment is **ineligible**, and is counted and reported as such rather than
silently dropped, when one of the following holds. Each is a property of the unit
rather than of the scenes, per the principle in the preamble above.

| reason | condition |
|---|---|
| `FUEL` | **more than 0.50** of the usable pixels in the lee band fall in non-burnable classes (open water, bare rock, built-up area, actively cultivated land or non-stocked forest). Below that fraction the segment stays in, and the non-burnable pixels are simply not in the analysis set of section 4.0 |
| `POSTDATE` | the barrier's own recorded construction or survey year postdates the fire (section 3.4, branch A) |
| `NOEXIST` | pre-fire orthoimagery shows no canopy gap at the mapped centreline, so the barrier did not exist or was not visible before the fire (section 3.4, branch B item 4) |
| `EDITION` | the barrier layer's edition date postdates the fire and no per-segment existence check is available (section 3.4, the bounding case) |
| `WIDTH` | the segment's own width is unknown and cannot be assigned even a class-level prior under section 6.3 |
| `NOBURN` | C1 fails: the windward band is not burned up to the barrier, so no front arrived here |
| `NOTMAIN` | C2 fails: the windward burn is not connected to the main burn |
| `NODETECT` | C3 fails: no active-fire detection places a front at this segment |

The last three are the failures of C1, C2 and C3. v0.1b let those segments
"leave the study" without a code, which made leakage item B3's required count of
segments excluded for want of an arrival impossible to produce. They are now
counted like every other exit, and section 12.9 checks whether they cluster on the
wide barriers.

**The 0.50 in `FUEL` is a number where v0.1b had none**, and A6's scenario S6 is
the reason: "the lee-side band is not burnable" with no fraction is a clause that
three readers resolve three ways, and the three give three different eligible
sets. The value is set at a majority for the stated reason that below a majority
the remaining burnable pixels still support the 7-pixel minimum of section 4.0,
and above it they usually do not, so the two thresholds do not fight. `FUEL`
carries a declared sensitivity grid in section 12.9.

Ineligible counts are published per fire and per reason. They are part of the
result, because the size of the eligible set is the main thing that decides
whether this design can say anything at all.

---

## 5. The pre-registered labels

Two people following this section must put the same segment in the same box. That
is the bar this section has to clear.

### 5.1 Which side is which

**This rule is replaced outright. A6 showed that v0.1b's version assigns no
sides at all, and A3 re-derived the arithmetic and agrees with it.**

#### 5.1.1 Why the old rule produced nothing

v0.1b compared the two sides' **fitted arrival times** against the arrival-time
fit's own residual standard error. The two analysis-band centroids sit about 60 m
apart plus the barrier width, so at spread rates of 0.3 to 3 km/h the arrival gap
across the barrier is 1.2 to 14.4 minutes. The denominator was the residual
standard error of a plane fitted over a 1 km neighbourhood to detections at as few
as two acquisition epochs hours apart, which is tens of minutes at best. Applied
literally, `SIDE` fails at essentially every segment and the study produces no
labels. That is not a prediction about the data; it follows from this document's
own buffer geometry, its own minimum detection count and the revisit structure of
the sensor it names.

The defect has one cause and it is worth naming, because it is what the
replacement fixes: **the old rule's signal was a fixed 60 m offset while its noise
scaled with the 1 km neighbourhood.** Shrinking the buffer would not help and
widening it would make it worse. The replacement puts signal and noise on the same
scale.

#### 5.1.2 The rule

The side assignment does not need the arrival-time **difference** across the
barrier. It needs the **sign of the fitted arrival-time gradient projected onto
the barrier normal**, which is a statement about the whole 1 km neighbourhood and
uses the whole neighbourhood as its lever arm.

Let the weighted local plane of section 6.4 be `t(x) = t0 + g . (x - x0)` with
fitted time gradient `g` (minutes per metre) and covariance `Sigma_g` from the
same weighted least squares. Let `n` be the unit normal to the segment centreline,
pointing to one of the two sides, fixed by the committed layout so it cannot be
chosen later. Define

    s      = g . n                         (minutes per metre, signed)
    se(s)  = sqrt( n' Sigma_g n )
    T      = s / se(s)

Then:

- **`T >= z_side`**: the front arrived from the `-n` side. That side is windward.
- **`T <= -z_side`**: the front arrived from the `+n` side. That side is windward.
- **`|T| < z_side`**: the side assignment fails and the segment is indeterminate
  with reason `SIDE`.

`z_side` is pre-registered at **2.0**, with a declared sensitivity grid of
{1.5, 2.0, 2.5} in section 12.9.

**Tier S-B, the coarser fallback, applied only when tier S-A fails.** The same
statistic is recomputed from a plane fitted over a **3 km** neighbourhood,
requiring at least 12 detections spanning at least 3 distinct acquisition epochs,
with the same `z_side`. A longer lever arm buys a smaller gradient standard error,
at the cost of averaging over terrain the front did not treat uniformly. The tier
that assigned each segment is recorded as `side_tier` in {`S-A`, `S-B`, `none`},
it enters the model as a covariate, and the label rate by tier is reported. If the
label rate differs materially between the tiers, the S-B segments are reported
separately and a pre-registered secondary refits on S-A segments only.

**Nothing else may assign a side.** The side assignment is a function of the
active-fire detection record and the committed barrier geometry, and of nothing
else. In particular:

- **Not the burned mask, and not the fire perimeter.** A6's refusal lists "the
  local fire-perimeter geometry" among the information that distinguishes windward
  from lee, and A3 must record a disagreement here, because that route is closed.
  The perimeter and the burned mask are both derived from the dNBR scene pair that
  produces the label. Assigning "lee" to the side that burned less would let the
  label define its own geometry, and it would manufacture `HELD` exactly where the
  hypothesis predicts it. This extends the provenance firewall of section 6.1 from
  the covariates to the side rule, which v0.1b did not state.
- **Not the wind direction**, for v0.1b's original reason: a Korean fire runs
  upslope against the surface wind often enough that wind alone mislabels sides.
  Wind is used as a **diagnostic only**: the agreement rate between the
  gradient-assigned side and the side wind would have assigned is reported per
  fire, whichever way it comes out, as a check that the gradient fit is describing
  a front and not noise.
- **Not the terrain aspect.** Signed slope in the direction of spread is a
  covariate (section 6.2). Deriving the side from terrain would make that covariate
  partly a function of the side assignment and would collapse a contrast the design
  needs.
- **Not the order in which the two sides burned.** That is the quantity A6's
  arithmetic shows the sensor cannot deliver at a 60 m offset, and it is the reason
  this rule exists.

#### 5.1.3 The precision this rule needs, and whether the data can supply it

This is the check v0.1b skipped, so it is done here explicitly.

Write the residual standard error of the plane fit as `sigma_r`, the number of
detections as `n_det`, and the standard deviation of the detections' positions
projected on `n` as `s_R`. For a roughly isotropic cloud of radius `R`, `s_R` is
about `R/2`. Then

    se(s)  ~  sigma_r / ( sqrt(n_det) * s_R )  =  2 sigma_r / ( sqrt(n_det) * R )

and with `|g| = 1/r` for spread rate `r`, and `theta` the approach angle of
section 6.4, `s = |g| sin(theta)`, so

    T  ~  sin(theta) * sqrt(n_det) * R / ( 2 r sigma_r )

Now express `sigma_r` in the only dimensionless way available. The residual is
dominated by the deviation of the real front from a plane across the
neighbourhood, so write `sigma_r = c * (R / r)`, where `R/r` is the time the front
takes to cross the neighbourhood and `c` is the **relative front irregularity**, a
dimensionless number. Substituting,

    T  ~  sin(theta) * sqrt(n_det) / ( 2 c )

**The spread rate cancels, and so does the neighbourhood radius.** That is the
whole reason this rule can work where the old one could not: the old rule's
signal-to-noise fell as the neighbourhood grew, and this one does not depend on
the neighbourhood at all. Requiring `T >= 2` gives the operational condition

    sin(theta)  >=  4 c / sqrt(n_det)

which is a statement about approach angle, detection count and front irregularity,
and about nothing else. The minimum resolvable approach angle, in degrees:

| `c` | `n_det` = 5 | 8 | 12 | 25 | 40 |
|---|---|---|---|---|---|
| 0.15 | 15.6 | 12.2 | 10.0 | 6.9 | 5.4 |
| 0.20 | 21.0 | 16.4 | 13.4 | 9.2 | 7.3 |
| 0.30 | 32.5 | 25.1 | 20.3 | 13.9 | 10.9 |
| 0.40 | 45.7 | 34.4 | 27.5 | 18.7 | 14.7 |
| 0.50 | 63.4 | 45.0 | 35.3 | 23.6 | 18.4 |

**Can the data supply it?** `c` is not known and A3 has not looked. But `c` is
estimable from the detection record alone, before any label exists, and doing so
is a pre-registered pre-labelling check:

> **Check S0, run before any label is computed.** Fit the section 6.4 plane at
> every candidate segment on all five fires, record `sigma_r`, `n_det`, `R` and the
> fitted `r`, form `c = sigma_r r / R` per segment, and report its distribution per
> fire and per barrier type. From the same run, report the fraction of candidate
> segments that would pass the section 5.1.2 test at each value of the `z_side`
> grid. This is a function of the detection record and the barrier geometry only;
> it touches no scene and no label, and it is committed before labelling starts.

The table above says what the answer has to look like. At the C4 minimum of 5
detections the rule resolves only near-perpendicular approaches unless the front is
unusually regular; at 12 to 25 detections it resolves most of the angular range for
`c` up to about 0.3. **If check S0 reports `c` above about 0.5 at typical detection
counts, the side assignment fails for most segments and this design cannot produce
a label**, and that is known before the labelling effort is spent rather than after.
Gate **S1** in section 11.3 is that rule.

#### 5.1.4 What this rule selects on, which is a cost and is reported

The rule keeps segments where the front approached at a large enough angle, and
drops grazing approaches. That is not a neutral filter, because **`W_eff =
W_cleared / sin(max(theta, 15 degrees))` is largest at exactly the grazing angles
the rule removes.** So the side rule truncates the effective-width support from
above, and it does so through the same quantity that enters the covariate.

Three pre-registered responses:

1. The `SIDE`-excluded segments' `W_cleared` and approach-angle distributions are
   reported against the retained ones, in the same table as the arrival-rule
   clustering check of section 12.9.
2. The width slope is reported on **`W_cleared`** as well as on `W_eff`, and F3 and
   the smallest effect of interest are stated in `W_cleared` (section 1.5, 11.5.3)
   precisely so that the headline quantity is the one the truncation does not act
   on directly.
3. The 15 degree clip in `W_eff` is kept unchanged. Under this rule the clip is
   rarely binding, since the side test already requires a larger angle in most
   configurations, and a clip that almost never binds is preferable to one tuned
   after the fact.

### 5.2 Scene selection, and what makes a pixel usable

- **Initial assessment, not extended.** Korean spring fires are followed by fast
  greenup, so an extended assessment would mix regrowth into the severity signal.
  The post-fire scene is the earliest scene at or after containment with a usable
  fraction of at least 0.70 over the fire's bounding box, and no later than 30
  days after containment. The pre-fire scene is the latest usable scene before
  ignition, no earlier than 60 days before it.
- **Where the containment time comes from, and the 2019 problem.** A1 has verified
  that `kfs_fire_stats_csv` covers report years 2022 to 2025 only, so it does not
  reach Goseong 2019, and that `kfs_fire_state_history_csv` covers 2022-01-01 to
  2025-11-10 across 2030 rows, so it does not either. The containment time is taken
  from `kfs_fire_state_history_csv` where that file covers the fire, and otherwise
  from the active-fire record itself: the last detection inside the fire's
  acquisition box, plus a 24 hour margin. This substitution is pre-registered now
  rather than improvised later, it applies to any fire without a KFS containment
  record, and the source of the containment time is recorded as a column per fire.
  Note that the scoring clock of this direction was never the KFS report time:
  arrival times come from the detection record (section 6.4), so the KFS files
  affect scene selection only.
- **The KFS sunrise and sunset columns are never used.** A1 has now confirmed
  empirically that 일출시간 and 일몰시간 in `kfs_fire_state_history_csv` carry a
  single national value per calendar date: zero of 607 dates carry more than one
  distinct value. Every local solar quantity in this document, including the
  day-against-night contrast of section 12.4.7, is computed from the segment's own
  coordinates through `research/shared/geo/solar.py`.
- If no scene pair satisfies both windows, the whole fire's segments are
  indeterminate with reason `SCENE`, and this is reported as a fire-level
  exclusion, not as a set of missing rows.
- A pixel is **usable** when the Sentinel-2 L2A scene classification does not mark
  it as cloud medium probability, cloud high probability, thin cirrus, cloud
  shadow, snow, saturated or no-data, in **either** the pre or the post scene, and
  when it is not inside the smoke mask of section 5.2.1. A pixel that is usable in
  one scene and not the other cannot contribute a difference and is not usable.

#### 5.2.1 The smoke mask, which closes Q5

**A6 ratified option 2 of Q5 as the route, rejected option 3 outright, and
deliberately declined to write the rule, because a label rule A6 authored is a
label rule A6 cannot sign. So A3 writes it, and it is written here in full: the
band, the threshold, the resampling, which scene, the sensitivity grid and the
fallback trigger.** The reason this is not a detail is the direction of its bias.
Undetected smoke suppresses the post-fire NBR depression, which lowers dNBR, which
lowers the lee burned fraction, which pushes segments toward `HELD`. **The label
that undetected smoke manufactures is the label the hypothesis predicts**, and
that is the one direction of bias a design testing this hypothesis cannot leave
undefined.

**The input.** The aerosol optical thickness raster at 550 nm carried in the
Sentinel-2 L2A product (the Sen2Cor `AOT` band), read at its **20 m** posting,
which is the analysis grid of this document, so the primary rule needs no
resampling. Where only the 60 m raster is present for a scene, it is resampled to
20 m by nearest neighbour, the substitution is recorded per scene, and the
affected segments carry an `aot_60m` flag whose effect on the label rate is
reported.

**The threshold, and why it is not an absolute number.** An absolute aerosol
threshold is wrong for Korea. Korean spring carries transported dust and haze at
background aerosol optical thicknesses that are routinely a substantial fraction
of what a smoke plume adds, so a fixed cut would mask whole scenes in some springs
and nothing in others, and the resulting mask would track the weather of the year
rather than the smoke of the fire. The rule is therefore stated against the
scene's own background, with an absolute ceiling to catch the case where the
background rule defines the smoke away:

    AOT_ref(scene)   = median AOT over the reference region of that scene
    AOT_excess(px)   = AOT(px) - AOT_ref(scene)

> A pixel is **smoke-affected** when `AOT_excess >= 0.10`, **or** when
> `AOT >= 0.60` in absolute terms.

**The reference region is label-blind by construction.** It is the complement,
inside the scene's bounding box, of the convex hull of that fire's active-fire
detections buffered by 5 km, further excluding pixels the scene classification
marks as cloud, shadow, snow or no-data. It is defined from the detection record
and from the scene classification only. It is **not** defined from the burned mask
or the fire perimeter, which come from the dNBR pair that makes the label, and
this is the same firewall extension that section 5.1.2 applies to the side rule.

**Which scene.** A pixel smoke-affected in **either** the pre or the post scene is
unusable, exactly as for cloud. A difference needs both dates, and an asymmetric
rule would be a second unexplained decision.

**The sensitivity grid, declared here, every value reported.** `AOT_excess`
threshold in {0.05, 0.10, 0.20, 0.40}; absolute ceiling in {0.45, 0.60, 0.80}.
Primary is (0.10, 0.60). The grid is run one parameter at a time from the primary,
and the label accounting table is reported at every value, not only at the chosen
one.

**The fallback to option 1, with its trigger fixed in advance.** Option 1 is the
scene-classification cloud classes alone, with no aerosol term. It is available
**only** when one of two conditions holds for a given fire, and the condition is
computed and committed before any lee-side burned fraction is computed anywhere in
the pipeline:

- **T1.** The `AOT` band is absent from, or entirely no-data in, the L2A product
  for that fire's pre or post scene.
- **T2.** The primary rule masks more than **0.50** of all analysis-band pixels
  across that fire's candidate segments. This quantity is a count of masked pixels
  and involves no burn status and no label, on either side.

If neither fires, option 1 is not available for that fire, and the primary rule
stands however few segments survive it. The decision is made per fire, once, and
the decision record with its triggering quantity is written by a committed script
whose output is a required input to the labelling script, so the pipeline enforces
the order. **This is the clause that stops the choice between option 2 and option 1
being made after seeing which leaves more segments labelable.**

If option 1 is taken for any fire, the bias sentence goes in the abstract, not in
a limitations paragraph: for that fire, thin smoke passed into the scene pair
undetected, and undetected smoke biases the labels toward `HELD`.

**Option 3, a hand-drawn smoke polygon, is refused and no branch of this document
reaches it**, for A3's own round-1 reason which A6 ratified: it puts an analyst
inside the label path, and section 12 spends its length keeping analysts out of it.

**One free check, added because it costs nothing.** A smoke plume is large
relative to a 100 m segment, so it should mask a segment's two bands about
equally. The per-segment difference in masked fraction between the windward and
lee bands is recorded and its distribution reported. A systematic difference is
evidence that the mask is tracking something other than smoke, and it is reported
whichever way it comes out.

### 5.3 The buffer geometry, and where the distances come from

Distances are measured from the **barrier edge**, not from the centreline. The
edge is the centreline offset by half the barrier width from section 6.3.

- **Inner exclusion `d_in`, 10 m.** Discarded on each side. A 20 m NBR pixel
  straddling a road edge mixes bare running surface with vegetation, and mixed
  pixels dilute the difference in both directions. Ten metres removes the worst of
  them.
- **Analysis band, `d_in` to `d_out` from the barrier edge, on each side, with
  `d_out` at 50 m.** Forty metres gives two full rows of 20 m pixels, and about 10
  pixels per side per 100 m segment.
- **Why the band stops at 50 m.** This is the boundary between the two model
  components and it is deliberate. A lee-side burn inside `d_out` is treated as
  flame crossing. A lee-side burn beyond `d_out` that is not connected to the
  barrier edge is treated as spotting and is measured by the ember arm (section
  7.3). Setting one boundary for both components is what stops the same event being
  counted twice, once in each arm of a model whose whole form is a product of the
  two.

**Both distances now carry declared sensitivity grids, because v0.1b asserted that
they did and they did not.** Section 12.8 gives the grids in full. Three
properties of those grids are stated here, where the geometry is, because they are
properties of the geometry and not of the reporting:

1. **`d_out` is doubly load-bearing.** Moving it moves the label *and* reassigns
   events between the flame arm and the ember arm, because the ember arm's inner
   truncation is `d_out` and not a separately fixed 50 m. Every value of the
   `d_out` grid therefore re-runs **both** arms with the truncation moved, and the
   count of events that change arms is reported for each value. A sensitivity
   analysis that moved the label boundary and left the ember truncation at 50 m
   would double-count at every value except the primary.
2. **`d_in` is coupled to the width measurement.** The band starts from the barrier
   *edge*, which is the centreline offset by half the **measured** width, so a
   segment measured wider has its band pushed outward. The `d_in` sensitivity
   therefore partly re-expresses the width measurement error of section 6.3, and it
   is reported with that noted rather than as an independent axis.
3. **The 7-pixel minimum of section 4.0 moves with `d_out`.** A narrower band holds
   fewer pixels. The minimum is held at 0.70 of the band's nominal pixel count at
   each grid value (5 pixels at `d_out` = 30 m, 7 at 50 m, 11 at 80 m), so that the
   usability requirement stays the same requirement across the grid instead of
   silently tightening.

### 5.4 dNBR, RdNBR, the burned threshold, and the two sides having different fuel

**The index and the threshold are reconciled here. v0.1b took `tau_burn` = 0.10
from the Key and Benson dNBR scheme and then applied the burned threshold on
RdNBR, which is a different scale, and A6's scenario S10 is right that this puts
the cut point in the wrong place. A6 asked which of the two would be fixed. The
answer is: the index.**

- dNBR is pre-fire NBR minus post-fire NBR, on the scene pair of section 5.2,
  after reprojection to EPSG:5186.
- **dNBR is the primary index for the burned threshold**, and `tau_burn` stays at
  **0.10**, the low-severity break point of the Key and Benson FIREMON scheme.
  Number and scale now agree, which is the point. That scheme is prior art from
  outside Korea and is used here as the source of a method, never as a source of
  data. A verified Korean calibration, if A7 finds one, replaces the default in a
  version bump and not silently. The sensitivity grid over `tau_burn` stays at
  {0.05, 0.10, 0.15, 0.20}.
- **RdNBR is retained as a pre-registered secondary index**, computed as dNBR
  divided by the square root of the absolute pre-fire NBR, with two fixes that
  v0.1b lacked:
  - a **floor on the divisor**: pre-fire absolute NBR is floored at **0.10** before
    the square root is taken. Without a floor RdNBR is unbounded as pre-fire NBR
    approaches zero, which is exactly what happens on the sparse and non-stocked
    classes that section 6.2 uses as the lee-fuel reference category. Pixels whose
    unfloored pre-fire absolute NBR is below the floor are excluded from the RdNBR
    arm and counted, and they remain in the dNBR arm;
  - its own threshold, **`tau_burn_R` = 0.15**, which is `tau_burn` converted at a
    reference pre-fire NBR of 0.45, a value typical of a stocked Korean conifer
    stand: `0.10 / sqrt(0.45) = 0.149`. The conversion and its reference are stated
    so the number is traceable rather than asserted, and the RdNBR grid is
    {0.10, 0.15, 0.20, 0.25}.
- **Why the primary flipped to dNBR rather than the threshold being restated on
  RdNBR.** Three reasons, in order of weight. First, `tau_burn`'s provenance is a
  dNBR break point, and a design that keeps the borrowed number should keep the
  borrowed scale. Second, the RdNBR divisor's pathology lands precisely on the fuel
  class the model uses as its reference category, so the secondary index is least
  trustworthy exactly where the primary contrast is anchored. Third, the burned
  and not-burned decision is made at the **low** end of the severity range, where
  the divisor is most unstable, so RdNBR is worst at the only cut point that
  matters. What RdNBR was doing for fuel normalisation is already done three other
  ways, listed next.
- **Different pre-fire fuel on the two sides** is handled three ways at once, none
  of which depends on RdNBR being primary. First, a **fuel-discordance flag** is
  set when the two bands fall in different forest-type classes in the pre-fire
  임상도, and the flag enters the model as a covariate. Second, a pre-registered
  sensitivity analysis refits on the fuel-concordant segments only. Third, lee-side
  fuel class is itself a covariate. The RdNBR label is computed and reported
  throughout as the fourth, and any disagreement between the dNBR and RdNBR labels
  is reported as a count by fire and by barrier type.
- **The provenance firewall is not relaxed by this change.** Pre-fire spectral
  indices remain unavailable as covariates (section 12.1). The reason v0.1b gave,
  that the primary label contains pre-fire NBR through RdNBR, still holds for the
  secondary index, and dNBR contains post-fire NBR in any case. Loosening a
  firewall because the index it guards has moved is the exact shape of drift the
  firewall exists to stop.

### 5.5 The label rule

Let `f_lee` be the fraction of the lee side's **analysis pixels** (section 4.0) at
or above the burned threshold `tau_burn` of section 5.4, on the primary index.
The denominator is the analysis pixel set and nothing else: not all pixels in the
band, not all usable pixels, but the pixels that are usable in both scenes and
burnable. That is the fix for A6's scenario S6.

**HELD.** The segment is an encounter under section 4, its side assignment
succeeded under section 5.1, and `f_lee` is **below 0.10**.

**CROSSED.** The segment is an encounter, its side assignment succeeded, `f_lee`
is **at or above 0.50**, the lee burned patch **touches the inner exclusion
boundary** on the lee side, and the attribution test of section 5.6 passes.

**INDETERMINATE.** Everything else, always with a reason code, always retained in
the table, never dropped.

| code | meaning | where it is decided |
|---|---|---|
| `SCENE` | no scene pair for this fire satisfies section 5.2 | 5.7 step 3 |
| `TIMING` | condition C4 fails, so the encounter cannot be timed | 5.7 step 4 |
| `SIDE` | the projected arrival-time gradient does not resolve windward from lee at `z_side` in either tier | 5.7 step 5 |
| `CLOUD` | fewer than the required analysis pixels on one or both sides, from cloud, shadow, snow, smoke, no-data or non-burnable loss, with the dominant cause recorded | 5.7 step 7 |
| `MID` | `f_lee` at or above 0.10 and below 0.50 | 5.7 step 10 |
| `DETACH` | `f_lee` at or above 0.50 but the lee burned patch does not touch the inner exclusion boundary | 5.7 step 11 |
| `FLANK` | the attribution test of section 5.6 fails: the lee burn is better explained by a path around a barrier terminus | 5.7 step 12 |
| `FLANK_AMBIG` | a flanking route is close enough to compete and no detection inside the lee patch can resolve the timing | 5.7 step 12 |

**Two codes from v0.1b are gone and one is new.**

- `DISCORD` is **removed**. v0.1b gave a code for "fuel discordance beyond the
  pre-registered limit" and pre-registered no limit anywhere, which A6's scenario
  S8 caught. The correct resolution is not to invent a limit but to decide what the
  discordance flag is: it is a **covariate and a sensitivity stratum, never an
  exclusion**. A discordance exclusion would drop exactly the segments where the two
  sides differ in fuel, and lee-side fuel is a covariate of interest in its own
  right (section 14.1). So no segment is ever made indeterminate by fuel
  discordance, and the flag does the work it was always meant to do.
- `DETACH` is **new**, and it exists because A6's scenario S7 found a case the
  v0.1b code list could not name: `f_lee` at or above 0.50 with a lee burned patch
  detached from the barrier edge. That case is neither arm's event under v0.1b: it
  is inside `d_out` so the ember arm excludes it, and detached so the flame arm
  excludes it. It is now counted, and section 7.3 pre-registers the sensitivity
  analysis that moves the ember arm's inner truncation from `d_out` to `d_in` so
  that `DETACH` events enter the ember arm, with both readings reported.

Indeterminate is a third class, not a bin for inconvenient rows. It is counted in
every table, and section 10.5 says what is done with it.

### 5.6 The attribution test, which stops flanking being read as crossing

A lee-side burn can arrive by going **around the end of the barrier** rather than
across this segment. **v0.1b's version of this test is replaced. A6 found three
defects and all three are real:** its two bullets contradicted its closing
sentence at 480 m against "more than 500 m"; its first bullet was vacuous, since
it was satisfied by a connection across the lee band **or** by a path leaving the
neighbourhood, and flanking is the second of those; and it had no branch for a lee
patch containing no active-fire detection, which is the input its timing clause
requires.

**The quantities, defined once.**

- `P` is the connected component of the burned mask that contains the segment's
  lee-band burned pixels.
- A **bypass point** is a barrier terminus, or a mapped gap in the barrier line,
  through which `P` is connected to the windward burn by a path that **does not
  cross the barrier**. A crossing at a neighbouring segment is not a bypass point,
  because a crossing is what the study is measuring, not a route around it. This is
  the definition that removes v0.1b's vacuous bullet.
- `d_bypass` is the along-barrier distance from this segment's midpoint to the
  nearest bypass point, searched to a maximum of 2,000 m in each direction along
  the barrier line. If no bypass point is found inside that window, `d_bypass` is
  undefined.
- `d_bypass_min` is pre-registered at **500 m**, with a declared sensitivity grid
  of {300, 500, 800} m in section 12.9.

**The test, in two steps, with the geometric step first.**

> **Step A, geometry.** If `d_bypass` is undefined, or `d_bypass > d_bypass_min`,
> the attribution test **passes**. The nearest route around the barrier is too far
> to explain a lee burn beside this segment, so flanking is not a competing
> explanation and no timing information is needed.
>
> **Step B, timing, reached only when `d_bypass <= d_bypass_min`.** A flanking
> route would deliver fire to this segment's lee side no earlier than
> `t_w + d_bypass / r_flank`, where `t_w` is the fitted windward arrival time at
> this segment (section 6.4) and `r_flank` is the fitted spread rate along the
> barrier in the direction of the bypass point.
> - **B1.** If at least one active-fire detection lies inside `P`, let `t_lee` be
>   the earliest such detection's acquisition time. The test **passes** when
>   `t_lee` is earlier than the flanking arrival by more than the combined
>   standard error of `t_w` and the acquisition time, and **fails** with reason
>   `FLANK` otherwise.
> - **B2.** If no active-fire detection lies inside `P`, the timing cannot be
>   read, and the segment is indeterminate with reason **`FLANK_AMBIG`**. It is
>   not `FLANK`, which asserts flanking, and it is not `CROSSED`, which asserts a
>   crossing.

**Why `CROSSED` is now reachable, which A6 was right to ask about.** A6's scenario
S4 observes that a 40 m lee band against a 375 m VIIRS pixel means a lee burn
confined to the band usually carries no detection of its own, and concludes that
the attribution test is inoperative and `CROSSED` unreachable for the majority of
segments. The premise is correct and the conclusion overstates its own premise, in
a way worth recording because it changes how much of the positive class is at
risk. The test's input is the lee **patch** `P`, not the lee **band**. A fire that
crossed a barrier and kept running produces a patch that extends well past 50 m
into the lee landscape, and a patch of that size carries detections. The genuinely
detection-free case is the one where the fire crossed and **stalled within 50 m**,
which is a real and interesting minority rather than the majority.

Either way the rule has to have a branch, and after the rewrite:

- every segment with `d_bypass` undefined or above 500 m reaches `CROSSED` on
  geometry alone, with no detection required anywhere. On a long barrier, bypass
  points are termini and mapped gaps, which are sparse, so this is the common case;
- the detection-free branch B2 is confined to segments that are both near a bypass
  point **and** have a stalled lee patch, and it exits to a named code rather than
  to a default in either direction;
- the counts reaching each exit are reported, so the reachability of `CROSSED` is
  a measured quantity in the accounting table rather than an argument.

**One case the rewrite does not exclude, and what is done instead.** Several
contiguous segments can share one lee patch `P`, so one crossing event can produce
`CROSSED` at more than one segment. Excluding all but one would discard real
information; counting them all as independent would inflate the sample. So:

- `n_share`, the number of segments sharing `P`, is recorded per segment;
- a **lee-patch random intercept** joins the fire-complex and barrier-line
  intercepts of section 10.6, so the model does not treat one crossing event as
  several independent observations, and the effective-encounter count of section
  10.6 is computed from all three variance components;
- a pre-registered secondary refits on the **patch-anchor subset**: one segment per
  lee patch, the one with the earliest fitted windward arrival, ties broken by the
  lowest chainage in the committed layout.

This also answers the residual A6 identified in leakage item B6 and scenario S9,
where two barriers 45 m apart are near-duplicates sitting on different barrier
lines: under section 3.3 they are now one composite barrier line, and if they are
between 100 m and 200 m apart their shared lee burn is one patch and the patch
intercept absorbs it.

### 5.7 The label rule as an ordered decision procedure

**This section is the answer to A6's item P3, and it is the structural change in
this version.** Eight of A6's ten boundary scenarios were undetermined by v0.1b's
text, and in six of them the cause was the same: two clauses in different sections
applied to one segment and put it in different classes, or no clause applied at
all. A prose rule with many clauses cannot be checked for exhaustiveness. An
ordered procedure can, and it is what two people following the document have to
execute to reach the same answer.

**The procedure runs top to bottom on every candidate segment. The first step
whose exit fires ends the evaluation. Exactly one exit is reached.**

| step | test | exit if it fires |
|---|---|---|
| 1 | barrier dating or existence fails (section 3.4) | **ineligible** `POSTDATE`, `NOEXIST` or `EDITION` |
| 2 | width unknown and no class prior available (section 6.3) | **ineligible** `WIDTH` |
| 3 | this fire has no scene pair satisfying section 5.2 | **indeterminate** `SCENE` |
| 4 | the arrival-time fit fails condition C4 (section 4.4) | **indeterminate** `TIMING` |
| 5 | the side test of section 5.1.2 fails in both tiers | **indeterminate** `SIDE` |
| 6 | more than 0.50 of the **lee** band's usable pixels are non-burnable (section 4.5) | **ineligible** `FUEL` |
| 7 | fewer than the required analysis pixels on either side (section 4.0) | **indeterminate** `CLOUD` |
| 8 | C1, C2 or C3 fails (sections 4.1 to 4.3) | **ineligible** `NOBURN`, `NOTMAIN` or `NODETECT` |
| 9 | `f_lee` below 0.10 | **label** `HELD` |
| 10 | `f_lee` at or above 0.10 and below 0.50 | **indeterminate** `MID` |
| 11 | `f_lee` at or above 0.50 and the lee patch does not touch the inner exclusion boundary | **indeterminate** `DETACH` |
| 12 | `f_lee` at or above 0.50, patch touches, attribution test of section 5.6 | **label** `CROSSED` on a pass; **indeterminate** `FLANK` on a step-B1 failure; **indeterminate** `FLANK_AMBIG` on step B2 |
| 13 | unreachable | the pipeline **raises and stops**. See below |

**Why the order is what it is.** Steps 1 and 2 are properties of the barrier and
cannot change with the scenes. Step 3 is fire-level. Steps 4 and 5 come before
every test that mentions "windward" or "lee", because until the side assignment
succeeds those two words do not denote anything, and v0.1b's ordering left that
implicit. Step 6 needs a side, which is why it sits after step 5 although it is an
eligibility test. Step 8 comes after step 7 because C1 is a fraction over the
analysis pixel set, and a fraction over four pixels is not a measurement.

**Step 13 is the exhaustiveness guarantee, and it is deliberately not a bin.**
A6's scenario S7 showed that v0.1b's reason-code list was not exhaustive over its
own rule's complement, so a real segment could reach "indeterminate, always with a
reason code" and have no code. Steps 9 to 12 now partition the range of `f_lee`
with no gap, so step 13 is unreachable by construction. If it is ever reached, the
labelling script raises and the run stops, and the offending segment is reported.
It is an error, not a category, because an eleventh reason code discovered at run
time is exactly the kind of degree of freedom this document exists to remove.

**A worked pass over A6's ten scenarios**, to show the procedure determines each
one. This is a check of the text against itself and contains no data.

| A6's scenario | v0.1b | this procedure |
|---|---|---|
| S1, `f_lee` 0.49, patch touches, attribution passes | `MID` | step 10, `MID`. Unchanged |
| S2, usable 0.65 lee and 0.92 windward | undetermined | one threshold now, the 7-pixel minimum of section 4.0, reached at step 7 as `CLOUD`. The 0.60 clause is gone |
| S3, `f_lee` 0.62, bypass at 480 m, lee detection 6.5 h late | undetermined | step 12. `d_bypass` 480 m is at or below 500 m, so step B applies; a detection exists, so B1 applies; 6.5 h against the flanking arrival decides it. No contradiction between a bullet and a sentence, because there is one rule |
| S4, as S3 with no detection in the lee patch | undetermined | step 12, branch B2, `FLANK_AMBIG` |
| S5, ridge, `W_cleared` = 0 by construction, 40 degree approach | undetermined | section 6.3.4: ridges carry no errors-in-variables term, `W_true` fixed at 0 |
| S6, windward burned fraction exactly 0.80, lee 45 per cent bare rock | undetermined | 45 per cent is at or below 0.50, so step 6 does not fire; the rock pixels are outside the analysis set of section 4.0, so they are in neither numerator nor denominator; step 7 then decides on the surviving count; C1's "at least 0.80" includes 0.80 |
| S7, `f_lee` 0.52, lee patch starts 25 m out and does not touch | undetermined | step 11, `DETACH` |
| S8, two bands in different 임상도 classes | undetermined | no exit. The discordance flag is a covariate; `DISCORD` no longer exists |
| S9, forest road 45 m from a stream, both mapped | undetermined | section 3.3: `d_sep` below 100 m, one composite barrier with one composite barrier-line id |
| S10, `f_lee` 0.08, pre-fire NBR near zero | undetermined | step 9, `HELD`, on dNBR at `tau_burn` 0.10, which is now the primary index at the scale the number came from. The RdNBR secondary excludes the pixel under the 0.10 divisor floor and counts it |

### 5.8 The second labelling pass, which P3 requires and v0.1b did not have

P3 asks for a second pass over at least thirty units by a path the author did not
write, with the disagreement rate in the pre-registration rather than in a later
footnote. v0.1b had neither the pass nor a plan for one. The width measurement had
its duplicate study (section 6.3.3), but that duplicates the **covariate**, not the
**label**, and there was no inter-path check on the label rule at all.

**The sample.** Thirty candidate segments, drawn by a committed script with a fixed
seed from the candidate set **before any label is computed by the primary path**,
stratified as 10 road, 10 river and 10 ridge, and within each barrier type spread
across the five fire complexes. They are drawn from the **candidate** set and not
from the labelable set, because the labelable set does not exist until the rule has
run, and drawing from it would be conditioning the validation sample on the rule
being validated.

**The second path.** An independent implementation of sections 4 and 5 of this
document, written against this text alone by an agent that is **not A3** and that
has not read `research/roads/label.py`, and executed on the same committed inputs.
The request text handed to that agent is committed alongside the script, so a
reader can see what it was and was not told. A6 is available for the ten-unit blind
pass of its own review protocol but is not the right author for this one, because
this pass is part of the design A6 signs.

**What is reported.** The three-class confusion matrix over {label, indeterminate,
ineligible}, the finer confusion matrix over every reason code, the count of
disagreements, and for each disagreement the **step number of section 5.7 at which
the two paths diverged**. The step number is the useful part: a disagreement at
step 12 is a rule that needs rewriting, and a disagreement at step 7 is usually a
pixel-handling difference that a sentence fixes.

**Gate L1, pre-registered.** If more than **3 of the thirty units** disagree at the
three-class level, the rule is declared not executable, section 5 is amended, the
amendment is a new version, and the pass is re-run on a freshly drawn thirty before
any fit. Three of thirty is one in ten, which is the bar A6's own ten-unit
acceptance test sets.

**The cost, stated rather than hidden.** Running this pass means thirty labels are
computed and looked at before the fit, and that is a look at the outcome variable
under `SIGNOFF.md` section 4. Two things follow and both are pre-registered here:

1. **The thirty units are removed from the modelling dataset permanently**, counted
   as `RULEVAL` in the accounting table and reported. They are drawn from the
   candidate set, which section 11.1 expects to be in the high hundreds to low
   thousands, so the expected cost in **labelable** segments is thirty times the
   labelable rate, which is single digits. That is the honest price and it is small.
2. **The disagreement rate enters this document by a version bump**, not by an
   edit. The procedure is frozen here; the number is filled in at v0.3, whose
   amendment section records exactly which thirty units were seen and by whom, per
   `SIGNOFF.md` section 4. A pre-registration cannot carry a number that does not
   exist yet, and pretending otherwise would be worse than the gap.

---

## 6. Covariates, and where each one is allowed to come from

### 6.1 The provenance firewall

**No covariate in either model component may be derived from the post-fire
scene, and none may be derived from any spectral index, pre-fire or post-fire.**
This is the leakage rule of section 12.1, stated here as a hard constraint on the
design matrix. Every covariate is accompanied in the output by its source layer,
and a committed audit script fails the build if any covariate's provenance
resolves to the scene pair that produced the label.

### 6.2 The list

P4 asks for a **knowable-at** column and an explicit yes-or-no column for
**derived from anything that touches the label**. v0.1b had neither, and A6 is
right that the firewall of section 6.1 makes every answer in the last column "no",
which is exactly why the column is cheap: it is the audit script's contract, and
the audit script is what fails the build.

"Knowable at" is the moment the value could have been written down. For this
design that moment is the hour the front arrived at the segment, because the
prediction the model expresses is about what happens next at that barrier.

| covariate | source | knowable at | derived from anything that touches the label | notes |
|---|---|---|---|---|
| `W_cleared`, and `W_eff` derived from it | **measured from pre-fire orthoimagery, section 6.3.** The road layer has no width attribute | before ignition | no | latent, with an errors-in-variables term; 6.3.4 and 6.5 |
| barrier type | barrier layer | before ignition | no | road, river, ridge |
| `composite` flag | barrier layout, section 3.3 | before ignition | no | |
| approach angle `theta` | arrival-time fit, section 6.4 | arrival hour | no | detection record only; folded into `W_eff` and also reported raw |
| `side_tier` | side rule, section 5.1.2 | arrival hour | no | S-A, S-B |
| signed slope in the direction of spread | `dem_korea` and the arrival-time fit | arrival hour | no | positive is uphill into the barrier; section 6.7 |
| fireline intensity at arrival | section 6.6 | arrival hour | no | not from fire radiative power, and not from any spectral band |
| detection persistence | active-fire record | arrival hour | no | ordinal intensity proxy |
| lee-side fuel class | pre-fire 임상도 (`kfs_forest_type_map`) | before ignition | no | categorical, non-stocked as reference |
| fuel discordance flag | pre-fire 임상도 | before ignition | no | section 5.4; a covariate and never an exclusion |
| wind speed, relative humidity, temperature at arrival | `kma_asos_aws` | arrival hour | no | nearest station with distance recorded; averaged over the arrival-time predictive distribution, section 12.11 |
| local solar hour of arrival, and the night indicator | computed from coordinates by `research/shared/geo/solar.py` | arrival hour | no | never from the KFS sunrise and sunset columns, section 5.2 |
| overpass cadence during the fire | active-fire record | arrival hour | no | section 2.3 |
| `delta_illum`, the per-side illumination difference | `dem_korea` plus solar geometry at each scene's acquisition time | scene acquisition | no | section 12.10; derived from terrain and sun position, from no spectral band |
| imagery vintage gap | `korea_prefire_orthoimagery` per-tile date | before ignition | no | section 6.3.5 |
| `aot_60m` flag | Sentinel-2 L2A product structure | scene acquisition | no | a property of which raster exists, not of any radiometric value |
| `n_share`, lee-patch sharing count | label geometry | after the label | **yes** | see the paragraph below |

**The one yes, and what is done about it.** `n_share` counts how many segments
share a lee burned patch, so it is computed from the burned mask and therefore
from the scene pair that makes the label. It is **not a covariate in the design
matrix**. It appears in exactly two places: as the grouping variable for the
lee-patch random intercept of section 5.6 and 10.6, and as the selector for the
patch-anchor secondary. Both are parts of the dependence structure rather than
predictors, and neither can move a fitted probability up or down through a
coefficient. The audit script of section 6.1 whitelists it by name for this reason
and fails the build if it appears in the design matrix. Stating it as a "yes" with
a paragraph is what P4 asks for, and the alternative, leaving it out of the table
because it is not strictly a covariate, would hide the one row worth looking at.

### 6.3 Barrier width: the measurement is the design's main liability

**This section was rewritten on 2026-09-16 after A1 reported a confirmed finding.**
The KFS forest road dataset (data.go.kr id 3045621, SHP, no usage restriction)
**has no width attribute**. That is confirmed, not assumed. So deriving width from
high-resolution imagery is not a contingency in this design. It is the primary and
only path, and the covariate it produces is the axis the whole question turns on.

#### 6.3.1 The two widths, which are not the same thing

- **`W_surface`**, the running surface width. This is what a road layer's width
  attribute would have meant, and it is probably the width the claim under test is
  stated in. It is the secondary covariate and the NIFoS-comparable one. Which of
  the two the claim actually refers to is question 2 in section 15.1, and it cannot
  be settled without attachment 2-2.
- **`W_cleared`**, the full canopy gap: running surface plus cut slope, fill slope
  and cleared shoulder. This is the gap a flame front has to cross, and on a Korean
  mountain forest road it can be a multiple of the running surface. `W_cleared` is
  the **primary** width covariate.

Both are measured from **pre-fire** high-resolution orthoimagery. Neither is read
from an attribute, because no such attribute exists.

#### 6.3.2 How the measurement is made

1. **Semi-automatic extraction, for every segment.** Five transects perpendicular
   to the segment centreline at 20 m spacing. Along each transect the canopy gap is
   the contiguous run of non-canopy pixels containing the centreline, from an
   orthoimagery classifier committed before any measurement. `W_cleared` is the
   median over the five transects; the transect spread is retained as a
   within-segment component and is part of the error model.
2. **Hand measurement, on a stratified subsample**, blind to the label
   (section 12.5), used to estimate the bias and the standard deviation of the
   automatic method rather than to replace it.
3. **A second independent pass** over part of the subsample, to separate the
   measuring agent's variance from the method's variance.

#### 6.3.3 How many hand-measured segments are needed, and why that number

The hand-measured subsample exists to estimate two quantities: a systematic bias
`b` of the automatic method, and its error standard deviation `sigma_u`. Both
follow from the paired differences between hand and automatic measurements on the
same segments.

- The standard error of an estimated standard deviation from `n` paired
  differences is about `sigma_u / sqrt(2(n-1))`. Estimating `sigma_u` to within
  about 10 per cent relative needs `n` near 50.
- Detecting a systematic bias of 0.4 `sigma_u` with 80 per cent power at the 5 per
  cent level needs `n` near 49.

Both land in the same place, so the pre-registered requirement is:

> **At least 60 hand-measured segments**, drawn as 4 per cell from a 5 by 3
> stratification of fire complex by automatic-width tercile, so that the error is
> estimated across the whole width range rather than only where roads are typical.
> **At least 30 of those 60 are measured a second time, independently**, giving 30
> repeat pairs from which the error variance is estimated directly. Segments are
> presented in randomised order with the burn footprint and the label withheld.

The repeat count of 30 is A6's number and A3 has adopted it over an earlier 20.
The arithmetic supports it: 30 paired repeats give `sigma_u` to about 13 per cent
relative, against about 16 per cent at 20, and 30 is where the estimate stops
being the weakest link in the attenuation correction. It is a few hours of work
and it is the difference between a reportable slope and an uninterpretable one.
The repeat study is **not optional and is not contingent on the sample size that
the labelling produces**: it runs on the pre-fire imagery and can be done before
any label exists.

If fewer than 60 can be measured, for example because pre-fire orthoimagery of
adequate vintage does not exist for one fire, the shortfall is reported per fire
and the error model falls back to a prior on `sigma_u` rather than an estimate.
That fallback triggers gate M1 in section 11.3.

#### 6.3.4 What the measurement error does to the result, and the correction

Classical measurement error in a covariate attenuates its slope toward zero. On
the **raw** width scale the attenuation factor is

    kappa_raw = sigma_x^2 / (sigma_x^2 + sigma_u^2)

where `sigma_x` is the spread of true widths in the sample. **The direction of
this bias is the dangerous one.** It pushes the width slope toward zero, which
pushes the study toward concluding that width does not matter. That is exactly the
conclusion F1 in section 1.5 is written to detect, so an uncorrected analysis
would be biased toward its own most eye-catching negative finding.

**`kappa_raw` is not the quantity that governs this model, and section 11.5.1
replaces it.** A6's repair (a) is correct: the covariate that enters the fit is
`log(W_eff + 1)` with `W_eff = W_cleared / sin(max(theta, 15 deg))`, and additive
classical error on `W_cleared` is neither additive nor classical after a division
by a sine and a logarithm. The induced error on the fitted covariate is
heteroscedastic and segment-dependent, and it is largest for the narrow barriers
at grazing angles that carry most of the leverage. `kappa_raw` is retained and
reported as a continuity diagnostic, labelled as a raw-scale quantity; the gate M1
moves to `kappa_v`, defined in section 11.5.1 on the scale the model uses.

Four things are done about the measurement error, all pre-registered:

1. **An errors-in-variables term in the Bayesian model.** The true width
   `W_true_i` is a latent parameter with a prior informed by the automatic
   measurement, and the observed measurement is `W_obs_i = W_true_i + b + e_i` with
   `e_i` drawn at standard deviation `sigma_u`. `b` and `sigma_u` are estimated
   jointly from the hand-measured subsample inside the same fit, not fixed
   beforehand. The width posterior that comes out is disattenuated, with honestly
   wider intervals, and both the naive and the corrected posteriors are reported
   side by side so the size of the correction is visible.

   **Ridges are exempt, and the exemption is stated rather than implied.** A6's
   scenario S5 found this undefined in v0.1b, and it matters twice: an
   errors-in-variables term applied to a ridge would put posterior mass on negative
   widths, where `W_eff` is undefined, and instrument 5 of section 11.5.5 uses
   ridges as a negative control, which works only if their width is exact. So
   `sigma_u_i = 0` for ridges, `W_true_i = 0` exactly, and
   `log(W_eff_i + 1) = 0` exactly. The zero is a **definition** from section 3.1,
   not a measurement, and the ridge intercept `alpha_type[ridge]` absorbs whatever
   a crest does that a zero-width gap does not describe.

2. **`kappa_v` is reported as a headline diagnostic**, with its interval, next to
   the breach curve, together with the distribution of the per-segment attenuation.
   A reader can then see how much of the curve is measurement, and where in the
   width range the measurement is worst.

3. **F1 becomes asymmetric**, which is the change that matters most. See section
   1.5 and gate M1.

4. **A pre-registered reading rule for a flat curve**, section 11.5, which decides
   before the fit how a true null is told apart from an attenuated one. The
   discrimination does not rest on the fitted slope alone, because the fitted slope
   is the thing under suspicion.

**Where the error model is estimated, and why that is not a fold violation.**
v0.1b said two different things: section 10.1 listed the digitising error among
the quantities computed inside the training folds, and this section estimates `b`
and `sigma_u` jointly inside the fit from a subsample stratified across all five
complexes. A6 noticed the contradiction and judged it small. It is resolved here in
favour of this section: **`b` and `sigma_u` are estimated once, from the whole
hand-measured subsample across all five complexes, and are not fold-internal.**
Two reasons. The hand measurement runs on pre-fire imagery, before any label
exists, and is blind to the burn footprint and to the label by section 12.5, so it
carries no outcome information across a fold boundary and is not leakage in either
reading. And a per-fold error model estimated from about a dozen repeat pairs would
be noise, which would make the correction worse rather than more honest. Section
10.1's list is corrected to match.

#### 6.3.5 What still cannot be fixed

The automatic extraction depends on orthoimagery whose vintage must predate the
fire. Where the nearest pre-fire orthoimagery is several years old, the gap may
have changed through vegetation encroachment or road maintenance, and that is a
bias the duplicate measurements cannot see because both passes read the same
image. The imagery vintage and its gap to the fire date are recorded per segment
and enter the model as a covariate, and a sensitivity analysis restricted to
segments whose imagery is within 3 years of the fire is pre-registered.

There is also no road-class fallback to lean on. Whether the SHP carries a class
attribute (간선임도, 지선임도, 작업임도) is not yet known, and A1 is asked for the
attribute schema (section 15.2). If a class attribute exists it supplies a
class-level prior for segments the automatic extraction fails on. If it does not,
those segments are `WIDTH` indeterminate and are counted as such.

### 6.4 The arrival-time fit

At each segment, acquisition times of active-fire detections within a
neighbourhood of radius `R` are fitted by a weighted local plane
`t(x) = t0 + g . (x - x0)`, by weighted least squares, retaining the full
parameter covariance. The primary neighbourhood is `R` = 1 km and the fit requires
at least 5 detections spanning at least 2 distinct acquisition times, or condition
C4 fails. Section 5.1.2 defines a second, coarser fit at `R` = 3 km used only as
the side-assignment fallback.

- **Spread direction** is the direction of increasing fitted time.
- **Rate of spread** `r` is the reciprocal of the fitted gradient magnitude `|g|`.
- **Approach angle** `theta` is the angle between the segment centreline bearing
  and the spread direction, folded into (0, 90] degrees.
- **The gradient covariance `Sigma_g`** is retained, and it is what section 5.1.2
  projects onto the barrier normal. This is the quantity v0.1b did not keep, and
  keeping it is what makes the side rule executable.
- **The residual standard error `sigma_r`** is retained, and is used for two
  things: the relative front irregularity `c = sigma_r * r / R` of section 5.1.3,
  and the arrival-time standard error at the windward band centroid, which section
  12.11 propagates into the weather covariates.
- **Two distinct acquisition epochs support a direction and not a rate.** VIIRS
  detections arrive in discrete overpasses, and at the C4 minimum the fitted
  gradient's **direction** is essentially the direction from the earlier epoch's
  detection centroid to the later epoch's, which is well determined, while its
  **magnitude** is poorly determined because the time axis takes only two values.
  The side rule of section 5.1 needs the direction and the sign, so it is
  serviceable at the C4 minimum for large approach angles (section 5.1.3). The
  Byram intensity of section 6.6 needs the rate, so it is not. Segments fitted at
  exactly 2 epochs carry a `two_epoch` flag, the intensity covariate carries the
  fit's own uncertainty on `r` into the model rather than a point value, and a
  pre-registered secondary refits on segments with 3 or more epochs.

Sub-daily geostationary detections from GK-2A would tighten the timing
considerably, and the repository already has the scaffold at
`src/wildfireguardian/fire_detection/gk2a.py`. That scaffold is blocked on a KMA
API Hub key and its keyless fallback only reaches back to 2023-02, so it cannot
serve the 2019 and 2022 fires. GK-2A is therefore **not** in the primary
specification. If the key arrives, a GK-2A-timed run is a pre-registered
secondary, reported beside the primary and never in place of it. What it would buy
is stated in advance so it cannot be discovered later: more acquisition epochs
raises `n_det` and lowers `c`, and by the table in section 5.1.3 both push the
minimum resolvable approach angle down, so the main effect of GK-2A on this design
is more segments surviving the `SIDE` step.

### 6.5 Effective width and the approach angle

A front crossing a barrier obliquely has to travel further inside the gap than one
crossing it square. The pre-registered primary parameterisation is

    W_eff = W_cleared / sin(max(theta, 15 degrees))

with the clip at 15 degrees to stop the quantity running away at grazing angles.
`W_cleared` here is the latent true width of section 6.3.4, not the raw
measurement, so the measurement error propagates into `W_eff` rather than being
absorbed silently.

The covariate enters as `log(W_eff + 1 m)`. The offset is there because ridges
carry zero fuel gap by construction (section 3.1) and `log(0)` is undefined; it is
pre-registered rather than chosen later, and the width slope is reported both on
the full barrier set and on roads and rivers only, since ridges sit at the offset
and contribute nothing to the slope except leverage.
The alternative parameterisation, raw width plus `theta` as a separate additive
covariate, is a **pre-registered robustness check**, not a choice to be made after
seeing which fits better.

⚠ **A dependency that must clear before the signature.** The effective-width
formulation is attributed to Swedosh et al. 2021 and A3 has not read that paper.
A7 worked from the indexed summary rather than the source PDF, so **the exact
formula must be confirmed against the PDF before it is hard-coded**. If it differs
from the expression above, this section is corrected and the version is bumped.

A7 also reports that the effective widths in that paper's validation cases were
**32.6 m and 33.8 m**, at a fire danger index of 80 with a 25 t/ha fuel load. Two
things follow, and they are different in kind.

- **Methodologically**, those figures set the scale the formulation was validated
  at, which is useful context for whether extrapolating it to Korean forest road
  widths is sound at all. That question belongs in the limitations, and it is
  raised here rather than discovered later.
- **Substantively, nothing follows for Korea.** Those are Australian validation
  cases under Australian fuel and danger conditions. They are not a Korean
  expectation, they are not a benchmark this study is measured against, and no
  comparison between them and any Korean width is made anywhere in this direction.
  The paper is the source of a method, and its data is not used.

### 6.6 Fire intensity without fire radiative power

`research/data/REGISTRY.yaml` already records that VIIRS 375 m fire radiative
power saturates at intense fronts. Intense fronts are precisely where the
interesting encounters are, so fire radiative power is **not** an intensity
covariate in this design, at any front.

What is used instead:

1. **Byram fireline intensity**, `I = H * w * r`, with `H` the heat yield taken as
   a constant from the literature, `w` the fuel consumed per unit area, and `r` the
   rate of spread from the arrival-time fit of section 6.4.
2. `w` comes from a fuel-load table keyed to the **pre-fire** 임상도 classes. It
   must not come from the burn severity image, which is the label. If no verified
   Korean fuel-load table exists, `w` enters as a class-level prior with wide
   uncertainty, propagated rather than fixed.
3. **Detection persistence**, the count of consecutive overpasses in which the
   segment's windward neighbourhood remains detected, as an ordinal proxy that
   does not depend on any radiometric quantity at all.

Intensity enters the model on the log scale, standardised.

### 6.7 What a 30 m DEM does to slope, ridges and approach angle

A1 has confirmed that the NGII 5 m DEM is blocked by the same HTTP 400 as the
national base map, and that Copernicus GLO-30 is available under a free licence
with a DOI citation and registration. **The design therefore plans on a 30 m DEM.**
At 30 m a 6 m road is a fifth of a pixel wide, and this has three separate
consequences that are not interchangeable.

**Approach angle is unaffected, and that is worth stating because it is the
surprising one.** The approach angle of section 6.4 is the angle between the
barrier centreline bearing and the local spread direction. The bearing comes from
the barrier vector geometry, which is metre-scale regardless of the DEM. The spread
direction comes from the arrival-time fit over active-fire detections, which is
limited by the 375 m detection footprint and not by the terrain model. Neither
input touches the DEM, so the 30 m DEM costs the approach angle nothing. What does
limit the approach angle is the detection footprint, and that limit is already in
section 6.4.

**Signed slope becomes a hillslope quantity, not a barrier-local one.** A 30 m DEM
with a 3 by 3 gradient window measures slope over roughly 90 m of terrain. It
cannot see the road's own cut and fill, and it cannot see a local break in slope at
the barrier. Two responses, both pre-registered. First, the signed slope covariate
is **defined** as the hillslope gradient in the direction of spread over the
windward 90 m, which is arguably the scale a fire front responds to anyway, and is
reported under that definition rather than as "the slope at the road". Second, the
smoothing is itself a measurement error, attenuating the slope coefficient in the
same direction as section 6.3.4 attenuates the width coefficient. A sensitivity
analysis on any subset for which a 5 m DEM is later obtained is pre-registered, and
if John clears the NGII gate before the fit, the 5 m DEM becomes primary and this
document is version-bumped.

**The ridge class is systematically incomplete, and it is biased.** A ridge crest
is resolvable in a 30 m DEM only when the ridge and its flanking valleys span
several pixels, which puts the smallest reliably detected ridge spacing near 90 m.
Narrow secondary spurs, which are common in Korean terrain and are exactly the
small ridges a fire crosses without noticing, are missed. So the ridge sample is
skewed toward large ridges, which are the ones most likely to be recorded as
holding. Pre-registered response: the ridge prominence threshold of section 3.1 is
kept at 20 m over a 200 m neighbourhood, which at 30 m posting is about 7 pixels
and is resolvable; every retained ridge records its prominence and its crest
curvature, and the ridge intercept is reported with the explicit caveat that it
describes detectable ridges only. No statement is made about ridges in general.

---

## 7. The model

### 7.1 The form

Per segment `i`, in fire complex `f(i)`:

    P(breach_i) = 1 - (1 - p_flame_i) * (1 - p_spot_i)

The flame arm is fitted to the near-field label of section 5.5. The ember arm is
fitted to the far-field spot record of section 7.3. The 50 m boundary of section
5.3 is what keeps an event out of both.

**The independence this form assumes, and the check for it.** The product form
assumes the two mechanisms are conditionally independent given the covariates.
That is doubtful: an intense front both pushes flame further and throws more
embers. The mitigation is pre-registered: the two arms share the fire-complex
random effect and the intensity covariate, and a residual-correlation check
between the arms is reported. If the check shows material correlation, the product
form is reported as a stated limitation of the published model, not quietly
replaced.

### 7.2 The flame-crossing arm

    logit(p_flame_i) = alpha + alpha_type[type_i] + u[f(i)]
                     + b_w   * z(log W_eff_i)
                     + b_s   * z(signed slope_i)
                     + b_I   * z(log I_i)
                     + b_L   * (lee fuel class contrasts)
                     + b_D   * discordance_i
                     + b_env * z(wind, humidity, solar hour)

`z(.)` is standardisation on the training folds only, never on the held-out fold.

### 7.3 The ember arm

The ember arm needs two things, and only one of them is a distance distribution.

**Spot identification.** A spot is a burned patch, at least `A_min` in area, that
is not connected within the burned mask to the main burn at the time of its first
detection, and whose distance to the nearest point of the then-current windward
perimeter is between `d_out` and `R_max`. `A_min` is pre-registered at 4 NBR pixels
(about 1,600 square metres), which is roughly the smallest patch that the scene
can show without being a single mixed pixel. `R_max` is pre-registered at 2,000 m,
beyond which attributing a spot to a particular barrier segment is not credible.
A spot with two candidate source perimeter points within 20 per cent of each other
in distance is flagged ambiguous and excluded from the distance fit, with the
count reported.

**The inner truncation is `d_out`, not a separately fixed 50 m**, and it moves with
`d_out` through the whole sensitivity grid of section 12.8. This is the coupling
A6 identified in leakage item B4: the 50 m edge is both the label boundary and the
boundary between the two arms, so a sensitivity analysis that moved one without the
other would double-count events at every grid value except the primary.

**The `DETACH` sensitivity.** Section 5.5 introduces the `DETACH` code for a lee
burn at or above the crossed fraction that does not touch the inner exclusion
boundary. Such an event is inside `d_out`, so the ember arm excludes it, and
detached, so the flame arm excludes it. A pre-registered secondary moves the ember
arm's inner truncation from `d_out` to `d_in` so that `DETACH` events enter the
ember arm as near-field spots, and both readings are reported. The primary keeps
the truncation at `d_out`, because a near-field spot and a flame crossing are hard
to tell apart at 20 m posting and the primary should not pretend otherwise.

**The distance distribution.** Lognormal as primary, with a generalised Pareto
tail as the pre-registered alternative, compared by leave-one-out information
criteria. The likelihood is **truncated to [`d_out`, `R_max`]**, because the sample
is truncated by construction at both ends. This is not a cosmetic point: the
estimand is the distribution of **detectable** spot distances given detection, and
it is reported under that name. Small spots below `A_min` and spots that burned
out before an overpass are invisible to this record, and no correction is
attempted for them.

**The rate, which is the hard part and the parameter F4 names first.** A distance
distribution alone cannot give a per-segment spotting probability. A Poisson rate
`lambda` is needed: spots per 100 m of active front per hour. It is estimated from
the counted spots and the estimated active front length-hours from the
arrival-time surface, and then

    p_spot_i = 1 - exp( -lambda * T_i * (1 - F(W_eff_i + d_out)) )

with `T_i` the residence time of the front at the segment. **`lambda` is the
parameter this section expects to be weakly identified**, because a rate needs an
exposure denominator that this record estimates rather than observes, while a
distance distribution needs only the distances. F4 in section 1.5 names `lambda`
by symbol for that reason, and names `mu_jump` and `sigma_jump` as well so that
the arm is withdrawn whichever of the three fails.

### 7.4 Priors, and why each one

Priors are on standardised covariates unless stated. All are weakly informative
and symmetric.

| parameter | prior | justification |
|---|---|---|
| `alpha` | Normal(0, 1.5) | on the logit scale this spreads the implied base rate across most of (0, 1) without piling mass at the ends |
| `alpha_type` | Normal(0, 1) | three barrier types, partially informative so a type with few segments is pulled toward the pooled intercept |
| `b_w` | Normal(0, 1) | see the note below on why this is **not** sign-constrained |
| `b_s`, `b_I`, `b_L`, `b_D`, `b_env` | Normal(0, 1) | a unit change of one standard deviation moving the log-odds by more than about 2 is implausible |
| `u[f]`, fire complex | Normal(0, sigma_fire), non-centred | see section 7.5 |
| `sigma_fire` | HalfNormal(0.5) | see section 7.5 |
| `log lambda` | Normal(log 0.1, 1) | a spot per 100 m of front per 10 hours as the prior centre, with an order of magnitude of prior spread either way |
| `mu_jump` | Normal(log 200 m, 1) | centres the jump distribution in the hundreds of metres, with wide spread |
| `sigma_jump` | HalfNormal(1) | |
| digitising error `sigma_W` | estimated from the duplicate digitising, with a HalfNormal(2 m) prior | section 6.3 |

**Why `b_w` is not sign-constrained.** A half-normal or otherwise one-sided prior
on the width coefficient would build the hypothesis into the model and make F1
unfalsifiable. The prior is symmetric on purpose, and this is the single most
important line in the prior table.

**Prior predictive checks, run and reported before the fit.** Draws from the prior
must produce implied hold rates that span the full range across plausible barrier
configurations without piling up at 0 or 1. If they do not, the priors are revised
**before** any label is seen, and the revision is recorded here as a version bump.

### 7.5 Five levels is not many, and here is what is done about it

The fire-complex random effect has five levels, which is few enough that
`sigma_fire` is barely identified by the data. Four decisions, all pre-registered:

1. The random effect is on the **intercept only**. No random slopes. There is not
   enough between-complex information to estimate a varying width effect, and
   attempting it would produce a width posterior that is mostly prior.
2. `sigma_fire` gets an informative HalfNormal(0.5) rather than a half-Cauchy. On
   the logit scale this allows complex-level shifts of roughly one unit at two
   standard deviations, which is a large but not absurd between-fire difference. A
   heavy-tailed prior with five groups puts too much posterior mass on values the
   data cannot rule out.
3. A **prior sensitivity analysis over `sigma_fire` in {0.25, 0.5, 1.0}** is
   pre-registered, and the width posterior under all three is reported in the same
   table. If the width conclusion changes across them, the conclusion is that the
   record does not support a width conclusion.
4. **No per-complex claim is made.** The complex intercepts are reported as
   partially pooled estimates with intervals, and nothing of the form "fire X had
   a higher hold rate" is written, because with five levels that comparison is
   noise.

A parallel **complete-pooling** fit and a parallel **fixed-effect** fit are also
pre-registered, and all three are reported. If the three disagree about F1, F1 is
judged on the partially pooled fit and the disagreement is reported in the
abstract.

### 7.6 Computation and convergence gates

PyMC, NUTS, 4 chains, 2,000 warmup and 2,000 post-warmup draws per chain,
`target_accept` 0.9, seed fixed and recorded. On one laptop, no GPU (scope rule 4).

Every reported parameter must reach R-hat below 1.01 and bulk effective sample
size above 400. Divergences must be zero; a non-zero count triggers
reparameterisation, and both the failure and the fix are recorded. A fit that
cannot clear these gates is not reported as a result at all.

### 7.7 What this design cannot identify, named in advance

A pre-registration that names no unidentified parameter has not looked hard
enough. Two are named here, and the first is structural.

#### 7.7.1 The flame-crossing and ember-spotting split

**The problem.** The label is one binary outcome per segment, and the model is

    P(breach) = 1 - (1 - p_flame) * (1 - p_spot)

Only the **product** is constrained by that label. Infinitely many pairs
`(p_flame, p_spot)` give the same product, so a held-or-crossed label cannot
apportion a breach between the two mechanisms. No amount of data of that one kind
fixes it, and no prior choice fixes it honestly either: a tighter prior on
`p_spot` would simply move the answer to wherever the prior was put and dress the
result up as an inference.

**What identifies it.** Information of a **different kind**, observed on a
different support. That is exactly what the far-field spot record of section 7.3
is, and it is why the ember jump-distance distribution is load-bearing rather than
decorative:

- **spot fires detected beyond the barrier**, at distances between 50 m and 2 km,
  with their counts and their distances, pin the spotting rate `lambda` and the
  jump distribution `F` **without** reference to the held-or-crossed label;
- with `lambda` and `F` estimated externally, `p_spot` at a segment becomes a
  computed quantity rather than a free one, and the label is then free to identify
  `p_flame`.

So the split is identified only through the spot record, and only to the extent
that spots are detectable. That is the whole argument for the 50 m boundary of
section 5.3: it is the line that keeps the two kinds of evidence on separate
supports so one can identify what the other cannot.

**What is reported if it stays unidentified.** Condition F4 of section 1.5 is the
trigger, and the consequence is spelled out now so it cannot be softened later:

1. **Only the combined breach probability is reported.** The decomposition is
   stated as not estimable on this record, in the abstract and not only in a
   limitations paragraph.
2. **The ember arm is withdrawn**, not published with wide intervals as if wide
   intervals were an estimate. The jump distances that were observed are published
   as a descriptive figure, under the name of what they are: detectable spot
   distances, truncated at both ends.
3. **The flame arm's coefficients are renamed.** With no separable ember term, the
   fitted logistic is a model of **breach**, not of flame crossing, and every
   coefficient is reported under that name. Width, angle, slope and lee fuel then
   describe the combined mechanism. This is a real loss: the mechanistic reading
   that motivated the product form is gone, and the model becomes a well-specified
   empirical one instead. It is reported as that.
4. **No sentence anywhere attributes a breach to flames rather than to embers, or
   the reverse.**

If the spot count is literally zero across all five fires, the product collapses to
a single logistic by construction and item 3 is the whole outcome. Given the
detection floor and five fires, that is a live possibility and not a remote one.

#### 7.7.2 Barrier physics against suppression effort

The second unidentified quantity is the split between what the barrier did and
what the people standing on it did. It has its own section because it is A6's
strongest objection to this direction: section 12.4.

---

## 8. The comparison model, pre-registered so it cannot become a rescue

A gradient-boosted classifier is fitted on the same data and reported whatever it
says. Pre-registering it now is the point: it exists to answer whether the
structured model misses learnable structure, and it must not be able to turn into
a post-hoc replacement for a structured model that disappointed.

- **Implementation.** scikit-learn `HistGradientBoostingClassifier` (scope rule 4).
- **Design matrix.** Byte for byte the covariate set of section 6.2. No extra
  covariates, no engineered interactions, no post-fire-derived anything.
- **Folds and metric.** Identical to section 10. Standardisation and any tuning
  happen inside the training folds only.
- **Hyperparameters.** A pre-registered grid, searched by nested cross-validation
  inside the training folds. The grid is committed before any fit:
  `max_depth` in {2, 3, None}, `learning_rate` in {0.03, 0.1}, `max_iter` in
  {200, 600}, `min_samples_leaf` in {5, 20}, `l2_regularization` in {0, 1}.
- **Reported regardless of direction.** If the classifier beats the structured
  model, that is reported in the abstract. If it does not, that is reported too.
- **SHAP is description only.** SHAP values over the same covariates are reported
  to say what the classifier used. A SHAP-suggested interaction is **not** added to
  the structured model in this round. It is written into `OPEN_QUESTIONS.md` as a
  hypothesis for a future pre-registration. This sentence is the whole reason the
  comparison is pre-registered.

---

## 9. The baselines the model has to beat

| id | model | why it is here |
|---|---|---|
| B0 | intercept only, the base hold rate | the floor; anything that cannot beat this is not a model |
| B1 | **width-only logistic regression** on `W_cleared` | the honest candidate, and the one that matters |
| B2 | width plus barrier type | separates "width matters" from "roads, rivers and ridges differ" |

B1 is the primary comparison. If B1 does as well as the structured model, the
finding reported is that on this record width alone accounts for what can be
measured, and the structured model's extra terms are not earning their place.
That is a real finding and it is written as one. F2 in section 1.5 is the rule
that makes it happen automatically.

---

## 10. Held-out sets, the primary metric, and the decision rules

### 10.1 The folds, named now

Leave-one-complex-out, five folds, fixed before any data is touched:

1. Goseong 2019
2. Uljin and Samcheok 2022
3. Gangneung 2023
4. 의성 and 안동 2025 (and 영덕 2025 if it is ever added, per section 2.2)
5. Sancheong 2025

The exact call, its keyword arguments, both fingerprints and the row-order
convention are in section 18, which is item P6. This subsection names the folds;
section 18 makes the naming checkable.

Nothing is tuned on a held-out complex. Standardisation constants, hyperparameter
choices and thresholds are all computed inside the training folds. **The width
error model `b` and `sigma_u` is the one declared exception and it is not
fold-internal**, for the reason set out in section 6.3.4: the hand measurement runs
on pre-fire imagery, before any label exists and blind to the label, so it carries
no outcome information across a fold boundary, and a per-fold estimate from about a
dozen repeat pairs would be noise. v0.1b listed the digitising error among the
fold-internal quantities and section 6.3.4 estimated it across all five complexes;
that contradiction is resolved here in favour of section 6.3.4, and the exception
is named so that it is a declared design choice rather than an inconsistency a
reviewer has to find.

### 10.2 The primary metric, named now

**Mean out-of-complex log predictive score per labelled segment**, higher is
better. It is a proper scoring rule, it rewards calibration and discrimination
together, and the deliverable is a probability that a county office would act on,
so calibration is not optional. It is computed under the held-out random-effect
rule of section 10.7, which is the rule B7 requires to be named in advance.

**Its uncertainty, and the resampling unit, which P7 requires and v0.1b omitted.**
The clustering unit from P2 is the fire complex, and there are five of them. A
bootstrap over five clusters does not produce an interval anybody should quote, and
saying so is more useful than producing one. So the uncertainty is reported in two
parts and the limits of each are stated on the same line:

1. **The five per-fold values themselves**, reported in full, always, with the
   held-out complex named beside each. With five clusters this is the honest
   presentation, and the spread across the five is what is quoted whenever a single
   uncertainty statement is wanted.
2. **A cluster bootstrap resampling barrier lines within the held-out complex**,
   2,000 resamples, reported per fold. This captures the within-fold component only
   and is stated as a **lower bound** on the true uncertainty, because it does not
   resample complexes and therefore cannot see the between-fire variance that
   dominates. It is never reported without that sentence attached.

Nowhere is a segment-level bootstrap reported, because segments within a barrier
line are near-duplicates (leakage item A11 and B6) and an interval built from them
would be far too narrow.

### 10.3 Secondary metrics

Brier score, PR-AUC, calibration slope and calibration intercept, each reported
per fold with the held-out complex named, never bare, and each under the same
held-out random-effect rule as the primary. Secondary metrics are labelled
secondary in the artifact's key paths as well as in prose (section 22), so a
secondary cannot be promoted by being quoted without its label.

### 10.4 The decision rule against the baseline

With five folds, a formal test has almost no power, and pretending otherwise
would be the kind of thing this document exists to prevent. The pre-registered
rule is therefore deliberately crude and deliberately strict:

> The structured model is preferred over B1 only if it achieves a higher mean
> out-of-complex log score in **at least 4 of the 5 folds** and the mean
> difference exceeds **0.02 nats per segment**. Otherwise B1 is the model of
> record.

### 10.5 What is done with the indeterminate segments

They are never dropped and never imputed into a label. Two things happen:

1. Their counts, by reason code, by fire and by barrier type, are a reported
   result in their own right, because a design that cannot label most of its
   encounters is telling you something.
2. A **bounding analysis** is pre-registered: the whole primary fit is re-run
   twice, once with every indeterminate segment labelled held and once with every
   one labelled crossed. The width posterior under both extremes is reported
   beside the primary. If F1 fires under one extreme and not the other, the
   reported conclusion is the one that holds under both, which is usually that the
   record does not decide.

### 10.6 Spatial dependence between segments

Adjacent segments on the same barrier line share width, fuel and often the same
crossing event. Three consequences, all handled in advance, and the third is new
in this version.

- a **barrier-line random intercept** is included alongside the fire-complex one,
  so the model does not treat 10 segments of one road as 10 independent
  observations. Composite barriers (section 3.3) carry one composite line id, so a
  road running beside a stream is one line and not two;
- a **lee-patch random intercept** is included as well, grouping segments that
  share one lee burned patch (section 5.6). A single crossing event can produce
  `CROSSED` at several contiguous segments, and the barrier-line intercept does not
  separate that from several independent crossings along one road. This is the
  level A6's scenario S9 and leakage item B6 are about, and it is the one v0.1b did
  not have;
- the **effective number of independent encounters**, estimated from all three
  variance components, is reported next to the raw segment count everywhere the raw
  count appears, and its key path is `labels.effective_encounters.value` with the
  estimation method at `.method`.

P2 requires the row count and the effective sample size as **numbers** and not as
orders of magnitude. Section 11.1's "order 10^2" is a planning estimate written
before the data exists, which is honest at this stage; the numbers are written into
the result artifact at `labels.counts.total_labelled` and
`labels.effective_encounters.value` before the first fit, and the gates of section
11.3 read them there.

### 10.7 Predicting a held-out complex, which is two different models

Leakage item B7 asks a question v0.1b did not answer: when predicting a complex
that was held out, is its random intercept `u[f]` set to zero, or drawn from the
fitted hyperprior? These are two different predictive models, and the
zero-substitution one usually scores better for the wrong reason, because zero is
the mean of a distribution whose spread it then ignores.

**The primary prediction rule is the hyperprior draw.** For a held-out complex,
the predictive distribution integrates `u[f]` over `Normal(0, sigma_fire)` using
the posterior draws of `sigma_fire`, so the held-out prediction carries the
between-complex uncertainty the fit actually estimated. This is the honest
predictive distribution for a fire nobody has seen, and it is the one the primary
metric of section 10.2 is computed under.

**The zero-substitution rule is reported alongside**, at its own key path in the
result artifact, labelled as the optimistic variant. Both numbers appear in the
comparison table of section 13 item 9, and the difference between them is itself
reported, because that difference is a direct measurement of how much of the
model's apparent skill is a fire-level offset it could not have known.

The same rule applies to the barrier-line and lee-patch intercepts of section
10.6: a held-out complex contains barrier lines and lee patches the fit never saw,
so those are integrated over their hyperpriors too, and the rule is stated once
here for all three levels rather than three times.

---

## 11. Sample size, honestly, and what happens when it is small

### 11.1 The honest estimate

These are planning estimates from public order-of-magnitude reasoning, not
measurements, and A3 has fetched nothing.

Korean forest road density is of order a few metres per hectare, so a fire of
20,000 ha plausibly contains tens of kilometres of forest road, which is hundreds
of 100 m segments before any filter. Across five fires the raw segment count is
plausibly in the high hundreds to low thousands.

The eligible and labelable count is far smaller, and the filters compound:

- ineligible lee side, section 4.5;
- cloud, smoke or missing overpass, `CLOUD` and `SCENE`;
- flanking ambiguity in the fire interior, `FLANK`;
- mid-range lee burned fraction, `MID`;
- unknown width, `WIDTH`.

A working expectation is **order 10^2 labelable segments in total**, possibly a
few hundred, with **held segments much rarer than crossed ones**, because held
segments sit on the fire perimeter while crossed ones fill the interior. And the
effective sample size is smaller again: after the barrier-line variance component
of section 10.6, the number of genuinely independent encounters could plausibly
be in the tens.

The class balance risk is worth saying out loud: if held segments number in the
low tens, the width term is being estimated from a few dozen events, and no
amount of Bayesian machinery makes that into a curve.

### 11.2 The width support problem, which is the design's real cliff

The claim under test is about 6 m. Korean forest road design classes put most
running surfaces well below that, so if `W_surface` is nearly constant across the
sample there is nothing to regress against. `W_cleared` has more spread, and
rivers span a wide range, but rivers differ from roads in riparian fuel, valley
position and humidity, so a width slope carried mainly by the road-versus-river
contrast is a barrier-type effect wearing a width effect's clothes. Section 11.3
gate W1 exists precisely for this.

A1's confirmation that the road layer carries no width attribute makes this worse
in a specific way. The width contrast is now not merely narrow, it is also
measured with error, and the two problems multiply: the attenuation factor `kappa`
of section 6.3.4 has `sigma_x`, the true width spread, in its numerator. A sample
with little true width variation is exactly the sample in which a given
measurement error does the most damage. Gates W1 and M1 are both needed, and they
are checked together.

### 11.3 Feasibility gates, declared now, with the phase each is checked in

Every gate is checked in a fixed phase, the branch taken is recorded, and the
boolean outcome of each gate is a key in the result artifact (section 22). Three
of them now run **before** the labelling rather than after it, which is the change
A6 asked for when it said the recoverability harness should be built and reported
before the labelling starts.

| gate | phase | condition | consequence if not met |
|---|---|---|---|
| **E1** | after acquisition, before layout | at least two fire complexes supply road segments that pass the edition or existence check of section 3.4 | the roads arm is not executable. Rivers and ridges continue, the width slope is reported for rivers only, and no statement of any kind is made about forest roads |
| **S1** | after detections land, before labelling | check S0 of section 5.1.3 shows at least 0.25 of candidate segments passing the side test at `z_side` = 2.0, in at least three complexes | the side assignment fails at scale. The round delivers check S0's distributions as its result and no label is computed, because a labelled table built from a quarter of a quarter of the candidates is not a table |
| **R0** | after width measurement, before labelling | instrument 2 of section 11.5.2 reports detection power at the smallest effect of interest of at least **0.20** | the labelling proceeds for the descriptive deliverables only and **the width fit is not attempted**. 0.20 is a much lower bar than the 0.80 of instrument 2 and it is a different decision: 0.80 decides whether a flat curve is informative, 0.20 decides whether the labelling effort is worth spending on the width question at all |
| **L1** | during labelling | at most 3 of the thirty rule-validation units of section 5.8 disagree at the three-class level | the label rule is amended, the amendment is a new version, and the pass is re-run on a freshly drawn thirty before any fit |
| **G1** | on the labelled table, before the first fit | at least 150 labelable segments **and** at least 30 held | full specification, section 7.2 |
| **G2** | same | 60 to 150 labelable, **or** 10 to 30 held | **reduced specification**: covariates cut to width, barrier type and signed slope; fire effect becomes a pooled intercept with the section 7.4 prior; the ember arm is descriptive only |
| **G3** | same | fewer than 60 labelable **or** fewer than 10 held | **no model is fitted.** The round delivers the labelled dataset, the descriptive tables, the indeterminate counts and the bounding analysis, and records the design as untestable on this record (F5) |
| **W1** | same | within the road barrier type, at least 25 segments with **`W_cleared`** at or above 6 m **and** at least 25 below | the width curve is reported as not identified for roads, and only the barrier-type contrast and the ember distribution are published |
| **N1** | same | at least 15 labelled segments with a night arrival **and** at least 15 with a day arrival, by local solar time from `research/shared/geo/solar.py` | the day-against-night contrast of section 12.4.7 is reported as not estimable, with the two counts given |
| **H1** | same | at most half the labelled segments carry the `AMBIG_HOUR` flag of section 12.11 | the weather covariates are dropped from the primary specification, and that is reported in the abstract rather than in a limitations paragraph |
| **M1** | after the fit | the **lower end of the 90 per cent posterior interval** of `kappa_v` (section 11.5.1) is at or above **0.70**, and at least 60 hand-measured segments support the error model (section 6.3.3) | the width covariate is declared too noisy to carry the question: no breach curve against width is published, F1 cannot be reported as evidence either way, and the outcome is written as **not resolvable at the achieved measurement precision** |
| **M2** | before the fit | exclusion power at the smallest effect of interest (section 11.5.2b) is at or above 0.80 | the informative-null reading of section 11.5.4 is unavailable. A flat curve is then reported as not resolvable, never as an informative null |
| **P1** | after the fit | the width posterior standard deviation is below 0.8 times its prior standard deviation | the width result is reported as prior-dominated and **no breach curve is published at all** |

**W1 counts in `W_cleared`, and the document now says so**, per A6's ruling: W1
sits beside `W_eff` throughout section 11 and the two give different counts, so the
variable has to be named. W1 is not leakage item B11, because it counts support
rather than binning the covariate; width still enters the model continuously and
no 6 m bin exists anywhere in the design matrix.

**M1's interval form makes the "not resolvable" outcome the modal one, and that is
said here rather than discovered later.** A6 ruled that M1 must gate on the lower
end of a declared interval, and A3 adopts it: a point estimate at 0.70 clears a
point gate about half the time when the truth is 0.70, so a point gate is passed by
noise. The arithmetic of what that costs is worth having in advance. With
`sigma_u` estimated to about 13 per cent relative from 30 repeat pairs, `sigma_u`
squared carries about 26 per cent relative, and a point `kappa_v` of 0.70 gives a
5th percentile near 0.62. To reach a lower bound of 0.70 the point estimate has to
be near **0.77**. So the interval form raises the effective requirement by roughly
seven points of `kappa_v`, and combined with A6's own expectation that M1 is the
modal failure it makes "not resolvable at the achieved measurement precision" the
most likely headline of this direction. A3 agrees with the ruling and records the
consequence: `kappa_v` and its interval are reported as **numbers**, always, never
as a pass or a fail, so that a design landing at 0.68 is not reported the same way
as one landing at 0.31. That is the same treatment A6 required for recoverability
in its section 8.2, applied to the gate beside it.

P1 is the one that stops a pretty figure being drawn out of a prior. M1 is its
counterpart for measurement rather than prior: it stops a flat curve being drawn
out of a noisy ruler. Both can veto the headline output, and both are checked and
reported whatever they say.

### 11.4 If the sample is an order of magnitude smaller than hoped

That is the G3 branch, and it is not a failure of the round. The labelled
encounter table, with its pre-registered rules and its indeterminate accounting,
is itself the deliverable, and it is what a later round or a later fire would be
appended to. What is **not** done in that branch: fitting anyway, reporting a
curve with an interval spanning most of the unit interval, or quietly relaxing a
threshold from section 5 to manufacture rows.

### 11.5 The reading rule for a flat breach curve

**This is the section A6 asked for, and it is the one to read first.** The road
layer has no width attribute (section 6.3), so width is measured, and classical
measurement error attenuates a slope toward zero. **A flat curve is therefore what
a true null and a badly measured covariate both produce.** Deciding between them
after seeing a flat curve would be exactly the kind of reasoning this document
exists to forbid, so the procedure is fixed here, before the fit, and it does not
rest on the fitted slope, because the fitted slope is the thing under suspicion.

Six instruments, four of which run **before any label is computed**: instrument 1,
instrument 2, instrument 2b and instrument 5's first two checks. Instrument 2b is
new in this version and is A6's repair (b); it is numbered 2b rather than 6 because
it is the second arm of the same simulation and shares its geometry, its draws and
its seed.

#### 11.5.1 Instrument 1: the repeat-measurement study, and `kappa` on the right scale

Thirty segments measured twice, independently (section 6.3.3). This yields
`sigma_u`, the measurement error standard deviation on `W_cleared`, to about 13
per cent relative.

**The attenuation factor is defined on the covariate the model uses, which is A6's
repair (a).** v0.1b defined it on raw width. The fitted covariate is
`v_i = log(W_eff_i + 1)` with `W_eff_i = W_cleared_i / s_i` and
`s_i = sin(max(theta_i, 15 deg))`. By the delta method the induced error on `v_i`
has standard deviation approximately

    sigma_v_i  ~  sigma_u / ( W_cleared_i + s_i )

which is heteroscedastic, segment-dependent, and **largest for the narrow barriers
at grazing angles that carry most of the leverage**. That expression is stated for
intuition only. The reported quantity does not rely on it: `sigma_v_i` is obtained
by Monte Carlo, drawing `W_cleared_i` from its posterior under the
errors-in-variables layer and pushing each draw through the exact transform, so the
delta-method approximation is nowhere load-bearing.

Then, with `Var(v_true)` the posterior variance of the true transformed covariate
across the sample,

    kappa_v        = Var(v_true) / ( Var(v_true) + mean_i( sigma_v_i^2 ) )
    kappa_v_i      = Var(v_true) / ( Var(v_true) + sigma_v_i^2 )

- **`kappa_v` is the single summary that gate M1 gates on**, and the document says
  which summary it is: the sample-mean-error version above, reported with a 90 per
  cent posterior interval, with M1 reading the lower end.
- **`kappa_v_i` is reported as a distribution**, with its deciles and with a plot
  against `W_cleared` and against `theta`, because the whole content of A6's repair
  is that a single number hides where the measurement is worst.
- **`kappa_raw`** on the raw width scale is reported as a continuity diagnostic,
  labelled as a raw-scale quantity, so that a reader comparing against v0.1b can
  see both. It gates nothing.

The two algebraic spellings of the raw-scale factor that v0.1b carried,
`(sigma_obs^2 - sigma_u^2)/sigma_obs^2` and `sigma_x^2/(sigma_x^2 + sigma_u^2)`,
are identical under `sigma_obs^2 = sigma_x^2 + sigma_u^2`, as A6 verified. Only
the scale was wrong, and only the scale has changed.

#### 11.5.2 Instrument 2: design-stage recoverability, before labelling

This is the decisive one, and it is available before a single label exists.

Take the **real** segment geometry and the **real** measured width distribution,
including its real measurement error from instrument 1. Simulate outcomes under a
pre-registered non-null slope equal to the smallest effect of interest (section
11.5.3). Refit the pre-registered model to the simulated outcomes. Repeat 500
times. **Detection power** is the fraction of simulations in which the fitted
model reaches the F1 threshold of `P(beta_width < 0)` at or above 0.90.

- Detection power is computed on **simulated outcomes only**. The real labels are
  never touched, so this can and must be run while the labelling is still in
  progress, and the number is committed before any real fit.
- **Reported at both the 0.80 threshold and the achieved value**, never as a pass
  or a fail, per A6's section 8.2. A design landing at 0.79 is not reported the
  same way as one landing at 0.31.
- **If detection power is below 0.80, a flat curve is uninformative whatever the
  real fit produces, and that is known in advance.** The pre-registered consequence
  is that the width result is reported as **not resolvable at the achieved
  measurement precision and sample size**, and F1 is not reported as evidence
  either way.
- **Gate R0 sits below it at 0.20** (section 11.3) and is a different decision: it
  decides whether the labelling effort is worth spending on the width question at
  all, and it runs before the labelling rather than beside it.

#### 11.5.2b Instrument 2b: exclusion power, which is A6's repair (b)

Detection power is the right number for F1 and it is **the wrong number for the
informative-null claim**. The middle row of instrument 4 requires the disattenuated
interval to **exclude** the smallest effect of interest, and a design can have
adequate power to detect an effect while having almost no ability to exclude one,
because exclusion depends on the width of the interval at a point away from zero
rather than on the posterior mass on one side of zero. v0.1b gated a claim about
exclusion on a measurement of detection, which A6 is right to refuse.

The second arm, at the same 500 draws, the same real geometry and the same real
measurement error:

> Simulate outcomes under a **true width slope of zero**. Refit the pre-registered
> model. **Exclusion power** is the fraction of simulations in which the 90 per
> cent credible interval on the disattenuated probability contrast between
> `W_cleared` of 6 m and `W_cleared` of 3 m, at the sample median approach angle,
> lies **entirely below the smallest effect of interest**.

- Exclusion power is computed on the same probability-contrast scale as the
  smallest effect of interest, so the two are directly comparable and no conversion
  is needed at reading time.
- **Gate M2 sits at 0.80**, and the middle row of instrument 4 is conditional on
  it. Below 0.80 the informative-null reading is simply unavailable, whatever the
  real interval turns out to do.
- Exclusion power is reported at both the threshold and the achieved value, like
  detection power.
- Both arms are reported at the primary smallest effect of interest of 0.05 and at
  the 0.10 reported alongside it, so a reader can see what the design could have
  excluded at each.

#### 11.5.3 Instrument 3: a smallest effect of interest, ruled and fixed

The null has to be null **of something**, or an equivalence claim is unfalsifiable.
A6 refused v0.1b's value of 0.10 and ruled that **the unit was wrong before the
level was**: v0.1b stated the effect over **effective** width, which is a composite
of cleared width and approach angle, and a county planner builds cleared metres,
not effective ones. Both the unit and the level are fixed here as A6 ruled them.

> **The pre-registered smallest effect of interest is a change of 0.05 in the
> modelled probability of a lee-side burn between `W_cleared` of 3 m and
> `W_cleared` of 6 m, at the sample median approach angle, holding every other
> covariate at its sample median.**

- **The unit is `W_cleared`.** The corresponding `W_eff` contrast is reported
  beside it at the sample median approach angle, so the two are legible together.
  It is a reported quantity, not a pre-specified number, because the sample median
  approach angle does not exist before the data does.
- **The contrast is 3 m to 6 m, and it is the only contrast.** v0.1b used 3 m to
  9 m here and 3 m to 6 m in F3, which made a pre-registered failure condition and
  a pre-registered equivalence threshold refer to different quantities. One
  contrast now serves both, and 6 m is chosen because it is the width in the claim
  under test.
- **The level is 0.05, and 0.10 is reported alongside, with 0.05 primary.**
  Instrument 4's equivalence reading is reported at both, so a reader sees the
  effect size the record can exclude rather than a binary, and the informative-null
  sentence, if it is ever written, carries the number it excluded inside it.

**A6's three reasons for 0.05, recorded here because the number is A6's and not
A3's.** The threshold must be set by what matters rather than by what is
reachable, which is the whole point of instrument 3 and the one place the
temptation runs hardest the other way. The decision it feeds aggregates: forest
road widening is a capital programme over tens of kilometres, and over a few
hundred encounter-segments a five point shift in breach probability is a different
number of holds. And the error costs are asymmetric in a life-safety context,
because the consequence of wrongly declaring an effect not worth acting on is that
somebody stops widening roads.

**What A6 recorded in advance, and A3's agreement.** A6 states that it expects
recoverability at 0.05 to fall below 0.80 on the sample sizes section 11.1 plans,
and therefore expects this design to report "not resolvable" rather than an
informative null, and that this is the correct outcome and not a failure. A3
agrees, and draws one operational consequence that A6 hinted at and did not
formalise: if that is the expected branch, **the recoverability simulation should
be allowed to stop the labelling rather than merely to caveat it.** That is gate
R0 in section 11.3. Learning that a Korean five-fire record of this size cannot
resolve the question is a publishable result, and it is cheaper to learn it before
several hundred segments are labelled than after.

#### 11.5.4 Instrument 4: the equivalence reading of the disattenuated posterior

After the fit, on the **errors-in-variables posterior only**, never the naive one,
and at both 0.05 (primary) and 0.10 (reported alongside):

| what the disattenuated interval does | how it is read |
|---|---|
| excludes zero in the hypothesised direction | the width term is reported with its interval, and F1 does not fire |
| **excludes the smallest effect of interest**, and gate M2 holds, and instruments 1, 2 and 5 all pass | **an informative null.** The record is reported as inconsistent with a width effect large enough to matter, with the effect size it can exclude stated explicitly inside the sentence |
| includes both zero and the smallest effect of interest | **uninterpretable.** Reported as not resolvable at the achieved measurement precision, and F1 is not reported as evidence either way |

The middle row is the outcome that makes a null worth publishing. The bottom row
is the outcome this section exists to stop being mistaken for it. **The middle row
is conditional on gate M2**, which is A6's repair (b): without demonstrated
exclusion power the design was never shown capable of producing the exclusion it
would be claiming.

#### 11.5.5 Instrument 5: is the measurement a measurement at all?

Attenuation assumes the ruler is noisy. A broken ruler is a different failure and
needs a different check, so the measured width is validated against things it must
predict **if it is a real measurement**, none of which involve the outcome:

- measured road width against the road class field, if the SHP carries one
  (section 6.3.5): the class design widths must order correctly;
- measured river width against upstream flow accumulation from the DEM: a wider
  channel must sit on a larger catchment;
- measured width against itself across the two independent passes of instrument 1.

If width fails these, **the measurement is broken and the hypothesis has not been
tested**. That is reported as a measurement failure, and no curve is published.

There is also a negative control available for free: ridges carry zero width by
construction (section 3.1). A width effect appearing where no width exists is a
sign that the pipeline is wrong, not that ridges are narrow.

#### 11.5.6 The decision, in one place

A flat curve is reported as an **informative null** only when all five hold:

1. gate M1: the lower end of the 90 per cent interval on `kappa_v` is at or above
   0.70, and at least 60 hand-measured segments support the error model;
2. detection power at or above 0.80 (instrument 2);
3. **gate M2: exclusion power at or above 0.80 (instrument 2b)**;
4. the disattenuated interval excludes the smallest effect of interest at 0.05;
5. the measurement passes instrument 5.

If any one fails, the outcome is **not resolvable at the achieved measurement
precision**, and the document says in terms that this is not a synonym for "width
does not matter". The conjunction is deliberate and it is stated as a conjunction
so that the informative-null claim cannot be reached by reading four of five
favourably.

---

## 12. Leakage traps, addressed before A6 raises them

### 12.1 The one A6 will raise first: severity encodes its own label

The label is computed from dNBR on a specific scene pair. Any severity covariate
computed from that same scene pair is partly the label, and a model given it will
look good for no reason.

**The fix is a hard constraint, not a caution.** Section 6.1: no covariate in
either arm may be derived from the post-fire scene, and none from any spectral
index at all, pre-fire included. Pre-fire indices are excluded too, because the
secondary label index is RdNBR, which has pre-fire NBR inside it, so a pre-fire
index is also a partial function of a label this direction computes and reports.
Section 5.4 moves the **primary** index to dNBR, and it explicitly does not relax
this firewall: loosening a constraint because the index it guards has moved is the
exact shape of drift the firewall exists to stop. Fuel and fuel load come from the categorical
임상도 and land-cover layers; intensity comes from detection timing and geometry;
weather comes from station observations. A committed audit script resolves every
column in the design matrix to a source layer and fails if any resolves to the
scene pair.

The cost is real and is accepted: the design gives up the most natural intensity
proxy, and the 임상도 fuel classes are coarser than a spectral fuel index would be.
That is the price of the label being independent of the covariates.

### 12.2 Adjacent-segment leakage

Random cross-validation would put a segment's immediate neighbour in the training
set. Leave-one-complex-out is the primary split (section 10.1) and no random split
is reported anywhere. Any within-fire secondary split is blocked by barrier line,
never by segment.

### 12.3 The two arms eating each other

A spot fire that lands 30 m past a barrier would be scored as a flame crossing if
the boundary were not fixed. The 50 m boundary of section 5.3 is one boundary for
both arms, and a lee burn not contiguous with the barrier edge is a spot and not a
crossing (section 5.5). The flame arm is a near-field statement by construction.

### 12.4 Confounding by suppression effort, which is the strongest objection to this direction

**A6 names this as its strongest prior objection, and it is correct.** It is set
out here in full rather than as a caveat, because a document that does not notice
the problem is weaker than one that states it and bounds it.

#### 12.4.1 The mechanism

A wide Korean forest road is also the road the engines drove in on and the line
the crews held. Width, access and suppression effort are produced by the same
decisions: roads are built where machinery can go, wider roads are built on the
routes that matter, and a crew that has to anchor a line anchors it on the widest
road it can reach. So a segment that held may have held because the gap was wide,
or because two engines and a crew were standing on it, and the two arrive together.

This lands specifically on the width coefficient, which is the coefficient the
whole direction is about. It is not a general caveat about observational data.

#### 12.4.2 Nothing in the planned covariate set separates them

Said plainly, because it is true: **the covariate set of section 6.2 cannot
separate barrier physics from suppression effort.** There is no suppression
resource placement record in `research/data/REGISTRY.yaml`, and obtaining one is an
information-disclosure request and therefore a human gate (WJ-010 on the
taskboard).

A proximity proxy is also rejected, and the reason is worth stating because the
proxy is the obvious move. Distance to the nearest station, or road-class-based
accessibility, is a function of the road network, which **is** the barrier layer.
Controlling for it would put the exposure inside its own control variable, and
what came out would be neither the physical effect nor the operational one. A bad
control is worse than an acknowledged confound.

#### 12.4.3 The one discriminator the design does have

Rivers and ridges are barriers that crews cannot drive along. Access to a river
line is not produced by the river's width the way access to a road is produced by
the road's width, so the access confound is weaker there, although it is not
absent (crews still work from riverbanks, and rivers carry their own confounds in
riparian fuel, valley position and humidity).

Pre-registered as a secondary analysis, always reported:

> the width slope estimated on roads is compared with the width slope estimated on
> rivers. A width effect of similar sign and magnitude on rivers, where the access
> mechanism is weaker, is weak evidence that the road slope is not purely access. A
> width effect on roads and none on rivers is consistent with access driving the
> road slope, and is also consistent with rivers simply being a different kind of
> barrier.

This is a weak instrument and it is labelled as one. It cannot settle the question.
It is pre-registered anyway, because a weak discriminator declared in advance is
worth more than a strong one invented afterwards, and because its two possible
outcomes are both written down here before it is run.

#### 12.4.4 What the width coefficient can and cannot be read as

This is the reading rule, and it governs every output of this direction.

**It can be read as:** the association between a barrier's measured width and the
absence of a lee-side burn, given front arrival, **for barriers as they are
actually used in Korean wildfire operations**, which includes their use as access
routes and as anchor lines. That is a real and operationally meaningful quantity.
A planner comparing "a landscape with wider forest roads" against "a landscape
without" is asking about roughly that bundle, and this direction can speak to it.

**It cannot be read as:** the effect of the fuel gap on flame propagation; the
effect of widening an existing road; a prediction of what a 6 m road would do
without crews on it; or grounds for any counterfactual about construction policy.

**Concretely, in the outputs:** the estimated quantity is named **operational
barrier performance** in every table, figure caption and abstract sentence, never
"barrier effectiveness" and never "the effect of width". The distinction is <!-- research-vocab-ok: RV-001, RV-002 -->
enforced in the same way as the claim rules: a fixed vocabulary, used everywhere or
nowhere.

#### 12.4.5 Selection, the general form of the same problem

Underneath the suppression confound is a plainer one: a barrier that stopped a
fire is, by construction, part of that fire's perimeter, and everything else that
decides where a fire stops (a wind drop, nightfall, rain, a fuel change) arrives
bundled into the same encounter. Conditioning on arrival (section 4) and on
arrival-hour weather (section 6.2) does real work against this, and it does not
finish the job. Section 1.4 states the estimand as associational for this reason.


#### 12.4.6 The vocabulary, with a detector rather than a promise

A6's condition, in its own words: section 12.4.4 says the distinction is "enforced
in the same way as the claim rules: a fixed vocabulary, used everywhere or
nowhere", and the claim rules are enforced by
`research/shared/check_research_claims.py`, which has no rule for this vocabulary.
**A fixed vocabulary that nothing checks lasts until the first author who writes a
figure caption in a hurry.** That is correct and it is met two ways here, one
inside A3's ownership and one outside it.

**Inside A3's ownership, and therefore done rather than requested.**
`research/roads/check_vocabulary.py` is committed with this version. It scans
`research/roads/**` and `research/reports/A3/**`, it fires on the assertive
spellings and spares the permitted one, it carries a `catches` corpus and a
`spares` corpus and a `--self-test` that runs both, and it exits non-zero on a
violation. Its rule table is:

| id | fires on | spares |
|---|---|---|
| `RV-001` | "barrier effectiveness", "effectiveness of the barrier", "방화선 효과" as a noun phrase about this direction's estimand | "operational barrier performance"; any line that also carries "operational barrier performance"; hedged lines under the same hedge guard as the claim checker |
| `RV-002` | "the effect of width", "the effect of road width", "width effect on breach" stated as this direction's estimand | "the width slope", "the width term", "the association between width and", "operational barrier performance" |
| `RV-003` | "wider roads hold fires", "wider roads stop fires", "넓은 임도가 산불을 막는다" | the same sentences under the hedge guard, and quotations of the claim under test that name it as the claim under test |

The per-line pragma convention is the repository's own
(`<!-- research-vocab-ok: RV-001 -->`), there is no whole-file exemption, and the
rule's own statement in this table carries the pragma so the file does not fail
against itself.

**Outside A3's ownership, and therefore a request.** A3 does not own
`research/FORBIDDEN_CLAIMS.md` or `research/shared/check_research_claims.py`, so
the program-wide version is drafted here as **RC-011** and is a dependency in
section 15.4, not something this document can land:

<!-- research-vocab-ok: RV-001, RV-002 -->
> **RC-011.** The roads direction's estimand stated as barrier effectiveness or as
> the effect of width. *Why:* the quantity is an association under Korean
> suppression practice, and 12.4.4 forecloses the counterfactual reading that a
> county planner would otherwise take by default. The fixed term is **operational
> barrier performance**.

The local detector holds the line inside the roads tree until RC-011 lands. It is
a copy-paste ratchet and not a claim detector, the same limit the research claims
checker records for itself, and the ratchet is the part that matters: it stops the
assertive spelling spreading across the tree by copy and paste.

#### 12.4.7 The day-against-night contrast, which the design already held

A6 points out that item B2 of its own checklist names time of day as a proxy for
helicopter availability, that section 6.2 already carries local solar hour of
arrival as a covariate, and that **Korean aerial suppression does not fly at
night**. So the design holds a second discriminator against suppression
confounding and v0.1b was not using it. That is a fair finding and the contrast is
pre-registered here, with both of its outcomes written down in advance the way the
rivers comparison's were.

**Definition.** A segment's arrival is **night** when its fitted arrival time
(section 6.4) falls between local sunset and local sunrise at the segment's own
coordinates on the arrival date, computed by `research/shared/geo/solar.py`.
**Never** from the 일출시간 and 일몰시간 columns of `kfs_fire_state_history_csv`,
which A1 has confirmed carry a single national value per date across all 607 dates
in the file.

**The analysis.** A pre-registered, always-reported secondary specification adds a
width-by-night interaction to the flame arm, and the width slope is reported
separately for day arrivals and night arrivals with its interval. Gate N1 of
section 11.3 requires at least 15 labelled segments in each.

**The three outcomes, written now.**

1. **The width slope is materially larger by day than by night.** This is
   consistent with aerial and ground suppression contributing to the day-time
   association. The width coefficient is then reported with that reading attached
   in the abstract, and the night-only slope is reported beside the pooled one.
2. **The width slope is similar by day and by night.** This is weak evidence that
   the association is not primarily aerial suppression. It is weak for a reason
   that must be stated wherever it is quoted: night also changes fire behaviour
   through humidity, wind and stability, and all three are already covariates in
   the model, so conditioning on them removes part of the very contrast the
   discriminator relies on. A near-equal slope is therefore consistent with no
   suppression effect and also with a suppression effect that the weather
   covariates have absorbed.
3. **The width slope is larger by night than by day.** This is reported as
   uninterpretable on this design and is **not** read as evidence for the barrier
   mechanism. Night differs from day in too many ways that this design does not
   separate, and a reading that treats an unexpected direction as confirmation is
   the failure this subsection exists to prevent.

Like the rivers comparison of 12.4.3 this is a weak instrument and it is labelled
as one. It cannot settle the question. It is pre-registered anyway, because a weak
discriminator declared in advance is worth more than a strong one invented
afterwards, and because **a discriminator noticed after the fit is worth nothing**.

### 12.5 Analyst leakage through width measurement

Width is now measured rather than read from an attribute (section 6.3), which
creates a leakage route that an attribute would not have had: whoever measures a
width can see which side burned, and can drift toward the width that makes the
segment fit the expected story.

The fixes, all pre-registered:

- the automatic extraction of section 6.3.2 runs on pre-fire orthoimagery only and
  never sees a label, and it produces the width for every segment, so the bulk of
  the covariate is untouched by any analyst;
- the hand-measured subsample of section 6.3.3 is presented with the burn footprint
  and the label withheld from the measuring interface and with segment order
  randomised;
- the second independent pass on at least thirty of the 60 is what turns "we were
  careful" into an estimated variance;
- the hand measurements are used to estimate the automatic method's bias and error,
  never to overwrite an automatic width on a segment-by-segment basis. A per-segment
  override is the exact mechanism by which this kind of leakage happens, and it is
  forbidden here.

### 12.6 Post-hoc segment selection

The segment layout script runs and its output is committed **before** any label
is computed (section 3.2). A segment cannot be created, moved or deleted because
of what happened to it.

### 12.7 Fire-level collinearity

If one complex supplies most of the wide barriers, the complex intercept and the
width slope compete for the same variance. The within-complex width variation is
reported per complex before the fit, and the fixed-effect (within-complex) width
estimate is reported beside the partially pooled one (section 7.5).

### 12.8 Threshold shopping, and the sensitivity register

**v0.1b asserted that "the buffer distances are all fixed in this document. The
sensitivity analyses over them are declared here" and they were not. A6 is right,
and this subsection is the repair (leakage item B4).** What v0.1b actually declared
was a grid over `tau_burn` and a segment length at 50 m and 200 m. There was no
grid over the inner exclusion and none over the band's outer edge, which is the
one that matters most, because the 50 m edge is both the outer edge of the label
band **and** the boundary between the flame arm and the ember arm: moving it moves
the label and reassigns events between the two arms of a model whose whole form is
a product of the two.

Every number below is fixed at its primary value in this document. Every grid is
run one parameter at a time from the primary, and **every value in every grid is
reported**, in the label accounting table and in the width posterior table, never
only the chosen one.

| parameter | section | primary | grid | what moves with it |
|---|---|---|---|---|
| `d_in`, inner exclusion | 5.3 | 10 m | {5, 10, 20} m | the barrier edge offset, and therefore the analysis band on both sides. Coupled to the width measurement, see below |
| `d_out`, band outer edge | 5.3 | 50 m | {30, 50, 80} m | the label, **and** the ember arm's inner truncation, **and** the 7-pixel minimum of section 4.0, which is held at 0.70 of the nominal band pixel count at each value (5, 7, 11) |
| `tau_burn`, dNBR | 5.4 | 0.10 | {0.05, 0.10, 0.15, 0.20} | the burned mask, C1, `f_lee` |
| `tau_burn_R`, RdNBR secondary | 5.4 | 0.15 | {0.10, 0.15, 0.20, 0.25} | the secondary label only |
| RdNBR divisor floor | 5.4 | 0.10 | {0.05, 0.10, 0.20} | which pixels the RdNBR arm can use |
| `f_lee` held cut | 5.5 | 0.10 | {0.05, 0.10, 0.15} | `HELD` against `MID` |
| `f_lee` crossed cut | 5.5 | 0.50 | {0.40, 0.50, 0.60} | `MID` against `CROSSED` |
| `z_side` | 5.1.2 | 2.0 | {1.5, 2.0, 2.5} | how many segments survive the `SIDE` step |
| `d_bypass_min` | 5.6 | 500 m | {300, 500, 800} m | `CROSSED` against `FLANK` and `FLANK_AMBIG` |
| smoke `AOT_excess` | 5.2.1 | 0.10 | {0.05, 0.10, 0.20, 0.40} | usable pixels, therefore every count |
| smoke absolute ceiling | 5.2.1 | 0.60 | {0.45, 0.60, 0.80} | as above |
| `A_min` | 7.3 | 4 pixels | {2, 4, 8} pixels | the spot record |
| `R_max` | 7.3 | 2,000 m | {1,000, 2,000, 3,000} m | the spot record and the truncation |
| `delta_flank` window | 5.6 | fit standard error | not gridded; it is a fitted quantity, not a chosen one | |
| segment length | 3.2 | 100 m | {50, 100, 200} m | everything. Reported as a sensitivity and never as a model-selection step |
| `sigma_fire` prior | 7.5 | HalfNormal(0.5) | {0.25, 0.5, 1.0} | the partial pooling |
| arrival rule, four numbers | 12.9 | see 12.9 | see 12.9 | which segments exist at all |

**Three couplings that a grid table alone would hide**, stated so that no
sensitivity result is read as an independent axis when it is not:

1. **`d_out` moves two things at once.** Each value of `d_out` re-runs both arms
   with the ember truncation moved to the same value, and the count of events that
   change arms between grid values is reported. A grid that moved the label
   boundary and left the ember truncation at 50 m would double-count at every value
   except the primary, which is the specific defect A6's item B4 names.
2. **`d_in` is not independent of the width measurement.** The band starts from the
   barrier edge, which is the centreline offset by half the **measured** width, so
   a segment measured wider has its band pushed outward. The `d_in` sensitivity
   therefore partly re-expresses `sigma_u`, and it is reported with that noted.
3. **The `z_side` grid is a selection grid, not a labelling grid.** It changes which
   segments are labelled rather than how a labelled segment reads, so its output
   belongs in the accounting table and in the section 12.9 clustering check, and its
   effect on the width posterior is reported there rather than as a label
   sensitivity.

### 12.9 The arrival rule, its grid, and whether its exclusions cluster on the wide barriers

**Leakage item B3, which A6 ended at `unresolved` and which is the second of the
two CRITICAL items that refused v0.1b.** Section 4's C1 to C4 are a genuine arrival
definition and section 4.5 publishes ineligible counts per fire and per reason,
which is half of what B3 asks. The other half was missing, and it is the half that
turns censoring into bias on the coefficient of interest. Both halves are here.

**The grid.** Four numbers decide which segments exist at all, and none of them was
on v0.1b's sensitivity list.

| parameter | section | primary | grid |
|---|---|---|---|
| C1 windward burned fraction | 4.1 | 0.80 | {0.70, 0.80, 0.90} |
| C4 minimum detections | 4.4 | 5 | {5, 8, 12} |
| C4 minimum distinct acquisition epochs | 4.4 | 2 | {2, 3} |
| C3 footprint fallback radius | 4.3 | 400 m | {375, 400, 500} m |
| `FUEL` non-burnable fraction | 4.5 | 0.50 | {0.35, 0.50, 0.65} |

Run one at a time from the primary, with the labelled counts, the label rate and
the width posterior reported at every value.

**The clustering check, which is the part B3 is actually about.** A barrier that
stopped a front early is exactly the case that leaves too little heat to clear C1
and C3, so the arrival rule censors preferentially against holds, and if that
censoring is correlated with width it biases the width slope directly. The check is
possible because **width is measured for every candidate segment from pre-fire
imagery regardless of whether it is ever labelled** (section 6.3.2), so the
excluded segments have widths.

Reported, per fire and pooled, whichever way each comes out:

1. the distribution of `W_cleared` among segments excluded at each of `NOBURN`,
   `NOTMAIN`, `NODETECT`, `TIMING` and `SIDE`, against the retained ones, with the
   mean difference and a cluster bootstrap by barrier line;
2. the exclusion rate by `W_cleared` tercile, by barrier type;
3. a logistic regression of exclusion on `log(W_cleared + 1)` with barrier type and
   fire complex, reported with its coefficient and interval.

**Both readings are written in advance.**

- **Exclusion rate rising with width.** The censoring runs against wide barriers.
  Wide barriers are then under-represented among labelled segments, which
  attenuates the width slope toward zero. This is the **conservative** direction
  for the hypothesis, it is reported as such, and the width result stands with the
  bias direction stated.
- **Exclusion rate falling with width.** The censoring runs against narrow
  barriers, which inflates the apparent width effect. This is the **dangerous**
  direction. In that branch the width result is reported with the bias direction
  named in the abstract and not in a limitations paragraph, and a bounding analysis
  is run in which every excluded segment is entered once as held and once as
  crossed, in the same shape as section 10.5, with the width posterior under both
  extremes reported beside the primary.
- **No detectable relationship.** Reported as no detectable relationship, with the
  interval, and with the sample size that produced it, so that a null here is not
  read as an absence of the problem.

### 12.10 One scene, two sides: illumination, not only fuel

**Leakage item B5, a MAJOR item A6 ended at `unresolved` and therefore a numbered
condition.** Section 5.4 handles the two sides having different **fuel**, three
ways, and handles it well. It did not handle the two sides having different
**illumination**, which is the B5 mechanism, and which is worst on exactly the
barrier class this design relies on for identification: a ridge crest puts its two
sides at different incidence angles, and a terrain illumination difference moves
NBR on both dates unequally, which is a difference the label reads as burn.

**The recorded quantity.** For each side of each segment, the mean cosine of the
local solar incidence angle over the analysis pixel set, computed from
`dem_korea` slope and aspect and the solar position at that scene's acquisition
time, on **both** the pre-fire and the post-fire scene. Then

    delta_illum_pre   = mean cos(inc) lee, pre   - mean cos(inc) windward, pre
    delta_illum_post  = mean cos(inc) lee, post  - mean cos(inc) windward, post
    delta_illum       = delta_illum_post - delta_illum_pre

`delta_illum` is the difference of differences, and it is the quantity that moves
a **difference** index such as dNBR, which is why it and not the single-date
values is the covariate. It is derived from terrain and solar geometry and from no
spectral band, so it passes the firewall of section 6.1, and it is in the covariate
table of section 6.2 with that noted.

**The three checks, reported whichever way they come out.**

1. **Label rate against `delta_illum` decile**, pooled and separately for ridges,
   which are the worst case. Ridges are reported separately because if the effect
   exists anywhere it is there, and pooling would dilute it.
2. **Label rate against the scene date and against the scene's cloud-mask
   fraction**, per fire. These are the two B5 detections A6 asks for by name. A
   label rate that tracks the scene date is a label rate measuring the scene rather
   than the fire.
3. **A pre-registered secondary specification with `delta_illum` as a covariate.**
   If the width slope moves materially between the primary and that specification,
   the primary is reported with the movement stated in the abstract, and both
   posteriors are in the result artifact at their own key paths.

**A topographic illumination correction is refused for the primary, and the
refusal is pre-registered.** A C-correction or a Minnaert correction would be the
textbook move, and both fit per-scene parameters by regressing band reflectance on
illumination **over the scene**, which means over the label pixels. The correction's
parameters would then be a function of the burn, and a covariate-side correction
fitted on the outcome's own pixels is the shape of leakage item A1. Carrying
`delta_illum` as a recorded quantity and as a covariate costs nothing and fits no
parameter on the scene. A corrected-reflectance run is available as a declared
secondary only if a correction can be fitted on pixels outside every fire's
perimeter buffer, and if it cannot, it is not run.

### 12.11 The arrival hour, its uncertainty, and the weather covariates

**Leakage item B9, a MAJOR item A6 ended at `unresolved` and therefore a numbered
condition.** Section 6.4 defines the arrival-time fit and retains its residual
standard error, which is the raw material. What v0.1b did was take the weather
covariates "at the arrival hour" as if that hour were known, with no propagation of
the fit's own uncertainty and no count of segments with an ambiguous hour. Section
5.1.1's arithmetic shows the fit's timing uncertainty is large, so this is not a
small correction.

**The attribution rule.** The arrival time at a segment is the fitted plane's value
at the **windward** band centroid, `t_hat`, with standard error `se_t` from the same
weighted least squares, converted to KST and then to local solar hour through
`research/shared/geo/solar.py` at the segment's own coordinates.

**The propagation.** No weather covariate is read at a point hour. For each
segment, 200 arrival times are drawn from `Normal(t_hat, se_t)`, the nearest
station's hourly observation is looked up for each draw, and:

- **wind speed** enters the model as the **mean over those draws**, with the
  **standard deviation across the draws carried as a per-segment measurement-error
  input**, in the same errors-in-variables machinery as width. Wind is the covariate
  most sensitive to the hour and it is the one that gets the full treatment;
- **relative humidity and temperature** enter as the mean over the draws, with
  their across-draw spread recorded and reported but not modelled as error. The
  reason is stated rather than assumed: both vary on a slower timescale than wind,
  so at a timing uncertainty of an hour or two the induced error is small relative
  to the station-distance error that is already unmodelled, and adding a second
  latent layer for each would buy precision the design does not have;
- the **night indicator** of section 12.4.7 is taken as the majority over the
  draws, and segments whose draws split more evenly than 0.80 to 0.20 carry a
  `night_ambig` flag and are excluded from the day-against-night contrast only.

**The count, which B9 asks for by name.** The number of segments whose `se_t`
exceeds **2 hours** is reported per fire. Those segments carry the `AMBIG_HOUR`
flag, a pre-registered secondary refits excluding them, and **gate H1** of section
11.3 drops the weather covariates from the primary specification altogether if more
than half the labelled segments carry the flag. Dropping them is the honest branch:
a weather covariate whose hour is unknown for most segments is a covariate that
measures the fit's noise.

---

## 13. The outputs, pre-registered before any fitting

Each of these is produced, or its non-production is explained by a named gate
from section 11.3. Every number in every one of them has a key path in section
22.2 and is rendered from the artifact of section 22.1, never typed into a caption.

1. **The breach curve against `W_cleared` and against `W_eff`, with uncertainty**,
   per barrier type, with the number of supporting segments shown in each width bin
   on the figure itself, and with the P1 gate applied.
2. **The approach-angle effect and the lee-side fuel effect**, as posterior
   contrasts with intervals, including the robustness check of section 6.5.
3. **The empirical ember jump-distance distribution**, with the truncation of
   section 7.3 stated on the figure, the fitted family, the family comparison, and
   the F4 gate applied.
4. **A per-segment barrier score**: the posterior mean breach probability with its
   credible interval, per segment, as a table and a layer in EPSG:5186.
5. **A per-segment access score**, drawn from the existing rescue routing layer:
   ingress corridor travel time from the nearest depot and corridor survival time,
   computed by importing `src/wildfireguardian/routing/rescue.py` **read only**.
   Nothing under `src/` is created or edited (decision D-001). Outputs are written
   only under `research/roads/`.
6. **The label accounting table**: candidate, eligible, ineligible by reason,
   held, crossed, indeterminate by reason, per fire and per barrier type, plus the
   effective independent-encounter count of section 10.6 and the `CROSSED`
   reachability breakdown of section 5.6.
7. **The covariate provenance audit table** from section 6.1, including the
   single "yes" row of section 6.2 and the whitelist that permits it.
8. **The bounding analysis** of section 10.5, the prior sensitivity analysis of
   section 7.5, and the selection bounding analysis of section 12.9 if its
   dangerous branch fires.
9. **The comparison table**: structured model, B0, B1, B2 and the gradient-boosted
   classifier, on the primary metric, per fold, with the held-out complex named,
   under both held-out random-effect rules of section 10.7, plus the SHAP summary,
   plus any specification that failed to converge under section 19.3.
10. **Check S0's output** (section 5.1.3): the distribution of the relative front
    irregularity `c` per fire and per barrier type, and the fraction of candidate
    segments passing the side test at each `z_side`. Produced before any label
    exists and reported whether or not a label is ever computed.
11. **The smoke decision record** (section 5.2.1): per fire, which option was
    taken, the triggering quantity, and the masked fraction.
12. **The sensitivity register** (sections 12.8 and 12.9): every parameter, every
    value, the labelled counts and the width posterior at each, plus the
    arm-reassignment count for every value of `d_out`.
13. **The second labelling pass** (section 5.8): the confusion matrices, the
    disagreement count, and the section 5.7 step number at which each disagreement
    arose.
14. **The fit log** (section 19.2), with its length reported as the number of fits
    run before the reported one.

Every number in these outputs is registered before it appears on any surface, per
scope rule 6 of `research/README.md`, and section 22 is the mechanism that makes
that possible rather than aspirational.

---

## 14. Prior art, and how this design differs

A7 owns the verified bibliography (`research/lit/`, task T1.6). A3 has not read
any of the items below in full, has verified none of them, and writes nothing into
`research/lit/`. Every line here is a statement of what the design assumes the
source says, flagged as unverified, and it must be checked before the signature.

| source | what the design takes from it | how this design differs | verification status |
|---|---|---|---|
| NIFoS press release 2025-04-25 and attachment 2-2 | the claim under test: that forest roads of 6 m or wider show the most effective firebreak function under Korea-like conditions | **the claim is relative, not absolute** (section 1.2), so the design tests a comparative proposition against labelled encounters from real Korean fires, with a pre-registered label rule and declared falsification conditions | A7 reached the public page: **no authors, no sample size, no breach rate given there**. Attachment 2-2 itself is still missing (human gate WJ-004) |
| Kim and Im 2024, FDS simulation of Yeongdeok 2022 roads, Korean Society of Forest Engineering | Korean prior art, and the mechanism hint that **widening a road plus removing fill-slope canopy fuel stops the fire, while as-built width alone does not** | that work simulates a case in computational fluid dynamics; this is an observational study over five fires with pre-registered labels and out-of-complex validation. Its finding is why two of this design's choices exist (see below) | A7 reports a one-page abstract with no DOI. Treated as a mechanism hint, not as a result to reproduce |
| Kwon, Zoh and Kang 2025, DOI 10.1007/s11629-025-9472-z | Korean prior art relating wider roads to fewer nearby fires | **different outcome entirely.** That is fire **occurrence** in coarse distance bands, not whether an arriving front crossed a barrier. This design conditions on the front having arrived (section 4) and its outcome is a lee-side burn at a 100 m segment. The two cannot confirm or contradict each other | verified by A7, DOI recorded |
| Thompson et al. 2021 (Forests) | fuel-break effectiveness framing, and the idea of evaluating breaks against observed fire encounters | **American. Source of a method and framing only. Its fire data is not used for fitting** (scope rule 1, and RC-010) | unverified by A3 |
| Zong et al. 2026 firebreak review (Fire Ecology) | the review's taxonomy of firebreak effectiveness evidence, for positioning | a review, not a Korean encounter dataset. This design contributes the encounter record that the review class of work summarises | unverified by A3 |
| Swedosh et al. 2021, effective width in Spark | the effective-width formulation of section 6.5 | **Australian. Source of a method, and its data is not used.** Applied to Korean encounters with coefficients fitted on Korean data only | A7 worked from the indexed summary. Section 6.5 is blocked on confirming the formula against the source PDF |

### 14.1 Kim and Im 2024 is why two design choices exist

A7's summary of that work deserves separating out, because it turns two choices in
this document from arbitrary into motivated, and A6 should see the connection
rather than have to find it.

Their simulation indicates that widening plus removing fill-slope canopy fuel
stops the fire, where as-built width alone does not. If that mechanism holds:

1. **The lee-side fuel term is load-bearing, not an afterthought.** It is entirely
   possible that lee-side fuel dominates width. The design already separates the
   two (section 6.2), and it can report that separation as a primary finding rather
   than a control.
2. **It is a direct argument for `W_cleared` over `W_surface` as the primary width
   covariate.** Fill-slope canopy is precisely the difference between the running
   surface and the full cleared gap. If removing fill-slope canopy is what changes
   the outcome, then the canopy gap is the physically relevant width and the running
   surface is not. Section 6.3.1 chose `W_cleared` before A3 saw this; the choice now
   has a mechanism behind it, and question Q1 in `OPEN_QUESTIONS.md` should be
   resolved with that in mind.

This is prior art shaping a design, which is what prior art is for. It is not
evidence for any result here, and the simulation's finding is not restated as a
fact anywhere in this direction.

**The line, stated once and plainly.** Thompson et al. and Swedosh et al. supply
equations, framings and definitions. No foreign fire, road or landslide record is
pooled into any model here (scope rule 1). Every observation fitted is Korean.

A3 makes no novelty claim. Whether anything here is new is A7's question, and the
prior-art sweep is not finished.

---

## 15. What must be true before fitting starts

### 15.1 From John, through the human gates

- **WJ-004, the NIFoS attachment 2-2.** This is the blocker that matters most for
  this direction, because the design has to test the claim as its author stated
  it. What is needed from the attachment:
  1. the exact wording and scope of the width claim, in Korean;
  2. **which width it means**: running surface only, or the full cleared gap
     including cut slope, fill slope and shoulder. Section 6.3 measures both, and
     which one is the NIFoS-comparable one depends entirely on this answer;
  3. what "most effective" is relative to, and under what conditions;
  4. whether the basis is simulation, observation or expert judgement, and on
     which fires;
  5. any stated wind, slope or fuel conditions attached to the claim;
  6. **whether the attachment carries the sample size and the breach rate that the
     public page does not.** A7 reached the reachable page and reports no authors,
     no sample size and no rate there. If attachment 2-2 has them, the design gains
     a direct comparison and section 14 is rewritten; if it does not, then the claim
     under test has no published evidential base, and that fact is itself a result
     worth reporting and must be stated neutrally rather than used as a point
     against it.
- **WJ-001, the six API keys.** All six are unset in this sandbox. Nothing can be
  fetched until they exist. Sentinel-2 and the active-fire archive are both behind
  them.

### 15.2 From A1

Registry entries reaching `verified` for `kfs_forest_roads`,
`korea_prefire_orthoimagery`, `base_map_linear_features`, `sentinel2_l2a_dnbr`,
`firms_active_fire_korea`, `dem_korea`, `kfs_forest_type_map` and `kma_asos_aws`.
Section 21.1 is the status table. `research/roads/DATA_REQUIREMENTS.md` is the
keyed list, and it is written against what A1 has confirmed obtainable rather than
what was hoped for.

**The width question is answered and the answer is no**: the forest road SHP has
no width attribute, so section 6.3 is built around image-derived measurement.
**The dating question is not answered and cannot be until WJ-017 clears**, because
the SHP never downloaded, so nobody has seen its field list. Section 3.4 is written
to work under both answers for that reason, and it is the part of this document
most likely to change when the file lands.

What is still needed from A1, in priority order:

1. **the forest road SHP itself**, behind WJ-017, and from it the full attribute
   schema: whether a road class field (간선임도, 지선임도, 작업임도) exists, which
   supplies the fallback prior of section 6.3.5, and whether any per-road
   construction or survey year exists, which decides between branch A and branch B
   of section 3.4. Also the layer's **internal edition date**, read from the file
   rather than from the portal, which is what branch B turns on;
2. **a source of pre-fire high-resolution orthoimagery with per-tile vintage**,
   behind WJ-009. Per section 21.3 this decides whether the direction has a
   question at all, and since section 3.4 it also carries the per-segment existence
   check, so it is load-bearing twice;
3. **the OpenStreetMap hydrography completeness audit inputs** for section 3.1, and
   the OpenStreetMap `highway=track` extract for the roads mapping audit of leakage
   item B10 in section 20.3;
4. **confirmation of which Sentinel-2 L2A aerosol raster is present per scene**
   (20 m or 60 m only), which section 5.2.1's `aot_60m` flag depends on.

Two A1 findings are already folded into this version and need nothing further:
`kfs_fire_stats_csv` at 2022 to 2025 and `kfs_fire_state_history_csv` at 2022-01-01
to 2025-11-10, neither reaching Goseong 2019, which is why section 5.2 carries the
detection-based containment fallback; and the confirmation that the state-history
file's sunrise and sunset columns are a single national value per date, which is
why every solar quantity here comes from `research/shared/geo/solar.py`.

### 15.3 From A2

The complex rule implementation, the local solar time helper and the
dirty-timestamp quality control (task T1.5). This direction consumes them and does
not reimplement them.

### 15.4 From A6, and from the orchestrator

- The shared evaluation harness and the cross-validation split contract (task
  T2.1). If A6's harness names a different program-wide primary metric from section
  10.2, A6's name wins and this document is version-bumped to match. A6 has already
  ruled on Q6 that it will not name a different one.
- **RC-011, the vocabulary rule, is a request to the orchestrator and not
  something this document can land.** A3 does not own `research/FORBIDDEN_CLAIMS.md`
  or `research/shared/check_research_claims.py`. The rule is drafted in full in
  section 12.4.6 with its assertive spellings and its permitted term, and the local
  detector `research/roads/check_vocabulary.py` holds the line inside the roads tree
  until it lands. This is a **blocking condition for the named secondary claim**
  that the estimand is operational barrier performance, and not for the primary
  result.
- **The second labelling pass of section 5.8 needs an agent that is not A3** to
  write the independent implementation. A6 is not the right author, because this
  pass is part of the design A6 signs. The request text is committed with the
  script.

### 15.5 From A7

Verification of the five prior-art items in section 14, and in particular the
Swedosh et al. effective-width formulation, on which section 6.5 is explicitly
blocked. Also a Korean dNBR calibration and a Korean fuel-load table if either
exists.

---

## 16. Change control

Once A6 signs this document, it is frozen. Any change is a new version in a new
file with a dated entry in the table below, and every output names the version it
was produced under. The superseded file is kept unedited. A change made after a
label has been computed must say so in its entry, and the reason must not be that
the result was disappointing.

| version | file | date | what changed | why |
|---|---|---|---|---|
| v0.2 | `research/roads/PREREG_roads_2026-09-16_v0.2.md` | 2026-09-16 | the `SIDE` rule replaced with a gradient-projection test and its precision derived (5.1); the smoke mask written in full, closing Q5 (5.2.1); dNBR made the primary index so `tau_burn` sits on the scale it came from, with an RdNBR divisor floor and its own threshold (5.4); the label rule restated as an ordered decision procedure with an exhaustive exit set (5.7); the attribution test rewritten with a geometric first step and a branch for a lee patch with no detection (5.6); the 0.60 and 0.70 usable-fraction conflict resolved into one 7-pixel minimum (4.0); the non-burnable clause given a fraction (4.5); `DISCORD` removed and `DETACH`, `FLANK_AMBIG`, `NOBURN`, `NOTMAIN`, `NODETECT`, `RULEVAL` added; overlapping barrier bands defined (3.3); barrier dating made executable under both branches of the unanswered SHP question (3.4); ridges exempted from the errors-in-variables layer (6.3.4); the second labelling pass built (5.8); the buffer and arrival-rule sensitivity registers written with the `d_out` arm coupling and the exclusion-clustering check (12.8, 12.9); `kappa_v` defined on `log(W_eff + 1)` and M1 moved to an interval (11.5.1, 11.3); the exclusion-power arm and gate M2 added (11.5.2b); the smallest effect of interest restated as 0.05 in `W_cleared` at the median approach angle with F3 on the same contrast (11.5.3, 1.5); P6, P10, P11, P12, P13 and P16 written (18 to 22); the `prereg:` block and the versioned filename added; F4 named by symbol (1.5, 7.3); the vocabulary detector committed and RC-011 drafted (12.4.6); the day-against-night contrast pre-registered (12.4.7); per-side illumination handled (12.10); the held-out random-effect rule named (10.7); the arrival hour propagated with its uncertainty (12.11). Still before any data was touched | A6 refused v0.1b with reasons R1 to R7 in `research/eval/signoffs/roads_v0.1b.md` |
| v0.1b | `research/roads/PREREGISTRATION.md` | 2026-09-16 | added section 11.5 (the reading rule for a flat breach curve, five instruments, three running before labelling), section 7.7 (what the design cannot identify), rewrote section 12.4 (suppression confounding) with an explicit reading rule for the width coefficient, raised the repeat-measurement subsample to thirty pairs, and rewrote sections 1.2, 6.5 and 14 against A7's completed prior-art sweep. Still before any data was touched | A6 named the null-reading rule and the unidentified parameter as conditions of sign-off, and named suppression confounding as its strongest objection. A7 corrected the NIFoS claim to a relative claim, supplied Kim and Im 2024's mechanism hint, added Kwon, Zoh and Kang 2025, and flagged the Swedosh formula as needing PDF confirmation |
| v0.1a | `research/roads/PREREGISTRATION.md` | 2026-09-16 | sections 3.1, 5.2, 6.2, 6.3, 6.5, 6.7, 1.5, 11.2, 11.3, 12.5 and 15.2 revised, still before any data was touched | A1 confirmed the forest road SHP has no width attribute, NGII base map and NGII 5 m DEM are blocked (HTTP 400, now a human gate), OpenStreetMap and Copernicus GLO-30 are the working routes, and `kfs_fire_stats_csv` covers 2022 to 2025 only. Image-derived width became the primary path, gate M1 and the asymmetric reading of F1 were added |
| v0.1 | `research/roads/PREREGISTRATION.md` | 2026-09-16 | first draft, written before any data was touched | task T2.2 |

**Two amendments are already scheduled and are named here so they are not
surprises.** Both are mechanical version bumps whose only content is a value that
does not exist yet:

- **v0.3a**, the segment-level split fingerprint of section 18.2, written
  immediately after the layout script runs and before any label exists;
- **v0.3b**, the second-pass disagreement rate of section 5.8, written after the
  thirty rule-validation units are labelled, carrying the "what was seen before
  this amendment" section that `SIGNOFF.md` section 4 requires for exactly that
  look.

---

## 17. Statement for the signing agent

### 17.1 What has and has not happened

Written by A3 on 2026-09-16. No model was fitted. No dataset was downloaded by A3.
No label was computed. No number in this document is a measurement. Every threshold
here is a decision rule declared before the data exists, and the falsification
conditions in section 1.5, the feasibility gates in section 11.3 and the baseline
rule in section 10.4 are the places where this design is allowed to tell its author
that it did not work.

Section 4 of `SIGNOFF.md` does not apply to this version. Section 21.4 lists
everything A3 has read since v0.1b, and none of it is an outcome or a covariate
value.

### 17.2 What A3 thinks the most likely outcome of this direction is

Said in the document rather than reached by chaining five gates, because A6 asked
for it to be said plainly. **The modal outcome of this design is not F1 firing or
not firing. It is a gate failing and the round reporting a labelled encounter
table with no breach curve on it.** The chain is: WJ-017 and WJ-009 both have to
clear before there is a road layer or a width covariate at all; gate E1 needs two
complexes whose roads can be dated; gate S1 needs the side rule to resolve at a
useful rate; gate R0 needs the design to be able to see a 0.05 effect at better
than one time in five; gate W1 needs 25 road segments on each side of 6 m of
`W_cleared`; and gate M1 now reads the lower end of an interval, which by section
11.3's arithmetic wants a point `kappa_v` near 0.77.

That is not a criticism of the design and it is not an argument for loosening any
of those gates. It is what section 11.4 already says, and a design that states its
own most likely outcome in advance is behaving correctly. It is also what makes
instrument 2 and gate R0 the most valuable things in this document: **they can tell
the program that the answer is not resolvable before anybody labels a segment**,
which is the cheapest true thing this direction can produce, and a pre-registered
demonstration that a Korean five-fire record of this size cannot resolve the
question is a result the field does not have.

### 17.3 Where A3 disagrees with the refusal

Per `SIGNOFF.md` section 5 there is no negotiation between agents, and A3 is not
opening one. This version complies with every ruling in the refusal, including the
two below. These are recorded for John, and if any of them is worth a formal
disagreement that is a one-page rebuttal at
`research/reports/A3/<date>_rebuttal_roads.md` and not a change in this file.

**1. One of A6's own suggested remedies for the `SIDE` rule is closed, and closing
it should be on the record.** A6's R1 lists "the local fire-perimeter geometry" and
"the order in which the two sides burned" among the information that genuinely
distinguishes windward from lee. Both are derived from the burned mask, which is
derived from the dNBR scene pair that produces the label. Assigning a side from
them would let the label define its own geometry, and the bias would run toward
`HELD` on exactly the segments the hypothesis is about. A3 has refused both routes
and extended the section 6.1 provenance firewall to cover the side rule (5.1.2).
A6's arithmetic in its section 3.1 is unaffected and A3 accepts it in full; this is
about the remedy list, not the finding.

**2. A6's scenario S4 overstates its own premise, and the size of the risk to the
positive class is smaller than the refusal says.** A6 concludes that because the
lee analysis band is 40 m wide against a 375 m VIIRS pixel, "the attribution test
is inoperative, and therefore `CROSSED` is unreachable, for the majority of
segments". The premise is correct. The inference is not, because the attribution
test's input is the lee **patch**, not the lee **band**: a fire that crossed and
kept running produces a patch that extends well beyond 50 m and carries detections.
The genuinely detection-free case is a crossing that stalled within 50 m, which is
a real and interesting minority rather than the majority. A3 has rewritten the test
anyway, because the branch has to exist either way, and has made the geometric step
primary so that `CROSSED` is reachable with no detection at all whenever the nearest
route around the barrier is more than 500 m away (5.6). The reachability is now a
reported count rather than an argument, so this disagreement will be settled by the
accounting table.

**3. A6's ruling on M1 is adopted and its cost is larger than the refusal states.**
Gating `kappa_v` on an interval lower bound is right and A3 does not contest it.
The arithmetic in section 11.3 shows it raises the effective point requirement from
0.70 to about 0.77, which combined with A6's own expectation that M1 is the modal
failure means this design will usually not publish a curve. A3 records the
consequence rather than the objection, and has made `kappa_v` and its interval
reported numbers rather than a pass or a fail, which is the same treatment A6
required for recoverability.

### 17.4 What this version does not fix

Three things, named so that a signature is not read as covering them.

- **The two datasets that decide whether the direction has a question are still
  behind human gates**, WJ-017 and WJ-009, and section 21.3 states what WJ-009
  decides. Under P12 that caps this at `signed with conditions`.
- **The second-pass disagreement rate of section 5.8 does not exist yet.** The
  procedure is frozen; the number arrives at v0.3b.
- **The segment-level split fingerprint does not exist yet**, because the layout
  has not run. The complex-level one is in section 18.2 and in the `prereg:` block;
  the segment-level one arrives at v0.3a.

---

## 18. P6, the held-out sets, made checkable

v0.1b named the folds in prose and contained no call, no keyword arguments and no
fingerprint, so the item failed although its substance was right. A6 recorded that
the substance is right and that the folds match `PRIMARY_SPLITS["roads"]` and
`FIRE_COMPLEXES` exactly. What was missing is the mechanism that makes the naming
checkable afterwards, which is the whole reason the item exists.

### 18.1 The call

```python
import sys
sys.path.insert(0, "research/eval")
from splits import leave_one_complex_out, splits_fingerprint

fire_ids = [
    "goseong_2019",
    "uljin_samcheok_2022",
    "gangneung_2023",
    "uiseong_andong_2025",
    "sancheong_2025",
]
splits = leave_one_complex_out(fire_ids)          # kwargs: {} (no extra_complexes)
fingerprint = splits_fingerprint(splits)
```

There are no keyword arguments. `extra_complexes` is deliberately not passed,
because every fire id above resolves in `FIRE_COMPLEXES` and passing an override
would be a way to redefine a complex at fit time. 영덕 2025, if it is ever added
under section 2.2, is appended to `fire_ids` and joins the `yeongnam_2025` complex
automatically; it does not create a sixth fold.

### 18.2 The two fingerprints, and the trap between them

**Complex-level fingerprint**, over the five ids in the section 2.1 order above,
recomputed by A3 and matching the value A6 recorded:

    844e82d06b534901590bc660f62cb49bb2b57279be055e112c93d801098d2cd5

The five folds it covers, in the order `leave_one_complex_out` returns them
(sorted by complex id), are `gangneung_2023`, `goseong_2019`, `sancheong_2025`,
`uljin_samcheok_2022`, `yeongnam_2025`.

**The trap, recorded because it will otherwise break the fingerprint silently.**
A `Split` holds **positional indices**, so the fingerprint is a function of row
order. A6 supplied the demonstration and it is kept here so nobody has to rediscover
it:

| what is hashed | fingerprint |
|---|---|
| the five complexes, section 2.1 order | `844e82d0...` |
| the same five, reversed | `7233bb94...` |
| three segments per fire, grouped by fire | `d16ffd5d...` |
| the same rows, interleaved | `9f50f8a2...` |

**Segment-level fingerprint, which is the one a result will carry.** The unit of
analysis in this direction is the segment, not the fire, so the split that a number
is produced under is a segment-level split, and its fingerprint is pinned only when
the segment layout is pinned. The row order is fixed here so that it cannot be
chosen later:

> **Row order.** Segments appear in the order the committed layout script emits
> them: barrier lines sorted by the stable hash of their geometry (section 3.2 item
> 4), and within each line by chainage ascending from the line's start vertex, in
> EPSG:5186. Composite barriers (section 3.3) are ordered by the hash of the
> composite's merged geometry, and their member lines do not appear separately.

The segment-level fingerprint is computed by running `leave_one_complex_out` over
the per-segment fire id vector in that order, immediately after the layout is
committed and **before any label is computed**, and it is written into the
`prereg:` block at the top of this file in a v0.3 amendment whose only change is
that value. That is a version bump with a one-line change table entry, and it is
the honest way to pin a value that does not exist until a script has run.

### 18.3 The statement P6 asks for

No held-out outcome has been looked at, by anyone, for any of the five complexes.
No label exists for any segment of any fire. A3 has fetched no dataset and
computed no label. The quantities A3 has read are listed in section 21.4 and none
of them is an outcome.

---

## 19. P10, the stopping rule and multiplicity

v0.1b had no text for this item. It is written here so that the count of fits is a
number somebody can check rather than a thing nobody volunteers, which is what
leakage item A7 is about.

### 19.1 How many fits, and the enumeration

Every fit on real labels comes from the table below. **The pre-registered ceiling
is 48 fits on real labels.** A fit that is not in this table is a version bump, is
recorded as such, and is reported as an unplanned fit in the abstract-level
framing.

| specification group | fits |
|---|---|
| primary (or the G2 reduced specification, which is mutually exclusive with it) | 1 |
| complete-pooling and fixed-effect parallels (7.5) | 2 |
| `sigma_fire` prior sensitivity, the two non-primary values (7.5) | 2 |
| bounding analysis, all-held and all-crossed (10.5) | 2 |
| fuel-concordant subset (5.4) | 1 |
| roads and rivers only, no ridges (6.5) | 1 |
| raw width plus `theta` parameterisation (6.5) | 1 |
| `delta_illum` covariate specification (12.10) | 1 |
| width-by-night interaction (12.4.7) | 1 |
| patch-anchor subset (5.6) | 1 |
| composites dropped (3.3) | 1 |
| imagery vintage within 3 years (6.3.5) | 1 |
| three-or-more-epoch subset (6.4) | 1 |
| S-A tier only (5.1.2) | 1 |
| `AMBIG_HOUR` excluded (12.11) | 1 |
| ember arm family comparison, lognormal and generalised Pareto (7.3) | 2 |
| `DETACH` entering the ember arm (7.3) | 1 |
| baselines B0, B1, B2 (section 9) | 3 |
| gradient-boosted comparison model (section 8) | 1 |
| buffer grid, `d_in` and `d_out`, one at a time from the primary (12.8) | 4 |
| label-threshold grids, `tau_burn`, the two `f_lee` cuts (12.8) | 7 |
| smoke grid, one at a time (12.8) | 5 |
| `z_side` and `d_bypass_min` grids (12.8) | 4 |
| arrival-rule grid (12.9) | 7 |
| segment length 50 m and 200 m (3.2) | 2 |
| **total** | **48** |

Each fit is under leave-one-complex-out, so each is five model runs; the table
counts specifications, not sampler invocations, and section 22.4 gives the
wall-clock arithmetic on the sampler count.

Simulation fits (instruments 2 and 2b, 500 draws each, and the prior predictive
checks) are not in this table and are not counted against the ceiling, because no
real label enters them. They carry their own committed seeds.

### 19.2 The fit log, which is the mechanism

A committed harness runs every fit and appends one record to
`research/roads/results/fit_log.json` before the fit starts and updates it when the
fit ends. Each record carries: the specification id from the table above, the
seed, the start and end times, the R-hat maximum, the minimum bulk effective
sample size, the divergence count, the convergence verdict, and whether the fit was
an attempt-1 or an attempt-2 under section 19.3. **Fits that failed to converge are
in the log**, which is the only reason the log is worth keeping. The length of the
log is reported as "the number of fits run before the reported one", per P10 and
leakage item A7.

### 19.3 What happens when a fit does not converge

Section 7.6's gates are R-hat below 1.01, bulk effective sample size above 400, and
zero divergences. When a fit fails them:

1. it is re-run **once**, with `target_accept` raised from 0.9 to 0.95 and a new
   seed, with the non-centred parameterisation of section 7.4 already in place;
2. if it fails again, **the specification is reported as not fittable on this
   record** and the failure is a result. It is in the log twice, and its failure
   appears in the comparison table of section 13;
3. **no specification is modified to make it converge.** Dropping a covariate,
   tightening a prior, removing a random-effect level or trimming rows to reach
   convergence are all forbidden here, because each of them is a model chosen by
   the outcome, which is leakage item A8.

At most two attempts per specification. The attempt count is in the log.

### 19.4 The comparison family, and why no correction is applied

The confirmatory family is exactly three items: **F1**, **F2** and **F3**. No
correction is applied, and the reason is stated rather than left as an omission.

These three are not a search over a family of hypotheses. They are three fixed
readings of one pre-registered coefficient and one pre-registered baseline
comparison, each with a threshold fixed before the data exists, each reported
whichever way it comes out, and none of them able to be swapped for another after
the fact. A multiplicity correction protects against a search, and there is no
search: the 45 other fits in section 19.1 are sensitivity and robustness analyses
which are reported in full and **none of which can become the reported result**,
because section 10.4's decision rule and section 11.5.6's conjunction both name the
primary specification by construction.

What does the protecting here is the fixed table plus the reported count, not an
alpha adjustment. This paragraph exists so that the absence of a correction is read
as a declared decision and not as an oversight.

---

## 20. P11, the leakage self-audit

### 20.1 The order defect, declared rather than concealed

P11 says the author's verdicts must exist first, because the difference between
the author's list and A6's independent list is itself the information, and A6
restated that condition for this round: the checklist must be written "before
reading this record so that the two lists can differ".

**That is not what happened and the document says so.** v0.1b carried no
checklist, A6 ran its own pass and published it in the refusal, and A3 has read it.
The verdicts below are therefore written **after** reading A6's, and the
comparison the protocol wants is not available for this round. Pretending otherwise
by writing verdicts that happen to agree would be worse than the gap, because it
would destroy the one thing the item exists to produce.

Three things are done about it instead:

1. the defect is stated here, where a reader looking for the comparison will find
   it, and it is carried into the sign-off record as a known limitation of this
   round rather than a cleared item;
2. **where A3's verdict differs from A6's, the difference is marked** in the table
   below, so that the residual information is at least visible;
3. for the landslide and suppression directions the order is fixed the other way
   round in their own pre-registrations: the author's checklist is written and
   committed before A6's pass begins. That is a recommendation to the orchestrator
   and not something this document can impose.

### 20.2 Part A, cross-cutting

| id | severity | A3's verdict | one line |
|---|---|---|---|
| A1 preprocessing inside the fold | CRITICAL | **clean** | `z(.)` is standardised on training folds only (7.2), the gradient-boosted grid is searched by nested cross-validation inside training folds (section 8), and section 10.1 names the one declared exception, the width error model, with the reason it is not fold-internal |
| A2 hyper-parameters and priors selected on the held-out set | CRITICAL | **clean** | priors are fixed in 7.4 and never moved; the comparison model's grid is committed in section 8; the number of looks at the held-out score is bounded by section 19.1 |
| A3 feature selection before the split | CRITICAL | **clean** | the covariate set of 6.2 is fixed here and no screening step exists. SHAP is description only and cannot add a term (section 8) |
| A4 feature support crossing the fold boundary | CRITICAL | **mitigated** | the supports that cross a segment are the 1 km and 3 km arrival-time fits (6.4) and the flow-accumulation catchment for the river-width check (11.5.5). Neither crosses a **complex** boundary, because complexes are separated by hundreds of kilometres. The lee-patch grouping of 5.6 is within one fire by construction |
| A5 duplicates and near-duplicates | MAJOR | **mitigated** | exact duplicate segments cannot exist under the committed layout. Near-duplicates are handled three ways now rather than one: the barrier-line intercept, the new lee-patch intercept (5.6) and the composite-barrier rule (3.3), which is the case A6's scenario S9 found the random effect could not absorb. Counts reported |
| A6 the analyst's memory | MAJOR | **present, stated** | everyone in this program knows roughly what happened at Uljin 2022 and Uiseong 2025, and no split cures that. The mitigations are the ones the checklist names: the design is fixed before the data, the amendment record is kept, and the limitation is stated in the paper rather than treated as solved |
| A7 undocumented fits | MAJOR | **mitigated** | section 19.2, the fit log, with failed fits in it and its length reported |
| A8 outcome-driven cleaning or stopping | MAJOR | **clean** | every exclusion rule is a function of covariates, geometry or scene quality and is declared in sections 4, 5 and 5.7. Section 19.3 forbids modifying a specification to make it converge |
| A9 geocoder drift | MINOR | **not applicable** | no address is geocoded in this direction. Every unit is a geometry in EPSG:5186 |
| A10 outcome-dependent missingness | MAJOR | **present, bounded** | this is the same mechanism as B3 and it is the direction's real one: a barrier that stopped a front leaves less heat and is more likely to fail C1 and C3. Section 12.9 is the check and the bounding analysis, and section 10.5 is the second |
| A11 resampling unit | MAJOR | **mitigated** | section 10.2 states the resampling unit, refuses a segment-level bootstrap outright, and reports the five per-fold values as the honest presentation with five clusters |
| A12 foreign quantity entering through a prior | MINOR | **mitigated** | `mu_jump` at Normal(log 200 m, 1) is **A3's own order-of-magnitude judgement and is not taken from a named foreign coefficient**, which A6 asked to have stated either way. The flat-prior sensitivity run is pre-registered anyway (7.4), because the distinction between a judgement and a half-remembered import is not one a reader can check |

### 20.3 Part B, roads

Marked **[differs]** where A3's verdict is not A6's.

| id | severity | A3's verdict | one line |
|---|---|---|---|
| B1 severity covariate is partly its own label | CRITICAL | **mitigated** | section 6.1 is a hard constraint with a committed audit script, extending to pre-fire indices. v0.2 extends the same firewall to the **side rule** (5.1.2) and to the **smoke reference region** (5.2.1), which v0.1b did not do and which is where the firewall was actually leaking |
| B2 suppression confounded with width | CRITICAL | **present, with an accepted scope cut** | section 12.4, with the scope cut A6 accepted, plus the vocabulary detector of 12.4.6 and the day-against-night contrast of 12.4.7 that A6's conditions required |
| B3 selection on the front having reached the barrier | CRITICAL | **mitigated** | section 12.9: the four-number grid and the clustering check, with both readings written in advance and the bounding analysis attached to the dangerous one |
| B4 the buffer distance is a researcher degree of freedom | CRITICAL | **mitigated** | section 12.8: the full register, with the `d_out` coupling to the ember arm and the `d_in` coupling to the width measurement both stated |
| B5 one scene, two sides | MAJOR | **mitigated** | section 12.10: `delta_illum` as a difference of differences, the three checks, and the pre-registered refusal of a scene-fitted illumination correction |
| B6 adjacent segments are near-duplicates | CRITICAL in Part B | **mitigated** | as A5, plus leave-one-complex-out primary and no random split anywhere |
| B7 the fire random effect and the held-out fire | MAJOR | **mitigated** | section 10.7: the hyperprior draw is primary, the zero substitution is reported alongside and labelled optimistic, and the difference between them is itself reported |
| B8 the two-term product is not identified by a binary label | MAJOR | **mitigated** | section 7.7.1, unchanged from v0.1b except that F4 now names `lambda` first |
| B9 detection timing cannot attribute an overnight crossing | MAJOR | **mitigated** | section 12.11: the attribution rule, the 200-draw propagation, wind carried as a second errors-in-variables input, the `AMBIG_HOUR` count and gate H1 |
| B10 the barrier map conditions the sample | MINOR | **partly mitigated** **[differs]** | A6 recorded that nothing equivalent to the hydrography audit exists for roads. That is true of v0.1b and is fixed here: the KFS forest-road length inside each fire's perimeter buffer is audited against the OpenStreetMap `highway=track` length over the same area, per fire and per complex, and the ratio is reported. It is a weak audit, because OpenStreetMap forest-track coverage in Korea is itself uneven, and it is reported as weak. It is better than nothing, which is what v0.1b had |
| B11 the claim under test must not enter as a cut point | MAJOR | **clean** | width enters as `log(W_eff + 1)`, no 6 m bin exists in the design matrix, F3 is a posterior contrast read off the fitted curve, and W1's 6 m split counts support rather than binning a covariate (11.3) |
| B12 measured width, and attenuation biases the test toward the null | CRITICAL | **mitigated, conditionally** | sections 6.3, 6.3.3, 6.3.4, 11.2, 11.3 and 11.5 together, now with `kappa_v` on the model's scale, M1 on an interval, and the exclusion-power arm. The condition is unchanged and it is WJ-009: without pre-fire orthoimagery there is no width covariate, no error variance, no `kappa_v`, no gate M1 and no recoverability simulation |

### 20.4 Where A3 reads an item differently from A6

Only one verdict differs, B10, and it differs by A3 supplying a mitigation rather
than by A3 disagreeing with A6's reading. Two further points where A3 disagrees
with A6's **reasoning** rather than with a verdict are in section 17.3, because
they are not checklist items.

---

## 21. P12, data provenance

Status and sha256 as recorded in `research/data/REGISTRY.yaml` on 2026-09-16. A3
has downloaded nothing; every status here is A1's, and a status of `pending` means
the fit does not start on that dataset, per `SIGNOFF.md` section 3.

### 21.1 The table

| registry id | role in this direction | status | sha256 on disk | gate |
|---|---|---|---|---|
| `kfs_forest_roads` | the road barrier layer, and the only source of road geometry | **pending** | none, the file never downloaded | **WJ-017**, the highest-priority item for this direction. See section 3.4 |
| `korea_prefire_orthoimagery` | **the width covariate**, and the existence check of section 3.4 item 4 | **pending** | none | **WJ-009**. See 21.3 |
| `sentinel2_l2a_dnbr` | the label, through dNBR; the smoke mask, through AOT | **pending** | none | WJ-001 |
| `firms_active_fire_korea` | arrival time, side assignment, spread rate, intensity, smoke reference region | **pending** | none | WJ-001 |
| `dem_korea` | signed slope, ridges, `delta_illum`, the river-width check | **pending** | none | Copernicus GLO-30 registration; see 6.7 |
| `kfs_forest_type_map` | lee-side fuel class, the discordance flag, the fuel-load table for Byram intensity | **pending** | none | WJ-018, and the KOGL question WJ-012 |
| `base_map_linear_features` | rivers, and public roads crossing forest | **pending** | none | OpenStreetMap Geofabrik is the planned route; NGII is WJ-011 |
| `kma_asos_aws` | wind, humidity and temperature at arrival | **pending** | none | WJ-001 |
| `kfs_fire_state_history_csv` | containment time for scene selection, 2022 onward | **verified** | `2e94ab963feeb9ad998761537a397e4d5912ac7f90e147487ef43aafc1512c00` | none. Its sunrise and sunset columns are never used, section 5.2 |
| `kfs_fire_stats_csv` | containment time cross-check, 2022 to 2025 | **verified** | `ae3e8426702168cb288761735dabe5b8a45f429ba7bc13e9f0318e838a92c153` | none |

**Two of the ten are verified and neither of them carries a covariate or a label.**
That is the honest summary of this direction's data position, and under P12 it puts
any signature at `signed with conditions` at best, with the condition that the fit
does not start until each dataset reaches `verified`.

### 21.2 The known defects A3 designs against

- `kfs_fire_state_history_csv`: 41 negative durations, independently counted and
  agreeing with the program brief; 일출시간 and 일몰시간 are a single national
  value per date, confirmed across all 607 dates; Uiseong 2025 appears as two
  same-day records with different areas. None of the three touches this direction's
  label, and the third is handled by the complex rule of section 2.2.
- `kfs_fire_stats_csv`: 12 negative durations, 2 impossible end years, CP949
  encoding. Used only as a containment cross-check.
- `firms_active_fire_korea`: 375 m fire radiative power saturates at intense
  fronts, which is why section 6.6 does not use it at all.

### 21.3 The orthoimagery is a gap, not a pending entry, and A6 is right about that

A6's item P12 verdict says the orthoimagery "has no registry entry at all". It has
one now, `korea_prefire_orthoimagery`, added by A1 in round 2, and the entry
records that **both** candidate routes are account-gated: NGII 국토정보플랫폼 needs
login, membership and a large-file-transfer client, and its map endpoint returns
HTTP 400 to a non-browser fetch; VWorld returned a genuine HTTP 502 from its own
origin across repeated attempts and, per an independent check, needs signup, an API
key request, email verification and activation before any key-gated endpoint can be
called. Per-tile vintage, which is the property this direction actually needs, is
unconfirmed for both.

So the substance of A6's finding stands even though the registry line now exists,
and it is recorded here in the strongest form rather than softened by the entry:

> **WJ-009 decides whether this direction has a question.** Without pre-fire
> orthoimagery there is no width covariate, no hand-measured subsample, no error
> variance, no `kappa_v`, no gate M1, no recoverability simulation and, since
> section 3.4, no per-segment existence check either. The direction would then have
> a label rule, an encounter table and no axis to regress it against.

### 21.4 What A3 has read, so that section 4 of the protocol has nothing to find

A3 has looked at no outcome and no covariate value for any segment. Between v0.1b
and this version A3 read, from `research/data/REGISTRY.yaml` and A1's round-2
report: the access status and licence position of each dataset above; the temporal
coverage of the two KFS CSV files; the row counts 2030 and 2020; the defect counts
41 and 12; the confirmation that the sunrise and sunset columns carry one national
value per date across 607 dates; and the two blocked-download findings for the
forest road SHP and the orthoimagery. Every one of these is a dataset-level
acquisition fact. None is a label, a covariate value, a crosstab, a fitted
coefficient or a convergence diagnostic, and none of them is from a held-out
complex in any sense, because no complex has been split yet.

---

## 22. P16, the shape of the result artifact, and P13, compute

**A6 calls this the cheapest of the six failures to fix and the most expensive to
fix late, and that is right.** `scripts/build_numbers.py` registers a number only
when `source_file` is a committed JSON artifact and `json_path` is a dotted path
into it, resolved by the registrar's `dig()` helper, so a number that lives in a
figure, a table or a sentence cannot be registered at all. Asking for the key paths
after a fit means rewriting the output layer.

### 22.1 The artifact

    research/roads/results/roads_prereg_v0_2_results.json

One committed JSON file, written by the committed pipeline, with addressable keys.
Every quantity that might later be quoted has a key path in it before the fit
exists. Figures and tables are rendered **from** this file and never carry a number
the file does not hold.

### 22.2 The key paths

Not exhaustive of the artifact, exhaustive of what may be quoted. Anything not on
this list may not be quoted anywhere, and adding a key path after the fit is a
version bump that says so.

**The primary result and the baselines**

| key path | what |
|---|---|
| `held_out.primary_metric.value` | mean out-of-complex log predictive score per labelled segment, under the hyperprior rule of 10.7 |
| `held_out.primary_metric.per_fold[].complex` / `.value` | the five per-fold values with the held-out complex named |
| `held_out.primary_metric.within_fold_bootstrap[].low` / `.high` | the barrier-line cluster bootstrap, per fold, which is a lower bound |
| `held_out.primary_metric.zero_re_variant.value` | the zero-substitution variant of 10.7, labelled optimistic |
| `held_out.primary_metric.re_rule_difference` | the difference between the two rules |
| `baselines.B0.primary_metric.value`, `baselines.B1...`, `baselines.B2...` | the three baselines, same shape |
| `baselines.B1.primary_metric.per_fold[]` | per fold, for the 4-of-5 rule of 10.4 |
| `comparison_model.primary_metric.value` | the gradient-boosted classifier |
| `decision.F2.folds_won`, `decision.F2.mean_difference_nats`, `decision.F2.fires` | the section 10.4 decision, as three addressable numbers |

**The width posterior, which is the coefficient of interest**

| key path | what |
|---|---|
| `width.naive.posterior_mean`, `.ci90_low`, `.ci90_high` | the naive fit |
| `width.eiv.posterior_mean`, `.ci90_low`, `.ci90_high` | the errors-in-variables fit, which is the one F1 reads |
| `width.eiv.p_beta_lt_zero` | the F1 quantity |
| `width.contrast_3m_6m_cleared.mean`, `.ci90_low`, `.ci90_high` | the probability contrast of F3 and of the smallest effect of interest, in `W_cleared` at the sample median approach angle |
| `width.contrast_3m_6m_cleared.median_theta_deg` | the sample median approach angle it was evaluated at |
| `width.contrast_equivalent_weff_low_m`, `.._high_m` | the `W_eff` contrast reported beside it |
| `width.by_barrier_type.road...`, `.river...`, `.ridge...` | the per-type slopes, for 12.4.3 |
| `width.by_daynight.day...`, `.night...`, `.interaction...` | the 12.4.7 contrast |
| `width.curve[].w_cleared_m`, `.p_mean`, `.p_ci90_low`, `.p_ci90_high`, `.n_support` | the breach curve, with the supporting count per bin on the figure |

**The measurement instruments**

| key path | what |
|---|---|
| `measurement.sigma_u_m.mean`, `.ci90_low`, `.ci90_high` | the error standard deviation on `W_cleared` |
| `measurement.bias_b_m.mean`, `.ci90_low`, `.ci90_high` | the systematic bias |
| `measurement.kappa_v.mean`, `.ci90_low`, `.ci90_high` | the attenuation on the model's scale. **M1 reads `.ci90_low`** |
| `measurement.kappa_v_per_segment.deciles[]` | the per-segment distribution |
| `measurement.kappa_raw.mean`, `.ci90_low`, `.ci90_high` | the raw-scale continuity diagnostic, which gates nothing |
| `measurement.n_hand_measured`, `.n_repeat_pairs` | the two counts gate M1 also reads |
| `recoverability.detection_power.value`, `.threshold`, `.at_effect` | instrument 2, at 0.05 and at 0.10 |
| `recoverability.exclusion_power.value`, `.threshold`, `.at_effect` | instrument 2b, gate M2 |
| `instrument5.road_class_ordering_ok`, `.river_flowacc_rho`, `.repeat_pass_correlation`, `.ridge_negative_control_slope` | instrument 5's four checks |

**The gates, each as a boolean plus the quantity it read**

`gates.E1.passed` / `.value`, and the same for `S1`, `R0`, `L1`, `G1`, `G2`, `G3`,
`W1`, `N1`, `H1`, `M1`, `M2`, `P1`. Thirteen booleans and thirteen quantities.
A gate's outcome is a result and it is reported whether it passed or failed.

**The label accounting, which is a result in its own right**

| key path | what |
|---|---|
| `labels.counts.by_fire[].fire` / `.candidate` / `.eligible` / `.held` / `.crossed` / `.indeterminate` | the accounting table's spine |
| `labels.counts.by_fire[].by_reason.{SCENE,TIMING,SIDE,CLOUD,MID,DETACH,FLANK,FLANK_AMBIG}` | indeterminate by code |
| `labels.counts.by_fire[].by_ineligible.{FUEL,POSTDATE,NOEXIST,EDITION,WIDTH,NOBURN,NOTMAIN,NODETECT,RULEVAL}` | ineligible by code |
| `labels.counts.by_barrier_type[]` | the same, by road, river and ridge |
| `labels.counts.total_labelled`, `.total_held`, `.total_crossed` | **the numbers P2 requires to stop being orders of magnitude**, written before the first fit |
| `labels.effective_encounters.value`, `.method` | the effective independent-encounter count of 10.6, from the three variance components |
| `labels.rule_validation.n_units`, `.disagreements`, `.confusion[][]`, `.divergence_steps[]` | the second pass of 5.8 |
| `labels.side_tier_counts.S_A`, `.S_B`, `.none` | how the side rule resolved |
| `labels.crossed_reachability.by_geometry`, `.by_timing`, `.flank_ambig` | how `CROSSED` was reached, which is the measured answer to A6's scenario S4 |

**The pre-labelling checks and the sensitivity register**

`checks.S0.c_distribution.deciles[]`, `checks.S0.pass_fraction_by_z_side{}`,
`checks.smoke_decision.by_fire[].option`, `.trigger`, `.masked_fraction`,
`checks.osm_road_length_ratio.by_fire[]`,
`checks.wind_side_agreement.by_fire[]`,
`checks.mask_symmetry.deciles[]`,
`sensitivity.<parameter>.<value>.{labels,width_eiv_mean,width_ci90_low,width_ci90_high,arm_reassignment_count}`
for every parameter and every value of section 12.8 and 12.9,
`selection.exclusion_vs_width.coefficient`, `.ci90_low`, `.ci90_high`, `.reading`
for the section 12.9 clustering check.

**Provenance, carried inside the artifact**

`meta.prereg_version`, `meta.prereg_path`, `meta.signoff_record`,
`meta.split.call`, `meta.split.kwargs`, `meta.split.fingerprint_complex`,
`meta.split.fingerprint_segment`, `meta.seeds{}`, `meta.n_fits_run`,
`meta.fit_log_path`, `meta.inputs[].dataset_id` / `.sha256`,
`meta.software.pymc_version`, `.python_version`.

### 22.3 The staging file

    research/roads/numbers_staged.json

A JSON list, in the registrar's own `entry()` shape from `scripts/build_numbers.py`,
one object per number this direction proposes, with `git_commit` left empty for the
orchestrator per `NUMBERS_PROTOCOL.md` section 5. The shape, with the primary
metric as the worked example and `value` null because no fit has run:

```json
[
  {
    "value": null,
    "unit": "log predictive score per labelled segment",
    "source_file": "research/roads/results/roads_prereg_v0_2_results.json",
    "json_path": "held_out.primary_metric.value",
    "derivation": "mean out-of-complex log predictive score, leave-one-complex-out over five Korean fire complexes, held-out random effects integrated over the fitted hyperprior per section 10.7, computed by research/roads/fit.py",
    "config_hash": null,
    "config_hash_at_production": null,
    "git_commit": "",
    "sample": "labelled encounter segments, five fire complexes, held-out complex named per fold",
    "caveat": "operational barrier performance under Korean suppression practice, not a physical barrier effect; interval is the spread across five folds, and the within-fold bootstrap is a lower bound",
    "forbidden_phrasings": [],
    "check": "",
    "reproducibility": null,
    "reproducible": false
  }
]
```

`forbidden_phrasings` and `check` are written by A6 at verification time from the
claim sentence, per `NUMBERS_PROTOCOL.md` section 5, so they are empty here
deliberately rather than by omission. `reproducibility` resolves through
`REPRO[source_file]` inside `scripts/build_numbers.py`, and a new research artifact
needs a reproducibility record added to that file, which is outside `research/` and
is standing human-gate item NH-A6-04.

### 22.4 P13, compute and feasibility

One laptop, no HPC, no GPU (scope rule 4). PyMC with NUTS, 4 chains, 2,000 warmup
and 2,000 post-warmup draws, `target_accept` 0.9.

**The estimate.** The primary model has about 15 population parameters, three
variance components, and one latent width per road and river segment. At the G1
sample size of order 150 to 300 labelled segments that is roughly 200 to 350
parameters, dominated by the latent widths, on a likelihood that is a logistic with
a Gaussian measurement layer. Expected wall clock:

| what | estimate |
|---|---|
| one primary fit, all data, 4 chains | 5 to 20 minutes |
| one cross-validated primary, 5 folds | 25 to 100 minutes |
| the 48 specifications of section 19.1, each cross-validated | 20 to 80 hours |
| instrument 2 and 2b, 500 draws each, at reduced sampler settings | 10 to 40 hours |
| the label pipeline, all five fires, once | 1 to 4 hours, dominated by raster input and output |
| the label pipeline re-run over the section 12.8 and 12.9 grids | 30 to 130 hours |

The total is days rather than hours, and on one laptop that is the binding
constraint, not memory.

**What gets cut if it does not fit, decided now and in this order.** The list is
ordered so that nothing above a cut can depend on anything below it.

1. **The sensitivity grids drop from three values to two** (the primary and the
   more conservative neighbour) for every parameter except `d_out`, `tau_burn` and
   the two `f_lee` cuts, which keep their full grids because they move the label
   itself. The dropped values are named in the results artifact as dropped.
2. **The sensitivity and robustness fits run at 1,000 warmup and 1,000 draws**
   instead of 2,000 and 2,000, with their R-hat and effective sample size reported
   at the reduced settings and with any that fail the section 7.6 gates reported as
   failed rather than quoted. The primary, the baselines, the two bounding fits and
   the comparison model keep the full settings and are never reduced.
3. **Instruments 2 and 2b drop from 500 draws to 200**, with the Monte Carlo
   standard error on the reported power stated beside it. They are not dropped
   entirely under any circumstances, because gates R0, M2 and the whole reading rule
   of section 11.5 depend on them, and a design that cannot afford its own reading
   rule should not be fitted.
4. **The label pipeline grid re-runs are restricted to one fire complex** for the
   parameters that survive step 1, with the restriction and the complex named.
5. **The segment-length sensitivity at 50 m and 200 m is dropped last**, because it
   is the most expensive single item (two full label pipeline runs and two full
   cross-validated fits) and the least load-bearing: it answers a question about the
   unit rather than about the hypothesis.

What is **never** cut: the primary fit, the five folds, the three baselines, the
errors-in-variables layer, the bounding analysis of section 10.5, the gates of
section 11.3, and the full label accounting table. If those do not fit on one
laptop, the finding is that the design does not fit on one laptop, and it is
reported rather than trimmed around.
