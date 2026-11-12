# Pass rules, committed before any code or run (orchestrator, 2026-11-12)

## X1. Cross-representation check: packet HAZARD.json vs the router's ContactModel

For each certified packet (v3 kriged_mean and firms_early, v3.1 firms_early; and any later variant before it is
certified), compare on [0, H):
1. **Cell sets.** The cells active in HAZARD.json (`p1_check.from_hazard`) and in `ContactModel.from_packet(...)`
   (merged) are the same set.
2. **Intervals.** Per cell, the merged interval lists have the same count and the same starts exactly. Ends are equal,
   or within 1 µs in either direction (binary64 representation of the writer's end sum); any larger difference fails.
3. **Integer instances.** For EVERY origin of the packet's INSTANCE.json entry, at each certified departure (0 and
   7,200 s), `frontend.build_instance` on HAZARD intervals equals the one on ContactModel intervals (edge blocks, wait
   blocks, acceptance).

PASS for a packet: 1, 2 and 3 all hold. A packet that fails is reported with counts. Its certificates are withdrawn
from any claim until the packet is fixed. Counts are reported per variant.
Negative control, required: the check must FAIL on the envelope_burnset packets of MANIFEST_v3_3 (4463892), where the
failure is already known.

## X2. Third-party cross-check of earliest arrival on small instances (Iris)

**Instances.** 2,000 random integer instances of the CERTIFICATE_SPEC §1 lattice, seed 20261112:
- V ∈ [3, 8] nodes, E ∈ [V, 3V] edges, D ∈ [1, 6];
- H ∈ [8, 48], dep ∈ [0, 3];
- 0–3 random closed blocked intervals per edge (EB) and per node (WB);
- 1–2 destination nodes with 1–2 acceptance windows each;
- waitable with p = 0.6, forbidden (state, edge) pairs with p = 0.1;
- the start state is the issue sentinel, or (p = 0.2) an edge into the origin.

Plus hand-written edge cases: dep = H; no acceptance window; origin is a destination; nothing waitable; every edge
blocked. No instance is discarded after generation.

**Methods**, each producing NO_ROUTE or the earliest arrival:
- **M1** `wfg_sipp.sipp.solve` (the router's search).
- **M2** `generate.certify`, with the certificate accepted by BOTH checkers (check_py.py and the C checker) with the
  same claim and T.
- **M3, third party.** networkx 3.4.2 on a time-expanded graph. Nodes are (s, t, a), with edges by the §1 EDGE and WAIT
  rules. The answer is the least t over goal nodes in `networkx.descendants(init)`. The encoder is new code, written
  from the §1 text only.
- **M4, brute force.** An exhaustive time sweep: the set of reachable lattice points t = dep..H is advanced one second
  at a time over every point and every move, written from the §1 text only.

M3 and M4 do not import or read sipp.py, generate.py, check_py.py or wfgc_check.c. Independence lies in the code path,
not in authorship: M3/M4 are by the same author as generate.py. Only the C checker had a separate author.

**PASS.** For every instance, M1 = M2 = M3 = M4 (status and arrival). Any disagreement fails the run, is kept with its
instance JSON, and is reported. An encoder fault found in M3 or M4 is fixed and the WHOLE set rerun; the failure stays
in the report.

**Negative controls**, each required to be DETECTED (≥ 1 disagreement):
- (i) an M1 answer perturbed by +1 s on 50 instances;
- (ii) an M3 variant that admits WAIT arrivals (a = 1);
- (iii) an M3 variant that ignores EB.

Undetected (ii) or (iii) means the instance set does not exercise that rule, and the run is NOT a pass.
