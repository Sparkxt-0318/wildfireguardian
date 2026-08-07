"""PHASE 22 — the transport, and the gate on what it sends.

The routing is NOT re-tested here. It has its own regression, and an API test
that asserted 414/42/2 would be a fifth place for those numbers to live. What is
tested is what the transport can get wrong on its own: status codes, the job
lifecycle, parameters that must not be settable over HTTP, and the rule that no
response may carry a URL a browser could fetch.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from wildfireguardian.api import create_app  # noqa: E402
from wildfireguardian.api.guard import (  # noqa: E402
    ExternalReferenceError, assert_offline, find_external_refs,
)
from wildfireguardian.service import jobs as _jobs  # noqa: E402
from wildfireguardian.service import resources as _resources  # noqa: E402
from wildfireguardian.service import routing as _routing  # noqa: E402


# ---------------------------------------------------------------------------
# 1. The offline gate on responses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", [
    {"doc": "https://fonts.googleapis.com/css2?family=X"},
    {"nested": [{"see": "http://example.com/a.js"}]},
    {"ws": "wss://events.example.com/stream"},
    {"file": "file:///Users/someone/secret.txt"},
    {"protocol_relative": "//cdn.example.com/lib.js"},
    {"https://key.example.com/": "even in a key"},
])
def test_a_fetchable_url_anywhere_in_a_payload_is_caught(payload):
    assert find_external_refs(payload), payload
    with pytest.raises(ExternalReferenceError):
        assert_offline(payload)


@pytest.mark.parametrize("payload", [
    {"path": "data/processed/routing_demo_canonical.npz"},
    {"sha256": "81b4e4d159daa7a8" * 4},
    {"ko": "기상 자료: 2025-03-25 12:25 UTC 기준 (ERA5는 약 5일 지연 발행)"},
    {"svg": "http://www.w3.org/2000/svg"},
    {"xlink": "http://www.w3.org/1999/xlink"},
    {"ratio": "125~530 m"},
    {"version": "osmnx 2.0.7"},
    {"not_a_url": "see docs/service_layer.md §5.1"},
])
def test_ordinary_payload_content_is_not_flagged(payload):
    assert find_external_refs(payload) == [], payload
    assert assert_offline(payload) is payload


def test_the_namespace_exemption_matches_the_static_gate_exactly():
    """The two gates must not disagree about what counts as a URL."""
    from check_screen_assets import NAMESPACE_IDENTIFIERS as STATIC

    from wildfireguardian.api.guard import NAMESPACE_IDENTIFIERS as WIRE
    assert STATIC == WIRE, (
        "the file gate and the response gate exempt different strings; one of "
        "them is now wrong and nobody will notice which")


def test_the_error_names_the_urls_rather_than_scrubbing_them():
    with pytest.raises(ExternalReferenceError) as ei:
        assert_offline({"a": "https://cdn.example.com/x.js"}, where="test")
    assert "cdn.example.com" in str(ei.value)
    assert ei.value.urls == ["https://cdn.example.com/x.js"]


# ---------------------------------------------------------------------------
# 2. The transport, against a stubbed runner
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch):
    """A real app over a runner whose work is a controllable sleep."""
    gate = threading.Event()
    gate.set()

    def _fake(request, *, cache, run_id=None, progress=None, should_cancel=None,
              repo=None):
        gate.wait(timeout=10)
        if progress is not None:
            progress.begin("routing", 4)
            for _ in range(4):
                if should_cancel is not None and should_cancel():
                    from wildfireguardian.live.pipeline import RoutingCancelled
                    raise RoutingCancelled("cancelled after 0 of 4 origins")
                progress.advance("routing")
            progress.finish("routing")
        return {"run_id": run_id, "counts": {"both_safe": 414},
                "n_scanned": 458,
                "determinism_key": request.determinism_key(),
                "hazard_npz": "data/processed/routing_demo_canonical.npz"}

    monkeypatch.setattr(_jobs, "route_from_ignition", _fake)
    runner = _jobs.JobRunner(cache=_resources.ResourceCache(capacity=1),
                             max_workers=1, max_queue=4)
    app = create_app(runner=runner)
    with TestClient(app) as c:
        c._gate = gate          # type: ignore[attr-defined]
        yield c
    runner.shutdown(wait=False)


def _body(**over):
    w, s, e, n = _routing.walk_bbox("yeongdeok_2025")
    return {"region": "yeongdeok_2025", "lat": (s + n) / 2, "lon": (w + e) / 2,
            **over}


def test_health_reports_startup_and_the_cache(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and "runner" in d
    assert "resource_cache" in d["runner"]


def test_regions_lists_every_registered_region(client):
    d = client.get("/api/regions").json()
    assert {x["region"] for x in d["regions"]} == set(_routing.known_regions())


def test_submit_returns_202_and_a_job_id_without_waiting(client):
    t0 = time.monotonic()
    r = client.post("/api/jobs", json=_body())
    assert r.status_code == 202, r.text
    assert time.monotonic() - t0 < 1.0, "submit must not block on the scan"
    assert r.json()["job_id"]


def test_the_full_flow_submit_poll_result(client):
    job_id = client.post("/api/jobs", json=_body()).json()["job_id"]
    for _ in range(200):
        st = client.get(f"/api/jobs/{job_id}").json()
        if st["state"] in _jobs.TERMINAL:
            break
        time.sleep(0.05)
    assert st["state"] == _jobs.SUCCEEDED, st
    assert "progress" in st and st["progress"]["overall_fraction"] == 1.0
    res = client.get(f"/api/jobs/{job_id}/result")
    assert res.status_code == 200
    assert res.json()["counts"] == {"both_safe": 414}


def test_asking_for_a_result_too_early_is_409_not_404(client):
    client._gate.clear()                          # type: ignore[attr-defined]
    try:
        job_id = client.post("/api/jobs", json=_body()).json()["job_id"]
        r = client.get(f"/api/jobs/{job_id}/result")
        assert r.status_code == 409, (
            "404 would tell a poller to stop; the job exists and is not done")
    finally:
        client._gate.set()                        # type: ignore[attr-defined]


def test_an_unknown_job_id_is_404_on_every_endpoint(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/result").status_code == 404
    assert client.delete("/api/jobs/nope").status_code == 404


def test_a_coordinate_outside_the_region_is_422_with_the_services_own_wording(client):
    w, s, _e, _n = _routing.walk_bbox("yeongdeok_2025")
    r = client.post("/api/jobs", json=_body(lat=s - 5.0, lon=w - 5.0))
    assert r.status_code == 422
    assert "없는 근거를 만들어내는" in r.json()["detail"], (
        "the refusal sentence must be the service's, not a second copy written "
        "in the transport")


def test_an_unknown_region_is_404(client):
    assert client.post("/api/jobs", json=_body(region="gangwon_2099")).status_code == 404


def test_a_malformed_coordinate_is_rejected_by_validation(client):
    assert client.post("/api/jobs", json=_body(lat=999.0)).status_code == 422
    assert client.post("/api/jobs", json={"region": "yeongdeok_2025"}).status_code == 422


def test_a_full_queue_is_429_rather_than_a_silent_accept(client):
    client._gate.clear()                          # type: ignore[attr-defined]
    try:
        codes = [client.post("/api/jobs", json=_body()).status_code
                 for _ in range(20)]
        assert 429 in codes, "an unbounded queue would accept work it cannot do"
    finally:
        client._gate.set()                        # type: ignore[attr-defined]


def test_cancel_is_accepted_and_the_job_ends_cancelled(client):
    client._gate.clear()                          # type: ignore[attr-defined]
    job_id = client.post("/api/jobs", json=_body()).json()["job_id"]
    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 200 and r.json()["cancel_accepted"] is True
    client._gate.set()                            # type: ignore[attr-defined]
    for _ in range(200):
        st = client.get(f"/api/jobs/{job_id}").json()
        if st["state"] in _jobs.TERMINAL:
            break
        time.sleep(0.05)
    assert st["state"] == _jobs.CANCELLED, st
    assert st.get("nothing_was_written") is True


def test_two_submissions_with_the_same_coordinate_agree(client):
    ids = [client.post("/api/jobs", json=_body()).json()["job_id"]
           for _ in range(2)]
    out = []
    for j in ids:
        for _ in range(300):
            if client.get(f"/api/jobs/{j}").json()["state"] in _jobs.TERMINAL:
                break
            time.sleep(0.05)
        out.append(client.get(f"/api/jobs/{j}/result").json())
    assert out[0]["determinism_key"] == out[1]["determinism_key"]
    assert out[0]["counts"] == out[1]["counts"]
    assert out[0]["run_id"] != out[1]["run_id"], "two runs, two directories"


# ---------------------------------------------------------------------------
# 3. What the transport must NOT expose
# ---------------------------------------------------------------------------


def test_no_response_carries_an_external_url(client):
    """Every endpoint, through the real gate."""
    job_id = client.post("/api/jobs", json=_body()).json()["job_id"]
    for _ in range(200):
        if client.get(f"/api/jobs/{job_id}").json()["state"] in _jobs.TERMINAL:
            break
        time.sleep(0.05)
    for path in ("/api/health", "/api/regions",
                 "/api/regions/yeongdeok_2025/gate?lat=36.44&lon=129.37",
                 f"/api/jobs/{job_id}", f"/api/jobs/{job_id}/result"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert find_external_refs(r.json()) == [], f"{path} leaked a URL"


def test_the_html_doc_pages_are_disabled_because_they_load_from_a_cdn(client):
    """FastAPI's /docs and /redoc pull Swagger UI and ReDoc from jsDelivr.

    That is the only reason they are off. The SCHEMA is a different question and
    is answered by the next test rather than by lumping it in here — which is
    what the first version of this test did, and it failed for the right reason.
    """
    for path in ("/docs", "/redoc"):
        assert client.get(path).status_code in (404, 405), path


def test_the_openapi_schema_is_served_and_is_itself_offline_clean(client):
    """Measured, not assumed: the schema carries no fetchable URL.

    It stays available because it is pure JSON with nothing to fetch, and it is
    how someone explores this API with curl and no screen.
    """
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert find_external_refs(r.json()) == [], (
        "the generated schema now contains a URL — either a field gained an "
        "externalDocs link or a description does; disable openapi_url rather "
        "than shipping it")


def test_routing_parameters_are_not_settable_over_http():
    """A stride typed into a request would make the result incomparable."""
    from wildfireguardian.api.app import IgnitionBody
    settable = set(IgnitionBody.model_fields)
    for forbidden in ("p_cut", "stride", "time_budget_min", "time_step_min",
                      "eps_m", "sampling_m", "max_abs_slope", "limit_origins"):
        assert forbidden not in settable, (
            f"{forbidden} is settable over HTTP; every published 459-series "
            "number depends on it coming from config/default.yaml")


def test_the_service_package_still_imports_no_web_framework():
    """The dependency runs one way. PHASE 19 stays callable without a server."""
    banned = ("fastapi", "uvicorn", "starlette", "flask")
    for path in sorted((REPO / "src" / "wildfireguardian" / "service").glob("*.py")):
        low = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert f"import {token}" not in low and f"from {token}" not in low, (
                f"{path.name} imports {token}")


def test_static_mount_does_not_shadow_the_api(client):
    """The web root is mounted at / and must lose to /api on every path."""
    assert client.get("/api/regions").status_code == 200


# ---------------------------------------------------------------------------
# 4. Map-click ignition: the geodesy stays server-side
# ---------------------------------------------------------------------------


def test_locate_unprojects_and_gates_in_one_round_trip(client):
    """A click costs one request, not two, and the page does no projection."""
    from pyproj import Transformer
    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    w, s, e, n = _routing.walk_bbox("yeongdeok_2025")
    lon, lat = (w + e) / 2, (s + n) / 2
    x, y = to5179.transform(lon, lat)
    d = client.get(f"/api/regions/yeongdeok_2025/locate?x={x:.2f}&y={y:.2f}").json()
    assert d["inside_registered_region"] is True
    assert d["lon"] == pytest.approx(lon, abs=1e-6)
    assert d["lat"] == pytest.approx(lat, abs=1e-6)
    assert "재생성되지 않습니다" in d["hazard_field_note_ko"]


def test_the_locate_round_trip_is_exact_to_the_centimetre(client):
    """Measured, not assumed. The only loss is the 2-decimal metre in the URL."""
    from pyproj import Geod, Transformer
    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    geod = Geod(ellps="WGS84")
    for lon, lat in ((129.3696, 36.4436), (129.40, 36.45), (129.26, 36.31)):
        x, y = to5179.transform(lon, lat)
        d = client.get(
            f"/api/regions/yeongdeok_2025/locate?x={x:.2f}&y={y:.2f}").json()
        _a, _b, err_m = geod.inv(lon, lat, d["lon"], d["lat"])
        assert err_m < 0.05, f"{lon},{lat} round-tripped {err_m*100:.2f} cm out"


def test_a_click_outside_the_region_is_refused_with_the_services_sentence(client):
    """Refused, and refused in words the service owns — not composed here."""
    from pyproj import Transformer
    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    x, y = to5179.transform(129.20, 35.60)          # far south, outside the grid
    d = client.get(f"/api/regions/yeongdeok_2025/locate?x={x:.2f}&y={y:.2f}").json()
    assert d["inside_registered_region"] is False
    assert "없는 근거를 만들어내는" in d["reason_ko"]


def test_locate_carries_no_external_url(client):
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:5179",
                                always_xy=True).transform(129.40, 36.45)
    d = client.get(f"/api/regions/yeongdeok_2025/locate?x={x:.1f}&y={y:.1f}").json()
    assert find_external_refs(d) == []


def test_locate_on_an_unknown_region_is_404(client):
    assert client.get("/api/regions/nowhere_2099/locate?x=1&y=1").status_code == 404


# ---------------------------------------------------------------------------
# 5. The root URL IS the console
# ---------------------------------------------------------------------------


def test_the_root_url_serves_the_console(client):
    """「127.0.0.1:8000 을 여시면 됩니다」 has to be true.

    It was not. `StaticFiles(html=True)` serves `index.html` for a directory
    request, `web/` has no `index.html`, and so GET / returned
    {"detail":"Not Found"} while /console.html worked — a demonstration where
    the presenter reads a path aloud instead of saying "open localhost".
    """
    r = client.get("/")
    if not (REPO / "web" / "console.html").is_file():
        assert r.status_code == 503, "an unbuilt console must say so, not 404"
        return
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "<title>" in r.text and "운영자 콘솔" in r.text


def test_the_root_url_and_console_html_serve_the_same_bytes(client):
    if not (REPO / "web" / "console.html").is_file():
        pytest.skip("console not built")
    assert client.get("/").content == client.get("/console.html").content


def test_the_build_template_is_not_served(client):
    """Everything under web/ is public, so build inputs do not live there.

    The template still carries its /*__DATA__*/ placeholder: a browser reaching
    it runs JSON.parse on a comment and renders a blank console. It WAS at
    /console.template.html with HTTP 200.
    """
    assert client.get("/console.template.html").status_code == 404
    assert not (REPO / "web" / "console.template.html").exists(), (
        "the template is back under web/, where it is publicly served")
    assert (REPO / "scripts" / "console.template.html").is_file()


def test_no_html_under_web_is_a_template(client):
    """Generalised: nothing served from web/ may contain a build placeholder."""
    for page in (REPO / "web").rglob("*.html"):
        assert "/*__DATA__*/" not in page.read_text(encoding="utf-8"), (
            f"{page.name} is a template and is being served")


def test_the_startup_message_names_the_url_that_actually_works():
    """The message promised the root URL while the root URL returned 404.

    Both halves are pinned: the script must print the root URL, and the app must
    serve it.
    """
    src = (REPO / "scripts" / "run_api.py").read_text(encoding="utf-8")
    assert 'url = f"http://{args.host}:{args.port}/"' in src
    assert "{url}" in src, "the message must interpolate the URL, not retype it"
    app_src = (REPO / "src" / "wildfireguardian" / "api" / "app.py").read_text(
        encoding="utf-8")
    assert '@app.get("/"' in app_src
