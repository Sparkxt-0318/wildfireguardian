"""Spot-fire finding on a 375 m grid from a time-ordered list of looks (PROTOCOL section 2, amendment 1).

A look is (time, system, cells). Systems: 'V' VIIRS overpass, 'G' GOFER hourly perimeter, 'H' Himawari AHI hour.
Processing is chronological. B = cells marked by any earlier look. Each look's new cells are clustered and every
cluster is labelled FRONT, SPOT (new candidate), GROWTH (of an earlier spot), SEPARATE (> d_max) or UNSEARCHED.
Pure numpy/scipy.
"""
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

CELL_KM = 0.375
NEVER = np.inf
D_MIN = {"V": 1.0, "H": 4.0, "G": 4.0}          # km, PROTOCOL 2.2
LINK = {"V": 0.375, "H": 2.0, "G": 2.0}         # km, clustering linkage
D_MAX = 15.0
RECENT_H = 2.0                                  # amendment 1: a look is searched only if the fire was seen <= 2 h before
MIN_AGE_H = 3.0

FRONT, SPOT, GROWTH, SEPARATE, UNSEARCHED, INTERIOR = 1, 2, 3, 4, 5, 6
LABELS = {1: "front", 2: "spot", 3: "growth", 4: "separate", 5: "unsearched", 6: "interior"}


@dataclass
class Look:
    t: float                 # hours since the fire's epoch
    system: str              # V, G, H
    rows: np.ndarray
    cols: np.ndarray
    sat: str = ""
    meta: dict = field(default_factory=dict)


def _disk(radius_cells):
    r = int(np.ceil(radius_cells))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= radius_cells * radius_cells + 1e-9


def cluster(mask, link_km):
    """Label cells of mask; cells closer than link_km (centre to centre, at least 8-connectivity) share a label."""
    rc = link_km / CELL_KM
    if rc <= 1.5:
        lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
        return lab, n
    grown = ndimage.binary_dilation(mask, structure=_disk(rc / 2.0))
    lab, n = ndimage.label(grown, structure=np.ones((3, 3), bool))
    lab = np.where(mask, lab, 0)
    # relabel compactly
    u = np.unique(lab[lab > 0])
    remap = np.zeros(lab.max() + 1, np.int64)
    remap[u] = np.arange(1, len(u) + 1)
    return remap[lab], len(u)


def edt(mask):
    """Distance (km) to the nearest True cell, and the indices of that cell. If mask is empty: inf."""
    if not mask.any():
        return np.full(mask.shape, np.inf), None
    d, ind = ndimage.distance_transform_edt(~mask, return_indices=True)
    return d * CELL_KM, ind


def hull_mask(mask):
    """Convex hull of True cells as a boolean grid (scipy Delaunay test)."""
    from scipy.spatial import ConvexHull, Delaunay
    r, c = np.nonzero(mask)
    if len(r) < 4:
        return mask.copy()
    pts = np.c_[r, c].astype(float)
    try:
        hull = ConvexHull(pts)
    except Exception:
        return mask.copy()
    hv = pts[hull.vertices]
    r0, r1, c0, c1 = int(hv[:, 0].min()), int(hv[:, 0].max()), int(hv[:, 1].min()), int(hv[:, 1].max())
    rr, cc = np.mgrid[r0:r1 + 1, c0:c1 + 1]
    tri = Delaunay(hv)
    inside = tri.find_simplex(np.c_[rr.ravel(), cc.ravel()]) >= 0
    out = np.zeros(mask.shape, bool)
    out[rr.ravel()[inside], cc.ravel()[inside]] = True
    return out | mask


def line_cells(p, q):
    """Grid cells strictly between p and q (row, col), sampled at quarter-cell steps."""
    n = int(np.ceil(np.hypot(q[0] - p[0], q[1] - p[1]) * 4))
    if n < 2:
        return np.zeros((0, 2), int)
    s = np.linspace(0, 1, n + 1)[1:-1]
    pts = np.rint(np.c_[p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1])]).astype(int)
    pts = np.unique(pts, axis=0)
    keep = ~(((pts[:, 0] == p[0]) & (pts[:, 1] == p[1])) | ((pts[:, 0] == q[0]) & (pts[:, 1] == q[1])))
    return pts[keep]


def find_spots(looks, shape, first_seen_t=None):
    """Chronological labelling. Returns (spots list of dict, arrays dict).

    arrays: first (time of first mark, any system), first_sys (system code of first mark), label (per cell, label of
    the cluster that first marked it), spot_id (id of the spot whose region the cell belongs to, -1 otherwise),
    first_by (dict system -> time of first mark by that system).
    """
    looks = sorted(looks, key=lambda L: (L.t, L.system))
    H, W = shape
    first = np.full(shape, NEVER)
    first_sys = np.zeros(shape, "U1")
    label = np.zeros(shape, np.int8)
    spot_id = np.full(shape, -1, np.int32)
    first_by = {s: np.full(shape, NEVER) for s in "VGH"}
    B = np.zeros(shape, bool)
    Bfront = np.zeros(shape, bool)
    Bspot = np.zeros(shape, bool)
    spots = []
    t_first = None
    last_look_t = None
    hull_cache = (None, None)
    for L in looks:
        m = np.zeros(shape, bool)
        ok = (L.rows >= 0) & (L.rows < H) & (L.cols >= 0) & (L.cols < W)
        m[L.rows[ok], L.cols[ok]] = True
        fb = first_by[L.system]
        upd = m & (fb == NEVER)
        fb[upd] = L.t
        new = m & ~B
        if not new.any():
            last_look_t = L.t
            continue
        if not B.any():
            first[new], first_sys[new], label[new] = L.t, L.system, FRONT
            B |= new
            Bfront |= new
            t_first = L.t if t_first is None else t_first
            last_look_t = L.t
            continue
        dmin, link = D_MIN[L.system], LINK[L.system]
        d_all, ind_all = edt(B)
        d_front, _ = edt(Bfront)
        d_spot, _ = edt(Bspot)
        lab, n = cluster(new, link)
        idx = np.arange(1, n + 1)
        c_all = np.asarray(ndimage.minimum(d_all, lab, idx)) if n else np.zeros(0)
        c_front = np.asarray(ndimage.minimum(d_front, lab, idx)) if n else np.zeros(0)
        c_spot = np.asarray(ndimage.minimum(d_spot, lab, idx)) if n else np.zeros(0)
        cls = np.zeros(n + 1, np.int8)
        is_front = np.concatenate([[False], c_front < dmin])
        # chain: clusters within d_min of this look's front clusters are front
        while True:
            fm = is_front[lab] & new
            df, _ = edt(fm)
            cf = np.asarray(ndimage.minimum(df, lab, idx))
            add = np.concatenate([[False], (cf < dmin)]) & ~is_front
            if not add.any():
                break
            is_front |= add
        cls[is_front] = FRONT
        d_now = edt(Bfront | (is_front[lab] & new))[0]   # distance to the front as seen now (B front + this look's front)
        searched = (last_look_t is not None and L.t - last_look_t <= RECENT_H and t_first is not None
                    and L.t - t_first >= MIN_AGE_H)
        need_hull = False
        for k in idx:
            if cls[k]:
                continue
            if c_spot[k - 1] < dmin:
                cls[k] = GROWTH
            elif c_all[k - 1] > D_MAX or c_all[k - 1] < dmin:
                cls[k] = SEPARATE          # far away, or adjacent to an earlier separate fire
            elif not searched:
                cls[k] = UNSEARCHED
            else:
                cls[k] = SPOT
                need_hull = True
        if need_hull:
            key = int((Bfront | Bspot).sum())
            if hull_cache[0] != key:
                hull_cache = (key, hull_mask(Bfront | Bspot))
            hm = hull_cache[1]
            for k in idx:
                if cls[k] == SPOT:
                    cells = lab == k
                    r, c = np.nonzero(cells)
                    if hm[int(round(r.mean())), int(round(c.mean()))]:
                        cls[k] = INTERIOR
        # assign spot ids and record candidates
        ind_s = edt(Bspot)[1] if (cls == GROWTH).any() else None
        for k in idx:
            cells = lab == k
            if cls[k] == GROWTH:
                r, c = np.nonzero(cells)
                j = np.argmin(d_spot[r, c])
                sid = spot_id[ind_s[0][r[j], c[j]], ind_s[1][r[j], c[j]]]
                spot_id[cells] = sid
                spots[sid]["growth_cells"] += int(cells.sum())
            elif cls[k] == SPOT:
                r, c = np.nonzero(cells)
                j = int(np.argmin(d_all[r, c]))
                p = (r[j], c[j])
                q = (ind_all[0][p], ind_all[1][p])
                sid = len(spots)
                spot_id[cells] = sid
                spots.append(dict(spot=sid, t=L.t, system=L.system, sat=L.sat, n_cells=int(cells.sum()),
                                  dist_km=float(c_all[k - 1]), dist_now_km=float(d_now[cells].min()), r=float(r.mean()), c=float(c.mean()),
                                  near_r=int(p[0]), near_c=int(p[1]), src_r=int(q[0]), src_c=int(q[1]),
                                  frp=float(L.meta["frp"][cells].sum()) if "frp" in L.meta else np.nan,
                                  growth_cells=0, gap=line_cells(p, q)))
        lab_cls = cls[lab]
        first[new], first_sys[new], label[new] = L.t, L.system, lab_cls[new]
        B |= new
        Bfront |= new & (lab_cls == FRONT) | new & (lab_cls == INTERIOR) | new & (lab_cls == UNSEARCHED)
        Bspot |= new & ((lab_cls == SPOT) | (lab_cls == GROWTH))
        last_look_t = L.t
    # confirmation (amendment 1: by a later look of the same system)
    for s in spots:
        g = s.pop("gap")
        fb = first_by[s["system"]]
        later = fb[g[:, 0], g[:, 1]] > s["t"] if len(g) else np.zeros(0, bool)
        marked = np.isfinite(fb[g[:, 0], g[:, 1]]) if len(g) else np.zeros(0, bool)
        s["gap_cells"] = int(len(g))
        s["gap_marked_later"] = int((later & marked).sum())
        s["gap_marked_any_later"] = int(sum(((first_by[x][g[:, 0], g[:, 1]] > s["t"]) &
                                             np.isfinite(first_by[x][g[:, 0], g[:, 1]])).sum() for x in "VGH")) if len(g) else 0
        s["confirmed"] = bool(s["gap_marked_later"] > 0)
    arrays = dict(first=first, first_sys=first_sys, label=label, spot_id=spot_id, first_by=first_by)
    return spots, arrays


def bearing_deg(dr, dc):
    """Grid bearing (deg clockwise from north) for a step of dr rows (down = south) and dc cols (east)."""
    return (np.degrees(np.arctan2(dc, -dr)) + 360.0) % 360.0


def angle_to_downwind(bearing, wind_from_deg):
    """Absolute angle (0-180) between a bearing and the downwind direction (wind_from + 180)."""
    dw = (wind_from_deg + 180.0) % 360.0
    a = np.abs((bearing - dw + 180.0) % 360.0 - 180.0)
    return a


def sector(a):
    return np.where(a <= 45, "down", np.where(a >= 135, "up", "cross"))
