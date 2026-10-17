"""Region registry: road graphs, recorded hazard packets (scenario sets), recorded forecast exports and missions.

Everything is discovered from the verified input tree (tools/fetch_routing_inputs.py). Graph indexes are cached in
memory as frozen copies (read-only arrays, tuples, mapping proxies) and every access re-runs a content check: the
file's SHA-256 (re-hashed whenever size, mtime or inode change) must equal the hash recorded when the copy was built.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import numpy as np

from .config import REGION_NAMES, SNAP_MAX_M, Settings
from .errors import not_found, unprocessable
from .provenance import sha256_file

TAG_RE = re.compile(r"^(\d{8}T\d{2}0000Z)$")
MISSION_RE = re.compile(r"^(\d{8}T\d{2}0000Z)_([A-Z]+\d+)\.json$")


def tag_to_iso(tag: str) -> str:
    return "%s-%s-%sT%s:00:00Z" % (tag[0:4], tag[4:6], tag[6:8], tag[9:11])


def normalize_input_time(text) -> str:
    """Accept '2022-03-04T03:00:00Z', '...+00:00' or '20220304T030000Z'; return the tag. Whole UTC hours only."""
    import datetime as dt
    s = str(text).strip()
    if TAG_RE.match(s):
        return s
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise unprocessable("INVALID_INPUT_TIME", "input_time must be an ISO 8601 UTC time such as 2022-03-04T03:00:00Z", {"input_time": s})
    if t.tzinfo is None:
        raise unprocessable("INVALID_INPUT_TIME", "input_time must carry a time zone (use Z for UTC)", {"input_time": s})
    t = t.astimezone(dt.timezone.utc)
    if t.minute or t.second or t.microsecond:
        raise unprocessable("INVALID_INPUT_TIME", "input_time must be a whole UTC hour", {"input_time": s})
    return t.strftime("%Y%m%dT%H0000Z")


def _wgs84_transformers():
    from pyproj import Transformer
    return (Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True),
            Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True))


_TF = None


def transformers():
    global _TF
    if _TF is None:
        _TF = _wgs84_transformers()
    return _TF


def to_wgs84(x, y):
    lon, lat = transformers()[0].transform(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return lon, lat


def to_5179(lon, lat):
    x, y = transformers()[1].transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return x, y


def _ro(a):
    a = np.ascontiguousarray(a)
    a.setflags(write=False)
    return a


@dataclass(frozen=True)
class GraphIndex:
    region: str
    path: Path
    sha256: str
    revision: str
    crs: str
    grid: MappingProxyType
    node_ids: tuple
    node_index: MappingProxyType
    xy: np.ndarray
    lonlat: np.ndarray
    allowed: np.ndarray
    waitable: np.ndarray
    edges: MappingProxyType          # edge id -> (u, v, travel_ticks)
    node_count: int
    edge_count: int
    bbox: tuple

    @classmethod
    def load(cls, region: str, path: Path) -> "GraphIndex":
        digest = sha256_file(path)
        g = json.loads(Path(path).read_text())
        ids = tuple(n["id"] for n in g["nodes"])
        xy = np.array([[n["x"], n["y"]] for n in g["nodes"]], dtype=float)
        lon, lat = to_wgs84(xy[:, 0], xy[:, 1])
        out_deg, in_deg = {}, {}
        edges = {}
        for e in g["edges"]:
            out_deg[e["u"]] = out_deg.get(e["u"], 0) + 1
            in_deg[e["v"]] = in_deg.get(e["v"], 0) + 1
            edges[e["id"]] = (e["u"], e["v"], int(e["travel_ticks"]))
        allowed = np.array([out_deg.get(i, 0) > 0 and in_deg.get(i, 0) > 0 for i in ids], dtype=bool)
        grid = dict(g["grid"])
        res = float(grid["resolution"])
        x0, y0 = float(grid["x0"]), float(grid["y0"])
        x1, y1 = x0 + grid["width"] * res, y0 + grid["height"] * res
        # densified grid boundary -> WGS84 bbox (covers every forecast cell and every node)
        t = np.linspace(0.0, 1.0, 33)
        bx = np.concatenate([x0 + (x1 - x0) * t, np.full_like(t, x1), x1 - (x1 - x0) * t, np.full_like(t, x0)])
        by = np.concatenate([np.full_like(t, y0), y0 + (y1 - y0) * t, np.full_like(t, y1), y1 - (y1 - y0) * t])
        blon, blat = to_wgs84(bx, by)
        bbox = (float(min(blon.min(), lon.min())), float(min(blat.min(), lat.min())),
                float(max(blon.max(), lon.max())), float(max(blat.max(), lat.max())))
        return cls(region=region, path=Path(path), sha256=digest, revision=g["revision"], crs=g["crs"],
                   grid=MappingProxyType(grid), node_ids=ids, node_index=MappingProxyType({n: k for k, n in enumerate(ids)}),
                   xy=_ro(xy), lonlat=_ro(np.column_stack([lon, lat])), allowed=_ro(allowed),
                   waitable=_ro(np.array([bool(n.get("waitable")) for n in g["nodes"]], dtype=bool)),
                   edges=MappingProxyType(edges), node_count=len(ids), edge_count=len(g["edges"]), bbox=bbox)

    def content_ok(self) -> bool:
        try:
            return sha256_file(self.path) == self.sha256
        except FileNotFoundError:
            return False

    def node_lonlat(self, node_id: str):
        k = self.node_index[node_id]
        return float(self.lonlat[k, 0]), float(self.lonlat[k, 1])

    def snap(self, loc: dict, role: str) -> dict:
        """Snap {lon,lat} to the nearest allowed node (planar EPSG:5179 distance) or validate {node_id}."""
        if "node_id" in loc:
            nid = loc["node_id"]
            if nid not in self.node_index:
                raise unprocessable("UNKNOWN_NODE", "%s node %r is not in the %s road graph" % (role, nid, self.region),
                                    {"role": role, "node_id": nid})
            if not self.allowed[self.node_index[nid]]:
                raise unprocessable("NODE_NOT_ALLOWED", "%s node %r needs at least one incoming and one outgoing road" % (role, nid),
                                    {"role": role, "node_id": nid})
            lon, lat = self.node_lonlat(nid)
            return {"node_id": nid, "distance_m": 0.0, "lon": lon, "lat": lat, "input": "node_id"}
        lon, lat = float(loc["lon"]), float(loc["lat"])
        x, y = to_5179(lon, lat)
        x, y = float(x), float(y)
        idx = np.flatnonzero(self.allowed)
        d2 = (self.xy[idx, 0] - x) ** 2 + (self.xy[idx, 1] - y) ** 2
        k = int(idx[int(np.argmin(d2))])
        dist = float(np.sqrt(d2.min()))
        if dist > SNAP_MAX_M:
            raise unprocessable("SNAP_TOO_FAR", "%s is %.1f m from the nearest allowed road node (limit %.0f m)" % (role, dist, SNAP_MAX_M),
                                {"role": role, "distance_m": round(dist, 3), "nearest_node_id": self.node_ids[k], "limit_m": SNAP_MAX_M})
        nlon, nlat = self.node_lonlat(self.node_ids[k])
        return {"node_id": self.node_ids[k], "distance_m": round(dist, 3), "lon": nlon, "lat": nlat, "input": "lonlat"}


@dataclass(frozen=True)
class ScenarioSet:
    region: str
    tag: str
    packet_dir: Path
    scenario_set_id: str
    scenario_ids: tuple
    horizon_s: float
    valid_from: float
    hazard_version: int
    time_origin: str
    graph_revision: str
    hazard_sha256: str
    event_id: str | None
    dt: int

    def public(self) -> dict:
        return {"scenario_set_id": self.scenario_set_id, "input_time": tag_to_iso(self.tag), "scenario_ids": list(self.scenario_ids),
                "horizon_s": self.horizon_s, "hazard_sha256": self.hazard_sha256}


def scenario_set_from_packet(region: str, tag: str, packet_dir: Path) -> ScenarioSet:
    hz = json.loads((packet_dir / "HAZARD.json").read_text())
    ids = tuple(m["id"] for m in hz["members"])
    prefixes = {i.rsplit(":", 1)[0] for i in ids}
    if len(prefixes) != 1:
        raise ValueError("members of %s do not share one scenario-set prefix" % packet_dir)
    md = json.loads((packet_dir / "NATIVE_METADATA.json").read_text())
    event = (((md.get("construction") or {}).get("parent_forecast")) or {}).get("event_id")
    return ScenarioSet(region=region, tag=tag, packet_dir=packet_dir, scenario_set_id=prefixes.pop(), scenario_ids=ids,
                       horizon_s=float(hz["valid_until"]), valid_from=float(hz["valid_from"]), hazard_version=int(hz["version"]),
                       time_origin=hz["time_origin"], graph_revision=hz["graph_revision"],
                       hazard_sha256=sha256_file(packet_dir / "HAZARD.json"), event_id=event, dt=int(hz["dt"]))


@dataclass
class Region:
    id: str
    graph_path: Path
    graph: GraphIndex
    scenario_sets: dict = field(default_factory=dict)   # tag -> ScenarioSet
    missions: dict = field(default_factory=dict)        # "<tag>_<mission>" -> request path
    exports: dict = field(default_factory=dict)         # tag -> (npz, record)

    @property
    def event_id(self):
        evs = {s.event_id for s in self.scenario_sets.values() if s.event_id}
        return evs.pop() if len(evs) == 1 else None

    def public(self) -> dict:
        name_ko, name_en = REGION_NAMES.get(self.id, (self.id, self.id))
        g = self.graph
        return {"id": self.id, "name_ko": name_ko, "name_en": name_en, "event_id": self.event_id,
                "bbox": list(g.bbox), "graph_id": g.revision, "graph_sha256": g.sha256, "node_count": g.node_count,
                "edge_count": g.edge_count, "allowed_node_count": int(g.allowed.sum()), "crs": g.crs,
                "grid": {"x0": g.grid["x0"], "y0": g.grid["y0"], "resolution_m": g.grid["resolution"],
                         "width": g.grid["width"], "height": g.grid["height"]},
                "input_times": [tag_to_iso(t) for t in sorted(self.scenario_sets)],
                "scenario_sets": [self.scenario_sets[t].public() for t in sorted(self.scenario_sets)],
                "recorded_missions": [{"mission": k, "input_time": tag_to_iso(k.split("_")[0])} for k in sorted(self.missions)]}


class Registry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.regions: dict[str, Region] = {}
        self.issues: list[str] = []
        self._lock = threading.Lock()

    def load(self) -> "Registry":
        root = self.settings.data_root
        graphs = root / "graphs"
        if not graphs.is_dir():
            self.issues.append("routing inputs not found at %s; run: python tools/fetch_routing_inputs.py" % root)
            return self
        for gp in sorted(graphs.glob("*/graph.json")):
            rid = gp.parent.name
            try:
                region = Region(id=rid, graph_path=gp, graph=GraphIndex.load(rid, gp))
                pk = self.settings.inputs_root / "packets" / rid
                for d in sorted(pk.glob("*")) if pk.is_dir() else []:
                    if TAG_RE.match(d.name) and (d / "HAZARD.json").is_file():
                        region.scenario_sets[d.name] = scenario_set_from_packet(rid, d.name, d)
                rq = self.settings.inputs_root / "requests" / rid
                for f in sorted(rq.glob("*.json")) if rq.is_dir() else []:
                    m = MISSION_RE.match(f.name)
                    if m:
                        region.missions["%s_%s" % m.groups()] = f
                ev = region.event_id
                if ev:
                    ex = self.settings.inputs_root / "exports" / ev
                    for tag in region.scenario_sets:
                        npz, rec = ex / ("FORECAST_%s.npz" % tag), ex / ("FORECAST_RECORD_%s.json" % tag)
                        if npz.is_file() and rec.is_file():
                            region.exports[tag] = (npz, rec)
                self.regions[rid] = region
            except Exception as exc:   # a broken region is reported, never silently served
                self.issues.append("region %s failed to load: %s: %s" % (rid, type(exc).__name__, exc))
        return self

    # ---- lookups (each raises a clear API error) -------------------------------------------------------------
    def region(self, rid: str, *, status=422) -> Region:
        r = self.regions.get(rid)
        if r is None:
            err = (not_found if status == 404 else unprocessable)("UNKNOWN_REGION", "region %r is not available" % rid,
                                                                  {"available": sorted(self.regions)})
            raise err
        self._check_graph(r)
        return r

    def _check_graph(self, r: Region):
        if not r.graph.content_ok():
            with self._lock:
                if not r.graph.content_ok():
                    r.graph = GraphIndex.load(r.id, r.graph_path)   # content changed: rebuild the frozen copy

    def scenario_set(self, r: Region, tag: str, *, status=422) -> ScenarioSet:
        s = r.scenario_sets.get(tag)
        if s is None:
            err = (not_found if status == 404 else unprocessable)(
                "INPUT_TIME_UNAVAILABLE", "no recorded input for %s at %s" % (r.id, tag_to_iso(tag)),
                {"available": [tag_to_iso(t) for t in sorted(r.scenario_sets)]})
            raise err
        if sha256_file(s.packet_dir / "HAZARD.json") != s.hazard_sha256:
            raise unprocessable("INPUT_CHANGED", "recorded hazard packet changed on disk; restart the API", {"packet": str(s.packet_dir)})
        return s

    def scenario_set_by_id(self, r: Region, sid: str) -> ScenarioSet:
        for s in r.scenario_sets.values():
            if s.scenario_set_id == sid:
                return s
        raise unprocessable("UNKNOWN_SCENARIO_SET", "scenario set %r is not recorded for %s" % (sid, r.id),
                            {"available": [s.scenario_set_id for s in r.scenario_sets.values()]})
