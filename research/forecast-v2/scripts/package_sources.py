"""Preserve exact receipt-bound producer bytes as deterministic gzip snapshots."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import audit_fit_coverage as coverage

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = REPO / "research/forecast-v2"
RETIRED = [f"a03_fold_{year}_burnout_spotting" for year in (2020, 2021, 2022)] + ["a03_final_burnout_spotting"]


def preserve(relative, expected):
    # Recovery authenticates exact original bytes; similar current source is
    # never substituted for a missing historical producer.
    blob = coverage._source_blob(REPO, relative, expected).encode("utf-8")
    if hashlib.sha256(blob).hexdigest() != expected:
        raise ValueError("Historical source recovery changed original bytes")
    path = EVIDENCE / "source_snapshots" / expected / (Path(relative).name + ".gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(gzip.compress(blob, mtime=0))
    if hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() != expected:
        raise ValueError("Compressed snapshot roundtrip changed original bytes")
    return dict(source=relative, original_sha256=expected, compressed=coverage.identity(REPO, path), original_bytes=len(blob))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prune-identical-plain", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve the earlier packaging manifest")
    records, failures, phases = {}, [], {}
    for receipt in sorted((EVIDENCE / "executions").glob("*.json")):
        record = json.loads(receipt.read_text())
        source = record.get("source_sha256", {})
        if not isinstance(source, dict):
            continue
        declared = []
        for relative, expected in sorted(source.items()):
            key = relative + ":" + str(expected)
            if key not in records:
                try:
                    records[key] = preserve(relative, expected)
                except (ValueError, FileNotFoundError) as error:
                    failures.append(dict(phase=receipt.stem, source=relative, sha256=expected, reason=str(error)))
                    if receipt.stem in RETIRED:
                        raise ValueError("Every retired spotting producer must be recoverable") from error
                    continue
            declared.append(records[key])
        phases[receipt.stem] = dict(receipt=coverage.identity(REPO, receipt), sources=declared)
    if not set(RETIRED) <= phases.keys():
        raise ValueError("Every retired spotting execution receipt must be retained")
    pruned = []
    if args.prune_identical_plain:
        for path in sorted((EVIDENCE / "source_snapshots").rglob("*")):
            if not path.is_file() or path.suffix == ".gz":
                continue
            expected = path.parent.name
            if coverage.sha(path) != expected:
                raise ValueError("A plain snapshot does not match its content-addressed identity")
            zipped = path.with_name(path.name + ".gz")
            if not zipped.exists():
                zipped.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
            if hashlib.sha256(gzip.decompress(zipped.read_bytes())).hexdigest() != expected:
                raise ValueError("Never remove a plain source without an exact compressed replacement")
            pruned.append(str(path.relative_to(REPO)))
            path.unlink()
    result = dict(schema="wfg.forecast-source-snapshots/1", generated_utc=datetime.now(timezone.utc).isoformat(),
                  phases=phases, unique_source_identities=len(records), unresolved_original_source=failures,
                  retired_spotting_sources_complete=True, removed_identical_plain_paths=pruned,
                  script_sha256=coverage.sha(Path(__file__)),
                  interpretation="Gzip bytes preserve each original source SHA; no source is relabelled as a different producer.")
    coverage.write_new(args.out, result)
    print(json.dumps(dict(unique_sources=len(records), retired_complete=True, other_unresolved=len(failures), plain_pruned=len(pruned))))


if __name__ == "__main__":
    main()
