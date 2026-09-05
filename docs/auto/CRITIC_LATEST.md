# CRITIC_LATEST — critic #16, 2026-09-05

Window `466900b..c37f27e` on `auto/dev` (7 commits; the 24 h window is 60 files, 2,971 insertions).
Written by the `wfg-autoloop-critic` routine. The next dev lap clears every
`fix-before-next-row` item here before claiming a row.

## fix-before-next-row

**One item, WFG-100: the five minutes the whole booth turns on is a budget nobody has measured, and its six segments cannot all be right.**

`docs/auto/DEMO_SCRIPT_5MIN.md` §5 says the six segment times were set from
「문장 수와 한국어 발화 속도」. Nobody has checked the arithmetic of that, and the tests cannot:
`tests/test_demo_script_5min.py` asserts the six numbers **sum to 300**, which is true and is
not the same question.

**Measured this lap**, over the spoken blockquote lines only (Hangul syllables plus numerals
read as sino-Korean; the ⚠ blocks, the mapping table and the DRAFT header are excluded because
nobody says them):

| segment | declared | spoken syllables | implied syllables/second |
|---|---:|---:|---:|
| 도입 | 25 s | 161 | 6.44 |
| 1막 · 발견 | 45 s | 235 | 5.22 |
| 2막 · 시간이 도로망을 바꿉니다 | 55 s | 279 | 5.07 |
| 3막 · 같은 출발지, 두 개의 답 | 75 s | 318 | 4.24 |
| 4막 · 예측을 판단으로 | 55 s | 319 | 5.80 |
| 마무리 · 한계 | 45 s | 318 | 7.07 |
| **total** | **300 s** | **1,630** | **5.43** |

The finding does not depend on knowing the true comfortable rate for spoken Korean, and I am
not asserting one. It depends on the spread: **4.24 to 7.07 is 1.67×, inside one document, from
one stated method.** One rate cannot satisfy both ends. If 3막's 4.24 is the right pace the
script needs **385 s**; if 마무리's 7.07 is achievable it needs **231 s** and 3막 is 30 s too
long. At least one of the six numbers is wrong and probably five are.

**Why this is the item and not a note.** The segment that must be spoken fastest is
**마무리 · 한계**, the limitations close, and it is **last**. `docs/auto/RUBRIC.md` 심사개요:
「발표는 5분을 넘지 않는 것을 권장; 길어지면 중단될 수 있음」. So the material that gets cut
when the clock runs out is the material 창의성 and 과학적 사고 are scored on — the withdrawn
claims, the 0.138 recall, the 「20가구를 구했다가 아니라」 correction — and it gets cut five
times, once per judge. The three **[버림]** sentences buy back 84 syllables, about 17 s, and §2
of the same document guarantees interruptions that will spend it.

**Done when** the six segment times are re-derived from a per-segment syllable count at ONE
rate, the table and every cumulative bracket updated to still sum to 300 s (the proportional
re-budget at 5.43 syl/s is **30 / 43 / 51 / 58 / 59 / 59 s**), any segment still over its share
trimmed of text carrying neither a number nor a caveat, and `tests/test_demo_script_5min.py`
gains a check that each segment's spoken syllable count over its seconds stays inside a stated
band. **No caveat is deleted to buy seconds** (CHARTER §3.5) — that is the whole point of
WFG-095, which closed cleanly this window. The half no test reaches is unchanged and this item
does not claim it: a human reading it aloud with a stopwatch is R12 / NH-014.

**Cheapest test, if the row is doubted:** read 마무리 aloud once and time it.

This qualifies under CHARTER §14b on the same reading critic #15 used for WFG-095: the words the
student says to the judge. It is the only item this lap sets.

## The rest, ranked, and where each lives

1. **WFG-101** (P0, new) — the headline 24.73 % was **3.53 %** before this project found and
   corrected the DEM defect that trains every other fire's model
   (`docs/dem_defect_2026-08-02.md:67-70`, `docs/decision_shift.md:118-151`,
   `docs/multi_region.md:8-18`, where it is the first blockquote a judge reads). Nothing in
   `JUDGE_QA.md`'s 41 questions and nothing in the booth script says so. This is the best
   과학적 사고 answer the project owns and the student has no card for it.
2. **WFG-096 corrected in place** — the row filed last window told the next lap the 368 and 458
   origins are 「a census of that region's walk-network origins」. They are not: 458 of 8,443
   nodes at stride 18, then hazard-filtered, 5.4 % of the graph. The paper lap's reviewer
   removed the same sentence from `paper/manuscript.md` §6 six hours after the row was filed;
   the backlog was the second place the false framing was living.
3. **NH-026** (author) + **WFG-102** (P1, parked by §14b) — `2b7c3a0` was pushed by the paper
   routine on `gates.py --mode quick`, which does not run `pytest-full`, and it broke two tests.
   Its own `auto-gates` run 109 was **cancelled** by the next push, so the red landed on run 110
   at `d2418c2`, a bare claim marker that changes no code. CHARTER §3 rule 9 requires
   `--mode full`; CHARTER §12 grants the paper loop no exemption. And
   `docs/auto/ROUTINE_PROMPTS.md` is titled 「the three cloud routines」, carries four, and does
   **not** carry `wfg-autoloop-paper` — so the one routine that pushed a red commit is the one
   whose instruction the repository cannot show anyone (CHARTER §9).
4. **KCF_READINESS correction** — critics #14 and #15 wrote 「web/ untouched, twelfth /
   thirteenth consecutive window」. `web/finals.html` was changed at `deeb147`,
   2026-09-04T15:32Z (one line, the WFG-067 commit stamp). The sentence they meant is true:
   the screen's **content** has not changed since `dc63a06`, 2026-09-04T07:14Z.
5. **SCORECARD series table** — the `83f49bc` row appears twice and the first of the two spills a
   paragraph into the `A·목적` column, so the combined table stops rendering from there down.
   Left in place under §3.7 rather than deleted; recorded here so a lap that may edit it does.

## What this lap verified rather than read

- `gates.py --mode full` at `c37f27e`: **ALL GREEN**, 1,475 passed / 62 skipped in 197 s, cold.
  `baseline-verify` WARN, expected off-laptop, `hard: false`, sixteenth window, still not a
  finding.
- `make finals-bundle`: exit 0, `OK — release/kcf-finals-2026/ rebuilt byte-identically, 16 files`.
- `gates.py --assert-reported --base 466900b`: exit 0, 18 substantive paths travel with a report.
- Every dev report in the 24 h window carries a `Reviewed by:` line. Seven of seven.
- `auto-gates` runs 111 and 112 are `success`; 112 is this head's parent line. Run 110 is the
  window's one red and item 3 above is why.
- The demo script's §3 mapping table: 35 rows, 33 backtick keys, **33 of 33 resolve** in
  `docs/NUMBERS.json`.
- `paper/references.bib`: 28 entries, **every one** carries a `verified` note. Spot-checked five,
  including `radeloff2005` against Ecol. Appl. 15(3):799-805, doi 10.1890/04-1413.

## Readiness and score

**4 of 11 (R2, R4, R5, R6), no line ticked this window.** R4 moved last window so the
「zero for two consecutive critic laps」 direction finding does not fire. R9 is ☐ on the
printables (R7) and the booth recipe (WFG-037) only — critic #16 answered on the line itself
that R9 does **not** require a committed payload.

**B 83 held** (16 / 15 / 19 / 15 / 18) · **A 76 → 77** (16 / 15 / **17** / 15 / 14), the +1 on
구현 및 유용성 for a bundle this lap assembled itself.
