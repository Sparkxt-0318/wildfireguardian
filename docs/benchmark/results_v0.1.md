# K-SPREAD-2025 — results v0.1

**Protocol: `docs/benchmark/K_SPREAD_2025.md`, version v0.1, pre-registered 2026-09-14 before
any entrant was run. This page is the leaderboard as it stands and the list of what could not
be run. §7 is appended by `scripts/benchmark/render_results_v0_1.py` from the committed
artifacts; nothing above that line is edited after a run.**

Scorer: `scripts/benchmark/score_kspread.py`. Truth: `docs/regrade_three_way.md` §2 (A1–A6),
reference implementation `scripts/regrade_three_way.py`. Tests: `tests/test_kspread_scorer.py`.
Artifacts: `data/processed/benchmark/leaderboard.json` and
`data/processed/benchmark/<entrant>/<event>.json`.

## 1. What ran, and what did not

Two of the six protocol §6 entrants ran: **E0 persistence** and **E3 WFG canonical**
(leave-one-complex-out). E1, E2 and E4 need the 임상도 1:5000 and KMA station data the build
brief's Stage 0 lists, and E5 needs the 정보공개청구 return; none of those files is in
`data/raw/` and there is no `MANIFEST.json` there, so Stages 2–4 of the brief did not start.

One of the six protocol §2 events was scored: **영덕 2025**. Scoring needs a per-cell observed
detection stack, and 영덕 is the only event that has one committed
(`data/processed/routing_demo_canonical.npz` → `obs_stack`/`obs_times`). 의성·안동 2025 and
울진·삼척 2022 have committed model fields but no committed observation; 강릉 2023, 홍성 2023 and
밀양 2022 have neither. Rebuilding any of them needs the git-ignored raw FIRMS/ERA5/DEM bundle.
The mean-over-events and worst-event figures of protocol §5 are therefore **not reported**: one
event is not a mean, and a single-event leaderboard is what this page is.

## 2. The two tracks are not comparable, and the WFG entrant is in the second one

Protocol §3 puts an entrant that uses any observation after T0 in the **hindcast** track,
reported separately and never beside a forecast-track score.

- **E0 persistence** uses FIRMS detections at T0 and nothing else. **Forecast track.**
- **E3 WFG canonical** is the committed `spread_v2` field. `forward_simulate` advances each
  step 「with the next step's real weather」 — ERA5 reanalysis at times **after T0**
  (`src/wildfireguardian/spread_v2/forward_sim.py`, steps 2 and 5). That is an observation
  after T0, so E3 is **hindcast track** under the protocol the project itself wrote.

This is not a defect in the model and it is not a hedge. It is the first thing the benchmark
measured, and it means the committed 영덕 field is a *reconstruction* of what the fire did with
the weather that actually occurred, not a forecast anyone could have issued at T0. A
forecast-track WFG entrant is buildable — the same model on a KMA 초단기예보 issued before T0 —
and it is not committed, so it is not scored here. Any sentence of the form 「our forecast beats
X」 that rests on the committed field is unsupported until that entrant exists.

E3 is the **leak-free** field (`data/processed/routing_demo_leakfree.npz`), fitted with 영덕 and
의성·안동 both held out, because protocol §2's complex rule requires it. The canonical field
(`routing_demo_canonical.npz`) had 의성·안동 in its training set and is not an entrant.
`tests/test_kspread_scorer.py::test_e3_is_the_leave_one_complex_out_field_and_not_the_canonical_one`
is what keeps that from lapsing.

## 3. The scorer's declared conventions

Fixed before any entrant was run; the full text is the module docstring of
`scripts/benchmark/kspread_metrics.py`, and this is the summary.

| | convention |
|---|---|
| C1 time | probability between surface times is linear and clamped outside, the committed `HazardSequence` rule; an entrant's arrival at a cell is the interpolated first crossing of p ≥ 0.5, and `inf` if it never crosses |
| C2 space | metrics 1–3 sample by A5 cell membership, the same floor arithmetic as `classify_route`; metric 3 reports the router's bilinear sampling beside it |
| C3 truth | `docs/regrade_three_way.md` §2, miss allowance *m* = 0 as the headline with *m* = 1 and ∞ in the artifact; indeterminate cells enter neither the AUC nor the IoU and are counted as unscorable |
| C4 resolution | both entrants are 500 m; nearest-neighbour upsampling of entrant and truth alike to the protocol's 100 m grid replaces each cell by twenty-five identical ones and changes no metric, which the test asserts rather than assumes <!-- collision-ok: 100 --> |
| C5 metric 3 nodes | one node set for every entrant, from the canonical scan, never the entrant's own |
| C6 metric 4 classes | `docs/last_safe_departure.md`'s own cuts written out: `never`, `closes_before_5h`, `closes_after_5h`, `censored` |

**One convention changed after the first run and the reason is structural.** C5 first read
protocol §5.3's 「every walk-network node the canonical routing scans」 as the canonical scan's
origins. Measured, that set is degenerate by construction and not by any property of an
entrant: `candidate_origins` refuses an origin already standing in the fire at T0, so almost no
origin node is one an entrant can burn, and on the first run every entrant burned two of them
and the median was taken over those two. The primary set is now every node of the canonical
walk network, which is the network the canonical scan uses; the origin subset is reported
unchanged beside it in every artifact. The change applies identically to both entrants and to
every entrant that follows.

**A second choice metric 3 needs, which the protocol does not state.** An entrant's field ends
at its last surface; the 영덕 observation runs four overpasses past it. Scored against the whole
observation record an entrant is charged for every road node the fire reached after its
horizon, which measures the horizon and not the entrant. The headline counts therefore run over
a common window — the entrant's own last surface — and every count is repeated against the full
record under `whole_observation_record` in the artifact.

## 4. What this leaderboard cannot say

Everything in protocol §8, plus four things specific to v0.1:

1. **Nothing about five of the six events.** One event, one region, one fire complex.
2. **Nothing that compares the two tracks.** E0 and E3 are in different tables for a reason.
3. **Nothing about a 3-hour forecast in 영덕.** §7 shows why: between T0 and the next overpass
   at 333 minutes there is no observation, so the 3 h and 5 h horizons have the same truth as
   each other and the entire difference between them is unscorable.
4. **Nothing about passability, households, or the real fire.** It scores what FIRMS saw at
   375–500 m with a detection floor (`docs/detection_floor.md`), under A4's assumption that a
   cell nobody detected did not burn.

## 5. Nothing here is registered, and nothing here is judge-facing

No number on this page is in `docs/NUMBERS.json` and none appears on a judge-facing surface,
which is the same standing `docs/regrade_three_way.md` took and for the same reason: a
registered value is additive and permanent, and a v0.1 leaderboard with one event and two
entrants will move when Stage 2's and Stage 3's entrants land. Protocol §7 requires
registration for a number quoted at the booth; when one of these is quoted at the booth, it is
registered first. Until then the artifacts under `data/processed/benchmark/` are the record and
this page is read from them.

## 6. How to reproduce

```
python scripts/benchmark/build_entrants_v0_1.py
python scripts/benchmark/score_kspread.py --with-decision-shift
python scripts/benchmark/render_results_v0_1.py
python -m pytest tests/test_kspread_scorer.py -q
```

## 7. Adding an entrant

Write `data/processed/benchmark/entrants/<id>/entrant.json` with `id`, `track`
(`forecast` or `hindcast`), `resolution_m`, `inputs_used` and an `events` map, plus one
`<event>.npz` per event holding `grid_extent`, `times_min` and `stack`. The scorer picks it up
with no change to itself. Declaring the wrong track is the one thing no gate can catch: the
track is a claim about what the entrant read, and it is on the entrant's author.

## 8. Results

_(appended by `scripts/benchmark/render_results_v0_1.py`; nothing above this line is edited after the run)_

_Run 2026-09-14T09:31:22Z at `37a441a`; protocol `v0.1`; scorer `scripts/benchmark/score_kspread.py`; artifacts `data/processed/benchmark/`; 4135 s._

### 8.1 What the observation can and cannot separate

Truth on the 영덕 500 m canvas at each horizon, under `docs/regrade_three_way.md` §2 with *m* = 0. 「unscorable」 is the indeterminate class, which enters neither the AUC nor the IoU.

| horizon | detected cells | indeterminate (unscorable) | not detected |
|---|---:|---:|---:|
| T0 + 3 h | 249 | 688 | 27,299 |
| T0 + 5 h | 249 | 688 | 27,299 |
| T0 + 8 h | 937 | 50 | 27,249 |

The overpasses are at 0, 333, 1005, 1480, 1812, 2403 minutes after T0. Nothing observes 영덕 between T0 and the second overpass, so the 3 h and 5 h horizons have **identical truth**, and every cell first seen at the second overpass is unscorable at both. A score at 3 h in 영덕 is therefore not evidence about a 3-hour forecast; it is evidence about the T0 footprint. That is a property of the observation, not of any entrant, and it is the first thing this benchmark established.

### 8.2 Metrics 1 and 2, by track

The two tables are not to be read against each other (protocol §3).

**forecast track**

| entrant | horizon | ROC-AUC | IoU at p ≥ 0.5 | predicted positive | unscorable |
|---|---|---:|---:|---:|---:|
| E0 persistence | T0 + 3 h | 1.0000 | 1.0000 | 249 | 688 |
| E0 persistence | T0 + 5 h | 1.0000 | 1.0000 | 249 | 688 |
| E0 persistence | T0 + 8 h | 0.6329 | 0.2657 | 249 | 50 |

**hindcast track**

| entrant | horizon | ROC-AUC | IoU at p ≥ 0.5 | predicted positive | unscorable |
|---|---|---:|---:|---:|---:|
| E3 WFG canonical (leave-one-complex-out) | T0 + 3 h | 0.9990 | 0.8272 | 373 | 688 |
| E3 WFG canonical (leave-one-complex-out) | T0 + 5 h | 0.9990 | 0.6368 | 528 | 688 |
| E3 WFG canonical (leave-one-complex-out) | T0 + 8 h | 0.9791 | 0.3606 | 536 | 50 |

### 8.3 Metric 3 — arrival-time error at the road nodes (the one that matters)

Node set: every node of the canonical walk network (C5) --- 8,443 nodes, identical for every entrant, with the 458-origin subset reported beside each row. Cell membership (A5). The window is the entrant's own last surface; `whole_observation_record` in the artifact repeats every count against the full observation. Signed error is model minus observation, so **positive is late** — the direction that strands people.

| entrant | track | nodes | observation burns | entrant burns | both | median abs error | false-safe | false-safe rate | false alarms |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| E0 persistence | forecast | 8,443 | 1,772 | 275 | 275 | 0.0 min | 1,497 of 8,168 | 0.1833 | 0 |
| E3 WFG canonical (leave-one-complex-out) | hindcast | 8,443 | 1,772 | 281 | 278 | 0.0 min | 1,494 of 8,162 | 0.1830 | 3 |

Beside the headline, per entrant:

- **E0 persistence** (forecast): of the 275 nodes both call burned, 0 are late, 0 early and 275 exact; 17 more nodes are indeterminate at the window and are charged to neither side. 0 of the nodes it calls safe still carry a non-zero probability at its last surface (720 min), so C1's clamp may be hiding a later crossing for them. Read through the router's bilinear sampler instead of cell membership the false-safe count is 1,610 of 8,281; on the 458-origin subset it is 79 of 456.
- **E3 WFG canonical (leave-one-complex-out)** (hindcast): of the 278 nodes both call burned, 0 are late, 3 early and 275 exact; 17 more nodes are indeterminate at the window and are charged to neither side. 4,176 of the nodes it calls safe still carry a non-zero probability at its last surface (720 min), so C1's clamp may be hiding a later crossing for them. Read through the router's bilinear sampler instead of cell membership the false-safe count is 1,596 of 8,261; on the 458-origin subset it is 79 of 456.

**Why the two entrants land within three nodes of each other.** The canonical walk network touches 1,009 of the canvas's 28,236 cells, so most of the map has no road node in it at all. Per entrant, of the cells it calls burned within its horizon:

- **E0 persistence**: 249 cells, of which 53 contain a road node, holding 275 nodes. The observation burns 937 cells in the same window, of which 227 contain a road node, holding 1,772.
- **E3 WFG canonical (leave-one-complex-out)**: 540 cells, of which 56 contain a road node, holding 281 nodes. The observation burns 937 cells in the same window, of which 227 contain a road node, holding 1,772.

### 8.4 Metric 4 — decision shift (영덕 주건물)

Buildings whose last-safe-departure class differs between the entrant's field and the observation-graded field, under the committed time-aware policy with only the field changed. ⚠ Both sweeps read their field through the router's **bilinear** sampler, which on a binary footprint is the softer reading (`docs/regrade_three_way.md` §A5, §6); metrics 1–3 do not.

| entrant | track | buildings scored | class changed | entrant more optimistic |
|---|---|---:|---:|---:|
| E0 persistence | forecast | 19,250 | 3,906 | 3,906 |
| E3 WFG canonical (leave-one-complex-out) | hindcast | 19,250 | 3,898 | 3,879 |

- **E0 persistence**: the observation-graded field says 3,906 buildings have a window that closes inside 600 min; this entrant flags 0 as closing, of which 0 do (0 in exactly the right class). Entrant classes {'censored': 19060, 'never': 190}; observation-graded classes {'censored': 15154, 'closes_after_5h': 1261, 'closes_before_5h': 2645, 'never': 190}.
- **E3 WFG canonical (leave-one-complex-out)**: the observation-graded field says 3,906 buildings have a window that closes inside 600 min; this entrant flags 34 as closing, of which 27 do (15 in exactly the right class). Entrant classes {'censored': 19026, 'never': 190, 'closes_after_5h': 15, 'closes_before_5h': 19}; observation-graded classes {'censored': 15154, 'closes_after_5h': 1261, 'closes_before_5h': 2645, 'never': 190}.

### 8.5 What could not be run

| protocol item | why |
|---|---|
| event gangneung_2023 | no committed observed detection stack in this repository |
| event hongseong_2023 | no committed observed detection stack in this repository |
| event miryang_2022 | no committed observed detection stack in this repository |
| event uiseong_andong_2025 | no committed observed detection stack in this repository |
| event uljin_samcheok_2022 | no committed observed detection stack in this repository |
| entrants E1, E2, E4 | 임상도 1:5000 and KMA station data absent from `data/raw/`, no `MANIFEST.json` |
| entrant E5 | the 정보공개청구 to 국립산림과학원 has not returned |
| protocol §5 mean and worst event | one event scored; a mean over one event is that event |

