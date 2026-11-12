# W-KIT — channel-ready message outputs (design draft 1, for Iris)

Status: design, nothing built. Planning aid only; no output may be presented as fit for live use.

## Basis

Extends the planner's last-mile kit (`planner/docs/LASTMILE.md`, `planner/src/features/lastmile/`). Reuses, unchanged:
`MessagePlan` (`plan.ts`: `leave_by` / `partial` / `no_route` / `unresolved`, fail-closed), the EUC-KR / GSM-7 /
spoken-length counters (`encoding.ts`), the forbidden-word list and mandatory phrases (`strings.ts`), and the
per-output fail-closed rule (`checks.ts`, `messages.ts outputOk`). New code: `planner/src/features/lastmile/channels/`
(pure TypeScript, deterministic templates, no network); tests `tests/planner/wkit*.test.ts`. Korean is the source
text; English is a translation for review.

## Outputs (per origin unless stated)

1. **Village-head script (이장 20초 안내)** — ≤ 20 s spoken at the kit's 3.0 syllables/s (≈ 60 syllables). Carries
   the five warning elements, each as a tagged block so a test can assert presence:
   - *source*: "○○리 이장입니다" + "컴퓨터 예측 계산" (never "모델" in speech);
   - *hazard*: "산불";
   - *location*: the village's own name and, for `leave_by` with a non-varying destination, the destination name
     (local OSM names only; unnamed → generic word; never invented);
   - *time*: leave-by HH:MM (spoken form) for `leave_by`; data time for every kind;
   - *guidance*: "차로 [destination]으로 출발하십시오" / no-car line / "공식 지시를 따르십시오".
   The replay/"not real" sentence and "공식 대피 명령이 우선합니다" are mandatory. Block fallbacks as in `assembleSpoken`;
   if the mandatory blocks cannot fit 20 s the script is **withheld** (fail closed) and the panel says so. We report
   how many booth-cache origins fit.
2. **Automatic voice call (자동 음성 전화, ARS)** — the spoken message plus key-press prompt
   "1번: 지금 출발합니다 / 2번: 차가 없어 이동 도움이 필요합니다 / 3번: 다시 듣기". Never promises transport (the kit's
   FORBIDDEN list bans 픽업, 데리러, 태워, 차량 지원, "pickup", "we will send"…): "2" is said to be *passed to the
   이장 and 읍·면사무소*, nothing more.
   **English call (OWNER DECISION, 2026-11-12):** at a place whose shelter has no English name there is no English
   automated call at all; the call is never produced without its destination. English-only callers at those places
   (373 of the 531 real place-scenarios) get no automated call. The human-read English script keeps the Korean name
   with a reader note.
   **Transport-need list (이동 도움 요청 명단)** for staff: pure function `transportNeedList(replies, plans)` →
   rows ordered: (a) origins with no checked leave-by (`no_route`, `unresolved`, `partial`) first, flagged
   "출발 마감 없음 — 먼저 확인"; then (b) `leave_by` ascending by T; ties by planner urgency rank, then reply time.
   Unresolved is never sorted as "later". Key "1" rows are excluded; unknown keys are kept and flagged.
3. **Family relay (가족 전달)** — a ≤ 90-byte EUC-KR text a family member can forward, plus a 3-line call script:
   (1) who/what ("[이름]님, ○○리 산불 대피 안내입니다"), (2) time/where (leave by HH:MM to [destination] — or the
   kind's no-time line), (3) action (no car → tell the 이장 / follow official instructions; 119 only "위급하면").
4. **No-order-yet message (명령 전 안내)** — for a village where the official order status is supplied as
   `not_issued` (input from officials; the planner has no order data — absent status → message not produced).
   `leave_by`: "아직 공식 대피 명령은 없습니다. 컴퓨터 예측 계산으로는 HH:MM까지 출발해야 합니다. 명령이 없다고 위험이
   없는 것은 아닙니다." Other kinds: no time; `unresolved`: "확인되지 않았습니다 … 명령이 없다고 위험이 없는 것은
   아닙니다". So silence is never read as safety. ("안전" is forbidden; the phrasing avoids it.)
5. **Issue-order-by field (명령 발령 시한, for officials only)** — Richard's F-3.1 value, rendered read-only in the
   staff outputs (long text, card staff line, CSV column): "공식 명령이 HH:MM까지 나가야 마감 전 출발이 가능합니다
   (모델 계산)". Missing / unresolved / no-route → "산출되지 않음" — never a time. Never in resident outputs.
6. **Data age everywhere** — every new output states the data time; staff outputs also state the age relative to a
   supplied `nowIso` ("자료 35분 전"); for a recorded replay the age line is "2025년 기록 재현 자료" (an age in months is
   meaningless). `unresolved` is never rendered with a time, a destination, green styling or reassurance.

## Constraints and rules

- Lengths: urgent text ≤ 90 bytes EUC-KR; standard text ≤ 157 characters (pending Sofia's exact rule for the
  August 2025 reform: unit, mandatory when/where/how order). Voice and broadcast first: the head script and voice call
  are the primary outputs; texts are secondary.
- **Destinations never reversed / never contradicted**: every output of one origin names the same destination as
  `MessagePlan.destination`, or none when `destinationVaries` or the kind is not `leave_by`. Test: across all outputs
  of an origin, the set of named destinations has size ≤ 1 and equals the plan's.
- Forbidden words (existing list), mandatory phrases, replay/MOCK/test markers: enforced by reusing `checks.ts` logic
  over the new outputs; each new output fails closed on its own.
- Deterministic: same input → byte-identical output (tested).

## Tests (planned)

Unit (each template, each kind), property (the kit's 600 synthetic cases via `lastmile.generator.ts`), booth caches
(all real origins): lengths, five-element tags, forbidden words, destination consistency, unresolved never timed,
ordering of the transport-need list (incl. ties and unresolved), no-order message only when status `not_issued`,
data-age line present, determinism. Independent re-implementation of the length counters is already in the kit tests.

## Draft decree four-field report (W6)
The kit checks each resident-facing output against the four items of draft 제49조② (재난 및 안전관리 기본법 시행령
일부개정령안, 행정안전부공고 제2026-1391호, notice of 2026-11-04, comment period to 2026-12-14). **This is a draft
requirement as of the notice date, and it may change.** The check (`draftDecreeCheck`) is a REPORT, shown in every staff
output (`staff.decree`, Korean and English). It never withholds a message, and **the kit does not decide whether a
notice missing an item may be sent: that is for officials.** Each missing item carries one reason:
- not applicable: no checked departure time, so no timing;
- not supplied: no issuer, no English agency name, no drill/replay mark, or no nameable place or shelter;
- does not fit: the item exists but a length budget left it out.

On a reading of the draft text (Sofia; hers, not an official reading), the duty attaches to the evacuation guidance as
a whole, and ③ lets the issuer choose and combine channels. A short family text without the contact is therefore not
by itself a gap in the notice. Sofia flags that ③ refers to "제1항" where the list is in ②, apparently a drafting slip.

Agency and contact number are supplied inputs only (`issuer`), never invented or defaulted:
- In replay, mock or test-data outputs, the contact line is rendered only if the issuer record is explicitly marked
  `forDrillOrReplay`. A real number in a replay of a 2025 event invites real calls.
- Committed fixtures use all-zero placeholder numbers.
- English outputs use only a supplied English or romanised agency name, never Hangul.

## Open questions for Iris

1. 20 s for a head's script with mandatory replay + "official first" sentences leaves ≈ 35 syllables for content.
   Should a too-long script be withheld (my default) or should the mandatory replay sentence be allowed to move to a
   separate opener the head reads once?
2. Is ordering unresolved/no-route *before* the earliest leave-by right for a staff list, or should they be a
   separate section?
3. The no-order message depends on order status the planner does not have. Is a supplied input acceptable, or should
   it be produced for every village with a marker "명령 여부 미확인"?
