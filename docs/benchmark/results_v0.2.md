# K-SPREAD-2025 — results v0.2 (Stage 2: the proxy ceilings)

**Protocol: `docs/benchmark/K_SPREAD_2025.md` v0.1, frozen and unchanged.** This page adds
entrants under it; it does not amend it. v0.1's results and every convention behind them are
`docs/benchmark/results_v0.1.md`, which this page does not restate and does not supersede.
The entrant rule was pre-registered at `docs/benchmark/stage2_proxy_rules.md` **before any
field here was built**. Stage 2 brief: `docs/auto/briefs/K_SPREAD_STAGE2.md`; Stage 2 report:
`docs/auto/briefs/K_SPREAD_STAGE2_REPORT.md`.

## 1. What v0.2 adds, in one line

The protocol's two **proxy** entrants — E1 wind-cone (the G-DAPS class) and E2
Rothermel-family (the NIFoS class) — scored for the first time, as **ceilings**: the best
either method class could have done on 영덕 2025 under **any** wind.

## 2. What could not run, and is therefore absent rather than estimated

| not run | why |
|---|---|
| **F1 frozen-weather WFG** | needs `{fire}_era5.nc` to freeze the T0 weather. No ERA5 file for any fire exists on this machine. |
| **F2 mountain-weather WFG** | needs `data/raw/mountain_weather/` (git-ignored) and station coordinates, which `docs/mountain_weather_yeongdeok.md` §4 records the API does not return. |
| **F3 KMA-forecast WFG** | needs the 초단기/단기예보 archive under `data/raw/kma_forecast/`. Absent; the brief says record it as 「not run: input missing」, and that is what this is. |
| **forecast-track E1 and E2** | both need the wind observed at T0. It is not reachable here, and none was invented — see §3. |
| **5 of the 6 protocol §2 events** | unchanged from v0.1: only 영덕 has a committed observed detection stack. |
| **protocol §5's mean-over-events and worst-event** | one event scored. A mean over one event is that event. |

## 3. ⚠ Every Stage 2 row is a ceiling, and a ceiling is not a score

The wind at T0 is not on this machine. Rather than transcribe an extremum from a prose table
as though it were the wind field over the canvas, each proxy was **swept over 720 declared
wind settings** and the best-scoring setting was written as the entrant.

That makes both Stage 2 entrants **oracles**, and they are filed in the **hindcast track**
because choosing a wind by how well it matches the outcome is using an observation after T0.
What each row states is: **no wind would have let this method class do better on this fire.**
It does **not** state what the method scores, and the forecast-track E1 and E2 the brief
asked for are in §2's table as not run.

A ceiling is the one form of the comparison that is immune to 「you gave it the wrong wind」.
It is also, by construction, **generous to the proxies and to nobody else**: E0 and E3 were
not tuned against the observation and their rows are unchanged from v0.1.

## 4. How to read the three groups of rows

- **E0 persistence** (forecast track) — v0.1's baseline, re-derived here by the same scorer
  and byte-compared against its committed v0.1 artifact.
- **E3 WFG canonical** (hindcast track) — v0.1's committed field, likewise re-derived.
- **E1 / E2 oracles** (hindcast track) — new in v0.2, ceilings, per §3.

E1 and E2 differ by **exactly one term**: E2 multiplies the cone's rate by Rothermel's
upslope factor on the committed DEM (`stage2_proxy_rules.md` §2). Their gap is therefore a
measurement of what that slope term buys at 500 m on this fire, and nothing else.

## 5. What this page still cannot say

Everything `results_v0.1.md` §8's limits already say, and one more: a ceiling built by
searching against the observation tells you what a method class **could** reach, never what
an operator **would** have got. The number that would say that is a forecast-track proxy on
a real issued wind, and it is not run.

## 6. Results

_(appended by `scripts/benchmark/render_results_v0_2.py`; nothing above this line is edited after the run)_

_Run 2026-09-14T16:15:07Z at `caffe3a`; protocol `v0.1`; scorer `scripts/benchmark/score_kspread.py`, unchanged from Stage 1; artifacts `data/processed/benchmark/`; 10502 s._

### 6.1 Metrics 1 and 2, by track

The two tables are **not** to be read against each other (protocol §3). Every Stage 2 row is an **oracle upper bound**, not a score the method achieved — see §3.

**forecast track**

| entrant | horizon | ROC-AUC | IoU at p ≥ 0.5 | predicted positive | unscorable |
|---|---|---:|---:|---:|---:|
| E0 persistence | T0 + 3 h | 1.0000 | 1.0000 | 249 | 688 |
| E0 persistence | T0 + 5 h | 1.0000 | 1.0000 | 249 | 688 |
| E0 persistence | T0 + 8 h | 0.6329 | 0.2657 | 249 | 50 |

**hindcast track**

| entrant | horizon | ROC-AUC | IoU at p ≥ 0.5 | predicted positive | unscorable |
|---|---|---:|---:|---:|---:|
| E1 wind-cone oracle (upper bound) | T0 + 3 h | 0.9975 | 0.6501 | 491 | 688 |
| E1 wind-cone oracle (upper bound) | T0 + 5 h | 0.9952 | 0.4242 | 817 | 688 |
| E1 wind-cone oracle (upper bound) | T0 + 8 h | 0.9802 | 0.4286 | 1,257 | 50 |
| E1 wind-cone oracle (upper bound) [IoU-selected] | T0 + 3 h | 1.0000 | 1.0000 | 249 | 688 |
| E1 wind-cone oracle (upper bound) [IoU-selected] | T0 + 5 h | 0.9929 | 0.3744 | 998 | 688 |
| E1 wind-cone oracle (upper bound) [IoU-selected] | T0 + 8 h | 0.9784 | 0.4309 | 1,378 | 50 |
| E2 Rothermel-family oracle (upper bound) | T0 + 3 h | 0.9975 | 0.6451 | 497 | 688 |
| E2 Rothermel-family oracle (upper bound) | T0 + 5 h | 0.9943 | 0.3965 | 893 | 688 |
| E2 Rothermel-family oracle (upper bound) | T0 + 8 h | 0.9796 | 0.4277 | 1,302 | 50 |
| E2 Rothermel-family oracle (upper bound) [IoU-selected] | T0 + 3 h | 0.9992 | 0.8557 | 337 | 688 |
| E2 Rothermel-family oracle (upper bound) [IoU-selected] | T0 + 5 h | 0.9927 | 0.3694 | 1,010 | 688 |
| E2 Rothermel-family oracle (upper bound) [IoU-selected] | T0 + 8 h | 0.9781 | 0.4298 | 1,395 | 50 |
| E3 WFG canonical (leave-one-complex-out) | T0 + 3 h | 0.9990 | 0.8272 | 373 | 688 |
| E3 WFG canonical (leave-one-complex-out) | T0 + 5 h | 0.9990 | 0.6368 | 528 | 688 |
| E3 WFG canonical (leave-one-complex-out) | T0 + 8 h | 0.9791 | 0.3606 | 536 | 50 |

### 6.2 Metric 3 — arrival-time error at the road nodes (the one the protocol says matters)

Node set: every node of the canonical walk network (C5) — 8,443 nodes, identical for every entrant. Cell membership (A5); window = the entrant's own last surface. Signed error is model minus observation, so **positive is late**.

| entrant | track | entrant burns | both | median abs error | false-safe | false-safe rate | false alarms |
|---|---|---:|---:|---:|---|---:|---:|
| E0 persistence | forecast | 275 | 275 | 0.0 min | 1,497 of 8,168 | 0.1833 | 0 |
| E1 wind-cone oracle (upper bound) | hindcast | 2,042 | 1,501 | 83.7 min | 271 of 6,401 | 0.0423 | 541 |
| E1 wind-cone oracle (upper bound) [IoU-selected] | hindcast | 2,352 | 1,491 | 111.9 min | 281 of 6,091 | 0.0461 | 861 |
| E2 Rothermel-family oracle (upper bound) | hindcast | 2,054 | 1,506 | 84.5 min | 266 of 6,389 | 0.0416 | 548 |
| E2 Rothermel-family oracle (upper bound) [IoU-selected] | hindcast | 2,357 | 1,492 | 112.3 min | 280 of 6,086 | 0.0460 | 865 |
| E3 WFG canonical (leave-one-complex-out) | hindcast | 281 | 278 | 0.0 min | 1,494 of 8,162 | 0.1830 | 3 |

### 6.3 Metric 4 — decision shift on the 주건물

Buildings whose last-safe-departure class changes between the entrant's field and the observation-graded field, the committed time-aware policy with only the hazard changed. The observation puts **2,645** buildings in `closes_before_5h`, **1,261** in `closes_after_5h`, **190** in `never` and the rest `censored`; 「windows found」 below counts the buildings the observation says have a window that closes and the entrant does **not** call `censored` — the buildings an operator would have been warned about.

| entrant | track | buildings changing class | entrant more optimistic | closing windows found (of 3,906) | flagged where truth is censored | precision | recall |
|---|---|---:|---:|---:|---:|---:|---:|
| E0 persistence | forecast | 3,906 | 3,906 | 0 | 0 | — | 0.000 |
| E1 wind-cone oracle (upper bound) | hindcast | 3,062 | 1,235 | 3,001 | 1,078 | 0.736 | 0.768 |
| E1 wind-cone oracle (upper bound) [IoU-selected] | hindcast | 3,360 | 1,169 | 2,988 | 1,397 | 0.681 | 0.765 |
| E2 Rothermel-family oracle (upper bound) | hindcast | 3,110 | 1,231 | 3,008 | 1,115 | 0.730 | 0.770 |
| E2 Rothermel-family oracle (upper bound) [IoU-selected] | hindcast | 3,821 | 1,078 | 3,068 | 1,946 | 0.612 | 0.785 |
| E3 WFG canonical (leave-one-complex-out) | hindcast | 3,898 | 3,879 | 27 | 7 | 0.794 | 0.007 |


⚠ **Precision is what makes this row comparable and recall is what it measures.** 「precision」 is the share of the buildings an entrant flags (any class but `censored`) whose window the observation really does close; 「recall」 is the share of the observation's closing windows the entrant flags at all. An entrant that flags nothing has no precision to report and zero recall, and one that flags everything has recall 1 and the base rate for precision. Read the two together or neither.

### 6.4 What survives NOT knowing the wind, and the operating point that explains it

Metric 3's false-safe rate at **every** declared grid point, not only at the oracle's (`data/processed/benchmark/stage2_wind_sensitivity.json`). E3's rate is **0.1830** and E0's is **0.1833**.

| proxy | grid points with a defined rate | false-safe rate min / median / max | points beating E3 | points that call no node safe |
|---|---:|---|---:|---:|
| E1 wind-cone | 684 | 0.0000 / 0.0000 / 0.1162 | 684 | 36 |
| E2 Rothermel-family | 672 | 0.0000 / 0.0000 / 0.1162 | 672 | 48 |

⚠ **This is not 「a wind-cone always beats the model」, and reading it that way would be the mistake this section exists to prevent.** The proxies beat E3's false-safe rate at every wind because they burn far more of the network, not because they locate the fire better. Across the grid:

- **E1 wind-cone** burns 1,284 / 6,101 / 8,443 of the 8,443 nodes (min / median / max) and raises 303 / 4,329 / 6,671 false alarms. **E3 burns 281 nodes and raises 3.** Not one of the 720 grid points operates anywhere near that alarm budget.
- **E2 Rothermel-family** burns 1,285 / 6,166 / 8,443 of the 8,443 nodes (min / median / max) and raises 303 / 4,394 / 6,671 false alarms. **E3 burns 281 nodes and raises 3.** Not one of the 720 grid points operates anywhere near that alarm budget.

**So metric 3's false-safe rate is not comparable between entrants at different operating points**, and Stage 2 is the first entry that makes that visible: a field that burns the whole canvas has a false-safe rate of 0.0000 and no value at all. Stage 1 could compare E0 and E3 on it fairly only because both burn about 280 nodes. The rate belongs beside the false-alarm count, always — which is why every table above carries both, and why metric 4's precision/recall pair is the row that actually separates these entrants. **A change to protocol §5.3 is the author's call, not this lap's; v0.1 is frozen and was applied as written.**

### 6.5 The wind sweep behind the two oracles

Each proxy was built at every one of 36 × 20 = 720 declared grid points (`docs/benchmark/stage2_proxy_rules.md` §3) and the best-scoring point was written as the entrant. The spread across the grid is what 「the wind has to be roughly right」 costs.

| proxy | criterion | bearing | head rate | mean ROC-AUC | mean IoU |
|---|---|---:|---:|---:|---:|
| E1 wind-cone | max mean ROC-AUC (primary) | 100° | 100 m/30 min | 0.9910 | 0.5010 |
| E1 wind-cone | max mean IoU (secondary) | 130° | 100 m/30 min | 0.9904 | 0.6018 |
| E2 Rothermel-family | max mean ROC-AUC (primary) | 100° | 100 m/30 min | 0.9904 | 0.4898 |
| E2 Rothermel-family | max mean IoU (secondary) | 140° | 100 m/30 min | 0.9900 | 0.5516 |

| proxy | mean ROC-AUC across the grid (min / median / max) | mean IoU (min / median / max) |
|---|---|---|
| E1 wind-cone | 0.8656 / 0.9322 / 0.9910 | 0.0559 / 0.1022 / 0.6018 |
| E2 Rothermel-family | 0.8589 / 0.9286 / 0.9904 | 0.0536 / 0.0976 / 0.5516 |

**DEM coverage behind E2.** The committed snapshot covers 14,462 of the canvas's 28,236 cells (51.2 %); cells outside it are given slope 0. Per entrant, the number of cells it puts at p ≥ 0.5 outside that coverage:

- **E1 wind-cone oracle (upper bound)**: 0
- **E1 wind-cone oracle (upper bound) [IoU-selected]**: 0
- **E2 Rothermel-family oracle (upper bound)**: 0
- **E2 Rothermel-family oracle (upper bound) [IoU-selected]**: 0
