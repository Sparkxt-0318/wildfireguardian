# kcf-defend — results: where would holding the fire add the most safe departure time?

**Every number here is model output on reconstructed inputs. It is not what happened to people. No claim is made that
any suppression action would have changed any outcome, nor about what any official, crew or pilot should have done.**

Protocol: `PROTOCOL.md`, frozen at `af06676` before any outcome. Amendment 1 (FRONT tiles span both regions) was
committed before any delay was evaluated. Amendment 2 (gate result, plus one extra reference check) was committed after
the gate and before the production run. Clock times written inside the amendments are approximate; the commit times
are authoritative. Run 2026-11-18, 16:00–17:45 UTC, 312 jobs (2 regions × 6 arms × 2 horizons × 13 issue hours).

The pages are in `pages/`: one per issue hour, Korean (`*.ko.md`) and English (`*.en.md`), 26 in all, plus
`pages/pages_ko_en.pdf`.

## 0 Headline (primary configuration fixed in advance: MEASURED arm, 8 h horizon, ranked by a 60 min delay)

*Model output on reconstructed inputs. Not what happened to people.*

* **What was ranked.** At each issue hour the primary configuration evaluated:
  * between 292 and 979 road cells (375 m cells with roads that close within 8 h and are not already burning);
  * between 10 and 41 front sections (2 km × 2 km tiles of the known fire area).

  Of these, **9 to 70 candidates** add any window to any village at Δ = 60 min. All others add nothing: every village
  they could affect is already inside the fire area, is not cut within 8 h, or is cut by a different cell.
* **Rank 1 is a front section at every one of the 13 hours.** A 60 min hold there adds **43,726 to 347,825
  person-minutes**: 26 to 540 village-minutes, at 1 to 15 villages. Holding a front section delays every cell that
  fire from it reaches, so it can help several villages at once. A single road cell helps the one or two villages whose
  last route runs through it. Below rank 1 the top ten mixes the two types: 3 to 6 road cells per hour.
* **No village gains more than the delay itself** (largest single-village gain: 30 / 60 / 120 min at Δ = 30 / 60 /
  120). Doubling the hold from 60 to 120 min adds little at rank 1 in the evening, because gains are truncated by the
  8 h horizon and by the next cell that closes. For example, at 21:00 KST: 155,034 → 159,528 person-minutes.
* **Stability across arms is partial.** Count of the primary top ten (8 h, Δ = 60) that also appear in each other arm's
  top ten, median over 13 hours (range):

  | arm | median (range) |
  |---|---|
  | MEASURED_GUST (ERA5, **PROVISIONAL**) | 8 (3–10) |
  | MEASURED_GUST_KMA | 8 (3–10) |
  | ORDINARY | 6 (3–8) |
  | RUNNING | 3 (2–8) |
  | WORST | 2 (0–7) |

  * Within MEASURED, the ranking moves less:
    * against the 5 h horizon: median 7 of 10 (range 6–10);
    * against the unweighted ranking: 8 (5–9);
    * against Δ = 30: 9 (7–10);
    * against Δ = 120: 10 (8–10).
  * **Stable** candidates, in the top ten of the primary and of at least 4 of the other 5 arms: 1 to 8 per hour, most
    at 19:00–21:00 KST (5, 6 and 8).
  * The fast arms disagree most. RUNNING and WORST have about 100–170 ranked candidates in the afternoon, against 9–41
    for MEASURED, because they put most of the region within reach.
  * **A ranking from one reach curve should not be read as robust.**
* **Population weighting matters at some hours.** Care facilities take their Voronoi share of HRSL population (§5),
  and two senior centres in 안동 town carry the largest shares: 마지경로당 about 6,550 and 용상3구경로당 about 4,310.
  At 17:00 KST the rank-1 candidate helps only 마지경로당 (+26 min), which gives 170,269 person-minutes.
  Facilities provide 13.7 % of all person-minutes in the 13 primary top tens.
* **Verification.**
  * The fast solver equals `deadline_field.core` exactly in the gate: 4 base jobs and 32 delayed instances, 0
    mismatches.
  * It reproduces all 27,144 committed replay rows on latest departure and shelter.
  * Every rank-1 candidate's gains were re-computed with `core.backward` and are equal to the second (§2).

### 0.1 Per issue hour (primary: MEASURED, 8 h; ranked by Δ = 60)

*Model output on reconstructed inputs. Not what happened to people.*

| Issue (KST) | ranked | rank 1 | person-min Δ30 / Δ60 / Δ120 | village-min Δ60 | villages helped Δ60 | distinct villages helped by top ten | top ten road / front | overlap with other arms (ORD, RUN, WORST, GUST, GUST_KMA) | stable |
|---|---|---|---|---|---|---|---|---|---|
| 12:00 | 23 | front near 병방리 (의성군) (36.416 N, 128.716 E) | 34,788 / 69,576 / 124,192 | 240 | 4 | 13 | 5 / 5 | 8, 2, 1, 3, 3 | 2 |
| 13:00 | 24 | front near 하화리 (의성군) (36.417 N, 128.693 E) | 75,915 / 147,549 / 265,521 | 265 | 6 | 15 | 4 / 6 | 7, 3, 2, 4, 4 | 3 |
| 14:00 | 22 | front near 하화리 (의성군) (36.417 N, 128.693 E) | 75,915 / 147,549 / 265,521 | 265 | 6 | 12 | 5 / 5 | 6, 3, 2, 4, 4 | 3 |
| 15:00 | 41 | front near 망호리 (안동시) (36.453 N, 128.694 E) | 204,876 / 347,825 / 468,688 | 421 | 10 | 24 | 3 / 7 | 3, 3, 2, 8, 8 | 3 |
| 16:00 | 37 | front near 추목리 (안동시) (36.469 N, 128.828 E) | 199,931 / 326,538 / 328,271 | 222 | 6 | 21 | 4 / 6 | 5, 2, 2, 10, 10 | 2 |
| 17:00 | 9 | front near 현내리 (안동시) (36.524 N, 128.717 E) | 65,202 / 170,269 / 170,269 | 26 | 1 | 5 | 4 / 5 | 7, 2, 0, 8, 8 | 1 |
| 18:00 | 31 | front near 기사리 (영덕군) (36.429 N, 129.162 E) | 32,260 / 47,172 / 50,105 | 272 | 7 | 24 | 5 / 5 | 3, 3, 3, 7, 7 | 3 |
| 19:00 | 51 | front near 낙평리 (영덕군) (36.464 N, 129.252 E) | 71,015 / 116,097 / 129,660 | 500 | 13 | 39 | 5 / 5 | 4, 5, 5, 8, 8 | 5 |
| 20:00 | 56 | front near 율전리 (영덕군) (36.463 N, 129.275 E) | 127,514 / 178,567 / 187,214 | 540 | 14 | 32 | 5 / 5 | 5, 6, 5, 8, 8 | 6 |
| 21:00 | 70 | front near 화개리 (영덕군) (36.426 N, 129.363 E) | 110,690 / 155,034 / 159,528 | 514 | 15 | 40 | 6 / 4 | 6, 8, 7, 9, 9 | 8 |
| 22:00 | 43 | front near 소월리 (영덕군) (36.372 N, 129.384 E) | 37,128 / 43,726 / 44,909 | 291 | 8 | 16 | 6 / 4 | 6, 6, 2, 10, 10 | 3 |
| 23:00 | 43 | front near 소월리 (영덕군) (36.372 N, 129.384 E) | 37,128 / 43,726 / 44,909 | 291 | 8 | 16 | 6 / 4 | 6, 6, 2, 9, 7 | 1 |
| 24:00 | 32 | front near 벌영리 (영덕군) (36.534 N, 129.388 E) | 41,634 / 75,149 / 75,149 | 54 | 1 | 18 | 5 / 5 | 7, 6, 3, 9, 8 | 3 |

How to read the table:

* **"ranked"** = candidates with any gain.
* **"rank 1"** is located by its tile centre and the nearest planner place, which is not necessarily where the gain
  falls.
* **13:00 and 14:00, and 22:00 and 23:00, have the same rank 1 and values.** Between 22:00 and 23:00 KST no new disc
  entered the known fire area. Between 13:00 and 14:00 only 2 did, and they did not change the rank-1 gains. The
  13:00/14:00 top tens still differ (see the pages).
* The full top ten with every helped village, its minutes, road names (Overture refs and names joined by OSM way) and
  coordinates is on the page for each hour.
* Every ranked candidate × configuration × hour × delay is in `ranking.csv.gz`.

## 1 Method (as frozen)

* **Window.** For each of the 174 places, the window is the number of seconds in [0, H] in which leaving still reaches
  one of its 3 planner shelters. It is computed in the F-3.1 deadline field with the kcf-replay closures of each arm.
* **Candidates.**
  * **ROAD:** a 375 m routing cell with roads, closing after the issue and within H. Its closure is delayed by Δ.
  * **FRONT:** the known-fire discs of a 2 km tile. Every cell's closure becomes min(closure from the other discs,
    Δ + closure from the tile's discs). Cells already inside the fire area are never delayed.
* **Benefit.** Σ over villages of population × window gain, in person-minutes. The village-minutes and the number of
  villages helped are reported beside it.
* **Population.** Meta/CIESIN HRSL `hrsl_general` (tile `v1/cog_globallat_30_lon_120_general-v1.1.tif`, VRT
  last-modified 2023-04-06, retrieved 2026-11-18 15:33 UTC). Pixels within 2 km are assigned to the nearest place:
  70,227 people over 174 places, none zero (`population.csv`, `population_meta.json`).
* **Solver.** Under permanent closures every set in the field is a prefix, so the field reduces to one integer per edge
  state. It is computed with a bottleneck label-setting pass per shelter (`fastfield.py`, numba), about 5 ms per
  shelter against about 1.4 s for `core.backward`.
* **Pruning.** A shelter field is recomputed only when a changed cell binds one of its edges or is its own cell. This is
  exact, and gate part 2 checks it.

## 2 Verification

| check | n | result |
|---|---|---|
| Fast base vs committed `per_place.csv` (minute of last departure, shelter, empty/non-empty) | 27,144 rows | **0 mismatches** |
| same, CUT / NOT_CUT label | 27,144 | 9 differ: the replay labels from a greedy, non-earliest witness arrival; gains do not use the label (`gate1.json`) |
| Fast vs `core.backward` + `core.issue_set`, exact seconds, base jobs | 4 jobs, 348 place-rows | 0 mismatches (`gate2.json`) |
| same, seeded delayed instances | 32 (+8 draws with no candidate of the drawn kind) | 0 mismatches; pruned = unpruned in 32/32; only 3 had any gain |
| Rank-1 candidate per hour (primary, Δ = 60), every gaining place, `core.backward` before and after the delay | 13 hours | see `check_top.json`: CHECK_TOP_RESULT |
| Issue sets with more than one piece (`core`) | 4 base jobs, 348 place-rows | 0 (prefix property; kcf-roadcut found none in all 27,144) |

## 3 Stability across arms (PROTOCOL §6)

*Model output on reconstructed inputs. Not what happened to people.*

The per-hour overlaps are in the table in §0.1. The rank of every primary top-ten candidate in each arm is in
`numbers.json` → `stability_by_hour`.

The MEASURED and the two gust arms share curve shapes, and in the evening often the same class, so they agree most.
ORDINARY (341 m/h) and the fast arms RUNNING and WORST (8.2 km/h) move the cut-off roads to different villages. At those
speeds the same hold buys time in different places. WORST, whose 3 km head start puts many villages inside at once, has
the lowest overlap: 0 to 7.

Read the ranking as conditional on the reach curve. Only the "stable" candidates on each page survive most of the
curves.

## 4 What is not modelled

Printed on every page (PROTOCOL §8):

* whether a crew, engine or aircraft can reach the location in time, hold it, or for how long;
* aircraft limits: availability, turnaround, wind and visibility, and night flying (most of the 25 March evening is
  night);
* crew safety: escape routes, safety zones and entrapment risk. A location ranked high here may be one no crew should
  be sent to;
* fire behaviour beyond a uniform postponement of the reach curve: spotting, fire going around a held section,
  re-ignition, and effects elsewhere. Only one location is held at a time and resources are not limited;
* evacuation itself: traffic, warnings, and who had already left. Population is a residential estimate.

By construction, villages already inside the fire area cannot gain, nor can villages whose window already reaches the
horizon. Gains are truncated at H.

## 5 Limits specific to this study

* **The FRONT unit is a 2 km tile of detection-disc centres.** Several top fronts contain a single 375 m disc: a lone
  hotspot ahead of the main area, whose reach drives the closures of nearby roads. "Hold this section" then means
  "stop spread from this hotspot". The tile size was fixed in advance and not varied.
* **Population.** HRSL is a residential model estimate with a single 2 km Voronoi rule. Care facilities in town take a
  town share. The unweighted ranking agrees with the weighted one on a median of 8 of 10.
* **One fire day, one replay.** All the kcf-replay and kcf-roadcut limits apply: the reconstructed known fire area,
  distance-only reach curves, and MEASURED_GUST being PROVISIONAL.
* **No validation is possible.** There is no record of where holding would have bought time, so these are model
  rankings, not tested predictions.

## 6 Prior work and how this differs

See `PRIOR_WORK.md`. Only search snippets were read, because arXiv was not reachable.

Harris, Forbes & Taimre (2023, *Computers & Operations Research* 160, 106392) place k suppression resources. Each
resource adds a delay to minimum-travel-time arrival on a landscape graph, and the objective is **area burned**. The
Alvelos/Mendes/Delazeri line uses the same model.

This study uses the same delay idea but measures it on **evacuation departure windows on the road network**,
population-weighted. It evaluates single candidates exhaustively instead of optimising a set of resources.

The nearest neighbours are:

* Hof et al. 2000: delays fire arrival at targets;
* Zhou & Erdogan 2019: joint suppression and evacuation, as a goal programme;
* Li, Cova & Dennison: trigger buffers, with no suppression.

No source found ranks road cells or front sections by the departure time they would buy. That finding rests on snippets.

## Files

| file | content |
|---|---|
| `PROTOCOL.md` | frozen protocol and amendments |
| `pages/HH00_KST.{ko,en}.md`, `pages/pages_ko_en.pdf` | one page per issue hour, Korean and English |
| `numbers.json` | stability per hour, summaries, per-configuration rank-1, place states, candidate counts |
| `ranking.csv.gz` | every ranked candidate × arm × horizon × hour × delay, with helped villages and gains (seconds) |
| `population.csv`, `population_meta.json` | HRSL population per place and provenance |
| `roadnames.json` | OSM way → Overture 2026-10-21.0 name, refs, class |
| `gate1.json`, `gate2.json`, `check_top.json` | verification |
| `fastfield.py`, `defend.py`, `aggregate.py`, `pages.py`, `results_table.py`, `population.py`, `roadnames.py`, `gate1.py`, `gate2.py`, `check_top.py`, `render_pdf.py` | code |

The raw job outputs (312 JSON files) stay in scratch because of their size. They are reproduced with:

```bash
python3 tools/fetch_routing_inputs.py
```

```bash
cd research/kcf-defend && python3 defend.py out/runs --workers 4 && python3 pages.py out/runs
```
