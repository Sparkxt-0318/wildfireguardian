"""The booth application: fullscreen live measurement on the external monitor.

Sources come from a SourceChain built from config (camera.chain): the iPhone, then the USB
webcam, then labelled replay of the prepared booth clip, then a labelled synthetic demo.
When a prepared clip (booth-prep metadata) is configured, camera and replay frames go
through screen rectification and frame-code timing; otherwise frames are analysed
directly and the screen says the clip is unprepared.

Screen health (PLAN.md section 7: a source is healthy only when the markers are locked and
the decoded index advances). With booth metadata, every live camera attempt gets its own
ScreenCheck in its capture thread, so a camera filming a paused or absent screen becomes
unhealthy after capture.freeze_s and the chain falls back (webcam, then labelled replay),
switching back once the iPad plays again. While a camera is shown, its pipeline's booth
status turns the picture into "iPad paused" or "iPad screen not found"; on the fallback
source a small note says why the better camera is out of use. Sources without booth
metadata (synthetic, file, an unprepared camera) are never checked.

Keys: L language, I limits card, T tracks, F field, G gate, Esc quit (press twice).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.io.capture import ChainConfig, ChainStatus, SourceChain, SourceOption
from wfglink.io.devices import AutoCameraSource, camera_backends, list_cameras, pick_camera
from wfglink.io.frames import Frame
from wfglink.io.sources import CameraSpec, FileSource
from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.pipeline import BoothContext, Pipeline, frame_wall_time, heartbeat_counters, screen_index
from wfglink.render.scene import LiveState, paint_scene
from wfglink.ui.live_check import choose_screen

# Failure reasons of ScreenCheck (they appear in the chain events) and the screen message for each.
SCREEN_REASONS = {"screen paused": "paused", "no screen markers": "no_screen", "screen code unreadable": "no_screen"}


def load_booth_meta(cfg: dict) -> dict | None:
    """booth-prep metadata for the configured replay clip, if any."""
    clip = cfg.get("booth", {}).get("replay_clip")
    if not clip:
        return None
    clip = Path(clip)
    if not clip.is_absolute():
        clip = PROJECT_ROOT / clip
    for meta_path in (clip.with_name(clip.name.split("_hold")[0] + "_booth.json"), clip.parent / f"{clip.stem}_booth.json"):
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta["_dir"] = str(meta_path.parent)
            meta["_clip"] = str(clip)
            return meta
    return None


def _layout(meta: dict):
    from wfglink.screen.codes import Layout

    return Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})


def make_booth_context(meta: dict, cfg: dict) -> BoothContext:
    from wfglink.screen.booth_prep import load_sidecar
    from wfglink.screen.rectify import ScreenRectifier

    rect = ScreenRectifier(_layout(meta), int(cfg["live"]["analysis_max_width"]))
    times = load_sidecar(Path(meta["_dir"]) / meta["sidecar"])
    return BoothContext(rect, times)


class ScreenCheck:
    """Health hook for one attempt of a live camera in booth mode: is the iPad screen in view,
    and does its frame code advance?

    Runs in the capture thread and reads only the corner codes (its own rectifier, with a tiny
    analysis warp), at most every capture.booth_check_s seconds; other frames return None.
    A check passes (True) when the screen index changed since the previous check, and
    otherwise returns why not: "screen paused" (the same index again), "no screen markers"
    or "screen code unreadable". The capture worker makes the camera unhealthy when no check
    has passed for capture.freeze_s.
    """

    def __init__(self, meta: dict, cfg: dict):
        from wfglink.screen.rectify import ScreenRectifier

        self.rect = ScreenRectifier(_layout(meta), analysis_max_width=64)
        self.every_s = float((cfg.get("capture") or {}).get("booth_check_s", 0.2))
        self._t = -math.inf
        self._index: int | None = None

    def __call__(self, frame: Frame) -> bool | str | None:
        now = frame_wall_time(frame)
        if now - self._t < self.every_s:
            return None
        self._t = now
        r = self.rect.process(frame.image)
        idx = screen_index(r.code)
        if idx is None:
            return "no screen markers" if r.markers_found == 0 else "screen code unreadable"
        prev, self._index = self._index, idx
        if prev is None:
            return None                      # the first reading says nothing about playback
        return True if idx != prev else "screen paused"


def screen_check_factory(meta: dict | None, cfg: dict):
    """SourceChain hook_factory for booth mode: a fresh ScreenCheck for every attempt of a live
    option; replay, synthetic and file options stay unchecked. None without booth metadata."""
    if meta is None:
        return None

    def make(option: SourceOption) -> ScreenCheck | None:
        return ScreenCheck(meta, cfg) if option.live else None

    return make


def screen_note(chain: SourceChain | None, active_key: str | None) -> str:
    """'paused' or 'no_screen' when the last failure of a live option ranked above the active
    source was its screen check, so the fallback picture can say why the camera is out of use;
    '' otherwise (also when the best camera is active)."""
    if chain is None:
        return ""
    keys = [o.key for o in chain.options]
    if active_key not in keys:
        return ""
    better = {o.key for o in chain.options[:keys.index(active_key)] if o.live}
    if not better:
        return ""
    for e in reversed(chain.events[-100:]):
        if e.get("event") == "failed" and e.get("key") in better:
            return SCREEN_REASONS.get(e.get("reason", ""), "")
    return ""


def source_fields(pipe: Pipeline, status: ChainStatus, frame: Frame, chain: SourceChain | None) -> dict[str, Any]:
    """The source fields of a LiveState (label, state, unprepared, note), the same in both worker modes.

    A live camera with booth codes shows its pipeline's booth status: "paused" while its
    frames still arrive but the code has not advanced for capture.freeze_s, "no_screen"
    while no code could be read for that long.
    """
    state = "synthetic" if status.key == "synthetic" else status.state
    if status.live:
        scr = pipe.screen_status(frame_wall_time(frame))
        if scr in ("paused", "no_screen"):
            state = scr
    return {"source_label": status.label or status.key or "", "source_state": state,
            "unprepared": pipe.booth is None and status.key not in ("synthetic", "file"),
            "source_note": screen_note(chain, status.key)}


def last_events(events: list[dict], n: int) -> list[dict]:
    """The last n events (none for n <= 0)."""
    return list(events[-n:]) if n > 0 else []


def build_options(cfg: dict, source: str = "auto") -> list[SourceOption]:
    """Source options in priority order. source: auto (config chain), synthetic, file:PATH, camera,
    loopsim:PATH, loopsim-unplug:PATH or loopsim-pause:PATH.

    loopsim:PATH films a prepared booth clip through the camera-in-the-loop simulator
    (wfglink.screen.loopsim, settings in sitting2.loopsim); loopsim-unplug:PATH adds a
    disconnect during sitting2.dry_unplug_s seconds, and loopsim-pause:PATH pauses the
    simulated iPad during booth.sim_pause_s seconds; as a source, both are followed by
    labelled replay of the same clip, so dry runs exercise the real fallback chain. All
    three may also be entries of camera.chain, because the booth codes (and the screen
    check) are loaded only for the auto and camera sources.
    """
    if source == "synthetic":
        return [SourceOption("synthetic", lambda: SyntheticLiveSource(seed=1), False, "Synthetic")]
    if source.startswith("file:"):
        path = source[5:]
        return [SourceOption("file", lambda: FileSource(path, loop=True, realtime=True), False, Path(path).name)]

    def loopsim_options(spec: str, with_replay: bool) -> list[SourceOption]:
        from wfglink.io.fake import FaultScript
        from wfglink.screen.loopsim import LoopSimSource

        kind, path = spec.split(":", 1)
        s2 = cfg.get("sitting2", {}) or {}
        params = dict(s2.get("loopsim", {}) or {})
        faults = None
        if kind == "loopsim-unplug":
            t0, t1 = (float(v) for v in s2.get("dry_unplug_s", [15, 35]))
            faults = FaultScript([("disconnect", t0, t1)])
        elif kind == "loopsim-pause":
            t0, t1 = (float(v) for v in (cfg.get("booth", {}) or {}).get("sim_pause_s", [15, 35]))
            faults = FaultScript([("pause", t0, t1)])
        epoch = time.monotonic()   # one clock for every attempt: the iPad keeps playing while unplugged
        opts = [SourceOption("loopsim", lambda: LoopSimSource(path, faults=faults, epoch=epoch, realtime=True,
                                                              label="loopsim", **params),
                             True, f"Loop simulator ({Path(path).name})")]
        if with_replay and kind in ("loopsim-unplug", "loopsim-pause"):
            opts.append(SourceOption("replay", lambda: FileSource(path, loop=True, realtime=True), False, Path(path).name))
        return opts

    loopsim_kinds = ("loopsim:", "loopsim-unplug:", "loopsim-pause:")
    if source.startswith(loopsim_kinds):
        return loopsim_options(source, True) + [
            SourceOption("synthetic", lambda: SyntheticLiveSource(seed=1), False, "Synthetic")]
    options: list[SourceOption] = []
    devs = list_cameras().get("devices", [])
    spec = CameraSpec("", int(cfg["camera"]["width"]), int(cfg["camera"]["height"]), float(cfg["camera"]["fps"]))
    for key in cfg["camera"].get("chain", ["iphone", "webcam", "replay"]):
        if key in ("iphone", "webcam"):
            d = pick_camera(devs, key, cfg["camera"].get("iphone_uid") if key == "iphone" else None,
                            cfg["camera"].get("webcam_match") if key == "webcam" else None)
            if d:
                options.append(SourceOption(key, lambda d=d: AutoCameraSource(d, spec, camera_backends(cfg)), True, d["name"]))
        elif key == "replay":
            meta = load_booth_meta(cfg)
            if meta:
                clip = meta["_clip"]
                options.append(SourceOption("replay", lambda clip=clip: FileSource(clip, loop=True, realtime=True), False,
                                            Path(clip).name))
        elif key.startswith(loopsim_kinds):
            options.extend(loopsim_options(key, False))
    if source != "camera":
        options.append(SourceOption("synthetic", lambda: SyntheticLiveSource(seed=1), False, "Synthetic"))
    return options


class BoothWorker(QThread):
    state_ready = Signal(object)

    def __init__(self, chain: SourceChain, cfg: dict, booth_meta: dict | None):
        super().__init__()
        self.chain = chain
        self.cfg = cfg
        self.booth_meta = booth_meta
        self._running = True
        self._pipes: dict[str, Pipeline] = {}
        self._active_key: str | None = None
        self._last = None
        self.errors: list[str] = []
        self.frames = 0
        self._times: list[float] = []

    def stop(self) -> None:
        self._running = False

    def _pipeline_for(self, key: str) -> Pipeline:
        if key not in self._pipes:
            booth = None
            if self.booth_meta is not None and key != "synthetic":
                booth = make_booth_context(self.booth_meta, self.cfg)
            self._pipes[key] = Pipeline(self.cfg, booth=booth, downscale=True)
        return self._pipes[key]

    def run(self) -> None:
        import gc

        gc.freeze()  # long-lived objects out of the collector: avoids 50 ms pauses
        while self._running:
            frame, status = self.chain.latest()
            key = (status.key, frame.index) if frame is not None else None
            if frame is None or key == self._last:
                self.msleep(3)
                continue
            self._last = key
            try:
                if status.key != self._active_key:
                    if self._active_key is not None:
                        self._pipes.pop(status.key, None)   # counts restart on a source switch
                    self._active_key = status.key
                pipe = self._pipeline_for(status.key)
                state = pipe.process(frame)
            except Exception as exc:  # keep the booth alive; record and continue
                self.errors.append(f"{type(exc).__name__}: {exc}")
                self.msleep(10)
                continue
            now = time.monotonic()
            self._times.append(now)
            self._times = self._times[-60:]
            fps = (len(self._times) - 1) / (self._times[-1] - self._times[0]) if len(self._times) > 2 else 0.0
            s = LiveState(**state.__dict__)  # shallow copy, owned by the GUI from now on
            if s.image is not None:
                s.image = np.ascontiguousarray(s.image)
            for k, v in source_fields(pipe, status, frame, self.chain).items():
                setattr(s, k, v)
            s.fps = fps
            if pipe.booth is not None and pipe.stats.frames_analysed > 30 and len(self._times) > 2:
                s.playback_speed = self._playback_speed(pipe)
            self.frames += 1
            self.state_ready.emit(s)

    def _playback_speed(self, pipe: Pipeline) -> float | None:
        meta = self.booth_meta or {}
        outs = meta.get("outputs", {})
        hold = str(self.cfg["booth"].get("hold_factor", 2))
        return outs.get(hold, {}).get("playback_speed")

    def report(self, n_events: int) -> dict[str, Any]:
        """Source at the end, the last n_events chain events and each pipeline's stats (call after wait)."""
        return {"source": self.chain.status.key, "source_events": last_events(self.chain.events, n_events),
                "pipelines": {k: p.stats.as_dict() for k, p in self._pipes.items()}}

    def pipeline_counters(self) -> dict[str, Any] | None:
        """The active pipeline's frame counters (they restart on a source switch)."""
        key = self._active_key
        pipe = self._pipes.get(key) if key is not None else None
        return heartbeat_counters(key, pipe.stats if pipe is not None else None)


class BoothWindow(QWidget):
    def __init__(self, lang: str = "ko"):
        super().__init__()
        self.setWindowTitle("wfglink")
        self.setStyleSheet("background-color: #000000;")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.lang = lang
        self.state = LiveState()
        self.show_limits = False
        self.show_tracks = True
        self.show_field = True
        self.show_gate = True
        self._esc_at = 0.0
        self.paints = 0
        self.quit_confirmed = False
        self.states_seen: dict[str, int] = {}   # states received, by source state (and note): for the report

    def on_state(self, s: LiveState) -> None:
        self.state = s
        key = f"{s.source_state}+{s.source_note}" if s.source_note else s.source_state
        self.states_seen[key] = self.states_seen.get(key, 0) + 1
        self.update()

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        k = ev.key()
        if k == Qt.Key.Key_L:
            self.lang = "en" if self.lang == "ko" else "ko"
        elif k == Qt.Key.Key_I:
            self.show_limits = not self.show_limits
        elif k == Qt.Key.Key_T:
            self.show_tracks = not self.show_tracks
        elif k == Qt.Key.Key_F:
            self.show_field = not self.show_field
        elif k == Qt.Key.Key_G:
            self.show_gate = not self.show_gate
        elif k == Qt.Key.Key_Escape:
            now = time.monotonic()
            if now - self._esc_at < 2.0:
                self.quit_confirmed = True
                self.close()
            self._esc_at = now
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        paint_scene(p, self.width(), self.height(), self.state, self.lang, show_limits=self.show_limits,
                    show_tracks=self.show_tracks, show_field=self.show_field, show_gate=self.show_gate)
        p.end()
        self.paints += 1


class LimitsWindow(QWidget):
    """The limits card alone, fullscreen on a second display."""

    def __init__(self, main: BoothWindow):
        super().__init__()
        self.main = main
        self.setStyleSheet("background-color: #000000;")

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        paint_scene(p, self.width(), self.height(), LiveState(), self.main.lang, show_limits=True,
                    show_tracks=False, show_field=False, show_gate=False)
        p.end()


def rss_mb(pid: int) -> float | None:
    """Resident memory of a process in MB (Linux /proc, otherwise ps), or None."""
    import os
    import subprocess

    statm = Path(f"/proc/{pid}/statm")
    try:
        if statm.exists():
            return int(statm.read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
        return int(out.stdout.strip()) / 1024 if out.stdout.strip() else None
    except Exception:
        return None


class Heartbeat:
    """A small JSON file rewritten every few seconds; the booth supervisor watches it."""

    def __init__(self, path: str | Path, every_s: float = 2.0):
        import os

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.every_s = every_s
        self.t0 = time.monotonic()
        self.pid = os.getpid()
        self._rss: dict[int, float | None] = {}
        self._rss_at = -1e9

    def write(self, win: "BoothWindow", worker, status: str = "running") -> None:
        from wfglink.provenance import now_shanghai

        now = time.monotonic()
        if now - self._rss_at > 10.0:     # ps is not free; memory moves slowly
            pids = [self.pid] + ([worker.proc.pid] if getattr(worker, "proc", None) is not None and worker.proc.pid else [])
            self._rss = {pid: rss_mb(pid) for pid in pids}
            self._rss_at = now
        st = win.state
        data = {"status": status, "time": now_shanghai(), "epoch": time.time(), "pid": self.pid,
                "uptime_s": round(now - self.t0, 1), "frames": worker.frames, "paints": win.paints,
                "fps": round(st.fps or 0.0, 2), "source": st.source_label, "state": st.source_state,
                "errors": len(worker.errors), "last_error": worker.errors[-1] if worker.errors else None,
                "rss_mb": {str(k): (round(v, 1) if v is not None else None) for k, v in self._rss.items()}}
        counters = getattr(worker, "pipeline_counters", None)
        if counters is not None:
            # Frames received and analysed by the active pipeline, so the soak can tell an
            # app that keeps painting from one that keeps analysing.
            data["pipeline"] = counters()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(self.path)


def run_booth(cfg: dict | None = None, source: str = "auto", screen: str | None = None, lang: str | None = None,
              limits_screen: str | None = None, duration_s: float | None = None,
              screenshot: str | None = None, heartbeat: str | None = None) -> dict[str, Any]:
    cfg = cfg or load_config(local=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from wfglink.ui.fonts import load_fonts

    load_fonts()
    options = build_options(cfg, source)
    meta = load_booth_meta(cfg) if source in ("auto", "camera") else None
    chain = SourceChain(options, ChainConfig.from_config(cfg), hook_factory=screen_check_factory(meta, cfg))
    n_events = int((cfg.get("booth") or {}).get("report_events", 100))
    win = BoothWindow(lang or cfg["ui"]["language"])
    scr = choose_screen(app, screen or cfg["ui"]["screen"])
    win.setScreen(scr)
    win.setGeometry(scr.geometry())
    win.showFullScreen()
    limits = None
    if limits_screen:
        lscr = choose_screen(app, limits_screen)
        if lscr is not scr:
            limits = LimitsWindow(win)
            limits.setScreen(lscr)
            limits.setGeometry(lscr.geometry())
            limits.showFullScreen()
    mode = cfg.get("live", {}).get("worker_mode", "thread")
    if mode == "process":
        from wfglink.ui.process_worker import ProcessBoothWorker

        worker = ProcessBoothWorker(cfg, source, meta)
        chain = None  # capture runs in the child process
    else:
        worker = BoothWorker(chain, cfg, meta)
        chain.start()
    worker.state_ready.connect(win.on_state, Qt.ConnectionType.QueuedConnection)
    worker.start()
    if duration_s:
        def finish():
            win.duration_done = True
            if screenshot:
                Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
                win.grab().save(screenshot)
            win.close()
        QTimer.singleShot(int(duration_s * 1000), finish)
    hb = Heartbeat(heartbeat) if heartbeat else None
    t0 = time.monotonic()
    t_hb = 0.0
    try:
        while win.isVisible():
            app.processEvents()
            time.sleep(0.002)
            now = time.monotonic()
            if hb is not None and now - t_hb >= hb.every_s:
                t_hb = now
                hb.write(win, worker)
            if duration_s and now - t0 > duration_s + 5:
                break
    finally:
        worker.stop()
        worker.wait(5000)
        if chain is not None:
            chain.stop()
        if limits:
            limits.close()
        if hb is not None:
            done = win.quit_confirmed or getattr(win, "duration_done", False)
            hb.write(win, worker, "clean_exit" if done else "closed")
    st = win.state
    rep = worker.report(n_events)    # in process mode, the child's last periodic report
    result = {
        "seconds": round(time.monotonic() - t0, 1), "frames": worker.frames, "paints": win.paints,
        "errors": worker.errors[-10:], "worker_mode": mode,
        "source": rep.get("source") or st.source_label,
        "source_events": rep.get("source_events", []),
        "quit_confirmed": win.quit_confirmed,
        "last": {"count_rate": st.count_rate, "cpc": st.cpc_gross, "pnf": st.pnf, "speed": st.speed,
                 "fps": st.fps, "state": st.source_state},
        "pipelines": rep.get("pipelines", {}),
        "source_states": dict(win.states_seen),
    }
    win.deleteLater()
    app.processEvents()
    return result
