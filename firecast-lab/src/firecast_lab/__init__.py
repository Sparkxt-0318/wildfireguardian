"""Track A (firecast-lab): a calibrated probabilistic fire-hazard generator, Phase 0 harness.

Modules: ``splits`` (SPLITS.json), ``domain`` (scoring domain and masks), ``metrics`` (scores on explicit
scoring masks), ``data`` (real data root and forecast windows; fails loudly when the root is absent),
``members`` (spatially coherent members from cumulative probabilities), ``baselines`` (persistence, dilation,
calibrated dilation, logistic), ``c651`` (the c651 SMOKE wrapper; needs torch), ``harness`` (whole-fire
cross-fitting and per-window scores), ``producer`` (hazard_contract v1 scenario sets), ``cli`` (``firecast-lab``).
"""
__version__ = "0.1.0"
