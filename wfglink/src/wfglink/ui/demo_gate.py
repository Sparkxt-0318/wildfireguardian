"""The demo gate: is this commit demo-ready?

    python -m wfglink demo-gate [--seconds 60] [--playlist booth/playlist.yaml] [--out DIR] [--config FILE ...]

Runs the live screen headless (Qt offscreen) for `seconds` three times: fire mode on
synthetic video, fire mode on the booth playlist, and ember mode ("Become an ember") on a
generated phone scene played like a camera (ui/phone_scene.py; no camera is opened). It
passes when every run went without errors, analysed and painted frames and produced finite
numbers, when the playlist run really played clips (no synthetic fallback because the clips
are missing), and when the ember run tracked phones with finite speeds. Screenshots and a
JSON report go to `out`. Used before every daily `wfglink-demo-YYYYMMDD` tag (scripts/tag_demo.sh).
"""
from __future__ import annotations

import json
import math
import os

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import git_state, now_shanghai


def _healthy(res: dict, seconds: float, needs_clips: bool, ember: bool = False) -> tuple[bool, list[str]]:
    why = []
    if res["errors"]:
        why.append("errors: " + "; ".join(res["errors"][:3]))
    if res["frames"] < max(10, seconds * 3):
        why.append(f"too few analysed frames ({res['frames']})")
    if res["paints"] < max(10, seconds * 3):
        why.append(f"too few painted frames ({res['paints']})")
    last = res.get("last", {})
    for k in ("count_rate", "speed"):
        v = last.get(k)
        if v is not None and not math.isfinite(v):
            why.append(f"{k} is not finite")
    if needs_clips:
        states = res.get("states", {})
        if not states.get("playing"):
            why.append("no clip played (are the clips in data/raw?)")
        elif states.get("synthetic"):
            why.append("the playlist fell back to synthetic video")
    if ember:
        e = res.get("ember") or {}
        if res.get("camera_state") not in ("ok", "starting"):
            why.append(f"ember mode camera state is {res.get('camera_state')!r} (see the log for the reason)")
        if not e.get("states"):
            why.append("ember mode showed no analysed frame")
        elif not e.get("max_count"):
            why.append("ember mode tracked no phone")
        elif not e.get("speeds"):
            why.append("ember mode gave no ember speed")
    return not why, why


def demo_gate(seconds: float = 60.0, playlist: str | None = None, out: str = "results/runs/demo_gate",
              config: list[str] | None = None) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from wfglink.ui.booth_app import ember_spec, run_live, source_spec

    out_dir = PROJECT_ROOT / out
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(*(config or []))
    report = {"at": now_shanghai(), "git": git_state(), "seconds": seconds, "runs": {}}
    ok_all = True
    runs = (("synthetic", source_spec(synthetic=True), "fire"),
            ("playlist", source_spec(playlist=playlist, cfg=cfg), "fire"),
            ("ember", source_spec(synthetic=True), "ember"))
    for name, spec, mode in runs:
        res = run_live(cfg, source=spec, screen="primary", lang="ko", duration_s=seconds,
                       screenshot=str(out_dir / f"{name}.png"), ember=ember_spec(synthetic=True), start_mode=mode)
        ok, why = _healthy(res, seconds, needs_clips=(name == "playlist"), ember=(mode == "ember"))
        res["ok"], res["why"] = ok, why
        report["runs"][name] = res
        ok_all = ok_all and ok
        print(f"demo gate {name}: {'PASS' if ok else 'FAIL'} frames={res['frames']} paints={res['paints']} {why}")
    report["pass"] = ok_all
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print("demo gate:", "PASS" if ok_all else "FAIL", f"({out_dir / 'report.json'})")
    return 0 if ok_all else 1
