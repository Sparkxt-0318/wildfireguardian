# Is the fair opponent's best buffer width a spike or a plateau?

*Method proposed by the loop (critic #23, 2026-09-06; row WFG-127), run
2026-09-08. Artifact:
`data/processed/present_perimeter_buffer_shape_uiseong_andong_2025.json`.
Registry prefix: `ppshape_uiseong_`.*

## 1. The question, and why it was worth a run

`docs/present_perimeter_arm.md` §4 measures the fair opponent — a router that
refuses every node within a fixed buffer of the fire's **present** perimeter and
uses no spread model at all — at five buffer widths: **250, 500, 1000, 2000,
3000 m**. The 1 km row scored best, and three surfaces then described that peak
as a **spike rather than a plateau**, from which the booth script concluded that
an operator could not know the right width on the day.

The grid cannot support that. The two neighbours of 1 km are each a **factor of
two** away, so nothing in the five points separates a spike at 1 km from a
shoulder spanning roughly 800 m to 1.5 km — and a shoulder that wide is exactly
what an operator *can* aim at. This run adds the three widths that were missing
from the gap the claim was about: **750, 1250 and 1500 m**.

## 2. Method

The same runner, `scripts/run_present_perimeter_arm.py`, with a new additive
flag:

```
python scripts/run_present_perimeter_arm.py --sweep-extra-m 750,1250,1500 \
  --out data/processed/present_perimeter_buffer_shape_uiseong_andong_2025.json
```

`--sweep-extra-m` **adds** widths to the five-point grid and defaults to empty,
so a default run is unchanged and still reproduces the committed artifact. The
output goes to a **separate file**: no committed artifact was modified
(CHARTER §3 rule 2), and `data/processed/present_perimeter_arm_uiseong_andong_2025.json`
still holds exactly the five widths it always held.

Everything else is held fixed and comes from the committed inputs: the canonical
slope 60 m / DiGraph timing model, `p_cut` 0.5, the 600-minute budget, the
`walk_out` origin rule, the hash-verified snapshot walk graph, the committed
hazard `npz` and the committed refuge snapshot. No retraining, no
re-acquisition, no network (CHARTER §3.11 untouched). The run refuses to write
unless it first reproduces the committed canonical arm exactly, which it did.

**The control that makes the two grids comparable.** The run recomputes all five
old widths as well as the three new ones, and every cell of all five —
`recovered_of_forecast_only`, `already_safe_broken`, `safe_total`,
`failed_enters_hazard`, `failed_unreachable`, `failed_over_budget` — comes out
**identical** to the committed artifact. That is checked mechanically by
`tests/test_buffer_shape.py::test_the_five_shared_widths_reproduce_cell_for_cell`,
because three new points are only worth reading beside five old ones if the
five old ones land in the same place.

## 3. Result: it is a shoulder, not a spike

Eight widths, one fire, 368 scanned origins. The three new rows are in **bold**.

| buffer | recovered of 91 | already-safe broken | safe total | walks into the fire | no route | too slow |
|---|---|---|---|---|---|---|
| 250 m | 12 | 0 | 275 | 91 | 0 | 2 |
| 500 m | 23 | 2 | 284 | 80 | 2 | 2 |
| **750 m** | **88** | **3** | **349** | **3** | **3** | **13** |
| 1 km | 86 | 4 | 345 | 3 | 4 | 16 |
| **1250 m** | **59** | **4** | **318** | **4** | **3** | **43** |
| **1500 m** | **46** | **4** | **305** | **4** | **3** | **56** |
| 2 km | 19 | 7 | 275 | 5 | 8 | 80 |
| 3 km | 24 | 4 | 283 | 3 | 9 | 73 |

Three things the denser grid says that the five-point grid could not.

**(a) The top is a shoulder, and 「spike, not a plateau」 is withdrawn.** 750 m
and 1 km score **349** and **345** — four origins apart out of 368, on a grid
whose own step is 250 m. That is a flat top two sampled points wide, not a
single peak. The withdrawal is registered as **WC-011** in
`docs/auto/withdrawn_claims.json`.

**(b) The shoulder is not symmetric, and that is the operationally useful part.**
The left edge is a cliff and the right side is a ramp: 500 m → 750 m moves the
safe total from **284** to **349**, while 1 km → 1250 m → 1500 m → 2 km walks it
down **345** → **318** → **305** → **275**. The failure columns say why, and
they are the same two regimes §4 of the arm document already named: too thin and
the fire grows past the buffer (**91** and **80** origins walk into it at 250 m
and 500 m); too thick and the detour outlives the walker (**43**, **56** and
**80** origins arrive past the 600-minute budget at 1250 m, 1500 m and 2 km).
So an operator who guesses **too thin** loses far more than one who guesses
**too thick** by the same distance. 「You cannot know which width is right」 was
the wrong lesson to draw; 「err thick」 is a lesson this grid does support, for
this fire.

**(c) It runs against this project, and that is why it is here.** 750 m scores
**higher** than the 1 km the committed headline uses. The fair opponent is
therefore **stronger** than the committed artifact reports, and the forecast's
margin over it on this fire is **smaller** than the committed margin: **5**
origins at 750 m against **9** at 1 km. The margin numbers stay in this document
and in the artifact; they do not go to a judge-facing surface while **NH-032**
and **NH-034** are open.

## 4. What this does NOT show

- **It is one fire, one region, one hazard realisation.** Uiseong–Andong 2025.
  Nothing here says the shoulder sits at 750 m–1 km on a different fire, in
  different terrain, or under a different wind. The width is still a free
  parameter that no data in this repository chooses **in advance**.
- **The grid is still coarse.** Its finest step is 250 m. It can now say the top
  is at least two sampled points wide; it cannot locate the maximum, and the
  difference between 349 and 345 is well inside what a finer grid could reorder.
- **It does not make the buffer knowable on the day.** Knowing that a shoulder
  exists **after** the fire is not knowing where it is **during** one. What
  changed is narrower and stated exactly: the repository may no longer say the
  five-point grid showed a spike, and may no longer rest 「you cannot know」 on a
  shape the grid never resolved.
- **It measures no forecast error.** As with every row of the fair-opponent
  experiment, the forecast-aware arm is scored on the **same** hazard field it
  plans on, so every margin here is what a **noiseless** forecast would buy over
  a present-perimeter policy — an upper bound, not what this project's own model
  buys. That difference is still unmeasured, and it is what WFG-125 exists for.
- **It does not revisit the origin-rule question.** The `walk_out` rule is the
  primary one throughout; the strict-rule comparison lives in
  `docs/present_perimeter_arm.md` and is unchanged by this run.

## 5. What changed on the surfaces

| surface | before | after |
|---|---|---|
| `README.md` | 「sweep 안에서 고원이 아니라 뾰족한 봉우리」 | states the eight-point grid and the shoulder |
| `docs/present_perimeter_arm.md` §4 | 「The 1 km row is a spike, not a plateau」 | points at this document, states the shoulder |
| `docs/fair_opponent_line.md` §3 | the grid cannot say which shape it is | the denser grid says: a shoulder |
| `docs/auto/DEMO_SCRIPT_5MIN.md` 3막 | 「뾰족한 봉우리인지 넓은 고원인지 가리지 못합니다」 | it is a shoulder; the thin side is the dangerous side |
| `docs/auto/JUDGE_QA.md` Q37 | 다섯 가지 · 구분할 수 없습니다 | 여덟 가지 · 어깨 모양 |
