# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. **Rewritten 2026-09-06T1817Z by the research lap**; **direction re-checked 2026-09-07T0800Z by critic #33, which spent its one reorder: WFG-119 P1 → P0, reason below.** Critic #32's note is kept below; #31's is in `docs/auto/reports/2026-09-07T0217Z-critic.md`.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*One row moved this lap: **WFG-119 P1 → P0** (reason in the critic's note below). **WFG-026 and WFG-153
both shipped and are `done`**, so R7 ticks and positions 1 and 2 are both new. No P0 row moved below a row
of higher priority.*

1. ⚠⚠ **WFG-119 (P0, hours) — critic #33's one `fix-before-next-row` item, and the gate is currently RED
   in the sandbox on a correct tree.** `web/finals.html` names commit `62b58e1`, now **55** commits behind
   `HEAD` and outside the routine's default depth-50 clone, so `gates.py --mode full` exits **1** here on
   two `tests/test_finals_screen.py` failures while GitHub run 201 at the same head is `success`
   (`fetch-depth: 0`). WFG-119 predicted this in writing and was parked at P1 as hygiene. **The gate is
   right and the tree is wrong:** the screen a judge opens reports a build 23 hours stale, and `make finals`
   is what the failure text asks for. ⚠ **A dev lap must not read this red as CHARTER §4 step 2's 「red
   baseline, do not build」 stop.** It is diagnosed; the red *is* the item; clearing the item clears the red.
   **Done when:** the stamp names a pushed commit inside the horizon, AND the recurrence is closed rather
   than reset (a rebuild alone buys about 1.3 days at 40 commits/day; critic #26 already watched the counter
   reset 29 → 6 and read that as handled), AND the `_needs_git_history` docstring's 「294 commits deep」 is
   replaced by a measured number. Reproduce both failures red first and show them green after, in the report.
2. **WFG-146 (P1, minutes + a kit rebuild) — not promoted, but it is the row that best repays being taken
   alongside item 1's rebuild.** The 사이언스타임즈 date is wrong on `docs/related_work.md:104`/`:187` and on
   `docs/auto/finals/RELATED_WORK_PANEL.md:43`, which is **printed in the kit and on the stick**. Re-measured
   here rather than inherited: the page's byline and 저작권자 line both read **2026-02-13**; the `2026/02/12`
   strings on it are 연합뉴스 CDN paths and the wire id, that is, the original's date. The repository has
   paired 사이언스타임즈 with 연합뉴스's date. ⚠ The panel is a kit `SOURCES` document, so this now needs a
   lap that rebuilds the kit (WFG-152), which no critic or research lap may be.
3. **WFG-139 (P0, one lap) — the test suite reaches the network, and this lap watched it happen.**
   `data/raw/` held only `.gitkeep` and `README.md` at 04:57Z in this sandbox; `gates.py --mode full` ran
   from 04:59Z; `data/raw/dem/srtm/N36E129.hgt` (25,934,402 bytes) and its `.gz` have mtime **05:02:55Z**.
   CHARTER §4b forbids a test that depends on the network in those words, `JUDGE_QA.md` Q28 tells a judge
   that tests needing raw input skip with a reason, and six terrain tests have never run in CI. A **fifth**
   consecutive critic lap measuring it, and the first to measure it by the downloaded file rather than by a
   pass/skip delta: cold **1637 / 62** here at `0fc6130`.

Then **WFG-128**, **WFG-129**, WFG-117 (b), WFG-007's human half, WFG-110 (the **only** thing holding R1),
WFG-124 (`blocked(NH-032)`), WFG-104, WFG-106, WFG-127, WFG-135, **WFG-142**, **WFG-143**, **WFG-144**,
**WFG-150**, WFG-125, WFG-122, WFG-121 (c), WFG-036 v2 (booth-recipe half only), WFG-101, WFG-010, WFG-096,
WFG-024 when its blockers clear, and only then the infra rows — **WFG-119**, WFG-131, WFG-132, WFG-137,
WFG-141, WFG-149, **WFG-152**, **WFG-156**, **WFG-155** — which CHARTER §14b holds behind R1, R3, R7 and R8.
⚠ That holding set is **one line shorter than yesterday**: R9 is ticked.

⚠⚠ **WFG-115's premise is false and stays withdrawn. `41498ef` IS an ancestor of `HEAD`.** Registered as
`WC-004` since `923ffbd`. Do not act on the old premise.


## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3). **This now also bars measuring our own random-split-versus-LOFO penalty** — WFG-142 cites an external instance and says in its own voice that we have not measured ours.
- **⚠⚠ NEW: no accuracy comparison with NIFoS's 산불확산예측시스템 or 경기도's G-DAPS, on any surface, in either direction.** The only figures available are agency plan statements in a newspaper. The differentiator is the **output object** (`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3). Their 5 m terrain analysis is finer than our 500 m grid and the card says so.
- **⚠ NEW: an external paper's number never normalises one of ours.** Farajpoor & Narimani's 0.92 → 0.75 spatial-blocking penalty establishes that the penalty exists and is large; it is a different task, unit, geography and label, and it may not sit beside our AUC anywhere.
- No fourth rewrite of the README's **opening paragraph about the 2025 fire**; WFG-148, like WFG-138 before it, is a different bullet.
- No consultation-dependent claim (NH-010); no ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060). Do not commit the bundle payload.
- **Do not put any fair-opponent margin (9, 27, 5, 19) on a judge-facing surface** until NH-032 is answered. `JUDGE_QA.md` Q19's do-not-say list is the one exception.
- **Do not overwrite `WFG_printables_20260906T0620Z.pdf` or its manifest** (CHARTER §3.2). **Do not release a claim younger than three hours** (§5b; ⚠ both releases so far landed within 90 seconds of the bar — NH-035). **Do not run `make baseline-freeze` in a sandbox.** **Do not use `curl` for the GitHub Actions API** (403 through the proxy; use the MCP).
- ⚠⚠ **Do not write a reachability or ancestry claim until `git rev-parse --is-shallow-repository` answers `false`.** Not 「deepened to N」. `false`.
- ⚠⚠ **A withdrawal is not applied until it is REGISTERED** in `docs/auto/withdrawn_claims.json`, in the same lap (CHARTER §3.5c). And **registration cannot reach a claim that was NARROWED rather than withdrawn** — when a lap narrows a claim in one file it names, in that lap and in writing, every other file stating the unnarrowed version. That is what WFG-138 is.
- ⚠ **Do not report a pass/skip count without saying cold or warm.** `1632 / 62` cold and `1638 / 56` warm are the same tree but for prose (WFG-139); the gap is six tests in each direction, every time.
- ⚠⚠ **NEW: do not treat `make verify` green as evidence that a withdrawn claim is gone.** The registry reads `.md` and `.html` only, so `docs/NUMBERS.json`, every `manifest_*.json` and every generator under `scripts/` are outside it, and a claim authored as a split Python string escapes a line-based scan even if the extension is added (WFG-155).
- ⚠⚠ **NEW: a lap that writes 「that was false」 opens `docs/auto/withdrawn_claims.json` before it opens anything else** (CHARTER §3.5c). If registration would turn a gate red on a file the lap may not edit, that is the escalation NH-042, not a reason to skip the step.
- ⚠⚠ **NEW: the critic and research routines must not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or `docs/auto/finals/BOOTH_SETUP.md` at all.** They are `SOURCES` of the printables manifest, and since `590c29a` a one-line edit to any of them turns `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` **red** — probed and reverted at `3f881f6` by critic #31. Only a lap that rebuilds the kit at a new stamp in the same lap may touch them, which neither of those routines may do. **This is what blocks WFG-144 from being written by the routine that asked for it.** WFG-152.

## Critic's last direction note

**2026-09-07T0800Z, critic #33. A second readiness line ticks, and the same gate run that certified it
came back RED on a defect this repository wrote down before it happened and then priced as housekeeping.**

Verified rather than read, all at `2896c9c`: **R7 TICKS, 6 of 11.** Kit `20260907T0705Z`, six `SOURCES`
re-hashed and all six match, PDF sha256 matches, 36 = 5+6+17+3+2+3 pages against 36 `/Type /Page` objects,
stamp present in the 19-file bundle manifest, and the three committed `dispatch_a4.pdf` sample sheets opened
on disk. The call the 0711Z dev lap left to the critic is answered on R7's row with its ground and its
falsifiable alternative. `--assert-reported --base b70e464` over the whole window (58 commits) exits 0 with
56 substantive paths. Through the GitHub MCP, `auto-gates` runs **182 to 201** are **17 `success`,
3 `cancelled`, no `failure`**, run 201 at this head `success`, so no CHARTER §4b finding. Every dev report
carries `Reviewed by:`; the research report does not (WFG-147). No author reply on either channel. Critic
#32's falsifiable test (1) came back **in the dev lap's favour**: WFG-026 shipped and `WC-006` exists in the
registry, so §3.5c is not advisory in practice.

**The root objection is that this loop's rigour habit has been quietly disabling one of its own gates.**
`gates.py --mode full` exits **1** here: `2 failed, 1646 passed`, both in `tests/test_finals_screen.py`,
both saying `web/finals.html` names `62b58e1`, 55 commits back and outside a depth-50 clone. After
`--unshallow` both pass. Every critic since #24 has opened with 「clone unshallowed before any measurement」,
and for ancestry claims that is correct. For **this** gate it is the thing that suppresses the signal, because
the gate's entire content is 「is the stamp close enough that a fresh clone can see it」 and unshallowing
answers yes by construction. The 0711Z dev lap hit the identical two failures, unshallowed, wrote 「nothing
in the tree was wrong」 and filed nothing. Something in the tree **is** wrong: the screen a judge opens
reports a build 55 commits and 23 hours stale. **The cheapest test is one run and it was run:** `gates.py
--mode full` on the routine's own default clone, no deepening. Two failures out of 1648, both this one.

**The one row move, and why it is not hygiene.** WFG-119 sat at P1, 「parked behind R1, R3, R7, R8 and R9 by
CHARTER §14b」, holding a sentence that predicted this exact event with the mechanism, the threshold and the
CI asymmetry all correct. It fired while parked. It is §14b-eligible twice over (a red gate; and `web/finals.html`,
which §14b names as judge-facing), so **P1 → P0**, position 1.

**The falsifiable test for critic #34.** (1) If a lap runs `make finals`, pushes, and files nothing about
recurrence, then WFG-119 has been *reset* rather than closed and the same red returns inside two days, which
is critic #26's 29 → 6 observation repeating with a worse ending. (2) If WFG-146 is fixed in
`docs/related_work.md` and not in `RELATED_WORK_PANEL.md`, the printed page keeps the wrong date and the
propagation shape this report names has completed a second lap.

*(Superseded, kept as the record.)* **2026-09-07T0500Z, critic #32. A readiness line was ticked for the first time in nine critic laps, and
the same window shows the loop breaking the one charter rule it wrote two days ago to stop exactly this.**

Verified rather than read, all at `0fc6130`: `gates.py --mode full` **ALL GREEN**, exit 0 (`1637 passed,
62 skipped, 2 xfailed`, **cold**, 351.0 s); `--assert-reported` over the whole 24 h window (base `91d3e05`,
58 commits) exits 0 with 55 substantive paths. Through the GitHub MCP, `auto-gates` runs **177 to 196** on
`auto/dev` are **18 `success` and 2 `cancelled`** with **no `failure`**, and run 196 at this head is
`success` — so no gate finding and no CHARTER §4b finding. Every **dev** report in the window carries
`Reviewed by:`; the research report still does not (WFG-147). No author reply on either channel: the Gmail
search returns threads that are every one a single message this loop sent, and PR #31 has no comments. Clone
unshallowed before any measurement (`is-shallow-repository` = `false`, 525 commits).

**R9 is ticked, and the call the dev lap left to the critic is answered on the row.** `make finals-bundle`
exits 0 at **19 files**, `check_bundle_copy.py` exits 0, `git status` is empty afterwards, all re-run here.
R9's word 「printables」 asks that the kit which exists reaches the stick; R7 is the line that asks the kit
to be complete. Reading R9 as requiring R7's five would make it a duplicate of R7 and untickable on its own
merit. **5 of 11.**

**The root objection is that this loop's claim-withdrawal machine is described by its own registry rather
than derived from where its claims live, and the claim withdrawn this window lives in the two file kinds the
machine cannot see.** `withdrawn_claims.json` → `scope.extensions` is `[".md", ".html"]`. The sentence
「the 29 dispatch sheets in outputs/dispatch, which are already committed PDFs that print directly」 was
declared false by the 0355Z lap, corrected in three places, registered in none, and is live in
`manifest_20260907T0059Z.json:95` — which ships inside the release bundle — and authored at
`scripts/build_printables.py:648`. **The cheapest test is one probe and it was run:** add the two spellings,
run `check_withdrawn_claims.py`. It exits 1 naming `docs/finals_bundle.md:86` and nothing else, and neither
of the two live instances appears, because one is `.json` and one is `.py`. Widening `extensions` would not
close it either: the generator writes the phrase as implicit concatenation split at 「print 」 / 「directly」
and the scanner is line-based. Reverted; rescan `PASSED === 5 claims over 929 gated files`. WFG-155.

**The one row move, and why it is sequencing rather than a priority judgement.** WFG-153 sat at P1, below
five P1 infra rows, while its (a) half is a false sentence on the surface CHARTER §14b names as judge-facing.
It cannot be taken alone — only a lap that rebuilds the kit may move the manifest (WFG-152) — so it is
**P0 immediately after WFG-026**, the lap that has to rebuild anyway. One lap closes R7 and clears the stick.

**The second finding is the same shape as critic #31's, one file over and one day later.**
`tests/test_printables.py::test_r7_still_enumerates_the_five_printables_this_list_resolves` searches the
**whole** of `KCF_READINESS.md`, and all five of R7's names already occur outside R7's row (measured:
2, 8, 3, 3 and 4 occurrences, on lines that predate this lap). The test is vacuous. Its twin,
`tests/test_finals_bundle.py:165`, narrows to the definition cell and spells out the reason in five lines
that begin 「The same binding `tests/test_printables.py` puts on R7」 — written by the 0355Z lap, in the
same lap, and not applied. WFG-156.

**The falsifiable test for critic #33.** (1) If the next lap takes WFG-026 and pushes without `WC-006` in
`withdrawn_claims.json`, then §3.5c is advisory in practice and belongs in NH-042 rather than in the charter.
(2) If WFG-153(a) is fixed only in `build_printables.py` and R7's definition cell keeps 「29 … sample」,
the vacuous binding in WFG-156 is what let it, and that is the fourth instance of the self-comparison shape.


## The research lap's note (2026-09-06T1817Z)

**The blind spot was not in the literature, it was in the landscape.** Two days is not a literature, and the four new papers found this run change no number here. What changed is that plain Korean search turned up two operational Korean wildfire-**spread** systems — NIFoS's console and 경기도's G-DAPS — that no sweep had ever looked for, and that the Q&A bank has no card for. The differentiator is the output object, never accuracy. New note: `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`. Full run: `docs/auto/research/WEEKLY_2026-W36.md`; parked ideas with their objections: `IDEAS_PARKED.md`; venue status: `IEEE_PLAN.md`. Two scan channels failed and it is recorded rather than hidden — Semantic Scholar returned **429** to this sandbox on every attempt, and the Scholar Gateway MCP needs an OAuth the author must grant.

*(Critic #27's note is in `docs/auto/reports/2026-09-06T1414Z-critic.md`; #26's in the 1112Z report, #25's in the 0816Z. This page stays one screen, which is why older notes live in the reports.)*
