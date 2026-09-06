# CRITIC_LATEST — critic #29, 2026-09-06T2015Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `1b26c3a`. Window: `e95fe28..1b26c3a`, plus the
24 h to 2026-09-05T19:57Z for the gate, CI and report checks.*

⚠⚠ **READ THIS FIRST: the window I reviewed contains NO DEV LAP.** `git diff e95fe28..1b26c3a` changes
**zero lines outside `docs/auto/`**. The 18:17Z slot was ceded to the research routine (CHARTER §14,
`LOOP_CONFIG.json` -> `research_cadence_note`, the author's 2026-09-04 decision). So critic #28's one
`fix-before-next-row` item has **never been in front of a dev lap**, and I have **carried it forward
verbatim rather than spending a new one**. If you are the 20:17Z dev lap, this is your first item and it
is the same item as last time, one line wider.

## fix-before-next-row (exactly one, CHARTER §14b — CARRIED, not re-filed)

**WFG-138 — the fire-blind caveat reached the manuscript, the booth script and the finals template, and
stopped at the two surfaces a human actually reads. There are now two halves.**

**(a) `README.md:22-26`, unchanged since critic #28 filed it.** The 「Headline result」 bullet:

> On the canonical Yeongdeok field, **42 of 458** scanned origins reach a refuge **only** when the router
> accounts for where the fire will be, and **2** have no safe walking route at all
> ([Round 3](#round-3-2026-08); the 32.6 % coverage caveat applies).

`paper/manuscript.md`'s Abstract carries the same two numbers and then says: 「That contrast is measured
against a fire-blind baseline, so it does not separate knowing where the fire will be from knowing where
it is.」 The baseline is fire-blind in this repository's own words
(`src/wildfireguardian/routing/evacuation.py:270`, `docs/real_roads_real_hazard.md:50`). `paper/GAPS.md`
G7 names the two surfaces already repaired for the identical claim: the booth script's 3막 sentence
(**WFG-103**, `92366cb`) and the finals template (**WFG-109**). The README is the fourth.

**(b) NEW, found by this lap's judge drill, and it is the surface the student speaks from.**
`docs/auto/JUDGE_QA.md` **Q19**'s draft answer contains:

> 예보가 결정을 바꾸는 축은 다른 곳입니다. 도로를 따라가는 경로 선택이고, 영덕에서
> 458개 원점 중 **42**개, 의성·안동에서 368개 중 **91**개가 시간 인지 경로에서만 대피 지점에 닿습니다.

The ⚠ block **immediately beneath it**, written by critic #22 and tightened by critic #23, corrects the
**91** (「91은 불을 전혀 보지 않는 대조군과의 비교입니다」) and says **nothing at all** about the **42**
in the same sentence. Both numbers come from the same fire-blind control. And 영덕 needs the caveat
**more**, not less: the present-perimeter opponent has only ever been run on 의성·안동
(`data/processed/present_perimeter_arm_uiseong_andong_2025.json`), so for the 42 the fair opponent has
never been run at all.

**Why this is the same item and not a second one.** Critic #27's root objection was that a correction
reaches the pages the loop reads and stops at the surface a human meets. This is that objection at its
smallest scale yet: not one file short of the human surface, but **one clause short inside it**. The
mechanism that would have caught it does not reach it either — `WC-004` and `check_withdrawn_claims.py`
key on a **withdrawn string**, and this claim was **narrowed**, never withdrawn.

**Done when.** (a) The README bullet carries the manuscript's own caveat, in the manuscript's own words
or a faithful equivalent. Suggested minimal edit, additive, no number moves: append 「That contrast is
measured against a **fire-blind** baseline, so it does not separate knowing where the fire will be from
knowing where it **is**; the present-perimeter opponent has been run on 의성·안동 only
(`docs/present_perimeter_arm.md`, WFG-129 for 영덕)」. (b) Q19's **draft answer** carries the same
caveat on the 42 — in the draft the student speaks, not only in the ⚠ note above it, since the ⚠ note is
what already failed to reach it. Grade (b) by mutation: put the bare sentence back and a test in
`tests/test_judge_qa_bank.py` should go red naming Q19.

**Constraints.** This is the 「Headline result」 bullet, **not** the README's opening paragraph about the
2025 fire, which CHARTER §3.5b and `DIRECTION.md` protect. Put **no** fair-opponent margin (9, 27, 5, 19)
in either sentence; NH-032 is open. Do not enlarge into WFG-129's experiment. A dated ⚠⚠ note with the
sentence to say is already on Q19 at this head, so nobody rehearses the bare 42 tonight; 50 judge-qa,
printables and fair-opponent tests are green over it.

## The root objection

**The booth kit's staleness has become a reason not to improve the booth.**

`docs/auto/JUDGE_QA.md` has now drifted from the printed manifest three times. Re-hashed here at
`1b26c3a`, all four `SOURCES` in one process: `BOOTH_SETUP.md` `ef7342dacf…`, `DEMO_SCRIPT_5MIN.md`
`b1aae78f35…` and `DETECTION_FLOOR_CARD.md` `84648d4d6e…` all **match**; `docs/auto/JUDGE_QA.md`
manifest `2c8451211e5f97…` against tree **`175da9e50c5ce9…`**. The series is `af955a30fa…` (critic #27)
-> `7d5ac4c9c5…` (critic #28) -> `175da9e50c…` (here).

**Every one of those three drifts was a critic or dev lap adding a correction note to the bank** — #27's
Q35 note at `a64b904`, the WFG-133 lap at `923ffbd`/`32de531`, critic #28's own `050731a` — and **not one
of them was a judge-facing improvement.** This lap adds a fourth for the same reason and does not exempt
itself.

Meanwhile **WFG-144**, the one genuinely new judge-facing card the research lap found (「산림청·경기도가
이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」, the most likely question a disaster-response judge
asks, and the bank has no card for it), is filed **P1**, sequenced 「after the WFG-134 / WFG-130 rebuild,
or the printed 17 pages go stale a fourth time」. So freshness is rationed against the booth and spent
freely on the loop's own corrections, and the rebuild it is sequenced behind has been displaced four
windows.

**The cheapest test: take WFG-140 and WFG-134 in one lap, gate first.** Once drift is caught by a gate,
the sequencing argument dissolves and no judge-facing row needs to wait behind a rebuild again. WFG-140
must go **red on today's tree** before the rebuild makes it green.

## Verified rather than read

- `gates.py --mode full` **ALL GREEN** at `1b26c3a`: `1599 passed, 62 skipped`, cold, 273.6 s — identical
  to critic #28's cold `1599 / 62`, like for like, which is the correct result for a window with no code
  in it. `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is CHARTER §3d information.
- `auto-gates` runs **161 to 180** on `auto/dev`, read through the GitHub MCP (WFG-119 records the `curl`
  403): **17 `success`, 3 `cancelled`** (`dfdf480`, `828bbae`, `ef61e9b`, each superseded by a green push),
  **no `failure` at all**. Run 180 at `1b26c3a`, this head, is `success`. **No gate finding and no CHARTER
  §4b finding this lap.**
- `--assert-head` exits 0. Every **dev** report in the window carries `Reviewed by:`. The research lap's
  report carries none — **WFG-147**, a gap in the routine's prompt rather than a missing practice.
- Clone fully unshallowed: `git rev-parse --is-shallow-repository` answers `false`, 500 commits.
- **Sourcing re-checked, not accepted.** Both live URLs behind the new landscape note re-opened here.
  경향신문 (G-DAPS) confirms the date, the 30-minute steps, the 읍면동 unit, the **589** alert facilities,
  the following-month trial and **no accuracy figure**. 사이언스타임즈 confirms every NIFoS figure quoted.
  **One error: the note dates that article 2026-02-12 and the page says 2026-02-13** — **WFG-146**.
- Gmail: no author reply is waiting. The search returns only the loop's own sent reports.

## Filed this lap

| id | what | priority |
|---|---|---|
| **WFG-138** | widened by half (b), Q19's uncorrected 42; **carried** as the one item | P0 (existing) |
| **WFG-140** | annotated with the third drift and the root objection; take it with WFG-134 | P0 (existing) |
| **WFG-145** | on a research day a `fix-before-next-row` item has no dev lap to take it | P1 |
| **WFG-146** | 사이언스타임즈 date is 2026-02-13, not 2026-02-12 | P1 |
| **WFG-147** | the research report carries no `Reviewed by:` line | P1 |
| **NH-038** | updated with the sixth window and the ceded-slot fact; **no new NH entry opened** | open |

## Not reported, deliberately

- **Critic #28's falsifiable test (2) on WFG-138 could not be run and its verdict is not reported.** It
  asked whether the item survives a dev window; there was no dev window. It runs cleanly at the next
  critic head, because the 20:17Z slot is a dev slot.
- **KCF_READINESS is 4 of 11 for a sixth consecutive critic lap and I did not fire the direction rule.**
  A window with no dev lap cannot tick a line; reading that as a direction failure would be false. The
  measurement went to NH-038.
- **No row moved and the reorder budget is unspent.** WFG-138 is still the highest-leverage row for
  2026-10-24.

## The falsifiable test for critic #30

1. The 20:17Z slot is a dev slot, so critic #28's test finally runs. If `README.md:22-26` still says
   「only when the router accounts for where the fire will be」 with no fire-blind caveat at the next
   critic head, the finding is about the dev lap's step 3 and not about the row.
2. If that lap clears WFG-138's README half and leaves Q19's **42** standing, then a widened row does not
   travel and the correct unit is one row per surface. Re-file (b) separately and say so.
3. Re-hash `docs/auto/JUDGE_QA.md` against the newest printables manifest. If it has drifted a **fourth**
   time and the fourth drift is again a correction note rather than an improvement, the root objection
   above is confirmed and WFG-140 stops being a P0 row and becomes the item.
