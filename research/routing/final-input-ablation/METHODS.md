# Final-input routing constraint ablation

## Purpose

This study evaluates how the flame-contact, peak heat-flux and cumulative thermal-exposure constraints affect routing outcomes on the final evaluated inputs. It is a constraint ablation of the proposed implementation, not a comparison of five different search algorithms. It is separate from the earlier-input 300-execution Uljin ablation and from the final 80-execution comparison of proposed and reference implementations.

## Fixed missions and policies

The original 20 designed missions are retained: four missions in each of five Korean regional panels, representing four parent fires. The Uiseong–Andong and Yeongdeok panels share a parent incident. Repetitions, scenario members and forecast windows are not counted as additional independent fires. The selected final forecast checkpoint and the already constructed hazard packets are unchanged; no model was retrained and no threshold was tuned after observing outcomes.

| Policy | Flame contact | Peak flux | Cumulative exposure |
|---|---|---|---|
| Travel time only | Omitted | Omitted | Omitted |
| Flame avoidance | Enforced | Omitted | Omitted |
| Flame + peak flux | Enforced | Enforced | Omitted |
| Flame + cumulative exposure | Enforced | Omitted | Enforced |
| Full policy | Enforced | Enforced | Enforced |

All policies retain the supplied directed roads, legal turns, permitted waiting, action lattice, input support requirements, departure and horizon, destination opening intervals, destination-admission convention and required stay. Supplied incurred exposure is preserved in the raw requests. When cumulative exposure is omitted, its limit is disabled at departure as well as during future travel and stay. This is recorded as an explicit policy change; incurred exposure is not silently erased.

## Execution

Five policies and two repetitions per mission produce 200 scored executions. Every request starts a fresh native macOS process using the reviewed final controller, cold graph preparation and the proposed solver. Each receives the original 30-second complete-request allowance, search caps and 3,072 MiB sampled process-family memory guard. Preparation, search, mandatory selected-policy checking and publication are timed; forecast inference, packet construction and offline assessment are excluded. A deterministic cyclic policy order rotates between missions and is reversed in the second repetition. Lifecycle controls and one real request per policy precede the scored queue and are not counted as results.

The isolated wrapper removes the selected constraints consistently from planning, source-based contact checks, thermal prefilters and selected-policy end checking. Disabled numerical limits use a documented finite sentinel proved nonbinding for these bounded inputs. When both thermal constraints are omitted, planning flux is zeroed to avoid unnecessary exposure bookkeeping; this does not assign zero physical heat to the unchanged source model. Full-policy assessment always uses the original heat information. The full-policy configuration preserves the original request and hazard values and uses the original checking path. Core search, bounds, preparation, controller and publication modules remain unchanged. Per-file hashes bind the protocol, queue, source and derived inputs before scored execution.

## Outcome assessment

Selected-policy correctness and full-policy passage are assessed separately. A selected-policy route counts only if its authoritative publication and mandatory certificate complete within the request allowance, process cleanup is confirmed and independent checks find no contradiction. A late offline success cannot convert a rejected or incomplete runtime result into an on-time success. A route admitted under a weaker policy may legitimately fail the full policy; this is the intended counterfactual comparison and is not mislabeled as an incorrect selected-policy certificate.

Returned trajectories undergo independent centre-model, mission and exact-contact checks, plus the project's adaptive whole-road thermal checker against the unchanged full-policy inputs. Radiation-check uncertainty remains unresolved. This procedure does not supply an independent mathematical proof of continuous-road radiation enclosures. Refusals are reported with their supported model scope, separately from routes and unresolved outcomes.

Raw decision-enumeration names inherited from the original full-policy implementation may contain `FULL`. In the ablation, these certify the selected configuration, not every original hazard constraint. The explicit `policy`, `own_outcome` and `full_policy_pass` fields determine the cross-policy interpretation.

Mission-level categories require the corresponding outcome in both repetitions. Execution-level tables retain both runs and distinguish accepted routes, qualifying refusals, end-check rejection, resource stops, interruption and unresolved checking. Latency and memory statistics retain their population and measurement scope; removing a constraint also removes its checking work, so cross-policy cost differences are not evidence of a same-problem solver speedup.
