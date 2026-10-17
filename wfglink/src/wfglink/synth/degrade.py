"""Camera model and video degradations for synthetic clips.

The scene arrives as linear intensity (DN on a 0 to 255 scale at gain 1 and the clip's
reference exposure, B G R). Per frame, in this order:

1. Haze (Koschmieder): I = J t + A (1 - t), t = exp(-beta z), with a per-pixel depth map z
   that is either constant or a simple ground plane (rows below the horizon at
   z = camera_height focal_px / (y - y_horizon), the sky at z_max). The background and
   flames use the depth map; embers use either the depth map or their own constant depth.
   (Applied by the generator when composing the scene; the functions live here.)
2. Optional pillbox defocus (optics, mismatch effect).
3. Exposure and gain: I *= gain x gain_ratio x illumination x exposure_s / exposure_ref.
   gain_ratio models an exposure step with automatic gain compensation; illumination is
   the global flicker 1 + a sin(2 pi f t + phi).
4. Optional blooming: energy above the full-well level spills into neighbours (an
   isotropic Gaussian part plus a vertical smear part).
5. Noise: shot noise with variance I x gain_eff / electrons_per_dn (electrons_per_dn is
   given at gain 1) plus Gaussian read noise in DN. "gaussian" mode uses the normal
   approximation of the Poisson law (fast, accurate above about 10 electrons); "poisson"
   draws exact Poisson electron counts (slower). The Gaussian noise of the three channels
   is partly correlated (channel_noise_corr), as after demosaicking and chroma denoise.
6. Gamma encoding 255 (I / 255)^(1 / gamma) with gamma 2.2.
7. Optional unsharp-mask sharpening and temporal denoise (exponential blend with the
   previous output frame), as a phone image processor would do.
8. Clipping and rounding to 8 bits.

Then the frames are compressed with PyAV: H.264 (libx264, yuv420p, a given CRF) or H.265
(libx265, only when this PyAV build has the encoder). Presentation timestamps are written
exactly (90 kHz time base by default), so variable frame intervals survive.

Timing mismatch effects (FrameTiming): jittered frame intervals, duplicated frames (a slot
that repeats the previous image) and an exposure step at a given time. The rolling shutter
is handled by the renderer (row-dependent sample times).

Random numbers are drawn from np.random.default_rng([seed, stream, frame, block]) in row
blocks, so results do not depend on thread scheduling.
"""
from __future__ import annotations

import io
import math
import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import av
import cv2
import numpy as np

LUMA_BGR = np.array([0.114, 0.587, 0.299])
NOISE_STREAM = 301
TIMING_STREAM = 302
FLICKER_STREAM = 303

_POOL: ThreadPoolExecutor | None = None


def _pool() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 1)))
    return _POOL


def _row_blocks(h: int, n: int) -> list[tuple[int, int]]:
    edges = np.linspace(0, h, n + 1).astype(int)
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b > a]


# Haze -------------------------------------------------------------------------------------
def depth_map(cfg: Mapping[str, Any] | None, frame_size: Sequence[int]) -> np.ndarray:
    """Per-pixel depth (m), (H, W) float32. mode "constant" (depth_m) or "ground_plane"
    (camera_height_m, focal_px, horizon_frac, z_max_m)."""
    cfg = cfg or {}
    w, h = int(frame_size[0]), int(frame_size[1])
    mode = str(cfg.get("mode", "constant"))
    if mode == "constant":
        return np.full((h, w), float(cfg.get("depth_m", 30.0)), np.float32)
    if mode != "ground_plane":
        raise ValueError(f"unknown depth mode {mode!r}")
    yh = float(cfg.get("horizon_frac", 0.6)) * h
    zmax = float(cfg.get("z_max_m", 500.0))
    cam_h = float(cfg.get("camera_height_m", 10.0))
    f = float(cfg.get("focal_px", 1000.0))
    dy = np.arange(h, dtype=np.float64) - yh
    z = np.where(dy > 0, cam_h * f / np.where(dy > 0, dy, 1.0), zmax)
    z = np.minimum(z, zmax)
    return np.broadcast_to(z[:, None], (h, w)).astype(np.float32)


def transmission(depth: np.ndarray | float, beta_per_m: float) -> np.ndarray | float:
    """Koschmieder transmission t = exp(-beta z)."""
    if isinstance(depth, np.ndarray):
        return np.exp(-float(beta_per_m) * depth).astype(np.float32)
    return float(math.exp(-float(beta_per_m) * float(depth)))


def apply_haze(j: np.ndarray, t: np.ndarray | float, airlight: Sequence[float]) -> np.ndarray:
    """I = J t + A (1 - t) for a (H, W, 3) image, per-pixel or scalar t, airlight A (B, G, R)."""
    a = np.asarray(airlight, dtype=np.float32)
    if isinstance(t, np.ndarray):
        tt = t[..., None] if t.ndim == 2 else t
        return (j * tt + a * (1.0 - tt)).astype(np.float32)
    return (j * float(t) + a * (1.0 - float(t))).astype(np.float32)


# Optical and sensor effects ---------------------------------------------------------------
def pillbox_kernel(radius_px: float, supersample: int = 8) -> np.ndarray:
    """Normalised disk kernel of the given radius, anti-aliased by supersampling."""
    r = float(radius_px)
    if r <= 0:
        return np.ones((1, 1), np.float32)
    n = int(math.ceil(r))
    k = 2 * n + 1
    s = supersample
    off = (np.arange(k * s) + 0.5) / s - (n + 0.5)
    yy, xx = np.meshgrid(off, off, indexing="ij")
    inside = (xx ** 2 + yy ** 2 <= r * r).astype(np.float64)
    ker = inside.reshape(k, s, k, s).mean(axis=(1, 3))
    return (ker / ker.sum()).astype(np.float32)


def defocus(img: np.ndarray, radius_px: float) -> np.ndarray:
    """Pillbox (uniform disk) defocus blur; conserves flux away from the border."""
    if radius_px <= 0:
        return img
    return cv2.filter2D(img, -1, pillbox_kernel(radius_px), borderType=cv2.BORDER_REFLECT)


def bloom(img: np.ndarray, full_well_dn: float, sigma_px: float = 2.5, vertical_frac: float = 0.5,
          vertical_len_px: int = 21) -> np.ndarray:
    """Spill energy above the full-well level into neighbouring pixels (total energy kept)."""
    excess = np.maximum(img - full_well_dn, 0.0).astype(np.float32)
    if not excess.any():
        return img
    out = np.minimum(img, full_well_dn).astype(np.float32)
    vf = float(np.clip(vertical_frac, 0.0, 1.0))
    if vf < 1:
        out += (1 - vf) * cv2.GaussianBlur(excess, (0, 0), float(sigma_px), borderType=cv2.BORDER_CONSTANT)
    if vf > 0:
        L = max(1, int(vertical_len_px)) | 1
        out += vf * cv2.blur(excess, (1, L), borderType=cv2.BORDER_CONSTANT)
    return out


def add_noise(img: np.ndarray, *, gain: float, electrons_per_dn: float, read_noise_dn: float,
              seed: Sequence[int], mode: str = "gaussian", channel_corr: float = 0.0,
              blocks: int = 4) -> np.ndarray:
    """Shot noise (variance I gain / electrons_per_dn) plus Gaussian read noise, in DN.

    channel_corr (0 to 1) correlates the Gaussian noise of the three channels, as
    demosaicking and the chroma denoise of a camera do; per-channel variances are kept.
    In "poisson" mode only the read noise is correlated.
    """
    out = np.empty_like(img, dtype=np.float32)
    k = float(gain) / float(electrons_per_dn)
    r2 = float(read_noise_dn) ** 2
    rho = float(np.clip(channel_corr, 0.0, 1.0))
    a_ind, a_com = np.float32(math.sqrt(1.0 - rho)), np.float32(math.sqrt(rho))

    def work(i_ab: tuple[int, tuple[int, int]]) -> None:
        i, (a, b) = i_ab
        rng = np.random.default_rng([*seed, i])
        src = np.maximum(img[a:b], 0.0)
        z = rng.standard_normal(src.shape, dtype=np.float32)
        if rho > 0 and src.ndim == 3:
            z *= a_ind
            z += a_com * rng.standard_normal(src.shape[:-1] + (1,), dtype=np.float32)
        if mode == "poisson":
            e = rng.poisson(src.astype(np.float64) / k).astype(np.float32)
            np.multiply(e, k, out=out[a:b])
            out[a:b] += float(read_noise_dn) * z
        else:
            sd = src * np.float32(k)
            sd += np.float32(r2)
            np.sqrt(sd, out=sd)
            sd *= z
            np.add(img[a:b], sd, out=out[a:b])

    list(_pool().map(work, enumerate(_row_blocks(img.shape[0], blocks))))
    return out


def gamma_encode(img: np.ndarray, gamma: float = 2.2, blocks: int = 4) -> np.ndarray:
    """255 (I / 255)^(1 / gamma), negative values clipped to 0. Float32 output."""
    out = np.empty_like(img, dtype=np.float32)
    inv = 1.0 / float(gamma)

    def work(ab: tuple[int, int]) -> None:
        a, b = ab
        x = np.maximum(img[a:b], 0.0) * np.float32(1.0 / 255.0)
        black = x == 0.0
        cv2.pow(x, inv, dst=x)
        x[black] = 0.0           # some SIMD pow implementations return a tiny positive value at zero
        np.multiply(x, np.float32(255.0), out=out[a:b])

    list(_pool().map(work, _row_blocks(img.shape[0], blocks)))
    return out


def gamma_decode(enc: np.ndarray, gamma: float = 2.2) -> np.ndarray:
    """Inverse of gamma_encode for 0 to 255 values."""
    return 255.0 * (np.clip(np.asarray(enc, dtype=np.float64), 0, 255) / 255.0) ** float(gamma)


def unsharp(img: np.ndarray, amount: float, sigma_px: float = 1.0) -> np.ndarray:
    """Unsharp-mask sharpening: I + amount (I - blur(I))."""
    if amount <= 0:
        return img
    blur = cv2.GaussianBlur(img, (0, 0), float(sigma_px))
    return cv2.addWeighted(img, 1.0 + float(amount), blur, -float(amount), 0.0)


def quantize(img: np.ndarray) -> np.ndarray:
    """Round to nearest and clip to uint8 (OpenCV saturating conversion of a non-negative image)."""
    return cv2.convertScaleAbs(cv2.max(np.ascontiguousarray(img, dtype=np.float32), 0.0))


# Timing -----------------------------------------------------------------------------------
@dataclass
class FrameTiming:
    """Exposure timing of every frame slot (seconds)."""

    t_start: np.ndarray
    exposure_s: np.ndarray
    duplicate: np.ndarray
    gain_ratio: np.ndarray
    illumination: np.ndarray
    exposure_ref_s: float

    @property
    def n(self) -> int:
        return int(self.t_start.shape[0])

    @property
    def t_end(self) -> np.ndarray:
        return self.t_start + self.exposure_s

    @property
    def t_mid(self) -> np.ndarray:
        return self.t_start + 0.5 * self.exposure_s


def make_timing(cfg: Mapping[str, Any], seed: int) -> FrameTiming:
    """Frame start times, exposures, duplicates, gain steps and global flicker of a clip.

    Keys: fps, duration_s, duty, timing.{jitter_frac, duplicate_prob, exposure_step.{t_s,
    factor, gain_compensate}}, camera.flicker.{amp, freq_hz}. Intervals are
    (1 / fps) (1 + jitter_frac U(-1, 1)); exposures are duty / fps (times the step factor
    after t_s) and never longer than the interval to the next frame. With gain_compensate
    the camera gain rises by 1 / factor so the image brightness stays the same.
    """
    fps = float(cfg.get("fps", 30.0))
    n = int(round(float(cfg.get("duration_s", 5.0)) * fps))
    dt = 1.0 / fps
    tc = cfg.get("timing", {}) or {}
    rng = np.random.default_rng([int(seed), TIMING_STREAM])
    jit = float(tc.get("jitter_frac", 0.0))
    u = rng.uniform(-1.0, 1.0, n)
    intervals = dt * (1.0 + jit * u) if jit > 0 else np.full(n, dt)
    t_start = np.concatenate([[0.0], np.cumsum(intervals[:-1])]) if n else np.zeros(0)
    exp_ref = float(cfg.get("duty", 0.5)) * dt
    step = tc.get("exposure_step") or {}
    factor = np.ones(n)
    gain_ratio = np.ones(n)
    if step.get("t_s") is not None:
        after = t_start >= float(step["t_s"])
        f = float(step.get("factor", 0.5))
        factor[after] = f
        if step.get("gain_compensate", True):
            gain_ratio[after] = 1.0 / f
    exposure = np.minimum(exp_ref * factor, intervals)
    dup = rng.uniform(0, 1, n) < float(tc.get("duplicate_prob", 0.0))
    if n:
        dup[0] = False
    fl = (cfg.get("camera", {}) or {}).get("flicker") or {}
    frng = np.random.default_rng([int(seed), FLICKER_STREAM])
    phase = frng.uniform(0, 2 * np.pi)
    amp = float(fl.get("amp", 0.0))
    illum = 1.0 + amp * np.sin(2 * np.pi * float(fl.get("freq_hz", 2.0)) * (t_start + 0.5 * exposure) + phase)
    return FrameTiming(t_start=t_start, exposure_s=exposure, duplicate=dup, gain_ratio=gain_ratio,
                       illumination=illum, exposure_ref_s=exp_ref)


# Camera -----------------------------------------------------------------------------------
class Camera:
    """Stateful per-clip camera: exposure scaling, bloom, noise, gamma, sharpening, denoise."""

    def __init__(self, cfg: Mapping[str, Any], seed: int):
        cam = cfg.get("camera", {}) or {}
        mm = cfg.get("mismatch", {}) or {}
        self.seed = int(seed)
        self.gain = float(cam.get("gain", 1.0))
        self.electrons_per_dn = float(cam.get("electrons_per_dn", 4.0))
        self.read_noise_dn = float(cam.get("read_noise_dn", 0.4))
        self.channel_corr = float(cam.get("channel_noise_corr", 0.5))
        self.shot_noise = str(cam.get("shot_noise", "gaussian"))
        self.gamma = float(cam.get("gamma", 2.2))
        self.defocus_px = float(mm.get("defocus_radius_px", 0.0))
        sh = mm.get("sharpen") or {}
        self.sharpen_amount = float(sh.get("amount", 0.0))
        self.sharpen_sigma = float(sh.get("sigma_px", 1.0))
        self.denoise_alpha = float(mm.get("denoise_alpha", 1.0))
        bl = mm.get("bloom") or {}
        self.bloom = bool(bl.get("enabled", False))
        self.full_well = float(bl.get("full_well_dn", 255.0))
        self.bloom_sigma = float(bl.get("sigma_px", 2.5))
        self.bloom_vfrac = float(bl.get("vertical_frac", 0.5))
        self.bloom_vlen = int(bl.get("vertical_len_px", 21))
        self._prev: np.ndarray | None = None

    def scale(self, timing: FrameTiming, i: int) -> float:
        """Output DN per scene DN for frame i."""
        return (self.gain * float(timing.gain_ratio[i]) * float(timing.illumination[i])
                * float(timing.exposure_s[i]) / timing.exposure_ref_s)

    def gain_eff(self, timing: FrameTiming, i: int) -> float:
        return self.gain * float(timing.gain_ratio[i])

    def luma_noise_sigma(self, background: np.ndarray, scale: float, gain_eff: float) -> np.ndarray:
        """BT.601 luma noise sigma (linear DN) over a noise-free scene `background` (scene DN,
        B G R in the last axis) for a frame with the given scale and effective gain.

        Channel variance: s_c^2 = B_c scale gain_eff / electrons_per_dn + read^2. With channel
        correlation rho: var = (1 - rho) sum_c w_c^2 s_c^2 + rho (sum_c w_c s_c)^2 (Gaussian
        mode); in Poisson mode only the read noise is correlated.
        """
        b = np.maximum(np.asarray(background, dtype=np.float64), 0.0)
        shot = b * (scale * gain_eff / self.electrons_per_dn)
        r2 = self.read_noise_dn ** 2
        rho = self.channel_corr
        w = LUMA_BGR
        if self.shot_noise == "poisson":
            var = shot @ (w ** 2) + r2 * ((1 - rho) * float(np.sum(w ** 2)) + rho * float(np.sum(w)) ** 2)
        else:
            sc = np.sqrt(shot + r2)
            var = (1 - rho) * ((sc ** 2) @ (w ** 2)) + rho * (sc @ w) ** 2
        return np.sqrt(var)

    def process(self, scene: np.ndarray, timing: FrameTiming, i: int) -> np.ndarray:
        """Scene (scene DN, hazed) to the 8-bit BGR frame for slot i."""
        img = defocus(scene, self.defocus_px) if self.defocus_px > 0 else scene
        img = img * np.float32(self.scale(timing, i))
        if self.bloom:
            img = bloom(img, self.full_well, self.bloom_sigma, self.bloom_vfrac, self.bloom_vlen)
        img = add_noise(img, gain=self.gain_eff(timing, i), electrons_per_dn=self.electrons_per_dn,
                        read_noise_dn=self.read_noise_dn, seed=(self.seed, NOISE_STREAM, i), mode=self.shot_noise,
                        channel_corr=self.channel_corr)
        enc = gamma_encode(img, self.gamma)
        if self.sharpen_amount > 0:
            enc = unsharp(enc, self.sharpen_amount, self.sharpen_sigma)
        if self.denoise_alpha < 1.0:
            if self._prev is not None:
                enc = cv2.addWeighted(enc, self.denoise_alpha, self._prev, 1.0 - self.denoise_alpha, 0.0)
            self._prev = enc
        return quantize(enc)


# Video I/O --------------------------------------------------------------------------------
CODECS = {"h264": "libx264", "h265": "libx265", "hevc": "libx265"}


def encoder_name(codec: str) -> str:
    """PyAV encoder for "h264" or "h265"; raises RuntimeError if this build lacks it."""
    name = CODECS.get(codec.lower(), codec)
    if name not in av.codecs_available:
        raise RuntimeError(f"PyAV {av.__version__} has no {name} encoder, so {codec} output is unavailable "
                           f"in this environment; use codec h264 instead")
    return name


def has_encoder(codec: str) -> bool:
    return CODECS.get(codec.lower(), codec) in av.codecs_available


class VideoWriter:
    """H.264 or H.265 writer with exact presentation timestamps (seconds).

    With threaded=True (default) frames are encoded on a background thread, so encoding
    overlaps with rendering the next frame (PyAV releases the GIL while encoding).
    encoder_threads fixes the encoder's own thread count (0: encoder default).
    """

    def __init__(self, path: str | Path | io.BytesIO, frame_size: Sequence[int], fps: float, *,
                 codec: str = "h264", crf: int = 23, preset: str = "medium", time_base: int = 90000,
                 container_format: str | None = None, threaded: bool = True, queue_size: int = 4,
                 encoder_threads: int = 4):
        self.name = encoder_name(codec)
        self.tb = Fraction(1, int(time_base))
        self.container = av.open(path, "w", format=container_format)
        st = self.container.add_stream(self.name, rate=Fraction(fps).limit_denominator(1001))
        st.width, st.height = int(frame_size[0]), int(frame_size[1])
        st.pix_fmt = "yuv420p"
        st.time_base = self.tb
        st.codec_context.time_base = self.tb
        # A fixed encoder thread count keeps the bitstream independent of the machine's core
        # count (x264 output depends on its number of frame threads); 0 lets the encoder choose.
        opts = {"crf": str(crf), "preset": str(preset)}
        if int(encoder_threads) > 0:
            opts["threads"] = str(int(encoder_threads))
        if self.name == "libx265":
            opts["x265-params"] = "log-level=error"
            try:
                st.codec_tag = "hvc1"
            except Exception:  # tag support differs between PyAV versions; not essential
                pass
        st.options = opts
        self.stream = st
        self._last_pts: int | None = None
        self._error: BaseException | None = None
        self._closed = False
        self._queue: queue.Queue | None = None
        self._thread: threading.Thread | None = None
        if threaded:
            self._queue = queue.Queue(maxsize=max(1, int(queue_size)))
            self._thread = threading.Thread(target=self._worker, name="wfglink-encoder", daemon=True)
            self._thread.start()

    def _encode(self, img_bgr: np.ndarray | None, pts: int | None) -> None:
        if img_bgr is None:
            packets = self.stream.encode()
        else:
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(img_bgr), format="bgr24")
            frame.pts = pts
            frame.time_base = self.tb
            packets = self.stream.encode(frame)
        for pkt in packets:
            self.container.mux(pkt)

    def _worker(self) -> None:
        assert self._queue is not None
        while True:
            item = self._queue.get()
            if item is None:
                return
            if self._error is None:
                try:
                    self._encode(*item)
                except BaseException as exc:  # reported to the caller on the next write or close
                    self._error = exc

    def write(self, img_bgr: np.ndarray, t_s: float) -> int:
        if self._error is not None:
            raise RuntimeError("video encoding failed") from self._error
        pts = int(round(float(t_s) / self.tb))
        if self._last_pts is not None and pts <= self._last_pts:
            raise ValueError("presentation timestamps must increase")
        self._last_pts = pts
        if self._queue is not None:
            self._queue.put((img_bgr, pts))
        else:
            self._encode(img_bgr, pts)
        return pts

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._queue is not None and self._thread is not None:
            self._queue.put(None)
            self._thread.join()
        try:
            if self._error is None:
                self._encode(None, None)
        finally:
            self.container.close()
        if self._error is not None:
            raise RuntimeError("video encoding failed") from self._error

    def __enter__(self) -> "VideoWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def iter_video(path: str | Path | io.BytesIO) -> Iterator[tuple[np.ndarray, float]]:
    """Decode every frame as (BGR uint8, PTS in seconds)."""
    with av.open(path) as c:
        st = c.streams.video[0]
        for f in c.decode(st):
            yield f.to_ndarray(format="bgr24"), float(f.pts * f.time_base)


def read_video(path: str | Path | io.BytesIO) -> tuple[list[np.ndarray], np.ndarray]:
    frames, pts = [], []
    for img, t in iter_video(path):
        frames.append(img)
        pts.append(t)
    return frames, np.asarray(pts)


def compress_roundtrip(frames: Iterable[np.ndarray], fps: float, *, crf: int = 23, codec: str = "h264",
                       preset: str = "medium", pts_s: Sequence[float] | None = None) -> tuple[list[np.ndarray], np.ndarray]:
    """Encode frames in memory (mp4) and decode them back. Returns (frames, PTS seconds)."""
    frames = list(frames)
    if not frames:
        return [], np.zeros(0)
    h, w = frames[0].shape[:2]
    if pts_s is None:
        pts_s = np.arange(len(frames)) / float(fps)
    buf = io.BytesIO()
    wr = VideoWriter(buf, (w, h), fps, codec=codec, crf=crf, preset=preset, container_format="mp4")
    for img, t in zip(frames, pts_s):
        wr.write(img, t)
    wr.close()
    buf.seek(0)
    return read_video(buf)
