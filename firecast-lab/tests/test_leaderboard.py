"""Per-window terms and the leaderboard aggregator on SYNTHETIC fires (review finding A-M4 and A-m5).

Every row here is SYNTHETIC and goes to pytest's tmp_path, never to firecast-lab/results/ or LEADERBOARD.md."""
import csv
import json

import numpy as np
import pytest

import synthetic as syn
from firecast_lab import baselines as bl
from firecast_lab import cli, harness
from firecast_lab import leaderboard as lb
from firecast_lab import metrics as m
from firecast_lab.members import burned_by
from firecast_lab.splits import LAB

FIRES = {"SYNTHETIC_A1": "A", "SYNTHETIC_A2": "A", "SYNTHETIC_B1": "B", "SYNTHETIC_B2": "B"}
SPLITS = syn.splits(**FIRES)
K, SEED, LENGTH = 8, 3, 3.0


def _fire(i):
    return syn.fire(seed=40 + i, wind_toward_deg=25.0 * i)


def _windows_of(ids):
    return [w for i, f in enumerate(FIRES) if f in ids for w in syn.windows(f, *_fire(i), fold=FIRES[f])]


@pytest.fixture(scope="module")
def scored():
    """Rows of a cross-fitted SYNTHETIC logistic run (copula members) and, per window, the scored cells."""
    rows = harness.run("logistic", "dev", _windows_of, SPLITS, K=K, seed=SEED, coupling="copula",
                       length_cells=LENGTH)
    cells = []
    draw = dict(K=K, seed=SEED, coupling="copula", length_cells=LENGTH)
    for window, model, reference in harness.crossfit("logistic", "dev", _windows_of, SPLITS):
        hours, reference_hours = bl.forecast(model, window, **draw)[0], bl.forecast(reference, window, **draw)[0]
        mask = window.fitting_rows & ~np.isnan(hours).any(axis=0) & ~np.isnan(reference_hours).any(axis=0)
        lead = window.lead_h
        y = ((window.outcome_h > 0) & (window.outcome_h <= lead)).astype(float)
        cells.append(dict(window=window, mask=mask, y=y, p=burned_by(hours, lead),
                          r=burned_by(reference_hours, lead), lattice=m.hourly_arrival(hours, lead),
                          observed=m.hourly_arrival(window.outcome_h, lead), seed=syn.fd.case_seed(
                              SEED, window.fire, window.cutoff_utc)))
    return [lb.parse_row(r) for r in rows], cells


def test_pooled_terms_equal_the_direct_metrics_on_concatenated_cells(scored):
    rows, cells = scored
    assert len(rows) == len(cells) >= 8 and {r["fire"] for r in rows} == set(FIRES)
    cat = lambda key: np.concatenate([c[key][c["mask"]] for c in cells])
    y, p, r = cat("y"), cat("p"), cat("r")
    lattice = np.concatenate([c["lattice"][:, c["mask"]] for c in cells], axis=1)
    observed, every = cat("observed"), np.ones(y.size, bool)
    assert 0 < y.sum() < y.size and len(np.unique(p)) > 3                    # a non-trivial SYNTHETIC case
    entry = lb.score_entry(rows, draws=200)
    point = {k: v["point"] for k, v in entry["metrics"].items()}
    assert entry["cells"] == y.size and entry["positives"] == y.sum() and entry["fires"] == 4
    assert point["brier"] == pytest.approx(m.brier(y, p, every), rel=1e-12)
    assert point["bss_vs_persistence"] == pytest.approx(m.brier_skill(y, p, 0.0, every), rel=1e-12)
    assert point["bss_vs_calibrated_dilation"] == pytest.approx(m.brier_skill(y, p, r, every), rel=1e-12)
    assert point["ece"] == pytest.approx(m.ece(y, p, every), rel=1e-12)
    direct = m.reliability(y, p, every)
    assert [row["count"] for row in entry["reliability"]] == [row["count"] for row in direct]
    for pooled, row in zip(entry["reliability"], direct):
        assert pooled["forecast_sum"] == pytest.approx(row["forecast_sum"], rel=1e-12, abs=1e-12)
        assert pooled["observed_sum"] == row["observed_sum"]
    assert point["average_precision"] == pytest.approx(m.average_precision(y, p, every), rel=1e-12)
    assert point["base_rate"] == pytest.approx(y.mean(), rel=1e-12)
    for n in m.FSS_SIZES:                       # aggregate FSS: the per-cell terms of every window, summed
        terms = [m.fss_terms(c["y"], c["p"], c["mask"], n) for c in cells]
        num, den = (np.concatenate([t[i] for t in terms]) for i in (0, 1))
        assert point[f"fss_{n}"] == pytest.approx(1.0 - num.sum() / den.sum(), rel=1e-12)
    assert point["crps_h"] == pytest.approx(m.crps_arrival(lattice, observed, every, 24), rel=1e-12)
    assert point["crps_fair_h"] == pytest.approx(m.crps_arrival(lattice, observed, every, 24, fair=True), rel=1e-12)
    spread = m.spread_skill(lattice, observed, every, sd_edges_h=m.SPREAD_SD_EDGES_H)
    assert point["spread_skill"] == pytest.approx(spread["ratio"], rel=1e-12)
    assert [row["cells"] for row in entry["spread_rows"]] == [row["cells"] for row in spread["rows"]]
    assert sum(row["cells"] for row in spread["rows"]) == y.size
    for pooled, row in zip(entry["spread_rows"], spread["rows"]):
        assert pooled["ratio"] == pytest.approx(row["ratio"], rel=1e-12, nan_ok=True)
    # rank histogram: ties are broken with each window's seed, so the reference sums the per-window histograms;
    # its deterministic parts are checked against one call on all cells
    windows = [m.rank_histogram(c["lattice"], c["observed"], c["mask"], seed=c["seed"]) for c in cells]
    assert entry["rank_counts"] == np.sum([w["counts"] for w in windows], axis=0).tolist()
    whole = m.rank_histogram(lattice, observed, every, seed=0)
    assert sum(entry["rank_counts"]) == whole["cells"] and entry["rank_fully_tied"] == whole["fully_tied"]
    outer = (entry["rank_counts"][0] + entry["rank_counts"][-1]) / sum(entry["rank_counts"])
    assert point["rank_outer_share"] == pytest.approx(outer, rel=1e-12)
    for name, value in entry["metrics"].items():          # whole-fire intervals around every defined point value
        if value["point"] is not None:
            lo, hi = value["interval"]
            assert lo <= value["point"] + 1e-12 and value["point"] <= hi + 1e-12, name
    assert entry["metrics"]["brier_probability_field"]["point"] is not None   # the logistic has a probability field


def test_pooling_helpers_match_the_direct_metrics():
    rng = np.random.default_rng(8)                                             # SYNTHETIC, many ties
    count = rng.integers(0, 9, 2000)
    y = (rng.random(2000) < 0.05 + 0.1 * count / 8).astype(float)
    every = np.ones(y.size, bool)
    cells, positives = m.level_counts(y, count, every, 9)
    assert cells.sum() == y.size and positives.sum() == y.sum()
    assert m.average_precision_from_counts(cells, positives) == pytest.approx(m.average_precision(y, count / 8, every),
                                                                              rel=1e-12)
    assert np.isnan(m.average_precision_from_counts(cells, np.zeros(9)))
    rows = m.reliability(y, count / 8, every)
    sums = [[row[k] for row in rows] for k in ("count", "forecast_sum", "observed_sum")]
    assert m.ece_from_sums(*sums) == pytest.approx(m.ece(y, count / 8, every), rel=1e-12)
    assert m.reliability_from_sums(*sums) == rows
    with pytest.raises(ValueError, match="levels"):
        m.level_counts(y, count + 0.5, every, 9)


def test_fire_bootstrap_blocks_do_not_change_the_result():
    rng = np.random.default_rng(2)                                             # SYNTHETIC
    fire = np.repeat([f"SYNTHETIC_{i}" for i in range(7)], 5)
    terms = rng.random((fire.size, 40))
    statistic = lambda s: s[..., :20].sum(axis=-1) / s[..., 20:].sum(axis=-1)
    whole = m.fire_bootstrap(fire, terms, statistic, draws=999, seed=4)
    assert m.fire_bootstrap(fire, terms, statistic, draws=999, seed=4, block_elements=1) == whole
    assert m.fire_bootstrap(fire, terms, statistic, draws=999, seed=4, block_elements=7 * 40 * 100) == whole


# ------------------------------------------------------------------------------------------- the command
@pytest.fixture(scope="module")
def results(tmp_path_factory):
    """`firecast-lab run` CSVs of two baselines on a SYNTHETIC data root, plus a CSV that is not a run file."""
    root = syn.write_root(tmp_path_factory.mktemp("synthetic_root"), {f: _fire(i) for i, f in enumerate(FIRES)})
    folder = tmp_path_factory.mktemp("synthetic_results")
    for name in ("persistence", "calibrated_dilation"):
        cli.main(["run", "--baseline", name, "--split", "dev", "--members", "4", "--data-root", str(root),
                  "--out", str(folder / f"{name}.csv")], splits=SPLITS)
    (folder / "decision_dilation.csv").write_text("model,request\nSYNTHETIC,R000\n")
    return folder


def test_leaderboard_writes_synthetic_rows_only_where_told_and_labels_them(results, tmp_path, monkeypatch, capsys):
    committed = (LAB / "LEADERBOARD.md").read_bytes()
    monkeypatch.setattr(cli, "LEADERBOARD", tmp_path / "default" / "LEADERBOARD.md")
    with pytest.raises(lb.LeaderboardError, match="SYNTHETIC"):
        cli.main(["leaderboard", "--results", str(results)])                    # no --out on SYNTHETIC rows
    assert not (tmp_path / "default").exists()
    out = cli.main(["leaderboard", "--results", str(results), "--out", str(tmp_path / "board.md"), "--draws", "300"])
    text, board = out.read_text(), json.loads(out.with_suffix(".json").read_text())
    assert text.startswith("# SYNTHETIC - Track A leaderboard") and "not a result about any real fire" in text
    assert board["synthetic"] and len(board["tables"]) == 1
    table = board["tables"][0]
    assert table["title"].startswith("SYNTHETIC - KR, dev, lead 24 h, headline domain, K = 4")
    assert f"## {table['title']}" in text and table["fires"] == 4
    assert {e["baseline"] for e in table["entries"]} == {"persistence", "calibrated_dilation"}
    for e in table["entries"]:
        assert e["synthetic"] and e["metrics"]["brier"]["point"] is not None and e["fires"] == 4
    persistence = next(e for e in table["entries"] if e["baseline"] == "persistence")
    assert persistence["metrics"]["bss_vs_persistence"]["point"] == 0.0         # persistence against itself
    printed = capsys.readouterr().out.splitlines()
    assert printed and all(line.startswith("SYNTHETIC ") for line in printed)
    assert any("not a run file, skipped: decision_dilation.csv" in line for line in printed)
    assert (LAB / "LEADERBOARD.md").read_bytes() == committed and not (LAB / "LEADERBOARD.json").exists()


def _rows(results):
    rows, _ = lb.read_rows(results)
    return rows


def test_leaderboard_refuses_runs_that_scored_different_cells_or_windows(results):
    rows = _rows(results)
    assert lb.build(rows, draws=50)["tables"]
    other = [dict(r) for r in rows]
    victim = next(r for r in other if r["baseline"] == "calibrated_dilation")
    victim["mask_sha256"] = "0" * 16                                           # one window scored other cells
    with pytest.raises(lb.LeaderboardError, match="different cells"):
        lb.build(other, draws=50)
    dropped = next(r for r in rows if r["baseline"] == "persistence")
    with pytest.raises(lb.LeaderboardError, match="different windows"):
        lb.build([r for r in rows if r is not dropped], draws=50)                # one run lacks a window
    with pytest.raises(lb.LeaderboardError, match="two rows"):
        lb.build(rows + [rows[0]], draws=50)
    changed = [dict(r, config=dict(r["config"], terms=dict(r["config"]["terms"], fss_sizes=[1]))) if i == 0 else r
               for i, r in enumerate(rows)]
    with pytest.raises(lb.LeaderboardError, match="term definitions"):
        lb.build(changed, draws=50)


def test_leaderboard_never_pools_synthetic_with_real_rows_or_countries(results):
    rows = _rows(results)
    real = [dict(r, synthetic=False) for r in rows if r["baseline"] == "persistence"]
    us = [dict(r, country="US") for r in rows if r["baseline"] == "persistence"]
    board = lb.build(rows + real + us, draws=50)
    titles = sorted(t["title"] for t in board["tables"])
    assert len(titles) == 3 and sum(t.startswith("SYNTHETIC") for t in titles) == 2
    assert any(t.startswith("KR") for t in titles)


def test_leaderboard_refuses_old_rows_and_empty_folders(results, tmp_path):
    with (results / "persistence.csv").open() as handle:
        row = next(csv.DictReader(handle))
    old = {k: v for k, v in row.items() if k not in harness.TERM_COLUMNS}
    with pytest.raises(lb.LeaderboardError, match="per-window terms"):
        lb.parse_row(old, "old.csv")
    (tmp_path / "empty").mkdir()
    with pytest.raises(lb.LeaderboardError, match="no `firecast-lab run` rows"):
        cli.main(["leaderboard", "--results", str(tmp_path / "empty"), "--out", str(tmp_path / "x.md")])
    with pytest.raises(lb.LeaderboardError, match="no `firecast-lab run` rows"):
        cli.main(["leaderboard", "--results", str(tmp_path / "missing"), "--out", str(tmp_path / "x.md")])
    assert not (tmp_path / "x.md").exists()
