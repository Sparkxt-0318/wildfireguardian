# Suppression direction, pre-registration, v0.1

```yaml
prereg:
  direction: suppression
  version: 1
  date: 2026-09-16
  author: A5
  items_present: [P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, P15, P16]
  result_artifact: "research/suppression/results/suppression_v0.1.json"
  primary_metric_json_path: "held_out.primary_metric.value"
  split_call: "forward_chaining_by_year(report_years, **PRIMARY_SPLITS['suppression']['kwargs'])"
  split_fingerprint: "does not exist; the registered call refuses the committed record, see section 13.2"
  primary_metric: "held-out mean log predictive density per fire of the 10 ha exceedance indicator at horizon H3"
  baseline: "B0, the training-window exceedance base rate"
  datasets: [kfs_fire_stats_csv, kfs_fire_state_history_csv, kfs_fire_stats_api,
             kma_asos_aws, vworld_geocoder, firms_active_fire_korea, dem_korea,
             kfs_forest_roads, base_map_linear_features, kfs_forest_type_map]
  outcome_seen: partly, and section 2 lists exactly what
  signoff: unsigned
  signoff_record: null
```

**Nothing in this direction has been fitted.** Section 2 lists every quantity of
this direction's outcome that A5 has been told or has read, and who saw it, so
that section 4 of `research/eval/SIGNOFF.md` has nothing to find later. The
answer is not "none", and pretending otherwise would be the first thing wrong
with this document.

**A5 has not read `research/eval/leakage_reads/suppression_A6_prior.md`, nor
anything else under `research/eval/leakage_reads/`.** That file was written
while this document was being drafted and A5 was instructed, before filing, not
to open it, because it carries outcome views including an unadjusted
night-against-day comparison on burned area, which is this direction's own
headline contrast. It has not been opened. Section 2.5 records the one
incidental exposure to the neighbouring landslides read that did occur, so that
the declaration is complete rather than merely clean.

**This document does not pre-register the design it was handed.** Three of its
load-bearing choices are changed, each for a reason that is measured in section
2 or section 5 rather than argued from taste, and section 1.6 lists them
together rather than leaving them to be discovered. The largest of the three is
that the counterfactual question the direction was set is withdrawn as a
reported quantity, and section 3 fixes in advance what is reported instead.

---

## 0. Where each required item lives

| item | section |
|---|---|
| P1 hypothesis in falsifiable form | 1 |
| P2 unit of analysis | 8 |
| P3 label rule | 9 |
| P4 covariates and sources | 10 |
| P5 model form | 11 |
| P6 held-out sets named in advance | 13 |
| P7 primary metric | 14 |
| P8 simple baseline | 15 |
| P9 what would count as failing | 16 |
| P10 stopping rule and multiplicity | 17 |
| P11 leakage self-audit | 18 |
| P12 data provenance | 19 |
| P13 compute and feasibility | 20 |
| P14 scope declaration | 21 |
| P15 what the result will not say | 22 |
| P16 shape of the result artifact | 23 |

The five things this direction was told to confront rather than file as
limitations are in sections 3 (the unobserved counterfactual), 4 (four years),
5 (report time against ignition time), 6 (the held-out year) and 7 (the neural
extreme-value model). Each ends with a pre-registered reading rule or a gate,
not with an acknowledgement.

---

## 1. The hypothesis, in falsifiable form (P1)

### 1.1 The question as it was asked

Recorded Korean fire sizes are cut short by firefighting. Which fires would have
grown large, and can that be flagged in the first hours?

### 1.2 The estimand, split in two, because only one of the two is identified

The question contains two quantities and they are not the same object.

**Q-CF, the counterfactual.** For a Korean fire with covariates `x`, the
distribution of the size it would have reached had suppression not been applied.
**This quantity is not identified by any Korean record, and section 3 shows why
in a form stronger than the usual one: it is not that the data are thin, it is
that the event of interest never occurs.** Every Korean forest fire is
suppressed. A hazard analysis in which no subject ever experiences the event
identifies nothing about the event-time distribution without an assumption that
does the identifying.

**Q-OP, the operational quantity.** For a Korean fire with covariates `x`
knowable at a fixed horizon after the fire is reported, the probability that its
**recorded final size** reaches a stated floor, under the suppression regime
that was actually operating. This is identified, it is what the record contains,
and it is the only thing the deliverable the brief asks for needs. An integer
point score that flags fires in their first hours is a statement about Q-OP. It
does not require Q-CF and it is not improved by pretending to have it.

**The pre-registered estimand of this direction is Q-OP.** Q-CF appears in this
document only in section 3, only as an assumption-indexed sensitivity family,
and never as a reported distribution under any outcome.

### 1.3 The hypothesis

`research/FORBIDDEN_CLAIMS.md` fixes the permitted wording of H-SUPP and this
section does not restate it as a result. In the estimand of 1.2, the testable
clause is:

> Among Korean forest fires, information knowable within three hours of the
> report time separates the fires whose recorded final size reaches 10 ha from
> those whose does not, better than the exceedance base rate of the preceding
> years, and the margin is at least 0.02 nats per fire in held-out mean log
> predictive density under forward-chained evaluation by report year.

The predicted direction is positive: the covariate model scores better than the
base rate. The value under the null is zero improvement, which is what a base
rate delivers by construction.

### 1.4 This hypothesis is wrong if

The covariate model does not beat the base rate B0 of section 15 by at least
0.02 nats per fire in held-out mean log predictive density averaged over the
forward-chaining folds, or the 90 per cent cluster bootstrap interval on the
difference contains zero. Either of those is a failure of the testable clause,
and section 16 fixes the reading of each in advance.

*A6's acceptance test for P1, anticipated.* Both sentences are writable from the
text above. **Support:** "the covariate model scored 0.0N nats per fire above
the training-window base rate on held-out report years YYYY to YYYY, with a 90
per cent interval excluding zero." **Negation:** "the covariate model did not
separate the two classes better than the base rate of the preceding years by the
pre-registered margin on held-out report years YYYY to YYYY, and the interval on
the difference contains zero." Neither sentence can be written from the other's
outcome.

### 1.5 The failing conditions, fixed now

Five, each with a threshold in section 16 and a reading that cannot be re-read
as a success:

- **F1.** The margin against B0 is not met, or its interval contains zero.
- **F2.** Gate G1 never opens, because the Korean record never reaches the depth
  the registered split needs. The direction then reports no held-out number at
  all, and the deliverable is the accounting of sections 4 and 5.
- **F3.** Gate G4, the tail recoverability instrument, fails. No generalised
  Pareto model is fitted and no size distribution is reported.
- **F4.** The night contrast changes sign anywhere inside the declared
  report-offset grid of section 5.4. The night arm is withdrawn, not caveated.
- **F5.** The integer score's held-out log score is worse than the hazard
  model's by more than 0.01 nats per fire. The distillation is reported as lossy
  and the score is not recommended.

### 1.6 Where this document departs from the design it was handed

**Three departures, and a fourth thing dropped.**

1. **The counterfactual size distribution is withdrawn as a reported quantity**
   (section 3). The brief asks which fires would have grown large. This document
   answers which fires did grow large under the regime that operated, says why
   the other question is not answerable from a Korean record, and reports a
   sensitivity family rather than a distribution.

2. **The night arm becomes a containment-hazard contrast, not a growth
   contrast** (section 12). Leakage item D2 is right and it is fatal to the arm
   as briefed: the record carries a final area entered after containment and no
   area at any intermediate hour, so night-versus-day **growth** has no
   observable to compare. What can be compared is the rate at which fires are
   contained by local solar phase. That is a different quantity and this
   document calls it one.

3. **Cause is removed from the primary covariate set** (section 10.4). The brief
   names it as a first-hours covariate. The record's own cause field carries the
   words 조사중, 추정 and 미상 on 34.75 per cent of rows, and 73.22 per cent of
   rows carry a free-text detail code rather than a coded one. A field that
   records its own investigation status is an outcome of an enquiry, not an
   observation available three hours in.

4. **The partially interpretable neural extreme-value model is not designed
   against at all** (section 7), because the brief makes it conditional on a
   confirmation that has not happened and because it is not in the verified
   bibliography.

---

## 2. What has been seen, and by whom

Section 4 of `research/eval/SIGNOFF.md` defines a look at data as any view of
the outcome variable or of any quantity computed from it, **including a summary
from another agent.** This direction has two outcome variables, the recorded
burned area and the report-to-containment duration, and A5 has been shown
summaries of the first. This section exists so that the amendment machinery has
a starting point rather than a memory.

### 2.1 Outcome quantities A5 has been told, in the round-1 briefing

| quantity | value as briefed | who computed it |
|---|---|---|
| fires of at least 10 ha, by report year 2022 to 2025 | 26, 32, 1, 19 | A4, `research/landslides/design/aliasing_separation.py` |
| fires above 30 ha in 2024 | none | A4, same |
| fires of at least 100 ha, by report year | 11, 8, 0, 6 | A4, same |
| national burned area by report year, ha | 24,797 / 4,988 / 131.93 / 105,011 | A4, same |
| negative durations, statistics file | 12 | A1 and A2, counted independently |
| negative durations, state-history file | 41 | A1 and A2, counted independently |
| impossible end years, statistics file | 2, being 2055 and 2223 | A1 |
| the Uiseong 2025 duplicate pair and its two areas | two same-day records | registry, carried from the program brief |

**A5 has recomputed none of them** and has not looked at the burned-area column,
at any duration, or at any cross-tabulation of either against a covariate.
`research/suppression/design/clock_and_address.py` states in its own docstring
what it deliberately does not read, and it reads neither outcome column.

### 2.2 What this contaminates, stated plainly

The exceedance counts in 2.1 are the outcome of this direction at the two floors
the brief names. Knowing them shaped three things in this document and it would
be dishonest to present any of them as independent of that knowledge:

- the choice of 10 ha rather than 100 ha as the **primary** floor, made because
  a year with no positives makes a precision-recall summary undefined and 2024
  is that year at the 100 ha floor;
- the concentration gate G3, which exists because one 2025 complex is known to
  dominate the excess mass;
- the decision to gate the tail fit rather than caveat it.

All three are conservative in the sense that they make the direction harder to
claim a result from, not easier. That is an argument, not a defence, and A6
should weigh it as one.

### 2.3 What A5 has read

`research/eval/SIGNOFF.md`, `research/eval/LEAKAGE.md`,
`research/eval/NUMBERS_PROTOCOL.md`, `research/eval/splits.py`,
`research/eval/signoffs/roads_v0.2.md`,
`research/eval/signoffs/landslides_v0.1.md`,
`research/eval/signoffs/LEDGER.md`, `research/FORBIDDEN_CLAIMS.md`,
`research/data/REGISTRY.yaml`, `research/data/checks/probe_kfs_api.py`,
`research/shared/qc/timestamps.py`, `research/shared/qc/complexes.py`,
`research/shared/geo/solar.py`, `research/lit/suppression_prior_art.md`,
`research/lit/UNVERIFIED.md`, `research/lit/bibliography.bib`, and the
landslides direction's v0.1 pre-registration and its supporting documents as
worked examples of the standard.

### 2.4 What A5 has NOT read, declared rather than assumed

`research/eval/leakage_reads/suppression_A6_prior.md` has not been opened, at
any point, by A5. Neither has `research/eval/leakage_reads/landslides_A6_prior.md`
as a document. This matters more than a usual such declaration, because A6's
prior read for this direction is known to contain outcome views of the committed
extract, including an unadjusted night-against-day comparison on burned area,
and reading it before filing would make this a post-registration on its own
headline contrast.

### 2.5 The one incidental exposure, declared because it happened

During the survey pass of this repository, before A6's suppression read existed,
A5 ran a repository-wide text search for the strings `10 ha`, `100 ha` and
`30 ha`. Two of the matching lines it printed came from
`research/eval/leakage_reads/landslides_A6_prior.md`, as two lines of context
and nothing more:

1. a line of landslide **damaged-area** figures by year, which is the landslides
   direction's outcome and not this one's;
2. a line restating the fire cohort counts at the 10 ha floor, 26 in 2022, 32 in
   2023 and one in 2024, which are the same figures section 2.1 already records
   A5 as having been given in its own briefing.

Neither line added information about this direction's outcome beyond what 2.1
already declares, and the suppression read did not exist at that time. It is
recorded here anyway, because a declaration that lists only the exposures that
were harmless is not a declaration.

### 2.6 The information barrier, which A6 raised as process finding PF-1

A6's landslides record closes with PF-1: the reversed self-audit order was
followed and independence was still partly defeated, because the briefing named
A4's conclusions before A6 wrote its own list. The successor condition named
there is an information barrier rather than an order.

**A5 cannot honour that barrier from this side, and says so rather than
claiming it.** The round-1 briefing for this direction states in its own words
that the unobserved counterfactual is A6's strongest prior objection to this
direction. That is A6's conclusion on the single largest item, delivered to the
author before the author wrote. Section 3 was therefore written knowing where
the reviewer stands on it. The mitigations available to A5 are two and both are
weak: section 3 states the objection in a sharper form than the briefing did and
carries it to a withdrawal rather than to a mitigation, and this paragraph
records the contamination so that A6 can discount section 3's apparent
convergence accordingly.

---

## 3. The counterfactual, confronted

### 3.1 It is not censoring, and calling it censoring is the first error

The brief and leakage item D4 both describe the recorded Korean fire-size
distribution as right-censored by suppression. The word is doing damage.

In ordinary right-censoring, each subject carries an event time `T` and a
censoring time `C`, the analyst observes `min(T, C)` and the indicator
`delta = 1{T <= C}`, and identification of the distribution of `T` rests on
having subjects for whom `delta = 1`. The Kaplan-Meier estimator is identified
because some subjects have the event.

Here, let `S*` be the size a fire would reach if it burned until it stopped on
its own and let `S` be the recorded final size. Suppression is applied to every
Korean forest fire, so `S <= S*` always and `delta = 0` for every row in the
record. **There is no subject with the event.** The record contains not one
Korean fire that burned to its own natural end, and the estimator of `S*` is
therefore whatever the model extrapolates past the last instant at which any
fire was observed still burning. That is a property of the assumption, not of
the data.

This is worse than a small-sample problem and it does not improve with a longer
record. A record reaching 1991 would add thirty more years of fires, every one
of them suppressed, and `delta` would still be zero on all of them.

### 3.2 The assumption a correction would rest on, stated as an assumption

Any recovery of `S*` from this record needs, at minimum:

> **A-NI, conditionally non-informative suppression.** Given the covariates `X`
> knowable at the prediction horizon, the containment process and the latent
> growth process are conditionally independent. Equivalently: among fires of the
> same `X` still burning at fire-hour `t`, the instantaneous growth intensity is
> the same as it would have been among fires of that same `X` had none of them
> been contained.

A-NI is what makes a fitted containment hazard combinable with a fitted growth
process to give a distribution for `S*`. **A-NI is false in Korea in a known
direction.** Dispatch is not blind. Crews, engines and the leased helicopter
fleet are sent preferentially to the fires that look dangerous, which means
containment is applied hardest exactly where the latent growth intensity is
highest, which is the violation A-NI forbids. Conditioning on `X` repairs this
only if `X` contains everything the dispatcher conditioned on, and section 10
shows that `X` contains almost none of it: there is no resource record, no
dispatch record, no crew count and no helicopter count in either committed file.

So the honest statement is not that A-NI is an approximation. It is that A-NI is
violated, that the sign of the violation is known, and that the size of it is
not.

### 3.3 What would falsify A-NI, and whether Korea can run the test

A-NI has a testable implication: **conditional on `X`, the containment hazard
must not respond to anything that shifts suppression supply without shifting
the fire's own growth potential.** If it does, and if the recorded sizes move
with it, then suppression is informative about growth and A-NI fails.

Three candidate supply shifters exist in a Korean record, in decreasing order of
credibility:

1. **Concurrent regional fire load.** On a day when several fires are burning in
   one province, the marginal fire competes for the same engines and the same
   aircraft. Load at the moment of report is computable from the statistics file
   alone, inside the training fold, and it is a covariate rather than an outcome.
   Its exclusion restriction is the weak point and it is a real one: a day that
   produces many fires is a dry windy day, which also produces more dangerous
   fires. The restriction is therefore conditional on the day's weather, and
   residual violation is not excluded.
2. **Local solar phase as a fleet constraint.** Rotary-wing water-dropping
   capacity is constrained after dark. This is the same variable as the night
   arm and cannot serve both as the exposure of interest and as the instrument
   that validates the assumption underlying its interpretation, so it is not
   used as a falsification handle here.
3. **Calendar staffing.** Weekends and public holidays change the standing duty
   roster. This is a weak shifter and it is correlated with the human ignition
   pattern that drives Korean spring fires, so it is recorded as a candidate and
   not registered as a test.

**The falsification test, fixed now.** Fit the containment hazard with and
without the concurrent-load covariate, inside the training folds only. A-NI
fails if the concurrent-load coefficient's 90 per cent posterior interval
excludes zero after conditioning on the pre-registered weather covariates. The
test is one-sided in reading: **a rejection falsifies A-NI, and a failure to
reject does not support it**, because the power of this test on a four-year or
even a thirty-year Korean record is unknown and the confounding path runs
through weather that is measured with error.

### 3.4 What is reported if A-NI cannot be defended, which is the expected case

**A5's prior is that A-NI cannot be defended and that the test in 3.3 will
either reject it or be uninformative.** The pre-registered consequence, fixed
before any fit:

- **No size distribution with the suppression effect removed is produced, at any
  stage, under any outcome.** Not as a figure, not as a table, not as a
  parameter, not in a caveated footnote. Rule RC-006 governs the sentence and
  this section governs the quantity, because a number that exists finds a
  sentence eventually.
- **The tail model is fitted, if gate G4 permits, to the recorded sizes and is
  described as the tail of the recorded sizes under the operative suppression
  regime.** That is a real and citable quantity. It is what a Korean planner
  actually faces.
- **The counterfactual appears only as a bounded sensitivity family**, indexed by
  a single named parameter `phi` in [0, 1], the share of the containment hazard
  attributable to suppression rather than to fuel exhaustion and terrain, with
  `phi` fixed at the three declared values 0.00, 0.50 and 1.00. The three
  resulting exceedance curves are reported **as three curves with their
  assumption printed on each**, never interpolated, never envelope-filled, and
  never summarised as a single corrected curve. `phi = 0` is the recorded
  distribution itself. `phi = 1` is the extreme in which every containment was
  suppression and no fire would ever have stopped on its own, which is
  physically false and is included precisely so that the reader sees the width
  of the assumption rather than a preferred value inside it.
- **If gate G4 fails**, even that family is not produced, and the tail is
  reported as the count of recorded exceedances by report year and by season.

### 3.5 Why this is not the direction dying

The deliverable the brief asks for is an integer point score that flags fires in
their first hours. That deliverable is a statement about Q-OP and it survives
section 3 untouched. What section 3 removes is a quantity nobody needs for the
deliverable and which the record cannot supply. The landslides direction reached
the same shape of conclusion for a different reason and A6 ruled that it should
proceed; the argument here is the same argument.

---

## 4. Four years, confronted, and the gate that stops the fit

### 4.1 The record, as measured

`kfs_fire_stats_csv` is at status `verified` and covers **report years 2022 to
2025, 2,020 rows**. `kfs_fire_state_history_csv` is at status `verified` and
covers **2022-01-01 to 2025-11-10, 2,030 rows**. `kfs_fire_stats_api` is at
status `pending`; the record's true depth is unknown because
`DATA_GO_KR_KEY` is unset and the 1991 probe in
`research/data/checks/probe_kfs_api.py` has never run. That is human gate
WJ-001, and WJ-006 is the drafted records request that goes out only if the
probe shows the API does not reach 1991.

Four report years, one of which carries a single fire at the 10 ha floor and
none above 30 ha.

### 4.2 The registered split refuses the committed record, demonstrated

`research/eval/splits.py` registers this direction's primary split as
`forward_chaining_by_year` with `min_train_years: 10, horizon: 1, gap_years: 0`.
Run against the committed record's four report years it raises, verbatim:

```
LeakageRefusal: 4 distinct year(s) cannot support min_train_years=10 plus a
horizon of 1. Shorten the training requirement or say in the pre-registration
that the record is too short for this scheme.
```

**This pre-registration takes the second option and does not take the first.**
The training requirement is not shortened. `PRIMARY_SPLITS` is A6's file, this
direction does not edit it, and a modeller who shortens a registered training
window because it refuses his data has converted a gate into a preference.

A6's own test `test_the_registered_suppression_split_refuses_the_committed_four_year_extract`
in `research/eval/tests/test_splits.py` already asserts this refusal. The gate
that stops this direction is therefore not a number this document chose. It is
someone else's committed code with someone else's test on it, and it refuses
today.

### 4.3 How deep the Korean record must reach, arithmetic

The registered scheme yields `max(0, Y - 10)` folds on `Y` distinct report
years. Run on synthetic year lists, which contain no outcome:

| distinct report years | folds the registered scheme yields |
|---|---|
| 4 (the committed record) | refuses |
| 10 | refuses |
| 11 | 1 |
| 12 | 2 |
| 15 | 5 |
| 20 | 10 |
| 25 | 15 |
| 35 (1991 to 2025) | 25 |

**So the API probe's answer is the whole question.** If `kfs_fire_stats_api`
reaches 1991 this direction has 25 folds and a genuine forward-chained
evaluation. If it reaches 2015 it has one fold, which is one held-out year and
is not an evaluation. If it reaches only 2022 the direction has no evaluation at
all and section 16's F2 applies.

A one-line summary for whoever clears WJ-001: **the record must reach at least
2014 for one fold to exist, and at least 2010 for the five folds that make a
season-by-season ledger mean anything.**

### 4.4 The effective sample size, and why it is much smaller than the row count

Four clustering axes, in increasing order of how much they bind:

1. **The fire.** Every fire-hour of one fire shares its weather, its terrain,
   its crew and its address. Anything fire-level has an effective count equal to
   the number of fires, not the number of fire-hours.
2. **The complex.** `research/shared/qc/complexes.py` collapses the 2025
   Yeongdeok, Uiseong and Andong records into one complex per the K-SPREAD rule.
   Section 9.4 registers what happens to the other multi-county events, because
   the module names that one complex and no other.
3. **The report day crossed with the province.** Korean spring fires arrive in
   bursts on a handful of dry, windy, high-wind-warning days. Fires sharing a day
   and a province share the weather, the fire-danger rating, the duty roster and
   the aircraft. This is the binding axis, and it is the analogue of the storm
   axis that A6 accepted as binding for the landslides direction.
4. **The report year.** Doctrine, the leased fleet, the reporting rules and the
   detection system all change between years. Four years is four.

**For the tail model the binding count is the number of independent large-fire
episodes, not the number of large-fire rows.** A5 has not computed that number
and will not before the gates, because computing it requires reading the
burned-area column. What can be said without reading it is structural: the
statistics file records one row per administrative fire report, a single
connected fire crossing three counties therefore appears as three rows, and the
complex module currently collapses exactly one such event.

The effective sample size is reported beside every interval, computed at fit
time by the declared design-effect method of section 8.4, and it is the number
A6 should look at before any interval in this direction's output.

### 4.5 The gates, fixed now

Six gates. Each is checked, in order, before any fit whose outcome variable is a
real label. A gate that does not pass stops the thing it gates and the stop is
reported as the result of that arm, per section 16.

**G1, the split gate. Blocking for everything.**
`forward_chaining_by_year(report_years, **PRIMARY_SPLITS['suppression']['kwargs'])`
must return without raising and must return at least two folds. Two rather than
one, because a single fold is a single held-out year and carries no variation
across folds from which to compute anything. On the committed record this gate
is shut. Degrees of freedom available to A5: none.

**G2, the exceedance count. Blocking for the tail model.** Every training fold
must contain at least 50 fires whose recorded size reaches the threshold `u` of
section 11.6, counted after the complex collapse of section 9.4, and the
held-out year at least 5. Fifty is a working convention for a stationary
generalised Pareto shape and this document states it as a convention rather than
as a theorem; G4 is the gate that actually does the work and G2 exists so that
G4 is not run on a count where its answer is obvious.

**G3, the concentration gate. Blocking for the tail model.** No single complex
may contribute more than 25 per cent of the summed excess in any training fold.
This is a data-adequacy gate and not outcome-driven cleaning in the sense of
leakage item A8, because **no row is dropped by it**: the gate's only action is
to stop the tail fit and report the concentration. The distinction matters and
A6 should check it: a rule that removes rows on the basis of the outcome is A8,
a rule that refuses to fit on the basis of the outcome's concentration is a
declared stopping rule under P10, and this is the second.

**G4, the tail recoverability instrument. Blocking for the tail model.** Before
any fit on real sizes, simulate 100 replicate exceedance sets at the smallest
training fold's own exceedance count from a generalised Pareto distribution with
the pre-registered scale and with shape `xi` set at 0.20 and at 0.80 in turn.
Fit the section 11.6 tail model to each replicate. The gate passes if, at each
of the two generating values, at least 80 of the 100 replicates put posterior
probability of at least 0.80 on the correct side of `xi = 0.40`. If it fails,
**no generalised Pareto model is fitted at all** and section 3.4's fallback
applies. Every number in this gate is fixed in this paragraph and none of them
may move after the exceedance count is known.

**G5, the covariate-dependent shape. Blocking for a named secondary claim.** The
shape parameter `xi` carries covariates only if the smallest training fold holds
at least 250 exceedances. Below that, `xi` is constant across covariates and
only the scale `sigma` carries them, and the document reports that the shape was
held constant and why. A covariate-dependent shape estimated on a few dozen
exceedances is a restatement of its prior.

**G6, the neural extreme-value model.** Section 7. Not available in v0.1 under
any outcome.

---

## 5. Report time against ignition time, confronted

### 5.1 What is measured about the clock, and what is not

`research/suppression/design/clock_and_address.py` measures the report clock and
`research/suppression/design/design_numbers.json` commits the result. Nothing in
it reads a burned area or a duration.

- **The clock is minute-resolved.** 2.48 per cent of report times fall on the
  hour and 4.11 per cent on the hour or the half hour. There is no rounding
  artefact, so an hourly discrete-time hazard has a clock that can carry it.
- **The report-hour histogram is heavily daytime.** 1,576 of 2,020 fires are
  reported between 10:00 and 17:59 KST. 98 are reported between 00:00 and 05:59
  and 112 between 20:00 and 23:59, so **210 fires, 10.40 per cent, are reported
  in the clock-hour night.**
- **The night arm's exposure in the hazard model is not that number**, because
  the hazard model counts fire-hours and a fire reported at 16:00 that burns
  through the evening contributes night fire-hours. Fire-hours depend on
  durations and durations are the outcome, so the exposure of the night arm
  cannot be measured before the fit. This document states the fire-level bound
  and refuses to state the fire-hour figure, and section 12.5 makes reporting it
  a condition on the night arm's output.

### 5.2 The algebra of the offset

Let `g` be ignition, `r` the reported start recorded in 발생일시, and
`D = r - g >= 0` the report offset. The record contains `r` and never `g`. The
registry records that every duration in both files is report-to-containment.

Let the true containment hazard as a function of true fire age `a` be `h(a | x)`.
The clock this direction can actually run is `t = a - D(x)`. What the model fits
is therefore

    h_tilde(t | x) = h(t + D(x) | x)

**If `D` were a constant**, the whole hazard curve shifts along the age axis and
its shape is preserved. Only the origin moves, the hazard ratios between
covariate levels are untouched, and the harm is confined to the interpretation
of the baseline's first bin.

**`D` is not a constant and the damage is not in the baseline.** Taking logs and
expanding to first order in `D`,

    log h_tilde(t | x) ≈ log h(t | x) + D(x) · ∂ log h(a | x) / ∂a

so the fitted log-hazard for every covariate picks up a term equal to **the
covariate's report offset multiplied by the age slope of the true hazard**.

### 5.3 The direction of the bias, which is the dangerous one

The age slope is negative in any plausible containment process: the fires that
are going to be caught quickly are caught quickly, the risk set at later hours
is progressively enriched for the hard ones, and the hazard falls with age. So
`∂ log h / ∂a < 0`, and a covariate with a **larger** report offset acquires a
**lower** fitted containment hazard, purely from the clock.

A lower containment hazard means a longer fitted duration, which means a larger
fitted size. So the clock alone manufactures the finding that late-reported
fires are harder to contain and end up bigger.

**Which covariates have large `D`?** The remote ones, the ones far from a road,
the ones in low-population districts, and the ones that start at night. Those
are exactly:

- the **access-distance** covariate, which is the covariate the escape score
  would lean on hardest;
- the **night** indicator, which is the entire third arm of this direction.

**Both of the direction's headline covariates are biased by the clock in the
direction that confirms the hypothesis.** This is the same shape as the finding
A6 recorded against the landslides direction, where the reporting-attention
mechanism ran with the same sign and the same time profile as the hypothesis,
and it should be read with the same suspicion. It is not a caveat. It is the
mechanism by which this direction would produce a wrong answer that looks right.

Including `D` as a covariate does not help, because `D` is not observed.
Including remoteness as a covariate does not help either, because remoteness is
the very thing whose coefficient is contaminated.

### 5.4 The offset grid, and the measurement that would set its endpoints

**The grid, declared now.** Model `D | x` as `D = m + d · 1{night or remote}`
with `m` in {0, 0.5, 1, 2} hours and `d` in {0, 0.5, 1, 2} hours, a sixteen-cell
grid. For each cell, refit the discrete-time hazard with the fire's clock origin
shifted back by the implied offset and its first `D` hours entered as delayed
entry, which is a cheap refit of the same model and not a different model.
**The primary result is reported at the cell `m = 0, d = 0`, which is the naive
clock, and the whole grid is reported beside it.** Reporting the naive cell as
primary is deliberate: it is the cell that a reader would otherwise assume, and
putting the grid next to it is what makes the assumption visible.

**M-R, the measurement that would replace the grid's guesswork with Korean
data.** For fires with a VIIRS or MODIS active-fire detection whose timestamp
precedes 발생일시, the difference `r - (first detection)` is a **lower bound on
`D` for that fire**, observed rather than assumed. Registry id
`firms_active_fire_korea`, status `pending`, behind `FIRMS_MAP_KEY` and
therefore behind WJ-001.

Its limitations are declared now rather than found later. The 375 m sensor
detects only fires already large at overpass, so the bound is available on a
size-selected subsample; overpasses are a few per day so the bound is coarse;
and a fire not detected before its report yields no bound rather than a bound of
zero. The selection runs toward the large fires, which is inconvenient for
generality and convenient for this purpose, because the large fires are the ones
whose offset matters to the tail.

**If M-R runs**, the grid's `m` and `d` are re-registered in a v0.2 from the
measured distribution, before any fit, and the amendment carries section 4's
"what was seen" block. **If M-R never runs**, the grid stays at the values
declared in this section, and the pre-registration states in its output that the
endpoints are assumptions and not Korean measurements.

### 5.5 The reading rule, fixed now

- **The night contrast and the access-distance coefficient are quoted with the
  grid attached, always.** A quotation of either at the naive cell alone is a
  forbidden phrasing and is listed as such in section 23's
  `forbidden_phrasings`.
- **If the sign of the night contrast flips anywhere inside the sixteen-cell
  grid, the night arm is withdrawn**, per F4. It is not reported with a caveat,
  because a sign that depends on an unmeasured nuisance parameter is not a
  finding.
- **If the access-distance coefficient's sign flips inside the grid**, access
  distance is withdrawn from the reported covariate effects and retained only as
  a predictor inside the score, where its coefficient is not interpreted.
- **No sentence in any output says the report-time offset has been corrected.**
  At best it is bounded below on a size-selected subsample, and the grid is a
  sensitivity family and not a correction.

---

## 6. The held-out year that may not be held out

Leakage item D5 requires forward chaining and gives the reason: policy drift
across a long record. The item's premise cuts the other way as well and this
section is about that.

**A held-out report year is not independent of its training years.**

1. **Weather is shared within a year and the fires arrive in bursts.** A single
   synoptic pattern can produce most of a Korean spring's large fires within a
   fortnight. A held-out year is then effectively a handful of weather episodes,
   not a few hundred independent draws, and the fold-to-fold variation in the
   primary metric will be dominated by which episodes fell in which year.
2. **Policy is shared across the boundary.** Doctrine, the leased fleet contract
   and the standing dispatch rules are set for periods longer than a year, so
   adjacent years share the regime that the forward-chained split is supposed to
   respect. The split protects against a 2020 rule predicting a 1998 fire; it
   does not make 2023 independent of 2022.
3. **One 2025 event dominates the record.** The registry records the Uiseong
   2025 duplicate pair and the K-SPREAD rule names the Yeongdeok, Uiseong and
   Andong complex. A fold whose held-out year is 2025 is, for the tail model,
   largely a single event, and a fold whose training window contains 2025 is
   trained largely on that event.
4. **The year boundary itself leaks.** The docstring of
   `forward_chaining_by_year` names this direction explicitly: a fire reported on
   31 December is contained in the next year. The registered kwargs nonetheless
   set `gap_years: 0`. Section 13.3 registers what this direction does about
   that, and `OPEN_QUESTIONS.md` Q3 asks A6 whether the registered value is
   intended.

**What is pre-registered in response, rather than acknowledged:**

- **The effective sample size at the day-by-province axis is reported per fold**,
  beside the fold's metric, so that a reader can see how many independent
  episodes a held-out year actually contained.
- **The fold-level metrics are reported individually and never only as a mean.**
  A mean over folds whose effective counts differ by an order of magnitude hides
  precisely the thing this section is about.
- **The season-by-season ledger the brief asks for is reported per fold as well
  as pooled**, for the same reason.
- **No year is designated a stress test.** The landslides direction learned that
  a famous event is only held out if nobody read about it first, and leakage item
  A6 applies here with more force than there: every agent in this program knows
  what happened at Uljin in 2022 and at Uiseong in 2025. The honest mitigation is
  the one A6's own checklist names, which is to fix the design before touching
  the data, keep the amendment record, and state the limitation rather than
  pretend the split cured it.

---

## 7. The neural extreme-value model

The brief permits the Richards and Huser partially interpretable neural
extreme-value model **only if A6 confirms the large-fire sample is sufficient**.

**This document does not design against it and does not reserve a place for it.**
Three reasons, and the third is the one that settles it:

1. The confirmation has not happened, and section 5 of `SIGNOFF.md` is explicit
   that silence is not a signature.
2. Gate G5 already says that a covariate-dependent **shape** is out of reach
   below 250 exceedances in the smallest training fold. A neural
   parameterisation of the same quantity needs more, not less.
3. **It is not in the verified bibliography.** `research/lit/bibliography.bib`
   carries `liu2022fasterrisk` and `ustun2017riskslim` for the scoring method,
   both verified by A7 on 2026-09-16. It carries no entry for arXiv 2208.07581,
   and `research/lit/suppression_prior_art.md` states in its own words that no
   dedicated sweep for this direction has been run. A method this direction
   cannot yet cite is a method this direction cannot yet pre-register.

**If A6 confirms sufficiency**, the route is a v0.2 pre-registration with its own
date and version, carrying the mandatory "what was seen before this amendment"
block, and not a substitution at fit time. The model does not appear in section
17's fit enumeration, so fitting it under this version would be an undeclared
fit and a P10 violation on its own.

---

## 8. The unit of analysis (P2)

### 8.1 Two models, two units

**U1, the containment hazard.** One row is **one fire-hour**: the pair (fire,
integer hour since report) for every hour in which the fire was still
uncontained at the start of the hour. A fire contributes rows from hour 1 until
the hour of containment inclusive, or until the end of the record if it is still
burning then.

**U2, the size model and the score.** One row is **one fire complex**, after the
collapse of section 9.4. The outcome is the complex's recorded final size for
the size model, and the 10 ha exceedance indicator for the score.

### 8.2 Expected row counts

**U2 is exact and known without touching the outcome.** The committed record
holds 2,020 statistics rows and 2,030 state-history rows. After the complex
collapse the count falls by the number of rows merged, which section 9.4's rule
determines and which is reported per fold.

**U1 is a bound and not a number, and the reason is discipline rather than
ignorance.** The fire-hour count is the sum of durations, and the duration
distribution is this direction's outcome. Computing it now would be a look at the
outcome under section 4 of `SIGNOFF.md` and would have to be declared in section
2. So U1's row count is reported at fit time and the bound registered here is:
`n_rows(U1) >= n_fires`, with equality only if every fire were contained inside
its first hour.

A6's acceptance test for P2 asks for the row count and the effective sample size
as numbers, with the second smaller. For U2 both are supplied below. For U1 the
row count is deferred to fit time by the rule just stated, and A5 expects this to
be an open item in the same class as the landslides direction's deferred row
count rather than a pass.

### 8.3 The clustering structure, stated explicitly

| axis | what it shares | binds which model |
|---|---|---|
| fire | weather, terrain, address, crew, the whole covariate vector | U1, totally: all of a fire's fire-hours are one observation for anything fire-level |
| complex | a single connected event reported as several administrative rows | U1 and U2 |
| report day crossed with province | the synoptic weather, the fire-danger rating, the duty roster, the aircraft | **the binding axis for both** |
| report year | doctrine, fleet, reporting rules, detection | the fold structure itself |

### 8.4 The effective sample size and the method

The resampling unit for every interval in this direction is the **day-province
cluster**, not the fire and never the fire-hour. The effective sample size is
reported as

    n_eff = n_clusters / (1 + (m_bar - 1) * rho)

with `m_bar` the mean cluster size and `rho` the intra-cluster correlation of the
10 ha exceedance indicator, both estimated inside the training folds only, per
leakage item A1. `n_eff` is reported beside every interval, per fold and pooled,
and is one of the key paths of section 23.

For the tail model the reported effective count is additionally **the number of
distinct complexes contributing an exceedance**, because that is the count that
governs a tail fit and it is smaller again.

---

## 9. The label rule (P3)

### 9.1 What is being labelled

Three labels, each with an explicit unlabelable class.

**L-SIZE, the exceedance indicator.** For a complex, `1` if its recorded final
size in 피해면적_합계, summed over the rows merged into the complex, is greater
than or equal to the floor; `0` if it is less; **unlabelable** if every merged
row has a missing or non-numeric area. Floors: 10 ha primary, 100 ha secondary.
Unit: hectares as recorded, with no conversion. Tie-break: a value exactly equal
to the floor is a `1`.

**L-CONT, the containment indicator per fire-hour.** For fire-hour `t`, `1` if
the fire's containment timestamp falls inside that hour, `0` if it does not and
the fire is still uncontained at the hour's end, and the fire's rows end at the
`1`. **Unlabelable** if the containment timestamp is missing, is earlier than
the report timestamp, or carries an impossible year.

**L-PHASE, the local solar phase of a fire-hour.** `night` if the hour's
midpoint falls between local sunset and local sunrise at the fire's coordinates,
`day` otherwise, computed with `research/shared/geo/solar.py` and with nothing
else. **Unlabelable** if the fire has no coordinates at a precision the rule
accepts, per 9.3.

### 9.2 The timestamp rule, and the two transforms that are not interchangeable

`research/shared/qc/timestamps.py` supplies two layer-1 parsers because the two
KFS files carry two different real column shapes, and it flags rather than drops.

- For `kfs_fire_stats_csv`: `flag_kfs_ymdhm_timestamps`, on the
  `발생일시_*` and `진화종료시간_*` quadruples.
- For `kfs_fire_state_history_csv`: `flag_kfs_state_history_timestamps`, on the
  combined `진화시작시간` and `진화완료시간` strings.

**The rule for flagged rows, fixed now and never revisited after seeing a fit.**
Per leakage item D9, flagged rows are neither silently dropped nor silently
kept:

1. A row with an impossible containment year (the two known cases, 2055 and
   2223) is **unlabelable for L-CONT** and its fire contributes **no fire-hour
   rows to U1**. It remains in U2 with its recorded area, because the area is
   not the defective field.
2. A row with a negative duration (12 in the statistics file, 41 in the state
   history file) is **unlabelable for L-CONT** and its fire contributes no
   fire-hour rows to U1. It remains in U2.
3. Counts of both classes are reported per fold, in the result artifact, and
   their share of the U2 exceedances is reported separately, because a defect
   that concentrates on the large fires is a different problem from one that does
   not.
4. **No row is ever excluded from U2 on the basis of its area.**

### 9.3 The address rule, and the ceiling it runs into

Every spatial and solar covariate needs coordinates. The record has none.
`research/suppression/design/clock_and_address.py` measures how far an address
can be resolved, over all 2,020 rows:

| address fields present (시도 / 시군구 / 읍면 / 동리) | rows | share |
|---|---|---|
| all four | 1,703 | 84.31 % |
| 시도, 시군구, 동리, no 읍면 | 303 | 15.00 % |
| 시도, 읍면, 동리, no 시군구 | 9 | 0.45 % |
| 시도 and 동리 only | 4 | 0.20 % |
| 시도, 시군구, 읍면, no 동리 | 1 | 0.05 % |

**Zero of the 2,019 rows that carry a finest address field carry a lot number in
it.** The three values containing any digit at all are 장충2가, 평화2가 and
우아1가, which are district names and not 지번. So the `PARCEL` rung of
`research/shared/geo/geocode.py` is unreachable for the whole file, exactly as
A4 measured for the landslide occurrence record, and the finest reachable rung
is the 리 or 동 polygon.

**Two further defects that a naive join would hit silently.**

- Among the 1,703 fully addressed rows there are 1,503 distinct four-tuples and
  1,250 distinct finest names, and **191 of those 1,250 names occur under more
  than one parent path.** Resolving on the finest name alone would weld distinct
  places together. **The pre-registered rule is that an address is resolved on
  its full parent path and never on the finest name alone.** This is the same
  defect A6 wrote as landslides condition C4, found independently in this file.
- The province column carries **18 raw values for 17 provinces**, because one row
  spells 충남 with a trailing space. Any per-province random effect or grouping
  built on the raw column would split that province in two. **Every address field
  is whitespace-stripped before any grouping, join or geocode**, and the count of
  rows whose raw spelling differed is reported.

**The consequence for L-PHASE and for access distance, stated now.** A 리
polygon in a Korean mountain district spans kilometres, so a 리 centroid is not
the fire. The error in an access-distance covariate computed from a centroid is
therefore largest in the largest and most mountainous 리, which are exactly the
places where access distance is largest and where the escape hypothesis expects
its signal. **The assignment error is correlated with the covariate it
measures**, which is the same shape as landslides item C10. Section 18 registers
this as a proposed new leakage item D13 rather than filing it under an existing
one.

L-PHASE is less exposed, because sunrise and sunset move slowly with longitude
inside one province, but it is not unexposed, and the rule is that the phase is
computed from the centroid with the precision class carried as a covariate and
never used as a filter.

### 9.4 The complex rule, and the gap in it

`research/shared/qc/complexes.py` implements the K-SPREAD rule and its
membership table names **one** complex: the 2025 Yeongdeok, Uiseong and Andong
event. It names no complex for 2022, although the largest event of that year
crossed county boundaries in the same way.

**The pre-registered rule for this direction:**

1. Apply `assign_complex_id` with the shipped membership table, unchanged. This
   direction does not edit `research/shared/`.
2. Then apply a **supplementary adjacency rule, declared here and keyed on
   geography and time only**: two rows merge if their provinces are the same,
   their 시군구 are adjacent in the administrative boundary layer, and their
   report timestamps fall within 48 hours of each other. Transitive closure is
   taken. **The rule uses no area and no duration**, because a complex rule keyed
   on size would group on the outcome and would be leakage item A8 wearing a
   different hat.
3. The number of merges the supplementary rule makes, and the rows it merges,
   are reported in the result artifact per fold.
4. `OPEN_QUESTIONS.md` Q2 asks A2, who owns `research/shared/qc/`, whether the
   membership table should carry the 2022 event so that all three directions
   group it identically. **If A2 adds it, the supplementary rule is expected to
   make zero additional merges for that event, and that agreement is itself
   reported as a check.**

### 9.5 The second pass P3 requires

P3 asks for a blind second pass over at least thirty units by a path the author
did not write, with the disagreement rate in the pre-registration rather than in
a later footnote.

**It cannot run, and this document says so rather than promising it.** L-SIZE
and L-CONT are deterministic functions of committed columns, so a second pass on
them measures a reimplementation and not a judgement, which is worth doing and is
registered as a condition rather than claimed as done. L-PHASE cannot be labelled
at all today, by anyone, because it needs coordinates and the geocoder is behind
WJ-001. A5 expects this item to be passed on the text and open on the test, in
the same class as the corresponding items in both signed records.

---

## 10. Covariates and their sources (P4)

### 10.1 The prediction horizon, named once and used everywhere

**H3: three hours after the report timestamp.** Every covariate below must be
writable down at H3 by somebody standing at a desk with the information that
existed then. The horizon is fixed here and does not move; a sensitivity at H1
and H6 is declared in section 17 as a fully reported family, with H3 the primary.

### 10.2 The table

`knowable_at` is the moment the value could first have been written down.
`from_label` is leakage item D1's question: is it derived from anything that
touches the outcome.

| name | definition | unit | registry id | knowable at | from label |
|---|---|---|---|---|---|
| report hour | local clock hour of 발생일시 | hour | `kfs_fire_stats_csv` | report | no |
| weekday | 발생일시_요일 | factor | `kfs_fire_stats_csv` | report | no |
| day of year | from 발생일시 | day | `kfs_fire_stats_csv` | report | no |
| solar phase | day or night at the fire's coordinates, `research/shared/geo/solar.py` | binary, time-varying | `kfs_fire_stats_csv` + `vworld_geocoder` | each hour | no |
| hours since local sunset | time-varying | hour | same | each hour | no |
| wind speed | 10 m mean at the nearest station | m/s, time-varying | `kma_asos_aws` | each hour | no |
| wind gust | maximum in the hour | m/s, time-varying | `kma_asos_aws` | each hour | no |
| relative humidity | at the nearest station | per cent, time-varying | `kma_asos_aws` | each hour | no |
| days since 1 mm rain | at the nearest station, at report | day | `kma_asos_aws` | report | no |
| access distance | distance from the resolved location to the nearest mapped road | m | `kfs_forest_roads`, `base_map_linear_features` | report | no |
| slope, elevation | at the resolved location | degree, m | `dem_korea` | report | no |
| forest type | pine, broadleaf or mixed at the resolved location | factor | `kfs_forest_type_map` | report | no |
| concurrent fire load | fires reported in the same province in the preceding 24 h | count | `kfs_fire_stats_csv` | report | **see 10.5** |
| geocode precision class | the rung reached by section 9.3's rule | factor | derived | report | no |
| administrative unit | 발생장소_관서, as a random effect | factor | `kfs_fire_stats_csv` | report | **see 10.5** |

### 10.3 Every time-varying covariate is behind WJ-001, and so is the clock

The table has fourteen rows. **Three of them are computable today**: report hour,
weekday and day of year, all from the verified statistics file. Concurrent fire
load is computable today too, subject to 10.5. Everything else needs either
coordinates, which need `vworld_geocoder`, or weather, which needs
`kma_asos_aws`, or a raster, and all three are at status `pending` behind
WJ-001 or a portal gate.

**This means the containment hazard cannot be fitted with any time-varying
covariate at all today, and the night arm cannot be constructed at all today**,
because L-PHASE needs coordinates. That is a harder statement than "the data are
thin" and it belongs in the sign-off rather than in a limitations paragraph.

**The sunrise and sunset columns of the state-history file are never used.** The
registry records, and A1 confirmed independently, that they are a single national
value per calendar date. This direction is the one that would be most tempted by
them, because it is the one with a solar covariate, and so the prohibition is
repeated here: local solar times come from `research/shared/geo/solar.py` and
from nowhere else.

### 10.4 Cause is removed from the primary model, and the record says why

The brief names cause as a covariate. The record's own cause fields, measured in
`design_numbers.json`:

- 발생원인_세부원인 has no nulls, and **1,479 of 2,020 rows, 73.22 per cent,
  carry the value 기타(직접입력)**, which is the free-text escape hatch. The
  remaining coded values run from 작업장실화 at 111 rows down to 어린이불장난 at
  one.
- 발생원인_구분 is a single Korean character in four values and is **null on 294
  rows**, while the detail column is never null. So the coarse column is a
  derived code that is sometimes not derived.
- The free-text field is populated on all 2,020 rows, carries 454 distinct
  values, and **702 of them, 34.75 per cent of the record, contain 조사중 (under
  investigation), 추정 (presumed) or 미상 (unknown)**. Values such as
  조사중(담뱃불실화추정) are in the file verbatim.

**A field that records its own investigation status is an outcome of an enquiry.**
Whether a fire was arson is not knowable three hours after the report; that is
what 조사중 means. Using cause at H3 would be leakage item D1 in the form the
item does not enumerate, because the value is not computed over the fire's
duration, it is assigned after it.

**Pre-registered consequence.** Cause is excluded from the primary containment
hazard, from the primary size model and from the score. It enters exactly one
named secondary analysis, labelled as such and unpromotable, whose stated purpose
is to measure how much a post-hoc field would have added if it had been
available, and whose result may not be quoted as a predictor. Section 18
registers this as proposed leakage item D12.

### 10.5 The two `yes` entries and their paragraphs

**Concurrent fire load.** This is a count over other fires in the record, and
the other fires carry outcomes. Computed over the whole record it would be
target leakage of the administrative-encoding kind that leakage item D7 names.
**The rule: it is computed from report timestamps and provinces only, never from
areas or durations, and it is recomputed inside each training fold with the test
year's fires excluded from the counting window.** A fire near the start of a test
year therefore sees a truncated window, and the count of such fires is reported.
The load variable is also the falsification handle of section 3.3, which is a
second reason its construction cannot be allowed to touch the outcome.

**Administrative unit.** 발생장소_관서 is an obvious target-encoding trap: a
station mean escape rate over the whole record contains the target fire.
**It enters as a random intercept fitted inside the training fold and never as a
target-encoded numeric.** Stations appearing only in the test year draw from the
hyperprior, and the count of such fires is reported per fold, because that count
is the honest measure of how much the random effect is doing.

### 10.6 The covariate firewall

No covariate in the primary model is derived from 피해면적_합계, from any
duration, from any containment timestamp, or from any quantity computed over a
fire's own duration. The result artifact carries the covariate list with its
`knowable_at` column so that the firewall is checkable after the fact rather
than asserted.

---

## 11. The model form (P5)

### 11.1 Software, seeds and convergence, fixed in advance

PyMC with NUTS, on CPU, version recorded in the result artifact at fit time.
Seeds fixed at 20260916 for every chain set. Four chains, 1,000 tuning and 1,000
sampling iterations, `target_accept = 0.90`.

**Convergence criteria, fixed now:** R-hat at most 1.01 on every parameter, bulk
and tail effective sample size at least 400 on every parameter, zero divergent
transitions.

**What happens when they are not met, fixed now, because deciding it afterwards
is where the degrees of freedom live.** One escalation, in this order, each step
taken at most once and each recorded in the fit log of section 17.2:

1. `target_accept` to 0.95.
2. A non-centred parameterisation of the random effects.
3. Stop. The fit is reported as non-converged, no number from it is staged, and
   the non-convergence is itself the reported outcome of that arm.

There is no fourth step and in particular there is no step that changes the
model form, because changing the model form after seeing a convergence warning
that depended on the outcome is leakage item A8.

### 11.2 The containment hazard

Discrete-time hazard on U1 with a complementary log-log link, which makes it the
grouped-time form of a proportional hazards model and lets the hourly bins be
read as a continuous-time hazard:

    cloglog( P(contained in hour t | uncontained at t-1, x) )
        = alpha_{b(t)} + x_fire(t) · beta + u_{day,province}

`b(t)` maps the fire-hour to one of eight pre-registered bins: 1, 2, 3, 4 to 6,
7 to 12, 13 to 24, 25 to 48, 49 and above. The bins are fixed here and are not
chosen from the data. `u` is a day-by-province random intercept.

**No fire-level frailty is included.** Each fire contributes one sequence, so a
fire-level frailty is identified only through the parametric form and would
absorb the covariate effects the direction exists to estimate. Stating that is
the point of item P5's identifiability requirement, and it is the first of four
below.

### 11.3 Priors, each with one line

| parameter | prior | why |
|---|---|---|
| `alpha_b`, eight bin intercepts | Normal(-2, 1.5) | on the cloglog scale this spans roughly 0.001 to 0.5 hourly containment probability, which brackets anything plausible without preferring a shape |
| `beta`, on standardised covariates | Normal(0, 1) | allows about a sevenfold hazard ratio at two standard deviations and shrinks the rest; deliberately not flat, because a flat prior on a rare-outcome logistic-type model produces separation |
| `sd(u)` | HalfNormal(1) | a day-province effect larger than a factor of about seven is implausible and this says so weakly |
| `sigma` scale coefficients, tail model | Normal(0, 1) on the log scale | same reasoning as `beta` |
| `xi`, tail shape | Normal(0.2, 0.3), truncated to (-0.5, 1.5) | weakly centred on a moderately heavy tail; the sensitivity run with a flat prior on `xi` is mandatory and is declared in section 17.1, per leakage item A12 |

**Item A12 and the foreign-prior question.** No prior above takes its centre or
its scale from a non-Korean fitted coefficient. The `xi` prior's centre is the
one place where a reader might suspect it, so it carries a mandatory flat-prior
sensitivity run and both are reported.

### 11.4 Identifiability: four things this design cannot pin down

P5's acceptance test asks for at least one. There are four and the first two are
fatal to specific claims rather than to the model.

1. **The baseline hazard at fire-hour 1 is not separable from the mean report
   offset.** Section 5.2 is the algebra. The design cannot distinguish "Korean
   fires are hard to contain in their first hour" from "Korean fires were
   already an hour old when the clock started", and no covariate in the record
   breaks the tie. Consequence: the first bin's intercept is never interpreted.
2. **The night coefficient is not separable from the night report offset**
   without M-R of section 5.4. Consequence: the grid of 5.4, and F4.
3. **Suppression effort is not in the model at all.** There is no resource,
   crew, engine or aircraft record in either committed file. Every coefficient is
   therefore an association under the operative suppression regime, which is the
   suppression analogue of what rule RC-011 fixed for the roads direction, and
   section 22 fixes the permitted vocabulary accordingly.
4. **`xi` and the covariate effects on `sigma` trade off at low exceedance
   counts.** A heavier shape and a smaller scale slope produce nearly the same
   likelihood on a few dozen exceedances. Gates G4 and G5 exist for this and the
   posterior correlation between `xi` and the scale coefficients is a reported
   key path.

### 11.5 The size model

Two pieces, fitted jointly on U2:

- **Bulk.** A log-normal for recorded sizes below the threshold `u`, with a
  linear predictor on the same covariates as the hazard.
- **Tail.** Exceedances above `u` modelled as generalised Pareto, scale
  `sigma(x) = exp(x · gamma)`, shape `xi` constant unless gate G5 opens.

The two pieces are tied at `u` by the exceedance probability, which is modelled
by the same logistic form used for L-SIZE, so that the size model and the score
are consistent by construction rather than by inspection.

### 11.6 The threshold, and the degree of freedom leakage item D11 names

**`u` is fixed at 10 ha and does not move.** The declared sensitivity grid is
`{5, 10, 30, 50, 100}` hectares, **every value of which is reported**, and the
primary is the fixed value and not the best value. This is the strongest
available answer to D11: a threshold selected by a diagnostic is a threshold
selected by the analyst, and a threshold fixed in a pre-registration is not.

Justification for 10 ha: it is the operational floor the brief names for the
classification deliverable, so using the same floor keeps the size model and the
score on one scale. 100 ha appears in the grid and as a secondary because it is
the floor at which Korean practice recognises a large fire, and section 2.2
records that A5 knew before choosing that 2024 holds no fire above it.

---

## 12. The night arm

### 12.1 What is compared, after the correction of section 1.6

**Not growth.** The record carries a final area entered after containment and no
area at any intermediate hour, which is leakage item D2, so there is no observed
growth to compare by solar phase. Any night-versus-day growth number computed
from this record would be a reconstruction, and its assumptions would be doing
the work.

**The registered comparison is the containment hazard contrast by L-PHASE**: the
coefficient on the night indicator in the section 11.2 hazard, with the weather
covariates entered, which is the "matched weather" the brief asks for
implemented as conditioning rather than as a matched design. A matched design is
declared as a secondary in section 17.1, with matching on wind speed, humidity
and day of year inside training folds only.

### 12.2 The calm-night stratum, and what it can and cannot be

The brief asks for calm nights as a negative control. The logic is sound and the
name is not quite right, so the design states what it is.

If the night contrast is produced by the diurnal meteorological cycle, then in
the stratum of hours with low wind speed the contrast should attenuate toward
zero. If it is produced by the constraint on rotary-wing operations after dark,
the contrast should persist in that stratum. **This is an effect-modification
test that discriminates between two mechanisms, not a negative control in the
sense of an exposure with no plausible path to the outcome.**

Its own weaknesses, declared now:

- Calm is not randomly assigned. Calm nights in Korean mountain valleys carry
  stable stratification and drainage flows, which have their own fire-behaviour
  and their own access consequences.
- Calm at the nearest ASOS station is not calm at the fire, and the measurement
  error grows with distance to the station, which is correlated with remoteness,
  which is correlated with the report offset of section 5.
- The stratum is defined on a covariate measured with error, so the stratum
  boundary is itself noisy and the contrast between strata is attenuated.

**Pre-registered stratum definition**: hourly mean wind speed at the nearest
station below 2 m/s, fixed here, with a declared sensitivity at 1.5 and 3 m/s,
all three reported.

### 12.3 The E-value, and the honest statement that goes with it

Rule RC-007 requires an E-value before any causal wording, and the brief asks
for one to address two named biases. **An E-value addresses neither of them, and
this document says so rather than letting the number stand in for an answer.**

An E-value bounds how strong an **unmeasured confounder** would have to be, on
the risk-ratio scale, to explain away an observed association. The two biases the
brief names are not confounding:

- **Dispatch responding to danger is reverse causality**, or more precisely
  treatment assignment responding to the latent outcome. The E-value's derivation
  assumes the exposure is not assigned on the basis of the outcome, which is
  exactly what this bias violates.
- **Report time not being ignition time is measurement error in the timing of the
  exposure.** An E-value says nothing about a mismeasured exposure and, for a
  non-differential error, the association it is computed from is already
  attenuated.

**What is reported.** The E-value is computed and reported because RC-007
requires it, on the risk-ratio scale, with the hazard-ratio-to-risk-ratio
approximation named explicitly in the artifact so the transformation is
checkable. It is reported with a fixed sentence stating that it bounds
unmeasured confounding only and bounds neither of the two named biases. **The two
named biases get their own separate treatments**: section 5.4's grid for the
timing error, and section 3.3's concurrent-load test for the dispatch response.

The method reference for the E-value is **not in
`research/lit/bibliography.bib`**. `OPEN_QUESTIONS.md` Q5 asks A7 to verify it.
Until it is verified, no output of this direction cites it, and the quantity is
described by its definition rather than by an attribution.

### 12.4 What the night arm may conclude

Nothing causal. The permitted vocabulary is in section 22.2. The arm's output is
a contrast, its grid from section 5.4, its E-value with the sentence above, and
the calm stratum comparison.

### 12.5 The condition on the arm's output

Every night result is reported beside **the fire-hour exposure of the night
stratum in that fold**, which section 5.1 shows cannot be known before the fit.
A night contrast reported without its exposure is a forbidden phrasing and is
listed in section 23.

---

## 13. Held-out sets, named in advance (P6)

### 13.1 The call

```python
from research.eval.splits import forward_chaining_by_year, primary_split_spec
spec = primary_split_spec("suppression")
splits = forward_chaining_by_year(report_years, **spec["kwargs"])
```

`report_years` is the report year of each U2 row, taken from 발생일시_년 and from
nowhere else, so that the year a fire belongs to is knowable at report. The
kwargs are read from `PRIMARY_SPLITS` rather than retyped, which is the
construction A6 approved for the landslides direction.

### 13.2 The fingerprint does not exist, and cannot

`splits_fingerprint` needs splits, and the call raises on the committed record,
so there is no fingerprint to pin and A5 does not invent one. The `prereg:`
block records this rather than leaving the field blank or filling it with a
placeholder that would later look like a mismatch.

**What is pinnable today** is the refusal, and section 4.2 quotes it verbatim.
A6 can re-run both the refusal and the fold arithmetic of section 4.3 from
synthetic year lists in under a minute, and neither touches an outcome.

### 13.3 The year boundary, and a defect in the registered arguments

The docstring of `forward_chaining_by_year` names `gap_years` and names this
direction as the one that needs it, because a fire reported on 31 December is
contained in the next year. `PRIMARY_SPLITS["suppression"]["kwargs"]`
nonetheless sets `gap_years: 0`.

**This direction does not change the registered value**, and instead registers a
row-level boundary rule that closes the same hole at lower cost than losing a
whole training year:

1. A fire's fold membership is decided by its **report** year, always.
2. A training fire whose containment extends into the test year contributes to
   training **only the fire-hours falling inside its own report year**. The
   remaining fire-hours are dropped from training and are not moved to the test
   set.
3. Such a fire is **excluded from the test set entirely** regardless of its
   report year, because its outcome is partly determined inside the test window.
4. The count of fires affected is reported per fold.
5. `assert_time_ordered(split, report_years, gap_years=0)` is run on every fold
   and its result is recorded.

`OPEN_QUESTIONS.md` Q3 asks A6 whether `gap_years: 0` is intended or is an
oversight in A6's own registry, with A5's recommendation.

### 13.4 The statement P6 asks for

**No held-out outcome has been looked at by A5**, with the exception recorded in
section 2.1: A5 has been told the year-by-year exceedance counts computed by A4,
which span every year that would ever be a held-out year on the committed
record. On a lengthened record those counts cover four of many years. On the
committed record they cover all of them, which is one more reason the committed
record cannot support an evaluation from this author.

---

## 14. The primary metric (P7)

### 14.1 One metric, one number

**The held-out mean log predictive density per fire of the 10 ha exceedance
indicator at horizon H3**, averaged over the forward-chaining folds with each
fold weighted by its number of day-province clusters.

Three reasons it is this and not a discrimination summary:

1. It is a proper scoring rule, so it cannot be improved by miscalibration.
2. It is defined in a year with no positives. A precision-recall summary is not,
   and section 2.2 records that A5 knew 2024 is such a year at the 100 ha floor
   before choosing.
3. It is on the same scale as the baseline's score, so the margin of section 15
   is a difference of two numbers in one unit and needs no transformation.

### 14.2 The evaluation frame quoted beside it, per RC-008

Every quotation of this number carries, in the same sentence: **the held-out
report years, the number of folds, the number of day-province clusters in the
held-out years, and the fact that the fires were evaluated at horizon H3.**
A quotation without all four is a forbidden phrasing and is listed in section
23.

### 14.3 The uncertainty and the resampling unit

A cluster bootstrap over **day-province clusters** inside the held-out years,
2,000 resamples, 90 per cent interval. Never a bootstrap over fires, and never
over fire-hours. Leakage item A11 is the reason and section 8.4 is the
arithmetic.

### 14.4 Secondary metrics, labelled secondary and unpromotable

None of these may become the primary after the fact, under any outcome:

- tail-weighted Brier score at the 10 ha floor, weights declared in section 17.1;
- the precision-recall summary at 10 ha, **reported as undefined in any held-out
  year with no positives, never imputed and never dropped from the mean**;
- the same at 100 ha, under the same rule;
- the season-by-season ledger, per fold and pooled;
- the containment hazard's calibration by fire-hour bin;
- the integer score's own log predictive density, which is what F5 is keyed on;
- the tail model's held-out log predictive density on exceedances, if gate G4
  opened.

---

## 15. The baseline it must beat (P8)

**B0, the training-window exceedance base rate.** The predicted probability for
every fire in the held-out year is the share of training-window complexes whose
recorded size reached 10 ha. One line of code, its own code path, no covariates.

B0 is the honest null of this direction: it is the model that says the first
hours tell you nothing and your best guess is last decade's rate.

**B1, a two-covariate logistic** on report-time wind speed and relative humidity
at the nearest station, fitted inside the training window. Labelled a second
baseline, reported always, and not the one the margin is keyed on. B1 exists
because beating B0 is a low bar for anything with weather in it, and a reader is
entitled to know whether the rest of the model added anything to the weather.

**The margin, fixed now.** The primary model must exceed B0 by **at least 0.02
nats per fire** in held-out mean log predictive density, and the 90 per cent
cluster bootstrap interval on the **difference** must exclude zero. Both
conditions, not either.

**The arithmetic behind 0.02, shown because a margin without arithmetic is a
number somebody liked.** At an exceedance rate near four per cent the entropy of
the outcome is about 0.163 nats per fire, so 0.02 nats is about twelve per cent
of the information available to be explained. A margin of 0.05 would demand
about a third of it and would make the direction close to impossible; a margin
of 0.005 would be met by noise on a held-out year of a few hundred fires. The
figure uses the exceedance share that section 2.1 records A5 as having been
told, and that dependency is declared rather than hidden.

**Against B1 there is no pre-registered margin**, deliberately. B1 is reported as
a comparison and not as a hurdle, because inventing a second hurdle after the
first invites picking whichever is passed.

---

## 16. What would count as the hypothesis failing (P9)

Each reading below is fixed now and is written so that it cannot be re-read as a
success.

**F1. The margin against B0 is not met, or its interval contains zero.**
*Reading:* the information available in the Korean administrative record three
hours after a fire is reported does not separate the fires that reach 10 ha from
those that do not, better than the preceding years' base rate, by the margin
fixed in advance. It is reported as that, not as a call for more covariates, and
the score is not recommended. It is **not** evidence that no early information
could separate them; it is evidence about this record.

**F2. Gate G1 never opens.** *Reading:* the Korean fire record available to this
program is too short for a forward-chained evaluation, so this direction reports
no held-out number and makes no claim about discrimination. Its deliverable is
the accounting of sections 4 and 5 and the data case in `DATA_REQUIREMENTS.md`.
A descriptive fit on four years is not substituted, and the phrase "preliminary
result" does not appear.

**F3. Gate G4 fails, or G2 or G3 fails.** *Reading:* the Korean large-fire sample
available cannot recover a tail shape at the precision a generalised Pareto fit
would imply, so no tail parameter is reported and no size distribution is
reported. The exceedance counts by year and season are reported instead, as
counts.

**F4. The night contrast changes sign anywhere inside the section 5.4 grid.**
*Reading:* the night contrast is not identified separately from the
night-specific report offset with this record, and the arm is withdrawn. Not
"suggestive", not "directionally consistent", withdrawn.

**F5. The integer score's held-out log score is worse than the hazard model's by
more than 0.01 nats per fire.** *Reading:* the distillation to integer weights is
lossy at a level that matters, the score is reported as such, and it is not
recommended for use.

**A note on how these read together.** F1 and F2 are not the same outcome. F2 is
the expected outcome today and it is a statement about the record. F1 is a
statement about the hypothesis and it requires the record first.

---

## 17. Stopping rule and multiplicity (P10)

### 17.1 The enumeration of fits, fixed now

**Primary fits: four.** The containment hazard, the exceedance logistic, the
size model's bulk and tail piece, and the FasterRisk distillation. Each is fitted
once per fold.

**Baselines: two.** B0 and B1.

**Declared families, every member of which is reported:**

| family | members | reported |
|---|---|---|
| threshold grid `u` | 5 values | all |
| report-offset grid | 16 cells | all |
| horizon sensitivity | H1, H3, H6 | all, H3 primary |
| calm-wind stratum | 3 cutoffs | all |
| `xi` prior sensitivity | the registered prior and a flat prior | both |
| matched night design | 1 | reported as secondary |
| cause as a covariate | 1 | reported as secondary, never as a predictor |
| random effect at prediction | drawn from the hyperprior, and set to zero | both, with the hyperprior draw primary |

**The primary held-out metric is computed once per model.** A second computation
is recorded in the fit log as a finding, per leakage item A2.

### 17.2 The fit log

Every fit, including failures, non-convergences and abandoned attempts, is
appended to `research/suppression/results/fit_log.jsonl` with its timestamp,
seed, model identifier, fold, convergence diagnostics and whether the held-out
metric was computed. **The count of fits run before the reported one is
reported**, which leakage item A7 names as the single most useful diagnostic
nobody volunteers.

### 17.3 Multiplicity

No correction is applied, and the reason is that the families above are a fixed
table reported in full rather than a search whose winner is reported. A fixed
table is not a multiplicity problem; a table from which one cell is quoted is,
and section 22 forbids quoting a cell of the offset grid alone.

The one place a correction would be warranted is the season ledger, where a
per-season contrast could be mined. **The season ledger is descriptive and
carries no hypothesis test**, which is declared here so that it cannot acquire
one later.

---

## 18. The leakage self-audit (P11)

Written and committed before A6's pass, per roads condition C10. Verdicts are
A5's own; A6 runs the list independently and the differences are the finding.

### 18.1 Part A, cross-cutting

| id | severity | verdict | one line |
|---|---|---|---|
| A1 preprocessing inside the fold | CRITICAL | `mitigated` | every standardisation, the base rate, the concurrent-load window, the random-effect hyperparameters and `n_eff`'s `rho` are constructed inside the fold loop; the threshold `u` is a constant declared in 11.6 |
| A2 hyper-parameters and priors on held-out | CRITICAL | `mitigated` | every prior, the threshold, the bin edges, the horizon, the score's sparsity and coefficient range are fixed in this document; one held-out metric computation per model, a second is a logged finding |
| A3 feature selection before the split | CRITICAL | `mitigated` | the covariate table of 10.2 is fixed here; FasterRisk's own selection runs inside the training fold |
| A4 feature support crossing the boundary | CRITICAL | `mitigated` | the only feature with a support wider than one fire is concurrent load, and 10.5 recomputes it per fold with the test year excluded from the window |
| A5 duplicates and near-duplicates | MAJOR | `mitigated` | the complex rule of 9.4 plus the supplementary adjacency rule; exact and merged counts reported per fold |
| A6 the analyst's memory | MAJOR | `present` | every agent knows what happened at Uljin 2022 and Uiseong 2025, and section 2 records that A5 was additionally told the exceedance counts for every year of the committed record. There is no fix; section 6 states the limitation |
| A7 undocumented fits | MAJOR | `mitigated` | the fit log of 17.2 |
| A8 outcome-driven cleaning or stopping | MAJOR | `mitigated` | 9.2 fixes the defect rule in advance and drops no row from U2; gate G3 stops a fit rather than removing rows, and 4.5 argues the distinction explicitly rather than assuming A6 will accept it |
| A9 geocoder drift | MINOR | `unresolved` | the geocoder does not exist yet; precision class is a covariate per 9.3 and never a filter; the geocoder version and date are recorded when it lands |
| A10 outcome-dependent missingness | MAJOR | `mitigated` | the 12 and 41 defective rows are flagged, counted, kept in U2 and excluded only from the hazard model's rows, with their share of exceedances reported separately per 9.2 |
| A11 resampling unit | MAJOR | `mitigated` | day-province clusters, 14.3, never fires and never fire-hours |
| A12 foreign quantity through a prior | MINOR | `mitigated` | no prior centre or scale comes from a foreign fitted coefficient; the `xi` prior carries a mandatory flat-prior sensitivity run |

### 18.2 Part D, suppression

| id | severity | verdict | one line |
|---|---|---|---|
| D1 covariates over the whole duration | CRITICAL | `mitigated` | 10.2's `knowable_at` column, the firewall of 10.6, and horizon H3 fixed in 10.1 |
| D2 reported size at hour h does not exist | CRITICAL | `present, and the arm is changed` | the night growth comparison is withdrawn and replaced by a containment-hazard contrast, 1.6 item 2 and section 12.1; no early-size feature exists in this design |
| D3 report time is not ignition time | MAJOR | `present` | section 5 in full. The bias runs toward the hypothesis on both headline covariates. Mitigations are the grid of 5.4, the measurement M-R, and the withdrawal rule F4 |
| D4 the tail is fitted to what suppression left | CRITICAL | `present, and the quantity is withdrawn` | section 3. No suppression-free size distribution is produced under any outcome; the tail is described as the tail of the recorded sizes under the operative regime |
| D5 forward chaining only | CRITICAL | `mitigated, and the gate is shut` | the registered call, unchanged, which refuses today; gate G1 |
| D6 the score needs its own held-out year | CRITICAL | `mitigated` | the distillation runs entirely inside the training window of each fold, so the held-out year is unseen by both the hazard model and the distillation; section 19.2 |
| D7 administrative target encoding | MAJOR | `mitigated` | 10.5: a random intercept fitted inside the fold, never a target-encoded mean; count of test-only stations reported |
| D8 duplicate fire records | MAJOR | `mitigated` | 9.4, with the shipped table's one complex plus the supplementary adjacency rule and its reported merge count |
| D9 outcome-dependent cleaning | MAJOR | `mitigated` | 9.2, flag, count, report, pre-registered rule |
| D10 night carries reverse causality | MAJOR | `present` | section 12, the E-value with the statement that it bounds neither named bias, and the vocabulary of 22.2 |
| D11 the tail threshold is a degree of freedom | MAJOR | `mitigated` | `u` fixed at 10 ha in 11.6, grid of five reported in full, primary is the fixed value not the best value |

### 18.3 Two items A5 proposes adding to the checklist

A5 does not own `research/eval/LEAKAGE.md` and has not edited it. Both are
requested in `OPEN_QUESTIONS.md` Q6.

**D12, proposed. Administratively determined covariates. MAJOR.** A field
recorded in an administrative dataset may be determined after the event it
describes, without being computed over the event's duration, so item D1's test
does not catch it. The cause field of `kfs_fire_stats_csv` is the instance:
34.75 per cent of rows carry 조사중, 추정 or 미상 in the free-text field, and
some rows say 조사중 verbatim. *Detection:* for every covariate, ask not only
whether its value could have been computed at the horizon, but whether the
administrative process that produced it had concluded by then.

**D13, proposed. Geocoding error correlated with the covariate being measured.
CRITICAL.** Item C10 states this for landslides. It is not stated for
suppression and it applies with the same force and to a more load-bearing
covariate: zero of 2,019 addressed fire records carry a lot number, the finest
reachable rung is a 리 polygon, and the distance from a 리 centroid to the
nearest road is worst in the largest and most mountainous 리, which is exactly
where access distance is largest. The covariate's measurement error is a function
of the covariate's own value.

---

## 19. Data provenance (P12)

### 19.1 The table

<!-- forbidden-ok: 154, 264, 452, 2731, 0.834, 0.874, 0.867 -->

| registry id | status | sha256 on disk | gate |
|---|---|---|---|
| `kfs_fire_stats_csv` | `verified` | `ae3e8426702168cb288761735dabe5b8a45f429ba7bc13e9f0318e838a92c153` | none | <!-- forbidden-ok: 154, 264, 452, 2731, 0.834, 0.874, 0.867 -->
| `kfs_fire_state_history_csv` | `verified` | `2e94ab963feeb9ad998761537a397e4d5912ac7f90e147487ef43aafc1512c00` | none | <!-- forbidden-ok: 154, 264, 452, 2731, 0.834, 0.874, 0.867 -->
| `kfs_fire_stats_api` | `pending` | not on disk | WJ-001, then WJ-006 |
| `kma_asos_aws` | `pending` | not on disk | WJ-001 |
| `vworld_geocoder` | `pending` | not on disk | WJ-001 |
| `firms_active_fire_korea` | `pending` | not on disk | WJ-001 |
| `dem_korea` | `pending` | not on disk | WJ-011, fallback behind WJ-001 |
| `kfs_forest_roads` | `pending` | not on disk | WJ-017 |
| `base_map_linear_features` | `pending` | not on disk | portal |
| `kfs_forest_type_map` | `pending` | not on disk | WJ-018, WJ-012 |

**Two of ten are `verified`, and neither of the two carries a covariate that the
containment hazard needs beyond the clock.** Per section 3 of `SIGNOFF.md` this
caps the attainable state at `signed with conditions`, and A5 states the cap
rather than leaving A6 to apply it.

### 19.2 The score's own provenance

FasterRisk, `liu2022fasterrisk`, verified by A7 on 2026-09-16 by Crossref DOI
lookup. Hyperparameters fixed now and not tuned on any held-out year: **at most
8 features, integer coefficients in the range -5 to 5, the model selected from
the returned pool by inner-fold log loss on a declared inner split of the
training window only.** The inner split is a forward chain inside the training
window with the same registered kwargs, so that the distillation never sees the
fold's test year, which is what leakage item D6 requires.

---

## 20. Compute and feasibility (P13)

One Apple M4 Pro laptop. No HPC, no GPU training.

| fit | expected wall clock |
|---|---|
| containment hazard, one fold | minutes to about an hour, depending on the fire-hour row count |
| exceedance logistic, one fold | under a minute |
| size model bulk and tail, one fold | a few minutes |
| FasterRisk distillation, one fold | under a minute |
| full forward chain at 25 folds, all four models | the binding cost, on the order of a day |
| the 16-cell offset grid at 25 folds | the second binding cost, and the first thing cut |

**The cut order, decided now.** Cut in this order and stop as soon as it fits:
the offset grid from 16 cells to the 4 corner cells; the horizon sensitivity to
H3 alone; the calm-wind cutoffs to the primary alone; the threshold grid to
three values.

**Never cut:** the split, the primary metric, the baseline B0, the cluster
bootstrap, the fit log, gate G4. If those do not fit, the direction reports fewer
folds rather than weaker gates.

---

## 21. Scope declaration (P14)

**Korea only.** Every dataset in section 19.1 is Korean. No foreign fire record
is used for fitting, for validation, for calibration or as a source of a fixed
coefficient.

Foreign sources appearing anywhere in this design, each with the sentence rule
RC-010 and item P14 require:

- **Liu, Zhong, Li, Seltzer and Rudin 2022**, `liu2022fasterrisk`, verified.
  *Supplies a method for fitting sparse integer risk scores. Its data is not used
  for fitting.*
- **Ustun and Rudin 2017**, `ustun2017riskslim`, verified. *Supplies the prior
  method in the same family, cited as prior art. Its data is not used for
  fitting.*
- **The generalised Pareto peaks-over-threshold framework.** *Supplies an
  equation. No foreign fitted shape or scale enters as a prior centre; section
  11.3's `xi` prior is weakly informative and carries a flat-prior sensitivity
  run.* **The standard reference is not in
  `research/lit/bibliography.bib`**, and `OPEN_QUESTIONS.md` Q5 asks A7 for it.
  Until it is verified this document cites the method by its definition.
- **The E-value.** *Supplies a sensitivity quantity for unmeasured confounding.*
  **Not in the bibliography either**, same question Q5, same rule.
- **Richards and Huser, arXiv 2208.07581.** *Would supply a method. Not verified
  in the bibliography, not designed against, section 7.*

No Korean study is used as a fitting input either;
`research/lit/suppression_prior_art.md` records that no dedicated sweep for this
direction has yet been run, and `OPEN_QUESTIONS.md` Q5 asks for one.

---

## 22. What the result will not say (P15)

### 22.1 The claims this direction will not make under any outcome

1. **No size distribution with the suppression effect removed**, whatever it is
   called, as a figure, table, parameter or sentence. Rule RC-006 governs the
   sentence and section 3.4 governs the quantity. <!-- research-claim-ok: RC-006 -->
2. **No statement that suppression censoring has been corrected**, because it has
   not and cannot be, and section 3.1 says why in a stronger form than
   "insufficient data". <!-- research-claim-ok: RC-006 -->
3. **No causal statement about night.** Not "night causes faster growth", not
   "growth is driven by the diurnal shift", not any Korean equivalent. Rule
   RC-007 governs the sentence; sections 12.3 and 12.4 govern the reading. <!-- research-claim-ok: RC-007 -->
4. **No score quoted without its held-out report years**, its fold count, its
   cluster count and its horizon. Rule RC-008 governs the sentence and section
   14.2 fixes the four things that travel with it. <!-- research-claim-ok: RC-008 -->
5. **No claim that the score is ready for operational dispatch use.** It is
   fitted on an administrative record, at address-level precision, with no
   resource data, and validated on held-out years from the same record.
6. **No claim that suppression effort was measured or controlled for.** It is not
   in either file. Every coefficient is an association under the suppression
   regime that operated, and 22.2 fixes the vocabulary.
7. **No attribution of a containment-hazard coefficient to a physical
   mechanism.** A lower hazard at night is not a statement about fire behaviour
   at night.
8. **No cross-year comparison of national burned area presented as evidence about
   the model**, in either direction.
9. **No novelty claim.** Rule RC-009, and
   `research/lit/suppression_prior_art.md` states that the sweep has not been
   run.
10. **No transfer of the score or of any coefficient to a non-Korean record**,
    and no import of a foreign coefficient into a Korean fit.
11. **No statement that the report-time offset has been corrected.** At best it
    is bounded below on a size-selected subsample; section 5.5.
12. **No sentence describing a quantity from the `phi` family of section 3.4
    without printing its `phi` on the same line.**

### 22.2 The permitted vocabulary

| forbidden | permitted |
|---|---|
| the corrected size distribution | the recorded size distribution under the operative suppression regime | <!-- research-claim-ok: RC-006 -->
| night causes faster growth | the night-versus-day containment hazard contrast, with its E-value and its exposure | <!-- research-claim-ok: RC-007 -->
| the effect of access distance | the association between resolved access distance and the containment hazard, at the stated offset cell |
| the fire would have reached X ha | under assumption A-NI at `phi = p`, the exceedance curve is |
| escape probability | the modelled probability that the recorded final size reaches the stated floor |
| suppression reduced sizes by | no permitted form; the quantity is not estimated |

`OPEN_QUESTIONS.md` Q7 asks the orchestrator whether this direction should carry
its own vocabulary detector in the tree it owns, as the roads direction does,
with A5's recommendation.

---

## 23. The shape of the result artifact (P16)

### 23.1 The artifact

`research/suppression/results/suppression_v0.1.json`, a committed JSON file
whose keys are addressable by the registrar's `dig()` helper. The staging file
is `research/suppression/numbers_staged.json`, written in the registrar's own
`entry()` shape with every value null and every entry at state `not_produced`.

The design-side artifact `research/suppression/design/design_numbers.json`
already exists, is outcome-free, and is re-runnable today by
`research/suppression/design/clock_and_address.py`. Nothing in it is a result and
nothing in it is staged as one.

### 23.2 The key paths, named before the fit exists

| quantity | json path |
|---|---|
| primary metric | `held_out.primary_metric.value` |
| its 90 per cent interval | `held_out.primary_metric.ci_low`, `.ci_high` |
| baseline B0's metric | `held_out.baseline_b0.value` |
| the difference and its interval | `held_out.margin_vs_b0.value`, `.ci_low`, `.ci_high` |
| whether the margin was met | `held_out.margin_vs_b0.met` |
| baseline B1's metric | `held_out.baseline_b1.value` |
| per fold | `held_out.folds[].test_year`, `.value`, `.n_clusters`, `.n_eff` |
| held-out report years | `held_out.frame.test_years` |
| horizon | `held_out.frame.horizon_fire_hours` |
| row and cluster counts | `counts.n_fires`, `.n_complexes`, `.n_fire_hours`, `.n_day_province_clusters`, `.n_eff` |
| defect counts | `counts.negative_duration`, `.impossible_end_year`, `.unlabelable_L_CONT` |
| complex merges | `counts.kspread_merges`, `.supplementary_merges` |
| night contrast at the naive cell | `night.contrast.value`, `.ci_low`, `.ci_high` |
| night exposure in fire-hours | `night.exposure_fire_hours` |
| the offset grid | `night.offset_grid[].m`, `.d`, `.value`, `.sign` |
| whether any sign flipped | `night.offset_grid_sign_stable` |
| the E-value | `night.e_value.value`, `.scale`, `.transformation` |
| calm-wind strata | `night.calm_strata[].cutoff_ms`, `.value` |
| A-NI falsification test | `assumption_a_ni.concurrent_load.value`, `.ci_low`, `.ci_high`, `.rejects` |
| gate outcomes | `gates.g1.passed` through `gates.g6.passed`, each with `.evidence` |
| tail shape | `tail.xi.value`, `.ci_low`, `.ci_high`, `.covariate_dependent` |
| tail threshold grid | `tail.threshold_grid[].u_ha`, `.xi`, `.n_exceedances` |
| tail and scale correlation | `tail.xi_sigma_posterior_correlation` |
| the `phi` family | `counterfactual_family[].phi`, `.exceedance_curve` |
| the integer score | `score.features[].name`, `.points`, `score.held_out.value` |
| score loss against the hazard model | `score.distillation_loss_nats` |
| fits run before the reported one | `provenance.n_fits_before_reported` |
| software and seeds | `provenance.pymc_version`, `.seed`, `.packages` |

**Every quantity that could embarrass this direction has a key path**, including
the gate outcomes, the sign-stability flag, the distillation loss and the fit
count. That is deliberate: a result artifact that can only express success is
not a result artifact.

### 23.3 The registrar gap

`scripts/build_numbers.py`'s `entry()` reads a reproducibility record keyed on
`source_file`, so a new research artifact needs an entry there. That file is
outside `research/` and is therefore a human gate, already recorded by A6 as
NH-A6-04 in `research/eval/NUMBERS_PROTOCOL.md`. A5 has not touched it.

---

## 24. What must be true before fitting starts

In order. Nothing below is optional and nothing below is A5's to waive.

1. **A6 signs this pre-registration**, in a record under
   `research/eval/signoffs/`. Silence is not a signature.
2. **WJ-001 clears** and the probe of `research/data/checks/probe_kfs_api.py`
   runs. Until then the record's depth is unknown and gate G1 is shut.
3. **Gate G1 opens**: the registered split returns at least two folds. Section
   4.3 says how deep the record must be for that.
4. **`vworld_geocoder` reaches `verified`** or the direction fits with no spatial
   covariate, no access distance and **no night arm**, and says so.
5. **`kma_asos_aws` reaches `verified`** or the direction fits with no weather and
   the matched-weather comparison of section 12.1 does not exist.
6. **Gates G2, G3 and G4 pass** before any generalised Pareto fit.
7. **The blocking conditions of A6's record are closed**, whatever they turn out
   to be.

---

## 25. Statement for the signing agent

### 25.1 What has and has not happened

No model has been fitted. No burned area and no duration has been read by A5.
The outcome quantities A5 has been told by others are listed in section 2.1 and
the three places that knowledge shaped this document are listed in 2.2. The
information-barrier problem A6 raised as PF-1 was not avoidable from this side
and section 2.6 records the contamination rather than claiming the barrier held.

### 25.2 What A5 thinks the most likely outcome of this direction is

**F2.** The API key does not arrive, or it arrives and the API does not reach
back far enough, gate G1 stays shut, and this direction's deliverable is the
accounting rather than a model. A5 puts more weight on that than on all the
other outcomes combined.

Conditional on the record reaching 1991, A5's expectation is: the containment
hazard fits cleanly and is interesting; the margin against B0 is met, because
weather and season carry real signal about which Korean fires get large; the
night arm fails F4 at the offset grid; and gate G4 passes at a threshold of 10 ha
and fails at 100 ha, so the tail is reported at the lower floor only.

### 25.3 The single weakest point, in A5's own judgement

**Not the counterfactual.** Section 3 withdraws that quantity, and a withdrawn
quantity cannot be wrong.

**The weakest point is section 5, the report-time clock, and specifically that
the mitigation is a grid whose endpoints are guesses.** The bias runs toward the
hypothesis on both of the direction's headline covariates, its size is governed
by a parameter the Korean record does not contain, and the only measurement that
would bound it, M-R, depends on a satellite product behind the same key as
everything else and would bound it only on a size-selected subsample and only
from below. If A6 wants one thing strengthened before signing, it is that: either
M-R becomes a blocking condition on the night arm and on the access-distance
coefficient, or both are demoted to permanently secondary status in v0.1 and the
direction reports the score without interpreting its inputs.

A5's recommendation between those two is the second, because it does not depend
on a gate clearing.

### 25.4 Should this direction proceed at all on a four-year record

**As a fit, no, and nothing in this document permits one.** Gate G1 is shut, it
is shut by A6's committed code with A6's committed test on it, and the arithmetic
of section 4.3 says the record must roughly triple in depth before a single fold
exists.

**As a direction, yes**, for three reasons that mirror the ones A6 accepted for
landslides. The outcome-free work is real and is already done in part: the clock
measurement, the address ceiling, the cause-field finding and the fold arithmetic
are all committed and all re-runnable, and the cause-field finding alone removes
a covariate the brief assumed. The data case in `DATA_REQUIREMENTS.md` is what
turns WJ-001 from a blocker into a decision with a stated payoff, and section
4.3 gives John the one number he needs, which is how far back the record must
reach. And the gate structure means the direction can be handed the longer record
and run without renegotiating anything.

### 25.5 What this version does not fix

- P2's row count for U1 is a bound, not a number, and will stay one until the
  gates open, because computing it means reading the outcome.
- P3's second pass cannot run on any label, and L-PHASE cannot be labelled by
  anyone today.
- P6's fingerprint does not exist and cannot be pinned.
- The offset grid's endpoints are not Korean measurements.
- Three method references this design needs are not in the verified
  bibliography, and this document cites none of them as though they were.
