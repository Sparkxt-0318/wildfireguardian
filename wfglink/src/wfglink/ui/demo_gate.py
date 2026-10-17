"""The demo gate: is this commit demo-ready?

    python -m wfglink demo-gate [--seconds 60] [--playlist booth/playlist.yaml] [--out DIR] [--config FILE ...]

Runs the live screen headless (Qt offscreen) for `seconds` four times, with the booth's own
ember pipeline (live.ember_pipeline, EmberPipeline):
1. fire mode on synthetic video;
2. fire mode on the booth playlist;
3. ember mode ("Become an ember") on the generated phone scene played like a camera
   (ui/phone_scene.py, wfglink.ember.synth's "booth" scene with its phones; no camera is opened);
4. the keys: the playlist in fire mode, then A, A (raw and back), M (ember mode), Space, Space
   (pause and resume), M (back to the fire footage), at fixed shares of the run.
It passes when every run went without errors, analysed and painted frames and produced finite
numbers; when the playlist run really played clips (no synthetic fallback because the clips
are missing); when the ember run tracked phones with finite speeds and its count of embers was
above the scene's phones in at most demo_gate.ember_over_max of its frames (a lamp or another
static light shown as an ember would break that); and when the keys run did what each key
says, showed both modes, ended in fire mode with the camera off, and left no thread behind.
Screenshots and a JSON report go to `out`. Used before every daily `wfglink-demo-YYYYMMDD` tag
(scripts/tag_demo.sh).
"""
from __future__ import annotations

import json
import math
import os

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import git_state, now_shanghai


KEY_SCRIPT = ((0.15, "A"), (0.25, "A"), (0.35, "M"), (0.60, "Space"), (0.65, "Space"), (0.80, "M"))


def scene_phones(cfg: dict) -> int:
    """How many phones the generated scene of ember mode holds (wfglink.ember.synth "booth")."""
    from wfglink.ember.synth import LIVE_SCENES

    return len(LIVE_SCENES["booth"]["phones"])


def ember_over_share(res: dict, phones: int) -> float:
    """The share of ember-mode frames whose count of embers was above the scene's phones."""
    counts = {int(k): v for k, v in ((res.get("ember") or {}).get("counts") or {}).items()}
    total = sum(counts.values())
    return sum(v for k, v in counts.items() if k > phones) / total if total else 0.0


def _healthy(res: dict, seconds: float, needs_clips: bool, ember: bool = False, phones: int = 3,
             over_max: float = 0.01) -> tuple[bool, list[str]]:
    why = []
    if res["errors"]:
        why.append("errors: " + "; ".join(res["errors"][:3]))
    if res["frames"] < max(10, seconds * 3):
        why.append(f"too few analysed frames ({res['frames']})")
    if res["paints"] < max(10, seconds * 3):
        why.append(f"too few painted frames ({res['paints']})")
    last = res.get("last", {})
    for k in ("count_rate", "speed"):
        v = last.get(k)
        if v is not None and not math.isfinite(v):
            why.append(f"{k} is not finite")
    if needs_clips:
        states = res.get("states", {})
        if not states.get("playing"):
            why.append("no clip played (are the clips in data/raw?)")
        elif states.get("synthetic"):
            why.append("the playlist fell back to synthetic video")
    if ember:
        e = res.get("ember") or {}
        if res.get("camera_state") not in ("ok", "starting"):
            why.append(f"ember mode camera state is {res.get('camera_state')!r} (see the log for the reason)")
        if not e.get("states"):
            why.append("ember mode showed no analysed frame")
        elif not e.get("max_count"):
            why.append("ember mode tracked no phone")
        elif not e.get("speeds"):
            why.append("ember mode gave no ember speed")
        over = ember_over_share(res, phones)
        res["ember_over_share"] = round(over, 4)
        if over > over_max:
            why.append(f"ember mode counted more embers than the scene's {phones} phones in {over:.1%} of its frames "
                       f"(at most {over_max:.0%}; most at once {e.get('max_count')})")
    return not why, why


def _keys_healthy(res: dict) -> list[str]:
    why = []
    pressed = res.get("keys_pressed") or []
    if [k["key"] for k in pressed] != [k for _, k in KEY_SCRIPT]:
        why.append(f"keys pressed {[k['key'] for k in pressed]}, expected {[k for _, k in KEY_SCRIPT]}")
        return why
    a1, a2, m1, s1, s2, m2 = pressed
    if not (a1["raw"] and not a2["raw"] and a1["mode"] == "fire"):
        why.append("A did not switch the fire footage to raw and back")
    if m1["mode"] != "ember" or m2["mode"] != "fire":
        why.append("M did not switch to ember mode and back")
    if not (s1["paused"] and not s2["paused"]):
        why.append("Space did not pause and resume")
    modes = res.get("modes") or {}
    if not modes.get("fire") or not modes.get("ember"):
        why.append(f"both modes must show analysed frames (seen: {modes})")
    if (res.get("raw_toggles"), res.get("mode_switches"), res.get("pauses")) != (2, 2, 2):
        why.append(f"raw toggles {res.get('raw_toggles')}, mode switches {res.get('mode_switches')}, "
                   f"pauses {res.get('pauses')}: expected 2 each")
    if res.get("mode") != "fire" or res.get("camera_state") != "off" or res.get("raw"):
        why.append(f"the run should end in fire mode, analysed, camera off (mode {res.get('mode')}, "
                   f"raw {res.get('raw')}, camera {res.get('camera_state')})")
    if res.get("threads_end", 0) > res.get("threads_start", 0) + 1:
        why.append(f"threads left behind: {res.get('threads_start')} at the start, {res.get('threads_end')} at the end")
    return why


def demo_gate(seconds: float = 60.0, playlist: str | None = None, out: str = "results/runs/demo_gate",
              config: list[str] | None = None) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from wfglink.ui.booth_app import ember_spec, run_live, source_spec

    out_dir = PROJECT_ROOT / out
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(*(config or []))
    # The scene has as many phones as the booth's cap, so the cap would hide an extra ember (a lamp
    # taken for one); the gate lifts it to judge the count. tests/test_ember.py checks the cap itself.
    cfg.setdefault("ember", {})["max_tracks"] = max(int(cfg["ember"].get("max_tracks", 6)), 6)
    report = {"at": now_shanghai(), "git": git_state(), "seconds": seconds, "runs": {}}
    ok_all = True
    phones = scene_phones(cfg)
    over_max = float((cfg.get("demo_gate") or {}).get("ember_over_max", 0.01))
    report["ember_scene_phones"] = phones
    runs = (("synthetic", source_spec(synthetic=True), "fire", None),
            ("playlist", source_spec(playlist=playlist, cfg=cfg), "fire", None),
            ("ember", source_spec(synthetic=True), "ember", None),
            ("keys", source_spec(playlist=playlist, cfg=cfg), "fire", [(f * seconds, k) for f, k in KEY_SCRIPT]))
    for name, spec, mode, keys in runs:
        res = run_live(cfg, source=spec, screen="primary", lang="ko", duration_s=seconds,
                       screenshot=str(out_dir / f"{name}.png"), ember=ember_spec(synthetic=True), start_mode=mode,
                       keys=keys)
        ok, why = _healthy(res, seconds, needs_clips=(name == "playlist"), ember=(mode == "ember"), phones=phones,
                           over_max=over_max)
        if keys:
            why += _keys_healthy(res)
            over = ember_over_share(res, phones)       # the ember part of the keys run, entered with M
            res["ember_over_share"] = round(over, 4)
            if over > over_max:
                why.append(f"keys run: more embers than the scene's {phones} phones in {over:.1%} of its ember frames "
                           f"(at most {over_max:.0%})")
            ok = not why
        res["ok"], res["why"] = ok, why
        report["runs"][name] = res
        ok_all = ok_all and ok
        print(f"demo gate {name}: {'PASS' if ok else 'FAIL'} frames={res['frames']} paints={res['paints']} {why}")
    report["pass"] = ok_all
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print("demo gate:", "PASS" if ok_all else "FAIL", f"({out_dir / 'report.json'})")
    return 0 if ok_all else 1
