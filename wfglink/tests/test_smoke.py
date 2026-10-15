"""Scaffold smoke tests: environment, provenance registry and documentation guards."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wfglink import PROJECT_ROOT
from wfglink import provenance


def test_core_imports():
    import av
    import cv2
    import numpy
    import pyarrow  # noqa: F401
    import scipy  # noqa: F401

    assert numpy.__version__.startswith("2.")
    assert cv2.__version__.startswith("4.14")
    assert hasattr(cv2.aruco, "ArucoDetector")
    assert "libx264" in av.codecs_available


@pytest.mark.qt
def test_pretendard_is_loaded_and_resolved():
    from PySide6.QtGui import QFontInfo, QGuiApplication

    from wfglink.ui.fonts import load_fonts, ui_font

    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    assert "Pretendard" in load_fonts()
    assert QFontInfo(ui_font(40, "semibold")).family() == "Pretendard"


def test_record_number_writes_provenance(tmp_path: Path):
    path = tmp_path / "NUMBERS.json"
    entry = provenance.record_number(
        "test.value", 0.5, "fraction", "unit test value",
        script="tests/test_smoke.py", config={"a": 1}, config_path="inline", path=path,
    )
    data = json.loads(path.read_text())
    assert data["numbers"]["test.value"]["value"] == 0.5
    for field in ("git_commit", "git_dirty", "config_sha256", "produced_at", "host", "script"):
        assert field in entry
    assert entry["produced_at"].endswith("+08:00")


def test_check_docs_passes():
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "check_docs.py")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_doctor_reports_ok():
    # data/raw and the playlist clips are not in every checkout, so only the four setup checks must pass here.
    result = subprocess.run([sys.executable, "-m", "wfglink", "doctor", "--json"], capture_output=True, text=True)
    checks = {c["name"]: c for c in json.loads(result.stdout)["checks"]}
    for name in ("python", "packages", "fonts", "screens", "video"):
        assert checks[name]["ok"] is True, checks[name]
