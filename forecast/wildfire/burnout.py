"""Flaming-window sources: burned cells stop acting as full sources after burnout.

The released transition treats every burned cell as a source forever. Here a
cell contributes with weight one while its age since ignition is below the
flaming residence ``t_r`` (hours) and with a smouldering multiplier
``m`` in [0, 1] afterwards. In the mean field, with ignition probability
``p_ign(t)``, the source field is

    s(t) = [p_ign(t) - p_ign(t - t_r)] + m * p_ign(t - t_r),

so ``m = 1`` (or ``t_r = inf``) recovers the absorbing model and ``m = 0``
gives ``p_burning(t) = p_ign(t) - p_ign(t - t_r)``. A step's new occupancy
is assigned the step midpoint as its ignition time.

Time scale. ``heat.FlameResidenceTime.from_fbfm40`` gives the *point* flame
residence of a reference fuel bed (Anderson's 384/sigma minutes), typically
one to a few minutes. A 375 m cell keeps burning for the time the front
needs to cross it plus that residence, which is hours at observed spread
rates. :func:`cell_window_hours` therefore adds the point residence to a
crossing time; with the point residence alone every hourly source would
vanish within its own step. The scalar crossing time is a modelling choice
recorded with every fit, not a measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import numpy as np
import torch
from torch import Tensor

__all__ = ["FlamingWindow", "cell_window_hours", "source_weight"]


def source_weight(age_hours: Tensor, residence_hours: Tensor | Real, smoulder: Tensor | Real) -> Tensor:
    """Weight one for ``0 <= age < t_r``, ``smoulder`` for ``age >= t_r``."""
    residence = torch.as_tensor(residence_hours, dtype=age_hours.dtype, device=age_hours.device)
    m = torch.as_tensor(smoulder, dtype=age_hours.dtype, device=age_hours.device)
    return torch.where(age_hours < residence, torch.ones_like(age_hours), m)


@dataclass
class FlamingWindow:
    """Source law ``s = sum_k dp_k * w(t - tau_k)`` for the mean field.

    ``residence_hours`` is a positive scalar or a tensor broadcastable to the
    grid; ``smoulder`` is a scalar or a 0-d tensor (it may require grad).
    """

    residence_hours: Tensor | Real
    smoulder: Tensor | Real = 0.0

    def __post_init__(self):
        value = torch.as_tensor(self.residence_hours)
        if not bool(torch.isfinite(value).all()) or bool((value <= 0).any()):
            raise ValueError("residence_hours must be finite and positive")
        m = torch.as_tensor(self.smoulder)
        if m.ndim != 0 or not bool(torch.isfinite(m)) or not 0 <= float(m) <= 1:
            raise ValueError("smoulder must be a scalar in [0, 1]")

    def source(self, initial: Tensor, initial_age_hours: Tensor, history, clock_hours: float,
               current: Tensor | None = None) -> Tensor:
        """Source field at ``clock_hours`` after the cutoff.

        ``initial`` is the cutoff occupancy with ages ``initial_age_hours``;
        ``history`` lists ``(ignition_time_hours, increment)`` of earlier steps.
        When ``current`` (= initial + all increments) is supplied and the
        residence is a scalar, the identical value is computed as
        ``m * current + (1 - m) * flaming`` from the young increments only.
        """
        residence = torch.as_tensor(self.residence_hours)
        if current is not None and residence.ndim == 0:
            m = torch.as_tensor(self.smoulder, dtype=current.dtype, device=current.device)
            young = initial * (initial_age_hours + clock_hours < residence).to(current.dtype)
            for ignition_time, increment in reversed(history):
                if clock_hours - ignition_time >= float(residence):
                    break
                young = young + increment
            return m * current + (1 - m) * young
        total = initial * source_weight(initial_age_hours + clock_hours, self.residence_hours, self.smoulder)
        for ignition_time, increment in history:
            age = torch.full_like(increment, clock_hours - ignition_time)
            total = total + increment * source_weight(age, self.residence_hours, self.smoulder)
        return total


def cell_window_hours(crossing_hours: float, fbfm40_codes: np.ndarray | None = None,
                      fallback_sav_m_inv: float | None = None) -> np.ndarray | float:
    """Flaming window of a 375 m cell: crossing time plus point residence.

    Without fuel codes the scalar ``crossing_hours`` is returned. With
    Scott and Burgan codes, the point residence from
    ``heat.FlameResidenceTime.from_fbfm40`` (seconds) is added per cell.
    """
    if not np.isfinite(crossing_hours) or crossing_hours <= 0:
        raise ValueError("crossing_hours must be finite and positive")
    if fbfm40_codes is None:
        return float(crossing_hours)
    from .heat import FlameResidenceTime
    residence = FlameResidenceTime.from_fbfm40(fbfm40_codes, fallback_sav_m_inv=fallback_sav_m_inv)
    return crossing_hours + np.asarray(residence.duration_s, dtype=np.float64) / 3600.0
