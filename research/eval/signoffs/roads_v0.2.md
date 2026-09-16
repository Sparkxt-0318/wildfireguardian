# Sign-off record: roads, PREREG_roads_2026-09-16_v0.2.md

```yaml
signoff:
  direction: roads
  prereg_file: research/roads/PREREG_roads_2026-09-16_v0.2.md
  prereg_sha256: 860f6ac1748ce956905ab7958a89c54a5f3d154ed19d83f800115ab3af6fa7df  <!-- forbidden-ok: 154 -->
  prereg_version: v0.2
  prereg_author: A3
  reviewer: A6
  date: 2026-09-16
  round: 3
  state: signed with conditions
  supersedes: research/eval/signoffs/roads_v0.1b.md
  outcome_seen: false
  fits_permitted_on_real_labels: true
  blocking_conditions_open: 8
  numbers_stageable_while_blocking_open: false
```

**State: `signed with conditions`.** Per `research/eval/SIGNOFF.md` section 3 the
design may fit. A number produced while a blocking condition is open is not
staged, and if it has already been staged it is marked
`withdrawn_pending_condition`. Eight of the ten conditions in section 9 are
blocking for the primary result and two are blocking for a named secondary
claim, and condition C1 alone is sufficient to hold
every one of them shut today, because eight of the ten datasets are at status
`pending` and neither of the two that are `verified` carries a covariate or a
label. In practice this signature permits the pre-labelling work, the
simulation work and the accounting work, and nothing else, until data arrives.

---

## 0. The verdict, in one paragraph

Every one of the seven reasons that refused v0.1b is answered, and four of them
are answered past what the refusal asked for. The `SIDE` rule is not patched but
replaced, with its own precision derivation and a pre-labelling check that can
veto the direction before any labelling effort is spent. Section 11.5 now carries
`kappa_v` on the covariate the model actually fits, obtained by Monte Carlo rather
than by the delta method I would have accepted, and a per-segment attenuation
distribution I did not ask for. The exclusion-power arm and gate M2 close the
defect where a claim about exclusion was gated on a measurement of detection.
Section 5.7 turns a prose rule with many clauses into an ordered procedure whose
exit set is exhaustive by construction, with a step that raises and stops rather
than inventing an eleventh reason code at run time, and all ten of my boundary
scenarios are determined by it. The six absent items are present, the complex
level split fingerprint reproduces exactly under my own re-run, and the vocabulary
promise has become two detectors and a program rule. **This is a signable design
and the reason it is not signed outright is not a defect in the document.** It is
that the direction has no data: P12 caps it, my own ten unit blind pass of P3
cannot be run because no unit exists, and the segment level fingerprint that a
result will carry cannot exist until a layout script has run. A3 states all three
plainly rather than letting me find them, which is the behaviour this protocol is
for. What I add on top is four findings that are new this round, all of them in
the new machinery rather than the old, all of them fixable before any fit and none
of them needing data: the `z_side` cutoff is stated on the wrong sampling scale;
the two tier side rule is a two stage test reported at a one stage threshold; the
`SIDE` exclusion is outcome dependent in the direction that removes holds, and the
check that would see it is missing from section 12.9 although it is cheap and
side blind; and the grazing truncation A3 declares reaches `kappa_v` and the
recoverability simulation, so it is not as benign as section 5.1.4 reports.

---

## 1. What the state turns on, and what it does not

**It turns on P12 and on nothing in the design.** `SIGNOFF.md` section 3 is
unambiguous and it is my own text: "A dataset at status `pending` may appear in a
pre-registration, but the sign-off is then `signed with conditions` at best, and
the condition is that the fit does not start until the status reaches `verified`."
Eight of ten datasets are pending. A3's reading that this caps the signature is
correct and I confirm it in section 6.3 below.

**It does not turn on my four new findings.** Each of them is a specified repair
inside machinery the document already carries and already reports, each costs no
data and no fit, and none of them changes what the design would mean if it ran.
A refusal is for a design not specified tightly enough for its result to mean
something whichever way it comes out. That is not this document. Recording them as
numbered conditions rather than as a second refusal is the honest grading, and
inventing a refusal out of them to look rigorous would be the failure mode the
task warns against.

**It does not turn on the order defect in P11**, which costs this round the
comparison the item exists to produce, and which A3 declared rather than faked.
Section 6.2 prices it.

---

## 2. Item verdicts, P1 to P16

| item | v0.1b | v0.2 | note |
|---|---|---|---|
| P1 hypothesis in falsifiable form | pass | **pass** | F1 to F5 each carry a threshold and a reported consequence. F1's asymmetry is stated as a qualification rather than buried. F4 now names `lambda` first and is disjunctive, which is what R6 asked |
| P2 unit of analysis | conditional | **pass, with C9 open** | the row count and the effective encounter count are now pre-fit key paths (`labels.counts.total_labelled`, `labels.effective_encounters.value`) rather than orders of magnitude in prose, which is the right resolution. The numbers themselves cannot exist yet |
| P3 label rule | **fail** | **pass on the text, C9 open on the test** | section 5.7 determines all ten of my scenarios; the exit set partitions `f_lee` with no gap; step 13 raises. My ten unit blind pass cannot run and A3's thirty unit pass cannot run. Executability is argued and not yet demonstrated |
| P4 covariates and sources | conditional | **pass** | knowable-at and label-touching columns present. The single "yes" row, `n_share`, is declared with its paragraph, kept out of the design matrix and whitelisted by name in the audit script. Declaring it rather than omitting it because it is not strictly a covariate is the right call |
| P5 model form | pass | **pass** | 7.7.1 names the unidentified product and says what is reported when it stays unidentified, including the renaming in item 3. 10.7 names the held-out random-effect rule. 6.3.4 settles ridges at `sigma_u = 0` and `W_true = 0` exactly |
| P6 held-out sets | **fail** | **conditional pass, C8 open** | the call, its empty keyword arguments, the row-order convention and the complex-level fingerprint are present. I re-ran the call: `844e82d0...` reproduces exactly, and so does the four-way row-order demonstration. The segment-level fingerprint is null and scheduled for v0.3a |
| P7 primary metric | conditional | **pass** | one metric, the resampling unit is the cluster from P2, and the within-fold bootstrap is labelled a lower bound with the sentence attached wherever it is quoted. Refusing a segment-level bootstrap outright is correct |
| P8 simple baseline | pass | **pass** | B1 on `W_cleared`, the 4 of 5 folds rule and the 0.02 nats margin fixed now |
| P9 failing condition | pass | **pass** | F3 restated in cleared metres on one contrast shared with the smallest effect of interest, which is what R4 required |
| P10 stopping rule | **fail** | **pass** | 48 fits enumerated, the fit log carries failed fits, at most two attempts, and 19.3 forbids modifying a specification to make it converge. 19.4's argument for no correction is right: three fixed readings of one coefficient are not a search |
| P11 leakage self-audit | **fail** | **present, comparison lost** | see section 6.2. The verdicts exist and are not independent of mine |
| P12 data provenance | **fail** | **present, cannot reach verified** | see section 6.3. This is what sets the state |
| P13 compute | **fail** | **pass** | the cut order is decided in advance and ordered so nothing above a cut depends on anything below it. Instruments 2 and 2b are never dropped, which is the right thing to protect |
| P14 scope | pass | **pass** | every foreign source carries the method-only sentence. Section 6.5 is explicitly blocked on confirming the Swedosh formula against the source, and 6.5 states that nothing substantive follows for Korea from the Australian validation widths |
| P15 what the result will not say | pass | **pass, upgraded** | 12.4.4's list, and now two detectors plus RC-011 behind it |
| P16 result artifact | **fail** | **pass** | the artifact path, the exhaustive quotable key paths, the staging file in the registrar's own shape, and the honest empty `forbidden_phrasings` because those are mine to write at verification time |

---

## 3. The replacement side rule, judged on the merits

The orchestrator re-derived A3's central claim independently and it holds: the
statistic reduces to `sin(theta) * sqrt(n_det) / (2c)`, and the spread rate and
the neighbourhood radius both cancel. I have not re-checked that algebra and I
accept it. The following is about whether the rule is the right rule.

### 3.1 Is `c` estimable without touching the label? Yes, and it matters less than the document thinks

`c = sigma_r * r / R`. `sigma_r` and `r` come from the weighted local plane fitted
to VIIRS active-fire detections; `R` is a design constant. No dNBR scene, no
burned mask, no perimeter. Check S0 is declared to touch no scene and no label and
that declaration is accurate. **Verdict: `c` is label-blind and check S0 is
executable exactly as written, before any label exists.**

One clarification that strengthens the rule rather than weakening it, and which
the document does not make. `c` is **not in the critical path of the label**. The
side test is `T = s / se(s)` computed directly from `Sigma_g`; `c` appears only in
the section 5.1.3 derivation and in check S0's diagnostic distribution and gate
S1. So even if `c` is estimated poorly, no segment is mislabelled by that; what is
misestimated is the forecast of how many segments will survive. That is a better
position than 5.1.3 claims for itself, and A3 should say so, because it means gate
S1 can read the realised pass fraction directly rather than reading `c`, which
5.1.3 already has it doing.

Where `c` is weakly determined is worth recording anyway. At the C4 minimum the
plane is fitted to detections at two distinct acquisition epochs, so `r`, which is
the reciprocal of the fitted gradient magnitude, is poorly determined; section 6.4
says this in terms. `c` inherits it. The sentence in 5.1.3 that reads "if check S0
reports `c` above about 0.5 at typical detection counts, the side assignment fails
for most segments" is therefore a statement about a noisy quantity, and gate S1
should be read off the pass fraction and not off `c`. It already is. No change
required beyond saying it.

### 3.2 The 2.0 cutoff is on the wrong sampling scale, and this is condition C2

`T = s / se(s)` divides a fitted quantity by **an estimated** standard error.
`se(s) = sqrt(n' Sigma_g n)` and `Sigma_g` scales with `sigma_r`, which is
estimated from the residuals of the same weighted plane fit. The plane
`t(x) = t0 + g . (x - x0)` carries three parameters in two dimensions, so the
residual degrees of freedom are `n_det - 3`. `T` is therefore a Student's t
statistic on `n_det - 3` degrees of freedom and not a z statistic, and `z_side` at
2.0 is a normal-scale number applied to it.

What that costs, computed under the null that the projected gradient is zero:

| `n_det` | degrees of freedom | P(`T` > 2.0) per tail | normal value the 2.0 implies |
|---|---|---|---|
| 5 (the C4 minimum, tier S-A) | 2 | 0.092 | 0.023 |
| 6 | 3 | 0.070 | 0.023 |
| 8 | 5 | 0.051 | 0.023 |
| 12 (the tier S-B minimum) | 9 | 0.038 | 0.023 |
| 25 | 22 | 0.029 | 0.023 |
| 40 | 37 | 0.026 | 0.023 |

At the C4 minimum the nominal cutoff delivers about four times the false side
assignment rate it appears to promise, and no value on the declared grid repairs
it there: at two degrees of freedom, 2.5 still gives 0.065 and 1.5 gives 0.136.
The grid is on the wrong axis.

**Why this is blocking rather than cosmetic.** A false side assignment swaps the
two bands. Section 5.7 evaluates the side test at step 5 and C1 at step 8, so a
swapped segment then has C1, the windward-burned-up-to-the-barrier test, applied
to what is really the lee band. On a crossed segment both bands burned and the
swap is harmless. On a held segment the true windward burned and the true lee did
not, so the swapped C1 fails and the segment exits as `NOBURN`, ineligible.
**Side assignment error removes holds and leaves crossings**, and holds are the
rare class that section 11.1 already expects to be in the low tens. This is
leakage item A10 and B3 arriving through the side rule.

There is a second, compounding effect at exactly two acquisition epochs. With `t`
taking only two distinct values, a plane can separate the two level sets almost
exactly, so the residual measures how planar two level sets are rather than how
irregular a propagating front is. `sigma_r` is then biased low, `se(s)` is biased
low and `T` is biased high, on top of the degrees-of-freedom problem. The design
already carries the `two_epoch` flag and a three-or-more-epoch secondary, so the
instrument exists; what is missing is that the side rule treats a two-epoch fit
and a twenty-five-detection fit at the same cutoff.

The fix is one line and a recomputed table. See condition C2.

### 3.3 What the 3 km fallback tier introduces

Three things, of which A3 names one.

**Named, and handled well.** The 3 km plane averages over terrain the front did
not treat uniformly. A3 records `side_tier` as a covariate, reports the label rate
by tier, and pre-registers an S-A-only refit. That is the right set of three.

**Not named: it is a two stage test reported at a one stage threshold.** Tier S-B
is applied only where tier S-A failed, so the per-segment procedure is a
conditional second look at a correlated statistic on an enlarged neighbourhood.
The realised false-pass rate over the two stages exceeds either stage's nominal
rate, and with the scale problem of section 3.2 on top of it the gap is not small.
The mitigation costs nothing, because check S0 already computes the pass fraction
at each `z_side` and can compute it per tier: report the S-A pass fraction, the
S-B-given-S-A-failure pass fraction and the union, and state the combined
operating characteristic rather than `z_side` alone. Folded into C2.

**Not named, and more interesting: at 3 km the detection cloud around a barrier is
informative about the outcome by a route that is not the burned mask.** A 3 km
neighbourhood on a long barrier spans the barrier. If the front crossed, detections
straddle the line; if it held, detections sit on one side only. So the geometry the
S-B plane is fitted to is partly a picture of the event the label reads, observed
by a different sensor. This does not break the letter of the provenance firewall,
because the detection record is a declared and legitimate input to the side rule
and the firewall of 6.1 is about the scene pair. It does mean the S-B tier's
behaviour is outcome dependent, which is the subject of the next subsection and
the reason the S-A-only refit is load-bearing rather than decorative.

### 3.4 The `SIDE` exclusion is outcome dependent, and the check that would see it is missing

This is the finding I rate highest in this section, above the cutoff scale.

A front that crossed a barrier cleanly leaves a locally planar arrival surface
through the segment. A front that was **stopped** at a barrier leaves a kinked,
one-sided, locally non-planar arrival surface at exactly that segment: the arrival
times pile up along the windward edge and there is nothing on the other side. That
is large `sigma_r`, which is large `c`, which is small `T`, which is `SIDE`
indeterminate. **The side rule is less able to resolve a hold than a crossing, and
the failure removes the segment.** Same direction as C1 and C3 censoring, same
leakage item, new route, and the design's most important covariate is estimated on
what survives.

Section 12.9 is the right place and does not cover it. Its clustering check reports
the `W_cleared` distribution among segments excluded at `NOBURN`, `NOTMAIN`,
`NODETECT`, `TIMING` and `SIDE` against the retained ones. That answers whether
exclusion correlates with **width**. It cannot answer whether exclusion correlates
with the **outcome**, and the obvious reason is that an excluded segment has no
outcome, because the outcome needs a side.

It has one anyway, in side-invariant form, and this is the part that makes the
condition cheap. For any segment with the section 4.0 pixel minimum on both bands,
the pair `f_A` and `f_B`, the burned fractions of the two bands, is computable
without knowing which is windward. The **unordered** pair is side invariant:
`min(f_A, f_B)` and `max(f_A, f_B)` do not depend on the assignment. A segment
where both bands burned is a crossing whichever side was windward; a segment where
exactly one burned is a hold or a non-arrival whichever side was windward. So the
distribution of that pair among `SIDE`-excluded segments, against the same pair
among retained ones, measures the bias directly, requires no side assignment, and
is computable inside the committed accounting script. Condition C3.

---

## 4. The grazing truncation and the attenuation problem

A3 asks whether the cost it reports is as benign as it reports. **It is not, and
the reason is that the truncation reaches `kappa_v`, which is the quantity gate M1
gates on.** Three mechanisms, of which A3 identifies none, and a fourth that is
A3's and is fine.

**Mechanism 1, the numerator.** `kappa_v = Var(v_true) / (Var(v_true) + mean_i
sigma_v_i^2)` with `v = log(W_eff + 1)`. The side rule truncates `W_eff` from above
through `sin(theta)`. Truncating the top of the range lowers `Var(v_true)`, which
lowers `kappa_v`. Section 11.2 already knows that narrow true width spread is what
makes a given measurement error most damaging, and attributes the narrowness to
Korean road design classes. The side rule is a second, independent squeeze on the
same quantity, and nobody has connected the two.

**Mechanism 2, the denominator, and it pulls the other way.** Section 11.5.1 states
that `sigma_v_i` is approximately `sigma_u / (W_cleared_i + s_i)` and is largest
for narrow barriers at grazing angles. The side rule removes grazing angles, so it
removes the worst-measured segments, which **raises** `kappa_v`. So the net sign
is not decidable by argument. It is decidable by arithmetic, and the arithmetic is
available before any label exists, from check S0's per-segment `theta` and pass
flag together with the width measurement, which section 12.9 already establishes is
made for every candidate segment whether or not it is ever labelled.

**Mechanism 3, and this one is not symmetric.** On the retained set the side rule
enforces `sin(theta) >= 4c / sqrt(n_det)`, so `W_eff <= W_cleared * sqrt(n_det) /
(4c)`. **The ceiling on the width covariate is a function of the detection count.**
`n_det` rises with overpass cadence, which is section 2.3's own declared confound:
Suomi NPP and NOAA-20 cover all five fires, NOAA-21 only the 2025 ones. So the
retained width support differs by fire, and the fire is also the fold unit and the
random-effect level. That is section 12.7's collinearity between the complex
intercept and the width slope, arriving through a door 12.7 does not watch, because
12.7 reports within-complex width variation and nothing says it is reported on the
retained set.

**Where this lands.** The document does not say which geometry instruments 2 and 2b
are run on. Section 11.5.2 says "the **real** segment geometry and the **real**
measured width distribution", and both the candidate set and the side-passing set
are real and both are available before labelling, since check S0 and gate S1 run
after detections land and gate R0 runs after width measurement. If the simulation
is run on the candidate set it overstates the power of a fit that will be run on
the side-passing subset, with its truncated support and its smaller count. That
silence is the gap the truncation creates, and closing it is one sentence.
Condition C4.

**What A3's response (2) does and does not buy.** Reporting the slope on
`W_cleared` as well as on `W_eff`, and stating F3 and the smallest effect of
interest in `W_cleared`, is right and I ratified the unit change myself. It does
not remove the interaction. The fitted covariate is still `v`; gate M1 still reads
`kappa_v`, which is defined on `v`; and F3's contrast is read off the fitted curve,
not off a separate `W_cleared` regression. The truncation does not reach
`W_cleared` through the filter, and it reaches F3 **through the model**. A3's
sentence that the headline quantity "is the one the truncation does not act on
directly" is true as written and is read too kindly.

**The compounding with condition C5.** Section 6.5 keeps the answer honest at the
other end. In the bounding case of section 3.4 the roads arm survives only through
the `NOEXIST` per-segment existence check, and that check is the width
measurement's own null result, so it truncates `W_cleared` from **below**. Combine
the two and the roads width support is squeezed from below by the instrument that
measures width and from above by the rule that assigns sides, both through the
covariate's own machinery, and `Var(v_true)` sits between them. That is the single
sharpest technical statement I can make about this direction today, and it is why
gate W1's 25-and-25 support requirement is the gate I now expect to fail first,
ahead of M1. That gate is checked on the labelled table, after both truncations
have run, so the design fails safe rather than misleading. It behaves correctly.
The cost is that the modal outcome moves further toward "no curve" than section
17.2's chain already says.

---

## 5. A3's three disagreements, adjudicated

### 5.1 My R1 remedy list contained a closed route. **A3 is right. Conceded without reservation.**

My R1 listed "the local fire-perimeter geometry" and "the order in which the two
sides burned" among the information that genuinely distinguishes windward from lee.
The perimeter and the burned mask are both derived from the dNBR scene pair that
produces the label. Assigning a side from either lets the label define its own
geometry, and it manufactures `HELD` on exactly the segments the hypothesis is
about, because the side that burned less becomes "lee" by construction and a lee
side that burned less is what `HELD` means. That is the same dangerous direction I
correctly identified for undetected smoke in the same document, applied to a
different input, and I did not apply my own reasoning to my own suggestion.

**Registering it plainly, because a red-team agent that proposes a leaking remedy
should register that.** My refusal of v0.1b was correct on the arithmetic and one
of its three offered repairs would have destroyed the study more completely than
the defect it repaired. The arithmetic finding stands and A3 accepts it in full.
The remedy list was reviewer error of exactly the kind I exist to catch in others.
Two consequences I am taking, not one:

1. A3's extension of the section 6.1 provenance firewall from the covariates to
   the **side rule** (5.1.2) and to the **smoke reference region** (5.2.1) is the
   correct generalisation and it is more than the refusal asked for. It is ratified
   here as part of the signed design and is not reopenable without a version bump.
2. **The offering of candidate remedies inside a refusal is itself a hazard I have
   now demonstrated.** A refusal's job is to say what would clear a reason, not to
   pick the mechanism, because a reviewer who picks the mechanism has begun
   designing, and `SIGNOFF.md` section 5 says A6 does not sign a design A6 helped
   create. I record this as a limitation of my own round-2 record rather than
   amending the protocol mid-round, and it belongs in the report at
   `research/reports/A6/2026-09-16_round3.md`. Had A3 taken either route, the
   correct state today would have been a human gate and not a signature.

### 5.2 My scenario S4 overstates its premise. **A3 is right on the mechanics. Conceded, with one residual that is new and is condition C6.**

S4's premise was correct: a 40 m lee band against a 375 m VIIRS pixel means a lee
burn confined to the band usually carries no detection of its own. The inference
was not. The attribution test's input is `P`, the connected component of the burned
mask containing the segment's lee-band burned pixels, and `P` is not bounded by the
band. A fire that crossed and kept running produces a patch extending well past
50 m, and a patch of that size is intersected by a 375 m footprint. The genuinely
detection-free case is a crossing that stalled inside 50 m, which is a minority and
an interesting one. **A3's correction is right and my "majority of segments" was
wrong.**

A3 is also right that the repair is elsewhere: making the geometric step primary
means `CROSSED` is reachable with no detection anywhere whenever the nearest route
around the barrier is beyond `d_bypass_min`, so the reachability question S4 raised
is now settled by a reported count rather than by either of our arguments. That is
the correct way to end a disagreement of this kind and I adopt it.

**The residual, which is not a defence of S4.** A3 states that step A's geometric
pass is the common case on a long barrier, because bypass points are termini and
mapped gaps and those are sparse. If most `CROSSED` labels are reached on geometry
alone, then the attribution test performs no attribution on most of the positive
class, and the whole guard against flanking rests on 500 m being far enough. At a
flanking spread rate of 1 km/h a bypass point just past 500 m is about half an hour
away, and section 12.11 reports that the fitted arrival standard error `se_t`
exceeds two hours on some segments and counts them. A distance threshold is the
right shape only where the time margin it implies exceeds the timing uncertainty,
and here the document holds both quantities per segment and does not compare them.
No label needs to change. What is missing is the measurement of how large the
unchecked class is, which is the move A3 makes correctly everywhere else in this
version. Condition C6.

### 5.3 My M1 interval ruling is right and costlier than I stated. **A3 is right. Conceded, and the cost is a floor rather than the figure.**

I re-derived it. Write `kappa = 1 / (1 + lambda)` with `lambda = sigma_u^2 /
sigma_x^2`. At `kappa` of 0.70, `lambda` is 3/7. With `sigma_u` at about 13 per
cent relative from thirty repeat pairs, `sigma_u^2` carries about 26 per cent, so
the 95th percentile of `lambda` is about `(3/7) * (1 + 1.645 * 0.26)`, giving a
5th percentile of `kappa` of about 0.62. Inverting, a lower bound of 0.70 needs a
point `lambda` of about 0.30 and therefore a point `kappa` of about 0.77. **A3's
arithmetic reproduces exactly and its conclusion is correct: the interval form
raises the effective requirement by roughly seven points.**

Two things I add, both of which make the cost larger and neither of which changes
the ruling.

1. The derivation treats `Var(v_true)` as known. It is estimated, from the same
   sample, and by section 4 above it is estimated on a support that two of this
   design's own filters truncate. So 0.77 is a floor on the point requirement and
   not the requirement.
2. `kappa_v` is a posterior quantity from the joint fit and not a plug-in, so the
   number is indicative of the direction and the size, which is all it needs to be.

**The ruling stands unchanged**, and A3's handling of it, reporting `kappa_v` and
its interval as numbers always and never as a pass or a fail, is the same treatment
I required for recoverability in section 8.2 of the previous record and is the
correct generalisation. A design landing at 0.68 is not reported the way one
landing at 0.31 is.

---

## 6. The things A3 declares rather than hides

### 6.1 R1 is closed except the second-pass disagreement rate

Agreed. The rate cannot exist before labels, the procedure is frozen here, and
filling a number that does not exist would be worse than the gap. A3's handling,
a scheduled v0.3b version bump carrying the "what was seen before this amendment"
section that `SIGNOFF.md` section 4 requires for exactly that look, is the correct
mechanism, and pre-announcing v0.3a and v0.3b in section 16 so they are not
surprises is good practice I would like the other two directions to copy.

Two points on gate L1 that I ratify rather than contest. Three of thirty at the
three-class level is one in ten, which is the bar my own ten-unit acceptance test
sets, so the two are consistent by construction. And removing the thirty units from
the modelling dataset permanently, counted as `RULEVAL`, is the right price: the
alternative is to validate the rule on units that then enter the fit, which is a
look at the outcome inside the training set. The expected cost in labelable
segments is small because the draw is from candidates.

The one thing I require: **the second path's author must be neither A3 nor A6**, as
5.8 states, and the request text handed to that agent must be committed alongside
the script before the pass runs, as 5.8 also states. I confirm I am not the right
author for it, for the reason A3 gives, and I am available for my own separate
ten-unit blind pass, which is a different instrument with a different purpose.

### 6.2 P11 carries a declared order defect, and what it costs

**A3's handling is correct and the declaration is worth more than a faked
agreement.** The item exists to produce the difference between two independently
formed lists. A3 read mine before writing its own, so for this round that
difference does not exist and cannot be reconstructed. Pretending otherwise by
writing verdicts that happen to agree would destroy the one thing the item
produces, which is exactly what section 20.1 says.

**What it costs, priced honestly.** The item loses its value as an independent
second look. It keeps its value as a declared verdict list that later behaviour can
be checked against, which is not nothing: a verdict of "mitigated" on B3 written
before any fit is a commitment that a later reader can hold the direction to.

**Two facts that bound the cost, and I want them on the record because they are the
difference between a lost round and a compromised one.**

1. **The contamination ran in the cheaper direction.** The author read the
   reviewer's list. The reverse, a reviewer reading the author's verdicts first,
   would have been much worse, because a reviewer who starts from the author's
   framing inherits the author's blind spots and the review becomes a ratification.
   My round-2 pass over the twelve roads items was run independently, before A3
   wrote anything, and it is that pass which produced B3 and B4 at CRITICAL
   unresolved and B5, B7 and B9 as conditions. So the round did receive one
   genuinely independent audit; what it did not receive is a second one.
2. **The single differing verdict carries little information.** B10 differs by A3
   supplying a mitigation rather than by disputing my reading, which is what
   contamination predicts. The OpenStreetMap `highway=track` audit is a real
   improvement on nothing and is labelled weak by its own author, which is the right
   label. It should not be counted as a disagreement that survived independent
   formation, because it was not independently formed.

**The consequence I am fixing rather than noting.** Section 20's Part A and Part B
are not independent evidence this round and must not be summarised as agreement
between two audits in any later report, poster or paper sentence. And the order is
reversed for the other two directions: the author's checklist is written and
committed before A6's pass begins. A3 recommends this to the orchestrator in 20.1
item 3 and I am making it a condition rather than a recommendation, because the
same defect occurring twice would be a pattern rather than an accident. Condition
C10.

### 6.3 P12 cannot reach verified. **Confirmed, and the reasoning is sound in a sharper form than A3 states it.**

A3's reasoning: two of ten datasets are verified, neither carries a covariate or a
label, and under P12 that caps any signature at `signed with conditions`. I confirm
it. `SIGNOFF.md` section 3 makes it mechanical rather than a judgement, and the
condition it names is exactly the one in C1.

The sharper form. The two verified files are `kfs_fire_state_history_csv` and
`kfs_fire_stats_csv`. Section 5.2 uses the first for containment time in scene
selection and the second as a cross-check, section 21.2 records their defects, and
section 5.2 states that the sunrise and sunset columns of the first are never used
because A1 confirmed they carry one national value per date. Neither file supplies
a covariate, a label, a barrier, a scene, a detection, a terrain value or a weather
value. **Every input from which this direction could compute a number is pending**,
including both of the two whose absence would end the direction outright: the
forest road layer behind WJ-017 and the pre-fire orthoimagery behind WJ-009. The
honest one-line statement of the data position is not "eight of ten pending", it is
"nothing that can produce a number has arrived".

### 6.4 The segment-level split fingerprint, deferred to v0.3a

Correct and correctly handled. The unit of analysis is the segment, so the split a
number is produced under is a segment-level split, and its fingerprint cannot exist
before the layout script runs. Pinning the row order now, in section 18.2, is the
part that makes the deferral safe, because the row order is the thing that could
otherwise be chosen after the fact. A version bump whose only change is that value
is the honest mechanism.

I re-ran the complex-level call this round, with no keyword arguments and the five
fire ids in section 2.1 order, and the fingerprint reproduces exactly:
`844e82d06b534901590bc660f62cb49bb2b57279be055e112c93d801098d2cd5`. The four-way
row-order demonstration in 18.2 also reproduces: forward, reversed, grouped and
interleaved give four distinct values. Condition C8 is the outstanding half.

### 6.5 The forest road dating branch, and the consequence A3 states plainly

A3 states it: at the only edition known to exist, 2025-11-20, no fire is safe, the
edition test on its own removes the entire roads arm, and the mitigation is the
per-segment existence check that comes free with the width measurement, which makes
WJ-009 load-bearing twice. The statement is accurate and stating it is right.

**What follows and is not stated, and it is the reason for condition C5.** A segment
exits `NOEXIST` exactly when the orthoimagery classifier finds no canopy gap at the
mapped centreline. That is the same instrument, reading the same image, that
produces `W_cleared`. So `NOEXIST` is the width measurement's own null result wearing
an existence code, and its false-negative rate is a function of the covariate of
interest: a narrow forest road under closed canopy is precisely the case the
classifier most easily misses, and a 작업임도 at the narrow end is where that lands.
The exclusion therefore runs against **narrow** roads, which is the branch section
12.9 itself names as the **dangerous** direction, the one that inflates an apparent
width slope rather than attenuating it, and the one whose reading rule 12.9 says
goes in the abstract rather than in a limitations paragraph.

Section 12.9's clustering check lists `NOBURN`, `NOTMAIN`, `NODETECT`, `TIMING` and
`SIDE`. It does not list `NOEXIST` or `WIDTH`, which are the two exclusions that are
by construction functions of the measured covariate. That is the gap.

**And the two loads are not independent.** A3 says WJ-009 is load-bearing twice. The
sharper statement is that in the bounding case the edition test and the existence
check are one measurement doing double duty: gate E1 can be satisfied by the
existence check alone, but the existence check cannot establish existence, only the
visibility of a gap in pre-fire imagery at whatever ground sample distance arrives.
One imagery failure, or one imagery vintage too coarse, takes the width covariate,
the error model, `kappa_v`, gate M1, the recoverability simulation and the existence
check together. E1's consequence text should say so where E1 is, not only in 3.4
item 4.

---

## 7. The record class for frozen superseded pre-registrations

I own the protocol this construction serves, so I rule on it.

**The construction is sound in principle and the split is the right split.** A
superseded pre-registration must contain, by construction, the wording a later rule
exists to stop recurring, because the point of keeping it is to show what was
proposed before it was corrected. A per-line pragma on it would be an edit to the
one file `SIGNOFF.md` section 4 says can never be edited, and an edit made to
satisfy a checker is still an edit. So a structural exemption is the only honest
construction available. Exempting the file from the **claim** rules while keeping
the **em-dash** check, which is a program scope rule with no pragma anywhere, is
the correct place to draw the line: the claim rules are about what a document
asserts, and a frozen record asserts nothing in the present tense, while the
em-dash rule is about the character set of the tree. Mirroring the repository's own
withdrawn-claims record class rather than inventing a new mechanism is also right.

**It needs two narrowings, and neither is A3's to make.**

1. **It grants membership by path to two files that do not exist.**
   `research/landslides/PREREGISTRATION.md` and
   `research/suppression/PREREGISTRATION.md` are both absent today. The comment
   defends this by saying the live pre-registration of the day is a versioned
   `PREREG_<direction>_<date>_v<n>.md` file and is not exempt. That is the rule in
   `SIGNOFF.md` section 2 and it is correct, but the roads direction's own history
   is that v0.1, v0.1a and v0.1b all lived at exactly `research/roads/PREREGISTRATION.md`
   while they were live, and the versioned name was adopted only at v0.2. So the
   class currently pre-grants a claim-rule exemption to the path where two
   directions are most likely to write their live first drafts, on the strength of a
   convention that the only direction with a history broke one version ago. A
   pre-granted exemption is the kind of thing that is discovered by an agent writing
   a first draft and finding that the checker is quiet.
2. **Membership is by path and not by content.** Nothing in the construction
   prevents a file in the class from being edited afterwards, and being in the class
   is precisely what removes the checker that would notice. The one rule in this
   protocol that cannot be repaired after the fact is now the one rule with no
   detector on it.

**The second one I have fixed inside my own tree this round**, because it is the
one that matters and because pinning a hash does not require touching anyone else's
file. `research/eval/tests/test_signoff_roads.py` now pins
`research/roads/PREREGISTRATION.md` to
`9ddb41f9f86710b62d9732db23079a1c60e1f115ece993ff1e48936f39ed579e` and fails if it
moves, and asserts that no record-class path that does not exist has a live
pre-registration written to it. The first narrowing is a request, condition C7.

---

## 8. RC-011, and the vocabulary condition from R6

**Discharged, and by a better route than the condition asked for.** R6 required a
claim rule with a detector before the scope cut of 12.4.4 could be treated as
anything but a promise, on the grounds that a fixed vocabulary nothing checks lasts
until the first author writing a figure caption in a hurry. Two things now exist:
`research/roads/check_vocabulary.py`, committed by A3 inside its own ownership, with
RV-001 to RV-003, a catches corpus, a spares corpus and a self-test; and RC-011 in
`research/FORBIDDEN_CLAIMS.md` with its detector in the program checker. I ran the
program checker's self-test this round: 11 rules, 32 of 32 catches, 31 of 31 spares.

A3 drafted RC-011 and could not land it, because A3 does not own that file, and it
was landed by the orchestrator after validation in both directions. That sequence is
correct and it is the sequence I want to see repeated: the agent that needs a rule
drafts it with its catches and its spares, and the owner validates and lands it.

**One gap remains and it is not A3's.** The program checker's scope is `research/`.
A width sentence rendered into a poster caption, a README line or the manuscript
under `docs/` is covered by neither detector. The drafted patch to
`scripts/check_forbidden.py` is already on the taskboard as WJ-002. Until it lands,
no width number from this direction appears on a surface outside `research/`.
Condition C7, marked blocking for the named secondary claim rather than for the
primary result, because it governs how a result may be worded and not whether it
may be computed.

---

## 9. The conditions

Each carries the verification action that clears it, the phase by which it must
clear, and whether it is blocking for the primary result or for a named secondary
claim, per `SIGNOFF.md` section 3. The owner is named because three of the ten are
not A3's to satisfy.

| id | condition | owner | blocking | phase | what clears it |
|---|---|---|---|---|---|
| **C1** | Every dataset that supplies a barrier, a covariate, a scene, a detection or a weather value reaches status `verified` with a sha256 on disk before any fit on real labels. Eight of ten are `pending` (section 21.1) and the two that are `verified` supply neither a covariate nor a label | A1, and John through WJ-017, WJ-009, WJ-001, WJ-011, WJ-012, WJ-018 | **primary** | before the first fit on real labels | A6 reads `research/data/REGISTRY.yaml` and confirms `verified` plus a sha256 for `kfs_forest_roads`, `korea_prefire_orthoimagery`, `sentinel2_l2a_dnbr`, `firms_active_fire_korea`, `dem_korea`, `kfs_forest_type_map`, `base_map_linear_features` and `kma_asos_aws` |
| **C2** | `z_side` is restated as a quantile of Student's t at the fit's own residual degrees of freedom, `n_det - 3`, at a one-sided alpha declared now, and the section 5.1.3 minimum-resolvable-angle table is recomputed with `t_{1-alpha}(n_det - 3)` in place of 2.0. The declared grid is stated in alpha rather than in z. Tier S-A additionally either requires three distinct acquisition epochs or carries its two-epoch segments at an explicitly separate cutoff, because at two epochs the residual measures the planarity of two level sets and `sigma_r` is biased low. Check S0 reports realised degrees of freedom per segment, and the pass fraction per tier and for the union of the two tiers, so the two-stage procedure is reported at its own operating characteristic and not at a one-stage threshold | A3 | **primary** | before check S0 runs, and therefore before any labelling | A6 re-derives the angle table from the declared alpha and confirms it matches, and confirms `checks.S0` carries `degrees_of_freedom`, `pass_fraction_by_tier` and `pass_fraction_union` key paths |
| **C3** | The `SIDE` exclusion is checked for outcome dependence by a side-invariant statistic. For every segment excluded at `SIDE` or at `TIMING` that meets the section 4.0 pixel minimum on both bands, the unordered pair `min(f_A, f_B)` and `max(f_A, f_B)` of the two bands' burned fractions is computed and its distribution reported against the same pair on retained segments, per fire and per barrier type, with both readings written in advance the way section 12.9's are: enrichment of the excluded set in the one-side-burned configuration means the censoring runs against holds, which attenuates the width slope and is the conservative direction, and it is reported as such. `SIDE` and `TIMING` join the readings of 12.9 | A3 | **primary** | with the label accounting, before the first fit | A6 confirms the quantity is in the committed accounting script and has a key path, and that both readings are written before any value exists |
| **C4** | The geometry the attenuation and recoverability instruments run on is pinned to the set that will be fitted. `Var(v_true)`, `kappa_v` and `kappa_v_i` are computed on the side-passing retained set and additionally on the full candidate set, both reported, with gate M1 reading the retained one. Instruments 2 and 2b take the retained geometry and the retained width distribution, and gate R0 reads the retained value. Section 12.7's within-complex width variation is reported on the retained set as well, because the retained `W_eff` ceiling is `W_cleared * sqrt(n_det) / (4c)` and `n_det` varies by fire with the overpass cadence of section 2.3. Section 5.1.4's third response stands; its second response is restated to say that reporting a `W_cleared` slope does not remove the interaction, because the fitted covariate is `v`, gate M1 reads `kappa_v`, and F3 is read off the fitted curve | A3 | **primary** | gate R0 and check S0, before labelling | A6 confirms both values of `kappa_v` are at distinct key paths, that `recoverability.*` records which geometry it used, and that gate R0's recorded value is the retained one |
| **C5** | `NOEXIST` is treated as the width measurement's null result rather than as an existence fact. (a) The classifier's minimum detectable gap width at the delivered ground sample distance is declared as a number before any measurement, and `NOEXIST` means "below the declared floor", with the per-segment imagery ground sample distance and vintage reported beside it. (b) `NOEXIST` and `WIDTH` join the exclusion-clustering readings of section 12.9, with the dangerous-direction bounding analysis attached to them, because both are by construction functions of the measured covariate and the exclusion runs against narrow roads. (c) Gate E1's consequence text records that in the bounding case of section 3.4 the edition test and the existence check are one measurement doing double duty, so E1 passed by existence check alone is reported under that name | A3 | **primary** | (a) before the width measurement; (b) and (c) with the label accounting | A6 confirms the declared floor is a committed number predating the measurement, and that `labels.counts.by_fire[].by_ineligible.NOEXIST` appears in the 12.9 readings |
| **C6** | Step A of the attribution test records the time margin it is implicitly asserting. For every segment passed on geometry alone, `d_bypass / r_flank` is compared against the combined standard error of `t_w` and the acquisition time, and the count of geometric passes whose time margin falls below that standard error is reported per fire at `labels.crossed_reachability.by_geometry_thin_margin`. No label changes and the `d_bypass_min` grid of {300, 500, 800} m stands. What changes is that the size of the class `CROSSED` reaches without any attribution becomes a measured quantity | A3 | **primary** | with the label accounting | A6 confirms the key path exists and that the count is reported per fire whichever way it comes out |
| **C7** | The vocabulary rule reaches the surfaces a number is quoted on. RC-011 and `research/roads/check_vocabulary.py` cover `research/**` and the roads tree; neither covers `docs/`, the README or the manuscript. Until WJ-002 lands the drafted patch to `scripts/check_forbidden.py`, no width number or width sentence from this direction appears on any surface outside `research/` | orchestrator, and John through WJ-002 | **named secondary claim**: that the estimand is operational barrier performance | before any output of this direction leaves `research/` | A6 confirms the program-wide detector's scope covers the surface the sentence is written on, by running it against that file |
| **C8** | The segment-level split fingerprint is pinned at v0.3a, computed by running `leave_one_complex_out` over the per-segment fire-id vector in the committed layout row order of section 18.2, immediately after the layout is committed and before any label is computed. The complex-level fingerprint is verified this round and reproduces exactly | A3 | **primary** | v0.3a, before any label | A6 re-runs the call over the committed layout and compares against the value written into the v0.3a `prereg:` block. A mismatch is a refusal with no discussion, per P6 |
| **C9** | Both label-rule passes run before any width number is quoted. A6's ten-unit blind pass of `SIGNOFF.md` section 6 step 2 runs on the first committed candidate set that has scenes. A3's thirty-unit second pass of section 5.8 runs under gate L1, by an agent that is neither A3 nor A6, with the request text committed alongside the script, and the disagreement rate enters at v0.3b with the section 4 amendment record. Until both have run, P3 is passed on the text and not on the test | A3 for the second pass, A6 for the blind pass, orchestrator for the second path's author | **primary** | before any width number is quoted anywhere | A6 records its own ten-unit result in this signoffs tree, and confirms `labels.rule_validation.*` is populated and that gate L1's branch is recorded |
| **C10** | The P11 order is reversed for the other two directions: the author's leakage checklist is written and committed before A6's pass begins. For this round, section 20's Part A and Part B are recorded as not independent of A6's round-2 pass and are not summarised as agreement between two audits in any report, poster or paper sentence | orchestrator, A4, A5 | **named secondary claim**: any statement that the leakage audit was independently corroborated | before the landslides pre-registration is reviewed | A6 confirms the landslides checklist's commit predates the start of A6's pass, by the ordering recorded in the ledger |

---

## 10. What is not a condition, and why

Recorded so that nothing on this list is later mistaken for an open item.

- **The estimand being associational rather than causal.** Section 1.4 and 12.4 are
  correct and complete. This is a property of the record, not a defect of the
  design, and section 12.4.2's refusal of a proximity proxy on the grounds that the
  road network is the barrier layer is exactly right: a bad control is worse than an
  acknowledged confound. The kill-shot file already carries the objection and its
  scope-cut ceiling.
- **Five levels in the fire random effect.** Section 7.5 handles it about as well as
  it can be handled: intercept only, an informative `sigma_fire` prior with a
  declared sensitivity, a complete-pooling and a fixed-effect parallel, and no
  per-complex claim. Asking for more would be asking for fires that do not exist.
- **The refusal of a topographic illumination correction for the primary.** Section
  12.10 is right and I want it on the record as right. A C-correction or a Minnaert
  correction fits its parameters by regressing reflectance on illumination over the
  scene, which is over the label pixels, so a covariate-side correction would be
  fitted on the outcome's own pixels. Carrying `delta_illum` as a difference of
  differences costs nothing and fits nothing on the scene. The conditional secondary,
  available only if a correction can be fitted outside every perimeter buffer, is the
  correct shape for the alternative.
- **The ember arm probably being withdrawn.** F4 fires and 7.7.1 item 3 renames the
  coefficients. That is a declared branch with a written consequence, not an open
  item.
- **`n_share` being derived from the label.** Declared as a "yes" with its paragraph,
  kept out of the design matrix, whitelisted by name in the audit script, and used
  only as a grouping variable and a subset selector. Declaring it rather than
  omitting it on the technicality that it is not a predictor is the right call and I
  would rather see this than a table of twenty clean rows.
- **The absence of a multiplicity correction.** Section 19.4's argument is correct.
  Three fixed readings of one pre-registered coefficient and one pre-registered
  baseline comparison, each with a threshold fixed before the data exists and none
  able to be swapped for another, is not a search, and the fixed table plus the
  reported count is what does the protecting.
- **The OpenStreetMap roads audit being weak.** It is weak and A3 says so. A weak
  audit that is declared and reported is not an open condition.
- **The 15 degree clip in `W_eff` being kept unchanged.** Correct, and for the stated
  reason: under the new side rule the clip is rarely binding, and a clip that almost
  never binds is preferable to one tuned after the fact.

---

## 11. What now stands between this direction and a fit

In the order the gates actually fire, with the conditions attached where they sit.

1. **WJ-017.** The forest road SHP has never downloaded. Without it there is no road
   geometry, no attribute schema, no road class fallback and no internal edition
   date, so branch A and branch B of section 3.4 cannot even be chosen between.
   Condition C1.
2. **WJ-009.** The pre-fire orthoimagery. Without it there is no width covariate, no
   hand-measured subsample, no `sigma_u`, no `kappa_v`, no gate M1, no recoverability
   simulation and, since section 3.4, no per-segment existence check. In the bounding
   case where the only obtainable edition postdates all five fires, this one gate
   decides whether the roads arm exists at all, and conditions C1 and C5 both sit on
   it.
3. **WJ-001.** Six API keys, unset. Sentinel-2 and the active-fire archive are both
   behind them, so there is no scene pair and no detection record, which means no
   label and no arrival-time fit. Condition C1.
4. **Gate E1**, at least two complexes whose roads pass the edition or existence
   check. Condition C5 governs how a pass by existence check alone is reported.
5. **Check S0 and gate S1**, at least a quarter of candidate segments passing the
   side test in at least three complexes. Condition C2 must be satisfied before this
   runs, because C2 changes what the test is. This is the cheapest true thing the
   direction can produce and it is available before any labelling.
6. **Gate R0**, detection power at the smallest effect of interest at or above 0.20,
   which decides whether the labelling effort is worth spending on the width question
   at all. Condition C4 must be satisfied before this runs, because C4 changes what
   geometry it is computed on.
7. **The two label-rule passes**, C9, and gate L1.
8. **Gates G1, G2 and G3, W1, N1 and H1** on the labelled table.
9. **Gates M1, M2 and P1** around the fit.

**Where I now expect it to end, recorded so it can be scored later.** My round-2
prior was that at least one of W1, G1 and M1 fails and the round delivers the
labelled encounter table with no breach curve on it, and I rated that more likely
than all other outcomes combined. Section 4 of this record moves one thing inside
that prior: **I now expect W1 to fail before M1**, because the roads width support
is truncated from below by the existence check that is the width measurement's own
null result and from above by the side rule's angle requirement, both through the
covariate's own machinery, and W1 counts 25 segments at or above 6 m of `W_cleared`
and 25 below on what survives both. The headline prediction is unchanged and the
ordering inside it has moved. It is worth saying that this is the design failing
safe rather than failing quietly: W1 is checked on the labelled table, after both
truncations have run, and its consequence is that the curve is not published.

**And the cheapest true result stands where A3 puts it.** Check S0 and instrument 2
can tell the program that a Korean five-fire record of this size cannot resolve the
question, before anybody labels a segment, and gate R0 lets that finding stop the
labelling rather than merely caveat it. That is a publishable result and the design
is built to reach it early. Nothing in this record should be read as an argument for
loosening any gate to avoid it.

---

## 12. Process notes

- Sign-off pass run per `SIGNOFF.md` section 6. Step 1 done (section 2). Step 2, the
  ten-unit blind pass, **not run: no unit exists**, and that is condition C9 rather
  than a silent omission. Step 3 done: the complex-level fingerprint reproduces
  exactly and the row-order demonstration reproduces four distinct values. Step 4,
  the independent leakage pass, was run in round 2 before A3 wrote anything and is
  the one in `research/eval/signoffs/roads_v0.1b.md` section 7; this round compares
  A3's verdicts against it and records in section 6.2 why that comparison carries
  less than P11 intends. Step 5 done in round 2, items 1 to 4 of
  `research/eval/killshots/roads.md`, unedited since. Step 6 is this record and the
  ledger row.
- **A6 has not contributed to the design of this direction beyond checklists,
  refusals and ratified levels**, with one exception now on the record: the remedy
  list in R1 of the previous record named two mechanisms, and A3 refused both. See
  section 5.1. Nothing A6 proposed is in the signed design, so the standing rule in
  `SIGNOFF.md` section 5 that A6 does not sign a design A6 helped create is not
  triggered. Had A3 adopted either route, the correct state today would have been the
  human gate at step 5 rather than this signature.
- No outcome has been seen by A6. No dataset has been fetched by A6. No number in
  this record is a measurement: the t-distribution tail probabilities in section 3.2
  and the `kappa` arithmetic in section 5.3 are properties of named distributions and
  of algebra, computed this round and reproducible from the text, and neither touches
  the Korean record.
- Every number this direction later proposes is re-run by A6 from the registered raw
  input per `research/eval/NUMBERS_PROTOCOL.md` before it is quoted anywhere, and the
  `forbidden_phrasings` and `check` fields that section 22.3 leaves deliberately empty
  are written by A6 at that time.
