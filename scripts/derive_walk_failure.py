#!/usr/bin/env python
"""Derive the assumption-LIGHT walk-failure rate w from the committed fc sweep.

Reads ``data/processed/rescue_verify_fc.json`` (the immobile_fraction × walk_cutoff
sweep) and augments it with the per-cell decomposition

    needs_rescuer = round(f·N) + walk_failures_mobile ,   w = walk_failures_mobile / n_mobile

so the headline "cannot self-evacuate on foot" rate is a *measured* quantity
independent of the immobility assumption. **No pipeline / sweep re-run** — this is
pure arithmetic on the already-committed four-way counts (reuses
``verify_rescue_routing.walk_failure_table``). Writes the augmented JSON back and
prints the w range.

Run:  python scripts/derive_walk_failure.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from verify_rescue_routing import walk_failure_summary, walk_failure_table  # noqa: E402

FC = REPO / "data" / "processed" / "rescue_verify_fc.json"


def main() -> int:
    if not FC.exists():
        print(f"missing {FC}; run verify_rescue_routing.py --sweep fc first", file=sys.stderr)
        return 2
    data = json.loads(FC.read_text())
    N = data["n_origins"]
    # Reconstruct the {(f, c): counts} grid from the committed "f|c" keys.
    grid = {}
    for key, counts in data["grid"].items():
        f_s, c_s = key.split("|")
        grid[(float(f_s), float(c_s))] = counts
    rows = walk_failure_table(grid, N)
    summary = walk_failure_summary(rows)
    data["walk_failure"] = {"per_cell": rows, "summary": summary}
    FC.write_text(json.dumps(data, indent=2, default=str))

    print(f"N = {N}; derived w from {len(rows)} committed fc cells (no re-run).")
    print("per-cell (immobile f, walk_cutoff c -> n_mobile, walk_failures_mobile, w, "
          "needs_rescuer, identity f·N+(1-f)·w·N):")
    for r in rows:
        print(f"  f={r['immobile_fraction']:.2f} c={r['walk_cutoff']:.2f} -> "
              f"n_mob={r['n_mobile']} wf={r['walk_failures_mobile']} w={r['w']:.3f} "
              f"needs={r['needs_rescuer']} (identity {r['needs_rescuer_identity_f_plus_1mf_w']})")
    print(f"\nw range across grid: {summary['w_grid_min']:.3f}-{summary['w_grid_max']:.3f}")
    print("w by walk cutoff (min-max across f):",
          {k: [round(v[0], 3), round(v[1], 3)] for k, v in summary['w_by_walk_cutoff_minmax'].items()})
    print(f"w ~flat across f at fixed cutoff? {summary['w_approx_flat_across_f']} "
          f"(max spread {summary['w_max_spread_across_f_fixed_cutoff']:.3f})")
    print(f"wrote {FC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
