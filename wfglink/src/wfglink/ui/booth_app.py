"""The booth screen: approved clips analysed live as they play (python -m wfglink live), and
"Become an ember", the live camera tracking visitors' phones (key M).

    python -m wfglink live                      # the playlist (booth/playlist.yaml), in a loop
    python -m wfglink live --synthetic          # generated video (ember mode: a generated phone scene)
    python -m wfglink live --clip data/clips/C6_nist_dragon.yaml
    python -m wfglink live --ember              # start in ember mode (the camera)
    python -m wfglink live --fake-camera FILE   # ember mode plays FILE as if it were the camera
    bash booth/booth.sh                         # the playlist under the supervisor, for a whole day

Fire mode (the start): playback (wfglink.io.playlist.Player) decodes the clips in real time
and keeps only the newest frame; the analysis takes the newest frame whenever it is free, so
frames are skipped rather than queued and the picture never lags.

Ember mode (key M, or live --ember): the camera (wfglink.io.camera.CameraSource, chosen by
camera.name) is read in its own thread that keeps only the newest frame (CameraFeed), and
wfglink.ember.pipeline.EmberPipeline (live.ember_pipeline) tracks the phones showing the
ember page. Playback holds while ember mode runs, and the camera is opened only in ember
mode and closed when M returns to fire mode. Camera permission (macOS) is asked on the main
thread only: at start-up, before any window or worker exists (waiting up to
live.camera_permission_timeout_s for the answer), and again at an M press while it is still
undecided; that second request returns at once and a timer polls the answer, so the screen
never stops while the dialog is open (CameraPermission). Without a usable camera, ember mode shows a calm
message in both languages (missing, denied, asking, error) and M still returns to fire mode;
a camera that comes back is picked up by itself. live --synthetic plays a generated phone
scene in ember mode (ui/phone_scene.py) and --fake-camera FILE plays a recording.

live.worker_mode chooses where playback, the camera and the analysis run: in this process
(thread) or in a child process (process, ui/process_worker.py). Both use BoothEngine, so
the screen is the same; the child opens the camera only after the parent has the permission.

Counts: with booth.reset_per_clip true (the default) every clip start resets the pipeline,
so the counts are per clip; with false each clip keeps one pipeline whose counts run on
across loops. A cut inside a clip (its next segment) restarts only the background model
and the tracks. Each entry into ember mode starts a fresh ember pipeline.

Screen (--screen, ui.screen): auto puts the window fullscreen on the external monitor when
one is connected, else on the built-in screen, and moves it when a monitor is plugged in or
out (screenAdded, screenRemoved); external means the same; primary is the main screen; any
other value is a screen name (auto while that screen is absent). Built-in screens are
recognised by name (ui.builtin_screen). --limits-screen puts the limits card on a second
screen while that screen is not the booth's.

Keys: L language, T tracks (in ember mode also the numbers and speeds on the picture), F
field, G gate, Space pause (playback and analysis hold; a small tag shows), I limits card, A
raw or analysed fire footage (the clip alone, or the full overlay with trails, wind arrows,
gate and counters; a fade of ui.raw_fade_s seconds; the booth starts analysed and the
analysis keeps running underneath, so the numbers are current when they come back; A acts on
the fire footage only: ember mode always shows its analysed screen, and the fire footage's
choice is kept for when M returns to it), M fire or ember mode (the booth starts in fire
mode; a switch also ends a pause), Esc then Esc again within ui.quit_confirm_s seconds quits
(a prompt shows after the first). SIGTERM or SIGINT closes the window too (not a clean exit).

Fire mode draws the points and trails of confirmed tracks only (ui.show_unconfirmed false, the
default): a faint detection that never became a track (compression flicker on a steel frame,
a lab light) is analysed but not drawn. The counts and the analysis are the same either way.

Ember mode shows the ember page's address (booth.ember_page_url) small with a QR code of it in
the bottom-right corner, when the key is set.

Heartbeat (--heartbeat FILE, booth.sh passes logs/heartbeat.json), rewritten every 2 s:
status (running, clean_exit, closed), time, epoch, pid, uptime_s, frames (states analysed,
both modes), paints, fps (analysis), source (playlist, clip or synthetic), state (starting,
playing, synthetic, camera), errors (count), last_error, rss_mb {pid: MB}, clip (the
playlist item playing, or "synthetic"), paused, pipeline {key, frames_in, frames_analysed,
frames_duplicate} (key "ember" in ember mode), mode (fire or ember), raw (the fire footage's
raw picture is chosen) and camera_state (off in fire mode; starting, ok, missing, denied,
asking or error). In ember mode state is starting until the first camera frame, then camera
(synthetic for a generated scene, playing for a recording), and clip is null.
booth.sh does not count a stop of new frames as a hang while ember mode waits for its camera.
"""
from __future__ import annotations

import dataclasses
import importlib
import itertools
import json
import math
import re
import signal
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget

from wfglink.config import load_config
from wfglink.io.frames import Frame
from wfglink.io.playlist import PlaybackConfig, Player, PlaylistError, clip_item, load_playlist
from wfglink.pipeline import Pipeline, heartbeat_counters
from wfglink.render.scene import LiveState, paint_scene

MODES = ("fire", "ember")
DEFAULT_EMBER_PIPELINE = "wfglink.ember.pipeline:EmberPipeline"

# Names of a laptop's own panel: macOS says "Built-in Retina Display" (Korean "내장 Retina
# 디스플레이", older Macs "Color LCD"); Linux says eDP-1, LVDS-1 or DSI-1. ui.builtin_screen overrides.
BUILTIN_SCREEN = r"built-?in|내장|color lcd|^edp|^lvds|^dsi"


# Sources -------------------------------------------------------------------------------------

def source_spec(synthetic: bool = False, playlist: str | None = None, clip: str | None = None,
                cfg: dict | None = None) -> dict[str, str]:
    """What to play: {"kind": "synthetic"}, {"kind": "clip", "path": ...} or {"kind": "playlist", "path": ...}
    (booth.playlist by default)."""
    if synthetic:
        return {"kind": "synthetic"}
    if clip:
        return {"kind": "clip", "path": str(clip)}
    return {"kind": "playlist", "path": str(playlist or ((cfg or {}).get("booth") or {}).get("playlist")
                                            or "booth/playlist.yaml")}


def _log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [live] {msg}", file=sys.stderr, flush=True)


def make_player(cfg: dict, spec: dict[str, str]) -> Player:
    """The Player for a source spec. A playlist that cannot be read plays synthetic video
    (with a log line), so the booth never shows a black screen."""
    from wfglink.io.synthetic_live import SyntheticLiveSource

    items = []
    kind = spec.get("kind", "playlist")
    note = ""
    if kind == "clip":
        items = [clip_item(spec["path"])]
    elif kind == "playlist":
        try:
            items = load_playlist(spec["path"])
        except PlaylistError as exc:
            note = str(exc)
            _log(f"{exc}; playing synthetic video")
    seed = int((cfg.get("booth") or {}).get("synthetic_seed", 1))
    player = Player(items, PlaybackConfig.from_config(cfg), synthetic=lambda: SyntheticLiveSource(seed=seed, realtime=False))
    if note:
        player._event("playlist_error", reason=note)
    return player


def ember_spec(synthetic: bool = False, fake_camera: str | None = None) -> dict[str, str]:
    """What ember mode reads: {"kind": "camera"} (the configured camera), {"kind": "file", "path": ...}
    (a recording played as if it were the camera) or {"kind": "synthetic"} (a generated phone scene)."""
    if fake_camera:
        return {"kind": "file", "path": str(fake_camera)}
    return {"kind": "synthetic"} if synthetic else {"kind": "camera"}


def make_ember_source(cfg: dict, spec: dict[str, str]):
    """A fresh Source for ember mode (built in the thread that reads it, on every attempt)."""
    kind = spec.get("kind", "camera")
    if kind == "synthetic":
        from wfglink.ui.phone_scene import phone_scene_source

        return phone_scene_source(cfg, realtime=True)
    if kind == "file":
        try:
            from wfglink.io.camera import FakeCameraSource
        except ImportError:      # a tree without wfglink.io.camera: the file plays like a camera all the same
            from wfglink.io.sources import FileSource

            return FileSource(spec["path"], loop=True, realtime=True)
        return FakeCameraSource(spec["path"], realtime=True)
    from wfglink.io.camera import CameraSource

    return CameraSource(cfg)


def ember_source_state(spec: dict[str, str]) -> str:
    """What ember mode's picture is, for the screen: camera, playing (a recording) or synthetic."""
    return {"file": "playing", "synthetic": "synthetic"}.get(spec.get("kind", "camera"), "camera")


def ember_pipeline_class(cfg: dict):
    """The class behind ember mode's analysis: live.ember_pipeline as module:Class."""
    path = str((cfg.get("live") or {}).get("ember_pipeline") or DEFAULT_EMBER_PIPELINE)
    module, _, name = path.partition(":")
    return getattr(importlib.import_module(module), name or "EmberPipeline")


def _own_state(st: Any) -> LiveState:
    """A shallow copy as a LiveState with only its declared fields (owned by the screen from now on)."""
    names = {f.name for f in dataclasses.fields(LiveState)}
    s = LiveState(**{k: v for k, v in vars(st).items() if k in names})
    if s.image is not None:
        s.image = np.ascontiguousarray(s.image)
    return s


class LiveAnalyser:
    """Turns playback frames into LiveStates; the same code in both worker modes.

    One pipeline per clip, created with the clip's gate (if its settings file gives one);
    booth.reset_per_clip decides whether a clip start replaces it (see the module docstring).
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.reset_per_clip = bool((cfg.get("booth") or {}).get("reset_per_clip", True))
        self.show_unconfirmed = bool((cfg.get("ui") or {}).get("show_unconfirmed", False))
        self.pipes: dict[str, Pipeline] = {}
        self.active: str | None = None
        self._item: Any = None
        self._segment: Any = None
        self._times: deque = deque(maxlen=60)

    def process(self, frame: Frame) -> LiveState:
        m = frame.meta
        key = str(m.get("clip") or "clip")
        if m.get("item") != self._item or key not in self.pipes:
            self._item, self._segment = m.get("item"), m.get("segment")
            if self.reset_per_clip or key not in self.pipes:
                g = m.get("gate")
                gate = {"p1": list(g[:2]), "p2": list(g[2:]), "name": "gate"} if g else None
                self.pipes[key] = Pipeline(self.cfg, gate=gate, downscale=True)
            else:
                self.pipes[key].cut()
            self.active = key
        elif m.get("segment") != self._segment:
            self._segment = m.get("segment")
            self.pipes[key].cut()
        st = self.pipes[key].process(frame)
        now = time.monotonic()
        self._times.append(now)
        span = self._times[-1] - self._times[0]
        s = _own_state(st)
        if not self.show_unconfirmed:
            s.detections = confirmed_points(self.pipes[key], s.t)
        s.source_label = str(m.get("label") or "")
        s.source_credit = str(m.get("credit") or "")
        s.source_state = "synthetic" if m.get("synthetic") else "playing"
        s.fps = (len(self._times) - 1) / span if len(self._times) > 2 and span > 0 else 0.0
        return s

    def resume(self) -> None:
        """Fire mode comes back after ember mode: the analysis rate starts afresh (the window
        would otherwise span the time in ember mode)."""
        self._times.clear()

    def stats(self) -> dict[str, dict]:
        """Each clip's pipeline stats (the latest pipeline of each clip)."""
        return {k: p.stats.as_dict() for k, p in self.pipes.items()}

    def counters(self) -> dict[str, Any] | None:
        """The active pipeline's frame counters for the heartbeat."""
        pipe = self.pipes.get(self.active) if self.active is not None else None
        return heartbeat_counters(self.active, pipe.stats if pipe is not None else None)


def confirmed_points(pipe: Pipeline, t: float) -> np.ndarray:
    """Where the confirmed, moving tracks were measured in the frame at time t (n, 2): what fire
    mode draws as glowing points (ui.show_unconfirmed false). A detection that is no confirmed
    track's (a faint flicker that never became a track, a static light) is not drawn."""
    pts = []
    for tr in pipe.tracker.active_tracks():
        if tr.static or not tr.records:
            continue
        r = tr.records[-1]
        if r[1] != t or r[14] or not math.isfinite(r[2]):
            continue
        pts.append((r[2], r[3]))
    return np.array(pts, dtype=float) if pts else np.zeros((0, 2))


# Ember mode ------------------------------------------------------------------------------------

class EmberNumbers:
    """Small, steady numbers for the embers on screen: a new ember takes the lowest free number
    (1, 2, ...), keeps it while it is tracked and frees it when it goes, so a visitor whose
    phone is found again usually gets the same number back."""

    def __init__(self):
        self.by_id: dict[int, int] = {}

    def assign(self, embers: list[dict]) -> list[dict]:
        ids = {int(e["id"]) for e in embers}
        for i in [i for i in self.by_id if i not in ids]:
            del self.by_id[i]
        used = set(self.by_id.values())
        out = []
        for e in sorted(embers, key=lambda e: -float(e.get("age_s") or 0.0)):     # the longest tracked first
            i = int(e["id"])
            if i not in self.by_id:
                self.by_id[i] = next(k for k in itertools.count(1) if k not in used)
                used.add(self.by_id[i])
            out.append({**e, "n": self.by_id[i]})
        return sorted(out, key=lambda e: e["n"])


class EmberAnalyser:
    """Turns camera frames into ember mode LiveStates; the same code in both worker modes.

    Wraps the ember pipeline (live.ember_pipeline, core's EmberPipeline) and adds what the
    screen needs: the numbers shown (EmberNumbers), the camera's name, what the picture is,
    the analysis rate and a 60 s sparkline of the embers on screen (most per second)."""

    def __init__(self, cfg: dict, source_state: str = "camera", pipeline_class: Any = None):
        self.cfg = cfg
        self.pipe = (pipeline_class or ember_pipeline_class(cfg))(cfg)
        self.source_state = source_state
        self.numbers = EmberNumbers()
        self._times: deque = deque(maxlen=60)
        self._spark: deque = deque()                 # (second, most embers seen in it)
        self.frames_in = 0
        self.frames_analysed = 0

    def process(self, frame: Frame) -> LiveState:
        self.frames_in += 1
        s = _own_state(self.pipe.process(frame))
        self.frames_analysed += 1
        m = frame.meta or {}
        s.mode = "ember"
        s.embers = self.numbers.assign([e for e in (s.embers or []) if isinstance(e, dict) and "id" in e])
        if s.ember_count is None:
            s.ember_count = len(s.embers)
        # A generated scene says so in the status line ("generated phone scene"), not by its
        # developer name ("fake: booth"); a camera or a recording shows its name.
        s.source_label = "" if m.get("synthetic") else str(m.get("camera") or m.get("source") or "")
        s.source_credit = ""
        s.source_state = "synthetic" if m.get("synthetic") else self.source_state
        s.camera_state = "ok"
        now = time.monotonic()
        self._times.append(now)
        span = self._times[-1] - self._times[0]
        s.fps = (len(self._times) - 1) / span if len(self._times) > 2 and span > 0 else 0.0
        s.sparkline = self._sparkline(float(frame.t), int(s.ember_count or 0))
        return s

    def _sparkline(self, t: float, count: int) -> np.ndarray:
        sec = math.floor(t)
        if self._spark and sec < self._spark[-1][0]:      # the clock went back (a recording restarted)
            self._spark.clear()
        if self._spark and self._spark[-1][0] == sec:
            self._spark[-1] = (sec, max(self._spark[-1][1], count))
        else:
            self._spark.append((sec, count))
        while self._spark and self._spark[0][0] < sec - 59:
            self._spark.popleft()
        # Seconds without a frame (a pause, a camera gap) stay empty rather than reading 0.
        spark = np.full(60, np.nan)
        for s_, n in self._spark:
            spark[s_ - (sec - 59)] = n
        return spark

    def counters(self) -> dict[str, Any]:
        return heartbeat_counters("ember", {"frames_in": self.frames_in, "frames_analysed": self.frames_analysed})

    def stats(self) -> dict[str, Any]:
        return {"frames_in": self.frames_in, "frames_analysed": self.frames_analysed}


class CameraFeed(threading.Thread):
    """Reads ember mode's camera (or a fake one) in its own thread and keeps only the newest frame.

    A source that fails to open or to read is closed and built again after live.camera_retry_s
    (doubling up to its second value), so a camera plugged in later is picked up by itself.
    state(): starting (no frame yet, for at most live.camera_start_s), ok (a frame within
    live.camera_lost_s), missing (otherwise)."""

    def __init__(self, make_source: Callable[[], Any], start_s: float = 10.0, lost_s: float = 2.0,
                 retry_s: tuple[float, float] = (0.5, 8.0), log: Callable[[str], None] | None = None):
        super().__init__(daemon=True, name="camera")
        self.make_source = make_source
        self.start_s, self.lost_s = float(start_s), float(lost_s)
        self.retry_s = (float(retry_s[0]), float(retry_s[1]))
        self.log = log or _log
        self._halt = threading.Event()
        self._lock = threading.Lock()
        self.frame: Frame | None = None
        self.seq = 0
        self.t_start = time.monotonic()
        self.t_frame: float | None = None
        self.failures = 0
        self.last_error = ""
        self.opens = 0

    @classmethod
    def from_config(cls, cfg: dict, make_source: Callable[[], Any]) -> "CameraFeed":
        lv = cfg.get("live") or {}
        retry = lv.get("camera_retry_s", [0.5, 8.0])
        return cls(make_source, float(lv.get("camera_start_s", 10.0)), float(lv.get("camera_lost_s", 2.0)),
                   (float(retry[0]), float(retry[1])))

    def latest(self) -> tuple[int, Frame | None]:
        with self._lock:
            return self.seq, self.frame

    def state(self, now: float | None = None) -> str:
        now = time.monotonic() if now is None else now
        if self.t_frame is not None and now - self.t_frame <= self.lost_s:
            return "ok"
        if self.t_frame is None and self.failures == 0 and now - self.t_start <= self.start_s:
            return "starting"
        return "missing"

    def stop(self, timeout_s: float = 3.0) -> None:
        self._halt.set()
        if timeout_s > 0 and self.is_alive() and self is not threading.current_thread():
            self.join(timeout_s)

    def run(self) -> None:
        delay = self.retry_s[0]
        while not self._halt.is_set():
            with _autorelease_pool():
                delay = self._attempt(delay)
        with self._lock:
            self.frame = None

    def _attempt(self, delay: float) -> float:
        """One open, read until it fails, close; returns the next wait (doubling up to retry_s[1])."""
        src = None
        try:
            src = self.make_source()
            src.open()
            self.opens += 1
            if getattr(src, "effects_on", None):
                self.log(f"camera: video effects on: {', '.join(src.effects_on)}; turn them off in the Video menu "
                         "(the green camera icon in the menu bar)")
            while not self._halt.is_set():
                f = src.read()
                if f is None:
                    if self.t_frame is not None and time.monotonic() - self.t_frame > self.lost_s:
                        raise RuntimeError("no frame from the camera")
                    self._halt.wait(0.01)
                    continue
                with self._lock:
                    self.frame, self.seq = f, self.seq + 1
                self.t_frame = time.monotonic()
                delay = self.retry_s[0]
        except Exception as exc:     # no camera, unplugged, or failing: try again later
            self.failures += 1
            msg = f"{type(exc).__name__}: {exc}"
            if msg != self.last_error:
                self.log(f"camera: {msg}; trying again")
            self.last_error = msg
        finally:
            if src is not None:
                try:
                    src.close()
                except Exception:
                    pass
        self._halt.wait(delay)
        return min(2 * delay, self.retry_s[1])


def _autorelease_pool():
    """macOS: an Objective-C autorelease pool around each camera attempt, so the AVFoundation and
    permission objects made in this thread are released (a thread without one leaks them);
    elsewhere nothing."""
    import contextlib

    if sys.platform != "darwin":
        return contextlib.nullcontext()
    try:
        import objc

        return objc.autorelease_pool()
    except Exception:
        return contextlib.nullcontext()


def _send_permission() -> str:
    """wfglink.io.camera.ask_permission (the request without waiting), or "unsupported"."""
    try:
        from wfglink.io.camera import ask_permission
    except ImportError:
        return "unsupported"
    try:
        return str(ask_permission())
    except Exception as exc:
        _log(f"camera permission request failed: {type(exc).__name__}: {exc}")
        return "unsupported"


def _read_permission() -> str:
    try:
        from wfglink.io.camera import permission_status
    except ImportError:
        return "unsupported"
    try:
        return str(permission_status())
    except Exception:
        return "unsupported"


def _request_permission(timeout_s: float) -> str:
    """wfglink.io.camera.request_permission, or "unsupported" when it cannot be used here."""
    try:
        from wfglink.io.camera import request_permission
    except ImportError:
        return "unsupported"
    try:
        return str(request_permission(timeout_s=timeout_s))
    except Exception as exc:
        _log(f"camera permission request failed: {type(exc).__name__}: {exc}")
        return "unsupported"


class CameraPermission:
    """Camera permission for ember mode, asked on the main thread only: macOS needs that before
    any capture thread starts. Not needed when ember mode plays a fake camera."""

    ALLOWED = ("authorized", "unsupported")      # unsupported: no permission system here, capture is tried directly

    def __init__(self, needed: bool = True, timeout_s: float = 20.0, request: Callable[[float], str] | None = None,
                 send: Callable[[], str] | None = None, read: Callable[[], str] | None = None):
        """request(timeout) asks and waits for the answer; send() asks without waiting and read()
        reads the status, for asking while the booth runs (both default to the real ones unless
        a request is given, as tests do: then every ask waits)."""
        self.needed = bool(needed)
        self.timeout_s = float(timeout_s)
        self.request = request or _request_permission
        self.send = send if send is not None else (None if request else _send_permission)
        self.read = read if read is not None else (None if request else _read_permission)
        self.status = "not_determined" if self.needed else "authorized"
        self.asks = 0

    def ask(self) -> str:
        """Ask (the system dialog shows only while undecided); returns the status. Main thread only."""
        if not self.needed or self.allowed:
            return self.status
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("camera permission must be asked on the main thread")
        self.asks += 1
        self.status = self.request(self.timeout_s)
        _log(f"camera permission: {self.status}")
        return self.status

    def ask_async(self) -> bool:
        """Ask without waiting (the booth's M press); True when the answer must be polled with
        refresh(). Without send and read it asks and waits like ask(). Main thread only."""
        if not self.needed or self.allowed:
            return False
        if self.send is None or self.read is None:
            self.ask()
            return False
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("camera permission must be asked on the main thread")
        self.asks += 1
        self.status = self.send()
        _log(f"camera permission asked: {self.status}")
        return self.status == "not_determined"

    def refresh(self) -> str:
        """The status now (polled while the dialog is open)."""
        if self.read is not None and self.needed and not self.allowed:
            self.status = self.read()
        return self.status

    @property
    def allowed(self) -> bool:
        return self.status in self.ALLOWED

    def camera_state(self) -> str | None:
        """The screen's camera state while the camera may not be opened (None when it may)."""
        if self.allowed:
            return None
        return "denied" if self.status in ("denied", "restricted") else "asking"


class BoothEngine:
    """Both modes' sources and analyses, driven from one thread (the analysis QThread, or the
    child process's main loop): fire mode plays the playlist into LiveAnalyser; ember mode reads
    the camera (CameraFeed) into EmberAnalyser. Playback holds while ember mode runs; the camera
    is opened when ember mode starts (and the permission allows it) and closed when it ends."""

    def __init__(self, cfg: dict, spec: dict[str, str], ember: dict[str, str] | None = None,
                 camera_allowed: Callable[[], bool] | None = None, pipeline_class: Any = None):
        self.cfg = cfg
        self.spec = spec
        self.ember_spec = ember or {"kind": "camera"}
        self.camera_allowed = camera_allowed or (lambda: True)
        self.pipeline_class = pipeline_class
        self.player = make_player(cfg, spec)
        self.analyser = LiveAnalyser(cfg)
        self.ember: EmberAnalyser | None = None
        self.feed: CameraFeed | None = None
        self.ember_error: str | None = None
        self._ember_last: dict[str, Any] | None = None
        self.mode = "fire"
        self.paused = False
        self.retired: list[CameraFeed] = []      # camera threads told to stop, joined at the end
        self.entries = 0               # times ember mode started
        self._last_fire: int | None = None
        self._last_seq = 0

    def start(self, mode: str = "fire") -> None:
        self.player.start()
        self.set_mode(mode)

    def set_paused(self, paused: bool) -> None:
        self.paused = bool(paused)
        self._hold_playback()

    def _hold_playback(self) -> None:
        if self.paused or self.mode != "fire":
            self.player.pause()
        else:
            self.player.resume()

    def set_mode(self, mode: str) -> None:
        mode = mode if mode in MODES else "fire"
        if mode == self.mode:
            return
        self._close_ember()
        self.mode = mode
        if mode == "ember":
            self.entries += 1
            self.ember_error = None
        else:
            self.analyser.resume()
        self._hold_playback()

    def _close_ember(self) -> None:
        if self.feed is not None:
            # A short wait only: a camera that is reading stops within it, while one still
            # opening must not freeze the fire picture. That one ends by itself once its open
            # returns; stop() joins them all at the end.
            self.feed.stop(timeout_s=0.3)
            self.retired = [f for f in self.retired if f.is_alive()] + [self.feed]
        if self.ember is not None:       # its numbers stay for the report and the last heartbeat
            self._ember_last = {"counters": self.ember.counters(), "stats": self.ember.stats()}
        self.feed = None
        self.ember = None
        self._last_seq = 0

    def _open_ember(self) -> None:
        """The ember analysis first (a missing module shows as an error, with no camera opened),
        then the camera, once the permission allows it."""
        if self.ember is None and self.ember_error is None:
            try:
                self.ember = EmberAnalyser(self.cfg, ember_source_state(self.ember_spec), self.pipeline_class)
            except Exception as exc:
                self.ember_error = f"{type(exc).__name__}: {exc}"
                _log(f"ember mode could not start: {self.ember_error}")
        if self.ember is not None and self.feed is None and self.camera_allowed():
            self.feed = CameraFeed.from_config(self.cfg, lambda: make_ember_source(self.cfg, self.ember_spec))
            self.feed.start()

    def step(self) -> LiveState | None:
        """Analyse the active source's newest frame, if it is new (None otherwise)."""
        if self.mode == "fire":
            f = self.player.latest()
            if f is None or f.index == self._last_fire:
                return None
            self._last_fire = f.index
            return self.analyser.process(f)
        self._open_ember()
        if self.feed is None or self.paused:
            return None
        seq, f = self.feed.latest()
        if f is None or seq == self._last_seq:
            return None
        self._last_seq = seq
        return self.ember.process(f)

    def camera_state(self) -> str:
        """off (fire mode, or ember mode before the camera may be opened), error, or the feed's state."""
        if self.mode != "ember":
            return "off"
        if self.ember_error:
            return "error"
        feed = self.feed
        return feed.state() if feed is not None else "off"

    def stop(self) -> None:
        self._close_ember()
        self.player.stop()
        for f in self.retired:
            f.stop(timeout_s=3.0)
        self.retired = [f for f in self.retired if f.is_alive()]

    @property
    def clip(self) -> str | None:
        return self.analyser.active

    def counters(self) -> dict[str, Any] | None:
        """The active analysis's frame counters (ember mode's last ones after it closed)."""
        if self.mode == "ember":
            return self.ember.counters() if self.ember is not None else (self._ember_last or {}).get("counters")
        return self.analyser.counters()

    def report(self, n_events: int) -> dict[str, Any]:
        """Playback events (the last n_events), counters and each clip's pipeline stats (plus ember mode's)."""
        pipes = self.analyser.stats()
        if self.ember is not None:
            pipes["ember"] = self.ember.stats()
        elif self._ember_last:
            pipes["ember"] = self._ember_last["stats"]
        return {"clip": self.analyser.active, "events": list(self.player.events[-n_events:]) if n_events > 0 else [],
                "playback": dict(self.player.stats), "pipelines": pipes, "mode": self.mode,
                "camera_state": self.camera_state(), "ember_entries": self.entries}


class LiveWorker(QThread):
    """Thread mode: playback and the camera in their own threads, analysis in this QThread (the
    newest frame only). Mode and pause requests from the GUI are applied in this thread."""

    state_ready = Signal(object)

    def __init__(self, cfg: dict, spec: dict[str, str], ember: dict[str, str] | None = None, mode: str = "fire",
                 camera_allowed: bool = True):
        super().__init__()
        self.cfg = cfg
        self._camera_allowed = bool(camera_allowed)
        self.engine = BoothEngine(cfg, spec, ember, camera_allowed=lambda: self._camera_allowed)
        self._want_mode = mode if mode in MODES else "fire"
        self._want_paused = False
        self._running = True
        self.frames = 0
        self.errors: list[str] = []
        self.error_count = 0

    @property
    def player(self) -> Player:
        return self.engine.player

    @property
    def analyser(self) -> LiveAnalyser:
        return self.engine.analyser

    def start(self) -> None:  # type: ignore[override]
        self.engine.start(self._want_mode)
        super().start()

    def stop(self) -> None:
        self._running = False

    def shutdown(self, ms: int = 5000) -> bool:
        """Stop analysis, playback and the camera and wait for them."""
        self.stop()
        done = self.wait(ms)
        self.engine.stop()
        return bool(done)

    def set_paused(self, paused: bool) -> None:
        self._want_paused = bool(paused)

    def set_mode(self, mode: str) -> None:
        self._want_mode = mode if mode in MODES else "fire"

    def set_camera_allowed(self, allowed: bool) -> None:
        self._camera_allowed = bool(allowed)

    @property
    def paused(self) -> bool:
        return self._want_paused

    @property
    def mode(self) -> str:
        return self.engine.mode

    @property
    def camera_state(self) -> str:
        return self.engine.camera_state() if self._want_mode == self.engine.mode else "off"

    @property
    def clip(self) -> str | None:
        return self.engine.clip

    def child_pids(self) -> list[int]:
        return []

    def run(self) -> None:
        import gc

        gc.freeze()  # long-lived objects out of the collector: avoids 50 ms pauses
        eng = self.engine
        while self._running:
            try:
                if eng.mode != self._want_mode:
                    eng.set_mode(self._want_mode)
                if eng.paused != self._want_paused:
                    eng.set_paused(self._want_paused)
                s = eng.step()
            except Exception as exc:  # keep the booth alive; record and continue
                self.error_count += 1
                self.errors = (self.errors + [f"{type(exc).__name__}: {exc}"])[-100:]
                self.msleep(10)
                continue
            if s is None:
                self.msleep(3)
                continue
            self.frames += 1
            self.state_ready.emit(s)

    def report(self, n_events: int) -> dict[str, Any]:
        """Playback events (the last n_events), counters and each clip's pipeline stats."""
        return self.engine.report(n_events)

    def pipeline_counters(self) -> dict[str, Any] | None:
        return self.engine.counters()


# Screens -------------------------------------------------------------------------------------

def choose_screen(screens: list, primary: Any, preference: str | None = "auto", builtin: str | None = BUILTIN_SCREEN):
    """The screen for a window (see the module docstring). Screens need only .name()."""
    screens = list(screens)
    if not screens:
        return primary
    has_primary = any(s is primary for s in screens)
    pref = (preference or "auto").strip()
    if pref not in ("auto", "external", "primary"):
        for s in screens:
            if s.name() == pref:
                return s
        pref = "auto"
    if pref == "primary":
        return primary if has_primary else screens[0]
    pat = re.compile(builtin, re.I) if builtin else None
    inside = [s for s in screens if pat is not None and pat.search(s.name() or "")]
    outside = [s for s in screens if not any(s is i for i in inside)]
    if outside and inside:
        return outside[0]
    if inside:
        return inside[0]
    others = [s for s in screens if s is not primary]    # the names say nothing: a second screen is external
    return others[0] if others else (primary if has_primary else screens[0])


def _fullscreen_on(w, scr) -> None:
    if w.isFullScreen():
        w.showNormal()
    w.setScreen(scr)
    w.setGeometry(scr.geometry())
    w.showFullScreen()


class ScreenPlacer:
    """Keeps the booth window fullscreen on its chosen screen, and the limits window on its
    own, also when a monitor is plugged in or out while the booth runs."""

    def __init__(self, app, win, preference: str | None, builtin: str | None = BUILTIN_SCREEN, limits=None,
                 limits_preference: str | None = None, defer: Callable[[int, Callable], None] | None = None):
        self.app, self.win, self.preference, self.builtin = app, win, preference, builtin
        self.limits, self.limits_preference = limits, limits_preference
        self.defer = defer or (lambda ms, fn: QTimer.singleShot(ms, fn))
        self.screen = None
        self.moves: list[dict[str, Any]] = []
        app.screenAdded.connect(self._changed)
        app.screenRemoved.connect(self._changed)
        self.place()

    def _changed(self, *_) -> None:
        self.defer(400, self.place)       # after the system has finished rearranging the screens

    def place(self) -> None:
        screens, primary = list(self.app.screens()), self.app.primaryScreen()
        scr = choose_screen(screens, primary, self.preference, self.builtin)
        if scr is not None and (scr is not self.screen or self.win.screen() is not scr):
            _fullscreen_on(self.win, scr)
            self.moves.append({"t": round(time.monotonic(), 3), "screen": scr.name()})
            self.screen = scr
        if self.limits is not None:
            lscr = choose_screen(screens, primary, self.limits_preference, self.builtin)
            if lscr is None or lscr is scr:
                self.limits.hide()
            elif not self.limits.isVisible() or self.limits.screen() is not lscr:
                _fullscreen_on(self.limits, lscr)


# Windows -------------------------------------------------------------------------------------

class BoothWindow(QWidget):
    """The booth screen. It keeps the newest state of each mode and shows the chosen mode's;
    in ember mode the camera state comes from the worker (set_camera_state) and the permission."""

    def __init__(self, lang: str = "ko", quit_confirm_s: float = 3.0, on_pause: Callable[[bool], None] | None = None,
                 *, mode: str = "fire", on_mode: Callable[[str], None] | None = None,
                 permission: CameraPermission | None = None, on_permission: Callable[[bool], None] | None = None,
                 raw_fade_s: float = 0.5, clock: Callable[[], float] = time.monotonic, page_url: str = ""):
        super().__init__()
        self.setWindowTitle("wfglink")
        self.setStyleSheet("background-color: #000000;")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.lang = lang
        self.mode = mode if mode in MODES else "fire"
        self.states: dict[str, LiveState] = {"fire": LiveState(), "ember": _ember_start()}
        self.page_url = str(page_url or "").strip()
        self.show_limits = False
        self.show_tracks = True
        self.show_field = True
        self.show_gate = True
        self.paused = False
        self.on_pause = on_pause
        self.on_mode = on_mode
        self.permission = permission
        self.on_permission = on_permission
        self.worker_camera_state = "off"
        self.quit_confirm_s = float(quit_confirm_s)
        self.clock = clock
        self._esc_at = -1e9
        # Raw or analysed (key A): the analysed level fades from _fade[0] to _fade[1] from time _fade[2].
        self.raw = False
        self.raw_fade_s = max(0.0, float(raw_fade_s))
        self._fade = (1.0, 1.0, -1e9)
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(15)
        self._fade_timer.timeout.connect(self._fade_tick)
        # An M press while the permission is undecided asks without waiting; this polls the answer.
        self._perm_timer = QTimer(self)
        self._perm_timer.setInterval(500)
        self._perm_timer.timeout.connect(self._poll_permission)
        self._perm_until = 0.0
        self.paints = 0
        self.pauses = 0
        self.raw_toggles = 0
        self.mode_switches = 0
        self.quit_confirmed = False
        self.states_seen: dict[str, int] = {}   # states received, by source state: for the report
        self.clips_seen: dict[str, int] = {}    # ... and by clip name
        self.modes_seen: dict[str, int] = {}    # ... and by mode
        self.ember_seen = {"states": 0, "max_count": 0, "speeds": 0, "numbers": set(), "counts": {}}

    @property
    def state(self) -> LiveState:
        """The shown mode's newest state."""
        return self.states[self.mode]

    def on_state(self, s: LiveState) -> None:
        mode = s.mode if s.mode in MODES else "fire"
        self.states[mode] = s
        self.states_seen[s.source_state] = self.states_seen.get(s.source_state, 0) + 1
        self.modes_seen[mode] = self.modes_seen.get(mode, 0) + 1
        if s.source_label and mode == "fire":
            self.clips_seen[s.source_label] = self.clips_seen.get(s.source_label, 0) + 1
        if mode == "ember":
            e = self.ember_seen
            e["states"] += 1
            e["max_count"] = max(e["max_count"], int(s.ember_count or 0))
            e["counts"][int(s.ember_count or 0)] = e["counts"].get(int(s.ember_count or 0), 0) + 1
            for em in s.embers or []:
                v = em.get("speed_m_s")
                if v is not None and math.isfinite(float(v)):
                    e["speeds"] += 1
                e["numbers"].add(int(em.get("n", em.get("id", 0))))
        if mode == self.mode:
            self.update()

    # Ember mode ------------------------------------------------------------------------------
    def set_camera_state(self, state: str) -> None:
        """The worker's camera state (off, starting, ok, missing, error); repaints when the shown one changes."""
        if state != self.worker_camera_state:
            before = self.camera_state_shown()
            self.worker_camera_state = state
            if self.mode == "ember" and self.camera_state_shown() != before:
                self.update()

    def camera_state_shown(self) -> str:
        """off in fire mode; in ember mode the permission's state while the camera may not be
        opened, else the worker's (starting until the worker has the camera)."""
        if self.mode != "ember":
            return "off"
        if self.worker_camera_state == "error":
            return "error"
        held = self.permission.camera_state() if self.permission is not None else None
        if held:
            return held
        return "starting" if self.worker_camera_state == "off" else self.worker_camera_state

    def set_mode(self, mode: str) -> None:
        """Switch between fire and ember mode (key M). A switch ends a pause, and ember mode starts
        from an empty picture; the permission is asked again while it is undecided."""
        mode = mode if mode in MODES else "fire"
        if mode == self.mode:
            return
        if self.paused:
            self.toggle_pause()
        self.mode = mode
        self.mode_switches += 1
        if mode == "ember":
            self.states["ember"] = _ember_start()
            self.worker_camera_state = "off"
            if self.permission is not None and not self.permission.allowed:
                QTimer.singleShot(80, self._ask_permission)    # after the "asking" message has been painted
        if self.on_mode is not None:
            self.on_mode(mode)
        self.update()

    def _ask_permission(self) -> None:
        if self.mode != "ember" or self.permission is None or self.permission.allowed:
            return
        if self._perm_timer.isActive():
            return                             # a request is open already: its answer is polled
        if self.permission.ask_async():        # the GUI thread is the main thread; it returns at once
            self._perm_until = time.monotonic() + self.permission.timeout_s
            self._perm_timer.start()
            self.update()
            return
        self._permission_answered()

    def _poll_permission(self) -> None:
        status = self.permission.refresh() if self.permission is not None else "authorized"
        if status != "not_determined" or time.monotonic() > self._perm_until:
            self._perm_timer.stop()
            self._permission_answered()

    def _permission_answered(self) -> None:
        if self.on_permission is not None and self.permission is not None:
            self.on_permission(self.permission.allowed)
        self.update()

    # Raw or analysed ---------------------------------------------------------------------------
    def analysed_level(self, now: float | None = None) -> float:
        """1 for the analysed screen, 0 for the raw picture, in between during the fade."""
        a0, a1, t0 = self._fade
        dur = abs(a1 - a0) * self.raw_fade_s
        if dur <= 0:
            return a1
        f = min(1.0, max(0.0, ((self.clock() if now is None else now) - t0) / dur))
        return a0 + (a1 - a0) * f

    def fading(self) -> bool:
        return self.analysed_level() != self._fade[1]

    def shown_level(self) -> float:
        """The analysed level painted: the fire footage's (key A) in fire mode; ember mode is always analysed."""
        return 1.0 if self.mode == "ember" else self.analysed_level()

    def toggle_raw(self) -> None:
        """Key A: the fire footage between raw and analysed. In ember mode it does nothing (the
        ember screen is always analysed, so a visitor never meets a bare camera picture)."""
        if self.mode != "fire":
            return
        now = self.clock()
        level = self.analysed_level(now)
        self.raw = not self.raw
        self.raw_toggles += 1
        self._fade = (level, 0.0 if self.raw else 1.0, now)
        if self.raw_fade_s > 0:
            self._fade_timer.start()

    def _fade_tick(self) -> None:
        self.update()
        if not self.fading():
            self._fade_timer.stop()

    # Keys ------------------------------------------------------------------------------------
    def quit_prompt(self) -> bool:
        """The Esc confirm prompt is showing."""
        return time.monotonic() - self._esc_at < self.quit_confirm_s

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pauses += 1
        if self.on_pause is not None:
            self.on_pause(self.paused)

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        k = ev.key()
        if ev.isAutoRepeat() and k in (Qt.Key.Key_Escape, Qt.Key.Key_Space, Qt.Key.Key_A, Qt.Key.Key_M):
            return                            # a held key must not quit, flicker the pause, the fade or the mode
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
        elif k == Qt.Key.Key_A:
            self.toggle_raw()
        elif k == Qt.Key.Key_M:
            self.set_mode("ember" if self.mode == "fire" else "fire")
        elif k == Qt.Key.Key_Space:
            self.toggle_pause()
        elif k == Qt.Key.Key_Escape:
            if self.quit_prompt():
                self.quit_confirmed = True
                self.close()
                return
            self._esc_at = time.monotonic()
            QTimer.singleShot(int(self.quit_confirm_s * 1000) + 50, self.update)   # the prompt goes away
        self.update()

    def shown_state(self) -> LiveState:
        """The state as painted: in ember mode with the camera state shown."""
        s = self.state
        if self.mode == "ember":
            cam = self.camera_state_shown()
            if cam != s.camera_state:
                s = dataclasses.replace(s, camera_state=cam)
        return s

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        paint_scene(p, self.width(), self.height(), self.shown_state(), self.lang, show_limits=self.show_limits,
                    show_tracks=self.show_tracks, show_field=self.show_field, show_gate=self.show_gate,
                    paused=self.paused, quit_prompt=self.quit_prompt(), analysed=self.shown_level(),
                    page_url=self.page_url)
        p.end()
        self.paints += 1

    def report(self) -> dict[str, Any]:
        e = dict(self.ember_seen)
        e["numbers"] = sorted(e["numbers"])
        e["counts"] = {str(k): v for k, v in sorted(e["counts"].items())}
        return {"mode": self.mode, "raw": self.raw, "raw_toggles": self.raw_toggles, "mode_switches": self.mode_switches,
                "modes": dict(self.modes_seen), "camera_state": self.camera_state_shown(), "ember": e}


def _ember_start() -> LiveState:
    """Ember mode before its first camera frame."""
    return LiveState(mode="ember", camera_state="starting", source_state="starting")


class LimitsWindow(QWidget):
    """The limits card alone, fullscreen on a second display."""

    def __init__(self, main: BoothWindow):
        super().__init__()
        self.main = main
        self.setStyleSheet("background-color: #000000;")
        self.setCursor(Qt.CursorShape.BlankCursor)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        paint_scene(p, self.width(), self.height(), LiveState(), self.main.lang, show_limits=True,
                    show_tracks=False, show_field=False, show_gate=False)
        p.end()


# Heartbeat -----------------------------------------------------------------------------------

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
    """A small JSON file rewritten every few seconds; the booth supervisor and the soak read it
    (keys in the module docstring)."""

    def __init__(self, path: str | Path, source: str = "", every_s: float = 2.0):
        import os

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.source = source
        self.every_s = every_s
        self.t0 = time.monotonic()
        self.pid = os.getpid()
        self._rss: dict[int, float | None] = {}
        self._rss_at = -1e9

    def write(self, win: BoothWindow, worker, status: str = "running") -> None:
        from wfglink.provenance import now_shanghai

        now = time.monotonic()
        if now - self._rss_at > 10.0:     # ps is not free; memory moves slowly
            self._rss = {pid: rss_mb(pid) for pid in [self.pid] + list(worker.child_pids())}
            self._rss_at = now
        st = win.state
        data = {"status": status, "time": now_shanghai(), "epoch": time.time(), "pid": self.pid,
                "uptime_s": round(now - self.t0, 1), "frames": worker.frames, "paints": win.paints,
                "fps": round(st.fps or 0.0, 2), "source": self.source,
                "state": (st.source_state if worker.frames else "starting") if win.mode == "fire"
                else (st.source_state or "starting"),
                "errors": worker.error_count, "last_error": worker.errors[-1] if worker.errors else None,
                "rss_mb": {str(k): (round(v, 1) if v is not None else None) for k, v in self._rss.items()},
                "clip": worker.clip if win.mode == "fire" else None, "paused": bool(win.paused),
                # Frames received and analysed by the active pipeline, so the soak can tell an
                # app that keeps painting from one that keeps analysing.
                "pipeline": worker.pipeline_counters(),
                "mode": win.mode, "raw": bool(win.raw), "camera_state": win.camera_state_shown()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(self.path)


# The app -------------------------------------------------------------------------------------

KEY_NAMES = {"A": Qt.Key.Key_A, "M": Qt.Key.Key_M, "L": Qt.Key.Key_L, "T": Qt.Key.Key_T, "F": Qt.Key.Key_F,
             "G": Qt.Key.Key_G, "I": Qt.Key.Key_I, "Space": Qt.Key.Key_Space}


def press_key(win: QWidget, name: str) -> None:
    """A key press as the keyboard gives it (the demo gate's key script)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, KEY_NAMES[name], Qt.KeyboardModifier.NoModifier))


def run_live(cfg: dict | None = None, source: dict[str, str] | None = None, screen: str | None = None,
             lang: str | None = None, limits_screen: str | None = None, duration_s: float | None = None,
             screenshot: str | None = None, heartbeat: str | None = None, ember: dict[str, str] | None = None,
             start_mode: str = "fire", permission: Callable[[float], str] | None = None,
             keys: list[tuple[float, str]] | None = None) -> dict[str, Any]:
    """Run the booth screen until Esc is confirmed, the duration ends or a signal arrives; returns a report.

    source is fire mode's (source_spec), ember ember mode's (ember_spec; by default the camera,
    or the generated phone scene with a synthetic source); start_mode fire or ember; permission
    replaces wfglink.io.camera.request_permission (tests); keys presses keys (KEY_NAMES) at the
    given seconds after the start (the demo gate)."""
    cfg = cfg or load_config(local=True)
    spec = source or source_spec(cfg=cfg)
    espec = ember or ember_spec(synthetic=spec.get("kind") == "synthetic")
    start_mode = start_mode if start_mode in MODES else "fire"
    ui = cfg.get("ui") or {}
    lv = cfg.get("live") or {}
    # Camera permission on the main thread, before any window or thread exists (macOS shows its
    # dialog once, on the first run; afterwards this returns at once). Fake cameras need none.
    perm = CameraPermission(espec.get("kind", "camera") == "camera", float(lv.get("camera_permission_timeout_s", 20.0)),
                            permission)
    perm.ask()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from wfglink.ui.fonts import load_fonts

    load_fonts()
    mode = lv.get("worker_mode", "thread")
    if mode == "process":
        from wfglink.ui.process_worker import ProcessLiveWorker

        worker = ProcessLiveWorker(cfg, spec, espec, start_mode, perm.allowed)
    else:
        worker = LiveWorker(cfg, spec, espec, start_mode, perm.allowed)
    win = BoothWindow(lang or ui.get("language", "ko"), float(ui.get("quit_confirm_s", 3.0)), worker.set_paused,
                      mode=start_mode, on_mode=worker.set_mode, permission=perm, on_permission=worker.set_camera_allowed,
                      raw_fade_s=float(ui.get("raw_fade_s", 0.5)),
                      page_url=str((cfg.get("booth") or {}).get("ember_page_url") or ""))
    limits = LimitsWindow(win) if limits_screen else None
    placer = ScreenPlacer(app, win, screen or ui.get("screen", "auto"), ui.get("builtin_screen", BUILTIN_SCREEN),
                          limits, limits_screen)
    worker.state_ready.connect(win.on_state, Qt.ConnectionType.QueuedConnection)
    threads_start = threading.active_count()
    worker.start()
    pressed: list[dict[str, Any]] = []
    for at_s, name in keys or []:
        def _press(n=name, at=at_s):
            press_key(win, n)
            pressed.append({"key": n, "at_s": at, "mode": win.mode, "raw": win.raw, "paused": win.paused})
        QTimer.singleShot(int(float(at_s) * 1000), _press)
    if duration_s:
        def finish():
            win.duration_done = True
            if screenshot:
                Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
                win.grab().save(screenshot)
            win.close()
        QTimer.singleShot(int(duration_s * 1000), finish)
    # SIGTERM (the supervisor) or SIGINT (Ctrl-C) closes the window; the loop below notices.
    stop_signal: list[int] = []
    old_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            old_handlers[sig] = signal.signal(sig, lambda signum, _f: stop_signal.append(signum))
        except ValueError:      # not the main thread (tests): leave the handlers alone
            pass
    hb = Heartbeat(heartbeat, spec.get("kind", "")) if heartbeat else None
    n_events = int((cfg.get("booth") or {}).get("report_events", 100))
    t0 = time.monotonic()
    t_hb = 0.0
    try:
        while win.isVisible():
            app.processEvents()
            time.sleep(0.002)
            if stop_signal:
                win.close()
                break
            win.set_camera_state(worker.camera_state)
            now = time.monotonic()
            if hb is not None and now - t_hb >= hb.every_s:
                t_hb = now
                hb.write(win, worker)
            if duration_s and now - t0 > duration_s + 5:
                break
    finally:
        worker.shutdown(5000)
        for sig, h in old_handlers.items():
            signal.signal(sig, h)
        if limits is not None:
            limits.close()
        if hb is not None:
            done = win.quit_confirmed or getattr(win, "duration_done", False)
            hb.write(win, worker, "clean_exit" if done and not stop_signal else "closed")
    st = win.state
    rep = worker.report(n_events)    # in process mode, the child's last periodic report
    result = {
        "seconds": round(time.monotonic() - t0, 1), "frames": worker.frames, "paints": win.paints,
        "errors": worker.errors[-10:], "error_count": worker.error_count, "worker_mode": mode,
        "source": spec.get("kind"), "clip": rep.get("clip"),
        "quit_confirmed": win.quit_confirmed, "signal": stop_signal[0] if stop_signal else None,
        "last": {"count_rate": st.count_rate, "cpc": st.cpc_gross, "pnf": st.pnf, "speed": st.speed,
                 "fps": st.fps, "state": st.source_state, "label": st.source_label},
        "pipelines": rep.get("pipelines", {}), "playback": rep.get("playback", {}), "events": rep.get("events", []),
        "states": dict(win.states_seen), "clips": dict(win.clips_seen), "pauses": win.pauses,
        "screen": {"name": placer.screen.name() if placer.screen is not None else None, "moves": placer.moves},
        "ember_source": espec.get("kind"), "permission": perm.status, "permission_asks": perm.asks, **win.report(),
        "keys_pressed": pressed, "threads_start": threads_start, "threads_end": threading.active_count(),
    }
    win.deleteLater()
    app.processEvents()
    return result
