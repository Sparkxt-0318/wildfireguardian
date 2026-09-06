# The fair-opponent line — what every judge-facing surface says beside the 91

**Row:** WFG-121 (the author's own, 2026-09-06: 「Keep the headline, add the fair-opponent
line」). **Method proposed by:** the author; the buffer reading below is the loop's.
**Status:** the half that no open decision changes is shipped here. The margin half is
**held** until the author answers NH-032.

## 1. What this file is for

`docs/auto/DEMO_SCRIPT_5MIN.md` 3막, `docs/auto/JUDGE_QA.md` Q19 and the README's
multi-region table all carry the same contrast: of 368 scanned origins in 의성·안동 2025,
91 reach a refuge **only** on the time-aware route. The author's instruction is that this
headline keeps its place and gains the sentence that makes it fair. This file is the one
place that says what that sentence is, so the surfaces quote a single source instead of
each other.

## 2. The sentence that ships today, and why it carries no margin

> The 91 is measured against a **fire-blind** control. The comparison against a router
> that avoids where the fire **is** has now been run and is published in the repository
> (`docs/present_perimeter_arm.md`). Which of two defensible ways to build that opponent
> the project reports is the author's open decision, so no single margin figure is spoken.

Both clauses are load-bearing and neither depends on how NH-032 is answered:

- **Fire-blind is a property of the committed experiment, not of the new arm.** The
  control is `naive`, which consults no hazard at all, present or forecast
  (`src/wildfireguardian/routing/evacuation.py:270` 「Fire-blind shortest path to the
  nearest shelter」; `docs/real_roads_real_hazard.md:50`). Calling it 「the map that only
  sees now」 gives a weak opponent a strong name, and the percentage in the next breath
  then leans on that name. Critic #17 caught that wording; WFG-103 fixed it.
- **The comparison exists.** Until 2026-09-05 every surface said it had not been run. It
  ran (WFG-114, author decision NH-027 option A). A limitation that has been closed and is
  still spoken is a fabricated limitation, which CHARTER §3.5 forbids in the same breath as
  a fabricated result: it understates the work to a judge who could check.

## 3. The finding that survives either answer: **which** width works is not knowable on the day

The present-perimeter opponent needs a width — how far beyond the burning edge to refuse.
Nothing in the problem chooses one, so `scripts/run_present_perimeter_arm.py` swept five.
**The sweep lives in one place and this file is not it:**
[`docs/present_perimeter_arm.md`](present_perimeter_arm.md) §4 holds the full table, all six
columns, gated cell-by-cell against the artifact by
`tests/test_present_perimeter_arm.py::test_the_doc_s_sensitivity_table_matches_the_sweep`.
Read the counts there. This file states only what the surfaces are allowed to say about them.

**State it at the strength the data carries, and no more.** On this fire a *well-chosen* fixed
buffer nearly matches the forecast: at 1 km the committed arm reaches 345 of 368 against the
forecast-aware arm's 354. So 「a fixed buffer cannot work」 is **false**, and this file said it
in its first draft — the lap's own independent reviewer struck it out. What is true, and it is
narrower:

- **The safe total is a spike, not a plateau** (275 / 284 / **345** / 275 / 283 across
  250 m → 3 km). Move off the best width in either direction and the arm loses ground fast.
- **The two ways it loses are different.** Too thin and routes walk through ground that is
  alight before they cross it; too thick and the detour either outruns the evacuation window
  or walls the refuges off entirely.
- **Nothing on the day tells you which width you are on.** The best width here is a property
  of this fire, this road network and this departure time. And the two defensible builds of
  the same opponent do not even agree on it: the committed arm's best is 1 km, the parked
  arm's is 500 m (§4).

That last point is the argument, and it needs no answer from you: a policy whose quality turns
on a parameter chosen after the fact is not a policy an operator can run. **It is a claim about
this fire only** — one region, one ignition, one departure time — and §5 says why it cannot yet
be widened.

⚠ **Two coincidences of value in that table, named so nobody reads them as one number.**
The 250 m burn count `pp_uiseong_w250m_burns` is 91, and that is *not* the headline's 91
(`mr_uiseong_future_aware_only_safe`); they are different quantities that happen to be equal.
The same is true of the two 80s — `pp_uiseong_w500m_burns` is a burn count at 500 m and
`pp_uiseong_w2000m_late` is a late-arrival count at 2 km.

## 4. What this file corrected in the brief it was given

Critic #22 (2026-09-05T2330Z) instructed the next lap that the buffer counts above are 「the
half no answer changes」. **That is not quite true and the check is cheap**, so it is
recorded here rather than assumed: the parked lap's artifact on `auto/red/20260905T2248Z`
contains its own sweep, and under its opponent the same widths distribute their failures
differently — its wide buffers strand people by refusing departure and by walling every
refuge off, where the committed arm records them as late arrivals, and the two arms do not
agree on which width comes off best — the committed arm's is 1 km, the parked arm's is 500 m.
(Four of the five widths are shared between the two sweeps; neither swept exactly the other's
set.) So the **counts** are convention-dependent like the margin is, which is why §3 quotes
none of them and sends the reader to the one gated table instead.

What is convention-independent is the weaker claim §3 makes: **both** arms show a spike rather
than a plateau, and **both** say a well-chosen fixed buffer nearly matches the forecast — the
parked arm's best width reaches within a handful of origins of the same forecast-aware total.
That is the honest version, and it is less flattering than the one this file first wrote.

This is filed as information on NH-032 rather than as an argument with either lap.

## 5. What this does not show

- **No margin, by choice.** Nothing here says what the forecast is worth against the
  present-perimeter opponent. That number is NH-032's and both candidate answers are in
  that entry.
- **Both candidate margins are upper bounds anyway.** The forecast-aware arm plans on the
  same hazard field it is graded against, so it carries no forecast error; what it measures
  is what a *perfect* forecast buys. This project's real model buys less, by an amount no
  run has measured (WFG-125).
- **One region, one ignition, one departure time.** The sweep is a sensitivity check on a
  single run of 의성·안동 2025, not evidence that any width generalises to another fire —
  and §3's operational conclusion is bounded the same way. That an operator cannot know the
  right width in advance is argued *from this fire*; no run has tested it on a second one.
- **⚠ The shape inherits the oracle, exactly as the margin does.** Every column of the sweep
  is graded against `hazard_uiseong_andong_2025.npz`, the same simulated field the
  forecast-aware arm plans on. So §3's finding is no more externally grounded than the number
  it stands in for: it is a statement about this model's field, not about the fire that burned.
  Grading the sweep against the observed FIRMS burn footprint instead is what would close that,
  and no run has done it. Raised by this lap's independent reviewer under `mandela`.
- **The spoken 3막 line is unchanged.** Adding a sentence to it would move the registered
  `demo_pace_*` allocation, which CHARTER §3.2 forbids editing; the spoken half of WFG-121
  needs a new pace tag and is left for the lap that does WFG-100's re-allocation.
- 「Safe」 is the committed definition — reached a refuge without standing on a cell at
  p ≥ p_cut while it was there — and not survival.

**Sources:** `data/processed/present_perimeter_arm_uiseong_andong_2025.json` (the sweep),
`docs/present_perimeter_arm.md` (the arm's own method and withdrawals),
`docs/auto/NEEDS_HUMAN.md` NH-032 and NH-034 (the open decision),
`docs/real_roads_real_hazard.md` (the committed 91 and its control).
**Gate:** `tests/test_fair_opponent_line.py`.
