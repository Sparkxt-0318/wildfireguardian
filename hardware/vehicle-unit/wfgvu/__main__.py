"""Run the roof unit: ``python -m wfgvu [--config config/unit.yaml] [--sim SESSION_DIR [--speed 1.0] [--loop]]``.

Live mode opens every enabled sensor from the config (missing devices report ``no_device`` and are retried every
2 s), records to ``records/<session_id>/`` and serves ``ws://<host>:<port>/stream``.

Sim mode replays a recorded session directory through the same drivers (one per recorded sensor stream), at the
recorded timing divided by ``--speed``; every message is labelled ``"sim": true``. Sim mode does not record unless
``--record`` is given. The unit never decides anything; it only streams and records.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import errno
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import protocol, replay
from .drivers.bno055 import Bno055Driver
from .drivers.gnss_nmea import GnssDriver
from .drivers.max31855 import DISC_MAX_C_USER, Max31855Driver, reserve_cs_from_config
from .drivers.pi_health import PiHealthDriver
from .drivers.radar_iwr6843 import RadarDriver
from .drivers.thermal_tc001 import ThermalTC001Driver
from .recorder import Recorder
from .server import UnitServer

VU_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = VU_ROOT / "config" / "unit.yaml"

DRIVER_CLASSES = {"thermal": ThermalTC001Driver, "radar": RadarDriver, "tc_plate": Max31855Driver,
                  "tc_housing": Max31855Driver, "tc_air": Max31855Driver, "imu": Bno055Driver,
                  "gnss": GnssDriver, "pi": PiHealthDriver}

DEFAULTS: Dict[str, Any] = {
    "unit_id": "VU-01",
    "server": {"host": "0.0.0.0", "port": 8770, "path": "/stream", "thermal_wire_hz": 4.0,
               "client_queue_max": 400, "heartbeat_s": 0.5},
    "records": {"dir": "records", "flush_s": 1.0, "rotate_mb": 256, "low_free_mb": 1000, "stop_free_mb": 200},
    "sensors": {name: {"enabled": True} for name in protocol.SENSORS},
    "mount": {},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(path: Optional[Path] = None) -> dict:
    """Defaults merged with the YAML file (PyYAML). Relative paths in it are relative to hardware/vehicle-unit."""
    p = Path(path) if path else DEFAULT_CONFIG
    data: dict = {}
    if p.exists():
        import yaml
        data = yaml.safe_load(p.read_text()) or {}
    return _merge(DEFAULTS, data)


def config_warnings(cfg: dict) -> list:
    """Warnings about the unit config (logged at start; nothing is refused here).

    - ``mount.radar_height_m`` and ``mount.plate_height_m`` must equal ``mount.camera_height_m``: on the supplied
      housing the camera hole, the radar window and the flux-disc hole are on one horizontal centre line
      (``housing.sensor_centre_line_above_base_mm``).
    - ``sensors.tc_plate.disc_max_c`` should be the user's 70 C (PETG tabs); the driver never uses more than 70."""
    out = []
    m = cfg.get("mount") or {}
    cam = m.get("camera_height_m")
    for key in ("radar_height_m", "plate_height_m"):
        other = m.get(key)
        if cam is None or other is None:
            continue
        try:
            if abs(float(cam) - float(other)) > 1e-6:
                out.append("mount.%s (%s) != mount.camera_height_m (%s): on the supplied housing both sit on one "
                           "centre line; set them equal" % (key, other, cam))
        except (TypeError, ValueError):
            out.append("mount.camera_height_m / %s are not numbers" % key)
    plate = (cfg.get("sensors") or {}).get("tc_plate") or {}
    v = plate.get("disc_max_c")
    try:
        bad = v is None or float(v) > DISC_MAX_C_USER or float(v) <= 0
    except (TypeError, ValueError):
        bad = True
    if bad:
        out.append("sensors.tc_plate.disc_max_c is %r; using %.0f C (user-set limit, PETG tabs)" % (v, DISC_MAX_C_USER))
    return out


def _abs(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else VU_ROOT / q


def hello_mount(cfg: dict, session=None) -> Optional[dict]:
    """Mount sent in ``hello`` (camera height/pitch/roll/yaw, radar height ...; unit.yaml key names).

    Live: ``cfg["mount"]`` (config/unit.yaml). Sim: the replayed session's own mount, i.e. session.json
    ``config.mount`` (a live recording stores the whole config; synth writes the mount it rendered with), else the
    synth ``truth.camera`` of older synthetic sessions; else None and ``hello`` carries no ``mount`` (the replayed
    frames' camera pitch is then unknown to the unit; it never substitutes this unit's config for it)."""
    if session is None:
        m = cfg.get("mount")
        return dict(m) if isinstance(m, dict) else None
    info = session.info or {}
    m = (info.get("config") or {}).get("mount") if isinstance(info.get("config"), dict) else None
    if isinstance(m, dict) and m:
        return dict(m)
    cam = (info.get("truth") or {}).get("camera") if isinstance(info.get("truth"), dict) else None
    if isinstance(cam, dict) and "mount_pitch_deg" in cam:
        return {"camera_height_m": cam.get("height_m"), "camera_pitch_deg": cam.get("mount_pitch_deg"),
                "camera_roll_deg": cam.get("mount_roll_deg"), "camera_yaw_deg": cam.get("mount_yaw_deg"),
                "source": "session.json truth.camera"}
    return None


def build(cfg: dict, sim_dir: Optional[Path] = None, speed: float = 1.0, loop: bool = False,
          record: Optional[bool] = None, host: Optional[str] = None, port: Optional[int] = None,
          records_dir: Optional[Path] = None) -> UnitServer:
    """Create context, recorder, server and drivers from a config (live) or a recorded session (sim)."""
    srv_cfg, rec_cfg = cfg["server"], cfg["records"]
    session = replay.load(sim_dir) if sim_dir is not None else None
    unit_id = (session.unit_id if session is not None else None) or cfg["unit_id"]
    ctx = protocol.Context(unit_id=unit_id, sim=session is not None)
    if record is None:
        record = session is None
    root = Path(records_dir) if records_dir else _abs(rec_cfg["dir"])
    recorder = None
    server: Optional[UnitServer] = None

    def on_rec_event(kind: str, detail: str) -> None:
        if server is not None:
            server.event(kind, detail)

    if record:
        extra = {"replay_of": str(sim_dir)} if session is not None else None
        recorder = Recorder(root, ctx.session_id, unit_id, sim=ctx.sim, config=cfg,
                            flush_s=float(rec_cfg["flush_s"]), rotate_bytes=int(float(rec_cfg["rotate_mb"]) * 1e6),
                            low_free_mb=float(rec_cfg["low_free_mb"]), stop_free_mb=float(rec_cfg["stop_free_mb"]),
                            on_event=on_rec_event, extra_info=extra)
        # The recorder never reuses a directory (two boots can share a wall-clock id: no RTC, no GNSS time); every
        # message must carry the id it really used, so set it before the server or any driver sends anything.
        ctx.session_id = recorder.session_id
    if session is None:
        # hold every MAX31855 software chip select (enabled or not) HIGH before any SPI transfer on its bus
        reserve_cs_from_config(cfg.get("sensors") or {})
    server = UnitServer(ctx, cfg, recorder, host=host or srv_cfg["host"], port=srv_cfg["port"] if port is None
                        else port, path=srv_cfg["path"], thermal_wire_hz=srv_cfg.get("thermal_wire_hz"),
                        client_queue_max=int(srv_cfg["client_queue_max"]),
                        heartbeat_s=float(srv_cfg.get("heartbeat_s", 0.5)), session=session, speed=speed,
                        loop_replay=loop, stop_timeout_s=float(srv_cfg.get("stop_timeout_s", 1.8)),
                        mount=hello_mount(cfg, session),
                        recorder_close_s=float(srv_cfg.get("recorder_close_s", 5.0)))
    for name in protocol.SENSORS:
        scfg = dict(cfg["sensors"].get(name) or {})
        if session is not None:
            if name not in session.streams:
                continue
            drv = DRIVER_CLASSES[name](name, scfg, server.emit, session.streams[name], ctx=ctx)
        else:
            if not scfg.get("enabled", True):
                continue
            kwargs: Dict[str, Any] = {}
            if name == "radar":
                if scfg.get("cfg_file"):
                    scfg["cfg_file"] = str(_abs(scfg["cfg_file"]))
                if recorder is not None:
                    kwargs["raw_sink"] = lambda b, r=recorder: r.write_raw("radar_uart", b)
            if name == "gnss" and recorder is not None:      # VU-R6: every raw NMEA line, Pi-time stamped
                kwargs["raw_sink"] = lambda b, r=recorder: r.write_raw("gnss_nmea", b)
            if name == "pi":
                scfg.setdefault("records_dir", str(root))
                if recorder is not None:
                    kwargs["rec_bytes_fn"] = lambda r=recorder: r.rec_bytes
            drv = DRIVER_CLASSES[name](name, scfg, server.emit, None, ctx=ctx, **kwargs)
        server.add_driver(drv)
    return server


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wfgvu", description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--sim", type=Path, metavar="SESSION_DIR", help="replay a recorded session instead of sensors")
    ap.add_argument("--speed", type=float, default=1.0, help="sim playback speed factor")
    ap.add_argument("--loop", action="store_true", help="sim: restart the session when it ends")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--records", type=Path, help="records root (default from config)")
    rec = ap.add_mutually_exclusive_group()
    rec.add_argument("--record", dest="record", action="store_true", default=None)
    rec.add_argument("--no-record", dest="record", action="store_false")
    ap.add_argument("--duration", type=float, help="stop after this many seconds")
    ap.add_argument("--exit-on-end", action="store_true", help="sim: exit when the recorded session has ended")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(a.config)
    cfg_path = Path(a.config) if a.config else DEFAULT_CONFIG
    if not cfg_path.exists():
        logging.getLogger("wfgvu").warning("config: %s not found: running on built-in DEFAULTS (not the build "
                                           "manual's pin map or mount); pass --config or run from "
                                           "hardware/vehicle-unit", cfg_path)
    for w in config_warnings(cfg):
        logging.getLogger("wfgvu").warning("config: %s", w)
    try:
        server = build(cfg, a.sim, a.speed, a.loop, a.record, a.host, a.port, a.records)
    except (FileNotFoundError, ValueError) as exc:          # ValueError includes json.JSONDecodeError
        print("error: %s" % exc, file=sys.stderr)
        return 2

    async def _run() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass
        await server.run(a.duration, stop, exit_on_sim_end=a.exit_on_end)

    try:
        asyncio.run(_run())
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise
        print("error: port %s is already in use (%s). Is wfgvu.service (or another wfgvu) running? "
              "Stop it first: sudo systemctl stop wfgvu" % (a.port if a.port else (cfg.get("server") or {}).get("port"), exc.strerror),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
