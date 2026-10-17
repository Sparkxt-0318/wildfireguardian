"""File mode: tables, summary and overlay from one clip."""
import json

import av
import numpy as np
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
    assert {"count_rate", "cpc_gross", "cpc_net", "pnf"} <= set(frames.columns)
    tracks = pd.read_parquet(out / "tracks.parquet")
    assert {"track_id", "track_speed_px_s", "best_speed_px_s", "direction_deg", "crossings_pos"} <= set(tracks.columns)
    t = summary["totals"]
    assert t["tracks_moving"] > 0 and t["cpc_gross"] >= 0 and "pnf" in t
    assert summary["metrics_scope"] == "all" and "speed" in summary["units"]
    assert {"pnf", "cpc"} <= set(summary["labels"])
    assert {"vx", "vy", "speed_poly"} <= set(pd.read_parquet(out / "track_points.parquet").columns)
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


def test_tracking_only_clips_report_no_speeds_or_counts(tmp_path, monkeypatch):
    """A slow-motion clip (metrics_scope tracking_only) keeps its tracks but reports no speed, count or flux."""
    cfg = load_config()
    states = []

    class CapturedOverlay:
        def __init__(self, *args):
            pass

        def write(self, state):
            states.append(state)

        def close(self):
            pass

    monkeypatch.setattr("wfglink.outputs.process.OverlayWriter", CapturedOverlay)
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
    out = tmp_path / "out"
    out.mkdir()
    for name in ("field.parquet", "field.csv", "frames.csv", "overlay.mp4", "plausibility.json"):
        (out / name).write_bytes(b"stale all-metrics export")
    summ = process_clip(clip, out, cfg, overlay=True, metrics_scope="tracking_only")
    t = summ["totals"]
    assert summ["metrics_scope"] == "tracking_only" and "tracks" in t
    assert not {"speed_px_s", "cpc_gross", "pnf", "count_rate_per_s"} & set(t)
    assert "cpc_gross" in t["not_reported"]["quantities"] and any("tracking only" in w for w in summ["warnings"])
    assert not {"direction_deg_circular_mean", "gate"} & set(t)
    assert set(summ["units"]) == {"position", "time"} and set(summ["labels"]) == {"scope"}
    assert "t_exp_s" not in summ["exposure"] and "tracking_only" in summ["exposure"]["status"]
    assert "field" not in summ["outputs"] and not (out / "field.parquet").exists()
    assert not any((out / name).exists() for name in ("field.csv", "frames.csv", "overlay.mp4", "plausibility.json"))
    frames = pd.read_parquet(out / "frames.parquet")
    points = pd.read_parquet(out / "track_points.parquet")
    tracks = pd.read_parquet(out / "tracks.parquet")
    det = pd.read_parquet(out / "detections.parquet")
    assert len(frames) == 60 and len(points) > 0 and len(tracks) > 0 and len(det) > 0
    assert {"track_id", "frame", "t", "x_meas", "y_meas", "x", "y", "length", "theta"} <= set(points.columns)
    assert {"track_id", "frame_start", "frame_end", "points", "static"} <= set(tracks.columns)
    for df in (frames, points, tracks, det):
        assert not any("speed" in c or "crossings" in c or c in {
            "vx", "vy", "vx_poly", "vy_poly", "vx_streak", "vy_streak", "u_px_s", "v_px_s", "flux",
            "count_rate", "cpc_gross", "cpc_net", "pnf"} for c in df.columns)
    assert len(states) == 60 and any(len(s.detections) for s in states)
    for state in states:
        assert state.metrics_scope == "tracking_only"
        assert all(getattr(state, k) is None for k in (
            "count_rate", "cpc_gross", "cpc_net", "pnf", "speed", "direction_deg", "field_uvn", "gate"))
        assert state.sparkline.size == 0 and not state.calibrated and state.distance_m is None


@pytest.mark.qt
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_tracking_only_renderer_ignores_invalid_metric_values(monkeypatch, lang):
    """The renderer itself enforces scope, even if its caller supplies computed readouts."""
    from dataclasses import replace

    from PySide6.QtGui import QGuiApplication

    from wfglink.render import scene

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication([])
    used = []
    translate = scene.t

    def translated(language, key, **fmt):
        used.append((language, key))
        return translate(language, key, **fmt)

    monkeypatch.setattr(scene, "t", translated)
    base = scene.LiveState(image=np.zeros((180, 320, 3), dtype=np.uint8), metrics_scope="tracking_only",
                           detections=np.array([[20.0, 30.0]]), trails=[np.array([[10.0, 15.0], [20.0, 30.0]])])
    populated = replace(base, count_rate=123.0, cpc_gross=456, cpc_net=99, pnf=7.5, speed=900.0,
                        direction_deg=45.0, field_uvn=np.array([[[100.0, 100.0, 10.0]]]),
                        gate=((0.0, 0.0), (319.0, 179.0)), sparkline=np.arange(20.0), calibrated=True,
                        distance_m=2.0)
    plain = scene.render_image(640, 360, base, lang)
    filled = scene.render_image(640, 360, populated, lang)
    assert bytes(plain.constBits()) == bytes(filled.constBits())
    assert (lang, "tracking_only") in used and (lang, "tracking_only_note") in used
    assert not {(lang, key) for key in ("count_rate", "cpc", "pnf", "speed", "sparkline", "field_legend", "gate")} & set(used)
    assert app is not None
