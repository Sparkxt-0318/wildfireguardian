"""Phase 2 receive side: radio links, gateways, multi-hop relaying, store-and-forward.

Radio model (per link, fixed for a deployment):
    PL(d) = alpha + 10 n log10(d / 1 m) + X,   X ~ N(0, sigma) per link
    (alpha, n, sigma from published forest LoRa/BLE fits; see docs/PARAMETERS_PHASE2.md)
    link up if TX + G_tx + G_rx - PL >= sensitivity + fade_margin
Separate (alpha, n, sigma) for tag-to-tag (both near the ground) and
tag-to-gateway (gateway antenna elevated). A free-space-plus-Weissberger
vegetation form is kept as an alternative when alpha is not given.

Reception (1 min time steps):
- star: a tag's heartbeat is received only over a direct link to a live gateway.
- mesh: heartbeats relay over live tags (any hop count up to max_hops) to a live gateway.
- mesh_sf: mesh plus store-and-forward. When a tag dies, its live neighbours
  (witnesses) record its last-heard time. That record spreads epidemically
  through the live part of the network and is delivered when any holder is
  connected to a live gateway, possibly much later.
A death is "observed" only if a live listener notices the silence. If every
listener died first or was cut off, the death is unobserved (censored).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree


def path_loss_db(d, n, cfg, veg_fraction, alpha=None):
    """Log-distance path loss. With alpha given, PL = alpha + 10 n log10(d) (an empirical fit in which
    vegetation and antenna effects are already included); otherwise free space at 1 m plus 10 n log10(d)
    plus an optional Weissberger-type vegetation term."""
    d = np.maximum(d, 1.0)
    if alpha is not None:
        return alpha + 10 * n * np.log10(d)
    pl0 = 20 * math.log10(4 * math.pi / (299_792_458.0 / (cfg["freq_mhz"] * 1e6)))  # free space at 1 m
    pl = pl0 + 10 * n * np.log10(d)
    if cfg.get("veg_a_db", 0) > 0 and veg_fraction > 0:
        dv = np.minimum(veg_fraction * d, cfg["veg_dmax_m"])
        pl = pl + cfg["veg_a_db"] * (cfg["freq_mhz"] / 1000.0) ** 0.284 * dv ** 0.588
    return pl


def link_budget_db(cfg, rx_gain):
    return cfg["tx_dbm"] + cfg["tag_gain_dbi"] + rx_gain - cfg["sensitivity_dbm"] - cfg["fade_margin_db"]


def max_range_m(cfg, n, rx_gain, veg_fraction, sigma, alpha=None):
    """Largest distance at which a +3 sigma lucky link could still close (search radius)."""
    budget = link_budget_db(cfg, rx_gain) + 3 * sigma
    d = np.logspace(0, 4.5, 400)
    ok = path_loss_db(d, n, cfg, veg_fraction, alpha) <= budget
    return float(d[ok].max()) if ok.any() else 1.0


def build_links(tag_xy, gw_xy, cfg, rng):
    """Return (tag-tag adjacency CSR, tag-gateway boolean matrix [n_tag, n_gw])."""
    nt = len(tag_xy)
    tt = sparse.csr_matrix((nt, nt), dtype=bool)
    if cfg["mesh_capable"] and nt > 1:
        r = max_range_m(cfg, cfg["n_tag_tag"], cfg["tag_gain_dbi"], cfg["veg_fraction"], cfg["sigma_tag_tag_db"],
                        cfg.get("alpha_tag_tag_db"))
        pairs = cKDTree(tag_xy).query_pairs(r, output_type="ndarray")
        if len(pairs):
            d = np.hypot(*(tag_xy[pairs[:, 0]] - tag_xy[pairs[:, 1]]).T)
            pl = (path_loss_db(d, cfg["n_tag_tag"], cfg, cfg["veg_fraction"], cfg.get("alpha_tag_tag_db"))
                  + rng.normal(0, cfg["sigma_tag_tag_db"], len(d)))
            up = pl <= link_budget_db(cfg, cfg["tag_gain_dbi"])
            a, b = pairs[up, 0], pairs[up, 1]
            tt = sparse.coo_matrix((np.ones(2 * len(a), bool), (np.r_[a, b], np.r_[b, a])), shape=(nt, nt)).tocsr()
    tg = np.zeros((nt, len(gw_xy)), bool)
    if len(gw_xy):
        d = np.hypot(tag_xy[:, None, 0] - gw_xy[None, :, 0], tag_xy[:, None, 1] - gw_xy[None, :, 1])
        pl = (path_loss_db(d, cfg["n_tag_gw"], cfg, cfg["veg_fraction"], cfg.get("alpha_tag_gw_db"))
              + rng.normal(0, cfg["sigma_tag_gw_db"], d.shape))
        tg = pl <= link_budget_db(cfg, cfg["gw_gain_dbi"])
    return tt, tg


def p_link_gw(tag_xy, site_xy, cfg):
    """Expected probability that each tag has a direct link to each candidate site (no draw)."""
    from scipy.stats import norm
    d = np.hypot(tag_xy[:, None, 0] - site_xy[None, :, 0], tag_xy[:, None, 1] - site_xy[None, :, 1])
    pl = path_loss_db(d, cfg["n_tag_gw"], cfg, cfg["veg_fraction"], cfg.get("alpha_tag_gw_db"))
    return norm.cdf((link_budget_db(cfg, cfg["gw_gain_dbi"]) - pl) / cfg["sigma_tag_gw_db"])


def greedy_gateways(tag_xy, site_xy, cfg, k, weight=None, tt=None):
    """Choose k sites greedily to maximise expected tags covered (directly or, for mesh, via hop reach).

    For mesh modes, a tag counts as covered if any tag within its mesh component of
    hop distance <= max_hops reaches the site; approximated by smoothing coverage
    over the tag-tag graph.
    """
    P = p_link_gw(tag_xy, site_xy, cfg)
    if tt is not None and cfg["mesh_capable"]:
        # Hop reach: tag i is covered by site s if some tag j within max_hops of i links to s.
        hops = dijkstra(tt.astype(float), directed=False, unweighted=True, limit=cfg["max_hops"])
        reach = np.isfinite(hops)
        P = 1 - np.exp(reach.astype(float) @ np.log(np.clip(1 - P, 1e-12, 1)))
    w = np.ones(len(tag_xy)) if weight is None else weight
    chosen = []
    miss = np.ones(len(tag_xy))
    for _ in range(min(k, len(site_xy))):
        gain = (w[:, None] * miss[:, None] * P).sum(0)
        gain[chosen] = -1
        s = int(np.argmax(gain))
        chosen.append(s)
        miss = miss * (1 - P[:, s])
    return np.array(chosen, int)


def simulate_reception(tag_t_death, gw_t_death, tt, tg, cfg, t_end, rng):
    """Observed death time (or nan) and delivery time for each tag, plus last-known-alive times.

    tag_t_death: true time each tag stops transmitting (inf if it survives).
    gw_t_death: time each gateway stops working (inf if it survives).
    Returns dict with arrays over tags: obs_time (reported death time, nan if
    unobserved), delivered_at (time the operator learns of it), last_alive_known.
    """
    nt, ng = tg.shape
    mode = cfg["mode"]
    dt = cfg["step_min"]
    hb = cfg["heartbeat_s"] / 60.0
    timeout = cfg["timeout_beats"] * hb
    times = np.arange(0.0, t_end + dt, dt)
    obs_time = np.full(nt, np.nan)
    delivered = np.full(nt, np.nan)
    last_alive_known = np.full(nt, -np.inf)
    # Last heartbeat actually sent before death (heartbeat phase).
    phase = rng.uniform(0, hb, nt)
    t_last_beat = tag_t_death - phase
    know = np.zeros((nt, nt), bool)       # know[i, j]: node j holds the record of tag i's death
    pending = np.zeros(nt, bool)          # death noticed, record not yet delivered
    noticed = np.zeros(nt, bool)
    tt = tt.tocsr()
    max_hops = cfg["max_hops"]
    for t in times:
        alive_t = tag_t_death > t
        alive_g = gw_t_death > t
        # Which tags are connected to a live gateway now?
        direct = (tg[:, alive_g].any(1) if ng else np.zeros(nt, bool)) & alive_t
        if mode == "star":
            conn = direct
            comp_has_gw = None
        else:
            sub = tt[alive_t][:, alive_t]
            idx = np.where(alive_t)[0]
            if max_hops >= 50:
                ncomp, lab = connected_components(sub, directed=False)
                has = np.zeros(ncomp, bool)
                has[np.unique(lab[direct[idx]])] = True
                conn = np.zeros(nt, bool)
                conn[idx] = has[lab]
            else:
                src = np.where(direct[idx])[0]
                conn = np.zeros(nt, bool)
                if len(src):
                    h = dijkstra(sub.astype(float), directed=False, unweighted=True, indices=src,
                                      limit=max_hops - 1, min_only=True)
                    conn[idx[np.isfinite(h)]] = True
            if mode == "mesh_sf":
                comp_lab = np.full(nt, -1)
                ncomp, lab = connected_components(sub, directed=False)
                comp_lab[idx] = lab
        last_alive_known[conn] = t
        # Newly silent tags: noticed by live listeners at t_last_beat + timeout.
        newly = (~noticed) & (t_last_beat + timeout <= t) & np.isfinite(tag_t_death)
        for i in np.where(newly)[0]:
            noticed[i] = True
            t_notice = t_last_beat[i] + timeout
            gw_listen = tg[i] & (gw_t_death > t_notice)
            if mode == "star":
                if gw_listen.any():
                    obs_time[i] = t_last_beat[i]
                    delivered[i] = t
                continue
            nb = tt.indices[tt.indptr[i]:tt.indptr[i + 1]]
            nb = nb[tag_t_death[nb] > t_notice]
            if gw_listen.any() or conn[nb].any():
                obs_time[i] = t_last_beat[i]
                delivered[i] = t
            elif mode == "mesh_sf" and len(nb):
                know[i, nb] = True
                pending[i] = True
        if mode == "mesh_sf" and pending.any():
            alive_idx = np.where(alive_t)[0]
            for i in np.where(pending)[0]:
                holders = np.where(know[i] & alive_t)[0]
                if not len(holders):
                    pending[i] = False  # every holder died: record lost
                    continue
                comps = np.unique(comp_lab[holders])
                members = alive_idx[np.isin(comp_lab[alive_idx], comps)]
                know[i, members] = True
                if conn[members].any():
                    obs_time[i] = t_last_beat[i]
                    delivered[i] = t
                    pending[i] = False
    # Survivors' alive status is known up to their last connected step.
    return {"obs_time": obs_time, "delivered_at": delivered, "last_alive_known": last_alive_known}
