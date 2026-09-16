# A6 prior leakage read, landslides (H-SLIDE)

**Owner: A6. Written 2026-09-16, round 4.**

## Provenance of this document, and why the header matters

**This read was written BEFORE opening `research/landslides/` at all.** No file
under `research/landslides/` and no file under `research/reports/A4/` was read
before the last line of this document was written. That includes
`PREREG_landslides_2026-09-16_v0.1.md`, `PREREGISTRATION.md`,
`DATA_REQUIREMENTS.md`, `OPEN_QUESTIONS.md`, `numbers_staged.json` and the three
scripts under `research/landslides/design/`.

The reason is condition C10 on the roads record. On roads the order ran the
other way: A3 read `research/eval/LEAKAGE.md` and then wrote its P11 answers,
and A6 read A3's answers before running the list. The two lists were therefore
not independent, the comparison that item P11 exists to produce was lost, and
A3 said so rather than manufacturing agreement. C10 fixed the order for the
remaining two directions. This file is the first half of that fix.

**What was consulted before writing.** All of it is material A4 also had, and
none of it is A4's own analysis:

| source | what was taken from it |
|---|---|
| the program brief's landslide design, as stated in this round's task | the design under review |
| `research/README.md` | the direction's question and the scope rules |
| `research/eval/LEAKAGE.md` v1.0 | A6's own checklist, items A1 to A12 and C1 to C10 |
| `research/eval/SIGNOFF.md` v1.0 | items P1 to P16 |
| `research/eval/KILLSHOT_TEMPLATE.md` | A6's own seeded landslide prior of 2026-09-16 |
| `research/data/REGISTRY.yaml` | dataset ids, statuses, known issues |
| `research/data/raw/kfs_landslide_history/` the CSV itself | column structure and the counts in section 2, computed here |
| `research/eval/splits.py` | A6's own splitter, read for C1 |
| `research/FORBIDDEN_CLAIMS.md` | RC-003, RC-004, RC-005, RC-009, RC-010 |
| the orchestrator's three re-derived facts, restated in this round's task | the lot-number finding, the fire cohort counts, the rank finding |

The last row is the one place where a fact that originated with A4 reached this
document before A4's document did. It is restated here rather than hidden,
because pretending otherwise would corrupt the comparison in the other
direction. What it gave me is three facts. It gave me none of A4's reasoning,
none of A4's verdicts, and no item of A4's own checklist.

---

## 1. The design as briefed, restated

So that the comparison later is against a fixed target:

1. A discrete-time hazard on DEM-derived slope units.
2. Covariates: storm rainfall, slope, soil, geology, root reinforcement.
3. A Sidle-type root curve: exponential decay of old root strength plus sigmoid
   regrowth of new root strength, against years since fire and burn severity.
4. Rates estimated separately for pine and for broadleaf.
5. An infinite-slope factor-of-safety link, reporting critical rainfall by years
   since fire.
6. Sancheong 2025 held out.
7. Roads and salvage logging carried as separate exposures.
8. Spatial block cross-validation only.

---

## 2. What the committed record actually is, computed here

Every number in this section was computed in this session from
`research/data/raw/kfs_landslide_history/` directly, with the loader bypassed.
They are covariate-side and record-structure facts, not outcome views in the
sense of `SIGNOFF.md` section 4, because no hazard and no fit exists to view.

**Columns.** `연도`, `순번`, `재난구분`, `시설구분_등급`, `상세주소_시도`,
`상세주소_시군구`, `상세주소_읍면도`, `상세주소_리`, `피해물량(ha)`. 5,118 rows.

**There is no lot number and no coordinate.** The finest address column is `리`.
This matches the orchestrator's independent re-derivation across all four
address columns. The parcel rung does not exist anywhere in the record.

**The address resolution is coarse and is the binding constraint on the unit.**
178 distinct 시군구, 800 distinct 읍면, 1,977 distinct full address tuples for
5,118 rows. 220 rows (4.3 per cent) have no 리 at all and 4 have no 읍면.

**The trigger is a storm window, not an event.** `재난구분` holds a multi-day
range such as `2021-07-05~07-08`, or a named typhoon. 24 distinct values over
five years. The registry already warns against parsing it as one date.

**The triggering events are far fewer than 24 in any usable sense.** Per year,
the single largest storm window's share of that year's records is 0.513 in 2021,
0.731 in 2022, 0.847 in 2023, 0.857 in 2024 and 0.986 in 2025. The 2025 window
`2025-07-16~07-20` alone carries 2,599 of the 5,118 rows, which is 50.8 per cent
of the whole record.

**Annual volume rises steeply and monotonically.** 119 rows in 2021, 457 in
2022, 798 in 2023, 1,107 in 2024, 2,637 in 2025. That is a factor of 22 across
the observation window.

**The record is forest land only, by ownership class.** Every value of
`시설구분_등급` is a `산사태_` prefix on a forest ownership class: 사유림 4,151,
국유림 744, 지자체소유림 210, and five smaller classes. There is no non-forest
stratum and no non-landslide stratum.

**Each row carries a damage area in hectares, not a located failure.** Median
damage area by year runs 0.12, 0.43, 0.33, 0.09, 0.10 ha. Annual sums run 26.8,
327.3, 458.8, 178.9, 611.3 ha.

**Rows are not one-to-one with places.** There are 2,127 distinct
(storm window, 리) cells. 62.6 per cent hold exactly one row, but the largest
holds 78 rows (가평군 조종면 마일리 in the 2025 July window), then 55, then 47.

**Years since fire that the record can observe.** Taking the orchestrator's
cohort counts for fires of 10 ha or more, 26 in 2022, 32 in 2023, one in 2024
and 19 in 2025, and crossing them with storm years 2021 to 2025, the observable
values of years since fire are 0, 1, 2 and 3 and nothing else. Every t = 3 cell
is the 2022 cohort seen in 2025, and half the record's mass sits in one 2025
storm window, so the entire far end of the curve rests on one storm.

---

## 3. Part A of `research/eval/LEAKAGE.md`, run against this design

| id | severity | verdict | one line |
|---|---|---|---|
| A1 preprocessing inside the fold | CRITICAL | `unresolved` | The natural home for a rainfall normalisation, a soil class recode and a severity rescale is the loader, which runs once. No fold-scoped construction is stated in the brief. |
| A2 hyper-parameters and priors | CRITICAL | `unresolved` | The root curve carries at least four free rates. The brief does not say whether any of them is chosen by looking at block cross-validated performance, nor how many looks are allowed. |
| A3 feature selection before the split | CRITICAL | `mitigated` | The covariate list is mechanistic and named in advance rather than screened. Holds as long as geology and soil classes are not collapsed by their association with the outcome. |
| A4 feature support crossing the boundary | CRITICAL | `present` | Radar QPE has a spatial correlation length of tens of kilometres, terrain derivatives use neighbourhood windows, and any per-시군구 rate spans blocks. At a 5,000 m block the rainfall field is common to both sides of every fold edge. |
| A5 duplicates and near-duplicates | MAJOR | `present` | 78 rows in one (storm, 리) cell cannot be 78 independent events at any unit this record can support. Whether they are one failure split across parcels or many is not decidable from the file. |
| A6 the analyst's memory | MAJOR | `present` | Sancheong 2025 is the most reported Korean post-fire landslide event of the decade and the held-out fire. See C8. |
| A7 undocumented fits | MAJOR | `unresolved` | No fit count is stated in the brief. |
| A8 outcome-driven cleaning | MAJOR | `unresolved` | The 220 rows with no 리 are unassignable, and the exclusion rule for them has to be written before anyone sees where they fall. |
| A9 geocoder drift | MINOR | `present` | `vworld_geocoder` is at status `pending`. Korean 리 boundaries and names have been revised inside the observation window. |
| A10 outcome-dependent missingness | MAJOR | `present` | The 4.3 per cent missing 리 is not random: an address is recorded poorly where the place is remote, which is where the slopes are steep. |
| A11 resampling unit | MAJOR | `unresolved` | The cluster is the storm window, not the unit. With one storm holding 50.8 per cent of the record, an interval resampled over units is not merely narrow, it is close to meaningless. |
| A12 foreign prior | MINOR | `present` | The Sidle curve is not Korean. See C9. |

---

## 4. Part C of `research/eval/LEAKAGE.md`, run against this design

### C1. Random splits are forbidden. CRITICAL. Verdict: `mitigated`, with a defect in my own code.

The brief registers spatial block cross-validation only, which is the right
scheme, and `PRIMARY_SPLITS["landslides"]` fixes 5,000 m blocks, a 1,000 m
buffer, five folds and `require_fire_disjoint=True`.

Reading `spatial_block_cv` again for this pass, `require_fire_disjoint=True`
routes every row's fire id through `complex_of` and then unions every block that
shares a key. That is correct when every row belongs to a fire. It is wrong the
moment unburned control units exist, because they have no fire, and whatever
sentinel id they are given is shared by all of them. One shared sentinel unions
every block that holds a single control row, and since controls are by
construction spread across the country, the union swallows the country into one
group. The splitter then hits `len(keys) < n_folds` and raises `LeakageRefusal`.

The refusal is the correct behaviour, in the sense that returning a split would
have been worse, but the message would send the author hunting for a block size
rather than for the sentinel. The fix is that control rows carry a unique id
each, not a shared one, so that they weld nothing. I am recording this against
my own file, not against the direction.

Separately, the block size has to be justified against the correlation range of
the radar QPE product, and 5,000 m is almost certainly below it. This is the
same defect as A4 above, and it is not fixed by a 1,000 m buffer.

### C2. Time since fire aliased with calendar year. CRITICAL. Verdict: `present`, and my v1.0 wording of this item is wrong in an important way.

My v1.0 text says each fire contributes one and only one run of years since
fire, so within a fire t and the calendar are the same variable. That part
stands. But the arithmetic of section 2 above says the binding problem is not
the aliasing at all. It is the **support**.

The observable values of t are 0, 1, 2, 3. Nothing else exists in this record.
A root strength curve of the Sidle shape is an exponential decay plus a sigmoid
regrowth whose interesting behaviour, the minimum of net root cohesion and the
recovery out of it, sits at t of roughly one to ten with a tail to twenty five.
The record observes the first four integers of that domain and stops. Every
t = 3 observation comes from one cohort in one calendar year, and half the
record's mass is one storm in that year.

So the design is right-censored below the quantity it exists to estimate. That
is a different defect from aliasing and it is worse, because aliasing can
sometimes be broken by a between-fire contrast while missing support cannot be
broken by anything except more years of record.

Within the support that does exist, there is then a second problem which is
aliasing proper. The national record volume rises monotonically from 119 to
2,637 rows across 2021 to 2025. For every cohort, larger t means a later
calendar year, which means a year in which many more landslides were recorded
nationally. A reporting series that grows by a factor of 22 over the window runs
in the opposite direction to the hypothesised decay, so the confound biases
toward a null or toward a positive slope on t. That is a direction worth stating
in advance: a flat or rising fitted curve on this record is consistent both with
no post-fire window and with a real window swamped by a rising reporting rate,
and so is weak evidence, while a falling curve fitted against a rising reporting
trend would be evidence of something.

An explicit rainfall term at the storm level does not fix this, because the
storms are so few and so unequal that the rainfall term and the calendar term
are nearly the same variable too.

**This item alone is enough for a refusal in the briefed form, and I expect to
write one.**

### C3. Inventory completeness varies with time and campaign. CRITICAL. Verdict: `present`, and the mechanism named in v1.0 is the wrong mechanism.

My v1.0 text describes mapping campaigns of varying intensity: who mapped it,
from what imagery, at what minimum mapped size. Having now read the file's own
columns, that description does not fit this record.

There is no imagery and no minimum mapped size, because nothing here was mapped.
The columns are an administrative damage entry: a year, a sequence number, a
storm window, a forest ownership class, an address to 리, and a damage area in
hectares. The ownership column is the giveaway. A mapped inventory has no reason
to carry whether the slope is 사유림 or 국유림; a damage record compiled by an
agency that administers forest land by ownership has every reason to.

So the mechanism is **reporting**, not mapping. A failure enters this file when
somebody reports damage on forest land and an office writes it down. That
changes what the bias is attached to. Mapping effort attaches to fire fame and
to post-event campaigns. Reporting attaches to whether anybody was there to see
the failure and had a reason to report it, which means proximity to a road, to a
dwelling, to a cultivated plot or to an asset with a repair budget.

And that mechanism is worse than the mapping one for this specific design, for
two reasons that are particular to this brief.

First, **the brief carries roads as a separate exposure.** If reporting
probability rises with proximity to a road, then a road covariate and the
detection probability are the same variable measured twice, and a fitted road
exposure coefficient is partly the reporting model. The direction would be
putting its confounder on the right-hand side and calling it an exposure.

Second, **a reporting record has no observable zero.** A mapped inventory at
least defines its own frame: within the mapped scene, an unmarked slope was
looked at and found intact. A reporting record defines nothing. Absence in this
file means either that no failure occurred or that no failure was reported, and
the file carries no column that distinguishes them.

I rate this CRITICAL in v1.0 and I rate it CRITICAL still, but for the
reporting mechanism rather than the mapping one, and I now think it is the
second most serious item in this direction rather than somewhere in the middle.

### C4. Burn severity is both covariate and search prior. MAJOR. Verdict: `mitigated` to MINOR, by the same correction.

This item was written for mappers who look where the fire burned hot. If nobody
mapped anything, the search-prior mechanism largely goes away. What survives is
weaker and indirect: a severely burned catchment draws official attention, and
attention raises the reporting rate. That is real but it is a second-order path
through C3 rather than an item of its own. The severity covariate must still
come from `sentinel2_l2a_dnbr`, which is at status `pending`.

### C5. The unburned control is not comparable. MAJOR. Verdict: `unresolved`, and it interacts with C1.

Unchanged in substance. Added this round: the control set is also the thing that
breaks my splitter under a shared sentinel id, and the matching design has to be
declared before anyone looks at where the controls fall.

### C6. Species confounded with terrain and management. MAJOR. Verdict: `present`.

Unchanged, and sharpened by the support finding. Fitting separate decay and
regrowth rates for pine and for broadleaf means fitting two curves on a domain
of four integers, where the far integer is one cohort in one storm. The species
arm should be demoted to a declared secondary analysis, or dropped. RC-004 holds
regardless of what comes out.

### C7. The risk set in discrete time. MAJOR. Verdict: `unresolved`, and the brief's unit makes it undecidable.

A discrete-time hazard needs a rule for whether a failed unit leaves the risk
set. On this record it is not merely undeclared, it is unanswerable: nothing
identifies a place across storms. Two rows in the same 리 in two different
storms may be the same slope or two different ones. Post-fire erosion control
works, which are a treatment applied in response to risk, are not in the
registry at all.

### C8. Sancheong 2025 as a held-out stress test. CRITICAL. Verdict: `present`, and the brief's premise is wrong on the dates.

Two separate problems.

The first is the one v1.0 names: if the Nguyen, Song and Kim 2026 Sancheong
inventory and its 568 initiation points informed the model form, the covariate
list, a root rate or a prior, then Sancheong is a training set wearing a test
set's label, and reading the paper's results counts.

The second I had not seen before doing the arithmetic of section 2. The
Sancheong fire is in the March 2025 cohort and the 2025 storm window is that
July. Sancheong therefore contributes **t = 0 only**. Holding out a fire that
contributes t = 0 tests the model at the one place on the curve where the root
hypothesis makes no distinctive prediction, because at t = 0 the old roots have
not yet decayed. Whatever else Sancheong is, it is not a stress test of the
window. The brief's choice of it as the held-out fire is a mistake about what
the held-out fire would be testing, independent of whether anybody read the
paper.

### C9. Root curve parameters imported from elsewhere. MAJOR. Verdict: `present`, and on this support it is closer to CRITICAL.

Item A12 allows a foreign quantity as a weak prior with a flat-prior sensitivity
run. That allowance assumes the Korean data can move the prior. On a domain of
four integers with one cohort at the far end, it cannot. The posterior on the
decay rate and on the regrowth rate will be the prior with slightly narrower
tails, and reporting it as an estimate would be reporting the Sidle paper back
to itself with a Korean label on it. The flat-prior sensitivity run of A12 is
not an adequate mitigation here; it is the diagnostic that will demonstrate the
problem, which is a different thing. RC-005 and RC-010 both bear.

### C10. Address-level records cannot be assigned to slope units cleanly. CRITICAL. Verdict: `present`, and it is now worse than v1.0 states.

My v1.0 text assumes geocoding an address to a point and worrying about the
precision class. Having read the columns, the record does not contain an address
in the sense a geocoder consumes. It contains an administrative path that stops
at 리, with 220 rows stopping at 읍면 or above. There is no lot number anywhere
in the file, which the orchestrator has confirmed independently across all four
address columns. So there is no rung below the 리 polygon to geocode to, and the
best possible assignment is uniform over a 리, which in Korean mountain districts
is square kilometres of mixed slope, valley floor and settlement.

This kills the slope unit as the primary unit outright. It is not a matter of
carrying a precision class as a covariate; there is no precision to carry. My
v1.0 already says a sign-off will not be given for a slope unit model whose unit
assignment error has not been quantified, and the quantification here returns
the answer that the error is the size of the unit.

The v1.0 mitigation text offers running the primary analysis at a coarser unit
such as the catchment. I would now say more strongly: **the slope unit is not
available as a primary unit on this record at all**, and a coarser unit is not a
fallback but the only thing the record supports. The remaining question is
whether the coarser unit is a catchment, a 리 polygon, or a 읍면.

---

## 5. Items not in `research/eval/LEAKAGE.md` v1.0, found in this pass

These are numbered L1 onward and are candidates for a v1.1 of the checklist.

**L1. The record has no denominator, so a unit-level binary manufactures a
label. CRITICAL.**
A discrete-time hazard on units needs, for every unit and every storm, a zero or
a one. This file supplies neither. It supplies a count of damage entries and a
damage area for the places where something was reported, and says nothing at all
about the places where nothing was. Turning that into a unit-level binary
requires asserting that every unit not named in the file was observed and found
intact, which is an assertion about a reporting record that nothing in the
record supports. The label would be an artefact of the assertion, and the fitted
hazard would be a model of the assertion.
*What is available instead:* a count, or a damage area, per unit per storm, on a
unit large enough that the address supports the assignment, with an explicit
exposure or offset. That is a different likelihood from the briefed one and it
is the honest one. The brief's binary should not survive this pass.

**L2. The trigger is a multi-day window, so the rainfall covariate cannot be the
triggering rainfall. MAJOR.**
`재난구분` is a range such as `2021-07-05~07-08` or a typhoon name. The failure
happened at some hour inside it. An infinite-slope factor of safety is driven by
pore pressure at an hour, and the brief promises to report critical rainfall.
Aggregating radar QPE over a four-day window and calling it the trigger puts
large measurement error on the covariate the factor-of-safety link turns on, and
classical measurement error attenuates its coefficient, so the critical-rainfall
output would be biased in a known direction before anything else happens. The
same asymmetry that item B12 writes for road width applies here and has to be
written into the reading rule before the fit.

**L3. The effective number of triggering events is single digit, and one storm
is half the record. MAJOR, and it is the resampling unit.**
The cluster for any interval is the storm, not the unit. 24 storm windows exist
but the concentration figures in section 2 mean the effective count is nearer
five. One storm window carries 50.8 per cent of the record. An interval that
does not resample storms will be far too narrow, and a leave-one-storm-out check
will move the answer a great deal, which is the honest thing for it to do.

**L4. Salvage logging after Korean fires falls in the same window as root decay
and pushes the same way. MAJOR, and there is no dataset for it.**
Korean post-fire practice removes burned timber in the years immediately after a
fire. That is machinery on wet steep ground, new skid trails, cut stumps and
disturbed soil, concentrated at small t, which is exactly the window the root
curve is trying to measure. Its effect on slope stability runs in the same
direction as root decay. A fitted decline in stability at small t is therefore
consistent with root loss, with salvage disturbance, or with both, and the
briefed design carries salvage as an exposure without any dataset in
`research/data/REGISTRY.yaml` to populate it. Absent that dataset the exposure
is a declared term with no data behind it, which is worse than omitting it,
because it looks adjusted for.

**L5. Rows are administrative damage entries, so the count is partly a count of
parcels. MAJOR.**
78 rows in one (storm, 리) cell, then 55, then 47, against 62.6 per cent of
cells holding exactly one row. One large failure that crosses many ownership
parcels and one storm that produced many separate failures look identical in
this file. Since the ownership class is a column, the split into rows plausibly
follows ownership boundaries rather than failure boundaries, and ownership
parcel density is higher near settlements, which is where reporting is higher
too. So the count covariate and the reporting bias of C3 share a mechanism.
Damage area in hectares is the less contaminated of the two outcome columns and
should probably be the one used.

**L6. The forest-land frame is itself a selection. MINOR, and it bounds the
claim.**
Every row is on forest land by ownership class. A failure on a road cut, a fill
slope or a cultivated hillside is not in this file. If the direction's
deliverable is a post-fire landslide warning adjustment, the warning's users
care about all of those. This is a scope sentence for P15 rather than a leakage
path, but it has to be written.

**L7. `require_fire_disjoint` with a shared control sentinel collapses the
country into one group. MAJOR, and it is a defect in A6's own code.**
Stated in full under C1. The fix is unique ids per control row. This belongs to
`research/eval/`, not to the direction.

---

## 6. Where I expect this to land, written before reading A4

Recorded now so it can be checked later.

I expect to **refuse** the briefed design, on C2 in its support form, on C10,
and on L1, in that order of weight. I expect the slope unit to be unavailable
and a coarser unit to be forced. I expect the unit-level binary to be
unavailable and a count or area per unit per storm to be forced. I expect the
species arm to be demoted or dropped, and Sancheong to be the wrong held-out
fire for the reason in C8.

On whether the direction should proceed at all, my prior before reading A4 is
that the recovery curve is not recoverable from this record and that saying so,
with the assignability and support arithmetic that shows why, is a real result
and the only one available. I do not yet know whether that is enough to justify
the direction continuing, and I will decide that after reading A4.
