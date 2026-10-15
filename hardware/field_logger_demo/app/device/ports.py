"""List serial ports without opening any of them (opening one may restart the board)."""
import fnmatch

WCH_VID = 0x1A86
CHIPS = {0x7523: "CH340", 0x55D4: "CH9102"}
NAME_PATTERNS = ("/dev/cu.usbserial-*", "/dev/cu.wchusbserial*")


def identity(p):
    """Stable identity of a port for the board profile index: VID:PID plus the USB serial number if the bridge reports
    one, otherwise the port name (macOS names CH340 ports after the USB location, so the name is stable per socket)."""
    if p.get("vid") is not None:
        base = "%04X:%04X" % (p["vid"], p["pid"] or 0)
        return base + ":" + (p["serial"] or p["device"])
    return p["device"]


def list_ports(extra_candidates=(), extra_ports=()):
    """Return port dicts. extra_candidates: VID:PID strings the owner chose before. extra_ports: simulated ports."""
    from serial.tools import list_ports as lp
    out = []
    for p in lp.comports():
        vid, pid = p.vid, p.pid
        chip = CHIPS.get(pid) if vid == WCH_VID else None
        vp = ("%04X:%04X" % (vid, pid)) if vid is not None else None
        likely = (vid == WCH_VID) or any(fnmatch.fnmatch(p.device, pat) for pat in NAME_PATTERNS) or \
            (vp is not None and vp in extra_candidates)
        out.append({"device": p.device, "description": p.description if p.description != "n/a" else "",
                    "vid": vid, "pid": pid, "vidpid": vp, "serial": p.serial_number, "chip": chip, "usb": vid is not None,
                    "likely": bool(likely), "simulated": False})
    for sp in extra_ports:
        out.append(dict(sp))
    for p in out:
        p["id"] = identity(p)
    out.sort(key=lambda p: (not p["likely"], not p["usb"], p["device"]))
    return out
