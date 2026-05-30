"""Huygens-elliptical cellular automaton wildfire spread simulator.

Combines the Rothermel (1972) point spread model — implemented in
:mod:`wildfireguardian.spread_model.rothermel` — with a Huygens elliptical
wavelet expansion (Finney 1998 style) so that each burning cell propagates
heat to its eight neighbours at a *direction-dependent* rate. The resulting
fire perimeter is an ensemble of overlapping ellipses, the canonical FARSITE
approach.

Architecture
------------

- :class:`FireGrid` owns the state arrays (cell state, accumulated heat,
  burn-start time) and the cell-level metadata (fuel model id, fuel
  moisture, slope, aspect, elevation).
- :class:`WindField` provides a wind speed and direction at any (i, j).
  The default implementation is spatially uniform; a subclass can extend it
  to handle KMA-station-interpolated fields.
- :func:`FireGrid.step` advances the simulation by ``dt`` minutes, dropping
  heat into neighbours' accumulators using the elliptical wavelet kernel,
  igniting any neighbour whose accumulated heat crosses 1.0, and burning out
  any cell whose residence time has elapsed.
- :func:`FireGrid.run` is the high-level loop; it returns a list of
  ``(time_min, perimeter_polygon)`` tuples.
- :class:`MonteCarloEnsemble` repeats :func:`run` with Gaussian-perturbed
  wind / moisture inputs and returns a per-cell burn-probability raster.

Coordinate / convention notes
-----------------------------

- Array convention: ``state[i, j]`` where ``i`` is the row (0 at the top,
  increasing southward) and ``j`` is the column (0 at the left, increasing
  eastward).
- Compass bearings: 0° = North, 90° = East, etc.
- Wind direction is stored as **"blowing toward"** (i.e. the direction the
  fire will preferentially spread). Use :meth:`WindField.from_meteo` to
  convert from the standard meteorological "from" convention.

Citations
---------

- Finney, M.A. (1998). *FARSITE: Fire Area Simulator — model development
  and evaluation.* USDA Forest Service Research Paper RMRS-RP-4. 47 pp.
- Anderson, H.E. (1983). *Predicting wind-driven wild land fire size and
  shape.* USDA Forest Service Research Paper INT-305. 26 pp.
- Sullivan, A.L. (2009). Wildland surface fire spread modelling, 1990–2007.
  *International Journal of Wildland Fire* 18(4), 369–386.

저자 주: 본 CA 시뮬레이터는 Rothermel 점 모델을 커널로 사용하며,
Huygens 타원파 방식 (Finney 1998) 으로 8 방향 이웃 셀에 대한 방향
의존 확산 속도를 계산합니다. 풍속·풍향·연료 수분 섭동에 대한
Monte Carlo 앙상블도 포함되어 있습니다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Iterable

import numpy as np

from ..utils import units as U
from .rothermel import (
    ANDERSON_13,
    FUEL_MODELS,
    KOREAN_PINUS,
    FuelModel,
    MultiClassFuelModel,
    compute_spread_rate,
)

if TYPE_CHECKING:
    from ..utils.regions import RegionConfig


# ---------------------------------------------------------------------------
# Cell state enum
# ---------------------------------------------------------------------------


class CellState(IntEnum):
    """States a single grid cell can be in."""

    UNBURNED = 0
    BURNING = 1
    BURNED = 2


#: 8-connected neighbour offsets, as (di, dj) pairs.
_NEIGHBOURS: tuple[tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    ( 0, -1),          ( 0, 1),
    ( 1, -1), ( 1, 0), ( 1, 1),
)


def _bearing_to_neighbour(di: int, dj: int) -> float:
    """Compass bearing (deg, 0=N) from a cell to its (di, dj) neighbour.

    With ``di`` increasing southward and ``dj`` increasing eastward,
    bearing = atan2(dj, -di) in degrees, normalised to [0, 360).
    """
    return (math.degrees(math.atan2(dj, -di)) + 360.0) % 360.0


# ---------------------------------------------------------------------------
# Wind
# ---------------------------------------------------------------------------


@dataclass
class WindField:
    """Spatially uniform wind. Subclass / replace for spatially varying fields.

    Attributes
    ----------
    speed_ms : float
        Midflame wind speed, m/s. Note this is **midflame**, not 10-m WMO.
    direction_to_deg : float
        Direction the wind is blowing **toward**, compass degrees (0=N, 90=E).
    """

    speed_ms: float
    direction_to_deg: float

    @classmethod
    def from_meteo(cls, speed_ms: float, from_deg: float) -> "WindField":
        """Build from the standard meteorological 'wind FROM' convention.

        E.g. ``from_meteo(15.0, 270.0)`` = "15 m/s from the west", i.e.
        blowing toward the east.
        """
        return cls(speed_ms=speed_ms, direction_to_deg=(from_deg + 180.0) % 360.0)

    def at(self, i: int, j: int) -> tuple[float, float]:
        """Return (speed_ms, direction_to_deg) at cell (i, j)."""
        del i, j
        return self.speed_ms, self.direction_to_deg

    def at_10m(self, i: int, j: int) -> float:
        """Return the 10-m open wind speed at (i, j), m/s.

        The base :class:`WindField` carries midflame wind; crown-fire and
        spotting physics need the 10-m wind, so callers divide back out an
        assumed WAF. A :class:`GriddedWindField` overrides this with a real
        per-cell 10-m field.
        """
        return self.speed_ms / max(_DEFAULT_WAF_FOR_10M, 1e-6)


#: Fallback WAF used only to back out a 10-m wind from a uniform midflame
#: :class:`WindField` when no explicit 10-m field is supplied. Closed Korean
#: pine canopy value (Andrews 2012; see spread_model/wind.py).
_DEFAULT_WAF_FOR_10M: float = 0.10


@dataclass
class GriddedWindField(WindField):
    """Spatially-varying wind: per-cell midflame field + per-cell 10-m field.

    ``speed_field`` / ``direction_to_field`` are the **midflame** wind the
    surface Rothermel kernel consumes (``.at``). ``u10m_field`` is the
    **10-m** open wind that crown-fire and spotting physics consume
    (``.at_10m``). Build with :meth:`from_topographic`.
    """

    speed_field: np.ndarray = field(default=None, repr=False)        # type: ignore[assignment]
    direction_to_field: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    u10m_field: np.ndarray | None = field(default=None, repr=False)

    def at(self, i: int, j: int) -> tuple[float, float]:
        return float(self.speed_field[i, j]), float(self.direction_to_field[i, j])

    def at_10m(self, i: int, j: int) -> float:
        if self.u10m_field is not None:
            return float(self.u10m_field[i, j])
        return float(self.speed_field[i, j]) / max(_DEFAULT_WAF_FOR_10M, 1e-6)

    @classmethod
    def from_topographic(
        cls,
        u10m_field: np.ndarray,
        direction_to_field: np.ndarray,
        waf: float,
    ) -> "GriddedWindField":
        """Build from a 10-m field + WAF; midflame field = waf · u10m_field."""
        mid = (np.asarray(u10m_field, dtype=np.float32) * waf).astype(np.float32)
        return cls(
            speed_ms=float(np.mean(mid)),
            direction_to_deg=float(np.mean(direction_to_field)),
            speed_field=mid,
            direction_to_field=np.asarray(direction_to_field, dtype=np.float32),
            u10m_field=np.asarray(u10m_field, dtype=np.float32),
        )


# ---------------------------------------------------------------------------
# Anderson 1983 length-to-breadth ratio
# ---------------------------------------------------------------------------


#: FARSITE-style cap on the Anderson 1983 length-to-breadth ratio.
#: The raw correlation grows exponentially with wind and becomes unphysical
#: above ~5 mph. Operational fire models (FARSITE, BehavePlus) clamp LB at
#: a value in the 6–10 range; Alexander (1985) recommends ~3–4 for
#: temperate surface fires. We use 3.0 — clear wind asymmetry while
#: keeping lateral spread resolvable on a cellular grid (flank ≈ 6 % of
#: head, vs ≈ 0.8 % at LB = 8).
LB_MAX: float = 3.0


def length_to_breadth_ratio(midflame_wind_ms: float) -> float:
    """Anderson (1983) wind-driven length-to-breadth ratio of a fire ellipse.

    .. math::
       LB = 0.936 \\, e^{0.2566 U} + 0.461 \\, e^{-0.1548 U} - 0.397

    where U is the midflame wind in **mph**. LB ≥ 1, with LB = 1 at U = 0
    (circular spread). Capped at :data:`LB_MAX` because the raw correlation
    diverges for higher winds.

    Reference: Anderson 1983 eq. (1); Finney 1998 §2.2.2.
    """
    if midflame_wind_ms <= 0.0:
        return 1.0
    U_mph = midflame_wind_ms * U.MPH_PER_MS
    lb = (0.936 * math.exp(0.2566 * U_mph)
          + 0.461 * math.exp(-0.1548 * U_mph)
          - 0.397)
    return float(np.clip(lb, 1.0, LB_MAX))


def eccentricity_from_lb(lb: float) -> float:
    """Eccentricity of an ellipse given its length-to-breadth ratio a/b."""
    if lb <= 1.0:
        return 0.0
    return math.sqrt(1.0 - 1.0 / (lb * lb))


def directional_spread_rate(
    R_max: float, eccentricity: float, angle_from_wind_deg: float,
) -> float:
    """Direction-dependent rate of spread (Finney 1998 §2.2.3).

    Polar form of an ellipse with the burning cell at one focus and the
    head fire (downwind) along the major axis. ``R_max`` is the head-fire
    rate of spread (the Rothermel R with current wind / slope), and the
    formula reduces to the back-fire rate for ``angle = 180°``.

    .. math::
       R(\\theta) = R_{max} \\frac{1 - e}{1 - e \\cos\\theta}

    where θ is the angle between the neighbour direction and the
    wind / spread direction (rad).
    """
    if eccentricity <= 0.0:
        return R_max
    theta = math.radians(angle_from_wind_deg)
    return R_max * (1.0 - eccentricity) / (1.0 - eccentricity * math.cos(theta))


# ---------------------------------------------------------------------------
# FireGrid
# ---------------------------------------------------------------------------


@dataclass
class FireGrid:
    """A 2-D wildfire spread simulator.

    The grid is built around fixed-size square cells. Each cell holds a
    state in :class:`CellState`, an accumulated-heat scalar, and the
    metadata (fuel model id, fuel moisture, slope, aspect, elevation)
    needed to compute its own Rothermel spread rate.

    Parameters
    ----------
    nrows, ncols : int
        Grid shape.
    cell_size_m : float, default 30.0
        Side length of one cell, in metres.
    residence_time_min : float, default 30.0
        How long a cell stays in the BURNING state before transitioning to
        BURNED. Surface fires typically burn out in 20–60 minutes; 30 min
        is a reasonable default for the Rothermel surface-fire regime.
    ignition_threshold : float, default 1.0
        Accumulated dimensionless heat at which an UNBURNED neighbour
        transitions to BURNING. ``R · dt / d`` accumulates such that under
        steady R the time to ignite at distance d is d / R; threshold of 1
        recovers exactly that geometry.
    """

    nrows: int
    ncols: int
    cell_size_m: float = 30.0
    residence_time_min: float = 30.0
    ignition_threshold: float = 1.0

    # ----- mutable state arrays initialised in __post_init__ -----
    state: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    heat: np.ndarray = field(default=None, repr=False)   # type: ignore[assignment]
    burn_start_time_min: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]

    # ----- metadata layers -----
    fuel_model_id: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    fuel_moisture: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    slope_degrees: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    aspect_degrees: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    elevation_m: np.ndarray = field(default=None, repr=False)    # type: ignore[assignment]

    # ----- geographic anchor (Session 2: CRS-aware FireGrid) -----
    # If `region` is set, the grid is georeferenced. If None (Session 1
    # default), the grid is a local Cartesian frame with origin at SW
    # corner; export methods will refuse to attach CRS metadata.
    region: "RegionConfig | None" = None

    # ----- Session 6 fire-type physics (default OFF: surface-only) -----
    enable_crown_fire: bool = False
    enable_spotting: bool = False
    spotting_seed: int = 0
    spot_probability_per_min: float = 0.02   # per active-crown cell per minute
    #: Per-cell regime: 0=SURFACE, 1=PASSIVE_CROWN, 2=ACTIVE_CROWN.
    regime: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    n_spot_ignitions: int = 0
    #: Session 7: tree-crown foliar moisture (%) for the Van Wagner check.
    #: ``None`` reproduces the Session-6 behaviour (reuse the surface live-fuel
    #: moisture ``m_f``, which conflates two physically distinct quantities);
    #: a value DECOUPLES the crown foliar moisture from the surface LFMC.
    crown_foliar_moisture_pct: float | None = None
    #: Diagnostic: if a list, transition records are appended (Session 7).
    _crown_log: "list | None" = field(default=None, repr=False)

    def _crown_foliar_moisture_pct(self, m_f: float) -> float:
        """Foliar moisture (%) for the crown check: decoupled value or LFMC."""
        if self.crown_foliar_moisture_pct is not None:
            return self.crown_foliar_moisture_pct
        return m_f * 100.0

    # Internal: cached R_max per burning cell, per step.
    _R_cache: dict[tuple[int, int], tuple[float, float, float]] = field(
        default_factory=dict, repr=False,
    )
    _spot_rng: "np.random.Generator | None" = field(default=None, repr=False)

    def __post_init__(self) -> None:
        shape = (self.nrows, self.ncols)
        if self.regime is None:
            self.regime = np.zeros(shape, dtype=np.uint8)
        if self.state is None:
            self.state = np.zeros(shape, dtype=np.uint8)
        if self.heat is None:
            self.heat = np.zeros(shape, dtype=np.float32)
        if self.burn_start_time_min is None:
            # NaN until ignited.
            self.burn_start_time_min = np.full(shape, np.nan, dtype=np.float32)
        if self.fuel_model_id is None:
            self.fuel_model_id = np.full(shape, "FM10", dtype=object)
        if self.fuel_moisture is None:
            self.fuel_moisture = np.full(shape, 0.08, dtype=np.float32)
        if self.slope_degrees is None:
            self.slope_degrees = np.zeros(shape, dtype=np.float32)
        if self.aspect_degrees is None:
            self.aspect_degrees = np.zeros(shape, dtype=np.float32)
        if self.elevation_m is None:
            self.elevation_m = np.zeros(shape, dtype=np.float32)

    # ------------------------------------------------------------------
    # Geographic factories (Session 2 — CRS-aware FireGrid)
    # ------------------------------------------------------------------

    @classmethod
    def from_region(
        cls,
        region: "RegionConfig",
        cell_size_m: float = 30.0,
        residence_time_min: float = 30.0,
        ignition_threshold: float = 1.0,
    ) -> "FireGrid":
        """Construct a FireGrid sized to a :class:`RegionConfig`'s EPSG:5179 bbox.

        The grid is georeferenced: ``self.region`` is set, and
        :meth:`perimeter_geodataframe`, :meth:`to_geotiff`, and
        :meth:`to_wgs84` will emit CRS metadata.
        """
        nrows, ncols = region.grid_dims(cell_size_m)
        grid = cls(
            nrows=nrows, ncols=ncols, cell_size_m=cell_size_m,
            residence_time_min=residence_time_min,
            ignition_threshold=ignition_threshold,
            region=region,
        )
        return grid

    @property
    def is_georeferenced(self) -> bool:
        return self.region is not None and not self.region.is_synthetic

    @property
    def crs(self) -> str | None:
        """The EPSG code attached to the grid, or None if non-geographic."""
        from ..utils.regions import KOREA_2000_UNIFIED
        return KOREA_2000_UNIFIED if self.is_georeferenced else None

    @property
    def affine(self) -> tuple[float, float, float, float, float, float] | None:
        """Rasterio-style affine transform (a, b, c, d, e, f), or None."""
        if not self.is_georeferenced:
            return None
        assert self.region is not None
        return self.region.affine_transform(self.cell_size_m)

    def cell_to_epsg5179(self, i: int, j: int) -> tuple[float, float]:
        """Map grid cell centre (i, j) → EPSG:5179 (x, y) in metres.

        Raises if the grid is not georeferenced.
        """
        if not self.is_georeferenced:
            raise RuntimeError(
                "FireGrid has no geographic CRS attached; "
                "construct via FireGrid.from_region(...) first"
            )
        a, _b, c, _d, e, f = self.affine  # type: ignore[misc]
        # Cell centre: add 0.5 to the index.
        x = c + a * (j + 0.5)
        y = f + e * (i + 0.5)
        return x, y

    # ------------------------------------------------------------------
    # Ignition initialisation
    # ------------------------------------------------------------------

    def ignite_point(self, i: int, j: int, time_min: float = 0.0) -> None:
        """Ignite a single cell."""
        self._ignite(i, j, time_min)

    def ignite_polygon(
        self,
        cells: Iterable[tuple[int, int]],
        time_min: float = 0.0,
    ) -> None:
        """Ignite a set of cells representing an ignition polygon."""
        for i, j in cells:
            self._ignite(i, j, time_min)

    def ignite_disc(
        self, i: int, j: int, radius_m: float, time_min: float = 0.0,
    ) -> int:
        """Ignite all cells within ``radius_m`` of cell (i, j).

        Returns the number of cells ignited. Used to initialise the fire
        from a finite established perimeter rather than a single cell —
        see ``docs/methodology/spread_warmup.md`` for why this is the
        physically-correct initialisation for a spread model (a point has
        zero perimeter and therefore zero spread "supply"; real fires are
        modelled from an established front, as in FARSITE).

        ``radius_m`` is interpreted in grid-distance metres. A radius below
        half a cell still ignites the centre cell.
        """
        r_cells = radius_m / self.cell_size_m
        r_ceil = int(math.ceil(r_cells))
        n = 0
        for di in range(-r_ceil, r_ceil + 1):
            for dj in range(-r_ceil, r_ceil + 1):
                if math.hypot(di, dj) > r_cells:
                    continue
                ni, nj = i + di, j + dj
                if 0 <= ni < self.nrows and 0 <= nj < self.ncols:
                    self._ignite(ni, nj, time_min)
                    n += 1
        if n == 0:
            # radius too small to capture any cell; at least light the centre.
            self._ignite(i, j, time_min)
            n = 1
        return n

    def _ignite(self, i: int, j: int, time_min: float) -> None:
        if not (0 <= i < self.nrows and 0 <= j < self.ncols):
            raise IndexError(f"ignition cell ({i},{j}) is outside the grid")
        self.state[i, j] = CellState.BURNING
        self.burn_start_time_min[i, j] = time_min

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self, dt_min: float, wind: WindField, current_time_min: float) -> int:
        """Advance the simulation by ``dt_min`` minutes.

        Returns
        -------
        int
            Number of cells newly ignited this step.
        """
        if dt_min <= 0.0:
            raise ValueError("dt_min must be > 0")

        # Snapshot the indices of currently burning cells so newly ignited
        # cells in this step don't immediately spread within the same step.
        burning = np.argwhere(self.state == CellState.BURNING)

        for i, j in burning:
            self._spread_from(int(i), int(j), dt_min, wind)

        # Promote unburned cells whose heat crossed threshold.
        new_ig_mask = (
            (self.state == CellState.UNBURNED)
            & (self.heat >= self.ignition_threshold)
        )
        new_count = int(new_ig_mask.sum())
        if new_count > 0:
            self.state[new_ig_mask] = CellState.BURNING
            self.burn_start_time_min[new_ig_mask] = current_time_min + dt_min

        # Burnout: BURNING → BURNED after residence time elapsed.
        elapsed = current_time_min + dt_min - self.burn_start_time_min
        burnout_mask = (
            (self.state == CellState.BURNING)
            & (elapsed >= self.residence_time_min)
        )
        if burnout_mask.any():
            self.state[burnout_mask] = CellState.BURNED

        # ----- Session 6: spotting (stochastic ember jumps) -----
        if self.enable_spotting:
            self._spot_step(dt_min, wind, current_time_min)

        return new_count

    def _spot_step(self, dt_min: float, wind: WindField, current_time_min: float) -> None:
        """Launch igniting embers from active-crown cells (Albini spotting)."""
        from .crown_fire import CrownRegime, byram_intensity
        from .spotting import (
            flame_length_m,
            landing_cell,
            max_spot_distance,
            sample_spot_landing,
        )

        if self._spot_rng is None:
            self._spot_rng = np.random.default_rng(self.spotting_seed)
        rng = self._spot_rng
        p = self.spot_probability_per_min * dt_min

        active = np.argwhere(
            (self.state == CellState.BURNING)
            & (self.regime == int(CrownRegime.ACTIVE_CROWN))
        )
        for i, j in active:
            if rng.random() >= p:
                continue
            i, j = int(i), int(j)
            cached = self._R_cache.get((i, j))
            if cached is None:
                continue
            R_eff, _ecc, wind_to_deg = cached
            fm_id = self.fuel_model_id[i, j]
            fm = FUEL_MODELS[fm_id] if isinstance(fm_id, str) else fm_id
            fine = getattr(fm, "fine_fuel_load_kg_m2", 0.5)
            i_b = byram_intensity(R_eff, fine)
            fl = flame_length_m(i_b)
            u10 = wind.at_10m(i, j)
            d_max = max_spot_distance(fl, u10)
            if d_max <= self.cell_size_m:
                continue
            d, bearing = sample_spot_landing(rng, d_max, wind_to_deg)
            ni, nj = landing_cell(i, j, d, bearing, self.cell_size_m)
            if (0 <= ni < self.nrows and 0 <= nj < self.ncols
                    and self.state[ni, nj] == CellState.UNBURNED):
                self.state[ni, nj] = CellState.BURNING
                self.burn_start_time_min[ni, nj] = current_time_min + dt_min
                self.n_spot_ignitions += 1

    def _spread_from(self, i: int, j: int, dt_min: float, wind: WindField) -> None:
        """Deposit heat into the 8 neighbours of burning cell (i, j)."""
        # ----- local environment -----
        fm_id = self.fuel_model_id[i, j]
        if isinstance(fm_id, str):
            # String code: resolve via the legacy single-class registry
            # (multi-class lookups by string must use ANDERSON_13 explicitly).
            fm = FUEL_MODELS[fm_id]
        else:
            # Either FuelModel or MultiClassFuelModel instance; compute_spread_rate
            # dispatches on type.
            fm = fm_id
        m_f = float(self.fuel_moisture[i, j])
        slope_deg = float(self.slope_degrees[i, j])
        wind_speed_ms, wind_dir_to_deg = wind.at(i, j)

        # ----- head-fire rate via Rothermel; cache per-cell -----
        key = (i, j)
        cached = self._R_cache.get(key)
        if cached is None:
            if isinstance(fm, MultiClassFuelModel):
                # Treat the cell-level fuel_moisture as LFMC (live moisture);
                # use a typical Korean spring dead 1-h moisture of 10 % unless
                # the user has overridden it via a separate metadata field.
                R = compute_spread_rate(
                    fm, dead_moisture=0.10, live_moisture=m_f,
                    wind_speed_ms=wind_speed_ms, slope_degrees=slope_deg,
                )
            else:
                R = compute_spread_rate(
                    fm, fuel_moisture=m_f,
                    wind_speed_ms=wind_speed_ms, slope_degrees=slope_deg,
                )
            R_max = R.rate_m_min
            R_surf = R_max            # surface rate before any crown override
            lb_wind = wind_speed_ms   # midflame drives surface elongation

            # ----- Session 6: crown-fire regime switch -----
            if (self.enable_crown_fire
                    and isinstance(fm, MultiClassFuelModel) and fm.can_crown):
                from .crown_fire import CrownRegime, classify_crown_regime
                u10 = wind.at_10m(i, j)
                regime, R_eff = classify_crown_regime(
                    r_surface_m_min=R_max,
                    fine_load_kg_m2=fm.fine_fuel_load_kg_m2,
                    u_10m_ms=u10,
                    canopy_base_height_m=fm.canopy_base_height_m,
                    canopy_bulk_density_kg_m3=fm.canopy_bulk_density_kg_m3,
                    foliar_moisture_pct=self._crown_foliar_moisture_pct(m_f),
                )
                self.regime[i, j] = int(regime)
                if regime == CrownRegime.ACTIVE_CROWN:
                    R_max = R_eff
                    lb_wind = u10   # crown runs are 10-m-wind-driven, more elongated

                # ----- Session 7 diagnostic hook -----
                if self._crown_log is not None:
                    from .crown_fire import (
                        byram_intensity,
                        critical_surface_intensity,
                    )
                    fmc = self._crown_foliar_moisture_pct(m_f)
                    self._crown_log.append({
                        "R_surf": R_surf, "midflame_ms": wind_speed_ms,
                        "u10_ms": u10,
                        "I_B": byram_intensity(R_surf, fm.fine_fuel_load_kg_m2),
                        "I_o": critical_surface_intensity(
                            fm.canopy_base_height_m, fmc),
                        "cbh_m": fm.canopy_base_height_m,
                        "fine_load": fm.fine_fuel_load_kg_m2,
                        "slope_deg": slope_deg, "fmc_pct": fmc,
                        "regime": int(regime),
                    })

            lb = length_to_breadth_ratio(lb_wind)
            ecc = eccentricity_from_lb(lb)
            self._R_cache[key] = (R_max, ecc, wind_dir_to_deg)
        else:
            R_max, ecc, wind_dir_to_deg = cached

        if R_max <= 0.0:
            return  # no spread

        # ----- deposit heat into neighbours -----
        for di, dj in _NEIGHBOURS:
            ni, nj = i + di, j + dj
            if not (0 <= ni < self.nrows and 0 <= nj < self.ncols):
                continue
            if self.state[ni, nj] != CellState.UNBURNED:
                continue

            bearing = _bearing_to_neighbour(di, dj)
            # angle between neighbour direction and wind-to direction
            angle_diff = ((bearing - wind_dir_to_deg + 540.0) % 360.0) - 180.0
            R_theta = directional_spread_rate(R_max, ecc, angle_diff)
            d_m = self.cell_size_m * math.hypot(di, dj)
            self.heat[ni, nj] += float(R_theta * dt_min / d_m)

    # ------------------------------------------------------------------
    # High-level run
    # ------------------------------------------------------------------

    def run(
        self,
        duration_minutes: float,
        dt_minutes: float,
        wind: WindField,
        snapshot_every_min: float | None = None,
        return_perimeters: bool = True,
    ) -> list[tuple[float, "Polygon | None"]]:
        """Run the simulation and return (time, perimeter) snapshots.

        Parameters
        ----------
        duration_minutes : float
            Total time to simulate.
        dt_minutes : float
            Step size. Must divide ``duration_minutes`` cleanly enough that
            the simulation reaches end of horizon.
        wind : WindField
            Wind field. Currently expected to be spatially uniform; the
            framework supports spatially varying fields by subclassing.
        snapshot_every_min : float | None
            How often to snapshot the perimeter. Default = ``dt_minutes``.
        return_perimeters : bool
            If True, compute the union polygon at each snapshot. Disable for
            speed when only the final raster matters.

        Returns
        -------
        list of (time_min, perimeter_polygon_or_None)
        """
        if snapshot_every_min is None:
            snapshot_every_min = dt_minutes
        snapshots: list[tuple[float, object]] = []
        t = 0.0
        next_snapshot = 0.0
        while t < duration_minutes - 1e-9:
            if t >= next_snapshot - 1e-9:
                snapshots.append(
                    (t, self.perimeter() if return_perimeters else None)
                )
                next_snapshot += snapshot_every_min
            self.step(dt_minutes, wind, current_time_min=t)
            t += dt_minutes
        # Final snapshot
        snapshots.append(
            (t, self.perimeter() if return_perimeters else None)
        )
        return snapshots

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def burned_area_m2(self) -> float:
        """Total burning + burned area, in m²."""
        mask = self.state >= CellState.BURNING
        return float(mask.sum()) * (self.cell_size_m ** 2)

    def burned_mask(self) -> np.ndarray:
        """Boolean array True where state ∈ {BURNING, BURNED}."""
        return self.state >= CellState.BURNING

    def perimeter(self):
        """Return a shapely (Multi)Polygon of all burning + burned cells.

        Returns ``None`` if no cell has been touched yet.

        Coordinates are in the grid's projected frame:

        - If :attr:`is_georeferenced`, coordinates are in EPSG:5179 metres.
        - Otherwise (Session 1 / synthetic grids), coordinates are in
          metres with the SW corner of the grid as the origin (x east,
          y north).
        """
        from shapely.geometry import box
        from shapely.ops import unary_union

        mask = self.burned_mask()
        if not mask.any():
            return None
        ii, jj = np.where(mask)
        cs = self.cell_size_m

        if self.is_georeferenced:
            assert self.region is not None
            minx, _miny, _maxx, maxy = self.region.bbox_epsg5179
            # i goes south (top → bottom), so y = maxy - (i+1)*cs is the
            # SW corner y of the cell.
            x_sw = minx + jj * cs
            y_sw = maxy - (ii + 1) * cs
            polys = [box(x, y, x + cs, y + cs) for x, y in zip(x_sw, y_sw)]
        else:
            # Local Cartesian with SW corner at origin (Session 1 behaviour).
            y0 = (self.nrows - 1 - ii) * cs
            x0 = jj * cs
            polys = [box(x, y, x + cs, y + cs) for x, y in zip(x0, y0)]
        return unary_union(polys)

    # ------------------------------------------------------------------
    # Geographic export (Session 2)
    # ------------------------------------------------------------------

    def perimeter_geodataframe(self):
        """Return the perimeter as a :class:`geopandas.GeoDataFrame` with CRS.

        Returns ``None`` if no cells have been touched.
        """
        if not self.is_georeferenced:
            raise RuntimeError(
                "FireGrid is not georeferenced; use .perimeter() for a "
                "non-georeferenced shapely polygon, or construct the grid "
                "via FireGrid.from_region(...)"
            )
        import geopandas as gpd
        peri = self.perimeter()
        if peri is None:
            return None
        return gpd.GeoDataFrame(
            {
                "n_cells": [int(self.burned_mask().sum())],
                "area_m2": [self.burned_area_m2()],
            },
            geometry=[peri],
            crs=self.crs,
        )

    def to_wgs84_perimeter(self):
        """Return the perimeter polygon reprojected to EPSG:4326 (WGS84)."""
        if not self.is_georeferenced:
            raise RuntimeError("grid has no CRS")
        gdf = self.perimeter_geodataframe()
        if gdf is None:
            return None
        return gdf.to_crs("EPSG:4326")

    def to_geotiff(self, path) -> None:
        """Write the cell-state raster to a GeoTIFF in EPSG:5179.

        Values: 0 = UNBURNED, 1 = BURNING, 2 = BURNED.
        """
        if not self.is_georeferenced:
            raise RuntimeError("grid has no CRS")
        import rasterio
        from rasterio.transform import Affine
        a, b, c, d, e, f = self.affine  # type: ignore[misc]
        transform = Affine(a, b, c, d, e, f)
        with rasterio.open(
            path, "w",
            driver="GTiff",
            height=self.nrows, width=self.ncols,
            count=1, dtype="uint8",
            crs=self.crs, transform=transform,
            compress="lzw", nodata=255,
        ) as dst:
            dst.write(self.state.astype(np.uint8), 1)
            dst.set_band_description(1, "fire_state: 0=unburned, 1=burning, 2=burned")


# ---------------------------------------------------------------------------
# Monte Carlo ensemble
# ---------------------------------------------------------------------------


@dataclass
class EnsembleConfig:
    """Perturbation parameters for the Monte Carlo ensemble."""

    n_members: int = 20
    wind_speed_sigma_ms: float = 2.0
    wind_dir_sigma_deg: float = 15.0
    fuel_moisture_sigma: float = 0.05  # fraction, e.g. 0.05 = 5 %
    random_seed: int | None = 0


class MonteCarloEnsemble:
    """Run a :class:`FireGrid` configuration N times with perturbed inputs.

    The base ``grid_factory`` callable is expected to return a *fresh*
    :class:`FireGrid` (with metadata and ignition pre-applied) on each call.
    A ``wind_factory`` callable returns a :class:`WindField`. Both factories
    accept a numpy ``Generator`` so they can introduce member-specific
    perturbations consistently.

    Output: per-cell burn probability after the requested duration.

    Notes
    -----
    The ensemble is **embarrassingly parallel** but the current implementation
    is serial. Vectorising or multiprocessing it is a documented future
    improvement.
    """

    def __init__(self, config: EnsembleConfig | None = None) -> None:
        self.config = config or EnsembleConfig()

    def run(
        self,
        grid_factory,
        wind_factory,
        duration_minutes: float,
        dt_minutes: float,
    ) -> np.ndarray:
        """Run N members and return per-cell burn probability ∈ [0, 1]."""
        rng = np.random.default_rng(self.config.random_seed)
        burn_count: np.ndarray | None = None

        for member in range(self.config.n_members):
            member_rng = np.random.default_rng(
                rng.integers(0, 2**32 - 1, dtype=np.uint32)
            )
            grid = grid_factory(member_rng)
            wind = wind_factory(member_rng)

            # Inject perturbations into the fuel-moisture layer.
            dm = member_rng.normal(0.0, self.config.fuel_moisture_sigma,
                                   size=grid.fuel_moisture.shape)
            grid.fuel_moisture = np.clip(
                grid.fuel_moisture + dm, 0.01, 5.00,
            ).astype(np.float32)

            grid.run(
                duration_minutes=duration_minutes,
                dt_minutes=dt_minutes,
                wind=wind,
                return_perimeters=False,
            )
            mask = grid.burned_mask().astype(np.uint16)
            if burn_count is None:
                burn_count = mask.copy()
            else:
                burn_count += mask

        if burn_count is None:  # n_members == 0
            raise ValueError("ensemble had zero members")
        return burn_count.astype(np.float32) / float(self.config.n_members)


def perturb_wind(
    base_wind: WindField,
    rng: np.random.Generator,
    speed_sigma_ms: float = 2.0,
    dir_sigma_deg: float = 15.0,
) -> WindField:
    """Convenience: return a copy of ``base_wind`` with Gaussian perturbations.

    ``speed`` is clipped to ≥ 0.
    """
    return WindField(
        speed_ms=max(0.0, base_wind.speed_ms + rng.normal(0.0, speed_sigma_ms)),
        direction_to_deg=(base_wind.direction_to_deg + rng.normal(0.0, dir_sigma_deg)) % 360.0,
    )


__all__ = [
    "CellState",
    "WindField",
    "GriddedWindField",
    "FireGrid",
    "EnsembleConfig",
    "MonteCarloEnsemble",
    "length_to_breadth_ratio",
    "eccentricity_from_lb",
    "directional_spread_rate",
    "perturb_wind",
]
