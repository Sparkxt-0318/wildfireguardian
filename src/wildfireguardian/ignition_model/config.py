"""Shared configuration for the data-driven ignition-probability model.

This sub-package implements a *data-driven* fire-spread model that learns,
per currently-unburned cell, the probability that the cell ignites by the
next satellite overpass::

    P(cell ignites by t+1 | local conditions at <= t)

It is a deliberate pivot away from the retired mechanistic
:mod:`wildfireguardian.spread_model` (Rothermel surface CA + crown/spotting),
which captured only ~9% of observed burned area on Korean spring pine fires
because those fires are crown- and spotting-driven. The data-driven model
sidesteps that physics bottleneck by learning spread directly from observed
fire progression in real multi-fire satellite data.

All geometry is done in a single projected CRS so distances/slopes are in
metres. We use **EPSG:5179 (Korea 2000 / Unified CS)** -- the same CRS the
rest of WildfireGuardian uses -- because:

* It is a single Transverse-Mercator system covering *all* of South Korea,
  including both the ~129 deg E east-coast fires and the ~126.6 deg E
  west-coast Hongseong fire, with sub-metre-level distance error over a
  fire-sized AOI. A single UTM zone (51N vs 52N) would split that set and
  distort one region.
* Units are metres, which is what every feature (distance, slope, FRP
  kernels) needs.

Provenance of the underlying layers (all real, no synthetic data):

* Active fire detections -- NASA FIRMS (VIIRS 375 m + MODIS 1 km).
* DEM -- NASA SRTMGL1 1-arc-second (~30 m), EPSG:4326.
* Fuel / landcover -- ESA WorldCover 2021 (10 m).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# Repository root = three parents up from this file
# (.../src/wildfireguardian/ignition_model/config.py).
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "raw" / "firms_data"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "ignition_model"
DEFAULT_FIGURE_DIR = REPO_ROOT / "docs" / "figures" / "ignition_model"

# --------------------------------------------------------------------------
# Projected CRS and grid
# --------------------------------------------------------------------------
PROJECTED_CRS = "EPSG:5179"  # Korea 2000 / Unified CS (metres)
GEOGRAPHIC_CRS = "EPSG:4326"

# 375 m matches the VIIRS I-band active-fire pixel. Going finer would invent
# precision the labels do not have (a VIIRS pixel is the atomic unit of
# observation); going coarser would merge distinct ignition events.
CELL_SIZE_M = 375.0

# --------------------------------------------------------------------------
# Overpass clustering
# --------------------------------------------------------------------------
# Detections whose timestamps are within this gap belong to the same
# "overpass" epoch. The afternoon constellation (Aqua, SNPP, NOAA-20, all
# ~13:30 local) crosses a given fire within ~50 min of each other and sees
# essentially the *same* fire state, so they must be merged -- otherwise we
# manufacture spurious near-zero-spread "transitions". Terra (~10:30) and the
# night passes are hours away. A 60-minute gap merges the co-incident
# constellation (<=~50 min apart) while cleanly separating the genuinely
# distinct morning / afternoon / night observation windows. (Audited: at
# 30-45 min the ~50-min NOAA-20/SNPP offset splits into noise; at 90 min we
# lose real transitions on the small fires.)
OVERPASS_GAP_MINUTES = 60.0

# --------------------------------------------------------------------------
# Candidate neighbourhood
# --------------------------------------------------------------------------
# A currently-unburned cell is a *candidate* (gets a row + label) only if it
# lies within this distance of any actively-burning cell. Rationale: the
# front advances from the current perimeter, so next-overpass ignitions
# concentrate in a band around it. 2 km balances (a) capturing realistic
# wind-driven spread over the multi-hour gaps between Korean-fire overpasses
# against (b) keeping the negative class tractable. We *report* the fraction
# of true new ignitions that fall inside this band (the recall ceiling) so
# the choice is auditable rather than assumed.
CANDIDATE_RADIUS_M = 2000.0

# Local-count / FRP kernel radii (metres).
NEIGHBOUR_RADII_M = (500.0, 1000.0)

# Distance bands (metres) for the conditional-AUC honesty metric. Bands are
# half-open on the LEFT, closed on the RIGHT: (lo, hi]. With 375 m cells the
# smallest possible candidate->fire distance is exactly one cell (375 m, an
# orthogonal neighbour), so the first band is "<= 375 m" (the adjacent ring);
# a literal [0,375) band would always be empty.
DISTANCE_BANDS_M = ((-1.0, 375.0), (375.0, 750.0), (750.0, 1500.0), (1500.0, 1e9))
DISTANCE_BAND_LABELS = ("<=375m", "375-750m", "750-1500m", ">1500m")

# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------
RANDOM_SEED = 20260530

# --------------------------------------------------------------------------
# Fire usability (from the brief + the Deliverable-0 audit).
# --------------------------------------------------------------------------
# Fires dropped outright: too few overpasses to observe spread at all.
DROP_FIRES = ("gangneung_2023",)  # 2 overpass-hours, 17 detections

# Fires whose fuel raster is broken (clipped at the WorldCover 129 deg E
# 3-degree tile boundary so the fire itself is almost entirely outside fuel
# coverage). Confirmed in the audit: fraction of detections inside the fuel
# extent is ~9% (yeongdeok) and ~5% (gangneung_donghae). Handled per-cell:
# fuel features become NaN where the cell is outside fuel coverage and the
# is_burnable HARD GATE only fires on *known* non-burnable cells, so these
# fires are predicted "fuel-blind". Their held-out scores are reported
# separately and excluded from the headline mean.
FUEL_BROKEN_FIRES = ("yeongdeok_2025", "gangneung_donghae_2022")

# Temporally sparse: include in the training pool but report its held-out
# result separately (per the brief).
SPARSE_FIRES = ("goseong_2019",)  # 3 overpass-hours

# Fires forming the headline mean +/- std (adequate fuel AND temporal depth).
HEADLINE_FIRES = (
    "uljin_samcheok_2022",
    "uiseong_andong_2025",
    "hongseong_2023",
    "miryang_2022",
)


@dataclass(frozen=True)
class PipelineConfig:
    """Bundle of knobs threaded through the pipeline (all have defaults)."""

    data_dir: Path = DEFAULT_DATA_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    figure_dir: Path = DEFAULT_FIGURE_DIR
    cell_size_m: float = CELL_SIZE_M
    overpass_gap_minutes: float = OVERPASS_GAP_MINUTES
    candidate_radius_m: float = CANDIDATE_RADIUS_M
    neighbour_radii_m: tuple[float, ...] = NEIGHBOUR_RADII_M
    random_seed: int = RANDOM_SEED
    drop_fires: tuple[str, ...] = DROP_FIRES
    fuel_broken_fires: tuple[str, ...] = FUEL_BROKEN_FIRES
    sparse_fires: tuple[str, ...] = SPARSE_FIRES
    headline_fires: tuple[str, ...] = HEADLINE_FIRES
    extra_buffer_m: float = 3000.0  # grid padding beyond detection extent
