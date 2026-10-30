"""Recover small pinned supplements from the user-supplied source archive.

The original archive's SHA is mandatory. Existing different output bytes are
never overwritten. No downloaded source or new licence is introduced.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ARCHIVE_SHA = "b9e000e8661128416fe7561690f78b1955d5a32189ac71536c1cd4110cd5dd65"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--kind", choices=["baseline-terrain", "native-farsite", "farsite-inputs"], required=True)
    args = parser.parse_args()
    if sha(args.archive) != ARCHIVE_SHA:
        raise ValueError("Source archive identity differs")
    requested, pins = {}, {}
    if args.kind == "baseline-terrain":
        for event in json.loads((args.data / "environment/events.json").read_text()):
            relative = f"regions/{event['id']}/terrain/elevation_m_375m.tif"
            requested["wildfire/data/environment/" + relative] = args.data / "baseline-terrain" / event["id"] / "elevation_m_375m.tif"
    elif args.kind == "farsite-inputs":
        for case in (args.data / "historical_observed/20261013_observed_merged/cases").iterdir():
            report = json.loads((case / "report.json").read_text())
            for row in report["farsite_input_manifest"]["source_files"]:
                relative = row["path"].split("/data/environment/", 1)[1]
                member = "wildfire/data/environment/" + relative
                if member in pins and pins[member] != row["sha256"]:
                    raise ValueError("Historical scenarios disagree about an input identity")
                pins[member] = row["sha256"]
                requested[member] = args.data / "farsite-inputs" / relative
    records = []
    with zipfile.ZipFile(args.archive) as archive:
        if args.kind == "native-farsite":
            prefix = "wildfire/tmp/farsite_observed_source/"
            for entry in archive.infolist():
                if entry.is_dir() or not entry.filename.startswith(prefix):
                    continue
                rel = PurePosixPath(entry.filename[len(prefix):])
                if ".git" in rel.parts or any(p.startswith("._") for p in rel.parts):
                    continue
                requested[entry.filename] = args.data / "native-farsite" / str(rel)
        for member, path in sorted(requested.items()):
            if ".." in PurePosixPath(member).parts:
                raise ValueError("Unsafe archive member")
            data = archive.read(member)
            digest = hashlib.sha256(data).hexdigest()
            if member in pins and digest != pins[member]:
                raise ValueError(f"Archived input does not match the historical pinned scenario: {member}")
            if path.exists() and sha(path) != digest:
                raise ValueError(f"Existing different bytes are preserved: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if args.kind == "native-farsite" and path.name in ("TestFARSITE", "observed_clock_probe"):
                path.chmod(0o755)
            records.append(dict(member=member, path=str(path.relative_to(args.data)), bytes=len(data), sha256=digest,
                                historical_input_identity_matches=member in pins))
    output = dict(kind=args.kind, source_archive_sha256=ARCHIVE_SHA, files=records,
                  interpretation="Original supplied bytes. Native availability and scientific validation require separate execution.")
    target = args.data / (args.kind.upper().replace("-", "_") + "_EXTRACTION.json")
    target.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(dict(kind=args.kind, files=len(records), bytes=sum(r["bytes"] for r in records), manifest=str(target))))


if __name__ == "__main__":
    main()
