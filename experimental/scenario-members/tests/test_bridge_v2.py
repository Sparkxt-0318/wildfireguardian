import importlib.util
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("_bridge_v2_test", ROOT / "experimental/scenario-members/bridge_v2.py")
bridge = importlib.util.module_from_spec(spec); spec.loader.exec_module(bridge)


def raw_fixture():
    field = np.zeros((3, 3), dtype=float)
    valid = np.ones((3, 3), dtype=bool)
    return dict(new_burn_probability=field.copy(), probability_valid=valid.copy(),
                rate_per_h=field.copy(), rate_valid=valid.copy(), source_burned_area=field.copy(),
                source_burned_area_valid=valid.copy(), affine_transform=np.array([10., 0., 0., 0., -10., 30.]),
                heat__initial_active_burning_probability=field.copy(),
                heat__initial_remaining_burning_duration_s=field.copy(), heat__initial_burning_valid=valid.copy())


def test_native_members_and_unknown_support_are_preserved():
    f = raw_fixture()
    f["new_burn_probability"][1, 1] = 0.5
    first = np.full((2, 3, 3), -1, dtype=np.int16); first[0, 1, 1] = 1; first[1, 2, 0] = -2
    f["trajectory_first_burn_hour"] = first
    built = bridge.construct(f, cutoff_utc="2025-01-01T00:00:00Z", epsg=5179,
                             settings=bridge.v1.settings_for(100))
    assert len(built["members"]) == 2
    assert np.isfinite(built["events"][0, 1, 1])
    assert built["masks"]["trajectory_unknown"][1, 2, 0]
    assert built["settings"]["source_law_version"] == "wfg.hazard.construction/1"
    assert built["settings"]["construction_version"] == "wfg.hazard.construction/2"


def test_sub_hour_times_are_stable_under_selection_and_reordering():
    first = np.ones((3, 3, 3), dtype=np.int16)
    full = bridge.ignition_seconds(first, seed=7)
    selected = bridge.ignition_seconds(first[[2, 0]], seed=7, trajectory_indices=[2, 0])
    np.testing.assert_array_equal(full[[2, 0]], selected)
