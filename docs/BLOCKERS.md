# Known limitations & blockers — overnight session 1

This document records issues encountered during the initial overnight build
that the next session (or the human collaborator) will need to address.
Each entry is honest about what was tried, what didn't work, and what
would be needed to close it out.

---

## 1. Single-class Rothermel vs. multi-class BehavePlus

**Status**: known, documented, not blocking.

**Issue**: the canonical Rothermel reference values published in
Andrews 2018 (and BehavePlus output) use the multi-class fuel weighting —
each Anderson 13 fuel model contributes 1-h, 10-h, 100-h dead and live
herbaceous / live woody fuels, combined by surface-area weighting (Albini
1976 §IV; Andrews 2018 §3). The task spec asked for a single-class
:class:`FuelModel` API. Our implementation honours that.

**Consequence**: for multi-class-rich fuels (FM4 chaparral, FM10 timber
understory) the single-class implementation **overestimates** rate of
spread by 2–5×. For single-class fuels (FM1 short grass, FM8 closed
litter) the agreement is within ~ 15 % of published values.

| Fuel | Single-class (this code, m_f=0.06, no wind) | Andrews 2018 / BehavePlus | Ratio |
|------|--------------------------------------------:|--------------------------:|------:|
| FM1  | 1.40 m/min                                  | ~ 1.2–1.5 m/min           | 1.0×  |
| FM4  | 6.11 m/min                                  | ~ 2.0–2.5 m/min           | 2.5×  |
| FM8  | 0.27 m/min                                  | ~ 0.15–0.30 m/min         | 1.0×  |
| FM10 | 1.39 m/min                                  | ~ 0.4–0.6 m/min           | 2.5×  |

The unit tests in ``tests/test_rothermel.py`` use loose bounds to capture
this regime; see ``test_published_reference_values``.

**To close**: implement Albini-style multi-class surface-area weighting.
Concretely, extend the fuel-model registry with per-class loadings and
SAVs, and add the weighting equations (Andrews 2018 §3, eq. 7–17). This is
a half-day of work for a careful implementer plus an afternoon of cross-
checks against a known BehavePlus baseline. Suggested deliverable for
the next session.

---

## 2. LFMC sensitivity demo uses a hand-calibrated "Korean Pinus" fuel

**Status**: known, documented, intentional.

**Issue**: the Anderson 13 fuel models all have dead moisture of
extinction $m_x \in [0.12, 0.40]$. The task spec asked for an LFMC
sensitivity sweep from 10 % to 200 %. Standard Anderson fuels go to zero
at the dead $m_x$ band; the curve would be empty above ~ 40 % LFMC.

In real BehavePlus, live fuels have a separate $m_x^{\text{live}}$
computed dynamically per Burgan & Rothermel (1984). For the single-class
demo we use a **custom Korean Pinus densiflora analogue** fuel model with
$m_x = 1.20$ that approximates the live-fuel extinction regime. The
parameters are documented in ``demo_sensitivity.py``.

**To close**: once multi-class weighting is in (issue 1), the demo can be
re-done with FM10 + the proper live $m_x$ machinery, and the synthetic
"Korean Pinus" fuel can be retired in favour of a derived-from-Anderson
formulation.

---

## 3. Huygens elliptical wavelet flank ratio is small even at moderate winds

**Status**: known, documented.

**Issue**: the elliptical-wavelet directional spread rate is
$R(\theta) = R_{\max}(1 - e) / (1 - e\cos\theta)$ where $e$ is the
eccentricity derived from the length-to-breadth ratio $LB$. The Anderson
1983 LB correlation diverges exponentially with wind, so we cap LB at 3.0
(see ``cellular_automaton.LB_MAX``). At LB = 3.0, $e \approx 0.943$ and
the flank rate is $\approx 5.7 \%$ of head rate.

**Consequence**: in the cellular automaton demo, lateral spread is much
slower than downwind spread — sometimes only 1–3 cells lateral over 6 h.
This is qualitatively correct (real wind-driven fires *are* highly
elongated) but visually thin on small grids.

**To close**: not a true bug, but the next session could (a) add
optional spotting / crown-fire ignition, which is the dominant
lateral-spread mechanism in real wind-driven fires, or (b) parameterise
LB from a per-fuel-model length-to-breadth correlation rather than the
universal Anderson one (Cruz & Alexander 2010).

---

## 4. CA does not yet split wind and slope into a vector sum

**Status**: known simplification.

**Issue**: in FARSITE, wind and slope are combined as vectors into an
effective "direction of maximum spread" with magnitude
$\phi_{\text{eff}} = |\phi_w \hat{u}_{\text{wind}} + \phi_s \hat{u}_{\text{upslope}}|$.
Our implementation uses the wind direction alone for the ellipse major
axis, and slope contributes only to the scalar $R_{\max}$ via Rothermel's
$\phi_s$. Aspect data is ingested but not used yet.

**Consequence**: when wind and slope point in different directions, our
fire still elongates along the wind axis rather than along the combined
vector. The synthetic Yeongdeok demo has gentle terrain so this is not
visible; on steep terrain with cross-wind it would be wrong.

**To close**: implement the vector combination per Finney 1998 §2.2.4
(eq. 14–17). This is a half-day of work plus tests.

---

## 5. No real geographic CRS

**Status**: deliberately deferred.

**Issue**: the cellular automaton works in a local Cartesian frame with
the SW corner of the grid at the origin (units: metres). It does not yet
know how to attach to a real-world CRS like EPSG:5179 (Korea 2000
Unified) or EPSG:4326 (WGS84). The synthetic demo GeoJSON has
metres-from-SW-corner coordinates, which are **not georeferenced**.

**To close**: this is part of the ``data_io`` module's responsibility. The
next session should wire up a ``FireGrid.attach_crs(transform, crs)``
method (where ``transform`` is an affine like rasterio uses) and have
``perimeter()`` emit geographic GeoJSON.

---

## Genuine blockers

**None.** All three deliverables completed; all 37 unit tests pass.
