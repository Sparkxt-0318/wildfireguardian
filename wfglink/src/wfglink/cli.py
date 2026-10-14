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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfglink", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the environment (versions, codecs, Qt, fonts)")
    p.add_argument("--gui", action="store_true", help="use the native Qt platform instead of offscreen")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)
