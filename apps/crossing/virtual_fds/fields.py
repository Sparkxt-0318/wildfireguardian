"""FDS volume frames for the virtual vehicle unit: loading, composite, trilinear sampling and truth metrics.

Data model
----------
A `Field` is one snapshot on a uniform cell-centred grid, arrays ordered [z, y, x] as in the C064 npz files:
temperature in K, soot density in kg/m3, HRRPUV in kW/m3. Cell centres x0 + i*dx etc. (1 m cells in C064).
The FDS case is flat ground at z = 0; the fire spreads towards +x (wind 4.6 m/s from 270 deg, i.e. towards +x).

Two C064 products are used (both outside the repository, read-only; paths and sha256 in REPORT.md):
- `csiro-volume-dt5-120.npz`: whole domain x -9.5..109.5, y -59.5..59.5, z 0.5..19.5, every 5 s (0..120 s).
- `c064-roi1-full.npz`: the region x 30.5..69.5, y -19.5..19.5 every ~1 s. It was checked here to be bit-identical
  to the 5 s product on every common frame and cell (same deterministic run), so the two can be combined.

Composite 1 s frames (`compose`): inside the ROI the 1 s values are used unchanged. Outside it, the nearest 5 s
snapshot is used, shifted along x by round(R * (t - t5)) cells with R the measured spread rate ("frozen field
advected with the head"). That is an approximation for the parts of the scene outside the ROI (plume ahead of the
head, burnt area behind it, the flanks beyond |y| = 20 m); the flame itself is inside the ROI for the 1 s windows
used here. It is stated in REPORT.md and quantified there.

Sampling (`Sampler`): trilinear between cell centres; within half a cell of the outer faces the edge value is held;
outside the grid the ambient value is returned (ambient air at the FDS TMPA = 32 C, no soot, no HRR).

Truth (`truth_metrics`): research/kcf-heat/kcf_heat/voxel.py `front_metrics` (loaded by file path, not copied):
leading edge = downstream face of the outermost centreline (|y| <= 2.5 m) voxel above an HRRPUV threshold,
trailing edge the upstream face, depth = le - te, flame height = top face of the highest voxel above the threshold.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from crossing import _repo

T_AMBIENT_K = 32.0 + 273.15            # FDS &MISC TMPA=32. in research/kcf-heat/data/fds_rerun/input.fds
THRESHOLDS_KW_M3 = (5.0, 20.0, 100.0)
DEFAULT_FIRE_DATA = Path("/Users/jp/Documents/Codex/2026-11-16/new-chat-2/outputs/c064-refinement-study/fire-data")
DT5_NAME = "csiro-volume-dt5-120.npz"
ROI_NAME = "c064-roi1-full.npz"


@lru_cache(maxsize=1)
def voxel():
    """research/kcf-heat/kcf_heat/voxel.py loaded by path (numpy only; the package __init__ is not executed)."""
    p = _repo.KCF_HEAT / "kcf_heat" / "voxel.py"
    spec = importlib.util.spec_from_file_location("kcf_heat_voxel_by_path", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Field:
    """One snapshot. x, y, z: cell-centre coordinates (m, uniform); arrays [z, y, x]: temp_k (K), soot (kg/m3),
    hrr (kW/m3). t: simulation time (s). label: provenance string."""
    t: float
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    temp_k: np.ndarray
    soot: np.ndarray
    hrr: np.ndarray
    label: str = ""
    t_ambient_k: float = T_AMBIENT_K

    def __post_init__(self):
        for name in ("x", "y", "z"):
            a = np.asarray(getattr(self, name), dtype=float)
            if a.ndim != 1 or a.size < 2 or not np.allclose(np.diff(a), np.diff(a)[0], rtol=1e-6, atol=1e-6):
                raise ValueError(f"{name} must be a uniform 1-D grid of >= 2 cell centres")
            setattr(self, name, a)
        shape = (self.z.size, self.y.size, self.x.size)
        for name in ("temp_k", "soot", "hrr"):
            a = np.asarray(getattr(self, name), dtype=np.float32)
            if a.shape != shape:
                raise ValueError(f"{name} shape {a.shape} != {shape}")
            setattr(self, name, a)

    @property
    def d(self):
        return float(self.x[1] - self.x[0]), float(self.y[1] - self.y[0]), float(self.z[1] - self.z[0])

    def metrics(self, threshold_kw_m3: float = 20.0) -> Optional[dict]:
        return voxel().front_metrics(self.hrr.astype(float), self.x, self.y, self.z,
                                     threshold_kw_m3=threshold_kw_m3)


def truth_metrics(f: Field, thresholds: Iterable[float] = THRESHOLDS_KW_M3) -> Dict[str, Optional[dict]]:
    """front_metrics at each HRRPUV threshold, keyed '5', '20', '100'."""
    return {("%g" % th): f.metrics(th) for th in thresholds}


class Sampler:
    """Trilinear sampling of [z, y, x] cell-centred arrays (several fields stacked at once).

    `sample(px, py, pz)` returns (n_fields, N). Points outside the grid get `outside` values (per field)."""

    def __init__(self, f: Field, stack: np.ndarray, outside: Sequence[float]):
        self.x0, self.y0, self.z0 = float(f.x[0]), float(f.y[0]), float(f.z[0])
        self.dx, self.dy, self.dz = f.d
        self.nx, self.ny, self.nz = f.x.size, f.y.size, f.z.size
        s = np.asarray(stack, dtype=np.float32)
        if s.ndim == 3:
            s = s[None]
        self.nf = s.shape[0]
        self.flat = s.reshape(self.nf, -1)
        self.outside = np.asarray(outside, dtype=np.float32).reshape(self.nf, 1)
        self.lo = np.array([self.x0 - self.dx / 2, self.y0 - self.dy / 2, self.z0 - self.dz / 2])
        self.hi = np.array([self.x0 + (self.nx - 0.5) * self.dx, self.y0 + (self.ny - 0.5) * self.dy,
                            self.z0 + (self.nz - 0.5) * self.dz])

    def _axis(self, p, p0, d, n):
        f = (np.asarray(p, dtype=np.float64) - p0) / d
        i0 = np.clip(np.floor(f).astype(np.int64), 0, n - 2)
        w = np.clip(f - i0, 0.0, 1.0).astype(np.float32)
        return i0, w

    def sample(self, px, py, pz) -> np.ndarray:
        px = np.asarray(px, dtype=np.float64); py = np.asarray(py, dtype=np.float64); pz = np.asarray(pz, dtype=np.float64)
        inside = ((px >= self.lo[0]) & (px <= self.hi[0]) & (py >= self.lo[1]) & (py <= self.hi[1])
                  & (pz >= self.lo[2]) & (pz <= self.hi[2]))
        ix, wx = self._axis(px, self.x0, self.dx, self.nx)
        iy, wy = self._axis(py, self.y0, self.dy, self.ny)
        iz, wz = self._axis(pz, self.z0, self.dz, self.nz)
        out = np.zeros((self.nf, px.size), dtype=np.float32)
        nxy = self.nx * self.ny
        for dzi, fz in ((0, 1.0 - wz), (1, wz)):
            for dyi, fy in ((0, 1.0 - wy), (1, wy)):
                base = (iz + dzi) * nxy + (iy + dyi) * self.nx + ix
                fzy = fz * fy
                out += self.flat[:, base] * (fzy * (1.0 - wx))
                out += self.flat[:, base + 1] * (fzy * wx)
        return np.where(inside[None, :], out, self.outside)


class FireData:
    """Lazy access to the two C064 products. Frames are converted to `Field` on demand (temperature C -> K)."""

    def __init__(self, data_dir=DEFAULT_FIRE_DATA):
        self.dir = Path(data_dir)
        self.dt5_path = self.dir / DT5_NAME
        self.roi_path = self.dir / ROI_NAME
        self._dt5 = None
        self._roi = None

    @property
    def available(self) -> bool:
        return self.dt5_path.is_file() and self.roi_path.is_file()

    @property
    def dt5(self):
        if self._dt5 is None:
            self._dt5 = np.load(self.dt5_path)
        return self._dt5

    @property
    def roi(self):
        if self._roi is None:
            self._roi = np.load(self.roi_path)
        return self._roi

    @staticmethod
    def _field(z, k, label) -> Field:
        return Field(t=float(z["time_s"][k]), x=z["x_m"], y=z["y_m"], z=z["z_m"],
                     temp_k=z["temperature_c"][k] + np.float32(273.15), soot=z["soot_density_kg_m3"][k],
                     hrr=z["hrrpuv_kw_m3"][k], label=label)

    def dt5_times(self) -> np.ndarray:
        return np.asarray(self.dt5["time_s"], dtype=float)

    def roi_times(self) -> np.ndarray:
        return np.asarray(self.roi["time_s"], dtype=float)

    def dt5_field(self, k: int) -> Field:
        return self._field(self.dt5, k, "dt5[%d]" % k)

    def roi_field(self, k: int) -> Field:
        return self._field(self.roi, k, "roi1[%d]" % k)

    def check_roi_identity(self) -> dict:
        """Max |difference| of temperature, soot and HRRPUV between the 1 s ROI and the 5 s volume on common frames."""
        z5, z1 = self.dt5, self.roi
        ix = np.searchsorted(z5["x_m"], z1["x_m"]); iy = np.searchsorted(z5["y_m"], z1["y_m"])
        out = {"frames": 0, "max_abs_temperature_c": 0.0, "max_abs_soot": 0.0, "max_abs_hrrpuv": 0.0,
               "grid_aligned": bool(np.allclose(z5["x_m"][ix], z1["x_m"]) and np.allclose(z5["y_m"][iy], z1["y_m"]))}
        t1 = z1["time_s"]
        for k, t in enumerate(z5["time_s"]):
            j = int(np.argmin(np.abs(t1 - t)))
            if abs(t1[j] - t) > 0.05:
                continue
            out["frames"] += 1
            for key, name in (("temperature_c", "max_abs_temperature_c"), ("soot_density_kg_m3", "max_abs_soot"),
                              ("hrrpuv_kw_m3", "max_abs_hrrpuv")):
                a = z5[key][k][:, iy][:, :, ix]
                out[name] = max(out[name], float(np.abs(a - z1[key][j]).max()))
        return out

    def compose(self, k_roi: int, spread_m_s: float) -> Field:
        """1 s composite on the 5 s grid: ROI frame k_roi inside the ROI, nearest 5 s frame (shifted by
        round(R * (t - t5)) cells along x, edge-replicated) outside it."""
        z5, z1 = self.dt5, self.roi
        t = float(z1["time_s"][k_roi])
        t5s = np.asarray(z5["time_s"], dtype=float)
        k5 = int(np.argmin(np.abs(t5s - t)))
        dx = float(z5["x_m"][1] - z5["x_m"][0])
        shift = int(round(spread_m_s * (t - t5s[k5]) / dx))
        ix = np.searchsorted(z5["x_m"], z1["x_m"]); iy = np.searchsorted(z5["y_m"], z1["y_m"])
        arrays = {}
        for key in ("temperature_c", "soot_density_kg_m3", "hrrpuv_kw_m3"):
            a = np.array(z5[key][k5], dtype=np.float32)
            if shift > 0:
                a[:, :, shift:] = a[:, :, :-shift].copy(); a[:, :, :shift] = a[:, :, shift:shift + 1]
            elif shift < 0:
                s = -shift
                a[:, :, :-s] = a[:, :, s:].copy(); a[:, :, -s:] = a[:, :, -s - 1:-s]
            a[:, iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1] = z1[key][k_roi]
            arrays[key] = a
        return Field(t=t, x=z5["x_m"], y=z5["y_m"], z=z5["z_m"], temp_k=arrays["temperature_c"] + np.float32(273.15),
                     soot=arrays["soot_density_kg_m3"], hrr=arrays["hrrpuv_kw_m3"],
                     label="composite roi1[%d] + dt5[%d] shifted %+d cells" % (k_roi, k5, shift))


def spread_fit(times: Sequence[float], positions: Sequence[float]) -> float:
    """Least-squares spread rate (m/s) of a leading-edge track (kcf_heat.voxel.spread_rate)."""
    return float(voxel().spread_rate(list(times), list(positions)))


def synthetic_slab(nx: int = 48, ny: int = 24, nz: int = 10, x_lead: float = 20.0, depth: float = 10.0,
                   height: float = 4.0, t_flame_k: float = 1250.0, soot_kg_m3: float = 3e-4, hrr: float = 600.0,
                   t: float = 0.0) -> Field:
    """SYNTHETIC test volume (no FDS data): a uniform flaming slab x in [x_lead - depth, x_lead], all y, z < height,
    on 1 m cells starting at x = 0.5, y centred on 0, z = 0.5 .. nz - 0.5. Used by the tests only."""
    x = np.arange(nx) + 0.5
    y = np.arange(ny) - (ny - 1) / 2.0
    z = np.arange(nz) + 0.5
    X = x[None, None, :]; Z = z[:, None, None]
    inside = (X >= x_lead - depth) & (X <= x_lead) & (Z <= height) & np.ones((1, ny, 1), dtype=bool)
    temp = np.where(inside, t_flame_k, T_AMBIENT_K).astype(np.float32)
    soot = np.where(inside, soot_kg_m3, 0.0).astype(np.float32)
    h = np.where(inside, hrr, 0.0).astype(np.float32)
    return Field(t=t, x=x, y=y, z=z, temp_k=temp, soot=soot, hrr=h, label="synthetic slab (not FDS)")
