# F-3.1 Deadline field: every leave-by time from one backward search per shelter

The planner's leave-by time (출발 마감) is the latest departure that still has a checked vehicle route. It was
computed by brute force: one forward route check per origin, per 10-minute offset and per candidate shelter. That is
9,722 checks for the six recorded 2025 caches, each with a 30 s budget.

This directory computes the same deadlines another way. For each shelter it runs one exact **backward** pass over
road states. The pass yields, for every road state, the set of departure seconds from which an accepted journey
still exists. Each recorded attempt is then read off that field, and the forward witness is replayed with both
contact rules.

* Design, state definition and correctness argument: [DESIGN.md](DESIGN.md)
* Results and evidence: [RESULTS.md](RESULTS.md)

## Layout

| path | what |
|---|---|
| `deadline_field/intervals.py` | integer interval sets |
| `deadline_field/core.py` | abstract instance; `backward` (event-driven least fixed point); `issue_set`; `witness` (A* pruned to the field); `check_fixed_point` (order-independent certificate) |
| `deadline_field/bruteforce.py` | independent exhaustive forward oracle (plain sets, one departure at a time) |
| `deadline_field/real.py` | exact blocked intervals from the frozen graph and hazard packet (router rule, closed-footprint rule); full-policy-to-contact precondition |
| `deadline_field/reproduce.py` | reads every planner attempt and every route-check job of a cache file off the fields; exact deadlines |
| `deadline_field/analyze.py` | agreement tables, deadlines, compute |
| `deadline_field/crosscheck_kit.py` | per-second comparison with the kit's frozen dense sweep `zsweep.EarliestArrivalBound` |
| `tests/` | oracle property tests, certificate and mutation test, real-data mask equality |

## Reproduce

Python 3.12 or 3.13 with numpy; `pip install pytest hypothesis`. Run from the repository root.

```sh
python3 tools/fetch_routing_inputs.py                       # frozen graphs + packets, SHA-verified (76 MB)
cd research/harness-2026-11/F-3.1
python3 -m pytest -q -p no:cacheprovider tests              # ~30 s
python3 -m deadline_field.reproduce ../../../planner/cache/uiseong_andong_2025/20250323T010000Z.json --out /tmp/f31/ua0323.json
python3 -m deadline_field.analyze /tmp/f31/ua0323.json
python3 -m deadline_field.crosscheck_kit ../../../planner/cache/uiseong_andong_2025/20250323T010000Z.json --pairs 2 --out /tmp/f31/kit.json
```

Large outputs (per-attempt witnesses) are written outside git. Only summaries are committed.
