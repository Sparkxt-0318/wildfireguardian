"""Step 10: research log of one laptop session (DESIGN.md section 11). Column dictionary: research_log/README.md.

Layout, per session, under ``apps/crossing/records/<session>/`` (git-ignored)::

    session.json                versions, config, vehicle, fuel (+ changes), sim flag, Pi unit/session ids, counts
    readings_<sensor>.csv       one row per received reading, flattened scalars (laptop receipt time first)
    thermal_frames.<n>.npz      thermal images (raw u16, raw / raw_per_k = K), <= chunk_frames per file
    radar_frames.<n>.npz        radar range profile (dB) and azimuth heatmap (complex64), <= chunk_frames per file
    heartbeats.csv  events.csv  Pi heartbeats; Pi/link/app events
    verdicts.csv  depth.csv  flux.csv  health.csv  pairs.csv
    wire.jsonl.gz               every received message with its receipt time, plus link up/down markers
                                (``python -m crossing --replay <session dir>`` replays this file)
    radar_baseline_<n>.json     each radar baseline captured in the session
    *.parquet                   copies of every CSV when pyarrow is importable (``export_parquet``)

Times: ``rx_mono`` is the laptop's ``time.monotonic()`` at receipt (the clock that decides freshness);
``t_mono_pi`` is the Pi's monotonic clock in the message envelope. Temperatures shown in C, flux kW/m2, dose TDU =
(kW/m2)^(4/3) s, distances m, speeds m/s.

Durability: CSV and gzip streams are flushed at every pipeline tick (5 Hz) and on close; a crash loses at most the
rows since the last tick and the current npz chunk (frames are kept in memory until a chunk is full).
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from . import __version__ as CROSSING_VERSION
from . import _repo

_repo.vu()
from wfgvu import __version__ as WFGVU_VERSION  # noqa: E402
from wfgvu import protocol  # noqa: E402

SCHEMA = "crossing.research_log/1"
SENSORS = protocol.SENSORS
ESTIMATORS = ("spread_burn", "byram", "radar_ceiling", "flicker_extent", "radar_loss_depth")

COMMON = ("rx_mono", "t_mono_pi", "t_utc", "seq", "sim")
DATA_COLUMNS: Dict[str, tuple] = {
    "thermal": ("w", "h", "gain", "shutter", "raw_per_k", "t_min_c", "t_max_c", "t_mean_c", "flame_pixels",
                "valid", "reason", "chunk", "index"),
    "radar": ("frame", "range_res_m", "n_bins", "frame_ok", "tlv_types", "n_points", "has_heatmap", "n_ant",
              "has_profile", "chunk", "index"),
    "tc_plate": ("temp_c", "cj_c", "fault"),
    "tc_housing": ("temp_c", "cj_c", "fault"),
    "tc_air": ("temp_c", "cj_c", "fault"),
    "imu": ("roll_deg", "pitch_deg", "heading_deg", "grav_x", "grav_y", "grav_z", "calib_sys", "calib_gyro",
            "calib_accel", "calib_mag"),
    "gnss": ("fix", "lat", "lon", "alt_m", "speed_m_s", "course_deg", "hdop", "sats", "utc"),
    "pi": ("cpu_c", "throttled_hex", "under_voltage_now", "under_voltage_ever", "input_v", "disk_free_mb",
           "rec_bytes"),
}
HEARTBEAT_COLUMNS = ("rx_mono", "t_mono_pi", "sensor", "status", "detail", "last_reading_seq", "rate_hz", "seq")
EVENT_COLUMNS = ("rx_mono", "source", "kind", "detail")
VERDICT_COLUMNS = ("rx_mono", "utc", "state", "decided_state", "verdict_id", "reasons", "min_speed_m_s",
                   "time_in_flame_s", "dose_tdu", "dose_limit_tdu", "dose_fds_ref_tdu", "flame_status",
                   "radar_status", "thermal_flame", "near_edge_m", "far_echo_m", "depth_m", "depth_lo_m",
                   "depth_hi_m", "intensity_kw_m", "intensity_hi_kw_m", "lat", "lon", "speed_m_s", "passed",
                   "reopen_quiet_s", "link_up", "sim", "vehicle", "fuel",
                   "depth_hi_decision_m")          # appended: DEPTH-HI rule, the upper end the dose uses
DEPTH_COLUMNS = (("rx_mono", "valid", "depth_m", "lo_m", "hi_m", "level", "used", "calibrated", "n_pairs", "scale",
                  "sigma_log", "ceiling_m", "flags")
                 + tuple("%s_%s" % (e, k) for e in ESTIMATORS for k in ("m", "lo_m", "hi_m", "valid", "reason"))
                 + ("intensity_kw_m", "intensity_lo_kw_m", "intensity_hi_kw_m", "intensity_sources",
                    "flame_height_m", "flame_height_lo_m", "flame_height_hi_m", "near_edge_m", "fuel")
                 + ("hi_decision_m", "hi_decision_from", "disagree_ratio"))     # appended: DEPTH-HI rule
FLUX_COLUMNS = ("rx_mono", "t_pi", "plate_c", "air_c", "q_kw_m2", "q_abs_kw_m2", "dTdt_k_s", "valid", "reason",
                "dose_tdu", "dose_complete", "uncounted_s")
HEALTH_COLUMNS = (("rx_mono", "link_up", "link_reason")
                  + tuple("%s_%s" % (s, k) for s in SENSORS for k in ("fresh", "reason", "age_s", "pi_status")))
PAIR_COLUMNS = (("rx_mono", "utc", "source", "fuel", "predicted_m", "lo_m", "hi_m", "sigma_log", "measured_m",
                 "loss_db")
                + tuple("est_%s_m" % e for e in ESTIMATORS)
                + ("lat", "lon", "session", "sim", "thickness_duration_s", "thickness_mean_speed_m_s",
                   "prediction_age_s", "store",
                   # FS-5 / R6 (appended): dedup key and pulse window; estimator d (experimental) on every pair
                   "key", "t_start_pi", "t_end_pi", "est_flicker_extent_lo_m", "est_flicker_extent_hi_m",
                   "est_flicker_extent_valid", "est_flicker_extent_reason", "flicker_extent_agrees"))
TABLES: Dict[str, tuple] = {"verdicts": VERDICT_COLUMNS, "depth": DEPTH_COLUMNS, "flux": FLUX_COLUMNS,
                            "health": HEALTH_COLUMNS, "pairs": PAIR_COLUMNS, "heartbeats": HEARTBEAT_COLUMNS,
                            "events": EVENT_COLUMNS}
TABLES.update({"readings_%s" % s: COMMON + DATA_COLUMNS[s] for s in SENSORS})


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def session_name(prefix: str = "CX") -> str:
    return "%s-%s" % (prefix, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")[:-4])


def _cell(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "true" if v else "false"
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return repr(f) if math.isfinite(f) else ("inf" if f == math.inf else ("-inf" if f == -math.inf else ""))
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (list, tuple)):
        return ";".join(str(_cell(x)) for x in v)
    if isinstance(v, dict):
        return json.dumps(protocol.sanitize(v), sort_keys=True)
    return str(v)


class _Table:
    def __init__(self, path: Path, columns: tuple):
        self.path = path
        self.columns = columns
        new = not path.exists()
        self.fh = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.writer(self.fh)
        if new:
            self.w.writerow(columns)
        self.rows = 0

    def write(self, row: Dict[str, Any]) -> None:
        self.w.writerow([_cell(row.get(c)) for c in self.columns])
        self.rows += 1

    def flush(self) -> None:
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


class _Chunker:
    """Collects arrays of one kind and writes ``<name>.<n>.npz`` every ``chunk`` frames (or on a shape change)."""

    def __init__(self, directory: Path, name: str, chunk: int):
        self.dir, self.name, self.chunk = directory, name, max(1, int(chunk))
        self.n_file = 0
        self.rows: List[dict] = []
        self.shape_key = None
        self.files: List[str] = []

    def add(self, row: dict, shape_key) -> tuple:
        if self.rows and shape_key != self.shape_key:
            self.flush()
        self.shape_key = shape_key
        self.rows.append(row)
        pos = (self.n_file, len(self.rows) - 1)
        if len(self.rows) >= self.chunk:
            self.flush()
        return pos

    def flush(self) -> None:
        if not self.rows:
            return
        keys = self.rows[0].keys()
        arrays = {k: np.stack([np.asarray(r[k]) for r in self.rows]) for k in keys}
        path = self.dir / ("%s.%d.npz" % (self.name, self.n_file))
        np.savez_compressed(path, **arrays)
        self.files.append(path.name)
        self.n_file += 1
        self.rows = []


class ResearchLog:
    """Writer for one session directory. Use from one thread (the pipeline's event loop)."""

    def __init__(self, root: Any, name: Optional[str] = None, info: Optional[dict] = None, chunk_frames: int = 100,
                 keep_wire: bool = True, health_every_s: float = 1.0):
        self.root = Path(root)
        self.name = name or session_name()
        self.dir = self.root / self.name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.info: Dict[str, Any] = {
            "schema": SCHEMA, "session": self.name, "started_utc": utc_now(), "ended_utc": None, "sim": False,
            "versions": versions(), "changes": [], "pi": {}, "baselines": [],
            "note": "Research log of the crossing app. Verdicts are advisory; every limit is a placeholder. "
                    "Data from simulated sessions is labelled sim = true.",
        }
        if info:
            self.info.update(protocol.sanitize(info))
        self.tables: Dict[str, _Table] = {}
        self.thermal = _Chunker(self.dir, "thermal_frames", chunk_frames)
        self.radar = _Chunker(self.dir, "radar_frames", chunk_frames)
        self.keep_wire = keep_wire
        self.wire_fh = gzip.open(self.dir / "wire.jsonl.gz", "at", compresslevel=1) if keep_wire else None
        self.health_every_s = health_every_s
        self._last_health: Optional[float] = None
        self.closed = False
        self.write_session_json()

    # ------------------------------------------------------------------------------------------- helpers
    def table(self, name: str) -> _Table:
        t = self.tables.get(name)
        if t is None:
            t = self.tables[name] = _Table(self.dir / ("%s.csv" % name), TABLES[name])
        return t

    def write_session_json(self) -> None:
        self.info["files"] = sorted(p.name for p in self.dir.iterdir() if p.is_file() and p.name != "session.json")
        self.info["counts"] = {k: t.rows for k, t in self.tables.items()}
        tmp = self.dir / "session.json.tmp"
        tmp.write_text(json.dumps(protocol.sanitize(self.info), indent=1, sort_keys=True))
        tmp.replace(self.dir / "session.json")

    def update_info(self, **kw) -> None:
        self.info.update(protocol.sanitize(kw))
        self.write_session_json()

    def change(self, rx: float, what: str, value: Any) -> None:
        """Record a vehicle / fuel / baseline change (session.json ``changes`` and events.csv)."""
        self.info["changes"].append({"rx_mono": rx, "utc": utc_now(), "what": what,
                                     "value": protocol.sanitize(value)})
        self.event(rx, "app", "change_" + what, json.dumps(protocol.sanitize(value), sort_keys=True)[:2000])
        self.write_session_json()

    # ------------------------------------------------------------------------------------------- inputs
    def wire(self, rx: float, msg: dict) -> None:
        if self.wire_fh is not None:
            self.wire_fh.write(json.dumps({"rx": rx, "msg": msg}, separators=(",", ":"), allow_nan=False) + "\n")

    def wire_link(self, rx: float, up: bool, reason: str = "") -> None:
        if self.wire_fh is not None:
            self.wire_fh.write(json.dumps({"rx": rx, "link": "up" if up else "down", "reason": reason}) + "\n")
        self.event(rx, "link", "link_up" if up else "link_down", reason)

    def message(self, msg: dict, rx: float, extras: Optional[dict] = None) -> None:
        """Log one parsed protocol message received at laptop time ``rx``."""
        self.wire(rx, msg)
        mtype = msg.get("type")
        if msg.get("sim") is True and not self.info.get("sim"):
            self.info["sim"] = True
            self.write_session_json()
        if mtype == "hello":
            self.info["pi"] = {"unit_id": msg.get("unit_id"), "session_id": msg.get("session_id"),
                               "version": msg.get("version"), "sensors": msg.get("sensors"),
                               "config_digest": msg.get("config_digest"),
                               "thermal_wire_hz": msg.get("thermal_wire_hz")}
            self.write_session_json()
        elif mtype == "heartbeat":
            self.table("heartbeats").write({"rx_mono": rx, "t_mono_pi": msg.get("t_mono"), **{
                k: msg.get(k) for k in ("sensor", "status", "detail", "last_reading_seq", "rate_hz", "seq")}})
        elif mtype == "event":
            self.event(rx, "pi", msg.get("kind"), msg.get("detail"))
        elif mtype == "reading":
            self.reading(msg, rx, extras or {})

    def reading(self, msg: dict, rx: float, extras: dict) -> None:
        sensor = msg["sensor"]
        d = msg.get("data") or {}
        row: Dict[str, Any] = {"rx_mono": rx, "t_mono_pi": msg.get("t_mono"), "t_utc": msg.get("t_utc"),
                               "seq": msg.get("seq"), "sim": msg.get("sim")}
        if sensor == "thermal":
            row.update({k: d.get(k) for k in ("w", "h", "gain", "shutter", "raw_per_k")})
            temps = extras.get("temps_k")
            row.update(valid=extras.get("valid"), reason=extras.get("reason"),
                       flame_pixels=extras.get("flame_pixels"))
            if temps is not None:
                t = np.asarray(temps, dtype=np.float32)
                if t.size:
                    row.update(t_min_c=float(t.min()) - 273.15, t_max_c=float(t.max()) - 273.15,
                               t_mean_c=float(t.mean()) - 273.15)
                rpk = float(d.get("raw_per_k") or protocol.RAW_PER_K)
                raw = np.clip(np.round(t * rpk), 0, 65535).astype(np.uint16)
                row["chunk"], row["index"] = self.thermal.add(
                    {"rx_mono": float(rx), "seq": int(msg.get("seq", -1)), "raw_u16": raw,
                     "raw_per_k": rpk}, raw.shape)
        elif sensor == "radar":
            hm = d.get("az_heatmap")
            row.update({k: d.get(k) for k in ("frame", "range_res_m", "n_bins", "frame_ok", "tlv_types")})
            row.update(n_points=None if d.get("points") is None else len(d["points"]), has_heatmap=hm is not None,
                       n_ant=(hm or {}).get("n_ant"), has_profile=d.get("range_profile_db") is not None)
            iq = extras.get("iq")
            prof = d.get("range_profile_db")
            n_bins = int(iq.shape[0]) if iq is not None else (len(prof) if prof is not None else 0)
            n_ant = int(iq.shape[1]) if iq is not None else 0
            if n_bins:
                p = np.full(n_bins, np.nan, dtype=np.float32)
                if prof is not None and len(prof) == n_bins:
                    p[:] = [np.nan if v is None else v for v in prof]
                q = np.zeros((n_bins, max(n_ant, 1)), dtype=np.complex64) if iq is None else iq.astype(np.complex64)
                row["chunk"], row["index"] = self.radar.add(
                    {"rx_mono": float(rx), "seq": int(msg.get("seq", -1)), "frame": int(d.get("frame", -1)),
                     "range_res_m": float(d.get("range_res_m") or np.nan), "profile_db": p, "iq": q,
                     "has_iq": iq is not None, "has_profile": prof is not None}, (n_bins, q.shape[1]))
        elif sensor == "imu":
            row.update({k: d.get(k) for k in ("roll_deg", "pitch_deg", "heading_deg")})
            g = d.get("grav") or [None, None, None]
            row.update(grav_x=g[0], grav_y=g[1], grav_z=g[2])
            c = d.get("calib") or {}
            row.update(calib_sys=c.get("sys"), calib_gyro=c.get("gyro"), calib_accel=c.get("accel"),
                       calib_mag=c.get("mag"))
        else:
            row.update({k: d.get(k) for k in DATA_COLUMNS[sensor]})
        self.table("readings_%s" % sensor).write(row)

    def event(self, rx: float, source: str, kind: Any, detail: Any) -> None:
        self.table("events").write({"rx_mono": rx, "source": source, "kind": kind, "detail": detail})

    def flux(self, row: dict) -> None:
        self.table("flux").write(row)

    def pair(self, row: dict) -> None:
        self.table("pairs").write(row)
        self.flush()

    def baseline(self, rx: float, baseline_dict: dict) -> Path:
        n = len(self.info["baselines"])
        path = self.dir / ("radar_baseline_%d.json" % n)
        path.write_text(json.dumps(protocol.sanitize(baseline_dict)))
        self.info["baselines"].append({"rx_mono": rx, "file": path.name, "utc": utc_now()})
        self.write_session_json()
        return path

    def tick(self, state: dict) -> None:
        """Rows of verdicts.csv and depth.csv every tick; health.csv every ``health_every_s``."""
        now = state.get("t_mono")
        v = state.get("verdict") or {}
        fl = state.get("flame") or {}
        geo = state.get("geometry") or {}
        dep = state.get("depth") or {}
        inten = state.get("intensity") or {}
        g = state.get("gnss") or {}
        self.table("verdicts").write({
            "rx_mono": now, "utc": state.get("utc"), "state": v.get("state"), "decided_state": v.get("decided_state"),
            "verdict_id": v.get("verdict_id"), "reasons": v.get("reasons"), "min_speed_m_s": v.get("min_speed_m_s"),
            "time_in_flame_s": v.get("time_in_flame_s"), "dose_tdu": v.get("dose_tdu"),
            "dose_limit_tdu": v.get("dose_limit_tdu"), "dose_fds_ref_tdu": v.get("dose_fds_ref_tdu"),
            "flame_status": fl.get("status"), "radar_status": (fl.get("radar") or {}).get("status"),
            "thermal_flame": (fl.get("thermal") or {}).get("flame_at_bearing"),
            "near_edge_m": geo.get("near_edge_m"), "far_echo_m": geo.get("far_echo_m"),
            "depth_m": dep.get("depth_m"), "depth_lo_m": dep.get("lo_m"), "depth_hi_m": dep.get("hi_m"),
            "intensity_kw_m": inten.get("i_kw_m"), "intensity_hi_kw_m": inten.get("hi"), "lat": g.get("lat"),
            "lon": g.get("lon"), "speed_m_s": g.get("speed_m_s"), "passed": state.get("reopen", {}).get("passed"),
            "reopen_quiet_s": state.get("reopen", {}).get("quiet_s"),
            "link_up": (state.get("health") or {}).get("link_up"), "sim": state.get("sim"),
            "vehicle": (state.get("vehicle") or {}).get("name"), "fuel": (state.get("fuel") or {}).get("code"),
            "depth_hi_decision_m": dep.get("hi_decision_m")})
        row = {"rx_mono": now, **{k: dep.get(k) for k in ("valid", "depth_m", "lo_m", "hi_m", "level", "used",
                                                         "calibrated", "n_pairs", "scale", "sigma_log",
                                                         "ceiling_m", "flags", "hi_decision_m",
                                                         "hi_decision_from", "disagree_ratio")}}
        for e in dep.get("estimators") or []:
            name = e.get("name")
            if name in ESTIMATORS:
                row.update({"%s_m" % name: e.get("value_m"), "%s_lo_m" % name: e.get("lo_m"),
                            "%s_hi_m" % name: e.get("hi_m"), "%s_valid" % name: e.get("valid"),
                            "%s_reason" % name: e.get("reason")})
        row.update(intensity_kw_m=inten.get("i_kw_m"), intensity_lo_kw_m=inten.get("lo"),
                   intensity_hi_kw_m=inten.get("hi"), intensity_sources=inten.get("sources"),
                   flame_height_m=geo.get("flame_height_m"), flame_height_lo_m=geo.get("flame_height_lo_m"),
                   flame_height_hi_m=geo.get("flame_height_hi_m"), near_edge_m=geo.get("near_edge_m"),
                   fuel=(state.get("fuel") or {}).get("code"))
        self.table("depth").write(row)
        h = state.get("health") or {}
        if now is not None and (self._last_health is None or now - self._last_health >= self.health_every_s):
            self._last_health = now
            hrow = {"rx_mono": now, "link_up": h.get("link_up"), "link_reason": h.get("link_reason")}
            for s, sh in (h.get("sensors") or {}).items():
                hrow.update({"%s_fresh" % s: sh.get("fresh"), "%s_reason" % s: sh.get("reason"),
                             "%s_age_s" % s: sh.get("age_s"), "%s_pi_status" % s: sh.get("status_from_pi")})
            self.table("health").write(hrow)
        self.flush()

    def flush(self) -> None:
        for t in self.tables.values():
            t.flush()
        if self.wire_fh is not None:
            self.wire_fh.flush()

    def close(self, parquet: bool = True) -> List[Path]:
        if self.closed:
            return []
        self.closed = True
        self.thermal.flush()
        self.radar.flush()
        for t in self.tables.values():
            t.close()
        if self.wire_fh is not None:
            self.wire_fh.close()
        self.info["ended_utc"] = utc_now()
        out: List[Path] = []
        if parquet:
            out = export_parquet(self.dir)
            self.info["parquet"] = [p.name for p in out] if out else "pyarrow not available or no CSV"
        self.write_session_json()
        return out


def versions() -> dict:
    v = {"crossing": CROSSING_VERSION, "wfgvu": WFGVU_VERSION, "protocol": protocol.PROTOCOL_VERSION,
         "python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__}
    for mod in ("pyarrow", "fastapi", "websockets", "pyproj"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001 - optional
            v[mod] = None
    return v


def export_parquet(directory: Any) -> List[Path]:
    """Write ``<table>.parquet`` next to every ``<table>.csv`` in ``directory``. Returns the files written, or []
    when pyarrow is not importable (the CSVs stay the primary record)."""
    try:
        import pyarrow.csv as pacsv
        import pyarrow.parquet as pq
    except ImportError:
        return []
    out = []
    for p in sorted(Path(directory).glob("*.csv")):
        try:
            table = pacsv.read_csv(p, convert_options=pacsv.ConvertOptions(
                strings_can_be_null=True, true_values=["true"], false_values=["false"]))
        except Exception:  # noqa: BLE001 - a malformed CSV must not stop the export of the others
            continue
        target = p.with_suffix(".parquet")
        pq.write_table(table, target)
        out.append(target)
    return out


def read_csv(path: Any) -> List[dict]:
    """Rows of a research-log CSV as dicts of strings (helper for tests and analysis scripts)."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def iter_wire(session_dir: Any) -> Iterable[dict]:
    """Records of ``wire.jsonl.gz``: {"rx", "msg"} or {"rx", "link", "reason"}; a truncated tail is tolerated."""
    path = Path(session_dir) / "wire.jsonl.gz"
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            while True:
                try:
                    line = fh.readline()
                except (EOFError, OSError):
                    return
                if not line:
                    return
                if not line.endswith("\n"):
                    return
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except FileNotFoundError:
        return
