#!/usr/bin/env python
"""Manual ignition-point trigger: a coordinate someone reported, routed at once.

Round-3 PHASE 12.

WHY THIS EXISTS
---------------
The pipeline reacted only to FIRMS. But in real operation a wildfire's location
arrives from a **119 call, a watch-tower, or a CCTV operator** long before a
satellite sees it: VIIRS revisits roughly every 12 hours and FIRMS NRT publishes
within about three hours of the overpass, so waiting for a detection can cost
hours that a phone call did not. There is no reason to wait.

This is not a replacement. **Both triggers coexist** — `run_live_detection.py`
still polls FIRMS and still replays — and they converge on the same routing.

IDENTICAL DOWNSTREAM, BY CONSTRUCTION
-------------------------------------
This script does not reimplement the pipeline. It builds a one-point trigger and
hands it to ``run_live_detection.run_trigger`` — the same function the FIRMS and
replay branches call. The routing, the classification, the clustering and the
three delivery formats are therefore the same code, not merely the same idea,
and the outputs are structurally identical. Only the recorded SOURCE differs:

    trigger_source: "manual" | "firms_nrt" | "replay"

⚠ THE TRIGGER TIME MEANS SOMETHING DIFFERENT HERE
For FIRMS and replay, the trigger time is a **satellite overpass** — when an
instrument observed a fire. For a manual trigger it is when the **coordinate was
entered** — when a person reported one. Those are not the same kind of fact and
the screen, the console and every artifact say which they are showing.

WHAT IT DOES NOT DO
-------------------
* No address or 지번 lookup — out of scope. Latitude and longitude only.
* It does NOT re-simulate the hazard surface. The surface is pre-computed and
  fixed (ERA5 publishes on a ~5-day lag); a manual report decides *whether* and
  *where* to act, exactly as a detection does.

Run:
    python scripts/run_manual_trigger.py --lat 36.44 --lon 129.37
    python scripts/run_manual_trigger.py --lat 36.36 --lon 128.62 \
        --region uiseong_andong_2025 \
        --npz data/processed/hazard_uiseong_andong_2025.npz
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import get as _cfg  # noqa: E402
from wildfireguardian.delivery import sms  # noqa: E402
from wildfireguardian.live import firms, pipeline  # noqa: E402
from wildfireguardian.live.scope import Scope  # noqa: E402

# The SAME trigger path the FIRMS and replay branches use. Imported, never
# copied: a second implementation could drift, and "identical to the FIRMS
# route" is the property this phase is supposed to deliver.
from run_live_detection import banner, load_dotenv, run_trigger  # noqa: E402
from run_multi_region_routing import PROTECTED, protected_digests  # noqa: E402

EXIT_OUT_OF_REGION = 3
EXIT_PROTECTED_MOVED = 4


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True,
                    help="ignition latitude, WGS84 decimal degrees")
    ap.add_argument("--lon", type=float, required=True,
                    help="ignition longitude, WGS84 decimal degrees")
    ap.add_argument("--reported-by", default="수동 입력",
                    help="who reported it (119 신고 / 감시원 / CCTV). Recorded "
                         "verbatim; no personal data belongs here.")
    ap.add_argument("--region", default=str(_cfg("live.region", "yeongdeok_2025")))
    ap.add_argument("--npz", default=None,
                    help="pre-computed hazard field (default: this region's)")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--applicability-radius-km", type=float,
                    default=float(_cfg("live.trigger.field_applicability_radius_km", 15.0)))
    ap.add_argument("--p-cut", type=float,
                    default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-budget-min", type=float,
                    default=float(_cfg("pedestrian.walk_budget_min", 600.0)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(_cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--stride", type=int,
                    default=int(_cfg("origin_scan.real_osm_stride", 18)))
    ap.add_argument("--eps-m", type=float, default=500.0)
    ap.add_argument("--collect-routes", type=int, default=12)
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--limit-origins", type=int, default=0,
                    help="SMOKE TEST ONLY: truncate the origin list")
    args = ap.parse_args()

    # The clock starts the instant the operator's coordinate is in hand. This is
    # the number the phase exists to measure: report -> dispatch list.
    t_input = time.monotonic()
    entered_utc = datetime.now(UTC)

    load_dotenv(REPO / ".env")
    if args.npz is None:
        args.npz = str(REPO / (
            _cfg("live.hazard_npz", "data/processed/routing_demo_canonical.npz")
            if args.region == "yeongdeok_2025"
            else f"data/processed/hazard_{args.region}.npz"))
    if args.out_root is None:
        args.out_root = str(REPO / _cfg("live.output_root", "outputs/live")
                            / "manual" / args.region)

    before = protected_digests()
    if any(v is None for v in before.values()):
        print("STOP: a protected artifact is missing.", file=sys.stderr)
        return 2

    npz = Path(args.npz)
    if not npz.exists():
        print(f"STOP: {npz} missing.", file=sys.stderr)
        return 2
    if npz.name == "routing_demo.npz":
        print("STOP: routing_demo.npz is the output of a REVERTED run and must "
              "not be consumed in new work (HANDOFF_ROUND3.md §2-A).",
              file=sys.stderr)
        return 2

    # ---- is the coordinate inside the registered region? -------------------
    bbox = tuple((_cfg("bbox.multi_region_walk_bbox", {}) or {})[args.region])
    w, s, e, n = bbox
    inside = (w <= args.lon <= e) and (s <= args.lat <= n)
    print("=" * 74)
    print(f"  수동 발화점 입력 — {args.reported_by}")
    print("=" * 74)
    print(f"  좌표        : {args.lat:.5f}, {args.lon:.5f}")
    print(f"  입력 시각   : {entered_utc:%Y-%m-%d %H:%M:%S UTC}"
          "   ← 좌표 입력 시각 (위성 통과 시각 아님)")
    print(f"  등록 지역   : {args.region}  bbox {bbox}")
    if not inside:
        print(f"\nSTOP (exit {EXIT_OUT_OF_REGION}): 좌표가 등록 지역 bbox 밖입니다.\n"
              "  이 지역의 보행망·대피소·위험면은 이 범위에 대해서만 준비되어 "
              "있으므로,\n  범위 밖 좌표로 산출하면 없는 근거를 만들어내는 것이 "
              "됩니다.", file=sys.stderr)
        return EXIT_OUT_OF_REGION
    print("  범위 검사   : 통과 (등록 지역 안)\n")

    # ---- the pre-computed surface, network and refuges ----------------------
    basis, basis_meta = pipeline.weather_basis(args.region, repo=REPO)
    scope = Scope(mode="manual", weather_basis=basis,
                  hazard_field=str(npz.relative_to(REPO)), region=args.region,
                  trigger_source="manual",
                  trigger_at=entered_utc.strftime("%Y-%m-%d %H:%M UTC"))
    print(banner(scope))

    print("\n  [0/2] 사전 계산 위험면·스냅샷 도로망·대피 POI 적재 ...", flush=True)
    res = pipeline.load_resources(args.region, npz_path=npz, repo=REPO)
    print(f"        위험면 {res.haz.shape} sha256 {res.npz_sha256[:16]}...")
    print(f"        보행망 {res.net.graph.number_of_nodes():,} 노드 / "
          f"{res.net.graph.number_of_edges():,} 간선")
    print(f"        대피 POI {res.n_shelter_pois}곳 → 노드 {len(res.net.shelters)}개")
    load_s = (res.timings.load_hazard_s + res.timings.load_network_s
              + res.timings.load_pois_s)
    print(f"        적재 소요 {load_s:.1f}s\n")

    # ---- the reported point, as a one-element trigger ----------------------
    # Typed as a Hotspot so the downstream path cannot tell the difference and
    # therefore cannot behave differently. `source` records what it really is.
    point = firms.Hotspot(
        lat=args.lat, lon=args.lon, acquired_utc=entered_utc,
        source=f"manual:{args.reported_by}", satellite="", instrument="manual",
        confidence_raw="high", frp=None, daynight="")

    params = {
        "p_cut": args.p_cut, "time_budget_min": args.time_budget_min,
        "time_step_min": args.time_step_min, "origin_scan_stride": args.stride,
        "eps_m": args.eps_m, "routing_objective": "length_m (distance-ranked)",
        "weather_basis": basis_meta,
        "source": "config/default.yaml — identical to the FIRMS path",
    }
    meta = {
        "kind": "manual",
        "reported_by": args.reported_by,
        "entered_utc": entered_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entered_utc_meaning": "when the coordinate was entered by an operator; "
                               "NOT a satellite overpass time",
        "input_lat": args.lat, "input_lon": args.lon,
        "region_bbox_wsen": list(bbox), "inside_registered_region": True,
        "hazard_field": str(npz.relative_to(REPO)),
        "hazard_field_sha256": res.npz_sha256,
        "hazard_weather_basis": basis,
        "hazard_weather_basis_utc": basis_meta["basis_utc"],
        "no_geocoding": "latitude/longitude only; address and 지번 lookup are "
                        "out of scope for this phase",
    }
    notes = [
        "MANUAL TRIGGER. The ignition point was reported, not detected. The "
        "trigger time is when the coordinate was entered, not a satellite "
        "overpass.",
        "The hazard surface is the SAME pre-computed field the FIRMS path uses "
        "and was not re-simulated: ERA5 publishes on a ~5-day lag.",
    ]

    summary = run_trigger(res, scope, point, [point], meta, args, params, notes,
                          all_hotspots=[point])

    # PDF conversion is excluded, for the same reason it is excluded
    # everywhere else: it runs AFTER the dispatch list already exists in every
    # text format, and it scales with the number of villages rather than with
    # the decision. Including it would answer "how long to print 29 sheets?"
    # when the question is "how long from a 119 call to a dispatch list?".
    pdf_s = summary["timings"]["pdf_s"]
    total_s = (time.monotonic() - t_input) - pdf_s
    out_dir = Path(summary["out_dir"])
    rec = json.loads((out_dir / "RUN.json").read_text(encoding="utf-8"))
    rec["manual_trigger"] = {
        **meta,
        "input_to_dispatch_list_s": round(total_s, 3),
        "input_to_dispatch_list_excludes_pdf_s": round(pdf_s, 3),
        "input_to_dispatch_list_note": (
            "wall clock from the coordinate being in hand to the dispatch list "
            "existing in every text format. Includes loading the field, the "
            "graph and the POIs, which a running service does once at "
            "start-up; the warm figure is in timings_s. EXCLUDES A4 PDF "
            "conversion, which runs after the list already exists."),
    }
    (out_dir / "RUN.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    after = protected_digests()
    changed = [k for k in before if before[k] != after[k]]
    if changed:
        print(f"\nSTOP (exit {EXIT_PROTECTED_MOVED}): protected artifact(s) "
              f"changed: {changed}", file=sys.stderr)
        return EXIT_PROTECTED_MOVED

    t = summary["timings"]
    print("=" * 74)
    print(f"좌표 입력 → 출동 목록 : {total_s:.1f}s  (cold, 적재 포함, PDF 제외)")
    print(f"  그중 라우팅        : {t['route_s']:.1f}s")
    print(f"  그중 전달물 생성    : {t['render_s']:.2f}s"
          + (f"  + A4 PDF {t['pdf_s']:.0f}s (목록 확정 이후)"
             if t["pdf_s"] else ""))
    print(f"  warm (적재 제외)   : {t['warm_total_s']:.1f}s "
          "— 상시 구동 서비스가 보이는 값")
    print(f"트리거 출처          : {summary['trigger_source']} "
          "(FIRMS 경로와 동일한 라우팅, 출처만 다름)")
    print(f"보호 산출물 {len(PROTECTED)}개 무변경 확인")
    print(f"SMS: DEMO_MODE={sms.demo_mode()} — 발송된 메시지 없음")
    print(f"기록: {out_dir.relative_to(REPO)}/RUN.json")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
