# F-C1b account-based: did residents first see fire with less time left than the route needed? (fixed before computing)

Orchestrator decision, 2026-11-12. This is a **separate, labelled "account-based" analysis**, run beside the satellite
analysis (`DEFINITION_C1b.md` + amendment 1, `RESULTS_C1b.md`, all indeterminate). It is never mixed into the
satellite columns. This file is committed before any number in it is computed, and sent to Iris and Hannah.

> Retrospective research on the 2025 event. Accounts are what a newspaper or broadcaster reported a named person
> said; they are a third source, not truth. At most 6 case descriptions; **no rate or share is quoted**; every sign
> is labelled "account-based".

## 1. Eligible accounts

An account is used only if it was **read in full** (not a search snippet) and states all four of:

1. a **place** that maps to an observer point already fixed in `DEFINITION_C1b.md` (no new coordinates);
2. a **clock time** (or clock range) on 25–26 Mar 2025, KST;
3. an **observation** of fire or smoke (seen, or fire at the place);
4. a **source URL**, written into the table below.

Hearsay forecasts ("told the fire was 1 h away"), warnings ("이장 knocks on doors") and official orders are not
observations. They are listed as context only.

| Case | Observer point (DEFINITION_C1b.md) | First-seen S (as reported) | Arrival A at the place (as reported) | Source |
|---|---|---|---|---|
| C1 = V1 | 지품면사무소 node 11835585365 | black smoke from the north, about 16:30 KST, seen by the 면장 at the office | flames at the office, about 17:55 KST, **only if Sofia confirms the wording in the full text**; otherwise not documented | dgmbc 628364 (URL to be added, §6) |
| C2 = V2 | 매정1리, 매정2리, 매정3리 halls (each separately) | **not documented as a sighting** (20:00 door-knock is a warning) | "10 min after leaving at about 20:30 the fire swallowed the village", i.e. about 20:40 KST | hankookilbo A2025032714350000238 (URL to be added, §6) |
| C3 = V6 | 신덕리 place node 415158335 (centroid, flagged) | red flames came over the ridge about 17:30–18:00 KST | fire reached the village about 10 min after S | Nocut 6318424 (URL to be added, §6) |

**Not eligible:** V3 경정리, V4 노물리, V5 강구면. These are snippets. They are listed by name with the reason and are
not computed. Cheongsong 파천면 is excluded because it has no coordinates.

## 2. Fixed uncertainty windows

- **Clock time "about hh:mm":** [hh:mm − 30 min, hh:mm + 30 min].
- **Clock range "a–b":** [a − 30 min, b + 30 min].
- **Stated delay "about N min later"** (an arrival given relative to S): A − S ∈ [max(0, N − 15), N + 15] min. Here
  the delay is used directly, and A's clock window is S's window shifted by the delay.
- **Sensitivity row:** the same with ±15 min for clock times. It is reported, but **signs are called on ±30 only.**

## 3. Route need and leave-by

- **trip** = trip_min of the observer's leave-by place, exactly as in the satellite analysis. trip_min is the fastest
  fire-free trip from the nearest planner place's road entry node to its quickest destination; the values are already
  in `C1B_documented.json`.
- **Account leave-by:** L = A − trip (an interval). It ignores roads cut before the village is reached, so it is an
  **upper bound on the true deadline** (DEFINITION_C1b.md amendment 1.3).
- **F-DYN leave-by per variant:** reported **only if** Richard's F-3.1 deadline field exists, at computation time, for
  the region-start whose window [start, start + H) contains S_lo. It is reported for kriged_mean, firms_early,
  envelope and envelope_sound, each with its `soundness` label, at the graph node nearest the observer. If it does
  not exist, the entry is "not available". **No substitute is computed.**

## 4. The answer per case

- **Margin** M = L − S = [L_lo − S_hi, L_hi − S_lo] (minutes). With a stated delay, M = (A − S) − trip, using the
  §2 delay window.
- **"Saw with less time left than the route needed" (account-based)** only if M_hi < 0. This is robust to the
  leave-by simplification, because L is an upper bound.
- **"Saw with enough time" (account-based)** only if M_lo ≥ 0. It is labelled "not robust to the leave-by
  simplification".
- Otherwise **indeterminate**.
- **Cases with S not documented** (C2): no sign. Only A, trip and visibility are reported.
- **Cases with A not documented:** no account-based sign. The satellite arrival bracket is shown beside S, labelled
  "satellite", and no sign is called from it.
- **Final count:** k of n eligible cases, where n counts only cases with both S and A documented. **The count is not
  a rate.**
- **F-DYN variants:** the same test with L_v in place of L, reported as a separate row per variant. It is labelled
  with that variant's soundness. Only envelope_sound is a sound bound.

## 5. Visibility check at S (settings unchanged)

- **Settings:** the same optimistic and pessimistic settings as `DEFINITION_C1b.md`, including the smoke column only
  before sunset at 18:50 KST.
- **Inputs:** the per-observer first-visible intervals [V_lo, V_hi] already computed in `C1B_documented.json`, for
  rows `bracket_detected_only` and `wide_bracket_all_burned`. No new viewshed run, and no change to any height,
  observer or cap.
- **Per case, setting and row:**
  - "visible by S possible" if V_lo ≤ S_hi;
  - "not possible" if V_lo > S_hi (no modelled burning cell in sight even at the earliest);
  - "certain by S" if V_hi ≤ S_lo.
- A "not possible" result means the **model's fire positions** fail to explain the account. It is reported as such,
  not as evidence against the account.

## 6. Order of commits

1. This file. No computation has been made under it.
2. A **URL-only commit**: the three URLs from Sofia, plus her confirmation (yes/no) of the C1 17:55 flames wording.
   Nothing else changes. A case without a URL in that commit is not computed.
3. Computation (`seebefore/c1b_accounts.py`, reading only `C1B_documented.json` and this table), then
   `RESULTS_C1b_accounts.md`. Results go to Iris and Hannah.
