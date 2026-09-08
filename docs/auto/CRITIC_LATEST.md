# CRITIC_LATEST — critic #40, 2026-09-08T0524Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`47e48b5`. Window: the 24 h to 2026-09-08T05:00Z. ⚠ **This clone resolves the window from
2026-09-07T04:08:02Z forward, not the whole of it:** `git rev-parse --is-shallow-repository` =
**true**, `git rev-list --count HEAD` = **50**, and the oldest resolvable commit is `0fc6130`. That
is 49 commits and about 25 hours, so the window is covered; I still make no claim about anything
older than that boundary. Full report: `docs/auto/reports/2026-09-08T0524Z-critic.md`.*

## `fix-before-next-row` — NONE this lap, and that is a decision, not an oversight

**Take the table. It is WFG-167.**

Under CHARTER §14b as amended by NH-038 B, an item must be a fix of **minutes** on a judge-facing
surface or a red gate. No gate is red. Both judge-facing findings this lap produced (**WFG-181**,
**WFG-182**) are a lap each, and §14b files a lap-sized judge-facing finding as a P0 row that is
**never a preemption**. Spending the item on something smaller would have displaced WFG-167 for a
fifth consecutive lap, which is what NH-038 was written to stop.

---

## The baseline, re-derived rather than read

✅ **ALL GREEN on the routine's DEFAULT clone, measured before any deepening, read unpiped.**
`gates.py --mode full` exits **0** at `47e48b5`: `1722 passed, 63 skipped, 2 xfailed`, pytest
277.3 s. `verify`, `snapshot-verify`, `env-check` PASS; the `baseline-verify` WARN is the documented
CHARTER §3d state. **The run downloaded nothing:** `du -sb data/raw` answers **201,187** bytes and
`data/raw/dem/srtm/` is empty afterwards. **Cold on the tile, which was never present; WARM on
`data/cache`**, and I say which rather than implying (DIRECTION's rule). `--assert-head` exits 0;
`--assert-reported --base 0fc6130` exits 0 with 75 substantive paths.

✅ **No CHARTER §4b finding.** Through the GitHub MCP (`curl` is 403 here, WFG-119): `auto-gates`
runs **211 to 231** on `auto/dev` are **18 `success`, 3 `cancelled` (218, 226, 229), ZERO
`failure`**, and run **231** at this exact head is `success`. Every push in the window carried a
report; every **dev** and **critic** report in the window carries `Reviewed by:`.

✅✅ **WFG-178 is closed and I verified it by a channel the lap did not use.** Whole-suite
`pytest -rs` in this tile-less clone prints **60 skip lines, 11 of them naming SRTM**: seven
tile-gated (`test_srtm_dem.py` ×4, `test_raster_ingestion.py:168`,
`test_validation_robustness.py:57`, `test_validation_session3.py:171`) and four gating on the
laptop bundle (`test_slope_digraph.py:145/160/174/209`). That is exactly what `JUDGE_QA.md` Q28 and
Q40 and `docs/clean_clone_gates.md` now state, and `tests/test_tile_gated_skip_count.py` binds
twelve sentences on those pages to the tree, the two spoken lines included, with a
matches-nothing-fails clause. The kit was rebuilt twice (`20260908T0406Z`, 38 pages) and
`release/kcf-finals-2026/MANIFEST.json` re-points at it.

**KCF_READINESS holds at 7 of 11. Zero lines ticked since critic #39.** R1 ticked at
2026-09-07T2020Z, inside this 24 h window, so the 「zero across two consecutive critic laps」
direction finding does not fire — but it fires at the next critic lap if nothing moves.

---

## What the next dev lap should carry into WFG-167

Not corrections; context. Two things this lap established that touch the row you are about to take.

1. **WFG-181 is WFG-167's twin and belongs in the same lap if the clock allows.** Both are one
   `Q · T0` card in `docs/auto/JUDGE_QA.md`, from the same judge (the public-sector
   disaster-response official), and `JUDGE_QA.md` is a printables `SOURCES` file, so doing them
   together costs **one** kit rebuild and one bundle re-point instead of two (WFG-152). Take
   WFG-167 first and only fold WFG-181 in if the row is genuinely finished; a half-written
   개인정보 card is worse than none.
2. **WFG-180's row said 「minutes」 and it is wrong. I updated the row; read it before you take it.**
   `tests/test_tile_gated_skip_count.py` derives a second set, `srtm_named_only`, and that set
   **is** WFG-180. Renaming the four skip reasons takes it 4 → 0 and the derived total 11 → 7, and
   four bound judge-facing sentences go red: two in `JUDGE_QA.md` Q40 (a T1 card with a spoken
   line) and two in `docs/clean_clone_gates.md`. The fix is one lap, including a kit rebuild.

---

## Findings, ranked

**F1 (P0, judge-facing) — WFG-181. The bank has no 개인정보 card, for a tool that outputs a
household-level rescue list for elderly residents.** `git grep -ciE '개인정보|프라이버시|privacy' --
docs/auto/JUDGE_QA.md` returns **zero** across 42 cards, and the same grep returns zero on
`web/finals.html`, `docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/finals/` and `README.md`. The answer
exists in committed files and is a strong one: `docs/data_sources.md:101-102,147` name 행정안전부
주민등록 연령별 인구 통계 and KOSIS 시군구별 65세 이상 독거노인 as *aggregate density* sources,
`outputs/dispatch/README.md` says in its own voice that the clusters are DBSCAN groupings at
eps = 500 m and **not 행정리**, the SMS drafts count places rather than naming people, and
`MANIFEST.json` records `nothing_was_sent: true`. **I checked the negative rather than asserting
it:** the phone-shaped digit runs a regex finds under `outputs/` are all inside floats and hashes
(`1814997.0179265365`), so no phone number is in the tree.

**F2 (P0, judge-facing, and this lap's root objection) — WFG-182. 창의성 is worth 20 points on both
tables and has never moved.** `awk` over the 창의성 columns of `SCORECARD.md`'s combined series
returns the single line `39 15/15`: 15 and 15 in every row from the first critic lap to critic #39,
while the totals went 72 to 86 on the other four rows. `grep -c '창의성' docs/auto/BACKLOG.md`
returns **2** across about 180 rows. The 심사기준 names 창의성 first, and it plus the interview is
over half the ISEF score. Six days of laps have been aimed at correctness; none at the row worth a
fifth of the mark.

**F3 (escalation, updated not duplicated) — the manuscript is SIX WORDS from parking, and CI cannot
measure the limit the author actually set.** `paper/check_paper.py` run here prints
`body_words 8994` against `body_words_max` **9,000**, and `pages {"pages": null, "why": "no
LibreOffice Writer here"}`. The last real page measurement, in the paper lap's own container, was
**23** against a 25-page rule. **NH-037 updated with today's numbers; no new entry opened.**

**F4 (P1, loop hygiene) — WFG-183. A dev report told the author three commit ids resolve on
`auto/dev` and two of them exist nowhere.** `docs/auto/reports/2026-09-08T0407Z-dev.md` writes
「All three ids resolve on `auto/dev`」 of `b1af739`, `893c75c` and `ebba1aa`. Checked by two
channels because a shallow clone is not evidence of absence: `git cat-file -t` fails on both, **and
the GitHub API answers `No commit found for SHA: b1af739`** on a server holding the whole branch.
Both are the lap's own pre-rebase commits. The same annotation says so four paragraphs later. The
lap's *work* is sound — `47e48b5` is green here and run 231 is `success` — this is bookkeeping.

**F5 (P1, loop hygiene) — WFG-184. Three consecutive critic laps got the scorecard append wrong.**
#37 appended to neither detail table, #38's backfill landed mid-table so a 09-07 row sits after a
09-04 one in both, and #39 appended to the combined series only. Annotated in place; **nothing
reordered**, because the charter says append and never rewrite.

---

## `Do NOT edit` notes (CHARTER §14c, NH-036 A)

**None written this lap, and one was deliberately not written.** The obvious candidate was
`JUDGE_QA.md` Q40's 11 / 7 / 4 and `docs/clean_clone_gates.md`'s matching sentences, which are
correct today and which I verified line by line. Freezing them would have been wrong: **WFG-180
will change those numbers on purpose**, and a note telling the next lap not to touch them is exactly
the mechanism NH-036 was opened about. The coupling is recorded in WFG-180's row instead, where the
lap that changes them will read it.

---

## What I changed

`docs/auto/` only, staged by explicit path: `BACKLOG.md` (one reorder, four new rows, WFG-180
updated), `NEEDS_HUMAN.md` (NH-037 updated), `KCF_READINESS.md`, `SCORECARD.md` (three appended
rows plus an ordering note), `DIRECTION.md`, this file, the report and its images. **No code, no
test, no data, no figure, no `docs/NUMBERS.json`, and none of the four printables `SOURCES` files.**
