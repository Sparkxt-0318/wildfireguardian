import json
R = json.load(open("work/gust_hours.json")); L = json.load(open("work/fetch_log.json"))
P = ["Uiseong", "Andong", "Cheongsong", "Yeongyang", "Yeongdeok"]
def yn(x): return "-" if x is None else ("held" if x else "**MISSED**")
def cell(f):
    if not f: return "-"
    star = "†" if f["cls"] == ">=20" else ""
    return f'{f["fire_wide_max"]:.1f} / {f["cls"]}{star} / R {f["R_km"]:g} / reach {f["reach_km"]:.1f} / {yn(f["held"]) if f["complete"] else "not scored (truncated)"}'
t = ["| KST stamp | " + " | ".join(P) + " | fire-wide max | class at stamp | 5 h: fwd max / class / R / reach / verdict | 8 h: fwd max / class / R / reach / verdict |", "|" + "---|" * (len(P) + 5)]
for r in R:
    t.append(f'| {r["kst_stamp"]:02d}:00 | ' + " | ".join(f"{r[p]:.1f}" for p in P) + f' | {r["fire_wide_max"]:.1f} | {r["class_at_stamp"]}{"†" if r["class_at_stamp"]==">=20" else ""} | {cell(r["fwd5"])} | {cell(r["fwd8"])} |')
open("work/hour_table.md", "w").write("\n".join(t))
