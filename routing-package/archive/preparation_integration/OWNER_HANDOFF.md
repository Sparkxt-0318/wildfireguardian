# Owner handoff — immutable preparation integration, 5 October 2026

Delivered a runnable optional integration in `candidate/`, preserving raw baseline and verified parent source. Stable sessions, retained/progress/update flows, recorded return and process-local replay now reuse graph preparation. Adoption is narrow and supported by full measured lifecycle; no algorithm redesign or dependency was added. This isolated candidate is available for host adoption, not a merge or deployed production service. The existing separate established AS-EAGER/CAND-2 road-research recommendation remains unchanged.

## What to adopt

- `RoutingSession(graph, prepare=True)` for an owned immutable snapshot; add `graph_ownership="checked"` when external mutable contents remain authoritative. Graph exports are fresh copies. Same-revision changes reject through full content comparison.
- `session.check_return(...)`, `plan_with_return(prepared, ...)` and `checked_return(prepared, ...)` reuse geometry admission for primary/reverse checks. Facades also support `prepared=handle` with a supplied mutable graph, checking complete contents.
- `replay(fixture, prepare=True)` or CLI `replay --prepare-graph` prepares one graph for the process and all relevant event operations. One-shot `solve --prepare-graph` can reuse primary/fallback admission, but ordinarily successful one-shot solves should remain raw.
- `replace_graph(graph, reset=True)` admits a replacement then clears mission state; active replacement without an explicit Boolean reset rejects. Reset alone keeps admitted graph bytes; changed checked authority must still be explicitly replaced. Old completions cannot commit.

Read `candidate/PREPARATION_LIFECYCLE.md`. Raw `solve(graph,...)`, session defaults, service/fallback and CLI/replay remain available. There is no daemon, persistent serialized cache, thread synchronization or across-process reuse.

## Complete lifecycle and memory

Simple full Nangok geometry with generated hazards, 3 interleaved pairs per mode:

| Flow | Raw → prepared lifecycle s |
|---|---:|
| Cold session through first commit/retained/reset | 13.132 → 2.862 |
| 3 complete session request cycles, including initialization | 29.286 → 3.044 |
| 2 hazard updates + 3 complete request cycles | 34.045 → 3.102 |
| Replay | 23.549 → 3.040 |
| 2 primary/return facades with initialization | 20.914 → 2.865 |
| Initial request + graph replacement/rebuild + new request | 26.605 → 5.799 |
| Successful one-shot CLI, full process wrapper lifecycle | 2.699 → 2.791 |

Standalone graph initialization: 2.604 / 2.669 s; replacement rebuild: 2.709 / 2.781 s. These costs are charged, not erased from warm measurements. Repeated-road peak RSS: 136.11 / 155.67 MiB. Retained prepared payload: 3.679 MiB. RSS is process high-water, not steady-state service memory. Every tiny regression, timeout and unsupported event is in `BENCHMARK_REPORT.md` and raw rows.

## Correctness and status

Preserved baseline 73 and upstream candidate 84 tests reproduced; the upstream independently authored 499-gate review was also freshly reproduced with zero failures; integrated 84 package tests, deterministic raw/prepared replay and full-road witness pass. Independent final review: 41 grouped checks / 153 finite session/reference comparisons, plus 312 extra benchmark witness checks; 120 rows / 60 pairs with no semantic/search-counter disagreement or child errors. Exact dose and mandatory checks match preserved raw behavior. Search/validation/reference bodies remain unchanged after graph admission.

Coordinator found and repaired the strict-reset control-input bug missed by the initial reviewer suite; malformed reset values now preserve state. Old failed/harness runs and partial pre-repair timing rows are retained. Corrected source was refrozen on identical confirmation inputs before the final run. Read `CORRECTNESS_REPORT.md` and `review/INDEPENDENT_REVIEW.md` for the actual tested scope and failures.

**Adopted recommendation:** optional stable large-graph sessions, checked-authority repeated requests, replay and compatible primary/return integration that earn full lifecycle cost. **Experimental:** this isolated host integration, bounded distant-road cap experiment, successful one-shot preparation and frequent rebuilding where marginal savings do not repay complexity. **Unverified:** universal speed, large exposure-active road-search efficacy/global certificates, concurrency, actual forecasts, real-road thermal/passability truth, physical safety and deployment. Tiny and successful one-shot CLI should remain raw by default. Rebuild-dominated direct workloads also warrant raw use; the measured full session replacement lifecycle does earn optional preparation, despite slightly slower standalone rebuild. Graph rebuild itself is no guaranteed gain.

## Delivery and preservation

`CANDIDATE.patch` is against `baseline/`; `INTEGRATION_ONLY.patch` is against the verified preparation parent. `REPRODUCE.md`, `reproduce.py`, `verify_delivery.py`, environment/freezes, manifests and all raw rows are included. Current parent candidate manifest and handoff point here; copied historical evidence is retained as history. Original delivered 100 files and upstream 255 manifest entries remain unchanged. Dated canonical context appended with its existing file-inode lock and prefix preservation. No push, merge, deployment, forecast changes or dependencies. Authorship is coordinator + separately owned agent reviewer, not an external human audit.


Supplemental hard-path check: the original intended hard case was structurally DISCONNECTED and is retained. A separately frozen connected diagnostic then exercised identical 500-expansion TIMEOUTs and successful separately checked nonzero-dose returns in both arms. It adds 18 rows / 9 pairs and 12 independent witness checks, bringing all executed rows to 138 / 69 pairs and 324 extra checks. It supports bounded lifecycle/cap behavior, not hard-search efficacy or independent road optimality/refusal. Read the separate diagnostic section in BENCHMARK_REPORT.md; main adoption numbers above remain the original confirmation.
