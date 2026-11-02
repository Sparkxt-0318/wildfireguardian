# Who needs more time: impact numbers from the recorded 2025 planner cache

Reproducible, model-relative numbers and English figures for the MIT Solve 2027 application, computed from the
six booth-cache files the village evacuation planner already ships (`planner/cache/`, 2 regions x 3 recorded input
times). This package re-reads those recorded Route-Check API results; it runs no new route checks and changes no
routing, forecast or checking code.

> **사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다. / Planning aid only — not for live evacuation operations.**
> Fire input: 2025년 실제 산불 기록 기반 시나리오 재현 / Recorded 2025 wildfire · scenario replay.

## Read this first: what these numbers are not

1. **Fire scenarios from the forecast, not fire-spread simulations.** Each recorded input time has 4 scenario members
   drawn independently per 375 m cell from the c651 forecast. They are not simulations of the actual fire.
2. **One-hour horizon.** Hazards cover 1 hour after each recorded input time. Departures were checked every 10 minutes
   (+0 to +50 min). Times between checked departures are not checked; a leave-by deadline of +50 min means the checked
   window may extend later, the scenario window just ends.
3. **Roads are a model.** Provisional pre-fire OpenStreetMap snapshot (2025-03-21) at an assumed 40 km/h, rounded up to
   1 s ticks; no congestion; missing one-way tags assumed two-way; passability never field-validated.
4. **Destinations are not official shelters.** Each place is checked against its 3 nearest (straight-line) OSM
   destinations with distinct road entry nodes; the ones used are OSM schools, community halls and one OSM-mapped
   `amenity=shelter` in Yeongdeok (`destinations_used.*` keys). Travel between a mapped point and its road entry node
   (진입 지점) is not modelled. Places come from a 2026-10-17 OSM extract (current data), roads from the pre-fire snapshot.
5. **Recorded on the evaluated host.** Every result in the cache was computed by the Route-Check API on a native macOS
   arm64 host, the planner's test for the evaluated booth host (purpose `booth`, fixed 30 s budget per check); the API
   records platform and machine, not the chip. Checks that timed out and were re-checked are shown
   as their re-check, exactly as the planner shows them.
6. **Model-relative only.** `checked_route` = a route that passed the checks within the model and its inputs (never
   "safe"); `model_no_route` = no route within this model and input scope (not proof that escape is impossible);
   `unresolved` = cannot judge (never safe, never a deadline). **None of these numbers are evacuation outcomes,
   observed travel times or casualties avoided.**
7. **Small and incomplete samples.** 5 care facilities are mapped in OSM (all in Uiseong-Andong), none in Yeongdeok.
   OSM coverage of villages and facilities is incomplete. Results are specific to these recorded scenarios.

## Headline numbers

All values come from [`NUMBERS.json`](NUMBERS.json) (key, definition, value, numerator/denominator, scope, script and
input SHA-256 for each). "Cases" count each place once per recorded input time; "places" count each place once.

<!-- BEGIN GENERATED: headline -->
| Key (NUMBERS.json) | Value | Meaning (short; full definition in NUMBERS.json) |
|---|---:|---|
| `records.route_checks@all/pooled` | 9,722 | route-check records in the six cache files (incl. re-checks) |
| `records.rechecks@all/pooled` | 279 | re-checks of timed-out checks among them |
| `places@all/places` | 174 | distinct villages/hamlets + care facilities checked (both regions) |
| `osm_origins_not_checkable@all/places` | 3 | listed OSM villages with no road node within 2 km (never checked) |
| `cases@all/pooled` | 522 | place-input-time cases (each place once per recorded input time) |
| `cell.checked_route.offset_0000s@all/pooled` | 501/522 (96.0%) | cases with a checked route for departure at the input time |
| `cell.checked_route.offset_3000s@all/pooled` | 354/522 (67.8%) | cases with a checked route for departure at +50 min |
| `cell.checked_route.offset_0000s@uiseong_andong_2025/pooled` | 239/252 (94.8%) | same, Uiseong-Andong, departure at +0 min |
| `cell.checked_route.offset_3000s@uiseong_andong_2025/pooled` | 103/252 (40.9%) | same, Uiseong-Andong, departure at +50 min |
| `cell.checked_route.offset_0000s@yeongdeok_2025/pooled` | 262/270 (97.0%) | same, Yeongdeok, departure at +0 min |
| `cell.checked_route.offset_3000s@yeongdeok_2025/pooled` | 251/270 (93.0%) | same, Yeongdeok, departure at +50 min |
| `no_checked_route_at_offset_0000s@all/pooled` | 21/522 (4.0%) | cases with no checked route for departure at the input time |
| `no_checked_route_any_offset@all/pooled` | 21/522 (4.0%) | cases with no checked route at any departure time |
| `attempts@all/pooled` | 9,396 | route checks behind the cases (place x candidate destination x departure) |
| `best_verdict.model_no_route@all/pooled` | 11/522 (2.1%) | cases with model_no_route at every attempt (no route within the model) |
| `best_verdict.unresolved@all/pooled` | 10/522 (1.9%) | cases with no checked route and >= 1 unresolved attempt (cannot judge) |
| `window_closes_within_hour@all/pooled` | 147/522 (28.2%) | cases whose checked departure window ends before +50 min |
| `window_closes_within_hour@uiseong_andong_2025/pooled` | 136/252 (54.0%) | same, Uiseong-Andong |
| `places.no_checked_route_at_offset_0000s_any_input@all/places` | 21/174 (12.1%) | places with no checked route at +0 min in >= 1 input time |
| `places.not_checked_at_offset_3000s_any_input@all/places` | 65/174 (37.4%) | places with no checked route at +50 min in >= 1 input time |
| `deadline.latest_3000s@all/pooled#care_facility` | 15/15 (100.0%) | care-facility cases still checked at +50 min |
| `api_check.recorded_equals_planner_rule_on_original@all/pooled` | 522/522 (100.0%) | API recorded fields = planner rules on original attempts |
| `api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled` | 517/522 (99.0%) | planner-displayed deadline = API latest_checked_depart_offset_s |
| `api_check.displayed_differs_explained_by_recheck@all/pooled` | 8/8 (100.0%) | displayed differences explained by re-checks |
| `travel_only.fastest_meets_flames@all/pooled` | 9/501 (1.8%) | fastest (travel-time-only) routes with predicted flame contact, at the leave-by time |
| `travel_only.fastest_meets_flames@uiseong_andong_2025/pooled` | 9/239 (3.8%) | same, Uiseong-Andong |
| `travel_only.clear_pairs_equal_arrival@all/pooled` | 492/492 (100.0%) | other comparisons: checked route arrives at the same second |
| `travel_only.extra_arrival_s.min@all/pooled` | 31 (n = 9) | extra arrival time of the checked alternative, min (s) |
| `travel_only.extra_arrival_s.median@all/pooled` | 328 (n = 9) | extra arrival time, median (s) |
| `travel_only.extra_arrival_s.max@all/pooled` | 1,309 (n = 9) | extra arrival time, max (s) |
| `travel_only.extra_length_m.min@all/pooled` | 270.7 (n = 9) | extra route length, min (m) |
| `travel_only.extra_length_m.median@all/pooled` | 2646.9 (n = 9) | extra route length, median (m) |
| `travel_only.extra_length_m.max@all/pooled` | 12783.2 (n = 9) | extra route length, max (m) |
| `redundancy.turn_aware_paths_1@all/places` | 115/174 (66.1%) | places with one edge-disjoint legal path (a single bottleneck segment) |
| `redundancy.single_cut_at_entry_node@all/places` | 108/115 (93.9%) | of those, bottleneck = first segment leaving the entry node |
| `redundancy.turn_aware_equals_plain@all/places` | 174/174 (100.0%) | turn-aware count = count ignoring turn restrictions |
<!-- END GENERATED: headline -->

Candidate wording for the application, with cautions: [`APPLICATION_SENTENCES.md`](APPLICATION_SENTENCES.md).

## Results by recorded scenario set

Origins = OSM villages/hamlets and care facilities with an accepted road node within 2 km (the ones the API checked).
"Window closes before +50 min" = a checked route exists at some departure but not at +50 min.

<!-- BEGIN GENERATED: by-scenario -->
| Region | Recorded input time | Origins | Checked at +0 min | Checked at +50 min | No checked route at any departure (model_no_route + unresolved) | Window closes before +50 min | Fastest route meets predicted flames |
|---|---|---:|---:|---:|---:|---:|---:|
| Uiseong-Andong | 2025-03-23 10:00 KST (2025-03-23T01:00:00Z) | 84 | 83/84 (98.8%) | 36/84 (42.9%) | 1 + 0 | 47/84 (56.0%) | 1/83 (1.2%) |
| Uiseong-Andong | 2025-03-24 18:00 KST (2025-03-24T09:00:00Z) | 84 | 84/84 (100.0%) | 36/84 (42.9%) | 0 + 0 | 48/84 (57.1%) | 7/84 (8.3%) |
| Uiseong-Andong | 2025-03-26 02:00 KST (2025-03-25T17:00:00Z) | 84 | 72/84 (85.7%) | 31/84 (36.9%) | 7 + 5 | 41/84 (48.8%) | 1/72 (1.4%) |
| Yeongdeok | 2025-03-26 04:00 KST (2025-03-25T19:00:00Z) | 90 | 84/90 (93.3%) | 81/90 (90.0%) | 3 + 3 | 3/90 (3.3%) | 0/84 (0.0%) |
| Yeongdeok | 2025-03-26 08:00 KST (2025-03-25T23:00:00Z) | 90 | 90/90 (100.0%) | 86/90 (95.6%) | 0 + 0 | 4/90 (4.4%) | 0/90 (0.0%) |
| Yeongdeok | 2025-03-26 17:00 KST (2025-03-26T08:00:00Z) | 90 | 88/90 (97.8%) | 84/90 (93.3%) | 0 + 2 | 4/90 (4.4%) | 0/88 (0.0%) |
| **Uiseong-Andong, 3 input times** | pooled cases | 252 | 239/252 (94.8%) | 103/252 (40.9%) | 8 + 5 | 136/252 (54.0%) | 9/239 (3.8%) |
| **Yeongdeok, 3 input times** | pooled cases | 270 | 262/270 (97.0%) | 251/270 (93.0%) | 3 + 5 | 11/270 (4.1%) | 0/262 (0.0%) |
| **Both regions, 6 input times** | pooled cases | 522 | 501/522 (96.0%) | 354/522 (67.8%) | 11 + 10 | 147/522 (28.2%) | 9/501 (1.8%) |
<!-- END GENERATED: by-scenario -->

Pooling: within a region the three input times are different scenario sets for the same places, so pooled rows count
place-input-time cases (descriptive, not independent samples). Distinct-place counts (`@*/places` keys) count each
place once. The two regions share no place.

## Leave-by deadline (출발 마감) by origin type

Cases by the latest departure (minutes after the recorded input time) with a checked route, pooled over the three
input times of each region. Origin types are the planner's: village (`place=village|hamlet`) or care facility
(`vulnerable = true`: `nursing_home` / `social_facility`), as in `planner/src/components/LeftPanel.tsx` `glyphKind`.

<!-- BEGIN GENERATED: deadlines -->
| Subset | Cases | +10 | +20 | +30 | +40 | +50 (last checked; may be later) | none: model_no_route | none: unresolved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Uiseong-Andong villages | 237 | 3 | 13 | 38 | 82 | 88 | 8 | 5 |
| Uiseong-Andong care facilities | 15 | 0 | 0 | 0 | 0 | 15 | 0 | 0 |
| Yeongdeok villages | 270 | 0 | 0 | 3 | 8 | 251 | 3 | 5 |

No case had its last checked departure at +0 min (`deadline.latest_0000s@*` = 0). Yeongdeok has no care facility in the OSM extract.
<!-- END GENERATED: deadlines -->

## Road redundancy

Number of walks from each place's road entry node to any of its three candidate destination nodes that share no
directed road segment, on the exact graph the API used (SHA-256 asserted against the `input_hashes.graph` of every
cached route check). Turn-aware counts obey the graph's `forbidden_turns` as the routing kit does; counts ignoring turn
restrictions are also computed and equal for every place.

<!-- BEGIN GENERATED: redundancy -->
| Subset | Places | 1 path | 2 paths | 3 paths | >= 4 | 1 path, bottleneck at the entry node |
|---|---:|---:|---:|---:|---:|---:|
| Uiseong-Andong villages | 79 | 53 | 26 | 0 | 0 | 48/53 |
| Uiseong-Andong care facilities | 5 | 5 | 0 | 0 | 0 | 4/5 |
| Yeongdeok villages | 90 | 57 | 31 | 2 | 0 | 56/57 |
| All checked places | 174 | 115 | 57 | 2 | 0 | 108/115 |

Descriptive only (no causal or statistical claim): no checked route at +0 min in 14/345 (4.1%) cases of single-path places versus 7/177 (4.0%) of places with at least two paths; no checked route at +50 min in 117/345 (33.9%) versus 51/177 (28.8%) (keys `redundancy_x.*@all/pooled#rc1|rc2plus`).
<!-- END GENERATED: redundancy -->

A value of 1 means every route to all three candidate destinations shares at least one directed road segment. It is a
property of the provisional road graph and of the planner's entry node (the nearest node of the largest strongly
connected component to the OSM point, which can lie on a dead-end spur; see `redundancy.entry_out_degree_1@*`). It
ignores capacity, travel time and fire, and is not a field-verified count of access roads.

## Figures

PNG and SVG in [`figures/`](figures/); each has a CSV twin in [`tables/`](tables/) and every plotted count is asserted
equal to `NUMBERS.json` when the figure is drawn. Verdicts use the planner's fixed colours (`planner/docs/ARCHITECTURE.md`
section 7) plus text labels, and unresolved is always hatched, so no verdict relies on colour alone: green `#1A9E55`
checked route, ink `#0B0B0C` model_no_route, grey `#9A9AA0` hatched unresolved. The travel-time-only route is never green.

1. [`fig1_checked_share_by_offset`](figures/fig1_checked_share_by_offset.png) - share of origins with a checked route
   at each departure time, per scenario set, split into the three verdicts (the green part is the survival curve of the
   checked departure window).
2. [`fig2_deadline_by_origin_type`](figures/fig2_deadline_by_origin_type.png) - leave-by deadline distribution by
   origin type and region.
3. [`fig3_travel_only_vs_checked`](figures/fig3_travel_only_vs_checked.png) - the comparisons where the fastest route
   meets predicted flames, with the checked alternative's extra time and length.

![Checked-route share by departure time](figures/fig1_checked_share_by_offset.png)

## Definitions (replicated exactly from the planner)

- **Cell verdict at a departure offset** (`planner/src/domain/plan.ts` `combineVerdicts`/`cellVerdict`, lines 106-115):
  `checked_route` if any candidate destination has a checked route; `model_no_route` only if every attempted
  destination is `model_no_route`; otherwise `unresolved`. No attempt at all is `unresolved`.
- **Re-checks** (`planner/src/api/cache.ts` lines 120-145): a re-check (`recheck_of`) replaces the attempt it re-ran.
- **Leave-by deadline, 출발 마감** (`plan.ts` `latestSafeDeparture`, 155-161): the latest departure offset whose cell
  is `checked_route`. Unresolved and skipped cells never count.
- **Contiguous deadline** (`plan.ts` `contiguousSafeDeparture`, 169-178; contract
  `latest_contiguous_checked_depart_offset_s`): walk the offsets from the earliest, leaving out only "시간창 밖"
  (`window_unsatisfiable`) cells, and stop at the first cell that is not `checked_route`. In this cache no origin has
  a gap, so it always equals the leave-by deadline (`contiguous_differs_from_latest@*` = 0).
- **Window-unsatisfiable offsets** ("시간창 밖", `cache.ts` 223-226): research-origin offsets that precompute did not
  send because the recorded arrival window cannot be met. They are their own category, never a verdict; none occur for
  village/care-facility origins.
- **Overall verdict** (`plan.ts` 204, contract `best_verdict`): the same rule over all attempts of an origin.
- **Origin set** (`planner/src/data/staticData.ts` `scenarioOrigins`, 179-183; `controller.ts` `completePlans`,
  494-501): all OSM origins plus the scenario's research-mission origins; origins without results are unresolved.
  Headline numbers cover checked OSM villages and care facilities only; the 3 not-checkable villages and the 8 research
  origins are listed in [`tables/origin_cases.csv`](tables/origin_cases.csv).
- **Travel-time-only comparison** (`cache.ts` 250-258, `planner/scripts/precompute.py` `best_checked`): for each origin
  with a checked route, one route check with `policy: travel_only` at the same start, destination and departure as its
  default checked route (the earliest-arriving checked attempt at its leave-by deadline). "Meets predicted flames" =
  centre-model flame contact (`exposure[].contact`) in at least one of the 4 scenario members. Extra arrival = checked
  arrival minus travel-only arrival (same departure); extra length = difference of summed straight edge chords (EPSG:5179).
- **Road redundancy**: see the section above and `wfg_impact/maxflow.py`. The legality rule is the kit's
  (`integration/kit/routing_candidate/baseline/temporal_contract.py` `check_mission`: an edge is legal iff it starts at
  the current node and `(incoming edge, edge)` is not a forbidden turn).

The port is `wfg_impact/planner_rules.py`; its docstring lists every replicated function and line range.

## Cross-check against the API's own fields

For every village/care-facility origin the cache stores the API's `best_verdict`, `latest_checked_depart_offset_s`
and `latest_contiguous_checked_depart_offset_s`. They are compared with (1) the API's own `api/dispatch.py`
`origin_plan` re-applied to the recorded attempts, (2) the planner rules applied to the same original attempts and
(3) the values the planner displays (re-checks substituted).

<!-- BEGIN GENERATED: crosscheck -->
| Scenario set | Origins | Recorded = API rule on original attempts | Recorded = planner rules on original attempts | Displayed = recorded: latest / contiguous / best verdict | Origins with re-checked attempts | Differences explained by re-checks |
|---|---:|---:|---:|---:|---:|---:|
| uiseong_andong_2025/20250323T010000Z | 84 | 84 | 84 | 84 / 84 / 84 | 0 | 0/0 |
| uiseong_andong_2025/20250324T090000Z | 84 | 84 | 84 | 84 / 84 / 84 | 0 | 0/0 |
| uiseong_andong_2025/20250325T170000Z | 84 | 84 | 84 | 83 / 83 / 83 | 12 | 1/1 |
| yeongdeok_2025/20250325T190000Z | 90 | 90 | 90 | 86 / 86 / 84 | 26 | 7/7 |
| yeongdeok_2025/20250325T230000Z | 90 | 90 | 90 | 90 / 90 / 90 | 13 | 0/0 |
| yeongdeok_2025/20250326T080000Z | 90 | 90 | 90 | 90 / 90 / 90 | 5 | 0/0 |
| all/pooled | 522 | 522 | 522 | 517 / 517 / 515 | 56 | 8/8 |
<!-- END GENERATED: crosscheck -->

All recorded fields are reproduced from the original attempts. Every displayed difference comes from an origin with
re-checked attempts whose original attempts reproduce the recorded fields exactly (for example, timed-out attempts
that were re-checked as `checked_route` or `model_no_route`). The planner shows the re-check, so its deadline is the
re-checked one.

## Independent second computation

`verify.py` recomputes every key of `NUMBERS.json` with different code (`wfg_impact/path_b.py`, pandas + networkx):
attempts are rebuilt from the cache's `route_checks` (each check's own request), not from the dispatch plans' attempt
arrays; re-checks are substituted by `recheck_of` after checking that each re-check repeated its original request;
flame contact is read from `full_policy_assessment.per_scenario`, arrivals from the route `times_s`, lengths from
`node_ids`; redundancy uses networkx's Edmonds-Karp. It fails on any difference in value, numerator or denominator.
The tests run it.

## Reproduce

From the repository root, with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -c constraints-routing.txt './integration[packets]'
.venv/bin/python -m pip install -c constraints-routing.txt -r research/solve2027-impact/requirements.txt
.venv/bin/python tools/fetch_routing_inputs.py             # SHA-verified road graphs (only needed once)
.venv/bin/python research/solve2027-impact/compute.py       # path A: NUMBERS.json, tables, figures, generated text
.venv/bin/python research/solve2027-impact/verify.py        # path B: independent recomputation, exits 1 on mismatch
.venv/bin/python -m pytest -q research/solve2027-impact/tests
```

`compute.py --check` recomputes and fails if any committed text output (NUMBERS.json, tables, generated README blocks,
APPLICATION_SENTENCES.md, figure CSV twins) would change. On a shared 2-vCPU Linux container `compute.py` took under a
minute, `verify.py` about 2.5 minutes and the tests about 3.5 minutes, each below 1 GB peak memory. The numbers do not
depend on the host running this package: they are read from the recorded cache, not recomputed by the router.

## Inputs

All inputs are verified by SHA-256 before use (cache files against `planner/cache/INDEX.json`, graphs against the API
provenance in every cached route check). Full list with hashes: `NUMBERS.json` -> `inputs`.

<!-- BEGIN GENERATED: inputs -->
| Scope key | Cache file | SHA-256 | Scenario set | Hazard SHA-256 | Graph SHA-256 | Host | Created |
|---|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | `planner/cache/uiseong_andong_2025/20250323T010000Z.json` | `e94d3dfae1860f61…` | `ffb1:20250323T010000Z:da4a13e53bc0b6a2` | `21a8a087f419382b…` | `8c37e5b6440608bc…` | macOS-27.0.1-arm64-arm-64bit (1608 results) | 2026-10-17T22:54:04+00:00 |
| uiseong_andong_2025/20250324T090000Z | `planner/cache/uiseong_andong_2025/20250324T090000Z.json` | `53e54f019c540b51…` | `ffb1:20250324T090000Z:08721049cc48e045` | `cde0707dcd5bd8ed…` | `8c37e5b6440608bc…` | macOS-27.0.1-arm64-arm-64bit (1603 results) | 2026-10-17T22:54:05+00:00 |
| uiseong_andong_2025/20250325T170000Z | `planner/cache/uiseong_andong_2025/20250325T170000Z.json` | `f851a19ba71c0484…` | `ffb1:20250325T170000Z:53e6da7897bf9b5b` | `87c2ee0c367fad73…` | `8c37e5b6440608bc…` | macOS-27.0.1-arm64-arm-64bit (1630 results) | 2026-10-17T23:10:25+00:00 |
| yeongdeok_2025/20250325T190000Z | `planner/cache/yeongdeok_2025/20250325T190000Z.json` | `fad4d227e81e7d6c…` | `ffb1:20250325T190000Z:20cb6955b51ab0c6` | `fe33db2193742879…` | `f097e6c8d8bb4454…` | macOS-27.0.1-arm64-arm-64bit (1894 results) | 2026-10-18T00:10:31+00:00 |
| yeongdeok_2025/20250325T230000Z | `planner/cache/yeongdeok_2025/20250325T230000Z.json` | `b0700a1b288bf8d1…` | `ffb1:20250325T230000Z:c1b46f3c00c2036c` | `fa347cf3077fdbed…` | `f097e6c8d8bb4454…` | macOS-27.0.1-arm64-arm-64bit (1764 results) | 2026-10-18T00:24:29+00:00 |
| yeongdeok_2025/20250326T080000Z | `planner/cache/yeongdeok_2025/20250326T080000Z.json` | `a7f3fe90211dbb78…` | `ffb1:20250326T080000Z:d8d21b8e3ced8a48` | `0f468b69a569b2c2…` | `f097e6c8d8bb4454…` | macOS-27.0.1-arm64-arm-64bit (1730 results) | 2026-10-18T00:29:34+00:00 |
<!-- END GENERATED: inputs -->

## Population context: not included

The brief allowed the share of residents aged 65+ in the affected counties only from an official open source reachable
without an API key, cited exactly. The official resident-registration statistics (Ministry of the Interior and Safety,
`jumin.mois.go.kr`; KOSIS) are served through interactive forms or a keyed API, and a fetch of `jumin.mois.go.kr` was
not permitted from this environment. No population figure is used here, and none should be added without such a citation.

## Files

| Path | Content |
|---|---|
| `compute.py` | path A entry point: writes every output below |
| `verify.py` | path B entry point: recomputes and compares every number |
| `wfg_impact/` | `sources` (inputs, hashes), `planner_rules` (planner port), `api_rules` (API cross-check), `maxflow` (redundancy), `analysis`, `numbers`, `figures`, `sentences`, `path_b` |
| `NUMBERS.json` | every number with definition, value, numerator/denominator, scope, script, inputs; `headline` entries carry their input SHA-256 inline |
| `APPLICATION_SENTENCES.md` | 8 candidate sentences rendered from NUMBERS.json, with keys and cautions |
| `tables/origin_cases.csv` | one row per scenario set x origin (all 3 verdict cells per offset, deadlines, API fields, reasons) |
| `tables/travel_only_pairs.csv`, `tables/redundancy_places.csv` | per comparison / per place details |
| `tables/fig*_*.csv` | table twins of the figures |
| `figures/` | 3 figures, PNG + SVG |
| `tests/` | synthetic-case tests of the planner port and max-flow, and the full path A / path B reproduction |
| `requirements.txt` | pinned analysis dependencies |

## Key format

`<metric>@<scope>[#<subset>]`. Scope: `<region>/<input time>` (one scenario set), `<region>/pooled` or `all/pooled`
(place-input-time cases), `<region>/places` or `all/places` (distinct places). Subset: `#village`, `#care_facility`;
`#rc1` / `#rc2plus` for places with one / at least two edge-disjoint paths.
