"""`python -m wfglink verify ...`: offline tools of the high-precision verifier.

cli.py adds the group with `add_parser(sub)`; every handler imports its module only when
it runs, so building the parser imports nothing heavy. Implemented: audit, sheets,
windows, truth, eval, identity. dataset, train, calibrate, replay, freeze and bench belong
to a later builder and exit with status 2 for now. `main(argv)` runs the group on its own
(python -m wfglink.verify.cli_tools ...), for tests.
"""
from __future__ import annotations

import argparse
import json
import sys

STUBS = {
    "dataset": "build training rows from verify dumps and window truth",
    "train": "train a patch or temporal scorer",
    "calibrate": "set rule thresholds for a profile",
    "replay": "replay scorers offline over dumped features",
    "freeze": "freeze the evaluation protocol (hash pinned)",
    "bench": "runtime benchmark of the observer",
}
NOT_YET = "not implemented yet (later builder)"


def _cfg(args):
    from wfglink.config import load_config

    return load_config(*(getattr(args, "config", None) or []))


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

    try:
        cfg = _cfg(args) if getattr(args, "config", None) else None
        res = evaluate_run(args.protocol, args.sha256, args.run, args.out, require_clean=not args.allow_dirty, cfg=cfg)
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


def _stub(name: str):
    def run(args: argparse.Namespace) -> int:
        print(f"verify {name}: {NOT_YET}", file=sys.stderr)
        return 2
    return run


def add_parser(sub) -> argparse.ArgumentParser:
    """Add the `verify` group to the subparsers of the wfglink command line."""
    p = sub.add_parser("verify", help="high-precision verifier, offline tools: audit, sheets, windows, truth, eval, "
                                      "identity")
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
    q.add_argument("--sha256", required=True, help="the protocol's pinned SHA-256")
    q.add_argument("--run", required=True, help="output folder of `process` (with high_precision/ for HP runs)")
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

    for name, text in STUBS.items():
        # Any arguments are taken as they come (no option parsing), so a stub always answers
        # with its own message and status 2.
        q = vs.add_parser(name, help=f"{text} ({NOT_YET})", prefix_chars="+", add_help=False)
        q.add_argument("rest", nargs=argparse.REMAINDER)
        q.set_defaults(func=_stub(name))
    return p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wfglink")
    sub = parser.add_subparsers(dest="command", required=True)
    add_parser(sub)
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
