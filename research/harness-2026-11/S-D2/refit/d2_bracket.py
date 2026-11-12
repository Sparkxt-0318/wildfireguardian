"""d2_bracket_rebuilt fitting procedure (A1 §3.1 item 21): EM over latent arrival times within survey brackets.

It replaces ``survival.fit_mean_field`` in memory (see ``run_d2.py --d2 bracket``) and mirrors it everywhere
except the loss and its E-step:
* same Adam optimiser, learning rate, weight decay, seed, epochs and samples-per-step;
* same interval order and per-epoch subsampling;
* same D4 augmentation (applied consistently to the latent times);
* same biome balance weights and prevalence scaling;
* no validation selection when ``validate_each_epoch=False``, which is the final-stage setting.

Model fact used. In ``StructuredKernelModel`` the per-offset kernels ``K[δ, i]`` (``kernel_rates``) depend on the
environment only, so the hazard is linear in the burned state:

    λ_i(t) = Σ_δ K[δ, i] · 1{τ_(i+δ) <= t}

This is the PyTorch cross-correlation convention of ``meanfield.kernel_source_rate``. Within a window the
environment is fixed (cutoff weather), so K is constant over the interval.

For one window (cells initially burned have τ = 0; cells newly mapped by the endpoint have latent τ in (0, hours];
other scored cells are unburned through ``hours``):

* E-step: ``sweeps`` Gibbs sweeps over the latent cells with K fixed (detached). Each cell's conditional is
  evaluated on a ``step``-hour grid inside its bracket; it combines its own density and its effect on its targets
  (the verified synthetic sampler, here with spatially varying K).
* M-step loss: the negative complete-data log-likelihood

      -[ Σ_(latent i) w_i log(λ_i(τ_i) + eps) - Σ_(scored j) w_j Σ_δ K[δ, j] (min(τ_j, hours) - τ_(j+δ))_+ ],

  normalised by Σ_j w_j and the training prevalence, as ``fit_mean_field`` normalises Brier. eps = 1e-7 is additive.

Fixed E-step protocol (A1 stage-2 amendment, Victor's items a-d):
(a) exactly ``sweeps`` Gibbs sweeps per window visit per epoch; no adaptive or convergence-based count and no
    burn-in beyond these sweeps;
(b) initialisation: on a window's first visit, every latent cell starts at its bracket midpoint (hours / 2). On later
    visits it starts from its last sampled times (warm start), kept in the sample's original frame;
(c) the E-step draws from its own RNG stream, ``np.random.default_rng(np.random.SeedSequence([seed, 0x5D2B]))``,
    separate from the training stream ``np.random.default_rng(seed)``, which controls interval order and D4 draws
    exactly as in fit_mean_field. Changing the E-step therefore never changes the training order;
(d) order per window visit: (1) ONE ``kernel_rates`` pass with the current parameters; (2) ``sweeps`` Gibbs sweeps,
    all using those kernels, detached; (3) the M-step loss on the same kernels (with gradient); (4) the optimiser
    update after each ``samples_per_step`` group. Kernels are therefore recomputed only on the next visit, after an
    M-step update, never between sweeps.

Recorded constraint: the E-step is valid only because the hazard is linear in the burned state, which holds for
kernel-only variants without burnout/residence or spotting (d4_wind). ``fit_bracket`` refuses other variants. Label validity comes from the
perimeter states (A1 §4.1 rule 3); arrival rasters are not used.
"""
from __future__ import annotations

import json
import math
import time

import numpy as np
import torch

EPS = 1e-7


def offsets(D: int) -> np.ndarray:
    k = int(round(math.sqrt(D)))
    r = np.arange(k) - k // 2
    return np.stack(np.meshgrid(r, r, indexing="ij"), -1).reshape(-1, 2)   # row-major δ = (dr, dc)


def source_index(H: int, W: int, offs: np.ndarray) -> np.ndarray:
    """src[δ, i] = flat index of i + δ, or -1 outside the grid."""
    rr, cc = np.divmod(np.arange(H * W), W)
    sr = rr[None, :] + offs[:, 0:1]
    sc = cc[None, :] + offs[:, 1:2]
    ok = (sr >= 0) & (sr < H) & (sc >= 0) & (sc < W)
    return np.where(ok, sr * W + sc, -1)


def complete_loglik(K: torch.Tensor, tau: np.ndarray, latent: np.ndarray, scored: np.ndarray,
                    weight: np.ndarray, hours: float, src: np.ndarray):
    """Weighted complete-data log-likelihood and the weight sum. K: [D, N] (N = H*W), torch, may require grad."""
    N = tau.shape[0]
    ts = np.where(src >= 0, tau[np.clip(src, 0, None)], np.inf)                      # [D, N]
    ev = np.flatnonzero(latent)
    active = torch.as_tensor((ts[:, ev] < tau[ev][None, :]) & np.isfinite(ts[:, ev]), dtype=K.dtype)
    lam = (K[:, ev] * active).sum(0) + EPS
    w = torch.as_tensor(weight, dtype=K.dtype)
    ll_events = (w[ev] * torch.log(lam)).sum()
    sc = np.flatnonzero(scored)
    end = np.minimum(tau[sc], hours)
    expo = np.clip(end[None, :] - ts[:, sc], 0, None)
    expo[~np.isfinite(expo)] = 0.0
    ll_expo = (w[sc] * (K[:, sc] * torch.as_tensor(expo, dtype=K.dtype)).sum(0)).sum()
    return ll_events - ll_expo, float(w[sc].sum())


def gibbs_sweep(K: np.ndarray, tau: np.ndarray, latent_idx: np.ndarray, src: np.ndarray, tgt: np.ndarray,
                scored: np.ndarray, hours: float, step: float, rng) -> np.ndarray:
    """One random-order sweep; K [D, N] numpy (finite, >= 0); tau [N] float (inf = unburned)."""
    x_all = np.arange(step / 2, hours, step)
    for i in rng.permutation(latent_idx):
        x = x_all
        s = src[:, i]
        ok = s >= 0
        ts = tau[s[ok]]
        kk = K[ok, i]
        lam = EPS + (ts[None, :] < x[:, None]) @ kk
        Lam = np.clip(x[:, None] - ts[None, :], 0, None) @ kk
        logf = np.log(lam) - Lam
        t = tgt[:, i]
        for d in np.flatnonzero(t >= 0):
            m = t[d]
            if not scored[m]:
                continue
            kd = K[d, m]
            if kd <= 0:
                continue
            tm = tau[m]
            if np.isfinite(tm) and tm <= hours:
                ms = src[:, m]
                okm = (ms >= 0) & (ms != i)
                rest = EPS + K[okm, m][tau[ms[okm]] < tm].sum()
                logf = logf + np.log(rest + kd * (x < tm)) - kd * np.clip(tm - x, 0, None)
            else:
                logf = logf - kd * np.clip(hours - x, 0, None)
        logf -= logf.max()
        p = np.exp(logf)
        p /= p.sum()
        b = rng.choice(len(x), p=p)
        tau[i] = rng.uniform(max(x[b] - step / 2, 1e-9), min(x[b] + step / 2, hours))
    return tau


class WindowState:
    """Per-sample latent times in the ORIGINAL frame (warm start across epochs)."""

    def __init__(self):
        self.tau = {}

    def get(self, idx, sample):
        if idx not in self.tau:
            H, W = sample.initial.shape
            t = np.full(H * W, np.inf)
            t[sample.initial.ravel()] = 0.0
            new = (sample.endpoint & sample.score_mask & ~sample.initial).ravel()
            t[new] = 0.5 * sample.hours
            self.tau[idx] = t
        return self.tau[idx]


def _perm(H, W, k, flip):
    from wildfire.canonical import d4_spatial
    idx = torch.arange(H * W).reshape(1, H, W)
    return d4_spatial(idx, k, flip).reshape(-1).numpy()   # augmented[j] = original[perm[j]]


def fit_bracket(model, train, validation, *, epochs=8, learning_rate=3e-3, weight_decay=1e-4, seed=0, patience=3,
                d4=False, samples_per_step=4, balance=None, biome_channels=None, intervals_per_epoch=None,
                validate_each_epoch=True, runtime_case_id_fn=None, runtime_object_sha_fn=None,
                runtime_sample_manifest_sha256=None, log=print, sweeps=2, step=0.25):
    from wildfire.survival import augment, sample_tensors
    if not train or epochs < 1 or samples_per_step < 1:
        raise ValueError("Fitting requires nonempty training samples and positive budgets")
    if getattr(model, "spotting_radius", 0) or getattr(model, "residence_hours", None) is not None:
        raise ValueError("d2_bracket supports kernel-only variants (no burnout/spotting), e.g. d4_wind")
    rng = np.random.default_rng(seed)                                            # training stream, as fit_mean_field
    estep_rng = np.random.default_rng(np.random.SeedSequence([seed, 0x5D2B]))      # separate E-step stream (c)
    torch.manual_seed(seed)
    positives = sum(float((s.endpoint & s.score_mask).sum()) for s in train)
    cells = sum(float(s.score_mask.sum()) for s in train)
    prevalence = max(positives / max(cells, 1.0), 1e-6)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=learning_rate,
                                 weight_decay=weight_decay)
    state = WindowState()
    history = []
    for epoch in range(1, epochs + 1):
        started = time.perf_counter()
        model.train()
        order = rng.permutation(len(train))
        if intervals_per_epoch is not None:
            order = order[:intervals_per_epoch]
        running, steps, skipped, estep_s = 0.0, 0, [], 0.0
        for start in range(0, len(order), samples_per_step):
            optimizer.zero_grad(set_to_none=True)
            terms, w_total = [], 0.0
            for index in order[start:start + samples_per_step]:
                sample0 = train[index]
                H, W = sample0.initial.shape
                tau0 = state.get(int(index), sample0)
                k, flip = 0, False
                if d4:
                    k, flip = int(rng.integers(4)), bool(rng.integers(2))
                sample = augment(sample0, k, flip, model.wind_index) if d4 else sample0
                perm = _perm(H, W, k, flip) if d4 else np.arange(H * W)
                h2, w2 = sample.initial.shape
                tau = tau0[perm].copy()
                t = sample_tensors(sample)
                weight = t["weight"]
                if balance and biome_channels:
                    factor = torch.ones_like(weight)
                    for code, channel in biome_channels.items():
                        factor = torch.where(t["environment"][0, channel] == 1,
                                             torch.full_like(factor, balance.get(code, 1.0)), factor)
                    weight = weight * factor
                Kfull = model.kernel_rates(t["environment"], boundary="zero")[0]          # [D, h2, w2]
                valid = torch.isfinite(Kfull).all(0).reshape(-1).numpy()
                K = torch.nan_to_num(Kfull, nan=0.0).reshape(Kfull.shape[0], -1)
                offs = offsets(K.shape[0])
                src = source_index(h2, w2, offs)
                tgt = source_index(h2, w2, -offs)                                         # tgt[δ, i] = i - δ
                scored = t["mask"].reshape(-1).numpy() & valid
                latent = (sample.endpoint.ravel() & scored & ~sample.initial.ravel())
                if not latent.any() and not scored.any():
                    skipped.append(dict(event=sample.event_id, cutoff=sample.t1, reason="no_scored_cells"))
                    continue
                e0 = time.perf_counter()
                Kn = K.detach().numpy()
                for _ in range(sweeps):
                    tau = gibbs_sweep(Kn, tau, np.flatnonzero(latent), src, tgt, scored, sample.hours, step, estep_rng)
                estep_s += time.perf_counter() - e0
                tau0[perm] = tau                                                          # back to original frame
                ll, wsum = complete_loglik(K, tau, latent, scored, weight.reshape(-1).numpy(), sample.hours, src)
                if wsum <= 0:
                    continue
                terms.append(-ll)
                w_total += wsum
            if w_total <= 0:
                continue
            loss = torch.stack(terms).sum() / w_total / prevalence
            if not bool(torch.isfinite(loss)):
                raise RuntimeError(f"Nonfinite training loss at epoch {epoch}")
            loss.backward()
            optimizer.step()
            steps += 1
            running += float(loss) * len(terms)
        if steps == 0:
            raise ValueError("No supported positive-weight cells remain in the training epoch")
        record = dict(epoch=epoch, train_scaled_loss=running / max(len(order), 1), seconds=time.perf_counter() - started,
                      estep_seconds=estep_s, selected=epoch == epochs, optimizer_steps=steps,
                      skipped_unsupported_intervals=skipped, sweeps=sweeps, step_hours=step)
        history.append(record)
        log(json.dumps(record))
    return dict(history=history, best_validation_brier=None, train_prevalence=prevalence)
