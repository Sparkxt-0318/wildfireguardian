# Critic latest — the next dev lap's first read

*Critic lap #61, 2026-09-10T2000Z. Reviewed head `be39dea`. Window 2026-09-10T16:44Z to
2026-09-10T18:40Z since the last critic lap, inside a 24 h look-back to 2026-09-09T18:40Z:
5 commits since critic #60, of which one is a research lap and four are report or archive
commits. This lap changed no code, no test, no data, no figure and no committed artifact.
It wrote only under `docs/auto/`.*

⚠ The clone arrived **SHALLOW at 50 commits**, the fifth lap running, which is shorter than the
24 h window itself, so `git log --since` would have returned the whole clone and truncated in
silence. `git fetch --unshallow` was run before anything was counted:
`--is-shallow-repository` answers **false** and `git rev-list --count HEAD` answers **730**.
Every ancestry statement below is licensed under CHARTER §4.

## `fix-before-next-row`: ZERO. Take the top row directly.

Measured rather than assumed, at `be39dea`. CHARTER §14b lets a preemption be **minutes** AND on
a listed surface (README opening, finals screen, Q&A bank, manuscript, printables, release
bundle) or a red gate.

- **No gate is red anywhere.** `gates.py --mode full` exits **0** (2042 passed, 63 skipped,
  3 xfailed, pytest 282.0 s). `baseline-verify` WARNs on the two git-ignored `data/raw/**`
  contracts, which is NH-029 and §3d working as designed. `--assert-head` and
  `--assert-reported` both exit 0.
- **GitHub's own runs are green.** `auto-gates` runs **294 to 343**: ZERO `failure`, with run
  **343** `success` at this exact head. CHARTER §4b sets no finding #1, the tenth consecutive lap.
- **Both judge-facing defects this lap found pay the NH-049 rebuild.** WFG-240 edits
  `docs/auto/finals/RELATED_WORK_PANEL.md` and WFG-241 edits `docs/auto/JUDGE_QA.md`; both are
  hashed printables sources, so each costs `make printables` at a new stamp plus a re-pointed
  `release/kcf-finals-2026/MANIFEST.json`. That is a price tag, not minutes. So they are rows.

**One thing was fixed here rather than left for a row: WFG-239's own headline.** As filed it said
「the manuscript claims the architecture as its contribution」 and cited no manuscript line. It is
false at this head, checked in three places: `paper/manuscript.md:29-31` (Abstract, 「the
transferable contribution is the evaluation design ... rather than the model」), `:84-88`
(Introduction, 「**We make three claims**」, none of them the architecture) and `:821-833`
(Conclusion, 「is not a contribution to spread modelling, and this paper does not present it as
one」 ... 「The rest of the contribution is the instrument」). A lap acting on the row as filed
would have hunted for a claim to retract that is not there. The deliverables were right and are
unchanged; the card half moved to WFG-241. That is a backlog edit, not a preemption.

## Findings, ranked

**1. (WFG-240, P0, KCF) The printed 관련연구 panel names this project's spatial unit and its own
differentiator in the household register `WC-013` withdrew, and no gate can see either spelling.**
`docs/auto/finals/RELATED_WORK_PANEL.md:46` reads 「공간 단위는 **가구(집)**」 as the third row of a
three-way comparison whose other rows are NIFoS and G-DAPS's 「**읍면동**」 (`:43`), and `:119-120`
reads 「**조사한 범위에서 찾지 못한 것**은 그 발상을 농촌 **가구 단위의 도보 대피**에 ...」, the
sentence that states what this project does that the survey did not find. The same file already
carries the correction: `:23` says 「**지점 단위의 대피 경로와 구조 출동 순서**」 and `:27-31` is the
⚠ 2026-09-10 정정 block naming WFG-222 and WC-013, which scopes itself to 「**이 문단**의 단위 낱말」
and leaves the rest of the sheet in the old register. **It is on the paper, verified:**
`manifest_20260910T1233Z.json` lists this file among its seven `sources` and all **seven** hash
equal to the tree at this head, re-computed here, so `WFG_printables_20260910T1233Z.pdf` carries
both lines. **Why the gate is silent, and this is the part worth keeping.** WC-013's Korean
pattern is anchored on 「가구 단위」 plus one of {걸어서 나갈, 대피 판정, 구조 순서, 출동 순서,
판정과 걸어, 인명}, deliberately, so Q20a and Q16 do not trip; 「공간 단위는 가구(집)」 contains no
「가구 단위」 at all and 「가구 단위의 **도보 대피**」 matches no alternative. **And a spelling that
covered it would still miss this one**, because the phrase wraps the source line break between
`:119` and `:120`, which is WFG-223's measured limit. `docs/creativity_card.md:721-726` predicted
this instance in writing (「a fourth, differently-worded copy of the same claim escapes both
gates」). This is it, and it is printed.

**2. (WFG-241, P0, KCF; carved out of WFG-239) The judge question this week made unavoidable has
no card, and the row that was to write it sat at P1/IEEE at position 233 of 233.**
「비슷한 걸 만든 사람이 이미 있지 않습니까?」 Bokade et al., Zenodo preprint, **2026-09-09**, concept
DOI `10.5281/zenodo.22668357`, couple a U-Net prior to a CA physics engine and then route away from
actively predicted fire. `docs/auto/JUDGE_QA.md:1246-1247` (Q29a, 없는 것 item 4) tells the student
「그 범위 밖에서 같은 일을 한 연구가 있는지는 모릅니다」, and item 3 sends the judge to Q16a and the
관련연구 패널, neither of which names it. Under DIRECTION's own 「do not start a P1 row while a P0
row is `todo`」 with 15 P0 rows `todo`, a P1/IEEE row at the bottom of the table is not reachable
before the freeze. WFG-239 keeps the manuscript and `references.bib` half.

**3. (NH-057, HIGH, the author's) The object the project now says it contributes has never been
produced from a real fire, and no cloud lap can produce one.** DIRECTION's thesis is now 「the
output object and its measured limits」. `scripts/generate_dispatch_outputs.py:43` needs a
per-origin artifact; `data/processed/real_roads_real_hazard_canonical.json` carries counts only
(`n_origins_scanned` 458, `n_shelter_nodes` 46, `n_nodes` 8443, `n_edges` 21982, **no per-origin
record**), and re-running the routing needs `data/cache/osm/yeongdeok_2025`, which
`tests/test_rescue_routing_real.py:71-109` skips on in the green run at this head. Four options,
nothing proposed for deletion, and option C (「the sentence stays」) is explicitly not a bad outcome.
Row is **WFG-242**, `blocked(NH-057)`.

**4. (no row; resolved on DIRECTION.md) The board's own P0 count is knowable and both of the
research lap's rival parses are artifacts.** 236 rows; **94 P0** (73 written `**P0**`, 21 bare
`P0`); **15 with a `todo` cell**, which is exactly critic #60's number. 「21 / 3」 counted only the
bare spelling; 「108 / 28」 is a substring match over the whole line. WFG-191's column-shift defect
is real, separate, and does not move this count. **No fourth number. Use 94 / 15.**

**5. (no row; corrected inside WFG-239) The knowledge note calls a version DOI a 「duplicate」.**
Re-fetched here: Zenodo record `22668357` returns `doi: ...22668358`, and `22069027` returns
`...22069028`. One record, two DOIs, concept and version. The note cites the concept DOI, which is
the right one; 「duplicate」 is the wrong word and it matters because WFG-239 asks a lap to add a
`verified` `references.bib` entry.

## What the window actually produced

One research lap (`ae4b1f2`), and it was a disciplined one. Both external records were re-fetched
in this lap's own process and **both verify**: Bokade et al.'s title, date, five authors and the
「neither a recurrent nor a non-recurrent network learns to advect fire past the persistence
baseline」 wording are in the record's own abstract; Choi & Chae's 118 events, 102-event
operating-envelope subset and 2026-09-01 date are in theirs. The lap recorded the 위험 구역 zoning
framing as **UNVERIFIED** and forbade writing it, which is exactly right, and it registered no
figure from any note. **The research report carries no `Reviewed by:` line and that is by design**,
not a defect: only the dev and paper routines have a reviewer step, and no research report has ever
carried one.

## Scorecard, at `be39dea`

**Track B 96 → 95.** 제출 자료 **19 → 18**. 연구 목적 18, 설계와 방법론 20, 데이터 수집·분석·해석 20,
창의성 19, all HELD.
**Track A 97 → 96.** 제출 자료 **19 → 18** on the identically worded criterion. 개발 목적 19,
설계와 방법론 20, 구현 및 유용성 20, 창의성 19, all HELD.

⚠ **The window's diff moved nothing, and the deduction is still honest.** Critic #59 set the
precedent in this file's own terms: the instruction is to score today's state, not the window's
delta. What changed is the measurement, not the tree. **The evidence is new even though the defect
is not:** WFG-240 is on the printed paper a judge is handed, it is the fourth open 제출 자료 defect
(WFG-233, WFG-236, WFG-240, WFG-241), and two of the four are now on paper rather than in `docs/`.
**Pre-registered for critic #62:** 제출 자료 returns to 19 when WFG-240 and WFG-241 both close with
the kit rebuilt, and to 20 when WFG-233 and WFG-236 close as well; 구현 및 유용성 is re-examined
upward only when the disc null or the centroid overshoot reaches `web/finals.html` or
`docs/auto/JUDGE_QA.md`, unchanged from critic #60.

## Root objection (`hate`), and its cheapest test

**The project has just moved its entire novelty claim onto the one artifact class whose real-data
instance does not exist.** The output object's committed instances were made on a synthetic hazard
surface and synthetic terrain from sampled origins; the run where both axes are real emits
four-way verdicts and no dispatch documents. Every surface says this, honestly, which is precisely
what makes the objection load-bearing rather than a gotcha.
**Cheapest test, and it was run here:** point `generate_dispatch_outputs.py --source` at the
real-hazard artifact. It cannot be done, and the reason is finding 3 above. That is NH-057, and
the second-cheapest test is the author's option B, one run on the laptop that emits per-origin
records so every later lap can do it without them.

## `Do NOT edit` notes — one, line-scoped, re-measured, expiring

⚠ **Do not write a byte into `docs/auto/JUDGE_QA.md` or
`docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed
`release/kcf-finals-2026/MANIFEST.json`.** Critic #60's note is **re-stated after re-measuring its
premise, and widened by one file** because this lap's finding 1 lives in the second one. The
measurement, taken in this lap's own process at `be39dea`:
`docs/auto/finals/printables/manifest_20260910T1233Z.json` lists seven `sources` and all **seven**
hash equal to the tree, both of these files among them, so the first changed byte turns
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red. **This
note covers those two files and expires at the next critic lap unless that lap re-measures the
seven hashes and re-states it.** It is a price tag, not a prohibition: WFG-235, WFG-240 and
WFG-241 are all expected to edit them, and **one lap should take all three so the rebuild is paid
once instead of three times.**

⚠ **No `Do NOT edit` note is written on `docs/oracle_gap.md`, `docs/disc_null.md`,
`docs/MODEL_CARD.md` or `docs/auto/KCF_READINESS.md`.** WFG-233, WFG-236, WFG-237 and WFG-238 must
all edit them.

## Judge drill — the questions that still have no file behind them

Run against `docs/auto/JUDGE_QA.md` at this head, answering only from files.

1. 「비슷한 걸 만든 사람이 이미 있지 않습니까?」 **No card answers this**, and Q29a's item 4 tells
   the student the repository does not know. It does. → **WFG-241**.
2. 「이 출동 지시서, 진짜 불로 만든 겁니까?」 **Answerable, and well:** Q29a's 없는 것 item 1 gives
   the answer 「아직 아닙니다」 with the artifact that proves it. ⚠ What no file answers is
   **why not**, and after this lap the answer is a measured one. → **WFG-242 / NH-057**.
3. 「이 프로젝트의 공간 단위는 집입니까, 지점입니까?」 **Two files answer, differently, and one of
   them is the printed panel.** → **WFG-240**.
4. 「0.394를 원에 견주셨는데, 이미 물리 모델 0.09가 있지 않습니까?」 Unchanged from critic #60. →
   **WFG-236**.
5. 「약한 폴드는 얼마나 작습니까?」 Answerable but inconsistent across surfaces. → **WFG-233**,
   still the top row.

## Nothing new from the author, on either channel

Sixth consecutive lap saying so. Gmail `from:siyeong0318@gmail.com subject:"WildfireGuardian
autoloop" newer_than:14d` returns 25 threads on the first page and **every one holds exactly one
message**, all of them the loop's own sends, so no reply is threaded under any of them. **PR #31
has zero comments** (read through the GitHub MCP, empty list). `docs/auto/decisions_seen.json` is
unchanged: its `applied` list still ends at **NH-031**, closed 2026-09-06 in a Claude Code session
on the laptop. No `NH-###:` line has ever reached the loop by email.

**24 open entries (23 DECISION + 1 BLOCKER)**, 5 open FYI besides. Two entries (**NH-005**,
**NH-014**) carry no date at all. **NH-046 is due TODAY, 2026-09-10, and is not overdue.** NH-049
and NH-051 come due 2026-09-11. **NH-057** was filed here and is the highest-severity open entry.
