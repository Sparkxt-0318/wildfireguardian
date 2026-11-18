"""live/ tests (PROTOCOL §11). Run from the repository root:  python3 -m pytest -q live/tests

* a recorded-input run that reproduces a past day exactly (25 March 2025, 18:00 KST, the 의성 fire);
* the out-of-range score reproduces research/kcf-abstain's committed 25 March scores;
* replays of logged live records reproduce their records (fixtures/logged/, when present);
* one failure test per missing input: KFS, FIRMS, AHI, GFS, stale input, road data; plus the fetch stage offline;
* alerts send exactly the two kinds of message.
"""
import copy
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

LIVE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIVE))
from wfg_live import alerts, common as C, compute, fetch, flags, pages, road  # noqa: E402
from wfg_live.run import REPLAY_DROP  # noqa: E402

FIX = LIVE / "tests/fixtures"
DAY = FIX / "kfs01_20250325T0900Z"
GOLDEN = LIVE / "tests/golden/kfs01_20250325T0900Z.record.json"
VOLATILE = ("settings_sha256", "protocol_sha256")


def canon(rec):
    r = {k: v for k, v in rec.items() if k not in REPLAY_DROP + VOLATILE}
    return json.loads(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str))


def copy_inputs(tmp, src=DAY):
    d = tmp / "inputs"
    shutil.copytree(src, d)
    return d, json.loads((d / "manifest.json").read_text())


def save(d, man):
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False))


@pytest.fixture
def no_road(monkeypatch):
    """Skip the slow road layer where a test is about inputs only."""
    monkeypatch.setattr(road, "run_roadlayer", lambda region, raster, issue, out, replay, cards=True: {"region": region, "run_exit": 0, "stub": True,
                                                                                                         "rows": []})
    monkeypatch.setattr(road, "affected", lambda rows, horizon_s=0: [])


# ------------------------------------------------------------------ reproduction
@pytest.mark.parametrize("name", ["kfs01_20250325T0900Z", "kfs01_20250324T1500Z"])
def test_recorded_day_reproduces_exactly(name, tmp_path):
    """25 March 2025 18:00 KST (out of range: numbers withheld) and 00:00 KST (in range: numbers published)."""
    rec = compute.compute(FIX / name, tmp_path / "road", replay=True, with_cards=False)
    got = canon(rec)
    golden = LIVE / "tests/golden" / (name + ".record.json")
    if os.environ.get("WFG_LIVE_UPDATE_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(json.dumps(got, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert got == json.loads(golden.read_text(encoding="utf-8"))
    F = rec["fires"][0]
    if name == "kfs01_20250325T0900Z":
        assert F["margin"]["class"] == "running" and F["margin"]["r5_km"] == 7.6
        assert F["withheld"] == ["OUT_OF_RANGE"] and not F["publish_numbers"]
        assert set(F["zone"]["regions_reached"]) == {"uiseong_andong_2025", "yeongdeok_2025"}
    else:
        assert F["margin"]["class"] == "quiet" and F["withheld"] == [] and F["publish_numbers"]
        assert F["flags"]["oor"]["state"] is False and F["villages_affected"] > 0


def test_recorded_day_is_deterministic(tmp_path):
    a = canon(compute.compute(DAY, tmp_path / "a", replay=True, with_cards=False))
    b = canon(compute.compute(DAY, tmp_path / "b", replay=True, with_cards=False))
    assert a == b


def test_forecast_predictors_match_kcf_abstain():
    """The GFS predictors at 25 March 18 KST equal research/kcf-abstain's committed DET row (same cycle, same lattice rule)."""
    man = json.loads((DAY / "manifest.json").read_text())
    df = pd.read_csv(C.REPO / "research/kcf-abstain/derived/hours.csv.gz", low_memory=False)
    row = df[(df["product"] == "DET") & (df.kst_hour == 18)].iloc[0]
    pr = flags.predictors(DAY, man, C.parse_iso("2025-03-25T09:00:00Z"), row.lat, row.lon)
    for k in ("gust_ms", "w850_ms", "rhmin_pct", "hdw"):
        assert abs(pr[k] - row[k]) < 1e-3, (k, pr[k], row[k])


def test_oor_score_reproduces_committed_march25():
    df = pd.read_csv(C.REPO / "research/kcf-abstain/derived/hours.csv.gz", low_memory=False)
    det = df[df["product"] == "DET"]
    n = 0
    for r in det.itertuples():
        v = dict(gust_ms=r.gust_ms, w850_ms=r.w850_ms, rhmin_pct=r.rhmin_pct, hdw=r.hdw, prior3_km=r.prior3_km)
        if any(isinstance(x, float) and math.isnan(x) for x in v.values()):
            continue
        o = flags.oor_score(v)
        assert abs(o["score"] - r.score) < 6e-6          # committed scores are rounded to 5 decimals
        assert o["state"] == bool(r.abstain)
        n += 1
    assert n == 24


@pytest.mark.parametrize("d", sorted((FIX / "logged").glob("*/manifest.json")) if (FIX / "logged").exists() else [],
                         ids=lambda p: p.parent.name)
def test_logged_live_record_replays(d, tmp_path):
    want = json.loads((d.parent / "record.json").read_text(encoding="utf-8"))
    got = compute.compute(d.parent, tmp_path / "road", replay=True, with_cards=True)
    assert canon(got) == canon(want)


# ------------------------------------------------------------------ one failure test per missing input
def test_kfs_missing(tmp_path, no_road):
    d, man = copy_inputs(tmp_path)
    man["sources"]["kfs"].update(ok=False, error="HTTP 503", file=None)
    save(d, man)
    rec = compute.compute(d, tmp_path / "road", replay=True)
    assert rec["kfs_ok"] is False and rec["fires"] == [] and rec["listed"] == []
    html = pages.index_html(dict(rec, bulletin_day={}))
    assert "fire list could not be fetched" in html


def test_firms_missing(tmp_path, no_road):
    d, man = copy_inputs(tmp_path)
    for k in list(man["sources"]):
        if k.startswith("firms:"):
            man["sources"][k].update(ok=False, error="no FIRMS map key", file=None)
    save(d, man)
    rec = compute.compute(d, tmp_path / "road", replay=True)
    F = rec["fires"][0]
    assert "FIRMS_MISSING" in F["withheld"] and not F["publish_numbers"]


def test_ahi_missing(tmp_path, no_road):
    d, man = copy_inputs(tmp_path)
    man["sources"]["ahi"].update(ok=False, error="no AHI scan could be read")
    save(d, man)
    rec = compute.compute(d, tmp_path / "road", replay=True)
    F = rec["fires"][0]
    assert rec["ahi_ok"] is False
    assert F["area"]["n_by_src"].get("AHI") is None
    # without AHI the newest evidence is the 13:30 KST VIIRS overpass, more than 3 h before 18:00 KST
    assert "EVIDENCE_OLD" in F["withheld"]


def test_gfs_missing(tmp_path, no_road):
    d, man = copy_inputs(tmp_path)
    man["sources"]["gfs"].update(ok=False, complete=False, error="GFS cycle incomplete", file=None)
    save(d, man)
    rec = compute.compute(d, tmp_path / "road", replay=True)
    F = rec["fires"][0]
    assert "FORECAST_MISSING" in F["withheld"]
    assert F["flags"]["gust"]["state"] is None and F["flags"]["oor"]["state"] is None
    assert rec["bulletin"].get("error")


def test_stale_input(tmp_path, no_road):
    d, man = copy_inputs(tmp_path)
    man["sources"]["kfs"]["fetched_utc"] = "2025-03-25T08:00:00Z"     # 60 min before the issue time (limit 45)
    save(d, man)
    F = compute.compute(d, tmp_path / "road", replay=True)["fires"][0]
    assert "INPUT_OLD" in F["withheld"]


def test_road_data_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("WFG_ROADLAYER_CACHE", str(tmp_path / "empty-cache"))
    rec = compute.compute(DAY, tmp_path / "road", replay=True, with_cards=False)
    for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
        assert rec["regions"][rid]["refused"]["codes"] == ["DATA_NOT_SET_UP"]
    assert "ROAD_REFUSED" in rec["fires"][0]["withheld"]


def test_fetch_stage_offline(tmp_path, monkeypatch):
    """Every source unreachable: the fetch stage records each failure and the run still produces a record."""
    monkeypatch.setattr(C, "http", lambda *a, **k: (0, None, "URLError: offline"))
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    monkeypatch.setattr(fetch, "firms_key", lambda: ("dummy", "test"))
    import fetch_nwp
    monkeypatch.setattr(fetch_nwp, "get", lambda *a, **k: None)
    man = fetch.fetch_all(tmp_path / "in", C.parse_iso("2026-11-19T00:07:00Z"))
    assert man["sources"]["kfs"]["ok"] is False
    assert all(not v["ok"] for k, v in man["sources"].items() if k.startswith("firms:"))
    assert man["sources"]["gfs"]["ok"] is False and "incomplete" in man["sources"]["gfs"]["error"]
    rec = compute.compute(tmp_path / "in", tmp_path / "road", replay=True)
    assert rec["kfs_ok"] is False and rec["fires"] == [] and rec["bulletin"].get("error")


def test_firms_without_key(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "firms_key", lambda: (None, "none"))
    res = fetch.fetch_firms(C.settings(), tmp_path)
    assert all(not r["ok"] and "no FIRMS map key" in r["error"] for r in res.values())
    assert all("<MAP_KEY>" in r["url"] for r in res.values())       # the key never enters a record


# ------------------------------------------------------------------ scope and alerts
def test_scope_rule():
    cfg = C.settings()
    assert fetch.in_scope(cfg, {"frfrPrgrsStcd": "02", "lgdngCd": "4773000000", "frfrSttmnAddr": "경상북도 의성군"})
    assert fetch.in_scope(cfg, {"frfrPrgrsStcd": "02", "lgdngCd": "5115000000", "frfrSttmnAddr": "강원특별자치도 강릉시"})
    assert not fetch.in_scope(cfg, {"frfrPrgrsStcd": "03", "lgdngCd": "4773000000", "frfrSttmnAddr": "경상북도 의성군"})
    assert not fetch.in_scope(cfg, {"frfrPrgrsStcd": "02", "lgdngCd": "4180033021", "frfrSttmnAddr": "경기도 연천군"})


def _rec(cut_s, publish=True):
    return {"issue_utc": "2026-11-19T00:07:00Z", "fires": [{"id": "1", "address": "경상북도 영덕군", "publish_numbers": publish,
                                                            "zone": {"regions_reached": ["yeongdeok_2025"]}}],
            "regions": {"yeongdeok_2025": {"affected": [{"place_id": "p1", "name_ko": "가리", "road_cut_s": cut_s}]}}}


def test_alerts_only_two_kinds(monkeypatch):
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_HOST"):
        monkeypatch.delenv(k, raising=False)
    st = {}
    m1 = alerts.decide(_rec(3600), st)
    assert [m["kind"] for m in m1] == ["first_affect"]
    assert C.NOTICE["ko"] in m1[0]["text"] and C.NOTICE["en"] in m1[0]["text"]
    r2 = _rec(3600 + 600)
    r2["issue_utc"] = "2026-11-19T00:07:00Z"
    assert alerts.decide(r2, st) == []                 # moved 10 min: nothing
    r3 = _rec(3600 + 20 * 60)
    assert [m["kind"] for m in alerts.decide(r3, st)] == ["cut_moved"]    # moved 20 min from the last alerted time
    assert alerts.decide(_rec(3600 + 20 * 60), st) == []
    sent = alerts.send(m1)
    assert sent["sent"] == [] and "skipped" in sent["note"]


def test_withheld_numbers_not_published(tmp_path):
    rec = json.loads(GOLDEN.read_text(encoding="utf-8"))
    rec.update(issue_kst=C.kst(C.parse_iso(rec["issue_utc"])), bulletin_day={})
    files = pages.build(rec, tmp_path / "road", tmp_path / "site")
    html = (tmp_path / "site/fire/FIXTURE-20250322-UISEONG.html").read_text(encoding="utf-8")
    assert "times withheld" in html and "class=num>" not in html
    pub = json.loads((tmp_path / "site/data/latest.json").read_text(encoding="utf-8"))
    for rr in pub["regions"].values():
        assert all(v.get("times") == "withheld" and "road_cut_s" not in v for v in rr["affected"])
    for f in files:
        if f.endswith(".html"):
            t = (tmp_path / "site" / f).read_text(encoding="utf-8")
            assert C.NOTICE["ko"] in t and C.NOTICE["en"] in t and "data-stale-min" in t
