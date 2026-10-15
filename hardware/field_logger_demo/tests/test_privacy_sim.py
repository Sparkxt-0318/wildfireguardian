"""SIM ground truth (spec test 2, the numbers) and privacy (test 6, everything except the page's DOM, which
test_web.py checks)."""
import json
import re
import struct

import pytest

from app import config, exports, library, privacy, replay
from conftest import ROOT

LIB = json.loads((ROOT / "sessions" / "sessions.json").read_text(encoding="utf-8"))


def _truth(entry):
    return json.loads((ROOT / "sessions" / (entry["file"] + ".sim.json")).read_text(encoding="utf-8"))["truth"]


@pytest.mark.parametrize("entry", LIB, ids=[e["file"] for e in LIB])
def test_detected_stops_match_the_ground_truth(entry):
    p = replay.build(entry)
    truth = _truth(entry)
    assert p["meta"]["sim"] and p["meta"]["sim_kind"] == "sim" and p["meta"]["device"] == "WFG-00000000"
    assert len(p["stops"]) == len(truth["stops"])
    for d, tr in zip(p["stops"], truth["stops"]):
        assert abs(d["t0"] - tr["t0"]) <= 2.0, (d, tr)
        assert abs(d["dur"] - tr["dur"]) <= 3.0, (d, tr)
    # the 60 s wait at the start (cold start, then standing) is not a stop and is outside the analysed span
    assert truth["lead_in_s"] == 60
    assert all(d["t0"] > truth["lead_in_s"] for d in p["stops"])
    assert abs(p["span"][0] - truth["lead_in_s"]) <= 2.0
    assert p["metrics"]["lead_in"] >= truth["lead_in_s"] - 2.0
    assert len(p["gaps"]) == len(truth["gaps"])
    for g, tg in zip(p["gaps"], truth["gaps"]):
        assert abs(g["dur"] - tg["s"]) <= 1.0 and abs(g["t0"] - tg["t0"]) <= 2.0
    # validation: every real press is matched, a stray press is not, an unmarked stop stays unmatched
    v = p["validation"]
    real = [x for x in truth["presses"] if not x["stray"]]
    assert v["presses"] == len(truth["presses"]) and v["matched"] == len(real)
    for d, tr in zip(p["stops"], truth["stops"]):
        assert (d["me"] is not None) == tr["press"]


@pytest.mark.parametrize("entry", LIB, ids=[e["file"] for e in LIB])
def test_summary_numbers_are_the_payload_numbers(entry):
    p = replay.build(entry)
    num = replay.summary_numbers(p)
    assert num["metrics"] == p["metrics"] and num["simulated"] is True
    assert [s["duration_s"] for s in num["stops"]] == [s["dur"] for s in p["stops"]]
    m = p["metrics"]
    assert abs(m["moving"] - (m["elapsed"] - m["stopped"] - m["gap"])) < 1e-6
    assert m["n_stops"] == len(p["stops"])


def _hidden_rows(entry):
    s = library.load(library.safe_path(entry["file"]))
    zones = privacy.zones_for(s, entry.get("privacy"))
    rows = [r for r in s.rows if r["fix"] and privacy.inside(zones, r["lat"], r["lon"])]
    events = [e for e in s.events if e["located"] and privacy.inside(zones, e["lat"], e["lon"])]
    return s, zones, rows, events


def _forms(v):
    return {repr(round(v, 7)), "%.7f" % v, "%.6f" % v, "%.5f" % v}


def _needles(points):
    """Every form a hidden position could take: its latitude and longitude as neighbouring numbers in either order
    (JSON, 7, 6 or 5 decimals), and the record's lat/lon bytes as hex. A latitude alone is a line around the earth,
    not a position, and visible rows share single values with hidden ones by chance, so pairs are what is checked."""
    pairs, hexes = set(), set()
    for lat, lon in points:
        for a in _forms(lat):
            for b in _forms(lon):
                pairs.add((a, b))
                pairs.add((b, a))
        hexes.add(struct.pack("<ii", int(round(lat * 1e7)), int(round(lon * 1e7))).hex())
    return pairs, hexes


def _assert_clean(text, needles, where):
    pairs, hexes = needles
    tokens = re.findall(r"-?\d+\.\d+", text)
    found = sorted({(a, b) for a, b in zip(tokens, tokens[1:]) if (a, b) in pairs})
    found += sorted(h for h in hexes if h in text)
    assert not found, "%s contains hidden positions: %s" % (where, found[:5])


def _shown_positions(p):
    """Every position the payload carries (rows, button marks, stops, gap ends, bounds corners)."""
    out = [(r["la"], r["lo"]) for r in p["rows"] if r["la"] is not None]
    out += [(e["la"], e["lo"]) for e in p["events"] if e["la"] is not None]
    out += [(s["la"], s["lo"]) for s in p["stops"] if s["la"] is not None]
    for g in p["gaps"]:
        out += [(g[k][1], g[k][0]) for k in ("a", "b") if g[k]]
    if p["bounds"]:
        b = p["bounds"]
        out += [(b[1], b[0]), (b[3], b[2])]
    return out


@pytest.mark.parametrize("entry", LIB, ids=[e["file"] for e in LIB])
def test_no_hidden_coordinate_reaches_the_payload_or_the_exports(entry, tmp_path):
    s, zones, hidden, hidden_ev = _hidden_rows(entry)
    if entry["privacy"]["auto_zones"]:
        assert hidden and len(zones) == 2
    else:
        assert not zones and not hidden
    p = replay.build(entry)
    needles = _needles([(r["lat"], r["lon"]) for r in hidden] + [(e["lat"], e["lon"]) for e in hidden_ev])
    _assert_clean(json.dumps(p), needles, "replay payload")
    # every row inside a zone is flagged and carries no position; everything shown is outside every zone
    hidden_idx = {r["idx"] for r in hidden} | {e["idx"] for e in hidden_ev}
    assert sum(r["h"] for r in p["rows"]) == len(hidden)
    assert all(r["la"] is None and r["lo"] is None for r in p["rows"] if r["h"])
    worst = replay.nearest_check(p)
    assert worst is None or worst >= 0.0
    raw_zones = [{"lat": z["la"], "lon": z["lo"], "radius_m": z["r"]} for z in p["zones"]]
    inside = [pt for pt in _shown_positions(p) if privacy.inside(raw_zones, pt[0], pt[1])]
    assert not inside, inside[:3]
    for rec in p["records"]:
        if rec["i"] in hidden_idx:
            assert rec["hx"][40:56] == "x" * 16 and rec["hx"][88:96] == "x" * 8, rec
    # exports: stops.csv and summary.json
    exports.write_tables(p, tmp_path)
    for name in ("stops.csv", "summary.json"):
        _assert_clean((tmp_path / name).read_text(encoding="utf-8"), needles, name)
    # the zone circles always cover the protected disc around the first and last fix
    fixes = [r for r in s.rows if r["fix"]]
    for z, anchor in zip([z for z in zones if z["kind"] in ("start", "end")], (fixes[0], fixes[-1])):
        from app.geo import haversine
        assert haversine(anchor["lat"], anchor["lon"], z["lat"], z["lon"]) + z["protected_m"] <= z["radius_m"] + 1e-6


def test_a_stop_inside_a_zone_is_counted_without_coordinates(tmp_root):
    entry = next(e for e in LIB if e["key"] == 1)
    truth = _truth(entry)
    st = truth["stops"][1]
    config.PRIVACY_FILE.write_text(json.dumps([{"name": "school", "lat": st["lat"], "lon": st["lon"], "radius_m": 60}]),
                                   encoding="utf-8")
    p = replay.build(entry)
    assert len(p["zones"]) == 3 and p["zones"][2]["kind"] == "named"
    hit = p["stops"][1]
    assert hit["h"] == 1 and hit["la"] is None and hit["lo"] is None
    num = replay.summary_numbers(p)
    assert num["stops"][1]["inside_privacy_zone"] is True and num["stops"][1]["lat"] is None
    assert num["metrics"]["n_stops"] == len(truth["stops"])          # still counted
    _s, _z, hidden, hidden_ev = _hidden_rows(entry)
    _assert_clean(json.dumps(p), _needles([(r["lat"], r["lon"]) for r in hidden] + [(e["lat"], e["lon"]) for e in hidden_ev]),
                  "payload with a named zone")


def test_a_record_that_fails_its_crc_shows_no_position_bytes(tmp_root):
    """A corrupted record keeps its position bytes, and nothing tells whether that position is inside a zone: its
    position bytes and CRC are always masked in the replay payload (as DUMP lines are on the device page)."""
    data = bytearray((config.SIM_DIR / "sim_walk_4_crossings.wfg").read_bytes())
    k = next(i for i in range(len(data) // 48) if data[i * 48 + 2] == 2)        # the first FIX record
    pos_hex = bytes(data[k * 48 + 20:k * 48 + 28]).hex()
    data[k * 48 + 30] ^= 0xFF                                                    # breaks the CRC, not the position
    (config.SIM_DIR / "corrupt_walk.wfg").write_bytes(bytes(data))
    p = replay.build(library.entry_for_file("sim/corrupt_walk.wfg"))
    bad = [r for r in p["records"] if not r["ok"]]
    assert len(bad) == 1 and bad[0]["i"] == k
    assert bad[0]["hx"][40:56] == "x" * 16 and bad[0]["hx"][88:96] == "x" * 8
    assert pos_hex not in json.dumps(p)
    ok = [r for r in p["records"] if r["ok"] and r["hx"] and "x" not in r["hx"]]
    assert ok                                                                    # records outside the zones stay whole


def test_circle_offsets_are_keyed_with_the_local_secret(tmp_path, monkeypatch):
    """The offset of a circle cannot be worked out from what the page or summary.json shows (the session's SHA-256, a
    zone's name): it is keyed with a secret kept only on this Mac. Same secret, same circles; another secret, others."""
    entry = next(e for e in LIB if e["key"] == 1)
    s = library.load(library.safe_path(entry["file"]))
    a = privacy.zones_for(s, entry["privacy"], named=[])
    again = privacy.zones_for(s, entry["privacy"], named=[])
    assert [(z["lat"], z["lon"]) for z in a] == [(z["lat"], z["lon"]) for z in again]
    other = tmp_path / "zone_secret"
    monkeypatch.setattr(config, "ZONE_SECRET_FILE", other)
    b = privacy.zones_for(s, entry["privacy"], named=[])
    assert other.exists() and other.stat().st_mode & 0o777 == 0o600 and len(other.read_text().strip()) == 64
    assert all((x["lat"], x["lon"]) != (y["lat"], y["lon"]) for x, y in zip(a, b))
    fixes = [r for r in s.rows if r["fix"]]
    for zs in (a, b):                                    # either way the protected disc stays covered
        for z, anchor in zip(zs, (fixes[0], fixes[-1])):
            from app.geo import haversine
            assert haversine(anchor["lat"], anchor["lon"], z["lat"], z["lon"]) + z["protected_m"] <= z["radius_m"] + 1e-6


def test_a_named_zone_the_route_does_not_touch_is_never_drawn(tmp_root):
    """A named zone (home) hides wherever the route enters it, but one the route never touches is not sent to the
    page: its circle would only show where home is."""
    entry = next(e for e in LIB if e["key"] == 1)
    config.PRIVACY_FILE.write_text(json.dumps([{"name": "home", "lat": 31.2, "lon": 121.4, "radius_m": 300}]),
                                   encoding="utf-8")
    p = replay.build(entry)
    assert [z["kind"] for z in p["zones"]] == ["start", "end"]
    assert replay.summary_numbers(p)["privacy_zones"] == 2


def test_mask_hex_touches_only_position_and_crc():
    hx = "".join("%02x" % (i * 5 % 256) for i in range(48))
    m = privacy.mask_hex(hx, "FIX")
    assert m[:40] == hx[:40] and m[56:88] == hx[56:88]
    assert m[40:56] == "x" * 16 and m[88:96] == "x" * 8
    assert privacy.mask_hex(hx, "STATUS") == hx and privacy.mask_hex(hx, "CLOCK") == hx


def test_the_checks_find_a_planted_position():
    """Negative control: the same checks fail when one hidden position is put back into the payload."""
    entry = next(e for e in LIB if e["key"] == 1)
    _s, _z, hidden, _ev = _hidden_rows(entry)
    p = replay.build(entry)
    needles = _needles([(r["lat"], r["lon"]) for r in hidden])
    k = next(i for i, r in enumerate(p["rows"]) if r["h"])
    src = next(r for r in hidden if r["idx"] == p["rows"][k]["i"])
    p["rows"][k].update(la=round(src["lat"], 7), lo=round(src["lon"], 7))
    with pytest.raises(AssertionError):
        _assert_clean(json.dumps(p), needles, "planted")
    raw_zones = [{"lat": z["la"], "lon": z["lo"], "radius_m": z["r"]} for z in p["zones"]]
    assert any(privacy.inside(raw_zones, a, b) for a, b in _shown_positions(p))
