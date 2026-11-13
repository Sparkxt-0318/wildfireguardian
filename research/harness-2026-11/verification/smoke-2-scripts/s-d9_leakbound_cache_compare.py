"""Owen: compare a fresh re-extraction of leak-bound caches with the run's caches (closes ledger row 63, note 1).

Fires chosen by the verifier, not the author. Rule: rng = np.random.default_rng(20261113063); fires = sorted Incident_C
of FOLDS.csv (1187a9d6); a = fires[rng.integers(len(fires))]; b = drawn the same way from the fires in a different
fold -> MT-KNF-000201_SouthYaak (fold 2), CO-SJF-001184_TrailSprings (fold 3).

Prints, per fire and per array: shape, dtype, exact equality and the sha256 of the raw bytes in both files.
No values are printed (part-a cell data stays in the executor's container).

    python s-d9_leakbound_cache_compare.py RUN/cache FRESH/cache MT-KNF-000201_SouthYaak CO-SJF-001184_TrailSprings
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

KEYS = ("x", "y", "dist_m", "f1", "interval", "f2", "intervals", "newburn", "newburn_outside_crop",
        "band_uncropped", "band_uncropped_inside_crop")


def h(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main(run_cache, fresh_cache, *fires):
    out, all_eq = {}, True
    for f in fires:
        a, b = np.load(Path(run_cache) / f"{f}.npz"), np.load(Path(fresh_cache) / f"{f}.npz")
        keys_a, keys_b = sorted(a.files), sorted(b.files)
        rec = dict(keys_equal=keys_a == keys_b, missing_expected=[k for k in KEYS if k not in a.files])
        for k in KEYS:
            if k in a.files and k in b.files:
                eq = bool(a[k].shape == b[k].shape and a[k].dtype == b[k].dtype and np.array_equal(a[k], b[k]))
                rec[k] = dict(shape=list(a[k].shape), dtype=str(a[k].dtype), equal=eq, sha_run=h(a[k])[:16], sha_fresh=h(b[k])[:16])
                all_eq &= eq
        all_eq &= rec["keys_equal"] and not rec["missing_expected"]
        out[f] = rec
    out["ALL_EQUAL"] = all_eq
    print(json.dumps(out, indent=1))
    sys.exit(0 if all_eq else 1)


if __name__ == "__main__":
    main(*sys.argv[1:])
