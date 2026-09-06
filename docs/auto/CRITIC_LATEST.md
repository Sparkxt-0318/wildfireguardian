# CRITIC_LATEST — critic #23, 2026-09-06

Window `9cc973b..de7bd0a` on `auto/dev` — four commits, one of them a real build lap (WFG-121). Verified here
rather than read from the reports: `gates.py --mode full` **ALL GREEN** at `de7bd0a` (`1545 passed, 62 skipped`,
cold, 302.5 s, against critic #22's cold `1535 / 62`, like for like), `--assert-head` green, all **68**
consecutive push pairs in the 24-hour window pass `--assert-reported`, every dev report of the last 24 h carries
a `Reviewed by:` line (eight of eight), and the five `auto-gates` runs
in this window are all `success`, the newest of them at this head. **No red run sits behind a green report, so there is no gate finding this lap.**

## fix-before-next-row

**One item, and it is fifteen minutes of prose with no run and no new number: WFG-127's half (i).**

Two surfaces assert a shape their evidence cannot resolve:

- `docs/fair_opponent_line.md` §3 — 「The safe total is a **spike, not a plateau** (275 / 284 / **345** / 275 /
  283 across 250 m → 3 km)」 and 「Move off the best width in either direction and the arm loses ground fast」.
- `docs/auto/DEMO_SCRIPT_5MIN.md` 3막 — 「**어느 폭이 맞는지는 그날 알 수 없고**, 같은 실험의 두 가지 구현조차
  최적 폭을 서로 다르게 답합니다」. This is the sentence the student says out loud at the booth.

The sweep is `data/processed/present_perimeter_arm_uiseong_andong_2025.json` → `buffer_sensitivity`, read cell
by cell by this critic: **five** widths, 250 / 500 / **1000** / 2000 / 3000 m. The winner's nearest measured
neighbours are a **factor of two** away on each side. Nothing in the run separates a spike at 1 km from a
plateau spanning roughly 800 m to 1.5 km — and a plateau that wide is exactly the thing an operator **can** aim
at, which is the opposite of the operational conclusion. The second leg fails the same way: two coarse grids
landing on 1 km and 500 m is what a broad optimum produces, not evidence of unknowability.

**What to do, and only this:** on both surfaces, state the grid (five widths, the neighbours are 2× away) and
narrow the claim to what five points support. Do not run anything. Do not add a number. Do not touch §4's
gated table, which is correct and lives in `docs/present_perimeter_arm.md`. Then **claim WFG-007.**

The run half — adding 750 / 1250 / 1500 m to the existing `scripts/run_present_perimeter_arm.py` sweep,
routing only on committed inputs, registered additively — is WFG-127 (ii) and is its own lap, behind the
printables.

## Then take WFG-007, and nothing is in front of it any more

`docs/auto/finals/` holds two `.md` files and one screenshot folder; `find docs/auto -name '*.pdf'` returns
nothing on the **eighth** day. R7 and half of R9 are this row alone; readiness has read 4 of 11 for **eight**
consecutive critic laps. WFG-007 is now first on `docs/auto/DIRECTION.md` **and** first in the backlog table
(this lap's one row move), so neither route sends you elsewhere.

**Why the previous top row is spent, so you do not re-take it:** WFG-121's (a) shipped at `a182cc0`; its (b) is
`blocked(NH-032)`; its (c) — the spoken 3막 line — needs a new `demo_pace_*` allocation because CHARTER §3.2
forbids editing the registered one, and that is WFG-100's machinery and a different row.

## Still binding from critic #22, unchanged

1. **Do not put 9, 27, 5 or 19 on any judge-facing surface** while NH-032 is open. **Settled this lap:** the
   do-not-say list in `JUDGE_QA.md` Q19 is the one deliberate exception and is not a violation — the docstring
   of `tests/test_fair_opponent_line.py::test_no_contested_margin_reaches_the_booth_script` states that the
   list lives there. One defect in it was fixed here: it forbade picking 「어느 하나만」 (only one of them),
   which permitted reciting all three. It now forbids all of them. The 0020Z lap's escalation is closed.
2. **Do not delete or force-push `auto/red/20260905T2248Z`.** It is the only copy of the escape analysis and
   of the 265-vs-263 control question.
3. **NH-032, NH-033, NH-034 are open** and NH-031 was an ID collision; read the banners before applying any
   `NH-031: …` reply.

## The three open defects on the judged screen, which one rebuild closes

Re-tested here on a clone deepened past the depth-50 boundary (WFG-119), not inherited:

- `web/finals.html` prints `built at commit 41498ef`; `git merge-base --is-ancestor 41498ef HEAD` exits **1**.
  Fourteen windows. **WFG-115.**
- The same screen prints `n_entries":326`; `docs/NUMBERS.json` holds **383** entries, counted here. **WFG-113**
  (the value is hand-typed and ungated) and **WFG-117** (the Q&A bank's T0 question about it).

## New this lap

- **WFG-127** (P0) — the buffer grid, above.
- **WFG-126 raised P1 → P0** (a priority change, not a position move; critic #22's WFG-104 precedent).
  `paper/manuscript.md:386` tells a reviewer the fair-opponent arm 「is specified in the project backlog and
  scheduled after this sprint」. It ran on 2026-09-05 and its artifact is committed. This window's own diff
  wrote the rule that makes this a violation rather than staleness — `docs/fair_opponent_line.md:32-35`,
  「A limitation that has been closed and is still spoken is a fabricated limitation, which CHARTER §3.5
  forbids in the same breath as a fabricated result」 — applied it to the booth script, and left the twin
  surface saying the closed thing. **This is the paper routine's row, not a dev lap's** (`paper/` is §12's).
- **JUDGE_QA Q36 and Q37**, both marked 근거 없음. Q36 is the oracle question (WFG-125): the forecast-aware arm
  plans on the field it is graded against, so every margin in the dispute is a **perfect-forecast** bound, and
  the honest booth answer today is 「맞습니다」 followed by nothing. Q37 is the buffer-grid question above.

## What I did not find

No red gate, no red CI run, no missing report, no uncertified push, no fabricated number in the window's new
prose. Every numeric claim in `docs/fair_opponent_line.md` §3 was checked against the artifact and every one
holds: 345 / 354 at 1 km, 91 burns at 250 m, 80 late at 2 km, the 275 / 284 / 345 / 275 / 283 series, and both
value collisions the file flags. `factchk`: the window's new prose makes **no** new claim about the world — no
agency figure, no citation, no external statistic — so there was nothing to verify outside the repository.
