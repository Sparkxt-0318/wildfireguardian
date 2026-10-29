"""Summaries, RESULTS.json, CSV tables and figures for campaigns C1 to C4 from the Contract E records in data/.

  python research/synthetic-truth/analyze.py [--data research/synthetic-truth/data] [--tag TAG]
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import figures as FG  # noqa: E402
from wfg_members import kit  # noqa: E402

C = FG.OKABE_ITO


def load(data, name, tag):
    p = Path(data) / ("%s%s.jsonl.gz" % (name, ("_" + tag) if tag else ""))
    if not p.exists():
        return []
    with gzip.open(p, "rt") as f:
        return [json.loads(l) for l in f]


def summarise(rows, key):
    groups = collections.OrderedDict()
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    out = []
    for k, rs in groups.items():
        n = len(rs)
        verdict = collections.Counter(r["verdict"] for r in rs)
        fs = sum(1 for r in rs if r["false_safe"])
        clair = [r for r in rs if r["clairvoyant_status"] == "ROUTE"]
        fr = sum(1 for r in clair if r["false_refusal"])
        fr_nr = sum(1 for r in clair if r["false_refusal"] and r["verdict"] == "model_no_route")
        fr_un = sum(1 for r in clair if r["false_refusal"] and r["verdict"] == "unresolved")
        unscorable = sum(1 for r in rs if r["verdict"] != "checked_route" and r["false_refusal"] is None)
        regrets = [r["regret_s"] for r in rs if r["regret_s"] is not None and not r["false_safe"]]
        briers = [r["brier"] for r in rs if r.get("brier") is not None]
        lo, hi = FG.wilson(fs, n)
        flo, fhi = FG.wilson(fr, len(clair))
        decisions = {(r["cutoff"], r["mission"]) for r in rs}
        out.append({"group": k, "cases": n, "decisions": len(decisions), "checked_route": verdict.get("checked_route", 0),
                    "model_no_route": verdict.get("model_no_route", 0), "unresolved": verdict.get("unresolved", 0),
                    "false_safe": fs, "false_safe_rate": fs / n if n else None, "false_safe_wilson95": [lo, hi],
                    "cases_with_clairvoyant_route": len(clair), "false_refusal": fr,
                    "false_refusal_rate": fr / len(clair) if clair else None, "false_refusal_wilson95": [flo, fhi],
                    "false_refusal_by_no_route": fr_nr, "false_refusal_by_unresolved": fr_un, "false_refusal_unscorable": unscorable,
                    "regret_s_median": statistics.median(regrets) if regrets else None,
                    "regret_s_mean": statistics.fmean(regrets) if regrets else None,
                    "regret_s_max": max(regrets) if regrets else None,
                    "brier_mean": statistics.fmean(briers) if briers else None,
                    "false_safe_by_parent_fire": dict(collections.Counter(r["parent_fire"] for r in rs if r["false_safe"])),
                    "cases_by_parent_fire": dict(collections.Counter(r["parent_fire"] for r in rs))})
    return out


def write_csv(path, rows):
    if not rows:
        return
    keys = list(rows[0])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict, tuple)) else v) for k, v in r.items()})


def bars_with_ci(ax, labels, rates, cis, color, offset=0.0, width=0.38, label=None):
    x = np.arange(len(labels)) + offset
    err = np.array([[r - lo, hi - r] for r, (lo, hi) in zip(rates, cis)]).T
    ax.bar(x, rates, width, color=color, label=label, yerr=err, capsize=2, error_kw={"lw": 0.7})
    return x


def fig_c1(s1, out):
    FG.setup()
    fig, ax = FG.plt.subplots(figsize=(FG.DOUBLE, 2.6))
    labels = [g["group"][0] for g in s1]
    x = bars_with_ci(ax, labels, [g["false_safe_rate"] for g in s1], [g["false_safe_wilson95"] for g in s1], C["vermillion"], -0.2,
                     label="false-safe (all cases)")
    bars_with_ci(ax, labels, [g["false_refusal_rate"] or 0 for g in s1], [g["false_refusal_wilson95"] for g in s1], C["blue"], 0.2,
                 label="false-refusal (cases with a clairvoyant route)")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel("rate (fraction of cases)")
    ax.set_xlabel("forecast members (v1 independent draws, v2 trajectories; K members)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    return FG.save(fig, out, "fig01_false_safe_false_refusal_by_members")


def fig_c2(s2, out):
    FG.setup()
    fig, ax = FG.plt.subplots(figsize=(FG.SINGLE + 1.2, 2.8))
    for g in s2:
        b = g["brier_mean"]
        if b is None:
            continue
        ax.scatter(b, g["false_safe_rate"], color=C["vermillion"], marker="o", s=16)
        ax.scatter(b, g["false_refusal_rate"] or 0, color=C["blue"], marker="s", s=16)
        ax.annotate(g["group"][0], (b, max(g["false_safe_rate"], g["false_refusal_rate"] or 0)), fontsize=6,
                    xytext=(2, 3), textcoords="offset points")
    ax.scatter([], [], color=C["vermillion"], marker="o", s=16, label="false-safe rate")
    ax.scatter([], [], color=C["blue"], marker="s", s=16, label="false-refusal rate")
    ax.set_xlabel("forecast quality: mean Brier score of the members against the truth (lower is better)")
    ax.set_ylabel("rate (fraction of cases)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    return FG.save(fig, out, "fig02_decision_vs_forecast_quality")


def fig_c3(s3, out):
    FG.setup()
    fig, ax = FG.plt.subplots(figsize=(FG.SINGLE + 1.2, 2.8))
    markers = {1.0: "o", 0.9: "s", 0.75: "^"}
    colours = {4: C["blue"], 8: C["orange"], 16: C["green"], 32: C["vermillion"]}
    for g in s3:
        label, rule, k, f = g["group"]
        K = int(label.split("K")[1])
        ax.scatter(g["false_refusal_rate"] or 0, g["false_safe_rate"], color=colours[K], marker=markers[f], s=18)
    for K, col in colours.items():
        ax.scatter([], [], color=col, marker="o", s=16, label="K = %d" % K)
    for f, mk in markers.items():
        ax.scatter([], [], color=C["grey"], marker=mk, s=16, label="k/m = %s" % ("all" if f == 1.0 else f))
    ax.set_xlabel("false-refusal rate (cases with a clairvoyant route)")
    ax.set_ylabel("false-safe rate (all cases)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    return FG.save(fig, out, "fig03_acceptance_tradeoff")


def fig_map(c4_journeys, region, cutoff, mission, toa_dir, out, name, title_note):
    """Executed journeys of the forecast sources over the reconstructed arrival isochrones (hours after the cutoff)."""
    sys.path.insert(0, str(REPO / "experimental" / "synthetic-truth" / "src"))
    from wfg_osse import toa as TOA
    p = kit.paths(region, cutoff)
    graph = json.loads(p["graph"].read_text())
    md = json.loads((p["packet"] / "NATIVE_METADATA.json").read_text())
    reg = md.get("regional") or {}
    event = reg.get("event_id")
    events = {e["id"]: e for e in json.loads((REPO / "forecast/data/environment/events.json").read_text())}
    arr, transform, _ = TOA.read(Path(toa_dir) / ("%s_pswt_ok_toa.tif" % event))
    from datetime import datetime
    t0 = datetime.fromisoformat(events[event]["t0_utc"])
    cut = datetime.fromisoformat(kit.cutoff_iso(cutoff).replace("Z", "+00:00"))
    c_h = (cut - t0).total_seconds() / 3600.0
    rel = arr - c_h
    a, _, x0, _, e, y0 = transform
    H, W = rel.shape
    extent = (x0, x0 + W * a, y0 + H * e, y0)
    FG.setup()
    fig, ax = FG.plt.subplots(figsize=(FG.DOUBLE, 5.0))
    show = np.where(np.isfinite(rel) & (rel > -6) & (rel <= 6), rel, np.nan)
    im = ax.imshow(show, extent=extent, origin="upper", cmap="cividis", vmin=-6, vmax=6, interpolation="nearest")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("reconstructed arrival relative to the cutoff (h); 0 to 1 h is the scored hour")
    nodes = {n["id"]: (float(n["x"]), float(n["y"])) for n in graph["nodes"]}
    edges = {ed["id"]: ed for ed in graph["edges"]}
    xs, ys = [], []
    for ed in graph["edges"][::1]:
        (ux, uy), (vx, vy) = nodes[ed["u"]], nodes[ed["v"]]
        xs += [ux, vx, None]
        ys += [uy, vy, None]
    ax.plot(xs, ys, color=C["grey"], lw=0.15, alpha=0.6)
    styles = {"v1_K4": (C["orange"], "-"), "v2_K16": (C["sky"], "--"), "current_state_only": (C["vermillion"], ":"),
              "persistence": (C["purple"], "-.")}
    bbox = [np.inf, np.inf, -np.inf, -np.inf]
    for j in c4_journeys:
        if (j["region"], j["cutoff"], j["mission"]) != (region, cutoff, mission) or j["verdict"] != "checked_route":
            continue
        pts = []
        for leg in j["legs"]:
            if leg["kind"] == "EDGE":
                ed = edges[leg["edge"]]
                pts += [nodes[ed["u"]], nodes[ed["v"]]]
        if not pts:
            continue
        P = np.array(pts)
        col, ls = styles.get(j["forecast_source"], (C["black"], "-"))
        ax.plot(P[:, 0], P[:, 1], color=col, ls=ls, lw=1.4, label="%s (arrival %s s)" % (j["forecast_source"], j["arrival_s"]))
        bbox = [min(bbox[0], P[:, 0].min()), min(bbox[1], P[:, 1].min()), max(bbox[2], P[:, 0].max()), max(bbox[3], P[:, 1].max())]
    if np.isfinite(bbox[0]):
        pad = 1500
        ax.set_xlim(bbox[0] - pad, bbox[2] + pad)
        ax.set_ylim(bbox[1] - pad, bbox[3] + pad)
    ax.set_xlabel("easting, EPSG:5179 (m)")
    ax.set_ylabel("northing, EPSG:5179 (m)")
    ax.set_aspect("equal")
    ax.legend(loc="upper left", bbox_to_anchor=(1.12, 1.0), frameon=False, title=title_note)
    return FG.save(fig, out, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--toa-dir", default="/home/user/wfg-data-1c/zenodo_21788344/extracted/rasters_kr")
    ap.add_argument("--figures", default=str(HERE / "figures"))
    a = ap.parse_args()
    rows = {c: load(a.data, c, a.tag) for c in ("C1", "C2", "C3", "C4")}
    res = {}
    s1 = summarise(rows["C1"], lambda r: (r["forecast_source"],))
    s2 = summarise(rows["C2"], lambda r: (r["forecast_source"],))
    s3 = summarise(rows["C3"], lambda r: (r["forecast_source"], r["rule"], r["k"], r["k_over_m_target"]))
    s4 = summarise(rows["C4"], lambda r: (r["forecast_source"],))
    s4_rows = [{k: r[k] for k in ("region", "cutoff", "mission", "forecast_source", "verdict", "arrival_s", "clairvoyant_arrival_s",
                                  "true_contact", "false_safe", "false_refusal", "regret_s", "truth_new_ignitions")} for r in rows["C4"]]
    s1_fire = summarise(rows["C1"], lambda r: (r["forecast_source"], r["parent_fire"]))
    res = {"C1": s1, "C1_by_parent_fire": s1_fire, "C2": s2, "C3": s3, "C4": s4, "C4_rows": s4_rows,
           "record_counts": {c: len(v) for c, v in rows.items()}}
    (HERE / "RESULTS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    for name, s in (("C1_summary.csv", s1), ("C2_summary.csv", s2), ("C3_summary.csv", s3), ("C4_summary.csv", s4), ("C4_cases.csv", s4_rows)):
        write_csv(HERE / name, s)
    if s1:
        fig_c1(s1, a.figures)
    if s2:
        fig_c2(s2, a.figures)
    if s3:
        fig_c3(s3, a.figures)
    jp = Path(a.data) / ("C4_journeys%s.json" % (("_" + a.tag) if a.tag else ""))
    if jp.exists():
        js = json.loads(jp.read_text())
        fig_map(js, "uiseong_andong_2025", "20250325T170000Z", "FW1", a.toa_dir, a.figures, "fig04_retrospective_uiseong_map",
                "Uiseong-Andong 2025, cutoff 2025-03-25 17:00 UTC, mission FW1")
        fig_map(js, "yeongdeok_2025", "20250325T190000Z", "FX2", a.toa_dir, a.figures, "fig05_retrospective_yeongdeok_map",
                "Yeongdeok 2025 (Caldor inputs unavailable), cutoff 2025-03-25 19:00 UTC, mission FX2")
    print(json.dumps({k: [(g["group"], g["cases"], g["false_safe"], g["false_refusal"], g["cases_with_clairvoyant_route"]) for g in v]
                      for k, v in res.items() if k in ("C1", "C2", "C4")}, default=str, indent=0))


if __name__ == "__main__":
    main()
