"""Invented-metadata tests for cohort/apply_filters.py (A1 §1.2 items 9–12 and §1.3)."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cohort"))

import apply_filters as F  # noqa: E402


def meta(lat, lon, day, first="2021-07-01T00:00:00", last="2021-07-20T00:00:00"):
    return dict(loc=(lat, lon), day=date.fromisoformat(day),
                win=(datetime.fromisoformat(first), datetime.fromisoformat(last)))


def split(*rows):
    return [dict(Incident_C=k, part=p, u=str(i / 100), eligible_rank=str(i + 1)) for i, (k, p) in enumerate(rows)]


def test_independence_excludes_test_fire_near_reference_and_refills():
    rows = split(("B1", "b"), ("C1", "c"), *[(f"D{i}", "d") for i in range(32)])
    md = {"B1": meta(40.0, -120.0, "2021-07-01"), "C1": meta(45.0, -110.0, "2021-07-01")}
    md.update({f"D{i}": meta(30.0 + i, -100.0, "2021-07-01") for i in range(32)})
    ref = {"R": meta(40.1, -120.0, "2021-07-10")}               # ~11 km and 9 days from B1
    out, s = F.run(rows, md, ref)
    st = {o["Incident_C"]: o for o in out}
    assert st["B1"]["status"] == "excluded"
    assert s["replacements"] == ["D0"] and st["D0"]["part"] == "b"
    assert s["kept"]["d"] == 31


def test_d_floor_stops_refills():
    rows = split(("B1", "b"), ("B2", "b"), *[(f"D{i}", "d") for i in range(31)])
    md = {"B1": meta(40.0, -120.0, "2021-07-01"), "B2": meta(40.0, -120.2, "2021-07-01")}
    md.update({f"D{i}": meta(10.0 + i, -100.0, "2021-07-01") for i in range(31)})
    out, s = F.run(rows, md, {"R": meta(40.0, -120.1, "2021-07-01")})
    assert s["excluded"]["b"] == 2 and len(s["replacements"]) == 1 and s["kept"]["d"] == 30


def test_leakage_drops_from_a_only():
    rows = split(("C1", "c"), ("A1", "a"), ("A2", "a"))
    md = {"C1": meta(40.0, -120.0, "2021-07-01"), "A1": meta(40.2, -120.0, "2021-07-20"),
          "A2": meta(40.2, -120.0, "2021-09-30",                  # near in space but 91 days apart, and a
                     "2021-09-30T00:00:00", "2021-10-10T00:00:00")}  # separate survey window (not a duplicate of A1)
    out, _ = F.run(rows, md, {})
    st = {o["Incident_C"]: o["status"] for o in out}
    assert st == {"C1": "kept", "A1": "excluded", "A2": "kept"}


def test_duplicate_removes_a_copy_not_c():
    rows = split(("C1", "c"), ("A1", "a"))
    md = {"C1": meta(40.0, -120.0, "2021-07-01"), "A1": meta(40.01, -120.0, "2021-12-01",
                                                               "2021-07-10T00:00:00", "2021-07-30T00:00:00")}
    out, _ = F.run(rows, md, {})
    st = {o["Incident_C"]: o for o in out}
    assert st["C1"]["status"] == "kept" and st["A1"]["status"] == "excluded"
    assert "duplicate" in st["A1"]["reason"]


def test_missing_metadata_kept_and_counted():
    rows = split(("B1", "b"))
    out, s = F.run(rows, {}, {"R": meta(40.0, -120.0, "2021-07-01")})
    assert out[0]["status"] == "kept" and s["missing_metadata"] == 1


def test_haversine_scale():
    assert abs(F.km((40.0, -120.0), (41.0, -120.0)) - 111.2) < 0.5


def test_ledger_incident_excluded_from_test_parts():
    rows = split(("C1", "c"), *[(f"D{i}", "d") for i in range(32)])
    md = {"C1": meta(40.0, -120.0, "2021-07-01")}
    md.update({f"D{i}": meta(10.0 + i, -100.0, "2021-07-01") for i in range(32)})
    out, s = F.run(rows, md, {}, ledger_ids=["C1"])
    assert {o["Incident_C"]: o["status"] for o in out}["C1"] == "excluded" and s["replacements"] == ["D0"]


def test_duplicate_of_opened_pilot_is_exposed():
    rows = split(("B1", "b"), ("A1", "a"), *[(f"D{i}", "d") for i in range(32)])
    md = {"B1": meta(40.0, -120.0, "2021-07-01"), "A1": meta(40.01, -120.0, "2021-07-01")}
    md.update({f"D{i}": meta(10.0 + i, -100.0, "2021-07-01") for i in range(32)})
    out, s = F.run(rows, md, {}, opened=["A1"])
    st = {o["Incident_C"]: o for o in out}
    assert st["B1"]["status"] == "excluded" and "opened" in st["B1"]["reason"]
    assert s["replacements"] == ["D0"]
