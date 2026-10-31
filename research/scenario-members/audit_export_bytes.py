"""Stronger audit, retaining EXPORT_AUDIT.json as the historical value audit."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile
import numpy as np


def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def sha(path): return sha_bytes(path.read_bytes())


def compare_arrays(new, old):
    """C-order payload equality preserves NaN bits; dtype and shape are separate."""
    x = new.tobytes(order="C"); y = old.tobytes(order="C")
    return {"v3_dtype": new.dtype.str, "v2_dtype": old.dtype.str, "dtype_equal": new.dtype == old.dtype,
            "v3_shape": list(new.shape), "v2_shape": list(old.shape), "shape_equal": new.shape == old.shape,
            "v3_payload_sha256": sha_bytes(x), "v2_payload_sha256": sha_bytes(y), "payload_bytes_equal": x == y}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--exports", type=Path, required=True)
    p.add_argument("--frozen-exports", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(); rows = []
    for record_path in sorted(a.exports.glob("*/*/FORECAST_RECORD_*.json")):
        r = json.loads(record_path.read_text()); new = record_path.parent/r["npz"]
        old = a.frozen_exports/r["event"]/r["npz"]; old_record = old.parent/record_path.name
        old_r = json.loads(old_record.read_text())
        if sha(new) != r["npz_sha256"] or sha(old) != old_r["npz_sha256"]:
            raise ValueError("Frozen or v3 export fails its own producer record digest")
        arrays = {}
        with np.load(new, allow_pickle=False) as z, np.load(old, allow_pickle=False) as v2, zipfile.ZipFile(new) as zn, zipfile.ZipFile(old) as zo:
            for k in v2.files:
                if k not in z:
                    arrays[k] = {"missing": True}; continue
                c = compare_arrays(z[k], v2[k]); bn = zn.read(k+".npy"); bo = zo.read(k+".npy")
                c.update(v3_npy_sha256=sha_bytes(bn), v2_npy_sha256=sha_bytes(bo), npy_entry_bytes_equal=bn == bo)
                arrays[k] = c
        same = all(c.get("dtype_equal") and c.get("shape_equal") and c.get("payload_bytes_equal") for c in arrays.values())
        rows.append({"event": r["event"], "cutoff": r["cutoff_utc"], "shared_arrays": len(arrays), "exact_arrays_equal": same,
                     "all_npy_entries_equal": all(c.get("npy_entry_bytes_equal") for c in arrays.values()), "arrays": arrays,
                     "v3_npz_sha256": sha(new), "v2_npz_sha256": sha(old), "v3_record_sha256": sha(record_path), "v2_record_sha256": sha(old_record)})
    result = {"scope": "dtype, shape, exact C-order array payload including NaN bits, and uncompressed NPY entries; no value canonicalization",
              "host": platform.platform(), "python": sys.version, "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "producer_sha256": sha(Path(__file__)), "historical_value_audit_sha256": sha(Path("research/scenario-members/EXPORT_AUDIT.json")),
              "windows": len(rows), "exact_array_window_passes": sum(r["exact_arrays_equal"] for r in rows),
              "exact_npy_window_passes": sum(r["all_npy_entries_equal"] for r in rows), "rows": rows}
    a.out.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({k: v for k,v in result.items() if k != "rows"}))
    if not rows or not all(r["exact_arrays_equal"] for r in rows): raise SystemExit(1)


if __name__ == "__main__": main()
