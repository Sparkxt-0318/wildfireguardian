# Kill-shot template

**Owner: A6. Version 1.0, 2026-09-16.**

One kill-shot section per direction, written into
`research/eval/killshots/<direction>.md`. It holds the single strongest
objection a hostile reviewer would raise, and whether the result survives it.

Not a list of limitations. A limitations list is a way of mentioning ten small
things so that the one large thing is not conspicuous. This section carries one
objection, the one that would end the direction if it were right, and it is
written twice: once as a prior before any result exists, and once as a verdict
after the result is in. Both stay in the file. A prior that was wrong is
evidence that the check worked.

---

## The structure

### 1. The objection, in one sentence

A reviewer's sentence, not the author's paraphrase. If it cannot be said in one
sentence without hedging, it is not yet understood.

### 2. Why a hostile reviewer raises it

Who raises it and from what standpoint: a fire scientist, a statistician, a
county emergency officer, a landslide geomorphologist. What they know that makes
the objection obvious to them.

### 3. What would have to be true for the result to survive

Write this **before** the discriminating test is run. State the observable
consequences of the objection being right, and the observable consequences of it
being wrong, and make sure they differ. If they do not differ, there is no test
and the honest move is to scope the claim instead.

### 4. The discriminating test, with its reading rule fixed in advance

The analysis that separates the two worlds of item 3. Pre-registered: its
inputs, its metric, and the reading rule, in the form "if X then the objection
stands, if Y then it does not, and if the outcome falls between X and Y then the
claim is scoped to Z". A test without a reading rule fixed in advance is a test
whose result will be read as support.

### 5. What the test actually returned

Numbers, with their split fingerprint and their staging id from
`research/eval/numbers_staging.json`. Written after the run, and the section
above it is not edited afterwards.

### 6. Verdict

One of:

- **survives** as stated;
- **survives with a scope cut**, and the cut is written as the sentence the
  direction may now use;
- **does not survive**, and the claim is withdrawn, registered in the program's
  withdrawal record, and the direction either redesigns or stops.

### 7. The sentence the claim becomes

The exact wording permitted on a poster, in the README and in the paper after
this kill shot, carrying its uncertainty interval and its evaluation frame. This
sentence is what the graduation step in `research/FORBIDDEN_CLAIMS.md` promotes,
and nothing wider than it is allowed anywhere.

---

# Seeded priors

**These are A6's guesses, written 2026-09-16, before any pre-registration was
received and before any data was fitted. They are priors, not findings. They are
recorded here so that it can be checked later whether the review anticipated the
real problem or missed it.**

---

## Prior kill shot, roads (H-ROADS)

**1. The objection.** The barrier width coefficient may be measuring where
firefighters could get to and stand, rather than the physical barrier, because
in Korea a wide forest road is exactly the road the engines used, the line the
crews held and the place a backfire would be lit.

**2. Why a reviewer raises it.** Any operational fire officer knows that a road
is an access asset before it is a barrier, and the Korea Forest Service builds
forest roads for access. The claim under test, that roads of 6 m or wider are
the most effective firebreak, is a claim about a treatment that is deliberately
placed where suppression happens. This is confounding by indication, and it is
the same shape as the night-growth problem that forbidden-claim rule RC-007
already guards.

**3. What would have to be true to survive.** The width relationship would have
to hold within strata where suppression effort is plausibly constant: at night
before helicopters fly, on segments far from any access point, on river and
ridge barriers that no crew can stand on, and during the hours of the 2022 and
2025 fires when resources were demonstrably saturated and most segments got no
attention at all. If the relationship exists only where effort was concentrated,
the objection stands.

**4. The discriminating test.** Stratified re-fit on segments with no recorded
resource within a declared distance and time, plus a barrier-type contrast in
which rivers and ridges, which take no crews, carry the same width relationship
as roads. Reading rule to be fixed with A3 in the pre-registration, in the units
of the primary metric, before the fit.

**5. My prior on the outcome.** The objection is not fully answerable with the
planned data, and the honest end state is a scope cut: the claim becomes a
statement about barriers as they are used in Korean suppression practice, not a
statement about width as a physical property. A second, near-equal objection is
that the effective sample size is five fires, and a hierarchical model with a
fire random effect over five fires carries most of its apparent precision in the
prior.

**6. The threat that arrived with the data, added 2026-09-16 on A1's finding,
still before any fit.** The Korea Forest Service forest road dataset carries no
width attribute. Width has to be measured from imagery on a sample, so the one
covariate this direction turns on is measured with error, and classical
measurement error attenuates the fitted slope toward zero. This flips the
asymmetry of the whole test: a flat breach curve becomes weak evidence, because
it is what both a true null and a badly measured covariate produce, while a
steep curve measured under attenuation is strong evidence. My prior is that a
hostile reviewer will raise the confounding objection first and the attenuation
objection second, and that the attenuation one is the harder of the two to
answer, because the confounding can at least be stratified against while the
attenuation needs a repeat-measurement study that nobody has budgeted. The
reading rule for a null result has to be fixed before the fit, or a null will be
read afterwards as a refutation of a claim that the data never had the power to
refute.

---

## Prior kill shot, landslides (H-SLIDE)

**1. The objection.** The apparent decline of landslide rate with years since
fire may be a decline in triggering rainfall intensity and in inventory mapping
effort over those same years, because with a handful of Korean fires the years
since fire are aliased with the calendar years and with the mapping campaigns
that followed each event.

**2. Why a reviewer raises it.** A geomorphologist reads a recovery curve and
immediately asks what the rainfall did in those years. An inventory specialist
asks who mapped which year and at what minimum size. Both questions have obvious
answers for Korean data, and neither is favourable: the post-fire mapping effort
is concentrated in the first year after a famous fire, and Korean summer
rainfall varies enormously between years.

**3. What would have to be true to survive.** The time-since-fire term would
have to survive the explicit inclusion of event rainfall at the storm level and
a documented or modelled detection probability, and it would have to appear
consistently across fires whose years since fire map to different calendar
years. A window that is a root strength window rather than a weather window
should also show the severity gradient that root loss predicts.

**4. The discriminating test.** A fit with the time term and the rainfall term
entered together, with the design matrix collinearity reported; a fit restricted
to a window of documented constant inventory completeness; and the leave-one-
fire-out contrast across fires of different years. Reading rule to be fixed with
A4 in the pre-registration.

**5. My prior on the outcome, sharpened 2026-09-16 by A1's finding that the
landslide occurrence record on hand covers 2021 to 2025 and is address-level
with 5118 records.** Inside a five-year observation window each fire contributes
exactly one run of years since fire, so within a fire the time term and the
calendar are the same variable, and only the between-fire contrast says anything
about the shape of the curve. On top of that, an address-level record has to be
geocoded onto a slope unit, and the geocoding error is worst where the terrain
is steepest, which is where the model is meant to work. This is the direction I
currently expect to fail its primary form. My prior is that with the available Korean fires the recovery
window is not separably identified from calendar rainfall, and the defensible
result is a bound rather than a curve: something of the form that the elevated
period is no shorter than some number of years and no longer than another, with
a wide interval. The pine versus broadleaf arm is weaker still, because in Korea
species covaries with soil depth, aspect and management, and I would advise
demoting it to a pre-registered secondary analysis before anyone invests in it.

---

## Prior kill shot, suppression (H-SUPP)

**1. The objection.** Whatever size distribution this direction would report
after correcting for censoring may be an extrapolation whose shape is set by an
untestable assumption rather than by the Korean record, because suppression is applied to every Korean fire and the
counterfactual of an unsuppressed Korean fire is never observed.

**2. Why a reviewer raises it.** A statistician sees a censoring correction and
asks where the uncensored observations are. In a medical survival analysis some
patients are observed to the event. Here the intervention is universal, so the
identification comes entirely from a modelling assumption about how the
containment hazard would behave in its absence. That assumption cannot be
checked against anything in the data.

**3. What would have to be true to survive.** There would have to be real
variation in suppression intensity that is not itself a response to fire
behaviour: fires where resources arrived late for reasons unrelated to the fire,
such as simultaneous incidents elsewhere, terrain access, or an aircraft
grounding for weather independent of the fire's own conditions. That variation
is the only thing that could carry identification, and finding it in the Korean
record is the real work of this direction.

**4. The discriminating test.** Sensitivity of the corrected tail across a
declared range of the identifying assumption, reported as a band. If the band
spans the operationally meaningful range, the correction does not support a
usable number, and the deliverable becomes the early escape-risk score, which
does not need the counterfactual at all.

**5. My prior on the outcome, sharpened 2026-09-16 by A1's finding that the
committed Korea Forest Service fire statistics extract covers 2022 to 2025 only,
2020 rows.** Four distinct years cannot carry a forward-chained evaluation that
means anything: at most two folds, one doctrine period, and a tail estimated on
a few hundred fires. On the committed data alone my prior is that this direction
should not fit at all, and should instead be pre-registered as descriptive until
the longer record clears WJ-001 and WJ-006. Conditional on the longer record
arriving, the escape-risk score is likely to survive, on forward-chained
held-out years, as a discrimination claim with its evaluation
frame attached. The censoring correction is likely to end as a sensitivity band
rather than a corrected distribution. I would suggest that the direction be
written from the start with the score as its primary deliverable and the
correction as a secondary, assumption-dependent analysis, rather than the other
way round.

---

## Standing note on these priors

A6 wrote these before seeing any pre-registration. They are not conditions, they
are not a refusal, and a modeling agent is free to argue that a prior is wrong.
What they are is a record: when the results arrive, the file will show whether
the strongest objection was anticipated or invented afterwards to fit the
answer.
