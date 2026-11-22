"""Owen: the Gibbs conditional used by gibbs_sweep must equal (up to a constant) the complete-data log-likelihood as a
function of tau_i, evaluated on the same grid, for every latent cell, on random 3x3-kernel and 5x5-kernel problems with
scored/unscored latents, initially burned and unburned targets."""
import sys, numpy as np, torch
sys.path.insert(0, "."); import d2_bracket as B
ZERO_CENTRE = len(sys.argv) > 1
rng = np.random.default_rng(1); worst = 0.0; n = 0
for trial in range(60):
    D = [9, 25][trial % 2]; H, W = rng.integers(4, 8, 2); N = H * W; hours = float(rng.uniform(3, 30)); step = 0.25
    offs = B.offsets(D); src = B.source_index(H, W, offs); tgt = B.source_index(H, W, -offs)
    K = rng.exponential(0.05, (D, N)) * (rng.random((D, N)) < 0.8)
    if ZERO_CENTRE: K[D // 2] = 0.0
    init = rng.random(N) < 0.15; endb = init | (rng.random(N) < 0.35)
    scored = (~init) & (rng.random(N) < 0.85)
    tau = np.full(N, np.inf); tau[init] = 0.0
    lat = np.flatnonzero(endb & ~init); tau[lat] = rng.uniform(0, hours, len(lat))
    latent_sc = np.zeros(N, bool); latent_sc[lat] = scored[lat]
    w = np.ones(N); Kt = torch.as_tensor(K)
    x = np.arange(step / 2, hours, step)
    for i in lat:
        # sweep's logf, reconstructed by calling gibbs_sweep internals: replicate with a deterministic probe
        ll = []
        for xv in x:
            t2 = tau.copy(); t2[i] = xv
            v, _ = B.complete_loglik(Kt, t2, latent_sc, scored, w, hours, src); ll.append(float(v))
        ll = np.array(ll); ll -= ll.max()
        # capture the sweep's probabilities by monkeypatching rng.choice
        class R:
            def permutation(self, a): return np.array([i])
            def choice(self, n_, p): R.p = p; return 0
            def uniform(self, a, b): return a
        B.gibbs_sweep(K, tau.copy(), np.array([i]), src, tgt, scored, hours, step, R())
        lp = np.log(np.maximum(R.p, 1e-300)); lp -= lp.max()
        m = R.p > 1e-12
        worst = max(worst, float(np.max(np.abs((lp - ll)[m])))); n += 1
print(f"latent cells checked {n}; max |log p_sweep - log p_loglik| (up to const) = {worst:.3e}")
