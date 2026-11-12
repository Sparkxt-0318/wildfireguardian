# Deadline provenance flags (stream 3) — UNVERIFIED

Design: Iris (adopted, with four changes). Data: Richard's F-3.1 field, `DEADLINE_PROVENANCE_1h.json` at f0577de,
sha256 3f558d92…, **verified by Owen (PASS WITH NOTES)**. Staff outputs only. Branch: clara/deadline-provenance,
built on clara/staff-headline (the flags hang off the staff headline function; that branch has Mira's PASS WITH
NOTES at b45a94b, and 37fb457 is pending).

## Data
`split_provenance.py` (Python 3.12) checks the source sha256 and writes one file per cached scenario:
`planner/public/data/provenance/<region>__<input>.json`, schema `wfg.planner.deadline_provenance/1`. Each file
records the verified source (commit, path, sha256, verdict), the horizon (3600 s) and **the cache it belongs to
(path + sha256 from planner/cache/INDEX.json)**. The planner accepts a file only for exactly that cache, so a record
from a different input time is never used (test). The schema reads the horizon from the file, so it does not depend on
the 1-hour run.

## Rule (`planner/src/features/provenance/model.ts`)
A label shows only when all of these hold:
- the staff headline kind is a deadline;
- the plan on screen comes from the recorded cache (not live, not MOCK);
- the file belongs to this cache;
- a record exists;
- **T ≤ the record's exact leave_by_s**.

Otherwise the label is "not established", or "not computed" when there is no record. Unresolved places never get a
time or "no route". Where the exact field proves no route, staff get Richard's note: "the route check timed out; an
exact later analysis finds no checked route at any departure in the model".

## Wording (staff; Korean pending Sofia)
- window: "Set by the scenario window; fire does not change it. Nothing after the 1-hour scenario was computed." This
  states Owen's limit 2 without the kit-forbidden 안전.
- present_fire: "Set by fire already burning (the same without forecast new ignitions)."
- forecast_dependent: "Depends on the fire forecast. Re-check at every update; it may move earlier. Without forecast
  new ignitions the model time would be N min later; that is not extra time and not a checked route."
  - This covers Owen's limit 3: the present-only witnesses are not full-policy checked.
  - The gap is given in whole minutes, never as a clock time; "less than 1 min" below a minute.
- Footer: "Model provenance on the 1-hour replay; not fit for live use. Comprehension is untested." Hypothesis (Iris):
  staff may read "later" as permission. That risk is untested.

## Surfaces
- **Right panel:** a line under the headline, with tag, text and footer.
- **A4 sheet:** the kind only, as a compact tag on the deadline cell's sub line. There is never a later value.
  Measured: a separate line pushed 3 English sheets past one page (print-fit test, 2.75–9.72 mm). The tag therefore
  shares the sub line, and the redundant "same on contiguous basis" sub was dropped (the main time is the contiguous
  time since STAFF-HEADLINE). The sheet test was updated accordingly.
- **CSV:** three new columns.
  - "마감 근거 (모델, 1시간 재현)": the kind.
  - Both raw values in seconds after the input time ("예측 포함 마감 s", "현재 불만 마감 s (여유 시간 아님)"), for
    forecast-dependent rows only.
  - Header test updated: 12 → 15 columns.
- **W-KIT staff block:** NOT in this cut. This branch's kit is Main's, without the W6 staff fields, so adding it here
  would only conflict with the W6 branch. It follows once W6 merges.
- **Resident outputs and the public page:** none. A test checks every provenance text and tag against the card and
  the kit messages of all real places.

## Measured (531 real places, six booth caches)

| staff headline | label | count |
|---|---|---|
| deadline | window | 473 |
| deadline | present_fire | 7 |
| deadline | forecast_dependent | 21 (gap 0–24 min; 0 → "less than 1 min") |
| unresolved | timed out, exact analysis: no route | 10 |
| unresolved | — | 9 (not in the caches: no road node within 2 km; Richard) |
| no_route | — | 11 |

T ≤ exact leave_by_s in all 501 labelled deadlines. No place is "not established" on the real set.

Tests:
- `tests/planner/provenance.test.ts`: file identity, counts, fail-closed cases, A4 kinds, CSV raw-value direction,
  no provenance string in resident outputs, live/MOCK plans refused;
- `features.exports.test.ts`: header;
- `features.plansheet.test.ts`: sub line.

Suite 26 files / 415 tests; build:static OK; the 6 provenance files ship in the default static build (staff planner
data). The static smoke script was not run: it rewrites the tracked screenshots.
