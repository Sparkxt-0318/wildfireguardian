# CRITIC_LATEST — critic #57, 2026-09-10T0825Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `16e6824`, and
every measurement below was taken at that head unless it says otherwise. ⚠ **This clone arrived SHALLOW at
exactly 50 commits, and 50 commits was exactly my 26-hour window**, so `git log --since='26 hours ago'`
returned all 50 and would have silently truncated every count on this page. I ran `git fetch --unshallow`
before counting anything: `git rev-parse --is-shallow-repository` now answers **`false`** and
`git rev-list --count HEAD` answers **703**, so the window below is a real 24 hours and the ancestry claims
here are licensed under CHARTER §4. Full report: `docs/auto/reports/2026-09-10T0825Z-critic.md`.*

## `fix-before-next-row`: ONE. `docs/oracle_gap.md:39`, and it is one script name

**Replace `scripts/run_forward_sim_region.py` with `scripts/build_canonical_hazard.py` in the `haz_stack`
row of the §2 table, and cite `:129-130`. Change nothing else on the page.** It is prose, it writes no
number, it registers nothing, it rebuilds nothing, and it touches no `SOURCES` list.

**What is wrong.** `docs/oracle_gap.md:39` reads:

> `haz_stack` | float32 `(5, 181, 156)` | the **leave-one-fire-out forward simulation**.
> `scripts/run_forward_sim_region.py` fits the spread_v2 model on every fire EXCEPT the target, so this is a
> model output on a fire the model never saw. The router plans on it.

That script never touches that file. Measured here in one process, not read from a report:

| check | answer |
|---|---|
| `grep -c routing_demo_canonical scripts/run_forward_sim_region.py` | **0** |
| what that script writes | `hazard_{fid}.npz` (`:283-285`) and `forward_sim_regions.json` (`:338`) |
| what writes `data/processed/routing_demo_canonical.npz` | **`scripts/build_canonical_hazard.py`** — `:109` (`--npz-out` default) and `:177` (`np.savez_compressed`) |
| the shape in the row itself | `(5, 181, 156)`, which is the canonical npz; the named script's own `grid_note` says Yeongdeok's field used the larger fire-ACQUISITION bbox, i.e. it is telling the reader it did not make this array |

⚠⚠ **THE CLAIM IS TRUE AND MUST NOT BE SOFTENED, HEDGED OR WITHDRAWN.** `scripts/build_canonical_hazard.py:130`
reads `model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != args.fire])` and its own step print at
`:129` says 「fitting leave-the-target-fire-out」. The target fire **is** excluded. This is a wrong pointer
under a correct claim, so the repair is to fix the pointer — **not** to weaken the sentence, and **not** to
open a `WC-###`, because nothing is being withdrawn.

**Why it is a preemption and not a row.** It is the only one of this lap's three findings that is genuinely
minutes: `docs/oracle_gap.md` is in no `SOURCES` list and on no build path, so the edit cascades into no
gate. And it is 「사용된 자료에 대한 출처 명기」, a named criterion of a 20-point row on **both** rubric tables,
failing on the page **seven places on four judge-facing surfaces** send a judge to for exactly this question
(critic #56's count, re-checked at this head). A software-professor judge who opens the named script to check
the LOFO claim finds a script that does not make the array.

**One more line, in the same edit.** **NH-053** in `docs/auto/NEEDS_HUMAN.md` quotes the wrong sentence
verbatim (find it with `grep -n run_forward_sim_region docs/auto/NEEDS_HUMAN.md`, one hit; it was at `:3200`
at `9b7d21c` and this lap's own appends pushed it to `:3236`, which is exactly why it is cited by entry and
not by line). That page is record class and the quote must stay, so annotate it in the same lap — one
bracketed note saying the script name was corrected at this commit and the LOFO claim was not.

## The two larger findings, filed as rows, NOT as preemptions

Both are judge-facing and both are larger than minutes, so under CHARTER §14b they are rows.
`docs/auto/DIRECTION.md` names them as the next two rows to claim.

**1. WFG-225 (P0) — the screen five judges stand in front of prints the two counts this window corrected,
with none of the correction.** `web/finals.html`'s `renderPanel()` loops `DATA.buckets` and writes one row
per bucket as mark + Korean label + `r.counts[b.key]`, so the region panel shows **◆ 예산 초과 2** for
`uiseong_andong_2025` — which is `DATA.default_region`, so it is the first panel a judge sees — and **3** for
`uljin_samcheok_2022`; the bucket is a map legend entry too. `5bcfe11` had qualified exactly those two counts
six hours earlier on `README.md:145-149` and `docs/multi_region.md` §3.1. The screen says nothing: 예산
appears on **one** line of the file (`:434`, inside the data payload, as the label), and the 알려진 한계
panel's **ten** `rel(...)` cards (`:2067, 2071, 2076, 2080, 2084, 2088, 2092, 2108, 2112, 2116`) contain no
card about the budget rule. **The gate written to keep the correction honest cannot see the screen:**
`tests/test_budget_rule_asymmetry_is_stated.py:63-64` grades `docs/multi_region.md` and `README.md` and
nothing else. This is critic #53's fifth-surface shape, one window later, on the same surface.
⚠ **Do not change the number.** `mr_uiseong_fa_exceeds_budget` is 2, registered, and NH-031 option A says
nothing committed moves; the registry half is **WFG-122** and is still `todo`. Add the caveat to
`scripts/finals.template.html` **and not only to the built `web/finals.html`** — that is WFG-109's lesson —
then rebuild, re-point `release/kcf-finals-2026/MANIFEST.json`, and extend the test to a third surface.

**2. WFG-226 (P0) — card Q38 is stale, and it is on the paper in the booth kit.**
`docs/auto/JUDGE_QA.md:1421` still opens 「**아닙니다. 그리고 오늘 저장소는 이 질문에 두 가지로 답합니다 —
그게 결함입니다.**」 and attributes to `docs/multi_region.md:191` the uncaveated reading. Both halves are
false at this head: `:191` now reads 「asserted in `tests/test_partition_categories.py`」 and the ⚠⚠ asymmetry
block starts at `:195`. **The card's substantive answer is still right** — different rules, bucket empty
under one rule, 624.8 and 628.2 minutes, do not extend it to Uljin-Samcheok's 3 — so this is a re-framing
that should now credit the fix, not a rewrite. ⚠ A bank edit **without** `make printables` at a new stamp
plus a re-pointed bundle manifest takes `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree`
red (NH-049).

## `Do NOT edit` notes — one re-stated after re-checking, one DELETED because it was false

CHARTER §14c: such a note names the exact lines and the measurement behind it, and expires at the next
critic lap unless that lap re-states it after re-checking. Both are handled here, and one of them is deleted.

**RE-STATED, re-measured at this head. Do not put a margin value (9, 27, 5, 19, 86) anywhere in the README's
Round-4 section 1 while NH-032, NH-034 and NH-052 are open.** ⚠ **The bounds moved again this window, for the
third window running.** Measured by the two section headers rather than copied: 「### 1. 가장 강한 주장에
「공정한 상대」를 세웠습니다」 opens the block and 「### 2. 철회한 주장이…」 closes it, and that pair sits at
**`:263-342`** at `7dabdef`, **`:270-349`** at `9b7d21c` and **`:274-353`** at `16e6824`. The single
「구체적인 margin 값들은 부스에서 말하지 않습니다」 line is at **`:340`**. **Anchor on the two headers, not on
the digits** — three consecutive laps have now had to re-measure this, and a lap that copies an earlier pair
protects the wrong lines.

**DELETED, and the deletion is this lap's most important finding about the loop itself.** Critic #56 wrote,
on DIRECTION and again in the WFG-215 row in capitals: 「Do not print a per-slice `obs_time_min` … only the
headline `og_yeongdeok_obs_time_min` is registered … the row's own 「Do」 is wrong in one clause and a lap must
not follow it literally.」 **That was false.** The `0703Z` dev lap obeyed it and shipped a first draft of
`docs/oracle_gap.md` §4 that **withheld its own evidence, in prose, on a judge-facing page**, on the stated
ground that the numbers were unregisterable. Its independent reviewer blocked on exactly that; the lap
registered the five keys additively rather than arguing. Re-checked here in one process:
`grep -o 'og_yeongdeok_t[0-9]*min_obs_time_min' docs/NUMBERS.json | sort -u` returns **five** keys.
I re-checked, it is false, so it is **gone rather than re-stated**, and the instance is appended to NH-036,
which is the author's question about exactly this mechanism. **The lesson for the next dev lap:** a
`Do NOT` note from a critic is a claim, not an instruction, and the thing that caught this one was
`LOOP_CONFIG.json` → `review: subagent`, not any gate. Keep the reviewer on.

## What this lap verified and found clean

- **`gates.py --mode full` exits 0 at `16e6824`** — **1985 passed**, 64 skipped, 3 xfailed, pytest 482.0 s,
  **up 27 tests in one window**. `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts,
  which is NH-029 and CHARTER §3d working as designed.
- **GitHub `auto-gates`, runs 278 to 321: 44 runs, 36 `success`, 8 `cancelled` (278, 284, 306, 310, 312,
  316, 317, 320 — each superseded by the next push within minutes) and ZERO `failure`**, with run **321
  green at this exact head**. CHARTER §4b sets **no finding #1** for the sixth consecutive lap.
- **All eight** dev reports in the window record `Reviewed by:`, all eight name `subagent`, and **seven of
  the eight record `block`** and spend commits acting on it; the eighth (1928Z) records `pass`.
- **The printed kit's seven sources hash equal to the tree, seven of seven** — which is how WFG-226 was
  proved rather than guessed.
- **`factchk` on the window's new prose about the world: nothing to correct.** The window adds no new
  citation and no new external URL to any judge-facing surface; the URLs the diff appears to add are
  re-emitted lines of the twice-rebuilt `web/finals.html` and record-class pages under `docs/auto/`.
- **The window's strongest new claim survives attack.** 「`haz_stack` is a leave-one-fire-out output」 now
  stands on the README TL;DR, the finals screen's first limits card, JUDGE_QA Q36 at T0 and the manuscript.
  I traced it to the code rather than the prose and it holds at `build_canonical_hazard.py:130`. Only the
  pointer is wrong, which is the preemption above.

## Direction

**ZERO §3b reorders — the first critic lap of the sprint to spend none.** The two rows a dev lap should meet
first are rows this lap filed, and a newly filed row is not a move. They are filed **in the table like any
other P0 row, not at position 1**, because NH-051 is open and 「position 1」 is NH-038 option **D**'s mechanic
while this routine's prompt cites option **B**. `docs/auto/DIRECTION.md` names them instead, which is
CHARTER §14's own mechanism and is undone by deleting two paragraphs.

**Readiness: 8 of 11, ZERO ticked, fourteenth consecutive critic lap.** R3 is `blocked(NH-046)`, **NH-046
came due 2026-09-10 and is open**, and R3 is now the only unticked line of the six that gate the P1 infra
block. R12 is the author's.

⚠ **The open-decision count the loop has been reporting is wrong, and this lap counted rather than inherited
it.** The `0703Z` dev report says 「Twenty DECISION entries stay open, **six** of them at or past their stated
date」, and critic #56 carried the same six. Counted at `16e6824` with
`grep -oE '^## NH-[0-9]+ · [A-Z]+ · open'`: **19 DECISION + 1 BLOCKER = 20 open** for the author (plus 5
FYI), which matches. But **13**, not six, are at or past their stated date: NH-032, 034 and 045 were due
09-08; NH-035, 038, 043 and 044 were due 09-09; NH-036, 037, 042, 046, 048 and 050 were due **today**. The
「six」 is a hand-written number beside a generated block, which is the WFG-107 shape. Say 13.

**Scorecard: Track B 94 → 95, Track A 94 HELD.** 설계와 방법론 UP to 20 on both tracks (critic #56's own
pre-registration, paid on the condition it stated); 데이터 수집·분석·해석 UP to 20 on Track B (WFG-215 closed
both halves); 제출 자료 DOWN on both tracks, on the three defects above.
