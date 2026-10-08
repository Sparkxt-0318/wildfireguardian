"""Exclude no-burned-neighbor targets from every prepared partition."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


def filter_contact(source: Path, output: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Contact-only output is not empty; choose a new directory")
    source_metadata = source / "metadata.json"
    metadata = json.loads(source_metadata.read_text())
    kernel_size = metadata["kernel_size"]
    if type(kernel_size) is not int or kernel_size < 3 or kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    radius = kernel_size // 2
    output.mkdir(parents=True, exist_ok=True)
    summaries, event_counts, parent_files = {}, {}, []
    for split in ("train", "validation", "test"):
        path = source / f"{split}.npz"
        with np.load(path, allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        if arrays["burned"].shape[1:] != (1, kernel_size, kernel_size):
            raise ValueError("Burned patch shape differs from the kernel metadata")
        if not (arrays["burned"][:, 0, radius, radius] == 0).all():
            raise ValueError("Expected currently unburned target centers")
        counts = arrays["burned"].sum(axis=(1, 2, 3))
        keep = counts > 0
        excluded_positives = int(arrays["target"][~keep].sum())
        filtered = {key: value[keep] for key, value in arrays.items()}
        assert (filtered["burned"].sum(axis=(1, 2, 3)) > 0).all()
        np.savez_compressed(output / f"{split}.npz", **filtered)
        summaries[split] = dict(
            events=sum(value == split for value in metadata["splits"].values()),
            contributing_events=len(np.unique(filtered["event_index"])),
            samples=int(keep.sum()), positives=int(filtered["target"].sum()),
            estimated_eligible_cell_hours=float(filtered["weight"].sum()),
            excluded_no_contact_samples=int((~keep).sum()),
            excluded_no_contact_positives=excluded_positives,
        )
        for index in np.unique(arrays["event_index"]):
            before = arrays["event_index"] == index
            after = filtered["event_index"] == index
            event_counts[metadata["event_ids"][int(index)]] = dict(
                unfiltered_accepted_samples=int(before.sum()),
                excluded_no_contact_samples=int((before & ~keep).sum()),
                excluded_no_contact_positives=int(arrays["target"][before & ~keep].sum()),
                accepted_samples=int(after.sum()), accepted_positives=int(filtered["target"][after].sum()),
                accepted_no_contact_positives=0,
                estimated_environment_valid_cell_hours=float(filtered["weight"][after].sum()),
            )
        parent_files.append(dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for event in metadata["per_event"]:
        event.update(event_counts.get(event["id"], {}))
        if event["accepted_samples"] == 0 and event["exclusion"] is None:
            event["exclusion"] = f"No targets with a previously burned neighbor within the {kernel_size}x{kernel_size} kernel"
    metadata.update(
        created_at_utc=datetime.now(timezone.utc).isoformat(), split_summary=summaries,
        eligibility="at_least_one_burned_neighbor",
        population_condition=f"Known currently unburned target with complete context and at least one burned neighbor inside the {kernel_size}x{kernel_size} kernel",
        parent_prepared_directory=str(source.resolve()),
        parent_metadata_sha256=hashlib.sha256(source_metadata.read_bytes()).hexdigest(),
        parent_cache_files=parent_files,
    )
    metadata["sampling"]["metric_scope"] = "Contact-conditioned eligible targets; inverse-inclusion weighted estimates"
    metadata["sampling"]["contact_filter_weights"] = "Original inverse inclusion weights retained exactly, with no class or prevalence reweighting"
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(summaries, indent=2), flush=True)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    filter_contact(args.source_dir, args.output_dir)


if __name__ == "__main__":
    main()
