# What should IoU 0.394 be compared with?

**Row:** WFG-228 · **Method proposed by:** the loop (critic #58 filed the row, and
fixed the disc rule in it; the lap that ran it added the centroid reading in §5
after objecting to the row's own interpretation)
**Artifact:** `data/processed/disc_null_yeongdeok.json`
**Script:** `scripts/measure_disc_null.py` · **Registry:** the `dn_yeongdeok_` prefix
of `docs/NUMBERS.json` — count it there rather than here.

---

## 1. The question this answers

`docs/oracle_gap.md` §4 reports **IoU 0.394** between the forward-simulated core
and the observed footprint at the well-matched pair, and concludes that the model
「gets the size nearly exactly right and the place substantially wrong」. That
reading is now on `README.md`'s TL;DR, the finals screen's first 알려진 한계 card,
`docs/auto/JUDGE_QA.md` Q36 at tier T0 and `paper/manuscript.md`.

Until this document, **nothing in the repository said what 0.394 should be
compared with.** A judge who asks 「0.394는 무엇에 견준 값입니까?」 — and the
ML-reviewer and statistician lenses both ask it in the first minute — was being
handed a number with no scale. 0.394 could have been a criticism of the model or a
compliment to it and the repository could not say which.

## 2. The null, and why it has no free parameters

For each forward-simulation slice, an **area-matched disc**:

| choice | what it is | why it is not a free parameter |
|---|---|---|
| centre | the centroid of the `t = 0` seed | `obs_stack[0] > 0` and `haz_stack[0] >= 0.5` are the **same 249 cells** — the script asserts this and aborts if it ever stops being true — so the centre uses only what the two stacks already **share**. ⚠ It is not free of the observation: `obs_stack` is cumulative, so that seed sits *inside* the footprint being scored. §3c is where that is paid for |
| size | that slice's **own** predicted core count (692 / 952 / 981 / 1036) | the area is not chosen, it is **handed over** from the model. The one thing the model gets right is given to the null for free |
| membership | the N cells of smallest Euclidean distance from that centre | no radius is picked; N fixes it |
| ties | `(row, col)` ascending | makes the mask deterministic, nothing more |
| scoring | the **same** observed footprint, the **same** nearest-observation matching, the **same** `p_cut`, the **same** cumulative masks as `scripts/measure_oracle_gap.py` | the comparison is between two masks on one grader, not between two graders |

**The rule above and the interpretation below were written into the WFG-228 claim
commit `4ab2e07` before the script was run** (the WFG-201 discipline). The
pre-registration said: if the disc scores at or above 0.394, that is the finding
and it goes on this page in those words. It did not, and this page would have said
so if it had.

No refit, no re-acquisition, no fill rule, no threshold sweep. The script reads one
committed artifact and writes a new one.

### 2b. ⚠⚠ The centre is **not** the ignition point, and eight sentences said it was

〔정정 · 2026-09-11 · WFG-254〕 Until this date **eight** sentences across **seven** files
placed this disc **at the ignition point** — 「발화점에」, 「at the ignition」, <!-- forbidden-ok: wc017-disc-at-ignition-en -->
<!-- forbidden-ok: wc017-centred-on-ignition-en -->
「centred on the ignition」. They are enumerated rather than counted, because the count is
the thing a later lap will get wrong:

| # | where | why it reached a reader |
|---|---|---|
| 1 | `docs/auto/JUDGE_QA.md` Q36, the 부스에서 할 말 half | tier **T0** — said from memory to all five judges, and printed in the booth kit |
| 2 | this page's §6 spoken draft | the draft the student rehearses from |
| 3 | `docs/oracle_gap.md` §4c | the page `README.md` sends a judge to |
| 4 | `paper/manuscript.md` §6 | the manuscript's limitations section |
| 5 | `paper/README.md` quoting §6 | the paper routine's ledger |
| 6 | `paper/GAPS.md` quoting §6 | the same sentence again |
| 7 | `paper/GAPS.md`'s lap-30 record, 「an **area-matched disc** at the ignition」 | ⚠ **found only after the first sweep closed**, because the emphasis marker sits between the two words the English pattern anchored on | <!-- forbidden-ok: wc017-disc-at-ignition-en -->
| 8 | `paper/make_figures.py`'s bar-group heading | rendered into the committed `paper/figures/F10_disc_null.png` |

⚠ **Seven of the eight are now corrected in place; the eighth is a PNG and is not.** The
table above always said otherwise, and so does the artifact's own `null_rule.centre_from`.
The words were wrong; the null was not.

**How far apart the two places are**, measured by
`scripts/measure_disc_centre_vs_ignition.py` into
`data/processed/disc_null_centre_vs_ignition.json`:

| | |
|---|---|
| the centre the null used | grid `(97.7751, 55.1205)` — the `t = 0` seed centroid |
| the ignition the array records | `ign_xy` `(1138940.54, 1826944.63)` → grid cell `(74, 25)` |
| distance between them | `dnc_yeongdeok_seedcentre_to_ignition_cells` **38.3986** cells, `dnc_yeongdeok_seedcentre_to_ignition_m` **19199.3** m |
| the largest disc drawn at any slice | `dn_yeongdeok_t720min_disc_radius_cells` **18.162** cells | <!-- collision-ok: 18.162 — the key is named in the row: the 720-minute slice's radius, the largest of the five. The other registered radii (8.913, 14.881, 17.355, 17.681) are different slices of the same run, not stale values of this one. -->

So **no disc at any slice contains the recorded ignition point**, and the headline
slice's centre is more than twice its own radius away from it.

⚠ **The measurement does not assume a row convention.** `grid_extent` leaves row 0
ambiguous, and the two candidates put the ignition at `(74, 25)` or `(107, 25)`. The
observation settles it rather than the script: the recorded ignition must be burning
in the `t = 0` frame, and only `(74, 25)` is — `(107, 25)` is not observed at any
slice. Under the losing convention the gap is **31.6008** cells, still larger than
every disc radius above, so the finding survives the choice either way.

⚠⚠ **This is a correction to the WORDS and not to the null.** The centroid rule is
the honest one: it uses only what the two stacks share (the table above), whereas a
disc re-sited on `ign_xy` would be a different and worse null. And 「발화점」 was never
loose speech here, because **the `t = 0` seed is not a point** — it is a scatter of
`obs_stack[0] > 0` cells spread across the grid, so no single cell of it summarises
it. `docs/submission_reconciliation.md` §「정본」 uses 발화점 to mean the real ignition
the canonical array was **seeded from**, and that line is correct and untouched; it is
precisely why a judge reads the two as one place. The withdrawn spellings are
registered as **WC-017**.

## 3. Result

At the headline slice — forecast 360 min against the 333 min observation, the
**27-minute** pair `docs/oracle_gap.md` §4 already quotes, fixed before the run and
not re-chosen after:

| | forward simulation | area-matched disc |
|---|---:|---:|
| cells | **952** | **952** (matched by construction) |
| in both | **534** | **254** |
| predicted, did not burn | **418** | **698** |
| burned, not predicted | **403** | **683** |
| **IoU** | **0.3941** | **0.1554** |

**The model scores 2.536 times the null**, a gap of **0.2387** IoU. And it is not a
property of the quoted slice — every slice says the same thing:

| forecast time | `time_gap_min` | cells | model IoU | disc IoU | model − disc | model ÷ disc |
|---:|---:|---:|---:|---:|---:|---:|
| 180 min | 153 | 692 | 0.3586 | 0.1320 | 0.2266 | 2.7167 |
| **360 min** | **27** | **952** | **0.3941** | **0.1554** | **0.2387** | **2.5360** |
| 540 min | 207 | 981 | 0.3949 | 0.1547 | 0.2402 | 2.5527 |
| 720 min | 285 | 1036 | 0.3981 | 0.1606 | 0.2375 | 2.4788 |

⚠ The three badly-matched rows are still badly matched, and `docs/oracle_gap.md`
§4's warning applies here unchanged: 180, 360 and 540 are graded against the **same**
observation, so this is not four independent readings. What the column adds is that
the model-minus-disc gap is **stable across all four** — from **0.2266** to
**0.2402** — while the time gaps underneath them run from **27** to **285** minutes.
A quantity that barely moves while the thing contaminating it swings that far is the
more robust half of this table.

### 3b. The sanity anchor: the fire was never disc-shaped

At `t = 0` the disc is scored against the 249-cell seed both stacks agree on, and
gets **0.0803** — it recovers **74** of those 249 cells at the next slice and
**92** at the headline slice. The footprint this project is trying to predict is
irregular from the first frame, which is the whole reason a disc is a floor and not
a rival.

### 3c. ⚠⚠ The raw ratio is inflated, and this is the honest one

**The comparison above is not clean, and the defect was found by this row's
independent reviewer — not by the row, and not by the lap that ran it.**

`obs_stack` is **cumulative**. So the 249-cell `t = 0` seed is a **subset** of the
937-cell observation being scored, and the two masks do not meet it on equal terms:

- the **model's** core contains **all 249** seed cells at every slice — by
  construction, because they are its *initial condition*, not a prediction;
- the **disc**, being a circle, recovers only **92** of them at the headline slice.

So the model collects a free intersection of cells it never predicted, and the null
was never given the same gift. Removing the shared seed from **all three** masks —
model, disc and observation — is the comparison with that advantage taken away:

| headline slice | model | disc | ratio |
|---|---:|---:|---:|
| as scored above | 0.3941 | 0.1554 | **2.5360** |
| **shared seed removed** | **0.2577** | **0.1169** | **2.2044** |

| forecast time | model (seed removed) | disc (seed removed) | ratio |
|---:|---:|---:|---:|
| 180 min | 0.1905 | 0.0975 | **1.9538** |
| **360 min** | **0.2577** | **0.1169** | **2.2044** |
| 540 min | 0.2611 | 0.1169 | **2.2335** |
| 720 min | 0.2730 | 0.1225 | **2.2286** |

**The finding survives in sign at every slice, and its size drops by about a
fifth.** So the sentence this document adds to the project is the seed-removed one:
*the forecast's footprint overlaps the fire about 2.2 times better than a disc of
exactly the same area centred on where the fire started, once the shared starting
footprint is taken away from both.* **2.5360 is not quotable without 2.2044 beside
it**, and the caveat band on all 87 keys says so.

## 4. What the gap is NOT: the row's own interpretation, corrected

The WFG-228 row says the disc 「holds constant the one thing the model got right
(area) and destroys the one thing routing depends on (direction), so the difference
between the two IoUs is the model's directional skill and nothing else」.

**That is wrong, and the artifact contains the evidence against it.** A disc differs
from the model's core in **two** ways at once: where its mass sits (direction) *and*
that it is a circle rather than an irregular, terrain- and wind-shaped blob (shape).
The IoU gap is therefore **joint placement-and-shape skill**, and this comparison
alone cannot split it.

The centroid displacements can, and they say something the IoU gap hides:

| centre-of-mass distance, headline slice | cells | metres |
|---|---:|---:|
| seed → **observed** footprint | **2.250** | 1,124.8 |
| seed → **model** core | **7.292** | 3,646.1 |
| **model** → observed | **5.340** | 2,670.2 |
| **disc** → observed | **2.266** | 1,133.0 |

⚠⚠ **By centre of mass, the disc is closer to the truth than the model is.** The
observed footprint's centre of mass barely leaves the seed — **2.250** cells,
**1,124.8 m** — while the model's core centre of mass travels **7.292** cells,
**3,646.1 m**. The model **overshoots**. The disc, which by construction stays put,
ends up with a centre-of-mass error of **2.266** cells (**1,133.0 m**) against the
model's **5.340** (**2,670.2 m**).

So the model's advantage is **not** that it points in the right direction. On this
fire, at this slice, it points in a *worse* direction than doing nothing. Its
advantage is that it reproduces the **shape and reach** of an elongated, irregular
footprint — it puts cells along the arms the fire actually ran down — while a
compact circle covering the same area cannot, whatever its centre.

⚠ **「Reach」 and not 「extent」, and the word matters.** The null holds **area**
equal by construction: §2's rule sizes the disc from the model's own core count, so
at the headline slice both masks hold `dn_yeongdeok_n_cells` **952** cells. The
model therefore *cannot* win on area, and 「extent」 read as area is an impossible
claim rather than a wrong one. What it wins on is how far the mask spreads: the
model puts its 952 cells along the arms while the disc must pack the same 952 into
a circle of radius `dn_yeongdeok_disc_radius_cells` **17.355** cells. Where this <!-- collision-ok: 17.355 — the HEADLINE slice's own radius, which is the slice this sentence is about. The other registered radii (8.913, 14.881, 17.681, 18.162) are different slices of the same run, not stale values of this one. -->
document, `docs/oracle_gap.md`, the manuscript and the Q&A bank said 「shape and
extent」 before 2026-09-11 they meant this reach reading; the word was corrected and
the claim was not (WFG-254). ⚠ The geometry of the observed footprint itself — how
many disconnected pieces it is, and how wide a box they span — is **not** measured
in this repository yet; that is row WFG-255 and no sentence here assumes an answer.

The two masks are genuinely different objects and not one mask twice: disc against
model core is IoU **0.2453**.

**Both readings are true and they must travel together.** Quoting 「2.5 times the
null」 without the centroid row would tell a judge the model has directional skill
it does not have, which is the failure mode `docs/auto/withdrawn_claims.json`
exists to record. The registry band on all 52 `dn_yeongdeok_` keys carries the
centroid numbers for that reason.

## 5. What this does NOT show

1. **It is not a validation.** The disc is a **floor**, not a competitive baseline.
   A circle scored against an elongated fire is a weak opponent by construction, so
   clearing it is **necessary** and not **sufficient** evidence of skill. 「Better
   than the null」 here means only 「better than *this* null」. ⚠ **2026-09-12 (WFG-256):
   「a weak opponent by construction」 is no longer a qualitative claim, and the
   measurement qualifies it in a direction this page did not expect — the disc is
   a weak opponent only against the core *as oriented*, and a **stronger** opponent
   than **20** of 23 rotations of that same core. §5b has the numbers. Nothing in
   this item is withdrawn: necessary-and-not-sufficient stands.
2. **The strong nulls are not scored against *this* truth.** `src/wildfireguardian/validation/baselines.py`
   defines `run_persistence_baseline` (`:44`) and `run_isotropic_baseline` (`:68`)
   — the WFG-228 row dates them to 「Session 4」 and this page deliberately does not
   repeat that, because the only in-repo evidence is
   `docs/OVERNIGHT_REPORT_SESSION3.md:195` and **this clone is shallow (51 commits),
   so it cannot settle a history claim at all** (CHARTER §4). What is checkable here
   is that the two functions exist at those lines and are called. ⚠ **They are not
   unused** — `validation/harness.py:703-704`
   runs both and `compute_horizon_metrics` (`:496`) scores them with a **polygon**
   IoU (`perimeter_iou`, `:514`). But that is a different measurement from this one
   in both halves: it compares **polygons**, not 500 m raster masks on the canonical
   canvas, and it grades against `load_observed_perimeter_series`, which the harness
   itself labels 「APPROXIMATE, reconstructed from public reporting」 — not the
   FIRMS-derived `obs_stack` that produced 0.394. So the honest statement is narrow:
   **no persistence or isotropic null has been scored against the truth 0.394 is
   scored against**, and the two IoU families are not comparable as they stand. A
   persistence null is the one a fire scientist will ask for, and it is a harder
   opponent than a disc because it inherits the fire's real shape. That is filed as
   **WFG-234**, not done here.
3. **No margin, no route, no committed number moves.** 42, 91, 9 and 27 are
   untouched. Nothing here was routed; this is two masks against a third.
4. **`obs_stack` is not ground truth.** It is a FIRMS-derived observation with its
   own detection floor (`docs/detection_floor.md`) and 500 m resampling. A 「missed」
   cell may be a cell FIRMS did not see, and the same caveat applies to the disc's
   misses and the model's equally — which is one reason the *comparison* survives it
   better than either number alone does.
5. **One fire, one canvas, one threshold.** 영덕 2025 on the canonical 181×156 grid
   at `p_cut = 0.5`. Nothing here is a claim about 의성·안동 or 울진·삼척.
6. **The disc is not clipped, and that was checked rather than assumed.** Neither
   the disc nor the model core touches a grid border at any of the five slices, so
   the rule executed as written. Each slice's disc radius is registered separately,
   and the largest of the five is
   <!-- collision-ok: 18.162 — dn_yeongdeok_t720min_disc_radius_cells, the LARGEST slice's radius, which is what this sentence claims. The other registered radii (headline 17.355, t540 17.681) are different slices, not stale values; test_every_radius_the_doc_quotes_is_the_slice_it_names binds this line to max(). -->
   **18.162** cells against a 181×156 canvas, at `t = 720`. An earlier draft of this
   page quoted that figure while registering only the *headline* slice's 17.355, and
   `make verify`'s collision gate refused it — correctly.
7. **The null is not perfectly clean, and §3c is the price.** The centre is derived
   from a seed that is *inside* the cumulative observation being scored, and the
   model contains that seed by construction while the disc does not. The
   seed-removed figures (ratio **2.2044**, not 2.5360) are the fair ones and both
   are published. A null that had to be sited *without* any shared information
   would need a centre chosen from something other than the fire's own first frame,
   and there is no such thing in this artifact.


### 5b. ⚠ How much of the gap is bought by not being a circle: measured (WFG-256)

Item 1 above and §5.1's 「weak opponent by construction」 were, until 2026-09-12, the
page's own words for something it had not measured. The rotation null measures it.

The rule, pre-registered in the WFG-256 claim commit before the script existed: hold
the model's **own** shape and cell count fixed, rotate that mask rigidly about the
**same** `t = 0` seed centroid this disc uses, through every **15** degrees with 0
excluded (**23** rotations), and score each one against the same observation under
the same matching and the same `p_cut`, with the scorer **imported** from
`scripts/measure_disc_null.py` rather than copied. Seed removed, at the headline
slice:

| | seed-removed IoU |
|---|---|
| the core **as oriented** | **0.2577** |
| the **best** of the 23 rotations | **0.1359** |
| the **median** of the 23 rotations | **0.0746** |
| the **worst** of the 23 rotations | **0.0387** |
| this **disc** | **0.1169** |

Two results, and the second is the one that refines item 1:

1. **The true orientation ranks 1 of 24, with 0 ties, at all four off-seed
   slices.** So the overlap is not produced by the core's irregularity, nor by its
   being anchored at the seed: rotate the identical mask and the IoU falls to
   **0.1359** at best.
2. **Only 3 of the 23 rotations beat this disc, and the worst reaches 0.3311 of
   it.** A misoriented version of the model's own irregular, terrain-shaped mask is
   a **worse** opponent than a circle, twenty times out of twenty-three. So the
   2.2044 is not bought by 「원이 아니라서」; it is bought by that shape being at
   **that** angle.

⚠ **This licenses no directional claim, and §4 above is unchanged.** The model's
centre of mass still ends up farther from the observation (**5.34** cells) than this
stationary disc's does (**2.266**), and 「저희가 나은 것은 겹침이고, 방향은 아닙니다」
stays exactly as written. The two readings are consistent: **the axis is right and
the distance along it is overrun.** Method, the rasterisation residual, the
lattice-exact controls and the full list of what it does not show are in
[`docs/rotation_null.md`](rotation_null.md); it reports **no p-value**, because 23
rotations of one fire is a reference spread and not a test.

## 6. What a judge should hear

Short, and in this order, because the second sentence is what keeps the first
honest:

> 「0.394가 좋은 값인지 나쁜 값인지 견줄 대상을 만들었습니다. 같은 면적의 원을
> `t = 0` 씨앗의 무게중심에 놓고 같은 방식으로 채점하면 0.155입니다. 다만 두 마스크가 처음 불씨
> 249칸을 똑같이 물려받기 때문에, 그 부분을 양쪽에서 빼고 다시 재면 0.2577 대
> 0.1169, 약 2.2배입니다 — 저희가 인용하는 값은 이쪽입니다. 그리고 무게중심으로
> 보면 저희 모델이 불을 3,646 m 보냈고 실제로는 1,125 m 움직였습니다 — 원보다 더
> 많이 빗나갔습니다. 저희가 나은 것은 겹침이고, 방향은 아닙니다. 그리고 그 겹침이
> 모양이 불규칙해서 생긴 것인지도 재봤습니다 — 같은 모양을 각도만 바꿔 23번 돌리면
> 최고가 0.1359 인데 실제 방향은 0.2577 로 24개 중 1위였고, 돌린 것 중 20개는
> 원판보다도 못했습니다. 겹침을 만든 것은 그 모양을 그 각도로 놓은 것입니다 — 다만
> 이것도 「방향을 맞혔다」는 뜻은 아닙니다.」

The draft Korean above is a draft for the student's own voice (CHARTER §9).

⚠ **2026-09-11 (WFG-235): it is now on the card.** `docs/auto/JUDGE_QA.md` Q36 carries the
comparison in two places — an analytic block holding **both** IoU pairs with their
`dn_yeongdeok_` keys, the four centroid displacements, the floor-not-a-competitor caveat and
the time gap, and a shortened spoken form inside the card's 부스에서 할 말 quote. The draft
label that CHARTER §9 asks for is on the bank's own first line (「Status: DRAFT」), which is
where it is read. Two figures of the paragraph above were deliberately **not** carried across:
the 249-cell seed count and the metre forms (3,646 m / 1,125 m), the first because it is not a
registered key and the second because putting the magnitude on the document the front door
already points at is **WFG-237**, a separate row. The rebuild the note below priced was paid in
the same lap as WFG-240, WFG-241 and WFG-243.
