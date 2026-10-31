"""Scoring domain and scoring masks on SYNTHETIC grids (375 m cells, as in every event grid)."""
import numpy as np
import pytest

from firecast_lab import domain as d

CELL = 375.0


def _disk_count(radius_cells: float, quadrant: bool = False) -> int:
    r = int(radius_cells)
    span = range(0, r + 1) if quadrant else range(-r, r + 1)
    return sum(1 for i in span for j in span if i * i + j * j <= radius_cells ** 2)


def test_headline_buffer_is_three_km_by_cell_centres():
    perimeter = np.zeros((21, 21), bool)
    perimeter[10, 10] = True                                                   # SYNTHETIC one-cell fire
    dom = d.headline_domain(perimeter, CELL)
    assert d.HEADLINE_BUFFER_M == 3000.0
    assert dom.sum() == _disk_count(8) == 197                                  # Gauss circle count for r = 8
    assert dom[10, 18] and dom[10, 2] and not dom[10, 19]                      # 3000 m on an axis is inside
    assert d.headline_domain(perimeter, 500.0).sum() == _disk_count(6)        # 3000 m = 6 cells of 500 m


def test_ring_beyond_the_grid_is_counted_not_scored():
    perimeter = np.zeros((21, 21), bool)
    perimeter[0, 0] = True                                                     # SYNTHETIC fire in a corner
    dom = d.headline_domain(perimeter, CELL)
    assert dom.sum() == _disk_count(8, quadrant=True) == 58
    assert d.ring_cells_off_grid(perimeter, CELL) == 197 - 58
    centred = np.zeros((21, 21), bool)
    centred[10, 10] = True
    assert d.ring_cells_off_grid(centred, CELL) == 0


def test_scoring_mask_intersects_domain_labels_cutoff_state_and_every_model():
    dom = np.array([True, True, True, True, False])
    known = np.array([True, True, True, False, True])
    burned_at_cutoff = np.array([True, False, False, False, False])
    model_a = np.array([True, True, False, True, True])
    model_b = np.array([True, True, True, True, True])
    mask = d.scoring_mask(dom, known, burned_at_cutoff, model_a, model_b)
    assert mask.tolist() == [False, True, False, False, False]
    assert d.scoring_mask(dom, known, burned_at_cutoff).tolist() == [False, True, True, False, False]
    assert d.full_rectangle((2, 3)).all()
    with pytest.raises(ValueError):
        d.scoring_mask(dom, known[:4], burned_at_cutoff)
    with pytest.raises(ValueError):
        d.headline_domain(np.zeros((3, 3), bool), CELL)
