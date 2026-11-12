# F-3.4 option A: two-tier radiation check — acceptance rule (written before anything is built or run)

Written 12 Nov 2026, about 12:20 UTC, while the F-DYN profile runs. Nothing for option A exists yet: no kit, no test,
no run. Option B (dyadic snapping) was negative (`results/option_b/`, `db2c516`, sent to Mira as REQUEST 9). If option
A also fails this rule, the speed-up line stops and the phase profile is reported as the F-3.4 result.

## What option A is

An opt-in copy of the request-window kit (`RDA_CAND`). The frozen kit is not edited.

`HybridRadiationBounds._coefficients` currently intersects three enclosures for every receiver box:
- the radial binary64 enclosure (outward rounded);
- the tiled radial enclosure;
- the exact-rational analytic enclosure for near sources. The analytic one dominates the radiation time.

Option A runs the two binary64 tiers first and returns their enclosure. It runs the exact analytic tier for a box
only when the cheap enclosure cannot decide the check, i.e. when a dose or peak upper bound built from it would reach
the request's budget. The analytic call stays, unchanged, as the fallback.

**Half-budget guard.** The cheap-first path is used only while less than half of the request's check budget has
elapsed. After that, the check reverts to the current behaviour (all tiers for every box). This holds until the
review argument below is accepted.

## Test-first deliverables (before any panel run)

1. **Property test** (`fastrad/test_two_tier.py`). On at least 10,000 random source/receiver boxes, drawn from the
   frozen packets' rectangles and road boxes plus random jitter, check that the cheap enclosure contains the exact
   analytic enclosure: `lo_cheap ≤ lo_exact` and `hi_exact ≤ hi_cheap`. Zero violations are required.
2. **Nesting log.** In the test arm only, every box decided by the cheap tier is also computed exactly, offline, after
   the run. The log records the same two inequalities. Zero violations over all panel executions are required.
3. **Review argument** (`fastrad/TWO_TIER_ARGUMENT.md`). Why a decision taken from the cheap enclosure cannot
   certify a route that the exact enclosure would refuse. Mira reviews it before any result is called verified.

## Acceptance rule (all conditions must hold)

**Panel and comparison.** 20 missions × 2 repetitions at the 81 s speed-equivalent budget, `--mode plain`, on this
host, quiet. The control is a fresh 2-rep run of the unchanged kit, made in the same session, interleaved by mission
(A then control for each mission, alternating the order by rep).

**(1) Verdicts and arrivals.** For each of the 19 missions other than Yeongdeok 0325T23 FL2: the set of
(authoritative status, arrival seconds) over A's reps equals the set over the control's reps.

**(1′) Stated rule for Yeongdeok 0325T23 FL2** (cap-sensitive). At 81 s on this host the unchanged kit has produced
`UNRESOLVED` (plain control, 2/2 reps), `CHECKED_JOURNEY_FEASIBLE` at 1922 s and `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN`
at 1922 s (phase runs). A passes for this mission iff every A outcome is one of those three. Any arrival other than
1922 s, or any other status, fails. It is excluded from the wall-time sum in (3), which is reported both with and
without it.

**(2) Certified bounds unchanged.** Per mission, compared only between runs with the same (status, arrival): the
median largest dose upper bound and the median largest peak upper bound, each as a share of the request's budget,
differ from the control by at most 0.0001 (absolute share). A looser bound that stays below budget still fails this
condition.

**(3) Wall-time gain that matters. Threshold: at least 20%.** The sum over the 19 missions of median plain wall time
must fall by ≥ 20% against the fresh control.

Why 20%:
- the largest arm-to-arm wall difference seen so far between kits with identical verdicts is 8.3% (option B), so
  20% is above twice that noise;
- radiation enclosure is 30.9% of cold wall on the 1-hour panel (73–96% on present-fire missions), so a gain under
  20% would mean the cheap tier rarely decides.

Also reported, not part of the rule: how many of the four missions unresolved at 30 s in both reps (Uljin 0304T03
FX1, Yeongdeok 0325T19 FD1, Yeongdeok 0325T19 FX2, Yeongdeok 0325T23 FL2) resolve at 30 s under A (2 reps).

**(4) Safety tests.** Zero violations in the property test and the nesting log. The existing kit tests pass
unchanged. No test is weakened.

**Outcome.** If any of (1), (1′), (2), (4) fails, A is rejected whatever its speed. If only (3) fails, A is recorded
as a correct but insufficient speed-up. In both cases the speed-up line stops and the profile is the F-3.4 result.
Either way the result goes to Mira with the same check as a positive.
