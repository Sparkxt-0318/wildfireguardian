# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-10T1120Z by critic #58 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy (Korea's own agencies forecast spread better resourced
than we can) but the **output object**: a time-dependent decision per point, with its limits measured and
written down.

## Before any row: this lap's one `fix-before-next-row` item

**`docs/oracle_gap.md:233` claims a registry protection that does not exist for the string it quotes.
Rewrite that one clause; change nothing else on the page.** The sentence reads 「Anyone quoting 0.394 as
"what the forecast buys" has misread it, and that phrasing is registered as forbidden on all ten keys」.
Measured at `d3ca754`: the `og_yeongdeok_*` prefix holds **30** keys, not ten; all 30 do carry a
`forbidden_phrasings` list, so 「all of them」 is right and only the number is wrong; and the quoted string
「what the forecast buys」 is a registered forbidden phrasing on **zero** keys. The nearest registered
spelling is 「**this measures what the model buys**」.

⚠⚠ **The paragraph's argument is correct and must not be softened.** 0.394 is not what the forecast buys.
Only the appeal to the registry is wrong. ⚠ **Do NOT write 「thirty keys」 either** — this page's own §Registry
line at `:6-9` says a key count written into prose goes stale the next time the registrar grows, and `:233`
is that mistake made 226 lines below the warning. Name the prefix and quote the registered spelling verbatim.
Details and a suggested sentence: `docs/auto/CRITIC_LATEST.md`.

**Why this and not the three larger findings.** It is the only one that is genuinely minutes.
`docs/oracle_gap.md` is in no `SOURCES` list of the printed kit and on no build path, and no test pins any
sentence of §7, so the edit cascades into no gate. And it is 「사용된 자료에 대한 출처 명기」, a named
criterion of a 20-point row on **both** tables, failing on the page whose entire purpose is to be checkable.

## Next three rows, and why each is next

Table order at `d3ca754`. This lap spent **ZERO** §3b reorders, the second consecutive critic lap to spend
none; the ordering below uses this page's own naming power (§14: dev 「takes the row it names when it names
one with a reason」), which is reversible by one line and does not touch the table.

1. **WFG-226 (P0, KCF) is the next row to claim, unchanged from critic #57 and still `todo`.**
   `docs/auto/JUDGE_QA.md` card Q38 still tells the student to say 「오늘 저장소는 이 질문에 두 가지로
   답합니다 — 그게 결함입니다」, and the repository has given one answer since `5bcfe11`. The bank is one of
   the seven hashed sources of the printed kit, so the stale card is on paper in the booth.

2. **WFG-229 (P0, KCF) in the SAME lap, because it edits the same file and the rebuild is the cost.**
   `docs/auto/finals/TIMELINE_ROLES.md:81` now publishes 「트레일러 513개 (전체 662개 중)」, which is
   **77.5 %** of the tree, on the document that answers a named sub-item of a 20-point row on both tables.
   `grep -c 513 docs/auto/JUDGE_QA.md` answers **0**, and Q29 is a **T0** card said from memory. Either row
   alone needs `make printables` at a new stamp plus a re-pointed bundle manifest (NH-049); together they
   pay it once.

3. **WFG-228 (P0, science) behind them.** The headline of the new anchor document, IoU **0.394**, has no
   null model, and `src/wildfireguardian/validation/baselines.py` has shipped baseline machinery since
   Session 4. The cheapest null with zero free parameters is an area-matched disc, and the row writes its
   interpretation down before it looks at the answer.

**Behind those: ten inherited P0 rows and five sprint days.** Counted at this head: WFG-007, 117, 129, 121,
106, 036, 101, 119, 024, 054 are `todo`; `blocked`: WFG-213 (NH-052), WFG-124 and WFG-104 (NH-032), WFG-023
(human). **WFG-007 is still the trap** its own status cell describes (「the agent half is done; the student
half is not」), so a lap falling back to table order reaches a row with nothing takeable in it. Take WFG-117
before it, or record in the row why not.

⚠ **Filing note, and it is the same deliberate departure critic #57 made.** The stored prompt says a larger
judge-facing finding is 「filed as a P0 row at position 1」. **NH-051 is open and shows that mechanic belongs
to NH-038 option D**, while the prompt cites option **B**, whose own words put the row 「in the table like
any other」. This lap filed WFG-228, 229 and 230 in table order and named them here instead. If the author's
answer to NH-051 is D, moving them up is one edit.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not soften, hedge or withdraw `docs/oracle_gap.md` §7's argument** while fixing `:233`. Nothing is
  being withdrawn and no `WC-###` is opened; a wrong appeal to the registry sits under a correct claim.
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」** anywhere. The repository has **no**
  observation between 0 and 333 minutes (obs_times are 0 / 333 / 1005 / 1480 / 1812 / 2403) and cannot say
  when the growth happened. WFG-230 is the row that says this properly.
- ⚠ **Do not "fix" 「household-level」 in `README.md:3`, `CITATION.cff:5`,
  `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1`.** They name the **application**, not a
  per-household result, `paper/GAPS.md:389` records the ruling, and WC-013 deliberately registers no
  spelling for the bare term. **WFG-231** moves the ruling to where a lap will find it.
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a clone you deepened.**
  Re-measured here: `web/finals.html`'s 개발 일정과 역할 card prints its as-of stamp from that artifact's
  `last_commit_date` (**2026-09-09** at this head), so the guardrail freezes a date a judge reads, and the
  finals are 2026-10-24. A rebuild from a **fresh full clone** writes seven-character anchors and is safe.
  **WFG-217** is the fix; its deadline is the 10-16 freeze.
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets.** `done` (WFG-222,
  `WC-013`); the corrected wording is **지점 단위** with 「화재 위험면과 지형은 합성 · 출발지는 표본 좌표」 and
  「실제 확산면으로 만든 출동 지시서는 아직 없습니다」 **in the same block**. `README.md:220-251` is the model.
  The four remaining 「가구 단위」 in `docs/auto/JUDGE_QA.md` are **deliberate and correct**. Do not "fix" them.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** NH-053 is open. Describe the mechanism.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open. Re-measured by the section headers rather than copied: 「### 1. 가장 강한 주장에
  「공정한 상대」를 세웠습니다」 opens the block at **`:274`** and 「### 2. 철회한 주장이…」 closes it at
  **`:354`** at `d3ca754`. ⚠ **The two ends moved differently this window for the first time** — the opener
  held and the closer moved down one line, so the block grew rather than slid, and a lap that memorised
  critic #57's pair (274, 353) now protects one line too few. The single 「구체적인 margin 값들은 부스에서
  말하지 않습니다」 line is at **`:340`**, unmoved. **Anchor on the two headers, not on the digits.**
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one.** NH-037 came due **2026-09-10** and
  is open; `paper/check_paper.py` reads the body against a 9,000-word hard fail with single-digit margin.
- **Do not change `mr_uiseong_fa_exceeds_budget`.** It is 2, it is registered, NH-031 option A says nothing
  committed moves, and the registry half is **WFG-122** (`todo`). WFG-225 added a caveat to the screen and
  moved no value.
- **Do not refit anything**, and do not regenerate a committed artifact (CHARTER §3 rule 2).
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** The differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the fifteenth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. Re-counted from the checklist table at `:1825-1836`
(its position after this lap's own append to that page) rather than inherited: R1, R2, R4, R5,
R6, R7, R8, R9 ticked; R3, R11, R12 not; R10 withdrawn 2026-09-04. The cause is unchanged: R12 is the
author's (NH-014); R3 is `blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b until R1, R3, R4,
R7, R8 and R9 all tick, of which **R3 is the only one unticked**. **NH-046 came due 2026-09-10 and is now
one day past due, and the sprint ends 2026-09-15.** Appended to NH-046; not filed again as a new entry.

**Open decisions: 20 for the author (19 DECISION + 1 BLOCKER), 5 FYI besides, and 13 at or past their date**
— NH-032, 034, 045 (09-08), NH-035, 038, 043, 044 (09-09), NH-036, 037, 042, 046, 048, 050 (09-10). ⚠ Two
open entries (**NH-005, NH-014**) carry **no date at all** and drop out of any date-based count silently;
say 「13 of 20, and 2 undated」 rather than a bare number. Counted at `d3ca754` by status prefix over the
table between the header row and `## Details`: **P0 is 66 done, 4 blocked, 1 dropped and 14 `todo`** — ten
inherited (WFG-007, 117, 129, 121, 106, 036, 101, 119, 024, 054), one from critic #57 (WFG-226) and three
filed here (WFG-228, 229, 230). **P1 is 9 done against 102 `todo`**, up one this lap, and mine is the 102nd.
The P1 queue remains a write-only ledger on the measured rate; that is NH-038 and it is the author's.

## Critic's last direction note

**2026-09-10T1120Z, critic #58. ZERO §3b reorders, the second consecutive critic lap to spend none. ONE
`fix-before-next-row` item (`docs/oracle_gap.md:233`, a false appeal to the registry under a correct claim,
pure prose). FOUR new backlog rows (WFG-228, 229, 230 as P0 science/KCF; WFG-231 as P1), none at position 1.
ZERO new NEEDS_HUMAN entries; three existing entries gained measurements (NH-046, NH-038, NH-049) and two
existing backlog rows did (WFG-119, WFG-107). Scorecard: Track B 95 HELD (제출 자료 UP to 20,
데이터 수집·분석·해석 DOWN to 19 on WFG-228, offsetting); Track A 94 → 95 (제출 자료 UP to 18).**

Verified at `d3ca754`. `gates.py --mode full` exits **0** (**2016 passed**, 64 skipped, 3 xfailed, pytest
**299.1 s**, up 31 tests and 183 seconds FASTER than critic #57's run, which is worth knowing before a lap
reads a slow suite as a regression); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts,
which is NH-029 and §3d working. **GitHub `auto-gates`, runs 301 to 327: 27 runs, 20 `success`, 7
`cancelled` (306, 310, 312, 316, 317, 320, 326 — each superseded by the next push within minutes) and ZERO
`failure`**, with **327 green at this exact head**, so CHARTER §4b sets no finding #1 for the seventh
consecutive lap. **All eight** dev reports in the window record `Reviewed by:`, all eight name `subagent`,
and **seven of the eight record `block`**. **Every push in the window carried a report**:
`gates.py --assert-reported` over the twelve consecutive pushed heads `16f3525` → `d3ca754` returns twelve
OK. The clone was **unshallowed** before any counting (`--is-shallow-repository` answers `false`, 712
commits) because it arrived at depth 50 again and 50 commits is almost exactly the 24-hour window.
