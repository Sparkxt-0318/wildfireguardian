"""Save a pulled session (spec section 3C, test step 5, and section 8 P).

usb_export.write_outputs() names the files from the session id (<sid>_<mode>.wfg, .sha256, .csv, .gpx, .geojson,
.integrity.json) and overwrites what is there, so the name is checked first: the same SHA-256 means the session is
already saved; a different SHA-256 under the same name (possible after a board is reformatted) is written into a
temporary folder and moved in with the suffix -2 (or -3, ...), with the file name inside the .wfg.sha256 rewritten.
A transfer whose bytes do not match the device is kept beside the target with the suffix .bad and nothing else is
written.
"""
import hashlib
import json
import shutil
import uuid
from pathlib import Path

from .. import config
from ..vendor import usb_export as ux

OUTPUT_EXTS = (".wfg", ".wfg.sha256", ".csv", ".gpx", ".geojson", ".integrity.json")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def reserved_sim_id(data):
    """True for a file whose START record carries the reserved SIM device id 00000000. A real logger never has it, so
    such a file is kept with the simulated data (sessions/sim/), never under sessions/real/, wherever it came from."""
    try:
        m = ux.Meta(data)
    except Exception:   # noqa: BLE001  (an unreadable start is decided by the connection alone)
        return False
    return bool(m.start) and m.start["device_id"] == 0


def target_dir(simulated, device_test):
    if simulated:
        return config.SIM_DIR / "device_double"
    return config.DEVICE_TESTS_DIR if device_test else config.REAL_DIR


def base_name(data, device_name):
    m = ux.Meta(data, device_name)
    return "%s_%s" % (m.sid, m.mode)


def save_pulled(data, device_name, out_dir, simulated=False):
    """Returns {"path": Path of the .wfg, "status": "saved" | "same" | "renamed"}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = base_name(data, device_name)
    digest = sha256(data)
    target = out_dir / (base + ".wfg")
    if not target.exists():
        ux.write_outputs(data, device_name, str(out_dir))
        _sidecar(target, simulated)
        return {"path": target, "status": "saved"}
    if sha256(target.read_bytes()) == digest:
        return {"path": target, "status": "same"}
    k = 2
    while True:
        cand = out_dir / ("%s-%d.wfg" % (base, k))
        if not cand.exists():
            break
        if sha256(cand.read_bytes()) == digest:
            return {"path": cand, "status": "same"}
        k += 1
    new_base = "%s-%d" % (base, k)
    tmp = out_dir / (".tmp_" + uuid.uuid4().hex[:8])
    try:
        ux.write_outputs(data, device_name, str(tmp))
        for ext in OUTPUT_EXTS:
            src = tmp / (base + ext)
            if src.exists():
                src.rename(out_dir / (new_base + ext))
        (out_dir / (new_base + ".wfg.sha256")).write_text("%s  %s\n" % (digest, new_base + ".wfg"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    final = out_dir / (new_base + ".wfg")
    _sidecar(final, simulated)
    return {"path": final, "status": "renamed"}


def save_bad(data, device_name, out_dir):
    """Keep a failed copy for inspection: <sid>_<mode>.wfg.bad (or the device name when the start is unreadable)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        base = base_name(data, device_name)
    except Exception:   # noqa: BLE001  (a broken first record must not stop us from keeping the bytes)
        base = device_name.replace(".wfg", "")
    p = out_dir / (base + ".wfg.bad")
    p.write_bytes(data)
    return p


def _sidecar(wfg_path, simulated):
    """Sessions from the simulated logger get a .sim.json sidecar, so they are watermarked like every SIM file."""
    if not simulated:
        return
    side = wfg_path.with_name(wfg_path.name + ".sim.json")
    side.write_text(json.dumps({"generator": "app/device/double.py", "simulated": True, "double": True,
                                "device_id": "00000000",
                                "note": "SIMULATED DEVICE: recorded by the logger double, not by real hardware."},
                               indent=1), encoding="utf-8")


def library_sha_index():
    """SHA-256 -> path (relative to sessions/) of every .wfg the laptop already has."""
    out = {}
    for p in sorted(config.SESSIONS.rglob("*.wfg")):
        if not p.is_file():
            continue
        st = p.stat()
        key = (str(p), st.st_mtime_ns, st.st_size)
        hit = _SHA_CACHE.get(key)
        if hit is None:
            hit = sha256(p.read_bytes())
            _SHA_CACHE[key] = hit
        out.setdefault(hit, str(p.relative_to(config.SESSIONS)))
    return out


_SHA_CACHE = {}
