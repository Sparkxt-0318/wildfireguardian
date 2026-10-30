"""Polygonal marching-squares approximation between affine cell centres.

Straight segments approximate the generally curved bilinear contour. Cells with
unknown values and quads touching infinity cannot determine a finite contour.
They are recorded as unsupported, never silently replaced by no emission.
The advancing direction is +grad(tau)/|grad(tau)|: tau(x)=x/R is the test.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
from .intensity import fireline_intensity, flame_length, flame_geometry


class UnsupportedGeometry(ValueError):
    """The input does not determine the requested flame geometry."""


@dataclass(frozen=True)
class AffineGrid:
    transform: tuple

    def __post_init__(self):
        value = np.asarray(self.transform, dtype=float)
        if value.shape != (6,) or not np.isfinite(value).all():
            raise ValueError("six finite affine coefficients required")
        a,b,_,d,e,_ = value
        if a*e-b*d == 0:
            raise ValueError("affine transform must be nonsingular and in metres")
        object.__setattr__(self, "transform", tuple(value))

    def xy(self, column, row):
        a,b,c,d,e,f = self.transform
        return np.array([a*column+b*row+c, d*column+e*row+f])


def as_grid(grid):
    if hasattr(grid, "transform"):
        return AffineGrid(tuple(grid.transform))
    if isinstance(grid, dict):
        value = grid.get("affine_transform", grid.get("transform"))
        if value is None and {"x0","y0","resolution","height"} <= grid.keys():
            r = grid["resolution"]
            value = (r,0,grid["x0"],0,-r,grid["y0"]+grid["height"]*r)
        if value is not None:
            return AffineGrid(tuple(value))
    return AffineGrid(tuple(grid))


@dataclass(frozen=True)
class FrontSegment:
    start_xy: tuple
    end_xy: tuple
    rate_m_s: float
    direction_xy: tuple
    kind: str
    cell: tuple
    intensity_kw_m: float
    flame_length_m: float
    flame_height_m: float
    tilt_rad: float
    tip_shift_xy: tuple


class FrontSegments(list):
    def __init__(self):
        super().__init__()
        self.unsupported_cells = []
        self.degenerate_quads = []


def _at(value, cell, shape, name):
    raw = np.asarray(value, dtype=float)
    if raw.ndim == 0:
        out = float(raw)
    elif raw.shape == shape:
        out = float(raw[cell])
    else:
        raise ValueError(name+" must be scalar or aligned [H,W]")
    if not math.isfinite(out) or out < 0:
        raise ValueError(name+" must be finite and nonnegative")
    return out


def front_segments(ignition_time_s, t, grid, residence_s=11.52, *, fuel=None):
    """Return leading and trailing polygons with source intensity and geometry.

    Equality follows a deterministic >= tie rule. Four-crossing saddle cases
    are paired using the quad-centre sign, a declared topology approximation.
    Flat quads have no identifiable moving front and are explicitly recorded.
    Negative finite ignition times are valid past ignitions; NaN is unknown,
    positive infinity is never. A finite never_time_s supplied in fuel is an
    explicit counterfactual interpolation scenario, never inferred by default.
    """
    tau = np.asarray(ignition_time_s, dtype=float)
    if tau.ndim != 2 or min(tau.shape) < 1 or not math.isfinite(float(t)):
        raise ValueError("nonempty ignition matrix and finite time required")
    if np.isneginf(tau).any():
        raise ValueError("negative infinite ignition is unsupported")
    fuel = dict(fuel or {})
    if "never_time_s" in fuel:
        sentinel = float(fuel["never_time_s"])
        if not math.isfinite(sentinel):
            raise ValueError("never_time_s must be finite")
        tau = np.where(np.isposinf(tau), sentinel, tau)
    residence = np.broadcast_to(np.asarray(residence_s, dtype=float), tau.shape)
    if np.any(~np.isfinite(residence) | (residence <= 0)):
        raise ValueError("residence_s must be positive, finite and aligned")
    g = as_grid(grid)
    a,b,_,d,e,_ = g.transform
    inverse_transpose = np.linalg.inv(np.array([[a,b],[d,e]])).T
    max_rate = float(fuel.get("ros_max_m_s", 3.0))
    if not math.isfinite(max_rate) or max_rate <= 0:
        raise ValueError("positive finite ros_max_m_s required")
    out = FrontSegments()
    h,w = tau.shape
    for row in range(h-1):
        for col in range(w-1):
            cells = [(row,col),(row,col+1),(row+1,col+1),(row+1,col)]
            val = np.array([tau[c] for c in cells])
            if np.isposinf(val).all():
                continue
            if not np.isfinite(val).all():
                out.unsupported_cells.extend(c for c,v in zip(cells,val) if not np.isfinite(v))
                continue
            xy = [g.xy(col+.5,row+.5),g.xy(col+1.5,row+.5),g.xy(col+1.5,row+1.5),g.xy(col+.5,row+1.5)]
            grad_lattice = np.array([(val[1]+val[2]-val[0]-val[3])/2, (val[2]+val[3]-val[0]-val[1])/2])
            gradient = inverse_transpose @ grad_lattice
            norm = float(np.linalg.norm(gradient))
            if norm == 0:
                out.degenerate_quads.append((row,col))
            rate = min(max_rate, 1/norm) if norm else max_rate
            direction = tuple(gradient/norm) if norm else (0.0,0.0)
            intensity = float(fireline_intensity(rate, _at(fuel.get("consumed_fuel_kg_m2",1), (row,col), tau.shape,"consumed_fuel"), _at(fuel.get("heat_of_combustion_kj_kg",18608),(row,col),tau.shape,"heat")))
            length = float(flame_length(intensity))
            height,tilt,shift = flame_geometry(length, fuel.get("wind_xy",(0,0)))
            for kind,field in (("leading",val),("trailing",val+np.array([residence[c] for c in cells]))):
                signed = field-float(t)
                crossings=[]
                for i,j in ((0,1),(1,2),(2,3),(3,0)):
                    if (signed[i]>=0) != (signed[j]>=0):
                        fraction = -signed[i]/(signed[j]-signed[i])
                        crossings.append(xy[i]+fraction*(xy[j]-xy[i]))
                if len(crossings)==4:
                    if signed.mean()>=0:
                        crossings=[crossings[0],crossings[3],crossings[1],crossings[2]]
                for i in range(0,len(crossings),2):
                    p,q=crossings[i:i+2]
                    if np.linalg.norm(q-p)>0:
                        out.append(FrontSegment(tuple(p),tuple(q),rate,direction,kind,(row,col),intensity,length,height,tilt,shift))
    out.unsupported_cells=sorted(set(out.unsupported_cells))
    return out
