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
- **CSV:** one new column, "마감 근거 (모델 · 1시간 재현)", holding the kind ONLY. The raw-seconds columns of 79ad132
  were removed: the orchestrator ruled that "no later value in any form" covers every operational output, raw
  seconds included. The present-fire-only value stays only in Richard's research file. Header test: 12 → 13 columns.
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

## Count reconciliation with Owen's verified file (530 records: window 478 / present_fire 8 / forecast_dependent 22 / no_checked_route 22)
Measured from the source file by record kind:

| | window | present_fire | forecast_dependent | no_checked_route | total |
|---|---|---|---|---|---|
| dispatch (villages, facilities) | 473 | 7 | 21 | 21 | 522 |
| research origins | 5 | 1 | 1 | 1 | 8 |
| file total (Owen) | 478 | 8 | 22 | 22 | 530 |

- The planner kit covers 531 field places. That is the 522 dispatch records plus 9 village-scenarios with no record: 3
  villages × 3 caches that never reached the caches (no road node within 2 km; Richard). It builds no field messages
  for the 8 research origins.
- The 21 dispatch no_checked_route records split by the planner's own verdict: 11 are model_no_route (no label) and 10
  are unresolved (they get the "timed out; the exact analysis finds no route" note).
- So labelled = 473 + 7 + 21 = 501, the planner's leave-by places. Mira's independent join reproduces every count.

## Delta after Mira's PASS WITH NOTES at 79ad132 (one commit; wording a0b1077 before it)
- **N1, fail closed:** `parseProvenanceFile` validates every record: known kind, integer-second fields, and both values
  for forecast_dependent. A bad record is kept apart in `invalid`. That place is "not established" (`invalid_record`),
  never a crash, and an unknown kind never reaches the text table (test with three malformed records).
- **N2, help sentence**, shown with every labelled deadline: "This label describes the model's exact latest departure;
  the leave-by time shown is the last checked departure step at or before it." / "이 표시는 모델이 계산한 정확한 마지막
  출발 시각의 근거입니다. 화면의 출발 마감은 그 시각이거나 그보다 앞선, 마지막으로 점검한 출발 시각입니다." On the real set
  T < exact in all 501, so it reads "at or before" to stay true in general.
- **N3, decision:** the CSV carries the kind only (above). A test asserts that no present-fire-only value appears
  anywhere in the CSV.
- **Wording:** Sofia's Korean ("근거" throughout). For the window line, Sofia's second suggestion: "산불 상황에 따라 정해진
  시각이 아닙니다". It avoids "관계없는" being read as "not urgent".
- The CSV column header uses "·" instead of a comma.
- Suite 26 files / 417 tests; build:static OK.

## Message-kit staff block (branch clara/kit-provenance-line, after #138 and #139) (UNVERIFIED)
`buildChannels` takes `deadlineProvenance` (the `staffProvenance` label) and writes **`staff.provenance` only**: tag,
text, help sentence (for a labelled deadline) and footer, in Korean and English. It is excluded from the
official-first and replay-note rules, as the other staff lines are. The kit's word scans still apply to it.
Test over the 531 real places: every resident output, and every other staff field, is identical with and without the
label, and the violations are identical. The line is present exactly when there is a label (473 window, 7 present_fire,
21 forecast_dependent, 10 unresolved-proven-no-route; 20 none) and never carries a clock time. No app code calls the
channel builder yet, so this is wiring for when it does. Suite 26 files / 447 tests; build:static OK.
