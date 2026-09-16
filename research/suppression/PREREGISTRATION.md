# Suppression direction, pre-registration index

**The pre-registration is not in this file.** Section 2 of
`research/eval/SIGNOFF.md` names pre-registrations
`research/<direction>/PREREG_<direction>_<YYYY-MM-DD>.md`, so that a v0.1 and a
v0.2 can both exist unedited and neither can overwrite the other. A6's round-2
record for the roads direction calls a single file named `PREREGISTRATION.md` a
file that gets overwritten, and that is the whole reason for the naming rule.

This file is an index, so that the path a brief might name resolves to
something, and so that a reader who arrives here is sent to the versioned
document rather than to a stale copy.

## Versions

| version | file | date | state | signoff record |
|---|---|---|---|---|
| v0.1 | [`PREREG_suppression_2026-09-16_v0.1.md`](PREREG_suppression_2026-09-16_v0.1.md) | 2026-09-16 | `unsigned` | none yet |

A version is never edited after it is written. An amendment made after any look
at data is a new file with a new date and a new version number, carrying the
mandatory "what was seen before this amendment" section of `SIGNOFF.md` section
4. The `signoff` and `signoff_record` fields inside a pre-registration are
written by A6 and by nobody else.

## The supporting documents

| what | file |
|---|---|
| what each dataset is for, what happens if it never arrives, and the fallback | [`DATA_REQUIREMENTS.md`](DATA_REQUIREMENTS.md) |
| the open questions, each with A5's recommendation | [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) |
| the design-side measurements, committed and re-runnable | [`design/design_numbers.json`](design/design_numbers.json) |
| the script that produced them | [`design/clock_and_address.py`](design/clock_and_address.py) |
| the numbers staging file, in the registrar's `entry()` shape | [`numbers_staged.json`](numbers_staged.json) |

## State

`unsigned`. Per `research/eval/SIGNOFF.md` section 3 that is the default and the
state of all three directions. This direction may acquire data, build loaders
and feature code, run prior predictive checks and simulation-based calibration,
and run the outcome-free measurements already committed under `design/`.
**It may not fit on real labels and no number from it may be staged.** Silence
is not a signature.

**And a second gate sits underneath the first.** Even a signature would not
permit a fit today, because the registered split
`forward_chaining_by_year` with `min_train_years: 10` refuses the committed
four-year record, and pre-registration section 4.2 quotes the refusal verbatim.
That refusal is A6's own committed code with A6's own committed test on it.

## The five things v0.1 confronts rather than files as limitations

1. **The unsuppressed counterfactual is never observed**, section 3. It is not
   censoring in the usual sense: every Korean fire is suppressed, so no row in
   the record has the event, and any recovery of the unsuppressed distribution is
   done by an assumption rather than by the data. The quantity is withdrawn and
   a three-value sensitivity family replaces it.
2. **Four years, and one of them nearly empty**, section 4. Six numbered gates,
   the first of which is the registered split and is shut today. The arithmetic
   of how deep the Korean record must reach is in section 4.3.
3. **Report time is not ignition time**, section 5. The offset biases both of the
   direction's headline covariates toward the hypothesis. A sixteen-cell
   sensitivity grid, a measurement that would bound the offset from Korean
   satellite detections, and a withdrawal rule if a sign flips.
4. **The held-out year may not be held out**, section 6. Per-fold effective
   sample sizes reported beside every per-fold metric, and no year designated a
   stress test.
5. **The neural extreme-value model is conditional**, section 7. Not designed
   against, not in the fit enumeration, and not in the verified bibliography.

## Three departures from the design as briefed

Listed in pre-registration section 1.6 and summarised here:

- the counterfactual size distribution is withdrawn as a reported quantity;
- the night arm becomes a containment-hazard contrast, because the record holds
  no fire size at any intermediate hour and so no growth to compare;
- cause is removed from the primary covariate set, because 34.75 per cent of the
  record's cause entries carry 조사중, 추정 or 미상 and the field is therefore an
  outcome of an investigation rather than an observation at the horizon.
