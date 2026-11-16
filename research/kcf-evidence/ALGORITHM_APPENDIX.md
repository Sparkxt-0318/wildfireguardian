# Algorithm appendix

Code and design come from `research/harness-2026-11/F-3.1/` (`DESIGN.md`, `deadline_field/core.py`, `deadline_field/bruteforce.py`). The worked example is produced by the repository's own code: `python3 research/kcf-evidence/toy_example.py` (output reproduced below; run at the checkout this file was committed with).

## Part 1. The deadline field

**Question answered.** For an origin and a set of destinations, which departure seconds `t` (0 ≤ t ≤ H, H = 3,600) have a vehicle journey that is accepted (no flame contact while driving, waiting or staying; destination open for the whole stay)? The leave-by time is the largest such `t`. The forward method asked this once per origin, per 10-minute offset and per shelter (9,722 searches on the six recorded caches). The field answers it for every second, for every origin, with one backward pass per shelter set.

1. **Reduce the hazard to integer-second interval sets** (exact rational arithmetic, `deadline_field/real.py`). Per directed edge `j` with integer travel time `D_j ≥ 1`: `B_j` = start seconds at which driving the edge touches flame; `A_j` = arrival seconds at which arriving over `j` is accepted (head is a destination, opening window and horizon fit, and the destination stay is flame-free). Per node `v`: `W_v` = seconds at which a 1-second wait at `v` touches flame. Per origin `o`: `IB_o` = seconds at which the starting point is in flame. For the six recorded caches the full policy (flame, peak 10 kW/m², dose 100 kJ/m²) reduces to flame contact, checked per packet (`F-3.1/DESIGN.md` §2), so these sets are the whole constraint.
2. **State = an edge `s`** (the vehicle is at `head(s)` having arrived over `s`). For each state keep `R_s ⊆ {0..H}`: the seconds at which standing at `head(s)` (not freshly admitted, i.e. after a wait) an accepted completion exists. Let `G_s = R_s ∪ A_s`. Each set is a sorted list of disjoint integer intervals. No scalar "latest departure" is stored, because departing later is not always at least as good (a flame can pass).
3. **Equation.** `R_s = ⋃ over allowed next edges j (turn (s,j) not forbidden) of { t : t ∉ B_j and t + D_j ∈ G_j }`, plus, if `head(s)` is waitable, `{ t : t ∉ W_head(s) and t + 1 ∈ R_s }`. A wait never re-admits: acceptance is checked only on arrival over an edge.
4. **Seed** a max-heap (ordered by upper end of the piece) with every `A_j`.
5. **Propagate backward.** Pop a piece `[lo, hi]` of `G_j`. Each allowed predecessor `s` (an edge into `tail(j)`) receives `([lo, hi] − D_j) ∩ [0, H]`, minus `B_j`, minus what `R_s` already holds. Every genuinely new piece is added to `R_s` and pushed.
6. **Waiting closure.** If `head(s)` is waitable, a new piece `[lo, hi]` also extends downward to `w + 1`, where `w` is the largest wait-blocked second below `lo`: if you can be there at `lo` you could have been there earlier and waited.
7. **Stop at the fixed point.** The operator is monotone on a finite lattice and every move costs at least 1 s, so the time-expanded graph is acyclic and the fixed point is unique; processing order changes only speed. Cost grows with the number of interval pieces, not with H × edges.
8. **Read off an origin.** Feasible departures `= (⋃ over edges j out of o of (G_j − D_j) \ B_j, wait-closed if o is waitable) \ IB_o`. The exact deadline is its maximum; the planner's grid answer is the largest 10-minute offset inside it; the planner deadline is the maximum over the origin's shelters.
9. **Witness.** For any feasible second `t`, a forward search over time, pruned to states inside `G`, returns the earliest arrival and a concrete journey. Every witness is replayed with both contact rules and the unchanged full checker.
10. **Certificate.** `check_fixed_point` recomputes the right-hand side of step 3 from the stored sets and requires equality for every state. Equality proves `R` is the unique solution (induction on time from H downward), given step 1's sets. Separately, a brute-force forward oracle on random small instances (`tests/test_field_vs_oracle.py`) and per-second comparison against the kit's dense sweep (`deadline_field/crosscheck_kit.py`) test the implementation.

### Worked example (6 nodes, 7 directed edges, H = 60)

Nodes 0–5; origin 0; shelter 5 with a 5-second stay, so any arrival over an edge into 5 at `t ≤ 55` is accepted. No node is waitable.

| edge | route | D (s) | flame blocks starts `B` | accepted arrival `A` |
|---|---|---:|---|---|
| e0 | 0→1 | 10 | – | – |
| e1 | 1→5 | 10 | 18–60 | 0–55 |
| e2 | 0→2 | 15 | – | – |
| e3 | 2→3 | 15 | – | – |
| e4 | 3→5 | 15 | – | 0–55 |
| e5 | 1→4 | 5 | – | – |
| e6 | 4→5 | 8 | 14–40 | 0–55 |

Fast route 0→1→5 takes 20 s but e1 burns from t = 18 to the end. Detour 0→1→4→5 takes 23 s but e6 burns 14–40. Slow route 0→2→3→5 takes 45 s and is never blocked.

Backward pass (steps 4–7), listed by dependency (the heap pops in a different order, which changes only speed, step 7):

| step | piece popped | predecessor and arithmetic | new piece in `R` |
|---|---|---|---|
| seed | `A_e1 = [0,55]` | e0: `[0,55] − 10 = [0,45]`, minus `B_e1 = [18,60]` | `R_e0 += [0,17]` |
| seed | `A_e4 = [0,55]` | e3: `[0,55] − 15 = [0,40]` | `R_e3 = [0,40]` |
| seed | `A_e6 = [0,55]` | e5: `[0,55] − 8 = [0,47]`, minus `B_e6 = [14,40]` | `R_e5 = [0,13] ∪ [41,47]` |
| next | `R_e3 = [0,40]` | e2: `[0,40] − 15 = [0,25]` | `R_e2 = [0,25]` |
| next | `R_e5` pieces | e0: `[0,13] − 5 = [0,8]` (already held); `[41,47] − 5 = [36,42]` | `R_e0 += [36,42]` |

Final sets (printed by the repository's `backward`):

| edge | `R` | `G = R ∪ A` |
|---|---|---|
| e0 (at node 1) | 0–17, 36–42 | 0–17, 36–42 |
| e1, e4, e6 (at shelter) | – | 0–55 |
| e2 (at node 2) | 0–25 | 0–25 |
| e3 (at node 3) | 0–40 | 0–40 |
| e5 (at node 4) | 0–13, 41–47 | 0–13, 41–47 |

Origin 0 (step 8): via e0, `G_e0 − 10 = [0,7] ∪ [26,32]`; via e2, `G_e2 − 15 = [0,10]`. Union: **departures 0–10 and 26–32; deadline LD = 32.**

What the numbers say. Leaving at 10 uses the slow route and arrives at 55. Leaving at 11–25 fails on every route: the fast road is in flame by the time you reach it, the detour reaches e6 inside 14–40, and the slow route arrives after 55. Leaving at 26 works again, because the detour reaches e6 at second 41, after its flame ends (earliest arrival 49). Leaving at 32 arrives at node 1 at 42, drives e5 to 47 and e6 to 55, finishing the 5 s stay at 60 = H. Leaving at 33 would arrive at 56 > 55, so 32 is the last second. This is why the field keeps whole interval sets: the feasible set has a hole, and "latest feasible departure" is not the same as "leave as late as the first feasible one allows".

Verification of the example (step 10): `check_fixed_point` passes on all 7 states, and the brute-force oracle (plain Python sets, one departure at a time, no interval code) agrees with the field at every second 0–60 (feasible: 0–10 and 26–32). Output: `research/kcf-evidence/toy_example.py`.

Real data differ in one respect worth saying: on the six caches no state ever has more than one interval (`F-3.1/results/SUMMARY_final_70f70d7.json`, `piece_stats.*:max_intervals_per_state` = 1), so there the feasible sets have no holes. The hole above is built into the toy to show why the representation does not assume that.

## Part 2. The calibrated reach rule

**Not written.** I searched `Main` (all `.md`, `.py`, `.json` files, plus GitHub code search for "calibrated reach", "reach rule", "reach_rule") and `codex/experimental-corridor-router-v8` (`git grep -i reach`). Neither contains a rule by that name. The only hits for "reach" are unrelated: a research-scout note on the 행안부/산림청 plan ("land the fire can reach within 5 h", `research/harness-2026-11/research-scout/MISSION_A.md`, row K8), and the phrase "optimistic full reachable set exhausted" in the corridor router's no-route proofs. I did not guess which of these, or which other branch, you meant, because a ten-step appendix of an invented rule would look authoritative and be wrong. Tell me the file or branch (or paste the definition) and I will write it in the same form: at most ten numbered steps and a worked example on the same 6-node graph.
