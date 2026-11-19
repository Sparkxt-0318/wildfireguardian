"""Tests for crossing.flux. All plate data here are SYNTHETIC: the energy balance is forward-integrated with a known
h / eps / flux and then sampled like a MAX31855 (10 Hz, Gaussian noise, 0.25 C quantisation). Nothing here is a
hardware measurement."""
import ast
import math

import numpy as np
import pytest

from crossing import _repo
from crossing.flux import (C_TO_K, SIGMA, FluxEstimator, LossModel, PlateSpec, RunningDose, derivative,
                           fit_cooldown, tdu)

SPEC = PlateSpec(emissivity=0.90, absorptivity=0.95)
H_TRUE = 12.0          # W/m2/K, synthetic
EPS_TRUE = 0.90
AIR_C = 20.0


def simulate_plate(q_of_t, t_end, t0_c, spec=SPEC, h=H_TRUE, eps=EPS_TRUE, air_c=AIR_C, fs=10.0,
                   noise_c=0.12, seed=0):
    """Forward-integrate rho*cp*d*dT/dt = alpha*q(t) - h(T-Ta) - eps*sigma*(T^4-Ta^4) (RK4, 5 ms steps) and sample
    at fs with MAX31855-like noise + 0.25 C quantisation. q in kW/m2. Returns (t, plate_c_measured, plate_c_true)."""
    m = spec.heat_capacity_j_m2_k
    ta = air_c + C_TO_K

    def f(t, T):
        return (spec.absorptivity * q_of_t(t) * 1000.0 - h * (T - ta) - eps * SIGMA * (T ** 4 - ta ** 4)) / m

    dt = 0.005
    n_sub = int(round(1.0 / fs / dt))
    n = int(round(t_end * fs)) + 1
    T = t0_c + C_TO_K
    t = 0.0
    out_t, out_T = [], []
    for i in range(n):
        out_t.append(t)
        out_T.append(T)
        for _ in range(n_sub):
            k1 = f(t, T); k2 = f(t + dt / 2, T + dt / 2 * k1); k3 = f(t + dt / 2, T + dt / 2 * k2)
            k4 = f(t + dt, T + dt * k3)
            T += dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            t += dt
    t_arr = np.asarray(out_t)
    true_c = np.asarray(out_T) - C_TO_K
    rng = np.random.default_rng(seed)
    meas = np.round((true_c + rng.normal(0.0, noise_c, true_c.size)) / 0.25) * 0.25
    return t_arr, meas, true_c


@pytest.fixture(scope="module")
def cooldown():
    return simulate_plate(lambda t: 0.0, t_end=900.0, t0_c=250.0, seed=1)


@pytest.fixture(scope="module")
def fitted(cooldown):
    t, meas, _ = cooldown
    return fit_cooldown(t, meas, AIR_C, SPEC)


def test_derivative_exact_on_polynomial():
    t = np.linspace(0, 10, 101)
    y = 3.0 + 2.0 * t - 0.1 * t ** 2
    d = derivative(t, y, window_s=1.0, order=2)
    ok = np.isfinite(d)
    assert ok.sum() > 80
    assert np.allclose(d[ok], 2.0 - 0.2 * t[ok], atol=1e-9)


def test_fit_cooldown_recovers_h(fitted):
    lm = fitted
    assert abs(lm.h - H_TRUE) / H_TRUE < 0.15, lm
    assert lm.n > 1000
    assert lm.t_range_c[1] > 200


def test_fit_cooldown_with_free_eps(cooldown):
    t, meas, _ = cooldown
    lm = fit_cooldown(t, meas, AIR_C, SPEC, fit_eps=True)
    # h and eps trade off on a single cool-down; only check the total loss at 150 C is right within 10 %
    true_loss = H_TRUE * 130 + EPS_TRUE * SIGMA * ((150 + C_TO_K) ** 4 - (20 + C_TO_K) ** 4)
    assert abs(float(lm.loss_w_m2(150 + C_TO_K, 20 + C_TO_K)) - true_loss) / true_loss < 0.10


def test_loss_model_json_roundtrip(fitted, tmp_path):
    p = tmp_path / "plate_loss.json"
    fitted.save(p)
    back = LossModel.load(p)
    assert back.h == pytest.approx(fitted.h) and back.eps == pytest.approx(fitted.eps) and back.n == fitted.n


@pytest.mark.parametrize("q_step", [10.0, 3.0])
def test_flux_step_recovered(fitted, q_step):
    t_on = 10.0
    t, meas, _ = simulate_plate(lambda tt: q_step if tt >= t_on else 0.0, t_end=70.0, t0_c=AIR_C, seed=2)
    est = FluxEstimator(SPEC, fitted, window_s=1.0)
    out = [est.update(ti, yi, AIR_C) for ti, yi in zip(t, meas)]
    tt = np.array([s.t for s in out])
    q = np.array([s.q_kw_m2 for s in out])
    valid = np.array([s.valid for s in out])
    assert valid[20:].all()
    before = valid & (tt > 2.0) & (tt < t_on - 1.0)
    after = valid & (tt > t_on + 3.0)                       # settled: > window lag after the step
    assert abs(np.mean(q[before])) < 0.3
    assert abs(np.mean(q[after]) - q_step) / q_step < 0.10, np.mean(q[after])
    assert abs(np.median(q[after]) - q_step) / q_step < 0.10


def test_invalid_on_fault_gap_range_and_missing_air(fitted):
    est = FluxEstimator(SPEC, fitted)
    t = 0.0
    for _ in range(15):
        s = est.update(t, 30.0, AIR_C); t += 0.1
    assert s.valid
    s = est.update(t, None, AIR_C, fault="open")
    assert not s.valid and "fault" in s.reason and math.isnan(s.q_kw_m2)
    # refill after fault
    for _ in range(12):
        t += 0.1; s = est.update(t, 30.0, AIR_C)
    assert s.valid
    t += 0.8
    s = est.update(t, 30.0, AIR_C)
    assert not s.valid and "gap" in s.reason
    t += 0.1
    assert not est.update(t, 30.0, AIR_C).valid           # window must refill after a gap
    assert not est.update(t + 0.1, 1200.0, AIR_C).valid
    assert not est.update(t + 0.2, float("nan"), AIR_C).valid
    est2 = FluxEstimator(SPEC, fitted)
    for i in range(15):
        s = est2.update(i * 0.1, 30.0, None)
    assert not s.valid and "air" in s.reason
    s = est2.update(1.4, 30.0, AIR_C)
    assert not est2.update(1.3, 30.0, AIR_C).valid       # time going backwards


def _reference_tdu():
    """Compile ONLY the tdu function out of research/kcf-heat/kcf_heat/exposure.py (the module itself imports
    closure.py and the repo root, so it is not imported)."""
    path = _repo.KCF_HEAT / "kcf_heat" / "exposure.py"
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "tdu")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
    return ns["tdu"]


def test_tdu_identical_to_reference():
    ref = _reference_tdu()
    rng = np.random.default_rng(3)
    for _ in range(50):
        qs = list(rng.uniform(-1.0, 40.0, rng.integers(1, 200)))
        dt = float(rng.uniform(0.1, 2.0)); q0 = float(rng.choice([0.0, 1.0, 2.5]))
        assert tdu(qs, dt=dt, q0=q0) == ref(qs, dt=dt, q0=q0)
    assert tdu([]) == 0.0
    assert tdu([8.0, 0.5], dt=1.0, q0=1.0) == pytest.approx(8.0 ** (4 / 3))


def test_running_dose_matches_tdu_and_flags_gaps():
    rng = np.random.default_rng(4)
    q = rng.uniform(0, 20, 101)
    rd = RunningDose(q0=1.0)
    for i, qi in enumerate(q):
        rd.add(i * 0.1, qi)
    assert rd.dose_tdu == pytest.approx(tdu(q[1:], dt=0.1, q0=1.0))
    assert rd.complete
    rd.add(10.0 + 1.0, 10.0)                                 # 1 s gap: not integrated
    assert not rd.complete and rd.uncounted_s == pytest.approx(1.0)
    before = rd.dose_tdu
    rd.add(11.1, float("nan"), valid=False)
    assert rd.dose_tdu == before


def test_estimator_valid_with_jittered_10hz_timestamps():
    """Regression: 10 Hz samples with a few ms of timestamp jitter must give valid flux once the window is filled
    (the old pruning rule rejected about half of them as 'filling derivative window')."""
    rng = np.random.default_rng(11)
    est = FluxEstimator(PlateSpec(), window_s=1.0)
    t = 100.0 + np.arange(300) * 0.1 + rng.uniform(-0.004, 0.004, 300)
    out = [est.update(float(ti), 25.0 + 0.05 * (ti - 100.0), 25.0) for ti in t]
    after = [s for s, ti in zip(out, t) if ti > t[0] + 1.2]
    assert after and all(s.valid for s in after), sum(not s.valid for s in after)
