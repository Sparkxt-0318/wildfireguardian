"""The manuscript builds, its figures regenerate, and its gate passes."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper"


def test_figures_regenerate_into_a_temp_dir(tmp_path: Path):
    pytest.importorskip("matplotlib")
    r = subprocess.run([sys.executable, str(PAPER / "make_figures.py"), "--out", str(tmp_path)], cwd=REPO, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    assert (tmp_path / "F1_system.png").exists() and (tmp_path / "F2_lofo_auc.png").exists()


def test_manuscript_builds_and_passes_its_gate():
    pytest.importorskip("docx")
    r = subprocess.run([sys.executable, str(PAPER / "check_paper.py")], cwd=REPO, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
