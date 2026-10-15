"""Replay the booth tuning scene at several analysis strides, without a count cap hiding errors.

Usage: .venv/bin/python scripts/check_ember_stride.py --out results/runs/ember_stride.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from wfglink import PROJECT_ROOT
from wfglink.config import config_hash, load_config
from wfglink.ember.pipeline import EmberPipeline
from wfglink.provenance import git_state, now_shanghai
from wfglink.ui.phone_scene import phone_scene_source


def replay(seconds: float, strides: list[int]) -> dict:
    cfg = load_config()
    cfg["ember"]["max_tracks"] = 6
    source = phone_scene_source(cfg, realtime=False)
    pipes = {stride: EmberPipeline(cfg) for stride in strides}
    counts = {stride: Counter() for stride in strides}
    over_visible = {stride: 0 for stride in strides}
    on_light = {stride: 0 for stride in strides}
    runs = {stride: 0 for stride in strides}
    longest = {stride: 0 for stride in strides}
    visible = []
    source.open()
    try:
        scene = source._scene.scene
        width = int(cfg["camera"]["width"])
        boxes = [light["box"] for light in scene.room.lights]
        frames = int(math.ceil(seconds * source.fps))
        for i in range(frames):
            frame = source.read()
            truth = scene.truth(frame.t)
            visible.append((frame.t, sum(1 for phone in truth if phone.get("vis"))))
            visible = [(t, n) for t, n in visible if t >= frame.t - 0.5]
            recent = max(n for _, n in visible)
            for stride, pipe in pipes.items():
                if i % stride:
                    continue
                state = pipe.process(frame)
                counts[stride][state.ember_count or 0] += 1
                over_visible[stride] += int((state.ember_count or 0) > recent)
                caught = False
                for ember in state.embers:
                    near_phone = any(math.hypot(ember["x"] - (width - 1 - p["x"]),
                                                ember["y"] - p["y"]) <= 60 for p in truth)
                    in_light = any(width - 1 - b[2] - 5 <= ember["x"] <= width - 1 - b[0] + 5
                                   and b[1] - 5 <= ember["y"] <= b[3] + 5 for b in boxes)
                    caught |= in_light and not near_phone
                on_light[stride] += int(caught)
                runs[stride] = runs[stride] + 1 if caught else 0
                longest[stride] = max(longest[stride], runs[stride])
    finally:
        source.close()
    results = {}
    for stride in strides:
        n = sum(counts[stride].values())
        over = sum(k for count, k in counts[stride].items() if count > 3)
        results[str(stride)] = {"frames": n, "count_histogram": dict(sorted(counts[stride].items())),
                                "over_three_frames": over, "over_three_fraction": over / n,
                                "over_recent_visible_frames": over_visible[stride],
                                "over_recent_visible_fraction": over_visible[stride] / n,
                                "lamp_frames": on_light[stride],
                                "longest_lamp_s": longest[stride] * stride / source.fps}
    track = PROJECT_ROOT / "src/wfglink/ember/track.py"
    return {"created": now_shanghai(), **git_state(), "tuned_on": True,
            "scene": "booth", "seed": cfg["booth"]["synthetic_seed"], "seconds": seconds,
            "max_tracks": cfg["ember"]["max_tracks"], "config_sha256": config_hash(cfg),
            "track_sha256": hashlib.sha256(track.read_bytes()).hexdigest(), "strides": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=40.0)
    parser.add_argument("--strides", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.seconds <= 0 or any(stride <= 0 for stride in args.strides):
        parser.error("seconds and strides must be positive")
    report = replay(args.seconds, args.strides)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
