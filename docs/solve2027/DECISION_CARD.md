# Decision card: what WildfireGuardian decides, and what it never says

WildfireGuardian answers one narrow question: **for one origin, one destination, one departure time and one recorded set of fire scenarios from the forecast, is there a vehicle journey that the model checks end to end?** "End to end" means driving, permitted waiting and the required stay at the destination. This card describes the code on `Main`. Sources are linked; quoted labels are copied from them.

## Exactly three verdicts

| Verdict | Planner label | Shown as | Meaning | Reached when (frozen kit decision) | What it does **not** mean |
|---|---|---|---|---|---|
| `checked_route` | 확인된 경로 | green, check icon, text | The whole journey (driving, waiting and the destination stay) was checked: no flame contact, and within the heat limits | One of the three `CHECKED_JOURNEY_*` statuses with `whole_road_check.status == CERTIFIED_ADMISSIBLE`; whole-road contact must be `CLEAR` | It is not "a guarantee of real-world safety" ([README](../../README.md#reproducibility-attribution-and-intended-use)) |
| `model_no_route` | 모델상 경로 없음 | black, slashed-circle icon, text | The relaxation search was exhausted, so no route exists in this model and input scope | `FULL_MODEL_REFUSAL_PROVEN` | Proof "that every real-world escape is impossible" |
| `unresolved` | 미확인 | grey hatch, question-mark icon, text | Neither a checked route nor a scoped refusal was established: timeout, cap, check not finished or failed, worker or cleanup failure | Everything else, with a `reason_code` such as `TIMEOUT` | Safe: unresolved is never green, never called safe and never counts toward a deadline |

Sources: [API verdict table](../../api/README.md#verdicts-and-reason-codes) (mapping in `api/verdict.py`), [planner honesty rules](../../planner/README.md#honesty-rules-the-ui-applies), [architecture §0](../../planner/docs/ARCHITECTURE.md#0-non-negotiable-rules). A job that ends `failed` "is never safe; treat it as `unresolved`".

## From verdicts to a leave-by time (출발 마감)

- The planner checks each origin at fixed departure offsets (default step 10 min, `VITE_DEPARTURE_STEP_MIN`) across the recorded scenario window ("0–3600 s after the input time", [architecture §1](../../planner/docs/ARCHITECTURE.md#1-fixed-facts-do-not-change)). "Times between offsets are not checked."
- Per departure time: checked if any candidate destination is checked; `model_no_route` only if every attempted destination is `model_no_route`; otherwise `unresolved`.
- **출발 마감** "= the latest departure offset with a checked route". When an earlier offset is not checked, the headline adds "앞선 출발 시각 중 확인되지 않은 구간이 있습니다 (연속 확인 기준 HH:MM | 없음)", using the API's conservative `latest_contiguous_checked_depart_offset_s`.
- The urgency list puts `model_no_route` first, then `unresolved`, then checked origins by their contiguous deadline.
- The planner states that "travel between an OSM point and its road entry node, and waiting at the origin before departure, are not modelled."

Sources: [planner README](../../planner/README.md#honesty-rules-the-ui-applies) and its [limitations](../../planner/README.md#limitations-also-in-the-about-panel); [dispatch-plan fields](../../api/README.md#dispatch-plan).

## Guardrails on `Main`

- **Fixed budget.** "Each request has a fixed 30 s budget, which is never raised"; the memory guard is 3072 MiB ([api/README.md](../../api/README.md#what-it-is), constants in [api/config.py](../../api/config.py)). Running out of time gives `unresolved`/`TIMEOUT`, never a refusal.
- **One authority.** The verdict is the frozen kit's authoritative journey decision mapped onto three states; the API and the planner never re-derive it. The decision module states: "No physical-safety claim is made by any status." ([integration/kit/decision/journey_decision_v2_1.py](../../integration/kit/decision/journey_decision_v2_1.py))
- **Independent check is optional.** The API notes that "a default `checked_route` or `model_no_route` is the kit's verdict without independent corroboration". When the offline checker is requested, a contradiction or an unfinished check downgrades the verdict to `unresolved` ([known limitations](../../api/README.md#known-limitations)).
- **Only checked routes leave the system as routes.** "Only `checked_route` results can be exported, so an unresolved result is never drawn as if it were a route" (other verdicts get HTTP 409).
- **Provenance everywhere.** Every response records the API and package versions, kit, checkpoint, git commit, SHA-256 of every input file, scenario IDs and host.
- **Every screen states its inputs.** A fire-input banner ("2025년 실제 산불 기록 기반 시나리오 재현" for recorded scenarios, "사용자 입력 확산 구역 (가정)" for drawn zones), a `MOCK` badge whenever data comes from the mock, and the footer "사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다." / "Planning aid only — not for live evacuation operations."
- **Assumptions are labelled.** Drawn spread zones carry "approximation, requires expert review"; the travel-time-only comparison is a dashed line labelled "이동시간만 고려한 경로 (비교용)" and is "never green or called safe"; dispatch plans accept only the `full` policy.
- **No invented places.** "Never invent villages, shelters, routes, fires or numbers." Unnamed places stay unnamed; a place with no accepted road node within 2 km is shown as "도로망 2 km 밖 — 점검 불가" and never sent.
- **Host is visible.** Precomputed results from a host other than the evaluated one are marked "시험 데이터 · 평가 호스트 아님"; every live result shows the host it was computed on next to its compute time.

## What the system never says

1. **That a route is "safe" / "안전한 경로".** The UI uses the word only to warn: "미확인은 안전이 아닙니다." / "Unresolved is not safe." ([planner/src/features/shared/strings.ts](../../planner/src/features/shared/strings.ts)).
2. **That a timeout means "no route",** or that `model_no_route` proves escape is impossible: "A timeout is unresolved, and a scoped refusal is not proof that every real-world escape is impossible" ([README](../../README.md#4-import-it-in-python)).
3. **A leave-by time built on an unresolved departure.**
4. **A village, shelter, route, fire or number that is not in its inputs.**
5. **That its scenarios are simulations of the actual fire.** Each check uses "one scenario set of 4 members". Besides the fire already burning at the input time, each member's new ignitions are independent per-cell draws from the forecast's next-hour new-burn probabilities, at uniformly drawn times within the one-hour horizon (`draw_ignitions` in [integration/src/wfg_latest/bridge.py](../../integration/src/wfg_latest/bridge.py)).
6. **That it can direct a live evacuation.** Every screen's footer says it is a planning aid, not for live evacuation operations.

## Outside the decision's scope

A checked route covers the implemented model and declared inputs only. "Smoke, embers, convection, shielding, data freshness, accessibility and destination suitability require additional evidence for operational use" ([README](../../README.md#reproducibility-attribution-and-intended-use)). The evaluated road graphs record "assumed 40km/h rounded up to 1s ticks; missing oneway assumed two-way" and "no road/passability or wait-location field validation" in their `provenance` field. These are the inputs that [`tools/fetch_routing_inputs.py`](../../tools/fetch_routing_inputs.py) downloads and verifies. Planner destinations are OpenStreetMap-tagged shelters, assembly points, schools, community centres and 회관 halls ([architecture §4.2](../../planner/docs/ARCHITECTURE.md#42-plannerpublicdataregionsregion_idplacesgeojson-consumed-by-the-app)), not an official shelter designation. Field effectiveness and evacuation safety have not been established.
