# F-BASE: an independent exact baseline for the router (design and frozen comparison rules)

Owner: Marcus. Stream from the FIRE direction document §7.1. Status: **design and rules committed before any run.**

## Problem (as defined by the O2 integer instance)

The input is Thomas's independently re-derived integer instance in the `.wfgc` `INSTANCE` block (F-3.2 `FORMAT.md`, PR #116).
- **States.** A state `s` is the incoming edge: `s ∈ {0..nE-1}`, plus `s = nE` for the origin start state. The state's node is `hd(s)`.
- **Moves from `(s, t)`.**
  - **Edge `j`:** allowed when `tail[j] = hd(s)`, `(s, j)` is not forbidden, `t ∉ EB_j` and `t + D_j ≤ H`. It leads to `(j, t + D_j)`, and that arrival is *admitted*.
  - **Wait:** allowed when `hd(s)` is waitable and `t ∉ WB_hd(s)`, with `t + 1 ≤ H`. It leads to `(s, t + 1)` and is *not admitted*.
- **Goal.** The smallest admitted arrival time `T` with `T ∈ AC_hd(state)`, starting from `(s0, dep)`, which is admitted (the `k = 0` case). If none exists by `H`, the verdict is NO_ROUTE.

This is the contact relaxation of the router only. Radiation, peak and dose obligations are out of scope, exactly as for F-3.2's certificates.

## Exact baseline (F-BASE-X)

Forward label sweep with **interval-set labels**, one set of reachable seconds per state, not a single earliest time.

- **Why sets.** At a non-waitable node a later arrival can depart on an edge whose departure window was blocked earlier, so earliest-arrival dominance is invalid (F-3.2 spec).
- **Ordering.** States are processed in chronological order of interval starts, with a priority queue keyed by the earliest unprocessed second of each state.
- **Waiting.** At waitable nodes waiting closes each reachable interval forward, until the next blocked wait-start second (inclusive of the arrival second).
- **Edges.** Each edge maps a reachable set `S` to `(S \ EB_j) + D_j`, intersected with `[dep, H]`.
- **Termination.** The first admitted arrival in an acceptance set gives `T`, and a parent pointer per (state, interval) reconstructs a witness. The search stops when the queue empties (NO_ROUTE) or when the earliest unprocessed second exceeds the best `T`.
- **Independence.** Integers only. No code shared with `experimental/sipp-routing` (the router), Richard's F-3.1 deadline field or Thomas's checkers and generators. It reads only the `INSTANCE` block.
- **Self-check.** Every ROUTE witness is replayed by an independent lattice walker in the same module, and every result is fed to Thomas's checker: Python, and C where it builds.

## Naive baselines (what they get wrong is the informative part)

- **N1, classic time-dependent Dijkstra.** One earliest label per state, waiting assumed allowed everywhere (the FIFO idealisation). At a blocked departure it waits at any node. It can claim routes that need waiting at non-waitable nodes, so it is unsound.
- **N2, earliest label with waiting rules.** One earliest label per state, waiting respected, so a blocked departure at a non-waitable node is a dead end. It can miss routes that need a later arrival, so it is incomplete: false NO_ROUTE or a late T.
- **N3, no acceptance windows.** N1 or X with the destination accepted on first arrival. It can report a T before the destination opens.

For each naive baseline we report the disagreements on the 20 missions and on the 140-request departure sweep, and the **smallest failing instance**. The smallest instance is found by delta-debugging the instance (removing edges, intervals and nodes while the disagreement persists) and by hand-built 3–5 node cases.

## Frozen comparison rules (fixed before running)

1. **Instances.** The 20 frozen native-panel missions, instance bytes produced by F-3.2 at its frozen commit (PR #116 head `a03f218`). The instance sha256 (FORMAT.md identity rule) is recorded per mission. If they are available, the 140 departure-sweep requests are a second, separately reported set.
2. **Reference results.** The recorded SIPP results: 15 ROUTE arrival seconds and 5 NO_ROUTE, per F-3.2 claim 2, read from F-3.2's committed `results/panel_summary_*.json`. No other reference is used for agreement.
3. **Agreement.**
   - Verdicts must be identical, ROUTE or NO_ROUTE.
   - For ROUTE, `T` must be equal to the second.
   - Any difference is a disagreement to be explained, never tolerated: an instance error, a baseline bug, or a router discrepancy, in that order of suspicion.
   - Witness acceptance by Thomas's checker is reported separately.
4. **Cost.**
   - Wall time and peak RSS per mission, each solver in a fresh process on the same host, single thread.
   - Instance parse time is reported separately from search time.
   - Comparators: the router (`run_panel.py`'s SIPP search on the same mission) and Richard's F-3.1 field, using their own commands.
   - Timings are host-specific. The median of 3 runs is reported, and no speed claim is made across hosts.
5. **Naive baselines.** Disagreement counts per class (unsound ROUTE, false NO_ROUTE, late T, early T) and the smallest failing example per baseline. Each smallest example is committed as a `.wfgc` instance with Thomas's checker verdict on the exact baseline's answer.
6. **Second baseline.** A published exact method for time-dependent shortest paths with waiting restrictions, requested from Sofia: for example Orda & Rom-type waiting-policy results, or an exact resource-constrained / time-expanded formulation. It is matched under the same rules if one is identified and feasible.
7. **No retuning.** Rules 1–5 are fixed by this commit. Any change is a new dated section, and results are reported under both the old and the new rule.

## Not in scope

Full-policy obligations (radiation, peak, dose); fire-model or scenario construction; any change to router code.
