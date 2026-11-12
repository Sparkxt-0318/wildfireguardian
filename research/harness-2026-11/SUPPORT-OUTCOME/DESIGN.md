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

## Headline tier: provisional position and sensitivity (2026-11-12)
- Provisional (orchestrator, supported by Iris; the owner picks): the headline uses the rate-assumed tier at 8.2 km/h
  (R8.2). Staff see every tier unpooled. "Checked" is contact-only and never worded "certified". Name: "rate-assumed,
  8.2 km/h", never "bounded" (Iris: the rate's primary source is unverified).
- **Downgrade-only rule (new, from this measurement):** a tier can only make a recorded result MORE cautious.
  - A recorded checked_route whose tier label is not checked(contact) becomes unresolved.
  - A recorded model_no_route or unresolved NEVER changes.
  - Why: a tier's no_route or checked(contact) comes from the contact-only deadline field, not from a whole-road
    certificate or refusal. Mapped straight through, the tier labels would have UPGRADED 988 recorded job results
    (all tiers), e.g. recorded unresolved → "no route", and changed 12 more R8.2 headlines. So the pass rule gains:
    9. 0 recorded unresolved / model_no_route results are changed by any tier (test).
- Measured with the planner's own planFromAttempts + deadlineHeadline on Richard's per-job rows (b927c21c; not yet
  verified by Nora). Script: tier_sensitivity.test.ts; output: TIER_SENSITIVITY_1h.json. Results:
  - the rebuild reproduces every recorded headline;
  - 0 jobs are missing from the tier files;
  - 539 plans = 531 field origins + 8 research origins.

  Headline changed (kind or time), downgrade-only, summed over the six 1-h caches:

  | Comparison | Plans changed (of 539) |
  |---|---|
  | R8.2 vs Tier A, i.e. Iris's staff flag "depends on the assumed maximum spread rate" | **246** |
  | R8.2 vs recorded | 134 |
  | R1.5 vs recorded | 22 |
  | Tier A vs recorded | 259 |

  - Per cache, the R8.2 vs Tier A counts are 29 / 30 / 23 (의성–안동) and 53 / 55 / 56 (영덕).
  - "Twice 8.2" (16.4 km/h), which Iris asked for, is not in Richard's tiers yet; requested.
- Prepared, not built (Iris):
  - (b) the staff flag "depends on the assumed maximum spread rate" wherever the R8.2 and Tier A headlines differ
    (246 / 539 at 1 h), with the same pattern as the forecast-dependent flag;
  - (3) one resident item in "what this does not check": "Where the fire map has no data, the model assumes fire
    cannot arrive faster than about 8 km an hour." Fallback: "…assumes a maximum fire speed; it could be wrong."
    Korean to Sofia.

## Downgrade-only: reason and the would-be upgrades by type (Iris, 2026-11-12)
- **Reason (Iris):** the tier results come from the contact-only deadline field, while the recorded results come from
  the full kit with its checks. A weaker kind of evidence may withdraw a claim but must not create one. So a recorded
  checked route may become unresolved, but a recorded unresolved or no-route is never changed by a tier.
- The 988 would-be upgrades (direct mapping, all five tiers, six 1-h caches; TIER_SENSITIVITY_1h.json):

  | Recorded → tier label | Count | Note |
  |---|---|---|
  | unresolved → no_route | **970** | 194 jobs per tier, the same in every tier |
  | unresolved → checked(contact) | **18** | A 2, B1.5 2, B8.2 2, R1.5 8, R8.2 4 |
  | model_no_route → checked(contact) | **0** | |

  - The 194 unresolved → no_route jobs are infeasible even in the contact field's optimistic instance, yet the kit did
    not resolve them. The contact field reads them as a refusal, but that is not a refusal certificate, so they stay
    unresolved.
  - Iris's evidence question asked: does the contact-only field call a run feasible where the kit's full rules
    refused? At 1 h there is **no** such job (no recorded model_no_route becomes checked(contact) in any tier). So, on
    these caches, the contact field does not overstate feasibility against a recorded refusal.
- **Item 9 acceptance:** with the rule on, **0** headlines move in the upgrade direction, across all five tiers and six
  caches (test value upgrade_moves_with_rule = 0). The 12 R8.2 headlines the rule keeps from moving, by place:
  - 의성–안동 03-25 17Z: osm:node/415160467, 415160362, 415160358, 415158334, 415160360. Each is recorded unresolved;
    direct mapping would show "no route".
  - 영덕 03-25 19Z: osm:node/415158320, 415160183, 415158259, research:…_FD1. Each is unresolved; direct would show
    "no route".
  - 영덕 03-25 23Z: research:…_FL2. Recorded deadline 0 s; direct would give 1,200 s (a later time, i.e. an upgrade).
  - 영덕 03-26 08Z: osm:node/415160178, 415160314. Each is unresolved; direct would show "no route".
- Iris on the flag: it marks 246 of 539 places, which is too common to work as a per-place warning. So it LEADS with
  the count in the staff summary ("the leave-by time at N of M places depends on the assumed maximum spread rate"),
  and the per-place flag stays as a detail.
- Orchestrator (b): provisional label "rate-assumed, 8.2 km/h (reported orally, method unpublished)". The resident
  list item uses Iris's no-number fallback unless the owner wants a number. R16.4 / B16.4 are being run by Richard
  (rules committed first: RATE_ASSUMED_RULE.md, 8a16dc2, and the "Addition 2026-11-12" for B16.4 at 41a2ae7).

## Denominators and why the kit left the would-be upgrades unresolved (Iris follow-up, 2026-11-12)
Scope: 1 h, the six booth caches only, distinct route-check jobs, Richard's rows b927c21c (not yet verified by Nora).
It says nothing about longer horizons.
- Denominators (per tier, the same in every tier): recorded checked_route **7,771**, model_no_route **1,468**,
  unresolved **204**.
  - So "model_no_route → checked(contact) = 0" is **0 of 1,468** in each of the five tiers: at 1 h, on these caches,
    the contact field never calls feasible a run that the kit's full rules refused.
- The 194 unresolved → tier no_route (the same jobs in every tier), by recorded reason code / raw status:
  - **186 AT_ISSUE_FAILURE.** This is the kit's own pass-through status: the mission is already violated at issue time
    under the supplied members, so there is no journey. The planner shows it as "already over a limit at departure".
    They are not undecided searches, so they are not candidates for a refusal; the contact field's "no route" only
    restates them. They stay as recorded.
  - **8 TIMEOUT** (raw UNRESOLVED). These are the only true candidates for Iris's relaxation hypothesis, i.e. a contact
    "no route" that might be promoted to a refusal once Thomas's dominance check (permissive-tier blocked set ⊆ kit
    blocked set at every step, plus independent reachability) exists. The possible gain is at most 8 jobs at 1 h, not
    194.
- The 18 unresolved → checked(contact) (A 2, B1.5 2, B8.2 2, R1.5 8, R8.2 4): **all TIMEOUT** (raw UNRESOLVED), i.e.
  the compute budget, not a rule difference. They are candidates for kit v2's declared larger budget (PLAN D1: 12,288
  MiB), where any result must carry the non-default-budget label and is never pooled. R1.5 has 8 because its blocks
  start latest of the rate tiers (U_state is also delayed), so more timed-out searches are contact-feasible under it.
  This is consistent with the definitions, not an anomaly.
- Until Thomas's check exists, all of these stay unresolved (downgrade-only, item 9).
