# CRITIC_LATEST — critic #22, 2026-09-05

Window `492364c..4d705df` on `auto/dev` — which grew an author push at 23:12Z while this lap's gates were
running — plus one branch that is not on `auto/dev` and matters more than the diff. Gates re-run here: **ALL GREEN** at `f118bfe` (`1535 passed, 62 skipped`, cold, 306.7 s),
`--assert-head` green, all **70** consecutive push pairs in the 24-hour window pass `--assert-reported`,
`auto-gates` runs **128 to 145** carry no `failure` and run 145 at this head is `success`.

## Read this before you claim anything: WFG-114 was built twice

`c8a3eee` on `auto/dev` reports the forecast's margin over a present-aware planner as **9 of 368**.
A second lap built the same row concurrently, could not rebase (15 conflicting files), and parked green on
**`auto/red/20260905T2248Z`** reporting **27** — and **5** at its sweep's best buffer (0.5 km). Both laps
re-derive the committed 91 node-for-node first; both use the canonical slope/DiGraph arm; both grade with
`_evaluate_path`. They differ only in how the *opponent* is built.

**Consequences for you, in order:**

1. **Do not put 9, 27, 5 or 19 on any judge-facing surface.** That is the parked lap's own constraint and
   this lap adopts it: 「Until you answer, no judge-facing surface should carry either margin.」 It binds
   `JUDGE_QA.md`, `DEMO_SCRIPT_5MIN.md`, `web/`, `paper/` and the printables.
2. **WFG-104 is `blocked(NH-032)` on its margin half.** The last dev lap named it as your next row. Its
   fire-blind half is still writable today (「the baseline is fire-blind, and the fair-opponent arm HAS now
   been run — see `docs/present_perimeter_arm.md`」) with no number in it. If you write it, write only that.
3. **`docs/auto/NEEDS_HUMAN.md` now carries NH-032, NH-033 and NH-034**, imported verbatim from the parked
   branch by this lap, because they existed only there and `decisions.py` writes to `auto/dev`. **NH-031
   was an ID collision** — two laps filed one ninety minutes apart on two branches — and the fair-opponent
   entry is **NH-034** here. Both entries carry a banner. If the author replies `NH-031: …`, read the
   banner before applying it.
4. **Do not delete or force-push `auto/red/20260905T2248Z`.** It is the only copy of the escape analysis
   (10 of 11 forecast-only escapes cross ground that never burns) and of the 265-vs-263 control question.

## fix-before-next-row

**One item, and it sits on the author's own new row: read NH-032 before WFG-121 prints 9 anywhere.**

At `4d705df` the author decided 「Keep the headline, add the fair-opponent line」 and filed **WFG-121** to
put 「9 of 368」 on every judge-facing surface — README opening, `web/finals.html`, the 3막 script,
`JUDGE_QA.md`, the manuscript. That is a judge-facing surface under CHARTER §14b and it is now the top
row, so the next lap will take it.

**The 9 is contested by a second green measurement of the same experiment that says 27**, and 5 at its
sweep's best buffer (see the section above). **The author's instruction stands and nothing here overrules
it** — but their decision was made from a `docs/auto/NEEDS_HUMAN.md` that did not carry NH-032 or NH-034,
because those entries lived only on the parked branch until this critic lap imported them. They have not
declined the question; they were never shown it.

**So do this, in this order:**

1. Do the half of WFG-121 that **no answer changes**, and it is the better half anyway: the buffer finding
   (250 m walks 91 origins into the fire; 2 km leaves 80 unable to finish inside the 600-minute budget; no
   fixed width works and an operator on the day cannot know which one they are on) and the plain statement
   that the 91's control is **fire-blind**. Neither sentence contains a margin.
2. **Do not print 9, 27, 5 or 19** on any judge-facing surface until NH-032 is answered.
3. If the author answers 9, the row proceeds unchanged and nothing was lost.

**WFG-117 stays P0 and is not this lap's item only because the author's row outranks it.** Its bleeding is
stopped: this lap rewrote `JUDGE_QA.md` Q30's ⚠ note to quote no count and point at no screen. What is left
is the durable fix, and the window is its own argument — critic #21's corrected literal (326 / 268) survived
exactly **one lap** before WFG-114 registered 57 keys and the registry became **383 / 325 / 58**, while
`web/finals.html` still prints 326 · 268:

| where | 등록 | 재현 가능 | 재현 불가 |
|---|---:|---:|---:|
| Q30's draft answer | 295 | 261 | 34 |
| Q30's old ⚠ note and `web/finals.html` | 326 | 268 | 58 |
| `docs/NUMBERS.json`, counted here | **383** | **325** | **58** |

The row's done-when is the only fix with a fuse longer than one lap: the bank states a count only if a test
derives it from `docs/NUMBERS.json` at run time, the 16 + 18 decomposition is recounted against 58 or
withdrawn in writing, and `tests/test_judge_qa_bank.py` goes red when a count in the bank disagrees with the
registry — graded both ways. The screen half is **WFG-113**, which now has a live instance.

## After that: WFG-007, and it is not a suggestion this time

`docs/auto/KCF_READINESS.md` reads **4 of 11 for the seventh consecutive critic lap**. R7 and half of R9
are held by **WFG-007** — the printables — which is **P0**, `todo`, and has never been claimed by any lap
in twenty-two critic windows. `docs/auto/finals/` has held two `.md` files and no PDF for seven days.
It is **#1** on `docs/auto/DIRECTION.md` by arithmetic rather than by a move: the row above it finished.

Critic #23's falsifiable test is written on the direction page and is about you: if the next lap ships a
PDF under `docs/auto/finals/`, the seven-lap stall was the queue's tail. If it ships another Q&A or gate
row and R7 is still empty on day eight, the constraint is that no lap will voluntarily take a row whose
output is a file rather than an argument.

## One thing about the loop you should know before you use the release rule

Critic #21 wrote the CHARTER §5 release procedure into this file for a claim it believed dead. The claim
was alive: the 18:17Z lap was on its second rebuild after three reviewer blocks and pushed at 21:02Z. The
release was applied correctly, to a live lap, and that is how one row came to be built twice by two laps
that could not see each other. **A claim marker cannot distinguish working from dead.** ⚠ **The author has since chosen NH-030 option C
with a three-hour window (CHARTER §5b, `4d705df`) — and the duplicate this lap is reporting happened at
3 h 10 m, so the new rule would not have prevented it.** That is not an argument against the rule, which
un-sticks real dead claims; it is the reason the rule needs its companion check. Before releasing any
claim, run `git log --all --grep=<row>` **and** list `auto/red/*` and the remote branches for a
work-in-progress push. Prefer waiting one lap over building a duplicate.

## Everything else this lap filed

- **WFG-124** (P0, `blocked(NH-032)`) — reconcile the two measurements; carry or explicitly decline the
  parked branch's escape analysis and its 265/263 control question. ⚠ **Filed as WFG-121/122/123 and
  renumbered to 124/125/126 in the same lap**, because the author's `4d705df` took 121 and 122 first.
- **WFG-125** (P1) — every margin in the dispute is a **perfect-forecast** bound: the forecast-aware arm
  plans on the field it is graded against (`docs/present_perimeter_arm.md` §5 says so). Re-run with a
  predicted field, or record in writing that none is committed and what would produce one.
- **WFG-126** (P1, the paper routine's paths) — `paper/manuscript.md:386` still carries
  `[GAP: … a present-perimeter baseline …]`, so the manuscript tells a reviewer the experiment has not run.
- **WFG-113 and WFG-117** updated, not duplicated. **No row was moved**; the reorder budget is unspent
  deliberately.

Full report: `docs/auto/reports/2026-09-05T2330Z-critic.md`.
