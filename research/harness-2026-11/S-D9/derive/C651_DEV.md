# c651_mc against perimeter-trained models on full-rectangle labels (DEVELOPMENT-ONLY)

This is Iris's experiment 2, run at the orchestrator's request. It uses cohort R (US2024: 6 fires, already exposed, full-rectangle perimeter labels). Only committed forecast-v2 entry files are used, plus `dist_m` from `derive_dist.py`. **No untouched fire is used, and nothing here is confirmatory.**

Reproduce: `python derive/c651_dev.py --dist <derive_dist output> --heldout forecast/runs/20261030_perimeter_trained/execution_v3/heldout --out C651_DEV.json` (sha256 4f051a04…dd3c; byte-identical on rerun).

**Why.** c651_mc was trained only on interior patches of final kriged footprints (A1 §4.1; `prepare.py:862-883`). d4_wind_seed0 and the frozen logistic were trained on perimeter states.

**Method.**
- Intervals are 95% whole-fire bootstrap intervals (10,000 draws, seed 20261030), so the unit of resampling is the fire and there are only 6.
- Differences are candidate minus reference, so a positive difference means the candidate is worse.
- The pooled Brier scores reproduce the committed RESULTS.json exactly: c651_mc 0.0098522, d4_wind 0.0049269, persistence 0.0049968.

## Results

| population | entries / positives | c651_mc | d4_wind | logistic | persistence | c651 − d4_wind [95%] | c651 − logistic [95%] | c651 − persistence [95%] | fires where c651 is better than d4_wind |
|---|---|---|---|---|---|---|---|---|---|
| full domain | 1,705,079 / 8,520 | 0.009852 | 0.004927 | 0.004859 | 0.004997 | +0.00493 [+0.00275, +0.00854] | +0.00499 [+0.00278, +0.00862] | +0.00486 [+0.00266, +0.00857] | 0 / 6 |
| 4 km band | 596,719 / 8,179 | 0.02757 | 0.01351 | 0.01331 | 0.01371 | +0.01407 [+0.00781, +0.02575] | +0.01426 [+0.00802, +0.02598] | +0.01387 [+0.00767, +0.02578] | 0 / 6 |
| *off final footprint* (y ≡ 0) | 1,376,682 / 0 | 0.006671 | 0.0000751 | 0.000256 | 0 | +0.00660 [+0.00374, +0.01168] | +0.00642 [+0.00354, +0.01166] | +0.00667 [+0.00376, +0.01183] | 0 / 6 |
| *on final footprint* | 328,397 / 8,520 | 0.02319 | 0.02527 | 0.02415 | 0.02594 | −0.00208 [−0.00405, −0.00024] | −0.00096 [−0.00235, +0.00032] | −0.00276 [−0.00509, −0.00083] | 5 / 6 |

*The off/on rows split cells by the **final** mapped union, which is hindsight. They decompose the full-rectangle score for diagnosis and are not decision populations. Taken alone, the on-footprint row is hindsight-conditioned (A1 §4.1).*

**Off the final footprint, where cells never burn:**
- Mean p: c651 0.0237, logistic 0.0069, d4_wind 0.0009.
- Share of cells with p ≥ 0.01: c651 17.1%, logistic 16.3%, d4_wind 2.0%.
- c651's off-footprint Brier is 89 times d4_wind's.
- Off-footprint cells are 80.7% of all entries and 83.7% of the band.
- Off-footprint error accounts for 0.00539 of c651's full-domain Brier of 0.00985.

**Tail (4 km band).**
- *Owen's caveat.* c651_mc marginals are multiples of 1/1024: 27.8% of band entries (74.2% of the full domain) are exact Monte Carlo zeros. Its tail is stated against the 1/1024 floor, and no decay slope is fitted.
- **Positives at p < 1/1024:** c651 571 (7.0%), d4_wind 3,212 (39.3%), logistic 22 (0.3%).
- **Lowest-bin calibration gap, [0, 1e-3):** c651 0.0033 (mean p 0.00021 vs observed 0.0035), d4_wind 0.0066, logistic 0.0136 (on only 1,877 entries).

## Reading

1. **On full-rectangle perimeter labels, c651_mc is clearly worse than d4_wind, the logistic and persistence.** This holds in both the full domain and the 4 km band, on all 6 fires. Every interval excludes zero.
2. **The deficit is off the footprint.** c651 puts substantial probability on cells that never burn, which is consistent with a model that never saw a cell that stays unburned. On the footprint, c651 is **better** than d4_wind and persistence, and level with the logistic. Scored only on cells that eventually burn, as the kriged populations are, c651 would look good. That is the hindsight conditioning of A1 §4.1 at work.
3. **In the tail, c651 leaves fewer positives at near-zero p than d4_wind does.** Its error is over-warning, not missed spread.

## Implication for the routing default (for the user's decision)

The forecast-v2 delivery index records `default_checkpoint: "c651 unchanged"` (`research/forecast-v2/DELIVERY_INDEX.json`). Per the orchestrator, c651 feeds the routing packets and the planner. I have not traced the routing code here.

On these 6 exposed US fires, the routing default:
- **over-warns away from the fire.** About 17% of cells that never burn get p ≥ 0.01.
- **scores worse than persistence on Brier.** The full-domain excess is +0.0049 [+0.0027, +0.0086].
- **misses fewer near-zero positives than d4_wind.**

For evacuation routing, that means more closures or detours driven by false alarms rather than missed fire. Calibration is still poor. Whether that trade is acceptable is a product decision.

The remedy, if one is wanted, is a **new, separately versioned kit** with a perimeter-trained or recalibrated model. The frozen kit is never edited. **That decision is the user's.** The evidence is limited: 6 fires from one season and region, already exposed, and development-only.
