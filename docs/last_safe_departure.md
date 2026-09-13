# Last safe departure — fire-blind vs time-aware, 영덕 주건물 population

_Run 2026-09-13T13:52:58Z at `2da2dd5`; artifact `data/processed/last_safe_departure_yeongdeok.json`; 4970 nodes / 19250 buildings; forecast-graded; 591 s. Rule in the script docstring (declared before the run)._

LSD = the latest departure (minutes after the forecast clock's zero, 10-min grid, ≤ 600) at which the policy's route still reaches a refuge without entering p ≥ 0.5. −1 = never, even at 0. 600 = censored (still safe at the last grid point; the horizon clamp applies beyond 720 min). Building-weighted medians.

| subset | nodes | buildings | LSD fire-blind median | LSD time-aware median | gain median (p25–p75) | buildings gaining | losing | FB < 5 h | TA < 5 h | FB never | TA never | FB ≥ 600 | TA ≥ 600 |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all routable | 4970 | 19250 | 600 | 600 | 0 (0–0) | 1750 | 88 | 2095 | 966 | 1796 | 190 | 17141 | 18240 |
| both safe at departure 0 | 4439 | 17454 | 600 | 600 | 0 (0–0) | 144 | 88 | 299 | 223 | 0 | 0 | 17141 | 17227 |
| fire-blind safe now but closes before 600 min (threatened) | 94 | 313 | 70 | 150 | 0 (-10–280) | 144 | 88 | 299 | 223 | 0 | 0 | 0 | 86 |
| fire-blind never safe, time-aware safe at some departure | 477 | 1606 | -1 | 600 | 601 (261–601) | 1606 | 0 | 1606 | 553 | 1606 | 0 | 0 | 1013 |

What it does not show: passability, households, the observed footprint (this page is forecast-graded like the committed arms), or anything outside 영덕. Censoring at 600 min means the medians are lower bounds where the ≥ 600 column is large.

Limitation recorded after the run: for 88 buildings the time-aware search fails at a late departure at which the fixed fire-blind path still passes. The search is a 10-minute-stepped heuristic with a 600-min budget, not an exhaustive one; a route that exists can be missed at some departures. The count is reported, not corrected.
