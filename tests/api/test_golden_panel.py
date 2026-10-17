"""Golden replays and the full 20-mission panel through POST /route-checks (recorded inputs, policy full).

Expected values are read from the repository's recorded results (no numbers are typed in here except the three the
task fixes for Uljin FX1: arrival 3,119 s, 512 road legs, 120 s dwell). Requests are submitted one at a time, as in
the campaign's serial controller. A mismatch is reported, never tuned away: on hosts slower than the evaluated native
macOS machine the fixed 30 s budget can turn a recorded route into unresolved/TIMEOUT.
Reports are written to artifacts/api_golden/ and artifacts/api_panel/ (git-ignored).
"""
import json
import platform
import statistics
import time
from pathlib import Path

import pytest

from .conftest import REPO, body_from_recorded, needs_kit, recorded_panel, scenario_set_for, wait_job
from .contract_check import assert_conforms

PANEL = recorded_panel()
GOLDEN = [("uiseong_andong_2025", "20250324T090000Z_FL2"), ("hongseong_2023", "20230402T140000Z_FW2"),
          ("uljin_2022", "20220304T030000Z_FX1")]


def _run(client, mission: dict) -> dict:
    sid = scenario_set_for(client, mission["region"], mission["case_id"].split("_")[0])
    body = body_from_recorded(mission["region"], mission["case_id"], sid, run_independent_check=True)
    t0 = time.time()
    r = client.post("/v1/route-checks", json=body)
    assert_conforms(r, "/route-checks", "post")
    assert r.status_code == 202, r.json()
    j = wait_job(client, "/v1/route-checks/" + r.json()["job_id"])
    assert_conforms(client.get("/v1/route-checks/" + j["job_id"]), "/route-checks/{job_id}")
    res = j["result"] or {}
    props = (res.get("route") or {}).get("properties") or {}
    return {"region": mission["region"], "case_id": mission["case_id"], "job_id": j["job_id"], "status": j["status"],
            "verdict": res.get("verdict"), "reason_code": res.get("reason_code"), "raw_status": res.get("raw_status"),
            "raw_reason": res.get("raw_reason"), "arrival_s": res.get("arrival_s"), "lower_bound_L_s": res.get("lower_bound_L_s"),
            "dwell_s": None if res.get("dwell_end_s") is None else res["dwell_end_s"] - res["arrival_s"],
            "legs_total": props.get("legs_total"), "road_segments": props.get("segment_count"), "route_sha256": props.get("route_sha256"),
            "compute_s": res.get("compute_s"), "within_budget": res.get("within_budget"),
            "independent": (res.get("independent_check") or {}).get("verdict"),
            "recorded_mission_match": (res.get("provenance") or {}).get("recorded_mission_match"),
            "wall_s": time.time() - t0,
            "expected": {k: mission[k] for k in ("verdict", "arrival_s", "n_legs", "route_hash", "recorded_wall_s")}}


def _mismatches(row: dict) -> list:
    e = row["expected"]
    out = []
    if row["verdict"] != e["verdict"]:
        out.append("verdict %s (reason %s, compute_s %s) != recorded %s" % (row["verdict"], row["reason_code"], row["compute_s"], e["verdict"]))
    elif e["verdict"] == "checked_route":
        if row["arrival_s"] != e["arrival_s"]:
            out.append("arrival %s != recorded %s" % (row["arrival_s"], e["arrival_s"]))
        if row["legs_total"] != e["n_legs"]:
            out.append("legs %s != recorded %s" % (row["legs_total"], e["n_legs"]))
        if e["route_hash"] and row["route_sha256"] != e["route_hash"]:
            out.append("route hash %s != recorded %s" % (row["route_sha256"], e["route_hash"]))
    if row["recorded_mission_match"] != row["case_id"]:
        out.append("request is not byte-identical to the recorded mission")
    return out


def _write(name: str, rows: list) -> Path:
    d = REPO / "artifacts" / name
    d.mkdir(parents=True, exist_ok=True)
    cs = [r["compute_s"] for r in rows if r["compute_s"] is not None]
    rep = {"host": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
           "missions": len(rows), "identical": sum(not _mismatches(r) for r in rows),
           "median_compute_s": statistics.median(cs) if cs else None,
           "median_recorded_wall_s": statistics.median([w for r in rows for w in r["expected"]["recorded_wall_s"]]),
           "rows": [dict(r, mismatches=_mismatches(r)) for r in rows]}
    p = d / "REPORT.json"
    p.write_text(json.dumps(rep, indent=1, default=str))
    lines = ["| region | mission | recorded | API verdict | reason | arrival (rec/API) | legs (rec/API) | compute_s | recorded wall_s | match |",
             "|---|---|---|---|---|---|---|---:|---:|---|"]
    for r in rep["rows"]:
        e = r["expected"]
        lines.append("| %s | %s | %s | %s | %s | %s / %s | %s / %s | %s | %s | %s |" % (
            r["region"], r["case_id"], e["verdict"], r["verdict"], r["reason_code"] or "", e["arrival_s"], r["arrival_s"], e["n_legs"],
            r["legs_total"], "%.2f" % r["compute_s"] if r["compute_s"] is not None else "-",
            "/".join("%.2f" % w for w in e["recorded_wall_s"]), "yes" if not r["mismatches"] else "NO"))
    lines.append("")
    lines.append("identical: %d/%d; median compute_s: %s; median recorded wall_s (M5 Pro, both reps): %.3f" % (
        rep["identical"], rep["missions"], rep["median_compute_s"], rep["median_recorded_wall_s"]))
    (d / "REPORT.md").write_text("\n".join(lines) + "\n")
    return p


@pytest.mark.golden
@needs_kit
def test_golden_missions(client):
    missions = [m for key in GOLDEN for m in PANEL if (m["region"], m["case_id"]) == key]
    assert len(missions) == 3
    rows = [_run(client, m) for m in missions]
    _write("api_golden", rows)
    fx1 = rows[-1]
    problems = {"%s/%s" % (r["region"], r["case_id"]): _mismatches(r) for r in rows if _mismatches(r)}
    if fx1["verdict"] == "checked_route":
        assert (fx1["arrival_s"], fx1["legs_total"], fx1["road_segments"], fx1["dwell_s"]) == (3119, 512, 512, 120)
    assert not problems, "golden replay differs from the recorded campaign: %s" % json.dumps(problems, indent=1)


@pytest.mark.panel
@needs_kit
def test_full_final_panel(client):
    rows = [_run(client, m) for m in PANEL]
    path = _write("api_panel", rows)
    bad = {"%s/%s" % (r["region"], r["case_id"]): _mismatches(r) for r in rows if _mismatches(r)}
    assert not bad, "%d/20 identical; report %s; differences: %s" % (20 - len(bad), path, json.dumps(bad, indent=1))
