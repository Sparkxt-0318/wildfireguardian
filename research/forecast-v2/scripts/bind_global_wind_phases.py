"""Bind phase visits to immutable wind-audit cache/case/tensor inventories."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import pickle
import sys
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "forecast"))
from wildfire.survival import sample_tensors


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve the previous phase-binding receipt")
    evidence = REPO / "research/forecast-v2"
    audit_path, cache_path = evidence / "GLOBAL_WIND_INPUT_AUDIT.json", evidence / "CACHE_AUDIT.json"
    audit, cache = json.loads(audit_path.read_text()), json.loads(cache_path.read_text())
    cache_rows = {Path(r["cache"]).name: r for r in cache["records"] if r["kind"] == "sample-list"}
    loaded, inventory = {}, []
    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for row in audit["rows"]:
            name = row["cache"]
            if name not in loaded:
                pin = cache_rows[name]
                path = Path(pin["cache"])
                if pin["status"] != "MATCHES_RECOMPUTED_SOURCES" or sha(path) != pin["cache_sha256"]:
                    raise ValueError("Original source-authenticated sample cache changed")
                loaded[name] = {s.t1: s for s in pickle.loads(path.read_bytes())}
            sample = loaded[name][row["cutoff"]]
            tensor = sample_tensors(sample)["environment"].contiguous()
            digest = hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
            if digest != row["produced_tensor_sha256"] or list(tensor.shape) != row["actual_preclean_tensor_shape"]:
                raise ValueError("Produced tensor no longer matches its original audit")
            key = dict(event=sample.event_id, kind=sample.kind,
                       cutoff=pd.Timestamp(sample.t1).tz_convert("UTC").isoformat(),
                       endpoint=pd.Timestamp(sample.meta["t2"]).tz_convert("UTC").isoformat())
            content = dict(dtype=str(tensor.dtype), shape=list(tensor.shape), bytes_sha256=digest)
            record = dict(cache=name, source_case=key, source_case_id=identity(key),
                tensor_content=content, tensor_content_id=identity(content),
                missing_wind_values=row["missing_wind_values"], crop=row["crop"],
                source_cache_sha256=cache_rows[name]["cache_sha256"])
            record["inventory_record_id"] = identity(record)
            inventory.append(record)
        fcntl.flock(lock, fcntl.LOCK_UN)
    phases = []
    for phase in audit["phases"]:
        prefix = "perimeter_crop_first0_" if phase["phase"] == "a03_final_burnout_spotting" else "perimeter_crop_first3_"
        roles = {}
        for role in ("train", "validation"):
            rows = [r for r in inventory if r["cache"].startswith(prefix) and r["source_case"]["event"] in phase[role + "_events"]]
            if len(rows) != phase["audited_" + role + "_samples"]:
                raise ValueError("Phase visit population differs from audited producer counts")
            roles[role] = dict(inventory_record_ids=[r["inventory_record_id"] for r in rows],
                              source_case_ids=[r["source_case_id"] for r in rows], visits=len(rows))
        phases.append(dict(phase=phase["phase"], producer_receipt_sha256=phase["receipt_sha256"], roles=roles))
    result = dict(schema="wfg.spotting-wind-phase-bindings/1", original_wind_audit_sha256=sha(audit_path),
        original_cache_audit_sha256=sha(cache_path), source_sha256=sha(Path(__file__)), inventory=inventory, phases=phases,
        role_specific_inventory_records=len(inventory), development_role_records=sum(r["cache"].startswith("perimeter_crop_first3_") for r in inventory),
        full_fit_role_records=sum(r["cache"].startswith("perimeter_crop_first0_") for r in inventory),
        unique_source_cases=len({r["source_case_id"] for r in inventory}),
        unique_tensor_contents=len({r["tensor_content_id"] for r in inventory}),
        phase_visits=sum(role["visits"] for p in phases for role in p["roles"].values()),
        independent_fires=len({r["source_case"]["event"] for r in inventory}),
        interpretation="Role records, content identities and phase visits are distinct denominators, not independent observations")
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("role_specific_inventory_records", "unique_source_cases", "unique_tensor_contents", "phase_visits", "independent_fires")}))


if __name__ == "__main__":
    main()
