"""Download the OSM extract (if missing) and build the processed synthetic world.

Usage: .venv/bin/python scripts/01_build_world.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lastgasp.pipeline import get_world, load_config  # noqa: E402

cfg = load_config()
w, bxy, net = get_world(cfg)
kinds = {}
for d in net.devices:
    kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
summary = {
    "source": w["source"], "note": w["note"], "width_m": round(w["width_m"], 1), "height_m": round(w["height_m"], 1),
    "area_km2": round(w["width_m"] * w["height_m"] / 1e6, 3), "n_roads": len(w["roads"]),
    "n_buildings": len(w["buildings"]), "n_osm_buildings": w["n_osm_buildings"],
    "n_synthetic_buildings": w["n_synthetic_buildings"], "substation": w["substation"]["name"],
    "n_poles": int(net.n_poles), "devices": kinds,
}
print(json.dumps(summary, indent=2))
(ROOT / "results").mkdir(exist_ok=True)
(ROOT / "results/world_summary.json").write_text(json.dumps(summary, indent=2))
