import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import spotlib as S  # noqa: E402


def look(t, sys_, cells):
    r, c = np.array([x[0] for x in cells]), np.array([x[1] for x in cells])
    return S.Look(t, sys_, r, c)


def block(r0, r1, c0, c1):
    return [(r, c) for r in range(r0, r1) for c in range(c0, c1)]


def test_front_spot_growth_confirm():
    shape = (60, 60)
    L = [look(0, "V", block(28, 32, 5, 9)),
         look(4, "V", block(28, 32, 9, 12)),                     # front advances, adjacent
         look(5, "V", block(28, 32, 12, 13) + block(29, 31, 20, 22)),  # front + detached cluster 7 cells ahead (2.6 km)
         look(6, "V", block(29, 31, 22, 23)),                    # spot grows
         look(9, "V", block(28, 32, 13, 20))]                    # front fills the gap later -> confirmed
    spots, A = S.find_spots(L, shape)
    assert len(spots) == 1
    s = spots[0]
    assert s["confirmed"] and abs(s["dist_km"] - 9 * 0.375) < 1e-6 and abs(s["dist_now_km"] - 8 * 0.375) < 1e-6 and s["growth_cells"] == 2
    assert A["label"][30, 22] == S.GROWTH and A["label"][30, 15] == S.FRONT


def test_not_searched_when_stale_and_separate():
    shape = (80, 80)
    L = [look(0, "V", block(28, 32, 5, 9)),
         look(4, "V", block(28, 32, 9, 10)),
         look(9, "V", block(29, 31, 20, 22)),      # 5 h after the last look: not searched
         look(10, "V", block(29, 31, 70, 72))]     # > 15 km away: separate
    spots, A = S.find_spots(L, shape)
    assert len(spots) == 0
    assert A["label"][30, 20] == S.UNSEARCHED and A["label"][30, 70] == S.SEPARATE


def test_interior_island():
    shape = (60, 60)
    ring = [(r, c) for r in range(10, 40) for c in range(10, 40) if not (18 <= r < 32 and 18 <= c < 32)]
    L = [look(0, "V", ring[: len(ring) // 2]), look(4, "V", ring[len(ring) // 2:]), look(5, "V", block(24, 26, 24, 26))]
    spots, A = S.find_spots(L, shape)
    assert len(spots) == 0 and A["label"][24, 24] == S.INTERIOR


def test_angle():
    # wind from west (270) -> downwind is east (90)
    assert S.angle_to_downwind(90.0, 270.0) == 0
    assert S.angle_to_downwind(270.0, 270.0) == 180
    assert S.bearing_deg(0, 1) == 90 and S.bearing_deg(-1, 0) == 0
