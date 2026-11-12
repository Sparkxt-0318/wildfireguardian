import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seebefore.compute import gap_class, robust_class, tvis  # noqa: E402
from seebefore.fire import FireSet  # noqa: E402


def test_robust_requires_agreement():
    assert robust_class('negative', 'negative') == 'robust_negative'
    assert robust_class('nonneg_visible_now', 'nonneg') == 'robust_nonneg'
    assert robust_class('negative', 'indeterminate_mixed') == 'indeterminate'
    assert robust_class('nonneg_visible_now', 'indeterminate_censored_deadline') == 'indeterminate'
    assert robust_class('negative', 'nonneg') == 'indeterminate'
    assert robust_class('no_route', 'no_route') == 'no_route'


def case(L, by):
    return {'latest_s': L, 'deadline_set_by': by}


def test_no_route():
    assert gap_class(case(None, None), [0.0] * 4, 3600)[0] == 'no_route'


def test_visible_now_is_nonnegative_for_any_deadline_class():
    for by, L in (('grid_end', 3000), ('window', 1800), ('fire_or_limits', 1200)):
        assert gap_class(case(L, by), [0.0] * 4, 3600)[0] == 'nonneg_visible_now'


def test_fire_set_and_unseen_in_hour_is_negative():
    assert gap_class(case(1200, 'fire_or_limits'), [None] * 4, 3600)[0] == 'negative'
    # visible only after the upper bound L+600 in every member -> negative
    assert gap_class(case(1200, 'fire_or_limits'), [1800.0, None, 2000.0, None], 3600)[0] == 'negative'


def test_fire_set_mixed_members():
    # one member sees it before L+600 but after L -> cannot decide
    assert gap_class(case(1200, 'fire_or_limits'), [1500.0, None, None, None], 3600)[0] == 'indeterminate_mixed'
    assert gap_class(case(1200, 'fire_or_limits'), [600.0, 900.0, 1000.0, 1100.0], 3600)[0] == 'nonneg'


def test_censored_or_window_deadline_unseen_is_indeterminate():
    for by, L in (('grid_end', 3000), ('window', 2400)):
        assert gap_class(case(L, by), [None] * 4, 3600)[0] == 'indeterminate_censored_deadline'
        assert gap_class(case(L, by), [100.0] * 4, 3600)[0] == 'nonneg'


def test_tvis_present_then_new_ignition():
    fs = FireSet(scope='x', present_xy=np.array([[0.0, 0.0]]),
                 member_new=[[(500.0, np.array([[375.0, 0.0]]))], []])
    keys_h = {(0, 0): 50.0, (375, 0): 5.0}
    dist = {(0, 0): 1000.0, (375, 0): 20000.0}
    assert tvis(fs, keys_h, dist, 10.0) == [500.0, None]
    assert tvis(fs, keys_h, dist, 10.0, cap=15000.0) == [None, None]
    assert tvis(fs, keys_h, dist, 100.0) == [0.0, 0.0]
