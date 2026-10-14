"""The demo gate: is this commit demo-ready?

Runs the booth UI headless (Qt offscreen) for `seconds` on the synthetic source and on an
approved clip, and passes when both ran without errors, processed and painted frames,
and produced finite numbers. Screenshots and a JSON report go to `out`. Used before
every daily `wfglink-demo-YYYYMMDD` tag (scripts/tag_demo.sh).
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import git_state, now_shanghai


def _healthy(res: dict, seconds: float) -> tuple[bool, list[str]]:
    why = []
    if res["errors"]:
        why.append("errors: " + "; ".join(res["errors"][:3]))
    if res["frames"] < max(10, seconds * 3):
        why.append(f"too few processed frames ({res['frames']})")
    if res["paints"] < max(10, seconds * 3):
        why.append(f"too few painted frames ({res['paints']})")
    last = res.get("last", {})
    for k in ("count_rate", "speed"):
        v = last.get(k)
        if v is not None and not math.isfinite(v):
            why.append(f"{k} is not finite")
    return not why, why


def demo_gate(seconds: float = 60.0, clip: str | None = None, out: str = "results/runs/demo_gate") -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from wfglink.ui.booth_app import run_booth

    out_dir = PROJECT_ROOT / out
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    report = {"at": now_shanghai(), "git": git_state(), "seconds": seconds, "runs": {}}
    ok_all = True
    runs = [("synthetic", "synthetic")]
    clip_path = PROJECT_ROOT / clip if clip and not Path(clip).is_absolute() else (Path(clip) if clip else None)
    if clip_path and clip_path.exists():
        runs.append(("clip", f"file:{clip_path}"))
    else:
        report["clip_note"] = f"approved clip not available: {clip}"
        ok_all = False
    for name, source in runs:
        res = run_booth(cfg, source=source, screen="primary", lang="ko", duration_s=seconds,
                        screenshot=str(out_dir / f"{name}.png"))
        ok, why = _healthy(res, seconds)
        res["ok"], res["why"] = ok, why
        report["runs"][name] = res
        ok_all = ok_all and ok
        print(f"demo gate {name}: {'PASS' if ok else 'FAIL'} frames={res['frames']} paints={res['paints']} {why}")
    report["pass"] = ok_all
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print("demo gate:", "PASS" if ok_all else "FAIL", f"({out_dir / 'report.json'})")
    return 0 if ok_all else 1
