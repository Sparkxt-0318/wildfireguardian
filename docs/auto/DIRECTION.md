# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #28, 2026-09-06T1736Z.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*No existing row moved this lap. WFG-133 closed at `923ffbd`. Three new P0 rows enter — one at position 1, two
below the judge-facing block — and everything else keeps its order. The direction check's answer is **yes,
the next todo row is still the highest-leverage one**: R7 and R9 both wait on the booth kit and nothing else
does.*

1. **WFG-138 (P0, minutes) — the README asserts what the manuscript disclaims, about the number the project
   leads with. This is critic #28's one `fix-before-next-row` item.** `README.md:22-26` says 42 of 458 origins
   reach a refuge 「**only** when the router accounts for where the fire **will be**」. `paper/manuscript.md`'s
   Abstract carries the same two numbers and then says the contrast 「does not separate knowing where the fire
   will be from knowing where it is」, because the baseline is fire-blind
   (`src/wildfireguardian/routing/evacuation.py:270`, `docs/real_roads_real_hazard.md:50`). `paper/GAPS.md` G7
   records that the abstract was corrected for exactly this and names the two surfaces already repaired:
   the booth script (**WFG-103**) and the finals template (**WFG-109**). The README is the fourth surface and
   nobody went there. It is the first page a KCF judge, an ISEF reviewer or an IEEE reader opens. One clause,
   additive, no number moves. ⚠ This is the 「Headline result」 bullet, **not** the opening paragraph about the
   2025 fire, which stays untouched.
2. **WFG-134 with WFG-130 and WFG-140 in one lap (P0)** — the booth kit. Re-hashed at `e95fe28`: three of the
   four manifest sources match, `docs/auto/JUDGE_QA.md` does not, and the drift is **larger** than critic #27
   measured (manifest `2c8451211e…`, tree `7d5ac4c9c5…`, was `af955a30fa…`) because the WFG-133 lap edited Q35
   again. The printed 17 pages carry the pre-WFG-117 Q30 **and** Q35's ⚠ block with no retraction on it.
   **WFG-140 is new and is the freshness gate, split out of the two rebuild rows** on critic #27's own
   pre-registered branch: a gate that ships only if a rebuild ships is not a gate, and the rebuild has now
   been displaced three windows. Grade WFG-140 red on today's tree before the rebuild makes it green.
3. **WFG-139 (P0, one lap) — the test suite reaches the network and the clean-clone claim is false.** On a
   clone with no `data/raw/`, `gates.py --mode full` downloaded a 25 MB SRTM tile from
   `elevation-tiles-prod.s3.amazonaws.com` (`tests/test_spread_warmup.py:156`, no skip guard). CHARTER §4b
   forbids it in those words; `docs/clean_clone_gates.md:27` says 「No network」 and `JUDGE_QA.md` Q28 cites
   that file to a judge; six terrain-plausibility tests keyed on that tile have never run in CI. This is the
   whole of the cold/warm `62 / 56` skip gap two dev laps diagnosed wrongly and declined to chase.

Then **WFG-128** (P0, `docs/multi_region.md:191` + `README.md:113`), **WFG-129** (P0, one lap: the cheapest
test of the headline 42 of 458, fully specified in `paper/GAPS.md` G7), **WFG-117 (b)**, WFG-007's human half,
WFG-110 (the **only** thing holding R1), WFG-124 (`blocked(NH-032)`), WFG-104, WFG-106, WFG-127, WFG-135,
WFG-125, WFG-122, WFG-121 (c), WFG-036 v2, WFG-101, WFG-010 (README Round-4 + abstract → R8), WFG-096,
WFG-026 (the other half of R7), WFG-024 when its blockers clear (R11), and only then the infra rows —
**WFG-119**, WFG-131, WFG-132, WFG-137, **WFG-141** among them — which CHARTER §14b holds behind R1, R3, R7,
R8 and R9.

⚠⚠ **WFG-115's premise is false and stays withdrawn. `41498ef` IS an ancestor of `HEAD`.** Registered as
`WC-004` in `docs/auto/withdrawn_claims.json` since `923ffbd`, so `make verify` now reads it against 925
gated files. Do not act on the old premise; do not edit the screen's provenance line to "fix" reachability.
The row survives at P1, re-scoped to the real and much smaller defect: the line is stale by construction and
mislabelled.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3).
- No fourth rewrite of the README's **opening paragraph about the 2025 fire**; disagreements go to
  NEEDS_HUMAN. WFG-138 is a different bullet and is not covered by this.
- No consultation-dependent claim (NH-010); no ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it.
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
  `false`.** Not 「deepened to N」. `false`. This lap ran `git fetch --unshallow`, got `false` and 496
  commits, and only then wrote anything about the graph.
- ⚠⚠ **A withdrawal is not applied until it has been REGISTERED** (CHARTER §3.5c, from `923ffbd`): add it to
  `docs/auto/withdrawn_claims.json` in the same lap and let `check_withdrawn_claims.py` read all 925 files.
  Grepping the judge-facing surfaces by hand is the method that misses one; the registry is the method that
  does not depend on picking.
- ⚠⚠ **New, from this lap: registration does not reach a claim that was NARROWED rather than withdrawn.**
  WFG-138's sentence was never retracted, only qualified in one document, so `WC-004`'s machinery cannot see
  it and neither can any grep for a withdrawn string. When a lap narrows a claim in one file, it names every
  other file that states the unnarrowed version, in that lap, in writing.
- ⚠ **Do not report a pass/skip count without saying whether the sandbox was cold or warm.** `1599 / 62`
  cold and `1605 / 56` warm are the same commit (WFG-139). Critic laps have been quoting cold counts and dev
  laps warm ones, so every 「+N passed」 across the two kinds is contaminated until WFG-139 closes.

## Critic's last direction note

**2026-09-06T1736Z, critic #28. The window did its one item well and found the mechanism behind it; what I
found is that the same shape is on the front page, and that the mechanism which finds these has taken the
last three dev laps.**

Verified here rather than read: `gates.py --mode full` **ALL GREEN** at `e95fe28` (`1599 passed, 62 skipped`,
cold, 288.4 s; **+30 passed** on critic #27's cold `1569 / 62`), the 25 most recent `auto-gates` runs on
`auto/dev` (numbers **#154 to #178**) are **21 `success` and 4 `cancelled`** with **no `failure`** — so there is <!-- forbidden-ok: 154 -->
no gate finding and no CHARTER §4b finding this lap — `--assert-head` and `--assert-reported` both exit 0,
every dev report in the window carries `Reviewed by:`, and no author reply is waiting (the Gmail search
returns a first page of 50 threads, newest first, every one sent by this loop and holding exactly one
message, so no thread carries a reply; `decisions_seen.json` unchanged; PR #31 has no comments).

**Critic #27's falsifiable test, both branches, answered.** (1) Q35's ⚠ block no longer tells the student
「지금 브랜치에서 닿지 않습니다」: the block is retracted in place with a dated ⚠⚠ note and the measured table
above it, and `WC-004` now makes `make verify` red if the sentence reappears anywhere in 925 files. A
`fix-before-next-row` item **can** survive a previous critic's prohibition, and the way it survived was to
stop relying on a lap choosing the right document. (2) The manifest is **still stale**, and staler than when
critic #27 measured it, so the pre-registered branch fires: the freshness gate is filed separately as
**WFG-140**, not as part of the rebuild.

**The root objection is that the loop's honesty machinery is built for claims it has retracted, and the two
worst sentences in this repository today were never retracted — they were narrowed in one file and left
standing in another.** `README.md:22-26` and `docs/clean_clone_gates.md:27` are both cases: the manuscript
narrowed the first and `paper/GAPS.md` G7 wrote down that it had; nobody carried it to the README. Nobody
ever narrowed the second, because nobody measured it. `WC-004`, the registry, the 925-file sweep and
critic #27's grep rule all key on a **withdrawn string**, and a claim that was merely qualified has no
string to key on. The cheapest test is the one WFG-138 asks for and it costs one clause.

**My one `fix-before-next-row` item is WFG-138**, the README's headline attribution. I kept it to minutes on
purpose, because the second finding of this lap is that the item mechanism itself has taken the last three
dev laps (WFG-113, WFG-117, WFG-133, all critic items, all defects in documents the loop wrote) while the
booth kit has not moved since `3e92b69` and `KCF_READINESS.md` has read 4 of 11 for five consecutive critic
laps. That is **NH-038**, open, with four options, and it is the author's because §14b is the author's steer.

**The falsifiable test for critic #29.** (1) Delete `data/raw/dem/srtm/` and run the full suite with no
network. If it is green at `1599 / 62`, WFG-139 closed properly; if it is red, the fix guarded the wrong
test. (2) If `README.md:22-26` still says 「only when the router accounts for where the fire will be」 with no
fire-blind caveat at the next critic head, then a `fix-before-next-row` item costing one clause is not
cheap enough to survive a window, and the finding is about the dev lap's step 3 rather than about the row.

## Critic's previous direction note

**2026-09-06T1400Z, critic #27.** Its root objection was that the loop measures whether a correction was
*made*, never whether it *arrived*; its one item was WFG-133 on Q35, and critic #28 confirms it ran and ran
well, and that it found the registry defect one level up.
*(Full text: `docs/auto/reports/2026-09-06T1414Z-critic.md`; #26's is in the 1112Z report, #25's in the
0816Z, #24's in the 0516Z. This page stays one screen, which is why the older notes live in the reports.)*
