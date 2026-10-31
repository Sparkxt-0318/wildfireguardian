"""hazard_contract v1 — the interface between fire-scenario producers and the evacuation oracle.

A scenario set is a folder with ``members.npz`` (``ignite_s``, ``extinguish_s``, ``supported``,
each ``[K, H, W]``) and ``meta.json`` (:class:`ScenarioMeta`). Times are seconds after the
issue time; ``inf`` = never burns within the horizon; ``nan`` = unknown (must be unsupported).

Consumers query members with :meth:`HazardMember.segment` and get a :class:`SegmentHazard`.
Unknown is never unburned: anything that touches unknown data comes back ``supported=False``.
"""
from .adapters import from_drawn_zones, from_perimeters, from_wfg_packet, synthetic
from .geometry import Grid
from .meta import CONTRACT_VERSION, ContractError, HeatSource, ScenarioMeta
from .query import HazardMember, SegmentHazard
from .scenario import DEFAULT_NEAR_RADIUS_M, RasterMember, ScenarioSet

__version__ = "1.0.1"

__all__ = [
    "CONTRACT_VERSION", "ContractError", "DEFAULT_NEAR_RADIUS_M", "Grid", "HazardMember", "HeatSource",
    "RasterMember", "ScenarioMeta", "ScenarioSet", "SegmentHazard", "from_drawn_zones", "from_perimeters",
    "from_wfg_packet", "synthetic",
]
