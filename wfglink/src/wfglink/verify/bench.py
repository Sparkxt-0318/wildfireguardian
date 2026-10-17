"""Live runtime benchmark of the booth with and without the high-precision verifier
(python -m wfglink verify bench). A Linux reference only: the booth Mac is not measured.

Each mode runs the booth headless (Qt offscreen) for `seconds`, in a fresh child process so
memory figures do not mix: ui.booth_app.run_live, as the demo gate drives it, on the
playlist (booth/playlist.yaml by default), a clip or synthetic video, with
live.worker_mode thread. Modes: legacy (the default config) and high_precision (the
overlay with the given method; the booth's profile is live_downscaled, so a method without
settings for that profile is unavailable and the report says so). No product code
changes: the child wraps, for the run only, LiveAnalyser.process (the times around each
analysed frame), BoothWindow.paintEvent (paint times) and Ledger.checkpoint (acceptances
and their delays), and samples its own RSS once a second.

Report (JSON), per mode:
- frames: analyser calls, frames analysed by the pipeline (not repeats), analysed frames per
  second, frames skipped (published by playback but never analysed: newest frame wins) and
  the playback counters (decoded, shown, late drops);
- processing ms (the pipeline's own per-frame time, median and p95), observer ms (the
  verifier's on_frame), and the whole analyser call;
- publish-to-state latency: from Frame.t_wall (playback published the frame, monotonic
  clock) to the state being available (the analyser returned), median and p95, over all
  analysed frames and over the decision frames (frames in which a track was accepted);
- paint fps per one-second bin (median and p5) from the paint times;
- RSS peak and slope (MB per hour, a least-squares line over the samples after the first
  tenth of the run);
- confirmation delay (t_accept - t_confirm and t_accept - t_first) of the tracks accepted;
- the run_live summary (frames, paints, errors, and the states and clips the window saw) and
  the scorer's status.

A latency at decision frames needs a scorer that decides: when the scorer is unavailable on
the booth's profile (or legacy mode, or no track was accepted), decision_frames is
{"status": "NOT_MEASURED", "reason": ...}, never an empty statistic. The booth plays
synthetic video when a playlist cannot be read or no clip plays; a playlist or clip source
whose analysed frames came from synthetic video gets source_problem (and the command exits
1), so its numbers are not taken for the playlist's.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

MODES = ("legacy", "high_precision")
NOTE = ("Linux container reference only (headless Qt offscreen); not the booth Mac. Latencies use the monotonic "
        "clock from playback's publish (Frame.t_wall) to the analysed state.")


def _stat(v, ps=(50, 95)) -> dict[str, Any]:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    out: dict[str, Any] = {"n": int(v.size)}
    for p in ps:
        out["median" if p == 50 else f"p{p}"] = float(np.percentile(v, p)) if v.size else None
    return out


def _slope_mb_h(samples: list[tuple[float, float]]) -> float | None:
    s = [(t, m) for t, m in samples if m is not None]
    if len(s) < 3:
        return None
    t = np.array([a for a, _ in s])
    m = np.array([b for _, b in s])
    keep = t >= t[0] + 0.1 * (t[-1] - t[0])
    if keep.sum() < 3:
        keep[:] = True
    a = np.polyfit(t[keep] - t[keep][0], m[keep], 1)[0]
    return float(a * 3600.0)


def run_mode(mode: str, seconds: float, method: str = "rules", source: dict | None = None,
             configs: list[str] | None = None) -> dict[str, Any]:
    """One mode in this process (see the module notes); returns its report."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from wfglink.config import load_config
    from wfglink.ui.booth_app import BoothWindow, LiveAnalyser, rss_mb, run_live, source_spec

    if mode == "legacy":
        cfg = load_config(*(configs or []))
    else:
        from wfglink.verify.config import hp_config

        cfg = hp_config(method, configs or ())
    cfg.setdefault("live", {})["worker_mode"] = "thread"
    spec = source or source_spec(cfg=cfg)
    rows: list[tuple] = []
    synthetic_frames = [0]
    paints: list[float] = []
    accepts: list[tuple[float, float, float]] = []
    state: dict[str, Any] = {"accepted": 0}
    lock = threading.Lock()

    orig_process = LiveAnalyser.process
    orig_paint = BoothWindow.paintEvent

    def process(self, frame):
        t_in = time.monotonic()
        acc0 = state["accepted"]
        key = str(frame.meta.get("clip") or "clip")
        before = self.pipes.get(key)
        n0 = before.stats.frames_analysed if before is not None else 0
        st = orig_process(self, frame)
        t_out = time.monotonic()
        if frame.meta.get("synthetic"):
            synthetic_frames[0] += 1
        pipe = self.pipes.get(self.active)
        analysed = pipe is not None and (pipe is not before or pipe.stats.frames_analysed > n0) and \
            pipe.stats.frames_analysed > 0
        proc = pipe.stats.proc_ms[-1] if analysed and len(pipe.stats.proc_ms) else np.nan
        obs = getattr(pipe, "observer", None) if pipe is not None else None
        obs_ms = obs._ms[-1] if analysed and obs is not None and len(obs._ms) else np.nan
        if pipe is not None:
            state["last_pipe"] = pipe
        with lock:
            rows.append((int(frame.index), float(frame.t_wall), t_in, t_out, bool(analysed), float(proc),
                         float(obs_ms), state["accepted"] - acc0))
        return st

    def paint(self, ev):
        orig_paint(self, ev)
        paints.append(time.monotonic())

    ledger_cls = orig_check = None
    if mode != "legacy":
        from wfglink.verify import ledger as led

        ledger_cls = led.Ledger
        orig_check = led.Ledger.checkpoint

        def checkpoint(self, key, t, window, scorer, flags=(), frame=-1):
            ok = orig_check(self, key, t, window, scorer, flags, frame)
            if ok:
                d = self.get(key)
                state["accepted"] += 1
                accepts.append((float(d.t_accept - d.t_confirm), float(d.t_accept - d.t_first), time.monotonic()))
            return ok

        led.Ledger.checkpoint = checkpoint
    rss: list[tuple[float, float | None]] = []
    stop = threading.Event()

    def sample():
        pid = os.getpid()
        while not stop.is_set():
            rss.append((time.monotonic(), rss_mb(pid)))
            stop.wait(1.0)

    sampler = threading.Thread(target=sample, daemon=True)
    LiveAnalyser.process, BoothWindow.paintEvent = process, paint
    sampler.start()
    t0 = time.monotonic()
    try:
        res = run_live(cfg, source=spec, screen="primary", lang="en", duration_s=float(seconds))
    finally:
        stop.set()
        sampler.join(3.0)
        LiveAnalyser.process, BoothWindow.paintEvent = orig_process, orig_paint
        if ledger_cls is not None:
            ledger_cls.checkpoint = orig_check
    wall = time.monotonic() - t0
    arr = rows
    analysed = [r for r in arr if r[4]]
    lat = [r[3] - r[1] for r in analysed if r[1] > 0]
    lat_dec = [r[3] - r[1] for r in analysed if r[1] > 0 and r[7] > 0]
    span = (analysed[-1][3] - analysed[0][3]) if len(analysed) > 1 else 0.0
    pb = res.get("playback") or {}
    pf = None
    if len(paints) > 2:
        p = np.asarray(paints)
        edges = np.arange(np.floor(p[0]) + 1.0, p[-1], 1.0)
        if edges.size >= 2:
            counts = np.histogram(p, bins=edges)[0]
            pf = {"median": float(np.median(counts)), "p5": float(np.percentile(counts, 5)), "bins": int(counts.size)}
    peak = max((m for _, m in rss if m is not None), default=None)
    scorer = None
    lp = state.get("last_pipe")
    if lp is not None and getattr(lp, "observer", None) is not None:
        sc = lp.observer.scorer
        scorer = {"available": bool(getattr(sc, "available", True)), "reason": getattr(sc, "reason", None),
                  "profile": lp.observer.profile, **sc.identity()}
    problem = source_problem(spec, synthetic_frames[0], len(arr), res)
    return {
        "mode": mode, "method": None if mode == "legacy" else method, "seconds": float(seconds),
        "wall_s": round(wall, 2), "source": spec,
        "frames": {"analyser_calls": len(arr), "analysed": len(analysed),
                   "analysed_fps": (len(analysed) - 1) / span if span > 0 else None,
                   "skipped_newest_frame_wins": max(int(pb.get("shown", 0)) - len(arr), 0) if pb else None,
                   "playback": pb},
        "processing_ms": _stat([r[5] for r in analysed]), "observer_ms": _stat([r[6] for r in analysed]),
        "analyser_call_ms": _stat([(r[3] - r[2]) * 1000.0 for r in analysed]),
        "publish_to_state_ms": {**_stat(np.asarray(lat) * 1000.0),
                                "decision_frames": decision_latency(mode, scorer, lat_dec)},
        "paint_fps": pf, "paints": len(paints),
        "rss_mb": {"peak": peak, "slope_mb_per_h": _slope_mb_h(rss), "samples": len(rss)},
        "confirmation_delay_s": {"confirm_to_accept": _stat([a[0] for a in accepts]),
                                 "first_to_accept": _stat([a[1] for a in accepts]), "accepted": len(accepts)}
        if mode != "legacy" else None,
        "scorer": scorer, "source_problem": problem, "synthetic_frames": synthetic_frames[0],
        "run_live": {k: res.get(k) for k in ("seconds", "frames", "paints", "error_count", "errors", "worker_mode",
                                             "clip", "source", "states", "clips")},
        "playback_events": [e for e in (res.get("events") or []) if isinstance(e, dict)
                            and str(e.get("kind") or e.get("event") or "") in ("playlist_error", "synthetic")],
    }


def source_problem(spec: dict[str, Any], synthetic_frames: int, calls: int, res: dict[str, Any]) -> str | None:
    """Why a playlist or clip run did not measure that source (synthetic video played), or None."""
    if spec.get("kind") not in ("playlist", "clip"):
        return None
    states = res.get("states") or {}
    if synthetic_frames > 0 or states.get("synthetic"):
        return (f"the {spec.get('kind')} source played synthetic video ({synthetic_frames} of {calls} analyser calls; "
                f"states {states}): the playlist could not be read or no clip played, so these numbers are not the "
                "source's")
    if calls == 0:
        return f"no frame of the {spec.get('kind')} source reached the analyser"
    return None


def decision_latency(mode: str, scorer: dict[str, Any] | None, lat_dec_s) -> dict[str, Any]:
    """Publish-to-state latency at decision frames (ms), or NOT_MEASURED with the reason."""
    if mode == "legacy":
        return {"status": "NOT_MEASURED", "reason": "legacy mode makes no decisions"}
    if scorer is not None and not scorer.get("available", True):
        return {"status": "NOT_MEASURED", "reason": f"the scorer is unavailable on profile {scorer.get('profile')} "
                                                    f"({scorer.get('reason')}): no decision frames, model inference "
                                                    "not measured"}
    if not len(lat_dec_s):
        return {"status": "NOT_MEASURED", "reason": "no track was accepted during the run"}
    return {"status": "MEASURED", **_stat(np.asarray(lat_dec_s, float) * 1000.0)}


def bench(seconds: float = 300.0, method: str = "rules", source: dict | None = None, configs: list[str] | None = None,
          modes=MODES, out: str | Path | None = None, in_process: bool = False, timeout_pad_s: float = 120.0
          ) -> dict[str, Any]:
    """Every mode, each in its own child process (in_process: here, for debugging); writes out."""
    from wfglink.provenance import git_state, now_shanghai

    results = {}
    for mode in modes:
        if in_process:
            results[mode] = run_mode(mode, seconds, method, source, configs)
            continue
        with tempfile.TemporaryDirectory() as td:
            res_p = Path(td) / "mode.json"
            arg = json.dumps({"mode": mode, "seconds": seconds, "method": method, "source": source,
                              "configs": configs or [], "out": str(res_p)})
            env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
            proc = subprocess.run([sys.executable, "-m", "wfglink.verify.bench", "--child", arg], capture_output=True,
                                  text=True, timeout=float(seconds) + timeout_pad_s, env=env)
            if proc.returncode != 0 or not res_p.is_file():
                results[mode] = {"mode": mode, "error": f"child exited {proc.returncode}",
                                 "stderr": proc.stderr[-3000:]}
                continue
            results[mode] = json.loads(res_p.read_text(encoding="utf-8"))
    rep = {"schema_version": 1, "created": now_shanghai(), "note": NOTE, "platform": sys.platform,
           "seconds_per_mode": float(seconds), "method": method, "modes": results, **git_state()}
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    return rep


def _child(arg: str) -> int:
    a = json.loads(arg)
    res = run_mode(a["mode"], float(a["seconds"]), a["method"], a.get("source"), a.get("configs"))
    Path(a["out"]).write_text(json.dumps(res, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        raise SystemExit(_child(sys.argv[2]))
    raise SystemExit("usage: python -m wfglink verify bench ... (this module's --child is internal)")
