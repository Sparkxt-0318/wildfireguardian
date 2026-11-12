# Unknown-support outcome in the planner and the message kit — design and pre-registered pass rule

Status: DESIGN (orchestrator go-ahead, 2026-11-12). Committed BEFORE any code or any count, so the pass rule cannot
be fitted to the result. Field names are proposals, to be agreed with Priya (kit v2 journey_decision output). Richard
owns the Tier A / Tier R counts, and Thomas reviews any wording about a certificate. No resident-facing wording ships
without Iris and Sofia.

## Fixed constraints (orchestrator)
1. Unknown support → **unresolved**. Never "no route", never safe.
2. A result computed at a declared non-default memory budget is **labelled** (staff) and **never pooled** with
   default-budget results in any count, sweep or headline.
3. The **writer identity** (packet_writer_sha256 / support_writer) is shown in the staff provenance.

## What the planner has today (Main)
- planner/src/api/cache.ts maps every cached attempt to verdict ∈ {checked_route, model_no_route, unresolved}, plus
  a reasonCode (api/verdict.py: a strict mapping from journey_decision_v2_1 and the receipt).
- The staff provenance kinds include unresolved_proven_no_route.
- There is no field for unknown support, the memory budget or the writer identity. The F-9.3 support_mask (#152) is
  packet-level and not yet wired into F-DYN or the planner caches (PR #105).

## Proposed fields from kit v2 (to agree with Priya)
Per attempt (one origin × departure offset):
- `support`: `{ writer_version, rule, mask_sha256, packet_writer_sha256, base_packet_writer_sha256 }`, or null when
  the packet was built without a mask (the frozen writer).
- `unknown_support_involved`: one of
  - `"none"`: the decision did not depend on any unsupported cell;
  - `"route_crosses"`: a candidate route enters a cell with unknown support;
  - `"refusal_depends"`: a refusal certificate counts an unsupported cell as blocking;
  - `"not_evaluated"`.
- `memory_budget_mib`: the declared budget, and `memory_budget_default`: bool.

## Mapping (planner, fail closed)

| kit verdict | unknown_support_involved | planner verdict | reasonCode | staff kind |
|---|---|---|---|---|
| checked_route | none | checked_route | (as today) | (as today) |
| checked_route | route_crosses | **unresolved** | UNKNOWN_SUPPORT_ROUTE | unknown_support |
| model_no_route | none | model_no_route | (as today) | (as today) |
| model_no_route | refusal_depends | **unresolved** | UNKNOWN_SUPPORT_REFUSAL | unknown_support |
| any | not_evaluated, or the field is missing on a masked packet | **unresolved** | UNKNOWN_SUPPORT_NOT_EVALUATED | unknown_support |
| unresolved | any | unresolved | (as today) | (as today) |

- A masked packet (`support` ≠ null) without `packet_writer_sha256` gives unresolved, with WRITER_IDENTITY_MISSING
  (Hannah's consumer rule 1).
- A packet directory holding SUPPORT_WRITE_FAILED, or with no BUILD_SUMMARY, is refused (consumer rule 2).
- Whether `route_crosses` should be unresolved, or whether a whole-road certificate can stand over an unsupported cell,
  is a certificate question for **Thomas**. The table takes the conservative side until he answers.

## Presentation
- Staff: the headline is unchanged (unresolved: no time, never safe). The provenance line reads "Unresolved: fire
  state unknown on part of the road network (support mask <rule>, writer <sha8>)". It is never "no route". The writer
  identity is shown for every masked result.
- Non-default memory budget: a staff label "computed at a non-default memory budget (N MiB)" on the result, and
  separate rows in every count. The result is never part of a headline sweep that mixes budgets.
- Residents: no new wording. An unresolved result already says the model could not check it and to follow official
  orders. Any change goes to Iris and Sofia first.

## PRE-REGISTERED PASS RULE
On a fixture set covering every row of the mapping table, plus, once Richard's Tier A / Tier R cases exist, on those:
1. 0 results with unknown_support_involved ∈ {route_crosses, refusal_depends, not_evaluated} are shown, in any staff or
   resident output, as checked_route, model_no_route or "no route". 0 outputs for them contain a safe word, a
   departure time or a destination.
2. 100 % of masked results show the writer identity (sha8 of packet_writer_sha256) in the staff provenance. Every
   masked result without it is unresolved with WRITER_IDENTITY_MISSING.
3. 100 % of non-default-budget results carry the staff label. 0 non-default results enter a default-budget count,
   sweep, CSV total or headline; separate counts are reported.
4. Unmasked, default-budget results: every planner and kit output is byte-identical to Main (all real and synthetic
   cases).
5. Refusals: a SUPPORT_WRITE_FAILED marker or a missing BUILD_SUMMARY gives no result from that packet (test).
6. Mutations each fail at least one test: (a) refusal_depends mapped to model_no_route; (b) the writer identity
   hidden; (c) a non-default budget pooled into a default count.
7. Counts reported, not gated: by region and Tier (A / R, Richard), the number of results that move from checked_route
   or model_no_route to unresolved.

## Richard's three-way tiers (F-3.1, deadline_field/unknown.py and threeway.py; branch claude/f31-deadline-field)
Recorded here after his answer (2026-11-12). The gated pass rule above is unchanged.
- Masks: U_state = mask__unknown_cumulative_state. U_q = mask__policy_assigned_zero & ~mask__known_burned & ~U_state.
  Unknown cells are added as blocks [start, beyond H) under both the router rule and the closed-footprint rule.
- Tiers:
  - Tier A: every unknown cell is blocked from t = 0. The most pessimistic tier.
  - Tier B(v), v ∈ {1.5, 8.2} km/h: U_state is blocked from 0, and U_q from d/v.
  - Tier R(v): U_state and U_q are both blocked from d/v, with d measured from present fire ∪ positive-probability
    cells.
  - Optimistic: the frozen packet.
- Per-job label under a tier:
  - checked(contact) if the departure is feasible in the tier field;
  - no_route if it is infeasible even optimistically;
  - unresolved if it is feasible optimistically but not under the tier.
- **Caveat carried into the presentation:** a "checked" result under a pessimistic tier is contact-only. The dose and
  peak preconditions for hypothetical unknown sources are NOT established. The planner must never present a tier's
  "checked(contact)" as a whole-road-certified route. It stays labelled "contact-only under tier <X>" in staff
  outputs, and it is never shown to residents as a route.
- Where: the summary is research/harness-2026-11/F-3.1/results/UNKNOWN_THREEWAY_1h.json (b0ca8bc), per cache and tier.
  The per-job rows come from `python3 -m deadline_field.threeway <cache.json>`, with transition keys
  "tier|recorded|label".
- **OPEN (orchestrator / Iris):** which tier the planner presents as its headline. That is a policy choice; Tier A
  is the most conservative. The design reports every tier in staff, and pools none. F-DYN tiers do not exist yet
  (Leo's masked F-DYN packets).

## Answers from Priya and Thomas (2026-11-12)
**Priya (kit v2):**
- v2 is at Step 0 and emits the frozen decision, "wfg.journey-decision/1", plus RESULT.kit_identity (the KIT's identity,
  not the packet writer's). No per-attempt route_crosses or refusal_depends exists.
  - route_crosses could be derived from the published route plus HAZARD support.
  - refusal_depends needs the refusal certificate's reasoning, so it would be a new v2 step (plan amendment, with
    Thomas reviewing), after v2 Step 1.
- Agreed names: `memory_budget_mib`, `memory_budget_default` (PLAN D1: 3,072 MiB default, 12,288 declared); the writer
  identity is `support.packet_writer_sha256`, aligned with Thomas's G2b field. When v2 adds them it bumps to
  "wfg.journey-decision/2".
- **Consequence for the planner today:** check "wfg.journey-decision/1" + kit_identity.candidate_id. Every masked
  result is `not_evaluated`, hence unresolved, until v2 emits the fields. Today's planner caches hold no masked
  packets, so nothing visible changes yet; the rule fails closed when they arrive.

**Thomas (certificate):**
- route_crosses → UNRESOLVED is right. Under c651_unknown/1 the packet carries no fire in unknown cells (the optimistic
  instance), so a whole-road certificate holds only on the assumption that those cells are not burning.
- Upgrade path, not implemented: a re-check on a pessimistic instance.
  - Tier A fails any crossing route by construction.
  - Tier R(v) can pass. Such a result is conditional and must read "checked under Tier R(v = …)", never "certified".
  - The tooling is contact-only today.
- Even a route that does NOT cross an unknown cell is not covered for fire spreading from unknown cells, or for heat
  from them. So a certified route in a packet with unknown cells carries the assumption in its staff text.
- **Staff wording (Thomas), replacing the draft above:**
  - crossing: "Unresolved: this route passes through areas whose fire state is unknown (support mask <rule>, writer
    <sha8>). The road check assumed no fire there; it does not cover the actual fire state in those areas."
  - certified, but the packet window holds unknown areas: "Checked against the forecast hazard, which assumes no fire
    in areas of unknown fire state (support mask <rule>, writer <sha8>). Fire spreading from, or heat from, those
    areas is not covered."
  - The Korean goes to Sofia. Staff only; residents unchanged unless Iris and the orchestrator decide otherwise.
- **Addition to the pass rule (stricter, consistent with Thomas):** 8. 100 % of certified results from a masked packet
  with unknown cells in the window carry the assumption sentence in staff outputs. 0 carry "certified" without it.
