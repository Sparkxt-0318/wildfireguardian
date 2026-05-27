"""Synthetic Yeongdeok-like cellular-automaton demonstration.

Run::

    python -m wildfireguardian.spread_model.demo_yeongdeok_synthetic

This generates two artefacts:

- ``docs/figures/cellular_automaton_demo.gif`` — an animated spread
  visualisation, one frame per snapshot.
- ``data/processed/synthetic_demo_perimeters.geojson`` — a GeoJSON
  FeatureCollection of perimeter polygons, one feature per snapshot, with
  the snapshot time stored in the feature ``properties.time_min``.

Scenario
--------

A 100 × 100 grid of 60-m cells (6 km × 6 km) representing the kind of
terrain that surrounded the March 22–28 2025 영덕군 fires:

- Ignition at the centre of the grid, time 0.
- Synthetic terrain: a gentle ridge rising eastward (~0.5 km elevation
  gain across the grid), so the eastern half is upslope.
- Fuel: the Korean Pinus densiflora analogue defined here, with
  m_x = 120 % (live-fuel moisture of extinction) and LFMC = 40 %.
- Wind: 3 m/s **midflame** from the west, representing the 10-m KMA
  observed wind of ~15 m/s reduced by a canopy factor of ~0.2 for
  closed-canopy Korean Pinus (Andrews 2012).
- 6 hours of simulated time, dt = 2 min, snapshot every 20 min.

This is a **synthetic** scenario: no real terrain, fuel, or weather data
are used. The output is for visual demonstration of the model, not for
prediction. Real validation against the 2025 event will be done by the
``validation`` module in a later session.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np

from .cellular_automaton import (
    CellState,
    EnsembleConfig,
    FireGrid,
    MonteCarloEnsemble,
    WindField,
)
from .rothermel import FuelModel

# ---------------------------------------------------------------------------
# Scenario parameters
# ---------------------------------------------------------------------------

GRID_ROWS: int = 100
GRID_COLS: int = 100
CELL_SIZE_M: float = 50.0           # 5 km × 5 km landscape

IGNITION_RC: tuple[int, int] = (50, 30)   # offset west of centre so fire has room
DURATION_MIN: float = 360.0          # 6 hours
DT_MIN: float = 2.0
SNAPSHOT_EVERY_MIN: float = 20.0

# Yeongdeok-like fuel and weather.
# KMA reported 10-m winds of 10–15 m/s during 25 Mar 2025. Open-canopy and
# steep-slope sections give midflame factors ~ 0.3–0.5 (Andrews 2012), so a
# midflame of ~ 5 m/s is a defensible scenario value.
LFMC: float = 0.40                   # 40 % live fuel moisture
WIND_MIDFLAME_MS: float = 5.0        # midflame wind, m/s
WIND_FROM_DEG: float = 270.0         # from west (blowing east)

# Synthetic terrain.
SLOPE_MAX_DEG: float = 20.0          # peak slope on the synthetic ridge


def yeongdeok_pinus_fuel() -> FuelModel:
    """Korean Pinus densiflora analogue, single-class.

    See ``demo_sensitivity.py`` for the parameter rationale. Cloned here so
    that the two demos are independent.
    """
    return FuelModel(
        code="KP_PINE",
        name="Korean Pinus densiflora analogue (illustrative)",
        w_o=0.15,
        delta=0.5,
        sigma=2200.0,
        m_x=1.20,
        description="Custom: not part of Anderson 13. For demo only.",
    )


# ---------------------------------------------------------------------------
# Scenario construction
# ---------------------------------------------------------------------------


def build_grid(rng: np.random.Generator | None = None) -> FireGrid:
    """Construct the synthetic scenario grid.

    Parameters
    ----------
    rng : numpy.random.Generator | None
        If given, used to add small Gaussian noise to fuel moisture so each
        ensemble member sees a slightly different fuel state. If None, the
        fuel moisture is uniform.
    """
    grid = FireGrid(
        nrows=GRID_ROWS, ncols=GRID_COLS, cell_size_m=CELL_SIZE_M,
        residence_time_min=30.0,
    )

    # ----- fuel -----
    fm = yeongdeok_pinus_fuel()
    # Object array; each cell holds a reference to the same FuelModel
    # instance (FuelModel is frozen so sharing is safe).
    grid.fuel_model_id[:] = fm
    grid.fuel_moisture[:] = LFMC
    if rng is not None:
        # ±2 % moisture noise.
        grid.fuel_moisture[:] = np.clip(
            grid.fuel_moisture + rng.normal(0.0, 0.02, size=grid.fuel_moisture.shape),
            0.05, 2.00,
        ).astype(np.float32)

    # ----- terrain -----
    # A gentle east-rising ridge: elevation grows ~linearly with column j,
    # with a sinusoidal undulation along rows.
    ii, jj = np.meshgrid(
        np.arange(GRID_ROWS, dtype=np.float32),
        np.arange(GRID_COLS, dtype=np.float32),
        indexing="ij",
    )
    elev = (
        300.0
        + jj * 5.0                                 # ~500 m gain across 100 cells
        + 30.0 * np.sin(2.0 * np.pi * ii / 50.0)   # gentle N-S undulation
    )
    grid.elevation_m[:] = elev.astype(np.float32)

    # Slope and aspect from elevation gradient.
    dz_di, dz_dj = np.gradient(elev, CELL_SIZE_M, CELL_SIZE_M)
    # In array coords, di > 0 is south, dj > 0 is east. The slope magnitude
    # is atan(|grad|) and the aspect (compass bearing of downslope dir) is
    # atan2(dj, -di) of the gradient vector (downslope is the direction of
    # steepest descent = -grad).
    slope_rad = np.arctan(np.hypot(dz_di, dz_dj))
    grid.slope_degrees[:] = np.degrees(slope_rad).astype(np.float32)
    grid.aspect_degrees[:] = (
        (np.degrees(np.arctan2(dz_dj, -dz_di)) + 180.0) % 360.0
    ).astype(np.float32)
    # Cap slope at SLOPE_MAX_DEG just to keep numerics tame.
    np.minimum(grid.slope_degrees, SLOPE_MAX_DEG, out=grid.slope_degrees)

    # ----- ignition -----
    grid.ignite_point(*IGNITION_RC, time_min=0.0)
    return grid


def build_wind() -> WindField:
    return WindField.from_meteo(speed_ms=WIND_MIDFLAME_MS, from_deg=WIND_FROM_DEG)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_frame(grid: FireGrid, t_min: float) -> "PIL.Image.Image":
    """Render one CA snapshot as a PIL Image."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from PIL import Image

    fig, ax = plt.subplots(figsize=(6.5, 6.0), dpi=100)

    # Show elevation as a faint hillshade-like background.
    ax.imshow(grid.elevation_m, cmap="terrain", alpha=0.45,
              origin="upper", extent=(0, GRID_COLS * CELL_SIZE_M / 1000.0,
                                       0, GRID_ROWS * CELL_SIZE_M / 1000.0))

    # State overlay: transparent on UNBURNED, orange on BURNING, charcoal on BURNED.
    state = grid.state.astype(np.int32)
    overlay = np.full((*state.shape, 4), 0.0, dtype=np.float32)
    burning = state == CellState.BURNING
    burned = state == CellState.BURNED
    overlay[burning] = [0.95, 0.40, 0.10, 0.92]   # orange
    overlay[burned] = [0.18, 0.18, 0.18, 0.88]    # charcoal
    ax.imshow(overlay, origin="upper",
              extent=(0, GRID_COLS * CELL_SIZE_M / 1000.0,
                      0, GRID_ROWS * CELL_SIZE_M / 1000.0))

    # Wind arrow.
    ax.annotate(
        "", xy=(GRID_COLS * CELL_SIZE_M / 1000.0 * 0.85,
                GRID_ROWS * CELL_SIZE_M / 1000.0 * 0.92),
        xytext=(GRID_COLS * CELL_SIZE_M / 1000.0 * 0.70,
                GRID_ROWS * CELL_SIZE_M / 1000.0 * 0.92),
        arrowprops=dict(arrowstyle="-|>", color="#2c3e50", lw=2.0),
    )
    ax.text(GRID_COLS * CELL_SIZE_M / 1000.0 * 0.70,
            GRID_ROWS * CELL_SIZE_M / 1000.0 * 0.96,
            f"wind {WIND_MIDFLAME_MS:.1f} m/s midflame", fontsize=8.5,
            color="#2c3e50")

    ax.set_xlabel("East (km)")
    ax.set_ylabel("North (km)")
    n_burning = int(burning.sum())
    n_burned = int(burned.sum())
    burned_ha = (n_burning + n_burned) * (CELL_SIZE_M ** 2) / 10_000.0
    ax.set_title(
        f"Yeongdeok-synthetic CA  ·  t = {t_min:5.1f} min  "
        f"({t_min/60:.2f} h)\n"
        f"burning={n_burning}, burned={n_burned}, area = {burned_ha:.1f} ha",
        fontsize=10.5,
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def write_gif(frames: list, out_path: Path, duration_ms: int = 350) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    head, *tail = frames
    head.save(
        out_path,
        save_as="GIF",
        save_all=True,
        append_images=tail,
        loop=0,
        duration=duration_ms,
        disposal=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_demo(out_dir_docs: Path, out_dir_data: Path) -> dict:
    """Run the synthetic scenario and write GIF + GeoJSON artefacts.

    Returns
    -------
    dict
        Summary statistics for the overnight report.
    """
    grid = build_grid()
    wind = build_wind()

    # We step manually so we can render at each snapshot interval.
    frames: list = []
    perimeter_features: list[dict] = []

    t = 0.0
    next_snap = 0.0
    while t < DURATION_MIN - 1e-9:
        if t >= next_snap - 1e-9:
            frames.append(_render_frame(grid, t))
            peri = grid.perimeter()
            perimeter_features.append({
                "type": "Feature",
                "properties": {
                    "time_min": float(t),
                    "n_burning": int((grid.state == CellState.BURNING).sum()),
                    "n_burned": int((grid.state == CellState.BURNED).sum()),
                    "area_m2": grid.burned_area_m2(),
                },
                "geometry": peri.__geo_interface__ if peri is not None else None,
            })
            next_snap += SNAPSHOT_EVERY_MIN
        grid.step(DT_MIN, wind, current_time_min=t)
        t += DT_MIN

    # Final snapshot.
    frames.append(_render_frame(grid, t))
    peri = grid.perimeter()
    perimeter_features.append({
        "type": "Feature",
        "properties": {
            "time_min": float(t),
            "n_burning": int((grid.state == CellState.BURNING).sum()),
            "n_burned": int((grid.state == CellState.BURNED).sum()),
            "area_m2": grid.burned_area_m2(),
        },
        "geometry": peri.__geo_interface__ if peri is not None else None,
    })

    # Write GIF.
    gif_path = out_dir_docs / "cellular_automaton_demo.gif"
    write_gif(frames, gif_path, duration_ms=350)

    # Write GeoJSON.
    geojson_path = out_dir_data / "synthetic_demo_perimeters.geojson"
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    geojson_doc = {
        "type": "FeatureCollection",
        "name": "wildfireguardian_synthetic_yeongdeok_perimeters",
        "metadata": {
            "synthetic": True,
            "fuel_model": "KP_PINE (custom, not Anderson 13)",
            "lfmc": LFMC,
            "wind_midflame_ms": WIND_MIDFLAME_MS,
            "wind_from_deg": WIND_FROM_DEG,
            "cell_size_m": CELL_SIZE_M,
            "grid_shape": [GRID_ROWS, GRID_COLS],
            "duration_min": DURATION_MIN,
            "dt_min": DT_MIN,
            "ignition_rc": list(IGNITION_RC),
            "note": (
                "Coordinates are in metres in a synthetic local frame "
                "anchored at the SW corner of the grid. Not georeferenced."
            ),
        },
        "features": perimeter_features,
    }
    geojson_path.write_text(json.dumps(geojson_doc, indent=2))

    return {
        "n_frames": len(frames),
        "n_perimeter_features": len(perimeter_features),
        "final_burned_cells": int(grid.burned_mask().sum()),
        "final_burned_ha": grid.burned_area_m2() / 10_000.0,
        "final_burning_cells": int((grid.state == CellState.BURNING).sum()),
        "final_burned_only_cells": int((grid.state == CellState.BURNED).sum()),
        "gif_path": str(gif_path),
        "geojson_path": str(geojson_path),
    }


def main() -> None:  # pragma: no cover - CLI entry
    from rich.console import Console
    from rich.table import Table

    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    docs_dir = repo_root / "docs" / "figures"
    data_dir = repo_root / "data" / "processed"

    console = Console()
    console.rule("[bold]Synthetic Yeongdeok CA demo")

    stats = run_demo(docs_dir, data_dir)

    table = Table(title="Run summary")
    table.add_column("metric", style="bold")
    table.add_column("value", justify="right")
    for k, v in stats.items():
        table.add_row(k, str(v))
    console.print(table)
    console.print(f"[green]done.[/green]")


if __name__ == "__main__":  # pragma: no cover
    main()
