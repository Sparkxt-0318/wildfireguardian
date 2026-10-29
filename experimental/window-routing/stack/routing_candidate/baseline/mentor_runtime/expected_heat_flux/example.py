"""Deterministic illustrative active-burning probability-to-radiant-flux demo.

Run from the workspace directory with::

    python -m expected_heat_flux.example --output expected_heat_flux/outputs/demo

The probabilities and physical parameters are synthetic, not a calibrated
wildfire case or a temperature/total-heat prediction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import AffineGrid, CombustionParameters, ExpectedHeatFluxModel


def run_demo(output: str | Path) -> dict:
    """Write deterministic arrays, a figure, and a unit-explicit JSON summary."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    shape = (100, 100)
    cell_size_m = 10.0
    grid = AffineGrid.from_cell_size(
        cell_size_m=cell_size_m,
        origin_xy_m=(-500.0, -500.0),
        row_direction=1,
    )
    centers_xy_m = grid.centers(shape)
    x_m = centers_xy_m[..., 0]
    y_m = centers_xy_m[..., 1]
    # Analytic smooth patches ensure reproducibility without random sampling.
    main_patch = 0.85 * np.exp(
        -0.5 * (((x_m + 100.0) / 85.0) ** 2 + ((y_m - 40.0) / 65.0) ** 2)
    )
    second_patch = 0.45 * np.exp(
        -0.5 * (((x_m - 140.0) / 55.0) ** 2 + ((y_m + 100.0) / 90.0) ** 2)
    )
    p = np.clip(main_patch + second_patch, 0.0, 1.0)

    fuel = CombustionParameters(
        fuel_load_kg_m2=1.0,
        heat_of_combustion_j_kg=18_000_000.0,
        burning_duration_s=60.0,
        consumed_fraction=1.0,
    )
    hrr_density_w_m2 = float(fuel.heat_release_rate_density_w_m2)
    radiative_fraction = 0.30
    emission_height_m = 5.0
    receiver_height_m = 0.0
    atmospheric_transmissivity = 1.0
    exposure_duration_s = 60.0

    model = ExpectedHeatFluxModel(
        grid=grid,
        heat_release_rate_density_w_m2=hrr_density_w_m2,
        radiative_fraction=radiative_fraction,
        emission_height_m=emission_height_m,
        receiver_height_m=receiver_height_m,
        atmospheric_transmissivity=atmospheric_transmissivity,
    )
    result = model.predict(p)
    flux_w_m2 = result.incident_heat_flux_w_m2
    energy_j_m2 = result.incident_energy_j_m2(exposure_duration_s)

    # Independent square-center formula: Omega=4*atan(L²/(4h*sqrt(h²+L²/2))).
    separation_m = emission_height_m - receiver_height_m
    omega_sr = 4.0 * np.arctan(
        cell_size_m**2
        / (4.0 * separation_m * np.sqrt(separation_m**2 + cell_size_m**2 / 2.0))
    )
    analytic_transfer = omega_sr / (4.0 * np.pi)
    analytic_flux_w_m2 = (
        atmospheric_transmissivity
        * radiative_fraction
        * hrr_density_w_m2
        * analytic_transfer
    )
    single_result = model.predict(np.ones((1, 1), dtype=float))
    computed_single_flux_w_m2 = float(single_result.incident_heat_flux_w_m2[0, 0])
    np.testing.assert_allclose(
        computed_single_flux_w_m2,
        analytic_flux_w_m2,
        rtol=1e-12,
        atol=1e-8,
        err_msg="Single-square geometric verification failed",
    )

    arrays_path = output_path / "heat_flux_arrays.npz"
    np.savez_compressed(
        arrays_path,
        active_burning_probability=p,
        incident_heat_flux_w_m2=flux_w_m2,
        incident_heat_flux_kw_m2=result.incident_heat_flux_kw_m2,
        constant_exposure_incident_energy_j_m2=energy_j_m2,
        cell_centers_xy_m=centers_xy_m,
        affine_transform=np.asarray(grid.transform, dtype=float),
        exposure_duration_s=np.asarray(exposure_duration_s),
    )

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), constrained_layout=True)
    extent = (-500.0, 500.0, -500.0, 500.0)
    panels = [
        (p, "Active-burning probability", "Probability [0–1]", "viridis", 1.0),
        (
            result.incident_heat_flux_kw_m2,
            "Expected incident radiant flux",
            "Incident flux [kW/m²]",
            "inferno",
            None,
        ),
        (
            energy_j_m2 / 1_000_000.0,
            "Radiant energy over constant 60 s",
            "Incident energy [MJ/m²]",
            "magma",
            None,
        ),
    ]
    for ax, (values, title, colorbar_label, cmap, vmax) in zip(axes, panels):
        artist = ax.imshow(
            values,
            origin="lower",
            extent=extent,
            cmap=cmap,
            vmin=0.0,
            vmax=vmax,
            interpolation="nearest",
        )
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        fig.colorbar(artist, ax=ax, shrink=0.84, label=colorbar_label)
    fig.suptitle(
        "Synthetic illustration · 10 m cells · source 5 m above receiver\n"
        "Conditional HRR 300 kW/m² · radiative fraction 0.30 · transmission 1",
        fontsize=12,
    )
    figure_path = output_path / "heat_flux_demo.png"
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)

    summary = {
        "case": "deterministic synthetic illustration",
        "probability_semantics": "P(cell is actively burning at the modeled instant)",
        "validation_status": "Analytic geometry verification only; no measured wildfire validation",
        "output_scope": "Expected incident thermal radiation at upward-facing horizontal receiver points",
        "constant_exposure_assumption": "Probability and conditional source strengths remain constant throughout the receiver exposure",
        "shape_rows_columns": list(shape),
        "grid": {
            "affine_transform": list(grid.transform),
            "transform_convention": "x=a*column+b*row+c; y=d*column+e*row+f; pixel corners",
            "coordinate_units": "m",
            "cell_area_m2": float(grid.cell_area_m2),
            "receiver_location": "grid cell centers; point values, not receiver-area means",
        },
        "parameters": {
            "fuel_load_kg_m2": 1.0,
            "heat_of_combustion_j_kg": 18_000_000.0,
            "burning_duration_s": 60.0,
            "consumed_fraction": 1.0,
            "heat_release_rate_density_w_m2": hrr_density_w_m2,
            "radiative_fraction": radiative_fraction,
            "emission_height_m": emission_height_m,
            "receiver_height_m": receiver_height_m,
            "atmospheric_transmissivity": atmospheric_transmissivity,
            "receiver_exposure_duration_s": exposure_duration_s,
        },
        "statistics": {
            "active_burning_probability_min": float(np.min(p)),
            "active_burning_probability_max": float(np.max(p)),
            "expected_active_source_area_m2": float(np.sum(p) * grid.cell_area_m2),
            "expected_total_radiant_power_w": float(result.expected_total_radiant_power_w),
            "incident_heat_flux_min_w_m2": float(np.min(flux_w_m2)),
            "incident_heat_flux_max_w_m2": float(np.max(flux_w_m2)),
            "incident_heat_flux_mean_w_m2": float(np.mean(flux_w_m2)),
            "constant_exposure_incident_energy_max_j_m2": float(np.max(energy_j_m2)),
        },
        "single_square_analytic_check": {
            "cell_side_m": cell_size_m,
            "source_receiver_separation_m": separation_m,
            "active_burning_probability": 1.0,
            "solid_angle_sr": float(omega_sr),
            "transfer_factor": float(analytic_transfer),
            "analytic_incident_heat_flux_w_m2": float(analytic_flux_w_m2),
            "computed_incident_heat_flux_w_m2": computed_single_flux_w_m2,
            "absolute_error_w_m2": float(abs(computed_single_flux_w_m2 - analytic_flux_w_m2)),
            "passed": True,
        },
        "files": {"arrays": arrays_path.name, "figure": figure_path.name, "summary": "summary.json"},
    }
    (output_path / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("expected_heat_flux/outputs/demo"),
        help="Directory for deterministic arrays, summary, and figure",
    )
    args = parser.parse_args()
    summary = run_demo(args.output)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
