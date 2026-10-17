"""Synthetic flows (divergence, circulation sign and size, shear) and ember particle dynamics."""
import math

import numpy as np
import pytest

from wfglink.synth import flows
from wfglink.synth import particles as P
from wfglink.synth.flows import LambOseen, RandomModes, Rankine, Shear, Sum, Uniform

RNG = np.random.default_rng(12)


def _points(n=400, lo=-300.0, hi=1500.0):
    return RNG.uniform(lo, hi, n), RNG.uniform(lo, hi, n)


ALL_FLOWS = {
    "uniform": Uniform(120.0, -35.0),
    "shear": Shear(100.0, -0.3, 360.0, 12.0),
    "rankine": Rankine(640.0, 360.0, 9.0e4, 110.0, (50.0, 5.0)),
    "lamb_oseen": LambOseen(600.0, 300.0, -7.0e4, 90.0, (0.0, 20.0)),
    "random_modes": RandomModes(n_modes=20, wavelength_px=(120.0, 700.0), rms_speed=55.0, period_s=(0.8, 3.0),
                                advection=(150.0, 0.0), seed=4),
    "sum": Sum(Uniform(150.0, 0.0), RandomModes(n_modes=8, rms_speed=30.0, seed=9),
               LambOseen(300.0, 200.0, 4.0e4, 60.0)),
}


@pytest.mark.parametrize("name", list(ALL_FLOWS))
def test_every_field_is_divergence_free(name):
    f = ALL_FLOWS[name]
    x, y = _points()
    if isinstance(f, Rankine):  # finite differences must not straddle the core edge
        keep = np.abs(np.hypot(x - f.cx, y - f.cy) - f.core_radius) > 0.5
        x, y = x[keep], y[keep]
    for t in (0.0, 1.7):
        div = flows.divergence(f, x, y, t, h=1e-3)
        u, v = f.velocity(x, y, t)
        assert np.max(np.abs(div)) < 1e-5 * max(1.0, float(np.max(np.hypot(u, v))) / 100.0)


def test_divergence_helper_detects_a_source():
    class Source(flows.Flow):
        def velocity(self, x, y, t=0.0):
            x, y, _ = flows._bcast(x, y, t)
            return 0.5 * x, 0.25 * y

    div = flows.divergence(Source(), np.array([10.0, 200.0]), np.array([5.0, 50.0]))
    assert np.allclose(div, 0.75)


def test_positive_circulation_turns_clockwise_on_screen():
    f = Rankine(100.0, 100.0, 5.0e4, 20.0)
    r = 50.0
    # Right of centre moves down (+y), below moves left (-x), left moves up, above moves right.
    u, v = f.velocity(np.array([100 + r, 100.0, 100 - r, 100.0]), np.array([100.0, 100 + r, 100.0, 100 - r]))
    assert v[0] > 0 and abs(u[0]) < 1e-12
    assert u[1] < 0 and abs(v[1]) < 1e-12
    assert v[2] < 0
    assert u[3] > 0
    # The z component of the image-axes cross product r x v is positive (from +x toward +y).
    assert r * v[0] > 0


@pytest.mark.parametrize("cls", [Rankine, LambOseen])
@pytest.mark.parametrize("gamma", [6.0e4, -2.5e4])
def test_circulation_line_integral(cls, gamma):
    rc = 40.0
    f = cls(300.0, 200.0, gamma, rc, (30.0, -10.0))
    for r in (0.5 * rc, rc, 2.0 * rc, 6.0 * rc):
        got = flows.circulation(f, 300.0, 200.0, r)
        if cls is Rankine:
            want = gamma * min(r / rc, 1.0) ** 2
        else:
            want = gamma * (1 - math.exp(-(r / rc) ** 2))
        assert got == pytest.approx(want, rel=1e-9, abs=1e-6 * abs(gamma))
    # Far outside the core the line integral is the full circulation.
    assert flows.circulation(f, 300.0, 200.0, 20 * rc) == pytest.approx(gamma, rel=1e-9 if cls is Rankine else 1e-6)


def test_uniform_and_shear_circulation():
    assert flows.circulation(Uniform(80.0, 30.0), 10.0, 10.0, 25.0) == pytest.approx(0.0, abs=1e-8)
    s = Shear(100.0, -0.4, 50.0, 3.0)
    # Vorticity dv/dx - du/dy = -dudy, so circulation = -dudy pi r^2 in the image-axes sense.
    assert flows.circulation(s, 0.0, 0.0, 30.0) == pytest.approx(0.4 * math.pi * 900.0, rel=1e-9)


def test_shear_gradient():
    s = Shear(u0=150.0, dudy=-0.25, y_ref=360.0, v=7.0)
    y = np.linspace(0, 720, 13)
    u, v = s.velocity(np.full(y.size, 33.0), y)
    assert np.allclose(np.diff(u) / np.diff(y), -0.25)
    assert u[6] == pytest.approx(150.0)
    assert np.allclose(v, 7.0)
    f = flows.from_config({"type": "shear", "u0": 150.0, "dudy": -0.25, "y_ref_frac": 0.5}, (1280, 720))
    assert f.velocity(0.0, 0.0)[0] == pytest.approx(240.0)
    assert f.velocity(0.0, 720.0)[0] == pytest.approx(60.0)


def test_vortex_profiles_and_config():
    f = flows.from_config({"type": "rankine", "center_frac": [0.5, 0.5], "core_radius": 120.0,
                           "core_speed": 150.0, "background": [100.0, 0.0]}, (1280, 720))
    assert (f.cx, f.cy) == (640.0, 360.0)
    assert f.circulation == pytest.approx(2 * math.pi * 120.0 * 150.0)
    assert f.tangential_speed(120.0) == pytest.approx(150.0)
    assert f.tangential_speed(60.0) == pytest.approx(75.0)          # solid body inside
    assert f.tangential_speed(240.0) == pytest.approx(75.0)         # 1/r outside
    u, v = f.velocity(640.0, 360.0 - 120.0)
    assert u == pytest.approx(250.0) and v == pytest.approx(0.0)
    lo = flows.from_config({"type": "lamb_oseen", "cx": 0.0, "cy": 0.0, "core_radius": 50.0, "core_speed": 80.0})
    assert lo.tangential_speed(50.0) == pytest.approx(80.0)
    assert lo.tangential_speed(1e-9) == pytest.approx(0.0, abs=1e-6)
    u0, v0 = lo.velocity(0.0, 0.0)
    assert u0 == 0.0 and v0 == 0.0 and np.isfinite(u0)
    with pytest.raises(ValueError):
        flows.from_config({"type": "rankine", "core_radius": 10.0})
    with pytest.raises(ValueError):
        flows.from_config({"type": "nonsense"})


def test_random_modes_rms_seed_and_time():
    f = RandomModes(n_modes=24, wavelength_px=(100.0, 600.0), rms_speed=50.0, period_s=(1.0, 3.0), seed=3)
    x, y = RNG.uniform(0, 6000, 20000), RNG.uniform(0, 6000, 20000)
    t = RNG.uniform(0, 50, 20000)
    u, v = f.velocity(x, y, t)
    assert math.sqrt(np.mean(u ** 2 + v ** 2)) == pytest.approx(50.0, rel=0.08)
    same = RandomModes(n_modes=24, wavelength_px=(100.0, 600.0), rms_speed=50.0, period_s=(1.0, 3.0), seed=3)
    other = RandomModes(n_modes=24, wavelength_px=(100.0, 600.0), rms_speed=50.0, period_s=(1.0, 3.0), seed=4)
    assert np.array_equal(same.velocity(x[:50], y[:50], t[:50])[0], u[:50])
    assert not np.allclose(other.velocity(x[:50], y[:50], t[:50])[0], u[:50])
    a = f.velocity(x[:50], y[:50], 0.0)[0]
    b = f.velocity(x[:50], y[:50], 1.0)[0]
    assert np.max(np.abs(a - b)) > 5.0
    cfg = {"type": "sum", "flows": [{"type": "uniform", "u": 150.0}, {"type": "random_modes", "rms_speed": 20.0}]}
    s1 = flows.from_config(cfg, (640, 360), seed=1)
    s2 = flows.from_config(cfg, (640, 360), seed=2)
    assert not np.allclose(s1.velocity(x[:20], y[:20])[0], s2.velocity(x[:20], y[:20])[0])


def test_flow_broadcasting():
    f = ALL_FLOWS["sum"]
    u, v = f.velocity(np.zeros((3, 1)), np.zeros((1, 4)), 0.5)
    assert u.shape == (3, 4) and v.shape == (3, 4)
    u, v = Uniform(1.0, 2.0).velocity(5.0, 6.0)
    assert u.shape == () and float(u) == 1.0


# Particles -------------------------------------------------------------------------------
def _integrate_one(flow, x0, y0, vt_px, t_end=3.0, h=1e-3, vx0=None, vy0=None, g_px=392.4):
    n = len(x0)
    vx0 = np.zeros(n) if vx0 is None else vx0
    vy0 = np.zeros(n) if vy0 is None else vy0
    steps = int(round(t_end / h))
    st = P.integrate(flow, x0=np.asarray(x0, float), y0=np.asarray(y0, float), vx0=vx0, vy0=vy0,
                     vt_px=np.asarray(vt_px, float), k_birth=np.zeros(n, np.int64),
                     k_death=np.full(n, steps, np.int64), t0=0.0, h=h, n_steps=steps, g_px=g_px)
    return st, steps


def _system(flow, x0, y0, vt_px, t_end=3.0, h=2e-3, g_px=392.4):
    st, steps = _integrate_one(flow, x0, y0, vt_px, t_end, h, g_px=g_px)
    n = len(x0)
    return P.EmberSystem(t0=0.0, h=h, k_birth=np.zeros(n, np.int64), n_states=st["n_states"], offset=st["offset"],
                         X=st["X"], Y=st["Y"], VX=st["VX"], VY=st["VY"], vt_px=np.asarray(vt_px, float),
                         pid=np.arange(n), kind=np.full(n, "ember"), t_birth=np.zeros(n),
                         t_death=st["k_death"] * h, flux=np.ones(n), sigma=np.ones(n), color=np.ones((n, 3)))


def test_tracer_follows_uniform_flow_exactly():
    f = Uniform(150.0, -40.0)
    sysm = _system(f, [10.0, 300.0], [400.0, 20.0], [np.nan, np.nan], t_end=2.0)
    t = RNG.uniform(0, 2.0, 200)
    for i, (xb, yb) in enumerate([(10.0, 400.0), (300.0, 20.0)]):
        x, y, vx, vy = sysm.state(np.full(t.size, i), t)
        assert np.allclose(x, xb + 150.0 * t, atol=1e-9)
        assert np.allclose(y, yb - 40.0 * t, atol=1e-9)
        assert np.allclose(vx, 150.0, atol=1e-9) and np.allclose(vy, -40.0, atol=1e-9)


def test_tracer_follows_solid_body_rotation():
    f = Rankine(0.0, 0.0, 2 * math.pi * 100.0 * 150.0, 100.0)   # omega = 1.5 rad/s inside
    om = 1.5
    sysm = _system(f, [60.0], [0.0], [np.nan], t_end=3.0, h=2e-3)
    t = np.linspace(0, 3.0, 301)
    x, y, vx, vy = sysm.state(np.zeros(t.size, np.int64), t)
    assert np.allclose(x, 60.0 * np.cos(om * t), atol=1e-6)
    assert np.allclose(y, 60.0 * np.sin(om * t), atol=1e-6)
    u, v = f.velocity(x, y)
    assert np.allclose(vx, u, atol=1e-3) and np.allclose(vy, v, atol=1e-3)
    # Grid states carry exactly the air velocity at the grid positions.
    _, gx, gy, gvx, gvy = sysm.grid_states(0)
    gu, gv = f.velocity(gx, gy)
    assert np.allclose(gvx, gu, atol=1e-12) and np.allclose(gvy, gv, atol=1e-12)


def test_terminal_velocity_in_still_air_and_wind():
    vt_px, g_px = 100.0, 9.81 * 40.0
    st, _ = _integrate_one(Uniform(0.0, 0.0), [0.0], [0.0], [vt_px], t_end=3.0, h=2e-3, g_px=g_px)
    # Quadratic drag from rest: v(t) = Vt tanh(g t / Vt).
    k = np.arange(st["n_states"][0])
    t = k * 2e-3
    assert np.allclose(st["VY"], vt_px * np.tanh(g_px * t / vt_px), rtol=1e-6, atol=1e-6)
    assert st["VY"][-1] == pytest.approx(vt_px, rel=1e-6)
    assert np.allclose(st["VX"], 0.0)
    # In a uniform wind the ember drifts with the wind and settles at Vt relative to the air.
    st, _ = _integrate_one(Uniform(150.0, 0.0), [0.0], [0.0], [vt_px], t_end=3.0, h=2e-3, g_px=g_px,
                           vx0=np.array([150.0]), vy0=np.array([0.0]))
    assert st["VX"][-1] == pytest.approx(150.0, abs=1e-6)
    assert st["VY"][-1] == pytest.approx(vt_px, rel=1e-6)


def test_ember_lags_a_gust():
    # Heavier embers (larger Vt) relax to a new air speed more slowly: tau = Vt / g.
    g_px = 9.81 * 40.0
    st, _ = _integrate_one(Uniform(200.0, 0.0), [0.0, 0.0], [0.0, 0.0], [40.0, 320.0], t_end=0.2, h=1e-3,
                           g_px=g_px)
    n = st["n_states"]
    vx_light = st["VX"][st["offset"][0] + n[0] - 1]
    vx_heavy = st["VX"][st["offset"][1] + n[1] - 1]
    assert 0 < vx_heavy < vx_light < 200.0


def test_cox_rate_mean_and_dispersion():
    h, T = 0.005, 3000.0
    n = int(T / h)
    for s, lo, hi in ((0.0, 0.8, 1.2), (0.6, 2.0, 1e9)):
        kb, g = P.cox_birth_steps(20.0, s, 1.0, n, h, np.random.default_rng(5))
        assert kb.size / T == pytest.approx(20.0, rel=0.05)
        counts = np.bincount((kb * h).astype(int), minlength=int(T))
        dispersion = counts.var() / counts.mean()
        assert lo < dispersion < hi
    g = P.ou_process(400000, 0.01, 0.5, np.random.default_rng(1))
    assert g.mean() == pytest.approx(0.0, abs=0.05)
    assert g.var() == pytest.approx(1.0, rel=0.05)
    lag = 50   # 0.5 s = tau
    assert np.corrcoef(g[:-lag], g[lag:])[0, 1] == pytest.approx(math.exp(-1.0), abs=0.05)


def test_upwind_spawn_edges():
    rng = np.random.default_rng(0)
    n = 20000
    spawn = {"mode": "upwind", "margin_px": 8}
    x, y = P.spawn_positions(spawn, n, rng, (640, 360), np.tile([100.0, 0.0], (n, 1)))
    assert np.all(x == -8.0) and y.min() >= 0 and y.max() <= 359
    x, y = P.spawn_positions(spawn, n, rng, (640, 360), np.tile([-50.0, -30.0], (n, 1)))
    right = x == 639 + 8.0
    bottom = y == 359 + 8.0
    assert np.all(right | bottom)
    # Edge weights |dx| H and |dy| W: 50 * 360 versus 30 * 640.
    assert right.mean() == pytest.approx(50 * 360 / (50 * 360 + 30 * 640), abs=0.02)
    x, y = P.spawn_positions(spawn, 100, rng, (640, 360), np.zeros((100, 2)))
    assert x.min() >= 0 and x.max() <= 639 and y.min() >= 0
    x, y = P.spawn_positions({"mode": "rect", "rect_frac": [0.5, 0.5, 0.6, 0.6]}, 100, rng, (640, 360))
    assert x.min() >= 320 and x.max() <= 384 and y.min() >= 180 and y.max() <= 216


def test_glow_color_and_levels():
    c = P.glow_color(np.array([900.0, 1100.0, 1300.0, 2000.0]))
    assert np.allclose(c @ P.LUMA_BGR, 1.0)
    assert np.all(c[:, 2] >= c[:, 1]) and np.all(c[:, 1] >= c[:, 0])
    assert np.all(np.diff(c[:, 1] / c[:, 2]) > 0)            # yellower when hotter
    lv = P.sigma_levels([0.6, 2.0], 4)
    assert lv[0] == pytest.approx(0.6) and lv[-1] == pytest.approx(2.0) and lv.size == 4
    snapped = P.snap_to_levels(np.array([0.61, 1.0, 1.9]), lv)
    assert set(np.round(snapped, 6)) <= set(np.round(lv, 6))


def test_emission_envelope_flicker_and_tumble():
    src = P.LinearSources(pid=[0, 1], kind=["ember", "ember"], t_birth=[0.0, 0.0], t_death=[2.0, 2.0],
                          t_fade_end=[2.0, 2.0], flux=[1.0, 1.0], sigma=[1.0, 1.0], color=np.ones((2, 3)),
                          fade_in_s=[0.5, 0.0], fade_out_s=[0.5, 0.0], flicker_amp=[0.0, 0.5],
                          flicker_hz=[0.0, 5.0], tumble_amp=[0.0, 1.0], tumble_hz=[0.0, 40.0], x0=[0, 0], y0=[0, 0])
    t = np.array([-0.1, 0.25, 1.0, 1.75, 2.1])
    e0 = src.emission(np.zeros(5, np.int64), t)
    assert np.allclose(e0, [0.0, 0.5, 1.0, 0.5, 0.0])
    tt = np.linspace(0.0, 2.0, 200001)
    e1 = src.emission(np.ones(tt.size, np.int64), tt)
    assert e1.min() >= 0.0 and e1.mean() == pytest.approx(1.0, abs=0.01)
    assert e1.min() < 0.01                                   # tumbling: dark gaps


def test_simulate_density_tracers_and_determinism():
    cfg = {"px_per_m": 40.0, "embers": {"density": {"on_screen": 40, "pilot_particles": 800},
                                        "gust": {"strength": 0.0}, "spawn": {"mode": "upwind"},
                                        "vt_m_s": None, "lifetime_s": 30.0, "sigma_px": [0.6, 2.0]},
           "particles": {"warmup_max_s": 5.0}}
    f = Uniform(100.0, 0.0)
    counts = []
    for seed in range(3):
        sysm = P.simulate(cfg, f, frame_size=(320, 240), fps=30.0, duration_s=6.0, seed=seed)
        assert np.all(np.isnan(sysm.vt_px))
        tt = np.arange(0.0, 6.0, 0.1)
        n_in = []
        for t in tt:
            idx = sysm.alive_in(t - 1e-9, t + 1e-9)
            x, y = sysm.position(idx, np.full(idx.size, t))
            n_in.append(np.sum((x >= 0) & (x <= 319) & (y >= 0) & (y <= 239)))
        counts.append(np.mean(n_in))
        # Tracers move exactly with the air.
        i = int(np.argmax(sysm.t_death - sysm.t_birth))
        tq = np.linspace(sysm.t_birth[i], sysm.t_death[i], 50)
        _, _, vx, vy = sysm.state(np.full(50, i), tq)
        assert np.allclose(vx, 100.0) and np.allclose(vy, 0.0)
    assert np.mean(counts) == pytest.approx(40.0, rel=0.15)
    a = P.simulate(cfg, f, frame_size=(320, 240), fps=30.0, duration_s=2.0, seed=7)
    b = P.simulate(cfg, f, frame_size=(320, 240), fps=30.0, duration_s=2.0, seed=7)
    assert np.array_equal(a.X, b.X) and np.array_equal(a.t_birth, b.t_birth) and np.array_equal(a.flux, b.flux)


def test_simulate_step_limits():
    cfg = {"px_per_m": 40.0, "embers": {"density": {"rate_hz": 5.0}, "vt_m_s": [1.0, 8.0], "lifetime_s": 1.0},
           "sparks": {"enabled": True, "density": {"rate_hz": 5.0}, "vt_m_s": {"range": [2.0, 4.0]},
                      "eject_speed_px_s": [200.0, 600.0], "lifetime_s": 0.3},
           "render": {"n_sub_min": 8}, "particles": {"warmup_s": 0.5}}
    sysm = P.simulate(cfg, Uniform(50.0, 0.0), frame_size=(320, 240), fps=30.0, duration_s=1.0, seed=1)
    h = sysm.info["step_s"]
    assert h <= 1.0 / 9.81 / 4 + 1e-12          # a quarter of the shortest relaxation time
    assert h <= 1.0 / (30.0 * 8) + 1e-12         # frame interval / render samples
    ej_ratio = 600.0 / (2.0 * 40.0)
    assert h <= 2.0 / 9.81 / (4 * ej_ratio) + 1e-12
    kinds = set(sysm.kind.tolist())
    assert kinds == {"ember", "spark"}
    sp = sysm.kind == "spark"
    # Sparks start with the ejection kick on top of the air velocity.
    i = int(np.nonzero(sp)[0][0])
    _, _, vx, vy = sysm.state(np.array([i]), np.array([sysm.t_birth[i]]))
    assert math.hypot(vx[0] - 50.0, vy[0]) >= 199.0
