# Forecast-conditioned, time-expanded routing for household-level wildfire evacuation and rescue in rural Korea

## Abstract

Satellite fire detection and district-level fire-danger forecasts were both operating in
Korea during the March 2025 Gyeongbuk wildfires, the deadliest on the country's record.
What neither produced was the last-kilometre answer a specific rural household needs:
which way to walk now, and whether a rescue crew can still reach the house. This paper
describes WildfireGuardian, a system that couples an event-held-out ignition-probability
model to a time-expanded pedestrian router and a rescue-ingress calculation, and reports
the result through a registry in which every published number is re-derived from a
committed artifact by an automated gate. The spread model is deliberately ordinary — a
gradient-boosted classifier over sixteen public features, evaluated leave-one-fire-out
on six real Korean fires, mean-of-folds held-out ROC-AUC 0.890 (fold range 0.682–0.974,
pooled out-of-fold 0.905, a different quantity). Its operating point is weak and is
reported as such: pooled cell recall at the shipped threshold is 0.138, and three of the
six held-out fires produce no true positive at all. The coupling is nonetheless where
the decision changes. On the canonical Yeongdeok field, 42 of 458 scanned walk-network
origins reach a refuge only when the router accounts for where the fire will be, and 2
have no safe walking route; those rates hold on a network covering 32.6 % of the
predicted fire core, and the direction of the resulting bias is unmeasured. A second
contribution is negative and is reported in full: the deadline-first dispatch ordering
the system ships never out-rescues nearest-first at the operating window, in 0 of 180
configuration cells. We argue that on a six-event dataset the transferable contribution
is the evaluation design — paired contrasts, matched null controls, and a registry that
keeps withdrawn claims in the tree — rather than the model.

## 1. Introduction

In March 2025 a wildfire that began in Uiseong-gun spread east across Gyeongsangbuk-do
and became, by the count of the rapid attribution study published on it, South Korea's
deadliest wildfire event on record: 32 casualties, 26 of them in Uiseong-gun, more than
48,000 hectares burned and around 5,000 buildings destroyed [@wwa2025korea]. [GAP: the
age composition of the casualties — the motivating fact that most were rural residents
in their sixties to eighties — is reported by Korean press sources that this manuscript
cannot yet cite with a stable URL; the repository's own sourcing task is open]

Detection was not the failure. NASA FIRMS was returning thermal anomalies and the
national forecast was issuing district-level fire-danger levels throughout. The gap was
between those products and an action: a district-level probability does not tell one
household on one lane which direction is still walkable at 09:40, and it does not tell a
fire crew which of the houses that cannot self-evacuate they can still drive to, or for
how much longer. That gap is sharpest exactly where the deaths occurred — in dispersed
rural settlement, among residents who walk slowly, on road networks with few
alternatives.

This paper describes WildfireGuardian, a system built to close that gap on public data,
and — more importantly for a reader deciding whether to believe any of it — the evaluation
design under which it was built. It takes public inputs (satellite detections, reanalysis
weather, terrain, land cover, road networks), fits a per-cell ignition-probability model,
propagates it into a time-sliced hazard field, and consumes that field twice: in a
time-expanded pedestrian router that refuses nodes whose forecast risk will have crossed a
cutoff by the time a slow walker arrives, and in a rescue-ingress calculation that asks
when each approach corridor closes to a vehicle. Its outputs are operator documents, not
maps.

We make three claims and one non-claim.

1. **The coupling changes decisions, and the change is measurable as a paired contrast.** On the canonical Yeongdeok hazard field, 42 of 458 scanned origins reach a refuge only under the forecast-aware policy — a rate on the 32.6 % of that fire's predicted core that the walk network covers, and not a rate for the region as a whole. Both arms run over the same origins, the same network and the same field, so the contrast itself is not contaminated by the routing layer's known approximations or by the coverage limit.
2. **The operating point is weak, and owning that is part of the result.** Read as a classifier at the cut the system actually ships, the spread model recalls 0.138 of igniting cells out of fold, and three of six held-out fires yield zero true positives. A high ranking score and a low detection rate are both true at this prevalence, and the paper reports the pair.
3. **The evaluation design is the transferable part.** Six fires cannot compete with datasets of hundreds [@wildfirespreadts2024; @wstsplus2026; @ndws2022], and we do not try. What six fires permit — and what a large dataset makes easy to skip — is a discipline of matched controls: a flat-terrain control for every terrain result, a column-addition null for every feature-count change, a platform-drift floor beneath every cross-run comparison, a null-hazard control beneath every claim that the fire mattered, and a gate that re-derives each published number from its artifact.

The non-claim is the dispatch ordering. The system ranks rescue targets by how soon their
ingress corridor closes; measured against nearest-first, that ordering wins in 0 of 180
configuration cells at the operating window. We report it, keep it with the finding
attached, and explain the mechanism.

## 2. Related work

**Wildfire spread as a learning problem.** Public benchmarks now train next-day spread
models over hundreds of fires with multi-modal inputs — Next Day Wildfire Spread over
roughly a decade of US observations [@ndws2022], WildfireSpreadTS as a multi-temporal
successor [@wildfirespreadts2024], and the WSTS+ extension, which doubles the unique
years of history and reports that time-series inputs beat single-day inputs
[@wstsplus2026]. Six Korean fires cannot compete on that axis, and the metrics are not
comparable across these settings anyway: label definition, geometry and above all
prevalence differ, and prevalence moves average precision by construction. That line of
work matters here for a different reason — it is part of a turn toward asking whether a
spread model works rather than whether it scores well, which is the question our
evaluation design is built around. Physical modelling supplies the alternative framing:
minimum-travel-time fire growth [@finney2002], and an earlier Rothermel-based surface
model in this project captured a small fraction of the burned area, which is what
motivated the move to a data-driven field.

**Evacuation routing.** Network-flow formulations of evacuation routing are long
established; lane-based evacuation routing was posed as a network flow problem two
decades ago [@cova2003]. Recent work brings wildfire information into that formulation directly:
Borgwardt et al. pose wildfire evacuation as maximum flow on a time-expanded network with
integrated hazard data [@borgwardt2024], and RESCUE routes under stochastic congestion and
uncertain spread [@rescue2026]. Both are vehicle-centric and network-scale. This paper's
layer is neither: it routes individual slow pedestrians from sampled origins to refuges on
a real walk graph, and adds a responder-side ingress term that a maximum-flow objective
has no notion of, because it has no crew driving toward the fire.

**Evacuation triggers and simulation.** The closest conceptual ancestor is the wildfire
evacuation trigger point: a spatial line whose crossing by the fire front should start an
evacuation, set by coupling spread modelling to GIS [@cova2005], refined by reverse
geocoding to name the road segments that matter [@li2017], and later coupled to traffic
simulation so it accounts for the time evacuation itself takes [@li2019]. Trigger geometry
answers *when to leave*; our router answers *which way*, on the same idea that a route's
safety depends on arrival time rather than on the fire's present extent. At community
scale, WUI-NITY couples fire, pedestrian and traffic models into one platform
[@wahlqvist2021]; the wildland-urban-interface framing follows the standard definition
[@radeloff2005].

**Calibration and guarantees.** Conformal risk control offers distribution-free
guarantees on a monotone risk by calibrating a threshold [@angelopoulos2024crc]. Section
4.2 reports what happens when it is applied honestly at six fires, which is that the
finite-sample term consumes most of the error budget; the negative result is the
contribution, not the method.

**Walking speed.** The elderly gait speeds this system assumes sit in the range for
which gait speed is an established predictor of survival in older adults
[@studenski2011]; we use a fixed conservative speed rather than an individualised one,
and sweep it.

## 3. Data and methods

### 3.1 Study fires and public inputs

Six real Korean wildfires form the dataset: Gangneung 2023, Hongseong 2023, Miryang
2022, Uiseong-Andong 2025, Uljin-Samcheok 2022 and Yeongdeok 2025. These are five
independent events plus one co-located pair — Uiseong-Andong 2025 and Yeongdeok 2025
belong to the same March 2025 chain of fires, a dependence Section 6 returns to.

Inputs are public. Active-fire detections come from NASA FIRMS (VIIRS and MODIS)
[@firms], and the detection times define the prediction target. Weather comes from ERA5
reanalysis on single levels [@era5]. Terrain comes from SRTM [@farr2007]. Fuel comes
from ESA WorldCover at 10 m [@worldcover]. Road networks, building footprints and
candidate refuge and depot points of interest come from OpenStreetMap, retrieved and
graph-built with OSMnx [@boeing2017; @osm]. No proprietary or paid source is used, and
the repository distributes no raw data: acquisition scripts and manifests reproduce it.

![System overview. Public inputs feed a per-cell ignition-probability model; its time-sliced hazard field drives a time-expanded pedestrian router and a rescue-ingress calculation; the outputs are operator documents. Every reported number is re-derived from its committed artifact by the registry gate.](figures/F1_system.png)

### 3.2 Spread model and evaluation protocol

The model predicts, for each 500 m grid cell and each satellite overpass, the
probability that the cell is detected as burning at the next overpass. It is a
gradient-boosted tree classifier (`HistGradientBoostingClassifier`) over sixteen
features spanning fire geometry (distance to the nearest prior detection, elevation
above the source), terrain (slope, aspect), fuel (burnable fraction from land cover) and
weather (temperature, relative humidity, vapour-pressure deficit, wind speed, wind
alignment, antecedent precipitation and dryness). The training table holds 151,904 rows
with 2,989 positives, a prevalence of 0.0197; the seed is fixed and the projection is
EPSG:5179.

Evaluation is leave-one-fire-out (leave-one-group-out with the fire as the group): the
model is trained on five fires and scored on the sixth, so no cell of the held-out fire
is in training. Two summaries of the same run are reported, and they are different
quantities that must never be substituted for each other. The **mean of folds** gives
each fire one vote and is reported as the generalisation figure. The **pooled
out-of-fold** AUC scores one ROC over all 151,904 out-of-fold rows, weighting each row
once; it is dominated by the two largest folds, which supply 54.5 % and 27.4 % of the
rows. Fold sizes differ by a factor of 208.9 between the largest and the smallest, and
the smallest fold carries 0.26 % of the rows, so neither summary is neutral:
mean-of-folds over-weights an eight-positive fold, pooled under-weights it to nothing.

Three baselines run through the same folds, features and seed — random forest, logistic
regression and the shipped gradient-boosted model — as a control against the objection
that the model only beats a bad physics model.

### 3.3 Hazard field and time-expanded routing

The classifier's calibrated probabilities are propagated forward into a hazard field: a
stack of time slices, each a grid of P(ignite) values, covering 0 to 720 minutes from
the trigger in 180-minute steps on the canonical Yeongdeok field. This field is the
single object both downstream layers consume.

The pedestrian router is a Dijkstra search over a time-expanded state `(node, time bin)`
on the OpenStreetMap walking graph, at a fixed elderly gait speed of 0.7 m/s adjusted
for slope, with a 10-minute time bin and a 600-minute travel budget. An edge is
admissible only if the hazard at its head node, read at the arrival time rounded up to
the next bin, is below a pedestrian cutoff of 0.5; among admissible paths the search
minimises cumulative exposure, the integral of P(ignite) over travel time. Two policies
are compared over identical origins: a **fire-blind** policy that takes the
shortest-distance route to the nearest refuge and never consults the hazard, and a
**forecast-aware** policy that applies the cutoff and the exposure objective. Origins
are sampled by walking the graph's node list at a fixed stride of 18; they are sampled
walk-network locations, not households, and are never described as households anywhere
in this paper.

Section 6 records four limitations of this router, found by reading its mathematics
against its documentation and deliberately not fixed, because every committed count was
produced by the code as it stands. All of them divide out of a paired contrast: both
arms run through the same scoring function on the same field.

### 3.4 Rescue ingress and dispatch

Residents who cannot self-evacuate need a crew, and a crew driving toward a fire faces
the mirror-image problem. For each home the responder route is computed on the
OpenStreetMap driving graph from the nearest mapped depot and sampled into points; the
**ingress survival time** is the earliest forecast slice at which any sampled point
reaches a separate, higher vehicle cutoff of 0.7. A home is dispatchable if that time
exceeds the responder's estimated arrival — dispatch delay plus travel time — by a
safety margin. The four-way outcome partitions the origin set exactly and the
unreachable class is reported, never imputed: on the committed run of 439 origins, 272
are self-sufficient and 167 need a rescuer, of whom 143 are dispatchable and 24 have no
surviving vehicle ingress. An assumed immobile fraction of 0.3 drives the split and is
swept.

The system's shipped dispatch ordering ranks dispatchable homes by urgency — ingress
survival minus responder arrival, smallest closing window first. Section 4.6 measures
that ordering against nearest-first, earliest-closure, unsorted scan order and 200
random permutations, across a grid of operational window, on-scene service time,
dispatch delay and team count.

### 3.5 Controls, sweeps and the evidence registry

Every result below is accompanied by at least one of five kinds of control, each of
which exists because an earlier version of this project made a claim that one of them
later removed.

- **A flat-terrain control** beside every slope result. With flat timing, edge time is proportional to length, so a distance-ranked router must produce identical routes; a non-zero flat control means the pipeline, not the terrain, moved.
- **A column-addition null** beside every experiment that changes the feature count. Adding two columns of pure noise to the sixteen raises pooled AUC by +0.0041 on average over 60 draws, with a 95th percentile of +0.0093; on far-band AUC the same null spans -0.0363 to +0.0425. An arm that changes feature count must clear that envelope, not zero.
- **A platform-drift floor** beneath every cross-run comparison. Re-running the committed protocol on a second machine moves pooled AUC by 0.0064 and far-band AUC by 0.0307; differences below those are not measurements.
- **A null-hazard control** beneath every claim that the fire changed an outcome, implemented as an identically-zero hazard field.
- **Sweeps rather than defaults** for the parameters that carry the most weight: the evacuation-time budget, the slope sampling interval, the immobile fraction, the vehicle cutoff, the dispatch delay and the forecast-perturbation magnitude.

The registry makes the rest checkable. Each publishable value has an entry in
`docs/NUMBERS.json` naming its source artifact, its JSON path, the expression that
re-derives it, its caveat, and the phrasings that misstate it; a gate re-derives every
entry on every change, scans the prose for retired figures and quantity-name collisions,
and refuses a document that states a registered quantity with a different value.
Superseded values are annotated in place, never deleted, and withdrawn claims stay in
the tree as withdrawn. This manuscript is scanned by that gate like any other document
here.

## 4. Results

### 4.1 Held-out spread skill

Under leave-one-fire-out cross-validation the mean of the six held-out ROC-AUC values is
0.890, with a sample standard deviation across folds of 0.107 and a range of 0.682 to
0.974 (Fig. 2). The pooled out-of-fold AUC over all 151,904 rows is 0.905. These are
different quantities and the difference is structural rather than cosmetic: pooled is
row-weighted, so it is effectively an average over the two largest fires, while
mean-of-folds gives Gangneung 2023 — 396 rows, 8 igniting cells, 0.26 % of the evidence
— the same vote as Uiseong-Andong 2025 with 82,736 rows. The weakest fold is the
smallest one, and any single-number headline hides it.

![Held-out ROC-AUC per fire under leave-one-fire-out cross-validation. The dashed line is the mean of folds; the dotted line is the pooled out-of-fold AUC, a different quantity that weights each row once and is therefore dominated by the two largest fires.](figures/F2_lofo_auc.png)

Standard baselines over the same folds, features and seed do not establish the shipped
model as the most accurate one, and we say so.

Table 1. Baselines over the same six leave-one-fire-out folds, the same sixteen features and the same seed. Hyperparameters are untuned. ⚠ Lineage: these rows were produced on the corrected-DEM bundle, which is why the shipped model reads 0.8943 here against the committed headline's 0.890 in the text — the same model on a different, deliberately not-adopted lineage, not a second estimate of the same quantity. Read the ordering, not the gap: the shipped model leads on pooled AUC (0.9036 against 0.8963) and trails on mean-of-folds, and calibration does not separate it from the random forest either. That pooled gap is 0.0073, barely clear of this project's own 0.0064 platform-drift floor, so it is an ordering that reproduces across both lineages rather than a measured margin.

| model | mean-of-folds AUC | fold sd | pooled Brier | pooled ECE |
|---|---:|---:|---:|---:|
| Random forest | 0.9142 | 0.0437 | 0.0174 | 0.0068 |
| Logistic regression | 0.9028 | 0.0605 | — | — |
| Gradient-boosted trees (shipped) | 0.8943 | 0.0924 | 0.0183 | 0.0086 |

The measured reasons for shipping the gradient-boosted model are therefore pooled-AUC
advantage, inference speed, native handling of missing values and the availability of
permutation importances — not calibration and not mean-of-folds accuracy. An earlier
version of this project justified the choice by a finding that fire-weather severity
dominates wind direction by a large ratio in permutation importance. That claim has been
**withdrawn** and is described here only as withdrawn: it compared the sum of six
features against a single variable, and ERA5's 0.25° grid does not resolve the local
winds the comparison concerned. The underlying measurement is retained in the repository
with its limits.

Two further results bear on how much of this skill is real. Correcting a defective
digital elevation model that had filled the East Sea with a ramp to -497 m across half
of one fire's raster — and which, because training pools all six fires, was training
data for every fold — moves mean-of-folds by +0.0048 and pooled by -0.0017. Two
summaries of one re-run disagreeing in sign is the honest reading, and it is why that
lineage was not adopted; the far-band figure moves by -0.0358, the largest correction in
the number set and the reason far-band values must always carry their lineage.
Separately, an arm adding two directional terrain features sits at the 66.7th percentile
of the column-addition null on pooled AUC — inside the noise of adding any two columns.
It exceeds all 60 noise draws on mean-of-folds, but excluding the 8-positive fold that
supplies the gain leaves -0.0002: the exceedance was a fold, not a finding.

### 4.2 The operating point, and why no threshold guarantee is available

A ranking metric is not an operating point, and the question a technical reviewer asks
next is what the system does at the threshold it ships. It is weak, and Fig. 3 states it
plainly.

![Operating point of the spread model. Left: held-out cell recall at the shipped 0.3 advance threshold, per fire, with each fold's igniting-cell count; on Gangneung 2023 and Hongseong 2023 no cell anywhere in the fold reaches 0.3, so the threshold can produce neither a true nor a false positive. Right: the pooled out-of-fold precision-recall curve against the no-skill prevalence baseline, with the shipped cut marked.](figures/F4_operating_point.png)

At the 0.3 advance threshold the pooled out-of-fold recall is 0.138 — 412 true positives
among 2,989 igniting cells — with precision 0.308 and F1 0.19. The unweighted mean of
the six per-fold recalls is 0.0867, and the gap has a structural cause: three of the six
folds have exactly zero true positives at 0.3. On two of those the threshold is not
merely unmet but unreachable, the largest out-of-fold probability anywhere in the fold
being 0.0241 at Gangneung 2023 and 0.296 at Hongseong 2023; on the third, Miryang 2022,
two cells exceed 0.3 and neither ignites. Average precision over the full ranking is
0.169 against a no-skill baseline of 0.0197, which is 8.6 times chance and is not
comparable to published average-precision figures on other benchmarks, whose label
definitions, geometry and prevalence all differ.

Two clarifications travel with these numbers. First, 0.3 is a configuration default
never tuned on these probabilities; the F1-maximising threshold on the same data is
0.14, recorded in the artifact and deliberately not adopted, because a threshold chosen
on the probabilities it is scored on is optimistically biased. Second, this recall is
**not** the router's miss rate: it is a per-simulation-step cut on the classifier's
output, whereas the router thresholds the cumulative, survival-accumulated field at 0.5
— different surfaces, different cuts.

The natural next move is to calibrate the threshold with a distribution-free guarantee
[@angelopoulos2024crc]. Done honestly at six fires it produces a negative result. With
five calibration fires the finite-sample correction is 1/(n+1) = 0.167, consuming 0.833
of a 0.20 false-negative-rate budget. Under the naive convention the bound holds on 3 of
6 held-out fires, worst held-out rate 0.75, and a satisfying threshold flags 9.9 % to
18.5 % of all cells. Under the conformal convention it holds on 6 of 6, worst rate
0.108, but flags 26.0 % to 45.6 % of the map — against a 1.97 % prevalence.
Exchangeability breaks twice besides: the held-out fire's probabilities come from a
model trained on the fires used to calibrate, and a fire-level finite-sample term is
applied to a cell-level quantile. No threshold computed here is adopted; the operating
point stays at 0.3, and the reason is now stated rather than defaulted.

### 4.3 What the forecast changes about who can walk out

The routing contrast is where the coupling earns its place. On the canonical Yeongdeok
hazard field, 458 origins are scanned; the fire-blind route reaches a refuge without
entering the predicted hazard for 414 of them, and enters the hazard for 44. Of those
44, the forecast-aware router brings 42 to a refuge without entering the hazard, and
finds no route at all for 2 (Fig. 4). No origin falls into the budget-exceeded class at
600 minutes, and no origin enters the hazard under the forecast-aware policy, which is
structural: the policy refuses any node at or above the cutoff.

![Decision shift on the canonical Yeongdeok field. Left: the same 458 scanned origins under the fire-blind and the forecast-aware policies. Right: the predicted hazard core over the forecast horizon. The absolute rates on the left are computed on a walk network covering 32.6 % of the predicted fire core; the remaining two thirds are unmeasured and the direction of the bias is unknown.](figures/F5_decision_shift.png)

Three caveats are inseparable from those counts. **First and most important, they are
rates on a covered third.** Yeongdeok's walk-network bounding box contains only 32.6 %
of the grid cells at P(ignite) ≥ 0.5 in the field's final slice; the western part of the
predicted core has no road network in the box at all. The origins are a spatially biased
sample, the bias is real, and its direction is unmeasured. Every absolute Yeongdeok rate
here carries that caveat, and not re-acquiring the region is deliberate: the box does
not fit the simulation grid, so redrawing it would force re-extending the canvas and
re-simulating the field, replacing a stated limit with an unstated one. Paired contrasts
are unaffected, since both arms use the same origins. **Second, the field itself was
reconstructed.** An earlier lineage of these counts came from the surviving output of a
run reverted the next day; the "quasi-static fire core" limitation recorded against
those numbers was a property of that reverted field, not of the fire. On the canonical
field the core grows by 316.06 % from the first slice to the last. The two lineages
differ on more than one axis at once, so the movement between them is not a
single-variable contrast and no per-origin ledger exists for that pair. **Third, these
are sampled walk-network origins, not households.**

### 4.4 Three regions under one rule

The same rule, parameters and stride were applied to two further regions acquired
identically (Fig. 5, Table 2).

![Three-region routing partition, as a share of scanned origins, with each region's walk-network coverage of its own predicted fire core beside its name. The three regions must not be ranked on the orange band alone: n = 3 and the covariates in Table 2 move together.](figures/F3_regions.png)

Table 2. Three regions under one identical rule. The right-hand columns are the covariates that must travel with any cross-region statement: OpenStreetMap mapping density and the share of each region's own predicted fire core that its walk-network box actually contains. Densities are over the geodesic bounding-box area. Depot density is a statement about what OpenStreetMap maps, not about where fire stations are.

| region | origins | safe on both | safe only forecast-aware | no safe route | over budget | core coverage | core area (ha) | road km/km² | nodes/km² | refuge POIs/100 km² | depot POIs/100 km² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Yeongdeok 2025 | 458 | 414 | 42 | 2 | 0 | 32.6 % | 25,900 | 1.803 | 9.43 | 5.58 | 0.45 |
| Uiseong-Andong 2025 | 368 | 263 | 91 | 12 | 2 | 99.2 % | 3,275 | 2.39 | 7.45 | 3.79 | 0.00 |
| Uljin-Samcheok 2022 | 393 | 377 | 3 | 10 | 3 | 81.5 % | 7,300 | 1.663 | 8.21 | 2.92 | 0.45 |

The forecast-aware-only share is 9.17 %, 24.73 % and 0.76 %. **These three rows must not
be ranked against each other on that column.** With n = 3, coverage, core area and
mapping density all move together; the predicted-core areas span a factor of 7.91 under
one definition, and one region's rate is computed on a third of its own core. The one
ordering that does carry information runs against the naive reading: the Spearman rank
statistic relating a region's core growth to its share of origins safe on the
forecast-aware route alone is -0.5 over three regions. With n = 3 that is an ordering,
not an association: it has no p-value and none is claimed. The
mechanism is visible in a second quantity — of the origins whose fire-blind route is
unsafe, the share the forecast-aware router still gets to a refuge is 0.955, 0.883 and
0.231 across the three regions. Where the core advances fastest, unsafe origins fall
into "no safe route" instead of into the forecast-aware bucket. A headline share alone
would have hidden that, which is why both are reported.

One region has no `amenity=fire_station` mapped in OpenStreetMap inside its 896.5 km²
walk box, though the wider acquisition box for the same region contains six. Its responder side is
therefore recorded as not applicable, never as zero dispatches, and the cross-region
metric above is resident-side and unaffected.

### 4.5 Sensitivity and controls

![Sensitivity on the canonical Yeongdeok field. Left: the share of origins whose fire-blind route fails, against the evacuation-time budget, with a flat-timing control. Centre: origins safe only on the forecast-aware route, against the slope-sampling interval, with a flat control. Right: peak P(ignite) along the two committed routes as the forecast field is dilated, with the pedestrian cutoff and the radius at which the forecast-aware route first crosses it.](figures/F6_sensitivity.png)

**The evacuation-time budget is the binding assumption, not the terrain.** Sweeping the
budget on the canonical field, the share of origins whose fire-blind route fails rises
from 0.0961 at 600 minutes to 0.5655 at 30 minutes, a ratio of 5.89; at 120 minutes it
is 0.2227 and at 60 minutes 0.4017. The 600-minute default, in other words, was
concealing the operational picture, and a short-budget failure share is meaningless
without its budget attached. The forecast-aware router never exceeds the 600-minute
budget at Yeongdeok — that class is empty — because a budget failure is a walk-time
failure, and walk time is a property of the graph and the terrain, neither of which the
fire changes.

The count of fire-blind routes that enter the predicted hazard rises from 20 to 44
between the reverted and the canonical fields. That number belongs to the **fire-blind
baseline**, not to the proposed system: the forecast-aware router cannot enter the
hazard at all, and a fire-blind walk is likelier to walk into a fire four times larger.
It is evidence for a hazard-aware routing layer, not a cost of one.

**Terrain changes how people walk, not whether they arrive.** Applying real slope to
edge times raises whole-network traversal time by 26.6 % at Yeongdeok at 60 m sampling
(15.14 % and 23.67 % in the two other regions), with a mean absolute gradient of 0.0818
and a mean directional asymmetry of 0.1996 of flat time — which is why the walking graph
is directed. Yet the classification barely moves: 42 origins are safe only on the
forecast-aware route at 30 m and 60 m sampling and 41 at 90 m, against 41 in the flat
control, and the number whose bucket differs from the flat control at all three
intervals is **zero**. Three move at some interval and none at all three, tracking the
sampling-induced time penalty rather than the terrain, while 179 forecast-aware routes —
39.1 % — differ from the flat control at 60 m. Terrain does real work on the paths and
none on the verdicts: a null result about this instrument, not about slope. Switching
the objective from distance to time under slope timing changes 150 of 458 routes and
cuts the longest single walk from 444.0 to 352.8 minutes, a saving of 91.3 minutes for
one worst-case origin; the flat control changes 0 routes, as it must, so the mechanism
is identified rather than inferred.

**Forecast error has a characterised failure mode, not robustness.** Perturbing the
hazard field, the forecast-aware route's exposure is below the fire-blind route's in 86
% of 2,000 Monte-Carlo draws, but the safety margin itself is fragile: under a
morphological dilation of the field the forecast-aware route's peak risk first reaches
the 0.5 cutoff at a dilation radius of 125 m, and an independent spatial-translation axis
first breaks at that same 125 m — but 125 m is the minimum over eight directions and the
band runs to 530 m, so the margin's fragility is strongly direction-dependent. A quarter
of one grid cell of forecast error in the worst direction is enough to invalidate it.
These two axes and the Monte-Carlo figure come from `forecast_robustness.json` and
`dilation_perturbation.json`; they are committed artifact values that do not yet carry
registry keys of their own, and are flagged here as such. This is stated as a risk reduction with a measured
breaking point rather than as robustness.

**The road network itself is a source of uncertainty.** Re-acquiring the OpenStreetMap
network eleven months later changed the walk-graph node count by 0.0474 % and moved the
count of origins with no surviving vehicle ingress by 33.3 % (24 to 32), while the
paired exposure-reduction contrast moved by 0.5614 percentage points. Neither network is
the right one; the reported quantity is sensitivity. Binary verdicts are network-fragile
and paired contrasts are not — the strongest argument in this paper for reporting
contrasts.

### 4.6 Rescue ingress, and a dispatch ordering that does not work

On the committed 439-origin responder run, survival-aware responder routing reduces mean
responder exposure from 6.12 to 1.71 probability-minutes over the 143 dispatchable
origins, a 72.0 % reduction. This is a relative contrast between two routing policies on
the same hazard field on the responder side only; it is not an absolute safety
guarantee, and 57 of the 143 shortest-path routes cross the hazard, which is what the
survival-aware policy is avoiding.

The dispatch ordering is a different story, and the honest report of it is negative. Its
lineage has to be stated before its numbers, because it is not the lineage of the
paragraph above: the ordering grid was measured on a re-acquired network vintage rather
than the committed 439-origin series, two of its four arms use a synthetic hazard and
terrain, and it runs a travel-aware occupancy rule in which a team stays occupied for its
return leg — a rule the shipped triage code does not use, and without which the number
rescued is teams times slots and no ordering can differ from any other. What follows is
therefore a contrast between orderings under that rule, on those arms; it is not a
rescue-capacity forecast for any region and carries no lives-saved reading. "Homes" here
is shorthand for the sampled walk-graph origins of Section 3.3, not dwellings.

![Dispatch ordering. Left: homes reached within the operational window against the number of rescue teams, at the committed operating cell, for the shipped deadline-first ordering and four alternatives including 200 random permutations. Right: win, tie and loss tally of deadline-first against nearest-first across 180 configuration cells per window. The second window is exploratory and more than three times the committed one.](figures/F7_dispatch_ordering.png)

Across 360 headline configuration cells — four arms by two windows by three service
times by three dispatch delays by five team counts — the shipped deadline-first ordering
rescues more than nearest-first in 3.6 % of cells, ties in 36.7 % and loses in 59.7 %.
Every one of the 13 wins occurs at the exploratory 240-minute window; at the committed
75-minute window it wins **0 of 180** cells, with 88 ties and 92 losses. At the single
most operationally relevant cell — the committed window, 25-minute service, 30-minute
delay, eight teams — deadline-first reaches 19 homes against nearest-first's 24, a gap
of -5; unsorted scan order reaches 16 and 200 random permutations average 16.49 ± 1.69,
so the sort does beat no sort, and it is nearest-first it loses to. The worst cell in
the grid is -31, and in that cell the shipped ordering falls below an arbitrary order as
well.

The mechanism is measured rather than guessed. The urgency key is corridor closure minus
responder arrival, and at the committed window the window closes before most corridors
do, so the number of distinct deadline values is tiny: 2 over 116 homes in one arm, 6
over 142 in another. With two distinct deadlines the key is nearly constant and any sort
of it is a sort of noise — a property of the window relative to the closure times, not a
defect in the sort.

Widening the operational-window axis to 600 minutes does not rescue the ordering. Over
2,160 cells on a twelve-point axis from 60 to 600 minutes, deadline-first loses in 68.7 %
of cells, ties in 26.0 % and wins in 5.3 %; it beats unsorted order in only 31.5 % of
cells and the random mean in 37.8 %. The lowest window at which it wins any cell is 120
minutes and the highest non-winning window is 600, so the two regions overlap completely
and no window threshold separates them; nor does the number of distinct deadlines, where
1,580 cells fail to win despite having at least as many as the lowest-scoring winning
cell. There is no operating region in which the shipped ordering can be recommended, and
the paper does not construct one. The one thing this
analysis does establish positively is reproducibility: re-deriving 3,744 values from the
earlier run of this experiment cell by cell produced **0** differences.

## 5. Discussion

**What the coupling adds over a spread map.** A hazard map answers "where will the fire
be". A household needs "is my route still passable when I get there", and those differ
because a slow walker's arrival time is a variable in the answer. The measurable form of
that difference is Section 4.3: for 42 of 458 origins on the covered third of that fire's
predicted core, consulting the forecast is what separates reaching a refuge from walking
into the predicted fire. The same field answers the responder's mirror-image question at
no extra cost, since it is computed once and read twice. That is why the contribution is
stated as a coupling rather than as a model.

**Where the weak operating point bites.** The router does not consume the classifier as
a detector: it consumes a calibrated probability surface and cuts a cumulative,
survival-accumulated version of it at a different threshold, so ranking quality is the
property it needs. What the weak operating point does undermine is the inference a reader
might otherwise draw — that the system knows where the fire will be. It does not, at any
usable per-cell precision, and three of six fires would produce no advance flag at all
under the shipped step threshold. This is also why the first limitation in Section 6 is
that the 42 is graded against the predicted field rather than against observed burn.

**Why n = 6 forbids a threshold guarantee.** Section 4.2's conformal analysis is the
most transferable negative result here. The intuition that a distribution-free method
rescues a small-sample setting is wrong in a specific, quantifiable way: at six fires the
finite-sample term alone eats five sixths of a 20 % error budget, and the threshold that
satisfies the bound paints between a quarter and a half of the map. Small-N event datasets
do not get guarantees by changing the calibration method; they get them by having more
events.

**Why the negative dispatch result is worth keeping.** The ordering is a designed
feature that does not work, measured against four alternatives including chance, and the
mechanism — a near-degenerate sort key when the operational window closes before the
corridors do — is itself a finding about dispatch in this regime. Removing it would delete
the evidence; the system keeps it with the finding attached.

**The instrument is the contribution.** Several results here exist only because a control
existed: the terrain null survives because of the flat control, the feature-arm null
because of the column-addition envelope, and the claim that distance drives vulnerability
was **withdrawn** because a null-hazard control showed the failing set was set-identical
with no fire at all. On a six-event dataset, a registry that re-derives every number and
keeps withdrawn claims in the tree is what separates a result from a coincidence.

[GAP: structured expert consultations with a fire-service duty officer, a village head
and a social worker are planned in the project's consultation format; they are design
feedback, not collected data, and require the author's consent handling before any
quotation appears here]

## 6. Limitations

**The routing result is graded against the predicted field, not against observed
burn.** This is the objection we would raise first against this paper. An origin counted
in the 42 is one whose fire-blind route crosses a cell the *model* flagged and whose
forecast-aware route does not. That is a statement about the two policies read on one
surface; it is not a statement that the fire went where the surface said. Given Section
4.2's operating point, the same evidence is consistent with some of the 42 being detoured
around cells that never burned, while cells that did burn and were never flagged sit
unavoided under both policies. Every control in this paper perturbs the predicted field —
dilation, translation, the null-hazard arm, the Monte-Carlo draws — so none of them admits
external truth, and the paired contrast controls for the router while leaving the field
unchecked. [GAP: the arm that settles this is a third routing pass over the same 458
origins on a hindsight field rasterised from the observed FIRMS detections for this fire,
reporting how many of the 42 fire-blind routes actually intersect observed burn inside the
walker's arrival window. The acquisition manifest for those 2,290 detections is committed
and records the observation span, but the detections themselves live under a git-ignored
raw bundle that does not travel with the repository, so the arm needs the author's laptop]

**Six fires, and not six independent ones.** Uiseong-Andong 2025 and Yeongdeok 2025
belong to the same March 2025 chain, so the dataset is five independent events plus a
co-located pair. The Yeongdeok fold's training data may contain cells of the same fire
complex, and a leak-free refit of that fold has not been run. [GAP: the leak-free
Yeongdeok fold and the hindsight-oracle arm — refitting the Yeongdeok fold with the
co-located fire excluded, re-simulating its field, and routing the same 458 origins on
the original, leak-free and hindsight fields — require the raw acquisition bundle, which
is not distributed with the repository; this is the single experiment most likely to
move the 42-origin result and it is planned before submission]

**Coverage.** Every absolute Yeongdeok rate is computed on a walk network containing
32.6 % of that fire's predicted core. The bias is established and its direction is not.

**Origins are not households.** They are walk-graph nodes at a fixed stride, so their
distribution reflects road-network structure. Where building footprints were used
instead, OpenStreetMap's coverage of rural Korean buildings is a small and
region-dependent fraction of the real stock — 124, 339 and 1,220 mapped footprints
across the three regions — and 91.5 % of 1 km cells containing built-up land at
Yeongdeok contain no mapped building at all. Origins needing rescue are 2.13 times more
dispersed than origins in general, and 69.2 % of clusters at a 500 m radius hold a
single point, so village-level broadcast has no audience at most of them; both figures
describe the sample, not the region.

**Weather resolution.** ERA5's 0.25° (~28 km) grid means the severity features are
nearly uniform within a fire at a time step: they discriminate between fires and days,
not between cells within an overpass. This is the measured reason the
severity-versus-direction claim was withdrawn, and it bounds what any wind-direction
feature in this model can be shown to do. The cost of moving to a real forecast source
is bounded but not measured: permuting the six swappable instantaneous weather features
costs 0.0344 of far-band AUC, which is a ceiling on the cost of the swap rather than a
measurement of it, and no forecast data was acquired.

**The top feature is partly an acquisition artifact.** Days-since-rain ranks first by
permutation importance, yet removing it *raises* mean-of-folds by 0.0270 and far-band by
0.0533, because for three of six fires the ERA5 window contains no wet sample and the
feature is pinned to the window's start — an acquisition parameter acting as a per-fire
fingerprint. This is a statement about the feature as computed, not about dryness.

**The 500 m grid attenuates terrain.** Native ~30 m effective slope is 3.01 times the
500 m-baseline slope pooled over the six fires, with a native mean of 17.3°, so the grid
the model sees hides roughly two thirds of the terrain. Direction analyses inherit this:
the observed spread bearing sits 83.5° from the ERA5 wind bearing, where 90° is what
unrelated bearings give, and upslope agreement is 51.8° on steep steps against 88.4° on
gentle ones — terrain explains direction where terrain is steep and not where it is
flat.

**Router approximations, recorded and not fixed.** The objective the router minimises
samples risk at the edge head at a rounded arrival time, while the reported exposure
samples at the tail at the exact departure time; on a constructed example the optimiser can
prefer a path whose *reported* exposure is 2.22 times the alternative's. Remaining-time
displays are quantised to the field's slice grid and are an upper bound. The time-expanded
search is deterministic but not provably optimal over exact-clock paths, though no
counterexample exists at the bin sizes in use. The class named "forecast-aware route
exceeds budget" names a cause its code condition does not establish; it is empty at
Yeongdeok, and elsewhere the correct wording is that the search did not complete within the
scan's constraints. None was fixed, because every committed count was produced by this code
— and all of them divide out of the paired contrasts this paper leads with.

**Assumptions the results ride on.** A fixed 0.7 m/s gait speed with no individual
variation and no pre-movement delay; an immobile fraction of 0.3; a pedestrian cutoff of
0.5 and a vehicle cutoff of 0.7; dispatch service times and team counts that are
proof-of-concept parameters, not measured fire-service capacity; and refuge semantics from
OpenStreetMap tags, which in rural Korea return parks and open-sided pavilions unless the
query is corrected for the local tagging of village halls.

**Operational status.** No trigger has ever fired on a live detection, and the messaging
layer is a dry run: the SMS path is simulated, private cell-broadcast origination is not
lawful in Korea, and the approval-gated email channel has never completed a verification
send. Nothing here was deployed to a real resident or a real crew.

## 7. Conclusion

A wildfire spread model trained on six fires is not a contribution to spread modelling,
and this paper does not present it as one. What six real fires, real road networks and a
strict evidence discipline do support is a different claim: that coupling an
event-held-out probability field into a time-expanded pedestrian router and a
rescue-ingress calculation changes household-level decisions in a way that can be
measured as a paired contrast — 42 of 458 scanned origins on the canonical Yeongdeok
field reach a refuge only under the forecast-aware policy, on a network covering 32.6 %
of that fire's predicted core — and that the same field answers the responder's
mirror-image question at no extra cost.

The rest of the contribution is the instrument. The weak operating point is reported
rather than hidden; the conformal calibration is reported as vacuous at this sample size
rather than dressed as a guarantee; the shipped dispatch ordering is reported as losing
to nearest-first with its mechanism explained; and the claims this project has withdrawn
stay in the tree as withdrawn. On an event dataset this small, matched controls and a
registry that re-derives every published number are not process overhead. They are the
difference between a result and a coincidence, and they are the part of this work that
transfers to the next small-N evaluation.

## Data and code availability

The code, committed artifacts, evidence registry and this manuscript are at
https://github.com/Sparkxt-0318/wildfireguardian. Raw geospatial inputs are public and
are re-acquired by the scripts in `scripts/`; the repository distributes no raw data.
Every number in this paper is registered in `docs/NUMBERS.json` with its source
artifact, derivation and caveat, and is re-derived from that artifact by `make verify`.
Figures are regenerated deterministically from committed artifacts by
`paper/make_figures.py`; no figure was edited by hand. Authorship and the disclosure of
agent-assisted drafting are recorded in `paper/AUTHORSHIP.md`.
