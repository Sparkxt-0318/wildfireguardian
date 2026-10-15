"""The session library: sessions/sessions.json (keys 1 to 9 for the start screen) plus any other file under sessions/."""
import json
import threading
from pathlib import Path

from . import config, geo, session

_lock = threading.RLock()
_cache = {}


def _read():
    try:
        return json.loads(config.LIBRARY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _write(items):
    config.LIBRARY_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def safe_path(rel):
    """Resolve a path relative to sessions/ and refuse anything outside it."""
    p = (config.SESSIONS / rel).resolve()
    if config.SESSIONS.resolve() not in p.parents:
        raise ValueError("path outside sessions/")
    return p


def load(path):
    """Decoded Session, cached by path and modification time."""
    p = Path(path)
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    with _lock:
        hit = _cache.get(str(p))
        if hit and hit[0] == key:
            return hit[1]
    s = session.load_any(p)
    with _lock:
        _cache[str(p)] = (key, s)
    return s


def info(entry):
    """Card data for the start screen."""
    out = dict(entry)
    try:
        s = load(safe_path(entry["file"]))
    except (OSError, ValueError) as e:
        out.update({"missing": True, "error": str(e)})
        return out
    out.update({"missing": False, "sim": s.sim, "mode": s.mode, "sid": s.sid, "source": s.source,
                "duration_s": (s.rows[-1]["t"] - s.rows[0]["t"] + 1.0) if s.rows else 0, "utc0": s.first_utc(),
                "tz": entry.get("tz") or _tz_of(s), "sha256": s.sha256})
    return out


def _tz_of(s):
    fix = next((r for r in s.rows if r["fix"] and r["lat"] is not None), None)
    return (geo.tz_for(fix["lat"], fix["lon"]) if fix else None) or config.DEFAULT_TZ


def entries():
    return [info(e) for e in _read()]


def by_key(key):
    for e in _read():
        if e.get("key") == key:
            return e
    return None


def entry_for_file(rel):
    """A library entry for a file; files that are not in sessions.json get defaults (privacy zones on)."""
    for e in _read():
        if e.get("file") == rel:
            return e
    sim = rel.startswith("sim/")
    return {"key": None, "file": rel, "title_ko": None, "title_en": None, "area": None, "tz": None,
            "marks_are_stops": False, "privacy": {"auto_zones": True, "radius_m": 150}, "sim": sim}


def add(rel, title_ko=None, title_en=None, tz=None, area=None):
    """Add a pulled or copied session to the library under the next free key (1 to 9); returns the entry."""
    with _lock:
        items = _read()
        for e in items:
            if e.get("file") == rel:
                return e
        used = {e.get("key") for e in items}
        key = next((k for k in range(1, 10) if k not in used), None)
        s = load(safe_path(rel))
        mode_ko = {"WALK": "도보", "VEHICLE": "차량"}.get(s.mode, "미지정")
        mode_en = {"WALK": "Walk", "VEHICLE": "Vehicle"}.get(s.mode, "Unknown")
        fix = next((r for r in s.rows if r["fix"] and r["lat"] is not None), None)
        here = geo.tz_for(fix["lat"], fix["lon"]) if fix else None
        e = {"key": key, "file": rel, "title_ko": title_ko or "%s · %s" % (mode_ko, s.sid[-6:]),
             "title_en": title_en or "%s · %s" % (mode_en, s.sid[-6:]), "area": area,
             "tz": tz or here or config.DEFAULT_TZ,
             "marks_are_stops": False, "privacy": {"auto_zones": True, "radius_m": 150}}
        items.append(e)
        items.sort(key=lambda x: (x.get("key") is None, x.get("key") or 0))
        _write(items)
        return e


def all_files():
    """Every session file under sessions/ (for the 'all recordings' list)."""
    out = []
    for p in sorted(config.SESSIONS.rglob("*")):
        ext = p.suffix.lower()
        if ext not in (".wfg", ".csv", ".gpx") or not p.is_file():
            continue
        if ext != ".wfg" and p.with_suffix(".wfg").exists():
            continue   # the CSV and GPX that usb_export.py writes next to a .wfg are copies of it
        out.append(str(p.relative_to(config.SESSIONS)))
    return out
