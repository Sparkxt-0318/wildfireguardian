"""Record the precision verifier's saved results (protocol precision_20261017) in results/NUMBERS.json.

    bash scripts/run_from_head.sh python scripts/record_precision.py

Reads saved reports only (gates.json, the calibration review, selection.json, the C5 development
comparison and the runtime bench); it runs and scores nothing. Every accuracy number rests on
agent-only annotation or review and is PROVISIONAL.
"""
from __future__ import annotations

import json
from pathlib import Path

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import git_state, record_number

SCRIPT = "scripts/record_precision.py"
V = PROJECT_ROOT / "results" / "validation" / "precision_20261017"


def main() -> int:
    if git_state()["git_dirty"]:
        raise SystemExit("recording requires committed source")
    paths = {"gates": V / "gates.json", "cal_review": V / "review_calibration" / "review_points.json",
             "selection": V / "selection.json", "dev": V / "dev" / "c5_dev_comparison.json",
             "bench": V / "runtime" / "bench_linux_rules_q0.3.json"}
    rep = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    cfg = load_config()

    def put(key, value, unit, description, name):
        if value is None:
            return
        record_number(f"precision.{key}", round(value, 6) if isinstance(value, float) else value, unit, description,
                      script=SCRIPT, config=cfg, config_path="configs/default.yaml", inputs={name: paths[name]})

    g = rep["gates"]["gates"]
    p, r, fa = g["precision"], g["recall"], g["false_alarm"]
    put("sealed.accepted_tracks", p["accepted_tracks"], "tracks", "Tracks the selected method accepted on the sealed test", "gates")
    put("sealed.review_true", p["true"], "tracks", "Sealed accepted tracks the blind review judged true", "gates")
    put("sealed.review_false", p["false"], "tracks", "Sealed accepted tracks the blind review judged false", "gates")
    put("sealed.precision_lower95", p["precision_lower95_one_sided"], "fraction", "One-sided 95 percent lower bound of sealed reviewed precision", "gates")
    put("sealed.recall_matched", r["matched"], "tracks", "Observable ember-positive truth tracks matched", "gates")
    put("sealed.recall_observable", r["observable"], "tracks", "Observable ember-positive truth tracks", "gates")
    put("sealed.false_per_min_upper95", fa["review"]["upper95"], "per supported minute", "One-sided 95 percent upper bound of reviewed false accepted tracks per supported minute", "gates")
    put("sealed.supported_minutes", fa["review"]["minutes"], "minutes", "Supported minutes of the scorable sealed recordings", "gates")
    ctl = p.get("control_accept_all") or {}
    put("sealed.control_precision", ctl.get("precision"), "fraction", "Reviewed precision of the accept_all control on the sealed test", "gates")
    put("tests.passed", g["implementation"]["runs"][0]["passed"], "tests", "Tests passed (committed source)", "gates")
    put("tests.failed", g["implementation"]["runs"][0]["failed"], "tests", "Tests failed (committed source)", "gates")

    sel = rep["selection"]
    pts = rep["cal_review"]["points"]
    chosen = sel.get("point") if isinstance(sel.get("point"), dict) else sel.get("selected")
    best = pts[chosen["name"]] if isinstance(chosen, dict) else None
    if best:
        put("calibration.selected_true", best["true"], "tracks", "Reviewed true tracks of the selected calibration point", "cal_review")
        put("calibration.selected_false", best["false"], "tracks", "Reviewed false tracks of the selected calibration point", "cal_review")
        put("calibration.selected_precision", best["precision"], "fraction", "Reviewed precision of the selected calibration point", "cal_review")
        put("calibration.selected_lower95", best["precision_lower95"], "fraction", "One-sided 95 percent lower bound of the selected point's reviewed precision", "cal_review")
    put("calibration.observable_tracks", sel["observable_calibration_truth_tracks"], "tracks", "Observable calibration truth tracks", "selection")

    rows = {row["name"]: row for row in rep["dev"]["rows"]}
    for name, key in (("legacy_raw_detections", "legacy"), ("accept_all", "accept_all")):
        if name in rows:
            put(f"dev_c5.{key}.precision", rows[name]["precision"], "fraction", f"C5 development frame-level precision, {name}", "dev")
    best_dev = max((row for row in rows.values() if row.get("precision") is not None and row["name"] != "legacy_raw_detections"),
                   key=lambda row: row["precision"])
    put("dev_c5.best.precision", best_dev["precision"], "fraction", f"Best C5 development frame-level precision ({best_dev['name']})", "dev")

    for mode in ("legacy", "high_precision"):
        m = rep["bench"]["modes"][mode]
        put(f"bench_linux.{mode}.paint_fps_median", m["paint_fps"]["median"], "fps", f"Median paint rate, {mode}, Linux container reference", "bench")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
