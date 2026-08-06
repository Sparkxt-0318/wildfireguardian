#!/usr/bin/env python
"""Measure what the PHASE-19 service layer actually costs and actually promises.

Round-3 PHASE 19 STEP 1 and STEP 2.

SIX QUESTIONS, MEASURED RATHER THAN ASSERTED
--------------------------------------------
0. **Cancelling a running scan stops it, and leaves nothing behind.** A real
   458-origin job is cancelled five seconds in; what is timed is how long it
   takes to stop and what it left on disk (STEP 2).
1. **Per-request time after pre-loading.** The cold request pays for the
   hazard field, the walk graph and the refuge POIs; every warm one does not.
   Both are timed here, from the same process, so the difference is the cache
   and not the machine.
2. **Memory, per region and for all three.** Whether the three regions can be
   resident at once is a memory question with a number, not a preference.
3. **Two requests at once give the same answer.** Submitted to two workers,
   with the resources shared, and their result digests compared.
4. **The same request twice gives the same answer.** The property a web button
   needs: pressing it again must not produce a different dispatch list.
5. **The process globals did not move.** osmnx settings and numpy's global RNG
   are digested before and after the whole run.

⚠ Every timing here EXCLUDES A4 PDF conversion, exactly as every other timing
in this project does: it runs after the dispatch list already exists and scales
with village count rather than with the decision.

Run:
    python scripts/measure_service_layer.py
    python scripts/measure_service_layer.py --regions yeongdeok_2025 --repeats 2
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

from wildfireguardian.service import guards, jobs, params, progress, resources  # noqa: E402
from wildfireguardian.service import routing as svc  # noqa: E402

#: A coordinate inside each region's registered walk bbox. The Yeongdeok one is
#: the coordinate the committed PHASE-12 manual run used, so its timing is
#: directly comparable with the figure in HANDOFF_ROUND3.md.
PROBE: dict[str, tuple[float, float]] = {
    "yeongdeok_2025": (36.4436, 129.3696),
    "uiseong_andong_2025": (36.36, 128.62),
    "uljin_samcheok_2022": (36.95, 129.32),
}


def _probe(region: str) -> tuple[float, float]:
    if region in PROBE:
        return PROBE[region]
    w, s, e, n = params.walk_bbox(region)
    return ((s + n) / 2.0, (w + e) / 2.0)


def measure_memory(regions: list[str], p: params.RoutingParams) -> dict:
    """Load each region into ONE cache and report what it cost.

    Loaded in sequence into a cache big enough to hold them all, so the report
    answers "can three be resident at once" rather than "how big is one".
    """
    cache = resources.ResourceCache(capacity=len(regions))
    rss0 = resources._peak_rss_bytes()
    per = []
    for r in regions:
        npz = params.npz_for_region(r)
        if not npz.exists():
            per.append({"region": r, "skipped": "hazard field absent"})
            continue
        t0 = time.monotonic()
        _res, cached, entry = cache.get(r, p, npz_path=npz)
        per.append({**entry.as_dict(), "was_cached": cached,
                    "wall_s": round(time.monotonic() - t0, 3)})
    stats = cache.stats()
    return {
        "per_region": per,
        "cache": stats,
        "process_peak_rss_mib_before": round(rss0 / 1048576, 2),
        "process_peak_rss_mib_after": stats["process_peak_rss_mib"],
        "all_regions_resident": stats["resident"] == len(
            [x for x in per if "skipped" not in x]),
        "note": "rss figures are PEAK RSS for the whole process. Peak never "
                "falls, so the after-minus-before difference is an upper bound "
                "on what the loads kept, and includes the interpreter, numpy, "
                "osmnx, rasterio and every parse buffer. hazard_bytes is exact.",
    }


def measure_timing(region: str, p: params.RoutingParams, *, repeats: int,
                   out_root: Path) -> dict:
    """Cold once, then warm ``repeats`` times, in one process with one cache."""
    cache = resources.ResourceCache(capacity=1)
    runs = []
    for i in range(repeats + 1):
        lat, lon = _probe(region)
        req = svc.IgnitionRequest(region=region, lat=lat, lon=lon,
                                  reported_by="측정", params=p, make_pdf=False,
                                  out_root=out_root / f"timing_{i}")
        prog_seen: list[dict] = []
        prog = progress.Progress(on_event=prog_seen.append, min_interval_s=0.5)
        t0 = time.monotonic()
        summary = svc.route_from_ignition(req, cache=cache, progress=prog)
        wall = time.monotonic() - t0
        t = summary["timings"]
        runs.append({
            "index": i,
            "kind": "cold (nothing resident)" if i == 0 else "warm (cache hit)",
            "resources_were_cached": summary["resources_were_cached"],
            "wall_s": round(wall, 3),
            "load_s": round(t["load_hazard_s"] + t["load_network_s"]
                            + t["load_pois_s"], 3),
            "route_s": t["route_s"],
            "cluster_s": t["cluster_s"],
            "render_s": t["render_s"],
            "warm_total_s": t["warm_total_s"],
            "n_scanned": summary["n_scanned"],
            "counts": summary["counts"],
            "n_villages": summary["n_villages"],
            "n_points": summary["n_points"],
            "result_digest": svc.result_digest(summary),
            "bucket_fingerprint": summary["bucket_fingerprint"],
            "run_id": summary["run_id"],
            "progress_events": len(prog_seen),
            "progress_last_text_ko": (prog_seen[-1]["current_text_ko"]
                                      if prog_seen else ""),
        })
    cold, warm = runs[0], runs[1:]
    digests = {r["result_digest"] for r in runs}
    return {
        "region": region,
        "runs": runs,
        "cold_wall_s": cold["wall_s"],
        "warm_wall_s_median": (sorted(r["wall_s"] for r in warm)[len(warm) // 2]
                               if warm else None),
        "preload_saving_s": (round(cold["wall_s"]
                                   - sorted(r["wall_s"] for r in warm)[len(warm) // 2], 3)
                             if warm else None),
        "same_input_same_answer": len(digests) == 1,
        "distinct_result_digests": sorted(digests),
        "distinct_run_ids": len({r["run_id"] for r in runs}) == len(runs),
    }


def measure_concurrency(region: str, p: params.RoutingParams, *,
                        out_root: Path) -> dict:
    """Two requests in flight at once. Same answer, two directories, no crosstalk."""
    cache = resources.ResourceCache(capacity=1)
    lat, lon = _probe(region)
    # Warm first, so the measurement is about concurrent ROUTING rather than
    # about two threads racing to load the same graph (which is tested
    # separately, in tests/test_service_layer.py).
    cache.get(region, p, npz_path=params.npz_for_region(region))
    runner = jobs.JobRunner(cache=cache, max_workers=2, max_queue=8)
    try:
        t0 = time.monotonic()
        ids = [runner.submit_ignition(svc.IgnitionRequest(
            region=region, lat=lat, lon=lon, reported_by=f"동시-{i}", params=p,
            make_pdf=False, out_root=out_root / "concurrent")) for i in range(2)]
        submit_s = time.monotonic() - t0
        states = [runner.wait(j, timeout=900) for j in ids]
        wall = time.monotonic() - t0
    finally:
        runner.shutdown(wait=False)

    results = [s["result"] for s in states]
    digests = [svc.result_digest(r) for r in results]
    return {
        "region": region,
        "n_concurrent": 2,
        "submit_returned_after_s": round(submit_s, 4),
        "both_finished_after_s": round(wall, 3),
        "identical_answer": digests[0] == digests[1],
        "result_digests": digests,
        "bucket_fingerprints": [r["bucket_fingerprint"] for r in results],
        "counts": [r["counts"] for r in results],
        "run_ids": [r["run_id"] for r in results],
        "distinct_run_directories": len({r["out_dir"] for r in results}) == 2,
        "per_job_route_s": [r["timings"]["route_s"] for r in results],
        "note": "workers are THREADS and the scan is pure-Python Dijkstra, so "
                "two concurrent jobs are SAFE but not faster: the GIL "
                "serialises them and each one's route_s roughly doubles. What "
                "concurrency buys here is that the second request starts at "
                "once instead of waiting for the first to finish.",
    }


def measure_cancel(region: str, p: params.RoutingParams, *,
                   out_root: Path, after_s: float = 5.0) -> dict:
    """Cancel a real 458-origin scan mid-flight and time how long it takes to stop.

    The demonstration case: a presenter clicks the wrong coordinate and cannot
    wait 26 seconds for it. What is measured is the two things that decide
    whether cancellation is usable — how quickly it stops, and whether it left
    anything behind.
    """
    cache = resources.ResourceCache(capacity=1)
    lat, lon = _probe(region)
    cache.get(region, p, npz_path=params.npz_for_region(region))   # warm first
    runner = jobs.JobRunner(cache=cache, max_workers=1, max_queue=4)
    root = out_root / "cancelled"
    try:
        job_id = runner.submit_ignition(svc.IgnitionRequest(
            region=region, lat=lat, lon=lon, reported_by="취소 측정", params=p,
            make_pdf=False, out_root=root))
        # Let it get properly under way, so this measures a cancel that lands
        # in the middle of the scan rather than one that races the start.
        deadline = time.monotonic() + after_s
        while time.monotonic() < deadline:
            time.sleep(0.05)
        snap = runner.status(job_id)["progress"]
        t0 = time.monotonic()
        asked = runner.cancel(job_id)
        state = runner.wait(job_id, timeout=120)
        stopped_after = time.monotonic() - t0
    finally:
        runner.shutdown(wait=False)

    leftovers = sorted(str(q.relative_to(root)) for q in root.rglob("*")) \
        if root.exists() else []
    return {
        "region": region,
        "cancel_requested_after_s": after_s,
        "cancel_accepted": asked,
        "progress_when_cancelled": snap.get("current_text_ko", ""),
        "origins_done_when_cancelled": next(
            (s["done"] for s in snap.get("stages", []) if s["key"] == "routing"), None),
        "stopped_after_s": round(stopped_after, 3),
        "final_state": state["state"],
        "nothing_was_written": state.get("nothing_was_written"),
        "leftover_files": leftovers,
        "note": "cooperative cancellation: the flag is read at an origin "
                "boundary, so the stop latency is one origin (~55 ms) plus "
                "scheduling. Routing precedes every write, so a cancelled "
                "request cannot leave a partial dispatch list.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(params.known_regions()))
    ap.add_argument("--timing-region", default="yeongdeok_2025")
    ap.add_argument("--repeats", type=int, default=2,
                    help="warm requests after the cold one")
    ap.add_argument("--skip-concurrency", action="store_true")
    ap.add_argument("--out", default=str(REPO / "outputs" / "service_layer"
                                         / "measurement.json"))
    ap.add_argument("--run-root", default=None,
                    help="where the measurement runs write (default: beside --out)")
    args = ap.parse_args()

    out = Path(args.out)
    run_root = Path(args.run_root) if args.run_root else out.parent / "runs"
    out.parent.mkdir(parents=True, exist_ok=True)

    before = guards.freeze_globals(force=True)
    p = params.RoutingParams.from_config()
    started = datetime.now(UTC)
    t0 = time.monotonic()

    print("=" * 74)
    print("  PHASE 19 — service-layer measurement")
    print("=" * 74)

    print("\n[1/4] 메모리 — 지역별 적재 비용")
    mem = measure_memory(args.regions, p)
    for e in mem["per_region"]:
        if "skipped" in e:
            print(f"      {e['region']:24s} 생략 ({e['skipped']})")
            continue
        print(f"      {e['region']:24s} {e['wall_s']:5.2f}s  "
              f"위험면 {e['hazard_mib']:6.2f} MiB  RSS+{e['rss_delta_mib']:7.2f} MiB  "
              f"노드 {e['n_walk_nodes']:,}")
    print(f"      전체 상주 가능: {mem['all_regions_resident']}  "
          f"프로세스 peak RSS {mem['process_peak_rss_mib_after']:.1f} MiB")

    print(f"\n[2/4] 요청당 소요 — {args.timing_region} (cold 1회 + warm {args.repeats}회)")
    timing = measure_timing(args.timing_region, p, repeats=args.repeats,
                            out_root=run_root)
    for r in timing["runs"]:
        print(f"      #{r['index']} {r['kind']:24s} 총 {r['wall_s']:6.2f}s "
              f"(적재 {r['load_s']:5.2f} + 라우팅 {r['route_s']:6.2f} "
              f"+ 전달물 {r['render_s']:.2f})")
    print(f"      사전 적재 절감 : {timing['preload_saving_s']}s")
    print(f"      같은 입력 같은 답: {timing['same_input_same_answer']}")

    print(f"\n[3/4] 취소 — {args.timing_region} (5초 뒤 취소)")
    canc = measure_cancel(args.timing_region, p, out_root=run_root)
    print(f"      취소 시점      : {canc['progress_when_cancelled']}")
    print(f"      정지까지       : {canc['stopped_after_s']:.3f}s")
    print(f"      최종 상태      : {canc['final_state']}")
    print(f"      남긴 파일      : {len(canc['leftover_files'])}개")

    conc = None
    if not args.skip_concurrency:
        print(f"\n[4/4] 동시 2요청 — {args.timing_region}")
        conc = measure_concurrency(args.timing_region, p, out_root=run_root)
        print(f"      접수 반환      : {conc['submit_returned_after_s']:.4f}s "
              "(대기하지 않음)")
        print(f"      둘 다 완료     : {conc['both_finished_after_s']:.1f}s")
        print(f"      결과 동일      : {conc['identical_answer']}")
        print(f"      디렉터리 분리  : {conc['distinct_run_directories']}")

    after_osm = guards.osmnx_settings_digest()
    after_np = guards.numpy_global_digest()
    doc = {
        "schema_version": 1,
        "title": "PHASE 19 — service-layer measurement",
        "measured_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_seconds": round(time.monotonic() - t0, 1),
        "parameters": p.as_dict(),
        "memory": mem,
        "timing": timing,
        "cancellation": canc,
        "concurrency": conc,
        "globals": {
            "before": before.as_dict(),
            "osmnx_settings_sha256_after": after_osm,
            "numpy_global_rng_sha256_after": after_np,
            "unchanged": (after_osm == before.osmnx_digest
                          and after_np == before.numpy_global_digest),
        },
        "excludes": "A4 PDF conversion, everywhere, for the reason stated in "
                    "live/state.py StageTimings.pdf_s",
    }
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"\n전역 상태 무변경 : {doc['globals']['unchanged']}")
    print(f"기록             : {out}")
    print("=" * 74)
    return 0 if doc["globals"]["unchanged"] and timing["same_input_same_answer"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
