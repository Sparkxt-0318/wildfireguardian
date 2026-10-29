"""Derive the extended-horizon exploratory missions (3 h and 6 h) from the 20 frozen Korean requests and record, for each,
the source request file hash and canonical hash (rule: experimental/scenario-members/src/wfg_members/extended.py).

  python research/synthetic-truth/derive_extended_missions.py
Writes research/synthetic-truth/data/extended_panel/MISSIONS.json. These are NOT frozen missions.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import extended, kit  # noqa: E402


def main():
    kit.verify_inputs()
    out = {"label": extended.LABEL, "rule": extended.RULE, "horizons_s": list(extended.HORIZONS), "missions": []}
    for region, tag, event, m in kit.missions():
        p = kit.paths(region, tag, event, m)["request"]
        req = json.loads(p.read_text())
        for H in extended.HORIZONS:
            new, prov = extended.derive(req, H, source_file_sha256=kit.sha256_file(p),
                                        source_name="latest_inputs_try02/requests/%s/%s_%s.json" % (region, tag, m))
            out["missions"].append({"region": region, "cutoff": tag, "event": event, "mission": m, "horizon_s": H,
                                    "extended_id": "%s_%s_H%dh" % (tag, m, H // 3600), "provenance": prov,
                                    "open_intervals": [d["open_intervals"] for d in new["destinations"]]})
    dest = HERE / "data" / "extended_panel" / "MISSIONS.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(dest, len(out["missions"]))


if __name__ == "__main__":
    main()
