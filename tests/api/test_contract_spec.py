"""The contract file itself and the documentation endpoints (no recorded data needed)."""
import re

from openapi_spec_validator import validate

from .contract_check import CONTRACT, SPEC, assert_conforms

REQUIRED = {
    "/health": {"get"}, "/regions": {"get"}, "/regions/{region}/forecast": {"get"},
    "/route-checks": {"post"}, "/route-checks/{job_id}": {"get"}, "/route-checks/{job_id}/export": {"get"},
    "/dispatch-plans": {"post"}, "/dispatch-plans/{job_id}": {"get"},
}


def test_contract_is_valid_openapi_31():
    assert SPEC["openapi"] == "3.1.0"
    validate(SPEC)


def test_contract_paths_and_server():
    assert {p: set(v) for p, v in SPEC["paths"].items()} == REQUIRED
    assert SPEC["servers"][0]["url"] == "http://127.0.0.1:8765/v1"


def test_contract_enums_fixed_by_the_task():
    s = SPEC["components"]["schemas"]
    assert s["Verdict"]["enum"] == ["checked_route", "model_no_route", "unresolved"]
    assert s["JobStatus"]["enum"] == ["queued", "running", "done", "failed"]
    assert s["Policy"]["enum"] == ["full", "travel_only", "flame_only", "flame_peak", "flame_dose"] and s["Policy"]["default"] == "full"
    assert s["DispatchPlanRequest"]["properties"]["origins"]["maxItems"] == 200
    for k in ("verdict", "reason_code", "arrival_s", "lower_bound_L_s", "dwell_end_s", "route", "exposure", "compute_s", "provenance"):
        assert k in s["RouteCheckResult"]["required"]
    for k in ("api_version", "package", "kit", "checkpoint", "git_commit", "input_hashes", "scenario_ids"):
        assert k in s["Provenance"]["required"]


def test_changelog_records_contract_version():
    log = (CONTRACT.parent / "CHANGELOG.md").read_text()
    major_minor = ".".join(SPEC["info"]["version"].split(".")[:2])
    assert ("v%s" % major_minor) in log


def test_openapi_json_is_the_contract(empty_client):
    for url in ("/openapi.json", "/v1/openapi.json"):
        r = empty_client.get(url)
        assert r.status_code == 200 and r.json() == SPEC


def test_docs_are_served_offline_with_korean_descriptions(empty_client):
    r = empty_client.get("/docs")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    html = r.text
    assert "/static/swagger-ui/swagger-ui-bundle.js" in html and "/openapi.json" in html
    external = [u for u in re.findall(r'(?:src|href)="([^"]+)"', html) if u.startswith(("http://", "https://", "//"))]
    assert not external, "docs page loads external assets: %s" % external
    for asset in ("swagger-ui-bundle.js", "swagger-ui.css"):
        assert empty_client.get("/static/swagger-ui/" + asset).status_code == 200
    assert "경로 점검" in SPEC["paths"]["/route-checks"]["post"]["summary"]


def test_error_envelope_for_unknown_route(empty_client):
    r = empty_client.get("/v1/route-checks/does-not-exist")
    assert_conforms(r, "/route-checks/{job_id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "JOB_NOT_FOUND"
