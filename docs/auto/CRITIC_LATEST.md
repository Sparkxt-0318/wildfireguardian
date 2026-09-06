# CRITIC_LATEST — critic #25, 2026-09-06T0800Z

Window `91d3e05..b70e464` on `auto/dev` — six commits, of which two are substantive (`3e92b69` and
`5f927b0`, the 06:17Z dev lap's WFG-007) and four are a claim, a critic report and two report tails.
Verified here rather than read from the reports:

- `gates.py --mode full` **ALL GREEN** at `b70e464` (`1562 passed, 62 skipped`, cold, 298.9 s;
  `baseline-verify` WARN is the documented NH-029 behaviour). Against critic #24's cold `1545 / 62`:
  **+17 passed**, skips unchanged.
- The twenty most recent `auto-gates` runs on `auto/dev` (numbers 140 to 163, 2026-09-05T20:21Z to
  2026-09-06T07:25Z), read through the GitHub MCP rather than `curl`, are **nineteen `success` and one
  `cancelled`** (`9ebf5a5`, critic #24's own push, superseded four minutes later by `3656bea`, green).
  **No red run sits behind a green report: no gate finding, no CHARTER §4b finding this lap.**
- Every dev report of the last 24 h carries a `Reviewed by:` line, and the 0711Z lap's is the strongest
  one this loop has produced (`block` → fixed → re-verified, on a number no artifact had produced).
- **No author reply is waiting.** The Gmail search for `from:siyeong0318@gmail.com subject:"WildfireGuardian
  autoloop" newer_than:14d` returns thirty threads and every one is a report this loop sent, each holding a
  single message with no reply on it. `docs/auto/decisions_seen.json` is unchanged. Nothing new to apply.

**Critic #24 left a two-branch falsifiable test and branch (1) is what happened: `docs/auto/finals/` holds a
PDF.** WFG-007's agent half is finished, R7 has an object for the first time in nine days, and I am not
writing about queue position again.

## fix-before-next-row

**One item: run WFG-113's two-command repair on the judged screen, before any row.**

    make finals        PYTHON=.auto/venv/bin/python
    make finals-bundle UPDATE=1 PYTHON=.auto/venv/bin/python

Then verify the card against the registry and commit both. Why this and not one of my own findings:

- **It is wrong on the surface five judges look at, and it has been for sixteen windows.**
  `web/finals.html:434` prints `n_entries` **326** and `n_reproducible` **268**. `docs/NUMBERS.json` holds
  **383** and **325** — I counted both in one process rather than reading either from a lap. The screen was
  correct when it was built (`built_utc` 2026-09-05 15:22 UTC, stamp `5f9a3b8`) and went stale six hours
  later when WFG-114 registered 57 `pp_uiseong_*` keys.
- **It needs no decision from anyone.** `scripts/build_finals.py:629-630` derives both counts from the
  registry, so `make finals` re-derives them. WFG-109's closure records this loop running exactly these two
  commands in this sandbox and the only line `make finals` changed was the payload (434).
- **The same two commands travel into the release bundle**, which ships `web/finals.html` among its 17
  files, so the stale pair is on the USB stick as well as on the screen.
- **And it is now on a clock, which is the part that is new today.** WFG-119 predicted the screen's stamp
  would cross the sandbox's shallow boundary 「during 2026-09-06」. Measured at `b70e464`: `5f9a3b8` is
  **29** commits behind `HEAD` (23 at critic #24), the branch took **51** commits in my 24 h, and
  `git rev-parse --is-shallow-repository` is `true` at depth **50**. That is roughly **ten hours** of
  headroom. After it, `test_the_integrity_panel_names_a_commit_this_repository_has` goes RED in every
  sandbox on a screen that is not wrong, CI at `fetch-depth: 0` stays green, and CHARTER §9 spends the
  first lap that hits it on parking rather than building. `make finals` resets that clock as a side effect.

**Do not** try to fix `registry.built_at_commit` (`41498ef`) in the same breath — `make finals` does not
touch it, it comes from `docs/NUMBERS.json` → `built_at_git_commit`, and it is **WFG-115**, a separate row
with a separate done-when. One repair, two commands, then go to the rows below.

## The root objection

**The loop now ships the booth kit, and it assembled the kit from the documents it writes rather than from
the list of what the booth needs.**

`docs/auto/KCF_READINESS.md` **R7** enumerates five printables: 「evidence sheet (A4), **reconciliation
sheet**, related-work and SFTD059T differentiation panel, booth checklist, 29 dispatch sheets sample」.
`scripts/build_printables.py:97-101` lists four sources. **The overlap is one** — the booth checklist. Three
of the four documents in the PDF are not on R7's list, and three of R7's five are not in the PDF.

That alone would be a scope note. What makes it the objection is the sentence the build wrote about the gap.
`docs/auto/finals/printables/manifest_20260906T0620Z.json` → `what_this_does_not_show` says 「The A4 evidence
sheet (WFG-018), the related-work table (WFG-026) and the 29 dispatch sheets ... are NOT in this file; **the
first two do not exist yet**」, and `docs/auto/BACKLOG.md` repeated it in WFG-007's own status cell.

**WFG-018 is `done(20260903T0653Z)` in that same table, three days old.** Its artifact is
`docs/submission_reconciliation.md`: 13,702 bytes of Korean prose, the file `docs/auto/KCF_READINESS.md`
**R6's tick is written on**, whose own fourth line reads 「부스에서 심사위원이 ... 물었을 때 그 자리에서 펴는
종이. **인쇄본은 양면 한 장입니다**」. It was written to be printed, and the booth PDF says it does not exist.

**The cheapest test, and it is one minute with no run:** open `scripts/build_printables.py:97-101` beside
R7's sentence and count the overlap. It returns 1 of 5. Nothing in the repository reads those two lists
together, which is why an otherwise excellent build could declare a committed artifact absent and stay green
through fifteen new tests.

**Filed as WFG-130 (P0, minutes), not as this lap's `fix-before-next-row` item**, because the judged screen
is wrong to a judge today and this one only makes the kit smaller than it should be. Its done-when offers
both repairs — bind the builder to R7, or correct R7 to the documents the booth actually needs — because
either closes the gap and the choice belongs to a lap, not to me.

## What I did not make an item, and where it went instead

**WFG-131 (P1, minutes).** `docs/printables.md` §2 says, in its own voice and correctly, that `brotli` is
declared nowhere: `matplotlib==3.11.1` and `fonttools==4.63.0` are pinned in `requirements.txt` (`:44`,
`:76`), and `brotli` appears in neither that file nor `pyproject.toml` — only at
`scripts/auto/bootstrap.sh:69-70`, 「brotli, which no pin pulls in」. fontTools needs it to open the vendored
`.woff2` faces, so without it `make printables` cannot build a **P0** deliverable and
`tests/test_screen_checks.py`'s woff2 reads fail. This is three days old (`docs/auto/BACKLOG.md:179` records
it as cause 1 of the first cloud lap's 17 red items) and was resolved by teaching `bootstrap.sh` to install
it rather than by declaring it, so `scripts/env_check.py` reports 「the environment matches
requirements.txt」 while the hole is open. P1 and parked behind R1/R3/R7/R8/R9 by CHARTER §14b.

**WFG-127 (i) is cleared — critic #23's item, carried by #24, spent by the 06:17Z lap.** Both surfaces
checked here at `b70e464`: `docs/fair_opponent_line.md` §3 now says the grid 「separates a spike at 1 km from
a plateau an operator could aim at in **neither** direction, and this file asserts neither」, with the
withdrawn wording described rather than quoted so the ban can name its exact spellings; `DEMO_SCRIPT_5MIN.md`
3막 now says 「좋았던 폭 주변이 뾰족한 봉우리인지 넓은 고원인지 이 실험은 가리지 못합니다」. An item
survived one lap unspent and was then spent, which is the answer to the question #24 was holding it open to
ask: the item was fine and the mechanism works.

**WFG-128 and WFG-129 are both still open and neither is a new finding.** `docs/multi_region.md:191` still
reads 「fire-blind route safe, future-aware router cannot finish in time」 and `README.md:113` still sends a
judge there for 「완전한 분할」 (WFG-128); `paper/GAPS.md` G7's test of the headline 42 of 458 is still
unrun (WFG-129). Both were filed at `9ebf5a5`, which landed **57 minutes before** the 06:17Z lap woke, and
that lap took WFG-007 — first in the table, first on `DIRECTION.md`, and the right choice. The rows were
readable and were not read past; that is the queue working, not failing.

## One thing in §3 of `docs/fair_opponent_line.md` to watch, filed as information

The file says at `:99-100` that 「the **counts** are convention-dependent like the margin is, **which is why
§3 quotes none of them**」. §3 quotes two, at `:48-49`: 「at 1 km the committed arm reaches **345** of 368
against the forecast-aware arm's **354**」. Their difference is **9**, which is one of NH-032's two contested
margins and one of the four figures `docs/auto/DIRECTION.md` bans from judge-facing surfaces.

I am **not** filing this as a violation and I am not asking for it to be cut. The gate
(`test_no_contested_margin_reaches_the_booth_script`) is scoped to `DEMO_SCRIPT_5MIN.md`, correctly; this
file is not in the printables PDF, not in the release bundle, and not linked from the README; and the two
numbers are the load-bearing evidence for 「a fixed buffer cannot work is **false**」, which is the honest
half of the section and would be unsupportable without them. What is wrong is only the **self-description**
at `:99-100`, which tells a later reader the section is cleaner than it is — and that sentence is exactly
how a real constraint gets read charitably until it is gone. Corrected wording is one clause: 「§3 quotes
only the pair its own claim rests on, and sends the reader to §4 for the rest」. Left to WFG-121's owner
rather than filed as a row, because it is one clause inside a document another lap is still working.
