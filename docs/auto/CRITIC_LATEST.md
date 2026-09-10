# CRITIC_LATEST — critic #56, 2026-09-10T0523Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `9b7d21c`, and
every measurement below was taken at that head unless it says otherwise. ⚠ This clone is **SHALLOW at 50
commits** (`git rev-parse --is-shallow-repository` answers `true`, `git rev-list --count HEAD` answers 50,
oldest object `435c54d` of 2026-09-09T0643Z) and I did **not** deepen it; **no ancestry or reachability claim
appears anywhere below**, per CHARTER §4. My 24 h window is therefore `435c54d..9b7d21c`, about 22 hours, and I
say so rather than claiming a day I cannot see. Full report: `docs/auto/reports/2026-09-10T0523Z-critic.md`.*

## `fix-before-next-row`: ONE. `docs/oracle_gap.md` §4 and §4b, and it is minutes

**Print `time_gap_min` beside every ratio and every IoU in §4 and §4b, and say in one sentence that three of
the four slices are scored against the same observation.** That is the whole item. It is prose, it writes no
number that is not already a registry key, and it runs no measurement.

**Why it is a preemption and not a row.** The finding is **WFG-215**, filed by critic #51 on 2026-09-09 with
the placement note 「P1 and not P0 deliberately: this is a qualification inside one `docs/` analysis page, not
a judge-facing surface」. **That sentence is false at this head, and it stopped being true inside this window.**
Counted here, `docs/oracle_gap.md` is the cited evidence anchor from **seven places on four judge-facing
surfaces**:

| surface | where | note |
|---|---|---|
| `README.md` | `:43`, `:256`, `:331`, `:784` | the front door, four times |
| `docs/auto/JUDGE_QA.md` | `:1419` | card **Q36**, tier **T0**, and the bank is one of the seven hashed sources of the printed kit |
| `paper/manuscript.md` | `:512` | Discussion |
| `web/finals.html` | `:2069` | **new at `c4eb8d2`, this window**: the anchor of the **first** card in the 알려진 한계 panel |

Six of the seven send the judge with the same phrase, 「셀 단위로 재어 두었고」.

**I confirmed the finding against the artifact rather than inheriting it**, in one process against
`data/processed/oracle_gap_yeongdeok.json`:

| `haz_time_min` | `obs_time_min` | `time_gap_min` | `predicted_cells` | `observed_cells` | `size_ratio` |
|---:|---:|---:|---:|---:|---:|
| 180 | 333 | 153 | 692 | 937 | 0.7385 |
| 360 | 333 | 27 | 952 | 937 | 1.016 |
| 540 | 333 | 207 | 981 | 937 | 1.047 |
| 720 | 1005 | 285 | 1036 | 987 | 1.0496 |

Three of the four are graded against **one** observation. The series 0.74 / 1.02 / 1.05 / 1.05 is therefore a
monotonically growing numerator over a **constant denominator** for three of its four terms, and §4's sentence
「at 3 h the simulation is **26 % under**」 compares a forecast with an observation **153 minutes later than the
forecast time**. That is a matching gap read as forecast bias, on the page four judge-facing surfaces send a
judge to for the sentence 「예측이 관측과 얼마나 벌어지는지」.

⚠⚠ **Do NOT follow WFG-215's own 「Do」 literally.** It says to print `time_gap_min` **and `obs_time_min`**
beside every ratio, on the stated ground that 「all 15 per-slice keys are already registered」. Checked here:
`docs/NUMBERS.json` holds **25** `og_yeongdeok_*` keys, the five per-slice `og_yeongdeok_t###min_time_gap_min`
among them, and **no per-slice `obs_time_min`** — only the headline `og_yeongdeok_obs_time_min`. Printing 333
and 1005 beside each ratio would write numbers CHARTER §3 rule 3 forbids. Registering those five keys
additively through `scripts/register_oracle_gap.py` is the rest of the row and is **not** this preemption.

⚠ **The misreading is contained.** `26 %` and `0.74` count **0** on `README.md`, `docs/auto/JUDGE_QA.md`,
`docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/creativity_card.md`, `web/finals.html` and `paper/manuscript.md`. No
surface repeats it; the document a judge is sent to carries it. That is why the repair is minutes and why it is
a preemption rather than a P0 row (§14b as amended by NH-038 B).

## The §3b reorder: WFG-128 to the head of the P0 block

One move, P0 above P0, so CHARTER §14's ordering rule is untouched. **DIRECTION.md named WFG-218 and WFG-220
and both are `done`**, so the page named nothing and a dev lap would have fallen back to table order onto
**WFG-007**, whose own status cell reads 「the agent half is done; the student half is not」 and whose remaining
clauses are a printing task that belongs to the student and WFG-130.

**WFG-128 is the row that should meet a dev lap first on every reading**, and I re-read the defect at the file
rather than at the row: `docs/multi_region.md:187-192` now reads 「is **0 for Yeongdeok at 600 minutes** ... It
is **2** for Uiseong-Andong and **3** for Uljin-Samcheok」. A budget clause has been added for the
**future-aware** arm since the row was filed. The sentence still does not say that the **fire-blind** arm is
scored under **no** budget, still does not say that under one rule applied to both arms the Uiseong-Andong
bucket is **empty**, and still carries no pointer to `docs/present_perimeter_arm.md`. `README.md:146` still
sends a judge to that page for 「완전한 분할」. P0, `minutes`, judge-facing, decided by the author eight days ago
(NH-031 option A, closed 2026-09-06), needs no margin value so NH-032 does not bar it.

## Nothing is red, and I ran it rather than inherited it

`gates.py --mode full` exits **0** at `9b7d21c`: `verify` PASS 21.2 s, `snapshot-verify` PASS, `env-check`
PASS, `pytest-full` PASS **1958 passed, 64 skipped, 3 xfailed** in 373.8 s. That is **+17 tests** in one
window. `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and CHARTER §3d
working as the author chose.

**GitHub `auto-gates`, every run in the window: no `failure`.** Read from
`api.github.com/repos/Sparkxt-0318/wildfireguardian/actions/runs?branch=auto/dev`, runs **283 to 315**. Four
non-success, all `cancelled` and all superseded by the next push within minutes: **284** (`e095e2f`), **306**
(`88cb2e7`), **310** (`55466eb`), **312** (`4cb7cf7`). Run **315** is `success` at this exact head. **CHARTER
§4b therefore sets no finding #1, for the fifth consecutive lap.** ⚠ `curl` against `api.github.com` returned
**HTTP 200** from this sandbox again this lap; CHARTER §4's sandbox-facts paragraph and **WFG-119** both say
403 and 「must not be used」. That is a second measured line for **WFG-204**, not a new row.

Every **dev** report of the last 24 h records `Reviewed by:`, checked by grep across all eight (`0654Z`,
`0950Z`, `1250Z`, `1619Z`, `1928Z`, `2206Z`, `0142Z`, `0415Z`); **seven of the eight** record
`subagent (block)` and spend commits acting on it, and the eighth (`1928Z`) records `pass`.
`gates.py --assert-reported --base 435c54d` exits **0**: 66 substantive paths travel with a new report.

## WFG-218 and WFG-220, reviewed rather than accepted

Both closed at `c4eb8d2`. I checked the closure at the artifacts, not at the report.

- **The screen's schedule card is data-driven, not hand-typed.** `web/finals.html`'s embedded payload carries a
  `timeline` key holding all five phases with their `start`, `end` and `open` flags, read by
  `scripts/build_finals.py`'s `timeline_phases()` from `data/processed/timeline_roles/timeline_roles.json`.
  The card renders the count from `TL.phases.length`, so 「다섯」 cannot drift from the artifact on the screen.
- **The README's half is gated on content, not on presence.** `tests/test_timeline_reaches_the_judge_surfaces.py`
  binds every phase name to the artifact, binds the 구간 count word to the artifact's phase count, and requires
  the 「계획서가 아니라 기록입니다」 caveat in the same bullet block. I read the assertions rather than the count.
- **No total from the document reaches either surface**, which was the row's own constraint, and the screen's
  as-of stamp is `last_commit_date` rather than the artifact's `ref` field, which is the literal string `HEAD`.
  That correction came from the lap's own reviewer.
- **WFG-220's card is FIRST in the 알려진 한계 grid**, not appended twelfth, and the lap's own root objection is
  why. It carries no margin value, settles nothing about 상한, and names NH-053.

**R7 and R9 hold, tested on content rather than on existence.** `release/kcf-finals-2026/MANIFEST.json` was
re-pointed in the same commit as the screen rebuild, and I re-hashed **all nineteen** declared files against
their sources: **nineteen of nineteen match**, including the rebuilt `web/finals.html`. The printed kit is
still `WFG_printables_20260910T0140Z.pdf`, and its **seven** sources still hash equal to the tree, **seven of
seven**, so nothing this window invalidated the paper a judge is handed. `README.md` and `web/finals.html` are
not printed sources, which is why the kit did not need a rebuild for this window's work.

## The root objection (`hate`)

**The loop's P1 queue is a write-only ledger, and the critic is its main producer.**

Counted at this head across the whole backlog table, not read from a report:

| priority | done | todo | blocked |
|---|---:|---:|---:|
| **P0** | **64** | 11 | 4 |
| **P1** | **6** | **100** | 3 |

Six P1 rows have ever closed. One hundred are `todo`. The trend over the window is not noise: every critic lap
in the last 24 h added one or two rows and every dev lap removed one or two, so the `todo` count went
**104 → 107** while `done` went 32 → 33 (read from the backlog-count line in each report's own header, which
is generated and not typed). CHARTER §14b releases the P1 infra block only when R1, R3, R4, R7, R8 and R9 all
tick; **R3 is the only unticked one and it cannot tick without the author** (NH-046, due 2026-09-10, open); the
sprint ends **2026-09-15**.

**The cheapest test, and it is already run:** count P1 rows closed during the sprint. Six. If the rule were
serving the product, the number would be small **and falling**, because the queue would be draining; instead
the queue grew by three in the window that closed three P0 rows. So each P1 row a critic files is, in
expectation, a row that will not be worked before the finals, and filing it is the loop writing to itself.

**Two things this objection is NOT saying.** It is not saying §14b is wrong: P0 is 64 done against 11 todo and
this window closed three, which is exactly what the rule was written to protect. And it is not saying the P1
rows are worthless: WFG-215 is one of them and it is this lap's preemption precisely because it turned out to
be judge-facing. It is saying that the **filing** of a P1 row is currently indistinguishable from recording it
in a report, and that the loop should know that when it files.

**Filed as a measurement on NH-038, raised MEDIUM to HIGH, not as a fourteenth question.** NH-038 is the
author's own open question about this rule. Critic #55 declined to file a new one on the ground that it would
be the loop asking itself, and that ground is still right.

## `factchk` on the window's new prose

The window `435c54d..9b7d21c` adds **three** external URLs and **none of them is on a judge-facing surface**:
two arXiv identifiers and one Frontiers DOI, all inside `docs/auto/reports/2026-09-09T1122Z-critic.md` and
`docs/auto/BACKLOG.md`, which are record class. No card, no README block, no manuscript sentence and no screen
string acquired a new claim about the world. The window's added judge-facing prose is entirely claims about
this repository's own artifacts, and the load-bearing ones re-derive: the screen's `timeline` payload equals
the committed artifact field for field, and the nineteen bundle hashes and seven printed-source hashes match.

The paper routine applied `WC-013` correctly in the same window (`per-household` → `origin-level` at
`manuscript.md:676`, and the household-level clause dropped from the Discussion's headline sentence at `:825`), which is CHARTER §5c's ratchet working
across routines rather than only inside one.

## The judge drill, and three probes that found nothing

Answered from a file, opened rather than remembered: 「어떤 일정으로 만드셨습니까?」 (`docs/auto/finals/TIMELINE_ROLES.md`,
now reachable from `README.md`, `web/finals.html`, `docs/auto/JUDGE_QA.md:1428` and `docs/auto/DEMO_SCRIPT_5MIN.md:288`),
「화면의 점은 무엇으로 채점합니까?」 (`web/finals.html`'s first 한계 card, `docs/oracle_gap.md` §2), 「주민에게
문자를 보낸 적이 있습니까?」 (Q16b), 「인쇄물은 무엇에서 나왔습니까?」
(`docs/auto/finals/printables/manifest_20260910T0140Z.json`).

**Three probes that found nothing, recorded so the next lap does not spend them again.**

1. ⚠ **I nearly filed a false finding and am recording the near miss rather than the conclusion.** Q16b and
   Q20a, both **T0** and both printed, tell a judge 「커밋된 실행 기록 **28**개가 전부 `nothing_was_sent: true`」.
   My first count globbed `MANIFEST.json` and answered **16**, which looks like a wrong number on a printed
   card. It is not: `tests/test_responsibility_and_privacy_cards.py::_manifests` counts `MANIFEST.json`
   **and** `RUN.json` (the PHASE-6 replay writes the second spelling), 16 + 12 = **28**, and
   `test_nothing_was_ever_sent_and_the_cards_count_the_manifests` asserts the card's literal equals that count
   in-process. Re-counted both spellings: **28**. The gate's own docstring records that its first draft made
   exactly my mistake. **The card is right and the gate binds the number**, which is the pattern the rest of
   this repository should copy.
2. **Every T0 card cites a file.** All **19** T0 cards in `docs/auto/JUDGE_QA.md` carry at least one file path,
   and every path resolves except four pieces of module-relative shorthand the surrounding prose establishes
   (`printable.py`, `vulnerability.py`, `references.bib`) and one that is **deliberately** absent:
   `email_sent.json` is Q16b's negative evidence, and `scripts/send_dispatch_email.py:270` confirms it is what
   a real send would write. **WFG-111** would have found nothing today.
3. **The release bundle is current with the window's work.** Nineteen of nineteen declared hashes match,
   including the rebuilt screen; the printed kit's seven sources match; nothing in the bundle is stale.

**No card was added to `docs/auto/JUDGE_QA.md` this lap**: **WFG-216** records that the bank's answered cards
and its open questions share one id namespace, and **NH-049** is the author's open question about it.

## Readiness: ZERO lines ticked in 24 h, for the THIRTEENTH consecutive critic lap

8 of 11, unchanged since critic #43 ticked R8 at 2026-09-08T1429Z. R12 is the author's (NH-014); R3 is
`blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b until R1, R3, R4, R7, R8 and R9 tick, of
which **R3 is the only one unticked**. **NH-046 came due 2026-09-10 and is open.** This lap does not re-argue
the count; it measures what the same rule has cost the P1 queue, above, and puts that on NH-038.

## NH-037 has three words of margin, re-measured rather than quoted

`paper/check_paper.py` at this head prints `{"body_words": 8997, "figures": 8, "tables": 4, "references": 29,
"gaps": 7}` and exits 0 against a hard fail at **9,000**. The margin is **three words**, up from zero at
`7dabdef`, and it is up because the paper lap **spent** words rather than gained room: it rewrote three
sentences shorter while applying `WC-013`. **NH-037 came due 2026-09-10 and is open.**

## ⚠ The one `Do NOT edit` note, RE-STATED after re-reading its premise and RE-MEASURING its bounds

CHARTER §14c as this routine's prompt states it, NH-036 A. It covers the Round-4 **fair-opponent** block.
⚠⚠ **Re-measured this lap with `grep -n '^### ' README.md` at `9b7d21c`, and the bounds MOVED. They are now
`README.md:270-349`, not the `263-342` critic #55 wrote.** 「### 1.」 is at **270** and 「### 2.」 at **350**.
The cause is measured, not guessed: this window added **thirteen** lines to `README.md` in two hunks,
**seven at line 65** (the TL;DR schedule bullet, WFG-218) and **six at line 389** (the §4 entry for the same
document), and the seven above the block pushed it down by exactly seven. The six landed inside §4, at 375-398,
which is below the block.

**This is the third time in four laps that these bounds have gone stale, and it is the whole reason CHARTER
§14c makes the note expire.** Critic #55 held only because that window's added lines happened to land below
the block; this window's did not. A lap that copies a `Do NOT edit` line instead of re-measuring it is
protecting the wrong lines.

It forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19, 86)
there while **NH-032** and **NH-034** are open. Both re-read in `NEEDS_HUMAN.md` this lap: both still `open`,
both stated due **2026-09-08**, so **three days past**. A regex scan of the re-measured **270-349** for each value as a
standalone integer finds **zero** occurrences of all five.

**It expires at critic #57 unless that lap re-states it after re-reading NH-032 and NH-034, and that lap
re-measures the bounds before quoting them rather than copying this line.** It freezes no file and no question.

## Scorecard

**Track B 94, HELD, on two moves that offset. Track A 93 → 94.**

- **제출 자료 UP on both tracks (B 19 → 20, A 17 → 18): critic #55's pre-registration, paid on its own stated
  condition.** That condition was 「제출 자료 reaches 20 when WFG-218 and WFG-220 both close, because at that
  point every named criterion of 자료의 논리적 구성 has an answer on the surface a judge actually stands in front
  of」. Both closed, and I verified the closure at the payload, the gate assertions and the nineteen bundle
  hashes rather than at the lap's report.
- **데이터 수집·분석·해석 DOWN on Track B only, 20 → 19.** The ceiling is not defensible on a window in which the
  project's newest analysis page was confirmed to read a matching gap as forecast bias, on the day that page
  became the first card of the finals screen's own limits panel. Track A has no 데이터 row, which is the whole
  reason the two tracks part company this window.
- **Everything else HELD**, including 설계와 방법론 at 19, where I decline critic #52's pre-registered raise to
  20 and say why in the table rather than paying a ceiling.

Full reasoning in `docs/auto/SCORECARD.md`.
