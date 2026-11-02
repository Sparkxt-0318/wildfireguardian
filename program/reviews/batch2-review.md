# Batch 2 review (checkpoint 4)

Proportional review, 2026-11-02, of Track C batch 2: the batch-2 harness, E1b and E2 (SYNTHETIC dev). Per
Siyeong's process rule it used one clean-checkout reproduction agent and one reviewer, with no verifier layer. Neither
wrote the code. The full findings, with file:line evidence and the reviewer's scripts, are in the session scratchpad;
this file is the record.

## Reproduction (clean detached checkout of `evacplan/phase0` @ `5d0991ca`, fresh venv)

- **Install.** The README steps work as written. `uv pip freeze` equals `requirements.lock` (40 of 40). The wheel cache
  was warm, so this checks the pins and the steps, not a cold download.
- **Suites** (under the lock, real-data tests on, dev fires only):
  - evacplan: **433 passed**, 0 skipped, 0 failed (13.4 min; the README said about ten);
  - hazard_contract: **76 passed**.
- **Leaderboard.** Regenerated from the committed rows, it is byte-identical, margin figures included.
- **Headline reruns** (same VM session as the rows):
  - **E2, seed 0, both tight M instances:** delivered 131 and 124, bounds 156 and 143, B2 140 and 139. All as
    committed, gaps and slack counts included.
  - **E1b, seed 1, L-geo:** 486, certified in the loop at 51.4 s (committed 50.2 s); B2 528. The certify trigger
    cleared its threshold by about 0.2 s, so a slightly faster first iteration or a 10-15 % slower oracle gives B1's
    plan (395), as in 6 of the 10 committed L runs.
- **Bound validity.** 80 bound rows (E2, B3, E4) against 480 plan rows, 3,900 comparisons: **0 violations**.

## Review findings (0 major, 9 minor, 6 notes, plus one note from the reproduction; no result or decision changes)

| id | finding | status |
|---|---|---|
| H-D1 | B2's default seed offset split B2's seeds across holds; an explicit offset could overwrite B2 rows | fixed `97536395` |
| H-D2 | a hold could still replace the challenger's rows silently; the offset was read before the lock | fixed `42e0d2a5` (`--replace`, check inside the lock, `HoldRefused`) |
| H-D3 (note) | verdicts ignored interleaving and the speed flag | fixed `42e0d2a5` (n/a without a B2 partner; flagged holds counted under the bar) |
| H-D4 (note) | B2 always first in a pair; one probe per pair | kept as specified (ABAB); for the Mac holds |
| H-D5 | wording: "time to certified plan" is a mean; `runtime_s` docstring; Repeats note | fixed `42e0d2a5` |
| H-D6 | no tests for the cold certification or the "–" cell | fixed `42e0d2a5` (5 new tests) |
| E1b-D1 | a relaxed-only pass was counted as a certification | fixed `42e0d2a5` (new counters, test; rows unchanged) |
| E1b-D2 | README: B2's level reached in 3 of 10 L runs, not 6; two ms-per-leg ranges swapped | fixed `42e0d2a5` |
| E1b-D3 (note) | four tables without SYNTHETIC; no `figures/` | fixed `42e0d2a5` |
| E1b-D4 (note) | time to certified plan counts certification twice for in-loop certifiers | explained in the legend and README |
| E2-D1 | the L hold's 20 rows are `ceca7380+dirty` (`analyze.py` edited during the hold; `src/` unchanged); the leaderboard dropped `+dirty` | README discloses it (`601b6ec9`); the leaderboard keeps `+dirty` (`a2794d07`) |
| E2-D2 | six stale or slightly-off README numbers | fixed `601b6ec9` (the locked debugging runs were six, not five) |
| E2-D3 | the in-budget oracle repair path had no test (it never ran on dev) | test added `601b6ec9` (dose-limited tiny case: 2 repairs, every returned trip checked) |
| E2-D4 (note) | a repair-path MIP could wait up to ~1 s past the deadline | fixed `601b6ec9`: every worker call is capped at the deadline; a failed call keeps the incumbent |
| E2-D5 (note) | the full suite and the rule-3 guard had not run on merged code | resolved by the reproduction (433 passed) |
| R (note) | `program/benchlock.py` on the track branch lacks `--wait-max` (next/integration has it); CLI path flags hidden from `--help` | no action: program/ lives on next/integration |

Found while fixing, left for E2's second iteration because fixing them changes the method:
- the repair loop can make 3 repairs (config says at most 2) and return a plan it did not re-check (the harness certifies it anyway);
- the phase-C "5 % MIP if new columns" never runs once LNS has run.

**Checked and found correct**, recomputed from the rows:
- **Rule 3:** only the oracle declares states, and unresolved is never counted. Every row comes from the harness's
  cold certification.
- **Budget:** the budget is respected (0 of 200 batch-2 rows over 60 s). In-loop oracle time counts; final
  certification is outside the budget for every method.
- **Pre-registration:** both pre-registrations were pushed before any method code or dev run. E2's three amendments
  used generated instances only.
- **Decisions:** both decision rules were applied as written: E1b KILL, E2 ITERATE.
- **Numbers:** every number in both READMEs, `results.csv`, the leaderboard's 150 per-instance cells and the profile
  matches the rows.
- **Merge:** the merge (`a67b8ea2`) is the exact keyed union: B2 seeds 0-9 on all 10 instances, and 100 speed rows
  across 4 holds.
