# Owner brief: kit v2 Step 2 (memory accounting), for the ~22:40 UTC decision

1. **Passed** (1-hour panel, 20 × 2 interleaved, no restart): G1 20/20, G2 28/28, G2b 40 runs / 0 violations, G3 20/20,
   G5 wall 0.893 (0.996 without FL2). Every published check was proven within budget by its own cgroup peak (largest
   493 MiB), with 0 memory-mapped statuses. Separately, the 9.1–9.6 GiB bound-model spike is gone (now 709–728 MiB,
   byte-identical arrays).
2. **The one failure: G5 memory.**
   - Family peak RSS-sum is up **+40–78% on 12/20 missions**, i.e. every mission that runs a whole-road check.
   - PSS-sum, which counts shared pages once, is still **+23–38%** on the two missions measured.
   - All values stay **≤ 3,072 MiB** (largest 1,138).
   - `gc.freeze()` does not fix it (PSS 903 → 852 MiB).
3. **Risk:** the controller's guard reads the same RSS-sum, which counts the forked check's shared pages twice. On an
   F-DYN Yeongdeok job it read **9,352 MiB while PSS was 5,083 MiB**, so any guard between about 5.1 and 9.4 GiB would
   stop a job on pages that exist once.
4. **Options:**
   - **F4 + F3: keep check isolation.**
     - Accept the measured memory cost, all ≤ 3,072 MiB on the panel, and move the v2 controller guard (and the G5
       measure) to family PSS or the job cgroup.
     - Gain: completed checks are kept and proven within budget. One F-DYN request discarded in A1 now ends
       FULL_OPTIMUM_PROVEN, within budget; that is a diagnostic, not yet the acceptance run.
     - Cost: +23–38% real memory, and a gate measure changed after the result, so it must be declared.
   - **Drop check isolation.** Keep only the current-RSS solver gate and the chunked bound model.
     - Gain: G5 memory as written holds on the 1-hour panel. Hypothesis, to be re-run: the failure comes only from the
       fork.
     - Cost: checks stay gated on the lifetime peak, so F-DYN Yeongdeok checks are still discarded and v2 does not
       certify those routes.
5. **Recommendation: F4 + F3,** declared as an amendment before any rerun, with PSS or job-cgroup as the guard and G5
   measure in v2. Reason: dropping isolation removes the step's purpose beyond one hour, and the guard risk exists only
   under RSS-sum.
