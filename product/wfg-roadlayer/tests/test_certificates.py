"""Certificates re-verify with the shipped standalone verifier (no tool import), and tampering is caught."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

CASE = "uiseong_andong_20250325_1200KST"


def verify(*paths):
    first = Path(paths[0])
    script = first / "verify_certificate.py" if first.is_dir() else first.parents[1] / "verify_certificate.py"
    return subprocess.run([sys.executable, "-I", str(script)] + [str(p) for p in paths], capture_output=True, text=True)


def test_all_uiseong_certificates_pass(example_out):
    r = verify(example_out["path"] / CASE / "certificates")
    assert r.returncode == 0, r.stdout[-2000:]
    assert "84 certificate(s): 84 pass, 0 fail" in r.stdout


def test_sample_of_yeongdeok_certificates_pass(example_out):
    c = example_out["path"] / "yeongdeok_20250325_1800KST/certificates/villages"
    sample = sorted(c.glob("*.json"))[::15]
    r = verify(*sample)
    assert r.returncode == 0, r.stdout[-2000:]


def _tamper(example_out, tmp_path, fn):
    src = example_out["path"] / CASE / "certificates"
    dst = tmp_path / "certificates"
    shutil.copytree(src, dst)
    cert = sorted((dst / "villages").glob("*.json"), key=lambda p: -len(p.read_text()))[0]
    c = json.loads(cert.read_text(encoding="utf-8"))
    fn(c)
    cert.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    return verify(cert)


def test_tampered_deadline_fails(example_out, tmp_path):
    def f(c):
        c["claims"]["latest_departure_s"] = (c["claims"]["latest_departure_s"] or 0) + 60
    r = _tamper(example_out, tmp_path, f)
    assert r.returncode == 1 and "FAIL" in r.stdout


def test_tampered_witness_fails(example_out, tmp_path):
    def f(c):
        w = c["witnesses"][0]
        w["legs"] = w["legs"][1:]  # drop the first leg
    r = _tamper(example_out, tmp_path, f)
    assert r.returncode == 1 and "checker.py" in r.stdout


def test_tampered_flag_fails(example_out, tmp_path):
    def f(c):
        c["stage"]["flag"] = not c["stage"]["flag"] if c["stage"]["flag"] is not None else True
    r = _tamper(example_out, tmp_path, f)
    assert r.returncode == 1 and "flag" in r.stdout


def test_shipped_checker_is_the_research_checker(example_out):
    repo = Path(__file__).resolve().parents[3]
    assert (example_out["path"] / CASE / "certificates/checker.py").read_bytes() == (repo / "research/kcf-theorem/checker.py").read_bytes()
