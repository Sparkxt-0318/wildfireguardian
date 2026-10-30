"""Read-only, targeted consistency check for the radiation prototype."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.track_a.resolve()
    sys.path.insert(0, str(root / "experimental/flame-front-radiation/src"))
    import numpy as np
    from wfg_flamefront import flux_at_points, flux_enclosure

    member = {"ignition_time_s": np.zeros((2, 2)), "residence_s": 10.0}
    grid = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    values = {}
    operations = {
        "point": lambda: flux_at_points([[3.0, 3.0]], [1.5], member, grid),
        "enclosure": lambda: flux_enclosure([2.0, 4.0, 2.0, 4.0], [1.0, 2.0], member, grid),
    }
    for name, operation in operations.items():
        try:
            raw = operation()
            values[name] = {"state": "RETURNED", "value": np.asarray(raw).tolist()}
        except Exception as exc:
            values[name] = {"state": "RAISED", "type": type(exc).__name__, "message": str(exc)}
    consistent_refusal = values["point"].get("type") == values["enclosure"].get("type") == "UnsupportedGeometry"
    result = {
        "scope": "simultaneous-ignition unsupported geometry consistency only",
        "host": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "track_head": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (root / "experimental/flame-front-radiation/src/wfg_flamefront").glob("*.py")
        },
        "fixture": {"ignition_time_s": [[0, 0], [0, 0]], "residence_s": 10, "query_time_s": 1.5, "interval_s": [1, 2], "point_xy": [3, 3], "box_xy": [2, 4, 2, 4], "affine_transform": list(grid)},
        "observations": values,
        "consistent_unsupported_refusal": consistent_refusal,
        "status": "PASS_TARGETED_REFUSAL" if consistent_refusal else "FAIL_TARGETED_REFUSAL",
        "not_established": ["physical correctness", "full enclosure proof", "routing acceptance"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "observations": values}, indent=2))
    return 0 if consistent_refusal else 1


if __name__ == "__main__":
    raise SystemExit(main())
