# The oracle is in the grader, not in the planner

**Row:** WFG-125 · **Method proposed by:** the loop (four consecutive critic laps
wrote the objection; critic #50 promoted the row to first position)
**Artifact:** `data/processed/oracle_gap_yeongdeok.json`
**Script:** `scripts/measure_oracle_gap.py` · **Registry:** the `og_yeongdeok_*` prefix
of `docs/NUMBERS.json` — count it there rather than here. This line said 「10 keys」
until 2026-09-10 and the prefix had held 25 since the per-slice band was registered;
a key count written into prose goes stale the next time the registrar grows.

---

## 1. The question this answers

`docs/present_perimeter_arm.md` §5, `README.md`'s TL;DR and the WFG-125 backlog
row all say the same sentence in different words:

> The forecast-aware arm carries no forecast error here. It plans on the same
> hazard field it is scored against, so 9 is the margin a **perfect** forecast
> buys. The margin of this project's actual model is smaller by an amount this
> run does not measure.

A judge can turn that into five seconds of Korean — 「비교하신 예보는 정답을 미리 본
예보 아닙니까?」 — and until this document the honest answer was 「맞습니다」 with
nothing after it.

WFG-125 asked, as its **first** question, which of the committed fields is a
prediction and which is the graded truth, and told the lap taking it not to
assume the answer. The answer is not the one the row assumed.

## 2. What the two committed stacks actually are

`data/processed/routing_demo_canonical.npz` — the canonical Yeongdeok field, the
one the headline **42 of 458** is scanned on — holds **both** of these, on one
grid, in one file:

| array | dtype | what it is |
|---|---|---|
| `haz_stack` | float32 `(5, 181, 156)` | the **leave-one-fire-out forward simulation**. `scripts/build_canonical_hazard.py` (`:129-130`) fits the spread_v2 model on every fire EXCEPT the target, so this is a model output on a fire the model never saw. The router plans on it. |
| `obs_stack` | uint8 `(6, 181, 156)` | the **cumulative FIRMS-observed footprint** on the same 500 m grid, at its own observation times. Nothing scores against it. |

So the forecast-aware arm does **not** plan on truth. It already plans on a field
the model produced — which is exactly what WFG-125's expensive branch asked
someone to build, and it has been committed since Round 3.

**What makes the arm an oracle is that the grader uses `haz_stack` as if it were
truth.** The arm is graded against the same array it planned on, so by
construction it cannot be wrong.

That relocates the fix. Removing the oracle does **not** need a new *planning*
field. It needs a different *grading* field — and a complete one, defined over
every cell of the grid, is committed beside the one in use.

### 2b. Why this makes the row cheaper than it was costed

Critic #47 costed WFG-125's first branch as unaffordable, and the arithmetic was
right for the instrument it assumed. That instrument was
`data/processed/spread_v2_lofo_oof_cells.csv.gz`, the per-cell out-of-fold
probability **sample**: 20,749 rows over 5 operating points for `yeongdeok_2025`,
touching **4,859** distinct cells. Against **this** document's canonical grid
(181 × 156 = 28,236 cells) that is **17.2 %**; critic #47's 18.3 % is the same
4,859 cells against the older `routing_demo.npz` grid (181 × 147 = 26,607), and
the two figures are quoted with their grids because the argument silently swapped
them once already. Either way, re-planning on it needs a fill rule for the other
four fifths, and a fill rule chosen after seeing the margin is a second post-hoc
maximum of exactly the kind WFG-201 was filed about.

That reasoning is sound and it is about the wrong instrument. The out-of-fold
sample would be needed to build a *planning* field, and the planning field is not
what is missing. `obs_stack` is a **grading** field, it is complete over the grid,
and it needs no fill rule, no refit and no re-acquisition.

## 3. Method

`scripts/measure_oracle_gap.py` reads that one npz and counts cells. For each
forward-simulation slice it takes the predicted core (`p >= 0.5`, the committed
routing impassability threshold), pairs it with the observed cumulative footprint
at the **nearest available observation time**, and decomposes the disagreement.
Both stacks are asserted cumulative rather than assumed so (they are).

The quoted slice is the best time-matched pair. `t = 0` is excluded from the
headline because both stacks are seeded from the same detection there and agree
perfectly by construction — that is not skill.

## 4. Result

At the best-matched pair, **27 minutes** apart:

| quantity | value |
|---|---|
| forward-simulated core, 360 min | **952** cells |
| observed footprint, 333 min | **937** cells |
| in both | **534** cells |
| predicted, did not burn | **418** cells |
| burned, not predicted | **403** cells |
| IoU | **0.394** |
| predicted / observed area | **1.016** |

Every slice, including the badly-matched ones, is in the artifact.

**At this slice the model gets the size nearly exactly right and the place
substantially wrong.** It puts 952 cells in the fire where 937 burned — within
2 % on area — and only 534 of them are the same cells. Routing depends entirely
on *which* cells, and on nothing at all about how many.

⚠ **What those 937 cells ARE, geometrically, was unstated on this page until
2026-09-12** (WFG-255; full account in
[`docs/footprint_components.md`](footprint_components.md)). They are **one
elongated structure plus scatter**: a dominant connected piece of
`fc_yeongdeok_obs_largest_cells` **656** cells — `fc_yeongdeok_obs_largest_share`
**70.01 %** of the mask, `fc_yeongdeok_obs_largest_span_long_km` **44.5 km** long <!-- collision-ok: 70.01 — this is `fc_yeongdeok_obs_largest_share` written as a PERCENTAGE (the registry holds it as a ratio), the dominant piece's share of the OBSERVED mask. The gate matches it against `fc_yeongdeok_core_largest_share`, which is the MODEL CORE's dominant share on a different mask. Two quantities, neither stale. --> <!-- collision-ok: 44.5 — this is `fc_yeongdeok_obs_largest_span_long_km`, the long side of the DOMINANT PIECE's own bounding box. The gate matches it against the three keys for the WHOLE mask's box (`fc_yeongdeok_obs_span_long_km`, `fc_yeongdeok_obs_span_short_km`, `fc_yeongdeok_obs_centre_span_long_km`). Four different edges; the piece is necessarily no longer than the mask that contains it, and none of the four is stale. -->
by itself — plus `fc_yeongdeok_obs_cells_outside_largest` **281** cells of scatter
around it, the whole mask fitting a box of `fc_yeongdeok_obs_span_short_km`
**25.0** × `fc_yeongdeok_obs_span_long_km` **45.5 km**. ⚠⚠ **How many pieces that scatter
is, is a reading of a rule and not a property of the fire:** the same mask is
`fc_yeongdeok_obs_components_4conn` **101** pieces under 4-connectivity,
`fc_yeongdeok_obs_components_8conn` **55** under 8-connectivity,
`fc_yeongdeok_obs_components_link_1km` **11** when cells within 1 km are joined
and `fc_yeongdeok_obs_components_link_4km` **1** at 4 km. So
no count here is a count of fires, and none may be written as one. ⚠ The model's
own core is fragmented too — `fc_yeongdeok_core_components_8conn` **37** pieces —
so this is a property of both sides of the comparison, not a defect of the
observation. **None of it moves 0.394 or any number in the table above.**

⚠ **The size agreement is a property of this slice, not of the model.** The
selection rule (exclude the shared seed at `t = 0`, then take the smallest time
gap) is fixed in the script and pinned by a test, and it does **not** pick the
IoU maximum — `t = 540` and `t = 720` both score higher than the quoted 0.394.
But it does land on the slice where the area ratio is best.

⚠⚠ **And the other three slices are not readings of the model, because they are
not time-matched. Every ratio and every IoU below is printed with the gap it was
scored across, because without that column the series reads as forecast bias when
most of it is the matching.**

| forecast time | observation it was graded against | `time_gap_min` | predicted / observed area | IoU |
|---:|---:|---:|---:|---:|
| 180 min | **333 min** | **153** | 0.7385 | 0.3586 |
| 360 min | **333 min** | **27** | 1.016 | 0.3941 |
| 540 min | **333 min** | **207** | 1.047 | 0.3949 |
| 720 min | **1005 min** | **285** | 1.0496 | 0.3981 |

**Three of the four slices — 180, 360 and 540 minutes — are scored against the
same observation**, the 333-minute one the headline pair uses; only `t = 720`
matches a later one. So the denominator is one constant footprint across three of
the four rows,
and the ratio series 0.74 / 1.02 / 1.05 is a growing simulated area over a fixed
observed area, not three independent readings of the model.

That changes what the first row means, and an earlier draft of this document read
it the other way — as a statement about the forecast's size bias at three hours.
It is withdrawn as `WC-014`, and the sentence it was is in
`docs/auto/withdrawn_claims.json` rather than here. At `t = 180` the forecast is
compared with a footprint **153 minutes later than the forecast time**, on a fire
that was still growing, so the simulated area is smaller than the thing it is
measured against largely because that thing had 153 more minutes to burn. The
honest statement is narrower: **the size agreement at the 27-minute pair is not
evidence of size agreement anywhere else, and the three badly-matched slices are
evidence about the matching, not about the model.** The place disagreement remains
the stable finding — it is the one quantity in this table a time gap cannot
manufacture, because a longer gap grows the intersection and the union together.

Every number in that table is a registry key:
`og_yeongdeok_t###min_time_gap_min`, `_size_ratio`, `_iou` and — new in the same
lap that added the column — `_obs_time_min`. **The observation column exists
because the first draft of this section left it out and told the reader the
registry forbade it.** That was false twice over: the headline
`og_yeongdeok_obs_time_min` has been registered since this document was written
and §4's own result table above prints it, and the withheld column is precisely
the evidence for the claim this section makes. The lap's independent reviewer
blocked on it, the five per-slice keys were registered through
`scripts/register_oracle_gap.py` rather than argued about, and that closes
`WFG-215`'s registry half. The general form of the mistake is worth more than the
correction: **invoking a rule to license an omission is worse than writing a wrong
number, because the next reader inherits a registry that says no when it says
yes.**

### 4b. What the IoU is, and what it is not

The per-slice IoU here (0.36 / 0.39 / 0.39 / 0.40 at 3/6/9/12 h, scored across
time gaps of **153 / 27 / 207 / 285** minutes and, for the first three, against
one observation) sits beside the
**≈ 0.40** figure `docs/MODEL_CARD.md` §「Footprint IoU — honest figure」 already
reports (0.37 / 0.40 / 0.39 / 0.40, sourced from `yeongdeok_forward_sim.json/drift`).

⚠ **That is not an independent confirmation, and an earlier draft of this
document called it one.** `scripts/measure_oracle_gap.py` recomputes the same
quantity as `src/wildfireguardian/spread_v2/forward_sim.py`'s
`drift_vs_observed`: the same `p_cut`, the same nearest-observation matching, the
same cumulative masks, on a field from the same estimator, the same
leave-target-out fit, the same fire and the same FIRMS overpasses. The only
difference is the canvas (181×147 → 181×156). So the agreement is close to
**mechanical**, and it is a consistency check on the canvas change — not
evidence from an independent route. It is recorded here because the alternative
is letting a self-confirming replication travel in the caveat band as though it
were corroboration.

### 4c. What 0.394 should be compared with

§4 above says the place is 「substantially wrong」 and, until 2026-09-10, nothing in
this repository said what 0.394 should be measured against. `docs/disc_null.md`
(WFG-228) builds the comparison: an **area-matched disc**, centred on the centroid
of the `t = 0` seed the two stacks agree on exactly, holding exactly as many cells
as that slice's own predicted core, scored against the same observation under the
same matching rule. Zero free parameters, and the rule and the interpretation were
both fixed in the claim commit before the run.

| headline slice, 27 min apart | forward simulation | area-matched disc | ratio |
|---|---:|---:|---:|
| cells | 952 | 952 | |
| IoU as scored here | **0.3941** | **0.1554** | **2.5360** |
| IoU, **shared seed removed** | **0.2577** | **0.1169** | **2.2044** |

⚠ **Quote the second row, not the first.** `obs_stack` is cumulative, so the 249-cell
`t = 0` seed is a subset of the observation being scored; the model's core contains
all 249 by construction — they are its initial condition, not a prediction — while
the disc recovers 92. Removing the shared seed from all three masks takes that free
intersection away, and `docs/disc_null.md` §3c is where it is argued. The finding
survives in sign at all four slices and loses about a fifth of its size.

So 「substantially wrong」 stands as a statement about how many cells disagree — and
it is now also true that the forecast overlaps the fire about **2.2** times better
than a disc of identical area centred on the `t = 0` seed centroid. The gap is stable
across all four slices while the time gap under them runs from 27 to 285 minutes.

<!-- forbidden-ok: wc017-centred-on-ignition-en -->
⚠ 〔정정 · 2026-09-11 · WFG-254〕 **This sentence said 「centred on the ignition」
until this date, and that was a false locative.** The disc's centre is the centroid
of the `t = 0` detection seed; the ignition point the canonical array records sits
`dnc_yeongdeok_seedcentre_to_ignition_cells` **38.3986** cells from it, further than
the largest disc radius at any slice. `docs/disc_null.md` §2b holds the measurement.
No measured value moved — only the word for the centre.

⚠ **The gap is not directional skill, and `docs/disc_null.md` §4 is where that is
argued.** By centre of mass the model **overshoots**: the observed footprint's
centroid moves 2.250 cells from the seed, the model's core moves 7.292, and the
disc's centre-of-mass error (2.266 cells) is *smaller* than the model's (5.340).
What the model does better than a circle is **shape and reach**, not direction.
Quote the two rows together or neither. ⚠ 「Reach」 and not 「extent」: the null holds
**area** equal by construction, so on the area reading that claim is impossible
rather than merely unproven (`docs/disc_null.md` §4, corrected 2026-09-11, WFG-254).

⚠ **What the centroid is a centroid OF.** The `t = 0` seed those 2.250 cells are
measured from is `fc_yeongdeok_seed_cells` **249** cells in
`fc_yeongdeok_seed_components_8conn` **226** disconnected pieces whose largest is
`fc_yeongdeok_seed_largest_cells` **3** cells (WFG-255,
[`docs/footprint_components.md`](footprint_components.md) §3b). The arithmetic
above is therefore the centre of mass of a nearly-isolated detection scatter, not
of a fire front. That does not make it the wrong centre — it is the best available
and both nulls are explicit that they use it — but 「how far the fire moved」 is a
looser reading of it than the words suggest.

⚠ The disc is a **floor**, not a competitive baseline: a circle against an elongated
fire is a weak opponent, so clearing it is necessary and not sufficient. The
persistence null a fire scientist would ask for is **WFG-234** and is not built.

## 5. What this changes for the judge answer

The honest answer to 「비교하신 예보는 정답을 미리 본 예보 아닙니까?」 is no longer
「맞습니다」 and a silence. It is:

> 예, 같은 장을 보고 계획하고 같은 장으로 채점합니다. 다만 그 장은 「정답」이
> 아닙니다 — 이 불을 한 번도 학습하지 않은 모델이 만든 예측입니다. 그리고 그
> 예측이 실제 관측과 얼마나 다른지는 같은 파일 안에 있습니다: 면적은 2 % 안에서
> 맞히고, 자리는 절반 정도만 맞힙니다. 그래서 42는 「완벽한 예보의 값」이라기보다
> 「자기 예측을 그대로 믿었을 때의 값」입니다. 실제 예보 오차를 넣은 값은 아직
> 재지 않았고, 무엇을 하면 잴 수 있는지는 문서에 적어 두었습니다.

⚠ That draft is for the student's own voice and is not yet in
`docs/auto/JUDGE_QA.md`; putting it on a judge-facing surface is a separate row
(WFG-213), because it touches the reading of a committed headline number and
NH-032 and NH-034 are open.

## 6. What would actually measure the margin, and what it costs

Re-grade the **already-computed** routes against `obs_stack` instead of
`haz_stack`, changing nothing else:

1. the fire-blind arm, the present-perimeter arm and the forecast-aware arm all
   keep the routes they choose today;
2. `_evaluate_path`'s hazard sequence is swapped for one built from `obs_stack`;
3. every arm is scored under the one rule, as `docs/present_perimeter_arm.md` §2
   already insists.

The forecast-aware arm then carries real forecast error and the margin it wins is
what **this project's model** buys, not what a noiseless one would. No refit, no
re-acquisition, no fill rule, no new free parameter.

**Three things make it a separate row (WFG-213) and not a paragraph here.**

- **It would change the meaning of a committed, judged headline number.** 42 and
  91 are cited by the submission. CHARTER §6 makes that a decision for the
  author, not a lap: **NH-052**.
- **The time grids do not line up.** `haz_times` are 0/180/360/540/720 min;
  `obs_times` are 0/333/1005/1480/1812/2403. A route is evaluated continuously in
  time, so re-grading needs a stated rule for reading `obs_stack` between
  observations, and that rule is a free parameter that must be written down
  **before** the run — the WFG-201 discipline.
- **`obs_stack` is not ground truth.** It is FIRMS at a 500 m resample with a
  detection floor (`docs/detection_floor.md`). A cell counted as "burned, not
  predicted" may be a cell the model missed or a cell FIRMS saw and the model
  correctly did not, and this comparison cannot separate those. Re-grading
  against it measures the model against *the observation*, which is the honest
  available target and is not the same as measuring it against the fire.

## 7. What this does NOT show

- **It is not a routing result and produces no margin.** No route was run. It
  moves no committed number: 42, 91, 9 and 27 are untouched. Anyone quoting
  0.394 as "what the forecast buys" has misread it. That exact spelling is not
  in the registry; what every `og_yeongdeok_*` key does carry, in its
  `forbidden_phrasings` field, is a list of neighbouring readings, and
  `tests/test_oracle_gap.py::test_the_forbidden_phrasings_are_registered_and_absent_from_the_doc`
  binds that list by asserting **this page contains none of them** — which is
  why none of them is quoted here, in the sentence that would most naturally
  quote one. ⚠ For **this page** that test is the whole of the enforcement:
  `make verify` does not read the field, and `scripts/check_forbidden.py`,
  which is the tree-wide prose scanner, carries none of these strings. Other
  documents are not scanned for these spellings at all (`WFG-232`). Read the
  list at the keys.
- **It is not a new performance claim, and it is not an independent one.** The
  IoU is the model card's own drift metric recomputed on the extended canvas
  (§4b) — a consistency check, not corroboration. What is new here is the
  decomposition into false alarms and misses, and the observation that the two
  are nearly equal while the areas match.
- **One fire, one ignition, one region, one threshold.** `p_cut` 0.5 is the
  committed routing threshold; nothing here sweeps it.
- **The compared slices are 27 minutes apart, not simultaneous.** That gap is
  registered as its own key so it cannot be quietly dropped, and the other
  pairings — one of them 285 minutes apart — are in the artifact beside it.
- **It says nothing about 의성·안동.** `hazard_uiseong_andong_2025.npz` carries
  `haz_stack` and no `obs_stack` at all, so the same measurement cannot be made
  there from committed data. That asymmetry is stated in WFG-213 rather than
  papered over: the region the fair-opponent margin (9, 27) comes from is the
  region where this check is **not** currently possible.
