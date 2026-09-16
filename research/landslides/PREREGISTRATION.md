# Landslides direction, pre-registration index

**The pre-registration is not in this file.** Section 2 of
`research/eval/SIGNOFF.md` names pre-registrations
`research/<direction>/PREREG_<direction>_<YYYY-MM-DD>.md`, so that a v0.1 and a
v0.2 can both exist unedited and neither can be overwritten. A6's round-2 record
for the roads direction, `research/eval/signoffs/roads_v0.1b.md` section 2, calls
a single file named `PREREGISTRATION.md` a file that gets overwritten, and that
is the whole reason for the naming rule.

This file is an index, so that the path the task brief names resolves to
something, and so that a reader who arrives here is sent to the versioned
document rather than to a stale copy.

## Versions

| version | file | date | state | signoff record |
|---|---|---|---|---|
| v0.1 | [`PREREG_landslides_2026-09-16_v0.1.md`](PREREG_landslides_2026-09-16_v0.1.md) | 2026-09-16 | `unsigned` | none yet |

A version is never edited after it is written. An amendment made after any look
at data is a new file with a new date and a new version number, carrying the
mandatory "what was seen before this amendment" section of `SIGNOFF.md` section
4. The `signoff` and `signoff_record` fields inside a pre-registration are
written by A6 and by nobody else.

## The supporting documents

| what | file |
|---|---|
| what each dataset is for, and what happens if it never arrives | [`DATA_REQUIREMENTS.md`](DATA_REQUIREMENTS.md) |
| the open questions, each with A4's recommendation | [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) |
| the design-side numbers, committed and re-runnable | [`design/design_numbers.json`](design/design_numbers.json) |
| the scripts that produced them | [`design/`](design/) |
| the numbers staging file, in the registrar's `entry()` shape | [`numbers_staged.json`](numbers_staged.json) |

## State

`unsigned`. Per `research/eval/SIGNOFF.md` section 3 that is the default and the
state of all three directions. This direction may acquire data, build loaders and
feature code, run prior predictive checks and simulation-based calibration, and
run the outcome-free assignability measurements M1 to M3 of the pre-registration.
**It may not fit on real labels and no number from it may be staged.** Silence is
not a signature.

## The three things v0.1 confronts rather than files as limitations

1. **The aliasing of years since fire with calendar year**, section 7. The
   identity is exact, it is the age, period and cohort identity, and the design
   matrix rank is measured rather than asserted. The committed exposure record
   supports years since fire of zero to three only.
2. **Whether the unit of analysis is viable**, section 8. No record in the
   occurrence file carries a lot number, so parcel-level geocoding is unreachable
   for all 5,118 of them. The primary unit is changed from the slope unit to the
   catchment, and the assignment error is measured before it is used.
3. **The species contrast having no data**, section 11. The forest type map is
   behind two human gates and the fallback classifier cannot be validated on
   Korean data without the map it replaces.
