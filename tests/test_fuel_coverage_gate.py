"""The fuel-coverage gate — Round-3 PHASE 13.

WHAT IS BEING GUARDED
---------------------
``spread_v2.grid.burnable_fraction_on_grid`` reprojects the WorldCover mask onto
the simulation grid. Where the raster does not reach, the cell reads 0 — and
``spread_v2.features.build_transition_frame`` gates candidacy on
``burnable_frac > 0.05``, so such a cell is EXCLUDED FROM PREDICTION, not merely
down-weighted. Before this gate existed, nothing raised and nothing logged.

⚠ THE MEASURE IS UNCOVERED **LAND**, NOT UNCOVERED AREA. A coastal bbox is
legitimately uncovered over the sea. ``gangneung_2023`` is 17.61 % uncovered and
17.2 pp of that is the East Sea — a plain uncovered-area gate would fire on it
for a correct reason, which is how a gate becomes noise and then gets ignored.
The tests below pin that distinction, because it is the whole design.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

MANIFEST = REPO / "data" / "raw" / "firms_data" / "fire_manifest.json"

pytestmark = pytest.mark.skipif(
    not MANIFEST.exists(),
    reason="FIRMS bundle absent in this environment",
)


def _cov(fire_id: str) -> dict:
    from wildfireguardian.spread_v2 import data as datamod, grid as gridmod

    ev = datamod.load_event(fire_id)
    g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=500.0)
    return gridmod.fuel_coverage(ev, g)


# ---------------------------------------------------------------------------
# The measurement
# ---------------------------------------------------------------------------


def test_thresholds_come_from_config_not_from_a_literal():
    """The brief was explicit: the threshold lives in config."""
    import yaml

    cfg = yaml.safe_load((REPO / "config" / "default.yaml").read_text(encoding="utf-8"))
    assert cfg["fuel"]["uncovered_land_warn_fraction"] == 0.01
    assert cfg["fuel"]["uncovered_land_stop_fraction"] == 0.05

    import run_forward_sim_region as runner

    assert runner.FUEL_UNCOVERED_WARN == cfg["fuel"]["uncovered_land_warn_fraction"]
    assert runner.FUEL_UNCOVERED_STOP == cfg["fuel"]["uncovered_land_stop_fraction"]


def test_fuel_coverage_never_raises_it_only_measures():
    """The library half is a measurement. The gate is a separate, explicit call."""
    cov = _cov("miryang_2022")
    assert set(cov) >= {
        "n_cells", "n_uncovered", "frac_uncovered",
        "n_uncovered_land", "frac_uncovered_land", "uncovered_land_km2",
    }
    assert 0.0 <= cov["frac_uncovered"] <= 1.0
    assert cov["frac_uncovered_land"] <= cov["frac_uncovered"]


def test_miryang_has_the_missing_worldcover_tile():
    """The defect this gate was built for.

    ESA WorldCover ships 3 x 3 degree tiles. miryang_2022's analysis bbox runs to
    129.05 E but only N36E126 was fetched, so the raster stops dead at 129.000 E.
    """
    cov = _cov("miryang_2022")
    assert cov["frac_uncovered_land"] > 0.05, "the stop threshold must be exceeded"
    assert cov["n_uncovered_land"] > 500
    assert cov["uncovered_land_km2"] > 150


def test_coastal_fires_are_uncovered_over_the_sea_and_that_is_correct():
    """⚠ The reason the gate measures LAND and not area.

    gangneung_2023 is more uncovered than miryang by area, and it is fine: the
    uncovered part is the East Sea. Gating on area would fire on the wrong fire.
    """
    gangneung = _cov("gangneung_2023")
    miryang = _cov("miryang_2022")

    assert gangneung["frac_uncovered"] > miryang["frac_uncovered"], (
        "gangneung is the more uncovered by AREA")
    assert gangneung["frac_uncovered_land"] < miryang["frac_uncovered_land"], (
        "...and the less uncovered by LAND, which is the quantity that matters")
    assert gangneung["frac_uncovered_land"] < 0.01, "sea, not a missing tile"


@pytest.mark.parametrize("fire_id", [
    "yeongdeok_2025", "gangneung_donghae_2022", "goseong_2019", "hongseong_2023",
])
def test_fully_tiled_fires_read_exactly_zero_uncovered_land(fire_id):
    """The null result that makes the gate believable.

    Wherever the tiles were fully fetched, uncovered-LAND is 0.00 % — not "small",
    zero. That is what licenses a 1 % warn threshold.
    """
    assert _cov(fire_id)["n_uncovered_land"] == 0


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_gate_stops_on_miryang_and_the_stop_is_not_silenceable():
    import run_forward_sim_region as runner

    cov = _cov("miryang_2022")
    with pytest.raises(runner.FuelGapError) as exc:
        runner.check_fuel_coverage("miryang_2022", cov, acknowledged=False)
    assert "burnable_frac" in str(exc.value), "the message must say WHY it matters"

    # Acknowledging proceeds — and records, rather than hides.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = runner.check_fuel_coverage("miryang_2022", cov, acknowledged=True)
    assert report["verdict"] == "stop"
    assert report["acknowledged_via_flag"] is True
    assert report["frac_uncovered_land"] == cov["frac_uncovered_land"], (
        "acknowledging must not alter the measurement")


def test_gate_warns_on_uiseong_and_passes_the_rest():
    import run_forward_sim_region as runner

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        r = runner.check_fuel_coverage(
            "uiseong_andong_2025", _cov("uiseong_andong_2025"), acknowledged=False)
    assert r["verdict"] == "warn"
    assert caught, "a warn verdict must actually emit a warning"

    for fire_id in ("yeongdeok_2025", "uljin_samcheok_2022", "gangneung_2023"):
        assert runner.check_fuel_coverage(
            fire_id, _cov(fire_id), acknowledged=False)["verdict"] == "ok"


def test_exit_code_is_distinct_from_the_dem_gap():
    """A caller must be able to tell WHICH input layer failed without parsing text."""
    import run_forward_sim_region as runner
    import run_multi_region_routing as mr

    assert runner.EXIT_FUEL_GAP == 6
    assert mr.EXIT_DEM_GAP == 5
    assert runner.EXIT_FUEL_GAP != mr.EXIT_DEM_GAP


def test_the_report_is_written_into_the_artifact():
    """An acknowledged gap that is not recorded is a hidden gap."""
    src = (REPO / "scripts" / "run_forward_sim_region.py").read_text(encoding="utf-8")
    assert '"fuel_coverage": fuel_report' in src
    assert "--acknowledge-fuel-gap" in src


def test_committed_miryang_numbers_are_not_contaminated_by_the_gap():
    """⚠ The gap is real and the reported figures are still clean — say both.

    miryang's easternmost detection is 128.777 E; the fuel raster stops at
    129.000 E; the candidate buffer is 6 km (config grid.feature_buffer_m). The
    gap is ~20 km beyond the furthest candidate, so it was never sampled. That is
    luck, not design, which is why the gate exists — but it means no committed
    number moves.
    """
    from wildfireguardian.spread_v2 import data as datamod

    det = datamod.load_event("miryang_2022").detections
    assert det["longitude"].max() < 128.80
    east_of_gap = int((det["longitude"] > 129.000).sum())
    assert east_of_gap == 0, "no detection lies inside the uncovered strip"
