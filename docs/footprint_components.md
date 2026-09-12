# What the graded footprint actually is, geometrically

*Method proposed by the loop (critic #65 filed the row, WFG-255; the measurement
and the reading below are the 2026-09-12T1517Z dev lap's). Artifact:
`data/processed/footprint_components/footprint_components_20260912T1527Z.json`.
Script: `scripts/measure_footprint_components.py`. Registry prefix
`fc_yeongdeok_`.*

## 1. The question this answers

Every headline IoU this project publishes for the 2025 영덕 fire scores a
forward-simulated core against one slice of `obs_stack` in the committed
`data/processed/routing_demo_canonical.npz`. Two published sentences read that
slice as **one advancing fire**: `docs/disc_null.md` said the model 「puts cells
along the arms the fire actually ran down」, and `docs/oracle_gap.md` §4's
centroid reading turns on how far 「the fire」 moved.

Until this page, **no file in this repository said what that object's geometry
is.** A judge who is a disaster-response official asks 「이 마스크 안에 무엇이
들어 있습니까」 in the first minute, and the honest answer was a shrug.

## 2. Method

One committed array is read. Nothing is refit, re-acquired, re-routed or
regenerated, and no committed artifact is touched.

- Grid: the canonical **181 × 156** at **500 m**, the same one every null on this
  fire uses.
- The forecast core is `haz_stack[i] >= 0.5` — the same `p_cut`
  `scripts/measure_disc_null.py` asserts, imported as a literal so this page
  cannot be scoring a different core than that one.
- The observation is `obs_stack[j] > 0`, matched by the same
  nearest-observation rule.
- Components are labelled under **both** 4- and 8-connectivity, and then under a
  **link-distance sweep**: cells within *k* cells of one another are counted as
  one piece. The dilation used to decide those labels is a joining rule only —
  no dilated cell is ever counted, measured or reported as burnt area.

**Bounding-box convention, stated because two are defensible.** `span_km` is the
union of the cells' own footprints, `(max − min + 1) × cell`. `centre_span_km` is
between the extreme cell **centres**, `(max − min) × cell`. They differ by exactly
one cell. Both are registered, because the WFG-255 row was filed quoting the
second convention (「24.5 km × 45.0 km」) and a later lap reading only the first
would think the row's number was wrong. It is not: `fc_yeongdeok_obs_span_long_km`
**45.5** and `fc_yeongdeok_obs_centre_span_long_km` **45.0** are the same edge
measured two ways.

## 3. Result, and why the result is not a number

The graded observation at **333** minutes holds `fc_yeongdeok_obs_cells` **937**
cells. How many pieces that is depends entirely on a rule nobody in this project
has ever justified:

| joining rule | pieces |
|---|---:|
| 4-connectivity (edges only) | `fc_yeongdeok_obs_components_4conn` **101** |
| 8-connectivity (edges and corners) | `fc_yeongdeok_obs_components_8conn` **55** |
| within 500 m | `fc_yeongdeok_obs_components_link_500m` **6** |
| within 1.0 km | `fc_yeongdeok_obs_components_link_1km` **2** |
| within 2.0 km | `fc_yeongdeok_obs_components_link_2km` **1** |

⚠⚠ **That table is the result. Any single row of it is a parameter wearing a
finding's clothes.** The identical committed mask is one hundred and one objects
or one object depending on a knob, and moving the knob by one cell — from plain
8-connectivity to 「within 500 m」 — takes **55** pieces to **6**. A page that
prints 「55 disconnected pieces」 without the rule beside it has published a
setting and called it a discovery. That is why the row's own framing, which asked
for the component structure, is answered here with a sweep and not with a count.

**What survives every rule in that table** is a different and more useful
statement. One piece dominates: `fc_yeongdeok_obs_largest_cells` **656** cells,
`fc_yeongdeok_obs_largest_share` **70.01 %** of the mask, against a second piece <!-- collision-ok: 70.01 — this is `fc_yeongdeok_obs_largest_share` written as a PERCENTAGE (the registry holds it as a ratio), the dominant piece's share of the OBSERVED mask. The gate matches it against `fc_yeongdeok_core_largest_share`, which is the MODEL CORE's dominant share on a different mask. Two quantities, neither stale. -->
of `fc_yeongdeok_obs_second_cells` **135**. And that dominant piece is itself
long: its own bounding box is `fc_yeongdeok_obs_largest_span_long_km` **44.5 km** <!-- collision-ok: 44.5 — this is `fc_yeongdeok_obs_largest_span_long_km`, the long side of the DOMINANT PIECE's own bounding box. The gate matches it against the three keys for the WHOLE mask's box (`fc_yeongdeok_obs_span_long_km`, `fc_yeongdeok_obs_span_short_km`, `fc_yeongdeok_obs_centre_span_long_km`). Four different edges; the piece is necessarily no longer than the mask that contains it, and none of the four is stale. -->
on the long side, inside a full-mask box of **25.0 × 45.5 km**. The remaining
`fc_yeongdeok_obs_cells_outside_largest` **281** cells are **not** all dust: the
second piece alone is **135** of them. It is the tail below that which is dust —
`fc_yeongdeok_obs_singletons_8conn` **39** of the 55 8-connected pieces are a
single cell each, contributing 39 cells between them.

So the graded object is **one elongated 44.5 km structure carrying about seven
tenths of the mask, plus scatter** — not 55 comparable pieces, and not one clean
perimeter either.

### 3b. The seed the nulls are centred on is almost pure scatter

The `t = 0` slice, whose centroid `scripts/measure_disc_null.py` and
`scripts/measure_rotation_null.py` both take as the neutral centre, holds
`fc_yeongdeok_seed_cells` **249** cells in `fc_yeongdeok_seed_components_8conn`
**226** pieces whose largest is `fc_yeongdeok_seed_largest_cells` **3** cells.

That is worth saying plainly: **the centre every null on this fire is anchored at
is the centre of mass of 249 nearly-isolated detection pixels**, not of a fire
front. Nothing here says that centre is wrong — it is the best available and both
nulls are explicit that they use it — but `docs/oracle_gap.md` §4's centroid
arithmetic is arithmetic on that object, and readers should know it.

### 3c. The model's own core is fragmented too

`fc_yeongdeok_core_cells` **952** cells at **360** minutes fall in
`fc_yeongdeok_core_components_8conn` **37** 8-connected pieces, dominant share
`fc_yeongdeok_core_largest_share` **75.0 %**. Fragmentation is therefore **not** a
defect found in the observation and absent from the forecast; both sides of the
comparison are spread fields on this grid.

## 4. What this does to the 「arms」 sentence

The WFG-255 row required that `docs/disc_null.md`'s 「puts cells along the arms
the fire actually ran down」 either earn that reading from the artifact or be
rewritten to the reading the artifact supports. **It is half earned, and the
half that fails is the word 「arms」.**

- **Earned: reach.** The observed field really does span a 45 km box and its
  dominant piece really is 44.5 km long, so a mask that spreads 952 cells along
  that box can collect overlap a compact circle cannot, whatever its centre.
  Nothing in this measurement disturbs that, and it is the surviving half of the
  sentence.
- **Not earned: the morphology.** 「Arms the fire ran down」 asserts branches of
  one advancing fire. At 8-connectivity the object is 55 pieces of which 39 are
  single cells, and **this repository cannot tell branches from spot fires, from
  separate fires, or from gaps in the detection record.** The artifact licenses
  「the long band the fire was detected along」 and not 「the arms it ran down」.
- **And the overlap is not concentrated in the dominant piece.** Of the
  `fc_yeongdeok_intersection_cells` **534** cells in both masks,
  `fc_yeongdeok_intersection_share_in_largest` **64.79 %** lie in the <!-- collision-ok: 64.79 — this is `fc_yeongdeok_intersection_share_in_largest` written as a PERCENTAGE, the share of the OVERLAP lying in the observation's dominant piece. The gate matches it against `fc_yeongdeok_core_largest_share`, the model core's dominant share. Two quantities, and the whole point of the sentence is that they differ. -->
  observation's dominant piece — which is *below* that piece's **70.01 %** share
  of the observation itself. The core touches
  `fc_yeongdeok_obs_components_touched` **48** of the **55** pieces. The model is
  therefore not winning by tracing one structure; it is winning by being spread
  across a field that is itself spread.

The sentence at `docs/disc_null.md` §5 was rewritten accordingly in the same lap,
and the superseded wording is kept there rather than deleted (HANDOFF §5 rule 7).

## 5. The component count standing still is the record standing still

`obs_stack` is **cumulative**. The 8-connected count is **55** at 333, 1005, 1480
and 1812 minutes and 56 at 2403. That stability is not the fire holding its shape:
between the graded slice and the last one, more than a day later, the record adds
`fc_yeongdeok_cells_added_graded_to_last` **86** cells in total
(`fc_yeongdeok_last_slice_cells` **1023** against **937**). Four slices agreeing is
four readings of nearly the same array.

## 6. What this does NOT show

1. **It does not say how many fires are in the mask, and no surface may write
   「여러 개의 산불」 or any count of fires from it.** §3's table is the reason:
   the count is a reading of a rule. FIRMS gaps fragment a single perimeter and
   the 2025 경북 event was a multi-fire complex; this repository cannot tell those
   apart, and this measurement does not help it.
2. **It moves no IoU and produces no margin.** 0.394, the 2.2044 seed-removed
   ratio, every `dn_yeongdeok_` and `rn_yeongdeok_` key, 42, 91, 9 and 27 are
   untouched. Nothing was refit or re-run; one committed array was read.
3. **It measures a detection field, not a fire.** `obs_stack` is FIRMS-derived
   with its own detection floor (`docs/detection_floor.md`) and 500 m resampling.
   The fragmentation reported here may be a property of the record rather than of
   the fire, and §3's sweep cannot separate the two.
4. **It is one fire at one set of slices.** No rate, frequency or typical value
   is implied, and nothing here generalises to another event.
5. **It is not a shape metric and settles nothing about `WC-018`.** No arithmetic
   here attributes any part of the IoU gap to shape, orientation or placement.
   The withdrawn claim that the model's winning axis is 「모양」 stays withdrawn,
   and §4 above narrows a sentence rather than reinstating one.
