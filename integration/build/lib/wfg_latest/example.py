"""Reproducible latest-forecast-to-checked-route example (unscored). Usage:
  python -I -B -m wfg_latest.example --workspace W --kit-root KIT --python PY --out OUT [--arms RDA_CAND,RDA_BASE]
Uses the Hongseong 2023 inputs (event KFS_05, cutoff 2023-04-02T07:00:00Z, request template 20230402T070000Z_FW1, which is NOT one of the 20 scored missions)."""
import argparse, json, sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wfg_latest import api  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True); ap.add_argument("--kit-root", required=True)
    ap.add_argument("--python", default=sys.executable); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default="RDA_CAND,RDA_BASE")
    a = ap.parse_args(); W = Path(a.workspace); out = Path(a.out)
    if out.exists():
        raise SystemExit("OUT_EXISTS (fresh folder required): %s" % out)
    src = W / "outputs/forecast_github_update_20261014_v1/source"
    data = W / "outputs/final_forecast_ablation_20261014_v1/source/wildfire/data/environment"
    ck = src / "runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
    graph = W / "outputs/korean_multi_incident_routing_20261012_v1/phaseA/roads/A_miryang_hongseong/hongseong_2023/graph.json"
    request = W / "outputs/korean_multi_incident_routing_20261012_v1/phaseA/missions/hongseong_2023/requests/20230402T070000Z_FW1.json"
    cut = "2023-04-02T07:00:00Z"; out.mkdir(parents=True)
    rec = api.export_forecast(source_root=src, data_root=data, checkpoint=ck, event="KFS_05", cutoff=cut, out_dir=out / "export", python=a.python)
    pkt = api.build_packet(graph=graph, export_dir=out / "export", event="KFS_05", cutoff=cut, region="hongseong_2023",
                           out_dir=out / "packet", python=a.python)
    api.rekey_request(request, out / "packet", cut, out_path=out / "request.json")
    results = [api.route_and_check(kit_root=a.kit_root, packet_dir=out / "packet", graph=graph, request=out / "request.json",
                                   out_dir=out / ("route_" + arm), arm=arm, python=a.python) for arm in a.arms.split(",")]
    summary = {"export": {k: rec.get(k) for k in ("event", "cutoff_utc", "npz_sha256", "timing_s", "raw_summary")},
               "packet": {k: pkt.get(k) for k in ("shape", "present_fire_cells", "initial_remaining_s", "ignitions_per_member", "max_flux_kW_m2",
                                                   "hazard_construction_wall_s", "enclosure")},
               "routes": results}
    (out / "EXAMPLE_RESULT.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
