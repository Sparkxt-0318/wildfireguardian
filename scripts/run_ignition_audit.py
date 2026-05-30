#!/usr/bin/env python3
"""Deliverable 0 -- run the data audit and write data audit JSON + print table.

Usage:
    python scripts/run_ignition_audit.py
"""

from __future__ import annotations

import json

from wildfireguardian.ignition_model.audit import format_audit_table, run_audit
from wildfireguardian.ignition_model.config import PipelineConfig


def main() -> None:
    config = PipelineConfig()
    audit = run_audit(config)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    out = config.output_dir / "data_audit.json"
    out.write_text(json.dumps(audit, indent=2, default=str))

    print("=" * 78)
    print("DELIVERABLE 0 -- DATA AUDIT")
    print("provenance:", audit["provenance"])
    print("=" * 78)
    print(format_audit_table(audit))
    print()
    print("Per-fire detail:")
    for f in audit["fires"]:
        print(f"\n--- {f['fire_id']}  ({f['name']}) ---")
        print(f"  bbox            : {f['bbox']}")
        print(f"  detections      : csv={f['n_detections_csv']} manifest={f['n_detections_manifest']}")
        print(f"  time span       : {f['first_detection']} -> {f['last_detection']} ({f['time_span_hours']} h)")
        print(f"  overpasses      : clustered={f['n_overpasses_clustered']} manifest_hours={f['overpass_hours_manifest']}")
        print(f"  det/overpass    : {f['detections_per_overpass']}")
        print(f"  instruments     : {f['instruments']}")
        print(f"  timestamps      : parseable={f['timestamps_parseable']} ordered_ok={f['timestamps_ordered_ok']}")
        print(f"  DEM             : shape={f['dem']['shape']} crs={f['dem']['crs']} bounds={tuple(round(x,3) for x in f['dem']['bounds'])} nodata={f['dem']['nodata']}")
        print(f"  FUEL            : shape={f['fuel']['shape']} crs={f['fuel']['crs']} bounds={tuple(round(x,3) for x in f['fuel']['bounds'])} nodata={f['fuel']['nodata']}")
        print(f"  burnable_frac   : {f['burnable_frac_manifest']}")
        print(f"  % det in fuel   : {100*f['frac_detections_in_fuel']:.1f}%")
        print(f"  DECISION        : {f['fuel_decision']} -- {f['fuel_reason']}")

    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
