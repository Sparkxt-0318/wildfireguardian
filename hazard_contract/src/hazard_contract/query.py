"""Query protocol: what a consumer may ask of one scenario member."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class SegmentHazard:
    """Hazard experienced by a vehicle occupying a geometry during ``[t_in, t_out]`` in one member.

    contact
        ``True``: some supported cell the geometry touches is burning at some instant of the
        occupancy interval (certain, whatever unknown cells hold). ``False``: no touched cell
        burns during the interval and every touched cell is supported. ``None``: unknown.
    flux_lower, flux_upper (kW/m^2)
        Bounds on the PEAK incident radiative flux the occupant experiences, valid for any
        speed profile along the geometry. ``flux_upper`` treats unknown cells as burning and is
        ``inf`` when nothing bounds it (the geometry touches the grid's outside, or the interval
        passes the horizon).
    dose_lower, dose_upper (kJ/m^2)
        Bounds on the time-integrated flux over the occupancy interval (same conventions).
    supported
        ``False`` if any touched cell is unknown, the geometry touches the grid's outside, or
        ``t_out`` exceeds the scenario horizon. Consumers must treat unsupported as unresolved,
        never as safe.
    """

    contact: bool | None
    flux_lower: float
    flux_upper: float
    supported: bool
    dose_lower: float = 0.0
    dose_upper: float = math.inf

    def __post_init__(self) -> None:
        if self.contact not in (True, False, None):
            raise TypeError("contact must be True, False or None")
        for name in ("flux_lower", "flux_upper", "dose_lower", "dose_upper"):
            if math.isnan(getattr(self, name)):
                raise ValueError(f"{name} is NaN")
        if not (0.0 <= self.flux_lower <= self.flux_upper):
            raise ValueError(f"need 0 <= flux_lower <= flux_upper, got {self.flux_lower}, {self.flux_upper}")
        if not (0.0 <= self.dose_lower <= self.dose_upper):
            raise ValueError(f"need 0 <= dose_lower <= dose_upper, got {self.dose_lower}, {self.dose_upper}")
        if self.contact is False and not self.supported:
            raise ValueError("contact=False requires supported=True")


@runtime_checkable
class HazardMember(Protocol):
    """One scenario member. A stationary position (waiting, a destination stay) is a
    zero-length geometry (a single point) over its occupancy interval."""

    def segment(self, geom_xy: np.ndarray, t_in: float, t_out: float) -> SegmentHazard: ...
