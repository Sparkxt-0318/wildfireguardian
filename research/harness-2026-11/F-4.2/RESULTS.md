# F-4.2 margin routing on the frozen 1-hour panel

Status: the monotonicity counterexample, the proofs and the static-obstacle finding are **verified by Mira
(PASS / PASS WITH NOTES, @ b6c94bb)**. The clearance margins are **verified PASS WITH NOTES by Mira (@ 0e6f7db)**:

- She re-derived all 15 published-route clearances with independent code, matching to 1 mm.
- She confirmed the limiting source is active at the limiting time.
- She reproduced 3 of 15 missions and 15 of 90 witnesses.
- She found no flaw in the r_fail soundness argument; it is sound up to the 1e-6 m outward pad.

Not independently verified: the other 12 missions' trade-off points and the other 75 witnesses. Those were
self-checked by the unchanged full checker and the exact rational clearance.

## 1. The ignition-advance margin is dropped as the headline (verified)

- **Not monotone.** Under a uniform advance of drawn ignition times (b → b − δ), fixed-route admissibility is monotone
  only for δ < T − t_end + b_min, which always covers δ < T − H ≈ 370 s. Beyond that range an advanced source also
  burns out earlier, and a route can become admissible again: `counterexample.py` is admissible on [0, 70],
  inadmissible on (70, 420.46) and admissible again after. Contact alone is monotone on [0, T], with closed-form margin
  `min(b − t_exit)`, valid up to T. See `MONOTONICITY.md`.
- **Mostly vacuous on this panel.** 8 of the 15 packets have zero drawn ignitions in every member. 14 of the 15
  published routes have closed footprints that never touch an igniting cell. The single exception, Uljin 1200Z FW2, has
  a contact time margin of 2320 s (`static_obstacle.py`).
- **Radiation never binds.** On the 15 routes the certified dose upper bound is at most 0.33 of budget, with 0.30 of
  that being incurred history on 3 missions, and the peak at most 0.0005 of budget. So the counterexample's mechanism
  cannot flip a verdict here. Mira did not check this headroom figure.

## 2. Primary margin: spatial clearance (measured)

**Definition.** A route's clearance r* is the largest dilation, in metres, of every active flame region that the route
survives. Each source is a closed 375 m cell rectangle from the packet affine. Activity is [b, b+T) for drawn ignitions
and [0, R_max) for present fire. A Minkowski dilation by a disc of radius r means the vehicle's position must stay more
than r from every active rectangle. Position is taken along straight node-to-node segments with linear timing, and is
stationary during waits and the dwell. Members are combined worst case. At r = 0 this is the whole-road contact
checker's closed footprint. Dilated sets are nested, so admissibility is monotone in r by construction. Radiation is
not part of the margin; see §1.

**Margin-optimal route.** For a deadline D, find the largest r such that some route with clearance > r arrives by D.
Earliest arrival a(r) is nondecreasing in r, so bisection on r is sound. The result is a bracket:

- the lower end is a feasible witness route: a search witness, or the published route when it meets D;
- the upper end comes from an earliest-arrival search with the destination opening start relaxed. It needs earliest
  labels to dominate, which a present-fire expiry R_max < H before D can break; those entries are marked †.

Five missions have a destination opening start. Their witnesses come from a two-phase search: wait at a waitable
node, then continue. The search at r = 0 reproduces all 15 published arrivals.

`results/TABLE.md`, with the published route, the margin bracket at the same arrival, and the best clearance within
+60, +300 and +600 s and by the horizon:

| Mission | Arrival (s) | Published clearance (m) | Limit | Crop distance (m) | Bracket at same arrival (m) | ≤ +60 s | ≤ +300 s | ≤ +600 s |
|---|---:|---:|---|---:|---|---|---|---|
| hongseong 1400 FW2 | 1459 | 295.0 | crop / origin | 46 | [295, 295] | 295 | 295 | 295 |
| hongseong 2300 FD1 | 531 | 857.5 | crop | 303 | [858, 858] | 858 | 858 | 858 |
| miryang 0531 FN1 | 1142 | 592.1 | crop | 27 | [592, 593] | 592 | **833 @ +148 s** | 833 |
| miryang 0601T02 FW1 | 1270 | 1610.5 | crop | 3 | [1780, 1781] | **1781 @ +0 s** | 1781 | 1781 |
| uiseong 0323 FD1 | 2460 | 3122.7 | crop | 1239 | [3123, 3123] | 3123 | 3123 | 3123 |
| uiseong 0323 FX2 | 2540 | **111.5** | fire | 3462 | [112, 112] | 112 | 112 | 112 |
| uiseong 0324 FL2 | 2143 | 287.0 | fire | 1266 | [287, 287] | 287 | 287 | 287 |
| uiseong 0325 FW1 | 1064 | 1490.7 | fire | 8757 | [1530, 1531] | **1531 @ +0 s** | 1531 | 1531 |
| uljin 0300 FD1 | 1589 | 3166.2 | crop | 2811 | [3166, 3166] | 3166 | 3166 | 3166† |
| uljin 0300 FX1 | 3119 | 506.5 | fire | 860 | [506, 507] | 506 | **680 @ +140 s†** | 680† |
| uljin 0600 FL1 | 2067 | 1617.8 | crop | 915 | [1618, 1618] | 1622 @ +1 s | 1622 | 1622 |
| uljin 1200 FW2 | 1655 | **179.9** | fire | 5520 | [180, 412] | **412 @ +19 s** | 412 | 412 |
| yeongdeok 0325T19 FX2 | 2512 | 503.7 | fire | 3057 | [504, 504] | 504 | 504 | 504 |
| yeongdeok 0325T23 FL2 | 1922 | 640.8 | fire | 3668 | [641, 641] | 641 | 641 | 641 |
| yeongdeok 0326 FW1 | 896 | 12870.8 | crop | 12 | lower 12871 (published route); upper censored (search cap 6000 < 12871) | 12871 | 12871 | 12871 |

**Findings (measured, verification pending):**

- **Limiting reasons.** 7 of the 15 published-route clearances are limited by represented fire and 8 by the packet
  domain. In the domain-limited cases the route passes within the clearance distance of the packet edge, where fire
  beyond the edge is not represented; these are whole-grid packets for Hongseong and Miryang and windows elsewhere.
  Those 8 margins are lower-bounded by fire but cannot be claimed as fire margins. None is limited by the horizon
  within ±600 s.
- **Small margins.** 7 of the 15 earliest routes clear the fire by under 600 m, and the smallest are 112 m (Uiseong
  FX2) and 180 m (Uljin FW2). As a labelled conversion only, at the bridge's documented 341 m/h front speed, 112 m is
  about 20 minutes and 180 m about 32 minutes.
- **The trade-off the assignment asked for exists in 3 of 15 missions:**
  - Uljin FW2: 180 m becomes 412 m for 19 s of extra travel;
  - Miryang FN1: 592 m becomes 833 m for +148 s;
  - Uljin FX1: 506 m becomes 680 m for +140 s.
  In the other 12 the earliest route is already the clearance optimum within +600 s, or the limit is at an endpoint or
  the domain.
- **Free improvement at the same arrival** in 2 missions: Miryang FW1 goes from 1610 to 1781 m and Uiseong FW1 from
  1491 to 1531 m. The router breaks arrival ties without regard to clearance; a lexicographic tie-break
  (arrival, then −clearance) would cost no arrival time.

## Verification (self-checks; independent verification pending)

All **90 witnesses pass both checks** (`verify_witnesses.py`, `results/VERIFY.jsonl`): 75 margin routes (15 missions × 5
deadlines) and the 15 published routes.

1. **Full checker.** The kit's unchanged whole-road checker (`adaptive_checker.HybridChecker`) on the original frozen
   packet returns `CERTIFIED_ADMISSIBLE` for all 90: contact, radiation, grammar, opening, dwell and horizon.
2. **Exact rational clearance.** The squared distance from each time-overlapping segment to each source rectangle is
   minimised exactly. It is piecewise quadratic, so the minimum lies at a breakpoint or vertex. It exceeds the claimed
   r for all 90.

## Not verified / limitations

- **Radiation is not dilated.** Whether dose and peak stay monotone under spatial dilation is not addressed; only the
  contact part is claimed. On this panel radiation never binds (§1).
- **Upper bounds.** The upper ends rely on earliest-label dominance and are marked † where a present-fire expiry
  precedes the deadline. Uljin FW2's bracket at the earliest arrival is wide, [180, 412], because the relaxed bound
  ignores the opening start. Yeongdeok FW1 is censored by the 6 km search cap.
- **Witness search.** It tries at most 60 waitable nodes on missions with an opening start. A failure to find a
  witness is not a proof of infeasibility; the bracket's upper end carries that role.
- **Outward rounding.** Binary64 distances carry a 1e-6 m outward pad. Integer departure seconds use exact
  ceil(b − u1·τ) … ceil(e − u0·τ) − 1. An earlier floor-based rounding produced an inverted bracket; it was fixed
  before this run.
- **Pending work.** Downwind-stretched (hexagon) dilation and F-DYN margins are not done; F-DYN waits for Leo's v3
  packets to pass Nora.

## Reproduce

```sh
# after the repo setup in ../F-3.4/RESULTS.md (fetch_routing_inputs + window kit at /tmp/wkit)
.venv/bin/python research/harness-2026-11/F-4.2/clearance_panel.py --out /tmp/clr --only uljin_2022__20220304T120000Z_FW2,miryang_2022__20220531T100000Z_FN1,uiseong_andong_2025__20250323T010000Z_FX2   # ~2 min
python3 research/harness-2026-11/F-4.2/analyze_clearance.py /tmp/clr/CLEARANCE.jsonl
.venv/bin/python research/harness-2026-11/F-4.2/verify_witnesses.py --kit /tmp/wkit --margins /tmp/clr/margin_routes --out /tmp/clr/VERIFY.jsonl   # ~3 min
# full panel: clearance_panel.py --out DIR (~25 min on this host); witnesses: results/margin_routes.tgz
```
