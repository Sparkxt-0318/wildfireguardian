"""Privacy zones (spec section 7).

By default everything within 150 m of the first and last fix of a session is hidden, on the map, in the console and
in every export. The circle that is drawn and used for hiding has its centre moved by a random offset of up to half
the protected radius, and its radius is 1.5 times the protected radius, so it always covers the whole protected disc
while its centre does not reveal the protected point. Extra named zones (home, school) come from
sessions/privacy.json (git-ignored).

The offset is keyed with a random secret kept only on this Mac (sessions/zone_secret, git-ignored), so it is stable
between runs, yet nobody who sees a circle, a session's SHA-256 (it is in summary.json) or a zone's name can work out
the offset and move the circle back onto the hidden point. A named zone is drawn only when it hides part of the
session shown (page_zones): one the route does not touch would only show where it is.
"""
import hashlib
import hmac
import json
import math
import random
import secrets
import threading

from . import config
from .geo import Local, haversine

_SECRET = {"path": None, "value": None}
_SECRET_LOCK = threading.Lock()

DEFAULT_RADIUS_M = 150.0


def load_named_zones(path=None):
    p = path or config.PRIVACY_FILE
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for z in items:
        try:
            out.append({"name": str(z.get("name", "zone")), "lat": float(z["lat"]), "lon": float(z["lon"]),
                        "radius_m": float(z.get("radius_m", DEFAULT_RADIUS_M))})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def secret():
    """The key of the circle offsets: 32 random bytes, written to sessions/zone_secret on first use."""
    p = config.ZONE_SECRET_FILE
    with _SECRET_LOCK:
        if _SECRET["path"] == p and _SECRET["value"]:
            return _SECRET["value"]
        try:
            v = p.read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            v = ""
        if len(v) < 32:
            v = secrets.token_hex(32)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(v + "\n", encoding="ascii")
            try:
                p.chmod(0o600)
            except OSError:
                pass
        _SECRET.update(path=p, value=v)
        return v


def _offset_zone(lat, lon, r, seed_text, kind, name=None):
    key = hmac.new(secret().encode("ascii"), seed_text.encode("utf-8"), hashlib.sha256).hexdigest()
    rnd = random.Random(int(key[:16], 16))
    ang = rnd.random() * 2 * math.pi
    dist = rnd.random() * r / 2.0
    loc = Local(lat, lon)
    clat, clon = loc.ll(dist * math.cos(ang), dist * math.sin(ang))
    return {"kind": kind, "name": name, "lat": clat, "lon": clon, "radius_m": r * 1.5, "protected_m": r}


def zones_for(session, settings=None, named=None):
    """Zones for one session. settings: {"auto_zones": bool, "radius_m": number} from sessions.json."""
    st = settings or {}
    auto = st.get("auto_zones", True)
    r = float(st.get("radius_m", DEFAULT_RADIUS_M))
    zones = []
    fixes = [x for x in session.rows if x["fix"] and x["lat"] is not None]
    if auto and fixes:
        a, b = fixes[0], fixes[-1]
        zones.append(_offset_zone(a["lat"], a["lon"], r, session.sha256 + ":start", "start"))
        zones.append(_offset_zone(b["lat"], b["lon"], r, session.sha256 + ":end", "end"))
    for k, z in enumerate(named if named is not None else load_named_zones()):
        zones.append(_offset_zone(z["lat"], z["lon"], z["radius_m"], "%s:%s:%d" % (session.sha256, z["name"], k),
                                  "named", z["name"]))
    return zones


def inside(zones, lat, lon):
    if lat is None or lon is None:
        return False
    return any(haversine(lat, lon, z["lat"], z["lon"]) <= z["radius_m"] for z in zones)


def page_zones(zones, points):
    """The zones the page may draw and frame: the start and end zones, and a named zone only when one of the points
    (the session's fixes and located button marks) lies in it. Hiding always uses every zone."""
    return [z for z in zones if z["kind"] != "named" or any(inside([z], la, lo) for la, lo in points)]


MASK_BYTES = (20, 28)   # lat/lon inside a FIX/NOFIX or EVENT record: bytes 20 to 27
CRC_BYTES = (44, 48)    # the CRC is masked too: with the CRC known, 8 hidden bytes near a zone could be recovered


def mask_hex(hexstr, kind):
    """Mask the lat/lon bytes (record bytes 20 to 27) and the CRC (44 to 47) of a record inside a zone. Only FIX,
    NOFIX and EVENT records carry a position at these offsets."""
    if not hexstr or kind not in ("FIX", "NOFIX", "EVENT"):
        return hexstr
    a, b = MASK_BYTES
    c, d = CRC_BYTES
    h = hexstr[:a * 2] + "x" * ((b - a) * 2) + hexstr[b * 2:]
    return h[:c * 2] + "x" * ((d - c) * 2) + h[d * 2:]
