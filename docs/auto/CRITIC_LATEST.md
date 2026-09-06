# CRITIC_LATEST — critic #26, 2026-09-06T1100Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `b2bdaf0`. Window: `b70e464..b2bdaf0`, plus the
24 h to 2026-09-05T10:00Z for the gate, CI and report checks.*

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-117 — `docs/auto/JUDGE_QA.md` Q30 warns the student against a screen that is now correct.**

Q30 is **T0**: the student answers it from memory, with no paper, and it is the question about why today's
numbers should be believed. Its ⚠⚠ block says three things, and all three are false at this head:

| the bank says | the truth at `b2bdaf0`, measured here |
|---|---|
| 「화면은 아직 **326 · 268** 을 인쇄합니다」 | `web/finals.html` prints `n_entries` **383**, `n_reproducible` **325** |
| 「화면을 가리키라는 조언은 학생을 낡은 숫자로 데려갑니다」 | the screen and `docs/NUMBERS.json` agree exactly |
| 「서로 다른 수가 셋 있습니다」 | two: the draft's 295 / 261 / 34, and 383 / 325 everywhere else |

`docs/NUMBERS.json` counted in one process this lap: **383** entries, **325** reproducible, **58** not.
WFG-113 closed the screen half at `1ec1d06`; the warning about it did not move, so a wrong warning has
outlived a correct repair. A dated correction note is already on Q30 (critic #26) so nobody rehearses the
stale block — **the row's job is to make the answer itself true and to gate it**, not to re-add a literal
that goes stale on the next lap that registers a key. The done-when is on the row.

## Do NOT do this (withdrawal, and it is the lap's main finding)

⚠⚠ **WFG-115's premise is false. `41498ef` IS an ancestor of `HEAD`.** Verified three ways on a clone
deepened to **300** commits:

    git merge-base --is-ancestor 41498ef HEAD          -> exit 0
    git rev-list HEAD | grep -c 41498efbf0679276c...   -> 1
    git rev-list --count 41498ef..HEAD                 -> 277
    git branch -a --contains 41498ef                   -> auto/dev, origin/auto/dev, origin/Main, ...

The object sits **277** commits back. Critic #20 raised the row in the sandbox's default **depth-50** clone;
critic #21 deepened by 120 and re-confirmed; critic #24 deepened to **250** and wrote 「so the shallow
boundary is not the confounder」. 250 < 277, so it still was. Five critic laps published it as measured fact.

So, for the next lap:

- **Do not edit `web/finals.html` or `scripts/finals.template.html` to "fix" reachability.** Nothing on the
  judged screen is wrong about it.
- **Do not edit `docs/auto/JUDGE_QA.md` Q35.** It is correct as written.
- WFG-115 survives at **P1**, re-scoped to the real and much smaller defect: the provenance line is stale by
  construction and mislabelled (the registry held **153** entries at that commit; the card prints **383**).
- **New standing rule, now on `docs/auto/DIRECTION.md`:** write no reachability or ancestry claim until
  `git rev-parse --is-shallow-repository` answers `false`, and record the depth beside the claim. Deepening
  by a number you chose is not a control.

## What this lap verified rather than read

- `gates.py --mode full` **ALL GREEN** at `b2bdaf0`: `1565 passed, 62 skipped`, cold, 199.1 s
  (critic #25: `1562 / 62` — **+3 passed**, skips unchanged). `verify`, `snapshot-verify`, `env-check` PASS;
  `baseline-verify` WARN is CHARTER §3d information.
- **No red CI run behind a green report, so no CHARTER §4b finding.** Read through the GitHub MCP (the
  routine's `curl` returns 403, WFG-119): `auto-gates` runs **140 to 168** on `auto/dev` are **22 `success`
  and 3 `cancelled`** (`ef61e9b`, `9ebf5a5`, `785ba13`, each superseded by a green push). Run 168 at
  `b2bdaf0`, this head, is `success`. **Zero `failure`.**
- `--assert-reported` exits 0 across the window; every dev, paper and critic report of the last 24 h carries
  `Reviewed by:` (the four without it are `manual`, the author's laptop).
- **Critic #25's falsifiable test, branch (1): answered.** The screen prints 383 / 325, the stamp moved to
  `62b58e1` (**6** commits behind `HEAD`, was 29), and WFG-119's ten-hour clock is reset.
- **No author decision is waiting.** The Gmail search returns only threads this loop sent, each holding one
  message with no reply on it; `docs/auto/decisions_seen.json` is unchanged; PR #31 carries no comment in the
  `NH-###:` form.

## Filed this lap

| id | what | where it sits |
|---|---|---|
| **WFG-117** | re-scoped and **moved to position 2** (this lap's one row move); the Q30 repair | `fix-before-next-row` |
| **WFG-115** | premise withdrawn, **P0 -> P1**, re-scoped to staleness and mislabelling | not scheduled |
| **WFG-119** | strengthened: the predicted failure already happened five times; done-when now requires an unshallowed clone before any ancestry claim | P1, held behind R1/R3/R7/R8/R9 |
| **WFG-132** | new: `2026-09-06T1000Z-dev.md` and its email name `a464d1a` and `a68c2d0`, neither of which is a valid object anywhere | P1, loop hygiene, held by CHARTER §14b |

No new NEEDS_HUMAN entry. Every finding above is agent-doable and none of them moves a committed number.
