"""wfg-roadlayer: village road cut-off sheets from a fire-arrival raster. Offline after `setup`.

  python -m wfg_roadlayer setup                         # once, with network: road graphs + Korean font into the cache
  python -m wfg_roadlayer run --region 영덕 --issue-time 2025-03-25T18:00+09:00 --raster arrival.tif [--as-of ...]
  python -m wfg_roadlayer example                       # the 25 March 2025 worked example (의성·안동 and 영덕)
  python -m wfg_roadlayer verify OUT/certificates       # re-check every village certificate
  python -m wfg_roadlayer cards --region 영덕 --issue-time ... --raster ...   # A5 village cards, audit CSV, pickup list
  python -m wfg_roadlayer cards-example                 # cards for all 174 places of the worked example + overlap check

Exit status: 0 done, 2 refused (an input is missing or stale; REFUSED.txt says which), 1 error.
모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import pipeline, regiondata
from .errors import Refusal

PRODUCT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    {"name": "uiseong_andong_20250325_1200KST", "region": "uiseong_andong_2025", "issue": "2025-03-25T12:00+09:00",
     "raster": "examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"},
    {"name": "yeongdeok_20250325_1800KST", "region": "yeongdeok_2025", "issue": "2025-03-25T18:00+09:00",
     "raster": "examples/fire_arrival_20250325T0900Z_MEASURED_8h.tif"},
]


def _run_args(sp, fragility=False):
    sp.add_argument("--region", help="지역 / region: 영덕, 의성·안동 (or yeongdeok_2025, uiseong_andong_2025)")
    sp.add_argument("--issue-time", help="발표 시각 / issue time, ISO 8601 with zone, e.g. 2025-03-25T18:00+09:00")
    g = sp.add_argument_group("fire input (one of)")
    g.add_argument("--raster", help="fire-arrival GeoTIFF: minutes from the issue time (INTERFACE.md)")
    g.add_argument("--packet", help="repository hazard packet folder (HAZARD.json, REPORT.json, constructed_arrays.npz)")
    sp.add_argument("--horizon-min", type=float, help="forecast horizon in minutes (if the raster lacks WFG_HORIZON_MIN)")
    sp.add_argument("--not-reached-value", type=float, help="raster value meaning 'not reached within the horizon'")
    sp.add_argument("--as-of", help="기준 시각 / as-of time for the staleness check (default: now). Set it only for a replay.")
    sp.add_argument("--settings", help="settings TOML (default: wfg_roadlayer/settings.toml)")
    sp.add_argument("--out", help="output folder (default: wfg-roadlayer-out/<region>_<issue>)")
    sp.add_argument("--workers", type=int, help="worker processes (default: settings run.workers; 0 = CPU count up to 8)")
    sp.add_argument("--assume-uncovered-not-reached", action="store_true",
                    help="read road cells without fire data as not reached (printed on every page)")
    sp.add_argument("--overwrite", action="store_true", help="replace a non-empty output folder")
    if fragility:
        sp.add_argument("--fragility", action="store_true",
                        help="optional: add tolerated extra fire reach and closure-timing error per village (leaving now), with the "
                             "road that fails first, as CSV columns and one extra page per town (research/kcf-robust)")
    sp.add_argument("--cache", help="data cache (default: $WFG_ROADLAYER_CACHE or ~/.cache/wfg-roadlayer)")


def _refused(ref: Refusal, out, overwrite):
    sys.stderr.write(ref.text())
    if out is not None:
        out = Path(out)
        if out.exists() and any(out.iterdir()) and not overwrite:
            sys.stderr.write("(출력 폴더가 비어 있지 않아 REFUSED.txt 를 쓰지 않았습니다 / output folder not empty: REFUSED.txt not written)\n")
        else:
            if out.exists():
                shutil.rmtree(out)
            pipeline.write_refusal(out, ref)
            sys.stderr.write("-> %s\n" % (out / "REFUSED.txt"))
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wfg-roadlayer", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="fetch and verify the road graphs and the Korean font once (needs network unless given files)")
    s.add_argument("--archive", help="local copy of WFG-evaluated-routing-inputs-20261015.zip")
    s.add_argument("--data-routing", help="an already fetched data/routing folder (tools/fetch_routing_inputs.py)")
    s.add_argument("--font-wheel", help="local copy of koreanize_matplotlib-0.1.1-py3-none-any.whl")
    s.add_argument("--cache")
    r = sub.add_parser("run", help="one region, one fire-arrival input")
    _run_args(r, fragility=True)
    e = sub.add_parser("example", help="the 25 March 2025 worked example: 의성·안동 12:00 KST and 영덕 18:00 KST")
    e.add_argument("--out", default="wfg-roadlayer-example")
    e.add_argument("--workers", type=int)
    e.add_argument("--cache")
    e.add_argument("--overwrite", action="store_true")
    cr = sub.add_parser("cards", help="village cards (A5, ko + en), audit CSV, departure order and pickup list")
    _run_args(cr)
    cr.add_argument("--card-settings", help="card settings TOML (default: wfg_roadlayer/cards.toml)")
    ce = sub.add_parser("cards-example", help="cards for the worked example (both regions) and the replay overlap check")
    ce.add_argument("--out", default="wfg-roadlayer-cards-example")
    ce.add_argument("--workers", type=int)
    ce.add_argument("--cache")
    ce.add_argument("--card-settings")
    ce.add_argument("--overwrite", action="store_true")
    v = sub.add_parser("verify", help="re-check certificates with the standalone verifier")
    v.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)

    if a.cmd == "setup":
        regiondata.setup(Path(a.cache) if a.cache else regiondata.default_cache(), archive=a.archive,
                         data_routing=a.data_routing, font_wheel=a.font_wheel)
        return 0
    if a.cmd == "verify":
        code = 0
        for p in a.paths:
            p = Path(p)
            script = (p if p.is_dir() else p.parent.parent) / "verify_certificate.py"
            if not script.is_file():
                script = Path(__file__).resolve().parent / "verifier/verify_certificate.py"
            code |= subprocess.call([sys.executable, str(script), str(p)])
        return code
    if a.cmd == "run":
        try:
            pipeline.run(region_name=a.region, issue_time=a.issue_time, raster=a.raster, packet=a.packet, horizon_min=a.horizon_min,
                         not_reached_value=a.not_reached_value, as_of=a.as_of, settings_path=a.settings, out=a.out,
                         workers=a.workers, assume_uncovered=a.assume_uncovered_not_reached, overwrite=a.overwrite, cache=a.cache,
                         fragility=a.fragility)
        except Refusal as ref:
            return _refused(ref, a.out, a.overwrite)
        return 0
    if a.cmd == "cards":
        from . import cardrun
        try:
            cardrun.run_cards(region_name=a.region, issue_time=a.issue_time, raster=a.raster, packet=a.packet,
                              horizon_min=a.horizon_min, not_reached_value=a.not_reached_value, as_of=a.as_of,
                              settings_path=a.settings, card_settings=a.card_settings, out=a.out, workers=a.workers,
                              assume_uncovered=a.assume_uncovered_not_reached, overwrite=a.overwrite, cache=a.cache)
        except Refusal as ref:
            return _refused(ref, a.out, a.overwrite)
        return 0
    if a.cmd == "cards-example":
        from . import cardrun
        t0 = time.perf_counter()
        base = Path(a.out)
        results = []
        for ex in EXAMPLES:
            out = base / ex["name"]
            print("== %s ==" % ex["name"])
            try:
                results.append(cardrun.run_cards(region_name=ex["region"], issue_time=ex["issue"], raster=str(PRODUCT / ex["raster"]),
                                                 as_of=ex["issue"], card_settings=a.card_settings, out=out, workers=a.workers,
                                                 overwrite=a.overwrite, cache=a.cache))
            except Refusal as ref:
                return _refused(ref, out, a.overwrite)
        tab = cardrun.overlap_report(results, base / "OVERLAP.md", base / "overlap.json")
        for r in tab["rows"]:
            if r["region"] == "all":
                print("overlap %-14s flagged %3d, earliest %3d, both %3d (if unrelated %.1f)" % (
                    r["flag"], r["flagged"], r["earliest"], r["both"], r["expected_both_if_unrelated"]))
        print("cards example done in %.1f s -> %s" % (time.perf_counter() - t0, base))
        return 0
    if a.cmd == "example":
        t0 = time.perf_counter()
        base = Path(a.out)
        for ex in EXAMPLES:
            out = base / ex["name"]
            print("== %s ==" % ex["name"])
            try:
                pipeline.run(region_name=ex["region"], issue_time=ex["issue"], raster=str(PRODUCT / ex["raster"]), as_of=ex["issue"],
                             out=out, workers=a.workers, overwrite=a.overwrite, cache=a.cache)
            except Refusal as ref:
                return _refused(ref, out, a.overwrite)
        print("worked example done in %.1f s -> %s" % (time.perf_counter() - t0, base))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
