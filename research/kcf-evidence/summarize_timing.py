"""Summarize a clean single-process `--timing-only` run of the F-3.1 deadline field on the six planner caches.

Usage (from the repository root):
    python3 research/kcf-evidence/summarize_timing.py RUN_DIR OUT_JSON

RUN_DIR holds the six outputs of `python3 -m deadline_field.reproduce <cache> --timing-only --out RUN_DIR/<stamp>.json`
(see TIMING_RUN.sh) and the optional WALL.txt written by that script. Standard library only.

Reads, for every number printed, the file it came from:
  * field time        : RUN_DIR/<stamp>.json  ->  timing_s.{prepare_packet_model, fields.*, issue_and_witness.*, total_wall}
  * recorded compute  : planner/cache/<region>/<stamp>.json -> route_checks[*].result.compute_s
                        (all 9,722 route-check jobs) and, for the 9,443 planner attempts, F-3.1/results/SUMMARY_final_70f70d7.json
                        -> recorded_compute_s_sum  (this is the 147,900 s quoted in F-3.1/RESULTS.md section 5)
"""
import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
run_dir = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
SUMMARY = "research/harness-2026-11/F-3.1/results/SUMMARY_final_70f70d7.json"
summ = {pathlib.Path(r["cache_file"]).name: r for r in json.loads((ROOT / SUMMARY).read_text())}

rows, host = [], None
for f in sorted(glob.glob(str(ROOT / "planner/cache/*/*.json"))):
    if f.endswith("INDEX.json"):
        continue
    name = pathlib.Path(f).name
    cache = json.loads(pathlib.Path(f).read_text())
    rec_all = sum((j["result"].get("compute_s") or 0.0) for j in cache["route_checks"].values())
    n_all = len(cache["route_checks"])
    r = json.loads((run_dir / name).read_text())
    t = r["timing_s"]
    host = r.get("host")
    rows.append({
        "cache": "planner/cache/" + cache["region_id"] + "/" + name,
        "jobs_all": n_all,
        "attempts": summ[name]["jobs"],
        "recorded_compute_s_all_jobs": rec_all,
        "recorded_compute_s_attempts": summ[name]["recorded_compute_s_sum"],
        "field_s_total_wall_3_variants": t["total_wall"],
        "field_s_router_plus_cert": t["prepare_packet_model"] + t["fields"]["router"] + t["fields"]["cert"]
                                    + t["issue_and_witness"]["router"] + t["issue_and_witness"]["cert"],
        "field_s_cert_only": t["prepare_packet_model"] + t["fields"]["cert"] + t["issue_and_witness"]["cert"],
        "timing_s": t,
        "peak_rss_mib": r["peak_rss_mib"],
        "run_json": str(run_dir.name + "/" + name),
    })

tot = {k: sum(r[k] for r in rows) for k in rows[0] if isinstance(rows[0][k], (int, float)) and k != "peak_rss_mib"}
tot["peak_rss_mib_max"] = max(r["peak_rss_mib"] for r in rows)
res = {
    "host_recorded_in_run_json": host,
    "rows": rows,
    "totals": tot,
    "ratios_recorded_over_field": {
        "all_9722_jobs_vs_total_wall_3_variants": tot["recorded_compute_s_all_jobs"] / tot["field_s_total_wall_3_variants"],
        "all_9722_jobs_vs_router_plus_cert": tot["recorded_compute_s_all_jobs"] / tot["field_s_router_plus_cert"],
        "all_9722_jobs_vs_cert_only": tot["recorded_compute_s_all_jobs"] / tot["field_s_cert_only"],
        "attempts_9443_vs_total_wall_3_variants": tot["recorded_compute_s_attempts"] / tot["field_s_total_wall_3_variants"],
    },
}
wall = run_dir / "WALL.txt"
if wall.exists():
    res["outer_wall_lines"] = wall.read_text().splitlines()
out.write_text(json.dumps(res, indent=1))
print(json.dumps({"host": host, "totals": tot, "ratios": res["ratios_recorded_over_field"]}, indent=1))
