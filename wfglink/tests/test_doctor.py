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
    checks = lines
    # One line per check: the manual's four first, then video, camera, data and clips.
    assert [ln.split()[0] for ln in checks] == ["python", "packages", "fonts", "screens", "video", "camera", "data",
                                                    "clips"]
    assert all(ln.endswith(" OK") or ln.endswith(" FAIL") for ln in checks)
    # Every FAIL carries its fix hint on the same line; the exit code says whether all were OK.
    for ln in lines:
        if ln.endswith(" FAIL"):
            assert "; fix: " in ln
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
    assert "\n" not in bad and bad.endswith(" FAIL")
    assert bad.startswith("data      data/raw is missing; fix: run ./scripts/setup_mac.sh ")
    # A long line keeps everything; the status still ends it.
    long = format_line(Check("clips", False, "0 of 2 playlist clips missing: " + "C" * 80, "run it again"))
    assert long.endswith("; fix: run it again FAIL") and "C" * 80 in long


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
    ok = check_camera(cfg, [webcam, iphone], "authorized", mac=True, effects={})
    assert ok.ok and "USB Camera" in ok.detail and "granted" in ok.detail and "effects" not in ok.detail
    fx = check_camera(cfg, [webcam], "authorized", mac=True, effects={"reactions": True, "center_stage": True})
    assert fx.ok and "video effects on: reactions" in fx.detail and "center stage" not in fx.detail
    denied = check_camera(cfg, [webcam], "denied", mac=True)
    assert not denied.ok and "Privacy and Security" in denied.fix and "Terminal" in denied.fix
    ask = check_camera(cfg, [webcam], "not_determined", mac=True)
    assert not ask.ok and "cameras --request" in ask.fix
    only_phone = check_camera(cfg, [iphone], "authorized", mac=True)
    assert not only_phone.ok and "camera.name" in only_phone.fix
    off = check_camera(cfg, [], "unsupported", mac=False)               # Linux without a camera: OK ...
    assert off.ok and "No camera found" in off.detail and "--synthetic" in off.detail   # ... and says what ember mode shows


def test_clip_downloads_trust_certifi_when_python_has_no_certificates(tmp_path, monkeypatch):
    """python.org's macOS Python has no certificates until 'Install Certificates' has run: the
    downloads add certifi's bundle (pinned for macOS in requirements.txt) to Python's own."""
    import importlib.util
    import types
    from pathlib import Path

    bundle = Path("/etc/ssl/certs/ca-certificates.crt")
    if not bundle.exists():
        pytest.skip("no system CA bundle here to stand in for certifi's")
    empty = tmp_path / "empty.pem"
    empty.write_text("")
    monkeypatch.setenv("SSL_CERT_FILE", str(empty))                     # Python's own: nothing
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path))
    spec = importlib.util.spec_from_file_location("fetch_clips_t", PROJECT_ROOT / "scripts" / "fetch_clips.py")
    fc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fc)
    monkeypatch.setitem(sys.modules, "certifi", None)                    # certifi not installed
    assert fc.ssl_context().cert_store_stats()["x509_ca"] == 0
    monkeypatch.setitem(sys.modules, "certifi", types.SimpleNamespace(where=lambda: str(bundle)))
    assert fc.ssl_context().cert_store_stats()["x509_ca"] > 50
    lines = (PROJECT_ROOT / "requirements.txt").read_text().splitlines()
    assert any(ln.startswith("certifi==") and 'sys_platform == "darwin"' in ln for ln in lines)
    # A certificate failure says what to do instead of retrying for a minute.
    err = fc.urllib.error.URLError(fc.ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))
    assert fc._cert_error(err) and "setup_mac.sh" in fc.CERT_FIX
