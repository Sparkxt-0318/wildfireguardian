"""Setup check: `python -m wfglink doctor [--json]` (scripts/setup_mac.sh runs it last).

One line per check, each ending in OK or FAIL; a FAIL line is followed by its fix. In order:

  python    Python 3.12 (doctor.python) and, on macOS, python.org's build (doctor.pythonorg_prefix)
  packages  every pin in requirements.txt that applies here imports, at its pinned version
  fonts     Pretendard (doctor.font) loaded from assets/fonts and resolved by Qt, Hangul included
  screens   how many, their names and sizes, which is built in and which external, and the
            screen the booth takes with --screen auto; no external monitor is OK (the booth
            then uses the built-in screen)
  video     a short H.264 clip encoded and decoded in memory (PyAV)
  data      data/raw present (setup_mac.sh creates it); led_notes.yaml and the LED clips noted
  clips     the playlist's clips (booth.playlist) present in data/raw: n of m

On macOS Qt runs on its native platform so the real screens are listed; elsewhere on the
offscreen platform (a QT_QPA_PLATFORM already set wins). Built-in screens are recognised by
name like the booth does (ui.builtin_screen); on macOS CoreGraphics also says which display
is built in, and a disagreement fails the check, since the booth would pick the wrong
screen. --json prints every detail as JSON. The exit code is 0 when every check is OK.
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from wfglink import PROJECT_ROOT

# The same default as the booth's (ui.builtin_screen): macOS says "Built-in Retina Display"
# (Korean "내장 Retina 디스플레이", older Macs "Color LCD"); Linux says eDP-1, LVDS-1 or DSI-1.
BUILTIN_SCREEN = r"built-?in|내장|color lcd|^edp|^lvds|^dsi"
# Distribution name -> import name where they differ (pyobjc-framework-X imports as X).
IMPORT_NAMES = {"opencv-contrib-python-headless": "cv2", "opencv-contrib-python": "cv2",
                "opencv-python-headless": "cv2", "opencv-python": "cv2", "pyyaml": "yaml", "pyobjc-core": "objc"}
PYTHON_DOWNLOAD = "https://www.python.org/downloads/macos/"
LED_ROLES = ("led_33rpm", "led_45rpm", "led_ruler")
VIDEO_SUFFIXES = (".mp4", ".mov", ".ts", ".avi", ".webm", ".mkv", ".m4v")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""
    data: dict[str, Any] = field(default_factory=dict)


def _rel(p: Path) -> str:
    """The path relative to the wfglink folder when it lies inside (symlinks such as data/raw are kept)."""
    try:
        return str(Path(os.path.abspath(p)).relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


# python, packages --------------------------------------------------------------------------

def check_python(dc: dict[str, Any]) -> Check:
    want = str(dc.get("python", "3.12"))
    have = f"{sys.version_info[0]}.{sys.version_info[1]}"
    base = sys.base_prefix
    mac = platform.system() == "Darwin"
    org = base.startswith(str(dc.get("pythonorg_prefix", "/Library/Frameworks/Python.framework/Versions/3.12")))
    data = {"version": platform.python_version(), "base_prefix": base, "prefix": sys.prefix, "python_org": org,
            "venv": sys.prefix != base}
    fix = (f"install Python {want} from {PYTHON_DOWNLOAD} (macOS 64-bit universal2 installer), "
           "then run ./scripts/setup_mac.sh again (it rebuilds .venv)")
    if have != want:
        return Check("python", False, f"{platform.python_version()} at {base}, but wfglink needs {want}", fix, data)
    if mac and not org:
        return Check("python", False, f"{platform.python_version()} at {base}: not python.org's build", fix, data)
    where = "python.org" if org else "python.org check is for macOS only"
    venv = "in .venv" if sys.prefix != base else "not in a venv"
    return Check("python", True, f"{platform.python_version()} at {base} ({where}), {venv}", "", data)


def _marker_applies(marker: str) -> bool:
    try:
        from packaging.markers import Marker

        return bool(Marker(marker).evaluate())
    except ImportError:    # packaging is not installed yet: the platform markers requirements.txt uses
        m = re.fullmatch(r"""sys_platform\s*(==|!=)\s*["']([^"']+)["']""", marker.strip())
        if not m:
            return True
        return (sys.platform == m.group(2)) == (m.group(1) == "==")


def pinned_requirements(path: Path) -> list[tuple[str, str]]:
    """(distribution, version) for every exact pin in requirements.txt that applies to this platform."""
    pins = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        spec, _, marker = line.partition(";")
        name, sep, version = spec.partition("==")
        if not sep or (marker.strip() and not _marker_applies(marker.strip())):
            continue
        pins.append((name.strip(), version.strip()))
    return pins


def import_name(dist: str) -> str:
    key = dist.lower()
    if key in IMPORT_NAMES:
        return IMPORT_NAMES[key]
    if key.startswith("pyobjc-framework-"):
        return dist[len("pyobjc-framework-"):]
    return dist.replace("-", "_")


def check_packages(req: Path) -> Check:
    from importlib import metadata

    fix = ".venv/bin/python -m pip install -r requirements.txt (from the wfglink folder; needs internet)"
    try:
        pins = pinned_requirements(req)
    except OSError as exc:
        return Check("packages", False, f"cannot read {_rel(req)}: {exc}", "refresh the worktree (the file is in git)")
    wrong: list[str] = []
    found: dict[str, str | None] = {}
    for dist, version in pins:
        try:
            have = metadata.version(dist)
        except metadata.PackageNotFoundError:
            have = None
        found[dist] = have
        if have is None:
            wrong.append(f"{dist} missing")
            continue
        if have != version:
            wrong.append(f"{dist} {have} (pinned {version})")
            continue
        try:
            importlib.import_module(import_name(dist))
        except Exception as exc:     # a broken binary wheel raises all sorts of errors
            wrong.append(f"{dist} does not import ({type(exc).__name__}: {str(exc)[:60]})")
    data = {"pins": dict(pins), "installed": found, "problems": wrong}
    if wrong:
        return Check("packages", False, f"{len(wrong)} of {len(pins)} pinned packages wrong: {'; '.join(wrong)}", fix, data)
    return Check("packages", True, f"all {len(pins)} pinned packages import at their pinned versions", "", data)


# Qt: fonts, screens ------------------------------------------------------------------------

def qt_app():
    """The QGuiApplication: macOS native (real screens), offscreen elsewhere."""
    if platform.system() != "Darwin":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication(sys.argv[:1])


def check_fonts(dc: dict[str, Any]) -> Check:
    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetrics

    from wfglink.ui.fonts import FONT_DIR, load_fonts, ui_font

    want = str(dc.get("font", "Pretendard"))
    files = sorted(p.name for p in FONT_DIR.glob("*.otf"))
    families = load_fonts()
    resolved = QFontInfo(ui_font(32)).family()
    order = ["Regular", "Medium", "SemiBold", "Bold"]
    styles = sorted(QFontDatabase.styles(want) if want in families else [],
                    key=lambda s: order.index(s) if s in order else len(order))
    hangul = want in families and QFontMetrics(QFont(want)).inFont("불")
    data = {"files": files, "families": families, "resolved": resolved, "styles": styles, "hangul": hangul,
            "qt_platform": qt_app().platformName()}
    fix = (f"the font files are part of the repository (assets/fonts/{want}-*.otf): refresh the worktree, "
           "git -C ~/wfglink-run checkout --detach origin/claude/practical-rubin-5vu12u")
    if want not in families:
        return Check("fonts", False, f"{want} not loaded ({len(files)} OTF files in {_rel(FONT_DIR)})", fix, data)
    if resolved != want or not hangul:
        return Check("fonts", False, f"{want} loaded but Qt resolves {resolved!r}" + ("" if hangul else ", no Hangul"),
                     fix, data)
    return Check("fonts", True, f"{want} ({', '.join(styles)}) used by Qt, with Hangul", "", data)


def _cg_builtin_rects() -> list[tuple[int, int, int, int]] | None:
    """macOS: (x, y, w, h) in points of the built-in displays, from CoreGraphics; None elsewhere
    or when it cannot be asked. Qt's screen geometry uses the same global coordinates."""
    if platform.system() != "Darwin":
        return None
    try:
        import ctypes
        import ctypes.util

        cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics")
                         or "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

        class CGRect(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]

        cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                              ctypes.POINTER(ctypes.c_uint32)]
        cg.CGGetActiveDisplayList.restype = ctypes.c_int32
        cg.CGDisplayIsBuiltin.argtypes = [ctypes.c_uint32]
        cg.CGDisplayIsBuiltin.restype = ctypes.c_int
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        cg.CGDisplayBounds.restype = CGRect
        ids = (ctypes.c_uint32 * 16)()
        n = ctypes.c_uint32(0)
        if cg.CGGetActiveDisplayList(16, ids, ctypes.byref(n)) != 0:
            return None
        rects = []
        for i in range(n.value):
            if cg.CGDisplayIsBuiltin(ids[i]):
                r = cg.CGDisplayBounds(ids[i])
                rects.append((round(r.x), round(r.y), round(r.w), round(r.h)))
        return rects
    except Exception:
        return None


def classify_screens(screens: list[dict[str, Any]], primary: int, pattern: str,
                     cg_builtin: list[tuple[int, int, int, int]] | None = None) -> dict[str, Any]:
    """Which screens are built in, which external, and where the booth goes with --screen auto.

    screens: dicts with name, x, y, w, h. The booth decides by name (pattern), with the same
    rule as ui/booth_app.py choose_screen: the first screen whose name is not a built-in one,
    when a built-in one is named; else the built-in one; when no name says anything, the
    first screen that is not the main screen. cg_builtin (macOS) is the truth to check the
    names against: a mismatch means the booth may pick the wrong screen.
    """
    pat = re.compile(pattern, re.I) if pattern else None
    by_name = [bool(pat and pat.search(s.get("name") or "")) for s in screens]
    inside = [i for i, b in enumerate(by_name) if b]
    outside = [i for i, b in enumerate(by_name) if not b]
    if outside and inside:
        booth = outside[0]
    elif inside:
        booth = inside[0]
    else:
        others = [i for i in range(len(screens)) if i != primary]
        booth = others[0] if others else (primary if 0 <= primary < len(screens) else 0)
    truth = None
    if cg_builtin is not None:
        truth = [(s["x"], s["y"], s["w"], s["h"]) in cg_builtin for s in screens]
    if truth is not None or inside:
        builtin = truth if truth is not None else by_name
        labels = ["built-in" if b else "external" for b in builtin]
    else:   # nothing says which is built in: the main screen, and the others
        labels = ["main" if i == primary else "external" for i in range(len(screens))]
    mismatch = [screens[i]["name"] for i in range(len(screens)) if truth is not None and truth[i] != by_name[i]]
    return {"labels": labels, "booth": booth if screens else None, "mismatch": mismatch,
            "external": [i for i, lab in enumerate(labels) if lab == "external"]}


def check_screens(app, cfg: dict[str, Any]) -> Check:
    pattern = (cfg.get("ui") or {}).get("builtin_screen") or BUILTIN_SCREEN
    qs = app.screens()
    primary = app.primaryScreen()
    screens = [{"name": s.name() or "(no name)", "x": s.geometry().x(), "y": s.geometry().y(),
                "w": s.geometry().width(), "h": s.geometry().height(), "dpr": round(s.devicePixelRatio(), 2),
                "refresh_hz": round(s.refreshRate(), 1)} for s in qs]
    pidx = next((i for i, s in enumerate(qs) if s is primary), 0)
    plat = app.platformName()
    data: dict[str, Any] = {"qt_platform": plat, "screens": screens, "primary": pidx, "builtin_pattern": pattern}
    if not screens:
        return Check("screens", False, "Qt found no screen", "run the doctor in Terminal on the Mac, logged in", data)

    def size(s: dict[str, Any]) -> str:
        return f"{s['w']}x{s['h']}" + (f"@{s['dpr']:g}x" if s["dpr"] != 1 else "")

    if plat == "offscreen":
        names = ", ".join(f"{s['name']} {size(s)}" for s in screens)
        return Check("screens", True, f"{len(screens)}: {names} (offscreen: no real screens here)", "", data)
    c = classify_screens(screens, pidx, pattern, _cg_builtin_rects())
    data.update(c)
    names = ", ".join(f"{s['name']} {size(s)} ({lab})" for s, lab in zip(screens, c["labels"]))
    booth = screens[c["booth"]]["name"]
    if c["mismatch"]:
        ext = [screens[i]["name"] for i in c["external"]]
        screen = f'"{ext[0]}"' if ext else "primary"
        return Check("screens", False, f"{len(screens)}: {names}; the booth would take {booth}, because the name of "
                     f"{', '.join(c['mismatch'])} does not tell the booth whether it is built in",
                     f"start the booth with ./booth/booth.sh --screen {screen}, or add part of the name "
                     f"\"{c['mismatch'][0]}\" to ui.builtin_screen in configs/booth_local.yaml", data)
    if c["external"]:
        return Check("screens", True, f"{len(screens)}: {names}; the booth goes to {booth}", "", data)
    return Check("screens", True, f"{len(screens)}: {names}; no external monitor, so the booth uses {booth} "
                 "(connect the monitor before starting the booth)", "", data)


# video, data, clips ------------------------------------------------------------------------

def check_video() -> Check:
    """Encode ten 64x64 frames as H.264 into memory and decode them again."""
    import io

    import av
    import numpy as np

    codecs = av.codecs_available
    data: dict[str, Any] = {"pyav": av.__version__, "h264_decoder": "h264" in codecs, "libx264": "libx264" in codecs,
                            "videotoolbox": "h264_videotoolbox" in codecs}
    fix = ".venv/bin/python -m pip install --force-reinstall -r requirements.txt (from the wfglink folder)"
    if not data["h264_decoder"]:
        return Check("video", False, "PyAV has no H.264 decoder", fix, data)
    if not data["libx264"]:
        return Check("video", True, "H.264 decoder present (no libx264 encoder to test it with)", "", data)
    try:
        buf = io.BytesIO()
        with av.open(buf, "w", format="mp4") as out:
            st = out.add_stream("libx264", rate=30)
            st.width, st.height, st.pix_fmt = 64, 64, "yuv420p"
            for i in range(10):
                img = np.full((64, 64, 3), 20 * i, np.uint8)
                for pkt in st.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
                    out.mux(pkt)
            for pkt in st.encode():
                out.mux(pkt)
        buf.seek(0)
        with av.open(buf) as inp:
            codec = inp.streams.video[0].codec_context.name
            n = sum(1 for _ in inp.decode(video=0))
    except Exception as exc:
        return Check("video", False, f"H.264 test clip failed: {type(exc).__name__}: {str(exc)[:80]}", fix, data)
    data.update({"decoded_frames": n, "codec": codec})
    if n != 10 or codec != "h264":
        return Check("video", False, f"H.264 test clip: {n} of 10 frames decoded ({codec})", fix, data)
    return Check("video", True, f"H.264 encoded and decoded (PyAV {av.__version__})", "", data)


def check_data() -> Check:
    raw = PROJECT_ROOT / "data" / "raw"
    if not raw.is_dir():
        return Check("data", False, "data/raw is missing", "run ./scripts/setup_mac.sh (it creates data/raw)",
                     {"raw": str(raw)})
    notes = (raw / "led_notes.yaml").exists()
    led = [r for r in LED_ROLES if any(p.suffix.lower() in VIDEO_SUFFIXES for p in raw.glob(f"{r}*"))]
    data = {"raw": str(raw), "led_notes": notes, "led_clips": led}
    return Check("data", True, f"data/raw present; led_notes.yaml {'present' if notes else 'not yet there'}; "
                 f"LED clips {len(led)} of {len(LED_ROLES)}", "", data)


def playlist_clips(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """The playlist's clips (booth.playlist) and whether each video file is there; setup_mac.sh
    downloads the missing ones that data/clips_manifest.yaml lists. An entry names a clip id
    (data/clips/<id>.yaml), a clip settings file or a video file, as in io/playlist.py."""
    import yaml

    if cfg is None:
        from wfglink.config import load_config

        cfg = load_config(local=True)
    path = Path((cfg.get("booth") or {}).get("playlist") or "booth/playlist.yaml")
    path = path if path.is_absolute() else PROJECT_ROOT / path
    out: dict[str, Any] = {"playlist": _rel(path), "clips": [], "error": None}
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        out["error"] = f"cannot read {_rel(path)}: {type(exc).__name__}"
        return out
    try:
        manifest = {c["id"] for c in yaml.safe_load((PROJECT_ROOT / "data" / "clips_manifest.yaml")
                                                    .read_text(encoding="utf-8"))["clips"]}
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        manifest = set()
    entries = doc.get("clips") if isinstance(doc, dict) else doc
    for e in entries if isinstance(entries, list) else []:
        spec = str((e.get("clip") if isinstance(e, dict) else e) or "")
        p = Path(spec)
        if not p.suffix and len(p.parts) == 1:
            p = Path("data") / "clips" / f"{spec}.yaml"
        p = p if p.is_absolute() else PROJECT_ROOT / p
        key, video = p.stem, p
        if p.suffix.lower() in (".yaml", ".yml"):
            try:
                cc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                key = str(cc.get("clip_id") or p.stem)
                video = Path(cc["file"]) if Path(cc["file"]).is_absolute() else PROJECT_ROOT / cc["file"]
            except (OSError, yaml.YAMLError, KeyError, TypeError):
                video = None
        out["clips"].append({"id": key, "file": _rel(video) if video else None,
                             "present": bool(video and video.exists()), "downloadable": key in manifest})
    return out


def check_clips(cfg: dict[str, Any]) -> Check:
    pc = playlist_clips(cfg)
    if pc["error"]:
        return Check("clips", False, pc["error"], "refresh the worktree (booth/playlist.yaml is in git)", pc)
    clips = pc["clips"]
    have = [c for c in clips if c["present"]]
    detail = f"{len(have)} of {len(clips)} playlist clips in data/raw ({pc['playlist']})"
    if not clips:
        return Check("clips", False, f"{pc['playlist']} lists no clip", "refresh the worktree", pc)
    if len(have) == len(clips):
        return Check("clips", True, detail, "", pc)
    missing = [c for c in clips if not c["present"]]
    fetch = [c["id"] for c in missing if c["downloadable"]]
    by_hand = [c["file"] or c["id"] for c in missing if not c["downloadable"]]
    fixes = []
    if fetch:
        fixes.append(f"run ./scripts/setup_mac.sh while online, or python scripts/fetch_clips.py --only {' '.join(fetch)}")
    if by_hand:
        fixes.append(f"copy {', '.join(by_hand)} into place by hand")
    return Check("clips", False, f"{detail}; missing: {', '.join(c['id'] for c in missing)}", "; ".join(fixes), pc)


# Running -----------------------------------------------------------------------------------

def run_checks(cfg: dict[str, Any] | None = None) -> list[Check]:
    if cfg is None:
        from wfglink.config import load_config

        cfg = load_config(local=True)
    dc = cfg.get("doctor") or {}
    checks = [check_python(dc), check_packages(PROJECT_ROOT / "requirements.txt")]
    pkg_fix = checks[1].fix or "fix the packages line first"
    try:
        app = qt_app()
    except Exception as exc:
        app = None
        qt_error = f"Qt does not start: {type(exc).__name__}: {str(exc)[:80]}"
    for name, fn in (("fonts", lambda: check_fonts(dc)), ("screens", lambda: check_screens(app, cfg))):
        if app is None:
            checks.append(Check(name, False, qt_error, pkg_fix))
            continue
        try:
            checks.append(fn())
        except Exception as exc:
            checks.append(Check(name, False, f"{type(exc).__name__}: {str(exc)[:100]}", pkg_fix))
    for name, fn in (("video", check_video), ("data", check_data), ("clips", lambda: check_clips(cfg))):
        try:
            checks.append(fn())
        except Exception as exc:
            checks.append(Check(name, False, f"{type(exc).__name__}: {str(exc)[:100]}", pkg_fix))
    return checks


def _width(text: str) -> int:
    """Terminal columns (Hangul and other wide characters take two)."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def format_line(c: Check, width: int = 78) -> str:
    text = f"{c.name:<9} {c.detail}"
    status = "OK" if c.ok else "FAIL"
    line = text + " " * max(1, width - _width(text) - len(status)) + status
    if not c.ok and c.fix:
        line += f"\n{'':<10}fix: {c.fix}"
    return line


def main(json_out: bool = False) -> int:
    checks = run_checks()
    ok = all(c.ok for c in checks)
    if json_out:
        print(json.dumps({"ok": ok, "system": platform.system(), "release": platform.release(),
                          "machine": platform.machine(), "checks": [asdict(c) for c in checks]},
                         indent=2, ensure_ascii=False, default=str))
    else:
        for c in checks:
            print(format_line(c), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main("--json" in sys.argv[1:]))
