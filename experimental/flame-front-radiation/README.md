# Flame-front radiation prototype

This opt-in NumPy library implements the public radiation interface on supported front geometry. Its empirical physics gate remains unresolved, so it is not admitted for the requested routing campaign. The full requirement ledger is in `research/flame-front-radiation/REQUIREMENTS_STATUS.json`.

```python
import numpy as np
from wfg_flamefront import flux_at_points, flux_enclosure, dose

member = {"ignition_time_s": np.tile(np.arange(4)*10.0, (4, 1))}
grid = (10, 0, 0, 0, 10, 0)
q = flux_at_points([[-10, 15]], [3, 4], member, grid)
lower, upper = flux_enclosure((-11, -9, 14, 16), (3, 4), member, grid)
```

Install with `python -m pip install ./experimental/flame-front-radiation`. Run tests with `python -m pytest experimental/flame-front-radiation/tests`. Reproduce the exact evidence with `python research/flame-front-radiation/run_evidence.py`.

NaN and explicit invalid masks are unknown. Infinity is never ignited, and a mixed finite/infinite quad has no finite bilinear contour without an additional interpolation scenario. Missing exact past ignition phases and simultaneous active ignition fields raise `UnsupportedGeometry`. They do not yield a zero flux decision. `never_time_s` and `unsupported_policy='exclude'` are explicit counterfactual visualization controls and must be labeled if used. Scalar or aligned fuel maps are supported for consumed fuel, heat and emissive power. Wind is a common local horizontal vector in this prototype.

`adapters/journey_check.py` exposes a gated integration seam, not a complete copied checker. Law v2 raises `NotImplementedError` until the physics gate and full journey implementation are complete. The unchanged complete law-v1 evaluator must be explicitly supplied.

Point and enclosure evaluation share a domain guard. An enclosure refuses any interval intersecting a zero-gradient ignition or extinction field's potentially active period, including unsupported interiors between contour events. It also conservatively refuses boxes that may intersect an emitting panel. Finite containment and monotonicity apply only to supported queries; enlarging a query may make it unsupported, never silently zero. All-known never-ignited cells have zero emission, while invalid masks remain unknown.

The enclosure uses an exact rational swept hull, upper panel area and box-to-hull minimum distance. A proved angular-cone condition permits an inverse-square upper; elsewhere the original unit-view-factor bound remains. Whole-quad hulls can remain loose under refinement. The point evaluator uses directed Decimal intervals and a proved arctangent remainder, returning a directed lower approximation to the analytic panel value, except for the declared unit orientation envelope. It does not use an arbitrary error epsilon or clip the earlier cancellation error to make the upper pass. Source hashes bind the implementation and read-only frozen inputs. Nothing here establishes field validation, physical accuracy or operational safety. See `docs/RADIATION_LAW_V2.md` for equations and open obligations.

Post-merge source repairs are documented in [the October 31 repair record](../../research/postmerge-fixes-20261031/README.md). The original SOURCE_SHA256.json identifies the producer used by the saved studies; it is retained verbatim. The separate post-merge source ledger identifies current repairs. Recorded historical timings are not measurements of this repaired version.
