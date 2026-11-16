# Input contract — kcf-facility-brief

Version: `kcf-brief-core/1.1.0`. Times are **seconds after the exercise time origin T0**. A `null` time means
**unknown** and is displayed as **모름**. It is never filled from an earlier file. Displayed times are rounded **up**
to the minute (`T0+N분`). When the metadata gives a T0 clock, a fictional clock time is added (`T0+25분 (14:25)`).

## 1. Planner output (baseline and revised)

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | recorded in provenance; a major-version difference between baseline and revised produces a warning |
| `case_id` | string | must match across baseline, revised and metadata |
| `status` | enum | `CHECKED_ROUTE`, `MODEL_SCOPED_NO_ROUTE`, `MISSING_INPUT`, `UNRESOLVED` |
| `reason` | string \| null | shown verbatim as "플래너 사유(원문)" |
| `final_unload_s` | number ≥ 0 \| null | **must be null** if any person is unconfirmed or `status ≠ CHECKED_ROUTE`; otherwise must equal the latest checked trip `unload_s` |
| `groups_total` | int ≥ 0 | ≥ distinct trip `group_id`s; = metadata group count |
| `people_total` | int ≥ 0 | = sum of metadata group people |
| `people_with_checked_transport` | int ≥ 0 | ≤ `people_total`; = sum of `people` over trips with `assignment_checked: true` |
| `trips` | array | see below |
| `missing_information` | array of string \| `{code, kind?, text_ko\|text, who_role?}` | each item becomes an outstanding confirmation |
| `assumptions` | array of string \| `{code, kind?, text_ko\|text}` | `kind: MODEL_FIRE_RESTRICTION` goes to the "모델 산출 화재 제한" column; all others are listed as 탑승·운행 전제 |

### Trip

| Field (accepted aliases) | Type | Notes |
|---|---|---|
| `trip_id` (`id`, `trip`) | string | generated if missing (warning) |
| `vehicle_id` (`vehicle`) | string | label from metadata `vehicles` |
| `group_id` (`group`) | string | must exist in metadata `groups` when groups are given |
| `people` (`people_count`, `passengers`, `n_people`) | int ≥ 0 | required |
| `vehicle_status` | `READY \| EN_ROUTE \| DELAYED \| UNAVAILABLE \| UNKNOWN` | missing or unrecognised values become `UNKNOWN` |
| `assignment_checked` (`checked`, `transport_checked`) | bool | planner-checked assignment, **not** boarding. If any trip lacks this field, per-trip reconciliation is skipped and the brief says "대조 불가" |
| `depart_s` (`departure_s`, `depart_time_s`) | number \| null | |
| `unload_s` (`unload_time_s`, `arrival_unload_s`) | number \| null | must be ≥ `depart_s` |
| `boarding_s` (`boarding_duration_s`) | number \| null | assumed boarding duration |
| `destination_id` (`destination`) | string | label from metadata `destinations` |
| `destination_status` | `CONFIRMED \| AWAITING_CONFIRMATION \| UNKNOWN` | anything not `CONFIRMED` becomes an outstanding confirmation |

Fields are read under an alias only when the canonical name is absent. Each alias read is reported as a warning.

## 1a. kcf-facility-planner dialect (Chat 1, `SCHEMA.md` schema_version 1)

The dialect is detected by the presence of `groups_with_checked_transport`. In that dialect:

- `schema_version` may be an integer, which is read as a string.
- `unloading_end_s` → `unload_s` and `end_node` → `destination_id`.
- `boarding_s` = `boarding_end_s − boarding_start_s`.
- Trips in `groups_with_checked_transport` are `assignment_checked: true`; `empty_return` trips are not checked
  and are shown as "빈 차 복귀".
- `conditional_trips` are never shown as checked.
- `UNKNOWN_EDGE_INTERVAL` items in `missing_information` get Korean text.
- `INVALID_INPUT` is rejected.
- If no assumption has `kind: MODEL_FIRE_RESTRICTION`, the adapter adds one labelled **어댑터 해석**: planner closures
  are simulated fire restrictions, not observed closures.

All totals, time and cross-case checks still apply.

## 2. Briefing metadata (`briefing_meta.json`)

```json
{
  "meta_version": "kcf-brief-meta/1",
  "case_id": "KCF-EX-DELAY-01",
  "exercise_label": "훈련 · 가상 상황 · 실제 상황 아님",      // must contain 훈련
  "facility": { "label": "가상 … (훈련용)", "short": "가상 A요양병원" },
  "time_origin": { "label": "T0 = 시설 대피 결정 시각 (훈련 각본)", "clock": "14:00" },
  "roles": { "facility": "…", "county": "…", "fire": "…", "police": "…", "destination": "…" },
  "groups": [ { "group_id": "G2", "label": "휠체어 이용", "people": 4, "need": "…",
               "spoken": "휠체어 이용", "request": "휠체어 리프트 차량 1대 지원", "request_role": "county" } ],
  "vehicles": { "V2": { "label": "2호차 (휠체어 리프트, 협약 차량)", "short": "2호차", "owner_role": "facility" } },
  "destinations": { "D1": { "label": "가상 임시대피소 (읍 체육관)" } },
  "updates": { "baseline": { "at_s": 300, "source_label": "플래너 1차 계산" },
               "revised":  { "at_s": 1500, "source_label": "플래너 재계산 — 2호차 지연 반영" } },
  "field_reports": [ { "at_s": 1080, "text": "…(가상)…", "source_role": "facility" } ],
  "road_status": [ { "segment": "가상 군도 3호선 고개 구간", "status": "UNKNOWN", "note": "…", "who_role": "police" } ],
  "assistance_requests": [ { "text": "…", "people": 2, "who_role": "fire" } ]
}
```

Rules: `updates.revised.at_s` must be greater than `updates.baseline.at_s`. A field report dated after the latest
update is rejected. In the "before" view, later field reports are excluded with a notice. A trip that departed
before the report time cannot still be `READY` or `DELAYED`. `road_status.status` is one of `UNKNOWN`,
`CLOSED_REPORTED` or `OPEN_REPORTED`. Every reported value is fictional.

## 3. Personal data guard

The tool rejects any key that looks like a personal field (`name`, `*_name`, `phone`, `contact`, `address`,
`birth`, `rrn`, `patient_id`, 성명, 이름, 연락처, 전화, 주소, 주민 …). It also rejects any value that looks like a
Korean mobile or landline number, a resident registration number or an email address, in any of the three files.

## 4. Derived quantities (identical in both views)

- 미확정 = `people_total − people_with_checked_transport`. Per group: group people − checked trip people in the group.
- Requests: one per group that has unconfirmed people, using the group's `request`, `need` and `request_role`, plus any metadata `assistance_requests`.
- Outstanding confirmations: delayed or unknown vehicles (unless already named in `missing_information`), each destination not `CONFIRMED`, every `missing_information` item, every `UNKNOWN` road segment, and always "실제 탑승·하차 인원".
- What changed: status, totals, unconfirmed count and final unload, then one line per trip (vehicle, status, assignment, people, departure, unloading, destination and its status), then missing information and assumptions added or removed.
