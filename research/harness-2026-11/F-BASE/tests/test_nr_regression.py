"""Regression test for the no-re-entry defect (DESIGN.md (f), acceptance 1; Nora's counter-example).

UA 20250325T170000Z h5 kriged_mean, origin osm_node_415158323, under no_reentry/1 built FROM THE NR PACKET:
  dep 7200: exact, S1, S2 all NO_ROUTE; edges 152, 153, 154 blocked at the departure second.
  dep 0:    exact ROUTE 259, S1 ROUTE 259, S2 NO_ROUTE.
Needs the local packets and the (c) run directory, so it runs only when these env vars are set (skipped otherwise):
  FBASE_NR_FDYN (reopening worktree), FBASE_NR_FDYN_NR (NR worktree), FBASE_NR_F32 (F-3.2 worktree root),
  FBASE_NR_CDIR ((c) run dir), FBASE_NR_PY (python with the F-3.2 deps).
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ENV = ("FBASE_NR_FDYN", "FBASE_NR_FDYN_NR", "FBASE_NR_F32", "FBASE_NR_CDIR", "FBASE_NR_PY")
PACKET = "uiseong_andong_2025:20250325T170000Z:5:kriged_mean"
ORIGIN = "osm_node_415158323"


def run(dep):
    out = Path(tempfile.mkdtemp())
    f32 = Path(os.environ["FBASE_NR_F32"])
    env = dict(os.environ, PYTHONPATH="experimental/sipp-routing/src:experimental/scenario-members/src:"
                                      "experimental/synthetic-truth/src")
    subprocess.run([os.environ["FBASE_NR_PY"], str(HERE / "run_fdyn_nr.py"), "--fdyn", os.environ["FBASE_NR_FDYN"],
                    "--fdyn-nr", os.environ["FBASE_NR_FDYN_NR"], "--nr-manifest", "MANIFEST_v3_6.json",
                    "--transform", "no_reentry/1", "--f32", "research/harness-2026-11/F-3.2", "--packet", PACKET,
                    "--c-dir", os.environ["FBASE_NR_CDIR"], "--out-dir", str(out), "--only", f"{ORIGIN}:{dep}"],
                   cwd=f32, env=env, check=True, capture_output=True)
    rows = [json.loads(l) for f in out.glob("*.jsonl") for l in f.read_text().splitlines()]
    return [r for r in rows if not r.get("header")]


@pytest.mark.skipif(not all(k in os.environ for k in ENV), reason="local NR packets / (c) run dir not configured")
def test_dep7200_no_route():
    (r,) = run(7200)
    nr = r["no_reentry"]
    assert nr["exact"][0] == "NO_ROUTE" and nr["s1"][0] == "NO_ROUTE" and nr["s2"][0] == "NO_ROUTE"
    assert {152, 153, 154} <= set(r["blocked_edges_at_dep"])


@pytest.mark.skipif(not all(k in os.environ for k in ENV), reason="local NR packets / (c) run dir not configured")
def test_dep0_route():
    (r,) = run(0)
    nr = r["no_reentry"]
    assert nr["exact"] == ["ROUTE", 259] and nr["s1"] == ["ROUTE", 259] and nr["s2"][0] == "NO_ROUTE"
