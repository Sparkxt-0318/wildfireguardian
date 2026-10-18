"""Shared helpers for the village evacuation planner data tools (planner/docs/ARCHITECTURE.md).

Reads only recorded data from the verified release extracts under planner/.assets/extracted/
(graph JSON, packet HAZARD.json / NPZ, request JSON, recorded RESULT.json, CSV rows). It never
imports or runs forecasting or routing code.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

PLANNER = Path(__file__).resolve().parents[1]
REPO = PLANNER.parent
ASSETS = Path(os.environ.get("WFG_ASSETS_DIR", PLANNER / ".assets"))
EXTRACTED = ASSETS / "extracted"

INPUTS_ASSET = "WFG-evaluated-routing-inputs-20261015.zip"
FINAL_ASSET = "WildfireGuardian_Latest_Independent_Final_20261015.zip"
ABLATION_ASSET = "WFG-final-input-routing-ablation-20261016-v1.zip"

RELEASE_ASSETS = [
    {"release_tag": "research-final-20261015", "asset": INPUTS_ASSET,
     "sha256": "d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202"},
    {"release_tag": "research-final-20261015", "asset": FINAL_ASSET,
     "sha256": "a3cd27b88d065883ce3d0534592d1406e3f9798c1abd98256c730f0cf3d60d3f"},
    {"release_tag": "routing-ablation-final-inputs-20261016", "asset": ABLATION_ASSET,
     "sha256": "661090bd059a862a9874c4e19977c105d1978bf32ee6d6d3cd7f6d40d244c006"},
]

INPUTS_ROOT = EXTRACTED / "WFG-evaluated-routing-inputs-20261015"
FINAL_ROOT = (EXTRACTED / "WildfireGuardian_Latest_Independent_Final_20261015"
              / "WildfireGuardian_Latest_Independent_Final_20261015")
ABLATION_ROOT = (EXTRACTED / "WFG-final-input-routing-ablation-20261016-v1"
                 / "routing_final_input_ablation_20261016_v1")
FINAL_RAW_REL = "study/execution/run/WFG-latest-completion-kit-20261015-v3/raw/LATEST_PRIMARY"
ABLATION_RAW_REL = "study/raw/ABLATION"

# Fixed facts (ARCHITECTURE.md §1) and region labels (§4.2). Event ids are re-verified from the
# packet NATIVE_METADATA.json and the export NPZ at build time; a mismatch stops the build.
REGIONS = [
    {"id": "uljin_2022", "name_ko": "울진", "name_en": "Uljin", "fire_year": 2022,
     "expected_event": "KFS_02", "demo": False},
    {"id": "miryang_2022", "name_ko": "밀양", "name_en": "Miryang", "fire_year": 2022,
     "expected_event": "KFS_11", "demo": False},
    {"id": "hongseong_2023", "name_ko": "홍성", "name_en": "Hongseong", "fire_year": 2023,
     "expected_event": "KFS_05", "demo": False},
    {"id": "uiseong_andong_2025", "name_ko": "의성·안동", "name_en": "Uiseong–Andong", "fire_year": 2025,
     "expected_event": "KFS_01", "demo": True},
    {"id": "yeongdeok_2025", "name_ko": "영덕", "name_en": "Yeongdeok", "fire_year": 2025,
     "expected_event": "KFS_01", "demo": True},
]
REGION_IDS = [r["id"] for r in REGIONS]

PROVENANCE_BASE = {
    "api_version": "1.0.0",
    "package": "wfg_latest",
    "package_version": "1.0.0",
    "kit": "v3",
    "checkpoint": "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843",
}

_TO_WGS84 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def to_wgs84(x, y):
    return _TO_WGS84.transform(x, y)


def to_5179(lon, lat):
    return _TO_5179.transform(lon, lat)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def real_utc_now() -> str:
    """Wall-clock UTC time (never overridden; used for fetch times)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now() -> str:
    """Current UTC time, or SOURCE_DATE_EPOCH when set (reproducible builds)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    now = datetime.fromtimestamp(int(epoch), timezone.utc) if epoch else datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # pragma: no cover - git missing
        return "unknown"


def assets_present() -> bool:
    return (INPUTS_ROOT / "graphs").is_dir() and (FINAL_ROOT / "INDEPENDENT_ROWS.csv").is_file() \
        and (ABLATION_ROOT / "analysis" / "ROWS.csv").is_file()


def require_assets() -> None:
    if not assets_present():
        raise SystemExit("release extracts missing under %s — run planner/scripts/fetch_planner_assets.sh"
                         % EXTRACTED)


def round6(v: float) -> float:
    return float(round(float(v), 6))


def sig6(v: float) -> float:
    """Round to 6 significant digits (for probabilities)."""
    v = float(v)
    if v == 0.0 or not math.isfinite(v):
        return v
    return float(f"{v:.6g}")


def compact_time(iso: str) -> str:
    """'2025-03-24T09:00:00+00:00' or '...Z' -> '20250324T090000Z'."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def iso_z(compact_or_iso: str) -> str:
    """'20250324T090000Z' or ISO -> '2025-03-24T09:00:00Z'."""
    s = compact_or_iso
    if "-" not in s:
        dt = datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, obj, compact: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    else:
        text = json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=False)
    data = (text + "\n").encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return len(data)


# ---------------------------------------------------------------------------------------------
# Road graph
# ---------------------------------------------------------------------------------------------

@dataclass
class Graph:
    region: str
    path: Path
    sha256: str
    revision: str
    grid: dict
    provenance: dict
    node_ids: list
    x: np.ndarray
    y: np.ndarray
    index: dict
    edges: dict           # edge id -> (u_idx, v_idx)
    edge_count: int
    scc_mask: np.ndarray = field(default=None)  # bool per node: in largest SCC
    raw: dict = field(default=None, repr=False)

    @property
    def node_count(self) -> int:
        return len(self.node_ids)

    def grid_rect(self):
        g = self.grid
        return (g["x0"], g["y0"], g["x0"] + g["width"] * g["resolution"], g["y0"] + g["height"] * g["resolution"])

    def wgs84_bbox(self):
        """[min_lon, min_lat, max_lon, max_lat] of the graph grid rectangle (edges densified)."""
        x0, y0, x1, y1 = self.grid_rect()
        t = np.linspace(0.0, 1.0, 101)
        xs = np.concatenate([x0 + t * (x1 - x0), np.full_like(t, x1), x0 + t * (x1 - x0), np.full_like(t, x0)])
        ys = np.concatenate([np.full_like(t, y0), y0 + t * (y1 - y0), np.full_like(t, y1), y0 + t * (y1 - y0)])
        lon, lat = to_wgs84(xs, ys)
        return [float(np.min(lon)), float(np.min(lat)), float(np.max(lon)), float(np.max(lat))]


def largest_scc_mask(n: int, edges_uv) -> np.ndarray:
    """Iterative Tarjan SCC on a directed graph; returns a bool mask of the largest component."""
    adj = [[] for _ in range(n)]
    for u, v in edges_uv:
        adj[u].append(v)
    index = [-1] * n
    low = [0] * n
    on_stack = [False] * n
    stack = []
    comp = [-1] * n
    counter = 0
    ncomp = 0
    for root in range(n):
        if index[root] != -1:
            continue
        work = [(root, 0)]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True
        while work:
            v, i = work[-1]
            if i < len(adj[v]):
                work[-1] = (v, i + 1)
                w = adj[v][i]
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack[w] = True
                    work.append((w, 0))
                elif on_stack[w]:
                    if index[w] < low[v]:
                        low[v] = index[w]
            else:
                work.pop()
                if work:
                    p = work[-1][0]
                    if low[v] < low[p]:
                        low[p] = low[v]
                if low[v] == index[v]:
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        comp[w] = ncomp
                        if w == v:
                            break
                    ncomp += 1
    sizes = np.bincount(np.asarray(comp, dtype=np.int64), minlength=ncomp)
    big = int(np.argmax(sizes))
    return np.asarray(comp) == big


_GRAPH_CACHE: dict = {}


def load_graph(region: str) -> Graph:
    if region in _GRAPH_CACHE:
        return _GRAPH_CACHE[region]
    path = INPUTS_ROOT / "graphs" / region / "graph.json"
    raw = json.loads(path.read_bytes())
    ids = [n["id"] for n in raw["nodes"]]
    index = {nid: i for i, nid in enumerate(ids)}
    x = np.array([n["x"] for n in raw["nodes"]], dtype=np.float64)
    y = np.array([n["y"] for n in raw["nodes"]], dtype=np.float64)
    edges = {}
    for e in raw["edges"]:
        edges[e["id"]] = (index[e["u"]], index[e["v"]])
    g = Graph(region=region, path=path, sha256=sha256_file(path), revision=raw["revision"], grid=raw["grid"],
              provenance=raw.get("provenance", {}), node_ids=ids, x=x, y=y, index=index, edges=edges,
              edge_count=len(raw["edges"]), raw=raw)
    g.scc_mask = largest_scc_mask(len(ids), edges.values())
    _GRAPH_CACHE[region] = g
    return g


def graph_snapshot_date(g: Graph):
    src = g.provenance.get("source", "")
    marker = "historical snapshot "
    if marker in src:
        return src.split(marker, 1)[1].split()[0]
    return None


# ---------------------------------------------------------------------------------------------
# Packets (recorded scenario sets) and requests (recorded missions)
# ---------------------------------------------------------------------------------------------

def packet_dirs(region: str):
    return sorted(p for p in (INPUTS_ROOT / "latest_inputs_try02" / "packets" / region).iterdir() if p.is_dir())


def scenario_set_from_hazard(h: dict) -> tuple:
    ids = [m["id"] for m in h["members"]]
    prefix = os.path.commonprefix(ids)
    if prefix.endswith(":"):
        prefix = prefix[:-1]
    for i, mid in enumerate(ids):
        if mid != f"{prefix}:{i}":
            raise ValueError("unexpected scenario member id %r (prefix %r)" % (mid, prefix))
    return prefix, ids


def request_paths(region: str):
    return sorted((INPUTS_ROOT / "latest_inputs_try02" / "requests" / region).glob("*.json"))


def packet_event_id(pdir: Path) -> str:
    meta = json.loads((pdir / "NATIVE_METADATA.json").read_text())
    return meta["construction"]["parent_forecast"]["event_id"]


def single_value(values):
    vals = list(values)
    if vals and all(v == vals[0] for v in vals):
        return vals[0]
    return None
