"""The entrant npz contract: the keys the scorer reads are the keys our writers write.

⚠ WHY THIS FILE EXISTS. F1's first scoring attempt died with

    KeyError: 'stack is not a file in the archive'

*after* the field had taken 36 minutes to build on the author's laptop. The bundle had been
written with the FIELD npz's key names (``haz_stack`` / ``haz_times``), which is the
``routing_demo_*.npz`` contract, while ``scripts/benchmark/score_kspread.py`` reads
``stack`` / ``times_min`` / ``grid_extent``. Two neighbouring files, two different
vocabularies, and nothing anywhere asserted that a bundle we wrote could be read by the
scorer we wrote. The cost of that gap is paid in whole simulation runs, so it is pinned here.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
SCORER = REPO / "scripts/benchmark/score_kspread.py"
ENTRANTS = REPO / "data/processed/benchmark/entrants"
#: What an entrant event npz must hold. Not a guess: the committed bundles carry exactly
#: these, and the scorer reads exactly these.
CONTRACT = ("grid_extent", "stack", "times_min")


def test_the_scorer_reads_exactly_the_contract_keys():
    """Derived from the scorer's source, so the contract cannot drift silently."""
    src = SCORER.read_text(encoding="utf-8")
    read = set(re.findall(r'\be\[\s*"([a-z_]+)"\s*\]', src))
    assert read == set(CONTRACT), (
        f"score_kspread reads {sorted(read)} from an entrant npz, but this contract says "
        f"{sorted(CONTRACT)}. Update both together or a bundle becomes unscoreable."
    )


@pytest.mark.parametrize("bundle", sorted(p.name for p in ENTRANTS.iterdir() if p.is_dir())
                         if ENTRANTS.exists() else [])
def test_every_committed_entrant_bundle_satisfies_the_contract(bundle):
    meta = json.loads((ENTRANTS / bundle / "entrant.json").read_text(encoding="utf-8"))
    for event, spec in meta["events"].items():
        npz = REPO / spec["npz"]
        if not npz.exists():
            pytest.skip(f"{spec['npz']} is not in this checkout")
        z = np.load(npz)
        missing = [k for k in CONTRACT if k not in z.files]
        assert not missing, (
            f"{bundle}/{event} is missing {missing}; it holds {sorted(z.files)}. "
            "The scorer will raise KeyError on it — the exact failure this file pins."
        )


def test_the_adopt_script_writes_a_scoreable_bundle(tmp_path, monkeypatch):
    """Round-trip: build a field npz, adopt it, and read the result the scorer's way.

    The field npz deliberately uses haz_stack / haz_times — the names that broke it — so
    this test fails if the adopt script ever goes back to copying them through.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "adopt", REPO / "scripts/adopt_f1_stage2_naming.py")
    adopt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adopt)

    grid = np.array([0.0, 0.0, 1000.0, 1000.0, 500.0])
    stack = np.zeros((3, 2, 2), dtype=np.float32)
    times = np.array([0.0, 180.0, 360.0])
    outdir = tmp_path / "forecast_track"
    outdir.mkdir(parents=True)
    npz = outdir / "routing_demo_f1_frozen_t0.npz"
    np.savez_compressed(npz, grid_extent=grid, haz_stack=stack, haz_times=times)

    import hashlib
    art = outdir / "forecast_track_f1.json"
    art.write_text(json.dumps({
        "generated_utc": "2026-09-15T00:00:00Z", "git_commit": "0" * 40,
        "field": {"npz_sha256": hashlib.sha256(npz.read_bytes()).hexdigest(),
                  "parameters": {"cell_size_m": 500.0},
                  "held_out_yeongdeok_auc_same_fit": 0.5},
    }), encoding="utf-8")
    leak = tmp_path / "leakfree.json"
    leak.write_text(json.dumps({"held_out_yeongdeok_auc": {"leakfree_fold": 0.5}}), encoding="utf-8")

    monkeypatch.setattr(adopt, "REPO", tmp_path)
    monkeypatch.setattr(adopt, "OUT", art)
    monkeypatch.setattr(adopt, "OUT_NPZ", npz)
    monkeypatch.setattr(adopt, "LEAKFREE_JSON", leak)
    monkeypatch.setattr(adopt, "OLD_ENTRANT", tmp_path / "old")
    monkeypatch.setattr(adopt, "NEW_ENTRANT", tmp_path / "new")
    monkeypatch.setattr(adopt, "DOC", tmp_path / "doc.md")

    assert adopt.main() == 0
    z = np.load(tmp_path / "new" / f"{adopt.FIRE}.npz")
    assert sorted(z.files) == sorted(CONTRACT), sorted(z.files)
    # Read it the way the scorer does — this is the line that used to raise.
    np.asarray(z["stack"], float), np.asarray(z["times_min"], float)
    assert np.array_equal(np.asarray(z["stack"]), stack)


def test_the_f1_script_writes_the_contract_not_the_field_names():
    """The other writer, pinned by source: it is not exercised without the raw bundle."""
    src = (REPO / "scripts/run_forecast_track_f1.py").read_text(encoding="utf-8")
    m = re.search(r"np\.savez_compressed\(ev_npz,(.*?)\)\n", src, re.S)
    assert m, "run_forecast_track_f1.py no longer writes an entrant npz the same way"
    call = m.group(1)
    for k in CONTRACT:
        assert re.search(rf"\b{k}\s*=", call), f"the entrant npz call does not set {k}=: {call}"
    for bad in ("haz_stack=", "haz_times="):
        assert bad not in call, f"the entrant npz call still uses the FIELD name {bad}"
