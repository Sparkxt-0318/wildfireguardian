"""Observation model: which devices die, why, and what the operator sees.

Device types
- meter: grid powered smart meter. Dies when its building loses power (fire
  damage to the building or service drop, an upstream grid outage, or an
  unrelated failure). Sends a last-gasp message delivered with probability
  p_deliver (lower during mass outages, when many meters gasp at once).
  Timestamp = true power-loss time + clock jitter + small latency.
- router: grid powered. The ISP notices loss of the session at the next poll,
  so the reported time is delayed by Uniform(0, poll_interval).
- tag: battery radio beacon (the ESP32 demo). Ignores the grid. Dies when the
  fire reaches it; the receiver records the last heartbeat heard.

Fire death of a building = fire arrival + ignition delay (lognormal), with the
building burning at all with probability p_building_burns. A device whose
power is already lost cannot report a later fire death (censoring).
"""
from __future__ import annotations

import numpy as np

CAUSES = ("fire", "fire_grid", "random_grid", "random_device")


def observe(world_b_xy, T_building, net_out, cfg, rng, t_end):
    """Return a dict of arrays, one row per instrumented device."""
    nb = len(T_building)
    c = cfg
    tn = c["timing_noise_multiplier"]
    burns = rng.random(nb) < c["p_building_burns"]
    ign_delay = rng.lognormal(np.log(max(1e-3, c["ignition_delay_median_min"] * tn)), c["ignition_delay_sigma_log"], nb)
    t_fire_kill = np.where(burns & (T_building <= t_end), T_building + ign_delay, np.inf)
    rate = c["random_device_failure_rate_per_h"]

    rows = []
    for kind, frac in (("meter", c["meter_fraction"]), ("router", c["router_fraction"]), ("tag", c["tag_fraction"])):
        if frac <= 0:
            continue
        sel = np.where(rng.random(nb) < frac)[0]
        for b in sel:
            rows.append((b, kind))
    if not rows:
        return None
    b_idx = np.array([r[0] for r in rows])
    kind = np.array([r[1] for r in rows])
    n = len(rows)
    # Unrelated device failures.
    t_rand = np.where(rng.random(n) < 1 - np.exp(-rate * t_end / 60.0), rng.uniform(0, t_end, n), np.inf)

    t_true = np.full(n, np.inf)
    cause = np.array(["none"] * n, dtype=object)
    grid_dev = -np.ones(n, int)
    is_tag = kind == "tag"
    # Grid powered devices.
    gp = ~is_tag
    tg = net_out["t_building"][b_idx]
    tf = t_fire_kill[b_idx]
    stack = np.vstack([tf, tg, t_rand])
    k = np.argmin(stack, axis=0)
    tmin = stack[k, np.arange(n)]
    gcause = net_out["cause"][np.maximum(net_out["device_building"][b_idx], 0)]
    lab = np.where(k == 0, "fire", np.where(k == 1, gcause, "random_device"))
    t_true[gp] = tmin[gp]
    cause[gp] = lab[gp]
    grid_dev[gp] = np.where(k[gp] == 1, net_out["device_building"][b_idx][gp], -1)
    # Tags: fire only (plus random failure).
    if is_tag.any():
        tc = c["tag"]
        Tb = T_building[b_idx][is_tag]
        dies = (rng.random(is_tag.sum()) < tc["p_die_given_fire"]) & (Tb <= t_end)
        tfire = np.where(dies, Tb + rng.uniform(*tc["death_delay_min"], is_tag.sum()) * tn, np.inf)
        tr = t_rand[is_tag]
        t_true[is_tag] = np.minimum(tfire, tr)
        cause[is_tag] = np.where(tfire <= tr, "fire", "random_device")
    dead = t_true <= t_end
    cause[~dead] = "none"
    t_true[~dead] = np.inf

    # Reporting.
    t_rep = np.full(n, np.nan)
    delivered = np.zeros(n, bool)
    m = kind == "meter"
    if m.any():
        mc = c["meter"]
        p = np.full(n, mc["p_deliver"])
        # Mass outage congestion: devices on a grid event with many simultaneous members.
        if (grid_dev >= 0).any():
            ids, counts = np.unique(grid_dev[grid_dev >= 0], return_counts=True)
            big = set(ids[counts >= mc["mass_outage_size"]].tolist())
            mass = np.array([g in big for g in grid_dev])
            p = np.where(mass, p * mc["mass_outage_delivery_factor"], p)
        dm = m & dead
        delivered[dm] = rng.random(dm.sum()) < p[dm]
        jit = rng.normal(0, mc["clock_jitter_sd_min"] * tn, n) + mc["latency_min"]
        t_rep[dm & delivered] = (t_true + jit)[dm & delivered]
    r = kind == "router"
    if r.any():
        rc = c["router"]
        dr = r & dead
        delivered[dr] = rng.random(dr.sum()) < rc["p_deliver"]
        t_rep[dr & delivered] = (t_true + rng.uniform(0, rc["poll_interval_min"], n))[dr & delivered]
    if is_tag.any():
        tc = c["tag"]
        hb = tc["heartbeat_s"] / 60.0
        dt = is_tag & dead
        # Last heartbeat received before death: phase offset plus geometric run of missed beats.
        phase = rng.uniform(0, hb, n)
        missed = rng.geometric(tc["p_heartbeat"], n) - 1
        t_rep[dt] = (t_true - phase - missed * hb)[dt]
        delivered[dt] = True
    return {
        "building": b_idx, "kind": kind, "x": world_b_xy[b_idx, 0], "y": world_b_xy[b_idx, 1],
        "t_true": t_true, "cause": cause, "dead": dead, "delivered": delivered, "t_rep": t_rep,
        "grid_device": grid_dev, "T_fire_building": T_building[b_idx],
        "building_burns": burns[b_idx],
    }
