import os
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "adapters"))

REPO = ROOT.parents[1]
INPUTS = Path(os.environ.get("WFG_ROUTING_INPUTS", "/home/user/wfg-shared/routing-inputs"))


def synthetic_member(seed=7, H=14, W=16, cell=375.0):
    """A coherent synthetic fire: present-fire block, new ignitions spreading outward, burned-out cells, one unknown."""
    rng = np.random.default_rng(seed)
    yy, xx = np.indices((H, W)).astype(float)
    r = np.hypot(yy - 6.0, xx - 5.0)
    ign = np.full((H, W), np.inf)
    spread = r * cell / 0.12           # seconds at 0.12 m/s from the centre, offset so that some cells are past
    ign_t = spread - 2500.0 + rng.uniform(-200, 200, size=(H, W))
    new = (ign_t > 0) & (ign_t < 3600)
    ign[new] = ign_t[new]
    cur = (ign_t <= 0) & (ign_t > -1500)
    burned = ign_t <= 0
    unknown = np.zeros((H, W), bool)
    unknown[2, 12] = True
    ign[2, 12] = np.inf
    member = {"ignition_time_s": ign, "current_active": cur, "remaining_s": 3000.0, "known_burned": burned,
              "unknown_state": unknown, "burning_duration_s": 3970.4642815249267, "horizon_s": 3600.0}
    grid = (cell, 0.0, 1000.0, 0.0, -cell, 1000.0 + H * cell)
    return member, grid


@pytest.fixture
def synth():
    import wfg_flamefront as W
    member, transform = synthetic_member()
    grid = W.Grid(transform, member["ignition_time_s"].shape[0], member["ignition_time_s"].shape[1])
    return member, grid
