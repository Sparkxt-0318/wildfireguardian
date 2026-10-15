"""Command line entry point: `python -m wfglink <command>`."""
from __future__ import annotations

import argparse
import json
import sys


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check the setup, one line per check ending in OK or FAIL (wfglink/doctor.py)."""
    from wfglink.doctor import main as doctor_main

    return doctor_main(json_out=args.json)


def cmd_live(args: argparse.Namespace) -> int:
    from wfglink.config import load_config
    from wfglink.ui.booth_app import run_live, source_spec

    cfg = load_config(*(args.config or []), local=True)
    spec = source_spec(synthetic=args.synthetic, playlist=args.playlist, clip=args.clip, cfg=cfg)
    res = run_live(cfg, source=spec, screen=args.screen, lang=args.lang, limits_screen=args.limits_screen,
                   duration_s=args.duration, screenshot=args.screenshot, heartbeat=args.heartbeat)
    if args.report:
        with open(args.report, "w") as f:
            json.dump(res, f, indent=2, default=str)
    return 0 if (res["quit_confirmed"] or (args.duration and not res["signal"])) else 1


def _gate_arg(text: str | None) -> dict | None:
    """x1,y1,x2,y2 in pixels, or in fractions of the frame when every value is at most 1."""
    if not text:
        return None
    v = [float(t) for t in text.split(",")]
    if len(v) != 4:
        raise SystemExit("--gate needs four numbers: x1,y1,x2,y2")
    return {"p1": v[:2], "p2": v[2:], "name": "gate"}


def cmd_process(args: argparse.Namespace) -> int:
    from pathlib import Path

    from wfglink import PROJECT_ROOT
    from wfglink.config import load_config
    from wfglink.outputs.process import process_clip

    cfg = load_config(*(args.config or []))
    clip = Path(args.clip)
    cc: dict = {}
    if clip.suffix in (".yaml", ".yml"):   # a clip settings file (data/clips/<id>.yaml)
        from wfglink.validate.clips import load_clip_settings

        cc, clip, _ = load_clip_settings(clip)
    seg = (cc.get("segments_s") or [[None, None]])[0]
    start = args.start_seconds if args.start_seconds else (seg[0] or 0.0)
    end = args.max_seconds if args.max_seconds is not None else seg[1]
    gate = _gate_arg(args.gate) or (cc.get("gate") and {"p1": cc["gate"][:2], "p2": cc["gate"][2:], "name": "gate"})
    roi = [float(v) for v in args.roi.split(",")] if args.roi else cc.get("roi")
    out = Path(args.out) if args.out else PROJECT_ROOT / "results" / "runs" / "process" / (cc.get("clip_id") or clip.stem)
    s = process_clip(clip, out, cfg, gate=gate, t_exp=args.exposure or cc.get("exposure_s"), overlay=not args.no_overlay,
                     lang=args.lang, max_seconds=end, m_per_px=args.m_per_px, distance_m=args.distance_m,
                     start_s=start, roi=roi, metrics_scope=str(cc.get("metrics_scope") or "all"))
    t = s["totals"]
    print(f"{clip.name}: {t.get('frames')} frames, {t.get('tracks_moving')} moving tracks, "
          f"CPC gross {t.get('cpc_gross')}, speed median {t.get('speed_px_s', {}).get('median')} px/s -> {out}")
    for w in s["warnings"]:
        print("warning:", w)
    return 0


def cmd_plausibility(args: argparse.Namespace) -> int:
    from wfglink.config import load_config
    from wfglink.validate.plausibility import run_plausibility

    try:
        out = run_plausibility(args.run_dir, args.clip, load_config(*(args.config or [])),
                               determinism_seconds=args.determinism_seconds)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"plausibility: {exc}") from None
    for name, c in out["checks"].items():
        print(f"{name}: {c['status']}: {c['reason']}")
    print(f"-> {args.run_dir}/plausibility.json")
    return 0


def cmd_label_tiles(args: argparse.Namespace) -> int:
    from wfglink.config import load_config
    from wfglink.validate.labels import make_tiles

    try:
        rec = make_tiles(args.clip, args.out, frames=args.frames, seed=args.seed, reserve=args.reserve,
                         tile_px=args.tile_px, tiles_per_frame=args.tiles_per_frame, force=args.force,
                         cfg=load_config(*(args.config or [])))
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"label-tiles: {exc}") from None
    print(f"{rec['tiles']} tiles from {rec['frames_drawn']} frames of {rec['clip_id']} "
          f"({rec['frames_requested']} to score, the rest in reserve), tile set {rec['tile_set_id']} -> {args.out}")
    return 0


def cmd_label_score(args: argparse.Namespace) -> int:
    from pathlib import Path

    from wfglink.config import load_config
    from wfglink.validate.labels import MANIFEST, inter_labeler_f1, score_labels

    cfg = load_config(*(args.config or []))
    if args.out and Path(args.tile_dir).resolve() in Path(args.out).resolve().parents:
        raise SystemExit("label-score: --out must not be inside the tile folder "
                         "(it holds nothing derived from detections)")
    try:
        res = score_labels(args.tile_dir, args.labels, args.run, cfg, tag=args.tag)
        if args.compare:
            res["inter_labeler"] = inter_labeler_f1(args.labels, args.compare, cfg=cfg,
                                                    manifest=Path(args.tile_dir) / MANIFEST,
                                                    tags=(args.tag, args.compare_tag))
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"label-score: {exc}") from None
    text = json.dumps(res, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    for w in res.get("warnings", []):
        print("warning:", w, file=sys.stderr)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from wfglink.validate.command import run_validate

    return run_validate(args)


def cmd_demo_gate(args: argparse.Namespace) -> int:
    from wfglink.ui.demo_gate import demo_gate

    return demo_gate(seconds=args.seconds, playlist=args.playlist, out=args.out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfglink", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the setup: python, packages, fonts, screens, video, data, clips (OK or FAIL)")
    p.add_argument("--json", action="store_true", help="print every detail as JSON")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("live", help="the booth screen: approved clips analysed live as they play (or synthetic video)")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--synthetic", action="store_true", help="play generated video instead of clips")
    src.add_argument("--playlist", default=None, help="playlist file (default booth/playlist.yaml, config booth.playlist)")
    src.add_argument("--clip", default=None, help="play one video file, or one clip settings file data/clips/<id>.yaml")
    p.add_argument("--screen", default=None,
                   help="auto (default: the external monitor if connected, else the built-in screen), external, "
                        "primary, or a screen name")
    p.add_argument("--lang", default=None, choices=["ko", "en"])
    p.add_argument("--limits-screen", default=None, help="show the limits card on this second screen")
    p.add_argument("--duration", type=float, default=None, help="stop after this many seconds (tests, checks)")
    p.add_argument("--heartbeat", default=None, help="JSON file rewritten every 2 s for the booth supervisor and the soak")
    p.add_argument("--report", default=None, help="write a JSON report of the run here")
    p.add_argument("--screenshot", default=None, help="save the screen here when --duration ends")
    p.add_argument("--config", nargs="*", help="extra YAML config files")
    p.set_defaults(func=cmd_live)

    p = sub.add_parser("process", help="file mode: tables, summary JSON and overlay video for one clip")
    p.add_argument("clip", help="a video file, or a clip settings file data/clips/<id>.yaml")
    p.add_argument("--out", default=None, help="output folder (default results/runs/process/<clip name>)")
    p.add_argument("--gate", default=None, help="x1,y1,x2,y2 in px, or fractions of the frame")
    p.add_argument("--exposure", type=float, default=None, help="exposure time in s if known (else estimated)")
    p.add_argument("--no-overlay", action="store_true")
    p.add_argument("--lang", default="ko", choices=["ko", "en"])
    p.add_argument("--start-seconds", type=float, default=0.0, help="start of the segment to process")
    p.add_argument("--roi", default=None, help="x0,y0,x1,y1 region to analyse (fractions or px)")
    p.add_argument("--max-seconds", type=float, default=None, help="end of the segment (clip time)")
    p.add_argument("--m-per-px", type=float, default=None, help="scale at the stated distance (default: pixels)")
    p.add_argument("--distance-m", type=float, default=None)
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_process)

    p = sub.add_parser("plausibility", help="real-clip plausibility checks on a process run (writes plausibility.json)")
    p.add_argument("run_dir", help="output folder of `process`")
    p.add_argument("--clip", required=True, help="clip settings file data/clips/<id>.yaml")
    p.add_argument("--determinism-seconds", type=float, default=None,
                   help="length of the two determinism reruns (default plausibility.determinism.seconds; 0 skips "
                        "and keeps an earlier result; minutes per second of video on 4K clips)")
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_plausibility)

    p = sub.add_parser("label-tiles", help="blind label tiles of randomly sampled frames (no detections involved)")
    p.add_argument("clip", help="clip settings file data/clips/<id>.yaml")
    p.add_argument("--out", required=True, help="tile folder (new or empty; an earlier tile set only with --force)")
    p.add_argument("--frames", type=int, default=None, help="frames to score (default labels.frames)")
    p.add_argument("--reserve", type=int, default=None, help="frames drawn in reserve (default labels.reserve_frames)")
    p.add_argument("--seed", type=int, default=None, help="sampling seed (default labels.seed)")
    p.add_argument("--tile-px", type=int, default=None, help="tile side in source pixels (default labels.tile_px)")
    p.add_argument("--tiles-per-frame", type=int, default=None, help="tiles per frame (default labels.tiles_per_frame)")
    p.add_argument("--force", action="store_true",
                   help="replace an earlier tile set in --out (its labels no longer apply)")
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_label_tiles)

    p = sub.add_parser("label-score", help="precision, recall and F1 of a run's detections against blind labels")
    p.add_argument("tile_dir", help="tile folder written by label-tiles")
    p.add_argument("--labels", required=True, help="labels CSV (tile_id, x, y, confidence, note)")
    p.add_argument("--run", required=True, help="output folder of `process` for the same clip")
    p.add_argument("--tag", default="agent-labeled", help="who labelled (agent-labeled, or for example user-labeled)")
    p.add_argument("--compare", default=None, help="a second labeler's CSV: adds the inter-labeler F1")
    p.add_argument("--compare-tag", default="user-labeled", help="who made the --compare labels")
    p.add_argument("--out", default=None, help="write the scores here as JSON (outside the tile folder)")
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_label_score)

    from wfglink.validate.command import add_arguments as validate_arguments

    p = sub.add_parser("validate", help="validation: led (dashcam LED turntable, room test, night drive) "
                                        "or the synthetic core, mismatch and coverage suites")
    validate_arguments(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("demo-gate", help="run the live screen headless on synthetic video and on the playlist; "
                                         "exit 0 if healthy")
    p.add_argument("--seconds", type=float, default=60.0)
    p.add_argument("--playlist", default=None, help="playlist file (default booth/playlist.yaml, config booth.playlist)")
    p.add_argument("--out", default="results/runs/demo_gate")
    p.set_defaults(func=cmd_demo_gate)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)
