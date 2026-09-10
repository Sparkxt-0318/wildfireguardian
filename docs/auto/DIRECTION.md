# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-10T0825Z by critic #57 (CHARTER §14).
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

**`docs/oracle_gap.md:39` names the wrong script for the array that document is entirely about. Change the
name; change nothing else.** The table row for `haz_stack` reads 「the **leave-one-fire-out forward
simulation**. `scripts/run_forward_sim_region.py` fits the spread_v2 model on every fire EXCEPT the target」.
That script never touches this file: `grep -c routing_demo_canonical scripts/run_forward_sim_region.py`
answers **0**, and the script writes `hazard_{fid}.npz` (`:283`) and `forward_sim_regions.json` (`:338`).
`data/processed/routing_demo_canonical.npz` — shape `(5, 181, 156)`, which is the row's own shape — is
written by **`scripts/build_canonical_hazard.py`** (`:109` `--npz-out`, `:177` `savez_compressed`).

⚠ **The claim itself is TRUE and must not be softened.** `scripts/build_canonical_hazard.py:130` reads
`model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != args.fire])`, and its own step print at
`:129` says 「fitting leave-the-target-fire-out」. Only the pointer is wrong. Replace the script name with
`scripts/build_canonical_hazard.py` and cite `:129-130`; write no new number, register nothing, rebuild
nothing.

**Why this and not the two larger findings.** It is the only one of the three that is genuinely minutes:
`docs/oracle_gap.md` is in no `SOURCES` list and on no build path, so the edit cascades into no gate. It is
on the page **seven places on four judge-facing surfaces** send a judge to for exactly this question
(critic #56's count, re-checked), and it is 「사용된 자료에 대한 출처 명기」, a named criterion of a 20-point
row, failing on the one page whose whole purpose is to be checkable. A software-professor judge who opens
the named script finds a `grid_note` saying Yeongdeok's field was built on a different bbox — that is, the
script telling them it did not make this array. **NH-053** quotes the wrong sentence verbatim (one hit for
`grep -n run_forward_sim_region docs/auto/NEEDS_HUMAN.md`; cited by entry and not by line because this lap's
own appends moved it from `:3200` to `:3236`); it is record class, so annotate it in the same lap rather than
editing the quote.

## Next three rows, and why each is next

Table order at `16e6824`. This lap spent **ZERO** §3b reorders; the ordering below is done with this page's
own naming power (§14: dev 「takes the row it names when it names one with a reason」), which is reversible
by one line and does not touch the table.

1. **WFG-225 (P0, KCF) is the next row to claim.** The screen five judges stand in front of prints
   **◆ 예산 초과 2** on the panel for the region it opens on, and **3** for Uljin-Samcheok, with no word of
   the correction that reached `README.md:145-149` and `docs/multi_region.md` §3.1 six hours ago. The gate
   written to keep that correction honest, `tests/test_budget_rule_asymmetry_is_stated.py`, grades those two
   files and nothing else (`:63-64`), so it cannot see the screen. This is critic #53's fifth-surface shape
   on the same surface, one window later.

2. **WFG-226 (P0, KCF) behind it, and it is on paper.** `docs/auto/JUDGE_QA.md:1421` card Q38 still tells
   the student to say 「오늘 저장소는 이 질문에 두 가지로 답합니다 — 그게 결함입니다」. It gives one answer
   as of `5bcfe11`. The bank is one of the seven hashed sources of the 0140Z printed kit and all seven hash
   equal to the tree, so the stale card is in the booth kit too. Bank edit **plus** `make printables` plus a
   re-pointed bundle manifest, or `tests/test_printables.py` goes red (NH-049).

3. **Behind those: ten inherited P0 rows and five sprint days.** Counted at this head rather than inherited:
   WFG-007, 117, 129, 121, 106, 036, 101, 119, 024, 054 are `todo`; `blocked`: WFG-213 (NH-052), WFG-124 and
   WFG-104 (NH-032), WFG-023 (human). **WFG-007 is still the trap** its own status cell describes (「the
   agent half is done; the student half is not」), so a lap that falls back to table order reaches a row with
   nothing takeable in it. Take WFG-117 before it, or record in the row why not.

### Why zero reorders, in one paragraph

DIRECTION named WFG-128 and it closed at `5bcfe11`, so this page was stale again on arrival — the third
consecutive window in which the page's named row was `done` before the page was read. The fix for that is
not another reorder: the two rows this lap wants a dev lap to meet first are rows this lap **filed**, and a
newly filed row is not a move. They are filed in the table like any other P0 row and named here instead,
which costs the table nothing and is undone by deleting two paragraphs.

⚠ **Filing note, and it is a deliberate departure from this routine's stored prompt.** The prompt says a
larger judge-facing finding is 「filed as a P0 row at position 1」. **NH-051 is open and shows that mechanic
belongs to NH-038 option D**, while the prompt cites option **B**, whose own words put the row 「in the table
like any other」. Three critic laps have already filed at position 1 on that authority. This lap filed in
table order and used this page instead. If the author's answer to NH-051 is D, moving these two rows up is
one edit.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **REMOVED, and the removal is the point.** Critic #56 wrote here 「Do not print a per-slice
  `obs_time_min` … only the headline `og_yeongdeok_obs_time_min` is registered」. **That was false**, and it
  did damage before it was caught: the `0703Z` dev lap obeyed it and shipped a first draft of
  `docs/oracle_gap.md` §4 that **withheld its own evidence, in prose, on a judge-facing page**, on the
  ground that the numbers were unregisterable. Its independent reviewer blocked on it; the lap registered
  the five keys additively instead of arguing. Re-checked here rather than inherited:
  `grep -o 'og_yeongdeok_t[0-9]*min_obs_time_min' docs/NUMBERS.json | sort -u` returns **five** keys at
  `16e6824`. CHARTER §14c says such a note expires at the next critic lap unless that lap re-states it after
  re-checking; I re-checked, it is false, so it is gone rather than re-stated. This is the concrete instance
  NH-036 asks the author about, and it is appended there.
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a clone you deepened.**
  Unchanged from critic #55 and #56, and re-measured here: `web/finals.html`'s 개발 일정과 역할 card prints
  its as-of stamp from that artifact's `last_commit_date` (**2026-09-09** at this head), so the guardrail
  freezes a date a judge reads, and the finals are 2026-10-24. A rebuild from a **fresh full clone** writes
  seven-character anchors and is safe. **WFG-217** is the fix; its deadline is the 10-16 freeze.
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets.** `done` (WFG-222,
  `WC-013`); the corrected wording is **지점 단위** with 「화재 위험면과 지형은 합성 · 출발지는 표본 좌표」 and
  「실제 확산면으로 만든 출동 지시서는 아직 없습니다」 **in the same block**. `README.md:220-251` is the model.
  The four remaining 「가구 단위」 in `docs/auto/JUDGE_QA.md` are **deliberate and correct**. Do not "fix" them.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** NH-053 is open. Describe the mechanism.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open. ⚠ **The README bounds MOVED AGAIN this window, for the third window running**, measured
  by the section headers rather than copied: 「### 1. 가장 강한 주장에 「공정한 상대」를 세웠습니다」 opens the
  block and 「### 2. 철회한 주장이…」 closes it, and that pair sits at **`:263-342`** at `7dabdef`,
  **`:270-349`** at `9b7d21c` and **`:274-353`** at `16e6824` — down four more lines, pushed by the Round-4
  preamble. The single 「구체적인 margin 값들은 부스에서 말하지 않습니다」 line is at **`:340`**. The
  `Do NOT edit` note in `CRITIC_LATEST.md` is re-measured there this lap and expires at the next critic lap
  (CHARTER §14c). **A lap that copies any earlier pair of numbers protects the wrong lines** — anchor on the
  two headers, not on the digits.
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one.** `paper/check_paper.py` reads
  **8,997** body words at this head against a 9,000 hard fail: **three** words of margin, unchanged from
  `9b7d21c`. NH-037 came due **2026-09-10** and is open.
- **Do not change `mr_uiseong_fa_exceeds_budget`.** It is 2, it is registered, NH-031 option A says nothing
  committed moves, and the registry half is **WFG-122** (`todo`). WFG-225 adds a caveat to a screen; it
  moves no value.
- **Do not refit anything**, and do not regenerate a committed artifact (CHARTER §3 rule 2).
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** The differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the fourteenth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. The cause is unchanged and was re-read rather than restated: R12 is the author's (NH-014);
R3 is `blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b until R1, R3, R4, R7, R8 and R9 all
tick, of which **R3 is the only one unticked**. **NH-046 came due 2026-09-10 and is open.**

⚠ **The P1 measurement critic #56 appended to NH-038 is re-counted here, because a one-window number is an
anecdote and a two-window trend is a fact.** Counted at `16e6824` by status prefix over the table between
the header row and `## Details`, which is the method and is stated because critic #56's P1 `done` count of 6
and mine of 9 differ by parser and not by fact (seven P1 cells begin with prose the prefix match cannot
classify): **P0 is 65 done, 4 blocked, 1 dropped, and 12 todo — of which 10 are inherited and 2 are this
lap's own filings.** The loop closed WFG-128 and WFG-215 this window, so the inherited P0 `todo` count fell
11 → 10, the second consecutive window it has fallen. **P1 is 9 done and 101 todo**, and this lap added the
101st. §14b releases
that block only when R1, R3, R4, R7, R8 and R9 tick, R3 cannot tick without the author, and the sprint ends
**2026-09-15**. The P1 queue is a write-only ledger on the measured rate, and the critic is still its main
producer. Appended to **NH-038**, which is the author's question about exactly this rule.

## Critic's last direction note

**2026-09-10T0825Z, critic #57. ZERO §3b reorders — the first critic lap of the sprint to spend none, and
the reason is that the two rows a dev lap should meet first are rows this lap filed. ONE
`fix-before-next-row` item (`docs/oracle_gap.md:39`, a wrong script name on the anchor page, pure prose).
THREE new backlog rows (WFG-225, WFG-226, WFG-227), none at position 1, and the departure from the prompt's
mechanic is stated above rather than done quietly. ZERO new NEEDS_HUMAN entries; three existing entries
gained measurements (NH-036, NH-038, NH-049, NH-051). Scorecard: Track B 94 → 95 (설계와 방법론 UP to 20 on
critic #56's own pre-registration, 데이터 수집·분석·해석 UP to 20, 제출 자료 DOWN to 19); Track A 94 HELD on
two moves that offset (설계와 방법론 UP to 20, 제출 자료 DOWN to 17).**

Verified at `16e6824`. `gates.py --mode full` exits **0** (**1985 passed**, 64 skipped, 3 xfailed, pytest
482.0 s, up 27 tests in one window); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts,
which is NH-029 and §3d working. **GitHub `auto-gates`, runs 278 to 321: 44 runs, 36 `success`, 8
`cancelled` (278, 284, 306, 310, 312, 316, 317, 320 — each superseded by the next push within minutes) and
ZERO `failure`**, with **321 green at this exact head**, so CHARTER §4b sets no finding #1 for the sixth
consecutive lap. **All eight** dev reports in the window record `Reviewed by:`, all eight name `subagent`,
and **seven of the eight record `block`** and spend commits acting on it (the eighth, 1928Z, records `pass`). The clone was **unshallowed** before any counting
(`--is-shallow-repository` answers `false`, 703 commits) because at depth 50 the 26-hour window and the
clone boundary coincided exactly, which would have silently truncated every count on this page.
