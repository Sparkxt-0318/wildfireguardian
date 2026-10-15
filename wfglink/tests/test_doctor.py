"""python -m wfglink doctor: the line format, requirement pins, screen roles and playlist clips."""
import json
import subprocess
import sys

import pytest

from wfglink import PROJECT_ROOT
from wfglink.doctor import (Check, check_camera, check_clips, classify_screens, format_line, import_name,
                            pinned_requirements, playlist_clips)

PATTERN = r"built-?in|내장|color lcd|^edp|^lvds|^dsi"


def _scr(name, x=0, y=0, w=1512, h=982):
    return {"name": name, "x": x, "y": y, "w": w, "h": h}


def test_doctor_prints_one_line_per_check_in_order():
    res = subprocess.run([sys.executable, "-m", "wfglink", "doctor"], capture_output=True, text=True, timeout=300)
    lines = res.stdout.splitlines()
    checks = [ln for ln in lines if not ln.startswith(" ")]
    assert [ln.split()[0] for ln in checks] == ["python", "packages", "fonts", "screens", "video", "camera", "data",
                                                    "clips"]
    assert all(ln.endswith(" OK") or ln.endswith(" FAIL") for ln in checks)
    # Every FAIL is followed by its fix; the exit code says whether all were OK.
    for i, ln in enumerate(lines):
        if ln.endswith(" FAIL"):
            assert lines[i + 1].strip().startswith("fix: ")
    assert (res.returncode == 0) == all(ln.endswith(" OK") for ln in checks)
    data = json.loads(subprocess.run([sys.executable, "-m", "wfglink", "doctor", "--json"], capture_output=True,
                                     text=True, timeout=300).stdout)
    assert [c["name"] for c in data["checks"]] == [ln.split()[0] for ln in checks]
    assert data["ok"] == (res.returncode == 0)


def test_format_line_counts_wide_characters():
    ok = format_line(Check("screens", True, "1: 내장 Retina 디스플레이 1512x982@2x (built-in)"), width=70)
    assert ok.endswith(" OK") and "\n" not in ok
    # Hangul takes two columns: the status lands in the same column as for plain text.
    plain = format_line(Check("screens", True, "x" * 20), width=70)
    wide = format_line(Check("screens", True, "가" * 10), width=70)
    assert len(plain) == 70 and len(wide) == 60
    bad = format_line(Check("data", False, "data/raw is missing", "run ./scripts/setup_mac.sh"))
    first, second = bad.splitlines()
    assert first.endswith(" FAIL") and second.strip() == "fix: run ./scripts/setup_mac.sh"


def test_pinned_requirements_follow_platform_markers(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("# comment\nnumpy==2.5.4\nPySide6==6.12.0  # Qt\nloose>=1\n"
                   'pyobjc-core==12.2.2; sys_platform == "darwin"\nonlylinux==1.0; sys_platform != "darwin"\n')
    pins = dict(pinned_requirements(req))
    assert pins["numpy"] == "2.5.4" and pins["PySide6"] == "6.12.0" and "loose" not in pins
    assert ("pyobjc-core" in pins) == (sys.platform == "darwin")
    assert ("onlylinux" in pins) == (sys.platform != "darwin")
    assert [import_name(d) for d in ("opencv-contrib-python-headless", "PyYAML", "pyobjc-core",
                                     "pyobjc-framework-AVFoundation", "PySide6")] == ["cv2", "yaml", "objc",
                                                                                      "AVFoundation", "PySide6"]
    # The project's own file parses, with every pin for this platform.
    assert len(pinned_requirements(PROJECT_ROOT / "requirements.txt")) >= 9


def test_screen_roles_and_the_booth_screen():
    mac, dell = _scr("Built-in Retina Display"), _scr("DELL U2723QE", x=1512, w=2560, h=1440)
    c = classify_screens([mac, dell], 0, PATTERN)
    assert c["labels"] == ["built-in", "external"] and c["booth"] == 1 and not c["mismatch"]
    # The external monitor as the main screen (menu bar moved) changes nothing.
    assert classify_screens([dell, mac], 0, PATTERN)["booth"] == 0
    # Only the MacBook: the booth uses it.
    only = classify_screens([_scr("내장 Retina 디스플레이")], 0, PATTERN)
    assert only["labels"] == ["built-in"] and only["booth"] == 0 and only["external"] == []
    # Names that say nothing: the screen that is not the main one is the booth's.
    c = classify_screens([_scr("Screen A"), _scr("Screen B", x=1512)], 0, PATTERN)
    assert c["labels"] == ["main", "external"] and c["booth"] == 1
    # CoreGraphics knows which is built in: names that disagree fail, since the booth goes by name.
    ok = classify_screens([mac, dell], 0, PATTERN, cg_builtin=[(0, 0, 1512, 982)])
    assert ok["labels"] == ["built-in", "external"] and not ok["mismatch"]
    odd = classify_screens([_scr("Retina Display"), dell], 0, PATTERN, cg_builtin=[(0, 0, 1512, 982)])
    assert odd["mismatch"] == ["Retina Display"] and odd["external"] == [1]
    assert classify_screens([], 0, PATTERN)["booth"] is None


def test_screen_rule_matches_the_booth():
    booth_app = pytest.importorskip("wfglink.ui.booth_app")
    if not hasattr(booth_app, "choose_screen") or not hasattr(booth_app, "BUILTIN_SCREEN"):
        pytest.skip("the booth's screen rule is not in this tree")

    class S:
        def __init__(self, name):
            self._n = name

        def name(self):
            return self._n

    cases = [["Built-in Retina Display", "DELL"], ["DELL", "Built-in Retina Display"], ["내장 Retina 디스플레이"],
             ["A", "B"], ["A"], ["LG", "DELL", "Color LCD"]]
    for names in cases:
        objs = [S(n) for n in names]
        want = objs.index(booth_app.choose_screen(objs, objs[0], "auto", booth_app.BUILTIN_SCREEN))
        got = classify_screens([_scr(n, x=i * 2000) for i, n in enumerate(names)], 0, booth_app.BUILTIN_SCREEN)
        assert got["booth"] == want, names


def test_playlist_clips_and_the_clips_check(tmp_path):
    video = tmp_path / "own_clip.mp4"
    video.write_bytes(b"\0")
    playlist = tmp_path / "playlist.yaml"
    playlist.write_text(f"clips:\n  - clip: C6_nist_dragon\n  - clip: {video}\n  - {tmp_path / 'gone.mov'}\n")
    pc = playlist_clips({"booth": {"playlist": str(playlist)}})
    assert pc["error"] is None
    by_id = {c["id"]: c for c in pc["clips"]}
    assert by_id["C6_nist_dragon"]["file"] == "data/raw/C6_nist_dragon.mp4" and by_id["C6_nist_dragon"]["downloadable"]
    assert by_id["own_clip"]["present"] and not by_id["own_clip"]["downloadable"]
    assert not by_id["gone"]["present"] and not by_id["gone"]["downloadable"]
    chk = check_clips({"booth": {"playlist": str(playlist)}})
    n_present = sum(c["present"] for c in pc["clips"])
    assert not chk.ok and chk.detail.startswith(f"{n_present} of 3 playlist clips")
    assert "gone" in chk.detail and "copy" in chk.fix
    assert ("fetch_clips.py --only C6_nist_dragon" in chk.fix) == (not by_id["C6_nist_dragon"]["present"])
    playlist.write_text(f"clips:\n  - clip: {video}\n")
    assert check_clips({"booth": {"playlist": str(playlist)}}).ok
    missing = check_clips({"booth": {"playlist": str(tmp_path / "none.yaml")}})
    assert not missing.ok and "cannot read" in missing.detail


def test_camera_check_names_the_camera_and_the_permission():
    webcam = {"name": "USB Camera", "unique_id": "0x1400000", "transport": "usb ", "device_type": "External"}
    iphone = {"name": "My iPhone Camera", "unique_id": "AA", "is_continuity": True}
    cfg = {"camera": {"name": "auto"}}
    ok = check_camera(cfg, [webcam, iphone], "authorized", mac=True)
    assert ok.ok and "USB Camera" in ok.detail and "granted" in ok.detail
    denied = check_camera(cfg, [webcam], "denied", mac=True)
    assert not denied.ok and "Privacy and Security" in denied.fix and "Terminal" in denied.fix
    ask = check_camera(cfg, [webcam], "not_determined", mac=True)
    assert not ask.ok and "cameras --request" in ask.fix
    only_phone = check_camera(cfg, [iphone], "authorized", mac=True)
    assert not only_phone.ok and "camera.name" in only_phone.fix
    assert check_camera(cfg, [], "unsupported", mac=False).ok          # Linux without a camera: ember mode is generated
