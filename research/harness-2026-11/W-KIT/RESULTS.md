# W-KIT checkpoint 3 (measured; not fit for live use; comprehension untested)

Code: `planner/src/features/lastmile/channels/build.ts` · tests: `tests/planner/wkit.channels.test.ts` (20 tests).
Run: `cd planner && npm ci && npx vitest run ../tests/planner/wkit.channels.test.ts`; full suite `npx vitest run` →
22 files, 385 tests passed (this container, Node 22, Linux x86_64).

## Claim boundary
The outputs are well-formed and mutually consistent under the kit's rules. Nothing here shows that anyone understands
or acts on them; comprehension is untested. Inputs are replayed planner results; nothing is fit for live use.

## Decisions applied (Iris + orchestrator, 2026-11-12)
- Head script = fixed opener (not real / data / markers; live: data age) + ≤ 20 s core with the five elements
  (source first, per NIST TN 1982 §5.3) + closer "공식 대피 명령이 우선합니다" in full. Exported only as one
  inseparable `script`; both lengths reported, at 3.0 and at 2.5 syllables/s.
- "No order yet" is a STAFF / village-head output only, produced only from an explicit status
  `{status: not_issued, suppliedBy, suppliedAtIso, expiresAtIso}` valid at `nowIso`; absent/expired/unattributed →
  not produced; never inferred. It carries the planning-only frame, the data age and who supplied the status.
- Transport-need list (key 2): synthetic households only; held in practice by 읍·면사무소 staff and the 이장.
  `topSection` (model no-route, then unresolved incl. origins without a plan, then partial — the planner's order) is
  separate from `byDeadline` (leave-by ascending).
- Issue-order-by: Richard's F-3.1 record `{leaveByS, issueByS:{low,median,high}}`; times only for a planner
  `leave_by`; negative → "already past"; null leave-by shown only when the planner also says no-route (never a
  time); absent → "not computed"; latencies labelled as assumptions.
- Time wording centralised (`timeStyle`: `clock` default, `clock_and_minutes`) so a comprehension test can vary it.
- Existing kit outputs unchanged: sha256 snapshot over all 531 real origins (test).

## Measured
- 531 real origins: 0 violations; every core ≤ 20 s with all five elements; full ≤ 35 s, at 3.0 syll/s.
- At 2.5 syll/s the same scripts fit for only 197/531 cores (≤ 20 s) and 182/531 full scripts (≤ 35 s); the
  same texts take up to 24 s core / 39 s full. Withholding at 2.5 would leave most villages without a script, so the
  checks stay at the kit's 3.0 rate and the 2.5 figures are reported. Decision on the budget returned to Iris.
- 600 synthetic cases: only violations are 19 Korean full scripts > 35 s (long names / markers; one more since the
  midnight day marker) — flagged for withholding.

## Verifier notes folded in (Mira, PASS WITH NOTES on 6ac1bc62)
- N1: issue-order-by records are range-checked (integer; 0 ≤ leaveBy ≤ H; every issue-by ≤ leaveBy); otherwise
  "input out of range — not computed".
- N2: any time on another KST date than the data date is marked ("다음날 …" / "(next day)", or the date).
- N3: the destination-swap fault test now uses a named second destination and always runs.
- N4: the Python euc_kr oracle fails the test if python3 is missing (no silent skip).
- N6 (Mira, e28c4aff): the issue-by bound is the planner's leave-by (what residents are told) as well as the field's;
  a field EARLIER than the planner's leave-by is "disagrees with the planner" (the field is exact, the planner a sweep
  value, so the field may be later, never earlier).
- N7: latency settings must satisfy issue_low ≥ issue_median ≥ issue_high (shorter latency → later issue-by).
- N5: "withheld" means the violation list is non-empty; no consumer enforces it yet (not wired into UI/CSV). The
  enforcement claim applies only once wired, mirroring the kit's `outputOk`.

## Source notes (Sofia, 2026-11-12)
- 행정안전부예규 제361호 「재난문자방송 기준 및 운영규정」: limits are 90 / 157 CHARACTERS (annex labels), no byte
  rule; agency name mandatory (제10조②). The kit's 90-byte EUC-KR limit is stricter than 90 characters and is kept.
  Orders stay at 90 characters; 157 applies to 안전안내문자 only.
- No official guidance found on 마을방송 length; the 20 s target is an assumption. No real evacuation ARS script
  found; the key-press design is ours. "Do not reverse destinations" has no official basis found; it is our rule.

## Message-class character limits (orchestrator relay of Sofia's reading of 행안부예규 361)
`CBS_CHAR_LIMIT` (characters: 위급·긴급 90, 안전안내 157) and `cbsClassFor` (leave_by → 안전안내 advance advice;
no_route/unresolved → 긴급). The kit's older 90-BYTE EUC-KR rule is stricter (≤ 90 bytes ⇒ ≤ 90 characters) and is
kept; a test asserts every kit SMS and family text fits 90 characters and its own class. None of these is a 재난문자;
if sent as one, the agency name is mandatory and goes last (제10조②).

## W6 — draft decree four-field report (draft requirement, as of the notice date 2026-11-04)
Source (Sofia, via Thomas): 재난 및 안전관리 기본법 시행령 일부개정령안 입법예고, 행정안전부공고 제2026-1391호, 2026-11-04,
https://opinion.lawmaking.go.kr/gcom/ogLmPp/89332, 안 제49조②: 1. 대피 대상 지역 및 대피 대상자; 2. 대피의 사유 및 대피가 필요한
시기; 3. 대피장소의 명칭ㆍ위치; 4. 안내를 실시하는 기관의 명칭 및 문의 연락처. This is a DRAFT; the check describes the draft as of
that notice and nothing more.

The first version (66e3e62, Thomas) FAILED verification: with any supplied issuer, every one of the 531 real channel
sets was withheld. This version addresses the verifier's four points:
1. **Supplied proper nouns are data.** The exact contact lines built from the supplied issuer (`issuerLines`) are masked
   before the forbidden-word, departure, clock-time and destination scans, like place names. The agency name alone is
   not masked, so the same word elsewhere in generated text is still caught, even when the agency is called exactly
   "안전" / "Safe" (test). An issuer adds no violation to any of the 531 real or 600 synthetic sets (test).
2. **Contact line length, decided by measurement.** The Korean village-head script (opener + core + closer) already runs
   28.7–32.7 s (p50 32.0) of its 35 s budget over the 531 real places, so a contact line (5–11 s) cannot fit inside it.
   The head therefore carries the line after the closer under its own budget, `HEAD_CONTACT_MAX_S` = 10 s. The 35 s budget
   is unchanged. The number is read digit by digit, one syllable or word per digit. Measured Korean line length:
   4.7 s (2-syllable agency, 10 digits) up to 11.0 s (20 syllables, 11 digits). With an 11-digit number the line fits
   agencies of up to 16 syllables. Over budget, the head leaves out the FIELD and stays usable. The voice call and the
   three-line family script have no length limit and always carry the line. The family text carries it only if it still
   fits 90 bytes EUC-KR / 160 GSM-7. Measured with the synthetic issuer: Korean 0 of 531, English 509 of 531.
3. **English never carries Hangul.** English outputs use only a supplied English or romanised agency name (GSM-7
   printable ASCII, ≤ 60 characters). Without one, the English field is withheld (`no_english_name`) and never filled
   from the Korean name. The GSM-7 check on the English family text is unchanged and passes.
4. **Metrics (revised after Iris):** two shares of resident outputs that are four-field complete AND not withheld,
   over the 531 real origins: overall (n = 531 per output), and among outputs where all four fields apply (the 501
   leave-by places, n = 501). The measuring code is the same on both commits. Synthetic issuer 합성군 재난안전과 /
   Synthetic County Disaster Safety Division / 000-0000-0000, marked for drill/replay use (every booth cache is a replay).

   | output | no issuer | 66e3e62 (overall · applicable) | this version (overall · applicable) |
   |---|---|---|---|
   | ko head | 0 · 0 | 0 · 0 (531 withheld) | **299/531 · 299/501** |
   | ko voice | 0 · 0 | 0 · 0 (531 withheld) | **299/531 · 299/501** |
   | ko family text | 0 · 0 | 0 · 0 | 0 · 0 |
   | ko family script | 0 · 0 | 0 · 0 (531 withheld) | **440/531 · 440/501** |
   | en head / voice / family script | 0 · 0 | 64* · 64* | 64/531 · 64/501 |
   | en family text | 0 · 0 | 0 · 0 (531 withheld: Hangul, not GSM-7) | 0 · 0 |

   \* At 66e3e62 these counted the Hangul agency name inside English text as the field, which is the defect fixed here.
   Now they count a supplied English name. Withheld resident outputs: 2,124 at 66e3e62, 0 now, with or without an issuer.

   Every missing item now carries one reason (with the issuer, 8 outputs × 531):

   | | not applicable | not supplied | does not fit |
   |---|---|---|---|
   | ko | timing 120 | area 24, shelter 364 | shelter 722, agency+contact 531 |
   | en | timing 120 | area 72, shelter 1,856 | shelter 67, agency+contact 22 |
   | total | 240 | 2,316 | 1,342 |

   - "Not applicable" is the 30 no-route/unresolved places × 4 outputs, which have no checked time.
   - "Does not fit" covers three cases: the head drops its optional shelter block to stay within 20 s; the 90-byte
     Korean family text has no room for a shelter or a contact (it never carries a destination, by design); and the
     English family text runs over 160 GSM-7 characters for 22 places.
   - English shelter and area are mostly "not supplied", because many names have no English form and none is ever made
     up.

   Why the family text is 0 in every column, and that this is intended: it is a 90-byte / 160-character relay. Per
   Sofia's reading of the draft (DESIGN.md), the four items are owed by the guidance as a whole, and the voice call and
   family script carry them.
5. **Report only (Iris agreed).** `draftDecreeCheck` adds `set.decree[lang][output] = { present, missing, reasons,
   contact }` and a staff text, `staff.decree` (Korean and English, 5 lines). The staff text says the check is against
   a draft requirement as of the notice date and that officials decide whether an incomplete notice is sent. The check
   adds no violation, so resident outputs are identical with and without it (test). The staff text passes the kit's
   word scans.
6. **Iris's conditions:**
   - The contact line never displaces "official orders first". Over every real and synthetic set, opener + core +
     closer stay contiguous and in order, the line comes after them, and every output keeps the official-first text
     (property test).
   - In replay, mock or test-data outputs, the contact is rendered only for an issuer marked `forDrillOrReplay`;
     otherwise it is reported as not supplied (test). Live data needs no mark.
   - Committed fixtures use only all-zero placeholder numbers, or numbers the validator refuses (test reads the test
     source).

Agency and contact are supplied inputs, validated by `validIssuer`: one line; Korean ≤ 40 characters; contact digits
and hyphens, 3–12 digits, not 110/112/119. Anything else counts as not supplied, and nothing is invented or defaulted
(test). Without an issuer, every output is as before (the existing W-KIT tests pass unchanged). Comprehension is untested.

## W6 follow-up — owner decision on shelter names in English, agency-name guard (UNVERIFIED)
- **Owner decision (via the orchestrator):** where a shelter has no English name, English messages show its Korean
  (Hangul) name, with everything else in English. Never romanised. Applies to the shelter-name field only. Agency names,
  place names and all other English text keep the no-Hangul rule. A new check withholds any English resident output
  with Hangul anywhere other than the plan's own shelter name (test with a planted name).
  - Village-head script and family call script (read by a person): the Korean name is shown. Shown in 373 English
    family scripts over the 531 real places.
  - English automated voice call: the Korean name is NOT read, because a TTS voice cannot be relied on to pronounce
    Hangul. Its behaviour is unchanged, and the shelter field is reported missing there. How to handle it is open with
    Iris: (a) keep the name with a staff note, (b) leave it out, or (c) leave it to the TTS engine.
  - Family text (SMS): unchanged. It never names a destination, so no SMS gains Hangul. Segment counting is now done in
    the encoding the text needs (`smsSegments`): GSM-7 160/153, or UCS-2 70/67 as soon as one Hangul character
    appears. Measured: all 531 English family texts are GSM-7 in 1 segment, so **0 messages change segment count**.
  - Metric (complete AND not withheld; overall · applicable), English, synthetic issuer:

    | output | before | after |
    |---|---|---|
    | head | 64/531 · 64/501 | **431/531 · 431/501** |
    | family script | 64 · 64 | **431 · 431** |
    | voice | 64 · 64 | 64 · 64 (pending Iris) |
    | family text | 0 · 0 | 0 · 0 |

    Korean is unchanged (299 / 299 / 0 / 440). Withheld: 0. Missing-field reasons with the issuer: not applicable 240,
    not supplied 824 (was 2,316), does not fit 2,088 (was 1,342). Shelter names that were "not supplied" in English now
    exist and are subject to the length budgets.
- **Agency-name guard (Mira N2).** Whole contact lines are masked before the kit's scans, so the name itself is now
  checked at input (`agencyLike`). Refused: a clock time, a departure instruction, a sentence ending, or a kit-forbidden
  word outside a standard agency compound (재난안전, 안전총괄, 119구조, 구조대, …; en "safety", "rescue"). The name must end
  in an agency suffix (과/실/청/본부/센터/단/군/시/구/읍/면/동/…; Division/Office/County/Unit/…). Mira's probe "지금
  출발하십시오 18:30 안전합니다" is refused (test).
- **Channel, limit and unit of each W-KIT message (Iris), before any count:**

  | output | channel | limit | unit | source |
  |---|---|---|---|---|
  | head | village broadcast read aloud by the 이장 | core ≤ 20 s, opener+core+closer ≤ 35 s, contact line ≤ 10 s | spoken seconds at the kit's assumed rate | W-KIT DESIGN; the 10 s budget is pending Iris (Mira N1) |
  | voice | automated voice call (ARS) | none in the kit | — | W-KIT DESIGN |
  | family text | personal SMS sent by a family member: not a 재난문자, not cell broadcast | ko ≤ 90 bytes EUC-KR; en ≤ 160 GSM-7 (1 segment) | bytes / septets | kit rule (LASTMILE §4) |
  | family script | phone call by a person | none | — | W-KIT DESIGN |

  The 90 / 157-character classes (행안부예규 361) apply only to an official 재난문자 by cell broadcast. W5 already
  asserts that every kit SMS also fits 90 characters and its own class. None of these outputs is a 재난문자.
- Suite 23 files / 411 tests; build:static OK.

## W6 — confirmed answers (Iris; orchestrator, interim for voice) (UNVERIFIED)
- **Contact line: 35 s + its own 10 s (Iris signed off).** The line is the last thing in the head, after the closer,
  and the core stays within 20 s (test over every real and synthetic set). Every staff report gives the total for its
  message, e.g. "이장 방송 길이: 기본 32.0초(한도 35초) + 문의 7.7초(한도 10초) = 39.7초". Measured maximum over the
  531 real Korean heads: **39.7 s**. Neither budget has been tested with people.
- **Shelter name in English voice (INTERIM, reported to the owner; may change).**
  - Human-read English head script: keeps the Hangul shelter name. The English staff output gets a reader note
    ("Reader: say the shelter name in Korean: …"). 373 heads on the real set.
  - English automated voice call: does not read the name. It says "The shelter has no English name; it is named in the
    Korean message." and the shelter field is reported as **not supplied**.
  - **GAP, recorded:** an English-only listener who gets only the automated call has no destination. Affected: **373
    of the 531 real places**, every place whose shelter has no English name. The gap is stated in both staff reports.
  - TTS reading of Hangul is not used. It would need a language-tagged Korean voice segment and a test that a Korean
    listener can identify the shelter from the audio. No engine is in scope.
- **Issuer form guard (Iris's specification).** The main rule: the name ends in an agency suffix, is ≤ 25 characters
  (ko) / 60 (en) and ≤ 8 words, and contains no sentence punctuation. Secondary rejections:
  - clock-time patterns (not digits, so 119안전센터 passes);
  - departure instructions;
  - a sentence ending at the end of any word (…니다/…시오/…세요/…하라/…바랍니다);
  - kit-forbidden words outside standard agency compounds (재난안전, 행정안전, 안전센터, 119구조, 구조대, …).

  Acceptance:
  - 17 of 17 real issuer strings pass: the 2025 senders 의성군/청송군/안동시/영양군 and standard agencies (산림청,
    행정안전부, 경상북도, 소방청, …). **This list was used to tune the guard.** Four failed at first (행정안전부,
    경상북도, 의성소방서, 119안전센터) until the suffixes 도/서 and the compounds 행정안전/안전센터 were added, so it is
    not an independent test.
  - All 13 Korean and 5 English adversarial names fail, including instructions that end in a valid suffix ("지금 바로
    출발하십시오 동", "18:30까지 대피 동") and Mira's string.
  - **Form only:** the guard cannot show that an agency exists. The repository holds no issuer list, so no allowlist is
    possible yet; with one, an allowlist match would be the stronger check.
- **Guidance as a whole** (Sofia: the duty attaches to the guidance, not to each channel). **440 of 531** places have
  four Korean outputs that together carry all four items: all 440 through the family script. Item 5 of 안 제49조② ("그
  밖에 … 명령권자가 인정하는 사항") is open-ended and not checkable.
- **First-message destination** (Iris, from Sofia's Andong case), measured over leave-by places with a nameable shelter:
  timed Korean outputs without the shelter: family text 440 (by design, no room), head 141 and voice 141 (the head's
  optional shelter block was dropped to keep the core within 20 s). The family script carries it in every case. This is
  a report, not a rule.
- Metric (complete AND not withheld, overall · applicable): ko 299·299 / 299·299 / 0·0 / 440·440; en 431·431 / 64·64 /
  0·0 / 431·431. Withheld 0. Reasons with the issuer: not applicable 240, not supplied 1,197, does not fit 1,715.
- Suite 23 files / 415 tests; build:static OK.

## W6 — issuer guard after Mira's FAIL at 344657e (UNVERIFIED)
Mira found that the suffix-plus-blocklist guard let instruction-, transport-, status- and time-shaped names through
whenever they ended in a valid suffix: 18/21 Korean and 11/15 English of her own names, e.g. "구조대 도착 예정 본부",
"Transport provided Agency". End to end, these produced a contact line in all 531 sets with 0 violations. Everything
else at 344657e passed. The guard is now, in her order of preference:
1. **Registry first.** When the caller supplies `agencyRegistry` (official Korean and English agency names), only
   names in it are accepted. The repository holds no registry, so the form rule below is the fallback.
2. **Structure.**
   - Korean: every word is Hangul (digits allowed) and ends in a place ending (도/시/군/구/읍/면/동/리…) or a
     department ending (과/실/청/본부/센터/단/…). No word may contain an instruction, transport, status or time word
     (대피, 출발, 출동, 도착, 배차, 운행, 해제, 완료, 필요, 지금, 즉시, 바로, 예정, 버스, 셔틀, 진화, 오늘, 밤, 시간, Korean hour
     numerals, digits + 분/시간, …). Standard compounds (주민대피지원단, 재난안전, 119구조, 구조대, …) are removed first.
   - English: every word is Capitalised or a connector, the last word is an agency noun, and no word is an instruction,
     transport, status or time word (now, go, coming, clear, need, transport, provided, bus, evacuat*, cancel*, at,
     six, …).
3. **Staff are told.** A supplied issuer that is refused adds no contact line, and both staff reports say why.

Acceptance:
- 17/17 real issuer strings pass. This is still the tuning list, not an independent test.
- All 31 Korean adversarial names fail: the original 13, Mira's 14, and 4 run-together variants such as "셔틀운행센터".
- All 15 English adversarial names fail: Mira's 9 plus Title-Case variants.
- **Form only:** this cannot show that an agency exists. A registry is the stronger check.

Also fixed (Mira's minor note): `smsSegments` packs segments, so an escape pair or a surrogate pair never straddles a
boundary. 152 'a' + '{' + 152 'a' is 3 segments, not 2, and similarly for UCS-2 with an emoji.
Suite 23 files / 418 tests; build:static OK.

## W6 — issuer ALLOWLIST (orchestrator decision after Mira's FAIL at 344657e) (UNVERIFIED)
The form guard is dropped as the safety mechanism. **A contact line renders only when the supplied agency name exactly
matches an entry of a committed registry of official issuing bodies**
(`planner/src/features/lastmile/channels/agencyRegistry.ts`, each entry {ko, en | null, source}).
- **Not in the registry:** no contact line in any output. Contact status `not_in_registry`, reason "not supplied".
  Both staff reports say: "문의처 없음: 입력한 기관명이 등록된 공식 기관 목록에 없습니다. 목록은 아직 일부만 담고 있으며,
  기관을 추가하려면 공식 명칭과 출처가 필요합니다." / "No contact line: the issuer is not in the registry of official
  issuing bodies. The registry is incomplete; adding a body needs its exact official name and a source."
- **English:** the English name is used only when it equals the entry's own published English name. Every entry has
  en = null today, so there is no English contact field until official English names are sourced. No romanisation.
- **The registry is INCOMPLETE.** It holds 6 bodies whose exact names have a source: 의성군, 청송군, 안동시, 영양군 (2025
  긴급재난문자 sender tags), 산림청 (산림재난방지법 제33조) and 행정안전부 (공고 제2026-1391호), all via Sofia. The other 11
  names of the earlier "real" list (department names such as 의성군 안전재난과, 의성소방서, 119안전센터, …) were NOT added:
  I had no source for their exact form. Sofia has been asked for official department names, English names and sources.
  The file says how to extend it, and it never holds phone numbers.
- **The form check (`agencyLike`) is a secondary lint only.** It never admits a name. A registry name that fails it
  renders but gets a staff warning. A test asserts every committed entry passes it.
- **Tests:**
  - the exact-match rule (trimmed; no near-matches);
  - every committed entry has a source, passes the lint, and holds no digits and no synthetic names;
  - the default registry is used when none is passed (의성군 renders; a synthetic name does not);
  - **property: no free-text issuer string reaches any output**. Mira's names, the adversarial lists and 2,000 seeded
    fuzz strings built from agency parts, instruction words and real names; over 1,500 of them are non-registry,
    checked on a leave-by and a no-time place. None renders a contact line or the number.
  - The W6 tests that need a contact line use an explicit SYNTHETIC test registry. The committed one holds only real,
    sourced bodies.
- Suite 23 files / 419 tests; build:static OK.

## Pending
English native review; UI/CSV wiring; F-3.1 values once Richard's run is verified; the unknown-support rule (a time
appears only for a result checked on the pessimistic instance) is not yet in planner data.
