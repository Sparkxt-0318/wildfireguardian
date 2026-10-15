"""Fire versus grid classification of observed deaths.

Topology method: for each protective device, upstream first, look for a
burst of last gasps from meters below that device inside a short window.
If the burst is large relative to the number of still-powered meters below
the device, every death in the burst is labelled 'grid'. Battery tags are
never grid-labelled.

Time-only baseline (no topology): any burst of at least `min_cluster` deaths
anywhere in the network within the window is labelled 'grid'.

Deaths not labelled grid are 'fire' candidates. Single unsupported early
deaths are later relabelled 'other' by the reconstruction step.
"""
from __future__ import annotations

import numpy as np


def _best_window(t, w):
    """Index range [i, j) of the densest window of width w in sorted t."""
    j = np.searchsorted(t, t + w, side="right")
    counts = j - np.arange(len(t))
    i = int(np.argmax(counts))
    return i, int(j[i]), int(counts[i])


def classify_topology(obs, net, cfg, p_deliver_assumed, window_by_kind=None):
    n = len(obs["kind"])
    label = np.array(["unobserved"] * n, dtype=object)
    seen = obs["delivered"] & np.isfinite(obs["t_rep"])
    label[seen] = "fire"
    grid_powered = obs["kind"] != "tag"
    w_default = cfg["window_min"]
    window_by_kind = window_by_kind or {}
    # Members below each device.
    b2rows = {}
    for r, b in enumerate(obs["building"]):
        b2rows.setdefault(int(b), []).append(r)
    order = np.argsort(net.device_depth, kind="stable")
    assigned_dev = -np.ones(n, int)
    for d in order:
        rows = [r for b in net.device_buildings.get(int(d), []) for r in b2rows.get(b, [])]
        if len(rows) < cfg["min_cluster"]:
            continue
        rows = np.array(rows)
        rows = rows[grid_powered[rows]]
        if rows.size < cfg["min_cluster"]:
            continue
        for kind in np.unique(obs["kind"][rows]):
            rk = rows[obs["kind"][rows] == kind]
            w = window_by_kind.get(kind, w_default)
            cand = rk[seen[rk] & (label[rk] == "fire")]
            while cand.size >= cfg["min_cluster"]:
                t = obs["t_rep"][cand]
                o = np.argsort(t)
                ts = t[o]
                i, j, cnt = _best_window(ts, w)
                t0 = ts[i]
                # Meters below the device still powered (not reported dead) just before the burst.
                prior_dead = seen[rk] & (obs["t_rep"][rk] < t0 - w)
                alive = rk.size - int(prior_dead.sum())
                expected = p_deliver_assumed.get(kind, 0.8) * alive
                if cnt >= max(cfg["min_cluster"], cfg["min_fraction_of_expected"] * expected):
                    members = cand[o[i:j]]
                    label[members] = "grid"
                    assigned_dev[members] = d
                    cand = cand[label[cand] == "fire"]
                else:
                    break
    return label, assigned_dev


def classify_time_only(obs, cfg):
    n = len(obs["kind"])
    label = np.array(["unobserved"] * n, dtype=object)
    seen = obs["delivered"] & np.isfinite(obs["t_rep"])
    label[seen] = "fire"
    rows = np.where(seen & (obs["kind"] != "tag"))[0]
    t = obs["t_rep"][rows]
    o = np.argsort(t)
    ts, rs = t[o], rows[o]
    w = cfg["window_min"]
    i = 0
    while i < len(ts):
        j = np.searchsorted(ts, ts[i] + w, side="right")
        if j - i >= cfg["min_cluster"]:
            label[rs[i:j]] = "grid"
            i = j
        else:
            i += 1
    return label
