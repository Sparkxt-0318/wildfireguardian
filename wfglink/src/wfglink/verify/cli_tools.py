"""`python -m wfglink verify ...`: offline tools of the high-precision verifier.

cli.py adds the group with `add_parser(sub)`; every handler imports its module only when
it runs, so building the parser imports nothing heavy. Subcommands: audit, sheets,
windows, truth, eval, identity, and dataset, train, calibrate, replay, freeze, bench (the
training, selection and runtime tools). `main(argv)` runs the group on its own
(python -m wfglink.verify.cli_tools ...), for tests.
"""
from __future__ import annotations

import argparse
import json
import sys

def _cfg(args):
    from wfglink.config import load_config

    return load_config(*(getattr(args, "config", None) or []))


def _hp_cfg(args, method: str = "accept_all"):
    from wfglink.verify.config import hp_config

    return hp_config(method, getattr(args, "config", None) or ())


def _cmdline() -> str:
    import shlex

    return " ".join(shlex.quote(a) for a in ["python", "-m", "wfglink", *sys.argv[1:]])


def cmd_audit(args: argparse.Namespace) -> int:
    from wfglink.verify.audit import audit_labels, write_audit

    try:
        res = audit_labels(args.tile_dir, args.labels, args.run, _cfg(args), strict_config=args.strict_config)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify audit: {exc}") from None
    for w in res.get("warnings", []):
        print(f"verify audit: warning: {w}", file=sys.stderr)
    if args.out:
        path = write_audit(res, args.out)
        print(f"-> {path} and {path.with_suffix('.json')}")
    print(json.dumps({"totals": res["totals"], "reproduces_score_labels": res["reproduces_score_labels"]}, indent=2))
    return 0


def cmd_sheets(args: argparse.Namespace) -> int:
    from pathlib import Path

    import pandas as pd

    from wfglink.verify.sheets import items_from_table, render_sheets

    p = Path(args.items)
    df = pd.read_csv(p) if p.suffix == ".csv" else pd.read_parquet(p)
    if args.kind and "kind" in df:
        df = df[df["kind"] == args.kind]
    items = items_from_table(df, args.category_col, args.limit, args.category or None)
    if not items:
        raise SystemExit("verify sheets: no items to draw")
    try:
        rec = render_sheets(args.run, items, args.out, clip=args.clip, credit=args.credit)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify sheets: {exc}") from None
    print(f"{len(rec['sheets'])} sheets and {len(rec['contact_sheets'])} contact sheets -> {args.out}")
    return 0


def cmd_windows(args: argparse.Namespace) -> int:
    from wfglink.verify.windows import make_windows

    roi = [float(v) for v in args.roi.split(",")] if args.roi else None
    # Only what is given replaces the clip settings' segment: the other end stays the clip's.
    seg = (args.start_seconds, args.end_seconds)
    try:
        rec = make_windows(args.clip, args.out, n=args.n, k=args.k, seed=args.seed, tile_px=args.tile_px, roi=roi,
                           segment=seg, cfg=_cfg(args), force=args.force)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify windows: {exc}") from None
    print(f"{rec['n_windows']} windows of {rec['k']} frames ({rec['tile_px'][0]}x{rec['tile_px'][1]} px) from "
          f"{rec['clip_id']}, window set {rec['window_set_id']} -> {args.out}")
    return 0


def cmd_truth(args: argparse.Namespace) -> int:
    from wfglink.verify.truth import merge_truth, write_truth

    try:
        rec = merge_truth(args.windows_dir, args.a, args.b, args.adjudicator, match_px=args.match_px,
                          edge_px=args.edge_px, min_points=args.min_points)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify truth: {exc}") from None
    write_truth(rec, args.out)
    for w in rec.get("warnings", []):
        print(f"verify truth: warning: {w}", file=sys.stderr)
    print(json.dumps({"totals": rec["totals"], "agreement": {k: v for k, v in rec["agreement"].items()
                                                              if k != "per_window"}}, indent=2, default=str))
    print(f"-> {args.out}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from wfglink.verify.evaluate import ProtocolError, evaluate_run
    from wfglink.verify.freeze import read_sha256

    try:
        cfg = _cfg(args) if getattr(args, "config", None) else None
        res = evaluate_run(args.protocol, read_sha256(args.sha256), args.run, args.out,
                           require_clean=not args.allow_dirty, cfg=cfg, recording=args.recording,
                           selection=args.selection)
    except (ProtocolError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify eval: {exc}") from None
    for w in res.get("notes", []):
        print(f"verify eval: note: {w}", file=sys.stderr)
    tl = res["track_level"]
    print(json.dumps({"precision": tl["precision"], "recall": tl["recall"], "status": tl["status"],
                      "status_notes": tl["status_notes"], "capability_passed": res["capability_passed"],
                      "counts": tl["counts"]}, indent=2, default=str))
    return 0


def cmd_identity(args: argparse.Namespace) -> int:
    from wfglink.verify.identity import compare, run_identity

    try:
        if args.other is None:
            print(json.dumps(run_identity(args.run, not args.top_level), indent=2))
            return 0
        res = compare(args.run, args.other, recursive=not args.top_level)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify identity: {exc}") from None
    print(json.dumps(res, indent=2))
    return 0 if res["identical"] else 1


def cmd_dataset(args: argparse.Namespace) -> int:
    from wfglink.verify.dataset import build_dataset
    from wfglink.verify.replay import ReplayError

    try:
        rec = build_dataset(args.run, args.labels, args.out, _hp_cfg(args), block_s=args.block_s, cell_px=args.cell_px,
                            max_neg_per_cell=args.max_neg_per_cell, max_hits_per_track=args.max_hits_per_track,
                            profile=args.profile, exclude_tiles=args.exclude_tiles, command_line=_cmdline())
    except (ReplayError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify dataset: {exc}") from None
    print(json.dumps({"counts": rec["counts"], "exclusions": rec["exclusions"], "floor": rec["floor"]}, indent=2))
    print(f"-> {args.out}")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from wfglink.verify.train import train_all

    try:
        rep = train_all(args.dataset, args.models, args.report, families=tuple(args.families), seeds=tuple(args.seeds),
                        max_seconds=args.max_seconds, command_line=_cmdline(), cv=not args.no_cv)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify train: {exc}") from None
    if rep["status"] != "OK":
        print(f"verify train: {rep['status']}: {rep.get('reason')}", file=sys.stderr)
        print(f"-> {args.report}")
        return 1
    for name, m in rep["models"].items():
        print(f"{name}: development AUC {(m.get('cv') or {}).get('auc')} (agent labels, PROVISIONAL) -> "
              f"{m['final']['path']} sha256 {m['final']['sha256']}")
    print(f"-> {args.report}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from wfglink.verify.calibrate import calibrate
    from wfglink.verify.evaluate import ProtocolError
    from wfglink.verify.freeze import read_sha256
    from wfglink.verify.replay import ReplayError

    if not args.protocol or not args.sha256:
        raise SystemExit("verify calibrate: calibration runs under the frozen protocol: give --protocol and --sha256")
    try:
        rec = calibrate(args.dataset, args.models, [tuple(r) for r in args.recording], args.out, _hp_cfg(args),
                        profile=args.profile, protocol=args.protocol,
                        protocol_sha256=read_sha256(args.sha256) if args.sha256 else None,
                        write_overlay=args.write_config, overlay=args.overlay, families=tuple(args.families),
                        train_report=args.train_report, allow_unfrozen_truth=args.allow_unfrozen_truth,
                        command_line=_cmdline(),
                        progress=(lambda r, i, n: print(f"  {r}: {i}/{n} frames", file=sys.stderr)
                                  if i == n else None))
    except (ProtocolError, ReplayError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify calibrate: {exc}") from None
    for w in rec.get("warnings", []):
        print(f"verify calibrate: warning: {w}", file=sys.stderr)
    if rec.get("development"):
        print(f"verify calibrate: {rec['development_note']}", file=sys.stderr)
    print(json.dumps({k: rec.get(k) for k in ("status", "branch", "target_missed", "selected", "family_bests",
                                                "duplicate_models", "overlay_sha256")}, indent=2, default=str))
    print(f"-> {args.out}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    from wfglink.verify.config import VerifyConfig
    from wfglink.verify.replay import ReplayError, load_dump, replay, write_replay
    from wfglink.verify.scorers import build_scorer

    cfg = _hp_cfg(args, args.method)
    try:
        dump = load_dump(args.run, allow_truncated=args.allow_truncated)
        scorer = build_scorer(VerifyConfig.from_cfg(cfg), args.profile)
        res = replay(dump, cfg, scorer, args.profile, strict_config=not args.loose_config)
        rec = write_replay(res, dump, args.out)
    except (ReplayError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify replay: {exc}") from None
    print(json.dumps({k: rec.get(k) for k in ("method", "online_method", "decisions", "events", "online_comparison",
                                                "missing_patches")}, indent=2, default=str))
    print(f"-> {args.out}")
    cmp = rec.get("online_comparison")
    return 0 if cmp is None or (cmp["decisions"]["identical"] and cmp["events"]["identical"]) else 1


def cmd_freeze(args: argparse.Namespace) -> int:
    import yaml

    from wfglink.verify.freeze import FreezeError, freeze

    windows: dict[str, list[str]] = {}
    for pop, d in args.windows or []:
        windows.setdefault(pop, []).append(d)
    values = {}
    for kv in args.set or []:
        k, _, v = kv.partition("=")
        if not k or not _:
            raise SystemExit(f"verify freeze: --set takes key.path=value, not {kv!r}")
        values[k] = yaml.safe_load(v)
    fill = {"windows": windows, "truth": args.truth or [], "values": values, "scoring_commit": args.scoring_commit,
            "allow_missing_truth": args.allow_missing_truth}
    if args.sealed_populations:
        fill["sealed_populations"] = args.sealed_populations
    try:
        rec = freeze(args.draft, args.out, fill)
    except (FreezeError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"verify freeze: {exc}") from None
    for n in rec["notes"]:
        print(f"verify freeze: note: {n}", file=sys.stderr)
    print(f"{rec['protocol']} sha256 {rec['sha256']} ({len(rec['filled'])} fields filled, {len(rec['truth'])} truth "
          "entries)")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    from wfglink.verify.bench import bench

    if args.synthetic:
        src = {"kind": "synthetic"}
    elif args.clip:
        src = {"kind": "clip", "path": args.clip}
    else:
        src = {"kind": "playlist", "path": args.playlist or "booth/playlist.yaml"}
    rep = bench(args.seconds, args.method, src, args.config or [], tuple(args.modes), args.out)
    for m, r in rep["modes"].items():
        if "error" in r:
            print(f"{m}: {r['error']}", file=sys.stderr)
            continue
        print(f"{m}: {r['frames']['analysed_fps'] or 0:.1f} analysed fps, publish-to-state p95 "
              f"{r['publish_to_state_ms']['p95']} ms, paint fps median {(r['paint_fps'] or {}).get('median')}")
        dec = r["publish_to_state_ms"].get("decision_frames") or {}
        if dec.get("status") == "NOT_MEASURED":
            print(f"{m}: decision frames NOT_MEASURED: {dec.get('reason')}", file=sys.stderr)
        if r.get("source_problem"):
            print(f"{m}: {r['source_problem']}", file=sys.stderr)
    print(f"-> {args.out} ({rep['note']})")
    return 0 if all("error" not in r and not r.get("source_problem") for r in rep["modes"].values()) else 1


def add_parser(sub) -> argparse.ArgumentParser:
    """Add the `verify` group to the subparsers of the wfglink command line."""
    p = sub.add_parser("verify", help="high-precision verifier, offline tools: audit, sheets, windows, truth, eval, "
                                      "identity, dataset, train, calibrate, replay, freeze, bench")
    vs = p.add_subparsers(dest="verify_command", required=True)

    q = vs.add_parser("audit", help="per-detection label status of a run against blind label tiles "
                                    "(reproduces label-score)")
    q.add_argument("tile_dir", help="tile folder written by label-tiles")
    q.add_argument("--labels", required=True, help="labels CSV (tile_id, x, y, confidence, note)")
    q.add_argument("--run", required=True, help="output folder of `process` for the same clip")
    q.add_argument("--out", default=None, help="audit table (.parquet or .csv; a .json of totals is written next to it)")
    q.add_argument("--config", nargs="*", help="the run's config files (its track settings replay confirmation and "
                                              "static flags)")
    q.add_argument("--strict-config", action="store_true", help="refuse when the config is not the run's "
                                                                "(config_sha256 differs) instead of warning")
    q.set_defaults(func=cmd_audit)

    q = vs.add_parser("sheets", help="PNG sheets (t-2 .. t+2 crops) of items: frame, x, y in a run's coordinates")
    q.add_argument("--run", required=True, help="output folder of `process` (its video is decoded again)")
    q.add_argument("--items", required=True, help="CSV or Parquet with frame, x, y [track_id, item_id, category or "
                                                  "status, note], for example a verify audit table")
    q.add_argument("--out", required=True, help="folder for the sheets")
    q.add_argument("--clip", default=None, help="the video or clip settings file when the run's path moved")
    q.add_argument("--credit", default=None, help="credit line (default: data/clips.csv by the video's SHA-256)")
    q.add_argument("--category", nargs="*", default=None, help="only these categories (statuses)")
    q.add_argument("--category-col", default=None, help="column holding the category (default category or status)")
    q.add_argument("--kind", default=None, help="audit tables: only rows of this kind (detection or label)")
    q.add_argument("--limit", type=int, default=None, help="at most this many items per category")
    q.set_defaults(func=cmd_sheets)

    q = vs.add_parser("windows", help="blind annotation windows: n seeded space-time tiles of k changed frames")
    q.add_argument("clip", help="a clip settings file data/clips/<id>.yaml or a video file")
    q.add_argument("--out", required=True, help="window folder (new or empty; an earlier set only with --force)")
    q.add_argument("--n", type=int, default=20, help="windows (default 20)")
    q.add_argument("--k", type=int, default=8, help="consecutive changed frames per window (default 8)")
    q.add_argument("--seed", type=int, default=0)
    q.add_argument("--tile-px", type=int, default=None, help="tile side (default 192 up to 1080 lines, else 256)")
    q.add_argument("--roi", default=None, help="x0,y0,x1,y1 (fractions or px); default the clip settings' ROI")
    q.add_argument("--start-seconds", type=float, default=None, help="segment start (default the clip settings')")
    q.add_argument("--end-seconds", type=float, default=None, help="segment end (default the clip settings')")
    q.add_argument("--force", action="store_true", help="replace an earlier window set in --out")
    q.add_argument("--config", nargs="*")
    q.set_defaults(func=cmd_windows)

    q = vs.add_parser("truth", help="merge two labellers and an adjudicator into truth tracks per window")
    q.add_argument("windows_dir", help="window folder written by verify windows")
    q.add_argument("--a", required=True, help="labeller A's CSV (window_id,k,x,y,confidence,ember_id,size_class,note)")
    q.add_argument("--b", required=True, help="labeller B's CSV")
    q.add_argument("--adjudicator", default=None, help="the adjudicator's CSV (same columns)")
    q.add_argument("--out", required=True, help="truth.json")
    q.add_argument("--match-px", type=float, default=3.0)
    q.add_argument("--edge-px", type=float, default=4.0)
    q.add_argument("--min-points", type=int, default=3)
    q.set_defaults(func=cmd_truth)

    q = vs.add_parser("eval", help="score a run against window truth under a frozen protocol (hash pinned)")
    q.add_argument("--protocol", required=True, help="protocol JSON")
    q.add_argument("--sha256", required=True, help="the protocol's pinned SHA-256 (hex, or its protocol.sha256 file)")
    q.add_argument("--run", required=True, help="output folder of `process` (with high_precision/ for HP runs)")
    q.add_argument("--recording", default=None, help="frozen protocols: the truth entry to use (default: the one of "
                                                     "the run's video and segment start)")
    q.add_argument("--selection", default=None, help="the committed selection.json (verify calibrate): the run must "
                                                     "be the selected method, overlay and model or thresholds")
    q.add_argument("--out", default=None, help="write the result JSON here")
    q.add_argument("--allow-dirty", action="store_true", help="development only: accept an uncommitted protocol "
                                                               "(refused for a sealed protocol)")
    q.add_argument("--config", nargs="*", help="legacy runs: the run's config files (track settings for the static "
                                              "replay; default configs/default.yaml)")
    q.set_defaults(func=cmd_eval)

    q = vs.add_parser("identity", help="content hashes of a run's tables and summary; with a second run, compare")
    q.add_argument("run", help="run folder")
    q.add_argument("other", nargs="?", default=None, help="second run folder: exit 0 when identical, 1 otherwise")
    q.add_argument("--top-level", action="store_true", help="only the run folder's own tables (not high_precision/)")
    q.set_defaults(func=cmd_identity)

    q = vs.add_parser("dataset", help="training rows (track and hit samples, patches) from a verify dump run and "
                                      "track labels")
    q.add_argument("run", help="dump run folder (process --high-precision accept_all --verify-dump)")
    q.add_argument("--labels", nargs="+", required=True, help="track review CSVs (track_key or track_id, category, "
                                                              "reviewer, adjudicated) and audit category CSVs")
    q.add_argument("--out", required=True, help="dataset folder")
    q.add_argument("--profile", default="file_native")
    q.add_argument("--block-s", type=float, default=4.0, help="time block of a group (default 4 s)")
    q.add_argument("--cell-px", type=int, default=16, help="cell of the negative cap (default 16 px)")
    q.add_argument("--max-neg-per-cell", type=int, default=20)
    q.add_argument("--max-hits-per-track", type=int, default=8)
    q.add_argument("--exclude-tiles", default=None, help="label tile folder whose tiles (16 px, 1 s) stay out of "
                                                         "training")
    q.add_argument("--config", nargs="*", help="the run's config files (its legacy config must be the run's)")
    q.set_defaults(func=cmd_dataset)

    q = vs.add_parser("train", help="train the temporal (C) and patch (B) families, development estimate by grouped "
                                    "cross-validation")
    q.add_argument("dataset", help="dataset folder (verify dataset)")
    q.add_argument("--models", default="data/models/verify", help="models folder (default data/models/verify)")
    q.add_argument("--report", required=True, help="train_report.json")
    q.add_argument("--families", nargs="+", default=["temporal", "patch"], choices=["temporal", "patch"])
    q.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    q.add_argument("--max-seconds", type=float, default=600.0, help="wall-time cap per patch fit (default 600)")
    q.add_argument("--no-cv", action="store_true", help="skip the cross-validation (final models only)")
    q.set_defaults(func=cmd_train)

    q = vs.add_parser("calibrate", help="rules candidates, calibration replays against window truth, selection, "
                                        "--write-config pins the overlay")
    q.add_argument("--dataset", required=True, help="development dataset (its ember tracks give the rules ranges)")
    q.add_argument("--models", default="data/models/verify", help="models folder (verify train)")
    q.add_argument("--recording", nargs=2, action="append", required=True, metavar=("RUN", "TRUTH"),
                   help="a calibration recording: its accept_all dump run and its truth.json (repeat per recording)")
    q.add_argument("--out", required=True, help="folder for rules_candidates.json, calibration_points.json and "
                                                "selection.json")
    q.add_argument("--profile", default="file_native")
    q.add_argument("--protocol", default=None, help="the frozen, committed protocol: its calibration_selection "
                                                    "truth entries must hold every truth given (grids, settings)")
    q.add_argument("--sha256", default=None, help="the protocol's pinned SHA-256 (hex or protocol.sha256)")
    q.add_argument("--train-report", default=None, help="train_report.json of verify train: every model must be "
                                                        "listed there with status OK")
    q.add_argument("--families", nargs="+", default=["accept_all", "rules", "patch", "temporal"])
    q.add_argument("--allow-unfrozen-truth", action="store_true", help="development only: truth of a recording "
                                                                       "the protocol does not hold (never one it "
                                                                       "holds); --write-config is then refused")
    q.add_argument("--write-config", action="store_true", help="pin the selection into the overlay and write "
                                                               "selection.json (needs --protocol)")
    q.add_argument("--overlay", default=None, help="the overlay to pin (default configs/high_precision.yaml)")
    q.add_argument("--config", nargs="*")
    q.set_defaults(func=cmd_calibrate)

    q = vs.add_parser("replay", help="rebuild a method's decisions and crossings offline from a verify dump")
    q.add_argument("run", help="dump run folder")
    q.add_argument("--method", default="rules", choices=["accept_all", "rules", "patch", "temporal"])
    q.add_argument("--out", required=True, help="folder for replay_decisions.parquet, replay_events.parquet and "
                                                "replay.json")
    q.add_argument("--profile", default="file_native")
    q.add_argument("--allow-truncated", action="store_true", help="replay a dump cut at its row limit (differs)")
    q.add_argument("--loose-config", action="store_true", help="warn instead of refusing when the config is not "
                                                               "the run's")
    q.add_argument("--config", nargs="*")
    q.set_defaults(func=cmd_replay)

    q = vs.add_parser("freeze", help="fill a protocol draft's FILLED_AT_FREEZE fields, pin truth, write "
                                     "protocol.yaml and protocol.sha256")
    q.add_argument("draft", help="the protocol draft (YAML)")
    q.add_argument("--out", required=True, help="folder for protocol.yaml and protocol.sha256")
    q.add_argument("--windows", nargs=2, action="append", metavar=("POPULATION", "DIR"),
                   help="a window set (verify windows folder) of a population (repeat)")
    q.add_argument("--truth", nargs="*", default=[], help="truth.json files of those window sets")
    q.add_argument("--scoring-commit", default=None, help="default: the current git commit")
    q.add_argument("--set", nargs="*", default=[], help="key.path=value (YAML value) for any other field")
    q.add_argument("--sealed-populations", nargs="*", default=None, help="default: sealed_test")
    q.add_argument("--allow-missing-truth", action="store_true")
    q.set_defaults(func=cmd_freeze)

    q = vs.add_parser("bench", help="live runtime benchmark of the booth, legacy and high precision (Linux reference)")
    g = q.add_mutually_exclusive_group()
    g.add_argument("--playlist", default=None, help="playlist (default booth/playlist.yaml)")
    g.add_argument("--clip", default=None, help="one clip settings file or video")
    g.add_argument("--synthetic", action="store_true", help="generated video")
    q.add_argument("--seconds", type=float, default=300.0, help="seconds per mode (default 300)")
    q.add_argument("--method", default="rules", choices=["accept_all", "rules", "patch", "temporal"])
    q.add_argument("--modes", nargs="+", default=["legacy", "high_precision"], choices=["legacy", "high_precision"])
    q.add_argument("--out", required=True, help="report JSON")
    q.add_argument("--config", nargs="*")
    q.set_defaults(func=cmd_bench)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wfglink")
    sub = parser.add_subparsers(dest="command", required=True)
    add_parser(sub)
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
