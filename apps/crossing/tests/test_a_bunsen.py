"""Tests for the Bunsen test-A models and analysis. ALL INPUT IS SYNTHETIC (field_tests/a_bunsen_synth.py, seeded)."""
from __future__ import annotations

import csv
import math
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))

from field_tests import a_bunsen_analyse as A, a_bunsen_synth as S, bunsen_models as bm  # noqa: E402

FLAME = bm.Flame(q_kw=bm.power_kw(1.0, 33.9))
RS = [0.10, 0.15, 0.20, 0.30, 0.40]


def test_power():
    assert bm.power_kw(1.0, 33.9) == pytest.approx(0.565, rel=1e-3)


def test_thin_line_matches_kcf_law_at_midheight():
    for r in RS:
        law = bm._law().line_flux_s(r, 1.0, FLAME.q_kw / FLAME.height_m, FLAME.height_m / 2)
        assert bm._thin_line_centre(r, FLAME) == pytest.approx(law, rel=2e-3)


def test_curves_collapse_at_bunsen_scale():
    c = bm.curves(RS, FLAME)
    assert np.allclose(c["closed_form"], c["voxel_sum"], rtol=0.01)
    assert np.allclose(c["fds_fit_transfer"], c["voxel_sum"], rtol=0.02)       # optical depth ~ 0.01-0.02
    assert np.allclose(c["point"][-1], c["closed_form"][-1], rtol=0.02)          # far field = point source
    assert c["closed_form"][0] < c["point"][0] * 0.9                             # near field differs by >10 %


def test_curves_linear_in_power():
    f2 = bm.Flame(q_kw=2 * FLAME.q_kw)
    assert bm.voxel_sum(0.2, f2) == pytest.approx(2 * bm.voxel_sum(0.2, FLAME))


def test_shape_separation_says_bunsen_cannot_split_them():
    s = bm.shape_separation(RS, FLAME, "closed_form", "voxel_sum", 0.05)
    assert s["max_shape_diff_pct"] < 1.0 and s["sqrt_d2_sigma"] < 1.0


def test_optical_depth_needed():
    assert bm.optical_depth_fit(0.4, 0.02) < 0.03 < 0.7 < bm.optical_depth_fit(0.0, 3.0)


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    truth = S.make(d / "log.csv", truth="closed_form", chi_true=0.08, seed=7)
    out = A.run(d / "log.csv", truth["sheet"], d / "out", True)
    return d, truth, out


def test_recovers_flux_and_chi(synth):
    d, truth, out = synth
    for row in out["distances"]:
        q_true = np.mean([truth["q_true"][(row["distance_m"], k)] for k in (1, 2, 3)])
        assert row["q_kw_m2"] == pytest.approx(q_true, rel=0.12, abs=0.004)
    c = out["compare"]["curves"]["closed_form"]
    assert c["chi_eff"] == pytest.approx(0.08, rel=0.15)
    assert out["loss"]["h"] == pytest.approx(truth["h_true"], rel=0.10)


def test_verdict_does_not_claim_what_bunsen_cannot_show(synth):
    _, _, out = synth
    v = out["compare"]["verdict"]
    assert v["favoured"] is None
    assert "point" in " ".join(v["reasons"]) or "not distinguishable" in " ".join(v["reasons"])
    assert out["compare"]["curves"]["point"]["chi2"] > out["compare"]["curves"]["closed_form"]["chi2"]


def test_outputs_written_and_labelled_simulated(synth):
    d, _, _ = synth
    o = d / "out"
    for f in ("A_bunsen_runs.csv", "A_bunsen_table.csv", "A_bunsen_compare.csv", "A_bunsen_figure.png",
              "A_bunsen_snippet.md", "A_bunsen_summary.json"):
        assert (o / f).exists() and (o / f).stat().st_size > 0
    assert "SIMULATED" in (o / "A_bunsen_snippet.md").read_text()
    assert all(r["simulated"] == "true" for r in csv.DictReader(open(o / "A_bunsen_table.csv")))
    assert (o / "A_bunsen_figure.png").read_bytes()[:4] == b"\x89PNG"


def test_over_70c_run_is_reported_and_excluded(tmp_path):
    truth = S.make(tmp_path / "log.csv", seed=3, overheat_at=0.10)
    out = A.run(tmp_path / "log.csv", truth["sheet"], tmp_path / "o", True)
    runs = list(csv.DictReader(open(tmp_path / "o" / "A_bunsen_runs.csv")))
    bad = [r for r in runs if r["ok"] == "false"]
    assert len(bad) == 1 and "UNUSABLE" in bad[0]["status"] and float(bad[0]["plate_max_c"]) >= 70
    assert [r["n_runs"] for r in out["distances"]][0] == 2
    assert "Runs not used" in (tmp_path / "o" / "A_bunsen_snippet.md").read_text()


def test_no_cooldown_runs_is_flagged_not_hidden(tmp_path):
    truth = S.make(tmp_path / "log.csv", seed=4)
    rows = [r for r in csv.DictReader(open(tmp_path / "log.csv")) if r["kind"] != "cooldown"]
    with open(tmp_path / "nocool.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, rows[0].keys()); w.writeheader(); w.writerows(rows)
    out = A.run(tmp_path / "nocool.csv", truth["sheet"], tmp_path / "o", True)
    assert out["u_h_rel"] == 0.5 and "UNFITTED" in out["loss"]["note"]
    assert "UNFITTED" in (tmp_path / "o" / "A_bunsen_snippet.md").read_text()


def test_flame_too_weak_gives_no_verdict(tmp_path):
    truth = S.make(tmp_path / "log.csv", chi_true=0.0005, seed=5)
    out = A.run(tmp_path / "log.csv", truth["sheet"], tmp_path / "o", True)
    assert out["compare"]["verdict"]["favoured"] is None
    assert out["compare"]["n_used"] < 3 and "NO VERDICT" in out["compare"]["verdict"]["text"]


def test_phase_column_is_honoured(tmp_path):
    truth = S.make(tmp_path / "log.csv", seed=6)
    rows = list(csv.DictReader(open(tmp_path / "log.csv")))
    for r in rows:
        t = float(r["t_s"]); r["phase"] = "baseline" if t < 0 else ("exposure" if t <= 60 else "tail")
        if r["kind"] == "cooldown":
            r["phase"] = "tail"
    with open(tmp_path / "ph.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, rows[0].keys()); w.writeheader(); w.writerows(rows)
    a = A.run(tmp_path / "ph.csv", truth["sheet"], tmp_path / "o1", True)
    b = A.run(tmp_path / "log.csv", truth["sheet"], tmp_path / "o2", True)
    assert [r["q_kw_m2"] for r in a["distances"]] == pytest.approx([r["q_kw_m2"] for r in b["distances"]], rel=0.03)


def test_bad_log_columns_rejected(tmp_path):
    (tmp_path / "x.csv").write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        A.read_log(tmp_path / "x.csv")


def test_thermocouple_fault_rows_dropped(tmp_path):
    S.make(tmp_path / "log.csv", seed=8)
    rows = list(csv.DictReader(open(tmp_path / "log.csv")))
    for r in rows:
        r["fault"] = ""
    rows[500]["fault"] = "OC"
    with open(tmp_path / "f.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, rows[0].keys()); w.writeheader(); w.writerows(rows)
    runs = A.read_log(tmp_path / "f.csv")
    assert sum(r.n_fault for r in runs) == 1
