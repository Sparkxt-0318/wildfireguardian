# Arrival-RPS censoring propriety test (A1 amendment 1): PASS

The rule was committed at 6954c37a **before** this run. The scorer is the unchanged `sd9bench.arrival.rps`. Nothing is read from any fire except survey times (the three part-a pilots' `intervals.csv` at daniel/data-fetch 9ab223cf). 200,000 cells per pattern, seed 20261112.

Reproduce: `python derive/rps_propriety.py --intervals <Line,ThreeNine,Blue2 intervals.csv> --out RPS_PROPRIETY.json`

The table gives each forecast's excess mean RPS over the truth, with its z-score. The pass rule requires every excess to be above 3 SE.

| forecast | real part-a gaps (61 patterns; 74% not mapped by the last lead) | one survey at 3 h (95% not mapped) | surveys at 2 h and 5 h (93% not mapped) |
|---|---|---|---|
| always-early (F ≡ 1) | +0.851 (z 404) | +0.907 (z 1025) | +1.794 (z 1092) |
| never (F ≡ 0) | +0.115 (z 126) | +0.0044 (z 43) | +0.0118 (z 53) |
| shifted earlier 12 h | +0.0035 (z 29) | +0.0200 (z 106) | +0.0390 (z 117) |
| shifted later 12 h | +0.0075 (z 39) | +0.0044 (z 43) | +0.0118 (z 53) |
| over-dispersed | +0.00083 (z 13) | +0.00030 (z 14) | +0.00067 (z 18) |
| climatology | +0.0254 (z 67) | +0.0020 (z 29) | +0.0050 (z 34) |

**Verdict: PASS.** The truth scores best in every censoring pattern, by at least 13 standard errors. The always-early forecast, the WiDS failure mode, is the worst by far.

**Notes.**
- In the stress patterns every lead is at or below 5 h. "Shifted later by 12 h" is therefore F(0) = 0 there, identical to "never", which is why those two rows match.
- The earlier-to-later excess ratio (0.46, 4.5 and 3.3 across the three patterns) is a reported diagnostic. Under a proper score it is expected to depend on the hazard and the censoring pattern.
