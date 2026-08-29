"""Build the Arm D dataset: the Arm A table, plus prior-observation columns.

The Arm A columns are produced by calling ``spread_v2.features`` itself rather
than by reimplementing it, so they are bit-identical to Arm A's own dataset by
construction. Arm D columns are computed separately and joined on
``(fire_id, op_from, row, col)``. Nothing in ``spread_v2`` is modified.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..spread_v2 import grid as gridmod
from ..spread_v2.features import (
    FEATURE_COLUMNS,
    StaticLayers,
    build_transition_frame,
)
from .features import ARM_D_FEATURE_COLUMNS, prior_observation_features

#: Arm A's 16 columns followed by Arm D's 7. Order is fixed and reported.
ARM_D_ALL_FEATURE_COLUMNS: tuple[str, ...] = FEATURE_COLUMNS + ARM_D_FEATURE_COLUMNS

JOIN_KEYS = ["fire_id", "op_from", "row", "col"]


def overpass_cadence(snaps: list) -> dict:
    """Observed cadence for one fire — reported, not assumed.

    The brief requires the cadence on the record per fire, because a fire with
    too few prior overpasses cannot support a stable displacement estimate and
    must be visible as such rather than quietly averaged in.
    """
    if len(snaps) < 2:
        return {"n_overpasses": len(snaps), "gaps_h": [], "median_gap_h": None,
                "span_h": None}
    gaps = [(b.time - a.time).total_seconds() / 3600.0
            for a, b in zip(snaps[:-1], snaps[1:])]
    return {
        "n_overpasses": len(snaps),
        "gaps_h": [round(g, 3) for g in gaps],
        "median_gap_h": round(float(np.median(gaps)), 3),
        "span_h": round((snaps[-1].time - snaps[0].time).total_seconds() / 3600.0, 3),
    }


def arm_d_frame_for_fire(event, grid, snaps: list, arm_a: pd.DataFrame) -> pd.DataFrame:
    """Arm D columns for one fire, aligned to that fire's Arm A rows."""
    by_index = {op.index: k for k, op in enumerate(snaps)}
    parts: list[pd.DataFrame] = []

    for op_from, chunk in arm_a.groupby("op_from", sort=True):
        k = by_index.get(int(op_from))
        if k is None:                     # an Arm A row we cannot place in time
            continue
        rows = chunk["row"].to_numpy()
        cols = chunk["col"].to_numpy()
        feats = prior_observation_features(
            snaps, k, rows, cols, cell_size_m=grid.cell_size_m)
        part = chunk[JOIN_KEYS].copy()
        for name in ARM_D_FEATURE_COLUMNS:
            part[name] = feats[name]
        parts.append(part)

    if not parts:
        return pd.DataFrame(columns=[*JOIN_KEYS, *ARM_D_FEATURE_COLUMNS])
    return pd.concat(parts, ignore_index=True)


def build_arm_d_dataset(
    fire_ids: list[str],
    *,
    cell_size_m: float = gridmod.DEFAULT_CELL_M,
    gap_minutes: float = 90.0,
    buffer_m: float = 6000.0,
    data_dir=None,
    require_weather: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Return ``(dataset, cadence_by_fire)``.

    The arguments mirror ``spread_v2.features.build_dataset`` exactly, and the
    same fires are skipped for the same reasons, so the Arm A rows in the
    returned table are the Arm A rows.
    """
    from ..spread_v2 import data as datamod
    from ..spread_v2.weather import weather_series_from_event

    frames: list[pd.DataFrame] = []
    cadence: dict = {}

    for fid in fire_ids:
        ev = datamod.load_event(fid, data_dir=data_dir)
        ws = weather_series_from_event(ev)
        if ws is None and require_weather:
            continue
        g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=cell_size_m)
        snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=gap_minutes)
        if len(snaps) < 2:
            continue
        static = StaticLayers.from_event(ev, g)
        arm_a = build_transition_frame(ev, g, static, snaps, ws, buffer_m=buffer_m)
        if arm_a.empty:
            continue
        cadence[fid] = overpass_cadence(snaps)
        arm_d = arm_d_frame_for_fire(ev, g, snaps, arm_a)
        merged = arm_a.merge(arm_d, on=JOIN_KEYS, how="left", validate="one_to_one")
        assert len(merged) == len(arm_a), "Arm D join changed the Arm A row count"
        frames.append(merged)

    if not frames:
        empty = pd.DataFrame(columns=("fire_id", "op_from", "row", "col", "label",
                                      *ARM_D_ALL_FEATURE_COLUMNS, "dist_band"))
        return empty, cadence
    return pd.concat(frames, ignore_index=True), cadence


__all__ = [
    "ARM_D_ALL_FEATURE_COLUMNS",
    "build_arm_d_dataset",
    "arm_d_frame_for_fire",
    "overpass_cadence",
]
