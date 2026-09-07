# CRITIC_LATEST — critic #37, 2026-09-07T2020Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `64f015b`. Window: the 24 h to
2026-09-07T20:00Z; this clone resolves the WHOLE of it, because `git rev-list --count HEAD` = **50**
and the oldest resolvable commit `d6cb996` is inside the window (`git log --since='26 hours ago'`
returns exactly 50). Full report: `docs/auto/reports/2026-09-07T2020Z-critic.md`.*

✅ **The baseline is GREEN on the routine's DEFAULT clone, measured before any deepening, and read
unpiped.** `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**.
`gates.py --mode full` exits **0**, ALL GREEN at `64f015b`: `1682 passed, 62 skipped, 2 xfailed`,
pytest 289.3 s, **COLD**, and the run **downloaded 25.9 MB** partway through (see finding 3).
`verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d
state. `--assert-head` exits 0; `--assert-reported --base 018dd78` exits 0 with 20 substantive paths.

✅ **No CHARTER §4b finding.** Through the GitHub MCP (`curl` against `api.github.com` is 403 here,
WFG-119): `auto-gates` runs **200 to 219** on `auto/dev` are **18 `success`, 2 `cancelled` (200,
218), ZERO `failure`**, and run **219** at this head is `success`. Every push in the window carried a
report; every dev and critic report carries `Reviewed by:`; the research report does not (WFG-147,
unchanged).

✅✅ **R1 TICKS. 7 of 11, and it is the first movement on this line since the checklist was
written.** Both remaining clauses were re-derived here rather than read, and one of them was
re-derived on a machine that is not this sandbox. See `docs/auto/KCF_READINESS.md`.

⚠ `web/finals.html` names `7308b06`, **24** commits behind `HEAD`, inside the staleness gate's limit
of 30. NH-043, not a defect in this window. If it is red when you arrive, `make finals` is the
remedy the gate's own message prints, and the bundle must be re-pointed in the same lap.

---

## `fix-before-next-row` — ONE item (CHARTER §14b)

### WFG-171 — the same family as WFG-166, in the POSITIVE direction, on the same two surfaces

`docs/auto/finals/RELATED_WORK_PANEL.md:32` (printed, 뒷면 1) and `docs/auto/JUDGE_QA.md:652`
(the recited **Q16a · T0** draft, printed on the kit's Q&A pages) both assert, flat, present tense,
one of them in bold:

> 발화점은 **운영자가 손으로 입력**합니다.

That is a positive factual claim about another agency's operating system, and its whole provenance is
a **chapter title in a library catalogue's table of contents** (「발화지점 생성」). Nobody in this
project has opened the NIFoS user guide; NH-039 is open precisely because of that.

**Why this is the same defect the last three laps have been fixing, not a new one.** Every other
surface in this repository states it with its attribution and its limit:

- `paper/references.bib:258` writes it as what the catalogue's chapter list implies, names the eight
  chapters, and adds 「Only the catalogue page was opened」.
- `paper/manuscript.md:111-112` writes 「publishes a 2026 user guide for an AI spread-prediction
  console driven by a human-entered origin point [@nifos2026guide]」, attributed.
- `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §1 writes 「The catalogue's table of contents
  describes an operator workflow ... So it is an operator console ... driven by a human-entered
  origin point」, with the derivation visible.

The two surfaces a judge actually meets are the two that dropped the attribution. And the panel does
it **four lines above** its own ⚠ note, whose argument is that this panel read only 「카탈로그
기록·언론 보도」 and that 「열어 본 적 없는 문서에 무엇이 **없다**고 말하는 것은 요약이 아니라 새로운
주장입니다」. The note's rule covers only negatives. A positive assertion of the same provenance is the
same new claim, and it fails in the same way: a judge who has driven that console and knows it can
take an origin from a KFS feed hears a flat sentence that is simply wrong, and what breaks is not one
answer but, in the card's own words, 「신뢰 전부」.

⚠ **The 읍면동 and 30분 clauses beside it are NOT this finding and must not be softened.** Those are
reported by 경향신문 2026-03-30, an article this project opened, and the register they are in is
correct.

**Done when** both lines state the claim at the strength of its source, in the register those two
files already use elsewhere, for example 「카탈로그의 목차가 「발화지점 생성」을 한 장으로 두고 있어,
운영자가 발화점을 지정하는 흐름으로 읽힙니다」; **and** the same lap runs `make printables` and
re-points `release/kcf-finals-2026/MANIFEST.json` (WFG-152), because both files are printables
`SOURCES` and a one-line edit without the rebuild turns
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red; **and** the
lap runs the subject grep DIRECTION mandates (`git grep -n '발화' -- docs/ paper/ release/ web/`) and
names in writing every file it returned and what it did about each.

**This is why I did not fix it myself.** DIRECTION's *What not to do* forbids the critic and research
routines from editing `JUDGE_QA.md`, `DEMO_SCRIPT_5MIN.md` and `BOOTH_SETUP.md` at all, for exactly
the staleness reason above; `RELATED_WORK_PANEL.md` is a `SOURCES` entry on the same footing. Only a
lap that rebuilds the kit in the same lap may touch them.

---

## The rest, ranked, and none of them is a `fix-before-next-row` item

2. **WFG-172 (new, P1, infra) — the cold/warm rule DIRECTION wrote has no enforcement, and the very
   next lap broke it.** `docs/auto/reports/2026-09-07T1900Z-dev.md` and commit `64f015b`'s message
   both record 「1688 passed / 56 skipped / 2 xfailed, unpiped」 with **no** cold/warm word and **no**
   statement of whether the run downloaded anything. DIRECTION's *What not to do* says, in its own
   ⚠ bullet: 「Do not report a pass/skip count without saying cold or warm, and without saying whether
   the run downloaded anything (WFG-139).」 It is not a slip with no consequence: my **cold** count at
   the **same tree** is `1682 passed, 62 skipped`, and a reader comparing 1682 to 1688 reads a
   six-test regression that did not happen. `report.py` can take both facts mechanically (the pytest
   summary it already parses, plus the size of `data/raw/` before and after) and no lap then has to
   remember.

3. **WFG-139 — TENTH consecutive measurement, taken on this lap's own clock.** At container start
   `data/raw/` held `.gitkeep` and `README.md` only. After `gates.py --mode full`,
   `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 B**) and `N36E129.hgt.gz` (8,473,868 B) carry mtime
   **2026-09-07T20:02Z**, inside a `pytest-full` stage that ran 19:59Z to 20:04Z. Unchanged, unrepaired,
   and it is DIRECTION position 1 for the next lap.

4. **The author has TWELVE open decisions and two of them are due TOMORROW.** `decisions_seen.json`
   shows `"seen": []`: no decision has ever arrived by email, and the newest applied one is NH-031
   from a laptop session on 2026-09-06. NH-032 and NH-034 (**by 2026-09-08**) are the two that decide
   what the project's headline number means against a fair opponent; NH-035, NH-038, NH-043 and NH-044
   are due **2026-09-09**. This is not a finding against a lap. It is the one thing in this window
   that no lap can clear.

## Direction

**No reorder, and no reorder was needed.** DIRECTION's position 1 (WFG-009) and its
`fix-before-next-row` (WFG-166) both **closed** this window and closed well. Position 1 is now
**WFG-139**, which is where the page already had it, and it stays P0 rather than falling to the §14b
infra block because it blocks readiness line **R3** and puts a false sentence on `JUDGE_QA.md` Q28.
My one item above sits ahead of it and displaces nothing, per §14b.

**Readiness lines ticked in the window:** R9 (05:00Z), R7 (08:00Z) and now **R1** (this lap). The
「zero across two consecutive critic laps」 direction finding does not fire, and this is the first lap
in the checklist's life where it could not have.

## `Do NOT edit` notes carried forward

**None.** Critic #36 left none, and this lap writes none. The DIRECTION rule that keeps this routine
out of `JUDGE_QA.md`, `DEMO_SCRIPT_5MIN.md`, `BOOTH_SETUP.md` and `RELATED_WORK_PANEL.md` is a
standing routine boundary, not a `Do NOT edit` note on a file's content, and it names its own
mechanism (`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree`,
probed and reverted at `3f881f6`). It is re-checked and re-stated here rather than inherited.
