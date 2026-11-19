"""Bundled and cached region data: road graph, places (villages, care facilities, shelters), 읍·면 table, fonts.

``setup`` fetches what is not bundled ONCE (road graphs from the research release archive, the Korean font from a
PyPI wheel), verifies every file by SHA-256 and stores it in the cache. ``load_region`` only reads the cache and
re-verifies the hashes, so a run needs no network.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

from .errors import Refusal, reason

PKG = Path(__file__).resolve().parent
PRODUCT = PKG.parent
REPO = PRODUCT.parents[1]
REGISTRY = json.loads((PRODUCT / "data/regions.json").read_text(encoding="utf-8"))


def default_cache() -> Path:
    env = os.environ.get("WFG_ROADLAYER_CACHE")
    return Path(env).expanduser() if env else Path.home() / ".cache" / "wfg-roadlayer"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def resolve_region(name: str | None) -> str:
    if not name:
        raise Refusal(reason("REGION_MISSING", "지역 이름이 없습니다 (--region).", "no region name given (--region)."))
    for rid, r in REGISTRY["regions"].items():
        if name == rid or name in r["aliases"] or name.lower() == rid.lower():
            return rid
    known = ", ".join("%s (%s)" % (rid, r["name"]["ko"]) for rid, r in REGISTRY["regions"].items())
    raise Refusal(reason("REGION_UNKNOWN", "알 수 없는 지역: %s. 사용 가능: %s" % (name, known),
                         "unknown region: %s. Available: %s" % (name, known)))


# ------------------------------------------------------------------------------------------------ setup
def _write_verified(dest: Path, data: bytes, want: str, what: str):
    got = sha256_bytes(data)
    if got != want:
        raise SystemExit("%s: SHA-256 %s differs from the pinned %s; nothing written" % (what, got, want))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)


def _download(url: str, log) -> bytes:
    log("download %s" % url)
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def setup(cache: Path, *, archive: Path | None = None, data_routing: Path | None = None, font_wheel: Path | None = None,
          log=print) -> dict:
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    zipped = None
    manifest = {"schema": "wfg.roadlayer.cache/1", "files": {}}
    for rid, r in REGISTRY["regions"].items():
        dest = cache / "graphs" / rid / "graph.json"
        want = r["graph"]["sha256"]
        if not (dest.is_file() and sha256_file(dest) == want):
            src = None
            for root in [data_routing, REPO / "data/routing"]:
                if root and (Path(root) / r["graph"]["archive_member"]).is_file():
                    cand = Path(root) / r["graph"]["archive_member"]
                    if sha256_file(cand) == want:
                        src = cand.read_bytes()
                        log("copy %s" % cand)
                        break
            if src is None:
                if zipped is None:
                    raw = Path(archive).read_bytes() if archive else _download(REGISTRY["routing_inputs_archive"]["url"], log)
                    if sha256_bytes(raw) != REGISTRY["routing_inputs_archive"]["sha256"]:
                        raise SystemExit("routing input archive SHA-256 mismatch; nothing written")
                    zipped = zipfile.ZipFile(io.BytesIO(raw))
                src = zipped.read(r["graph"]["archive_member"])
            _write_verified(dest, src, want, "graph %s" % rid)
        manifest["files"]["graphs/%s/graph.json" % rid] = want
        pdest = cache / "places" / ("%s.geojson" % rid)
        pwant = r["places"]["sha256"]
        if not (pdest.is_file() and sha256_file(pdest) == pwant):
            _write_verified(pdest, (REPO / r["places"]["repo_path"]).read_bytes(), pwant, "places %s" % rid)
        manifest["files"]["places/%s.geojson" % rid] = pwant
    fw = REGISTRY["font_wheel"]
    wheel = None
    for name, m in fw["members"].items():
        dest = cache / "fonts" / name
        if not (dest.is_file() and sha256_file(dest) == m["sha256"]):
            if wheel is None:
                raw = Path(font_wheel).read_bytes() if font_wheel else _download(fw["url"], log)
                if sha256_bytes(raw) != fw["sha256"]:
                    raise SystemExit("font wheel SHA-256 mismatch; nothing written")
                wheel = zipfile.ZipFile(io.BytesIO(raw))
            _write_verified(dest, wheel.read(m["member"]), m["sha256"], "font %s" % name)
        manifest["files"]["fonts/%s" % name] = m["sha256"]
    (cache / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    log("cache ready: %s (%d files verified)" % (cache, len(manifest["files"])))
    return manifest


def _cached(cache: Path, rel: str, want: str, what_ko: str, what_en: str) -> Path:
    p = Path(cache) / rel
    if not p.is_file():
        raise Refusal(reason("DATA_NOT_SET_UP", "%s 이(가) 캐시에 없습니다 (%s). 먼저 'setup' 을 한 번 실행하십시오." % (what_ko, p),
                             "%s is not in the cache (%s). Run 'setup' once first." % (what_en, p)))
    if sha256_file(p) != want:
        raise Refusal(reason("DATA_CORRUPT", "%s 의 SHA-256 이 고정값과 다릅니다 (%s). 'setup' 을 다시 실행하십시오." % (what_ko, p),
                             "%s does not match its pinned SHA-256 (%s). Run 'setup' again." % (what_en, p)))
    return p


def font_paths(cache: Path) -> dict:
    out = {}
    for name, m in REGISTRY["font_wheel"]["members"].items():
        out[name] = _cached(cache, "fonts/" + name, m["sha256"], "한글 글꼴 " + name, "Korean font " + name)
    return out


# ------------------------------------------------------------------------------------------------ road model
def _exact(v) -> F:
    return F(v) if isinstance(v, (int, float)) else F(str(v))


def _floor(x: F) -> int:
    return x.numerator // x.denominator


class RoadModel:
    """The routing graph exactly as research/kcf-replay/replay.py reads it (Region.__init__)."""

    def __init__(self, raw: dict):
        g = raw["grid"]
        self.crs = raw.get("crs")
        self.revision = raw.get("revision")
        self.x0, self.y0, self.res = _exact(g["x0"]), _exact(g["y0"]), _exact(g["resolution"])
        self.W, self.H = int(g["width"]), int(g["height"])
        self.grid_json = {k: g[k] for k in ("x0", "y0", "resolution", "width", "height")}
        if raw.get("mid_edge_reversal"):
            raise ValueError("mid-edge reversal graphs are not supported")
        self.node_ids = [n["id"] for n in raw["nodes"]]
        self.nidx = {n: i for i, n in enumerate(self.node_ids)}
        self.node_xy = [(float(n["x"]), float(n["y"])) for n in raw["nodes"]]
        self.waitable = [n.get("waitable") is True for n in raw["nodes"]]
        self.edge_ids = [e["id"] for e in raw["edges"]]
        eidx = {e: i for i, e in enumerate(self.edge_ids)}
        self.tail = [self.nidx[e["u"]] for e in raw["edges"]]
        self.head = [self.nidx[e["v"]] for e in raw["edges"]]
        self.D = [int(e["travel_ticks"]) for e in raw["edges"]]
        if any(t < 1 or t != e["travel_ticks"] for t, e in zip(self.D, raw["edges"])):
            raise ValueError("graph travel_ticks must be positive integers (1 s ticks)")
        self.source_way = [e.get("source_way") for e in raw["edges"]]
        self.reverse_edge = [e.get("reverse_edge") for e in raw["edges"]]
        # replay.py: segment end fraction, float ends via limit_denominator(1e9)
        self.seg = [[(int(s["cell"]), F(s["end"]).limit_denominator(10 ** 9) if not isinstance(s["end"], int) else F(s["end"]))
                     for s in e["segments"]] for e in raw["edges"]]
        self.seg_raw = [[[int(s["cell"]), s["end"]] for s in e["segments"]] for e in raw["edges"]]
        self.forbidden = set()
        for a, b in raw.get("forbidden_turns", []):
            if a in eidx and b in eidx:
                self.forbidden.add((eidx[a], eidx[b]))
        self.node_cell = [self.cell_of(_exact(n["x"]), _exact(n["y"])) for n in raw["nodes"]]
        self.inc_by_node = {}
        for j, v in enumerate(self.head):
            self.inc_by_node.setdefault(v, []).append(j)
        self.out_by_node = {}
        for j, u in enumerate(self.tail):
            self.out_by_node.setdefault(u, []).append(j)
        self.road_cells = sorted({c for segs in self.seg for c, _ in segs} | set(self.node_cell))

    def cell_of(self, x: F, y: F) -> int:
        c = _floor((x - self.x0) / self.res)
        r = _floor((y - self.y0) / self.res)
        if not (0 <= c < self.W and 0 <= r < self.H):
            raise ValueError("coordinate outside grid")
        return r * self.W + c

    def cell_rect(self, cell: int):
        r, c = divmod(int(cell), self.W)
        x0, y0, res = float(self.x0), float(self.y0), float(self.res)
        return (x0 + c * res, x0 + (c + 1) * res, y0 + r * res, y0 + (r + 1) * res)

    def fastest_ticks(self, start: int, targets: set, max_ticks: int | None = None) -> dict:
        """Fire-free earliest arrival (seconds) at each target node over an edge (tools/explain_deadlines/roads.py)."""
        import heapq
        best = {t: None for t in targets}
        dist, heap = {}, []
        for e in self.out_by_node.get(start, []):
            d = self.D[e]
            if max_ticks is not None and d > max_ticks:
                continue
            if d < dist.get(e, 1 << 62):
                dist[e] = d
                heapq.heappush(heap, (d, e))
        remaining = set(targets)
        while heap and remaining:
            d, e = heapq.heappop(heap)
            if d != dist.get(e):
                continue
            node = self.head[e]
            if node in remaining:
                best[node] = d
                remaining.discard(node)
            for f in self.out_by_node.get(node, []):
                if (e, f) in self.forbidden:
                    continue
                nd = d + self.D[f]
                if max_ticks is not None and nd > max_ticks:
                    continue
                if nd < dist.get(f, 1 << 62):
                    dist[f] = nd
                    heapq.heappush(heap, (nd, f))
        return best


def haversine_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


class Region:
    def __init__(self, rid: str, cache: Path):
        self.id = rid
        self.meta = REGISTRY["regions"][rid]
        self.name = self.meta["name"]
        gp = _cached(cache, "graphs/%s/graph.json" % rid, self.meta["graph"]["sha256"], "도로망 (%s)" % rid, "road graph (%s)" % rid)
        pp = _cached(cache, "places/%s.geojson" % rid, self.meta["places"]["sha256"], "마을·대피소 (%s)" % rid,
                     "places and shelters (%s)" % rid)
        self.graph_sha256 = self.meta["graph"]["sha256"]
        self.places_sha256 = self.meta["places"]["sha256"]
        self.road = RoadModel(json.loads(gp.read_text(encoding="utf-8")))
        feats = json.loads(pp.read_text(encoding="utf-8"))["features"]
        tpath = PRODUCT / self.meta["towns"]
        if not tpath.is_file():
            raise Refusal(reason("TOWNS_MISSING", "읍·면 표가 없습니다: %s" % tpath, "읍·면 table missing: %s" % tpath))
        self.towns_sha256 = sha256_file(tpath)
        towns = {r["place_id"]: r for r in csv.DictReader(open(tpath, encoding="utf-8"))}
        self.origins, self.shelters = [], []
        for f in feats:
            p = f["properties"]
            lonlat = tuple(f["geometry"]["coordinates"])
            entry = (p.get("entry") or {}).get("node")
            rec = {"id": p["id"], "name": p.get("name") or "", "category": p.get("category"), "vulnerable": bool(p.get("vulnerable")),
                   "lonlat": lonlat, "entry_node_id": entry, "checkable": bool(p.get("checkable")),
                   "entry_distance_m": (p.get("entry") or {}).get("distance_m"),
                   "node": self.road.nidx.get(entry) if entry else None}
            if p["role"] == "origin":
                t = towns.get(p["id"])
                sg = p.get("sigungu") or {}
                rec["sigungu"] = sg.get("ko") if sg.get("status") == "established" else (t or {}).get("sigungu") or ""
                rec["eupmyeon"] = (t or {}).get("eupmyeon") or ""
                rec["town_method"] = (t or {}).get("method") or "unknown"
                self.origins.append(rec)
            elif p["role"] == "destination" and p.get("checkable"):
                self.shelters.append(rec)
        self.candidates()

    def candidates(self, k: int = 3):
        """planner/scripts/precompute.py::dispatch_requests as replay.py reads it: the k nearest shelters (straight
        line, ties by id) with distinct entry nodes, excluding shelters at the origin's own entry node."""
        out = {}
        for o in self.origins:
            if o["node"] is None or not o["checkable"]:
                out[o["id"]] = []
                continue
            cand = [s for s in self.shelters if s["entry_node_id"] != o["entry_node_id"] and s["node"] is not None]
            near, seen = [], set()
            for s in sorted(cand, key=lambda s: (haversine_m(o["lonlat"], s["lonlat"]), s["id"])):
                if s["entry_node_id"] in seen:
                    continue
                seen.add(s["entry_node_id"])
                near.append(s)
                if len(near) >= k:
                    break
            out[o["id"]] = near
        self.cands = out
        return out
