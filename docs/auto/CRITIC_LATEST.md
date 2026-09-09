# CRITIC_LATEST — critic #52, 2026-09-09T1719Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `375be25`, and
every measurement below was taken on that head in this clone. ⚠ This clone opened **SHALLOW at 50 commits**;
I deepened it first by the window predicate (`--shallow-since='2026-09-08T00:00:00Z'`, 101 commits) and then
with `--unshallow`, so `--is-shallow-repository` now answers **false** and the clone holds **666** commits
reachable from `HEAD`. Ancestry and re-derivation claims below are therefore licensed, and each says which
clone state it was taken in. Full report: `docs/auto/reports/2026-09-09T1719Z-critic.md`.*

## `fix-before-next-row`: ONE item, prose only, and it is on the document this window shipped

**`docs/auto/finals/TIMELINE_ROLES.md` says two things about itself that are not true at this head.** It is
the answer to 「일정 및 팀원(개인의 경우 제외) 역할 배분의 타당성」, a named sub-item worth **20 points on
both scoring tables**, it shipped six hours ago, and it is reachable from the two printed judge surfaces
(`docs/auto/JUDGE_QA.md:1414`, `docs/auto/DEMO_SCRIPT_5MIN.md:287`), so a judge meets it through the kit.

**(1) The boundary claim is an overclaim, and a software-engineering judge falsifies it in the builder.**
§0 says 「각 구간의 경계는 제가 정한 것이 아니라 커밋 기록에 실제로 비어 있는 달력 간격입니다」. Measured at
this head on the builder's own clock (`TZ=UTC`, `--date=format-local:%Y-%m-%d`), the record's empty-day gaps,
largest first, are:

| empty days | gap |
|---:|---|
| 32 | 2026-06-15 → 07-18 |
| 15 | 2026-08-12 → 08-28 |
| **6** | **2026-06-06 → 06-13** |
| 5 | 2026-07-26 → 08-01 |
| 2 | 2026-05-30 → 06-02 |
| 1 | four of them, including 2026-09-01 → 09-03 |

The document splits on the 32, the 15, the 5 and **one of the one-day gaps**, and does **not** split on the
**six-day** gap. There is no gap-selecting rule anywhere: `scripts/build_timeline_roles.py:40-84` hard-codes
all five `start` / `end` / `anchor` literals, and `build()` only counts inside them. So the boundaries **are**
a choice. What is genuinely verified is the weaker claim the same paragraph also makes:
`commits_outside_phases` is **0**, so the four gaps it does name are real and no commit falls in one.

**(2) Two of the three totals were already wrong within six hours of being written.** §2's AI row states
「`Co-Authored-By: Claude` 트레일러 **513개** (전체 **662개** 중)」 as a flat present-tense fact. Re-derived
at this head with the repository's own builder: **517 of 666**. 활동일 **42** is still 42. §3 item 4
discloses growth for **5기's** counts only; §0's 「활동한 날 42일」 and §2's pair carry no as-of stamp, and
the booth line in `DEMO_SCRIPT_5MIN.md:284-287` tells the student to say 「활동한 날은 42일」 out loud.

**Scope it exactly, and no wider:**

- **Prose only.** Do **NOT** rebuild `data/processed/timeline_roles/timeline_roles.json` and do **NOT**
  register or re-register any `timeline_*` key. The artifact is correct for the commit it was built at, and
  rebuilding it in this sandbox writes 8-character anchors that turn GitHub's own check red (**WFG-217**).
- Replace the boundary claim with what is verified: the split was chosen from the record's longest gaps, and
  the script proves no commit falls outside the five phases. Add the **six-day 06-06 → 06-13 gap that was not
  split on** to §3's 「보여 주지 않는 것」 list as a fifth item, in the document's own annotate-never-delete form.
- Put an as-of stamp on every total in §0 and §2, in this repository's own agency/as-of/scope convention
  (CHARTER §3 rule 5b): 「2026-09-09 `359fd15` 기준」. **Do not retype them to today's values**, because
  nothing would then re-derive them.
- Give `docs/auto/DEMO_SCRIPT_5MIN.md:284-287` the same as-of clause. That line is printed.
- The kit is hashed, so the same lap runs `make printables` and re-points
  `release/kcf-finals-2026/MANIFEST.json` **after** staging, exactly as the 0949Z, 1250Z and 1619Z laps did.
- ⚠ **Do not touch the 42일 / 42곳 collision warnings** in §0 and in the demo script. They are correct, they
  are the best thing in the document, and they are why this item is a repair and not a retraction.

**Then take WFG-214, not WFG-212.** That is this lap's one §3b reorder and the reason is in `DIRECTION.md`.

## Nothing is red, and I checked rather than inherited it

`gates.py --mode full` exits **0** at `375be25` (1850 passed, 64 skipped, 3 xfailed, pytest 263.3 s).
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and CHARTER §3d
working as the author chose. `--assert-head` exits 0.

⚠ **My pytest counts differ from the 1619Z dev lap's (1851 passed, 63 skipped) by exactly one test, and the
difference is the point of WFG-217 below.** `tests/test_timeline_roles.py::test_the_artifact_still_agrees_with_the_history_when_the_clone_has_one`
**skips** in a shallow clone and **runs** in a full one. It skipped in my first pass and, once I unshallowed,
it does not merely run: it **fails**, and the failure is not a defect in the tree.

**GitHub `auto-gates`, the full 24 h window (runs 255 to 294):** two `failure` runs, **255** (`b7c1837`,
`actions/upload-artifact` 403) and **260** (`7eeccab`, a debug-port race), both already inside critic #50's
window, both closed by `wfg-autoloop-ci-red` inside the hour (runs 256 and 261), and both already reported.
Three runs are `cancelled` (275, 278, 284), each superseded by the next push. **The five runs since critic
#51 (290, 291, 292, 293, 294) are all `success`, and 294 is green at this exact head.** There is **no new red
run**, so CHARTER §4b sets no finding #1 this lap.

Every **dev** report in the window records `Reviewed by:`; the 1619Z lap records `subagent (block)` and lists
all six nails fixed, none argued.

## The root objection (`hate`)

**The one gate that binds the schedule document to the history it reports gives two different verdicts on two
clean clones of the same commit, and the one it gives here accuses a correct document of drift.**

`scripts/build_timeline_roles.py:110-115` resolves each phase's anchor with `%h` / `--abbrev-commit`. Git's
abbreviation width is a property of the **clone's object count**, not of the history. Measured at `375be25`:

| | stored artifact | re-derived in this clone |
|---|---|---|
| p1 anchor | `a88700c` | `a88700c8` |
| p2 anchor | `4e9dfe3` | `4e9dfe39` |
| p3 anchor | `66abf92` | `66abf92e` |
| p4 anchor | `25f1e14` | `25f1e142` |
| p5 anchor | `522f7a7` | `522f7a72` |

`build_timeline_roles.py --check` therefore exits **1** with `STALE timeline artifact: phase starts or anchor
commits` here, while GitHub run **294**, which ran the same check on the same commit at `fetch-depth: 0`,
exits 0. The `--check` design is otherwise careful: it deliberately exempts the totals and 5기's counts as
growth (`:181-186`) and pins only the settled past. **The one thing it says must never move is the one thing
it measures with a clone-dependent string.**

Two costs, and the second is the one that reaches a judge. First, the next lap that unshallows to make a
dated claim, which CHARTER §4 tells laps to do, meets a red gate whose message says the document drifted when
it did not. Second, and worse, the obvious repair is to **rebuild the artifact**, which writes eight-character
anchors into a committed file and turns **GitHub** red instead. That is why the `fix-before-next-row` item
above forbids the rebuild in as many words.

**Cheapest test, ten seconds, already run:**
`.auto/venv/bin/python scripts/build_timeline_roles.py --check` in a full clone at `375be25` prints
`STALE timeline artifact: phase starts or anchor commits`; the same command in the shallow clone prints
`shallow` and exits 2; GitHub 294 is green. Three clones, three answers, one commit.

**Credit, because it changes the reading.** The file this objection is about is the best-instrumented
document the loop has shipped: 20 registry keys, 10 tests with 9 graded by mutation, `commits_outside_phases`
as a partition proof rather than a selection, an honest empty 지도교사 row, and a §3 that names four things
its own numbers do not show. The defect is that the one check reading git measures the clone, which is the
same class CHARTER §4 says the loop has paid for five times, arriving through width instead of depth.

## What this lap changed, so you do not re-derive it

- **ONE §3b reorder, spent:** **WFG-214 moved above WFG-212**. Both are P0, so no P0 row falls below a
  non-P0 row. Reason in `DIRECTION.md`, and it also removes a live contradiction: `DIRECTION.md` listed
  WFG-214 second and WFG-212 third while the table had WFG-212 at row 19 and WFG-214 at row 21, so
  「table order」 and 「DIRECTION order」 named different next rows and the 1619Z dev report inherited the error
  (「WFG-214 sits above it in table order」).
- **ONE `fix-before-next-row` item**, above, prose only.
- **TWO new rows.** **WFG-217** (P1, infra) is the `%h` defect. **WFG-218** (P0, KCF) is WFG-027's own
  disclosed residue, refiled as a row because **residue recorded on a `done` row is work no dev lap will ever
  pick up** (CHARTER §5 puts residue on a row set back to `todo`, and WFG-027 is `done`).
- **ONE existing row updated, not duplicated.** **WFG-214**'s inventory of five surfaces is stale by two:
  `paper/manuscript.md:509-512` had its mechanism corrected by paper lap 24 (`bd0da54`) and
  `docs/auto/JUDGE_QA.md` Q36 was corrected in full by the 1619Z dev lap. Three README lines remain, plus the
  `docs/oracle_gap.md` link the manuscript still lacks.
- **NO new NEEDS_HUMAN entry**, deliberately. Nothing this lap found needs the author. What does need the
  author is already asked: **25 entries open**, and **seven are at or past their stated date** (NH-032 and
  NH-034 one day past; NH-035, NH-038, NH-043 and NH-044 due today; NH-045, a BLOCKER, one day past).
- **`docs/auto/JUDGE_QA.md` was NOT edited** (NH-049). The drill's outputs are rows.
- **Scorecard:** **no row moves on either track.** Track B holds **93**, Track A holds **92**. See
  `docs/auto/SCORECARD.md` for the two cancelling moves and for the raise I pre-registered instead.
- **`docs/auto/KCF_READINESS.md` was refreshed.** Critic #51 did not touch it: its tick header still named
  critic #50 at `9c22ff3`, so the page CHARTER §11 calls the product's definition of done was one lap behind
  the last critic that verified it.

## The judge drill, and what it answers today that it could not yesterday

I took the bank's hardest cards and tried to answer them from files alone.

1. **「어떤 일정으로 만드셨습니까?」 is ANSWERED.** It read literal zero on all four judge surfaces for five
   consecutive critic laps. `docs/auto/finals/TIMELINE_ROLES.md` answers it, and 일정 now counts **4** on
   `docs/auto/JUDGE_QA.md` and **4** on `docs/auto/DEMO_SCRIPT_5MIN.md`, both of which name the file.
2. **「그 구간 경계는 누가 정하셨습니까?」 has NO honest answer in the files.** The document says the record
   did; the builder shows a person did. That is the `fix-before-next-row` item.
3. **「그 662와 513은 지금도 맞습니까?」 answers NO.** 666 and 517 at this head. Same item.
4. **「그럼 42는 완벽한 예보의 값입니까, 자기 예측을 믿은 값입니까?」** Two surfaces now answer correctly
   (Q36 and the manuscript's mechanism clause); three README lines still answer the old way. **WFG-214**,
   and the word 「상한」 itself is **NH-053**, open.
5. **「선생님 모델이 실제로 벌어 주는 값은 얼마입니까?」** Still no number, and still correctly so: WFG-213 is
   `blocked(NH-052)`.
6. **「일정 문서를 화면에서 보여 주실 수 있습니까?」 answers NO.** 일정 counts **0** on `README.md` and **0**
   on `web/finals.html`. **WFG-218.**

Everything else in the bank I could answer from a file.

## `factchk`: nothing new about the world entered the tree this window

The window's new prose is `docs/auto/finals/TIMELINE_ROLES.md`, the Q36 rewrite, the 일정 blocks, and paper
lap 24's two manuscript corrections. A diff of every added markdown line since `4693540` contains **no new
external URL and no new citation**. Every claim is about this repository's own git history or its own
committed arrays. The two checkable cross-references I did verify by opening the file rather than trusting
the prose: 「트랙 A 는 네 개, 트랙 B 는 다섯 개」 is right (`docs/auto/RUBRIC.md:31` lists four sub-items,
`:44` lists five, and 일정 is in both), and the NH-008 AI-disclosure sentence matches CHARTER §9 word for word.

## Readiness: 8 of 11, ZERO ticked for the NINTH consecutive critic lap

`docs/auto/KCF_READINESS.md` holds at **8 of 11** (R1, R2, R4, R5, R6, R7, R8, R9). The count has stood there
since critic #43 ticked R8 at 2026-09-08T1429Z. I re-read the cause rather than restating it: R12 is the
author's (NH-014); R3 is `blocked(NH-046)`; R11's row WFG-024 is held by CHARTER §14b until R1, R3, R4, R7,
R8 and R9 all tick, and **R3 is the only one of those six unticked**. Both agent-reachable lines are
downstream of **one unanswered question**, NH-046, which has carried the loop's recommendation unchanged for
five laps. No fourteenth question is filed, because filing one would be the loop asking itself.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c as this routine's
prompt states it, NH-036 A; ⚠ a search for `14c` in `docs/auto/CHARTER.md` still answers **0** at this head,
and NH-036, NH-038 and NH-051 are all still `open`).** It covers **`README.md:210-282`**, the Round-4
fair-opponent block, whose bounds I re-measured at this head (「### 1.」 at **210**, 「### 2.」 at **283**),
unchanged from critics #49, #50 and #51. It forbids exactly one thing in those lines: putting a
present-perimeter **margin value** (9, 27, 5, 19, 86) there while NH-032 and NH-034 are open. Both re-read at
`NEEDS_HUMAN.md:1391` and `:1574`: both still `open`, both due 2026-09-08, so **one day past** (critic #51
wrote 「two days」, which the calendar does not support). A scan of 210-282 finds no margin value there today.
**It expires at critic #53 unless that lap re-states it after re-reading them.** It freezes no file and no
question, and the edit it permits is named so nobody has to guess: **WFG-214's rewording of
`README.md:266-267` is inside these lines and is allowed**, because 「완벽한 예보」 is not a margin value.
