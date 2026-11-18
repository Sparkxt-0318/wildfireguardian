"""Figures for kcf-adaptive, drawn from derived/*.json only.

    python figures.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
D, OUT = HERE / "derived", HERE / "fig"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
C = dict(blue="#2a78d6", orange="#eb6834", aqua="#1baf7a", yellow="#eda100", violet="#6250d6")
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.titlesize": 10,
                     "axes.titleweight": "bold", "axes.titlelocation": "left"})


def fig_arm1():
    f = D / "arm1.json"
    if not f.exists():
        return
    d = json.load(open(f))
    out = json.load(open(D / "arm1_output.json"))["us2024"]["all_windows"]
    r = d["all_windows"]
    rows = [("c651, not adapted", r["models"]["unadapted_rebuilt"], MUTED)]
    names = dict(P4_real=("adapted: 4 parameters (primary)", C["blue"]), **{"P+_real": ("adapted: 168 parameters", C["orange"])},
                 **{"P4_pen1e-3": ("4 parameters, penalty 0.001 (sensitivity)", C["aqua"]),
                    "P4_pen1e-4": ("4 parameters, penalty 0.0001 (sensitivity)", C["yellow"])})
    for k, (lab, col) in names.items():
        if k in r["models"]:
            rows.append((lab, r["models"][k], col))
    rows.append(("output rescaled by one number (not weights)", out["models"]["adapted_output_level"], C["violet"]))
    rows.append(("persistence (no new burning)", r["models"]["persistence"], INK))
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), sharey=True)
    specs = [("Brier score (lower is better)", lambda m: m["brier"], "{:.4f}"),
             ("Area flagged per burned cell (expected)", lambda m: m["flagging"]["expected_area_per_burned_cell"], "{:.2f}"),
             ("Burned cells missed (expected share)", lambda m: m["flagging"]["expected_miss_rate"], "{:.3f}")]
    y = range(len(rows))[::-1]
    for ax, (title, get, fmt) in zip(axes, specs):
        vals = [get(m) for _, m, _ in rows]
        ax.barh(list(y), vals, height=0.55, color=[c for *_, c in rows])
        for yy, v in zip(y, vals):
            ax.text(v, yy, " " + fmt.format(v), va="center", ha="left", color=INK, fontsize=8)
        ax.set_title(title)
        ax.set_xlim(0, max(vals) * 1.22)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(list(y))
    axes[0].set_yticklabels([lab for lab, *_ in rows])
    fig.suptitle(f"Arm 1: six held-out US fires, 273 windows, {r['entries']:,} cell-windows, {r['positives']:,} burned",
                 x=0.01, ha="left", fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT / "fig1_arm1_scores.png", dpi=200)
    plt.close(fig)


def fig_arm2():
    d = json.load(open(D / "arm2.json"))
    arms = [("FIXED-CIRC", "None", "fixed circle (baseline)", C["blue"], "o"),
            ("FIXED-DIR", "None", "fixed wind-aligned", C["orange"], "s"),
            ("ADAPT-CIRC", "0.005", "adaptive circle", C["aqua"], "^"),
            ("ADAPT-DIR", "0.005", "adaptive wind-aligned", C["yellow"], "D")]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for ax, h in zip(axes, ("5", "8")):
        for arm, par, lab, col, mk in arms:
            pts = []
            for al in d["meta"]["alphas"]:
                ag = d["lofo"][h].get(f"{arm}|{al}|{par}", {})
                if "miss_fire_weighted" in ag:
                    pts.append((100 * ag["miss_fire_weighted"], ag["op_fire_weighted"], al))
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=2, marker=mk, ms=5, label=lab,
                    markeredgecolor=SURFACE, markeredgewidth=1)
            for x, yv, al in pts:
                if al == 0.10:
                    ax.plot([x], [yv], marker=mk, ms=10, color=col, markeredgecolor=INK, markeredgewidth=1.2)
        b = d["lofo"][h]["FIXED-CIRC|0.1|None"]
        a = d["lofo"][h]["ADAPT-CIRC|0.1|0.005"]
        ax.annotate("fixed circle, 10% target", (100 * b["miss_fire_weighted"], b["op_fire_weighted"]),
                    xytext=(8, 10), textcoords="offset points", fontsize=8, color=INK)
        ax.annotate("adaptive, 10% target", (100 * a["miss_fire_weighted"], a["op_fire_weighted"]),
                    xytext=(8, 8), textcoords="offset points", fontsize=8, color=INK)
        ax.set_title(f"{h} h ahead")
        ax.set_xlabel("issue hours missed, % (leave-one-fire-out, fire-weighted)")
        ax.set_xlim(0, 31)
        ax.set_ylim(0, None)
    axes[0].set_ylabel("area flagged per cell actually burned")
    axes[1].legend(frameon=False, loc="upper right")
    fig.suptitle("Arm 2: 28 California fires. Each line runs over miss targets 2-30%; outlined marker = 10% target. "
                 "Lower left is better.", x=0.01, ha="left", fontsize=9.5, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT / "fig2_arm2_frontier.png", dpi=200)
    plt.close(fig)

    # 25 March 2025, 5 h
    m = d["march25"]["5"]["hours"]
    hrs = [r["kst_hour"] for r in m if r["complete"]]
    fig, ax = plt.subplots(figsize=(10.5, 4.4))
    ax.plot(hrs, [r["reach_km"] for r in m if r["complete"]], color=INK, lw=2.5, label="what the fire did: reach in the next 5 h")
    series = [("FIXED-CIRC|0.1|None", "fixed circle (3.75 km)", C["blue"]),
              ("ADAPT-CIRC|0.1|0.005", "adaptive circle, frozen step 0.005", C["aqua"]),
              ("ADAPT-CIRC|0.1|0.05", "adaptive circle, step 0.05 (sensitivity)", C["orange"]),
              ("TRACK-CIRC|0.1|0.2", "unbounded tracker, 0.2 (secondary)", C["violet"])]
    for key, lab, col in series:
        q = [r[key]["q_km"] for r in m if r["complete"]]
        ax.plot(hrs, q, color=col, lw=2, label=lab)
        miss = [(r["kst_hour"], r[key]["q_km"]) for r in m if r["complete"] and r[key]["missed"]]
        ax.plot([x for x, _ in miss], [y for _, y in miss], ls="none", marker="x", ms=6, color=col, mew=1.6)
    ax.axvspan(9.5, 20.5, color=GRID, alpha=0.6, lw=0)
    ax.text(15, 43.5, "fixed margin missed every hour 10-20 KST", ha="center", fontsize=8, color=MUTED)
    ax.set_xlabel("issue hour, 25 March 2025 (KST); x = margin missed at that hour")
    ax.set_ylabel("km beyond the known burned area")
    ax.set_xticks(range(0, 23, 2))
    ax.set_ylim(0, 46)
    ax.set_title("25 March 2025, Gyeongbuk: margins that learn from their own misses grow only after the run has started")
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_march25.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig_arm1()
    fig_arm2()
    print(sorted(p.name for p in OUT.glob("*.png")))
