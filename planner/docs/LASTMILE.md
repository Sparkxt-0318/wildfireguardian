# Last-mile kit — 현장 전달 문구 / Field messages

The planner's result for a village or care facility is only useful if it reaches the people who
must act on it. In the March 2025 Gyeongbuk fires most of the dead were 60 or older, warnings
travelled from officials to the village head (이장) to the village loudspeaker (마을방송), older
phones missed text alerts, and residents doubted warnings while no fire was visible. The kit
therefore turns each origin's planner result into short, fixed wording that a village head or care
worker can pass on as is: a concrete time, a place and a plain reason, without claiming more
certainty than the model has.

It adds no data and computes no route. Every sentence is a deterministic template filled with the
planner's own result for the scenario on screen (recorded fire scenarios only) and, when present,
the deadline explanation file (§6).

Code: `planner/src/features/lastmile/` · tests: `tests/planner/lastmile*.ts` · one hook in
`planner/src/components/RightPanel.tsx` (origin detail, below the departure windows).

## 1. Outputs per origin (Korean source + English)

| Output | Limit (enforced) | Notes |
|---|---|---|
| SMS 단문 | Korean ≤ 90 bytes in strict EUC-KR (KS X 1001); English ≤ 160 GSM-7 characters | Short forms of the mandatory lines (§3) |
| Long text 장문 (LMS) | ≤ 2,000 bytes EUC-KR (both languages) | Full wording, verbatim mandatory lines |
| Village broadcast 마을방송 | ≤ 60 s read aloud at the assumed rate (§4) | Required blocks first; optional ones (reason > repeat > no-car note) only while the script stays ≤ 60 s |
| Phone-call script (care staff → families) | none; estimated duration shown | `[brackets]` for the caller to fill in; a "before the call" line first |
| One-page card | A5 at 14 pt or A4 at 18 pt, one page | High contrast, status as icon + text, leave-by time in large type |
| CSV | — | One row per origin of the scenario (§8) |

Every output states the data time (KST) and, for a recorded fire, that it is a replay of the
recorded 2025 data. Clock times are the input time plus the planner's offsets, in KST.

## 2. What each verdict may say

The kit never decides anything itself; `plan.ts` maps the planner's result to one of four message
kinds and fails closed to the less specific one on any inconsistency.

- **checked_route → `leave_by`** — only when every requested departure time from the first one up
  to T has a checked route, T being the contract's contiguous basis
  (`latest_contiguous_checked_depart_offset_s`). If later times are checked but one in between is
  not, the message keeps T (earlier than the planner's headline deadline) and says why. Window-closed
  times are not requests. Each output gives: leave by T (and "do not wait for the deadline"), the
  destination checked at every time up to T (or "the destination depends on the departure time"),
  the arrival time and minutes by car when known, what is true after T (not checked with this data /
  no checked route / not every later time checked), the reason when the explanation file agrees
  (§6), the data time and the mandatory lines.
- **checked_route without a contiguous basis → `partial`** — no departure time at all; follow
  official evacuation guidance. (No origin in the six booth caches is in this state; it is covered
  by synthetic unit tests.)
- **model_no_route → `no_route`** — contact 119 or the 읍·면사무소 now and follow official
  instructions. No departure time, no clock time other than the data time, no tactical advice. With
  a consistent explanation: which roads leaving the village meet flames, in how many fire scenarios
  from the forecast (never a clock time or a departure window).
- **unresolved (incl. not computed / not checkable) → `unresolved`** — the model could not check a
  route; this means neither that a route exists nor that it does not; follow official evacuation
  guidance. Never green, never a departure time, never explained.

User-drawn spread zones (an assumption) produce no field messages. MOCK and test data are marked in
every output, including the SMS.

## 3. Mandatory lines and words never used

Written outputs (card, long text) carry verbatim: `공식 대피 명령이 우선합니다.` /
`Official evacuation orders come first.` and `모델 기반 계획 정보 · 실시간 아님` /
`Model-based planning information · not live`. Spoken outputs say them as sentences. The card
also carries the planner footer (`사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.` /
`Planning aid only — not for live evacuation operations.`) and the fire-input banner text.

A Korean SMS is 90 bytes (45 Hangul) in total and the two verbatim lines alone take 61, so the
single SMS — and only the SMS — uses short forms: `공식명령 우선·실시간 아님` and
`Official orders come first. / Model-based info, not live.` (`strings.ts`). The Korean SMS also
always contains `모델` and ends with the data date and `재현` (or `MOCK` / `시험`).

Never used, in any output (`FORBIDDEN`, case-insensitive substrings; names from the data are
masked first so a village called 안전마을 does not trip it): 안전/safe, rescue or pickup words
(구조, 데리러, 태워, 픽업, "we will send", "vehicle will" …), shelter-in-place or "stay home/wait"
advice, and reassurance (보장, 안심, 괜찮, "guarantee", "don't worry", "no danger" …). Scenario
members are always "fire scenarios from the forecast" (산불 예측 시나리오). A departure instruction
(`DEPARTURE_INSTRUCTION`) appears only in `leave_by` messages.

`checks.ts` checks all of this for every output of every origin (lengths, mandatory phrases, data
time, replay note with its year, forbidden words, departure instructions, clock times). The panel
disables copy and print for a text that fails and shows why; the tests use the same function as
their oracle plus independent re-implementations (§9).

## 4. How lengths are counted

- **Korean bytes**: strict EUC-KR — ASCII 1 byte, a KS X 1001 character 2 bytes. The repertoire is
  built from the platform's WHATWG `euc-kr` decoder restricted to lead/trail bytes 0xA1–0xFE
  without the private-use rows; anything outside (e.g. `—`, rare syllables, emoji) is reported as
  unencodable and fails the check. The tests cross-check every count with Python's `euc_kr` codec.
- **English SMS**: GSM 03.38 septets; extension-table characters count 2; any other character would
  force UCS-2 and fails the check.
- **Spoken length**: Korean syllables with numbers expanded the way they are read (native-Korean
  hours and counters, Sino-Korean minutes and dates, 119 digit by digit); English words with every
  digit counted as a word.
- **Reading-rate assumption**: Korean **3.0 syllables/s** including pauses. Hwang & Lee (2012),
  「다문화가정 이주여성의 발화속도와 쉼」, *The Journal of the Acoustical Society of Korea* 31(2):63–72
  (https://www.koreascience.kr/article/JAKO201212961960491.pdf) measured 5.04 syllables/s overall,
  pauses included, for native Korean speakers reading aloud; 3.0 is about 40 % slower, so a script
  that fits at 3.0 also fits a slow, deliberate announcer. English: **2.0 words/s** (120 wpm),
  below the 150–160 wpm usually quoted for read speech. Both are assumptions for a loudspeaker to
  older listeners, not measurements of one; the panel states them next to the estimate.

## 5. Plain Korean for older listeners

Short sentences in polite 하십시오체; times spoken as 새벽/오전/낮/오후/밤 + hour ("새벽 2시 20분",
"낮 12시"); the leave-by time repeated at the end of the broadcast when the 60 s allow; only particles that do not
depend on the preceding sound (까지/에/의/에서) follow inserted names; no English abbreviations or
model jargon in spoken text ("미확인" is always explained). The English text is the project's own
translation of the Korean source, not machine translation.

## 6. Deadline explanation (P2 contract `wfg.explanation/1`)

`explanation.ts` loads `data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json` with a
same-origin relative fetch under `import.meta.env.BASE_URL` — the only network request of the kit,
to a static file of the app itself, so it works in the static (no-API) build. A missing file, an
SPA fallback page or a network error means *absent*; bad JSON, another schema or another
region/input/scenario set means *invalid*; either way the messages are built without reasons, and
the dialog says which. Nothing is fabricated when the file is absent.

A reason line is used only when the entry agrees exactly with the planner: status `explained` (or
`explained_partial` with a usable item); same verdict; for `leave_by` the entry's
`deadline_offset_s` equals the planner's deadline, the message's T is that deadline (not an earlier
contiguous basis), and `next_offset_s` / `next_verdict` match the sweep with the next departure
recorded as `model_no_route` (an unresolved next time is never explained). A usable item has a
finite flame time inside the recorded window, a valid member set, flame contact after the vehicle
passes, and a label from the data (`osm_name`, `osm_ref`, `nearest_place` or "unnamed road"),
≤ 40 characters. For `no_route`, every exit item must be usable and the text names at most three
roads. The SMS never carries a reason (no room).

## 7. Languages

`LANGUAGES` in `strings.ts`: Korean is the source, English the brief-required translation; both
are marked `nativeSpeakerReview: 'pending'`. A further language can be added as a template set but
stays disabled — out of the panel, the CSV and every output — until a native speaker has reviewed
it (tested).

## 8. Panel, printing and CSV

The origin detail shows a "현장 전달 문구 / Field messages" section. Its dialog lists every origin of
the scenario in urgency order, shows the status, the explanation state, the rule-check result and
each text in both languages with its counter (bytes, GSM-7 characters, estimated seconds) and a
copy button. It previews the card and prints it (this origin at A5 or A4, or every origin at A5, one
card per page) through a print-only root (`@page` size, everything else hidden). The CSV (UTF-8 BOM,
CRLF, Korean or English headers) has one row per origin with every text, its counters, the
deadline, destination, data time, scenario, fire input, MOCK/test flags, reason source and the
rule-check result.

Card layout (`lastmile.css`): A5 148 × 209.6 mm with 7/8 mm padding at 14 pt, A4 210 × 296.6 mm
with 14/16 mm padding at 18 pt, line-height 1.32, black on white, bundled Pretendard Variable. The
fit is tested (§9) for every origin of the six caches, plain and with a 40-character road name.

## 9. Tests

Run from `planner/` (single worker on small machines):

```
NODE_OPTIONS=--max-old-space-size=2048 npx vitest run --no-file-parallelism --maxWorkers=1 \
  ../tests/planner/lastmile.test.ts ../tests/planner/lastmile.cache.test.ts \
  ../tests/planner/lastmile.render.test.ts ../tests/planner/lastmile.print.test.ts
```

- `lastmile.test.ts` — counting rules, KST wording, the message plan per verdict (contiguous
  basis, gaps, partial, destination coverage, window-closed times), each template per verdict,
  MOCK/test marking, worst-case dates, explanation loading/fallback/consistency, rule checks, CSV,
  the language registry, and inline snapshots of synthetic messages in both languages.
- `lastmile.cache.test.ts` — property tests over every origin of the six booth caches (2 regions ×
  3 recorded input times, loaded through the app's own cache reader): limits (Korean bytes
  cross-checked with Python `euc_kr`, an independent GSM-7 class), mandatory lines, forbidden words
  and departure instructions with independent patterns; then the same with a contract-shaped
  synthetic explanation file (made-up 40-character road name) and with one whose deadlines are off
  by one step (no reason at all). Inline snapshots of three real origins: 삼춘리 (leave_by),
  구계리 (no_route), 광연리 (unresolved).
- `lastmile.render.test.ts` — the dialog and card in jsdom: counters, copy, print root, CSV,
  fail-closed disabling, verdict icons.
- `lastmile.print.test.ts` — a browser-free box-model estimate (`lastmile.printfit.ts`, measured
  advance widths of the bundled font) that every card fits; and, when Playwright with Chromium is
  installed, the real print layout of every card (no overflow, body ≥ 14 pt, estimate never below
  the real height) and PDFs with exactly one page per card.

Synthetic fixtures (`lastmile.fixture.ts`, `lastmile.cachedata.ts`) are marked SYNTHETIC and never
leave the tests.

## 10. Limitations

- The deadline explanation file is produced by another work package; until it exists the messages
  carry no reason line (tested with a contract-shaped synthetic file only).
- The wording has not been reviewed with village heads, care staff or older residents, nor by a
  native English speaker; reading rates are assumptions (§4).
- The single SMS uses short forms of the mandatory lines; the long text, card and scripts carry them
  verbatim.
- Results are model results for vehicles from the road entry point: no walking, boarding time,
  congestion, road closures or smoke; departure times between the 10-minute steps are not checked.
- Print fit is verified in Chromium only; other browsers' print engines may break lines differently.
- Carriers differ in how they count and split Korean messages; the 90/2,000-byte limits follow the
  common EUC-KR convention.
