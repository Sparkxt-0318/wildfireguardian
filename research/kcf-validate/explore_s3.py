"""EXPLORATORY (not in PROTOCOL.md; written after the first output of satellite_extent.py): where do the satellite-burned cells that
the MEASURED 8 h zone did not cover lie, and had FIRMS/AHI or Choi seen them by t_S? Usage: python3 -I explore_s3.py MAPS.npz OUT.json FIG.png"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import satellite_extent as se
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

m = np.load(sys.argv[1]); sat, v1, v2, v3 = m["sat"], m["v1"], m["v2"], m["v3"]
CX, CY = se.centres(); discs = se.load_discs()
T = datetime(2025, 3, 23, 18, tzinfo=timezone.utc)
dT = se.dist_to_discs([d for d in discs if d["t"] < T], CX, CY)
newb = (sat == 1) & (dT > 0); beyond = newb & ~v3
res = {"label": "EXPLORATORY, not in the frozen protocol. Model output on reconstructed inputs. Not what happened to people.",
       "primary_map": "raw DN, dNBR >= 0.10", "new_burned_cells_not_in_known_area_at_T": int(newb.sum()),
       "of_which_beyond_R8": int(beyond.sum()), "new_detected_by_FIRMS_AHI_between_T_and_t_S": int((newb & v2).sum()),
       "beyond_R8_in_Choi_reached_at_t_S": int((beyond & v1).sum()), "beyond_R8_in_known_area_at_t_S": int((beyond & v2).sum()),
       "new_cells_in_Choi_reached_at_t_S": int((newb & v1).sum()),
       "beyond_R8_column_range_0_237": [int(np.where(beyond)[1].min()), int(np.where(beyond)[1].max())] if beyond.any() else None,
       "discs_added_between_T_and_t_S": int(sum(1 for d in discs if T <= d["t"] < se.T_S)),
       "reading": "No FIRMS/AHI disc is added between T and t_S that touches a satellite-burned cell outside the known area at T; the 23-24 March interval holds no detected growth, so this scene has little power to test the 8 h margin."}
Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
fig, ax = plt.subplots(2, 2, figsize=(14, 6.5), sharex=True, sharey=True)
ext = [se.X0 / 1000, (se.X0 + se.W * se.RES) / 1000, (se.Y0 - se.H * se.RES) / 1000, se.Y0 / 1000]
for a, (t, g) in zip(ax.ravel(), (("Sentinel-2 burned (raw dNBR>=0.10; grey = not assessable)", None), ("Choi TOA reached by t_S (model input)", v1),
                                  ("FIRMS+AHI known area at t_S (replay discs)", v2), ("MEASURED 8 h zone from 23 Mar 18:00 UTC", v3))):
    if g is None:
        img = np.where(sat < 0, 0.5, sat).astype(float); a.imshow(img, extent=ext, cmap="Greys", vmin=0, vmax=1.5)
    else:
        a.imshow(np.where(sat < 0, 0.5, 0.0), extent=ext, cmap="Greys", vmin=0, vmax=1.5, alpha=0.5)
        a.imshow(np.ma.masked_where(~g, g), extent=ext, cmap="Reds", vmin=0, vmax=1.3, alpha=0.8)
        a.contour(CX / 1000, CY / 1000, np.where(sat == 1, 1, 0).astype(float), levels=[0.5], colors="k", linewidths=0.7)
    a.set_title(t, fontsize=9)
fig.suptitle("24 March 2025 02:17 UTC. Model output on reconstructed inputs. Not what happened to people. Axes: EPSG:5179 km.", fontsize=9)
fig.tight_layout(); fig.savefig(sys.argv[3], dpi=130)
print(json.dumps(res)[:400])
