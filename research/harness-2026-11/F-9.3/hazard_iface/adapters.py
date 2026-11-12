"""Adapters: source -> ArrivalScenario (F-9.3 DESIGN.md @df2c797; unknown flags per Iris's definition)."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

from .scenario import INPUTS, REPO, ArrivalScenario

T0 = dt.datetime(2025, 3, 22, 2, 24, tzinfo=dt.timezone.utc)
EXPORT_GRID = {'x0': 1085250.0, 'y0': 1845375.0 - 79 * 375.0, 'resolution': 375.0, 'width': 237, 'height': 79}


def c651_known_flags(region: str, tag: str) -> dict:
    """Iris: three flags from the packet's constructed masks (window-shaped, north-up rows).
    known_burned_state = ~unknown_cumulative_state; known_probability = ~(policy_zero & ~known_burned & ~U_state);
    inside_reconstruction = burned-state known (for KFS exports the state comes from the arrival raster's valid mask,
    so 'unknown state' equals 'outside the reconstruction footprint')."""
    with np.load(INPUTS / 'packets' / region / tag / 'constructed_arrays.npz') as z:
        us = z['mask__unknown_cumulative_state'].astype(bool)
        uq = z['mask__policy_assigned_zero'].astype(bool) & ~z['mask__known_burned'].astype(bool) & ~us
    return {'known_burned_state': ~us, 'known_probability': ~uq, 'inside_reconstruction': ~us}


def from_c651(region: str, tag: str) -> ArrivalScenario:
    return ArrivalScenario(source='c651', rule='random_draws', region=region, start_tag=tag,
                           label='recorded c651 forecast (unchanged build)', known=c651_known_flags(region, tag),
                           provenance={'packet': f'packets/{region}/{tag}'})


def from_zones_plan(zone_plan: dict, region: str, tag: str) -> ArrivalScenario:
    """The API's spread_zones plan, verbatim (sampled 4-member rule)."""
    return ArrivalScenario(source='zones', rule='sampled', region=region, start_tag=tag, zone_plan=zone_plan,
                           label='agency zones as supplied (spread_zones adapter v4, sampled members)',
                           provenance={'plan_sha256': zone_plan['plan_sha256']})


def _rasterize_full_grid(geom: dict) -> np.ndarray:
    """Conservative rasterization of a GeoJSON polygon onto the KFS_01 export grid (spread_zones rules), returned
    NORTH-UP (row 0 = north) like the arrival rasters."""
    sys.path.insert(0, str(REPO))
    from api.adapters import spread_zones as SZ
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    polys = []
    for rings in SZ._rings_of(geom):
        rr = []
        for ring in rings:
            ring = SZ._densify(ring)
            x, y = tr.transform(ring[:, 0], ring[:, 1])
            rr.append(np.column_stack([x, y]))
        polys.append(rr)
    return np.asarray(SZ.rasterize(polys, EXPORT_GRID), bool)    # spread_zones.rasterize is native north-up


def _hours(t: dt.datetime) -> float:
    return (t.astimezone(dt.timezone.utc) - T0).total_seconds() / 3600.0


def from_perimeter_sequence(polygons: list, issued_at: str, region: str, tag: str, graph: Path, horizon_h: float,
                            domain: dict | None = None, rule: str = 'envelope', quantum_s: float = 300.0,
                            label: str = 'agency perimeter sequence as supplied') -> ArrivalScenario:
    """polygons: [(valid_time_iso, geojson_geometry), ...] increasing in time, each the fire extent at that time.
    A cell first inside P_k: lo = t_{k-1} (lo = issued_at for P_1), hi = t_k (earliest reading for lo).
    Cells in no polygon: no fire up to t_n; known = False outside `domain` (or outside P_n without a domain)."""
    issued = dt.datetime.fromisoformat(issued_at.replace('Z', '+00:00'))
    times = [dt.datetime.fromisoformat(t.replace('Z', '+00:00')) for t, _ in polygons]
    if any(b <= a for a, b in zip(times, times[1:])) or times[0] < issued:
        raise ValueError('perimeter times must increase and not precede issued_at')
    lo = np.full((79, 237), np.nan)
    hi = np.full((79, 237), np.nan)
    prev_t = issued
    covered = np.zeros((79, 237), bool)
    for (t, geom), tk in zip(polygons, times):
        m = _rasterize_full_grid(geom) & ~covered
        lo[m] = _hours(prev_t)
        hi[m] = _hours(tk)
        covered |= m
        prev_t = tk
    inside = _rasterize_full_grid(domain) if domain is not None else covered
    known = {'inside_declared_domain': inside}
    prov = {'issued_at': issued.isoformat(), 'perimeter_times': [t.isoformat() for t in times],
            'domain_declared': domain is not None,
            'rule_text': 'cell first inside P_k: [t_{k-1}, t_k] (t_0 = issued_at); outside all: no fire to t_n, '
                         'unknown outside the declared domain'}
    return ArrivalScenario(source='perimeter_sequence', rule=rule, region=region, start_tag=tag, label=label,
                           provenance=prov, known=known, arrival_lo_h=lo,
                           arrival_hi_h=hi if rule == 'envelope' else None, horizon_h=horizon_h,
                           quantum_s=quantum_s, graph=graph)
