# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. **Rewritten 2026-09-06T1817Z by the research lap** (first research run of the sprint cadence); critic #28's note below is kept in full.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*No existing row moved this lap. Three new rows enter (**WFG-142, WFG-143, WFG-144**) and all three enter the **P1** block at the end — no P0 row moved, and no row moved below a row of higher priority. The research lap's own answer to 「is the next todo row still the highest-leverage one」 is **yes**, and its finding is that the highest-leverage thing it could do for the queue was not to add to the front of it.*

1. **WFG-138 (P0, minutes) — the README asserts what the manuscript disclaims, about the number the project leads with. Critic #28's one `fix-before-next-row` item, still `todo`.** `README.md:22-26` says 42 of 458 origins reach a refuge 「**only** when the router accounts for where the fire **will be**」; the manuscript's Abstract carries the same two numbers and then says the contrast 「does not separate knowing where the fire will be from knowing where it is」, because the baseline is fire-blind (`src/wildfireguardian/routing/evacuation.py:270`). The README is the fourth surface for this claim and the only one nobody repaired. One clause, additive, no number moves. ⚠ The 「Headline result」 bullet, **not** the opening paragraph about the 2025 fire.
2. **WFG-134 with WFG-130 and WFG-140 in one lap (P0) — the booth kit.** The manifest's `JUDGE_QA.md` hash is stale and has drifted twice; the printed 17 pages carry the pre-WFG-117 Q30 and Q35's un-retracted block. **WFG-140 is the freshness gate and must go red on today's tree before the rebuild makes it green.** R7 and R9 both wait on this and nothing else does — the fifth consecutive critic lap has read 4 of 11.
3. **WFG-139 (P0, one lap) — the test suite reaches the network and the clean-clone claim is false.** `tests/test_spread_warmup.py:156` downloads a 25 MB SRTM tile on a clone with no `data/raw/`; CHARTER §4b forbids it in those words and `JUDGE_QA.md` Q28 cites the file that promises 「No network」. Six terrain tests have never run in CI, and this is the whole of the cold/warm `62 / 56` skip gap.

Then **WFG-128**, **WFG-129**, WFG-117 (b), WFG-007's human half, WFG-110 (the **only** thing holding R1), WFG-124 (`blocked(NH-032)`), WFG-104, WFG-106, WFG-127, WFG-135, **WFG-142**, **WFG-143**, **WFG-144**, WFG-125, WFG-122, WFG-121 (c), WFG-036 v2, WFG-101, WFG-010, WFG-096, WFG-026 (the other half of R7), WFG-024 when its blockers clear, and only then the infra rows — **WFG-119**, WFG-131, WFG-132, WFG-137, WFG-141 — which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

**Of the three new rows, the one with a claim on promotion is WFG-144** (the Q&A card for 「산림청·경기도가 이미 산불확산예측을 하고 있는데요」 — a judge-facing question with no answer in the bank). It is filed P1 anyway, for two reasons: NH-038 says the front of the queue is already starving, and the card must land **after** the printables rebuild or the 17 pages go stale a fourth time. If the author promotes one row from this lap, it is that one.

⚠⚠ **WFG-115's premise is false and stays withdrawn. `41498ef` IS an ancestor of `HEAD`.** Registered as `WC-004` since `923ffbd`, so `make verify` reads it against 925 gated files. Do not act on the old premise.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3). **This now also bars measuring our own random-split-versus-LOFO penalty** — WFG-142 cites an external instance and says in its own voice that we have not measured ours.
- **⚠⚠ NEW: no accuracy comparison with NIFoS's 산불확산예측시스템 or 경기도's G-DAPS, on any surface, in either direction.** The only figures available are agency plan statements in a newspaper. The differentiator is the **output object** (`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3). Their 5 m terrain analysis is finer than our 500 m grid and the card says so.
- **⚠ NEW: an external paper's number never normalises one of ours.** Farajpoor & Narimani's 0.92 → 0.75 spatial-blocking penalty establishes that the penalty exists and is large; it is a different task, unit, geography and label, and it may not sit beside our AUC anywhere.
- No fourth rewrite of the README's **opening paragraph about the 2025 fire**; WFG-138 is a different bullet.
- No consultation-dependent claim (NH-010); no ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060). Do not commit the bundle payload.
- **Do not put any fair-opponent margin (9, 27, 5, 19) on a judge-facing surface** until NH-032 is answered. `JUDGE_QA.md` Q19's do-not-say list is the one exception.
- **Do not overwrite `WFG_printables_20260906T0620Z.pdf` or its manifest** (CHARTER §3.2). **Do not release a claim younger than three hours** (§5b; ⚠ both releases so far landed within 90 seconds of the bar — NH-035). **Do not run `make baseline-freeze` in a sandbox.** **Do not use `curl` for the GitHub Actions API** (403 through the proxy; use the MCP).
- ⚠⚠ **Do not write a reachability or ancestry claim until `git rev-parse --is-shallow-repository` answers `false`.** Not 「deepened to N」. `false`.
- ⚠⚠ **A withdrawal is not applied until it is REGISTERED** in `docs/auto/withdrawn_claims.json`, in the same lap (CHARTER §3.5c). And **registration cannot reach a claim that was NARROWED rather than withdrawn** — when a lap narrows a claim in one file it names, in that lap and in writing, every other file stating the unnarrowed version. That is what WFG-138 is.
- ⚠ **Do not report a pass/skip count without saying cold or warm.** `1599 / 62` cold and `1605 / 56` warm are the same commit (WFG-139).

## Critic's last direction note

**2026-09-06T1736Z, critic #28. The window did its one item well and found the mechanism behind it; what I found is that the same shape is on the front page, and that the mechanism which finds these has taken the last three dev laps.**

Verified rather than read: `gates.py --mode full` **ALL GREEN** at `e95fe28` (`1599 passed, 62 skipped`, cold, 288.4 s; **+30 passed** on critic #27's cold `1569 / 62`), the 25 most recent `auto-gates` runs on `auto/dev` are **21 `success` and 4 `cancelled`** with **no `failure`** — so no gate finding and no CHARTER §4b finding — `--assert-head` and `--assert-reported` both exit 0, every dev report in the window carries `Reviewed by:`, and no author reply is waiting.

**The root objection is that the loop's honesty machinery is built for claims it has retracted, and the two worst sentences in this repository today were never retracted — they were narrowed in one file and left standing in another.** `README.md:22-26` and `docs/clean_clone_gates.md:27` are both cases. `WC-004`, the registry and the 925-file sweep all key on a **withdrawn string**, and a claim that was merely qualified has no string to key on. The cheapest test is the one WFG-138 asks for and it costs one clause.

**My one `fix-before-next-row` item is WFG-138.** The second finding of this lap is that the item mechanism itself has taken the last three dev laps (WFG-113, WFG-117, WFG-133) while the booth kit has not moved since `3e92b69` and `KCF_READINESS.md` has read 4 of 11 for five consecutive critic laps. That is **NH-038**, open, with four options, and it is the author's because §14b is the author's steer.

**The falsifiable test for critic #29.** (1) Delete `data/raw/dem/srtm/` and run the full suite with no network. Green at `1599 / 62` means WFG-139 closed properly; red means the fix guarded the wrong test. (2) If `README.md:22-26` still says 「only when the router accounts for where the fire will be」 with no fire-blind caveat at the next critic head, then a `fix-before-next-row` item costing one clause is not cheap enough to survive a window, and the finding is about the dev lap's step 3 rather than about the row.

## The research lap's note (2026-09-06T1817Z)

**The blind spot was not in the literature, it was in the landscape.** Two days is not a literature, and the four new papers found this run change no number here. What changed is that plain Korean search turned up two operational Korean wildfire-**spread** systems — NIFoS's console and 경기도's G-DAPS — that no sweep had ever looked for, and that the Q&A bank has no card for. The differentiator is the output object, never accuracy. New note: `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`. Full run: `docs/auto/research/WEEKLY_2026-W36.md`; parked ideas with their objections: `IDEAS_PARKED.md`; venue status: `IEEE_PLAN.md`. Two scan channels failed and it is recorded rather than hidden — Semantic Scholar returned **429** to this sandbox on every attempt, and the Scholar Gateway MCP needs an OAuth the author must grant.

*(Critic #27's note is in `docs/auto/reports/2026-09-06T1414Z-critic.md`; #26's in the 1112Z report, #25's in the 0816Z. This page stays one screen, which is why older notes live in the reports.)*
