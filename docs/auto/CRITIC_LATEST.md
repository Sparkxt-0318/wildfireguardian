# Critic #66 — 2026-09-11T1125Z, reviewed `d67de57`, ships at `c241904`

**The next dev lap reads this file first.** Window `ba76b8c..d67de57`. `ba76b8c` is this shallow
clone's oldest resolvable commit (2026-09-10T12:45Z, 22 h 15 m back), so it is the base rather than
a chosen one; critic #65's base `6d4a60b` no longer resolves here, which is the clone-depth fact
CHARTER §4 warns about and not a history change. Counted from the reports added in the range: **six
finished dev laps**, seven critic laps, four paper laps (filed `--kind manual`, because `report.py`
has no `paper` choice) and one research lap. Two board rebuilds after rebases, four report-header
fixes, the printed kit rebuilt twice. `docs/NUMBERS.json` gained keys additively. No model, no
refit, no regenerated artifact.

⚠⚠ **CORRECTED MID-LAP, AND THE CORRECTION IS THE FIRST THING THIS FILE SHOULD SAY.** This lap
reviewed `d67de57`, where **WFG-254 was `in-progress(20260911T0921Z)` with only its claim commit
pushed**, and it wrote its item and its scores on that state. The lap holding WFG-254 then pushed
`05d3bb3` while this lap was writing, and **WFG-254 is now `done(20260911T0921Z)`**. Everything below
was **re-measured at the rebased head before this file was finished**, not inferred from the report:

- **All eight surfaces now name the `t = 0` seed centroid.** `발화점` answers **0** in the Q36 cell,
  `모양과 범위` answers **0** across `docs/auto/JUDGE_QA.md`, `docs/disc_null.md` and
  `docs/oracle_gap.md`, and the three remaining `발화점` hits in `docs/disc_null.md` are the
  `forbidden-ok` record line and the two paragraphs explaining the word. `docs/oracle_gap.md:208`
  carries a dated 〔정정〕 rather than a silent edit.
- **The kit was rebuilt and the bundle re-pointed.** `WFG_printables_20260911T0939Z.pdf`, 59 pages,
  its seven sources re-hashed here at **7 of 7**, and `release/kcf-finals-2026/MANIFEST.json` names
  that kit and its manifest.
- **The row went further than it was asked to**, finding an eighth surface in `paper/GAPS.md`,
  turning the measurement into an artifact (`scripts/measure_disc_centre_vs_ignition.py`), and
  registering four spellings as `WC-017`.

**So critic #65's item is PAID, and this lap's item is a different clause on the same card.**

---

## `fix-before-next-row`: ONE, it is NEW, and it is one clause plus the rebuild

⚠⚠ **`docs/auto/JUDGE_QA.md:1513` (Q36, tier T0) and `docs/disc_null.md:225` both still close on
「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」, and nothing in this repository has measured
the 「모양」 half.** On the card it is the last thing the student says about the comparison, in the
부스에서 할 말 block, from memory, to all five judges, and it is on page 25 of the kit rebuilt
**40 minutes ago**.

**WFG-254 did not touch it, and that is not a criticism of WFG-254.** That row was asked to
disambiguate the **area versus reach** axis and it did exactly that: Q36's analytic block now reads
「모델이 원판을 이긴 축은 **모양과 뻗은 거리**이고(면적은 원판이 구조상 똑같이 맞춰 오므로
겨룰 축이 아닙니다)」, which is right, is measurable, and is not re-opened here. **What it left
standing is 「모양」 as an axis the model is said to have WON.** The card is now correct about where
the disc sits and still unsupported about why the model beats it.

**The fix is one clause, on the two lines above, in the same `make printables` shape the last lap
just paid twice.** Say what the artifact supports and stop at it: the model overlaps the burn better
than the area-matched disc, the centre of mass says that is not direction, and **which axis it is has
not been measured**. A form that costs nothing and is true: replace
「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」 with
「저희가 나은 것은 겹침이고, 방향은 아닙니다 — 그것이 모양 때문인지는 아직 재지 않았습니다」.
Then `make printables` at a new stamp and re-point `release/kcf-finals-2026/MANIFEST.json`.

⚠ **This is the Q&A half of WFG-256 and it does not wait for the experiment.** The experiment may
later license a stronger sentence; until it runs, the card must not claim the answer. ⚠ Do **not**
weaken 「방향은 아닙니다」: that half **is** measured, by the `direction` block, and it is the card's
strongest move.

## Finding 1 — WFG-256 (P0, science, filed at table position 3). The card claims the half of the comparison the artifact declines to attribute

**Measured in this lap's own process, read-only, at `d67de57`.**

- `docs/disc_null.md:225` (the spoken draft) and `docs/auto/JUDGE_QA.md:1513` (Q36, **T0**) both close
  on 「저희가 잘하는 것은 방향이 아니라 불의 모양입니다」. Q36 states the same attribution again as
  「모델이 원판을 이긴 것은 모양과 범위이고」. The card tells the student to volunteer it
  「심사위원이 캐내기 전에 먼저」.
- **The artifact refuses that attribution in its own words.**
  `data/processed/disc_null_yeongdeok.json :: what_this_is_not` reads 「The gap between the model's
  IoU and the disc's is **joint PLACEMENT-AND-SHAPE skill**, not directional skill alone, because a
  disc differs from the model's core both in where its mass sits and in being a circle rather than an
  irregular terrain-shaped blob」. `docs/disc_null.md` §5.1 adds that a circle against an elongated
  fire is a weak opponent **by construction**.
- So the IoU gap is a two-component quantity. The `direction` block prices one component and it goes
  <!-- collision-ok: 5.34 — dn_yeongdeok_model_to_observed_cells, the MODEL's centroid error. The registry's 2.25 under a similar anchor set is dn_yeongdeok_seed_to_observed_cells, how far the OBSERVED centroid moved, which is a different quantity. -->
  the wrong way for the model: `dn_yeongdeok_model_to_observed_cells` **5.34** against the stationary
  <!-- collision-ok: 2.266 — dn_yeongdeok_disc_to_observed_cells, the DISC's centroid error in cells. The registered dn_yeongdeok_*_disc_radius_cells values (8.913, 14.881, 17.355, 17.681, 18.162) are per-slice RADII, a different quantity, not stale values. -->
  disc's `dn_yeongdeok_disc_to_observed_cells` **2.266**. The card then attributes the **entire
  remainder** to 「모양」. That is the forbidden single-component move mirrored: the artifact declines
  to attribute the gap to direction alone, and the card attributes it to shape alone.
- ⚠ **Nothing in this repository measures the shape component.** Searched here across `docs/`,
  `paper/`, `scripts/` and `src/` for a shape-matched, second-moment, principal-axis or rotated null:
  the only hit is `scripts/direction_drivers.py:31`, gradient covariance on a different object.
  `run_isotropic_baseline` **is** this disc once the area match removes its rate parameter;
  `run_persistence_baseline` is **WFG-234**; neither separates shape from placement.
- ⚠ **The headline slice is NOT cherry-picked, and this lap checked rather than assumed.** The
  seed-removed ratio is 1.9538 / 2.2044 / 2.2335 / 2.2286 across the four non-seed slices and the
  headline slice (haz 360, obs 333) is the smallest time gap at 27 min, fixed in the claim commit
  before the answer. The model's own IoU is slightly **higher** at t=540 and t=720 than at the
  headline. Selection is not the defect here; attribution is.

**The cheapest test, and it is why this is a row rather than a complaint.** Rotate the model's **own**
predicted core rigidly about the `t = 0` seed centroid (grid 97.775, 55.120) through a pre-registered
angle sweep and re-score against the same `obs_stack` slice under the same rule. Shape, area and cell
count are the model's own by construction; only orientation about the fire's own start varies. The
spread of rotated IoUs is the **shape-controlled** null for placement, and the model's rank within it
is the number the card is missing. Zero free parameters, one committed npz, no refit. Pre-register the
interpretation in the claim commit and publish it either way: if the rotated cores score near
<!-- collision-ok: 0.2577 2.2 — 0.2577 is dn_yeongdeok_bare_model_iou, the HEADLINE slice's seed-removed model IoU; the other registered *_model_iou and *_bare_* values are OTHER SLICES, not stale values. 2.2 is the rounded seed-removed RATIO dn_yeongdeok_bare_iou_ratio 2.2044 and is not an IoU. -->
`dn_yeongdeok_bare_model_iou` **0.2577**, the 2.2x measures irregularity and not skill, and the clause
comes off the card.

⚠ **Constraints on the row:** do not rotate about the grid centre or the observed centroid; do not
report a p-value (12 or 24 rotations of one fire is a reference spread, not a test); do not touch any
committed number. Full row text in `docs/auto/BACKLOG.md`.

---

## Finding 2 — WFG-257 (P1, KCF, appended at the end of the table). The demo pays for every caveat out of its own core

**Read from the six committed artifacts in `data/processed/demo_script_pace/` and the allocation table
in `docs/demo_script_pace.md` §3.**

| what | at `039a0de` | now (`pace_20260911T0620Z.json`) | change |
|---|---:|---:|---:|
| total spoken syllables | 1,684 | **1,799** | +115 (+6.8 %) |
| implied rate, syl/s at a fixed 300 s | 5.61 | **6.00** | +7 % |
| 3막 · 같은 출발지, 두 개의 답 | 75 s | **58 s** | **-23 %** |
| 마무리 · 한계 | 45 s | **64 s** | **+42 %** |
| 마무리 syllables | 328 | **383** | +55 |

⚠⚠ **마무리 is now the longest segment of the five-minute demo** (allocation 35 / 41 / 47 / 58 / 55 /
64). At `039a0de` it was the **shortest**, tied with 1막. And 3막, which `docs/demo_script_pace.md`
itself calls 「이 프로젝트의 전부」, lost 17 of its 75 seconds **without losing a word**: its spoken
text has been 346 syllables since 2026-09-05 (`pace_20260905T0947Z.json` and
`pace_20260911T0620Z.json` agree).

**What the page already says and what it does not.** It records the allocations, the four totals and
that the rate is rising on four consecutive measurements, and it prices 3막's loss once as 「what one
rate costs it」. It does **not** say that the transfer is monotone across five allocations, that the
segment losing the time has not lost a word, or that the limits segment is now the longest thing five
judges hear. Every one of the four growth events was a caveat added by a lap that was right to add it,
which is exactly why nobody has been able to see the total.

⚠ **The row adds no syllable and removes none.** Whether the proportion is right is the author's, and
it is the identical question NH-054 already asks about `README.md`'s TL;DR; a dated measured note was
appended there rather than opening a twenty-fifth entry.

---

## Finding 3 — WFG-252 confirmed and widened (P1, infra, updated in place, NOT re-filed)

**`docs/auto/SCORECARD.md` is the page whose whole job is to show direction between laps, and three
things are wrong with its newest entry.**

1. ⚠⚠ **Critic #65 appended BOTH of its rows to the Track A table, and neither to the Track B table
   nor to the series.** Measured at this head before any edit: the Track B table ended at `5482ba8`
   (line 167); the series table ended at `5482ba8` (line 90); and the Track A table held **two**
   `f7ee58d` rows (lines 235 and 236). **A reader of the Track A table therefore sees 구현 및 유용성
   fall to 19 and hold at 20 at the same head**, because Track B's 데이터 수집·분석·해석 cell lands
   in Track A's 구현 및 유용성 column. That is WFG-252's and WFG-184's subject, and critic #40
   measured the same failure class on 2026-09-08.
2. ⚠⚠ **The row also carries an unevidenced point.** Track B 연구 목적 reads **18** at `5482ba8`
   and **19** at `f7ee58d`, while that row's own narrative says 「연구 목적 19 ... all HELD」. No lap
   has published a reason for the raise, and it is what makes that row total **95** rather than 94.
3. **The published delta is measured against the wrong series.** Critic #65's report and
   `docs/auto/DIRECTION.md` both said 「Track B 97 to 95」. Track B's previous value was **96**; **97**
   is Track A's.

This lap **transcribed** the missing rows into the Track B table and the series rather than leaving
them, annotated as transcriptions, which is the practice critic #64 already used. The misplaced Track
A copy is left exactly where it is.

⚠ **No row another lap wrote was edited** (CHARTER §3.7). This lap scored 연구 목적 itself at **18**
with a reason rather than inheriting the 19, and named the discrepancy in its own row. WFG-252's
done-when gained one clause: the gate must also refuse a detail row whose cell differs from the
previous row for that track when the narrative does not name that criterion as moving.

---

## What is green, measured here and not read from a report

- `gates.py --mode full` exits **0** on its **first** run: 2097 passed, 65 skipped, 3 xfailed, pytest
  386.5 s. `baseline-verify` is the expected WARN (NH-029: new artifacts and a grown registry are
  information in a sandbox that cannot re-freeze).
- `gates.py --assert-reported --base ba76b8c` exits **0** over 68 substantive paths.
- **GitHub `auto-gates` run 369 is `success` at exactly `d67de57`**, and **no run in the 24-hour
  window concluded `failure`**: runs 344, 352 and 368 are `cancelled`, each superseded by the next
  push. CHARTER §4b therefore sets **no finding #1**, for the fifteenth consecutive lap.
- **Every dev report in the window records `Reviewed by:`** (ten checked, all `subagent`; the
  2026-09-11T0119Z lap's is bolded but present).
- The printed kit's seven sources hash **7 of 7** against the tree, and
  `release/kcf-finals-2026/MANIFEST.json` names the newest kit,
  `WFG_printables_20260911T0706Z.pdf`, 59 pages; **at the rebased head the kit is
  `WFG_printables_20260911T0939Z.pdf`, also 59 pages, also 7 of 7, with the bundle re-pointed to it.**
  ⚠ This lap did **not** independently re-derive the 19-file bundle tally and does not restate it;
  `tests/test_finals_bundle.py` is green inside the full gate run above.
- ⚠ **`gates.py --mode full` was run twice**: at `d67de57`, the head reviewed, and again on this lap's
  own commit after the rebase onto `05d3bb3`. Both exit 0. `--assert-head` and `--assert-reported`
  are run on the commit that is pushed, never on the one that was reviewed.
- ⚠ **One honest subtraction.** This clone is SHALLOW at **50** commits and was deliberately not
  deepened, so `tests/test_timeline_roles.py:234` **SKIPS** rather than runs and a green critic gate
  does not certify it. GitHub at `fetch-depth: 0` does. No ancestry or reachability claim is written
  anywhere in this lap.

## Your decisions, applied

**Nothing new arrived.** `docs/auto/decisions_seen.json` records `"seen": []`, the newest applied
decision is NH-031 of 2026-09-06, every thread matching the report subject in the last 14 days at the
Gmail connector carries exactly one message and every one of them is the loop's own send, and PR #31
returned an **empty comment list** at the GitHub MCP in this lap. ⚠ **The count is now 25, not 24:** the 0921Z lap filed **NH-058** in the same push that closed WFG-254, asking why the paper routine built a row the dev routine had already claimed on `origin`. It is the window's one new author question and it is not this lap's. **Five days, no reply, 25 open decisions and four
days of sprint left.** That is **WFG-211**, already `todo`, confirmed here and not re-filed.
