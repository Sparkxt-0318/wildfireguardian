import sys, json, hashlib
from pathlib import Path
sys.path.insert(0, "research/harness-2026-11/s-d1/control")
import unmodified_rollout_control as U
import numpy as np
P = U.load_module("full_cohort_pipeline", U.SCRIPTS / "pipeline.py")
ev = "ID-BOF-000683_Wapiti_Wapiti"
pins_new = json.loads(Path("/tmp/claude-0/us2024_regen/pins.json").read_text())
e_new = P.Environment(Path("/tmp/claude-0/us2024_regen/ws/data/environment"), Path("/tmp/claude-0/dd/new"), input_sha256=pins_new)
ro = Path("/tmp/claude-0/ARCH/wildfire/data/environment").resolve()
pins_old = {str(p.relative_to(ro.parent)): U.sha(p) for p in ro.rglob("*") if p.is_file()}
e_old = P.Environment(ro, Path("/tmp/claude-0/dd/old"), input_sha256=pins_old)
s_new = P.perimeter_samples(ev, Path("/tmp/claude-0/perim"), e_new, crop=False)[0]
s_old = P.perimeter_samples(ev, Path("/tmp/claude-0/perim"), e_old, crop=False)[0]
a, b = s_new.environment, s_old.environment
print("shape", a.shape, b.shape, "names", len(e_new.names))
for i, n in enumerate(e_new.names):
    x, y = a[i].astype(float), b[i].astype(float)
    f = np.isfinite(x) & np.isfinite(y)
    d = np.abs(x - y)[f]
    print(f"{n:45s} maxabs={d.max() if d.size else 0:.4g} frac_changed={(d>0).mean() if d.size else 0:.3f} finite_mismatch={int((np.isfinite(x)!=np.isfinite(y)).sum())}")
