"""Write SOURCE_SHA256.json for this overlay: every source file in the folder, the frozen files it imports (pinned in
src/wfg_members/kit.py) and the one shared touch point forecast/wildfire/rollout.py. `--check` verifies instead."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "src"))
from wfg_members.kit import PINNED  # noqa: E402

EXTRA = ["forecast/wildfire/rollout.py", "forecast/tests/test_rollout_trajectory_callback.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest():
    own = sorted(p for p in HERE.rglob("*") if p.is_file() and p.suffix in (".py", ".txt", ".md")
                 and "__pycache__" not in p.parts and p.name != "SOURCE_SHA256.json")
    return {"overlay": {str(p.relative_to(REPO)): sha(p) for p in own},
            "frozen_imports_pinned": dict(PINNED),
            "shared_touch_point": {r: sha(REPO / r) for r in EXTRA}}


if __name__ == "__main__":
    out = HERE / "SOURCE_SHA256.json"
    m = manifest()
    if "--check" in sys.argv:
        old = json.loads(out.read_text())
        bad = [k for sec in m for k in m[sec] if old.get(sec, {}).get(k) != m[sec][k]]
        raise SystemExit("MISMATCH %s" % bad if bad else 0)
    out.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print("wrote", out, sum(len(v) for v in m.values()), "entries")
