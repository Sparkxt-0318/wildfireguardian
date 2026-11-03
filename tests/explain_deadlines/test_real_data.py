"""The committed explanation files (planner/public/data/explanations) against the recorded inputs.

Skipped when the frozen routing inputs are not installed (python tools/fetch_routing_inputs.py).
"""
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from tools.explain_deadlines.cli import EVALUATED_HOST_PLATFORM, RUN_STAMPS, compact, main as cli_main
from tools.explain_deadlines.explain import REASONS, STATUSES
from tools.explain_deadlines.plans import CacheModel

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "planner" / "public" / "data" / "explanations"
INDEX = json.loads((REPO / "planner" / "cache" / "INDEX.json").read_text())
HAVE_INPUTS = (REPO / "data" / "routing" / "INPUT_FILES.json").is_file()
pytestmark = pytest.mark.skipif(not HAVE_INPUTS, reason="frozen routing inputs not installed (python tools/fetch_routing_inputs.py)")

ITEM_KEYS = {"edge_id", "label_ko", "label_en", "label_source", "flame_time_s", "members", "members_total",
             "pass_time_at_deadline_s", "slack_s"}
ORIGIN_KEYS = {"status", "verdict_summary", "deadline_offset_s", "next_offset_s", "next_verdict", "reason_code", "binding",
               "exits", "notes"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def out_path(e):
    return OUT / ("%s__%s.json" % (e["region_id"], compact(e["input_time"])))


def test_one_file_per_cache_file():
    assert sorted(p.name for p in OUT.glob("*.json")) == sorted(out_path(e).name for e in INDEX)
    assert len(INDEX) == 6


@pytest.mark.parametrize("entry", INDEX, ids=[e["path"] for e in INDEX])
def test_file_matches_its_inputs_and_the_planner(entry):
    d = json.loads(out_path(entry).read_text())
    assert d["schema"] == "wfg.explanation/1"
    assert (d["region_id"], d["input_time"], d["scenario_set_id"]) == (entry["region_id"], entry["input_time"], entry["scenario_set_id"])
    p = d["provenance"]
    cache = REPO / "planner" / "cache" / entry["path"]
    assert p["cache_sha256"] == sha(cache) == entry["sha256"]
    assert p["graph_sha256"] == sha(REPO / "data" / "routing" / "graphs" / entry["region_id"] / "graph.json")
    for name, h in p["packet_hashes"].items():
        assert sha(REPO / p["packet_dir"] / name) == h
    assert p["code_dirty"] is False and len(p["code_commit"]) == 40
    # where the explanation was computed; evaluated_host only for a native macOS arm64 run (--evaluated-host)
    host = p["computed_on"]
    assert set(host) == {"platform", "system", "machine", "python", "numpy", "pyproj"}
    assert p["evaluated_host"] is False or (host["system"], host["machine"]) == EVALUATED_HOST_PLATFORM
    raw = json.loads(cache.read_text())
    # every recorded checked route and every travel-only route of the cache file was replayed (counted independently here)
    n_checked = sum(1 for j in raw["route_checks"].values() if (j.get("result") or {}).get("verdict") == "checked_route")
    n_travel = sum(1 for j in raw["travel_only"].values() if (j.get("result") or {}).get("verdict") == "checked_route")
    v = d["summary"]["validation"]
    assert v["replay_checked_routes"] == {"unit": "route", "routes": n_checked, "contact_free": n_checked, "mismatches": 0,
                                          "not_replayed": 0, "applicable": n_checked, "passed": n_checked, "failed": 0}
    rt = v["replay_travel_only"]
    assert (rt["entries"], rt["routes"], rt["matches"], rt["mismatches"], rt["not_replayed"], rt["member_flags"]) == \
        (len(raw["travel_only"]), n_travel, n_travel, 0, 0, 4 * n_travel)
    assert rt["with_contact"] == sum(1 for j in raw["travel_only"].values()
                                     if any(s["contact"] for s in j["result"]["full_policy_assessment"]["per_scenario"].values()))
    plans = CacheModel(raw).plans
    assert set(d["origins"]) == set(plans)                     # keyed exactly as the planner keys origins
    s = d["summary"]
    assert s["explained"] + s["explained_partial"] + s["not_explainable"] == s["origins"] == len(plans)
    assert sum(s["by_reason"].values()) == len(plans)
    assert all(v["failed"] == 0 for v in s["validation"].values())
    H = p["horizon_s"]
    for oid, o in d["origins"].items():
        assert ORIGIN_KEYS <= set(o), oid
        assert o["status"] in STATUSES and o["reason_code"] in REASONS
        assert all(v is True for v in o["checks"].values()), oid
        plan = plans[oid]
        assert o["verdict_summary"] == plan.best_verdict and o["deadline_offset_s"] == plan.latest_s
        if plan.latest_s is not None:
            later = [c for c in plan.sweep if c.offset_s > plan.latest_s]
            assert o["next_offset_s"] == (later[0].offset_s if later else None)
        if o["verdict_summary"] == "unresolved":
            assert o["status"] == "not_explainable" and not o["binding"] and not o["exits"]
        if o["reason_code"] == "unresolved_next":
            assert o["status"] == "not_explainable" and o["next_verdict"] == "unresolved" and not o["binding"]
        assert bool(o["binding"]) == (o["reason_code"] in ("flame_on_route", "dwell_at_destination"))
        assert bool(o["exits"]) == (o["reason_code"] == "all_exits_blocked" and o["detail_code"] != "entry_point_in_flame")
        for it in o["binding"] + o["exits"]:
            assert ITEM_KEYS <= set(it)
            assert it["members_total"] == 4 and 1 <= len(it["members"]) <= 4 and set(it["members"]) <= {0, 1, 2, 3}
            assert it["label_source"] in ("osm_name", "osm_ref", "nearest_place", "unnamed")
            for k in ("flame_time_s", "contact_time_s", "pass_time_at_deadline_s"):
                if it.get(k) is not None:
                    assert 0 <= it[k] <= H
        for it in o["binding"]:
            assert 0 < it["slack_s"] <= o["next_offset_s"] - o["deadline_offset_s"]
            assert it["pass_time_at_deadline_s"] < it["flame_time_s"]
        for it in o["binding"] + o["exits"]:
            assert it["place_is_origin"] == (it["place_osm_id"] is not None and "osm:" + it["place_osm_id"] == oid)
        sh = o.get("shelters_next")
        if o["next_verdict"] == "model_no_route" and o["verdict_summary"] == "checked_route":
            # every shelter checked at D and every shelter tried at N is accounted for
            ids = {x["destination_id"] for x in sh}
            assert set(o["destination_classes"]) <= ids and sum(x["checked_at_deadline"] for x in sh) == o["checked_at_deadline"]
            fits = [x for x in sh if x["fire_free_fits"]]
            for x in sh:
                assert x["fire_free_fits"] == (x["fire_free_end_s"] is not None and x["fire_free_end_s"] <= x["close_s"])
            if o["deadline_cause"] == "time_window":
                assert not fits and o["reason_code"] == "window" and o["detail_code"] == "window_fire_free"
            if o["deadline_cause"] == "flames":
                assert any(x["proven"] for x in fits) and o["reason_code"] in ("flame_on_route", "no_flame_avoiding_route", "dwell_at_destination")
        if o["reason_code"] == "window" and o["detail_code"] == "window_fire_free":
            # the time window alone: no shelter considered at N would be reached in time even without fire
            assert o["deadline_cause"] == "time_window" and all(x["fire_free_fits"] is False for x in sh)
            w = o["window"]
            assert w["fire_free"] and (w["fastest_end_s"] is None or w["fastest_end_s"] > w["close_s"])
        if o["reason_code"] == "no_flame_avoiding_route":
            assert o["deadline_cause"] == "flames"


def test_replay_totals_over_the_six_files():
    """README section 5: 7,771 recorded checked routes replayed flame-free; 507 travel-only routes whose per-member
    contact flags equal the API's full-policy assessment (10 of them with contact in some member)."""
    tot = {"checked": 0, "contact_free": 0, "travel": 0, "matches": 0, "with_contact": 0}
    for e in INDEX:
        v = json.loads(out_path(e).read_text())["summary"]["validation"]
        tot["checked"] += v["replay_checked_routes"]["routes"]
        tot["contact_free"] += v["replay_checked_routes"]["contact_free"]
        tot["travel"] += v["replay_travel_only"]["routes"]
        tot["matches"] += v["replay_travel_only"]["matches"]
        tot["with_contact"] += v["replay_travel_only"]["with_contact"]
    assert tot == {"checked": 7771, "contact_free": 7771, "travel": 507, "matches": 507, "with_contact": 10}


def test_regeneration_is_identical(tmp_path):
    """Regenerate the smallest file from the same inputs and compare every field but the run stamps."""
    entry = [e for e in INDEX if e["path"] == "yeongdeok_2025/20250326T080000Z.json"][0]
    assert cli_main(["generate", "--only", entry["path"], "--out", str(tmp_path), "--no-kit"]) == 0
    a = json.loads((tmp_path / out_path(entry).name).read_text())
    b = json.loads(out_path(entry).read_text())
    for d in (a, b):
        for k in (*RUN_STAMPS, "kit_checker_sha256"):
            d["provenance"].pop(k, None)
        d["summary"]["validation"] = {k: v for k, v in d["summary"]["validation"].items() if not k.startswith("kit_")}
        for o in d["origins"].values():
            o["checks"] = {k: v for k, v in o["checks"].items() if not k.startswith("kit_")}
    assert a == b
