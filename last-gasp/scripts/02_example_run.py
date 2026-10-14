"""One fully recorded example run (default config) for maps and timelines. SYNTHETIC.

Usage: .venv/bin/python scripts/02_example_run.py [--fire-seed 0] [--obs-seed 0] [--set key=value ...] [--tag NAME]
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lastgasp.pipeline import load_config, run_one  # noqa: E402
from lastgasp.provenance import git_info  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--fire-seed", type=int, default=0)
ap.add_argument("--obs-seed", type=int, default=0)
ap.add_argument("--set", nargs="*", default=[])
ap.add_argument("--tag", default="default")
a = ap.parse_args()
ov = {}
for kv in a.set:
    k, v = kv.split("=", 1)
    ov[k] = json.loads(v)
cfg = load_config(overrides=ov)
t0 = time.time()
out = run_one(cfg, a.fire_seed, a.obs_seed, keep=True)
art = out.pop("_artifacts")
out["runtime_s"] = round(time.time() - t0, 1)
out["overrides"] = ov
out["provenance"] = {**git_info(), "script": "scripts/02_example_run.py", "config": "configs/default.json",
                     "fire_seed": a.fire_seed, "obs_seed": a.obs_seed}
rdir = ROOT / "results/runs"
rdir.mkdir(parents=True, exist_ok=True)
(rdir / f"example_{a.tag}.pkl").write_bytes(pickle.dumps({"metrics": out, "artifacts": art, "config": cfg}))
(ROOT / f"results/example_{a.tag}_metrics.json").write_text(json.dumps(out, indent=2, default=str))
print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if k != "provenance"}, indent=1))
