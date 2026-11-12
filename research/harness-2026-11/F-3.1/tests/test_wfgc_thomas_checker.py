"""NO_ROUTE certificates exported from the backward field are accepted by F-3.2's independent checker
(check_py.py, fetched from branch origin/thomas/f-3.2-certificates; skipped when unavailable)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from deadline_field import intervals as iv
from deadline_field.core import Instance, backward, issue_core
from deadline_field.export import wfgc_no_route
from deadline_field.real import ROOT

from .test_field_vs_oracle import random_instance

REF = "origin/thomas/f-3.2-certificates:research/harness-2026-11/F-3.2/check_py.py"


@pytest.fixture(scope="module")
def checker(tmp_path_factory):
    r = subprocess.run(["git", "-C", str(ROOT), "show", REF], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("F-3.2 checker not available (git fetch origin thomas/f-3.2-certificates)")
    p = tmp_path_factory.mktemp("chk") / "check_py.py"
    p.write_text(r.stdout)
    return p


def test_no_route_certificates_accepted(checker, tmp_path):
    accepted = 0
    for seed in range(600):
        raw = random_instance(seed)
        inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
        fld = backward(inst)
        for o in range(inst.n_nodes):
            core = issue_core(fld, o)
            deps = [d for d in range(inst.H + 1) if not iv.contains(core, d)]
            if not deps:
                continue
            dep = deps[seed % len(deps)]
            txt, _ = wfgc_no_route(fld, o, dep)
            f = tmp_path / "c.wfgc"
            f.write_text(txt)
            r = subprocess.run([sys.executable, str(checker), str(f)], capture_output=True, text=True)
            assert r.returncode == 0 and r.stdout.startswith("ACCEPT NO_ROUTE"), (seed, o, dep, r.stdout)
            accepted += 1
            break
    assert accepted > 500
