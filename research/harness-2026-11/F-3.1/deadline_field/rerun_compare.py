"""Compare two fdyn_run output directories packet by packet (e.g. MANIFEST_v3_3 vs MANIFEST_v3_4 reruns).

Equal means: every result key except paths, timing, memory, writer identity and the manifest/instance echo is equal
after rounding floats to 9 significant digits. Prints and writes per-packet hashes of both runs.
    python3 -m deadline_field.rerun_compare --old DIR --new DIR --out OUT
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SKIP = {"timing_s", "peak_rss_mib", "packet", "graph", "manifest_entry", "writer_identity", "hazard_sha256",
        "instance_entry"}


def norm(x):
    if isinstance(x, float):
        return float("%.9g" % x)
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", type=Path, required=True)
    ap.add_argument("--new", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = []
    for f in sorted(a.new.glob("*.json")):
        n, o = json.loads(f.read_text()), json.loads((a.old / f.name).read_text())
        keys = sorted((set(n) | set(o)) - SKIP)
        exact = [k for k in keys if n.get(k) != o.get(k)]
        rounded = [k for k in exact if norm(n.get(k)) != norm(o.get(k))]
        rows.append({"packet": f.stem, "hazard_sha256_old": o.get("hazard_sha256"), "hazard_sha256_new": n.get("hazard_sha256"),
                     "writer_identity_new": n.get("writer_identity"), "classes": n["classes"],
                     "witness_checks": n["witness_checks"], "keys_differing_exactly": exact,
                     "keys_differing_after_9sig_rounding": rounded})
    a.out.write_text(json.dumps({"what": "packet-by-packet comparison of two fdyn_run reruns", "old": str(a.old),
                                 "new": str(a.new), "packets_compared": len(rows),
                                 "packets_differing_after_rounding": sum(bool(r["keys_differing_after_9sig_rounding"]) for r in rows),
                                 "rows": rows}, indent=1))
    for r in rows:
        print(r["packet"], r["keys_differing_exactly"], r["keys_differing_after_9sig_rounding"])


if __name__ == "__main__":
    main()
