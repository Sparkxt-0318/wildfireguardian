"""Command line entry point: `python -m wfglink <command>`."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys


def cmd_doctor(args: argparse.Namespace) -> int:
    """Report the environment: versions, codecs, Qt platform and fonts."""
    report: dict = {"python": platform.python_version(), "machine": platform.machine(),
                    "system": platform.system(), "release": platform.release()}
    ok = True
    try:
        import numpy, scipy, cv2, av, pyarrow, pandas, yaml, matplotlib  # noqa: E401
        report["versions"] = {
            "numpy": numpy.__version__, "scipy": scipy.__version__, "opencv": cv2.__version__,
            "av": av.__version__, "pyarrow": pyarrow.__version__, "pandas": pandas.__version__,
            "pyyaml": yaml.__version__, "matplotlib": matplotlib.__version__,
        }
        report["opencv_aruco"] = hasattr(cv2, "aruco") and hasattr(cv2.aruco, "ArucoDetector")
        codecs = av.codecs_available
        report["decoders"] = {c: c in codecs for c in ("h264", "hevc", "libdav1d", "vp9", "vp8")}
        report["encoders"] = {c: c in codecs for c in ("libx264", "h264_videotoolbox")}
    except Exception as exc:  # report, do not crash
        ok = False
        report["import_error"] = repr(exc)
    try:
        if "QT_QPA_PLATFORM" not in os.environ and not args.gui:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6 import __version__ as pyside_version
        from PySide6.QtGui import QFont, QFontInfo, QGuiApplication

        from wfglink.ui.fonts import load_fonts, ui_font

        app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
        report["pyside6"] = pyside_version
        report["qt_platform"] = app.platformName()
        report["fonts_loaded"] = load_fonts()
        report["font_resolved"] = QFontInfo(ui_font(32)).family()
        report["screens"] = [
            {"name": s.name(), "size": [s.geometry().width(), s.geometry().height()],
             "dpr": s.devicePixelRatio(), "refresh_hz": round(s.refreshRate(), 1)}
            for s in app.screens()
        ]
        ok = ok and report["font_resolved"] == "Pretendard"
        del QFont
    except Exception as exc:
        ok = False
        report["qt_error"] = repr(exc)
    report["ok"] = ok
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if ok else 1


def cmd_devices(args: argparse.Namespace) -> int:
    from wfglink.io.devices import list_cameras

    print(json.dumps(list_cameras(), indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_camera_test(args: argparse.Namespace) -> int:
    from wfglink.config import load_config
    from wfglink.sitting.check_a import camera_test_cli

    return camera_test_cli(args.uid, args.out, args.seconds, load_config(local=True))


def cmd_panel_video(args: argparse.Namespace) -> int:
    from pathlib import Path

    from wfglink.sitting.panel import write_panel_video

    print(write_panel_video(Path(args.out), seconds=args.seconds))
    return 0


def cmd_booth_prep(args: argparse.Namespace) -> int:
    from wfglink.screen.booth_prep import prepare

    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    meta = prepare(args.clip, args.out, holds=tuple(args.holds), max_height=args.max_height, crop=crop,
                   source_step=args.source_step, max_seconds=args.max_seconds)
    print(json.dumps({k: meta[k] for k in ("outputs", "sidecar", "source_step", "frames_source_used")}, indent=2))
    return 0


# Commands that own their argument parsing (everything after the command name is theirs).
PASSTHROUGH = {
    "sitting1": ("wfglink.sitting.sitting1", "guided sitting 1: install check, check A, recordings, report"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfglink", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the environment (versions, codecs, Qt, fonts)")
    p.add_argument("--gui", action="store_true", help="use the native Qt platform instead of offscreen")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("devices", help="list cameras with names, uniqueIDs and backend indices")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("camera-test", help="camera permission and capture tests written as JSON (used inside the .app)")
    p.add_argument("--out", required=True)
    p.add_argument("--uid", default=None)
    p.add_argument("--seconds", type=float, default=6.0)
    p.set_defaults(func=cmd_camera_test)

    p = sub.add_parser("panel-video", help="write the iPad panel test video")
    p.add_argument("--out", default="PANEL_TEST.mp4")
    p.add_argument("--seconds", type=float, default=12.0)
    p.set_defaults(func=cmd_panel_video)

    p = sub.add_parser("booth-prep", help="prepare a clip for the booth (corner codes, held frames, sidecar)")
    p.add_argument("clip")
    p.add_argument("--out", default="data/booth")
    p.add_argument("--holds", type=int, nargs="+", default=[2, 3])
    p.add_argument("--max-height", type=int, default=1080)
    p.add_argument("--crop", default=None, help="x,y,w,h source rectangle to enlarge")
    p.add_argument("--source-step", type=int, default=None)
    p.add_argument("--max-seconds", type=float, default=None)
    p.set_defaults(func=cmd_booth_prep)

    for name, (_, help_text) in PASSTHROUGH.items():
        sub.add_parser(name, help=help_text, add_help=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in PASSTHROUGH:
        import importlib

        module = importlib.import_module(PASSTHROUGH[argv[0]][0])
        return int(module.main(argv[1:]) or 0)
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)
