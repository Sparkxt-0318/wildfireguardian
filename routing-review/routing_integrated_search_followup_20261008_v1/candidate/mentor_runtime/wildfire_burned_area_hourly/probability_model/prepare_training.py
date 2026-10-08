"""Prepare strictly paired one-hour targets with weighted negative sampling.

All positive targets are retained before environmental validity filtering.
Negative targets are sampled without replacement within fire/contact strata;
their inverse inclusion probabilities preserve the cell-hour population loss.
The raw source rasters are never modified.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import minimum_filter

from ..pytorch_loader import WildfireSequenceDataset
from ..pytorch_loader.dataset import DEFAULT_ROOT
from .input_schema import CHANNELS, TRAINING_SOURCE_CHANNELS




def resolve_channel_schema(root, source_channels=TRAINING_SOURCE_CHANNELS):
    """Freeze the loader's expanded inputs and published categorical legend."""
    dataset = WildfireSequenceDataset(root, sequence_length=1, channels=source_channels,
                                      categorical_encoding="one_hot")
    try:
        return dict(
            source_channels=list(dataset.source_channel_names),
            channels=list(dataset.channel_names),
            channel_info=list(dataset.channel_info),
            categorical_encoding="one_hot",
            categorical_classes={name: list(dataset.categorical_classes[name])
                                 for name in dataset.source_channel_names
                                 if name in dataset.categorical_classes},
            channel_groups={name: list(indices) for name, indices in dataset.channel_groups.items()},
        )
    finally:
        dataset.close()


def season_split(event):
    season = (event["country"], event["year"])
    if season in (("KR", 2022), ("US", 2020), ("US", 2021)):
        return "train"
    if season in (("KR", 2023), ("US", 2022)):
        return "validation"
    if season in (("KR", 2025), ("US", 2024)):
        return "test"
    raise ValueError(f"No predetermined split for {season}")


def sample_segments(lengths, starts, limit, rng):
    """Uniform distinct indices from disjoint integer time segments per cell."""
    lengths = np.asarray(lengths, dtype=np.int64)
    cumulative = np.cumsum(lengths)
    total = int(cumulative[-1]) if len(cumulative) else 0
    count = min(limit, total)
    if not count:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64), np.empty(0), total
    draws = np.sort(rng.choice(total, size=count, replace=False))
    cells = np.searchsorted(cumulative, draws, side="right")
    prior = np.concatenate(([0], cumulative[:-1]))
    times = starts[cells] + draws - prior[cells]
    weights = np.full(count, total / count, dtype=np.float64)
    return cells, times, weights, total


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _patches(array, rows, cols, radius=1):
    windows = np.lib.stride_tricks.sliding_window_view(array, (2 * radius + 1,) * 2, axis=(-2, -1))
    return windows[:, rows - radius, cols - radius].transpose(1, 0, 2, 3).copy()


def prepare_event(root, event, event_index, rng, contact_limit, no_contact_limit, chunk_hours=24,
                  *, source_channels=None, categorical_classes=None, channel_names=None, kernel_size=3):
    if type(kernel_size) is not int or kernel_size < 3 or kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    radius = kernel_size // 2
    with rasterio.open(root / event["arrival_path"]) as source:
        arrival = source.read(1, masked=True).filled(np.nan).astype(np.float32)
        metric_grid = source.crs.is_projected and source.crs.linear_units in ("metre", "meter")
        spacing = [abs(source.transform.a), abs(source.transform.e)] if metric_grid and source.transform.b == source.transform.d == 0 else None
    finite = np.isfinite(arrival)
    neighborhood_known = minimum_filter(finite.astype("uint8"), size=kernel_size, mode="constant", cval=0) > 0
    offsets = np.ones((kernel_size, kernel_size), dtype=bool)
    offsets[radius, radius] = False
    neighbor_arrival = minimum_filter(
        np.where(finite, arrival, np.inf), footprint=offsets, mode="constant", cval=np.inf,
    )
    start = pd.Timestamp(event["start_utc"])
    end = pd.Timestamp(event["end_utc"])
    origin = pd.Timestamp(event["t0_utc"])
    hours = int((end - start).total_seconds() // 3600)
    elapsed = (start - origin).total_seconds() / 3600 + np.arange(hours + 1, dtype=np.float64)
    # First burned snapshot index. Match the loader's float64 elapsed values
    # rather than rounding fractional event origins to the arrival dtype.
    first_burn = np.searchsorted(elapsed, arrival, side="left")
    risk_lengths = np.minimum(first_burn, hours)
    raw_risk = int(risk_lengths[finite].sum())
    cells_flat = np.flatnonzero(neighborhood_known)
    a = arrival.ravel()[cells_flat]
    first = first_burn.ravel()[cells_flat]
    risk = risk_lengths.ravel()[cells_flat]
    positive = (first >= 1) & (first <= hours)
    negative_lengths = risk - positive.astype(np.int64)
    contact_start = np.searchsorted(elapsed[:-1], neighbor_arrival.ravel()[cells_flat], side="left")
    no_contact_lengths = np.minimum(contact_start, negative_lengths)
    contact_lengths = negative_lengths - no_contact_lengths
    pos_cells = np.flatnonzero(positive)
    cell_lists = [pos_cells]
    time_lists = [first[pos_cells] - 1]
    weight_lists = [np.ones(len(pos_cells), dtype=np.float64)]
    contact_cells, contact_times, contact_weights, contact_population = sample_segments(
        contact_lengths, no_contact_lengths, contact_limit, rng,
    )
    cold_cells, cold_times, cold_weights, cold_population = sample_segments(
        no_contact_lengths, np.zeros_like(no_contact_lengths), no_contact_limit, rng,
    )
    cell_lists.extend((contact_cells, cold_cells))
    time_lists.extend((contact_times, cold_times))
    weight_lists.extend((contact_weights, cold_weights))
    chosen = np.concatenate(cell_lists)
    indices = np.concatenate(time_lists).astype(np.int64)
    weights = np.concatenate(weight_lists)
    expected_target = np.concatenate((np.ones(len(pos_cells)), np.zeros(len(contact_cells) + len(cold_cells))))
    absolute = cells_flat[chosen]
    rows, cols = np.unravel_index(absolute, arrival.shape)
    order = np.argsort(indices, kind="stable")
    indices, rows, cols = indices[order], rows[order], cols[order]
    weights, expected_target = weights[order], expected_target[order]
    storage = defaultdict(list)
    unknown_environment = 0
    files = [root / event["arrival_path"]]
    dataset = WildfireSequenceDataset(
        root, events=[event["id"]], sequence_length=chunk_hours, temporal_stride=chunk_hours,
        patch_size=None, channels=CHANNELS if source_channels is None else source_channels,
        categorical_encoding="one_hot", categorical_classes=categorical_classes,
    )
    try:
        state = dataset._events[0]
        if channel_names is not None and tuple(channel_names) != dataset.channel_names:
            raise ValueError("Expanded event channels differ from the frozen training schema")
        files.extend(state["layers"][name].path for name in dataset.source_channel_names)
        for model in state["hourly_times"]:
            files.append(root / "regions" / event["id"] / "weather" / f"{model}_bands.csv")
            files.append(root / "regions" / event["id"] / "weather" / f"{model}_complete.json")
        blocks = np.unique(indices // chunk_hours)
        for block in blocks:
            sample = dataset[int(block)]
            features = sample["features"].numpy()
            feature_valid = sample["feature_valid"].numpy()
            burned = sample["burned_area"].numpy()
            label_valid = sample["burned_area_valid"].numpy()
            selected = np.flatnonzero(indices // chunk_hours == block)
            for hour in np.unique(indices[selected]):
                positions = selected[indices[selected] == hour]
                local = int(hour % chunk_hours)
                rr, cc = rows[positions], cols[positions]
                assert bool(sample["time_valid"][local])
                current_utc = int(sample["time_utc"][local])
                expected_utc = int(start.timestamp()) + int(hour) * 3600
                assert current_utc == expected_utc and current_utc + 3600 <= int(end.timestamp())
                dynamic_ends = sample["source_interval_end_utc"][local]
                assert bool(((dynamic_ends <= current_utc) | (dynamic_ends == -1)).all())
                valid_context = _patches(feature_valid[local], rr, cc, radius).all(axis=(1, 2, 3))
                valid_burned = _patches(label_valid[local], rr, cc, radius).all(axis=(1, 2, 3))
                current_patch = _patches(burned[local], rr, cc, radius)
                next_state = (arrival[rr, cc].astype(np.float64) <= elapsed[int(hour) + 1]).astype(np.float32)
                assert (current_patch[:, 0, radius, radius] == 0).all()
                assert valid_burned.all()
                assert np.array_equal(next_state, expected_target[positions])
                unknown_environment += int((~valid_context).sum())
                keep = positions[valid_context]
                if not len(keep):
                    continue
                storage["environment"].append(_patches(features[local], rr, cc, radius)[valid_context])
                storage["burned"].append(current_patch[valid_context])
                storage["target"].append(next_state[valid_context])
                storage["weight"].append(weights[keep])
                storage["event_index"].append(np.full(len(keep), event_index, dtype=np.int64))
                storage["time_utc"].append(np.full(len(keep), current_utc, dtype=np.int64))
                storage["row"].append(rows[keep].astype(np.int32))
                storage["col"].append(cols[keep].astype(np.int32))
    finally:
        dataset.close()
    arrays = {name: np.concatenate(values) for name, values in storage.items()}
    count = len(arrays.get("target", []))
    audit = dict(
        id=event["id"], name=event["name"], country=event["country"], year=event["year"],
        grid_pixel_size_m=spacing,
        split=season_split(event), hourly_intervals=hours,
        label_known_unburned_cell_hours=raw_risk,
        burned_context_known_unburned_cell_hours=int(risk.sum()),
        positive_targets_before_environment_filter=int(positive.sum()),
        no_contact_positive_targets_before_environment_filter=int((positive & (contact_start > first - 1)).sum()),
        contact_negative_population=contact_population, no_contact_negative_population=cold_population,
        candidate_samples=len(chosen), environmental_context_rejections=unknown_environment,
        accepted_samples=count,
        accepted_positives=int(arrays["target"].sum()) if count else 0,
        accepted_no_contact_positives=int(((arrays["target"] == 1) & (arrays["burned"].sum(axis=(1, 2, 3)) == 0)).sum()) if count else 0,
        estimated_environment_valid_cell_hours=float(arrays["weight"].sum()) if count else 0,
        exclusion=f"No eligible full {kernel_size}x{kernel_size} context / next-hour at-risk target" if not count else None,
    )
    return arrays, audit, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--contact-negatives-per-event", type=int, default=5000)
    parser.add_argument("--no-contact-negatives-per-event", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--kernel-size", type=int, default=3)
    parser.add_argument("--channels", nargs="+", default=TRAINING_SOURCE_CHANNELS,
                        help="Ordered source fields; categorical fields expand into complete one-hot groups")
    args = parser.parse_args()
    if args.kernel_size < 3 or args.kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    if args.contact_negatives_per_event <= 0 or args.no_contact_negatives_per_event <= 0:
        raise ValueError("Negative sampling limits must be positive")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Prepared output directory is not empty; choose a new directory")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    root = args.data_root.resolve()
    catalog = json.loads((root / "events.json").read_text())
    schema = resolve_channel_schema(root, args.channels)
    rng = np.random.default_rng(args.seed)
    splits = defaultdict(lambda: defaultdict(list))
    per_event, source_files = [], {root / "events.json"}
    if "biome.biome_class" in schema["source_channels"]:
        source_files.add(root / "biome_classes.json")
    for index, event in enumerate(catalog):
        arrays, audit, files = prepare_event(
            root, event, index, rng, args.contact_negatives_per_event, args.no_contact_negatives_per_event,
            source_channels=schema["source_channels"], categorical_classes=schema["categorical_classes"],
            channel_names=schema["channels"],
            kernel_size=args.kernel_size,
        )
        per_event.append(audit)
        source_files.update(files)
        for name, value in arrays.items():
            splits[audit["split"]][name].append(value)
        print(json.dumps(audit), flush=True)
    split_summary = {}
    for partition in ("train", "validation", "test"):
        arrays = {name: np.concatenate(values) for name, values in splits[partition].items()}
        np.savez_compressed(args.output_dir / f"{partition}.npz", **arrays)
        split_summary[partition] = dict(
            events=sum(season_split(event) == partition for event in catalog),
            samples=len(arrays["target"]), positives=int(arrays["target"].sum()),
            estimated_eligible_cell_hours=float(arrays["weight"].sum()),
        )
    manifest = []
    for path in sorted(source_files):
        manifest.append(dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, sha256=_hash(path)))
    metadata = dict(
        created_at_utc=datetime.now(timezone.utc).isoformat(), data_root=str(root),
        **schema, kernel_size=args.kernel_size, dt_hours=1.0, seed=args.seed,
        evaluation_grouping="pooled_countries",
        event_ids=[event["id"] for event in catalog],
        splits={event["id"]: season_split(event) for event in catalog},
        split_policy="Whole country-year seasons, fixed before fitting or test evaluation",
        split_summary=split_summary, per_event=per_event, source_files=manifest,
        sampling=dict(
            all_positives=True, negatives="Uniform without replacement within event and contact stratum",
            contact_limit=args.contact_negatives_per_event, no_contact_limit=args.no_contact_negatives_per_event,
            weights="Inverse candidate inclusion probability N_stratum/n_sampled; no refill after validity filtering",
            metric_scope="All eligible reconstructed targets; negative-population metrics estimated by sampling weights",
        ),
        label_interpretation="Retrospective reconstructed hourly burned states inside final perimeter; not observed hourly ground truth",
        target="Currently unburned at t becomes burned at t+3600 seconds, using current t environmental context",
    )
    spacings = [event["grid_pixel_size_m"] for event in per_event]
    if all(spacing == spacings[0] for spacing in spacings) and spacings[0] is not None and spacings[0][0] == spacings[0][1]:
        metadata["grid_resolution_m"] = spacings[0][0]
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(split_summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
