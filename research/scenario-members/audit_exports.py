"""Audit v3 support, full-N empirical means and exact unchanged v2 arrays."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument("--exports", required=True)
    p.add_argument("--frozen-exports", required=True); p.add_argument("--out", required=True)
    a = p.parse_args(); rows = []
    for record_path in sorted(Path(a.exports).glob("*/*/FORECAST_RECORD_*.json")):
        record = json.loads(record_path.read_text())
        npz = record_path.parent / record["npz"]
        if sha(npz) != record["npz_sha256"]:
            raise RuntimeError("V3_EXPORT_HASH_MISMATCH")
        old = Path(a.frozen_exports) / record["event"] / record["npz"]
        with np.load(npz, allow_pickle=False) as z, np.load(old, allow_pickle=False) as v2:
            unchanged = all(k in z and np.array_equal(z[k], v2[k], equal_nan=True) if v2[k].dtype.kind == "f" else k in z and np.array_equal(z[k], v2[k]) for k in v2.files)
            first = z["trajectory_first_burn_hour"]
            known = first[0] != -2
            empirical = ((first >= 0) & (first <= 1)).mean(axis=0)
            expected = z["trajectory_cumulative_probability"][0]
            max_error = float(np.max(np.abs(empirical[known] - expected[known]))) if known.any() else None
            rows.append(dict(event=record["event"], cutoff=record["cutoff_utc"],
                             trajectory_count=record["trajectory_count"], horizon_hours=record["trajectory_horizon_hours"],
                             cells=int(known.size), unknown_cells=int((~known).sum()),
                             unknown_fraction=float((~known).mean()),
                             trajectory_component_indices=np.unique(z["trajectory_component"]).tolist(),
                             unchanged_v2_arrays=unchanged, full_n_mean_max_abs_error=max_error,
                             v3_npz_sha256=sha(npz), frozen_v2_npz_sha256=sha(old),
                             seed=record["trajectory_base_seed"], batch_size=record["trajectory_batch_size"]))
    result = {"windows": len(rows), "v2_array_identity_passes": sum(r["unchanged_v2_arrays"] for r in rows),
              "full_n_mean_passes": sum(r["full_n_mean_max_abs_error"] == 0 for r in rows),
              "windows_with_unknown_support": sum(r["unknown_cells"] > 0 for r in rows),
              "comparability": "One-hour single-component rollout and independent conditional cell draws have the same spatial law. Old all-supported zero-assigned packets versus strict v3 support confound missingness with member construction.",
              "rows": rows}
    Path(a.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()
