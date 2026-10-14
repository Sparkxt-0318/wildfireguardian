"""A deterministic camera-in-the-loop simulator: the iPhone filming the iPad, without either.

LoopSimSource is a Source (open, read, close) that plays a prepared booth clip
(booth-prep output `<stem>_hold{h}.mp4`) on a simulated tablet panel and films it with a
simulated phone camera. It exists so that the booth path (rectification, frame codes,
clean-frame yield, fallback chain) can be exercised here, offscreen, before sitting 2.

The model, in the order the light travels:

1. Video player. The clip plays at its own frame rate (30 fps for booth-prep files) and
   loops. Video frame j shows source frame j // hold (booth-prep repeats every source
   frame `hold` times), so decoded frames are cached once per source frame.
2. Panel. The panel refreshes at panel_hz (60). Refresh n shows video frame
   floor(n * video_fps / panel_hz), so every video frame stays on for the refreshes it
   covers (2 refreshes for a 30 fps clip). Each refresh is written row by row: the scan
   moves across the panel in `scan` direction ("down" = top to bottom, as assumed for
   the iPad; also "up", "right", "left") over scan_s seconds (default one refresh period).
   A point at scan position phi (0 at the start of the scan, 1 at the end) therefore
   switches to new content at n / panel_hz + phi * scan_s. The panel is wider than the
   video (`panel_aspect`, the iPad Air's 2360x1640); the video is letterboxed with
   black bars, which are part of the scan.
3. Camera clock. The camera runs free at camera_fps (default 29.97, a small mismatch
   against the panel), so its sampling phase drifts slowly through the content period.
   Frame k starts its exposure at phase_s + k / camera_fps on the panel clock.
4. Exposure and readout. Every camera row integrates the panel for exp_s seconds; with a
   rolling shutter, camera row r starts r / H * readout_s later than row 0 (readout_s = 0
   is a global shutter). A camera frame that straddles a content change is a weighted
   mix of the two source frames (a blend; the Gray-coded frame index shows a gray cell).
   When the switch time differs across the picture (panel scan, rolling shutter, or
   both), the corners show different source frames (a tear). Note that the panel scan
   alone tears a short exposure: a camera frame taken during the refresh that writes new
   content sees new rows above the scan line and old rows below it. A rolling shutter
   running the same way as the scan partly cancels that; one running against it adds.
   The weights are computed exactly per panel pixel: each video frame's overlap with that
   pixel's exposure window, divided by the exposure.
5. Optics. A homography places the panel at about screen_frac (65 percent) of the camera
   width, rotated by tilt_deg and with a slight keystone (the camera is not square on).
   The panel shows black_dn to white_dn (an LCD in a dark hood never reaches 0), framed by
   a dark bezel on a black cloth. A Gaussian defocus of defocus_px camera pixels follows.
6. Sensor. An optional static glare gradient (glare_dn at its brightest corner) adds to
   the light; a slow auto-exposure gain drift (ae_amp, ae_period_s) multiplies it; then
   sensor noise with a read part and a shot part (sigma^2 = read^2 + shot * signal),
   drawn from a seeded noise bank so every run is identical.
7. Faults. An optional FaultScript (as in wfglink.io.fake: stall, freeze, disconnect,
   fail_open) runs on its own clock: `clock` (default time.monotonic) in seconds since
   `epoch` (default the first open). Pass one epoch to every instance a SourceChain
   builds, so a disconnect window is the same wall-clock window across reconnects.

Timing. With realtime=False (tests) every read() returns the next camera frame at once.
With realtime=True, read() waits until the frame's exposure and readout end on the
`clock`, and frames the consumer was too slow to take are dropped, like a real camera;
the panel keeps playing on the shared epoch while the camera is unplugged.

Each frame carries ground truth in frame.meta["loopsim"]: the exposure start on the
panel clock, the source frames that contributed with their mean weight, and whether any
pixel was mixed (blend) or the dominant source differed across the screen (tear).

The simulator is deliberately simple where the booth analysis does not care: no LCD
response time, no colour crosstalk, no lens distortion, no compression.
"""
from __future__ import annotations

import math
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from wfglink.io.fake import FaultScript
from wfglink.io.frames import Frame
from wfglink.io.sources import Source, SourceError

SCANS = ("down", "up", "right", "left")


def hold_from_name(path: str | Path) -> int:
    """Hold factor from a booth-prep file name (`<stem>_hold{h}.mp4`), else 1."""
    m = re.search(r"_hold(\d+)$", Path(path).stem)
    return int(m.group(1)) if m else 1


class ClipFrames:
    """Decoded source frames of a clip, by source index, with the clip's timing.

    Small clips are decoded once and kept (shared between instances through a module
    cache, so a reconnecting source does not decode again). Clips larger than budget_mb
    are decoded as a stream that keeps only the last few frames; the simulator reads
    forward, so it restarts the decoder only when the clip loops.
    """

    def __init__(self, path: str | Path, hold: int, budget_mb: float = 600.0):
        import av

        self.path = Path(path)
        self.hold = max(1, int(hold))
        if not self.path.exists():
            raise SourceError(f"loopsim: clip not found: {self.path}")
        with av.open(str(self.path)) as c:
            st = c.streams.video[0]
            rate = st.average_rate or st.guessed_rate
            self.video_fps = float(rate) if rate else 30.0
            self.width, self.height = st.codec_context.width, st.codec_context.height
            n = int(st.frames or 0)
            if n <= 0:
                n = sum(1 for p in c.demux(st) if p.size)
        if n <= 0:
            raise SourceError(f"loopsim: no video frames in {self.path}")
        self.n_video = n
        self.n_source = int(math.ceil(n / self.hold))
        self.keep_all = self.n_source * self.width * self.height * 3 <= budget_mb * 1e6
        self._frames: dict[int, np.ndarray] = {}
        self._lock = threading.Lock()
        self._container = None
        self._decoder = None
        self._next_video = 0

    def _restart(self) -> None:
        import av

        if self._container is not None:
            self._container.close()
        self._container = av.open(str(self.path))
        st = self._container.streams.video[0]
        st.thread_type = "AUTO"
        self._decoder = self._container.decode(st)
        self._next_video = 0

    def get(self, m: int) -> np.ndarray:
        """Source frame m (0 <= m < n_source) as BGR uint8 at clip resolution."""
        m = int(m) % self.n_source
        with self._lock:
            img = self._frames.get(m)
            if img is not None:
                return img
            want = m * self.hold
            if self._decoder is None or want < self._next_video:
                self._restart()
            last = None
            while self._next_video <= want:
                try:
                    vf = next(self._decoder)
                except StopIteration:
                    break
                j = self._next_video
                self._next_video += 1
                if j % self.hold == 0:
                    last = vf.to_ndarray(format="bgr24")
                    self._frames[j // self.hold] = last
            if not self.keep_all:
                for k in [k for k in self._frames if k < m - 3 or k > m + 3]:
                    del self._frames[k]
            img = self._frames.get(m)
            if img is None:              # declared count was longer than the stream
                img = last if last is not None else np.zeros((self.height, self.width, 3), np.uint8)
                self._frames[m] = img
            if self.keep_all and len(self._frames) >= self.n_source and self._container is not None:
                self._container.close()
                self._container, self._decoder = None, None
            return img


_CLIP_CACHE: dict[tuple, ClipFrames] = {}
_CACHE_LOCK = threading.Lock()


def clip_frames(path: str | Path, hold: int, budget_mb: float = 600.0) -> ClipFrames:
    """Shared ClipFrames for small clips (keyed by path, size and mtime); a private one otherwise."""
    p = Path(path).resolve()
    try:
        st = p.stat()
    except OSError as exc:
        raise SourceError(f"loopsim: clip not found: {p}") from exc
    key = (str(p), st.st_size, st.st_mtime_ns, int(hold), float(budget_mb))
    with _CACHE_LOCK:
        cf = _CLIP_CACHE.get(key)
        if cf is not None:
            return cf
    cf = ClipFrames(p, hold, budget_mb)
    if cf.keep_all:
        with _CACHE_LOCK:
            while len(_CLIP_CACHE) >= 2:
                _CLIP_CACHE.pop(next(iter(_CLIP_CACHE)))
            _CLIP_CACHE[key] = cf
    return cf


class LoopSimSource(Source):
    """A simulated phone camera filming a tablet that loops a prepared booth clip."""

    kind = "camera"
    is_live = True

    def __init__(self, clip: str | Path, *, hold: int | None = None, panel_hz: float = 60.0,
                 scan: str = "down", scan_s: float | None = None, panel_aspect: float = 2360 / 1640,
                 camera_fps: float = 29.97, exp_s: float = 1 / 120, readout_s: float = 0.0,
                 size: tuple[int, int] = (1920, 1080), screen_frac: float = 0.65, tilt_deg: float = 2.0,
                 keystone: float = 0.04, center: tuple[float, float] = (0.52, 0.49),
                 black_dn: float = 10.0, white_dn: float = 225.0, defocus_px: float = 0.9,
                 read_noise_dn: float = 1.5, shot_noise: float = 0.06, ae_amp: float = 0.05,
                 ae_period_s: float = 23.0, glare_dn: float = 0.0, phase_s: float | None = None,
                 faults: FaultScript | None = None, clock: Callable[[], float] | None = None,
                 epoch: float | None = None, realtime: bool = False, seed: int = 0,
                 cache_mb: float = 600.0, label: str = "loopsim"):
        super().__init__(label)
        if scan not in SCANS:
            raise ValueError(f"scan must be one of {SCANS}")
        if exp_s <= 0 or exp_s > 1.0 / camera_fps + 1e-9:
            raise ValueError("exp_s must be positive and at most one camera frame period")
        self.clip = Path(clip)
        self.hold = int(hold) if hold else hold_from_name(self.clip)
        self.panel_hz = float(panel_hz)
        self.scan = scan
        self.scan_s = (1.0 / self.panel_hz) if scan_s is None else float(scan_s)
        self.panel_aspect = float(panel_aspect)
        self.camera_fps = float(camera_fps)
        self.exp_s = float(exp_s)
        self.readout_s = float(readout_s)
        self.size = (int(size[0]), int(size[1]))
        self.screen_frac = float(screen_frac)
        self.tilt_deg = float(tilt_deg)
        self.keystone = float(keystone)
        self.center = (float(center[0]), float(center[1]))
        self.black_dn, self.white_dn = float(black_dn), float(white_dn)
        self.defocus_px = float(defocus_px)
        self.read_noise_dn = float(read_noise_dn)
        self.shot_noise = float(shot_noise)
        self.ae_amp, self.ae_period_s = float(ae_amp), float(ae_period_s)
        self.glare_dn = float(glare_dn)
        self.faults = faults or FaultScript()
        self.clock = clock or time.monotonic
        if epoch is not None:
            self._epoch = float(epoch)
        self.realtime = bool(realtime)
        self.seed = int(seed)
        self.cache_mb = float(cache_mb)
        rng = np.random.default_rng(self.seed)
        self.phase_s = float(rng.uniform(0.0, 1.0)) if phase_s is None else float(phase_s)
        self._ae_phase = float(rng.uniform(0, 2 * math.pi))
        self._rng_seed = int(rng.integers(0, 2 ** 31 - 1))
        self._clip: ClipFrames | None = None
        self._k: int | None = None          # camera frame counter on the panel clock grid
        self._t_open_cam: float | None = None
        self._last: Frame | None = None
        self.opens = 0

    # Geometry and static layers (built once per instance) ---------------------------------
    def _build(self, cf: ClipFrames) -> None:
        cw, ch = self.size
        vw, vh = cf.width, cf.height
        # Panel coordinates: the video fills the panel width, letterboxed vertically.
        pw = float(vw)
        ph = max(pw / self.panel_aspect, float(vh))
        y_off = 0.5 * (ph - vh)
        A = np.array([[1, 0, 0], [0, 1, y_off], [0, 0, 1]], np.float64)       # video -> panel
        sw = self.screen_frac * cw
        sh = sw * ph / pw
        cx, cy = self.center[0] * cw, self.center[1] * ch
        k = self.keystone
        quad = np.array([[-sw / 2, -sh / 2 * (1 + k / 2)], [sw / 2, -sh / 2 * (1 - k / 2)],
                         [sw / 2, sh / 2 * (1 - k / 2)], [-sw / 2, sh / 2 * (1 + k / 2)]])
        a = math.radians(self.tilt_deg)
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        quad = quad @ R.T + [cx, cy]
        panel_rect = np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]])
        Hs = cv2.getPerspectiveTransform(panel_rect, quad.astype(np.float32))  # panel -> camera
        self.H_panel = Hs
        self.H = Hs @ A                                                        # video -> camera
        # Scan phase (0..1) and rolling-shutter delay per video pixel, as one offset map:
        # pixel switches at n / hz + phi * scan_s; its exposure starts at s_k + delay.
        ys = (np.arange(vh, dtype=np.float64) + 0.5 + y_off) / ph
        xs = (np.arange(vw, dtype=np.float64) + 0.5) / pw
        if self.scan == "down":
            phi = ys[:, None]
        elif self.scan == "up":
            phi = (1.0 - ys)[:, None]
        elif self.scan == "right":
            phi = xs[None, :]
        else:
            phi = (1.0 - xs)[None, :]
        offset = -phi * self.scan_s
        if self.readout_s > 0:
            gx, gy = np.meshgrid(np.arange(vw) + 0.5, np.arange(vh) + 0.5)
            pts = np.stack([gx, gy, np.ones_like(gx)], axis=-1) @ self.H.T
            row = pts[..., 1] / pts[..., 2]
            offset = offset + np.clip(row / ch, 0, 1) * self.readout_s
        self._offset = np.asarray(offset, np.float64)
        self._off_min, self._off_max = float(self._offset.min()), float(self._offset.max())
        # Static light outside the video: cloth, bezel and the letterbox bars (panel black).
        rng = np.random.default_rng(self.seed + 1)
        tex = cv2.GaussianBlur(rng.normal(0, 1, (ch // 16, cw // 16)).astype(np.float32), (0, 0), 2)
        tex = cv2.resize(tex, (cw, ch), interpolation=cv2.INTER_CUBIC)
        bg = 5.0 + 1.5 * tex
        bezel = quad + (quad - quad.mean(axis=0)) * 0.035
        cv2.fillConvexPoly(bg, np.round(bezel * 16).astype(np.int32), 20.0, lineType=cv2.LINE_AA, shift=4)
        cv2.fillConvexPoly(bg, np.round(quad * 16).astype(np.int32), self.black_dn, lineType=cv2.LINE_AA, shift=4)
        ones = np.ones((vh, vw), np.float32)
        vmask = cv2.warpPerspective(ones, self.H, (cw, ch), flags=cv2.INTER_LINEAR, borderValue=0)
        outside = bg * (1.0 - vmask)
        if self.glare_dn > 0:
            gy, gx = np.mgrid[0:ch, 0:cw].astype(np.float32)
            g = np.clip(1.0 - (gx / cw * 0.7 + gy / ch * 0.3), 0, 1) ** 2   # brightest at the top left
            outside = outside + self.glare_dn * g
        self._outside = np.repeat(outside[:, :, None], 3, axis=2).astype(np.float32)
        x, y, w, h = cv2.boundingRect(np.round(bezel).astype(np.int32))
        pad = int(4 * self.defocus_px) + 2
        self._roi = (max(0, x - pad), max(0, y - pad), min(cw, x + w + pad), min(ch, y + h + pad))
        x0, y0, x1, y1 = self._roi
        H_roi = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float64) @ self.H
        # Precomputed fixed-point remap tables: twice as fast as warpPerspective per frame.
        Hi = np.linalg.inv(H_roi)
        gx, gy = np.meshgrid(np.arange(x1 - x0, dtype=np.float64), np.arange(y1 - y0, dtype=np.float64))
        d = Hi[2, 0] * gx + Hi[2, 1] * gy + Hi[2, 2]
        mx = ((Hi[0, 0] * gx + Hi[0, 1] * gy + Hi[0, 2]) / d).astype(np.float32)
        my = ((Hi[1, 0] * gx + Hi[1, 1] * gy + Hi[1, 2]) / d).astype(np.float32)
        self._maps = cv2.convertMaps(mx, my, cv2.CV_16SC2)
        self._outside_by_gain: dict[int, np.ndarray] = {}
        # Noise bank: one 3-channel int16 plane (unit sigma = 64) larger than the frame; each
        # frame takes a shifted window, so the noise is seeded, fresh-looking and cheap.
        nrng = np.random.default_rng(self._rng_seed)
        self._bank_pad = 64
        bank = nrng.standard_normal((ch + self._bank_pad, cw + self._bank_pad, 3)) * 64.0
        self._bank = np.clip(np.round(bank), -32000, 32000).astype(np.int16)
        self._nrng = np.random.default_rng(self._rng_seed + 7)
        levels = np.arange(256, dtype=np.float64)
        sigma = np.sqrt(self.read_noise_dn ** 2 + self.shot_noise * levels)
        self._sigma_lut = np.round(sigma * 16.0).astype(np.int16)    # x16; product scaled by 1/1024

    # Timing ----------------------------------------------------------------------------------
    def _video_start(self, j: int) -> float:
        """Content time at which video frame j (absolute, not wrapped) first appears."""
        n = math.ceil(j * self.panel_hz / self._clip.video_fps - 1e-9)
        return n / self.panel_hz

    def _video_at(self, u: float) -> int:
        n = math.floor(u * self.panel_hz + 1e-9)
        return math.floor(n * self._clip.video_fps / self.panel_hz + 1e-9)

    def _weights(self, s: float) -> dict[int, np.ndarray | float]:
        """Weight of every contributing source frame for the exposure starting at s."""
        e = self.exp_s
        a = s + self._offset                       # per pixel exposure start, content time
        j0 = self._video_at(s + self._off_min)
        j1 = self._video_at(s + self._off_max + e)
        out: dict[int, np.ndarray | float] = {}
        cf = self._clip
        for j in range(j0, j1 + 1):
            lo, hi = self._video_start(j), self._video_start(j + 1)
            w = (np.minimum(a + e, hi) - np.maximum(a, lo)).clip(0, None) / e
            if not np.any(w > 1e-6):
                continue
            m = (j % cf.n_video) // cf.hold
            out[m] = out.get(m, 0.0) + w
        return out

    def _ae_gain(self, s: float) -> float:
        if self.ae_amp <= 0:
            return 1.0
        p = 2 * math.pi * s / max(self.ae_period_s, 1e-3) + self._ae_phase
        return 1.0 + self.ae_amp * (0.8 * math.sin(p) + 0.2 * math.sin(2.7 * p + 1.3))

    # Source interface ------------------------------------------------------------------------
    def _fault_t(self) -> float:
        return self.clock() - self._epoch

    def open(self) -> None:
        now = self.clock()
        if not hasattr(self, "_epoch"):
            self._epoch = now
        t = now - self._epoch
        if self.faults.active("fail_open", t) or self.faults.active("disconnect", t):
            raise SourceError(f"{self.name}: device not available")
        if self._clip is None:
            self._clip = clip_frames(self.clip, self.hold, self.cache_mb)
            self._build(self._clip)
        self._k = None
        self._t_open_cam = None
        self.opens += 1
        cf = self._clip
        self.info = {"backend": "loopsim", "clip": str(self.clip), "hold": cf.hold, "width": self.size[0],
                     "height": self.size[1], "fps": self.camera_fps, "exp_s": self.exp_s,
                     "readout_s": self.readout_s, "panel_hz": self.panel_hz, "scan": self.scan,
                     "scan_s": self.scan_s, "video_fps": cf.video_fps, "n_video": cf.n_video,
                     "n_source": cf.n_source, "loop_s": cf.n_video / cf.video_fps, "phase_s": self.phase_s,
                     "realtime": self.realtime, "seed": self.seed}

    def _next_k(self) -> int:
        if not self.realtime:
            return 0 if self._k is None else self._k + 1
        fps = self.camera_fps
        lag = self.exp_s + self.readout_s
        now = self.clock() - self._epoch
        latest = math.floor((now - self.phase_s - lag) * fps)
        k = latest if self._k is None else max(self._k + 1, latest)
        ready = self.phase_s + k / fps + lag
        if ready > now:
            time.sleep(min(ready - now, 1.0))
        return k

    def read(self) -> Frame | None:
        if self._clip is None:
            raise SourceError("source not opened")
        t = self._fault_t()
        if self.faults.active("disconnect", t):
            raise SourceError(f"{self.name}: device disconnected")
        if self.faults.active("stall", t):
            if self.realtime:
                time.sleep(1.0 / self.camera_fps)
            return None
        if self.faults.active("freeze", t) and self._last is not None:
            f = self._last
            if self.realtime:
                time.sleep(1.0 / self.camera_fps)
            return Frame(f.image.copy(), f.t, self._next_index(), time.monotonic(), dict(f.meta, frozen=True))
        k = self._next_k()
        self._k = k
        s = self.phase_s + k / self.camera_fps
        img, truth = self.render(s)
        if self._t_open_cam is None:
            self._t_open_cam = s
        f = Frame(img, s - self._t_open_cam, self._next_index(), time.monotonic(),
                  {"source": self.name, "backend": "loopsim", "loopsim": truth})
        self._last = f
        return f

    def close(self) -> None:
        self._last = None

    # Rendering -------------------------------------------------------------------------------
    def render(self, s: float) -> tuple[np.ndarray, dict[str, Any]]:
        """The camera frame whose exposure starts at panel time s, and its ground truth."""
        cf = self._clip
        weights = self._weights(s)
        if len(weights) == 1:
            (m, _), = weights.items()
            panel = cf.get(m)
            mixed, torn = False, False
            truth_src = {int(m): 1.0}
        else:
            acc = None
            dom_w, dom_m = None, None
            truth_src = {}
            mixed = False
            for m, w in weights.items():
                wf = np.broadcast_to(np.asarray(w, np.float32), cf.get(m).shape[:2])
                term = cf.get(m).astype(np.float32) * wf[:, :, None]
                acc = term if acc is None else acc + term
                truth_src[int(m)] = round(float(wf.mean()), 4)
                mixed = mixed or bool(np.any((wf > 0.02) & (wf < 0.98)))
                if dom_w is None:
                    dom_w, dom_m = wf.copy(), np.full(wf.shape, m, np.int32)
                else:
                    better = wf > dom_w
                    dom_w = np.where(better, wf, dom_w)
                    dom_m = np.where(better, m, dom_m)
            torn = bool(dom_m.min() != dom_m.max())
            panel = cv2.convertScaleAbs(acc)   # the integrated light, rounded to 8 bits
        img = self._camera(panel, s)
        truth = {"s": round(s, 6), "k": self._k, "sources": truth_src, "mixed": mixed, "torn": torn,
                 "video_index": self._video_at(s + self.exp_s / 2) % cf.n_video}
        return img, truth

    def _outside_at(self, gain: float) -> np.ndarray:
        """The static light around the video (cloth, bezel, bars, glare) at this gain, in 2 percent steps."""
        key = int(round(gain * 50))
        img = self._outside_by_gain.get(key)
        if img is None:
            if len(self._outside_by_gain) >= 8:
                self._outside_by_gain.pop(next(iter(self._outside_by_gain)))
            img = cv2.convertScaleAbs(self._outside, alpha=key / 50.0)
            self._outside_by_gain[key] = img
        return img

    def _camera(self, panel: np.ndarray, s: float) -> np.ndarray:
        """Panel light (uint8, video pixels) to a camera frame: optics, gain, glare, noise."""
        cw, ch = self.size
        x0, y0, x1, y1 = self._roi
        gain = self._ae_gain(s)
        lut = np.clip((self.black_dn + (self.white_dn - self.black_dn) * np.arange(256) / 255.0) * gain, 0, 255)
        lit = cv2.LUT(panel, np.round(lut).astype(np.uint8))
        screen = cv2.remap(lit, self._maps[0], self._maps[1], cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        cam = self._outside_at(gain).copy()
        roi = cam[y0:y1, x0:x1]
        cv2.add(roi, screen, dst=roi)
        if self.defocus_px > 0:
            cv2.GaussianBlur(roi, (0, 0), self.defocus_px, dst=roi)
        if self.read_noise_dn > 0 or self.shot_noise > 0:
            dx, dy = (int(v) for v in self._nrng.integers(0, self._bank_pad, 2))
            sigma = cv2.LUT(cam, self._sigma_lut)
            noise = cv2.multiply(self._bank[dy:dy + ch, dx:dx + cw], sigma, scale=1.0 / 1024.0, dtype=cv2.CV_16S)
            cam = cv2.add(cam, noise, dtype=cv2.CV_8U)
        return cam
