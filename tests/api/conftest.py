"""Shared fixtures for the Route-Check API tests.

Tests that need data which is not in the repository are SKIPPED with an explicit reason:
  * recorded routing inputs (python tools/fetch_routing_inputs.py -> data/routing), and
  * GNU /usr/bin/time and /bin/ps, which the kit controller uses to launch and measure every request.
Markers: ``golden`` (three recorded final-panel missions) and ``panel`` (all 20 missions) are slow and timing-sensitive;
run them on a quiet machine with ``make api-golden`` / ``make api-panel``.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DATA = Path(os.environ.get("WFG_API_DATA_ROOT", REPO / "data" / "routing")).resolve()
INPUTS = DATA / "latest_inputs_try02"
HAS_DATA = (DATA / "graphs").is_dir() and (INPUTS / "packets").is_dir() and (INPUTS / "requests").is_dir()
HAS_TOOLS = os.access("/usr/bin/time", os.X_OK) and os.access("/bin/ps", os.X_OK)

needs_data = pytest.mark.skipif(not HAS_DATA, reason="SKIPPED (data not in repo): recorded routing inputs missing; "
                                                      "run `python tools/fetch_routing_inputs.py`")
needs_kit = pytest.mark.skipif(not (HAS_DATA and HAS_TOOLS),
                               reason="SKIPPED (data/tools not in repo): needs recorded routing inputs and GNU /usr/bin/time + "
                                      "/bin/ps for the kit controller")


def pytest_configure(config):
    config.addinivalue_line("markers", "golden: replays three recorded final-panel missions through POST /route-checks")
    config.addinivalue_line("markers", "panel: runs all 20 final-panel missions once through the API")


def _settings(data_root: Path, runtime: Path):
    from api.config import Settings, load_settings
    s = load_settings()
    return Settings(data_root=data_root, runtime_dir=runtime, workers=s.workers, python=s.python, host=s.host, port=s.port)


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient
    from api.app import create_app
    with TestClient(create_app(_settings(DATA, tmp_path_factory.mktemp("api_runtime")))) as c:
        yield c


@pytest.fixture(scope="session")
def empty_client(tmp_path_factory):
    """An API instance whose data root does not exist (CI without recorded inputs)."""
    from fastapi.testclient import TestClient
    from api.app import create_app
    root = tmp_path_factory.mktemp("no_data") / "routing"
    with TestClient(create_app(_settings(root, tmp_path_factory.mktemp("api_runtime_empty")))) as c:
        yield c


def wait_job(client, url, timeout=900):
    t0 = time.time()
    while True:
        j = client.get(url).json()
        if j.get("status") in ("done", "failed"):
            return j
        if time.time() - t0 > timeout:
            raise AssertionError("job %s did not finish within %s s" % (url, timeout))
        time.sleep(0.5)


# ------------------------------------------------------------------------------------------- recorded panel
MISSION_KEYS = ("region", "case_id")


def recorded_panel() -> list:
    """The 20 final-panel missions with their recorded candidate outcome, read from the repository's result files
    (research/routing/INDEPENDENT_ROWS.csv for verdict/arrival, final-input-ablation ROWS.csv A4 for legs and route hash)."""
    rows = list(csv.DictReader((REPO / "research/routing/INDEPENDENT_ROWS.csv").open()))
    abl = list(csv.DictReader((REPO / "research/routing/final-input-ablation/data/ROWS.csv").open()))
    state_map = {"CHECKED_CENTRE_OPTIMUM": "checked_route", "CERTIFIED_CENTRE_REFUSAL": "model_no_route"}
    out = {}
    for r in rows:
        if r["arm"] != "RDA_CAND":
            continue
        key = (r["region"], r["case_id"])
        v = state_map.get(r["state"], "unresolved")
        arr = int(r["arrival"]) if r["arrival"] not in ("", None) else None
        e = out.setdefault(key, {"region": r["region"], "case_id": r["case_id"], "verdicts": set(), "arrivals": set(), "wall_s": []})
        e["verdicts"].add(v); e["arrivals"].add(arr); e["wall_s"].append(float(r["wall_s"]))
    for a in abl:
        if a["policy"] != "A4":
            continue
        e = out.get((a["cohort"], a["case_id"]))
        if e is not None:
            e.setdefault("n_legs", set()).add(int(a["n_legs"]) if a["n_legs"] else None)
            e.setdefault("route_hash", set()).add(a["route_hash"] or None)
    panel = []
    for key in sorted(out):
        e = out[key]
        assert len(e["verdicts"]) == 1 and len(e["arrivals"]) == 1, "recorded repetitions disagree for %s" % (key,)
        panel.append({"region": e["region"], "case_id": e["case_id"], "verdict": e["verdicts"].pop(), "arrival_s": e["arrivals"].pop(),
                      "n_legs": (e.get("n_legs") or {None}).pop(), "route_hash": (e.get("route_hash") or {None}).pop(),
                      "recorded_wall_s": e["wall_s"]})
    return panel


def mission_request(region: str, case_id: str) -> dict:
    return json.loads((INPUTS / "requests" / region / (case_id + ".json")).read_text())


def body_from_recorded(region: str, case_id: str, scenario_set_id: str, **extra) -> dict:
    """An API body that restates a recorded mission (node ids, departure, dwell, window, limits, incurred dose)."""
    q = mission_request(region, case_id)
    d = q["destinations"][0]
    doses = set(q["budgets"]["dose"].values()); inc = set(q["incurred"].values())
    assert len(doses) == 1 and len(inc) == 1 and len(q["destinations"]) == 1 and len(d["open_intervals"]) == 1
    body = {"region": region, "input_time": case_id.split("_")[0], "start": {"node_id": q["position"]["node"]},
            "destination": {"node_id": d["node"]}, "depart_offset_s": q["departure"], "dwell_s": d["dwell"],
            "destination_window": d["open_intervals"][0], "policy": "full",
            "limits": {"peak_kw_m2": q["budgets"]["peak"], "dose_kj_m2": doses.pop()}, "incurred_dose_kj_m2": inc.pop(),
            "fire_input": {"type": "recorded", "scenario_set_id": scenario_set_id}}
    body.update(extra)
    return body


def scenario_set_for(client, region: str, tag: str) -> str:
    iso = "%s-%s-%sT%s:00:00Z" % (tag[0:4], tag[4:6], tag[6:8], tag[9:11])
    regs = {r["id"]: r for r in client.get("/v1/regions").json()["regions"]}
    return [s for s in regs[region]["scenario_sets"] if s["input_time"] == iso][0]["scenario_set_id"]
