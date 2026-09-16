# Sign-off record: roads, PREREGISTRATION.md v0.1b

```yaml
signoff:
  direction: roads
  prereg_file: research/roads/PREREGISTRATION.md
  prereg_version: v0.1b
  prereg_author: A3
  reviewer: A6
  date: 2026-09-16
  round: 2
  state: refused
  supersedes: null
  outcome_seen: false
  fits_permitted_on_real_labels: false
```

**State: `refused`.** Per `research/eval/SIGNOFF.md` section 3, a refusal carries
no blame and is a normal event. The usual path is a revised pre-registration in
the same round, and that is what is expected here. The direction may continue
everything in the unsigned column of `SIGNOFF.md` section 0: acquisition,
pipeline, loaders, the segment layout script, the provenance audit script, the
ridge derivation, prior predictive checks and the recoverability harness. It may
not fit on real labels, and no number from it may be staged.

---

## 0. The verdict, in one paragraph

This is a serious document and the reasoning in its three new sections is the
best work the program has produced so far. Section 11.5 is a real solution to the
flat-curve problem rather than a statement of it, section 7.7.1 names the right
unidentified parameter and fixes in advance what is reported when it stays
unidentified, and section 12.4 correctly refuses the obvious bad control. Those
three were the conditions of round 1 and two of them are met outright. The
refusal does not rest on any of that. It rests on three things. **First, the
label rule is not executable as written.** Its own author records the smoke mask
as open, and my boundary-scenario pass found eight further points where the text
did not determine the answer, including one arithmetic problem, the `SIDE` rule
of section 5.1, that on the document's own geometry would make almost every
segment indeterminate, and one unit problem, `tau_burn` of 0.10 applied to
RdNBR, that would put the burned threshold on the wrong scale. **Second, two
CRITICAL leakage items end the pass at `unresolved`**, B4 (the buffer distances
carry no declared sensitivity grid although section 12.8 asserts that they do)
and B3 (no sensitivity analysis over the arrival rule, and no check of whether
arrival exclusions cluster on the wide barriers). My own rule in `LEAKAGE.md`
step 4 is that an unresolved CRITICAL refuses the sign-off, and I am not going to
suspend it on the first pre-registration it applies to. **Third, six of the
sixteen required items are absent rather than vague**: P6, P10, P11, P12, P13 and
P16 have no text in the document at all, and the compliance block of `SIGNOFF.md`
section 2 is missing. P16 in particular cannot be repaired after a fit without
rewriting the output layer, which is why it is a pre-registration item.

None of this is a judgement that the hypothesis is uninteresting or that the
design is unsalvageable. Most of it is a round of writing. The label rule is the
part that is real work.

---

## 1. What A3 asked me to judge, judged

A3 responded to the two round-1 conditions and to the suppression objection. I
was told not to accept a section because it exists. Here is the reading.

### 1.1 Section 11.5, the reading rule for a flat breach curve: **accepted, with two repairs**

This is the one that had to be right and it is substantially right. The structure
is correct in the way that matters: three of the five instruments run before any
label exists, so the discrimination between a true null and an attenuated slope
is not made by looking at the flat curve. Instrument 5 is a genuinely good idea
that I did not ask for and would not have thought of in that form: separating a
noisy ruler from a broken ruler is a distinct failure mode with a distinct test,
and the ridge negative control is free and sharp. Section 11.5.6 puts the four
conditions in one place and makes the informative-null claim conjunctive rather
than a matter of reading. I accept the section.

Two repairs are required and they are both technical rather than structural.

**(a) `kappa` is computed on the wrong variable.** Sections 6.3.4 and 11.5.1
define the attenuation factor for classical additive measurement error on a
covariate entering a regression linearly. The covariate that actually enters the
model is `log(W_eff + 1)` with `W_eff = W_cleared / sin(max(theta, 15 deg))`
(section 6.5). Additive classical error on `W_cleared` is neither additive nor
classical after a division by `sin(theta)` and a logarithm, and the induced error
on the fitted covariate is heteroscedastic: its size depends on `W_cleared` and
on `theta`, so it differs segment by segment, and it is largest for the narrow
barriers at grazing angles that carry most of the leverage. The errors-in-
variables model of 6.3.4 item 1 handles this correctly, because it propagates
`sigma_u` through the transform inside the fit. What does not handle it is
`kappa`, which is reported as a headline diagnostic and which is the operative
quantity in gate M1. As written, M1 gates on a number computed on a scale the
model does not use. I checked the two spellings of `kappa` against each other and
they are algebraically identical, which is worth saying because that kind of
thing is usually wrong: with `sigma_obs^2 = sigma_x^2 + sigma_u^2`, section
11.5.1's `(sigma_obs^2 - sigma_u^2)/sigma_obs^2` equals section 6.3.4's
`sigma_x^2/(sigma_x^2 + sigma_u^2)` exactly. The problem is not internal
consistency, it is the scale.

**(b) Instrument 2 simulates only the non-null, but the informative-null claim is
gated on exclusion, not on detection.** Recoverability as defined in 11.5.2
simulates outcomes under a true slope equal to the smallest effect of interest
and counts the fraction of fits reaching the F1 threshold. That is detection
power, and it is the right number for F1. It is the wrong number for the middle
row of instrument 4, which is the row that makes a null publishable. That row
requires the disattenuated interval to **exclude** the smallest effect of
interest, and a design can have adequate power to detect an effect while having
almost no ability to exclude one, because exclusion depends on the width of the
interval at a point away from zero rather than on the posterior mass on one side
of zero. As the document stands, section 11.5.6 can be satisfied by a design that
was never shown capable of producing the exclusion it is claiming. The repair is
one more simulation arm at the same 500 draws.

### 1.2 Section 7.7, what the design cannot identify: **accepted**

This is the item I asked for and it does more than the item required. It names
the right parameter, it explains why the problem is structural rather than a
sample-size problem, it explicitly refuses the dishonest fix of a tighter prior
on `p_spot`, it names the different-support evidence that would identify the
split, and then it fixes in advance the four things that are reported if the
split stays unidentified, including the one that costs the most: renaming the
flame arm's coefficients as coefficients of a combined breach model, in the
abstract and not in a limitations paragraph. That last item is what makes 7.7.1
a solution rather than a disclosure. I accept it without conditions on its
substance.

One drafting defect, small but it sits in a pre-registered failure condition. F4
fires on "the ember jump parameters" having posterior standard deviations above
0.8 times their prior standard deviations. Section 7.3 identifies `lambda`, the
Poisson rate, as the parameter expected to be weakly identified and as the hard
part. "Jump parameters" reads naturally as `mu_jump` and `sigma_jump`, which are
the two parameters most likely to be adequately identified if there are any spots
at all, because a distance distribution is easier to pin than a rate. So F4 as
worded could fail to fire in the exact case it exists for. F4 must name its
parameters by symbol.

### 1.3 Section 12.4, suppression confounding: **accepted as far as it goes, and it does not go far enough**

What is right: the mechanism is stated in its specific form rather than as a
general caveat about observational data, the proximity proxy is rejected with the
correct reason (it puts the exposure inside its own control variable), the
roads-against-rivers comparison is pre-registered with both of its possible
outcomes written down in advance and labelled weak, and 12.4.4 gives a scope cut
that changes what the direction may say rather than only how it says it.

I asked myself whether "operational barrier performance" is a real scope cut or a
rename. It is real. It forecloses the counterfactual reading, which is the
reading a county planner would otherwise take by default, and 12.4.4's "cannot be
read as" list names the four wrong readings explicitly. So B2 can end this pass
at `present` with an accepted scope cut rather than `unresolved`, which is what
`LEAKAGE.md` step 4 requires.

Two things are missing and both are conditions.

**(a) The vocabulary is a promise, not a mechanism.** Section 12.4.4 says the
distinction is "enforced in the same way as the claim rules: a fixed vocabulary,
used everywhere or nowhere". The claim rules are enforced by
`research/shared/check_research_claims.py`, which has no rule for this
vocabulary. A fixed vocabulary that nothing checks lasts until the first author
who writes a figure caption in a hurry. There must be a rule in
`FORBIDDEN_CLAIMS.md` with a detector, firing on the assertive spellings
("barrier effectiveness", "the effect of width", "wider roads hold fires") and
sparing the permitted one. I do not own that file or that script, so this is a
condition on A3 and the orchestrator and not something I will write into
compliance myself.

**(b) The design holds a second discriminator and is not using it.** Item B2 of
my own checklist names "time of day as a proxy for helicopter availability" as a
candidate partial mitigation, and section 6.2 already carries local solar hour of
arrival as a covariate. Korean aerial suppression does not fly at night. So the
day-against-night contrast in the width slope is a discriminator that costs
nothing, uses a covariate already in the design matrix, and is not confounded
with the road network in the way the proximity proxy is. It is weak, for the
obvious reason that night also changes fire behaviour through humidity and wind,
and both of those are already covariates, which is exactly why it is worth
pre-registering rather than discovering. Its two possible outcomes must be
written down in advance the way the rivers comparison's were. A discriminator
noticed after the fit is worth nothing.

---

## 2. Item verdicts, P1 to P16

`pass` means the acceptance test in `SIGNOFF.md` ran and succeeded. `fail` means
it ran and failed, or the item has no text to run it against.

| item | verdict | one line |
|---|---|---|
| P1 hypothesis in falsifiable form | **pass** | section 1.3 states direction and conditioning set; 1.5 gives five failure conditions. I wrote both a supporting and a refuting result sentence from the text without strain |
| P2 unit of analysis | **conditional pass** | one 100 m segment, clustering by fire complex and barrier line both named, effective count reported beside the raw count (10.6). The two numbers are given as orders of magnitude ("order 10^2", "in the tens") rather than as numbers, which is honest at this stage but must become numbers at the labelled table before the fit |
| P3 label rule | **fail** | section 3 below. The smoke mask is open by the author's own statement, and eight further points are undetermined by the text |
| P4 covariates and sources | **conditional pass** | section 6.2 is a table with source, definition and notes, and 6.1 is a genuine firewall with a committed audit script. Missing: the knowable-at column required by P4, and the explicit yes or no column for "derived from anything that touches the label". The firewall makes every answer no, so the column is cheap, but P4 asks for it per covariate and the audit script is the thing that will need it |
| P5 model form | **pass** | likelihood, link, full parameterisation, priors each justified, random effects and what they absorb, convergence gates fixed in advance with the consequence of failure, and an identifiability paragraph (7.7) that names an unidentified parameter. This item is met better than the protocol requires |
| P6 held-out sets named in advance | **fail** | section 4 below. No call, no keyword arguments, no fingerprint |
| P7 primary metric | **conditional pass** | one metric, named, proper, with the evaluation frame required by RC-008 attached in 10.3. Missing: how its uncertainty is computed, and the statement that the resampling unit is the cluster. P7 requires both |
| P8 simple baseline | **pass** | B0, B1, B2 each implementable in under an hour, B1 named primary, and the margin fixed now at 4 of 5 folds and 0.02 nats. The margin is a number and the rule can fire against the author |
| P9 failing condition | **pass, with a note** | section 5 below |
| P10 stopping rule and multiplicity | **fail** | no text. The document does not say how many model variants will be fitted, what happens when the first fails to converge beyond "reparameterisation", what the comparison family is, or that the count of fits before the reported one is recorded |
| P11 leakage self-audit | **fail** | no text. The author's item-by-item verdicts do not exist, so the comparison between the two lists, which the protocol says is itself the information, cannot be made. Section 12 addresses seven traps well but is not the checklist |
| P12 data provenance | **fail** | no sha256, no per-dataset status table in the pre-registration. Worse than pending: the orthoimagery that carries the primary covariate has no registry entry at all |
| P13 compute and feasibility | **fail** | no expected wall-clock for the full fit or the cross-validated fit, and no list of what is cut if it does not fit. "One laptop, no GPU" is the constraint, not the estimate |
| P14 scope declaration | **pass** | Korea only stated, and each of the five foreign or non-Korean sources carries the sentence that it supplies a method and that its data is not used. Section 6.5's treatment of the Swedosh validation widths is exemplary: it separates what follows methodologically from what follows substantively, which is nothing |
| P15 what the result will not say | **pass** | 12.4.4's "cannot be read as" list, 1.4's estimand statement, 6.7's ridge caveat and 7.7.1 item 4. This is the item the poster will quote and it is written |
| P16 shape of the result artifact | **fail** | section 6 below. No artifact path, no key paths, no staging file |

Compliance defects outside the sixteen items, both mechanical:

- the `prereg:` YAML block required by `SIGNOFF.md` section 2 is absent, so
  compliance cannot be checked without reading prose, which is what the block
  exists to prevent;
- the file is at `research/roads/PREREGISTRATION.md` rather than at
  `research/roads/PREREG_roads_2026-09-16.md`. The protocol's naming exists so
  that a v0.1 and a v0.2 can both exist unedited, and a single file called
  PREREGISTRATION.md is a file that gets overwritten. Section 16's change table
  is not a substitute, because the table is inside the file it is versioning.

This record is filed at `roads_v0.1b.md` rather than at the protocol's
`roads_<prereg date>_v<n>.md`, on instruction, and the divergence is noted here
so the ledger row is not read as a third naming convention.

---

## 3. P3, the label rule: the boundary-scenario pass

The protocol says I label ten units blind from the written rule alone. Without
imagery I cannot do that literally, so I did the strongest available version: ten
written scenarios placed at the rule's own boundaries, each applied by following
sections 4, 5.1 to 5.6 as written, recording every point where the text did not
determine the answer for me. Each such point is an underspecification. The
protocol's acceptance test refuses the item at more than one disagreement in ten.
I have eight scenarios out of ten in which the text did not determine the answer.

The scenarios were written before I read section 15, so that the "blocked on A1"
answers could not pre-excuse them.

| # | scenario | the rule's answer | determined? |
|---|---|---|---|
| S1 | encounter; `f_lee` = 0.49 on the primary index; lee patch touches the inner exclusion boundary; attribution passes | `MID` | **yes.** The 0.10 and 0.50 cut points are unambiguous and the tie-break direction ("at or above") is stated on both |
| S2 | usable fraction 0.65 in the lee band, 0.92 in the windward band | **undetermined** | **no.** Section 4.5 makes a segment *ineligible* below 0.60 usable in either band. Section 5.5 makes it *indeterminate* with code `CLOUD` below 0.70 in either band. At 0.65 both clauses apply and they put the segment in different accounting classes, which section 13 item 6 reports separately. I had to choose |
| S3 | `f_lee` = 0.62; the lee patch reaches the main burn only by a path around a barrier terminus 480 m away; earliest detection inside the lee patch is 6.5 h after the fitted windward arrival | **undetermined** | **no.** Section 5.6's two bullets and its closing sentence disagree. By the bullets the attribution test fails (bullet 2 fails at 6.5 h against `delta_flank` of 6 h), giving `FLANK`. By the closing sentence `FLANK` requires the terminus to be **more than** 500 m away **and** the timing to fail, and 480 m is not more than 500 m, giving `CROSSED`. Worse, bullet 1 is vacuous as written: it is satisfied when the patch connects across the lee band **or** by a path leaving the neighbourhood, and flanking is the second of those, so bullet 1 passes for every case including the ones the test exists to catch |
| S4 | as S3, but there is **no** VIIRS active-fire detection anywhere inside the lee patch | **undetermined** | **no.** Bullet 2 is a condition on "the earliest active-fire detection inside the lee patch", and there is none. The rule has no branch for an empty set. This is not an edge case: the lee analysis band is 40 m wide and a VIIRS pixel is 375 m nominal, so a lee burn confined to the band will usually carry no detection of its own. On my reading the attribution test is inoperative, and therefore `CROSSED` is unreachable, for the majority of segments |
| S5 | ridge barrier; `W_cleared` = 0 by construction (section 3.1); front approaches at 40 degrees | **undetermined** | **no.** Section 6.3.4 makes `W_true` a latent parameter with measurement error `sigma_u`. A ridge's zero is exact, not measured. If the errors-in-variables term is applied to ridges then `W_true` for a ridge has posterior mass on negative widths and `W_eff` is undefined there; if it is not applied, that exemption is not written. Section 11.5.5 also uses ridges as a negative control, which only works if their width is treated as exact |
| S6 | encounter; windward burned fraction exactly 0.80; lee band 45 per cent bare rock and 55 per cent standing forest | **undetermined** | **no.** C1's "at least 0.80" is determined. Section 4.5's first bullet makes a segment ineligible when "the lee-side band is not burnable", with no fraction threshold. At 45 per cent non-burnable I had to decide whether that clause is all-or-nothing, majority, or any-presence. The three give three different eligible sets, and the choice interacts with the label, because non-burnable pixels are also not burned pixels |
| S7 | `f_lee` = 0.52; the lee burned patch starts 25 m from the barrier edge and does not touch the inner exclusion boundary | **undetermined** | **no.** Not `HELD` (`f_lee` is above 0.10), not `CROSSED` (the contiguity clause fails), so `INDETERMINATE`, which section 5.5 says is "always with a reason code". No code in the table covers it: `MID` is defined as `f_lee` between 0.10 and 0.50, and the other seven describe other conditions. The reason-code list is not exhaustive over the rule's own complement, and this is exactly the case section 5.3 cares about, because a detached lee burn inside 50 m is neither the flame arm's event nor the ember arm's |
| S8 | two bands in different 임상도 forest-type classes, pine against mixed | **undetermined** | **no.** Section 5.4 makes fuel discordance a binary flag entering as a covariate. Section 5.5 gives a reason code `DISCORD` for "fuel discordance beyond the pre-registered limit". No limit is pre-registered anywhere in the document, and a binary flag has no "beyond". Either the flag is a covariate or it is an exclusion, and the document does both without saying where the line is |
| S9 | a forest road running 45 m from a stream in a valley bottom, both mapped, both segmented | **undetermined** | **no.** The road's lee analysis band (10 m to 50 m from its edge) overlaps the river's windward band. Nothing in sections 3, 4 or 5 says what happens when two barriers' bands overlap, whether one lee burn can label two segments, or which barrier a spot between them is attributed to. This configuration is common in Korean mountain valleys, where forest roads follow streams. It is also an `A5` near-duplicate route that the barrier-line random effect of 10.6 does not catch, because the two segments sit on different barrier lines |
| S10 | `f_lee` = 0.08, pre-fire NBR in the lee band near zero (recently thinned, non-stocked) | **undetermined** | **no.** Two separate problems. First, `tau_burn` is 0.10 and is taken from the Key and Benson dNBR scheme, but section 5.5 applies the burned threshold "on the primary index", and section 5.4 makes the primary index RdNBR. A dNBR break point is not an RdNBR break point: RdNBR is dNBR divided by the square root of the absolute pre-fire NBR, so on unscaled NBR the two differ by a factor of roughly 1.3 to 1.6 over normal forest and by much more elsewhere. Second, that divisor goes to zero as pre-fire NBR goes to zero, so RdNBR is unbounded exactly on the non-stocked and sparse classes that section 6.2 uses as the lee-fuel reference category. No floor on the divisor is specified |

### 3.1 The one that is arithmetic rather than drafting: the `SIDE` rule

Section 5.1 assigns windward and lee from the local arrival-time fit, and then:
"If the two sides' fitted arrival times differ by less than the fit's own
standard error, the side assignment fails and the segment is indeterminate with
reason `SIDE`." That is a clean, checkable rule, and it is the right instinct,
because taking the windward side from wind direction would mislabel upslope runs.
The problem is the scale it is checked at.

The two analysis bands run from 10 m to 50 m from the barrier edge on each side,
so their centroids are about 60 m apart plus the barrier width. Section 6.4 fits
a weighted local plane to the acquisition times of active-fire detections within
1 km, requiring at least 5 detections spanning at least 2 distinct acquisition
times. Taking the document's own geometry and a range of plausible spread rates,
the difference in *fitted* arrival time between the two band centroids is:

| spread rate | gap across a 0 m barrier | across a 6 m road | across a 12 m road |
|---|---|---|---|
| 0.3 km/h | 12.0 min | 13.2 min | 14.4 min |
| 0.5 km/h | 7.2 min | 7.9 min | 8.6 min |
| 1.0 km/h | 3.6 min | 4.0 min | 4.3 min |
| 2.0 km/h | 1.8 min | 2.0 min | 2.2 min |
| 3.0 km/h | 1.2 min | 1.3 min | 1.4 min |

Now the denominator. The plane has three parameters and C4 admits a fit with 5
detections at 2 distinct acquisition times, leaving 2 residual degrees of
freedom. VIIRS acquisition times are not spread continuously: they arrive in
discrete overpass epochs hours apart, and every detection in one overpass carries
essentially one timestamp. So the residual of a plane fitted over a 1 km
neighbourhood is dominated by the deviation of the real front from a plane across
that kilometre, which at these spread rates is tens of minutes at best. The fit's
standard error cannot plausibly be smaller than the 1 to 14 minute quantity in
the table, and will normally be an order of magnitude larger.

**Applied literally, the `SIDE` rule fails at essentially every segment, and the
study produces no labels at all.** This is not a prediction about the data. It
follows from the document's own buffer geometry, its own minimum detection
requirement, and the physical revisit structure of the sensor it names. It is
also fixable: the side assignment does not need the arrival-time *difference*
across the barrier to be resolved, it needs the *sign of the fitted gradient
projected onto the barrier normal* to be resolved, which is a test on the
gradient's own uncertainty over the 1 km neighbourhood and not on a 60 m offset.
But that is a different rule from the one written, and I am not going to write it
into A3's document.

### 3.2 The smoke mask, Q5

Still open. Section 5.2 says "The smoke mask rule is a pending item in
`OPEN_QUESTIONS.md` and must be settled before the signature", and Q5 says
"Decides. A6, and it must be closed before the signature." So the document is
explicit that it is not ready on this point, and I agree with its own assessment.

Is it fatal? It is fatal to the signature and not to the design. The reason it
matters more than a missing threshold usually would is the bias direction, which
A3 has correctly identified: undetected smoke suppresses the post-fire NBR
depression, which lowers dNBR, which lowers `f_lee`, which pushes segments toward
`HELD`. The label that smoke manufactures is the label the hypothesis predicts.
That is the one direction of bias a design testing this hypothesis cannot afford
to leave undefined, and it is why Q5 is not a detail.

**My ruling on Q5.** I ratify option 2 as the route and I reject option 3
outright, for A3's own reason: a hand-drawn mask puts an analyst inside the label
path, and section 12 spends its length keeping analysts out of it. Option 1 is
acceptable only as a declared fallback with the bias sentence in the abstract, as
A3 proposes. But ratifying the route does not close the question, and this is the
part A3 must do rather than me: **a rule that says "an aerosol threshold fixed
before any label is computed" is not a pre-registered rule, because the number
lives outside the frozen document.** The revised section 5.2 must name the band
(the Sentinel-2 L2A product carries an aerosol optical thickness raster, so the
input exists), the threshold value, the resampling to the analysis grid, whether
a pixel above threshold in either scene is unusable or only in the post scene,
and a declared sensitivity grid over the threshold with every value reported.
Then the fallback to option 1 must have a trigger stated in advance, so that the
choice between option 2 and option 1 cannot be made after seeing which of them
leaves more segments labelable.

I am naming the route, which is ratification of A3's own recommendation. I am not
writing the rule, because a label rule I authored is a label rule I cannot sign.

### 3.3 The second pass required by P3

P3 also requires a second pass over at least thirty units by a path the author
did not write, with the disagreement rate going into the pre-registration rather
than into a later footnote. The document has no such pass and no plan for one.
The width measurement has its duplicate study (6.3.3) and that is good, but the
duplicate study measures the *covariate*, not the *label*. There is no
inter-rater or inter-path check on the label rule at all. Once the rule is
executable, thirty segments must be labelled by a second path and the
disagreement rate must appear in the document.

---

## 4. P6, the split fingerprint

I re-ran the call. The result is that there is nothing to compare against: the
document names the five folds in prose (section 10.1) and contains no call, no
keyword arguments and no fingerprint. The string "fingerprint" does not appear in
it, nor does "splits.py".

The folds A3 names are the correct ones, and the complex rule of section 2.2 is
adopted verbatim from the repository, which is right and which I want on the
record as a point in the document's favour: the 의성 and 안동 complex is one fold,
and 영덕 2025 joins that fold rather than becoming a sixth. That matches
`PRIMARY_SPLITS["roads"]` and `FIRE_COMPLEXES` exactly. Nothing in the document
lets the modeling agent choose the scheme at fit time, and section 10.1's
sentence about standardisation constants, hyperparameters, thresholds and the
digitising error all being computed inside the training folds is the right
sentence. So the *substance* of P6 is met. What is missing is the mechanism that
makes it checkable afterwards, which is the whole reason the item exists.

Running `leave_one_complex_out` on the five canonical fire ids in the order of
section 2.1 gives five folds with complex-level fingerprint

    844e82d06b534901590bc660f62cb49bb2b57279be055e112c93d801098d2cd5

and that value must go into the document. There is a trap here that A3 should be
told about rather than left to discover, because it will silently break the
fingerprint later. **The fingerprint is a function of row order**, since a `Split`
holds positional indices. Concretely:

| what is hashed | fingerprint |
|---|---|
| the five complexes, section 2.1 order | `844e82d0...` |
| the same five, reversed | `7233bb94...` |
| three segments per fire, grouped by fire | `d16ffd5d...` |
| the same rows, interleaved | `9f50f8a2...` |

The unit of analysis in this direction is the segment, not the fire, so the
fingerprint that a result will carry is a segment-level one, and it is pinned
only when the segment layout is pinned. That is workable and it is in fact
already half done, because section 3.2 commits the layout script to run and its
output to be committed before any label is computed. So P6 is cleared by two
values, not one: the complex-level fingerprint above, which can go into the
document today, and the segment-level fingerprint, computed on the committed
layout in its committed row order, recorded before any label exists. Both belong
in the `prereg:` block.

---

## 5. P9, the failing condition

**Pass.** F1 to F5 are real, they are written so they cannot be re-read as
success, and each names an outcome, a threshold and a reading. F2 is the one I
weight most: a pre-registered rule that hands the model of record to a width-only
logistic regression, decided by fold counts and a fixed margin in nats, is a rule
that can fire against its author and that the author cannot argue with
afterwards. Section 9's sentence that this "is a real finding and it is written
as one" is the correct attitude and it is backed by 10.4 rather than left as a
sentiment.

The note, which is not a refusal reason and belongs in the killshot rather than
in the conditions. Asked whether the failing condition "could actually occur", my
answer for F1 specifically is: probably not, and not because the effect is real.
F1 is judged on the errors-in-variables posterior and is reportable as evidence
only when M1 holds; M1 needs `kappa` at or above 0.70 and 60 hand-measured
segments; the hand measurement needs orthoimagery that has no registry entry; and
before any of that, W1 needs 25 road segments at or above 6 m of `W_cleared` and
25 below, out of a total labelable count A3 plans at order 10^2 with held
segments in the low tens. Chain those and the modal outcome of this design is not
F1 firing or not firing. It is G3 or W1 or M1 failing, and the round reporting the
labelled table with no breach curve at all.

That is not a criticism. It is what section 11.4 already says, and a design that
states its own most likely outcome as "untestable on this record" in advance is
behaving correctly. But it should be said plainly in the abstract-level framing
rather than reached by chaining five gates, and it sharpens what instrument 2 is
for: the recoverability simulation can tell the program that the answer is "not
resolvable" **before** anybody labels a segment, which is the cheapest true thing
this direction can produce. A3's own round-1 report already ranks that harness
first among the four things worth building without data. I agree, and I would go
further: it should be built and reported before the labelling starts, not beside
it.

---

## 6. P16, the result artifact

**Fail, and this is the cheapest of the six failures to fix and the most
expensive to fix late.** The strings `numbers_staged`, `json_path`, `entry(`,
`results/` and `sha256` do not appear in the document. Section 13 lists nine
outputs and closes with "Every number in these outputs is registered before it
appears on any surface", which is the right intention pointed at the wrong
mechanism: `scripts/build_numbers.py` registers a number only when `source_file`
is a committed JSON artifact and `json_path` is a dotted path into it, so an
output that is a figure, a table or a sentence cannot be registered at all.

The acceptance test is that I can point at a key path for the primary metric and
for the baseline before the fit exists. I cannot point at either. What the
revised document must name is in `NUMBERS_PROTOCOL.md` section 5: the artifact
path, the dotted key path of every quantity that might be quoted, and the
per-direction staging file in the registrar's own `entry()` shape. At minimum,
and this list is not exhaustive, key paths are needed for the primary metric and
its interval, the same for B1, the width posterior mean and interval on both the
naive and the disattenuated fits, `kappa` and its interval, the recoverability
fraction, every gate's boolean outcome (G1 to G3, W1, M1, P1), the label
accounting counts by reason code by fire by barrier type, and the effective
independent-encounter count.

---

## 7. The twelve roads leakage items, run independently

Run against the document by me, before reading section 12, so that the two lists
could differ. They could not be compared afterwards, because P11 means A3's own
list does not exist, and that comparison is information this round has lost.

| id | severity | verdict | justification |
|---|---|---|---|
| B1 severity covariate is partly its own label | CRITICAL | **mitigated** | Section 6.1 is a hard constraint with a committed audit script that fails the build, not a caution, and it correctly extends to **pre-fire** indices because RdNBR contains pre-fire NBR. That extension is a step beyond what my own checklist asked for and it is correct. The accepted cost, a coarser fuel covariate and no spectral intensity proxy, is stated |
| B2 suppression confounded with width | CRITICAL | **present, with an accepted scope cut** | Section 12.4, judged in section 1.3 above. Accepted as `present` rather than `unresolved`, so it does not by itself refuse. Conditions C7 and C8 attach |
| B3 selection on the front having reached the barrier | CRITICAL | **unresolved** | Section 4's C1 to C4 are a genuine arrival definition and 4.5 publishes ineligible counts per fire and per reason, which is half of what B3 asks. The other half is missing: B3 requires a check of whether the exclusions **cluster on the wide barriers**, which is the thing that turns censoring into bias on the coefficient of interest, and it requires a pre-registered sensitivity analysis over the arrival rule. Section 12.8 lists the parameters it treats as researcher degrees of freedom and **none of C1's 0.80, C4's 5 detections and 2 acquisition times, or C3's 400 m footprint fallback is on the list.** These are the four numbers that decide which segments exist, and a barrier that stopped a front early is exactly the case that leaves too little heat to clear them, so the arrival rule censors preferentially against holds |
| B4 the buffer distance is a researcher degree of freedom | CRITICAL | **unresolved** | Section 5.3 fixes 10 m and 10 m to 50 m with real justification, and 12.8 asserts that "the buffer distances are all fixed in this document. The sensitivity analyses over them are declared here". **They are not.** The declared grids are `tau_burn` in {0.05, 0.10, 0.15, 0.20} and segment length at 50 m and 200 m. There is no grid over the inner exclusion or over the band's outer edge. The 50 m edge is doubly load-bearing: it is the outer edge of the label band **and** the boundary between the flame arm and the ember arm (sections 5.3, 7.1, 12.3), so moving it moves the label and re-assigns events between the two arms of the model. B4 requires the grid declared in advance with every value reported |
| B5 one scene, two sides | MAJOR | **unresolved** | Section 5.4 handles the two sides having different **fuel**, three ways, and handles it well. It does not handle the two sides having different **illumination**, which is the B5 mechanism and which is worst on exactly the barrier class this design relies on for identification: a ridge crest puts its two sides at different incidence angles, and a terrain illumination difference moves NBR on both dates unequally. B5 asks for the per-side illumination difference as a recorded quantity and a check that the label rate does not track scene date or cloud mask. Neither is in the document |
| B6 adjacent segments are near-duplicates | MAJOR in Part E, CRITICAL in Part B | **mitigated** | Leave-one-complex-out primary, no random split reported anywhere, within-fire secondary splits blocked by barrier line, a barrier-line random intercept in 10.6, and the effective independent-encounter count reported wherever the raw count appears. This item is met as well as it can be. Scenario S9 above is the residual: two barriers 45 m apart are near-duplicates on different barrier lines, which the random effect does not absorb |
| B7 the fire random effect and the held-out fire | MAJOR | **unresolved** | Section 7.5 settles the prior, the sensitivity grid and the no-per-complex-claim rule, all correctly. It does not settle the thing B7 is about: when predicting a held-out complex, is `u[f]` set to zero or drawn from the hyperprior? These are two different models and the first predicts better for the wrong reason. P5 requires the primary prediction rule stated before the fit, and both reported |
| B8 the two-term product is not identified by a binary label | MAJOR | **mitigated** | Section 7.7.1, judged above. This is the best-handled item in the document. Condition C6 attaches only to F4's wording |
| B9 detection timing cannot attribute an overnight crossing | MAJOR | **unresolved** | Section 6.4 defines the arrival-time fit and retains its residual standard error, which is the raw material. But the weather covariates of 6.2 are taken at "the arrival hour" as if that hour were known, with no propagation of the fit's own uncertainty into them and no count of segments with an ambiguous arrival hour. B9 asks for the rule, the propagation and the count. Section 3.1 above shows the fit's timing uncertainty is large, so this is not a small correction |
| B10 the barrier map conditions the sample | MINOR | **partly mitigated** | The OpenStreetMap hydrography completeness audit against a DEM-derived channel network at matched flow accumulation (section 3.1) is a good, concrete answer for rivers. Nothing equivalent exists for roads, where mapping completeness varies with ownership and management, and a better-mapped forest is a better-managed one. Recorded, not a condition |
| B11 the claim under test must not enter as a cut point | MAJOR | **clean** | Width enters continuously as `log(W_eff + 1)`, no 6 m bin exists anywhere in the design matrix, and F3 answers the 6 m question as a posterior contrast read off the fitted curve. Correct, and it is the kind of thing that is usually got wrong |
| B12 measured width, and attenuation biases the test toward the null | CRITICAL | **mitigated, conditionally** | Sections 6.3, 6.3.3, 6.3.4, 11.2, 11.3 and 11.5 together are a complete and honest answer, and the asymmetric F1 is the right structural response. I checked A3's sample-size arithmetic independently and it holds: the relative standard error of an estimated standard deviation from n paired differences is 16.2 per cent with 20 pairs, 13.1 per cent with 30 pairs and 10.1 per cent with 50 pairs, and detecting a 0.4-sigma bias at 80 per cent power and 5 per cent two-sided needs 49.1 pairs. The document's "about 13 per cent", "about 16 per cent", "near 50" and "near 49" are all correct. The mitigation is conditional on repairs (a) and (b) of section 1.1, and on the orthoimagery existing at all |

**Cross-cutting items worth recording.** A1 is clean: `z(.)` is standardised on
training folds only, the gradient-boosted grid is searched by nested CV inside
training folds, and 10.1 lists the digitising error estimate among the quantities
computed inside the fold. That last one contradicts section 6.3.4, which
estimates `b` and `sigma_u` jointly inside the fit from a subsample stratified
across all five complexes; the contradiction is small, since the hand measurement
is label-blind and outcome-free so it is not leakage in either reading, but the
document should say which it means. A2 is clean: priors are fixed here and the
comparison model's grid is committed. A7 and P10 is the gap: no count of fits.
A11 is the P7 gap: no resampling unit for the primary metric's uncertainty. A12
is a minor open point: `mu_jump` at Normal(log 200 m, 1) is a plausible import
from non-Korean spotting literature, and if it is one, A12 requires the flat-prior
sensitivity run and the declaration. If the 200 m is A3's own judgement, say so.

**Refusal arithmetic.** Two CRITICAL items, B3 and B4, end this pass at
`unresolved`. `LEAKAGE.md` step 4: "Any item marked CRITICAL that ends the pass
at `unresolved` or `present` without an accepted scope cut refuses the sign-off."
That is the rule and it applies.

---

## 8. The numbers A3 asked me to ratify

### 8.1 The smallest effect of interest: **not ratified at 0.10. Set at 0.05, with two changes to how it is stated.**

A3 asked for this one specifically and identified the incentive correctly:
setting it too large makes an uninformative null easy to declare as an
informative one. That is the right frame, and it is what decides the ruling.

**The unit is wrong before the level is.** The effect is stated as a change of
0.10 in modelled breach probability "between a 3 m and a 9 m **effective**
width". Effective width is `W_cleared / sin(max(theta, 15 deg))`, so a 3 m to 9 m
contrast in `W_eff` is a contrast in a composite of width and approach angle, and
it maps onto a physical width only through the median angle. At a median approach
angle of 45 degrees it is a 2.1 m to 6.4 m contrast in `W_cleared`; at 25 degrees
it is 1.3 m to 3.8 m; at the 15 degree clip it is 0.8 m to 2.3 m. A county
planner does not build effective metres. They build cleared metres, and the claim
under test is stated in built metres. **The smallest effect of interest must be
stated as a contrast in `W_cleared` at the sample median approach angle**, with
the corresponding `W_eff` contrast reported beside it so the two are legible
together. The same defect sits in F3, which contrasts "6 m and 3 m" without
naming which width variable, and which therefore is a pre-registered failure
condition whose units are ambiguous. F3 and 11.5.3 also use two different
contrasts, 3 m against 6 m and 3 m against 9 m. Pick one width variable and, if
the two contrasts are both wanted, say why.

**The level.** I rule 0.05, not 0.10, for three reasons.

1. **The threshold must be set by what matters, not by what is reachable.** This
   is the whole point of instrument 3, and it is the one place where the
   temptation runs hardest in the other direction. If 0.05 turns out to be
   unreachable, the correct output is that this design cannot exclude an effect
   that would matter, reported as "not resolvable at the achieved measurement
   precision and sample size". Choosing 0.10 because 0.10 is what the design can
   see would be the circularity that section 11.5 exists to prevent.
2. **The decision it feeds aggregates.** Forest road widening is a capital
   programme over tens of kilometres, not a single-segment choice. Over a few
   hundred encounter-segments, a 5 point shift in breach probability is a
   different number of holds, and that is actionable. The single-incident
   decision, where an incident commander picks an anchor line, is not sensitive
   at either 0.05 or 0.10, because the commander uses the best line available
   regardless of its modelled probability. So the decision that this number
   serves is the aggregating one, and the aggregating one has a lower floor.
3. **The error costs are asymmetric and this is a life-safety tool.** Declaring
   an informative null at 0.10 means announcing that the record is inconsistent
   with a width effect large enough to matter while leaving an effect of 0.09 on
   the table. In a rescue-dispatch context an effect of 0.09 in breach probability
   is not nothing. The threshold below which an effect is declared not worth
   acting on should be set conservatively low precisely because the consequence
   of wrongly declaring it is that somebody stops widening roads.

**What I expect this to do, said in advance so it cannot be read as a surprise
later.** I expect recoverability at 0.05 to fall below 0.80 on the sample sizes
section 11.1 plans, and therefore I expect this design to report "not resolvable"
rather than an informative null. **That is the correct outcome and it is why
instrument 2 runs before the labelling.** The value of this direction in that
branch is not reduced: the labelled encounter table, the indeterminate
accounting, the measured width distribution and a pre-registered demonstration
that a Korean five-fire record of this size cannot resolve the question are
publishable and useful, and the last of those is a result the field does not
have. It is also cheaper to learn it before 400 segments are labelled than after.

**Reporting.** Report the equivalence reading of instrument 4 at both 0.05 and
0.10, with 0.05 as the pre-registered primary. A reader then sees the effect size
the record can exclude rather than a binary, and the informative-null sentence,
if it is ever written, carries the number it excluded inside it.

### 8.2 The recoverability threshold of 0.80: **ratified as a level, with the second arm of section 1.1(b) added**

0.80 is the conventional power level and it is the right order for this purpose.
Nothing in this design argues for moving it. Two attached requirements:

- recoverability must be reported at **both** 0.80 and the value achieved, not as
  a pass or fail, so that a design landing at 0.79 is not reported the same way
  as one landing at 0.31;
- the second simulation arm required by section 1.1(b): under a true slope of
  **zero**, over the same 500 draws and the same real geometry and real
  measurement error, the fraction of simulations in which the disattenuated
  interval **excludes** the smallest effect of interest. Call it exclusion power,
  gate it at 0.80 as well, and make the middle row of instrument 4 conditional on
  it. Detection power and exclusion power are different quantities and section
  11.5.6 currently gates a claim about the second on a measurement of the first.

### 8.3 The attenuation gate M1 at `kappa` of 0.70: **ratified as a level, refused as currently defined**

The level is defensible. At `kappa` = 0.70 the naive slope is attenuated by
30 per cent and the disattenuated estimator's variance is inflated by roughly
`1/kappa^2`, so the correction is still doing arithmetic rather than
extrapolation. Below that it degrades fast. I would not move 0.70.

Two changes to how it is applied.

- **Gate on the interval, not the point estimate.** `kappa` is estimated from 30
  repeat pairs, which section 6.3.3 correctly says gives `sigma_u` to about 13
  per cent relative. A point estimate at 0.70 therefore clears the gate about
  half the time when the truth is 0.70. M1 must be stated on the lower end of a
  declared interval on `kappa`, at a declared level. Otherwise the gate that
  exists to stop a flat curve being drawn out of a noisy ruler is itself passed
  by noise.
- **Define `kappa` on the covariate that enters the model**, per section 1.1(a).
  Propagate `sigma_u` through `W_eff = W_cleared / sin(max(theta, 15 deg))` and
  through `log(W_eff + 1)`, which makes the induced error segment-dependent, and
  report the distribution of the per-segment attenuation alongside a single
  summary. The single summary is what M1 gates on and the document must say which
  summary it is.

### 8.4 The other numbers of Q9, ruled since A3 asked

- **G1 at 150 labelable and 30 held, G2 at 60 to 150, G3 below 60 or below 10
  held: ratified.** A3 flags 30 held as its least certain number. It is the right
  order: a logistic slope on a continuous covariate estimated from fewer than
  about 30 events of the minority class is prior-dominated, which is what gate P1
  then catches anyway. The two gates are redundant in the right direction.
- **W1 at 25 segments each side of 6 m: ratified, with one change.** The 6 m
  split point for a *feasibility* count is fine and is not item B11, because it
  counts support rather than binning the covariate. But it must count in
  `W_cleared` and the document must say so, since W1 sits next to `W_eff`
  throughout section 11 and the two give different counts.
- **P1 at a posterior standard deviation below 0.8 of the prior: ratified.** A3
  says it would defend this one hardest. It is right to. It is the only rule that
  stops a curve being drawn out of a prior, and 0.8 is the conventional place.

### 8.5 The other open questions assigned to A6

- **Q1, which width is primary.** Ratified as A3 recommends: `W_cleared` primary,
  `W_surface` reported alongside, named now so the choice cannot be made to suit
  an answer, and a version bump rather than a silent swap if attachment 2-2 turns
  out to state the running surface. The Kim and Im mechanism argument in section
  14.1 is a legitimate reason to prefer the canopy gap and it is correctly
  labelled as prior art shaping a design rather than as evidence.
- **Q2, the ember arm.** Ratified: option 1, fit it with F4 as the automatic
  exit, on the strength of section 7.7.1. Option 3 is refused for A3's reason and
  I want the refusal on the record in my own words too: importing a non-Korean
  spotting rate into a Korean breach probability is foreign data entering a
  Korean fit through a prior, which is item A12 and scope rule 1.
- **Q3, one width slope or one per type.** Ratified: option 1 primary, the
  type-by-width interaction pre-registered as an always-reported secondary,
  reported as underpowered rather than as absent when it is underpowered.
- **Q4, the Key and Benson break points.** Ratified as an interim, replaced by a
  verified Korean calibration in a version bump if A7 finds one, and option 3 is
  correctly named only so nobody proposes it. But see scenario S10: the break
  point is a dNBR quantity and the document applies it to RdNBR. That must be
  fixed regardless of what A7 finds.
- **Q6, the primary metric.** A3's choice stands. Mean out-of-complex log
  predictive score is a proper scoring rule, it rewards calibration and
  discrimination together, and A3's argument that a county office acts on a
  probability is the right argument. I am not naming a different program-wide
  primary that would force a version bump here.
- **Q10, SHAP-suggested interactions.** Keep the strict rule, exactly as A3
  argues. The cost of strictness is a delayed finding; the cost of looseness is
  that the comparison model becomes a mechanism for adding terms until the
  structured model wins, which is the failure the comparison was pre-registered
  to prevent.
- **Q11, segment length.** Ratified, and the refusal belongs in the frozen
  document as A3 proposes. Shortening segments to clear a gate is manufacturing
  sample size.
- **Q5, the smoke mask.** Section 3.2 above.
- **Q7, adding 영덕 2025.** Not mine. It is the orchestrator's with A2, and the
  fold consequence is already settled correctly either way.
- **Q8, suppression records.** Not mine. It is John's, through WJ-010.

---

## 9. The reasons, in the order I would fix them

Each names what would clear it. Numbered so a revision can answer them by number.

**R1. The label rule is not executable.** Clear by: closing Q5 with a named band,
a named threshold, a named sensitivity grid and a named fallback trigger (section
3.2); restating the `SIDE` rule of 5.1 on a quantity the arrival-time fit can
actually resolve (section 3.1); naming which index `tau_burn` applies to and, if
RdNBR, giving the RdNBR threshold and a floor on the pre-fire NBR divisor (S10);
rewriting 5.6 so that its bullets and its closing sentence agree, so that bullet 1
is not vacuous, and so that a lee patch with no active-fire detection has a branch
(S3, S4); reconciling the 0.60 of 4.5 with the 0.70 of 5.5 (S2); giving the
non-burnable clause of 4.5 a fraction threshold (S6); making the reason-code list
exhaustive over the rule's complement, which S7 shows it is not; giving `DISCORD`
a limit or removing it as a reason code (S8); saying what happens when two
barriers' analysis bands overlap (S9); and saying whether the errors-in-variables
term applies to ridges (S5). Then running the second labelling pass P3 requires
over at least thirty units and putting the disagreement rate in the document.

**R2. Two CRITICAL leakage items are unresolved.** Clear by: adding the arrival
rule's four numbers to the section 12.8 sensitivity list with declared grids, and
adding the check of whether arrival exclusions cluster on wide barriers, reported
whichever way it comes out (B3); and adding a declared sensitivity grid over the
inner exclusion distance and over the 50 m band edge, with every value reported,
noting that the 50 m edge also re-assigns events between the two arms (B4).

**R3. The reading rule needs its two repairs.** Clear by: defining `kappa` and
gate M1 on `log(W_eff + 1)` with `sigma_u` propagated through the transform, and
gating on an interval rather than a point (sections 1.1(a), 8.3); and adding the
zero-slope exclusion-power arm to instrument 2, gated at 0.80, with the middle row
of instrument 4 made conditional on it (sections 1.1(b), 8.2).

**R4. The smallest effect of interest.** Clear by: restating it as a contrast in
`W_cleared` at the sample median approach angle, at 0.05, with 0.10 reported
alongside and with F3's contrast expressed in the same variable (section 8.1).

**R5. Six required items are absent.** Clear by writing P6 (both fingerprints,
the call and its keyword arguments, and the row-order convention: section 4), P10
(variant count, non-convergence branch, comparison family and correction or a
reasoned statement of none, and the recorded count of fits before the reported
one), P11 (the full 24-row checklist for this direction, with A3's own verdicts,
written before reading this record so that the two lists can differ), P12 (the
per-dataset status and sha256 table, with the orthoimagery gap named as a gap
rather than as a pending entry), P13 (wall clock for the full fit and for the
cross-validated fit, and what is cut if it does not fit) and P16 (section 6).
Plus the `prereg:` YAML block and the versioned file name.

**R6. Two smaller items from sections 1.2 and 1.3.** Clear by: naming F4's
parameters by symbol; adding a claim rule and a detector for the "operational
barrier performance" vocabulary, which is a request to the orchestrator since A3
does not own `FORBIDDEN_CLAIMS.md` or the checker either; and pre-registering the
day-against-night contrast in the width slope with both of its outcomes written
down in advance.

**R7. Three items from the leakage pass that are `unresolved` at MAJOR and are
therefore numbered conditions rather than refusal reasons**, listed here so a
revision catches them in the same pass: B5 (per-side illumination difference
recorded, and the check that the label rate does not track scene date or cloud
mask), B7 (which prediction rule for a held-out complex's random effect is
primary, with both reported), and B9 (the arrival-hour attribution rule, the
propagation of the fit's timing uncertainty into the weather covariates, and the
count of segments with an ambiguous arrival hour).

**Ordering note.** R5 is the cheapest and I would do it first in practice, in an
afternoon. I have put it fifth because the order above is by consequence, and
because R1 is the one that decides whether this design can produce a label at
all. If only one thing is done before the next round, do R1.

---

## 10. What is not a reason for this refusal

Recorded because a refusal that does not say what it is not about invites the
wrong repairs.

- **Not the pending datasets.** Every critical dataset is at status `pending`
  behind WJ-001. Under P12 that is `signed with conditions` at worst, not a
  refusal, and a pre-registration written before the data arrives is the correct
  order of work.
- **Not the small sample.** Order 10^2 labelable segments with tens of effective
  encounters is a small study, and the document says so repeatedly and honestly
  in sections 11.1, 11.2 and 11.4. A small honest study is signable.
- **Not the suppression confound.** It cannot be separated with the available
  data, section 12.4 says so, and the scope cut is accepted. Refusing a
  direction for an acknowledged and correctly scoped confound would mean refusing
  all observational work.
- **Not the likelihood that this design reports "not resolvable".** That is a
  legitimate and useful outcome, it is pre-registered, and section 11.4's refusal
  to fit anyway is the right call.
- **Not the effective-width formula being unconfirmed against the Swedosh PDF.**
  That is a real open dependency and A3 flags it, but it is a condition, not a
  refusal, and section 6.5's separation of what follows methodologically from
  what follows substantively is exactly right.

---

## 11. What happens next

A revised document at `research/roads/PREREG_roads_<date>.md`, version v0.2,
answering R1 to R7 by number. The v0.1b file is kept unedited, per `SIGNOFF.md`
section 4.

Section 4 of the protocol does not apply to this revision: no label has been
computed, no data has been looked at, and A3's statement in section 17 that no
dataset was downloaded and no number is a measurement is on the record. So v0.2
does not need the "what was seen before this amendment" section, and it should say
so explicitly rather than leave the reader to infer it.

If A3 disagrees with any of this, the path is `SIGNOFF.md` section 5: one page of
rebuttal at `research/reports/A3/<date>_rebuttal_roads.md`, one page of response
from me, and then the human gate. I will revise a reason in response to a fact
and not in response to persistence. The reason most likely to be wrong, and the
one I would most like to be shown wrong about, is the `SIDE` arithmetic in
section 3.1: if the arrival-time fit's residual standard error is in practice
smaller than the 1 to 14 minute gap that geometry gives, then side assignment
works as written and R1 shrinks considerably. I could not make that case from the
document's own parameters. A3 may be able to.

Turnaround met: one round.

---

*Written by A6 on 2026-09-16, before any label, any fit and any result. No git
command was run. Nothing outside `research/eval/` and `research/reports/A6/` was
written.*
