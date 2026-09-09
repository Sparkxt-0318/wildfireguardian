# CRITIC_LATEST — critic #54, 2026-09-09T2319Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `3eec471`, and
every measurement below was taken at that head unless it says otherwise. ⚠ This clone is **SHALLOW at 50
commits** (`git rev-parse --is-shallow-repository` = `true`, `git rev-list --count HEAD` = 50, measured here
this lap) and I did **not** deepen it; **no ancestry or reachability claim appears anywhere below**, per
CHARTER §4. Full report: `docs/auto/reports/2026-09-09T2319Z-critic.md`.*

## `fix-before-next-row`: ONE, and it is three lines in the Q&A bank

**`docs/auto/JUDGE_QA.md` lines 609, 1159 and 1377 tell the student that an answer from the 운영사무국 is still
awaited. The author closed that on 2026-09-04, five days ago, and the bank is printed in the booth kit.**

CHARTER §14b names the Q&A bank in its own list of judge-facing surfaces, and this fix is **minutes**: three
prose passages, no artifact, no number, no rebuild of the screen. Measured at `3eec471`:

- **:1159** is inside Q29's 「없는 것」 block. Q29 is **T0** — `docs/auto/JUDGE_QA.md:1385` puts it in the
  nineteen the student speaks 「자기 문장으로, 종이 없이」. It reads 「한국코드페어가 AI 보조 개발을 어떤
  형식으로 공시하기를 요구하는지는 **아직 사무국 답을 못 받았습니다** (NH-008, 백로그 WFG-022)」.
  `docs/auto/NEEDS_HUMAN.md:135` carries NH-008 as **closed 2026-09-04**, and its resolution records that the
  organisers addressed the disclosure question directly and no artifact is required — which is also what
  CHARTER §9 says, and what `docs/auto/finals/TIMELINE_ROLES.md:85` says in the same printed kit.
- **:609** holds a spoken sentence back until 「**WFG-022(사무국 답변)가 오기 전에는**」. `WFG-022` is
  `dropped(NH-008 closed 2026-09-04 by the author: no contact with the 운영사무국 will be made)`. The release
  condition **cannot occur**, so the student is held to the fallback sentence permanently by an instruction
  whose premise the author retired.
- **:1377** is the sharpest and it is not merely stale: 「사무국에 **질의한** 항목이 NH-008입니다」 tells a
  judge a query was put to the 운영사무국. NH-008's own resolution says **「No contact with the 운영사무국 will
  be made」**. That is a false statement about what this team did, on a printed surface, and CHARTER §3 rule 5
  is the rule it breaks.

⚠ **Scope it tightly.** The three passages are the item. The printables rebuild that any lap touching a printed
source pays (the WFG-152 / WFG-187 mechanic: `make printables`, then re-point
`release/kcf-finals-2026/MANIFEST.json` **after** staging) rides with it as usual, and if the same lap also
takes **WFG-222** — which touches this same file — do both first and rebuild the kit **once**.

⚠ **What this item is not.** It is not a licence to re-open the AI-disclosure question. NH-008 is closed and
CHARTER §9 states what the project keeps voluntarily; the fix is to make the bank agree with the record, not to
restate the record.

## Nothing is red, and I ran it rather than inherited it

`gates.py --mode full` exits **0** at `3eec471` (1871 passed, 64 skipped, 3 xfailed, pytest 333.2 s).
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and CHARTER §3d working
as the author chose. `--assert-head` exits 0; `--assert-reported --base ba06467` exits 0 (14 substantive paths
travel with `docs/auto/reports/2026-09-09T2206Z-dev.md`).

**GitHub `auto-gates`, the full 24-hour window (runs 262 to 305, read through the GitHub MCP because `curl`
against `api.github.com` is 403 in this sandbox, WFG-119): no `failure` anywhere.** Three runs are `cancelled`
(275, 278, 284), each superseded by the next push. Run **305** is `success` at this exact head. **CHARTER §4b
therefore sets no finding #1**, for the third consecutive lap. Run 260 (`failure`, `7eeccab`,
2026-09-08T21:47Z) is **outside** this window and was closed the same evening by `wfg-autoloop-ci-red`.

Every **dev** report of the last 24 h records `Reviewed by:`; the 2206Z lap records `subagent (block)` and
spends its commit acting on the block rather than banking it, which is the second consecutive lap to do that.

## The root objection (`hate`)

**This lap corrected the front door's one affirmative claim and left the identical claim, in the identical
words, on the four surfaces that carry it by design — including the screen five judges stand in front of and a
T0 card the student says out loud from memory.**

WFG-212's independent reviewer broke the first draft of the lead block on a conjunction: two artifacts named
side by side are a claim about their **conjunction**, and the committed dispatch sheets were produced on a
**synthetic** hazard surface, while the run where the walk graph and the spread surface are both real produces
no dispatch documents. The lap accepted that. `README.md:212-251` now says 「**지점 단위**」, names what was real
and what was synthetic in that run, and states 「**실제 확산면으로 만든 출동 지시서는 아직 없습니다**」.

I re-derived the reviewer's premise rather than reading it: `data/processed/rescue_routing.json` →
`provenance.sources` reads `walk_network: osm`, `drive_network: osm`, `shelters: osm`, `depots: osm`,
**`hazard: synthetic`**, **`terrain: synthetic`**, **`origins: sampled candidates`**. And
`outputs/dispatch/README.md` states the clusters are DBSCAN groupings at eps = 500 m, not 행정리, and that the
committed sheets cover 44 of the artifact's 143 dispatch points. Both hold.

**The same claim, uncorrected, at this head:**

| surface | what it says | bound present |
|---|---|---|
| `README.md:391-395` (§5 item ①) | 「**가구 단위**의 …판정과 그 도보 경로」 + 「그 산출물의 실물이 저장소에 커밋돼 있습니다」 | **none** |
| `web/finals.html:1580` + `scripts/finals.template.html` | 「**가구 단위**의 대피 판정」 / "a **per-household** evacuation verdict" + 「그 실물이 저장소에 커밋돼 있습니다」 | **none** |
| `docs/auto/JUDGE_QA.md:1172` (Q29a, **T0**) | 「**가구 단위** 구조 순서와 보행 경로가 붙습니다」 + 「실물을 열어 드릴 수 있습니다」 | 행정리 only |
| `docs/auto/DEMO_SCRIPT_5MIN.md:67` | 「지도가 아니라 **가구 단위 판정과 걸어 나갈 길**입니다」 | **none** |
| `docs/creativity_card.md` | "per-household", printed in `WFG_printables_20260909T1908Z.pdf` | **none** |

Counts, unpiped, at `3eec471`: 「가구 단위」 is 1 in `README.md`, 1 in `web/finals.html`, 1 in
`scripts/finals.template.html`, 5 in `docs/auto/JUDGE_QA.md`, 1 in `docs/auto/DEMO_SCRIPT_5MIN.md`;
「지점 단위」 is **1 in the whole repository** and it is the line added this lap.

**Three things make this worse than an inventory of stale words.**

1. **On three of the five, item ① sits immediately beside item ②** — 「두 축이 동시에 실제인 실행」, doc
   `docs/real_roads_real_hazard.md` — which is the exact adjacency the reviewer named. A judge reading ① then ②
   reads 「real roads + real fire → these committed sheets」, and that execution does not exist here.
2. **The loop built a consistency mechanism and the correction landed outside it.** `web/finals.html:1574-1576`
   carries this comment in the source: 「The three items, kept in one place because the Q29a card, the booth
   script and this screen must make the same three claims against the same three files.」 Three surfaces were
   deliberately bound to each other; the README was not bound to any of them, and the README is the one that
   was fixed.
3. **The gate written this lap to stop exactly this cannot see it.** `tests/test_readme_round4_lead.py` scopes
   `test_the_lead_block_carries_its_own_bounds` to the `lead` fixture — 「Everything between the Round-4 heading
   and item 1」 — and its `items` fixture (「### 1.」 to the section end, which **contains** §5) asserts only
   caveat-fragment presence, a ⚠ floor of 10 and the dispatch-ordering hedge. **No assertion binds §5 item ① to
   the lead's bounds.** The section can contradict itself on its own headline claim with the whole suite green.
   No mutation was needed to establish this; it is the file's own fixture boundaries. That is the
   `_UPPER_BOUND` anti-pattern MEMO named yesterday, in the lap that wrote the MEMO paragraph about it.

The row is **WFG-222**, P0, filed at the **end** of the P0 block and **not** at position 1 — see the guardrail
in `DIRECTION.md`, NH-051, and §14b as `NEEDS_HUMAN.md:2016-2019` actually words option B.

## Two rows changed on evidence, and neither is a §3b reorder

**WFG-214 is `done(4f3bd85)`.** Critic #53 re-measured the row down to one remaining item: 「one link in
`paper/manuscript.md`」. Paper lap 25 (`4f3bd85`, 2126Z) added it — `grep -c oracle_gap paper/manuscript.md`
answers **1** at this head, at `manuscript.md:511`. The paper routine may not touch `docs/auto/` beyond its own
report (CHARTER §12), so nobody could close the row, and it sat `todo` **at table position 1** with no work
left in it. A dev lap would have claimed it and found nothing. Closed here with the commit that did it.
⚠ This is a status update on a measurement, **not** a §3b reorder; §3b limits moving a row's position, and no
row moved.

**WFG-222 filed** (above), at the end of the P0 block.

**ZERO §3b reorders this lap.** Closing WFG-214 hands the top of the table to **WFG-218**, which is runnable,
so there is nothing a reorder would buy. §3b permits one act; it does not require one.

## `factchk` on the window's new prose

The window (`ba06467..3eec471`) adds **no new external URL and no new citation**. Every URL in an added line is
either this repository's own clone address or a quotation inside a record page. The only new claims about the
world are claims about this repository's own committed artifacts, and the two load-bearing ones are re-derived
above from `rescue_routing.json` and `outputs/dispatch/README.md`. Both hold. `paper/manuscript.md` moved by
one clause and one link, and the bound clause 「this project's own model is worth less」 is unchanged word for
word, which is correct while **NH-053** is open.

## The judge drill, ten questions, one with no evidence

Answered from a file, verified by opening it: 「어떤 일정으로 만들었습니까?」
(`docs/auto/finals/TIMELINE_ROLES.md`), 「42가 무슨 뜻입니까?」 (`docs/oracle_gap.md`), 「가구 위치는 어디서
얻었습니까?」 (`README.md:235-238` + `outputs/dispatch/README.md`), 「개인정보는?」 (Q20a), 「누가
책임집니까?」 (Q16b), 「저희 군이 도입하려면?」 (Q16c), 「완충거리 폭은 어떻게 골랐습니까?」 (README §1),
「탐지 바닥은?」 (`docs/auto/finals/DETECTION_FLOOR_CARD.md`), 「다른 지역에도 됩니까?」 (README lead, which
declines the claim).

**No evidence yet, on the surfaces a judge reaches:** 「이 출동 지시서, 진짜 불로 만든 겁니까?」 — answered on
`README.md` since 2206Z today and **nowhere else**. That is WFG-222 and it is why the row exists.

⚠ **No card was added to `docs/auto/JUDGE_QA.md` this lap and that is not an oversight**: **WFG-216** (P1)
records that the bank's answered cards and its open questions share one id namespace and the open questions have
consumed the next five ids, and **NH-049** is the author's open question about it. The drill's one gap is filed
as a backlog row instead, which is what CHARTER §5 asks for.

## Readiness: ZERO lines ticked in 24 h, for the ELEVENTH consecutive critic lap

8 of 11, unchanged since critic #43 ticked R8 at 2026-09-08T1429Z. I re-read the cause rather than restating it:
R12 is the author's (NH-014); R3 is `blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b as loop
hygiene until R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. Both agent-reachable
lines are downstream of **one unanswered question, NH-046, which comes due 2026-09-10 — tomorrow**. No
fourteenth question is filed; filing one would be the loop asking itself.

## NH-037 is now zero-margin, and I measured it rather than quoted it

`paper/check_paper.py` at this head prints `body_words: 9000` and `LIMIT = 9000` with `> LIMIT` failing
(`check_paper.py:75`, `:194`). Exit 0, with a margin of **ZERO words**. The next paper lap that must correct a
sentence cannot add one word without trading a caveat away, which CHARTER §3 rule 5 forbids. **NH-037 is open
and due 2026-09-10, tomorrow.** Recorded on the existing entry; no new entry, because the question is already
the right question.

## ⚠ The one `Do NOT edit` note, RE-STATED after re-reading its premise and RE-MEASURING its bounds

CHARTER §14c as this routine's prompt states it, NH-036 A. It covers the Round-4 **fair-opponent** block, and at
this head that block is **`README.md:263-342`** — not the 220-299 critic #53 wrote, because WFG-212 inserted 43
net lines above it: 「### 1.」 moved 220 → **263** and 「### 2.」 300 → **343**. Measured this lap with
`grep -n '^### '`.

It forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19, 86)
there while **NH-032** and **NH-034** are open. Both re-read in `NEEDS_HUMAN.md` this lap: both still `open`,
both stated due **2026-09-08**, so **two days past**. A regex scan of 263-342 for each value as a standalone
integer finds **zero** occurrences of all five.

**It expires at critic #55 unless that lap re-states it after re-reading NH-032 and NH-034, and that lap must
re-measure the bounds before quoting them — they have now gone stale twice in three laps.** It freezes no file
and no question: every other edit in those lines, this lap's own WFG-222 wording included, is permitted.

## Scorecard

**Track B 94 → 93, Track A 93 → 92. One row moves on each and it is the same row, 제출 자료, DOWN.** Full
reasoning in `docs/auto/SCORECARD.md` at `3eec471`. In short: the lead block is a real 「자료의 논리적 구성」
gain on the front door, and the same window leaves the same file answering its own headline claim two ways 180
lines apart, with the printed kit and the finals screen carrying only the unbounded answer. That is critic
#51's own deduction, on a different claim, in the window that discharged the first one. **Pre-registered
restoration:** it goes back to 19 / 17 when WFG-222 closes on all five surfaces **with the kit rebuilt**, not
when the README alone is fixed.
