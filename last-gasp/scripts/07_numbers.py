"""Collect every quoted number into results/NUMBERS.json with its provenance. SYNTHETIC.

Usage: .venv/bin/python scripts/07_numbers.py
Each entry: value, description, source file, producing script, config, git commit.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lastgasp.provenance import git_info  # noqa: E402

numbers = {}


def add(key, value, desc, source, script, prov, config="configs/default.json"):
    if isinstance(value, float):
        if math.isnan(value):
            value = None
        else:
            value = round(value, 4)
    numbers[key] = {"value": value, "description": desc, "source": source, "script": script, "config": config,
                    "commit": prov.get("commit"), "code_dirty": prov.get("code_dirty")}


cur = git_info()
w = json.loads((ROOT / "results/world_summary.json").read_text())
for k in ("area_km2", "n_buildings", "n_osm_buildings", "n_synthetic_buildings", "n_poles", "n_roads"):
    add(f"world.{k}", w[k], f"Test area: {k}", "results/world_summary.json", "scripts/01_build_world.py", cur)
for k, v in w["devices"].items():
    add(f"world.devices.{k}", v, f"Number of {k} devices in the synthetic network", "results/world_summary.json",
        "scripts/01_build_world.py", cur)

for tag in ("default", "tags50"):
    m = json.loads((ROOT / f"results/example_{tag}_metrics.json").read_text())
    prov = m["provenance"]
    for k, v in m.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            add(f"example.{tag}.{k}", float(v) if isinstance(v, float) else v,
                f"Example run '{tag}' (fire seed {prov['fire_seed']}, obs seed {prov['obs_seed']}, overrides "
                f"{m.get('overrides')}): {k}", f"results/example_{tag}_metrics.json", prov["script"], prov)

s = json.loads((ROOT / "results/sweep_summary.json").read_text())
prov = s["_provenance"]
for sweep, rows in s.items():
    if sweep.startswith("_"):
        continue
    for d in rows:
        for k, v in d.items():
            if k in ("value",) or not isinstance(v, (int, float)) or k.endswith(("_q25", "_q75")):
                continue
            add(f"sweep.{sweep}.{d['value']}.{k}", float(v),
                f"Sweep '{sweep}' at value {d['value']}: {k} (median over {d['n_runs']} runs; spot rates pooled)",
                "results/sweep_summary.json", "scripts/03_sweeps.py + scripts/05_figures_sweeps.py", prov)

# Per-world fire statistics from the default scenario rows of the sweep.
import csv  # noqa: E402

rows = [r for r in csv.DictReader(open(ROOT / "results/sweeps.csv"))
        if r["sweep"] == "scenario" and r["value"] == "meters_50pct" and r["obs_seed"] == "0"]
meta = json.loads((ROOT / "results/sweeps_meta.json").read_text())
n_spots = [int(r["fire_n_spots"]) for r in rows]
n_sig = [int(r["spot_n_true"]) for r in rows]
burned = [float(r["fire_burned_frac_buildings"]) for r in rows]
for k, v in (("n_spots_min", min(n_spots)), ("n_spots_max", max(n_spots)), ("n_significant_spots_min", min(n_sig)),
             ("n_significant_spots_max", max(n_sig)), ("burned_frac_buildings_min", min(burned)),
             ("burned_frac_buildings_max", max(burned))):
    add(f"fireworlds.{k}", v, f"Across the {len(rows)} synthetic fire worlds: {k}", "results/sweeps.csv",
        "scripts/03_sweeps.py", meta)

dm = json.loads((ROOT / "results/demo_metrics.json").read_text())
for k in ("iou_median_while_front_inside", "detection_latency_median_min", "detection_latency_p90_min", "n_tags",
          "n_runs"):
    add(f"demo.{k}", dm[k], f"Tabletop demo analogue: {k}", "results/demo_metrics.json", "scripts/06_demo_sim.py",
        dm["provenance"])
for t, v in zip(dm["times_min"], dm["iou_median_by_time"]):
    add(f"demo.iou_median_t{t}", v, f"Demo burned-area IoU at t = {t} min (median over runs; null if undefined)",
        "results/demo_metrics.json", "scripts/06_demo_sim.py", dm["provenance"])

add("sweep.wall_s", meta["wall_s"], "Wall time of the 410-run sweep (s)", "results/sweeps_meta.json",
    "scripts/03_sweeps.py", meta)
add("sweep.n_runs", meta["n_runs"], "Number of sweep runs", "results/sweeps_meta.json", "scripts/03_sweeps.py", meta)
add("sweep.n_errors", meta["n_errors"], "Number of failed sweep runs", "results/sweeps_meta.json", "scripts/03_sweeps.py",
    meta)
expl = json.loads((ROOT / "results/exploratory_numbers.json").read_text())
for k, v in expl.items():
    if k.startswith("_"):
        continue
    numbers[f"exploratory.{k}"] = {"value": v["value"], "description": v["how"], "source": "results/exploratory_numbers.json",
                                   "script": "inline exploratory command (see LOG.md)", "config": "intermediate",
                                   "commit": "uncommitted intermediate state", "code_dirty": True}

out = {"_note": "All values are from SYNTHETIC simulations, not real-world performance.",
       "_generated_by": "scripts/07_numbers.py", "_generated_at_commit": cur, "numbers": numbers}
(ROOT / "results/NUMBERS.json").write_text(json.dumps(out, indent=1))
print(f"{len(numbers)} numbers written")
