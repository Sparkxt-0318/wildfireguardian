"""The loop's own reporting tooling gets a gate, because nothing else covered it.

A 2026-09-03 lap lost its report step to a SyntaxError in scripts/auto/*: the
files used 3.12-only syntax, `make verify` reads them as text, pytest never
collected them, and check_declared_deps tolerates a file it cannot parse
(docs/auto/MEMO.md). This test byte-compiles every script under scripts/auto
with the running interpreter and smoke-runs the two renderers into a temp dir.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
AUTO_SCRIPTS = sorted((REPO / "scripts" / "auto").glob("*.py"))


@pytest.mark.parametrize("path", AUTO_SCRIPTS, ids=lambda p: p.name)
def test_auto_script_parses_on_this_interpreter(path: Path):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_dashboard_renders_to_a_temp_file(tmp_path: Path):
    out = tmp_path / "board.html"
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "auto" / "dashboard.py"), "--out", str(out)],
                       cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    html = out.read_text(encoding="utf-8")
    assert "<title>" in html and "Project map" in html and "Backlog board" in html


def test_images_render_to_a_temp_dir(tmp_path: Path):
    pytest.importorskip("matplotlib")
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "auto" / "render_images.py"),
                        "--stamp", "TEST", "--out", str(tmp_path)],
                       cwd=REPO, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    names = sorted(p.name for p in (tmp_path / "TEST").glob("*.png"))
    assert names == ["01_full_map.png", "02_changes.png", "03_backlog.png", "04_rubric.png", "05_timeline.png"]
    assert all((tmp_path / "latest" / n).exists() for n in names)
