# What the demo checks — and what it does not

## Checked on every emitted witness

| Rule | Constraint | Planner | Independent replay (`kcf_planner/replay.py`) | Existing repository logic (`wfg_sipp`) |
|---|---|---|---|---|
| R-EDGE / R-CONTIG | edges exist, connect head to tail, no time travel | yes | yes | JS-2, JS-5 |
| R-DURATION | `exit − entry = travel_s` | yes | yes | JS-3, JS-4 |
| R-CLOSED | no positive overlap of `[entry, exit)` with a closed interval | yes | yes | JS-8 (blocked departure seconds) |
| R-UNKNOWN | checked trips never overlap unknown intervals | yes | yes | JS-8 with unknown treated as blocked |
| R-HORIZON | exits and unloading end ≤ `horizon_s` | yes | yes | JS-3, JS-11 |
| R-TURN | forbidden consecutive pairs, incoming edge kept through waits and between legs | yes | yes | JS-5 (start state = previous leg's last edge) |
| R-BOARD | boarding `board_s`, starts ≥ availability/return, ends ≤ departure | yes | yes | — |
| R-WINDOW | arrival ≥ open, unloading end ≤ close, admission (edge) arrival only | yes | yes | JS-11 (acceptance set) |
| R-CAPACITY | people ≤ seats, people = group size | yes | yes | — |
| R-CONTINUITY | location, clock and incoming edge carry from trip to trip | yes | yes | leg start state/time |
| R-ASSIGN | parallel i→i; shuttle single vehicle, listed order | yes | yes | — |
| R-COVERAGE / R-STATUS | counts and `final_unload_s` match the witness | yes | yes | — |
| R-MISSING | MISSING_INPUT lists every touched unknown interval | yes | yes | — |
| optimality | earliest final unloading | DP over legs | brute-force oracle in tests | `sipp.solve` + `bruteforce.earliest_arrival` equal on the last leg of each vehicle |

`wfg_sipp` is imported read-only from `experimental/sipp-routing/src` (unchanged). JS identifiers refer to `experimental/sipp-routing/docs/JOURNEY_SAFETY_PREDICATE.md`.

## Not checked (explicit limits)

* **JS-9 peak flux and JS-10 cumulative dose / heat exposure:** the portable contract carries no thermal data. The richer research scenario's separate peak-flux and dose checks are not run; final cumulative heat exposure stays unresolved, as in the archived Uiseong–Andong exercise.
* Physical road status, traffic, smoke, visibility; the "closed" intervals are a simulated restriction.
* Destination capacity/readiness, driver availability, resident health, boarding-time variability.
* Vehicle interaction and road capacity (two vehicles may use the same road at once).
* Node hazards: nodes are assumed supported and open (the research kit also tracks node/cell support).
* Forecast provenance: an `unknown` interval imitates a missing new-burn-probability input; the research distinction between missing forecast data, out-of-horizon time, unresolved computation and model-scoped infeasibility is preserved as `MISSING_INPUT`, `OUT_OF_HORIZON`, `UNRESOLVED` and `MODEL_SCOPED_NO_ROUTE`.

The demo additionally flags (for a person, not as a failure): traversals within 300 s of a closed/unknown interval (`TIGHT_MARGIN`), every hold and its location, groups awaiting transport, and the unmodelled items above.
