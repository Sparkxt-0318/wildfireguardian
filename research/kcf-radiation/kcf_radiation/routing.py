"""Leave-by times with and without a heat closure, on product/wfg-roadlayer's engine (no new routing science).

The instance, the shelter acceptance and the origin closure are those of wfg_roadlayer.engine (= research/kcf-replay
replay.py), with the per-cell closure seconds replaced by per-piece and per-node seconds from ``closure.HeatClosure``.
With a zero safe distance everywhere this reproduces the engine's own instance exactly (tests/test_closure.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRODUCT = ROOT / "product/wfg-roadlayer"
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))

from wfg_roadlayer import engine, regiondata  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import core  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import intervals as iv  # noqa: E402

from .closure import HeatClosure  # noqa: E402

PLACES = ROOT / "planner/public/data/regions"


class AnyRegion(regiondata.Region):
    """wfg_roadlayer Region for any of the five routing regions: graph from data/routing, places from the planner.
    The 읍·면 table is only bundled for the two 2025 regions; it is not needed for leave-by times."""

    def __init__(self, rid: str, graph_path: Path):
        self.id = rid
        self.meta = {"name": {"en": rid}}
        self.name = self.meta["name"]
        self.road = regiondata.RoadModel(json.loads(Path(graph_path).read_text(encoding="utf-8")))
        feats = json.loads((PLACES / rid / "places.geojson").read_text(encoding="utf-8"))["features"]
        self.origins, self.shelters = [], []
        for f in feats:
            p = f["properties"]
            entry = (p.get("entry") or {}).get("node")
            rec = {"id": p["id"], "name": p.get("name") or "", "category": p.get("category"),
                   "lonlat": tuple(f["geometry"]["coordinates"]), "entry_node_id": entry,
                   "checkable": bool(p.get("checkable")), "node": self.road.nidx.get(entry) if entry else None}
            if p["role"] == "origin":
                self.origins.append(rec)
            elif p["role"] == "destination" and p.get("checkable"):
                self.shelters.append(rec)
        self.candidates()


def _accept(node_b, node, H, dwell):
    acc = (0, H - dwell)
    if acc[1] < 0:
        return []
    b = node_b(node)
    if b is not None:
        return iv.subtract(acc, [(max(b - dwell, 0), H)])
    return [acc]


def _origin(node_b, node, H):
    b = node_b(node)
    return [(b, H)] if b is not None else []


def leave_by(region, hc: HeatClosure, *, dwell: int = 120, workers: int = 1):
    """Per origin: the deadline-field issue set over its candidate shelters and the summary numbers
    (leave_by = end of the window starting at 0, latest = last departure second), as engine.assemble reads them."""
    road, H = region.road, hc.H
    inst = core.Instance(H=H, n_nodes=len(road.node_ids), tail=road.tail, head=road.head, D=road.D,
                         waitable=road.waitable, forbidden=road.forbidden, B=hc.edge_blocks(), W=hc.wait_blocks())
    jobs_by = {}
    for o in region.origins:
        if o["node"] is None or not o["checkable"]:
            continue
        for s in region.cands.get(o["id"], []):
            jobs_by.setdefault(s["node"], set()).add(o["node"])
    jobs = [(sn, _accept(hc.node_b, sn, H, dwell), [(on, _origin(hc.node_b, on, H)) for on in sorted(ons)])
            for sn, ons in sorted(jobs_by.items())]
    results = engine.run_passes(road, inst, jobs, workers)
    by = {sn: out for sn, out, _ in results}
    rows = {}
    for o in region.origins:
        if o["node"] is None or not o["checkable"] or not region.cands.get(o["id"]):
            continue
        sets = [tuple(p) for s in region.cands[o["id"]] for p in by[s["node"]][o["node"]]["set"]]
        win = iv.normalize(sets)
        rows[o["id"]] = {"windows": win, "leave_by": (win[0][1] if win and win[0][0] == 0 else None),
                         "latest": (win[-1][1] if win else None)}
    return rows, inst
