"""Arm 1: the history rule (L1), the adjoint, and the L2 / L3 machinery on a synthetic fire (PROTOCOL 2.7)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import arm1_run  # noqa: E402
import fastmf  # noqa: E402
import tta  # noqa: E402
from cases import Window, check_history, history_for  # noqa: E402

H, W = 22, 24


def synthetic_fire(n=6, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:H, :W]
    t0 = pd.Timestamp("2024-08-01T06:00:00+00:00")
    ws = []
    for i in range(n):
        burned = (yy - 11) ** 2 + (xx - 8 - i) ** 2 <= (2 + i) ** 2
        nxt = (yy - 11) ** 2 + (xx - 9 - i) ** 2 <= (3 + i) ** 2
        row, col = np.nonzero(~burned)
        y = (nxt & ~burned)[row, col].astype(np.int8)
        cut = t0 + pd.Timedelta(hours=24 * i)
        ws.append(Window("SYN", f"c{i}", cut, cut + pd.Timedelta(hours=3.5), 3.5, (H, W), cut.floor("h"), row, col, y))
    return ws, rng


class FakeEnv:
    def __init__(self, seed=1):
        self.rng_seed = seed

    def at(self, event, hour):
        rng = np.random.default_rng([self.rng_seed, int(pd.Timestamp(hour).value // 3_600_000_000_000)])
        e = np.zeros((19, H, W), np.float32)
        e[0] = 20 + 5 * rng.random((H, W)); e[1] = 4 * rng.standard_normal(); e[2] = 4 * rng.standard_normal()
        e[3] = 30 * rng.random((H, W)); e[4] = 100 * rng.random((H, W))
        e[5 + 3] = 1
        return e


@pytest.fixture(scope="module")
def model():
    torch.set_num_threads(1)
    return tta.C651Model()


def test_history_is_strictly_past_L1():
    ws, _ = synthetic_fire()
    for i, w in enumerate(ws):
        hist = history_for(ws, w)
        assert [v.case_id for v in hist] == [f"c{j}" for j in range(i)][-8:]
        assert all(v.endpoint <= w.cutoff for v in hist)
    assert history_for(ws, ws[0]) == []
    with pytest.raises(ValueError):
        check_history([ws[3]], ws[2])            # a later window
    with pytest.raises(ValueError):
        check_history([ws[2]], ws[2])            # the target itself
    overlap = Window("SYN", "x", ws[1].cutoff, ws[2].cutoff + pd.Timedelta(hours=1), 25.0, (H, W),
                     ws[1].cutoff.floor("h"), ws[1].row, ws[1].col, ws[1].y)
    assert overlap not in history_for(ws + [overlap], ws[2])      # ends after the issue time: dropped
    with pytest.raises(ValueError):
        check_history([overlap], ws[2])
    assert len(history_for(ws * 3, ws[-1], max_history=8)) == 8


def test_fast_rollout_and_adjoint_match_torch(model):
    ws, _ = synthetic_fire()
    env = FakeEnv().at("SYN", ws[2].weather_hour)
    hid = model.hidden(env)
    w = ws[2]
    theta = model.zero_theta("P+")
    g = torch.Generator().manual_seed(3)
    for v in theta.values():
        v.data.normal_(0, 0.5, generator=g)
    K = model.kernels(hid, theta)
    ref = tta.rollout(K, w.initial, w.hours)
    loss = tta.window_brier(ref, w)
    loss.backward()
    want = {k: v.grad.clone() for k, v in theta.items()}
    for v in theta.values():
        v.grad = None
    K = model.kernels(hid, theta)
    p, (Kn, P, E, dur) = tta.fast_new_burn(K, w)
    assert np.allclose(p, ref.detach().numpy()[w.row, w.col], rtol=0, atol=1e-13)
    a = np.zeros(w.shape)
    a[w.row, w.col] = 2 * (p - w.y) / len(w.y)
    K.backward(torch.from_numpy(fastmf.backward(Kn, P, E, dur, a)).permute(2, 0, 1)[None])
    for k in theta:
        assert torch.allclose(theta[k].grad, want[k], rtol=1e-9, atol=1e-15)
    assert np.allclose(tta.repo_meanfield(model, env, w.initial, w.hours)[w.row, w.col],
                       tta.predict(model, None, w, lambda v: hid), atol=1e-13)


def test_adaptation_moves_only_the_named_parameters(model, monkeypatch):
    monkeypatch.setattr(tta, "STEPS", 3)
    ws, _ = synthetic_fire()
    env = FakeEnv()
    before = {n: p.clone() for n, p in model.tm.named_parameters()}
    th = tta.adapt(model, "P4", history_for(ws, ws[3]), lambda v: model.hidden(env.at(v.event, v.weather_hour)))
    assert set(th) == {"mix"} and th["mix"].shape == (4,) and float(th["mix"].abs().sum()) > 0
    th = tta.adapt(model, "P+", history_for(ws, ws[3]), lambda v: model.hidden(env.at(v.event, v.weather_hour)))
    assert sum(v.numel() for v in th.values()) == 168
    for n, p in model.tm.named_parameters():
        assert torch.equal(p, before[n])          # the checkpoint itself is never written
    assert tta.adapt(model, "P4", [], None) is None


@pytest.mark.parametrize("which", ["P4", "P+"])
def test_future_scramble_invariance_L2_and_positive_control_L3(model, monkeypatch, which):
    monkeypatch.setattr(tta, "STEPS", 4)
    ws, _ = synthetic_fire()
    env = FakeEnv()
    _, real = arm1_run.run_fire("SYN", ws, model, which, "real", False, env, 7)
    _, scr = arm1_run.run_fire("SYN", ws, model, which, "scramble", False, env, 7)
    assert all(np.array_equal(real[k], scr[k]) for k in real)                 # the method cannot see the future
    _, leak = arm1_run.run_fire("SYN", ws, model, which, "real", True, env, 7)
    _, leak_scr = arm1_run.run_fire("SYN", ws, model, which, "scramble", True, env, 7)
    differ = [k for k in leak if not np.array_equal(leak[k], leak_scr[k])]
    assert len(differ) >= len(ws)                                             # the test does detect a leak
    assert any(not np.array_equal(leak[k], real[k]) for k in real)
