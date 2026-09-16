# Suppression direction, open questions

Owner: A5. Companion to
`research/suppression/PREREG_suppression_2026-09-16_v0.1.md`.

Every question carries A5's recommendation, so that nothing here reads as a
request for somebody else to decide what A5 should have decided. Where the
recommendation is already binding inside the pre-registration, the question is
whether to overturn it, not whether to make it.

Each row names who owns the decision. A5 owns nothing outside
`research/suppression/**` and `research/reports/A5/**`.

| id | question | owner | A5's recommendation |
|---|---|---|---|
| Q1 | should the API probe record the endpoint's field list, not only its depth | A1 | yes, and it is a second reason to run the probe |
| Q2 | should the K-SPREAD complex table carry the 2022 multi-county event | A2 | yes, and until it does A5 runs a declared supplementary rule |
| Q3 | is `gap_years: 0` in the registered suppression split intended | A6 | it should be 0, and the boundary is closed at the row level instead |
| Q4 | is the primary floor 10 ha or 100 ha | A6, at sign-off | 10 ha, and section 2.2 declares what A5 knew when choosing |
| Q5 | three method references this design needs are not in the bibliography | A7 | verify them, and run the H-SUPP sweep that has not been run |
| Q6 | should two new leakage items be added for this direction | A6 | yes, D12 and D13, both drafted in pre-registration 18.3 |
| Q7 | does this direction need its own vocabulary detector | orchestrator | yes, and A5 will write it in the tree it owns |
| Q8 | should the night arm and the access coefficient be demoted in v0.1 | A6 | yes, unless the offset measurement M-R becomes a blocking condition |
| Q9 | is the counterfactual withdrawal of section 3 too strong | A6 and John | no, and A5 would resist a weakening of it |
| Q10 | should this direction fit anything if the record never lengthens | John and A6 | no fit, and the accounting is the deliverable |

---

## Q1. Should the API probe record the endpoint's field list, not only its depth

**The question.** `research/data/checks/probe_kfs_api.py` prints an HTTP status
and a body preview per probe year, and its closing message tells the reader to
update the registry's `temporal_coverage` from what was actually returned. It
does not ask the reader to record **which fields** the endpoint returns.

**Why it matters to this direction specifically.** Pre-registration section 5 is
built around one missing field. The committed CSV carries a single time column,
발생일시, which the registry records as a reported start. If the Open API returns
a richer time schema, for example a separate 신고 timestamp and an estimated
발화 timestamp, then the sixteen-cell offset grid collapses into a covariate and
the direction's weakest point largely disappears. If it returns the same single
field, the grid stands. **Either answer is worth having and the probe is already
going to make the request.**

**Recommendation. Yes, and it costs one line of the reader's attention.** When
the probe runs, record the returned field names in the registry entry alongside
the temporal coverage. A5 does not own `research/data/` and has not edited the
probe script.

**If the answer is no**, the field list gets discovered at ingest time instead,
which is later but not fatal.

---

## Q2. Should the K-SPREAD complex table carry the 2022 multi-county event

**The question.** `research/shared/qc/complexes.py` exists so that all three
directions assign the same complex id to the same records, and its docstring
says so explicitly. Its membership table names one complex: the 2025 Yeongdeok,
Uiseong and Andong event, quoted from the K-SPREAD-2025 protocol. The largest
event of 2022 crossed county boundaries in the same way and is not in the table.

**Why it matters.** Pre-registration section 8.3 makes the complex a clustering
axis and section 13 puts whole complexes on one side of a fold. An event
reported as several administrative rows and not collapsed is counted as several
independent fires, which inflates the row count, overstates the effective sample
size, and puts pieces of one event on both sides of a fold boundary. That last
one is leakage item D8 directly.

**Recommendation. Yes, add it, and the reason is the module's own.** The module
exists to stop three directions re-deriving a grouping and disagreeing. A5
adding a private rule is exactly the outcome the module was written to prevent,
which is why the pre-registration's supplementary rule in section 9.4 is declared
as a stopgap and is keyed on geography and time only, never on area, and reports
its merge count.

**The check A5 registers either way.** If A2 adds the 2022 event, the
supplementary rule should make zero additional merges for it, and that agreement
is reported as a check rather than assumed.

**If the answer is no**, the supplementary rule stands, and the pre-registration
reports its merges so that a reader can see exactly which rows this direction
grouped and no other direction did.

---

## Q3. Is `gap_years: 0` in the registered suppression split intended

**The question.** The docstring of `forward_chaining_by_year` in
`research/eval/splits.py` says, of `gap_years`: "Use it whenever a feature looks
back or forward across a year boundary, **which in the suppression direction it
does**: a fire reported on 31 December is contained in the next year."
`PRIMARY_SPLITS["suppression"]["kwargs"]` then sets `gap_years: 0`.

**Why it matters.** The docstring names this direction as the one that needs the
embargo and the registry does not give it one. Either the registry is an
oversight, or the intent is that the boundary is handled at the row level and
the embargo is not the instrument for it.

**What it would cost to set it to 1.** An entire training year per fold. On a
record that may have eleven distinct years in total, that is expensive, and it
buys protection against a defect that affects only fires reported in the last
days of a year.

**Recommendation. Leave it at 0, and close the boundary at the row level.**
Pre-registration section 13.3 registers the rule: fold membership by report
year; a training fire whose containment extends into the test year contributes
only the fire-hours falling inside its own report year; such a fire is excluded
from the test set entirely; the count is reported per fold. That is narrower
than a whole-year embargo and it closes the same hole.

**What A5 is actually asking for** is not a change to the value. It is a line in
A6's record saying which of the two readings is intended, because
`research/eval/splits.py` currently reads both ways and A5 should not be the one
who decides that in someone else's file.

---

## Q4. Is the primary floor 10 ha or 100 ha

**The question.** The brief asks for precision-recall summaries at both 10 ha
and 100 ha. Item P7 permits one primary metric. The pre-registration makes the
primary the 10 ha exceedance and the 100 ha a labelled secondary.

**Why it is not a free choice.** 100 ha is the doctrinally meaningful floor and
is what a Korean planner would recognise as a large fire. It is also the floor
at which a held-out year in the committed record contains no positives, which
makes a precision-recall summary undefined and a log score extremely noisy.

**The honesty problem.** A5 knew, before choosing, that 2024 holds no fire above
100 ha, because the round-1 briefing said so. That is an outcome view steering a
metric choice and pre-registration section 2.2 declares it rather than letting
it pass as a methodological preference.

**Recommendation. 10 ha primary, 100 ha secondary, both reported always, and
the 100 ha summary reported as undefined in any year with no positives rather
than imputed or dropped from a mean.** Dropping an undefined fold from a mean is
the quiet version of selecting folds on the outcome.

**If A6 rules for 100 ha as primary**, the pre-registration needs a new failing
condition, because F1's margin arithmetic is computed at the 10 ha base rate and
would not transfer.

---

## Q5. Three method references this design needs are not in the bibliography

**The question.** `research/lit/bibliography.bib` carries `liu2022fasterrisk`
and `ustun2017riskslim`, both verified by A7 on 2026-09-16, and nothing else
this direction uses. Missing:

1. **The generalised Pareto peaks-over-threshold framework.** The tail model of
   pre-registration section 11.5 is built on it.
2. **The E-value.** Rule RC-007 requires one before any causal wording about
   night, and section 12.3 computes one.
3. **Richards and Huser, arXiv 2208.07581.** The brief names it, conditionally.

**Why it matters more than a tidiness issue.** Item P14 requires every foreign
source to be listed with the sentence that it supplies a method and that its
data is not used for fitting. A source that cannot be cited cannot carry that
sentence. A6 would be right to treat an uncitable method as an unregistered one.

**What this direction does in the meantime.** Cites none of them as verified.
Section 21 lists each by its role with an explicit note that it is not in the
bibliography, and section 12.3 describes the E-value by its definition rather
than by an attribution.

**Recommendation. Verify the first two and leave the third.** The first two are
load-bearing and are standard references that a DOI lookup settles in minutes.
The third is gated behind a confirmation that has not happened, so verifying it
now would be work done for a branch that may never open.

**And the larger request.** `research/lit/suppression_prior_art.md` states in its
own words that no dedicated sweep for H-SUPP has been run and that the absence
of findings there is not evidence the literature is thin. A5 needs that sweep
before section 22's novelty prohibition can relax, and specifically needs the
Korean-language sweep on 대형산불 전이, 초기진화 and 진화 실패. The unresolved
"Keeling et al. 2001" citation recorded in `research/lit/UNVERIFIED.md` should be
settled first, because until it is, nobody knows what is already verified for
this direction.

---

## Q6. Should two new leakage items be added for this direction

**The question.** Pre-registration section 18.3 drafts two items that
`research/eval/LEAKAGE.md` does not currently carry. A5 does not own that file
and has not edited it.

**D12, administratively determined covariates, MAJOR.** Item D1's test is
whether a covariate's value could have been written down at the prediction
horizon, and it is framed around quantities computed over a fire's duration. The
cause field fails a different test: it is not computed over the duration, it is
**assigned after an investigation concludes**. 34.75 per cent of the record's
rows carry 조사중, 추정 or 미상 in the free-text cause field, and some say 조사중
verbatim. A covariate that records its own investigation status is an outcome of
an enquiry.

**D13, geocoding error correlated with the covariate being measured, CRITICAL.**
Item C10 states this for the landslides direction. Nothing states it for
suppression, and it applies here to a more load-bearing covariate. Zero of 2,019
addressed fire records carry a lot number, so the finest reachable rung is a 리
polygon, and the distance from a 리 centroid to the nearest road is worst in the
largest and most mountainous 리, which is exactly where access distance is
largest and where the escape hypothesis expects its signal.

**Recommendation. Add both.** D13 in particular, because it is CRITICAL by the
same reasoning that made C10 CRITICAL, and because the checklist's Part D is
currently the only Part without a unit-assignment item even though its unit has
the same address ceiling as the landslides record.

**If the answer is no**, the pre-registration's verdicts stand where they are
and both are carried inside this direction's own section 18 rather than in the
shared checklist, which is worse for the other directions and no worse for this
one.

---

## Q7. Does this direction need its own vocabulary detector

**The question.** The roads direction carries `research/roads/check_vocabulary.py`
for the vocabulary A6 fixed in rule RC-011. Rules RC-006, RC-007 and RC-008 are
this direction's, and `research/shared/check_research_claims.py` already carries
regexes for all three.

**What the shared checker does not cover.** Three of this direction's own
prohibitions are narrower than any RC rule and no detector exists for them:

- a night contrast quoted without its fire-hour exposure, which
  pre-registration section 12.5 requires;
- a coefficient from the offset grid quoted without its grid cell, which section
  5.5 requires;
- a quantity from the `phi` sensitivity family quoted without its `phi`
  printed on the same line, which section 22.1 item 12 requires.

Each of those is a forbidden phrasing listed in section 23 and each is exactly
the kind of thing that survives review and then appears on a poster.

**Recommendation. Yes, and A5 writes it in the tree it owns**, as
`research/suppression/check_vocabulary.py`, validated in both directions on a
corpus of overclaim spellings and a corpus of legitimate neighbours, in the way
`research/FORBIDDEN_CLAIMS.md` requires, because a rule that fires on legitimate
hedged wording teaches people to ignore the checker.

**Not this round.** It is a detector for sentences that do not exist yet, and
writing it now would be an unvalidated script committed ahead of its corpus. It
is the first thing A5 writes once a sign-off state exists.

---

## Q8. Should the night arm and the access coefficient be demoted in v0.1

**The question.** Pre-registration section 25.3 names this as the direction's
weakest point and offers A6 two routes:

- **Route A.** Measurement M-R becomes a blocking condition on both the night
  contrast and the access-distance coefficient. Neither is reported until Korean
  satellite detections have bounded the report offset from below.
- **Route B.** Both are demoted to permanently secondary status in v0.1. They are
  reported, always with the grid, never as headline findings, and never
  interpreted as effects. The score may still use access distance as a predictor
  because a predictor's coefficient is not interpreted.

**Why it is a real choice and not a formality.** Route A is stronger and it
makes two of the direction's three arms hostage to `FIRMS_MAP_KEY`, which is
behind WJ-001 along with everything else. Route B is weaker and it does not
depend on a gate clearing.

**Recommendation. Route B.** The pre-registration already withdraws the night
arm outright if a sign flips inside the grid (failing condition F4), so the
catastrophic case is covered by a rule that needs no data. Demotion covers the
non-catastrophic case, where the sign holds but the magnitude is unbounded.
Making the arm depend on a key that may never arrive converts an interpretation
problem into a scheduling problem, and this program has enough of those.

**If A6 prefers Route A**, nothing in the design changes except that two entries
in section 23's key path list become conditional, which is a smaller edit than
it sounds.

---

## Q9. Is the counterfactual withdrawal of section 3 too strong

**The question.** The brief asks which fires would have grown large.
Pre-registration section 3 withdraws that quantity as a reported output
entirely, keeps a three-value sensitivity family in its place, and forbids
interpolating between the three values or summarising them as one curve.

**The case that it is too strong.** A withdrawn quantity cannot be examined. A
reader who wants to know how much suppression changed Korean fire sizes gets
three curves and an assumption rather than an answer, and three curves under an
assumption nobody believes at either endpoint may communicate less than a single
estimate with a wide interval.

**The case that it is right, which is A5's.** Section 3.1's argument is not that
the data are thin. It is that **no row in the record has the event**: every
Korean forest fire is suppressed, so the indicator that ordinarily identifies a
survival distribution is zero everywhere, and the estimator of the unsuppressed
distribution is whatever the model extrapolates past the last instant any fire
was observed burning. A wide interval would describe sampling variability around
a quantity that the data do not identify at all, which is a worse
misrepresentation than three labelled curves, because an interval reads as
uncertainty that more data would shrink and this one would not.

**Recommendation. Keep the withdrawal.** A5 would resist a weakening of it and
would want the resistance recorded. The landslides direction reached the
equivalent conclusion about its recovery window and A6 made the withdrawal a
condition on the **quantity** rather than on the sentence, precisely because a
number that exists finds a sentence. The same reasoning applies here.

**If A6 or John rules the other way**, the minimum A5 would ask for is that
whatever is reported carries assumption A-NI's name in the same sentence, that
its violation's known direction is stated there, and that rule RC-006's
graduation path is not treated as cleared by the ruling.

---

## Q10. Should this direction fit anything if the record never lengthens

**The question.** Gate G1 is shut. If WJ-001 never clears, or if it clears and
the API does not reach past 2015, the registered split never returns a fold.
Does the direction fit something anyway on four years, described honestly as
descriptive?

**Why the temptation is real.** Four years and 2,020 fires is not nothing. A
containment hazard fitted on it would converge, would produce plausible
coefficients, and would look like progress in a program that needs some.

**Why the answer is no.** Three reasons and the third is the one that settles
it. A descriptive fit on four years of one doctrine period, with no held-out
year, cannot distinguish a signal from the two spring weeks that dominate the
record. A tail fitted on the same support is dominated by a single 2025 complex,
which gate G3 exists to catch. And **a number that exists finds a sentence**: a
descriptive coefficient will be quoted without the word descriptive inside a
month, which is the exact failure mode that
`research/FORBIDDEN_CLAIMS.md` was written to prevent and that A6 invoked when
it withdrew the landslides direction's lower bound rather than hedging it.

**Recommendation. No fit, and the accounting is the deliverable.** Failing
condition F2 of the pre-registration fixes this in advance, and the phrase
"preliminary result" is named there as one that does not appear.

**What the direction delivers instead, and it is not nothing.** The clock and
address measurements committed under `design/`; the cause-field finding, which
removes a covariate the brief assumed was available; the fold arithmetic that
tells John the record must reach 2015 before a single fold exists and 2010
before the season ledger means anything; and the data case in
`DATA_REQUIREMENTS.md` that turns WJ-001 from a blocker into a decision with a
stated payoff. That is a real output of a round and it is the honest one.
