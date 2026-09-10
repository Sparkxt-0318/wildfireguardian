# Critic latest — the next dev lap's first read

*Critic lap #60, 2026-09-10T1657Z. Reviewed head `71e95ee`. Window 2026-09-09T16:20Z to
2026-09-10T16:44Z: 61 commits, 46 pushed heads, 9 dev laps, 3 paper laps, 4 critic laps.
This lap changed no code, no test, no data, no figure and no committed artifact. It wrote only
under `docs/auto/`.*

⚠ The clone arrived **SHALLOW at 51 commits**, the fourth lap running, which is about the length of
the window itself, so `git log --since` would have returned the whole clone and truncated in silence.
`git fetch --unshallow` was run before anything was counted: `--is-shallow-repository` answers
**false** and `git rev-list --count HEAD` answers **725**. Every ancestry statement below is licensed
under CHARTER §4.

## `fix-before-next-row`: ZERO. Take the top row directly.

Measured rather than assumed, at `71e95ee`. CHARTER §14b lets a preemption be **minutes** AND on a
listed surface (README opening, finals screen, Q&A bank, manuscript, printables, release bundle) or a
red gate.

- **No gate is red anywhere.** `gates.py --mode full` exits **0** (2041 passed, 64 skipped,
  3 xfailed, pytest 315.2 s). `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts,
  which is NH-029 and §3d working as designed.
- **GitHub's own runs are green.** `auto-gates` runs **294 to 338**: 45 runs, **36 `success`,
  9 `cancelled`, ZERO `failure`**, with run **338 green at this exact head**. CHARTER §4b sets no
  finding #1, the ninth consecutive lap.
- **The judge-facing surfaces hash clean**, all re-computed in this lap's own process: the printed
  kit `manifest_20260910T1233Z.json` at **7 of 7** sources against the tree,
  `release/kcf-finals-2026/MANIFEST.json` at **19 of 19**, `web/finals.html` stamped `4ab2e07`,
  an ancestor of `HEAD` by **5** commits against a 30-commit limit.
- **The window's sharpest defect (WFG-236) is on `docs/disc_null.md` and `docs/oracle_gap.md`**,
  which are on none of §14b's listed surfaces and in neither hashed set. So it is a row.

**One thing was fixed here rather than left for a row: WFG-235's own text.** As filed it told the
next lap to write **2.536** onto `docs/auto/JUDGE_QA.md` Q36, a **T0** card said from memory to five
judges, while the same day's `docs/disc_null.md:119-120` says 「**2.5360 is not quotable without
2.2044 beside it**」 and `docs/oracle_gap.md:194` says 「⚠ **Quote the second row, not the first.**」.
The row now carries the seed-removed pair (**0.2577 / 0.1169**, ratio **2.2044**) and the three
registry keys behind it. That is a backlog edit, not a preemption.

## Findings, ranked

**1. (WFG-236, P0, KCF) The two new sections that answer 「what should IoU 0.394 be compared with」
both state the repository offered no comparison, and the front door has been offering one for
months.** `docs/disc_null.md:20-21` and `docs/oracle_gap.md:180-181`. `README.md:520-522` (Korean)
and `:888-891` (English) compare the same forward-simulated footprint IoU to the Rothermel surface
model's **~0.09** and call it 「약 4배」 / 「roughly 4×」, sourced to
`docs/ROUTING_INTEGRATION_REPORT.md:183`. Same fire, same 3-to-12-hour slice family. The two
comparisons point opposite ways, neither page names the other, and the README's comparator is a model
its own TL;DR calls broken (「a documented moisture-conflation bug, which motivated the pivot」).
Whether the README's framing itself should move is **NH-055**, the author's; **no lap edits that
bullet**.

**2. (WFG-237, P0, science) The caveat the front door already carries about 42 acquired a magnitude
today, and it lives in one file nothing points at.** The TL;DR already says 42 is 「what this policy
buys when its own prediction is believed」. `docs/disc_null.md` §4 now sizes that: the model's core
centre of mass travels **3,646.1 m** where the observed footprint's travels **1,124.8 m**, and the
**stationary disc ends up closer to the truth than the model** (2.266 cells of error against 5.340).
`docs/oracle_gap.md` §4c carries the IoU pair and **none** of the centroid figures.

**3. (WFG-235, corrected in place) The row carrying today's result to a T0 card quoted the number its
own day forbids quoting alone.** See the preemption section above.

**4. (WFG-238, P1, infra; text repaired here) The definition-of-done page led with a tick count one
critic lap stale, which is the exact shape the lap before it had just named.**
`docs/auto/KCF_READINESS.md:8-11` read 「critic #58 … **FIFTEENTH** consecutive」 while the same file's
newest section at `:1841` read 「critic #59 … **SIXTEENTH**」. Critic #58's own append at `:12-16` had
named that shape (WFG-107) one lap before critic #59 repeated it. Repaired by hand; WFG-238 is the
gate that would bind them. §14b holds it at P1 behind R3.

**5. (no row; corrected in two pages and recorded on WFG-107) NH-046 is due TODAY, not two days past
due.** Its heading at `docs/auto/NEEDS_HUMAN.md:2847` reads 「(by 2026-09-10)」 and it was never
re-dated, yet critic #58 and critic #59 both published 「NH-046 is now two days past due」 on
`DIRECTION.md` and `KCF_READINESS.md`. Corrected on both pages rather than repeated. It still holds
**R3**, the only unticked line of the six CHARTER §14b needs before the P1 block opens.

## What the window actually produced, and it was a good day

`b8fd6a8` (WFG-228) is the strongest single artifact this loop has shipped. It answers a question five
judges will ask in the first minute, with a null that has **zero free parameters** whose rule and
interpretation were both fixed in the claim commit `4ab2e07` **before** the script ran. It then did
two things a weaker lap would not have. It **refused its own row's interpretation in writing** (the
row said the gap is 「the model's directional skill and nothing else」; §4 shows the disc places the
fire better than the model does). And when the independent reviewer found that both masks inherit the
fire's 249-cell first frame from a cumulative `obs_stack`, it **published the harsher number**:
2.2044, not 2.5360, on both pages and in the caveat band on all 84 `dn_yeongdeok_` keys.

Critic #58's pre-registration is therefore **paid**, and the scorecard pays it.

## Scorecard, at `71e95ee`

**Track B 94 → 96.** 데이터 수집·분석·해석 **19 → 20** (pre-registered by critic #58, paid by
WFG-228). 창의성 **18 → 19**. 연구 목적 18, 설계와 방법론 20, 제출 자료 19, all HELD.
**Track A 96 → 97.** 창의성 **18 → 19** on the identically worded criterion. 개발 목적 19,
설계와 방법론 20, 구현 및 유용성 20, 제출 자료 19, all HELD.

⚠ **구현 및 유용성 did not move, and that is this lap's quietest finding.** The window's largest
result reached **no** judge-facing surface: the disc null lives in `docs/`, and WFG-235 (the Q36 card)
and WFG-237 (the document half) are both `todo`.

## `Do NOT edit` notes — one, line-scoped, re-measured, expiring

⚠ **Do not write a byte into `docs/auto/JUDGE_QA.md` without `make printables` at a new stamp and a
re-pointed `release/kcf-finals-2026/MANIFEST.json`.** The measurement, taken in this lap's own process
at `71e95ee`: `docs/auto/finals/printables/manifest_20260910T1233Z.json` lists seven `sources` and all
**seven** hash equal to the tree, `docs/auto/JUDGE_QA.md` among them
(sha256 `df826a4cec52…`, first twelve characters; the full digest is in the manifest and is not restated here, because it contains a three-digit substring the retired-claim scanner reads as a count), so the first changed byte turns
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red. **This note
covers that one file and expires at the next critic lap unless that lap re-measures the seven hashes
and re-states it.** It is a price tag, not a prohibition: WFG-235 and WFG-237 are expected to edit the
bank and pay the rebuild. It is also why this lap filed its judge-drill gap as a backlog row instead
of adding a 「no evidence yet」 card, as the routine prompt's default would have had it do.

⚠ **No `Do NOT edit` note is written on `docs/oracle_gap.md`, `docs/disc_null.md` or
`docs/MODEL_CARD.md`.** WFG-233, WFG-236 and WFG-237 must all edit them.

## Judge drill — the questions that still have no file behind them

Run against `docs/auto/JUDGE_QA.md` at this head, answering only from files.

1. 「0.394를 원(disc)에 견주셨는데, 이미 물리 모델 0.09가 있지 않습니까? 왜 원입니까?」 **No file
   answers this.** `docs/disc_null.md` §5.2 lists `run_persistence_baseline` and
   `run_isotropic_baseline` as unscored opponents and never mentions the Rothermel CA baseline the
   README compares to. → **WFG-236**.
2. 「예보를 믿고 대피시키면, 실제로는 그만큼 가지도 않은 불에서 사람을 멀리 보내는 것 아닙니까?」
   Answerable from `docs/disc_null.md` §4 alone, and from **no** card, screen or README line. →
   **WFG-237** (document half) and **WFG-235** (card half).
3. 「0.394 안에 이미 불이 난 곳이 들어 있습니까?」 **Answerable**, and well:
   `docs/disc_null.md` §3c and `docs/oracle_gap.md` §4c. New this window.
4. 「약한 폴드는 얼마나 작습니까?」 **Answerable but inconsistent across surfaces.** → **WFG-233**,
   still the top row.

## Nothing new from the author, on either channel

Fifth consecutive lap saying so. Gmail `from:siyeong0318@gmail.com subject:"WildfireGuardian
autoloop" newer_than:14d` returns 30 threads on the first page and **every one holds exactly one
message**, so no reply is threaded under any of them. **PR #31 has zero comments.**
`docs/auto/decisions_seen.json` is unchanged: its `applied` list still ends at **NH-031**, closed
2026-09-06 in a Claude Code session on the laptop. No `NH-###:` line has ever reached the loop by
email.

**22 open entries (21 DECISION + 1 BLOCKER)**, 5 open FYI besides. **13 are at or past their date**
(the 09-10 group is due today, not overdue). NH-049 and NH-051 both come due tomorrow. Two entries
(**NH-005, NH-014**) carry no date at all. NH-055 was filed today.
