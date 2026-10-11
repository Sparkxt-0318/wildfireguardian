"""Expected incident radiant heat and duration-aware surface-flame activity.

Radiation consumes active-burning occupancy probabilities. The integrated API
converts first-new-burning forecasts using an explicit arrival-time scenario;
cumulative burned area alone does not identify current flames. Missing source
coverage remains unknown and produces bounds. NumPy is the only eager numerical
dependency; coordinate, raster, and trained-model dependencies load on demand.
"""

from __future__ import annotations

from .paths import resolve_recorded_path

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import hashlib
from numbers import Integral
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .coordinates import (
    geographic_coordinates,
    geographic_coordinates_for_points,
    validate_metric_crs,
)

FloatArray = NDArray[np.float64]


# Model
# Finite-cell, probabilistic radiation model in SI units.
#
# The NIST point-source irradiance equation is integrated over horizontal source
# cells with uniform isotropic radiant power per ground area. Receivers face
# upward and lie below a common source elevation. Cell integrals are exact solid
# angles, evaluated as two triangles. This is a source-sheet idealization, not a
# solid-flame model or a calibrated prediction of total wildfire heat transfer.

def _finite_array(value: ArrayLike, name: str) -> FloatArray:
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} contains masked values; missing values are not zero")
    try:
        if np.iscomplexobj(value):
            raise ValueError(f"{name} must be real-valued")
        result = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a real numeric scalar or array") from error
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite; missing values are not zero")
    return result


def _physical_array(
    value: ArrayLike, name: str, *, positive: bool = False, upper: float | None = None
) -> FloatArray:
    result = _finite_array(value, name)
    if np.any(result <= 0 if positive else result < 0):
        relation = "positive" if positive else "nonnegative"
        raise ValueError(f"{name} must be {relation}")
    if upper is not None and np.any(result > upper):
        raise ValueError(f"{name} must be at most {upper}")
    result.setflags(write=False)
    return result


def _physical_scalar(value: ArrayLike, name: str) -> float:
    result = _finite_array(value, name)
    if result.ndim != 0:
        raise ValueError(f"{name} must be a scalar")
    return float(result)


def _shape(shape: tuple[int, int]) -> tuple[int, int]:
    if (
        len(shape) != 2
        or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral) for v in shape)
        or any(v <= 0 for v in shape)
    ):
        raise ValueError("shape must contain two positive integers (rows, columns)")
    return int(shape[0]), int(shape[1])


@dataclass(frozen=True)
class AffineGrid:
    """Pixel-corner affine transform in a planar coordinate system in metres.

    ``transform=(a,b,c,d,e,f)`` means ``x=a*column+b*row+c`` and
    ``y=d*column+e*row+f`` at pixel corners. Rotation and shear are supported.
    A cell center uses ``column+0.5`` and ``row+0.5``. Geographic longitude and
    latitude must be projected to metres before use.
    """

    transform: tuple[float, float, float, float, float, float]

    def __post_init__(self) -> None:
        values = _finite_array(self.transform, "transform")
        if values.shape != (6,):
            raise ValueError("transform must be six coefficients (a,b,c,d,e,f)")
        object.__setattr__(self, "transform", tuple(float(v) for v in values))
        a, b, _, d, e, _ = self.transform
        area = abs(a * e - b * d)
        if not np.isfinite(area) or area <= 0:
            raise ValueError("transform must have a finite nonzero cell area")

    @classmethod
    def from_cell_size(
        cls,
        cell_size_m: float | tuple[float, float],
        origin_xy_m: tuple[float, float] = (0.0, 0.0),
        row_direction: int = 1,
    ) -> AffineGrid:
        """Construct a grid; a tuple is (row spacing, column spacing).

        The origin is the upper/first corner of cell (0,0), not its center.
        ``row_direction=-1`` makes rows increase toward decreasing y.
        """
        spacing = _physical_array(cell_size_m, "cell_size_m", positive=True)
        if spacing.ndim == 0:
            dy = dx = float(spacing)
        elif spacing.shape == (2,):
            dy, dx = (float(v) for v in spacing)
        else:
            raise ValueError("cell_size_m must be scalar or (row_m, column_m)")
        origin = _finite_array(origin_xy_m, "origin_xy_m")
        if origin.shape != (2,):
            raise ValueError("origin_xy_m must contain (x,y)")
        if isinstance(row_direction, (bool, np.bool_)) or row_direction not in (-1, 1):
            raise ValueError("row_direction must be +1 or -1")
        return cls((dx, 0.0, float(origin[0]), 0.0, row_direction * dy, float(origin[1])))

    @property
    def cell_area_m2(self) -> float:
        a, b, _, d, e, _ = self.transform
        return abs(a * e - b * d)

    @property
    def column_vector_m(self) -> tuple[float, float]:
        a, _, _, d, _, _ = self.transform
        return a, d

    @property
    def row_vector_m(self) -> tuple[float, float]:
        _, b, _, _, e, _ = self.transform
        return b, e

    def centers(self, shape: tuple[int, int]) -> FloatArray:
        """Return projected cell-center coordinates with shape [H,W,2]."""
        rows, columns = np.indices(_shape(shape), dtype=np.float64)
        a, b, c, d, e, f = self.transform
        columns += 0.5
        rows += 0.5
        return np.stack((a * columns + b * rows + c, d * columns + e * rows + f), axis=-1)


@dataclass(frozen=True)
class CombustionParameters:
    """Uniform-rate combustion estimate, conditional on an actively burning cell.

    Fuel load is dry fuel per entire ground-cell area (kg/m²). Heat of combustion
    is the effective released heat (J/kg), not an automatically moisture-corrected
    gross calorific value. ``consumed_fraction`` describes the part of that load
    consumed in the specified burning phase. Burning duration is in seconds.
    Fields may be scalars or broadcast-compatible arrays.
    """

    fuel_load_kg_m2: ArrayLike
    heat_of_combustion_j_kg: ArrayLike
    burning_duration_s: ArrayLike
    consumed_fraction: ArrayLike = 1.0

    @classmethod
    def from_flame_residence(
        cls, residence_time, *, fuel_load_kg_m2: ArrayLike,
        heat_of_combustion_j_kg: ArrayLike, consumed_fraction: ArrayLike,
    ) -> CombustionParameters:
        """Use the same flaming duration for activity and conditional heat.

        Consumed fraction must describe the fuel consumed in this modeled
        flaming phase. Total fuel burnout or smoldering durations are different.
        """

        if not isinstance(residence_time, FlameResidenceTime):
            raise TypeError("residence_time must be FlameResidenceTime")
        return cls(fuel_load_kg_m2, heat_of_combustion_j_kg,
                   residence_time.duration_s, consumed_fraction)

    def __post_init__(self) -> None:
        for name, positive, upper in (
            ("fuel_load_kg_m2", False, None),
            ("heat_of_combustion_j_kg", True, None),
            ("burning_duration_s", True, None),
            ("consumed_fraction", False, 1.0),
        ):
            object.__setattr__(
                self, name, _physical_array(getattr(self, name), name, positive=positive, upper=upper)
            )
        # Validate both broadcasting and finite derived intensity on construction.
        self.heat_release_rate_density_w_m2

    @property
    def heat_release_rate_density_w_m2(self) -> FloatArray:
        """Return fuel_load * consumed_fraction * heat_of_combustion / duration."""
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            try:
                density = (
                    self.fuel_load_kg_m2
                    * self.consumed_fraction
                    * self.heat_of_combustion_j_kg
                    / self.burning_duration_s
                )
            except ValueError as error:
                raise ValueError("combustion parameter arrays must be broadcast-compatible") from error
        return _physical_array(density, "derived heat_release_rate_density_w_m2")


@dataclass(frozen=True)
class HeatFluxResult:
    """Expected incident radiant irradiance at point receivers.

    The map contains receiver cell-center values, not receiver-area averages.
    Radiant source power excludes atmospheric loss. Incident heat is distinct
    from absorbed heat; no absorptivity, temperature, or convective term is used.
    """

    incident_heat_flux_w_m2: FloatArray
    expected_total_radiant_power_w: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "incident_heat_flux_w_m2",
            _physical_array(self.incident_heat_flux_w_m2, "incident_heat_flux_w_m2"),
        )
        power = _physical_scalar(self.expected_total_radiant_power_w, "expected_total_radiant_power_w")
        if power < 0:
            raise ValueError("expected_total_radiant_power_w must be nonnegative")
        object.__setattr__(self, "expected_total_radiant_power_w", power)

    @property
    def incident_heat_flux_kw_m2(self) -> FloatArray:
        return self.incident_heat_flux_w_m2 / 1000.0

    def incident_energy_j_m2(self, duration_s: float) -> FloatArray:
        """Incident radiant dose (J/m²), assuming this flux is constant in time."""
        duration = _physical_scalar(duration_s, "duration_s")
        if duration < 0:
            raise ValueError("duration_s must be nonnegative")
        return _physical_array(self.incident_heat_flux_w_m2 * duration, "incident_energy_j_m2")

    def incident_power_w(self, receiver_area_m2: ArrayLike) -> FloatArray:
        """Flux times area (W), assuming uniform irradiance over that small receiver.

        This multiplication does not integrate irradiance over a large receiver
        patch. For a large surface, integrate sufficiently resolved flux samples.
        """
        area = _physical_array(receiver_area_m2, "receiver_area_m2")
        if area.ndim != 0 and area.shape != self.incident_heat_flux_w_m2.shape:
            raise ValueError("receiver_area_m2 must be scalar or have the flux shape")
        return _physical_array(self.incident_heat_flux_w_m2 * area, "incident_power_w")

    def incident_energy_j(self, duration_s: float, receiver_area_m2: ArrayLike) -> FloatArray:
        """Incident radiant energy (J) for a uniformly irradiated small receiver.

        Assumes constant flux for the specified duration and uniform flux over
        each specified area. This does not calculate absorbed heat.
        """
        duration = _physical_scalar(duration_s, "duration_s")
        if duration < 0:
            raise ValueError("duration_s must be nonnegative")
        return _physical_array(self.incident_power_w(receiver_area_m2) * duration, "incident_energy_j")


def integrate_heat_flux(flux_w_m2: ArrayLike, times_s: ArrayLike) -> FloatArray:
    """Integrate samples [T,...] by the trapezoid rule, returning dose in J/m².

    Time must be strictly increasing in seconds. Flux is assumed to interpolate
    linearly between samples; unsampled fluctuations and missing intervals are
    not reconstructed. To integrate a piecewise-constant forecast, multiply each
    interval's flux by its duration instead.
    """
    flux = _physical_array(flux_w_m2, "flux_w_m2")
    times = _finite_array(times_s, "times_s")
    if times.ndim != 1 or times.size < 2:
        raise ValueError("times_s must be a one-dimensional array of at least two samples")
    if flux.ndim < 1 or flux.shape[0] != times.size:
        raise ValueError("the first flux dimension must match times_s")
    durations = np.diff(times)
    if np.any(durations <= 0):
        raise ValueError("times_s must be strictly increasing")
    duration_shape = (durations.size,) + (1,) * (flux.ndim - 1)
    dose = np.sum((0.5 * flux[:-1] + 0.5 * flux[1:]) * durations.reshape(duration_shape), axis=0)
    return _physical_array(dose, "integrated incident dose")


class ExpectedHeatFluxModel:
    """Linear expectation of finite-cell radiation from a burning-probability map.

    Required physical inputs specify the conditional heat release rate per ground
    area, radiative fraction, and emission height. Scalars or exact [H,W] source
    parameter maps are accepted. ``atmospheric_transmissivity`` is a uniform
    path-independent scalar in [0,1]; it is a scenario parameter, not a calculated
    smoke/humidity correction. All sources are at ``emission_height_m`` and all
    upward-facing receivers at ``receiver_height_m`` in the same height datum.

    ``predict`` consumes a complete, finite [H,W] array with probabilities in
    [0,1]. These must mean actively burning at the same instant. Marginal
    dependence is unrestricted. Conditional source strengths and the transfer
    geometry are fixed; uncertainty in those inputs is not marginalized.

    It returns ``(incident_heat_flux_w_m2, coordinates)``. Coordinates have
    shape [H,W,2] and contain (latitude, longitude) in degrees, EPSG:4326, at
    receiver cell centers. Set ``epsg`` to the grid's projected CRS in metres.
    For local grids without a geographic CRS, use ``predict_details`` to obtain
    the physical result without asserting a location on Earth.
    """

    def __init__(
        self,
        *,
        grid: AffineGrid,
        heat_release_rate_density_w_m2: ArrayLike,
        radiative_fraction: ArrayLike,
        emission_height_m: float,
        receiver_height_m: float = 0.0,
        atmospheric_transmissivity: float = 1.0,
        epsg: int | None = None,
    ) -> None:
        if not isinstance(grid, AffineGrid):
            raise TypeError("grid must be an AffineGrid")
        self.grid = grid
        self.epsg = None if epsg is None else validate_metric_crs(epsg)
        self.heat_release_rate_density_w_m2 = _physical_array(
            heat_release_rate_density_w_m2, "heat_release_rate_density_w_m2"
        )
        self.radiative_fraction = _physical_array(radiative_fraction, "radiative_fraction", upper=1.0)
        for name in ("heat_release_rate_density_w_m2", "radiative_fraction"):
            if getattr(self, name).ndim not in (0, 2):
                raise ValueError(f"{name} must be scalar or a two-dimensional source map")
        self.emission_height_m = _physical_scalar(emission_height_m, "emission_height_m")
        self.receiver_height_m = _physical_scalar(receiver_height_m, "receiver_height_m")
        self.height_separation_m = self.emission_height_m - self.receiver_height_m
        if not np.isfinite(self.height_separation_m) or self.height_separation_m <= 0:
            raise ValueError("emission_height_m must be strictly above receiver_height_m")
        self.atmospheric_transmissivity = _physical_scalar(atmospheric_transmissivity, "atmospheric_transmissivity")
        if not 0 <= self.atmospheric_transmissivity <= 1:
            raise ValueError("atmospheric_transmissivity must lie in [0,1]")

    def _weighted_sources(self, probability: ArrayLike) -> FloatArray:
        p = _physical_array(probability, "active_burning_probability", upper=1.0)
        if p.ndim != 2 or min(p.shape) < 1:
            raise ValueError("active_burning_probability must be a nonempty [H,W] matrix")
        for name in ("heat_release_rate_density_w_m2", "radiative_fraction"):
            value = getattr(self, name)
            if value.ndim != 0 and value.shape != p.shape:
                raise ValueError(f"{name} must be scalar or exactly match probability shape {p.shape}")
        with np.errstate(over="ignore", invalid="ignore"):
            weighted = p * self.heat_release_rate_density_w_m2 * self.radiative_fraction
        return _physical_array(weighted, "expected radiant source density")

    def _cell_transfer(self, dx: FloatArray, dy: FloatArray) -> FloatArray:
        """Exact solid angle / (4π) for a cell centered at relative (dx,dy)."""
        cx, cy = self.grid.column_vector_m
        rx, ry = self.grid.row_vector_m
        h = self.height_separation_m
        vertices = [
            (dx + 0.5 * (u * cx + v * rx), dy + 0.5 * (u * cy + v * ry))
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        norms = [np.sqrt(x * x + y * y + h * h) for x, y in vertices]

        def dot(i: int, j: int) -> FloatArray:
            xi, yi = vertices[i]
            xj, yj = vertices[j]
            return xi * xj + yi * yj + h * h

        def triangle(i: int, j: int, k: int) -> FloatArray:
            ni, nj, nk = norms[i], norms[j], norms[k]
            denominator = ni * nj * nk + dot(i, j) * nk + dot(j, k) * ni + dot(k, i) * nj
            # Each triangle is half of the parallelogram. Its triple product is
            # h * (twice triangle area) = h * full cell area, independent of dx/dy.
            return 2.0 * np.arctan2(h * self.grid.cell_area_m2, denominator)

        transfer = (triangle(0, 1, 2) + triangle(0, 2, 3)) / (4.0 * np.pi)
        if not np.all(np.isfinite(transfer)):
            raise ValueError("source/receiver geometry exceeds supported numeric range")
        return np.clip(transfer, 0.0, 0.5)

    def transfer_kernel(self, shape: tuple[int, int]) -> FloatArray:
        """Return [2H-1,2W-1] dimensionless cell-to-center transfer coefficients.

        Center index [H-1,W-1] is the same-cell contribution. The entire source
        raster contributes; there is no distance cutoff and the kernel is not
        normalized. Atmospheric transmissivity is applied separately.
        """
        height, width = _shape(shape)
        row_offsets = np.arange(1 - height, height, dtype=np.float64)[:, None]
        col_offsets = np.arange(1 - width, width, dtype=np.float64)[None, :]
        cx, cy = self.grid.column_vector_m
        rx, ry = self.grid.row_vector_m
        return self._cell_transfer(col_offsets * cx + row_offsets * rx, col_offsets * cy + row_offsets * ry)

    def _result(self, flux: FloatArray, sources: FloatArray) -> HeatFluxResult:
        power = float(np.sum(sources) * self.grid.cell_area_m2)
        if not np.isfinite(power):
            raise ValueError("expected radiant source power exceeds supported numeric range")
        # Roundoff from the FFT can introduce tiny negative values into a
        # mathematically nonnegative convolution. No input probabilities are clipped.
        return HeatFluxResult(np.maximum(flux, 0.0), power)

    def predict(self, active_burning_probability: ArrayLike) -> tuple[FloatArray, FloatArray]:
        """Return flux [H,W] and corresponding (latitude, longitude) [H,W,2].

        Coordinates are receiver cell centers in degrees, EPSG:4326. A known
        projected ``epsg`` in metres is required to locate the grid on Earth.
        """
        if self.epsg is None:
            raise ValueError("geographic heat output requires epsg for the grid; use predict_details for a local grid")
        result = self.predict_details(active_burning_probability)
        coordinates = geographic_coordinates(
            result.incident_heat_flux_w_m2.shape,
            affine_transform=self.grid.transform,
            epsg=self.epsg,
        )
        return result.incident_heat_flux_w_m2, coordinates

    def predict_details(self, active_burning_probability: ArrayLike) -> HeatFluxResult:
        """Return expected radiant flux [H,W] at aligned receiver cell centers.

        Linear convolution is zero-padded before the FFT, so sources at one edge
        cannot wrap to the opposite edge. Outside-raster emission is excluded;
        zero padding is a finite-source-domain assumption, not a missing-data fill.
        """
        sources = self._weighted_sources(active_burning_probability)
        height, width = sources.shape
        if not np.any(sources) or self.atmospheric_transmissivity == 0:
            return self._result(np.zeros_like(sources), sources)
        kernel = self.transfer_kernel(sources.shape)
        full_shape = (height + kernel.shape[0] - 1, width + kernel.shape[1] - 1)
        source_fft = np.fft.rfft2(sources, s=full_shape)
        kernel_fft = np.fft.rfft2(kernel, s=full_shape)
        full_flux = np.fft.irfft2(source_fft * kernel_fft, s=full_shape)
        flux = full_flux[height - 1 : 2 * height - 1, width - 1 : 2 * width - 1]
        return self._result(flux * self.atmospheric_transmissivity, sources)

    def predict_at_points(
        self,
        active_burning_probability: ArrayLike,
        receiver_xy_m: ArrayLike,
        *,
        target_chunk_size: int = 128,
        source_chunk_size: int = 1024,
    ) -> tuple[FloatArray, FloatArray]:
        """Return flux [N] and receiver (latitude, longitude) coordinates [N,2].

        Input points are (x,y) in metres in the configured projected ``epsg``;
        output coordinates are degrees in EPSG:4326.
        """
        if self.epsg is None:
            raise ValueError("geographic heat output requires epsg for the grid; use predict_at_points_details for a local grid")
        coordinates = geographic_coordinates_for_points(receiver_xy_m, epsg=self.epsg)
        result = self.predict_at_points_details(
            active_burning_probability, receiver_xy_m,
            target_chunk_size=target_chunk_size, source_chunk_size=source_chunk_size,
        )
        return result.incident_heat_flux_w_m2, coordinates

    def predict_at_points_details(
        self,
        active_burning_probability: ArrayLike,
        receiver_xy_m: ArrayLike,
        *,
        target_chunk_size: int = 128,
        source_chunk_size: int = 1024,
    ) -> HeatFluxResult:
        """Evaluate arbitrary [N,2] horizontal receiver coordinates in metres.

        Source and target chunks bound temporary array sizes. This is an exact
        finite-cell sum with the same physical assumptions as ``predict``.
        Receiver heights remain the model's common horizontal receiving plane.
        """
        sources = self._weighted_sources(active_burning_probability)
        points = _finite_array(receiver_xy_m, "receiver_xy_m")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("receiver_xy_m must have shape [N,2]")
        for name, value in (("target_chunk_size", target_chunk_size), ("source_chunk_size", source_chunk_size)):
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        density = sources.ravel()
        active = density > 0
        centers = self.grid.centers(sources.shape).reshape(-1, 2)[active]
        density = density[active]
        flux = np.zeros(points.shape[0], dtype=np.float64)
        if self.atmospheric_transmissivity == 0:
            return self._result(flux, sources)
        for target_start in range(0, len(points), target_chunk_size):
            target = points[target_start : target_start + target_chunk_size]
            subtotal = np.zeros(len(target), dtype=np.float64)
            for source_start in range(0, len(centers), source_chunk_size):
                center = centers[source_start : source_start + source_chunk_size]
                displacement = center[None, :, :] - target[:, None, :]
                transfer = self._cell_transfer(displacement[..., 0], displacement[..., 1])
                subtotal += transfer @ density[source_start : source_start + source_chunk_size]
            flux[target_start : target_start + len(target)] = subtotal
        return self._result(flux * self.atmospheric_transmissivity, sources)


# Ecology
# Load ecological fuel maps without turning unknown fuel into zero fuel.
#
# LANDFIRE FCCS loadings describe reference fuelbeds, not event-date field
# measurements. A partially covered target cell contains a mean over its mapped
# portion. Such a mean is retained, but is not a whole-cell combustion input until
# the caller supplies a loading for the unmapped portion.

# U.S. short ton (2000 lb), international pound, international acre.
FCCS_TONS_PER_ACRE_TO_KG_M2 = 2000.0 * 0.45359237 / (43560.0 * 0.3048**2)


def _fuel_map(value: ArrayLike, name: str) -> NDArray[np.float64]:
    if np.iscomplexobj(value):
        raise ValueError(f"{name} must be real-valued")
    try:
        array = np.ma.asarray(value, dtype=np.float64).filled(np.nan)
        array = np.array(array, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a numeric spatial matrix") from error
    if array.ndim != 2 or 0 in array.shape:
        raise ValueError(f"{name} must have nonempty shape [H,W]")
    return array


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_shape(value: Any) -> tuple[int, int]:
    try:
        shape = tuple(value)
    except TypeError as error:
        raise ValueError("expected_shape must be two positive integers") from error
    if len(shape) != 2 or any(
        isinstance(item, (bool, np.bool_))
        or not isinstance(item, Integral)
        or item <= 0
        for item in shape
    ):
        raise ValueError("expected_shape must be two positive integers")
    return int(shape[0]), int(shape[1])


@dataclass(frozen=True)
class EcologicalFuelMaps:
    """Mapped-part dry loading and the fraction of each cell it describes.

    ``fuel_load_kg_m2`` and ``coverage_fraction`` have shape [H,W]. Missing or
    physically invalid entries become NaN; readable partial means are retained.
    ``valid`` is a boolean mask declaring complete loading inputs. It must never
    mark unreadable data valid. ``from_fccs_rasters`` constructs this mask using
    complete coverage, within its explicitly recorded numerical tolerance.

    Fuel mass and coverage are retained separately; no biome, canopy-height,
    humidity, or soil-moisture conversion to fuel mass is performed.
    """

    fuel_load_kg_m2: ArrayLike
    valid: ArrayLike
    coverage_fraction: ArrayLike
    provenance: dict[str, Any]

    def __post_init__(self) -> None:
        loading = _fuel_map(self.fuel_load_kg_m2, "fuel_load_kg_m2")
        coverage = _fuel_map(self.coverage_fraction, "coverage_fraction")
        if coverage.shape != loading.shape:
            raise ValueError("coverage_fraction must match fuel_load_kg_m2 shape")
        if np.ma.isMaskedArray(self.valid) and np.any(np.ma.getmaskarray(self.valid)):
            raise ValueError("valid must be an unmasked boolean matrix")
        valid = np.asarray(self.valid)
        if valid.dtype != np.bool_ or valid.shape != loading.shape:
            raise ValueError("valid must be a boolean matrix matching fuel_load_kg_m2")
        valid = np.array(valid, copy=True)
        loading[~np.isfinite(loading) | (loading < 0)] = np.nan
        coverage[~np.isfinite(coverage) | (coverage < 0) | (coverage > 1)] = np.nan
        if np.any(valid & ~(np.isfinite(loading) & np.isfinite(coverage))):
            raise ValueError("valid cannot mark missing or invalid fuel/coverage values valid")
        provenance = deepcopy(self.provenance)
        if not isinstance(provenance, dict):
            raise ValueError("provenance must be a dictionary")
        tolerance = provenance.get("full_coverage_tolerance", 1e-6)
        if (
            isinstance(tolerance, bool)
            or not np.isscalar(tolerance)
            or not np.isfinite(tolerance)
            or not 0 <= tolerance < 1
        ):
            raise ValueError("full_coverage_tolerance must be finite and in [0,1)")
        if np.any(valid & (coverage < 1.0 - tolerance)):
            raise ValueError("valid cannot mark a partially covered cell complete")
        for array in (loading, coverage, valid):
            array.setflags(write=False)
        object.__setattr__(self, "fuel_load_kg_m2", loading)
        object.__setattr__(self, "coverage_fraction", coverage)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "provenance", provenance)

    @classmethod
    def from_fccs_rasters(
        cls,
        total_loading_path: str | Path,
        coverage_path: str | Path,
        *,
        grid: AffineGrid | None = None,
        expected_shape: tuple[int, int] | None = None,
        full_coverage_tolerance: float = 1e-6,
    ) -> EcologicalFuelMaps:
        """Read exactly aligned static FCCS reference-loading rasters.

        Loading is interpreted as U.S. short tons per acre, as published by
        LANDFIRE. Both rasters must be single-band, have identical shape, CRS
        and affine transform, and use a projected CRS whose linear unit is one
        metre. Optional ``grid`` and ``expected_shape`` verify prediction-grid
        alignment. Rasterio is required only when this constructor is used.
        """
        if (
            isinstance(full_coverage_tolerance, (bool, np.bool_))
            or not np.isscalar(full_coverage_tolerance)
            or not np.isfinite(full_coverage_tolerance)
            or not 0 <= full_coverage_tolerance < 1
        ):
            raise ValueError("full_coverage_tolerance must be finite and in [0,1)")
        if grid is not None and not isinstance(grid, AffineGrid):
            raise ValueError("grid must be an AffineGrid")
        try:
            import rasterio
        except ImportError as error:
            raise ImportError("Reading ecological GeoTIFFs requires the optional rasterio dependency") from error

        loading_path = Path(total_loading_path).expanduser().resolve()
        fraction_path = Path(coverage_path).expanduser().resolve()
        with rasterio.open(loading_path) as source, rasterio.open(fraction_path) as fraction:
            if source.count != 1 or fraction.count != 1:
                raise ValueError("fuel loading and coverage rasters must each have one static band")
            if source.shape != fraction.shape:
                raise ValueError("fuel loading and coverage raster shapes differ")
            if source.crs != fraction.crs:
                raise ValueError("fuel loading and coverage raster CRS differ")
            if source.transform != fraction.transform:
                raise ValueError("fuel loading and coverage raster affine transforms differ")
            if source.crs is None or not source.crs.is_projected:
                raise ValueError("ecological rasters must use a projected CRS in metres")
            _, unit_factor = source.crs.linear_units_factor
            if unit_factor != 1.0:
                raise ValueError("ecological rasters must use metre linear units")
            transform = tuple(float(v) for v in tuple(source.transform)[:6])
            raster_grid = AffineGrid(transform)
            if grid is not None and raster_grid.transform != grid.transform:
                raise ValueError("ecological raster affine transform does not match grid")
            if expected_shape is not None and source.shape != _expected_shape(expected_shape):
                raise ValueError("ecological raster shape does not match expected_shape")
            loading = _fuel_map(source.read(1, masked=True), "fuel loading raster")
            coverage = _fuel_map(fraction.read(1, masked=True), "coverage raster")
            crs = source.crs.to_string()
            shape = source.shape

        loading[~np.isfinite(loading) | (loading < 0)] = np.nan
        coverage[~np.isfinite(coverage) | (coverage < 0) | (coverage > 1)] = np.nan
        with np.errstate(over="ignore", invalid="ignore"):
            loading *= FCCS_TONS_PER_ACRE_TO_KG_M2
        loading[~np.isfinite(loading)] = np.nan
        valid = (
            np.isfinite(loading)
            & np.isfinite(coverage)
            & (coverage >= 1.0 - float(full_coverage_tolerance))
        )
        provenance = {
            "source": "LANDFIRE FCCS reference fuelbed loading",
            "source_url": "https://www.landfire.gov/fuel/fccs",
            "reference_table_url": "https://www.landfire.gov/sites/default/files/CSV/LF_ConsumeLoadings.csv",
            "physical_definition": "reference dry fuelbed loading, not measured event-date available fuel",
            "loading_path": str(loading_path),
            "coverage_path": str(fraction_path),
            "loading_sha256": _file_hash(loading_path),
            "coverage_sha256": _file_hash(fraction_path),
            "original_loading_units": "U.S. short tons per acre",
            "loading_units": "kg/m2",
            "conversion_factor": FCCS_TONS_PER_ACRE_TO_KG_M2,
            "crs": crs,
            "transform": list(transform),
            "shape": list(shape),
            "full_coverage_tolerance": float(full_coverage_tolerance),
            "partial_coverage_policy": "retain mapped-part mean; reject as whole-cell combustion input unless explicit fallback is supplied",
            "fallback_policy": "caller loading describes unmapped fraction: coverage*mapped_mean + (1-coverage)*fallback; unreadable mapped mean or coverage uses fallback for entire cell",
            "zero_bound_policy": "zero for unknown data is a nonnegative mathematical lower bound, not an observed or assumed zero fuel load",
            "ecological_limitations": "no automatic biome-to-mass, canopy-to-mass, or moisture damping; consumption fraction, heat yield and duration remain caller assumptions",
        }
        return cls(loading, valid, coverage, provenance)

    @property
    def fuel_load_lower_bound_kg_m2(self) -> NDArray[np.float64]:
        """Known mapped fuel contribution, allowing any nonnegative unknown load.

        This is a lower bound *under the reference-loading input assumptions*.
        It is not a lower bound on true field fuel mass: the reference estimates
        themselves can be inaccurate. Unknown coverage or loading yields the
        trivial nonnegative bound zero and does not establish zero fuel.
        """
        readable = np.isfinite(self.fuel_load_kg_m2) & np.isfinite(self.coverage_fraction)
        result = np.zeros(self.fuel_load_kg_m2.shape, dtype=np.float64)
        result[readable] = (
            self.fuel_load_kg_m2[readable] * self.coverage_fraction[readable]
        )
        result.setflags(write=False)
        return result

    def combustion_parameters(
        self,
        *,
        heat_of_combustion_j_kg: ArrayLike,
        burning_duration_s: ArrayLike,
        consumed_fraction: ArrayLike,
        fallback_fuel_load_kg_m2: ArrayLike | None = None,
    ) -> CombustionParameters:
        """Convert reference mass to a supplied uniform combustion-rate model.

        With no fallback every cell must be valid. An explicit nonnegative,
        finite scalar or spatial fallback describes the unknown part of partial
        cells. If the mapped mean or coverage is unreadable, it supplies the
        entire cell. Supplied fuel and combustion arrays must broadcast to the
        existing [H,W] grid; leading time/batch dimensions are not accepted.
        """
        shape = self.fuel_load_kg_m2.shape
        if fallback_fuel_load_kg_m2 is None:
            if not np.all(self.valid):
                raise ValueError(
                    f"{int(np.count_nonzero(~self.valid))} cells have missing or incomplete fuel coverage; "
                    "supply explicit fallback_fuel_load_kg_m2 for their unmapped fuel"
                )
            loading = self.fuel_load_kg_m2
        else:
            if np.iscomplexobj(fallback_fuel_load_kg_m2) or (
                np.ma.isMaskedArray(fallback_fuel_load_kg_m2)
                and np.any(np.ma.getmaskarray(fallback_fuel_load_kg_m2))
            ):
                raise ValueError("fallback_fuel_load_kg_m2 must be real, finite and unmasked")
            try:
                fallback = np.asarray(fallback_fuel_load_kg_m2, dtype=np.float64)
                fallback = np.broadcast_to(fallback, shape)
            except (TypeError, ValueError) as error:
                raise ValueError("fallback_fuel_load_kg_m2 must broadcast to fuel-map shape [H,W]") from error
            if np.any(~np.isfinite(fallback)) or np.any(fallback < 0):
                raise ValueError("fallback_fuel_load_kg_m2 must be finite and nonnegative")
            readable = np.isfinite(self.fuel_load_kg_m2) & np.isfinite(self.coverage_fraction)
            loading = np.array(fallback, copy=True)
            c = self.coverage_fraction[readable]
            loading[readable] = c * self.fuel_load_kg_m2[readable] + (1.0 - c) * fallback[readable]
        parameters = CombustionParameters(
            fuel_load_kg_m2=loading,
            heat_of_combustion_j_kg=heat_of_combustion_j_kg,
            burning_duration_s=burning_duration_s,
            consumed_fraction=consumed_fraction,
        )
        if parameters.heat_release_rate_density_w_m2.shape != shape:
            raise ValueError("combustion parameter arrays must broadcast to fuel-map shape [H,W]")
        return parameters


# Temporal
# Convert first-ignition probability to active-burning probability.
#
# A model's probability of a first ignition during an interval is not its
# probability of active burning at a particular instant. This module supplies an
# explicit temporal assumption for that conversion. Conditional on first ignition
# in ``[0, interval_s]``, the ignition time is uniform on that interval; each cell
# then burns for a deterministic duration. The trained wildfire model does not
# provide this within-interval arrival law or the burning duration.
#
# These are marginal probabilities, so dependence between different cells is not
# restricted. The conversion does not simulate fire propagation, reignition,
# changing fuel consumption, or a time-varying heat-release rate during a burn.
# All times are numeric seconds. No date, timedelta, or implicit unit conversion
# is supported.

def _numeric_array(value: ArrayLike, name: str) -> FloatArray:
    """Copy finite real values without converting strings or time objects."""
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} contains masked values; missing values are not zero")
    try:
        original = np.asarray(value)
        if original.dtype.kind not in "biuf":
            raise ValueError(f"{name} must contain real numeric values")
        result = np.array(original, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain real numeric values") from error
    if result.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite; missing values are not zero")
    return result


def _probability(value: ArrayLike, name: str) -> FloatArray:
    result = _numeric_array(value, name)
    if np.any((result < 0) | (result > 1)):
        raise ValueError(f"{name} must lie in [0, 1]")
    return result


def _interval(value: float) -> float:
    result = _numeric_array(value, "interval_s")
    if result.ndim != 0 or np.asarray(value).dtype.kind == "b" or result <= 0:
        raise ValueError("interval_s must be a positive numeric scalar in seconds")
    return float(result)


def _occupancy_duration(
    value: ArrayLike, name: str, shape: tuple[int, ...], *, allow_zero: bool
) -> FloatArray:
    result = _numeric_array(value, name)
    if np.asarray(value).dtype.kind == "b":
        raise ValueError(f"{name} must contain numeric seconds, not booleans")
    if result.ndim != 0 and result.shape != shape:
        raise ValueError(f"{name} must be a scalar or have exactly probability shape {shape}")
    if np.any(result < 0 if allow_zero else result <= 0):
        relation = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {relation}")
    return result


@dataclass(frozen=True)
class BurningOccupancy:
    """Active-burning probabilities averaged over and at the end of an interval.

    ``mean_active_probability`` is the expectation of the fraction of the
    forecast interval for which each cell burns. Equivalently, it is the time
    average of each cell's instantaneous active-burning probability.
    ``endpoint_active_probability`` is each cell's active-burning probability
    at exactly ``interval_s``. Arrays have identical shape and are read-only.

    Multiplying the mean probability by constant conditional heat-release-rate
    density gives the mean expected source density over the interval. That
    source density may be passed through a fixed linear radiation operator to
    obtain mean expected incident heat flux. Multiplying the resulting mean
    flux by the interval duration gives expected incident heat dose.
    """

    mean_active_probability: FloatArray
    endpoint_active_probability: FloatArray

    def __post_init__(self) -> None:
        mean = _probability(self.mean_active_probability, "mean_active_probability")
        endpoint = _probability(self.endpoint_active_probability, "endpoint_active_probability")
        if mean.shape != endpoint.shape:
            raise ValueError("mean and endpoint probability arrays must have identical shapes")
        mean.setflags(write=False)
        endpoint.setflags(write=False)
        object.__setattr__(self, "mean_active_probability", mean)
        object.__setattr__(self, "endpoint_active_probability", endpoint)


def ignition_to_active_probability(
    new_burn_probability: ArrayLike,
    burning_duration_s: ArrayLike,
    interval_s: float,
) -> BurningOccupancy:
    """Convert probability of first ignition during an interval to occupancy.

    For each cell let ``q`` be the unconditional probability of first ignition
    in ``[0, D]``, where ``D = interval_s > 0``. Given that event, assume an
    ignition time ``A ~ Uniform(0, D)`` and a deterministic burning duration
    ``T = burning_duration_s > 0``. The active period is ``[A, A + T)``.
    A cell that does not ignite in this interval contributes zero occupancy
    through this function. Burning already present at time zero must be handled
    separately with :func:`initial_active_occupancy`.

    The time integral of the active indicator over ``[0, D]`` is
    ``min(T, D - A)``. Averaging over ``A`` gives mean occupancy
    ``q * (r - r**2 / 2)`` if ``T <= D``, where ``r = T / D``;
    if ``T >= D``, it gives ``q / 2``. At time ``D``, activity occurs precisely
    when ``D - T < A <= D``, apart from zero-probability endpoints. Hence the
    endpoint probability is ``q * min(T / D, 1)``.

    Input probabilities must be complete, finite, and in ``[0, 1]``. Duration
    may be a scalar or an array with exactly the probability array's shape;
    implicit broadcasting across cells is rejected. Output shape equals input
    probability shape. This function also supports a scalar probability.

    The uniform arrival assumption is additional information supplied by this
    conversion, not a consequence of a model predicting ``q``. Earlier or later
    ignition distributions can produce different mean flux and endpoint flux.
    """
    probability = _probability(new_burn_probability, "new_burn_probability")
    interval = _interval(interval_s)
    duration = _occupancy_duration(
        burning_duration_s, "burning_duration_s", probability.shape, allow_zero=False
    )
    # Clip before division to avoid overflowing a physically valid T / D.
    ratio = np.minimum(duration, interval) / interval
    mean = probability * (ratio - 0.5 * ratio * ratio)
    endpoint = probability * ratio
    return BurningOccupancy(mean, endpoint)


def initial_active_occupancy(
    initial_active_probability: ArrayLike,
    remaining_burning_duration_s: ArrayLike,
    interval_s: float,
) -> BurningOccupancy:
    """Occupancy from cells that may already be burning at time zero.

    Let ``p`` be the probability a cell is active at time zero and let ``R >= 0``
    be its deterministic remaining duration conditional on that state. It is
    treated as active on ``[0, R)``. For an interval of duration ``D > 0``, mean
    occupancy is ``p * min(R / D, 1)`` and endpoint occupancy is ``p`` if
    ``R > D``, otherwise zero. In particular, ``R == D`` means extinction at
    exactly the forecast endpoint and therefore zero endpoint occupancy.

    ``R == 0`` is allowed and contributes zero at all evaluation times here.
    Duration must be a scalar or have exactly the probability array's shape.
    Probabilities and durations must be complete and finite.

    Combining this result with first-ignition occupancy is justified only when
    the initial-burning event and the forecast first-ignition event are
    disjoint for every cell and their probabilities are unconditional. A
    forecast conditional on being initially unburned must first be weighted
    by that conditioning event's probability.
    """
    probability = _probability(initial_active_probability, "initial_active_probability")
    interval = _interval(interval_s)
    remaining = _occupancy_duration(
        remaining_burning_duration_s,
        "remaining_burning_duration_s",
        probability.shape,
        allow_zero=True,
    )
    mean = probability * (np.minimum(remaining, interval) / interval)
    endpoint = probability * (remaining > interval)
    return BurningOccupancy(mean, endpoint)


# Residence
# Literature-based residence time of a passing surface-fire flaming front.
#
# Anderson (1969) approximates flaming time in a uniform fuel array by
# ``t_minutes = 8 * particle_diameter_inches``. Andrews (2018, section 4.2)
# expresses this as ``t_minutes = 384 / characteristic_SAV_feet_inverse``.
# This is the time for the flaming front to pass one point. It excludes the
# indefinite trailing edge, smouldering, crown fire, and reignition; it does not
# estimate the time needed to traverse an entire coarse raster cell. Applying it
# to a raster means assigning the representative point-scale duration to each
# cell, an additional spatial assumption that the caller must evaluate.
#
# Sources:
# * https://research.fs.usda.gov/download/treesearch/40489.pdf
# * https://research.fs.usda.gov/download/treesearch/55928.pdf
# * https://research.fs.usda.gov/download/treesearch/9521.pdf

# The international inch and foot have exact SI lengths. Convert the numeric
# value sigma_ft^-1 = 0.3048 * sigma_m^-1 before applying minutes -> seconds.
SAV_RESIDENCE_COEFFICIENT_S_PER_M = 384.0 * 60.0 / 0.3048
DIAMETER_RESIDENCE_COEFFICIENT_S_PER_M = 8.0 * 60.0 / 0.0254

_ANDERSON_URL = "https://research.fs.usda.gov/download/treesearch/40489.pdf"
_ANDREWS_URL = "https://research.fs.usda.gov/download/treesearch/55928.pdf"
_SCOTT_BURGAN_URL = "https://research.fs.usda.gov/download/treesearch/9521.pdf"

# Scott and Burgan (2005), table 7, printed p.18. Columns are name,
# dry load (short tons/acre) for [dead1h,dead10h,dead100h,liveherb,livewoody],
# and SAV (ft^-1) for [dead1h,liveherb,livewoody]. For ALL models dead10h
# SAV=109 and dead100h SAV=30; common particle density=32 lb/ft^3 (p.17).
# 9999 is the source-table placeholder in classes whose load is zero, so it
# contributes no surface area and has no influence on characteristic SAV.
_FBFM40_PARAMETERS = MappingProxyType({
    101: ("GR1", (0.10, 0.00, 0.00, 0.30, 0.00), (2200, 2000, 9999)),
    102: ("GR2", (0.10, 0.00, 0.00, 1.00, 0.00), (2000, 1800, 9999)),
    103: ("GR3", (0.10, 0.40, 0.00, 1.50, 0.00), (1500, 1300, 9999)),
    104: ("GR4", (0.25, 0.00, 0.00, 1.90, 0.00), (2000, 1800, 9999)),
    105: ("GR5", (0.40, 0.00, 0.00, 2.50, 0.00), (1800, 1600, 9999)),
    106: ("GR6", (0.10, 0.00, 0.00, 3.40, 0.00), (2200, 2000, 9999)),
    107: ("GR7", (1.00, 0.00, 0.00, 5.40, 0.00), (2000, 1800, 9999)),
    108: ("GR8", (0.50, 1.00, 0.00, 7.30, 0.00), (1500, 1300, 9999)),
    109: ("GR9", (1.00, 1.00, 0.00, 9.00, 0.00), (1800, 1600, 9999)),
    121: ("GS1", (0.20, 0.00, 0.00, 0.50, 0.65), (2000, 1800, 1800)),
    122: ("GS2", (0.50, 0.50, 0.00, 0.60, 1.00), (2000, 1800, 1800)),
    123: ("GS3", (0.30, 0.25, 0.00, 1.45, 1.25), (1800, 1600, 1600)),
    124: ("GS4", (1.90, 0.30, 0.10, 3.40, 7.10), (1800, 1600, 1600)),
    141: ("SH1", (0.25, 0.25, 0.00, 0.15, 1.30), (2000, 1800, 1600)),
    142: ("SH2", (1.35, 2.40, 0.75, 0.00, 3.85), (2000, 9999, 1600)),
    143: ("SH3", (0.45, 3.00, 0.00, 0.00, 6.20), (1600, 9999, 1400)),
    144: ("SH4", (0.85, 1.15, 0.20, 0.00, 2.55), (2000, 1800, 1600)),
    145: ("SH5", (3.60, 2.10, 0.00, 0.00, 2.90), (750, 9999, 1600)),
    146: ("SH6", (2.90, 1.45, 0.00, 0.00, 1.40), (750, 9999, 1600)),
    147: ("SH7", (3.50, 5.30, 2.20, 0.00, 3.40), (750, 9999, 1600)),
    148: ("SH8", (2.05, 3.40, 0.85, 0.00, 4.35), (750, 9999, 1600)),
    149: ("SH9", (4.50, 2.45, 0.00, 1.55, 7.00), (750, 1800, 1500)),
    161: ("TU1", (0.20, 0.90, 1.50, 0.20, 0.90), (2000, 1800, 1600)),
    162: ("TU2", (0.95, 1.80, 1.25, 0.00, 0.20), (2000, 9999, 1600)),
    163: ("TU3", (1.10, 0.15, 0.25, 0.65, 1.10), (1800, 1600, 1400)),
    164: ("TU4", (4.50, 0.00, 0.00, 0.00, 2.00), (2300, 9999, 2000)),
    165: ("TU5", (4.00, 4.00, 3.00, 0.00, 3.00), (1500, 9999, 750)),
    181: ("TL1", (1.00, 2.20, 3.60, 0.00, 0.00), (2000, 9999, 9999)),
    182: ("TL2", (1.40, 2.30, 2.20, 0.00, 0.00), (2000, 9999, 9999)),
    183: ("TL3", (0.50, 2.20, 2.80, 0.00, 0.00), (2000, 9999, 9999)),
    184: ("TL4", (0.50, 1.50, 4.20, 0.00, 0.00), (2000, 9999, 9999)),
    185: ("TL5", (1.15, 2.50, 4.40, 0.00, 0.00), (2000, 9999, 1600)),
    186: ("TL6", (2.40, 1.20, 1.20, 0.00, 0.00), (2000, 9999, 9999)),
    187: ("TL7", (0.30, 1.40, 8.10, 0.00, 0.00), (2000, 9999, 9999)),
    188: ("TL8", (5.80, 1.40, 1.10, 0.00, 0.00), (1800, 9999, 9999)),
    189: ("TL9", (6.65, 3.30, 4.15, 0.00, 0.00), (1800, 9999, 1600)),
    201: ("SB1", (1.50, 3.00, 11.00, 0.00, 0.00), (2000, 9999, 9999)),
    202: ("SB2", (4.50, 4.25, 4.00, 0.00, 0.00), (2000, 9999, 9999)),
    203: ("SB3", (5.50, 2.75, 3.00, 0.00, 0.00), (2000, 9999, 9999)),
    204: ("SB4", (5.25, 3.50, 5.25, 0.00, 0.00), (2000, 9999, 9999)),
})


def _real_array(value: ArrayLike, name: str, *, allow_missing: bool = False) -> FloatArray:
    """Copy genuine numeric scalars/maps without accepting strings or booleans."""
    if np.ma.isMaskedArray(value) and not allow_missing and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} contains masked values; a missing duration is not zero")
    try:
        original = np.asanyarray(value)
        if original.dtype.kind not in "iuf":
            raise ValueError(f"{name} must contain real numeric values, not booleans or strings")
        result = np.array(original, dtype=np.float64, copy=True)
        if np.ma.isMaskedArray(value):
            result[np.ma.getmaskarray(value)] = np.nan
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must contain real numeric values") from error
    if result.ndim not in (0, 2) or result.size == 0:
        raise ValueError(f"{name} must be a scalar or a nonempty spatial matrix [H,W]")
    if not allow_missing and not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite; a missing duration is not zero")
    return result


def _positive(value: ArrayLike, name: str) -> FloatArray:
    result = _real_array(value, name)
    if np.any(result <= 0):
        raise ValueError(f"{name} must be strictly positive")
    return result


def _immutable_array(value: FloatArray) -> FloatArray:
    # A bytes-backed view cannot have WRITEABLE re-enabled, unlike setflags on
    # an owning ndarray. Also isolate the result from the caller's input.
    return np.frombuffer(value.tobytes(), dtype=np.float64).reshape(value.shape)


def _freeze_metadata(value: Any) -> Any:
    """Make provenance deeply immutable and limit it to JSON-compatible data."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("provenance mapping keys must be strings")
        return MappingProxyType({key: _freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_metadata(item) for item in value)
    if isinstance(value, np.generic):
        return _freeze_metadata(value.item())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and np.isfinite(value):
        return value
    raise ValueError("provenance must contain finite JSON-compatible metadata")


def _thaw_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_metadata(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_metadata(item) for item in value]
    return value


def _metadata(method: str, equation: str, provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "method": method,
        "equation": equation,
        "output_unit": "seconds",
        "sources": [
            {"author_year": "Anderson 1969", "url": _ANDERSON_URL, "location": "printed pp.15-16"},
            {"author_year": "Andrews 2018", "url": _ANDREWS_URL, "location": "section 4.2, printed p.27"},
        ],
        "meaning": "point-scale passing surface-fire flaming-front residence time",
        "limitations": [
            "excludes indefinite trailing burning and smouldering",
            "assumes no fuel-bed packing effect",
            "does not determine coarse-cell traversal time or subcell flame positions",
            "does not establish arrival time or an active-flame observation",
        ],
    }
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        result["input_provenance"] = provenance
    return result


@dataclass(frozen=True, eq=False)
class FlameResidenceTime:
    """A complete deterministic residence-time scenario in numeric seconds.

    ``duration_s`` is a strictly positive, finite scalar or nonempty [H,W]
    matrix. Scalar duration may be used for all cells; a matrix must be aligned
    by the consumer. Both the copied array and provenance are immutable.
    Missing values and nonburnable cells do not receive durations implicitly.
    This type is a duration input, not an assertion that any cell is burning.
    Direct construction requires explicit provenance for a supplied scenario.
    """

    duration_s: ArrayLike
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        duration = _positive(self.duration_s, "duration_s")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        object.__setattr__(self, "duration_s", _immutable_array(duration))
        object.__setattr__(self, "provenance", _freeze_metadata(self.provenance))

    def provenance_dict(self) -> dict[str, Any]:
        """Return an independent JSON-ready mutable copy of the provenance."""
        return _thaw_metadata(self.provenance)

    @classmethod
    def from_surface_area_to_volume(
        cls, sav_m_inv: ArrayLike, *, provenance: Mapping[str, Any] | None = None
    ) -> FlameResidenceTime:
        """Apply ``duration_s = (384 * 60 / 0.3048) / sav_m_inv``.

        ``sav_m_inv`` is the characteristic particle surface area divided by
        particle volume, in m^-1, and must be strictly positive and finite.
        The original equation uses minutes and ft^-1. Its equivalent SI
        coefficient is 75590.55118110236 s/m. For cylindrical particles,
        neglecting end area, ``sav_m_inv = 4 / diameter_m``.
        """
        sav = _positive(sav_m_inv, "sav_m_inv")
        with np.errstate(over="ignore", under="ignore", divide="ignore"):
            duration = SAV_RESIDENCE_COEFFICIENT_S_PER_M / sav
        return cls(duration, _metadata(
            "anderson_1969_characteristic_sav",
            "duration_s = (384 * 60 / 0.3048) / sav_m_inv",
            provenance,
        ))

    @classmethod
    def from_particle_diameter(
        cls, diameter_m: ArrayLike, *, provenance: Mapping[str, Any] | None = None
    ) -> FlameResidenceTime:
        """Apply Anderson's ``duration_s = (8 * 60 / 0.0254) * diameter_m``.

        Diameter is in metres and must be strictly positive and finite. The
        source relation uses particle diameter in inches and time in minutes.
        It approximates flaming time in a uniform fuel array; it does not mean
        the entire heterogeneous fuelbed burns until all particles are consumed.
        """
        diameter = _positive(diameter_m, "diameter_m")
        with np.errstate(over="ignore", under="ignore"):
            duration = DIAMETER_RESIDENCE_COEFFICIENT_S_PER_M * diameter
        return cls(duration, _metadata(
            "anderson_1969_particle_diameter",
            "duration_s = (8 * 60 / 0.0254) * diameter_m",
            provenance,
        ))

    @classmethod
    def from_eucalypt_wood_diameter(
        cls, diameter_mm: ArrayLike, *, provenance: Mapping[str, Any] | None = None
    ) -> FlameResidenceTime:
        """Apply Burrows' oven-dry jarrah-twig flame-out time in its tested range.

        Burrows (1994), printed p.69, equation 6-1, gives
        ``duration_s = 0.871 * diameter_mm**1.875``. Diameter must be in the
        tested inclusive range 1--16 mm. The experiments used individual
        oven-dried jarrah (Eucalyptus marginata) twig samples 10 cm long,
        burning in still air at 26--32 degrees Celsius.

        This is a conditional laboratory scenario for individual wood flaming
        duration, not the Anderson front-passage duration, and not a general
        extinction-time law for other fuels, moisture, wind, crown fire, or
        coarse raster cells. It does not include smouldering after flame-out.
        """
        diameter = _positive(diameter_mm, "diameter_mm")
        if np.any((diameter < 1.0) | (diameter > 16.0)):
            raise ValueError("diameter_mm must lie in the tested inclusive range [1,16] mm")
        metadata: dict[str, Any] = {
            "method": "burrows_1994_oven_dry_jarrah_twig_flame_out",
            "equation": "duration_s = 0.871 * diameter_mm**1.875",
            "output_unit": "seconds",
            "sources": [{
                "author_year": "Burrows 1994",
                "url": "https://library.dbca.wa.gov.au/FullTextFiles/016094.pdf",
                "location": "printed p.69, equation 6-1",
            }],
            "meaning": "individual oven-dry jarrah twig flaming duration under laboratory conditions",
            "tested_diameter_range_mm": [1.0, 16.0],
            "laboratory_conditions": {
                "species": "Eucalyptus marginata (jarrah)",
                "sample_length_cm": 10.0,
                "fuel_moisture": "oven-dried",
                "airflow": "still air",
                "ambient_temperature_celsius_range": [26.0, 32.0],
            },
            "limitations": [
                "not a universal law for complete fuelbed flame extinction",
                "not calibrated for other species, moist fuels, or windy conditions",
                "does not determine coarse-cell traversal time or subcell flame positions",
                "excludes smouldering after flame-out",
            ],
        }
        if provenance is not None:
            if not isinstance(provenance, Mapping):
                raise ValueError("provenance must be a mapping")
            metadata["input_provenance"] = provenance
        return cls(0.871 * diameter**1.875, metadata)

    @classmethod
    def from_fbfm40(
        cls,
        codes: ArrayLike,
        *,
        fallback_sav_m_inv: ArrayLike | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> FlameResidenceTime:
        """Map standard Scott--Burgan numeric fuel codes to front duration.

        Supported codes are 101--109 (GR), 121--124 (GS), 141--149 (SH),
        161--165 (TU), 181--189 (TL), and 201--204 (SB). Custom codes,
        missing values, masked cells, and nonburnable codes 91,92,93,98,99
        fail unless ``fallback_sav_m_inv`` explicitly supplies a positive
        finite scalar or matrix matching ``codes``. A fallback is a caller's
        combustion scenario, including any override of a nonburnable class,
        and is recorded separately from the source-based assignment.

        Characteristic SAV weights every particle class by its surface area:
        ``sigma = sum(load * particle_sigma**2) / sum(load * particle_sigma)``.
        The common particle density cancels, as does the common load unit.
        This follows Andrews (2018), sections 3.2.3--3.2.5, pp.21--24.
        Dynamic curing merely moves herbaceous load between live and dead
        categories while preserving its particle SAV (Scott--Burgan p.6).
        The combined characteristic SAV is therefore invariant to the curing
        fraction; no live moisture value is assumed for this duration alone.

        The numeric raster codes identify reference fuelbeds. A modal coarse
        raster code does not establish homogeneous fuel, cell traversal time,
        or a measured event-specific residence time.
        """
        code_array = _real_array(codes, "codes", allow_missing=True)
        finite = np.isfinite(code_array)
        if np.any(finite & (code_array != np.floor(code_array))):
            raise ValueError("codes must contain integer-valued fuel-model identifiers")
        sav = np.full(code_array.shape, np.nan, dtype=np.float64)
        used_codes: dict[str, str] = {}
        for code, (name, loads, three_sav) in _FBFM40_PARAMETERS.items():
            selection = finite & (code_array == code)
            if not np.any(selection):
                continue
            particle_sav = np.array([three_sav[0], 109.0, 30.0, three_sav[1], three_sav[2]])
            loading = np.asarray(loads)
            surface_weights = loading * particle_sav
            characteristic_sav_ft_inv = np.dot(surface_weights, particle_sav) / np.sum(surface_weights)
            sav[selection] = characteristic_sav_ft_inv / 0.3048
            used_codes[str(code)] = name
        unsupported = ~np.isfinite(sav)
        unsupported_codes = [int(item) for item in np.unique(code_array[unsupported & finite])]
        if fallback_sav_m_inv is not None:
            fallback = _positive(fallback_sav_m_inv, "fallback_sav_m_inv")
            if fallback.ndim != 0 and fallback.shape != sav.shape:
                raise ValueError("fallback_sav_m_inv must be a scalar or match codes shape exactly")
            sav = np.where(unsupported, fallback, sav)
        elif np.any(unsupported):
            raise ValueError(
                "FBFM40 duration is unavailable for missing, nonburnable, or unsupported codes "
                f"{unsupported_codes}; supply an explicit fallback_sav_m_inv scenario or exclude these cells"
            )
        metadata = _metadata(
            "scott_burgan_2005_fbfm40_anderson_residence",
            "sigma_ft_inv = sum(load * particle_sav_ft_inv**2) / sum(load * particle_sav_ft_inv); "
            "duration_s = 384 * 60 / sigma_ft_inv",
            provenance,
        )
        metadata.update({
            "fuel_catalog": {"author_year": "Scott and Burgan 2005", "url": _SCOTT_BURGAN_URL,
                             "location": "table 7, p.18; constants p.17; code assignment table 1, p.5"},
            "sav_weighting_source": {"author_year": "Andrews 2018", "url": _ANDREWS_URL,
                                     "location": "sections 3.2.3-3.2.5, pp.21-24"},
            "dynamic_curing": "characteristic SAV invariant because transferred herbaceous load preserves SAV (Scott and Burgan p.6)",
            "gs4_source_note": "table 7 parameters imply approximately 1631 ft^-1, consistent with Andrews table 8c; Scott and Burgan GS4 summary reports 1674 ft^-1",
            "catalog_codes_used": used_codes,
            "catalog_cell_count": int(np.count_nonzero(~unsupported)),
            "fallback_cell_count": int(np.count_nonzero(unsupported)),
            "missing_code_cell_count": int(np.count_nonzero(~finite)),
            "unsupported_finite_codes": unsupported_codes,
            "fallback_scenario_supplied": fallback_sav_m_inv is not None,
        })
        if fallback_sav_m_inv is not None:
            metadata["fallback_sav_m_inv"] = np.asarray(fallback).tolist()
        with np.errstate(over="ignore", under="ignore", divide="ignore"):
            duration = SAV_RESIDENCE_COEFFICIENT_S_PER_M / sav
        return cls(duration, metadata)

    @classmethod
    def from_fbfm40_raster(
        cls,
        path: str | Path,
        *,
        grid: AffineGrid | None = None,
        expected_shape: tuple[int, int] | None = None,
        epsg: int | None = None,
        fallback_sav_m_inv: ArrayLike | None = None,
    ) -> FlameResidenceTime:
        """Read a single-band reference-fuel raster and derive residence seconds.

        The raster must have a projected CRS whose linear unit is one metre.
        Optional ``grid``, ``expected_shape`` and ``epsg`` check exact affine,
        spatial-shape and CRS alignment. Supply all three when connecting the
        result to a prediction sample; they may be omitted for general loading,
        whose source grid is retained in provenance. No resampling is performed.

        Masked/missing, nonburnable and unsupported codes retain the strict
        :meth:`from_fbfm40` contract: they fail unless an explicit positive
        ``fallback_sav_m_inv`` scenario is supplied. The source file, SHA256,
        grid and tags are recorded separately from the literature-based duration
        law. Reference fuel classes do not provide measured event-specific
        extinction times. Rasterio is imported only by this constructor.
        """

        if grid is not None and not isinstance(grid, AffineGrid):
            raise ValueError("grid must be an AffineGrid")
        shape = None
        if expected_shape is not None:
            try:
                shape = tuple(expected_shape)
            except TypeError as error:
                raise ValueError("expected_shape must contain two positive integers") from error
            if len(shape) != 2 or any(
                isinstance(value, (bool, np.bool_))
                or not isinstance(value, Integral)
                or value <= 0
                for value in shape
            ):
                raise ValueError("expected_shape must contain two positive integers")
        if epsg is not None and (
            isinstance(epsg, (bool, np.bool_))
            or not isinstance(epsg, Integral)
            or epsg <= 0
        ):
            raise ValueError("epsg must be a positive integer")
        try:
            import rasterio
        except ImportError as error:
            raise ImportError("Reading FBFM40 GeoTIFFs requires the optional rasterio dependency") from error

        source_path = resolve_recorded_path(path).resolve()
        with rasterio.open(source_path) as source:
            if source.count != 1:
                raise ValueError("FBFM40 raster must have one static band")
            if source.crs is None or not source.crs.is_projected:
                raise ValueError("FBFM40 raster must use a projected CRS in metres")
            if source.crs.linear_units_factor[1] != 1.0:
                raise ValueError("FBFM40 raster must use metre linear units")
            transform = tuple(float(value) for value in tuple(source.transform)[:6])
            raster_grid = AffineGrid(transform)
            if grid is not None and raster_grid.transform != grid.transform:
                raise ValueError("FBFM40 raster affine transform does not match grid")
            if shape is not None and source.shape != shape:
                raise ValueError("FBFM40 raster shape does not match expected_shape")
            source_epsg = source.crs.to_epsg()
            if epsg is not None and source_epsg != epsg:
                raise ValueError("FBFM40 raster CRS does not match epsg")
            codes = source.read(1, masked=True)
            source_metadata = {
                "source": "FBFM40 reference-fuel raster",
                "path": str(source_path),
                "crs": source.crs.to_string(),
                "epsg": source_epsg,
                "transform": list(transform),
                "shape": list(source.shape),
                "source_tags": source.tags(),
                "physical_definition": "reference fuel classes, not measured event-specific flaming durations",
                "alignment_checks": {
                    "affine_transform": grid is not None,
                    "shape": expected_shape is not None,
                    "epsg": epsg is not None,
                },
            }
        digest = sha256()
        with source_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        source_metadata["sha256"] = digest.hexdigest()
        return cls.from_fbfm40(
            codes,
            fallback_sav_m_inv=fallback_sav_m_inv,
            provenance=source_metadata,
        )


# Flames
# Estimated surface-flame activity at representative grid locations.
#
# Residence time describes flaming at a fixed fuel location. A selected cell
# center is a model location, not a measured flame or a subcell fire perimeter.
# Known arrivals and uncertain next-interval arrivals have separate public APIs;
# neither identifies smoldering, reignition, or crown-fire activity.

def _real(value: ArrayLike, name: str) -> NDArray[np.float64]:
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} requires an explicit validity mask; masked values are not zero")
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain real numeric values, not booleans or time objects")
    return np.array(raw, dtype=np.float64, copy=True)


def _flame_scalar(value: float, name: str, *, positive: bool = False) -> float:
    array = _real(value, name)
    if array.ndim != 0 or not np.isfinite(array) or (positive and array <= 0):
        raise ValueError(f"{name} must be a {'positive ' if positive else ''}finite numeric scalar")
    return float(array)


def _matrix(value: ArrayLike, name: str) -> NDArray[np.float64]:
    array = _real(value, name)
    if array.ndim != 2 or 0 in array.shape:
        raise ValueError(f"{name} must have nonempty shape [H,W]")
    if np.any(np.isinf(array)):
        raise ValueError(f"{name} cannot contain infinity")
    return array


def _valid(value, array, name):
    if value is None:
        return np.isfinite(array)
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} must be an unmasked boolean matrix")
    valid = np.asarray(value)
    if valid.dtype != np.bool_ or valid.shape != array.shape:
        raise ValueError(f"{name} must be boolean and match shape {array.shape}")
    if np.any(valid & ~np.isfinite(array)):
        raise ValueError(f"{name} cannot mark a missing value valid")
    return valid.copy()


def _flame_duration(residence_time: FlameResidenceTime, shape) -> NDArray[np.float64]:
    if not isinstance(residence_time, FlameResidenceTime):
        raise TypeError("residence_time must be FlameResidenceTime")
    duration = np.asarray(residence_time.duration_s)
    if duration.ndim == 0:
        return np.full(shape, float(duration))
    if duration.shape != shape:
        raise ValueError(f"residence duration must be scalar or match shape {shape}")
    return duration


@dataclass(frozen=True)
class FlamePositions:
    """Selected grid centers; rows/columns are zero-based and x/y are metres.

    ``probabilities`` are estimates under the map's timing and fuel assumptions.
    Selecting a probability threshold does not establish detection or accuracy.
    Empty maps return arrays of shapes [0,2], [0,2], and [0].
    """

    cells_rc: NDArray[np.int64]
    coordinates_xy_m: NDArray[np.float64]
    probabilities: NDArray[np.float64]

    def __post_init__(self):
        raw_cells = np.asarray(self.cells_rc)
        if raw_cells.dtype.kind not in "iu":
            raise ValueError("cell indices must contain integers, not fractional values or booleans")
        if np.any(raw_cells > np.iinfo(np.int64).max):
            raise ValueError("cell indices exceed the supported int64 range")
        cells = np.array(raw_cells, dtype=np.int64, copy=True)
        xy = _real(self.coordinates_xy_m, "coordinates_xy_m")
        probability = _real(self.probabilities, "probabilities")
        if cells.ndim != 2 or cells.shape[1] != 2 or xy.shape != cells.shape or probability.shape != (len(cells),):
            raise ValueError("positions must have shapes [N,2], [N,2], and [N]")
        if np.any(cells < 0) or not np.all(np.isfinite(xy)) or not np.all(np.isfinite(probability)) or np.any((probability <= 0) | (probability > 1)):
            raise ValueError("positions require nonnegative cell indices, finite coordinates and probabilities in (0,1]")
        for name, array in (("cells_rc", cells), ("coordinates_xy_m", xy), ("probabilities", probability)):
            array.setflags(write=False)
            object.__setattr__(self, name, array)


@dataclass(frozen=True)
class ActiveFlameMap:
    """Instantaneous estimated probability of surface flaming, shape [H,W].

    Invalid cells contain NaN and remain unclassified. ``time_s`` is measured
    from the origin named by the caller. Optional remaining duration applies
    only to deterministic arrival scenarios, not to a forecast probability.
    """

    probability: ArrayLike
    valid: ArrayLike
    grid: AffineGrid
    time_s: float
    metadata: dict
    remaining_duration_s: ArrayLike | None = None

    def __post_init__(self):
        if not isinstance(self.grid, AffineGrid):
            raise TypeError("grid must be AffineGrid in projected metres")
        probability = _matrix(self.probability, "probability")
        valid = _valid(self.valid, probability, "valid")
        if np.any(valid & ((probability < 0) | (probability > 1))):
            raise ValueError("valid flame probabilities must lie in [0,1]")
        probability[~valid] = np.nan
        remaining = None
        if self.remaining_duration_s is not None:
            remaining = _matrix(self.remaining_duration_s, "remaining_duration_s")
            if remaining.shape != probability.shape or np.any(valid & (~np.isfinite(remaining) | (remaining < 0))):
                raise ValueError("remaining duration must match shape and be finite nonnegative seconds on valid cells")
            remaining[~valid] = np.nan
            remaining.setflags(write=False)
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        probability.setflags(write=False)
        valid.setflags(write=False)
        object.__setattr__(self, "probability", probability)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "time_s", _flame_scalar(self.time_s, "time_s"))
        object.__setattr__(self, "metadata", deepcopy(self.metadata))
        object.__setattr__(self, "remaining_duration_s", remaining)

    def positions(self, *, min_probability: float) -> FlamePositions:
        """Return valid centers whose probability is at least an explicit cutoff."""
        threshold = _flame_scalar(min_probability, "min_probability", positive=True)
        if threshold > 1:
            raise ValueError("min_probability must be in (0,1]")
        selected = self.valid & (self.probability >= threshold)
        return FlamePositions(
            np.argwhere(selected), self.grid.centers(self.probability.shape)[selected],
            self.probability[selected],
        )


@dataclass(frozen=True)
class ActiveFlameForecast:
    """New-ignition surface-flame estimates for one specified forecast interval.

    The mean is time-averaged occupancy; only ``endpoint`` describes activity
    at an instant. Existing flames are excluded because cumulative burned area
    does not determine their age. Arrival inside the interval is assumed uniform
    conditional on a first-new-burning event.
    """

    new_burn_probability: NDArray[np.float64]
    valid: NDArray[np.bool_]
    mean_active_probability: NDArray[np.float64]
    endpoint: ActiveFlameMap
    residence_time: FlameResidenceTime
    interval_s: float
    metadata: dict

    def __post_init__(self):
        q = _matrix(self.new_burn_probability, "new_burn_probability")
        valid = _valid(self.valid, q, "valid")
        mean = _matrix(self.mean_active_probability, "mean_active_probability")
        if mean.shape != q.shape or self.endpoint.probability.shape != q.shape or not np.array_equal(valid, self.endpoint.valid):
            raise ValueError("forecast matrices and endpoint validity must match")
        if np.any(valid & ((q < 0) | (q > 1) | ~np.isfinite(mean) | (mean < 0) | (mean > 1))):
            raise ValueError("valid forecast probabilities must be finite in [0,1]")
        _flame_duration(self.residence_time, q.shape)
        interval = _flame_scalar(self.interval_s, "interval_s", positive=True)
        if self.endpoint.time_s != interval:
            raise ValueError("endpoint time must equal forecast interval")
        for name, array in (("new_burn_probability", q), ("valid", valid), ("mean_active_probability", mean)):
            if name != "valid":
                array[~valid] = np.nan
            array.setflags(write=False)
            object.__setattr__(self, name, array)
        object.__setattr__(self, "interval_s", interval)
        object.__setattr__(self, "metadata", deepcopy(self.metadata))


def active_flames_from_arrival(
    arrival_time_s: ArrayLike,
    residence_time: FlameResidenceTime,
    time_s: float,
    *,
    grid: AffineGrid,
    arrival_valid: ArrayLike | None = None,
) -> ActiveFlameMap:
    """Apply ``arrival <= time < arrival + duration`` at each valid location.

    All times are numeric seconds sharing one origin. Negative arrivals are
    permitted. An estimated arrival produces a scenario indicator, not a claim
    that the actual arrival or flame position is known. Arrival uncertainty is
    not integrated out by this function. Duration is point residence time;
    propagation through the interior of a large cell is not resolved.
    """
    arrival = _matrix(arrival_time_s, "arrival_time_s")
    valid = _valid(arrival_valid, arrival, "arrival_valid")
    duration = _flame_duration(residence_time, arrival.shape)
    time = _flame_scalar(time_s, "time_s")
    # Compare elapsed age to duration without overflowing arrival + duration.
    with np.errstate(over="ignore", invalid="ignore"):
        age = time - arrival
    active = valid & (age >= 0) & (age < duration)
    probability = np.where(valid, active.astype(float), np.nan)
    remaining = np.zeros(arrival.shape)
    remaining[active] = duration[active] - age[active]
    remaining[~valid] = np.nan
    metadata = {
        "semantics": "surface flaming at representative grid locations under supplied arrival and residence scenario",
        "activity_interval": "[arrival_time_s, arrival_time_s + duration_s)",
        "arrival_uncertainty": "not integrated; supplied arrivals are point estimates or known times",
        "time_origin": "caller-supplied common origin",
        "residence_time": residence_time.provenance_dict(),
        "position_semantics": "projected grid-cell centers, not measured subcell flame geometry",
        "excluded_processes": "smoldering, trailing intermittent flames, reignition, crown combustion and within-cell propagation",
    }
    return ActiveFlameMap(probability, valid, grid, time, metadata, remaining)


def forecast_active_flames(
    new_burn_probability: ArrayLike,
    residence_time: FlameResidenceTime,
    interval_s: float,
    *,
    grid: AffineGrid,
    probability_valid: ArrayLike | None = None,
) -> ActiveFlameForecast:
    """Convert first-new-burning probability to mean and endpoint flaming.

    For ``q=P(A in [0,D])``, assume ``A | first event ~ Uniform(0,D)`` and a
    fixed point residence ``T``. With ``r=min(T/D,1)``, endpoint activity is
    ``q*r`` and interval-mean activity is ``q*(r-r*r/2)``. The trained model
    supplies q, not this conditional arrival law or a calibrated flame target.
    Unknown cells remain NaN. No observed-current-flame inference is performed.
    """
    q = _matrix(new_burn_probability, "new_burn_probability")
    valid = _valid(probability_valid, q, "probability_valid")
    if np.any(valid & ((q < 0) | (q > 1))):
        raise ValueError("valid new-burn probabilities must lie in [0,1]")
    duration = _flame_duration(residence_time, q.shape)
    interval = _flame_scalar(interval_s, "interval_s", positive=True)
    occupancy = ignition_to_active_probability(np.where(valid, q, 0.0), duration, interval)
    mean = np.where(valid, occupancy.mean_active_probability, np.nan)
    endpoint = np.where(valid, occupancy.endpoint_active_probability, np.nan)
    q[~valid] = np.nan
    metadata = {
        "scope": "newly igniting locations only; ongoing flames require separate age or present-flame inputs",
        "arrival_time_assumption": "uniform within forecast interval conditional on first-new-burning event",
        "residence_time": residence_time.provenance_dict(),
        "forecast_interval_s": interval,
        "position_semantics": "projected grid-cell centers with estimated instantaneous probability",
        "calibration": "derived timing scenario; not calibrated against active-flame observations",
    }
    snapshot = ActiveFlameMap(endpoint, valid, grid, interval, metadata)
    return ActiveFlameForecast(q, valid, mean, snapshot, residence_time, interval, metadata)


# Pipeline
# A trained one-hour new-burn predictor connected to incident radiant heat.
#
# New burning during an interval is converted to active occupancy under an
# explicit uniform conditional arrival-time model. Unknown ignition probabilities
# produce bounds, not invented zero observations. Present burning requires an
# arrival/age and duration, or explicitly supplied activity and remaining time.
# Cumulative burned area alone does not identify ongoing combustion.

def _numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError("masked inputs require explicit numeric arrays and separate validity masks")
    return np.asarray(value)


def _single_matrix(value: Any, name: str) -> np.ndarray:
    array = _numpy(value)
    if array.ndim < 2 or any(size != 1 for size in array.shape[:-2]):
        raise ValueError(f"{name} must be [H,W] or have only singleton leading dimensions")
    if min(array.shape[-2:]) < 1:
        raise ValueError(f"{name} must have a nonempty spatial matrix")
    return array.reshape(array.shape[-2:])


def _mask(value: Any, shape: tuple[int, int], name: str) -> np.ndarray:
    array = _single_matrix(value, name)
    if array.dtype != np.bool_ or array.shape != shape:
        raise ValueError(f"{name} must be boolean and match shape {shape}")
    return np.array(array, copy=True)


def _heat_map(value: ArrayLike, shape: tuple[int, int], name: str, *, upper=None) -> FloatArray:
    array = _physical_array(value, name, upper=upper)
    if array.ndim == 0:
        return np.full(shape, float(array))
    if array.shape != shape:
        raise ValueError(f"{name} must be scalar or exactly match shape {shape}")
    return array


@dataclass(frozen=True)
class IntegratedHeatPrediction:
    """One forecast interval, with [H,W] matrices and explicit source coverage.

    ``expected_heat_flux_w_m2`` is the interval-mean full supplied-domain radiant
    flux. It is NaN if any unresolved positive emitting source can contribute.
    ``known_source_heat_flux_w_m2`` is the finite expected contribution of known
    new-burn sources and any supplied present-active sources. Under the stated
    fixed combustion/arrival assumptions it equals the lower bound. Upper bounds
    let each unknown new-event probability vary up to one and, when arrival
    timing is selected, each unknown existing-fire age vary over nonnegative
    ages. Existing fire is restricted to known already-burned support. They do
    not bound unmodeled convection, emission parameters, outside-domain fires,
    or an existing fire hidden by unknown cumulative-state coverage.
    """

    new_burn_probability: FloatArray
    probability_valid: np.ndarray
    original_probability_valid: np.ndarray
    externally_supplied_probability_mask: np.ndarray
    mean_active_burning_probability: FloatArray
    endpoint_active_burning_probability: FloatArray
    initial_active_burning_probability: FloatArray
    initial_remaining_burning_duration_s: FloatArray
    initial_burning_valid: np.ndarray
    active_burning_valid: np.ndarray
    endpoint_active_burning_valid: np.ndarray
    expected_heat_flux_w_m2: FloatArray
    known_source_heat_flux_w_m2: FloatArray
    heat_flux_lower_bound_w_m2: FloatArray
    heat_flux_upper_bound_w_m2: FloatArray
    expected_incident_energy_j_m2: FloatArray
    incident_energy_lower_bound_j_m2: FloatArray
    incident_energy_upper_bound_j_m2: FloatArray
    endpoint_heat_flux_lower_bound_w_m2: FloatArray
    endpoint_heat_flux_upper_bound_w_m2: FloatArray
    expected_endpoint_heat_flux_w_m2: FloatArray
    complete: bool
    endpoint_complete: bool
    metadata: dict

    @property
    def expected_heat_flux_kw_m2(self) -> FloatArray:
        return self.expected_heat_flux_w_m2 / 1000.0

    @property
    def known_source_heat_flux_kw_m2(self) -> FloatArray:
        return self.known_source_heat_flux_w_m2 / 1000.0

    def endpoint_flame_map(self):
        """Return the instantaneous endpoint probability map and cell positions.

        This includes present flames inferred from arrival and duration, or
        supplied explicitly. Use positions(min_probability=...) on
        the returned map to make the selection rule explicit.
        """

        return ActiveFlameMap(
            self.endpoint_active_burning_probability, self.endpoint_active_burning_valid,
            AffineGrid(tuple(self.metadata["affine_transform"])),
            self.metadata["forecast_interval_s"], self.metadata,
        )


class WildfireHeatModel:
    """Compose a trained one-hour wildfire predictor and finite-cell radiation.

    ``combustion.burning_duration_s`` is also the duration of active emission
    after a future ignition. First-event arrival is uniform in the next hour,
    conditional on that event. Sample predictions use available arrival/elapsed
    data to include ongoing burning by default. Raw predictions accept arrival
    times or explicit activity and remaining duration. Without either, only new
    burning is modeled. One invocation processes one spatial snapshot.

    Public prediction methods return ``(expected_heat_flux_w_m2, coordinates)``
    with shapes [H,W] and [H,W,2]. Coordinate entries are receiver cell-center
    (latitude, longitude) in degrees, EPSG:4326. The ``*_details`` methods retain
    probabilities, physical bounds, dose, source coverage, and provenance.
    """

    def __init__(
        self,
        predictor: Any,
        *,
        grid: AffineGrid,
        combustion: CombustionParameters,
        radiative_fraction: ArrayLike,
        emission_height_m: float,
        receiver_height_m: float = 0.0,
        atmospheric_transmissivity: float = 1.0,
        interval_s: float = 3600.0,
        predictor_provenance: dict | None = None,
        residence_time: FlameResidenceTime | None = None,
        epsg: int | None = None,
    ):
        if not isinstance(combustion, CombustionParameters):
            raise TypeError("combustion must be CombustionParameters")
        if np.asarray(interval_s).dtype.kind not in "iuf":
            raise ValueError("interval_s must be numeric seconds, not strings or booleans")
        self.interval_s = _physical_scalar(interval_s, "interval_s")
        # Maintained probability checkpoints were fitted on exact one-hour pairs.
        if self.interval_s != 3600.0:
            raise ValueError("the maintained wildfire checkpoint endpoint is exactly 3600 seconds")
        self.predictor = predictor
        self.combustion = combustion
        if residence_time is not None:
            if not isinstance(residence_time, FlameResidenceTime):
                raise TypeError("residence_time must be FlameResidenceTime")
            try:
                same = np.equal(combustion.burning_duration_s, residence_time.duration_s)
            except ValueError as error:
                raise ValueError("combustion and flame residence durations must match") from error
            if not np.all(same):
                raise ValueError("combustion and flame residence durations must match")
        self.residence_time = residence_time
        self.predictor_provenance = dict(predictor_provenance or {})
        self.heat_model = ExpectedHeatFluxModel(
            grid=grid,
            heat_release_rate_density_w_m2=combustion.heat_release_rate_density_w_m2,
            radiative_fraction=radiative_fraction,
            emission_height_m=emission_height_m,
            receiver_height_m=receiver_height_m,
            atmospheric_transmissivity=atmospheric_transmissivity,
            epsg=epsg,
        )

    @property
    def epsg(self) -> int | None:
        """The supplied grid's projected EPSG code, or None for a local grid."""
        return self.heat_model.epsg

    def _coordinate_output(self, result: IntegratedHeatPrediction) -> tuple[FloatArray, FloatArray]:
        if self.epsg is None:
            raise ValueError("geographic heat output requires epsg for the grid; use the corresponding *_details method for a local grid")
        coordinates = geographic_coordinates(
            result.expected_heat_flux_w_m2.shape,
            affine_transform=self.heat_model.grid.transform,
            epsg=self.epsg,
        )
        return result.expected_heat_flux_w_m2, coordinates

    def _sample_geometry(self, sample: dict, *, require_epsg: bool = False):
        transform = _finite_array(_numpy(sample["affine_transform"]), "sample affine_transform")
        if transform.shape != (6,) or not np.allclose(
            transform, self.heat_model.grid.transform, rtol=0, atol=1e-9
        ):
            raise ValueError("sample affine grid differs from the configured radiation grid")
        sample_epsg = sample.get("epsg")
        if sample_epsg is None:
            if require_epsg:
                raise ValueError("sample requires epsg to locate heat predictions on Earth")
            return transform, self.epsg
        epsg = validate_metric_crs(_numpy(sample_epsg))
        if self.epsg is not None and self.epsg != epsg:
            raise ValueError("sample epsg differs from the configured radiation grid epsg")
        return transform, epsg

    def _arrival_burning(self, arrival_time_s, current_time_s, arrival_valid, old_burned):
        """Infer present emission only on known already-burned support.

        Future/unburned arrival entries are deliberately ignored. Missing age
        on an old cell remains unknown; it is never converted to no fire.
        """
        arrival = _single_matrix(arrival_time_s, "arrival_time_s")
        if arrival.dtype.kind not in "iuf" or arrival.shape != old_burned.shape:
            raise ValueError("arrival_time_s must be a real numeric matrix matching the burned-area grid")
        arrival = np.array(arrival, dtype=float, copy=True)
        if np.any(np.isinf(arrival)):
            raise ValueError("arrival_time_s cannot contain infinity")
        time = _numpy(current_time_s)
        if time.dtype.kind not in "iuf" or time.ndim != 0 or not np.isfinite(time):
            raise ValueError("current_time_s must be a finite numeric scalar in seconds")
        known_arrival = np.isfinite(arrival)
        if arrival_valid is not None:
            mask = _mask(arrival_valid, arrival.shape, "arrival_valid")
            if np.any(mask & ~known_arrival):
                raise ValueError("arrival_valid cannot mark a missing arrival valid")
            known_arrival &= mask
        known_old = old_burned & known_arrival
        if np.any(known_old & (arrival > float(time))):
            raise ValueError("known already-burned cells cannot have arrival after current_time_s")
        duration = _heat_map(self.combustion.burning_duration_s, arrival.shape, "burning_duration_s")
        with np.errstate(over="ignore", invalid="ignore"):
            age = float(time) - arrival
        active = known_old & (age < duration)
        remaining = np.zeros(arrival.shape)
        remaining[active] = duration[active] - age[active]
        initial_valid = ~old_burned | known_arrival
        probability = active.astype(float)
        probability[~initial_valid] = np.nan
        remaining[~initial_valid] = np.nan
        return probability, remaining, initial_valid

    @classmethod
    def from_checkpoint(cls, path: str | Path, *, device="cpu", **physical_parameters):
        """Load saved normalization/channel schema and the proper model family.

        Torch and the maintained ``wildfire`` package are
        optional integration dependencies. The radiation-only API remains NumPy.
        No training or preprocessing fit is performed. CPU is the default.
        """
        import torch

        path = resolve_recorded_path(path).resolve()
        saved = torch.load(path, map_location="cpu", weights_only=True)
        architecture = saved.get("contract", {}).get("architecture")
        del saved
        if architecture == "DirectEnvironmentConditionedConvolution":
            raise ValueError(
                "The signed direct-convolution model has been retired. Historical "
                "signed checkpoints cannot be loaded by the active heat API. "
                "Use a supported nonnegative-kernel checkpoint."
            )
        elif architecture in {"EnvironmentConditionedConvolution", "LearnedNonnegativeKernel",
                              "MixedNonnegativeKernel", "NeuralMixedNonnegativeKernel",
                              "BayesianModelAverage"}:
            from .inference import load_trained_model
        else:
            raise ValueError(f"Unsupported wildfire checkpoint architecture: {architecture!r}")
        predictor = load_trained_model(path, device=device)
        provenance = {
            "checkpoint_path": str(path),
            "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "architecture": architecture,
            "best_epoch": int(predictor.best_epoch),
            "device": str(device),
            "channel_names": list(predictor.channel_names),
            "source_channels": list(predictor.source_channels),
            "categorical_classes": predictor.categorical_classes,
            "normalization": "checkpoint's saved training-only statistics",
            "probability_semantics": "new cumulative burning during the next exact hour",
        }
        return cls(predictor, predictor_provenance=provenance, **physical_parameters)

    def predict_sample(self, sample: dict, *, initial_burning_from_arrival: bool = True,
                       **current_burning) -> tuple[FloatArray, FloatArray]:
        """Return interval mean heat and geographic coordinates for one sample.

        The sample supplies ``epsg`` and ``affine_transform``. Spatial padding
        in ``pixel_valid`` has NaN coordinates. Locations are static and remain
        independent of ``time_valid`` or model prediction availability.
        """
        transform, epsg = self._sample_geometry(sample, require_epsg=True)
        shape = _single_matrix(sample["burned_area"], "burned_area").shape
        pixel_valid = None
        if sample.get("pixel_valid") is not None:
            pixel_valid = _mask(sample["pixel_valid"], shape, "pixel_valid")
        if sample.get("time_valid") is not None:
            time_mask = _numpy(sample["time_valid"])
            if time_mask.dtype != np.bool_ or time_mask.size != 1:
                raise ValueError("time_valid must be boolean with one entry for the single heat snapshot")
        coordinates = geographic_coordinates(
            shape, affine_transform=transform, epsg=epsg,
            pixel_valid=pixel_valid,
        )
        result = self.predict_sample_details(
            sample, initial_burning_from_arrival=initial_burning_from_arrival, **current_burning,
        )
        return result.expected_heat_flux_w_m2, coordinates

    def predict_sample_details(self, sample: dict, *, initial_burning_from_arrival: bool = True,
                               **current_burning) -> IntegratedHeatPrediction:
        """Use arrival age and combustion duration for existing burning when available.

        ``arrival_hours`` and singleton ``elapsed_hours`` share the event's
        origin and are converted to seconds. Only known already-burned cells
        use arrival data. New-burn inference never receives arrivals or future
        labels. Explicit present-burning inputs override automatic sample timing.
        Set ``initial_burning_from_arrival=False`` to exclude sample arrivals.
        Reconstructed arrivals produce a retrospective scenario, not observations
        of current flames. Missing arrival age remains unknown on burned support.
        """
        if not isinstance(initial_burning_from_arrival, (bool, np.bool_)):
            raise ValueError("initial_burning_from_arrival must be boolean")
        _, epsg = self._sample_geometry(sample)
        current_burning = dict(current_burning)
        explicit = any(current_burning.get(key) is not None for key in (
            "initial_active_burning_probability", "initial_remaining_burning_duration_s",
            "arrival_time_s", "current_time_s", "arrival_valid",
        ))
        sample_timing = False
        if initial_burning_from_arrival and not explicit:
            arrival = sample.get("arrival_hours")
            elapsed = sample.get("elapsed_hours")
            arrival_mask = sample.get("arrival_valid")
            if arrival is not None or elapsed is not None or arrival_mask is not None:
                if arrival is None or elapsed is None:
                    raise ValueError("sample arrival timing requires both arrival_hours and elapsed_hours")
                elapsed = _numpy(elapsed)
                if elapsed.dtype.kind not in "iuf" or elapsed.size != 1 or not np.all(np.isfinite(elapsed)):
                    raise ValueError("elapsed_hours must contain one finite numeric time for a single snapshot")
                if sample.get("time_valid") is not None:
                    time_valid = _numpy(sample["time_valid"])
                    if time_valid.dtype != np.bool_ or time_valid.size != 1 or not bool(time_valid.item()):
                        raise ValueError("arrival timing requires one unpadded valid snapshot")
                arrival = _single_matrix(arrival, "arrival_hours")
                if arrival.dtype.kind not in "iuf":
                    raise ValueError("arrival_hours must contain real numeric hours")
                with np.errstate(over="ignore", invalid="ignore"):
                    arrival_s = np.asarray(arrival, dtype=float) * 3600.0
                    current_s = float(elapsed.item()) * 3600.0
                current_burning.update(
                    arrival_time_s=arrival_s, current_time_s=current_s,
                    arrival_valid=arrival_mask,
                )
                sample_timing = True
        result = self.predict_details(
            sample["burned_area"], sample["features"],
            channel_names=sample["channel_names"],
            burned_area_valid=sample.get("burned_area_valid"),
            feature_valid=sample.get("feature_valid"),
            **current_burning,
        )
        if epsg is not None:
            result.metadata["epsg"] = epsg
        if sample_timing:
            result.metadata["present_burning_timing_source"] = {
                "source": "sample arrival_hours and elapsed_hours",
                "units_conversion": "hours multiplied by 3600 to seconds",
                "time_origin": sample.get("event_t0_utc", "sample event origin"),
                "event_id": sample.get("event_id"),
                "interpretation": "supplied point-arrival scenario; dataset arrivals are retrospective reconstructions",
                "arrival_uncertainty": "not integrated; nominal arrival estimates are used",
                "future_arrival_policy": "only known already-burned cells use arrival values; new-burn predictions use current inputs",
            }
        timestamp = sample.get("time_utc")
        if timestamp is not None:
            timestamp = _numpy(timestamp)
            if timestamp.dtype.kind not in "iu" or timestamp.size != 1:
                raise ValueError("time_utc must contain one integer Unix timestamp for a single heat snapshot")
            result.metadata["cutoff_unix_s"] = int(timestamp.item())
            result.metadata["endpoint_unix_s"] = int(timestamp.item()) + int(self.interval_s)
        return result

    def predict(
        self,
        burned_area: Any,
        environmental_data: Any,
        *,
        channel_names,
        burned_area_valid=None,
        feature_valid=None,
        initial_active_burning_probability=None,
        initial_remaining_burning_duration_s=None,
        arrival_time_s=None,
        current_time_s=None,
        arrival_valid=None,
        unknown_new_burn_probability=None,
    ) -> tuple[FloatArray, FloatArray]:
        """Return interval mean heat [H,W] and (latitude, longitude) [H,W,2].

        Set the constructor's projected ``epsg`` in metres before using this
        method. Use ``predict_details`` for physical bounds and provenance.
        """
        if self.epsg is None:
            raise ValueError("geographic heat output requires epsg for the grid; use predict_details for a local grid")
        result = self.predict_details(
            burned_area, environmental_data, channel_names=channel_names,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            initial_active_burning_probability=initial_active_burning_probability,
            initial_remaining_burning_duration_s=initial_remaining_burning_duration_s,
            arrival_time_s=arrival_time_s, current_time_s=current_time_s, arrival_valid=arrival_valid,
            unknown_new_burn_probability=unknown_new_burn_probability,
        )
        return self._coordinate_output(result)

    def predict_details(
        self,
        burned_area: Any,
        environmental_data: Any,
        *,
        channel_names,
        burned_area_valid=None,
        feature_valid=None,
        initial_active_burning_probability=None,
        initial_remaining_burning_duration_s=None,
        arrival_time_s=None,
        current_time_s=None,
        arrival_valid=None,
        unknown_new_burn_probability=None,
    ) -> IntegratedHeatPrediction:
        """Run the trained predictor and return interval mean heat and radiant dose.

        An optional ``unknown_new_burn_probability`` is a separately justified
        scalar/map used only for unsupported predictions. Such entries are marked
        as supplied estimates in metadata, never claimed as original predictions.
        Without it, the full expectation remains unknown and bounds are returned.
        Optional ``arrival_time_s`` and ``current_time_s`` infer existing activity
        from age and the same duration used for conditional heat release. Arrival
        times never enter the trained new-burning predictor.
        """
        if self.predictor is None:
            raise ValueError("predictor is absent; use predict_from_new_burn_probability")
        import torch

        burned = _single_matrix(burned_area, "burned_area")
        known = np.isfinite(burned)
        if burned_area_valid is not None:
            known &= _mask(burned_area_valid, burned.shape, "burned_area_valid")
        if np.any(known & (burned != 0) & (burned != 1)):
            raise ValueError("known burned_area must contain binary cumulative states")
        already_burned = known & (burned == 1)
        if initial_active_burning_probability is not None:
            initial = _heat_map(initial_active_burning_probability, burned.shape,
                           "initial_active_burning_probability", upper=1.0)
            if np.any((initial > 0) & ~already_burned):
                raise ValueError("present active fire must be in known already-burned cells")
        # Preserve wrapper channel checks and raw-input normalization. Match its
        # own device/dtype rather than refitting or converting physical features.
        parameter = next(self.predictor.parameters())
        def tensor(value, *, boolean=False):
            array = _numpy(value)
            if boolean and array.dtype.kind != "b":
                raise ValueError("validity masks must contain booleans")
            if not boolean and array.dtype.kind not in "biuf":
                raise ValueError("burned/environment inputs must contain real numeric values")
            return torch.as_tensor(value, device=parameter.device,
                                   dtype=torch.bool if boolean else parameter.dtype)
        with torch.inference_mode():
            prediction = self.predictor(
                tensor(burned_area), tensor(environmental_data),
                channel_names=channel_names,
                burned_area_valid=None if burned_area_valid is None else tensor(burned_area_valid, boolean=True),
                feature_valid=None if feature_valid is None else tensor(feature_valid, boolean=True),
                dt_hours=1.0, boundary="unknown",
            )
        return self.predict_from_new_burn_probability_details(
            _single_matrix(prediction.probability, "prediction probability"),
            probability_valid=_single_matrix(prediction.valid, "prediction validity"),
            already_burned_mask=already_burned,
            initial_active_burning_probability=initial_active_burning_probability,
            initial_remaining_burning_duration_s=initial_remaining_burning_duration_s,
            arrival_time_s=arrival_time_s, current_time_s=current_time_s, arrival_valid=arrival_valid,
            unknown_new_burn_probability=unknown_new_burn_probability,
        )

    def predict_from_new_burn_probability(
        self,
        new_burn_probability: ArrayLike,
        *,
        probability_valid=None,
        already_burned_mask=None,
        initial_active_burning_probability=None,
        initial_remaining_burning_duration_s=None,
        arrival_time_s=None,
        current_time_s=None,
        arrival_valid=None,
        unknown_new_burn_probability=None,
    ) -> tuple[FloatArray, FloatArray]:
        """Return heat [H,W] and geographic coordinates [H,W,2] from probabilities.

        Heat is the interval mean incident radiant flux in W/m². Coordinate
        entries are (latitude, longitude) degrees in EPSG:4326 at cell centers.
        """
        if self.epsg is None:
            raise ValueError("geographic heat output requires epsg for the grid; use predict_from_new_burn_probability_details for a local grid")
        result = self.predict_from_new_burn_probability_details(
            new_burn_probability,
            probability_valid=probability_valid,
            already_burned_mask=already_burned_mask,
            initial_active_burning_probability=initial_active_burning_probability,
            initial_remaining_burning_duration_s=initial_remaining_burning_duration_s,
            arrival_time_s=arrival_time_s, current_time_s=current_time_s, arrival_valid=arrival_valid,
            unknown_new_burn_probability=unknown_new_burn_probability,
        )
        return self._coordinate_output(result)

    def predict_from_new_burn_probability_details(
        self,
        new_burn_probability: ArrayLike,
        *,
        probability_valid=None,
        already_burned_mask=None,
        initial_active_burning_probability=None,
        initial_remaining_burning_duration_s=None,
        arrival_time_s=None,
        current_time_s=None,
        arrival_valid=None,
        unknown_new_burn_probability=None,
    ) -> IntegratedHeatPrediction:
        """Apply the timing/radiation bridge to a saved one-hour probability map.

        These inputs must be probabilities in [0, 1]. A known already-burned mask resolves its
        first-new-burn probability to zero even where model context is unavailable.
        Supply past ``arrival_time_s`` and ``current_time_s`` to include existing
        burning using the configured combustion duration. Missing ages on old
        support produce bounds; arrival data on other cells do not determine new
        burning. Explicit initial activity/time is an alternative to arrival timing.
        """
        if np.ma.isMaskedArray(new_burn_probability) or np.iscomplexobj(new_burn_probability):
            raise ValueError("use an explicit validity mask with a real new-burn probability map")
        raw_q = _single_matrix(new_burn_probability, "new_burn_probability")
        if raw_q.dtype.kind not in "biuf":
            raise ValueError("new_burn_probability must contain real numeric probabilities")
        q = np.array(raw_q, dtype=float, copy=True)
        shape = q.shape
        if np.any(np.isinf(q)):
            raise ValueError("new_burn_probability cannot contain infinity")
        valid = np.isfinite(q) if probability_valid is None else _mask(probability_valid, shape, "probability_valid")
        if np.any(valid & (~np.isfinite(q) | (q < 0) | (q > 1))):
            raise ValueError("valid new-burn probabilities must be finite and in [0,1]")
        if already_burned_mask is not None:
            old_burned = _mask(already_burned_mask, shape, "already_burned_mask")
            q[old_burned] = 0.0
            valid[old_burned] = True
        original_valid = valid.copy()
        supplied = np.zeros(shape, dtype=bool)
        if unknown_new_burn_probability is not None:
            fallback = _heat_map(unknown_new_burn_probability, shape, "unknown_new_burn_probability", upper=1.0)
            supplied = ~valid
            q[supplied] = fallback[supplied]
            valid[supplied] = True
        q[~valid] = np.nan
        duration = _heat_map(self.combustion.burning_duration_s, shape, "burning_duration_s")
        # Zero and one below are uncertainty endpoints, not missing-data fills.
        lower_q = np.where(valid, q, 0.0)
        upper_q = np.where(valid, q, 1.0)
        lower = ignition_to_active_probability(lower_q, duration, self.interval_s)
        upper = ignition_to_active_probability(upper_q, duration, self.interval_s)
        has_arrival = any(value is not None for value in (arrival_time_s, current_time_s, arrival_valid))
        initial_valid = np.ones(shape, dtype=bool)
        active = np.zeros(shape)
        remaining = np.zeros(shape)
        if has_arrival:
            if arrival_time_s is None or current_time_s is None:
                raise ValueError("arrival timing requires both arrival_time_s and current_time_s")
            if initial_active_burning_probability is not None or initial_remaining_burning_duration_s is not None:
                raise ValueError("arrival timing and explicit initial burning inputs cannot be combined")
            if already_burned_mask is None:
                raise ValueError("arrival timing requires an explicit known already_burned_mask")
            active, remaining, initial_valid = self._arrival_burning(
                arrival_time_s, current_time_s, arrival_valid, old_burned,
            )
            present_assumption = "activity inferred from past arrival and supplied duration on known already-burned cells"
            scope = "newly igniting cells plus existing burning under supplied arrival and duration scenario"
        elif initial_active_burning_probability is None:
            if initial_remaining_burning_duration_s is not None:
                raise ValueError("remaining burning duration requires an initial active probability")
            present_assumption = "present-fire contribution excluded because age or explicit activity was not supplied"
            scope = "radiation from newly igniting cells only; present-fire contribution is excluded"
        else:
            if initial_remaining_burning_duration_s is None:
                raise ValueError("initial active fire requires remaining_burning_duration_s")
            active = _heat_map(initial_active_burning_probability, shape,
                          "initial_active_burning_probability", upper=1.0)
            if np.any(active > 0) and already_burned_mask is None:
                raise ValueError("present active fire requires an explicit known already_burned_mask")
            if already_burned_mask is not None and np.any((active > 0) & ~old_burned):
                raise ValueError("present active fire must be in known already-burned cells")
            if np.any((active > 0) & ((upper_q > 0) | ~valid)):
                raise ValueError("initial active and possible first-new-burning sources must be disjoint")
            remaining = _heat_map(initial_remaining_burning_duration_s, shape, "initial_remaining_burning_duration_s")
            present_assumption = "caller-supplied active probabilities and remaining durations"
            scope = "newly igniting cells plus caller-supplied present active-fire contribution"
        # On an old cell with unknown age, remaining duration lies in [0,T].
        # Endpoints below are uncertainty bounds, not replacements for data.
        current_lower = initial_active_occupancy(
            np.where(initial_valid, active, 0.0), np.where(initial_valid, remaining, 0.0), self.interval_s,
        )
        current_upper = initial_active_occupancy(
            np.where(initial_valid, active, 1.0), np.where(initial_valid, remaining, duration), self.interval_s,
        )
        lower_mean = lower.mean_active_probability + current_lower.mean_active_probability
        upper_mean = upper.mean_active_probability + current_upper.mean_active_probability
        lower_end = lower.endpoint_active_probability + current_lower.endpoint_active_probability
        upper_end = upper.endpoint_active_probability + current_upper.endpoint_active_probability
        active_valid = valid & initial_valid
        endpoint_valid = valid & (initial_valid | (duration <= self.interval_s))
        mean_lower_flux = self.heat_model.predict_details(lower_mean).incident_heat_flux_w_m2
        mean_upper_flux = self.heat_model.predict_details(upper_mean).incident_heat_flux_w_m2
        end_lower_flux = self.heat_model.predict_details(lower_end).incident_heat_flux_w_m2
        end_upper_flux = self.heat_model.predict_details(upper_end).incident_heat_flux_w_m2
        emitting = self.heat_model._weighted_sources(np.ones(shape)) > 0
        unresolved_emission = (~active_valid) & emitting & (self.heat_model.atmospheric_transmissivity > 0)
        unresolved_endpoint = (~endpoint_valid) & emitting & (self.heat_model.atmospheric_transmissivity > 0)
        complete = not bool(np.any(unresolved_emission))
        endpoint_complete = not bool(np.any(unresolved_endpoint))
        exact_flux = mean_lower_flux.copy() if complete else np.full(shape, np.nan)
        exact_endpoint = end_lower_flux.copy() if endpoint_complete else np.full(shape, np.nan)
        mean_active = lower_mean.copy()
        endpoint_active = lower_end.copy()
        mean_active[~active_valid] = np.nan
        endpoint_active[~endpoint_valid] = np.nan
        metadata = {
            "affine_transform": list(self.heat_model.grid.transform),
            "epsg": self.epsg,
            "forecast_interval_s": self.interval_s,
            "heat_flux_semantics": "interval-mean incident radiant flux in W/m2",
            "dose_semantics": "integral of interval-mean radiant flux over forecast interval in J/m2",
            "scope": scope,
            "arrival_time_assumption": "conditional on a first-new-burning event, arrival is uniform within the hour",
            "burning_profile_assumption": "constant conditional HRR for the supplied residence duration after arrival",
            "present_burning_assumption": present_assumption,
            "activity_interval": "[arrival_time_s, arrival_time_s + burning_duration_s); inactive at exact extinction",
            "unknown_probability_policy": "full expectation is NaN when emitting-source activity is unresolved; nonnegative-source endpoints yield bounds",
            "unknown_current_age_policy": "remaining duration in [0,T]; mean occupancy upper min(T/D,1); endpoint upper 1 if T>D, otherwise 0",
            "source_cells": int(q.size),
            "original_probability_valid_cells": int(original_valid.sum()),
            "externally_supplied_probability_cells": int(supplied.sum()),
            "unresolved_probability_cells": int((~valid).sum()),
            "unresolved_initial_burning_cells": int((~initial_valid).sum()),
            "known_initial_active_cells": int(np.count_nonzero(initial_valid & (active > 0))),
            "unresolved_emitting_source_cells": int(unresolved_emission.sum()),
            "complete_full_domain_expectation": complete,
            "complete_endpoint_expectation": endpoint_complete,
            "bounds_scope": "fixed supplied combustion, duration, geometry, and finite source domain; existing fire restricted to known already-burned support; excludes existing fire hidden by unknown cumulative state, omitted transport and parameter uncertainty",
            "predictor": self.predictor_provenance,
            "residence_time": (
                self.residence_time.provenance_dict() if self.residence_time is not None
                else {"source": "caller-supplied combustion burning_duration_s"}
            ),
        }
        if has_arrival:
            metadata["present_burning_timing_source"] = {
                "source": "caller-supplied arrival_time_s and current_time_s",
                "current_time_s": float(_numpy(current_time_s)),
                "time_origin": "caller-supplied common numeric origin",
                "arrival_uncertainty": "not integrated; supplied point arrivals are used",
            }
        return IntegratedHeatPrediction(
            new_burn_probability=q, probability_valid=valid, original_probability_valid=original_valid,
            externally_supplied_probability_mask=supplied,
            mean_active_burning_probability=mean_active, endpoint_active_burning_probability=endpoint_active,
            initial_active_burning_probability=active, initial_remaining_burning_duration_s=remaining,
            initial_burning_valid=initial_valid, active_burning_valid=active_valid,
            endpoint_active_burning_valid=endpoint_valid,
            expected_heat_flux_w_m2=exact_flux, known_source_heat_flux_w_m2=mean_lower_flux,
            heat_flux_lower_bound_w_m2=mean_lower_flux, heat_flux_upper_bound_w_m2=mean_upper_flux,
            expected_incident_energy_j_m2=exact_flux * self.interval_s,
            incident_energy_lower_bound_j_m2=mean_lower_flux * self.interval_s,
            incident_energy_upper_bound_j_m2=mean_upper_flux * self.interval_s,
            endpoint_heat_flux_lower_bound_w_m2=end_lower_flux, endpoint_heat_flux_upper_bound_w_m2=end_upper_flux,
            expected_endpoint_heat_flux_w_m2=exact_endpoint,
            complete=complete, endpoint_complete=endpoint_complete, metadata=metadata,
        )
