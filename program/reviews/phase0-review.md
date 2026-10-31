# Phase 0 review (checkpoint 2)

Independent review, 2026-10-31. Each track was reviewed by a fresh agent that wrote none of the code,
from a clean detached checkout with a fresh venv; every finding was then put to a second agent that tried
to refute it (verdict after the arrow). Reviewed commits: Track C `evacplan/phase0` @ `31048003`,
Track A `firecast-lab/phase0` @ `821ceb4e`. Status of each fix: last section.

## Track C — evacplan

**Tests.** A README install resolves numpy 2.5.4 and ortools 9.15.6755: evacplan 254 passed, 7 failed
(all B2: OR-Tools 9.15 rejects `SetAllowedVehiclesForIndex`'s argument); the same 8 items pass with
ortools 9.14.6206 (the authors' version). hazard_contract 75 passed, 1 failed (`np.trapz`, gone in numpy 2.5).

**Headline (dev, 60 s, seed 0) vs committed rows @ 957e6720.**
- B1: 1353/1975, identical on all 10 instances.
- B2 (ortools 9.14): full run 1750 delivered / 0 unresolved vs 1683 / 67 committed (+4.0 %). Nine instances
  identical; on M-geo-t25-s106 the full run gave 155/155, three single-instance reruns 87 + 68 unresolved.
  A fresh oracle re-checks the authors' saved plan at 88/67, so the committed number is a real verdict.
  The verifier pinned the cause: B2's seedless, time-limited search is deterministic in its depth —
  155/0 up to ~900 solutions, 88/67 from ~920 to ~1130, 100/55 at 150 s — and machine load sets the depth.
- Every row: delivered + unresolved + model_no_route + not planned = residents; CSV, oracle JSON and
  per-facility sums agree; no row over budget.

**Checks.** Rule 3 pass (rows come only from `Oracle.check_plan`; deadline states only from
`Oracle.class_deadline`). Rule 4 pass (unknown cells, outside the grid and past the horizon →
`supported=False` → unresolved; only checked trips count). Negative relaxation sound (blocks only contact
certain by the horizon, unknown passable, free waits, no turn rules, complete lattice only). Oracle diff
since C0 keeps `_classify`/`_evaluate`/`check_plan` unchanged; property tests pass. `ed28317c` test edits
are the conservative direction. Split frozen before the harness and every method; fingerprints enforced;
`--set test` refused. Equal time pass (one 60 s table, solve wall clock incl. B3's child, single thread,
bench lock). Provenance on every row. SYNTHETIC labels everywhere. Caldor honestly BLOCKED.

**Discrepancies.**
- C-M1 B2's dev total depends on search depth (1682–1750 across reruns, all from s106) → **confirmed, major**.
- C-M2 `ortools>=9.10` unpinned; a README install crashes B2 → **confirmed, major**.
- C-M3 horizon-only refusals are reported UNSERVABLE `model_no_route` (cause NO_ROUTE, detail blames contact)
  while the oracle rates the trip unresolved/BEYOND_HORIZON → **partly, minor** (documented choice, ASSUMPTIONS
  #74, already question 12; nothing becomes safe; the cause label is wrong).
- C-M4 the suite regenerates the 10 test-set instances in memory for fingerprint checks → **partly, minor**.
- Minor, confirmed: real-data tests default to this session's scratchpad path; the rule-3 guard regex misses
  6 of 9 declaration patterns (no current violation); hazard_contract tests break on numpy 2.5 / a missing data
  folder; rows record hazard_contract "1.0" and no solver/numpy versions, dirty check covers only evacplan/;
  the leaderboard says every number comes from the oracle (bounds come from B3).

## Track A — firecast-lab

**Tests.** firecast-lab 116 passed, 3 skipped (2 need torch; 1 refusal branch skipped because `wfg_latest`
is importable). hazard_contract 74 passed, 1 failed (`np.trapz`), 1 skipped (real packet; passes with data).

**Headline.** No real-data number exists and none is claimed. `run`, `time-c651`, `decision` and
`python -m firecast_lab.data` all exit 1 with clear messages (no data root; metadata-only root rejected; no road
graphs; no PyTorch) and write nothing. The one documented number, the decision-metric cost (~4.6 min/window),
reran at 3.4 min/window on a SYNTHETIC hazard over the real Uljin graph — same order (no script committed).

**Checks.** SPLITS.json is the first track commit and unchanged; whole fires; test = US-2024 + KR-2025 marked
not fresh; fresh holdout locked; `--allow-test` gate. Cross-fitting: spy models never fit on the scored fire's
fold. Bootstrap resamples whole fires. Only `evacplan.Oracle` declares verdicts; cleared = checked in all K;
unknown truth excluded and counted. Rates match a hand example (false-safe undefined, not 0, when nothing is
cleared). Producer: NaN → unsupported; same cutoff, different futures → bit-identical scenario sets (no
hindsight). Domain: final perimeter + 3 km. All metric functions match hand values. Equal time n/a.

**Discrepancies.**
- A-M1 Korean decision truth treats cells outside Choi's centre-in-perimeter mask as never burning, so
  partly burned edge cells are truth-safe and false-safe is biased low → **confirmed, major** (on a SYNTHETIC
  fire over the real Uljin graph, every false-safe in the front-reaching windows came from this).
- A-M2 the decision .json and printed rate lines carry no SYNTHETIC flag → **partly, minor**.
- A-M3 scikit-learn and hypothesis are outside rule 8 with no recorded approval → **partly, minor**
  (installed by the orchestrator at setup; scikit-learn 1.5.2 is the frozen forecast package's own extra).
- A-M4 run rows hold only Brier/BSS/CRPS sums; reliability/ECE, AP, FSS, rank histograms, spread-skill are
  coded and tested but not produced by any run; no aggregator → **confirmed, major**.
- Minor, confirmed: DATA_NOTES used the US test fires' NIROPS survey times (metadata, no outcomes); no install
  recipe; Pillow undeclared; `program/LEADERBOARD.md` links a missing file; equal cells across baselines only
  checked within a row; METRICS spread-skill range needs n, "17 windows" is approximate.

## Fix status

Fixes are being made on the track branches with a regression test each; this section is updated at merge.
