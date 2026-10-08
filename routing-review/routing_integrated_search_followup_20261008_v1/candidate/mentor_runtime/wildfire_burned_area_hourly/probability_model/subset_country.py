"""Partition a prepared contact-only cache by country without resampling.

Original per-fire season assignments, raw features, labels, and inverse
inclusion weights are retained. Event indices are remapped to the country's
ordered event list. Parent checksums retain the complete provenance chain.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from .cache import SPLIT_NAMES, load_split


def subset_country(source: Path, output: Path, country: str) -> dict:
    """Write country-only partitions; fail for invalid or empty partitions."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if country not in ("KR", "US"):
        raise ValueError("country must be KR or US")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Country output is not empty; choose a new directory")
    metadata_path = source / "metadata.json"
    original = json.loads(metadata_path.read_text(encoding="utf-8"))
    if original.get("eligibility") != "at_least_one_burned_neighbor":
        raise ValueError("Country experiments require the contact-only source cache")
    events = original["per_event"]
    records = {event["id"]: event for event in events}
    original_ids = original["event_ids"]
    if len(records) != len(events) or set(records) != set(original_ids):
        raise ValueError("The source must identify every event and country exactly once")
    selected_ids = [event_id for event_id in original_ids if records[event_id]["country"] == country]
    if not selected_ids:
        raise ValueError(f"No {country} events in the source cache")
    mapping = np.full(len(original_ids), -1, dtype=np.int64)
    for new_index, event_id in enumerate(selected_ids):
        mapping[original_ids.index(event_id)] = new_index
    # Validate all partitions before writing any artifacts.
    partitions, summaries, parent_files = {}, {}, []
    for split in SPLIT_NAMES:
        data = load_split(source, split, original)
        keep = mapping[data.event_index] >= 0
        if not keep.any():
            raise ValueError(f"No eligible {country} targets in {split}")
        arrays = {key: getattr(data, key)[keep].copy() for key in data.__dataclass_fields__}
        arrays["event_index"] = mapping[data.event_index[keep]].astype(data.event_index.dtype)
        partitions[split] = arrays
        split_events = [records[event_id] for event_id in selected_ids if original["splits"][event_id] == split]
        if any(event["split"] != split for event in split_events):
            raise ValueError("Source per-event split assignments are inconsistent")
        summaries[split] = dict(
            events=len(split_events), contributing_events=len(np.unique(arrays["event_index"])),
            samples=len(arrays["target"]), positives=int(arrays["target"].sum()),
            estimated_eligible_cell_hours=float(arrays["weight"].sum(dtype=np.float64)),
            excluded_no_contact_samples=sum(event.get("excluded_no_contact_samples", 0) for event in split_events),
            excluded_no_contact_positives=sum(event.get("excluded_no_contact_positives", 0) for event in split_events),
            excluded_other_country_samples=int((~keep).sum()),
        )
        cache_path = source / f"{split}.npz"
        parent_files.append(dict(path=str(cache_path), sha256=hashlib.sha256(cache_path.read_bytes()).hexdigest()))
    metadata = deepcopy(original)
    metadata.update(
        created_at_utc=datetime.now(timezone.utc).isoformat(), country=country,
        event_ids=selected_ids, splits={event_id: original["splits"][event_id] for event_id in selected_ids},
        per_event=[deepcopy(records[event_id]) for event_id in selected_ids], split_summary=summaries,
        split_policy="Original whole country-year season assignments retained; all partitions restricted to " + country,
        parent_prepared_directory=str(source),
        parent_metadata_sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        parent_cache_files=parent_files,
        country_selection=dict(
            rule="Select events by per_event.country in every partition without resampling or reweighting",
            country=country, original_event_ids=original_ids,
            event_index_mapping={str(original_ids.index(event_id)): index for index, event_id in enumerate(selected_ids)},
            source_manifest_scope="Selected event files plus shared events.json; full parent manifest remains in parent metadata",
        ),
    )
    # A selected cache uses only its country-specific rasters and shared catalog.
    metadata["source_files"] = [item for item in original.get("source_files", [])
                                if item["path"] == "events.json" or any(
                                    item["path"].startswith(f"regions/{event_id}/") for event_id in selected_ids)]
    output.mkdir(parents=True, exist_ok=True)
    for split, arrays in partitions.items():
        np.savez_compressed(output / f"{split}.npz", **arrays)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"country": country, "split_summary": summaries}, indent=2), flush=True)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--country", choices=("KR", "US"), required=True)
    args = parser.parse_args()
    subset_country(args.source_dir, args.output_dir, args.country)


if __name__ == "__main__":
    main()
