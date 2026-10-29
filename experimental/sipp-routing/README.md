# Safe Interval Path Planning for the contact-only relaxation (track 1C-2, opt-in overlay)

**Headline.** SIPP returns the same status and the same arrival second as the frozen contact sweep (`integration/kit/phaseB/zsweep.py`) on **20/20 frozen Korean missions in both repetitions**. It also agrees with a brute-force time-expanded search on **10,000/10,000 random instances** and with the frozen sweep on **2,000/2,000 random geometric instances**. Cost, state counts and the equivalence argument: `research/sipp-routing/README.md`, `docs/SIPP_EQUIVALENCE.md`, `docs/JOURNEY_SAFETY_PREDICATE.md`.

This package imports track 1C-1 (`experimental/scenario-members/src/wfg_members`: the pinned frozen-kit loader, the planner result layout and the contact model). It never edits a frozen file.

## Contents

| Path | Role |
|---|---|
| `src/wfg_sipp/sipp.py` | SIPP on an abstract instance: pieces (state, interval of reachable seconds, last edge-arrival second); earliest-label dominance at waitable heads (Phillips and Likhachev 2011), set-inclusion dominance at non-waitable heads; best-first on lo + h with a consistent travel-time bound; goal candidates from raw edge-arrival runs; witness reconstruction. |
| `src/wfg_sipp/frontend.py` | Geometry: blocked departure seconds per edge from the frozen `core.edge_occupancies` and exact activity intervals (the sweep's rule), blocked wait seconds, acceptance sets; `sipp_plan(graph, request, model, *, extra_blocked=None, wall_s)` with the planner interface of `wfg_members.planner` (statuses CONDITIONAL_OPTIMUM, PROVEN_INFEASIBLE, DISCONNECTED, AT_ISSUE_FAILURE, TIMEOUT). `extra_blocked` carries lazy constraints. |
| `src/wfg_sipp/bruteforce.py` | Brute-force second-by-second reference and a lattice witness checker. |
| `src/wfg_sipp/predicate.py` | The journey-safety predicate (JS-1 to JS-12), written from the mathematics, independent of the search. |
| `src/wfg_sipp/intervals.py` | Closed integer interval sets. |
| `tests/` | Property tests (Hypothesis): equivalence with the brute force on 5,000 structured and 5,000 dense seeded instances, metamorphic tests, the predicate clauses one by one, and 2,000 geometric instances against the frozen sweep. |

## Tests

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -c constraints-routing.txt './integration[packets]' -r experimental/sipp-routing/requirements-test.txt
python -m pytest experimental/sipp-routing/tests     # about 2 minutes on this host; WFG_SIPP_CASES / WFG_SIPP_GEOMETRIC_CASES override counts
```

## Scope

SIPP decides the contact-only relaxation exactly (dose and peak relaxed), under the assumptions listed in `docs/SIPP_EQUIVALENCE.md` section 4: integer seconds, FIFO edges, waits only at waitable nodes, cost equal to arrival time, a node issue position. Dose and peak are checked after planning; lazy cuts make any later exhaustion an unresolved outcome, never a refusal. A refusal is model-scoped: it concerns the supplied members, graph, lattice and horizon, not every real-world escape.
