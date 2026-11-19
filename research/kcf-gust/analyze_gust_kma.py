"""KMA (primary) gust classes and frozen-R held test, PROTOCOL amendments 2-3. ERA5 results read from work/gust_hours.json."""
import json
from datetime import datetime, timedelta
R = json.load(open("work/kma_asos_hourly.json")); E = json.load(open("work/gust_hours.json"))
N = json.load(open("../kcf-margin/numbers.json"))["gyeongbuk_stress"]["hourly"]; hy = {(x["kst_hour"], x["h"]): x for x in N}
FR = {"<10": (2.6, 3.0), "10-20": (4.7, 5.9), ">=20": (8.6, 12.0)}
ST = {278: "Uiseong", 136: "Andong", 276: "Cheongsong", 277: "Yeongdeok"}
rows = {(r["tm"], r["stn"]): r for r in R}
D0 = datetime(2025, 3, 25)
def tm_of(H): return (D0 + timedelta(hours=H)).strftime("%Y%m%d%H00")
def mins(t): return int(t[:2]) * 60 + int(t[2:])
def val(stn, H):
    """gust m/s at stamp H (KST hour on 25 March), None = no row, 0 = no record (<10)."""
    r = rows.get((tm_of(H), stn))
    if r is None: return None
    g = float(r["gst_ws"])
    if g < 0: return 0.0
    Hd = (D0 + timedelta(hours=H)).hour; gm = mins(r["gst_tm"].zfill(4)); lo = ((Hd - 1) % 24) * 60; hi = Hd * 60 if Hd else 1440
    inh = (lo < gm <= hi) if Hd else (gm > 1380 or gm == 0)
    return g if inh else 0.0   # repeat of an earlier gust: dropped (amendment 3)
def cls(x): return "<10" if x < 10 else "10-20" if x < 20 else ">=20"
def fw(H):
    v = {ST[s]: val(s, H) for s in ST}; p = [x for x in v.values() if x is not None]
    return v, (max(p) if p else None)
out = []
for H in range(25):
    v, m = fw(H); r = dict(kst_stamp=H, by_station=v, fire_wide=m, cls=cls(m) if m is not None else None, era5_fire_wide=E[H]["fire_wide_max"], era5_cls=E[H]["class_at_stamp"])
    for h in (5, 8):
        if H == 24: r[f"fwd{h}"] = None; continue
        ms = []; hole = 0
        for k in range(H + 1, H + h + 1):
            _, mk = fw(k); 
            if mk is None: hole += 1
            else: ms.append(mk)
        fwm = max(ms); c = cls(fwm); Rk = FR[c][0 if h == 5 else 1]; x = hy.get((H, h)); e = E[H][f"fwd{h}"]
        r[f"fwd{h}"] = dict(fire_wide_max=fwm, cls=c, R_km=Rk, reach_km=x["reach_km"] if x else None, complete=bool(x and x["complete"]),
                            held=None if not (x and x["complete"]) else x["reach_km"] <= Rk, window_stamps_without_any_station=hole,
                            era5_cls=e["cls"], era5_R=e["R_km"], era5_held=e["held"], same_class_as_era5=(c == e["cls"]))
    out.append(r)
json.dump(out, open("work/gust_hours_kma.json", "w"), indent=1)
for r in out:
    f5, f8 = r["fwd5"], r["fwd8"]
    print(f'{r["kst_stamp"]:02d} stamp KMA {r["fire_wide"]!s:>5} {r["cls"]:>5} | ERA5 {r["era5_fire_wide"]:5.1f} {r["era5_cls"]:>5}', *(
        [f' | 5h KMA {f5["fire_wide_max"]:4.0f} {f5["cls"]:>5} R{f5["R_km"]:4.1f} reach {f5["reach_km"]:5.1f} held={f5["held"]} | ERA5 {f5["era5_cls"]:>5} held={f5["era5_held"]}'] if f5 else ["| -"]),
          *([f' | 8h KMA {f8["fire_wide_max"]:4.0f} {f8["cls"]:>5} R{f8["R_km"]:4.1f} reach {f8["reach_km"]:5.1f} held={f8["held"]} | ERA5 {f8["era5_cls"]:>5} held={f8["era5_held"]}'] if f8 else []))
for h in (5, 8):
    c = [r[f"fwd{h}"] for r in out if r[f"fwd{h}"] and r[f"fwd{h}"]["complete"]]
    from collections import Counter
    print(h, "complete", len(c), "KMA held", sum(x["held"] for x in c), "ERA5 held", sum(x["era5_held"] for x in c), "classes KMA", dict(Counter(x["cls"] for x in c)),
          "same class as ERA5", sum(x["same_class_as_era5"] for x in c), "windows with a hole", sum(x["window_stamps_without_any_station"] > 0 for x in c))
    for k in ("<10", "10-20", ">=20"):
        s = [x for x in c if x["cls"] == k]; print("  ", k, len(s), "held", sum(x["held"] for x in s))
