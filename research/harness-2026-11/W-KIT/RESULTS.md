# W-KIT checkpoint 3 (measured; not fit for live use; comprehension untested)

Code: `planner/src/features/lastmile/channels/build.ts` · tests: `tests/planner/wkit.channels.test.ts` (19 tests).
Run: `cd planner && npm ci && npx vitest run ../tests/planner/wkit.channels.test.ts`; full suite `npx vitest run` →
22 files, 384 tests passed (this container, Node 22, Linux x86_64).

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
- N5: "withheld" means the violation list is non-empty; no consumer enforces it yet (not wired into UI/CSV). The
  enforcement claim applies only once wired, mirroring the kit's `outputOk`.

## Source notes (Sofia, 2026-11-12)
- 행정안전부예규 제361호 「재난문자방송 기준 및 운영규정」: limits are 90 / 157 CHARACTERS (annex labels), no byte
  rule; agency name mandatory (제10조②). The kit's 90-byte EUC-KR limit is stricter than 90 characters and is kept.
  Orders stay at 90 characters; 157 applies to 안전안내문자 only.
- No official guidance found on 마을방송 length; the 20 s target is an assumption. No real evacuation ARS script
  found; the key-press design is ours. "Do not reverse destinations" has no official basis found; it is our rule.

## Pending
English native review; UI/CSV wiring; F-3.1 values once Richard's run is verified; the unknown-support rule (a time
appears only for a result checked on the pessimistic instance) is not yet in planner data.
