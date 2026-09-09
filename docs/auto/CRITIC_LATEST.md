# CRITIC_LATEST — critic #53, 2026-09-09T2023Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `ba06467`, and
every measurement below was taken at that head. ⚠ This clone is **SHALLOW at 51 commits** and I did **not**
deepen it: where a claim needed full history I made a **fresh clone** of the repository in the session
scratchpad and measured there, which is both cleaner than `--unshallow` and, as it turns out, the thing that
corrects yesterday's root objection. Every claim below says which clone it was taken in. Full report:
`docs/auto/reports/2026-09-09T2023Z-critic.md`.*

## `fix-before-next-row`: NONE this lap, and that is a decision rather than an oversight

CHARTER §14b caps these at one per critic lap. It does not require one. Nothing I found this lap is a fix of
**minutes** on a judge-facing surface, and no gate is red, so the two conditions §14b names are both unmet.
**Run the table.** Critic #52's item was executed correctly and completely; I checked all six of its clauses
rather than taking the report's word:

- the boundary overclaim is **withdrawn**, as `WC-012`, both halves registered separately, with the record line
  carrying the pragma (`docs/auto/finals/TIMELINE_ROLES.md` §0);
- the **six-day 06-06 → 06-13 gap that was not split on** is now §3 item 5, in the document's own
  annotate-never-delete form, and it is the strongest sentence added this window;
- §0 and §2's totals carry 「2026-09-09 `89da7d3` 기준」 and were **not** retyped to today's values;
- `docs/auto/DEMO_SCRIPT_5MIN.md:284-296` carries the same as-of clause, an explicit 「제가 정했습니다」 answer
  and a ❌ line banning the sentence that was withdrawn;
- the artifact was **not** rebuilt and no `timeline_*` key moved;
- the kit was rebuilt last (`WFG_printables_20260909T1908Z.pdf`, 53 pages) and
  `release/kcf-finals-2026/MANIFEST.json` re-pointed after staging.

**Then take WFG-212, not WFG-214.** That is this lap's one §3b reorder and the reason is in `DIRECTION.md`.

## Nothing is red, and I checked rather than inherited it

`gates.py --mode full` exits **0** at `ba06467` (1862 passed, 64 skipped, 3 xfailed, pytest 383.2 s).
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and CHARTER §3d working
as the author chose. `--assert-head` exits 0.

**GitHub `auto-gates`, the full window (runs 279 to 299): no `failure` at all.** Two runs are `cancelled` (278,
284), each superseded by the next push, and both predate this window's dev laps. Run **299** is `success` at
this exact head. **CHARTER §4b therefore sets no finding #1**, for the second consecutive lap.

Every **dev** report in the window records `Reviewed by:`; the 1928Z lap records `subagent (pass)` and, unusually,
spends the commit acting on the reviewer's root objection rather than banking it.

## The root objection (`hate`)

**`web/finals.html` is the one judge-facing surface carrying no word of the objection this repository spent the
whole day correcting everywhere else — and the single place the screen says 「LOFO」 is the card that uses the
leave-one-fire-out design to show the model is good.**

ACT 3 tells the judge, in as many words, that 「모든 출발지에서 화재 무시 직행 경로와 시간 인지 경로를 비교해
네 가지로 분류합니다. **이 판정이 화면의 점 하나하나입니다**」. So every dot on the screen is a verdict of that
comparison. `docs/oracle_gap.md` §2 establishes that those verdicts are graded on `haz_stack`, the very array
the time-aware arm planned on, while `obs_stack` sits in the same npz and scores nothing.

I opened the npz rather than reading that off the prose: `data/processed/routing_demo_canonical.npz` holds
`haz_stack` float32 `(5, 181, 156)` and `obs_stack` uint8 `(6, 181, 156)` on one grid, and a scan of
`scripts/` and `src/` finds **no grader that reads `obs_stack`** — only `measure_oracle_gap.py`, which exists to
measure the gap, and `make_routing_figures.py`, which draws it as a contour.

**Counts on the built screen at `ba06467`:**

| token | on `web/finals.html` | in `scripts/finals.template.html` |
|---|---:|---:|
| 채점 | **0** | **0** |
| 오라클 | **0** | **0** |
| `oracle_gap` | **0** | **0** |
| `haz_stack` / `obs_stack` | **0** / **0** | **0** / **0** |
| 정답을 미리 / 정답이 아니 | **0** / **0** | **0** / **0** |
| 「LOFO」 | **1**, and it is 「확산 모델 · LOFO 교차검증」, the AUC evidence card | 1, the same card |

The template counts matter: this is not a stale build. Meanwhile the screen has a dedicated 「알려진 한계」 panel
with **ten** `rel()` cards, spent on walking-network coverage, the ERA5 publication lag, OSM 정자 tagging in the
refuge layer, and the dispatch-ordering negative result. Every one of those is a smaller caveat than this one.

⚠ **Read the difference from WFG-214 exactly.** Those five surfaces said the **wrong** thing and were corrected.
The screen never said the wrong thing; it says **nothing**. That is an omission and not a contradiction, which is
why the scorecard restores 제출 자료 this lap rather than docking it again — and it is an omission on the surface
with by far the longest exposure: five judges, about ten minutes each, offline, with no README in front of them.

**Cheapest test, ten seconds, already run:** the seven `grep -c` counts above, on the built file and on the
template. **The row is WFG-220**, at the end of the P0 block, and it shares `make finals` + a re-pointed bundle
manifest with **WFG-218**, so a lap taking both pays that mechanic once.

**Credit, because it changes the reading.** The 1817Z and 1928Z laps did the best single day of correction work
this sprint: three README lines moved from a wrong mechanism to the right one with the file linked, a gate that
**required** the README to assert the sentence NH-053 asks about was found and widened, the reviewer's own
exploit sentence was turned into a direct property test that goes red when pasted, and a real defect in
`scripts/build_numbers.py` was found, verified read-only and filed as WFG-219 rather than fixed in passing.

## ⚠ Yesterday's root objection is CORRECTED, and the correction makes the loop freer, not more careful

Critic #52's root objection said `build_timeline_roles.py --check` is decided by the clone's object count, and
`DIRECTION.md` grew a guardrail from it forbidding any rebuild of `data/processed/timeline_roles/timeline_roles.json`
because 「the rebuild writes eight-character anchors and turns GitHub red」.

**The mechanism is right and the blast radius was wrong.** I did not deepen this clone. I cloned the repository
fresh into the session scratchpad, checked out `auto/dev` at `ba06467`, and measured:

| clone state | commits | packed objects | `%h` | `--check` |
|---|---:|---:|---:|---|
| this sandbox, as it opened (shallow at 51) | 51 | 12,975 | - | exit **2**, `shallow` (test skips) |
| **fresh full clone, default single-branch fetch** | **673** | **12,393** | **7** | exit **0** |
| **same clone, all 13 origin branches fetched** | **673** | **12,393** | **7** | exit **0** |
| critic #52's clone, `--unshallow`ed from shallow | 666 | 20,641 | 8 | exit 1, `STALE` |
| critic #52's clone, after `git gc --prune=now` | 666 | 12,052 | 7 | exit 0 |

`--check` in the fresh clone printed `OK — timeline artifact agrees with git log (673 commits, 42 active days)`.
**So the red state is not produced by a full clone, and not produced by extra branches.** It is produced by
`git fetch --unshallow` on an already-shallow clone, which leaves a bloated object store that `git gc --prune=now`
clears. The blast radius is **an agent lap that deepens its own sandbox clone** — not a stranger cloning the
repository, not the student's laptop, not GitHub at `fetch-depth: 0`, and **not `TIMELINE_ROLES.md` §5's
reproduce recipe, which I ran end to end in the fresh clone and which passes**. WFG-217 stays P1 and stays the
right fix; the guardrail on `DIRECTION.md` now names the discriminator and the one-command cure.

**The lesson for the next lap, and it is cheap:** when a claim needs full history, clone fresh into the
scratchpad. Do not `--unshallow` the working clone. It is faster, it leaves this clone's gates alone, and it is
the clone shape the student and the stranger actually have.

## What this lap changed, so you do not re-derive it

- **ONE §3b reorder, spent:** **WFG-212 moved back above WFG-214**, both P0. Critic #52's reason for the
  opposite order is discharged (all three README lines are corrected), and WFG-214's only residue is one link in
  `paper/manuscript.md`, which `paper/check_paper.py` cannot afford at **8,999 of 9,000** body words (re-run
  here, exit 0) and which lives in the paper routine's file (CHARTER §12) behind an open **NH-037**.
- **ZERO `fix-before-next-row` items**, deliberately, per §14b's cap being a cap.
- **ONE new row. WFG-220** (P0, KCF), the root objection above, filed at the end of the P0 block in table order.
- **ONE existing row re-measured and NARROWED, not duplicated: WFG-217**, above.
- **NO new NEEDS_HUMAN entry.** Nothing this lap found needs the author, and what does is already asked:
  **25 entries open** (counted with `decisions.py list`, not by hand). NH-032, NH-034 and **NH-045, a BLOCKER**,
  are **one day past** their stated 2026-09-08 date. NH-035, NH-038, NH-043 and NH-044 are due **today**.
  NH-036, NH-037, NH-042, NH-046 and NH-050 come due **tomorrow**. One reply clears most of them.
- **`docs/auto/JUDGE_QA.md` was NOT edited** (NH-049). The drill's outputs are rows.
- **Scorecard: ONE row moves on each track and it is the same row.** 제출 자료 **B 18 → 19** and **A 16 → 17**,
  restoring critic #51's deduction because the defect it was measured on is gone. Track B **93 → 94**,
  Track A **92 → 93**. See `docs/auto/SCORECARD.md` for what I declined to raise and why.
- **`docs/auto/KCF_READINESS.md`** re-read and its tick header refreshed to this lap. No line ticks.

## The judge drill, and what it answers today that it could not yesterday

I took the bank's hardest cards and tried to answer them from files alone.

1. **「그 구간 경계는 누가 정하셨습니까?」 is now ANSWERED**, and answered against the project's own interest:
   `TIMELINE_ROLES.md` §0's 〔정정〕 block and §3.5 both say a person chose them, and `DEMO_SCRIPT_5MIN.md` gives
   the student 「제가 정했습니다」 plus the ❌ line. Closed within one window of being found.
2. **「그 662와 513은 지금도 맞습니까?」 is now ANSWERED**, and I re-derived it independently in the fresh clone
   rather than trusting the stamp: **673 commits, 524 `Co-Authored-By: Claude` trailers, 42 active days** at
   `ba06467` against the artifact's **662 / 513 / 42** at `89da7d3`. The document says the totals grow and names
   the commit they were counted at, so the honest answer at the booth is 「그 수는 며칠 기준입니다」 and it is
   written down. **42 활동일 is unchanged and is the number the student says out loud.**
3. **「이걸 복제해서 그 일정 스크립트를 돌리면 같은 값이 나옵니까?」 answers YES**, measured today for the first
   time in a clone that is not this sandbox's: `--check` exits 0 in a fresh clone. Yesterday this repository
   believed the answer was no.
4. **「42는 완벽한 예보의 값입니까?」 answers correctly on four of five surfaces** (README ×3 with the file
   linked, Q36, and the manuscript's mechanism clause). The fifth is the manuscript's missing link, NH-037.
5. **「이 화면의 점 하나하나가 판정이라고 하셨는데, 그 판정은 무엇으로 채점했습니까?」 has NO answer on the
   screen.** That is the root objection and **WFG-220**.
6. **「일정 문서를 화면에서 보여 주실 수 있습니까?」 still answers NO.** 일정 counts 0 on `README.md` and 0 on
   `web/finals.html`. **WFG-218**, untouched.
7. **「선생님 모델이 실제로 벌어 주는 값은 얼마입니까?」** Still no number, and still correctly so: WFG-213 is
   `blocked(NH-052)`.
8. **「그 일정 문서를 부스에서 종이로 볼 수 있습니까?」 answers NO, and I am NOT filing it.**
   `docs/auto/finals/TIMELINE_ROLES.md` is not among the printed kit's seven `SOURCES`, while
   `JUDGE_QA.md:1414` and `DEMO_SCRIPT_5MIN.md:287` both point at it. It is **reachable on the judged laptop**,
   which `docs/auto/finals/BOOTH_SETUP.md` puts in front of the student, and `DIRECTION.md` says in as many
   words not to widen the freeze with new payload. Recorded here so the next lap does not re-find it and think
   it is new.

Everything else in the bank I could answer from a file.

## `factchk`: nothing new about the world entered the tree this window

The window's added prose is the three README oracle blocks, the `TIMELINE_ROLES.md` correction, the demo
script's 일정 block, MEMO, two reports and four new tests. A diff of every added markdown line since `375be25`
contains **no new external URL and no new citation**. Every claim in it is about this repository's own git
history or its own committed arrays, and I re-derived the two load-bearing ones independently: the npz key
shapes (above) and the git totals (drill item 2).

## Readiness: 8 of 11, ZERO ticked for the TENTH consecutive critic lap

`docs/auto/KCF_READINESS.md` holds at **8 of 11** (R1, R2, R4, R5, R6, R7, R8, R9), unchanged since critic #43
ticked R8 at 2026-09-08T1429Z. I re-read the cause rather than restating it: R12 is the author's (NH-014); R3 is
`blocked(NH-046)`; R11's row WFG-024 is held by CHARTER §14b until R1, R3, R4, R7, R8 and R9 all tick, and
**R3 is the only one of those six unticked**. Both agent-reachable lines are downstream of **one unanswered
question, NH-046**, which comes due tomorrow and has carried the loop's recommendation unchanged since critic #48.
No fourteenth question is filed, because filing one would be the loop asking itself.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise AND after re-measuring its bounds,
which had gone stale (CHARTER §14c as this routine's prompt states it, NH-036 A; ⚠ a search for `14c` in
`docs/auto/CHARTER.md` still answers **0** at this head, and NH-036, NH-038 and NH-051 are all still `open`).**

It covers the Round-4 fair-opponent block. **At this head that block is `README.md:220-299`, not the 210-282
that critics #49, #50, #51 and #52 all wrote.** WFG-214 added ten lines inside it, so `## Round 4` moved from
200 to **210**, 「### 1.」 from 210 to **220**, and 「### 2.」 from 283 to **300**. Re-measured here, not inherited.
⚠ **That staleness is itself evidence for NH-036, which comes due tomorrow:** a note written as absolute line
numbers stops naming what it means the first time anyone edits the file, which is the failure mode option A was
written to prevent, arriving through a different door.

The note forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19,
86) there while NH-032 and NH-034 are open. Both re-read: both still `open`, both stated due **2026-09-08**, so
one day past. A scan of 220-299 finds **zero** occurrences of any of the five values today.
**It expires at critic #54 unless that lap re-states it after re-reading NH-032 and NH-034, and that lap must
re-measure the bounds before quoting them.** It freezes no file and no question, and the edit it permits is
named so nobody has to guess: **WFG-212's lead paragraph is inside these lines and is allowed**, provided it
carries no margin value.
