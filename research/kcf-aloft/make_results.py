#!/usr/bin/env python3
"""Fill RESULTS.template.md with the tables printed by tables.py (so no table is typed by hand).

    python3 tables.py numbers.json > derived/tables.md && python3 make_results.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sec, cur = {}, None
for line in (HERE / "derived" / "tables.md").read_text().splitlines():
    m = re.match(r"## (T\d+b?) ", line)
    if m:
        cur = m.group(1)
        sec[cur] = []
    elif line.startswith("## "):
        cur = None
    elif cur:
        sec[cur].append(line)
tpl = (HERE / "RESULTS.template.md").read_text()


def fill(m):
    key, part = m.group(1), m.group(2)
    body = "\n".join(sec[key]).strip("\n")
    if part:                                   # {{T1:2}} = the 2nd blank-line-separated block of the section
        blocks = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
        return blocks[int(part) - 1]
    return body


out = re.sub(r"\{\{(T\d+b?)(?::(\d+))?\}\}", fill, tpl)

# G-obs burden: text depends on how much of the station fetch is in numbers.json
import json
N = json.load(open(HERE / "numbers.json"))
gb, q = N["burden"]["G-obs"], N["gobs_quality"]
done = gb.get("complete_seasons", [])
if gb["alarm_days_per_point_season"]:
    m, f, anyp = gb["alarm_days_per_point_season"], gb["false_alarm_days_per_point_season"], gb["days_any_point_per_season"]
    g = N["burden"]["G"]["alarm_days_per_point_season"]
    other = [s for s in done if s not in gb["full_seasons"]]
    txt = (f"In the burden set it fires on {m['mean']:.1f} days per point and season ({m['ci95'][0]:.1f}-{m['ci95'][1]:.1f}; seasons "
           f"{gb['full_seasons'][0]}-{gb['full_seasons'][-1]}), against {g['mean']:.1f} for G, and on {anyp['mean']:.1f} days of a season at one or\n"
           f"  more of the ten points.")
    if other:
        txt += " Seasons " + ", ".join(str(s) for s in other) + " are in section 5."
    missing = [s for s in (2019, 2020, 2021, 2022, 2023, 2024, 2025) if s not in done]
    nd = ("- G-obs in the burden set for season" + ("s " if len(missing) > 1 else " ") + ", ".join(str(s) for s in missing)
          + " (station hours not fetched or incomplete).") if missing else "- Nothing further for G-obs: all seven seasons were read."
else:
    txt = "Its burden-set counts are **NOT RUN yet**: the station hours for the ten points are still being fetched."
    nd = "- G-obs in the burden set (the station hours are still being fetched; about 17,000 calls)."
out = out.replace("{{GOBS_BURDEN}}", txt).replace("{{GOBS_NOT_DONE}}", nd)
out = out.replace("{{KMA_FETCH}}", f"{q['hours_fetched']:,} hours, {len(q['hours_failed'])} failed after 8 tries.")
(HERE / "RESULTS.md").write_text(out)
note = (HERE / "NOTE.template.md").read_text()
if gb["alarm_days_per_point_season"]:
    ko = f"한 지점에서 봄철 평균 {m['mean']:.1f}일 울립니다(예보 돌풍 기준 {g['mean']:.1f}일)."
    en = f"It fires on {m['mean']:.1f} days per place per spring (forecast gust rule: {g['mean']:.1f})."
else:
    ko = "지점별로 봄철에 며칠 울리는지는 아직 집계하지 못했습니다(관측 자료를 받는 중)."
    en = "How many days per spring it fires at the ten points is not counted yet (station data still being fetched)."
(HERE / "NOTE.md").write_text(note.replace("{{KO_BURDEN}}", ko).replace("{{EN_BURDEN}}", en))
print("wrote RESULTS.md,", len(out.splitlines()), "lines; sections available:", ", ".join(sec))
