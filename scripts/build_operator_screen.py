#!/usr/bin/env python
"""Build the single-file operator screen for the live demonstration.

Round-3 PHASE 8.

WHAT IT IS
----------
One self-contained HTML file that opens from ``file://`` with **no network of
any kind**. It replays a PHASE-6 run: the hazard surface advances through its
five slices, hotspots appear at the moment they were detected, the trigger fires,
and the dispatch list fills from the top.

WHAT IT IS NOT
--------------
* **Not a live client.** There is no polling, no fetch, no XHR, no WebSocket.
* **Not a map client.** No tiles, no basemap, no CDN. Coordinates are projected
  here, at build time, and drawn as SVG.
* **Not a calculator.** Every number on screen was computed by
  ``run_live_detection.py`` and is inlined. The page replays; it does not solve.
* **No localStorage**, no cookies, no service worker.

Those are not stylistic preferences. The venue's network will be unreliable or
absent, and a screen that degrades when the wifi drops is a screen that fails in
front of judges.

WHERE THE DATA COMES FROM
-------------------------
    viz.json          geometry: origins by outcome, two routes, refuges,
                      hotspots, the field's grid and slice times
    MANIFEST.json     villages and their points (coordinate-free)
    RUN.json          scope, timings, applicability, counts
    the region's hazard npz   the surface itself, quantised here into five
                      bands and run-length encoded. Yeongdeok reads
                      routing_demo_canonical.npz; the other regions read their
                      own hazard_{region}.npz. The name is carried onto the
                      status bar, never assumed.

TWO SCREENS ARE BUILT, AND THEY DO DIFFERENT JOBS
-------------------------------------------------
    의성·안동 2025   the demonstration. Coverage 99.2 %, 91 future-aware-only
                    origins, no responder side (no fire station is mapped in
                    OSM inside its walk bbox).
    영덕 2025        the limitation. Coverage 32.6 %, and the dashed walk-bbox
                    outline sits over a fire that runs 45 km west of it, so the
                    caveat is visible rather than merely stated.

Same builder, same pipeline; only the region changes. docs/operator_screen.md.

Run:  python scripts/build_operator_screen.py --region uiseong_andong_2025
      python scripts/build_operator_screen.py --region yeongdeok_2025
      python scripts/build_operator_screen.py --region … --skip-preroll
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# The standing honesty line is the A4 sheet's own constant, imported so the
# screen and the paper a 이장 holds cannot drift apart.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from wildfireguardian.delivery.printable import FOOTER_LINES  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

#: Five discrete probability bands. Discrete on purpose: a continuous ramp
#: invites reading a precision the model does not have, and a judge asking
#: "what is that shade?" should get an interval, not a guess.
BANDS: tuple[float, ...] = (0.10, 0.30, 0.50, 0.70)
BAND_LABELS = ("0.10~0.30", "0.30~0.50", "0.50~0.70", "0.70~1.00")
#: Monochrome-safe ramp: increasing saturation AND decreasing lightness, so the
#: order survives a black-and-white projector.
BAND_FILLS = ("#fde68a", "#fb923c", "#dc2626", "#7f1d1d")

#: Rows the right-hand panel can show without scrolling at 1920x1080.
#: Measured, not guessed: 19.5 px per row in a 954 px pane.
MAX_ROWS: int = 45

#: Minutes of empty lead-in before the first detection. See the template.
PREROLL_MIN: int = 25

#: How long 「계산 중」 shows, in field minutes (12 s at 60x). The real routing
#: takes ~25 s; this is a beat, and the status bar carries the measured figure.
CALC_MIN: int = 12

#: Field minutes over which the dispatch list fills, WHATEVER the row count.
#: Fixed duration rather than fixed rate, so the beat is the same length for
#: Yeongdeok's 44 rows and Uiseong-Andong's 45-of-105. Trigger -> full list is
#: therefore CALC_MIN + FILL_SPAN_MIN = 30 field minutes = 30 s at 60x, which
#: is what makes a 60-second demo window around the trigger possible.
FILL_SPAN_MIN: int = 18

#: Envelope coverage per region, from the committed runs. NOT computed here.
#: docs/walk_bbox_coverage.md · docs/multi_region.md
REGION_KO: dict[str, str] = {
    "yeongdeok_2025": "영덕 2025",
    "uiseong_andong_2025": "의성·안동 2025",
    "uljin_samcheok_2022": "울진·삼척 2022",
}

COVERAGE_PCT: dict[str, float] = {
    "yeongdeok_2025": 32.6,
    "uiseong_andong_2025": 99.2,
    "uljin_samcheok_2022": 81.5,
}

OUTCOME = {
    "both_safe": ("자력 대피", "#2563eb"),
    "naive_into_FA_safe": ("구조 필요", "#f59e0b"),
    "no_safe_route": ("도달 불가", "#dc2626"),
    "fa_exceeds_budget": ("예산 초과", "#dc2626"),
    "both_enter": ("도달 불가", "#dc2626"),
    "naive_unreachable": ("도달 불가", "#dc2626"),
}


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def quantise(npz_path: Path) -> tuple[list[list[list[int]]], dict]:
    """Run-length encode each slice into four visible bands.

    Returns ``bands[slice][band] = [[row, col0, width], …]`` in grid cells. The
    field is sparse — under 1,600 cells reach 0.10 even at the final slice — so
    the whole surface costs a few tens of kilobytes rather than a raster.
    """
    z = np.load(npz_path)
    haz = z["haz_stack"].astype(np.float32)
    out: list[list[list[int]]] = []
    for s in range(haz.shape[0]):
        idx = np.digitize(haz[s], BANDS, right=False)     # 0 = below 0.10
        per_band: list[list[int]] = []
        for b in range(1, 5):
            runs: list[int] = []
            m = idx == b
            for r in range(m.shape[0]):
                row = m[r]
                if not row.any():
                    continue
                c = 0
                n = len(row)
                while c < n:
                    if row[c]:
                        c0 = c
                        while c < n and row[c]:
                            c += 1
                        runs.append([r, c0, c - c0])
                    else:
                        c += 1
            per_band.append(runs)
        out.append(per_band)
    meta = {"nrows": int(haz.shape[1]), "ncols": int(haz.shape[2]),
            "times_min": [float(t) for t in z["haz_times"]]}
    return out, meta


def build(run_dir: Path, out_path: Path, *, skip_preroll: bool = False,
          start_at: float | None = None, paused_on_load: bool = False) -> dict:
    viz = json.loads((run_dir / "viz.json").read_text(encoding="utf-8"))
    man = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    run = json.loads((run_dir / "RUN.json").read_text(encoding="utf-8"))

    npz = REPO / viz["hazard"]["npz_path"]
    bands, hmeta = quantise(npz)

    xmin, ymin, xmax, ymax = viz["hazard"]["grid_extent_5179"]
    cell = viz["hazard"]["cell_size_m"]

    # Hotspot times, expressed on the FIELD's clock (minutes since t=0) so the
    # surface and the detections share one timeline. They are two different
    # records of the same fire and must not be drawn on two different axes.
    # Projected HERE, at build time, with the same transformer the routing
    # used. The page does no geodesy: it draws numbers it was handed.
    from pyproj import Transformer  # noqa: PLC0415

    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    t0 = min(h["acquired_utc"] for h in viz["hotspots"])
    t0dt = datetime.strptime(t0, "%Y-%m-%dT%H:%M:%SZ")
    hotspots = []
    for h in viz["hotspots"]:
        dt = datetime.strptime(h["acquired_utc"], "%Y-%m-%dT%H:%M:%SZ")
        px, py = to5179.transform(h["lon"], h["lat"])
        hotspots.append({
            "px": round(px, 1), "py": round(py, 1),
            "t": round((dt - t0dt).total_seconds() / 60.0, 1),
            "conf": h["confidence"], "utc": h["acquired_utc"],
        })
    hotspots.sort(key=lambda h: h["t"])

    # ---- when did the routing actually fire? ------------------------------
    # NOT "when did the first hotspot arrive". A trigger fires when an OVERPASS
    # completes and its batch is diffed against the seen-set, which is the
    # cluster's last detection time. For Yeongdeok the two coincide (every
    # detection in overpass 0 shares one timestamp); for Uiseong-Andong they are
    # 77 minutes apart, and the earlier version showed 계산 중 at t=0 for a run
    # that did not route until t+77.
    trigger_source = (viz.get("trigger_source")
                      or run.get("trigger_source")
                      or run["scope"].get("trigger_source")
                      or ("replay" if run["mode"] == "replay" else "firms_nrt"))
    overpasses = (run.get("inputs", {}).get("poll", {}) or {}).get("overpasses")
    if trigger_source == "manual":
        # A manual report has no overpass to wait for — that is the whole
        # point of it. The reported coordinate IS the trigger, and it is the
        # only point on the map, so the trigger sits at t = 0.
        triggers = [0.0]
    elif overpasses:
        triggers = sorted(
            round((datetime.strptime(o["archive_time_utc"], "%Y-%m-%dT%H:%M:%SZ")
                   - t0dt).total_seconds() / 60.0, 1)
            for o in overpasses)
    else:
        raise SystemExit(
            "RUN.json carries no overpass times and this is not a manual "
            "trigger, so the trigger moment cannot be established. Regenerate "
            "the run.")

    # The dispatch rows: actionable points, most urgent first. Same ordering
    # rule the A4 sheet uses, so the screen and the paper agree.
    rows = sorted(
        viz["actionable"],
        key=lambda p: (p["closing_window_min"] is None,
                       p["closing_window_min"] if p["closing_window_min"] is not None else 1e9))

    # The walk network's own bbox, projected here. Drawing it makes the
    # 32.6 % coverage figure something a judge can SEE — the fire runs 45 km
    # west, the network stops at the box — instead of a number in a footer
    # that has to be taken on trust.
    wb = (__import__("wildfireguardian.config", fromlist=["get"])
          .get("bbox.multi_region_walk_bbox", {}) or {}).get(viz["region"])
    walk_box = None
    if wb:
        cx = [to5179.transform(wb[0], wb[1])[0], to5179.transform(wb[0], wb[3])[0],
              to5179.transform(wb[2], wb[1])[0], to5179.transform(wb[2], wb[3])[0]]
        cy = [to5179.transform(wb[0], wb[1])[1], to5179.transform(wb[0], wb[3])[1],
              to5179.transform(wb[2], wb[1])[1], to5179.transform(wb[2], wb[3])[1]]
        walk_box = {"x0": min(cx), "y0": min(cy), "x1": max(cx), "y1": max(cy)}

    # ---- crop to the data ------------------------------------------------
    # The simulation canvas is 78 x 90 km; the fire, the origins and the
    # refuges occupy a fraction of it. Drawing the whole canvas would spend
    # most of a 1280 px pane on empty grid and leave the thing being judged
    # too small to read. So the viewBox is the union of what is actually
    # plotted, padded — cropping the FRAME, never the data.
    xs: list[float] = [o["x"] for o in viz["origins"]] + \
                      [r["x"] for r in viz["refuges"]] + \
                      [h["px"] for h in hotspots]
    ys: list[float] = [o["y"] for o in viz["origins"]] + \
                      [r["y"] for r in viz["refuges"]] + \
                      [h["py"] for h in hotspots]
    for s in bands:
        for runs in s:
            for r, c0, w in runs:
                xs += [xmin + c0 * cell, xmin + (c0 + w) * cell]
                ys += [ymax - (r + 1) * cell, ymax - r * cell]
    for rt in viz["routes"]:
        for seq in (rt["naive_xy"], rt["fa_xy"]):
            xs += [p[0] for p in seq]
            ys += [p[1] for p in seq]
    if walk_box:                       # the frame must contain the box it draws
        xs += [walk_box["x0"], walk_box["x1"]]
        ys += [walk_box["y0"], walk_box["y1"]]
    pad = 0.04 * max(max(xs) - min(xs), max(ys) - min(ys))
    view = {"x0": min(xs) - pad, "y0": min(ys) - pad,
            "x1": max(xs) + pad, "y1": max(ys) + pad}

    # Coverage is per REGION, and the whole point of keeping both screens is
    # that the two differ: Yeongdeok 32.6 % (the limitation, visible on the
    # map) against Uiseong-Andong 99.2 % (the demonstration). Reading it from
    # the region's own committed artifact stops the constant drifting.
    coverage_pct = COVERAGE_PCT.get(viz["region"])
    if coverage_pct is None:
        raise SystemExit(
            f"no committed coverage figure for {viz['region']}. Add it to "
            "COVERAGE_PCT rather than letting the screen invent one.")

    scope = run["scope"]
    # A manual trigger has nothing to lead in FROM — no satellite was being
    # waited on — so the pre-roll defaults off unless a start point was asked
    # for explicitly.
    if trigger_source == "manual" and start_at is None:
        skip_preroll = True

    payload = {
        "view": view,
        "walk_box": walk_box,
        "built_utc": run["started_utc"],
        "git_commit": _git(),
        "run_dir": str(run_dir.relative_to(REPO)),
        "grid": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                 "cell": cell, **hmeta},
        "bands": bands,
        "band_labels": list(BAND_LABELS),
        "band_fills": list(BAND_FILLS),
        "origins": viz["origins"],
        "actionable": rows,
        "routes": viz["routes"],
        "refuges": viz["refuges"],
        "hotspots": hotspots,
        "counts": viz["counts"],
        "coverage_pct": coverage_pct,
        "responder": viz.get("responder_side", {}),
        "max_rows": MAX_ROWS,
        "triggers": triggers,
        "trigger_source": trigger_source,
        "trigger_at": run["scope"].get("trigger_at", ""),
        "trigger_at_meaning": run["scope"].get("trigger_at_meaning", ""),
        "calc_min": CALC_MIN,
        "fill_span_min": FILL_SPAN_MIN,
        "start_at": start_at,
        "paused_on_load": bool(paused_on_load),
        "n_actionable_total": len(rows),
        "preroll": 0 if skip_preroll else PREROLL_MIN,
        "region": viz["region"],
        "region_ko": REGION_KO.get(viz["region"], viz["region"]),
        "scope": {
            "mode_banner": scope["mode_banner_ko"],
            "detection": scope["detection_line_ko"],
            "trigger_at": scope.get("trigger_at", ""),
            "weather": scope["weather_line_ko"],
            "weather_basis": scope["weather_basis"],
        },
        "applicability": viz["field_applicability"],
        "timings": run["timings_s"],
        "npz_name": Path(viz["hazard"]["npz_path"]).name,
        "npz_sha256": viz["hazard"]["npz_sha256"][:16],
        "n_villages": man["n_villages"],
    }

    html = TEMPLATE.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False,
                                                       separators=(",", ":")))
    html = html.replace("__HONESTY__", FOOTER_LINES[0])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {"triggers": triggers, "trigger_source": trigger_source,
            "bytes": out_path.stat().st_size, "n_origins": len(viz["origins"]),
            "n_rows": len(rows), "n_rows_shown": min(len(rows), MAX_ROWS),
            "n_routes": len(viz["routes"]), "n_hotspots": len(hotspots),
            "preroll": 0 if skip_preroll else PREROLL_MIN,
            "region": viz["region"], "coverage_pct": coverage_pct,
            "horizon_min": hmeta["times_min"][-1]}


TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>WildfireGuardian · 운영자 화면 (재생 모드)</title>
<style>
/* Self-contained: system fonts only, no external stylesheet, no network. */
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden;background:#0b0f14;color:#e8edf2;
  font-family:"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif}
#app{display:flex;flex-direction:column;height:100vh;width:100vw}
header{display:flex;align-items:center;gap:16px;padding:8px 16px;
  border-bottom:1px solid #1f2a37;background:#0e141b;flex:0 0 auto}
header h1{font-size:17px;font-weight:700;letter-spacing:-.3px}
.badge{font-size:12px;font-weight:700;padding:3px 9px;border-radius:3px;
  background:#7f1d1d;color:#fff;letter-spacing:.3px}
.clock{font-variant-numeric:tabular-nums;font-size:15px;font-weight:700;
  color:#93c5fd}
.ctrl{margin-left:auto;display:flex;gap:6px;align-items:center}
button{font:inherit;font-size:13px;font-weight:700;padding:5px 12px;
  background:#1f2a37;color:#e8edf2;border:1px solid #334155;border-radius:4px;
  cursor:pointer}
button:hover{background:#2b3a4d}
button.on{background:#2563eb;border-color:#3b82f6;color:#fff}
button.pause{min-width:74px}
main{display:flex;flex:1 1 auto;min-height:0}
#mapwrap{flex:0 0 66.6%;position:relative;border-right:1px solid #1f2a37;
  min-width:0}
svg{display:block;width:100%;height:100%}
#side{flex:1 1 auto;display:flex;flex-direction:column;min-width:0;
  background:#0e141b}
.sidehead{padding:8px 12px;border-bottom:1px solid #1f2a37;flex:0 0 auto}
.sidehead h2{font-size:15px;font-weight:700}
.sidehead .sub{font-size:11.5px;color:#94a3b8;margin-top:2px}
#calc{display:none;padding:9px 12px;background:#78350f;color:#fed7aa;
  font-size:13px;font-weight:700;border-bottom:1px solid #1f2a37;flex:0 0 auto}
#calc.on{display:block}
#tablewrap{flex:1 1 auto;overflow:hidden;min-height:0}
table{width:100%;border-collapse:collapse;font-size:12px;
  font-variant-numeric:tabular-nums}
th{position:sticky;top:0;background:#16202b;color:#94a3b8;font-size:10.5px;
  font-weight:700;text-align:left;padding:4px 8px;border-bottom:1px solid #334155}
td{padding:2px 8px;border-bottom:1px solid #16202b;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
tr.new{animation:flash .5s ease-out}
@keyframes flash{from{background:#1e3a5f}to{background:transparent}}
.rank{color:#7c8ba1;width:26px}
.loc{max-width:0;width:52%}
.win{width:64px;text-align:right;font-weight:700}
.st{width:70px;font-weight:700}
.ok{color:#fbbf24}.bad{color:#f87171}
.legend{position:absolute;left:12px;bottom:12px;background:rgba(11,15,20,.9);
  border:1px solid #1f2a37;border-radius:4px;padding:8px 10px;font-size:11px;
  line-height:1.5}
.legend b{display:block;font-size:10.5px;color:#94a3b8;margin-bottom:3px;
  font-weight:700}
.sw{display:inline-block;width:11px;height:11px;margin-right:5px;
  vertical-align:-1px;border:1px solid rgba(255,255,255,.25)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;
  margin-right:5px;vertical-align:-1px}
.legend .row{display:flex;gap:14px}
.legend .col{min-width:96px}
footer{flex:0 0 auto;display:flex;gap:0;border-top:1px solid #1f2a37;
  background:#0e141b;font-size:12.5px}
footer div{padding:7px 16px;border-right:1px solid #1f2a37;white-space:nowrap}
footer .warn{color:#fca5a5;font-weight:700}
footer .manual{background:#1e3a5f;color:#bfdbfe;font-weight:700}
footer .k{color:#7c8ba1;margin-right:6px}
footer .last{border-right:none;margin-left:auto;color:#7c8ba1}
#honesty{flex:0 0 auto;padding:5px 16px;background:#0b0f14;color:#94a3b8;font-size:12px;border-top:1px solid #1f2a37}
</style></head>
<body><div id="app">
<header>
  <h1>WildfireGuardian 운영자 화면 <span id="regionlbl"
    style="font-weight:400;color:#94a3b8;font-size:14px"></span></h1>
  <span class="badge" id="modebadge">재생 모드</span>
  <span class="clock" id="clock">+000분</span>
  <span style="font-size:12px;color:#94a3b8" id="slicelbl"></span>
  <span style="font-size:12px;color:#7c8ba1" id="durlbl"></span>
  <div class="ctrl">
    <button id="pause" class="pause">일시정지</button>
    <button data-sp="1">1×</button>
    <button data-sp="10">10×</button>
    <button data-sp="60" class="on">60×</button>
    <button id="reset">처음부터</button>
  </div>
</header>
<main>
  <div id="mapwrap">
    <svg id="map" preserveAspectRatio="xMidYMid meet"></svg>
    <div class="legend">
      <b>위험 확률 (12시간 예측, 이산 5구간)</b>
      <div id="bandleg"></div>
      <b style="margin-top:7px">출발지</b>
      <div class="row"><div class="col"><span class="dot" style="background:#2563eb"></span>자력 대피</div>
      <div class="col"><span class="dot" style="background:#f59e0b"></span>구조 필요</div>
      <div class="col"><span class="dot" style="background:#dc2626"></span>도달 불가</div></div>
      <b style="margin-top:7px">보행망 범위 (커버리지 32.6%)</b>
      <div><span class="sw" style="background:none;border:1px dashed #94a3b8"></span>이 범위 밖 출발지는 측정되지 않았습니다</div>
      <b style="margin-top:7px">경로</b>
      <div class="row"><div class="col"><span class="sw" style="background:#f87171"></span>주민 대피 경로</div>
      <div class="col"><span class="sw" style="background:#22d3ee"></span>미래 인지 경로</div></div>
    </div>
  </div>
  <div id="side">
    <div class="sidehead">
      <h2>출동 목록</h2>
      <div class="sub" id="sidesub">대기 중: 화점 탐지를 기다리는 중입니다</div>
    </div>
    <div id="calc">계산 중 …</div>
    <div id="tablewrap"><table>
      <thead><tr><th class="rank">#</th><th class="loc">위치</th>
      <th class="win">남은 시간</th><th class="st">도달</th></tr></thead>
      <tbody id="rows"></tbody></table></div>
  </div>
</main>
<footer>
  <div><span class="k">화점 탐지</span><span id="f1">재생 모드</span></div>
  <div><span class="k">기상 자료</span><span id="f2"></span></div>
  <div class="warn" id="f3"></div>
  <div><span class="k">위험면</span><span id="f4"></span></div>
  <div class="last" id="f5"></div>
</footer>
<!-- PHASE 21: the standing honesty line. Not a live value, never changes, and
     substituted from delivery.printable.FOOTER_LINES[0] at build time so it is
     the same sentence the A4 sheet carries. -->
<div id="honesty">__HONESTY__</div>
</div>
<script>
const D = /*__DATA__*/;

/* ---- projection: EPSG:5179 metres -> SVG units, computed once ------------
   No tile server, no basemap. The grid's own extent IS the viewBox, so the
   drawing is the data rather than an overlay on someone else's picture. */
const G = D.grid, V = D.view;
const W = V.x1 - V.x0, H = V.y1 - V.y0;
const svg = document.getElementById('map');
svg.setAttribute('viewBox', `0 0 ${W.toFixed(0)} ${H.toFixed(0)}`);
const PX = (x) => x - V.x0;                // metres east of the view origin
const PY = (y) => V.y1 - y;                // SVG y grows downward
/* One metre in viewBox units is one unit, so marker radii below are metres.
   R scales them with the crop so they stay legible whatever the extent. */
const R = Math.max(W, H) / 1000;
const NS = 'http://www.w3.org/2000/svg';
const el = (n, a) => { const e = document.createElementNS(NS, n);
  for (const k in a) e.setAttribute(k, a[k]); return e; };

/* ---- static layers ------------------------------------------------------ */
const gBox = el('g', {}), gHaz = el('g', {}), gRoute = el('g', {}),
      gOrig = el('g', {}), gRef = el('g', {}), gHot = el('g', {});
svg.append(gHaz, gBox, gRoute, gOrig, gRef, gHot);
if (D.walk_box) {
  const b = D.walk_box;
  gBox.appendChild(el('rect', {x: PX(b.x0), y: PY(b.y1),
    width: b.x1 - b.x0, height: b.y1 - b.y0, fill: 'none',
    stroke: '#7c8ba1', 'stroke-width': 1.6 * R,
    'stroke-dasharray': `${7 * R} ${5 * R}`}));
}

/* hazard: one <path> per band per slice, built from run-length rectangles */
const slicePaths = D.bands.map((bandsForSlice) => {
  const g = el('g', {opacity: 0});
  bandsForSlice.forEach((runs, bi) => {
    let d = '';
    for (const [r, c0, w] of runs) {
      const x = PX(G.xmin + c0 * G.cell), y = PY(G.ymax - r * G.cell);
      d += `M${x.toFixed(0)} ${y.toFixed(0)}h${(w * G.cell).toFixed(0)}` +
           `v${G.cell.toFixed(0)}h${(-w * G.cell).toFixed(0)}z`;
    }
    if (d) g.appendChild(el('path', {d, fill: D.band_fills[bi],
      'fill-opacity': 0.55 + 0.1 * bi, 'shape-rendering': 'crispEdges'}));
  });
  gHaz.appendChild(g);
  return g;
});

/* refuges */
for (const rf of D.refuges)
  gRef.appendChild(el('rect', {x: PX(rf.x) - 3.2 * R, y: PY(rf.y) - 3.2 * R,
    width: 6.4 * R, height: 6.4 * R, fill: '#34d399', 'fill-opacity': .95,
    stroke: '#052e1b', 'stroke-width': 1.2 * R}));

/* origins, drawn in three passes so the urgent ones sit on top */
const order = ['both_safe', 'naive_into_FA_safe', 'no_safe_route',
               'fa_exceeds_budget', 'both_enter', 'naive_unreachable'];
const COLOR = {both_safe: '#2563eb', naive_into_FA_safe: '#f59e0b',
  no_safe_route: '#dc2626', fa_exceeds_budget: '#dc2626',
  both_enter: '#dc2626', naive_unreachable: '#dc2626'};
const originNodes = [];
for (const b of order) for (const o of D.origins) {
  if (o.bucket !== b) continue;
  const safe = b === 'both_safe';
  const c = el('circle', {cx: PX(o.x), cy: PY(o.y), r: (safe ? 2.6 : 5.2) * R,
    fill: COLOR[b] || '#dc2626', 'fill-opacity': safe ? .6 : .98,
    stroke: safe ? 'none' : '#0b0f14', 'stroke-width': 1.3 * R, opacity: 0});
  gOrig.appendChild(c); originNodes.push(c);
}

/* the two routes — real polylines from the run, not an illustration */
const routePair = D.routes[0];
let rNaive = null, rFA = null;
if (routePair) {
  const path = (pts) => pts.map(([x, y], i) =>
    `${i ? 'L' : 'M'}${PX(x).toFixed(0)} ${PY(y).toFixed(0)}`).join('');
  rNaive = el('path', {d: path(routePair.naive_xy), fill: 'none',
    stroke: '#f87171', 'stroke-width': 3.4 * R, 'stroke-linejoin': 'round',
    'stroke-linecap': 'round', 'stroke-dasharray': `${9 * R} ${6 * R}`,
    opacity: 0});
  rFA = el('path', {d: path(routePair.fa_xy), fill: 'none', stroke: '#22d3ee',
    'stroke-width': 3.4 * R, 'stroke-linejoin': 'round',
    'stroke-linecap': 'round', opacity: 0});
  gRoute.append(rNaive, rFA);
}

/* ---- timeline ----------------------------------------------------------
   One clock, in minutes since the hazard field's t=0. The detections and the
   surface are two records of the same fire, so they share an axis. */
const HORIZON = G.times_min[G.times_min.length - 1];
/* When the routing ACTUALLY fired: an overpass completing, not the first
   hotspot arriving. For Yeongdeok the two coincide; for Uiseong-Andong they
   are 77 minutes apart. Carried from RUN.json, never inferred here. */
const TRIGGERS = D.triggers;
const CALC_MIN = D.calc_min;
/* A short lead-in before the first detection. The field's t=0 IS the first
   overpass, so without it the screen opens mid-trigger and the sequence
   detection -> surface -> routes -> list is never visible. These minutes are
   real and empty: nothing had been detected yet. The clock says so.
   --start-at overrides it: an explicit start point is where you meant. */
const PREROLL = D.preroll;
const T_START = (D.start_at !== null && D.start_at !== undefined)
  ? D.start_at : -PREROLL;
let t = T_START, speed = 60, paused = !!D.paused_on_load, last = null;
let shown = -1, filled = 0, fillStart = null;

const rowsEl = document.getElementById('rows');
const calcEl = document.getElementById('calc');
const subEl = document.getElementById('sidesub');

function fmtWin(v) {
  if (v === null || v === undefined) return '12h+';
  if (v <= 0) return '경과';
  return Math.round(v) + '분';
}
function addRow(i) {
  const p = D.actionable[i];
  const tr = document.createElement('tr');
  tr.className = 'new';
  tr.innerHTML =
    `<td class="rank">${i + 1}</td><td class="loc">${p.label || '-'}</td>` +
    `<td class="win ${p.unreachable ? 'bad' : 'ok'}">${fmtWin(p.closing_window_min)}</td>` +
    `<td class="st ${p.unreachable ? 'bad' : 'ok'}">` +
    `${p.unreachable ? '도보 불가' : '안내'}</td>`;
  rowsEl.appendChild(tr);
}

function sliceFor(tm) {
  let s = 0;
  for (let i = 0; i < G.times_min.length; i++) if (tm >= G.times_min[i]) s = i;
  return s;
}

function render() {
  document.getElementById('clock').textContent = t < 0
    ? '탐지 전 ' + Math.ceil(-t) + '분'
    : '+' + String(Math.floor(t)).padStart(3, '0') + '분';
  const s = sliceFor(Math.max(t, 0));
  if (s !== shown) {
    slicePaths.forEach((g, i) =>
      g.setAttribute('opacity', (t >= 0 && i === s) ? 1 : 0));
    shown = t < 0 ? -1 : s;
    document.getElementById('slicelbl').textContent = t < 0 ? '위험면 대기'
      : `위험면 슬라이스 ${s + 1}/${G.times_min.length} (t+${G.times_min[s]}분)`;
  }
  /* hotspots appear at the minute they were detected */
  let nHot = 0;
  if (t >= 0) for (const h of D.hotspots) if (t >= h.t) nHot++;
  while (gHot.childElementCount < nHot) {
    const h = D.hotspots[gHot.childElementCount];
    const x = PX(h.px), y = PY(h.py);
    const prev = gHot.lastElementChild;
    if (prev) prev.setAttribute('opacity', .5);
    const g = el('g', {});
    g.appendChild(el('circle', {cx: x, cy: y, r: 9 * R, fill: 'none',
      stroke: '#fde047', 'stroke-width': 1.4 * R, opacity: .8}));
    g.appendChild(el('circle', {cx: x, cy: y, r: 2.2 * R, fill: '#fde047'}));
    gHot.appendChild(g);
  }
  /* the trigger: 계산 중, then the list fills from the top */
  const fired = t < 0 ? [] : TRIGGERS.filter(x => t >= x);
  if (fired.length && fillStart === null) fillStart = fired[0] + CALC_MIN;
  if (fillStart !== null) {
    if (t < fillStart) {
      calcEl.classList.add('on');
      subEl.textContent = '트리거: 라우팅 실행 중';
    } else {
      calcEl.classList.remove('on');
      const cap = Math.min(D.actionable.length, D.max_rows);
      /* Fixed DURATION, not fixed rate: the beat is the same length whether
         the region has 44 rows or 45-of-105. */
      const per = D.fill_span_min / cap;
      const want = Math.min(cap, Math.ceil((t - fillStart) / per));
      while (filled < want) { addRow(filled); filled++; }
      /* More points than fit on one screen. Say so rather than letting the
         list appear to end — the A4 sheets carry every one of them. */
      if (filled === cap && D.n_actionable_total > cap && !rowsEl.dataset.more) {
        rowsEl.dataset.more = '1';
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="4" style="color:#94a3b8;font-weight:700;` +
          `padding:5px 8px">… 외 ${D.n_actionable_total - cap}곳 · ` +
          `전체 ${D.n_actionable_total}곳 (A4 시트에는 전부 포함)</td>`;
        rowsEl.appendChild(tr);
      }
      if (filled) {
        subEl.textContent =
          `${D.counts.naive_into_FA_safe}곳 안내 · ` +
          `${D.counts.no_safe_route}곳 도보 불가 · ` +
          `자력 대피 ${D.counts.both_safe}곳 (전체 ${D.origins.length})`;
        originNodes.forEach(n => n.setAttribute('opacity', 1));
        if (rNaive) { rNaive.setAttribute('opacity', .95);
                      rFA.setAttribute('opacity', .95); }
      }
    }
  }
}

/* ---- clock -------------------------------------------------------------- */
function tick(ts) {
  if (last === null) last = ts;
  const dt = (ts - last) / 1000; last = ts;
  if (!paused) { t += dt * speed / 60; if (t > HORIZON) { t = HORIZON; } }
  render();
  requestAnimationFrame(tick);
}

function durText() {
  const secs = HORIZON * 60 / speed;
  const s = secs < 90 ? `${Math.round(secs)}초`
          : secs < 5400 ? `${Math.round(secs / 60)}분`
          : `${(secs / 3600).toFixed(1)}시간`;
  return `전체 재생 ${s} (${speed}×, 예측 ${HORIZON}분)`;
}
document.querySelectorAll('button[data-sp]').forEach(b => {
  b.title = `${Math.round(HORIZON * 60 / +b.dataset.sp / 60)}분 전체 재생`;
  b.onclick = () => {
    speed = +b.dataset.sp;
    document.querySelectorAll('button[data-sp]').forEach(x =>
      x.classList.toggle('on', x === b));
    document.getElementById('durlbl').textContent = durText();
  };
});
document.getElementById('durlbl').textContent = durText();
const pb = document.getElementById('pause');
pb.textContent = paused ? '재생' : '일시정지';
pb.classList.toggle('on', paused);
pb.onclick = () => { paused = !paused;
  pb.textContent = paused ? '재생' : '일시정지';
  pb.classList.toggle('on', paused); };
document.getElementById('reset').onclick = () => {
  t = T_START; shown = -1; filled = 0; fillStart = null;
  rowsEl.innerHTML = ''; delete rowsEl.dataset.more; gHot.innerHTML = '';
  calcEl.classList.remove('on');
  subEl.textContent = '대기 중: 화점 탐지를 기다리는 중입니다';
  originNodes.forEach(n => n.setAttribute('opacity', 0));
  if (rNaive) { rNaive.setAttribute('opacity', 0); rFA.setAttribute('opacity', 0); }
  render();          /* repaint now, so reset works while paused too */
};

/* ---- chrome ------------------------------------------------------------- */
document.getElementById('calc').textContent =
  `계산 중 … 사전 계산 위험면에서 ${D.origins.length}개 출발지를 라우팅하고 있습니다`;
document.getElementById('bandleg').innerHTML = D.band_labels.map((l, i) =>
  `<div><span class="sw" style="background:${D.band_fills[i]}"></span>p ${l}</div>`
).join('');
document.getElementById('modebadge').textContent =
  D.trigger_source === 'manual' ? '수동 입력'
  : D.trigger_source === 'firms_nrt' ? '실시간 모드' : '재생 모드';
document.getElementById('regionlbl').textContent = D.region_ko;
/* The first status cell states the SOURCE. For a manual trigger the time on
   it is when the coordinate was entered — a 119 call, a watch-tower, a CCTV
   operator — and NOT a satellite overpass. Saying so on the bar itself is the
   difference between reporting and claiming. */
const f1 = document.getElementById('f1');
if (D.trigger_source === 'manual') {
  /* The mandated line is 「발화점: 수동 입력 · {시각}」 in full, so the generic
     label prefix is cleared rather than duplicated. */
  f1.parentNode.firstChild.textContent = '';
  f1.textContent = D.scope.detection;
  f1.parentNode.classList.add('manual');
  const note = document.createElement('div');
  note.className = 'warn';
  note.textContent = '트리거 시각 = 좌표 입력 시각 (위성 통과 시각 아님)';
  f1.parentNode.parentNode.insertBefore(note, f1.parentNode.nextSibling);
} else {
  f1.textContent = '재생 모드 · ' + D.scope.weather_basis.split(' ')[0] + ' 기록 재생';
}
document.getElementById('f2').textContent = D.scope.weather.replace('기상 자료: ', '');
document.getElementById('f3').textContent = '보행망 커버리지 ' + D.coverage_pct + '%';
if (D.responder && D.responder.available === false) {
  const f = document.querySelector('footer');
  const d = document.createElement('div');
  d.className = 'warn';
  d.textContent = D.responder.status_ko;
  f.insertBefore(d, document.getElementById('f4').parentNode);
}
document.getElementById('f4').textContent = D.npz_name + ' · ' + D.npz_sha256 + '…';
document.getElementById('f5').textContent =
  `라우팅 ${D.timings.route_s.toFixed(1)}s · 마을 ${D.n_villages}곳 · ` +
  `커밋 ${D.git_commit.slice(0, 7)} · 사전 계산 결과 재생 (실시간 계산 아님)`;

render();          /* paint the start state before the first frame, so a
                      --paused-on-load screen opens on its content */
requestAnimationFrame(tick);
</script></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default=None,
                    help="a PHASE-6 run directory containing viz.json")
    ap.add_argument("--region", default=None,
                    help="pick the newest run for this region instead of the "
                         "newest run overall")
    ap.add_argument("--trigger-source", default=None,
                    choices=["firms_nrt", "replay", "manual"],
                    help="which trigger's run to build from. Required when a "
                         "region has runs from more than one source — picking "
                         "the newest silently once built a FIRMS screen out of "
                         "a manual run.")
    ap.add_argument("--out", default=None,
                    help="default: outputs/live/screens/{region}/operator_screen.html")
    ap.add_argument("--also-demo", action="store_true",
                    help="additionally write demo/operator_screen.html")
    ap.add_argument("--skip-preroll", action="store_true",
                    help="start at the moment of detection instead of "
                         f"{PREROLL_MIN} empty minutes before it. A four-minute "
                         "talk may not have 25 seconds to spend on an empty map.")
    ap.add_argument("--start-at", type=float, default=None, metavar="MIN",
                    help="open at this many FIELD MINUTES from the field's t=0. "
                         "The hazard slice, the hotspots and the dispatch list "
                         "are reconstructed to that instant, so the screen is "
                         "identical to one played from the beginning and "
                         "scrubbed forward. Overrides --skip-preroll.")
    ap.add_argument("--paused-on-load", action="store_true",
                    help="open paused, showing the start state. Press 재생 when "
                         "you are ready to talk.")
    ap.add_argument("--list-triggers", action="store_true",
                    help="print this run's trigger times and exit")
    args = ap.parse_args()

    root = REPO / "outputs" / "live"
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()   # accept relative paths too
    else:
        cands = sorted(root.glob("**/viz.json"), key=lambda p: p.stat().st_mtime)
        def _src(v: Path) -> str:
            d = json.loads(v.read_text(encoding="utf-8"))
            return d.get("trigger_source") or (
                "manual" if "/manual/" in str(v) else "replay")

        if args.region:
            cands = [c for c in cands
                     if json.loads(c.read_text(encoding="utf-8")).get("region")
                     == args.region]
        if args.trigger_source:
            cands = [c for c in cands if _src(c) == args.trigger_source]
        elif cands:
            # Ambiguity is an error, not a coin toss. Building a FIRMS screen
            # out of a manual run is silent and wrong, and it happened once.
            sources = {_src(c) for c in cands}
            if len(sources) > 1:
                print(f"STOP: runs from {sorted(sources)} match. Pass "
                      "--trigger-source to say which one this screen is of.",
                      file=sys.stderr)
                return 2
        if not cands:
            print(f"STOP: no run with viz.json"
                  + (f" for {args.region}" if args.region else "") + ". Generate one:\n"
                  "  python scripts/run_live_detection.py --replay"
                  + (f" --region {args.region}" if args.region else ""),
                  file=sys.stderr)
            return 2
        run_dir = cands[-1].parent

    region = json.loads((run_dir / "viz.json").read_text(encoding="utf-8"))["region"]
    out = Path(args.out) if args.out else (
        REPO / "outputs" / "live" / "screens" / region / "operator_screen.html")

    if args.list_triggers:
        info = build(run_dir, REPO / ".trigger-probe.html")
        (REPO / ".trigger-probe.html").unlink(missing_ok=True)
        print(f"region : {region}")
        for i, tm in enumerate(info["triggers"], start=1):
            print(f"  trigger {i}: t+{tm:g} min  "
                  f"(60x -> {tm:g}s from the field's t=0)")
        return 0

    info = build(run_dir, out, skip_preroll=args.skip_preroll,
                 start_at=args.start_at,
                 paused_on_load=args.paused_on_load)
    print(f"region : {region}   source: {info['trigger_source']}")
    print(f"run    : {run_dir.relative_to(REPO)}")
    print(f"origins: {info['n_origins']}  rows shown: {info['n_rows_shown']}"
          f"/{info['n_rows']}  routes: {info['n_routes']}  "
          f"hotspots: {info['n_hotspots']}")
    print(f"triggers: {', '.join('t+' + format(x, 'g') for x in info['triggers'])} min")
    if args.start_at is not None:
        print(f"start-at: t+{args.start_at:g} min"
              + ("  (paused on load)" if args.paused_on_load else ""))
    else:
        print(f"pre-roll: {info['preroll']} min"
              + ("  (skipped)" if args.skip_preroll else ""))
    print(f"horizon: {info['horizon_min']:.0f} min "
          f"(60x -> {(info['horizon_min'] + info['preroll']) / 60:.1f} min wall clock)")
    print(f"wrote  : {out.relative_to(REPO)}  "
          f"({info['bytes'] / 1024:.0f} KB, self-contained)")
    if args.also_demo:
        d = REPO / "demo" / "operator_screen.html"
        build(run_dir, d, skip_preroll=args.skip_preroll)
        print(f"       : {d.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
