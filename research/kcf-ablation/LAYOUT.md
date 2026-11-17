# kcf-ablation LAYOUT (frozen before any cell is filled)

Frozen on 2026-11-17, Main at `a697d14` (PR #189; contains #188). Hard stop: Sat 21 Nov 2026, 18:00 Shanghai.
Nothing in §2–§6 changes after the first cell is written. A mistake found later is corrected by an **amendment** at the
bottom (dated, with the reason), never by editing this text. Deliverables: `LAYOUT.md`, `TABLE.md`, `cells.json`, `READING.md`.

## 0. What "finals submission" means here, and two things the user should know

* Papers read: **P1** "Fire: Finding Individual Routes for Evacuation Under Flame and Thermal Exposure Constraints"
  (Preprints 202610.1837.v1, 20 Oct 2026) and **P2** "SMOKE: Spread Modeling with Optimized Kernel Estimation" (the file
  `SMOKE_FINAL_PAPER.pdf`). The brief says "the finals paper" (singular) and two files were attached; I treat both as the
  submission and use P1 for routing fires and P2 for forecast fires.
* **P1 and P2 do not describe the measured reach margin, the heat closure, the thermal-dose budget or the deadline field.**
  Those components exist only in the repository (`research/kcf-margin`, `kcf-heat`, `harness-2026-11/F-3.1`, `kcf-replay`),
  listed for the talk in `research/kcf-evidence/TALK_NUMBERS.md`. "The full system as submitted" is therefore defined as the
  repository at Main `a697d14`, not as the system P1 evaluates. P1's own system is the router row's base (§3, row 6).
* `research/kcf-abstain/FIRES.md` does not exist at `a697d14` (checked in the tree, all remote branches and PRs #182–#189).
  The fire list below is built from P1, P2 and the repo registries.

## 1. Input versions (never pooled; a cell names its version; a row that mixes versions across columns carries a footnote)

| id | version | where | places / cases |
|---|---|---|---|
| V1 | P1 final panel, frozen try02 inputs, horizon 3,600 s, 20 designed missions from 5 regions | release asset `WFG-evaluated-routing-inputs-20261015.zip` (SHA-256 `d7e0a5fc…2202`, verified; fetched by `tools/fetch_routing_inputs.py`); results `research/routing/` | place = mission origin node; case = mission (both repetitions agree) |
| V2 | planner 1-hour panel, six recorded caches, 2025 only | `planner/cache/` (6 files); F-3.1 and kcf-heat results | place = planner origin (530; 508 have a leave-by); case = route-check job (9,722) |
| V3 | multi-hour F-DYN HEADLINE scenarios, 48 packets, 2025 only | `research/kcf-heat/data/multihour/` | place = origin (286 with a leave-by) |
| V4 | kcf-replay, 25 Mar 2025 12:00–24:00 KST, 5 h / 8 h horizons | `research/kcf-replay/` | place-hour (174 places × 13 hours) |
| V5 | corridor-router v8 campaign, 273 requests, permissive missing-input policy | `research/kcf-evidence/sources/corridor-router-v8/` | case = request |

The input build for V1/V2 is the same frozen packet set (forecast c651); V2 and V3 use different horizons and place sets
from V1 and from each other. Numbers from different versions are shown on separate lines and never added or averaged.

## 2. Columns (the frozen fire list)

A fire is a column if it appears as a case, place, held-out test fire or calibration fire in P1, P2, or the repo
registries (`LATEST_INPUT_FREEZE.json`, `research/kcf-margin/numbers.json`, `research/next-combined/**/RESULTS.json`,
`docs/NEXT_PLAN.md`). Columns with the same input version and no road network are grouped only where stated.

| col | fire | registry id | road graph and places? | versions present |
|---|---|---|---|---|
| F1 | Gyeongbuk 2025 (Uiseong–Andong and Yeongdeok graphs) | KFS_01 | yes | V1 (8 missions), V2, V3, V4 |
| F2 | Uljin 2022 | KFS_02 | yes | V1 (4), V5 |
| F3 | Hongseong 2023 | KFS_05 | yes | V1 (4), V5 |
| F4 | Miryang 2022 | KFS_11 | yes | V1 (4), V5 |
| F5 | Caldor 2021 | — | graph not in the fetched inputs | V5 (3 cases) |
| F6–F11 | Wapiti 2024, Goat, Lava, Red Rock, Pioneer, Fish Creek (US held-out forecast cohort, 273 windows) | `docs/NEXT_PLAN.md`; `canonical-summary-691cc162/RESULTS.json` | no | forecast scoring only |
| F12–F14 | Sancheong (KFS_04), Ulju (KFS_06), Bukgu (KFS_13) | `research/forecast/ABLATION_RESULTS.md`; `NEXT_PLAN.md` | no | forecast scoring only |
| P-A | the 28 GOFER fires of the margin calibration (names in `research/kcf-margin/derived/gofer_reach.csv.gz`) | `kcf-margin/numbers.json` | no | margin calibration only |
| P-B | the 488 NIROPS allowlist incidents of the margin check | `kcf-margin/numbers.json` | no | margin check only |
| P-C | the SMOKE 44-event catalog (15 Korean, 29 US; 25 development fires) | P2 App. B.1 | no | training / validation only |

F1–F4 are listed first in `TABLE.md`. P-A, P-B and P-C are populations (many fires, one input version, identical cells);
their cells are written once and carry the member count. No column is dropped; columns without road inputs are all
NOT RUN with that reason.

## 3. Rows (each: the full system with one change)

"Full system as submitted" (row 1) = forecast c651 hazard packets → deadline field with heat closure `cert_heat` and the
thermal-dose budget (TDU, shelter stay counted, budgets 92 / 105 / 290 reported side by side, none chosen) → leave-by; plus
the contact-first (corridor) router for routes (P1's "proposed implementation"). Row 1 is the base; every other row's
"changes" are measured against it on the same version.

| # | row | what changes | the committed contrast that can fill it (only if its base matches) |
|---|---|---|---|
| 1 | full system as submitted | nothing | F-3.1 RESULTS; kcf-heat `routing_1h`, `tdu_1h`, `multihour`; `research/routing` |
| 2 | forecast → persistence | hazard packet keeps only fire already burning (`PacketModel(present_only=True)`); no forecast ignitions | none committed for routing |
| 3 | forecast → measured reach margin | hazard = known fire area + R(h) closure (kcf-margin R, kcf-replay MEASURED rule) | none with a forecast base |
| 4 | heat closure off | `cert_heat` → `cert`, dose budget kept | kcf-heat compares `cert` with `cert_heat` with dose **off**; does not match |
| 5 | thermal-dose budget off | `cert_heat` + dose → `cert_heat` | kcf-heat C.4 (`tdu_1h`, `multihour`): matches |
| 6 | corridor router → reference router | contact-first router → resource-constrained A\* | `research/routing` (V1) |
| 7 | deadline field → recorded per-departure checks | field leave-by → latest checked departure on the recorded 10-min grid | F-3.1 `DEADLINES_per_origin.json`, `SUMMARY_final_70f70d7.json`; `tdu_1h` per-origin `recorded_deadline` |

Notes frozen with the rows:
* "Corridor router" is read as P1's proposed contact-first router. The separate `experimental/corridor-router-v8`
  (V5) has no reference-router arm in any committed file; it is listed only under V5 cells.
* Row 7: the recorded checks predate the heat closure and the dose budget, so against row 1 that arm differs in three ways.
  F-3.1's `cert` vs recorded contrast (field only) is given on a second line when row 1's base is not `cert`.
* The router in P1 has its own cumulative-exposure limit on the old 0.703 kW/m² law (200-execution ablation,
  `research/routing/final-input-ablation/`). It is a different component from the kcf-heat TDU budget and is cited
  under row 5 / V1 as a separate line, not as the row-5 value.
* Persistence in the forecast-skill sense (`research/next-combined/canonical-summary-691cc162/RESULTS.json`, Brier) is a
  forecast score, not one of the metrics below. It is quoted in `READING.md` only as context.

## 4. Metrics per cell (all three-part: value, status tag, source)

1. **Cases decided**: cases with a checked route or a proven no-route under the model, over cases in that version.
   Unresolved, timed-out, label-limit and AT_ISSUE-undecided cases do not count.
2. **Routes found**: cases with a checked route.
3. **Places whose leave-by changes** against row 1, on the same version: count over places with a leave-by in row 1;
   places that lose their leave-by are counted and also listed separately.
   *Leave-by* = latest feasible departure second: V1 uncapped exact in [0, H − dwell]; V2 exact, capped at the planner
   range [0, last offset], as kcf-heat; V3 the HEADLINE rule (latest second of the union over destinations, when the set
   starts at 0). Router rows that answer one departure have no leave-by: **NOT RUN (leave-by not produced)**.
4. **Median and largest change, seconds**: absolute difference over places counted in 3 only.
5. **Run time**: wall seconds of that arm, with host. Times from different hosts are not compared.

A cell may carry a different status per metric; the tag is attached to each value.

## 5. Status rules

* **RECORDED**: value copied or tabulated from a committed file; path cited. Tabulation, where needed, is by a script in
  this directory, committed, whose output is the cited value. A contrast counts only if its base is row 1 or differs
  from row 1 in exactly the one component of the row; otherwise the cell is not filled from it (it may appear in notes).
* **NEW RUN**: executed here, inputs from the repo or from the SHA-verified release asset in §1, one run ≤ 2 h wall,
  command and host stated, output committed under `research/kcf-ablation/runs/`.
* **NOT RUN**: with the reason. No cell from memory or estimate. Cells with a checked-file value that is not exactly the
  metric are NOT RUN for that metric.

## 6. Planned NEW RUNs (the only ones; frozen so none is chosen after seeing a result)

* **N1** (V1, F1–F4, 20 missions): field arms row 1, row 2 (`present_only`), row 4, row 5, from the frozen packets.
* **N2** (V2, F1): row 2 and row 4 over the six caches, using the kcf-heat runner with the one change.
* Rows 3 and 7 on V1 and row 6 leave-by are **not** planned; rows 3 reasons in §7.
* Any run exceeding 2 h wall is stopped and its cell is NOT RUN.

## 7. Reasons fixed in advance for not running row 3 (forecast → margin)

The frozen margin rule exists for 5 h and 8 h horizons (`kcf-margin/numbers.json`; `kcf-replay/MEASURED_RULE.md`, linear
below 5 h ASSUMED). The forecast arm exists at a 1-hour horizon on different issue times (V1, V2) or as retrospective
scenarios (V3); V4 has no forecast arm. No frozen rule maps R to a 1-hour hazard, so a run would need a rule chosen
after the full-system outputs are known. Row 3 is NOT RUN on every fire unless the user supplies a frozen rule.

## Amendments

(none)
