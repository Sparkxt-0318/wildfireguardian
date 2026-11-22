"""Reported cause (PROTOCOL amendment 2): a fire with a cause, without one, and with one that changes later.

The real feed carries no cause (live/README.md). The "with a cause" tests therefore point config [cause] at made-up
test-only keys (TEST_CAUSE, TEST_STATUS, TEST_POINTS) added to a copy of a recorded feed; no real field is implied.
"""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

LIVE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIVE))
from wfg_live import cause, common as C, compute, pages, road  # noqa: E402
from test_live import FIX, GOLDEN, strip_optional  # noqa: E402

DAY = FIX / "kfs01_20250324T1500Z"        # one active 의성 fire, reported 2025-03-22 11:25 KST
KEYS = {"feed_cause_keys": ["TEST_CAUSE"], "feed_status_keys": ["TEST_STATUS"], "feed_points_keys": ["TEST_POINTS"]}


@pytest.fixture(autouse=True)
def no_road(monkeypatch):
    monkeypatch.setattr(road, "run_roadlayer", lambda region, raster, issue, out, replay, cards=True: {"region": region, "run_exit": 0, "stub": True, "rows": []})
    monkeypatch.setattr(road, "affected", lambda rows, horizon_s=0: [])


def inputs_with(tmp, **extra):
    d = tmp / "inputs"
    shutil.copytree(DAY, d)
    j = json.loads((d / "kfs.json").read_text(encoding="utf-8"))
    j["fireShowInfoList"][0].update(extra)
    (d / "kfs.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return d


def with_keys(monkeypatch):
    cfg = copy.deepcopy(C.settings())
    cfg["cause"].update(KEYS)
    monkeypatch.setattr(C, "settings", lambda path=None: cfg)


def run(d, tmp, state=None):
    return compute.compute(d, tmp / "road", replay=True, with_cards=False, cause_state=state)


def fire_page(rec, tmp):
    rec = dict(rec, bulletin_day={}, issue_kst=C.kst(C.parse_iso(rec["issue_utc"])))
    pages.build(rec, tmp / "road", tmp / "site")
    return (tmp / "site/fire/FIXTURE-20250322-UISEONG.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- a fire with a cause
def test_fire_with_cause(tmp_path, monkeypatch):
    with_keys(monkeypatch)
    d = inputs_with(tmp_path, TEST_CAUSE="입산자 실화", TEST_STATUS="추정", TEST_POINTS="2")
    rec = run(d, tmp_path)
    c = rec["fires"][0]["cause"]
    assert c["text"] == "입산자 실화" and c["status"] == "presumed" and c["ignition_points"] == 2
    assert c["first_reported_utc"] == "2025-03-22T02:25:00Z"          # 11:25 KST, the feed's own report time
    assert c["source_fields"] == ["TEST_CAUSE", "TEST_STATUS", "TEST_POINTS"]
    assert rec["listed"][0]["cause"] == c
    html = fire_page(rec, tmp_path)
    assert "입산자 실화" in html and "presumed" in html and "2025-03-22 11:25 KST" in html
    assert "not a statement about this fire" in html and "retrieved 2026-11-21" in html      # history panel, labelled


def test_status_words_map_and_unknown_status_is_not_guessed(tmp_path, monkeypatch):
    with_keys(monkeypatch)
    for word, want in (("확정", "confirmed"), ("조사중", "investigating"), ("조사 중", "investigating"), ("글쎄", "unspecified")):
        assert run(inputs_with(tmp_path / word.replace(" ", "_"), TEST_CAUSE="담뱃불 실화", TEST_STATUS=word), tmp_path)["fires"][0]["cause"]["status"] == want
    # a cause with no status word at all is not promoted to "confirmed" or "presumed"
    c = run(inputs_with(tmp_path / "nostatus", TEST_CAUSE="담뱃불 실화"), tmp_path)["fires"][0]["cause"]
    assert c["text"] == "담뱃불 실화" and c["status"] == "unspecified"
    # a bad ignition-point count is dropped, not repaired
    assert run(inputs_with(tmp_path / "bad", TEST_CAUSE="x", TEST_POINTS="여러 곳"), tmp_path)["fires"][0]["cause"]["ignition_points"] is None
    assert run(inputs_with(tmp_path / "zero", TEST_CAUSE="x", TEST_POINTS="0"), tmp_path)["fires"][0]["cause"]["ignition_points"] is None


# ---------------------------------------------------------------- a fire without a cause (the real feed today)
def test_fire_without_cause(tmp_path):
    rec = run(inputs_with(tmp_path, frfrOccrrTpcd="05", frfrOccrrStcd="31"), tmp_path)       # coded fields the real feed has: not read as a cause
    c = rec["fires"][0]["cause"]
    assert c["text"] is None and c["status"] == "not_reported" and c["ignition_points"] is None and c["source_fields"] == []
    html = fire_page(rec, tmp_path)
    assert html.count("not reported") >= 3 and "미보고" in html            # cause, first line of status, ignition points
    assert c["status_word"] is None                                    # nothing was read from OccrrTpcd / OccrrStcd


def test_unknown_feed_key_is_flagged_not_used(tmp_path):
    rec = run(inputs_with(tmp_path, frfrSomeNewCauseField="방화"), tmp_path)
    assert "frfrSomeNewCauseField" in rec["cause_feed"]["unknown_keys"]
    assert rec["fires"][0]["cause"]["text"] is None            # seen, recorded, but never shown until the config names it


# ---------------------------------------------------------------- a cause that changes later
def test_cause_changes_later(tmp_path, monkeypatch):
    with_keys(monkeypatch)
    state = {}
    r1 = run(inputs_with(tmp_path / "a"), tmp_path, state)
    r2 = run(inputs_with(tmp_path / "b", TEST_CAUSE="쓰레기 태우기", TEST_STATUS="조사중"), tmp_path, state)
    r3 = run(inputs_with(tmp_path / "c", TEST_CAUSE="쓰레기 태우기", TEST_STATUS="조사중"), tmp_path, state)      # unchanged: no new entry
    r4 = run(inputs_with(tmp_path / "d", TEST_CAUSE="성묘객 실화", TEST_STATUS="확정", TEST_POINTS="3"), tmp_path, state)
    c = [r["fires"][0]["cause"] for r in (r1, r2, r3, r4)]
    assert c[0]["status"] == "not_reported" and c[0]["changes"] == []
    assert c[1]["status"] == "investigating" and len(c[1]["changes"]) == 1
    assert c[1]["changes"][0]["from"] == {"text": None, "status": "not_reported"}
    assert len(c[2]["changes"]) == 1                                                                         # nothing new
    assert len(c[3]["changes"]) == 2 and c[3]["changes"][1]["from"] == {"text": "쓰레기 태우기", "status": "investigating"}
    assert c[3]["changes"][1]["to"] == {"text": "성묘객 실화", "status": "confirmed"} and c[3]["ignition_points"] == 3
    assert c[3]["first_seen_utc"] == c[0]["first_seen_utc"] == r1["issue_utc"]
    assert c[0]["text"] is None                                           # the earlier record is not rewritten by the later change
    assert "쓰레기 태우기" in fire_page(r4, tmp_path) and "Cause changed since first listed" in fire_page(r4, tmp_path)


def test_cause_removed_is_a_change_too(tmp_path, monkeypatch):
    with_keys(monkeypatch)
    state = {}
    run(inputs_with(tmp_path / "a", TEST_CAUSE="방화", TEST_STATUS="확정"), tmp_path, state)
    c = run(inputs_with(tmp_path / "b"), tmp_path, state)["fires"][0]["cause"]
    assert c["status"] == "not_reported" and c["text"] is None and c["changes"][0]["to"] == {"text": None, "status": "not_reported"}


# ---------------------------------------------------------------- backward compatibility
def test_old_records_still_render_and_replay(tmp_path):
    old = json.loads(GOLDEN.read_text(encoding="utf-8"))            # written before the cause fields existed
    assert "cause_feed" not in old and "cause" not in old["fires"][0] and "cause" not in old["listed"][0]
    old.update(issue_kst=C.kst(C.parse_iso(old["issue_utc"])), bulletin_day={})
    pages.build(old, tmp_path / "road", tmp_path / "site")          # no cause block: page builds, panel simply absent
    html = (tmp_path / "site/fire/FIXTURE-20250322-UISEONG.html").read_text(encoding="utf-8")
    assert "Reported cause" not in html
    new = run(inputs_with(tmp_path), tmp_path)
    assert new["schema"] == "wfg.live.record/1"                      # the schema id does not change
    assert set(new) - set(strip_optional(new)) == {"cause_feed"}
    assert set(new["fires"][0]) - set(strip_optional(new)["fires"][0]) == {"cause", "cause_history"}


def test_score_reads_records_with_cause(tmp_path):
    """score.py scores records that carry the new fields exactly as it scores records without them."""
    import subprocess
    log = tmp_path / "log"
    for name, day in (("kfs01_20250324T1500Z", "2025/03/24"), ("kfs01_20250325T0900Z", "2025/03/25")):
        (log / "records" / day).mkdir(parents=True)
        st = name.split("_")[1]
        rec = compute.compute(FIX / name, tmp_path / "road", replay=True, with_cards=False)
        assert "cause" in rec["fires"][0]
        C.dump(log / "records" / day / (st + ".json"), json.loads(json.dumps({k: v for k, v in rec.items() if k not in ("run", "alerts", "pages", "bulletin_day")}, default=str)))
        shutil.copytree(FIX / name, log / "inputs" / st)
    subprocess.run([sys.executable, str(LIVE / "score.py"), "--log", str(log), "--now", "2025-03-27T00:00:00Z", "--late-h", "24"], check=True)
    f = json.loads((log / "scores/20250324T1500Z.json").read_text())["fires"][0]
    assert f["h5"]["held"] and f["h5"]["R_km"] == 2.6                    # the same numbers test_live.py gets from the old records


# ---------------------------------------------------------------- history panel
def test_history_is_history_and_matches_the_table(tmp_path):
    h = json.loads((LIVE / "config/cause_history.json").read_text(encoding="utf-8"))
    assert h["years"] == [2016, 2025] and h["source"] and h["retrieved"] and h["responses_sha256"]
    rec = run(inputs_with(tmp_path), tmp_path)
    H = rec["fires"][0]["cause_history"]
    assert (H["province"], H["month"]) == ("gyeongbuk", 3)                      # 의성, reported in March
    assert H["by_cause"] == h["provinces"]["gyeongbuk"]["03"] and H["n_fires"] == sum(H["by_cause"].values()) == 162
    html = fire_page(rec, tmp_path)
    assert "say nothing about the cause of this fire" in html and "산림청 국가산불정보시스템 산불통계" in html


def test_history_absent_outside_the_two_provinces():
    cfg = C.settings()
    assert cause.history_for(cfg, "경기도 연천군", "2026-11-16T03:00:00Z") is None
    assert cause.history_for(cfg, "경상북도 영덕군", None) is None
    assert cause.history_for(cfg, "강원특별자치도 강릉시", "2025-03-22T15:30:00Z")["month"] == 3      # 00:30 KST 23 March is still March
    assert cause.history_for(cfg, "강원특별자치도 강릉시", "2025-03-31T15:30:00Z")["month"] == 4      # 00:30 KST 1 April: KST month, not UTC
