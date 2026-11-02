# Last-mile kit — 현장 전달 문구 / Field messages

The planner's result for a village or care facility is only useful if it reaches the people who
must act on it. In the March 2025 Gyeongbuk wildfires most of the people killed or seriously injured
were 60 or older (Newsis, 2025-03-27, 「산불 피해 '최대·최다·최악'…사상자 56명, 대부분 60대 이상」,
https://www.newsis.com/view/NISX20250327_0003115304), and vulnerable residents reportedly missed
their evacuation window partly because older phones did not receive disaster texts (Kyongbuk Maeil,
2025-04-16, 「경북산불, 인명피해 증가…이유는?」, https://kbmaeil.com/article/20250416500546). The kit
therefore turns each origin's planner result into short, fixed wording that a village head or care
worker can pass on as is — in writing, over the village loudspeaker or by phone: a concrete time, a
place and a plain reason, without claiming more certainty than the model has.

It adds no data and computes no route. Every sentence is a deterministic template filled with the
planner's own result for the scenario on screen (recorded fire scenarios only) and, when present,
the deadline explanation file (§6).

Code: `planner/src/features/lastmile/` · tests: `tests/planner/lastmile*.ts` · one hook in
`planner/src/components/RightPanel.tsx` (origin detail, below the departure windows).

## 1. Outputs per origin (Korean source + English)

| Output | Audience | Limit (enforced) | Notes |
|---|---|---|---|
| SMS 단문 | residents, families | Korean ≤ 90 bytes in strict EUC-KR (KS X 1001); English ≤ 160 GSM-7 characters | First line: data time + `기록재현` / `REPLAY … not live`; short forms of the mandatory lines (§3) |
| Long text 장문 (LMS) | 이장, facility staff | ≤ 2,000 bytes EUC-KR (both languages) | First line `[2025년 기록 재현 · 실제 상황 아님]`; verbatim mandatory lines |
| Village broadcast 마을방송 | residents | ≤ 60 s read aloud at the assumed rate (§4) | Opens with `이 방송은 실제 상황이 아닙니다.` (replay); required blocks, then optional ones (§5) |
| Phone-call script | care staff → families | none; estimated duration shown | `[brackets]` for the caller; "before the call" checks first; villages: the no-car line |
| One-page card | 이장, facility staff (may be posted) | A5 at 14 pt or A4 at 18 pt, one page | Status as icon + text, the time in large type, badge `실제 상황 아님` |
| CSV | staff | — | One row per origin (§8) |

Every output states the data time (KST) and, for a recorded fire, that it is a replay of the
recorded 2025 data — first, in the SMS and the long text. Clock times are the input time plus the
planner's offsets, in KST. Research origins (recorded mission start points) get no field messages:
nobody lives there, so no resident-addressed text is made for them.

## 2. What each verdict may say

The kit never decides anything itself; `plan.ts` maps the planner's result to one of four message
kinds and fails closed to the less specific one on any inconsistency.

- **checked_route → `leave_by`** — only when every requested departure time from the first one up
  to T has a checked route, T being the contract's contiguous basis
  (`latest_contiguous_checked_depart_offset_s`). If later times are checked but one in between is
  not, the message keeps T (earlier than the planner's headline deadline) and says why. Window-closed
  times are not requests. Each output gives: leave by T ("do not wait until this time"), the
  destination checked at every time up to T (or "the destination depends on the departure time"),
  the arrival time and minutes by car when known, what limits T (below), the data time and the
  mandatory lines. **What limits T is never presented as fire unless the explanation file says so**:
  - nothing later was requested (the last departure checked, 50 min after the input time in the
    booth caches): "모델이 점검한 마지막 출발 시각이 T입니다 … 이 시각은 불길 때문에 정한 것이 아닙니다", and
    the card labels the time `점검한 마지막 출발 / Checked up to` instead of `출발 마감 / Leave by`;
  - explanation `window` with `deadline_cause: time_window` — the file proves only that the NEXT
    checked time fails, and the line says exactly that: "다음 점검 시각인 N에
    출발하면 1시간 자료 범위 안에 도착해 머물 수 없어, 그보다 늦은 출발은 점검하지 못했습니다. 이 시각은
    불길 때문에 정한 것이 아닙니다" (same label);
  - explanation `flame_on_route` for the message's destination: the fire reason (where, when, k of 4
    fire scenarios from the forecast; leaving at the next checked time may meet it);
    `no_flame_avoiding_route` (cause `flames`): "다음 점검 시각인 N에 출발하면 산불 예측 시나리오상
    불길을 피하는 길로는 제시간에 도착해 머물 수 있는 도착지가 없습니다";
  - otherwise the neutral "T보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다".
- **checked_route without a contiguous basis → `partial`** — no departure time; "출발 시각에 따라
  모델 결과가 달라, 출발 시각을 하나로 안내하지 않습니다"; follow official evacuation guidance. (No
  origin of the six booth caches is in this state; covered by synthetic tests.)
- **model_no_route → `no_route`** — by audience: the long text and card tell the 이장 / facility
  staff to contact 119 and the 읍·면사무소 now and follow official instructions; residents and families
  (SMS, broadcast, call script) are told to follow the official instructions of the 이장 (facility)
  and the 읍·면사무소 and, in an emergency, to report to 119 — never "call 119 now". No departure time,
  no clock time other than the data time, no tactical advice. With a consistent explanation: the
  roads out of the area reachable without meeting flames ("이 마을에서 차로 빠져나갈 수 있는 길 n곳"),
  distinct labels only ("길 2곳(둘 다 구계리 부근 도로)" when they share one), singular wording for
  one road, "자료 시각에 이미" when every exit is burning
  at the input time, and "길마다 … 최소 k가지" so k never reads as one scenario blocking every road.
- **unresolved (incl. not computed / not checkable) → `unresolved`** — the model could not check a
  route; this means neither that a route exists nor that it does not; follow official evacuation
  guidance. Never green, never a departure time, never explained.

User-drawn spread zones (an assumption) produce no field messages. MOCK and test data are marked in
every output, including the first line of the SMS.

## 3. Mandatory lines and words never used

Written outputs (card, long text) carry verbatim: `공식 대피 명령이 우선합니다.` /
`Official evacuation orders come first.` and `모델 기반 계획 정보 · 실시간 아님` /
`Model-based planning information · not live`. Spoken outputs say them as sentences; a replay
broadcast says "이 방송은 실제 상황이 아닙니다 … 모델 기반 계획 정보입니다" instead of "실시간 정보가
아닙니다". The card also carries the planner footer (`사전 계획 보조 도구입니다. 실시간 대피
지휘·운영용이 아닙니다.` / `Planning aid only — not for live evacuation operations.`) and the
fire-input banner text.

A Korean SMS is 90 bytes (45 Hangul) in total and the two verbatim lines alone take 62 bytes
(28 + 34), so the single SMS — and only the SMS — uses short forms: `공식명령 우선·실시간 아님` with
`모델`, and `Official orders come first.` / `not live` / `Model-based plan` (`strings.ts`).

Never used, in any output (`FORBIDDEN`, case-insensitive substrings; names from the data are
masked first so a village called 안전마을 does not trip it): 안전/safe, rescue or pickup words
(구조, 데리러, 태워, 픽업, "we will send", "vehicle will" …), shelter-in-place or "stay home/wait"
advice, and reassurance (보장, 안심, 괜찮, "guarantee", "don't worry", "no danger" …). Scenario
members are always "fire scenarios from the forecast" (산불 예측 시나리오). A departure instruction
(`DEPARTURE_INSTRUCTION`) appears only in `leave_by` messages; "call 119 now" (`RESIDENT_119_NOW`)
never in the SMS, broadcast or call script.

`checks.ts` checks all of this for every output of every origin (lengths, mandatory phrases, data
time, replay note with its year, the replay marker on the first line of the SMS and long text, the
broadcast's opening sentence, forbidden words, departure instructions, "119 now" to residents, clock
times). The panel disables copy and print for a text that fails and says why; the CSV leaves its
cells empty and marks it `검사 실패 — 사용 금지`. The tests use the same function as their oracle plus
independent re-implementations (§9).

## 4. How lengths are counted

- **Korean bytes**: strict EUC-KR — ASCII 1 byte, a KS X 1001 character 2 bytes. The repertoire is
  built from the platform's WHATWG `euc-kr` decoder restricted to lead/trail bytes 0xA1–0xFE
  without the private-use rows; anything outside (e.g. `—`, rare syllables, emoji) is reported as
  unencodable and fails the check. The tests cross-check every count with Python's `euc_kr` codec.
- **English SMS**: GSM 03.38 septets; extension-table characters count 2; any other character would
  force UCS-2 and fails the check.
- **Spoken length**: Korean syllables with numbers expanded the way they are read (native-Korean
  hours and counters, Sino-Korean minutes and dates, 119 digit by digit, "1.4 km" as 일점사
  킬로미터); English words with every digit and decimal point counted as a word.
- **Reading-rate assumption**: Korean **3.0 syllables/s** including pauses. Hwang & Lee (2012),
  「다문화가정 이주여성의 발화속도와 쉼」, *The Journal of the Acoustical Society of Korea* 31(2):63–72
  (https://www.koreascience.kr/article/JAKO201212961960491.pdf) measured 5.04 syllables/s overall,
  pauses included, for native Korean speakers reading aloud; 3.0 is about 40 % slower, so a script
  that fits at 3.0 also fits a slow, deliberate announcer. English: **2.0 words/s** (120 wpm),
  below the 150–160 wpm usually quoted for read speech. Both are assumptions for a loudspeaker to
  older listeners, not measurements of one; the panel states them next to the estimate.

## 5. Plain Korean for older listeners; the broadcast

Short sentences in 하십시오체 (the SMS too: `공식안내 따르십시오`); times spoken as 새벽/오전/낮/오후/밤
+ hour ("새벽 2시 20분"); "컴퓨터 예측 계산" instead of "모델" in spoken text; only particles that do
not depend on the preceding sound (까지/에/의/에서/입니다) follow inserted names or times. An unnamed
destination is "지도 자료에 이름이 없는 학교" in writing and "이름 없는 학교" when spoken; its OSM id
appears only in the card's staff footer. The English text is the project's own translation of the
Korean source, not machine translation.

The broadcast (`assembleSpoken`) keeps every required block — for a replay the opening "이 방송은
실제 상황이 아닙니다.", the greeting, the data sentence, the leave-by sentence with the destination,
the road entry point when it is more than 500 m away, **the no-car line** ("차가 없는 분은 이장에게
바로 알리십시오" / facilities: "차가 부족하면 읍·면사무소에 바로 알리십시오"), "대피 장소는 공식 안내를
따르십시오" and "공식 대피 명령이 우선합니다". If those alone exceed 60 s, a block's shorter wording
(without a long facility or destination name) is used, block by block. Then the optional blocks are
added while the script stays within 60 s: the reason (what limits T, or the flame reason), then the
repeat ("다시 알려 드립니다. 실제 상황이 아닌 2025년 기록 재현입니다.").

## 6. Deadline explanation (P2 contract `wfg.explanation/1`)

`explanation.ts` loads `data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json` with a
same-origin relative fetch under `import.meta.env.BASE_URL` — the only network request of the kit,
to a static file of the app itself, so it works in the static (no-API) build. A missing file, an
SPA fallback page or a network error means *absent*; bad JSON, another schema or another
region/input/scenario set means *invalid*; either way the messages are built without reasons, and
the dialog says which. Nothing is fabricated when the file is absent.

An entry is used only when it agrees exactly with the planner: same verdict; for `leave_by` the
entry's `deadline_offset_s` equals the planner's deadline, the message's T is that deadline (not an
earlier contiguous basis), and `next_offset_s` / `next_verdict` match the sweep with the next
departure recorded as `model_no_route` (an unresolved next time is never explained). Then:

| `reason_code` (`detail_code`) | used when | printed as |
|---|---|---|
| `flame_on_route`, `dwell_at_destination` | `binding[0]` (the shown route's item) is usable and the message's destination is in its `destination_ids` | fire reason: where (label below), when, k of n; leaving at the next checked time may meet it |
| `no_flame_avoiding_route` (`window_fire_detour`, `other_shelters_flame_blocked`) | status `explained`, `deadline_cause: flames` | "다음 점검 시각인 N에 출발하면 산불 예측 시나리오상 불길을 피하는 길로는 제시간에 도착해 머물 수 있는 도착지가 없습니다" |
| `window` (`window_fire_free`) | status `explained`, `deadline_cause: time_window` | leaving at the next checked time the trip cannot finish within the 1-hour range, so later departures were not checked; not set by fire |
| `window` (`outside_recorded_arrival_window`) | — (the next time is window-closed: the planner's own "last departure checked" line) | — |
| `no_later_offset` | — (the planner's own "last departure checked" line already says it) | — |
| `all_exits_blocked` (`flame_free_area_closed`; model_no_route) | every exit usable, one `members_total` | roads out by car, distinct labels (§2) |
| `all_exits_blocked` (`entry_point_in_flame`) | status `explained` | the road entry point is in flames at departure |
| `no_flame_avoiding_route` (`no_flame_avoiding_route_fits_window`; model_no_route) | `deadline_cause: flames` | no flame-avoiding road fits the range (no clock time) |
| `window` (`no_route_even_without_fire`; model_no_route) | `deadline_cause: time_window` | no destination fits the range even without fire |
| `unresolved_next`, `other`, any unknown code | never | — |

A usable item has a finite flame time inside the recorded window, distinct members
`0 … members_total − 1`, flame contact after the vehicle passes (binding items), and a label from
the data: `osm_name`, `osm_ref`, `unnamed`, or `nearest_place`, which names a road point by a
nearby place and the straight-line distance to it, never as the road's name — "구암리에서 약 800 m
떨어진 도로" / "a road about 800 m from Guam-ri", or "이 마을에서 … / … from this village" when the
place is the origin itself (`place_is_origin`). The composed label is at most 40 characters. The
SMS never carries a reason (no room).

## 7. Languages

`LANGUAGES` in `strings.ts`: Korean is the source, English the brief-required translation; both
are marked `nativeSpeakerReview: 'pending'`, and the dialog and the CSV say so (`원어민·현장 검토 전`).
A further language can be added as a template set but stays disabled — out of the panel, the CSV
and every output — until a native speaker has reviewed it (tested).

## 8. Panel, printing and CSV

The origin detail shows a "현장 전달 문구 / Field messages" section. Its dialog lists every village
and facility of the scenario in urgency order, shows the status, the explanation state, the
rule-check result and each text in both languages with its counter (bytes, GSM-7 characters,
estimated seconds), its review state and a copy button. It previews the card and prints it (this
origin at A5 or A4, or every origin at A5, one card per page) through a print-only root (`@page`
size, everything else hidden). The CSV (UTF-8 BOM, CRLF, Korean or English headers) has one row per
origin with every text, its counters, the deadline, destination, data time, scenario, fire input,
MOCK/test flags, reason source, the rule-check result and the review state.

Card layout (`lastmile.css`): A5 148 × 209.6 mm with 7/8 mm padding at 14 pt, A4 210 × 296.6 mm
with 14/16 mm padding at 18 pt, line-height 1.32, black on white, bundled Pretendard Variable. On A5
the header, category and planner footer line are 12 pt; the staff provenance line (scenario id,
stamps, unnamed-destination id) stays at 10 pt so every card keeps one page. The fit is tested (§9)
for every origin of the six caches, plain and with 40-character road names.

## 9. Tests

Run from `planner/` (single worker on small machines):

```
NODE_OPTIONS=--max-old-space-size=2048 npx vitest run --no-file-parallelism --maxWorkers=1 \
  ../tests/planner/lastmile.test.ts ../tests/planner/lastmile.cache.test.ts \
  ../tests/planner/lastmile.render.test.ts ../tests/planner/lastmile.print.test.ts
```

- `lastmile.test.ts` — counting rules, KST wording, the message plan per verdict (contiguous
  basis, gaps, partial, destination coverage, window-closed times), each template per verdict and
  audience, MOCK/test marking, worst-case dates, explanation loading/fallback/consistency with a
  synthetic file that mirrors every reason code of the real files (flame, window fire-free / mixed
  / detour, no later offset, unresolved next, one exit, duplicate labels, no-route window), rule
  checks, CSV, the language registry, and inline snapshots of synthetic messages.
- `lastmile.cache.test.ts` — property tests over every village and facility of the six booth caches
  (2 regions × 3 recorded input times, loaded through the app's own cache reader): limits (Korean
  bytes cross-checked with Python `euc_kr`, an independent GSM-7 class), mandatory lines, replay
  first, broadcast opening, no "119 now" to residents, the no-car line and far entry points in every
  leave-by broadcast, forbidden words and departure instructions with independent patterns; then
  the same with a contract-shaped synthetic explanation (40-character road names) and with one
  whose deadlines are off by one step (no reason at all); and, when the real explanation files are
  present (`planner/public/data/explanations/`, or a directory named by `WFG_EXPLANATIONS_DIR`),
  every rule over every origin with them. Inline snapshots of three real origins: 삼춘리
  (leave_by), 구계리 (no_route), 광연리 (unresolved).
- `lastmile.render.test.ts` — the dialog and card in jsdom: counters, review labels, copy, print
  root, CSV, fail-closed disabling, verdict icons.
- `lastmile.print.test.ts` — a browser-free box-model estimate (`lastmile.printfit.ts`, measured
  advance widths of the bundled font) that every card fits; and, when Playwright with Chromium is
  installed, the real print layout of every card (no overflow, body ≥ 14 pt, header / footer line
  ≥ 12 pt, estimate never below the real height) and PDFs with exactly one page per card.

Synthetic fixtures (`lastmile.fixture.ts`, `lastmile.cachedata.ts`) are marked SYNTHETIC and never
leave the tests.

## 10. Limitations

- The deadline explanation files are produced by another work package and are not in this branch;
  the committed tests use contract-shaped synthetic files (the real-file test runs when they are
  present).
- The wording has not been reviewed with village heads, care staff or older residents, nor by a
  native English speaker; reading rates are assumptions (§4).
- The single SMS uses short forms of the mandatory lines; the long text, card and scripts carry them
  verbatim.
- Results are model results for vehicles from the road entry point: no walking, boarding time,
  congestion, road closures or smoke; departure times between the 10-minute steps are not checked.
- Print fit is verified in Chromium only; other browsers' print engines may break lines differently.
- Carriers differ in how they count and split Korean messages; the 90/2,000-byte limits follow the
  common EUC-KR convention.
