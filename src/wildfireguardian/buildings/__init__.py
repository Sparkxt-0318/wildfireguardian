"""Building footprints as routing origins — source-agnostic.

Round-3 PHASE 18.

WHY AN INTERFACE AND NOT A LOADER
---------------------------------
This PHASE runs on OSM ``building=*`` because it needs no new credential. OSM is
**not** the intended long-term source: its Korean building coverage is a small
fraction of the national building stock and the fraction differs by region, which
is exactly the confound ``docs/HANDOFF_ROUND3.md`` §5 rules 7 and 12 exist to
prevent. The intended source is the 국토교통부 **GIS건물통합정보** layer
(건축물대장-joined, EPSG:5179, 용도/층수 attributes), which needs a VWorld
account the repository does not have.

So the source is a seam, not a hard-coded path. Everything downstream consumes a
:class:`BuildingSet`; swapping OSM for VWorld is implementing one class.

⚠ WHATEVER THE SOURCE, ITS COVERAGE IS A COVARIATE, NOT A DETAIL.
:class:`BuildingSet` therefore carries ``source`` and ``source_file`` and the
measurement scripts report them beside every count. A building number without
its source is not interpretable across regions.

CRS
---
:func:`load_walk_nodes` is the single place that knows the walk graphml caches
are inconsistent — ``yeongdeok_2025`` is stored in EPSG:4326 and the two PHASE-5
regions are stored already projected to EPSG:5179. Both project to EPSG:5179
here. Reading ``x``/``y`` off a graphml directly is a silent-wrong-answer bug:
EPSG:5179 metres parse as floats and raise nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

_REPO_DEFAULT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class BuildingSet:
    """Buildings for one region, ready to snap.

    ``xy`` is the footprint centroid in **EPSG:5179**, one row per building, in
    the source layer's own order. ``ids`` are opaque source identifiers, carried
    so a result can be traced back to a feature.
    """

    region: str
    xy: np.ndarray                 # (N, 2) EPSG:5179
    area_m2: np.ndarray            # (N,) projected footprint area
    ids: list[str]
    source: str                    # "osm" | "vworld" | ...
    source_file: str               # repo-relative provenance
    tag_counts: dict = field(default_factory=dict)

    def __len__(self) -> int:      # noqa: D105
        return int(len(self.xy))


class BuildingSource(Protocol):
    """Anything that can produce a :class:`BuildingSet` for a region."""

    name: str

    def load(self, region: str, *, repo: Path) -> BuildingSet:
        ...


# ---------------------------------------------------------------------------
# OSM
# ---------------------------------------------------------------------------


def _snapshot_for(region: str, layer: str, repo: Path) -> Path | None:
    """Resolve a snapshot from MANIFEST.json, or None if not snapshotted yet.

    Snapshots are preferred over ``data/cache/**`` for the reason the store
    exists: the cache is git-ignored and can be regenerated underneath a run.
    """
    man_path = repo / "data/snapshots/MANIFEST.json"
    if not man_path.exists():
        return None
    man = json.loads(man_path.read_text(encoding="utf-8"))
    want_src, want_region = f"osm-{layer}", region.replace("_", "-")
    hits = [s for s in man["snapshots"]
            if s.get("source") == want_src and s.get("region") == want_region
            and s.get("stored_file")]
    if len(hits) != 1:
        return None
    p = repo / "data/snapshots" / hits[0]["stored_file"]
    return p if p.exists() else None


class OSMBuildingSource:
    """``building=*`` polygons acquired by ``scripts/acquire_region_buildings.py``.

    ⚠ Coverage in rural Korea is a small and REGION-DEPENDENT fraction of the
    real building stock. Never present an OSM building count as a building count.
    """

    name = "osm"

    def load(self, region: str, *, repo: Path = _REPO_DEFAULT) -> BuildingSet:
        src = _snapshot_for(region, "buildings", repo)
        if src is None:
            src = repo / f"data/cache/osm/{region}/buildings.geojson"
            if not src.exists():
                raise FileNotFoundError(
                    f"no building layer for {region}. Run "
                    "`python scripts/acquire_region_buildings.py` then "
                    "`python scripts/snapshot_external.py --preset osm`.")
        doc = json.loads(src.read_text(encoding="utf-8"))
        feats = doc.get("features", [])
        xs, ys, areas, ids, tags = [], [], [], [], {}
        for f in feats:
            p = f.get("properties", {}) or {}
            cx, cy = p.get("centroid_x_5179"), p.get("centroid_y_5179")
            if cx is None or cy is None:
                continue
            xs.append(float(cx))
            ys.append(float(cy))
            areas.append(float(p.get("footprint_area_m2") or 0.0))
            ids.append(str(p.get("osmid") or p.get("id") or len(ids)))
            v = p.get("building")
            if v:
                tags[str(v)] = tags.get(str(v), 0) + 1
        return BuildingSet(
            region=region,
            xy=np.array(list(zip(xs, ys)), dtype=float).reshape(-1, 2),
            area_m2=np.array(areas, dtype=float),
            ids=ids, source=self.name,
            source_file=str(src.relative_to(repo)),
            tag_counts=dict(sorted(tags.items(), key=lambda kv: -kv[1])),
        )


class VWorldBuildingSource:
    """GIS건물통합정보 (국토교통부) — the intended source. NOT YET IMPLEMENTED.

    Everything needed is known; only the credential and the download are
    missing:

    * data.go.kr dataset 15083092 -> VWorld ``dsId=18``, SHP per 시도, free,
      "이용허락범위 제한 없음", 6,656,497 buildings nationally;
    * **already in EPSG:5179**, so no reprojection and no new CRS surface;
    * carries 건축물대장 attributes — ``BLD_NM``, ``GRO_FLO_CO`` (지상층수),
      ``UND_FLO_CO`` (지하층수), 용도 — which is what makes a 요양시설 / 경로당
      vulnerability proxy possible at all;
    * ⚠ ``uljin_samcheok_2022`` straddles 경상북도 and 강원특별자치도, so that
      region needs BOTH 시도 files merged. Same schema, same CRS, same producer,
      so the "identical rule across three regions" requirement survives — which
      is the decisive advantage over the 도로명주소 전자지도, whose multi-시도
      request needs 행정안전부장관 approval.

    Implementing this must NOT change :class:`BuildingSet`; if it needs a new
    field, the field is added as optional so OSM-era artifacts stay readable.
    """

    name = "vworld"

    def load(self, region: str, *, repo: Path = _REPO_DEFAULT) -> BuildingSet:
        raise NotImplementedError(
            "GIS건물통합정보 is not acquired. It needs a VWorld API key / "
            "download, which is a person-authenticated step. See this class's "
            "docstring for the exact dataset and the 경북+강원 merge that "
            "uljin_samcheok_2022 requires.")


SOURCES: dict[str, BuildingSource] = {
    "osm": OSMBuildingSource(),
    "vworld": VWorldBuildingSource(),
}


def load_buildings(region: str, *, source: str = "osm",
                   repo: Path = _REPO_DEFAULT) -> BuildingSet:
    """Load a region's buildings from the named source."""
    try:
        impl = SOURCES[source]
    except KeyError:
        raise ValueError(f"unknown building source {source!r}; "
                         f"have {sorted(SOURCES)}") from None
    return impl.load(region, repo=repo)


# ---------------------------------------------------------------------------
# Walk nodes — the one place that knows the caches disagree about CRS
# ---------------------------------------------------------------------------


def load_walk_nodes(region: str, *, repo: Path = _REPO_DEFAULT
                    ) -> tuple[list[str], np.ndarray, str]:
    """Return ``(node_ids, xy_5179, crs_as_stored)``, ids in the SAME sorted
    order the committed 459-series origin rule iterates.

    ⚠ The graphml caches are not consistent: ``yeongdeok_2025`` stores EPSG:4326,
    the two PHASE-5 regions store EPSG:5179 already projected. Assuming either
    one produces coordinates that parse fine and are wrong by ~1e6 m, with no
    exception raised — the same failure shape PHASE 13 found in the CRS audit.
    """
    import networkx as nx
    from pyproj import Transformer

    src = _snapshot_for(region, "walk", repo)
    if src is not None and src.suffix == ".gz":
        import gzip
        import io
        with gzip.open(src, "rb") as fh:
            G = nx.read_graphml(io.BytesIO(fh.read()))
    elif src is not None:
        G = nx.read_graphml(src)
    else:
        G = nx.read_graphml(repo / f"data/cache/osm/{region}/walk.graphml")

    ids = sorted(G.nodes)
    ax = np.array([float(G.nodes[n]["x"]) for n in ids])
    ay = np.array([float(G.nodes[n]["y"]) for n in ids])
    crs = str(G.graph.get("crs", "")).lower() or "absent"
    if "4326" in crs or (crs == "absent" and float(np.abs(ax).max()) < 1e4):
        x, y = Transformer.from_crs("EPSG:4326", "EPSG:5179",
                                    always_xy=True).transform(ax, ay)
    else:
        x, y = ax, ay
    return ids, np.column_stack([x, y]), crs


__all__ = ["BuildingSet", "BuildingSource", "OSMBuildingSource",
           "VWorldBuildingSource", "SOURCES", "load_buildings", "load_walk_nodes"]
