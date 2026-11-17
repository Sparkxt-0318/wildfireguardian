"""C.2 (1-hour panel): rerun the F-3.1 deadline field on the six recorded planner caches with the heat rule on.

Uses F-3.1's unchanged ``deadline_field.reproduce.run`` with its PacketModel replaced by
``kcf_heat.closure.HeatPacketModel`` and variants ``cert`` (the F-3.1 headline variant: router OR closed footprint)
and ``cert_heat`` (cert OR the heat rule). Full per-attempt outputs go to OUT_DIR (outside git); a compact per-origin
summary is printed and written to OUT_DIR/<tag>.summary.json.

    python scripts/c2_deadlines_1h.py --data-root DATA/routing --out-dir DIR [--lead-scale 1.0] [--certify] CACHE...
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import F31, HeatPacketModel, HeatRule, ROOT  # noqa: E402  (puts F-3.1 on sys.path)

from deadline_field import reproduce  # noqa: E402


def summarize(out, rule):
    origins = out["origins"]
    rows = {}
    for oid, o in origins.items():
        rows[oid] = {k: o.get(k) for k in ("recorded_deadline", "kind", "best_verdict",
                                           "field_deadline_grid_cert", "field_deadline_grid_cert_heat",
                                           "field_deadline_exact_cert", "field_deadline_exact_cert_heat",
                                           "field_deadline_exact_uncapped_cert", "field_deadline_exact_uncapped_cert_heat")}
    return {"cache_file": out["cache_file"], "cache_sha256": out["cache_sha256"], "hazard_sha256": out["hazard_sha256"],
            "graph_sha256": out["graph_sha256"], "region": out["region"], "input_time": out["input_time"], "H": out["H"],
            "heat_rule": rule.describe(), "timing_s": out["timing_s"], "peak_rss_mib": out["peak_rss_mib"],
            "precondition": out["precondition"], "origins": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caches", nargs="+", type=Path)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--lead-scale", type=float, default=1.0)
    ap.add_argument("--certify", action="store_true", help="run F-3.1's fixed-point certificate on every field")
    ap.add_argument("--limit-dests", type=int)
    a = ap.parse_args()
    rule = HeatRule(lead_scale=a.lead_scale)
    reproduce.PacketModel = lambda g, p: HeatPacketModel(g, p, heat=rule)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for cache in a.caches:
        t0 = time.time()
        out = reproduce.run(cache.resolve(), a.data_root, variants=("cert", "cert_heat"), limit_dests=a.limit_dests,
                            certify=a.certify, verify=False)
        tag = "%s__%s__scale%s" % (out["region"], out["input_time"].replace(":", "").replace("-", ""), a.lead_scale)
        (a.out_dir / (tag + ".full.json")).write_text(json.dumps(out, default=str))
        s = summarize(out, rule)
        (a.out_dir / (tag + ".summary.json")).write_text(json.dumps(s, indent=1, default=str))
        print(tag, "origins", len(s["origins"]), "wall", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
