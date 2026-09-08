# CRITIC_LATEST — critic #39, 2026-09-08T0217Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `1282198`. Window: the 24 h to
2026-09-08T02:00Z. ⚠ **This clone resolves the window from 02:25Z on 09-07 forward, not the whole of
it:** `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**, and the
oldest resolvable commit is `5cca6ce` (2026-09-07T02:25:10Z). The 25 minutes before that are outside
this clone and I did not read them. Full report: `docs/auto/reports/2026-09-08T0217Z-critic.md`.*

✅ **The baseline is GREEN on the routine's DEFAULT clone, measured before any deepening, read
unpiped.** `gates.py --mode full` exits **0**, ALL GREEN at `1282198`: `1708 passed, 63 skipped,
2 xfailed`, pytest 290.9 s, **COLD**, and **the run downloaded nothing** — `du -sb data/raw` answers
**201,187** bytes before and after, and `data/raw/dem/srtm/` is empty. `verify`, `snapshot-verify`,
`env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d state. `--assert-head` exits 0;
`--assert-reported --base 5cca6ce` exits 0 with 73 substantive paths.

✅ **No CHARTER §4b finding.** Through the GitHub MCP (`curl` is 403 here, WFG-119): `auto-gates` runs
**207 to 227** on `auto/dev` are **19 `success`, 2 `cancelled` (218, 226), ZERO `failure`**, and run
**227** at this exact head is `success`. Every push in the window carried a report; every **dev** and
**critic** report in the window carries `Reviewed by:`.

✅✅ **WFG-139 is closed after eleven laps, and I re-derived it rather than reading it.** The
mechanism is real: `tests/conftest.py` refuses outbound sockets session-wide, including to the
`*_proxy` addresses this sandbox routes egress through, and `pytest_sessionfinish` fails a run in
which `data/raw/` grew. This is the strongest single piece of evidence this repository has produced
for its own reproducibility claim, and it is the first cold gate run here that downloaded nothing.

✅ **WFG-173 is closed.** `web/finals.html` names `1bca8ed`; `git rev-list --count 1bca8ed..HEAD`
answers **4** against `STAMP_MAX_COMMITS_BEHIND = 30`. The branch is open, critic #38's parked lap is
on `auto/dev`, and NH-045 is no longer blocking anything (dated update written into that entry).

**KCF_READINESS holds at 7 of 11.** R1 ticked inside this window (2026-09-07T2020Z), so the
「zero across two consecutive critic laps」 direction finding does not fire.

---

## `fix-before-next-row` — ONE item (CHARTER §14b)

### WFG-178 — the honest remainder printed on the card is wrong by the test the same commit added

The WFG-139 lap did the hard thing right and then hand-typed the number that describes what it left
open. Three judge-facing surfaces say the tile-gated skip set is **six**:

| surface | what it says |
|---|---|
| `docs/auto/JUDGE_QA.md:980` (Q28, 없는 것) | 「지형 타일이 있어야 도는 테스트 **여섯 개**는 깨끗한 클론에서 여전히 건너뜁니다」 |
| `docs/auto/JUDGE_QA.md:1182` (Q40) | enumerates them as `test_srtm_dem.py` 네 개 + `test_validation_robustness.py` + `test_validation_session3.py`, and scripts the student to say 「**여섯 개**는 깨끗한 클론에서 건너뜁니다」 aloud |
| `docs/clean_clone_gates.md:85` | 「The **six** SRTM tests that `skipif` on the cached tile still skip on a clean clone」 |

**Measured here at `1282198`, cold, with `data/raw/dem/srtm/N36E129.hgt` absent, the tests whose
`skipif` predicate is exactly that tile number seven.** The six the card names, plus
`tests/test_raster_ingestion.py:168::test_auto_dem_prefers_srtm_when_the_tile_is_cached`, whose
predicate is `_srtm_tile_cached()` at `tests/test_raster_ingestion.py:166-169` reading that same
path. That test was **added by `ab4e71e`, the commit that wrote the card**, and the lap's own report
says so at `docs/auto/reports/2026-09-08T0121Z-dev.md:202`: 「The 63rd skip is new and is mine」. The
card did not learn it.

**It is on paper and in the student's mouth.** Kit `20260908T0114Z`, 38 pages; I re-hashed all six
`SOURCES` against the tree in one process and every one matches, `JUDGE_QA.md` at
`c7ab6e505ce0…`. Q28 and Q40 are inside the 17 printed JUDGE_QA pages, and Q40 is a T1 card with a
spoken line.

**Nothing reads the number.** `grep -rn '여섯 개' tests/` and `grep -rn 'six SRTM' tests/` both return
nothing outside a `.pyc`. The count is prose, and prose about this repository's own suite is the one
class of number this project does not register.

**Second defect in the same write-up, same minutes.** `docs/clean_clone_gates.md:45` reads
「**Result, measured 2026-09-08 on this sandbox at `088203c`**」. `git ls-tree -r 088203c --
tests/conftest.py` is **empty**; the guard that result is about first exists at `ab4e71e`. The
measurement is real and I reproduced it; the commit id under it names a tree with no guard in it.

⚠ **What is NOT wrong here, said plainly so the next lap does not over-correct.** The mechanism, the
two real callers, the false positive the lap admitted to, and the enumerated blind-spot list are all
accurate and I checked them. This is a count and a commit id, nothing else. Do not reopen WFG-139.

**Done when** `docs/auto/JUDGE_QA.md:980`, `:1182` and `docs/clean_clone_gates.md:85` state **seven**
and name `test_auto_dem_prefers_srtm_when_the_tile_is_cached`; `docs/clean_clone_gates.md:45` names
`ab4e71e`; the printables kit is rebuilt at a new stamp and `make finals-bundle` re-points
`release/kcf-finals-2026/MANIFEST.json` in the **same lap** (WFG-152); and `gates.py --mode full` is
re-run after the rebuild, read unpiped, with `--assert-head` and `--assert-reported` immediately
before the push.

⚠ **Prefer a pointer to a second hand-typed number.** The durable form is 「`pytest -rs`의 출력이
정본입니다」 with the seven named once; a fourth surface carrying a bare integer is a fourth thing to
go stale. If the next lap wants the count gated, that is WFG-172's territory and a separate row.

---

## The rest of the findings, ranked

**2. WFG-179 (P1) — readiness line R3 names a command nothing in this project runs.** `Makefile:215`
makes `baseline-verify` a hard prerequisite of `all-checks`; `baseline-verify` exits 2 in every clone
without the acquisition manifests (CHARTER §3d), so `make all-checks` cannot go green on a clean
clone by construction. `.github/workflows/auto-gates.yml:31` runs `gates.py --mode full` instead.
R3's CI half has been graded by a different command than it names for the checklist's whole life.
Filed rather than fixed: rewording a readiness line is the author's, **NH-046**.

**3. WFG-180 (P1) — four skip messages say SRTM for a file that is not the SRTM tile.**
`tests/test_slope_digraph.py:145/160/174/209` carry `reason="SRTM DEM absent"` and gate on
`DEM = data/raw/firms_data/yeongdeok_2025_dem.tif` (`:24`). On the cold run here `pytest -rs` prints
four SRTM-looking skips that are not tile-gated, beside the seven that are. A judge who follows Q40
to `pytest -rs` counts eleven against a card that says six, and four of the eleven are a naming
defect.

**4. A staleness, reported and deliberately not promoted.** `docs/clean_clone_gates.md:100` reports
`1063 passed, 54 skipped` and `:111-121` break the 54 down by cause with no SRTM row at all, while
the same file's new section above it reports a 2026-09-08 run and the suite reports **63** skips
today. I did **not** file this at P0 or as the item, and the reason is on the record: `:3-5` dates
the table 「measured 2026-09-03 … head `953eb6c`」 and `:183-186` says in the file's own voice
「Re-measure rather than quote these once the head has moved」. That is CHARTER §3 rule 5b's form used
correctly, so it is a staleness and not a false claim. It is noted in WFG-178's details as context
and nowhere promoted.

---

## The root objection (`hate`)

**This project registers every number it says about the world and none of the numbers it says about
itself, and the newest one was wrong within the same commit that wrote it.**

`docs/NUMBERS.json` holds 383 entries that `make verify` re-derives from committed artifacts, and
`docs/auto/withdrawn_claims.json` now holds ten claim families that a sweep reads across 933 gated
files. Both machines exist because a hand-typed figure about the fire, the model or another system
was wrong and nobody caught it. Meanwhile every figure this repository prints **about its own suite**
— 「여섯 개」, `1708 passed, 63 skipped`, 「933 gated files」, 「38 pages」 — is prose, and only the last
of those is gated (by the printables manifest). WFG-178 is what that costs: not a lie, not a
shortcut, just a number that no machine was watching, on the card whose whole subject is that this
project does not rely on people remembering things.

**The cheapest test, and I ran it:** `grep -rn '여섯 개' tests/` returns nothing. Neither does any
assertion binding a judge-facing skip count to what `pytest` itself reports. The fix is not another
number; it is that a card about the suite either points at `pytest -rs` or is derived from it.
WFG-172 is the row that already half-says this and is still `todo` behind the readiness block.

---

## `Do NOT edit` — restated after re-checking, expires at critic #40 (CHARTER §14c, NH-036 A)

**The critic and research routines must not edit `docs/auto/JUDGE_QA.md`,
`docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/finals/BOOTH_SETUP.md`,
`docs/auto/finals/RELATED_WORK_PANEL.md`, `docs/submission_reconciliation.md` or
`docs/auto/finals/DETECTION_FLOOR_CARD.md`.**

**The exact lines it covers and the measurement behind it, taken this lap.** These six paths are the
`sources` array of `docs/auto/finals/printables/manifest_20260908T0114Z.json`, the newest kit. I
re-hashed each file on disk at `1282198` in one process against the `sha256` the manifest records:
`BOOTH_SETUP.md` `99b2168f4bd7…`, `DEMO_SCRIPT_5MIN.md` `b1aae78f35c7…`, `JUDGE_QA.md`
`c7ab6e505ce0…`, `submission_reconciliation.md` `237de4f4aeab…`, `DETECTION_FLOOR_CARD.md`
`84648d4d6e0b…`, `RELATED_WORK_PANEL.md` `5c62a918cf4c…` — **six of six match**. Since `590c29a`,
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` compares exactly
these hashes, so a one-line edit to any of the six by a routine that cannot run `make printables`
turns that test red and closes the branch. That is what stops this lap from writing WFG-178's fix
itself. ⚠ I re-hashed; I did **not** re-probe the test by editing a source, because critic #31 did
that at `3f881f6` and reverted it, and repeating a destructive probe on the finals kit inside the
sprint is not worth the second data point.

**This note covers those six paths and nothing else.** It does not freeze any question in
`JUDGE_QA.md`, it does not freeze `docs/clean_clone_gates.md` (which is **not** a manifest source and
which a dev lap should edit freely), and it expires at critic #40 unless that lap re-hashes the
manifest and re-states it.
