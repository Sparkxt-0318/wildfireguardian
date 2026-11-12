"""Tests of score.py (PROTOCOL v2.3) on SYNTHETIC result rows (invented answers, no person).
Run: python3.12 -m pytest -q tools/test_score.py"""
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
    "C2": {"case": "C2", "found": True, "leave_by_kst": "10:30"},
    "C4": {"case": "C4", "found": True, "leave_by_kst": None},
}


def row(**kw) -> dict[str, str]:
    d = {c: "" for c in score.COLUMNS}
    d.update({k: str(v) for k, v in kw.items()})
    return d


def group(g: str, n: int, edit=None) -> list[dict[str, str]]:
    """n synthetic participants, each with C1, C2, C4 first (channel rotating), every answer correct."""
    rows = []
    chs = score.CHANNELS[g]
    for p in range(n):
        for i, c in enumerate(("C1", "C2", "C4")):
            r = row(participant=f"{g}{p + 1:02d}", group=g, seq=i + 1, case=c, channel=chs[(i + p) % len(chs)], exposure="first",
                    open_verbatim="(synthetic)", open_code_1="NEUTRAL", open_code_2="NEUTRAL", q1_seconds="12")
            if CASES[c]["leave_by_kst"]:
                r.update(q1_time=CASES[c]["leave_by_kst"], later_verbatim="(synthetic)", later_code_1="NEUTRAL", later_code_2="NEUTRAL", later_answer="not_stated")
            else:
                r.update(q1_time="none", stay_answer="no")
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
    ok, text = run(group("A", 8) + group("B", 6))
    assert ok, text
    assert "Q1 C1** (first exposure, pooled over channels): 0 misses of 8 (allowed ≤ 1)" in text


def test_allowances():
    assert [score.allowed_q1(n) for n in (6, 9, 10, 12)] == [1, 1, 2, 2]
    assert [score.allowed_q4(n) for n in (6, 9, 10, 12)] == [0, 0, 1, 1]


def test_q1_cut_applies_except_a4():
    def slow(rows):
        for r in rows:
            if r["case"] == "C1":
                r["q1_seconds"] = "95"
    ok, text = run(group("B", 6, slow))
    # B channels rotate headline/a4: only headline first exposures miss on time
    heads = sum(1 for r in group("B", 6) if r["case"] == "C1" and r["channel"] == "headline")
    assert f"{heads} misses of 6" in text and "no cut on this channel" in text
    assert not ok


def test_no_time_on_a_leave_by_case_is_a_q1_miss_and_a_time_on_c4_is_critical():
    def bad(rows):
        rows[0]["q1_time"] = "none"          # C1: said no time is given
        rows[2]["q1_time"] = "10:00"         # C4: gave a time to leave
    ok, text = run(group("A", 6, bad))
    assert not ok and "said no time is given" in text
    assert "Q1 critical (a time to leave given where none is shown)**: 1 of" in text


def test_repeating_the_data_time_is_not_a_miss_but_ambiguous_time_is_resolved_by_the_closed_answer():
    def amb(rows):
        rows[2]["open_code_2"] = "AMBIGUOUS-TIME"   # "오전 10시 자료로는…": closed answer says none → cleared
    ok, text = run(group("A", 6, amb))
    assert ok, text
    assert "AMBIGUOUS-TIME open answers cleared by the closed time question (no time given there): 1" in text


def test_either_coder_rule_and_closed_answers():
    def one(rows):
        rows[2]["open_code_2"] = "STAY"
        rows[4]["later_code_1"] = "USABLE-LATER"
        rows[3]["later_answer"] = "yes"
        rows[5]["stay_answer"] = "yes"
    ok, text = run(group("A", 6, one))
    assert not ok
    assert "Q3 (read as stay; C4 and C5)**: 2 of" in text
    assert "Q2 (a later time read as usable; C1 and C2)**: 2 of" in text


def test_not_stated_and_unsure_are_not_misses():
    def ns(rows):
        rows[2]["stay_answer"] = "unsure"
    ok, text = run(group("A", 6, ns))
    assert ok and "stay answered “unsure” (not a miss, reported): 1" in text


def test_q4_scored_for_a_descriptive_for_b():
    def a(rows):
        rows[0]["q4_code_2"] = "EMERGENCY-SERVICE"
    ok, text = run(group("A", 6, a))
    assert not ok and "Q4 (official first; first item only)**: 1 misses of 6 (allowed ≤ 0)" in text

    def b(rows):
        rows[0]["q4_code_1"] = rows[0]["q4_code_2"] = "MODEL-AUTHORITY"
        rows[3]["q4_code_1"] = rows[3]["q4_code_2"] = "NOT-STATED"
    ok, text = run(group("B", 6, b))
    assert ok, text
    assert "DESCRIPTIVE for group B" in text and "⚑ MODEL-AUTHORITY" in text


def test_malformed_sheet_is_refused():
    for field, value, msg in (("group", "C", "group must be A or B"), ("later_answer", "maybe", "later_answer"), ("q1_time", "ten", "q1_time"), ("open_code_1", "SAFE", "unknown code")):
        rows = group("A", 6)
        rows[0][field] = value
        try:
            run(rows)
        except score.SheetError as e:
            assert msg in str(e)
        else:
            raise AssertionError(f"{field}={value} accepted")


def test_template_from_build_print_has_the_columns():
    kit = HERE.parent
    with (kit / "results_template.csv").open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == score.COLUMNS
    doc = json.loads((kit / "CASES.json").read_text(encoding="utf-8"))
    assert [c["case"] for c in doc["cases"]] == ["C1", "C2", "C4", "C5"]


def test_cli_exit_code_on_empty_template_is_not_a_pass():
    r = subprocess.run([sys.executable, str(HERE / "score.py"), str(HERE.parent / "results_template.csv")], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
