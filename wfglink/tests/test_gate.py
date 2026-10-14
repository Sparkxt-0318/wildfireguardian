"""Gate crossings with hysteresis, counts, rates, flux units and their intervals."""
import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.measure.gate import (Gate, GateCounter, block_bootstrap_rate, count_crossings,
                                  garwood_interval, particle_number_flux)
from wfglink.track.tracker import Track

DT = 1.0 / 30.0


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def horizontal_gate(h=2.0):
    # p1 -> p2 to the right; the normal (-(y2 - y1), x2 - x1) points down (+y) on screen.
    return Gate((100.0, 200.0), (300.0, 200.0), h, "g1")


def feed(counter, tid, ys, x=200.0, t0=0.0, xs=None):
    events = []
    for i, y in enumerate(ys):
        ev = counter.update_point(tid, t0 + i * DT, x if xs is None else xs[i], y)
        if ev is not None:
            events.append(ev)
    return events


def make_track(tid, xy, t0=0.0, coasted=None, static=False):
    tr = Track(tid, 0, t0)
    for i, (x, y) in enumerate(xy):
        c = bool(coasted[i]) if coasted is not None else False
        tr.records.append((i, t0 + i * DT, np.nan if c else x, np.nan if c else y, x, y,
                           0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, c, -1))
    tr.static = static
    return tr


def test_geometry_and_normal_convention():
    g = horizontal_gate()
    assert g.normal == pytest.approx((0.0, 1.0))
    assert g.length == pytest.approx(200.0)
    assert g.signed_distance(150, 210) == pytest.approx(10.0)
    assert g.signed_distance(150, 190) == pytest.approx(-10.0)
    assert g.along(150, 0) == pytest.approx(0.25)
    # A gate drawn upward (p1 below p2): normal points right.
    v = Gate((50, 300), (50, 100), 1.0)
    assert v.normal == pytest.approx((1.0, 0.0))
    with pytest.raises(ValueError):
        Gate((1, 1), (1, 1), 1.0)
    spec = Gate.from_spec({"name": "mid", "p1": [0, 0], "p2": [10, 0]}, load_config())
    assert spec.name == "mid" and spec.h == load_config()["gate"]["hysteresis_px"]


def test_straight_crossing_counts_once_with_direction_and_time():
    c = GateCounter(horizontal_gate())
    ys = np.arange(150.0, 251.0, 7.0)               # moving down, toward the normal
    ev = feed(c, 1, ys)
    assert len(ev) == 1 and ev[0].direction == +1
    assert c.counts() == {"gross": 1, "net": 1, "positive": 1, "negative": 0}
    # Interpolated crossing time: y = 200 between samples at 199 and 206.
    i = np.flatnonzero(ys > 200)[0]
    assert ev[0].t == pytest.approx((i - 1 + (200 - ys[i - 1]) / 7.0) * DT)
    assert ev[0].s == pytest.approx(0.5) and ev[0].y == pytest.approx(200.0)
    # Moving up crosses against the normal.
    c2 = GateCounter(horizontal_gate())
    ev2 = feed(c2, 2, ys[::-1])
    assert len(ev2) == 1 and ev2[0].direction == -1 and c2.counts()["net"] == -1


def test_jitter_inside_band_never_double_counts():
    g = horizontal_gate(h=2.0)
    rng = np.random.default_rng(0)
    # Approach, cross, then jitter with amplitude below 2h around the line for a long time.
    ys = list(np.linspace(150, 203, 10)) + list(200 + rng.uniform(-3.9, 3.9, 300))
    c = GateCounter(g)
    feed(c, 1, ys)
    assert c.counts()["gross"] == 1
    # Jitter strictly inside the hysteresis band never commits a side, so never counts.
    c2 = GateCounter(g)
    feed(c2, 2, list(200 + rng.uniform(-1.9, 1.9, 300)))
    assert c2.counts()["gross"] == 0
    # Approaching and wobbling within the band, then leaving on the same side: no count.
    c3 = GateCounter(g)
    feed(c3, 3, [180, 190, 198, 201, 199, 201.5, 197, 185, 170])
    assert c3.counts()["gross"] == 0


def test_cross_and_return_counts_once_each_direction():
    c = GateCounter(horizontal_gate())
    ys = list(np.linspace(150, 250, 15)) + list(np.linspace(250, 150, 15))
    ev = feed(c, 1, ys)
    assert [e.direction for e in ev] == [1, -1]
    assert c.counts() == {"gross": 2, "net": 0, "positive": 1, "negative": 1}


def test_crossings_outside_segment_do_not_count():
    c = GateCounter(horizontal_gate())
    feed(c, 1, np.linspace(150, 250, 20), x=50.0)       # passes left of p1
    feed(c, 2, np.linspace(150, 250, 20), x=350.0)      # right of p2
    # Diagonal path whose crossing point lies just outside the segment end.
    xs = np.linspace(280, 320, 20)
    ys = np.linspace(160, 240, 20)                       # crosses y = 200 at x = 300 + eps
    feed(c, 3, ys, xs=xs + 0.5)
    assert c.counts()["gross"] == 0
    feed(c, 4, ys, xs=xs - 0.5)                          # just inside
    assert c.counts()["gross"] == 1


def test_track_input_skips_coasted_and_static_and_is_incremental(cfg):
    g = horizontal_gate()
    ys = np.linspace(150, 250, 12)
    xy = np.column_stack((np.full(12, 200.0), ys))
    tr = make_track(7, xy[:5])
    c = GateCounter(g, cfg)
    assert c.update_track(tr) == []
    for i in range(5, 12):                                # the track grows frame by frame
        tr.records.append((i, i * DT, 200.0, ys[i], 200.0, ys[i], 0.0, 0.0, 0.0, 0.0, 0.0,
                           0.0, 0.0, 0, False, -1))
        c.update_track(tr)
    assert c.counts()["gross"] == 1
    # Offline over the finished track gives the same result.
    off = count_crossings(g, [tr], cfg)
    assert off.counts() == c.counts() and off.events[0].t == pytest.approx(c.events[0].t)
    assert off.duration() == pytest.approx(11 * DT)
    # A crossing made only by coasted predictions is not counted.
    coast = np.zeros(12, bool)
    coast[4:9] = True
    tr2 = make_track(8, xy, coasted=coast)
    tr2.records = tr2.records[:8]
    assert count_crossings(g, [tr2]).counts()["gross"] == 0
    # A static track is excluded and its earlier crossings are withdrawn.
    tr3 = make_track(9, xy)
    c.update_track(tr3)
    assert c.counts()["gross"] == 2
    tr3.static = True
    c.update_track(tr3)
    assert c.counts()["gross"] == 1 and all(e.track_id != 9 for e in c.events)
    assert len(c.events_frame()) == 1


def test_rates_cpc_and_flux_units(cfg):
    g = horizontal_gate()
    c = GateCounter(g, cfg)
    c.observe(0.0)
    tid = 0
    for k in range(20):                                   # one downward crossing per second
        tid += 1
        feed(c, tid, np.linspace(190, 210, 5), t0=k + 0.5 - 2 * DT)
    for k in range(5):                                    # five upward crossings
        tid += 1
        feed(c, tid, np.linspace(210, 190, 5), t0=k + 0.7 - 2 * DT)
    c.observe(20.0)
    assert c.counts() == {"gross": 25, "net": 15, "positive": 20, "negative": 5}
    w = cfg["gate"]["rate_window_s"]
    assert c.rate(20.0) == pytest.approx(10 / w)
    assert c.rate(4.0) == pytest.approx(8 / 4.0)          # only 4 s observed so far
    assert c.rate(20.0, net=True) == pytest.approx(10 / w)
    cpc = c.cumulative_particle_count()
    assert cpc["gross"] == 25 and cpc["net"] == 15
    assert cpc["gross_lo"] < 25 < cpc["gross_hi"] and cpc["net_lo"] < 15 < cpc["net_hi"]
    pnf = c.particle_number_flux()
    assert pnf.value == pytest.approx(25 / (200 / 100) / 20.0) and pnf.unit == "per 100 px per s"
    met = c.particle_number_flux(m_per_px=0.01, z_m=12.0)
    assert met.value == pytest.approx(25 / 2.0 / 20.0) and met.unit == "m^-1 s^-1"
    assert "Z = 12 m" in met.label
    net = c.particle_number_flux(net=True)
    assert net.value == pytest.approx(15 / 2.0 / 20.0) and np.isnan(net.lo)
    ri = c.rate_interval(cfg=cfg)
    assert ri["rate"] == pytest.approx(25 / 20.0) and ri["n"] == 25
    assert ri["lo"] <= min(ri["garwood_lo"], ri["boot_lo"]) and ri["lo"] < 1.25 < ri["hi"]
    rn = c.rate_interval(net=True, cfg=cfg)
    assert rn["rate"] == pytest.approx(15 / 20.0)


@pytest.mark.parametrize("n,lo,hi", [(0, 0.0, 3.689), (1, 0.0253, 5.572), (10, 4.795, 18.390),
                                     (100, 81.364, 121.627)])
def test_garwood_reference_values(n, lo, hi):
    a, b = garwood_interval(n)
    assert a == pytest.approx(lo, abs=1e-3) and b == pytest.approx(hi, abs=1e-3)


def test_garwood_vectorised_and_90_percent():
    lo, hi = garwood_interval(np.array([0, 10]), ci=0.90)
    assert lo[0] == 0.0 and hi[0] == pytest.approx(-np.log(0.05))
    assert lo[1] == pytest.approx(5.426, abs=1e-3) and hi[1] == pytest.approx(16.962, abs=1e-3)


def test_block_bootstrap_rate():
    rng = np.random.default_rng(3)
    times = np.sort(rng.uniform(0, 60, 300))
    r = block_bootstrap_rate(times, np.ones(300), 0.0, 60.0, bin_s=1.0, n_boot=2000, seed=1)
    assert r["rate"] == pytest.approx(5.0) and r["n_bins"] == 60 and r["block_bins"] == 4
    assert r["lo"] < 5.0 < r["hi"]
    # Roughly the Poisson spread for a homogeneous process: sd near sqrt(300) / 60.
    assert 0.6 * np.sqrt(300) / 60 < r["sd"] < 1.5 * np.sqrt(300) / 60
    again = block_bootstrap_rate(times, np.ones(300), 0.0, 60.0, n_boot=2000, seed=1)
    assert again == r                                    # deterministic for a seed
    # Bursty (gusty) emission widens the interval compared with a uniform one.
    bursts = np.concatenate([k * 10 + rng.uniform(0, 1, 50) for k in range(6)])
    rb = block_bootstrap_rate(bursts, np.ones(bursts.size), 0.0, 60.0, block_bins=5,
                              n_boot=2000, seed=1)
    assert rb["sd"] > r["sd"]
    # Partial last bin and no events.
    r0 = block_bootstrap_rate(np.zeros(0), np.zeros(0), 0.0, 10.5, n_boot=100)
    assert r0["rate"] == 0.0 and r0["n_bins"] == 11 and r0["hi"] == 0.0


def test_flux_function_edge_cases():
    f = particle_number_flux(10, 50.0, 4.0)
    assert f.value == pytest.approx(10 / 0.5 / 4.0)
    assert f.lo == pytest.approx(4.795 / 2.0, abs=1e-3)
    assert f.hi == pytest.approx(18.390 / 2.0, abs=1e-3)
    assert np.isnan(particle_number_flux(1, 50.0, 0.0).value)


def _synthetic_crossings(seed=11, n=30, fps=30.0, n_frames=150):
    """Straight particles around a horizontal gate; returns detections per frame and truth."""
    import pandas as pd

    rng = np.random.default_rng(seed)
    gate = Gate((100.0, 200.0), (500.0, 200.0), 2.0, "g1")
    start = rng.integers(0, n_frames - 40, n)
    life = rng.integers(25, 40, n)
    x_c = rng.uniform(40, 560, n)                      # where each path meets y = 200
    sign = rng.choice([-1, 1], n)
    vy = sign * rng.uniform(150, 400, n)
    vx = rng.uniform(-60, 60, n)
    t_c = (start + life * rng.uniform(0.3, 0.7, n)) / fps
    dets = [[] for _ in range(n_frames)]
    rows = []
    for k in range(n):
        for f in range(start[k], min(start[k] + life[k], n_frames)):
            t = f / fps
            x = x_c[k] + vx[k] * (t - t_c[k])
            y = 200.0 + vy[k] * (t - t_c[k])
            dets[f].append((x + rng.normal(0, 0.3), y + rng.normal(0, 0.3)))
        inside = 100.0 <= x_c[k] <= 500.0
        fb = int(np.floor(t_c[k] * fps))
        if inside:
            rows.append({"gate": "g1", "particle_id": k, "t": t_c[k], "frame_before": fb,
                         "frame_after": fb + 1, "direction": np.int8(1 if vy[k] > 0 else -1),
                         "visible_both": True})
    truth_gate = pd.DataFrame(rows).astype({"particle_id": "int64", "frame_before": "int64",
                                            "frame_after": "int64"})
    return gate, [np.array(d).reshape(-1, 2) for d in dets], truth_gate


def test_live_and_offline_counts_match_truth(cfg):
    from wfglink.detect.candidates import Detections
    from wfglink.track.tracker import Tracker

    def make_det(xy):
        z = np.zeros(len(xy))
        return Detections(x=xy[:, 0].copy(), y=xy[:, 1].copy(), area=z + 3, peak=z + 50,
                          flux=z + 100, lam1=z, lam2=z, theta=z, length=z, width=z + 2,
                          sat_frac=z, color=z, flags=np.zeros(len(xy), np.uint8))
    from wfglink.validate.metrics import gate_metrics

    fps = 30.0
    gate, dets, truth_gate = _synthetic_crossings(fps=fps)
    tracker = Tracker(cfg, fps=fps)
    live = GateCounter(gate, cfg)
    for f, xy in enumerate(dets):
        t = f / fps
        tracker.update(make_det(xy), t, f)
        live.observe(t)
        live.update_tracks(tracker.active_tracks())
        live.update_tracks(tracker.pop_finished())
    live.update_tracks(tracker.finish_all())
    offline = count_crossings(gate, tracker.all_tracks(), cfg)
    assert live.counts() == offline.counts()
    assert [e.track_id for e in live.events] == [e.track_id for e in offline.events]
    assert np.allclose([e.t for e in live.events], [e.t for e in offline.events])
    true = truth_gate["direction"].to_numpy()
    assert live.counts()["gross"] == true.size
    assert live.counts()["net"] == int(true.sum())
    est_t = np.sort([e.t for e in live.events])
    assert np.allclose(est_t, np.sort(truth_gate["t"]), atol=0.5 / fps)
    m = gate_metrics(live, truth_gate, t0=0.0, t1=len(dets) / fps, cfg=cfg)
    assert m["cpc_gross"]["rel_err"] == 0.0 and m["cpc_gross"]["in_ci"]
    assert m["cpc_net"]["abs_err"] == 0 and m["pnf"]["rel_err"] == 0.0 and m["pnf"]["in_ci"]
    assert m["pnf"]["estimate"] == pytest.approx(true.size / 4.0 / 5.0)


def test_ember_that_crosses_then_rests_keeps_its_crossing(cfg):
    g = horizontal_gate()
    ys = np.concatenate((np.linspace(150, 250, 12), np.full(40, 250.0)))
    xy = np.column_stack((np.full(ys.size, 200.0), ys))
    tr = make_track(5, xy)
    c = GateCounter(g, cfg)
    c.update_track(tr)
    assert c.counts()["gross"] == 1
    tr.static = True
    tr.static_since = 20 * DT                       # it came to rest after crossing
    tr.records.append((52, 52 * DT, 200.0, 250.0, 200.0, 250.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0, False, -1))
    c.update_track(tr)
    assert c.counts()["gross"] == 1
    # A static light whose slow window covers its jitter crossing loses it.
    light = make_track(6, np.column_stack((np.full(6, 150.0), [195, 197, 203, 204, 196, 203])))
    c.update_track(light)
    assert c.counts()["gross"] == 2
    light.static = True
    light.static_since = 0.0
    c.update_track(light)
    assert c.counts()["gross"] == 1 and c.events[0].track_id == 5


def test_static_track_offline_matches_live(cfg):
    """Offline counting of a finished static track keeps the crossings made before its
    slow window, exactly as live counting does (offline used to drop the whole track)."""
    g = horizontal_gate()
    ys = np.concatenate((np.linspace(150, 250, 12), np.full(40, 250.0)))
    xy = np.column_stack((np.full(ys.size, 200.0), ys))
    tr = make_track(5, xy)
    live = GateCounter(g, cfg)
    for n in range(1, len(tr.records) + 1):             # records appear frame by frame
        grown = make_track(5, xy[:n])
        live.update_track(grown)
    tr.static = True
    tr.static_since = 20 * DT
    live.update_track(tr)
    off = count_crossings(g, [tr], cfg)
    assert live.counts() == off.counts() == {"gross": 1, "net": 1, "positive": 1, "negative": 0}
    assert off.events[0].t == pytest.approx(live.events[0].t)
    # A static light whose slow window starts before its crossing loses it offline too.
    light = make_track(6, np.column_stack((np.full(6, 150.0), [190, 195, 203, 206, 196, 190])))
    light.static, light.static_since = True, 0.0
    assert count_crossings(g, [light], cfg).counts()["gross"] == 0
    # The events returned by update_track are the ones that stay counted.
    c = GateCounter(g, cfg)
    assert [e.track_id for e in c.update_track(tr)] == [5]
    light2 = make_track(7, np.column_stack((np.full(6, 150.0), [190, 195, 203, 206, 196, 190])))
    light2.static, light2.static_since = True, 0.0
    assert c.update_track(light2) == [] and c.counts()["gross"] == 1
    # With exclude_static off the static flag is ignored.
    assert count_crossings(g, [light], cfg, exclude_static=False).counts()["gross"] >= 1


def test_offline_observation_span(cfg):
    """The flux of an offline count uses the processed span when given, not the shorter
    span of the tracks, which inflated rates and fluxes."""
    g = horizontal_gate()
    ys = np.linspace(150, 250, 12)
    tr = make_track(1, np.column_stack((np.full(12, 200.0), ys)), t0=2.0)
    by_tracks = count_crossings(g, [tr], cfg)
    assert by_tracks.duration() == pytest.approx(11 * DT)
    full = count_crossings(g, [tr], cfg, t_span=(0.0, 10.0))
    assert full.duration() == pytest.approx(10.0)
    assert full.counts() == by_tracks.counts()
    assert full.particle_number_flux().value == pytest.approx(1 / 2.0 / 10.0)
    assert full.rate_interval(cfg=cfg)["rate"] == pytest.approx(0.1)


def test_prune_and_forget_keep_totals_exact():
    """Long live runs: pruned events fold into totals; rates over recent windows unchanged."""
    from wfglink.measure.gate import Gate, GateCounter

    g = Gate((50.0, 0.0), (50.0, 100.0), 2.0, "g")
    c = GateCounter(g, {"gate": {"rate_window_s": 10.0}})
    t = 0.0
    for tid in range(1, 201):           # 200 tracks crossing left to right, one per 0.5 s
        for k in range(6):
            c.observe(t)
            c.update_point(tid, t, 40.0 + 4.0 * k, 50.0)
            t += 0.05
        c.forget(tid)
        t += 0.2
    before = c.counts()
    rate_before = c.rate(t)
    folded = c.prune_events(t - 30.0)
    assert folded > 0
    assert c.counts() == before
    assert c.rate(t) == rate_before
    assert len(c._state) == 0
    assert c.particle_number_flux().value > 0
