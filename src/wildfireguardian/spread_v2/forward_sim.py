"""Forward-simulate the spread_v2 model into a time-sequenced hazard surface.

Deliverable 0. The single-step model predicts P(cell ignites by the next
overpass | current active set, weather). To get an *evacuation-horizon*
hazard we iterate it:

1. Start from an early observed fire state ``A_0`` (a real overpass footprint).
2. At step ``s`` (clock ``t_s``): build features for every unburned candidate
   around ``A_s`` using the real ERA5 weather at ``t_s``; predict per-cell
   ignition probability ``p_s``.
3. Accumulate a **soft cumulative hazard** surface (the probability the cell
   has ignited by ``t_s``):  ``H_{s+1} = H_s + (1 - H_s) * p_s``  (monotone
   non-decreasing — the reach envelope only grows).
4. Advance a **hard "likely-burned" set** ``A_{s+1} = A_s ∪ {p_s >= τ}`` to
   drive the geometry features of the next step.
5. Repeat over the horizon with the next step's real weather.

**Compounding error (stated plainly):** each step's prediction conditions on
the *previous step's predicted* advance, so errors accumulate; the simulated
envelope drifts from what actually burned. :func:`drift_vs_observed`
quantifies that drift (IoU + area ratio) against the real overpass footprints.

The output :class:`ForwardSim` is exactly what the routing layer consumes —
a sequence of per-cell ignition-probability surfaces in EPSG:5179. It is kept
probabilistic (0-1), never binarised, so the router can weight by risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import grid as gridmod
from .features import StaticLayers, build_candidate_frame
from .model import IgnitionModelV2, cell_iou
from .weather import WeatherSeries


@dataclass
class ForwardSim:
    """A forward-simulated, time-sequenced probabilistic hazard for one fire."""

    fire_id: str
    grid: gridmod.CoarseGrid
    start_time: pd.Timestamp
    step_minutes: list[float]                 # minutes from start at each surface
    step_times: list[pd.Timestamp]
    hazard: list[np.ndarray]                  # cumulative P(ignited by t_s), 0-1
    ignition_prob: list[np.ndarray]           # per-step incremental P(ignite this step)
    active: list[np.ndarray]                  # hard "likely burned" mask per step
    advance_threshold: float = 0.5
    notes: list[str] = field(default_factory=list)

    @property
    def n_steps(self) -> int:
        return len(self.hazard)

    def envelope_area_ha(self, step: int, p_cut: float = 0.5) -> float:
        cell_ha = (self.grid.cell_size_m ** 2) / 1e4
        return float((self.hazard[step] >= p_cut).sum() * cell_ha)


def forward_simulate(
    model: IgnitionModelV2,
    event,
    grid: gridmod.CoarseGrid,
    static: StaticLayers,
    initial_active: np.ndarray,
    start_time: pd.Timestamp,
    weather: WeatherSeries | None,
    *,
    n_steps: int = 4,
    step_hours: float = 3.0,
    advance_threshold: float = 0.5,
    buffer_m: float = 6000.0,
) -> ForwardSim:
    """Iterate the single-step model into a hazard sequence (see module doc)."""
    A = initial_active.copy()
    H = A.astype(float).copy()  # already-burned cells are certain hazard
    hazards = [H.copy()]
    ign_probs = [np.zeros_like(H)]
    actives = [A.copy()]
    step_minutes = [0.0]
    step_times = [pd.Timestamp(start_time)]

    for s in range(n_steps):
        when = pd.Timestamp(start_time) + pd.Timedelta(hours=step_hours * s)
        frame = build_candidate_frame(
            event, grid, static, A, when, step_hours, weather, buffer_m=buffer_m)
        p_surface = np.zeros_like(H)
        if not frame.empty:
            p = model.predict_proba(frame)
            rr = frame["row"].to_numpy()
            cc = frame["col"].to_numpy()
            p_surface[rr, cc] = p
            # Advance the hard likely-burned set.
            adv = p >= advance_threshold
            A = A.copy()
            A[rr[adv], cc[adv]] = True
        # Soft cumulative hazard (survival accumulation), clamp burned to 1.
        H = H + (1.0 - H) * p_surface
        H = np.maximum(H, A.astype(float))
        hazards.append(H.copy())
        ign_probs.append(p_surface)
        actives.append(A.copy())
        step_minutes.append(step_hours * (s + 1) * 60.0)
        step_times.append(when + pd.Timedelta(hours=step_hours))

    return ForwardSim(
        fire_id=event.meta.id, grid=grid, start_time=pd.Timestamp(start_time),
        step_minutes=step_minutes, step_times=step_times,
        hazard=hazards, ignition_prob=ign_probs, active=actives,
        advance_threshold=advance_threshold,
        notes=[
            f"forward-simulated {n_steps} steps x {step_hours} h from observed state; "
            "compounding error accumulates each step.",
        ],
    )


# ---------------------------------------------------------------------------
# Drift vs observed + envelope breadth diagnostics
# ---------------------------------------------------------------------------


@dataclass
class DriftRow:
    step: int
    minutes: float
    pred_area_ha: float
    obs_area_ha: float
    iou: float
    captured_frac: float        # fraction of observed footprint inside predicted
    nearest_obs_op: int


def drift_vs_observed(
    sim: ForwardSim,
    overpasses: list[gridmod.Overpass],
    *,
    p_cut: float = 0.5,
) -> list[DriftRow]:
    """Compare the forward-simulated envelope to the real overpass footprints."""
    cell_ha = (sim.grid.cell_size_m ** 2) / 1e4
    op_times = np.array([op.time.value for op in overpasses])
    rows: list[DriftRow] = []
    for s in range(sim.n_steps):
        pred = sim.hazard[s] >= p_cut
        t = sim.step_times[s].value
        j = int(np.argmin(np.abs(op_times - t)))
        obs = overpasses[j].cumulative_mask
        inter = np.logical_and(pred, obs).sum()
        captured = float(inter / obs.sum()) if obs.sum() else float("nan")
        rows.append(DriftRow(
            step=s, minutes=sim.step_minutes[s],
            pred_area_ha=float(pred.sum() * cell_ha),
            obs_area_ha=float(obs.sum() * cell_ha),
            iou=cell_iou(pred, obs),
            captured_frac=captured,
            nearest_obs_op=overpasses[j].index,
        ))
    return rows


def envelope_breadth_deg(sim: ForwardSim, step: int, ignition_xy: tuple[float, float],
                         *, p_cut: float = 0.3, min_dist_m: float = 2000.0) -> float:
    """Angular span (deg) of the hazard envelope around the ignition point.

    A thin directional jet covers a small arc; a broad severity-driven reach
    covers a wide one. Measured as the circular spread of bearings to hazard
    cells beyond ``min_dist_m`` (so adjacent-cell growth doesn't dominate).
    """
    X, Y = sim.grid.center_grids()
    haz = sim.hazard[step] >= p_cut
    dx = X - ignition_xy[0]
    dy = Y - ignition_xy[1]
    dist = np.hypot(dx, dy)
    sel = haz & (dist >= min_dist_m)
    if sel.sum() < 3:
        return 0.0
    bearings = np.arctan2(dx[sel], dy[sel])  # radians
    # Circular standard deviation -> approximate angular span.
    R = np.hypot(np.cos(bearings).mean(), np.sin(bearings).mean())
    R = min(max(R, 1e-9), 1.0)
    circ_std = np.sqrt(-2.0 * np.log(R))
    return float(np.degrees(min(circ_std, np.pi)))


__all__ = [
    "ForwardSim",
    "forward_simulate",
    "DriftRow",
    "drift_vs_observed",
    "envelope_breadth_deg",
]
