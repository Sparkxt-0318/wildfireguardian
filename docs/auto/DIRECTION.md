# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #27, 2026-09-06T1400Z.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*No existing row moved this lap. Two new P0 rows enter at positions 1 and 2 and everything else keeps its
order. Both are the same defect on the same file, one window apart: a correction that reached every page the
loop reads and stopped at the page the student reads aloud.*

1. **WFG-133 (P0, minutes) — the Q&A bank scripts the student to say a false sentence to a judge, and the
   last critic lap forbade fixing it.** `docs/auto/JUDGE_QA.md` Q35 is **T1**, the reproducibility question.
   Its ⚠ block tells the student **not** to say the draft's true sentence 「현재 브랜치에서 닿는
   커밋입니다」 and to say instead 「… 지금 브랜치에서 닿지 않습니다」. Measured here on a clone
   **fully unshallowed** (`is-shallow-repository` = `false`, 488 commits): `merge-base --is-ancestor`
   exits **0**, the object is **283** back, `branch --contains` names `auto/dev` and `origin/Main`. The
   block also says the card prints **326**; it prints **383**. Critic #26 withdrew the measurement at 1100Z
   and wrote 「Q35 is correct as written and must not be edited」 into three pages. That is true of Q35's
   **draft answer** and false of the **⚠ block** that overrides it, and it protected the false half for a
   window. **This is critic #27's one `fix-before-next-row` item.** A dated ⚠⚠ correction note with the
   measured table is already on Q35 so nobody rehearses the false block tonight.
2. **WFG-134 (P0, one lap) — the booth PDF is stale against the Q&A bank, by exactly the text this window
   withdrew, and no gate reads for it.** The manifest records `docs/auto/JUDGE_QA.md` at `2c8451211e5f97eb…`;
   the file hashes `af955a30fa500391…`. The other three sources still match. So the paper the student
   physically carries holds the **pre-WFG-117 Q30** (the 「326 · 268」 warning) and Q35's false block.
   `tests/test_printables.py` checks the manifest *has* a hash per source and that the PDF matches its own
   hash; nothing compares a recorded source hash against the tree, which is the one comparison that detects
   a stale printable. CHARTER §3.2: a corrected build gets a new stamp beside the old one.
3. **WFG-130** (P0, minutes, carried from critics #25 and #26) — the booth PDF omits the reconciliation
   sheet and its manifest declares that committed file 「does not exist yet」. R7 names five printables and
   the build's source list overlaps it in **one**. Do it in the same lap as WFG-134: one rebuild pays both.

Then **WFG-128** (P0, `docs/multi_region.md:191` + `README.md:113`), **WFG-129** (P0, one lap: the cheapest
test of the headline 42 of 458, fully specified in `paper/GAPS.md` G7), **WFG-117 (b)** (its judge-facing
half shipped at `fc05320`; what is left is grading this row's own gate against a registry-moving mutation,
which is hygiene and now sits behind the two rows above it), WFG-007's human half, WFG-110 (the **only**
thing holding R1), WFG-124 (`blocked(NH-032)`), WFG-104, WFG-106, WFG-127, WFG-135, WFG-125, WFG-122,
WFG-121 (c), WFG-036 v2, WFG-101, WFG-010 (README Round-4 + abstract → R8), WFG-096, WFG-026 (the other
half of R7), WFG-024 when its blockers clear (R11), and only then the infra rows — **WFG-119**, WFG-131,
WFG-132 among them — which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

⚠⚠ **WFG-115's premise is false and stays withdrawn. `41498ef` IS an ancestor of `HEAD`.** Re-verified
this lap on an **unshallowed** clone, which is the control every earlier lap lacked. Do not act on the old
premise; do not edit the screen's provenance line to "fix" reachability. The row survives at P1, re-scoped
to the real and much smaller defect: the line is stale by construction and mislabelled.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3).
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010); no ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it.
- Do not open another gate-about-the-loop row while a judge-facing surface is wrong (CHARTER §14b).
- **Do not put any fair-opponent margin (9, 27, 5, 19) on a judge-facing surface** until NH-032 is answered.
  `JUDGE_QA.md` Q19's do-not-say list is the one deliberate exception. Settled by critic #23.
- **Do not overwrite `WFG_printables_20260906T0620Z.pdf` or its manifest.** CHARTER §3.2: WFG-134's
  corrected build gets a new stamp and sits beside it.
- **Do not release a claim younger than three hours** (CHARTER §5b, NH-030 option C). ⚠ Both releases this
  rule has ever performed landed within 90 seconds of the bar (**NH-035**, open, MEDIUM).
- **Do not run `make baseline-freeze` in a sandbox.**
- **Do not use `curl` for the GitHub Actions API in a cloud lap.** It returns 403 through the proxy. Read
  runs through the GitHub MCP (WFG-119).
- ⚠⚠ **Do not write a reachability or ancestry claim until `git rev-parse --is-shallow-repository` answers
  `false`.** Not 「deepened to N」. `false`. Five laps published a false finding by deepening to a number
  they chose (50, 170, 250) when the object sat at 283. This lap ran `git fetch --unshallow` and got
  `false`, 488 commits, and only then wrote the sentence.
- ⚠⚠ **New, from this lap: a withdrawal is not applied until it has reached the document a human reads
  aloud.** Correcting `CRITIC_LATEST.md`, `KCF_READINESS.md` and this page is correcting the loop's memory,
  not the product. Grep the judge-facing surfaces (`README.md`, `web/`, `docs/auto/JUDGE_QA.md`,
  `docs/auto/DEMO_SCRIPT_5MIN.md`, `paper/manuscript.md`, the newest printables manifest) for the withdrawn
  string before writing 「withdrawn」 anywhere.

## Critic's last direction note

**2026-09-06T1400Z, critic #27. The window did its one item well, and the correction it did not carry is
the same one twice.**

Verified here rather than read from the reports: `gates.py --mode full` **ALL GREEN** at `dd500e6`
(`1569 passed, 62 skipped`, cold, 304.3 s; **+4 passed** on critic #26), the 25 most recent `auto-gates`
runs on `auto/dev` (numbers 145 to 173) are **22 `success` and 3 `cancelled`** with **no `failure`** — so
there is no gate finding and no CHARTER §4b finding this lap — `--assert-head` and `--assert-reported` both
exit 0, every dev report in the window carries `Reviewed by:`, and no author reply is waiting (the Gmail
search returns only threads this loop sent, each holding one message with no reply; `decisions_seen.json`
unchanged).

**Critic #26's falsifiable test, both branches, answered.** (1) The three ancestry commands were re-run on
an **unshallowed** clone: `is-ancestor` exits 0, the object is **283** back (277 at `b2bdaf0` plus this
window's six commits), `branch --contains` names `auto/dev` and `origin/Main`. The withdrawal stands and
WFG-115 stays at P1. (2) Q30's ⚠⚠ block no longer says 326 · 268 — the item mechanism **did** carry prose,
and it carried it well: the card now names three reason-buckets instead of two, carries no live count at
all, and ships a gate that goes red when the registry grows a bucket the card does not describe. Do not
escalate the mechanism.

**The root objection is that the loop measures whether a correction was *made*, never whether it *arrived*.**
Critic #26 withdrew the `41498ef` finding into `CRITIC_LATEST.md`, `KCF_READINESS.md` R1 and this page, and
in the same breath wrote 「`JUDGE_QA.md` Q35 is correct as written and must not be edited」. Q35's ⚠ block
still carries the withdrawn measurement **and instructs the student to speak it**, so the sentence meant to
protect a correct answer is what shielded the false one. Then the same window's repair of Q30 never reached
the printed kit: the manifest's recorded hash for `JUDGE_QA.md` and the file's hash have diverged, and no
test compares them. **Twice in one window, on the same file, a repair landed in the source and not in the
surface a human meets** — once in prose, once in paper. The cheapest test is a grep, and it is now a rule
above.

**My one `fix-before-next-row` item is WFG-133**, the false ⚠ block on Q35, and lifting critic #26's
「must not be edited」 for that block is part of the item.

**The falsifiable test for critic #28.** (1) If `docs/auto/JUDGE_QA.md` Q35's ⚠ block still tells the
student 「지금 브랜치에서 닿지 않습니다」 at the next critic head, then a `fix-before-next-row` item cannot
survive a *previous critic's* prohibition, and the finding is about how critic laps bind each other, not
about the row. (2) Re-hash the newest printables manifest's four sources against the tree. If any is still
stale, then R7's kit is a snapshot with no freshness gate and WFG-134 is understated: file the gate as P0
rather than as part of the rebuild.

## Critic's previous direction note

**2026-09-06T1100Z, critic #26.** Its finding was the instrument: `41498ef` is an ancestor 277 commits
back, and five critic laps had measured inside a shorter graph. Its one `fix-before-next-row` item was
WFG-117 on Q30; critic #27 confirms it ran and ran well.
*(Full text: `docs/auto/reports/2026-09-06T1112Z-critic.md`; #25's is in the 2026-09-06T0816Z report, #24's
in the 0516Z, #23's in the 0215Z. This page stays one screen, which is why the older notes live in the
reports and not here.)*
