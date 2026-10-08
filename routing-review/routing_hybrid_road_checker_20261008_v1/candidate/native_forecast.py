"""Run the original one-hour predictor safely on original or portable inputs.

No training or altered eligibility. Checkpoints use the original weights_only
loaders. Portable inputs are numeric derivatives of the original raster loader,
not forecast simulations. Their current-state provenance stays retrospective.
"""
from __future__ import annotations

import argparse
import dataclasses
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

DEFAULT_CUTOFFS = ("2022-03-04T03:00:00Z", "2022-03-04T06:00:00Z", "2022-03-04T12:00:00Z")


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _runtime(mentor_root=None):
    root = Path(mentor_root) if mentor_root else Path(__file__).resolve().parent / "mentor_runtime"
    if not (root / "wildfire_burned_area_hourly" / "api.py").exists():
        raise FileNotFoundError("original model runtime missing: " + str(root))
    sys.path.insert(0, str(root))
    import torch
    torch.set_num_threads(1)
    from wildfire_burned_area_hourly.api import load_model
    from expected_heat_flux import AffineGrid, CombustionParameters, WildfireHeatModel
    return torch, load_model, AffineGrid, CombustionParameters, WildfireHeatModel


def _support_diagnosis(model, sample, prediction):
    """Reproduce the original masks, reporting disjoint rejection causes."""
    import torch.nn.functional as F
    p = model.predictor
    burn = sample["burned_area"]
    bv = sample["burned_area_valid"]
    feat = sample["features"]
    fv = sample["feature_valid"]
    _, env_complete = p.model._features((feat - p.mean) / p.std, fv, "unknown")
    contact, known = p._contact(burn, bv)
    radius = p.model.kernel_size // 2
    h, w = burn.shape[-2:]
    source = F.pad(known.to(feat.dtype).reshape(-1,1,h,w), (radius,) * 4, value=0.0)
    source_complete = (F.avg_pool2d(source, p.model.kernel_size, stride=1) == 1).reshape_as(burn)
    burned = known & (burn == 1)
    unburned = known & (burn == 0)
    cases = {
        "unknown_current_label_or_outside_final_reconstruction": ~known,
        "known_burned_probability_zero_override": burned,
        "known_unburned_environment_context_incomplete": unburned & ~env_complete,
        "known_unburned_burned_context_incomplete": unburned & env_complete & ~source_complete,
        "known_unburned_no_burned_neighbor_eligibility": unburned & env_complete & source_complete & ~contact,
        "known_unburned_eligible": unburned & env_complete & source_complete & contact,
    }
    masks = {key: value[0,0].detach().cpu().numpy() for key, value in cases.items()}
    expected = burned | (unburned & env_complete & source_complete & contact)
    original_valid = prediction.valid
    exact_match = bool((expected == original_valid).all())
    if not exact_match:
        raise ValueError("diagnostic masks failed to reproduce original valid mask")
    counts = {key: int(value.sum()) for key, value in masks.items()}
    counts.update(total_cells=int(h*w), probability_valid=int(original_valid.sum()),
                  diagnostic_validity_exact_match=exact_match,
                  all_disjoint_categories_cover_grid=bool(sum(counts.values()) == h*w),
                  environment_context_complete_cells=int(env_complete.sum()),
                  burned_context_complete_cells=int(source_complete.sum()),
                  burned_neighbor_contact_cells=int(contact.sum()),
                  physically_nonemitting_mask_supplied=False,
                  checkpoint_eligibility=model.contract.get("eligibility"))
    counts["feature_missing_cells_by_channel"] = {
        name: int((~sample["feature_valid"][0,j]).sum()) for j,name in enumerate(sample["channel_names"])
    }
    return counts, masks


def _forecast(model, sample, base_metadata, output_path, runtime):
    _, _, AffineGrid, CombustionParameters, WildfireHeatModel = runtime
    started = time.perf_counter()
    prediction = model.predict_sample(sample)
    inference_seconds = time.perf_counter() - started
    support, diagnostic_masks = _support_diagnosis(model, sample, prediction)
    transform = tuple(float(x) for x in np.asarray(sample["affine_transform"]))
    heat = WildfireHeatModel(
        model.predictor, grid=AffineGrid(transform),
        combustion=CombustionParameters(fuel_load_kg_m2=10.0, heat_of_combustion_j_kg=18000000.0,
                                        burning_duration_s=300.0, consumed_fraction=0.10),
        radiative_fraction=0.30, emission_height_m=5.0, receiver_height_m=0.0,
        atmospheric_transmissivity=1.0, interval_s=3600.0,
    )
    started = time.perf_counter()
    result = heat.predict_sample(sample)
    expected_heat_seconds = time.perf_counter() - started
    arrays = {f.name: getattr(result, f.name) for f in dataclasses.fields(result)
              if isinstance(getattr(result, f.name), np.ndarray)}
    def numeric(value):
        return value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)
    arrays.update(source_burned_area=numeric(sample["burned_area"])[0,0],
                  source_burned_area_valid=numeric(sample["burned_area_valid"])[0,0],
                  affine_transform=np.asarray(transform),
                  original_raw_score=numeric(prediction.raw_score)[0,0],
                  **{"diagnosis_" + key: value for key,value in diagnostic_masks.items()})
    cutoff_s = int(np.asarray(sample["time_utc"])[0])
    ends = np.asarray(sample["source_interval_end_utc"])
    if np.any((ends >= 0) & (ends > cutoff_s)):
        raise ValueError("feature interval extends beyond cutoff")
    row = dict(base_metadata,
               status="NATIVE_INFERENCE_COMPLETED", evidence="DEVELOPMENT_INFERENCE_ONLY",
               generated_at_utc=datetime.now(timezone.utc).isoformat(),
               cutoff_utc=datetime.fromtimestamp(cutoff_s, timezone.utc).isoformat().replace("+00:00", "Z"),
               shape=list(arrays["new_burn_probability"].shape), epsg=int(sample["epsg"]),
               affine_transform=list(transform), checkpoint_sha256=model.checkpoint_sha256,
               checkpoint_architecture=model.contract["architecture"], checkpoint_contract=model.contract,
               checkpoint_loading="original torch.load(weights_only=True); no unsafe pickle fallback",
               initial_active_burning_probability_supplied=False,
               complete_expected_flux_available=bool(result.complete),
               known_probability_cells=int(result.probability_valid.sum()),
               unknown_probability_cells=int((~result.probability_valid).sum()),
               finite_expected_flux_cells=int(np.isfinite(result.expected_heat_flux_w_m2).sum()),
               known_burned_cells=int(((arrays["source_burned_area"] == 1) & arrays["source_burned_area_valid"]).sum()),
               input_feature_intervals_end_by_cutoff=True,
               target="next-hour threshold crossing of retrospectively reconstructed kriging arrival; hypothetical ignition mapping only in research mode",
               calibration="not established for these Uljin development inputs; original clipped signed evaluation score",
               current_state="retrospective final-perimeter/full-history reconstructed arrival state; not live cutoff evidence",
               metadata=result.metadata, support_diagnosis=support,
               inference_seconds=inference_seconds, expected_heat_seconds=expected_heat_seconds)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **arrays)
    row["native_snapshot_sha256"] = _hash(output_path)
    output_path.with_suffix(".json").write_text(json.dumps(row, indent=2, allow_nan=False))
    return row


def export_original_snapshots(*, mentor_root, data_root, checkpoint, output_dir, input_dir=None, cutoffs=DEFAULT_CUTOFFS):
    """Actual original raster loader + original predictor, without retraining."""
    runtime = _runtime(mentor_root)
    _, load_model, *_ = runtime
    started = time.perf_counter()
    model = load_model(checkpoint, device="cpu")
    model_seconds = time.perf_counter() - started
    rows = []
    for cutoff in cutoffs:
        started = time.perf_counter()
        with model.load_data(data_root, events=["KFS_02"], sequence_length=1,
                             time_range=(cutoff, cutoff), daily_policy="completed_day") as dataset:
            if len(dataset) != 1:
                raise ValueError("expected one original cutoff sample")
            sample = dataset[0]
            state = dataset._events[0]
            sources = [Path(data_root)/state["info"]["arrival_path"]]
            sources.extend(layer.path for layer in state["layers"].values())
        loading_seconds = time.perf_counter() - started
        # Never export or consume next-hour outcomes for query/parameter selection.
        keys = ("burned_area", "features", "burned_area_valid", "feature_valid",
                "affine_transform", "time_utc", "source_interval_end_utc", "source_interval_start_utc", "epsg")
        inference = {key:sample[key] for key in keys}
        inference["channel_names"] = sample["channel_names"]
        stem = cutoff.replace("-", "").replace(":", "")
        base = {"event_id":"KFS_02", "cutoff_utc":cutoff,
                "input_origin":"original model-bound raster loader",
                "source_input_hashes":{str(path.relative_to(data_root)): _hash(path) for path in sources},
                "model_loading_seconds":model_seconds, "input_loading_seconds":loading_seconds}
        if input_dir:
            path = Path(input_dir)/ (stem + ".npz")
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, **{key:sample[key].detach().cpu().numpy() for key in keys})
            base["portable_input_sha256"] = _hash(path)
            path.with_suffix(".json").write_text(json.dumps(dict(base, channel_names=list(sample["channel_names"])), indent=2))
        row = _forecast(model, inference, base, Path(output_dir)/(stem + ".npz"), runtime)
        rows.append(row)
    Path(output_dir, "SUMMARY.json").write_text(json.dumps(rows, indent=2, allow_nan=False))
    return rows


def predict_numeric_input(input_path, checkpoint, output_path, *, metadata_path=None, mentor_root=None):
    """Portable original inference on preserved numeric input arrays."""
    runtime = _runtime(mentor_root)
    torch, load_model, *_ = runtime
    started = time.perf_counter()
    model = load_model(checkpoint, device="cpu")
    model_seconds = time.perf_counter() - started
    started = time.perf_counter()
    path = Path(input_path)
    mdpath = Path(metadata_path) if metadata_path else path.with_suffix(".json")
    metadata = json.loads(mdpath.read_text())
    if metadata.get("portable_input_sha256") != _hash(path):
        raise ValueError("portable input checksum differs from provenance")
    with np.load(path, allow_pickle=False) as packet:
        sample = {key:torch.from_numpy(packet[key].copy()) for key in packet.files}
    sample["channel_names"] = metadata["channel_names"]
    metadata.update(input_origin="numeric derivative of original model-bound raster input",
                    model_loading_seconds=model_seconds, input_loading_seconds=time.perf_counter()-started)
    return _forecast(model, sample, metadata, output_path, runtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentor-root")
    parser.add_argument("--data-root")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--input", help="portable original numeric input NPZ")
    parser.add_argument("--out", required=True)
    parser.add_argument("--input-out")
    parser.add_argument("--cutoff", action="append")
    args = parser.parse_args()
    if args.input:
        rows = [predict_numeric_input(args.input, args.checkpoint, args.out, mentor_root=args.mentor_root)]
    else:
        if not args.mentor_root or not args.data_root:
            parser.error("original raster mode requires --mentor-root and --data-root")
        rows = export_original_snapshots(mentor_root=args.mentor_root, data_root=args.data_root,
                                        checkpoint=args.checkpoint, output_dir=args.out, input_dir=args.input_out,
                                        cutoffs=args.cutoff or DEFAULT_CUTOFFS)
    print(json.dumps([{key:row.get(key) for key in ("status", "cutoff_utc", "known_probability_cells", "unknown_probability_cells", "inference_seconds")} for row in rows], indent=2))


if __name__ == "__main__":
    main()
