import numpy as np
import pytest
from wfg_scenario_members import accept, weighted_cvar, reduce_scenarios, distances


def test_weighted_acceptance_and_unknown_never_silently_pass():
    assert accept([True, False], rule="k_of_m", k=1, weights=[0.1, 0.9])["outcome"] == "rejected_candidate"
    assert accept([True, None], rule="all")["outcome"] == "unresolved"
    assert accept([False, None], rule="all")["outcome"] == "rejected_candidate"
    assert accept([True, True], rule="all")["outcome"] == "checked_route"


def test_cvar_splits_boundary_mass_and_refusal_costs_horizon():
    assert weighted_cvar([10, None], [0.9, 0.1], alpha=0.2, horizon=100) == pytest.approx(55)


@pytest.mark.parametrize("method", ["first_k", "forward_selection", "k_medoids"])
def test_reduction_preserves_mass_and_extremes_and_cost(method):
    x = np.array([0, 1, 10, 12])
    d = np.abs(x[:, None] - x[None, :]).astype(float)
    out = reduce_scenarios(d, 2, method=method, extreme_indices=[3])
    assert 3 in out["selected_indices"]
    assert sum(out["weights"]) == pytest.approx(1)
    assert out["reduction_cost"] == pytest.approx(np.min(d[:, out["selected_indices"]], axis=1).mean())


def test_distance_rejects_unknowns():
    with pytest.raises(ValueError):
        distances(np.array([[[-2]]], dtype=np.int16), horizon_hours=1)
