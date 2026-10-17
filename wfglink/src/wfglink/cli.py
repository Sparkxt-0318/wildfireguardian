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
    from pathlib import Path

    from wfglink.config import load_config
    from wfglink.ui.booth_app import ember_spec, run_live, source_spec

    if args.high_precision:
        cfg = _hp_cfg(args.high_precision, args.config, local=True)
    else:
        cfg = load_config(*(args.config or []), local=True)
    spec = source_spec(synthetic=args.synthetic, playlist=args.playlist, clip=args.clip, cfg=cfg)
    if args.fake_camera and not Path(args.fake_camera).is_file():
        raise SystemExit(f"live: --fake-camera {args.fake_camera}: file not found")
    res = run_live(cfg, source=spec, screen=args.screen, lang=args.lang, limits_screen=args.limits_screen,
                   duration_s=args.duration, screenshot=args.screenshot, heartbeat=args.heartbeat,
                   ember=ember_spec(synthetic=args.synthetic, fake_camera=args.fake_camera),
                   start_mode="ember" if args.ember else "fire")
    if args.report:
        with open(args.report, "w") as f:
            json.dump(res, f, indent=2, default=str)
    return 0 if (res["quit_confirmed"] or (args.duration and not res["signal"])) else 1


def _hp_cfg(method: str, extra: list[str] | None, local: bool = False, dump: bool = False) -> dict:
    """The config of high-precision mode (configs/high_precision.yaml over default.yaml, then the extra
    configs, then the method); wfglink.verify is imported only here."""
    from wfglink.verify.config import hp_config

    try:
        return hp_config(method, extra_configs=extra or (), overrides={"verify": {"dump": True}} if dump else None,
                         local=local)
    except ValueError as exc:
        raise SystemExit(f"--high-precision: {exc}") from None


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

    if args.verify_dump and not args.high_precision:
        raise SystemExit("--verify-dump needs --high-precision")
    if args.high_precision:
        cfg = _hp_cfg(args.high_precision, args.config, dump=args.verify_dump)
    else:
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
    if "high_precision" in s:
        hp = s["high_precision"]
        print(f"high precision ({hp['method']}, {hp['profile']}): {hp['status']}, {hp['accepted_tracks']} accepted "
              f"tracks, CPC gross {hp['cpc_gross']} -> {out / hp['folder']}")
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


def cmd_cameras(args: argparse.Namespace) -> int:
    """List the cameras and the one config picks; --request asks for camera permission (macOS)."""
    from wfglink.config import load_config
    from wfglink.io.camera import explain_pick, list_cameras, permission_status, pick_camera, request_permission
    from wfglink.io.camera import video_effects

    cfg = load_config(*(args.config or []), local=True)
    status = (request_permission(float((cfg.get("camera") or {}).get("permission_timeout_s", 30)))
              if args.request else permission_status())
    devs = list_cameras()
    picked = pick_camera(cfg, devs)
    effects = video_effects()
    if args.json:
        print(json.dumps({"permission": status, "cameras": devs, "picked": picked, "why": explain_pick(cfg, devs),
                          "video_effects": effects}, indent=2, ensure_ascii=False, default=str))
    else:
        for d in devs:
            mark = "*" if picked is not None and d["unique_id"] == picked["unique_id"] else " "
            use = "usable" if d["usable"] else f"not used: {d['why']}"
            print(f"{mark} {d['name']}  ({d['kind']}, OpenCV index {d['index']}, {use})")
        if not devs:
            print("no camera found")
        print(explain_pick(cfg, devs))
        print(f"camera permission: {status}")
        if status in ("denied", "restricted"):
            from wfglink.io.camera import PERMISSION_FIX

            print(f"fix: {PERMISSION_FIX}")
        on = [k for k, v in effects.items() if v]
        if on:
            print("video effects on (turn them off in Control Center, Video Effects, while the booth runs): "
                  + ", ".join(on))
    ok = picked is not None and status in ("authorized", "unsupported")
    if args.open and ok:
        ok = _try_camera(cfg, float(args.open))
    return 0 if ok else 1


def _try_camera(cfg: dict, seconds: float) -> bool:
    """Open the picked camera for a few seconds: backend, size and frame rate actually delivered."""
    import time

    from wfglink.io.camera import CameraSource
    from wfglink.io.sources import SourceError

    src = CameraSource(cfg)
    try:
        src.open()
    except SourceError as exc:
        print(f"camera did not open: {exc}")
        return False
    ts = []
    t_end = time.monotonic() + seconds
    size = None
    while time.monotonic() < t_end:
        f = src.read()
        if f is not None:
            ts.append(f.t)
            size = f.image.shape[1::-1]
    src.close()
    fps = (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) > 1 and ts[-1] > ts[0] else 0.0
    info = src.info
    print(f"opened {info.get('name')} with {info.get('backend')} ({info.get('options')}): native "
          f"{info.get('native_size')}, delivered {list(size) if size else None}, {len(ts)} frames in {seconds:g} s, "
          f"{fps:.1f} fps")
    return len(ts) > 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from wfglink.config import LOCAL_CONFIG, load_config
    from wfglink.ember.calibrate import calibrate_live, calibrate_video, write_local
    from wfglink.io.sources import SourceError

    cfg = load_config(*(args.config or []), local=True)
    dist = float(args.distance_m or (cfg.get("ember") or {}).get("distance_m", 2.0))
    try:
        if args.video:
            res = calibrate_video(args.video, cfg, dist)
        else:
            source = None
            if args.fake_camera:
                from wfglink.io.camera import FakeCameraSource

                source = FakeCameraSource(args.fake_camera, realtime=True, cfg=cfg)
            res = calibrate_live(cfg, dist, screen=args.screen, source=source)
    except (SourceError, ValueError, FileNotFoundError) as exc:
        print(f"calibrate: {exc}", file=sys.stderr)
        return 2
    if res is None:
        print("calibrate: cancelled or no stable result (hold the target flat, all four markers in the picture)",
              file=sys.stderr)
        return 1
    import datetime as _dt

    if not res["stable"]:
        # An unsteady result would be used as calibrated; the earlier calibration is kept instead.
        print(f"calibrate: not stable after {res['frames']} frames (spread {res['spread']:.4f}): nothing written. "
              "Hold the target flat and still, all four markers in the picture, and run it again.", file=sys.stderr)
        return 1
    nominal = float((cfg.get("camera") or {}).get("hfov_deg", 70.0))
    if abs(res["hfov_deg"] - nominal) > 15.0:
        print(f"calibrate: WARNING: the field of view came out {res['hfov_deg']:.1f} degrees, far from the camera's "
              f"nominal {nominal:g}: check that the target is {dist:g} m from the lens and was printed at 100 percent "
              "(its 100 mm line measures 100 mm)", file=sys.stderr)
    record = {"date": _dt.datetime.now().astimezone().isoformat(timespec="seconds"), "camera": res.get("camera"),
              "unique_id": res.get("unique_id"), "backend": res.get("backend"), "size": res["size"],
              "focal_px": res["focal_px"], "hfov_deg": res["hfov_deg"], "distance_m": res["distance_m"],
              "m_per_px": res["m_per_px"], "target": res["target"], "frames": res["frames"], "spread": res["spread"],
              "rms_px": res["rms_px"], "stable": res["stable"]}
    if args.video:
        record["video"] = str(args.video)
    path = write_local(record, args.out or LOCAL_CONFIG)
    print(f"focal length {res['focal_px']:.1f} px at {res['size'][0]}x{res['size'][1]} (horizontal field of view "
          f"{res['hfov_deg']:.1f} degrees); at {dist:g} m, 1 px = {res['m_per_px'] * 1000:.2f} mm "
          f"({res['frames']} frames, spread {res['spread']:.4f}, reprojection {res['rms_px']:.2f} px)")
    print(f"-> {path} (camera.focal_px, ember.distance_m, ember.calibration)")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    from wfglink.config import load_config
    from wfglink.ember.record import record
    from wfglink.io.sources import SourceError

    cfg = load_config(*(args.config or []), local=True)
    try:
        res = record(cfg, args.name, args.seconds, out_dir=args.out_dir, fake=args.fake_camera,
                     preview=not args.no_preview, force=args.force, screen=args.screen)
    except (SourceError, ValueError, FileExistsError) as exc:
        print(f"record: {exc}", file=sys.stderr)
        return 2
    print(f"{res['file']}: {res['frames']} frames, {res['seconds']} s, {res['size']}, mean {res['fps_mean']} fps, "
          f"longest gap {res['interval_max_ms']} ms ({res.get('camera')})"
          + (", cancelled" if res.get("cancelled") else ""))
    if res.get("error"):
        print(f"record: {res['error']}", file=sys.stderr)
        return 1
    return 0 if res["frames"] and not res.get("cancelled") else 1


def cmd_demo_gate(args: argparse.Namespace) -> int:
    from wfglink.ui.demo_gate import demo_gate

    return demo_gate(seconds=args.seconds, playlist=args.playlist, out=args.out, config=args.config)


def cmd_verify(args: argparse.Namespace) -> int:
    """`verify ...`: the verifier's offline tools; wfglink/verify/cli_tools.py is imported only now."""
    try:
        from wfglink.verify.cli_tools import add_parser
    except ImportError as exc:
        raise SystemExit(f"verify: the offline tools are not available ({exc})") from None
    parser = argparse.ArgumentParser(prog="wfglink")
    add_parser(parser.add_subparsers(dest="command", required=True))
    sub_args = parser.parse_args(["verify", *args.verify_args])
    return int(sub_args.func(sub_args) or 0)


def _add_verify(sub) -> None:
    """Register `verify`: the arguments are parsed by wfglink.verify.cli_tools.add_parser(sub) in
    cmd_verify, so no other command imports wfglink.verify."""
    p = sub.add_parser("verify", add_help=False, prefix_chars="+",
                       help="high-precision verifier tools (audit, sheets, windows, truth, dataset, train, calibrate, "
                            "replay, freeze, eval, bench, identity); `verify -h` lists them")
    p.add_argument("verify_args", nargs="*")
    p.set_defaults(func=cmd_verify)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wfglink", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the setup: python, packages, fonts, screens, video, data, clips, camera (one OK or FAIL line each)")
    p.add_argument("--json", action="store_true", help="print every detail as JSON")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("live", help="the booth screen: approved clips analysed live as they play (or synthetic video); "
                                    "M switches to ember mode (the camera), A to the raw picture")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--synthetic", action="store_true",
                     help="play generated video instead of clips (and a generated phone scene in ember mode)")
    src.add_argument("--playlist", default=None, help="playlist file (default booth/playlist.yaml, config booth.playlist)")
    src.add_argument("--clip", default=None, help="play one video file, or one clip settings file data/clips/<id>.yaml")
    p.add_argument("--ember", action="store_true", help="start in ember mode (\"Become an ember\") instead of fire mode")
    p.add_argument("--fake-camera", default=None, metavar="FILE",
                   help="ember mode plays this video file as if it were the camera (no camera is opened)")
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
    p.add_argument("--high-precision", nargs="?", const="rules", default=None, metavar="METHOD",
                   help="high-precision mode: count and draw only tracks accepted by METHOD (accept_all, rules, "
                        "patch, temporal; default rules); configs/high_precision.yaml")
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
    p.add_argument("--high-precision", nargs="?", const="rules", default=None, metavar="METHOD",
                   help="also write high_precision/: tables, counts and a frame-level run of the tracks accepted by "
                        "METHOD (accept_all, rules, patch, temporal; default rules); the legacy outputs are unchanged")
    p.add_argument("--verify-dump", action="store_true",
                   help="with --high-precision: also write per-hit features and patches (offline replay, training)")
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

    p = sub.add_parser("validate", help="validation: ember (phones: synthetic scenes, ember_free, ember_ruler) "
                                        "or the synthetic core, mismatch and coverage suites")
    validate_arguments(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("cameras", help="list the cameras and the one config picks (camera.name); --request asks "
                                       "for camera permission")
    p.add_argument("--request", action="store_true", help="ask for camera permission (the macOS dialog) first")
    p.add_argument("--open", type=float, nargs="?", const=3.0, default=None, metavar="SECONDS",
                   help="also open the picked camera for a few seconds (default 3): backend, size, frame rate")
    p.add_argument("--json", action="store_true", help="print every detail as JSON")
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_cameras)

    p = sub.add_parser("calibrate", help="focal length from the printed A4 target held at the standing spot "
                                         "(writes configs/booth_local.yaml)")
    p.add_argument("--distance-m", type=float, default=None,
                   help="camera lens to the target's centre, m (default ember.distance_m, 2.0)")
    p.add_argument("--video", default=None, help="run on a recording instead of the camera (no window)")
    p.add_argument("--out", default=None, help="config file to write (default configs/booth_local.yaml)")
    p.add_argument("--screen", default=None, help="screen for the preview (default ui.screen: auto)")
    p.add_argument("--fake-camera", default=None, help="show a video file as the camera, with the preview (tests)")
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("record", help="record the camera to data/raw/NAME.mp4 (H.264) with a countdown on screen")
    p.add_argument("name", help="file name without extension: ember_free or ember_ruler")
    p.add_argument("--seconds", type=float, default=None, help="length after the countdown (default ember.record.seconds)")
    p.add_argument("--out-dir", default=None, help="folder (default data/raw)")
    p.add_argument("--force", action="store_true", help="replace an existing file")
    p.add_argument("--no-preview", action="store_true", help="no window (the countdown still runs)")
    p.add_argument("--fake-camera", default=None, help="record a video file or a generated scene instead (tests)")
    p.add_argument("--screen", default=None, help="screen for the preview (default ui.screen: auto)")
    p.add_argument("--config", nargs="*")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("demo-gate", help="run the live screen headless: fire mode on synthetic video and on the playlist, "
                                         "ember mode on a generated phone scene; exit 0 if healthy")
    p.add_argument("--seconds", type=float, default=60.0, help="seconds of each run")
    p.add_argument("--playlist", default=None, help="playlist file (default booth/playlist.yaml, config booth.playlist)")
    p.add_argument("--out", default="results/runs/demo_gate")
    p.add_argument("--config", nargs="*", help="extra YAML config files")
    p.set_defaults(func=cmd_demo_gate)

    _add_verify(sub)   # verify subcommands: wfglink.verify.cli_tools.add_parser(sub), imported lazily
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)
