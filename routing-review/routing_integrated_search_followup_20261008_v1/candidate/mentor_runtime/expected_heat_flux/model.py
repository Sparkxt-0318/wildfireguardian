"""Finite-cell, probabilistic radiation model in SI units.

The NIST point-source irradiance equation is integrated over horizontal source
cells with uniform isotropic radiant power per ground area. Receivers face
upward and lie below a common source elevation. Cell integrals are exact solid
angles, evaluated as two triangles. This is a source-sheet idealization, not a
solid-flame model or a calibrated prediction of total wildfire heat transfer.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


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


def _scalar(value: ArrayLike, name: str) -> float:
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
        power = _scalar(self.expected_total_radiant_power_w, "expected_total_radiant_power_w")
        if power < 0:
            raise ValueError("expected_total_radiant_power_w must be nonnegative")
        object.__setattr__(self, "expected_total_radiant_power_w", power)

    @property
    def incident_heat_flux_kw_m2(self) -> FloatArray:
        return self.incident_heat_flux_w_m2 / 1000.0

    def incident_energy_j_m2(self, duration_s: float) -> FloatArray:
        """Incident radiant dose (J/m²), assuming this flux is constant in time."""
        duration = _scalar(duration_s, "duration_s")
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
        duration = _scalar(duration_s, "duration_s")
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
    ) -> None:
        if not isinstance(grid, AffineGrid):
            raise TypeError("grid must be an AffineGrid")
        self.grid = grid
        self.heat_release_rate_density_w_m2 = _physical_array(
            heat_release_rate_density_w_m2, "heat_release_rate_density_w_m2"
        )
        self.radiative_fraction = _physical_array(radiative_fraction, "radiative_fraction", upper=1.0)
        for name in ("heat_release_rate_density_w_m2", "radiative_fraction"):
            if getattr(self, name).ndim not in (0, 2):
                raise ValueError(f"{name} must be scalar or a two-dimensional source map")
        self.emission_height_m = _scalar(emission_height_m, "emission_height_m")
        self.receiver_height_m = _scalar(receiver_height_m, "receiver_height_m")
        self.height_separation_m = self.emission_height_m - self.receiver_height_m
        if not np.isfinite(self.height_separation_m) or self.height_separation_m <= 0:
            raise ValueError("emission_height_m must be strictly above receiver_height_m")
        self.atmospheric_transmissivity = _scalar(atmospheric_transmissivity, "atmospheric_transmissivity")
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

    def predict(self, active_burning_probability: ArrayLike) -> HeatFluxResult:
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
