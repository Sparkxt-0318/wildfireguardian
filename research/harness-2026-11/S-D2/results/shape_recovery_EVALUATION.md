# far_share recovery: evaluation against the tolerance committed in TOLERANCE_shape_recovery.md

The tolerance was committed at 946f1e4e, before this output was read.
Run: `python run_shape_recovery.py --seeds 5 --workers 2 --out results/shape_recovery.json` (wall time 1070 s).
Setup: 64×64 grid, T = 240 h, 24 h brackets, 5 seeds per kernel. MCEM uses a 0.1 h Gibbs grid.

| kernel (true) | estimator | far_share mean | SD | mean − true | rate ratio | rel-L2 | verdict |
|---|---|---|---|---|---|---|---|
| low_far (0.072) | plug-in | 0.388 | 0.016 | +0.316 | 0.941 | 0.544 | **inflates** (≥ true + 0.10) |
| low_far | composite | 0.047 | 0.008 | −0.025 | 0.992 | 0.180 | within ±0.05 |
| low_far | mean-field NLL | 0.095 | 0.026 | +0.023 | 0.987 | 0.219 | within ±0.05 |
| low_far | MCEM | 0.080 | 0.011 | +0.008 | 1.005 | 0.173 | within ±0.05 |
| high_far (0.602) | plug-in | 0.713 | 0.016 | +0.111 | 0.967 | 0.327 | outside ±0.05; not a collapse |
| high_far | composite | 0.524 | 0.039 | −0.078 | 0.969 | 0.321 | outside ±0.05; not a collapse (threshold 0.502) |
| high_far | mean-field NLL | 0.602 | 0.035 | +0.000 | 1.001 | 0.404 | within ±0.05 |
| high_far | MCEM | 0.588 | 0.033 | −0.014 | 0.991 | 0.310 | within ±0.05 |

**Per-estimator verdicts (both kernels):**
- MCEM **recovers**.
- Mean-field NLL **recovers**.
- Plug-in **inflates** on low_far.
- Composite does not recover: it is biased low on high_far, but short of the collapse threshold.

**Conclusion under the pre-stated rule:** MCEM recovers in both kernels, and plug-in inflates on low_far. So
"misallocates toward far offsets" holds **for plug-in only**. It does **not** hold for mean-field NLL, which recovers
here. No estimator collapses high_far.

**What this means for the real part-a fits (unverified there):** on real data, mean-field NLL gives a far share
of about 0.64–0.68, against 0.066 for MCEM. That gap is *not* explained by NLL estimator bias under this synthetic
model, where both recover. It must come from something the synthetic world lacks: model misspecification, the
environment modulation, observation error, or a real far-offset signal that MCEM misses. This result does not
say which.

**Scope:** this holds for MCEM on a 0.1 h grid only. The 0.25 h vs 0.05 h check (`run_step_check.py`) is running.
