"""Contract conformance with the recorded inputs present (skipped when they are not)."""
import json

import numpy as np
import pytest

from .conftest import INPUTS, body_from_recorded, needs_data, needs_kit, scenario_set_for, wait_job
from .contract_check import assert_conforms

pytestmark = needs_data
REGIONS = {"uljin_2022": "울진", "miryang_2022": "밀양", "hongseong_2023": "홍성", "uiseong_andong_2025": "의성·안동", "yeongdeok_2025": "영덕"}


def test_health_ok(client):
    r = client.get("/v1/health")
    assert_conforms(r, "/health")
    assert sorted(r.json()["regions"]) == sorted(REGIONS)


def test_regions(client):
    r = client.get("/v1/regions")
    assert_conforms(r, "/regions")
    regs = {x["id"]: x for x in r.json()["regions"]}
    assert {k: v["name_ko"] for k, v in regs.items()} == REGIONS
    for rid, reg in regs.items():
        lon0, lat0, lon1, lat1 = reg["bbox"]
        assert 124 < lon0 < lon1 < 132 and 33 < lat0 < lat1 < 39
        assert reg["node_count"] > 0 and reg["edge_count"] > 0 and reg["grid"]["resolution_m"] == 375
        assert len(reg["input_times"]) == 3 and len(reg["scenario_sets"]) == 3
        for s in reg["scenario_sets"]:
            assert len(s["scenario_ids"]) == 4 and all(i.startswith(s["scenario_set_id"] + ":") for i in s["scenario_ids"])
    prov = r.json()["provenance"]
    assert prov["package"] == "wfg_latest" and prov["kit"] == "v3" and prov["checkpoint"].startswith("c651f672")


def _packet_current(region, tag):
    with np.load(INPUTS / "packets" / region / tag / "constructed_arrays.npz") as z:
        return z["current_active"]


@pytest.mark.parametrize("region", sorted(REGIONS))
def test_forecast_all_recorded_times(client, region):
    reg = {x["id"]: x for x in client.get("/v1/regions").json()["regions"]}[region]
    for t in reg["input_times"]:
        r = client.get("/v1/regions/%s/forecast" % region, params={"input_time": t})
        assert_conforms(r, "/regions/{region}/forecast")
        fc = r.json()
        H, W = reg["grid"]["height"], reg["grid"]["width"]
        assert len(fc["features"]) == H * W
        tag = t.replace("-", "").replace(":", "")
        assert sum(f["properties"]["burning_now"] for f in fc["features"]) == int(_packet_current(region, tag).sum())
        for f in fc["features"]:
            p = f["properties"]
            assert 0.0 <= p["p_new_burn_1h"] <= 1.0
            if not p["valid"]:
                assert p["p_new_burn_1h"] == 0.0     # policy zero
        assert fc["provenance"]["checkpoint"].startswith("c651f672") and "forecast_export" in fc["provenance"]["input_hashes"]
        nz = client.get("/v1/regions/%s/forecast" % region, params={"input_time": t, "only_nonzero": True}).json()
        assert all(f["properties"]["p_new_burn_1h"] > 0 or f["properties"]["burning_now"] for f in nz["features"])


def test_forecast_errors(client):
    r = client.get("/v1/regions/nowhere/forecast", params={"input_time": "2022-03-04T03:00:00Z"})
    assert_conforms(r, "/regions/{region}/forecast"); assert r.status_code == 404
    r = client.get("/v1/regions/uljin_2022/forecast", params={"input_time": "2022-03-04T04:00:00Z"})
    assert_conforms(r, "/regions/{region}/forecast"); assert r.status_code == 404
    r = client.get("/v1/regions/uljin_2022/forecast", params={"input_time": "2022-03-04T03:30:00Z"})
    assert_conforms(r, "/regions/{region}/forecast"); assert r.status_code == 422
    r = client.get("/v1/regions/uljin_2022/forecast")
    assert_conforms(r, "/regions/{region}/forecast"); assert r.status_code == 422


@pytest.fixture(scope="module")
def hs_sid(client):
    return {t: scenario_set_for(client, "hongseong_2023", t) for t in ("20230402T070000Z", "20230402T140000Z", "20230402T230000Z")}


def _post(client, body, code=None):
    r = client.post("/v1/route-checks", json=body)
    assert_conforms(r, "/route-checks", "post")
    if code:
        assert r.status_code == 422 and r.json()["error"]["code"] == code, r.json()
    return r


def test_route_check_rejections(client, hs_sid):
    b = body_from_recorded("hongseong_2023", "20230402T230000Z_FD1", hs_sid["20230402T230000Z"])
    _post(client, dict(b, start={"lon": 126.0, "lat": 36.0}), "SNAP_TOO_FAR")
    _post(client, dict(b, region="atlantis"), "UNKNOWN_REGION")
    _post(client, dict(b, input_time="2023-04-02T08:00:00Z"), "INPUT_TIME_UNAVAILABLE")
    _post(client, dict(b, input_time="2023-04-02T08:30:00Z"), "INVALID_INPUT_TIME")
    _post(client, dict(b, fire_input={"type": "recorded", "scenario_set_id": "ffb1:nope"}), "UNKNOWN_SCENARIO_SET")
    _post(client, dict(b, fire_input={"type": "recorded", "scenario_set_id": hs_sid["20230402T070000Z"]}), "SCENARIO_SET_TIME_MISMATCH")
    _post(client, dict(b, destination=b["start"]), "START_EQUALS_DESTINATION")
    _post(client, dict(b, destination_window=[0, 100]), "WINDOW_UNSATISFIABLE")
    _post(client, dict(b, depart_offset_s=0.5), "NOT_ON_TIME_LATTICE")
    _post(client, dict(b, depart_offset_s=4000), "DEPARTURE_OUTSIDE_HORIZON")
    _post(client, dict(b, destination_window=[500, 400]), "INVALID_WINDOW")
    _post(client, dict(b, start={"node_id": "osm:0"}), "UNKNOWN_NODE")
    zone = {"type": "Feature", "properties": {"arrival_h_max": 5},
            "geometry": {"type": "Polygon", "coordinates": [[[127.5, 37.5], [127.6, 37.5], [127.6, 37.6], [127.5, 37.6], [127.5, 37.5]]]}}
    _post(client, dict(b, fire_input={"type": "spread_zones", "issued_at": "2023-04-02T22:00:00Z",
                                      "zones": {"type": "FeatureCollection", "features": [zone]}}), "ZONES_OUTSIDE_REGION")


def test_lonlat_snapping_reports_distance(client, hs_sid):
    from api.regions import to_5179, to_wgs84
    reg = {x["id"]: x for x in client.get("/v1/regions").json()["regions"]}["hongseong_2023"]
    b = body_from_recorded("hongseong_2023", "20230402T070000Z_FN1", hs_sid["20230402T070000Z"])
    q = json.loads((INPUTS / "requests/hongseong_2023/20230402T070000Z_FN1.json").read_text())
    g = json.loads((INPUTS.parent / "graphs/hongseong_2023/graph.json").read_text())
    n = [x for x in g["nodes"] if x["id"] == q["position"]["node"]][0]
    lon, lat = to_wgs84(n["x"] + 3.0, n["y"] + 4.0)        # 5 m away in EPSG:5179
    r = client.post("/v1/route-checks", json=dict(b, start={"lon": float(lon), "lat": float(lat)}))
    assert_conforms(r, "/route-checks", "post")
    snap = r.json()["snap"]["start"]
    assert snap["input"] == "lonlat" and snap["distance_m"] <= 5.01
    assert reg["allowed_node_count"] > 0


@needs_kit
def test_route_check_lifecycle_and_exports(client, hs_sid):
    """A scoped refusal (Hongseong FN1) and a checked route (Hongseong FD1), end to end, every response validated."""
    refusal = _post(client, body_from_recorded("hongseong_2023", "20230402T070000Z_FN1", hs_sid["20230402T070000Z"]))
    route = _post(client, body_from_recorded("hongseong_2023", "20230402T230000Z_FD1", hs_sid["20230402T230000Z"]))
    assert refusal.status_code == 202 and route.status_code == 202
    rid = route.json()["job_id"]
    early = client.get("/v1/route-checks/%s/export" % rid, params={"format": "geojson"})
    if early.status_code == 409:
        assert_conforms(early, "/route-checks/{job_id}/export")
        assert early.json()["error"]["code"] == "JOB_NOT_DONE"
    for jid, verdict in ((refusal.json()["job_id"], "model_no_route"), (rid, "checked_route")):
        j = wait_job(client, "/v1/route-checks/" + jid)
        r = client.get("/v1/route-checks/" + jid)
        assert_conforms(r, "/route-checks/{job_id}")
        res = j["result"]
        assert j["status"] == "done" and res["verdict"] == verdict, res
        p = res["provenance"]
        assert p["evaluated_configuration"] is True and p["recorded_mission_match"] and p["clock"]
        assert {"graph", "hazard", "request"} <= set(p["input_hashes"]) and len(p["scenario_ids"]) == 4
    res = client.get("/v1/route-checks/" + rid).json()["result"]
    assert res["arrival_s"] == 531 and res["dwell_end_s"] == 651 and res["lower_bound_L_s"] == 531
    props = res["route"]["properties"]
    assert len(props["times_s"]) == len(res["route"]["geometry"]["coordinates"]) == len(props["node_ids"])
    assert props["times_s"][0] == res["departure_s"] and props["times_s"][-1] == res["arrival_s"]
    assert all(e["contact"] is False and e["peak_kw_m2"] <= 10 for e in res["exposure"])
    assert res["compute_s"] is not None and res["within_budget"] is (res["compute_s"] <= 30)
    for fmt, media in (("geojson", "application/geo+json"), ("kml", "application/vnd.google-earth.kml+xml"), ("csv", "text/csv")):
        e = client.get("/v1/route-checks/%s/export" % rid, params={"format": fmt})
        assert_conforms(e, "/route-checks/{job_id}/export")
        assert e.status_code == 200 and e.headers["content-type"].startswith(media)
    assert client.get("/v1/route-checks/%s/export" % rid, params={"format": "csv"}).text.splitlines()[0] == "seq,node_id,lon,lat,time_s,event"
    e = client.get("/v1/route-checks/%s/export" % refusal.json()["job_id"], params={"format": "geojson"})
    assert_conforms(e, "/route-checks/{job_id}/export")
    assert e.status_code == 409 and e.json()["error"]["code"] == "NO_CHECKED_ROUTE"
    e = client.get("/v1/route-checks/%s/export" % rid, params={"format": "shp"})
    assert_conforms(e, "/route-checks/{job_id}/export"); assert e.status_code == 422


@needs_kit
def test_reduced_policy_reports_full_policy_assessment(client, hs_sid):
    b = body_from_recorded("hongseong_2023", "20230402T070000Z_FX1", hs_sid["20230402T070000Z"], policy="travel_only")
    j = wait_job(client, "/v1/route-checks/" + _post(client, b).json()["job_id"])
    assert_conforms(client.get("/v1/route-checks/" + j["job_id"]), "/route-checks/{job_id}")
    res = j["result"]
    # recorded ablation A0 for this mission: own-policy route at 551 s (110 legs) that fails FLAME and whole-road contact
    assert res["verdict"] == "checked_route" and res["arrival_s"] == 551 and res["route"]["properties"]["legs_total"] == 110
    fpa = res["full_policy_assessment"]
    assert fpa["passes_full_centre_and_contact"] is False and {"FLAME", "WHOLE_ROAD_CONTACT"} <= {v["constraint"] for v in fpa["violations"]}
    assert all(e["basis"] == "full_model_centre_check" for e in res["exposure"]) and any(e["contact"] for e in res["exposure"])
    assert res["provenance"]["evaluated_configuration"] is False


@needs_kit
def test_spread_zones_route_check(client, hs_sid):
    def rect(lon0, lat0, lon1, lat1, h):
        return {"type": "Feature", "properties": {"arrival_h_max": h},
                "geometry": {"type": "Polygon", "coordinates": [[[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]]}}
    b = body_from_recorded("hongseong_2023", "20230402T230000Z_FD1", hs_sid["20230402T230000Z"])
    b["fire_input"] = {"type": "spread_zones", "issued_at": "2023-04-02T22:00:00Z", "margin_min": 60,
                       "zones": {"type": "FeatureCollection", "features": [rect(126.49, 36.55, 126.51, 36.57, 5), rect(126.48, 36.54, 126.52, 36.58, 8)]}}
    j = wait_job(client, "/v1/route-checks/" + _post(client, b).json()["job_id"])
    assert_conforms(client.get("/v1/route-checks/" + j["job_id"]), "/route-checks/{job_id}")
    res = j["result"]
    assert j["status"] == "done" and res["verdict"] in ("checked_route", "model_no_route", "unresolved")
    assert res["provenance"]["approximation"] == "approximation, requires expert review"
    assert res["provenance"]["fire_input_type"] == "spread_zones"
    assert res["provenance"]["scenario_set_id"] != hs_sid["20230402T230000Z"]
    a = res["assumptions"]
    assert a["label"] == "approximation, requires expert review" and a["margin_min"] == 60 and len(a["bands_detail"]) == 2


@needs_kit
def test_dispatch_plan(client, hs_sid):
    body = {"region": "hongseong_2023", "input_time": "2023-04-02T07:00:00Z",
            "fire_input": {"type": "recorded", "scenario_set_id": hs_sid["20230402T070000Z"]},
            "origins": [{"id": "O1", "location": {"node_id": "osm:4267555571"}}, {"id": "FAR", "location": {"lon": 127.0, "lat": 37.0}}],
            "destinations": [{"id": "D1", "location": {"node_id": "osm:6430106206"}, "dwell_s": 120}],
            "depart_offsets_s": [0], "limits": {"dose_kj_m2": 0.059427700720859386}}
    r = client.post("/v1/dispatch-plans", json=body)
    assert_conforms(r, "/dispatch-plans", "post")
    assert r.status_code == 202
    j = wait_job(client, "/v1/dispatch-plans/" + r.json()["job_id"])
    assert_conforms(client.get("/v1/dispatch-plans/" + j["job_id"]), "/dispatch-plans/{job_id}")
    res = j["result"]
    assert j["status"] == "done" and j["progress"] == {"done": 1, "total": 1}
    assert [x["origin_id"] for x in res["rejected_origins"]] == ["FAR"]
    (plan,) = res["plans"]
    # this is the recorded Hongseong FN1 mission (scoped refusal in the campaign)
    assert plan["best_verdict"] == "model_no_route" and plan["latest_checked_depart_offset_s"] is None and plan["urgency_rank"] == 1
    sub = client.get("/v1/route-checks/" + plan["attempts"][0]["route_check_job_id"])
    assert_conforms(sub, "/route-checks/{job_id}")
