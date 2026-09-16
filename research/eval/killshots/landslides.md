# Kill shot: landslides (H-SLIDE)

**Owner: A6. Built from `research/eval/KILLSHOT_TEMPLATE.md` version 1.0.**
**Items 1 to 4 written 2026-09-16, round 4, before any result exists. They are
not edited afterwards.** Items 5 to 7 are appended after the result and are
empty today.

The template's seeded landslide prior, written 2026-09-16 before any
pre-registration was received, is copied unchanged into the appendix of this
file so the two can be compared later.

---

## 1. The objection, in one sentence

Any decline of recorded landslide rate with years since fire that this design
reports is equally well explained by administrative attention to burned forest
land being highest in the year or two after a named fire, because the record is
a reporting record with no observable zero and the design's identification of
the years-since-fire term rests entirely on assuming that the calendar effect is
the same on burned and unburned ground.

## 2. Why a hostile reviewer raises it

Three people raise it and they arrive from different directions.

**A landslide geomorphologist** reads a post-fire recovery curve and asks what
the rainfall did in those years, then asks who counted the landslides. Told that
the counts come from a Korea Forest Service occurrence file keyed by forest
ownership class, the second question becomes the sharper one: this is a damage
administration record, so a landslide enters it when somebody reports damage, and
after a nationally reported fire somebody is looking.

**A statistician** looks at the design matrix. The years-since-fire term is
identified here only because unburned control units carry the calendar effect and
the model gives burned and unburned units the same calendar effect. Written out,
that is the assumption that there is no interaction between being burned and the
calendar year. Post-fire administrative attention is exactly such an interaction,
and it is largest at small years since fire, which is the same shape and the same
sign as the hypothesis. The one assumption carrying the estimate is the one the
design's own reporting section gives a named mechanism to violate.

**A Korean county forestry officer** knows a third thing. After a large fire the
county salvage-logs the burned timber, and it does so in the first years. Nobody
has a spatial dataset for that. So the years immediately after a fire carry
decayed roots, heightened attention and heavy machinery on wet steep ground, all
at once, all pushing the recorded rate the same way.

The objection is not that the fitted number will be wrong. It is that three
mechanisms with the same time profile and the same sign are competing for one
observed decline, and only one of them is the hypothesis.

## 3. What would have to be true for the result to survive

Written before the discriminating test is run. The two worlds have to look
different or there is no test.

**If the objection is right**, these follow and are observable:

- The fitted fire term moves materially between specification M-B, which carries
  measured reporting covariates, and specification M-C, which carries none, and
  it moves in the direction of a steeper decline when the reporting covariates
  come out.
- The fitted decline is present in the coefficient on the reporting covariates as
  well: ownership class, distance to road and distance to built-up land each
  carry a burned-by-time signal that a pure hazard mechanism has no reason to
  produce.
- The share of the occurrence record that is assignable to a unit, and the
  reporting intensity per unit of burned area, are themselves functions of
  calendar year and of years since fire.
- In the unburned control set, which no fire attention reaches, the calendar-year
  profile of recorded rate is flat or is driven by rainfall alone, while in the
  burned set it carries an extra early hump that the rainfall term does not
  explain. That difference is the burned-by-year interaction, and it is
  estimable with three cohorts even though it destroys the identification of the
  years-since-fire term when it is left free.

**If the objection is wrong**, these follow instead:

- The fitted fire term is stable across M-A, M-B and M-C in sign, ordering and
  approximate magnitude, so that leaving the calendar and the reporting
  covariates out changes little.
- A model given a free burned-by-calendar-year interaction puts that interaction
  near zero, so the decline survives in the years-since-fire term rather than
  migrating into the interaction.
- The decline tracks burn severity in the way root loss predicts, with a steeper
  early term on severely burned units, and does not track distance to road or
  distance to built-up land, which are attention variables and not root
  variables.
- The decline appears in the same shape in the two cohorts that reach two years
  since fire in different calendar years, which is the only between-cohort
  contrast the record carries.

Those two lists differ, so a test exists.

## 4. The discriminating test, with its reading rule fixed in advance

**Inputs.** The same fitted design as the primary result, plus one additional
specification and two additional reported quantities, all named now.

- **T1, the migration test.** Fit specification M-B with a free burned-by-
  calendar-year interaction added. Report how much of the fitted decline over
  years zero to three migrates from the years-since-fire term into that
  interaction, as the ratio of the fitted fire term's range over t under M-B to
  its range over t in the interaction model. Both terms are reported with their
  intervals. This specification is not identified in the way the primary model
  is, and it is not offered as an estimate: it is offered as a decomposition.
- **T2, the attention-covariate test.** Report the coefficients of the reporting
  term interacted with years since fire: ownership class, distance to road and
  distance to built-up land each crossed with t, with intervals.
- **T3, the control-side calendar test.** Report the fitted calendar profile of
  recorded rate on unburned control units alone, with the rainfall term in, and
  compare it against the burned side's. The comparison statistic is the burned
  minus unburned difference in fitted log rate by calendar year, with its
  interval, resampled over storm by spatial-block clusters.
- **T4, the severity gradient.** Report the fitted interaction of burn severity
  with the years-since-fire term, with its interval. Root loss predicts a
  steeper early decline on severely burned units; attention predicts a level
  shift and not a slope.

**The reading rule, fixed now and in the units of the fitted log rate.**

- **The objection stands** if T1 migrates more than half of the fire term's
  range over t into the burned-by-year interaction, **or** if any T2 interaction
  clears zero at 90 per cent in the direction that mimics the hypothesis, **or**
  if T3's burned minus unburned calendar difference clears zero at 90 per cent
  with an early hump. Reading: the reported quantity is a recorded-rate
  association under Korea Forest Service reporting practice and carries no root,
  recovery or stability reading of any kind.
- **The objection does not stand** if T1 migrates less than one fifth of the
  range, **and** no T2 interaction clears zero, **and** T3's difference does not
  clear zero, **and** T4's severity gradient clears zero in the direction root
  loss predicts. Reading: the decline over years zero to three survives the
  attention explanation on the evidence available, and is still not a window.
- **Between those two**, which is where this is most likely to land, the claim is
  scoped to: an association between years since fire and recorded landslide rate
  on Korean forest land, over years zero to three only, under a reporting process
  that the design models but cannot separate from the hazard, with the migration
  fraction from T1 quoted beside it every time.

**Three things this reading rule does not do**, stated now so that they are not
offered later as though they had been.

1. It does not test the support problem. The design observes years since fire of
   zero, one, two and three, all of the last from one cohort in one calendar
   year and in practice from one storm window. No test in this file bears on what
   happens after year three, and no outcome of this kill shot licenses a
   statement about it.
2. It does not separate salvage logging from root decay. There is no salvage
   dataset. If one never arrives, the term is a combined root-decay and post-fire
   management term under every branch above, and T4's severity gradient does not
   rescue it, because salvage follows severity too.
3. It does not make the reporting term identified. T1 to T4 are decompositions
   and comparisons, not identification. The most this kill shot can produce is a
   bound on how much of the decline the attention mechanism could account for.

**And the failing condition that is not in this kill shot.** If failing condition
F3 of the pre-registration fires, no fit happens and this kill shot never runs.
That is the good case, not the bad one: the assignability table would then be the
direction's result, it is outcome free, and no kill shot is needed for a finding
that no outcome touched.

---

## 5. What the test actually returned

Not written. No result exists. A6 writes this after the fit, with the numbers,
their split fingerprint and their staging id from
`research/eval/numbers_staging.json`, and does not edit items 1 to 4 when doing
so.

## 6. Verdict

Not written.

## 7. The sentence the claim becomes

Not written.

---

## Appendix. The seeded prior, copied unchanged

Copied from `research/eval/KILLSHOT_TEMPLATE.md`, written 2026-09-16 before any
pre-registration was received. It is reproduced here verbatim so that the
anticipation can be scored later.

> **1. The objection.** The apparent decline of landslide rate with years since
> fire may be a decline in triggering rainfall intensity and in inventory mapping
> effort over those same years, because with a handful of Korean fires the years
> since fire are aliased with the calendar years and with the mapping campaigns
> that followed each event.
>
> **2. Why a reviewer raises it.** A geomorphologist reads a recovery curve and
> immediately asks what the rainfall did in those years. An inventory specialist
> asks who mapped which year and at what minimum size. Both questions have obvious
> answers for Korean data, and neither is favourable: the post-fire mapping effort
> is concentrated in the first year after a famous fire, and Korean summer
> rainfall varies enormously between years.
>
> **3. What would have to be true to survive.** The time-since-fire term would
> have to survive the explicit inclusion of event rainfall at the storm level and
> a documented or modelled detection probability, and it would have to appear
> consistently across fires whose years since fire map to different calendar
> years. A window that is a root strength window rather than a weather window
> should also show the severity gradient that root loss predicts.
>
> **4. The discriminating test.** A fit with the time term and the rainfall term
> entered together, with the design matrix collinearity reported; a fit restricted
> to a window of documented constant inventory completeness; and the leave-one-
> fire-out contrast across fires of different years. Reading rule to be fixed with
> A4 in the pre-registration.
>
> **5. My prior on the outcome, sharpened 2026-09-16 by A1's finding that the
> landslide occurrence record on hand covers 2021 to 2025 and is address-level
> with 5118 records.** Inside a five-year observation window each fire contributes
> exactly one run of years since fire, so within a fire the time term and the
> calendar are the same variable, and only the between-fire contrast says anything
> about the shape of the curve. On top of that, an address-level record has to be
> geocoded onto a slope unit, and the geocoding error is worst where the terrain
> is steepest, which is where the model is meant to work. This is the direction I
> currently expect to fail its primary form. My prior is that with the available Korean fires the recovery
> window is not separably identified from calendar rainfall, and the defensible
> result is a bound rather than a curve: something of the form that the elevated
> period is no shorter than some number of years and no longer than another, with
> a wide interval. The pine versus broadleaf arm is weaker still, because in Korea
> species covaries with soil depth, aspect and management, and I would advise
> demoting it to a pre-registered secondary analysis before anyone invests in it.

**Where items 1 to 4 above depart from that prior, recorded now.** The prior
named mapping effort. The record turns out to carry no mapping in it at all, so
the mechanism in the kill shot is reporting rather than mapping, which is the
same family and a different bias. The prior named the aliasing as the objection.
The kill shot names the burned-by-calendar-year interaction instead, which is
sharper: the aliasing as the prior stated it does not bind the design that was
pre-registered, and what does bind it is the assumption that replaces it. And
the prior's proposed remedy, a bound on the elevated period, is withdrawn in the
kill shot: on years zero to three with one cohort at the far end there is no
bound to state, and offering one would be the failure this file exists to catch.
