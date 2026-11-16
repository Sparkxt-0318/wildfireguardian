"""Rebind a frozen v8 job to a checkout and user-provided data files."""
import argparse
import json
from pathlib import Path

from io_utils import read, sha

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STACK = REPO / "experimental" / "window-routing" / "stack"


def prepare(template, graph, request, packet, output, cache, expected_template_sha256):
    if sha(template) != expected_template_sha256:
        raise ValueError("Frozen template checksum mismatch")
    job = read(template)
    graph, request, packet, output = (
        Path(path).resolve() for path in (graph, request, packet, output)
    )
    paths = {
        "graph_path": graph,
        "request_path": request,
        "hazard_path": packet / "HAZARD.json",
    }
    for key, path in paths.items():
        if sha(path) != job["input_sha256"][key]:
            raise ValueError(f"Input checksum mismatch for {key}")
    for name, expected in job["source_sha256"].items():
        if sha(packet / name) != expected:
            raise ValueError(f"Packet checksum mismatch for {name}")

    baseline = STACK / "routing_candidate" / "baseline"
    phase = STACK / "phaseB"
    for name, expected in job["checker_sha256"].items():
        if sha(baseline / name) != expected:
            raise ValueError(f"Checker checksum mismatch for {name}")
    for name, expected in job["phaseB_sha256"].items():
        if sha(phase / name) != expected:
            raise ValueError(f"Fallback checksum mismatch for {name}")
    if sha(baseline / "routing-package" / "routing" / "core.py") != job["core_sha256"]:
        raise ValueError("Routing core checksum mismatch")
    if job.get("preparation_mode_sha256") and sha(phase / "preparation_mode.py") != job["preparation_mode_sha256"]:
        raise ValueError("Preparation checksum mismatch")

    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    if cache is not None:
        cache = Path(cache).absolute()
        if not cache.is_dir():
            raise ValueError("Cache must be a directory")
    job["rebind_provenance"] = {
        "template_sha256": expected_template_sha256,
        "template_worker": job.get("worker"),
        "template_worker_sha256": job.get("actual_worker_sha256"),
    }
    job.update(
        {key: str(path) for key, path in paths.items()},
        source_directory=str(packet),
        source_root=str(STACK / "routing_candidate"),
        decision_dir=str(STACK / "decision"),
        root=str(REPO),
        output_path=str(output),
        worker=str(HERE / "update.py"),
        actual_worker_sha256=sha(HERE / "update.py"),
        update_arm="corridor",
        preparation_mode="AUTHENTICATED_ARTIFACT" if cache is not None else "COLD_FAST",
    )
    job.pop("old_job_path", None)
    output.mkdir(parents=True)
    try:
        with (output / "job.json").open("x") as file:
            json.dump(job, file, indent=2, allow_nan=False)
            file.write("\n")
    except Exception:
        # Remove only files created by this invocation.
        (output / "job.json").unlink(missing_ok=True)
        output.rmdir()
        raise
    return output / "job.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, help="Frozen v8 worker job JSON")
    parser.add_argument("--template-sha256", required=True, help="Trusted SHA-256 for the frozen template")
    parser.add_argument("--graph", required=True, help="Graph JSON matching template hash")
    parser.add_argument("--request", required=True, help="Request JSON matching template hash")
    parser.add_argument("--packet", required=True, help="Directory with the original frozen hazard packet")
    parser.add_argument("--output", required=True, help="New output directory")
    parser.add_argument("--cache", help="Authenticated prepared-graph cache directory")
    args = parser.parse_args()
    try:
        job = prepare(args.template, args.graph, args.request, args.packet, args.output, args.cache, args.template_sha256)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Cannot prepare job: {exc}\n")
    print(job)
    print("Run using a complete-request supervisor; set WFG_OWNER_PREPARED_CACHE when using --cache.")


if __name__ == "__main__":
    main()
