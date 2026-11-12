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
4. **Metric:** the share of resident outputs that are four-field complete AND not withheld (531 real origins). Same
   measuring code on both commits. Synthetic issuer 합성군 재난안전과 / Synthetic County Disaster Safety Division /
   000-0000-0000:

   | output | no issuer (both) | 66e3e62 | this version |
   |---|---|---|---|
   | ko head | 0 | 0 (299 complete, 531 withheld) | **299** (0 withheld) |
   | ko voice | 0 | 0 (299 complete, 531 withheld) | **299** |
   | ko family text | 0 | 0 | 0 (contact does not fit 90 bytes) |
   | ko family script | 0 | 0 (440 complete, 531 withheld) | **440** |
   | en head | 0 | 64* | 64 |
   | en voice | 0 | 64* | 64 |
   | en family text | 0 | 0 (531 withheld: Hangul, not GSM-7) | 0 |
   | en family script | 0 | 64* | 64 |

   \* At 66e3e62 these counted the Hangul agency name inside English text as the field, which is the defect fixed here.
   Now they count a supplied English name. With a Korean-only issuer the English rows are 0 and every English output
   reports `no_english_name`. Withheld resident outputs with the issuer: 0 of 4,248, against 2,124 at 66e3e62.

   What is still missing, and why (Korean, with the issuer): shelter in 1,086 of 2,124 outputs (the head drops its
   optional destination block to stay within 20 s; varying or unnamed destinations are never named; the family text
   has no room). Reason and timing are missing in 120, which are the 30 no-route/unresolved places × 4 outputs: by design
   they carry no time. Area is missing in 24. English shelter is missing more often (1,923) because many destinations
   have no English name and none is ever made up.
5. **A report only (design change; sent to Iris).** `draftDecreeCheck` adds `set.decree[lang][output] = { present,
   missing, contact }` and never a violation, so a missing decree field never withholds a message. Under a withholding
   rule every no-route and unresolved message, and every message without a nameable shelter, would be suppressed. That
   is a policy question for officials, not a template defect (test: with or without the check, identical outputs and
   violations).

Agency and contact are supplied inputs, validated by `validIssuer`: one line; Korean ≤ 40 characters; contact digits
and hyphens, 3–12 digits, not 110/112/119. Anything else counts as not supplied, and nothing is invented or defaulted
(test). Without an issuer, every output is as before (the existing W-KIT tests pass unchanged). Comprehension is untested.

## Pending
English native review; UI/CSV wiring; F-3.1 values once Richard's run is verified; the unknown-support rule (a time
appears only for a result checked on the pessimistic instance) is not yet in planner data.
