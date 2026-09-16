# Sign-off protocol

**Owner: A6, the validation agent. Version 1.0, 2026-09-16.**
Nothing in this file is negotiable between agents. Where it is wrong, it is
changed by a new version with a date, and the old version stays.

A sign-off is not a compliment and not a review of how good the idea is. It is
one narrow statement: **the design is specified tightly enough that the result
it produces will mean something, whichever way it comes out.** A direction can
be signed and then fail its hypothesis. That is the normal, successful case.

---

## 0. What the sign-off gates

| activity | unsigned | signed |
|---|---|---|
| acquiring and verifying data | yes | yes |
| building the pipeline, loaders, feature code | yes | yes |
| prior predictive checks, simulation-based calibration, fits on simulated data | yes | yes |
| looking at covariate distributions listed in the pre-registration | yes | yes |
| **any fit whose outcome variable is the real label** | no | yes |
| **any number, figure or table with a real outcome on it** | no | staged only, see `NUMBERS_PROTOCOL.md` |
| **any sentence that states the hypothesis as a result** | no | no, until the graduation path in `research/FORBIDDEN_CLAIMS.md` completes |

The reason the unsigned column allows so much: the expensive work is the
pipeline, and blocking it would make this protocol a tax rather than a gate.
The thing that is blocked is the one thing that cannot be undone, which is
seeing the answer before the question was fixed.

---

## 1. What a pre-registration must contain

Sixteen items. Each one carries the acceptance test A6 actually runs, and the
way it is usually failed. An item that is missing is not a refusal on its own;
a *vague* item is, because a vague item is what lets the design move after the
result is seen.

### P1. The hypothesis in falsifiable form

Write the claim, the direction of the predicted effect, and the value under the
null, in one paragraph that contains no methods. Then write the sentence "this
hypothesis is wrong if ...".

*Acceptance test.* A6 tries to write a result sentence that satisfies the
hypothesis and also a result sentence that satisfies its negation. If both are
writable from the text, it passes. If every plausible outcome can be read as
support, it is refused.

*Usual failure.* "We expect barrier width to be informative." Informative how
much, in which direction, against what alternative.

### P2. The unit of analysis

One row is what, exactly. Expected row count. The clustering structure stated
explicitly: which rows share a fire, a day, a storm, a road, a slope, a scene.
An estimate of the effective sample size after that clustering, and the method
used to get it.

*Acceptance test.* The row count and the effective sample size are both given
as numbers, and the second is smaller than the first.

*Usual failure.* Eight thousand 100 m segments reported as eight thousand
observations, when they are five fires.

### P3. The label rule

A procedure that two people would follow to the same answer. It must state:
the exact input data and the scene or file it comes from; every threshold with
its unit; the spatial and temporal windows; the tie-break for ambiguous cases;
and an explicit **unlabelable** class, because a rule with no unlabelable class
forces guesses into the majority label.

*Acceptance test.* A6 draws ten units at random, labels them from the written
rule alone without talking to the author, and compares. More than one
disagreement in ten refuses the item. A6 also asks for a second pass over at
least thirty units by a path the author did not write, and the disagreement
rate goes in the pre-registration, not in a later footnote.

*Usual failure.* "Segments where the fire clearly crossed." Clearly is not a
threshold.

### P4. Covariates and their sources

A table: name, definition, unit, source dataset id as it appears in
`research/data/REGISTRY.yaml`, the moment in time at which the value is
knowable, and a yes or no column **derived from anything that touches the
label**. Any yes needs a paragraph.

*Acceptance test.* Every dataset id resolves in the registry with status
`verified` or with a named Waiting-on-John item. Every knowable-at time is at
or before the prediction time. Every yes in the last column has its paragraph.

*Usual failure.* A covariate and the label computed from the same raster.

### P5. The model form

Likelihood, link, the full parameterisation, priors with one line of
justification each, the random effects and what they absorb, and a paragraph on
identifiability: which parameters the data can separate and which it cannot.
Software and version, seeds, and the convergence criteria fixed in advance
(R-hat, effective sample size, divergent transitions) together with what
happens when they are not met.

*Acceptance test.* The identifiability paragraph names at least one parameter
the design cannot pin down. A model form where everything is identified is a
model form nobody has thought about hard enough.

*Usual failure.* A product of two latent probabilities fitted to one binary
outcome, with no second source of information to separate them.

### P6. The held-out sets, named in advance

The named fires, complexes, years or blocks. The exact call into
`research/eval/splits.py` with its keyword arguments, and the fingerprint the
call returns. A sentence stating that the held-out outcomes have not been
looked at, and by whom.

*Acceptance test.* A6 re-runs the call and compares fingerprints. A mismatch is
a refusal with no discussion, because the fingerprint is the only thing that
makes "the split we said we would use" checkable later.

*Usual failure.* A split rebuilt at fit time with a different seed.

### P7. The primary metric, named in advance

One metric. One number. Its uncertainty and how the uncertainty is computed
(the resampling unit must be the cluster, not the row). The evaluation frame
that will always be quoted beside it, which is what rule RC-008 requires.
Secondary metrics are listed and labelled secondary; a secondary metric cannot
be promoted after the fact.

*Acceptance test.* The primary metric is a single named quantity, and the
resampling unit is the cluster from P2.

*Usual failure.* Four metrics, of which the best one is reported.

### P8. The simple baseline it must beat

Named, with its own code path, and genuinely simple: the majority class, a
single-covariate model, persistence, or the published rule the direction
exists to test. The margin that counts as beating it is fixed **now**, in the
units of the primary metric, with its uncertainty treatment.

*Acceptance test.* A6 can implement the baseline from the description in under
an hour, and the margin is a number, not "better".

*Usual failure.* A baseline chosen after the model's score is known, weak
enough to lose.

### P9. What would count as the hypothesis failing

Written so it cannot be re-read as a success. Name the outcome, the threshold
and the reading. This is the item A6 reads first and refuses on most often.

*Acceptance test.* A6 writes the failure sentence in advance, in the kill-shot
file, and the author agrees to it before the fit.

*Usual failure.* "If the effect is not found we will investigate why." That is
not a failing condition, that is a plan to keep going.

### P10. Stopping rule and multiplicity

How many model variants will be fitted. What happens when the first one fails
to converge. The family of comparisons and the correction, or a statement that
no correction is applied and why. The count of fits run before the reported one
is recorded and reported.

### P11. The leakage self-audit

The completed checklist of `research/eval/LEAKAGE.md`, item by item, with a
verdict and a one-line justification. A6 re-runs the checklist independently
rather than reading the author's verdicts, but the author's verdicts must exist
first, because the difference between the two lists is itself information.

### P12. Data provenance

Every dataset used, by registry id, with its status and its sha256 on disk. A
dataset at status `pending` may appear in a pre-registration, but the sign-off
is then `signed with conditions` at best, and the condition is that the fit
does not start until the status reaches `verified`.

### P13. Compute and feasibility

One laptop, no HPC, no GPU training. The expected wall-clock time of the full
fit and of the cross-validated fit. What gets cut if it does not fit, decided
in advance.

### P14. Scope declaration

Korea only, stated. Every foreign source listed with the sentence that it
supplies a method, an equation or prior art, and that its data is not used for
fitting. This mirrors scope rule 1 and rule RC-010.

### P15. What the result will not say

The claims the direction will not make even if the fit looks good. This is the
item that protects the program from its own enthusiasm, and it is the one that
the poster and the paper will quote.

### P16. The shape of the result artifact

Every number that might later be quoted has to be registrable, and
`docs/NUMBERS.json` accepts a number only through `scripts/build_numbers.py`,
whose `entry()` helper requires `source_file` to be a committed JSON artifact
and `json_path` a dotted path into it. So the pre-registration names:

- the path of the committed JSON result artifact the direction will emit;
- the dotted key path of every quantity that might be quoted, including the
  primary metric, its interval, the baseline's metric and the row counts;
- the per-direction staging file `research/<direction>/numbers_staged.json`,
  written in the registrar's own `entry()` shape.

*Acceptance test.* A6 can point at a key path for the primary metric and for the
baseline before the fit exists.

*Usual failure.* The direction emits a report and a figure, the number lives in
prose, and the registrar cannot address it. Fixing that after the fit means
rewriting the output layer, which is why this item is a pre-registration item
and not a reporting item. The detail is in `research/eval/NUMBERS_PROTOCOL.md`
section 5.

---

## 2. Files and naming

| what | where |
|---|---|
| pre-registration | `research/<direction>/PREREG_<direction>_<YYYY-MM-DD>.md` |
| sign-off record | `research/eval/signoffs/<direction>_<prereg date>_v<n>.md` |
| the ledger | `research/eval/signoffs/LEDGER.md` |
| staged numbers | `research/eval/numbers_staging.json` |
| kill-shot section | `research/eval/killshots/<direction>.md` from the template |

A6 cannot write inside a direction's own folder, and does not. The signature
lives under `research/eval/signoffs/`, and the pre-registration links to it.
That separation is deliberate: the reviewed document and the review are written
by different hands in different places.

Every pre-registration opens with this block, so compliance can be checked
without reading prose:

```yaml
prereg:
  direction: roads            # roads | landslides | suppression
  version: 1                  # increments only via section 4
  date: 2026-09-16
  author: A3
  items_present: [P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, P15, P16]
  result_artifact: "research/<direction>/results/<name>.json"
  primary_metric_json_path: "held_out.primary_metric.value"
  split_call: "leave_one_complex_out(fire_ids)"
  split_fingerprint: "<sha256 from splits_fingerprint()>"
  primary_metric: "<one name>"
  baseline: "<one name>"
  datasets: [kfs_forest_roads, sentinel2_l2a_dnbr, dem_korea]
  outcome_seen: false         # true means section 4 applies
  signoff: unsigned           # written by A6 only
  signoff_record: null        # path, written by A6 only
```

The `signoff` and `signoff_record` fields are written by A6 and by nobody else.
A pre-registration that arrives with `signoff: signed` already filled in is
refused on sight, and the refusal is recorded.

---

## 3. The four states

### `unsigned`

The default, and the state of all three directions today. The direction may do
everything in the unsigned column of section 0. It may not fit on real labels,
and no number from it may be staged.

### `signed`

The design is specified tightly enough to be worth running, and A6 found no
unresolved critical leakage item. The direction may fit, once, on the
pre-registered design with the pre-registered split. Numbers go to
`numbers_staging.json` and are re-run by A6 before they are quoted anywhere.
A signature covers the design that was read: a change to the model form, the
label rule, the covariates, the split or the metric is section 4, not a tweak.

### `signed with conditions`

The design is sound but something is unfinished or unverified. The record lists
numbered conditions, each with the verification action that clears it and the
phase by which it must clear. Each condition is marked **blocking for the
primary result** or **blocking for a named secondary claim**. The direction may
fit. A number produced while a blocking condition is open is not staged, and if
it has already been staged it is marked `withdrawn_pending_condition`. This is
the expected state for a direction whose datasets are still at status `pending`
behind a Waiting-on-John item.

### `refused`

The record lists the reasons, each with what would clear it, in the order A6
would fix them. The direction may not fit on real labels. Refusal is a normal
event and carries no blame; the usual path is a revised pre-registration in the
same round. What a refusal must never be is silent: it is written, dated and
carried in the ledger even when the author fixes it an hour later, because the
record of what was nearly done is part of the evidence base.

---

## 4. Amendment after data has been looked at

A pre-registration amended after any look at data is **a new pre-registration**.

- It gets a new file with a new date and `version: n+1`.
- The old file is kept, unedited, forever. Editing it is the one thing in this
  protocol that cannot be repaired afterwards.
- The new file carries a mandatory section, **"what was seen before this
  amendment"**, listing every quantity already looked at: every plot, count,
  crosstab, fitted coefficient and convergence diagnostic, and who saw it.
- A6 signs the new version only when that section is filled in. An amendment
  whose author cannot remember what they looked at is refused, and the honest
  remedy is a fresh held-out set that nobody has touched.
- Numbers produced under the old version keep the old version's name, and are
  reported as such.

"Looked at data" means any view of the outcome variable, or of any quantity
computed from it: a map coloured by the label, a count of crossings, a fitted
coefficient, a convergence warning that depended on the outcome, or a summary
from another agent. Views of covariates that carry no outcome information are
allowed and are listed in P4.

---

## 5. Escalation when A6 refuses and the author disagrees

There is no negotiation between agents. The order is fixed:

1. **A6 refuses**, in writing, with each reason naming what would clear it.
2. The modeling agent chooses one of three: revise the design, accept the
   conditions, or disagree.
3. On disagreement, the modeling agent writes **one page** at
   `research/reports/<agent>/<date>_rebuttal_<direction>.md`: what A6 got wrong,
   what evidence supports that, what it costs to comply.
4. A6 appends **one page** at `research/eval/signoffs/<direction>_<date>_response.md`.
   A6 does not revise the refusal in response to persistence alone. A6 revises
   it in response to a fact.
5. The orchestrator adds a **Waiting on John** item to `research/TASKBOARD.md`
   naming both documents and asking **one** question with two options and a
   recommendation. John decides. His answer is recorded in
   `research/DECISIONS.md` and is binding on both agents.
6. While the gate is open, the direction does not fit on real labels, and the
   other two directions are unaffected. An escalation never stops the program.

Two standing rules attached to this path:

- **A6 does not sign a design A6 helped create.** Where A6 has contributed more
  than a checklist to a direction's design, the record says so and the default
  is the human gate at step 5 rather than an A6 signature.
- **Silence is not a signature.** A direction that has not received a written
  state is `unsigned`, whatever the schedule says.

---

## 6. The review pass A6 runs on receipt

In this order, and the order matters, because steps 1 and 2 are done before A6
knows anything about what the design is likely to find:

1. Read the pre-registration against P1 to P16 and record the item verdicts.
2. Draw ten units and label them blind from the written rule alone (P3).
3. Re-run the split call and compare fingerprints (P6).
4. Run `research/eval/LEAKAGE.md` independently, then compare against the
   author's verdicts and record every difference (P11).
5. Write the direction's kill-shot prior from `research/eval/KILLSHOT_TEMPLATE.md`,
   before any result exists.
6. Write the state, the reasons and the conditions; update the ledger.

Turnaround: one round. A pre-registration that A6 has not answered within one
round is escalated by the orchestrator as a schedule item, not resolved by the
author assuming consent.
