# SIPP for the contact-only relaxation: equivalence and cost (track 1C-2)

**Equivalence first.**

| Check | Result |
|---|---|
| 20 frozen Korean missions, 2 repetitions, frozen sweep versus SIPP (status and arrival second) | **20/20 missions identical in both repetitions (40/40 execution pairs)**; 15 routes, 5 model-scoped refusals; 0 unresolved |
| Same 9 missions with first-new ignitions, members = first K export v3 trajectories, K = 1 ... 256 | **81/81 pairs identical** |
| Random abstract instances against a brute-force time-expanded search | **10,000/10,000 identical** (5,000 Hypothesis-structured, 5,000 dense seeded); 8,312 have a journey, 1,688 do not; in 1,244 the blocked intervals change the travel-only answer; all 8,312 witnesses are legal lattice journeys |
| Random geometric instances, SIPP front end against the frozen sweep | **2,000/2,000 identical** |

**Cost on this host (Linux, shared, 4 vCPU; not comparable with the frozen native-Mac timings).** SIPP was faster in **40/40** paired executions. The median planner-time ratio SIPP/sweep was **0.39** (range 0.11 to 0.72), and the median complete-execution ratio (imports, input loading and planning) was **0.51**. On the largest panel (Yeongdeok, 111,924 directed edges, 1,527 of 56,369 nodes waitable) the median planner time was **4.6 s against 9.5 s**. Peak RSS was 409 MiB against 441 MiB at most, inside the 3,072 MiB allowance. No execution came near the 30 s deadline.

Equivalence argument and assumptions: `docs/SIPP_EQUIVALENCE.md`. Journey-safety predicate with requirement identifiers and traceability: `docs/JOURNEY_SAFETY_PREDICATE.md`. Code: `experimental/sipp-routing/`.

## What was compared

Both solvers decide the same exact contact-only relaxation (dose and peak relaxed) of each frozen mission on the frozen packet's members, using the same exact activity intervals (`ContactModel`, equal to the kit's `RoadBoundModel.cell_intervals` by test). The sweep is the frozen `integration/kit/phaseB/zsweep.py::contact_sweep` imported unchanged (pinned SHA-256 `04b7387f...`); only its witness re-check was replaced by a structure check, because the per-member check is done separately in this track. The comparison is planner against planner. It is not the kit's complete request, which also builds radiation bounds and runs the whole-road checker; a speed-up of the planner alone says nothing about the complete request.

Protocol (`run_cost_study.py`): for every mission in panel order, repetition 1 runs sweep then SIPP and repetition 2 runs SIPP then sweep (ABBA). Each execution runs in a fresh `python -I` child under the 30 s complete-execution deadline (the child is killed at 30 s and recorded as unresolved) and a 6 GiB address-space safety limit. A peak RSS above the 3,072 MiB allowance would be recorded as a memory stop; none occurred. Repetitions are not independent missions.

## Cost table (rep 1 and rep 2 pooled, medians per panel, this host)

| Panel | Executions per solver | Sweep planner (s) | SIPP planner (s) | Sweep complete (s) | SIPP complete (s) | Max RSS sweep / SIPP (MiB) |
|---|---:|---:|---:|---:|---:|---|
| Hongseong 2023 | 8 | 0.124 | 0.024 | 0.223 | 0.121 | 43 / 41 |
| Miryang 2022 | 8 | 0.223 | 0.064 | 0.361 | 0.167 | 48 / 44 |
| Uiseong-Andong 2025 | 8 | 2.758 | 1.231 | 2.974 | 1.453 | 162 / 159 |
| Uljin 2022 | 8 | 0.986 | 0.365 | 1.149 | 0.498 | 93 / 76 |
| Yeongdeok 2025 | 8 | 9.468 | 4.626 | 10.025 | 5.157 | 441 / 409 |

Per-execution rows: `PAIRED_EXECUTIONS.csv` and `data/cost_executions.jsonl`; summaries in `RESULTS.json`.

Where the time goes. The sweep visits state-seconds: up to 195 million (edge, second) states for Yeongdeok FD1, 99 million for Yeongdeok FX2. SIPP creates 655,774 and 74,597 pieces on those missions, and 128 to 51,612 pieces on the other missions. Building the SIPP instance takes a large share of SIPP's time: the blocked-interval sets, the successor lists and the exact occupancy geometry of candidate edges (`fig03`). SIPP's search is fast when few pieces are needed. Refusals (exhaustion) are the expensive case for both solvers.

States versus members (`fig02`, `data/members_scaling.jsonl`). Adding members does not fragment the safe intervals much on this panel, because few member ignitions touch road edges. The piece count stays flat in K, except for jumps where more members block the earliest corridor. Examples: Uiseong-Andong 2025-03-23 FX2 changes route at K = 4 (2,540 s to 2,646 s) and becomes a refusal at K = 32; Uljin FW2 becomes a refusal at K = 16. A refusal costs SIPP up to 572,400 pieces (5.2 s on this host). At K = 128 and 256, Uljin FW2 has no acceptable destination second at all, so SIPP exhausts with 0 pieces.

## Figures

- `figures/fig01_time_vs_sweep_paired` (PNG 300 dpi and SVG). Planner wall time of the frozen sweep (x) against SIPP (y) for every execution pair (20 missions, 2 repetitions), log-log, coloured by panel, with the identity line. Host-specific Linux measurements on a shared host (load average 5.3 to 6.2 during the run).
- `figures/fig02_states_vs_members`. SIPP pieces created against the number of planning members K (first K export v3 trajectories, uniform sub-hour timing) for the 9 missions whose windows have first-new ignitions, log-log; points with 0 pieces (Uljin FW2 at K = 128 and 256, no acceptable destination second) cannot be drawn on the log scale.
- `figures/fig03_largest_panel_breakdown`. Complete execution time split into imports and input loading, setup (sweep static structures; SIPP instance) and search, for the four Yeongdeok missions, repetition 1, sweep (left) and SIPP (right). The prompt asked for a Caldor breakdown; the Caldor/Rim inputs are not on this host, so the largest Korean panel is shown instead.

## Not run here

- Caldor/Rim (6 missions): the sealed-study packets are not on this host; the Caldor cost comparison remains open.
- The chance-constrained variant (6a, subset enumeration) is implemented in `wfg_members.decide` (exact, with a shared-bound shortcut and free members) and used by the 1C-1 and 1C-3 campaigns. The bitset-label variant (6b) was not implemented, and no state-growth study up to m = 16 was made for 6b.
- Dose is handled by lazy constraint generation in the decision procedure (`wfg_members.decide`); dose never bound on the 20 missions, so the lazy loop was never exercised on real inputs.

## Reproduce

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -c constraints-routing.txt './integration[packets]' -r experimental/sipp-routing/requirements-test.txt
python tools/fetch_routing_inputs.py
python research/sipp-routing/property_census.py              # data/property_census.json
python research/sipp-routing/run_cost_study.py --exports EXPORTS_V3   # EXPORTS_V3 from research/scenario-members/make_exports_v3.py
python research/sipp-routing/analyze.py
```

Seeds: Hypothesis derandomised (no database); dense instances seeds 0..4999; export v3 seed 0, sub-hour timing seed 20261029. Inputs: release research-final-20261015, archive SHA-256 `d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202`, `INPUT_FILES.json` SHA-256 `5d820b97740d879d2bc78a76d1b5854420793c927c6315f656dc1c2927b35235`, read at `/home/user/wfg-shared/routing-inputs`. Host: Linux container, 4 vCPU, 15 GiB, no GPU, Python 3.12.3, NumPy 1.26.4, shared with two other track agents.

## Scope and limits

- The equivalence holds for the contact-only relaxation under the assumptions of `docs/SIPP_EQUIVALENCE.md`: integer seconds, FIFO edges, waits only at waitable nodes, cost equal to arrival time, node issue positions. A refusal is model-scoped: it is conditional on the supplied members, graph, lattice and horizon.
- The finite tests (10,000 abstract and 2,000 geometric instances, 20 missions) show agreement on these cases; the general argument is in the equivalence note. Neither is a machine-checked proof.
- Timings are from one shared Linux host and are planner-only. No universal speed-up is claimed, and the frozen kit's complete request time is not measured here.
- Nothing here concerns physical safety: "safe interval" is the technical term defined in `docs/SIPP_EQUIVALENCE.md`.
