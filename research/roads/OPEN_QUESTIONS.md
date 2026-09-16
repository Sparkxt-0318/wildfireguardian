# Roads direction, open questions

**Status: written 2026-09-16 by A3, alongside `PREREGISTRATION.md` v0.1a.** These
are the design decisions A3 could not settle alone. Each has the options, what
turns on it, A3's recommendation, and who decides. Every one of them must be
closed before A6 signs, because a pre-registration with an open question in it is
a pre-registration with a hole an unwelcome result can escape through.

Questions are ordered by how much damage an unlucky answer does.

---

## Q1. Which width does the claim under test actually mean?

**Blocked on WJ-004.** A7's sweep has since established that the public page
states the claim in **relative** form (forest roads of that width show the most
effective firebreak function under Korea-like conditions) and gives no authors, no
sample size and no rate. That fixes how the claim must be characterised, and it
does not answer which width it means, which is what Q1 is about.

The National Institute of Forest Science press release of
2025-04-25 and its attachment 2-2 state a width. The pre-registration measures two
widths that are not the same thing (section 6.3.1): the running surface, and the
full canopy gap including cut slope, fill slope and cleared shoulder. On a Korean
mountain forest road the second can be a multiple of the first.

**Why it decides the study.** If the design tests the canopy gap while the claim
is about the running surface, then whatever comes out is not a test of the claim.
The two are not close enough to hand-wave.

**Options.**
1. Primary covariate is the canopy gap `W_cleared`, on the argument that it is the
   physical gap a front has to cross.
2. Primary covariate is the running surface `W_surface`, on the argument that it is
   what the claim and the road standards are written in.
3. Both, with one named primary before the fit.

**Recommendation.** Option 3 as written: `W_cleared` primary because it is the
physical quantity, `W_surface` reported alongside as the comparable one, and the
naming settled **before** attachment 2-2 is read if it has to be, so the choice
cannot be made to suit an answer.

**A7's sweep has strengthened this recommendation with a mechanism.** Kim and Im
2024 indicate by simulation that widening a road **plus removing fill-slope canopy
fuel** stops the fire, where as-built width alone does not. Fill-slope canopy is
precisely the difference between the running surface and the full cleared gap, so
if that mechanism holds, the canopy gap is the physically relevant width. The
choice of `W_cleared` was made before A3 saw this; it now has a reason behind it
rather than only an argument. See pre-registration section 14.1. If attachment 2-2 turns out to state the running
surface, the comparison table leads with `W_surface` and this is a version bump,
not a silent swap.

**Decides.** John supplies the attachment (WJ-004); A6 ratifies the primary.

---

## Q2. Is the ember arm identifiable at all, and should it be attempted?

The breach form `1 - (1 - p_flame)(1 - p_spot)` needs a spotting **rate**, not
only a jump-distance distribution (pre-registration section 7.3). The rate is a
Poisson intensity estimated from counted detectable spots over estimated active
front length-hours. On five fires, with a minimum detectable spot area of about
four NBR pixels and a 2 km attribution radius, the count could plausibly be in the
tens, and it could plausibly be near zero.

**Options.**
1. Fit the full two-component model as pre-registered, with F4 withdrawing the
   ember arm if the parameters stay prior-dominated.
2. Drop the ember arm now, fit the flame arm alone, and publish the jump-distance
   distribution as a descriptive figure with no model attached.
3. Fit the jump distribution but fix the rate from prior literature.

**Recommendation.** Option 1 as pre-registered, with F4 as the automatic exit, and
with the identification problem now written up explicitly in pre-registration
section 7.7.1: one binary label per segment constrains only the **product** of the
two probabilities, so the split is identified **only** through the far-field spot
record, and only to the extent that spots are detectable. Section 7.7.1 also fixes
in advance what is reported if it stays unidentified, including that the flame
arm's coefficients get renamed as coefficients of a combined breach model.
Option 3 is rejected outright: the only rate literature available is not Korean,
and importing a foreign rate into a Korean breach probability is a foreign
quantity entering a Korean model through a side door. The pre-registration should
not leave that route open, and this entry is the record that it was considered and
refused.

**Decides.** A6.

---

## Q3. One width slope across barrier types, or one per type?

Roads, rivers and ridges all have a width, but a river's width means riparian fuel,
valley position and higher humidity, and a ridge's width is zero by construction.

**Options.**
1. Barrier-type intercepts with a **shared** width slope.
2. Barrier-type intercepts with a **separate** width slope per type.
3. Roads only, with rivers and ridges excluded.

**Why it matters.** Option 1 risks a width slope that is really the
road-versus-river contrast in disguise, which is section 11.2 of the
pre-registration. Option 2 is the honest structure but needs enough segments per
type, which gate G1 may not deliver. Option 3 throws away the only barriers with
real width variation and would likely fail gate W1.

**Recommendation.** Option 1 as primary, with the type-by-width interaction
pre-registered as a secondary that is always reported, and with the width slope
reported both on all barriers and on roads and rivers only (pre-registration
section 6.5). If gate G1 lands in the full-specification branch with enough
segments per type, the interaction becomes interpretable; if not, it is reported as
underpowered rather than as absent.

**Decides.** A6.

---

## Q4. Are the Key and Benson dNBR break points right for Korean stands?

The pre-registration uses 0.10 as the burned threshold, from the Key and Benson
FIREMON scheme, which is a method from outside Korea applied to Korean data. That
is allowed, and it is flagged as a method import. Whether the break points transfer
to Korean pine and mixed stands is not something A3 can settle.

**Options.**
1. Key and Benson break points as the pre-registered default, with the sensitivity
   analysis over `tau_burn` in {0.05, 0.10, 0.15, 0.20} already declared.
2. A verified Korean calibration if A7 finds one in the literature.
3. Calibrate on the study's own fires, which is circular and is not an option.

**Recommendation.** Option 1 now, replaced by option 2 in a version bump if A7
delivers a verified Korean calibration before the signature. Option 3 is named here
only so that nobody proposes it later.

**Decides.** A7 supplies the evidence; A6 ratifies.

---

## Q5. What is the smoke mask rule?

Section 5.2 of the pre-registration requires a smoke mask and does not define one.
This is the largest unclosed hole in the label rule, and the post-fire scene is
taken as early as possible precisely where smoke is thickest.

**Options.**
1. Scene classification cloud classes only, accepting that thin smoke passes
   through and biases dNBR low, which would push segments toward `held`.
2. Scene classification plus an aerosol-optical-thickness threshold from the L2A
   product.
3. Scene classification plus a hand-drawn smoke polygon per scene, which
   reintroduces an analyst into the label path.

**Recommendation.** Option 2, with the threshold fixed before any label is
computed and a sensitivity analysis over it. Option 3 is rejected because a
hand-drawn mask is an analyst decision inside the label, and section 12 of the
pre-registration spends its length keeping analysts out of the label. Option 1 is
the fallback if the aerosol layer proves unusable, and if it is taken, the bias
direction must be stated in the abstract: undetected smoke biases toward `held`.

**Decides.** A6, and it must be closed before the signature.

---

## Q6. Is the primary metric right for the program, or only for this direction?

Pre-registration section 10.2 names the mean out-of-complex log predictive score
per labelled segment. A6 is writing the shared evaluation harness (task T2.1) in
parallel and may name a different program-wide primary.

**Recommendation.** A6's program-wide choice wins, and this document is
version-bumped to match. A3's preference for a proper scoring rule stands on the
argument that the deliverable is a probability a county office would act on, so
calibration is not optional, but the argument is not worth a split between
directions.

**Decides.** A6.

---

## Q7. Should 영덕 2025 be added as a sixth fire?

`docs/benchmark/K_SPREAD_2025.md` makes 영덕 2025 and 의성 and 안동 2025 one
complex. The pre-registration already places 영덕 in the same fold if it is added
(section 2.2), so adding it changes the number of segments and not the number of
folds.

**Options.**
1. Keep the five fires as briefed.
2. Add 영덕 2025 into the existing 2025 fold, for more segments at no cost in
   folds.

**Recommendation.** Option 2, conditional on A2 publishing the complex rule
implementation and on the fire clearing the scene-pair and detection requirements.
More segments is exactly what a design facing gate G3 needs, and the complex rule
makes it free in fold terms. But it is not A3's call, because A2 owns the complex
rule and the orchestrator owns the fire list.

**Decides.** The orchestrator, with A2.

---

## Q8. Can suppression presence be obtained, and what is written if it cannot?

Pre-registration section 12.4: a road that held partly measures that a crew was
anchored on it and burning out from it. There is no suppression resource placement
record in `research/data/REGISTRY.yaml`, and obtaining one is an
information-disclosure request and therefore a human gate.

**Options.**
1. Request the records from KFS or the fire authorities for the five fires.
2. Proceed without, with the estimand stated as operational and associational, as
   the pre-registration already does.
3. Use a proxy, for example proximity to a fire station or to a water source.

**Recommendation.** Option 2 now, because option 1 is slow and may fail, plus
raising option 1 as a new human-gate item so that it is at least in flight. Option
3 is rejected: a proximity proxy would be confounded with the road network itself,
which is the barrier layer, so it would smuggle the barrier into its own control
variable.

**Decides.** John, for whether the request goes out.

---

## Q9. Are the feasibility gate numbers right?

Pre-registration section 11.3 proposes G1 at 150 labelable and 30 held, G2 between
60 and 150, G3 below 60 or below 10 held, W1 at 25 segments each side of 6 m, M1 at
an attenuation factor of 0.70 with 60 hand-measured segments, and P1 at a posterior
standard deviation below 0.8 of the prior.

These numbers are A3's judgement and nothing more. They are in the document because
a gate with no number is not a gate, and they are listed here because a number
chosen by one agent should not survive unexamined into a frozen document.

Section 11.5 adds two more numbers needing the same ratification: the
**recoverability threshold of 0.80** and the **smallest effect of interest**, set
at a change of 0.10 in the modelled probability of a lee-side burn between 3 m and
9 m of effective width. The second is the more consequential, because it is what an
informative null would be null **of**: set too large and a null is easy to declare,
set too small and it is unreachable.

**Recommendation.** A6 ratifies or replaces each, before the signature, and
whatever comes out is frozen. The one A3 would defend hardest is P1, because it is
the only rule that stops a breach curve being drawn out of a prior. The one A3 is
least sure of is G1's threshold of 30 held segments, which is a guess about how
many perimeter-coincident barrier segments five fires contain. The one A3 most
wants a second opinion on is the smallest effect of interest, because it is the
only number here encoding a judgement about what a county planner would act on,
and that is not A3's judgement to make alone.

**Decides.** A6.

---

## Q10. What is done with a SHAP-suggested interaction?

Pre-registration section 8 says SHAP is description only, and that a
SHAP-suggested interaction becomes a hypothesis for a future pre-registration
rather than a term added to this round's model.

**The question is whether that is too strict.** If the classifier plainly finds an
interaction the physics model misses, refusing to look at it in this round costs a
real finding.

**Recommendation.** Keep the rule. The cost of the strict version is a delayed
finding; the cost of the loose version is that the comparison model becomes a
mechanism for adding terms until the physics model wins, which is the exact
failure the comparison was pre-registered to prevent. Any interaction SHAP
suggests is logged in this file, in a section added at the time, with the date and
the fold it appeared in, so that a later pre-registration can pick it up with its
provenance intact.

**Decides.** A6.

---

## Q11. Segment length, once the real counts are known

The pre-registration fixes 100 m with a 30 degree bearing constraint, and
pre-registers sensitivity analyses at 50 m and 200 m (section 3.2). If the eligible
count lands near gate G3, shortening to 50 m would roughly double the row count
while halving the pixels behind each label and adding spatial correlation.

**Recommendation.** Do not take that trade. Shortening segments to clear a gate is
manufacturing sample size, the extra rows are not extra encounters, and the
barrier-line random effect of section 10.6 would absorb most of them anyway. This
entry exists so that the temptation is on the record as refused in advance rather
than debated when the counts disappoint.

**Decides.** A6, and A3 recommends writing the refusal into the frozen document.

---

## Closed since v0.1

| question | closed by | outcome |
|---|---|---|
| how is a flat breach curve to be read, when measurement error and a true null both produce one? | A6, 2026-09-16, written into pre-registration section 11.5 | Five instruments, three running before any label exists: a 30-pair repeat-measurement study, a design-stage recoverability simulation on real geometry with simulated outcomes, a named smallest effect of interest, an equivalence reading of the disattenuated posterior, and measurement validity checks against road class and catchment area. A flat curve is an **informative null** only when all four conditions of section 11.5.6 hold |
| which parameter can this design not identify? | A6, 2026-09-16, written into pre-registration section 7.7 | The flame-crossing and ember-spotting split. One binary label constrains only the product, so identification comes solely from the far-field spot record, and section 7.7.1 fixes what is reported if it stays unidentified |
| how is suppression confounding handled? | A6, 2026-09-16, written into pre-registration section 12.4 | It is not separable with available data, and the document says so. The width coefficient is named **operational barrier performance** everywhere, a proximity proxy is rejected as a bad control, and the roads-against-rivers width slope comparison is pre-registered as a weak and explicitly labelled discriminator |
| how should the NIFoS claim be characterised? | A7, 2026-09-16 | As a **relative** claim, not an absolute sufficiency claim, with no authors, sample size or rate on the reachable page. Written into pre-registration sections 1.2 and 14, and nothing may characterise it as stronger or weaker than that |
| does the forest road layer carry a width attribute? | A1's acquisition round, 2026-09-16 | **No.** Confirmed absent for data.go.kr id 3045621. Image-derived width became the primary path, not a contingency, and gate M1 plus the asymmetric reading of F1 were added |
| NGII or OpenStreetMap for rivers? | A1, 2026-09-16 | OpenStreetMap under ODbL 1.0. NGII returned HTTP 400 twice and is now a human gate |
| 5 m or 30 m DEM? | A1, 2026-09-16 | 30 m (Copernicus GLO-30). Consequences for slope, ridges and approach angle are written into pre-registration section 6.7 |
| where does the containment time for Goseong 2019 come from? | A1, 2026-09-16 | Not from `kfs_fire_stats_csv`, which covers 2022 to 2025. The detection-derived substitution is now pre-registered in section 5.2 |
