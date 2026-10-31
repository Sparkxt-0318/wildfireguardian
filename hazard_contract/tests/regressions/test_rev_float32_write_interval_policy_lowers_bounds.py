# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""ScenarioSet.write(dtype="float32") rounds ignitions down and extinctions up ("burning intervals
only grow") and treats that as safe. Under burn_duration_policy="interval" (accepted by HeatSource
and by write), a cell's emission is C / (extinguish_s - ignite_s): stretching the interval LOWERS
the emission. Reading the float32 file back, flux_upper and dose_upper fall below the true sheet-law
flux / dose of the float64 set that was written, on a supported query (KERNEL_MARGIN is 1e-9, the
float32 stretch is ulp/duration).

Set: one 100 m cell burning on [200000.01, 200030.01) (t ~ 55 h, e.g. a multi-day perimeter set;
float32 ulp there is 1/64 s), interval policy, packet-like heat parameters.
Truth: closed-form solid angle of the cell seen from its own centre (independent of the package).
"""
import math
from datetime import datetime, timezone

import numpy as np

import hazard_contract as hc

INF = np.inf


def _set():
    ig = np.full((1, 3, 3), INF)
    ex = np.full((1, 3, 3), INF)
    ig[0, 1, 1], ex[0, 1, 1] = 200000.01, 200030.01
    meta = hc.ScenarioMeta(
        crs_epsg=3310, transform=(100.0, 0.0, 0.0, 0.0, -100.0, 300.0), height=3, width=3, K=1,
        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=300000.0, source="model",
        synthetic=False, model_version="test", weather_source="test",
        heat_source=hc.HeatSource(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0,
                                  radiative_fraction=0.3, burn_duration_s=3970.0, burn_duration_policy="interval"))
    return hc.ScenarioSet(ig, ex, np.ones((1, 3, 3), bool), meta)


def test_float32_round_trip_keeps_upper_bounds_above_truth(tmp_path):
    s = _set()
    try:
        s.write(tmp_path / "f32", dtype="float32")
    except (ValueError, hc.ContractError):
        return                                   # refusing a lossy float32 write is also honest
    r = hc.ScenarioSet.read(tmp_path / "f32")
    h = s.meta.heat_source
    dur = s.extinguish_s[0, 1, 1] - s.ignite_s[0, 1, 1]
    q = h.emission_kw_m2(dur)                                   # interval policy: C / duration
    a, gap = 50.0, h.height_gap_m
    omega = 4.0 * math.atan(a * a / (gap * math.sqrt(2 * a * a + gap * gap)))
    true_flux = q * omega / (4 * math.pi)                       # at the cell centre, while burning
    c = s.grid.cell_centers(np.array([1]), np.array([1]))[0]
    t0, t1 = 200010.0, 200020.0                                 # inside the burning interval
    hz = r.member(0).segment(c, t0, t1)
    assert hz.supported
    assert hz.flux_upper >= true_flux, (
        f"float32 file: flux_upper {hz.flux_upper!r} < true flux {true_flux!r} of the written set "
        f"(stored interval [{r.ignite_s[0, 1, 1]!r}, {r.extinguish_s[0, 1, 1]!r}))")
    assert hz.dose_upper >= true_flux * (t1 - t0), (hz.dose_upper, true_flux * (t1 - t0))
