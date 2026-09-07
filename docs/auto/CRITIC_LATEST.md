# CRITIC_LATEST — critic #36, 2026-09-07T1717Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `7cc4eb7`. Window: the 24 h to
2026-09-07T17:00Z; this clone resolves the WHOLE of it, because the depth-50 boundary is
`719c420` (2026-09-06T21:20Z) and `git log --since='25 hours ago'` returns exactly 50 commits.
Full report: `docs/auto/reports/2026-09-07T1717Z-critic.md`.*

✅ **The baseline is GREEN on the routine's DEFAULT clone, measured before any deepening, and read
unpiped.** `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**.
`gates.py --mode full` exits **0**, ALL GREEN at `7cc4eb7`: `1665 passed, 62 skipped, 2 xfailed`,
pytest 260.5 s, **cold**. `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is
the documented CHARTER §3d state. `--assert-head` exits 0; `--assert-reported --base 719c420` exits
0 with 58 substantive paths.

✅ **No CHARTER §4b finding.** Through the GitHub MCP (`curl` against `api.github.com` is 403 here,
WFG-119): `auto-gates` runs **186 to 215** on `auto/dev` are **28 `success`, 2 `cancelled` (197,
200), ZERO `failure`**, and run **215** at this head is `success`. Every push in the window carried
a report; every dev and critic report carries `Reviewed by:`; the research report does not
(WFG-147, unchanged).

⚠ **A forward-looking number, taken rather than guessed, so you are not surprised by it.**
`web/finals.html` names `7308b06`, **19** commits behind `HEAD`, inside the staleness gate's limit
of 30. This branch put those 19 commits down in 7 h 40 m, about 2.5 per hour, so the gate fires in
roughly **four and a half hours** at that rate. That is NH-043, not a defect in this window. If it
is red when you arrive, `make finals` is the remedy the gate's own message prints, and the bundle
must be re-pointed in the same lap.

---

## `fix-before-next-row` — ONE item (CHARTER §14b)

### WFG-166 — `docs/auto/JUDGE_QA.md:650-652`, the T0 card that forbids its own sentence

Inside **Q16a · T0**, the recited draft has the student say aloud that G-DAPS
「사이렌을 어디에 울릴지는 정해 주지만 **특정한 집의 어느 길이 위험에 들어가고 어느 길이 들어가지
않는지는 말해 주지 않습니다**」. Lines **671-672** of the same card say ❌ 「저쪽은 가구 단위로는 못
합니다」라고 **단정하지 마십시오**, give the permitted form ⭕ 「**공개된 자료에서는** 가구 단위
산출물이 확인되지 않습니다」, and give the reason: 「심사위원이 그 시스템을 직접 써 본 분일 수 있고,
그때 무너지는 것은 이 답변 하나가 아니라 신뢰 전부입니다.」 Twenty lines apart, written by the same lap.

- It is the **Korean half of `WC-008`**, registered at 16:12Z on the English spelling
  `walk out, and along which path`, which a per-spelling ratchet structurally cannot reach. The
  mirror of what happened to `WC-007` in the same lap, in the other direction.
- `JUDGE_QA.md:625` asserts this card says 「공개된 자료에서는 확인되지 않습니다」**만**, which is
  false at `:651` and is what a later lap would read to decide the card is clean.
- It is **printed**: `JUDGE_QA.md` is a `SOURCES` file of kit `20260907T1551Z`, 17 of its 38 pages,
  and the kit is inside the release bundle.

**What the fix is:** the recited draft says only what this project checked (for example
「저희가 연 자료 — 카탈로그 기록과 언론 보도 — 에서는 가구 단위 경로 산출물이 확인되지
않습니다」), or drops the clause and keeps the positive statement of this project's own output
object; `:625` is corrected in the same edit; the superseded sentence is kept as a dated record
(CHARTER §3.7) and **is not reprinted verbatim on a printed page** (the `WC-005`/`WC-007`
precedent: the note describes, the registry quotes); `WC-008` gains the Korean spelling; the kit is
rebuilt at a new stamp **in the same lap** and the bundle re-pointed (WFG-152); and the lap runs the
DIRECTION subject grep on 「읍면동」 and 「가구 단위」 across `docs/ paper/ release/ web/` and names in
writing every file it returned.

⚠ **I could not do this myself.** `docs/auto/DIRECTION.md` forbids critic and research laps from
editing `JUDGE_QA.md` at all, because a one-line edit turns
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red unless the
same lap rebuilds the kit.

---

## The one row move, and the order behind it

**`WFG-009` raised P1 → P0, DIRECTION position 1.** `WFG-110` closed at `60c07c8` and I re-derived
it rather than reading it (28 parser keys, all 28 in `docs/finals_screen_numbers.md`, all 28 keys of
`docs/NUMBERS.json`), which met R1's **second** clause. R1's **first** clause is 「opens from
`file://` with Wi-Fi off, **all four acts advance**」, and nothing in this repository has ever
exercised the word *advance*. `WFG-009` is that row and it has sat at P1 inside the very block
CHARTER §14b holds **behind** R1, with eleven infra rows behind it. A row that unblocks a readiness
line cannot be parked behind that readiness line.

**What I measured, so you do not repeat it.** Chromium is present at
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`. `--headless=new --disable-gpu --no-sandbox
--virtual-time-budget=8000 --dump-dom file://$PWD/web/finals.html` exits **0** and returns
**3,449,612 bytes** of post-JS DOM holding `view-live`, `view-evidence`, `view-reliability`,
`view-system` and the labels 라이브 · 근거 · 신뢰성 · 시스템; the built file has **zero** `http(s)`
`src`/`href` references. ⚠ At initial load `view-live` = 1,157,688 B and `view-reliability` =
2,063,451 B, while **`view-evidence` = 225 B and `view-system` = 235 B with no Korean text**. Those
two build on switch and `--dump-dom` presses no key, so 「advance」 is the word nothing has measured.
⚠ **First risk to check in your first ten minutes:** whether `npm`/`@playwright/test` or a Python
`playwright` installs in this sandbox at all — `pip` timed out twice on `files.pythonhosted.org`
during this lap's own bootstrap. If not, drive the acts over `--remote-debugging-port` with the
stdlib. The row is the four screenshots, not the framework.

Order after WFG-166: **WFG-009**, **WFG-139** (ninth measurement, below), **WFG-167**, then WFG-128,
WFG-129 and the rest of `docs/auto/DIRECTION.md`'s list.

---

## New rows filed this lap

| id | P | what |
|---|---|---|
| **WFG-166** | P0 | the `fix-before-next-row` item above |
| **WFG-167** | P0 | 42 Q&A cards and **zero** on responsibility. `git grep -niE '책임\|법적\|면책' docs/auto/JUDGE_QA.md` returns nothing, while `web/finals.html:1393` prints 「최종 판단은 언제나 사람이 내립니다」 and `DEMO_SCRIPT_5MIN.md:217` gives it as the 재난대응 실무자 answer. One of the five judges is a public-sector disaster-response official. WFG-144's asymmetry in the other direction |
| **WFG-168** | P1 | five withdrawals of one claim family in one day, every one found by a reader and none by a gate. A lint over judge-facing prose (third-party subject + negative predicate, no licensed hedge), not a claim detector. Held behind R1/R3/R4/R7/R8/R9 by §14b, deliberately |

**No NEEDS_HUMAN entry was added this lap.** The one thing that could have been an escalation is
agent-doable and is WFG-168.

---

## Unchanged and untaken, re-checked rather than re-filed

- **WFG-139**, ninth consecutive measurement, on this lap's own clock:
  `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 B**) and its `.gz` have mtime **17:02:33Z**, inside
  a `pytest-full` run that began about 17:00Z, in a container whose `data/raw/` held only `.gitkeep`
  and `README.md` at start. Six terrain tests have still never run in CI.
- **WFG-163**: `docs/auto/knowledge/PYROGEOGRAPHY.md` §2 still states G-DAPS 「entered trial
  operation in April 2026」 as accomplished fact. I did not re-fetch the article and do not claim the
  reading as mine; critic #35 did, four hours ago.
- **WFG-147**: the research report is still the only report in the window with no `Reviewed by:`.
- The 1600Z dev report ships with its gate table marked `stale` (`13c79c1` vs `60c07c8`, pushed as
  `7cc4eb7`). The prose beside it reports a green unpiped run, GitHub run 215 is `success` and my
  own run is green, so the **tree is right and the report's table is what is wrong**. Loop hygiene,
  held behind R1 by §14b, covered by the existing report-certification rows; recorded, not re-filed.

## What I checked and found sound

- **`WFG-162` is genuinely closed on the printed panel**, and its dated note **describes** the
  withdrawn sentence instead of reprinting it — `WC-005`'s precedent used correctly on a page that
  prints. The best thing in the window.
- **`docs/related_work.md`'s four dead `docs/*.md` paths are the record, not a defect**: each is
  licensed with `<!-- dead-path-ok -->` and held true by
  `tests/test_related_work_paths.py::test_the_paths_named_as_dead_are_still_dead`.
- **The 42/91 caveat trace holds at this head**, re-run rather than inherited: both numbers appear
  only in `README.md`, `web/finals.html`, `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`
  and `paper/manuscript.md`, and all five carry the noiseless-forecast wording.

## Readiness and scores

**KCF_READINESS: 6 of 11** (R2, R4, R5, R6, R7, R9), unchanged. R9 (05:00Z) and R7 (08:00Z) both
ticked inside this 24 h window, so the "zero across two consecutive critic laps" direction finding
does not fire. **R1's blocker changed identity for the first time in five laps: WFG-110 → WFG-009.**

**Track B 86 (17 / 18 / 18 / 15 / 18); Track A 83 (16 / 18 / 19 / 15 / 15). Every row holds.** The
pre-registration, so the next critic can falsify me: **when a driver advances all four acts of
`web/finals.html` and uploads four screenshots (WFG-009), Track A 구현 및 유용성 goes to 20.**

## Root objection

**A registered withdrawal reaches one language, and nobody has ever registered both halves in the
same lap.** `WC-007` went in in Korean and its English half surfaced ninety minutes later; `WC-008`
went in in English and its Korean half is on the card the student says out loud. Registration is the
right tool and the ratchet is per-spelling by construction, while the project ships in two
languages. **Cheapest test:** for the next withdrawal, run the subject grep once in Korean and once
in English before calling it done, and write down both results. Two out of two so far have returned
something in the second language, both inside one day.
