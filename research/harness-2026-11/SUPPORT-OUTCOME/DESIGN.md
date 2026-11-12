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
