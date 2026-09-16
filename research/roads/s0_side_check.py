#!/usr/bin/env python
"""Check S0: the pre-labelling side-resolvability check for the roads direction.

    python research/roads/s0_side_check.py --tables
    python research/roads/s0_side_check.py --self-test

WHAT THIS IS
------------
Section 5.1.3 of `research/roads/PREREG_roads_2026-09-16_v0.3.md` pre-registers
check S0: fit the local arrival-time plane at every candidate barrier segment,
form the side statistic, and report what fraction of segments the side rule can
resolve, **before any label is computed**. Gate S1 reads its union pass fraction.

This module is the implementation. It is the cheapest true thing this direction
can produce, and it is available before any scene and before any label.

WHAT IT REFUSES TO DO
---------------------
It ships **no data**. It reads no scene, no burned mask, no perimeter and no
label, which is the section 6.1 provenance firewall as extended to the side rule
in section 5.1.2. Its only inputs are the active-fire detection record and the
committed barrier geometry.

**Every number produced by the self-test is from synthetic geometry generated
in-process from a declared seed.** None of it is Korean data, none of it is a
measurement, and none of it may be quoted anywhere. The Korean detection record
is behind WJ-001 and has never been downloaded. When that clears, the entry point
is `run_check`, which takes real per-segment detections and returns the artifact
block of section 22.2.

CONDITION C2 IS WHAT THIS FILE IMPLEMENTS
-----------------------------------------
`T = s / se(s)` divides by a standard error estimated from the residuals of the
same weighted plane fit. That plane carries three parameters in two dimensions,
so `T` is Student's t on `nu = n_det - 3`, not a z statistic. v0.2 applied a
normal-scale cutoff of 2.0 to it. Here the cutoff is
`t_crit = t_{1 - alpha}(n_det - 3)` at a declared one-sided false-assignment rate
`alpha`, evaluated per segment at that segment's own realised degrees of freedom.
`self_test` demonstrates the difference by Monte Carlo under the null.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Pre-registered constants. Changing any of these is a version bump of the
# pre-registration, not an edit to this file.
# ---------------------------------------------------------------------------

ALPHA_PRIMARY = 0.01                       # per tier, one sided (5.1.2a)
ALPHA_GRID = (0.005, 0.01, 0.025)          # stated in alpha, never in z (12.8)
N_TIERS = 2                                # S-A and S-B (5.1.2b)
ALPHA_UNION_BOUND = ALPHA_PRIMARY * N_TIERS

TIER_A = dict(name="S-A", radius_m=1000.0, min_det=5, min_epochs=3)
TIER_B = dict(name="S-B", radius_m=3000.0, min_det=12, min_epochs=3)

MIN_PARAMS = 3                             # t0 and a two-component gradient


def t_crit(n_det: int, alpha: float = ALPHA_PRIMARY) -> float:
    """The per-segment cutoff. Condition C2.

    Returns +inf when the fit has no residual degrees of freedom, so a segment
    that cannot support a residual scale is never assigned a side.
    """
    nu = n_det - MIN_PARAMS
    if nu < 1:
        return math.inf
    return float(stats.t.isf(alpha, nu))


def min_resolvable_sin_theta(n_det: int, c: float,
                             alpha: float = ALPHA_PRIMARY) -> float:
    """`sin(theta) >= 2 * t_crit(n_det - 3, alpha) * c / sqrt(n_det)` (5.1.3)."""
    return 2.0 * t_crit(n_det, alpha) * c / math.sqrt(n_det)


def c_max(n_det: int, alpha: float = ALPHA_PRIMARY) -> float:
    """Largest front irregularity resolvable at ANY approach angle (5.1.3)."""
    return math.sqrt(n_det) / (2.0 * t_crit(n_det, alpha))


# ---------------------------------------------------------------------------
# The plane fit and the statistic
# ---------------------------------------------------------------------------

@dataclass
class PlaneFit:
    """One weighted local plane `t(x) = t0 + g . (x - x0)` (section 6.4)."""
    n_det: int
    n_epochs: int
    nu: int
    g: np.ndarray                  # minutes per metre, length 2
    sigma_g: np.ndarray            # 2 by 2 covariance of g
    sigma_r: float                 # residual standard error, minutes
    radius_m: float
    ok: bool
    why: str = ""

    @property
    def spread_rate_m_per_min(self) -> float:
        gm = float(np.hypot(*self.g))
        return math.inf if gm == 0.0 else 1.0 / gm

    @property
    def c(self) -> float:
        """Relative front irregularity `c = sigma_r * r / R` (5.1.3)."""
        r = self.spread_rate_m_per_min
        if not np.isfinite(r) or self.radius_m <= 0:
            return math.inf
        return self.sigma_r * r / self.radius_m


def fit_plane(xy: np.ndarray, t_min: np.ndarray, epochs: np.ndarray,
              x0: np.ndarray, radius_m: float,
              weights: np.ndarray | None = None) -> PlaneFit:
    """Weighted least squares plane fit, returning everything the test needs.

    `xy` are detection positions in metres in a projected CRS (EPSG:5186 for
    this study), `t_min` their acquisition times in minutes, `epochs` their
    acquisition-epoch labels, `x0` the segment midpoint.
    """
    xy = np.asarray(xy, dtype=float)
    t_min = np.asarray(t_min, dtype=float)
    n = xy.shape[0]
    n_ep = int(len(np.unique(epochs)))
    nu = n - MIN_PARAMS
    bad = PlaneFit(n, n_ep, max(nu, 0), np.zeros(2), np.full((2, 2), np.nan),
                   float("nan"), radius_m, False, "")
    if n < MIN_PARAMS + 1:
        bad.why = "fewer than %d detections" % (MIN_PARAMS + 1)
        return bad

    d = xy - np.asarray(x0, dtype=float)
    X = np.column_stack([np.ones(n), d[:, 0], d[:, 1]])
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    sw = np.sqrt(w)
    Xw, yw = X * sw[:, None], t_min * sw

    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    rss = float(resid @ resid)
    sigma_r = math.sqrt(rss / nu) if nu > 0 else float("nan")

    xtx = Xw.T @ Xw
    if np.linalg.matrix_rank(xtx) < MIN_PARAMS:
        bad.why = "design matrix is rank deficient (collinear detections)"
        return bad
    cov = np.linalg.inv(xtx) * (sigma_r ** 2)
    return PlaneFit(n, n_ep, nu, beta[1:].copy(), cov[1:, 1:].copy(),
                    sigma_r, radius_m, True, "")


def side_statistic(fit: PlaneFit, normal: np.ndarray) -> float:
    """`T = (g . n) / sqrt(n' Sigma_g n)` (section 5.1.2)."""
    nvec = np.asarray(normal, dtype=float)
    nvec = nvec / np.linalg.norm(nvec)
    s = float(fit.g @ nvec)
    var = float(nvec @ fit.sigma_g @ nvec)
    if not np.isfinite(var) or var <= 0:
        return float("nan")
    return s / math.sqrt(var)


# ---------------------------------------------------------------------------
# The two-tier rule (5.1.2b, 5.1.2c)
# ---------------------------------------------------------------------------

@dataclass
class SideResult:
    tier: str                 # "S-A", "S-B" or "none"
    assigned: bool
    windward_sign: int        # +1, -1, or 0 when unassigned
    reason: str               # "", "SIDE" or "SIDE_2EP"
    T: float
    t_crit: float
    nu: int
    n_det: int
    n_epochs: int
    c: float


def assign_side(fit_a: PlaneFit, fit_b: PlaneFit | None,
                normal: np.ndarray, alpha: float = ALPHA_PRIMARY) -> SideResult:
    """Tier S-A, then tier S-B only where S-A failed. Conditions C2 and 5.1.2c.

    A tier S-A fit with exactly two acquisition epochs does not apply, because
    at two epochs the residual measures the planarity of two level sets rather
    than the irregularity of a propagating front, so `sigma_r` is biased low and
    `T` biased high by an amount no argument in the pre-registration bounds.
    Such a segment falls through to S-B and, failing that, exits `SIDE_2EP`.
    """
    two_epoch_only = False
    for fit, tier in ((fit_a, TIER_A), (fit_b, TIER_B)):
        if fit is None or not fit.ok:
            continue
        if fit.n_det < tier["min_det"]:
            continue
        if fit.n_epochs < tier["min_epochs"]:
            if tier is TIER_A and fit.n_epochs == 2:
                two_epoch_only = True
            continue
        T = side_statistic(fit, normal)
        tc = t_crit(fit.n_det, alpha)
        if np.isfinite(T) and abs(T) >= tc:
            return SideResult(tier["name"], True, -1 if T >= 0 else +1, "",
                              T, tc, fit.nu, fit.n_det, fit.n_epochs, fit.c)

    ref = fit_a if (fit_a is not None and fit_a.ok) else fit_b
    T = side_statistic(ref, normal) if (ref is not None and ref.ok) else float("nan")
    tc = t_crit(ref.n_det, alpha) if (ref is not None and ref.ok) else math.inf
    return SideResult("none", False, 0,
                      "SIDE_2EP" if two_epoch_only else "SIDE",
                      T, tc, ref.nu if ref else 0,
                      ref.n_det if ref else 0, ref.n_epochs if ref else 0,
                      ref.c if ref else math.inf)


# ---------------------------------------------------------------------------
# The reported summary (section 22.2 key paths)
# ---------------------------------------------------------------------------

@dataclass
class S0Summary:
    n_candidate: int = 0
    pass_fraction_by_tier: dict = field(default_factory=dict)
    pass_fraction_union: float = 0.0
    degrees_of_freedom: list = field(default_factory=list)
    c_values: list = field(default_factory=list)
    reasons: dict = field(default_factory=dict)
    wrong_side_plugin: float = float("nan")
    wrong_side_bound: float = float("nan")

    def as_keypaths(self, alpha: float) -> dict:
        return {
            "checks.S0.n_candidate": self.n_candidate,
            "checks.S0.pass_fraction_by_tier": self.pass_fraction_by_tier,
            "checks.S0.pass_fraction_union": self.pass_fraction_union,
            "checks.S0.degrees_of_freedom.deciles": _deciles(self.degrees_of_freedom),
            "checks.S0.c_distribution.deciles": _deciles(self.c_values),
            "checks.S0.wrong_side_plugin.value": self.wrong_side_plugin,
            "checks.S0.wrong_side_plugin.bias_direction": "understates",
            "labels.side_wrong_side_bound": self.wrong_side_bound,
            "meta.side_alpha_per_tier": alpha,
            "meta.side_alpha_union_bound": alpha * N_TIERS,
        }


def _deciles(v) -> list:
    arr = np.asarray([x for x in v if np.isfinite(x)], dtype=float)
    if arr.size == 0:
        return []
    return [float(x) for x in np.percentile(arr, np.arange(10, 100, 10))]


def summarise(results: list[SideResult], alpha: float = ALPHA_PRIMARY) -> S0Summary:
    """Pass fractions per tier and for the union, plus the 5.1.5 diagnostic."""
    s = S0Summary(n_candidate=len(results))
    if not results:
        return s
    n_a = sum(1 for r in results if r.tier == "S-A")
    n_b = sum(1 for r in results if r.tier == "S-B")
    n_fail_a = len(results) - n_a
    s.pass_fraction_by_tier = {
        "S_A": n_a / len(results),
        "S_B_given_S_A_fail": (n_b / n_fail_a) if n_fail_a else 0.0,
    }
    s.pass_fraction_union = (n_a + n_b) / len(results)
    s.degrees_of_freedom = [r.nu for r in results]
    s.c_values = [r.c for r in results]
    for r in results:
        if r.reason:
            s.reasons[r.reason] = s.reasons.get(r.reason, 0) + 1

    # The plug-in wrong-side diagnostic of section 5.1.5. |T| overstates the
    # true noncentrality on the retained set, because retention selects on |T|,
    # so this UNDERSTATES the wrong-side rate. Declared, not corrected.
    assigned = [r for r in results if r.assigned and np.isfinite(r.T) and r.nu >= 1]
    if assigned:
        num = sum(float(stats.nct.cdf(-r.t_crit, r.nu, abs(r.T))) for r in assigned)
        s.wrong_side_plugin = num / len(assigned)
    # The bound that MAY be quoted as a bound: alpha_union / q (section 5.1.5).
    if s.pass_fraction_union > 0:
        s.wrong_side_bound = (alpha * N_TIERS) / s.pass_fraction_union
    return s


def run_check(segments, alpha: float = ALPHA_PRIMARY) -> tuple[list, S0Summary]:
    """Entry point for the real detection record, when WJ-001 clears.

    `segments` is an iterable of dicts with keys `xy`, `t_min`, `epochs`,
    `x0`, `normal`, and optionally `xy_b`, `t_min_b`, `epochs_b` for the 3 km
    neighbourhood. Nothing here touches a scene or a label.
    """
    out = []
    for seg in segments:
        fa = fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                       seg["x0"], TIER_A["radius_m"])
        fb = None
        if "xy_b" in seg:
            fb = fit_plane(seg["xy_b"], seg["t_min_b"], seg["epochs_b"],
                           seg["x0"], TIER_B["radius_m"])
        out.append(assign_side(fa, fb, seg["normal"], alpha))
    return out, summarise(out, alpha)


# ---------------------------------------------------------------------------
# Tables. Pure properties of the t distribution: no data of any kind.
# ---------------------------------------------------------------------------

def table_null_rate_at_2(ns=(5, 6, 8, 12, 25, 40)) -> list[tuple]:
    """What a fixed 2.0 actually costs per tail. Reproduces the sign-off table."""
    return [(n, n - MIN_PARAMS, float(stats.t.sf(2.0, n - MIN_PARAMS)),
             float(stats.norm.sf(2.0))) for n in ns]


def table_min_angle(cs=(0.15, 0.20, 0.30, 0.40, 0.50),
                    ns=(5, 6, 8, 12, 25, 40),
                    alpha: float = ALPHA_PRIMARY) -> dict:
    """The section 5.1.3 angle table. `None` means no angle resolves a side."""
    out = {}
    for c in cs:
        row = []
        for n in ns:
            s = min_resolvable_sin_theta(n, c, alpha)
            row.append(None if s > 1.0 else math.degrees(math.asin(s)))
        out[c] = row
    return out


def print_tables(alpha: float = ALPHA_PRIMARY) -> None:
    ns = (5, 6, 8, 12, 25, 40)
    print("Per-tail null rate of a FIXED 2.0 cutoff (the v0.2 defect):")
    print("  n_det  nu   P(T>2.0)   normal")
    for n, nu, p, z in table_null_rate_at_2(ns):
        print("  %5d %3d   %8.4f %8.4f" % (n, nu, p, z))
    print()
    print("t_crit = t_{1-alpha}(n_det - 3), alpha = %g:" % alpha)
    print("  " + "".join("%9d" % n for n in ns))
    print("  " + "".join("%9.3f" % t_crit(n, alpha) for n in ns))
    print()
    print("Minimum resolvable approach angle, degrees (section 5.1.3):")
    print("  c      " + "".join("%9d" % n for n in ns))
    for c, row in table_min_angle(ns=ns, alpha=alpha).items():
        cells = "".join("%9s" % ("none" if v is None else "%.1f" % v) for v in row)
        print("  %.2f  %s" % (c, cells))
    print()
    print("c_max, largest irregularity resolvable at any angle:")
    print("  " + "".join("%9d" % n for n in ns))
    print("  " + "".join("%9.2f" % c_max(n, alpha) for n in ns))


# ---------------------------------------------------------------------------
# Self-test. SYNTHETIC GEOMETRY ONLY, seeded, never quotable.
# ---------------------------------------------------------------------------

def _synthetic_segment(rng, n_det, n_epochs, theta_deg, c, radius=1000.0,
                       rate_m_per_min=20.0):
    """A synthetic detection cloud with a known front direction.

    NOT KOREAN DATA. A declared generative model used to exercise the code.
    """
    ang = math.radians(theta_deg)
    direction = np.array([math.cos(ang), math.sin(ang)])
    xy = rng.uniform(-radius, radius, size=(n_det, 2))
    keep = np.hypot(xy[:, 0], xy[:, 1]) <= radius
    while keep.sum() < n_det:
        extra = rng.uniform(-radius, radius, size=(n_det, 2))
        xy = np.vstack([xy[keep], extra])
        keep = np.hypot(xy[:, 0], xy[:, 1]) <= radius
    xy = xy[keep][:n_det]
    t_clean = (xy @ direction) / rate_m_per_min
    sigma_r = c * (radius / rate_m_per_min)
    t_min = t_clean + rng.normal(0.0, sigma_r, size=n_det)
    epochs = rng.integers(0, max(n_epochs, 1), size=n_det)
    for k in range(min(n_epochs, n_det)):      # guarantee every epoch appears
        epochs[k] = k
    return dict(xy=xy, t_min=t_min, epochs=epochs, x0=np.zeros(2),
                normal=np.array([1.0, 0.0]), true_direction=direction)


def self_test() -> int:
    bad = 0

    def check(cond, msg):
        nonlocal bad
        if not cond:
            print("SELF-TEST FAIL: " + msg)
            bad += 1

    # 1. The sign-off's t-versus-normal table reproduces.
    want = {5: 0.0918, 6: 0.0697, 8: 0.0510, 12: 0.0383, 25: 0.0290, 40: 0.0264}
    for n, nu, p, _z in table_null_rate_at_2():
        check(abs(p - want[n]) < 5e-5,
              "null rate at 2.0 for n_det=%d is %.4f, expected %.4f" % (n, p, want[n]))

    # 2. The pre-registered angle table reproduces what section 5.1.3 prints.
    tab = table_min_angle()
    check(tab[0.15][0] is not None and abs(tab[0.15][0] - 69.1) < 0.1,
          "angle table c=0.15 n_det=5 should be about 69.1 degrees")
    check(tab[0.20][0] is None,
          "angle table c=0.20 n_det=5 should be unresolvable at any angle")
    check(abs(c_max(5) - 0.161) < 5e-4, "c_max at n_det=5 should be about 0.161")
    check(abs(c_max(25) - 0.997) < 5e-4, "c_max at n_det=25 should be about 0.997")

    # 3. Null calibration by Monte Carlo. THIS IS THE POINT OF CONDITION C2.
    #    Under a front running parallel to the barrier normal's perpendicular,
    #    the projected gradient is zero, so the two-sided assignment rate should
    #    be 2 * alpha under the t cutoff and materially above it under 2.0.
    rng = np.random.default_rng(20260916)
    n_sim, n_det, alpha = 4000, 5, ALPHA_PRIMARY
    hit_t = hit_z = 0
    for _ in range(n_sim):
        seg = _synthetic_segment(rng, n_det, 3, theta_deg=90.0, c=0.20)
        fit = fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                        seg["x0"], TIER_A["radius_m"])
        if not fit.ok:
            continue
        T = side_statistic(fit, seg["normal"])
        if np.isfinite(T):
            hit_t += abs(T) >= t_crit(n_det, alpha)
            hit_z += abs(T) >= 2.0
    rate_t, rate_z = hit_t / n_sim, hit_z / n_sim
    check(abs(rate_t - 2 * alpha) < 0.012,
          "t cutoff null assignment rate %.4f is not near %.4f" % (rate_t, 2 * alpha))
    check(rate_z > 0.10,
          "the 2.0 cutoff should be badly anticonservative at nu=2, got %.4f" % rate_z)
    check(rate_z > 3 * rate_t,
          "the 2.0 cutoff should be several times the t cutoff, got %.4f vs %.4f"
          % (rate_z, rate_t))

    # 4. A well-resolved front gets the right side.
    rng = np.random.default_rng(11)
    ok = 0
    for _ in range(200):
        seg = _synthetic_segment(rng, 40, 5, theta_deg=0.0, c=0.15)
        fa = fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                       seg["x0"], TIER_A["radius_m"])
        res = assign_side(fa, None, seg["normal"])
        ok += res.assigned and res.windward_sign == -1
    check(ok >= 190, "a perpendicular, well-detected front should resolve; got %d/200" % ok)

    # 5. Two epochs never reach tier S-A, and exit SIDE_2EP when S-B is absent.
    rng = np.random.default_rng(7)
    seg = _synthetic_segment(rng, 30, 2, theta_deg=0.0, c=0.15)
    fa = fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                   seg["x0"], TIER_A["radius_m"])
    res = assign_side(fa, None, seg["normal"])
    check(fa.n_epochs == 2, "the two-epoch fixture should carry two epochs")
    check(not res.assigned and res.reason == "SIDE_2EP",
          "a two-epoch segment must not be assigned by tier S-A; got %r" % res)

    # 6. Degrees of freedom and the fail-closed behaviour at the bottom.
    check(t_crit(3) == math.inf, "n_det=3 leaves no residual df and must never assign")
    check(fit_plane(np.zeros((3, 2)), np.zeros(3), np.zeros(3),
                    np.zeros(2), 1000.0).ok is False,
          "a three-detection fit must be refused")

    # 7. The union pass fraction and the quotable bound.
    results = [SideResult("S-A", True, -1, "", 8.0, 6.9, 2, 5, 3, 0.1)] * 30
    results += [SideResult("none", False, 0, "SIDE", 0.2, 6.9, 2, 5, 3, 0.9)] * 70
    s = summarise(results)
    check(abs(s.pass_fraction_union - 0.30) < 1e-9, "union pass fraction should be 0.30")
    check(abs(s.wrong_side_bound - (ALPHA_UNION_BOUND / 0.30)) < 1e-9,
          "the quotable bound should be alpha_union / q")

    if bad == 0:
        print("self-test ok: tables reproduce, null calibration holds, "
              "two-epoch segments are separated, and the fit fails closed")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tables", action="store_true",
                    help="print the section 5.1.3 tables (no data is read)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--alpha", type=float, default=ALPHA_PRIMARY)
    a = ap.parse_args()
    if a.self_test:
        return 1 if self_test() else 0
    if a.tables:
        print_tables(a.alpha)
        return 0
    print(__doc__)
    print("Nothing to run: the Korean detection record is behind WJ-001 and has "
          "never been downloaded. Use --tables or --self-test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
