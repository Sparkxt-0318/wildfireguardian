"""Contract conformance of every endpoint when the recorded inputs are NOT available (the CI situation)."""
from .contract_check import assert_conforms

BODY = {"region": "uljin_2022", "input_time": "2022-03-04T03:00:00Z", "start": {"lon": 129.3, "lat": 37.0},
        "destination": {"node_id": "osm:4744584066"}, "fire_input": {"type": "recorded", "scenario_set_id": "x"}}


def test_health_degraded_without_inputs(empty_client):
    r = empty_client.get("/v1/health")
    assert_conforms(r, "/health")
    j = r.json()
    assert j["status"] == "degraded" and j["regions"] == []
    assert any("fetch_routing_inputs" in i for i in j["issues"])
    assert j["package"] == "wfg_latest" and j["kit"] == "v3" and j["checkpoint"].startswith("c651f672")


def test_regions_and_forecast_unavailable(empty_client):
    r = empty_client.get("/v1/regions")
    assert_conforms(r, "/regions")
    assert r.status_code == 503 and r.json()["error"]["code"] == "DATA_UNAVAILABLE"
    r = empty_client.get("/v1/regions/uljin_2022/forecast", params={"input_time": "2022-03-04T03:00:00Z"})
    assert_conforms(r, "/regions/{region}/forecast")
    assert r.status_code == 503


def test_route_check_validation_and_unavailable(empty_client):
    r = empty_client.post("/v1/route-checks", json=BODY)
    assert_conforms(r, "/route-checks", "post")
    assert r.status_code == 503
    for bad in ({}, dict(BODY, policy="fastest"), dict(BODY, start={"lon": 200, "lat": 0}),
                dict(BODY, fire_input={"type": "spread_zones"}), dict(BODY, limits={"peak_kw_m2": -1}), dict(BODY, extra=1)):
        r = empty_client.post("/v1/route-checks", json=bad)
        assert_conforms(r, "/route-checks", "post")
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = empty_client.post("/v1/route-checks", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert_conforms(r, "/route-checks", "post")


def test_unknown_jobs_and_exports(empty_client):
    for path, url in (("/route-checks/{job_id}", "/v1/route-checks/rc_missing"), ("/dispatch-plans/{job_id}", "/v1/dispatch-plans/dp_missing"),
                      ("/route-checks/{job_id}/export", "/v1/route-checks/rc_missing/export?format=csv")):
        r = empty_client.get(url)
        assert_conforms(r, path)
        assert r.status_code == 404


def test_dispatch_validation(empty_client):
    origins = [{"id": "o%d" % i, "location": {"lon": 129.3, "lat": 37.0}} for i in range(201)]
    body = {"region": "uljin_2022", "input_time": "2022-03-04T03:00:00Z", "fire_input": {"type": "recorded", "scenario_set_id": "x"},
            "origins": origins, "destinations": [{"id": "d", "location": {"node_id": "osm:1"}}], "depart_offsets_s": [0]}
    r = empty_client.post("/v1/dispatch-plans", json=body)
    assert_conforms(r, "/dispatch-plans", "post")
    assert r.status_code == 422
    body["origins"] = origins[:2]
    r = empty_client.post("/v1/dispatch-plans", json=body)
    assert_conforms(r, "/dispatch-plans", "post")
    assert r.status_code == 503
