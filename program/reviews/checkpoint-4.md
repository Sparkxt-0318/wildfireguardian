# Checkpoint 4: Track C batch 2 (E1b, E2)

2026-11-02. All numbers SYNTHETIC: dev, 60 s, seeds 0-4, VM session `4169abd4`, B2 interleaved (ABAB) in two lock
holds. Code: `evacplan/phase0` `fcb7fc58`, merged into `next/integration` as `00155c5a`.

| SYNTHETIC dev, 60 s | worst of 5 (bar 1751) | median | M | L | mean time to certified plan | decision |
|---|---|---|---|---|---|---|
| B2 (10 seeds) | 1749 | 1749 | 597 | 1044 | 66.0 s | baseline |
| E1b, incremental certification | 1444 | 1446 | 605 | 730 | 66.3 s | **KILL** |
| E2, column generation | 1585 | 1611 | 573 | 929 | **44.8 s** | **ITERATE** |

**Where E1's 33-41 s went (your item 1).**
- E1 was certifying B1's warm start inside the budget: about 1,700 legs, all new to the cache.
- A cold check of an L plan takes 30-31 s (17-19 ms per leg):
  - 89 % is hazard queries (48 % per-member flux and dose bounds, 25 % cell geometry);
  - 10 % is the exact leg slack;
  - under 1 % is validation.
- The cost is linear in K: 8-9 ms plus 1.1-1.4 ms per member, per leg.
- Four internal speed-ups are proposed: an estimated 2-3×, not measured.

**E1b.**
- S and M: +9 over B2.
- L: −314. Certifying one changed L plan costs 32-36 s. In 6 of 10 L runs the certify trigger fired too late (prior
  15 ms per leg, about 20 ms measured), so B1's plan came back.

**E2.**
- Plans: equal to B2 or better on S and loose M; below on tight M and on L.
- Bounds: the tightest proven yet, inside 60 s.
  - 156 on M-s107 and 143 on M-s108; E4 had 160 and 144, the trivial bounds are 168 and 149.
  - 4 instances proven optimal in 4-23 s.
  - 0 violations in 470 plan rows.
- At the 30-min default margin, E2 delivers 1350 to B2's 1284.

**Review** ([`batch2-review.md`](batch2-review.md)).
- Clean-checkout reproduction:
  - 433 + 76 tests pass;
  - the leaderboard is byte-identical;
  - both headline numbers reproduce.
- Reviewer: 0 major, 9 minor, 6 notes. All are fixed or answered, and none changes a result.
- After the fixes: 438 tests pass.

**My calls** (`DECISIONS.md`).
- B2 partner seeds: 0-4 for E1b and 5-9 for E2, merged as a union.
- A hold never silently replaces rows.
- A verdict needs every row paired with B2.
- No checkout is edited during a hold.
- The speed check flagged all 4 holds (probe 0.09-0.26 s), so VM timings are indicative only. ABAB is kept as you
  specified, and I did not chase the drift further.

**Track A:** unchanged. Its data and torch are not reachable here.

## Questions (ranked; recommendation in bold)

1. **Batch 3: approve E5, E1's ALNS with no oracle inside the budget?** Relaxed checks in the loop; the harness
   certifies the result, as for B2. **Yes, pre-registered: KEEP if worst of 5 > 1751, else KILL.**
   - Post hoc it delivered 1774-1799 per seed (earlier session, indicative).
   - No in-loop oracle check cut a trip in 150 dev runs.
2. **E2's next iteration as a certificate, not a planner?** **Yes, small:** bound only on M, a longer budget, the best
   plans as columns. This gives certified gaps (now 3.8 % and 2.8 %), with no more plan-side work.
3. **Oracle speed-up in batch 3?** Internals of the hazard library and the oracle only: bit-for-bit identical results
   (regression test), version 1.0.2, no interface change. **Yes:** it speeds every certification and Track A's metric
   (about 80 min per model).
4. **Robust count in the verdict?** Once Track A gives the margin, should "beats B2" count residents delivered with
   slack ≥ margin? **Yes, then; until then both are reported.**
5. **Real data.** E3b, E4b, the margin and Track A all wait on your Mac's data. **After batch 3, move timed reruns and
   Track A's real-data work to the Mac;** I will prepare a one-command rerun kit.
