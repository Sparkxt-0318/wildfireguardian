"""TI IWR6843AOP EVM with the stock mmWave SDK 3.x out-of-box demo (``radar``). ``pyserial`` for the UARTs.

Live sequence: open the CLI UART (115200 8N1) and the data UART (921600 8N1); send ``config/iwr6843aop_vu.cfg``
line by line on the CLI port, waiting for each ``Done`` (or ``Error``); emit ``event`` ``radar_config_sent``; then
read the data UART in chunks, record every byte (``raw_sink`` -> ``radar_uart.bin``), find frames with
``tlv.FrameSync`` and emit one ``radar`` reading per frame.

Reading ``data`` (DESIGN.md section 2):

- ``range_res_m``: range-bin spacing from the config, ``c * Fs / (2 * S * N_fft)`` (complex 1x sampling, N_fft
  = next power of two of numAdcSamples). This is the FFT bin spacing, not a measured resolution.
- ``range_profile_db``: TLV 2 converted ``20*log10(2) * q9 / 512 / n_virt`` (uncalibrated demo units). TLV 2 is the
  SUM over the ``n_virt`` virtual antennas of log2|x| (TI documentation; UNVERIFIED on the EVM), so dividing by
  ``n_virt`` (from the CLI config: TX x RX) gives the mean per-antenna 20 log10|x|. Without a parsed config the
  antenna count is unknown and ``range_profile_db`` is null (the frame cannot feed the profile path).
- ``az_heatmap``: TLV 4, complex [n_bins, n_ant] (n_ant = TLV length / (4 * n_bins)), wire-encoded with
  ``protocol.encode_iq`` (real, imag).
- ``points``: TLV 1 (x, y, z in m, doppler in m/s) with TLV 7 SNR in dB (0.1 dB units / 10); ``[]`` when the
  header says zero objects (the demo then omits TLV 1), null when objects were announced but TLV 1 is missing.
- ``frame_ok``: false if the frame parsed but its TLVs were inconsistent with each other or with the config.

Configs (all UNTESTED on the EVM; arithmetic in each file's header):

- ``config/iwr6843aop_vu.cfg`` (default, long range): 128 bins x 0.468 m, IF-limited max range 54 m, 10 Hz,
  12 virtual antennas. 6456 B per frame without points = 64.6 kB/s = 70 % of a 921600-baud UART (92160 B/s).
- ``config/iwr6843aop_vu_short.cfg`` (the previous default): 512 bins x 0.049 m, max 22.5 m. Cannot see behind an
  ~11 m deep flame at 10-30 m standoff, and at 10 Hz it needs ~257 kB/s, 2.8x the UART: expect a lower achieved
  frame rate or a demo stall.
- ``config/iwr6843aop_vu_long_fine.cfg``: 512 bins x 0.117 m, max 54 m, 2.86 Hz (80 % of the UART).

``RadarProfile.uart_load(baud)`` gives the fraction of the data UART a config needs (no points); it is reported in
the ``radar_config_sent`` event, flagged "OVER UART BUDGET" above 1.0. ``rate_hz`` in the heartbeat reports the frame
rate actually achieved. A faster data port is not expected on the standalone EVM: the CP2105 "Standard" port is specified to 921.6 kbaud
(as we read the CP2105 datasheet; not checked on our board).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from .. import protocol
from . import tlv
from .base import DeviceUnavailable, Driver, first_present

C_M_S = 299_792_458.0
DEFAULT_CFG = Path(__file__).resolve().parents[2] / "config" / "iwr6843aop_vu.cfg"


@dataclass
class RadarProfile:
    """Chirp/frame parameters derived from a demo CLI config."""
    start_ghz: float
    slope_mhz_us: float
    n_adc: int
    fs_ksps: float
    ramp_end_us: float
    adc_start_us: float
    n_tx: int
    n_rx: int
    n_loops: int
    frame_period_ms: float
    n_chirps_per_loop: int = 1
    complex_sampling: bool = True

    @property
    def n_bins(self) -> int:
        return 1 << int(math.ceil(math.log2(self.n_adc)))

    @property
    def n_virt(self) -> int:
        return self.n_tx * self.n_rx

    @property
    def sampled_bandwidth_hz(self) -> float:
        return self.slope_mhz_us * 1e12 * self.n_adc / (self.fs_ksps * 1e3)

    @property
    def range_res_m(self) -> float:
        """FFT range-bin spacing [m]: c * Fs / (2 * S * N_fft)."""
        return C_M_S * self.fs_ksps * 1e3 / (2.0 * self.slope_mhz_us * 1e12 * self.n_bins)

    @property
    def max_range_m(self) -> float:
        """IF-bandwidth limited max range [m] (0.9 Fs usable for complex sampling, 0.9 Fs/2 for real)."""
        f_if = 0.9 * self.fs_ksps * 1e3 * (1.0 if self.complex_sampling else 0.5)
        return f_if * C_M_S / (2.0 * self.slope_mhz_us * 1e12)

    @property
    def sweep_end_ghz(self) -> float:
        return self.start_ghz + self.slope_mhz_us * self.ramp_end_us / 1e3

    @property
    def frame_rate_hz(self) -> float:
        return 1000.0 / self.frame_period_ms

    def bytes_per_frame(self, heatmap: bool = True, profile: bool = True, points: int = 0) -> int:
        """UART bytes of one demo frame: 40 B header, TLV 2 (uint16 per bin), TLV 4 (int16 I/Q per bin per virtual
        antenna), and ``points`` detections as TLV 1 (16 B) + TLV 7 (4 B) with their two 8 B TLV headers."""
        pts = (16 + 20 * points) if points > 0 else 0
        return 40 + (8 + 2 * self.n_bins if profile else 0) + (8 + 4 * self.n_bins * self.n_virt if heatmap else 0) \
            + pts

    def uart_bytes_per_s(self, points: int = 0) -> float:
        return self.bytes_per_frame(points=points) * self.frame_rate_hz

    def uart_load(self, baud: int = 921600, points: int = 0) -> float:
        """Fraction of an 8N1 UART at ``baud`` (10 bits per byte) the configured frames need. > 1: cannot keep up."""
        return self.uart_bytes_per_s(points) / (baud / 10.0)


def cfg_lines(text: str) -> List[str]:
    """Command lines of a demo CLI config (comments starting with % or # and blank lines removed)."""
    out = []
    for line in text.splitlines():
        line = line.split("%", 1)[0].split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def profile_from_cfg(text: str) -> RadarProfile:
    """Derive a ``RadarProfile`` from the config text (profileCfg, channelCfg, adcCfg, frameCfg)."""
    cmds: Dict[str, List[str]] = {}
    for line in cfg_lines(text):
        parts = line.split()
        cmds.setdefault(parts[0], parts[1:])                 # first occurrence wins (one profile)
    try:
        p = cmds["profileCfg"]
        ch = cmds["channelCfg"]
        fr = cmds["frameCfg"]
    except KeyError as exc:
        raise ValueError("config lacks %s" % exc) from exc
    adc = cmds.get("adcCfg", ["2", "1"])
    rx_mask, tx_mask = int(ch[0]), int(ch[1])
    chirp_start, chirp_end, loops = int(fr[0]), int(fr[1]), int(fr[2])
    return RadarProfile(start_ghz=float(p[1]), adc_start_us=float(p[3]), ramp_end_us=float(p[4]),
                        slope_mhz_us=float(p[7]), n_adc=int(p[9]), fs_ksps=float(p[10]),
                        n_rx=bin(rx_mask).count("1"), n_tx=bin(tx_mask).count("1"),
                        n_loops=loops, n_chirps_per_loop=chirp_end - chirp_start + 1,
                        frame_period_ms=float(fr[4]), complex_sampling=int(adc[1]) != 0)


def load_profile(path: Optional[Path] = None) -> RadarProfile:
    return profile_from_cfg(Path(path or DEFAULT_CFG).read_text())


def frame_to_data(frame: dict, profile: Optional[RadarProfile] = None) -> dict:
    """Parsed TLV frame -> ``radar`` reading ``data``."""
    ok = True
    rp = frame.get("range_profile_q9")
    # TLV 2 = sum over the virtual antennas of log2|x| (Q9): normalise by the antenna count from the config. No
    # config -> unknown count -> no profile (never send dB values that are n_virt times too large).
    n_virt = profile.n_virt if profile is not None else 0
    profile_db = tlv.q9_to_db(rp, n_virt).round(3).tolist() if rp is not None and n_virt >= 1 else None
    n_bins = int(len(rp)) if rp is not None else (profile.n_bins if profile else 0)
    if profile is not None and rp is not None and len(rp) != profile.n_bins:
        ok = False
    az = None
    hm = frame.get("az_heatmap")
    if hm is not None:
        n_ant = None
        if n_bins and hm.size % n_bins == 0:
            n_ant = hm.size // n_bins
        elif profile is not None and hm.size % profile.n_virt == 0:
            n_ant = profile.n_virt
            n_bins = hm.size // n_ant
        if n_ant:
            az = protocol.encode_iq(hm.reshape(-1, n_ant))
        else:
            ok = False
    pts = frame.get("points")
    if pts is not None:
        side = frame.get("side_info")
        snr = side[:, 0] * 0.1 if side is not None else [None] * len(pts)
        points = [[float(p[0]), float(p[1]), float(p[2]), float(p[3]),
                   None if s is None else float(s)] for p, s in zip(pts, snr)]
    elif frame.get("num_obj", 0) == 0:
        points = []
    else:
        points = None
        ok = False
    return {"frame": int(frame["frame"]), "range_res_m": profile.range_res_m if profile else None,
            "n_bins": int(n_bins), "range_profile_db": profile_db, "az_heatmap": az, "points": points,
            "tlv_types": list(frame.get("tlv_types", [])), "frame_ok": bool(ok)}


def send_cli_config(port, lines: Sequence[str], timeout_s: float = 1.0) -> List[dict]:
    """Send config lines on the CLI UART; wait for ``Done``/``Error`` per line. Returns per-line results."""
    results = []
    for line in lines:
        port.write((line + "\n").encode("ascii"))
        deadline = time.monotonic() + timeout_s
        resp = b""
        status = "timeout"
        while time.monotonic() < deadline:
            chunk = port.read(256)
            if chunk:
                resp += chunk
                if b"Done" in resp:
                    status = "done"
                    break
                if b"Error" in resp or b"not recognized" in resp:
                    status = "error"
                    break
        results.append({"line": line, "status": status, "response": resp.decode("ascii", "replace").strip()})
    return results


class RadarDriver(Driver):
    """cfg: ``cli_port``, ``data_port``, ``cli_baud`` (115200), ``data_baud`` (921600), ``cfg_file``,
    ``read_chunk`` (4096). ``raw_sink(bytes)`` receives every data-UART byte (recorder)."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, raw_sink: Optional[Callable] = None,
                 serial_factory: Optional[Callable] = None):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self.raw_sink = raw_sink
        self._serial_factory = serial_factory
        self._cli = None
        self._data = None
        self.sync = tlv.FrameSync()
        cfg_file = self.cfg.get("cfg_file")
        self.cfg_path = Path(cfg_file) if cfg_file else DEFAULT_CFG
        try:
            self.profile: Optional[RadarProfile] = load_profile(self.cfg_path)
        except (OSError, ValueError):
            self.profile = None

    def _open_serial(self, port: str, baud: int, timeout: float):
        if self._serial_factory is not None:
            return self._serial_factory(port, baud, timeout)
        serial = first_present(["serial"])
        if serial is None:
            raise DeviceUnavailable("python module pyserial not installed")
        return serial.Serial(port, baud, timeout=timeout)

    def open(self) -> None:
        text = self.cfg_path.read_text()
        self.profile = profile_from_cfg(text)
        self._cli = self._open_serial(self.cfg.get("cli_port", "/dev/ttyUSB0"),
                                      int(self.cfg.get("cli_baud", 115200)), 0.05)
        self._data = self._open_serial(self.cfg.get("data_port", "/dev/ttyUSB1"),
                                       int(self.cfg.get("data_baud", 921600)), 0.05)
        results = send_cli_config(self._cli, cfg_lines(text), float(self.cfg.get("cli_timeout_s", 1.0)))
        bad = [r for r in results if r["status"] != "done"]
        load = self.profile.uart_load(int(self.cfg.get("data_baud", 921600)))
        self.event("radar_config_sent", "%s: %d lines, %d not acknowledged%s; %d bins x %.3f m, max %.1f m, %.1f Hz, "
                   "data UART load %.0f %% without points%s" % (
                       self.cfg_path.name, len(results), len(bad),
                       (": " + "; ".join("%s -> %s" % (r["line"], r["status"]) for r in bad[:3])) if bad else "",
                       self.profile.n_bins, self.profile.range_res_m, self.profile.max_range_m,
                       self.profile.frame_rate_hz, 100.0 * load, " (OVER UART BUDGET)" if load > 1.0 else ""))
        # sensorStop/flushCfg may legitimately answer differently on a cold start; anything else is fatal
        fatal = [r for r in bad if r["line"].split()[0] not in ("sensorStop", "flushCfg")]
        if fatal:
            raise DeviceUnavailable("radar rejected config: %s -> %s" % (fatal[0]["line"], fatal[0]["status"]))
        self.sync = tlv.FrameSync()
        self._last_frame_mono = time.monotonic()            # grace period after config before the first frame

    def frame_watchdog_s(self) -> float:
        """VU-R3: a radar that is open but delivers no COMPLETE decoded frame for this long is re-opened (sensorStop,
        config, sensorStart again). cfg ``frame_watchdog_s``, default max(3 frame periods, 1 s) + 2 s, 3 s without a
        profile. PLACEHOLDER."""
        v = self.cfg.get("frame_watchdog_s")
        if v is not None:
            return float(v)
        if self.profile is not None and self.profile.frame_rate_hz:
            return max(3.0 / float(self.profile.frame_rate_hz), 1.0) + 2.0
        return 3.0

    def parser_stats(self) -> str:
        st = self.sync.stats()
        out = "frames=%d garbage_bytes=%d bad_frames=%d truncated=%d" % (
            st["frames"], st["garbage_bytes"], st["bad_frames"], st["truncated"])
        if self.sync.last_error:
            out += " last_error=%s" % str(self.sync.last_error)[:80]
        return out

    def read(self) -> List[dict]:
        chunk = self._data.read(int(self.cfg.get("read_chunk", 4096)))
        if chunk and self.raw_sink is not None:
            try:
                self.raw_sink(chunk)
            except Exception:                               # noqa: BLE001 - recording must not stop the radar
                pass
        frames = self.sync.feed(chunk) if chunk else []
        now = time.monotonic()
        if frames:
            self._last_frame_mono = now
        else:
            age = now - getattr(self, "_last_frame_mono", now)
            if age > self.frame_watchdog_s():
                self.event("radar_watchdog", "no complete radar frame for %.1f s (%s); re-opening"
                           % (age, self.parser_stats()))
                self._last_frame_mono = now
                raise IOError("no radar frames for %.1f s" % age)
        return [frame_to_data(f, self.profile) for f in frames]

    def close(self) -> None:
        for attr in ("_cli", "_data"):
            port = getattr(self, attr)
            if port is not None:
                try:
                    if attr == "_cli":
                        port.write(b"sensorStop\n")
                except Exception:                           # noqa: BLE001
                    pass
                try:
                    port.close()
                finally:
                    setattr(self, attr, None)

    def assess(self, data: dict):
        if not data.get("frame_ok"):
            return False, "inconsistent radar frame"
        if data.get("range_profile_db") is None and data.get("az_heatmap") is None:
            return False, "frame without range profile or heatmap"
        return True, ""


def frames_from_uart_file(path, profile: Optional[RadarProfile] = None) -> List[dict]:
    """Re-decode a recorded ``radar_uart.bin`` into ``radar`` data dicts (offline; no timing is stored)."""
    data = Path(path).read_bytes()
    return [frame_to_data(f, profile) for f in tlv.iter_frames(data)]

