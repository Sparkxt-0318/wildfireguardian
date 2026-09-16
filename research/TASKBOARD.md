# Research program taskboard

Single source of truth for task status. The orchestrator maintains this file;
agents report into `research/reports/<agent>/` and the orchestrator brings the
status back here.

Last updated: 2026-09-16, end of round 1 dispatch.

## Waiting on John

Each item is one action. They are batched so they can be cleared in a single
sitting.

| id | severity | action | why it needs a human |
|---|---|---|---|
| WJ-001 | BLOCKER | Provide the six API keys as environment variables in the research sandbox: `DATA_GO_KR_KEY`, `KMA_APIHUB_KEY`, `VWORLD_KEY`, `FIRMS_MAP_KEY`, `EARTHDATA_TOKEN`, and `COPERNICUS_USER` with `COPERNICUS_PASS` | All six are unset in this sandbox, confirmed by probe. The KFS statistics API answers 401 without one. Agents must never create accounts or accept terms |
| WJ-002 | DECISION | Approve moving the ten research claim rules from `research/shared/check_research_claims.py` into `scripts/check_forbidden.py` | Editing `scripts/` is a change outside `research/`, which the brief makes a human gate. The rules are written and validated; only the move needs the word |
| WJ-003 | DECISION | Confirm the branch: keep research work on `claude/wonderful-gates-jlutm9`, or re-cut each direction onto `research/<direction>-<topic>` | The brief asks for per-direction branches; this session is instructed never to push to a branch other than its designated one. See DECISIONS D-003 |
| WJ-004 | BLOCKER | Open the NIFoS press release of 2025-04-25 in a browser and save attachment 2-2 to `research/lit/sources/` | Session-bound download. It is the source of the 6 m firebreak claim that the roads direction exists to test. Page link is in the roads prior-art note |
| WJ-005 | DECISION | Send the drafted request for the Sancheong landslide inventory (Nguyen, Song and Kim 2026, 568 initiation points) to the Pukyong National University group | Outgoing email is a human gate. The draft will be in `research/reports/requests/` |
| WJ-006 | DECISION | If the KFS Open API does not reach back to 1991, send the drafted records request to KFS or NIFoS | Outgoing email is a human gate. Blocked behind WJ-001, since the probe needs the key |
| WJ-007 | FYI | The FIRMS NOAA-20/21 branch is not yet cut. It touches finals code, so it lands on `fix/firms-noaa20-21` for review and is never merged by an agent | Suomi NPP delivery ends 2026-11-01. Deferred to round 2 to avoid branch switching while parallel agents share one working tree |

## Status legend

`dispatched` sent to an agent, running. `done` delivered and checked against the
definition of done. `blocked` cannot proceed, with a WJ id or a task id that
must clear first. `not started` queued behind its phase.

## Phase 0, setup (orchestrator)

| task | agent | status | blocker | report |
|---|---|---|---|---|
| T0.1 Create the `research/` layout | orchestrator | done | none | this file |
| T0.2 Registry skeleton, 17 datasets in priority order | orchestrator | done | none | `research/data/REGISTRY.yaml` |
| T0.3 Forbidden-claims entries in hypothesis wording | orchestrator | done | WJ-002 for the repository-wide move | `research/FORBIDDEN_CLAIMS.md` |
| T0.4 Claims and em-dash checker, validated both directions | orchestrator | done | none | 10 rules, 28/28 catches, 27/27 spares |
| T0.5 Confirm the existing gates still run | orchestrator | dispatched | none | see round 1 summary |

## Phase 1, data and prior art

| task | agent | status | blocker | report |
|---|---|---|---|---|
| T1.1 Verify the committed KFS statistics CSV, register it, write its check | A1 | dispatched | none | |
| T1.2 Confirm dataset ids, endpoints and licences for every priority 1 entry | A1 | dispatched | none | |
| T1.3 KFS API probe for 1991 to 2001 | A1 | blocked | WJ-001 | |
| T1.4 Draft the request letters for the request-only items | A1 | dispatched | none | |
| T1.5 Local solar times, complex rule, dirty-timestamp QC, geocoding precision | A2 | dispatched | none | |
| T1.6 Roads prior-art note and verified bibliography | A7 | dispatched | none | |
| T1.7 Verify Wilson 1988 and Sidle 1992 | A7 | dispatched | none | |

## Phase 2, design

| task | agent | status | blocker | report |
|---|---|---|---|---|
| T2.1 Shared evaluation harness, CV split contracts, sign-off protocol | A6 | dispatched | none | |
| T2.2 Roads pre-registration draft | A3 | dispatched | none | |
| T2.3 A6 signs the roads pre-registration | A6 | not started | T2.1, T2.2 | |
| T2.4 Landslides pre-registration | A4 | not started | roads reaches phase 3 | |
| T2.5 Suppression pre-registration | A5 | not started | landslides reaches phase 3 | |

## Phase 3 to 6

Not started. Phases 1 to 4 run for roads first, then landslides, then
suppression. Phase 5 scenarios and phase 6 integration are gated on John.

## Definition of done for the program

Each direction needs a pre-registration, a verified dataset chain from raw
download to model, a fitted model with uncertainty, a simple-baseline
comparison, an A6 sign-off, and a prior-art note stating what is new. Every
reported number traces to a script and a registry entry. The em-dash count is
zero, all gates pass, and the finals build is untouched.
