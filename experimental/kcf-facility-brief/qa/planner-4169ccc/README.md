# Integration record — Chat 1 planner at `4169ccc`

Date: 2026-11-11. Brief core `kcf-brief-core/1.1.0`.

## Source (read-only)

- Chat 1's local tag `kcf/planner-delay-v1-ready` → `4169cccc427e9e19be3851326a1225df89fe96f2`. Chat 1's git proxy refused the tag push with HTTP 403. With the user's approval, Chat 1 published the same commit as branch `claude/stoic-davinci-eha5j9`.
- This session fetched that branch read-only and **pins the SHA, not the branch name**. Nothing was checked out and no worktree changed. The commit adds only `experimental/kcf-facility-planner/` on top of `5fa19a2`.
- Files were read with `git show 4169ccc:<path>`. Chat 1's `cli.py` was run on a `git archive` export in a scratch directory.

## Inputs (`inputs/`, sha256 first 12)

| File | Origin | sha256 |
|---|---|---|
| `demo_two_vehicle.result.json` | `cli.py` on `fixtures/demo_two_vehicle.json` (baseline) | `1995dc17ed5d` |
| `demo_two_vehicle_v2plus600.case.json` | same fixture with `vehicles[1].available_s += 600`, the "revised" construction Chat 1 described | `ec28cbbaf5c8` |
| `demo_two_vehicle_v2plus600.result.json` | `cli.py` on that case | `2dcabde15ed7` |
| `contract_normal.result.json` | `cli.py` on `fixtures/contract/normal.json` (Chat 1 did not commit this result) | `78fecdcd30d5` |
| `sample_result_parallel_delayed.json` | committed at 4169ccc; regenerating it gave identical `trips` | `ca590adb1f3c` |
| `sample_result_shuttle.json` | committed at 4169ccc | `a680ccfa4d99` |
| `sample_result_missing_input.json` | committed at 4169ccc | `ab92ae71b667` |
| `demo_briefing_meta.json` | **written by this session, not by the planner.** Group and vehicle labels come from Chat 1's fixture; update times, clock, field report and road row are invented exercise context | `126ede2a1985` |

Results include `wall_s` timings that vary between runs, so only status, totals and trips are compared.

## First run — adapter 1.0.0 as first committed (`first_run_core_1.0.0/`)

**All four REJECTED** at the first check: `schema_version 은 문자열이어야 함`. Chat 1 writes the integer `1`, as its `SCHEMA.md` documents; this contract had required a string.

A diagnostic pass on scratch copies, with only `schema_version` stringified, found further mismatches. That pass is not recorded as acceptance.

1. Unload time is `unloading_end_s`, a name the adapter did not recognise. Every trip showed 모름, although no stale number appeared.
2. There is no `assignment_checked`. `SCHEMA.md` says `trips` holds only checked witnesses, listed in `groups_with_checked_transport`. Without that mapping, per-trip reconciliation was skipped.
3. Structured `missing_information` objects (`UNKNOWN_EDGE_INTERVAL`) carry no text, so they were rejected.
4. There is no `vehicle_status` or `destination_status`. Both show as "확인 안 됨" / "미확인", which is correct: the planner does not report them.
5. Assumptions are untyped English strings, so the "모델 산출 화재 제한" column read "해당 가정 없음".
6. `contract-normal` and `contract-delayed` have **different `case_id`s**, so they cannot be paired.
7. A fifth status, `INVALID_INPUT`, exists for malformed input.
8. The 30-second handoff did not mention the late vehicle, because the planner gives no `DELAYED` status, only a later departure.

## Adapter changes (1.1.0), mapping Chat 1's documented `SCHEMA.md`. No check was loosened.

- An integer `schema_version` is read as a string, with a warning.
- Aliases: `unloading_end_s` → `unload_s`, `end_node` → `destination_id`; `boarding_s` = `boarding_end_s − boarding_start_s`.
- If `groups_with_checked_transport` is present, trips in those groups are checked and `empty_return` trips are not. The sum of checked trip people must still equal `people_with_checked_transport`.
- `conditional_trips` are **never** shown as checked; a warning gives their count.
- Structured missing-information items get Korean text, e.g. "도로 구간 e1 의 T0+0초~40초 상태 모름 … 모름은 안전하다는 뜻 아님".
- `INVALID_INPUT` is rejected with the planner's reason.
- If no assumption is typed as a fire restriction, a note marked **어댑터 해석** says closures are read as simulated fire restrictions, as Chat 1's fixture note states, not as observed closures.
- The handoff now reports a departure that moved later, plus one sentence for departures that became unknown. Destination confirmations are merged per destination.
- A4 fit is measured, not estimated. The tools re-print at a higher density class until the PDF is one page, and the viewer measures an off-screen print layout.

## Final run (`tools/verify.sh`)

| Run | Result | Status | People (total / checked / unconfirmed) | Final unload | A4 (county / facility) |
|---|---|---|---|---|---|
| `demo_pair_with_meta` | **ACCEPTED** | CHECKED_ROUTE | 12 / 12 / 0 | T0+35분 → **T0+57분 (10:57)** | 1 / 1 |
| `demo_pair_no_meta` | **ACCEPTED** (labels 미제공) | CHECKED_ROUTE | 12 / 12 / 0 | T0+57분 | 1 / 1 |
| `shuttle_single` | **ACCEPTED** | CHECKED_ROUTE | 12 / 12 / 0 | T0+1분 (contract times are seconds) | 1 / 1 |
| `missing_input_single` | **ACCEPTED** | MISSING_INPUT | 6 / 0 / 6 | 모름 | 1 / 1 |
| `contract_pair` (normal vs delayed) | **REJECTED**, as intended | — | — | — | — |

The demo pair shows "2호차: 출발 T0+20분→T0+30분, 하차 T0+35분→T0+57분". A 10-minute delay at the vehicle became 22 minutes at unloading, because the planner rerouted around the modelled restriction. The two views agree on every shared field (unit and browser tests). The viewer printed this pair, loaded through its file inputs, on one A4 page per view.

30-second handoff (`demo_pair_with_meta/handoff_30s.txt`):

> 훈련 상황입니다. 가상 요양시설 시설 당직 책임자입니다. 10시 14분 기준, 변경 사항 보고합니다. 2호차 출발이 10시 20분에서 10시 30분으로 늦어졌습니다. 전체 12명 모두 배정은 계산상 확인됐습니다. 가상 대피소 (SH) 수용 여부는 아직 확인 전입니다. 전원 하차는 계산상 10시 57분인데, 수용 확인 전 값입니다. 이상입니다.

Only the demo-pair-with-metadata A4 PDFs are committed. The HTML, PNG and other PDFs in these folders are regenerated by `tools/verify.sh`; every run's `integration_report.json` and handoff text are committed.

## Still open (planner ↔ brief)

- The planner gives no vehicle or destination status. Every vehicle shows "확인 안 됨" and every destination "미확인"; a person must supply these.
- The planner input has no mobility or transport needs per group. With metadata the needs read "미제공"; without it, group labels are just ids.
- The contract pair uses two different `case_id`s. To compare baseline and revised, Chat 1 should keep one `case_id`, as the demo pair does.
- Exercise update times are not in planner output and must come from the briefing metadata.
- The planner's assumptions are in English and are shown verbatim.
