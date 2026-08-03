#!/usr/bin/env python
"""Unattended live-detection pipeline: FIRMS NRT -> routing -> dispatch outputs.

Round-3 PHASE 6.

    ⚠ SCOPE. This is REAL-TIME DETECTION over a PRE-COMPUTED risk surface. It is
      not real-time forecasting. FIRMS NRT publishes hotspots within about three
      hours of overpass; ERA5 reanalysis publishes on an approximately five-day
      lag, so no hazard field exists for today. The field routed on was
      simulated once, from the weather of the fire it was built for, and is held
      fixed. Every screen and every artifact says so.

TWO BRANCHES
------------
``--replay``  OFFLINE. Replays a past fire's committed hotspot record in time
              order at a speed multiplier (default 60x — twelve hours in twelve
              minutes). No network, no credentials, no FIRMS client is ever
              constructed. **This is the demonstration path**: a live demo
              depends on a working network, an overpass inside the demo window,
              and an actual fire, and at least one of those will fail.

(default)     LIVE. Polls FIRMS NRT for the registered region's bbox every
              ``live.firms.poll_interval_min`` minutes (default 3 h), snapshots
              every acquisition immediately, and triggers on genuinely new
              hotspots.

NOTHING IS SENT. ``delivery.sms.send`` is never called; drafts are written to
disk. Sending requires a positional approval token and DEMO_MODE is on unless
the environment variable is exactly "0".

NO COMMITTED ARTIFACT IS TOUCHED. The protected digests are recorded before and
after every run and the process exits 4 if one moves.

Run:
    python scripts/run_live_detection.py --replay                 # 60x, 12 h
    python scripts/run_live_detection.py --replay --speed 720     # fast check
    python scripts/run_live_detection.py --once                   # one live poll
    python scripts/run_live_detection.py                          # poll forever
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import get as _cfg  # noqa: E402
from wildfireguardian.delivery import sms  # noqa: E402
from wildfireguardian.live import firms, pipeline, replay as replay_mod  # noqa: E402
from wildfireguardian.live.scope import Scope  # noqa: E402
from wildfireguardian.live.state import SeenState, StageTimings  # noqa: E402

from run_multi_region_routing import PROTECTED, protected_digests  # noqa: E402

EXIT_PROTECTED_MOVED = 4
EXIT_NO_CREDENTIALS = 6


def load_dotenv(path: Path) -> list[str]:
    """Read the git-ignored `.env` into the environment. Existing vars win.

    Values are never printed. The return value is the list of NAMES that were
    set, so a run can report which layers are configured without ever putting a
    secret into a log or an artifact.
    """
    names: list[str] = []
    if not path.exists():
        return names
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v
        if k and v:
            names.append(k)
    return names


def banner(scope: Scope, applicability: dict | None = None) -> str:
    bar = "=" * 74
    lines = [bar, f"  {scope.mode_banner()}", bar]
    for ln in scope.lines():
        lines.append(f"  {ln}")
    lines.append(f"  위험면      : {scope.hazard_field} (사전 계산, 고정)")
    lines.append(f"  등록 지역   : {scope.region}")
    if applicability:
        lines.append(f"  적용 범위   : {applicability['verdict']} "
                     f"({applicability['hotspot_to_field_core_km']:.1f} km)")
    lines.append(bar)
    return "\n".join(lines)


def snapshot_poll(poll: firms.PollResult, region: str, out_dir: Path) -> list[dict]:
    """Preserve an acquisition immediately, before anything is derived from it.

    `docs/HANDOFF_ROUND3.md` §5.8: never write acquired data only to a
    git-ignored cache. The raw CSV bodies are written into the run directory AND
    registered in the snapshot store, so the exact bytes that triggered a
    dispatch remain recoverable.
    """
    from snapshot_external import load_manifest, save_manifest, snapshot_one

    raw_dir = out_dir / "firms_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    man = load_manifest()
    entries: list[dict] = []
    for src, body in sorted(poll.raw_csv.items()):
        p = raw_dir / f"{src}.csv"
        p.write_text(body, encoding="utf-8")
        stored, created = snapshot_one(
            p, source=f"firms-nrt-{src.lower().replace('_', '-')}",
            region=region.replace("_", "-"),
            layer=f"FIRMS NRT area query, {src}", man=man,
            parameters={"bbox_wsen": list(poll.bbox_wsen),
                        "polled_utc": poll.polled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")})
        entries.append({"source": src, "stored_file": stored.name,
                        "newly_created": created,
                        "raw_path": str(p.relative_to(out_dir))})
    save_manifest(man)
    return entries


def run_trigger(res: pipeline.Resources, scope: Scope, trigger: firms.Hotspot,
                new: list[firms.Hotspot], poll_meta: dict, args, params: dict,
                notes: list[str]) -> dict:
    """One trigger: route, deliver, record. Returns a compact summary."""
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    applicability = pipeline.assess_applicability(
        trigger, res, float(args.applicability_radius_km))
    print(banner(scope, applicability))
    print(f"  트리거 화점 : {trigger.lat:.4f}, {trigger.lon:.4f}  "
          f"{trigger.acquired_utc:%Y-%m-%d %H:%M UTC}  "
          f"{trigger.source} conf={trigger.confidence}")
    if applicability["verdict"] != "IN_SCOPE":
        print(f"  ⚠ {applicability['statement_ko']}")

    print("  [1/2] 라우팅 (정본 위험면) ...", flush=True)
    counts, points, route_s = pipeline.route_region(
        res, p_cut=args.p_cut, budget_min=args.time_budget_min,
        step_min=args.time_step_min, stride=args.stride,
        limit_origins=args.limit_origins)
    n_scanned = sum(counts.values())
    print(f"        N={n_scanned}  both_safe={counts['both_safe']}  "
          f"FA_only={counts['naive_into_FA_safe']}  "
          f"no_safe={counts['no_safe_route']}  "
          f"budget={counts['fa_exceeds_budget']}   [{route_s:.1f}s]")

    print("  [2/2] 전달물 3종 생성 ...", flush=True)
    manifest, cluster_s, render_s, pdf_s = pipeline.deliver(
        points, res, out_dir, scope=scope, counts=counts,
        applicability=applicability, eps_m=args.eps_m,
        make_pdf=not args.no_pdf)
    print(f"        마을 {manifest['n_villages']}곳 · 지점 {manifest['n_points']}곳 "
          f"(안내 {manifest['n_dispatch']} / 도보 불가 {manifest['n_unreachable']})"
          f"   [{render_s:.2f}s]"
          + (f"  + A4 PDF 변환 {pdf_s:.0f}s (목록 확정 이후)" if pdf_s else ""))

    t = StageTimings(load_hazard_s=res.timings.load_hazard_s,
                     load_network_s=res.timings.load_network_s,
                     load_pois_s=res.timings.load_pois_s,
                     route_s=route_s, cluster_s=cluster_s, render_s=render_s,
                     pdf_s=pdf_s)
    rec = pipeline.build_run_record(
        run_id=run_id, started=started, scope=scope, res=res, trigger=trigger,
        new_hotspots=new, poll_meta=poll_meta, counts=counts,
        applicability=applicability, timings=t, manifest=manifest,
        out_dir=out_dir, params=params, notes=notes)
    rec.write(out_dir)

    print(f"  소요        : 탐지→목록 {t.warm_total_s:.1f}s (warm) / "
          f"{t.cold_total_s:.1f}s (cold, 적재 포함)"
          + (f" · PDF 포함 {t.warm_total_with_pdf_s:.0f}s" if t.pdf_s else ""))
    print(f"  기록        : {out_dir.relative_to(REPO)}/RUN.json")
    print(f"  SMS         : DEMO_MODE={sms.demo_mode()} "
          f"credentials={sms.credentials_present()} — 발송 없음\n")
    return {"run_id": run_id, "out_dir": str(out_dir), "counts": counts,
            "timings": t.as_dict(), "applicability": applicability,
            "n_villages": manifest["n_villages"]}


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay", action="store_true",
                    help="OFFLINE replay of a past fire's hotspot record. No "
                         "network, no credentials. The demonstration path.")
    ap.add_argument("--speed", type=float,
                    default=float(_cfg("live.replay.default_speed", 60.0)),
                    help="replay speed multiplier (60 = 12 h in 12 min); "
                         "0 = as fast as possible")
    ap.add_argument("--replay-hours", type=float,
                    default=float(_cfg("live.replay.default_window_h", 12.0)),
                    help="how many hours of the archive to replay")
    ap.add_argument("--replay-csv", default=None,
                    help="override the archive (default: this region's "
                         "committed detections CSV)")
    ap.add_argument("--once", action="store_true",
                    help="live mode: poll once and exit instead of looping")
    ap.add_argument("--region", default=str(_cfg("live.region", "yeongdeok_2025")))
    ap.add_argument("--npz", default=str(REPO / _cfg(
        "live.hazard_npz", "data/processed/routing_demo_canonical.npz")))
    ap.add_argument("--poll-interval-min", type=float,
                    default=float(_cfg("live.firms.poll_interval_min", 180.0)))
    ap.add_argument("--max-triggers", type=int, default=0,
                    help="stop after N triggered runs (0 = unlimited)")
    ap.add_argument("--retrigger-min-interval-min", type=float,
                    default=float(_cfg("live.trigger.retrigger_min_interval_min", 180.0)))
    ap.add_argument("--min-confidence",
                    default=str(_cfg("live.trigger.min_confidence", "nominal")))
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
    ap.add_argument("--no-pdf", action="store_true",
                    help="write the A4 sheet as HTML only (skip headless Chrome)")
    ap.add_argument("--limit-origins", type=int, default=0,
                    help="SMOKE TEST ONLY: truncate the origin list")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--state-file", default=None)
    ap.add_argument("--reset-state", action="store_true",
                    help="forget which hotspots have been seen before")
    args = ap.parse_args()

    env_names = load_dotenv(REPO / ".env")
    if args.out_root is None:
        args.out_root = str(REPO / _cfg("live.output_root", "outputs/live")
                            / ("replay" if args.replay else "live"))
    if args.state_file is None:
        args.state_file = str(Path(args.out_root) / f"state_{args.region}.json")

    before = protected_digests()
    if any(v is None for v in before.values()):
        print("STOP: a protected artifact is missing.", file=sys.stderr)
        return 2

    npz = Path(args.npz)
    if not npz.exists():
        print(f"STOP: {npz} missing — run scripts/build_canonical_hazard.py first.",
              file=sys.stderr)
        return 2
    if npz.name == "routing_demo.npz":
        print("STOP: routing_demo.npz is the output of a REVERTED run and must "
              "not be consumed in new work (HANDOFF_ROUND3.md §2-A). Use "
              "routing_demo_canonical.npz.", file=sys.stderr)
        return 2

    bbox = tuple((_cfg("bbox.multi_region_walk_bbox", {}) or {})[args.region])

    basis, basis_meta = pipeline.weather_basis(args.region, repo=REPO)
    scope = Scope(mode="replay" if args.replay else "live", weather_basis=basis,
                  hazard_field=str(npz.relative_to(REPO)), region=args.region)
    print(banner(scope))

    # -- credential report (names only; values are never printed) -------------
    twilio = [k for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                          "TWILIO_FROM_NUMBER") if os.environ.get(k)]
    notes: list[str] = []
    print(f"  .env        : {len(env_names)} 변수 로드 "
          f"({', '.join(sorted(set(env_names))) or '없음'})")
    print(f"  FIRMS 키    : {'있음' if firms.credentials_present() else '없음'}")
    if len(twilio) < 3:
        msg = ("Twilio credentials absent (%d/3): the SMS layer stays in "
               "DEMO_MODE and composes drafts only. Nothing could be sent even "
               "if the code tried." % len(twilio))
        notes.append(msg)
        print(f"  Twilio      : 없음 ({len(twilio)}/3) → SMS 계층 DEMO_MODE 유지, "
              f"초안만 생성")
    else:
        notes.append("Twilio credentials present, but this PHASE composes "
                     "drafts only; sms.send() is never called.")
        print("  Twilio      : 있음 — 그러나 이 단계는 초안 생성까지입니다")
    if args.limit_origins:
        notes.append(f"SMOKE TEST: origin list truncated to {args.limit_origins}. "
                     "Not a reportable result.")

    state_path = Path(args.state_file)
    if args.reset_state and state_path.exists():
        state_path.unlink()
    seen = SeenState.load(state_path, args.region)

    params = {"p_cut": args.p_cut, "time_budget_min": args.time_budget_min,
              "time_step_min": args.time_step_min,
              "origin_scan_stride": args.stride, "eps_m": args.eps_m,
              "routing_objective": "length_m (distance-ranked)",
              "min_confidence": args.min_confidence,
              "retrigger_min_interval_min": args.retrigger_min_interval_min,
              "weather_basis": basis_meta,
              "source": "config/default.yaml — identical to the 459-series runs"}
    min_rank = firms.confidence_rank(args.min_confidence)

    print("\n  [0/2] 사전 계산 위험면·스냅샷 도로망·대피 POI 적재 ...", flush=True)
    res = pipeline.load_resources(args.region, npz_path=npz, repo=REPO)
    print(f"        위험면 {res.haz.shape} sha256 {res.npz_sha256[:16]}...")
    print(f"        보행망 {res.net.graph.number_of_nodes():,} 노드 / "
          f"{res.net.graph.number_of_edges():,} 간선  ({res.snapshot_walk})")
    print(f"        대피 POI {res.n_shelter_pois}곳 → 노드 {len(res.net.shelters)}개")
    print(f"        적재 소요 {res.timings.load_hazard_s + res.timings.load_network_s + res.timings.load_pois_s:.1f}s\n")

    summaries: list[dict] = []

    # ---------------------------------------------------------------- replay --
    if args.replay:
        csv = Path(args.replay_csv) if args.replay_csv else REPO / str(
            _cfg("live.replay.detections_csv",
                 "data/raw/firms_data/{region}_detections.csv")
        ).format(region=args.region)
        src = replay_mod.ReplaySource.from_csv(
            csv, window_h=args.replay_hours, speed=args.speed, bbox_wsen=bbox)
        print(f"  재생 원본   : {csv.relative_to(REPO)}")
        print(f"  재생 범위   : {src.t0:%Y-%m-%d %H:%M} → {src.t_end:%H:%M} UTC "
              f"({src.archive_span_h:.1f} h, 화점 {len(src.hotspots)}개, "
              f"통과 {len(src.overpasses)}회)")
        print(f"  배속        : {args.speed:g}x → 예상 재생 시간 "
              f"{src.projected_wall_s / 60.0:.1f} 분")
        print(f"  네트워크    : 사용하지 않음 (완전 오프라인)\n")

        clock = src.clock()
        t_start = time.monotonic()
        last_trigger_archive = None
        for op in src.iter_overpasses():
            slept = clock.wait_until(op.archive_time, time.monotonic() - t_start)
            new = firms.new_hotspots(
                op.hotspots, seen.keys,
                dedupe_radius_m=float(_cfg("live.firms.dedupe_radius_m", 375.0)),
                seen_points=seen.points)
            new = [h for h in new if h.confidence_rank >= min_rank]
            seen.observe(op.hotspots)
            seen.n_polls += 1
            seen.last_poll_utc = op.archive_time
            seen.save()
            print(f"[재생 {op.archive_time:%m-%d %H:%M}Z] 통과 #{op.index + 1}: "
                  f"화점 {op.n}개 · 신규 {len(new)}개"
                  + (f" (대기 {slept:.1f}s)" if slept > 0.05 else ""))
            if not new:
                continue
            if (last_trigger_archive is not None
                    and op.archive_time - last_trigger_archive
                    < timedelta(minutes=args.retrigger_min_interval_min)):
                print("            → 재트리거 간격 미도달, 라우팅 생략")
                continue
            last_trigger_archive = op.archive_time
            seen.n_triggers += 1
            seen.last_trigger_utc = op.archive_time
            seen.save()
            summaries.append(run_trigger(
                res, scope, new[0], new,
                {"kind": "replay", **src.as_dict()}, args, params, notes))
            if args.max_triggers and len(summaries) >= args.max_triggers:
                print(f"  --max-triggers {args.max_triggers} 도달, 종료합니다.")
                break

    # ------------------------------------------------------------------ live --
    else:
        if not firms.credentials_present():
            print(f"STOP (exit {EXIT_NO_CREDENTIALS}): {firms.ENV_MAP_KEY} is not "
                  "set, so the live branch cannot poll. Replay mode needs no "
                  "key: python scripts/run_live_detection.py --replay",
                  file=sys.stderr)
            return EXIT_NO_CREDENTIALS
        sources = list(_cfg("live.firms.sources", ["VIIRS_SNPP_NRT"]))
        print(f"  FIRMS 소스  : {', '.join(sources)}")
        print(f"  폴링 간격   : {args.poll_interval_min:g} 분")
        print(f"  조회 bbox   : {bbox}\n")
        while True:
            poll = firms.fetch_hotspots(
                bbox, sources=sources,
                day_range=int(_cfg("live.firms.day_range", 1)),
                api_base=str(_cfg("live.firms.api_base",
                                  "https://firms.modaps.eosdis.nasa.gov/api/area/csv")),
                timeout_s=float(_cfg("live.firms.timeout_s", 60.0)),
                retries=int(_cfg("live.firms.retries", 3)),
                backoff_s=list(_cfg("live.firms.backoff_s", [30.0, 60.0, 120.0])))
            stamp = poll.polled_utc.strftime("%Y%m%dT%H%M%SZ")
            poll_dir = Path(args.out_root) / f"poll_{stamp}"
            snaps = snapshot_poll(poll, args.region, poll_dir)
            inside = [h for h in poll.hotspots if firms.in_bbox(h, bbox)]
            new = firms.new_hotspots(
                inside, seen.keys,
                dedupe_radius_m=float(_cfg("live.firms.dedupe_radius_m", 375.0)),
                seen_points=seen.points)
            new = [h for h in new if h.confidence_rank >= min_rank]
            seen.observe(inside)
            seen.n_polls += 1
            seen.last_poll_utc = poll.polled_utc
            seen.save()
            (poll_dir / "POLL.json").write_text(json.dumps(
                {**poll.as_dict(), "n_in_bbox": len(inside),
                 "n_new": len(new), "snapshots": snaps,
                 "scope": scope.as_dict()},
                indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"[{poll.polled_utc:%Y-%m-%d %H:%M}Z] 조회 완료: "
                  f"{poll.per_source_counts} · 지역 내 {len(inside)} · "
                  f"신규 {len(new)} → {poll_dir.relative_to(REPO)}")

            due = (seen.last_trigger_utc is None
                   or poll.polled_utc - seen.last_trigger_utc
                   >= timedelta(minutes=args.retrigger_min_interval_min))
            if new and due:
                seen.n_triggers += 1
                seen.last_trigger_utc = poll.polled_utc
                seen.save()
                summaries.append(run_trigger(
                    res, scope, new[0], new,
                    {"kind": "live", **poll.as_dict(), "snapshots": snaps},
                    args, params, notes))
            elif new:
                print("            → 재트리거 간격 미도달, 라우팅 생략")

            if args.once or (args.max_triggers and len(summaries) >= args.max_triggers):
                break
            time.sleep(args.poll_interval_min * 60.0)

    # -------------------------------------------------------------- epilogue --
    after = protected_digests()
    changed = [k for k in before if before[k] != after[k]]
    if changed:
        print(f"\nSTOP (exit {EXIT_PROTECTED_MOVED}): protected artifact(s) "
              f"changed: {changed}", file=sys.stderr)
        return EXIT_PROTECTED_MOVED

    print("=" * 74)
    print(f"트리거 {len(summaries)}회 · 보호 산출물 {len(PROTECTED)}개 무변경 확인")
    if summaries:
        warm = [s["timings"]["warm_total_s"] for s in summaries]
        route = [s["timings"]["route_s"] for s in summaries]
        pdfs = [s["timings"]["pdf_s"] for s in summaries]
        print(f"탐지→목록 (warm): 최소 {min(warm):.1f}s · 중앙 "
              f"{sorted(warm)[len(warm) // 2]:.1f}s · 최대 {max(warm):.1f}s")
        print(f"  그중 라우팅   : 최소 {min(route):.1f}s · 최대 {max(route):.1f}s")
        if any(pdfs):
            print(f"  A4 PDF 변환   : 최대 {max(pdfs):.0f}s — 목록 확정 이후이며 "
                  f"위 수치에 포함되지 않습니다")
        summary_path = Path(args.out_root) / f"SUMMARY_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
        summary_path.write_text(json.dumps(
            {"mode": scope.mode, "scope": scope.as_dict(),
             "n_triggers": len(summaries), "runs": summaries, "notes": notes},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"요약: {summary_path.relative_to(REPO)}")
    print(f"SMS: DEMO_MODE={sms.demo_mode()} — 발송된 메시지 없음")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
