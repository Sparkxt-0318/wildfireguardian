#!/usr/bin/env python
"""Generate the three operational outputs from a committed rescue result.

Round-3 PHASE 3.

INPUT IS THE COMMITTED ARTIFACT, UNCHANGED
------------------------------------------
Reads ``data/processed/rescue_routing.json`` — the 600-minute-budget result —
and never re-runs the pipeline or recomputes a number. The purpose here is to
demonstrate the OUTPUT FORMATS, not to publish current figures. In particular
the PHASE 2-C-2 budget sweep is deliberately NOT used: mixing a 30-minute w(t)
into a sheet built from a 600-minute run would produce a document whose numbers
came from two different assumptions.

The committed artifact carries the full 24-point unreachable list but only the
top 20 of its 143 dispatch points, so the sheets cover 44 points. That is a
property of what was committed, not a sampling decision made here, and it is
stated on every sheet and in the manifest.

NOTHING IS SENT. Files are written; ``sms.send`` is never called.

Run:  python scripts/generate_dispatch_outputs.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.delivery import broadcast, printable, sms  # noqa: E402
from wildfireguardian.delivery.villages import (  # noqa: E402
    _bearing_word, cluster_points, named_refuges,
)

SRC = REPO / "data" / "processed" / "rescue_routing.json"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _nearest_named(x: float, y: float, refuges: list[dict]) -> tuple[str, float]:
    best, bd = None, float("inf")
    for r in refuges:
        d = ((r["x"] - x) ** 2 + (r["y"] - y) ** 2) ** 0.5
        if d < bd:
            best, bd = r, d
    return (best["name"].strip() if best else "미상"), bd


def _place_label(x: float, y: float, refuges: list[dict]) -> str:
    """A coordinate-free label an operator can actually navigate by.

    Distance alone is ambiguous: two different points 151 m from the same park
    produce identical rows, and a 이장 cannot tell which is which. Adding the
    bearing makes each row locatable without ever printing a coordinate.
    """
    best, bd = None, float("inf")
    for r in refuges:
        d = ((r["x"] - x) ** 2 + (r["y"] - y) ** 2) ** 0.5
        if d < bd:
            best, bd = r, d
    if best is None:
        return "위치 미상"
    word = _bearing_word(x - best["x"], y - best["y"])
    return f"{best['name'].strip()} {word}쪽 {int(round(bd))}m"


def build_points_full(data: dict) -> list[dict]:
    """EVERY origin needing rescue, from the full-coverage re-run.

    The full artifact serialises all 441 origins with their four-way class, so
    no top-N slice is involved: this returns all 142 dispatch + 32 unreachable
    points rather than the committed artifact's 20 + 24.
    """
    refuges = named_refuges(data["destinations"])
    pts: list[dict] = []
    for r in data["origins_full"]:
        cls = r["four_way_class"]
        if cls not in ("no_safe_pedestrian_route", "no_surviving_vehicle_ingress"):
            continue
        unreachable = cls == "no_surviving_vehicle_ingress"
        pt = {
            "x": r["x_5179"], "y": r["y_5179"], "unreachable": unreachable,
            "home_node": r["origin_walk_node"],
            "label": _place_label(r["x_5179"], r["y_5179"], refuges),
        }
        if unreachable:
            pt["closing_window_min"] = r.get("best_closing_window_min")
            pt["reason_ko"] = "예산 내 차량 진입로가 화재로 차단됨(우회 포함)"
        else:
            pt["closing_window_min"] = r.get("closing_window_min")
            pt["responder_eta_min"] = r.get("responder_eta_min")
            pt["route_note"] = ("차량 진입 가능 — 생존 인지 경로"
                                if not r.get("shortest_path_enters_hazard")
                                else "최단 경로는 화재 통과 — 우회 경로 필요")
        pts.append(pt)
    return pts


def build_points(data: dict) -> list[dict]:
    """Committed dispatch + unreachable points, labelled by nearby place name."""
    refuges = named_refuges(data["destinations"])
    pts: list[dict] = []
    for p in data["dispatch_top20"]:
        pts.append({
            "x": p["x"], "y": p["y"], "unreachable": False,
            "home_node": p["home_node"],
            "closing_window_min": p.get("closing_window_min"),
            "responder_eta_min": p.get("responder_eta_min"),
            "label": _place_label(p["x"], p["y"], refuges),
            "route_note": ("차량 진입 가능 — 생존 인지 경로"
                           if not p.get("shortest_path_enters_hazard")
                           else "최단 경로는 화재 통과 — 우회 경로 필요"),
        })
    for p in data["unreachable_homes"]:
        pts.append({
            "x": p["x"], "y": p["y"], "unreachable": True,
            "home_node": p["home_node"],
            "closing_window_min": p.get("best_closing_window_min"),
            "label": _place_label(p["x"], p["y"], refuges),
            "reason_ko": "예산 내 차량 진입로가 화재로 차단됨(우회 포함)",
        })
    return pts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(SRC))
    ap.add_argument("--out-root", default=str(REPO / "outputs" / "dispatch"))
    ap.add_argument("--eps-m", type=float, default=500.0)
    ap.add_argument("--full", action="store_true",
                    help="read a full-coverage artifact (origins_full) instead "
                         "of the committed dispatch_top20 slice")
    args = ap.parse_args()
    if args.full and args.source == str(SRC):
        args.source = str(REPO / "data" / "processed" / "rescue_routing_full.json")
        if args.out_root == str(REPO / "outputs" / "dispatch"):
            args.out_root = str(REPO / "outputs" / "dispatch_full")

    src = Path(args.source)
    if not src.exists():
        print(f"STOP: missing {src}", file=sys.stderr)
        return 2
    data = json.loads(src.read_text(encoding="utf-8"))

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    commit, cfg_hash = _git(), config_hash()
    out_root = Path(args.out_root) / stamp
    out_root.mkdir(parents=True, exist_ok=True)

    full = "origins_full" in data
    pts = build_points_full(data) if full else build_points(data)
    extra_label = data.get("label_ko") if full else None
    villages = cluster_points(pts, data["destinations"], eps_m=args.eps_m)
    refuges = named_refuges(data["destinations"])
    safe_refuges = [r for r in refuges if r.get("rescue_reachable")]

    print(f"source   : {src.relative_to(REPO)} (600-min budget, NOT re-run)")
    if full:
        print(f"points   : {len(pts)}  (FULL COVERAGE — every origin needing "
              f"rescue: {data['four_way_counts']['no_safe_pedestrian_route']} "
              f"dispatch + "
              f"{data['four_way_counts']['no_surviving_vehicle_ingress']} "
              "unreachable)")
    else:
        print(f"points   : {len(pts)}  "
              f"({data['responder_exposure']['n_dispatch']} dispatch in the run, "
              f"top {len(data['dispatch_top20'])} committed; "
              f"{len(data['unreachable_homes'])} unreachable, all committed)")
    print(f"clusters : {len(villages)} (DBSCAN eps={args.eps_m:g} m — "
          f"spatial, NOT 행정리)\n")

    manifest = {
        "schema_version": 1,
        "generated_utc": stamp, "git_commit": commit, "config_hash": cfg_hash,
        "source_file": str(src.relative_to(REPO)),
        "source_budget_min": 600.0,
        "source_note": "committed artifact; not re-run, no number recomputed",
        "coverage_note": (
            f"FULL COVERAGE: all {len(pts)} origins needing rescue are covered "
            f"({data['four_way_counts']['no_safe_pedestrian_route']} dispatch + "
            f"{data['four_way_counts']['no_surviving_vehicle_ingress']} "
            "unreachable), serialized from origins_full."
            if full else
            f"The committed artifact carries all "
            f"{len(data['unreachable_homes'])} unreachable points but only the "
            f"top {len(data['dispatch_top20'])} of its "
            f"{data['responder_exposure']['n_dispatch']} dispatch points, so "
            f"these sheets cover {len(pts)} points."),
        "label_ko": extra_label,
        "is_full_coverage": full,
        "clustering": {"algorithm": "DBSCAN", "eps_m": args.eps_m,
                       "min_samples": 1,
                       "is_administrative_village": False,
                       "note": "행정리가 아닌 공간 군집"},
        "sms_demo_mode": sms.demo_mode(),
        "sms_credentials_present": sms.credentials_present(),
        "nothing_was_sent": True,
        "villages": [],
    }

    for v in villages:
        vdir = out_root / v.slug()
        vdir.mkdir(parents=True, exist_ok=True)
        cx, cy = v.centroid
        refuge_name, _ = _nearest_named(cx, cy, safe_refuges or refuges)

        # (1) A4 printable — HTML then PDF
        h = printable.render_html(
            v, generated_at=generated_at, git_commit=commit,
            config_hash=cfg_hash, source_file=str(src.relative_to(REPO)),
            n_total_dispatch=data["responder_exposure"]["n_dispatch"],
            n_total_unreachable=len(data["unreachable_homes"]),
            extra_label=extra_label)
        hp = vdir / "dispatch_a4.html"
        hp.write_text(h, encoding="utf-8")
        pdf = printable.html_to_pdf(hp, vdir / "dispatch_a4.pdf")

        # (2) Broadcast script
        soonest = min((p["closing_window_min"] for p in v.points
                       if p.get("closing_window_min") is not None), default=None)
        bc = broadcast.compose(v.name, refuge=refuge_name,
                               n_unreachable=v.n_unreachable)
        (vdir / "broadcast_script.txt").write_text(bc.text + "\n", encoding="utf-8")

        # (3) SMS drafts — composed and written, NEVER sent
        msgs = [sms.compose_family(v.name, v.n_points, v.n_unreachable,
                                   refuge=refuge_name),
                sms.compose_welfare(v.name, v.n_points, v.n_unreachable,
                                    soonest_min=soonest)]
        (vdir / "sms_drafts.json").write_text(
            json.dumps({"village": v.name,
                        "demo_mode": sms.demo_mode(),
                        "sent": False,
                        "note": "drafts only; sms.send() was never called and "
                                "requires an approval_token",
                        "messages": [m.as_dict() for m in msgs]},
                       indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (vdir / "sms_drafts.txt").write_text(
            "\n\n".join(f"[{m.recipient_role}] ({m.n_chars}자)\n{m.body}"
                        for m in msgs) + "\n", encoding="utf-8")

        entry = v.as_dict()
        entry.update({
            "directory": str(vdir.relative_to(REPO)),
            "refuge_used_in_messages": refuge_name,
            "pdf": pdf,
            "broadcast_check": bc.check(),
            "sms": [m.as_dict() for m in msgs],
        })
        manifest["villages"].append(entry)

        pg = pdf.get("n_pages")
        ok_sms = all(m.within_limit for m in msgs)
        print(f"  {v.slug():34s} pts={v.n_points:2d} "
              f"(출동 {v.n_dispatch:2d} / 불가 {v.n_unreachable:2d})  "
              f"PDF {'p' + str(pg) if pg else 'FAILED':>4s}  "
              f"방송 {'OK' if bc.check()['ok'] else 'OVER'}  "
              f"SMS {'OK' if ok_sms else 'OVER'}")

    (out_root / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    pdfs = [v["pdf"] for v in manifest["villages"]]
    n_ok = sum(1 for p in pdfs if p.get("ok"))
    multi = [v["name"] for v in manifest["villages"]
             if (v["pdf"].get("n_pages") or 1) > 1]
    print(f"\nPDF: {n_ok}/{len(pdfs)} generated"
          + (f"  ⚠ MULTI-PAGE: {multi}" if multi else "  (all single-page)"))
    print(f"SMS: DEMO_MODE={sms.demo_mode()}  credentials="
          f"{sms.credentials_present()}  nothing sent")
    print(f"wrote {out_root.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
