# The leak-free 영덕 fold (G3 / WFG-032)

**Status: rule pre-registered 2026-09-14 before the run; §3 is appended by the run.**
The manuscript (`paper/manuscript.md` §6) calls this 「the experiment most likely to move
the 42-origin result」. Laptop only: it needs the raw FIRMS/ERA5/DEM bundle. Docs and
`data/processed/` only; nothing registered, no committed artifact modified (the canonical
npz, `spread_v2_lofo.json` and `fire_manifest.json` are digest-checked before and after).

## 1. Why

의성·안동 2025 and 영덕 2025 are one fire complex: the same days (2025-03-22 → 28) and
acquisition boxes that overlap between 128.95 and 129.1 E. The canonical 영덕 hazard field
was simulated by a model fitted leave-the-target-fire-out, i.e. trained on the other five
fires **including 의성·안동**. Cells of the same complex, under the same weather, may
therefore sit in the training set of the model that produced the field every 영덕 routing
number stands on. The six fires are five independent events plus one co-located pair.

## 2. Rule

1. Build the canonical dataset exactly as `scripts/build_canonical_hazard.py` does and
   refuse to continue unless it reproduces 151,904 rows / 2,989 positives.
2. Count the overlap from the raw detections: 의성·안동 detections whose position lies
   inside the 영덕 acquisition box.
3. Fit two models with the canonical seed: **canonical** (train = all fires except 영덕) and
   **leak-free** (train = all fires except 영덕 and 의성·안동). Report the held-out 영덕
   ROC-AUC of both on the same test rows.
4. Simulate the leak-free field on the **same canvas** as the canonical field (bbox
   128.92–129.77 E, 36.10–36.90 N; 500 m; 181 × 156; 4 steps of 3 h; advance threshold
   0.3): no canvas search, so origins and grids stay comparable. Report core cells per
   slice, per-slice core IoU against the canonical field, and any boundary contact (a field
   that reaches the edge is reported, not re-canvassed).
5. Route the **same 458 origins** (the canonical set, chosen at the canonical t0) on both
   fields under the committed rule (slope DiGraph, p_cut 0.5, 600 min, 10-min step) and
   report the three-way partition on each, the forecast-only sets and their overlap.
6. Grade both fields' routes on the observed footprint with the three-way rule of
   `docs/regrade_three_way.md` (cell membership, A1–A6).
7. Repeat 5–6 on the WFG-275 building population (19,250 주건물 on 4,970 nodes), keeping
   the canonical routable set so the two fields are paired.

Reading rule, fixed now: the result is 「the leak moves the headline」 if the leak-free
forecast-only count differs from 42 by more than the network-drift noise already measured
on the 439 series (a 0.047 % node change moved 33 % of binary verdicts), i.e. by more than
about a third; otherwise 「the headline is robust to the leak」. Either way the observed
grading is the number to carry forward, because it does not depend on which field planned
the route.

## 3. Results

_(appended by `scripts/run_leakfree_yeongdeok_fold.py`; nothing above this line is edited after the run)_

_Run 2026-09-13T16:38:17Z at `bb820d6`; artifact `data/processed/leakfree_yeongdeok_fold.json`; field `data/processed/routing_demo_leakfree.npz`; 633 s. Protected digests unchanged._

- Overlap that motivates the fold: 671 of 4021 의성·안동 detections lie inside the 영덕 box; training rows drop from 131,155 to 48,419 (positives 2,220 → 718).
- Held-out 영덕 AUC: canonical fold 0.9403, leak-free fold 0.8691.
- Field: core cells (p ≥ 0.5) per slice leak-free [249, 373, 528, 537, 540] vs canonical [249, 692, 952, 981, 1036]; core IoU per slice [1.0, 0.5236, 0.5102, 0.5135, 0.5038]; boundary contact none.
- 458 origins (same set: True): partition canonical {'both_safe': 414, 'naive_into_FA_safe': 42, 'no_safe_route': 2, 'other': 0} → leak-free {'both_safe': 422, 'naive_into_FA_safe': 34, 'no_safe_route': 2, 'other': 0}; forecast-only overlap 34 of 42 / 34.
- 458 origins graded on the observation, forecast-aware route: canonical {'admissible_all': 351, 'indeterminate': 86, 'inadmissible_all': 19, 'not_reached': 2} → leak-free {'admissible_all': 350, 'indeterminate': 89, 'inadmissible_all': 17, 'not_reached': 2}; of the leak-free forecast-only set {'admissible_all': 8, 'indeterminate': 11, 'inadmissible_all': 15, 'not_reached': 0} (canonical set {'admissible_all': 9, 'indeterminate': 16, 'inadmissible_all': 17, 'not_reached': 0}).
- Buildings (19,250 on 4,970 nodes; 0 would be filtered out by the leak-free t0 field, kept for pairing): partition canonical {'both_safe': 17454, 'naive_into_FA_safe': 1606, 'no_safe_route': 190, 'other': 0} → leak-free {'both_safe': 17783, 'naive_into_FA_safe': 1277, 'no_safe_route': 190, 'other': 0}; observed forecast-aware canonical {'admissible_all': 15024, 'indeterminate': 3362, 'inadmissible_all': 674, 'not_reached': 190} → leak-free {'admissible_all': 15059, 'indeterminate': 3436, 'inadmissible_all': 565, 'not_reached': 190}.

## 4. Reading (written after the run)

- **The leak is real and it flattered the fold.** 671 of 4,021 의성·안동 detections lie inside
  the 영덕 acquisition box. Removing that fire from training drops the held-out 영덕 AUC from
  0.940 to 0.869 (still inside the six-fold range the model card reports) and removes 62 % of
  the training rows, because the two 2025 fires are the largest events in the set.
- **The leak-free field is roughly half the size.** At 720 min the canonical field carries
  1,036 core cells, the leak-free one 540; per-slice core IoU between them is about 0.51
  after the first slice. The observation had already reached 937 detected cells by 333 min,
  so the leak-free forecast **under-predicts** this fire's growth: without the co-located
  fire, the model has not seen a 2025-scale spread rate.
- **The headline moves, and by the pre-registered rule it does not move enough to change
  the reading.** 42 → 34 forecast-only origins (−19 %, all 34 inside the original 42);
  1,606 → 1,277 buildings (−20 %). The threshold declared in §2 was one third. The
  no-safe-route class is unchanged at 2 origins / 190 buildings.
- **The observed grading barely moves, which is the point of grading on the observation.**
  Forecast-aware routes on the 458: 351 / 86 / 19 → 350 / 89 / 17; on the buildings
  15,024 / 3,362 / 674 → 15,059 / 3,436 / 565. Of the leak-free forecast-only set, 15 of
  34 stand in an already-detected cell (canonical: 17 of 42). The share of the forecast's
  credited advantage that the observation contradicts is the same either way.
- **What to say in the manuscript.** The 42 is a leave-target-out number on a field whose
  training set included the same complex; the leak-free number is 34 and the field is
  smaller. Both should be printed together, with the observed grading beside them; the
  observed grading is the number that survives the choice of field.
- **Not shown:** anything about the other five folds (only 영덕 was refit); passability
  (A3); households; the 의성·안동 headline (its own fold would need the symmetric exclusion,
  not run here).
