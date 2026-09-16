# Roads direction, pre-registration

**Status: draft v0.1, written 2026-09-16 by A3. Nothing is fitted. No data is
downloaded. Every number below is a pre-registered decision threshold, a prior,
or a planning estimate, and none of them is a result.** This document is written
to be signed by A6 (task T2.3) before any labelling or fitting begins. Once it is
signed it is frozen; changes after the signature are versioned (v0.2, ...) and
every later output names the version it was produced under. See section 16.

Direction 1 of the research program (`research/README.md`). The hypothesis is
`H-ROADS` in `research/FORBIDDEN_CLAIMS.md`, and the claims discipline of that
file governs every sentence here.

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
| F1 | under the primary specification, and with the width gates W1 and M1 of section 11 met, the posterior mass `P(beta_width < 0)` does not reach 0.90 **in the errors-in-variables fit of section 6.3.4** | the width term is reported as not distinguishable from zero on this record, with its interval and with the attenuation factor `kappa`, and the breach curve is published flat |
| F2 | the width-only logistic baseline B1 (section 9) equals or beats the structured model in mean out-of-complex log score in 2 or more of the 5 folds, or the mean difference falls below the margin of section 10.4 | B1 is reported as the model of record, and the finding is that the added physics structure buys nothing measurable on this record |
| F3 | the posterior contrast between the breach curve at 6 m and at 3 m has a credible interval that spans both directions | the study reports that this record does not separate the two widths, which is a legitimate outcome and is not evidence for either side of the claim under test |
| F4 | the ember jump parameters have posterior standard deviations above 0.8 times their prior standard deviations | the ember arm is reported as not identified, the distance distribution is published descriptively only, and the combined breach model is withdrawn in favour of the flame-crossing arm alone |
| F5 | the feasibility gates of section 11 are not met | the round delivers the labelled dataset, the descriptive tables and the bounding analysis, and records the design as untestable on this record |

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
public roads that cross forest. Only barriers whose source edition predates the
fire are used; an edition-date check is a hard precondition, because a road built
after the fire that appears in a current layer would be scored as a barrier that
did not exist.

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
width zero and act purely through the slope reversal at the crest. That is the
point: ridges identify the slope-direction term separately from the width term,
which roads on their own cannot do.

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

## 4. What "the fire front reached it" means

This is the definition that separates an encounter from "the fire was somewhere
in the neighbourhood". A segment is an **encounter** only when all four
conditions C1 to C4 below hold. Anything less is not an encounter, and the segment leaves
the study before it is ever labelled.

### 4.1 C1, the windward side is burned right up to the barrier

The fraction of usable pixels in the windward analysis band (section 5.3) with
dNBR at or above the burned threshold is at least 0.80. The front has to have
consumed the fuel up to the barrier edge, not merely passed within sight of it.

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
the common-cadence run of section 2.3 can subset them.

### 4.4 C4, the encounter can be timed

A local arrival-time fit (section 6.4) succeeds at the segment: at least 5
detections within 1 km spanning at least 2 distinct acquisition times. Without
this there is no approach angle, no spread rate and therefore no intensity, and
the encounter cannot carry the model's covariates.

### 4.5 Eligibility, applied before labelling

A segment is **ineligible**, and is counted and reported as such rather than
silently dropped, when:

- the lee-side band is not burnable (open water, bare rock, built-up area,
  actively cultivated land, or non-stocked forest), because "it did not burn" there
  says nothing about the barrier;
- fewer than 60 per cent of the pixels in either band are usable under section 5.2;
- the barrier's source edition postdates the fire;
- the segment's own width is unknown and cannot be assigned even a class-level
  prior under section 6.3.

Ineligible counts are published per fire and per reason. They are part of the
result, because the size of the eligible set is the main thing that decides
whether this design can say anything at all.

---

## 5. The pre-registered labels

Two people following this section must put the same segment in the same box. That
is the bar this section has to clear.

### 5.1 Which side is which

The **windward side** is the side the front arrived from, taken from the local
arrival-time fit of section 6.4 as the side with the earlier fitted arrival time.
It is not taken from wind direction, because a fire in Korean terrain runs
upslope against the surface wind often enough that wind alone would mislabel
sides. The **lee side** is the other one. If the two sides' fitted arrival times
differ by less than the fit's own standard error, the side assignment fails and
the segment is indeterminate with reason `SIDE`.

### 5.2 Scene selection, and what makes a pixel usable

- **Initial assessment, not extended.** Korean spring fires are followed by fast
  greenup, so an extended assessment would mix regrowth into the severity signal.
  The post-fire scene is the earliest scene at or after containment with a usable
  fraction of at least 0.70 over the fire's bounding box, and no later than 30
  days after containment. The pre-fire scene is the latest usable scene before
  ignition, no earlier than 60 days before it.
- **Where the containment time comes from, and the 2019 problem.** A1 has verified
  that `kfs_fire_stats_csv` covers report years 2022 to 2025 only, so it does not
  reach Goseong 2019. The containment time is taken from
  `kfs_fire_state_history_csv` where that file covers the fire, and otherwise from
  the active-fire record itself: the last detection inside the fire's acquisition
  box, plus a 24 hour margin. This substitution is pre-registered now rather than
  improvised later, it applies to any fire without a KFS containment record, and
  the source of the containment time is recorded as a column per fire. Note that
  the scoring clock of this direction was never the KFS report time: arrival times
  come from the detection record (section 6.4), so the KFS files affect scene
  selection only.
- If no scene pair satisfies both windows, the whole fire's segments are
  indeterminate with reason `SCENE`, and this is reported as a fire-level
  exclusion, not as a set of missing rows.
- A pixel is **usable** when the Sentinel-2 L2A scene classification does not mark
  it as cloud medium probability, cloud high probability, thin cirrus, cloud
  shadow, snow, saturated or no-data, in **either** the pre or the post scene, and
  when it is not inside the smoke mask. A pixel that is usable in one scene and
  not the other cannot contribute a difference and is not usable.
- Smoke is the one that will bite, because the post-fire scene is taken as early
  as possible and Korean spring fires smoulder. The smoke mask rule is a pending
  item in `OPEN_QUESTIONS.md` and must be settled before the signature.

### 5.3 The buffer geometry, and where the distances come from

Distances are measured from the **barrier edge**, not from the centreline. The
edge is the centreline offset by half the barrier width from section 6.3.

- **Inner exclusion, 10 m.** Discarded on each side. A 20 m NBR pixel straddling a
  road edge mixes bare running surface with vegetation, and mixed pixels dilute the
  difference in both directions. Ten metres removes the worst of them.
- **Analysis band, 10 m to 50 m from the barrier edge, on each side.** Forty
  metres gives two full rows of 20 m pixels, and about 10 pixels per side per 100 m
  segment.
- **Why the band stops at 50 m.** This is the boundary between the two model
  components and it is deliberate. A lee-side burn inside 50 m is treated as flame
  crossing. A lee-side burn beyond 50 m that is not connected to the barrier edge
  is treated as spotting and is measured by the ember arm (section 7.3). Setting
  one boundary for both components is what stops the same event being counted
  twice, once in each arm of a model whose whole form is a product of the two.

### 5.4 dNBR, RdNBR, and the two sides having different fuel

- dNBR is pre-fire NBR minus post-fire NBR, on the scene pair of section 5.2,
  after reprojection to EPSG:5186.
- The **burned threshold** `tau_burn` is 0.10, the low-severity break point of the
  Key and Benson FIREMON scheme. That scheme is prior art from outside Korea and
  is used here as the source of a method, never as a source of data. Whether those
  break points transfer to Korean pine and mixed stands is an open question, and
  a sensitivity analysis over `tau_burn` in {0.05, 0.10, 0.15, 0.20} is
  pre-registered. A verified Korean calibration, if A7 finds one, replaces the
  default in a version bump and not silently.
- **Different pre-fire fuel on the two sides** is handled three ways at once.
  First, the primary label is computed on **RdNBR**, dNBR divided by the square
  root of the absolute pre-fire NBR, which normalises by pre-fire condition; the
  dNBR label is computed too and both are reported. Second, a **fuel-discordance
  flag** is set when the two bands fall in different forest-type classes in the
  pre-fire 임상도, and the flag enters the model as a covariate. Third, a
  pre-registered sensitivity analysis refits on the fuel-concordant segments only.
- Pre-fire spectral indices are **not** available as covariates, for the reason in
  section 12.1.

### 5.5 The label rule

Let `f_lee` be the fraction of usable pixels in the lee analysis band at or above
the burned threshold, on the primary index.

**HELD.** The segment is an encounter under section 4, and `f_lee` is below 0.10.

**CROSSED.** The segment is an encounter under section 4, and `f_lee` is at or
above 0.50, and the lee burned patch touches the inner exclusion boundary on the
lee side, and the attribution test of section 5.6 passes.

**INDETERMINATE.** Everything else, always with a reason code, always retained in
the table, never dropped. The reason codes are:

| code | meaning |
|---|---|
| `CLOUD` | usable fraction below 0.70 in either band |
| `SCENE` | no scene pair satisfying section 5.2 |
| `MID` | `f_lee` between 0.10 and 0.50 |
| `FLANK` | the attribution test of section 5.6 fails |
| `SIDE` | windward and lee cannot be told apart |
| `TIMING` | condition C4 fails |
| `DISCORD` | fuel discordance beyond the pre-registered limit |
| `WIDTH` | width unknown beyond what a class prior can carry |

Indeterminate is a third class, not a bin for inconvenient rows. It is counted in
every table, and section 10.5 says what is done with it.

### 5.6 The attribution test, which stops flanking being read as crossing

A lee-side burn can arrive by going around the end of the barrier rather than
across this segment. The test:

- the lee burned patch adjacent to the segment is connected, within the burned
  mask, to the main burn **either** across this segment's lee band, **or** by a
  path that leaves the segment's neighbourhood; and
- the earliest active-fire detection inside the lee patch is no more than
  `delta_flank` after the fitted windward arrival time at this segment.

`delta_flank` is pre-registered at 6 hours. If the only connection to the main
burn is a path around a barrier terminus more than 500 m away **and** the timing
does not separate the two, the segment is `FLANK`.

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

| covariate | source | notes |
|---|---|---|
| effective width `W_eff` | **measured from pre-fire orthoimagery, section 6.3.** The road layer has no width attribute | latent, with an errors-in-variables term; see 6.3.4 and 6.5 |
| barrier type | barrier layer | road, river, ridge |
| approach angle `theta` | arrival-time fit, section 6.4 | folded into `W_eff` and also reported raw |
| signed slope in the direction of spread | `dem_korea` | positive is uphill into the barrier |
| fireline intensity at arrival | section 6.6 | not from fire radiative power |
| detection persistence | active-fire record | ordinal intensity proxy |
| lee-side fuel class | pre-fire 임상도 (`kfs_forest_type_map`) | categorical, non-stocked as reference |
| fuel discordance flag | pre-fire 임상도 | section 5.4 |
| wind speed, relative humidity, temperature at the arrival hour | `kma_asos_aws` | nearest station, with distance recorded |
| local solar hour of arrival | computed from coordinates | A2 owns the solar-time helper (task T1.5) |
| overpass cadence during the fire | active-fire record | section 2.3 |

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

Classical measurement error in a covariate attenuates its slope toward zero by a
factor of about

    kappa = sigma_x^2 / (sigma_x^2 + sigma_u^2)

where `sigma_x` is the spread of true widths in the sample. **The direction of
this bias is the dangerous one.** It pushes the width slope toward zero, which
pushes the study toward concluding that width does not matter. That is exactly the
conclusion F1 in section 1.5 is written to detect, so an uncorrected analysis
would be biased toward its own most eye-catching negative finding.

Three things are done about it, all pre-registered:

1. **An errors-in-variables term in the Bayesian model.** The true width
   `W_true_i` is a latent parameter with a prior informed by the automatic
   measurement, and the observed measurement is `W_obs_i = W_true_i + b + e_i` with
   `e_i` drawn at standard deviation `sigma_u`. `b` and `sigma_u` are estimated
   jointly from the hand-measured subsample inside the same fit, not fixed
   beforehand. The width posterior that comes out is disattenuated, with honestly
   wider intervals, and both the naive and the corrected posteriors are reported
   side by side so the size of the correction is visible.
2. **`kappa` is reported as a headline diagnostic**, with its own interval, next to
   the breach curve. A reader can then see how much of the curve is measurement.
3. **F1 becomes asymmetric**, which is the change that matters most. See section
   1.5 and gate M1.
4. **A pre-registered reading rule for a flat curve**, section 11.5, which decides
   before the fit how a true null is told apart from an attenuated one. The
   discrimination does not rest on the fitted slope alone, because the fitted slope
   is the thing under suspicion.

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

At each segment, acquisition times of active-fire detections within 1 km are fitted
by a weighted local plane. The fit requires at least 5 detections spanning at
least 2 distinct acquisition times, or condition C4 fails.

- **Spread direction** is the direction of increasing fitted time.
- **Rate of spread** `r` is the reciprocal of the fitted gradient magnitude.
- **Approach angle** `theta` is the angle between the segment centreline bearing
  and the spread direction, folded into (0, 90] degrees.
- The fit's residual standard error is retained and is what section 5.1 compares
  the two sides' arrival times against.

Sub-daily geostationary detections from GK-2A would tighten the timing
considerably, and the repository already has the scaffold at
`src/wildfireguardian/fire_detection/gk2a.py`. That scaffold is blocked on a KMA
API Hub key and its keyless fallback only reaches back to 2023-02, so it cannot
serve the 2019 and 2022 fires. GK-2A is therefore **not** in the primary
specification. If the key arrives, a GK-2A-timed run is a pre-registered
secondary, reported beside the primary and never in place of it.

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
The exact formulation used there must be confirmed by A7 before this section is
frozen. If it differs from the expression above, this section is corrected and the
version is bumped, and the paper's data has no role either way: it is the source of
a method, and its data is not used.

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
perimeter is between 50 m and `R_max`. `A_min` is pre-registered at 4 NBR pixels
(about 1,600 square metres), which is roughly the smallest patch that the scene
can show without being a single mixed pixel. `R_max` is pre-registered at 2,000 m,
beyond which attributing a spot to a particular barrier segment is not credible.
A spot with two candidate source perimeter points within 20 per cent of each other
in distance is flagged ambiguous and excluded from the distance fit, with the
count reported.

**The distance distribution.** Lognormal as primary, with a generalised Pareto
tail as the pre-registered alternative, compared by leave-one-out information
criteria. The likelihood is **truncated to [50 m, `R_max`]**, because the sample
is truncated by construction at both ends. This is not a cosmetic point: the
estimand is the distribution of **detectable** spot distances given detection, and
it is reported under that name. Small spots below `A_min` and spots that burned
out before an overpass are invisible to this record, and no correction is
attempted for them.

**The rate, which is the hard part.** A distance distribution alone cannot give a
per-segment spotting probability. A Poisson rate `lambda` is needed: spots per 100
m of active front per hour. It is estimated from the counted spots and the
estimated active front length-hours from the arrival-time surface, and then

    p_spot_i = 1 - exp( -lambda * T_i * (1 - F(W_eff_i + 50 m)) )

with `T_i` the residence time of the front at the segment. `lambda` is expected to
be weakly identified on a sample of this size. F4 in section 1.5 is the condition
under which the arm is withdrawn rather than published.

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

Nothing is tuned on a held-out complex. Standardisation constants, hyperparameter
choices, thresholds and the digitising error estimate are all computed inside the
training folds.

### 10.2 The primary metric, named now

**Mean out-of-complex log predictive score per labelled segment**, higher is
better. It is a proper scoring rule, it rewards calibration and discrimination
together, and the deliverable is a probability that a county office would act on,
so calibration is not optional.

### 10.3 Secondary metrics

Brier score, PR-AUC, calibration slope and calibration intercept, each reported
per fold with the held-out complex named, never bare.

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
crossing event. Two consequences, both handled in advance:

- a **barrier-line random intercept** is included alongside the fire-complex one,
  so the model does not treat 10 segments of one road as 10 independent
  observations;
- the effective number of independent encounters, estimated from the barrier-line
  variance component, is reported next to the raw segment count everywhere the
  raw count appears.

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

### 11.3 Feasibility gates, declared now, checked before any model is fitted

These are checked on the labelled table, before the first fit, and the branch
taken is recorded.

| gate | condition | consequence |
|---|---|---|
| G1 | at least 150 labelable segments **and** at least 30 held | full specification, section 7.2 |
| G2 | 60 to 150 labelable, **or** 10 to 30 held | **reduced specification**: covariates cut to width, barrier type and signed slope; fire effect becomes a pooled intercept with the section 7.4 prior; the ember arm is descriptive only |
| G3 | fewer than 60 labelable **or** fewer than 10 held | **no model is fitted.** The round delivers the labelled dataset, the descriptive tables, the indeterminate counts and the bounding analysis, and records the design as untestable on this record (F5) |
| W1 | within the road barrier type, at least 25 segments with `W_cleared` at or above 6 m **and** at least 25 below | if not met, the width curve is reported as not identified for roads, and only the barrier-type contrast and the ember distribution are published |
| M1 | the estimated attenuation factor `kappa` of section 6.3.4 is at or above 0.70, **and** at least 60 hand-measured segments support the error model (section 6.3.3) | if not met, the width covariate is declared too noisy to carry the question: no breach curve against width is published, F1 cannot be reported as evidence either way, and the outcome is written as **not resolvable at the achieved measurement precision** |
| P1 | the width posterior standard deviation is below 0.8 times its prior standard deviation | if not met, the width result is reported as prior-dominated and **no breach curve is published at all** |

P1 is the one that stops a pretty figure being drawn out of a prior. It is
checked after the fit and it can veto the headline output. M1 is its counterpart
for measurement rather than prior: it stops a flat curve being drawn out of a
noisy ruler. Both can veto the headline output, and both are checked and reported
whatever they say.

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

Five instruments, three of which run **before any label is computed**.

#### 11.5.1 Instrument 1: the repeat-measurement study, before labelling

Thirty segments measured twice, independently (section 6.3.3). This yields
`sigma_u`, the measurement error standard deviation, to about 13 per cent
relative, and with the observed spread of measured widths `sigma_obs` it yields
the attenuation factor

    kappa = (sigma_obs^2 - sigma_u^2) / sigma_obs^2

with an interval. `kappa` says how much slope the measurement is expected to eat,
as a number, independently of any outcome. It is reported beside the curve.

#### 11.5.2 Instrument 2: design-stage recoverability, before labelling

This is the decisive one, and it is available before a single label exists.

Take the **real** segment geometry and the **real** measured width distribution,
including its real measurement error from instrument 1. Simulate outcomes under a
pre-registered non-null slope equal to the smallest effect of interest (section
11.5.3). Refit the pre-registered model to the simulated outcomes. Repeat 500
times. The **recoverability** is the fraction of simulations in which the fitted
model reaches the F1 threshold of `P(beta_width < 0)` at or above 0.90.

- Recoverability is computed on **simulated outcomes only**. The real labels are
  never touched, so this can and must be run while the labelling is still in
  progress, and the number is committed before any real fit.
- **If recoverability is below 0.80, a flat curve is uninformative whatever the
  real fit produces, and that is known in advance.** The pre-registered consequence
  is that the width result is reported as **not resolvable at the achieved
  measurement precision and sample size**, and F1 is not reported as evidence
  either way.
- If recoverability is at or above 0.80, the design can see an effect of the size
  that would matter, and a flat curve then means something.

#### 11.5.3 Instrument 3: a smallest effect of interest, named now

The null has to be null **of something**, or an equivalence claim is unfalsifiable.
The pre-registered smallest effect of interest is:

> a change of **0.10** in the modelled probability of a lee-side burn, between a
> 3 m and a 9 m effective width, holding all other covariates at their sample
> medians.

Three metres to nine metres brackets the width in the claim under test, and 0.10
is chosen as the smallest change a county planner could act on. The number is
A3's judgement, it is listed in `OPEN_QUESTIONS.md` as Q9 for A6 to ratify or
replace, and once ratified it is frozen.

#### 11.5.4 Instrument 4: the equivalence reading of the disattenuated posterior

After the fit, on the **errors-in-variables posterior only**, never the naive one:

| what the disattenuated interval does | how it is read |
|---|---|
| excludes zero in the hypothesised direction | the width term is reported with its interval, and F1 does not fire |
| **excludes the smallest effect of interest**, and instruments 1, 2 and 5 all pass | **an informative null.** The record is reported as inconsistent with a width effect large enough to matter, with the effect size it can exclude stated explicitly |
| includes both zero and the smallest effect of interest | **uninterpretable.** Reported as not resolvable at the achieved measurement precision, and F1 is not reported as evidence either way |

The middle row is the outcome that makes a null worth publishing. The bottom row
is the outcome this section exists to stop being mistaken for it.

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

A flat curve is reported as an **informative null** only when all four hold:
`kappa` at or above 0.70 (gate M1), recoverability at or above 0.80, the
disattenuated interval excluding the smallest effect of interest, and the
measurement passing instrument 5. If any one fails, the outcome is **not
resolvable at the achieved measurement precision**, and the document says in terms
that this is not a synonym for "width does not matter".

---

## 12. Leakage traps, addressed before A6 raises them

### 12.1 The one A6 will raise first: severity encodes its own label

The label is computed from dNBR on a specific scene pair. Any severity covariate
computed from that same scene pair is partly the label, and a model given it will
look good for no reason.

**The fix is a hard constraint, not a caution.** Section 6.1: no covariate in
either arm may be derived from the post-fire scene, and none from any spectral
index at all, pre-fire included. Pre-fire indices are excluded too, because the
primary label is RdNBR, which has pre-fire NBR inside it, so a pre-fire index is
also a partial function of the label. Fuel and fuel load come from the categorical
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
"barrier effectiveness" and never "the effect of width". The distinction is
enforced in the same way as the claim rules: a fixed vocabulary, used everywhere or
nowhere.

#### 12.4.5 Selection, the general form of the same problem

Underneath the suppression confound is a plainer one: a barrier that stopped a
fire is, by construction, part of that fire's perimeter, and everything else that
decides where a fire stops (a wind drop, nightfall, rain, a fuel change) arrives
bundled into the same encounter. Conditioning on arrival (section 4) and on
arrival-hour weather (section 6.2) does real work against this, and it does not
finish the job. Section 1.4 states the estimand as associational for this reason.

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
- the second independent pass on at least 20 of the 60 is what turns "we were
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

### 12.8 Threshold shopping

`tau_burn`, the 0.10 and 0.50 label cut points, `delta_flank`, `A_min`, `R_max`,
the segment length and the buffer distances are all fixed in this document. The
sensitivity analyses over them are declared here, and every sensitivity result is
reported together with the primary, never in place of it.

---

## 13. The outputs, pre-registered before any fitting

Each of these is produced, or its non-production is explained by a named gate
from section 11.

1. **The breach curve against effective width, with uncertainty**, per barrier
   type, with the number of supporting segments shown in each width bin on the
   figure itself, and with the P1 gate applied.
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
6. **The label accounting table**: eligible, ineligible by reason, held, crossed,
   indeterminate by reason, per fire and per barrier type, plus the effective
   independent-encounter count of section 10.6.
7. **The covariate provenance audit table** from section 6.1.
8. **The bounding analysis** of section 10.5 and the prior sensitivity analysis of
   section 7.5.
9. **The comparison table**: structured model, B0, B1, B2 and the gradient-boosted
   classifier, on the primary metric, per fold, with the held-out complex named,
   plus the SHAP summary.

Every number in these outputs is registered before it appears on any surface, per
scope rule 6 of `research/README.md`.

---

## 14. Prior art, and how this design differs

A7 owns the verified bibliography (`research/lit/`, task T1.6). A3 has not read
any of the items below in full, has verified none of them, and writes nothing into
`research/lit/`. Every line here is a statement of what the design assumes the
source says, flagged as unverified, and it must be checked before the signature.

| source | what the design takes from it | how this design differs | verification status |
|---|---|---|---|
| NIFoS press release 2025-04-25 and attachment 2-2 | the claim under test, that forest roads of 6 m or wider are the most effective firebreak | this design tests the claim against labelled encounters from real Korean fires, with a pre-registered label rule and a declared falsification condition, rather than restating it | **unverified. The attachment is not in the repository (human gate WJ-004).** Section 15.1 lists what is needed from it |
| Kim and Im 2024, FDS simulation of Yeongdeok 2022 roads, Korean Society of Forest Engineering | Korean prior art on road firebreak behaviour, and a physical reference for what a flame front does at a gap | that work is a computational fluid dynamics simulation of a case; this design is an observational study over five fires with pre-registered labels and out-of-complex validation. Simulation supplies mechanism, this supplies an encounter record | unverified by A3 |
| Thompson et al. 2021 (Forests) | fuel-break effectiveness framing and the idea of evaluating breaks against observed fire encounters | **American. Source of a method and framing only. Its fire data is not used for fitting** (scope rule 1, and RC-010) | unverified by A3 |
| Zong et al. 2026 firebreak review (Fire Ecology) | the review's taxonomy of firebreak effectiveness evidence, for positioning | a review, not a Korean encounter dataset. This design contributes the encounter record the review class of work summarises | unverified by A3 |
| Swedosh et al. 2021, effective width in Spark | the effective-width formulation of section 6.5 | **Australian. Source of a method, and its data is not used.** This design applies the formulation to Korean encounters and fits the coefficients on Korean data only | unverified by A3, and section 6.5 is blocked on this |

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
  6. whether the attachment contains a segment-level or road-level data table. If
     it does, the design gains a direct comparison and section 14 is rewritten.
- **WJ-001, the six API keys.** All six are unset in this sandbox. Nothing can be
  fetched until they exist. Sentinel-2 and the active-fire archive are both behind
  them.

### 15.2 From A1

Registry entries reaching `verified` for `kfs_forest_roads`,
`base_map_linear_features`, `sentinel2_l2a_dnbr`, `firms_active_fire_korea`,
`dem_korea` and `kfs_forest_type_map`. `research/roads/DATA_REQUIREMENTS.md` is
the keyed list, and it is written against what A1 has confirmed obtainable rather
than what was hoped for.

The width question is already answered and the answer is no: the forest road SHP
has no width attribute, so section 6.3 is rewritten around image-derived
measurement. What is still needed from A1:

1. **the full attribute schema of the forest road SHP**, and specifically whether
   a road class field (간선임도, 지선임도, 작업임도) or a construction or survey
   year exists. A class field supplies the fallback prior of section 6.3.5; a year
   field is what lets section 3.1 exclude roads built after a fire;
2. **a source of pre-fire high-resolution orthoimagery with per-tile vintage**,
   which is not currently a registry entry and is the single dependency that
   section 6.3 cannot proceed without;
3. **the temporal coverage of `kfs_fire_state_history_csv`**, since
   `kfs_fire_stats_csv` is now verified as 2022 to 2025 and does not reach Goseong
   2019 (section 5.2);
4. **the OpenStreetMap hydrography completeness audit inputs** for section 3.1.

### 15.3 From A2

The complex rule implementation, the local solar time helper and the
dirty-timestamp quality control (task T1.5). This direction consumes them and does
not reimplement them.

### 15.4 From A6

The shared evaluation harness and the cross-validation split contract (task T2.1).
If A6's harness names a different program-wide primary metric from section 10.2,
A6's name wins and this document is version-bumped to match.

### 15.5 From A7

Verification of the five prior-art items in section 14, and in particular the
Swedosh et al. effective-width formulation, on which section 6.5 is explicitly
blocked. Also a Korean dNBR calibration and a Korean fuel-load table if either
exists.

---

## 16. Change control

Once A6 signs this document, it is frozen. Any change is a new version with a
dated entry in the table below, and every output names the version it was produced
under. A change made after a label has been computed must say so in its entry, and
the reason must not be that the result was disappointing.

| version | date | what changed | why |
|---|---|---|---|
| v0.1 | 2026-09-16 | first draft, written before any data was touched | task T2.2 |
| v0.1a | 2026-09-16 | sections 3.1, 5.2, 6.2, 6.3, 6.5, 6.7, 1.5, 11.2, 11.3, 12.5 and 15.2 revised, still before any data was touched | A1 confirmed the forest road SHP has no width attribute, NGII base map and NGII 5 m DEM are blocked (HTTP 400, now a human gate), OpenStreetMap and Copernicus GLO-30 are the working routes, and `kfs_fire_stats_csv` covers 2022 to 2025 only. Image-derived width became the primary path, gate M1 and the asymmetric reading of F1 were added |

---

## 17. Statement for the signing agent

Written by A3 on 2026-09-16. No model was fitted. No dataset was downloaded. No
number in this document is a measurement. Every threshold here is a decision rule
declared before the data exists, and the falsification conditions in section 1.5,
the feasibility gates in section 11.3 and the baseline rule in section 10.4 are
the three places where this design is allowed to tell its author that it did not
work.
