# Independent bounded radiation arithmetic and upper-bound review

Reviewed immutable commit `43324736fc5301a0444b01b918ef14a0372b1ec3` at `work/audit-1a`. No confirmed actionable defect found in the reviewed directed polygon evaluator, swept-hull bound, or wiring, under their declared supported domain. This is a source/proof review with fixed sanity checks, not a machine-checked proof, universal input census, or physical validation.

## Reviewed argument

- `verified_view.py:38-63`: algebraic interval endpoints are directed; Decimal's correctly rounded square root is explicitly bracketed using adjacent Decimal values, rather than assuming its rounding mode follows the context.
- `verified_view.py:74-106`: half-angle reductions and the alternating next-term remainder enclose arctangent. The quadrant and endpoint choices for atan2 follow its monotonicity for nonnegative y. Machin's identity supplies an interval for pi.
- `verified_view.py:109-115`, `solidflame.py:40-53`, and `law_v2.py:121-146`: point conversion, nonnegative products and final sums are directed downward. Exact represented planar geometry, convexity, horizon clipping and receiver-plane decisions avoid the old geometric epsilon/cancellation dependence.
- `geometric_bounds.py:45-68`: monotonic rounded interpolation endpoints enclose each directed quad edge; the exact parallelogram side matches the point evaluator. The L1 cross-product area bound and exact prism-to-box distance bound are conservative. The condition `2*d2>D2` implies positive pairwise ray dot products, excluding the declared unit orientation-envelope branch. Then `A/(3*d2)` conservatively exceeds the diffuse-area bound using pi > 3. Outside that cone the implementation retains one.
- `law_v2.py:149-191`: four panels per candidate quad, exact nonnegative products/sums and upward final conversion preserve the upper. Enlarging supported time intervals only adds candidate quads; enlarging receiver boxes decreases separation and can only loosen the bound. The point and interval domain checks precede supported-zero selection.

## Independent fixed checks

`work/venv-routing/bin/python work/radiation-review/arithmetic_sanity.py` passed 42 small checks: 16 square-root brackets checked by exact rational squaring; 8 atan brackets checked against independent direct alternating rational series; 2 pi brackets from independent direct-series Machin bounds; 8 quadrant identities; and 8 maximal downward binary64 conversions. Source SHA256 `2ec65356bee50e552d0958f42521e6a09f73d3acd4d17b4d7423f2b5530e5d02` matches BOUND_RESULTS.

`work/venv-routing/bin/python work/radiation-review/artifact_sanity.py` independently reproduced the retained public counterexample: point `5.844308577232327e-26 kW/m2`, upper `5.865954053640389e-25 kW/m2`. Compared the retained compressed CSVs against current tables: changed flux values 10/4/4; maximum changes respectively `1.4210854715202004e-14`, `1.7763568394002505e-15`, and `3.552713678800501e-15 kW/m2`. Scenario/provenance columns remained equal. All four retained PNG/SVG files were byte-identical to their current counterparts.

## Limits and honest claims

The argument is conditional on the represented panel model and Python Decimal's documented correctly rounded operations, exact Fraction semantics, and NumPy binary64 operation behavior. This review does not prove those runtimes or cover alternative hardware, rounding environments, global Decimal-context mutations, all extreme inputs, or all public malformed polygon inputs. It did not rerun the owner's 42-test suite or 367 release checks.

The documentation and BOUND_RESULTS correctly retain lower zero, unit fallback outside the cone, possible nonconvergence of whole-quad hulls under refinement, and no uniform adaptive-precision runtime/memory guarantee. An outer checker must enforce a budget and preserve unresolved. Physics remains HOLD; no empirical fire accuracy, useful route-certificate tightness, physical threshold, field deployment or law-v2 routing result follows. No routing or physical experiment was run in this review.

Graph evidence: exact project `wfg-next-1a-audit-43324736-20261030`, generation `2026-10-30T04:09:55Z`; relevant snippets/traces were complete at requested scope; every source/test/results path checked had no recorded relevant coverage gap. The excluded `docs/RADIATION_LAW_V2.md` was read directly in full. The audited checkout remained clean; only this scratch directory was written.
