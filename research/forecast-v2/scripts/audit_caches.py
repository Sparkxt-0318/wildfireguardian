"""Recompute every consumed development/fitting cache from verified originals.

No cache, label, checkpoint or scientific result is modified. Earlier mixed
time-policy caches remain explicitly obsolete and are never admitted.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import re
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
spec = importlib.util.spec_from_file_location("cache_source_recomputation", HERE.with_name("pipeline.py"))
P = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = P
spec.loader.exec_module(P)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    producer = sha(HERE.with_name("pipeline.py"))
    records = []
    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        env = P.Environment(args.data / "environment", args.work / "env")
        for path in sorted((args.work / "env").glob("*.npz")):
            event, stamp = path.stem.rsplit("_", 1)
            before = sha(path)
            row = dict(kind="environment", cache=str(path), cache_sha256=before, event=event, stamp=stamp)
            try:
                raw = env.at(event, pd.to_datetime(stamp, format="%Y%m%dT%H", utc=True))
                row.update(status="MATCHES_RECOMPUTED_SOURCES", shape=list(raw.shape), dtype=str(raw.dtype))
                if sha(path) != before:
                    raise ValueError("Cache unexpectedly changed during read-only audit")
            except Exception as error:
                row.update(status="DIFFERS_OR_UNAVAILABLE", error_type=type(error).__name__, reason=str(error))
            records.append(row)
            print(json.dumps(row), flush=True)
        for path in sorted((args.work / "samples").glob("*.pkl")):
            row = dict(kind="sample-list", cache=str(path), cache_sha256=sha(path))
            matched = re.fullmatch(r"(perimeter_crop|kriged_utc_v2)_first(0|3)_(.+)", path.stem)
            if not matched:
                if path.stem.startswith("kriged_first3_"):
                    row.update(status="OBSOLETE_TIME_POLICY_EXCLUDED", reason="Preserved original mixed caches before UTC cutoff repair; not consumed by active phases")
                else:
                    row.update(status="UNRECOGNIZED_CACHE_HOLD")
            else:
                kind, limit, event = matched.groups()
                limit = int(limit) or None
                try:
                    fresh = (P.perimeter_samples(event, args.data / "perimeters", env, crop=True, max_intervals=limit)
                             if kind == "perimeter_crop" else P.kriged_samples(event, args.data / "environment", env, max_intervals=limit))
                    stored = pickle.loads(path.read_bytes())
                    old_id, fresh_id = P.sample_list_identity(stored), P.sample_list_identity(fresh)
                    row.update(event=event, samples=len(stored), cached_value_identity=old_id, recomputed_value_identity=fresh_id,
                               status="MATCHES_RECOMPUTED_SOURCES" if old_id == fresh_id else "DIFFERS_HOLD")
                except Exception as error:
                    row.update(status="DIFFERS_OR_UNAVAILABLE", error_type=type(error).__name__, reason=str(error))
            records.append(row)
            print(json.dumps(row), flush=True)
        fcntl.flock(lock, fcntl.LOCK_UN)
    bad = [r for r in records if r["status"] not in ("MATCHES_RECOMPUTED_SOURCES", "OBSOLETE_TIME_POLICY_EXCLUDED")]
    result = dict(status="PASS_NO_CONSUMED_VALUES_CHANGED" if not bad else "HOLD_INPUT_DIFFERENCE", records=records,
        environment_caches=sum(r["kind"] == "environment" for r in records),
        active_sample_caches=sum(r["kind"] == "sample-list" and r["status"] != "OBSOLETE_TIME_POLICY_EXCLUDED" for r in records),
        obsolete_sample_caches=sum(r["status"] == "OBSOLETE_TIME_POLICY_EXCLUDED" for r in records),
        mismatches=bad, producer_sha256=producer, producer_unchanged_during_audit=producer == sha(HERE.with_name("pipeline.py")),
        verified_input_sha256={p: env._pins[p] for p in sorted(env._verified)},
        audit_script_sha256=sha(HERE), completed_utc=datetime.now(timezone.utc).isoformat(),
        evidence_boundary="Input/cache equality only; no study forecast-quality score computed, no cache overwritten")
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "environment_caches", "active_sample_caches", "obsolete_sample_caches")}))
    if bad or not result["producer_unchanged_during_audit"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
