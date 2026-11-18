"""calibrate.py: measured thickness, pair store, conformal recalibration (S-D9 CRC rule), dB/m, ceiling trust.

All pairs here are SYNTHETIC (seeded lognormal errors); nothing here is a field measurement.
"""
import itertools
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from crossing import calibrate as cb
from crossing import depth as dp


# ------------------------------------------------------------------------------------------ measured thickness
def _pulse(t0=10.0, t1=12.0, ramp=0.2, peak=30.0, dt=0.1, total=20.0):
    t = np.arange(0.0, total, dt)
    q = np.zeros_like(t)
    up = (t >= t0 - ramp) & (t < t0 + ramp)
    q[up] = peak * (t[up] - (t0 - ramp)) / (2 * ramp)
    q[(t >= t0 + ramp) & (t <= t1 - ramp)] = peak
    dn = (t > t1 - ramp) & (t <= t1 + ramp)
    q[dn] = peak * ((t1 + ramp) - t[dn]) / (2 * ramp)
    return list(zip(t.tolist(), q.tolist()))


def test_measure_thickness_simple_pulse():
    flux = _pulse()
    gnss = [(t, 5.0) for t in np.arange(0.0, 20.0, 0.2)]
    # old fixed threshold (frac_of_peak = 0): 5 of peak 30 on a 0.4 s ramp, crossing 0.4*5/30 s into each ramp
    r = cb.measure_thickness(flux, gnss, frac_of_peak=0.0)
    assert r.valid, r.reason
    expected_dur = (12.2 - 0.4 * 5 / 30) - (9.8 + 0.4 * 5 / 30)
    assert r.duration_s == pytest.approx(expected_dur, abs=0.02)
    assert r.mean_speed_m_s == pytest.approx(5.0)
    assert r.thickness_m == pytest.approx(5.0 * expected_dur, abs=0.1)
    assert r.threshold_kw_m2 == 5.0
    # default: half maximum (15 kW/m2) crosses the symmetric ramps at their midpoints, t0 = 10 and t1 = 12
    r = cb.measure_thickness(flux, gnss)
    assert r.valid and r.threshold_kw_m2 == pytest.approx(15.0) and r.peak_kw_m2 == pytest.approx(30.0)
    assert r.duration_s == pytest.approx(2.0, abs=0.02) and r.thickness_m == pytest.approx(10.0, abs=0.1)


def _smoothed_top_hat(width_s, kernel_s, peak=40.0, halo_s=0.0, dt=0.02, t0=10.0):
    """Flaming top hat [t0, t0 + width_s] (peak kW/m2) plus an optional 1/r-like radiant halo either side, smoothed
    by a symmetric triangular kernel of full width kernel_s (the centred derivative window is symmetric)."""
    t = np.arange(0.0, 30.0, dt)
    q = np.where((t >= t0) & (t <= t0 + width_s), peak, 0.0)
    if halo_s > 0:
        d = np.where(t < t0, t0 - t, np.where(t > t0 + width_s, t - t0 - width_s, 0.0))
        out = (d > 0) & (d < 6 * halo_s)
        q = np.where(out, peak * halo_s / (2 * d + halo_s), q)
    if kernel_s > 0:
        n = max(1, int(round(kernel_s / dt / 2)))
        k = np.concatenate([np.arange(1, n + 1), np.arange(n - 1, 0, -1)]).astype(float)
        q = np.convolve(q, k / k.sum(), mode="same")
    return list(zip(t.tolist(), q.tolist()))


@pytest.mark.parametrize("width_s,kernel_s", [(0.6, 0.0), (0.6, 0.4), (0.6, 1.0), (0.6, 2.2), (2.0, 1.0)])
def test_half_max_never_shorter_than_the_flaming_zone(width_s, kernel_s):
    """D7 conservativeness: for a top hat smoothed by a symmetric kernel the width at half maximum is >= the top
    hat (equal while the kernel is shorter than it), so the measured thickness never undercuts the flaming depth;
    the halo widens it. A fixed 5 kW/m2 threshold measures far wider (radiant halo, smoothing)."""
    v = 5.0
    gnss = [(t, v) for t in np.arange(0.0, 30.0, 0.2)]
    clean = cb.measure_thickness(_smoothed_top_hat(width_s, kernel_s), gnss)
    assert clean.valid and clean.thickness_m >= v * width_s - 0.06, clean
    if kernel_s < width_s:
        assert clean.thickness_m == pytest.approx(v * width_s, abs=0.15)
    halo = _smoothed_top_hat(width_s, kernel_s, halo_s=0.3)
    new = cb.measure_thickness(halo, gnss)
    old = cb.measure_thickness(halo, gnss, frac_of_peak=0.0)
    assert new.valid and old.valid
    assert v * width_s - 0.06 <= new.thickness_m < old.thickness_m


def test_threshold_floor_and_bad_fraction():
    gnss = [(t, 5.0) for t in np.arange(0.0, 20.0, 0.2)]
    weak = cb.measure_thickness(_pulse(peak=8.0), gnss)            # half max 4 < floor 5: the floor is used
    assert weak.valid and weak.threshold_kw_m2 == 5.0
    assert not cb.measure_thickness(_pulse(), gnss, frac_of_peak=1.0).valid
    assert not cb.measure_thickness(_pulse(), gnss, frac_of_peak=-0.1).valid


def test_measure_thickness_accepts_flux_objects_and_gnss_dicts():
    flux = [SimpleNamespace(t=t, q_kw_m2=q, valid=True) for t, q in _pulse()]
    gnss = [{"t": t, "speed_m_s": 4.0, "fix": 1} for t in np.arange(0.0, 20.0, 0.5)]
    r = cb.measure_thickness(flux, gnss)
    assert r.valid and r.mean_speed_m_s == pytest.approx(4.0)


@pytest.mark.parametrize("case", ["truncated", "no_gnss", "slow", "gap", "invalid_edge", "never"])
def test_measure_thickness_invalid(case):
    flux = _pulse()
    gnss = [(t, 5.0) for t in np.arange(0.0, 20.0, 0.2)]
    if case == "truncated":
        flux = [(t, q) for t, q in flux if t > 11.0]
    elif case == "no_gnss":
        gnss = [(t, v) for t, v in gnss if t < 5.0]
    elif case == "slow":
        gnss = [(t, 0.1) for t, _ in gnss]
    elif case == "gap":
        flux = [(t, q) for t, q in flux if not 10.5 < t < 11.3]
    elif case == "invalid_edge":                     # the sample just after the half-maximum crossing at 12.0
        flux = [SimpleNamespace(t=t, q_kw_m2=q, valid=not (11.95 < t < 12.05)) for t, q in flux]
    elif case == "never":
        flux = [(t, 1.0) for t, _ in flux]
    assert not cb.measure_thickness(flux, gnss).valid


# ----------------------------------------------------------------------------------------------- pair store
_N = itertools.count()


def _pair(fuel="GR2", pred=4.0, meas=4.0, sig=0.3, ceiling=None, loss=None, session=None, key=None):
    """One distinct crossing: a unique dedup key, sessions alternating S0 / S1 (FS-5: calibration needs >= 2)."""
    k = next(_N)
    est = {"byram": pred}
    if ceiling is not None:
        est["radar_ceiling"] = ceiling
    sess = session if session is not None else "S%d" % (k % 2)
    return cb.Pair(fuel=fuel, predicted_m=pred, lo_m=pred / 2, hi_m=pred * 2, sigma_log=sig, measured_m=meas,
                   estimates=est, loss_db=loss, time="2026-11-17T10:00:00Z", lat=37.5, lon=128.9, session=sess,
                   sim=True, key=key if key is not None else cb.make_key(sess, fuel, "pulse", 1000.0 + 10 * k))


def test_pair_store_roundtrip_skips_malformed(tmp_path):
    store = cb.PairStore(tmp_path / "calibration" / "pairs.jsonl")
    store.append(_pair())
    store.append(_pair(meas=5.0, ceiling=6.0))
    with open(store.path, "a") as fh:
        fh.write("{not json\n")
        fh.write(json.dumps({"unexpected": 1}) + "\n")
    got = store.load()
    assert len(got) == 2 and store.skipped == 2
    assert got[1].ceiling_m == 6.0 and got[1].sim is True
    with pytest.raises(ValueError):          # NaN never written
        store.append(_pair(meas=float("nan")))


def test_make_pair_from_depth_result():
    r = dp.combine([dp._lognormal("byram", 3.0, 0.6), dp.radar_ceiling(20.0, 25.0)])
    p = cb.make_pair("GR2", r, measured_m=3.4, loss_db=2.0, session="S")
    assert p.predicted_m == r.depth_m and p.sigma_log == r.sigma_log and p.ceiling_m == pytest.approx(5.0)


# ------------------------------------------------------------------------------------------------- CRC rule
def test_n8_infeasible_at_alpha_010():
    pairs = [_pair(meas=4.0 * math.exp(0.1 * k)) for k in range(8)]
    cal = cb.recalibrate(pairs, "GR2", alpha=0.10)
    assert not cal.calibrated and cal.scale == 1.5
    assert cal.status == "uncalibrated (n = 8, need >= 9)"
    assert not cb.crc_scale([0.1] * 8, 0.10)["feasible"]


def test_n9_feasible_takes_max_score():
    scores = [0.1 * (k + 1) for k in range(9)]
    r = cb.crc_scale(scores, 0.10)
    assert r["feasible"] and r["s_hat"] == pytest.approx(0.9)
    # the rule itself: smallest s with n/(n+1) mean(score > s) + 1/(n+1) <= alpha
    n = 30
    sc = np.linspace(0.05, 3.0, n)
    s = cb.crc_scale(sc, 0.10)["s_hat"]
    ok = lambda x: n / (n + 1) * np.mean(sc > x) + 1 / (n + 1) <= 0.10 + 1e-12
    assert ok(s) and not any(ok(x) for x in sc[sc < s])


def test_minimum_pairs_per_fuel_before_anything_changes():
    """Calibration may only widen; nothing changes for a fuel before its documented minimum number of pairs:
    interval scale n >= 9 (stays the uncalibrated 1.5 until then), dB/m n >= 3, radar ceiling trust n >= 9.
    Pairs of other fuels never count."""
    assert (cb.MIN_CRC_PAIRS, cb.MIN_DB_PAIRS, cb.MIN_CEILING_PAIRS) == (9, 3, 9)
    perfect = lambda fuel, k: _pair(fuel=fuel, meas=4.0, ceiling=10.0, loss=2.0)
    for n in range(0, 9):
        cal = cb.recalibrate([perfect("GR2", k) for k in range(n)] + [perfect("GR1", k) for k in range(20)], "GR2")
        assert cal.scale == 1.5 and not cal.calibrated and not cal.trust_radar_ceiling, n
        assert (cal.db_per_m is None) == (n < 3), n
    cal = cb.recalibrate([perfect("GR2", k) for k in range(9)], "GR2")
    assert cal.calibrated and cal.scale >= 1.0 and cal.trust_radar_ceiling


def test_scale_never_below_one():
    pairs = [_pair(meas=4.0 * math.exp(0.001 * k)) for k in range(30)]     # far better than stated
    cal = cb.recalibrate(pairs, "GR2")
    assert cal.calibrated and cal.s_hat < 1.0 and cal.scale == 1.0


def test_calibrated_interval_covers_about_90_percent_of_fresh_pairs():
    """SYNTHETIC: true log error ~ N(0, (1.8*sigma)^2) while the predictor states sigma."""
    rng = np.random.default_rng(20261117)
    sigma = 0.3

    def draw(n):
        pred = np.exp(rng.normal(np.log(5.0), 0.5, n))
        meas = pred * np.exp(rng.normal(0.0, 1.8 * sigma, n))
        return [_pair(pred=float(p), meas=float(m), sig=sigma) for p, m in zip(pred, meas)]

    cal = cb.recalibrate(draw(200), "GR2", alpha=0.10)
    assert cal.calibrated and cal.n_pairs == 200
    assert cal.scale == pytest.approx(1.8, rel=0.25)
    fresh = draw(4000)
    covered = 0
    for p in fresh:
        r = dp.combine([dp._lognormal("byram", p.predicted_m, sigma)], cal, enabled=["byram"])
        covered += r.lo_m <= p.measured_m <= r.hi_m
    cov = covered / len(fresh)
    assert 0.85 <= cov <= 0.97, cov


def test_other_fuels_and_unusable_pairs_ignored():
    pairs = [_pair() for _ in range(9)] + [_pair(fuel="SH6", meas=50.0)] + [_pair(meas=-1.0)]
    cal = cb.recalibrate(pairs, "GR2")
    assert cal.n_pairs == 9 and cal.n_skipped == 1 and cal.calibrated
    allc = cb.calibrate_all(pairs)
    assert set(allc) == {"GR2", "SH6"} and not allc["SH6"].calibrated


# --------------------------------------------------------------------------------------- dB/m, ceiling trust
def test_db_per_m_needs_three():
    two = [_pair(meas=2.0, loss=4.0), _pair(meas=4.0, loss=4.0)]
    assert cb.recalibrate(two, "GR2").db_per_m is None
    three = two + [_pair(meas=1.0, loss=3.0), _pair(meas=3.0, loss=0.0)]
    cal = cb.recalibrate(three, "GR2")
    # PHYS-4: 90th percentile of 2, 1, 3 (an upper quantile: a low dB/m is anti-conservative for the dose)
    assert cal.n_db == 3 and cal.db_per_m == pytest.approx(float(np.percentile([2.0, 1.0, 3.0], 90)))
    assert cal.db_per_m > float(np.median([2.0, 1.0, 3.0]))


def test_trust_radar_ceiling_rule():
    ok9 = [_pair(meas=4.0, ceiling=5.0) for _ in range(9)]
    assert cb.recalibrate(ok9, "GR2").trust_radar_ceiling
    assert not cb.recalibrate(ok9[:8], "GR2").trust_radar_ceiling
    one_over = ok9 + [_pair(meas=6.0, ceiling=5.0)]
    assert not cb.recalibrate(one_over, "GR2").trust_radar_ceiling
    missing = ok9 + [_pair(meas=4.0)]
    assert not cb.recalibrate(missing, "GR2").trust_radar_ceiling


# ------------------------------------------------------------------------------- FS-5: independent crossings
def test_repeated_pair_counts_once_and_one_session_never_calibrates():
    """FS-5 (probe p2): one crossing (pred 3.0, meas 3.2, ceiling 4.0) stored 9 times (a replay looped 9 times or
    9 'mark crossing' presses) must not calibrate: duplicates collapse to one pair."""
    one = [_pair(pred=3.0, meas=3.2, ceiling=4.0, loss=3.0, session="S", key="S|GR2|pulse|1234") for _ in range(9)]
    cal = cb.recalibrate(one, "GR2")
    assert cal.n_pairs == 1 and cal.n_duplicates == 8
    assert not cal.calibrated and cal.scale == 1.5 and not cal.trust_radar_ceiling and cal.db_per_m is None
    # legacy rows without a key: one per (session, measured, predicted)
    legacy = [cb.Pair(fuel="GR2", predicted_m=3.0, lo_m=1.0, hi_m=9.0, sigma_log=0.3, measured_m=3.2,
                      estimates={"radar_ceiling": 4.0}, loss_db=3.0, session="S") for _ in range(9)]
    assert cb.recalibrate(legacy, "GR2").n_pairs == 1
    # nine DISTINCT crossings but all from one session: still nothing takes effect (needs >= 2 sessions)
    same_session = [_pair(meas=4.0, ceiling=10.0, loss=2.0, session="S") for _ in range(12)]
    cal = cb.recalibrate(same_session, "GR2")
    assert cal.n_pairs == 12 and cal.n_sessions == 1
    assert not cal.calibrated and not cal.trust_radar_ceiling and cal.db_per_m is None
    assert "need >= 2" in cal.status
    two = same_session + [_pair(meas=4.0, ceiling=10.0, loss=2.0, session="T")]
    cal = cb.recalibrate(two, "GR2")
    assert cal.calibrated and cal.trust_radar_ceiling and cal.db_per_m is not None


def test_is_duplicate_same_key_pulse_or_prediction():
    a = _pair(session="S", key="S|GR2|pulse|100")
    a.t_start_pi, a.t_end_pi, a.prediction_rx = 95.0, 100.2, 50.0
    b = _pair(session="S", key="S|GR2|pulse|100")
    assert cb.is_duplicate(b, [a])
    c = _pair(session="S", key="S|GR2|pulse|101")
    c.t_start_pi, c.t_end_pi = 99.0, 100.9                   # overlapping pulse window
    assert cb.is_duplicate(c, [a])
    d = _pair(session="S", key="S|GR2|prediction|50")
    d.prediction_rx = 50.0
    assert cb.is_duplicate(d, [a])
    e = _pair(session="T", key="T|GR2|pulse|100")
    e.t_start_pi, e.t_end_pi = 95.0, 100.2
    assert cb.is_duplicate(e, [a]) is None                  # other session: a different crossing


def test_old_pair_rows_still_load(tmp_path):
    store = cb.PairStore(tmp_path / "p.jsonl")
    store.path.write_text(json.dumps({"fuel": "GR2", "predicted_m": 3.0, "lo_m": 1.0, "hi_m": 9.0, "sigma_log": 0.3,
                                      "measured_m": 3.2, "session": "S"}) + "\n")
    got = store.load()
    assert len(got) == 1 and got[0].key is None and got[0].flicker_extent_agrees is None


# ------------------------------------------------------------------------------------ R6: estimator d reported
def test_make_pair_records_flicker_extent_agreement():
    d_ok = dp._lognormal("flicker_extent", 3.0, 0.8, kind="experimental")
    r = dp.combine([dp._lognormal("byram", 3.0, 0.6), d_ok])
    p_in = cb.make_pair("GR2", r, measured_m=3.4, session="S")
    assert p_in.est_flicker_extent_valid is True and p_in.flicker_extent_agrees is True
    assert p_in.est_flicker_extent_lo_m < 3.4 < p_in.est_flicker_extent_hi_m
    p_out = cb.make_pair("GR2", r, measured_m=50.0, session="S")
    assert p_out.flicker_extent_agrees is False
    r_bad = dp.combine([dp._lognormal("byram", 3.0, 0.6), dp.flicker_extent([], None)])
    p_bad = cb.make_pair("GR2", r_bad, measured_m=3.5, session="S")
    assert p_bad.est_flicker_extent_valid is False and p_bad.flicker_extent_agrees is None
    assert p_bad.est_flicker_extent_reason
    cal = cb.recalibrate([p_in, p_out, p_bad], "GR2")
    assert (cal.n_d_valid, cal.n_d_agree, cal.n_d_disagree) == (2, 1, 1) and "experimental" in cal.d_note
    assert cal.scale == 1.5                                   # never feeds calibration
