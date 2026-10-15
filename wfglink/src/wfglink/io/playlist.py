"""Real-time playback of the approved booth clips (python -m wfglink live).

The playlist (booth/playlist.yaml, config booth.playlist) names clip settings files
data/clips/<id>.yaml; an entry may override the clip's approved segments and its name:

    clips:
      - clip: C5_nist_emberometer              # data/clips/C5_nist_emberometer.yaml
      - clip: C6_nist_dragon
        segments_s: [[14.0, 20.0]]             # optional: seconds of the file to play
        label: NIST Dragon                     # optional: name in the status line

Each clip plays only over its segments_s (null as an end means the end of the file),
cropped to its roi, and the playlist loops for ever. The status line shows the clip's name
(the entry's label, else its title in data/clips.csv) and its credit line (data/clips.csv,
column credit_line).

Player is a thread that plays the items and keeps only the newest frame (a one-slot
buffer), so a slow analysis skips frames instead of building latency:
- frames are paced by their timestamps against a monotonic clock;
- a decoded frame more than booth.late_frames frame intervals late is dropped before its
  conversion, as long as dropping catches up; when it does not (decoding alone is slower
  than real time) or playback is more than booth.resync_s behind, the clock restarts at
  the current frame, so the clip plays on slower instead of racing;
- frames whose roi is wider than live.analysis_max_width, or has more pixels than
  live.analysis_max_pixels, are scaled down while they are converted (4K sources), so the
  analysis and the screen never handle more;
- a clip that is missing or fails to open or decode is skipped with a log line and tried
  again on the next loop;
- when a whole pass shows no frame, synthetic video plays for booth.retry_s seconds and
  the playlist is tried again, so the screen is never black;
- pause() holds the picture: nothing more is shown and the clock stops until resume().

Frame times are playback times: true clip times shifted so that they increase across
segments, clips and loops, with a gap of booth.cut_gap_s at every cut so that no track
joins two shots. frame.meta carries item (counts clip starts), segment (counts segment
starts), clip (id, or "synthetic"), label, credit, clip_t (seconds in the file), loop
(completed passes), synthetic (bool) and gate (the clip's gate in analysed pixels, or None).
"""
from __future__ import annotations

import csv
import math
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from wfglink import PROJECT_ROOT
from wfglink.io.frames import Frame


class PlaylistError(ValueError):
    """The playlist file is missing or has a wrong format."""


@dataclass
class PlayItem:
    key: str                                   # clip id, or the file name without extension
    path: Path | None                          # the video file (None: the entry could not be resolved)
    segments: list[tuple[float, float | None]] = field(default_factory=lambda: [(0.0, None)])
    roi: list[float] | None = None             # x0, y0, x1, y1: fractions of the frame, or pixels when any value exceeds 1
    gate: list[float] | None = None            # x1, y1, x2, y2 in the same units as the roi'd frame; None: default gate
    label: str = ""                            # name in the status line
    credit: str = ""                           # credit line in the status line
    error: str = ""                            # why the entry could not be resolved


@dataclass
class PlaybackConfig:
    late_frames: float = 1.0                   # drop a decoded frame later than this many frame intervals
    resync_s: float = 0.5                      # this far behind, the clock restarts instead
    retry_s: float = 30.0                      # nothing playable: synthetic video for this long, then try again
    cut_gap_s: float = 1.0                     # playback-time gap at a cut
    max_width: int = 1280                      # frames are converted at most this wide (after the roi)
    max_pixels: int = 1280 * 720               # ... and with at most this many pixels
    events_kept: int = 500

    @classmethod
    def from_config(cls, cfg: dict) -> "PlaybackConfig":
        b = (cfg.get("booth") or {}) if isinstance(cfg, dict) else {}
        live = (cfg.get("live") or {}) if isinstance(cfg, dict) else {}
        c = cls(**{k: type(getattr(cls, k))(b[k]) for k in ("late_frames", "resync_s", "retry_s", "cut_gap_s")
                   if b.get(k) is not None})
        if live.get("analysis_max_width"):
            c.max_width = int(live["analysis_max_width"])
        if live.get("analysis_max_pixels"):
            c.max_pixels = int(live["analysis_max_pixels"])
        c.retry_s = max(1.0, c.retry_s)
        return c


# Playlist files ------------------------------------------------------------------------

def read_clip_table(path: Path | None = None) -> dict[str, dict[str, str]]:
    """data/clips.csv rows by clip_id ({} when the file is missing)."""
    path = path or PROJECT_ROOT / "data" / "clips.csv"
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return {r["clip_id"]: r for r in csv.DictReader(fh) if r.get("clip_id")}
    except OSError:
        return {}


def _resolve(p: Path, root: Path) -> Path | None:
    """An existing path: as given (absolute, or relative to the working directory), else under root."""
    if p.is_absolute():
        return p if p.exists() else None
    for c in (Path.cwd() / p, root / p):
        if c.exists():
            return c
    return None


def _segments(raw: Any) -> list[tuple[float, float | None]]:
    if not raw:
        return [(0.0, None)]
    out = []
    for seg in raw:
        if not isinstance(seg, (list, tuple)) or len(seg) != 2:
            raise PlaylistError(f"segment {seg!r}: needs [start, end] in seconds")
        a, b = float(seg[0] or 0.0), (None if seg[1] is None else float(seg[1]))
        if b is not None and b <= a:
            raise PlaylistError(f"segment {seg!r}: ends before it starts")
        out.append((a, b))
    return out


def clip_item(spec: str | Path, root: Path = PROJECT_ROOT, segments: Any = None, label: str | None = None,
              table: dict[str, dict[str, str]] | None = None) -> PlayItem:
    """A PlayItem from a clip id (data/clips/<id>.yaml), a clip settings file or a video file.

    A video file plays whole and uncropped. A missing video is not an error here: the
    player skips it and tries again on every loop, so a clip copied in later still plays.
    """
    table = read_clip_table(root / "data" / "clips.csv") if table is None else table
    p = Path(str(spec))
    if not p.suffix and len(p.parts) == 1:
        p = Path("data") / "clips" / f"{spec}.yaml"
    path = _resolve(p, root)
    if path is None:
        return PlayItem(p.stem, None, error=f"not found: {spec}")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            cc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            return PlayItem(path.stem, None, error=f"cannot read {path}: {exc}")
        key = str(cc.get("clip_id") or path.stem)
        if not cc.get("file"):
            return PlayItem(key, None, error=f"{path}: no 'file'")
        video = Path(cc["file"]) if Path(cc["file"]).is_absolute() else root / cc["file"]
        row = table.get(key, {})
        return PlayItem(key, video, _segments(segments if segments is not None else cc.get("segments_s")),
                        cc.get("roi"), cc.get("gate"), label or row.get("title") or key, row.get("credit_line", ""))
    row = table.get(path.stem, {})
    return PlayItem(path.stem, path, _segments(segments), None, None, label or row.get("title") or path.name,
                    row.get("credit_line", ""))


def load_playlist(path: str | Path, root: Path = PROJECT_ROOT) -> list[PlayItem]:
    """The items of a playlist file (see the module docstring); raises PlaylistError."""
    p = _resolve(Path(path), root)
    if p is None:
        raise PlaylistError(f"playlist not found: {path}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PlaylistError(f"cannot read {p}: {exc}") from exc
    entries = data.get("clips") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise PlaylistError(f"{p}: needs a list of entries under 'clips'")
    table = read_clip_table(root / "data" / "clips.csv")
    items = []
    for e in entries:
        if isinstance(e, str):
            e = {"clip": e}
        if not isinstance(e, dict) or not e.get("clip"):
            raise PlaylistError(f"{p}: entry {e!r} needs 'clip'")
        items.append(clip_item(e["clip"], root, segments=e.get("segments_s"), label=e.get("label"), table=table))
    return items


def roi_pixels(roi: list[float] | None, w: int, h: int) -> tuple[int, int, int, int]:
    """x0, y0, x1, y1 in pixels of a w x h frame (the whole frame without a roi)."""
    if not roi:
        return 0, 0, w, h
    r = [float(v) for v in roi]
    if max(r) <= 1.0:
        r = [r[0] * w, r[1] * h, r[2] * w, r[3] * h]
    x0, x1 = sorted((int(round(min(max(r[0], 0), w))), int(round(min(max(r[2], 0), w)))))
    y0, y1 = sorted((int(round(min(max(r[1], 0), h))), int(round(min(max(r[3], 0), h)))))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return 0, 0, w, h
    return x0, y0, x1, y1


def _stderr(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [playlist] {msg}", file=sys.stderr, flush=True)


# The player ------------------------------------------------------------------------------

class Player(threading.Thread):
    """Plays items in a loop in real time and keeps only the newest frame (see the module docstring).

    items empty: synthetic video only (python -m wfglink live --synthetic).
    """

    def __init__(self, items: list[PlayItem], cfg: PlaybackConfig | None = None,
                 synthetic: Callable[[], Any] | None = None, log: Callable[[str], None] | None = None):
        super().__init__(daemon=True, name="playback")
        self.items = list(items)
        self.cfg = cfg or PlaybackConfig()
        self.make_synthetic = synthetic or _default_synthetic
        self.log = log or _stderr
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self._go = threading.Event()               # cleared while paused
        self._go.set()
        self.frame: Frame | None = None
        self.events: list[dict] = []
        self.stats = {"decoded": 0, "shown": 0, "late": 0, "resyncs": 0, "loops": 0, "skipped": 0, "failed": 0}
        self.errors: list[str] = []
        self._index = 0
        self._item = -1                            # clip starts so far (frame.meta["item"])
        self._segment = -1                         # segment starts so far
        self._t_next = 0.0                         # playback time of the next segment start
        self._t_last = None                        # playback time of the last decoded frame
        self._anchor: list[float] | None = None    # [monotonic time, playback time] of the clock
        self._prev_late: float | None = None
        self._synth = None
        self._synth_base = 0.0
        self._skip_reason: dict[str, str] = {}     # last logged skip reason per clip (quiet repeats)

    # Control ----------------------------------------------------------------------------
    def latest(self) -> Frame | None:
        with self._lock:
            return self.frame

    @property
    def paused(self) -> bool:
        return not self._go.is_set()

    def pause(self) -> None:
        if self._go.is_set():
            self._go.clear()
            self._event("paused")

    def resume(self) -> None:
        if not self._go.is_set():
            self._go.set()
            self._event("resumed")

    def stop(self, timeout_s: float = 3.0) -> None:
        self._halt.set()
        self._go.set()
        if self.is_alive():
            self.join(timeout_s)

    def _event(self, kind: str, **info) -> None:
        self.events.append({"t": round(time.monotonic(), 3), "event": kind, **info})
        if len(self.events) > self.cfg.events_kept:
            del self.events[: len(self.events) - self.cfg.events_kept]

    # Main loop --------------------------------------------------------------------------
    def run(self) -> None:
        while not self._halt.is_set():
            try:
                shown = False
                for item in self.items:
                    if self._halt.is_set():
                        break
                    shown = self._play_item(item) or shown
                if self.items and not self._halt.is_set():
                    self.stats["loops"] += 1
                if not shown and not self._halt.is_set():
                    if self.items and self._synth is None:
                        self.log(f"no playable clip in {len(self.items)} entries; synthetic video for "
                                 f"{self.cfg.retry_s:g} s, then the playlist again")
                    self._play_synthetic(self.cfg.retry_s if self.items else math.inf)
            except Exception as exc:   # never let playback die: log, wait a moment, go on
                msg = f"{type(exc).__name__}: {exc}"
                self.errors.append(msg)
                self.errors = self.errors[-20:]
                self.log(f"playback error: {msg}")
                self._halt.wait(1.0)

    def _skip(self, item: PlayItem, reason: str, kind: str = "skipped") -> None:
        self.stats[kind] += 1
        self._event(kind, clip=item.key, reason=reason)
        if self._skip_reason.get(item.key) != reason:      # one log line per new reason
            self._skip_reason[item.key] = reason
            self.log(f"{kind} {item.key}: {reason} (tried again on the next loop)")

    def _new_item(self) -> None:
        self._item += 1

    def _new_segment(self) -> float:
        """Start a segment: a new count, a clock restart; returns its playback start time
        (after the last frame and a cut gap, also when the previous clip failed mid-way)."""
        self._segment += 1
        self._anchor = None
        self._prev_late = None
        if self._t_last is not None:
            self._t_next = max(self._t_next, self._t_last + self.cfg.cut_gap_s)
        return self._t_next

    def _end_segment(self, dt: float) -> None:
        if self._t_last is not None:
            self._t_next = self._t_last + dt + self.cfg.cut_gap_s

    def _play_item(self, item: PlayItem) -> bool:
        """Play one item over its segments; True when it showed at least one frame."""
        import av

        if item.error:
            self._skip(item, item.error)
            return False
        if item.path is None or not item.path.exists():
            self._skip(item, f"file not found: {item.path}")
            return False
        shown0 = self.stats["shown"]
        started = False
        try:
            with av.open(str(item.path)) as c:
                stream = c.streams.video[0]
                stream.thread_type = "AUTO"
                rate = stream.average_rate or stream.guessed_rate
                dt = 1.0 / float(rate) if rate else 1.0 / 30.0
                fresh = True                       # nothing decoded yet: no seek needed for a start at 0
                for seg_start, seg_end in item.segments:
                    if self._halt.is_set():
                        break
                    if not started:
                        self._close_synthetic()
                        self._new_item()
                        started = True
                        self._event("started", clip=item.key)
                        if item.key in self._skip_reason:
                            self.log(f"{item.key} plays again")
                            del self._skip_reason[item.key]
                    base = self._new_segment()
                    if seg_start > 0 or not fresh:
                        c.seek(int(max(seg_start, 0.0) / stream.time_base), stream=stream, backward=True)
                    fresh = False
                    for vf in c.decode(stream):
                        if self._halt.is_set():
                            break
                        ct = vf.time
                        if ct is None or ct < seg_start - 1e-6:
                            continue
                        if seg_end is not None and ct >= seg_end:
                            break
                        self.stats["decoded"] += 1
                        t_play = base + (ct - seg_start)
                        self._t_last = t_play
                        if not self._on_time(t_play, dt, droppable=True):
                            continue
                        img, scale = self._convert(vf, item)
                        if not self._wait(t_play):
                            break
                        self._publish(img, t_play, item, ct, scale)
                    self._end_segment(dt)
        except Exception as exc:
            self._skip(item, f"{type(exc).__name__}: {exc}", "failed")
        return self.stats["shown"] > shown0

    # Pacing -------------------------------------------------------------------------------
    def _on_time(self, t_play: float, dt: float, droppable: bool) -> bool:
        """False when the frame should be dropped (late, and dropping catches up)."""
        now = time.monotonic()
        if self._anchor is None:
            self._anchor = [now, t_play]
        late = now - (self._anchor[0] + (t_play - self._anchor[1]))
        if late <= self.cfg.late_frames * dt:
            self._prev_late = None
            return True
        if droppable and late <= self.cfg.resync_s and (self._prev_late is None or late < self._prev_late):
            self._prev_late = late
            self.stats["late"] += 1
            return False
        # Dropping does not catch up (or the stall was long): restart the clock at this frame.
        self._anchor = [now, t_play]
        self._prev_late = None
        self.stats["resyncs"] += 1
        return True

    def _wait(self, t_play: float) -> bool:
        """Sleep until the frame is due; a pause stops the clock. False when stopping."""
        while not self._halt.is_set():
            if not self._go.is_set():
                t0 = time.monotonic()
                while not self._go.wait(0.05):
                    if self._halt.is_set():
                        return False
                if self._anchor is not None:
                    self._anchor[0] += time.monotonic() - t0     # the paused time does not count
                continue
            wait = self._anchor[0] + (t_play - self._anchor[1]) - time.monotonic()
            if wait <= 0:
                return True
            self._halt.wait(min(wait, 0.05))
        return False

    def _convert(self, vf, item: PlayItem) -> tuple[np.ndarray, float]:
        """BGR image of the roi, at most max_width wide and max_pixels large, and the scale applied."""
        w, h = vf.width, vf.height
        x0, y0, x1, y1 = roi_pixels(item.roi, w, h)
        s = 1.0
        if self.cfg.max_width:
            s = min(s, self.cfg.max_width / (x1 - x0))
        if self.cfg.max_pixels:
            s = min(s, (self.cfg.max_pixels / ((x1 - x0) * (y1 - y0))) ** 0.5)
        if s < 1.0:
            # Scale while converting: one pass over a 4K frame instead of two.
            img = vf.to_ndarray(format="bgr24", width=max(2, int(round(w * s))), height=max(2, int(round(h * s))),
                                interpolation="AREA")
            x0, y0, x1, y1 = (int(round(v * s)) for v in (x0, y0, x1, y1))
        else:
            img = vf.to_ndarray(format="bgr24")
        if (x0, y0, x1, y1) != (0, 0, img.shape[1], img.shape[0]):
            img = img[y0:y1, x0:x1]
        return np.ascontiguousarray(img), s

    def _publish(self, img: np.ndarray, t_play: float, item: PlayItem | None, clip_t: float, scale: float) -> None:
        gate = None
        if item is not None and item.gate:
            g = [float(v) for v in item.gate]
            gate = g if max(g) <= 1.0 else [v * scale for v in g]
        meta = {"item": self._item, "segment": self._segment, "loop": self.stats["loops"],
                "clip": item.key if item else "synthetic", "label": item.label if item else "",
                "credit": item.credit if item else "", "clip_t": round(float(clip_t), 4),
                "synthetic": item is None, "gate": gate}
        f = Frame(img, float(t_play), self._index, time.monotonic(), meta)
        self._index += 1
        with self._lock:
            self.frame = f
        self.stats["shown"] += 1

    # Synthetic video ------------------------------------------------------------------------
    def _play_synthetic(self, seconds: float) -> None:
        """Synthetic video for `seconds` of playback time; one item however often it is resumed."""
        if self._synth is None:
            self._synth = self.make_synthetic()
            self._synth.open()
            self._new_item()
            self._synth_base = self._new_segment()
            self._event("synthetic", reason="no playable clip" if self.items else "synthetic source")
        else:
            self._anchor = None
        dt = 1.0 / float(getattr(self._synth, "fps", 30.0) or 30.0)
        t_end = None
        while not self._halt.is_set():
            f = self._synth.read()
            t_play = self._synth_base + f.t
            if t_end is None:
                t_end = t_play + seconds
            self._t_last = t_play
            self._on_time(t_play, dt, droppable=False)    # generating costs the same, so never drop
            if not self._wait(t_play):
                break
            self._publish(f.image, t_play, None, f.t, 1.0)
            if t_play >= t_end:
                break

    def _close_synthetic(self) -> None:
        if self._synth is not None:
            try:
                self._synth.close()
            except Exception:
                pass
            self._synth = None
            self._end_segment(1.0 / 30.0)


def _default_synthetic():
    from wfglink.io.synthetic_live import SyntheticLiveSource

    return SyntheticLiveSource(seed=1, realtime=False)
