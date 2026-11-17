"""Timeline figure, map frames and MP4 for the KCF replay. Usage: python3 figures.py out/fire_discs.json out/runs OUT_DIR"""
from __future__ import annotations

import json, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Circle
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KST = timezone(timedelta(hours=9))
for p in ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
    if Path(p).exists():
        font_manager.fontManager.addfont(p)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

STEP_COL = {"LEAVE_NOW": "#c62828", "PREPARE_VULNERABLE_FIRST": "#f9a825", "NONE": "#cfd8dc"}
STEP_KO = {"LEAVE_NOW": "위험구역 (5 h): 즉시 대피", "PREPARE_VULNERABLE_FIRST": "잠재적 위험구역 (8 h): 취약계층 먼저",
           "NONE": "단계 없음"}

NAMED = [  # (place id, label)
    ("osm:node/415158322", "화매리 (영양군 석보면)"),
    ("osm:node/415160302", "지품리 (영덕군 지품면)"),
    ("osm:node/415160188", "옥류리 (영덕군 지품면)"),
    ("osm:node/415160192", "매정리 (영덕군 영덕읍)"),
    ("osm:node/415160193", "노물리 (영덕군 영덕읍)"),
    ("osm:node/415160154", "강구리 (영덕군 강구면)"),
]


def k(h, m=0, day=25):
    return datetime(2025, 3, day, h, m, tzinfo=KST)


# Documented events (SOURCES.md). kind: alert | road | fire | other. All SINGLE-source.
COUNTY = [(k(18, 0), "alert", "18:00 지품면·달산면 대피명령·CBS"), (k(19, 30), "alert", "19:30 9개 읍·면 대피명령"),
          (k(21, 0), "alert", "21:00 영덕군 CBS")]
DOC = {
    "osm:node/415158322": [(k(18, 0), "other", "~18:00 이장 음성 안내 (46가구)"), (k(18, 0), "fire", "~18:00 마을 가장자리 화염")],
    "osm:node/415160302": COUNTY + [(k(18, 25), "road", "18:25 황장재 통행제한 CBS"), (k(18, 58), "road", "18:58 국도34호선 구미~황장 통제"),
                                    (k(19, 4), "road", "19:04 도계→영양 도로통제"), (k(20, 25), "other", "20:25 지품리 단전")],
    "osm:node/415160188": COUNTY + [(k(18, 52), "alert", "18:52 옥류리 CBS"), (k(18, 58), "road", "18:58 국도34호선 통제")],
    "osm:node/415160192": COUNTY[1:] + [(k(20, 0), "other", "~20:00 이장 방문 안내"), (k(20, 40), "fire", "~20:40 마을에 불 (주민 1인)")],
    "osm:node/415160193": COUNTY[1:] + [(k(0, 0, 26), "other", "~24:00 주민 인지")],
    "osm:node/415160154": COUNTY[1:] + [(k(21, 58), "road", "21:58 국도7호선 송라 지경삼거리 통제"),
                                        (k(0, 7, 26), "alert", "00:07 강구·남정 문자"), (k(0, 37, 26), "fire", "~00:37 불 도달")],
}
KIND_STYLE = {"alert": ("v", "#1565c0"), "road": ("s", "#455a64"), "fire": ("*", "#b71c1c"), "other": ("o", "#6d4c41")}


def load_runs(runs):
    R = {}
    for p in Path(runs).glob("*.json"):
        j = json.loads(p.read_text())
        R[(j["region"], j["standin"], j["horizon"], j["issue_utc"])] = j
    return R


def timeline(R, out):
    issues = sorted({key[3] for key in R})
    fig, axes = plt.subplots(len(NAMED), 1, figsize=(15, 2.5 * len(NAMED)), sharex=True)
    x0, x1 = k(11, 50), k(1, 10, 26)
    for ax, (pid, label) in zip(axes, NAMED):
        for lane, st in enumerate(("ORDINARY", "RUNNING", "WORST")):
            y = 2 - lane
            for T in issues:
                job = R.get(("yeongdeok_2025", st, "8h", T))
                if not job:
                    continue
                row = next(r for r in job["rows"] if r["place_id"] == pid)
                t0 = datetime.fromisoformat(T).astimezone(KST)
                ax.add_patch(plt.Rectangle((t0, y - 0.35), timedelta(hours=1), 0.7, color=STEP_COL[row["step"]], lw=0))
                if row["ld_s"] is not None and row["cut_within_H"]:
                    ld = t0 + timedelta(seconds=row["ld_s"])
                    if ld <= x1:
                        ax.plot([t0, ld], [y, y], color="k", lw=0.6, alpha=0.5)
                        ax.plot(ld, y, marker="|", color="k", ms=10, mew=2)
                elif row["ld_s"] is None:
                    ax.text(t0 + timedelta(minutes=30), y, "×", ha="center", va="center", fontsize=9)
            ax.text(x0 - timedelta(minutes=5), y, st, ha="right", va="center", fontsize=8)
        for t, kind, txt in DOC.get(pid, []):
            m, c = KIND_STYLE[kind]
            ax.plot(t, 3.15, marker=m, color=c, ms=9 if kind == "fire" else 7)
            ax.axvline(t, color=c, lw=0.6, ls=":" if kind != "fire" else "-", alpha=0.8)
        for i, (t, kind, txt) in enumerate(sorted(DOC.get(pid, []))):
            ax.text(t + timedelta(minutes=2), 3.45 + 0.62 * (i % 4), txt, fontsize=7, color=KIND_STYLE[kind][1], ha="left",
                    va="bottom", bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.8))
        ax.set_ylim(-0.6, 6.1)
        ax.set_yticks([])
        ax.set_title(label, loc="left", fontsize=11, fontweight="bold")
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    import matplotlib.dates as mdates
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(tz=KST))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=KST))
    axes[-1].set_xlim(x0, x1)
    axes[-1].set_xlabel("2025-03-25 ~ 26 KST")
    handles = [plt.Rectangle((0, 0), 1, 1, color=STEP_COL[s]) for s in STEP_COL] + \
              [plt.Line2D([], [], marker="|", color="k", ls="", ms=10, mew=2)] + \
              [plt.Line2D([], [], marker=KIND_STYLE[x][0], color=KIND_STYLE[x][1], ls="") for x in ("alert", "road", "fire", "other")]
    labels = [STEP_KO[s] for s in STEP_COL] + ["latest safe departure shown at that hour (8 h)", "documented alert/order",
                                                  "documented road closure", "documented fire at the place", "other documented event"]
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("What the screen would have shown, hour by hour (each block = one issue hour; row = R(h) stand-in), "
                 "vs documented times (all single-source; SOURCES.md)", fontsize=11)
    fig.tight_layout(rect=(0.03, 0.05, 1, 0.97))
    fig.savefig(out / "timeline.png", dpi=130)
    plt.close(fig)


ARM_LANES = ("ORDINARY", "RUNNING", "WORST", "MEASURED", "MEASURED_GUST")
ARM_LABEL = {"ORDINARY": "ORDINARY", "RUNNING": "RUNNING", "WORST": "WORST", "MEASURED": "MEASURED (spread class)",
             "MEASURED_GUST": "MEASURED+GUST (ERA5, PROVISIONAL)"}


def timeline_csv(per_place_csv, out, hz="8h"):
    """Same figure as timeline(), read from the merged per_place.csv so the three stand-in rows need no rerun and the two
    MEASURED arms are added as lanes 4 and 5 (nothing removed or relabelled)."""
    import csv
    rows = {}
    for r in csv.DictReader(open(per_place_csv, encoding="utf-8")):
        if r["region"] == "yeongdeok_2025" and r["horizon"] == hz:
            rows[(r["place_id"], r["standin"], r["issue_kst"])] = r
    issues = sorted({key[2] for key in rows})
    fig, axes = plt.subplots(len(NAMED), 1, figsize=(15, 3.1 * len(NAMED)), sharex=True)
    x0, x1 = k(11, 50), k(1, 10, 26)
    n = len(ARM_LANES)
    for ax, (pid, label) in zip(axes, NAMED):
        for lane, st in enumerate(ARM_LANES):
            y = n - 1 - lane
            for ik in issues:
                r = rows.get((pid, st, ik))
                if not r:
                    continue
                mo_day, hm = ik.split(" ")
                hh = int(hm[:2]); day = int(mo_day[3:])
                t0 = datetime(2025, 3, day, hh, 0, tzinfo=KST)
                ax.add_patch(plt.Rectangle((t0, y - 0.35), timedelta(hours=1), 0.7, color=STEP_COL[r["government_step"]], lw=0))
                if r["departure_state"] == "LATEST_SAFE_DEPARTURE":
                    mo2, hm2 = r["latest_safe_departure_kst"].split(" ")
                    ld = datetime(2025, 3, int(mo2[3:]), int(hm2[:2]), int(hm2[3:5]), tzinfo=KST)
                    if ld <= x1:
                        ax.plot([t0, ld], [y, y], color="k", lw=0.6, alpha=0.5)
                        ax.plot(ld, y, marker="|", color="k", ms=10, mew=2)
                elif r["departure_state"] in ("INSIDE_KNOWN_FIRE_AREA", "NO_SAFE_DEPARTURE"):
                    ax.text(t0 + timedelta(minutes=30), y, "×", ha="center", va="center", fontsize=9)
            ax.text(x0 - timedelta(minutes=5), y, ARM_LABEL[st], ha="right", va="center", fontsize=8)
        for t, kind, txt in DOC.get(pid, []):
            m, c = KIND_STYLE[kind]
            ax.plot(t, n + 0.15, marker=m, color=c, ms=9 if kind == "fire" else 7)
            ax.axvline(t, color=c, lw=0.6, ls=":" if kind != "fire" else "-", alpha=0.8)
        for i, (t, kind, txt) in enumerate(sorted(DOC.get(pid, []))):
            ax.text(t + timedelta(minutes=2), n + 0.45 + 0.62 * (i % 4), txt, fontsize=7, color=KIND_STYLE[kind][1], ha="left",
                    va="bottom", bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.8))
        ax.set_ylim(-0.6, n + 3.1)
        ax.set_yticks([])
        ax.set_title(label, loc="left", fontsize=11, fontweight="bold")
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    import matplotlib.dates as mdates
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(tz=KST))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=KST))
    axes[-1].set_xlim(x0, x1)
    axes[-1].set_xlabel("2025-03-25 ~ 26 KST")
    handles = [plt.Rectangle((0, 0), 1, 1, color=STEP_COL[s]) for s in STEP_COL] + \
              [plt.Line2D([], [], marker="|", color="k", ls="", ms=10, mew=2)] + \
              [plt.Line2D([], [], marker=KIND_STYLE[x][0], color=KIND_STYLE[x][1], ls="") for x in ("alert", "road", "fire", "other")]
    labels = [STEP_KO[s] for s in STEP_COL] + [f"latest safe departure shown at that hour ({hz})", "documented alert/order",
                                                  "documented road closure", "documented fire at the place", "other documented event"]
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("What the screen would have shown, hour by hour (each block = one issue hour; row = R(h) arm:\n"
                 "3 stand-ins + MEASURED + MEASURED+GUST, the gust arm PROVISIONAL, ERA5 only), vs documented times (all single-source; SOURCES.md)",
                 fontsize=10)
    fig.tight_layout(rect=(0.03, 0.04, 1, 0.97))
    fig.savefig(out, dpi=130)
    plt.close(fig)


def roads(region):
    raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
    xy = {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}
    seen, segs = set(), []
    for e in raw["edges"]:
        key = tuple(sorted((e["u"], e["v"])))
        if key in seen:
            continue
        seen.add(key)
        segs.append((xy[e["u"]], xy[e["v"]]))
    return segs, xy


def frames(discs_path, R, out, standin="RUNNING", hz="8h"):
    discs = json.loads(Path(discs_path).read_text())["discs"]
    for d in discs:
        d["t"] = datetime.fromisoformat(d["t_utc"])
    places = {}
    for region in ("yeongdeok_2025", "uiseong_andong_2025"):
        for f in json.loads((ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]:
            places[f["properties"]["id"]] = f
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    segs = []
    for region in ("yeongdeok_2025", "uiseong_andong_2025"):
        segs += roads(region)[0]
    issues = sorted({key[3] for key in R})
    fdir = out / "frames"; fdir.mkdir(exist_ok=True)
    t = k(12, 0)
    i = 0
    names = dict(NAMED)
    ev_all = sorted({(tt, txt) for v in DOC.values() for tt, _, txt in v if not txt.startswith("18:58 국도34호선 통제")})
    while t <= k(0, 0, 26):
        T = max(x for x in issues if datetime.fromisoformat(x) <= t)
        fig, ax = plt.subplots(figsize=(16, 7.6))
        ax.add_collection(LineCollection(segs, colors="#9e9e9e", linewidths=0.25, alpha=0.6))
        cur = [d for d in discs if d["t"] < t]
        ahi = [Circle((d["x"], d["y"]), d["r_m"]) for d in cur if d["src"] == "AHI"]
        fir = [Circle((d["x"], d["y"]), d["r_m"]) for d in cur if d["src"] != "AHI"]
        ax.add_collection(PatchCollection(ahi, facecolor="#ff8a65", edgecolor="none", alpha=0.25))
        ax.add_collection(PatchCollection(fir, facecolor="#d84315", edgecolor="none", alpha=0.8))
        counts = {}
        for st in ("ORDINARY", "RUNNING", "WORST"):
            c = {"LEAVE_NOW": 0, "PREPARE_VULNERABLE_FIRST": 0, "NONE": 0}
            for region in ("yeongdeok_2025", "uiseong_andong_2025"):
                for r in R[(region, st, hz, T)]["rows"]:
                    c[r["step"]] += 1
            counts[st] = c
        for region in ("yeongdeok_2025", "uiseong_andong_2025"):
            for r in R[(region, standin, hz, T)]["rows"]:
                f = places[r["place_id"]]
                x, y = tr.transform(*f["geometry"]["coordinates"])
                vul = f["properties"].get("vulnerable")
                ax.scatter(x, y, s=55 if vul else 28, c=STEP_COL[r["step"]], marker="s" if vul else "o",
                           edgecolors="k", linewidths=0.5, zorder=5)
                if r["place_id"] in names:
                    t0 = datetime.fromisoformat(T).astimezone(KST)
                    if r["ld_s"] is None:
                        txt = "출발 가능 경로 없음" if r["dist_known_fire_m"] else "알려진 화재 구역 안"
                    elif r["cut_within_H"]:
                        txt = "출발 마감 " + (t0 + timedelta(seconds=r["ld_s"])).strftime("%H:%M") + " → " + (r.get("shelter_name") or "대피소")
                    else:
                        txt = "8시간 안에 경로 차단 없음"
                    ax.annotate(names[r["place_id"]].split(" ")[0] + "\n" + txt, (x, y), xytext=(8, 8), textcoords="offset points",
                                fontsize=8, zorder=6, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
        ax.set_xlim(1083000, 1180000); ax.set_ylim(1810000, 1852000); ax.set_aspect("equal"); ax.axis("off")
        Tk = datetime.fromisoformat(T).astimezone(KST)
        ax.set_title(f"{t.strftime('%m-%d %H:%M')} KST  ·  화면 기준 {Tk.strftime('%H:%M')} 발행  ·  R(h) = {standin}, horizon {hz}  ·  "
                     "what the screen would have shown (재현, 실제 상황 아님)", fontsize=11, loc="left")
        lines = [f"{st}: 즉시 {c['LEAVE_NOW']}  취약 먼저 {c['PREPARE_VULNERABLE_FIRST']}  없음 {c['NONE']}" for st, c in counts.items()]
        ax.text(0.005, 0.02, "174 places by step\n" + "\n".join(lines), transform=ax.transAxes, fontsize=9, va="bottom",
                bbox=dict(fc="white", ec="#bdbdbd"))
        evs = [txt for tt, txt in ev_all if tt <= t][-4:]
        ax.text(0.995, 0.02, "documented (single-source):\n" + ("\n".join(evs) if evs else "—"), transform=ax.transAxes,
                fontsize=9, ha="right", va="bottom", bbox=dict(fc="white", ec="#bdbdbd"))
        handles = [plt.Line2D([], [], marker="o", color=STEP_COL[s], ls="", mec="k") for s in STEP_COL] + \
                  [Circle((0, 0), 1, fc="#d84315"), Circle((0, 0), 1, fc="#ff8a65", alpha=0.4),
                   plt.Line2D([], [], marker="s", color="w", mec="k", ls="")]
        ax.legend(handles, [STEP_KO[s] for s in STEP_COL] + ["FIRMS detection (0.375/1 km)", "Himawari AHI hotspot (~2 km)",
                                                              "care facility (square)"], loc="upper left", fontsize=8)
        fig.savefig(fdir / f"frame_{i:03d}.png", dpi=100)
        plt.close(fig)
        i += 1
        t += timedelta(minutes=10)
    # 73 frames at 1 frame/s = 73 s
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1", "-i", str(fdir / "frame_%03d.png"),
                    "-vf", "scale=1600:-2,format=yuv420p", "-r", "10", "-c:v", "libx264", "-crf", "28",
                    str(out / "map_sequence.mp4")], check=True)
    return i


if __name__ == "__main__":
    discs, runs, out = sys.argv[1:4]
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    R = load_runs(runs)
    timeline(R, out)
    n = frames(discs, R, out)
    print("frames", n)
