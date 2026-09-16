# Kill-shot section: roads (H-ROADS)

Built from `research/eval/KILLSHOT_TEMPLATE.md`. Owner: A6.

**Items 1 to 4 are written on 2026-09-16, before any pre-registration was signed,
before any segment was labelled, before any fit and before any result exists.
They are not edited afterwards. Items 5 to 7 are appended when the result
arrives.** If a later reader wants to know whether this review anticipated the
real problem or invented one afterwards to fit the answer, that is what the
timestamps on this file are for.

State of the direction at the time of writing: `refused`, record at
`research/eval/signoffs/roads_v0.1b.md`. A kill shot is written for a refused
direction because the objection does not depend on the refusal being cleared, and
because writing it after the design is fixed would let the design shape it.

---

## 1. The objection, in one sentence

The barrier width coefficient may be measuring where firefighters could get to
and stand rather than the physical barrier, because in Korea a wide forest road
is exactly the road the engines used, the line the crews held and the place a
backfire would be lit.

That is the objection. One sentence, no hedge, and it has not changed since it
was seeded on 2026-09-16 before any pre-registration was received.

**The near-equal second objection, recorded here because it may overtake the
first.** The single covariate the direction turns on has to be measured from
imagery, so it carries classical measurement error, and measurement error
attenuates a slope toward zero. A flat breach curve is therefore what a true null
and a badly measured ruler both produce, and the study's most eye-catching
negative reading is the one its own measurement bias manufactures. I keep this as
a second objection rather than the first because it is answerable in advance by
work that costs a few days (a repeat-measurement study and a recoverability
simulation, both before any label exists), whereas the first is not answerable
with any data this program can obtain. But my prior is that a hostile reviewer
raises the confounding objection first and the attenuation objection second, and
that the second is the harder of the two to answer.

## 2. Why a hostile reviewer raises it

**Who.** An operational fire officer, and a statistician standing behind them.

**The officer's standpoint.** A forest road is an access asset before it is a
barrier. The Korea Forest Service builds 임도 to get machinery and crews into
terrain, and it builds the wider classes on the routes that matter most. When a
front arrives, an incident commander anchors a line on the widest road they can
reach, because that is where an engine can turn and where a crew has an escape
route. So the officer reads "wider barriers held more often" and hears "we put
our people on the wide ones", which is a sentence about deployment, not about
flame propagation across a fuel gap. They will say it in the first minute of
question time and they will be right to.

**The statistician's standpoint.** This is confounding by indication in its
textbook shape. The treatment, width, is deliberately placed where the outcome is
also acted on. It has the same structure as the night-growth problem that
forbidden-claim rule RC-007 already guards in this repository, where dispatch
responds to danger. Underneath it sits a plainer selection problem, which the
pre-registration states correctly in its section 12.4.5: a barrier that stopped a
fire is by construction part of that fire's perimeter, and everything else that
decides where a fire stops, a wind drop, nightfall, rain, a fuel change, arrives
bundled into the same encounter.

**Why it is not answerable by the planned covariate set.** There is no
suppression resource placement record in `research/data/REGISTRY.yaml`, and
obtaining one is an information-disclosure request, which is a human gate
(WJ-010). The obvious substitute, distance to the nearest station or a
road-class accessibility index, is a function of the road network, and the road
network is the barrier layer. Controlling for it would put the exposure inside
its own control variable. A bad control is worse than an acknowledged confound,
and the pre-registration is right to refuse it.

## 3. What would have to be true for the result to survive

Written before any discriminating test is run. The requirement is that the two
worlds have observable consequences that **differ**, so each row below states
both.

| discriminator | if the objection is right (access is driving it) | if the objection is wrong (the gap is driving it) |
|---|---|---|
| **D1. Barrier type.** Rivers and ridges are barriers crews cannot drive along, so the access mechanism that produces a road's width does not produce a river's width | the width slope is present on roads and absent on rivers | the width slope has similar sign and magnitude on rivers as on roads |
| **D2. Daylight.** Korean aerial suppression does not fly at night, so the resource intensity on a given barrier differs sharply between a daytime and a night-time arrival | the width slope is present in daytime encounters and weak or absent at night | the width slope is similar in both, or differs only as far as the humidity and wind covariates already in the model would predict |
| **D3. Saturation.** During the peak hours of the 2022 Uljin and Samcheok and the 2025 Yeongnam runs, resources were committed across a front far longer than they could cover, so most segments got no attention at all | the width slope is concentrated in the hours and places where effort was concentrated | the width slope holds in the saturated windows, where most segments were unattended |
| **D4. Remoteness within the road class.** Two segments of the same road class differ in how long it takes anything to reach them | the width slope weakens as the travel time from the nearest depot rises | the width slope is flat in travel time |
| **D5. The ridge negative control.** Ridges carry zero fuel gap by construction | irrelevant to this objection, but a width effect appearing on ridges at all means the pipeline is wrong and neither world is being observed | ridges contribute only through the slope reversal at the crest, as designed |

**What would falsify the objection outright: nothing available.** No row above
can separate the two worlds cleanly, and it is important to say that here rather
than discover it in item 6. D1 is confounded by rivers differing from roads in
riparian fuel, valley position and humidity. D2 is confounded by night changing
fire behaviour through exactly the humidity and wind covariates the model already
carries, so a night contrast is partly absorbed before it is read. D3 requires a
saturation window defined from the operational record, which this program does
not hold. D4 uses the routing layer at `src/wildfireguardian/routing/rescue.py`,
which is computed on the road network, so it inherits part of the bad-control
problem that sank the proximity proxy, though not all of it: travel time from a
depot varies along a single road of constant width, which is the variation the
proxy was rejected for lacking.

So the honest statement of item 3 is: **the objection survives every
discriminator this design can run, and the best available outcome is a scope cut
rather than a refutation.** That is written here, before the tests, so that a
scope cut arrived at later cannot be presented as a discovery.

## 4. The discriminating test, with its reading rule fixed in advance

**Inputs.** The primary fit of the pre-registration's section 7.2 on the
pre-registered leave-one-complex-out folds, re-estimated on three strata. All
three are pre-registered here and all three are reported whichever way they come
out. None is run more than once and the count of fits is recorded under P10.

- **T1, the barrier-type contrast (D1).** The width slope on roads against the
  width slope on rivers, as a posterior contrast with its interval. This is the
  test the pre-registration already carries in its section 12.4.3.
- **T2, the daylight contrast (D2).** The width slope in encounters whose fitted
  arrival falls in local daylight against those in local darkness, using the
  local solar hour covariate the design already holds. This test is **not** in
  the pre-registration and is a condition of the sign-off record (R6). Its two
  outcomes are written down here before it is run.
- **T3, the travel-time gradient (D4).** The width slope as a function of ingress
  corridor travel time from the nearest depot, from the read-only rescue routing
  layer. Reported as an interaction with its interval, and flagged as partially
  confounded for the reason in item 3.

**Metric.** The posterior contrast in the width slope between strata, on the
standardised `log(W_eff + 1)` scale, with its credible interval, computed from the
errors-in-variables posterior and never from the naive one. Reported beside the
smallest effect of interest, expressed as a change in modelled breach probability
over the pre-registered width contrast at sample medians.

**The reading rule, fixed now.**

> **If** the width slope on rivers has the same sign as on roads and their
> posterior contrast is centred near zero, **and** the daylight and night slopes
> do not differ by more than the smallest effect of interest, **and** the
> travel-time interaction is centred near zero, **then** the objection is
> weakened, and the direction may say that the association is not explained by
> the access mechanisms this design can observe. It may still not say the effect
> is physical.
>
> **If** the width slope is present on roads and its interval excludes the river
> slope, **or** the daytime and night slopes differ by more than the smallest
> effect of interest, **or** the travel-time interaction excludes zero in the
> direction where better access means more holds, **then** the objection stands,
> and the width coefficient is reported as a measure of operational barrier
> performance with the access mechanism named in the same sentence.
>
> **If the outcome falls between those two**, which on my prior is what will
> happen, **then** the claim is scoped to: an association between a barrier's
> measured width and the absence of a lee-side burn, given that a front arrived,
> for barriers as they are actually used in Korean wildfire operations, which
> includes their use as access routes and as anchor lines. That sentence is the
> ceiling. Nothing about the effect of the fuel gap on flame propagation, nothing
> about widening an existing road, nothing about what a road of any width would
> do without crews on it, and nothing that supports a counterfactual about
> construction policy.

**A pre-condition on all three tests.** None of T1, T2 or T3 is run, and no
scope-cut sentence is written, unless the width curve is published at all. The
pre-registration's gates W1, M1 and P1 can each veto the curve, and a stratified
contrast computed on a covariate that failed its own measurement validity check
(instrument 5 of section 11.5.5) is a contrast between two numbers that mean
nothing. The order is: measurement validity, then gates, then curve, then these
three tests.

**A pre-condition on the vocabulary.** The phrase "operational barrier
performance" only does work if the alternatives are mechanically blocked. Until
a claim rule and its detector exist for the assertive spellings, the scope cut is
a promise. That is condition R6 of the sign-off record and it applies to this
file too.

---

## 5. What the test actually returned

*Not written. No result exists. This section is appended after the run, with the
numbers, their split fingerprint and their staging id from
`research/eval/numbers_staging.json`, and items 1 to 4 above are not edited when
it is.*

## 6. Verdict

*Not written.*

## 7. The sentence the claim becomes

*Not written.*

---

## Appendix. A6's prior on the outcome, recorded 2026-09-16

Not part of items 1 to 4. A prediction, kept so that it can be scored later.

1. **The modal outcome of this direction is not a verdict on the objection at
   all.** It is that no breach curve is published. Chaining the design's own
   gates: gate W1 needs 25 road segments at or above 6 m of cleared width and 25
   below; gate G1 needs 150 labelable segments and 30 held; gate M1 needs an
   attenuation factor at or above 0.70 and 60 hand-measured segments, which needs
   pre-fire orthoimagery that currently has no registry entry. The
   pre-registration's own planning estimate is order 10^2 labelable segments with
   held segments in the low tens. My prior is that at least one of W1, G1 and M1
   fails, the round delivers the labelled encounter table and the indeterminate
   accounting, and the recorded outcome is "not resolvable at the achieved
   measurement precision and sample size". I rate this more likely than all other
   outcomes combined.
2. **Conditional on a curve being published, the objection ends in a scope cut**,
   for the reasons in item 3. I do not expect any of T1, T2 or T3 to be decisive,
   and I expect T1 to be the least informative of the three despite being the one
   already pre-registered, because the river sample will be small and rivers
   differ from roads on several axes at once.
3. **The attenuation objection may overtake the confounding objection as the one
   that ends the direction.** If the recoverability simulation of instrument 2
   returns a low number before any labelling, then the design is known to be
   unable to see an effect of the size that would matter, and the confounding
   question never gets asked. That would be the cheapest true result this
   direction can produce and it should be pursued first.
4. **The effective sample size, not the row count, is what a reviewer will attack
   after the confound.** Five fires, a fire random effect with five levels, and
   segments clustered on barrier lines. A hierarchical model over five groups
   carries much of its apparent precision in the prior, which the design knows
   (section 7.5) and handles about as well as it can be handled.

Scored later against what actually happened. A prior that was wrong is evidence
that the check worked.
