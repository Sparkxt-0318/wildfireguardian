"""wfg_flamefront: radiation law wfg.radiation.law/2-flamefront (opt-in research library, NumPy only).

Public API (Contract C, docs/NEXT_INTERFACES.md):

* ``front_segments(ignition_time_s, t, grid, residence_s)``
* ``flux_at_points(points_xy, times_s, member, grid, fuel, receiver="worst_case")``
* ``flux_enclosure(box_xy, interval_s, member, grid, fuel)``
* ``dose(q, times_s, form="linear" | "tdu")``
* ``provenance()``

Model-relative research construction only; no field validation and no physical-safety claim.
"""
from .field import FrontField, Grid, LawError, load_packet_members, prepare
from .intensity import FuelParameters, byram_flame_length_m, byram_intensity_kw_m, tilt_angle_rad
from .isochrone import front_pieces, front_segments
from .law_v2 import as3959_band, dose, flux_at_points, flux_enclosure, flux_enclosure_many, probit_lethality
from . import provenance as constants   # the module (submodules above already hold it as PV)
from .provenance import LAW_VERSION, provenance   # the package attribute ``provenance`` is the Contract C function

__all__ = ["LAW_VERSION", "provenance", "FrontField", "Grid", "LawError", "load_packet_members", "prepare",
           "FuelParameters", "byram_flame_length_m", "byram_intensity_kw_m", "tilt_angle_rad", "front_pieces",
           "front_segments", "as3959_band", "dose", "flux_at_points", "flux_enclosure", "flux_enclosure_many",
           "probit_lethality"]
