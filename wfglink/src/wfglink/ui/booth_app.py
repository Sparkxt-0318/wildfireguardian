"""The booth screen: approved clips analysed live as they play (python -m wfglink live).

    python -m wfglink live                      # the playlist (booth/playlist.yaml), in a loop
    python -m wfglink live --synthetic          # generated video
    python -m wfglink live --clip data/clips/C6_nist_dragon.yaml
    bash booth/booth.sh                         # the playlist under the supervisor, for a whole day

Playback (wfglink.io.playlist.Player) decodes the clips in real time and keeps only the
newest frame; the analysis takes the newest frame whenever it is free, so frames are
skipped rather than queued and the picture never lags. live.worker_mode chooses where
playback and analysis run: in this process (thread) or in a child process (process,
ui/process_worker.py). Both use LiveAnalyser, so the screen is the same.

Counts: with booth.reset_per_clip true (the default) every clip start resets the pipeline,
so the counts are per clip; with false each clip keeps one pipeline whose counts run on
across loops. A cut inside a clip (its next segment) restarts only the background model
and the tracks.

Screen (--screen, ui.screen): auto puts the window fullscreen on the external monitor when
one is connected, else on the built-in screen, and moves it when a monitor is plugged in or
out (screenAdded, screenRemoved); external means the same; primary is the main screen; any
other value is a screen name (auto while that screen is absent). Built-in screens are
recognised by name (ui.builtin_screen). --limits-screen puts the limits card on a second
screen while that screen is not the booth's.

Keys: L language, T tracks, F field, G gate, Space pause (playback and analysis hold; a
small tag shows), I limits card, Esc then Esc again within ui.quit_confirm_s seconds quits
(a prompt shows after the first). SIGTERM or SIGINT closes the window too (not a clean exit).

Heartbeat (--heartbeat FILE, booth.sh passes logs/heartbeat.json), rewritten every 2 s:
status (running, clean_exit, closed), time, epoch, pid, uptime_s, frames (states analysed),
paints, fps (analysis), source (playlist, clip or synthetic), state (starting, playing,
synthetic), errors (count), last_error, rss_mb {pid: MB}, clip (the playlist item playing,
or "synthetic"), paused, pipeline {key, frames_in, frames_analysed, frames_duplicate}.
"""
from __future__ import annotations

import json
import re
import signal
import sys
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


class LiveAnalyser:
    """Turns playback frames into LiveStates; the same code in both worker modes.

    One pipeline per clip, created with the clip's gate (if its settings file gives one);
    booth.reset_per_clip decides whether a clip start replaces it (see the module docstring).
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.reset_per_clip = bool((cfg.get("booth") or {}).get("reset_per_clip", True))
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
        s = LiveState(**st.__dict__)       # shallow copy, owned by the screen from now on
        if s.image is not None:
            s.image = np.ascontiguousarray(s.image)
        s.source_label = str(m.get("label") or "")
        s.source_credit = str(m.get("credit") or "")
        s.source_state = "synthetic" if m.get("synthetic") else "playing"
        s.fps = (len(self._times) - 1) / span if len(self._times) > 2 and span > 0 else 0.0
        return s

    def stats(self) -> dict[str, dict]:
        """Each clip's pipeline stats (the latest pipeline of each clip)."""
        return {k: p.stats.as_dict() for k, p in self.pipes.items()}

    def counters(self) -> dict[str, Any] | None:
        """The active pipeline's frame counters for the heartbeat."""
        pipe = self.pipes.get(self.active) if self.active is not None else None
        return heartbeat_counters(self.active, pipe.stats if pipe is not None else None)


class LiveWorker(QThread):
    """Thread mode: playback in its own thread, analysis in this QThread (the newest frame only)."""

    state_ready = Signal(object)

    def __init__(self, cfg: dict, spec: dict[str, str]):
        super().__init__()
        self.cfg = cfg
        self.player = make_player(cfg, spec)
        self.analyser = LiveAnalyser(cfg)
        self._running = True
        self.frames = 0
        self.errors: list[str] = []
        self.error_count = 0

    def start(self) -> None:  # type: ignore[override]
        self.player.start()
        super().start()

    def stop(self) -> None:
        self._running = False

    def shutdown(self, ms: int = 5000) -> bool:
        """Stop analysis and playback and wait for both."""
        self.stop()
        done = self.wait(ms)
        self.player.stop()
        return bool(done)

    def set_paused(self, paused: bool) -> None:
        self.player.pause() if paused else self.player.resume()

    @property
    def paused(self) -> bool:
        return self.player.paused

    @property
    def clip(self) -> str | None:
        return self.analyser.active

    def child_pids(self) -> list[int]:
        return []

    def run(self) -> None:
        import gc

        gc.freeze()  # long-lived objects out of the collector: avoids 50 ms pauses
        last = None
        while self._running:
            f = self.player.latest()
            if f is None or f.index == last:
                self.msleep(3)
                continue
            last = f.index
            try:
                s = self.analyser.process(f)
            except Exception as exc:  # keep the booth alive; record and continue
                self.error_count += 1
                self.errors = (self.errors + [f"{type(exc).__name__}: {exc}"])[-100:]
                self.msleep(10)
                continue
            self.frames += 1
            self.state_ready.emit(s)

    def report(self, n_events: int) -> dict[str, Any]:
        """Playback events (the last n_events), counters and each clip's pipeline stats."""
        return {"clip": self.analyser.active, "events": list(self.player.events[-n_events:]) if n_events > 0 else [],
                "playback": dict(self.player.stats), "pipelines": self.analyser.stats()}

    def pipeline_counters(self) -> dict[str, Any] | None:
        return self.analyser.counters()


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
    def __init__(self, lang: str = "ko", quit_confirm_s: float = 3.0, on_pause: Callable[[bool], None] | None = None):
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
        self.paused = False
        self.on_pause = on_pause
        self.quit_confirm_s = float(quit_confirm_s)
        self._esc_at = -1e9
        self.paints = 0
        self.pauses = 0
        self.quit_confirmed = False
        self.states_seen: dict[str, int] = {}   # states received, by source state: for the report
        self.clips_seen: dict[str, int] = {}    # ... and by clip name

    def on_state(self, s: LiveState) -> None:
        self.state = s
        self.states_seen[s.source_state] = self.states_seen.get(s.source_state, 0) + 1
        if s.source_label:
            self.clips_seen[s.source_label] = self.clips_seen.get(s.source_label, 0) + 1
        self.update()

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
        if ev.isAutoRepeat() and k in (Qt.Key.Key_Escape, Qt.Key.Key_Space):
            return                            # a held key must not quit or flicker the pause
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

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        paint_scene(p, self.width(), self.height(), self.state, self.lang, show_limits=self.show_limits,
                    show_tracks=self.show_tracks, show_field=self.show_field, show_gate=self.show_gate,
                    paused=self.paused, quit_prompt=self.quit_prompt())
        p.end()
        self.paints += 1


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
                "state": st.source_state if worker.frames else "starting",
                "errors": worker.error_count, "last_error": worker.errors[-1] if worker.errors else None,
                "rss_mb": {str(k): (round(v, 1) if v is not None else None) for k, v in self._rss.items()},
                "clip": worker.clip, "paused": bool(win.paused),
                # Frames received and analysed by the active pipeline, so the soak can tell an
                # app that keeps painting from one that keeps analysing.
                "pipeline": worker.pipeline_counters()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(self.path)


# The app -------------------------------------------------------------------------------------

def run_live(cfg: dict | None = None, source: dict[str, str] | None = None, screen: str | None = None,
             lang: str | None = None, limits_screen: str | None = None, duration_s: float | None = None,
             screenshot: str | None = None, heartbeat: str | None = None) -> dict[str, Any]:
    """Run the booth screen until Esc is confirmed, the duration ends or a signal arrives; returns a report."""
    cfg = cfg or load_config(local=True)
    spec = source or source_spec(cfg=cfg)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from wfglink.ui.fonts import load_fonts

    load_fonts()
    ui = cfg.get("ui") or {}
    mode = (cfg.get("live") or {}).get("worker_mode", "thread")
    if mode == "process":
        from wfglink.ui.process_worker import ProcessLiveWorker

        worker = ProcessLiveWorker(cfg, spec)
    else:
        worker = LiveWorker(cfg, spec)
    win = BoothWindow(lang or ui.get("language", "ko"), float(ui.get("quit_confirm_s", 3.0)), worker.set_paused)
    limits = LimitsWindow(win) if limits_screen else None
    placer = ScreenPlacer(app, win, screen or ui.get("screen", "auto"), ui.get("builtin_screen", BUILTIN_SCREEN),
                          limits, limits_screen)
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
    }
    win.deleteLater()
    app.processEvents()
    return result
