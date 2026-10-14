"""Sitting 1: install check, check A and every recording, in one guided run.

Run through scripts/sitting1.sh (which installs first). Steps, in order:

  preflight     parts list, machine, disk space
  panel_video   writes PANEL_TEST.mp4 for the iPad (AirDrop it early)
  doctor        versions, fonts, screens
  check_a       permission, devices, formats, exposure-lock probe, every capture backend,
                .app retry if Terminal gets no frames; writes configs/booth_local.yaml
  live_view     20 s fullscreen live check on the external monitor
  benchmark     detector time per frame at 720p and 1080p
  recordings    iPhone LED (two speeds, ruler), dashcam LED (two speeds, ruler),
                iPad 240 fps slow motion, optional dashcam night drive
  analysis      LED speed error per device, panel scan, night-drive false tracks
  package       one upload folder with renamed files, hashes and report_sitting1.json

Everything is saved after each step; `--from STEP` resumes, `--add night_drive` adds the
optional drive later, and `--dry-run` exercises the whole flow on stand-in clips.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import now_shanghai
from wfglink.sitting import check_a
from wfglink.sitting.console import Console, Report, newest_files
from wfglink.sitting.panel import analyse_panel_clip, write_panel_video
from wfglink.sitting.recordings import SITTING1, VIDEO_SUFFIXES, basic_checks, intake, led_quick_check

LOCAL_CONFIG = PROJECT_ROOT / "configs" / "booth_local.yaml"
PARTS = ["iPhone 13 with its Lightning to USB-C cable", "iPad Air (charged) with the panel test video",
         "turntable or motorized platform, three orange LEDs with tracing paper",
         "the 블랙박스 dashcam with its SD card, a card reader and USB power",
         "tripod with phone clamp, tape measure or ruler, stopwatch (the iPhone clock app is fine)",
         "external monitor connected to the MacBook", "a room you can make dark"]
STEP_ORDER = ["preflight", "panel_video", "doctor", "check_a", "live_view", "benchmark",
              *[s.rid for s in SITTING1], "analysis", "package"]


def _noise_clip(path: Path, seconds: float, size: tuple[int, int] = (1280, 720), fps: int = 30) -> None:
    """Dark noisy night-drive stand-in (no embers), cheap to encode."""
    import av
    import numpy as np

    rng = np.random.default_rng(0)
    bank = [np.clip(rng.normal(18, 3, (size[1], size[0], 3)), 0, 255).astype(np.uint8) for _ in range(8)]
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = size[0], size[1], "yuv420p"
        s.options = {"preset": "ultrafast", "crf": "28"}
        for i in range(int(seconds * fps)):
            for pkt in s.encode(av.VideoFrame.from_ndarray(bank[i % 8], format="bgr24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)


def write_local_config(updates: dict[str, Any]) -> dict[str, Any]:
    current = {}
    if LOCAL_CONFIG.exists():
        current = yaml.safe_load(LOCAL_CONFIG.read_text()) or {}
    for section, values in updates.items():
        if isinstance(values, dict) and values:
            current.setdefault(section, {}).update(values)
    LOCAL_CONFIG.write_text("# Written by the sittings; machine-specific overrides of configs/default.yaml.\n"
                            + yaml.safe_dump(current, sort_keys=True, allow_unicode=True))
    return current


class Sitting1:
    def __init__(self, out: Path, console: Console, dry_run: bool = False, seconds: float = 6.0):
        self.out = out
        self.c = console
        self.dry = dry_run
        self.seconds = seconds
        self.cfg = load_config()
        self.report = Report(out / "report_sitting1.json", "wfglink_sitting1_report")
        self.standins: dict[str, Path] = {}

    # Steps ------------------------------------------------------------------------------
    def preflight(self) -> dict[str, Any]:
        self.c.header("1", "Before you start", 5)
        self.c.say("Have these on the table:")
        self.c.bullet(PARTS)
        missing = self.c.ask("missing_parts", "Anything missing? Type it, or press Enter if all present", "")
        disk = shutil.disk_usage(self.out)
        info = {"platform": sys.platform, "machine": platform.machine(), "python": platform.python_version(),
                "mac_ver": platform.mac_ver()[0] if sys.platform == "darwin" else None,
                "free_gb": round(disk.free / 1e9, 1), "out_dir": str(self.out), "missing_parts": missing}
        install_info = PROJECT_ROOT / ".venv" / ".install_info.json"
        if install_info.exists():
            info["install"] = json.loads(install_info.read_text())
        if disk.free < 5e9:
            self.c.warn("Less than 5 GB free on this disk; the recordings need about 2 GB.")
        self.c.ok(f"macOS {info['mac_ver'] or 'n/a'}, Python {info['python']}, {info['free_gb']} GB free")
        return info

    def panel_video(self) -> dict[str, Any]:
        self.c.header("2", "Panel test video for the iPad", 2)
        path = write_panel_video(self.out / "PANEL_TEST.mp4")
        self.c.ok(f"Wrote {path}")
        self.c.say("AirDrop PANEL_TEST.mp4 to the iPad now; you need it in the slow-motion step.")
        return {"file": path.name}

    def doctor(self) -> dict[str, Any]:
        self.c.header("3", "Environment check", 1)
        import subprocess

        args = [sys.executable, "-m", "wfglink", "doctor"] + ([] if self.dry else ["--gui"])
        res = subprocess.run(args, capture_output=True, text=True)
        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            data = {"ok": False, "stdout": res.stdout[-2000:], "stderr": res.stderr[-2000:]}
        if data.get("ok"):
            self.c.ok(f"Libraries, fonts and Qt are fine; {len(data.get('screens', []))} screen(s) found")
        else:
            self.c.fail("Environment problem; the report has the details. Continuing.")
        if len(data.get("screens", [])) < 2 and not self.dry:
            self.c.warn("Only one screen found. Connect the external monitor before the live view step.")
        return data

    def check_a(self) -> dict[str, Any]:
        self.c.header("4", "Check A: camera", 10)
        self.c.say("Set up the iPhone as a Continuity Camera:")
        self.c.bullet([
            "Connect the iPhone to the MacBook with the cable. Both signed in to the same Apple Account.",
            "Wi-Fi and Bluetooth ON on both (no network needs to be joined). Personal Hotspot OFF.",
            "Lock the iPhone, mount it in landscape on the tripod, rear camera facing the turntable.",
            "Turn on the three LEDs and start the turntable, so the camera sees moving lights.",
            "Mac menu bar > Video (green camera icon) > turn OFF Reactions, Center Stage, Portrait and Studio Light.",
            "If a USB webcam is available, plug it in too (it is tested as the fallback).",
        ])
        self.c.wait_enter("ready_a", "Press Enter when the iPhone is mounted and locked")
        out: dict[str, Any] = {}
        out["permission"] = check_a.permission()
        if out["permission"].get("status") not in ("authorized", "not_applicable"):
            self.c.fail(f"Camera permission is {out['permission'].get('status')}. "
                        "Open System Settings > Privacy & Security > Camera and allow Terminal, then rerun with --from check_a.")
        devs = check_a.devices(self.cfg)
        out["devices"] = devs
        iphone = devs.get("iphone")
        if iphone:
            self.c.ok(f"iPhone found: {iphone['name']}")
        else:
            self.c.warn("No Continuity Camera found. Check the cable, the Apple Account, and that the iPhone is locked and in landscape.")
        if devs.get("webcam"):
            self.c.ok(f"Webcam found: {devs['webcam']['name']}")
        out["exposure_probe"] = check_a.exposure_probe(iphone)
        self.c.say("Testing every capture path (about 6 s each)...")
        out["capture"] = check_a.capture_matrix(self.cfg, devs, self.seconds)
        for r in out["capture"]:
            if r.get("ok"):
                self.c.ok(f"{r['role']} via {r['backend']}: {r.get('width')}x{r.get('height')} at {r.get('fps_measured')} fps")
            elif r.get("stage") != "find":
                self.c.warn(f"{r['role']} via {r.get('backend')}: {r.get('error') or 'no frames'}")
        if iphone and not check_a.best_backend(out["capture"], "iphone"):
            self.c.warn("No usable iPhone frames from Terminal. Building the WFGLink app and retrying inside it...")
            out["app_fallback"] = check_a.app_fallback(iphone["unique_id"], self.out / "camera_test_app.json", self.seconds)
            self.c.say(f"  App retry: {out['app_fallback'].get('status')}")
        rec = check_a.recommended_config(devs, out["capture"], out.get("app_fallback"))
        out["recommended_config"] = rec
        if not self.dry:
            write_local_config({"camera": rec["camera"], "booth": rec["booth"]})
            self.c.ok(f"Saved camera settings to {LOCAL_CONFIG.relative_to(PROJECT_ROOT)}")
        return out

    def live_view(self) -> dict[str, Any]:
        self.c.header("5", "Live view on the external monitor", 3)
        self.c.say("A fullscreen picture appears for 20 s on the external monitor. Watch for orange circles on the LEDs.")
        self.c.say("Press L once during the test to switch the language. Esc ends early.")
        self.c.wait_enter("ready_live", "Press Enter to start the live view")
        from wfglink.io.capture import ChainConfig, SourceChain, SourceOption
        from wfglink.io.devices import AutoCameraSource, camera_backends, list_cameras, pick_camera
        from wfglink.io.sources import CameraSpec
        from wfglink.io.synthetic_live import SyntheticLiveSource
        from wfglink.ui.live_check import run_live_check

        cfg = load_config(local=not self.dry)
        devs = list_cameras().get("devices", [])
        spec = CameraSpec("", cfg["camera"]["width"], cfg["camera"]["height"], float(cfg["camera"]["fps"]))
        options = []
        for role in ("iphone", "webcam"):
            d = pick_camera(devs, role, cfg["camera"].get("iphone_uid") if role == "iphone" else None,
                            cfg["camera"].get("webcam_match") if role == "webcam" else None)
            if d:
                options.append(SourceOption(role, lambda d=d: AutoCameraSource(d, spec, camera_backends(cfg)), True, d["name"]))
        options.append(SourceOption("synthetic", lambda: SyntheticLiveSource(seed=1), False, "Synthetic (no camera)"))
        chain = SourceChain(options, ChainConfig.from_config(cfg))
        chain.start()
        try:
            stats = run_live_check(chain, duration_s=6.0 if self.dry else 20.0,
                                   screen=cfg["ui"]["screen"], lang=cfg["ui"]["language"], cfg=cfg)
        finally:
            chain.stop()
        stats["source_events"] = chain.events[-20:]
        stats["source_used"] = chain.status.key
        self.c.ok(f"Painted at {stats['paint_fps']} fps; processing {stats['processing_ms_median']} ms; "
                  f"latency {stats['latency_ms_median']} ms; screen '{stats['screen']['name']}'")
        stats["user_saw_external_monitor"] = self.c.ask_yes("saw_external", "Did the picture fill the EXTERNAL monitor?", True)
        stats["user_saw_circles"] = self.c.ask_yes("saw_circles", "Did orange circles follow the LEDs?", True)
        return stats

    def benchmark(self) -> dict[str, Any]:
        self.c.header("6", "Speed benchmark", 1)
        res = check_a.detector_benchmark(self.cfg, frames=30 if self.dry else 60)
        for k, v in res.items():
            self.c.ok(f"Detector at {k}: {v['median_ms']} ms per frame (p95 {v['p95_ms']} ms)")
        return res

    def recording(self, spec) -> dict[str, Any]:
        n = STEP_ORDER.index(spec.rid) + 1
        self.c.header(str(n), spec.title + (" (optional)" if spec.optional else ""), spec.minutes)
        if spec.optional and not self.c.ask_yes(f"do_{spec.rid}", "Do it now? (No: add it later with --add night_drive)", False):
            return {"status_note": "deferred"}
        self.c.bullet(spec.instructions)
        attempt = 0
        while True:
            attempt += 1
            self.c.wait_enter(f"recorded_{spec.rid}", "Press Enter when the recording is done")
            files = self._get_files(spec)
            if not files:
                self.c.warn("Skipped.")
                return {"status_note": "skipped"}
            entry = intake(files, spec, self.out)
            problems = basic_checks(spec, entry["files"])
            if spec.check == "led":
                entry["led_check"] = led_quick_check(self.out / entry["files"][0]["file"], cfg=self.cfg)
                problems += entry["led_check"].get("problems", []) + ([entry["led_check"]["error"]] if entry["led_check"].get("error") else [])
                if entry["led_check"].get("axis_ratio") is not None:
                    self.c.say(f"  Alignment: circle axis ratio {entry['led_check']['axis_ratio']} (1.000 is perfect)")
            if spec.check == "panel":
                entry["panel_check"] = analyse_panel_clip(self.out / entry["files"][0]["file"])
                if not entry["panel_check"].get("ok"):
                    problems.append("panel: " + str(entry["panel_check"].get("error")))
            entry["problems"] = problems
            entry["attempt"] = attempt
            if not problems:
                self.c.ok(f"{', '.join(f['file'] for f in entry['files'])} looks right")
                break
            for p in problems:
                self.c.warn(p)
            if attempt >= 3 or not self.c.ask_yes(f"redo_{spec.rid}_{attempt}", "Record this one again?", False):
                break
        for key, prompt, lo, hi in spec.inputs:
            entry.setdefault("inputs", {})[key] = self.c.ask_float(key, prompt, self._default_input(key), lo, hi)
        return entry

    def _get_files(self, spec) -> list[Path] | None:
        if self.dry:
            return [self._standin(spec)]
        if spec.device == "iphone":
            folders = [Path.home() / "Downloads", Path.home() / "Desktop"]
            sugg = newest_files(folders, VIDEO_SUFFIXES, max_age_h=3)
            prompt = "Which file is it? AirDrop puts it in Downloads"
        else:
            vols = [p for p in Path("/Volumes").iterdir() if p.name not in ("Macintosh HD", "Recovery")] if Path("/Volumes").exists() else []
            sugg = newest_files(vols, VIDEO_SUFFIXES, max_age_h=36, limit=8)
            prompt = "Which dashcam segment(s)? Several numbers separated by spaces are fine"
        return self.c.ask_files(f"files_{spec.rid}", prompt, sugg)

    def _default_input(self, key: str) -> float | None:
        if not self.dry:
            return None
        return {"t30_s1": 54.0, "t30_s2": 40.0, "dc_t30_s1": 54.0, "dc_t30_s2": 40.0, "ruler_cm": 30.0}.get(key)

    def _standin(self, spec) -> Path:
        from wfglink.sitting.standins import led_turntable_clip, panel_slowmo_clip

        tmp = self.out / "_standins"
        tmp.mkdir(exist_ok=True)
        path = tmp / f"{spec.rid}.mp4"
        if not path.exists():
            if spec.check == "led":
                rpm = 45.0 if spec.rid.endswith("s2") else 33.333
                led_turntable_clip(path, rpm=rpm, seconds=16, size=(1280, 720), fps=30)
            elif spec.check == "ruler":
                led_turntable_clip(path, rpm=0.0, seconds=6, size=(1280, 720), fps=30)
            elif spec.check == "panel":
                panel_slowmo_clip(path, seconds=2.5)
            else:
                _noise_clip(path, seconds=62)
        return path

    def analysis(self) -> dict[str, Any]:
        self.c.header(str(STEP_ORDER.index("analysis") + 1), "Analysis of the recordings", 4)
        out: dict[str, Any] = {}
        try:
            from wfglink.validate.led import analyze_led_recordings
        except ImportError:
            analyze_led_recordings = None
        steps = self.report.data["steps"]
        if analyze_led_recordings is None:
            out["led"] = {"status": "pending: the LED analysis module is not in this build; Claude analyses the uploaded files"}
            self.c.warn("LED speed analysis runs on Claude's side for this build.")
        else:
            out["led"] = analyze_led_recordings(steps, self.out, self.cfg)
            for dev, res in out["led"].items():
                if isinstance(res, dict) and "median_speed_error_pct" in res:
                    self.c.ok(f"{dev}: median track-speed error {res['median_speed_error_pct']}%")
        panel = steps.get("panel_240", {})
        if panel.get("panel_check"):
            out["panel"] = panel["panel_check"]
        try:
            from wfglink.validate.drive import false_tracks_per_minute
        except ImportError:
            false_tracks_per_minute = None
        drive = steps.get("dc_night_drive", {})
        if drive.get("files") and false_tracks_per_minute is not None:
            out["night_drive"] = false_tracks_per_minute([self.out / f["file"] for f in drive["files"]], self.cfg)
            for row in (out["led"].get("table") or []) if isinstance(out.get("led"), dict) else []:
                if row["device"] == "dashcam":
                    row["false_tracks_per_min_night_drive"] = out["night_drive"].get("false_tracks_per_min")
        elif drive.get("files"):
            out["night_drive"] = {"status": "pending: analysed on Claude's side for this build"}
        return out

    def package(self) -> dict[str, Any]:
        self.c.header(str(STEP_ORDER.index("package") + 1), "Upload", 8)
        files = sorted(p for p in self.out.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES and p.name != "PANEL_TEST.mp4")
        total = sum(p.stat().st_size for p in files)
        readme = self.out / "UPLOAD_README.txt"
        readme.write_text(
            "wfglink sitting 1 upload\n"
            "Upload this whole folder to Google Drive, Dropbox or iCloud Drive and share it as 'anyone with the link can view'.\n"
            "Then paste the link and the short summary printed in Terminal into the chat with Claude.\n"
            "Do not rename or re-encode the video files; their SHA-256 hashes are in report_sitting1.json.\n")
        self.c.say(f"Upload folder: {self.out}  ({len(files)} videos, {total / 1e9:.2f} GB)")
        self.c.bullet(["Upload the whole folder to Google Drive, Dropbox or iCloud Drive.",
                       "Share it as 'anyone with the link can view'.",
                       "Paste the link and the summary below into the chat."])
        return {"folder": str(self.out), "videos": [p.name for p in files], "total_bytes": total}

    # Driver -----------------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        s = self.report.data["steps"]
        ca = s.get("check_a", {})
        rec = ca.get("recommended_config", {})
        lv = s.get("live_view", {})
        rows = {sp.rid: ("ok" if s.get(sp.rid, {}).get("files") and not s.get(sp.rid, {}).get("problems")
                         else s.get(sp.rid, {}).get("status_note") or ("check" if s.get(sp.rid, {}).get("files") else "missing"))
                for sp in SITTING1}
        return {"camera": rec.get("camera"), "launcher": rec.get("booth", {}).get("launcher"),
                "webcam_works": rec.get("webcam_works"), "live_fps": lv.get("paint_fps"),
                "live_latency_ms": lv.get("latency_ms_median"), "recordings": rows,
                "led": s.get("analysis", {}).get("led"), "panel_axis": s.get("analysis", {}).get("panel", {}).get("scan_axis"),
                "minutes": round((time.monotonic() - self._t0) / 60, 1)}

    def run(self, start: str | None = None, steps: list[str] | None = None) -> dict[str, Any]:
        """Run steps in order. Without arguments, completed steps are skipped (resume)."""
        self._t0 = time.monotonic()
        explicit = steps is not None or start is not None
        if steps is None:
            steps = STEP_ORDER[STEP_ORDER.index(start):] if start else STEP_ORDER
        for name in steps:
            if not explicit and self.report.done(name):
                continue
            t0 = time.monotonic()
            spec = next((s for s in SITTING1 if s.rid == name), None)
            try:
                payload = self.recording(spec) if spec else getattr(self, name)()
                status = "done"
            except KeyboardInterrupt:
                self.c.warn("Stopped. Rerun the same command to continue where you left off.")
                raise
            except Exception as exc:  # record and carry on: one failing step must not lose the sitting
                payload = {"error": f"{type(exc).__name__}: {exc}"}
                status = "error"
                self.c.fail(f"{name}: {payload['error']}")
            payload["minutes"] = round((time.monotonic() - t0) / 60, 2)
            self.report.put(name, payload, status)
        self.report.data["summary"] = self.summary()
        self.report.data["finished_at"] = now_shanghai()
        self.report.save()
        text = json.dumps(self.report.data["summary"], ensure_ascii=False, separators=(",", ":"), default=str)
        self.c.say("\nPaste this summary to Claude:\n" + text)
        return self.report.data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wfglink sitting1", description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(Path.home() / f"wfglink-sitting1"), help="upload folder (also holds the report)")
    ap.add_argument("--from", dest="start", choices=STEP_ORDER, help="resume from this step")
    ap.add_argument("--only", choices=STEP_ORDER, help="run a single step")
    ap.add_argument("--add", choices=["night_drive"], help="add the optional night drive later")
    ap.add_argument("--dry-run", action="store_true", help="exercise everything on stand-in clips (no hardware)")
    ap.add_argument("--yes", action="store_true", help="accept every default (dry runs and tests)")
    ap.add_argument("--seconds", type=float, default=6.0, help="seconds per capture test")
    args = ap.parse_args(argv)
    out = Path(os.path.expanduser(args.out))
    out.mkdir(parents=True, exist_ok=True)
    s = Sitting1(out, Console(assume_yes=args.yes or args.dry_run), dry_run=args.dry_run, seconds=args.seconds)
    if args.add == "night_drive":
        s.c.answers["do_dc_night_drive"] = "y"
        s.run(steps=["dc_night_drive", "analysis", "package"])
    elif args.only:
        s.run(steps=[args.only])
    else:
        s.run(start=args.start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
