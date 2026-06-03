"""Tests for the spread_v2 data-driven ignition model.

Pure-logic tests (gridding, weather physics, feature geometry, model
mechanics, forward-sim monotonicity) run everywhere on synthetic inputs.
Real-data integration tests are skipped when the (git-ignored) FIRMS bundle
is not present.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from wildfireguardian.spread_v2 import data, features, grid as gridmod, weather
from wildfireguardian.spread_v2.features import FEATURE_COLUMNS, StaticLayers, geometry_layers
from wildfireguardian.spread_v2.forward_sim import forward_simulate
from wildfireguardian.spread_v2.model import (
    IgnitionModelV2,
    cell_iou,
    _persistence_prediction,
)

DATA = data.data_available()
needs_data = pytest.mark.skipif(not DATA, reason="FIRMS dataset not present (git-ignored)")


# ---------------------------------------------------------------------------
# Weather physics
# ---------------------------------------------------------------------------


def test_relative_humidity_saturated_when_dewpoint_equals_temp():
    rh = weather.relative_humidity_pct(np.array([290.0]), np.array([290.0]))
    assert rh[0] == pytest.approx(100.0, abs=1e-6)


def test_relative_humidity_drops_as_dewpoint_falls():
    rh = weather.relative_humidity_pct(np.array([300.0, 300.0]), np.array([300.0, 280.0]))
    assert rh[0] > rh[1]
    assert 0.0 <= rh[1] <= 100.0


def test_vpd_zero_at_saturation_and_positive_when_dry():
    vpd = weather.vpd_kpa(np.array([300.0, 300.0]), np.array([300.0, 280.0]))
    assert vpd[0] == pytest.approx(0.0, abs=1e-6)
    assert vpd[1] > 0.0


def test_days_since_rain_resets_on_wet_step():
    t = pd.date_range("2025-03-22", periods=5, freq="6h", tz="UTC")
    tp = np.array([0.0, 0.002, 0.0, 0.0, 0.0])  # rain at step 1 (2 mm)
    dsr = weather._days_since_rain(t, tp)
    assert dsr[1] == pytest.approx(0.0, abs=1e-9)       # reset on the wet step
    assert dsr[4] > dsr[2] > 0.0                         # grows afterwards


# ---------------------------------------------------------------------------
# Gridding
# ---------------------------------------------------------------------------


def test_build_grid_covers_bbox_and_indexes_roundtrip():
    g = gridmod.build_grid((129.0, 36.3, 129.3, 36.6), cell_size_m=500.0)
    assert g.nrows > 0 and g.ncols > 0
    x, y = g.center_xy(3, 4)
    assert g.cell_of_xy(x, y) == (3, 4)
    assert g.cell_of_xy(g.minx - 1e6, g.maxy) is None  # outside


def test_cluster_overpasses_splits_on_large_gaps():
    times = pd.to_datetime([
        "2025-03-25 12:00", "2025-03-25 12:05",   # overpass 0
        "2025-03-25 18:00", "2025-03-25 18:03",   # overpass 1 (6 h later)
    ], utc=True)
    ids = gridmod.cluster_overpasses(pd.Series(times), gap_minutes=90.0)
    assert list(ids) == [0, 0, 1, 1]


def test_slope_zero_on_flat_dem():
    flat = np.full((10, 10), 100.0)
    assert np.allclose(gridmod.slope_deg(flat, 500.0), 0.0)


# ---------------------------------------------------------------------------
# Feature geometry
# ---------------------------------------------------------------------------


def test_geometry_distance_to_fire_is_zero_on_active_and_grows_outward():
    active = np.zeros((9, 9), dtype=bool)
    active[4, 4] = True
    dist_m, sr, sc, f1, f2, nadj = geometry_layers(active, 500.0)
    assert dist_m[4, 4] == 0.0
    assert dist_m[4, 5] == pytest.approx(500.0)
    assert dist_m[4, 6] == pytest.approx(1000.0)
    # nearest-source indices point back at the single active cell.
    assert (sr[4, 6], sc[4, 6]) == (4, 4)


def test_geometry_no_active_returns_nan_distance():
    active = np.zeros((5, 5), dtype=bool)
    dist_m, sr, sc, *_ = geometry_layers(active, 500.0)
    assert np.isnan(dist_m).all()
    assert sr is None and sc is None


# ---------------------------------------------------------------------------
# Model mechanics (synthetic, no rasters needed)
# ---------------------------------------------------------------------------


def _synthetic_frame(n=4000, seed=0):
    """A separable synthetic training frame with the real feature columns."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({c: rng.normal(size=n) for c in FEATURE_COLUMNS})
    df["dist_to_fire_m"] = rng.uniform(0, 6000, n)
    # Closer + drier => more likely to ignite (a learnable signal).
    logit = -3.0 - 0.0008 * df["dist_to_fire_m"] + 0.6 * df["days_since_rain"]
    p = 1.0 / (1.0 + np.exp(-logit))
    df["label"] = (rng.uniform(size=n) < p).astype(int)
    df["fire_id"] = "synthetic"
    df["dist_band"] = features.dist_band(df["dist_to_fire_m"].to_numpy())
    return df


def test_model_fits_and_predicts_in_unit_interval():
    df = _synthetic_frame()
    m = IgnitionModelV2().fit(df)
    p = m.predict_proba(df)
    assert p.shape == (len(df),)
    assert p.min() >= 0.0 and p.max() <= 1.0


def test_model_is_reproducible_with_fixed_seed():
    df = _synthetic_frame()
    p1 = IgnitionModelV2(seed=123).fit(df).predict_proba(df)
    p2 = IgnitionModelV2(seed=123).fit(df).predict_proba(df)
    assert np.allclose(p1, p2)


def test_cell_iou_basic():
    a = np.array([[1, 1], [0, 0]], dtype=bool)
    b = np.array([[1, 0], [0, 0]], dtype=bool)
    assert cell_iou(a, a) == 1.0
    assert cell_iou(a, b) == pytest.approx(0.5)
    assert cell_iou(np.zeros((2, 2), bool), np.zeros((2, 2), bool)) == 1.0


def test_persistence_prediction_is_one_cell_ring():
    active = np.zeros((5, 5), dtype=bool)
    active[2, 2] = True
    pred = _persistence_prediction(active)
    assert pred[2, 2] == False          # excludes the already-active cell
    assert pred[1, 2] and pred[2, 1]     # 4-neighbours included
    assert pred[0, 0] == False           # 2 cells away excluded


# ---------------------------------------------------------------------------
# Forward simulation monotonicity (synthetic event)
# ---------------------------------------------------------------------------


def _toy_world(seed=0):
    g = gridmod.build_grid((129.0, 36.3, 129.2, 36.5), cell_size_m=500.0)
    shape = (g.nrows, g.ncols)
    static = StaticLayers(
        elevation=np.full(shape, 200.0),
        slope=np.zeros(shape),
        burnable_frac=np.ones(shape),
    )
    n = 8
    t = pd.date_range("2025-03-25 12:00", periods=n, freq="3h", tz="UTC")
    ws = weather.WeatherSeries(
        time=t,
        wind_speed_ms=np.full(n, 6.0),
        wind_toward_deg=np.full(n, 90.0),
        wind_u=np.full(n, 1.0), wind_v=np.zeros(n),
        temp_c=np.full(n, 15.0), rh_pct=np.full(n, 30.0),
        vpd_kpa=np.full(n, 1.5), days_since_rain=np.full(n, 5.0),
        precip_24h_mm=np.zeros(n),
    )
    event = SimpleNamespace(meta=SimpleNamespace(id="toy"))
    return g, static, ws, event


def test_forward_sim_hazard_is_monotone_nondecreasing():
    g, static, ws, event = _toy_world()
    model = IgnitionModelV2().fit(_synthetic_frame())
    active0 = np.zeros((g.nrows, g.ncols), dtype=bool)
    active0[g.nrows // 2, g.ncols // 2] = True
    sim = forward_simulate(model, event, g, static, active0, ws.time[0], ws,
                           n_steps=3, step_hours=3.0, advance_threshold=0.3)
    assert sim.n_steps == 4  # step 0 (initial) + 3 advances
    for s in range(sim.n_steps - 1):
        # cumulative hazard never decreases and stays in [0, 1]
        assert np.all(sim.hazard[s + 1] + 1e-9 >= sim.hazard[s])
        assert sim.hazard[s].min() >= 0.0 and sim.hazard[s].max() <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# Real-data integration (skipped without the FIRMS bundle)
# ---------------------------------------------------------------------------


@needs_data
def test_yeongdeok_overpasses_and_features_build():
    ev = data.load_event("yeongdeok_2025")
    g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=500.0)
    snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=90.0)
    assert len(snaps) >= 2
    # cumulative footprint only grows
    for k in range(len(snaps) - 1):
        assert snaps[k + 1].cumulative_mask.sum() >= snaps[k].cumulative_mask.sum()
    ws = weather.weather_series_from_event(ev)
    assert ws is not None and len(ws.time) > 0


@needs_data
def test_lofo_auc_is_skilful_and_direction_is_unimportant():
    """The headline: AUC well above chance; wind direction ~ useless."""
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=500.0, buffer_m=6000.0)
    from wildfireguardian.spread_v2.model import leave_one_fire_out

    res = leave_one_fire_out(ds, compute_importance=True)
    assert res.pooled_auc is not None and res.pooled_auc > 0.75
    # Severity (dryness etc.) collectively dominates wind direction.
    sev = sum(res.permutation_importance.get(f, 0.0) for f in features.SEVERITY_FEATURES)
    align = res.permutation_importance.get("wind_alignment", 0.0)
    assert sev > 5.0 * max(align, 1e-6)
