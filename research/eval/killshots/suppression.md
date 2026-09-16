# Kill shot: suppression (H-SUPP)

**Owner: A6. Built from `research/eval/KILLSHOT_TEMPLATE.md` version 1.0.**
**Items 1 to 4 written 2026-09-16, round 6, before any result exists. They are
not edited afterwards.** Items 5 to 7 are appended after the result and are
empty today.

The template's seeded suppression prior, written 2026-09-16 before any
pre-registration was received, is copied unchanged into the appendix so the two
can be compared later. **That prior is retired rather than carried forward, and
the closing note of this file says why.**

---

## 1. The objection, in one sentence

Whatever held-out skill this direction reports at horizon H3 may be the
arithmetic of its own risk set rather than information about fire behaviour,
because two thirds of the fires in the evaluation frame are already contained by
hour three and every fire in the Korean record that reached 10 ha was still
burning then, so a model that has learned nothing except which fires burn past
their third hour will clear the pre-registered margin and be reported as having
separated the fires that get large from those that do not.

## 2. Why a hostile reviewer raises it

Three people raise it and they arrive from different directions.

**A statistician** reads the pre-registration's own numbers back at it. The
estimand is the probability that a fire's recorded final size reaches 10 ha,
given covariates knowable three hours after the report. The baseline is the
unconditional exceedance rate. On the committed Korean record that rate is 3.88
per cent over all fires and 12.21 per cent among the fires still uncontained at
hour three, and the shortest fire that ever reached the floor ran 3.67 hours. So
conditioning on nothing but survival to the horizon more than triples the base
rate, and the design measures its model against a baseline that has not done
that. A margin that looks like discrimination is then partly the gap between two
different populations.

**A survival analyst** asks a sharper version of the same question. The design
fits a containment hazard on fire-hours and an exceedance model on fires, from
the same covariates, on a record where duration and final size are very nearly
the same variable: no fire under three hours reached 10 ha, and the median
duration of the fires that did is on the order of a day. So the hazard model,
the size model and the score are three views of one measurement. Agreement
between them will read as corroboration and is closer to tautology.

**A Korean dispatcher** raises the operational version and it is the one that
stings. At hour three the dispatcher already knows whether the fire is out. A
score that tells him a fire which is still burning at hour three is more likely
to get large is telling him something he can see from the window. The
pre-registration's covariate firewall, section 10.6, excludes that indicator
because it is derived from a containment timestamp, so the score is not allowed
to use the one fact the dispatcher has; but the covariates it is allowed to use,
hour of day, day of year, province, wind, humidity and access distance, are
themselves good predictors of how long a fire burns. The model can therefore
learn the survival proxy without ever touching the forbidden column, and neither
the firewall nor the baseline will notice.

The objection is not that the fitted number will be wrong. It is that the number
answers "which Korean fires burn past their third hour" and will be reported as
answering "which Korean fires reach 10 ha", and on this record those two
questions have nearly the same answer for a reason that has nothing to do with
what the direction set out to measure.

## 3. What would have to be true for the result to survive

Written before the discriminating test is run. The two worlds have to look
different or there is no test.

**If the objection is right**, these follow and are observable:

- The model's margin over a baseline that already conditions on survival to the
  horizon is much smaller than its margin over the unconditional base rate, and
  may vanish.
- Restricted to the fires still uncontained at the horizon, which is the
  population a dispatcher is actually choosing among, the model's margin over
  that population's own base rate falls below the pre-registered threshold.
- The same covariates, asked to predict survival past the horizon rather than
  the size floor, score at least as well as they do on the size floor, and the
  two per-fire predictions are strongly rank-correlated.
- The fitted covariate effects in the containment hazard and the fitted
  covariate effects in the exceedance model point the same way with similar
  ordering, because they are estimating the same thing.
- The margin is sensitive to the horizon in the way the arithmetic predicts
  rather than in the way information accrual predicts: moving from H1 to H6
  shrinks the evaluation frame and raises the conditional base rate, and the
  reported margin tracks that rather than tracking the extra weather.

**If the objection is wrong**, these follow instead:

- The margin over the survival-conditional baseline is of the same order as the
  margin over the unconditional one, and clears the pre-registered threshold on
  its own.
- On the survivor-only frame the model still clears the threshold against that
  frame's base rate, with a cluster bootstrap interval excluding zero.
- The covariates carry information about size that they do not carry about
  duration: the size-model and duration-model rankings of the same held-out
  fires diverge materially, and the size model's advantage survives conditioning
  on the predicted duration.
- The integer score selects features that a duration model would not, or weights
  them differently, and the distillation loss is small on the size task while the
  same features distilled for duration lose more.

Those two lists differ, so a test exists.

## 4. The discriminating test, with its reading rule fixed in advance

**Inputs.** The same folds, the same covariates and the same fitted models as
the primary result. Nothing here needs an extra dataset and nothing here is a
new model form. Four reported quantities, all named now.

- **T1, the survival-conditional baseline.** Implement **B2**, the exceedance
  rate among training-window complexes still uncontained at the horizon, applied
  as a constant prediction to the held-out year. Its own code path, computed
  inside the training window, exactly as B0 is. Report the primary metric's
  margin over B2 with its 90 per cent cluster bootstrap interval over
  day-province clusters, beside the margin over B0.
- **T2, the survivor frame.** Recompute the primary metric, B0 and the model, on
  the subset of held-out complexes still uncontained at the horizon, and report
  the margin over that frame's own training-window base rate, with its interval.
  Report the frame's size as a count and as a share of the full frame, per fold.
- **T3, the duration twin.** Fit the same covariates, with the same prior and
  the same folds, to the binary outcome "uncontained at the horizon", and report
  its held-out mean log predictive density, the Spearman correlation between its
  per-complex prediction and the exceedance model's, and the exceedance model's
  margin over B0 after the duration prediction is entered as an offset.
- **T4, the horizon family.** Report T1 and T2 at H1, H3 and H6, which section
  17.1 already declares as a fully reported family, together with each horizon's
  conditional base rate and frame size.

**The reading rule, fixed now, in nats per fire on the declared frame of
condition C2 of `research/eval/signoffs/suppression_v0.1.md`.**

- **The objection stands** if the margin over B2 in T1 is below 0.02 nats per
  fire, **or** if its 90 per cent interval contains zero, **or** if the
  survivor-frame margin in T2 is below 0.02 nats per fire. Reading: the reported
  quantity is a statement about which Korean fires burn past the horizon, not
  about which reach 10 ha, and it is written that way in every output. The
  integer score is not recommended, and rule RC-008's evaluation frame grows a
  fifth element, which is the conditional base rate of the frame the score was
  scored on.
- **The objection does not stand** if the margin over B2 is at least 0.02 nats
  per fire with its interval excluding zero, **and** the survivor-frame margin in
  T2 is at least 0.02 nats per fire with its interval excluding zero, **and** the
  exceedance model's margin over B0 in T3 survives entering the duration
  prediction as an offset at no worse than half its original size. Reading: the
  covariates carry information about final size that is not merely information
  about duration, on the evidence available, and the claim may be stated at the
  size floor with its evaluation frame attached.
- **Between those two**, which is where I expect this to land, the claim is
  scoped to: an association, on Korean fires still uncontained at the stated
  horizon, between information available at that horizon and the probability that
  the recorded final size reaches 10 ha, under the suppression regime that
  operated, with the survivor-frame margin and the frame's own base rate quoted
  beside it every time.

**Four things this reading rule does not do**, stated now so that they are not
offered later as though they had been.

1. It does not bear on the counterfactual. Pre-registration section 3 withdrew
   that quantity under every outcome and no branch above revives it. A test
   cannot rescue a quantity that is not reported.
2. It does not bear on the report-time offset. The offset biases the night
   contrast and the access-distance coefficient toward the hypothesis, and the
   instrument for that is the sixteen-cell grid of pre-registration section 5.4
   and failing condition F4, not anything in this file. A model can survive this
   kill shot and still have both of those coefficients contaminated.
3. It does not make the duration and the size separable in principle. On a
   Korean record where the shortest fire to reach the floor ran 3.67 hours, they
   may not be. The most this kill shot can produce is a measurement of how much
   of the apparent skill is the risk set, and a scope sentence that says so.
4. It does not touch the tail. Gates G3 and G4 close that arm on the evidence in
   section 7 of the sign-off record, and conditions C4 and C5 settle it. If the
   arm is closed, none of T1 to T4 applies to it.

**And the failing condition that is not in this kill shot.** If failing condition
F2 of the pre-registration fires, which A5 and I both expect, gate G1 never
opens, no fit happens and this kill shot never runs. That is the good case rather
than the bad one: the direction's deliverable is then the accounting of
pre-registration sections 4 and 5 and the data case in `DATA_REQUIREMENTS.md`,
all of it outcome free, and no kill shot is needed for a finding that no outcome
touched.

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

> **1. The objection.** Whatever size distribution this direction would report
> after correcting for censoring may be an extrapolation whose shape is set by an
> untestable assumption rather than by the Korean record, because suppression is applied to every Korean fire and the
> counterfactual of an unsuppressed Korean fire is never observed.
>
> **2. Why a reviewer raises it.** A statistician sees a censoring correction and
> asks where the uncensored observations are. In a medical survival analysis some
> patients are observed to the event. Here the intervention is universal, so the
> identification comes entirely from a modelling assumption about how the
> containment hazard would behave in its absence. That assumption cannot be
> checked against anything in the data.
>
> **3. What would have to be true to survive.** There would have to be real
> variation in suppression intensity that is not itself a response to fire
> behaviour: fires where resources arrived late for reasons unrelated to the fire,
> such as simultaneous incidents elsewhere, terrain access, or an aircraft
> grounding for weather independent of the fire's own conditions. That variation
> is the only thing that could carry identification, and finding it in the Korean
> record is the real work of this direction.
>
> **4. The discriminating test.** Sensitivity of the corrected tail across a
> declared range of the identifying assumption, reported as a band. If the band
> spans the operationally meaningful range, the correction does not support a
> usable number, and the deliverable becomes the early escape-risk score, which
> does not need the counterfactual at all.
>
> **5. My prior on the outcome, sharpened 2026-09-16 by A1's finding that the
> committed Korea Forest Service fire statistics extract covers 2022 to 2025 only,
> 2020 rows.** Four distinct years cannot carry a forward-chained evaluation that
> means anything: at most two folds, one doctrine period, and a tail estimated on
> a few hundred fires. On the committed data alone my prior is that this direction
> should not fit at all, and should instead be pre-registered as descriptive until
> the longer record clears WJ-001 and WJ-006. Conditional on the longer record
> arriving, the escape-risk score is likely to survive, on forward-chained
> held-out years, as a discrimination claim with its evaluation
> frame attached. The censoring correction is likely to end as a sensitivity band
> rather than a corrected distribution. I would suggest that the direction be
> written from the start with the score as its primary deliverable and the
> correction as a secondary, assumption-dependent analysis, rather than the other
> way round. <!-- research-claim-ok: RC-006 -->

**Where items 1 to 4 above depart from that prior, recorded now.**

**The prior's objection is retired, and it was retired by the design rather than
answered.** Pre-registration section 3 withdraws the counterfactual size
distribution as a reported quantity under every outcome, keeps a three-value
sensitivity family in its place with the assumption printed on each curve, and
forbids interpolating between them or summarising them as one. A withdrawn
quantity cannot be killed. So the objection I seeded, which a hostile reviewer
would certainly have raised against the design as briefed, has nothing left to
attach to, and carrying it forward would be a kill shot aimed at a quantity
nobody is going to report.

**The prior's proposed remedy was adopted before I asked for it.** The prior
advised that the direction be written with the score as its primary deliverable
and the correction as a secondary, assumption-dependent analysis. The
pre-registration does exactly that, and goes further by making the correction a
labelled family rather than an analysis.

**What the prior missed, and it is the thing this file is now about.** The prior
worried about the quantity the direction could not identify and said nothing
about the quantity it can. On the record that actually exists, the identified
quantity has a defect of its own: at a three-hour horizon the evaluation frame is
two thirds settled before the prediction is made, and survival to the horizon is
very nearly sufficient for the label. I had the arithmetic for that in my prior
leakage read, at item S3, and I did not see that it was the kill shot until I
read a pre-registration that fixed a horizon and then defined its risk set
nowhere. That is worth recording as it is: the prior anticipated the objection
everybody would raise, and the objection that matters came from running the
design's own numbers.
