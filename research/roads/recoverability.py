#!/usr/bin/env python
"""Instruments 2 and 2b: design-stage recoverability, before any label exists.

    python research/roads/recoverability.py --self-test
    python research/roads/recoverability.py --demo        # synthetic geometry

WHAT THIS IS
------------
Section 11.5.2 and 11.5.2b of `research/roads/PREREG_roads_2026-09-16_v0.3.md`
pre-register two power instruments that run on **simulated outcomes** against the
**real geometry and the real measured width distribution**:

* **instrument 2, detection power.** Simulate under a true width slope equal to
  the smallest effect of interest, refit, and count the fraction of simulations
  reaching the F1 threshold `P(beta_width < 0) >= 0.90`. Gate **R0** reads it at
  0.20; the reading rule of 11.5.6 reads it at 0.80.
* **instrument 2b, exclusion power.** Simulate under a true slope of **zero**,
  refit, and count the fraction of simulations whose 90 per cent interval on the
  probability contrast between 6 m and 3 m of `W_cleared`, at the sample median
  approach angle, lies **entirely below** the smallest effect of interest. Gate
  **M2** reads it at 0.80.

They are different quantities and a design can pass one and fail the other, which
is why v0.1b's single instrument was refused.

CONDITION C4 IS WHAT `geometry` RECORDS
---------------------------------------
v0.2 said the instruments take "the real segment geometry" and never said which
real set. Both the candidate set and the side-passing set are real and they have
different width supports. Every result here carries the name of the set it ran on
and `run` refuses to produce a gate-readable number without one. Gate R0 reads the
R-set value (section 5.1.6).

THE BACKEND, AND WHY IT IS A PRE-REGISTERED FIELD
-------------------------------------------------
The pre-registered fit is PyMC with NUTS at the section 22.4 settings. That is
minutes per fit and 500 fits per arm, which is the section 22.4 wall-clock
problem, not a correctness problem. This module exposes the refit as a pluggable
backend so the harness itself can be exercised and tested now, before any real
geometry exists, without pretending a fast approximation is the pre-registered
number:

* ``laplace``  a MAP fit with a Laplace posterior. Fast. **Diagnostic only.**
* ``nuts``     the pre-registered backend. Not implemented here, because the
               model lives in the fit pipeline that WJ-009 and WJ-001 gate.

``Result.gate_readable`` is true only for ``nuts``. A ``laplace`` number may be
reported, labelled as a harness diagnostic, and may not be read by gate R0 or
gate M2. This is the same discipline section 11.5.1 applies to ``kappa_raw``.

NO DATA
-------
This module ships no data and reads nothing from disk. ``--demo`` and the tests
run on synthetic geometry generated in-process from a declared seed. **No number
from them is a measurement and none may be quoted.** The real geometry arrives
with WJ-009 and WJ-001.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats

# --------------------------------------------------------------- pre-registered
SMALLEST_EFFECT = 0.05           # probability, W_cleared 3 m to 6 m (11.5.3)
SMALLEST_EFFECT_ALONGSIDE = 0.10
CONTRAST_LOW_M, CONTRAST_HIGH_M = 3.0, 6.0
F1_THRESHOLD = 0.90              # P(beta_width < 0) (section 1.5)
GATE_R0 = 0.20
GATE_M2 = 0.80
DRAWS_PRIMARY = 500              # section 11.5.2; 200 under the 22.4 cut
THETA_CLIP_DEG = 15.0
GEOMETRIES = ("rset", "candidate", "labelled")
BACKENDS = ("nuts", "laplace")


def w_eff(w_cleared: np.ndarray, theta_deg: np.ndarray) -> np.ndarray:
    """`W_eff = W_cleared / sin(max(theta, 15 deg))` (section 6.5)."""
    s = np.sin(np.radians(np.maximum(theta_deg, THETA_CLIP_DEG)))
    return np.asarray(w_cleared, dtype=float) / s


def v_of(w_cleared: np.ndarray, theta_deg: np.ndarray) -> np.ndarray:
    """The fitted covariate `v = log(W_eff + 1)` (section 11.5.1)."""
    return np.log(w_eff(w_cleared, theta_deg) + 1.0)


@dataclass
class Geometry:
    """One of the three sets of section 5.1.6. Carries its own name."""
    name: str
    w_cleared_m: np.ndarray
    theta_deg: np.ndarray
    fire_id: np.ndarray
    sigma_u_m: float

    def __post_init__(self):
        if self.name not in GEOMETRIES:
            raise ValueError("geometry must be one of %r, got %r"
                             % (GEOMETRIES, self.name))
        self.w_cleared_m = np.asarray(self.w_cleared_m, dtype=float)
        self.theta_deg = np.asarray(self.theta_deg, dtype=float)
        self.fire_id = np.asarray(self.fire_id)
        n = len(self.w_cleared_m)
        if not (len(self.theta_deg) == len(self.fire_id) == n):
            raise ValueError("geometry columns have different lengths")
        if self.sigma_u_m <= 0:
            raise ValueError("sigma_u must be positive; it comes from instrument 1")

    def __len__(self) -> int:
        return len(self.w_cleared_m)

    @property
    def median_theta_deg(self) -> float:
        return float(np.median(self.theta_deg))

    def var_v_true(self) -> float:
        """`Var(v_true)`, mechanism 1 of section 5.1.4, on THIS set."""
        return float(np.var(v_of(self.w_cleared_m, self.theta_deg), ddof=1))

    def mean_sigma_v_sq(self) -> float:
        """`mean_i sigma_v_i^2`, mechanism 2 of section 5.1.4, on THIS set."""
        s = np.sin(np.radians(np.maximum(self.theta_deg, THETA_CLIP_DEG)))
        sigma_v = self.sigma_u_m / (self.w_cleared_m + s)
        return float(np.mean(sigma_v ** 2))

    def kappa_v(self) -> float:
        """The attenuation factor on the model's scale (section 11.5.1)."""
        vt = self.var_v_true()
        return vt / (vt + self.mean_sigma_v_sq())


# --------------------------------------------------------------- the contrast

def contrast_probability(intercept: float, beta: float, median_theta_deg: float,
                         low_m: float = CONTRAST_LOW_M,
                         high_m: float = CONTRAST_HIGH_M) -> float:
    """`p(low) - p(high)` on the probability scale, at the median approach angle.

    Positive means a wider barrier is associated with a lower modelled
    probability of a lee-side burn, which is the direction `H-ROADS` states.
    """
    th = np.array([median_theta_deg, median_theta_deg])
    v = v_of(np.array([low_m, high_m]), th)
    p = 1.0 / (1.0 + np.exp(-(intercept + beta * v)))
    return float(p[0] - p[1])


def beta_for_contrast(target: float, intercept: float,
                      median_theta_deg: float) -> float:
    """The slope that produces a given probability contrast. Used to simulate.

    `target` is positive under `H-ROADS`: the modelled probability of a lee-side
    burn is LOWER at 6 m than at 3 m, which needs a NEGATIVE slope on
    `v = log(W_eff + 1)`, because `v` increases with width. F1 reads
    `P(beta_width < 0)`, so the two conventions agree.

    The contrast is not monotone in `beta`: it vanishes at both extremes, because
    a large slope of either sign saturates both probabilities. So the root is
    taken on the branch between zero and the maximising slope, which is the one
    with the smaller absolute slope and is therefore the conservative choice for
    a power calculation.
    """
    if target == 0.0:
        return 0.0
    if target < 0:
        raise ValueError("target contrast is positive under H-ROADS; got %r" % target)
    grid = np.linspace(-50.0, 0.0, 2001)
    vals = np.array([contrast_probability(intercept, b, median_theta_deg)
                     for b in grid])
    i = int(np.argmax(vals))
    if vals[i] < target:
        raise ValueError(
            "a contrast of %.4f is unreachable at intercept %.3f and median angle "
            "%.1f deg; the largest attainable is %.4f. The smallest effect of "
            "interest is not attainable under this intercept, which is itself a "
            "reportable design finding (section 11.5.3)."
            % (target, intercept, median_theta_deg, vals[i]))
    f = lambda b: contrast_probability(intercept, b, median_theta_deg) - target
    return float(optimize.brentq(f, grid[i], 0.0, xtol=1e-12))


# --------------------------------------------------------------- the backends

def _laplace_refit(v_obs: np.ndarray, y: np.ndarray, sigma_v: np.ndarray,
                   rng, n_post: int = 400):
    """MAP plus Laplace posterior for a logistic with a measurement layer.

    The measurement layer is handled by regression calibration, which inflates
    the slope's variance rather than integrating the latent covariate. That is
    an approximation and it is why this backend is diagnostic only.
    """
    kappa = np.var(v_obs, ddof=1) / (np.var(v_obs, ddof=1) + np.mean(sigma_v ** 2))
    X = np.column_stack([np.ones(len(v_obs)), v_obs])

    def nll(p):
        z = X @ p
        z = np.clip(z, -30, 30)
        return float(np.sum(np.log1p(np.exp(z)) - y * z)
                     + 0.5 * (p[0] / 2.5) ** 2 + 0.5 * (p[1] / 1.0) ** 2)

    res = optimize.minimize(nll, np.array([0.0, 0.0]), method="BFGS")
    mean = res.x.copy()
    cov = res.hess_inv if np.ndim(res.hess_inv) == 2 else np.eye(2)
    cov = np.asarray(cov, dtype=float)
    # Disattenuate: divide the slope and inflate its standard deviation.
    mean[1] /= kappa
    cov[1, 1] /= kappa ** 2
    try:
        draws = rng.multivariate_normal(mean, cov, size=n_post)
    except np.linalg.LinAlgError:
        draws = rng.multivariate_normal(mean, np.diag(np.diag(cov)), size=n_post)
    return draws


# --------------------------------------------------------------- the instruments

@dataclass
class Result:
    instrument: str
    geometry: str
    backend: str
    value: float
    threshold: float
    at_effect: float
    n_draws: int
    n_segments: int
    mc_standard_error: float
    gate_readable: bool
    notes: str = ""

    def as_keypaths(self) -> dict:
        base = "recoverability.%s.%s" % (self.instrument, self.geometry)
        return {
            "recoverability.geometry": self.geometry,
            "recoverability.backend": self.backend,
            base + ".value": self.value,
            base + ".threshold": self.threshold,
            base + ".at_effect": self.at_effect,
            base + ".mc_standard_error": self.mc_standard_error,
            base + ".gate_readable": self.gate_readable,
        }


@dataclass
class Report:
    results: list = field(default_factory=list)

    def keypaths(self) -> dict:
        out = {}
        for r in self.results:
            out.update(r.as_keypaths())
        return out


def _simulate_once(geo: Geometry, beta_true: float, intercept: float, rng):
    v_true = v_of(geo.w_cleared_m, geo.theta_deg)
    s = np.sin(np.radians(np.maximum(geo.theta_deg, THETA_CLIP_DEG)))
    sigma_v = geo.sigma_u_m / (geo.w_cleared_m + s)
    v_obs = v_true + rng.normal(0.0, sigma_v)
    z = np.clip(intercept + beta_true * v_true, -30, 30)
    y = rng.binomial(1, 1.0 / (1.0 + np.exp(-z)))
    return v_obs, y, sigma_v


def run(geo: Geometry, instrument: str, at_effect: float = SMALLEST_EFFECT,
        n_draws: int = DRAWS_PRIMARY, backend: str = "laplace",
        intercept: float = 0.0, seed: int = 20260916) -> Result:
    """Run instrument 2 (`detection_power`) or 2b (`exclusion_power`)."""
    if instrument not in ("detection_power", "exclusion_power"):
        raise ValueError("unknown instrument %r" % instrument)
    if backend not in BACKENDS:
        raise ValueError("unknown backend %r" % backend)
    if backend == "nuts":
        raise NotImplementedError(
            "The pre-registered NUTS backend lives in the fit pipeline, which is "
            "gated on WJ-009 and WJ-001. Only this backend produces a number gate "
            "R0 or gate M2 may read (section 11.5.2).")

    rng = np.random.default_rng(seed)
    med = geo.median_theta_deg
    # Instrument 2 simulates UNDER the smallest effect; 2b simulates under zero.
    target = at_effect if instrument == "detection_power" else 0.0
    beta_true = beta_for_contrast(target, intercept, med) if target else 0.0

    hits = 0
    for _ in range(n_draws):
        v_obs, y, sigma_v = _simulate_once(geo, beta_true, intercept, rng)
        if y.sum() in (0, len(y)):        # a degenerate draw cannot be a hit
            continue
        post = _laplace_refit(v_obs, y, sigma_v, rng)
        if instrument == "detection_power":
            hits += float(np.mean(post[:, 1] < 0.0)) >= F1_THRESHOLD
        else:
            contrasts = np.array([contrast_probability(a, b, med) for a, b in post])
            hits += float(np.percentile(contrasts, 95)) < at_effect

    value = hits / n_draws
    mcse = math.sqrt(max(value * (1 - value), 1e-12) / n_draws)
    return Result(instrument, geo.name, backend, value,
                  GATE_R0 if instrument == "detection_power" else GATE_M2,
                  at_effect, n_draws, len(geo), mcse, gate_readable=False,
                  notes="laplace backend: harness diagnostic, not gate readable")


def run_both_geometries(rset: Geometry, candidate: Geometry, **kw) -> Report:
    """Condition C4: both sets, both instruments, every value carrying its set."""
    rep = Report()
    for geo in (rset, candidate):
        for inst in ("detection_power", "exclusion_power"):
            rep.results.append(run(geo, inst, **kw))
    return rep


# --------------------------------------------------------------- synthetic only

def _synthetic_geometry(rng, n, name="rset", sigma_u_m=0.6,
                        theta_low=20.0, theta_high=90.0, n_fires=5):
    """NOT KOREAN DATA. A declared generative model for exercising the harness."""
    w = np.clip(rng.lognormal(math.log(4.0), 0.45, size=n), 1.5, 14.0)
    th = rng.uniform(theta_low, theta_high, size=n)
    fid = rng.integers(0, n_fires, size=n)
    return Geometry(name, w, th, fid, sigma_u_m)


def self_test() -> int:
    bad = 0

    def check(cond, msg):
        nonlocal bad
        if not cond:
            print("SELF-TEST FAIL: " + msg)
            bad += 1

    rng = np.random.default_rng(1)
    geo = _synthetic_geometry(rng, 200)

    # The contrast machinery inverts.
    b = beta_for_contrast(0.05, 0.0, geo.median_theta_deg)
    check(abs(contrast_probability(0.0, b, geo.median_theta_deg) - 0.05) < 1e-8,
          "beta_for_contrast does not invert contrast_probability")
    check(b < 0, "a probability drop with width needs a negative slope on v")

    # Condition C4: a truncated set has a different kappa_v and says which it is.
    rng = np.random.default_rng(2)
    cand = _synthetic_geometry(rng, 400, name="candidate", theta_low=5.0)
    rs = Geometry("rset", cand.w_cleared_m[cand.theta_deg >= 20.0],
                  cand.theta_deg[cand.theta_deg >= 20.0],
                  cand.fire_id[cand.theta_deg >= 20.0], cand.sigma_u_m)
    check(rs.name == "rset" and cand.name == "candidate", "geometry must carry its name")
    check(rs.var_v_true() < cand.var_v_true(),
          "removing grazing angles must lower Var(v_true): mechanism 1")
    check(rs.mean_sigma_v_sq() <= cand.mean_sigma_v_sq(),
          "removing grazing angles must not raise mean sigma_v^2: mechanism 2")

    # A geometry cannot be built without a name from the declared set.
    try:
        Geometry("whatever", [3.0], [40.0], [0], 0.5)
        check(False, "an undeclared geometry name must be refused")
    except ValueError:
        pass

    # The pre-registered backend is not silently substituted.
    try:
        run(geo, "detection_power", backend="nuts", n_draws=1)
        check(False, "the nuts backend must not be silently faked")
    except NotImplementedError:
        pass

    # The two instruments are different quantities on the same geometry.
    rng = np.random.default_rng(5)
    small = _synthetic_geometry(rng, 120)
    d = run(small, "detection_power", n_draws=60, seed=3)
    x = run(small, "exclusion_power", n_draws=60, seed=3)
    check(d.instrument != x.instrument and d.threshold != x.threshold,
          "instrument 2 and 2b must carry different thresholds")
    check(not d.gate_readable and not x.gate_readable,
          "a laplace number must never be gate readable")
    check(d.geometry == "rset" and "recoverability.geometry" in d.as_keypaths(),
          "every result must record the geometry it ran on: condition C4")

    # Power rises with sample size. The direction is the harness's own sanity check.
    rng = np.random.default_rng(9)
    big = _synthetic_geometry(rng, 900)
    d_small = run(small, "detection_power", at_effect=0.05, n_draws=60, seed=11)
    d_big = run(big, "detection_power", at_effect=0.05, n_draws=60, seed=11)
    check(d_big.value >= d_small.value,
          "detection power must not fall with a nine-fold larger sample: %.3f vs %.3f"
          % (d_big.value, d_small.value))

    # The attainable contrast is bounded by the intercept, and the harness says
    # so rather than clipping. This is a real design fact, not a guard clause:
    # v(3 m) and v(6 m) are close on the log scale, so a large probability
    # contrast between them is not reachable at any slope.
    try:
        beta_for_contrast(0.20, 0.0, small.median_theta_deg)
        check(False, "an unreachable contrast must raise rather than clip")
    except ValueError as exc:
        check("unreachable" in str(exc), "the raise must say what was unreachable")

    # Monte Carlo standard error is reported, per section 22.4 item 3.
    check(d.mc_standard_error > 0 and d.n_draws == 60,
          "the Monte Carlo standard error and the draw count must be reported")

    if bad == 0:
        print("self-test ok: contrast inverts, geometries carry their names, "
              "the pre-registered backend cannot be faked, and the two "
              "instruments stay distinct")
    return bad


def demo() -> None:
    rng = np.random.default_rng(20260916)
    cand = _synthetic_geometry(rng, 600, name="candidate", theta_low=5.0)
    keep = cand.theta_deg >= 20.0
    rs = Geometry("rset", cand.w_cleared_m[keep], cand.theta_deg[keep],
                  cand.fire_id[keep], cand.sigma_u_m)
    print("SYNTHETIC GEOMETRY. Not Korean data. No number below may be quoted.\n")
    for g in (cand, rs):
        print("%-10s n=%4d  Var(v_true)=%.4f  mean sigma_v^2=%.5f  kappa_v=%.3f"
              % (g.name, len(g), g.var_v_true(), g.mean_sigma_v_sq(), g.kappa_v()))
    print()
    rep = run_both_geometries(rs, cand, n_draws=80)
    for r in rep.results:
        print("%-16s on %-10s %.3f (threshold %.2f, mcse %.3f, gate readable %s)"
              % (r.instrument, r.geometry, r.value, r.threshold,
                 r.mc_standard_error, r.gate_readable))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return 1 if self_test() else 0
    if a.demo:
        demo()
        return 0
    print(__doc__)
    print("Nothing to run: the real geometry is behind WJ-009 and WJ-001.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
