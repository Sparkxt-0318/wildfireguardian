# Leakage audit checklist

**Owner: A6. Version 1.0, 2026-09-16.** Run against every model in the program,
before the fit as a design review and after the fit as a verification.

A checklist that never refuses anything is worthless, so this one is written to
refuse. Every item names a trap that can actually happen to these three
directions with these three datasets. Items that would be true of any machine
learning project anywhere are in Part A and kept short; the value is in Parts B,
C and D, which are about Korean fires, Sentinel-2 scenes, forest roads, slope
units and the Korea Forest Service record.

## How to run it

1. The modeling agent fills in every item with a verdict and one line of
   justification, before the fit. This is item P11 of the sign-off protocol.
2. A6 fills the same list in independently, without reading the author's
   answers, then compares. The disagreements are the finding.
3. Verdicts: `clean`, `mitigated` (with the mitigation named), `present`
   (leakage is there and the result is scoped accordingly), `not applicable`
   (with the reason), `unresolved`.
4. **Refusal rule.** Any item marked CRITICAL that ends the pass at `unresolved`
   or `present` without an accepted scope cut refuses the sign-off. A MAJOR item
   at `unresolved` becomes a numbered condition. MINOR items are recorded.
5. Leakage found after a fit invalidates the numbers from that fit. They are
   marked withdrawn in `research/eval/numbers_staging.json`, not quietly
   recomputed, and the withdrawal is kept.

The repository has already measured what this costs. The Yeongdeok fold in
`docs/leakfree_fold.md` trained on a fire of the same complex as the held-out
fire: the held-out ROC-AUC was 0.9403 with the co-located fire in training and
0.8691 without it, and the forecast-only origin count moved from 42 to 34. That
is the scale of the thing this file exists to catch, and it was found only
because somebody went looking.

---

## Part A. Cross-cutting

**A1. Preprocessing fitted on the full set. CRITICAL.**
Scaling, centring, imputation, PCA, target encoding, variogram range, dNBR
normalisation constants and class weights are fitted inside the training fold or
they are leakage. The trap here is that the natural place to write a
normalisation is in the loader, which runs once over everything.
*Detection:* every transform that has parameters is constructed inside the fold
loop, or is a pure function of constants declared in the pre-registration.

**A2. Hyper-parameters and priors selected on the held-out set. CRITICAL.**
Choosing a prior scale, a GPD threshold, a block size, a learning rate or a
number of knots by looking at held-out performance makes the held-out set a
training set. Nested cross-validation, or a declared inner split, or the value
is fixed in the pre-registration and never moved.
*Detection:* count the times the held-out score was computed before the number
was reported. The pre-registration says how many are allowed (P10). More than
one look at the primary held-out score is a finding.

**A3. Feature selection before splitting. CRITICAL.**
Screening covariates by their association with the outcome over the whole
dataset, then cross-validating the survivors, gives an optimistic score on
covariates that carry no signal at all.

**A4. Derived features that cross the fold boundary. CRITICAL.**
A feature computed with a neighbourhood, a rolling window, a smooth or a
kriging over the whole dataset carries held-out information into training even
when the rows themselves are separated. Terrain smoothing over a window that
spans a block boundary, a fire-level mean, a per-county rate: all of these.
*Detection:* for each feature, name its support. If the support crosses the
split boundary, it is either recomputed per fold or dropped.

**A5. Duplicate and near-duplicate rows. MAJOR.**
The Korea Forest Service record has known duplicates: the registry notes that
Uiseong 2025 appears as two same-day records with different areas. Near
duplicates are worse than exact ones because deduplication does not find them.
*Detection:* exact duplicate count, and a near-duplicate count by a declared
rule, both reported. A duplicate pair split across the fold boundary is a
finding.

**A6. The analyst's memory. MAJOR.**
The held-out set is not held out from the person. Everyone in this program
already knows roughly what happened at Uljin 2022 and Sancheong 2025, and that
knowledge shapes the model form, the covariate list and the priors. There is no
clean fix. The honest mitigations are: fix the design before touching the data,
keep the amendment record of section 4 of `SIGNOFF.md`, and state this
limitation in the paper rather than pretending the split cured it.

**A7. Repeated peeking and undocumented fits. MAJOR.**
The number of fits run before the reported one is the single most useful
diagnostic a reviewer can ask for, and the only one nobody volunteers. It is
recorded in P10 and reported.

**A8. Early stopping, convergence tuning or outlier removal that uses the outcome. MAJOR.**
Dropping the rows the model fits badly is target leakage with a friendly name.
Outlier rules are declared in advance and are functions of covariates, not of
residuals.

**A9. Geocoding and gazetteer drift. MINOR.**
Addresses geocoded today with a gazetteer updated after the fire can place a
fire at a boundary that did not exist then. Record the geocoder, its version
and its date, and treat precision classes as a covariate rather than dropping
the imprecise rows, which would be outcome-dependent missingness.

**A10. Missingness that depends on the outcome. MAJOR.**
Rows dropped because a covariate is missing, when missingness is caused by the
event, shrinks the very cases that matter. The registry already records 12
negative durations and impossible end years in the Korea Forest Service files.
Those rows are flagged and counted, never silently dropped.

**A11. Metric computed on the wrong resampling unit. MAJOR.**
Bootstrapping rows when the rows are clustered by fire gives an interval that is
far too narrow. Resample the cluster.

**A12. The Korea-only rule as a leakage path. MINOR, and a scope rule.**
A foreign coefficient imported as a fixed prior mean is not a citation, it is
foreign data entering the fit through the prior. Where a foreign study supplies
a prior, the prior is weak, its influence is checked by a sensitivity run with a
flat prior, and both are reported.

---

## Part B. Roads, the barrier breach model

**B1. The severity covariate is partly its own label. CRITICAL.**
The label held or crossed is produced by comparing Sentinel-2 dNBR on the two
sides of the barrier against a threshold. Any burn severity covariate taken from
the same dNBR scene pair is a monotone function of the quantity that defines the
label, over the same pixels. A model given that covariate will look excellent
and will have learned the label rule.
*Mitigations, in order of preference:* take severity only from the windward side
and only from pixels outside the buffer that defines the label; or use a
pre-fire fuel covariate from the 임상도 forest type map instead of dNBR; or drop
severity from the primary model and report it only as a secondary analysis with
this contamination stated. Whichever is chosen goes in P4 with its paragraph.

**B2. Suppression effort is confounded with barrier width, and that is the
direction's central threat, not only a leakage item. CRITICAL.**
A wide forest road is also the road the engines drove up, the place the crews
stood, and the line the backfire was lit from. If wide barriers hold more often,
the width coefficient may be measuring access and effort rather than the
barrier. Nothing in the planned covariate set separates the two.
*Detection:* ask what covariate distinguishes a 6 m road with a crew on it from
a 6 m road without one. If the answer is none, the pre-registration says so in
P15 and the claim is scoped to association under Korean suppression practice,
not to the physical width. Candidate partial mitigations: helicopter and ground
resource records from the Korea Forest Service state history, time of day as a
proxy for helicopter availability, and distance to the nearest access point
treated as a separate covariate from width.

**B3. Selection on the front having reached the barrier. CRITICAL.**
Segments enter the dataset when a fire front reached them. That arrival is
established from satellite detections, which are censored by overpass timing,
cloud and the detection floor. A barrier that stopped a fire early may leave too
little heat to be recorded as reached, and would then never enter as a hold. The
sample is conditioned on a variable that is correlated with the outcome.
*Detection:* report the number of candidate segments excluded for want of an
arrival, by fire, and check whether exclusions cluster on the wide barriers. A
pre-registered sensitivity analysis over the arrival rule is required.

**B4. The buffer distance is a researcher degree of freedom. CRITICAL.**
The buffer that separates near side from far side sets both which pixels define
the label and which pixels feed several covariates. It can be moved until the
result improves.
*Mitigation:* the buffer is fixed in the pre-registration with its
justification, the sensitivity grid is declared in advance, and every value in
the grid is reported, not only the chosen one.

**B5. One scene, two sides. MAJOR.**
Both sides' dNBR come from the same pre-fire and post-fire scene pair. Haze,
a cloud edge, a shadow, a terrain illumination difference across a ridge or the
burned road surface itself moves both sides together and can create an apparent
crossing. Ridge barriers are the worst case, because the two sides differ
systematically in illumination and in aspect.
*Detection:* per-segment scene quality flags, the illumination difference
between the two sides as a recorded quantity, and a check that the label rate
does not track the scene date or the cloud mask.

**B6. Adjacent segments are near-duplicates. CRITICAL.**
One hundred metre slices of the same road under the same weather hour are not
independent observations. Effective sample size is closer to the number of
barrier runs per fire than to the number of segments, and it may be two orders
of magnitude below the row count.
*Mitigation:* never split segments at random. Blocks are contiguous runs, and
the primary split is leave-one-complex-out over fires
(`research/eval/splits.py`, `PRIMARY_SPLITS["roads"]`). The effective sample
size estimate is item P2 and is reported beside every interval.

**B7. The fire random effect and the held-out fire. MAJOR.**
With a fire-level random effect and five fires, the variance component is barely
identified, and a held-out fire has no fitted random effect. Predicting the
held-out fire with the random effect set to zero is a different model from the
one that was fitted, and it usually predicts better than the honest version
which draws from the hyperprior.
*Mitigation:* the pre-registration states which of the two is the primary
prediction rule, in P5, before the fit. Both are reported.

**B8. The two-term breach product is not identified by a binary label. MAJOR.**
A breach probability written as one minus the product of the complement of a
flame crossing term and the complement of an ember spotting term has two latent
components and one binary observation per segment. Without an extra source of
information, the split between the two is set by the priors rather than by the
data, and a posterior for either term separately is then a restatement of the
prior.
*Mitigation:* either bring a second observable that distinguishes them, for
example the presence of an ignition beyond the barrier at a distance longer than
any plausible flame length, with its own label rule, or fit the total breach
probability only and present the decomposition as a structural assumption rather
than as an estimate.

**B9. Detection timing cannot attribute an overnight crossing. MAJOR.**
Sentinel-2 revisit is measured in days, not hours. A crossing whose timing is
established from detections may be attributed to the wrong weather hour, so
wind speed and direction at crossing time carry substantial measurement error,
and that error is correlated with fire size because big fires are revisited
differently.
*Mitigation:* declare the time-attribution rule, propagate the uncertainty, and
report how many segments have an ambiguous crossing hour.

**B10. The barrier map conditions the sample. MINOR.**
Segments exist where a road, river or ridge is mapped. Mapping quality varies by
region and by land ownership, and a better-mapped area is also a
better-managed area.

**B11. The claim under test must not enter as a covariate cut point. MAJOR.**
The 6 m threshold is the claim being tested, and binning width at 6 m before
fitting bakes it in. Width enters continuously, and the 6 m question is answered
from the fitted curve, not from a bin boundary chosen to match the claim.

**B12. The width covariate has to be measured, and the measurement error
biases the test toward the null. CRITICAL, and it is not leakage but it belongs
on the same sheet because it damages the result the same way.**
A1 confirmed against the portal that the Korea Forest Service forest road
dataset carries **no width attribute**. Width therefore has to be derived from
imagery, on a sample, by a rule. That puts classical measurement error on the
single covariate the whole direction turns on, and classical measurement error
in a covariate attenuates its slope toward zero. The consequence is an
asymmetry that has to be written into the reading rule **before** the fit: a
flat fitted curve is consistent both with width not mattering and with width
mattering and being measured badly, so a null result is weak evidence against
the claim under test, while a steep curve measured under attenuation is strong
evidence for it.
*Mitigations, all of which go in P3 and P5:* a written measuring rule with its
imagery source and its unlabelable class; a repeat measurement on at least
thirty segments to estimate the error variance directly; a measurement error
model, or a reported attenuation bound computed from that variance; and the
sensitivity of the fitted slope to the assumed error variance, reported as a
range. Reporting a single attenuated slope as if it were the truth is the
failure mode here.

---

## Part C. Landslides, the post-fire hazard clock

**C1. Random splits are forbidden. CRITICAL.**
Slope units within a few hundred metres share a storm, a geology, a soil map
unit, an aspect and the same fire. A random split puts near-duplicates on both
sides and produces a score that has nothing to do with predicting a new slope.
Spatial block cross-validation only, through
`research/eval/splits.py::spatial_block_cv`, with the block size and buffer of
`PRIMARY_SPLITS["landslides"]` and the declared sensitivity grid.
*Detection:* the block must be larger than the correlation range of the
triggering rainfall, which is a property of the radar QPE product and not of the
slope units. The block size is justified against that range in P6, and the
buffer exists because a block edge is not a barrier.

**C2. Time since fire is aliased with calendar year. CRITICAL.**
With a handful of fires, the third year after the 2019 Goseong fire is 2022, and
nothing else is. A hazard that falls with years since fire is observationally
identical to a hazard that falls because 2022 had less intense rainfall than
2020. The recovery curve and the calendar cannot both be free.
*It is worse than the general argument suggests with the committed data.* A1
verified that the Korean landslide occurrence record on hand covers **2021 to
2025 only**. Inside that five-year window, each fire contributes one and only
one run of years since fire: Goseong 2019 contributes years two to six, and
Sancheong 2025 contributes year zero. Years since fire and calendar year are
then not merely correlated, they are a deterministic function of each other
within each fire, and only the between-fire contrast carries any information
about the shape of the curve. With a handful of fires that contrast is a
handful of points.
*Mitigation:* include the triggering rainfall explicitly at the event level, so
the time term is not carrying the weather; report the design matrix collinearity
honestly; and if the two are not separable with this set of fires, say so in P15
rather than reporting a clock that the data cannot support. This is the item
most likely to turn into a refusal.

**C3. Inventory completeness varies with time and campaign. CRITICAL.**
Landslide inventories are compiled after events, by campaigns of varying
intensity, and mapping effort after a famous fire is highest in the first year.
A hazard that decays with years since fire is indistinguishable from a mapping
effort that decays with years since fire.
*Detection:* record, per inventory and per year, who mapped it, from what
imagery, at what minimum mapped size. Model or bound the detection probability,
or restrict to a window where completeness is documented as constant.

**C4. Burn severity is both covariate and search prior. MAJOR.**
Mappers look where the fire burned hot. Severity then predicts the inventory,
partly because mappers found more there. Same family as B1, different mechanism.

**C5. The unburned control is not comparable. MAJOR.**
Control slope units taken outside the fire perimeter differ in aspect,
elevation, fuel and management, because fires do not burn at random. Control
units inside the perimeter but unburned are inside the fire's weather.
*Mitigation:* the matching or propensity design is declared in advance in P5,
with the covariates it balances on and the balance statistic that will be
reported whichever way it comes out.

**C6. Species is confounded with terrain and management. MAJOR.**
In Korea, pine dominates dry ridges and thin soils; broadleaf sits on deeper,
moister soils. A species contrast in landslide timing may be a soil depth
contrast, a slope contrast or a management contrast. The species arm is the
weakest arm of this direction and its pre-registration says so.

**C7. The risk set in discrete time. MAJOR.**
A slope unit that failed leaves the risk set, or it does not, and that choice
changes the estimated hazard. Repeat failures, partial failures and units
reworked by erosion control after the event all need a rule fixed in advance.
Units stabilised by post-fire erosion control works are a treatment applied in
response to risk, which is the same reverse-causality shape as suppression in
Part D.

**C8. Sancheong 2025 as a held-out stress test is only held out if nobody read
the paper first. CRITICAL.**
If the Sancheong inventory of Nguyen, Song and Kim 2026 and its 568 initiation
points inform the model form, the covariate list, a root decay rate or a prior,
then Sancheong is a training set wearing the label of a test set. Reading the
paper's results counts.
*Mitigation:* record, before any fit, exactly what has been read from that paper
and by whom, in the amendment section of the pre-registration. If its numbers
were used to set a prior, Sancheong is not a valid held-out fire, and another
fire has to take that role.

**C9. Root reinforcement curve parameters imported from elsewhere. MAJOR.**
A Sidle-type curve whose decay and regrowth rates come from a non-Korean study
is a foreign quantity entering a Korean fit through the prior. Allowed as a weak
prior with a sensitivity run, per item A12, and never as a fixed constant that
the Korean data cannot move.

**C10. Address-level records cannot be assigned to slope units cleanly, and the
error is not random. CRITICAL.**
A1 verified that the landslide occurrence record on hand is **address-level,
5118 records**, with no coordinates. Assigning an address to a DEM-derived slope
unit needs geocoding, and geocoding precision in Korean mountain districts is
worst exactly where the units are steepest, smallest and most numerous, because
a rural address resolves to a village centroid or a road access point rather
than to the failure. So the assignment error is correlated with slope, with
remoteness and with unit size, which are covariates in the model. A failure
placed at the valley road instead of on the slope above it becomes a negative on
the steep unit and a false positive on the flat one.
*Detection and mitigation:* record the geocoding precision class per record and
carry it as a covariate; report the share of records whose precision class
cannot support a slope-unit assignment at all, and exclude them by a rule
declared in advance rather than by inspection; run the primary analysis at a
coarser unit, such as the catchment, where the assignment error is contained,
and treat the slope-unit analysis as secondary. A sign-off will not be given for
a slope-unit model whose unit assignment error has not been quantified.

---

## Part D. Suppression as censoring

**D1. Any covariate computed over the whole fire duration leaks the outcome. CRITICAL.**
Final duration, total resources committed, maximum observed spread rate, the
number of helicopters and the count of status updates are all consequences of
how big the fire got. A prediction made from information available in the first
hours uses only quantities knowable by then, and each covariate in P4 carries
its knowable-at time for exactly this reason.
*Detection:* for every covariate, ask whether its value could have been written
down at the prediction horizon. If the answer needs the end of the fire, it is
out.

**D2. Reported size at hour h does not exist. CRITICAL.**
The record carries the final area, entered after containment. There is no
observed area at hour three. Any feature that looks like early size is a
back-filled final size, or a reconstruction whose own assumptions need stating.

**D3. Report time is not ignition time. MAJOR.**
The registry records that 발생일시 is a reported start time and that every
duration is report-to-containment. Fires reported late are already large when
the clock starts, which biases the early hazard downward and correlates the bias
with remoteness and with night.

**D4. The tail model is fitted to what suppression left behind. CRITICAL, and
this is the direction's central threat.**
A generalised Pareto tail estimated on recorded sizes is estimated on the
suppressed distribution. Recovering what the distribution would have been
without suppression requires an assumption about a counterfactual that the
Korean record never observes, because suppression is applied to every fire. The
shape of the corrected tail will be driven by that assumption more than by the
data.
*Mitigation:* the assumption is stated as an assumption in P5 and in P15, the
sensitivity of the corrected tail to it is reported as a range rather than a
curve, and the claim is written as conditional on the assumption.

**D5. Forward chaining only, and the reason is policy drift. CRITICAL.**
The Korean record spans decades of changing doctrine, a changing leased
helicopter fleet, changing reporting rules and changing detection. A random
split lets a 2020 policy predict a 1998 fire. Use
`forward_chaining_by_year` from `research/eval/splits.py` with the registered
arguments.
*And the committed data does not currently support it.* A1 verified that the
committed Korea Forest Service fire statistics extract covers **2022 to 2025
only, 2020 rows**. Four distinct years yield at most two forward-chained folds
with a two-year training window, and none at all at the registered training
length. Neither the containment hazard nor the tail can be fitted on that
extract in a way A6 would sign: a tail estimated on four years of one doctrine
period, evaluated on one held-out year, is an anecdote with an interval on it.
The direction is therefore conditional on the longer record reaching status
`verified` (Waiting-on-John items WJ-001 and WJ-006). Until then the honest
options are to fit nothing, or to pre-register a descriptive analysis that
makes no held-out claim at all and says so.

**D6. The point score is a second model and needs its own held-out year. CRITICAL.**
Distilling a fitted hazard into an integer score is model selection. Doing it
on the full data, or on the same held-out years used to evaluate the hazard
model, gives the score a free look. The distillation runs inside the training
fold, and the score is evaluated on years neither the hazard model nor the
distillation saw.

**D7. Administrative target encoding. MAJOR.**
A county mean fire size, a district escape rate or a station workload computed
over the whole record includes the target fire and its neighbours in time.
Recompute inside the fold, or drop.

**D8. Duplicate fire records counted twice. MAJOR.**
Uiseong 2025 appears twice in the state history file with different areas. A
duplicate pair straddling a fold boundary is a direct leak, and a duplicate pair
on the same side doubles a single fire's weight in the likelihood.

**D9. Outcome-dependent cleaning. MAJOR.**
The 12 negative durations and the impossible end years of 2055 and 2223 are
outcome-side defects. Dropping them silently removes cases non-randomly with
respect to the outcome. Flag, count, report, and pre-register the rule.

**D10. Night as a covariate carries reverse causality. MAJOR.**
Dispatch responds to danger, and detection, reporting and the helicopter fleet
all change at night. A night coefficient is an association under those
conditions, and forbidden-claim rule RC-007 requires an E-value before any
causal wording.

**D11. The threshold of the tail model is a researcher degree of freedom. MAJOR.**
The excess threshold is chosen before the covariate-dependent parameters are
fitted, with the diagnostic and the grid declared in advance, and every value in
the grid reported.

---

## Part E. The sheet to copy into a pre-registration

| id | severity | verdict | one line |
|---|---|---|---|
| A1 preprocessing inside the fold | CRITICAL | | |
| A2 hyper-parameters and priors | CRITICAL | | |
| A3 feature selection before the split | CRITICAL | | |
| A4 feature support crossing the boundary | CRITICAL | | |
| A5 duplicates and near-duplicates | MAJOR | | |
| A6 the analyst's memory | MAJOR | | |
| A7 undocumented fits | MAJOR | | |
| A8 outcome-driven cleaning or stopping | MAJOR | | |
| A9 geocoder drift | MINOR | | |
| A10 outcome-dependent missingness | MAJOR | | |
| A11 resampling unit | MAJOR | | |
| A12 foreign quantity entering through a prior | MINOR | | |
| B1 to B12 | see Part B | | roads only |
| C1 to C10 | see Part C | | landslides only |
| D1 to D11 | see Part D | | suppression only |

The pre-registration carries the full rows for its own direction, not the
summary line.
