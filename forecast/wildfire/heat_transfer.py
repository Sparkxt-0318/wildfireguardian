"""Referenced radiation scenarios and bounded finite-cell attenuation.

The grey homogeneous atmosphere is an explicit approximation to spectral
Beer--Lambert transport. Its coefficient must be supplied or calibrated; this
module does not infer smoke or humidity absorption from weather alone. NumPy is
the only eager numerical dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import heapq
import math
from numbers import Integral
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _array(value: ArrayLike, name: str, *, shape_kind: bool = False) -> FloatArray:
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} contains missing masked values")
    if np.iscomplexobj(value):
        raise ValueError(f"{name} must be real-valued")
    try:
        result = np.asarray(value, dtype=np.float64)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{name} must be real numeric") from error
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    if shape_kind and (result.ndim not in (0, 2) or (result.ndim == 2 and min(result.shape) < 1)):
        raise ValueError(f"{name} must be a scalar or a nonempty two-dimensional array")
    return result


def _scalar(value: ArrayLike, name: str) -> float:
    result = _array(value, name)
    if result.ndim != 0:
        raise ValueError(f"{name} must be scalar")
    return float(result)


def _immutable_array(value: ArrayLike) -> FloatArray:
    value = np.asarray(value, dtype=np.float64)
    # A bytes-backed array cannot be made writable using setflags(write=True).
    return np.frombuffer(value.tobytes(), dtype=np.float64).reshape(value.shape)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("provenance keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and np.isfinite(value):
        return value
    raise ValueError("provenance must contain finite JSON-compatible values")


def _provenance(value: Mapping[str, Any] | str) -> Mapping[str, Any]:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("provenance must be nonempty")
        value = {"description": value}
    if not isinstance(value, Mapping) or not value:
        raise ValueError("provenance must be a nonempty mapping or description")
    return _freeze(value)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, eq=False)
class RadiativeFractionEstimate:
    """A dimensionless source radiation fraction with explicit provenance.

    Scalars and complete [H,W] source maps are supported. The fraction is
    emitted radiant power / total released power when instantaneous, or the
    corresponding energy ratio over an identical period when energy-integrated.
    The latter does not identify a time-varying instantaneous radiation fraction.
    """

    fraction: ArrayLike
    provenance: Mapping[str, Any] | str

    def __post_init__(self) -> None:
        fraction = _array(self.fraction, "fraction", shape_kind=True)
        if np.any((fraction < 0) | (fraction > 1)):
            raise ValueError("fraction must lie in [0,1]")
        object.__setattr__(self, "fraction", _immutable_array(fraction))
        object.__setattr__(self, "provenance", _provenance(self.provenance))

    @classmethod
    def pine_litter_reference(cls) -> RadiativeFractionEstimate:
        """Return the explicitly selected 0.30 pine/litter reference scenario.

        Dietenberger and Boardman, Fire Technology 53 (2017), 577--607,
        section 4, p.592, reports experimental support for pine wood and dead
        litter. The litter validation used a 0.6 m fire under an HRR hood up to
        250 kW. This value is not a universal vegetation or crown-fire estimate.
        """
        return cls(0.30, {
            "method": "pine_litter_reference",
            "source": "Dietenberger and Boardman (2017), Fire Technology 53:577-607",
            "publication_year": 2017,
            "online_publication_year": 2016,
            "doi": "10.1007/s10694-016-0632-0",
            "url": "https://research.fs.usda.gov/treesearch/53606",
            "location": "section 4, printed page 592",
            "scope": "pine wood/dead litter reference; 0.6 m litter experiment up to 250 kW",
            "limitation": "caller-selected reference scenario, not event calibration or universal vegetation value",
            "denominator": "total released heat, consistent with HRR measurements",
        })

    @classmethod
    def from_energy_budget(
        cls,
        emitted_radiant_energy_j: ArrayLike,
        total_released_energy_j: ArrayLike,
        *,
        provenance: Mapping[str, Any] | str,
    ) -> RadiativeFractionEstimate:
        """Form an energy-integrated fraction from a matched source budget.

        Both inputs must be scalar, or both the same nonempty [H,W] shape.
        Incident energy at one receiver is not emitted source radiant energy.
        Total released energy must be strictly positive. The ratio is only
        constant in time if the caller imposes a constant-fraction scenario.
        """
        radiant = _array(emitted_radiant_energy_j, "emitted_radiant_energy_j", shape_kind=True)
        total = _array(total_released_energy_j, "total_released_energy_j", shape_kind=True)
        if radiant.shape != total.shape:
            raise ValueError("energy budgets must have exactly the same shape; broadcasting is not allowed")
        if np.any(radiant < 0) or np.any(total <= 0) or np.any(radiant > total):
            raise ValueError("require 0 <= emitted_radiant_energy_j <= total_released_energy_j and total > 0")
        record = _plain(_provenance(provenance))
        record.update({
            "method": "matched_source_energy_budget",
            "time_semantics": "energy-integrated over the same source and time period",
            "denominator": "total released source energy, not theoretical gross fuel energy",
            "limitation": "does not identify instantaneous fraction without a constant-fraction assumption",
        })
        return cls(radiant / total, record)

    def metadata(self) -> dict[str, Any]:
        return {"fraction": self.fraction.tolist(), "provenance": _plain(self.provenance)}

    def provenance_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible scenario record."""
        return self.metadata()


@dataclass(frozen=True)
class HomogeneousAtmosphere:
    """Caller-calibrated homogeneous grey absorption, in reciprocal metres.

    tau(r) = exp(-kappa*r), with r in metres. Spectral Beer--Lambert transport
    is given by Yilmaz (2009), NIST GCR 09-922, eq.(1.18), printed p.17.
    Replacing the spectral coefficient by one homogeneous grey coefficient
    is this implementation's explicit scenario assumption. Scattering and
    medium self-emission are excluded.
    """

    absorption_coefficient_m_inv: float
    provenance: Mapping[str, Any] | str

    def __post_init__(self) -> None:
        coefficient = _scalar(self.absorption_coefficient_m_inv, "absorption_coefficient_m_inv")
        if coefficient < 0:
            raise ValueError("absorption_coefficient_m_inv must be nonnegative")
        object.__setattr__(self, "absorption_coefficient_m_inv", coefficient)
        object.__setattr__(self, "provenance", _provenance(self.provenance))

    @classmethod
    def from_reference_transmission(
        cls,
        transmission: float,
        distance_m: float,
        *,
        provenance: Mapping[str, Any] | str,
    ) -> HomogeneousAtmosphere:
        """Calibrate kappa = -log(transmission)/distance for a matched band.

        A strictly positive reference transmission is required: zero would
        require an infinite coefficient. Broadband calibration remains a
        grey approximation when used at other path lengths or source spectra.
        """
        transmission = _scalar(transmission, "transmission")
        distance = _scalar(distance_m, "distance_m")
        if not 0 < transmission <= 1 or distance <= 0:
            raise ValueError("require transmission in (0,1] and distance_m > 0")
        record = _plain(_provenance(provenance))
        record.update({"method": "reference_path_calibration", "reference_transmission": transmission,
                       "reference_distance_m": distance})
        coefficient = -math.log(transmission) / distance
        if not math.isfinite(coefficient):
            raise ValueError("reference path produces an unsupported coefficient")
        return cls(coefficient, record)

    def transmission(self, distance_m: ArrayLike) -> FloatArray:
        distance = _array(distance_m, "distance_m")
        if np.any(distance < 0):
            raise ValueError("distance_m must be nonnegative")
        with np.errstate(over="ignore"):
            result = np.exp(-self.absorption_coefficient_m_inv * distance)
        return _immutable_array(result)

    def metadata(self) -> dict[str, Any]:
        return {
            "model": "homogeneous_grey_beer_lambert",
            "absorption_coefficient_m_inv": self.absorption_coefficient_m_inv,
            "provenance": _plain(self.provenance),
            "transport_source": {
                "source": "Yilmaz (2009), NIST GCR 09-922, equation 1.18, printed page 17",
                "url": "https://nvlpubs.nist.gov/nistpubs/gcr/2009/gcr09-922.pdf",
                "doi": "10.6028/NIST.GCR.09-922",
            },
            "scope": "fixed homogeneous grey absorption; excludes scattering and medium self-emission",
        }

    def provenance_dict(self) -> dict[str, Any]:
        """Return an independent JSON-compatible scenario record."""
        return self.metadata()


@dataclass(frozen=True, eq=False)
class AttenuatedCellTransfer:
    """Dimensionless cell-to-point transfer and numerical integration bounds.

    Each lower/upper pair encloses the source-area integral under the supplied
    radiation scenario, within floating-point evaluation accuracy. These are
    quadrature enclosures, separate from unknown-source-activity bounds.
    """

    midpoint: FloatArray
    lower_bound: FloatArray
    upper_bound: FloatArray

    def __post_init__(self) -> None:
        for name in ("midpoint", "lower_bound", "upper_bound"):
            object.__setattr__(self, name, _immutable_array(getattr(self, name)))


def _tile_bounds(
    centers: FloatArray,
    column: FloatArray,
    row: FloatArray,
    height: float,
    coefficient: float,
) -> tuple[FloatArray, FloatArray]:
    """Exact unattenuated solid angles times extremal path transmissions."""
    signs = np.array([[-1., -1.], [1., -1.], [1., 1.], [-1., 1.]])
    offsets = 0.5 * (signs[:, :1] * column + signs[:, 1:] * row)
    vertices = centers[:, None, :] + offsets[None, :, :]
    h2 = height * height
    norms = np.sqrt(np.sum(vertices * vertices, axis=-1) + h2)
    area = abs(float(column[0] * row[1] - column[1] * row[0]))
    def dot(i: int, j: int) -> FloatArray:
        return np.sum(vertices[:, i] * vertices[:, j], axis=-1) + h2
    def triangle(i: int, j: int, k: int) -> FloatArray:
        denominator = (norms[:, i] * norms[:, j] * norms[:, k]
                       + dot(i, j) * norms[:, k] + dot(j, k) * norms[:, i] + dot(k, i) * norms[:, j])
        return 2 * np.arctan2(height * area, denominator)
    exact = np.clip((triangle(0, 1, 2) + triangle(0, 2, 3)) / (4 * np.pi), 0, 0.5)
    if not np.all(np.isfinite(exact)) or not np.all(np.isfinite(norms)) or np.any(norms <= 0) or area <= 0:
        raise ValueError("source/receiver geometry exceeds supported numeric range")
    if coefficient == 0:
        return exact, exact
    # The farthest point of a convex polygon is a vertex. The nearest point is
    # either the origin (when inside) or its projection onto one of four edges.
    edge = np.roll(vertices, -1, axis=1) - vertices
    edge_squared = np.sum(edge * edge, axis=-1)
    fraction = np.clip(-np.sum(vertices * edge, axis=-1) / edge_squared, 0, 1)
    nearest = vertices + fraction[..., None] * edge
    min_horizontal_squared = np.min(np.sum(nearest * nearest, axis=-1), axis=-1)
    determinant = column[0] * row[1] - column[1] * row[0]
    u = (-centers[:, 0] * row[1] + centers[:, 1] * row[0]) / determinant
    v = (-column[0] * centers[:, 1] + column[1] * centers[:, 0]) / determinant
    inside = (np.abs(u) <= 0.5) & (np.abs(v) <= 0.5)
    min_horizontal_squared[inside] = 0
    shortest = np.sqrt(min_horizontal_squared + h2)
    longest = np.max(norms, axis=-1)
    with np.errstate(over="ignore"):
        lower = exact * np.exp(-coefficient * longest)
        upper = exact * np.exp(-coefficient * shortest)
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
        raise ValueError("source/receiver geometry exceeds supported numeric range")
    return lower, upper


def _integral(
    center: FloatArray, column: FloatArray, row: FloatArray, height: float,
    coefficient: float, atol: float, rtol: float, max_depth: int, max_tiles: int,
) -> tuple[float, float]:
    lower, upper = _tile_bounds(center[None], column, row, height, coefficient)
    initial_lower, initial_upper = float(lower[0]), float(upper[0])
    if initial_upper - initial_lower <= atol + rtol * initial_lower:
        return initial_lower, initial_upper
    # Heap tuples contain (-gap, unique id, lower, upper, center_x, center_y,
    # depth). A common depth determines the tile's affine side vectors.
    serial = 0
    heap = [(-(initial_upper - initial_lower), serial, initial_lower, initial_upper,
             float(center[0]), float(center[1]), 0)]
    frozen = []
    total_lower, total_upper = initial_lower, initial_upper
    signs = np.array([[-1., -1.], [1., -1.], [1., 1.], [-1., 1.]])
    while total_upper - total_lower > atol + rtol * total_lower:
        capacity = (max_tiles-len(heap)-len(frozen))//3
        if capacity <= 0:
            raise ValueError("attenuated cell integration exceeded max_tiles before meeting tolerance")
        # Evaluate a bounded batch of the largest gaps. Grouping by depth lets
        # all children use a common pair of affine side vectors in NumPy.
        groups: dict[int, list[tuple]] = {}
        for _ in range(min(32, capacity)):
            if not heap:
                break
            item = heapq.heappop(heap)
            if item[6] >= max_depth:
                frozen.append(item)
                continue
            groups.setdefault(item[6]+1, []).append(item)
        if not groups:
            if not heap:
                raise ValueError("attenuated cell integration exceeded max_depth before meeting tolerance")
            continue
        for next_depth, items in groups.items():
            next_column, next_row = column / (2 ** next_depth), row / (2 ** next_depth)
            offsets = 0.5*(signs[:, :1]*next_column + signs[:, 1:]*next_row)
            parent_centers = np.array([[item[4], item[5]] for item in items])
            children = (parent_centers[:, None, :] + offsets[None, :, :]).reshape(-1, 2)
            child_lower, child_upper = _tile_bounds(children, next_column, next_row, height, coefficient)
            total_lower += float(np.sum(child_lower)) - math.fsum(item[2] for item in items)
            total_upper += float(np.sum(child_upper)) - math.fsum(item[3] for item in items)
            for index in range(len(children)):
                serial += 1
                lo, hi = float(child_lower[index]), float(child_upper[index])
                heapq.heappush(heap, (-(hi-lo), serial, lo, hi,
                                     float(children[index, 0]), float(children[index, 1]), next_depth))
    # Recompute rather than trusting accumulated subtraction roundoff.
    total_lower = math.fsum(item[2] for item in heap + frozen)
    total_upper = math.fsum(item[3] for item in heap + frozen)
    if total_upper - total_lower > atol + rtol * total_lower:
        # Only roundoff can cause this path; never silently accept a wider gap.
        raise ValueError("attenuated cell integration did not meet the requested tolerance")
    return total_lower, total_upper


def attenuated_cell_transfer(
    dx: ArrayLike,
    dy: ArrayLike,
    *,
    column_vector_m: ArrayLike,
    row_vector_m: ArrayLike,
    height_separation_m: float,
    atmosphere: HomogeneousAtmosphere,
    atol: float = 1e-7,
    rtol: float = 1e-2,
    max_depth: int = 14,
    max_tiles: int = 100000,
    chunk_size: int = 128,
) -> AttenuatedCellTransfer:
    """Bound the finite-cell integral of homogeneous grey absorption.

    For each receiver/source displacement (dx,dy), this computes
    K = integral_cell h exp(-kappa*r)/(4*pi*r**3) dA,
    where r=sqrt(x*x+y*y+h*h). It includes the receiving-plane cosine factor
    and the complete affine source footprint. Rotation and shear are supported.
    dx and dy may broadcast; scalar/array result shape matches their broadcast.

    Each tile has exact unattenuated transfer K0 and distances Rmin,Rmax.
    K0 exp(-kappa Rmax) <= Ktile <= K0 exp(-kappa Rmin).
    The greatest-gap tile is subdivided until the summed enclosure width is
    <= atol + rtol * total_lower. Midpoint error is at most half that width,
    within floating-point evaluation accuracy. Failure to converge within the
    caller's depth or leaf budget raises ValueError. The exact transparent
    calculation is used when kappa=0. Absolute tolerance is dimensionless.

    The default relative enclosure width is 1% plus the absolute tolerance.
    Smaller tolerances can require many source tiles; callers may need to raise
    max_tiles for optically thick cells rather than assuming convergence.

    chunk_size bounds vectorized initial-geometry temporaries; optional
    absorption can be substantially slower than the transparent solid angle.
    The triangle formula is van Oosterom and Strackee (1983),
    DOI 10.1109/TBME.1983.325207.
    """
    if not isinstance(atmosphere, HomogeneousAtmosphere):
        raise TypeError("atmosphere must be a HomogeneousAtmosphere")
    dx_array, dy_array = np.broadcast_arrays(_array(dx, "dx"), _array(dy, "dy"))
    column, row = _array(column_vector_m, "column_vector_m"), _array(row_vector_m, "row_vector_m")
    if column.shape != (2,) or row.shape != (2,):
        raise ValueError("column_vector_m and row_vector_m must have shape [2]")
    determinant = float(column[0] * row[1] - column[1] * row[0])
    if not math.isfinite(determinant) or determinant == 0:
        raise ValueError("source footprint must have finite nonzero area")
    height = _scalar(height_separation_m, "height_separation_m")
    if height <= 0:
        raise ValueError("height_separation_m must be strictly positive")
    atol, rtol = _scalar(atol, "atol"), _scalar(rtol, "rtol")
    if atol < 0 or rtol < 0 or (atol == 0 and rtol == 0):
        raise ValueError("tolerances must be nonnegative and at least one strictly positive")
    for name, value in (("max_depth", max_depth), ("max_tiles", max_tiles), ("chunk_size", chunk_size)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    centers = np.stack((dx_array.ravel(), dy_array.ravel()), axis=-1)
    lower, upper = np.empty(len(centers)), np.empty(len(centers))
    coefficient = atmosphere.absorption_coefficient_m_inv
    for start in range(0, len(centers), chunk_size):
        end = min(start + chunk_size, len(centers))
        lo, hi = _tile_bounds(centers[start:end], column, row, height, coefficient)
        lower[start:end], upper[start:end] = lo, hi
        for index in np.flatnonzero(hi - lo > atol + rtol * lo):
            lower[start+index], upper[start+index] = _integral(
                centers[start+index], column, row, height, coefficient,
                atol, rtol, max_depth, max_tiles,
            )
    shape = dx_array.shape
    return AttenuatedCellTransfer((0.5*(lower+upper)).reshape(shape),
                                  lower.reshape(shape), upper.reshape(shape))
