"""Group dispatch points into named spatial clusters.

Round-3 PHASE 3.

⚠ THESE ARE NOT 행정리 (administrative villages).
No authoritative 행정리 boundary shapefile is available to this project
(``docs/BLOCKERS.md``), so the grouping is a **spatial clustering of dispatch
points**, DBSCAN with eps = 500 m. A cluster may span parts of two real villages
or cover only part of one. Every artifact this module feeds carries that
statement; do not drop it.

Naming is coordinate-free by requirement: an operator reads a place name, never
a number pair. Each cluster takes the name of the **nearest named refuge** from
``rescue_routing.json/destinations``, which is real OpenStreetMap POI naming.
About half those POIs are unnamed in OSM; unnamed ones are never used as a
source, and a cluster with no named refuge within reach falls back to a
positional descriptor built from the same named set (e.g. "정자 북쪽"), never to
coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

#: DBSCAN neighbourhood radius in metres. Fixed by the Round-3 brief.
DEFAULT_EPS_M: float = 500.0
#: A single dispatch point is still a village for our purposes: it is a place a
#: 이장 must be handed a sheet for. So min_samples = 1 and DBSCAN emits no noise.
DEFAULT_MIN_SAMPLES: int = 1

#: Compass suffixes for the positional fallback, in Korean.
_BEARINGS = ((22.5, "북"), (67.5, "북동"), (112.5, "동"), (157.5, "남동"),
             (202.5, "남"), (247.5, "남서"), (292.5, "서"), (337.5, "북서"))


def _bearing_word(dx: float, dy: float) -> str:
    """Compass word for a vector, EPSG:5179 (x east, y north)."""
    deg = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    for limit, word in _BEARINGS:
        if deg < limit:
            return word
    return "북"


@dataclass
class Village:
    """A named spatial cluster of dispatch points. NOT an administrative unit."""

    cluster_id: int
    name: str
    name_basis: str
    points: list[dict] = field(default_factory=list)

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_unreachable(self) -> int:
        return sum(1 for p in self.points if p.get("unreachable"))

    @property
    def n_dispatch(self) -> int:
        return sum(1 for p in self.points if not p.get("unreachable"))

    @property
    def centroid(self) -> tuple[float, float]:
        xs = [p["x"] for p in self.points]
        ys = [p["y"] for p in self.points]
        return float(np.mean(xs)), float(np.mean(ys))

    def slug(self) -> str:
        """Filesystem-safe directory name."""
        s = "".join(c if (c.isalnum() or c in "-_가-힣") else "-" for c in self.name)
        while "--" in s:
            s = s.replace("--", "-")
        return f"{self.cluster_id:02d}-{s.strip('-') or 'unnamed'}"

    def as_dict(self) -> dict:
        cx, cy = self.centroid
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "name_basis": self.name_basis,
            "is_administrative_village": False,
            "grouping_note": "DBSCAN 공간 군집(eps=500 m). 행정리가 아닙니다.",
            "n_points": self.n_points,
            "n_dispatch": self.n_dispatch,
            "n_unreachable": self.n_unreachable,
            "centroid_5179": [cx, cy],
        }


def named_refuges(destinations: list[dict]) -> list[dict]:
    """Refuges carrying a real OSM name. `nan` and blanks are not names."""
    out = []
    for d in destinations:
        n = d.get("name")
        if not isinstance(n, str):
            continue
        s = n.strip()
        if not s or s.lower() == "nan":
            continue
        out.append(d)
    return out


def cluster_points(points: list[dict], destinations: list[dict], *,
                   eps_m: float = DEFAULT_EPS_M,
                   min_samples: int = DEFAULT_MIN_SAMPLES) -> list[Village]:
    """DBSCAN the points and give every cluster a place name.

    ``points`` must each carry ``x`` / ``y`` in EPSG:5179 metres.
    """
    from sklearn.cluster import DBSCAN

    if not points:
        return []
    xy = np.array([[p["x"], p["y"]] for p in points], float)
    labels = DBSCAN(eps=eps_m, min_samples=min_samples).fit_predict(xy)

    refuges = named_refuges(destinations)
    rxy = np.array([[r["x"], r["y"]] for r in refuges], float) if refuges else None

    villages: list[Village] = []
    for cid in sorted(set(labels)):
        members = [points[i] for i in range(len(points)) if labels[i] == cid]
        cx = float(np.mean([m["x"] for m in members]))
        cy = float(np.mean([m["y"] for m in members]))
        if rxy is None or not len(rxy):
            name, basis = f"군집 {cid + 1}", "no named refuge available"
        else:
            d = np.hypot(rxy[:, 0] - cx, rxy[:, 1] - cy)
            j = int(np.argmin(d))
            near = refuges[j]["name"].strip()
            if d[j] <= 3000.0:
                name = f"{near} 일대"
                basis = f"nearest named refuge '{near}' at {d[j]:.0f} m"
            else:
                word = _bearing_word(cx - rxy[j, 0], cy - rxy[j, 1])
                name = f"{near} {word}쪽"
                basis = (f"positional descriptor from nearest named refuge "
                         f"'{near}' at {d[j]:.0f} m, bearing {word}")
        villages.append(Village(cluster_id=int(cid) + 1, name=name,
                                name_basis=basis, points=members))

    # Two clusters can sit near the same refuge and earn the same descriptor.
    # Identical titles on two sheets is an operational hazard — a 이장 cannot
    # tell which sheet is theirs — so collisions are broken with the approximate
    # distance to that refuge. A distance is still place-based information, and
    # unlike a coordinate it is directly usable.
    # Escalate only as far as needed, because these names are READ ALOUD over a
    # village PA. A bearing ("동쪽") is natural Korean; a decimal distance
    # ("0.1km") is not, and a listener cannot act on it. So: bearing first,
    # whole kilometres only if bearings still collide, ordinal as a last resort.
    def _regroup() -> dict[str, list[Village]]:
        g: dict[str, list[Village]] = {}
        for v in villages:
            g.setdefault(v.name, []).append(v)
        return g

    if rxy is not None and len(rxy):
        for _name, group in _regroup().items():
            if len(group) < 2:
                continue
            for v in group:
                cx, cy = v.centroid
                d = np.hypot(rxy[:, 0] - cx, rxy[:, 1] - cy)
                j = int(np.argmin(d))
                near = refuges[j]["name"].strip()
                word = _bearing_word(cx - rxy[j, 0], cy - rxy[j, 1])
                v.name = f"{near} {word}쪽"
                v.name_basis += f"; disambiguated by bearing ({word})"
        for _name, group in _regroup().items():
            if len(group) < 2:
                continue
            for v in group:
                cx, cy = v.centroid
                d = np.hypot(rxy[:, 0] - cx, rxy[:, 1] - cy)
                km = max(1, int(round(float(d.min()) / 1000.0)))
                v.name = f"{v.name} {km}km"
                v.name_basis += f"; disambiguated by distance (~{km} km)"

    # Largest first: the 이장 with the most work gets the first sheet.
    villages.sort(key=lambda v: (-v.n_points, v.cluster_id))
    for i, v in enumerate(villages, start=1):
        v.cluster_id = i

    dupes = [n for n, g in _count(v.name for v in villages).items() if g > 1]
    if dupes:
        for v in villages:
            if v.name in dupes:
                v.name = f"{v.name} {v.cluster_id}"
    return villages


def _count(it):
    out: dict[str, int] = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return out


__all__ = ["Village", "cluster_points", "named_refuges", "_bearing_word",
           "DEFAULT_EPS_M", "DEFAULT_MIN_SAMPLES"]
