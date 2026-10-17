"""Constant-velocity Kalman filter for image-plane ember tracks, vectorised over tracks.

State per track: [x, y, vx, vy] in px and px/s, image axes with x to the right and y down.
Time steps come from the true frame timestamps, so they may vary from frame to frame
(variable frame rate phone video, dropped frames, stalls).

Process noise: continuous white-noise acceleration with power spectral density q
(px^2/s^3). Over a step dt each axis gets

    Q(dt) = q [[dt^3/3, dt^2/2],
               [dt^2/2, dt    ]]

This form composes exactly: predicting over dt1 and then dt2 gives the same covariance as
predicting over dt1 + dt2 in one step, so it stays consistent when frame intervals vary.

The config states track.accel_sigma_px in px per frame squared at the nominal frame
interval dt0. It is converted to an acceleration sigma_a = accel_sigma_px / dt0^2 (px/s^2)
and q = sigma_a^2 dt0 (`process_psd`). Over one nominal frame the velocity variance then
grows by (accel_sigma_px / dt0)^2, exactly as in the usual discrete white-noise
acceleration model, while longer or shorter steps scale correctly.

Measurement noise: an isotropic track.meas_sigma_px for point-like spots. For motion-blur
streaks the centroid is less certain along the streak axis (flicker inside the exposure
moves the brightness-weighted centroid), so an extra standard deviation of
`streak_frac * L` is added along the axis direction theta (`measurement_cov`).

Every function works on stacks: X has shape (n, 4), P has shape (n, 4, 4), and the
2 x 2 matrices are inverted in closed form, so a frame with a hundred tracks costs a few
small numpy operations instead of a Python loop.
"""
from __future__ import annotations

import numpy as np

_EYE4 = np.eye(4)


def process_psd(accel_sigma_px_per_frame2: float, dt_nominal: float) -> float:
    """Power spectral density q (px^2/s^3) from an acceleration sigma in px per frame squared."""
    if dt_nominal <= 0:
        raise ValueError("nominal frame interval must be positive")
    sigma_a = accel_sigma_px_per_frame2 / dt_nominal ** 2   # px/s^2
    return float(sigma_a ** 2 * dt_nominal)


def transition(dt: float | np.ndarray) -> np.ndarray:
    """State transition F(dt). Scalar dt gives (4, 4); an array of n steps gives (n, 4, 4)."""
    dt_arr = np.asarray(dt, dtype=np.float64)
    f = np.broadcast_to(_EYE4, (*dt_arr.shape, 4, 4)).copy()
    f[..., 0, 2] = dt_arr
    f[..., 1, 3] = dt_arr
    return f


def process_noise(dt: float | np.ndarray, q: float) -> np.ndarray:
    """Continuous white-noise acceleration covariance Q(dt), shape (4, 4) or (n, 4, 4)."""
    dt_arr = np.asarray(dt, dtype=np.float64)
    out = np.zeros((*dt_arr.shape, 4, 4))
    a, b, c = q * dt_arr ** 3 / 3.0, q * dt_arr ** 2 / 2.0, q * dt_arr
    out[..., 0, 0] = out[..., 1, 1] = a
    out[..., 0, 2] = out[..., 2, 0] = out[..., 1, 3] = out[..., 3, 1] = b
    out[..., 2, 2] = out[..., 3, 3] = c
    return out


def predict(x: np.ndarray, p: np.ndarray, dt: float | np.ndarray, q: float | np.ndarray
            ) -> tuple[np.ndarray, np.ndarray]:
    """Predict states (n, 4) and covariances (n, 4, 4) forward by dt (scalar or (n,)).

    q is the process-noise power spectral density, one value or one per track (n,).

    Written out by blocks, P' = F P F^T + Q with F = [[I, dt I], [0, I]]:
    P'pp = Ppp + dt (Ppv + Pvp) + dt^2 Pvv, P'pv = Ppv + dt Pvv, P'vv = Pvv.
    """
    dt_arr = np.asarray(dt, dtype=np.float64)
    d1 = dt_arr if dt_arr.ndim == 0 else dt_arr[:, None]
    d2 = dt_arr if dt_arr.ndim == 0 else dt_arr[:, None, None]
    xn = x.copy()
    xn[:, :2] += x[:, 2:] * d1
    pn = p.copy()
    pvv = p[:, 2:, 2:]
    pvp = p[:, 2:, :2] + d2 * pvv
    pn[:, 2:, :2] = pvp
    pn[:, :2, 2:] = np.swapaxes(pvp, 1, 2)
    pn[:, :2, :2] = p[:, :2, :2] + d2 * (p[:, :2, 2:] + p[:, 2:, :2]) + d2 * d2 * pvv
    a, b, c = q * dt_arr ** 3 / 3.0, q * dt_arr ** 2 / 2.0, q * dt_arr
    for i in (0, 1):
        pn[:, i, i] += a
        pn[:, i, i + 2] += b
        pn[:, i + 2, i] += b
        pn[:, i + 2, i + 2] += c
    return xn, pn


def measurement_cov(length: np.ndarray, theta: np.ndarray, meas_sigma_px: float,
                    streak_frac: float) -> np.ndarray:
    """Per-detection measurement covariance R, shape (m, 2, 2).

    Isotropic meas_sigma_px^2 plus (streak_frac * L)^2 along the streak axis theta.
    """
    length = np.nan_to_num(np.asarray(length, dtype=np.float64), nan=0.0)
    theta = np.nan_to_num(np.asarray(theta, dtype=np.float64), nan=0.0)
    m = length.shape[0]
    r = np.zeros((m, 2, 2))
    extra = (streak_frac * length) ** 2
    c, s = np.cos(theta), np.sin(theta)
    base = meas_sigma_px ** 2
    r[:, 0, 0] = base + extra * c * c
    r[:, 1, 1] = base + extra * s * s
    r[:, 0, 1] = r[:, 1, 0] = extra * c * s
    return r


def inv2(s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form inverse of stacked symmetric 2 x 2 matrices. Returns (inverse, determinant)."""
    a, b, d = s[..., 0, 0], s[..., 0, 1], s[..., 1, 1]
    det = a * d - b * b
    inv = np.empty_like(s)
    inv[..., 0, 0] = d / det
    inv[..., 1, 1] = a / det
    inv[..., 0, 1] = inv[..., 1, 0] = -b / det
    return inv, det


def mahalanobis_sq(x: np.ndarray, p: np.ndarray, z: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Squared Mahalanobis distance of every detection to every predicted track.

    x (n, 4) and p (n, 4, 4) are predicted states; z (m, 2) are measured positions with
    covariances r (m, 2, 2). The innovation covariance of pair (i, j) is
    S_ij = H P_i H^T + R_j. Returns an (n, m) array.
    """
    n, m = x.shape[0], z.shape[0]
    if n == 0 or m == 0:
        return np.zeros((n, m))
    rows, cols = np.divmod(np.arange(n * m), m)
    return mahalanobis_pairs(x, p, z, r, rows, cols).reshape(n, m)


def mahalanobis_pairs(x: np.ndarray, p: np.ndarray, z: np.ndarray, r: np.ndarray,
                      rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """Squared Mahalanobis distance for the listed (track, detection) pairs only."""
    dx = z[cols, 0] - x[rows, 0]
    dy = z[cols, 1] - x[rows, 1]
    a = p[rows, 0, 0] + r[cols, 0, 0]
    b = p[rows, 0, 1] + r[cols, 0, 1]
    d = p[rows, 1, 1] + r[cols, 1, 1]
    return (d * dx * dx - 2.0 * b * dx * dy + a * dy * dy) / (a * d - b * b)


def gated_pairs(x: np.ndarray, p: np.ndarray, z: np.ndarray, r: np.ndarray, gate_chi2: float
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(track, detection) pairs with squared Mahalanobis distance <= gate_chi2.

    A cheap Euclidean pre-gate comes first: d2 >= |dz|^2 / lambda_max(S_ij) and
    lambda_max(S_ij) <= lambda_max(P_i) + lambda_max(R_j), so pairs farther apart than
    sqrt(gate_chi2 (lambda_max(P_i) + max_j lambda_max(R_j))) cannot pass the gate.
    The exact distance is then computed only for the surviving pairs.
    Returns (rows, cols, d2).
    """
    n, m = x.shape[0], z.shape[0]
    if n == 0 or m == 0:
        e = np.zeros(0, np.int64)
        return e, e, np.zeros(0)
    lam_p = _lambda_max(p[:, :2, :2])
    lam_r = float(_lambda_max(r).max())
    dx = z[None, :, 0] - x[:, None, 0]
    dy = z[None, :, 1] - x[:, None, 1]
    reach2 = gate_chi2 * (lam_p + lam_r)
    rows, cols = np.nonzero(dx * dx + dy * dy <= reach2[:, None])
    d2 = mahalanobis_pairs(x, p, z, r, rows, cols)
    ok = d2 <= gate_chi2
    return rows[ok], cols[ok], d2[ok]


def _lambda_max(s: np.ndarray) -> np.ndarray:
    """Largest eigenvalue of stacked symmetric 2 x 2 matrices."""
    a, b, d = s[..., 0, 0], s[..., 0, 1], s[..., 1, 1]
    return 0.5 * (a + d) + np.sqrt(0.25 * (a - d) ** 2 + b * b)


def update(x: np.ndarray, p: np.ndarray, z: np.ndarray, r: np.ndarray
           ) -> tuple[np.ndarray, np.ndarray]:
    """Kalman update of k tracks with k matched measurements.

    x (k, 4), p (k, 4, 4), z (k, 2), r (k, 2, 2). Returns the updated (x, p). Uses
    P' = P - K H P, then symmetrises; with 4 x 4 float64 matrices this stays positive
    definite in practice and costs half of the Joseph form.
    """
    if x.shape[0] == 0:
        return x.copy(), p.copy()
    innov = z - x[:, :2]
    s_inv, _ = inv2(p[:, :2, :2] + r)
    k = p[:, :, :2] @ s_inv                                   # (k, 4, 2)
    xn = x + np.einsum("kij,kj->ki", k, innov)
    pn = p - k @ p[:, :2, :]
    pn = 0.5 * (pn + np.swapaxes(pn, 1, 2))
    return xn, pn


def init_from_two(z1: np.ndarray, t1: np.ndarray, r1: np.ndarray, z2: np.ndarray,
                  t2: np.ndarray, r2: np.ndarray, q: float) -> tuple[np.ndarray, np.ndarray]:
    """Initialise k tracks from two measured positions each (two-point differencing).

    The state is placed at the second point with velocity (z2 - z1) / (t2 - t1). The
    covariance follows from the two measurement covariances, plus q dt / 3 on the
    velocity: under white acceleration the velocity at t2 differs from the mean velocity
    over [t1, t2] by that variance.
    """
    dt = np.asarray(t2, dtype=np.float64) - np.asarray(t1, dtype=np.float64)
    k = z1.shape[0]
    x = np.empty((k, 4))
    x[:, :2] = z2
    x[:, 2:] = (z2 - z1) / dt[:, None]
    p = np.zeros((k, 4, 4))
    p[:, :2, :2] = r2
    cross = r2 / dt[:, None, None]
    p[:, :2, 2:] = cross
    p[:, 2:, :2] = cross
    p[:, 2:, 2:] = (r1 + r2) / (dt ** 2)[:, None, None]
    p[:, 2, 2] += q * dt / 3.0
    p[:, 3, 3] += q * dt / 3.0
    return x, p


class ConstantVelocityModel:
    """Noise parameters of the constant-velocity model, read from the config.

    Keys: track.meas_sigma_px (px), track.accel_sigma_px (px per frame squared at the
    nominal frame interval) and track.meas_sigma_streak_frac (default 0.1, extra sigma
    along a streak as a fraction of its length).
    """

    def __init__(self, cfg: dict, dt_nominal: float | None = None):
        t = cfg.get("track", {})
        self.meas_sigma_px = float(t.get("meas_sigma_px", 1.0))
        self.accel_sigma_px = float(t.get("accel_sigma_px", 3.0))
        self.streak_frac = float(t.get("meas_sigma_streak_frac", 0.1))
        self.dt_nominal: float | None = None
        self.q = float("nan")
        if dt_nominal is not None:
            self.set_nominal_dt(dt_nominal)

    def set_nominal_dt(self, dt_nominal: float) -> None:
        self.dt_nominal = float(dt_nominal)
        self.q = process_psd(self.accel_sigma_px, self.dt_nominal)

    @property
    def accel_sigma_px_s2(self) -> float:
        """Equivalent acceleration sigma in px/s^2 at the nominal frame interval."""
        if self.dt_nominal is None:
            return float("nan")
        return self.accel_sigma_px / self.dt_nominal ** 2

    def meas_cov(self, length: np.ndarray, theta: np.ndarray) -> np.ndarray:
        return measurement_cov(length, theta, self.meas_sigma_px, self.streak_frac)
