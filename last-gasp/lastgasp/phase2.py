"""Phase 2 pipeline: independent tag network with a realistic receive side. SYNTHETIC.

run_tags(): world -> fire truth (phase 1 cache) -> tag layout -> tag deaths ->
gateways (greedy layout, fire-killed unless hardened) -> radio links ->
reception (star / mesh / mesh with store-and-forward) -> reconstruction
(IDW of observed death times) and spot detection -> metrics, compared with
perfect reception on the same tags.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from . import deploy
from .pipeline import get_fire, get_world, sample_T, set_path
from .receive import build_links, greedy_gateways, simulate_reception, spread_gateways
from .reconstruct import detect_and_reconstruct, idw

ROOT = Path(__file__).resolve().parents[1]


def load_config2(overrides=None):
    base = json.loads((ROOT / "configs/default.json").read_text())
    p2 = json.loads((ROOT / "configs/phase2.json").read_text())
    cfg = {**base, "phase2": p2}
    for k, v in (overrides or {}).items():
        set_path(cfg, k, v)
    return cfg


def radio_cfg(cfg):
    p2 = cfg["phase2"]
    r = copy.deepcopy(p2["radios"][p2["radio"]])
    r.update(p2["reception"])
    if r["mode"] == "star":
        r["mesh_capable"] = False
    return r


def spot_metrics(det, fire, tag_xy, observed, cfg):
    """Precision against any true spot; recall over significant spots; observability by tags."""
    ev = cfg["evaluate"]
    spots = fire["spots"]
    sig_idx = [k for k, s in enumerate(spots) if s["significant"]]
    own = fire["owner"]
    c = fire["cell"]
    ix = np.clip((tag_xy[:, 0] / c).astype(int), 0, own.shape[1] - 1)
    iy = np.clip((tag_xy[:, 1] / c).astype(int), 0, own.shape[0] - 1)
    owners = own[iy, ix]
    observable = {k: bool(np.any((owners == spots[k]["source_index"]) & observed)) for k in sig_idx}
    matched_sig, n_match, dist = set(), 0, []
    for d in det:
        best, bd = None, np.inf
        for k, s in enumerate(spots):
            dd = float(np.hypot(d["x"] - s["x"], d["y"] - s["y"]))
            if dd <= ev["spot_match_distance_m"] and abs(d["t"] - s["t_ign"]) <= ev["spot_match_time_min"] and dd < bd:
                best, bd = k, dd
        if best is not None:
            n_match += 1
            dist.append(bd)
            if best in sig_idx:
                matched_sig.add(best)
    return {"spot_n_true": len(sig_idx), "spot_n_observable": int(sum(observable.values())),
            "spot_n_detected": len(det), "spot_n_matched_det": n_match, "spot_n_matched_true": len(matched_sig),
            "spot_dist_err_med_m": float(np.median(dist)) if dist else float("nan")}


def reconstruct_and_score(prefix, xy, t_c, tag_xy, known_alive_fn, bxy, T_b, fire, cfg, rng, out, observed_mask):
    t_end = cfg["observe"]["t_end_min"]
    rc = cfg["reconstruct"]
    burned = T_b <= t_end
    if len(t_c) >= 3:
        pred = np.clip(idw(xy, t_c, bxy, rc["idw_power"], rc["idw_k"]), 0, t_end)
        err = np.abs(pred - T_b)[burned]
        out[f"{prefix}_bldg_med"] = float(np.median(err))
        out[f"{prefix}_bldg_p90"] = float(np.percentile(err, 90))
        rec = detect_and_reconstruct(xy, t_c, tag_xy, known_alive_fn, rc, cfg["classify"]["window_min"], rng)
        det = rec["spots"]
    else:
        out[f"{prefix}_bldg_med"] = float("nan")
        out[f"{prefix}_bldg_p90"] = float("nan")
        det = []
    sm = spot_metrics(det, fire, tag_xy, observed_mask, cfg)
    for k, v in sm.items():
        out[f"{prefix}_{k}"] = v


def run_tags(cfg, fire_seed=0, obs_seed=0, keep=False):
    p2 = cfg["phase2"]
    t_end = cfg["observe"]["t_end_min"]
    world, bxy, net = get_world(cfg)
    fire = get_fire(cfg, fire_seed)
    T_b = sample_T(fire, bxy)
    rng = np.random.default_rng(50_000 + 1000 * fire_seed + obs_seed)
    lay = p2["layout"]
    tag_xy = deploy.layout(world, bxy, lay["kind"], lay["spacing_m"], lay["edge_buffer_m"])
    nt = len(tag_xy)
    out = {"fire_seed": fire_seed, "obs_seed": obs_seed, "n_tags": nt,
           "tags_per_km2": nt / (world["width_m"] * world["height_m"] / 1e6)}
    # True tag deaths: fire arrival plus a short heat-to-failure delay; a few survive.
    tg_cfg = p2["tag"]
    T_tag = sample_T(fire, tag_xy)
    dies = (rng.random(nt) < tg_cfg["p_die_given_fire"]) & (T_tag <= t_end)
    t_death = np.where(dies, T_tag + rng.uniform(*tg_cfg["death_delay_min"], nt), np.inf)
    rate = tg_cfg["random_failure_rate_per_h"]
    t_rand = np.where(rng.random(nt) < 1 - np.exp(-rate * t_end / 60), rng.uniform(0, t_end, nt), np.inf)
    t_death = np.minimum(t_death, t_rand)
    t_death[t_death > t_end] = np.inf
    # Gateways.
    rcfg = radio_cfg(cfg)
    gw = p2["gateways"]
    sites = net.pole_xy[:: max(1, gw["candidate_stride"])]
    tt, _ = build_links(tag_xy, np.zeros((0, 2)), rcfg, rng)
    # Gateway layout. "coverage": greedy on expected direct links (scoring mesh reach instead makes every
    # site equal in a connected mesh). "spread": farthest-point layout. "perimeter": spread along the edge.
    placement = gw.get("placement", "spread")
    if placement == "coverage":
        g_idx = greedy_gateways(tag_xy, sites, rcfg, gw["count"])
    elif placement == "spread":
        g_idx = spread_gateways(tag_xy, sites, rcfg, gw["count"])
    elif placement == "perimeter":
        g_idx = spread_gateways(tag_xy, sites, rcfg, gw["count"],
                                (world["width_m"], world["height_m"], gw["perimeter_band_m"]))
    else:
        raise ValueError(placement)
    gw_xy = sites[g_idx]
    _, tg = build_links(tag_xy, gw_xy, {**rcfg, "mesh_capable": False}, rng)
    T_gw = sample_T(fire, gw_xy) if len(gw_xy) else np.zeros(0)
    if gw["hardened"]:
        gw_death = np.full(len(gw_xy), np.inf)
    else:
        burns = rng.random(len(gw_xy)) < gw["p_destroyed_given_fire"]
        gw_death = np.where(burns & (T_gw <= t_end), T_gw + rng.uniform(*gw["death_delay_min"], len(gw_xy)), np.inf)
    if gw["power"] == "grid":
        net_out = net.simulate_outages(lambda q: sample_T(fire, np.atleast_2d(q)), cfg["grid"], t_end, rng)
        from scipy.spatial import cKDTree
        nb = cKDTree(bxy).query(gw_xy)[1]
        gw_death = np.minimum(gw_death, net_out["t_building"][nb])
    out["n_gateways"] = len(gw_xy)
    out["frac_tags_direct_link"] = float(tg.any(1).mean()) if len(gw_xy) else 0.0
    out["mean_tag_degree"] = float(tt.sum() / max(nt, 1))
    rec = simulate_reception(t_death, gw_death, tt, tg, rcfg, t_end, rng)
    # Backhaul outage (cellular uplink down from fail to restore). With gateway buffering
    # (store-and-forward at the gateway) records wait and are sent at restore; without it they are lost.
    bf, br = gw.get("backhaul_fail_min"), gw.get("backhaul_restore_min")
    if bf is not None:
        br = np.inf if br is None else br
        during = (rec["delivered_at"] >= bf) & (rec["delivered_at"] < br)
        if gw.get("buffer", True) and np.isfinite(br):
            rec["delivered_at"] = np.where(during, br, rec["delivered_at"])
        else:
            rec["obs_time"] = np.where(during, np.nan, rec["obs_time"])
            rec["delivered_at"] = np.where(during, np.nan, rec["delivered_at"])
        rec["last_alive_known"] = np.where((rec["last_alive_known"] >= bf) & (rec["last_alive_known"] < br) &
                                           ~(gw.get("buffer", True) and np.isfinite(br)),
                                           bf, rec["last_alive_known"])
    true_dead = np.isfinite(t_death)
    fire_dead = true_dead & (T_tag <= t_end) & (t_death >= T_tag)
    obs = np.isfinite(rec["obs_time"])
    lag = rec["delivered_at"] - t_death
    out["n_fire_deaths"] = int(fire_dead.sum())
    out["frac_deaths_observed"] = float(obs[fire_dead].mean()) if fire_dead.any() else float("nan")
    out["frac_deaths_realtime"] = float((obs & (lag <= p2["realtime_window_min"]))[fire_dead].mean()) if fire_dead.any() else float("nan")
    out["delivery_lag_med_min"] = float(np.nanmedian(lag[obs & fire_dead])) if (obs & fire_dead).any() else float("nan")
    out["frac_gateways_lost"] = float(np.mean(np.isfinite(gw_death))) if len(gw_xy) else float("nan")
    hb = rcfg["heartbeat_s"] / 60.0
    delay = 0.5 * sum(tg_cfg["death_delay_min"]) - hb / 2
    # Perfect reception baseline on the same tags.
    hb_last = t_death - rng.uniform(0, hb, nt)
    perfect = true_dead
    reconstruct_and_score("perfect", tag_xy[perfect], hb_last[perfect] - delay, tag_xy,
                          lambda t0: (t_death > t0), bxy, T_b, fire, cfg, rng, out, perfect)
    # Realistic reception.
    known = rec["last_alive_known"]
    reconstruct_and_score("received", tag_xy[obs], rec["obs_time"][obs] - delay, tag_xy,
                          lambda t0: (known >= t0) | (np.nan_to_num(rec["obs_time"], nan=-np.inf) > t0),
                          bxy, T_b, fire, cfg, rng, out, obs)
    if keep:
        out["_artifacts"] = {"tag_xy": tag_xy, "gw_xy": gw_xy, "t_death": t_death, "gw_death": gw_death,
                             "rec": rec, "tt": tt, "tg": tg, "fire": fire, "T_tag": T_tag}
    return out
