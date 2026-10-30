"""Lightweight real-file reader smoke, not a new routing-risk experiment."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from wfg_synthetic_truth.adapters import GridSpec, reconstructed_arrival, observed_perimeters, external_simulator


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument("--data-root", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(); root = args.data_root.resolve(); env = root/"environment"; extraction = root/"EXTRACTION_MANIFEST.json"
    manifest = json.loads(extraction.read_text()); hashes = {row["path"]: row["sha256"] for row in manifest["members"]}
    historical = root/"historical_observed/MANIFEST.json"
    hm = json.loads(historical.read_text())
    hashes.update({"historical_observed/"+row["path"]: row["sha256"] for row in hm["members"]})
    def expected(path):
        digest = hashes[str(path.relative_to(root))]
        if sha(path) != digest: raise ValueError("Extraction manifest mismatch: "+str(path))
        return digest
    inputs = {str(extraction): sha(extraction), str(historical): sha(historical)}
    def grid_for(event):
        path = env/"regions"/event/"grid.json"; expected(path); inputs[str(path)] = sha(path)
        d = json.loads(path.read_text()); return d, GridSpec((d["height"], d["width"]), tuple(d["transform"]), d["epsg"])
    d, grid = grid_for("KFS_01")
    a = env/"regions/KFS_01/arrival_time_hours.tif"; sd = a.with_name("kriging_std_hours.tif")
    reconstruction = reconstructed_arrival(a, grid=grid, origin_utc=d["t0_utc"], cutoff_utc=d["start_utc"], units="hours", source_id="KFS_01:reconstruction", std_path=sd, expected_sha256=expected(a), expected_std_sha256=expected(sd))
    event = "OR-WIF-220180_CedarCreek"; d, grid = grid_for(event)
    path = root/"perimeters"/event/"perimeters.geojson"; pm = root/"perimeters/PERIMETER_MANIFEST.json"
    inputs[str(pm)] = sha(pm)
    perimeter = observed_perimeters(path, grid=grid, cutoff_utc=d["start_utc"], source_id=event+":NIROPS", expected_event=event,
                                   expected_sha256=json.loads(pm.read_text())["events"][event]["geojson_sha256"])
    case = root/"historical_observed/20261013_observed_merged/cases/b0196655a9648847dcb4"
    protocol = case/"protocol.json"; proto = json.loads(protocol.read_text()); expected(protocol); inputs[str(protocol)] = sha(protocol)
    arrival = case/"farsite_prediction.npz"; reference = case/"reference.npz"
    simulator = external_simulator(arrival, reference_path=reference, cutoff_utc=proto["cutoff"], source_id=proto["event"]+":stored-FARSITE", expected_event=proto["event"], expected_sha256=expected(arrival), expected_reference_sha256=expected(reference))
    src = Path("experimental/synthetic-truth/src/wfg_synthetic_truth/adapters.py")
    report = {"scope": "three real-format loader smokes, no exact observation truth or risk score", "host": platform.platform(), "python": sys.version,
              "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "producer_sha256": sha(Path(__file__)), "adapter_sha256": sha(src), "input_ledgers": inputs,
              "readers": [x.report() for x in (reconstruction, perimeter, simulator)],
              "native_simulator_execution": "NOT_RUN, current native installation availability unconfirmed; stored outputs only"}
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"readers": [{"kind": r["kind"], "status": r["status"], "known_cells": r["known_cells"], "unknown_cells": r["unknown_cells"]} for r in report["readers"]]}))


if __name__ == "__main__": main()
