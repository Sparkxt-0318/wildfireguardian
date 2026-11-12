"""Fire sets per recorded input (F-C1): full-grid present fire from the KFS_01 forecast export and per-member new
ignitions from the routing HAZARD packet, all as 375 m cell centres in EPSG:5179."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
INPUTS = REPO / 'data' / 'routing' / 'latest_inputs_try02'
EVENT = 'KFS_01'
CELL = 375.0


def export_path(input_compact: str) -> Path:
    return INPUTS / 'exports' / EVENT / f'FORECAST_{input_compact}.npz'


def packet_dir(region: str, input_compact: str) -> Path:
    return INPUTS / 'packets' / region / input_compact


@dataclass
class FireSet:
    scope: str
    present_xy: np.ndarray                      # (n, 2) cell centres burning at t = 0 (full export grid)
    member_new: list = field(default_factory=list)   # per member: list of (t_start_s, (k, 2) new cell centres)
    member_ids: list = field(default_factory=list)
    packet_present: int = 0                      # present-fire cells inside the packet domain
    valid_until_s: float = 3600.0
    unknown_cells: int = 0
    grid_cells: int = 0


def present_fire(input_compact: str):
    z = np.load(export_path(input_compact))
    a = z['affine_transform']
    if not (a[1] == 0 and a[3] == 0 and a[0] == CELL and a[4] == -CELL):
        raise ValueError(f'unexpected export affine {a}')
    act = z['heat__initial_active_burning_probability']
    vals = np.unique(act[act > 0])
    if vals.size and not np.allclose(vals, 1.0):
        raise ValueError(f'active-burning probability not 0/1: {vals[:5]}')
    rr, cc = np.nonzero(act > 0)
    xy = np.column_stack([a[2] + (cc + 0.5) * a[0], a[5] + (rr + 0.5) * a[4]])
    unknown = int((~z['source_burned_area_valid']).sum())
    return xy, unknown, act.size


def packet_cells_xy(grid: dict, flat_mask) -> np.ndarray:
    """Packet flat masks are row-major with row 0 at the south edge (y0); see DEFINITION.md (verified)."""
    w, h = grid['width'], grid['height']
    m = np.asarray(flat_mask, bool).reshape(h, w)
    rr, cc = np.nonzero(m)
    res = grid['resolution']
    return np.column_stack([grid['x0'] + (cc + 0.5) * res, grid['y0'] + (rr + 0.5) * res])


def _key(xy):
    return {(int(round(x)), int(round(y))) for x, y in xy}


def load(region: str, input_compact: str) -> FireSet:
    present, unknown, ncell = present_fire(input_compact)
    hz = json.loads((packet_dir(region, input_compact) / 'HAZARD.json').read_text())
    if hz['crs'] != 'EPSG:5179' or hz['valid_from'] != 0.0:
        raise ValueError('unexpected packet CRS or window')
    pres_keys = _key(present)
    fs = FireSet(scope=f'{region}/{input_compact}', present_xy=present, valid_until_s=float(hz['valid_until']),
                 unknown_cells=unknown, grid_cells=ncell)
    first = None
    for m in hz['members']:
        bps = m['breakpoints']
        if len(m['flame']) != len(bps) - 1:
            raise ValueError('flame intervals do not match breakpoints')
        seen, new = set(), []
        for i, mask in enumerate(m['flame']):
            xy = packet_cells_xy(hz['grid'], mask)
            k = _key(xy)
            if i == 0:
                inside = k & pres_keys
                if first is None:
                    first = len(inside)
                # Every packet flame cell at t = 0 must be a full-grid present cell (consistency check).
                if k - pres_keys:
                    raise ValueError(f'{fs.scope} {m["id"]}: {len(k - pres_keys)} t=0 flame cells not in export')
            fresh = sorted(k - pres_keys - seen)
            seen |= set(fresh)
            if fresh:
                new.append((float(bps[i]), np.array(fresh, float)))
        fs.member_new.append(new)
        fs.member_ids.append(m['id'])
    fs.packet_present = first or 0
    return fs
