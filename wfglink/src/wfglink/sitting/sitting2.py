"""Sitting 2: check B on the real booth loop, the unplug test, local config and the overnight soak.

Run through scripts/sitting2.sh (which installs first). Steps, in order:

  preflight           versions, git commit, free disk, sitting 1 settings, screens, cameras
  booth_clip          prepares the booth clip (C1, else C9, else C5) at hold 2 and 3 into
                      data/booth/; you AirDrop the hold-2 file to the iPad and loop it
  check_b_yield       booth runs through the iPhone with frame codes: clean-frame yield at
                      hold 2, retried at hold 3 when below sitting2.yield_min; chooses the
                      hold factor and the screen
  unplug_test         60 s run; you unplug and replug the iPhone when told; time to fall
                      back and time to recover
  webcam_test         30 s with the USB webcam (only when one is listed)
  worker_mode         equal runs in thread and process worker mode; the faster one wins
  write_local_config  merges hold factor, replay clip, worker mode and screen into
                      configs/booth_local.yaml (sitting 1's settings are kept)
  soak_start          starts booth/booth.sh and a heartbeat sampler in the background for
                      the night (check C)
  finish              (--finish, in the morning) stops both, analyses the soak, asks about
                      iPhone heat, prints the summary to paste to Claude

Everything is saved after each step; `--from STEP` resumes and `--only STEP` repeats one.
`--dry-run` runs the whole flow here on a synthetic stand-in clip filmed by the
camera-in-the-loop simulator (wfglink.screen.loopsim), with a simulated unplug, a short
soak and an automatic finish; it writes its local config into the output folder only.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import yaml

from wfglink import PROJECT_ROOT, __version__
from wfglink.config import deep_merge, load_config
from wfglink.provenance import git_state, now_shanghai, rel, sha256_file
from wfglink.sitting.console import Console, Report

LOCAL_CONFIG = PROJECT_ROOT / "configs" / "booth_local.yaml"
BOOTH_SH = PROJECT_ROOT / "booth" / "booth.sh"
LOG_DIR = PROJECT_ROOT / "logs"
HEARTBEAT = LOG_DIR / "heartbeat.json"
BOOTH_LOG = LOG_DIR / "booth.log"
SITTING1_REPORT = Path.home() / "wfglink-sitting1" / "report_sitting1.json"
CLIP_PATTERNS = ("C1*.mp4", "C9*", "C5*")
VIDEO_FPS = 30.0      # booth-prep writes 30 fps files; a source frame lasts `hold` of them

STEP_ORDER = ["preflight", "booth_clip", "check_b_yield", "unplug_test", "webcam_test", "worker_mode",
              "write_local_config", "soak_start"]
ALL_STEPS = STEP_ORDER + ["finish"]
MINUTES = {"preflight": 3, "booth_clip": 5, "check_b_yield": 7, "unplug_test": 3, "webcam_test": 3,
           "worker_mode": 3, "write_local_config": 1, "soak_start": 3, "finish": 5}
PARTS = ["iPhone 13 with its Lightning to USB-C cable, and the tripod with the phone clamp",
         "iPad Air on its rigid stand, with its charger plugged in",
         "the black cloth hood over the iPad and the iPhone",
         "the external monitor connected to the MacBook, and the MacBook on its charger",
         "the USB webcam, if you have it (tested as the second camera)"]


# Pure helpers (unit tested) -----------------------------------------------------------------

def choose_hold(y2: float | None, y3: float | None, yield_min: float) -> dict[str, Any]:
    """Hold factor from the clean-frame yields: keep 2 when it reaches yield_min, else 3 when it
    is better, else 2."""
    if y2 is not None and y2 >= yield_min:
        return {"hold_factor": 2, "reason": f"hold 2 yield {y2:.2f} reaches {yield_min:.2f}", "meets_min": True}
    if y3 is not None and (y2 is None or y3 > y2):
        return {"hold_factor": 3, "reason": (f"hold 2 yield {'n/a' if y2 is None else f'{y2:.2f}'} is below "
                                             f"{yield_min:.2f}; hold 3 gives {y3:.2f}"), "meets_min": y3 >= yield_min}
    return {"hold_factor": 2, "reason": "hold 3 was not better (or not measured); keeping the default",
            "meets_min": bool(y2 is not None and y2 >= yield_min)}


def unplug_timing(events: list[dict[str, Any]], primary: str, t_unplug: float, t_replug: float,
                  recover_max_s: float, early_s: float = 5.0) -> dict[str, Any]:
    """Fallback and recovery times from SourceChain events (monotonic 't' seconds).

    detect_s: unplug prompt to the primary source's failure; fall_back_s: unplug prompt to
    another source being active; recover_s: replug prompt to the primary being active again.
    """
    ev = sorted(events or [], key=lambda e: e.get("t", 0.0))
    fail = next((e for e in ev if e.get("event") == "failed" and e.get("key") == primary
                 and e["t"] >= t_unplug - early_s), None)
    t_from = fail["t"] if fail else t_unplug - early_s
    fallback = next((e for e in ev if e.get("event") == "activated" and e.get("key") != primary and e["t"] >= t_from), None)
    t_from2 = fallback["t"] if fallback else t_from
    recover = next((e for e in ev if e.get("event") == "activated" and e.get("key") == primary and e["t"] > t_from2), None)
    out: dict[str, Any] = {
        "primary": primary, "fallback_key": fallback.get("key") if fallback else None,
        "detect_s": round(fail["t"] - t_unplug, 2) if fail else None,
        "fall_back_s": round(fallback["t"] - t_unplug, 2) if fallback else None,
        "recover_s": round(recover["t"] - t_replug, 2) if recover else None,
        "recover_max_s": recover_max_s,
    }
    out["pass"] = bool(fallback and recover and out["recover_s"] <= recover_max_s)
    if not fail and not fallback:
        out["note"] = "the primary source never failed: was the cable unplugged?"
    elif not recover:
        out["note"] = "the primary source did not come back within the run"
    return out


def merge_local_config(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Merge section dicts into the local config, keeping every key not being updated."""
    out = dict(existing or {})
    for section, values in updates.items():
        if isinstance(values, dict):
            out[section] = {**(out.get(section) or {}), **values}
    return out


def find_booth_clip(raw: Path) -> Path | None:
    for pattern in CLIP_PATTERNS:
        for p in sorted(raw.glob(pattern)):
            if p.is_file() and not p.name.endswith(".part") and p.stat().st_size > 0:
                return p
    return None


def run_stats(res: dict[str, Any], key: str, hold: int | None = None) -> dict[str, Any]:
    """The numbers check B needs from a run_booth report."""
    st = (res.get("pipelines") or {}).get(key) or {}
    secs = float(res.get("seconds") or 0.0)
    proc_fps = (res.get("last") or {}).get("fps")
    out = {"source_key": key, "seconds": secs, "frames": res.get("frames"), "paints": res.get("paints"),
           "paint_fps": round(res["paints"] / secs, 2) if secs and res.get("paints") is not None else None,
           "processing_fps": round(proc_fps, 2) if proc_fps else None, "errors": res.get("errors", []),
           "source_at_end": res.get("source")}
    for k in ("frames_in", "frames_analysed", "frames_duplicate", "frames_unclean", "frames_blended", "frames_torn",
              "frames_no_code", "loops", "proc_ms_median", "proc_ms_p95"):
        out[k] = st.get(k)
    y = st.get("clean_frame_yield")
    out["clean_frame_yield"] = round(y, 4) if y is not None else None
    n = st.get("frames_in") or 0
    if n:
        out["blended_fraction"] = round((st.get("frames_blended") or 0) / n, 4)
        out["torn_fraction"] = round((st.get("frames_torn") or 0) / n, 4)
        out["no_code_fraction"] = round((st.get("frames_no_code") or 0) / n, 4)
    # Source coverage (approximate): source frames analysed at least once per loop over the
    # source frames the iPad showed while the pipeline was fed (frames_in / processing fps).
    if hold and n and proc_fps and st.get("frames_analysed") is not None:
        shown = n / proc_fps * VIDEO_FPS / hold
        out["source_coverage_est"] = round(min(1.0, st["frames_analysed"] / shown), 3) if shown > 0 else None
    fails = [e for e in res.get("source_events", []) if e.get("event") == "failed"]
    out["source_failures"] = len(fails)
    return out


# Process helpers -----------------------------------------------------------------------------

def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.waitpid(pid, os.WNOHANG)       # reap it if it is our own child
    except (ChildProcessError, OSError):
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(st) and not st.startswith("Z")


def _command(pid: int) -> str:
    return subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def _wait_gone(pid: int, timeout_s: float) -> bool:
    t_end = time.monotonic() + timeout_s
    while time.monotonic() < t_end:
        if not _alive(pid):
            return True
        time.sleep(0.1)
    return not _alive(pid)


# The sitting ---------------------------------------------------------------------------------

class Sitting2:
    def __init__(self, out: Path, console: Console, dry_run: bool = False, seconds: float | None = None,
                 soak_seconds: float | None = None):
        self.out = out
        self.c = console
        self.dry = dry_run
        self.cfg = load_config(local=not dry_run)
        self.s2 = self.cfg["sitting2"]
        self.seconds = float(seconds) if seconds else float(self.s2["dry_seconds"] if dry_run else self.s2["run_seconds"])
        self.soak_seconds = float(soak_seconds or self.s2["dry_soak_seconds"])
        self.report = Report(out / "report_sitting2.json", "wfglink_sitting2_report")
        was_dry = self.report.get("preflight").get("dry_run")
        if was_dry is not None and bool(was_dry) != dry_run:
            # Never resume a dry run as the real sitting (or the other way round).
            self.report.path.replace(self.report.path.with_name(f"report_sitting2.{'dry' if was_dry else 'real'}.old.json"))
            self.report = Report(out / "report_sitting2.json", "wfglink_sitting2_report")
        self.local_path = out / "booth_local.yaml" if dry_run else LOCAL_CONFIG
        self.booth_dir = out / "booth" if dry_run else PROJECT_ROOT / "data" / "booth"
        self.primary = "loopsim" if dry_run else "iphone"
        self._t0 = time.monotonic()

    # Configuration and runs ------------------------------------------------------------------
    def _cfg(self, **sections: dict[str, Any]) -> dict[str, Any]:
        cfg = load_config(local=not self.dry)
        if self.dry and self.local_path.exists():
            cfg = deep_merge(cfg, yaml.safe_load(self.local_path.read_text()) or {})
        return deep_merge(cfg, sections)

    def _hold_file(self, hold: int) -> Path:
        files = self.report.get("booth_clip").get("hold_files") or {}
        if str(hold) not in files:
            raise RuntimeError("no prepared booth clip: run the booth_clip step first")
        return Path(files[str(hold)])

    def _chosen(self) -> tuple[int, Path]:
        hold = int(self.report.get("check_b_yield").get("hold_factor") or self.cfg["booth"]["hold_factor"])
        return hold, self._hold_file(hold)

    def _camera_chain(self, path: Path, unplug: bool = False) -> dict[str, Any]:
        if self.dry:
            return {"chain": [f"loopsim-unplug:{path}", "replay"] if unplug else [f"loopsim:{path}"]}
        return {} if unplug else {"chain": ["iphone"]}

    def _booth_cfg(self, hold: int, path: Path, mode: str = "thread", unplug: bool = False,
                   chain: dict[str, Any] | None = None) -> dict[str, Any]:
        """Config for a booth run on the prepared clip; refuses to run without its frame codes,
        because a run without codes analyses every frame and would report a yield of 1."""
        from wfglink.ui.booth_app import load_booth_meta

        cfg = self._cfg(booth={"replay_clip": str(Path(path).resolve()), "hold_factor": hold},
                        live={"worker_mode": mode}, camera=chain if chain is not None else self._camera_chain(path, unplug))
        if load_booth_meta(cfg) is None:
            raise RuntimeError(f"booth-prep metadata for {path} not found; the frame codes cannot be used")
        return cfg

    def _booth(self, cfg: dict[str, Any], source: str, seconds: float) -> dict[str, Any]:
        from wfglink.ui.booth_app import run_booth

        return run_booth(cfg, source=source, duration_s=seconds)

    def _screen_names(self) -> tuple[list[str], str | None]:
        try:
            from PySide6.QtWidgets import QApplication

            from wfglink.ui.live_check import choose_screen

            app = QApplication.instance() or QApplication(sys.argv[:1])
            names = [s.name() for s in app.screens()]
            used = choose_screen(app, self.cfg["ui"]["screen"]).name()
            return names, used
        except Exception:
            return [], None

    # Steps -----------------------------------------------------------------------------------
    def preflight(self) -> dict[str, Any]:
        self.c.header("1", "Before you start", MINUTES["preflight"])
        self.c.say("Have these on the table:")
        self.c.bullet(PARTS)
        missing = self.c.ask("missing_parts", "Anything missing? Type it, or press Enter if all present", "")
        info: dict[str, Any] = {"platform": sys.platform, "machine": platform.machine(),
                                "python": platform.python_version(),
                                "mac_ver": platform.mac_ver()[0] if sys.platform == "darwin" else None,
                                "missing_parts": missing, "out_dir": str(self.out), "dry_run": self.dry}
        versions = {"wfglink": __version__}
        for mod in ("numpy", "cv2", "av", "PySide6", "yaml"):
            try:
                versions[mod] = getattr(__import__(mod), "__version__", "?")
            except Exception as exc:
                versions[mod] = f"missing: {type(exc).__name__}"
        info["versions"] = versions
        info["git"] = git_state()
        disk = shutil.disk_usage(self.out)
        info["free_gb"] = round(disk.free / 1e9, 1)
        if info["free_gb"] < float(self.s2["free_disk_min_gb"]):
            self.c.warn(f"Only {info['free_gb']} GB free; the booth clips and the overnight log need a few GB.")
        if LOCAL_CONFIG.exists():
            info["sitting1_local_config"] = yaml.safe_load(LOCAL_CONFIG.read_text()) or {}
            self.c.ok(f"Sitting 1 settings found: {rel(LOCAL_CONFIG)}")
        else:
            info["sitting1_local_config"] = None
            if not self.dry:
                self.c.warn("No configs/booth_local.yaml from sitting 1; the defaults are used (camera backend auto).")
        s1 = self._sitting1()
        info["sitting1_report"] = {k: s1.get(k) for k in ("camera", "launcher", "live_fps", "panel_axis")} if s1 else None
        args = [sys.executable, "-m", "wfglink", "doctor"] + ([] if self.dry else ["--gui"])
        res = subprocess.run(args, capture_output=True, text=True, timeout=180)
        try:
            doc = json.loads(res.stdout)
        except json.JSONDecodeError:
            doc = {"ok": False, "stderr": res.stderr[-1500:]}
        info["screens"] = doc.get("screens", [])
        info["doctor_ok"] = doc.get("ok")
        if len(info["screens"]) < 2 and not self.dry:
            self.c.warn("Only one screen found. Connect the external monitor before check B.")
        try:
            from wfglink.io.devices import list_cameras, pick_camera

            devs = list_cameras().get("devices", [])
            iph = pick_camera(devs, "iphone", self.cfg["camera"].get("iphone_uid"))
            web = pick_camera(devs, "webcam", None, self.cfg["camera"].get("webcam_match"))
            info["cameras"] = {"all": [d.get("name") for d in devs], "iphone": iph and iph.get("name"),
                               "webcam": web and web.get("name")}
        except Exception as exc:
            info["cameras"] = {"error": f"{type(exc).__name__}: {exc}"}
        if not self.dry and not info["cameras"].get("iphone"):
            self.c.warn("No iPhone camera listed yet. Connect it with the cable before check B.")
        self.c.ok(f"wfglink {__version__}, commit {str(info['git'].get('git_commit'))[:10]}, "
                  f"Python {info['python']}, {info['free_gb']} GB free, {len(info['screens'])} screen(s)")
        return info

    def _sitting1(self) -> dict[str, Any] | None:
        if not SITTING1_REPORT.exists():
            return None
        try:
            return json.loads(SITTING1_REPORT.read_text()).get("summary") or {}
        except (OSError, ValueError):
            return None

    def booth_clip(self) -> dict[str, Any]:
        from wfglink.screen.booth_prep import prepare

        self.c.header("2", "Booth clip for the iPad", MINUTES["booth_clip"])
        standin = False
        if self.dry:
            clip = self._standin_clip()
            standin = True
        else:
            clip = find_booth_clip(PROJECT_ROOT / "data" / "raw")
            if clip is None:
                self.c.warn("No C1, C9 or C5 clip in data/raw yet; using a synthetic stand-in clip for tonight.")
                clip = self._standin_clip()
                standin = True
        self.c.say(f"Clip: {clip.name}")
        meta_path = self.booth_dir / f"{clip.stem}_booth.json"
        meta = None
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                ok = meta.get("input_sha256") == sha256_file(clip) and all(
                    (self.booth_dir / meta["outputs"][h]["file"]).exists() for h in ("2", "3"))
                meta = meta if ok else None
            except (OSError, ValueError, KeyError):
                meta = None
        reused = meta is not None
        if meta is None:
            self.c.say("Preparing the booth files (corner codes, held frames); this takes a few minutes...")
            meta = prepare(clip, self.booth_dir, holds=(2, 3), max_seconds=self.s2.get("booth_clip_max_s"))
        files = {h: str(self.booth_dir / meta["outputs"][h]["file"]) for h in ("2", "3")}
        self.c.ok(f"Ready: {Path(files['2']).name} and {Path(files['3']).name} in {self.booth_dir}")
        if self.dry:
            self.c.say("Dry run: the loop simulator plays the hold-2 file; no iPad needed.")
        else:
            self.c.say("Put the clip on the iPad and loop it:")
            self.c.bullet([
                f"In Finder, open {self.booth_dir} and AirDrop {Path(files['2']).name} and "
                f"{Path(files['3']).name} to the iPad (the script says if the hold-3 file is needed).",
                "Play the hold-2 file full screen in a player that repeats one video (for example VLC: Repeat One), "
                "with the player controls hidden. All four corner patterns must be visible.",
                "iPad: brightness about 80 percent; Auto-Brightness, True Tone and Night Shift off; "
                "Auto-Lock Never; charger plugged in.",
                "iPhone on the tripod in landscape, about 30 to 50 cm away, so the iPad screen fills about two "
                "thirds of the picture, slightly off square. Black cloth hood over both.",
                "Mac menu bar > Video: Reactions, Center Stage, Portrait and Studio Light off.",
            ])
            self.c.wait_enter("ipad_ready", "Press Enter when the iPad is looping the hold-2 file")
        return {"clip": rel(clip), "clip_id": clip.stem, "standin": standin, "reused": reused,
                "hold_files": files, "playback_speed": {h: meta["outputs"][h]["playback_speed"] for h in ("2", "3")},
                "source_duration_s": meta.get("source_duration_s"), "layout": meta.get("layout")}

    def _standin_clip(self) -> Path:
        import av

        from wfglink.io.synthetic_live import SyntheticLiveSource

        w, h = (int(v) for v in self.s2["dry_clip_size"])
        path = self.out / "standin" / "S2_STANDIN.mp4"
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        src = SyntheticLiveSource(width=w, height=h, realtime=False, seed=3)
        src.open()
        n = int(round(float(self.s2["dry_clip_seconds"]) * 30))
        with av.open(str(path), "w") as c:
            s = c.add_stream("libx264", rate=30)
            s.width, s.height, s.pix_fmt = w, h, "yuv420p"
            s.options = {"crf": "18", "preset": "veryfast"}
            for _ in range(n):
                for pkt in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                    c.mux(pkt)
            for pkt in s.encode():
                c.mux(pkt)
        return path

    def _yield_run(self, hold: int) -> dict[str, Any]:
        path = self._hold_file(hold)
        cfg = self._booth_cfg(hold, path)
        source = "auto" if self.dry else "camera"
        self.c.say(f"Running the booth for {self.seconds:g} s at hold {hold} (watch the external monitor)...")
        try:
            res = self._booth(cfg, source, self.seconds)
        except ValueError as exc:    # SourceChain with no option: no iPhone listed
            return {"hold": hold, "file": Path(path).name, "error": f"no camera to run: {exc}"}
        st = run_stats(res, self.primary, hold)
        st.update(hold=hold, file=Path(path).name, source_events=res.get("source_events", []))
        y = st["clean_frame_yield"]
        if y is None:
            self.c.fail(f"Hold {hold}: no frame codes were read ({st.get('frames_no_code')} frames without markers). "
                        "Is the iPad in view, playing the prepared file, and bright enough?")
        else:
            self.c.ok(f"Hold {hold}: clean-frame yield {y:.2f} (blended {st.get('frames_blended')}, torn "
                      f"{st.get('frames_torn')}, no code {st.get('frames_no_code')} of {st.get('frames_in')} frames); "
                      f"{st.get('paint_fps')} fps painted")
            if (st.get("no_code_fraction") or 0) > 0.3:
                self.c.warn("Many frames without readable markers: move the iPhone so all four corners are inside the picture.")
            cov = st.get("source_coverage_est")
            if cov is not None and cov < 0.2:
                self.c.warn("The frame codes hardly advance: is the iPad paused?")
        if st.get("source_failures"):
            self.c.warn(f"The camera dropped out {st['source_failures']} time(s) during the run.")
        return st

    def check_b_yield(self) -> dict[str, Any]:
        self.c.header("3", "Check B: clean-frame yield on the booth loop", MINUTES["check_b_yield"])
        if not self.dry:
            self.c.bullet(["The iPad loops the hold-2 file under the hood; the iPhone films it on the cable, locked.",
                           "Nothing to do during the runs except not bumping the tripod."])
            self.c.wait_enter("ready_b", "Press Enter to start the first run")
        ymin = float(self.s2["yield_min"])
        runs: dict[str, Any] = {"2": self._yield_run(2)}
        names, used = self._screen_names()
        screen_ok = self.c.ask_yes("saw_external", "Did the booth picture fill the EXTERNAL monitor?", True)
        screen = "external"
        if not screen_ok and names:
            self.c.say("Screens: " + ", ".join(f"[{i}] {n}" for i, n in enumerate(names, 1)))
            pick = self.c.ask("screen_pick", "Which number is the monitor visitors will see?", "1")
            if pick.isdigit() and 1 <= int(pick) <= len(names):
                screen = names[int(pick) - 1]
        y2 = runs["2"].get("clean_frame_yield")
        if runs["2"].get("error"):     # no camera at all: recorded as an error, so a rerun repeats this step
            raise RuntimeError(f"hold 2: {runs['2']['error']}; connect the iPhone and rerun with --from check_b_yield")
        if y2 is None or y2 < ymin or self.dry:
            if not self.dry:
                self.c.say(f"The hold-2 yield is below {ymin:.2f}. Now play the hold-3 file instead:")
                self.c.bullet([f"{self._hold_file(3).name} (AirDropped with the hold-2 file, else from {self.booth_dir}), "
                               "same player, repeat one, controls hidden."])
                self.c.wait_enter("ipad_hold3", "Press Enter when the iPad is looping the hold-3 file")
            else:
                self.c.say("Dry run: measuring hold 3 as well.")
            runs["3"] = self._yield_run(3)
        y3 = runs.get("3", {}).get("clean_frame_yield")
        choice = choose_hold(y2, y3, ymin)
        hold = choice["hold_factor"]
        if not self.dry and hold == 3:
            self.c.say("Keep the hold-3 file looping on the iPad from now on.")
        elif not self.dry and "3" in runs:
            self.c.say("Switch the iPad back to the hold-2 file and loop it.")
            self.c.wait_enter("ipad_back_hold2", "Press Enter when the iPad is looping the hold-2 file again")
        (self.c.ok if choice["meets_min"] else self.c.warn)(f"Hold factor {hold}: {choice['reason']}")
        s1 = self._sitting1() or {}
        return {"runs": runs, "yield_min": ymin, "yield_hold2": y2, "yield_hold3": y3, **choice,
                "replay_clip": str(self._hold_file(hold)),
                "screen": screen, "screen_used": used, "screens": names, "user_saw_external_monitor": screen_ok,
                "sitting1_panel_axis": s1.get("panel_axis"),
                "note": ("Clean-frame yield counts every camera frame; source coverage counts source frames "
                         "analysed at least once, which is what tracking needs.")}

    def unplug_test(self) -> dict[str, Any]:
        self.c.header("4", "Unplug and replug the iPhone", MINUTES["unplug_test"])
        hold, path = self._chosen()
        secs = float(self.s2["unplug_seconds"])
        t_un, t_re = float(self.s2["unplug_at_s"]), float(self.s2["replug_at_s"])
        if self.dry:
            t_un, t_re = (float(v) for v in self.s2["dry_unplug_s"])
            self.c.say(f"Dry run: the loop simulator disconnects from {t_un:g} s to {t_re:g} s.")
        else:
            self.c.bullet([f"The booth runs for {secs:g} s. At {t_un:g} s the console says UNPLUG: pull the cable "
                           "out of the Mac (leave the iPhone on the tripod).",
                           f"At {t_re:g} s it says PLUG IN: put the cable back. The picture must come back by itself.",
                           "Watch the monitor: during the gap the screen shows another camera or the REPLAY band."])
            self.c.wait_enter("ready_unplug", "Press Enter to start")
        cfg = self._booth_cfg(hold, path, unplug=True)
        tag = " (simulated)" if self.dry else ""
        t0 = time.monotonic()
        timers = [threading.Timer(t_un, lambda: self.c.say(f"\n>>> UNPLUG the iPhone cable now{tag} <<<\n")),
                  threading.Timer(t_re, lambda: self.c.say(f"\n>>> PLUG the iPhone cable back in now{tag} <<<\n"))]
        for tm in timers:
            tm.daemon = True
            tm.start()
        try:
            res = self._booth(cfg, "auto", secs)
        finally:
            for tm in timers:
                tm.cancel()
        timing = unplug_timing(res.get("source_events", []), self.primary, t0 + t_un, t0 + t_re,
                               float(self.s2["recover_max_s"]))
        if timing["fall_back_s"] is not None:
            self.c.ok(f"Fell back to '{timing['fallback_key']}' {timing['fall_back_s']} s after the unplug prompt")
        else:
            self.c.fail("No fallback was seen. " + timing.get("note", ""))
        if timing["recover_s"] is not None:
            (self.c.ok if timing["pass"] else self.c.warn)(
                f"Camera back {timing['recover_s']} s after the replug prompt (limit {timing['recover_max_s']:g} s)")
        else:
            self.c.fail("The camera did not come back during the run. " + timing.get("note", ""))
        events = [{**e, "t_rel": round(e["t"] - t0, 2)} for e in res.get("source_events", [])]
        return {**timing, "seconds": secs, "unplug_at_s": t_un, "replug_at_s": t_re, "events": events,
                "errors": res.get("errors", []), "paint_fps": run_stats(res, self.primary).get("paint_fps")}

    def webcam_test(self) -> dict[str, Any]:
        self.c.header("5", "USB webcam", MINUTES["webcam_test"])
        from wfglink.io.devices import list_cameras, pick_camera

        devs = list_cameras().get("devices", [])
        web = pick_camera(devs, "webcam", None, self.cfg["camera"].get("webcam_match"))
        if not web:
            self.c.say("No USB webcam listed; skipped.")
            return {"status_note": "no webcam listed"}
        hold, path = self._chosen()
        secs = float(self.s2["dry_seconds"] if self.dry else self.s2["webcam_seconds"])
        if not self.dry:
            self.c.bullet([f"Webcam found: {web.get('name')}. Aim it at the iPad next to the iPhone, under the hood.",
                           f"The booth runs {secs:g} s from the webcam only."])
            self.c.wait_enter("ready_webcam", "Press Enter when the webcam sees the whole iPad")
        cfg = self._booth_cfg(hold, path, chain={"chain": ["webcam"]})
        res = self._booth(cfg, "camera", secs)
        st = run_stats(res, "webcam", hold)
        works = bool(st.get("frames") and st.get("clean_frame_yield") is not None)
        (self.c.ok if works else self.c.warn)(
            f"Webcam: {st.get('paint_fps')} fps painted, clean-frame yield {st.get('clean_frame_yield')}")
        return {"name": web.get("name"), "works": works, **st}

    def worker_mode(self) -> dict[str, Any]:
        self.c.header("6", "Worker mode: thread or process", MINUTES["worker_mode"])
        hold, path = self._chosen()
        secs = self.seconds if self.dry else float(self.s2["worker_seconds"])
        self.c.say(f"Two runs of {secs:g} s each. Nothing to do; the picture should move in both.")
        out: dict[str, Any] = {}
        for mode in ("thread", "process"):
            try:
                cfg = self._booth_cfg(hold, path, mode)
                res = self._booth(cfg, "auto" if self.dry else "camera", secs)
                st = run_stats(res, self.primary, hold)
                out[mode] = {k: st.get(k) for k in ("seconds", "frames", "paints", "paint_fps", "processing_fps", "errors")}
            except Exception as exc:
                out[mode] = {"error": f"{type(exc).__name__}: {exc}", "paint_fps": None}
            if out[mode].get("error") or out[mode].get("errors"):
                self.c.warn(f"{mode}: {out[mode].get('error') or out[mode]['errors'][-1]}")
            else:
                self.c.ok(f"{mode}: {out[mode].get('paint_fps')} fps painted, {out[mode].get('frames')} frames analysed")

        def score(m: str) -> float:
            r = out[m]
            return -1.0 if r.get("error") or r.get("errors") or not r.get("paint_fps") else float(r["paint_fps"])
        chosen = "process" if score("process") > score("thread") else "thread"
        self.c.ok(f"Worker mode: {chosen}")
        return {"runs": out, "worker_mode": chosen, "paint_fps": {m: out[m].get("paint_fps") for m in out}}

    def write_local_config(self) -> dict[str, Any]:
        self.c.header("7", "Save the booth settings", MINUTES["write_local_config"])
        hold, path = self._chosen()
        b = self.report.get("check_b_yield")
        mode = self.report.get("worker_mode").get("worker_mode") or self.cfg["live"]["worker_mode"]
        updates = {"booth": {"hold_factor": hold, "replay_clip": rel(path)}, "live": {"worker_mode": mode},
                   "ui": {"screen": b.get("screen") or self.cfg["ui"]["screen"]}}
        # Keep what sitting 1 wrote (a dry run starts from it and writes its own copy).
        base = self.local_path if self.local_path.exists() else LOCAL_CONFIG
        existing = (yaml.safe_load(base.read_text()) or {}) if base.exists() else {}
        merged = merge_local_config(existing, updates)
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self.local_path.write_text("# Written by the sittings; machine-specific overrides of configs/default.yaml.\n"
                                   + yaml.safe_dump(merged, sort_keys=True, allow_unicode=True))
        self.c.ok(f"Saved to {rel(self.local_path)}: hold factor {hold}, worker mode {mode}, "
                  f"screen {updates['ui']['screen']}")
        return {"path": str(self.local_path), "updates": updates, "merged": merged}

    def soak_start(self) -> dict[str, Any]:
        self.c.header("8", "Start the overnight soak (check C)", MINUTES["soak_start"])
        prev = self.report.get("soak_start")
        if prev.get("status") == "done" and _alive(prev.get("supervisor_pid")) and "booth.sh" in _command(prev["supervisor_pid"]):
            self.c.warn(f"A soak is already running (supervisor pid {prev['supervisor_pid']}); run with --finish first.")
            return {k: v for k, v in prev.items() if k not in ("status", "at")}
        hold, path = self._chosen()
        every = float(self.s2["dry_soak_every_s"] if self.dry else self.s2["soak_every_s"])
        if not self.dry:
            self.c.bullet(["Leave everything as it is for the night: iPad looping the clip on its charger, iPhone on "
                           "the cable, MacBook on its charger with the lid open.",
                           "The booth app starts fullscreen on the monitor and restarts itself if it fails.",
                           "You may close this Terminal window afterwards; the soak keeps running."])
            self.c.wait_enter("ready_soak", "Press Enter to start the soak")
        args = ["nohup", "bash", str(BOOTH_SH), "--replay-clip", str(Path(path).resolve())]
        env = dict(os.environ)
        if self.dry:
            chain = self.out / "dry_soak_chain.yaml"
            chain.write_text(yaml.safe_dump({"camera": {"chain": [f"loopsim:{Path(path).resolve()}", "replay"]}}))
            args += ["--screen", "primary", "--config", str(self.local_path), str(chain)]
            if sys.platform != "darwin":
                env.setdefault("QT_QPA_PLATFORM", "offscreen")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_size = BOOTH_LOG.stat().st_size if BOOTH_LOG.exists() else 0
        start_epoch = time.time()
        # Both run in their own session (setsid, plus nohup for the supervisor), so closing the
        # Terminal window does not stop them.
        with open(self.out / "soak_supervisor.out", "ab") as fh:
            sup = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   start_new_session=True, cwd=str(PROJECT_ROOT), env=env)
        (self.out / "soak_supervisor.pid").write_text(str(sup.pid))
        csv_path = self.out / "soak.csv"
        with open(self.out / "soak_sampler.log", "ab") as fh:
            sampler = subprocess.Popen(
                [sys.executable, "-m", "wfglink.sitting.soak", "sample", "--heartbeat", str(HEARTBEAT),
                 "--out", str(csv_path), "--every", f"{every:g}", "--pid-file", str(self.out / "soak_sampler.pid"),
                 "--stale-s", f"{float(self.s2['hb_stale_s']):g}"],
                stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
                cwd=str(PROJECT_ROOT))
        self._procs = (sup, sampler)
        hb_ok = self._wait_heartbeat(start_epoch, 40.0)
        (self.c.ok if hb_ok else self.c.warn)(
            "The booth app is running and writing its heartbeat" if hb_ok else
            "No heartbeat yet; check the monitor and wfglink/logs/booth.log")
        payload = {"start_epoch": round(start_epoch, 3), "start_time": now_shanghai(), "supervisor_pid": sup.pid,
                   "sampler_pid": sampler.pid, "csv": csv_path.name, "every_s": every, "booth_log_offset": log_size,
                   "args": args[1:], "heartbeat_seen": hb_ok, "hold_factor": hold, "replay_clip": rel(path)}
        if self.dry:
            self.c.say(f"Dry run: soaking for {self.soak_seconds:g} s, then finishing automatically.")
            time.sleep(self.soak_seconds)
        else:
            self.c.say("\nThe soak is running. Good night.")
            self.c.bullet(["In the morning, in Terminal: bash ~/wfglink-run/wfglink/scripts/sitting2.sh --finish",
                           "It stops the soak, asks one question and prints a line to paste to Claude.",
                           "Then do the rehearsal: docs/SITTING2.md, section 'The morning', with booth/BOOTH_RUNBOOK.md."])
        return payload

    def _wait_heartbeat(self, after_epoch: float, timeout_s: float, any_status: bool = False) -> bool:
        from wfglink.sitting.soak import read_heartbeat

        t_end = time.monotonic() + timeout_s
        while time.monotonic() < t_end:
            hb = read_heartbeat(HEARTBEAT)
            if hb and float(hb.get("epoch") or 0) >= after_epoch and (any_status or hb.get("status") == "running"):
                return True
            time.sleep(0.5)
        return False

    def finish(self) -> dict[str, Any]:
        from wfglink.sitting.soak import analyse_soak, read_heartbeat, sample_once

        self.c.header("9", "Morning: stop the soak and write the report", MINUTES["finish"])
        ss = self.report.get("soak_start")
        if ss.get("status") != "done":
            raise RuntimeError("no soak was started (run the soak_start step first)")
        csv_path = self.out / ss.get("csv", "soak.csv")
        out: dict[str, Any] = {}
        finish_epoch = time.time()
        out["finish_epoch"] = round(finish_epoch, 3)
        # The app rewrites its heartbeat every 2 s but has no SIGTERM handler, so the last word
        # it can give is the next heartbeat: wait for one written after this moment, sample it,
        # then stop the sampler and the supervisor.
        out["fresh_heartbeat"] = self._wait_heartbeat(finish_epoch, 10.0, any_status=True)
        out["final_sample"] = sample_once(HEARTBEAT, csv_path, float(self.s2["hb_stale_s"]))
        out["sampler_stopped"] = self._stop_sampler(ss)
        out["supervisor_stopped"], out["app_stopped"] = self._stop_booth(ss)
        hb = read_heartbeat(HEARTBEAT) or {}
        out["final_heartbeat"] = hb
        s2 = self.s2
        analysis = analyse_soak(csv_path, BOOTH_LOG, float(ss["start_epoch"]), finish_epoch,
                                last_h=float(s2["mem_fit_last_h"]),
                                warmup_s=0.0 if self.dry else float(s2["mem_warmup_s"]),
                                mem_max_mb_h=float(s2["mem_slope_max_mb_h"]),
                                min_hours=float(s2["mem_min_hours"]))
        if self.dry:
            analysis["note"] = "dry run: a soak of seconds, so the memory slope is warm-up, not a leak"
        out["analysis"] = analysis
        if analysis.get("ok"):
            mem = analysis["memory"]
            self.c.ok(f"Soak {analysis['hours']} h: paint fps median {analysis['paint_fps_median']}, "
                      f"5th percentile {analysis['paint_fps_p5']}; restarts {analysis['restarts']}; "
                      f"source switches {analysis['source_switches']}; errors {analysis['errors']}")
            (self.c.ok if mem["verdict"] != "fail" else self.c.fail)(
                f"Memory slope {mem['slope_mb_h']} MB/h over {mem['span_h']} h ({mem['verdict']}, limit {mem['max_mb_h']:g})")
        else:
            self.c.fail(f"Soak analysis: {analysis.get('error')}")
        out["iphone_hot"] = self.c.ask_yes("iphone_hot", "Was the iPhone uncomfortably hot to touch this morning?", False)
        return out

    def _stop_sampler(self, ss: dict[str, Any]) -> bool:
        pid_file = self.out / "soak_sampler.pid"
        pid = int(pid_file.read_text().strip()) if pid_file.exists() else ss.get("sampler_pid")
        if not pid or not _alive(pid):
            return True
        if "wfglink.sitting.soak" not in _command(pid):
            return False
        os.kill(pid, signal.SIGTERM)
        return _wait_gone(pid, 10.0)

    def _stop_booth(self, ss: dict[str, Any]) -> tuple[bool, bool]:
        """SIGTERM to the supervisor's process group (booth.sh, the app, caffeinate), SIGKILL only if
        that is ignored; then the app itself if it lives outside the group (booth.launcher app)."""
        from wfglink.sitting.soak import read_heartbeat

        hb = read_heartbeat(HEARTBEAT) or {}
        sup = int(ss.get("supervisor_pid") or 0)
        sup_ok = True
        if sup and _alive(sup):
            if "booth.sh" not in _command(sup):
                sup_ok = False
            else:
                try:
                    os.killpg(sup, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                sup_ok = _wait_gone(sup, 20.0)
                if not sup_ok:
                    try:
                        os.killpg(sup, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    sup_ok = _wait_gone(sup, 5.0)
        app = int(hb.get("pid") or 0)
        app_ok = True
        if app and _alive(app):
            cmd = _command(app)
            if "wfglink" in cmd or "WFGLink" in cmd:
                os.kill(app, signal.SIGTERM)
                app_ok = _wait_gone(app, 15.0)
        return sup_ok, app_ok

    # Driver ----------------------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        s = self.report.data["steps"]
        b, u, w = s.get("check_b_yield", {}), s.get("unplug_test", {}), s.get("worker_mode", {})
        fin = s.get("finish", {})
        an = fin.get("analysis") or {}
        r2 = (b.get("runs") or {}).get("2", {})
        r3 = (b.get("runs") or {}).get("3", {})
        web = s.get("webcam_test", {})
        out = {"dry_run": self.dry, "hold_factor": b.get("hold_factor"), "yield_hold2": b.get("yield_hold2"),
               "yield_hold3": b.get("yield_hold3"), "blended_torn_hold2": [r2.get("frames_blended"), r2.get("frames_torn")],
               "blended_torn_hold3": [r3.get("frames_blended"), r3.get("frames_torn")] if r3 else None,
               "coverage_hold2": r2.get("source_coverage_est"), "panel_axis": b.get("sitting1_panel_axis"),
               "screen": b.get("screen"), "unplug": {k: u.get(k) for k in ("fall_back_s", "recover_s", "pass")} if u else None,
               "webcam": web.get("works") if "works" in web else web.get("status_note"),
               "worker_mode": w.get("worker_mode"), "paint_fps": w.get("paint_fps"),
               "minutes": round((time.monotonic() - self._t0) / 60, 1)}
        if an:
            mem = an.get("memory") or {}
            out["soak"] = {"hours": an.get("hours"), "paint_fps_median": an.get("paint_fps_median"),
                           "paint_fps_p5": an.get("paint_fps_p5"), "mem_slope_mb_h": mem.get("slope_mb_h"),
                           "mem": mem.get("verdict"), "restarts": an.get("restarts"),
                           "switches": an.get("source_switches"), "errors": an.get("errors")}
            out["iphone_hot"] = fin.get("iphone_hot")
        errors = {k: v.get("error") for k, v in s.items() if v.get("status") == "error"}
        if errors:
            out["step_errors"] = errors
        return out

    def run(self, start: str | None = None, steps: list[str] | None = None) -> dict[str, Any]:
        """Run steps in order. Without arguments, completed steps are skipped (resume)."""
        explicit = steps is not None or start is not None
        order = ALL_STEPS if self.dry else STEP_ORDER
        if steps is None:
            steps = order[order.index(start):] if start else order
        for name in steps:
            if not explicit and self.report.done(name):
                continue
            t0 = time.monotonic()
            try:
                payload = getattr(self, name)()
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
        if self.report.done("finish"):
            self.c.say("\nPaste this summary to Claude:\n" + text)
        else:
            self.c.say("\nEvening summary (the full report is " + str(self.report.path) + "):\n" + text)
        return self.report.data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wfglink sitting2", description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None,
                    help="folder for the report and the soak files (default ~/wfglink-sitting2, dry run ~/wfglink-sitting2-dry)")
    ap.add_argument("--from", dest="start", choices=ALL_STEPS, help="resume from this step")
    ap.add_argument("--only", choices=ALL_STEPS, help="run a single step")
    ap.add_argument("--finish", action="store_true", help="in the morning: stop the soak and write the final report")
    ap.add_argument("--dry-run", action="store_true", help="the whole flow on a simulated booth loop (no hardware)")
    ap.add_argument("--yes", action="store_true", help="accept every default (dry runs and tests)")
    ap.add_argument("--seconds", type=float, default=None, help="seconds per check B run (default from config)")
    ap.add_argument("--soak-seconds", type=float, default=None, help="dry run: soak length before the automatic finish")
    args = ap.parse_args(argv)
    if args.dry_run and sys.platform != "darwin":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    out = Path(os.path.expanduser(args.out or ("~/wfglink-sitting2-dry" if args.dry_run else "~/wfglink-sitting2"))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    s = Sitting2(out, Console(assume_yes=args.yes or args.dry_run), dry_run=args.dry_run, seconds=args.seconds,
                 soak_seconds=args.soak_seconds)
    if args.finish:
        s.run(steps=["finish"])
    elif args.only:
        s.run(steps=[args.only])
    else:
        s.run(start=args.start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
