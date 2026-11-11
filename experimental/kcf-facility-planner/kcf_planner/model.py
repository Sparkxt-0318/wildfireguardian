"""Parsing and validation of the portable KCF facility-planner case contract (schema_version 1).

The contract is deliberately small; see SCHEMA.md. Validation errors raise CaseError with a stable code so the CLI can
emit an INVALID_INPUT result instead of guessing what an ill-formed case meant.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = 1
MODES = ("parallel", "shuttle")
REQUIRED_FIELDS = ("schema_version", "case_id", "horizon_s", "origin", "destination", "edges", "vehicles", "groups",
                   "board_s", "unload_s", "destination_window", "forbidden_turns", "mode")
# Optional presentation-only fields. They never change the computation.
OPTIONAL_TOP = {"title", "title_ko", "note", "note_ko", "fictional", "node_labels", "node_labels_ko", "provenance",
                "description", "description_ko", "node_xy"}
EDGE_KEYS = {"id", "u", "v", "travel_s", "closed", "unknown"}
EDGE_OPTIONAL = {"length_m", "name", "name_ko", "closed_note", "unknown_note"}
VEHICLE_KEYS = {"id", "available_s", "seats"}
VEHICLE_OPTIONAL = {"name", "name_ko"}
GROUP_KEYS = {"id", "people"}
GROUP_OPTIONAL = {"name", "name_ko"}


class CaseError(ValueError):
    def __init__(self, code, detail):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _int(x, what, *, minimum=None):
    # bool is a subclass of int in Python; reject it explicitly.
    if isinstance(x, bool) or not isinstance(x, int):
        raise CaseError("NOT_INTEGER", "%s must be an integer number of seconds/people, got %r" % (what, x))
    if minimum is not None and x < minimum:
        raise CaseError("OUT_OF_RANGE", "%s must be >= %d, got %d" % (what, minimum, x))
    return x


def _str(x, what):
    if not isinstance(x, str) or not x:
        raise CaseError("NOT_STRING", "%s must be a non-empty string, got %r" % (what, x))
    return x


def _intervals(raw, what):
    if not isinstance(raw, list):
        raise CaseError("BAD_INTERVALS", "%s must be a list of [start, end] pairs" % what)
    out = []
    for k, iv in enumerate(raw):
        if not isinstance(iv, list) or len(iv) != 2:
            raise CaseError("BAD_INTERVALS", "%s[%d] must be [start, end]" % (what, k))
        a = _int(iv[0], "%s[%d][0]" % (what, k))
        b = _int(iv[1], "%s[%d][1]" % (what, k))
        if b < a:
            raise CaseError("BAD_INTERVALS", "%s[%d] has end < start" % (what, k))
        out.append((a, b))
    return out


def positive(ivs):
    """Intervals with positive duration, sorted and merged. Zero-length intervals cannot overlap a traversal with
    positive duration under the contract's overlap convention, so they are dropped (recorded as an assumption)."""
    out = []
    for a, b in sorted(iv for iv in ivs if iv[1] > iv[0]):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


@dataclass
class Edge:
    id: str
    u: str
    v: str
    travel_s: int
    closed: list
    unknown: list
    length_m: float | None = None
    name: str | None = None
    name_ko: str | None = None
    unknown_raw: list = field(default_factory=list)
    closed_raw: list = field(default_factory=list)


@dataclass
class Vehicle:
    id: str
    available_s: int
    seats: int
    name_ko: str | None = None


@dataclass
class Group:
    id: str
    people: int
    name_ko: str | None = None


@dataclass
class Case:
    case_id: str
    horizon_s: int
    origin: str
    destination: str
    edges: list
    vehicles: list
    groups: list
    board_s: int
    unload_s: int
    window: tuple
    forbidden: set
    mode: str
    raw: dict
    notes: list = field(default_factory=list)

    @property
    def edge_by_id(self):
        return {e.id: e for e in self.edges}

    def out_edges(self, node):
        return [e for e in self.edges if e.u == node]

    @property
    def nodes(self):
        ns = []
        for e in self.edges:
            for n in (e.u, e.v):
                if n not in ns:
                    ns.append(n)
        return ns


def parse_case(raw):
    if not isinstance(raw, dict):
        raise CaseError("NOT_OBJECT", "case must be a JSON object")
    missing = [k for k in REQUIRED_FIELDS if k not in raw]
    if missing:
        raise CaseError("MISSING_FIELD", "missing required field(s): %s" % ", ".join(missing))
    notes = []
    extra = sorted(set(raw) - set(REQUIRED_FIELDS) - OPTIONAL_TOP)
    if extra:
        notes.append("Ignored unrecognised top-level field(s): %s." % ", ".join(extra))
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
        raise CaseError("SCHEMA_VERSION", "schema_version must be 1, got %r" % (raw["schema_version"],))
    case_id = _str(raw["case_id"], "case_id")
    H = _int(raw["horizon_s"], "horizon_s", minimum=0)
    origin = _str(raw["origin"], "origin")
    dest = _str(raw["destination"], "destination")
    if origin == dest:
        raise CaseError("ORIGIN_IS_DESTINATION", "origin and destination must differ; a transport needs an arrival")
    mode = raw["mode"]
    if mode not in MODES:
        raise CaseError("BAD_MODE", "mode must be 'parallel' or 'shuttle', got %r" % (mode,))
    board = _int(raw["board_s"], "board_s", minimum=0)
    unload = _int(raw["unload_s"], "unload_s", minimum=0)
    w = raw["destination_window"]
    if not isinstance(w, list) or len(w) != 2:
        raise CaseError("BAD_WINDOW", "destination_window must be [open_s, close_s]")
    wlo, whi = _int(w[0], "destination_window[0]"), _int(w[1], "destination_window[1]")
    if whi < wlo:
        raise CaseError("BAD_WINDOW", "destination_window close precedes open")

    if not isinstance(raw["edges"], list):
        raise CaseError("BAD_EDGES", "edges must be a list")
    edges, seen = [], set()
    for k, re_ in enumerate(raw["edges"]):
        if not isinstance(re_, dict):
            raise CaseError("BAD_EDGES", "edges[%d] must be an object" % k)
        miss = [x for x in ("id", "u", "v", "travel_s") if x not in re_]
        if miss:
            raise CaseError("BAD_EDGES", "edges[%d] missing %s" % (k, ", ".join(miss)))
        eid = _str(re_["id"], "edges[%d].id" % k)
        if eid in seen:
            raise CaseError("DUPLICATE_EDGE", "edge id %r repeated" % eid)
        seen.add(eid)
        u, v = _str(re_["u"], "edges[%d].u" % k), _str(re_["v"], "edges[%d].v" % k)
        D = _int(re_["travel_s"], "edges[%d].travel_s" % k, minimum=1)
        closed = _intervals(re_.get("closed", []), "edges[%d].closed" % k)
        unknown = _intervals(re_.get("unknown", []), "edges[%d].unknown" % k)
        if any(b == a for a, b in closed + unknown):
            notes.append("Edge %s lists a zero-length interval; it cannot overlap a positive-duration traversal and "
                         "is ignored." % eid)
        extra_e = sorted(set(re_) - EDGE_KEYS - EDGE_OPTIONAL)
        if extra_e:
            notes.append("Edge %s: ignored field(s) %s." % (eid, ", ".join(extra_e)))
        edges.append(Edge(eid, u, v, D, positive(closed), positive(unknown), re_.get("length_m"), re_.get("name"),
                          re_.get("name_ko"), unknown_raw=unknown, closed_raw=closed))

    if not isinstance(raw["vehicles"], list):
        raise CaseError("BAD_VEHICLES", "vehicles must be a list")
    vehicles, vseen = [], set()
    for k, rv in enumerate(raw["vehicles"]):
        if not isinstance(rv, dict) or any(x not in rv for x in VEHICLE_KEYS):
            raise CaseError("BAD_VEHICLES", "vehicles[%d] must have id, available_s, seats" % k)
        vid = _str(rv["id"], "vehicles[%d].id" % k)
        if vid in vseen:
            raise CaseError("DUPLICATE_VEHICLE", "vehicle id %r repeated" % vid)
        vseen.add(vid)
        vehicles.append(Vehicle(vid, _int(rv["available_s"], "vehicles[%d].available_s" % k, minimum=0),
                                _int(rv["seats"], "vehicles[%d].seats" % k, minimum=1), rv.get("name_ko")))
    if not isinstance(raw["groups"], list):
        raise CaseError("BAD_GROUPS", "groups must be a list")
    groups, gseen = [], set()
    for k, rg in enumerate(raw["groups"]):
        if not isinstance(rg, dict) or any(x not in rg for x in GROUP_KEYS):
            raise CaseError("BAD_GROUPS", "groups[%d] must have id, people" % k)
        gid = _str(rg["id"], "groups[%d].id" % k)
        if gid in gseen:
            raise CaseError("DUPLICATE_GROUP", "group id %r repeated" % gid)
        gseen.add(gid)
        groups.append(Group(gid, _int(rg["people"], "groups[%d].people" % k, minimum=1), rg.get("name_ko")))
    if not groups:
        raise CaseError("NO_GROUPS", "at least one group is required; there is nothing to plan otherwise")
    if mode == "shuttle" and len(vehicles) != 1:
        raise CaseError("SHUTTLE_VEHICLE_COUNT", "shuttle mode uses exactly one vehicle; got %d. A second vehicle is "
                        "never introduced or dropped silently." % len(vehicles))
    if mode == "parallel" and len(vehicles) > len(groups):
        notes.append("Parallel mode: %d vehicle(s) have no group (%s) and make no trip." % (
            len(vehicles) - len(groups), ", ".join(v.id for v in vehicles[len(groups):])))

    if not isinstance(raw["forbidden_turns"], list):
        raise CaseError("BAD_TURNS", "forbidden_turns must be a list of [incoming_edge_id, outgoing_edge_id]")
    by_id = {e.id: e for e in edges}
    forbidden = set()
    for k, pair in enumerate(raw["forbidden_turns"]):
        if not isinstance(pair, list) or len(pair) != 2:
            raise CaseError("BAD_TURNS", "forbidden_turns[%d] must be a pair of edge ids" % k)
        a, b = pair
        if a not in by_id or b not in by_id:
            raise CaseError("UNKNOWN_TURN_EDGE", "forbidden_turns[%d] names an edge that does not exist" % k)
        if by_id[a].v != by_id[b].u:
            notes.append("Forbidden turn %s->%s is not a consecutive pair (head of %s is %s, tail of %s is %s); it "
                         "can never apply." % (a, b, a, by_id[a].v, b, by_id[b].u))
        forbidden.add((a, b))
    return Case(case_id, H, origin, dest, edges, vehicles, groups, board, unload, (wlo, whi), forbidden, mode, raw,
                notes)
