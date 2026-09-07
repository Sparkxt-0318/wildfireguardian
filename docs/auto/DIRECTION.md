# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. **Rewritten 2026-09-06T1817Z by the research lap** (first research run of the sprint cadence); **direction re-checked 2026-09-07T0206Z by critic #31, which spent its one reorder: WFG-026 P1 → P0, reason below.** Critic #30's note is in `docs/auto/reports/2026-09-06T2317Z-critic.md`.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*One row moved this lap: **WFG-026 P1 → P0** (reason in the critic's note below). No new row is added here; WFG-151 and WFG-152 are filed in the backlog by the same lap. No P0 row moved below a row of higher priority.*

1. **WFG-151 (P0, twenty minutes) — the booth kit shipped and the bundle a judge would be handed does not contain it. Critic #31's one `fix-before-next-row` item.** `release/kcf-finals-2026/MANIFEST.json` lists **17 files** and not one is a printable; `scripts/build_finals_bundle.py:57` `PAYLOAD` names no PDF. The first kit existed at `3e92b69` (09-06 06:51Z) and the bundle manifest was rebuilt **2 h 43 m later** at `1ec1d06` and gained only a `web/finals.html` hash. Nothing went red because `tests/test_finals_bundle.py:41` compares the manifest to the **builder's own plan**, and `:74` — the only place R9's contents are written into code — transcribed four of R9's five names and dropped 「printables」. Add the newest-stamp PDF and its manifest to `PAYLOAD`, then bind R9's **named contents** to the plan in the `R7_ITEMS` shape WFG-130 used, graded **red** before the fix. ⚠ No new committed bytes: the bundle payload is git-ignored.
2. **WFG-026 (P0, one lap) — the sole remaining blocker of R7, promoted for that reason and not on its own merit.** R7 names five printables; three are in the `20260907T0059Z` kit, the 29 dispatch sheets are excused in writing, and the related-work and SFTD059T differentiation panel **is not written**. CHARTER §14b holds five P1 infra rows behind R7 while R7's only blocker sat at P1 itself. The panel should carry the two Korean operational systems (`KOREAN_OPERATIONAL_SYSTEMS.md`, `manuscript.md` §2), which absorbs most of **WFG-144**; WFG-144 keeps the spoken Korean card. ⚠ The lap that writes the panel **rebuilds the kit in the same lap** (WFG-152).
3. **WFG-139 (P0, one lap) — the test suite reaches the network and the clean-clone claim is false.** `tests/test_spread_warmup.py:156` downloads a 25 MB SRTM tile on a clone with no `data/raw/`; CHARTER §4b forbids it in those words and `JUDGE_QA.md` Q28 cites the file that promises 「No network」, which Q40 already has to contradict. Six terrain tests have never run in CI, and this is the whole cold/warm gap: **cold `1632 / 62`** here at `3f881f6` against the same lap's **warm `1638 / 56`**, a fourth consecutive critic lap measuring it.

Then **WFG-128**, **WFG-129**, WFG-117 (b), WFG-007's human half, WFG-110 (the **only** thing holding R1), WFG-124 (`blocked(NH-032)`), WFG-104, WFG-106, WFG-127, WFG-135, **WFG-142**, **WFG-143**, **WFG-144**, **WFG-150**, WFG-125, WFG-122, WFG-121 (c), WFG-036 v2 (booth-recipe half only, now that WFG-151 carries the printables half), WFG-101, WFG-010, WFG-096, WFG-024 when its blockers clear, and only then the infra rows — **WFG-119**, WFG-131, WFG-132, WFG-137, WFG-141, WFG-149, **WFG-152** — which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

⚠⚠ **WFG-115's premise is false and stays withdrawn. `41498ef` IS an ancestor of `HEAD`.** Registered as `WC-004` since `923ffbd`, so `make verify` reads it against 925 gated files. Do not act on the old premise.

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
- ⚠⚠ **NEW: the critic and research routines must not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or `docs/auto/finals/BOOTH_SETUP.md` at all.** They are `SOURCES` of the printables manifest, and since `590c29a` a one-line edit to any of them turns `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` **red** — probed and reverted at `3f881f6` by critic #31. Only a lap that rebuilds the kit at a new stamp in the same lap may touch them, which neither of those routines may do. **This is what blocks WFG-144 from being written by the routine that asked for it.** WFG-152.

## Critic's last direction note

**2026-09-07T0206Z, critic #31. The window's dev lap closed four rows and the readiness
checklist did not move, and for the first time that is not the pattern NH-038 names.**

Verified rather than read: `gates.py --mode full` **ALL GREEN** at `3f881f6`, exit 0 (`1632
passed, 62 skipped, 2 xfailed`, **cold**, 349.5 s); `--assert-head` exits 0; `--assert-reported`
over the whole 24 h window exits 0 (52 substantive paths, all carried by reports). Through the
GitHub MCP, `auto-gates` runs **171 to 190** on `auto/dev` are **18 `success` and 2 `cancelled`**
with **no `failure`**, and run 190 at this head is `success` — so no gate finding and no CHARTER
§4b finding. Every **dev** report in the window carries `Reviewed by:` (the research report still
does not, WFG-147). No author reply on either channel: 80 Gmail threads, every one a single
message this loop sent, and PR #31 has no comments. Clone unshallowed before any measurement
(`is-shallow-repository` = `false`, 517 commits).

**The one row move, and why it is not a priority judgement.** R7's five printables are now three
in the kit, one excused in writing, and one unwritten — **WFG-026**, which sat at **P1**, below
the five P1 infra rows that CHARTER §14b explicitly holds *behind R7*. A rule that gates infra
work on a readiness line, while that line's only blocker is filed at the same level as the work
being gated, cannot ever release. That is an ordering defect the loop could see, so the reorder is
**WFG-026 P1 → P0**. It also absorbs most of WFG-144, because a differentiation panel that omits
the two systems 산림청 and 경기도 actually run is not a differentiation panel.

**The root objection is that every gate this loop writes compares the artifact to its own
description, and the loop keeps discovering that one directory at a time instead of once.**
Three instances, three consecutive days, one shape: `tests/test_printables.py` read the manifest
against itself until WFG-140 hashed the sources against the tree (fixed yesterday); the reviewer's
`sum(pages_per_source) == pages` found four surfaces carrying wrong numbers under the true
sentence 「re-derived from the manifest rather than retyped」 (fixed yesterday); and
`tests/test_finals_bundle.py:41` compares the committed manifest to `bfb.plan()`, the builder's
own plan, **today**, which is why a bundle that omits a file R9 names has been green through two
rebuilds since that file existed. **The cheapest test is one grep** — every test that compares a
committed manifest to a builder's plan rather than to the tree — and its first hit is WFG-151.

**KCF_READINESS: 4 of 11, zero ticked for an EIGHTH consecutive critic lap, and the rule fires
again — but the diagnosis has changed.** The 01:09Z lap was product work, not a document
correction, and it still ticked nothing, because R7 and R9 are each one small unclaimed piece
short. Both are now filed (WFG-026, WFG-151) and both are P0. The eighth data point still goes to
**NH-038**, because the ordering rule that produced it is the author's and neither a dev nor a
critic lap may change it.

**The falsifiable test for critic #32.** (1) If WFG-151 ships and `MANIFEST.json` gains a
printable **without** a test that goes red when R9's named contents are dropped from the plan, then
the fix was to the omission and not to the shape, and the shape will produce a fourth instance.
(2) If the next lap takes WFG-026 and the kit is **not** rebuilt in the same lap, WFG-152's rule is
needed as a gate and not as a sentence.

## The research lap's note (2026-09-06T1817Z)

**The blind spot was not in the literature, it was in the landscape.** Two days is not a literature, and the four new papers found this run change no number here. What changed is that plain Korean search turned up two operational Korean wildfire-**spread** systems — NIFoS's console and 경기도's G-DAPS — that no sweep had ever looked for, and that the Q&A bank has no card for. The differentiator is the output object, never accuracy. New note: `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`. Full run: `docs/auto/research/WEEKLY_2026-W36.md`; parked ideas with their objections: `IDEAS_PARKED.md`; venue status: `IEEE_PLAN.md`. Two scan channels failed and it is recorded rather than hidden — Semantic Scholar returned **429** to this sandbox on every attempt, and the Scholar Gateway MCP needs an OAuth the author must grant.

*(Critic #27's note is in `docs/auto/reports/2026-09-06T1414Z-critic.md`; #26's in the 1112Z report, #25's in the 0816Z. This page stays one screen, which is why older notes live in the reports.)*
