"""Ground-truth fire spread: anisotropic eikonal (Dijkstra) model with spotting.

Model, kept deliberately simple (this experiment tests reconstruction, not fire
physics):
- Raster of `cell_m` cells. Arrival time is the shortest travel time on a
  16-neighbour graph (a discrete eikonal / minimum-travel-time solution, the
  same idea as FARSITE's minimum travel time method).
- Local rate of spread in direction theta: R(theta) = R_head * F(x) *
  (1 - e) / (1 - e cos(theta - wind_to)), the polar form of an ellipse with the
  ignition at its rear focus (Huygens elliptical wavelet). e follows from the
  length-to-breadth ratio LB (Alexander 1985). R_head = ros_wind_fraction *
  wind speed (Cruz and Alexander 2019 "10 percent rule of thumb").
- F(x) is a smooth lognormal fuel multiplier.
- Spotting: firebrands launch from burned cells (weighted by local spread
  rate), land downwind at lognormal distances and ignite with probability
  p_ignite after a short delay. A landing ahead of the front becomes a new
  ignition source; arrival times are recomputed with all sources. Repeated for
  a few rounds so spot fires can also throw spots.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import sparse
from scipy.ndimage import gaussian_filter
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

STENCIL = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1),
           (2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]


def length_to_breadth(wind_ms, model="alexander1985"):
    u_kmh = wind_ms * 3.6
    if model == "alexander1985":
        return 1.0 + 8.729 * (1.0 - math.exp(-0.030 * u_kmh)) ** 2.155
    raise ValueError(model)


def ellipse_e(lb):
    return math.sqrt(max(0.0, 1.0 - 1.0 / lb ** 2))


def ros_factor(theta, e):
    """Directional spread factor relative to head ROS for angle theta from the wind-to direction."""
    return (1.0 - e) / (1.0 - e * np.cos(theta))


class FireGrid:
    def __init__(self, width, height, cfg, rng):
        self.cell = cfg["cell_m"]
        self.nx = int(math.ceil(width / self.cell))
        self.ny = int(math.ceil(height / self.cell))
        self.n = self.nx * self.ny
        self.cfg = cfg
        # Convert compass "to" bearing (0 = north, clockwise) to math angle (0 = east, counter-clockwise).
        bearing_to = (cfg["wind_from_deg"] + 180.0) % 360.0
        self.wind_to_math = math.radians(90.0 - bearing_to)
        self.lb = length_to_breadth(cfg["wind_speed_ms"], cfg["lb_model"])
        self.e = ellipse_e(self.lb)
        self.r_head = cfg["ros_wind_fraction"] * cfg["wind_speed_ms"] * 60.0  # m/min
        g = gaussian_filter(rng.standard_normal((self.ny, self.nx)), cfg["fuel_corr_m"] / self.cell)
        g = (g - g.mean()) / (g.std() + 1e-12)
        s = cfg["fuel_sigma"]
        self.fuel = np.exp(s * g - 0.5 * s * s)
        self.xc = (np.arange(self.nx) + 0.5) * self.cell
        self.yc = (np.arange(self.ny) + 0.5) * self.cell
        self._build_graph()

    def idx(self, ix, iy):
        return iy * self.nx + ix

    def xy_to_idx(self, x, y):
        ix = np.clip((np.asarray(x) / self.cell).astype(int), 0, self.nx - 1)
        iy = np.clip((np.asarray(y) / self.cell).astype(int), 0, self.ny - 1)
        return iy * self.nx + ix

    def _build_graph(self):
        rows, cols, vals = [], [], []
        IY, IX = np.mgrid[0:self.ny, 0:self.nx]
        f = self.fuel
        for dx, dy in STENCIL:
            jx, jy = IX + dx, IY + dy
            ok = (jx >= 0) & (jx < self.nx) & (jy >= 0) & (jy < self.ny)
            src = (IY * self.nx + IX)[ok]
            dst = (jy * self.nx + jx)[ok]
            dist = math.hypot(dx, dy) * self.cell
            theta = math.atan2(dy, dx) - self.wind_to_math
            fac = float(ros_factor(theta, self.e))
            speed = self.r_head * fac * 0.5 * (f.ravel()[src] + f.ravel()[dst])
            rows.append(src)
            cols.append(dst)
            vals.append(dist / speed)
        n = self.n + 1  # last index = virtual super-source
        self.graph = sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                                       shape=(n, n))
        self._base_rows = np.concatenate(rows)
        self._base_cols = np.concatenate(cols)
        self._base_vals = np.concatenate(vals)

    def solve(self, sources):
        """Arrival times (min) from sources [(cell_index, start_time_min), ...]. Returns (T, owner)."""
        S = self.n
        src_idx = np.array([s[0] for s in sources], dtype=int)
        src_t = np.array([s[1] for s in sources], dtype=float) + 1e-6
        rows = np.concatenate([self._base_rows, np.full(len(src_idx), S)])
        cols = np.concatenate([self._base_cols, src_idx])
        vals = np.concatenate([self._base_vals, src_t])
        G = sparse.csr_matrix((vals, (rows, cols)), shape=(S + 1, S + 1))
        dist, pred = dijkstra(G, directed=True, indices=S, return_predecessors=True)
        T = dist[:S]
        pred = pred[:S]
        # Ownership: which source each cell's first arrival traces back to.
        owner = np.full(S, -1, dtype=int)
        best_src = {}
        for k, (c, t) in enumerate(zip(src_idx, src_t)):
            if c not in best_src or t < src_t[best_src[c]]:
                best_src[c] = k
        order = np.argsort(T)
        for c in order:
            if not np.isfinite(T[c]):
                break
            p = pred[c]
            if p == S or p < 0:
                owner[c] = best_src.get(c, -1)
            else:
                owner[c] = owner[p]
        return T, owner


def ignition_sources(fg: FireGrid, cfg, rng):
    ig = cfg["ignition"]
    if ig["type"] == "west_edge_line":
        ncol = max(1, int(ig["edge_width_m"] / fg.cell))
        y0, y1 = ig["y_range_frac"]
        iy_lo, iy_hi = int(y0 * fg.ny), int(y1 * fg.ny)
        # Smooth start-time jitter along the edge mimics an irregular incoming front.
        n = fg.ny
        jit = gaussian_filter(rng.standard_normal(n), ig["start_corr_m"] / fg.cell, mode="nearest")
        jit = (jit - jit.min()) / (jit.max() - jit.min() + 1e-12) * ig["start_jitter_min"]
        src = []
        for iy in range(iy_lo, iy_hi):
            for ix in range(ncol):
                src.append((fg.idx(ix, iy), float(jit[iy])))
        return src
    if ig["type"] == "point":
        x, y = ig["xy_m"]
        return [(int(fg.xy_to_idx(x, y)), 0.0)]
    raise ValueError(ig["type"])


def simulate_fire(fg: FireGrid, cfg, rng, t_end):
    """Run the eikonal model with spotting. Returns dict with T (ny, nx) and spot event list."""
    base = ignition_sources(fg, cfg, rng)
    n_base = len(base)
    sources = list(base)
    spots = []  # each: dict with landing, launch, time
    T, owner = fg.solve(sources)
    sp = cfg["spotting"]
    cell_area_km2 = (fg.cell / 1000.0) ** 2
    fuel_flat = fg.fuel.ravel()
    for rnd in range(sp["rounds"]):
        burned = np.where(T <= t_end)[0]
        if burned.size == 0:
            break
        lam = sp["launch_rate_per_km2"] * burned.size * cell_area_km2 / sp["rounds"]
        n_launch = rng.poisson(lam)
        w = fuel_flat[burned]
        launch_cells = rng.choice(burned, size=n_launch, p=w / w.sum())
        new = []
        for c in launch_cells:
            if rng.random() > sp["p_ignite"]:
                continue
            iy, ix = divmod(int(c), fg.nx)
            x0, y0 = fg.xc[ix], fg.yc[iy]
            d = min(sp["distance_max_m"], rng.lognormal(math.log(sp["distance_median_m"]), sp["distance_sigma_log"]))
            ang = fg.wind_to_math + math.radians(rng.normal(0, sp["direction_sigma_deg"]))
            x1, y1 = x0 + d * math.cos(ang), y0 + d * math.sin(ang)
            if not (0 <= x1 < fg.nx * fg.cell and 0 <= y1 < fg.ny * fg.cell):
                continue
            land = int(fg.xy_to_idx(x1, y1))
            t_launch = float(T[c])
            t_ign = t_launch + rng.uniform(*sp["ignition_delay_min"])
            if t_ign > t_end:
                continue
            if T[land] > t_ign + sp["min_lead_min"]:
                new.append({"cell": land, "x": float(x1), "y": float(y1), "t_ign": t_ign,
                            "launch_x": float(x0), "launch_y": float(y0), "t_launch": t_launch,
                            "flight_m": float(d), "round": rnd})
        # Keep spots that are still ahead after earlier spots in this round.
        new.sort(key=lambda s: s["t_ign"])
        for s in new:
            spots.append(s)
            sources.append((s["cell"], s["t_ign"]))
        if new:
            T, owner = fg.solve(sources)
    # Characterise each spot: owned area, lead time over a world without it, jump distance.
    T_final, owner_final = T, owner
    for k, s in enumerate(spots):
        sid = n_base + k
        s["owned_cells"] = int(np.sum((owner_final == sid) & (T_final <= t_end)))
        others = [src for j, src in enumerate(sources) if j != sid]
        T_wo, _ = fg.solve(others)
        s["lead_min"] = float(T_wo[s["cell"]] - s["t_ign"])
        burned_then = np.where(T_wo <= s["t_ign"])[0]
        if burned_then.size:
            iy, ix = np.divmod(burned_then, fg.nx)
            tree = cKDTree(np.c_[fg.xc[ix], fg.yc[iy]])
            s["jump_m"] = float(tree.query([s["x"], s["y"]])[0])
        else:
            s["jump_m"] = float("nan")
        s["source_index"] = sid
        s["significant"] = bool(s["lead_min"] >= sp["significant_lead_min"] and s["owned_cells"] > 0)
    return {"T": T_final.reshape(fg.ny, fg.nx), "owner": owner_final.reshape(fg.ny, fg.nx),
            "spots": spots, "n_base_sources": n_base, "r_head_m_min": fg.r_head, "lb": fg.lb, "e": fg.e}
