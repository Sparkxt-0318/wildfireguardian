"""Small geometry helpers (WGS84, metres). No map matching, no smoothing of stored positions."""
import math

R_EARTH = 6371008.8


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))


class Local:
    """Equirectangular projection around a reference point: good to centimetres over a few kilometres."""

    def __init__(self, lat0, lon0):
        self.lat0, self.lon0 = lat0, lon0
        self.ky = math.pi * R_EARTH / 180.0
        self.kx = self.ky * math.cos(math.radians(lat0))

    def xy(self, lat, lon):
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky

    def ll(self, x, y):
        return self.lat0 + y / self.ky, self.lon0 + x / self.kx


def median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        return None
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


def spread_p90(values):
    """The 90th percentile of a stop's distances (spec 6.7) by nearest rank, never the single largest value: "a single
    outlier must not delete a real stop". A linear 90th percentile of 10 or fewer fixes still gives the farthest one
    10 % or more of the weight, so one stray fix could push a short stop over R_max."""
    s = sorted(values)
    if not s:
        return None
    n = len(s)
    rank = (9 * n + 9) // 10                     # ceil(0.9 n), in integers
    return s[max(0, min(rank - 1, n - 2))]


# Time zones for clock labels, from where a session was recorded (labels only; durations never use UTC). Boxes are
# checked in order; the first that holds the point wins.
TZ_BOXES = (
    ("Asia/Seoul", 33.0, 124.5, 38.7, 131.0),
    ("Asia/Tokyo", 24.0, 129.5, 46.0, 146.0),
    ("Asia/Taipei", 21.8, 119.3, 25.4, 122.2),
    ("Asia/Hong_Kong", 22.13, 113.82, 22.57, 114.45),
    ("Asia/Shanghai", 18.0, 73.0, 53.6, 135.1),
)


def tz_for(lat, lon):
    """The time zone of a place (Korea, Japan, Taiwan, Hong Kong, mainland China), or None elsewhere."""
    if lat is None or lon is None:
        return None
    for name, s, w, n, e in TZ_BOXES:
        if s <= lat <= n and w <= lon <= e:
            return name
    return None
