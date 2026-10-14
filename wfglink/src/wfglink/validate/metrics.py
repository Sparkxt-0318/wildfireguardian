"""Validation metrics against synthetic ground truth: detection, tracking, velocity and counts.

Ground truth follows the shared schema (truth_particles.parquet, truth_frames.parquet,
truth_gate.parquet, meta.json). Only rows with kind == "ember", visible == True and
in_large_region == False are detectable truth. Embers that exist but are not detectable
(too faint, mostly outside the exposure, or inside a flame or headlight region) are
"don't care": an estimate matched to one is neither a true nor a false positive.
Every other kind (spark, light, headlight) is a distractor, so an estimate on it is a
false positive.

Detection: per frame, Hungarian matching within each truth's radius
(`wfglink.validate.match`), accumulated over frames into TP, FP, FN, precision, recall,
F1 and the localisation RMSE of matched pairs.

Tracking: CLEAR MOT. Per frame, a truth object that was matched to hypothesis h in the
previous frame keeps h if h is still within its radius (correspondence persistence);
the remaining objects are matched by the Hungarian method. A match to a hypothesis other
than the object's last matched one is an ID switch.
MOTA = 1 - (FN + FP + IDSW) / GT; MOTP is the mean matched distance in px. Mostly
tracked: matched in at least 80% of the frames an object is detectable; mostly lost:
below 20%; partially tracked: the rest (Li, Huang and Nevatia 2009, as in py-motmetrics).

Velocity: estimated per-point velocities are matched to truth by position, frame by
frame, and compared with the truth's mean ember velocity over the exposure (u, v): the
median and 90th percentile of the absolute relative speed error, the median signed
relative error (bias), the median angular error in degrees and the RMSE of u and v.

Counts: relative error of a count or flux, whether the truth lies in a confidence
interval, true gate crossings from truth_gate (embers visible in both bracketing frames,
or bridged over flicker dropouts that a coasting tracker spans) and the Clopper-Pearson
interval for a coverage fraction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.stats import beta

from wfglink.measure.gate import particle_number_flux
from wfglink.validate.match import match_points, match_radius

EMBER = "ember"


# Truth tables ----------------------------------------------------------------------------
def load_truth(clip_dir: str | Path) -> dict:
    """Read truth_particles, truth_frames, truth_gate (when present) and meta.json of a clip."""
    import pandas as pd

    d = Path(clip_dir)
    out: dict = {"particles": pd.read_parquet(d / "truth_particles.parquet")}
    for key, name in (("frames", "truth_frames.parquet"), ("gate", "truth_gate.parquet")):
        p = d / name
        out[key] = pd.read_parquet(p) if p.exists() else None
    meta = d / "meta.json"
    out["meta"] = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    return out


def detectable_mask(particles) -> np.ndarray:
    """Rows that count as detectable truth: visible embers outside flame or headlight regions."""
    return ((particles["kind"].to_numpy() == EMBER)
            & particles["visible"].to_numpy(dtype=bool)
            & ~particles["in_large_region"].to_numpy(dtype=bool))


def dont_care_mask(particles) -> np.ndarray:
    """Embers that exist in the frame but are not detectable truth."""
    return (particles["kind"].to_numpy() == EMBER) & ~detectable_mask(particles)


def _by_frame(df, cols: list[str]) -> dict[int, tuple[np.ndarray, ...]]:
    if df is None or len(df) == 0:
        return {}
    frames = df["frame"].to_numpy()
    arrs = [df[c].to_numpy() for c in cols]
    out = {}
    for f, idx in _group_indices(frames).items():
        out[f] = tuple(a[idx] for a in arrs)
    return out


def _group_indices(keys: np.ndarray) -> dict[int, np.ndarray]:
    order = np.argsort(keys, kind="stable")
    k = keys[order]
    uniq, starts = np.unique(k, return_index=True)
    ends = np.r_[starts[1:], k.size]
    return {int(u): order[a:b] for u, a, b in zip(uniq.tolist(), starts.tolist(), ends.tolist())}


def _truth_frames(truth, cfg: dict | None, extra: tuple[str, ...] = ()):
    """Per-frame detectable and don't-care truth: (ids, x, y, radius, *extra)."""
    det = truth[detectable_mask(truth)]
    dc = truth[dont_care_mask(truth)]
    out = []
    for df in (det, dc):
        df = df.assign(_r=match_radius(df["streak_length_px"].to_numpy(), cfg))
        out.append(_by_frame(df, ["particle_id", "x_mid", "y_mid", "_r", *extra]))
    return out


def _xy(a, b) -> np.ndarray:
    return np.column_stack((np.asarray(a, np.float64), np.asarray(b, np.float64)))


def _dont_care_hits(xy: np.ndarray, dc: tuple | None) -> np.ndarray:
    """Which estimates fall within the radius of a don't-care truth (one to one)."""
    hit = np.zeros(xy.shape[0], dtype=bool)
    if dc is None or xy.shape[0] == 0:
        return hit
    _, di, _ = match_points(_xy(dc[1], dc[2]), xy, dc[3])
    hit[di] = True
    return hit


# Detection -------------------------------------------------------------------------------
@dataclass
class DetectionAccumulator:
    """TP, FP, FN and squared localisation errors accumulated over frames."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    ignored: int = 0
    sq_err: float = 0.0
    n_frames: int = 0
    per_frame: list = field(default_factory=list)

    def add(self, gt_xy: np.ndarray, gt_radius: np.ndarray, det_xy: np.ndarray,
            dc_xy: np.ndarray | None = None, dc_radius: np.ndarray | None = None,
            frame: int | None = None) -> None:
        gt_xy = np.asarray(gt_xy, np.float64).reshape(-1, 2)
        det_xy = np.asarray(det_xy, np.float64).reshape(-1, 2)
        gi, di, dist = match_points(gt_xy, det_xy, gt_radius)
        tp = gi.size
        free = np.ones(det_xy.shape[0], dtype=bool)
        free[di] = False
        ign = 0
        if dc_xy is not None and np.asarray(dc_xy).size and free.any():
            fi = np.flatnonzero(free)
            _, dj, _ = match_points(np.asarray(dc_xy, np.float64).reshape(-1, 2), det_xy[fi],
                                    dc_radius)
            ign = dj.size
        fp = int(free.sum()) - ign
        fn = gt_xy.shape[0] - tp
        self.tp += tp
        self.fp += fp
        self.fn += fn
        self.ignored += ign
        self.sq_err += float(np.sum(dist ** 2))
        self.n_frames += 1
        self.per_frame.append((frame, tp, fp, fn, ign))

    def summary(self) -> dict[str, float]:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else float("nan")
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else float("nan")
        f1 = 2 * p * r / (p + r) if (p + r) and np.isfinite(p) and np.isfinite(r) else float("nan")
        rmse = float(np.sqrt(self.sq_err / self.tp)) if self.tp else float("nan")
        return {"tp": self.tp, "fp": self.fp, "fn": self.fn, "ignored": self.ignored,
                "precision": p, "recall": r, "f1": f1, "loc_rmse_px": rmse,
                "n_frames": self.n_frames}


def detection_metrics(truth, detections, cfg: dict | None = None, frames=None,
                      x_col: str = "x", y_col: str = "y", ignore_dont_care: bool = True
                      ) -> dict[str, float]:
    """Detection metrics over all frames present in either table (or the given frames).

    `detections` is a DataFrame with frame, x and y columns (one row per detection).
    """
    gt_f, dc_f = _truth_frames(truth, cfg)
    det_f = _by_frame(detections, [x_col, y_col])
    if frames is None:
        frames = sorted(set(gt_f) | set(det_f) | set(int(f) for f in truth["frame"].unique()))
    acc = DetectionAccumulator()
    e2 = np.zeros((0, 2))
    for f in frames:
        f = int(f)
        g = gt_f.get(f)
        gxy = _xy(g[1], g[2]) if g else e2
        grad = g[3] if g else np.zeros(0)
        d = det_f.get(f)
        dxy = _xy(d[0], d[1]) if d else e2
        dc = dc_f.get(f) if ignore_dont_care else None
        acc.add(gxy, grad, dxy, _xy(dc[1], dc[2]) if dc else None, dc[3] if dc else None, f)
    return acc.summary()


# Tracking (CLEAR MOT) --------------------------------------------------------------------
def tracking_metrics(truth, track_points, cfg: dict | None = None, x_col: str = "x",
                     y_col: str = "y", id_col: str = "track_id",
                     ignore_dont_care: bool = True, frames=None) -> dict[str, float]:
    """CLEAR MOT metrics of track points (frame, track_id, x, y) against detectable truth.

    `frames` restricts the evaluation to the frames the tracker processed (for example
    without duplicated frames the pipeline dropped); by default every frame present in
    the truth or the track points is scored, so a skipped frame counts all its truth as
    misses.
    """
    gt_f, dc_f = _truth_frames(truth, cfg)
    hyp_f = _by_frame(track_points, [id_col, x_col, y_col])
    if frames is None:
        frames = sorted(set(gt_f) | set(hyp_f))
    else:
        frames = sorted({int(f) for f in frames})
    prev: dict[int, int] = {}
    last: dict[int, int] = {}
    present: dict[int, int] = {}
    matched: dict[int, int] = {}
    fp = fn = idsw = n_match = n_gt = ignored = 0
    dist_sum = 0.0
    e2 = np.zeros((0, 2))
    for f in frames:
        g = gt_f.get(f)
        h = hyp_f.get(f)
        g_ids = g[0].astype(np.int64) if g else np.zeros(0, np.int64)
        g_xy = _xy(g[1], g[2]) if g else e2
        g_rad = g[3] if g else np.zeros(0)
        h_ids = h[0].astype(np.int64) if h else np.zeros(0, np.int64)
        h_xy = _xy(h[1], h[2]) if h else e2
        ok = np.isfinite(h_xy).all(axis=1)
        h_ids, h_xy = h_ids[ok], h_xy[ok]
        n_gt += g_ids.size
        for gid in g_ids.tolist():
            present[gid] = present.get(gid, 0) + 1
        g_used = np.zeros(g_ids.size, dtype=bool)
        h_used = np.zeros(h_ids.size, dtype=bool)
        pairs: list[tuple[int, int, float]] = []
        if prev and g_ids.size and h_ids.size:
            h_index = {hid: k for k, hid in enumerate(h_ids.tolist())}
            for gi, gid in enumerate(g_ids.tolist()):
                hid = prev.get(gid)
                hj = h_index.get(hid) if hid is not None else None
                if hj is None or h_used[hj]:
                    continue
                dist = float(np.hypot(*(g_xy[gi] - h_xy[hj])))
                if dist <= g_rad[gi]:
                    pairs.append((gi, hj, dist))
                    g_used[gi] = h_used[hj] = True
        rg, rh = np.flatnonzero(~g_used), np.flatnonzero(~h_used)
        gi2, hj2, d2 = match_points(g_xy[rg], h_xy[rh], g_rad[rg])
        for a, b, dd in zip(rg[gi2].tolist(), rh[hj2].tolist(), d2.tolist()):
            gid, hid = int(g_ids[a]), int(h_ids[b])
            if gid in last and last[gid] != hid:
                idsw += 1
            pairs.append((a, b, dd))
            g_used[a] = h_used[b] = True
        cur = {}
        for a, b, dd in pairs:
            gid = int(g_ids[a])
            cur[gid] = int(h_ids[b])
            matched[gid] = matched.get(gid, 0) + 1
            dist_sum += dd
        prev = cur
        last.update(cur)
        n_match += len(pairs)
        fn += int((~g_used).sum())
        free = ~h_used
        if ignore_dont_care and free.any():
            hit = _dont_care_hits(h_xy[free], dc_f.get(f))
            ignored += int(hit.sum())
            fp += int(free.sum() - hit.sum())
        else:
            fp += int(free.sum())
    ratios = np.array([matched.get(g, 0) / n for g, n in present.items()], dtype=np.float64)
    nan = float("nan")
    return {
        "mota": 1.0 - (fn + fp + idsw) / n_gt if n_gt else nan,
        "motp_px": dist_sum / n_match if n_match else nan,
        "id_switches": idsw, "fp": fp, "fn": fn, "gt": n_gt, "matches": n_match,
        "ignored": ignored,
        "mostly_tracked": int(np.sum(ratios >= 0.8)), "mostly_lost": int(np.sum(ratios < 0.2)),
        "partially_tracked": int(np.sum((ratios >= 0.2) & (ratios < 0.8))),
        "n_truth_objects": len(present),
        "n_hypotheses": int(track_points[id_col].nunique()) if len(track_points) else 0,
    }


# Velocity --------------------------------------------------------------------------------
def velocity_metrics(truth, est_points, cfg: dict | None = None, vx_col: str | None = "vx_poly",
                     vy_col: str | None = "vy_poly", speed_col: str | None = None,
                     x_col: str = "x", y_col: str = "y", min_true_speed_px_s: float | None = None
                     ) -> dict[str, float]:
    """Errors of per-point velocity estimates against the truth matched by position.

    The speed comes from `speed_col` when given (for example streak speed), otherwise
    from (vx_col, vy_col). Angular and component errors need vx_col and vy_col. Truth
    slower than min_true_speed_px_s (validate.min_true_speed_px_s, default 1.0) is left
    out of relative and angular errors.
    """
    vmin = (float((cfg or {}).get("validate", {}).get("min_true_speed_px_s", 1.0))
            if min_true_speed_px_s is None else float(min_true_speed_px_s))
    gt_f, _ = _truth_frames(truth, cfg, extra=("u", "v"))
    n_est = len(est_points)

    def col(name):
        if name is None:
            return np.full(n_est, np.nan)
        return est_points[name].to_numpy(dtype=np.float64)

    vx_all, vy_all = col(vx_col), col(vy_col)
    sp_all = col(speed_col) if speed_col else np.hypot(vx_all, vy_all)
    xy_all = _xy(est_points[x_col], est_points[y_col]) if n_est else np.zeros((0, 2))
    good = np.isfinite(xy_all).all(axis=1) & np.isfinite(sp_all)
    frames = est_points["frame"].to_numpy() if n_est else np.zeros(0, np.int64)
    true_u, true_v, sel = [], [], []
    for f, idx in _group_indices(frames[good]).items():
        g = gt_f.get(f)
        if not g:
            continue
        rows = np.flatnonzero(good)[idx]
        gi, di, _ = match_points(_xy(g[1], g[2]), xy_all[rows], g[3])
        true_u.append(g[4][gi])
        true_v.append(g[5][gi])
        sel.append(rows[di])
    nan = float("nan")
    if not true_u or sum(a.size for a in true_u) == 0:
        return {"n": 0, "n_rel": 0, "median_rel_speed_err": nan, "p90_rel_speed_err": nan,
                "median_signed_rel_speed_err": nan, "median_angle_err_deg": nan,
                "rmse_u": nan, "rmse_v": nan}
    tu, tv = np.concatenate(true_u).astype(float), np.concatenate(true_v).astype(float)
    j = np.concatenate(sel)
    ex, ey, es = vx_all[j], vy_all[j], sp_all[j]
    ts = np.hypot(tu, tv)
    fast = ts >= vmin
    rel = (es[fast] - ts[fast]) / ts[fast]
    ang_ok = fast & np.isfinite(ex) & np.isfinite(ey)
    ang = np.degrees(np.abs(np.angle(np.exp(1j * (np.arctan2(ey[ang_ok], ex[ang_ok])
                                                  - np.arctan2(tv[ang_ok], tu[ang_ok]))))))
    comp = np.isfinite(ex) & np.isfinite(ey)
    return {
        "n": int(ts.size), "n_rel": int(fast.sum()),
        "median_rel_speed_err": float(np.median(np.abs(rel))) if rel.size else nan,
        "p90_rel_speed_err": float(np.percentile(np.abs(rel), 90)) if rel.size else nan,
        "median_signed_rel_speed_err": float(np.median(rel)) if rel.size else nan,
        "median_angle_err_deg": float(np.median(ang)) if ang.size else nan,
        "rmse_u": float(np.sqrt(np.mean((ex[comp] - tu[comp]) ** 2))) if comp.any() else nan,
        "rmse_v": float(np.sqrt(np.mean((ey[comp] - tv[comp]) ** 2))) if comp.any() else nan,
    }


# Counts ----------------------------------------------------------------------------------
def bridged_crossings(truth_gate, truth_particles, max_gap_frames: int) -> np.ndarray:
    """Crossings a tracker that coasts over up to max_gap_frames missed frames can see.

    A crossing between frames frame_before and frame_after is bridged when the particle
    is detectable truth (visible, outside flame or headlight regions) in some frame
    a <= frame_before and some frame b >= frame_after with b - a - 1 <= max_gap_frames,
    or when it is visible in both bracketing frames (visible_both). With
    max_gap_frames = 0 this is visible_both alone.
    """
    vb = truth_gate["visible_both"].to_numpy(dtype=bool)
    if max_gap_frames <= 0 or len(truth_gate) == 0:
        return vb
    det = truth_particles[detectable_mask(truth_particles)]
    pid = truth_gate["particle_id"].to_numpy(dtype=np.int64)
    fb = truth_gate["frame_before"].to_numpy(dtype=np.int64)
    fa = truth_gate["frame_after"].to_numpy(dtype=np.int64)
    if len(det) == 0:
        return vb
    dp = det["particle_id"].to_numpy(dtype=np.int64)
    df_ = det["frame"].to_numpy(dtype=np.int64)
    span = int(max(df_.max(), fa.max(), 0)) + 2
    keys = np.unique(dp * span + df_)              # sorted (particle, frame) keys
    kb = pid * span + fb
    ka = pid * span + fa
    ib = np.searchsorted(keys, kb, side="right") - 1
    ia = np.searchsorted(keys, ka, side="left")
    has_b = ib >= 0
    has_a = ia < keys.size
    kb_hit = np.where(has_b, keys[np.clip(ib, 0, keys.size - 1)], -1)
    ka_hit = np.where(has_a, keys[np.clip(ia, 0, keys.size - 1)], -1)
    has_b &= kb_hit // span == pid
    has_a &= ka_hit // span == pid
    gap = (ka_hit % span) - (kb_hit % span) - 1
    return vb | (has_b & has_a & (gap <= max_gap_frames))


def true_gate_counts(truth_gate, truth_particles=None, gate: str | None = None,
                     t0: float | None = None, t1: float | None = None,
                     require_visible_both: bool = True, max_gap_frames: int = 0,
                     frame_range: tuple[int, int] | None = None) -> dict[str, int]:
    """True crossings of one gate: gross, net and per direction.

    Only embers count when truth_particles is given (kind looked up by particle_id).
    With require_visible_both, a crossing counts when it is visible in both bracketing
    frames or, with max_gap_frames > 0 and truth_particles given, when a tracker coasting
    over that many missed frames could bridge it (`bridged_crossings`). Flicker dropouts
    make visible_both alone far too strict: with 15% of frames dropped, a working counter
    reads about 35% above it.

    Selection in time: t0 <= t < t1 on the truth crossing time, which is on the clock of
    the exposure midpoints. Or, independent of any clock, frame_range = (f0, f1): only
    crossings with f0 <= frame_before and frame_after <= f1, the crossings a run over
    frames f0 to f1 can see.
    """
    g = truth_gate
    keep = np.ones(len(g), dtype=bool)
    if gate is not None:
        keep &= g["gate"].to_numpy() == gate
    if require_visible_both:
        if max_gap_frames > 0 and truth_particles is not None:
            keep &= bridged_crossings(g, truth_particles, int(max_gap_frames))
        else:
            keep &= g["visible_both"].to_numpy(dtype=bool)
    t = g["t"].to_numpy(dtype=np.float64)
    if t0 is not None:
        keep &= t >= t0
    if t1 is not None:
        keep &= t < t1
    if frame_range is not None:
        keep &= g["frame_before"].to_numpy() >= int(frame_range[0])
        keep &= g["frame_after"].to_numpy() <= int(frame_range[1])
    if truth_particles is not None:
        embers = np.unique(truth_particles.loc[truth_particles["kind"] == EMBER, "particle_id"])
        keep &= np.isin(g["particle_id"].to_numpy(), embers)
    d = g["direction"].to_numpy()[keep].astype(np.int64)
    pos = int(np.sum(d > 0))
    neg = int(np.sum(d < 0))
    return {"gross": pos + neg, "net": pos - neg, "positive": pos, "negative": neg}


def count_metrics(estimate: float, truth: float, ci_low: float | None = None,
                  ci_high: float | None = None) -> dict[str, float]:
    """Relative error of a count, rate or flux and whether the truth lies in [ci_low, ci_high]."""
    nan = float("nan")
    rel = (estimate - truth) / truth if truth else (0.0 if estimate == truth else nan)
    out = {"estimate": float(estimate), "truth": float(truth), "abs_err": float(estimate - truth),
           "rel_err": float(rel)}
    if ci_low is not None and ci_high is not None:
        out["in_ci"] = bool(ci_low <= truth <= ci_high)
    return out


def gate_metrics(counter, truth_gate, truth_particles=None, t0: float | None = None,
                 t1: float | None = None, cfg: dict | None = None, seed: int = 0,
                 ci: float = 0.95, frame_range: tuple[int, int] | None = None,
                 max_gap_frames: int | None = None) -> dict:
    """Compare a `wfglink.measure.gate.GateCounter` with the true crossings of its gate.

    Over [t0, t1) (default: the counter's observed span) it reports, for the gross and
    net Cumulative Particle Count (gate) and the gross Particle Number Flux (projected),
    the relative error and whether the truth lies in the interval. The interval is the
    union of the Garwood and moving-block bootstrap intervals (`GateCounter.rate_interval`).

    Clocks: the counter's times are the frame timestamps given to the tracker (the video
    PTS, which is the exposure start), while truth crossing times are on the exposure
    midpoint clock, half an exposure later. Selecting the truth by the same t0, t1 then
    drops true crossings near the end that the counter legitimately has. Pass
    frame_range = (first processed frame, last processed frame) to select the truth by
    its bracketing frames instead (exact for whole-run comparisons).

    Truth visibility: crossings visible in both bracketing frames, or bridged by a
    tracker coasting over max_gap_frames missed frames (default track.max_coast from cfg,
    else 3), which needs truth_particles. The rule used is reported as "truth_rule".
    """
    if (t0 is None and counter.t_first is None) or (t1 is None and counter.t_last is None):
        raise ValueError("gate_metrics needs t0 and t1 or a counter that observed frames")
    t0 = counter.t_first if t0 is None else float(t0)
    t1 = counter.t_last if t1 is None else float(t1)
    if max_gap_frames is None:
        max_gap_frames = int((cfg or {}).get("track", {}).get("max_coast", 3))
    gap = int(max_gap_frames) if truth_particles is not None else 0
    est = counter.counts(t0, t1)
    if frame_range is None:
        true = true_gate_counts(truth_gate, truth_particles, counter.gate.name, t0, t1,
                                max_gap_frames=gap)
    else:
        true = true_gate_counts(truth_gate, truth_particles, counter.gate.name,
                                max_gap_frames=gap, frame_range=frame_range)
    dur = t1 - t0
    rg = counter.rate_interval(t0, t1, net=False, cfg=cfg, seed=seed, ci=ci)
    rn = counter.rate_interval(t0, t1, net=True, cfg=cfg, seed=seed, ci=ci)
    length = counter.gate.length
    pe = particle_number_flux(est["gross"], length, dur)
    pt = particle_number_flux(true["gross"], length, dur)
    scale = 1.0 / (length / 100.0)
    return {
        "duration_s": dur, "estimate": est, "truth": true,
        "cpc_gross": count_metrics(est["gross"], true["gross"], rg["lo"] * dur, rg["hi"] * dur),
        "cpc_net": count_metrics(est["net"], true["net"], rn["lo"] * dur, rn["hi"] * dur),
        "pnf": count_metrics(pe.value, pt.value, rg["lo"] * scale, rg["hi"] * scale),
        "pnf_unit": pe.unit,
        "truth_rule": f"bridged (max gap {gap} frames)" if gap > 0 else "visible_both",
    }


def clopper_pearson(k: int, n: int, ci: float = 0.95) -> tuple[float, float]:
    """Exact binomial (Clopper-Pearson) interval for k successes out of n."""
    if n <= 0:
        return float("nan"), float("nan")
    alpha = 1.0 - ci
    lo = 0.0 if k <= 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k >= n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def coverage(in_ci, ci: float = 0.95) -> dict[str, float]:
    """Coverage fraction of a set of intervals, with its Clopper-Pearson interval."""
    flags = np.asarray(in_ci, dtype=bool)
    k, n = int(flags.sum()), int(flags.size)
    lo, hi = clopper_pearson(k, n, ci)
    return {"k": k, "n": n, "fraction": k / n if n else float("nan"), "lo": lo, "hi": hi}
