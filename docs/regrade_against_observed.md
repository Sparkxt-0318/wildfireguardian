# Re-grading the three routing arms against the OBSERVED footprint (WFG-213)

**Status: rule pre-registered 2026-09-12 before the run; results appended below the
rule by the run itself.** Decided by the author on 2026-09-12 (NH-052, option A): run
it on 영덕, report whatever it says, in `docs/` and `data/processed/` only; no
judge-facing surface moves until the author has read it.

## 1. Why

`docs/oracle_gap.md` established that the forecast-aware route plans on `haz_stack`
(the leave-one-fire-out forward simulation) and is graded on the same array. Both
routes are therefore graded on a model output, never on what burned. The same
`data/processed/routing_demo_canonical.npz` carries `obs_stack`, the cumulative
FIRMS-observed footprint on the same 500 m grid at its own observation times.
This run keeps every route the arms choose today and re-scores each route against
`obs_stack`.

## 2. The between-observations rule, fixed before the run

`haz_times` are 0 / 180 / 360 / 540 / 720 min; `obs_times` are 0 / 333 / 1005 /
1480 / 1812 / 2403 min. A walker at time `t` is scored against the observed
footprint as follows:

- **Primary rule (「seen so far」, step-hold backward):** the observed field at `t`
  is the latest observation at or before `t`. A cell counts as burning from the
  first overpass that saw it burning; before that overpass it counts as unburned.
  This is the field an office watching the satellite feed would have held at `t`.
- **Sensitivity rule (「will be seen」, step-hold forward):** the observed field at
  `t` is the earliest observation at or after `t`. This is the conservative reading:
  a cell that the next overpass will show burning is treated as already burning.
- Burned cells carry probability 1.0, unburned 0.0; `p_cut` stays the committed 0.5,
  so 「enters hazard」 means 「stood on a cell the footprint marks burned at that time
  under the rule」. The budget (600 min), the departure (0), the routes and the
  origins are exactly the committed ones. Both rules are reported; neither is chosen
  after seeing the numbers.
- Limits stated up front: `obs_stack` is FIRMS at 500 m with a detection floor
  (`docs/detection_floor.md`), so this measures the model against **what was seen**,
  not against the fire; the last observation is at 2403 min, well past the 600-min
  walk budget, so no route is ever scored beyond the last observation; 의성·안동 has
  no `obs_stack`, so this run is 영덕 only.

## 3. What is reported

For the 458 canonical origins: the committed partition (must re-derive as
414 / 42 / 2 before anything is written), then for each arm (fire-blind, forecast-
aware; and the present-perimeter zero-buffer arm from
`docs/present_perimeter_yeongdeok.md`) the count of origins whose chosen route is
**safe under the observed rule** (reached, never on a burned cell at the time it was
there, inside budget), under both rules; and the origins whose verdict changes:
forecast-aware-only-safe under the forecast that is not so under the observation,
and the reverse.

## 4. Results

_(appended by `scripts/regrade_against_observed.py`; nothing above this line is
edited after the run)_

_Run 2026-09-12T15:25:38Z at `925d1a3`; artifact `data/processed/regrade_against_observed_yeongdeok.json`; partition re-derived as 414 / 42 / 2._

| arm | safe, graded on the forecast | safe, graded on 「seen so far」 | safe, graded on 「will be seen」 |
|---|---:|---:|---:|
| fire-blind | 414 | 422 | 333 |
| forecast-aware | 456 | 456 | 354 |
| present perimeter (0 buffer) | 440 | 456 | 335 |

- Of the **42** origins safe only on the forecast-aware route under the forecast, **34** remain forecast-aware-only-safe under 「seen so far」 and **9** under 「will be seen」.
- Origins where the forecast-aware route is safe and the fire-blind route is not, under the observation, any bucket: **34** (seen so far) / **21** (will be seen).
- Origins where the fire-blind route is safe and the forecast-aware route is not, under the observation: **0** / **0**.
- Forecast-aware routes that were 「safe」 on the forecast but cross a cell the observation marks burned at that time: **0** / **102**.

These counts are what the author asked to see (NH-052 A). They are not registered, not on any judge-facing surface, and not a margin until the author decides what they mean.
