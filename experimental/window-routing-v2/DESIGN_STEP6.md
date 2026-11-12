# Step 6 design note: multi-hour solver (Priya with Richard; before any build)

**Question.** Should v2's multi-hour solver be Richard's interval deadline field, with the unchanged frozen checker as
verifier, instead of the dense per-second sweep (EarliestArrivalBound + LO/HI A*)?
- The orchestrator asked for this note before Step 6.
- Richard's inputs came at 16:12 UTC. This is a draft: Richard edits, Thomas reviews the certificate parts, Iris
  assesses.

## 1. Facts from the frozen kit at 5 h (measured here; F-3.4 FDYN_PLAN, A1/A3/A4)

- **Dense EA array.** The EarliestArrivalBound stores `C` as int16 over (horizon + 1) × (edges + 1)
  (`zsweep.py:434`).
  - Recorded bytes: Uiseong–Andong **1,505 MiB**, Yeongdeok **3,843 MiB**. This matches the reviewer's figure.
  - On Yeongdeok it is **the binding array**: resident at 4.4 GiB through search, above the 3,072 MiB guard by itself.
  - On Uiseong the binding peak is instead the **transient RoadBoundModel build** (9.0–9.5 GiB, 0.40 GiB resident
    after).
- **Time before search:** the bound model plus EA take about 100–130 s per request.
- **Uiseong search stalls.** With every memory gate at 12 GiB, the LO stage on Uiseong ran 246–273 s without finishing
  (cap ≈ 160 s). One call never returned.
- **But those Uiseong requests are easy.** Richard's router-only field finds checked routes for all 4 of them:
  - …323 arrives at **372 s**;
  - …324 arrives at **52 s**;
  - both pass the unchanged full checker (ac80919, `results/FDYN_KIT_REQUESTS_router_field.json`).
  So the kit's failure there is **not** a hard search problem. It is the dense machinery's cost.
- **Yeongdeok agreement.** The field and the (modified) kit agree on …207 = 59 s and …168 = 274 s.
  - For …166 the field's greedy witness gives 4,356 s against the kit's proven optimum of 3,953 s. It is feasible,
    not earliest, which is consistent.

## 2. What the field is today (Richard)

**Method.**
- Exact backward set equations over edge states (head node, incoming edge). Each state holds the set of feasible
  departure seconds as integer intervals.
- The fixed point is unique, because the time-expanded graph is acyclic.
- Certificate: `check_fixed_point` (order-independent). NO_ROUTE certificates export to Thomas's `.wfgc`.

**What it already covers:**
- turns and forbidden pairs;
- waitable nodes (waits only there; a wait clears admission);
- destination windows and dwell;
- issue-point blocking;
- the horizon;
- both contact rules (ROUTER sampling and the closed footprint).

**Tested.** Oracle-tested against brute force. On **7,771 of 7,771** recorded 1-hour routes it gives identical legs
and arrival.

**Cost.** Deterministic: states × interval pieces. These are natural work units for PLAN rule F and G6.

## 3. What it must add to be the solver

1. **Earliest-arrival optimality.**
   - The multi-hour witness today is greedy.
   - The exact A* witness ran out of memory (7.4 GB) on Yeongdeok at multi-hour.
   - Options: (a) a forward earliest-arrival pass restricted to the field's feasible states (no dead ends); (b) a
     bidirectional search with the backward field as an exact heuristic.
   - Either needs a stated memory budget and its own gate.
2. **Peak and dose.**
   - The field is contact-only. The frozen checker enforces peak and dose: the solver proposes the earliest
     contact-feasible route, and the checker accepts or rejects it.
   - **On a dose or peak rejection there is no exact fallback.** The result is then labelled `upper_bound`, never
     optimal.
   - Precondition that makes contact = full policy: journey duration ≤ (dose limit − incurred) / max non-flame flux,
     and peak cannot bind off flame. It held for 6,286 of 6,288 F-DYN v3.1 witnesses.
   - **[open — my concern, shared with Thomas's Step 7 review]** "max non-flame flux" must be a bound of the
     **checker's enclosure**, not the cell-binned packet flux. Otherwise the precondition can hold while the checker
     still rejects on dose. The precondition must be restated in the checker's own quantity, or used only as a
     predictor and never as a proof.
   - It must be revisited for the thresholded-dose variant (Step 9).
3. **Waitable nodes and windows:** already exact; verification only.
4. **Memory:** an interval representation instead of the dense int16 array. Its size must be measured on Uiseong and
   Yeongdeok at 5 h before adoption. Same 3,072 MiB default, and the declared 12,288 MiB is reported separately.

## 4. How the gates verify it

- **G2:** every returned route passes the frozen whole-road checker and `routing.independent`.
- **G2c:** every NO_ROUTE carries a `.wfgc` certificate, accepted by `check_py` and the C99 checker.
  - **Caveat (Thomas):** the step from field NO_ROUTE to kit-model no-route rests on the unverified dominance
    argument, until that argument is verified.
- **G6:** 1-hour reproduction (identical legs and arrival; identical refusals; timeouts never contradict).
  - The field already reproduced 7,771/7,771 routes in Richard's own run.
  - G6a/G6b re-runs it as v2.
- **Multi-hour optimality:** checked against an independent optimum where one exists. Example: the kit's proven 3,953 s
  on Yeongdeok …166 (modified kit A3b; labelled).
- **Labels throughout:** SCENARIO; road-limited graph (`graphs_interim`); the assumption line (no fire outside mapped
  or forecast cells); reporting rule R for every no-route.

## 5. My recommendation (for the orchestrator)

- **Yes: adopt the field as the multi-hour solver candidate for Step 6.** It is exact on contact, certified, and already
  reproduces the 1-hour routes. It finds the Uiseong routes the dense kit cannot.
- **Keep the frozen whole-road checker as the verifier,** unchanged.
- **The dense path stays the 1-hour solver until G6 shows the field reproduces it,** so G1 identity is kept.
- **Build order inside Step 6:**
  1. earliest-arrival pass (option a first: it is simpler and its memory is bounded by the field);
  2. measure the interval-field memory at 5 h;
  3. restate the exactness precondition in the checker's own enclosure quantity (Thomas reviews);
  4. G2, G2b, G2c and G6 as above.
- Steps 1–5 still come first: reasons, memory accounting, caps, precompute, EA memory. They also serve the 1-hour kit.
  The orchestrator may move Step 6 earlier, given that the dense multi-hour path may be superseded.
