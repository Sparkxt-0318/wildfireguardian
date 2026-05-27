# `validation` — retrospective skill assessment

**Status**: scaffold only.

**Purpose**: score the spread + smoke + routing pipeline against the
documented evolution of the March 22–28, 2025 영덕 wildfire (and any other
historical events we can collect).

**Inputs**: KFS official perimeter polygons (ground truth at successive
times), KMA AWS observed wind, Sentinel-2 LFMC ≤ 7 days pre-event, and the
pipeline's forecast outputs at the same times.

**Outputs**: a results table of skill scores — Sørensen–Dice on perimeter
polygons at +1 h / +3 h / +6 h horizons, Brier score on per-cell burn
probability for the Monte Carlo ensemble, and a "lead-time-to-warning"
metric for selected village centroids (when would the system have raised
the alert vs. when did the actual evacuation order arrive?).

**Algorithmic basis**: standard fire-spread-forecast verification statistics
following Cruz & Alexander (2013), *Uncertainty associated with model
predictions of surface and crown fire rates of spread*.
