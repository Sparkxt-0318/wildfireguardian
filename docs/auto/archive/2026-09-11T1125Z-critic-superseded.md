> ⚠⚠ **SUPERSEDED, ARCHIVED RATHER THAN DELETED (CHARTER §3.7), AND NEVER PUSHED AS A REPORT OF
> RECORD.** Critic #66 generated this draft at `d67de57`, where **WFG-254 was `in-progress` with only
> its claim commit pushed**. The lap holding WFG-254 pushed `05d3bb3` while this draft was being
> written and closed the row in full, which paid this draft's `fix-before-next-row` item and its
> 제출 자료 pre-registration. Every affected claim was re-measured at the rebased head and the lap's
> report of record is the later `-critic.md` file in `docs/auto/reports/`. It is kept because the
> difference between the two is the record of a critic lap being overtaken by the work it reviewed,
> which is a thing the loop does about once a day and had never written down.

# WildfireGuardian autoloop · critic · 2026-09-11T1125Z

| | |
|---|---|
| when | 2026-09-11 11:25 UTC · 2026-09-11 20:25 KST |
| branch / head | `auto/dev` / `d67de57` |
| kind | critic |
| environment | python 3.11.15 · pins_ok=True · stack_ok=True · Linux-6.18.44-fc-v24-x86_64-with-glibc2.39 |
| backlog | blocked: 10, done: 34, dropped: 1, in-progress: 1, parked: 1, title-derivable: 1, todo: 122 |

## What happened this lap

Critic lap #66. Window `ba76b8c..d67de57` (22 h 15 m; `ba76b8c` is this shallow clone's oldest
resolvable commit, so it is the base rather than a chosen one, and critic #65's base `6d4a60b` no
longer resolves here). Reviewed six finished dev laps, seven critic laps, four paper laps and one
research lap, plus a seventh dev lap that claimed WFG-254 at 0921Z and is still running. **No code,
no data, no figure, no `docs/NUMBERS.json` entry was touched.** Everything below is measured in this
lap's own process and cited by file path.

## Your decisions, applied

**Nothing new arrived, and this is the fifth day.** `docs/auto/decisions_seen.json` records
`"seen": []`; the newest applied decision is **NH-031 of 2026-09-06**; every thread matching
`subject:"WildfireGuardian autoloop"` from your address in the last 14 days carries exactly one
message at the Gmail connector and every one of them is the loop's own send; and **PR #31 returned
an empty comment list** at the GitHub MCP in this lap. `decisions.py parse` was therefore not run,
because there is nothing to parse. **24 decisions are open (23 DECISION + 1 BLOCKER), 2 of them
undated (NH-005, NH-014), plus 5 open FYI. NH-046, NH-049 and NH-051 are past due.** The sprint ends
2026-09-15. This is **WFG-211**, already `todo`, confirmed here and not re-filed.

## The `fix-before-next-row` item: ONE, and it is critic #65's, unpaid

`docs/auto/JUDGE_QA.md:1513` (Q36, tier T0, said from memory to all five judges, page 25 of the
59-page kit) still tells a judge the null circle is placed 「발화점에」, and the ignition point this
project records is **19.20 km** from that circle's centre. Re-measured at this head: the clause is
present, `docs/disc_null.md:221` and `docs/oracle_gap.md:204` carry the same locative, and the kit's
seven sources hash **7 of 7** against the tree, so it is on the paper in the box.

⚠⚠ **What changed in this window is that the ENGLISH half was paid and the KOREAN half was not.**
`paper/manuscript.md:710` now reads 「an equal-area disc centred on the first detections' centroid」
and has retired 「shape and extent」 in favour of 「overlaps」; `paper/figures/F10b_disc_null.png` is
the corrected figure under a new filename with `F10_disc_null.png` kept and annotated, which is
CHARTER §3 rule 2 obeyed exactly. **The manuscript and the booth card now disagree about what this
project claims it is good at, and the card is the half five judges hear.**

⚠ **WFG-254 is `in-progress(20260911T0921Z)` with only its claim commit pushed.** At this head that
claim is 1 h 40 m old, inside CHARTER §5b's three hours, so it is another lap's row and is not
released. Recorded so the next critic can measure its age rather than re-derive it.

## Findings, ranked

### 1. WFG-256 (P0, science, new, table position 3) — the card claims the half of the comparison the artifact declines to attribute

`docs/disc_null.md:225` (the spoken draft) and `docs/auto/JUDGE_QA.md:1513` (Q36, **T0**) both close
on 「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」, and Q36 repeats the attribution as
「모델이 원판을 이긴 것은 모양과 범위이고」. The card tells the student to volunteer it
「심사위원이 캐내기 전에 먼저」.

**The artifact underneath refuses that attribution in its own words.**
`data/processed/disc_null_yeongdeok.json :: what_this_is_not` reads 「The gap between the model's IoU
and the disc's is **joint PLACEMENT-AND-SHAPE skill**, not directional skill alone, because a disc
differs from the model's core both in where its mass sits and in being a circle rather than an
irregular terrain-shaped blob」, and `docs/disc_null.md` §5.1 adds that a circle against an elongated
fire is a weak opponent **by construction**. So the IoU gap is a two-component quantity. The
`direction` block prices one component and it goes against the model
(`dn_yeongdeok_model_to_observed_cells` is larger than the stationary
`dn_yeongdeok_disc_to_observed_cells`), and the card assigns the **entire remainder** to 「모양」.
That is the forbidden single-component move mirrored: the artifact declines to attribute the gap to
direction alone, and the card attributes it to shape alone.

⚠ **Nothing in this repository measures the shape component.** Searched here across `docs/`,
`paper/`, `scripts/` and `src/` for a shape-matched, second-moment, principal-axis or rotated null:
the only hit is `scripts/direction_drivers.py:31`, gradient covariance on a different object.
`run_isotropic_baseline` **is** this disc once the area match removes its rate parameter;
`run_persistence_baseline` is WFG-234; neither separates shape from placement.

⚠ **One thing checked rather than assumed, and it goes the project's way: the headline slice is NOT
cherry-picked.** The seed-removed ratio is stable across the four non-seed slices, the headline slice
is the smallest time gap at 27 min, the choice was fixed in the claim commit before the answer, and
the model's own IoU is slightly **higher** at two other slices than at the headline. Selection is
clean here. Attribution is not.

**The cheapest test, which is why this is a row and not a complaint.** Rotate the model's **own**
predicted core rigidly about the `t = 0` seed centroid through a pre-registered angle sweep and
re-score against the same `obs_stack` slice under the same rule. Shape, area and cell count are the
model's own by construction, so only orientation about the fire's own start varies: the spread of
rotated IoUs is the **shape-controlled** null for placement, and the model's rank within it is the
number the card is missing. Zero free parameters, one committed npz, no refit, no re-acquisition.
Pre-register the interpretation in the claim commit and publish it either way.

### 2. WFG-257 (P1, KCF, new, appended at the end of the table) — the demo pays for every caveat out of its own core

Read from the six committed artifacts in `data/processed/demo_script_pace/` and the allocation table
in `docs/demo_script_pace.md` §3.

| what | at `039a0de` (2026-09-05) | at `pace_20260911T0620Z.json` | change |
|---|---:|---:|---:|
| total spoken syllables, against a fixed 300 s | 1,684 | **1,799** | +115 (+6.8 %) |
| 3막 · 같은 출발지, 두 개의 답 | 75 s | **58 s** | **-23 %** |
| 마무리 · 한계 | 45 s | **64 s** | **+42 %** |
| 마무리 syllables | 328 | **383** | +55 |

⚠⚠ **마무리 is now the longest segment of the five-minute demo** (allocation 35 / 41 / 47 / 58 / 55 /
64); at `039a0de` it was the **shortest**, tied with 1막. And 3막, which `docs/demo_script_pace.md`
itself calls 「이 프로젝트의 전부」, lost 17 of its 75 seconds **without losing a word**: its spoken
text has been 346 syllables since 2026-09-05.

The page records the allocations, the four totals and that the rate is rising; it prices 3막's loss
once, as 「what one rate costs it」. It does **not** say that the transfer is monotone across five
allocations, that the segment losing the time has not lost a word, or that the limits segment is now
the longest thing five judges hear. Every one of the four growth events was a caveat added by a lap
that was right to add it, which is exactly why no single lap could see the total. The row adds no
syllable and removes none; the proportion is a presentation judgement reserved to the author, and a
dated measured note went onto **NH-054**, which asks the identical question about `README.md`'s
TL;DR, rather than opening a twenty-fifth entry.

### 3. WFG-252 confirmed and widened (P1, infra, updated in place, NOT re-filed)

Measured at this head **before any edit**: critic #65 appended **both** of its scorecard rows to the
**Track A** table (lines 235 and 236) and **neither** to the Track B table (which ended at
`5482ba8`, line 167) nor to the series table (which ended at `5482ba8`, line 90). **A reader of the
Track A table therefore sees 구현 및 유용성 fall to 19 and hold at 20 at the same head**, because
Track B's 데이터 수집·분석·해석 cell lands in Track A's 구현 및 유용성 column. Two more defects ride
with it: Track B **연구 목적 reads 18 at `5482ba8` and 19 at `f7ee58d` while that row's own narrative
says 「연구 목적 19 ... all HELD」**, with no published reason, which is what makes the row total 95
rather than 94; and the published delta 「Track B 97 to 95」, repeated in `docs/auto/DIRECTION.md`,
measures against **Track A's** previous 97 where Track B's own previous value is **96**.

No row another lap wrote was edited (CHARTER §3.7). This lap transcribed the missing rows into the
Track B table and the series, annotated as transcriptions, left the misplaced Track A copy where it
is, and scored 연구 목적 itself rather than inheriting the unevidenced point. WFG-252's done-when
gained one clause: the gate must also refuse a detail row whose cell differs from the previous row
for that track when the narrative does not name that criterion as moving. This is loop hygiene and
therefore P1 under CHARTER §14b; it waits.

### 4. Direction: the one §3b row move, spent on WFG-129

**WFG-129 moved from table position 78 to position 2.** Seven direction pages have called it the next
row and it has never been taken; critic #65 measured the cause as 「this page's ordering rather than
the lap's choice」, and the table was indeed 76 rows out of step with the page. CHARTER §14b tells the
dev lap to prefer DIRECTION when the two differ, so the two now agree and the ordering excuse is
gone. The move passes over WFG-255 (critic #65's own new row), WFG-117, and WFG-007 whose remaining
half its own cell marks 「print/laptop: human」. No P0 row sits below a non-P0 row as a result.

⚠ **Critic #65's pre-registration did NOT fire, and saying so is part of the job.** It asked for TWO
dev laps since `f7ee58d` with WFG-129 still `todo`; exactly ONE has claimed, and it is still running.
Re-stated for critic #67 with the same teeth, counting from `d67de57`.

### 5. Readiness: zero lines ticked, for the twenty-third consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** (R1, R2, R4, R5, R6, R7, R8, R9 tick; R3, R11, R12
do not; R10 was withdrawn 2026-09-04). The routine prompt makes two consecutive zeroes a finding
about the loop's direction. It is reported as one and deliberately **not** re-filed, for the reason
critic #52 measured and nothing has changed: the three unticked lines are **one** point of failure.
R12 is yours (NH-014), R3 is `blocked(NH-046)` and no lap may reword a readiness line, and R11's
WFG-024 is held by §14b until R3 ticks. **There is no path from any amount of loop work to a ninth
tick.** This window is not excused by inactivity: it held six finished dev laps and two kit rebuilds.

## Root objection (`hate`, one, against the current headline narrative)

**The narrative is 「our contribution is the output object and its measured limits, and what we are
measurably good at is the fire's shape, not its direction」. The second half has never been measured,
and the project's own artifact says it cannot be read off the only comparison that exists.** Every
lap for a week has been refining how carefully this project states its headline comparison, and this
lap found that the single positive sentence the comparison licenses is the one clause the artifact
explicitly declines to license. The pattern is the one every direction page has named: **the project
reasons about the measurement faster than it checks the measurement.**

**The cheapest test is the rotation null of Finding 1**, and it costs one committed npz and no free
parameters. It is decisive in both directions, which is the property that makes it worth doing before
the freeze rather than after.

## `factchk` on new prose claims about the world in the window

The window's world claims are all in the research lap's output, and they arrive already bounded: the
Bokade et al. record (opened, no metric, unrefereed, Uttarakhand, vehicles), the korea.kr 산림청
briefing for the Ready-Set-Go thresholds (the agency's own page, which upgrades the source class and
changes no figure), the Kangwon National University model (record opened, **no metric read**), and
three Zenodo pyrogeography archives each carrying its own embargo or scope caveat. Three sources the
run could not open are named with their HTTP status and used for nothing. **No new unbounded world
claim entered the repository in this window, and the one wording the run refused to write (the
「위험 구역」 zoning framing) is recorded UNVERIFIED and carried into DIRECTION's do-not list.** Nothing
to withdraw.

## Judge drill

Ten questions were put to the repository. Nine reach a file. The one that does not is 「그 2.2배가
모양을 맞혀서입니까, 원이 아니라서입니까?」, which both the statistician and the ML-reviewer lens ask
in the first minute, and it is **WFG-256**. ⚠ It was filed as a backlog row rather than as a
「근거 없음」 entry in `docs/auto/JUDGE_QA.md`, because NH-049 is open on whether the critic may write
the bank and editing it pays a `make printables` rebuild; critic #65 made the same call.

## Scorecard

**Track B 95 to 93. Track A 96, HELD.** Rows appended to the series table and to both detail tables,
plus the transcription of critic #65's missing rows. Evidence per row is in `docs/auto/SCORECARD.md`.

- **Track B 데이터 수집·분석·해석 19 to 18 (WFG-256).** A second instance in two consecutive windows of
  the same class on the same criterion 「예상 결과에 대한 논리적인 해석 및 결론」, and this one is on
  the T0 card rather than only in docs.
- **Track B 연구 목적 19 to 18.** Not a finding: the **withdrawal of an unevidenced point**. The last
  evidenced value is 18; the 19 appeared in a row whose narrative called the criterion HELD.
- **Track B 설계와 방법론 20, 창의성 19, 제출 자료 18, HELD.** 제출 자료 holds rather than rises
  because critic #65's pre-registered condition was all seven surfaces plus the kit rebuild, and
  **four of seven** were paid, all of them English. It holds rather than falls because the movement
  was real and in the right direction.
- **Track A 96 HELD**, every row. WFG-256's defect is an interpretation defect and Track A has no
  데이터 수집·분석·해석 row; 개발 목적 is a differently worded criterion and keeps its 19 with a
  published reason. Track A's own extra pre-registered clause, the replacement figure under a new
  filename with a correct heading, is **MET**, but the 제출 자료 clause it was conjoined to is not.
- **구현 및 유용성 20, re-earned rather than inherited**, and now with a named downgrade trigger:
  WFG-257. It is re-examined downward at critic #67 if the script grows again without the trade
  recorded.

## Gates and CI, measured here

- `gates.py --mode full` exits **0** on its **first** run: 2097 passed, 65 skipped, 3 xfailed, pytest
  386.5 s. `baseline-verify` is the expected WARN (NH-029).
- `gates.py --assert-reported --base ba76b8c` exits **0** over 68 substantive paths.
- **GitHub `auto-gates` run 369 is `success` at exactly `d67de57`**, and **no run in the 24-hour
  window concluded `failure`**: runs 344, 352 and 368 are `cancelled`, each superseded by the next
  push. CHARTER §4b sets **no finding #1**, for the fifteenth consecutive lap.
- **Every dev report in the window records `Reviewed by:`** (ten checked, all `subagent`).
- ⚠ This clone is SHALLOW at **50** commits and was deliberately **not** deepened, so
  `tests/test_timeline_roles.py:234` **SKIPS** rather than runs and a green critic gate does not
  certify it; GitHub at `fetch-depth: 0` does. **No ancestry or reachability claim is written
  anywhere in this lap.**
- ⚠ This lap did **not** independently re-derive the 19-file release-bundle tally and does not restate
  it; `tests/test_finals_bundle.py` is green inside the full gate run above. The printed kit's seven
  sources were re-hashed here at **7 of 7**.

## What this lap did not do

No code, no test, no data, no figure, no `docs/NUMBERS.json` entry, no `README.md`, no
`docs/auto/JUDGE_QA.md`, no `web/finals.html`. No em-dash was written into any file. No row another
lap wrote was edited. **No new NEEDS_HUMAN entry, deliberately, for the fourth consecutive critic
lap:** both findings are agent-doable and the one author question this lap raised is the one NH-054
already asks, so it went there as a dated measured note instead of becoming a twenty-fifth unanswered
item.

## In plain terms

- **What the judges would see today.** A project whose English paper and whose Korean booth card now
  say different things about what it is good at. Today the paper was corrected to say the honest
  version; the card five judges actually hear still says the fire circle sits at the ignition point,
  which is wrong by 19 km, and it still tells the student to claim 「what we are good at is the fire's
  shape」. That last sentence is the problem I want you to know about: nothing in your project has
  ever measured it, and your own data file says so in its own words.
- **What changed since yesterday.** Six build laps ran and the gates are green on every one of them,
  including GitHub's own clean machine. The paper fixed four of the seven places carrying the wrong
  sentence and drew a corrected figure. The three places that matter most to a judge, including the
  printed booklet, are still waiting on the lap that is running right now.
- **What you should do.** Two things, both small. **One:** reply to even three of the 24 waiting
  decisions. Nothing has arrived for five days, the sprint ends on the 15th, and NH-046, NH-049 and
  NH-051 are past due. **Two:** read the note I added to NH-054. Your five-minute demo has quietly
  grown by 115 syllables in six days, all of it caveats, and every second of that came out of 3막,
  the part your own notes call 「이 프로젝트의 전부」. The limits section is now the longest part of
  your demo. That may be exactly what you want. It is the one thing here that no lap is allowed to
  decide for you.



## Gates

**ALL GREEN** · mode `full` · head `d67de57` · 2026-09-11T11:05:59Z · current at `d67de57`

| step | result | time | last line |
|---|---|---|---|
| verify | PASS | 23.1 s | === make verify: PASSED === |
| baseline-verify | WARN | 0.1 s | make: *** [Makefile:159: baseline-verify] Error 1 |
| snapshot-verify | PASS | 1.7 s | VERIFY: all present snapshots intact (47 local-only/digest-only absent) |
| env-check | PASS | 0.1 s | OK — the environment matches requirements.txt. |
| pytest-full | PASS | 386.5 s | 2097 passed, 65 skipped, 3 xfailed, 52 warnings in 384.73s (0:06:24) |

## Commits since the previous report (748e89f49823b00a1d693819e0fede3216fe1a35..HEAD)

- d67de57 the paper report names the head it ships in, and names the assertion rather than a sha its gate table cannot know
- 5d2d603 the lap report annotates the per-slice radius it quotes, so the gate reads the quotation as one
- c3bd2bb the null circle is named where the measurement put it, and the figure that said otherwise is reissued rather than overwritten
- d4b7bef claim WFG-254 (20260911T0921Z)

## Needs a human (29 open)

- NH-003 [FYI] `Main` is behind the working line by design
- NH-004 [FYI] The sandbox has no API keys, so the loop works from committed snapshots
- NH-005 [DECISION] Building footprints for Yeongdeok (Session 21 blocker)
- NH-014 [DECISION] Run the booth recipe once on the real laptop (after 09-10, before 10-16)
- NH-032 [DECISION] Two laps built your fair-opponent row at the same time and got different answers: 9 and 27 (by 2026-09-08)
- NH-033 [FYI] This lap force-pushed its own parking branch, which CHARTER §3.8 forbids flatly
- NH-034 [DECISION] Your fair-opponent experiment ran, and it cuts the headline from 91 to between 5 and 27 (by 2026-09-08)
- NH-035 [DECISION] The three-hour rule you chose to un-stick a stranded row cannot fire on the three-hour dev grid (by 2026-09-09, one day past; raised to HIGH by critic #55 on a measured third instance)
- NH-036 [DECISION] One critic lap told the next one not to edit a file, and that is what kept a false sentence in front of a judge for a window (by 2026-09-10)
- NH-037 [DECISION] The paper's word proxy now stops it a thousand words before your 25-page rule (by 2026-09-10)
- NH-038 [DECISION] Your "product first" rule has spent the last three dev laps on documents, and the readiness line it was written to protect has not moved in five critic laps (by 2026-09-09)
- NH-039 [DECISION] The national wildfire-spread system's manual is an 18 MB PDF the sandbox could not fetch, and one of you can (by 2026-09-12)
- NH-040 [FYI] A critic lap pushed one commit past a red `--assert-reported`, and it is telling you rather than hiding it
- NH-041 [FYI] This lap sent you an email containing only the word PLACEHOLDER, and could not take it back
- NH-042 [DECISION] Two of your own rules collide whenever a withdrawn claim lives in a frozen artifact, and this week they collided three times (by 2026-09-10)
- NH-043 [DECISION] A gate your loop built this morning will go red about twice a day, and the charter tells the lap that meets it to stop working (by 2026-09-09)
- NH-045 [BLOCKER] The staleness gate has closed `auto/dev` to every routine, and the one routine that met it is the one forbidden to clear it (by 2026-09-08)
- NH-044 [DECISION] The claim the paper just retracted is still live on the page the paper cites for it (by 2026-09-09)
- NH-046 [DECISION] Your product's definition-of-done names a command nothing in this project has ever run (by 2026-09-10)
- NH-048 [DECISION] One of the research routine's three literature channels has been dead for two runs, and a working replacement is already proven (by 2026-09-10)
- NH-049 [DECISION] Your critic routine is told to add judge Q&A cards and your own printing gate makes that impossible for it (by 2026-09-11)
- NH-050 [DECISION] You answered two of these questions two days ago and the loop never heard you, because you answered them on the routine page (by 2026-09-10)
- NH-051 [DECISION] The rule your loop has been obeying for three days is not the option it names, and the difference is why one row has been pushed down five times (by 2026-09-11)
- NH-052 [DECISION] The experiment that measures what your own forecast is worth is now one run away, and it would change what 42 means (by 2026-09-12)
- NH-053 [DECISION] The word your front door uses for 42 stopped being right today, and the loop cannot pick its replacement (by 2026-09-12)
- NH-054 [DECISION] Four fifths of your front door's headline is limits, and no lap is allowed to decide whether that is the project's strength or its biggest presentation risk (by 2026-09-13)
- NH-055 [DECISION] Your front door compares the headline forecast number to a model the same page calls broken, and today the loop measured a second, harsher comparison it is not allowed to put beside it (by 2026-09-13)
- NH-056 [DECISION] A Korean university published a reproducible deep-learning wildfire model four weeks before your finals, and a lap may not decide on its own whether to mention it (by 2026-09-13)
- NH-057 [DECISION] The one thing your project now says it contributes has never once been produced from a real fire, and only your laptop can change that (by 2026-09-13)

---
Generated by `scripts/auto/report.py`. Charter: `docs/auto/CHARTER.md`. Backlog: `docs/auto/BACKLOG.md`.
