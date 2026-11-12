# F-C1 closing: see-before-leave cannot be decided on this event from the available data

**Status.** Closed as a verified negative result. This is the orchestrator's decision on Iris's recommendation,
2026-11-12. All three analyses were defined in advance and each returned "cannot decide" for a stated reason. The
conclusion is about the data, not the method.

> **For any public description:** on this event, neither satellites nor published accounts can establish
> village-level timing of sight against departure.

## The three analyses

| # | Analysis | Definition and result | Verification | Outcome | Why it cannot decide |
|---|---|---|---|---|---|
| 1 | Planner cache: the 2025 replay, 522 cases at 174 places, 1 h scenario | `DEFINITION.md` v2 @d9bb95d; `RESULTS.md` | Hannah PASS WITH NOTES (0f7db4b), notes applied | **No robust negative gap.** Flames: 76 non-negative, 425 indeterminate, 0 negative. Smoke: 262 / 239 / 0. 21 had no route. | Only 15 of 522 deadlines are set by the fire within the 1 h window. The 10 pessimistic flame negatives flip under the optimistic setting. |
| 2 | Satellite brackets: 6 documented villages, plus the unselected set of 174 planner places | `DEFINITION_C1b.md` @dae181e + amendment @a285c67; `RESULTS_C1b.md`; `C1B_documented.json` regenerated with committed code (99b9972) | Hannah PASS WITH NOTES (0207925); notes 1–3 closed (99b9972) | **Documented villages:** all indeterminate (9 bracketed points); both 강구 halls not bracketed. **Unselected set:** see below. | The FIRMS arrival brackets at village scale are 4–6.5 h wide. The bracket start is not a lower bound (non-detection is not absence of fire). AHI cannot narrow a 500 m footprint (one 2 km pixel). |
| 3 | Documented accounts: a sighting and an arrival at the same place | `DEFINITION_C1b_accounts.md` @0674f70 + amendment 1 @02c312d + sources @2ba8a85; code @0b2244d; `RESULTS_C1b_accounts.md` @345a8c7 | Hannah PASS (345a8c7); Iris accepted | **None of the 3 eligible cases can answer.** C1 (지품) has a sighting but no arrival; C2 (매정리) an arrival but no sighting; C3 (신덕리) a sighting with the arrival only implied. | Sources were read in full by Sofia. No published account gives both a timed sighting and a timed arrival for the same place. |

**Unselected set** (analysis 2, all 174 planner places, observer = the OSM place point), reported in full:

- **Files.** `C1B_places_0_87.json` (sha256 b803d506…) and `C1B_places_87_174.json` (sha256 ea1eaa5f…), from
  `seebefore/c1b.py --places-only --places-slice 0:87` and `87:174`.
- **Order.** Places are sorted by (region, origin_id). Slice 0:87 is 84 Uiseong-Andong places and 3 Yeongdeok;
  slice 87:174 is 87 Yeongdeok places.
- The first slice ran with c1b.py before the row-sort change (02c312d), which affects output order only.

| Flame | Smoke | Places 0–87 | Places 87–174 | **All 174** |
|---|---|---:|---:|---:|
| indeterminate | indeterminate | 49 | 46 | **95** |
| not bracketed | not bracketed | 15 | 41 | **56** |
| indeterminate | non-negative, not robust to the leave-by simplification | 12 | 0 | **12** |
| non-negative, not robust to the leave-by simplification | non-negative, not robust to the leave-by simplification | 11 | 0 | **11** |

- **No place has a robust negative sign.** A robust sign needs both timing rows and both visibility settings to agree
  (amendment 1.2).
- **12 places have a negative gap in at least one row and setting.** Correction, Hannah 2026-11-12: an earlier
  wording said "no place has a negative sign", which overstated. All 12 are classed indeterminate:
  - **괴산리 and 신월리** (Uiseong): negative under **both** settings, for flames and smoke, in the detected-cells
    bracket row. Indeterminate only because the wide (kriged ±2 sd) row does not agree.
  - **괴산리 and 대탄리** (Yeongdeok): flame negative under the pessimistic setting in **both** timing rows. Not
    negative under the optimistic setting.
  - **9 more**: flame negative under the pessimistic setting in the detected-cells row only. These are 신덕리,
    하령리, 하화리, 덕곡리, 신애리, 오천리, 삼화리, 노물리 and 기사리.
  - **Why this matters.** A negative gap under the preliminary leave-by, which is an upper bound on the deadline, is
    the direction that is robust to that simplification. These places are where better timing data would most
    likely settle the question.
- **Non-negative signs (23 places, all in the first slice) are not robust.** The preliminary leave-by (arrival
  minus the fastest fire-free trip) is an upper bound on the true deadline (amendment 1.3).
- **Not bracketed** (56 places) means no FIRMS detection within 500 m of the place plus its entry cell. That
  covers 41 of the 87 Yeongdeok places in the second slice.

**Notes from the analyses that stand on their own:**

- **Which cue is modelled changes the answer.** At 신덕리 (C3), the pessimistic flame setting has no visible flame
  until hours after the documented sighting. The optimistic smoke setting has smoke in sight since the day before.
- **A pixel-level time cannot be used per cell.** That is the reason the AHI routing variant was withdrawn (F-DYN
  `STARTS_RULE.md`). AHI timing remains valid as "fire within about 2 km by t".

## What data would decide it

Timed observations of **both** the sighting and the arrival **at the same place**. The candidates:

1. **Emergency call (119) logs** with caller location and time.
2. **CCTV timestamps** with a known camera position and view.
3. **Agency incident records** at village level. Per Sofia, none is published. Two likely sources are not public:
   - 경북소방본부 「경북 초대형 산불 맵백서」 (announced July 2025, reconstructed from internal records);
   - the 산림청 situation maps and reports behind a civil team's March 2026 report.

   Both are targets for a 정보공개청구 (public-records request); Sofia has sent the request list to the
   orchestrator.
4. **A structured post-fire survey** of residents: when they first saw smoke or flame, from where, and when the
   fire reached them. The questions would be fixed before any answers are read.

F-C1 reopens only if one of these becomes available.

## Carried forward

- **Documented notification latencies go to Richard** (sent 2026-11-12) as inputs to the issue-order-by field on
  F-DYN:
  - 지품: local evacuation decision at about 16:30, county alert and CBS at 18:00;
  - 지품: a household left at 17:00 and the text arrived about 2 h later;
  - 매정리: about 30 min from the door-knock to departure;
  - 강구 (snippet only): text at 00:07, fire about 30 min later.

  Each was sent with its source.
- **Corrections made during F-C1, all recorded where they occurred:**
  - the MODIS 12:25 pass was hidden by a listing bug;
  - the AHI left-censored count is 42, not 62;
  - "지품 flames 17:55" is not in its source.
