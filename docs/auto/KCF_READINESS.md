# KCF readiness — the final product's definition of done

The critic lap ticks every line daily with a commit or file as evidence, in the
`evidence` column; an unticked line is a finding, and the product is not ready
until every line is ticked. The dev laps work WFG-036 until it is. Dates: freeze
2026-10-16, finals 2026-10-24 (김대중컨벤션센터, Gwangju, offline booth).

**Tick count, critic #61, 2026-09-10T2000Z at `be39dea`: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), HELD.
R3, R11 and R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** ⚠⚠ **ZERO lines ticked, for
the EIGHTEENTH consecutive critic lap.** The count has stood at 8 since critic #43 ticked R8 at
2026-09-08T1429Z, and **the sprint ends 2026-09-15, five days out**. ⚠ This lead is rewritten by the lap
that appends below it, which is what WFG-238 asks a gate to enforce; until that gate exists it is done by
hand, deliberately, in the same commit as the append.


**Critic #61's re-read, 2026-09-10T2000Z at `be39dea`, counted from the checklist table rather than
inherited from the line above it.** ⚠ **This window could tick nothing by construction and saying so is the
point:** `71e95ee..be39dea` holds one research lap and four report or archive commits, no code, no data, no
figure and no judge-facing artifact. A window with nothing to tick against is not a direction failure; a
window with something to tick against and no tick would be.

- **R1 holds.** `web/finals.html` is offline by gate inside the green `gates.py --mode full` at this head
  (**2042 passed**, 63 skipped, 3 xfailed, pytest 282.0 s), and its stamp is unchanged from critic #60's
  reading because nothing rebuilt it. R1's other half asks that every on-screen number map to a registry
  key; no number reached the screen this window.
- ⚠⚠ **R7 and R9 hold on their own criteria, AND this lap used the same seven-of-seven hash to prove a
  judge-facing defect, exactly as critic #57 did.** `docs/auto/finals/printables/manifest_20260910T1233Z.json`
  declares seven `sources` and **all seven hash equal to the tree**, re-computed in this lap's own process;
  `release/kcf-finals-2026/MANIFEST.json` is unmoved and its gates are green. **That equality is what makes
  WFG-240 provable rather than suspected:** `docs/auto/finals/RELATED_WORK_PANEL.md` is one of the seven, so
  `WFG_printables_20260910T1233Z.pdf` carries `:46`'s 「공간 단위는 **가구(집)**」 and `:119-120`'s 「농촌
  **가구 단위의 도보 대피**」 onto the paper a judge is handed, 73 lines below the same file's own ⚠
  2026-09-10 정정 block, which scopes itself to 「**이 문단**」 and narrows the same register to 지점 단위 at
  `:23`. **A hash gate proves the paper matches the repository; it cannot prove the repository agrees with
  itself.** R7's criterion is that the printables exist and match, and they do, so **no tick is removed**;
  this is a 제출 자료 deduction and a P0 row.
- **R5 holds and gains a second named staleness beside WFG-226's.** Every T0 answer cites a file and no
  purged phrasing remains; `tests/test_judge_qa_bank.py` is green in the run above. What a green bank gate
  cannot see is a card that is complete and out of date: `docs/auto/JUDGE_QA.md:1246-1247` (Q29a, 없는 것
  item 4) tells the student 「그 범위 밖에서 같은 일을 한 연구가 있는지는 모릅니다」, and since 2026-09-10 the
  repository holds one that did (**WFG-241**). Not an untick, and named here so the next lap does not read a
  green bank gate as a current bank.
- **R3, R11 and R12 are unchanged and none is a lap's to move.** R12 is the author's (NH-014). R3 is
  `blocked(NH-046)`, and **NH-046 is due TODAY, 2026-09-10; it is NOT overdue**, which critic #60 corrected
  on two pages and this lap re-checked at the entry's own heading. R11's **WFG-024** is held by CHARTER §14b
  until R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**, so 102 P1 rows wait on
  one entry with five sprint days left. Eighteenth consecutive lap this paragraph is true; appended to
  **NH-046** rather than filed again.

⚠ **No `Do NOT edit` note is written on this page by this lap** (CHARTER §14c). There is nothing here a lap
would be tempted to edit wrongly today, and a note that froze the checklist table would block WFG-238.


*(Superseded lead, kept as the record, CHARTER §3 rule 7.)* **Tick count, critic #60, 2026-09-10T1657Z at `71e95ee`: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), HELD.
R3, R11 and R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** ⚠⚠ **ZERO lines ticked, for
the SEVENTEENTH consecutive critic lap.** The count has stood at 8 since critic #43 ticked R8 at
2026-09-08T1429Z, and **the sprint ends 2026-09-15**.

⚠ **This lead was one lap stale when critic #60 read it, and that is WFG-238.** It said 「critic #58 ...
FIFTEENTH」 while this file's own newest section, then at `:1841`, said 「critic #59 ... SIXTEENTH」.
Critic #59 appended its section and left the lead alone, which is the WFG-107 shape critic #58 had named
one lap earlier at `:12-16`. Nothing binds the two together; WFG-238 (P1, held by CHARTER §14b behind R3)
is the gate that would.

**Critic #58's re-read, 2026-09-10T1120Z at `d3ca754`. Counted from the checklist table at
`:1825-1836` (its line numbers AFTER this lap's own append, which is why they are quoted with that
condition rather than bare) rather than inherited from the line above it,** which matters because that line is prose beside a table and
this repository has now paid for that shape six times (WFG-107). The eight ticked lines are R1, R2, R4, R5,
R6, R7, R8 and R9; R3, R11 and R12 are unticked; R10 is struck through.

- **R1 holds, and its two halves were checked separately.** `web/finals.html` is offline by gate in the same
  green `gates.py --mode full` run as everything else here (**2016 passed**, 64 skipped, 3 xfailed at
  `d3ca754`), and its build stamp is `53d1a4e`, well inside `tests/test_finals_screen.py`'s staleness limit.
  R1's other half asks that every on-screen **number** map to a registry key: WFG-225 added two surfaces to
  the screen this window and **neither writes a number** — the `renderPanel()` pointer and the `rel(...)`
  card both state a rule and name no value — so R1 is not touched by the change. Verified by reading the
  built file rather than the template: the caveat string appears **twice** in `web/finals.html` and twice in
  `scripts/finals.template.html`.
- **R5 holds but is closer to the edge than it was, and the reason is a row, not a doubt.** R5 asks that
  every T0 answer cite a file and that no purged phrasing remain; `tests/test_judge_qa_bank.py` is green in
  the run above. What the gate cannot see is a T0 card that is *complete* and *out of date*: **Q38 is stale**
  (WFG-226, `todo`, filed by critic #57 and still open a full window later) and **Q29 · T0 carries none of
  the 513-of-662 arithmetic** `docs/auto/finals/TIMELINE_ROLES.md:81` now publishes (WFG-229, filed here).
  Neither is an untick — both cards cite files and neither says anything purged — and both are named here so
  the next lap does not read a green bank gate as a current bank.
- **R7 and R9 hold.** The printed kit's seven hashed `SOURCES` still equal the tree, which is exactly how
  WFG-226's staleness is provable rather than suspected: the bank has not moved since the `0140Z` print, so
  the print carries the same stale card. `release/kcf-finals-2026/MANIFEST.json` was re-pointed by the 0952Z
  lap and the bundle rebuilds. ⚠ A seven-of-seven means the kit matches the tree, **not** that the tree is
  right; critic #57 wrote that and it is re-stated here because it is what makes WFG-226 legible.
- **R3, R11 and R12 are unchanged and none is a lap's to move.** R12 is the author's (NH-014). R3 is
  `blocked(NH-046)` and its criterion names `make all-checks`, a command that cannot go green on any clone
  but the author's; **NH-046 came due 2026-09-10 and is now one day past due**. R11's row **WFG-024** is held
  by CHARTER §14b until R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. So the
  whole P1 block, 102 rows, waits on one entry in the author's queue with five sprint days left. That is the
  fifteenth consecutive lap this paragraph has been true, it is a finding about the loop's direction rather
  than about the product, and it is appended to **NH-046** rather than filed again.

⚠ **No `Do NOT edit` note is written on this page by this lap.** CHARTER §14c makes such a note expire at
the next critic lap unless re-checked, and there is nothing on this page that a lap would be tempted to
edit wrongly today.

**Tick count, critic #57, 2026-09-10T0825Z at `16e6824`: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), HELD.
R3, R11 and R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** ⚠⚠ **ZERO lines ticked, for the
FOURTEENTH consecutive critic lap.** The count has stood at 8 since critic #43 ticked R8 at 2026-09-08T1429Z.

**Critic #57's re-read, 2026-09-10T0825Z at `16e6824`. This lap re-hashed the two hand-over objects rather
than re-describing the count, and it found the one thing a hash cannot see.** **R7 and R9 hold on
arithmetic:** `release/kcf-finals-2026/MANIFEST.json` declares nineteen files and the printed kit is still
`WFG_printables_20260910T0140Z.pdf`, whose **seven** declared sources I re-hashed against the tree —
`docs/auto/finals/BOOTH_SETUP.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/JUDGE_QA.md`,
`docs/submission_reconciliation.md`, `docs/auto/finals/DETECTION_FLOOR_CARD.md`, `docs/creativity_card.md`,
`docs/auto/finals/RELATED_WORK_PANEL.md` — **seven of seven matching**, so nothing printed has drifted from
the repository. ⚠⚠ **AND THAT IS EXACTLY HOW THIS LAP PROVED THE KIT IS STALE.** Seven-of-seven means the
bank has not moved since the 0140Z print; card **Q38** at `docs/auto/JUDGE_QA.md:1421` still tells the
student to say 「오늘 저장소는 이 질문에 두 가지로 답합니다 — 그게 결함입니다」 about `fa_exceeds_budget`, and
`5bcfe11` closed that contradiction at 06:57Z. **A hash gate proves the paper matches the repository; it
cannot prove the repository was right when the paper was made.** R7 stays ticked because its own criterion is
about the printables existing and matching, and that criterion is met — but **WFG-226** is filed, and critic
#58 should not read a seven-of-seven as evidence the kit is current. **R1 holds and its staleness margin was
measured, not assumed:** `web/finals.html`'s build stamp names `97978fe`, **4** commits behind this head
against the 30-commit limit `tests/test_finals_screen.py` enforces, and the screen is offline by gate inside
the same green `gates.py --mode full` run (**1985 passed**, 64 skipped, 3 xfailed). ⚠ **R1's other half is
where WFG-225 lives:** every on-screen number maps to a registry key, and **◆ 예산 초과 2** does map to
`mr_uiseong_fa_exceeds_budget` — the defect is not the mapping, it is that the screen prints the number with
none of the caveat the README and `docs/multi_region.md` acquired six hours earlier. That is a 제출 자료
deduction and not an R1 untick, and the distinction is critic #53's. **R3, R11 and R12 are unchanged and none
is a lap's to move:** R12 is the author's (NH-014), R3 is `blocked(NH-046)` and **NH-046 came due 2026-09-10
and is open**, and R11's row WFG-024 is held by CHARTER §14b behind R3, which is now the only unticked line
of the six that gate it.

**Critic #56's own re-read, 2026-09-10T0523Z at `9b7d21c`, and this lap tests two lines on content rather than
re-describing the count.** The window closed **three P0 rows** (WFG-222, WFG-218, WFG-220), added **17** tests
(`gates.py --mode full` exits 0 with **1958 passed**, 64 skipped, 3 xfailed) and rebuilt the finals screen
twice. **R1 holds and its staleness margin was measured, not assumed**: `web/finals.html`'s build stamp names
`4cb7cf7`, which is **5** commits behind this head against the 30-commit limit `tests/test_finals_screen.py`
enforces, and the screen is offline by gate in the same green run. **R7 and R9 hold, and I tested the
hand-over objects rather than their existence**: `release/kcf-finals-2026/MANIFEST.json` was re-pointed in the
same commit as the screen rebuild, and I re-hashed **all nineteen** declared files against their sources,
**nineteen of nineteen matching**, including the rebuilt `web/finals.html`; the printed kit is still
`WFG_printables_20260910T0140Z.pdf` and its **seven** sources still hash equal to the tree, **seven of seven**,
because `README.md` and `web/finals.html` are not printed sources and this window's judge-facing work landed on
those two. **R3, R11 and R12 are unchanged and none is a lap's to move**: R12 is the author's (NH-014), R3 is
`blocked(NH-046)`, R11's row **WFG-024** is held by CHARTER §14b until R1, R3, R4, R7, R8 and R9 all tick, of
which **R3 is the only one unticked**, and **NH-046 came due 2026-09-10 and is open**.

⚠ **The judge-facing defect this lap found is NOT a readiness line, and I checked each line's own criterion
before saying so.** `docs/oracle_gap.md` §4 reads a size-ratio series as forecast behaviour when three of its
four slices are graded against the same 333-minute observation (confirmed against
`data/processed/oracle_gap_yeongdeok.json` this lap), and that document became the anchor of the **first** card
of the finals screen's 알려진 한계 panel at `c4eb8d2`. **R1** asks that the screen open offline and that every
on-screen **number** map to a registry key; the new card carries no number. **R5** asks that every T0 answer
cite a file and that no purged phrasing remain; Q36 cites its files, and nothing in that document is a
registered withdrawn spelling. **R7** and **R9** ask that the kit and the bundle exist and rebuild, not what
the documents they cite conclude. So this is a scorecard deduction (Track B 데이터 수집·분석·해석, 20 to 19) and
this lap's one `fix-before-next-row` item, and **no tick is removed**.

⚠ **One line of this page's own guardrail went stale this window and is corrected rather than carried**: the
`Do NOT edit` bounds on the README's fair-opponent block moved from `263-342` to **`270-349`**, because
WFG-218 inserted seven lines above the block. Re-measured in `CRITIC_LATEST.md` at this head.

**Critic #55's tick count, 2026-09-10T0237Z at `7dabdef`: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), HELD.
R3, R11 and R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** ⚠⚠ **ZERO lines ticked, for
the TWELFTH consecutive critic lap.** The count has stood at 8 since critic #43 ticked R8 at 2026-09-08T1429Z.

**Critic #55's own re-read, 2026-09-10T0237Z at `7dabdef`, and this is the window that shows what the count is
actually measuring.** The window closed **WFG-222** on **eleven** judge-facing surfaces, added **70** tests
(`gates.py --mode full` exits 0 with **1941 passed**, 64 skipped, 3 xfailed, up from 1871), rebuilt the printed
kit twice and re-pointed the bundle manifest. **The tick count did not move, and it should not have**, because
none of that is what the three unticked lines ask about. Saying so is the point: this page is the product's
definition of done, and a day of real judge-facing work leaving it flat is information about the **lines**, not
about the day. **R1 holds**: `web/finals.html` is offline by gate and its stamp is inside
`tests/test_finals_screen.py`'s 30-commit staleness limit, green in the run above. **R7 and R9 hold, and this
lap tested them on content rather than on existence**: `release/kcf-finals-2026/MANIFEST.json` names
`WFG_printables_20260910T0140Z.pdf`, that file is tracked, `tests/test_finals_bundle.py`'s hash gates are green
in the same run, and I re-hashed **all seven printed sources** of `manifest_20260910T0140Z.json` against the
tree, **seven of seven matching** — so the corrected 지점 단위 wording is on the paper a judge is handed and not
only in the repository. **R5 holds and was re-checked directly**: critic #54's three 운영사무국 passages in
`docs/auto/JUDGE_QA.md` are corrected at `:611`, `:1162-1163` and `:1395-1397`, and the false sentence 「사무국에
질의한 항목이 NH-008입니다」 is gone, replaced by 「사무국에 질의한 적은 없습니다」 with an instruction not to
let the answer sound like the 사무국 confirmed anything. **R3, R11 and R12 are unchanged and none is a lap's to
move**: R12 is the author's (NH-014), R3 is `blocked(NH-046)`, R11's row **WFG-024** is held by CHARTER §14b
until R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**, and **NH-046 comes due
TODAY, 2026-09-10**. ⚠ The one gate defect this lap found is not a readiness line either: `check_withdrawn_claims.py`
reads one line at a time and cannot see a registered spelling that wraps across a source line break. R5 asks
that no purged phrasing remain, and none does at this head; the blind spot is a **P1** row (**WFG-223**) about
the machine's reach, and **no tick is removed**.

**Critic #54's own re-read, 2026-09-09T2319Z at `3eec471`.** R1 holds: `web/finals.html` is offline by gate and
its stamp names `89da7d3`, which `tests/test_finals_screen.py`'s 30-commit staleness gate passes inside a green
`gates.py --mode full` at this head (exit 0, 1871 passed, 64 skipped, 3 xfailed). R7 and R9 hold:
`release/kcf-finals-2026/MANIFEST.json` names `WFG_printables_20260909T1908Z.pdf`, that file is tracked, and
`tests/test_finals_bundle.py`'s hash gates are green in the same run. R8 holds: the Round-4 section gained a
lead block at 2206Z (WFG-212) and the forbidden-string and collision gates are green over it. **R3, R11 and R12
are unchanged and none is a lap's to move**, for the reasons the table below already measures; NH-046, the
single point of failure, comes due **2026-09-10 — tomorrow**.

⚠ **The judge-facing gap this lap found is NOT a readiness line, and I checked each line's own criterion before
saying so.** Four surfaces — `README.md:391-395`, `web/finals.html:1580`, `docs/auto/JUDGE_QA.md:1172` (Q29a,
T0) and `docs/auto/DEMO_SCRIPT_5MIN.md:67` — plus the printed `docs/creativity_card.md` still call the committed
dispatch sheets 「가구 단위」 / "per-household" with no bound, after `README.md:212-251` corrected the same claim
to 「지점 단위」 at 2206Z. **R1** asks that the screen open offline and that every on-screen **number** map to a
registry key; no number moved. **R4** asks that the demo script exist with per-act timings and an interruption
sentence for each judge type; it does. **R5** asks that every T0 answer cite a file and that no purged phrasing
remain; Q29a cites its files, and 「가구 단위」 **as a description of this project's own committed sheets** is
not a registered spelling in `docs/auto/withdrawn_claims.json` — the single entry containing that phrase,
`WC-008`, is about what NIFoS's console and G-DAPS do **not** compute, a different claim. So this is an
**unregistered** overclaim, which is exactly why no gate caught it and why CHARTER §5c's ratchet could not. **R7** and **R9** ask that the kit and the
bundle exist and rebuild, not what they say. So this is a scorecard deduction (제출 자료) and a P0 row
(**WFG-222**), and **no tick is removed**. ⚠ A lap that closes WFG-222 rebuilds the kit and re-points the bundle
manifest in the same lap, or R7 and R9 stop being true of the corrected text.

**Critic #53's own re-read, 2026-09-09T2023Z at `ba06467`.** R1 holds: `web/finals.html` is offline by gate and
its stamp names `89da7d3`, six commits behind this head against the 30-commit limit `tests/test_finals_screen.py`
enforces. R9 holds: `release/kcf-finals-2026/MANIFEST.json` names `WFG_printables_20260909T1908Z.pdf`, that file
is tracked, and `tests/test_finals_bundle.py`'s hash gates are green inside a full `gates.py --mode full` run at
this head (exit 0, 1862 passed). **R3, R11 and R12 are unchanged and none is a lap's to move**, for the reasons
the table below already measures; NH-046, the single point of failure, comes due **2026-09-10**. ⚠ The one new
judge-facing gap this lap found is **not** a readiness line either: `web/finals.html` carries no word of the
oracle-in-the-grader objection that four other judge-facing surfaces now state, filed as **WFG-220**. R1's
criterion is that the screen opens offline and that every on-screen number maps to a registry key; it says
nothing about which caveats the screen carries, so WFG-220 is a scorecard deduction (제출 자료) and not a tick
this lap may remove.

⚠ **This header named critic #50 at `9c22ff3` until 2026-09-09T1719Z, because critic #51 did not touch this
file.** CHARTER §11 calls this page the final product's definition of done and says the critic ticks it with
evidence every day; #51 reported the count in its own report and in `DIRECTION.md` and left the page naming
the lap before it. Nothing below is changed by that: the three unticked lines and their causes are exactly
as critic #50 measured them, re-read at `375be25` by critic #52 rather than inherited, and R3 remains the
single point of failure the table below names. Recorded here rather than filed as a row, because the repair
is this sentence.

**Critic #52's own re-read, 2026-09-09T1719Z at `375be25`.** R1 holds: `web/finals.html` is offline by gate
and its stamp is current (built at `89da7d3` by the 1619Z lap, inside the 30-commit limit
`tests/test_finals_screen.py` enforces). R9 holds: `release/kcf-finals-2026/MANIFEST.json` was re-pointed
after staging by the 1619Z lap and `tests/test_finals_bundle.py`'s hash gates are green in a full
`gates.py --mode full` run at this head. **R11 and R3 are unchanged and neither is a lap's to move.** The one
new judge-facing gap this lap found is not a readiness line: it is 일정 reading 0 on `README.md` and 0 on
`web/finals.html`, filed as **WFG-218**.

⚠⚠ **This lap stops re-describing the zero and measures its cause, which turns out to be a single point of
failure.** The three unticked lines are not three independent gaps:

| line | why it does not tick | who can move it |
|---|---|---|
| R12 | the booth recipe has not been run on the real laptop | the author (NH-014) |
| R3 | `blocked(NH-046)` — its criterion names `make all-checks`, a command that cannot go green on any clone but the author's, and no lap may reword a readiness line | the author (NH-046) |
| R11 | its row **WFG-024** is one stale sentence, `agent_doable`, `todo`, and held at table position 163 by CHARTER §14b as loop hygiene | a lap, **once R3 ticks** |

§14b releases the P1 infra block only when **R1, R3, R4, R7, R8 and R9** are all ticked. Five of those six are
ticked. **R3 is the only one that is not, and NH-046 forbids a lap from ticking it.** So R11 is downstream of
R3, R3 is downstream of NH-046, and R12 is downstream of NH-014. **There is no path from any amount of loop
work to a ninth tick.** That is not a direction failure this lap can file against the product, and it is why
this lap files no fourteenth question: NH-046 and NH-014 already ask it, in the author's own terms, and
NH-046 has carried the loop's recommendation (option A) unchanged for three laps.

✅ **R1, R2, R5 and R7 hold, and critic #49's one defect inside R1/R2 is CLOSED and verified here rather than
read from the report.** The 창의성 answer's item ① no longer anchors only on the landscape note about the
other systems. Measured at `9c22ff3` on all four surfaces: `web/finals.html`'s `CREATIVE[0].doc` reads
`outputs/dispatch/20260801T163042Z/01-거무역리공원-북쪽/dispatch_a4.html · outputs/dispatch/README.md ·
docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md §3`, with the instance **first**; `docs/creativity_card.md:36`
names the index and a named sheet, then the note with its role in parentheses; `README.md:326-355` names
`outputs/dispatch/README.md` first; and `docs/auto/JUDGE_QA.md` Q29a offers to open the file. **Every anchor
resolves** — the named sheet is tracked (`git ls-files` answers it) and every markdown link target in
`README.md:200-362` exists in the tree, checked one by one here. `tests/test_creativity_card.py` binds the
anchors' **contents** rather than their names, and the lap's own M8 mutation (a threshold no document reaches,
which made the assertion vacuously true) is now red in both directions.

✅ **R9 holds and is re-earned rather than inherited.** `release/kcf-finals-2026/` tracks two files by design
(`MANIFEST.json` and `README_KO.md`; the 19-file payload is git-ignored at `.gitignore:438-454` and rebuilt by
`make finals-bundle`, so nothing is duplicated into the tree), the manifest declares **19** files, and
`gates.py --mode full` including `tests/test_printables.py` exits 0 at this head.

Measured at `9c22ff3`. ⚠ **The routine's clone opened SHALLOW at 50 commits**, deepened with
`git fetch --shallow-since='2026-09-08T00:00:00Z'` to **90** commits, oldest resolvable `088203c` at
**00:22:53Z on 09-08** — a deepening whose predicate is the window rather than a guessed depth.
`--is-shallow-repository` still answers **true**, so **no ancestry or reachability claim is made anywhere in
this lap's output.** `gates.py --mode full` exits **0**, ALL GREEN: `1830 passed, 63 skipped, 3 xfailed`,
pytest **373.4 s**; `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029
and §3d working as decided. `--assert-head` exits 0 and `--assert-reported --base 088203c` exits 0 over **95**
substantive paths. **GitHub `auto-gates`, runs 246 to 285 — the full 24 h window, wider than critic #49's —
carries THREE `failure` runs: 253 (`0cca093`, upload-artifact 403, closed at `b2cda36`), 255 (`b7c1837`,
browser launch, closed at `298a09c`) and 260 (`7eeccab`, a debug-port race, closed at `1fa0b7f`). All three
were caught and repaired inside the hour by `wfg-autoloop-ci-red`, none was a product test failure, and run
**285** is `success` at this exact head.** By CHARTER §4b's letter those are finding #1; **no
`fix-before-next-row` item is set for them, because all three are already closed and green.** Every dev
report in the window carries `Reviewed by:`.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c as the routine prompt
states it, NH-036 A; ⚠ a search for `14c` in `docs/auto/CHARTER.md` answers **0** at this head, and both NH-036
and NH-038 are still `open` — NH-050 and this lap's NH-051).** It covers **`README.md:210-282`**, the Round-4
fair-opponent block, whose bounds this lap re-measured (「### 1.」 at **210**, 「### 2.」 at **283**), unchanged
from critic #49. It forbids exactly one thing there: putting a present-perimeter **margin value**
(9, 27, 5, 19, 86) into those lines while NH-032 and NH-034 are open. Both re-read at `NEEDS_HUMAN.md:1391`
and `:1574`: still `open`, both due 2026-09-08, so **one day overdue**. A scan of 210-282 finds no margin
value there today. **It expires at critic #51 unless that lap re-states it after re-reading them.** It
freezes no file and no question: WFG-212's lead paragraph, filed by this lap, is an edit to this very section
that the note permits, and the note is written into that row as a constraint so the next lap cannot miss it.

*(Superseded lead, kept as the record.)* **Tick count, critic #49, 2026-09-09T0820Z at `7f914fd`: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), HELD.
R3, R11 and R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** ⚠⚠ **ZERO lines ticked, for
the SIXTH consecutive critic lap.** The count has stood at 8 since critic #43 ticked R8 at 2026-09-08T1429Z.

⚠⚠ **This window is NOT the honest zero the last one was, and the difference is the finding.** Critic #48's
window contained one paper lap and three report-header repairs and had nothing to tick against. This window,
`5f4e32b..7f914fd`, contains two dev laps that closed four rows and put the 창의성 answer onto **all four**
judge-facing surfaces — `web/finals.html`, `docs/auto/DEMO_SCRIPT_5MIN.md`, the printed kit
(`WFG_printables_20260909T0700Z.pdf`, **7** `SOURCES` now including `docs/creativity_card.md`,
`release/kcf-finals-2026/MANIFEST.json` re-pointed) and `README.md` §5 — and put the repository's address onto
the USB (WFG-208). **It ticked nothing, because none of the three unticked lines has a condition this window
could meet.** R3 is `blocked(NH-046)`, R12 is the author's (NH-014), and R11's row **WFG-024** is `todo`,
agent-doable and one stale sentence long, sitting at **table position 125** where CHARTER §14b holds it as
loop hygiene. **The only readiness line still in the loop's reach is held shut by the loop's own ordering
rule.** That measurement is written into **NH-038**, which asks exactly this in the author's words and is due
today, rather than into a new entry.

✅ **R5 and R7 hold and both got stronger, re-hashed rather than read.** The kit is
`WFG_printables_20260909T0700Z.pdf`; `release/kcf-finals-2026/MANIFEST.json` names that exact PDF, and the
manifest's `SOURCES` list is `BOOTH_SETUP.md`, `DEMO_SCRIPT_5MIN.md`, `JUDGE_QA.md`,
`submission_reconciliation.md`, `DETECTION_FLOOR_CARD.md`, **`docs/creativity_card.md`** and
`RELATED_WORK_PANEL.md` — seven, up from six, the seventh being the 창의성 card WFG-194 added.

✅ **R9 keeps its tick and critic #48's quality defect on it is CLOSED.** `release/kcf-finals-2026/README_KO.md`
now opens with one block saying that backticked `docs/…` / `scripts/…` / `outputs/…` paths are paths **in the
repository and not in this folder**, naming the repository URL once and `auto/dev` as the branch it was built
from; a count of `github.com` in that file answered **0** before and answers **1** now.
`make finals-bundle` still rebuilds byte-identically at **19** files, and no document was added to the payload.

⚠ **R1 and R2 keep their ticks and this lap files a defect inside the block that just landed on the screen.**
`web/finals.html`'s 「시스템 구조」 view now carries a 창의성 block whose item ① reads
「내놓는 것은 지도가 아니라 판정입니다 … 마을 단위 출동 목록입니다」 and whose `doc` anchor is
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3 — a landscape note about NIFoS and G-DAPS, carrying **34**
mentions of the systems `tests/test_creativity_card.py:86` makes red in the spoken draft and **12** of their
announced percentages. **This does NOT un-tick either line** — R1's condition is that the screen opens offline
and its numbers map to registry keys, and it does — it is **WFG-210**, filed at position 1, and its README half
is this lap's one `fix-before-next-row` item, minutes.

Measured at `7f914fd`. ⚠ **The routine's clone opened SHALLOW at 50 commits**, deepened with
`git fetch --shallow-since='2026-09-08T00:00:00Z'` to **83** commits, oldest resolvable `088203c` at
**00:22:53Z on 09-08** — a deepening whose predicate is the window rather than a guessed depth.
`--is-shallow-repository` still answers **true**, so **no ancestry or reachability claim is made anywhere in
this lap's output.** `gates.py --mode full` exits **0**, ALL GREEN: `1826 passed, 63 skipped, 3 xfailed`,
pytest **470.7 s**; `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029
and §3d working as decided. `--assert-head` exits 0 and `--assert-reported --base 088203c` exits 0 over **90**
substantive paths. GitHub `auto-gates`, the sixteen runs of this window ending at **279**: **zero
`failure`**; 275 and 278 are `cancelled`, each superseded by the next push, and run **279** is `success` at
this exact head. **No CHARTER §4b finding.**
Every dev report in the window carries `Reviewed by:`.

⚠ **The one `Do NOT edit` note, RE-STATED after re-reading its premise (CHARTER §14c as the routine prompt
states it, NH-036 A; both NH entries are still `open`, which is NH-050).** It covers **`README.md:210-282`**,
the Round-4 fair-opponent block, whose bounds this lap re-measured (「### 1.」 at 210, 「### 2.」 at 283) and
which are unchanged from critic #48's corrected range. It forbids exactly one thing there: putting a
present-perimeter **margin value** (9, 27, 5, 19, 86) into those lines while NH-032 and NH-034 are open. Both
re-read at `NEEDS_HUMAN.md:1391` and `:1574`: still `open`, both due 2026-09-08, so **one day overdue** —
critic #48 wrote 「two days」 and the 0654Z dev report 「three days」, and the correct figure is one. A scan of
210-282 finds no margin value there today. **It expires at critic #50 unless that lap re-states it after
re-reading them.** It freezes no file and no question: `README.md:326-355` was written four lines below it this
window, which is the kind of edit it permits.

*(Superseded lead, kept as the record.)* **Tick count, critic #48, 2026-09-09T0526Z at `5f4e32b`: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), HELD.
R3, R11 and R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** ⚠⚠ **ZERO lines ticked, for
the FIFTH consecutive critic lap.** The count has stood at 8 since critic #43 ticked R8 at 2026-09-08T1429Z,
and #44, #45, #46, #47 and #48 each ticked nothing.

**This lap's window is the honest reason, and it is not a direction failure.** The window `86f8929..5f4e32b`
contains one paper lap (`4b0010a`, manuscript §4.5) and three commits repairing a report header. The one dev
lap in it, `9a97e53`, is a bare claim of WFG-194 and was still running when this lap read the tree, so its work
is not in the window at all. **No readiness line has a surface in this window to tick against.** Saying it moved
would be a courtesy, and this page does not pay those.

⚠ **R9 keeps its tick and gains a defect, measured at `5f4e32b`.** R9's criterion is that the bundle exists
with the named contents, and it does: `make finals-bundle` rebuilds `release/kcf-finals-2026/` byte-identically,
19 files, exit 0. What this lap measured is a quality defect inside a criterion that still passes:
`release/kcf-finals-2026/README_KO.md` cites **15** repository paths, **7** of which exist in the tree and are
**not** in the bundle, and a count of github.com in that file answers **0**. The printed kit in the same folder
cites **105** repository paths from `docs/auto/JUDGE_QA.md`, of which **102** exist and **3** are in the bundle.
On the student's own laptop all of them resolve, because BOOTH_SETUP §1 has the full clone there; on the USB a
judge carries away, they do not, and there is no address at which to look. **This does NOT un-tick R9** and this
lap will not pretend it does; it is **WFG-208** and this lap's one `fix-before-next-row` item, minutes.

⚠ **NH-038, which was written about exactly this zero, came due today (2026-09-09) and is still `open` in
this repository, and this lap found the reason it may never be answered here: it looks as if you already
answered it.** See **NH-050**. This routine's own stored prompt binds it to 「§14b ... as amended 2026-09-07 by
NH-038 B」 and to a 「CHARTER §14c ... NH-036 A」 that does not exist in `docs/auto/CHARTER.md` (a search for
`14c` there answers **0**). So the zero-tick finding and the decision that would resolve it have been passing
each other for two days.

⚠ **Part of the cause is now measured rather than guessed, and it is bookkeeping.** R11's row is **WFG-024**,
and it had been `blocked(WFG-022, WFG-023)` since 2026-09-04. Neither blocker gates the work: WFG-022's own
blocker **NH-008 was closed by the author on 2026-09-04** (verbatim: 「Everything is fine here. Don't worry
about this, and continue with the project.」, and the closing lap recorded 「No contact with the 운영사무국
will be made」), and the branch decision WFG-023 was to ratify is settled in CHARTER §3 rule 1 and §4c.
WFG-022 is now `dropped` on the author's own words, WFG-023 records which three of its five items are
discharged, and **WFG-024 is `todo`**. R11 still does not tick — the defect is real and unfixed — but it is
no longer waiting on anyone. **The live defect, measured at this head:** `docs/HANDOFF_ROUND3.md:898` is rule
1 of the §5 block that `CLAUDE.md` and CHARTER §3 bind every lap to, and it reads 「Never push to `Main`. All
work stays on `round3-dev`.」 R3 remains blocked by NH-046; R12 is the author's (NH-014).

Measured at `86f8929`. ⚠ **The routine's clone opened SHALLOW at 50 commits**, reading back only to
2026-09-08T08:28Z, which would have hidden a third of the 24 h window. It was deepened with
`git fetch --shallow-since='2026-09-08T00:00:00Z'` to **66** commits, oldest resolvable `088203c` at
**00:22:53Z on 09-08** — **a deepening whose predicate is the window itself rather than a guessed depth**,
which is the control CHARTER §4 warns is missing when a lap guesses 120 or 250. `--is-shallow-repository`
still answers **true**, so **no ancestry or reachability claim is made anywhere in this lap's output.**
`gates.py --mode full` exits **0**, ALL GREEN: `1806 passed, 63 skipped, 2 xfailed`, pytest **348.2 s**;
`baseline-verify` WARNs on the two `data/raw/**` contract files that are git-ignored and cannot exist in any
sandbox, which is NH-029 and §3d working as decided. GitHub `auto-gates` runs **256 to 267**: one `failure`,
run **260** at `7eeccab`, already closed by `1fa0b7f` and reported by the 2231Z ci-red lap; **run 267 is
`success` at this exact head**. The printed kit is `WFG_printables_20260909T0055Z.pdf` and **all six of its
`SOURCES` re-hash to the tree**. The finals screen's stamp `97231a1` is **14** commits behind against a limit
of **30** — headroom 16, down from 24 two hours ago, and this is the third readiness cycle in which that
number has been the quietest live clock in the project.

*(Superseded lead, kept as the record.)* **Tick count, critic #46, 2026-09-08T2340Z: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), held. R3, R11 and R12
are the three that do not tick; R10 was withdrawn 2026-09-04.** Re-measured at `cb9fcc3` on the routine's
**default** clone before any deepening: `is-shallow-repository` = **true**, `rev-list --count HEAD` = **55**,
oldest resolvable `24f914f` at **03:21:30Z on 09-08**, so this clone reads about **20.3 hours** and I claim
nothing older and **no ancestry claim at all**. `gates.py --mode full` exits **0**, ALL GREEN: `1786 passed,
63 skipped, 2 xfailed`, pytest **346.6 s**. `git ls-remote origin Main` answers **`cb9fcc3`**, so `Main` is
following (CHARTER §4c).

- ⚠⚠ **THIS LAP'S OWN CORRECTION, recorded here because a readiness page is a record.** I first measured this
  window at `7cfe29a` (23:00Z) and wrote that the 21:17Z dev lap had claimed WFG-199 and WFG-127 and died: a
  pushed claim at `97231a1`, no work commit, no report, 1 h 43 m elapsed. **The evidence was real and the
  inference was wrong.** The lap was slow, not dead; it pushed `9170a37` at about 23:20Z and closed **both**
  rows. Nothing was pushed carrying the wrong finding. NH-035 already records the 2026-09-05 lap that
  「looked dead for 1 h 45 m and was only slow」, which is why §5b's window is three hours; I quoted that
  sentence in the draft and drew the opposite conclusion anyway.
- ✅ **R1 and R9 keep their ticks and the countdown two critic laps recorded is GONE.** WFG-199 closed at
  `9170a37`: `make finals` re-stamped `web/finals.html` onto `97231a1`, a commit reachable from
  `origin/auto/dev` as the row requires, and `git rev-list --count 97231a1..HEAD` answers **8** against
  `tests/test_finals_screen.py:540`'s limit of **30**. The series across four readings is 16 (1700Z), 22
  (2000Z), 27 (2300Z), **8** (here). NH-045's third replay did not happen.
- ✅ **R5 and R7 hold and both got stronger, and I re-hashed rather than read.** The kit is
  `WFG_printables_20260908T2156Z.pdf` with `release/kcf-finals-2026/MANIFEST.json` re-pointed at it in the
  same lap (WFG-152), and **all six `SOURCES` re-hash to the tree in one process**: `BOOTH_SETUP.md`,
  `DEMO_SCRIPT_5MIN.md`, `JUDGE_QA.md`, `submission_reconciliation.md`, `DETECTION_FLOOR_CARD.md`,
  `RELATED_WORK_PANEL.md`. The bank is **46** cards, unchanged in count, with Q37 rewritten from 「다섯
  가지 · 구분할 수 없습니다」 to 「여덟 가지 · 어깨 모양」 in the same commit that rebuilt the kit.
  ⚠ **What R5 still does not cover, measured:** `grep -ciE 'Ready.?Set.?Go|화선|8시간'` is **0** on the bank,
  the screen and the script, and no card asks why the horizon is 3 to 12 hours (**WFG-197**).
- ✅ **R1's browser evidence got STRONGER this window and I checked it on a second machine.** `1fa0b7f`
  replaced the substring skip critic #45 flagged with an `isinstance` check on a `BrowserLaunchError` raised
  at exactly one site, and removed the `_free_port()` TOCTOU race by asking Chromium for port 0 and reading
  `DevToolsActivePort`. `auto-gates` run **261**'s `finals-acts` job ran both steps to `success` on a clean
  `ubuntu-latest` runner. **WFG-196's residual risk is substantially discharged.** ⚠ It shipped with **no
  independent reviewer** (`docs/auto/reports/2026-09-08T2231Z-manual.md` contains 「Reviewed」 zero times
  while its commit changed 152 lines of driver and test); filed onto **WFG-147**.
- ⚠ **No CHARTER §4b finding.** `auto-gates` runs **246 to 263** on `auto/dev` carry three `failure`s, all
  three closed inside the window: 253 (`upload-artifact` 403, WFG-193), 255 (browser, closed by `298a09c`)
  and 260 (`7eeccab`, the port race, closed by `1fa0b7f`). Runs **262** and **263** are `success` at the two
  newest heads.
- ⚠ **R3 is unchanged and unchangeable by any lap, for a fourth consecutive window.** Its row is **WFG-179**,
  `blocked(NH-046)`, and NH-046 is due 2026-09-10 and still open. R3 is the last of CHARTER §14b's six lines,
  so the P1 infra block still waits on one reply. R11 and R12 are likewise the author's (R12 is NH-014).
- **Readiness lines ticked inside the last 24 h: ONE (R8, at `dee1bc1`, by critic #43 at 1429Z).** The
  「zero across two consecutive critic laps」 direction finding does **not** fire. None ticked in this
  three-hour window, and unlike the last two windows the reason is not that nothing happened: the window
  closed two P0 rows and ran a measurement against the project's own interest. The three lines that do not
  tick are all the author's.
- ⚠ **The one `Do NOT edit` note is RE-STATED and its LINE RANGE WIDENED to match the block that grew**
  (CHARTER §14c, NH-036 A). It lives in `CRITIC_LATEST.md`, covers `README.md:220-247` only, forbids
  **present-perimeter margin values (9, 27, 5, 19, 86)** in those lines while NH-032 and NH-034 are open
  (both re-read, both still `open`, both due today), and expires at critic #47 unless that lap re-states it.
  It freezes no question: **WFG-201 must edit those very lines**, and that edit is a sentence about how the
  number is chosen, not a margin value.


*(Superseded lead, kept as the record.)* **Tick count, critic #45, 2026-09-08T2000Z: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), held. R3, R11 and
R12 are the three that do not tick; R10 was withdrawn 2026-09-04.** Re-measured at `9c24a8b` on the routine's
**default** clone before any deepening: `git rev-parse --is-shallow-repository` = **true**, `git rev-list
--count HEAD` = **50**, oldest resolvable `088203c` at **00:22Z on 09-08**, so this clone reads about **19.6
hours** and I claim nothing older and **no ancestry claim at all**. `gates.py --mode full` exits **0**, ALL
GREEN: `1763 passed, 63 skipped, 2 xfailed`, pytest **322.5 s**. `--assert-head` exits 0;
`--assert-reported --base 088203c` exits 0 over **56** substantive paths.

- ✅ **CHARTER §4b: NO finding, and it is the first clean reading this week.** Through the GitHub MCP,
  `auto-gates` runs **240 to 257** on `auto/dev`: **16 `success`, 2 `failure`**, and both failures are
  closed inside the window. Run **253** (`0cca093`) was the `upload-artifact` 403 critic #44 filed as
  WFG-193; `b2cda36` put `continue-on-error: true` on 「Keep the gate record」 and run 254 then uploaded
  2,238,011 B and 9,792 B an hour later, which settles that 403 as **transient** and retires the
  ~555 MB quota theory the 1737Z lap had built. Run **255** (`b7c1837`) was a browser that never listened
  on its debugging port, closed by `298a09c`. Run **257** at this head is `success`, and **`git ls-remote
  origin Main` answers `9c24a8b`** — `Main` is following the last gate-certified commit again (CHARTER §4c).

- ⚠ **R1 keeps its tick and this lap attaches ONE measured risk to it rather than a defect.** R1's shipped
  browser evidence has two surfaces and both just got softer in the same 24 h: `tests/test_finals_acts.py`
  now **skips** when Chromium is found but never exposes a debugging port, and the `finals-acts` job carries
  `if-no-files-found: warn`, so a Chromium that stops starting permanently would take both surfaces quiet
  with nothing going red. The lap that made the trade filed it as **WFG-196** itself. I checked the
  discrimination rather than taking the commit message: `page_target()` has exactly one call site
  (`scripts/check_finals_acts.py:313`), against `about:blank`, **before** `Page.navigate` reaches
  `web/finals.html`, so the skipped error is unreachable from anything the screen does, and a JS throw still
  raises and still fails. **The trade is sound and R1 is not docked.**

- ⚠ **R1 and R9 carry a live clock, and it is this lap's one `fix-before-next-row` item (WFG-199).**
  `web/finals.html` names `25f6b60` and `git rev-list --count 25f6b60..HEAD` answers **22** against
  `tests/test_finals_screen.py:540`'s limit of **30**. Critic #44 measured **16** three hours earlier: about
  two commits an hour. `make finals` in the next dev lap, before it claims.

- ⚠ **One readiness line was ticked in the 24 h window and none in the last three hours.** R8 was ticked by
  critic #43 at 1115Z (`dee1bc1`) and holds here — re-derived, not read: `grep -nE '^## Round' README.md`
  answers `:59`, `:75` and **`:200`**, `grep -n '^### Abstract' README.md` answers **`:614`**, and
  `make check-forbidden` exits 0. **Zero for two consecutive critic laps would be a direction finding
  (routine prompt step 3b); this is not that**, but the three-hour window contained two CI-repair laps and
  one research lap and no judge-facing change at all, which is why every scorecard row holds.

- ⚠ **R3 is unchanged and unchangeable by any lap.** Its row is **WFG-179**, whose own *Done when* ends
  「whichever the author picks in NH-046」, and NH-046 (due 09-10) is still open. R3 is the last of §14b's
  six lines, so **eight P1 infra rows still wait on one reply**. R11 and R12 are likewise the author's
  (R12 is NH-014).


**Tick count, critic #44, 2026-09-08T1700Z: 8 of 11 (R1, R2, R4, R5, R6, R7, R8, R9), held. R8 keeps the tick
it earned last window and I re-derived it rather than reading it.** Re-measured at `0cca093` on the routine's
**default** clone, before any deepening: `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count
HEAD` = **54**, oldest resolvable `6d1d730` at **18:50Z on 09-07**, so this clone reads about **22 hours** and I claim
nothing about anything older and **no ancestry or reachability claim at all**. `gates.py --mode full` exits **0**,
ALL GREEN: `1763 passed, 63 skipped, 2 xfailed`, pytest **247.9 s**. **The run downloaded nothing:** `du -sb data/raw`
answers **201,187** bytes before and after and `data/raw/dem/srtm/` holds **0** files. **Cold on the tile, warm on
`data/cache`.** `--assert-head` exits 0; `--assert-reported --base 6d1d730` exits 0 over **56** substantive paths.

- ⚠⚠ **CHARTER §4b FINDING, and it is the first one any critic lap has had to write this week.** `auto-gates` run
  **253** (id 34250797625) at `0cca093` — the current head — is **`failure`**, and **the gates inside it are green**:
  the job log prints `[gates] ALL GREEN  mode=full head=0cca093 (auto/dev)` with `1763 passed, 63 skipped, 2 xfailed`
  in 341.5 s, and the gate step concluded `success`. What failed is the step after it, 「Keep the gate record」
  (`actions/upload-artifact@v4`): `Failed to FinalizeArtifact: … (403) Forbidden: Error from intermediary`.
  **`promote` has `needs: gates` (`.github/workflows/auto-gates.yml:89`) so it was SKIPPED**, and `git ls-remote
  origin Main` answers **`6ecc386`** while `auto/dev` is `0cca093`. **`Main` stopped following the last
  gate-certified commit because an archival upload 403'd** (CHARTER §4c). Runs **230 to 253** are otherwise 19
  `success`, 4 `cancelled` (232, 235, 242, 245) and **this one `failure`**. **WFG-193**, and it is this lap's one
  `fix-before-next-row` item — a red GitHub run, which §14b as amended by NH-038 B names alongside the judge-facing
  surfaces. ⚠ **No readiness line falls for it.** R1's and R9's conditions are about the screen and the bundle, not
  about the artifact store, and the gate's own verdict on this head is green on two machines.
- ✅ **R8 holds, and here are the three commands rather than the claim.** `grep -nE '^## Round' README.md` answers
  `:59`, `:75` and **`:200`**; `grep -n '^### Abstract' README.md` answers **`:614`** (it was `:596` last window; the
  section grew by this window's fix, which is why I re-took it instead of quoting critic #43's number);
  `make check-forbidden` exits **0** and `make verify` PASS inside the full run.
  ⚠⚠ **And the tick is on R8's condition, not on the section's prose, for the second consecutive lap.** Critic #43
  filed WFG-190 against two sentences inside that section; the 1518Z lap fixed both, correctly. In fixing them it
  wrote a third: `README.md:232` now states 「이 실행이 쓴 폭은 그 sweep 안에서 **고원이 아니라 뾰족한 봉우리**
  입니다」, which is the shape `docs/auto/JUDGE_QA.md:1394` and `:920` say the five-point sweep **cannot resolve** and
  which `docs/auto/DEMO_SCRIPT_5MIN.md:151` has the student disclaim aloud. That is **WFG-127**'s fourth surface and
  this lap's root objection; it is scored on 제출 자료 and 설계와 방법론, not here.
- ✅ **R5 and R7 hold and both got stronger.** The bank is **46** cards and the header's 46 / T0 19 / T1 20 / T2 7
  sums (`grep -cE '^\*\*Q[0-9]+[a-z]? · T[0-9]'` = 46, and the per-tier counts derive to 19 / 20 / 7). The 46th is
  the county-adoption card WFG-188 asked for, it leads with what the project cannot do, and
  `tests/test_adoption_card.py` (327 lines) binds it. The kit is `WFG_printables_20260908T1529Z.pdf` with
  `release/kcf-finals-2026/MANIFEST.json` re-pointed to it in the same lap, which is what a `SOURCES` edit requires.
- ⚠⚠ **R3 is still the last of CHARTER §14b's six lines and it is still the author's, not a lap's.** Unchanged from
  critic #43 and re-read rather than re-argued: `Makefile:215` still makes `baseline-verify` a hard prerequisite of
  the command R3 names, R3's row **WFG-179** is `blocked(NH-046)`, and **NH-046 is due 2026-09-10**. Eight P1 infra
  rows still wait on one reply. Nothing in the loop's power shortens that queue.
- **R1 and R9 keep their ticks and the staleness defect is nowhere near firing.** `web/finals.html` carries
  `"git":"25f6b60"` and `git rev-list --count 25f6b60..HEAD` answers **16** against
  `tests/test_finals_screen.py:540`'s `STAMP_MAX_COMMITS_BEHIND = 30`. DIRECTION's 「say so at 20 or more」 rule does
  **not** trigger this lap, and I say the number anyway so the next lap need not re-take it.
- **R11 unchanged (WFG-024, blocked on WFG-023); R10 stays withdrawn; R12 is the author's (NH-014).**
- **Readiness lines ticked inside this window: ONE (R8, at `dee1bc1`, 09-08).** The zero-tick direction finding does
  **not** fire, for the second consecutive lap.
- ⚠ **The one scoped `Do NOT edit` note this lap writes is RE-STATED after re-checking, per CHARTER §14c / NH-036 A.**
  It covers `README.md:220-239` only, it forbids exactly one thing — putting a **margin value** (9, 27, 5, 19, 42,
  91, 86) into those lines — and I re-read `docs/auto/NEEDS_HUMAN.md:1391` and `:1524` to confirm the premise: NH-032
  and NH-034 are both still `open` and both were due **2026-09-08**, which is today. It expires at critic #45 unless
  that lap re-states it after re-reading those two entries. **It freezes no file and no question:** WFG-127 (iv) must
  edit `README.md:232`, and that edit is prose about a **grid**, not a result number.

*(Superseded lead, kept as the record.)* **Tick count, critic #43, 2026-09-08T1429Z: 8 of 11 (R1, R2, R4, R5, R6, R7, **R8**, R9). ⚠ **R8 TICKS**, and the
zero-tick streak that ran for three consecutive critic laps ends here.** Re-derived at `dee1bc1` on the routine's
**default** clone, before any deepening: `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD`
= **50**, oldest resolvable `7cc4eb7` (16:12Z, 09-07), so this clone reads about 22 hours and I claim nothing about
anything older and no ancestry claim at all. `gates.py --mode full` exits **0**, ALL GREEN: `1749 passed, 63 skipped,
2 xfailed`, pytest 312.3 s. **The run downloaded nothing:** `du -sb data/raw` answers **201,187** bytes and
`data/raw/dem/srtm/` holds **0** files afterwards. **Cold on the tile, warm on `data/cache`.** `--assert-head` exits 0;
`--assert-reported --base 7cc4eb7` exits 0 over 61 substantive paths. Through the GitHub MCP (`curl` against
`api.github.com` is still refused here, WFG-119): `auto-gates` runs **230 to 249** on `auto/dev` are **16 `success`,
4 `cancelled` (232, 235, 242, 245), ZERO `failure`**, and run **249** at this exact head is `success`. **No CHARTER
§4b finding.** Every dev and critic report in the window carries `Reviewed by:` except `2026-09-08T1132Z-manual.md`,
a report written to satisfy `--assert-reported` for a prose correction carrying no build, which critic #42 declined to
file and this lap declines too.

- ✅ **R8 TICKED, and here are the three commands rather than the claim.** `grep -nE '^## Round' README.md` answers
  `:59`, `:75` and **`:200`** 「Round 4 (2026-09 — 본선 준비)」, where all week it answered only `:59` and `:75`.
  `grep -n '^### Abstract' README.md` answers **`:596`** 「Abstract (draft)」, carrying the draft label
  `tests/test_judge_qa_bank.py::test_the_draft_label_is_on_the_file` exists for. `make check-forbidden` exits **0**
  and `make verify` PASS inside the full run, which is the collision half. The row is WFG-010, done at `692497a` with
  the reviewer's fixes at `ea04478`, and `tests/test_readme_round4.py` (316 lines) binds it.
  ⚠ **The tick is on R8's condition, not on the section's prose.** This lap files **WFG-190** against two sentences
  inside that same section: `README.md:235-239` states 「구체적인 margin 값들은 아직 어느 심사용 자료에도 싣지
  않습니다」 while `docs/auto/JUDGE_QA.md:849-852` carries 9, 27 and 5 and is bound into the 41-page printed kit as
  「심사위원 질의응답 카드」; and `README.md:220-225` states the present-perimeter result with no mention that its
  buffer width is a free parameter, where `paper/manuscript.md:493` says outright 「nothing in the data chooses it」.
  R8 asks for a section and an abstract with green gates; it has them. The prose defect is scored on 제출 자료 and is
  the one `fix-before-next-row` item.
- ✅ **WFG-187 closed and R1/R9's five-commit defect is gone.** `web/finals.html` carries `"git":"25f6b60"`,
  `git rev-list --count 25f6b60..HEAD` answers **9**, and `tests/test_finals_screen.py:540` sets
  `STAMP_MAX_COMMITS_BEHIND = 30`. Critic #42 measured 29 at the head its own bookkeeping produced. The screen is 21
  commits of headroom clear.
- ⚠⚠ **R3 is now the LAST of CHARTER §14b's six lines, and it is the author's, not a lap's.** §14b holds the P1 infra
  block until R1, R3, R4, R7, R8 and R9 tick; five of the six are ticked and only R3 is not. `Makefile:215` still
  reads `all-checks: verify baseline-verify snapshot-verify env-check test`, so `baseline-verify` is still a hard
  prerequisite of the command R3 names and exits 2 in every clone without the acquisition manifests (CHARTER §3d).
  R3's row is **WFG-179**, whose own *Done when* ends 「whichever the author picks in NH-046」 and whose escalation
  says a lap doing it would be grading its own homework. **This lap set that row to `blocked(NH-046)`.** So eight P1
  infra rows now wait on one reply, **NH-046, due 2026-09-10**.
- **R11 re-checked, still correctly unticked, already filed.** `docs/HANDOFF_ROUND3.md:898` still reads 「All work
  stays on `round3-dev`」 inside §5, contradicting CHARTER §3.1. That is **WFG-024**, blocked on WFG-023, and it is
  named in R11's own evidence cell. No new row opened.
- **R5 and R7 hold.** The bank is **45** cards (`grep -cE '^\*\*Q[0-9]+[a-z]? · T[0-9]' docs/auto/JUDGE_QA.md` = 45,
  header's 45 / T0 19 / T1 19 / T2 7 sums) and the kit is `WFG_printables_20260908T0939Z.pdf` at **41** pages with
  `release/kcf-finals-2026/MANIFEST.json` pointing at it, re-read here. Nothing in this window touched either, so
  neither moves.
- **R12 is the author's (NH-014); R10 stays withdrawn.**
- **Readiness lines ticked inside this window: ONE (R8).** After three consecutive critic laps at zero, the direction
  finding the routine prompt defines does **not** fire. The measurement is written into NH-038, which asked this in
  the author's own words and is due 2026-09-09, because it is evidence bearing on that decision.
- ⚠ **No `Do NOT edit` note is written by this lap** (CHARTER §14c, NH-036 A). WFG-190 must edit `README.md:220-239`
  and WFG-188 must edit `docs/auto/JUDGE_QA.md`; freezing either would block the work. The single scoped prohibition
  is in `CRITIC_LATEST.md` (no margin value into `README.md` while NH-032 and NH-034 are open) and it expires at
  critic #44 unless that lap re-states it.

*(Superseded lead, kept as the record.)* **Tick count, critic #42, 2026-09-08T1115Z: 7 of 11 (R1, R2, R4, R5, R6, R7, R9), unchanged, and ZERO lines ticked
for the THIRD consecutive critic lap.** The direction finding critic #41 fired is now one lap worse and it is still a
finding about the loop's aim rather than about the product. Re-derived at `ceb43ba` on the routine's **default**
clone, before any deepening: `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**,
oldest resolvable `2720840` (10:09Z, 09-07), so this clone reads about 25 hours and I claim nothing about anything
older. `gates.py --mode full` exits **0**, ALL GREEN: `1741 passed, 63 skipped, 2 xfailed`, pytest 258.3 s. **The run
downloaded nothing:** `du -sb data/raw` answers **201,187** bytes before and after, and `data/raw/dem/srtm/` is empty
afterwards. **Cold on the tile, warm on `data/cache`.** `--assert-head` exits 0; `--assert-reported --base 2720840`
exits 0 over 69 substantive paths. Through the GitHub MCP (`curl` against `api.github.com` is still refused here,
WFG-119): `auto-gates` runs **216 to 241** on `auto/dev` are **21 `success`, 5 `cancelled` (218, 226, 229, 232, 235),
ZERO `failure`**, and run **241** at this exact head is `success`. **No CHARTER §4b finding.** Every dev and critic
report in the window carries `Reviewed by:`.

- ⚠⚠ **R3 and R8 are the two unticked lines a lap can move, and neither moved for a third window.** **R3:**
  `Makefile:215` still reads `all-checks: verify baseline-verify snapshot-verify env-check test`, so `baseline-verify`
  is still a hard prerequisite of the command R3 names and exits 2 in every clone without the acquisition manifests
  (CHARTER §3d). WFG-179, decision **NH-046**, plus the laptop recipe (NH-014, R12). **R8:** `grep -nE '^## Round'
  README.md` returns `:59` and `:75` and nothing for Round 4, unchanged all week. **R8's row WFG-010 is now at the head
  of the `todo` block** — critic #41 gave it P0 and left it at table line 151, which is this lap's one reorder.
- ⚠⚠ **R1 and R9 keep their ticks and this lap records a defect on both that is five commits from turning them red.**
  `web/finals.html:434` carries `"git":"1bca8ed"`, `git rev-list --count 1bca8ed..HEAD` answers **25**, and
  `tests/test_finals_screen.py:540` sets `STAMP_MAX_COMMITS_BEHIND = 30`. R1's condition is that the screen opens and
  its numbers map; R9's is that the bundle exists. Both hold **today**. The gate that closed `auto/dev` on 09-07
  (NH-045) trips at 31, and at this branch's measured rate — 25 commits in 11 h 59 m — that is the lap after next.
  **WFG-187**, and it is this lap's one `fix-before-next-row` item.
- **R5 and R7 keep their ticks and both got stronger this window.** The bank is **45** cards
  (`grep -cE '^\*\*Q[0-9]+[a-z]? · T[0-9]' docs/auto/JUDGE_QA.md` = 45, header's 45 / T0 19 / T1 19 / T2 7 sums), the
  WFG-185 scope defect critic #41 recorded here is **closed**, and the kit is `WFG_printables_20260908T0939Z.pdf` at
  41 pages with `release/kcf-finals-2026/MANIFEST.json` pointing at it, re-checked here.
- **Readiness lines ticked inside this window: NONE.** Three consecutive critic laps at zero. Six consecutive dev work
  commits in that span all edited `docs/auto/JUDGE_QA.md` and none touched R3's or R8's blocker. **NH-038**, due
  2026-09-09, is the author's decision on exactly this and this lap wrote the new measurement into it rather than
  opening a fourteenth question.
- ⚠ **No `Do NOT edit` note is written by this lap** (CHARTER §14c, NH-036 A). WFG-187 must rebuild `web/finals.html`
  and WFG-010 must edit `README.md`; freezing either would block the fix.

*(Superseded lead, kept as the record.)* **Tick count, critic #41, 2026-09-08T0820Z: 7 of 11 (R1, R2, R4, R5, R6, R7, R9), unchanged, and ZERO lines ticked
for the SECOND consecutive critic lap.** That fires the direction finding the routine prompt defines, and it is a
finding about the loop's aim rather than about the product. Re-derived at `9329400` on the routine's **default**
clone, before any deepening: `git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**,
so this clone reads about 50 commits and I claim nothing about anything older. `gates.py --mode full` exits **0**,
ALL GREEN: `1735 passed, 63 skipped, 2 xfailed`, pytest 466.2 s. **The run downloaded nothing:** `du -sb data/raw`
answers **201,187** bytes before and after, and `data/raw/dem/srtm/` is empty afterwards. **Cold on the tile, warm on
`data/cache`**, said rather than implied. `--assert-head` exits 0. Through the GitHub MCP (`curl` against
`api.github.com` returns 「GitHub access is not enabled for this session」 here, which is WFG-119's 403 in its current
wording): `auto-gates` runs **216 to 236** on `auto/dev` are **15 `success`, 5 `cancelled` (218, 226, 229, 232, 235),
ZERO `failure`**, and run **236** at this exact head is `success`. **No CHARTER §4b finding.** Every dev and critic
report in the window carries `Reviewed by:`.

- ⚠⚠ **R3 and R8 are the two unticked lines and NEITHER moved, which is why the tick count is a direction finding.**
  Re-measured here rather than read. **R3:** `Makefile:215` still reads `all-checks: verify baseline-verify
  snapshot-verify env-check test`, so `baseline-verify` is still a hard prerequisite of the command R3 names, and it
  exits 2 in every clone without the acquisition manifests (CHARTER §3d). The line still cannot go green on a clean
  clone by construction. WFG-179, decision NH-046, plus the laptop booth recipe (NH-014, R12). **R8:** `grep -nE
  '^## Round' README.md` returns `:59` Round 2 and `:75` Round 3 and nothing for Round 4, unchanged all week.
- ⚠⚠ **R8's blocker was never held by anything except its own priority, and the record said otherwise.** Critic #39
  wrote that WFG-010 「sits inside the very block R8 helps hold shut」 and filed it no further. That is a misreading:
  CHARTER §14b holds **loop hygiene** behind the readiness lines, WFG-010's goal column is **KCF**, and §14b's own
  sentence names 「README opening」 first among judge-facing surfaces. So for two laps the one row that ticks R8 sat
  as P1 `todo` under a reason that did not apply to it. **Promoted to P0 by this lap** (step 5, an update to an
  existing row, not a §3b reorder) with the measurement written into the row.
- **R5 and R7 keep their ticks and this lap adds a deduction to neither, but records one defect on both surfaces.**
  The bank is 44 cards (`grep -cE '^\*\*Q[0-9]+[a-z]? · T[0-9]' docs/auto/JUDGE_QA.md` = **44**, and the header's
  44 / T0 18 / T1 19 / T2 7 sums correctly), and the kit is `WFG_printables_20260908T0633Z.pdf` at 40 pages with
  `release/kcf-finals-2026/MANIFEST.json` pointing at it. R5's condition is coverage and R7's is that the kit exists
  and is fresh; both hold. The defect is **WFG-185** and it is scored on 제출 자료, not here: `JUDGE_QA.md:715` tells
  the student 「커밋된 33장 전부」 where `git ls-files '*dispatch_a4.html'` answers **642**.
  ⚠ **A `Do NOT edit` note is NOT written here** (CHARTER §14c): WFG-185 must edit `JUDGE_QA.md` and rebuild the kit
  in the same lap, and freezing either would block the fix.
- **R1, R2, R4, R6, R9 hold; R11 unchanged; R10 stays withdrawn; R12 is the author's (NH-014).** I did not re-run
  the finals acts driver: nothing in this window touched `web/`, and critic #37's two-machine evidence stands.
- **Readiness lines ticked inside this window: NONE.** Combined with critic #40's zero, this is **two consecutive
  critic laps at zero**, which the routine prompt makes a finding about the loop's direction. Said plainly: the loop
  spent both windows on the Q&A bank, which is real judge-facing work and closed two P0 rows, while the checklist
  that defines 「the product is done」 has not moved since 2026-09-07T2020Z.

*(Superseded lead, kept as the record.)* **Tick count, critic #40, 2026-09-08T0524Z: 7 of 11 (R1, R2, R4, R5, R6, R7, R9), unchanged, and ZERO lines moved
since critic #39.** Re-derived at `47e48b5` on the routine's **default** clone, before any deepening
(`git rev-parse --is-shallow-repository` = `true`, `git rev-list --count HEAD` = **50**; the oldest resolvable
commit is `0fc6130` at 2026-09-07T04:08:02Z, so this clone reads **49 commits / about 25 hours** and I make no claim
about anything older). `gates.py --mode full` exits **0**, ALL GREEN: `1722 passed, 63 skipped, 2 xfailed`, pytest
277.3 s. **The run downloaded nothing:** `du -sb data/raw` answers **201,187** bytes and `data/raw/dem/srtm/` is
empty after it. Cold on the tile, which was never present; **warm** on `data/cache` for the later runs in this
container, and I say which rather than implying. `--assert-head` exits 0; `--assert-reported --base 0fc6130` exits 0
with 75 substantive paths. Through the GitHub MCP (`curl` is 403 here, WFG-119): `auto-gates` runs **211 to 231** on
`auto/dev` are **18 `success`, 3 `cancelled` (218, 226, 229), ZERO `failure`**, and run **231** at this exact head is
`success`. **No CHARTER §4b finding.** Every dev and critic report in the window carries `Reviewed by:`.

- ✅ **R5 and R7 keep their ticks and critic #39's deduction against them is CLEARED.** The 2026-09-08T0407Z lap
  closed WFG-178 and I re-derived the result by a channel it did not use: `pytest -rs` over the **whole** suite in
  this tile-less clone prints **60 skip lines, 11 of them naming SRTM** — seven tile-gated
  (`test_srtm_dem.py` ×4, `test_raster_ingestion.py:168`, `test_validation_robustness.py:57`,
  `test_validation_session3.py:171`) and four gating on the laptop bundle (`test_slope_digraph.py:145/160/174/209`).
  That is exactly what `JUDGE_QA.md` Q28 and Q40 and `docs/clean_clone_gates.md` now say, and
  `tests/test_tile_gated_skip_count.py` binds twelve sentences on those pages to it, the two spoken lines included.
  ⚠ **A `Do NOT edit` note is NOT written here** (CHARTER §14c): WFG-180 will change these numbers on purpose, and
  the coupling is recorded in that row instead.
  *(Superseded, kept as the record: critic #39's finding that `:980`, `:1182` and `clean_clone_gates.md:85` said
  「여섯 개」 where the tree had seven.)*

*(Superseded lead, kept as the record.)* **Tick count, critic #39, 2026-09-08T0217Z: 7 of 11 (R1, R2, R4, R5, R6, R7, R9), unchanged, and for the first time
in eleven laps R3's sandbox half has NOTHING against it.** Checked on disk at `1282198`, re-run rather than read,
on the routine's **default** clone before any deepening (`git rev-parse --is-shallow-repository` = `true`,
`git rev-list --count HEAD` = **50**; ⚠ the oldest resolvable commit is `5cca6ce` at 2026-09-07T02:25:10Z, so this
clone reads the window from there forward and **not** the full 24 h, and I say so rather than implying otherwise).
`gates.py --mode full` exits **0**, ALL GREEN: `1708 passed, 63 skipped, 2 xfailed`, pytest 290.9 s, **COLD**, and
**the run downloaded nothing**. `--assert-head` exits 0; `--assert-reported --base 5cca6ce` exits 0 with 73
substantive paths. Through the GitHub MCP, `auto-gates` runs **207 to 227** on `auto/dev` are 19 `success`,
2 `cancelled` (218, 226), **zero `failure`**, and run **227** at this exact head is `success`. **No CHARTER §4b
finding.** Every dev and critic report in the window carries `Reviewed by:`.

- ✅✅ **R3's blocker is GONE, and R3 still does not tick. Both halves of that sentence are load-bearing.** WFG-139
  closed at `ab4e71e` and I re-derived it rather than reading it: at container start `data/raw/` held `.gitkeep`,
  `README.md` and the KFS CSV; after a **cold** `gates.py --mode full`, `du -sb data/raw` answers **201,187** bytes,
  `data/raw/dem/srtm/` exists and is **empty**, and no `N36E129.hgt` was written. The eleven-lap measurement finally
  reads zero. The mechanism is `tests/conftest.py` refusing outbound sockets session-wide including to the
  `*_proxy` addresses this sandbox routes egress through, plus a `pytest_sessionfinish` hook that fails a run in
  which `data/raw/` grew. ⚠ **What stops the tick is now the line's own wording, not the suite.** R3 says
  「`make all-checks` green on a clean clone (CI)」; `Makefile:215` makes `baseline-verify` a **hard** prerequisite
  of that target and `baseline-verify` exits **2** in every clone without the acquisition manifests (CHARTER §3d),
  so the named command cannot go green on a clean clone by construction, while `.github/workflows/auto-gates.yml:31`
  runs `gates.py --mode full` instead. **WFG-179**, and the decision is the author's: **NH-046**. R3 also still
  waits on one run of the booth recipe on the author's laptop (NH-014, R12).
- ⚠ **R5 and R7 keep their ticks and both carry this lap's one `fix-before-next-row` item.** `JUDGE_QA.md:980` and
  `:1182` tell the student the tile-gated skip set is 「여섯 개」 and Q40 enumerates it; measured here at `1282198`,
  cold, the tests whose `skipif` predicate is `data/raw/dem/srtm/N36E129.hgt` number **seven**, the seventh being
  `tests/test_raster_ingestion.py:168::test_auto_dem_prefers_srtm_when_the_tile_is_cached`, added by the same commit
  that wrote the card. `docs/clean_clone_gates.md:85` says six as well, and `:45` attributes the whole measurement
  to `088203c`, a tree in which `git ls-tree -r 088203c -- tests/conftest.py` is empty. Both ticks stand because
  R5's condition is coverage (the bank answers 42 questions) and R7's is that the kit exists and is fresh (kit
  `20260908T0114Z`, 38 pages, all six `SOURCES` re-hashed here and matching); this is a 제출 자료 deduction and is
  scored there. **WFG-178.**
- ✅ **R1 keeps its tick and the liveness defect critic #38 attached to it is CLEARED.** `web/finals.html` names
  `1bca8ed` and `git rev-list --count 1bca8ed..HEAD` answers **4** against `STAMP_MAX_COMMITS_BEHIND = 30`
  (`tests/test_finals_screen.py:540`). I did not re-run the acts driver: nothing in this window touched `web/`
  beyond the rebuilt stamp, `scripts/check_finals_acts.py` or the payload, and critic #37's two-machine evidence
  stands.
- ⚠ **R8 does not tick and its blocker is unchanged and unmeasured by anyone this week.** `README.md` has
  `## Round 2 결과 (2026-07)` at `:59` and `## Round 3 (2026-08)` at `:75` and **no Round-4 section**; R8's other
  clause (forbidden-string and collision gates green) is met. R8 is the second of the two lines holding §14b's infra
  block shut. Its row already exists and is **WFG-010** (P1, 「README Round-4 section + English abstract draft」),
  which sits inside the very block R8 helps hold shut. Recorded here rather than filed as new: no duplicate row, and
  the ordering knot is NH-038's subject, not a new finding.
- **R2, R4, R6, R9 hold; R11 unchanged; R10 stays withdrawn; R12 is the author's (NH-014).**
- **Readiness lines ticked inside this window: R1 (2026-09-07T2020Z).** The 「zero across two consecutive critic
  laps」 direction finding does not fire.

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #38, 2026-09-07T2319Z: 7 of 11 (R1, R2, R4, R5, R6, R7, R9). No line moved this window and no
line fell.** Checked on disk at `1bca8ed`, re-run rather than read, on the routine's **default** clone before any
deepening (`git rev-parse --is-shallow-repository` = `true`, `git rev-list --count HEAD` = **50**, `git log
--since='26 hours ago'` returns exactly 50, so the oldest resolvable commit `590c29a` (2026-09-07T00:43Z) is inside
the window and the window resolves from there forward; the hour before it does not, and I say so rather than implying
a full 24 h). `gates.py --mode full` exits **0**, ALL GREEN: `1689 passed, 62 skipped, 2 xfailed`, pytest 212.2 s,
**COLD**, and **the run downloaded 25.9 MB** (WFG-139, below). `--assert-head` exits 0; `--assert-reported --base
3426135` exits 0. Through the GitHub MCP, `auto-gates` runs **204 to 223** on `auto/dev` are 19 `success`, 1
`cancelled` (218), **zero `failure`**, and run **223** at this exact head is `success`. **No CHARTER §4b finding.**
Every dev and critic report in the window carries `Reviewed by:`; the research report of 2026-09-06T1838Z still does
not (WFG-147, unchanged, not duplicated).

- **R5 and R7 keep their ticks and the defect critic #37 attached to both is CLEARED.** That lap's one
  `fix-before-next-row` item was WFG-171: `RELATED_WORK_PANEL.md:32` and `JUDGE_QA.md:652` asserting flat and in bold
  that the NIFoS console's 발화점은 「운영자가 손으로 입력」한다, on the provenance of a catalogue chapter title. Both
  lines now state the claim at the strength of its source; the panel prints the eight chapter names and says the flow
  「읽힙니다」; the superseded wording is registered as **`WC-009`** rather than reprinted; the kit was rebuilt in the
  same lap (`WFG_printables_20260907T2149Z.pdf`, `manifest_20260907T2149Z.json`) and
  `release/kcf-finals-2026/MANIFEST.json` re-pointed. I read the replacement text on both files rather than grepping
  for the absence of the old one. ⚠ **What R5 still does not cover:** `JUDGE_QA.md` Q28 keeps a sentence this
  repository knows to be false, and its correction sits in Q40 **211 lines below**; both print in the same kit
  (WFG-139's 「Done when」).
- **R1 keeps the tick critic #37 earned for it, and I did not re-run its driver.** That lap's evidence was a headless
  `Chromium 141` run here plus the same four act labels and dot counts in `auto-gates` run 219's `finals-acts` job on a
  clean `ubuntu-latest` runner. Two independent machines is stronger than a third run on this one, and nothing in this
  window touched `web/`, `scripts/check_finals_acts.py` or the payload. ⚠ **But the screen the tick is about is one
  commit from a red gate**, which is a different property from R1's: `web/finals.html:434` names `7308b06`, **30**
  commits behind `HEAD` (`git rev-list --count 7308b06..HEAD`), against `STAMP_MAX_COMMITS_BEHIND = 30` at
  `tests/test_finals_screen.py:540` and `assert behind <= STAMP_MAX_COMMITS_BEHIND` at `:732`. Critic #37 read the
  same field at **24** and called it inside the limit, which it was. **WFG-173**, this lap's one `fix-before-next-row`
  item.
- **R3 unchanged, and its sandbox half now has an ELEVENTH measurement, this one isolated.** `verify`,
  `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d state. At container start
  `data/raw/` held `.gitkeep`, `README.md` and the KFS CSV; after the gate run it holds `dem/srtm/N36E129.hgt`
  (**25,934,402 B**) and `N36E129.hgt.gz` (8,473,868 B) at mtime **23:02Z**. I then deleted both tiles and the cached
  `data/cache/dem_yeongdeok_2025_srtm_500m_80858ae747.nc` (all git-ignored; `git status --short` clean afterwards) and
  ran the row's own named suspect **alone**: `tests/test_spread_warmup.py::test_model_config_ignition_radius_
  increases_initial_burn`, **1 passed in 1.54 s, both tiles back at 23:06Z**. The same test with the `.nc` cache
  present passes in 0.47 s and downloads nothing, which is why ten laps of re-running never located it. R3 also still
  waits on one `make all-checks` on the author's laptop.
- **R2, R4, R6, R9 hold; R8 and R11 unchanged; R10 stays withdrawn; R12 is the author's (NH-014).**
- **Readiness lines ticked inside this window: R9 (05:00Z), R7 (08:00Z), R1 (20:00Z).** The 「zero across two
  consecutive critic laps」 direction finding does not fire.

*(Superseded, kept as the record.)* **Tick count, critic #37, 2026-09-07T2020Z: 7 of 11 (R1, R2, R4, R5, R6, R7, R9) — and R1 TICKS, the first movement
on that line since the checklist was written.** Checked on disk at `64f015b`, re-run rather than read, on the routine's
**default** clone before any deepening (`is-shallow-repository` = `true`, `rev-list --count HEAD` = **50**, and the oldest
resolvable commit `d6cb996` is itself inside this lap's 24 h window, so the whole window resolves). Lines ticked inside
the window: **R9** at 05:00Z, **R7** at 08:00Z and **R1** here, so the "zero across two consecutive critic laps"
direction finding does not fire and could not have.

- ✅✅ **R1 TICKS.** Its three clauses, each re-derived here and one of them on a machine that is not this sandbox.
  **(a) 「opens from `file://` with Wi-Fi off」.** `scripts/check_finals_acts.py` copies `web/` whole into a temp dir,
  drives headless `Chromium 141.0.7390.37` over the DevTools protocol and records every request URL: **10 requests, none
  off `file://`, zero console errors**. The two `ERR_FILE_NOT_FOUND` lines it prints are the uncommitted optional booth
  media (`intro-forest-loop.mp4`, `ambient-documentary.mp3`), which `804e5b6` made the git index rather than an extension
  list decide. Critic #36's independent reading holds beside it: the built file carries **zero** `http(s)` `src`/`href`
  references.
  **(b) 「all four acts advance」, the clause nothing in this repository had ever tested.** I ran the driver myself:
  `1막 · 발견` 1 dot, `2막 · 시간과 도로망` 2, `3막 · 경로 비교` 3, `4막 · 판단` 4, four screenshots written, exit 0.
  ⚠ **And I did not stop at the sandbox, because a driver that only ever runs where it was written proves the machine
  and not the screen.** GitHub `auto-gates` run **219** at this exact head ran the `finals-acts` job on a clean
  `ubuntu-latest` runner, 19:12:10Z to 19:12:26Z, and its log prints the **same four act labels with the same dot counts
  and the same 「10 requests, none off file://, no console error」**, then uploaded 5 files (2,238,234 B, artifact
  10030536190). That closes finding 5 of the 1900Z dev report, which had recorded the CI browser as unverified: the
  runner has a browser, the job is not silently skipping, and the artifact is not empty. **Two independent machines, one
  of them not ours.**
  **(c) 「every on-screen number maps to a `docs/NUMBERS.json` key (mapping table committed)」.** Re-derived rather than
  inherited from critic #36: `scripts/finals_screen_keys.py` returns **28** keys; **all 28** appear in
  `docs/finals_screen_numbers.md`; **all 28** are keys of `docs/NUMBERS.json` (**383** entries). Zero misses on either
  side, counted in one process.
  ⚠ **What the tick does NOT cover, said here so nobody reads it as more than it is.** The four **view tabs** are a
  different mechanism and still have no driver (**WFG-169**); the booth's between-judges control is the **G** key and
  nothing presses it (**WFG-170**); and R1 is a statement about this repository's screen, not about the author's laptop,
  which is **NH-014** and **R12**.
- **R3 unchanged, and its sandbox half now has a TENTH measurement against it, on this lap's own clock.** `verify`,
  `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d state. `gates.py --mode full`
  exits **0**, ALL GREEN, `1682 passed, 62 skipped, 2 xfailed`, pytest 289.3 s, **COLD**. ⚠ At container start
  `data/raw/` held `.gitkeep` and `README.md` only; afterwards it holds `dem/srtm/N36E129.hgt` (**25,934,402 B**) and
  `N36E129.hgt.gz` (8,473,868 B) with mtime **2026-09-07T20:02Z**, inside a `pytest-full` stage that ran 19:59:37Z to
  20:04:26Z. **WFG-139, tenth consecutive lap**, and DIRECTION position 1 for the next one. Through the GitHub MCP
  (`curl` is 403 here, WFG-119): `auto-gates` runs **200 to 219** on `auto/dev` are **18 `success`, 2 `cancelled`, ZERO
  `failure`**; run **219** at this head is `success` — **no CHARTER §4b finding.** `--assert-head` exits 0;
  `--assert-reported --base 018dd78` exits 0 with 20 substantive paths. Every dev and critic report in the window carries
  `Reviewed by:`; the research report does not (WFG-147, unchanged). R3 also still waits on one `make all-checks` on the
  author's laptop.
- ⚠ **R5 and R7 keep their ticks, and both carry the same new defect, which is this lap's one `fix-before-next-row`
  item.** WFG-166's sentence is **gone** from `JUDGE_QA.md:650-652` and from `RELATED_WORK_PANEL.md`, and the kit was
  rebuilt in the same lap (`WFG_printables_20260907T1825Z.pdf`, 38 pages, manifest re-pointed and verified
  byte-identical) — I confirmed the replacement text on both files. What replaced it is correct. What sits four lines
  above it on the panel is not: `RELATED_WORK_PANEL.md:32` and `JUDGE_QA.md:652` assert, flat and in bold, that the NIFoS
  console's 발화점은 「운영자가 손으로 입력」한다, a positive claim whose whole provenance is a catalogue chapter title
  (「발화지점 생성」) on an unopened 18 MB PDF (NH-039), while `references.bib:258`, `manuscript.md:111-112` and
  `KOREAN_OPERATIONAL_SYSTEMS.md` §1 all state it with its attribution. Same family as WFG-144/162/166, positive
  direction. **WFG-171.** Both ticks stand because R5's condition is coverage (42 cards) and R7's is that the kit exists
  and is fresh (it is, and I re-checked the manifest); this is a 제출 자료 deduction and is scored there.
- **R2, R4, R6, R9 hold. R8, R11 unchanged**; R10 stays withdrawn and R12 is the author's (NH-014), and with R1 ticked
  NH-014 is now the **only** pre-registered blocker of Track A 구현 및 유용성 that is not the loop's to close.

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #36, 2026-09-07T1700Z: 6 of 11 (R2, R4, R5, R6, R7, R9), unchanged — and R1's blocker CHANGED
identity for the first time in five laps.** Checked on disk at `7cc4eb7`, re-run rather than read, on the routine's
**default** clone before any deepening (`is-shallow-repository` = `true`, `rev-list --count HEAD` = **50**, so the whole
resolvable history is inside this lap's 24 h window). Lines ticked inside the window: **R9** at 05:00Z and **R7** at
08:00Z, so the "zero across two consecutive critic laps" direction finding does not fire.

- ⚠⚠ **R1 does not tick, and the blocker is no longer WFG-110.** WFG-110 **closed** at `60c07c8` and I re-derived it
  rather than reading it: `scripts/finals_screen_keys.py` returns **28** keys, **all 28** appear in
  `docs/finals_screen_numbers.md`, and **all 28** are keys of `docs/NUMBERS.json` (383 entries). The doc writes no
  registry VALUE, which is what keeps it from becoming a second home for a number (CHARTER §3.3). **R1's second clause
  is met.** Its **first** clause — 「opens from `file://` with Wi-Fi off, **all four acts advance**」 — is the one no
  measurement has ever covered, and I took the cheapest honest reading rather than inheriting the 2026-09-05 hand-run:
  `/opt/pw-browsers/chromium-1194/chrome-linux/chrome --headless=new --disable-gpu --no-sandbox
  --virtual-time-budget=8000 --dump-dom file://$PWD/web/finals.html` exits **0** and returns **3,449,612 bytes** of
  post-JS DOM holding `view-live`, `view-evidence`, `view-reliability`, `view-system` and the labels 라이브 · 근거 ·
  신뢰성 · 시스템; the built file contains **zero** `http(s)` `src`/`href` references. ⚠ **What that does NOT show, and
  why I do not tick:** at initial load `view-live` = 1,157,688 B and `view-reliability` = 2,063,451 B, while
  `view-evidence` = **225 B** and `view-system` = **235 B**, with **no Korean text in either** — consistent with those
  two views building on switch, which `--dump-dom` cannot exercise because it presses no key. So 「advance」 is exactly
  the word nothing has measured. **WFG-009 is that row, it has been P1 since the kickoff inside the block §14b holds
  *behind* R1, and it is this lap's one row move: P1 → P0, DIRECTION position 1.**
- **R3 unchanged, and its sandbox half now has a NINTH measurement against it.** `verify`, `snapshot-verify`,
  `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d state. `gates.py --mode full` exits **0**, ALL
  GREEN, `1665 passed, 62 skipped, 2 xfailed`, 260.5 s, **cold**. Through the GitHub MCP (`curl` against
  `api.github.com` is 403 here again, WFG-119): `auto-gates` runs **186 to 215** on `auto/dev` are **28 `success`, 2
  `cancelled`, ZERO `failure`**, and run **215** at this head is `success` — **no CHARTER §4b finding.** `--assert-head`
  exits 0 and `--assert-reported --base 719c420` exits 0 over the 49 commits this clone resolves, with 58 substantive
  paths travelling with `docs/auto/reports/2026-09-07T1600Z-dev.md`. Every **dev** and **critic** report in the window
  carries `Reviewed by:`; the research report does not (WFG-147, unchanged). ⚠ R3 cannot tick while the suite reaches
  the network, and this lap watched it: `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 B**) and its `.gz` have mtime
  **2026-09-07T17:02:33Z**, inside a `pytest-full` run that began about 17:00Z, in a container whose `data/raw/` held
  only `.gitkeep` and `README.md` at start. **WFG-139, ninth consecutive lap.** R3 also still waits on one
  `make all-checks` on the author's laptop.
- ⚠⚠ **R5 keeps its tick, and it carries the sentence its own card forbids.** `docs/auto/JUDGE_QA.md:650-652` — inside
  **Q16a · T0**, the card critic #35 gave a scorecard point four hours ago — has the student say aloud that G-DAPS
  「특정한 집의 어느 길이 위험에 들어가고 어느 길이 들어가지 않는지는 **말해 주지 않습니다**」. `:671-672` of the same
  card says ❌ 「저쪽은 가구 단위로는 못 합니다」라고 **단정하지 마십시오**, gives the permitted form
  ⭕ 「**공개된 자료에서는** 가구 단위 산출물이 확인되지 않습니다」, and gives the reason: 「심사위원이 그 시스템을 직접
  써 본 분일 수 있고, 그때 무너지는 것은 이 답변 하나가 아니라 신뢰 전부입니다.」 It is the **Korean half of `WC-008`**,
  registered ninety minutes earlier on the English spelling `walk out, and along which path`, which structurally cannot
  reach it. `:625` of the same file asserts that Q16a 「「공개된 자료에서는 확인되지 않습니다」라고**만** 말합니다」, and
  that is false at `:651`. **WFG-166, and this lap's one `fix-before-next-row` item.** The tick stands because R5's
  condition is coverage and the bank answers 42 questions; the sentence is a 제출 자료 deduction and is scored there.
  ⚠ **A second R5 gap, found by this lap's judge drill and filed rather than ticked against:** `git grep -niE
  '책임|법적|면책|사람이 다치'` over `docs/auto/JUDGE_QA.md` returns **zero** at this head, while `web/finals.html:1393`
  prints 「최종 판단은 언제나 사람이 내립니다」 and `DEMO_SCRIPT_5MIN.md:217` gives it as the 재난대응 실무자 lens's
  one-line answer. One of the five judges is a public-sector disaster-response official. **WFG-167.**
- **R7 keeps its tick, and critic #35's printed defect is GONE.** Kit `20260907T1551Z`, **38** pages, sha256
  `b54eb514a95e…`, bundle manifest re-pointed to 19 files. `RELATED_WORK_PANEL.md:40` now reads 「**이 패널이 읽은
  자료(카탈로그 기록·언론 보도)에서는** 앞의 두 시스템의 재현 절차가 확인되지 않습니다」 — narrowed twice, once by the
  lap and once by its reviewer — and the dated note beside it **describes** the withdrawn sentence rather than
  reprinting it, which is `WC-005`'s precedent used correctly on a printed page. What R7 now carries instead is
  `JUDGE_QA.md:650-652`, 17 of the same 38 pages: the sentence is on paper, in the student's hand. Same deduction,
  different file, and it is WFG-166's second half.
- **R2, R4, R6, R9 hold. R8, R11 unchanged**; R10 stays withdrawn and R12 is the author's (NH-014, and it is now the
  only pre-registered blocker of Track A 구현 및 유용성 20 that is not the loop's to close).

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #35, 2026-09-07T1416Z: 6 of 11 (R2, R4, R5, R6, R7, R9), unchanged — and this is the second
consecutive lap where unchanged is correct rather than a stall.** R9 (05:00Z) and R7 (08:00Z) both moved inside this
24 h window, so the "zero for two consecutive critic laps" direction finding does not fire. Checked on disk at
`b54ca28`, re-run rather than read, on the routine's **default** clone before any deepening
(`is-shallow-repository` = `true`, `rev-list --count HEAD` = **50**).

- **R1 unchanged, and its blocker is unchanged for a fourth consecutive lap: WFG-110.** The baseline is green here —
  `gates.py --mode full` exits **0**, ALL GREEN, `1650 passed, 62 skipped, 2 xfailed`, pytest 283.6 s, cold — and
  `web/finals.html` names `7308b06`, **10** commits behind `HEAD`, inside the limit of 30, so critic #33's red stays
  cleared and the depth-independent carrier gate did not fire. What holds R1 is what has held it since critic #32:
  `scripts/finals.template.html` references **28** registry keys, `DEMO_SCRIPT_5MIN.md` §3 maps **22** of them the
  wrong way round, and **6** are in no committed mapping table. ⚠ **I did not re-measure those six and do not tick,
  or re-quote a count, on a number I did not take.** WFG-110 is DIRECTION position 1.
- **R3 unchanged, and its sandbox half now has an eighth measurement against it.** `verify`, `snapshot-verify`,
  `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d state. Through the GitHub MCP (`curl`
  against `api.github.com` returned **403** here again, WFG-119): `auto-gates` runs **170 to 209** on `auto/dev` are
  **36 `success`, 4 `cancelled`, ZERO `failure`**, and run **209** at this head is `success` — **no CHARTER §4b
  finding.** `--assert-head` exits 0 and `--assert-reported --base dfdf480` exits 0 over the 49 commits this clone
  resolves, with 60 substantive paths travelling with `docs/auto/reports/2026-09-07T1256Z-dev.md`. Every **dev**
  report in the window carries `Reviewed by:`; the research report does not (WFG-147). ⚠ R3 cannot tick while the
  suite reaches the network: my cold run reports `1650 passed / 62 skipped` where the same tree's warm re-runs
  report `1656 / 56`, which is the six terrain tests switching on a 25.9 MB SRTM download the suite performs itself.
  WFG-139, eighth consecutive lap. R3 also still waits on one `make all-checks` on the author's laptop.
- **R5 keeps its tick and the gap seven critic laps measured is CLOSED.** `docs/auto/JUDGE_QA.md:637-694` now holds
  **Q16a · T0**, answering 「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」 on the output
  object, with a 없는 것 block that refuses the accuracy comparison in either direction, refuses the 「저쪽은 못
  합니다」 form in favour of 「공개된 자료에서는 확인되지 않습니다」, and refuses any claim about 경상북도·영덕
  coverage. The panel and the spoken bank now say the same thing, which is what critic #33 and #34 said the
  asymmetry cost. I read the card rather than grepping for its existence.
- ⚠ **R7 keeps its tick, and it carries one printed claim that should not be on paper.** Kit `20260907T1248Z`,
  **38** pages (was 36), sha256 `4504f5984cb9…`, six source hashes, bundle re-pointed with no residual `0953Z`.
  WFG-146's date is corrected on the printed panel, which was critic #34's item, and I re-fetched the article as a
  fourth independent check rather than inheriting it. What is new is `docs/auto/finals/RELATED_WORK_PANEL.md:40` —
  3 of the 38 printed pages — asserting 「앞의 두 시스템은 재현 방법을 공개하지 않습니다」, an assertion about
  documents this repository has never opened (NH-039), where the survey it summarises writes 「not stated」 at
  `docs/related_work.md:134` and the same lap wrote the narrowed form into `JUDGE_QA.md:660` and
  `docs/dispatch_ordering.md:317`. **WFG-162, and this lap's one `fix-before-next-row` item.** The tick stands
  because R7's conditions are completeness and provenance hashes, all of which hold; the claim is a 제출 자료
  deduction and is scored there.
- **R2, R4, R6, R9 hold. R8, R11 unchanged**; R10 stays withdrawn and R12 is the author's.

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #34, 2026-09-07T1100Z: 6 of 11 (R2, R4, R5, R6, R7, R9), unchanged — and unchanged is the
correct answer this lap rather than a stall.** Two lines moved inside this 24 h window (R9 at 05:00Z, R7 at 08:00Z), so
the "zero for two consecutive critic laps" direction finding does not fire. Checked on disk at `2720840`, re-run rather
than read.

- ⚠⚠ **R1's red is CLEARED, and R1 still does not tick.** Critic #33's finding #1 was `gates.py --mode full` exiting
  **1** in the routine's default clone on `web/finals.html`'s aged-out stamp. Re-measured here **on the default clone
  before any deepening**, which is the reading that matters and the one two laps skipped: `is-shallow-repository` =
  `true`, `rev-list --count HEAD` = **50**, `gates.py --mode full` exits **0**, **ALL GREEN**, `1650 passed, 62 skipped,
  2 xfailed`, pytest 260.6 s. `web/finals.html` names `7308b06`, **6** commits behind `HEAD`, inside the new limit of
  30. WFG-119's (a), (b) and (c) all shipped and its carrier gate is depth-independent, so the recurrence was closed
  rather than reset. **R1 remains ☐ on its original and only sized blocker: WFG-110.** `scripts/finals.template.html`
  references **28** registry keys, `docs/auto/DEMO_SCRIPT_5MIN.md` §3 maps **22** and maps them script → key rather than
  screen → key, and **6** are in no committed mapping table. That is one lap of work and it is the last thing between
  this line and a tick, which is why WFG-110 is DIRECTION position 2.
- **R3 unchanged, and its sandbox half now has a seventh measurement against it.** `verify`, `snapshot-verify`,
  `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d state. Through the GitHub MCP (`curl` is 403
  here): `auto-gates` runs **181 to 205** on `auto/dev` are **22 `success`, 3 `cancelled`, no `failure`**, and run
  **205** at this head is `success` — **no CHARTER §4b finding**. `gates.py --assert-reported --base b2bdaf0` over the
  whole 59-commit window exits **0** with 59 substantive paths. Every **dev** report in the window carries
  `Reviewed by:`; the research report does not (WFG-147). ⚠ R3 cannot tick while the suite reaches the network:
  measured on this lap's own clock, `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 B**) and its `.gz` were written at
  **11:02:33Z**, inside a `pytest-full` run that began about 10:59:40Z, into a directory that held only `.gitkeep` and
  `README.md` at container start. WFG-139, seventh consecutive lap. R3 also still waits on one `make all-checks` on the
  author's laptop.
- **R5 keeps its tick and its one gap is now promoted rather than re-measured.** Re-run at this head: the only
  `산림청` hits in `docs/auto/JUDGE_QA.md` are the two burned-area lines at `:399` and `:1003`, so there is still no
  card for 「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」 while the kit prints three pages that
  invite it. Seventh consecutive lap measured, and the sixth to decline to promote it. **WFG-144 is this lap's one row
  move, P1 → P0 at position 1** (CHARTER §14b: judge-facing, larger than minutes, therefore a P0 row and never a
  preemption).
- **R7 keeps its tick, and it carries one printed error.** Kit `20260907T0953Z`, rebuilt when JUDGE_QA's line-number
  citations were re-cited by test name. `docs/auto/finals/RELATED_WORK_PANEL.md:43` — 3 of the kit's 36 pages, on the
  stick and in the release bundle — dates the 사이언스타임즈 NIFoS article **2026-02-12**. I fetched the article in
  this sandbox rather than inheriting the claim: its byline reads `연합뉴스 2026-02-13` and its 저작권자 line
  `2026-02-13 ⓒ ScienceTimes`; the only `2026/02/12` strings on the page are 연합뉴스 image CDN paths carrying the wire
  id `AKR20260212072300063`. WFG-146, and this lap's one `fix-before-next-row` item. The tick stands because R7's
  conditions are about completeness and provenance hashes, all of which hold; the date is a 제출 자료 deduction and is
  scored there.
- **R2, R4, R6, R9 hold. R8, R11 unchanged**; R10 stays withdrawn and R12 is the author's. I did not re-measure
  WFG-110's six registry keys myself and do not tick on a number I did not take.

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #33, 2026-09-07T0800Z: 6 of 11 (R2, R4, R5, R6, R7, R9). R7 is ticked, a line moves for
a second consecutive lap, and the two that moved are the two the loop has been circling since 09-05.** Checked
on disk at `2896c9c`, re-run rather than read. ⚠⚠ **And the same measurement that ticks R7 found `gates.py
--mode full` RED in this sandbox on a correct tree**, which is finding #1 and is written under R1 below.

- **R7 ticks.** Every condition re-measured here: six source hashes, the PDF hash, 36 = 5+6+17+3+2+3 pages
  against 36 `/Type /Page` objects, the stamp in the bundle manifest, and the three committed
  `dispatch_a4.pdf` sample sheets opened on disk. The call the 0711Z dev lap left to the critic (「whether
  four-of-five with a stated exclusion satisfies this line」) is answered on R7's row with its ground and its
  falsifiable alternative, so no later lap re-derives it. WFG-026 closed R7's last unwritten document.
- ⚠⚠ **R1 takes finding #1, and it is a red gate that WFG-119 predicted in writing and priced as hygiene.**
  `gates.py --mode full` at `2896c9c` in this sandbox exits **1**: `2 failed, 1646 passed, 62 skipped,
  2 xfailed`, cold, 247.0 s. Both failures are `tests/test_finals_screen.py`
  (`test_the_integrity_panel_names_a_commit_this_repository_has`,
  `test_the_escape_this_gate_cannot_close_is_still_open`) and both say the same thing: `web/finals.html`
  names commit **`62b58e1`**, which this clone cannot resolve. The clone was the routine's default,
  `is-shallow-repository` = `true`, `rev-list --count HEAD` = **50**. `62b58e1` is **55** commits behind
  `HEAD` and was built at 2026-09-06T09:21Z, so it now sits outside a depth-50 horizon. After
  `git fetch --unshallow` (531 commits) both tests pass and `62b58e1` resolves and is on `origin/auto/dev`.
  **WFG-119 wrote this event down before it happened**, in those words: 「once a stamp ages past 50 commits
  without `make finals` being re-run the ancestry test goes RED in every sandbox while staying GREEN in CI,
  which checks out at `fetch-depth: 0`」. GitHub run **201** at this exact head is `success`, so both halves
  of the prediction are confirmed. **The gate is right and the tree is wrong:** the screen a judge opens
  reports a build 55 commits and 23 hours stale, and `make finals` is the remedy the gate's own message
  prints. The 0711Z dev lap hit the identical two failures, unshallowed, wrote 「nothing in the tree was
  wrong」 and filed nothing. WFG-119 raised P1 → P0, and it is this lap's one `fix-before-next-row` item.
- **R3 keeps its sandbox half only as far as the unshallowed re-run goes**, and its CI half is clean.
  `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN is the documented CHARTER §3d
  state. Through the GitHub MCP (WFG-119 records the `curl` 403): `auto-gates` runs **182 to 201** on
  `auto/dev` are **17 `success` and 3 `cancelled`** with **no `failure`**, and run 201 at this head is
  `success`, so there is no CHARTER §4b finding. `--assert-reported --base b70e464` over the whole 24 h
  window (58 commits) exits **0** with 56 substantive paths. Every **dev** report in the window carries
  `Reviewed by:`; the research report still does not (WFG-147, unchanged). R3 still waits on one
  `make all-checks` on the author's laptop and on WFG-139.
- **R5 keeps its tick and its one gap is now sharper than 「no card exists」.** I re-ran the drill: the only
  `산림청` hits in `docs/auto/JUDGE_QA.md` are about burned-area figures and there is still **no card** for
  「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」 (**WFG-144**, P1, fifth lap measured).
  What changed this window is that the **printed** panel now answers it in three pages inside the kit, while
  the bank the student rehearses does not. A judge asks the question, the student has no rehearsed answer,
  and is holding a page that has one. That asymmetry is new and it is what WFG-144 is now worth.
- ⚠ **Sourcing spot-checked rather than accepted, and the one error found is the propagation of a row already
  filed and parked.** `docs/related_work.md:104` and `:187` and `docs/auto/finals/RELATED_WORK_PANEL.md:43`
  all date the 사이언스타임즈 NIFoS article **2026-02-12**. I re-fetched the page: its own byline and its
  저작권자 line both read **2026-02-13**, twice. The three `2026/02/12` strings on that page are Yonhap image
  CDN paths and the wire id `AKR20260212072300063`, that is, the **연합뉴스 original's** date, republished by
  사이언스타임즈 one day later. So the repository pairs 사이언스타임즈 with 연합뉴스's date, which CHARTER §3
  rule 5b makes load-bearing. **WFG-146 filed this on 09-06 as 「one character」 in a knowledge note and left
  it P1; in the 24 h since, it has reached a page that prints inside the booth kit.** Row updated, not
  duplicated. The manuscript is clean: it cites `@nifos2026guide` and carries no date of that article.
- **R2, R4, R6, R9 hold. R8, R11 unchanged**; R10 stays withdrawn and R12 is the author's. I did not
  re-measure WFG-110's six registry keys and do not tick on a number I did not take.

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #32, 2026-09-07T0500Z: 5 of 11 (R2, R4, R5, R6, R9). R9 is ticked, and it is the first
line to move in nine critic laps.** Every one of R9's five named conditions was re-run in this sandbox at
`0fc6130` rather than read from the lap that built it — `make finals-bundle` exits 0 at **19 files**,
`check_bundle_copy.py` exits 0, `git status` is empty afterwards, and the manifest's array holds the booth
kit and its provenance file. The reasoning for the call the dev lap left to the critic, and the one defect
that rides inside the bundle without holding the tick, are both written into R9's cell below. R7 is now
blocked by exactly one unwritten document (WFG-026) and owes one correction to its own wording (WFG-153).

*(Superseded, kept as the record, CHARTER §3.7.)* **Tick count, critic #31, 2026-09-07T0206Z: 4 of 11 (R2, R4, R5, R6), unchanged for an EIGHTH consecutive
critic lap — and this is the first of the eight where I can name, for each of the two lines that should
have moved, the single small thing that blocks it and has never been anyone's item.** Checked on disk at
`3f881f6`, re-run rather than read, on a clone fully unshallowed (`git rev-parse --is-shallow-repository`
answers `false`, 517 commits).

- **The window's dev lap closed four rows and the count still did not move, and that is not the lap's
  fault.** The 01:09Z lap shipped WFG-148, WFG-140, WFG-134 and WFG-130: the README bullet gained the
  second of its paper's two binding caveats, a freshness gate ended a four-drift series, and the booth kit
  was rebuilt at `20260907T0059Z` with the reconciliation sheet in it for the first time. **R7 and R9 are
  the two lines that work was aimed at, and each is now one small piece short:**
  - **R7 needs `WFG-026`,** the related-work and SFTD059T differentiation panel, which is not written. The
    kit's own `what_this_does_not_show` says so in those words. It was sitting at **P1**, below the five
    P1 infra rows that CHARTER §14b holds *behind R7*. That is this lap's one row move: **WFG-026 P1 → P0**.
  - **R9 needs the printables to be in the bundle.** They are not. This lap's one `fix-before-next-row`
    item, **WFG-151**.
  So the eighth zero is not another instance of NH-038's pattern (a critic's document correction crowding
  out product work) — the last lap *was* product work. It is an ordering defect that the loop could see
  and did not, and both halves of it are now filed. Eighth data point recorded in **NH-038** all the same,
  because the author's rule is what set the order.
- **R7 does not tick, and for the first time the reason is not drift.** Re-hashed here in one process at
  `3f881f6` against `manifest_20260907T0059Z.json`: all **five** `SOURCES` match the tree —
  `BOOTH_SETUP.md` `99b2168f4b…`, `DEMO_SCRIPT_5MIN.md` `b1aae78f35…`, `JUDGE_QA.md` `ec75a1657d…`,
  `submission_reconciliation.md` `237de4f4ae…`, `DETECTION_FLOOR_CARD.md` `84648d4d6e…`. The PDF's own
  sha256 matches (`a4970b12cdd1…`), `pages_per_source` sums 5+6+17+3+2 = **33** = `pages`, and the PDF
  really carries **33** `/Type /Page` objects. The `af955a30fa…` → `7d5ac4c9c5…` → `175da9e50c…` →
  `5ac45ea810…` series is over. What is left of R7 is one unwritten document.
- **R9 does not tick, and the reason is measured rather than inherited from its own cell.**
  `release/kcf-finals-2026/MANIFEST.json` lists **17 files** and no printable. `build_finals_bundle.py:57`
  `PAYLOAD` names no PDF. The first kit existed at `3e92b69` (2026-09-06T06:51Z) and the bundle manifest
  was rebuilt at `1ec1d06` (09:34Z), **2 h 43 m later**, gaining only a `web/finals.html` hash. Nothing
  went red because `tests/test_finals_bundle.py:41` compares the manifest to the **builder's own plan**,
  and `:74`, the one place R9's list is transcribed into code, asserts four screens, fonts, `CITATION.cff`,
  `LICENSE` and `README_KO.md` and never the printables. **WFG-151.**
- **R3 sandbox half green; CI half clean.** `gates.py --mode full` **ALL GREEN** at `3f881f6`, exit 0
  (`1632 passed, 62 skipped, 2 xfailed`, **cold**, 349.5 s); the 01:09Z lap's **warm** re-run reported
  `1638 / 56` on a tree differing only in prose, the same six-test gap for a fourth consecutive critic lap,
  which is **WFG-139** and is still `todo`. `verify`, `snapshot-verify`, `env-check` PASS;
  `baseline-verify` WARN is CHARTER §3d information. Through the GitHub MCP (WFG-119 records the `curl`
  403): `auto-gates` runs **171 to 190** on `auto/dev` are **18 `success` and 2 `cancelled`** with **no
  `failure`**, and run **190** at this head is `success`. `--assert-head` exits 0; `--assert-reported`
  over the whole window exits 0 (52 substantive paths, all carried by reports). Every **dev** report in
  the window carries `Reviewed by:`; the research report still does not (**WFG-147**). R3 still waits on
  one `make all-checks` on the author's laptop, and on WFG-139.
- **R5 keeps its tick, and its one gap is now also a mechanical one.** Q39 is repaired and true from the
  `20260907T0059Z` build; Q40 states the network defect honestly. ⚠ There is still **no card** for
  「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」 — I re-ran the drill and the only
  `산림청` hits in `JUDGE_QA.md` are about burned-area figures, unrelated. That is **WFG-144**, and it can
  no longer be written by a critic or research lap at all: editing `JUDGE_QA.md` turns the new freshness
  gate red (**WFG-152**, probed and reverted here).
- **R1, R2, R4, R6, R8, R11 unchanged**; R10 stays withdrawn and R12 is the author's. I did not re-measure
  WFG-110's six registry keys and do not tick on a number I did not take.
- **Sourcing spot-checked rather than accepted.** The window's new external prose is the manuscript's
  Related-work paragraph on the two Korean operational systems and its two `references.bib` entries. Both
  carry `verified 2026-09-06` notes with agency, series or publication date, scope, and an explicit
  statement that no accuracy or validation figure exists on either page — CHARTER §3 rule 5b in the form
  the rule asks for. The manuscript makes no accuracy comparison in either direction and cites neither the
  사이언스타임즈 article that **WFG-146**'s one-day date error is in; that row is unchanged and untaken.

**Tick count, critic #30, 2026-09-06T2317Z: 4 of 11 (R2, R4, R5, R6), unchanged for a SEVENTH consecutive
critic lap. This window DID contain a dev lap, so unlike last time the 「zero across two consecutive laps」
rule fires, and it fires about the loop's direction and not about the product.** Checked on disk at
`524f13c`, re-run rather than read, on a clone fully unshallowed (`git rev-parse --is-shallow-repository`
answers `false`, 508 commits).

- **Why the zero is a direction finding this time, stated before anything else.** The 20:17Z dev lap ran,
  claimed **WFG-138** and closed both of its halves, and the work is real: the README's headline bullet no
  longer asserts what the manuscript disclaims, the spoken Q19 draft carries the same caveat, and two test
  modules go red if either slips back. It ticked no readiness line because it could not: WFG-138 is a
  correction to a document this loop wrote, and every readiness line is an artifact a judge opens.
  **That is now five of the last six dev laps** (WFG-007 was the exception, and it is what put R7 within
  reach): WFG-113, WFG-117, WFG-133, WFG-138 were each some critic's one `fix-before-next-row` item. Each
  was worth doing. The sum is that `docs/auto/KCF_READINESS.md` has not moved since 2026-09-05 while the
  sprint is over halfway through, and R7 and R9 still wait on the same trio, WFG-134 + WFG-140 + WFG-130,
  now displaced a **fifth** window. The measurement goes to **NH-038**, which asks the author this exact
  question, because the rule that produces the pattern is theirs and neither a dev lap nor a critic lap
  may change it. ⚠ **And this lap does it again:** my one item, **WFG-148**, is another document
  correction. I file it anyway because it is on the README opening and it is twenty minutes, and I have
  written into the item that the same lap must then take WFG-134. That is the most a critic can do inside
  the rule as written.
- **R3 sandbox half green; CI half clean; and the cold/warm gap is now a controlled demonstration.**
  `gates.py --mode full` is **ALL GREEN** at `524f13c`, exit 0: `1616 passed, 62 skipped, 1 xfailed`,
  **cold**, 350.4 s. The 2154Z dev lap reported **warm** `1622 / 56` at `8e902dd`, a tree that differs
  from this one only in prose and generated board files. The difference is **exactly six tests in each
  direction**, which is **WFG-139**: the first suite run in a sandbox downloads the SRTM tile and every
  later run in that sandbox executes six more tests. Same defect, two sandboxes, one lap apart, and it is
  the cleanest evidence for that row anyone has produced. `verify`, `snapshot-verify` and `env-check`
  PASS; `baseline-verify` WARN is CHARTER §3d information. Read through the GitHub MCP (WFG-119 records
  the `curl` 403): `auto-gates` runs **165 to 184** on `auto/dev` are **18 `success` and 2 `cancelled`**,
  with **no `failure` at all**; run 184 at this head is `success`. `--assert-head` exits 0. Every push in
  the window carried a report, checked pair by pair. Every **dev** report carries `Reviewed by:`; the
  research report does not (**WFG-147**). R3 still waits on one `make all-checks` run on the author's
  laptop, and WFG-139 is untaken.
- **R7 does not tick, and the fourth drift is the first one that makes the printed pages WORSE.**
  Re-hashed in one process at this head: `BOOTH_SETUP.md` `ef7342dacf…`, `DEMO_SCRIPT_5MIN.md`
  `b1aae78f35…` and `DETECTION_FLOOR_CARD.md` `84648d4d6e…` all **match**; `docs/auto/JUDGE_QA.md`
  manifest `2c8451211e5f97…` against tree **`5ac45ea8103f11…`**. The PDF still matches its own manifest
  sha256, so `tests/test_printables.py` stays fully green over it. Series: `af955a30fa…` (#27) →
  `7d5ac4c9c5…` (#28) → `175da9e50c…` (#29) → **`5ac45ea810…`** (here). Critic #29's root objection was
  that all three earlier drifts were the loop's own correction notes rather than judge-facing
  improvements. **This one is a judge-facing improvement, which is precisely why it is worse than the
  three before it:** the 17 printed Q&A pages now carry Q19's answer **without** the fire-blind caveat
  that the repository decided in the same window is mandatory and now enforces in two test modules. The
  paper in the student's hand and the files the gates read disagree about what the student may say aloud.
  WFG-134 rebuilds and **WFG-140** is the gate that ends the series.
- **R8 does not tick, and the reason is no longer the defect critic #28 filed.** That defect is fixed:
  `README.md:22-33` states the fire-blind control inside the bullet and names the fair opponent's region
  scope. What holds R8 now is the **second** of the two caveats `paper/manuscript.md:506` says bind the
  same comparison: the forecast-aware arm plans on the hazard field it is graded against, so the 42 is
  what a **noiseless** forecast buys. `grep -niE "perfect|oracle|upper bound|상한|noiseless" README.md`
  returns **nothing** at this head. `docs/present_perimeter_arm.md` §5 states it and calls it 「a property
  the 91 has always had, inherited not introduced」; `docs/real_roads_real_hazard.md` hands both arms the
  same `HazardSequence`; `evacuation.py:270` says the fire-blind arm is 「then scored against the hazard」.
  And `tests/test_future_aware_attribution.py:135` `_is_caveated` accepts one CONTROL spelling and asks
  nothing else, so the new gate is green on it. Filed as **WFG-148**, this lap's one item. R8's own
  Round-4 and abstract half is unchanged and untaken.
- **R5 keeps its tick.** Q19's spoken draft is stronger than it was and 50 judge-qa, printables and
  fair-opponent tests are green over the file. ⚠ Still **no card** for
  「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」 (**WFG-144**, P1), which the paper
  now answers in its Related work at `719c420` while the bank does not. That is the one row whose
  promotion the research lap asked for.
- **R1, R2, R4, R6, R9, R11 unchanged**; R10 stays withdrawn and R12 is the author's. I did not re-measure
  WFG-110's six registry keys and do not tick on a number I did not take.
- **Sourcing spot-checked rather than accepted.** The window's only new external prose is the
  manuscript's Related-work paragraph on the two Korean operational systems (`719c420`). Both new
  `references.bib` entries carry a `verified 2026-09-06` note, an agency, a date and an explicit
  statement that no accuracy figure exists on either page, which is CHARTER §3 rule 5b satisfied in the
  form the rule asks for; the `khan2026gdaps` URL slug `202603301116001` agrees with the `30 March 2026`
  the entry records. **WFG-146** (the knowledge note's one-character date error on the 사이언스타임즈
  article) is unchanged and untaken; it did not propagate into the manuscript, which does not cite that
  article.


**Tick count, critic #29, 2026-09-06T2015Z: 4 of 11 (R2, R4, R5, R6), unchanged for a SIXTH consecutive
critic lap — and this is the first of those six windows that contained no dev lap at all, so the count
could not have moved.** Checked on disk at `1b26c3a`, re-run rather than read, on a clone fully unshallowed
(`git rev-parse --is-shallow-repository` answers `false`, 500 commits).

- **Why the zero is not a direction finding this time, stated before anything else.** `git diff
  e95fe28..1b26c3a` changes **zero lines outside `docs/auto/`**. The 18:17Z slot was ceded to the research
  routine (CHARTER §14, `LOOP_CONFIG.json` -> `research_cadence_note`, the author's 2026-09-04 decision),
  so the window holds one critic report and one research lap and nothing else. A window with no dev lap
  cannot tick a readiness line, and reading that as a failure of direction would be a false reading. The
  routine's rule (zero across two consecutive laps is a direction finding) is therefore **recorded and not
  fired**; the measurement went to **NH-038**, which asks the author this exact question and now carries a
  sixth data point. The mechanism the window exposed is **WFG-145**.
- **R3 sandbox half green; CI half clean; and the cold count is unchanged, which is the correct result.**
  `gates.py --mode full` is **ALL GREEN** at `1b26c3a`: `1599 passed, 62 skipped`, cold, 273.6 s — **identical**
  to critic #28's cold `1599 / 62` at `e95fe28`, like for like, which is what a window with no code in it
  should produce. `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN is CHARTER §3d
  information. Read through the GitHub MCP (WFG-119 records the `curl` 403): `auto-gates` runs **161 to 180**
  on `auto/dev` are **17 `success` and 3 `cancelled`** (`dfdf480`, `828bbae`, `ef61e9b`, each superseded by a
  green push), with **no `failure` at all**, so there is no gate finding and no CHARTER §4b finding this lap.
  Run 180 at `1b26c3a`, this head, is `success`. `--assert-head` exits 0. Every **dev** report in the window
  carries `Reviewed by:`. ⚠ The one report in the window that carries no such line is the research lap's
  (`2026-09-06T1838Z-research.md`), which is a gap in the routine's prompt rather than a missing practice —
  **WFG-147**. R3 still waits on one `make all-checks` run on the author's laptop, and WFG-139's network
  test is unchanged and untaken.
- **R7 does not tick, and the kit has drifted a THIRD time — written by critic #28's own commit.** I
  re-hashed all four manifest `SOURCES` against the tree here in one process: `BOOTH_SETUP.md`
  `ef7342dacf…`, `DEMO_SCRIPT_5MIN.md` `b1aae78f35…` and `DETECTION_FLOOR_CARD.md` `84648d4d6e…` all
  **match**; `docs/auto/JUDGE_QA.md` manifest `2c8451211e5f97…` against tree **`175da9e50c5ce9…`**. The PDF's
  own sha256 still matches its manifest, so `tests/test_printables.py` stays fully green over it. The series
  on that one file is `af955a30fa…` (#27) -> `7d5ac4c9c5…` (#28) -> `175da9e50c…` (here), and **all three
  drifts were correction notes written by critic or dev laps, not judge-facing improvements** — #27's Q35
  note at `a64b904`, the WFG-133 lap at `923ffbd`/`32de531`, and critic #28's own `050731a`. This lap adds a
  fourth for the same reason and does not exempt itself. **That is this report's root objection**, because
  `WFG-144`'s cell now sequences a genuinely new judge-facing card behind the rebuild 「or the printed 17
  pages go stale a fourth time」, while the laps making that argument spend the same freshness on themselves.
  WFG-134 rebuilds, **WFG-140** is the gate, and the gate is the half that dissolves the sequencing argument.
- **R8 does not tick and its defect is one clause wider than critic #28 measured.** `README.md:22-26` is
  unchanged and still says 42 of 458 reach a refuge 「**only** when the router accounts for where the fire
  **will be**」, so **WFG-138** is `todo` — but the item was never in front of a dev lap (see the first
  bullet), so critic #28's falsifiable test on it **could not be run and I do not report its verdict**. What
  the judge drill added: `docs/auto/JUDGE_QA.md` **Q19**'s draft answer carries 「영덕에서 458개 원점 중 **42**개,
  의성·안동에서 368개 중 **91**개가 시간 인지 경로에서만 …」, and the ⚠ block directly beneath it corrects the
  **91** and leaves the **42** untouched in the same sentence. Both come from the same fire-blind control
  (`src/wildfireguardian/routing/evacuation.py:270`); 영덕 needs the caveat **more**, because the
  present-perimeter opponent has only ever been run on 의성·안동
  (`data/processed/present_perimeter_arm_uiseong_andong_2025.json`). A dated ⚠⚠ note with the sentence to say
  is on Q19 at this head and 50 judge-qa, printables and fair-opponent tests are green over it. WFG-138 is
  widened by that half and **carried forward** as this lap's one item rather than re-filed.
- **R5 keeps its tick.** The bank gained one correction note and no card changed its answer; the drill's
  finding is R8's, above. ⚠ The bank still has **no card** for 「산림청·경기도가 이미 산불확산예측을 하고 있는데
  무엇이 다릅니까?」 (**WFG-144**, P1), which is the most likely question a disaster-response judge asks, and
  the research lap's own page says that if the author promotes one row it is that one.
- **R1, R2, R4, R6, R9, R11 unchanged**; R10 stays withdrawn and R12 is the author's. I did not re-measure
  WFG-110's six registry keys and do not tick on a number I did not take.
- **Sourcing re-checked rather than accepted**, because the window's only substantive prose is a new
  landscape note whose sources no gate can read. I re-opened both live URLs: 경향신문 (G-DAPS) confirms the
  date, the 30-minute steps, the 읍면동 unit, the **589** alert facilities, the following-month trial, and
  **no accuracy figure**; 사이언스타임즈 confirms every NIFoS figure the note quotes. **One error: the note
  dates that article 2026-02-12 and the page says 2026-02-13** — one character, filed as **WFG-146** because
  CHARTER §3 rule 5b makes the date part of what licenses the figure.

**Tick count, critic #28, 2026-09-06T1736Z: 4 of 11 (R2, R4, R5, R6), unchanged for a FIFTH consecutive
critic lap — and this lap's finding is that one of the ticked-adjacent claims, the one about running on a
clean clone, is false.** Checked on disk at `e95fe28`, re-run rather than read, on a clone **fully
unshallowed** (`git rev-parse --is-shallow-repository` answers `false`, 496 commits).

- **R3 is the line this lap moves against, and it does not lose its half-green so much as change what the
  green means.** `gates.py --mode full` is **ALL GREEN** at `e95fe28`: `1599 passed, 62 skipped`, cold,
  288.4 s (critic #27's cold `1569 / 62`: **+30 passed**, skips unchanged). `verify`, `snapshot-verify`,
  `env-check` PASS; `baseline-verify` WARN is CHARTER §3d information. CI half clean: read through the
  GitHub MCP (WFG-119 records the `curl` 403), `auto-gates` runs **#154 to #178** on `auto/dev` are **21 <!-- forbidden-ok: 154 -->
  `success` and 4 `cancelled`**, **no `failure` at all**, so there is no gate finding and no CHARTER §4b
  finding this lap. Run 178 at `e95fe28`, this head, is `success`. `--assert-head` and `--assert-reported`
  both exit 0, and every dev report in the window carries `Reviewed by:`. ⚠⚠ **What is new is that the
  clean-clone run is not clean.** On a clone created at 16:57Z with no `data/raw/` at all, the gate run
  wrote `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 bytes**) at 17:02Z, fetched from
  `elevation-tiles-prod.s3.amazonaws.com` by `tests/test_spread_warmup.py:156`, which passes
  `dem_source="srtm"` with no skip guard. `docs/clean_clone_gates.md:27` reads 「No network, no keys, no
  `.env`.」 and is one of the three files `docs/auto/JUDGE_QA.md` **Q28** cites to a judge. CHARTER §4b:
  「No test may depend on the local clock, the timezone, the network, or files outside the repository.」
  **WFG-139.** Six tests keyed on that tile (`test_srtm_dem.py:81/:94/:109/:170`,
  `test_validation_robustness.py:57`, `test_validation_session3.py:171`) are `skipif`-guarded and `skipif`
  is evaluated at collection, so on every fresh CI clone the download always lands after the decision to
  skip: **those six have never run in CI.** They are the terrain-plausibility checks (ocean clipped to 0 m,
  max elevation at least 400 m, east strip lower than west) on the DEM the router walks over. This is also
  the whole of the cold/warm split the loop has diagnosed twice and never chased: cold `1599 / 62`, warm
  `1605 / 56`, same commit, both measured here, delta exactly those six. R3 keeps its sandbox half-green
  because the suite does pass; what it can no longer be read as is evidence that a stranger with no network
  gets the same answer.
- **R7 does not tick and the kit is staler than critic #27 left it.** I re-hashed all four manifest sources
  against the tree at `e95fe28`: `BOOTH_SETUP.md`, `DEMO_SCRIPT_5MIN.md` and `DETECTION_FLOOR_CARD.md`
  match; `docs/auto/JUDGE_QA.md` does not, and the tree hash has moved again — manifest `2c8451211e…`,
  tree **`7d5ac4c9c5…`** where critic #27 measured `af955a30fa…`, because the WFG-133 lap edited Q35 after
  that measurement. So the printed 17 Q&A pages carry the pre-WFG-117 Q30 **and** Q35's ⚠ block with **no**
  retraction on it, since critic #27's ⚠⚠ note landed at `a64b904`, after the `3e92b69` build. Critic #27
  pre-registered this branch: if any source is still stale, file the gate separately. Done — **WFG-140**.
  WFG-130 and WFG-134 keep the rebuild.
- **R8 does not tick and takes a new defect that is worse than staleness.** `README.md:22-26` asserts that
  42 of 458 origins reach a refuge 「**only** when the router accounts for where the fire **will be**」.
  `paper/manuscript.md`'s Abstract carries the same two numbers and then says the contrast 「does not
  separate knowing where the fire will be from knowing where it is」, because the baseline is fire-blind
  (`src/wildfireguardian/routing/evacuation.py:270`). `paper/GAPS.md` G7 records that the abstract was
  corrected for exactly this, and names the booth script (WFG-103) and the finals template (WFG-109) as the
  two surfaces already repaired. The README is the fourth and was never touched. **WFG-138**, and it is this
  lap's one `fix-before-next-row` item.
- **R1, R2, R4, R5, R6, R9, R11 unchanged**; R10 stays withdrawn and R12 is the author's.
- **Zero ticks for a FIFTH consecutive critic lap, and this time I do not think the direction is right.**
  Critics #26 and #27 each read the same count and concluded the window had done its one item well, which
  was true both times. What the fifth reading exposes is the mechanism rather than any lap: the last three
  dev laps each built a critic's `fix-before-next-row` item, all three on documents the loop wrote, and
  nothing has finished the booth kit since it landed at `3e92b69` on 09-06 at 06:20Z. The sprint plan names
  09-11 for the printables and 09-10 for the bundle. The cap of one item per critic lap is also a floor of
  one, and it is a cap on the number of items rather than on their cost. That is **NH-038**, and I am asking
  the author rather than widening the rule myself, because §14b is the author's steer.

**Tick count, critic #27, 2026-09-06T1400Z: 4 of 11 (R2, R4, R5, R6), unchanged — and this lap's finding is
that the surface a line is ticked on and the surface a human meets are not the same object.** Checked on
disk at `dd500e6`, re-run rather than read from a report, on a clone **fully unshallowed**
(`git rev-parse --is-shallow-repository` answers `false`, 488 commits), which is the control the last seven
laps on this page did not have.

- **R1 is unchanged and waits on WFG-110's six unmapped registry keys alone.** The `41498ef` half stays
  **withdrawn** and is now verified with the instrument rather than around it: on the unshallowed clone
  `git merge-base --is-ancestor 41498ef HEAD` exits **0**, `git rev-list --count 41498ef..HEAD` answers
  **283** (critic #26's 277 plus this window's six commits, so the two measurements agree), and
  `git branch -a --contains 41498ef` names `auto/dev`, `origin/auto/dev` and `origin/Main`. The counts half
  stays fixed: `web/finals.html` prints `n_entries` **383** / `n_reproducible` **325** against a registry
  holding 383 / 325 / 58-not, counted here in one process. I did not re-measure WFG-110's six and do not
  tick on a number I did not take.
- **R5 keeps its tick and takes a defect on it that is worse than the one it took last lap, because this
  one is a false statement rather than a stale one.** `docs/auto/JUDGE_QA.md` Q35 is **T1**, the
  reproducibility question. Its ⚠ block tells the student **not** to say the draft's true sentence
  「현재 브랜치에서 닿는 커밋입니다」 and to say instead 「레지스트리 카드의 각인은 … 지금 브랜치에서
  닿지 않습니다」. That is false at this head and at every head since the object was written. It also
  asserts the card prints **326** where the screen prints **383**. **Critic #26 withdrew that measurement
  in this very cell at 1100Z and wrote 「`JUDGE_QA.md` Q35 is correct as written and must not be edited」**,
  which is true of Q35's draft answer and false of the ⚠ block that overrides it; the effect was to protect
  the false half from repair for a full window. WFG-133, and it is this lap's one `fix-before-next-row`
  item. The tick survives on R5's literal condition (Q35 is T1, not T0; the bank's self-count is unchanged;
  `tests/test_judge_qa_bank.py` is 23 green inside the full run below) and a dated ⚠⚠ correction note with
  the measured table is on Q35 at this head so nobody rehearses the false block.
- **R7 does not tick and now has a second reason, which is about freshness rather than contents.**
  WFG-130 is unchanged: the kit contains one of the five printables R7 names and its manifest still says
  the reconciliation sheet 「does not exist yet」 while `docs/submission_reconciliation.md` is the file R6's
  own tick is written on. **New this lap: the kit is also stale.** I re-hashed all four sources against the
  tree. `BOOTH_SETUP.md`, `DEMO_SCRIPT_5MIN.md` and `DETECTION_FLOOR_CARD.md` match; `docs/auto/JUDGE_QA.md`
  does not — manifest `2c8451211e5f97eb…`, tree `af955a30fa500391…`. The PDF was built at `3e92b69` and
  WFG-117 rewrote Q30 at `fc05320`, so **the 17 printed Q&A pages carry the pre-WFG-117 Q30 with the
  「326 · 268」 warning this window removed, plus Q35's false block.** `tests/test_printables.py` checks
  that the manifest *has* a hash per source and that the PDF matches its own hash; nothing compares a
  recorded source hash against the tree, which is the one comparison that detects this. WFG-134.
- **R3 sandbox half green; CI half clean.** `gates.py --mode full` is **ALL GREEN** at `dd500e6`
  (`1569 passed, 62 skipped`, cold, 304.3 s, against critic #26's cold `1565 / 62`: **+4 passed**, skips
  unchanged). `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is CHARTER §3d
  information. Read through the GitHub MCP (WFG-119 records the `curl` 403): the **25** most recent
  `auto-gates` runs on `auto/dev`, numbers **145 to 173**, are **22 `success` and 3 `cancelled`**
  (`828bbae`, `ef61e9b`, `9ebf5a5`, each superseded by a green push). **No `failure` at all, so there is no
  gate finding and no CHARTER §4b finding this lap.** Run 173 at `dd500e6`, this head, is `success`.
  `--assert-head` and `--assert-reported` both exit 0. Every dev report in the window carries
  `Reviewed by:`. ⚠ One small correction to critic #26's cell: it wrote that every *critic* report of the
  last 24 h carries `Reviewed by:` too, and `docs/auto/reports/2026-09-05T2330Z-critic.md` does not. Critic
  laps have no subagent reviewer by design, so this is a wrong sentence rather than a missing practice, and
  it is not a finding. R3 still waits on one `make all-checks` run on the author's laptop.
- **R2, R4, R6 hold. R8, R10, R11, R12 unchanged**, and R12 is the author's.
- **Zero ticks for a FOURTH consecutive critic lap, and the direction is still not what is wrong.** The
  window cleared critic #26's one item, cleared it well, and shipped a gate that did not exist. What the
  count exposes this time is narrower than last time and cheaper to fix: **the loop measures whether a
  correction was made, never whether it arrived.** Both of this lap's findings are one correction that
  reached the pages the loop reads and stopped at the surfaces a human meets — Q35's card, and the printed
  kit. That is WFG-133 and WFG-134, and the standing rule is now on `DIRECTION.md`: grep the judge-facing
  surfaces for the withdrawn string before writing 「withdrawn」 anywhere.

**Tick count, critic #26, 2026-09-06T1100Z: 4 of 11 (R2, R4, R5, R6), unchanged — and this lap's finding is
that one of the reasons R1 has been ☐ was never real.** Checked on disk at `b2bdaf0`, re-run rather than read
from a report, and on a clone **deepened to 300 commits with the depth recorded beside every claim**.

- **R1: two of its three recorded defects are gone, and the second one was never there.** The counts are
  fixed: `web/finals.html` prints `n_entries` **383** and `n_reproducible` **325**; `docs/NUMBERS.json`
  holds 383 entries, 325 reproducible, 58 not, counted here in one process. WFG-113 is `done(20260906T0920Z)`
  and this is critic #25's falsifiable-test branch (1): **the repair ran, and WFG-119's ten-hour clock is
  reset** — the screen's stamp is now `62b58e1`, **6** commits behind `HEAD` rather than 29.
- ⚠⚠ **The second defect on this line is WITHDRAWN, and it stood for five critic laps.** `41498ef` **is**
  an ancestor of `HEAD`. Measured here: `git merge-base --is-ancestor 41498ef HEAD` exits **0**,
  `git rev-list HEAD | grep -c 41498efbf0679276c140b3cbfc0819e5265e7733` answers **1**,
  `git rev-list --count 41498ef..HEAD` answers **277**, and `git branch -a --contains` names `auto/dev`,
  `origin/auto/dev` and `origin/Main`. The object sits **277** commits back. Critic #20 raised it in the
  default **depth-50** clone; critic #21 deepened by 120 and re-confirmed; critic #24 deepened to **250** and
  wrote 「so the shallow boundary is not the confounder」. **250 < 277, so it still was.** Critics #20, #21,
  #23, #24 and #25 each wrote 「re-run rather than read」 and each re-ran the same command inside the same
  short instrument. The withdrawal is on **WFG-115**, which drops P0 -> P1 and is re-scoped to the smaller
  defect that survives: the line is **stale by construction and mislabelled** (the registry held 153 entries
  at that commit and the card beside it prints 383), not unreachable. **`JUDGE_QA.md` Q35 is correct as
  written and must not be edited.** Nothing on the judged screen is wrong about reachability.
- **R1 stays ☐ on one thing only: WFG-110's six registry keys with no committed mapping table.** I did not
  re-measure that six this lap and do not tick on a number I did not take. R1 is now one row from tickable,
  which it has not been in twenty-six windows.
- **R5 keeps its tick and takes a defect on it, and the defect inverted inside one window.** `JUDGE_QA.md`
  Q30 is **T0**. Its ⚠⚠ block still tells the student the screen prints **326 · 268**, that pointing at the
  screen leads them to a stale number, and that three counts answer this question. **All three are false at
  this head.** A wrong warning survived a correct repair. WFG-117 is re-scoped, moved to position 2, and is
  this lap's one `fix-before-next-row` item; a dated correction note is on Q30 so the student does not
  rehearse the stale block. The tick survives: the bank's own self-count is unchanged and
  `tests/test_judge_qa_bank.py` is green inside the full run below.
- **R3 sandbox half green; CI half clean.** `gates.py --mode full` is **ALL GREEN** at `b2bdaf0`
  (`1565 passed, 62 skipped`, cold, 199.1 s, against critic #25's `1562 / 62`: **+3 passed**, skips
  unchanged). `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is CHARTER §3d
  information. Read through the GitHub MCP (WFG-119 records the `curl` 403): the **25** most recent
  `auto-gates` runs on `auto/dev`, numbers **140 to 168**, span 2026-09-05T20:21Z to 2026-09-06T10:14Z and
  are **22 `success` and 3 `cancelled`** (`ef61e9b`, `9ebf5a5`, `785ba13`, each superseded by a later push
  that is green). **No `failure` at all, so there is no gate finding and no CHARTER §4b finding this lap.**
  Run 168 at `b2bdaf0`, this head, is `success`. `--assert-reported` exits 0 across the window and every
  dev, paper and critic report in the last 24 h carries `Reviewed by:` (the four without it are `manual`,
  the author's own laptop). R3 still waits on one `make all-checks` run on the author's laptop.
- **R7 and R9 unchanged, and WFG-130 is still the whole of what they wait on**, exactly as critic #25 left
  it: the printables PDF contains one of the five documents R7 names, and the build's manifest still says
  the reconciliation sheet 「does not exist yet」 while `docs/submission_reconciliation.md` is
  `done(20260903T0653Z)` and is the file R6's own tick is written on. Not re-litigated here.
- **R8, R10, R11, R12 unchanged**, and R12 is the author's.
- **Zero ticks for a THIRD consecutive critic lap, and this time the rule points at the instrument.** The
  routine says zero across two laps is a finding about direction. Direction was right again — the window
  cleared critic #25's one item and reset a clock. What the count exposes is that the loop's central honesty
  claim, 「re-run rather than read」, defends against a *stale* reading and not against a *systematically
  wrong instrument*, and it took five laps and one deeper fetch to notice. That is **WFG-119**, whose
  predicted failure turns out to have already happened five times, and it is the root objection of critic
  #26's report.

**Tick count, critic #25, 2026-09-06T0800Z: 4 of 11 (R2, R4, R5, R6), unchanged — and for the first
time in nine laps the reason is not absence.** Checked on disk at `b70e464`, re-run rather than read from a
report.

- **R7 has an object.** `docs/auto/finals/printables/WFG_printables_20260906T0620Z.pdf` exists: **29 A4
  pages**, 395,927 bytes, built by `scripts/build_printables.py` at `3e92b69`, with a manifest recording the
  sha256 of all four sources and all three fonts. I re-hashed every one of them here against the tree: all
  four sources **OK**, the PDF's own sha256 **matches**, so the kit is current rather than already stale.
  Critic #24 left a two-branch falsifiable test on this line — 「(1) if `docs/auto/finals/` holds a PDF, R7
  moves and WFG-007 is finished, say so and stop writing about the queue」 — and **branch (1) is what
  happened.** Nine days of this line reading 「no lap has ever claimed WFG-007」 ended in one window. I am
  therefore not writing about queue position again, and the constraint critics #19 through #24 were
  arguing about (position, then the lock) is settled: it was both, and both are now paid.
- **R7 still does not tick, and the reason is new, specific and cheap.** The line enumerates five
  printables — 「evidence sheet (A4), **reconciliation sheet**, related-work and SFTD059T differentiation
  panel, booth checklist, 29 dispatch sheets sample」. The PDF contains **one** of them (the booth
  checklist) and three documents that are not on the list (demo script, this Q&A bank, the detection-floor
  card). Of the four missing: the related-work panel is WFG-026 and genuinely does not exist; the dispatch
  sheets were deliberately excluded, with a reason, because `outputs/dispatch*` already holds them as
  committed PDFs; and the **reconciliation sheet exists** — `docs/submission_reconciliation.md`, 13,702
  bytes, `done(20260903T0653Z)`, the file **R6's own tick is written on**. The build's manifest says it
  「does not exist yet」. That is **WFG-130**, minutes, and it is the difference between R7 ticking this week
  and not.
- **The finding underneath is about measurement, not about the PDF**, which is good work: the kit was
  assembled from the four documents the loop writes and never compared against the five this page asks
  for. `scripts/build_printables.py:97-101` and R7's own sentence overlap in exactly one item, and nothing
  reads them together. WFG-130's done-when offers both repairs (bind the builder to R7, or correct R7 to
  the documents the booth actually needs) because either one closes the gap and the choice is a lap's.
- **R9 is unchanged and now waits on strictly less.** `release/kcf-finals-2026/MANIFEST.json` lists 17
  files and the printables PDF is not among them; R9's sentence names 「printables」 explicitly. Once
  WFG-130 settles which PDF is the real one, `make finals-bundle UPDATE=1` is the whole of R9's remaining
  agent half.
- **R1 is unchanged and its defect is now sixteen windows old and on a clock.** `web/finals.html:434`
  prints `n_entries` **326** / `n_reproducible` **268**; `docs/NUMBERS.json` holds **383** / **325**,
  counted here in one process. `registry.built_at_commit` is `41498ef`, and `git merge-base --is-ancestor
  41498ef HEAD` still **rejects** on a deepened 250-commit clone. Measured for WFG-119's prediction: the
  screen's own stamp `5f9a3b8` is **29** commits behind `HEAD` today (23 at critic #24), the branch took
  **51** commits in my 24 h, and the sandbox clones at depth **50** — so the stamp crosses the shallow
  boundary in roughly **ten hours**, after which `gates.py --mode full` goes RED in every sandbox on a
  screen that is not wrong, and CHARTER §9 spends the first lap that hits it on parking. This is my one
  `fix-before-next-row` item; see `docs/auto/CRITIC_LATEST.md`.
- **R3, R8, R10, R11, R12 unchanged**, and R12 is the author's. `gates.py --mode full` is **ALL GREEN** at
  `b70e464` in this sandbox (`1562 passed, 62 skipped`, cold, 298.9 s, against critic #24's `1545 / 62`:
  **+17 passed**, skips unchanged). Read through the GitHub MCP rather than `curl` (WFG-119 records the
  403): the twenty most recent `auto-gates` runs on `auto/dev`, run numbers 140 to 163, spanning
  2026-09-05T20:21Z to 2026-09-06T07:25Z, are **nineteen `success` and one `cancelled`** — `9ebf5a5`,
  critic #24's own push, superseded four minutes later by `3656bea`, which is green. **No red run sits
  behind a green report, so there is no gate finding and no CHARTER §4b finding this lap.** R3 still waits
  on one `make all-checks` run on the author's own laptop.
- **Zero ticks for a second consecutive critic lap, and I am recording what that rule means today rather
  than firing it.** The routine says zero across two laps is a finding about direction. The window it
  covers built the object the line has been waiting nine days for; direction was correct. What the count
  actually exposes is that **a row can be `done` and leave its readiness line ☐ forever**, because
  WFG-007's done-when (「rehearsal aids + booth checklist」) and R7's condition (five named printables)
  do not describe the same object. That is the direction finding, it is one row wide, and it is WFG-130.

**Tick count, critic #23, 2026-09-06T0200Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for EIGHT consecutive critic laps (#16 to #23).** Checked on disk at `de7bd0a`, re-run rather than read:

- **R7 is empty on its eighth day** and it is still the whole of what this count is waiting for.
  `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot folder;
  `find docs/auto -name '*.pdf'` returns nothing. WFG-007 has never been claimed in twenty-three critic
  windows.
- **Critic #22 left a falsifiable test on this line and it did NOT run cleanly, so I am not reporting its
  verdict.** The test was: 「if the next lap ships a PDF, the stall was the queue's tail; if it ships another
  Q&A or gate row, no lap will voluntarily take a row whose output is a file rather than an argument.」 The
  window's lap shipped neither. It took **WFG-121**, which `docs/auto/DIRECTION.md` named **first** and which
  is the author's own row — the correct choice under CHARTER §14, and not a lap declining a file in favour of
  an argument. **A test of what a lap volunteers for cannot be run in a window where the lap was told what to
  take.** It runs cleanly for the first time in the next window, because WFG-007 is now first on the page
  **and** first in the table (this lap's one row move), so nothing else stands in front of it.
- **R3's sandbox half is green at `de7bd0a`:** `gates.py --mode full` exits 0 here (`1545 passed, 62 skipped`,
  302.5 s, COLD, against critic #22's cold `1535 / 62` at `f118bfe`: **+10 passed, skips unchanged**, like for
  like). `verify`, `snapshot-verify` and `env-check` PASS. `make baseline-verify` re-run rather than quoted:
  the same **2** differences, both the git-ignored `data/raw/firms_data/` manifests that exist only on the
  author's machine, so the author's NH-029 re-freeze still holds and CHARTER §3d makes this information.
  The CI half is green too: the five `auto-gates` runs in this window are all `success`, the newest at this head.
- **R9 re-earned rather than inherited:** `make finals-bundle` in this fresh sandbox exits 0 with
  `OK — release/kcf-finals-2026/ rebuilt byte-identically, 17 files`. It still waits on R7's printables.
- **R1 unchanged and still defective on the judged screen**, re-tested here on the deepened clone (WFG-119):
  `web/finals.html` prints `built at commit 41498ef` and `git merge-base --is-ancestor 41498ef HEAD` exits 1.
  The same screen still prints `n_entries":326` where `docs/NUMBERS.json` now holds **383** entries, counted
  here. WFG-115, WFG-113 and WFG-117 all close with one screen rebuild, and none has been done for fourteen
  windows.

**Tick count, critic #22, 2026-09-05T2330Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for SEVEN consecutive critic laps (#16 to #22) — and this is the first of those windows where the loop did
the right thing and the count still did not move.** Checked on disk at `f118bfe`, not read from the laps
that claimed it:

- **Why no line moved, and why that is not a criticism of the window.** The window's work is WFG-114, the
  author's own NH-027 row: the fair opponent for the headline. It ticks no readiness line by design — no
  readiness line is about the science — and it was the right row. Critic #18 blamed the queue, #19 the
  queue, #20 this page, #21 lap completion. This window rules out all four: the page named the row, the lap
  took it, it finished, it was good, and readiness is unchanged. **The remaining explanation is that R7 is
  held by an artifact type no lap volunteers for.** WFG-007 is P0, `todo`, has never been claimed by any
  lap in twenty-two critic windows, and its output is a *file* rather than an argument.
- **R3's sandbox half is green; `gates.py --mode full` exits 0 here at `f118bfe`** (`1535 passed, 62
  skipped` in 306.7 s, **COLD**, against critic #21's cold `1515 / 62` at `492364c`: **+20 passed, skips
  unchanged**, like for like). `verify`, `snapshot-verify` and `env-check` PASS. `make baseline-verify`
  re-run here rather than quoted: the same **2** differences, both the git-ignored `data/raw/firms_data/`
  manifests that exist only on the author's machine, so the author's NH-029 re-freeze still holds. R3 still
  waits on one `make all-checks` run on the author's own laptop (NH-029) and on R12/NH-014.
- **R3's CI half is clean, and it was read through the GitHub MCP because this routine's `curl` still
  returns 403 (WFG-119).** `auto-gates` runs **128 to 145** on `auto/dev` carry **no `failure`**; run 145 at
  `f118bfe` (this head) is `success`; 141 and 137 were `cancelled` by a superseding push. **No red run
  stands behind a green report in this window.** All **70** consecutive push pairs in the 24-hour window
  pass `--assert-reported` (run here, one pair at a time), and every dev, paper and critic report in the
  window carries `Reviewed by:` — the two without it are `manual`, the author's own laptop.
- ⚠ **A fourth branch exists and it is green: `auto/red/20260905T2248Z`.** The 2132Z lap built WFG-114
  concurrently, could not rebase, and parked rather than forced — correct under CHARTER §4. Its gates are
  ALL GREEN at `6938e90`. It is not a readiness defect; it is recorded on this line because the readiness
  of the *product* now depends on an author decision (**NH-032**) about which of two green measurements the
  project means, and because its escalation entries were invisible to `auto/dev` until this lap imported
  them.
- **R5 keeps its tick and takes its second defect in two laps, and the second one is the first critic's
  fix going stale.** Critic #21 put a ⚠ note on `JUDGE_QA.md` Q30 giving the student 326 / 268 / 58 and
  telling them to point at the screen's 검증 레지스트리 card. One dev lap later: WFG-114 registered **57**
  `pp_uiseong_*` keys, `docs/NUMBERS.json` at this head holds **383** entries / **325** reproducible / **58**
  not (counted here with `json.load`), and `web/finals.html` still prints **326 · 268** because the screen
  has not been rebuilt. **Three counts now answer one T0 question, and the newest wrong one was written by
  the lap fixing the problem.** The note is rewritten this lap to quote no count and point at no screen;
  WFG-117 is re-scoped and is this lap's one `fix-before-next-row` item; the screen half is WFG-113, which
  now has a live instance rather than only a mutation. The tick survives because the bank's own self-count
  (41 questions, 15 / 19 / 7) is still correct, re-counted here, and `tests/test_judge_qa_bank.py` is green
  (19 passed) after this lap's edits.
- ⚠ **A second defect recorded on R5, and it is the one a judge would actually hear.** `JUDGE_QA.md` has no
  card for 「그냥 지금 불난 데만 피하면 되지 않습니까?」 — WFG-104, open since critic #17 — and as of
  `c8a3eee` the answer 「그 실험은 안 해봤습니다」 became false. The row is now `blocked(NH-032)` on its
  margin half, because the two green measurements differ by a factor of three. A ⚠ 근거 확정 전 note is on
  the Q19 answer that carries the 91, with the sentence to say meanwhile and the three numbers not to say.
- **R7 and half of R9, SEVENTH day.** `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md`
  and one screenshot folder; `find . -iname '*.pdf'` outside `outputs/` and the venv returns nothing. R9's
  mechanism re-run here rather than quoted: `make finals-bundle` exits 0 with `OK — release/kcf-finals-2026/
  rebuilt byte-identically, 17 files`. WFG-007 is now **#1** on `docs/auto/DIRECTION.md`, by arithmetic
  rather than by a move: the row above it finished.
- **R8 is where the fair-opponent result will eventually be felt and is unchanged today.** No judge-facing
  surface carries the experiment: `JUDGE_QA.md`, `DEMO_SCRIPT_5MIN.md`, `web/finals.html`,
  `scripts/finals.template.html`, `docs/finals_screen_v2.md`, `BOOTH_SETUP.md` and `README.md` all return
  zero hits for the arm (grepped here). `paper/manuscript.md:386` is worse than zero: it still carries
  `[GAP: the arm that separates them, a present-perimeter baseline …]`, i.e. the manuscript tells a reviewer
  the experiment has not been run. Filed as **WFG-126** for the paper routine.
- ⚠ **The window grew an author push at 23:12Z, after this lap's measurements were taken.** `4d705df`
  closes NH-029, NH-030 and NH-031, adds CHARTER §5b (stale claims self-release after three hours) and
  §3d (the baseline freeze guards overwrites, not growth), and files two rows of the author's own —
  **WFG-121** (put the fair-opponent line beside the 91 on every judge-facing surface) and **WFG-122**
  (the budgeted bucket key). Every measurement on this line was taken at `f118bfe` and none of them is
  changed by that commit, which touches no artifact and no test. **What it does change is R8's near
  future:** WFG-121 is the first row in twenty-two windows whose entire output is judge-facing prose, and
  it is now the top row. ⚠ It is also the row that must not print a margin until **NH-032** is answered,
  and the author's decision was made from a ledger that did not yet carry NH-032 or NH-034 — this lap
  imported them from the parked branch. The critic's ids WFG-121/122/123 were renumbered to 124/125/126;
  the author's win.
- **Census for the window** (`492364c..f118bfe`, images and the `.docx` excluded): the window's authored
  work is one experiment — the arm script, its registrar, its 20 tests, `docs/present_perimeter_arm.md`
  and the paper lap's page-ceiling work. **Judge-facing share: 0 %**, and for once that is the correct
  answer rather than a slippage note: the row was science, the author asked for it, and its own escalation
  forbids putting its number in front of a judge until the author chooses. WFG-084's series takes this as
  its sixth data point **with that caveat attached**, because a census that scores this window low would be
  scoring the loop for obeying CHARTER §6.

*(Critic #21's count block, which stood here until 2026-09-05T2330Z, is preserved verbatim below.)*

**Tick count, critic #21, 2026-09-05T2000Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for SIX consecutive critic laps (#16 to #21) — and this window is the one where that sentence means
something different.** Checked on disk at `492364c`, not read from the laps that claimed it:

- **No line moved because the window is one line long.** `git diff 3efd0db..HEAD` is a single changed
  line: the status cell of one backlog row. The 18:17Z dev lap pushed `492364c`
  (`claim WFG-114 (20260905T1820Z)`) at 18:20Z and nothing since; at 20:10Z that is 1 h 50 m. No
  WFG-114 artifact exists under `data/processed/` and `git log --all --grep=WFG-114` finds only the
  claim and critic #20's report. **So the 「zero for two consecutive critic laps」 rule fires for a
  sixth lap, and for the first time the cause is not the queue and not the direction page.** Critic
  #20's falsifiable test is half-resolved and it resolved **for** the page: the lap took WFG-114, the
  row the page named and the author promoted. Then it produced nothing. Filed as **NH-030**; the
  release rule for the next lap is in `docs/auto/CRITIC_LATEST.md` and no claim was released here.
- **R3's sandbox half is green and its booth half is exactly where the author left it.** `gates.py
  --mode full` exits 0 in this fresh cloud sandbox at `492364c` (`1515 passed, 62 skipped` in 253.2 s,
  **COLD**, against critic #20's cold `1515 / 62` at `ce262fe`: **unchanged like for like**, which is
  what a one-line window should produce). `verify`, `snapshot-verify` and `env-check` PASS.
  `--assert-head` exits 0. **NH-029's measurement re-run rather than quoted:** `make baseline-verify`
  here reports `BASELINE MOVED — 2 difference(s) against 944243054a59`, and both are the git-ignored
  `data/raw/firms_data/` manifests that exist only on the author's machine. Critic #20's reading holds.
  R3 still waits on one `make all-checks` run on the author's own laptop.
- **R3's CI half is clean, read through the GitHub MCP because this routine's own command has stopped
  working.** `auto-gates` runs **131 to 139** on `auto/dev` carry **no `failure`**; 139 at this head is
  `success`; 137 and 131 were `cancelled` by a superseding push. ⚠ The step-2 command in this routine's
  prompt, `curl https://api.github.com/repos/Sparkxt-0318/wildfireguardian/actions/runs`, now returns
  **403** 「GitHub access is not enabled for this session」 from the sandbox proxy. Filed as **WFG-119**.
  All 44 consecutive push pairs in the 24-hour window pass `--assert-reported`, and every dev, paper and
  critic report in it carries `Reviewed by:` (the five without it are `manual`, the author's own laptop).
- **R5 keeps its tick and takes a defect on it, recorded the way WFG-067, WFG-095, WFG-100, WFG-103 and
  WFG-109 were: WFG-117, and it is this lap's one `fix-before-next-row` item.** The judge drill found it:
  `JUDGE_QA.md` Q30 is **T0**, it is the question about why today's numbers should be believed, and its
  drafted answer has the student say 「등록된 값 295개 중 261개」 with the remaining 34 split 16 + 18. I
  counted `docs/NUMBERS.json` myself: **326** entries, **268** reproducible, **58** not. The screen
  behind the student prints **326 · 재현 가능 268** in the same 검증 레지스트리 card. Nothing gates it —
  `tests/test_judge_qa_bank.py` reads no registry count — which is how they drifted 31 apart. A ⚠ 근거
  없음 note is on Q30 as of this lap so the student does not rehearse it. The tick survives because the
  bank's own self-count (41 questions, 15 / 19 / 7) is correct, re-counted here.
- **R1 is unchanged and WFG-115 survives an independent re-test with a confounder removed.** Critic #20
  proved `41498ef` is not reachable from `HEAD`. That test was run in a **depth-50 shallow clone**
  (`git rev-parse --is-shallow-repository` → `true`, `git rev-list --count HEAD` → 50), where
  `merge-base --is-ancestor` cannot answer across the boundary, and no critic lap has ever recorded that
  the sandbox is shallow. I ran `git fetch --deepen=120` (170 commits) and re-ran it: `41498ef` is
  **still** not an ancestor, and it is still on `origin/auto/lap-b1989d5-superseded` and
  `origin/ordering-boundary` only. WFG-115 stands. The shallow clone itself is **WFG-119**, with a
  predicted failure it has not yet caused: the screen's stamp `5f9a3b8` is 7 commits behind `HEAD`, the
  branch moves on the order of 40 commits a day, and once a stamp ages past 50 commits the ancestry gate
  goes RED in every sandbox while staying GREEN in CI, which checks out at `fetch-depth: 0`.
- **R7 and half of R9, sixth day, and this is now the longest-standing unticked line with a P0 row
  behind it.** `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot
  folder; `find . -iname '*.pdf'` outside `outputs/` and the venv returns nothing. WFG-007 is P0 and
  `todo` at table position 3, where critic #20 put it. R9's mechanism was re-run here rather than
  quoted: `make finals-bundle` exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically,
  17 files`.
- **Census for the window:** 1 authored insertion, 1 deletion, 1 file. There is no judge-facing share to
  report and no report share; WFG-084's series takes no sixth data point from a window with no work in it.

*(Critic #20's count block, which stood here until 2026-09-05T2000Z, is preserved verbatim below.)*

**Tick count, critic #20, 2026-09-05T1700Z: 4 of 11 (R2, R4, R5, R6). No line moved, and no line has moved
for FIVE consecutive critic laps (#16 to #20).** Checked on disk at `ce262fe`, not read from the laps that
claimed it:

- **R3 moved materially without moving the box, and the author is why.** Critic #19's NH-029 was answered:
  the author ran `make baseline-freeze` on the laptop at `38620f2`. Re-run here rather than quoted,
  `make baseline-verify` now reports **2** differences against `944243054a59`, not six, and **both** are the
  git-ignored `data/raw/firms_data/` manifests that exist only on the author's machine. The four
  in-every-clone differences are gone. ⚠ **And the re-freeze preserved every protection**, which is the thing
  CHARTER §3.2 exists for and which a sandbox re-freeze would have destroyed: diffing `38620f2^` against
  `38620f2`, both `untracked_contracts` hashes and all four `protected` artifact hashes are byte-identical,
  and `tracked_processed` went 127 to 130 (the three `pace_*.json` files). **Still ☐** on one thing only: one
  `make all-checks` run on the author's own machine, which is NH-029's remaining half.
- **R3's CI half is clean.** `auto-gates` runs 117 to 136 on `auto/dev` carry **no `failure`**; 136 at this
  head is `success`; 131 and 125 were `cancelled` by a superseding push (WFG-102). `gates.py --mode full`
  exits 0 in this fresh cloud sandbox at `ce262fe` (`1515 passed, 62 skipped` in 202.0 s, **COLD**, against
  critic #19's cold `1506 / 62`: **+9 like for like**). `verify`, `snapshot-verify` and `env-check` PASS.
  Every consecutive pair of commits in the window passes `--assert-reported`, and every dev, paper and critic
  report in the last 24 h carries `Reviewed by:` (the four without it are `manual`, the author's own laptop).
- **R7 and half of R9 are still held by one object that no lap has ever claimed: the printables.**
  `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot folder, and no PDF
  (`find . -iname '*.pdf'` outside `outputs/` and the venv returns nothing new). Critic #19 wrote the
  falsifiable test — 「if WFG-109 closes and the printables still do not exist, WFG-007's **priority** is the
  defect」 — WFG-109 is `done(20260905T1520Z)`, and **this lap raised WFG-007 from P1 to P0** and put it second
  on `docs/auto/DIRECTION.md`. That is the whole of this lap's row-move budget.
- **R1 is now further away than it was, and by a new fact rather than an old one.** Beyond WFG-110's six
  unmapped registry keys, the screen prints a second commit id, `41498ef`, which
  `git merge-base --is-ancestor 41498ef HEAD` **rejects** (WFG-115). R1 asks that every on-screen number map
  to a registry key; a provenance line that maps to a commit not on this branch is the same class of defect
  and is now named on the line.

*(Critic #19's count block, which stood here until 2026-09-05T1700Z, is preserved verbatim below. Nothing is
deleted; the newest count is the one above.)*

**Tick count, critic #19, 2026-09-05T1400Z: 4 of 11 (R2, R4, R5, R6). No line moved this window, and no line
has moved for FOUR consecutive critic laps (#16, #17, #18, #19).** The 「zero for two consecutive critic
laps」 rule fires again, and this lap's reading of it is different from the last three and is written up in
`docs/auto/DIRECTION.md`: **the loop built exactly the artifact the last three critics named, and the lines
still did not move, so the queue is no longer what holds them.** Checked on disk at `92bfc4f`, not read from
the laps that claimed it:

- **R3's booth half now has a written recipe, and R3 is further from tickable than it looked.**
  `docs/auto/finals/BOOTH_SETUP.md` EXISTS (256 lines, Korean, WFG-037, `5aecc5f`) and I read it rather than
  the report. Its citations resolve: `web/finals.html:2154` is `lang === 'ko' ? 'EN' : 'KO'` and
  `web/finals.html:2145` is the `state.view === 'live'` guard on keys 1-4, both exactly as §5.6 and §6 say.
  ⚠ **But the line's own command still does not pass, and now nobody can claim off-laptop for it.** I ran
  `make baseline-verify` myself: `BASELINE MOVED — 6 difference(s) against 89730db89921`, of which only the
  two `data/raw/firms_data/` manifests are sandbox conditions; `registry_entries: 320 -> 326` and three
  tracked `data/processed/demo_script_pace/pace_*.json` artifacts are in **every clone**, the author's
  included. Eighteen critic laps, mine included, wrote 「`baseline-verify` WARN, expected off-laptop,
  `hard: false`」 and read past four differences that are not. That is **NH-029** and it is the best thing
  this window produced.
- **R3's CI half is clean.** `auto-gates` run **130 at `92bfc4f` (this head) is `success`**; runs 130, 129,
  128, 127, 126, 124, 123, 122, 121, 120, 119, 118, 117, 113, 112 and 111 are `success`, and 125, 116 and
  115 were `cancelled` by a superseding push. **No `failure` at all in this window, and no red run stands
  behind a green report.** `gates.py --mode full` exits 0 in this fresh cloud sandbox at `92bfc4f`
  (`1506 passed, 62 skipped` in 197.4 s, **COLD**, against critic #18's `1490 / 56` warm and critic #17's
  cold `1484 / 62` at `26e200d`: **+22 passed like for like**). `verify`, `snapshot-verify` and `env-check`
  PASS. Fifteen of fifteen pushes in the window pass `--assert-reported`, and every dev, paper and manual
  report in it carries a `Reviewed by:` line.
- **R7 and R9 are held by one object and it is the same one as yesterday and the day before: the
  printables.** `docs/auto/finals/` holds `BOOTH_SETUP.md`, `DETECTION_FLOOR_CARD.md` and one screenshot
  folder, and **no printable, PDF or otherwise** (WFG-007, P1, never claimed). I re-ran `make finals-bundle`:
  exit 0, `OK — release/kcf-finals-2026/ rebuilt byte-identically, **17** files` (16 last window; the new
  file is `check_bundle_copy.py`, which travels in the bundle). I also ran the new checker on the built
  folder: `OK — release/kcf-finals-2026 matches its own MANIFEST.json.` The bundle carries the Korean fonts,
  so §7.2's 「한국어 글꼴은 꾸러미 안에 있습니다」 is true: `IBMPlexSansKR-{Regular,SemiBold}.woff2` and
  `Pretendard-arrow.subset.woff2` are three of the seventeen.
- **R1 is measured for the first time in nineteen laps, and it is six rows wide (WFG-110).** Critic #18 wrote
  「no such table exists」; that is too strong. `docs/auto/DEMO_SCRIPT_5MIN.md` §3 is a mapping table, but it
  runs script → key, and R1 asks screen → key. Using §3's own criterion for 화면 (does
  `scripts/finals.template.html` reference the key), the template references **28** registry keys, §3 names
  **22**, and **6** are in no committed table: `objective_canonical_longest_walk_saving_min`,
  `oof_average_precision`, `rescue_dispatch_count`, `responder_exposure_shortest_path_mean`,
  `responder_exposure_survival_aware_mean`, `slope_canonical_fa_routes_changed_60m`. R1's other half gained
  its first evidence this window (`BOOTH_SETUP.md` §3: headless Chromium, `file://`, network blocked, 0
  external requests on all four screens); **I did not reproduce that browser run** and do not tick on it.
- **R4 keeps its tick and gains one defect on it, recorded the way WFG-067, WFG-095, WFG-100 and WFG-103
  were: WFG-109.** `scripts/finals.template.html:1378` (KO) and `:1381` (EN) still carry the STATIC VIEW
  sentence WFG-103 withdrew, while the built `web/finals.html:1378`/`:1381` carry the correction. I diffed
  both files. Nothing is wrong on the judged screen today; the next `make finals` reverts it, and no gate
  reads the template. **This is critic #19's one `fix-before-next-row` item.** The window's one change to
  `DEMO_SCRIPT_5MIN.md` is §0's language-button line and it is correct.
- **Census for the window, measured** (`e2628f3..92bfc4f`, images, the `.docx` and the generated board
  excluded): **1,141 authored insertions, of which 272 (23.8 %) reached a judge-facing surface** — 256 of
  them `docs/auto/finals/BOOTH_SETUP.md` itself, 14 the bundle's `README_KO.md`, 2 the demo script — and
  **216 (18.9 %) are the report**. The largest remaining block, **481 lines (42.2 %), is two test files**
  (`tests/test_check_bundle_copy.py`, `tests/test_booth_setup.py`) that gate the judge-facing artifact.
  Prior windows: 6.2 %, 1.8 %, 21.8 %, 27.3 % judge-facing. **Fifth data point for WFG-084 and the highest
  judge-facing share this census has recorded**, on the first window since its cap became this routine's rule.

Previous count: **critic #18, 2026-09-05T1100Z: 4 of 11 (R2, R4, R5, R6). No line moved this window, and no line
has moved for THREE consecutive critic laps (#16, #17, #18).** That fires the 「zero for two consecutive critic
laps」 rule, and under this file's own wording it is a finding about the loop's direction and not about the
product. It is written up in `docs/auto/DIRECTION.md`, and the action taken on it is that critic #18 set **no**
`fix-before-next-row` item and moved WFG-037 above WFG-104, so the next dev lap owes the critic nothing and the
first row it meets is `BOOTH_SETUP.md`. Checked on disk at `6afd252`, not read from the laps that claimed it:

- **R1 could not move on its condition, though `web/` did change.** `web/finals.html` gained two lines this
  window (WFG-103, the STATIC VIEW caption in KO and EN) — so the sentence 「nothing touched `web/`」 is **not**
  true of this window and must not be repeated. R1 is unmoved for a different reason: its condition is a
  committed mapping table from every on-screen number to a `docs/NUMBERS.json` key, and no such table exists at
  this head (searched `docs/finals_screen_v2.md` and `docs/auto/DEMO_SCRIPT_5MIN.md`).
- **R3 (booth half), R7 and R9 are held by the same two absent artifacts as yesterday and the day before**,
  both checked on disk at this head: `docs/auto/finals/BOOTH_SETUP.md` does not exist (WFG-037) and
  `docs/auto/finals/` holds one card and one screenshot folder and no printable, PDF or otherwise (WFG-007).
  I re-ran `make finals-bundle` myself rather than reading critic #17's result: exit 0, `OK —
  release/kcf-finals-2026/ rebuilt byte-identically, 16 files`. R9's mechanism works for a third window; R9's
  contents still do not exist. **WFG-037 has never been claimed by any lap** (`git log -S` over this file's
  history finds it only in reorders), which is the whole of the direction finding above.
- **R3's CI half is clean.** `auto-gates` run **124 at `6afd252` (this head) is `success`**; 123, 122, 121,
  120, 119, 118 and 117 are `success`, 116 and 115 were `cancelled` by the next push. **No red run stands
  behind a green report in this window.** The last `failure` is run 110 (`d2418c2`, 03:20Z), already filed as
  NH-026 and WFG-102.
- **R4 keeps its tick and WFG-103 is closed on it, on both surfaces rather than the one the finding named.**
  The script's 3막 and `web/finals.html`'s STATIC VIEW caption both stopped calling the fire-blind arm 「지금 이
  순간만 보는 지도」. I re-derived the re-measure that followed: 161+246+280+346+331+328 = **1,692**;
  28+44+50+61+59+58 = **300**; per-segment 5.75 / 5.59 / 5.60 / 5.67 / 5.61 / 5.66, spread **1.03x**. Every
  cell holds. ⚠ **The new defect on this line is that the two surfaces now disagree**: the screen says only what
  is measured, the script adds 「이 도구가 없을 때의 기준선입니다」, a counterfactual the repository labels and has
  never measured. Recorded on the ticked line the way WFG-067, WFG-095, WFG-100 and WFG-103 were; it is folded
  into **WFG-104**, and it is **not** this lap's `fix-before-next-row` item because this lap sets none.
- **Census for the window, measured** (`6236c81..6afd252`, images, `.docx` and the generated board excluded):
  **1,043 authored insertions, of which 65 (6.2 %) reached a judge-facing surface and 493 (47.3 %) are
  reports** — the highest report share this census has recorded, on the window whose falsifiable test was
  about exactly that. Prior windows: 27.3 %, 21.8 %, 1.8 % judge-facing. Fourth data point for WFG-084, and
  the one that turns its cap from a proposal into this routine's rule.

Previous count: **critic #17, 2026-09-05T0800Z: 4 of 11 (R2, R4, R5, R6). No line moved this window.** R4 was
ticked inside the last 24 h (critic #15, `43710f7`, 0200Z), so the「zero for two consecutive critic laps」
direction finding does **not** fire. Checked on disk at `26e200d`, not read from the laps that claimed it:

- **R1 could not move.** Nothing has touched `web/` since `deeb147` (2026-09-04T15:59Z) and the screen's
  content is unchanged since `dc63a06` (2026-09-04T07:14Z) — the sentence critic #16 corrected this file
  to, used here as written.
- **R3 (booth half), R7 and R9 are held by the same two absent artifacts as yesterday**, both checked on
  disk at this head: `docs/auto/finals/BOOTH_SETUP.md` does not exist (WFG-037) and `docs/auto/finals/`
  still holds one card and one screenshot folder and no printable (WFG-007). I re-ran `make finals-bundle`
  myself rather than reading critic #16's result: exit 0, `OK — release/kcf-finals-2026/ rebuilt
  byte-identically, 16 files`. R9's mechanism works; R9's contents do not exist.
- **R3's CI half is clean.** `auto-gates` run **117 at `26e200d` (this head) is `success`**; 116 and 115
  were `cancelled` by the next push, 114 and 113 `success`. No red run stands behind a green report in this
  window. The last `failure` is run 110 (03:20Z), already filed as NH-026 and WFG-102 and outside it.
- **R4 keeps its tick and WFG-100 is closed on it.** The cell below records the re-budget; I re-derived
  every cell of `docs/demo_script_pace.md`'s table and they hold. **The new defect on this line is
  WFG-103** and it is not about the clock: `docs/auto/DEMO_SCRIPT_5MIN.md:108-109`, inside 3막, tells the
  judge the comparison is against 「지금 이 순간만 보는 지도」 while the arm is fire-blind
  (`src/wildfireguardian/routing/evacuation.py:270`, `docs/real_roads_real_hazard.md:50`). Recorded on the
  ticked line the way WFG-067, WFG-095 and WFG-100 were; one sentence, and it is this lap's one
  `fix-before-next-row` item. **WFG-105** carries the second half of the clock question — 5.61 syl/s is
  charged against all 300 s while §2 guarantees five interruptions inside them, and the published Korean
  *articulation* rate (pauses excluded) is 5.2–6.4 syl/s, so a *speaking* rate of 5.61 sits inside a band
  that excludes exactly what it must contain. NH-014 carries the amendment.
- **Census for the window, measured:** 1,542 authored insertions, of which **28 (1.8 %)** reached a
  judge-facing surface, against 21.8 % and 27.3 % in the two windows before. That is not a slippage note:
  the 28 lines are a correction to `DEMO_SCRIPT_5MIN.md` and the other 1,504 are the measurement apparatus
  that justified it, which is reusable and goes red on the next edit of the script. Whether that ratio is
  the right price is exactly WFG-084's open question, and this is the third data point for it.

Previous count: **critic #16, 2026-09-05T0530Z: 4 of 11 (R2, R4, R5, R6). No line moved this window, and
that is the right answer rather than a slippage note** — R4 moved last window, so the「zero for two
consecutive critic laps」direction finding does not fire. Checked on disk at `c37f27e`, not read from
the laps that claimed it:

- **R9 stays ☐, and this lap answers the question WFG-036 v1 put to the critic** rather than inheriting
  it. The v1 document asks whether R9 requires a **committed** payload. It does not: the line's own
  words are 「`make finals-bundle` rebuilds it byte-identically」, which presupposes a build, not a
  second copy in the tree. I ran it in this fresh sandbox — `OK — release/kcf-finals-2026/ rebuilt
  byte-identically, 16 files`, exit 0 — so the mechanism the line names works. R9 is ☐ for the two
  things the line also names and the bundle does not have: the printables (R7 / WFG-007) and the booth
  recipe the run steps stand in for (WFG-037). The generated payload is not what is holding it.
- **R4 holds its tick and takes a second defect on it**, recorded the way WFG-067 and WFG-095 were.
  WFG-095 is closed and I re-checked it: every **[버림]** marker now sits on a sentence that carries its
  own number, and §1's rule says so. The new defect is the budget those markers are spent against
  (**WFG-100**): measured over the spoken blockquotes only, the six segments hold 1,630 syllables
  against 300 s — 5.43 per second sustained — and the implied rate runs 4.24 (3막, 75 s) to 7.07
  (마무리, 45 s). The segment that must be spoken fastest is the limitations close, and it is last.
  The tick was for a document that exists and whose numbers verify; both still hold.
- **A correction this file owes the loop.** Critics #14 and #15 wrote 「nothing in this window touched
  `web/`, twelfth / thirteenth consecutive window」. `git log -- web/` in this fresh clone says
  otherwise: `web/finals.html` was changed at **`deeb147`, 2026-09-04T15:32Z** — one line, the commit
  stamp that closed WFG-067 — about four critic windows before #15, not thirteen. The sentence those
  laps meant is true and is the one to write from now on: the screen's **content** has not changed
  since `dc63a06`, 2026-09-04T07:14Z. Left as a correction rather than an edit of their text (§3.7).

Previous count: **critic #15, 2026-09-05T0200Z: 4 of 11 (R2, R4, R5, R6). R4 is ticked that lap and
it is the first line to move in SIX critic laps.** Checked on disk at `43710f7`, not read from the
lap that claimed it: `docs/auto/DEMO_SCRIPT_5MIN.md` EXISTS (231 lines, Korean, DRAFT-labelled),
and I verified its three testable halves myself rather than trusting `tests/test_demo_script_5min.py`
— the six segment lengths sum to exactly 300 s and every cumulative bracket is consistent with them;
the §2 table carries one interruption sentence for each of the five judge lenses the routine scores
against; and all **33 registry keys** in the §3 mapping table resolve in `docs/NUMBERS.json` with
values matching the spoken text (`0.1939`, `79.23`, `24.73`, `9.17`, `15.14`, `23.67`, `26.594`→26.6,
`3.6`, `0.138`, `0.0867`, `0.0197`, `2218`, `20`, `24`, `0`, `0.89`, `0.107` and the rest). The two
screen sentences the script tells the student to quote verbatim are in the built `web/finals.html`.
**Still MISSING at HEAD:** `docs/auto/finals/BOOTH_SETUP.md` (R3 booth half, WFG-037),
`release/kcf-finals-2026/` (R9, WFG-036), no printable under `docs/auto/finals/` (R7, WFG-007).
`web/` was not touched in this window (thirteenth consecutive window), so R1 could not move.
⚠ One defect recorded **on** the newly ticked line and not enough to withhold it, exactly as
WFG-067 was recorded on R2: the script's **[버림]** droppable markers in 2막 and 3막 sit on
caveat-only sentences whose claims stay behind (WFG-095), and deleting either is uncaught by every
claim gate in the tree. That is this lap's one `fix-before-next-row` item.

Previous count: **critic #14, 2026-09-04T2300Z: 3 of 11 (R2, R5, R6), and no line has been ticked
for FIVE consecutive critic laps.** Checked on disk at `ed35f0d`, not read from the last lap
that claimed it: `docs/auto/DEMO_SCRIPT_5MIN.md` MISSING (R4), `docs/auto/finals/BOOTH_SETUP.md`
MISSING (R3 booth half), `release/kcf-finals-2026/` MISSING (R9), `docs/auto/finals/` still
holds one card and one screenshot folder and no printable (R7). Ticked **inside** the 24 h
window: exactly one, R2 by critic #8 at `12bf2d9` (0750Z), fifteen hours ago. Nothing in this
window touched `web/` — twelfth consecutive window — so R1 could not have moved either. The
loop-direction half of that is already filed (WFG-084, NH-024) and critic #14 adds one thing
the earlier laps did not have: **NH-021 is now satisfied**, WFG-062 is `done(e350571)`, and the
next `todo` row in table order is WFG-003, which ticks R4 and half of R1. There is no longer a
gate row, an escalation or a critic item standing between the loop and this checklist. The one
`fix-before-next-row` item this lap sets (WFG-087) is fifteen minutes on the Q&A bank.

Previous count: **critic #13, 2026-09-04T2000Z: 3 of 11 (R2, R5, R6), and no line has been ticked
for four consecutive critic laps.** The last tick was R2 by critic #8 at `12bf2d9` (0750Z);
critics #9, #10, #11 and #12 each added evidence to lines already ticked or already open, and
critic #12 did not write this file at all. Checked on disk this lap: `docs/auto/DEMO_SCRIPT_5MIN.md`
MISSING (R4), `docs/auto/finals/BOOTH_SETUP.md` MISSING (R3 booth half), `release/kcf-finals-2026/`
MISSING (R9), no printables under `docs/auto/finals/` (R7, the directory holds one card and one
screenshot folder). Under the routine's own rule that is a finding about the loop's direction and
not about the product; it is the reason **NH-024** is open and the reason this critic set **no
`fix-before-next-row` item**, so the next dev lap owes the critic nothing.

| # | ready when | evidence | status |
|---|---|---|---|
| R1 | `web/finals.html` opens from `file://` with Wi-Fi off, all four acts advance, every on-screen number maps to a `docs/NUMBERS.json` key (mapping table committed) |  **2026-09-05T1700Z (critic #20), a second defect on this line and NOT a tick:** beyond WFG-110's six unmapped keys, the 검증 레지스트리 evidence card prints 「built at commit 41498ef」 (`web/finals.html:1924`) and `git merge-base --is-ancestor 41498ef HEAD` **exits non-zero** — the object is reachable only from `origin/auto/lap-b1989d5-superseded` and `origin/ordering-boundary`. `tests/test_finals_screen.py` gates the other stamp (`_payload()["git"]`, `:544`/`:550`/`:649`) and never reads this field. WFG-115. **2026-09-06T0457Z (critic #24), re-measured at `91d3e05` on a clone deepened to 250 commits so the shallow boundary is not the confounder:** `41498ef` is still **not** an ancestor of `HEAD`, and the same card now also prints `n_entries` **326** / `n_reproducible` **268** where `docs/NUMBERS.json` holds **383** / **325** — 57 entries apart, live, since WFG-114 registered the `pp_uiseong_*` keys at `c8a3eee`. Two of those three go away with `make finals` (`build_finals.py:629-630` re-derives both counts from the registry) and the third does not, because `built_at_commit` comes from the registry's own `built_at_git_commit`. WFG-113 carries the repair, WFG-115 the stamp.  **2026-09-06T1100Z (critic #26), and this cell is corrected rather than extended.** ⚠⚠ **The `41498ef` half of this line is WITHDRAWN: it IS an ancestor of `HEAD`.** On a clone deepened to **300** commits, `git merge-base --is-ancestor 41498ef HEAD` exits **0**, `git rev-list HEAD | grep -c 41498efbf0679276c140b3cbfc0819e5265e7733` answers **1**, `git rev-list --count 41498ef..HEAD` answers **277**, and `git branch -a --contains` names `auto/dev`, `origin/auto/dev` and `origin/Main`. Every earlier test on this line was taken inside a shorter graph than 277 commits (depth 50, then 170, then 250), so the answer they recorded was the instrument's, not the repository's. The sentences above claiming non-reachability are kept as a dated record (CHARTER §3.7) and are false. **`JUDGE_QA.md` Q35 is correct as written.** WFG-115 drops to P1 and is re-scoped to what survives: the line is stale by construction and mislabelled — the registry held **153** entries at that commit and the card beside it prints **383**. The counts half of this line is **fixed**: `web/finals.html` prints 383 / 325 against the registry's 383 / 325, counted here in one process, so WFG-113 is closed on the screen. **R1 now waits on WFG-110's six unmapped keys alone**, which I did not re-measure this lap and therefore do not tick on.  **2026-09-07T2020Z (critic #37) — TICKED, and all three clauses were re-derived rather than inherited.** (a) `scripts/check_finals_acts.py` records **10 requests, none off `file://`, zero console errors** (the two `ERR_FILE_NOT_FOUND` lines are the uncommitted optional booth media, which `804e5b6` made the git index decide), beside critic #36's **zero** `http(s)` references in the built file. (b) The driver advances `1막 · 발견`/1 dot → `2막 · 시간과 도로망`/2 → `3막 · 경로 비교`/3 → `4막 · 판단`/4 and writes four screenshots, exit 0, run here at `Chromium 141.0.7390.37` — **and independently on GitHub's clean `ubuntu-latest` runner**, `auto-gates` run **219** job `finals-acts` at this exact head, 19:12:10Z to 19:12:26Z, whose log prints the same four labels and the same 「10 requests, none off file://, no console error」 and uploads 5 files (2,238,234 B). That answers the 1900Z dev report's own open finding 5, which recorded the CI browser as unmeasured. (c) `scripts/finals_screen_keys.py` returns **28** keys; all 28 are in `docs/finals_screen_numbers.md` and all 28 are keys of `docs/NUMBERS.json` (383 entries), counted here in one process. ⚠ **Not covered by this tick:** the four view TABS (WFG-169), the **G** key the booth procedure uses between judges (WFG-170), and the author's own laptop (NH-014 / R12). | ☑ |
| R2 | The finals screen shows the evidence cards that exist today: operating point (WFG-019), reconciliation (WFG-018), detection floor (WFG-021), horizon grounding, refuge placement; rebuilt with `--verify` | **Detection-floor card written, screen not yet rebuilt (2026-09-03T2217Z dev lap).** WFG-047 released the stranded row and WFG-021 (a) shipped: `docs/auto/finals/DETECTION_FLOOR_CARD.md` states Session 19 with a registry key on every figure, `tests/test_detection_floor_card.py` (17) fails if any digit drifts from `docs/NUMBERS.json` or is attributed to the wrong fire, and `JUDGE_QA.md` Q10a/Q10b answer the 영덕-exclusion and false-alarm questions from it. Part (b) landed at `f5f8498`. **Still ☐:** nothing in `web/` has changed — putting this card and the other four onto the screen is WFG-017, and only that rebuild ticks R2  **Critic #6, 2026-09-04: the one finished card is now itself a finding.** `docs/auto/finals/DETECTION_FLOOR_CARD.md` opens 「위성은 사람보다 느렸습니다」 and this project's own `paper/manuscript.md` §4.7 says the measurement cannot say that; the manifest the delays are measured from calls the reference field the ignition. **F27 cleared 2026-09-04T0419Z (WFG-053).** The card's front sentence is now the size floor, the reference clock is named as the 기록된 발생일시 with the manifest's `provenance only` sentence quoted beside it, and the interim 99 % 목격신고 statistic was removed from the card after this lap's reviewer showed it is an unregistered year-to-date tally (CHARTER §3.3, §3.5b). **The card's text is correct today, verified line by line.** ⚠ But the gate written with it is a string tripwire, and the same reviewer escaped it repeatedly with reworded sentences (see that test's docstring for the verified-uncaught list). So WFG-017 may proceed on the card **as it now reads**, and whoever rebuilt the screen had to read the panel text rather than trust a green suite. **R2 TICKED by critic #8 at `12bf2d9`, 2026-09-04T0750Z.** All five cards are on the screen and critic #8 opened the committed screenshots to check: `5_card_operating.png` (운영점, pooled 0.138 with the three folds that have no true positive and their positive-cell counts), `6_card_detection.png` (탐지 바닥, 0.08~0.69 ha as a range with the flame-temperature caveat), `7_card_horizon.png` (240분 지평), `8_card_refuge.png` (대피 지점 배치, 20 → 24, and the claim narrowed to the one node actually re-verified), `9_card_reconciliation.png` (제출본과 정본, printing no retired value). `build_finals.py --verify` ran the three gates and the RELIABILITY tab prints their exit codes. `docs/finals_screen_v2.md` (219 lines) says for every card what it does NOT say, and the 탐지 바닥 card ships WFG-063's fix **before** the fix reached the three documents that still carry the old claim. ⚠ One defect on the ticked line, filed as WFG-067 and not enough to withhold the tick: the SYSTEM INTEGRITY panel prints `commit a562045`, which no longer exists after the lap's rebase. The durable claim gate is still WFG-062. **Critic #9, 2026-09-04: the tick holds and the defect is unchanged.** Nothing in this window touched `web/`; `git cat-file -t a562045` still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`, so WFG-067 is open for a second window on a ☑ line. One thing did improve on the screen's behalf without the screen moving: the 탐지 바닥 card's sentence, which the screen shipped first and alone, is now the sentence in all four markdown surfaces too, and `tests/test_detection_ordering_is_not_claimed.py` reads the built `web/finals.html` as one of its five guarded files, so the screen is no longer the only correct document and is no longer ungated (WFG-063). ⚠ That gate's measured catch rate against a mutation set its author did not write is 2 of 20 (critic #9 F47), so the tick still rests on a lap having read the panel text, not on the suite. **Critic #10, 2026-09-04: the tick holds; WFG-067 is now in its third window on this ☑ line.** Nothing in this window touched `web/`. `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`. One thing worth recording against the tick rather than for it: `web/finals.html` is listed in the new `tests/test_external_figures_carry_their_scope.py` `GUARDED` tuple, and it prints two registered external figures (3,819동, 3,587명) that the gate's own two-entry `EXTERNAL_FIGURES` registry does not contain, so listing the screen there buys it nothing today (WFG-071). Coverage on this line is still a lap having looked at the panel.  **Critic #11, 2026-09-04: the tick holds; WFG-067 is now in its FOURTH window on this ☑ line.** Nothing in this window touched `web/`. `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` and `web/finals.html` still carries `"git":"a562045"`. The line of the panel whose entire job is to let a judge verify the build has now named a commit that does not exist for four consecutive critic laps, against a fix that is one rebuild plus a one-line `git cat-file -e` gate. Coverage on this line is still a lap having looked at the panel text. | ☑ |
| R3 | `make all-checks` green on a clean clone (CI) and on the booth laptop recipe in `docs/auto/finals/BOOTH_SETUP.md` | **The F13 red is repaired at `509819d`** (the lineage annotation the critic specified). `gates.py --mode full` was RED at `633c3db` — this lap's own WFG-048 row was the first document to cite `data/processed/detection/firms_first_detection.json` and `check-artifact-manifest` fired; the manifest was rebuilt at `710d5b0` and the run there is ALL GREEN (`1188 passed, 56 skipped`), which is the head recorded in this lap's report. `--assert-head` refuses a push whose gates read a different commit, and it is what a lap should read before writing a line like this one. `baseline-verify` WARN is expected off-laptop and is a soft step. **Re-verified independently by critic #5 at `5a0466e` (2026-09-04T0147Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1229 passed, 62 skipped`, 163 s), now including the new `check-readme-figures` step, so `auto/dev` is green at HEAD for the second consecutive critic lap. **Re-verified independently by critic #4 at `12b8ac7`:** `gates.py --mode full` exits 0 in a fresh sandbox (`1185 passed, 62 skipped`, collected 1247), so `auto/dev` is green at HEAD for the first time in four critic laps and `--assert-head` is what makes that structural. **Re-verified independently by critic #8 at `12bf2d9` (2026-09-04T0753Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1273 passed, 62 skipped` in 204 s, **COLD**, against critic #7's cold `1261 / 62` at `8e0a6ad`: +12 passed, skips unchanged). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, eighth window and still not a finding. Green at HEAD for a fifth consecutive critic lap. **Re-verified independently by critic #9 at `ce31b91` (2026-09-04T0950Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1312 passed, 62 skipped` in 206 s, **COLD**, against critic #8's cold `1273 / 62` at `12bf2d9`: **+39 passed, skips unchanged**, like for like). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, ninth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **sixth** consecutive critic lap. **Re-verified independently by critic #10 at `3a70e16` (2026-09-04T1200Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1342 passed, 62 skipped` in 152 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #9's cold `1312 / 62` at `ce31b91`: **+30 passed, skips unchanged**, like for like, fourth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, tenth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **seventh** consecutive critic lap. **Re-verified independently by critic #11 at `83f49bc` (2026-09-04T1400Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1367 passed, 62 skipped` in 196 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #10's cold `1342 / 62` at `3a70e16`: **+25 passed, skips unchanged**, like for like, fifth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, eleventh window and still not a finding. Green at HEAD for an **eighth** consecutive critic lap. ⚠ And this is the window that shows what the sentence is worth: the suite was green, and one of its passing tests (`tests/test_juso_yeongdeok.py:11`) was asserting that 영덕's 시군구 code is 47920 over an artifact lying 45 km outside 영덕 (critic #11 F54, WFG-075/076, NH-022). Gate green means no gate disagreed, not that the tree is right. **Re-verified independently by critic #13 at `baf6962` (2026-09-04T2000Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1377 passed, 62 skipped` in 178 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #12's cold `1376 / 62` at `c65dc56`: **+1 passed, skips unchanged**, like for like, seventh comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, thirteenth window and still not a finding. Green at HEAD for a **tenth** consecutive critic lap. ⚠ And this is the window that shows what the CI half of this line is worth, which the sandbox half cannot: `auto-gates` was **RED on `auto/dev` for six consecutive pushes** (runs 86–91, `201c554` through `e4a7304`) while every lap that pushed them read ALL GREEN in its own sandbox. One test, `tests/test_finals_screen.py::test_the_stamp_gate_is_graded_against_the_ways_a_stamp_goes_wrong`, built a probe commit with `git commit-tree` and inherited a committer identity the runner does not have. Fixed at `21b8740`; runs 92, 93 and 95 are `success` and run 95 is this head. The residue worth recording against this line rather than for it: the first red was 16:03Z and the fix 18:39Z, **2 h 36 min against CHARTER §4b's 「catch it within the hour」**, and the hourly ci-red routine's own run on it produced a report and no fix because a concurrent lap had landed the same repair first. **Re-verified independently by critic #14 at `ed35f0d` (2026-09-04T2300Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1453 passed, 62 skipped` in 208.9 s, **COLD** — first full run in this sandbox, so the six SRTM-gated tests skipped, WFG-039 — against critic #13's cold `1377 / 62` at `baf6962`: **+76 passed, skips unchanged**, like for like, eighth comparable window and the largest single-window gain this line has recorded, all of it WFG-062's `tests/test_withdrawn_claims_registry.py`). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fourteenth window and still not a finding. `--assert-head` exits 0 at HEAD. Green at HEAD for an **eleventh** consecutive critic lap. The CI half also recovered: `auto-gates` runs 92, 93, 95, 96, 97, 98 and **99 (this head) are `success`** (94 cancelled by a superseding push), so the six-red episode of runs 86–91 is closed for a second consecutive window and no red run sits behind a green report here. **Re-verified independently by critic #15 at `43710f7` (2026-09-05T0206Z):** `gates.py --mode full` exits 0 in a fresh cloud sandbox (`1464 passed, 62 skipped` in 317.3 s, **COLD** — first full run here, so the six SRTM-gated tests skip, WFG-039 — against critic #14's cold `1453 / 62` at `ed35f0d`: **+11 passed, skips unchanged**, like for like, ninth comparable window). `verify`, `snapshot-verify` and `env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fifteenth window and still not a finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for a **twelfth** consecutive critic lap. ⚠ The CI half went red twice inside this window and the reason is new: `auto-gates` runs **103 (`a2a2994`) and 104 (`c8124a8`) are `failure`**, and in both the **`gates` job passed and the new `promote` job failed** — the fast-forward of `Main` that CHARTER §4c introduced at `a2a2994` cannot run while `Main` is a protected branch requiring a pull-request review, which is an author action nobody had filed (now **NH-025**). Fixed at `b3244f8` by making a refused fast-forward a warning rather than a red run, 20 minutes after the first red, well inside CHARTER §4b's hour. Runs 105, 106 and **107 (this head) are `success`**. Recorded here because it changes what a red `auto-gates` run means on this line: from 09-05 a red run can be a promotion refusal with green gates behind it, and a lap must read the **job**, not the run. **2026-09-05T1217Z (WFG-037), a note and NOT a tick — the dev lap does not tick, the critic does (CHARTER §10).** `docs/auto/finals/BOOTH_SETUP.md` now exists, so the sentence above it is history. ⚠ And writing it falsified this line's own command: **`make all-checks` does not pass, and not only off-laptop.** It aborts at `baseline-verify` with six differences against the freeze at `89730db89921`, of which only two are the missing `data/raw/firms_data/` manifests; the other four — the registry entry count and three tracked `pace_*.json` artifacts — are in every clone and will abort the same command on the author's laptop. `gates.py` treats the step as soft (`hard: false`), which is why eighteen windows of 「WARN, expected off-laptop」 read past it. The re-freeze needs the raw bundle and is the author's (**NH-029**); the recipe's §1.1 sends the booth morning to `gates.py --mode full` instead. **So the CI half of this line is unchanged and green; the booth half now has a written recipe whose every command was executed and whose own readiness command is the one that fails.** The rehearsal half is R12 / NH-014 | ☐ |
| R4 | A 5-minute demo script in Korean with per-act timings and the sentence for each judge type's interruption (`docs/auto/DEMO_SCRIPT_5MIN.md`) | **The file exists as of the 20260905T0025Z dev lap (WFG-003).** Korean, DRAFT-labelled per CHARTER §9, six timed segments summing to exactly 300 s over `docs/FINALS_DEMO.md`'s four acts plus an opening and a limits close, one interruption sentence for each of the five judge lenses, and a §3 mapping table of 35 rows (23 화면 / 12 구두) each carrying a registry key or a named artifact, where 화면 means a card in scripts/finals.template.html actually renders it (not merely that the key sits in the built page). `tests/test_demo_script_5min.py` (9) reads that table mechanically and was graded 6 of 6 against mutations written to break it. **The dev lap does not tick this line — the critic does (CHARTER §10)**, and the half a test cannot reach is whether five minutes of Korean fits in five minutes: the segment times are design values, not a rehearsal, and §5 of the document says so. R12/NH-014 is where a human reads it aloud. **R4 TICKED by critic #15 at `43710f7`, 2026-09-05T0200Z**, on the independent check recorded in the header above: 300 s exactly, five lenses, 33 registry keys resolved and value-matched by hand, two quoted screen sentences found in the built page. The half a test cannot reach is unchanged and the tick does not claim it — five minutes of spoken Korean fitting in five minutes is R12/NH-014, and §5 of the document says so in the document. ⚠ Defect carried on the ticked line: WFG-095, the **[버림]** markers on caveat-only sentences in 2막 and 3막 — **closed at `9345848`**. **2026-09-05T0625Z (WFG-100), correcting this cell rather than the tick (CHARTER §10 — the dev lap does not tick):** the sentence above saying 「the segment times are design values」 is no longer true. They are now a *measurement* — 1,684 spoken syllables allocated over 300 s at one rate of 5.61 syl/s, giving 29 / 44 / 50 / 60 / 59 / 58 s where the design values were 25 / 45 / 55 / 75 / 55 / 45 and implied six different rates spanning 1.62× (`docs/demo_script_pace.md`, `data/processed/demo_script_pace/pace_20260905T0625Z.json`, `tests/test_demo_script_pace.py`). **The half a test cannot reach is unchanged and this note does not claim it:** whether that rate is sayable is still R12 / NH-014, a human with a stopwatch. The critic owns whether the tick survives the re-budget. | ☑ |
| R5 | Judge Q&A bank v2 complete: every T0 answer cites a file; no purged phrasing remains (`tests/test_judge_qa_bank.py` green) | Invariants met: `docs/auto/JUDGE_QA.md` 33 questions, tiers 14/13/6, 18 tests green in `gates.py --mode full` at `1113388`, WFG-002 `done(20260903T1536Z)`. **Tickable at `1c1561e` (2026-09-03T2017Z dev lap):** the §0 bullet that told the student the repository was wrong about "6 → 34" (the 폐기된 452계열 bracket; canonical is 6 → 66) is rewritten onto `docs/ssot_audit_2026-09-03.md` §1 and now tells the student explicitly NOT to say 오타 at the booth. CRITIC F1 `done(1c1561e)`. `tests/test_judge_qa_bank.py` 18 passed, `check_forbidden` and `tests/test_rescue_lineage_ssot.py` green on the rewritten text | ☑ |
| R6 | 제출본 대비 정본 reconciliation sheet exists, in Korean, one page, and JUDGE_QA links to it | `docs/submission_reconciliation.md` (Korean, 11 rows, spoken lines); `JUDGE_QA.md:34` links to it; WFG-018 `done(20260903T0653Z)`; row 8 corrected by WFG-004 at `6a2c8a3` | ☑ |
| R7 | Printables as PDF under `docs/auto/finals/`: evidence sheet (A4), reconciliation sheet, related-work and SFTD059T differentiation panel, booth checklist, village dispatch sheets sample |  **2026-09-05T1700Z (critic #20):** still nothing. `docs/auto/finals/` holds two `.md` files and one screenshot folder and no PDF, on the sixth day this line has been held by a row no lap has claimed. Critic #19's falsifiable test resolved (WFG-109 closed, printables absent), so **WFG-007 is raised P1 -> P0** and is second on `docs/auto/DIRECTION.md`. The printing and the poster stay the student's; the files and the build script are the agent's and are what P0 buys. **2026-09-06T0457Z (critic #24): day nine, and for the first time the row is claimed.** `find docs/auto -name '*.pdf'` still returns nothing at `91d3e05`, but `7233743` set WFG-007 `in-progress(20260906T0320Z)` three minutes after the 03:17Z lap woke, with the row first in the table and first on `DIRECTION.md` — which is critic #23's falsifiable test actually running. The claim was still in flight when this lap ran its gates, so the verdict belongs to critic #25, not to me. ⚠ If that lap died, **NH-035** is why the row is not releasable at 06:17Z. ⚠⚠ **DEV LAP 2026-09-07T0018Z (WFG-134 + WFG-140 + WFG-130): both of this line's reasons are now addressed and the dev lap does NOT tick it — the critic does (CHARTER §10).** **(1) Contents.** `WFG_printables_20260907T0059Z.pdf` is **33 A4 pages** (체크리스트 5, 대본 6, 질의응답 17, 대조표 3, 탐지 카드 2, summing to 33 — the decomposition first written here was the build's own off-by-one, caught by this lap's independent reviewer and fixed at the source with `test_the_per_source_page_counts_sum_to_the_page_count`) from **five** sources; `docs/submission_reconciliation.md` is now one of them. Of R7's five items, three are in the kit and two are not: 「A4 근거 시트」 and 「대조표」 are **one document** (WFG-018 `done(20260903T0653Z)`, whose own fourth line says 「인쇄본은 양면 한 장입니다」, and which `JUDGE_QA.md` Q30's drill table names), the 부스 체크리스트 is the third; the related-work · SFTD059T panel is **WFG-026** and is not written, and the dispatch sheets are excluded. ⚠⚠ **CORRECTED 2026-09-07T0320Z (WFG-151): the reason written here was false and it propagated.** This clause read 「the 29 dispatch sheets are already committed PDFs that print directly」; `outputs/dispatch/20260801T163042Z/` holds **33** clusters and `git ls-files outputs/dispatch` counts 33 `dispatch_a4.html` and exactly **3** `dispatch_a4.pdf`, because `outputs/dispatch/README.md` commits only the three largest clusters' PDFs (33 would be 6.7 MB of regenerable output; `python scripts/generate_dispatch_outputs.py` rebuilds them). The exclusion still stands — the sheets are **regenerable from a committed artifact**, which is a good reason — but WFG-151 copied the false version of it into the judge-facing `release/kcf-finals-2026/README_KO.md`, where a student reading it on a clean clone would have gone looking for 29 finished PDFs and found 3. Corrected in `R7_ITEMS` and in the bundle. **R7's own wording 「29 dispatch sheets sample」 still says 29 and nothing in the tree does; that reword is the critic's, and the printables manifest's `what_this_does_not_show` repeats it and needs a new stamp (CHARTER §3.2) — both are WFG-153.** Both exclusions are written into `tests/test_printables.py` `R7_ITEMS` with their reasons, and `test_every_r7_printable_that_exists_is_actually_printed` fails when an R7 item that exists in the tree is not printed — graded red by removing the reconciliation sheet from `SOURCES`. A second test binds `R7_ITEMS` to this line's own wording, so a reword here does not silently outlive the mapping. **(2) Freshness.** The four-window `JUDGE_QA.md` drift is closed by a rebuild at a new stamp, and the gate that detects the next one exists: `test_the_newest_printable_is_not_stale_against_the_tree` re-hashes the newest manifest's sources against the working tree. ⚠ It was **red on the pre-rebuild tree** (`2c8451211e…` recorded against `5ac45ea810…` in the tree) before the rebuild made it green, which is what says it is not green by construction. The earlier stamp is kept beside it as the record of what it was built from. **What is left for the critic to verify, and for the author:** the student still has to print it once and tick the checklist offline (WFG-007's human half). ⚠⚠ **2026-09-07T0500Z, critic #32, still ☐ and now for ONE reason plus one correction owed.** The one reason is **WFG-026**, the related-work and SFTD059T differentiation panel, unwritten, this line's sole remaining blocker and position 1 on `docs/auto/DIRECTION.md`. The correction owed is this line's **own wording**: 「29 dispatch sheets sample」 is not a count of anything in this repository — `outputs/dispatch/20260801T163042Z/` holds **33** cluster directories and `git ls-files outputs/dispatch` counts 33 `dispatch_a4.html`, 33 `sms_drafts.json`, 33 `broadcast_script.txt` and **3** `dispatch_a4.pdf`, all four re-counted here at `0fc6130`. 「29」 traces to an aspiration in `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md` and to no artifact (CHARTER §3.3). The dev lap of 0355Z corrected the derived claim in three places and could not reach this line's definition cell or the printables manifest, both of which are frozen against it (§3.2 for the manifest, a bound definition for this cell). That is **WFG-153**, raised to **P0** by this lap, and its (a) half is the one `fix-before-next-row` item. ⚠⚠ **DEV LAP 2026-09-07T0630Z (WFG-026 + WFG-153(a) + WFG-156): this line's sole remaining blocker is written, and the dev lap does NOT tick the line — the critic does (CHARTER §10).** **(1) The panel exists.** `docs/related_work.md` is the survey (16 entries, every one resolved to a DOI or a permanent URL, with what each computes and what it does not) and `docs/auto/finals/RELATED_WORK_PANEL.md` is the Korean booth wording, which is now `SOURCES` entry six of `scripts/build_printables.py` and prints in the kit rebuilt at this lap's stamp. It carries the two Korean operational systems (`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`), which is most of WFG-144's content, and it states the one thing that must never be claimed: **no accuracy comparison with NIFoS or G-DAPS in either direction**, because no published validation of either was located and the figures in circulation are agency plan statements. It also concedes, in the panel's own voice, that their 5 m terrain analysis is finer than this project's grid. So four of R7's five printables are in the kit and one is excluded. **(2) The correction this line owed is paid.** This cell's own definition said 「29 dispatch sheets sample」 and nothing in the tree counts 29 — `outputs/dispatch/20260801T163042Z/` holds **33** cluster directories and `git ls-files outputs/dispatch` counts 33 `dispatch_a4.html`, 33 `sms_drafts.json`, 33 `broadcast_script.txt` and **3** `dispatch_a4.pdf`. The definition now reads 「village dispatch sheets sample」, the unregistered number is gone, and the item is unchanged. The false half of the exclusion reason — 「already committed PDFs that print directly」, untrue of 30 of the 33 — is out of the printables manifest at this new stamp and out of `docs/auto/JUDGE_QA.md` Q39, and is **registered as `WC-006`** in `docs/auto/withdrawn_claims.json`, which is what CHARTER §3.5c requires and what the 0355Z lap did not do. **(3) The binding that would have let the reword slip is fixed first.** `test_r7_still_enumerates_the_five_printables_this_list_resolves` searched the whole 111 KB of this file, where all five names already occur outside R7's row, so it was vacuous (critic #32, WFG-156); it now reads **this row's definition cell only**, exactly as its twin `tests/test_finals_bundle.py::test_r9_still_enumerates_the_contents_this_list_resolves` already did. It was graded red before the reword by renaming one item in `R7_ITEMS`. **What is left for the critic to verify, and for the author:** whether four-of-five with a stated exclusion satisfies this line, and the student still has to print the kit once and tick the checklist offline (WFG-007's human half, NH-014). ⚠⚠ **2026-09-07T0800Z, critic #33: TICKED, and the call the dev lap left here is answered on the row rather than deferred again.** Every condition re-measured in this sandbox at `2896c9c`, not read from the lap that built it. The kit is `20260907T0705Z`: all **six** `SOURCES` re-hashed against the tree in one process and all six **match** (`BOOTH_SETUP.md` `99b2168f4b…`, `DEMO_SCRIPT_5MIN.md` `b1aae78f35…`, `JUDGE_QA.md` `2e9d7940b0…`, `submission_reconciliation.md` `237de4f4ae…`, `DETECTION_FLOOR_CARD.md` `84648d4d6e…`, `RELATED_WORK_PANEL.md` `d3b405112e…`); the PDF's own sha256 matches its manifest (`d54aa6dd7802…`); `pages_per_source` sums 5+6+17+3+2+3 = **36** = `pages`, and the PDF really carries **36** `/Type /Page` objects. The stamp is in `release/kcf-finals-2026/MANIFEST.json` (19 files) so it reaches the stick. **On four-of-five with a stated exclusion: it satisfies this line, and here is the ground, so the next lap does not re-derive it.** R7's fifth name is the village dispatch sheets *sample*. A sample exists as committed, printable A4 PDF: `outputs/dispatch/20260801T163042Z/` carries `dispatch_a4.pdf` for the three largest clusters (209,717 / 216,444 / 203,281 bytes, all three opened here). The kit excludes them for a reason that is now true and specific rather than the false one WC-006 retired: 33 clusters, 6.7 MB of Korean-font-subset output, regenerable by `scripts/generate_dispatch_outputs.py`. Requiring them *inside* the kit PDF would commit regenerable output into a stamped artifact that CHARTER §3.2 then freezes forever, which is the trap this very lap paid for with two kit stamps in one lap. **The alternative reading, named so the tick is falsifiable:** if R7's clause 「under `docs/auto/finals/`」 binds all five items and not just the kit's location, R7 does not tick and the fix is one sample sheet added to the kit. I take the first reading because the second makes R7 ask the repository to freeze output it regenerates. **The printing itself is not R7's condition** and never was: R7 asks that the printables exist as PDF, and 「the student prints the kit once and ticks the checklist offline」 is R12 and NH-014, which stay ☐ and are the author's. | ☑ |
| R8 | `README.md` has a Round-4 section and the English abstract draft; forbidden-string and collision gates green | **Sourcing half now durable, 2026-09-04 (critic #5).** Every figure the opening paragraph prints was re-opened at its primary page this lap and every one holds (경상북도 보도자료: 99,289 ha / 149시간 / 3,819동 / 2,246세대 3,587명 / 1조 505억, and the 「1986년 이래 역대 최대 피해 면적」 superlative carried by that release itself; 산림청 2025-05-16 for 347건 / 104,788 ha over 봄철 산불조심기간 1.24~5.15). `data/processed/external/fire_2025_scale.json` + 16 `fire2025_*` registry keys + `check-readme-figures` + 44 new tests mean the figures can no longer be rewritten silently. **(b) is CLOSED at `e5aaaa7`/`28b4c38`, verified by critic #6 at `b855943`:** the 「약 43 %」 / 「about 43 %」 sentence is gone from both languages, `README.md` prints no share at all, and the tripwire now scans both whole paragraphs instead of the one line that carried `104,788`. **Still not tickable on (a) alone:** no Round-4 section and no abstract draft yet (WFG-010). Previously: **Still not tickable, for two reasons:** (a) no Round-4 section and no abstract draft yet (WFG-010), and (b) the scope note's 「about 43 %」 sentence at `README.md:210-211` / `:528` is false and contradicts this repository's own `fire2025_chain_share_of_nationwide_pct = 94.8` (critic #5 F21). Previously: **Half recovered, 2026-09-04.** The falsifiable-in-one-search half is fixed by two laps: the 0037Z manual lap rewrote both opening paragraphs onto 99,289 ha, and the 0017Z dev lap sourced every figure to a URL it opened, corrected the nationwide comparison's **period** (봄철 산불조심기간 2025-01-24~05-15, not March) against the 산림청 release, withdrew the 95 % share claim as basis-mixing, and added `tests/test_motivating_event_figures.py` — the gate these figures never had. **Still not tickable:** no Round-4 section and no abstract draft yet (WFG-010), which is the other half of this line. Original finding: **Moved backwards this window.** No Round-4 section and no abstract draft yet, and `12b8ac7` rewrote the existing opening paragraph in both languages to figures that are wrong: 45,157 ha for a chain that burned 99,289 ha, and 영덕 8명 against this repository's own correction to 10 (critic #4 F16/F17, WFG-043). The gates are green because none of these figures has a registry key, which is the point of WFG-049. This line cannot be ticked while the paragraph above the Round-4 section is falsifiable in one search. ⚠⚠ **DEV LAP 2026-09-08T1240Z (WFG-010): BOTH of this line's named conditions now exist, and the dev lap does NOT tick the line — the critic does (CHARTER §10).** **(a) The Round-4 section.** `grep -nE '^## Round' README.md` now returns `:59` Round 2, `:75` Round 3 and `:200` **Round 4 (2026-09 — 본선 준비)**, where it returned nothing for Round 4 every day this week. It is **below** Round 3 and the Round-2 record is untouched (CHARTER §3.12), and that ordering is now asserted rather than trusted. The section leads with what the round did NOT do (no new model, no retrain, no new region) and its own reading note says that **three of its four items cut against the project**: the fair opponent that recovers most of what the fire-blind contrast credited to the forecast (§1), the registry whose two measured limits it prints beside itself (§2), and the two negative results (§3). Only §4 is favourable, and it is a list of things a judge can open. ⚠ The fair-opponent **margin values are deliberately absent** from it, with the absence stated in the section's own voice, because NH-032 and NH-034 are open (DIRECTION's standing bar). **(b) The English abstract draft.** `README.md` §`Abstract (draft)` carries it, labelled a draft in its own opening lines and pointing at `paper/AUTHORSHIP.md` for who rewrites it, which is CHARTER §9's requirement that the label sit where the draft is read. It tracks `paper/manuscript.md`'s abstract and states the weak operating point in the same breath as the AUC. **(c) The third condition, and the reason this line stopped being graded by hand.** `forbidden-string and collision gates green`: `make verify` PASSED on the edited README, and `gates.py --mode full` exits 0 at the pushed head. Until this lap **nothing in `tests/` read this line at all** — R8 was graded four windows running by a critic typing `grep -nE '^## Round' README.md` into a report, which is the hand-typed-fact failure class DIRECTION names. `tests/test_readme_round4.py` (7 tests) now binds all three conditions plus CHARTER §3.12's ordering, §9's draft label, and DIRECTION's rule that a surface stating 42 carries **both** binding caveats. ⚠ **Graded red nine ways, and the grading found a real hole rather than confirming the design:** asserting the token `fire-blind` appeared in the abstract stayed GREEN when the caveat was deleted from the 42's own sentence, because a *different* claim four lines later also says `fire-blind` — critic #41's WFG-185 defect reproducing inside a test written after it. The assertions now match the binding clause inside the paragraph that states the number. ⚠⚠ **CORRECTED BY THIS LAP'S INDEPENDENT REVIEWER, BEFORE THE PUSH, AND THE CORRECTION IS THE MOST USEFUL LINE IN THIS CELL.** The sentence that stood here said the gate's one uncatchable mutation was 「a fresh uncaveated 「42곳」 sentence in the Korean half」 — **and the same commit had shipped exactly that**, at `README.md:227`, in the Round-4 section this lap added. The reviewer blocked the push, showed it in one command (none of the six registered spellings for the upper-bound caveat appeared anywhere in the section), and showed why nothing caught it: `tests/test_future_aware_attribution.py`'s claim regex requires the denominator (`458 … 42`), so a sentence that drops it is never classified as a claim block at all. It also named the deeper defect — the first version of the new gate asserted a hand-listed count of 「known sites」 written **after** looking at them, so the offending line was whitelisted and the artifact passed by construction, which is measurement leakage and not a guard. **Naming a mutation you cannot catch is not a substitute for not shipping it.** Both are fixed in the pushed commit: the Korean bullet now carries both caveats in its own block (fire-blind opponent; 42 as the 「상한」 a noiseless forecast would buy, with the sentence that this repository has never measured how much less the real model buys), and the gate is keyed on the **bare** number in **either** language across every block, with exactly one site exempted **by name and with a reason** (the Round-3 correction table, a §3.7 record) and a second test asserting that exemption still matches exactly one block. Re-graded: the reviewer's own nail and five further mutations all go red. **The mutation that remains, stated plainly:** this file reads `README.md` only, so the same uncaveated sentence on `web/finals.html`, `docs/auto/JUDGE_QA.md` or the printed panel still passes. **WFG-168** is the bilingual lint that closes it. **What is left for the critic:** whether a Round-4 section that reports three unfavourable items and one favourable one is what this line asked for, and whether the deliberate absence of the margin values is acceptable while NH-032 and NH-034 are open  **2026-09-08T1429Z (critic #43): TICKED.** All three halves measured at `dee1bc1`, unpiped. `grep -nE '^## Round' README.md` answers `:59`, `:75` and **`:200`** 「Round 4 (2026-09 — 본선 준비)」; `grep -n '^### Abstract' README.md` answers **`:596`** 「Abstract (draft)」 with the draft label on the file; `make check-forbidden` exits **0** and `make verify` PASS inside `gates.py --mode full` exit 0. The row is WFG-010, done at `692497a` with the reviewer's fixes at `ea04478`, bound by `tests/test_readme_round4.py`. ⚠ The tick is on the condition, not on the prose: **WFG-190** is open against `README.md:235-239` and `README.md:220-225` inside this same section and is scored on 제출 자료, not here. | ☑ |
| R9 | The release bundle `release/kcf-finals-2026/` (WFG-036) exists: `web/` whole, printables, `README_KO.md` with the 10-line run recipe, `CITATION.cff`, and `make finals-bundle` rebuilds it byte-identically | **v1 landed 2026-09-05 (WFG-036, dev lap 20260905T0355Z), and the dev lap does not tick this line — the critic does (CHARTER §10).** `release/kcf-finals-2026/` holds the four screens (`finals`, `console`, `field_view`, `refuge_placement`), the fonts and poster, `LICENSE`, `CITATION.cff`, a ten-step Korean `README_KO.md` and `MANIFEST.json`. `make finals-bundle` re-assembles the folder, re-derives every SHA-256 and exits non-zero naming any file the committed manifest does not describe; `tests/test_finals_bundle.py` (7) hashes the sources independently of the builder. ⚠ **Two things this v1 does not have, and they are why it is not tickable yet:** the printables the line names (R7 / WFG-007 — none exist), and the booth recipe the run steps stand in for (WFG-037). ⚠ The payload (`web/`, `CITATION.cff`, `LICENSE` inside the bundle) is **generated and git-ignored**, so a clean clone holds only `README_KO.md` and `MANIFEST.json` until the command is run once; the reasoning is in `docs/finals_bundle.md` and a critic who reads R9 as requiring a committed payload should say so rather than inherit the choice. **Answered by critic #16, 2026-09-05: R9 does NOT require a committed payload.** The line's own condition is that `make finals-bundle` rebuilds it byte-identically, which presupposes a build; I ran it in a fresh cloud sandbox and it exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically, 16 files`. The choice is accepted and is not what holds the line. **Still ☐ for exactly two things the line also names:** the printables (R7 / WFG-007) and the booth recipe (WFG-037), which is why WFG-037 was moved directly under WFG-036 in the table this lap. **2026-09-05T1217Z (WFG-037), a note and NOT a tick:** the booth recipe half is now written, and the bundle gained a seventeenth file — `check_bundle_copy.py`, which verifies a COPY of the folder against the manifest that travels with it, reads and never writes, and imports nothing outside the standard library so a borrowed machine with no repository can run it. It exists because this line's mechanism was found to answer a different question than the booth asks: `make finals-bundle` overwrites the bundle from the tree before hashing, so a file corrupted **on the stick** is repaired rather than reported (measured by appending seven bytes to the bundle's `finals.html`: the run printed `OK`), and the builder never enumerates the folder, so a file an earlier run left behind ships on the stick while the run reports byte-identity (**WFG-108**). The line still waits on the printables (R7 / WFG-007) ⚠⚠ **DEV LAP 2026-09-07T0320Z (WFG-151): the printables are in the bundle, and the dev lap does NOT tick this line — the critic does (CHARTER §10).** `make finals-bundle` exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically, **19 files**`, the two new ones being `printables/WFG_printables_20260907T0059Z.pdf` (33 A4 pages, sha256 `a4970b12cdd1…`) and `printables/manifest_20260907T0059Z.json`, which carries the SHA-256 of each of the five documents the PDF was built from. Both are **copied**, not authored: `release/kcf-finals-2026/printables/` is git-ignored like the rest of the payload, so this adds no committed bytes and does not put a second copy of a 433 KB PDF beside the first (CHARTER §3.2). **The stamp is resolved, not typed.** `build_finals_bundle.py:newest_printables()` takes the lexicographic maximum of the TRACKED `WFG_printables_*.pdf` stamps and then requires the manifest at that same stamp, so the next `make printables` moves the plan, the committed manifest stops matching, and `make finals-bundle` fails until the lap that built the kit rebuilds the bundle. That is WFG-152's rule enforced by the mechanism instead of by a sentence, and it is why a `PAYLOAD` literal was the wrong fix. **And the reason nothing went red for a day is fixed at the shape and not at the omission**, which is critic #31's falsifiable test (1): `tests/test_finals_bundle.py` gains `R9_ITEMS`, this line's own five names read into predicates over the **committed manifest** rather than over `bfb.plan()`, plus `test_r9_still_enumerates_the_contents_this_list_resolves`, which binds the mapping to this row so a reword cannot silently outlive it, and `test_the_bundle_carries_the_newest_booth_kit_and_not_an_older_stamp`, which re-derives the newest stamp from the tree and also fails if a superseded kit rides along. ⚠ **Graded red before the fix**, against the committed 17-file manifest at `3f881f6`: `test_the_bundle_carries_every_content_r9_names` failed naming exactly `printables`, and the newest-kit test failed with `the newest booth kit in the tree is 20260907T0059Z and the bundle does not carry it; the bundle's printables are []`. ⚠ **Two sentences were updated and NEITHER is a withdrawal, which is the distinction this lap had to get right.** The bundle's `README_KO.md` said 「A4 근거 시트와 부스 체크리스트는 아직 이 꾸러미에 없습니다」 and `docs/finals_bundle.md` said 「v1 has no printables」; both stayed **true** the whole time, because each was about the bundle and the bundle really did not contain the kit. So there is nothing to register in `docs/auto/withdrawn_claims.json` (CHARTER §3.5c) — the defect was in `PAYLOAD` and in a test that never read R9, not in the prose. Both are updated with the superseded sentence kept as a dated 〔기록〕 block (§3.7), and both say plainly which of the two was wrong. **What is left, and it is not this row's:** two of R7's five are still not on the stick — the related-work · SFTD059T panel is **WFG-026**, not written, and the dispatch-sheet sample. ⚠⚠ **The reason for that second exclusion was FALSE and this lap shipped it for one commit before its own reviewer caught it — recorded rather than quietly fixed, because it is the more interesting half of this row.** I wrote 「the 29 dispatch sheets are already committed PDFs that print directly」 into three places including the judge-facing `README_KO.md`, having read it from R7's line and from `tests/test_printables.py` `R7_ITEMS` and never from the tree. The tree: `outputs/dispatch/20260801T163042Z/` holds **33** clusters; `git ls-files outputs/dispatch` counts 33 `dispatch_a4.html`, 33 `sms_drafts.json`, 33 `broadcast_script.txt` and exactly **3** `dispatch_a4.pdf`, because `outputs/dispatch/README.md` says only the three largest clusters' PDFs are committed (33 would be 6.7 MB of regenerable output; `python scripts/generate_dispatch_outputs.py` rebuilds them). Neither 「29」 nor 「committed」 traced to a registered artifact — CHARTER §3.3 — and 「29」 originates in an aspiration in `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`, not in a count of anything. On a clean clone the student would have found **3**, in the bundle that goes on the USB stick. Corrected in `README_KO.md`, `docs/finals_bundle.md` and here; the upstream copies in R7's own line and in the printables manifest's `what_this_does_not_show` are behind CHARTER §3.2 (they need a new stamp) and are filed as **WFG-153**. **The shape lesson is that the row's own gate did not cover this:** `R9_ITEMS` had an exclusion slot with no assertion behind it, so an excused item shipped on an unchecked sentence. `tests/test_finals_bundle.py` now carries `EXCLUSION_EVIDENCE`, which asserts an excluded item's named path is really in the tree, and `test_the_dispatch_exclusion_reason_matches_what_is_committed`, which re-derives the 3-of-33 count from `git ls-files` so the Korean sentence in the bundle cannot drift from it. Both graded red. Whether the remaining two exclusions are compatible with R9's word 「printables」 is the critic's call, not the dev lap's. ⚠⚠ **TICKED 2026-09-07T0500Z BY CRITIC #32, AND THE CALL THE DEV LAP LEFT ME IS ANSWERED HERE SO A LATER CRITIC CAN OVERTURN IT KNOWINGLY.** Every one of this line's five named conditions was **re-run in this sandbox at `0fc6130`**, not read off the lap that built them: `make finals-bundle` exits 0 with `OK — release/kcf-finals-2026/ rebuilt byte-identically, 19 files`; the folder on disk holds those 19 plus `MANIFEST.json` itself and nothing else; `python scripts/check_bundle_copy.py release/kcf-finals-2026` exits 0 with `OK — matches its own MANIFEST.json`; `git status --short` is empty afterwards, so the payload really is ignored and no committed byte moved; the manifest's `files` array holds exactly 19 entries including `printables/WFG_printables_20260907T0059Z.pdf` and `printables/manifest_20260907T0059Z.json`; `README_KO.md` carries the ten-step recipe and `CITATION.cff` is in the list. **The call: R9's word 「printables」 asks that the kit which exists reaches the stick, and R7 is the line that asks the kit to be complete.** Reading R9 as also requiring R7's five would make R9 a duplicate of R7 and would mean the bundle line could never be ticked on its own merit; two lines, two questions. R7 stays ☐ on **WFG-026**. ⚠ **One defect rides inside this bundle and it is NOT one of this line's conditions, so it does not hold the tick — it is instead critic #32's one `fix-before-next-row` item.** `release/kcf-finals-2026/printables/manifest_20260907T0059Z.json:95` (and its repository original) still carries 「the 29 dispatch sheets in outputs/dispatch, which are already committed PDFs that print directly」, the sentence the same lap that fixed this line declared **false** and corrected in `README_KO.md`, `docs/finals_bundle.md` and this row. It is on the stick because the manifest is a stamped artifact under CHARTER §3.2 and only a kit rebuild can move it — **WFG-153(a)**, which rides with WFG-026's rebuild. | ☑ |
| R10 | ~~AI ledger~~ **Withdrawn 2026-09-04.** The organisers confirmed to the author that no AI-disclosure artifact is required (NH-008), and `AI_DISCLOSURE.md` was removed at the author's instruction. `ROUTINE_PROMPTS.md` and the `Co-Authored-By` trailers remain under CHARTER §9 as booth-explainability practice, not as a compliance artifact | Withdrawn, not failed | — |
| R11 | `docs/HANDOFF_ROUND3.md` §5.1 and every date in `docs/auto/` say `auto/dev`, 10-16 and 10-24 | The three live lines CRITIC F7 named are fixed at `1c1561e`: `CHARTER.md:11` and `RUBRIC.md:20` now read 10-24, and NH-006's question text is annotated as a superseded record rather than edited (§3.7). The `research/sweeps_2026-09-03/*` files and the two BACKLOG rows that quote the 10.18-vs-10.24 question predate or describe the NH-006 decision and keep their text as dated records. **Still ☐ for the branch half only:** `docs/HANDOFF_ROUND3.md:898` states "All work stays on `round3-dev`", which is WFG-024 and blocked on WFG-023 | ☐ |
| R12 | The author has run the booth recipe on the actual laptop once and closed NH-014 | | ☐ (author) |

---

## 2026-09-10T1426Z · critic #59 · ZERO lines ticked, the SIXTEENTH consecutive critic lap

**No line moves and no line is re-worded.** ⚠ **This lap appends prose only and does NOT re-emit the
checklist table**, deliberately: the table above sits at `:1826-1837` and three consecutive laps have now
cited it, two of them off by one. Re-emitting it would move it and silently invalidate every one of those
citations, which is the WFG-107 shape applied to a line reference instead of a count. ⚠ Its rows R1 to R12 are at **`:1826-1837`** at this head, not the `:1825-1836`
critic #57 and #58 both cited (header `:1824`, rule `:1825`); the note below uses the corrected pair.
Re-counted in place at `3867860`: **R1, R2, R4, R5, R6, R7, R8, R9 ticked; R3, R11, R12 not; R10 withdrawn 2026-09-04. 8 of 11.**
Unmoved since critic #43 ticked R8 at 2026-09-08T1429Z.

**Why nothing moved, measured rather than inherited.**

- **R3** is `blocked(NH-046)`, and NH-046 is now **two days past its date**. Its criterion names
  `make all-checks`, which cannot go green on any clone but the author's because `baseline-verify` is a hard
  prerequisite and the two acquisition manifests under `data/raw/firms_data/` are git-ignored. No lap may
  re-word a readiness line; that is the whole reason the entry exists.
- **R11**'s row **WFG-024** is `todo`, `agent_doable`, and one stale sentence of work. It is held shut by
  CHARTER §14b until R1, R3, R4, R7, R8 and R9 all tick, and **R3 is the only one of the six still unticked**.
- **R12** is the author's (NH-014, undated).

**So one open decision of the author's is holding two of the three remaining lines**, five days before
`sprint.end` (2026-09-15) and forty-four days before the finals.

**What this lap DID verify against the ticked lines, because a tick that is never re-checked is a claim and
not evidence.** All at `3867860`, each measured in this clone:

⚠ The first column below is deliberately NOT written as `| R7 |`, `| R9 |` or `| R1 |`:
`tests/test_finals_bundle.py::test_r9_still_enumerates_the_contents_this_list_resolves` and
`tests/test_printables.py::test_r7_still_enumerates_the_five_printables_this_list_resolves` each assert that
**exactly one** line of this file starts with that prefix, so a report table using the same cell shape turns
them red. That is the gate working, it caught this lap's first draft, and the note is here so the next lap
does not rediscover it.

| readiness line | re-checked how | result |
|---|---|---|
| line R7 | re-hashed all **seven** `SOURCES` of `docs/auto/finals/printables/manifest_20260910T1233Z.json` against the tree | **7 of 7 matching**; the paper in the booth box says what the repository says today |
| line R9 | re-hashed all **19** declared entries of `release/kcf-finals-2026/MANIFEST.json` against their sources | **19 of 19 matching**; the bundle names the `20260910T1233Z` kit |
| line R1 | read `web/finals.html`'s embedded payload and compared `registry.n_entries` / `n_reproducible` with `docs/NUMBERS.json` | **453 / 395** on the screen, **453 / 395** in the tree; the 57-entry drift critic #24 found is not back |
| line R1 | `web/finals.html` build stamp `53d1a4e` against this head | **11** commits behind a 30-commit staleness limit |
| line R5 | `gates.py --mode full` | exit **0**, `tests/test_judge_qa_bank.py` at **31** tests, all green |

⚠ **One thing R5's tick now costs, and it is worth writing on this page rather than only in NH-049.** R7 and
R5 are ticked by the same mechanism from opposite ends: the bank is a hashed source of the printed kit, so
**R5 being current is what makes any edit to the bank turn a gate red until R7 is rebuilt**. A critic lap,
which changes no artifact, therefore cannot add a Q&A card at all. That is NH-049, open, due tomorrow, and
this lap hit it for real: its judge drill produced one question with no answer in any file
(「IoU 0.394는 무엇에 견준 값입니까?」) and had to leave it as backlog row **WFG-228** rather than a card.

**Do NOT edit note (CHARTER §14c), and it covers lines rather than a file.** ⚠ **Do not re-emit the
checklist table at `docs/auto/KCF_READINESS.md:1826-1837` in an appended section.** Measurement behind it:
critic #57, #58 and this lap all cite the table by those exact line numbers, and critic #58's own append
moved it once already (its note says 「its position after this lap's own append」). A lap that needs to tick
a line **edits the status cell in place at those lines**; a lap that only reports edits nothing there.
**This note expires at the next critic lap unless that lap re-states it after re-checking the line numbers.**
It does not freeze the file, the table's contents, or any readiness question.


## 2026-09-10T1657Z · critic #60 · ZERO lines ticked, the SEVENTEENTH consecutive critic lap

Read at `71e95ee`, window 2026-09-09T16:20Z to 2026-09-10T16:44Z (61 commits, 46 pushed heads). Counted
from the checklist table itself rather than inherited: **its rows R1 to R12 are at `:1832-1843`** at this
head (the six lines this lap added to the page's lead moved them down by six from the `:1826-1837` critic
#59 correctly measured at `3867860`; header `:1830`, rule `:1831`). Ticked: R1, R2, R4, R5, R6, R7, R8, R9.
Unticked: R3, R11, R12. R10 struck through 2026-09-04.

- **R1 holds, both halves re-measured.** `web/finals.html` is offline by gate in the green
  `gates.py --mode full` run at this head (**2041 passed**, 64 skipped, 3 xfailed, pytest 315.2 s), and its
  build stamp is `4ab2e07`, **an ancestor of `HEAD` by 5 commits** against
  `tests/test_finals_screen.py`'s 30-commit staleness limit. The ancestry statement is licensed:
  `--is-shallow-repository` answers **false** and `git rev-list --count HEAD` answers **725** after this lap
  unshallowed a clone that again arrived at depth **51** (CHARTER §4). R1's other half asks that every
  on-screen **number** map to a registry key, and **WFG-228 put no number on the screen**: the disc null
  reached `docs/disc_null.md` and `docs/oracle_gap.md` §4c only, so R1 is untouched by the window's largest
  change. That is also why R2 does not move.
- **R2 holds and is one row away from being worth more.** The screen's 알려진 한계 panel gained nothing this
  window. The measurement a judge would most want beside the first card, the disc null and the centroid
  overshoot, is `todo` as **WFG-235** (Q36) and **WFG-237** (the document half); neither is on the screen.
- **R5 holds, and its two named stale cards from critic #58 are now closed.** Q38 (WFG-226) and Q29
  (WFG-229) closed at `ba76b8c` with the kit reprinted at `20260910T1233Z`. What replaces them is **not** an
  untick either: **Q36 · T0 is complete, cites a file, and is now out of date**, because since `b8fd6a8` the
  repository can answer 「0.394는 무엇에 견준 값입니까?」 and the card cannot. WFG-235 is that row, and this
  lap corrected it, because the row as filed told the next lap to write **2.536** onto a T0 card while the
  same day's `docs/disc_null.md:119-120` says 「2.5360 is not quotable without 2.2044 beside it」.
- **R7 and R9 hold, re-hashed here rather than inherited.** The newest printable is
  `manifest_20260910T1233Z.json` and its **seven** `sources` hash **7 of 7** against the tree;
  `release/kcf-finals-2026/MANIFEST.json` hashes **19 of 19**. Both re-computed in this lap's own process.
  ⚠ Seven of seven means the kit matches the tree, **not** that the tree is current: Q36 is stale inside a
  kit that hashes clean, which is the same gap critic #58 recorded for Q38.
- **R8 holds.** Forbidden-string and collision gates are green in the run above. ⚠ This lap files
  **WFG-236**, which is a `제출 자료` defect on two `docs/` pages rather than on the README, so R8's
  README half is not touched. The README half of the same question is **NH-055**, the author's.
- **R3 is still the only unticked line of the six CHARTER §14b needs**, and it is `blocked(NH-046)`.
  ⚠ **NH-046 is due TODAY, 2026-09-10, and it is NOT past due.** Its heading reads 「(by 2026-09-10)」 at
  `docs/auto/NEEDS_HUMAN.md:2847` and the entry was never re-dated. Critic #58 and critic #59 both wrote
  「NH-046 is now two days past due」, here and on `docs/auto/DIRECTION.md`; corrected rather than repeated,
  and recorded as a fresh instance of **WFG-107**. Five days of sprint remain. R11's row WFG-024 stays shut
  behind R3. R12 is the author's (NH-014). Appended to NH-046 on previous laps; not filed again.

⚠ **The one `Do NOT edit` note this lap writes, and it is line-scoped and re-measured (CHARTER §14c,
NH-036 A).** **Do not write a byte into `docs/auto/JUDGE_QA.md` without `make printables` at a new stamp and
a re-pointed `release/kcf-finals-2026/MANIFEST.json`.** The measurement behind it, taken in this lap's own
process at `71e95ee`: the newest manifest `docs/auto/finals/printables/manifest_20260910T1233Z.json` lists
seven `sources` and all **seven** hash equal to the tree, `docs/auto/JUDGE_QA.md` among them
(sha256 `df826a4cec52…`, first twelve characters; the full digest is in the manifest and is not restated here, because it contains a three-digit substring the retired-claim scanner reads as a count), so the first changed byte turns
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red. **This note covers
that one file and expires at the next critic lap unless that lap re-measures the seven hashes and re-states
it.** It freezes no other file and no question: WFG-235 and WFG-237 are expected to edit the bank, paying
the rebuild, and this note is the price tag rather than a prohibition on the work.

⚠ **No `Do NOT edit` note is written on `docs/oracle_gap.md`, `docs/disc_null.md` or `docs/MODEL_CARD.md`
by this lap.** WFG-233, WFG-236 and WFG-237 must all edit them, and a freeze would block three P0 rows.
