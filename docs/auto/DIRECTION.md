# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. **Rewritten 2026-09-06T1817Z by the research lap** (first research run of the sprint cadence); **direction re-checked 2026-09-06T2317Z by critic #30, no row moved, reorder budget unspent.** Critic #29's note is in `docs/auto/reports/2026-09-06T2015Z-critic.md`.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*No existing row moved this lap. Three new rows enter (**WFG-142, WFG-143, WFG-144**) and all three enter the **P1** block at the end — no P0 row moved, and no row moved below a row of higher priority. The research lap's own answer to 「is the next todo row still the highest-leverage one」 is **yes**, and its finding is that the highest-leverage thing it could do for the queue was not to add to the front of it.*

1. **WFG-148 (P0, twenty minutes) — the same bullet WFG-138 just repaired carries the first of the manuscript's TWO binding caveats and not the second. Critic #30's one `fix-before-next-row` item.** ✅ **WFG-138 is `done(20260906T2117Z)` and both of its halves shipped.** What remains is `paper/manuscript.md:506`: 「Two caveats bind the whole comparison. The forecast-aware arm plans on the same hazard field it is graded against, so whatever it is worth ... is what a *noiseless* forecast is worth.」 That is absent from `README.md` entirely, it binds the 42 for the same reason it binds the 91, and `tests/test_future_aware_attribution.py:135` is green on it because `_is_caveated` accepts one CONTROL spelling and asks nothing else. One clause, additive, no number moves, and **do not touch `docs/auto/JUDGE_QA.md`** (Q36 already carries the sentence; a fifth drift buys nothing). ⚠ The 「Headline result」 bullet, **not** the opening paragraph about the 2025 fire.
2. **WFG-134 with WFG-130 and WFG-140 in one lap (P0) — the booth kit, and the lap that clears row 1 takes this one in the same lap.** The manifest's `JUDGE_QA.md` hash has now drifted **four** times (`5ac45ea810…` against a recorded `2c8451211e…`), and this fourth drift is the first that makes the printed pages **worse rather than older**: the 17 printed Q&A pages hold Q19 without the caveat the repository has since made mandatory. **WFG-140 is the freshness gate and must go red on today's tree before the rebuild makes it green.** R7 and R9 wait on this and nothing else does; the seventh consecutive critic lap has read 4 of 11.
3. **WFG-139 (P0, one lap) — the test suite reaches the network and the clean-clone claim is false.** `tests/test_spread_warmup.py:156` downloads a 25 MB SRTM tile on a clone with no `data/raw/`; CHARTER §4b forbids it in those words and `JUDGE_QA.md` Q28 cites the file that promises 「No network」. Six terrain tests have never run in CI, and this is the whole of the cold/warm `62 / 56` skip gap, demonstrated cleanly across critic #30's cold `1616 / 62` and the 2154Z lap's warm `1622 / 56` on a tree differing only in prose.

Then **WFG-128**, **WFG-129**, WFG-117 (b), WFG-007's human half, WFG-110 (the **only** thing holding R1), WFG-124 (`blocked(NH-032)`), WFG-104, WFG-106, WFG-127, WFG-135, **WFG-142**, **WFG-143**, **WFG-144**, WFG-125, WFG-122, WFG-121 (c), WFG-036 v2, WFG-101, WFG-010, WFG-096, WFG-026 (the other half of R7), WFG-024 when its blockers clear, and only then the infra rows — **WFG-119**, WFG-131, WFG-132, WFG-137, WFG-141 — which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

**Of the three new rows, the one with a claim on promotion is WFG-144** (the Q&A card for 「산림청·경기도가 이미 산불확산예측을 하고 있는데요」 — a judge-facing question with no answer in the bank). It is filed P1 anyway, for two reasons: NH-038 says the front of the queue is already starving, and the card must land **after** the printables rebuild or the 17 pages go stale a fourth time. If the author promotes one row from this lap, it is that one.

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
- ⚠ **Do not report a pass/skip count without saying cold or warm.** `1599 / 62` cold and `1605 / 56` warm are the same commit (WFG-139).

## Critic's last direction note

**2026-09-06T2317Z, critic #30. Critic #29's two falsifiable tests both came back in the dev
lap's favour, and the one thing I found is the other half of the sentence they were about.**

Verified rather than read: `gates.py --mode full` **ALL GREEN** at `524f13c`, exit 0 (`1616
passed, 62 skipped, 1 xfailed`, **cold**, 350.4 s), `--assert-head` exits 0, and the `auto-gates`
runs **165 to 184** on `auto/dev` are **18 `success` and 2 `cancelled`** with **no `failure`** and
run 184 at this head `success`, so no gate finding and no CHARTER §4b finding. Every push in the
window carried a report; every **dev** report carries `Reviewed by:` (the research report still
does not, WFG-147). No author reply waits on either channel: 30 Gmail threads, all the loop's own
`SENT` reports, and PR #31 has no comments. Clone unshallowed before any measurement
(`is-shallow-repository` = `false`, 508 commits).

**Critic #29's tests, answered.** (1) `README.md:22-33` is repaired, so the finding is **not**
about the dev lap's step 3. (2) The widened row **did** travel: one lap closed both surfaces, so
「one row per surface」 is falsified and the unit stays the claim.

**No row moved and the reorder budget is unspent.** WFG-138 closed, so the first `todo` row in
table order is **WFG-134**, which is this page's row 2 and the 2154Z lap's own stated next row.
The page and the table already agree; a reorder would be motion without a reason. WFG-148 enters
at position 1 as this lap's one item, which is not a reorder.

**The root objection is that a gate certifying 「this sentence is caveated」 is only as wide as its
list of caveats, and the loop wrote that list from the one defect in front of it.**
`tests/test_future_aware_attribution.py:135` accepts one CONTROL spelling and asks nothing else,
so the README bullet is green under the gate built for it while the second of the manuscript's own
two binding caveats is missing from it. The cheapest test is one line and it is WFG-148's half
(b): add an ORACLE family, require both on README and the manuscript, and watch it go **red** at
this head.

**KCF_READINESS: zero lines ticked in the last 24 h, 4 of 11, a SEVENTH consecutive critic lap,
and this time the rule fires**, because unlike critic #29's window this one contained a dev lap.
Five of the last six dev laps built a critic's `fix-before-next-row` item, each one a correction
to a document the loop wrote, each one worth doing, and the checklist that defines 「the product is
ready」 has not moved since 2026-09-05. ⚠ **And this lap spends its item on another document
correction**, which is the pattern itself; I file it anyway because it is the README opening and
twenty minutes, and I have written into the item that the same lap must then take WFG-134. The
seventh data point went to **NH-038**, which asks the author this exact question, because the rule
that produces the pattern is theirs.

**The falsifiable test for critic #31.** (1) If the next dev lap clears WFG-148 and does **not**
also claim WFG-134 in the same lap, then 「clear the item, then take the next row」 does not fit in
one lap and the correct fix is to the cadence, not to the row. (2) If WFG-134 ships without
WFG-140 going red on the pre-rebuild tree first, the freshness gate is green by construction and
the drift series will reach five.

## The research lap's note (2026-09-06T1817Z)

**The blind spot was not in the literature, it was in the landscape.** Two days is not a literature, and the four new papers found this run change no number here. What changed is that plain Korean search turned up two operational Korean wildfire-**spread** systems — NIFoS's console and 경기도's G-DAPS — that no sweep had ever looked for, and that the Q&A bank has no card for. The differentiator is the output object, never accuracy. New note: `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`. Full run: `docs/auto/research/WEEKLY_2026-W36.md`; parked ideas with their objections: `IDEAS_PARKED.md`; venue status: `IEEE_PLAN.md`. Two scan channels failed and it is recorded rather than hidden — Semantic Scholar returned **429** to this sandbox on every attempt, and the Scholar Gateway MCP needs an OAuth the author must grant.

*(Critic #27's note is in `docs/auto/reports/2026-09-06T1414Z-critic.md`; #26's in the 1112Z report, #25's in the 0816Z. This page stays one screen, which is why older notes live in the reports.)*
