# F-3.2 certificate definition and soundness argument (draft 1, for review)

Status: **design decision awaiting verification (Hannah) and assessment (Iris).** Nothing here is a result claim yet.

## 1. What is certified

The object certified is the **integer-clock contact relaxation** `L(I)` of one routing request, i.e. the abstract
instance `I` built by `experimental/sipp-routing/src/wfg_sipp/frontend.py:build_instance` and solved by
`wfg_sipp/sipp.py:solve` (documented in `experimental/sipp-routing/docs/SIPP_EQUIVALENCE.md`).

Instance `I = (V, E, tail, head, D, origin, s0, F, waitable, EB, WB, AC, dep, H)`, all integers:

- states `s in {0..|E|}`: `s < |E|` is "just traversed directed edge s"; `s = |E|` is the issue sentinel. `hd(s)` is
  `head[s]`, or `origin` for the sentinel. `s0` is the start state.
- `D_j >= 1` travel seconds of edge `j`; `F` forbidden (incoming state, outgoing edge) pairs.
- `EB_j` blocked departure seconds of edge `j`; `WB_n` blocked wait-start seconds of node `n`; `AC_n` acceptance
  seconds of destination node `n` (opening interval, full dwell inside the horizon, dwell contact-free). Each is a
  normalised list of closed integer intervals.
- Lattice points `(s, t, a)`, `t` an integer second, `a in {0,1}` (admitted edge arrival or not).
  - Init: `(s0, dep, 1)`.
  - EDGE: from `(s,t,*)` to `(j, t+D_j, 1)` iff `tail[j] = hd(s)`, `(s,j) not in F`, `t not in EB_j`, `t+D_j <= H`.
  - WAIT: from `(s,t,*)` to `(s, t+1, 0)` iff `waitable[hd(s)]`, `t not in WB_hd(s)`, `t+1 <= H`.
  - Goal: a reachable `(s,t,1)` with `t in AC_hd(s)`. Its arrival is `t`.

`OPT(I)` = least goal arrival, or "none". A relaxed journey is a lattice path from Init to a goal.

## 2. Certificate

A certificate is `C = (T, {R_s, A_s})` with an integer threshold `dep <= T <= H+1` and, per state, normalised
interval sets `A_s ⊆ R_s ⊆ [dep, H]` (absent state = empty sets). Only times `< T` matter.

Checker conditions (every one is a local, search-free test):

- **C0 form:** integers, sorted, disjoint, non-adjacent intervals; `A_s ⊆ R_s`; bounds inside `[dep, H]`.
- **C1 init:** if `dep < T` then `dep in A_s0`.
- **C2 EDGE closure:** for every state `s` and every edge `j` with `tail[j] = hd(s)`, `(s,j) not in F`:
  `{ t + D_j : t in R_s \ EB_j, t + D_j <= min(H, T-1) } ⊆ A_j`.
- **C3 WAIT closure:** for every state `s` with `waitable[hd(s)]`:
  `{ t + 1 : t in R_s \ WB_hd(s), t + 1 <= min(H, T-1) } ⊆ R_s`.
  (Equivalently: every maximal interval `[lo,hi]` of `R_s` with `hi + 1 <= min(H,T-1)` has `hi in WB_hd(s)`.)
- **C4 goal-free:** for every state `s`: `A_s ∩ AC_hd(s) ∩ (-inf, T-1] = ∅`.

Claims:

- **Infeasibility claim** (`NO_ROUTE` in `L(I)`): certificate with `T = H+1`, no route.
- **Optimality claim** (`ROUTE` with arrival `T`): certificate with threshold `T`, **plus** a primal witness: a legal
  lattice path (legs EDGE `j` `[t, t+D_j]`, WAIT `n` `[t, t+1]`) from Init to a goal with arrival exactly `T`, checked
  edge by edge against the same `F`, `EB`, `WB`, `AC`, `H` and the admission rule.

## 3. Soundness: checker accepts ⇒ claim true in `L(I)`

**Lemma (invariant).** If C0–C3 hold, then every reachable lattice point `(s,t,a)` with `t < T` has `t in R_s`, and
`t in A_s` when `a = 1`.

*Proof.* Induction on `t`. Init `(s0,dep,1)`: C1. Any other reachable point `p = (s',t',a')` has a predecessor
`q = (s,t,*)` with a legal transition `q -> p`. Every transition strictly increases time (`D_j >= 1`, WAIT `+1`), so
`t < t' < T` and, by induction, `t in R_s`. If the transition is EDGE `j` it is legal so `t not in EB_j`,
`t' = t + D_j <= H` and `t' <= T-1`; C2 gives `t' in A_j` (and `A ⊆ R`). If it is WAIT, `waitable[hd(s)]`,
`t not in WB_hd(s)`, `t' = t+1 <= min(H,T-1)`; C3 gives `t' in R_s`; WAIT arrivals have `a' = 0`, so no `A` duty. ∎

**Theorem.** If C0–C4 hold, `L(I)` has no goal with arrival `< T`. With `T = H+1`: `L(I)` has no relaxed journey at all.
With a checked primal witness of arrival `T`: `OPT(I) = T`.

*Proof.* A goal `(s,t,1)` with `t < T` would, by the Lemma, have `t in A_s ∩ AC_hd(s)`, contradicting C4. All arrivals
are `<= H`. The witness shows a goal at `T` exists. ∎

**Completeness.** The exact reachable set truncated at `T` (`R_s` = all reachable `t < T` in state `s`, `A_s` = the
admitted ones) satisfies C0–C4 whenever the claim is true, so a true claim always has a certificate. It is also the
*smallest* certificate: deleting any single point from it violates C1, C2 or C3 (its predecessor is still in `R`).
This gives an exhaustive single-point-deletion mutation test.

**Why one earliest label per state is not enough.** A scalar `L_s` ("earliest reachable time") asserts that every
`t >= L_s` behaves like `L_s`. That holds only where waiting is free. At a non-waitable node, a later arrival can depart
into an edge's safe interval that the earliest arrival cannot reach; at a waitable node a blocked wait second
`t in WB` cuts the run. Both cases need the reachable set as an interval *set*. Where `hd(s)` is waitable and `WB` is
empty past `L_s`, the certificate degenerates to `R_s = [L_s, min(H,T-1)]`, i.e. the scalar label, so the interval-set
form is a strict generalisation. (The repository's own SIPP equivalence note makes the same point about dominance.)

## 3a. Complement (backward) form

A backward field gives, per state, the seconds `Gr_s` from which a non-admitted point can still reach a goal before
`T`, and `Ga_s = Gr_s ∪ (AC_hd(s) ∩ [dep, lim])` for admitted points. Its complement
`R_s = [dep,lim] \ Gr_s`, `A_s = [dep,lim] \ Ga_s` is the *largest* set satisfying C2–C4, and it satisfies C1 exactly
when the start cannot complete before `T`. So the same C0–C4 check verifies a backward certificate; only the encoding
differs (`COCERT`, FORMAT.md). Soundness is the theorem of §3 unchanged, because the checker materialises `R`, `A` and
checks C0–C4 on them. The exact forward set and the exact backward field are disjoint below `T` whenever the claim is
true (a point in both would lie on a journey arriving before `T`); the generator tests this.

## 4. Checking cost

For each (state, out-edge) pair the checker merges `R_s` against `EB_j` and tests inclusion in `A_j`; for each waitable
state it scans `R_s` against `WB`. Cost `O(Σ_s |R_s|·outdeg(s) + Σ_j (|EB_j| + |A_j|)·indeg(j) + Σ_n |AC_n|·indeg(n))`,
i.e. linear in (edges × intervals) for bounded degree. No priority queue, no heuristic, no search. All arithmetic is
integer addition and comparison.

## 4a. Relaxation refusal ⇒ full-policy refusal (justification and premises)

Claim: if `L(I)` has no journey arriving before `T`, the full policy (frozen independent journey checker
`experimental/synthetic-truth/src/wfg_synthetic_truth/frozen_checker.check_route`) admits none either, for the same
graph, request and hazard. Argument: every journey the full checker accepts (i) has legs on the `dt = 1` lattice
starting at the integer departure (`_shape`: "off lattice leg", contiguity), so all its departures are integer
seconds; (ii) uses legal turns, declared waits and the exact edge durations (`_shape`); (iii) has no `FLAME_CONTACT`
on any leg occupancy, node wait or dwell, and no `MISSING_SUPPORT` (`_charge`). By (i)–(ii) it is a lattice path of
`L(I)`; by (iii), under premise P1 below, none of its EDGE departures lies in `EB`, no WAIT start in `WB`, and its
arrival lies in `AC`. So it is a relaxed journey with the same arrival. Peak and dose only remove further journeys.

Premises (not proved here): **P1** the flame activity that the full checker samples from `HAZARD.json` equals the
per-cell half-open intervals `ContactModel.cell_intervals` derives from the packet arrays (asserted and tested in
`experimental/scenario-members`, "tested for equality on the frozen packets"; independently corroborated here only for
the 15 route witnesses, all `CHECKED_ROUTE`); **P2** the instance re-derivation of O2 (checked: 0 differences, 20
missions); **P3** the full checker's lattice and contact rules are the policy (they are the frozen definition).

**Integer seconds (Iris, point 4).** No lemma can remove this as a statement about continuous time: with a point
occupancy at fraction 1/2 of a 10 s edge (its other cells inactive) and activity intervals leaving a safe gap `[5.2, 5.7)` at that cell, the
departures `t ∈ [0.2, 0.7)` are safe and no integer departure is. So "no integer-second journey" does not imply "no
real-time journey". It does not affect the implication above, because the full policy itself admits only
integer-second departures (i); it is a boundary of the policy model, shared by every result on this lattice.

**Hazard extent.** Every certificate is relative to the hazard it was given. Each bundle has a provenance sidecar
(`*.wfgc.json`) with the sha256 of graph, request, `HAZARD.json`, packet arrays and build summary, the hazard grid
extent and validity window, and the packet's unknown-state counts (e.g. Uljin 03Z: 1,659 of 3,596 cells with unknown
burned state). Burning outside the packet domain or in cells the model treats as unsupported is outside the claim.

## 5. Scope boundary (what the certificate does NOT prove)

1. **Relaxation only.** It certifies the contact relaxation exactly. Peak flux, cumulative dose and continuous-road
   radiation bounds (law v1/v2) are separate obligations. Because the full policy's feasible journeys are a subset of the
   relaxation's (it only adds constraints), a relaxation `NO_ROUTE` implies full-policy infeasibility, and a full-policy
   route that attains the relaxation optimum is full-policy optimal. A relaxation route is **not** a full-policy route.
2. **Instance faithfulness (O2).** The certificate is checked against the integer instance `I`. That `I` is the
   correct translation of (graph, request, packet) — occupancy fractions, rational ceilings, bounding-box edge
   prefilter, dwell/opening clipping — is a separate obligation. Plan: an independent re-derivation of `I` from the raw
   inputs, compared byte for byte.
3. **Model assumptions** carried from SIPP_EQUIVALENCE: integer seconds (departures only on integer seconds), fixed
   FIFO durations, node issue position, waiting only where declared, complete declared support (`model.supported`).
   Unknown support => no certificate is issued (the planner already returns `UNSUPPORTED`).
4. **At-issue refusals** (origin cell burning at departure, incurred dose over budget) are not search results; they get
   a separate direct certificate (the offending cell interval / budget values), checked directly.
5. Mathematical argument, not machine-checked. The second checker is meant to be small enough to verify formally later.

## 6. Artifacts and independence

- Generator (solver side): exact truncated forward reachability, emitted alongside SIPP's answer.
- Canonical file `*.wfgc` — whitespace-separated keywords and integers (instance section + claim + certificate), so a
  C program can read it without a JSON parser. Byte-level spec in `FORMAT.md`.
- Checker 1: Python, written against this spec, no solver imports.
- Checker 2: C99, integer arithmetic only, fixed-width `int64_t`, no shared code with solver or checker 1, no dynamic
  dispatch; reads the `.wfgc` stream.
- Mutation test: every single-point deletion class, goal injection into `A`, threshold changes, witness edits, instance
  edits; both checkers must reject each one.
