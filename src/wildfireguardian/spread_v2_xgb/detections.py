"""FIRMS VIIRS detections → overpass clusters → monotone burned masks.

The observed "ground truth" for the spread classifier is the sequence of
satellite fire-detection overpasses. We:

1. Load the per-fire VIIRS detection CSV (lat, lon, frp, confidence, UTC time).
2. Cluster detections into **overpasses** by a 60-min gap rule: a new overpass
   begins whenever the time since the previous detection exceeds 60 min. This
   merges the SNPP + NOAA-20 multi-satellite passes that arrive within minutes
   of each other into one observation epoch.
3. Snap detections to the 375 m EPSG:5179 grid (orientation-safe, via
   :class:`~wildfireguardian.spread_v2_xgb.grid.Grid`).
4. Build the **monotone** cumulative burned mask per overpass — once a cell is
   detected, it stays burned. This is the label source for the classifier and
   the observed footprint for the IoU/capture metrics.

All times are UTC (FIRMS native). Provenance: NASA FIRMS VIIRS 375 m
active-fire product (VNP14IMG / VJ114IMG), SNPP + NOAA-20.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .grid import Grid


@dataclass
class Overpass:
    """One observation epoch (a 60-min-clustered group of detections)."""

    index: int
    time: pd.Timestamp           # representative (median) UTC time of the cluster
    n_detections: int
    rows: np.ndarray             # grid rows of this overpass's detection cells
    cols: np.ndarray             # grid cols
    frp: np.ndarray              # per-detection FRP (MW), aligned to rows/cols


@dataclass
class ObservedSequence:
    """The full observed spread sequence for one fire on its 375 m grid."""

    fire_id: str
    grid: Grid
    overpasses: list[Overpass]
    # cumulative[k] is the monotone burned boolean mask after overpass k.
    cumulative: list[np.ndarray]
    n_detections_total: int
    n_detections_in_grid: int

    @property
    def n_overpasses(self) -> int:
        return len(self.overpasses)

    def final_mask(self) -> np.ndarray:
        return self.cumulative[-1] if self.cumulative else np.zeros(self.grid.shape, bool)

    def observed_area_ha(self) -> float:
        return float(self.final_mask().sum()) * self.grid.cell_area_m2 / 10_000.0


def load_detections(csv_path) -> pd.DataFrame:
    """Load a FIRMS VIIRS detection CSV with a parsed UTC ``time`` column."""
    df = pd.read_csv(csv_path)
    # The bundle's ``timestamp`` column is ISO 8601 with +00:00 (UTC).
    df["time"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    if "frp" not in df:
        df["frp"] = np.nan
    return df


def cluster_overpasses(times: pd.Series, gap_minutes: float = 60.0) -> np.ndarray:
    """Assign each detection an overpass index via a gap rule.

    A new overpass starts whenever the gap from the previous (time-sorted)
    detection exceeds ``gap_minutes``. Returns an int array aligned to ``times``
    (which must already be sorted ascending).
    """
    t = times.to_numpy()
    if len(t) == 0:
        return np.array([], dtype=np.int64)
    gaps = np.diff(t).astype("timedelta64[s]").astype(np.float64) / 60.0
    new_pass = np.concatenate([[0], (gaps > gap_minutes).astype(np.int64)])
    return np.cumsum(new_pass)


def build_observed_sequence(
    fire_id: str, df: pd.DataFrame, grid: Grid, gap_minutes: float = 60.0
) -> ObservedSequence:
    """Cluster detections into overpasses and build monotone cumulative masks."""
    df = df.sort_values("time").reset_index(drop=True)
    op_idx = cluster_overpasses(df["time"], gap_minutes)
    df = df.assign(_op=op_idx)

    rows, cols, inside = grid.assign_cells(df["longitude"].to_numpy(),
                                           df["latitude"].to_numpy())
    df = df.assign(_row=rows, _col=cols, _inside=inside)
    in_grid = df[df["_inside"]].copy()

    overpasses: list[Overpass] = []
    cumulative: list[np.ndarray] = []
    burned = np.zeros(grid.shape, dtype=bool)

    for k, (_op, g) in enumerate(in_grid.groupby("_op", sort=True)):
        r = g["_row"].to_numpy()
        c = g["_col"].to_numpy()
        overpasses.append(
            Overpass(
                index=k,
                time=pd.Timestamp(g["time"].median()),
                n_detections=len(g),
                rows=r,
                cols=c,
                frp=g["frp"].to_numpy(dtype=np.float64),
            )
        )
        burned = burned.copy()
        burned[r, c] = True
        cumulative.append(burned)

    return ObservedSequence(
        fire_id=fire_id,
        grid=grid,
        overpasses=overpasses,
        cumulative=cumulative,
        n_detections_total=len(df),
        n_detections_in_grid=int(df["_inside"].sum()),
    )


def overpass_frp_grid(grid: Grid, op: Overpass) -> np.ndarray:
    """Rasterise one overpass's per-detection FRP onto the grid (sum per cell).

    Multiple detections in the same 375 m cell have their FRP summed; cells with
    no detection are 0. Used for the FRP-weighted proximity features.
    """
    out = np.zeros(grid.shape, dtype=np.float64)
    frp = np.nan_to_num(op.frp, nan=0.0)
    np.add.at(out, (op.rows, op.cols), frp)
    return out


__all__ = [
    "Overpass",
    "ObservedSequence",
    "load_detections",
    "cluster_overpasses",
    "build_observed_sequence",
    "overpass_frp_grid",
]
