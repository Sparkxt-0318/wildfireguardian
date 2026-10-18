"""Child process: write one spread_zones hazard packet with the unchanged packet writer.

Run as ``python -I -B _zone_packet_child.py --plan ZONE_PLAN.json --graph graph.json --out DIR``. Mirrors
wfg_latest/build_packet.py (vendored radiation operator and router validator installed as namespace packages, then
packets.write_regional_packet on the recorded, hash-bound c651 export at the plan's input time) with two injections at
the writer's own extension points: ``bridge.draw_ignitions`` returns the plan's ignition schedule instead of random
draws (the hook packets.construct_regional already uses), and ``bridge.settings_for`` adds a ``zone_adapter`` entry so
the settings digest -- and therefore the construction id and scenario ids -- identify the adapter output.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WFG = REPO / "integration" / "src" / "wfg_latest"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(WFG))
    import build_packet as BP            # noqa: E402
    BP.install_radiation()
    import numpy as np                   # noqa: E402
    import bridge as B                   # noqa: E402
    import contract as CT                # noqa: E402
    import packets as P                  # noqa: E402

    plan = json.loads(Path(a.plan).read_text())
    times = np.array(plan["times"], dtype=float)
    S, H, W = times.shape
    rec_packet = Path(plan["packet_dir"])
    md = json.loads((rec_packet / "NATIVE_METADATA.json").read_text())
    event = md["construction"]["parent_forecast"]["event_id"]
    window = (md.get("regional") or {}).get("window_rows_cols_north_up")
    if window != plan.get("window"):
        raise SystemExit("WINDOW_MISMATCH")
    inputs_root = rec_packet.parents[2]
    tag = plan["tag"]
    npz = inputs_root / "exports" / event / ("FORECAST_%s.npz" % tag)
    recp = inputs_root / "exports" / event / ("FORECAST_RECORD_%s.json" % tag)
    rec = json.loads(recp.read_text())
    if sha(npz) != md["construction"]["parent_forecast"]["export_sha256"]:
        raise SystemExit("RECORDED_EXPORT_MISMATCH")
    with np.load(rec_packet / "constructed_arrays.npz", allow_pickle=False) as z:
        recorded_current = z["current_active"].copy()
    if (np.isfinite(times) & recorded_current[None]).any():
        raise SystemExit("PLAN_IGNITES_PRESENT_FIRE")
    finite = times[np.isfinite(times)]
    if finite.size and (finite.min() < 0 or finite.max() >= 3600.0):
        raise SystemExit("PLAN_TIMES_OUTSIDE_HORIZON")

    calls = []

    def zone_draws(q, scenario_count, seed, horizon_s):
        q = np.asarray(q)
        if scenario_count != S:
            raise ValueError("SCENARIO_COUNT")
        if window is None:
            if q.shape != (H, W):
                raise ValueError("GRID_SHAPE")
            ev = times.copy()
        else:
            r0, r1, c0, c1 = window["r0"], window["r1"], window["c0"], window["c1"]
            if (r1 - r0 + 1, c1 - c0 + 1) != (H, W):
                raise ValueError("WINDOW_SHAPE")
            ev = np.full((S,) + q.shape, np.inf)
            ev[:, r0:r1 + 1, c0:c1 + 1] = times
        calls.append(1)
        return ev

    orig_settings = B.settings_for

    def zone_settings(T):
        s = orig_settings(T)
        s["zone_adapter"] = {"version": plan["assumptions"]["adapter"], "label": plan["assumptions"]["label"],
                             "plan_sha256": plan["plan_sha256"],
                             "ignition_times_sha256": plan["assumptions"]["ignition_times_sha256"],
                             "ignition_source": "spread_zones plan (not random draws)"}
        return s

    B.draw_ignitions = zone_draws
    B.settings_for = zone_settings
    graph = json.loads(Path(a.graph).read_text())
    epsg = int(graph["crs"].split(":", 1)[1])
    iso, _ = CT.normalize_cutoff(rec["cutoff_utc"])
    out, hz, summ = P.write_regional_packet(graph, a.graph, npz, rec, sha(recp), iso, epsg, a.out,
                                            event_id=event, region_id=plan["region"], window=window)
    if len(calls) != 1:
        raise SystemExit("DRAW_INJECTION_NOT_USED_EXACTLY_ONCE")
    with np.load(Path(out) / "constructed_arrays.npz", allow_pickle=False) as z:
        if not np.array_equal(z["ignition_time_s"], times):
            raise SystemExit("WRITTEN_IGNITIONS_DIFFER_FROM_PLAN")
        if not np.array_equal(z["current_active"], recorded_current):
            raise SystemExit("WRITTEN_PRESENT_FIRE_DIFFERS_FROM_RECORDED")
    meta = {"adapter": plan["assumptions"]["adapter"], "label": plan["assumptions"]["label"], "plan_sha256": plan["plan_sha256"],
            "ignition_times_sha256": plan["assumptions"]["ignition_times_sha256"], "region": plan["region"], "input_tag": tag, "event_id": event, "window": window,
            "scenario_ids": summ["scenario_ids"], "construction_id": summ["construction_id"],
            "ignitions_per_member": summ["ignitions_per_member"], "present_fire_cells": summ["present_fire_cells"],
            "files_sha256": summ["files_sha256"], "forecast_export_sha256": sha(npz), "forecast_record_sha256": sha(recp),
            "recorded_packet": str(rec_packet), "max_flux_kW_m2": summ["max_flux_kW_m2"]}
    with (Path(out) / "ZONE_ADAPTER.json").open("x") as f:
        json.dump(meta, f, indent=1, default=str)
        f.write("\n")
    print(json.dumps({k: meta[k] for k in ("scenario_ids", "ignitions_per_member", "present_fire_cells")}))


if __name__ == "__main__":
    main()
