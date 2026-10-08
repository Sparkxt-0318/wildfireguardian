"""Shared helpers for the RoutingKit vs WildfireGuardian routing experiments.

Everything here is a *synthetic* experimental harness:
  * the road graph is the real Nangok (Gangneung) r1 chord graph from
    routing-package/fixtures/nangok_full_graph_fixture.json;
  * the fire is a generated elliptical spread ensemble (wind from WSW, the
    April 2023 Gangneung fire pattern) -- NOT a forecast;
  * heat-flux / tenability thresholds are declared assumptions.
No physical-safety claim follows from any result.
"""

import heapq
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PKG = REPO / "routing-package"
sys.path.insert(0, str(PKG))
FIXTURE = PKG / "fixtures" / "nangok_full_graph_fixture.json"
RESULTS = HERE / "results"
RK_TOOL = HERE / "rk" / "rk_tool"

CAR_SPEED = 40 / 3.6  # m/s, free-flow 40 km/h assumption of the fixture
EVAC_SPEED = float(os.environ.get("EVAC_KMH", 15)) / 3.6  # congested evacuation traffic
WALK_SPEED = 1.2  # m/s, adult walking; slower groups are a sensitivity case
DT = 1.0  # seconds; lattice used for our exact solver in these experiments
BP_STEP = 60.0  # hazard breakpoint spacing (s)

# Declared tenability assumptions (kW/m2). Illustrative, not validated.
CAR_PEAK = 10.0  # inside a vehicle (same peak budget as the fixture)
CAR_DOSE = 500.0  # kJ/m2 route dose budget (same as fixture)
WALK_PEAK = 2.5  # unprotected skin pain threshold order of magnitude
WALK_DOSE = 150.0


# ----------------------------------------------------------------- graph
def load_fixture():
    return json.loads(FIXTURE.read_text())


class Road:
    """Index-based view of the fixture graph."""

    def __init__(self, graph):
        self.graph = graph
        self.grid = graph["grid"]
        self.node_ids = [n["id"] for n in graph["nodes"]]
        self.nidx = {k: i for i, k in enumerate(self.node_ids)}
        self.xy = np.array([[n["x"], n["y"]] for n in graph["nodes"]])
        self.edge_ids = [e["id"] for e in graph["edges"]]
        self.eidx = {k: i for i, k in enumerate(self.edge_ids)}
        self.eu = np.array([self.nidx[e["u"]] for e in graph["edges"]])
        self.ev = np.array([self.nidx[e["v"]] for e in graph["edges"]])
        self.length = np.hypot(*(self.xy[self.ev] - self.xy[self.eu]).T)
        self.cells = [sorted({s["cell"] for s in e["segments"]}) for e in graph["edges"]]
        self.forbidden = [(self.eidx[a], self.eidx[b]) for a, b in graph["forbidden_turns"]]
        self.out = [[] for _ in self.node_ids]
        self.inc = [[] for _ in self.node_ids]
        for i, (u, v) in enumerate(zip(self.eu, self.ev)):
            self.out[u].append(i)
            self.inc[v].append(i)
        g = self.grid
        col = np.floor((self.xy[:, 0] - g["x0"]) / g["resolution"]).astype(int)
        row = np.floor((self.xy[:, 1] - g["y0"]) / g["resolution"]).astype(int)
        self.node_cell = row * g["width"] + col

    def travel_ms(self, speed):
        return np.maximum(1, np.ceil(self.length / speed * 1000)).astype(np.int64)

    def write_rk(self, path, speed, pedestrian=False, lattice_dt=None):
        """Write rk_tool graph text. Pedestrian graphs ignore one-way and turn rules.

        lattice_dt: use exactly the solver's ceil(len/speed/dt)*dt edge times so
        RoutingKit and our solver/checker share identical travel times.
        """
        eu, ev = list(self.eu), list(self.ev)
        if lattice_dt:
            w = list((np.maximum(1, np.ceil(self.length / speed / lattice_dt)) * lattice_dt * 1000).astype(np.int64))
        else:
            w = list(self.travel_ms(speed))
        forbidden = self.forbidden
        if pedestrian:
            have = set(zip(eu, ev))
            for u, v, ww in list(zip(eu, ev, w)):
                if (v, u) not in have:
                    eu.append(v), ev.append(u), w.append(ww)
                    have.add((v, u))
            forbidden = []
        with open(path, "w") as f:
            f.write(f"{len(self.node_ids)} {len(eu)} {len(forbidden)}\n")
            for x, y in self.xy:
                f.write(f"{x:.3f} {y:.3f}\n")
            for u, v, ww in zip(eu, ev, w):
                f.write(f"{u} {v} {ww}\n")
            for a, b in forbidden:
                f.write(f"{a} {b}\n")
        return np.array(eu), np.array(ev), np.array(w)

    def solver_graph(self, speed=CAR_SPEED, dt=DT):
        """Fixture graph re-ticked for lattice dt (geometry/segments unchanged)."""
        g = json.loads(json.dumps(self.graph))
        ticks = np.maximum(1, np.ceil(self.length / speed / dt)).astype(int)
        for e, t in zip(g["edges"], ticks):
            e["travel_ticks"] = int(t)
        return g


# ----------------------------------------------------------------- fire
def _noise(shape, rng, scale_cells):
    """Smooth multiplicative fuel noise via box-blurred white noise."""
    z = rng.normal(size=shape)
    k = max(1, int(scale_cells))
    for axis in (0, 1):
        z = np.cumsum(z, axis=axis)
        z = (np.roll(z, -k, axis=axis) - np.roll(z, k, axis=axis))
    z = (z - z.mean()) / (z.std() + 1e-9)
    return np.exp(0.25 * z)


def fire_arrival(road, *, ignition_xy, wind_to_deg, head_ros, lb_ratio, t_ignite, rng, fine=100.0):
    """Minimum-travel-time elliptical spread on a fine raster.

    Returns arrival seconds (relative to planning t=0) per hazard-grid cell,
    taking the EARLIEST arrival anywhere in each 500 m cell (conservative).
    """
    g = road.grid
    sub = int(round(g["resolution"] / fine))
    H, W = g["height"] * sub, g["width"] * sub
    # unburnable sea: east of the easternmost road node in each band (+300 m)
    band_max = np.full(g["height"], -np.inf)
    for (x, y) in road.xy:
        r = int((y - g["y0"]) // g["resolution"])
        band_max[r] = max(band_max[r], x)
    for r in range(g["height"]):  # fill empty bands from neighbours
        if not np.isfinite(band_max[r]):
            band_max[r] = max(band_max[max(0, r - 1)], band_max[min(g["height"] - 1, r + 1)])
    xs = g["x0"] + (np.arange(W) + 0.5) * fine
    burnable = np.ones((H, W), bool)
    for r in range(H):
        burnable[r] = xs <= band_max[r // sub] + 300.0
    fuel = _noise((H, W), rng, 6)
    e = math.sqrt(lb_ratio**2 - 1) / lb_ratio
    wind = math.radians(90 - wind_to_deg)  # bearing -> math angle
    nbrs = [(dr, dc) for dr in range(-2, 3) for dc in range(-2, 3)
            if (dr, dc) != (0, 0) and math.gcd(abs(dr), abs(dc)) == 1]
    steps = []
    for dr, dc in nbrs:
        ang = math.atan2(dr, dc) - wind
        ros = head_ros * (1 - e) / (1 - e * math.cos(ang))
        steps.append((dr, dc, math.hypot(dr, dc) * fine, ros))
    T = np.full((H, W), np.inf)
    ir = int((ignition_xy[1] - g["y0"]) // fine)
    ic = int((ignition_xy[0] - g["x0"]) // fine)
    T[ir, ic] = t_ignite
    heap = [(t_ignite, ir, ic)]
    while heap:
        t, r, c = heapq.heappop(heap)
        if t > T[r, c]:
            continue
        for dr, dc, dist, ros in steps:
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W and burnable[rr, cc]:
                nt = t + dist / (ros * 0.5 * (fuel[r, c] + fuel[rr, cc]))
                if nt < T[rr, cc]:
                    T[rr, cc] = nt
                    heapq.heappush(heap, (nt, rr, cc))
    cell = T.reshape(g["height"], sub, g["width"], sub).min(axis=(1, 3))
    return cell.reshape(-1)


def make_ensemble(road, n_members=5, seed=7, head_ros=None):
    """Gangneung-like scenario: ignition WSW of downtown, wind toward ENE.

    The fire ignited 40 minutes before planning time t=0.
    """
    rng = np.random.default_rng(seed)
    g = road.grid
    ignition = (g["x0"] + 7.5 * g["resolution"], g["y0"] + 9.5 * g["resolution"])
    members = []
    for m in range(n_members):
        members.append(fire_arrival(
            road,
            ignition_xy=ignition,
            wind_to_deg=65 + rng.normal(0, 12),
            head_ros=(head_ros or float(os.environ.get("HEAD_ROS", 1.1))) * math.exp(rng.normal(0, 0.25)),
            lb_ratio=3.0 + rng.uniform(-0.5, 0.5),
            t_ignite=-2400.0,
            rng=rng,
        ))
    return np.array(members)


RESIDENCE = 600.0  # s of flaming at a cell after arrival
TAU = 90.0  # s e-folding of pre-front radiant heating
Q_FRONT = 60.0  # kW/m2 at the front


def flux_at(arrival, t):
    """Incident flux (kW/m2) and flame flag at time t for arrival-time array."""
    dtf = arrival - t
    pre = Q_FRONT * np.exp(-np.clip(dtf, 0, None) / TAU)
    post = Q_FRONT * np.exp(-np.clip(t - arrival - RESIDENCE, 0, None) / 300.0)
    flux = np.where(dtf > 0, pre, np.where(t <= arrival + RESIDENCE, Q_FRONT, post))
    flux = np.where(np.isfinite(arrival), flux, 0.0)
    flame = (arrival <= t) & (t < arrival + RESIDENCE)
    return flux, flame


def hazard_tables(arrivals, horizon, monotone=False):
    """Piecewise-constant per-interval (flux, flame) tables, value = interval max."""
    bps = np.arange(0.0, horizon + BP_STEP, BP_STEP)
    out = []
    for arr in arrivals:
        fl, fm = [], []
        for a, b in zip(bps, bps[1:]):
            ts = np.linspace(a, b, 7)
            f = np.max([flux_at(arr, t)[0] for t in ts], axis=0)
            m = np.any([flux_at(arr, t)[1] for t in ts], axis=0)
            # a front arriving inside the interval: count it
            m |= (arr >= a) & (arr < b)
            fl.append(f)
            fm.append(m)
        fl, fm = np.array(fl), np.array(fm)
        if monotone:
            fl = np.maximum.accumulate(fl, axis=0)
            fm = np.logical_or.accumulate(fm, axis=0)
        out.append((fl, fm))
    return bps, out


def to_solver_hazard(road, bps, tables, ids=None, version=1):
    g = road.graph
    members = []
    for k, (fl, fm) in enumerate(tables):
        members.append({
            "id": (ids[k] if ids else f"m{k}"),
            "breakpoints": [float(b) for b in bps],
            "flux": [[round(float(v), 6) for v in row] for row in fl],
            "flame": [[bool(v) for v in row] for row in fm],
            "support": [[True] * fl.shape[1] for _ in range(fl.shape[0])],
        })
    return {
        "schema": "wfg.routing.edgegrid/1",
        "version": version,
        "graph_revision": g["revision"],
        "crs": g["crs"],
        "grid": g["grid"],
        "dt": DT,
        "time_origin": "2026-10-04T00:00:00+09:00",
        "issued_at": "2026-10-04T00:00:00+09:00",
        "available_at": "2026-10-04T00:00:00+09:00",
        "valid_from": float(bps[0]),
        "valid_until": float(bps[-1]),
        "evidence_class": "LABELLED_FIXTURE",
        "provenance": {"source": "GENERATED elliptical spread ensemble (experiment)",
                       "interpretation": "synthetic experiment; not a forecast"},
        "channels": ["flame_contact", "incident_heat_flux"],
        "unsupported_channels": ["embers", "secondary_ignition"],
        "members": members,
    }


def cell_close_times(bps, tables, peak):
    """Earliest breakpoint at which each cell becomes inadmissible (monotone hull).

    Returns seconds per cell (inf when never within the horizon); minimum over members.
    """
    close = np.full(tables[0][0].shape[1], np.inf)
    for fl, fm in tables:
        bad = (fl > peak) | fm
        bad = np.logical_or.accumulate(bad, axis=0)
        first = np.where(bad.any(axis=0), bad.argmax(axis=0), -1)
        c = np.where(first >= 0, bps[np.maximum(first, 0)], np.inf)
        close = np.minimum(close, c)
    return close


def edge_close_ms(road, cell_close, edge_cells=None):
    cells = edge_cells if edge_cells is not None else road.cells
    out = []
    for cs in cells:
        c = min(cell_close[x] for x in cs)
        out.append(int(c * 1000) if np.isfinite(c) else None)
    return out


# ----------------------------------------------------------------- RoutingKit process
class RK:
    def __init__(self):
        if not RK_TOOL.exists():
            raise SystemExit("build rk/rk_tool first: sh rk/build.sh")
        self.p = subprocess.Popen([str(RK_TOOL)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def cmd(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def setclose(self, slot, close_ms):
        self.cmd(f"CLEARCLOSE {slot}")
        pairs = [(i, c) for i, c in enumerate(close_ms) if c is not None]
        for k in range(0, len(pairs), 4000):
            chunk = pairs[k:k + 4000]
            self.cmd(f"SETCLOSE {slot} {len(chunk)} " + " ".join(f"{i} {max(0, c)}" for i, c in chunk))

    def td(self, slot, sources, targets):
        s = " ".join(f"{n} {int(t)}" for n, t in sources)
        return self.cmd(f"TD {slot} {len(sources)} {s} {len(targets)} " + " ".join(map(str, targets)))

    def tree(self, slot, sources):
        s = " ".join(f"{n} {int(t)}" for n, t in sources)
        return self.cmd(f"TDTREE {slot} {len(sources)} {s}")

    def close(self):
        self.p.stdin.write("QUIT\n")
        self.p.stdin.close()
        self.p.wait()


def save(name, obj):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(obj, indent=1, default=float))
