# Critic #67 — 2026-09-11T1416Z, reviewed `dec00f4`

**The next dev lap reads this file first.** Window `fbc2273..dec00f4`. `fbc2273` is this
shallow clone's oldest resolvable commit (2026-09-10T18:39Z, 19 h 51 m back), so it is the
base rather than a chosen one; the clone is SHALLOW at **50** commits, measured here with
`git rev-parse --is-shallow-repository` and `git rev-list --count HEAD`, and was deliberately
NOT deepened. **No ancestry or reachability claim is written anywhere in this lap.** Counted
from the reports added in the range: **eight finished dev laps**, seven critic laps, four
paper laps (filed `--kind manual`) and one research lap.

**The window's one real result: WFG-129 ran, after seven direction pages named it next.**
The dev lap of `20260911T1219Z` built the fair opponent on the canonical 영덕 field and it
saves **26 of the 44**. That is the strongest methodological act of the last several days and
this lap does not qualify it: the run re-derived the committed 414 / 42 / 2 partition before
it wrote anything, pre-registered its own root objection and answered it by measurement, split
the outcome into three named buckets rather than one number, and its independent reviewer
BLOCKED it on a false monotonicity claim which the lap then fixed rather than argued with.

**And the window's defect is what the same lap did not do.** It read WFG-129's constraint
(「no number from this run reaches a judge-facing surface until the critic or the author has
read it」) as 「do not add」, which is right, and left four judge-facing lines standing that say
the comparison has **never been run** on 영덕.

---

## `fix-before-next-row`: ONE, and it is four lines of the same clause plus the rebuild

⚠⚠ **The repository disproved a sentence this morning and the sentence is still in front of
five judges, one of the four lines from memory and on paper in the box.** This is **WFG-258**
half (a), filed at table position 1. Measured at `dec00f4` in this lap's own process:

| line | what it says | status |
|---|---|---|
| `README.md:33-34` | 「The fair opponent ... a plan that refuses only what is burning now, has been run on 의성·안동 only ...; on 영덕, where the 42 comes from, **it has never been run**」 | FALSE at `7991512` |
| `README.md:325` | 「⚠ **영덕에서는 이 상대를 아직 돌리지 않았습니다.**」 | FALSE |
| `docs/auto/JUDGE_QA.md:954` | Q19's **draft answer, the sentence the student speaks**: 「지금 불난 자리를 피하는 경로와의 비교는 의성·안동에서만 했고, **영덕에서는 아직 하지 않았습니다**」 | FALSE, said from memory |
| `docs/auto/JUDGE_QA.md:1004` | critic #29's prescribed 「**42 를 말할 때 붙일 문장**」, repeating it verbatim | FALSE, prescribed |

The disproof is in this tree: `scripts/measure_present_perimeter_yeongdeok.py` →
`data/processed/present_perimeter_yeongdeok_2025.json` (six registered `ppy_yeongdeok_` keys)
→ `docs/present_perimeter_yeongdeok.md`, and `paper/GAPS.md` G7 already records it as
✅✅ **CLOSED**.

**On paper, measured here and not read from a report:** `release/kcf-finals-2026/MANIFEST.json`
hashes **19 of 19** against its sources and names `WFG_printables_20260911T1226Z.pdf`, whose
seven `SOURCES` documents hash **7 of 7** against the tree, 59 pages. So Q19's false clause is
in the box a judge carries away.

**The fix, and it is minutes.** Each of the four lines says instead that the comparison **has**
now been run on 영덕 and names `docs/present_perimeter_yeongdeok.md`, and says the counts are
not yet licensed for the booth. Then `make printables` at a new stamp and
`release/kcf-finals-2026/MANIFEST.json` re-pointed (NH-049). Grade by mutation: put the false
clause back and `tests/test_judge_qa_bank.py` should go red naming Q19.

⚠ **Put NO count on any surface in this item.** Not 26, not 16, not 2, not 44. **NH-059** is
the author's decision on whether they may be spoken, filed this lap. `docs/auto/DIRECTION.md`
bars every margin while NH-032, NH-034 and NH-052 are open, and although the artifact's
`what_this_is_not` says in its own words 「It is NOT a margin」, a judge hearing 26-of-44 will
compute one.

⚠ **NH-054 does not hold this edit, and here is the reasoning rather than an assertion.**
NH-054 is open on the **proportion** of the 「Headline result」 bullet — it measured 433
characters of result against 1,853 of qualification — and all four of its options preserve
every ⚠ block. This item changes the **truth** of one clause inside that bullet, at about the
same length, deletes no caveat, softens nothing, moves nothing, and leaves the proportion
NH-054 asks about intact. A freeze placed on a presentation judgement does not license leaving
a disproved sentence standing; CHARTER §3.5 is the senior rule. **Do not** touch `README.md`'s
opening paragraph about the 2025 fire (CHARTER §3.5b), and **do not** weaken the two caveats
the gate requires (the fire-blind control and the oracle-in-the-grading); both are still true
and both must stay in the same block as the number.

⚠ **Do not widen this into WFG-033(b) or NH-027.** A **buffered** present-perimeter opponent
genuinely has not been run on 영덕, and `docs/present_perimeter_yeongdeok.md` §5 item 5 says
so. Only the zero-buffer arm was run.

---

## The root objection (`hate`)

**This project checks whether its sentences are well-worded far faster than it checks whether
they are still true.** Critic #66 wrote a version of this and the window proved it in a harder
form. WFG-129's own page carries a 170-line §5 headed 「What this does **not** show」, eight
numbered items, two of them added by a reviewer that blocked the lap. It is the most careful
piece of self-criticism the repository has produced this week. And in the same window, on the
same subject, four lines a judge reads went stale and nobody looked. The loop's care is
concentrated on **the page being written** and almost absent on **the pages that page makes
wrong**. WFG-138 is the record of this exact sentence going wrong the last time.

**The cheapest test, and it is not a row:** before a lap declares a row done, grep the
judge-facing set (README, `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`,
`docs/auto/finals/`, `web/finals.html`, `paper/manuscript.md`) for the **negation** of what
the lap just measured. That is one command. It would have caught this one, WFG-138, and
critic #27's original.

---

## Findings, ranked

1. **WFG-258 (P0, position 1, and half (a) is the item above).** Four judge-facing lines
   assert what the tree disproves; the manuscript adds two more
   (`paper/manuscript.md:414-418` with a `[GAP:` marker `paper/GAPS.md` already calls closed,
   and `:718-724`), and `tests/test_future_aware_attribution.py:16-17,196` instructs the next
   lap to write the false clause into a failure message. The manuscript half is the **paper
   routine's** under CHARTER §12.
2. **WFG-259 (P0, position 2).** `docs/present_perimeter_yeongdeok.md` §5 item 5 asserts
   「at 500 m, **15 of the 16** flip」 and a named origin flipping at 100 m. Checked here: the
   artifact has **no** dilation or buffer-sensitivity block, `docs/NUMBERS.json` holds six
   `ppy_yeongdeok_` keys and none is the 15 or either width, and the script takes no buffer
   argument. **Nobody can re-derive it from this tree.** CHARTER §3.3: 「A number you cannot
   register, you do not write.」 The sentence exists because a reviewer blocked a **false**
   claim in the same place, which is why this is a row and not a rebuke — but it is the most
   consequential integer in the repository (it implies a slightly better opponent reaches
   41 of 42) and it is the one with nothing behind it.
3. **NH-059 (new, HIGH, the one new author question of this window).** Does 26 / 16 / 2 go on
   a judge-facing surface, and in what words? Four options, a reading offered.
4. **Zero KCF_READINESS lines ticked, for the twenty-fourth consecutive critic lap** — and
   this is reported rather than re-filed, because critic #52's measurement of the cause still
   holds and no lap can change it: R12 is the author's (NH-014), R3 is `blocked(NH-046)`,
   R11's WFG-024 is held by §14b until R3 ticks. 8 of 11. **There is no path from any amount
   of loop work to a ninth tick.**
5. **The decision channel has produced nothing for six days.** `decisions_seen.json` records
   `"seen": []`; the newest applied decision is NH-031 of **2026-09-06**. Confirmed here at
   the Gmail connector: the 25 newest threads matching the report subject in the last 14 days
   are all single-message sends by the loop itself. PR #31's comment list is empty. That is
   **WFG-211**, already `todo`, and **26 decisions are open, 2 undated**. Sprint ends 09-15.

**No finding #1 under CHARTER §4b, for the sixteenth consecutive lap.** Read through the
GitHub MCP (CHARTER §4 forbids `curl` against `api.github.com` here, WFG-119): runs 364 to 374
on `auto/dev`, **no run in the window concluded `failure`**; one `cancelled` (368, superseded
by the next push); run **374 is `success` at `dec00f4`**. Every dev report in the window
records `Reviewed by:` — nine checked, all `subagent`, four of them `block`.

---

## What this lap verified rather than assumed

- `gates.py --mode full` exits **0** on its FIRST run in this sandbox at `dec00f4`:
  **2127 passed**, 65 skipped, 3 xfailed, pytest 318.3 s. `baseline-verify` is the known
  WARN (NH-029 / CHARTER §3d; the two MISSING contracts are under git-ignored
  `data/raw/firms_data/`, which never reaches a fresh clone).
- The bundle hashes **19 of 19**; the kit hashes **7 of 7**, 59 pages,
  `WFG_printables_20260911T1226Z.pdf`, and the bundle names it.
- `docs/auto/DEMO_SCRIPT_5MIN.md` has **not** changed since `f7ee58d`, and the newest pace
  artifact `data/processed/demo_script_pace/pace_20260911T0620Z.json` still reads **6.00** <!-- collision-ok: 6.00 — the SPOKEN RATE of the whole script in syllables per second, which is `syllables_per_second` in that artifact. The gate reads it against demo_pace_20260911t0620z_rate_spread (1.02), the RATIO of the fastest segment's implied rate to the slowest (`implied_rate_spread`, unit x, max over min); two different quantities in the same file, and neither value is stale. -->
  syllables per second. Critic #66's pre-registered **downward** re-examination of Track A
  구현 및 유용성 on script growth therefore **does not fire**. This note names those two
  paths and that measurement and expires at critic #68 unless that lap re-measures.

## `Do NOT edit` notes carried, re-checked, and their expiry

Per CHARTER §14c every such note names lines and a measurement and expires at the next critic
lap unless re-stated. Re-checked here:

- **Do not unshallow the clone** (critic #66). RE-STATED. `git rev-parse
  --is-shallow-repository` answers `true` at **50** commits in this clone, and
  `gates.py --mode full` exits 0 on its first run without deepening. The stated cost holds:
  `tests/test_timeline_roles.py:234` **SKIPS** rather than runs in a shallow clone, so a green
  critic gate does not certify it; GitHub at `fetch-depth: 0` does, and run 374 is green.
  Recorded on **WFG-217**. Expires at critic #68 unless re-measured.
- **Do not edit `README.md`'s TL;DR lead while NH-054 is open.** RE-STATED **NARROWED**: the
  bar covers the bullet's **ordering and proportion**, which is what NH-054 measured
  (433 result characters against 1,853 of qualification). It does **not** cover the truth of a
  clause inside it. WFG-258 (a) corrects `README.md:33-34` under that narrowing and nothing
  else in the bullet.
- **Do not edit `docs/auto/JUDGE_QA.md` without `make printables` at a new stamp and a
  re-pointed MANIFEST** (NH-049). RE-STATED, re-measured here at `dec00f4`: kit 7 of 7,
  bundle 19 of 19, bundle names the newest kit.
- Every other ⚠ line in `docs/auto/DIRECTION.md` is carried unchanged and is not re-derived
  here; this lap re-measured only the three above.

## Scorecard

**Track B 94 → 94, Track A 97 → 96.** Two rows move on Track B and offset; one moves on
Track A. 데이터 수집·분석·해석 **18 → 19** (B), 제출 자료 **19 → 18** (both tracks). Evidence
in `docs/auto/SCORECARD.md` at this date.

## Next row for the dev lap

After the item above: **WFG-259**, then **WFG-256** (the rotation null, still `todo` and still
the only thing that would license a sentence about 「모양」), then **WFG-255**.
