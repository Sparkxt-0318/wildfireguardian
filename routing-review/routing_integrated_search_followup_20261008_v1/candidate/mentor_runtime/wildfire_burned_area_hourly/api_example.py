"""Load a saved model, predict one real snapshot, and optionally compute radiant heat.

Run from the workspace with ``python -m wildfire_burned_area_hourly.api_example``.
Data/checkpoint arguments are explicit overrides for a wheel installation. The
optional heat example uses illustrative uniform fuel and combustion parameters.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from . import load_model
from .pytorch_loader.dataset import DEFAULT_ROOT


DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parent / "probability_model/training_runs"
    / "20261007_1h_direct_convolution_signed/5x5/fitted/checkpoint.pt"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--event", default="WY-BTF-002416_FishCreek")
    parser.add_argument("--cutoff-utc", default="2024-08-23T00:00:00Z")
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--heat", action="store_true", help="Add illustrative radiant heat and coverage bounds")
    parser.add_argument("--output", type=Path, help="Save arrays to a new NPZ file")
    args = parser.parse_args()
    model = load_model(args.checkpoint, device=args.device)
    with model.load_data(args.data_root, events=[args.event], sequence_length=1,
                         time_range=(args.cutoff_utc, args.cutoff_utc)) as dataset:
        if len(dataset) != 1:
            raise ValueError("The example requires exactly one full-grid cutoff snapshot")
        sample = dataset[0]
    prediction = model.predict_sample(sample)
    arrays = {name: getattr(prediction, name).cpu().numpy()
              for name in prediction.__dataclass_fields__}
    known = arrays["probability"][arrays["valid"]]
    summary = {
        "event_id": args.event, "cutoff_utc": args.cutoff_utc, "family": model.family,
        "device": str(model.device), "channels": list(model.channel_names),
        "probability_shape": list(arrays["probability"].shape),
        "known_predictions": int(arrays["valid"].sum()),
        "unknown_predictions": int((~arrays["valid"]).sum()),
        "minimum_known_probability": float(known.min()) if known.size else None,
        "maximum_known_probability": float(known.max()) if known.size else None,
    }
    if args.heat:
        from expected_heat_flux import AffineGrid, CombustionParameters

        # Uniform fuel and the physical numbers below are illustrative assumptions.
        heat = model.heat_model(
            grid=AffineGrid(tuple(sample["affine_transform"].tolist())),
            combustion=CombustionParameters(fuel_load_kg_m2=1.0,
                                            heat_of_combustion_j_kg=18_000_000.0,
                                            burning_duration_s=120.0),
            radiative_fraction=0.3, emission_height_m=5.0,
        ).predict_sample(sample)
        for name in heat.__dataclass_fields__:
            value = getattr(heat, name)
            if isinstance(value, np.ndarray):
                arrays["heat_" + name] = value
        summary.update(complete_expected_heat_available=heat.complete,
                       heat_flux_units="W/m2", incident_energy_units="J/m2",
                       heat_parameters="illustrative uniform fuel and combustion")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        summary["saved_arrays"] = str(args.output.resolve())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
