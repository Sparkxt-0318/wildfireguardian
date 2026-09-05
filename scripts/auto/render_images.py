#!/usr/bin/env python
"""Render the images that go into the author's report email.

Five PNGs per lap, written to docs/auto/images/<stamp>/ and mirrored to
docs/auto/images/latest/, so an email can embed them by their GitHub raw URL
instead of hand-typed base64 (docs/auto/MEMO.md, 2026-09-03):

  01_full_map.png   the whole system as one map; areas touched by this lap glow
  02_changes.png    what changed this lap, by area (files, lines added/removed)
  03_backlog.png    the plan: rows done / in progress / to do / blocked, by priority
  04_rubric.png     the loop's rubric estimate, with history when the critic has scored
  05_timeline.png   the laps so far on the road to the freeze and the finals

Python 3.11 compatible; matplotlib (Agg) + networkx, both pinned. Labels are in
English because the sandbox has no Korean font; the board and reports keep the
Korean terms.

    python scripts/auto/render_images.py                # stamp = now
    python scripts/auto/render_images.py --stamp 2026-09-03T1300Z --out docs/auto/images
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
AUTO = REPO / "docs" / "auto"

INK, MUTED, LINE, PAPER = "#1B1F23", "#6F6A62", "#DDD8CE", "#F4F2EC"
ACCENT, DONE, PROG, BLOCK, TODO, QUIET = "#B4471B", "#2E7D4F", "#B7791F", "#B42318", "#3B4149", "#B8B3AA"

# The system as areas. Each area lists path prefixes; a file belongs to the first
# area whose prefix matches. Column = stage in the data flow (left to right).
AREAS = [
    ("data_io", "Data I/O", 0, ["src/wildfireguardian/data_io", "scripts/acquire_", "scripts/get_", "scripts/snapshot_", "scripts/merge_firms", "data/snapshots", "data/raw"]),
    ("detect", "Fire detection", 0, ["src/wildfireguardian/fire_detection", "src/wildfireguardian/detection", "scripts/gk2a", "scripts/run_live_detection"]),
    ("spread", "Spread model", 1, ["src/wildfireguardian/spread_v2", "src/wildfireguardian/spread_model", "scripts/spread_v2", "scripts/auc_", "scripts/oof_", "scripts/calibration", "scripts/ml_baselines", "scripts/arm_", "scripts/run_ablation", "scripts/measure_weather", "scripts/noise_envelope", "scripts/redundancy", "scripts/fold_sizes", "scripts/label_geometry", "scripts/crown", "scripts/diagnose"]),
    ("hazard", "Hazard field", 1, ["scripts/build_canonical_hazard", "scripts/run_forward_sim", "scripts/dilation", "scripts/mc_perturb", "scripts/run_routing_monte", "scripts/direction", "scripts/waf_"]),
    ("routing", "Routing", 2, ["src/wildfireguardian/routing", "scripts/run_real_roads", "scripts/run_yeongdeok", "scripts/run_multi_region", "scripts/run_routing", "scripts/run_village", "scripts/run_building", "scripts/run_budget", "scripts/run_canonical", "scripts/run_margin", "scripts/run_network_drift", "scripts/slope", "scripts/refuge", "scripts/derive_walk", "scripts/clearance", "scripts/osm_coverage", "scripts/measure_osm", "scripts/measure_building", "scripts/estimate_yeongdeok"]),
    ("rescue", "Rescue ingress", 2, ["scripts/run_rescue", "scripts/run_dispatch", "scripts/run_ordering", "scripts/verify_rescue", "scripts/analyse_cluster", "scripts/generate_dispatch", "scripts/vulnerability", "src/wildfireguardian/utils/vulnerability", "src/wildfireguardian/buildings"]),
    ("service", "Service & API", 3, ["src/wildfireguardian/service", "src/wildfireguardian/api", "src/wildfireguardian/live", "scripts/run_api", "scripts/run_manual_trigger", "scripts/operator_output"]),
    ("delivery", "Delivery", 3, ["src/wildfireguardian/delivery", "scripts/send_dispatch", "scripts/generate_alert", "outputs/"]),
    ("screens", "Screens & demo", 4, ["web/", "scripts/build_finals", "scripts/build_console", "scripts/build_operator", "scripts/build_field", "scripts/build_refuge", "scripts/build_demo", "scripts/export_demo", "scripts/finals.template", "scripts/console.template", "scripts/check_screen", "scripts/measure_fonts", "scripts/render_divergence", "scripts/make_", "demo/"]),
    ("evidence", "Evidence & gates", 4, ["docs/NUMBERS.json", "scripts/build_numbers", "scripts/verify_numbers", "scripts/check_", "scripts/freeze_baseline", "scripts/env_check", "scripts/build_artifact", "scripts/platform_drift", "Makefile", "data/processed", "docs/artifact_manifest", "docs/baseline_"]),
    ("loop", "Loop & reports", 5, ["docs/auto/", "scripts/auto/", ".github/", ".claude/", "CLAUDE.md"]),
    ("docs", "Documents", 5, ["docs/", "README.md", "requirements.txt", "pyproject.toml"]),
    ("tests", "Tests", 5, ["tests/"]),
]
STAGE_NAMES = ["inputs", "forecast", "decision", "operation", "presentation", "records"]


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout


def area_of(path: str) -> str:
    for aid, _, _, prefixes in AREAS:
        for p in prefixes:
            if path.startswith(p):
                return aid
    return "docs" if path.endswith(".md") else "evidence"


def module_area(mod: str) -> str | None:
    if not mod.startswith("wildfireguardian"):
        return None
    parts = mod.split(".")
    if len(parts) < 2:
        return None
    return area_of("src/" + "/".join(parts[:2]))


def import_edges() -> Counter:
    """Edges between areas from `import`/`from` statements in src/ and scripts/."""
    edges: Counter = Counter()
    files = [l for l in git("ls-files", "src", "scripts").splitlines() if l.endswith(".py")]
    for f in files:
        src_area = area_of(f)
        try:
            tree = ast.parse((REPO / f).read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for nme in names:
                dst = module_area(nme)
                if dst and dst != src_area:
                    edges[(src_area, dst)] += 1
    return edges


def changed_files(since: str | None) -> list[str]:
    rng = f"{since}..HEAD" if since and subprocess.run(["git", "cat-file", "-e", since], cwd=REPO).returncode == 0 else "HEAD~1..HEAD"
    return [l for l in git("diff", "--name-only", rng).splitlines() if l]


def numstat(since: str | None) -> dict:
    rng = f"{since}..HEAD" if since and subprocess.run(["git", "cat-file", "-e", since], cwd=REPO).returncode == 0 else "HEAD~1..HEAD"
    out = defaultdict(lambda: [0, 0, 0])
    for line in git("diff", "--numstat", rng).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add, rem, path = parts
        a = area_of(path)
        out[a][0] += 1
        out[a][1] += int(add) if add.isdigit() else 0
        out[a][2] += int(rem) if rem.isdigit() else 0
    return dict(out)


def parse_backlog() -> list[dict]:
    rows = []
    for line in (AUTO / "BACKLOG.md").read_text().splitlines():
        m = re.match(r"^\|\s*(WFG-\d+)\s*\|\s*(P\d)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*([^|]*?)\s*\|", line)
        if m:
            st = m.group(5).strip()
            kind = "done" if st.startswith("done") else "progress" if st.startswith("in-progress") else "blocked" if st.startswith("blocked") else "parked" if st.startswith("parked") else "todo"
            rows.append(dict(id=m.group(1), p=m.group(2), kind=kind))
    return rows


def parse_scorecard() -> list[tuple[str, list[float]]]:
    p = AUTO / "SCORECARD.md"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 6 and re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
            try:
                out.append((cells[0], [float(c) for c in cells[1:6]]))
            except ValueError:
                pass
    return out


def lap_reports() -> list[dict]:
    reps = []
    for f in sorted((AUTO / "reports").glob("*.md")):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})Z-(\w+)\.md", f.name)
        if not m:
            continue
        t = f.read_text()
        reps.append(dict(when=dt.datetime(*map(int, m.groups()[:5]), tzinfo=dt.timezone.utc), kind=m.group(6),
                         gates="green" if "**ALL GREEN**" in t else "red" if "**RED**" in t else "none"))
    return reps


def style(ax):
    ax.set_facecolor(PAPER)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)


# ---------------------------------------------------------------------------
def draw_full_map(out: Path, changed: list[str], stamp: str):
    G = nx.DiGraph()
    for aid, name, col, _ in AREAS:
        G.add_node(aid, label=name, col=col)
    for (a, b), w in import_edges().items():
        G.add_edge(a, b, w=w)
    touched = Counter(area_of(f) for f in changed)
    # layered layout: x by stage column, y spread within column
    cols = defaultdict(list)
    for aid, _, col, _ in AREAS:
        cols[col].append(aid)
    pos = {}
    for col, ids in cols.items():
        n = len(ids)
        for i, aid in enumerate(ids):
            pos[aid] = (col * 2.2, (n - 1) / 2 - i)
    fig, ax = plt.subplots(figsize=(14, 7.2), dpi=110)
    fig.patch.set_facecolor(PAPER)
    style(ax)
    ax.set_xticks([]); ax.set_yticks([])
    for (a, b, d) in G.edges(data=True):
        xa, ya = pos[a]; xb, yb = pos[b]
        ax.annotate("", xy=(xb - 0.6, yb), xytext=(xa + 0.6, ya),
                    arrowprops=dict(arrowstyle="-|>", color=LINE if not (touched.get(a) or touched.get(b)) else "#D9B7A5",
                                    lw=0.8 + min(d["w"], 12) / 6, shrinkA=0, shrinkB=0, connectionstyle="arc3,rad=0.08"))
    for aid, data in G.nodes(data=True):
        x, y = pos[aid]
        hot = touched.get(aid, 0)
        face = ACCENT if hot else "#FFFFFF"
        edge = ACCENT if hot else LINE
        ax.add_patch(plt.Rectangle((x - 0.62, y - 0.3), 1.24, 0.6, facecolor=face, edgecolor=edge, lw=1.4, zorder=3, joinstyle="round"))
        ax.text(x, y + 0.04, data["label"], ha="center", va="center", fontsize=9.5, color="#FFFFFF" if hot else INK, weight="bold", zorder=4)
        if hot:
            ax.text(x, y - 0.17, f"{hot} file{'s' if hot != 1 else ''} changed", ha="center", va="center", fontsize=8, color="#FFFFFF", zorder=4)
    for col, name in enumerate(STAGE_NAMES):
        ax.text(col * 2.2, 2.55, name.upper(), ha="center", va="bottom", fontsize=9, color=MUTED, letterspacing=1) if False else ax.text(col * 2.2, 2.55, name.upper(), ha="center", va="bottom", fontsize=9, color=MUTED)
    ax.set_xlim(-1.1, 5 * 2.2 + 1.1); ax.set_ylim(-2.4, 3.0)
    ax.set_title("WildfireGuardian: the whole system, and where this lap worked", loc="left", fontsize=14, color=INK, pad=14)
    ax.text(-1.05, -2.25, f"Lap {stamp}. Arrows are import dependencies between areas (thicker = more). Highlighted boxes are the areas whose files this lap changed; everything else is untouched.",
            fontsize=8.5, color=MUTED, va="bottom")
    fig.tight_layout(); fig.savefig(out / "01_full_map.png", facecolor=PAPER); plt.close(fig)


def draw_changes(out: Path, stats: dict, changed: list[str], stamp: str):
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=110)
    fig.patch.set_facecolor(PAPER); style(ax)
    names = {aid: name for aid, name, _, _ in AREAS}
    items = sorted(stats.items(), key=lambda kv: -(kv[1][1] + kv[1][2]))
    if not items:
        ax.text(0.5, 0.5, "No files changed in this lap.", ha="center", va="center", fontsize=13, color=MUTED, transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
    else:
        labels = [f"{names.get(a, a)}  ({v[0]} file{'s' if v[0] != 1 else ''})" for a, v in items]
        y = range(len(items))
        ax.barh(y, [v[1] for _, v in items], color=DONE, label="lines added")
        ax.barh(y, [-v[2] for _, v in items], color=BLOCK, label="lines removed")
        ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=10, color=INK)
        ax.invert_yaxis(); ax.axvline(0, color=LINE, lw=1)
        ax.legend(frameon=False, loc="lower right", fontsize=9)
        ax.xaxis.grid(True, color=LINE, lw=0.6); ax.set_axisbelow(True)
    ax.set_title(f"What changed in lap {stamp}: {len(changed)} file{'s' if len(changed) != 1 else ''} across {len(stats)} area{'s' if len(stats) != 1 else ''}", loc="left", fontsize=13, color=INK, pad=12)
    fig.tight_layout(); fig.savefig(out / "02_changes.png", facecolor=PAPER); plt.close(fig)


def draw_backlog(out: Path, rows: list[dict]):
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=110)
    fig.patch.set_facecolor(PAPER); style(ax)
    order = ["done", "progress", "todo", "blocked", "parked"]
    colors = dict(done=DONE, progress=PROG, todo=TODO, blocked=BLOCK, parked=QUIET)
    labels = dict(done="done", progress="in progress", todo="to do", blocked="blocked (needs you or data)", parked="parked")
    ps = ["P0", "P1", "P2", "P3"]
    left = [0] * 4
    for k in order:
        vals = [sum(1 for r in rows if r["p"] == p and r["kind"] == k) for p in ps]
        ax.barh(range(4), vals, left=left, color=colors[k], label=labels[k], height=0.55)
        for i, v in enumerate(vals):
            if v:
                ax.text(left[i] + v / 2, i, str(v), ha="center", va="center", fontsize=9, color="#FFFFFF", weight="bold")
        left = [l + v for l, v in zip(left, vals)]
    ax.set_yticks(range(4)); ax.set_yticklabels(["P0 · before the freeze", "P1 · before the finals", "P2 · after (ISEF)", "P3 · IEEE paper"], fontsize=10, color=INK)
    ax.invert_yaxis(); ax.legend(frameon=False, ncol=5, loc="lower center", bbox_to_anchor=(0.5, -0.32), fontsize=9)
    ax.xaxis.grid(True, color=LINE, lw=0.6); ax.set_axisbelow(True)
    done = sum(1 for r in rows if r["kind"] == "done")
    ax.set_title(f"The plan: {done} of {len(rows)} rows done", loc="left", fontsize=13, color=INK, pad=12)
    fig.tight_layout(); fig.savefig(out / "03_backlog.png", facecolor=PAPER); plt.close(fig)


def draw_rubric(out: Path):
    hist = parse_scorecard()
    rows_en = ["Research aim", "Design & method", "Data, analysis, interpretation", "Creativity", "Submitted materials"]
    base = [17, 14, 14, 16, 15]
    latest = hist[-1][1] if hist else base
    src = f"critic lap, {hist[-1][0]}" if hist else "research-sweep estimate, 2026-09-03 (the critic re-scores daily)"
    fig, ax = plt.subplots(figsize=(11, 4.4), dpi=110)
    fig.patch.set_facecolor(PAPER); style(ax)
    y = range(len(rows_en))
    ax.barh(y, [20] * 5, color=LINE, height=0.5)
    ax.barh(y, latest, color=ACCENT, height=0.5)
    if len(hist) >= 2:
        prev = hist[-2][1]
        for i, (a, b) in enumerate(zip(prev, latest)):
            if a != b:
                ax.annotate("", xy=(b, i), xytext=(a, i), arrowprops=dict(arrowstyle="->", color=INK, lw=1))
    for i, v in enumerate(latest):
        ax.text(20.3, i, f"{v:g} / 20", va="center", fontsize=10, color=MUTED)
    ax.set_yticks(list(y)); ax.set_yticklabels(rows_en, fontsize=10, color=INK); ax.invert_yaxis()
    ax.set_xlim(0, 23); ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_title(f"Rubric estimate (Track B, SW research): {sum(latest):g} / 100", loc="left", fontsize=13, color=INK, pad=12)
    ax.text(0, -0.95, f"Source: {src}. Estimates by the loop, not a judge's score.", fontsize=8.5, color=MUTED)
    fig.tight_layout(); fig.savefig(out / "04_rubric.png", facecolor=PAPER); plt.close(fig)


def draw_timeline(out: Path, state: dict):
    reps = lap_reports()
    start = dt.datetime(2026, 9, 3, tzinfo=dt.timezone.utc)
    finals = dt.datetime.fromisoformat(state.get("finals_date", "2026-10-18")).replace(tzinfo=dt.timezone.utc)
    freeze = dt.datetime.fromisoformat(state.get("freeze_date", "2026-10-10")).replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    fig, ax = plt.subplots(figsize=(12, 2.9), dpi=110)
    fig.patch.set_facecolor(PAPER); style(ax)
    ax.hlines(0, start, finals, color=LINE, lw=6)
    ax.hlines(0, start, now, color=INK, lw=6)
    for r in reps:
        ax.plot([r["when"]], [0], marker="o", ms=7, color={"green": DONE, "red": BLOCK, "none": QUIET}[r["gates"]], zorder=3)
    for x, label in ((freeze, "freeze"), (finals, "finals")):
        ax.axvline(x, color=ACCENT, lw=1, ls="--"); ax.text(x, 0.55, label, ha="center", fontsize=9, color=ACCENT)
    ax.text(now, -0.6, "today", ha="center", fontsize=9, color=INK)
    ax.set_yticks([]); ax.set_ylim(-1, 1)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d"))
    kinds = Counter(r["kind"] for r in reps)
    ax.set_title(f"{len(reps)} laps so far ({', '.join(f'{v} {k}' for k, v in kinds.items()) or 'none'}); {(finals - now).days} days to the finals", loc="left", fontsize=12, color=INK, pad=10)
    ax.text(start, -0.9, "Each dot is one lap: green = every gate passed, red = parked on auto/red.", fontsize=8.5, color=MUTED, va="bottom")
    fig.tight_layout(); fig.savefig(out / "05_timeline.png", facecolor=PAPER); plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%MZ"))
    ap.add_argument("--out", default=str(AUTO / "images"))
    ap.add_argument("--since", default=None, help="commit the lap started from; default = STATE.json last_report_commit")
    a = ap.parse_args()
    state = {}
    try:
        state = json.loads((AUTO / "STATE.json").read_text())
    except Exception:
        pass
    since = a.since or state.get("last_report_commit")
    out = Path(a.out) / a.stamp
    out.mkdir(parents=True, exist_ok=True)
    changed = changed_files(since)
    draw_full_map(out, changed, a.stamp)
    draw_changes(out, numstat(since), changed, a.stamp)
    draw_backlog(out, parse_backlog())
    draw_rubric(out)
    draw_timeline(out, state)
    latest = Path(a.out) / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        shutil.copy2(f, latest / f.name)
    print(f"[images] wrote {len(list(out.glob('*.png')))} images to {out} (and latest/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
