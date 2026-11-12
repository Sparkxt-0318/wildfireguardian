# F-C1 on the 2025 planner cache: short negative result

**Verification.** Hannah: PASS WITH NOTES at 0f7db4b. Her rerun's SUMMARY is identical to `SUMMARY_v2.json`; her
notes are applied.

**Quantity.** Line of sight to modelled burning cells versus the planner's leave-by time, on the recorded 2025 replay
(522 cases, 174 places).

**Definitions.** `DEFINITION.md` v2, fixed at `d9bb95d` before this counted run. Run: `_data/run_v2`, 2,002 s.

**Summary.** `SUMMARY_v2.json` (from `seebefore/summarize.py`).

> **Planning aid research only.** Line of sight is necessary, not sufficient, for a resident to notice a fire. The
> fire times come from a forecast that failed its superiority test, and from a 1-hour scenario window.

## Result

**No case has a robust negative gap.** That holds for flames and for the smoke column, under the rule fixed in
advance: a sign counts only when the optimistic and pessimistic visibility settings agree.

| Channel | Robust non-negative | No route | Indeterminate | Robust negative |
|---|---:|---:|---:|---:|
| Flames (opt: 10 m, best of 9 observers; pes: 2 m, cell centre, 15 km cap) | 76 | 21 | 425 | **0** |
| Smoke column (opt 1,000 m; pes 300 m, 15 km cap) | 262 | 21 | 239 | **0** |

Per setting (flames):

- **Optimistic:** 279 visible at the input time (gap ≥ 0), 219 censored or window deadlines not visible within the
  hour, 3 mixed members, 21 no route.
- **Pessimistic:** 76 visible now, 415 censored, **10 negative (8 places)**, 21 no route.
- **The 10 pessimistic negatives are all fire-set deadlines** (`fire_or_limits`, D = 1200–1800 s) at Uiseong
  03-23 01Z and 03-24 09Z. Fire is 1.3–4.6 km away. The optimistic setting sees flames at the input time in every
  scenario member for 7 of the 10, and in some members for the other 3. So all 10 are **indeterminate**: the sign
  depends on the observer and flame-height assumptions.

**Smoke, per setting.**

- **Pessimistic:** 1 negative and 1 mixed, both at Uiseong 03-24 09Z, `osm:node/415160433`.
- **Optimistic:** sees smoke at the input time there, so the robust smoke class is still indeterminate (robust
  negatives remain 0).

**Fire-set deadlines (15):**

- Flames: 5 robust non-negative, 10 indeterminate.
- Smoke: 13 robust non-negative, 2 indeterminate.

## Why this is a negative result (expected, as stated in advance)

1. **The scenario horizon is 1 h.** Only 15 of 522 deadlines are set by fire: 354 are censored at +50 min, 132 are
   set by the window, and 21 have no route. A gap sign that needs t_vis > D is decidable only for the 15.
2. **Within the hour the fire is the present fire** (0–9 new cells per member). So t_vis is either "now" or beyond
   the horizon.
3. **The visibility assumptions decide the sign for every fire-set case that is not visible from both settings.**
   Observer position, flame height and the cell sub-point decide it. A robust claim needs better observer and flame
   data, not more computation.

## Stated limits

- **Surface model.** GLO-30 is a DSM. **137 of 174 places** are flagged as non-bare-ground observers: the DSM is more
  than 5 m above the 5th percentile within 150 m, i.e. canopy or buildings at the mapped OSM point. Restricting to
  the 37 bare-ground places changes no robust sign (flames: 20 robust non-negative, 90 indeterminate, 1 no route).
  The flag is coarse and probably over-triggers in villages, so it is reported, not used as a filter.
- **Near-field clutter** within about 50 m dominates the required heights of hidden targets.
- **Not modelled:** haze, smoke obscuration (only the 15 km cap stands in), plume drift, and night glow (no sourced
  distance exists).
- **Robustness of negatives.** A fire-set deadline assumes no feasible second between the 10-min grid points. Nora
  verified that the later grid departures are `model_no_route`. Richard's exact 1-s field would be needed before any
  negative is claimed; none is claimed here.
- **Independent check.** An independent geodesic line-of-sight cross-check on the raw tiles agrees on 298 of 300
  visible/not-visible verdicts (`seebefore/validate_los.py`).

## Inputs

- **Surface:** GLO-30 tiles N36_00_E128_00 (SHA 8af5b10b…) and N36_00_E129_00 (SHA 1ece0425…), bilinear to EPSG:5179
  at 30 m. Built surface npz SHA fa5bc14a….
- **Fire:** `data/routing` (research-final-20261015), KFS_01 exports and HAZARD packets.
- **Planner records:** `research/solve2027-impact` (`analysis.run`).

## Reproduce (about 35 min on 3 workers)

```
python3 tools/fetch_routing_inputs.py
# GLO-30 tiles into research/harness-2026-11/F-C1/_data/raw/ (Daniel's fetch.py dem, or the S3 URLs in seebefore/dem.py)
cd research/harness-2026-11/F-C1
python3 seebefore/dem.py _data/raw/*.tif --out _data/surface_glo30_5179_30m.npz
python3 seebefore/compute.py --surface _data/surface_glo30_5179_30m.npz --out _data/run_v2 --workers 3
python3 seebefore/summarize.py _data/run_v2/cases_results.json --out _data/run_v2/SUMMARY.json
```

## Where F-C1 goes next (F-C1b)

- **Timing source.** Whole-event timing from the detection brackets (FIRMS), and from the timed village accounts
  Sofia collected, not the kriged mean (see the F-DYN README finding).
- **Kriged field.** Used for geometry only: from which direction, and over which ridge, the fire approached.
- **Partners.** Paired with the F-DYN deadlines.
- **Scope.** A few well-documented villages: Yeongdeok 지품면 (power cut 20:25 KST; smoke seen about 16:30),
  매정리 (arrival about 20:40), and the Cheongsong deaths. Not 174 indeterminate ones.
