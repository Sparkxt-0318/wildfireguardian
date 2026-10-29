"""Reproduce a saved wildfire forecast with ecological radiant-heat maps.

The example uses an existing checkpoint and an existing retrospective event
bundle. It does not train, download data, or use next-hour labels in inference.
Its combustion and missing-fuel fallback parameters are illustrative.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from .ecology import EcologicalFuelMaps
from .model import AffineGrid, CombustionParameters
from .pipeline import WildfireHeatModel


WORKSPACE = Path(__file__).resolve().parents[1]
DATA_ROOT = WORKSPACE / "wildfire_burned_area_hourly" / "environmental_data"
DEFAULT_CHECKPOINT = (
    WORKSPACE / "wildfire_burned_area_hourly" / "probability_model"
    / "training_runs" / "20261007_1h_direct_convolution_signed" / "5x5"
    / "fitted" / "checkpoint.pt"
)
DEFAULT_EVENT = "WY-BTF-002416_FishCreek"
DEFAULT_CUTOFF = "2024-08-23T00:00:00Z"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stats(values: np.ndarray) -> dict:
    finite = np.asarray(values)[np.isfinite(values)]
    return {
        "finite_cells": int(finite.size),
        "unknown_cells": int(np.asarray(values).size - finite.size),
        "minimum": float(finite.min()) if finite.size else None,
        "maximum": float(finite.max()) if finite.size else None,
        "mean": float(finite.mean()) if finite.size else None,
        "sum": float(finite.sum()) if finite.size else None,
    }


def _plot(path: Path, arrays: dict, cutoff: str, event: str) -> None:
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
    mask = arrays["probability_valid"]
    q = np.ma.array(arrays["new_burn_probability"], mask=~mask)
    mean_active = np.ma.array(arrays["mean_active_burning_probability"], mask=~mask)
    known = arrays["known_source_heat_flux_w_m2"]
    uniform = arrays["uniform_known_source_heat_flux_w_m2"]
    difference = known - uniform
    panels = [
        (q, "Predicted new burning within next hour", "Probability", "viridis", 0, 1),
        (arrays["fuel_load_with_explicit_fallback_kg_m2"],
         "FCCS reference fuel with explicit fallback", "Dry fuel load (kg/m²)", "YlGn", 0, None),
        (mean_active, "Mean occupancy from new ignitions", "Active-burning probability", "viridis", 0, None),
        (known, "Known-source expected mean radiant flux", "Incident radiant flux (W/m²)", "inferno", 0, None),
        (arrays["heat_flux_upper_bound_w_m2"],
         "Upper bound allowing unknown ignition q ≤ 1", "Incident radiant flux (W/m²)", "inferno", 0, None),
        (difference, "Ecological minus uniform-fuel contribution", "Flux difference (W/m²)", "RdBu_r", None, None),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 10), constrained_layout=True)
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
        "New-ignition radiation only; gray probability cells are unknown; "
        "upper bound is not an expected estimate",
        fontsize=13,
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(
    *,
    checkpoint: Path = DEFAULT_CHECKPOINT,
    data_root: Path = DATA_ROOT,
    event: str = DEFAULT_EVENT,
    cutoff_utc: str = DEFAULT_CUTOFF,
    output: Path | None = None,
    device: str = "cpu",
) -> dict:
    """Run one cutoff snapshot, retaining unknown coverage and assumptions."""
    import torch

    from wildfire_burned_area_hourly.pytorch_loader import WildfireSequenceDataset

    checkpoint = Path(checkpoint).expanduser().resolve()
    data_root = Path(data_root).expanduser().resolve()
    output = Path(output or Path(__file__).parent / "outputs" / "integrated_demo").resolve()
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
    combustion = ecology.combustion_parameters(
        heat_of_combustion_j_kg=18_000_000.0,
        burning_duration_s=300.0,
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
        device=device,
    )
    # These are the only inputs passed into forecasting. The loader also
    # exposes retrospective labels/arrival fields; they are not supplied.
    inference_keys = ("burned_area", "features", "channel_names", "burned_area_valid", "feature_valid", "affine_transform")
    inference_sample = {key: sample[key] for key in inference_keys}
    result = heat_model.predict_sample(inference_sample)

    uniform_model = WildfireHeatModel(
        heat_model.predictor,
        grid=grid,
        combustion=CombustionParameters(
            fuel_load_kg_m2=10.0,
            heat_of_combustion_j_kg=18_000_000.0,
            burning_duration_s=300.0,
            consumed_fraction=0.10,
        ),
        radiative_fraction=0.30,
        emission_height_m=5.0,
        interval_s=3600.0,
    )
    uniform = uniform_model.predict_from_new_burn_probability(
        result.new_burn_probability, probability_valid=result.probability_valid,
    )
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
        affine_transform=np.asarray(grid.transform),
        source_burned_area=sample["burned_area"][0, 0].numpy(),
        source_burned_area_valid=sample["burned_area_valid"][0, 0].numpy(),
        source_feature_valid=sample["feature_valid"][0].numpy(),
        checkpoint_channel_names=np.asarray(contract["channels"], dtype="U"),
    )
    np.savez_compressed(output / "integrated_heat_arrays.npz", **arrays)

    cutoff_s = int(sample["time_utc"][0])
    input_ends = sample["source_interval_end_utc"][0].numpy()
    if np.any((input_ends >= 0) & (input_ends > cutoff_s)):
        raise ValueError("An environmental feature interval extends beyond the cutoff")
    source_known = arrays["source_burned_area_valid"]
    source_burned = arrays["source_burned_area"]
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
        "current_burned_state_provenance": {
            "arrival_surface_path": str(data_root / "regions" / event / "arrival_time_hours.tif"),
            "arrival_surface_sha256": _sha256(data_root / "regions" / event / "arrival_time_hours.tif"),
            "construction": "arrival_time_hours <= elapsed hours at cutoff, restricted by retrospective arrival validity",
            "event_t0_utc": sample["event_t0_utc"],
        },
        "input_feature_intervals_end_by_cutoff": True,
        "excluded_loader_fields": ["newly_burned_area", "arrival_hours", "arrival_std_hours"],
        "retrospective_input_limitation": (
            "Current burned-area input is reconstructed from retrospective arrival-time/final-extent data. "
            "Restricting tensor timestamps does not make this an operational live forecast validation."
        ),
        "forecast_scope": "New-ignition radiation contribution only; currently active existing fires are not supplied",
        "initial_active_burning_probability_supplied": False,
        "known_already_burned_cells_excluded_from_new_ignition": int(np.count_nonzero(source_known & (source_burned == 1))),
        "known_current_burn_state_cells": int(np.count_nonzero(source_known)),
        "known_new_ignition_probability_cells": int(np.count_nonzero(result.probability_valid)),
        "unknown_new_ignition_probability_cells": int(np.count_nonzero(~result.probability_valid)),
        "positive_known_new_ignition_cells": int(np.count_nonzero(known_new > 0)),
        "known_new_ignition_probability_sum": float(known_new.sum()),
        "complete_expected_flux_available": bool(result.complete),
        "missing_probability_policy": (
            "Unknown new-ignition probabilities remain NaN. Their nonnegative contribution is bounded by "
            "q=0 and q=1 under the specified arrival and combustion assumptions. Neither bound is an observed value."
        ),
        "known_source_heat_meaning": "Finite contribution from known source probabilities only; not the full expected heat field",
        "bound_scope": "Supplied source grid only, with specified conditional source strength and ignition-time assumptions; exterior fire sources omitted",
        "fuel_source_provenance": ecology.provenance,
        "fuel_cells_with_complete_lookup_coverage": int(np.count_nonzero(ecology.valid)),
        "fuel_coverage_fraction_statistics": _stats(ecology.coverage_fraction),
        "illustrative_parameters": {
            "heat_of_combustion_j_kg": 18_000_000.0,
            "burning_duration_s": 300.0,
            "consumed_fraction": 0.10,
            "explicit_unmapped_fuel_fallback_kg_m2": 10.0,
            "radiative_fraction": 0.30,
            "emission_height_m": 5.0,
            "receiver_height_m": 0.0,
            "atmospheric_transmissivity": 1.0,
            "conditional_ignition_time": "Uniform over next hour given ignition occurs",
        },
        "matrix_statistics": {key: _stats(value) for key, value in arrays.items()
                              if np.issubdtype(value.dtype, np.number) and value.shape == shape},
        "ecology_vs_uniform_identical_probability_comparison": {
            "uniform_loading_kg_m2": 10.0,
            "maximum_absolute_known_source_flux_difference_w_m2": float(np.abs(flux_difference).max()),
            "mean_known_source_flux_difference_w_m2": float(flux_difference.mean()),
            "interpretation": "Sensitivity to reference spatial fuel loading; no measured accuracy improvement is established",
        },
        "pipeline_metadata": result.metadata,
        "validation_scope": "End-to-end inference and units/provenance demonstration; no measured wildfire heat-flux validation or calibration",
        "artifacts": ["integrated_heat_arrays.npz", "summary.json", "integrated_heat_demo.png"],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    _plot(output / "integrated_heat_demo.png", arrays, summary["cutoff_utc"], event)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--event", default=DEFAULT_EVENT)
    parser.add_argument("--cutoff-utc", default=DEFAULT_CUTOFF)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "outputs" / "integrated_demo")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    summary = run(checkpoint=args.checkpoint, data_root=args.data_root,
                  event=args.event, cutoff_utc=args.cutoff_utc,
                  output=args.output, device=args.device)
    print(json.dumps({key: summary[key] for key in (
        "event_id", "cutoff_utc", "shape", "known_new_ignition_probability_cells",
        "unknown_new_ignition_probability_cells", "complete_expected_flux_available",
        "ecology_vs_uniform_identical_probability_comparison",
    )}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
