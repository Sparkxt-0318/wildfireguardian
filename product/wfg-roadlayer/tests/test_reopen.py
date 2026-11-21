"""Reopening option (research/kcf-reopen): off by default; responders' windows only add departures; certificates of a
reopening run verify with the windowed verifier, and a tampered one fails; residents' confirmed mode reopens nothing
without a known burn age; refusals for combinations it does not support."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

PRODUCT = Path(__file__).resolve().parents[1]
CASE, REGION, ISSUE = "uiseong_andong_20250325_1200KST", "uiseong_andong_2025", "2025-03-25T12:00+09:00"
RASTER = PRODUCT / "examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"


def _sets(path):
    out = {}
    for r in csv.DictReader(open(path / ("en/villages_road_cut_%s.csv" % REGION), encoding="utf-8-sig")):
        w = r["departure windows (s after issue)"]
        s = set()
        for piece in filter(None, w.split(";")):
            a, b = piece.split("-")
            s.add((int(a), int(b)))
        out[r["place id"]] = s
    return out


def _covers(big, small):
    return all(any(a <= lo and hi <= b for a, b in big) for lo, hi in small)


def _run(cache, out, *extra):
    from wfg_roadlayer import cli
    return cli.main(["run", "--region", REGION, "--issue-time", ISSUE, "--raster", str(RASTER), "--as-of", ISSUE,
                     "--out", str(out), "--cache", str(cache), *extra])


def test_off_by_default():
    from wfg_roadlayer import settings
    s = settings.load()
    assert s["reopen"]["mode"] == 0 and s["reopen"]["burnout_min"] == 240.0


@pytest.fixture(scope="module")
def responders(cache, tmp_path_factory):
    out = tmp_path_factory.mktemp("reopen") / "responders"
    assert _run(cache, out, "--reopen", "responders") == 0
    return out


def test_responders_only_add_departures(example_out, responders):
    run = json.loads((responders / "run.json").read_text(encoding="utf-8"))
    assert run["reopen"]["mode"] == "responders" and run["reopen"]["cells_reopening_within_horizon"] > 0
    off, on = _sets(example_out["path"] / CASE), _sets(responders)
    assert set(off) == set(on)
    gained = 0
    for pid in off:
        assert _covers(on[pid], off[pid]), pid        # fewer closures can only add departures
        gained += on[pid] != off[pid]
    assert gained > 0


def _pick(responders, k=4):
    """A few villages whose answer changed, plus one that did not."""
    vs = sorted((responders / "certificates/villages").glob("*.json"))
    changed = [p for p in vs if len(json.loads(p.read_text(encoding="utf-8"))["claims"]["windows"]) > 1
               or (json.loads(p.read_text(encoding="utf-8"))["claims"]["windows"] or [[0]])[0][0] > 0]
    return changed[:k] + [p for p in vs if p not in changed][:1]


def test_reopening_certificates_verify(responders):
    files = _pick(responders)
    assert len(files) >= 2
    res = subprocess.run([sys.executable, "-I", str(responders / "certificates/verify_certificate.py"), *map(str, files)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-3000:] + res.stderr[-2000:]


def test_tampered_window_fails(responders, tmp_path):
    cdir = tmp_path / "certificates"
    shutil.copytree(responders / "certificates", cdir)
    p = _pick(responders, 1)[0]
    q = cdir / "villages" / p.name
    c = json.loads(q.read_text(encoding="utf-8"))
    sh = next(s for s in c["shelters"] if s["claimed_feasible"])
    sh["claimed_feasible"][-1][1] += 1                   # claim one second more than is feasible
    q.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    res = subprocess.run([sys.executable, "-I", str(cdir / "verify_certificate.py"), str(q)], capture_output=True, text=True)
    assert res.returncode != 0 and "equation (E)" in res.stdout


def test_confirmed_needs_known_burn_age(example_out, cache, tmp_path):
    """Residents: a REOPENED event before the issue time cannot confirm a cell whose burn age is unknown (input raster
    only): nothing reopens. With a central arrival raster that says the fire came 10 h before the issue time, the cell
    burned over and the confirmation counts."""
    from wfg_roadlayer import geotiff, regiondata
    from pyproj import Transformer
    import gzip
    road = regiondata.Region(REGION, cache).road
    r = geotiff.read(RASTER)
    inst = json.loads(gzip.decompress((example_out["path"] / CASE / "certificates/instance.json.gz").read_bytes()))
    burning = sorted(int(c) for c, b in inst["cell_closure_s"].items() if b == 0)
    assert burning
    x0c, x1c, y0c, y1c = road.cell_rect(burning[len(burning) // 2])
    x, y = (x0c + x1c) / 2, (y0c + y1c) / 2
    lon, lat = Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)
    ev = tmp_path / "events.json"
    ev.write_text(json.dumps({"events": [{"event": "REOPENED", "lat": lat, "lon": lon, "utc": "2025-03-25T02:59:00Z",
                                          "source": "test"}]}), encoding="utf-8")
    out1 = tmp_path / "c1"
    assert _run(cache, out1, "--reopen", "confirmed", "--reopen-confirmed", str(ev)) == 0
    run1 = json.loads((out1 / "run.json").read_text(encoding="utf-8"))
    assert run1["reopen"]["confirmations"]["cells_confirmed"] == 0
    assert _sets(out1) == _sets(example_out["path"] / CASE)
    central = tmp_path / "central.tif"
    vals = np.where(r.data <= 0, -600.0, r.data).astype(np.float32)
    geotiff.write(central, vals, r.affine, r.epsg, nodata=r.nodata, metadata=dict(r.metadata))
    out2 = tmp_path / "c2"
    assert _run(cache, out2, "--reopen", "confirmed", "--reopen-confirmed", str(ev), "--reopen-arrival", str(central)) == 0
    run2 = json.loads((out2 / "run.json").read_text(encoding="utf-8"))
    assert run2["reopen"]["confirmations"]["cells_confirmed"] == 1
    off, on = _sets(example_out["path"] / CASE), _sets(out2)
    assert all(_covers(on[p], off[p]) for p in off)


@pytest.mark.parametrize("extra", [("--reopen", "responders", "--heat"), ("--reopen", "responders", "--fragility"),
                                   ("--reopen", "confirmed")])
def test_refusals(cache, tmp_path, extra):
    assert _run(cache, tmp_path / "r", *extra) == 2


def test_cards_refuse_reopen(cache, tmp_path):
    from wfg_roadlayer import cli
    assert cli.main(["cards", "--region", REGION, "--issue-time", ISSUE, "--raster", str(RASTER), "--as-of", ISSUE,
                     "--out", str(tmp_path / "cards"), "--cache", str(cache), "--reopen", "responders"]) == 2
