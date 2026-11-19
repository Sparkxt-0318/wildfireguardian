"""Heat option (research/kcf-radiation): vendored byte for byte, off by default, and when on it only moves road cuts
earlier and certificates still verify."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
VEND = PRODUCT / "wfg_roadlayer/vendor/kcf_radiation"
RESEARCH = REPO / "research/kcf-radiation/kcf_radiation"
NAMES = sorted(p.name for p in VEND.glob("*.py"))


@pytest.mark.parametrize("name", NAMES)
def test_vendored_byte_identical(name):
    assert (VEND / name).read_bytes() == (RESEARCH / name).read_bytes()


def test_off_by_default():
    from wfg_roadlayer import settings
    assert settings.load()["heat"]["enabled"] == 0


def _windows(path, region):
    rows = {}
    for r in csv.DictReader(open(path / ("en/villages_road_cut_%s.csv" % region), encoding="utf-8-sig")):
        L = r["departure windows (s after issue)"]
        rows[r["place id"]] = int(L.split(";")[-1].split("-")[1]) if L else None
    return rows


def test_heat_on_moves_cuts_only_earlier(example_out, cache, tmp_path):
    from wfg_roadlayer import cli
    case, region = "uiseong_andong_20250325_1200KST", "uiseong_andong_2025"
    out = tmp_path / "heat"
    code = cli.main(["run", "--region", region, "--issue-time", "2025-03-25T12:00+09:00",
                     "--raster", str(PRODUCT / "examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"),
                     "--as-of", "2025-03-25T12:00+09:00", "--out", str(out), "--cache", str(cache), "--heat"])
    assert code == 0
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["heat"]["threshold_kw_m2"] == 4.7
    off = _windows(example_out["path"] / case, region)
    on = _windows(out, region)
    assert set(off) == set(on)
    for pid in off:
        if off[pid] is None:
            assert on[pid] is None
        elif on[pid] is not None:
            assert on[pid] <= off[pid], pid
    res = subprocess.run([sys.executable, "-I", str(out / "certificates/verify_certificate.py"), str(out / "certificates")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
