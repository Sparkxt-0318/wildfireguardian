"""The headline statements of RESULTS.md and NOTE.md, checked against numbers.json.  python3 -m pytest -q tests"""
import json
from pathlib import Path

N = json.load(open(Path(__file__).resolve().parent.parent / "numbers.json"))
F = lambda r, k="full": N["fire_set"][r][k]
B = lambda r: N["burden"][r]
mean = lambda r, key="alarm_days_per_point_season": round(B(r)[key]["mean"], 1)


def test_the_n():
    assert F("G")["fires"] == 12 and F("G")["fire_days"] == 43 and sum(N["pooled_hours"]["G"].values()) == 791
    assert F("G")["run_fire_days"] == 9 and F("G")["fires_with_run"] == 4 and F("G")["run_hours"] == 55


def test_gust_rule():
    assert F("G")["warned"]["k"] == 4 and sorted(F("G")["leads_h"]) == [0, 1, 12, 21]
    assert F("G")["alarm_days_without_run"]["k"] == 0 and F("G")["alarm_days_without_run"]["n"] == 34
    assert mean("G") == 3.7 and mean("G", "days_any_point_per_season") == 11.8


def test_wind_aloft():
    v = N["verdicts"]
    assert N["s_match"]["threshold_ms"] == 29.7 and F("A-match")["warned"]["k"] == 3
    assert v["A-match"]["more_reliably"] == "no better" and v["A-match"]["full"]["lead_a_minus_g_h"] == [0, 1, -4]
    assert F("A25")["warned"]["k"] == 4 and sorted(v["A25"]["full"]["lead_a_minus_g_h"]) == [1, 2, 2, 2]
    assert mean("A25") == 11.3 and F("A25")["alarm_days_without_run"]["k"] == 5
    assert F("A30")["warned"]["k"] == 3 and mean("A30") == 3.1
    assert F("A-cal")["warned"]["k"] == 8 and sorted(v["A-cal"]["full"]["lead_a_minus_g_h"]) == [3, 5, 5, 7]
    assert mean("A-cal") == 55.1 and mean("A-cal", "days_any_point_per_season") == 73.8
    assert F("A-cal")["alarm_days_without_run"]["k"] == 19
    assert v["A-cal"]["more_reliably"].startswith("A warned more") and v["A-cal"]["earlier"] == "A earlier"
    assert F("A30+G")["warned"]["k"] == 4 and mean("A30+G") == 4.5 and v["A30+G"]["full"]["lead_a_minus_g_h"] == [0, 1, 1, 1]
    assert F("A+G")["warned"] == F("A-cal")["warned"]


def test_25_march_and_without_it():
    h = {x["kst_hour"]: x for x in N["march25_hours"]}
    assert (h[8]["G"], h[9]["G"], h[8]["A30"], h[9]["A30"], h[7]["A25"], h[8]["A25"], h[1]["A_cal"], h[2]["A_cal"]) == (0, 1, 0, 1, 0, 1, 0, 1)
    assert h[18]["G_obs"] == 0 and h[19]["G_obs"] == 1 and h[10]["run"] and not h[9]["run"]
    assert [F(r, "without_25_march")["warned"]["k"] for r in ("G", "A-match", "A25", "A-cal")] == [3, 2, 3, 7]
    assert sum(1 for d in F("A25+G", "fire_days") if d["run_hours"] > 0 and not d["warned"]) == 5


def test_second_model():
    x = N["second_model_ifs"]["fire_set"]
    assert x["A30"]["IFS"]["full"]["warned"]["k"] == 0 and x["A25"]["IFS"]["full"]["leads_h"] == [0]
    assert all(r["ifs_w850"] == 27.6 and r["ifs_10fg"] >= 20 for r in x["gust_any_step_20"]["march25_10_to_16_kst"])
    assert len(x["fires_without_ifs"]) == 5


def test_sensitivity_statements():
    s = N["sensitivity"]
    assert sorted(s["G k=1"]["full"]["leads_h"]) == [1, 2, 13, 22]
    assert [s[k]["full"]["warned"]["k"] for k in ("G k=3", "G k=4", "G k=6", "G k=2, 5 h window", "A25 k=2", "A30 k=2")] == [3, 2, 1, 2, 3, 2]
    w = {x["threshold"]: x for x in N["sweep"]["w850_k1"]}
    assert w[26]["warned"] == 4 and w[28]["warned"] == 3 and w[18]["warned"] == 8
    assert max(x["warned"] for x in N["sweep"]["gust_k1"] + N["sweep"]["gust_k2"]) == 6
