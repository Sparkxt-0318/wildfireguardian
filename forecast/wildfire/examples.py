"""Examples operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path



# Api example
# Load a saved model, predict one real snapshot, and optionally compute radiant heat.
# 
# Run from the workspace with ``python -m wildfire example``.
# Data/checkpoint arguments are explicit overrides for a wheel installation. The
# optional heat example uses reference-fuel residence durations, reconstructed
# arrival ages, and illustrative fuel/combustion parameters.

import argparse
import json
from pathlib import Path

import numpy as np

from wildfire import load_model
from wildfire.data import DEFAULT_ROOT


from .paths import DEFAULT_CHECKPOINT as api_DEFAULT_CHECKPOINT


def api_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=api_DEFAULT_CHECKPOINT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--event", default="WY-BTF-002416_FishCreek")
    parser.add_argument("--cutoff-utc", default="2024-08-23T00:00:00Z")
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--heat", action="store_true", help="Add illustrative radiant heat and coverage bounds")
    parser.add_argument("--burning-duration-s", type=float,
                        help="Explicit uniform duration scenario; otherwise read aligned FBFM40 fuel data")
    parser.add_argument("--output", type=Path, help="Save arrays to a new NPZ file")
    args = parser.parse_args()
    model = load_model(args.checkpoint, device=args.device)
    with model.load_data(args.data_root, events=[args.event], sequence_length=1,
                         time_range=(args.cutoff_utc, args.cutoff_utc)) as dataset:
        if len(dataset) != 1:
            raise ValueError("The example requires exactly one full-grid cutoff snapshot")
        sample = dataset[0]
    probability, coordinates = model.predict_sample(sample)
    prediction = model.predict_sample_details(sample)
    arrays = {name: getattr(prediction, name).cpu().numpy()
              for name in prediction.__dataclass_fields__}
    arrays.update(probability=probability.cpu().numpy(), coordinates=coordinates.numpy(),
                  coordinate_epsg=np.asarray(4326, dtype=np.int64),
                  coordinate_order=np.asarray(["latitude", "longitude"]),
                  projected_coordinates=sample["coordinates"].numpy(),
                  affine_transform=sample["affine_transform"].numpy(),
                  source_epsg=sample["epsg"].numpy())
    known = arrays["probability"][arrays["valid"]]
    summary = {
        "event_id": args.event, "cutoff_utc": args.cutoff_utc, "family": model.family,
        "device": str(model.device), "channels": list(model.channel_names),
        "probability_shape": list(arrays["probability"].shape),
        "coordinate_shape": list(arrays["coordinates"].shape),
        "coordinate_order": ["latitude", "longitude"], "coordinate_epsg": 4326,
        "known_predictions": int(arrays["valid"].sum()),
        "unknown_predictions": int((~arrays["valid"]).sum()),
        "minimum_known_probability": float(known.min()) if known.size else None,
        "maximum_known_probability": float(known.max()) if known.size else None,
    }
    if args.heat:
        from wildfire.heat import AffineGrid
        from wildfire.heat import CombustionParameters
        from wildfire.heat import FlameResidenceTime

        grid = AffineGrid(tuple(sample["affine_transform"].tolist()))
        if args.burning_duration_s is None:
            residence = FlameResidenceTime.from_fbfm40_raster(
                args.data_root / "regions" / args.event / "fuel" / "landfire_2016_fbfm40_375m.tif",
                grid=grid, expected_shape=tuple(sample["burned_area"].shape[-2:]),
                epsg=int(sample["epsg"]), fallback_sav_m_inv=2000.0 / 0.3048,
            )
        else:
            residence = FlameResidenceTime(
                args.burning_duration_s, {"source": "explicit CLI uniform duration scenario"},
            )
        # Fuel/heat yield/consumed fraction are illustrative. The FBFM40 reader
        # records reference fuel and the explicit unsupported-class SAV fallback.
        heat_model = model.heat_model(
            grid=grid,
            combustion=CombustionParameters.from_flame_residence(
                residence, fuel_load_kg_m2=1.0, heat_of_combustion_j_kg=18_000_000.0,
                consumed_fraction=0.10,
            ),
            residence_time=residence,
            radiative_fraction=0.3, emission_height_m=5.0,
        )
        heat_flux, heat_coordinates = heat_model.predict_sample(sample)
        heat = heat_model.predict_sample_details(sample)
        arrays["heat_coordinates"] = heat_coordinates
        arrays["heat_expected_heat_flux_w_m2"] = heat_flux
        arrays["heat_residence_duration_s"] = residence.duration_s
        for name in heat.__dataclass_fields__:
            value = getattr(heat, name)
            if isinstance(value, np.ndarray):
                arrays["heat_" + name] = value
        summary.update(complete_expected_heat_available=heat.complete,
                       heat_coordinate_shape=list(heat_coordinates.shape),
                       heat_flux_units="W/m2", incident_energy_units="J/m2",
                       heat_parameters="duration-aware arrival scenario with illustrative uniform fuel and combustion",
                       heat_residence_provenance=residence.provenance_dict(),
                       initial_active_burning_cells=int(np.count_nonzero(
                           heat.initial_burning_valid & (heat.initial_active_burning_probability > 0))),
                       heat_endpoint_complete=heat.endpoint_complete)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        summary["saved_arrays"] = str(args.output.resolve())
    print(json.dumps(summary, indent=2))




# Example
# Runnable DataLoader example; no training or downloads.

import torch
from torch.utils.data import DataLoader

from wildfire.data import WildfireSequenceDataset
from wildfire.data import collate_fire_sequences


def load_main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--events',nargs='+')
    p.add_argument('--sequence-length',type=int,default=2)
    p.add_argument('--patch-size',type=int,nargs='+',default=[0],
                   help='0: original rectangle; one size: square patch; height width: rectangular patch')
    p.add_argument('--categorical-encoding',choices=['one_hot','raw'],default='one_hot')
    p.add_argument('--batch-size',type=int,default=1)
    p.add_argument('--workers',type=int,default=0)
    args = p.parse_args()
    if len(args.patch_size)==1:
        patch=args.patch_size[0] or None
    elif len(args.patch_size)==2:
        patch=tuple(args.patch_size)
    else:
        p.error('--patch-size expects one size or height width')
    dataset = WildfireSequenceDataset(args.data_root,events=args.events,
             sequence_length=args.sequence_length,patch_size=patch,
             categorical_encoding=args.categorical_encoding)
    try:
        loader = DataLoader(dataset,batch_size=args.batch_size,shuffle=False,
                            num_workers=args.workers,collate_fn=collate_fire_sequences,
                            multiprocessing_context='spawn' if args.workers else None)
        batch = next(iter(loader))
        summary = dict(events=len(dataset.event_ids),samples=len(dataset),
                       channels=len(dataset.channel_names),
                       source_channels=len(dataset.source_channel_names),
                       categorical_encoding=dataset.categorical_encoding,
                       input_shape=list(batch['features'].shape),
                       target_shape=list(batch['burned_area'].shape),
                       event_ids=batch['event_id'],
                       tensor_device=str(batch['features'].device),
                       valid_input_values=int(batch['feature_valid'].sum()),
                       pytorch_version=torch.__version__)
        print(json.dumps(summary,indent=2))
    finally:
        dataset.close()




# Example
# Run an explicitly untrained demonstration on a real rectangular sequence.



from wildfire.models import EnvironmentConditionedConvolution


# Re-exported for callers of the original demonstration module.
from wildfire.schema import CHANNELS
# Fixed unit scales, only for this untrained numerical demonstration. These
# are not fitted standard deviations or scientifically calibrated parameters.
UNIT_SCALES = (50.0, 20.0, 20.0, 90.0, 100.0)


def scale_demo_features(features):
    shape = (1,) * (features.ndim - 3) + (len(CHANNELS), 1, 1)
    return features / features.new_tensor(UNIT_SCALES).reshape(shape)


def model_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", default="KFS_01")
    parser.add_argument("--sample-index", type=int)
    parser.add_argument("--sequence-length", type=int, default=2)
    parser.add_argument("--kernel-size", type=int, default=3)
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    dataset = WildfireSequenceDataset(
        events=[args.event], sequence_length=args.sequence_length,
        patch_size=None, channels=CHANNELS,
    )
    try:
        index = len(dataset) // 4 if args.sample_index is None else args.sample_index
        sample = dataset[index]
        device = torch.device(args.device)
        torch.manual_seed(7)
        model = EnvironmentConditionedConvolution(
            len(CHANNELS), kernel_size=args.kernel_size,
        ).to(device).eval()
        with torch.no_grad():
            result = model(
                sample["burned_area"].to(device),
                scale_demo_features(sample["features"]).to(device),
                burned_area_valid=sample["burned_area_valid"].to(device),
                feature_valid=sample["feature_valid"].to(device),
                dt_hours=args.hours,
            )
        values = result.probability[result.valid]
        print(json.dumps({
            "interpretation": "Untrained shape/mask demonstration; no forecast validation",
            "event_id": sample["event_id"],
            "sample_index": index,
            "location": dataset.sample_location(index),
            "channel_names": list(CHANNELS),
            "input_shape": list(sample["features"].shape),
            "probability_shape": list(result.probability.shape),
            "dt_hours": args.hours,
            "kernel_size": args.kernel_size,
            "valid_probabilities": int(result.valid.sum()),
            "unknown_probabilities": int((~result.valid).sum()),
            "valid_rates": int(result.rate_valid.sum()),
            "probability_min": float(values.min()) if values.numel() else None,
            "probability_max": float(values.max()) if values.numel() else None,
            "device": str(device),
        }, indent=2))
    finally:
        dataset.close()




# Example
# Deterministic illustrative active-burning probability-to-radiant-flux demo.
# 
# Run from the workspace directory with::
# 
#     python -m wildfire radiation --output demonstration/heat/demo
# 
# The probabilities and physical parameters are synthetic, not a calibrated
# wildfire case or a temperature/total-heat prediction.




from wildfire.heat import AffineGrid
from wildfire.heat import CombustionParameters
from wildfire.heat import ExpectedHeatFluxModel


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
    # This synthetic metric grid has no geographic CRS. The details method
    # preserves the physical calculation without asserting a location on Earth.
    result = model.predict_details(p)
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
    single_result = model.predict_details(np.ones((1, 1), dtype=float))
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


def radiation_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("demonstration/heat/demo"),
        help="Directory for deterministic arrays, summary, and figure",
    )
    args = parser.parse_args()
    summary = run_demo(args.output)
    print(json.dumps(summary, indent=2, allow_nan=False))




# Integrated example
# Reproduce a saved forecast with duration-aware ecological radiant heat.
# 
# The example uses an existing checkpoint and an existing retrospective event
# bundle. It does not train, download data, or use next-hour labels in inference.
# Reference FBFM40 fuel classes supply literature-based per-cell front residence
# times. Retrospective point arrivals and those durations determine a present-fire
# scenario, not an observation of flames. Other combustion parameters and missing
# fuel/SAV fallback scenarios remain illustrative.


from dataclasses import fields
from datetime import datetime, timezone
import hashlib


from wildfire.heat import EcologicalFuelMaps
from wildfire.heat import WildfireHeatModel
from wildfire.heat import FlameResidenceTime


WORKSPACE = Path(__file__).resolve().parents[1]
DATA_ROOT = WORKSPACE / "data" / "environment"
from .paths import DEFAULT_CHECKPOINT as heat_DEFAULT_CHECKPOINT
DEFAULT_EVENT = "WY-BTF-002416_FishCreek"
DEFAULT_CUTOFF = "2024-08-23T00:00:00Z"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _heat_stats(values: np.ndarray) -> dict:
    finite = np.asarray(values)[np.isfinite(values)]
    return {
        "finite_cells": int(finite.size),
        "unknown_cells": int(np.asarray(values).size - finite.size),
        "minimum": float(finite.min()) if finite.size else None,
        "maximum": float(finite.max()) if finite.size else None,
        "mean": float(finite.mean()) if finite.size else None,
        "sum": float(finite.sum()) if finite.size else None,
    }


def _heat_plot(path: Path, arrays: dict, cutoff: str, event: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Work in map coordinates relative to the source-grid corner (kilometres).
    transform = arrays["affine_transform"]
    a, b, c, d, e, f = transform
    height, width = arrays["probability_valid"].shape
    if b != 0 or d != 0:
        raise ValueError("This demonstration plot requires an axis-aligned affine grid")
    extent = (0, a * width / 1000, e * height / 1000, 0)
    q = np.ma.array(arrays["new_burn_probability"], mask=~arrays["probability_valid"])
    mean_active = np.ma.array(arrays["mean_active_burning_probability"],
                              mask=~arrays["active_burning_valid"])
    initial_plot_valid = arrays["initial_burning_valid"] & arrays["source_burned_area_valid"]
    initial_active = np.ma.array(arrays["initial_active_burning_probability"],
                                 mask=~initial_plot_valid)
    initial_remaining = np.ma.array(arrays["initial_remaining_burning_duration_s"],
                                    mask=~initial_plot_valid)
    known = arrays["known_source_heat_flux_w_m2"]
    uniform = arrays["uniform_known_source_heat_flux_w_m2"]
    difference = known - uniform
    panels = [
        (q, "Predicted new burning within next hour", "Probability", "viridis", 0, 1),
        (arrays["fuel_load_with_explicit_fallback_kg_m2"],
         "FCCS reference fuel with explicit fallback", "Dry fuel load (kg/m²)", "YlGn", 0, None),
        (arrays["flame_residence_duration_s"],
         "FBFM40 residence with explicit SAV fallback", "Front residence (s)", "YlGn", 0, None),
        (initial_active, "Inferred flames at cutoff from arrival age", "Active-burning scenario (0 or 1)", "viridis", 0, 1),
        (initial_remaining, "Inferred remaining flame duration at cutoff", "Remaining duration (s)", "YlGn", 0,
         max(float(np.max(initial_remaining.filled(0.0))), 1.0)),
        (mean_active, "Mean occupancy: existing + new burning", "Active-burning probability", "viridis", 0, None),
        (known, "Known-source expected mean radiant flux", "Incident radiant flux (W/m²)", "inferno", 0, None),
        (arrays["heat_flux_upper_bound_w_m2"],
         "Upper bound for unresolved source activity", "Incident radiant flux (W/m²)", "inferno", 0, None),
        (difference, "Ecological minus uniform-fuel contribution", "Flux difference (W/m²)", "RdBu_r", None, None),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(16, 14), constrained_layout=True)
    for axis, (values, title, unit, cmap, vmin, vmax) in zip(axes.flat, panels):
        palette = plt.get_cmap(cmap).copy()
        palette.set_bad("#c8c8c8")
        if cmap == "RdBu_r":
            limit = max(float(np.max(np.abs(values))), 1e-12)
            vmin, vmax = -limit, limit
        image = axis.imshow(values, origin="upper", extent=extent, cmap=palette,
                            vmin=vmin, vmax=vmax, interpolation="nearest")
        axis.set_title(title, fontsize=11)
        axis.set_xlabel("East displacement from grid corner (km)")
        axis.set_ylabel("North displacement from grid corner (km)")
        fig.colorbar(image, ax=axis, label=unit, shrink=0.85)
    fig.suptitle(
        f"{event} — cutoff {cutoff}\n"
        "Retrospective arrival + reference-fuel residence scenario; gray cells are unknown; "
        "bounds are not observed heat",
        fontsize=13,
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)


def heat_run(
    *,
    checkpoint: Path = heat_DEFAULT_CHECKPOINT,
    data_root: Path = DATA_ROOT,
    event: str = DEFAULT_EVENT,
    cutoff_utc: str = DEFAULT_CUTOFF,
    output: Path | None = None,
    device: str = "cpu",
) -> dict:
    """Run one cutoff snapshot, retaining unknown coverage and assumptions."""
    import torch

    from wildfire.data import WildfireSequenceDataset

    checkpoint = resolve_recorded_path(checkpoint).resolve()
    data_root = resolve_recorded_path(data_root).resolve()
    output = Path(output or WORKSPACE / "demonstration" / "heat" / "duration_aware_demo").resolve()
    output.mkdir(parents=True, exist_ok=True)

    # The saved contract selects channels and categorical vocabulary; no new
    # normalization statistics are fitted on this event.
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    contract = saved["contract"]
    dataset = WildfireSequenceDataset(
        data_root,
        events=[event],
        channels=contract["channels"],
        categorical_encoding=contract.get("categorical_encoding", "one_hot"),
        categorical_classes=contract.get("categorical_classes") or None,
        sequence_length=1,
        time_range=(cutoff_utc, cutoff_utc),
        daily_policy="completed_day",
    )
    try:
        if len(dataset) != 1:
            raise ValueError("The demonstration requires exactly one full-grid cutoff sample")
        sample = dataset[0]
    finally:
        dataset.close()

    grid = AffineGrid(tuple(float(v) for v in sample["affine_transform"].tolist()))
    shape = tuple(sample["burned_area"].shape[-2:])
    fuel_dir = data_root / "regions" / event / "fuel"
    ecology = EcologicalFuelMaps.from_fccs_rasters(
        fuel_dir / "total_available_fuel_loading_tons_per_acre_375m.tif",
        fuel_dir / "fuel_loading_lookup_coverage_fraction_375m.tif",
        grid=grid,
        expected_shape=shape,
    )
    # Unsupported, missing, and nonburnable reference classes receive an
    # explicitly declared scenario rather than an inferred measurement. The
    # fallback SAV 2000 ft^-1 equals 2000/0.3048 m^-1 and implies 11.52 s.
    fallback_sav_m_inv = 2000.0 / 0.3048
    residence = FlameResidenceTime.from_fbfm40_raster(
        fuel_dir / "landfire_2016_fbfm40_375m.tif",
        grid=grid,
        expected_shape=shape,
        epsg=int(sample["epsg"]),
        fallback_sav_m_inv=fallback_sav_m_inv,
    )
    combustion = ecology.combustion_parameters(
        heat_of_combustion_j_kg=18_000_000.0,
        burning_duration_s=residence.duration_s,
        consumed_fraction=0.10,
        fallback_fuel_load_kg_m2=10.0,
    )
    heat_model = WildfireHeatModel.from_checkpoint(
        checkpoint,
        grid=grid,
        combustion=combustion,
        radiative_fraction=0.30,
        emission_height_m=5.0,
        receiver_height_m=0.0,
        atmospheric_transmissivity=1.0,
        interval_s=3600.0,
        residence_time=residence,
        epsg=int(sample["epsg"]),
        device=device,
    )
    # The heat wrapper uses past arrival timing only for known already-burned
    # cells. The checkpoint predictor receives burned state/features and their
    # masks; it never receives arrivals or next-hour targets.
    inference_keys = (
        "burned_area", "features", "channel_names", "burned_area_valid",
        "feature_valid", "affine_transform", "epsg", "pixel_valid", "time_valid",
        "arrival_hours", "arrival_valid", "elapsed_hours", "event_t0_utc",
        "event_id", "time_utc",
    )
    inference_sample = {key: sample[key] for key in inference_keys if key in sample}
    result = heat_model.predict_sample_details(inference_sample)
    source_burned = sample["burned_area"][0, 0].numpy()
    source_known = sample["burned_area_valid"][0, 0].numpy()
    source_arrival = sample["arrival_hours"][0].numpy()
    source_arrival_valid = sample["arrival_valid"][0].numpy()
    elapsed_hours = float(sample["elapsed_hours"].item())
    bridge_timing = {
        "already_burned_mask": source_known & (source_burned == 1),
        "arrival_time_s": np.asarray(source_arrival, dtype=np.float64) * 3600.0,
        "current_time_s": elapsed_hours * 3600.0,
        "arrival_valid": source_arrival_valid,
    }
    # The regular API returns a prediction/coordinate tuple. Reuse the saved
    # probability map to demonstrate that interface without another model call.
    predicted_heat_w_m2, coordinates_latlon_deg = heat_model.predict_from_new_burn_probability(
        result.new_burn_probability, probability_valid=result.probability_valid,
        **bridge_timing,
    )
    np.testing.assert_allclose(predicted_heat_w_m2, result.expected_heat_flux_w_m2, equal_nan=True)

    uniform_model = WildfireHeatModel(
        heat_model.predictor,
        grid=grid,
        combustion=CombustionParameters(
            fuel_load_kg_m2=10.0,
            heat_of_combustion_j_kg=18_000_000.0,
            burning_duration_s=residence.duration_s,
            consumed_fraction=0.10,
        ),
        radiative_fraction=0.30,
        emission_height_m=5.0,
        interval_s=3600.0,
        residence_time=residence,
        epsg=int(sample["epsg"]),
    )
    uniform = uniform_model.predict_from_new_burn_probability_details(
        result.new_burn_probability, probability_valid=result.probability_valid,
        **bridge_timing,
    )
    # Only fuel loading changes in this comparison, so temporal occupancy and
    # its coverage must match even when the full radiant expectation is NaN.
    np.testing.assert_array_equal(uniform.active_burning_valid, result.active_burning_valid)
    np.testing.assert_allclose(uniform.mean_active_burning_probability,
                               result.mean_active_burning_probability, equal_nan=True)
    np.testing.assert_allclose(uniform.initial_remaining_burning_duration_s,
                               result.initial_remaining_burning_duration_s, equal_nan=True)
    arrays = {
        field.name: getattr(result, field.name)
        for field in fields(result)
        if isinstance(getattr(result, field.name), np.ndarray)
    }
    arrays.update(
        uniform_known_source_heat_flux_w_m2=uniform.known_source_heat_flux_w_m2,
        uniform_heat_flux_upper_bound_w_m2=uniform.heat_flux_upper_bound_w_m2,
        fuel_load_reference_mapped_mean_kg_m2=ecology.fuel_load_kg_m2,
        fuel_load_with_explicit_fallback_kg_m2=combustion.fuel_load_kg_m2,
        fuel_loading_coverage_fraction=ecology.coverage_fraction,
        fuel_loading_strict_valid=ecology.valid,
        flame_residence_duration_s=residence.duration_s,
        affine_transform=np.asarray(grid.transform),
        geographic_coordinates_latlon_deg=coordinates_latlon_deg,
        epsg=np.asarray(int(sample["epsg"])),
        source_burned_area=source_burned,
        source_burned_area_valid=source_known,
        source_arrival_hours=source_arrival,
        source_arrival_valid=source_arrival_valid,
        source_elapsed_hours=np.asarray(elapsed_hours),
        source_time_utc=sample["time_utc"].numpy(),
        source_event_t0_utc=np.asarray(sample["event_t0_utc"], dtype="U"),
        source_event_id=np.asarray(sample["event_id"], dtype="U"),
        source_feature_valid=sample["feature_valid"][0].numpy(),
        checkpoint_channel_names=np.asarray(contract["channels"], dtype="U"),
    )
    np.savez_compressed(output / "integrated_heat_arrays.npz", **arrays)

    cutoff_s = int(sample["time_utc"][0])
    input_ends = sample["source_interval_end_utc"][0].numpy()
    if np.any((input_ends >= 0) & (input_ends > cutoff_s)):
        raise ValueError("An environmental feature interval extends beyond the cutoff")
    known_new = result.new_burn_probability[result.probability_valid]
    flux_difference = result.known_source_heat_flux_w_m2 - uniform.known_source_heat_flux_w_m2
    training_config_path = checkpoint.parent / "configuration.json"
    training_split = None
    if training_config_path.exists():
        config = json.loads(training_config_path.read_text())
        # The event split location may vary between historical training runs.
        def find_split(value):
            if isinstance(value, dict):
                if event in value and value[event] in ("train", "validation", "test"):
                    return value[event]
                for nested in value.values():
                    answer = find_split(nested)
                    if answer is not None:
                        return answer
            if isinstance(value, list):
                for nested in value:
                    answer = find_split(nested)
                    if answer is not None:
                        return answer
            return None
        training_split = find_split(config)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_id": event,
        "training_event_split": training_split,
        "cutoff_utc": datetime.fromtimestamp(cutoff_s, timezone.utc).isoformat(),
        "forecast_interval_s": 3600.0,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "checkpoint_architecture": contract.get("architecture"),
        "checkpoint_best_epoch": int(saved["best_epoch"]),
        "checkpoint_channel_count": len(contract["channels"]),
        "device": device,
        "shape": list(shape),
        "epsg": int(sample["epsg"]),
        "affine_transform": list(grid.transform),
        "inference_input_keys": list(inference_keys),
        "inference_input_scope": "heat wrapper input; timing fields are used only after checkpoint inference",
        "new_burn_predictor_input_fields": [
            "burned_area", "features", "channel_names", "burned_area_valid", "feature_valid",
        ],
        "current_burned_state_provenance": {
            "arrival_surface_path": str(data_root / "regions" / event / "arrival_time_hours.tif"),
            "arrival_surface_sha256": _sha256(data_root / "regions" / event / "arrival_time_hours.tif"),
            "construction": "arrival_time_hours <= elapsed hours at cutoff, restricted by retrospective arrival validity",
            "event_t0_utc": sample["event_t0_utc"],
        },
        "input_feature_intervals_end_by_cutoff": True,
        "excluded_loader_fields": ["newly_burned_area", "arrival_std_hours", "arrival_std_valid"],
        "retrospective_input_limitation": (
            "Current burned-area input is reconstructed from retrospective arrival-time/final-extent data. "
            "Restricting tensor timestamps does not make this an operational live forecast validation."
        ),
        "forecast_scope": "Existing burning inferred from past point arrival and reference-fuel residence, plus predicted new-ignition radiation",
        "initial_active_burning_probability_supplied": False,
        "initial_active_burning_probability_derived_from_sample_arrivals": True,
        "initial_burning_scenario": {
            "rule": "known already-burned cell is active iff arrival_s <= cutoff_s < arrival_s + duration_s",
            "time_origin": sample["event_t0_utc"],
            "current_elapsed_hours": elapsed_hours,
            "unknown_age_policy": "unknown activity and remaining duration retained as NaN on known burned cells with missing arrivals",
            "missing_cumulative_state_policy": "existing burning included only on known already-burned support; zeros outside that support denote exclusion, not observed inactivity",
            "future_arrival_policy": "future and unburned arrival entries are ignored when inferring existing burning",
            "arrival_uncertainty": "retrospective nominal arrivals used; kriging standard deviations are not integrated",
            "interpretation": "deterministic point-scale front scenario, not observed active flames or coarse-cell traversal",
        },
        "known_initial_active_burning_cells": int(np.count_nonzero(
            result.initial_burning_valid & (result.initial_active_burning_probability > 0))),
        "known_extinguished_already_burned_cells": int(np.count_nonzero(
            bridge_timing["already_burned_mask"] & result.initial_burning_valid
            & (result.initial_active_burning_probability == 0))),
        "unknown_initial_burning_cells": int(np.count_nonzero(~result.initial_burning_valid)),
        "known_already_burned_cells_excluded_from_new_ignition": int(np.count_nonzero(source_known & (source_burned == 1))),
        "known_current_burn_state_cells": int(np.count_nonzero(source_known)),
        "known_new_ignition_probability_cells": int(np.count_nonzero(result.probability_valid)),
        "unknown_new_ignition_probability_cells": int(np.count_nonzero(~result.probability_valid)),
        "positive_known_new_ignition_cells": int(np.count_nonzero(known_new > 0)),
        "known_new_ignition_probability_sum": float(known_new.sum()),
        "complete_expected_flux_available": bool(result.complete),
        "missing_probability_policy": (
            "Unknown new-ignition probabilities remain NaN. Their nonnegative contribution is bounded by "
            "q=0 and q=1 under the specified arrival and combustion assumptions. Missing ages on known "
            "already-burned cells leave existing activity unresolved, bounded by remaining duration in [0,T]. "
            "Neither bound is an observed value."
        ),
        "known_source_heat_meaning": "Finite contribution from known new-ignition probabilities and known existing-burning scenarios; not the full expected heat field",
        "bound_scope": (
            "Supplied source grid only, with specified conditional source strength and ignition-time assumptions. "
            "Existing burning is restricted to known already-burned support; hidden existing fire under missing "
            "cumulative-state coverage and exterior fire sources are omitted."
        ),
        "fuel_source_provenance": ecology.provenance,
        "flame_residence_time_provenance": residence.provenance_dict(),
        "flame_residence_duration_s_statistics": _heat_stats(residence.duration_s),
        "fuel_cells_with_complete_lookup_coverage": int(np.count_nonzero(ecology.valid)),
        "fuel_coverage_fraction_statistics": _heat_stats(ecology.coverage_fraction),
        "illustrative_parameters": {
            "heat_of_combustion_j_kg": 18_000_000.0,
            "burning_duration_s": "per-cell FBFM40 characteristic-SAV residence, with explicit fallback scenario",
            "explicit_unsupported_sav_fallback_ft_inv": 2000.0,
            "explicit_unsupported_sav_fallback_m_inv": fallback_sav_m_inv,
            "explicit_unsupported_sav_fallback_duration_s": 11.52,
            "residence_spatial_assumption": "representative point-scale front duration assigned to each 375 m cell; no cell-traversal timing is inferred",
            "consumed_fraction": 0.10,
            "explicit_unmapped_fuel_fallback_kg_m2": 10.0,
            "radiative_fraction": 0.30,
            "emission_height_m": 5.0,
            "receiver_height_m": 0.0,
            "atmospheric_transmissivity": 1.0,
            "conditional_ignition_time": "Uniform over next hour given ignition occurs",
            "flaming_duration_limitation": "excludes smouldering, crown fire, reignition, and indefinite trailing combustion",
        },
        "matrix_statistics": {key: _heat_stats(value) for key, value in arrays.items()
                              if np.issubdtype(value.dtype, np.number) and value.shape == shape},
        "ecology_vs_uniform_identical_probability_comparison": {
            "uniform_loading_kg_m2": 10.0,
            "shared_inputs": "same new-burn probabilities, already-burned mask, past arrival times, cutoff, arrival validity, and per-cell residence durations",
            "maximum_absolute_known_source_flux_difference_w_m2": float(np.abs(flux_difference).max()),
            "mean_known_source_flux_difference_w_m2": float(flux_difference.mean()),
            "interpretation": "Sensitivity to reference spatial fuel loading; no measured accuracy improvement is established",
        },
        "pipeline_metadata": result.metadata,
        "validation_scope": "End-to-end inference and units/provenance demonstration; no measured wildfire heat-flux validation or calibration",
        "artifacts": ["integrated_heat_arrays.npz", "summary.json", "integrated_heat_demo.png"],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    _heat_plot(output / "integrated_heat_demo.png", arrays, summary["cutoff_utc"], event)
    return summary


def heat_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=heat_DEFAULT_CHECKPOINT)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--event", default=DEFAULT_EVENT)
    parser.add_argument("--cutoff-utc", default=DEFAULT_CUTOFF)
    parser.add_argument("--output", type=Path, default=WORKSPACE / "demonstration" / "heat" / "duration_aware_demo")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    summary = heat_run(checkpoint=args.checkpoint, data_root=args.data_root,
                  event=args.event, cutoff_utc=args.cutoff_utc,
                  output=args.output, device=args.device)
    print(json.dumps({key: summary[key] for key in (
        "event_id", "cutoff_utc", "shape", "known_new_ignition_probability_cells",
        "unknown_new_ignition_probability_cells", "complete_expected_flux_available",
        "known_initial_active_burning_cells", "known_extinguished_already_burned_cells",
        "unknown_initial_burning_cells", "flame_residence_duration_s_statistics",
        "ecology_vs_uniform_identical_probability_comparison",
    )}, indent=2, allow_nan=False))




# Active flame example
# Export modeled surface-flame positions using an existing event/checkpoint.
# 
# Forecasting uses current-state/environment inputs only. A separate, explicitly
# retrospective calculation uses reconstructed point-arrival times. Both are fuel
# and timing scenarios, not validated observations of currently visible flames.


import csv


from wildfire.heat import FlamePositions
from wildfire.heat import active_flames_from_arrival



def _flames_stats(values):
    known = np.asarray(values)[np.isfinite(values)]
    return {
        "finite_cells": int(known.size),
        "minimum": float(known.min()) if known.size else None,
        "median": float(np.median(known)) if known.size else None,
        "maximum": float(known.max()) if known.size else None,
    }


def _csv(path, positions, *, epsg, timestamp, fallback_mask):
    from pyproj import Transformer

    transform = Transformer.from_crs(epsg, 4326, always_xy=True)
    xy = positions.coordinates_xy_m
    if len(xy):
        longitude, latitude = transform.transform(xy[:, 0], xy[:, 1])
    else:
        longitude, latitude = [], []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("row", "column", "x_m", "y_m", "epsg", "longitude", "latitude",
                         "modeled_active_probability", "query_time_utc", "residence_uses_fallback_scenario"))
        for (row, column), (x, y), p, lon, lat in zip(
            positions.cells_rc, xy, positions.probabilities, longitude, latitude,
        ):
            writer.writerow((row, column, x, y, epsg, lon, lat, p, timestamp,
                             bool(fallback_mask[row, column])))


def _flames_plot(path, current, forecast, duration, *, event, cutoff, endpoint):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(16, 6), constrained_layout=True)
    panels = (
        (duration, "Fuel-model point residence", "Seconds", "magma", None),
        (np.where(current.valid, current.probability, np.nan),
         f"Nominal arrival scenario at {cutoff}", "Modeled activity indicator", "viridis", 1.0),
        (forecast.endpoint.probability,
         f"New-ignition flame probability at {endpoint}", "Modeled probability", "viridis", None),
    )
    for axis, (matrix, title, unit, cmap, vmax) in zip(axes, panels):
        palette = plt.get_cmap(cmap).copy()
        palette.set_bad("#bdbdbd")
        image = axis.imshow(np.ma.masked_invalid(matrix), cmap=palette, vmin=0, vmax=vmax,
                            interpolation="nearest")
        axis.set(title=title, xlabel="Column (375 m cells)", ylabel="Row (375 m cells)")
        fig.colorbar(image, ax=axis, label=unit, shrink=0.75)
    fig.suptitle(
        f"{event}\nSurface-flame scenarios at grid centers; gray is unknown; "
        "arrival uncertainty is not resolved", fontsize=12,
    )
    fig.savefig(path, dpi=170)
    plt.close(fig)


def flames_run(
    *, checkpoint=heat_DEFAULT_CHECKPOINT, data_root=DATA_ROOT, event=DEFAULT_EVENT,
    cutoff_utc=DEFAULT_CUTOFF, output=None, device="cpu", min_probability=0.001,
    fallback_sav_ft_inv=2000.0,
) -> dict:
    """Run one saved-model snapshot and preserve source/assumption metadata.

    The explicit SAV fallback is a scenario for cells lacking a burnable FBFM40
    class (including NB98/NB99). It is not a conversion of nonburnable classes
    into observed fuel. Position exports identify every such selected cell.
    """
    import rasterio
    from wildfire import load_model

    output = Path(output or WORKSPACE / "demonstration" / "heat" / "active_flame_demo").resolve()
    output.mkdir(parents=True, exist_ok=True)
    data_root = resolve_recorded_path(data_root).resolve()
    model = load_model(checkpoint, device=device)
    with model.load_data(
        data_root, events=[event], sequence_length=1,
        time_range=(cutoff_utc, cutoff_utc), daily_policy="completed_day",
    ) as dataset:
        if len(dataset) != 1:
            raise ValueError("The active-flame example needs exactly one full-grid cutoff snapshot")
        sample = dataset[0]
    grid = AffineGrid(tuple(sample["affine_transform"].numpy()))
    shape = tuple(sample["burned_area"].shape[-2:])
    epsg = int(sample["epsg"])
    fuel_path = data_root / "regions" / event / "fuel" / "landfire_2016_fbfm40_375m.tif"
    with rasterio.open(fuel_path) as source:
        if source.shape != shape or tuple(source.transform)[:6] != grid.transform:
            raise ValueError("FBFM40 raster does not match the model grid")
        if source.crs is None or source.crs.to_epsg() != epsg or not source.crs.is_projected:
            raise ValueError("FBFM40 CRS must match the model's projected CRS")
        if source.crs.linear_units_factor[1] != 1.0:
            raise ValueError("FBFM40 grid coordinates must be in metres")
        codes = source.read(1, masked=True).astype(float).filled(np.nan)
    residence = FlameResidenceTime.from_fbfm40(
        codes, fallback_sav_m_inv=fallback_sav_ft_inv / 0.3048,
    )
    burnable_codes = tuple(
        code for first, last in ((101, 109), (121, 124), (141, 149),
                                (161, 165), (181, 189), (201, 204))
        for code in range(first, last + 1)
    )
    fallback_mask = ~np.isin(codes, burnable_codes)
    # No arrival or future-label fields enter checkpoint forecasting.
    inference_keys = ("burned_area", "features", "channel_names", "burned_area_valid",
                      "feature_valid", "affine_transform", "epsg", "time_utc", "time_valid")
    forecast = model.predict_active_flames_sample(
        {key: sample[key] for key in inference_keys}, residence_time=residence,
    )
    # This second computation explicitly opts into retrospective arrival data.
    arrival_valid = sample["arrival_valid"][0].numpy()
    arrival_s = sample["arrival_hours"][0].numpy().astype(float) * 3600.0
    arrival_s[~arrival_valid] = np.nan
    elapsed_s = float(sample["elapsed_hours"][0]) * 3600.0
    current = active_flames_from_arrival(
        arrival_s, residence, elapsed_s, grid=grid, arrival_valid=arrival_valid,
    )
    nominal_positions = current.positions(min_probability=1.0)
    candidates = forecast.endpoint.positions(min_probability=min_probability)
    positive = forecast.endpoint.positions(min_probability=np.nextafter(0.0, 1.0))
    order = np.argsort(-positive.probabilities, kind="stable")
    ranked = FlamePositions(positive.cells_rc[order], positive.coordinates_xy_m[order], positive.probabilities[order])
    cutoff_s = int(sample["time_utc"][0])
    cutoff = datetime.fromtimestamp(cutoff_s, timezone.utc).isoformat()
    endpoint = datetime.fromtimestamp(cutoff_s + 3600, timezone.utc).isoformat()
    _csv(output / "nominal_current_positions.csv", nominal_positions, epsg=epsg,
         timestamp=cutoff, fallback_mask=fallback_mask)
    _csv(output / "forecast_endpoint_candidates.csv", candidates, epsg=epsg,
         timestamp=endpoint, fallback_mask=fallback_mask)
    _csv(output / "forecast_probability_locations.csv", ranked, epsg=epsg,
         timestamp=endpoint, fallback_mask=fallback_mask)
    std_valid = sample["arrival_std_valid"][0].numpy()
    std_hours = np.where(std_valid, sample["arrival_std_hours"][0].numpy(), np.nan)
    np.savez_compressed(
        output / "active_flame_arrays.npz",
        residence_duration_s=residence.duration_s, fuel_model_codes=codes,
        residence_fallback_mask=fallback_mask, arrival_time_s=arrival_s,
        arrival_valid=arrival_valid, arrival_std_hours=std_hours,
        nominal_current_activity=current.probability, nominal_remaining_duration_s=current.remaining_duration_s,
        new_burn_probability=forecast.new_burn_probability,
        forecast_probability_valid=forecast.valid,
        mean_active_probability=forecast.mean_active_probability,
        endpoint_active_probability=forecast.endpoint.probability,
        affine_transform=np.asarray(grid.transform), epsg=epsg,
    )
    summary = {
        "event_id": event, "cutoff_utc": cutoff, "endpoint_utc": endpoint,
        "shape": list(shape), "epsg": epsg, "cell_area_m2": grid.cell_area_m2,
        "checkpoint": str(model.checkpoint_path), "checkpoint_sha256": model.checkpoint_sha256,
        "inference_input_keys": list(inference_keys),
        "residence_time": residence.provenance_dict(),
        "fuel_raster": str(fuel_path),
        "fuel_raster_sha256": hashlib.sha256(fuel_path.read_bytes()).hexdigest(),
        "fuel_reference_epoch": 2016,
        "fuel_class_aggregation": "modal native LANDFIRE class in each 375 m cell",
        "fallback_sav_ft_inv": fallback_sav_ft_inv,
        "residence_fallback_cells": int(fallback_mask.sum()),
        "residence_duration_s": _flames_stats(residence.duration_s),
        "nominal_current_active_locations": int(len(nominal_positions.cells_rc)),
        "nominal_arrival_valid_locations": int(arrival_valid.sum()),
        "arrival_kriging_std_hours": _flames_stats(std_hours),
        "forecast_endpoint_probability": _flames_stats(forecast.endpoint.probability),
        "forecast_selected_candidates": int(len(candidates.cells_rc)),
        "forecast_positive_probability_locations": int(len(ranked.cells_rc)),
        "forecast_selected_fallback_candidates": int(fallback_mask[tuple(candidates.cells_rc.T)].sum()),
        "candidate_selection_min_probability": min_probability,
        "forecast_metadata": forecast.metadata,
        "limitations": [
            "Retrospective reconstructed arrivals are not observed exact flaming onsets.",
            "Arrival uncertainty is much greater than point flaming residence; the nominal indicator is a scenario.",
            "Forecast probabilities add uniform within-hour arrival and reference-fuel residence assumptions.",
            "These grid centers are not observed flame coordinates or subcell flame-front geometry.",
            "Main-front residence excludes smoldering and does not guarantee extinction of all trailing flames.",
            "A selected probability threshold is not evidence of calibrated active-flame detection skill.",
            "Ongoing flames are excluded from the new-ignition forecast; the nominal current calculation is separate.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    _flames_plot(output / "active_flame_maps.png", current, forecast, residence.duration_s,
          event=event, cutoff=cutoff, endpoint=endpoint)
    return summary


def flames_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=heat_DEFAULT_CHECKPOINT)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--event", default=DEFAULT_EVENT)
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-probability", type=float, default=0.001)
    parser.add_argument("--fallback-sav-ft-inv", type=float, default=2000.0)
    args = parser.parse_args()
    summary = flames_run(checkpoint=args.checkpoint, data_root=args.data_root, event=args.event,
                  cutoff_utc=args.cutoff, output=args.output, device=args.device,
                  min_probability=args.min_probability, fallback_sav_ft_inv=args.fallback_sav_ft_inv)
    print(json.dumps(summary, indent=2, allow_nan=False))


