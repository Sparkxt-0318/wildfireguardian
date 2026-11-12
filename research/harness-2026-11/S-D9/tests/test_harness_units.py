"""Unit tests on invented data for the S-D9 additions: file contract, strata and CRPS."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from sd9bench import load, score
from sd9bench.score import crps_ensemble, stratified


def write(path, **arrays):
    np.savez(path, **arrays)
    return path


def fire_file(tmp_path, name="F1", n=40, k=4, seed=0, **extra):
    rng = np.random.default_rng(seed)
    interval = np.repeat(np.arange(k), n // k)
    y = (rng.random(n) < 0.2).astype(np.int8)
    arrays = dict(interval=interval, y=y, hours=np.array([6.0, 18.0, 30.0, 42.0][:k]),
                  p_model=rng.random(n), p_persistence=np.zeros(n), p_dilation_best=rng.random(n) * 0.5)
    arrays.update(extra)
    return write(tmp_path / f"{name}.npz", **arrays)


# --- file contract ---------------------------------------------------------

def test_load_concatenates_and_maps_hours(tmp_path):
    a = fire_file(tmp_path, "A", seed=1)
    b = fire_file(tmp_path, "B", seed=2)
    e = load([b, a])
    assert e.fire.tolist()[:10] == ["A"] * 10            # sorted by fire
    assert e.hours.tolist()[:10] == [6.0] * 10           # hours indexed by interval
    assert set(e.predictions) == {"model", "persistence", "dilation_best"}


@pytest.mark.parametrize("bad", [
    dict(p_model=np.full(40, 1.5)),                       # out of range
    dict(p_model=np.full(40, np.nan)),                    # non-finite
    dict(y=np.full(40, 2, dtype=np.int8)),                # non-binary
    dict(interval=np.full(40, 9)),                        # index outside hours
    dict(hours=np.array([6.0, -1.0, 30.0, 42.0])),        # nonpositive horizon
    dict(dist_m=np.full(40, -1.0)),                       # negative distance
    dict(area_samples_model=np.ones((3, 5))),             # wrong K
])
def test_contract_violations_raise(tmp_path, bad):
    with pytest.raises(ValueError):
        load([fire_file(tmp_path, **bad)])


def test_mismatched_predictors_raise(tmp_path):
    a = fire_file(tmp_path, "A")
    b = write(tmp_path / "B.npz", interval=np.zeros(4, int), y=np.zeros(4, np.int8), hours=np.array([1.0]),
              p_model=np.zeros(4))
    with pytest.raises(ValueError, match="differ"):
        load([a, b])


def test_partial_optional_arrays_raise(tmp_path):
    a = fire_file(tmp_path, "A", dist_m=np.zeros(40))
    b = fire_file(tmp_path, "B")
    with pytest.raises(ValueError, match="dist_m"):
        load([a, b])


# --- strata ----------------------------------------------------------------

def test_horizon_strata_partition_entries(tmp_path):
    e = load([fire_file(tmp_path, "A", seed=3), fire_file(tmp_path, "B", seed=4)])
    rows = stratified(e, e.hours, (0, 12, 24, 36, 48), "h")
    assert sum(r["entries"] for r in rows) == len(e.y)
    assert [r["intervals"] for r in rows] == [2, 2, 2, 2]  # one interval per fire per bin
    assert all(r["fires"] == 2 for r in rows)
    # Within-stratum Brier equals the direct computation.
    use = e.hours <= 12
    assert rows[0]["models"]["model"]["brier"] == pytest.approx(np.mean((e.predictions["model"][use] - e.y[use]) ** 2))


def test_band_strata_need_dist(tmp_path):
    e = load([fire_file(tmp_path)])
    assert score(e, draws=50)["by_band"] == {"status": "UNAVAILABLE_NO_DIST_M"}
    e = load([fire_file(tmp_path, "G", dist_m=np.linspace(0, 8000, 40))])
    rows = score(e, draws=50)["by_band"]
    assert sum(r["entries"] for r in rows) == 40


def test_base_rate_bss(tmp_path):
    e = load([fire_file(tmp_path)])
    r = score(e, draws=50)
    pbar = e.y.mean()
    b = np.mean((e.predictions["model"] - e.y) ** 2)
    assert r["models"]["model"]["pooled"]["base_rate_bss"] == pytest.approx(1 - b / (pbar * (1 - pbar)))


# --- CRPS ------------------------------------------------------------------

def brute_crps(x, y):
    x = np.asarray(x, float)
    return np.abs(x - y).mean() - 0.5 * np.mean([abs(a - b) for a, b in itertools.product(x, x)])


@pytest.mark.parametrize("x,y", [([3.0], 5.0), ([1, 2, 3, 4], 2.5), ([0, 0, 10], 0.0), ([7, 1, 4, 4, 9], 20.0)])
def test_crps_matches_brute_force(x, y):
    assert crps_ensemble(np.array(x, float), y) == pytest.approx(brute_crps(x, y), abs=1e-12)


def test_crps_point_ensemble_is_absolute_error():
    assert crps_ensemble(np.array([4.0, 4.0, 4.0]), 1.0) == pytest.approx(3.0)


def test_area_crps_scored_only_with_samples(tmp_path):
    samples = np.tile(np.arange(5, dtype=float), (4, 1))
    e = load([fire_file(tmp_path, area_samples_model=samples)])
    out = score(e, draws=50)["area_crps"]
    assert out["model"]["status"] == "SCORED" and out["model"]["intervals"] == 4
    assert out["persistence"]["status"] == "UNAVAILABLE_NO_AREA_SAMPLES"
    observed = np.bincount(e.interval, weights=e.y, minlength=4)
    expected = np.mean([brute_crps(np.arange(5), o) for o in observed])
    assert out["model"]["mean_crps"] == pytest.approx(expected)


def test_mc_correction_declared_only(tmp_path):
    e = load([fire_file(tmp_path)])
    r = score(e, draws=50, mc_trajectories={"model": 1024})
    p = e.predictions["model"]
    pooled = r["models"]["model"]["pooled"]
    assert pooled["brier_mc_variance_corrected"] == pytest.approx(pooled["brier"] - np.mean(p * (1 - p)) / 1023)
    with pytest.raises(ValueError):
        score(e, draws=50, mc_trajectories={"nope": 10})


# --- low-probability bins and cumulative bands ------------------------------

def test_low_probability_bins_partition_below_tenth(tmp_path):
    e = load([fire_file(tmp_path)])
    r = score(e, draws=50)
    for name, p in e.predictions.items():
        rows = r["models"][name]["pooled"]["low_probability_bins"]
        assert sum(x["count"] for x in rows) == int((p < 0.1).sum())
        assert sum(x["positives"] for x in rows) == int(e.y[p < 0.1].sum())


def test_zero_probability_positive_share(tmp_path):
    e = load([fire_file(tmp_path)])
    r = score(e, draws=50)
    assert r["models"]["persistence"]["pooled"]["zero_probability_positive_share"] == 1.0


def test_cumulative_bands_are_nested_and_count_beyond(tmp_path):
    d = np.linspace(0, 10000, 40)
    e = load([fire_file(tmp_path, dist_m=d)])
    r = score(e, draws=50)
    sizes = [r["cumulative_bands"][w]["entries"] for w in ("1000", "2000", "4000", "8000")
             if "entries" in r["cumulative_bands"][w]]
    assert sizes == sorted(sizes)
    assert r["positives_beyond_last_band"] == int(e.y[d > 8000].sum())


# --- arrival RPS (lead-time design) ----------------------------------------

def arrival_file(tmp_path, name="A", **over):
    # Two cutoffs; cutoff 0 has leads at 10, 20, 30 h, and cutoff 1 has one lead at 15 h.
    arrays = dict(
        cutoff=np.array([0, 0, 0, 1]), n_leads=np.array([3, 3, 3, 1]), arrival_bin=np.array([0, 2, 3, 1]),
        lead_hours=np.array([[10.0, 20.0, 30.0], [15.0, np.nan, np.nan]]),
        cdf_model=np.array([[0.5, 0.6, 0.9], [0.1, 0.2, 0.3], [0.0, 0.0, 0.0], [0.4, np.nan, np.nan]]),
        cdf_persistence=np.zeros((4, 3)),
    )
    arrays.update(over)
    np.savez(tmp_path / f"{name}.npz", **arrays)
    return tmp_path / f"{name}.npz"


def test_rps_hand_computed(tmp_path):
    from sd9bench import load_arrival
    from sd9bench.arrival import rps
    e = load_arrival([arrival_file(tmp_path)])
    r = rps(e, "model")
    # bin 0 -> O = 1, 1, 1; bin 2 -> O = 0, 0, 1; bin 3 (none) -> O = 0, 0, 0; single lead, bin 1 (none) -> O = 0
    expected = [0.25 + 0.16 + 0.01, 0.01 + 0.04 + 0.49, 0.0, 0.16]
    assert r.tolist() == pytest.approx(expected)
    assert rps(e, "persistence").tolist() == pytest.approx([3.0, 1.0, 0.0, 0.0])


def test_rps_single_lead_equals_brier(tmp_path):
    from sd9bench import load_arrival
    from sd9bench.arrival import rps
    e = load_arrival([arrival_file(tmp_path)])
    assert rps(e, "model")[3] == pytest.approx((0.4 - 0.0) ** 2)


def test_arrival_score_by_lead_and_paired(tmp_path):
    from sd9bench import load_arrival, score_arrival
    e = load_arrival([arrival_file(tmp_path, "A"), arrival_file(tmp_path, "B")])
    r = score_arrival(e, draws=200, references=("persistence",))
    by = {(x["lower"], x["upper"]): x for x in r["models"]["model"]["by_lead"]}
    assert by[(0.0, 12.0)]["cell_leads"] == 6           # lead 10 h for 3 entries x 2 fires
    assert by[(12.0, 24.0)]["cell_leads"] == 8          # 20 h x 3 plus 15 h x 1, per fire
    assert "model__vs__persistence" in r["paired"]


@pytest.mark.parametrize("over,msg", [
    (dict(cdf_model=np.array([[0.5, 0.4, 0.9], [0.1, 0.2, 0.3], [0, 0, 0], [0.4, np.nan, np.nan]])), "nondecreasing"),
    (dict(arrival_bin=np.array([0, 2, 4, 1])), "arrival_bin"),
    (dict(n_leads=np.array([3, 3, 3, 0])), "n_leads"),
    (dict(lead_hours=np.array([[10.0, 5.0, 30.0], [15.0, np.nan, np.nan]])), "increase"),
])
def test_arrival_contract_violations(tmp_path, over, msg):
    from sd9bench import load_arrival
    with pytest.raises(ValueError, match=msg):
        load_arrival([arrival_file(tmp_path, **over)])


# --- revision 2 additions: equal-fire, 1/1024 floor, domain, scaled band, meta ---

def test_equal_fire_interval_point(tmp_path):
    e = load([fire_file(tmp_path, "A", seed=5), fire_file(tmp_path, "B", seed=6)])
    r = score(e, draws=200)
    eq = r["paired"]["model__vs__persistence"]["equal_fire"]
    per = [np.mean((e.predictions["model"][e.fire == f] - e.y[e.fire == f]) ** 2)
           - np.mean((0 - e.y[e.fire == f]) ** 2) for f in ("A", "B")]
    assert eq["point_difference"] == pytest.approx(np.mean(per))
    lo, hi = eq["percentile_95_interval"]
    assert min(per) - 1e-12 <= lo <= hi <= max(per) + 1e-12


def test_positives_below_mc_floor(tmp_path):
    p = np.full(40, 0.5)
    p[:10] = 1 / 2048
    e = load([fire_file(tmp_path, p_model=p)])
    r = score(e, draws=50)
    assert r["models"]["model"]["pooled"]["positives_below_1_over_1024"] == int(e.y[:10].sum())
    assert r["models"]["persistence"]["pooled"]["positives_below_1_over_1024"] == int(e.y.sum())


def test_domain_stratum(tmp_path):
    dom = np.arange(40) < 20
    e = load([fire_file(tmp_path, in_domain=dom)])
    r = score(e, draws=50)
    if "entries" in r["by_domain"]["inside"]:
        assert r["by_domain"]["inside"]["entries"] == 20
    with pytest.raises(ValueError, match="in_domain"):
        load([fire_file(tmp_path, "X", in_domain=np.zeros(40, int))])


def test_horizon_scaled_band(tmp_path):
    d = np.full(40, 1500.0)  # hours 6, 18, 30, 42 -> widths 1000, 3000, 5000, 7000 m
    e = load([fire_file(tmp_path, dist_m=d)])
    r = score(e, draws=50)["horizon_scaled_band"]
    assert r["entries"] == 30
    assert r["positives_outside"] == int(e.y[e.hours == 6.0].sum())


def test_meta_passthrough_and_validation(tmp_path):
    e = load([fire_file(tmp_path, meta_model=np.array('{"n_traj": 1024}'))])
    assert e.meta == {"model": {"F1": '{"n_traj": 1024}'}}
    with pytest.raises(ValueError, match="JSON"):
        load([fire_file(tmp_path, "Y", meta_model=np.array("not json"))])


# --- scored population flag (A1 §4, revision 22) ---------------------------

def test_population_defaults_to_unspecified(tmp_path):
    e = load([fire_file(tmp_path, "A")])
    assert e.population == "unspecified"
    r = score(e, draws=50)
    assert r["population"] == "unspecified" and "population_note" not in r


def test_hindsight_restricted_flag_is_carried_and_noted(tmp_path):
    files = [fire_file(tmp_path, n, seed=i, population=np.array("hindsight_restricted"))
             for i, n in enumerate(("A", "B"))]
    e = load(files)
    assert e.population == "hindsight_restricted"
    assert e.subset(e.y >= 0).population == "hindsight_restricted"
    r = score(e, draws=50)
    assert r["population"] == "hindsight_restricted"
    assert r["population_note"].startswith("HINDSIGHT-RESTRICTED POPULATION")


def test_declared_population_without_file_value(tmp_path):
    e = load([fire_file(tmp_path, "A")], population="full_rectangle")
    assert e.population == "full_rectangle"


@pytest.mark.parametrize("files_pop,declared", [("full_rectangle", "hindsight_restricted"),
                                                ("hindsight_restricted", "full_rectangle")])
def test_declared_population_must_match_files(tmp_path, files_pop, declared):
    f = fire_file(tmp_path, "A", population=np.array(files_pop))
    with pytest.raises(ValueError, match="contradicts"):
        load([f], population=declared)


def test_population_must_agree_across_files(tmp_path):
    a = fire_file(tmp_path, "A", population=np.array("full_rectangle"))
    b = fire_file(tmp_path, "B", seed=3, population=np.array("hindsight_restricted"))
    with pytest.raises(ValueError, match="population differs"):
        load([a, b])
    c = fire_file(tmp_path, "C", seed=4)  # no population at all
    with pytest.raises(ValueError, match="population differs"):
        load([a, c])


@pytest.mark.parametrize("bad", [np.array("kriged"), np.array(["full_rectangle"]), np.array(1)])
def test_population_value_is_validated(tmp_path, bad):
    with pytest.raises(ValueError, match="population must be"):
        load([fire_file(tmp_path, "A", population=bad)])
    with pytest.raises(ValueError, match="population must be one of"):
        load([fire_file(tmp_path, "B")], population="kriged")
