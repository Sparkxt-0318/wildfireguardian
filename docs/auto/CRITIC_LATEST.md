# Critic #65 — 2026-09-11T0810Z, reviewed `f7ee58d`

**The next dev lap reads this file first.** Window `6d4a60b..f7ee58d` (the 24 h window; `6d4a60b`
is this shallow clone's oldest resolvable commit, so it is the base rather than a chosen one):
two dev laps that closed **five** P0 rows (WFG-247, WFG-248, WFG-249, WFG-250, WFG-251), one
research lap, two paper laps, two board rebuilds after rebases and three report-header fixes.
The printed kit was rebuilt **twice** and the bundle re-pointed both times. `docs/NUMBERS.json`
gained keys additively. No model, no refit, no regenerated artifact.

**Everything critic #64 asked for was done.** Its item 1 was 「ONE lap takes WFG-249 + WFG-250 +
WFG-251 and pays `make printables` ONCE」 and the 2026-09-11T0620Z lap did exactly that, in one
lap, with one rebuild, and the repairs are correct. This lap's findings are new defects, not
unpaid ones.

---

## `fix-before-next-row`: ONE, and it is one clause plus the 17-second rebuild

⚠⚠ **`docs/auto/JUDGE_QA.md:1513` — Q36, tier T0, said from memory to all five judges and
printed on page 25 of the 59-page kit — tells a judge the null circle is placed 「발화점에」.
The ignition point this project records is 19.20 km from that circle's centre, and no circle
the measurement drew contains it.**

Fix the 부스에서 할 말 clause to say what the centre actually is — the centroid of the `t = 0`
detection seed, which is what the same card's analytic block already says correctly two
paragraphs above — then `make printables` at a new stamp and re-point
`release/kcf-finals-2026/MANIFEST.json`. That is the Q&A half of **WFG-254**. Then take the
rest of WFG-254 in the same lap if the clock allows; it is six more one-clause edits and one
replacement figure.

⚠ **Critic #64 ruled that findings on hashed kit sources are 「un-preemptable」, and that reading
is wrong.** NH-049 asks whether the **critic** may write the bank. It says nothing about the
**dev lap** that executes a `fix-before-next-row` item, and the 0620Z lap closed three
bank-and-script rows plus the rebuild inside one lap. CHARTER §14b's test is the size of the
fix. This one is a clause and 17 seconds.

---

## Finding 1 — WFG-254 (P0, KCF, filed at position 1). The null is not at the ignition point

**Measured in this lap's own process, read-only, from `data/processed/routing_demo_canonical.npz`.**

- That array carries `ign_xy` = (1138940.54, 1826944.63) beside `grid_extent` =
  (1126514.93, 1789870.46, 1204514.93, 1880370.46, 500.0), on the canonical 181×156 grid.
- `scripts/measure_disc_null.py` **never reads `ign_xy`**, and it is right not to:
  `data/processed/disc_null_yeongdeok.json` → `null_rule.centre_from` states the rule correctly
  as 「centroid of the t=0 seed」. That centroid is grid **(97.775, 55.120)**.
- Mapping `ign_xy` onto the grid gives column **24.85** and row **74.15** or **106.85** depending
  on which edge row 0 sits at. **The data settles it:** only **(74, 25)** is burning at `t = 0`
  (`obs_stack[0] > 0`, and it is one of the 249 seed cells); (107, 25) is not observed at any
  slice. So the recorded ignition point is **38.40 cells = 19.20 km** from the disc's centre.
- ⚠ **The finding does not depend on that convention.** The other candidate is still **31.60
  cells = 15.80 km**, while the **largest** disc drawn at any of the five slices has radius
  **18.162** cells (9.08 km) and the headline slice's has **17.355** (8.68 km). **No disc at any
  slice contains the recorded ignition point**, and the headline disc's centre is more than
  twice its own radius from it.
- ⚠ **And 「발화점」 is not loose speech, because the seed is not a point.** The 249 cells both
  stacks agree on at `t = 0` are **226 connected components** (8-connectivity, largest **3**
  cells), bounding box **23.5 km × 44.5 km**, mean distance from their own centroid **23.2 cells
  (11.6 km)**. There is no ignition point in that mask to be near.
- `docs/submission_reconciliation.md:63` uses 발화점 elsewhere to mean the real ignition
  (「정본은 실제 발화점에서 다시 모사한」), which is exactly why a judge reads the two as the
  same place. **Do not touch that line; it is correct.**

**The seven surfaces.** `docs/auto/JUDGE_QA.md:1513` (Q36, T0, printed); `docs/disc_null.md:221`
(spoken draft); `docs/oracle_gap.md:203` (「centred on the ignition」, the page the README sends a
judge to); `paper/manuscript.md:710` (「an equal-area disc **at the ignition**」);
`paper/README.md:1052` (quoting it); and ⚠⚠ **`paper/make_figures.py:873`, which renders the bar
group heading 「distance moved from the ignition」 over `seed_to_observed_m` (1,124.8 m) and
`seed_to_model_m` (3,646.1 m) — both measured from the seed centroid — into
`paper/figures/F10_disc_null.png`, committed at `938dff7` in this window.** That figure is not
yet referenced by the manuscript, which lowers its reach and not its wrongness.

⚠ **A second clause, ambiguous rather than false.** Q36 says 「모델이 원판을 이긴 것은 **모양과
범위**」, and `docs/disc_null.md:152`, `docs/oracle_gap.md:211`, `paper/manuscript.md:710`,
`paper/README.md:894`, `paper/GAPS.md:100` and `:341` say 「shape and extent」. Both masks hold
**952** cells at the headline slice and `docs/disc_null.md` §2 says the area is 「handed over from
the model」, so on the **area** reading the claim is impossible. On the **reach** reading it is
true and measurable: the model's core spreads its 952 cells across a 44.5 km-wide box in 37
components while the disc packs the same 952 into a circle 17.4 km across. Disambiguate; do not
delete.

**Constraints.** CHARTER §3 rule 2 forbids regenerating `paper/figures/F10_disc_null.png` — the
corrected figure takes a **new filename** and the old one keeps a dated note saying what its
heading got wrong. Change **no measured value**; none of them is wrong. Do **not** weaken
`docs/disc_null.md` §4's centroid finding, which survives the relabelling unchanged.

## Finding 2 — WFG-255 (P0, science, position 2). The graded object's geometry is unstated

Measured here, 8-connectivity, same array and grid: the `t = 0` observation is **249 cells in 226
components** (largest 3); the **333-minute** observation that produces IoU 0.394 is **937 cells in
55 components** (largest **656**, second **135**), bounding box **24.5 km × 45.0 km**; the
360-minute forecast core is **952 cells in 37 components** over the same box; the cumulative stack
stays at 55 or 56 components at every later slice, adding only **86** cells between 333 and 2403
minutes.

**No file in this repository says any of this.** A search for component / 연결 성분 / disconnected
across `docs/`, `paper/` and `README.md` returns nothing about this array. Meanwhile
`docs/disc_null.md:153` tells a judge the model 「puts cells along the **arms the fire actually ran
down**」, and `docs/oracle_gap.md` §4's centroid argument turns on how far 「the fire」 moved. Both
read the mask as one advancing fire. A judge who is a disaster-response official asks 「이 마스크
안에 산불이 몇 개입니까」 in the first minute and gets no answer from any file.

⚠ **The row asserts the geometry, not a conclusion about it.** It does **not** claim the mask is
several fires: the 2025 경북 event was a multi-fire complex and FIRMS gaps also fragment a single
perimeter, and this repository cannot presently tell those apart. That is why the number belongs
on the page before the interpretation does. **Do not write 「여러 개의 산불」, or any count of
fires, from this measurement alone.**

## Finding 3 — the direction pre-registration fired, and the honest reading is split

Critic #64 pre-registered: 「if a dev lap ran in the next window and WFG-129 is still `todo`, that
is finding #1 and it is about the loop's direction」. **Two dev laps ran and WFG-129 is still
`todo`.** But both took critic #64's own item 1 and closed all three of its rows, so the cause is
**the page's ordering**, not the laps' choice, and this lap will not score a lap for obeying the
page it was told to obey. **WFG-129 is item 2 on `docs/auto/DIRECTION.md` now, behind one row
only.** ⚠ **Pre-registered for critic #66, with teeth: if TWO dev laps have run and WFG-129 is
still `todo`, that is finding #1 and critic #66 spends its one §3b row move putting WFG-129 at
table position 1.**

## Finding 4 — WFG-238 has a third live instance, repaired by hand here

`docs/auto/KCF_READINESS.md`'s lead was **two** laps stale: it named 「critic #62 … NINETEENTH」
while critic #63 (`f48876a`) and critic #64 (`0a66c90`) had each appended a section, both at the
bottom of the file. ⚠ The same two laps split the file's ordering convention — #58 to #62 are
newest-first under the lead, #63 onward are appended newest-last. This lap repaired the lead in
the same commit as its own append and **moved nothing**, because moving a section invalidates
every line citation made against it (the WFG-107 shape, seventh instance). Appended to **WFG-238**
rather than filed again. This is loop hygiene, P1, held by CHARTER §14b behind R3.

---

## What this lap verified and found clean

- **Gates.** `gates.py --mode full` exits **0** on its FIRST run in this sandbox: 2097 passed, 65
  skipped, 3 xfailed, pytest 493.5 s. `baseline-verify` WARNs on the two git-ignored
  `data/raw/**` contracts, which is NH-029 and CHARTER §3d working as decided. `--assert-head`
  exits 0; `--assert-reported --base 6d4a60b` exits 0 over **70** substantive paths.
- **GitHub's own runs (CHARTER §4b).** Runs **348 to 364** on `auto/dev` cover the window: **zero
  `failure`**, one `cancelled` (352, superseded by the next push), and run **364** is `success` at
  exactly `f7ee58d`. **No CHARTER §4b finding #1, for the fourteenth consecutive lap.**
- **Report certification.** Every dev report in the window records `Reviewed by:` — two `pass`,
  two `block` that the laps then fixed. The research report carries none, by design.
- **The hand-over objects.** Kit `manifest_20260911T0706Z.json` hashes **7 of 7** sources equal to
  the working tree; `release/kcf-finals-2026/MANIFEST.json` hashes **19 of 19** entries equal to
  their `source` paths and names the newest kit. 59 pages.
- **The five closed rows are correct repairs.** WFG-249 scopes Q20a to the 구조 · 경로 계층 and
  names the other population in the same block; WFG-250 replaces the population with the actual
  denominator (`l0i_failing_denominator_h240` **24**, not the **124**-building population) and the
  registry's own caveat says the two agreeing with `l0i_best_pair_saved` is a coincidence rather
  than a derivation, which is the right thing to have written; WFG-251 narrows Q16d to 「공개된
  기록과 초록」 with 「본문 PDF 는 저희가 열지 못했으므로」 beside it.
- **`factchk`.** ⚠ This lap could **not** reach the Zenodo API from the sandbox (the request
  returned no JSON), so it does **not** restate critic #64's verification of the Bokade record as
  its own. Nothing in this lap rests on it, and the WFG-251 repair above is the safe form whether
  or not a lap can reach the record.
- **Judge drill.** Q36 is where this lap's finding 1 came from. The three other hardest cards
  checked against files — Q16d (record-and-abstract scope), Q20a (household definition) and Q19
  (two populations) — all answer from a file at this head.

## The shallow clone

`git rev-parse --is-shallow-repository` answers **true** and the clone holds **50** commits,
measured in this lap. **No ancestry or reachability claim is written anywhere in this lap's
output.** ⚠ **Do NOT `git fetch --unshallow`, and CHARTER §4 does not ask you to.** It drags in
eleven side branches, lengthens `git`'s abbreviation and turns `tests/test_timeline_roles.py`'s
history check RED on a tree that is fine; critics #60 and #63 both paid for it. The cost of not
deepening, stated: in a shallow clone that check **SKIPS** rather than runs
(`tests/test_timeline_roles.py:234`), so a green critic gate does not certify it. GitHub at
`fetch-depth: 0` does, and run 364 is green. Recorded on **WFG-217**; this note names those file
lines and that measurement and **expires at critic #66** unless that lap re-runs the case.

## `Do NOT edit` notes written by this lap (CHARTER §14c, NH-036 A)

**ONE, and it names its lines and its measurement.** It covers **`docs/submission_reconciliation.md:63`**,
the sentence 「정본은 실제 발화점에서 다시 모사한 `routing_demo_canonical.npz`이고 414 / 42 / 2입니다」.
It forbids exactly one thing: changing or removing that line's 발화점 while WFG-254 is open. The
measurement behind it is the one in finding 1 — that 발화점 there refers to how the canonical array
was **seeded**, which the array's own `ign_xy` supports, and is a different object from the null's
centre. A lap sweeping 발화점 out of the seven WFG-254 surfaces will meet this line and must leave
it alone. It freezes no file and no question: every other 발화점 in the repository is in scope.
**It expires at critic #66 unless that lap re-states it after re-reading the line.**
