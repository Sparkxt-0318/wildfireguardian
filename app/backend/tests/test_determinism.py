"""Deterministic ``?t=<scenario minutes>`` behavior (spec section 4).

The same ``t`` must always produce the same payload; the scenario loops; and
the canonical demo states hold: far away is SAFE at t=0, the downwind user is
WATCH at t=0 and GO at t=200.
"""

from __future__ import annotations

# Reference user locations against the committed synthetic scenario:
FAR = (36.00, 129.00)    # ~53 km away: SAFE at any t
NEAR = (36.44, 129.45)   # downwind corridor: WATCH at t=0, GO at t=200
AHEAD = (36.43, 129.48)  # further downwind: GO at t=200 with a route
SOUTH = (36.37, 129.40)  # south flank: wind not toward user -> WATCH


def _level(client, latlon, t):
    lat, lon = latlon
    return client.get(f"/v1/situation?lat={lat}&lon={lon}&t={t}").json()["danger"]["level"]


def test_t0_far_away_is_safe(client):
    assert _level(client, FAR, 0) == "SAFE"


def test_t0_near_is_watch(client):
    j = client.get(f"/v1/situation?lat={NEAR[0]}&lon={NEAR[1]}&t=0").json()
    assert j["danger"]["level"] == "WATCH"
    assert j["weather"]["wind_toward_user"] is True
    assert j["eta_minutes"] is not None and j["eta_minutes"] > 180


def test_t200_near_is_go(client):
    j = client.get(f"/v1/situation?lat={NEAR[0]}&lon={NEAR[1]}&t=200").json()
    assert j["danger"]["level"] == "GO"
    assert j["fire"]["distance_km"] < 5.0
    assert j["eta_minutes"] is not None and j["eta_minutes"] <= 180
    # inside the 1-hour likely ring -> honest no-safe-walk card set
    assert [c["id"] for c in j["cards"]][0] == "call119_now"


def test_t200_ahead_is_go_with_route(client):
    j = client.get(f"/v1/situation?lat={AHEAD[0]}&lon={AHEAD[1]}&t=200").json()
    assert j["danger"]["level"] == "GO"
    assert [c["id"] for c in j["cards"]] == ["route", "shelter", "call119", "donots"]


def test_south_flank_wind_away_is_watch(client):
    j = client.get(f"/v1/situation?lat={SOUTH[0]}&lon={SOUTH[1]}&t=200").json()
    assert j["danger"]["level"] == "WATCH"
    assert j["weather"]["wind_toward_user"] is False


def test_same_t_same_payload(client):
    a = client.get("/v1/fires?t=125").json()
    b = client.get("/v1/fires?t=125").json()
    assert a == b


def test_fire_grows_with_t(client):
    n0 = len(client.get("/v1/fires?t=0").json()["features"])
    n355 = len(client.get("/v1/fires?t=355").json()["features"])
    assert n0 == 3, "fire starts small"
    assert n355 >= 40, "fire grows to 40+ detections"


def test_t_loops_and_snaps(client):
    t0 = client.get("/v1/fires?t=0").json()
    assert client.get("/v1/fires?t=360").json() == t0, "loops after 360 scenario minutes"
    assert client.get("/v1/fires?t=4").json() == t0, "snaps to the 5-minute step"


def test_history_prefix_grows_with_t(client):
    p0 = client.get("/v1/history?t=0").json()
    p355 = client.get("/v1/history?t=355").json()
    assert len(p0) == 1 and len(p355) == 72
    assert p355[0] == p0[0]
    rh = [p["rh_pct"] for p in p355]
    assert rh[0] == 30.0 and rh[-1] == 15.0, "RH drops 30 -> 15 over the scenario"


def test_route_deterministic_for_t(client):
    a = client.get(f"/v1/route?lat={AHEAD[0]}&lon={AHEAD[1]}&t=200").json()
    b = client.get(f"/v1/route?lat={AHEAD[0]}&lon={AHEAD[1]}&t=200").json()
    assert a == b and a["status"] == "ok"


def test_negative_t_rejected(client):
    r = client.get(f"/v1/situation?lat={NEAR[0]}&lon={NEAR[1]}&t=-5")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_request"
