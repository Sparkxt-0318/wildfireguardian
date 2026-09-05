# CRITIC_LATEST — critic #18, 2026-09-05

Window `6236c81..6afd252` on `auto/dev` (7 commits; 1,043 authored insertions,
images and the generated board excluded). Written by the `wfg-autoloop-critic`
routine.

## fix-before-next-row

**NONE. This is deliberate, and it is this lap's main act.**

Of the last **eleven** dev claims on this branch, **eight** were a critic's `fix-before-next-row`
item (WFG-063, WFG-069, WFG-070, WFG-067+WFG-075, WFG-087, WFG-095, WFG-100, WFG-103). The last
three ran on three consecutive dev slots — 0325Z, 0625Z, 0920Z — all three were scoped 「minutes」,
and all three were on the same document, `docs/auto/DEMO_SCRIPT_5MIN.md`. In the same six days
`docs/auto/finals/BOOTH_SETUP.md` has **never once been claimed**, and its absence holds three
readiness lines (R3's booth half, R7 and R9).

Every one of those eight items was real. Most were mine or my predecessors' best work. But the
queue has run ahead of the product for six days, and the lever that keeps it ahead is the one I
hold. So I am not pulling it. **The next dev lap owes the critic nothing and the first row it meets
is WFG-037.** I moved that row above WFG-104 to make table order and this page agree (CHARTER §3b:
both are P0, so no rule was bent either way).

This resolves critic #17's falsifiable test — 「if `BOOTH_SETUP.md` does not exist by then, WFG-084's
cap becomes the rule」 — against the loop. It does not exist. **The cap is now the rule for this
routine**, and this file and the report are written under it.

## Findings, ranked

**F1 · WFG-106 · judge-facing · P0 · the number that answers the strongest objection to the headline
is already registered, already gated, and reaches no judge.**
Critic #17's root objection was that 24.73 % is measured against a fire-blind walker. The repository
has already computed the version that is *not* diluted by the walkers who were never in danger, and
it is a registry key: `mr_uiseong_fa_rescue_rate` = **0.883**, derivation string 「naive_into_FA_safe /
(naive_into_FA_safe + no_safe_route + both_enter) — of the origins whose FIRE-BLIND route is unsafe,
the share the future-aware router still gets to a refuge」. `docs/multi_region.md:430-434` prints the
whole row for all three fires:

| fire | fire-blind route unsafe | future-aware rescues |
|---|---:|---:|
| 영덕 2025 | 44 / 458 = 9.61 % | **95.5 %** |
| 의성·안동 2025 | 103 / 368 = 27.99 % | **88.3 %** |
| 울진·삼척 2022 | 13 / 393 = 3.31 % | **23.1 %** |

Drilled against the files: `88.3`, `27.99` and `103 / 368` appear **zero times** in
`docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`, `paper/manuscript.md` and
`docs/finals_screen_v2.md`. So the student stands at the booth with 91 of 368 — a denominator holding
265 origins that were never at risk — and not with the conditional rate; and 울진·삼척's **23.1 %**,
the number that runs against the project, is spoken nowhere. This costs no compute and adds no claim:
it publishes three numbers the tree already re-derives. ⚠ Fix the key's own caveat while there — it
reads 「SMALL denominator (13–20 origins)」, true of 울진's 13 and false of this key's own 103.

**F2 · WFG-104 (updated, not duplicated) · judge-facing · the fix landed on two surfaces and left them
saying different things.** WFG-103 corrected the baseline sentence on the script *and* on the judged
screen, which is more than the finding asked for. But only one of them stayed inside what is measured:

- screen, `web/finals.html` — KO 「화재를 전혀 보지 않는 지도가 그리는 경로입니다」, EN 「This is the
  route a fire-blind map draws」. Description only.
- script, `docs/auto/DEMO_SCRIPT_5MIN.md:108-109` — adds 「**이 도구가 없을 때의 기준선입니다**」.

That clause is a counterfactual about what a resident without this tool actually walks. The repository
*labels* it (`docs/real_roads_real_hazard.md:50` calls `naive` 「the status quo」) and has never measured
it; a real resident sees the smoke. A judge reads the screen and hears the script at the same moment.
Folded into WFG-104, which is where a claim about the unaided resident belongs. Not a
`fix-before-next-row` item: it ships qualified by a ⚠ block directly beneath it that tells the student
what to say instead, and WFG-104 is two rows down.

**F3 · direction, acted on rather than filed · readiness has not moved for THREE consecutive critic
laps.** 4 of 11 (R2, R4, R5, R6) at #16, #17 and #18. That fires the 「zero for two consecutive critic
laps」 rule. `KCF_READINESS.md` carries the evidence line by line, checked on disk at this head, not
read from the laps that claimed it. The action is the empty `fix-before-next-row` block above.

**F4 · a correction this file owes the loop.** Critics #16 and #17 wrote 「nothing has touched `web/`」.
That was true of their windows and is **not** true of this one: `web/finals.html` gained two lines at
`92366cb`. R1 is unmoved for a different reason — its condition is a committed mapping table from every
on-screen number to a `docs/NUMBERS.json` key, and no such table exists. Left as a correction rather
than an edit of their text (CHARTER §3.7).

**F5 · checked and NOT a finding, recorded so no later lap re-derives it.** Three things I attacked and
that held: (a) `docs/demo_script_pace.md`'s variant table puts the re-budgeted allocation in one column
and, in the next, a spread belonging to the superseded design budget — the value registered as
`demo_pace_039a0de_rate_spread`, not either of the re-budget keys. It reads as a contradiction of the
shipped allocation for exactly as long as it takes to reach the line directly beneath the table, which
the dev lap wrote: 「The spread column is the *old* 25/45/55/75/55/45 budget under each convention」.
Checked and cleared; the numbers themselves are not reprinted here, because three spreads of one
quantity side by side is what the collision gate exists to stop and it stopped this paragraph twice. (b) The
LOFO ceiling probabilities (0.0241 / 0.296 / 0.369) are **below** the router's `p_cut = 0.5`, which looks
fatal until Q1 of the bank explains the two-threshold structure: 0.3 is the per-step advance threshold
shaping the field's extent, the router cuts the *cumulative survival* field. The bank is right. (c) The
「44 origins」 in `paper/GAPS.md` G7 is 영덕's 42 + 2, not a contradiction of 의성·안동's 103.

## Verification of the loop's claims

- `gates.py --mode full` **ALL GREEN at `6afd252`**: `1484 passed, 62 skipped` in 214 s, **COLD** (the
  six SRTM-gated tests skip, WFG-039), against critic #17's cold `1484 / 62` at `26e200d`: **unchanged
  like for like**, eleventh comparable window. `verify`, `snapshot-verify`, `env-check` PASS;
  `baseline-verify` WARN, expected off-laptop, `hard: false`, eighteenth window, still not a finding.
- **GitHub's own runs (CHARTER §4b).** `auto-gates` on `auto/dev`: run **124 (`6afd252`, this head)
  `success`**; 123, 122, 121, 120, 119, 118, 117 `success`; 116 and 115 `cancelled` by the next push.
  **No red run stands behind a green report.** Last `failure` is run 110 (03:20Z), already NH-026/WFG-102.
- **Every dev report of the last 24 h records `Reviewed by:`** — 1555Z, 1609Z (`self`, and it says why),
  1851Z, 2154Z, 0059Z, 0404Z, 0702Z, 0953Z. Eight of eight. `--assert-head` and `--assert-reported
  --base 6236c81` both exit 0.
- **`make finals-bundle` re-run by me, not read:** exit 0, byte-identical, 16 files.
- **Author decisions applied this lap: none.** `from:siyeong0318@gmail.com subject:"WildfireGuardian
  autoloop" newer_than:14d` returns 49 threads, every one a single outbound message from the loop, no
  reply. PR #31 carries no comment in `NH-###:` form. `decisions_seen.json` unchanged. **Six entries are
  open: NH-005, NH-014, NH-025, NH-026, NH-027, NH-028.** ⚠ I first wrote 「five」 here, omitting
  NH-005, which is the **third consecutive lap** to hand-write this count wrong beside a generated block
  that had it right (`26e200d`, `6afd252`, and now this one). Filed as WFG-107.

## Root objection (`hate`)

**The loop's most reliable behaviour is answering its own critic, and for six days that has been more
reliable than building the booth.** The window under review is a good window — a false description of
the baseline was removed from the script, the screen and the manuscript, found twice independently —
and it moved no score and no readiness line, because the rows are waiting on two files nobody has
written. The cheapest test is not another finding: it is one lap with no critic item in front of it.
That is what this lap bought, and critic #19 reads the result.

## Readiness and scores

**KCF readiness: 4 of 11 (R2, R4, R5, R6). No line moved, third consecutive lap.**
**Track B 84 → 84. Track A 78 → 78. Every row held**, with the evidence per row in
`docs/auto/SCORECARD.md`. Judge-facing census for the window: **65 of 1,043 authored insertions
(6.2 %)**, against 493 (47.3 %) in reports — the highest report share this census has recorded, in the
window whose falsifiable test was about exactly that.
