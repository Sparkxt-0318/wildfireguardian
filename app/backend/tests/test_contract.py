"""Contract-shape tests for every section-5 endpoint.

Asserts required fields, including the bilingual ``*_ko`` / ``*_en`` pairs,
on real responses from the demo provider (deterministic via ``?t``).
"""

from __future__ import annotations

# Reference user locations against the committed synthetic scenario:
NEAR = (36.44, 129.45)   # downwind corridor: GO at t=200 (inside 1-h ring)
AHEAD = (36.43, 129.48)  # further downwind: GO at t=200 with a walkable route


def _assert_bilingual(obj: dict, stem: str):
    ko, en = f"{stem}_ko", f"{stem}_en"
    assert ko in obj and en in obj, f"missing {ko}/{en}"
    assert isinstance(obj[ko], str) and obj[ko].strip(), f"empty {ko}"
    assert isinstance(obj[en], str) and obj[en].strip(), f"empty {en}"


def test_health_shape(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    j = r.json()
    assert j["ok"] is True
    assert j["mode"] == "demo"
    assert "time_utc" in j and j["time_utc"].endswith("Z")


def test_config_shape(client):
    j = client.get("/v1/config").json()
    assert j["mode"] == "demo"
    assert "stripe_publishable_key" in j  # may be null
    assert j["tile_url"].startswith("https://")
    _assert_bilingual(j, "demo_banner")


def test_situation_shape(client):
    lat, lon = NEAR
    r = client.get(f"/v1/situation?lat={lat}&lon={lon}&t=200")
    assert r.status_code == 200
    j = r.json()

    assert j["mode"] == "demo"
    assert j["generated_utc"].endswith("Z")
    assert isinstance(j["prediction_available"], bool)
    _assert_bilingual(j, "disclaimer")

    danger = j["danger"]
    assert danger["level"] in ("SAFE", "WATCH", "GO")
    _assert_bilingual(danger, "label")
    _assert_bilingual(danger, "reason")

    fire = j["fire"]
    assert fire["active"] is True
    assert isinstance(fire["distance_km"], (int, float))
    assert isinstance(fire["bearing_deg"], (int, float))
    _assert_bilingual(fire, "bearing_text")
    assert isinstance(fire["detections"], int) and fire["detections"] > 0
    assert fire["first_detected_utc"].endswith("Z")
    assert fire["last_update_utc"].endswith("Z")

    weather = j["weather"]
    for f in ("wind_speed_ms", "wind_dir_deg", "rh_pct", "temp_c", "days_since_rain"):
        assert f in weather
    assert isinstance(weather["wind_toward_user"], bool)
    assert weather["days_since_rain"] == 14

    assert "eta_minutes" in j  # int or null
    assert isinstance(j["cards"], list) and j["cards"]
    for card in j["cards"]:
        assert set(card) >= {
            "id", "priority", "kind", "title_ko", "title_en",
            "body_ko", "body_en", "icon", "action",
        }
        _assert_bilingual(card, "title")
        _assert_bilingual(card, "body")
        assert card["kind"] in ("action", "info", "route", "contact")
        assert card["icon"] in (
            "flame", "wind", "route", "phone", "shelter", "clock", "check", "home"
        )
        assert card["action"]["type"] in ("open_map", "open_route", "call", "none")


def test_fires_shape(client):
    j = client.get("/v1/fires?t=200").json()
    assert j["type"] == "FeatureCollection"
    assert j["mode"] == "demo"
    assert j["features"], "expected active detections"
    for f in j["features"]:
        assert f["type"] == "Feature"
        assert f["geometry"]["type"] == "Point"
        lon, lat = f["geometry"]["coordinates"]
        assert 128.0 < lon < 131.0 and 35.0 < lat < 38.0
        props = f["properties"]
        assert "frp_mw" in props
        assert props["confidence"] in ("h", "n", "l")
        assert props["sensor"] in ("VIIRS", "MODIS")


def test_spread_shape(client):
    lat, lon = NEAR
    j = client.get(f"/v1/spread?lat={lat}&lon={lon}&t=200").json()
    assert j["type"] == "FeatureCollection"
    assert j["prediction_available"] is True
    polys = [f for f in j["features"] if f["geometry"]["type"] == "Polygon"]
    paths = [f for f in j["features"] if f["geometry"]["type"] == "LineString"]
    combos = {(f["properties"]["horizon_hours"], f["properties"]["p_level"]) for f in polys}
    assert combos == {(h, p) for h in (1, 3, 6) for p in ("likely", "possible")}
    for f in polys:
        ring = f["geometry"]["coordinates"][0]
        assert len(ring) >= 4 and ring[0] == ring[-1], "closed ring"
    assert 2 <= len(paths) <= 3, "2-3 pathway arrows"
    for f in paths:
        assert f["properties"]["kind"] == "pathway"
        assert isinstance(f["properties"]["bearing_deg"], (int, float))
        assert len(f["geometry"]["coordinates"]) >= 2


def test_route_ok_shape(client):
    lat, lon = AHEAD
    j = client.get(f"/v1/route?lat={lat}&lon={lon}&t=200").json()
    assert j["status"] == "ok"
    sh = j["shelter"]
    _assert_bilingual(sh, "name")
    assert isinstance(sh["lat"], float) and isinstance(sh["lon"], float)
    assert sh["distance_km"] > 0
    assert sh["walk_minutes"] >= 1
    geom = j["geometry"]
    assert geom["type"] == "LineString" and len(geom["coordinates"]) >= 2
    assert j["steps"], "expected walking steps"
    for step in j["steps"]:
        _assert_bilingual(step, "instruction")
        assert isinstance(step["distance_m"], int)
    assert isinstance(j["warnings_ko"], list) and isinstance(j["warnings_en"], list)
    assert len(j["warnings_ko"]) == len(j["warnings_en"])


def test_route_statuses_are_contract_values(client):
    lat, lon = NEAR
    for t, expected in ((200, "no_safe_walk"),):
        j = client.get(f"/v1/route?lat={lat}&lon={lon}&t={t}").json()
        assert j["status"] == expected
        assert j["warnings_ko"] and j["warnings_en"]
    j = client.get("/v1/route?lat=35.0&lon=127.0&t=0").json()
    assert j["status"] == "outside_region"


def test_shelters_shape(client):
    lat, lon = NEAR
    j = client.get(f"/v1/shelters?lat={lat}&lon={lon}").json()
    shelters = j["shelters"]
    assert len(shelters) == 4
    dists = [s["distance_km"] for s in shelters]
    assert dists == sorted(dists), "sorted by distance"
    for s in shelters:
        _assert_bilingual(s, "name")
        assert isinstance(s["walk_minutes"], int) and s["walk_minutes"] >= 1


def test_history_shape(client):
    j = client.get("/v1/history?t=100").json()
    assert j["mode"] == "demo"
    points = j["points"]
    assert len(points) == 21  # timesteps 0..100 at 5-min spacing
    for p in points:
        assert set(p) == {"t_utc", "detections", "area_ha_est", "wind_speed_ms", "rh_pct"}
        assert p["t_utc"].endswith("Z")
    counts = [p["detections"] for p in points]
    assert counts == sorted(counts), "detection count grows monotonically"


def test_error_shape_on_bad_request(client):
    r = client.get("/v1/situation")  # lat/lon missing
    assert r.status_code == 400
    j = r.json()
    assert j["error"] == "invalid_request"
    _assert_bilingual(j, "detail")


def test_cors_header_present(client):
    r = client.get("/v1/health", headers={"Origin": "https://example.com"})
    assert r.headers.get("access-control-allow-origin") == "*"
