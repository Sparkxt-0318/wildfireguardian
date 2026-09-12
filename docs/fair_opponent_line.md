# The fair-opponent line — what every judge-facing surface says beside the 91

**Row:** WFG-121 (the author's own, 2026-09-06: 「Keep the headline, add the fair-opponent
line」). **Method proposed by:** the author; the buffer reading below is the loop's.
**Status:** the half that no open decision changes is shipped here. The margin half is
**held** until the author answers NH-032.
⚠ **Updated 2026-09-12:** NH-032 is **closed** (author, option C) and NH-034 is closed (option
B). The margin half now ships: §2 carries it, from the budget-capped arm. The screen is not
touched and 91 stays the headline everywhere (NH-034 B).

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

⚠ **Superseded 2026-09-12 — the last clause of the sentence above is no longer true.** NH-032 was
closed by the author on 2026-09-12 with option C, verbatim: 「C. Replace it with the parked
version (margin 27, budget-capped, refuses to move people inside the margin).」 The sentence
that ships from today is this one, and the numbers in it are `ppb_*` registry keys re-derived
from `data/processed/present_perimeter_arm_budgeted_uiseong_andong_2025.json`:

> The 91 is measured against a **fire-blind** control. Against the fair opponent — a planner
> that refuses what is burning **now** plus a 1 km margin, runs the same router under the same
> 600-minute budget, and tells anyone inside the margin not to move — the ladder on 의성·안동
> 2025 is **265 / 327 / 354** of 368 (fire-blind / present + 1 km / forecast-aware;
> `ppb_safe_naive`, `ppb_safe_1km`, `ppb_safe_forecast`), so the forecast's margin is **27**
> origins of 368 (`ppb_gap_1km`), and the opponent recovers **79** of the 91 (`ppb_recovered_1km`).
> That margin is an **upper bound**: the opponent never re-plans, and the forecast-aware arm
> is graded on the very field it planned on, so it carries no forecast error.

Three things bind that sentence, and they are the same three that bound the number before it
was chosen:

- **It is the margin at the author's named width, 1 km, not at the opponent's best width.** The
  same run's sweep finds 500 m stronger (349 safe, `ppb_safe_present_best`), where the margin is
  **5** (`ppb_gap_best`). That width was chosen after the fact by scanning outcomes, so 5 is a
  maximum over the six widths measured and is non-increasing in how finely anyone searches — a
  width added to the grid can only tie or beat the incumbent (WFG-201). This build has **not**
  been run at 750 / 1250 / 1500 m, so whether the pruned-graph arm's best width moves here is
  unmeasured. When the 27 is spoken, the 5 and its qualifier travel with it.
- **The pruned-graph build is not withdrawn.** At the same 1 km it reads **9**
  (`pp_uiseong_forecast_margin_1km`), because it has no time budget and lets an origin walk out
  of the buffer; it stays in the repository as the second, labelled arm
  (`docs/present_perimeter_arm.md`). 9 and 27 are two opponents, not two measurements of one,
  and neither number is spoken as *the* margin except the 27.
- **Where it is said.** Per NH-034 B the fair opponent is a 「반론에 대한 답」 card in the Q&A bank
  (`docs/auto/JUDGE_QA.md` Q19) and this page; the finals screen is not touched and the spoken
  3막 line is unchanged (§5).

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

## 3. The finding that survives either answer: the failure changes **kind** across widths, and this grid cannot say whether a width could be chosen in advance

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

- **The two ways it loses are different, and that change of kind is the finding.** Too thin and
  routes walk through ground that is alight before they cross it; too thick and the detour
  either outruns the evacuation window or walls the refuges off entirely. Both constructions
  of the opponent show it, and the manuscript's §4.5 states it in the same terms.
- **The grid was widened on 2026-09-08, and it now says what shape the top is.** The
  committed sweep is 250 m, 500 m, 1 km, 2 km, 3 km, so the best width's nearest measured
  neighbours were a factor of two away on each side and the run held a *single point* in the
  region a 「which width」 claim is about. WFG-127 added **750 m, 1250 m and 1500 m** on the
  same code and the same committed inputs, with all five original widths reproducing cell for
  cell. The answer is a **shoulder, not a peak** — 750 m and 1 km are four origins apart out
  of 368 — and the shoulder is **asymmetric**: the thin side is a cliff and the thick side a
  ramp. So the honest statement is no longer 「the grid cannot tell」 and never was 「you
  cannot know」; it is 「a band exists, we found it *after* the fire, and the thin side is the
  dangerous one to be wrong on」. Method, table and limits:
  [`docs/present_perimeter_buffer_shape.md`](present_perimeter_buffer_shape.md); the
  committed five-width counts stay at
  [`docs/present_perimeter_arm.md`](present_perimeter_arm.md) §4.
- **⚠ And the band was found by scanning outcomes, so it is a maximum over the
  measured grid: adding widths to this grid can only strengthen this opponent
  and can only shrink whatever margin the forecast is reported to hold over it.** Nothing in
  the problem chooses a width, so the sweep hands the opponent the best width it
  finds — after the run. A width added to the grid can only tie or beat the
  incumbent, so the opponent's best score is non-decreasing and the margin
  non-increasing in how finely anyone searches, holding this fire and this
  scoring fixed. The 2026-09-08 refinement is the worked instance and it moved
  the best width off 1 km; the property, the values and what bounds it does
  **not** carry are in
  [`docs/present_perimeter_buffer_shape.md`](present_perimeter_buffer_shape.md)
  §4. This file still quotes no margin (§5), and the qualifier is owed to
  whichever margin NH-032 settles on, not to a particular one.
- **What is measured, and is not a question of resolution, is that the two defensible builds
  disagree about which width is best** — the committed arm's is 1 km, the parked arm's is
  500 m (§4) — and that the best width here is in any case a property of this fire, this road
  network and this departure time.

That last point is the argument, and it needs no answer from you. It is **not** 「a present-perimeter
policy cannot be run」; it is that this project has not shown a width can be chosen ahead of time,
on one fire, where its own two builds of the same opponent answer differently. **It is a claim about
this fire only** — one region, one ignition, one departure time — and §5 says why even that cannot
yet be widened.

⚠ **Narrowed 2026-09-06 (WFG-127 (i), critic #23's finding, carried by critic #24).** This section
previously called the 1 km safe total a spike rather than a plateau <!-- forbidden-ok: wc011-buffer-width-is-a-spike-en -->, said that nothing on the day
tells you which width you are on, and quoted the five safe totals to support both.
*(The withdrawn sentences are described here rather than quoted, so that the gate below can ban
their exact spellings without this paragraph having to dodge its own rule on a line break.)* Neither sentence is
recoverable from a five-point grid whose spacing is a factor of two, and the counts belong to §4 of
the other document. Nothing was measured again and no committed value moved; the claim was cut back
to what the run carries. The withdrawn wording is recorded here rather than deleted (CHARTER §3.5).

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

What is convention-independent is the weaker claim §3 makes: **both** arms show the same change of
kind across the widths — thin buffers send people through burning ground, wide ones strand them —
and **both** say a well-chosen fixed buffer nearly matches the forecast; the parked arm's best
width reaches within a handful of origins of the same forecast-aware total.
That is the honest version, and it is less flattering than the one this file first wrote.

⚠ **Updated 2026-09-08 (WFG-127 (ii)).** This paragraph used to end by saying that neither arm's
grid was fine enough to tell a peak from a plateau. That is now true of the **parked** arm only.
The committed arm's grid was made finer — 750 m, 1250 m and 1500 m — and it answers: a shoulder,
asymmetric, with the thin side the dangerous one (§3, and
[`docs/present_perimeter_buffer_shape.md`](present_perimeter_buffer_shape.md)). The parked arm was
**not** re-run, so nothing here says the two builds agree about the shape; they are still measured
to disagree about the best width, and that disagreement is untouched by this lap.

This is filed as information on NH-032 rather than as an argument with either lap.

## 5. What this does not show

- **No margin, by choice.** Nothing here says what the forecast is worth against the
  present-perimeter opponent. That number is NH-032's and both candidate answers are in
  that entry.
  ⚠ *Superseded 2026-09-12:* NH-032 is closed (option C) and §2 now states the margin from
  the budget-capped arm. The bullet above is kept as the record of why this page carried none
  for six days.
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
