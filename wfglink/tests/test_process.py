"""File mode: tables, summary and overlay from one clip."""
import json

import av
import pandas as pd
import pytest

from wfglink.config import load_config
from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.outputs.process import process_clip


@pytest.mark.slow
@pytest.mark.qt
def test_process_writes_tables_summary_and_overlay(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=4)
    src.open()
    clip = tmp_path / "clip.mp4"
    with av.open(str(clip), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        for _ in range(90):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    out = tmp_path / "out"
    summary = process_clip(clip, out, load_config(), overlay_size=(640, 360))
    for name in ("detections.parquet", "frames.parquet", "track_points.parquet", "tracks.parquet",
                 "summary.json", "overlay.mp4"):
        assert (out / name).exists(), name
    assert json.loads((out / "summary.json").read_text())["input"]["sha256"] == summary["input"]["sha256"]
    frames = pd.read_parquet(out / "frames.parquet")
    assert len(frames) == 90
    tracks = pd.read_parquet(out / "tracks.parquet")
    assert {"track_id", "track_speed_px_s", "best_speed_px_s", "direction_deg", "crossings_pos"} <= set(tracks.columns)
    t = summary["totals"]
    assert t["tracks_moving"] > 0 and t["cpc_gross"] >= 0 and "pnf" in t
    a = summary["analysis"]   # a 640x360 clip is analysed at one scale
    det = pd.read_parquet(out / "detections.parquet")
    assert a["factors"] == [1] and a["sizes_px"] == [[640, 360]] and a["detections_by_scale"] == {"1": len(det)}
    with av.open(str(out / "overlay.mp4")) as c:
        assert c.streams.video[0].frames in (0, 90) or sum(1 for _ in c.decode(video=0)) == 90


def test_overlay_writer_needs_no_display(tmp_path):
    """File mode renders offscreen by itself: no QT_QPA_PLATFORM and no display must work."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k not in ("QT_QPA_PLATFORM", "DISPLAY", "WAYLAND_DISPLAY")}
    code = ("from pathlib import Path; from wfglink.outputs.process import OverlayWriter; "
            f"w = OverlayWriter(Path(r'{tmp_path / 'o.mp4'}'), (320, 180), 30.0, 23, 'en'); w.close(); print('ok')")
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, env=env)
    assert res.returncode == 0 and "ok" in res.stdout, res.stderr[-2000:]


def test_tracking_only_clips_report_no_speeds_or_counts(tmp_path):
    """A slow-motion clip (metrics_scope tracking_only) keeps its tracks but reports no speed, count or flux."""
    cfg = load_config()
    src = SyntheticLiveSource(width=480, height=270, realtime=False, seed=3)
    src.open()
    clip = tmp_path / "clip.mp4"
    with av.open(str(clip), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 480, 270, "yuv420p"
        for _ in range(60):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    summ = process_clip(clip, tmp_path / "out", cfg, overlay=False, metrics_scope="tracking_only")
    t = summ["totals"]
    assert summ["metrics_scope"] == "tracking_only" and "tracks" in t
    assert not {"speed_px_s", "cpc_gross", "pnf", "count_rate_per_s"} & set(t)
    assert "cpc_gross" in t["not_reported"]["quantities"] and any("tracking only" in w for w in summ["warnings"])
