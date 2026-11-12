# Tolerance for the synthetic far_share recovery run (`run_shape_recovery.py`)

**Timing.** Written at about 12:03 UTC on 2026-11-12, after the run started (about 12:02 UTC, commit 033fcbf6) and
before any output was seen. It was sent to Victor (S-D9) at that time and is committed here before
`results/shape_recovery.json` is read. The git timestamp of this commit is the checkable record.

**Definitions.** far_share = Σ over offsets with Chebyshev distance ≥ 2 of the kernel rate ÷ Σ over all offsets.
True values: low_far 0.072, high_far 0.602. Five seeds per kernel.

**Criteria, as accepted by Victor:**
- **Recovers:** |mean over 5 seeds of recovered far_share − true| ≤ 0.05 AND per-seed SD ≤ 0.05, in BOTH kernels.
- **Inflates when the truth is low:** plug-in (or mean-field NLL) mean far_share ≥ true + 0.10 on low_far.
- **Collapses a far-heavy truth:** mean ≤ true − 0.10 on high_far.
- **Conclusions:**
  - "plug-in/NLL misallocate toward far offsets" holds only if MCEM *recovers* in both kernels AND plug-in or NLL
    *inflates* on low_far;
  - if MCEM *collapses* high_far, the conclusion is "both biased, in opposite directions";
  - otherwise the result is reported as stated, without either claim.

**Scope note (Victor).** The synthetic MCEM uses a 0.1 h Gibbs grid; the real `d2_bracket` uses 0.25 h. This result
speaks for 0.1 h. `run_step_check.py` (0.25 vs 0.05 h) must show that 0.25 h is close enough, otherwise the
amendment states that the step differs from the validated one.
