# MEASURED and MEASURED+GUST arms (frozen before any outcome of them was computed)

Frozen 2026-11-17. `HOTSPOT_RULE.md` (known fire area, issue times, step rule, deadline field, score) is unchanged and
applies as is: same 174 places, same 13 issue hours (12:00-24:00 KST), same two horizons (5 h, 8 h), same score.
The three stand-ins ORDINARY, RUNNING, WORST stay, unrelabelled. Two arms are added; only R(h) differs.

## R(h) values (from `research/kcf-margin/numbers.json`, table, fire set all28, alpha 0.10, MEASURED on 28 GOFER fires)

| class | R(5 h) km | R(8 h) km |
|---|---|---|
| quiet (prior-3 h spread < 1 km) | 2.6 | 3.5 |
| slow (1-3 km) | 5.0 | 6.4 |
| running (>= 3 km) | 7.6 | 10.0 |
| gust < 10 m/s | 2.6 | 3.0 |
| gust 10-20 m/s | 4.7 | 5.9 |
| gust >= 20 m/s (9 fires only) | 8.6 | 12.0 |

R is in km beyond the known fire area, in the replay: from the edge of the known discs. R(h) for the closure time is
the piecewise-linear curve through (0 h, 0 km), (5 h, R5), (8 h, R8) (the part below 5 h is ASSUMED linear; the margin
work has no 1-8 h class table for these classes). Closure time of a road cell at distance d = the h at which the curve
reaches d (beyond 8 h: beyond every horizon, never closes within H). Government step: d <= R5 -> LEAVE_NOW; d <= R8 ->
PREPARE_VULNERABLE_FIRST, as in HOTSPOT_RULE.

## Arm 4, MEASURED: class by prior-3 h spread
Class at issue time T from the known fire area. New discs = those with t in [T-3 h, T); prior discs = t < T-3 h. For each
new disc, d = max(0, min over prior discs of (centre distance - prior disc radius)). A new disc with d > 5 km is a separate
fire and left out (the margin protocol's 5 km rule, per disc, not per 8-connected component: a simplification). Spread
= max d over the rest (0 if none). quiet < 1, slow 1-3, running >= 3 km. If there is no prior disc, the class is
"all hours" (R5 3.8, R8 5.0). One class per T, the same for all 174 places and both horizons.

## Arm 5, MEASURED+GUST: class by gust
Class from `research/kcf-gust` (frozen in its PROTOCOL.md): the maximum gust over (T, T+H] at the five points, maximum
over the points, for the run's horizon H (5 h run uses (T, T+5 h]; 8 h run uses (T, T+8 h]). One class per (T, H), the same
for all places. Series: KMA primary if it was fetched, else ERA5 and the arm is **PROVISIONAL** (labelled in every
table and in the figure). The gust >= 20 m/s class rests on 9 fires; stated next to every number that uses it.

## Tables and figure
Both arms added to every table of RESULTS.md and to timeline.png as extra series, nothing removed or relabelled.
Score as in HOTSPOT_RULE: count of place-hours with a latest safe departure whose witness route is reached by the
reconstructed fire earlier, places, places with >= 1.

## Amendments
(none)
