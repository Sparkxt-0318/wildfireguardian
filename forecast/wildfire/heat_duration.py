"""Explicit coarse-cell emission durations derived from front traversal.

Point flame residence and the time a propagating front occupies a finite cell
are separate quantities. This module supplies an optional constant-front cell
duration scenario; it does not infer spread speed or post-frontal combustion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import ArrayLike

if TYPE_CHECKING:
    from .heat import AffineGrid, FlameResidenceTime


_NWCG_RESIDENCE_URL = (
    "https://www.nwcg.gov/publications/pms205/"
    "nwcg-glossary-of-wildland-fire-pms-205/residence-time-94"
)
_FINNEY_POST_FRONTAL_URL = (
    "https://ams.confex.com/ams/FIRE2003/techprogram/paper_66204.htm"
)
_SPREAD_REFERENCE_URL = "https://essd.copernicus.org/articles/15/3791/2023/"
# Benali et al. (2023), section 3.1: median reconstructed forward ROS,
# not a universal fire speed or a calibrated estimate for another incident.
DEFAULT_FRONT_SPREAD_RATE_M_S = 341.0 / 3600.0


@dataclass(frozen=True, eq=False)
class CellBurningDuration:
    """A supplied whole-cell emission-duration scenario in numeric seconds.

    ``duration_s`` must be a strictly positive finite scalar or nonempty [H,W]
    matrix. The duration and JSON-compatible provenance are copied and deeply
    immutable. A duration alone asserts neither ignition nor current activity.
    Direct construction requires explicit provenance for the supplied scenario.
    """

    duration_s: ArrayLike
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        # Local imports keep heat.py free to expose this class after defining
        # its own duration, combustion, and numerical validation utilities.
        from .heat import _freeze_metadata, _immutable_array, _positive

        duration = _positive(self.duration_s, "duration_s")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        object.__setattr__(self, "duration_s", _immutable_array(duration))
        object.__setattr__(self, "provenance", _freeze_metadata(self.provenance))

    def provenance_dict(self) -> dict[str, Any]:
        """Return an independent mutable JSON-ready provenance copy."""
        from .heat import _thaw_metadata

        return _thaw_metadata(self.provenance)

    @classmethod
    def from_front_crossing(
        cls,
        point_residence_time: FlameResidenceTime,
        *,
        grid: AffineGrid,
        spread_rate_m_s: ArrayLike = DEFAULT_FRONT_SPREAD_RATE_M_S,
        spread_direction_deg: ArrayLike = 0.0,
        provenance: Mapping[str, Any] | None = None,
    ) -> CellBurningDuration:
        """Add straight-front cell-crossing time to point flame residence.

        ``spread_direction_deg`` is counterclockwise from the projected +x
        axis and specifies the advancing front's unit normal ``n``. It is not
        a meteorological wind bearing. For cell edge vectors ``u=(a,d)`` and
        ``v=(b,e)`` from ``AffineGrid.transform=(a,b,c,d,e,f)``, the cell's
        width projected onto that normal is ``|n.u| + |n.v|``. Under a straight
        front moving at a constant supplied speed ``R>0``, traversal takes
        ``T_cross=(|n.u|+|n.v|)/R`` and ``T_cell=T_cross+T_point``.

        Scalar and nonempty spatial-matrix inputs must be broadcast compatible.
        The speed default is the reported 341 m/h median forward ROS in
        PT-FireSprd (80 large Portuguese wildfires, 2015-2021). It is a
        reference scenario, not a universal or site-calibrated usual speed.
        This equation follows from projecting the parallelogram's four vertices;
        it is this package's geometric scenario, not an empirical extinction law.

        Supplied arrival times must represent first cell entry/burn start for
        this duration. A center-arrival timestamp requires a separately justified
        conversion. The heat model represents the cell by uniform emission over
        ``[arrival,arrival+T_cell)`` and divides its fixed phase energy by T_cell.
        That rectangular pulse preserves the energy budget but does not resolve
        moving subcell flame geometry or implement trailing/smoldering combustion.
        """
        from .heat import AffineGrid, FlameResidenceTime, _positive, _real_array

        if not isinstance(point_residence_time, FlameResidenceTime):
            raise TypeError("point_residence_time must be FlameResidenceTime")
        if not isinstance(grid, AffineGrid):
            raise TypeError("grid must be AffineGrid")
        rate = _positive(spread_rate_m_s, "spread_rate_m_s")
        direction = _real_array(spread_direction_deg, "spread_direction_deg")
        point = np.asarray(point_residence_time.duration_s)
        try:
            point, rate, direction = np.broadcast_arrays(point, rate, direction)
        except ValueError as error:
            raise ValueError(
                "point residence, spread rate, and spread direction must be broadcast compatible"
            ) from error

        # Reduce finite degrees before conversion so very large finite angles
        # retain periodic semantics without overflowing degrees*pi/180.
        angle = np.deg2rad(np.remainder(direction, 360.0))
        normal_x, normal_y = np.cos(angle), np.sin(angle)
        a, b, _, d, e, _ = grid.transform
        with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
            projected_width = np.abs(normal_x * a + normal_y * d) + np.abs(
                normal_x * b + normal_y * e
            )
            crossing = projected_width / rate
            duration = crossing + point
        if not np.all(np.isfinite(crossing)) or not np.all(np.isfinite(duration)):
            raise ValueError("front traversal and cell duration must remain finite")

        metadata: dict[str, Any] = {
            "method": "straight_constant_front_crossing_plus_point_residence",
            "equation": "T_cell = (abs(n dot u) + abs(n dot v)) / spread_rate_m_s + T_point",
            "equation_origin": "geometric projection of affine-cell vertices; explicit package model assumption",
            "output_unit": "seconds",
            "meaning": "whole-cell emission duration from first front entry until last-point front flame extinction",
            "point_residence_duration_s": np.asarray(point_residence_time.duration_s).tolist(),
            "point_residence_time": point_residence_time.provenance_dict(),
            "spread_rate_m_s": np.asarray(rate).tolist(),
            "spread_rate_selection": (
                "reported median reference value" if np.all(rate == DEFAULT_FRONT_SPREAD_RATE_M_S)
                else "caller-supplied spread-speed scenario"
            ),
            "default_spread_rate_reference": {
                "author_year": "Benali et al. 2023",
                "title": "The Portuguese Large Wildfire Spread database (PT-FireSprd)",
                "url": _SPREAD_REFERENCE_URL, "section": "3.1",
                "reported_statistic": "median reconstructed forward rate of spread",
                "reported_value_m_h": 341.0,
                "converted_value_m_s": DEFAULT_FRONT_SPREAD_RATE_M_S,
                "population": "spread observations from 80 large mainland Portuguese wildfires, 2015-2021",
                "scope": "reference scenario; not a universal speed or a Fish Creek measurement",
            },
            "spread_direction_deg": np.asarray(direction).tolist(),
            "cell_projected_width_m": np.asarray(projected_width).tolist(),
            "cell_crossing_duration_s": np.asarray(crossing).tolist(),
            "affine_transform": list(grid.transform),
            "direction_convention": "counterclockwise degrees from projected +x; advancing front normal; not wind bearing",
            "front_assumption": "straight front with constant normal direction and positive constant speed within each cell",
            "arrival_semantics": "first cell entry/burn start; supplied arrivals are not interpreted as center arrivals",
            "emission_profile": "uniform whole-cell rectangular pulse on [arrival, arrival + T_cell)",
            "energy_policy": "fixed supplied phase-consumed mass times heat yield; conditional HRR divided by T_cell; total phase energy preserved",
            "sources": [
                {
                    "author_year": "NWCG glossary residence time",
                    "url": _NWCG_RESIDENCE_URL,
                    "supported_role": "defines residence as front flaming time at a stationary fuel point; does not provide cell crossing duration",
                },
                {
                    "author_year": "Finney, Seli and Andrews 2003",
                    "url": _FINNEY_POST_FRONTAL_URL,
                    "supported_role": "distinguishes post-frontal flaming and smoldering combustion from perimeter spread; does not supply this geometric crossing law",
                },
            ],
            "limitations": [
                "spread speed and direction are explicit supplied scenarios, not inferred observations",
                "cell occupancy duration differs from point flame residence",
                "uniform rectangular emission does not resolve time-varying burning fraction or moving subcell flame geometry",
                "no automatic trailing, smoldering, reignition, or crown-combustion extension",
                "reconstructed arrival data do not establish actual first-cell-entry time",
            ],
        }
        if provenance is not None:
            if not isinstance(provenance, Mapping):
                raise ValueError("provenance must be a mapping")
            metadata["input_provenance"] = provenance
        return cls(duration, metadata)
