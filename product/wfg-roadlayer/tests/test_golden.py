"""Golden-file test: `python -m wfg_roadlayer example` reproduces the committed 25 March 2025 sheets exactly."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PRODUCT = Path(__file__).resolve().parents[1]
GOLDEN = PRODUCT / "golden"
CASES = sorted(p.name for p in GOLDEN.iterdir() if p.is_dir())


def test_golden_cases_exist():
    assert CASES == ["uiseong_andong_20250325_1200KST", "yeongdeok_20250325_1800KST"]


@pytest.mark.parametrize("case", CASES)
def test_csv_identical(example_out, case):
    g = GOLDEN / case
    for gold in sorted(g.rglob("*.csv")):
        rel = gold.relative_to(g)
        got = example_out["path"] / case / rel
        assert got.read_bytes() == gold.read_bytes(), "%s differs from golden (python3 tests/update_golden.py after a reviewed change)" % rel


@pytest.mark.parametrize("case", CASES)
def test_every_output_file(example_out, case):
    """Every certificate, CSV and helper byte for byte; the PDFs byte for byte when reportlab is the version that wrote
    the golden files (its output bytes can change between versions), otherwise one page each."""
    gold = json.loads((GOLDEN / case / "MANIFEST.json").read_text(encoding="utf-8"))
    run = json.loads((example_out["path"] / case / "run.json").read_text(encoding="utf-8"))
    same_rl = run["versions"]["reportlab"] == gold["versions"]["reportlab"]
    assert set(run["files_sha256"]) == set(gold["files_sha256"])
    for rel, sha in gold["files_sha256"].items():
        if rel.endswith(".pdf") and not same_rl:
            continue
        assert run["files_sha256"][rel] == sha, rel
    for k in ("counts", "villages", "certificates"):
        assert run[k] == gold[k], k
    assert run["model"]["instance_sha256_uncompressed"] == gold["model"]["instance_sha256_uncompressed"]


@pytest.mark.parametrize("case", CASES)
def test_sheets_one_page_with_notice(example_out, case):
    sheets = sorted((example_out["path"] / case).rglob("*.pdf"))
    assert sheets
    for p in sheets:
        b = p.read_bytes()
        assert b.count(b"/Type /Page") - b.count(b"/Type /Pages") == 1, p.name
    if shutil.which("pdftotext"):
        for p in sheets:
            txt = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout
            lang = p.parent.parent.name
            want = "모델 출력 · 참고용 · 명령 아님" if lang == "ko" else "Model output · advisory · not an order"
            assert txt.count(want) >= 2, p.name  # top banner and footer


@pytest.mark.parametrize("case", CASES)
def test_run_time_under_five_minutes(example_out, case):
    run = json.loads((example_out["path"] / case / "run.json").read_text(encoding="utf-8"))
    assert run["run_time_s"]["total"] < 300


def test_csv_notice_on_every_row(example_out):
    for case in CASES:
        for p in (example_out["path"] / case).rglob("*.csv"):
            lines = p.read_text(encoding="utf-8-sig").splitlines()[1:]
            assert lines and all(l.endswith("모델 출력 · 참고용 · 명령 아님") or l.endswith("Model output · advisory · not an order")
                                 for l in lines), p.name
