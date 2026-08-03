"""DEM slope on real OSM walk edges, with direction-aware traversal times.

Round-3 PHASE 2.

WHAT THIS CLOSES
----------------
`scripts/run_real_roads_real_hazard.py` disclosed its own gap in provenance:

    "NO DEM slope correction on the OSM walk edges: edge times use a FLAT
     elderly walk speed."

The 459-origin run therefore had real roads and a real hazard surface, but flat
terrain — in a county whose elevation spans −207 m to 1014 m. This module
supplies the third axis so all three are real at once.

TWO DESIGN DECISIONS, BOTH LOAD-BEARING
---------------------------------------
**Sampling spacing.** Edge elevation profiles are resampled at uniform
arc-length. The spacing is not a detail: measured slope is scale-dependent, and
mean traversal time rises +40.3 % at 30 m but only +20.9 % at 90 m. 60 m is
canonical (the SRTM raster is ~25 x 31 m/pixel, so 30 m samples below one pixel
and reads DEM noise as terrain — apparent slopes reach 309 %). All three
spacings are reported.

**Direction.** Tobler is asymmetric: uphill and downhill traversal of the same
edge differ, on this network by 19.9 % of flat time on average and by >10 % on
56 % of edges. The pipeline previously routed on an undirected `nx.Graph`
(OSM's 22,276 directed edges collapsed to 11,020), which cannot represent that.
This module builds a **DiGraph** with a separate `time_min` per direction.

Residents evacuate outward and responders drive inward over the same edges, so
averaging the two directions would be wrong for both parties in opposite
directions — and the errors would cancel in aggregate, hiding themselves.

NOTE ON THE 407-ORIGIN RUN
--------------------------
`build_evacuation_network` computes ``dz = abs(elev[b] - elev[a])``, so every
edge is treated as uphill. Because Tobler's ``|S + 0.05|`` makes uphill the
slower direction, that run already applies the conservative "slower direction"
convention — implicitly, and without recording it. This module is deliberately
direction-aware instead; the difference is stated in docs/slope_integration.md
rather than quietly reconciled.

The Tobler function itself is imported from :mod:`.evacuation` and NOT
reimplemented, so slope handling is identical to the 407-origin run.
"""

from __future__ import annotations

import gzip
import tempfile
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np

from ..config import get as _cfg
from .evacuation import ELDERLY_FLAT_SPEED_MS, elderly_speed_ms
from .future_front import RoadNetwork

#: Arc-length spacing (m) at which edge elevation profiles are sampled.
DEFAULT_SAMPLING_M: float = float(_cfg("pedestrian.slope_sampling_m", 60.0))
#: Hard bound on |rise/run| per sub-segment. A DEFENCE AGAINST DEM REGISTRATION
#: ERROR (bridges, tunnels, cuttings), NOT a physical correction — see the config.
DEFAULT_MAX_ABS_SLOPE: float = float(_cfg("pedestrian.max_abs_slope", 0.60))


@dataclass
class SlopeStats:
    """Diagnostics for one slope-aware network build."""

    sampling_m: float
    max_abs_slope: float | None
    n_edges_undirected: int
    n_edges_directed: int
    n_subsegments: int
    n_edges_with_geometry: int
    n_edges_straight_line: int
    n_clipped_subsegments: int
    clipped_edges: list[dict]
    slope_abs: np.ndarray
    seg_len: np.ndarray
    time_flat_s: np.ndarray
    time_fwd_s: np.ndarray
    time_rev_s: np.ndarray
    #: DEM-footprint accounting. A sample that falls OUTSIDE the raster reads
    #: nodata, and the ``nan_to_num`` below then times that sub-segment as FLAT.
    #: That fallback is silent, so it is counted here and reported: a region
    #: whose walk bbox overruns its DEM is partly a flat-timing run wearing a
    #: slope-run label. Zero for Yeongdeok; NOT zero for Uljin-Samcheok, whose
    #: DEM starts at 36.85 N while its walk bbox starts at 36.81 N.
    n_elev_samples: int = 0
    n_nodata_samples: int = 0
    n_edges_with_nodata: int = 0

    def as_dict(self) -> dict:
        s, L = self.slope_abs, self.seg_len
        tf, ta, tb = self.time_flat_s.sum(), self.time_fwd_s.sum(), self.time_rev_s.sum()
        asym = np.abs(self.time_fwd_s - self.time_rev_s) / np.maximum(self.time_flat_s, 1e-9)
        return {
            "sampling_m": self.sampling_m,
            "max_abs_slope": self.max_abs_slope,
            "n_edges_undirected": self.n_edges_undirected,
            "n_edges_directed": self.n_edges_directed,
            "n_subsegments": int(self.n_subsegments),
            "n_edges_with_geometry": self.n_edges_with_geometry,
            "n_edges_straight_line": self.n_edges_straight_line,
            "geometry_fraction": round(self.n_edges_with_geometry /
                                       max(self.n_edges_undirected, 1), 4),
            "slope_abs": {
                "mean": float(s.mean()),
                "length_weighted_mean": float(np.average(s, weights=L)),
                "median": float(np.median(s)),
                "p90": float(np.percentile(s, 90)),
                "p99": float(np.percentile(s, 99)),
                "max": float(s.max()),
                "frac_gt_5pct": float((s > 0.05).mean()),
                "frac_gt_15pct": float((s > 0.15).mean()),
                "frac_gt_50pct": float((s > 0.50).mean()),
            },
            "traversal_time": {
                "flat_total_h": tf / 3600.0,
                "slope_forward_total_h": ta / 3600.0,
                "slope_reverse_total_h": tb / 3600.0,
                "pct_change_forward": (ta / tf - 1.0) * 100.0,
                "pct_change_reverse": (tb / tf - 1.0) * 100.0,
                "pct_change_mean_of_directions": ((ta + tb) / 2.0 / tf - 1.0) * 100.0,
            },
            "directional_asymmetry": {
                "definition": "|t(u->v) - t(v->u)| / t_flat, per undirected edge",
                "mean": float(asym.mean()),
                "median": float(np.median(asym)),
                "p90": float(np.percentile(asym, 90)),
                "max": float(asym.max()),
                "frac_edges_gt_10pct": float((asym > 0.10).mean()),
            },
            "dem_sampling": {
                "note": ("A sample outside the DEM footprint reads nodata and is "
                         "then timed as FLAT. Silent by construction, so it is "
                         "counted: n_nodata_samples > 0 means part of this "
                         "'slope' run is a flat run."),
                "n_elev_samples": self.n_elev_samples,
                "n_nodata_samples": self.n_nodata_samples,
                "frac_nodata": (self.n_nodata_samples / max(self.n_elev_samples, 1)),
                "n_edges_with_nodata": self.n_edges_with_nodata,
                "frac_edges_with_nodata": (self.n_edges_with_nodata /
                                           max(self.n_edges_undirected, 1)),
            },
            "clipping": {
                "note": ("DEFENCE AGAINST DEM REGISTRATION ERROR, NOT a physical "
                         "correction. Where a road crosses a bridge, tunnel or "
                         "cutting, SRTM reports the terrain surface rather than the "
                         "roadbed; the resulting slope is an artefact of comparing a "
                         "road position with a hillside elevation."),
                "n_clipped_subsegments": self.n_clipped_subsegments,
                "frac_clipped": (self.n_clipped_subsegments / max(self.n_subsegments, 1)),
                "n_edges_affected": len(self.clipped_edges),
                "worst_edges": self.clipped_edges[:10],
            },
        }


def load_snapshot_graph(path: str | Path):
    """Load a (possibly gzipped) snapshot graphml via OSMnx.

    Reads from ``data/snapshots/`` — the evidence layer — never from
    ``data/cache/``, which is allowed to be regenerated underneath us.
    """
    import osmnx as ox

    p = Path(path)
    if p.suffix == ".gz":
        with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as fh:
            fh.write(gzip.decompress(p.read_bytes()))
            tmp = fh.name
        try:
            return ox.load_graphml(tmp)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return ox.load_graphml(p)


def _resample_uniform(x: np.ndarray, y: np.ndarray, step: float):
    """Points at uniform arc-length ``step`` along a projected polyline.

    Uniform ARC-LENGTH resampling, not per-vertex densification. Densifying each
    original segment independently leaves sub-segments shorter than one DEM
    pixel wherever OSM vertices are dense, and a sub-pixel baseline turns DEM
    noise into slope: measured that way the network's apparent maximum slope is
    1055 %. Resampling the whole polyline gives every sub-segment the same,
    controlled baseline.
    """
    if x.size < 2 or not (np.isfinite(x).all() and np.isfinite(y).all()):
        return None
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if not np.isfinite(total) or total <= 0.0:
        return None
    n = max(1, int(round(total / step)))
    t = np.linspace(0.0, total, n + 1)
    return np.interp(t, s, x), np.interp(t, s, y), total / n


def _is_analysis_crs(crs) -> bool:
    """True when ``crs`` denotes EPSG:5179, in whatever spelling it arrives.

    ⚠ This guard decides whether an incoming OSM graph is REPROJECTED. Answering
    "no" for a graph that is already in the analysis CRS reprojects it needlessly;
    answering "yes" for one that is not leaves lon/lat degrees being read as
    metres. So it has to recognise the CRS, not a particular way of writing it.

    The snapshot store already carries two spellings — ``osm-*_yeongdeok-2025_*``
    store ``epsg:4326`` while both 2026-08-02 regions store ``EPSG:5179`` — and
    osmnx/pyproj may hand back a :class:`pyproj.CRS`, a WKT string or an integer
    code rather than an authority string.

    This replaces a two-element membership test whose two elements were the same
    string, ``("epsg:5179", "epsg:5179")``. Because ``.lower()`` was already
    applied, the duplicate made it a plain equality test: correct for both values
    in the store, but unable to match any non-code spelling. Comparing CRS
    identity accepts every spelling of EPSG:5179 and none of any other; verified
    to give the identical answer for every ``crs`` value present in the six
    committed graphml snapshots.
    """
    if crs is None:
        return False
    try:
        from pyproj import CRS  # noqa: PLC0415
        return CRS.from_user_input(crs).equals(CRS.from_epsg(5179))
    except Exception:
        # Unparseable input is not a reason to raise here — fall back to the
        # historical string test, which sends anything unrecognised to
        # project_graph exactly as before.
        return str(crs).strip().lower() == "epsg:5179"


def build_walk_network(
    G,
    dem_path: str | Path | None,
    *,
    sampling_m: float = DEFAULT_SAMPLING_M,
    max_abs_slope: float | None = DEFAULT_MAX_ABS_SLOPE,
    flat_speed_ms: float = ELDERLY_FLAT_SPEED_MS,
    directed: bool = True,
    apply_slope: bool = True,
) -> tuple[RoadNetwork, SlopeStats | None]:
    """Build a routable walk network from a projected OSM graph.

    Parameters
    ----------
    G
        OSMnx graph. Reprojected to EPSG:5179 here if it is not already.
    dem_path
        SRTM GeoTIFF. Required when ``apply_slope``.
    directed
        ``True`` builds an ``nx.DiGraph`` carrying a separate ``time_min`` per
        direction. ``False`` reproduces the historical undirected collapse.
    apply_slope
        ``False`` gives flat-speed timing — the Round-2 behaviour — which is how
        the middle column of the three-column comparison and the DiGraph
        regression test are produced.
    """
    import osmnx as ox
    from pyproj import Transformer

    if not _is_analysis_crs(G.graph.get("crs")):
        G = ox.project_graph(G, to_crs="EPSG:5179")

    g: nx.Graph = nx.DiGraph() if directed else nx.Graph()
    for n, d in G.nodes(data=True):
        g.add_node(n, x=float(d["x"]), y=float(d["y"]))

    # Collapse OSM's parallel/directed edges to one undirected pair first, so
    # the geometry is sampled once and both directions come from one profile.
    undirected: dict[tuple[int, int], dict] = {}
    for u, v, d in G.edges(data=True):
        if u == v:
            continue
        key = (u, v) if u <= v else (v, u)
        if key in undirected:
            continue
        undirected[key] = d if (u <= v) else _reverse_geometry(d)

    if not apply_slope:
        for (u, v), d in undirected.items():
            length = float(d.get("length", 0.0)) or 1.0
            t = (length / flat_speed_ms) / 60.0
            g.add_edge(u, v, length_m=length, time_min=t)
            if directed:
                g.add_edge(v, u, length_m=length, time_min=t)
        return RoadNetwork(graph=g, shelters=set()), None

    if dem_path is None:
        raise ValueError("dem_path is required when apply_slope=True")

    import rasterio

    # After project_graph, node x/y AND edge geometry are ALL in EPSG:5179.
    # Only the DEM lookup needs geographic coordinates.
    to_wgs = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

    n_geom = n_straight = n_clip = 0
    n_elev = n_nodata = n_edges_nodata = 0
    slopes, seglens, t_flat, t_fwd, t_rev = [], [], [], [], []
    clipped_edges: list[dict] = []

    with rasterio.open(dem_path) as src:
        for (u, v), d in undirected.items():
            geom = d.get("geometry")
            if geom is not None:
                x, y = np.array(geom.coords).T          # already EPSG:5179
                n_geom += 1
            else:
                # ~33 % of edges carry no LineString. OSM omits geometry when the
                # way runs straight between its two nodes, so straight-line
                # interpolation is the intended reading, not a fallback. The
                # split is recorded in the stats either way.
                x = np.array([G.nodes[u]["x"], G.nodes[v]["x"]], float)
                y = np.array([G.nodes[u]["y"], G.nodes[v]["y"]], float)
                n_straight += 1

            r = _resample_uniform(np.asarray(x, float), np.asarray(y, float), sampling_m)
            length = float(d.get("length", 0.0)) or 1.0
            if r is None:
                t = (length / flat_speed_ms) / 60.0
                g.add_edge(u, v, length_m=length, time_min=t)
                if directed:
                    g.add_edge(v, u, length_m=length, time_min=t)
                continue
            xs, ys, dl = r
            lo, la = to_wgs.transform(xs, ys)
            z = np.array([w[0] for w in src.sample(np.column_stack([lo, la]))], float)
            z[z <= -1000.0] = np.nan
            n_bad = int((~np.isfinite(z)).sum())
            n_elev += int(z.size)
            n_nodata += n_bad
            n_edges_nodata += 1 if n_bad else 0
            dz = np.diff(z)
            if not np.isfinite(dz).all():
                dz = np.nan_to_num(dz, nan=0.0)

            s = dz / dl
            if max_abs_slope is not None:
                over = int((np.abs(s) > max_abs_slope).sum())
                if over:
                    n_clip += over
                    clipped_edges.append({
                        "u": int(u), "v": int(v),
                        "n_subsegments_clipped": over,
                        "max_abs_slope_raw": float(np.abs(s).max()),
                        "xy_5179": [float(xs[0]), float(ys[0])],
                    })
                    s = np.clip(s, -max_abs_slope, max_abs_slope)

            sp_f = np.array([elderly_speed_ms(q, flat_speed_ms) for q in s])
            sp_r = np.array([elderly_speed_ms(-q, flat_speed_ms) for q in s[::-1]])
            tf = float(dl * len(s) / flat_speed_ms)
            ta = float((dl / sp_f).sum())
            tb = float((dl / sp_r).sum())

            slopes.append(np.abs(s))
            seglens.append(np.full(s.size, dl))
            t_flat.append(tf); t_fwd.append(ta); t_rev.append(tb)

            g.add_edge(u, v, length_m=length, time_min=ta / 60.0)
            if directed:
                g.add_edge(v, u, length_m=length, time_min=tb / 60.0)

    clipped_edges.sort(key=lambda e: -e["max_abs_slope_raw"])
    stats = SlopeStats(
        sampling_m=sampling_m,
        max_abs_slope=max_abs_slope,
        n_edges_undirected=len(undirected),
        n_edges_directed=g.number_of_edges(),
        n_subsegments=int(sum(a.size for a in slopes)),
        n_edges_with_geometry=n_geom,
        n_edges_straight_line=n_straight,
        n_clipped_subsegments=n_clip,
        clipped_edges=clipped_edges,
        slope_abs=np.concatenate(slopes),
        seg_len=np.concatenate(seglens),
        time_flat_s=np.array(t_flat),
        time_fwd_s=np.array(t_fwd),
        time_rev_s=np.array(t_rev),
        n_elev_samples=n_elev,
        n_nodata_samples=n_nodata,
        n_edges_with_nodata=n_edges_nodata,
    )
    return RoadNetwork(graph=g, shelters=set()), stats


def _reverse_geometry(d: dict) -> dict:
    """Copy an edge dict with its LineString reversed (v->u becomes u->v)."""
    out = dict(d)
    geom = d.get("geometry")
    if geom is not None:
        out["geometry"] = geom.reverse() if hasattr(geom, "reverse") else geom
    return out


def slowest_edges(stats: SlopeStats, net: RoadNetwork, k: int = 10) -> list[dict]:
    """The k edges whose traversal time slope increases the most (seconds)."""
    delta = np.maximum(stats.time_fwd_s, stats.time_rev_s) - stats.time_flat_s
    order = np.argsort(-delta)[:k]
    keys = list(net.graph.edges())
    out = []
    for i in order:
        out.append({
            "rank": len(out) + 1,
            "flat_s": float(stats.time_flat_s[i]),
            "slope_uphill_s": float(max(stats.time_fwd_s[i], stats.time_rev_s[i])),
            "slope_downhill_s": float(min(stats.time_fwd_s[i], stats.time_rev_s[i])),
            "delta_s": float(delta[i]),
            "delta_pct": float(delta[i] / max(stats.time_flat_s[i], 1e-9) * 100.0),
        })
    _ = keys
    return out


__all__ = ["SlopeStats", "build_walk_network", "load_snapshot_graph",
           "slowest_edges", "DEFAULT_SAMPLING_M", "DEFAULT_MAX_ABS_SLOPE"]
