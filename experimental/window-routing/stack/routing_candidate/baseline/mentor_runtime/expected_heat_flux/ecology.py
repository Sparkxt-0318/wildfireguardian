"""Load ecological fuel maps without turning unknown fuel into zero fuel.

LANDFIRE FCCS loadings describe reference fuelbeds, not event-date field
measurements. A partially covered target cell contains a mean over its mapped
portion. Such a mean is retained, but is not a whole-cell combustion input until
the caller supplies a loading for the unmapped portion.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .model import AffineGrid, CombustionParameters

# U.S. short ton (2000 lb), international pound, international acre.
FCCS_TONS_PER_ACRE_TO_KG_M2 = 2000.0 * 0.45359237 / (43560.0 * 0.3048**2)


def _map(value: ArrayLike, name: str) -> NDArray[np.float64]:
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
        loading = _map(self.fuel_load_kg_m2, "fuel_load_kg_m2")
        coverage = _map(self.coverage_fraction, "coverage_fraction")
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
            loading = _map(source.read(1, masked=True), "fuel loading raster")
            coverage = _map(fraction.read(1, masked=True), "coverage raster")
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
