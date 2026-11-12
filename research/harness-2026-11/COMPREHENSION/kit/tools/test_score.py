"""Tests of score.py on SYNTHETIC result rows (invented answers, no person). Run: python3.12 -m pytest -q tools/test_score.py"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score  # noqa: E402

CASES = {
    "C1": {"case": "C1", "found": True, "leave_by_kst": "10:50"},
    "C2": {"case": "C2", "found": True, "leave_by_kst": "10:30", "q2_case": True},
    "C4": {"case": "C4", "found": True, "leave_by_kst": None},
}


def row(**kw) -> dict[str, str]:
    d = {c: "" for c in score.COLUMNS}
    d.update({k: str(v) for k, v in kw.items()})
    return d


def group_a(n: int, edit=None) -> list[dict[str, str]]:
    """n synthetic participants, each with C1, C2, C4 first (channel rotating), all answers correct."""
    rows = []
    chs = score.CHANNELS["A"]
    for p in range(n):
        for i, c in enumerate(("C1", "C2", "C4")):
            r = row(participant=f"A{p + 1:02d}", group="A", seq=i + 1, case=c, channel=chs[(i + p) % 3], exposure="first",
                    open_verbatim="(synthetic)", open_code_1="NEUTRAL", open_code_2="NEUTRAL")
            if CASES[c]["leave_by_kst"]:
                r.update(q1_time=CASES[c]["leave_by_kst"], q1_seconds="12")
            else:
                r.update(q3_answer="no")
            if c == "C2":
                r.update(q2_answer="no")
            if i == 0:
                r.update(q4_verbatim="(synthetic)", q4_code_1="OFFICIAL", q4_code_2="OFFICIAL")
            rows.append(r)
    if edit:
        edit(rows)
    return rows


def run(rows: list[dict[str, str]]) -> tuple[bool, str]:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=score.COLUMNS)
    w.writeheader()
    w.writerows(rows)
    p = HERE / "_synthetic_results.csv"
    p.write_text(buf.getvalue(), encoding="utf-8")
    try:
        return score.score(score.load(p), CASES)
    finally:
        p.unlink()


def test_clean_sheet_meets_every_target():
    ok, text = run(group_a(8))
    assert ok, text
    assert "Q1 C1** (first exposure, pooled over channels): 0 misses of 8 (allowed ≤ 1)" in text


def test_q1_allowance_is_floor_point_two_n():
    assert [score.allowed_q1(n) for n in (6, 9, 10, 12)] == [1, 1, 2, 2]
    assert [score.allowed_q4(n) for n in (6, 9, 10, 12)] == [0, 0, 1, 1]

    def two_slow(rows):
        for r in rows[:6]:
            if r["case"] == "C1":
                r["q1_seconds"] = "31"
    ok, text = run(group_a(8, two_slow))
    assert not ok and "2 misses of 8 (allowed ≤ 1)" in text and "after 31 s" in text


def test_one_coder_is_enough_for_a_miss():
    def one(rows):
        rows[2]["open_code_2"] = "STAY"  # C4 of participant 1
    ok, text = run(group_a(6, one))
    assert not ok and "Q3 (read as safe or as stay)**: 1 of" in text


def test_time_invented_is_critical_and_closed_yes_counts():
    def bad(rows):
        rows[2]["open_code_1"] = "TIME-INVENTED"
        rows[5]["q3_answer"] = "yes"
        rows[4]["q2_answer"] = "yes"
    ok, text = run(group_a(6, bad))
    assert not ok
    assert "Q1 critical (time invented where none is shown)**: 1 of" in text
    assert "closed Q3 answered yes" in text and "closed Q2 answered yes" in text


def test_unsure_is_reported_not_a_miss():
    def unsure(rows):
        rows[2]["q3_answer"] = "unsure"
    ok, text = run(group_a(6, unsure))
    assert ok and "answered “unsure” (not a miss; reported): 1" in text


def test_q4_needs_official_from_both_coders():
    def q4(rows):
        rows[0]["q4_code_2"] = "NEUTRAL"
    ok, text = run(group_a(6, q4))
    assert not ok and "Q4 (official first; first item only)**: 1 misses of 6 (allowed ≤ 0)" in text


def test_groups_are_never_pooled_and_malformed_is_refused():
    rows = group_a(6)
    rows[0]["group"] = "C"
    try:
        run(rows)
    except score.SheetError as e:
        assert "group must be A or B" in str(e)
    else:
        raise AssertionError("malformed group accepted")


def test_template_from_build_print_has_the_columns():
    kit = HERE.parent
    with (kit / "results_template.csv").open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == score.COLUMNS
    doc = json.loads((kit / "CASES.json").read_text(encoding="utf-8"))
    assert all(c["case"] in {"C1", "C2", "C3", "C4", "C5"} for c in doc["cases"])


def test_cli_exit_code_on_empty_template_is_not_a_pass():
    # the unfilled template has first exposures with no time: it must never score as a pass
    r = subprocess.run([sys.executable, str(HERE / "score.py"), str(HERE.parent / "results_template.csv")], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
