"""Cut-off-hour environment snapshots for the six held-out US fires (PROTOCOL.md 2.1): REBUILT inputs.

Weather (2 m temperature, 10 m wind east/north; ECMWF IFS via the Open-Meteo archive) comes from the
rasters written by research/forecast-v2/scripts/rebuild_environment.py (--stages inventory weather).
Slope, tree cover and biome come from research/harness-2026-11/data-fetch/us2024_static.
Only hours that are some window's `weather_hour` (never after its cut-off) are read.

    python build_env.py --root ENVROOT/environment_public --out ENVDIR
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from cases import REPO, load_windows

STATIC = REPO / "research/harness-2026-11/data-fetch/us2024_static"
WEATHER = ("temperature_2m", "wind_eastward_10m", "wind_northward_10m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for event, ws in load_windows().items():
        wdir = a.root / "regions" / event / "weather"
        if not (wdir / "ecmwf_ifs_complete.json").exists():
            print(f"{event}: weather not available (NOT BUILT)")
            continue
        bands = pd.read_csv(wdir / "ecmwf_ifs_bands.csv")
        band = dict(zip(pd.to_datetime(bands.time_utc, utc=True), bands.band))
        hours = sorted({w.weather_hour for w in ws})
        z = np.load(STATIC / f"{event}_static.npz", allow_pickle=False)
        H, W = ws[0].shape
        if tuple(z["shape"]) != (H, W) or not bool(z["all_static_valid"].all()):
            raise ValueError(f"{event}: static layers do not match the case rectangle")
        env = np.zeros((len(hours), 19, H, W), np.float32)
        for c, name in enumerate(WEATHER):
            with rasterio.open(wdir / f"{name}_375m.tif") as src:
                if (src.height, src.width) != (H, W):
                    raise ValueError(f"{event}: weather grid differs from the case rectangle")
                for i, h in enumerate(hours):
                    v = src.read(int(band[h]), masked=True).filled(np.nan)
                    if not np.isfinite(v).all():
                        raise ValueError(f"{event}: missing weather at {h}")
                    env[i, c] = v
        env[:, 3] = z["slope_degrees"]
        env[:, 4] = z["tree_cover_percent"]
        for cls in range(1, 15):
            env[:, 4 + cls] = z["biome"] == cls
        if not (env[:, 5:].sum(axis=1) == 1).all():
            raise ValueError(f"{event}: a cell has no biome class in 1..14")
        np.savez_compressed(a.out / f"{event}.npz", env=env, hours=np.array([h.isoformat() for h in hours]))
        print(f"{event}: {len(hours)} snapshots {env.shape[2:]} T {env[:, 0].min():.1f}..{env[:, 0].max():.1f} C "
              f"wind max {np.hypot(env[:, 1], env[:, 2]).max():.1f} m/s")


if __name__ == "__main__":
    main()
