# Sign-off record: landslides, PREREG_landslides_2026-09-16_v0.1.md

```yaml
signoff:
  direction: landslides
  prereg_file: research/landslides/PREREG_landslides_2026-09-16_v0.1.md
  prereg_sha256: 58872b44b45d7b84c60c385a977b847c2cf19deef0d769ea9052870a1f8c8348  <!-- forbidden-ok: sha256 -->
  prereg_version: v0.1
  prereg_author: A4
  reviewer: A6
  date: 2026-09-16
  round: 4
  state: signed with conditions
  supersedes: null
  outcome_seen: false
  fits_permitted_on_real_labels: true
  blocking_conditions_open: 11
  numbers_stageable_while_blocking_open: false
  prior_leakage_read: research/eval/leakage_reads/landslides_A6_prior.md
  prior_leakage_read_written_before_reading_prereg: true
```

**State: `signed with conditions`.** Per `research/eval/SIGNOFF.md` section 3 the
design may fit. Eleven of the thirteen conditions in section 10 are blocking for
the primary result and two are blocking for named secondary claims. A number
produced while a blocking condition is open is not staged, and if it has already
been staged it is marked `withdrawn_pending_condition`. Condition C1 alone holds
every one of them shut today: three of fourteen datasets are `verified`, none of
the three carries a covariate or a unit, and two are not registry entries at all.
Without `KMA_APIHUB_KEY` there is no storm enumeration, so there is no risk set
and no rows, which A4 states plainly in section 23 rather than letting me find
it. In practice this signature permits the outcome-free geometric work, the
assignability measurements, the simulation work and the accounting, and nothing
else, until data arrives.

---

## 0. The verdict, in one paragraph

This is a better document than the design it was asked to pre-register, and it
is better because it measured three things instead of arguing them: that no
record in the occurrence file carries a lot number, that the years-since-fire
geometry gives three usable cohorts and four annual steps, and that the
registered split refuses on a shared control identifier. All three re-derive, and
the split demonstration reproduces byte for byte under my own re-run. Both
departures from the brief are right: the catchment replaces the slope unit
because the address cannot reach a slope unit, and the areal count replaces the
unit-level binary because the record does not contain the binary and
manufacturing it would have made the label an artefact of the assignment rule. I
reached both independently before opening the document, which is the first thing
section 3 has to report. **What I add this round is six findings that are new,
none of which needs data, and one of which changes the reading of section 7.** The
identification statement in section 7.1 is not true of the model section 10.3
registers: with unburned controls in the risk set and a calendar main effect,
both the linear years-since-fire term and its curvature are identified, and what
carries them is the assumption that the calendar effect is the same on burned and
unburned ground. Section 6.5's own reporting-attention mechanism is precisely a
violation of that assumption, in the direction of the hypothesis. So the aliasing
section is simultaneously too pessimistic about the rank and too optimistic about
the escape, and the M-A reading rule in 7.6 is calibrated against a design matrix
that is not the one being fitted. The other five are: the F4 margin is stated on a
scale that depends on the unknown zero fraction and is close to certain to fire
whatever the truth; the 리 and 시군구 counts in section 4.2 are name counts and
not place counts; the 시도 column is partly a calendar clock, which makes item A9
a live leakage path into the aliasing rather than a mitigated one; the count
outcome is partly a count of ownership parcels, so the fitted mean is a product of
three things and not two; and the control identifier scheme needs a collision rule
or the fix in 12.3 fails silently instead of loudly. **On whether this direction
should proceed at all, my answer is yes, and the recovery window is withdrawn.**
The support problem is fatal to the question the direction was set, and it is not
a reason to stop, because the two things that survive are real and one of them is
outcome free and can stop the work cheaply.

---

## 1. What the state turns on, and what it does not

**It turns on P12 and on the conditions, not on the design.** `SIGNOFF.md`
section 3 is my own text and it is mechanical: a dataset at status `pending` may
appear, and the sign-off is then `signed with conditions` at best. Eleven of
fourteen are pending and two of those eleven do not exist as registry entries.

**It does not turn on the support problem**, and that needs saying because it is
the largest thing in the document. A design whose estimate is right-censored
below the quantity it was set to estimate is not an unsound design. It is a sound
design pointed at a question the data cannot answer. The protocol's test is
whether the result will mean something whichever way it comes out, and under this
pre-registration it does, on three branches: the fire term at year zero is
estimable and means something either way; failing condition F3 turns the
assignability table into the result and means something either way; and the
aliasing table is outcome free and already means something. What does not mean
anything either way is a recovery window, and condition C9 removes it rather than
hedging it.

**It does not turn on the two departures from the brief.** Both are ratified in
section 5 below.

---

## 2. Item verdicts, P1 to P16

| item | verdict | note |
|---|---|---|
| P1 hypothesis in falsifiable form | **pass** | Direction and null both written. I wrote a satisfying result sentence and a satisfying negation from section 1.2 alone. The five failing conditions of 1.5 are named, thresholded in section 15, and F1 and F4 can both fire against the author |
| P2 unit of analysis | **pass on the text, open on the test** | The row count is a bound and not a number, because the DEM does not exist. The effective sample size has a stated ceiling of 120 storm-by-block clusters and a declared design-effect method. Section 4.3's four clustering axes are right and the storm axis is correctly named the binding one. Condition C10 |
| P3 label rule | **pass on the text, open on the test** | L-A and L-B are ordered procedures with a tie-break at every branch and four real unlabelable classes. This is the best-specified label rule the program has produced. My ten-unit blind pass cannot run: there are no units, no 리 polygons and no storm enumeration. Condition C10 |
| P4 covariates and sources | **pass with conditions** | The table carries knowable-at and the derived-from-label column, and the two `yes` entries have their paragraphs. Section 9.4 is the sharper of the two and is right: an ownership covariate built from the occurrence record's own field would be defined only on rows that have a record. Two registry ids do not exist. Conditions C1, C6 |
| P5 model form | **refused as written, repairable without data** | The likelihood, link, parameterisation, priors and convergence ladder are all present and the identifiability paragraph names four parameters rather than the one the acceptance test asks for. The defect is that section 10.3 does not say whether the fitted model carries a free fire-cohort effect, and section 7's identification claim is computed on a matrix that assumes one. Condition C2 |
| P6 held-out sets | **pass with conditions** | The call reads its arguments from `PRIMARY_SPLITS` rather than retyping them, which is the right construction. The fingerprint is not pinnable and is accepted on the same terms as roads condition C8. Section 12.3 found a real defect in my splitter before it bit. Conditions C7, C10 |
| P7 primary metric | **pass** | One metric, one number, a proper scoring rule with no threshold, and the resampling unit is the cluster of P2 and not the row. Section 13.3's arithmetic on why rows would be wrong by three orders of magnitude is correct |
| P8 simple baseline | **refused as written, repairable without data** | B1 is the right baseline and is the null of the hypothesis made into a model. The margin is a number fixed in advance, which is what P8 asks for, but it is stated on the wrong scale. Condition C3 |
| P9 what counts as failing | **pass with one repair** | Five conditions, each with a threshold and a reading, and section 15.6's Sancheong reading is fixed in both directions in advance, which is the hard part. F4's threshold inherits condition C3 |
| P10 stopping rule and multiplicity | **pass** | Three primaries, two baselines, ten declared sensitivity families, a fit log, one held-out metric computation per model with a second recorded as a finding. The multiplicity argument, that a fixed table is not a search, is correct and is the right reason not to correct |
| P11 leakage self-audit | **pass** | Written and committed before my pass began, per roads condition C10. Section 3 below is the comparison |
| P12 data provenance | **pass, and it caps the state** | Three of fourteen verified, checksums given for all three, two not in the registry. A4 states the cap itself |
| P13 compute and feasibility | **pass** | The cut order is decided in advance and the split, metric, baseline and calendar specifications are named as never cut, which is the only part of a cut list that matters |
| P14 scope declaration | **pass** | Korea only. Sidle 1992 and DeBano 2000 each carry the sentence RC-010 and P14 require, and each is confined to a named subsection |
| P15 what the result will not say | **pass, and it is the strongest section in the document** | Nine claims withdrawn under every outcome. Item 5, that no sentence attributes a landslide to a road, is the one a reader will need and the one nobody would have written unprompted. The enforcement gap is declared rather than promised. Condition C11 |
| P16 shape of the result artifact | **pass** | Every quantity that might be quoted has a key path, including the ones that would embarrass the direction, and the design-side artifact already exists and is committed |

---

## 3. The P11 comparison, and the order discipline that produced it

This is the item roads lost and the item this round exists to recover. Roads
condition C10 says the checklist order is reversed for the other two directions:
A4 writes its P11 verdicts first, A6 writes its own read without opening the
direction's folder, and only then does A6 read A4.

**The order was followed.** `research/eval/leakage_reads/landslides_A6_prior.md`
was written to completion before any file under `research/landslides/` or
`research/reports/A4/` was opened. Its header lists what was consulted: the
program brief's design, `research/README.md`, my own three eval documents, the
data registry, the raw occurrence CSV read directly, `research/eval/splits.py`,
and `research/FORBIDDEN_CLAIMS.md`. Its section 6 records, in advance, where I
expected the review to land.

### 3.1 The order was followed and the independence was still partly defeated

Reading A4's document, the first thing I have to report is against myself.

**The round-4 task brief that set up the ordering contained A4's conclusions.**
It told me, before I wrote a word, that A4 had changed the unit to the catchment
and the likelihood to an areal count and why; that A4 rated support above
aliasing; that A4 read C3 as reporting rather than mapping and rated it worse;
that A4 raised salvage logging; that A4 had corrected the brief on Sancheong's
dates; and that A4 had found the control-sentinel defect in my splitter. Six of
the ten items on which my prior read and A4's checklist agree are items the task
brief named to me first.

So the reversed order was executed in the letter and the information still
travelled from A4 to A6 before A6 wrote. That is the roads failure in a new
shape, and the honest finding of this section is that a reversed order does not
by itself produce an independent comparison. What produces one is a briefing
drawn from the program brief and the data alone, with the direction's own
conclusions withheld. **This is registered as process finding PF-1 in section 12
and I am not treating it as A4's problem, because it is not.**

The prior read is not edited to correct this. It stays as written, the same way
kill-shot items 1 to 4 stay as written, and the correction lives here.

### 3.2 What both lists found, with the contamination marked

Ten items. The **[briefed]** mark means the round-4 task brief named A4's
position on that item to me before I wrote, so the agreement is not evidence of
independent convergence.

1. **[briefed]** The slope unit is unreachable and a coarser unit is forced.
   A6 prior, C10: "the slope unit is not available as a primary unit on this
   record at all, and a coarser unit is not a fallback but the only thing the
   record supports." A4, section 8.3, reaches the same place from two
   independent arguments, the address and the DEM posting.
2. **[briefed]** A unit-level binary manufactures a label the file does not
   contain; a count or area per unit per storm with an exposure offset is what an
   areal record supports. A6 prior, item L1. A4, section 10.2. The two texts
   independently use the same word, manufactured.
3. **[briefed]** The record is administrative and the completeness mechanism is
   reporting, not mapping, and both of us deduced it from the same column, the
   forest ownership class `시설구분_등급`, on the grounds that a mapped inventory
   has no reason to carry ownership. A6 prior, C3. A4, section 6.5 and 17.3.
4. **[briefed]** The road covariate is simultaneously a plausible cause of
   failure and a determinant of whether a failure is reported, nothing in the
   covariate set separates them, and the remedy is a scope cut rather than a
   control. A6 prior, C3 first reason. A4, section 6.5 item 3. Both of us
   independently tied it to roads item B2.
5. **[briefed]** Support, not aliasing, is the binding defect: years since fire
   of zero to three against a Sidle domain running to about twenty-five. A6
   prior, C2, which says my own v1.0 wording of that item is wrong about which
   half of the problem binds. A4, sections 7.5 and 24.3.
6. **[briefed]** Sancheong contributes years since fire of zero only and cannot
   test the window. A6 prior, C8 second problem. A4, sections 3.3 and 15.6.
7. **[briefed]** Salvage logging falls in the same window as root decay and
   pushes the same way, with no dataset. A6 prior, item L4. A4, section 11.6.
   **The task brief described this as a confounder nobody had. The prior read
   contradicts that**: the program brief itself names salvage logging as an
   exposure, and both of us noticed that an exposure with no dataset behind it is
   worse than an omitted one because it looks adjusted for.
8. The root curve's rates cannot be moved by this data, and `t_mid` is the prior
   restated. A6 prior, C9, which argues that item A12's flat-prior sensitivity is
   not a mitigation here but the diagnostic that demonstrates the problem. A4,
   section 10.5 item 1, independently pre-registers exactly that: `t_mid` is not
   reported as an estimate and its prior-to-posterior contraction is reported as
   a diagnostic. **Not briefed, and the closest thing in this list to a genuine
   independent convergence.**
9. The storm is the cluster and the storm count is the binding constraint. A6
   prior, items A11 and L3. A4, sections 4.3, 4.4 and 13.3. **Not briefed.**
10. **[briefed]** The most likely useful output is the assignability and aliasing
    tables rather than a recovery curve. A6 prior, section 6. A4, section 24.2.

### 3.3 What only A6's list found

Five items, all from my own computation on the raw record or my own reading of
`splits.py`, and none of them in A4's checklist. They are why the exercise was
worth running even after 3.1.

- **K1. The national annual volume of the record rises by a factor of about
  twenty-two across the observation window**, so for every cohort a larger years
  since fire means a calendar year in which far more landslides were recorded
  nationally, and the reporting confound therefore runs opposite to the
  hypothesis and biases toward the null. A6 prior, C2. A4 could not have found
  this: section 3.2 of the pre-registration declares the per-year count of
  landslide records as a quantity A4 deliberately did not look at, precisely
  because it is the quantity item C3 turns on. That restraint is correct and it
  has a cost, and the cost is this item. It belongs in the reading rule, because
  it makes a flat or rising fitted curve weak evidence and a falling one
  stronger. It is condition C9's second reason.
- **K2. One storm window carries 50.8 per cent of the entire record**, and
  98.6 per cent of its 2025 rows. Since every years-since-fire value of three is
  the 2022 cohort observed in calendar 2025, the far end of the curve rests on
  one cohort in **one storm**, not merely in one calendar year as section 7.2
  states. A6 prior, section 2. Sharper than A4's version of the same fact.
- **K3. The count outcome is partly a count of ownership parcels.** There are
  2,127 distinct storm-by-리 cells in the record; 62.6 per cent hold one row and
  the largest holds seventy-eight. One failure crossing several ownership parcels
  and several failures in one place are indistinguishable in this file, and the
  split into rows plausibly follows ownership boundaries, whose density is higher
  near settlements, which is where section 6.5's reporting probability is higher
  too. A6 prior, item L5. Condition C6.
- **K4. The triggering event is a multi-day window, so the rainfall covariate
  cannot be the triggering rainfall**, which puts measurement error on the one
  covariate the factor-of-safety link turns on, attenuating it in a known
  direction. A6 prior, item L2. **A4's answer is better than my objection.**
  Section 6.2 enumerates storms from the radar product alone and uses `재난구분`
  only to attach a record to an already-enumerated storm, which converts my
  covariate problem into a record-attachment problem with a declared tie-break
  and a reported `UNASSIGNABLE_TIME` count. I am recording the item as raised and
  answered, not as a condition.
- **K5. The forest-land frame is itself a selection** that bounds what the
  deliverable can be: a failure on a road cut, a fill slope or a cultivated
  hillside is not in this file, and a post-fire landslide warning adjustment has
  users who care about all of those. A6 prior, item L6. A4 has the restriction in
  section 6.3 step 2 as a rule but not in section 21 as a scope sentence. Minor,
  and it is in section 11 rather than in the conditions.

### 3.4 What only A4's list found

Five items, and the second of them is the best thing in the document.

- **J1. The committed precision ladder has no rung for a 리.**
  `research/shared/geo/geocode.py` runs `PARCEL`, `EUPMYEONDONG_CENTROID`,
  `SIGUNGU_CENTROID`, `UNRESOLVED`, and the modal record bottoms out between the
  first two. Carrying 95.64 per cent of the file at `EUPMYEONDONG_CENTROID`
  satisfies the never-mix-rungs rule in letter while discarding the one thing that
  makes the record spatially usable. My prior read said there was no rung below
  the 리 to geocode to and never noticed the ladder itself was missing one. A4's
  `RI_CENTROID` recommendation is right and is correctly routed to A1 as a
  request rather than an edit.
- **J2. The assignability apparatus, M1 to M4, and the U1, U2, U3 gates.** My
  checklist item C10 makes an allegation, that the assignment error is worst
  where the terrain is steepest, and then asks for it to be quantified. A4 turned
  the allegation into a measurement, M2, stratified over the national 법정리
  enumeration by steep-area fraction, reported whichever way it comes out. M1
  runs over the full enumeration of Korean administrative polygons rather than
  over the record's realised addresses, so the scale is chosen by geometry alone.
  M3 decides which covariates survive coarsening by their between-unit variance
  share, which nobody asked for and which is the right instrument. And U3 lets
  the assignability table be the direction's result, with no fit at all. This is
  the answer to my own item and it is better than the item.
- **J3. The separation is measured rather than asserted, and reported as a
  ceiling.** The exposure-weighted R-squared of years since fire on calendar year,
  the variance inflation, and the count of distinct calendar years at each value
  of years since fire, all computed from the fire record alone with no outcome in
  them, and then explicitly labelled an upper bound because the cell grid weights
  every cohort equally in every later year while the realised design will not.
  My prior read asserted the aliasing and gave no measurement.
- **J4. The identity binds only the residual calendar effect once the period
  term is measured storm rainfall at the unit.** Section 7.4. My prior read said
  flatly that an explicit rainfall term does not fix it because the storms are
  few and unequal. A4's mechanism is better than my dismissal: rainfall at fire
  A's location in a year is not rainfall at fire B's location in that year, so a
  spatially varying measured period term is not the same object as a national
  year factor. Section 7.4 then does the honest thing and names what the escape
  converts the problem into, an untestable exchangeability assumption. My
  condition C2 is downstream of J4 and sharpens it rather than contradicting it.
- **J5. The split demonstration**, which found the control-sentinel defect in my
  own splitter. The task brief carried this to me before I wrote, so I do not
  claim it as convergent. It is A4's, it is correct, and section 8 below confirms
  the fix and narrows it.

### 3.5 Verdict differences on the checklist itself

Three items where A4's verdict and mine differ, beyond the mechanism dispute in
section 7 below.

| item | A4 | A6 | ruling |
|---|---|---|---|
| A9 geocoder drift | `mitigated` | `present` | **A6.** A4's justification, that the ceiling is set by the address text which no gazetteer edition changes, is right about the ceiling and wrong about the realised resolution rate. Condition C5 |
| A4 feature support crossing the boundary | `mitigated` | `present` | **A4, conditionally.** My prior read said the radar correlation length spans the 5,000 m block. A4's section 12.4 concedes the point, declares the variogram procedure, and makes a re-registration mandatory if the registered block is too small. That is the right answer and it is already condition-shaped; it is folded into C1 rather than numbered separately |
| C4 severity as covariate and search prior | MAJOR, `mitigated` | MINOR | **A4.** I downgraded it in my prior read on the grounds that with no mappers the search-prior mechanism largely goes away. A4 keeps it at MAJOR and handles it with the S-SEV sensitivity. Keeping a severity item at MAJOR costs nothing and the attention path is real. A4's is the safer call and I adopt it |

---

## 4. The checklist itself is wrong in two places, and it is my file

Recorded here because a checklist that is never corrected by the directions it
audits is a checklist nobody is reading.

**C3 is written for the wrong mechanism.** Its text names mapping campaigns,
imagery, minimum mapped size and who mapped which year. The committed Korean
record contains none of those things. Section 7 below adjudicates the substance;
the file-level consequence is that C3's text is rewritten for the reporting
mechanism in `LEAKAGE.md` v1.1, and C2 and C3 are linked, because section 7
concludes they are one item and not two.

**C10's mitigation text is too weak.** It offers running the primary analysis at
a coarser unit "such as the catchment" as one option among three. The measured
answer is that the slope unit is not available at all, and the v1.1 text says so
rather than offering it as a choice.

Neither correction is made this round, because `LEAKAGE.md` v1.0 is the version
both A4 and I ran and editing it now would make the comparison in section 3
uncheckable. It goes to v1.1 after the suppression direction's P11 is filed, so
that all three directions are audited against one version.

---

## 5. The two departures from the brief, judged

### 5.1 The unit: catchment in place of slope unit. **Ratified.**

Three arguments support it and they are independent of each other.

1. **The address cannot reach a slope unit.** Zero of 5,118 records carry a lot
   number, confirmed by the orchestrator across all four address columns. The
   modal record bottoms out at a 리, and a 리 in a Korean mountain district is
   square kilometres of mixed slope, valley floor and settlement. Assignment to a
   slope unit is not a measurement, it is a draw.
2. **The DEM cannot resolve the initiation site.** At 30 m posting a convergent
   hollow of the order of tens of metres across spans about one cell. Section 5.2
   is right that this kills the slope unit a second time and that the argument is
   independent of the first.
3. **The catchment partition has one free parameter and it is not tuned against
   the outcome.** Section 5.1's procedural argument is the one I would not have
   made and it is correct: a slope-unit partition's half-basin parameters are
   conventionally tuned against a landslide inventory, which is item A3.

**Is the measured assignability rule genuinely outcome-free?** Yes, and the
evidence is stronger than A4 claims for it. M1 runs over the full national
enumeration of 법정리 polygons restricted to forest land, not over the record's
realised addresses, so it contains no landslide data. M2 stratifies that same
enumeration by DEM steepness. M3 is a variance decomposition of covariates. None
of the three touches the outcome. M4 does touch the outcome's addresses, and it
is ordered after the scale is fixed and is declared as able only to shrink the
sample. And the thresholds are not merely asserted to have been fixed first: **the
measurements cannot run today at all**, because they need a DEM and a 리 boundary
layer, neither of which exists, so the gate numbers are provably committed before
their inputs. That is an unusually clean construction and I am ratifying 0.60 and
the six-covariate M3 floor as levels.

The gap is M4. It is the number that decides how many records survive, F3 is
keyed on U1 which is M1-based, and nothing is written about what a bad M4 means.
Condition C8.

### 5.2 The likelihood: areal count in place of unit-level binary. **Ratified.**

A unit-level binary asserts, for every unit not named in the file, that the unit
was observed and found intact. Nothing in a reporting record supports that
assertion, so the label would be an artefact of the assertion and the fitted
hazard would be a model of the assertion. A count with an area offset is what an
areal record supports. Section 10.2's recovery of the unit failure probability as
a derived quantity from the fitted intensity, reported at its own key path with
the note that it is a transformation and not a separately estimated probability,
is the right way to keep the brief's requested quantity without pretending to
have observed it.

The negative binomial over the Poisson is also right, and for the reason given:
recorded landslides clump within a unit and a storm. What `phi` absorbs, though,
is the variance of that clumping and not its mean, and condition C6 is about the
mean.

---

## 6. The support problem, and whether the direction proceeds

**A4 is right that support is the weakest point and right that it is worse than
the aliasing.** It is also worse than section 7.5 states, because every
years-since-fire value of three is the 2022 cohort observed in the single 2025
storm window that carries half the record.

**Is it fatal?** To the question the direction was set, yes, and without
qualification. `research/README.md` asks how long a burned Korean slope stays
more landslide-prone. Prior art puts the analogous effect running to about
twenty-five years. The record reaches three. No statistical treatment reaches
past the last observation, and there is no bound to state either: a lower bound
of the form "at least three years" would rest on one cohort in one storm, and
would be quoted without either qualifier within a month.

**Should the direction stop?** No, and I considered it seriously, because the
brief permits me to conclude otherwise and because eleven of fourteen datasets
are pending, the species arm has no data and may never, salvage logging has no
data, and the reporting term is not identified. Three things decide it the other
way.

1. **The outcome-free work is real, cheap, and can stop the direction itself.**
   Measurements M1 to M3 and gate U1 run before any outcome is touched and can
   return the finding that Korean address-level landslide records cannot support
   a unit-level hazard model at any useful resolution. Gate U3 makes that the
   direction's result rather than a caveat on a different result. A design that
   has pre-registered its own termination and put it first in the gate order is a
   design that should be allowed to reach that gate.
2. **The year-zero contrast is a different question and it is answerable.**
   Whether burned ground carried a higher recorded landslide rate than comparable
   unburned ground, conditional on measured storm rainfall and terrain, is
   estimable with three cohorts, is not right-censored, and means something either
   way. It is not the question the direction was set, and saying so is condition
   C9's job.
3. **Stopping now would discard the aliasing and assignability tables**, which
   are the two things in this document that would be worth publishing whatever
   happens to the hypothesis, and which cost no data to finish beyond a DEM and a
   boundary layer.

**So: proceed, and withdraw the window.** Condition C9 makes this a condition on
the reported **quantity** and not only on the sentence, because RC-003 governs
sentences and a number that exists will find a sentence. The direction reports
the fire term at each of years since fire zero, one, two and three with its
interval, and synthesises no bound, no window, no duration and no lower bound
from them under any outcome. `OPEN_QUESTIONS.md` Q10's recommendation of a
right-censored lower bound is the one place in A4's material where the discipline
slips, and it slips in the direction that section 21 exists to prevent.

---

## 7. The reporting versus mapping question, adjudicated

A4 records the disagreement in section 17.3 and asks for a ruling.

**Ruling: A4 is right on the mechanism, right that it is worse than my version,
and the item is not separate from C2.**

**On the mechanism.** The record's columns are a year, a sequence number, a
multi-day storm window, a forest ownership class, an address path ending at a 리,
and a damaged area in hectares. Every one of the eight values of `시설구분_등급`
is a forest ownership class. A mapped inventory has no reason to carry ownership;
a damage administration record has every reason to, because ownership is who gets
billed and who does the repair. The damaged area in hectares is a damage
accounting quantity, not a mapped scar polygon. My checklist item C3 describes
mapping campaigns, imagery and minimum mapped size, and not one of those things is
in this file. I reached the same conclusion from the same column in my prior read
before opening A4's document, which is section 3.2 item 3, so this is not a
concession under argument.

**On it being worse.** A4 gives two reasons and both hold.

1. The reporting probability depends on proximity to roads and assets, and the
   program brief asks this direction to treat roads as a separate exposure. So
   the confounder and the exposure are the same covariate, measured once. A4's
   remedy is the one the roads direction got for item B2 and it is the correct
   one: the road coefficient lives inside the reporting term, is never given a
   mechanism, and section 21.1 item 5 forbids the sentence. I would not improve
   on it.
2. A reporting record has no observable zero. A mapped inventory at least defines
   its own frame, within which an unmarked slope was looked at and found intact.
   Absence here means either no failure or no report, and no column separates
   them. That is why section 10.5 item 4 is right that the hazard and the
   reporting probability are not separately identified, and why A4's answer to
   its own open question Q8, keep the term and never the claim, is the right
   answer: the choice is not between an identified model and an unidentified one,
   it is between an unidentified term that is named and an unnamed confound.

**Where I go further than A4, and it is the finding of this round.** A4 treats
C3 and C2 as two sections. Section 7.4 comes within one step of joining them,
noting that the residual calendar effect "is exactly the reporting-attention
term", and then stops. Taking the step:

Post-fire administrative attention is not a calendar main effect. It is
attention to **burned** land in the year or two after a named fire, which is a
**burned-by-calendar-year interaction**. And that interaction is precisely the
term whose freedom destroys the identification of the years-since-fire term. I
re-derived the rank on the model section 10.3 actually registers, with unburned
controls in the risk set:

| design, including unburned control rows | columns | rank | deficiency |
|---|---|---|---|
| intercept, calendar year, `burned`, `burned * t` | 8 | 7 | 1 |
| the same plus `burned * t^2` | 9 | 8 | 1 |
| the same plus free fire-cohort dummies | 12 | 10 | 2 |
| the same plus a free burned-by-calendar-year interaction | 16 | 11 | 5 |

At three usable cohorts and five observation years. The deficiencies of one and
two are ordinary dummy traps. **The linear years-since-fire term is identified in
the registered model**, and it stops being identified only in the last row.

So C3 is not a bias that sits beside C2. C3 names the specific mechanism by which
the assumption that carries C2's escape is violated, and it is violated in the
direction and with the time profile of the hypothesis. The two are one item. My
checklist goes to v1.1 saying so, and condition C2 makes the pre-registration say
so.

**One consequence for A4's own reading rule.** Section 7.6 restricts what may be
read from specification M-A to the curvature, on the strength of a rank
deficiency that the registered design does not have. That restriction discards
identified information for a reason that is not true of the model being fitted,
while the thing that genuinely threatens both the linear term and the curvature,
the burned-by-year interaction, has no specification and no reading rule at all.
That is the wrong way round, and condition C2 fixes it. The kill shot's
discriminating test T1 is built on the same finding.

---

## 8. The split fix, confirmed and narrowed

**The demonstration reproduces exactly.** I re-ran the call myself, without
executing A4's script, since running it would write into a directory I do not
own. On the declared geometry my fingerprints are
`7eab0f0267fb318ad36a9bcb70106b7da64955b4469a76094f66e60d5732a5f3` for the <!-- forbidden-ok: sha256 -->
fires-only case and
`5138895ca17fe17af909f3ce39618026e1e828d54c5bce464a30bad65e046178` for the <!-- forbidden-ok: sha256 -->
unique-identifier case, matching the committed `split_demo` values, and the
shared-sentinel case raises the refusal with the committed message.

**The unique-identifier rule is the right fix, and the diagnosis is right.**
`require_fire_disjoint=True` routes every row's identifier through `complex_of`
and unions every block that shares a key. A control has no fire, so one shared
sentinel unions every control block in the country into one group, and since
controls are by construction spread nationally that group swallows the country.
The splitter then refuses, which is the correct behaviour and a great deal better
than returning a split, but the message sends the reader hunting for a block size
rather than for the identifier. Giving each control its own identifier welds
nothing, which is exactly right, because a control has no fire to straddle. A
control that sits near a burned unit is still welded correctly, through block
membership rather than through its identifier, and the 1,000 m buffer covers the
rest. Section 12.3's second observation, that the buffer rarely drops a row in
the fire-only geometry but does matter for controls, is correct and reproduces.

**The narrowing, and it is a defect in my code and not in A4's design.**
`canonical_fire_id` normalises by stripping whitespace, underscores, hyphens,
dots, commas, parentheses and middle dots, and lowercasing. So `CONTROL_1_2`,
`CONTROL_12` and `CONTROL-12` all resolve to the same key. `spatial_block_cv`
calls `complex_of(..., strict=False)`, so an unregistered identifier is accepted
with no guard at all. Two colliding control identifiers weld two spatially
distant control blocks into one group **silently**, producing a plausible split
rather than a refusal, which is worse than the failure the fix repairs. A4's
demonstration scheme, `CONTROL_<integer>` with no internal separators, is safe;
a scheme keyed on a block index or an administrative code would not be. Condition
C7 requires an identifier scheme that is injective after `canonical_fire_id` and
an assertion of injectivity before the call.

Both the sentinel collapse and the normalisation collision are pinned this round
in `research/eval/tests/test_signoff_landslides.py`, so the trap cannot change
under either of us without a test failing. I am not changing `splits.py` itself:
the roads v0.2 signature is against the current behaviour, and a refusal that
fires is not a bug.

---

## 9. Findings that are new this round

Six, none of which needs data. C2, C3, C4, C5, C6 and C7 in section 10 are these.
They are listed there rather than repeated here.

The one that matters most is C2, because it is the only one that changes what
section 7 of the pre-registration means. The one that is most likely to be
dismissed as bookkeeping and should not be is C4, because a join on a 리 name
without its parent path is the kind of defect that produces a working pipeline
and a wrong answer.

---

## 10. The conditions

Thirteen. Each names the verification action that clears it and the phase by
which it must clear. Eleven are **primary**, meaning blocking for the primary
result; two are blocking for a named secondary claim.

**C1. Every dataset reaches `verified` before any fit on real outcomes.**
Blocking for the **primary** result. Three of fourteen are verified today and
none carries a covariate or a unit; two are not registry entries at all. This
condition also carries section 12.4's undertaking: the rainfall variogram range
is measured once the radar product is in hand, the registered 5,000 m block is
confirmed to exceed it, and if it does not the block is raised and that is a new
version rather than a tweak. *Clears when:* the provenance table of P12 reads
`verified` on every row with a checksum, and the variogram range is reported.
*Phase:* before any fit.

**C2. State which calendar and cohort terms the fitted model contains, recompute
the rank on the realised design, and rewrite the M-A reading rule.** Blocking for
the **primary** result. Section 7.1 says the linear component of the
years-since-fire term is not identified. That is true of the burned-cell grid with
a free cohort factor, which `aliasing_separation.py` measures, and it is not true
of the model section 10.3 registers, which carries unburned controls in the risk
set, a calendar main effect, and the fire term as `burned` times a function of
`t`. On that design the deficiency is one, the ordinary dummy trap, and both the
linear term and the curvature are identified; with free cohort dummies the
deficiency is two and both remain identified; the deficiency reaches five only
when a burned-by-calendar-year interaction is free. So the estimate is carried by
the assumption that the calendar effect is the same on burned and unburned
ground, and section 6.5's reporting-attention mechanism is a named violation of
exactly that assumption, with the same sign and the same time profile as the
hypothesis. *Clears when:* v0.2 states whether the fitted model carries no cohort
effect, fixed cohort effects or a random cohort effect; recomputes the rank on the
realised design matrix including control rows and reports it at
`aliasing.realised.rank_deficiency`; replaces section 7.6's M-A restriction, which
is calibrated against a matrix the design does not have; and adds the
burned-by-calendar-year specification and its reading rule, which is kill-shot
test T1. *Phase:* before any fit. No data needed.

**C3. Restate the F4 margin on a scale that does not depend on the zero
fraction.** Blocking for the **primary** result. The margin is 0.01 nats per
storm-unit cell in at least four of five blocks. On section 19's own estimate of
about half a million rows and at most 5,118 non-zero cells, zero cells at a small
intensity contribute a per-cell difference of order the intensity itself, so the
mean over all cells is dominated by the non-zero cells at a weight below about
0.01. Reaching 0.01 nats per cell therefore requires a mean improvement of about
one nat on every non-zero cell, which is a very large effect for adding a fire
term, and it is required in four blocks of five. F4 is close to certain to fire
whatever the truth, and its reading is that the fire terms buy nothing over
rainfall and terrain, which is a sentence that will be quoted as evidence against
H-SLIDE. A failing condition that fires regardless of the truth is not a test.
*Clears when:* the margin is restated either as a total held-out log predictive
density difference or as a difference per non-zero cell with the zero-cell
contribution reported separately, and the number is fixed after the row count is
known but before any fit, in a new version under section 4 of the protocol.
*Phase:* before any fit.

**C4. A 리 name is not a place; resolve on the full parent path and report both
counts.** Blocking for the **primary** result. `address_precision.py` reports
`distinct_values` as counts of distinct name strings, so section 4.2's bounds of
1,427 리 and 154 시군구 are name counts. Re-derived from the same file on the <!-- forbidden-ok: 154 -->
full address path: 1,813 distinct (시도, 시군구, 읍면, 리) tuples and 173
distinct (시도, 시군구) pairs; 263 리 names occur in more than one place and one
occurs in seven. The bound in 4.2 is understated by about twenty-seven per cent
at the 리 rung, which is the minor half. The major half is that a join keyed on
the 리 name alone would weld records from different provinces into one confusion
set, and section 6.3 step 1 resolves by rung without stating that resolution is on
the full parent path. *Clears when:* v0.2 states the resolution key explicitly as
the full parent path, reports both the name count and the place count at
`counts.*`, and the assignment code asserts the key is the tuple. *Phase:* before
any fit. No data needed.

**C5. The 시도 column is partly a calendar clock; item A9 is `present`, not
`mitigated`.** Blocking for the **primary** result. The column carries eighteen
names for seventeen provinces. 강원도 appears only in 2021 and 2022 and
강원특별자치도 only in 2023, 2024 and 2025; 전라북도 only in 2023 and
전북특별자치도 only in 2024 and 2025; and 제주시, which is a 시군구, appears once
in the 시도 column in 2022. Both renames fall inside the observation window and
each is an exact function of calendar year. A4's A9 justification, that the
ceiling is set by the address text and no gazetteer edition changes it, is right
about the ceiling and wrong about the realised rate: against a boundary layer of
one vintage, the resolution success rate becomes a function of calendar year,
`geocode_rung` becomes a calendar variable, and `UNASSIGNABLE_ADDRESS` becomes a
calendar-dependent exclusion. Calendar year is what years since fire is aliased
with, so this is a path from the gazetteer straight into C2. *Clears when:* v0.2
declares the boundary layer's vintage, declares the rename reconciliation as a
rule applied to every record rather than as a fix-up, handles the 제주시 rung
error by a declared rule, and reports the resolution rate by year at a key path
whichever way it comes out. *Phase:* before any fit. No data needed for the rule.

**C6. Name the third factor in the fitted mean, and pre-register the count
versus area choice with both reported.** Blocking for the **primary** result.
Section 10.5 item 4 names the fitted mean as a product of a hazard rate and a
reporting probability. It is a product of three things. The record's row is an
administrative damage entry keyed to an address and an ownership class, so one
failure crossing several ownership parcels and several failures in one place give
the same cell count; the split into rows plausibly follows ownership boundaries,
whose density is higher near settlements, which is where the reporting
probability is higher too. `phi` absorbs the clumping into the variance and leaves
the mean contaminated. **Declared, because it bears on this condition:** A6 has
computed per-year and per-place counts of the occurrence record, which section 3.2
of the pre-registration declares as quantities A4 deliberately did not look at.
The condition is therefore written so that it removes a degree of freedom rather
than steering a choice: **both the count outcome and the damaged-area outcome are
reported, whichever way they come out**, so that A6's having seen the clumping
distribution cannot bias a choice that is not being made. *Clears when:* v0.2
names entry multiplicity as the third factor in section 10.5 item 4, pre-registers
both outcomes with the count as primary and the area as a declared parallel, and
adds the clumping diagnostic to the key paths. *Phase:* before any fit.

**C7. The control identifier scheme must be injective after
`canonical_fire_id`.** Blocking for the **primary** result. The fix in section
12.3 is right and reproduces exactly, and the narrowing is in my code, not A4's
design: the normaliser strips underscores, hyphens, spaces and dots, so
`CONTROL_1_2` and `CONTROL_12` collide, and `spatial_block_cv` calls `complex_of`
with `strict=False` so nothing guards it. A collision welds two distant control
blocks into one group silently, producing a plausible split instead of a refusal.
*Clears when:* v0.2 declares the scheme, `CONTROL_<integer>` with no internal
separators being sufficient, and the fitting code asserts injectivity of the
normalised identifiers before calling the splitter. A6 has pinned both the
sentinel collapse and the collision in `research/eval/tests/`. *Phase:* before the
fingerprint is pinned.

**C8. Give M4 a floor and a reading rule.** Blocking for the **primary** result.
The assignability apparatus is ratified, including the thresholds, and the gap is
the last measurement. M4 is the realised assignable share and it decides how many
records survive, but F3 is keyed on gate U1, which is M1-based, so a realised
share far below the M1 share would leave the direction with a chosen scale, a
passed gate and almost no data, and nothing written about what that means.
*Clears when:* v0.2 fixes a floor on M4 and its reading in both directions, in the
shape of section 8.5's other gates. *Phase:* before any fit, and before M4 is run.

**C9. No window, no duration, no bound.** Blocking for the **primary** result.
Section 7.6 reading rule 2 says the reported quantity is not a recovery window;
`OPEN_QUESTIONS.md` Q10 recommends reporting a right-censored lower bound over
years zero to three. The second will be the one quoted. The support is worse than
section 7.5 states: every years-since-fire value of three is the 2022 cohort seen
in calendar 2025, and one storm window carries 50.8 per cent of the occurrence
record and 98.6 per cent of its 2025 rows, so the far end of the curve is one
cohort in one storm. The second reason is finding K1: the national annual volume
of the record rises about twenty-two-fold across the window, so for every cohort a
larger years since fire is a calendar year with far more records nationally, which
means the reporting confound runs opposite to the hypothesis and a flat or rising
fitted curve is weak evidence while a falling one is stronger. That asymmetry
belongs in the reading rule before the fit, in the same shape as roads item B12.
*Clears when:* v0.2 withdraws the Q10 wording, states that the direction reports
the fire term at each of years since fire zero, one, two and three with its
interval and synthesises no bound, window, duration or lower bound from them under
any outcome, and writes the K1 asymmetry into the reading rule. RC-003 governs the
sentence; this condition governs the quantity, which is what RC-003 cannot reach.
*Phase:* before any fit.

**C10. P3 and P6 are passed on the text and not on the test.** Blocking for the
**primary** result, and accepted on the same terms as roads conditions C8 and C9.
My ten-unit blind pass of sections 6.2 to 6.4 cannot run because there are no
units, no 리 polygons and no storm enumeration. The second label pass of section
6.6 has not run. The split fingerprint is not pinned and cannot be. *Clears when:*
both label passes have run and their disagreement rates are in the next version
rather than a footnote, and the fingerprint is computed over the committed unit
layout in its committed row order, before any outcome is assigned to any unit, and
written into the `prereg:` block of the version that does so. A mismatch at
verification is a refusal with no discussion. *Phase:* before any fit.

**C11. The vocabulary needs a detector.** Blocking for the **primary** result.
Section 21.2 declares the enforcement gap itself, which is the right way to raise
it. Roads answered the identical condition with
`research/roads/check_vocabulary.py`. RC-003, RC-004 and RC-005 cover `research/`
only until WJ-002 lands, and the permitted vocabulary of 21.2 is finer-grained
than any of them. *Clears when:* a local detector exists for this direction,
covering at minimum the forbidden list in 21.2, with the both-directions
validation record `research/FORBIDDEN_CLAIMS.md` requires of a rule. *Phase:*
before any number leaves the direction.

**C12. The species arm.** Blocking for a **named secondary claim**, the pine
versus broadleaf contrast. Section 11.4's construction is ratified: the
misclassification grid, the unvalidated-classifier wording and failing condition
F5 are the right treatment, and 11.4's observation that the only Korean reference
layer against which the fallback could be validated is the layer the fallback
exists to replace is correct and is the reason the arm cannot be rescued by
effort. *Clears when:* either `kfs_forest_type_map` clears WJ-018 and WJ-012, or
the phenological classifier is validated against a Korean reference that is not
that map. Until then no species contrast is reported. *Phase:* before any species
number.

**C13. Salvage logging is not carried as though it were adjusted for.** Blocking
for a **named secondary claim**, any root-specific reading of the fitted `g(t)`.
`gamma_salvage * salvage_frac` is a declared term with no dataset behind it, and
a declared term with no data is worse than an omitted one because it reads as
adjusted for. A4's remedy in 11.6, naming `g(t)` a combined root-decay and
post-fire-management term in the abstract rather than in a limitations paragraph,
is the right one and matches the treatment of the `D` and `R` split in 10.5 item
2. *Clears when:* either `kfs_salvage_logging` exists and is `verified`, or the
term is removed from the model and the composite naming is applied everywhere the
fitted curve is quoted, including every figure caption. *Phase:* before any fit,
for the naming; before any salvage coefficient, for the data.

---

## 11. What is not a condition, and why

- **The support problem itself.** It is not a defect in the design and no
  condition can clear it. It is a fact about the record, it is stated in the
  document three times, and what it requires is that the direction not claim a
  window, which is condition C9.
- **The reporting term not being identified.** A4's answer to Q8 is right: the
  choice is between an unidentified term that is named and an unnamed confound.
  Section 21.1 item 5 and section 10.5 item 4 carry it. Making it a condition
  would be asking for an identification the record cannot supply.
- **`D` and `R` not being separable.** Same shape as roads item B8, and section
  10.5 item 2 pre-registers the right answer, which is to report only the
  composite and to name it in the abstract rather than in a limitations
  paragraph.
- **`t_mid` not being identified.** Section 10.5 item 1 already forbids reporting
  it as an estimate and reports its prior-to-posterior contraction instead. That
  is better than a condition.
- **My finding K4, the multi-day storm window.** Raised in my prior read as item
  L2 and answered better by section 6.2 than I posed it. Recorded in section 3.3
  and not carried forward.
- **My finding K5, the forest-land frame.** A scope sentence for section 21
  rather than a leakage path. Recommended, not required.
- **Gate U2 being more generous than the evidence.** Section 8.5 lets the
  slope-unit arm run if it passes U1, and section 8.1 makes clear it will not.
  A4 records the expectation so it can be scored later and pre-registers
  reporting the arm as not run. That is the correct construction and a stricter
  gate would buy nothing.
- **The `RI_CENTROID` request.** Correctly routed to A1 as open question Q1 and
  as a request rather than an edit. It is not mine to condition and A4 was right
  not to make it.

---

## 12. Process notes

- **No git command was run**, read-only or otherwise. The split verification
  imported `research/eval/splits.py` and ran it over the declared geometry
  directly; the checksums quoted in this record were computed by hashing files on
  disk. A6 self-reported running a git command in the previous round and the
  route used this round is the intended one.
- **Nothing outside `research/eval/**` and `research/reports/A6/**` was written.**
  A4's scripts were read and not executed, because running them writes into
  `research/landslides/design/`, which A6 does not own; every verification was
  re-derived instead.
- **Step 1 was completed before step 2.**
  `research/eval/leakage_reads/landslides_A6_prior.md` was written to completion
  before any file under `research/landslides/` or `research/reports/A4/` was
  opened, and it is not edited afterwards.
- **PF-1, a process finding against the reviewer's own briefing.** Roads
  condition C10 reversed the P11 order, and the order was followed, and the
  independence was still partly defeated because the round-4 task brief named
  A4's conclusions on six of the ten convergent items before A6 wrote. Section
  3.1 has the detail. The successor to C10, for the suppression direction, is
  that the briefing given to A6 for its prior read is drawn from the program
  brief and the committed data alone, with the direction's own conclusions
  withheld until the prior read is committed. A reversed order without an
  information barrier is a ritual.
- **Three claims verified by the orchestrator were not re-checked**, per the
  round brief: the zero lot numbers, the fire cohort counts, and the age, period
  and cohort rank result. One line on the last of these, as asked. A4 reports a
  rank deficiency of three on `[1, t, year, cohort]` at every cohort set; my own
  reconstruction returns four on the short sets. The difference is the year-dummy
  basis: A4's script builds dummies only for calendar years the cell grid
  actually populates, so at the 100 ha floor the 2021 column does not exist,
  while a basis over all five observation years carries an all-zero column for
  it. Both are correct arithmetic on different grids and the substantive result is
  identical on both, since adding a squared term raises the rank by exactly one.
  It is worth one sentence in v0.2 so that a later reader does not think one of
  the two is wrong.
- **No em dashes.**
- **A6 did not contribute to this design**, so the standing rule in `SIGNOFF.md`
  section 5 about not signing a design A6 helped create does not apply. My
  contribution is `LEAKAGE.md` and `splits.py`, both of which A4 audited against
  and one of which A4 found a defect in.
