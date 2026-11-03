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
| Long text 장문 (LMS) | 이장, facility staff | ≤ 2,000 bytes EUC-KR (both languages) | First line `[2025년 기록 재현 · 실제 상황 아님]`; the data line names the origin's result source (§2); verbatim mandatory lines |
| Village broadcast 마을방송 | residents | ≤ 60 s read aloud at the assumed rate (§4) | Opens with `이 방송은 실제 상황이 아닙니다.` (replay); required blocks, then optional ones (§5) |
| Phone-call script | care staff → families | none; estimated duration shown | `[brackets]` for the caller; "before the call" checks first; villages: the no-car line |
| One-page card | 이장, facility staff (may be posted) | A5 at 14 pt or A4 at 18 pt, one page | Status as icon + text, the time in large type, badge `실제 상황 아님` |
| CSV | staff | — | One row per origin (§8) |

Every output states the data time (KST) and, for a recorded fire, that it is a replay of the
recorded 2025 data — first, in the SMS and the long text. Clock times are the input time plus the
planner's offsets, in KST. Research panel origins get no field messages: they are the start road
nodes of recorded research missions, not villages or care facilities, so there is no village or
facility to address (the data says nothing about who lives near them).

## 2. What each verdict may say

The kit never decides anything itself; `plan.ts` maps the planner's result to one of four message
kinds and fails closed to the less specific one on any inconsistency.

- **checked_route → `leave_by`** — only when every requested departure time from the first one up
  to T has a checked route, T being the contract's contiguous basis
  (`latest_contiguous_checked_depart_offset_s`). If later times are checked but one in between is
  not, the message keeps T (earlier than the planner's headline deadline) and says why. Window-closed
  times are not requests. Each output gives: leave by T ("do not wait until this time"), the
  destination checked at every time up to T (or "the destination depends on the departure time"),
  the arrival time and minutes by car when known — both from one rounding: the arrival rounded up
  to the whole minute (never earlier than the model's; the planner's panel shows it to the second)
  and the minutes as the difference of the two clocks shown, e.g. "10:10에 출발하면 10:53쯤 도착합니다
  (차로 약 43분 …)" for a 42 min 55 s trip (`compose.ts` `arrivalShown`) — what limits T (below), the
  data time and the mandatory lines. **What limits T is never presented as fire unless the explanation file says so**:
  - nothing later was requested (the last departure checked, 50 min after the input time in the
    booth caches): "모델이 점검한 마지막 출발 시각이 T입니다 … 이 시각은 불길 때문에 정한 것이 아닙니다", and
    the card labels the time `점검한 마지막 출발 / Checked up to` instead of `출발 마감 / Leave by` —
    the only case with that label (`plan.ts` `bigLabelKind`);
  - explanation `window` with `deadline_cause: time_window` — the next departure N **was** checked
    and has no checked route; the file proves that leaving at N none of the destinations checked can
    be reached and the stay finished in time even without fire. The line says only that, plus what
    the sweep shows: "다음 점검 시각인 N에 출발하면 불길이 없더라도 점검한 도착지 중 1시간 자료 범위 안에
    도착해 머물 수 있는 곳이 없습니다. T보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다. 이 시각은
    불길 때문에 정한 것이 아닙니다"; spoken: "그보다 늦게 출발하는 길은 확인되지 않았습니다. 이 시각은 불길
    때문에 정한 것이 아닙니다". The card label stays `출발 마감 / Leave by`;
  - explanation `flame_on_route` for the message's destination: the fire reason (where, when, k of 4
    fire scenarios from the forecast; leaving at the next checked time may meet it);
    `no_flame_avoiding_route` (cause `flames`): "다음 점검 시각인 N에 출발하면 점검한 도착지(후보
    대피소) 중 산불 예측 시나리오상 불길을 피하는 길로 제시간에 도착해 머물 수 있는 곳이 없습니다" — the
    file's claim covers the candidate shelters the planner tried, so the line names them;
  - otherwise the neutral "T보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다".
- **checked_route without a contiguous basis → `partial`** — no departure time; "출발 시각에 따라
  모델 결과가 달라, 출발 시각을 하나로 안내하지 않습니다"; follow official evacuation guidance. (No
  origin of the six booth caches is in this state; covered by synthetic tests.)
- **model_no_route → `no_route`** — by audience: the long text and card tell the 이장 / facility
  staff to contact 119 and the 읍·면사무소 now and follow official instructions; residents and families
  (SMS, broadcast, call script) are told to follow the official instructions of the 이장 (facility)
  and the 읍·면사무소 and, in an emergency, to report to 119 ("이장과 읍·면사무소의 공식 지시를
  따르십시오. 위급하면 119에 신고하십시오." in the broadcast and the call script; "위급 시 119" in the SMS)
  — never "call 119 now". No departure time, no clock time other than the data time, no tactical
  advice. With a consistent explanation: the roads leading out of the area reachable by car without
  meeting flames — the explanation's exits, not the roads out of the village, whose first roads are
  open in most recorded cases ("이 마을에서 불길을 만나지 않고 차로 갈 수 있는 구역을 벗어나는 길 n곳"),
  distinct labels only ("길 2곳(둘 다 구계리 부근 도로)" when they share one), singular wording for one
  road, "자료 시각에 이미" when every exit is burning at the input time, and "길마다 … 최소 k가지" so k
  never reads as one scenario blocking every road. The other no-route reasons name "점검한 도착지(후보
  대피소)" — the destinations the planner tried — never "no destination" at all.
- **unresolved (incl. not computed / not checkable) → `unresolved`** — the model could not check a
  route; this means neither that a route exists nor that it does not; follow official evacuation
  guidance. Never green, never a departure time, never explained.

User-drawn spread zones (an assumption) produce no field messages. MOCK and test data are marked in
every output, including the first line of the SMS (`MOCK`, `시험자료`, and `MOCK시험` — as many bytes
as `기록재현` — when both apply; English `MOCK` / `TEST` / `MOCK TEST`); the checks enforce it
(`checks.ts` `markerWords`), and no marker may push an output over its limit (§5).

**Provenance per origin.** Each origin's messages take their provenance from that origin's own result
(`input.ts` `originProvenance`, fed by `connect.ts`), never from the session:

- a result from the precomputed cache keeps the cache's provenance — its created time ("사전 계산
  2026-10-18 08:10 KST" on the long text's data line and the card's staff line; the cache file and
  time in the CSV) and the cache's own test-data flag (`planner/cache/**` was computed on the
  evaluated native macOS arm64 host);
- a result computed through the API — an origin recomputed in a cached scenario, or a live session
  such as the Docker front door's Linux API — never carries the cache's stamp; it says "실시간 API
  계산 · 계산 호스트 Linux x86_64 · 4 vCPU" (the hosts its results' route provenance reports, as the
  planner labels them) and is marked as test data — "시험 데이터 · 평가 호스트 아님" on the card, the
  SMS tag `시험자료` / `TEST`, the long text's first line and a closing note naming the host, the
  spoken "시험용 계산 자료입니다", the CSV — unless every host its results report is native macOS
  arm64, the planner's own evaluated-host rule (`src/api/cache.ts` `isTestDataHost`; the API reports
  only platform and machine, so the chip cannot be verified). A host that is not reported counts as
  not evaluated (fail closed). A live plan without any API result is never called computed.
- MOCK stays session-wide (the planner's MOCK rule, `isMockActive`): with the default `mock` build
  setting a live session is marked MOCK rather than test data; the Docker front door builds with
  `VITE_WFG_API_MODE=real`.

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

Never used, in any output of either language (`strings.ts` `FORBIDDEN`: case-insensitive
substrings, every word checked in every output; names from the data are masked first so a village
called 안전마을 does not trip it) — "safe", promises of a rescue, pickup or vehicle, shelter-in-place
or "stay / wait" advice, and reassurance. The full list (a test checks that it matches `FORBIDDEN`):

<!-- forbidden-list -->
- Korean (26): `안전`, `구조`, `구출`, `데리러`, `모시러`, `모시고 가`, `태워`, `픽업`, `차량을 보내`, `차를 보내`, `버스를 보내`, `차량 지원`, `이송해 드`, `실내 대피`, `옥내 대피`, `집 안에`, `집에 머`, `머무르십시오`, `대기하십시오`, `기다리십시오`, `보장`, `안심`, `걱정`, `괜찮`, `확실`, `무사`
- English (23): `safe`, `rescue`, `pick up`, `pickup`, `pick-up`, `we will send`, `will be sent`, `vehicle will`, `bus will`, `transport will`, `shelter in place`, `shelter-in-place`, `stay indoors`, `stay inside`, `stay home`, `stay put`, `wait for help`, `guarantee`, `certain`, `don't worry`, `do not worry`, `no danger`, `secure`
<!-- /forbidden-list -->

Scenario members are always "fire scenarios from the forecast" (산불 예측 시나리오). A departure instruction
(`DEPARTURE_INSTRUCTION`) appears only in `leave_by` messages; "call 119 now" (`RESIDENT_119_NOW`)
never in the SMS, broadcast or call script.

`checks.ts` checks all of this for every output of every origin (lengths, mandatory phrases, data
time, replay note with its year, the replay marker on the first line of the SMS and long text, the
broadcast's opening sentence, the MOCK / test-data marker, forbidden words, departure instructions,
"119 now" to residents, clock times). Every violation names its output (`ko.broadcast: …`), and the
kit fails closed **per output** (`messages.ts` `outputOk`): the panel greys the text that fails,
disables its copy button (or the print of that card) and says why, while the origin's other texts
stay usable; "print all cards" prints every card that passes and lists the ones left out; the CSV
leaves only the failing text's cell empty and marks the row `검사 실패 — 사용 금지` with the
violations. A violation that names no output blocks every output of the origin. The tests use the
same function as their oracle plus independent re-implementations (§9).

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
  that fits at 3.0 also fits a slow, deliberate announcer. English: **2.0 words/s** (120 wpm) — an
  assumption without a measured source, chosen slow for loudspeaker listening, with every digit
  counted as a word. Both are assumptions for a loudspeaker to older listeners, not measurements of
  one; the panel states them next to the estimate.

## 5. Plain Korean for older listeners; the broadcast

Short sentences in 하십시오체 (the SMS too: `공식안내 따르십시오`); times spoken as 새벽/오전/낮/오후/밤
+ hour ("새벽 2시 20분"); "컴퓨터 예측 계산" instead of "모델" in spoken text; only particles that do
not depend on the preceding sound (까지/에/의/에서/입니다) follow inserted names or times. An unnamed
destination is "지도 자료에 이름이 없는 학교" in writing and "이름 없는 학교" when spoken; its OSM id
appears only in the card's staff footer. English spoken outputs (broadcast and call script) read a
place name only when OSM has a Latin-script name (`name:en`); otherwise they use generic wording
("Attention, residents.", "from the nursing home", "the destination named on the card") — never a
Hangul name read in English (tested over every origin). Written English (long text, card) keeps the
name as the map data has it. The English text is the project's own translation of the Korean
source, not machine translation.

The broadcast (`assembleSpoken`) keeps every required block — for a replay the opening "이 방송은
실제 상황이 아닙니다.", the greeting, the data sentence, the leave-by sentence with the destination,
the road entry point when it is more than 500 m away, **the no-car line** ("차가 없는 분은 이장에게
바로 알리십시오" / facilities: "차가 부족하면 읍·면사무소에 바로 알리십시오"), "대피 장소는 공식 안내를
따르십시오" and "공식 대피 명령이 우선합니다". If those alone exceed 60 s, a block's shorter wording is
used, block by block: without a long facility or destination name, and — for a MOCK or test-data
origin — the data sentence with its markers folded in ("…기록을 모의 서버로 재현한 시험용 모델 기반
계획 정보입니다" instead of two extra sentences). Still over, a last-resort wording follows, block by
block (the greeting without the place name: "주민 여러분께 알려 드립니다."). Then the optional blocks
are added while the script stays within 60 s: the reason (what limits T, or the flame reason), then
the repeat ("다시 알려 드립니다. 실제 상황이 아닌 2025년 기록 재현입니다."). With MOCK, test-data or
both markers every origin of the six caches keeps every limit (tested); the plain outputs are
unchanged by these fallbacks.

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
| `no_flame_avoiding_route` (`window_fire_detour`, `other_shelters_flame_blocked`) | status `explained`, `deadline_cause: flames` | "다음 점검 시각인 N에 출발하면 점검한 도착지(후보 대피소) 중 산불 예측 시나리오상 불길을 피하는 길로 제시간에 도착해 머물 수 있는 곳이 없습니다" |
| `window` (`window_fire_free`) | status `explained`, `deadline_cause: time_window` | leaving at the next checked time none of the destinations checked can be reached and the stay finished within the 1-hour range even without fire; departures after T have no checked route; not set by fire (label `출발 마감 / Leave by`) |
| `window` (`outside_recorded_arrival_window`) | — (the next time is window-closed: the planner's own "last departure checked" line) | — |
| `no_later_offset` | — (the planner's own "last departure checked" line already says it) | — |
| `all_exits_blocked` (`flame_free_area_closed`; model_no_route) | every exit usable, one `members_total` | the roads leading out of the area reachable by car without meeting flames, distinct labels (§2) — never "the roads out of the village" |
| `all_exits_blocked` (`entry_point_in_flame`) | status `explained` | the road entry point is in flames at departure |
| `no_flame_avoiding_route` (`no_flame_avoiding_route_fits_window`; model_no_route) | `deadline_cause: flames` | none of the destinations checked (candidate shelters) can be reached in the range on a flame-avoiding road (no clock time) |
| `window` (`no_route_even_without_fire`; model_no_route) | `deadline_cause: time_window` | none of the destinations checked (candidate shelters) can be reached in the range even without fire |
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
MOCK/test flags, the origin's result source ("결과 출처": `사전 계산 캐시 · <cache file> · <created
KST>` or `실시간 API 계산 · 계산 호스트 <host>`, with `· 평가 호스트 아님` when not established as
evaluated-host output), the reason data ("이유 자료": the explanation file with its `code_commit` and
`generated_at`, when a reason line is used), the rule-check result and the review state. The dialog
shows the same result source for the chosen origin.

Card layout (`lastmile.css`): A5 148 × 209.6 mm with 7/8 mm padding at 14 pt, A4 210 × 296.6 mm
with 14/16 mm padding at 18 pt, line-height 1.32, black on white, bundled Pretendard Variable. On A5
the header, category and planner footer line are 12 pt; the staff provenance line (scenario id,
stamps, unnamed-destination id) stays at 10 pt so every card keeps one page. The fit is tested (§9)
for every origin of the six caches, plain, with 40-character road names, and with the MOCK /
test-data badges and live staff lines the app can produce. The English card's data line is one line
("Data time: … KST · replay of 2025 data"; the header already names the recorded fire) so that a
badge row still fits on A5.

## 9. Tests

Run from `planner/` (single worker on small machines):

```
NODE_OPTIONS=--max-old-space-size=2048 npx vitest run --no-file-parallelism --maxWorkers=1 \
  ../tests/planner/lastmile.test.ts ../tests/planner/lastmile.cache.test.ts \
  ../tests/planner/lastmile.property.test.ts ../tests/planner/lastmile.provenance.test.ts \
  ../tests/planner/lastmile.render.test.ts ../tests/planner/lastmile.print.test.ts \
  ../tests/planner/lastmile.docs.test.ts
```

- `lastmile.test.ts` — counting rules, KST wording, the arrival rounding, the message plan per
  verdict (contiguous basis, gaps, partial, destination coverage, window-closed times), each
  template per verdict and audience, MOCK / test-data / both marking, the spoken-script fallbacks,
  worst-case dates and names, explanation loading/fallback/consistency with a synthetic file that
  mirrors every reason code (flame, window fire-free / mixed / detour, no later offset, unresolved
  next, one exit, duplicate labels, no-route window), rule checks and per-output fail-closed, the
  CSV (result source, reason data, per-cell withholding), panel wording, the language registry, and
  inline snapshots of synthetic messages.
- `lastmile.cache.test.ts` — property tests over every village and facility of the six booth caches
  (2 regions × 3 recorded input times, loaded through the app's own cache reader): limits (Korean
  bytes cross-checked with Python `euc_kr`, an independent GSM-7 class), mandatory lines, replay
  first, broadcast opening, no "119 now" to residents, the no-route family instruction, the no-car
  line and far entry points, forbidden words and departure instructions with independent patterns,
  the arrival rounding, no Hangul read in English, "checked up to" only for the last departure
  checked, MOCK / test-data / both on every origin (limits and markers); then a contract-shaped
  synthetic explanation (40-character road names) and one whose deadlines are off by one step (no
  reason at all); and the six real explanation files (`planner/public/data/explanations/`, or a
  directory named by `WFG_EXPLANATIONS_DIR`): every rule, the reason each entry calls for with its
  flame time, k of n and exits (oracle in `lastmile.oracle.ts`, without the detail-code whitelist),
  and the pinned per-kind counts. Inline snapshots of 삼춘리 (leave_by), 구계리 (no_route) and
  광연리 (unresolved) without explanation files.
- `lastmile.property.test.ts` — 600 seeded synthetic cases (`lastmile.generator.ts`, mulberry32,
  seed 20261103, no new dependency) through the app's own plan and input builders: any date and
  minute, 30–120 min horizons, every step, gaps, late first checks, window-closed tails, missing /
  Hangul-only / long names, far entry points, cache or live results, MOCK and test flags,
  explanation entries of every code, consistent or not; the same independent properties.
- `lastmile.provenance.test.ts` — the store-aware `lastMileArgs` with the real booth cache: an
  origin recomputed through the API on a Linux, a macOS arm64 or an unreported host, and a live-only
  session built with `VITE_WFG_API_MODE=real` (the Docker front door) or the default MOCK setting.
- `lastmile.render.test.ts` — the dialog and card in jsdom: counters, review labels, the result
  source, copy, print root, CSV and its file name, per-output fail-closed (only the failing text or
  card withheld; "print all" prints the cards that pass and lists the rest), verdict icons.
- `lastmile.print.test.ts` — a browser-free box-model estimate (`lastmile.printfit.ts`, measured
  advance widths of the bundled font) that every card fits, also with the longest provenance lines
  and badges the app can produce; and, when Playwright with Chromium is installed, the real print
  layout of every card and of the 60 tightest badge / live-provenance variants per language and size
  (no overflow, body ≥ 14 pt, header / footer line ≥ 12 pt, estimate never below the real height)
  and PDFs with exactly one page per card.
- `lastmile.docs.test.ts` — every example in §11 equals the kit's output for that origin, and §3
  lists every word of `FORBIDDEN`.

Synthetic fixtures and generated cases (`lastmile.fixture.ts`, `lastmile.cachedata.ts`,
`lastmile.generator.ts`) are marked SYNTHETIC and never leave the tests.

## 10. Limitations

- **Not an official alerting channel — 재난문자·공식 경보가 아닙니다.** The kit prepares wording for
  village heads and care staff to pass on, built from a model replay of recorded data. It sends
  nothing, is not a cell broadcast (재난문자) or an official warning, and never replaces the
  instructions of the 읍·면사무소, 119 or the 이장; every output says that official orders come first.
- The six deadline explanation files ship in `planner/public/data/explanations/` (written by
  `tools/explain_deadlines`); the kit uses an entry only when it agrees with the planner, and the
  real-file test runs over all six (pinned per-kind counts). A newer file with other codes or
  classes gives no reason line until the kit is updated (fail closed).
- The wording has not been reviewed with village heads, care staff or older residents, nor by a
  native English speaker; reading rates are assumptions (§4).
- The single SMS uses short forms of the mandatory lines; the long text and the card carry them
  verbatim, the broadcast and the call script say them as sentences.
- Results are model results for vehicles from the road entry point: no walking, boarding time,
  congestion, road closures or smoke; departure times between the checked steps (10 minutes in the
  booth caches) are not checked.
- A live API result counts as evaluated-host output only when every host its results report is
  native macOS arm64 — the planner's own rule; the API reports platform and machine only, so the
  chip cannot be verified.
- Print fit is verified in Chromium only; other browsers' print engines may break lines differently.
- Carriers differ in how they count and split Korean messages; the 90/2,000-byte limits follow the
  common EUC-KR convention.

## 11. Examples from the booth caches

Every block below is the kit's output for a real origin of a booth cache (`planner/cache/…`, the
recorded scenarios computed on the evaluated host) with the deadline explanation file of the same
scenario (`planner/public/data/explanations/`) — what the panel shows. Labelled by region, recorded
input time, cache file and origin. Only the card's "작성 / Prepared" stamp is fixed (2026-11-02 14:00
KST, the time the tests use). `tests/planner/lastmile.docs.test.ts` regenerates each block and fails
if it differs.

### 삼춘리 (Samchun-ri) — 의성·안동, recorded input 2025-03-26 02:00 KST

`uiseong_andong_2025/20250325T170000Z.json`, origin `osm:node/415160437`: checked route, leave by
02:20; the next checked time (02:30) has no checked route, and the file shows that the 1-hour range,
not fire, sets the time (`window`, `time_window`) — so the card says `출발 마감`, never "checked up to".
The Korean broadcast has room for the repeat but not for the reason line; the English one has both.

SMS (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 ko.sms -->
```text
[25.3.26 02:00 기록재현]
모델상 02:20까지 차로 출발
공식명령 우선·실시간 아님
```

Long text (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 ko.lms -->
```text
[2025년 기록 재현 · 실제 상황 아님]
산불 대피 계획 정보 · 삼춘리(마을)
자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 사전 계산 2026-10-18 08:10 KST

■ 02:20(새벽 2시 20분)까지 차로 출발하십시오. 이 시각까지 기다리지 마십시오.
■ 모델이 점검한 도착지: 의성북부초등학교. 02:20에 출발하면 02:51쯤 도착합니다(차로 약 31분, 교통 정체 미반영).
■ 다음 점검 시각인 02:30에 출발하면 불길이 없더라도 점검한 도착지 중 1시간 자료 범위 안에 도착해 머물 수 있는 곳이 없습니다. 02:20보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다. 이 시각은 불길 때문에 정한 것이 아닙니다.
■ 실제 대피 장소와 길은 공식 안내를 따르십시오.
■ 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
■ 시각은 마을에서 195 m 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.

공식 대피 명령이 우선합니다.
모델 기반 계획 정보 · 실시간 아님
2025년 실제 산불 기록을 재현한 시나리오입니다.
사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
```

Village broadcast (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 ko.broadcast -->
```text
이 방송은 실제 상황이 아닙니다.
삼춘리 주민 여러분께 알려 드립니다.
2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보입니다.
새벽 2시 20분까지 차로 출발하십시오. 의성북부초등학교까지 가는 길이 컴퓨터 예측 계산으로 확인되었습니다.
차가 없는 분은 이장에게 바로 알리십시오.
대피 장소는 공식 안내를 따르십시오.
다시 알려 드립니다. 실제 상황이 아닌 2025년 기록 재현입니다.
공식 대피 명령이 우선합니다.
```

Family call script (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 ko.call -->
```text
[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
안녕하세요. [소속·이름]입니다. 삼춘리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
지금 드리는 내용은 실제 상황이 아니라, 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보입니다.
컴퓨터 예측 계산(모델)으로는 마을 근처 도로에서 새벽 2시 20분까지 차로 출발하면 의성북부초등학교까지 가는 경로가 확인되었습니다.
그보다 늦게 출발하는 길은 확인되지 않았습니다. 이 시각은 불길 때문에 정한 것이 아닙니다.
어르신께서 차가 없거나 혼자 움직이기 어려우시면 이장이나 읍·면사무소에 바로 알려 주십시오.
공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.
```

Card (Korean; the printed card shows the same strings):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 ko.card -->
```text
산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
삼춘리 (마을)
모델로 확인된 차량 경로 있음
출발 마감 02:20 (새벽 2시 20분 · 한국 시각)
이 시각까지 기다리지 말고 미리 차로 출발하십시오.
모델이 점검한 도착지: 의성북부초등학교 · 02:20 출발 시 02:51쯤 도착(차로 약 31분, 교통 정체 미반영)
다음 점검 시각인 02:30에 출발하면 불길이 없더라도 점검한 도착지 중 1시간 자료 범위 안에 도착해 머물 수 있는 곳이 없습니다. 02:20보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다. 이 시각은 불길 때문에 정한 것이 아닙니다.
실제 대피 장소와 길은 공식 안내를 따르십시오. 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
공식 대피 명령이 우선합니다.
자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
모델 기반 계획 정보 · 실시간 아님
시각은 마을에서 195 m 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외 · 차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 08:10 KST
```

SMS (English):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 en.sms -->
```text
REPLAY of 2025-03-26 02:00 KST data, not live
Model-based plan: leave by car no later than 02:20 KST.
Official orders come first.
```

Village broadcast (English):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160437 en.broadcast -->
```text
This is not a real emergency.
Attention, residents of Samchun-ri.
This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
Leave by car no later than 2:20 a.m. The computer forecast checked a route to Uiseong Bukbu Elementary School for departures up to then.
If you have no car, tell the village head now.
Follow official guidance on where to go.
Later departures have no checked route; this time was not set by fire.
Again: this is not a real emergency; it is a replay of recorded 2025 data.
Official evacuation orders come first.
```


### 구계리 (Gugye-ri) — 의성·안동, recorded input 2025-03-26 02:00 KST

`uiseong_andong_2025/20250325T170000Z.json`, origin `osm:node/415160471`: no route in the model; the
file shows the two roads leading out of the area reachable without meeting flames blocked at the data
time (`all_exits_blocked`).

SMS (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160471 ko.sms -->
```text
[25.3.26 02:00 기록재현]
모델상 경로 없음·실시간 아님
공식명령 우선, 위급 시 119
```

Long text (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160471 ko.lms -->
```text
[2025년 기록 재현 · 실제 상황 아님]
산불 대피 계획 정보 · 구계리(마을)
자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 사전 계산 2026-10-18 08:10 KST

■ 모델상 확인된 차량 경로가 없습니다.
■ 이장: 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오.
■ 주민: 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
■ 이유: 이 마을에서 불길을 만나지 않고 차로 갈 수 있는 구역을 벗어나는 길 2곳(이 마을에서 약 700 m·1.5 km 떨어진 도로)이 모두 자료 시각에 이미 불길에 막혀 있습니다(길마다 산불 예측 시나리오 4가지 모두에서).

공식 대피 명령이 우선합니다.
모델 기반 계획 정보 · 실시간 아님
2025년 실제 산불 기록을 재현한 시나리오입니다.
사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
```

Village broadcast (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160471 ko.broadcast -->
```text
이 방송은 실제 상황이 아닙니다.
구계리 주민 여러분께 알려 드립니다.
2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보입니다.
컴퓨터 예측 계산으로는 이곳에서 차로 나가는 확인된 길이 없습니다. 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
산불 예측에서는 이곳에서 불길을 피해 갈 수 있는 구역의 출구 2곳이 모두 이미 불길에 막혀 있습니다.
공식 대피 명령이 우선합니다.
```

Family call script (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160471 ko.call -->
```text
[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
[통화 전 확인] 이장이 119와 읍·면사무소에 먼저 연락했는지 확인하십시오.
안녕하세요. [소속·이름]입니다. 구계리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
지금 드리는 내용은 실제 상황이 아니라, 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보입니다.
컴퓨터 예측 계산(모델)으로는 마을에서 차로 나가는 확인된 경로가 없었습니다. 이런 결과라면 이장은 바로 119와 읍·면사무소에 연락해 공식 지시를 따라야 합니다.
산불 예측에서는 이곳에서 불길을 피해 갈 수 있는 구역의 출구 2곳이 모두 이미 불길에 막혀 있습니다.
이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.
```


### 광연리 (Gwang-yeon-ri) — 의성·안동, recorded input 2025-03-26 02:00 KST

`uiseong_andong_2025/20250325T170000Z.json`, origin `osm:node/415160467`: unresolved — no departure
time, never green, no reason.

SMS (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160467 ko.sms -->
```text
[25.3.26 02:00 기록재현]
모델 경로 미확인·실시간 아님
공식명령 우선·공식안내 따르십시오
```

Village broadcast (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160467 ko.broadcast -->
```text
이 방송은 실제 상황이 아닙니다.
광연리 주민 여러분께 알려 드립니다.
2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보입니다.
컴퓨터 예측 계산으로는 이곳의 차량 대피 길을 확인하지 못했습니다. 길이 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따르십시오.
다시 알려 드립니다. 실제 상황이 아닌 2025년 기록 재현입니다.
공식 대피 명령이 우선합니다.
```

Card (Korean):

<!-- example uiseong_andong_2025/20250325T170000Z.json osm:node/415160467 ko.card -->
```text
산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
광연리 (마을)
미확인: 모델로 확인하지 못함
미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.
공식 대피 안내를 따르십시오.
공식 대피 명령이 우선합니다.
자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
모델 기반 계획 정보 · 실시간 아님
차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 08:10 KST
```


### 석탑리 (Seoktap-ri) — 의성·안동, recorded input 2025-03-24 18:00 KST

`uiseong_andong_2025/20250324T090000Z.json`, origin `osm:node/415160428`: leave by 18:10 with the
fire reason from the file (`flame_on_route`: the route checked at 18:10, shifted to 18:20, meets the
flames on a road about 1.3 km from 하화리 in 1 of 4 fire scenarios from the forecast).

Long text (Korean):

<!-- example uiseong_andong_2025/20250324T090000Z.json osm:node/415160428 ko.lms -->
```text
[2025년 기록 재현 · 실제 상황 아님]
산불 대피 계획 정보 · 석탑리(마을)
자료 기준: 2025년 3월 24일 18:00 (한국 시각) · 사전 계산 2026-10-18 07:54 KST

■ 18:10(오후 6시 10분)까지 차로 출발하십시오. 이 시각까지 기다리지 마십시오.
■ 모델이 점검한 도착지: 의성북부초등학교. 18:10에 출발하면 18:26쯤 도착합니다(차로 약 16분, 교통 정체 미반영).
■ 이유: 산불 예측 시나리오 4가지 중 1가지에서는 하화리에서 약 1.3 km 떨어진 도로에 18:24쯤 불길이 닿습니다. 다음 점검 시각인 18:20에 출발하면 그곳에서 불길과 만날 수 있습니다.
■ 실제 대피 장소와 길은 공식 안내를 따르십시오.
■ 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
■ 시각은 마을에서 1.3 km 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.

공식 대피 명령이 우선합니다.
모델 기반 계획 정보 · 실시간 아님
2025년 실제 산불 기록을 재현한 시나리오입니다.
사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
```

Village broadcast (Korean; no room for the reason line):

<!-- example uiseong_andong_2025/20250324T090000Z.json osm:node/415160428 ko.broadcast -->
```text
이 방송은 실제 상황이 아닙니다.
석탑리 주민 여러분께 알려 드립니다.
2025년 3월 24일 오후 6시 기록을 재현한 모델 기반 계획 정보입니다.
오후 6시 10분까지 차로 출발하십시오. 의성북부초등학교까지 가는 길이 컴퓨터 예측 계산으로 확인되었습니다.
시각은 마을에서 1.3 km 떨어진 도로 기준입니다.
차가 없는 분은 이장에게 바로 알리십시오.
대피 장소는 공식 안내를 따르십시오.
공식 대피 명령이 우선합니다.
```

Long text (English):

<!-- example uiseong_andong_2025/20250324T090000Z.json osm:node/415160428 en.lms -->
```text
[REPLAY of recorded 2025 data - not a real emergency]
Wildfire evacuation plan information - Seoktap-ri (Village)
Data time: 2025-03-24 18:00 KST · Precomputed 2026-10-18 07:54 KST

- Leave by car no later than 18:10 KST (6:10 p.m.). Do not wait until that time.
- Destination the model checked: Uiseong Bukbu Elementary School. Leaving at 18:10, arrival around 18:26 KST (about 16 min by car; traffic not included).
- Why: in 1 of 4 fire scenarios from the forecast, flames reach a road about 1.3 km from Hahwa-ri around 18:24 KST. If you leave at the next checked time, 18:20, you may meet the fire there.
- Follow official guidance on where to go and which roads to use.
- If you have no car or cannot move on your own, tell the village head or the eup/myeon office now.
- Times refer to the nearest road point (entry point), 1.3 km from the village. Time to get ready and board is not included.

Official evacuation orders come first.
Model-based planning information · not live
Replay of recorded 2025 wildfire scenarios.
Planning aid only - not for live evacuation operations.
```


### 용봉리 (Yongbong-ri) — 의성·안동, recorded input 2025-03-23 10:00 KST

`uiseong_andong_2025/20250323T010000Z.json`, origin `osm:node/415160449`: a deadline set by the
1-hour range (`window`, `time_window`); the arrival 10:52:55 is shown as "10:53쯤 … 약 43분".
The English card keeps the Korean destination name (OSM has no English one); spoken English never
reads it.

Card (Korean):

<!-- example uiseong_andong_2025/20250323T010000Z.json osm:node/415160449 ko.card -->
```text
산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
용봉리 (마을)
모델로 확인된 차량 경로 있음
출발 마감 10:10 (오전 10시 10분 · 한국 시각)
이 시각까지 기다리지 말고 미리 차로 출발하십시오.
모델이 점검한 도착지: 일직초등학교 · 10:10 출발 시 10:53쯤 도착(차로 약 43분, 교통 정체 미반영)
다음 점검 시각인 10:20에 출발하면 불길이 없더라도 점검한 도착지 중 1시간 자료 범위 안에 도착해 머물 수 있는 곳이 없습니다. 10:10보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다. 이 시각은 불길 때문에 정한 것이 아닙니다.
실제 대피 장소와 길은 공식 안내를 따르십시오. 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
공식 대피 명령이 우선합니다.
자료 기준: 2025년 3월 23일 10:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
모델 기반 계획 정보 · 실시간 아님
시각은 마을에서 65 m 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외 · 차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
시나리오 ffb1:20250323T010000Z:da4a13e53bc0b6a2 · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 07:54 KST
```

Card (English):

<!-- example uiseong_andong_2025/20250323T010000Z.json osm:node/415160449 en.card -->
```text
Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay · Not a real emergency
Yongbong-ri (Village)
Checked vehicle route in the model
Leave by 10:10 (10:10 a.m. KST)
Do not wait until this time: leave by car early.
Model-checked destination: 일직초등학교 (School); leave 10:10, arrive around 10:53 (about 43 min by car; traffic not included)
Next checked time 10:20: even without fire, no destination checked fits the 1-hour range (arrival and stay). No checked route after 10:10; this time was not set by fire.
Follow official guidance on where to go. No car or need help? Tell the village head or eup/myeon office now.
Official evacuation orders come first.
Data time: 2025-03-23 10:00 KST · replay of 2025 data
Model-based planning information · not live
Times at the road entry point 65 m away; boarding time not included · Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
Planning aid only — not for live evacuation operations.
Scenario ffb1:20250323T010000Z:da4a13e53bc0b6a2 · Prepared 2026-11-02 14:00 KST · Precomputed 2026-10-18 07:54 KST
```
