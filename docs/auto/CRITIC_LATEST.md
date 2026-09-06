# CRITIC_LATEST — critic #28, 2026-09-06T1736Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `e95fe28`. Window: `dd500e6..e95fe28`, plus the
24 h to 2026-09-05T17:41Z for the gate, CI and report checks.*

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-138 — `README.md` asserts, about the number the project leads with, the attribution that
`paper/manuscript.md`'s own Abstract disclaims one sentence later.**

`README.md:22-26`, the 「Headline result」 bullet of the TL;DR:

> On the canonical Yeongdeok field, **42 of 458** scanned origins reach a refuge **only** when the router
> accounts for where the fire will be, and **2** have no safe walking route at all
> ([Round 3](#round-3-2026-08); the 32.6 % coverage caveat applies).

`paper/manuscript.md`, Abstract, same two numbers:

> on the canonical Yeongdeok field, 42 of 458 scanned walk-network origins reach a refuge only under the
> forecast-aware policy, and 2 have no safe walking route, on a network covering 32.6 % of the predicted
> fire core whose bias runs in an unmeasured direction. **That contrast is measured against a fire-blind
> baseline, so it does not separate knowing where the fire will be from knowing where it is.**

The baseline is fire-blind in this repository's own words: `src/wildfireguardian/routing/evacuation.py:270`
(「Fire-blind shortest path to the nearest shelter, then scored against the hazard」) and
`docs/real_roads_real_hazard.md:50` (「the fire-blind shortest walk to the nearest refuge (the status quo)」).

`paper/GAPS.md` G7 records that the manuscript's abstract 「had the same overclaim ... and it was corrected
this lap」, and names the two other surfaces the loop already repaired for the identical claim: the booth
script's 3막 sentence (**WFG-103**, `92366cb`) and the finals template (**WFG-109**). **The README is the
fourth surface and no row has ever named it.**

**Why it is the item.** The README is the first page a KCF judge, an ISEF reviewer or an IEEE reader opens,
it is what `CITATION.cff` points at, and its TL;DR advertises a withdrawn-claim record three bullets below
the unqualified sentence. A reader who opens the manuscript next finds the repository contradicting itself
about the number it leads with, on the axis it asks to be judged on.

**Why nothing caught it.** `WC-004`, `check_withdrawn_claims.py` and critic #27's own grep rule all key on a
**withdrawn string**. This claim was never withdrawn; it was **narrowed**, in one file, and a narrowed claim
has no banned spelling to key on. That is the root objection of this lap.

**Done when:** the bullet says no more than the manuscript says. Suggested minimal edit, additive, no number
moves and no registered value changes meaning: append 「That contrast is measured against a **fire-blind**
baseline, so it does not separate knowing where the fire will be from knowing where it **is**; the
present-perimeter opponent has been run on 의성·안동 only (`docs/present_perimeter_arm.md`, WFG-129 for
영덕)」.

⚠ **Constraints.** This is the 「Headline result」 bullet, **not** the README's opening paragraph about the
2025 fire, which CHARTER §3.5b and `DIRECTION.md` protect — do not touch that paragraph. Put **no**
fair-opponent margin (9, 27, 5, 19) in the sentence; NH-032 is open. Do not enlarge this into WFG-129's
experiment or WFG-125's oracle question. It is one clause, and I kept it to one clause deliberately: see
NH-038.

## What this lap verified rather than read

- `gates.py --mode full` **ALL GREEN** at `e95fe28`: `1599 passed, 62 skipped`, **cold**, 288.4 s
  (critic #27's cold `1569 / 62`: **+30 passed**, skips unchanged). `verify`, `snapshot-verify`, `env-check`
  PASS; `baseline-verify` WARN is CHARTER §3d information.
- **No red CI run behind a green report, so no CHARTER §4b finding.** Read through the GitHub MCP (the
  routine's `curl` returns 403, WFG-119): `auto-gates` runs **#154 to #178** on `auto/dev` are **21 `success` <!-- forbidden-ok: 154 -->
  and 4 `cancelled`** (`dfdf480`, `828bbae`, `ef61e9b`, `9ebf5a5`, each superseded by a later green push),
  **no `failure` at all**. Run **178** at `e95fe28`, this head, is `success`.
- `--assert-head` OK at `e95fe28`; `--assert-reported --base dd500e6` OK (18 substantive paths travel with
  a new report). Every **dev** report in the window carries `Reviewed by:`.
- **No author reply.** The Gmail search on `subject:"WildfireGuardian autoloop" newer_than:14d`
  returns a first page of 50 threads, newest first; every one is **sent by this loop** and holds exactly
  one message, so no thread carries a reply (a reply would bump its thread to the top of that ordering).
  `docs/auto/decisions_seen.json` is unchanged (`seen: []`, 23 applied, all from laptop sessions). PR #31
  has no comments. No `NH-###:` line reached the loop through either channel.
- The clone was **fully unshallowed** before anything about the graph was written:
  `git rev-parse --is-shallow-repository` answers `false`, 496 commits.

## Findings, ranked

1. **WFG-139 (P0, new) — the test suite downloads 25 MB from Amazon S3 mid-run, and the clean-clone
   reproducibility claim is false.** On a clone created at 16:57Z with no `data/raw/` at all,
   `gates.py --mode full` produced `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 bytes**) and its `.gz` at
   **17:02Z**, during `pytest-full`. Caller: `tests/test_spread_warmup.py:156`, `dem_source="srtm"`, **no
   skip guard**, reaching `elevation-tiles-prod.s3.amazonaws.com` via
   `src/wildfireguardian/data_io/raster.py:521` → `:282` → `:252`. CHARTER §4b: 「No test may depend on the
   local clock, the timezone, the network, or files outside the repository.」
   `docs/clean_clone_gates.md:27` reads 「No network, no keys, no `.env`.」 and is one of the three files
   `docs/auto/JUDGE_QA.md` **Q28 · T2** cites to a judge; Q28's card also says 「그 입력을 필요로 하는
   테스트는 이유를 적은 채로 건너뜁니다」, false of this one. **Six tests have never run in CI**
   (`test_srtm_dem.py:81/:94/:109/:170`, `test_validation_robustness.py:57`,
   `test_validation_session3.py:171`): `skipif` is evaluated at collection, every CI job is a fresh clone,
   so the download always lands after the decision to skip. They are the terrain-plausibility checks on the
   DEM the router walks over. **And this is the whole of the cold/warm skip gap the loop has diagnosed
   twice and never chased**: cold `1599 / 62`, warm `1605 / 56`, same commit `e95fe28`, both measured here.
   The 0059Z dev lap wrote 「(`data/cache/**` DEM and OSM caches) ... expected rather than a discrepancy to
   chase」 and the 1638Z lap wrote 「the two disagree by 6 and I did not chase it」. Both named the wrong
   directory. Q40 is added to `JUDGE_QA.md`'s open-questions table for it.
2. **WFG-138 — the README overclaim above.** The item.
3. **WFG-140 (P0, new) — the booth kit has no freshness gate, and critic #27 pre-registered this filing.**
   Re-hashed all four `SOURCES` at `e95fe28`: three match, `docs/auto/JUDGE_QA.md` does not, manifest
   `2c8451211e…` against tree **`7d5ac4c9c5…`** where critic #27 measured `af955a30fa…` — the drift is
   **larger**, because the WFG-133 lap edited Q35 again. The PDF's self-hash still matches, so
   `tests/test_printables.py` is fully green over a stale kit. The gate has been a sub-clause of two rebuild
   rows for two windows and both rebuilds were displaced; a gate that ships only if a rebuild ships is not a
   gate. ⚠ Grade it **red on today's tree**, before the rebuild makes it green.
4. **NH-038 (DECISION, MEDIUM, new) — the `fix-before-next-row` mechanism has taken the last three dev
   laps.** WFG-113 (critic #25's item), WFG-117 (#26's), WFG-133 (#27's): three consecutive dev laps, three
   critic items, all three defects in documents the loop itself wrote, every one worth fixing. Meanwhile
   nothing has finished the booth kit since `3e92b69` at 06:20Z on 09-06, and `KCF_READINESS.md` has read
   **4 of 11 for five consecutive critic laps**. The cap of one item per lap is also a floor of one, and it
   caps the *number* of items rather than their *cost* or how many laps in a row may carry one. §14b is the
   author's steer, so the change is the author's; four options are on the entry.
5. **WFG-141 (P1, new, and it waits) — `report.py --kind` has no `paper` and no `ci-red`**
   (`scripts/auto/report.py:227`), so three routines file as `manual`: of 33 `*-manual.md` reports, **12**
   are titled 「autoloop · paper」 and **2** 「autoloop · ci-red」. Critics #26 and #27 both wrote that the
   window's reports without `Reviewed by:` are 「`manual`, the author's own laptop」 and treated that as a
   reason it is not a finding; twelve of them are the paper routine, which does run a subagent reviewer and
   is held to the same discipline (CHARTER §12, NH-026). No report has actually escaped, so this is a wrong
   reason rather than a missed defect — filed because the reason is what the next critic reuses. Second
   defect on the same files: the stamp in the title disagrees with the stamp in the filename by up to 40
   minutes (`2026-09-06T1507Z-manual.md` is titled `1547Z`), and the **email subject uses the title stamp**,
   so the author cannot find in the repository the report they were sent. Loop mechanics: §14b holds it
   behind R1, R3, R4, R7, R8, R9.

## Direction check (CHARTER §14, five minutes)

**Yes, the next `todo` row is still the highest-leverage one for 2026-10-24, and no existing row moved.**
R7 and R9 both wait on the booth kit and nothing else does. Three new P0 rows enter (WFG-138 at position 1,
WFG-140 and WFG-139 below the judge-facing block); no P0 sits below a non-P0. **KCF_READINESS lines ticked
in the last 24 h: zero**, fifth consecutive critic lap at 4 of 11 — that is finding 4 above and it is about
the loop's direction, not about the product.

## What I did not do

I changed no code, no test, no data, no figure and no `docs/NUMBERS.json`. Every measurement above was
re-run in this sandbox; nothing was carried over from a report. I did not re-measure WFG-110's six unmapped
registry keys and do not tick R1 on a number I did not take.
