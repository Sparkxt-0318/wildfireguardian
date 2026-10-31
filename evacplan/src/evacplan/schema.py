"""Problem v0 instance and solution schema (pydantic v2) with JSON I/O.

Clock and space
---------------
* Instance times are seconds on the instance clock. The hazard clock (seconds after the scenario
  set's issue time) is ``t + hazard.t0_offset_s``.
* Coordinates are metres in the hazard CRS (``graph.crs_epsg`` must equal the scenario set's
  ``crs_epsg``; the oracle refuses a mismatch).

Instance
--------
Road graph (nodes with ``waitable``; directed edges with ``travel_time_s`` and an optional polyline,
default the straight chord u->v; forbidden turns as ``[in_edge, out_edge]``), facilities (residents
and boarding time per mobility class, release time), vehicles (depot, start time, seats, wheelchair
slots, stretcher slots, shift limit), shelters (capacity per class, closed opening windows,
unloading time per class), the hazard reference (scenario-set folder relative to the instance file,
``t0_offset_s``, peak and dose budgets) and the ``synthetic`` label.

Solution
--------
Per vehicle an ordered list of actions: ``drive`` (explicit edge path and departure time),
``wait`` (waitable node, duration), ``board`` (facility, counts per class) and ``unload``
(shelter, counts per class). Waits, boardings and unloadings start when the previous action ends;
their durations follow from the instance. A drive departing later than the vehicle's clock leaves
an implicit idle period at the current node, which obeys the waiting rules (see
:mod:`evacplan.validate` and ``docs/ASSUMPTIONS.md``).

Mobility classes map one-to-one to vehicle space: ambulatory -> seat, wheelchair -> wheelchair
slot, bedbound -> stretcher slot.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

if TYPE_CHECKING:  # pragma: no cover
    import hazard_contract

INSTANCE_SCHEMA = "evacplan.instance/0"
SOLUTION_SCHEMA = "evacplan.solution/0"
CLASSES: tuple[str, str, str] = ("ambulatory", "wheelchair", "bedbound")
VEHICLE_SPACE: tuple[str, str, str] = ("seats", "wheelchair_slots", "stretcher_slots")  # per class, same order
GEOMETRY_TOL_M = 1e-6

NonNegInt = Annotated[int, Field(ge=0, strict=True)]
NonNegFloat = Annotated[float, Field(ge=0)]
Point = tuple[float, float]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def _dupes(ids) -> list[str]:
    return sorted(k for k, n in Counter(ids).items() if n > 1)


# ----------------------------------------------------------------------------------- classes
class ClassCounts(_Model):
    """Residents per mobility class."""

    ambulatory: NonNegInt = 0
    wheelchair: NonNegInt = 0
    bedbound: NonNegInt = 0

    def vector(self) -> tuple[int, int, int]:
        return (self.ambulatory, self.wheelchair, self.bedbound)

    @property
    def total(self) -> int:
        return self.ambulatory + self.wheelchair + self.bedbound

    @classmethod
    def of(cls, v) -> "ClassCounts":
        return cls(ambulatory=int(v[0]), wheelchair=int(v[1]), bedbound=int(v[2]))


class ClassDurations(_Model):
    """Seconds per resident of each mobility class."""

    ambulatory: NonNegFloat
    wheelchair: NonNegFloat
    bedbound: NonNegFloat

    def vector(self) -> tuple[float, float, float]:
        return (self.ambulatory, self.wheelchair, self.bedbound)

    def duration(self, counts: ClassCounts) -> float:
        """Total seconds for ``counts`` residents (the validator's definition)."""
        n = counts.vector()
        d = self.vector()
        return float(n[0] * d[0] + n[1] * d[1] + n[2] * d[2])


# -------------------------------------------------------------------------------- road graph
class Node(_Model):
    id: str = Field(min_length=1)
    x: float
    y: float
    waitable: bool = False


class Edge(_Model):
    id: str = Field(min_length=1)
    u: str
    v: str
    travel_time_s: float = Field(gt=0)
    geometry: Annotated[list[Point], Field(min_length=2)] | None = Field(
        default=None, description="polyline u -> v in the hazard CRS; default: the straight chord")


class RoadGraph(_Model):
    crs_epsg: int
    nodes: list[Node] = Field(min_length=1)
    edges: list[Edge] = Field(default_factory=list)
    forbidden_turns: list[tuple[str, str]] = Field(default_factory=list, description="[in_edge, out_edge] pairs")
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _references(self) -> "RoadGraph":
        nodes = {n.id: n for n in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError(f"duplicate node ids {_dupes(n.id for n in self.nodes)[:5]}")
        edges = {e.id: e for e in self.edges}
        if len(edges) != len(self.edges):
            raise ValueError(f"duplicate edge ids {_dupes(e.id for e in self.edges)[:5]}")
        for e in self.edges:
            if e.u not in nodes or e.v not in nodes:
                raise ValueError(f"edge {e.id!r} references an unknown node")
            if e.geometry is not None:
                (x0, y0), (x1, y1) = e.geometry[0], e.geometry[-1]
                u, v = nodes[e.u], nodes[e.v]
                if math.hypot(x0 - u.x, y0 - u.y) > GEOMETRY_TOL_M or math.hypot(x1 - v.x, y1 - v.y) > GEOMETRY_TOL_M:
                    raise ValueError(f"edge {e.id!r}: geometry must start at node u and end at node v")
        for a, b in self.forbidden_turns:
            if a not in edges or b not in edges:
                raise ValueError(f"forbidden turn ({a!r}, {b!r}) references an unknown edge")
            if edges[a].v != edges[b].u:
                raise ValueError(f"forbidden turn ({a!r}, {b!r}): the edges do not meet")
        return self


# ---------------------------------------------------------------------------- sites and fleet
class Facility(_Model):
    id: str = Field(min_length=1)
    node: str
    residents: ClassCounts
    boarding_s: ClassDurations = Field(description="boarding time per resident of each class (s)")
    release_s: float = Field(default=0.0, description="staff ready: boarding cannot start earlier")
    name: str = ""


class Vehicle(_Model):
    id: str = Field(min_length=1)
    depot: str
    start_s: float = 0.0
    seats: NonNegInt
    wheelchair_slots: NonNegInt = 0
    stretcher_slots: NonNegInt = 0
    shift_limit_s: float | None = Field(default=None, gt=0, description="end of last action - start_s; None = no limit")
    kind: str = ""

    def capacity(self) -> tuple[int, int, int]:
        """Space per mobility class (ambulatory, wheelchair, bedbound)."""
        return (self.seats, self.wheelchair_slots, self.stretcher_slots)


class Shelter(_Model):
    id: str = Field(min_length=1)
    node: str
    capacity: ClassCounts = Field(description="residents of each class the shelter accepts over the whole plan")
    open_windows: list[tuple[float, float]] = Field(min_length=1, description="closed [open, close] intervals")
    unloading_s: ClassDurations = Field(description="unloading time per resident of each class (s)")
    name: str = ""

    @field_validator("open_windows")
    @classmethod
    def _windows(cls, w: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for a, b in w:
            if b < a:
                raise ValueError(f"opening window [{a}, {b}] ends before it starts")
        for (_a0, b0), (a1, _b1) in zip(w, w[1:]):
            if not b0 < a1:
                raise ValueError("opening windows must be sorted and disjoint")
        return w


# --------------------------------------------------------------------------------- hazard ref
class Budgets(_Model):
    """Exposure budgets: instantaneous peak flux (kW/m^2) and cumulative dose (kJ/m^2).

    Each is one number for every member or a list with one value per member (member order of the
    scenario set)."""

    peak_kw_m2: NonNegFloat | Annotated[list[NonNegFloat], Field(min_length=1)]
    dose_kj_m2: NonNegFloat | Annotated[list[NonNegFloat], Field(min_length=1)]

    def per_member(self, K: int) -> tuple[np.ndarray, np.ndarray]:
        def expand(v, name):
            if isinstance(v, list):
                if len(v) != K:
                    raise ValueError(f"budgets.{name} has {len(v)} values for K={K} members")
                return np.asarray(v, dtype=float)
            return np.full(K, float(v))
        return expand(self.peak_kw_m2, "peak_kw_m2"), expand(self.dose_kj_m2, "dose_kj_m2")


class HazardRef(_Model):
    scenario_set: str = Field(min_length=1, description="hazard_contract scenario-set folder, relative to the instance file")
    t0_offset_s: float = Field(default=0.0, description="hazard time of instance time 0 (s after issue)")
    budgets: Budgets


# ----------------------------------------------------------------------------------- instance
class Instance(_Model):
    schema_version: Literal["evacplan.instance/0"] = INSTANCE_SCHEMA
    name: str = Field(min_length=1)
    synthetic: bool = Field(description="True if any synthetic data went into this instance (label it SYNTHETIC)")
    graph: RoadGraph
    facilities: list[Facility] = Field(default_factory=list)
    vehicles: list[Vehicle] = Field(default_factory=list)
    shelters: list[Shelter] = Field(default_factory=list)
    hazard: HazardRef
    provenance: dict[str, Any] = Field(default_factory=dict)

    _source_path: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _references(self) -> "Instance":
        nodes = {n.id for n in self.graph.nodes}
        for kind, items in (("facility", self.facilities), ("vehicle", self.vehicles), ("shelter", self.shelters)):
            d = _dupes(x.id for x in items)
            if d:
                raise ValueError(f"duplicate {kind} ids {d[:5]}")
        for f in self.facilities:
            if f.node not in nodes:
                raise ValueError(f"facility {f.id!r} is at unknown node {f.node!r}")
        for v in self.vehicles:
            if v.depot not in nodes:
                raise ValueError(f"vehicle {v.id!r} has unknown depot node {v.depot!r}")
        for s in self.shelters:
            if s.node not in nodes:
                raise ValueError(f"shelter {s.id!r} is at unknown node {s.node!r}")
        return self

    @property
    def residents_total(self) -> int:
        return sum(f.residents.total for f in self.facilities)


# ----------------------------------------------------------------------------------- solution
class Drive(_Model):
    kind: Literal["drive"] = "drive"
    edges: list[str] = Field(min_length=1)
    depart_s: float


class Wait(_Model):
    kind: Literal["wait"] = "wait"
    node: str
    duration_s: NonNegFloat


class Board(_Model):
    kind: Literal["board"] = "board"
    facility: str
    counts: ClassCounts


class Unload(_Model):
    kind: Literal["unload"] = "unload"
    shelter: str
    counts: ClassCounts


Action = Annotated[Union[Drive, Wait, Board, Unload], Field(discriminator="kind")]


class Itinerary(_Model):
    vehicle: str
    actions: list[Action] = Field(default_factory=list)


class Solution(_Model):
    schema_version: Literal["evacplan.solution/0"] = SOLUTION_SCHEMA
    instance: str = Field(default="", description="name of the instance this plan is for ('' = unspecified)")
    method: str = ""
    itineraries: list[Itinerary] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict, description="commit, seed, config, host")


# ------------------------------------------------------------------------------------- I/O
def load_instance(path) -> Instance:
    """Read an instance JSON file; remembers its location to resolve the hazard folder."""
    p = Path(path)
    inst = Instance.model_validate_json(p.read_text())
    inst._source_path = p.resolve()
    return inst


def save_instance(instance: Instance, path, *, overwrite: bool = False) -> Path:
    p = Path(path)
    if p.exists() and not overwrite:
        raise FileExistsError(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(instance.model_dump_json(indent=1) + "\n")
    instance._source_path = p.resolve()
    return p


def load_solution(path) -> Solution:
    return Solution.model_validate_json(Path(path).read_text())


def save_solution(solution: Solution, path, *, overwrite: bool = False) -> Path:
    p = Path(path)
    if p.exists() and not overwrite:
        raise FileExistsError(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(solution.model_dump_json(indent=1) + "\n")
    return p


def scenario_set_path(instance: Instance, instance_path=None) -> Path:
    """The hazard folder, resolved against the instance file's directory."""
    if instance_path is not None:
        base = Path(instance_path).resolve().parent
    elif instance._source_path is not None:
        base = instance._source_path.parent
    else:
        raise ValueError("the instance has no file location: pass instance_path")
    return (base / instance.hazard.scenario_set).resolve()


def load_scenario_set(instance: Instance, instance_path=None) -> "hazard_contract.ScenarioSet":
    import hazard_contract as hc
    return hc.ScenarioSet.read(scenario_set_path(instance, instance_path))


# ------------------------------------------------------------------------------------ index
class InstanceIndex:
    """Lookups and geometry arrays for one instance (build once, reuse)."""

    def __init__(self, instance: Instance):
        g = instance.graph
        self.instance = instance
        self.nodes = {n.id: n for n in g.nodes}
        self.edges = {e.id: e for e in g.edges}
        self.forbidden = frozenset((a, b) for a, b in g.forbidden_turns)
        self.facilities = {f.id: f for f in instance.facilities}
        self.vehicles = {v.id: v for v in instance.vehicles}
        self.shelters = {s.id: s for s in instance.shelters}
        self._node_xy: dict[str, np.ndarray] = {}
        self._edge_geom: dict[str, np.ndarray] = {}
        self._out: dict[str, list[str]] | None = None

    def node_xy(self, node_id: str) -> np.ndarray:
        """``[1, 2]`` read-only array: the node as a stationary position."""
        a = self._node_xy.get(node_id)
        if a is None:
            n = self.nodes[node_id]
            a = np.array([[n.x, n.y]], dtype=float)
            a.setflags(write=False)
            self._node_xy[node_id] = a
        return a

    def edge_geometry(self, edge_id: str) -> np.ndarray:
        """``[n, 2]`` read-only polyline u -> v; its end vertices are exactly the node coordinates."""
        a = self._edge_geom.get(edge_id)
        if a is None:
            e = self.edges[edge_id]
            u, v = self.nodes[e.u], self.nodes[e.v]
            inner = [] if e.geometry is None else list(e.geometry[1:-1])
            a = np.array([(u.x, u.y), *inner, (v.x, v.y)], dtype=float)
            a.setflags(write=False)
            self._edge_geom[edge_id] = a
        return a

    def out_edges(self, node_id: str) -> list[str]:
        if self._out is None:
            out: dict[str, list[str]] = {n: [] for n in self.nodes}
            for e in self.instance.graph.edges:
                out[e.u].append(e.id)
            self._out = out
        return self._out.get(node_id, [])
