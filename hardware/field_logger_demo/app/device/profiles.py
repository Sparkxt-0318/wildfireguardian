"""Board profiles (git-ignored): devices/<device_id>.json, and devices/index.json mapping a port identity to the
device id, because the id is only known after HELLO but the open method must be chosen before opening."""
import datetime as dt
import json

from .. import config


def _read(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p, data):
    config.DEVICES.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def index():
    return _read(config.DEVICES / "index.json", {})


def load(device_id):
    return _read(config.DEVICES / ("%s.json" % device_id), None)


def for_port(port_id):
    """The profile to use before opening this port: by its identity, else the only profile there is."""
    idx = index()
    dev = idx.get(port_id)
    if dev:
        return load(dev)
    ids = sorted(set(idx.values()))
    if len(ids) == 1:
        return load(ids[0])
    return None


def remember_port(port_id, device_id):
    idx = index()
    if idx.get(port_id) != device_id:
        idx[port_id] = device_id
        _write(config.DEVICES / "index.json", idx)


def update(device_id, **fields):
    prof = load(device_id) or {"device_id": device_id}
    prof.update(fields)
    prof["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    _write(config.DEVICES / ("%s.json" % device_id), prof)
    return prof


def open_method(profile):
    if profile and profile.get("open_method") in ("default", "lines_low"):
        return profile["open_method"]
    return "default"


def reconnect_allowed(profile):
    return bool(profile and profile.get("reconnect_ok"))
