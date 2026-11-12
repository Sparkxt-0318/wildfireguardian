# Relaxation refusal ⇒ kit refusal for the 1-hour unresolved jobs: rule (committed before any run)

Orchestrator item (2026-11-12, from Iris's hypothesis): 194 one-hour jobs are UNRESOLVED in the kit, but "no route" in
Clara's contact-only field in every tier (`clara/support-outcome`, `TIER_SENSITIVITY_1h.json`).

**Scope.** 186 of the 194 are AT_ISSUE_FAILURE (origin burning at departure, or dose already over budget). Only 8 are
TIMEOUT / UNRESOLVED. At-issue is not search infeasibility (CERTIFICATE_SPEC §5.4), so relabelling those jobs as route
refusals is a policy question, raised with the orchestrator. Until it is decided, this rule covers the 8 TIMEOUT jobs.
For the 186, at most the at-issue fact itself is checked (the origin cell interval containing the departure, or
incurred > budget).

## 1. Dominance argument (code-level; every kit-feasible journey is relaxation-feasible)

The kit's whole-road check (`window-routing/stack/routing_candidate/baseline`: `hybrid_checker.check` →
`mission_contract.prepare_mission` + `contact_first.check_contact`, then radiation) accepts a journey only if all of the
following hold. Each requirement is at least as strict as the relaxation `L(I)` built by
`wfg_sipp.frontend.build_instance` (CERTIFICATE_SPEC §1). Read at Main f2cbcfc / 8fdce35.

| Kit requirement (file) | Relaxation counterpart | Inclusion |
|---|---|---|
| Departure t a multiple of dt = 1; each EDGE leg lasts exactly `travel_ticks`·dt; legs contiguous; waits are whole seconds (`prepare_mission`) | integer-second lattice; EDGE `t → t + D_j`; WAIT `t → t + 1` | same lattice |
| Forbidden turns (incoming, edge) from `graph.forbidden_turns`, with the request's incoming edge | `F` from the same table | equal |
| Waits only at `waitable` nodes | WAIT only if `waitable[hd(s)]` | equal |
| Arrival after an EDGE leg (`arrived`), at the single explicit destination; [t, t + dwell] inside an opening interval and the horizon | goal `(s, t, 1)` with `t ∈ AC`: opening, full dwell inside the horizon | equal |
| Contact: the straight segment p0→p1 between NODE points, clipped against CLOSED cell rectangles. The occupancy interval [enter, leave] is closed; flame is [birth, birth + T) or [0, R); reject if they intersect, for ANY member (`check_contact`) | EB from `core.edge_occupancies` on the SAME chord u→v: open sub-segments take their midpoint cell, cut points their floor cell. Block t iff [t + D·z0, t + D·z1] meets [b, e); union over members | the kit's cells ⊇ the relaxation's (a closed rectangle contains the floor-cell point); the time test is identical |
| Contact on WAIT and DWELL pieces at the node point | WB, and the dwell contact-free in AC, at `node_cell` (floor) | the kit's cells ⊇ |
| Contact on the ISSUE point (origin at departure) | none (the relaxation is weaker) | the kit is stricter |
| A point outside the source domain, or unsupported cells ⇒ UNRESOLVED | none | the kit is stricter |
| Radiation (peak, dose) | none | the kit is stricter |

**No kit rule found that could OPEN a route the relaxation closes.** If the run finds a kit-accepted journey that the
relaxation blocks, this argument is refuted and the item fails.

## 2. Per-job mechanical checks (all must pass for a job to count)

- **(i) Identity.** Graph, request and packet are the files of the kit job (sha256 equal), on the OPTIMISTIC tier (the
  frozen packet). A pessimistic tier is not a relaxation of the kit.
- **(ii) Packet.** X1 rules 0–4 pass (arrays routable; HAZARD = ContactModel = raw re-derivation; integer instances
  equal). This is P1: the kit's `ContactSources` and `ContactModel` read the same `constructed_arrays.npz` + REPORT
  law.
- **(iii) Grid alignment.** The graph's `grid` (x0, y0, resolution, width, height) describes the same physical cells as
  the packet's `affine_transform` and shape, with the row flip of `ContactModel`. Otherwise the cell indices of the two
  sides are not the same rectangles.
- **(iv) Code identity.** sha256 of the files this argument was read from: the kit's `contact_first.py`,
  `mission_contract.py` and `hybrid_checker.py`, and the frontend's core module. They are recorded per run; a
  mismatch voids the job.
- **(v) Independent reachability.** `generate.certify` gives NO_ROUTE (T = H + 1), accepted by BOTH checkers (Python and
  C99) with exactly "ACCEPT NO_ROUTE <H+1>".
- **(vi) Empirical corroboration of the contact inclusion.** For a sample of (edge j, departure t) with t ∈ EB_j (all
  of them if ≤ 2,000 per job; else 2,000 sampled with seed 20261112): build the one-leg trajectory ISSUE → EDGE j →
  DWELL 0 and call the kit's `check_contact`. It must return DEFINITE_REJECT. Any CLEAR refutes §1.
- **(vii) Zero disagreement.** No kit run of the job has published a route. Any published route on a job that passes
  (v) refutes §1 (the G2b(b) check).

## 3. Pass and report

- **PASS count:** the TIMEOUT jobs (of 8) passing (i)–(vii).
- **Reported separately:** the at-issue fact checks for the 186, if the orchestrator wants them.
- **Also reported:** the denominator, model_no_route at 1 h = 1,468 distinct jobs (Clara's `denominators_distinct_jobs`).
- **Failure:** any refutation in (vi) or (vii) fails the WHOLE item. It stays closed, and no job is relabelled.
- Until Mira verifies, every job stays UNRESOLVED, and nothing in the planner or kit changes. A supplied refusal
  certificate must carry the bundle sha and both checkers' verdicts: the kit's `_valid_refusal_certificate` records
  declared fields only and does not re-verify.

## Status (2026-11-12 ~15:55 UTC, orchestrator, superseding the scope above; the rule text above is unchanged)

- **At-issue jobs:** nothing is relabelled. The planner already shows "already over a limit at departure". No at-issue
  check is needed from this item.
- **Priority: LOW at 1 h.** Only the cheap per-job steps — (i), (ii), (iii), (v), (vii) and the sampled (vi) — run on the
  genuine timeout jobs, when the CPU is free. There is no further review of the kit checker for these jobs. §1 is
  already written, from the code read done for this rule.
- **Field.** A refusal claim uses Richard's ROUTER-only field under the recorded forecast: the same flame rule, graph,
  turns, admission, opening windows, horizon and departure, with peak and dose dropped. It never uses CERT alone or a
  pessimistic tier.
- **Count to reconcile.** Clara's 8 TIMEOUT jobs vs Richard's 98 TIMEOUT rows (all Yeongdeok): distinct jobs vs rows,
  or a different field. Richard and Clara reconcile this before any run, and the reconciled set is the one checked.
- **A wider review** of the kit's whole-road checker is decided by Richard's count of UNRESOLVED multi-hour (F-DYN 5 h /
  8 h) jobs that are infeasible in the ROUTER-only field.
- **Any result** is an OFFLINE checked refusal. The kit's 30 s behaviour claim is unchanged.
