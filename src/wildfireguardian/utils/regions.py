"""Geographic region configurations.

This module is the **single source of truth** for any geographic bounding
box, projected raster footprint, or named region that the rest of the
codebase consumes. No other file in this codebase should hardcode a
coordinate; instead, accept a :class:`RegionConfig` parameter and look up
the values here.

The module-level constants at the bottom (``YEONGDEOK_2025``, ``ULJIN_SAMCHEOK_2022``,
etc.) are the project's canonical region presets. They cover three tiers:

- **Tier 1 (East Coast Pine Belt)**: deployment-target region and primary
  validation cases. The three named historical wildfire events here are
  the validation backbone for the Korea Code Fair submission.
- **Tier 2 (Round 2+ research extension)**: the Central Mountain Belt and
  the Southwestern Coast. Defined as presets so the code is general, but
  NOT validated against in Session 2.
- **Architectural national scope**: ``KOREA_PENINSULA`` is the upper bound
  of what the data ingestion layer should be able to ingest. It is not a
  validation target.

Bounding boxes are stored in both WGS84 (lon/lat, EPSG:4326) and the
Korean operational CRS EPSG:5179 (Korea 2000 / Unified TM). Conversion
between the two is computed at construction time via pyproj and cached
on the dataclass.

Vulnerability tier scheme — see :mod:`wildfireguardian.utils.vulnerability`
for the actual scoring framework. Tier-1 regions are explicit deployment
targets; Tier-2 are research extensions; Tier-3 covers urban areas where
this system is NOT the right intervention.

References for bounding boxes
-----------------------------

- The Yeongdeok, Uljin/Samcheok, and Goseong event bounds are based on
  public news coverage of the burn perimeters. Exact KFS perimeter
  shapefiles are still pending (see ``docs/BLOCKERS.md``). The bboxes
  here are intentionally generous so a 20–50 % expansion of the perimeter
  still fits inside.
- The East Coast Pine Belt outline approximately covers Gangwon-do east
  coast + Gyeongsangbuk-do east coast, ≈ Goseong-gun in the north to
  Pohang-si in the south, ≈ 20 km inland.
- Korea Peninsula bbox ``[124.0, 33.0, 132.0, 39.0]`` covers all of South
  Korea plus Jeju with a margin.

If exact authoritative bbox values become available from KOSTAT
administrative shapefiles, this module should be the only thing that needs
updating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Final, Literal

from pyproj import Transformer


# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------

WGS84: Final[str] = "EPSG:4326"
KOREA_2000_UNIFIED: Final[str] = "EPSG:5179"

# pyproj transformers — module-level cache, always-xy.
_to_5179 = Transformer.from_crs(WGS84, KOREA_2000_UNIFIED, always_xy=True)
_to_4326 = Transformer.from_crs(KOREA_2000_UNIFIED, WGS84, always_xy=True)


# ---------------------------------------------------------------------------
# Vulnerability tier
# ---------------------------------------------------------------------------

VulnerabilityTier = Literal[1, 2, 3]

# Tier 1 — deployment-target population: rural elderly + fire-prone + sparse
#          evacuation infrastructure. Primary validation cases live here.
# Tier 2 — research extension: still rural, still fire-prone, but with
#          different fuel/climate/topography (mixed forest, humid).
# Tier 3 — urban or system-irrelevant. Defined for completeness only.


# ---------------------------------------------------------------------------
# RegionConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionConfig:
    """One named geographic region used by the system.

    Construct via the convenience factory :meth:`from_wgs84_bbox`, or use
    a module-level preset.

    Attributes
    ----------
    name : str
        Stable machine-readable identifier (e.g. ``"yeongdeok_2025"``).
    name_kr : str
        Korean display name.
    name_en : str
        English display name.
    bbox_wgs84 : tuple[float, float, float, float]
        (minlon, minlat, maxlon, maxlat) in EPSG:4326.
    bbox_epsg5179 : tuple[float, float, float, float]
        (minx, miny, maxx, maxy) in EPSG:5179. Computed automatically by
        :meth:`from_wgs84_bbox`.
    vulnerability_tier : 1 | 2 | 3
        Project priority class (see module docstring).
    dominant_fuel : str
        Code matching the fuel-model registry (e.g. ``"KP_PINE"``,
        ``"FM10"``, ``"FM9"``). Used by validation harnesses to choose
        the right Rothermel inputs.
    event_date_range : tuple[date, date] | None
        For historical-event regions: (start, end) of the wildfire event.
        ``None`` for general-purpose regions.
    notes : str
        Free-text description (citations, caveats, etc.).
    """

    name: str
    name_kr: str
    name_en: str
    bbox_wgs84: tuple[float, float, float, float]
    bbox_epsg5179: tuple[float, float, float, float]
    vulnerability_tier: VulnerabilityTier = 2
    dominant_fuel: str = "KP_PINE"
    event_date_range: tuple[date, date] | None = None
    notes: str = ""

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_wgs84_bbox(
        cls,
        name: str,
        bbox_wgs84: tuple[float, float, float, float],
        *,
        name_kr: str = "",
        name_en: str = "",
        vulnerability_tier: VulnerabilityTier = 2,
        dominant_fuel: str = "KP_PINE",
        event_date_range: tuple[date, date] | None = None,
        notes: str = "",
    ) -> "RegionConfig":
        """Build a region from a WGS84 bbox; computes the EPSG:5179 bbox."""
        minlon, minlat, maxlon, maxlat = bbox_wgs84
        if not (minlon < maxlon and minlat < maxlat):
            raise ValueError(
                f"degenerate bbox for region {name!r}: {bbox_wgs84}"
            )
        # Convert the 4 corners and take min/max — accounts for projection
        # distortion that could rotate the rectangle.
        xs, ys = [], []
        for lon, lat in (
            (minlon, minlat), (minlon, maxlat),
            (maxlon, minlat), (maxlon, maxlat),
        ):
            x, y = _to_5179.transform(lon, lat)
            xs.append(x); ys.append(y)
        bbox_5179 = (min(xs), min(ys), max(xs), max(ys))
        return cls(
            name=name,
            name_kr=name_kr or name,
            name_en=name_en or name,
            bbox_wgs84=bbox_wgs84,
            bbox_epsg5179=bbox_5179,
            vulnerability_tier=vulnerability_tier,
            dominant_fuel=dominant_fuel,
            event_date_range=event_date_range,
            notes=notes,
        )

    @classmethod
    def synthetic(
        cls,
        name: str = "synthetic",
        bbox_5179: tuple[float, float, float, float] = (0.0, 0.0, 5000.0, 5000.0),
    ) -> "RegionConfig":
        """A non-geographic synthetic region for unit tests.

        The synthetic region keeps an artificial EPSG:5179 bbox so the
        :class:`FireGrid` can still compute a grid; the WGS84 bbox is set
        to zeros (clearly non-geographic) so any downstream code that
        tries to overlay these on a map will fail loudly rather than
        silently produce nonsense.
        """
        return cls(
            name=name,
            name_kr="synthetic",
            name_en="synthetic",
            bbox_wgs84=(0.0, 0.0, 0.0, 0.0),   # sentinel
            bbox_epsg5179=bbox_5179,
            vulnerability_tier=3,
            dominant_fuel="KP_PINE",
            notes="Synthetic region for unit testing; NOT georeferenced.",
        )

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def width_m(self) -> float:
        """East-west extent of the region in metres (in EPSG:5179)."""
        minx, _, maxx, _ = self.bbox_epsg5179
        return maxx - minx

    @property
    def height_m(self) -> float:
        """North-south extent of the region in metres (in EPSG:5179)."""
        _, miny, _, maxy = self.bbox_epsg5179
        return maxy - miny

    @property
    def is_synthetic(self) -> bool:
        return self.bbox_wgs84 == (0.0, 0.0, 0.0, 0.0)

    def grid_dims(self, cell_size_m: float) -> tuple[int, int]:
        """Compute (nrows, ncols) for a regular EPSG:5179 grid at given cell size.

        Returns the smallest grid that fully contains the region bbox. Rows
        are i-up-to-down (max_y at top), columns are j-left-to-right
        (min_x at left) — i.e. the conventional raster orientation.
        """
        if cell_size_m <= 0.0:
            raise ValueError("cell_size_m must be > 0")
        ncols = max(1, int(round(self.width_m / cell_size_m)))
        nrows = max(1, int(round(self.height_m / cell_size_m)))
        return nrows, ncols

    def affine_transform(self, cell_size_m: float) -> tuple[float, float, float, float, float, float]:
        """Return a rasterio-style affine (a, b, c, d, e, f).

        For a north-up grid in EPSG:5179:

            x = c + a · j + b · i        (we want b = 0)
            y = f + d · j + e · i        (we want d = 0, e < 0)

        So we return ``(cell_size_m, 0, min_x, 0, -cell_size_m, max_y)``.
        """
        if cell_size_m <= 0.0:
            raise ValueError("cell_size_m must be > 0")
        minx, _miny, _maxx, maxy = self.bbox_epsg5179
        return (cell_size_m, 0.0, minx, 0.0, -cell_size_m, maxy)


# ---------------------------------------------------------------------------
# Tier 1 — Primary validation cases (East Coast Pine Belt)
# ---------------------------------------------------------------------------

# Yeongdeok 2025 — March 22–28, 2025 wildfire event in 영덕군.
# Approximate burn perimeter from KFS preliminary reports + news coverage.
# 3,800+ ha burned, evacuations across northern 영덕 (영해면, 창수면, 영덕읍).
YEONGDEOK_2025: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="yeongdeok_2025",
    name_kr="영덕군 (2025년 3월 산불)",
    name_en="Yeongdeok-gun (Mar 2025 wildfire)",
    bbox_wgs84=(129.25, 36.30, 129.55, 36.60),
    vulnerability_tier=1,
    dominant_fuel="KP_PINE",
    event_date_range=(date(2025, 3, 22), date(2025, 3, 28)),
    notes=(
        "Approximate bbox covering the affected area in northern Yeongdeok-gun. "
        "Refine with KFS perimeter shapefile when available. "
        "Reference: KFS preliminary report Mar 2025."
    ),
)

# Uljin/Samcheok 2022 — March 4–13, 2022, ~16,000 ha. Largest South Korean
# wildfire on record. Crossed 울진-삼척 boundary.
ULJIN_SAMCHEOK_2022: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="uljin_samcheok_2022",
    name_kr="울진·삼척 (2022년 3월 산불)",
    name_en="Uljin/Samcheok (Mar 2022 wildfire)",
    bbox_wgs84=(129.10, 36.85, 129.60, 37.30),
    vulnerability_tier=1,
    dominant_fuel="KP_PINE",
    event_date_range=(date(2022, 3, 4), date(2022, 3, 13)),
    notes=(
        "Approximate bbox spanning the Uljin → Samcheok burn corridor. "
        "Refine with KFS perimeter shapefile. "
        "Reference: KFS final report 2022."
    ),
)

# Goseong 2019 — April 4–6, 2019, ~2,800 ha, 2 fatalities. Wind-driven night fire.
GOSEONG_2019: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="goseong_2019",
    name_kr="고성·속초 (2019년 4월 산불)",
    name_en="Goseong/Sokcho (Apr 2019 wildfire)",
    bbox_wgs84=(128.45, 38.20, 128.65, 38.50),
    vulnerability_tier=1,
    dominant_fuel="KP_PINE",
    event_date_range=(date(2019, 4, 4), date(2019, 4, 6)),
    notes=(
        "Approximate bbox covering Goseong → Sokcho burn corridor. "
        "Refine with KFS perimeter shapefile. "
        "Reference: KFS final report 2019, MOIS deaths registry."
    ),
)


# ---------------------------------------------------------------------------
# Tier 1 — Deployment focus region (East Coast Pine Belt)
# ---------------------------------------------------------------------------

# Gangwon-do east coast + northern Gyeongsangbuk-do east coast.
# Boundaries: ~ 고성-군 in the north (~38.5° N), Pohang-si in the south
# (~36.0° N), 20 km inland (~127.8° E to coast at ~129.4° E).
EAST_COAST_PINE_BELT: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="east_coast_pine_belt",
    name_kr="동해안 소나무 벨트",
    name_en="East Coast Pine Belt",
    bbox_wgs84=(128.40, 36.00, 129.60, 38.60),
    vulnerability_tier=1,
    dominant_fuel="KP_PINE",
    notes=(
        "Gangwon-do east coast + northern Gyeongbuk east coast. "
        "Approximately Goseong-gun to Pohang-si. Predominantly Pinus densiflora "
        "stands with high rural-elderly population density and recurring "
        "wildfire history (Goseong 2019, Uljin/Samcheok 2022, Yeongdeok 2025)."
    ),
)


# ---------------------------------------------------------------------------
# Architectural national scope
# ---------------------------------------------------------------------------

KOREA_PENINSULA: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="korea_peninsula",
    name_kr="대한민국 전역",
    name_en="South Korea (national coverage)",
    bbox_wgs84=(124.0, 33.0, 132.0, 39.0),
    vulnerability_tier=2,
    dominant_fuel="KP_PINE",
    notes=(
        "Full South Korea coverage including Jeju and offshore islands. "
        "Data ingestion layer is expected to support this scope; deployment "
        "and validation focus on the East Coast Pine Belt only."
    ),
)


# ---------------------------------------------------------------------------
# Tier 2 — Round 2+ research extensions (NOT validated this session)
# ---------------------------------------------------------------------------

CENTRAL_MOUNTAIN_BELT: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="central_mountain_belt",
    name_kr="중부 산악 벨트 (충북·인내 강원)",
    name_en="Central Mountain Belt (N. Chungbuk + inland Gangwon)",
    bbox_wgs84=(127.40, 36.50, 128.50, 37.80),
    vulnerability_tier=2,
    dominant_fuel="FM9",  # mixed hardwood + conifer; FM9 closer than KP_PINE
    notes=(
        "Mixed forest, lower fire frequency than the pine belt. Defined as "
        "preset for the architecture but NOT validated in Session 2; "
        "reserved for Round 2+ research."
    ),
)

SOUTHWESTERN_COAST: Final[RegionConfig] = RegionConfig.from_wgs84_bbox(
    name="southwestern_coast",
    name_kr="서남해안 (전남·경남 서부)",
    name_en="Southwestern Coast (S. Jeolla + W. Gyeongnam)",
    bbox_wgs84=(125.50, 34.20, 127.50, 35.50),
    vulnerability_tier=2,
    dominant_fuel="FM9",
    notes=(
        "Humid spring climate, broadleaf-mixed stands. Lower wildfire risk "
        "than the East Coast Pine Belt. Reserved for Round 2+ research."
    ),
)


# ---------------------------------------------------------------------------
# Convenience registry
# ---------------------------------------------------------------------------

#: All named preset regions, by ``name`` key.
ALL_REGIONS: Final[dict[str, RegionConfig]] = {
    r.name: r
    for r in [
        YEONGDEOK_2025,
        ULJIN_SAMCHEOK_2022,
        GOSEONG_2019,
        EAST_COAST_PINE_BELT,
        KOREA_PENINSULA,
        CENTRAL_MOUNTAIN_BELT,
        SOUTHWESTERN_COAST,
    ]
}

#: Historical validation cases — the three events used to benchmark the
#: model in Session 2 / Session 3.
HISTORICAL_VALIDATION_CASES: Final[tuple[RegionConfig, ...]] = (
    YEONGDEOK_2025, ULJIN_SAMCHEOK_2022, GOSEONG_2019,
)


def lookup(name: str) -> RegionConfig:
    """Look up a region preset by name; raises KeyError on miss."""
    try:
        return ALL_REGIONS[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown region {name!r}. "
            f"Available: {sorted(ALL_REGIONS)}"
        ) from exc


__all__ = [
    # CRS strings
    "WGS84",
    "KOREA_2000_UNIFIED",
    # Type
    "RegionConfig",
    "VulnerabilityTier",
    # Tier 1 — primary
    "YEONGDEOK_2025",
    "ULJIN_SAMCHEOK_2022",
    "GOSEONG_2019",
    "EAST_COAST_PINE_BELT",
    # Architecture
    "KOREA_PENINSULA",
    # Tier 2
    "CENTRAL_MOUNTAIN_BELT",
    "SOUTHWESTERN_COAST",
    # Registry
    "ALL_REGIONS",
    "HISTORICAL_VALIDATION_CASES",
    "lookup",
]
