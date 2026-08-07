#!/usr/bin/env python
"""Build the operator console — one screen, 1920x1080, no scroll.

Round-3 PHASE 22 STEP 1.

WHAT THIS IS, AND HOW IT DIFFERS FROM PHASE 8
---------------------------------------------
`demo/operator_screen.html` REPLAYS. It has no solver, by design and by test,
and every number on it was computed before it was built. That is the right thing
for a four-minute talk and the wrong thing for a judge who asks "what if the fire
started here instead?".

This console shows a pre-computed run **by default** — instantly, because the
answer already exists — and can also ask the PHASE-22 API to compute a fresh
one, which reports its progress while it works.

⚠ THE DEFAULT IS PRE-COMPUTED AND THE SCREEN SAYS SO.
The badge reads 「사전 계산 결과 · 실제 계산 N초」, where N is READ FROM THE RUN
BEING SHOWN rather than typed. It is never implied that the answer appeared
instantly: the number beside it is what computing that very result cost, and a
live run is one click away for anyone who wants to watch it happen.

THE MAP IS THE PHASE-8 MAP
--------------------------
The quantised hazard bands, the band labels and their fills, the row ordering —
all imported from ``build_operator_screen``, not reimplemented. One definition
means the console and the replay screen cannot disagree about what a 0.30~0.50
band looks like or which dispatch row is most urgent.

    ⚠ No tiles. No basemap. No web font. Coordinates are projected at build time
      by the same transformer the routing used, and written into the file as SVG.

⚠ REBUILDING NEEDS A REPLAY RUN. WHETHER THAT RUN IS COMMITTED IS **UNSETTLED**.
``web/console.html`` is a committed build artifact with its data inlined, in
exactly the way ``demo/operator_screen.html`` is — it opens and works with
nothing else present. To rebuild:

    python scripts/run_live_detection.py --replay --speed 0 --no-pdf --max-triggers 1
    python scripts/build_console.py

⚠ **This docstring used to claim the build INPUT "is not worth committing", and
the repository disagreed with it**: the `20260803T…` runs under
`outputs/live/replay/` are tracked, 122 files each. The claim was therefore
false when read as a description and misleading when read as a rule, and a run
went missing under cover of it — see `docs/api_layer.md` §1.12, where the
inconsistency, what it cost, and three candidate resolutions are recorded.

The decision is the user's and is NOT taken here. What this file no longer does
is assert one of the two answers while the tree does the other.

The figure the badge shows is that run's OWN measured cost, read from its
RUN.json. It is never typed, so it cannot drift from the result beside it — and
a run made on older code would show its own slower number rather than a current
one borrowed from somewhere else.

Run:
    python scripts/build_console.py                       # newest replay run
    python scripts/build_console.py --run-dir <dir> --out web/console.html

⚠ THE TEMPLATE LIVES IN scripts/, NOT web/.
``web/`` is served wholesale by the API, and a template is a BUILD INPUT: it
still carries the ``/*__DATA__*/`` placeholder, so a browser that reached it
would run ``JSON.parse`` on a comment and render a blank, broken console. It was
in ``web/`` and WAS reachable at /console.template.html with HTTP 200. Anything
under ``web/`` is public; put build inputs somewhere else.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

# The A4 sheet's own constant. Imported, never retyped: the sentence a 이장 holds
# on paper and the sentence on the console must be one string.
from wildfireguardian.delivery.printable import FOOTER_LINES  # noqa: E402

# The photo-EXIF processing statement. Imported for the same reason: one copy.
from wildfireguardian.photo import PRIVACY_KO as PHOTO_PRIVACY_KO  # noqa: E402

# PHASE 8's rendering decisions, reused rather than re-made.
from build_operator_screen import (  # noqa: E402
    BAND_FILLS, BAND_LABELS, quantise,
)

#: The four routing outcomes, each with a colour AND a shape AND a label.
#: Colour alone is not a channel: about one man in twelve cannot separate the
#: amber from the red, a projector may render both as grey, and the A4 sheet is
#: photocopied. Shape and label carry the same information independently.
BUCKETS: tuple[dict, ...] = (
    {"key": "both_safe", "ko": "자력 대피", "fill": "#22d3ee",
     "shape": "circle", "mark": "●"},
    {"key": "naive_into_FA_safe", "ko": "구조 필요", "fill": "#f59e0b",
     "shape": "triangle", "mark": "▲"},
    {"key": "no_safe_route", "ko": "도달 불가", "fill": "#dc2626",
     "shape": "square", "mark": "■"},
    {"key": "fa_exceeds_budget", "ko": "예산 초과", "fill": "#2563eb",
     "shape": "diamond", "mark": "◆"},
)

#: Rows the right-hand panel shows without scrolling at 1920x1080. Measured
#: against the built page by rendering it and reading scrollHeight, not guessed.
#: 1080 - header 58 - bar 3 - sidehead 44 - thead 30 - footer 62 = 883 px, and a
#: row is 19.5 px, so 44 fit and all 44 actionable points are shown without the
#: 「외 N곳」 overflow line. If the count ever exceeds this the line returns.
MAX_ROWS: int = 44


def newest_run(region: str = "yeongdeok_2025") -> Path:
    base = REPO / "outputs" / "live" / "replay"
    # Runs land either directly under replay/ (the script's default out-root) or
    # under replay/{region}/ (when --out-root named one). Both are searched, and
    # only those whose viz.json actually names this region are eligible.
    runs = []
    for viz in list(base.glob("*/viz.json")) + list(base.glob("*/*/viz.json")):
        try:
            if json.loads(viz.read_text(encoding="utf-8")).get("region") == region:
                runs.append(viz.parent)
        except Exception:
            continue
    runs.sort(key=lambda d: d.name)
    if not runs:
        raise SystemExit(
            f"no replay run under {base}. Run scripts/run_live_detection.py "
            "--replay --speed 0 --no-pdf first.")
    return runs[-1]


def _coverage_pct(region: str) -> float:
    """Walk-bbox coverage of the predicted core, READ not typed.

    ⚠ This used to be the literal ``32.6``, which was right for Yeongdeok and
    would have been silently wrong for the other two the moment the console
    could switch. `multi_region_comparison.json` is the committed artifact that
    owns all three (`envelope_coverage_final_slice`), and
    `docs/walk_bbox_coverage.md` quotes the same numbers.
    """
    path = REPO / "data" / "processed" / "multi_region_comparison.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    for row in table["regions"]:
        if row["region"] == region:
            return round(float(row["envelope_coverage_final_slice"]) * 100.0, 1)
    raise SystemExit(f"{region} is not in {path.name}; coverage cannot be quoted")


#: EM and EN dash, neither of which the vendored subset has a glyph for.
_BANNED_DASHES = {"—": ". ", "–": ". "}


def _dash_safe(text: str) -> str:
    """Normalise dashes in a string the SERVER owns but the CONSOLE displays.

    ⚠ Why this is a build step and not an edit at the source. The responder-side
    sentence lives in `live.pipeline` and contains an EM dash. It is already on
    the generated `outputs/live/screens/**` screens (4 each, measured) and
    `tests/test_operator_screen.py` asserts those screens contain
    `status_ko` **verbatim** — so changing the constant would desync committed
    screens from the code that produced them.

    The console cannot show it as it stands: the PHASE-21 dash gate bans EM/EN
    dashes in visible text, and the reason it bans them is that the subset font
    shipped under `web/assets/fonts/` has no glyph, so the character would
    render as tofu on the one screen a judge reads.

    So the CONTENT stays single-sourced and only the punctuation is normalised
    here, on the way to this screen. A test asserts the load-bearing facts
    (919 km², 3,926 km², 6곳) survive the substitution and that rule 11's banned
    phrasing never appears.
    """
    for bad, good in _BANNED_DASHES.items():
        text = text.replace(f" {bad} ", good).replace(bad, good.strip())
    return text


def build_region_payload(run_dir: Path) -> dict:
    viz = json.loads((run_dir / "viz.json").read_text(encoding="utf-8"))
    man = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    run = json.loads((run_dir / "RUN.json").read_text(encoding="utf-8"))

    npz = REPO / viz["hazard"]["npz_path"]
    bands, _hmeta = quantise(npz)
    xmin, ymin, xmax, ymax = viz["hazard"]["grid_extent_5179"]
    cell = viz["hazard"]["cell_size_m"]

    from pyproj import Transformer

    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    w, s, e, n = _walk_bbox(viz["region"])
    bx0, by0 = to5179.transform(w, s)
    bx1, by1 = to5179.transform(e, n)
    ign_lon, ign_lat = viz["field_core_lonlat"]
    ix, iy = to5179.transform(ign_lon, ign_lat)

    # Same ordering rule the A4 sheet uses: most urgent first, unknowns last.
    rows = sorted(viz["actionable"],
                  key=lambda p: (p["closing_window_min"] is None,
                                 p["closing_window_min"] if
                                 p["closing_window_min"] is not None else 1e9))

    t = run["timings_s"]
    warm = t.get("warm_total_s")

    # ⚠ THE UNCLICKED START MUST BE ONE THE GATE WILL ACCEPT, AND FOR YEONGDEOK
    # IT IS NOT. The field's t=0 core is the right anchor for APPLICABILITY (the
    # 15 km radius that decides whether a detection is in scope) and it is not
    # necessarily inside the WALK BBOX, which is what routing is gated on. Those
    # are two different questions and for `yeongdeok_2025` they disagree: the
    # core sits 2,472 m west of the bbox, so a run from it was refused 422 by
    # `POST /api/jobs` every time, and the screen showed only the status code.
    #
    # So the verdict is computed HERE, at build time, by the service's own
    # `check_in_region` — the same function the API gates on, never a second
    # copy of the bbox test — and the screen is built knowing the answer instead
    # of discovering it when somebody presses the button.
    default_start = _default_start(viz["region"], ign_lat, ign_lon)

    region = viz["region"]
    responder = dict(viz["responder_side"])
    # ⚠ Displayed, so it goes through the dash normaliser. Content unchanged.
    responder["status_ko"] = _dash_safe(responder.get("status_ko", ""))

    return {
        "region": region,
        # The Korean name a switcher button shows. From the committed
        # comparison table (`label_kr`), never typed here.
        "label_kr": _label_kr(region),
        "grid": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                 "cell": cell,
                 "nrows": viz["hazard"]["nrows"], "ncols": viz["hazard"]["ncols"]},
        "bands": bands[-1],                 # final slice: the whole envelope
        "origins": viz["origins"],
        "routes": viz["routes"][:1],        # one pair, drawn not asserted
        "refuges": viz["refuges"],
        "responder": responder,
        "ignition": [round(ix, 1), round(iy, 1)],
        "walk_bbox": [round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)],
        "counts": viz["counts"],
        "rows": [{"label": r.get("label"), "bucket": r["bucket"],
                  "closing": r["closing_window_min"], "walk": r.get("walk_time_min"),
                  "x": r["x"], "y": r["y"]} for r in rows],
        "n_villages": man["n_villages"], "n_points": man["n_points"],
        # -- the honesty items, all read from the run or the committed table --
        "honesty": {
            "weather": viz["scope"]["weather_basis"],
            "weather_line": viz["scope"]["weather_line_ko"],
            "coverage_pct": _coverage_pct(region),
            "coverage_note": "보행망 커버리지",
            # The constraint a map click must not be allowed to hide. Composed
            # from the region name so it cannot claim the wrong region.
            "hazard_fixed": (
                f"⚠ 위험면은 {region}의 사전 계산 결과이며 클릭·사진 좌표로 "
                "재생성되지 않습니다. 발화점 지정은 라우팅 출발점만 바꿉니다."),
        },
        # The coordinate a live run would use when nothing has been clicked,
        # WITH the gate's verdict on it. `servable` false means the button must
        # not offer a run that cannot happen.
        "default_start": default_start,
        "precomputed": {
            "run_id": run["run_id"],
            "warm_total_s": warm,
            "route_s": t.get("route_s"),
            "hazard_sha256": viz["hazard"]["npz_sha256"][:16],
        },
    }


def _label_kr(region: str) -> str:
    path = REPO / "data" / "processed" / "multi_region_comparison.json"
    for row in json.loads(path.read_text(encoding="utf-8"))["regions"]:
        if row["region"] == region:
            return row["label_kr"]
    return region


def build_payload(regions: list[str], run_dirs: dict[str, Path]) -> dict:
    """All regions in ONE payload, with everything shared hoisted out.

    ⚠ THREE REGIONS INLINE, ONE FILE. The alternative — a per-region API fetch —
    was measured and rejected: on localhost a round trip is 0.42~0.73 ms and the
    inline cost is ~64 KiB, so neither size nor latency decides it. What decides
    it is that a fetching console would have to read a replay run directory AT
    RUNTIME, and a replay run directory is precisely the thing that went missing
    in §1.12 of `docs/api_layer.md`. It would also break the property that this
    file opens and works with nothing else present.

    Buckets, band labels, band fills, the standing footer line, the photo
    privacy statement and MAX_ROWS are the SAME for every region, so they are
    stored once rather than three times.
    """
    return {
        "default_region": regions[0],
        "region_order": list(regions),
        "regions": {r: build_region_payload(run_dirs[r]) for r in regions},
        # -- shared, stored once -------------------------------------------
        "band_labels": list(BAND_LABELS), "band_fills": list(BAND_FILLS),
        "buckets": list(BUCKETS),
        "max_rows": MAX_ROWS,
        # NOT typed. FOOTER_LINES[0] is the A4 sheet's constant.
        "standing": FOOTER_LINES[0],
        # NOT typed. `wildfireguardian.photo.PRIVACY_KO` is the one copy, the
        # same way `standing` is the A4 sheet's own constant. What happens to a
        # reported photograph must not be able to say one thing on the screen
        # and another in the documentation.
        "photo_privacy_ko": PHOTO_PRIVACY_KO,
    }


def shipped_payload(out: Path) -> dict | None:
    """The payload currently inside ``out``, or ``None`` if there is not one."""
    if not out.is_file():
        return None
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                  out.read_text(encoding="utf-8"), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def check_not_a_downgrade(payload: dict, out: Path, *, allow_older: bool) -> list[str]:
    """Refuse to overwrite a console with one built from OLDER runs.

    ⚠ THIS IS THE §1.12 GUARD, AND IT IS THE REASON THAT SECTION EXISTS.
    The run behind the previously shipped console was absent from the tree, so
    `newest_run()` would have happily picked a pre-PHASE-20 run and rebuilt the
    badge from 11.467 s to 29.051 s — no error, no warning, and a diff in one
    number that a presenter says aloud. Now the outgoing build is compared
    against the one already on disk, PER REGION, and a step backwards stops the
    build instead of shipping quietly.

    Two different complaints, and they are not the same:

    * **older run** — the run id about to be used sorts BEFORE the shipped one.
      Always a downgrade.
    * **missing provenance** — the shipped console names a run that is no longer
      on disk. Not a downgrade by itself, but it is exactly how the first one
      goes unnoticed, so it is reported.
    """
    problems: list[str] = []
    old = shipped_payload(out)
    for region, new_region in payload["regions"].items():
        new_pc = new_region["precomputed"]
        prev = ((old or {}).get("regions", {}).get(region) or {}).get("precomputed")
        if prev is None:
            continue                                   # new region, nothing to beat
        if str(new_pc["run_id"]) < str(prev["run_id"]):
            problems.append(
                f"{region}: about to build from {new_pc['run_id']} "
                f"(warm {new_pc['warm_total_s']} s) but the shipped console "
                f"was built from the NEWER {prev['run_id']} "
                f"(warm {prev['warm_total_s']} s)")
        if not _run_dir_exists(str(prev["run_id"])):
            problems.append(
                f"{region}: the shipped console names run {prev['run_id']}, "
                "which is not on disk. Its badge cannot be reproduced "
                "(docs/api_layer.md §1.12)")
    if problems and allow_older:
        for p in problems:
            print(f"  ⚠ ALLOWED BY --allow-older: {p}")
        return []
    return problems


def _run_dir_exists(run_id: str) -> bool:
    base = REPO / "outputs" / "live" / "replay"
    return any(p.is_dir() for p in
               (list(base.glob(run_id)) + list(base.glob(f"*/{run_id}"))))


def _walk_bbox(region: str):
    from wildfireguardian.service.params import walk_bbox
    return walk_bbox(region)


def _default_start(region: str, lat: float, lon: float) -> dict:
    """The unclicked start, and whether the routing gate will accept it.

    ⚠ ONE DEFINITION OF THE GATE. ``check_in_region`` is the function
    ``POST /api/jobs`` refuses on; asking it here means the screen and the
    server cannot disagree about which coordinates are servable. Re-testing the
    bbox in JavaScript would be a second copy, and a second copy is a thing that
    can drift.

    When the answer is no, the distance is MEASURED (geodesic, to the nearest
    point of the bbox) rather than described, so the screen can say how far
    outside the point is instead of only that it is outside.
    """
    from pyproj import Geod

    from wildfireguardian.service.params import check_in_region

    verdict = check_in_region(region, lat, lon)
    w, s, e, n = verdict["bbox_wsen"]
    out: dict = {
        "latlon": [round(lat, 4), round(lon, 4)],
        "servable": bool(verdict["inside_registered_region"]),
        "reason_ko": verdict["reason_ko"],
        "offset_m": None,
        "note_ko": "",
    }
    if out["servable"]:
        return out

    near_lon = min(max(lon, w), e)
    near_lat = min(max(lat, s), n)
    _az1, _az2, dist = Geod(ellps="WGS84").inv(lon, lat, near_lon, near_lat)
    out["offset_m"] = round(float(dist))
    # Composed here, from the service's own sentence plus what to do instead.
    # A refusal an operator cannot act on is only half an answer, and this one
    # has an action: the dashed rectangle on the map is exactly the servable set.
    out["note_ko"] = (
        f"발화점(위험면 t=0 핵심)이 보행망 범위에서 {out['offset_m']:,} m "
        "벗어나 있어 이 좌표로는 라이브 계산을 실행할 수 없습니다. "
        "지도의 점선(보행망 범위) 안을 클릭해 출발점을 지정하십시오. "
        + verdict["reason_ko"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "web" / "console.html")
    ap.add_argument("--regions", nargs="*", default=None,
                    help="default: every region with a registered walk bbox")
    ap.add_argument("--run-dir", type=Path, action="append", default=None,
                    help="pin one region's run; repeatable. Default: the newest "
                         "replay run whose viz.json names that region")
    ap.add_argument("--allow-older", action="store_true",
                    help="build even if a run is OLDER than the shipped one. "
                         "The downgrade is printed either way.")
    args = ap.parse_args()

    from wildfireguardian.service.params import known_regions
    regions = list(args.regions) if args.regions else list(known_regions())

    pinned = {}
    for d in (args.run_dir or []):
        viz = json.loads((d / "viz.json").read_text(encoding="utf-8"))
        pinned[viz["region"]] = d
    run_dirs = {r: pinned.get(r) or newest_run(r) for r in regions}

    payload = build_payload(regions, run_dirs)

    problems = check_not_a_downgrade(payload, args.out, allow_older=args.allow_older)
    if problems:
        print("REFUSED: this build would ship an older result than the one "
              "already on disk.\n")
        for p in problems:
            print(f"  ⚠ {p}")
        print("\n  Rebuild the run, or pass --allow-older to accept the "
              "downgrade deliberately.")
        return 5

    tpl = (REPO / "scripts" / "console.template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False,
                                                  separators=(",", ":")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    for region in regions:
        p = payload["regions"][region]
        c, ds, pc = p["counts"], p["default_start"], p["precomputed"]
        rel = run_dirs[region].resolve()
        rel = rel.relative_to(REPO) if rel.is_relative_to(REPO) else rel
        print(f"  {p['label_kr']}  ({region})")
        print(f"    run       : {rel}")
        print(f"    counts    : {c['both_safe']} / {c['naive_into_FA_safe']} / "
              f"{c['no_safe_route']}   warm {pc['warm_total_s']} s")
        print(f"    커버리지  : {p['honesty']['coverage_pct']} %   "
              f"기상 {p['honesty']['weather']}")
        print(f"    출동 목록 : {len(p['rows'])}행 · 마을 {p['n_villages']}곳"
              + ("" if p["responder"]["available"] else
                 f"   차고지 0곳 → 구조자 측 산출 불가 표시"))
        print("    기본 출발점: "
              + ("게이트 통과" if ds["servable"] else
                 f"게이트 거절 · 보행망 범위에서 {ds['offset_m']:,} m 밖 "
                 "→ 클릭 전 버튼 비활성"))
    size = args.out.stat().st_size / 1024
    print(f"\n  -> {args.out.resolve().relative_to(REPO)}  "
          f"({size:.1f} KiB, {len(regions)} regions inline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
