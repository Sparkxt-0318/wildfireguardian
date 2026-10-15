"""Dashcam recordings for the LED suite: file names, led_notes.yaml, the date-stamp mask and stills.

The dashcam's files are copied into data/raw under fixed names (plan 4.4 as changed on
2026-10-15):

    led_33rpm.*  led_45rpm.*  led_ruler.*  room_test.*  night_drive.*

with any of the extensions .mp4 .mov .ts .avi in either case (dashcams write .MP4 or .AVI).
A recording the dashcam split across loop files is named _a, _b, ... in time order
(led_33rpm_a.MP4, led_33rpm_b.MP4) and analysed as consecutive parts. Next to them,
led_notes.yaml (copied from data/led_notes_template.yaml) gives the dashcam settings and the
stopwatch timings.

A dashcam burns its date and time into the picture. Those digits change every second and
would be detected as small lights, so the stamp region named in the notes is masked from
detection in every clip, and a still of each clip with the mask outlined is written next to
the report so the mask can be checked by eye.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.detect.candidates import Detector
from wfglink.pipeline import Pipeline

VIDEO_EXTS = (".mp4", ".mov", ".ts", ".avi")
OTHER_VIDEO_EXTS = (".mkv", ".m4v", ".mts", ".m2ts", ".h264", ".h265", ".hevc", ".wmv", ".3gp")
ROLES = ("led_33rpm", "led_45rpm", "led_ruler", "room_test", "night_drive")
REQUIRED = ("led_33rpm", "led_45rpm")       # the speed truth needs both; the others are reported when present
SPEEDS = {"led_33rpm": ("33", 100.0 / 3.0), "led_45rpm": ("45", 45.0)}   # notes timing suffix, nominal rpm
STAMP_POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right", "top", "bottom")
NOTES_NAME = "led_notes.yaml"
TEMPLATE = "data/led_notes_template.yaml"

_NAME_RE = re.compile(r"^(?P<role>" + "|".join(ROLES) + r")(?:_(?P<part>[a-z]))?$", re.IGNORECASE)


def files_cfg(cfg: dict) -> dict:
    v = cfg.get("validate", {}).get("led_files", {})
    return {
        "raw_dir": v.get("raw_dir", "data/raw"),
        "report": v.get("report", "results/validation/led_report.json"),
        "stills_dir": v.get("stills_dir", "led_stills"),
        "stamp_band_frac": float(v.get("stamp_band_frac", 0.10)),
        "stamp_corner_frac": float(v.get("stamp_corner_frac", 0.5)),
        "fps_tol_frac": float(v.get("fps_tol_frac", 0.02)),
        "rpm_tol_frac": float(v.get("rpm_tol_frac", 0.15)),
        "interval_tol_frac": float(v.get("interval_tol_frac", 0.25)),
        "scene_max_seconds": v.get("scene_max_seconds"),
        "still_max_width": int(v.get("still_max_width", 1920)),
    }


# File names ---------------------------------------------------------------------------------
@dataclass
class Recording:
    role: str
    files: list[Path]                      # in time order
    parts: list[str] = field(default_factory=list)   # "" for one file, else the part letters

    @property
    def label(self) -> str:
        return " + ".join(p.name for p in self.files)


def find_recordings(raw_dir: Path) -> tuple[dict[str, Recording], list[str], list[str]]:
    """Recordings by role, problems (one line each; that role is then not used) and ignored files.

    Names are matched without regard to case. A plain name and parts of the same recording
    together, two files with the same name and different extensions, and a gap in the part
    letters are problems.
    """
    raw_dir = Path(raw_dir)
    found: dict[str, dict[str, list[Path]]] = {}
    ignored: list[str] = []
    for p in sorted(raw_dir.iterdir()) if raw_dir.is_dir() else []:
        if p.name.startswith(".") or not p.is_file():
            continue
        m = _NAME_RE.match(p.stem)
        if m is None:
            if p.stem.lower().startswith(("led_", "room_test", "night_drive")) and p.suffix.lower() in (
                    VIDEO_EXTS + OTHER_VIDEO_EXTS):
                ignored.append(f"{p.name}: not a recording name this suite reads (led_33rpm, led_45rpm, led_ruler, "
                               "room_test or night_drive, optionally with _a, _b, ...)")
            continue
        if p.suffix.lower() not in VIDEO_EXTS:
            ignored.append(f"{p.name}: extension {p.suffix or '(none)'} is not one of {' '.join(VIDEO_EXTS)}")
            continue
        role, part = m.group("role").lower(), (m.group("part") or "").lower()
        found.setdefault(role, {}).setdefault(part, []).append(p)

    recs: dict[str, Recording] = {}
    problems: list[str] = []
    for role in ROLES:
        groups = found.get(role)
        if not groups:
            continue
        bad = False
        for part, paths in sorted(groups.items()):
            if len(paths) > 1:
                problems.append(f"{role}: {' and '.join(p.name for p in paths)} have the same name; keep only one")
                bad = True
        letters = sorted(k for k in groups if k)
        if "" in groups and letters:
            problems.append(f"{role}: found both {groups[''][0].name} and parts "
                            f"{', '.join(groups[k][0].name for k in letters)}; keep either one file named "
                            f"{role}.<ext> or the parts {role}_a, {role}_b, ... (not both)")
            bad = True
        if letters:
            want = [chr(ord("a") + i) for i in range(ord(letters[-1]) - ord("a") + 1)]
            missing = [k for k in want if k not in groups]
            if missing:
                problems.append(f"{role}: part {', '.join(f'{role}_{k}' for k in missing)} is missing "
                                f"(found {', '.join('_' + k for k in letters)}); parts are named _a, _b, _c, ... "
                                "in time order with no gap")
                bad = True
        if bad:
            continue
        order = letters or [""]
        recs[role] = Recording(role, [groups[k][0] for k in order], order if letters else [""])
    return recs, problems, ignored


# Notes ---------------------------------------------------------------------------------------
NOTE_HINTS = {
    "dashcam_model": 'the dashcam brand and model from its label, for example: dashcam_model: "brand model"',
    "file_type": "the file type the dashcam writes, one of mp4, mov, ts, avi, for example: file_type: mp4",
    "resolution": "the recording resolution from the dashcam menu, for example: resolution: 1920x1080",
    "fps": "the frame rate from the dashcam menu, for example: fps: 30",
    "date_stamp": ("off, or where the date and time sit in the picture: top-left, top-right, bottom-left, "
                   "bottom-right, top or bottom (or a box [x0, y0, x1, y1] in fractions of the frame), "
                   "for example: date_stamp: bottom-left"),
    "wdr_hdr": "on, off or auto, as set in the dashcam menu (WDR or HDR), for example: wdr_hdr: off",
    "camera_height_cm": "the height of the dashcam lens above the LEDs in cm, for example: camera_height_cm: 40",
    "led_radius_mm": ("the distance of each LED from the turntable centre in mm, three numbers, "
                      "for example: led_radius_mm: [30, 80, 140]"),
    "turns_timed": "how many turns you timed with the stopwatch at each speed, for example: turns_timed: 30",
    "time_33rpm_s": "the stopwatch time in seconds for those turns at 33 rpm, for example: time_33rpm_s: 54.0",
    "time_45rpm_s": "the stopwatch time in seconds for those turns at 45 rpm, for example: time_45rpm_s: 40.0",
}
OPTIONAL_HINTS = {
    "ruler_px_per_mm": "pixels per mm read off the ruler still, for example: ruler_px_per_mm: 2.4",
    "ruler_rpm": "the turntable speed during the ruler clip, 33, 45 or 0 if it stood still, for example: ruler_rpm: 0",
    "comment": 'anything else worth knowing, for example: comment: "LED 2 flickers"',
}
_RES_NAMES = {"720p": (1280, 720), "1080p": (1920, 1080), "1440p": (2560, 1440), "1600p": (2560, 1600),
              "2160p": (3840, 2160), "4k": (3840, 2160)}


def _number(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(str(v).strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def parse_stamp(value: Any) -> tuple[Any, str | None]:
    """Normalised date_stamp ('off', a position, a box [x0, y0, x1, y1] or a list of these) or an error."""
    if value is False or (isinstance(value, str) and value.strip().lower() in ("off", "none", "no")):
        return "off", None
    if isinstance(value, str):
        pos = value.strip().lower().replace("_", "-").replace(" ", "-")
        if pos in STAMP_POSITIONS:
            return pos, None
        return None, f"not off or one of {', '.join(STAMP_POSITIONS)}"
    if isinstance(value, (list, tuple)) and value:
        nums = [_number(v) for v in value]
        if len(value) == 4 and all(n is not None for n in nums):
            x0, y0, x1, y1 = nums
            if 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1:
                return [x0, y0, x1, y1], None
            return None, "not a box [x0, y0, x1, y1] with 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1"
        if all(isinstance(v, (str, list, tuple)) for v in value):
            out = []
            for v in value:
                one, err = parse_stamp(v)
                if err or one == "off":
                    return None, f"a list holding {v!r}, which is " + (err or "off and cannot be part of a list")
                out.append(one)
            return out, None
    return None, "not off, a position or a box"


def stamp_boxes(spec: Any, cfg: dict) -> list[tuple[float, float, float, float]]:
    """Masked regions as (x0, y0, x1, y1) fractions of the frame for a parsed date_stamp."""
    fc = files_cfg(cfg)
    band, corner = fc["stamp_band_frac"], fc["stamp_corner_frac"]
    if spec in (None, "off"):
        return []
    if isinstance(spec, list) and spec and all(isinstance(v, (int, float)) for v in spec):
        return [tuple(float(v) for v in spec)]
    if isinstance(spec, list):
        return [b for s in spec for b in stamp_boxes(s, cfg)]
    y = (0.0, band) if spec.startswith("top") else (1.0 - band, 1.0)
    x = {"left": (0.0, corner), "right": (1.0 - corner, 1.0)}.get(spec.split("-")[-1], (0.0, 1.0))
    return [(x[0], y[0], x[1], y[1])]


def boxes_px(boxes, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Boxes in whole pixels, rounded outward so the mask covers the whole region."""
    return [(max(0, int(math.floor(x0 * w))), max(0, int(math.floor(y0 * h))),
             min(w, int(math.ceil(x1 * w))), min(h, int(math.ceil(y1 * h)))) for x0, y0, x1, y1 in boxes]


def stamp_mask(h: int, w: int, boxes) -> np.ndarray | None:
    """uint8 mask (nonzero = not analysed) for the boxes, or None without boxes."""
    if not boxes:
        return None
    m = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in boxes_px(boxes, w, h):
        m[y0:y1, x0:x1] = 1
    return m


def load_notes(path: Path, cfg: dict) -> tuple[dict[str, Any], list[str], list[str]]:
    """Parsed notes, errors (one line per missing or malformed key, saying what to write) and warnings."""
    import yaml

    from wfglink.provenance import rel

    path = Path(path)
    name = path.name
    if not path.exists():
        return {}, [f"{rel(path)}: not found. Copy {TEMPLATE} to {rel(path)} and fill it in"], []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        first = str(exc).splitlines()[0] if str(exc) else "syntax error"
        return {}, [f"{name}: cannot be read as YAML ({first}). Compare it with {TEMPLATE}"], []
    if not isinstance(raw, dict):
        return {}, [f"{name}: should hold lines like key: value. Compare it with {TEMPLATE}"], []
    n_leds = int(cfg.get("validate", {}).get("led", {}).get("n_leds", 3))
    fc = files_cfg(cfg)
    notes: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []

    def bad(key: str, why: str) -> None:
        hint = NOTE_HINTS.get(key) or OPTIONAL_HINTS[key]
        errors.append(f"{name}: {key} {why}. Write {hint}")

    def positive(key: str, hi: float = math.inf, unit: str = "") -> None:
        x = _number(raw[key])
        if x is None or not (0 < x <= hi):
            rng = f" above 0 and at most {hi:g}{unit}" if math.isfinite(hi) else " above 0"
            bad(key, f"is {raw[key]!r}, which is not a number{rng}")
        else:
            notes[key] = x

    for key in NOTE_HINTS:
        if key not in raw or raw[key] is None or (isinstance(raw[key], str) and not raw[key].strip()):
            bad(key, "is missing")
            continue
        v = raw[key]
        if key == "dashcam_model":
            notes[key] = str(v).strip()
        elif key == "file_type":
            ft = str(v).strip().lower().lstrip(".")
            if "." + ft in VIDEO_EXTS:
                notes[key] = ft
            else:
                bad(key, f"is {v!r}, which is not one of mp4, mov, ts, avi")
        elif key == "resolution":
            res = None
            if isinstance(v, (list, tuple)) and len(v) == 2:
                res = [_number(v[0]), _number(v[1])]
            elif isinstance(v, str):
                s = v.strip().lower().replace(" ", "")
                if s in _RES_NAMES:
                    res = list(_RES_NAMES[s])
                else:
                    m = re.fullmatch(r"(\d+)[x×*](\d+)", s)
                    res = [float(m.group(1)), float(m.group(2))] if m else None
            if res and all(r is not None and r >= 16 and float(r).is_integer() for r in res):
                notes[key] = [int(res[0]), int(res[1])]
            else:
                bad(key, f"is {v!r}, which is not width x height in pixels")
        elif key == "fps":
            positive(key, 1000.0)
        elif key == "date_stamp":
            spec, err = parse_stamp(v)
            if err:
                bad(key, f"is {v!r}, which is {err}")
            else:
                notes[key] = spec
        elif key == "wdr_hdr":
            s = ("on" if v else "off") if isinstance(v, bool) else str(v).strip().lower()
            if s in ("on", "off", "auto"):
                notes[key] = s
            else:
                bad(key, f"is {v!r}, which is not on, off or auto")
        elif key == "camera_height_cm":
            positive(key, 500.0, " cm")
        elif key == "led_radius_mm":
            nums = [_number(r) for r in v] if isinstance(v, (list, tuple)) else []
            if (len(nums) != n_leds or any(r is None or not (0 < r < 1000) for r in nums)
                    or len(set(nums)) != len(nums)):
                bad(key, f"is {v!r}, which is not {n_leds} different distances in mm")
            else:
                notes[key] = sorted(nums)
        elif key in ("turns_timed", "time_33rpm_s", "time_45rpm_s"):
            positive(key)
    for key in OPTIONAL_HINTS:
        if raw.get(key) is None:
            continue
        v = raw[key]
        if key == "ruler_px_per_mm":
            positive(key)
        elif key == "ruler_rpm":
            s = "0" if v is False else str(v).strip().lower()
            rpm = {"0": 0, "stopped": 0, "off": 0, "33": 33, "33.3": 33, "33.33": 33, "33 1/3": 33, "45": 45}.get(s)
            if rpm is None:
                bad(key, f"is {v!r}, which is not 33, 45 or 0")
            else:
                notes[key] = rpm
        else:
            notes[key] = str(v)
    for key in raw:
        if key not in NOTE_HINTS and key not in OPTIONAL_HINTS:
            warnings.append(f"{name}: unknown key {key} is ignored (check its spelling against {TEMPLATE})")

    # Plausibility: the timings should give about 33 1/3 and 45 rpm.
    if "turns_timed" in notes:
        for role, (suffix, nominal) in SPEEDS.items():
            key = f"time_{suffix}rpm_s"
            if key in notes:
                rpm = 60.0 * notes["turns_timed"] / notes[key]
                if abs(rpm / nominal - 1) > fc["rpm_tol_frac"]:
                    warnings.append(f"{name}: turns_timed {notes['turns_timed']:g} in {key} {notes[key]:g} s gives "
                                    f"{rpm:.1f} rpm, not about {nominal:.1f}; check both values")
    if notes.get("wdr_hdr") == "on":
        warnings.append(f"{name}: wdr_hdr is on; WDR or HDR can blur or double fast lights. If the dashcam menu "
                        "allows it, turn it off for the LED clips")
    return notes, errors, warnings


def omega_from_notes(notes: dict[str, Any], role: str) -> float | None:
    """Stopwatch angular speed in rad/s: 2 pi turns_timed / time for that speed (None without timing)."""
    suffix = SPEEDS.get(role, (None,))[0]
    if role == "led_ruler":
        suffix = {33: "33", 45: "45"}.get(notes.get("ruler_rpm"))
    t = notes.get(f"time_{suffix}rpm_s") if suffix else None
    turns = notes.get("turns_timed")
    if not t or not turns:
        return None
    return 2 * math.pi * turns / t


# File facts ----------------------------------------------------------------------------------
def probe_file(path: Path) -> dict[str, Any]:
    """Container facts of one file: size, codec, nominal fps, duration (or the error)."""
    from wfglink.io.sources import FileSource

    src = FileSource(path)
    try:
        src.open()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        src.close()
    i = src.info
    return {"width": i["width"], "height": i["height"], "codec": i["codec"],
            "fps": round(i["fps_nominal"], 3) if i.get("fps_nominal") else None,
            "duration_s": round(i["duration_s"], 2) if i.get("duration_s") else None,
            "frames_declared": i.get("frames_declared")}


def read_frames(src, errors: list[str]):
    """Frames of an opened FileSource until its end or the first decoding error, which is noted
    in errors (a dashcam file cut off by a power loss often ends in damaged data)."""
    while True:
        try:
            f = src.read()
        except Exception as exc:
            errors.append(f"{src.name}: decoding stopped early, the rest of this file is not used "
                          f"({type(exc).__name__}: {exc})")
            return
        if f is None:
            return
        yield f


def compare_with_notes(role: str, probes: dict[str, dict], notes: dict[str, Any], cfg: dict) -> list[str]:
    """Warnings where a file's resolution, frame rate or type differs from the notes."""
    tol = files_cfg(cfg)["fps_tol_frac"]
    out = []
    for name, pr in probes.items():
        if "error" in pr:
            continue
        if "resolution" in notes and [pr["width"], pr["height"]] != notes["resolution"]:
            out.append(f"{name}: {pr['width']}x{pr['height']} in the file, but the notes say resolution "
                       f"{notes['resolution'][0]}x{notes['resolution'][1]}")
        if "fps" in notes and pr.get("fps") and abs(pr["fps"] / notes["fps"] - 1) > tol:
            out.append(f"{name}: {pr['fps']:g} fps in the file, but the notes say fps {notes['fps']:g}")
        ext = Path(name).suffix.lower().lstrip(".")
        if "file_type" in notes and ext != notes["file_type"]:
            out.append(f"{name}: the file is .{ext}, but the notes say file_type {notes['file_type']}")
    return out


def timing_summary(times: list[np.ndarray], tol_frac: float, repeated: int | None = None) -> dict[str, Any]:
    """Frame timing of a recording from its decoded presentation times (one array per part)."""
    dts = [np.diff(np.asarray(t, float)) for t in times if len(t) > 1]
    d = np.concatenate(dts) if dts else np.zeros(0)
    out: dict[str, Any] = {"frames": int(sum(len(t) for t in times))}
    if repeated is not None:
        out["repeated_frames"] = int(repeated)
    back = int(np.count_nonzero(d <= 0))
    pos = d[d > 0]
    if pos.size == 0:
        out["problem"] = "no increasing timestamps"
        return out
    med = float(np.median(pos))
    gaps = pos[pos > 1.5 * med]
    # The mean rate, not 1 / median: a millisecond time base stores 29.97 fps as 33 and 34 ms steps.
    out.update({"fps_measured": round(1.0 / float(np.mean(pos)), 3), "frame_interval_median_ms": round(1000 * med, 3),
                "irregular_interval_fraction": round(float(np.mean(np.abs(pos - med) > tol_frac * med)), 4),
                "max_interval_ms": round(1000 * float(pos.max()), 2),
                "frames_missing_est": int(np.sum(np.round(gaps / med) - 1)),
                "timestamps_not_increasing": back})
    if back:
        out["warning"] = (f"timestamps go backwards or repeat {back} times; the file's timing is unreliable "
                          "(frames with such times are skipped)")
    return out


# Masked detection ----------------------------------------------------------------------------
class MaskedDetector(Detector):
    """The normal detector, never detecting inside fixed boxes (fractions of the frame)."""

    def __init__(self, cfg: dict, boxes=()):
        super().__init__(cfg)
        self.boxes = list(boxes)
        self._fixed: np.ndarray | None = None

    def detect(self, image: np.ndarray, mask: np.ndarray | None = None):
        if self.boxes:
            h, w = image.shape[:2]
            if self._fixed is None or self._fixed.shape != (h, w):
                self._fixed = stamp_mask(h, w, self.boxes)
            mask = self._fixed if mask is None else np.maximum(mask, self._fixed)
        return super().detect(image, mask)


class MaskedPipeline(Pipeline):
    """File-mode pipeline whose detector ignores the date-stamp boxes."""

    def __init__(self, cfg: dict, boxes=(), **kwargs):
        self.stamp_boxes = list(boxes)
        super().__init__(cfg, **kwargs)

    def reset(self, *args, **kwargs) -> None:
        super().reset(*args, **kwargs)
        self.detector = MaskedDetector(self.cfg, self.stamp_boxes)


# Stills -------------------------------------------------------------------------------------
def _save(path: Path, img: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    params = [cv2.IMWRITE_JPEG_QUALITY, 90] if path.suffix.lower() in (".jpg", ".jpeg") else []
    if not cv2.imwrite(str(path), img, params):
        raise OSError(f"cannot write {path}")
    return str(path)


def write_mask_still(image: np.ndarray, boxes, path: Path, cfg: dict, rings=None, title: str = "") -> str:
    """A still with the date-stamp mask outlined (cyan) and any fitted LED rings (green)."""
    img = image.copy()
    h, w = img.shape[:2]
    lw = max(2, int(round(h / 360)))
    for x0, y0, x1, y1 in boxes_px(boxes, w, h):
        over = img[y0:y1, x0:x1].astype(np.float32)
        img[y0:y1, x0:x1] = (0.6 * over + 0.4 * np.array([90, 90, 0], np.float32)).astype(np.uint8)
        cv2.rectangle(img, (x0, y0), (max(x0, x1 - 1), max(y0, y1 - 1)), (255, 255, 0), lw)
    for r in rings or []:
        (ex, ey), (ea, eb), ang = r
        cv2.ellipse(img, ((float(ex), float(ey)), (float(ea), float(eb)), float(ang)), (80, 220, 80), 1, cv2.LINE_AA)
    text = title + ("   cyan: date-stamp mask (not analysed)" if boxes else "   no date-stamp mask")
    scale = max(0.4, h / 1400)
    cv2.putText(img, text.strip(), (int(0.03 * w), int(0.18 * h)), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255, 255, 0), max(1, lw // 2), cv2.LINE_AA)
    maxw = files_cfg(cfg)["still_max_width"]
    if w > maxw:
        img = cv2.resize(img, (maxw, int(round(h * maxw / w))), interpolation=cv2.INTER_AREA)
    return _save(path, img)


def write_ruler_stills(image: np.ndarray, out_dir: Path, stem: str) -> dict[str, str]:
    """The sharp ruler still at full resolution, and the frame centre enlarged 2x, both lossless."""
    h, w = image.shape[:2]
    crop = image[h // 4: h // 4 + h // 2, w // 4: w // 4 + w // 2]
    big = cv2.resize(crop, (2 * crop.shape[1], 2 * crop.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    return {"full": _save(out_dir / f"{stem}_full.png", image),
            "centre_2x": _save(out_dir / f"{stem}_centre_2x.png", big)}


def sharpness(image: np.ndarray) -> float:
    """Variance of the Laplacian of the frame centre (larger is sharper)."""
    h, w = image.shape[:2]
    g = cv2.cvtColor(image[h // 4: 3 * h // 4, w // 4: 3 * w // 4], cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_32F).var())
