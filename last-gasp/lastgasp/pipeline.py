"""End-to-end run: world -> fire truth -> grid -> observations -> classify -> reconstruct -> evaluate.

All outputs are SYNTHETIC.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np

from .classify import classify_time_only, classify_topology
from .fire import FireGrid, simulate_fire
from .grid import PowerNetwork
from .observe import observe
from .reconstruct import HuygensCorrected, detect_and_reconstruct, idw

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None, overrides=None):
    cfg = json.loads(Path(path or ROOT / "configs/default.json").read_text())
    for k, v in (overrides or {}).items():
        set_path(cfg, k, v)
    return cfg


def set_path(cfg, dotted, value):
    keys = dotted.split(".")
    d = cfg
    for k in keys[:-1]:
        d = d[k]
    d[keys[-1]] = value


_WORLD = {}


def get_world(cfg):
    from .world import build_world
    key = cfg["world"]["processed"]
    if key not in _WORLD:
        w = build_world(cfg["world"], ROOT)
        bxy = np.array([[b["x"], b["y"]] for b in w["buildings"]])
        net = PowerNetwork(w, bxy, cfg["grid"])
        _WORLD[key] = (w, bxy, net)
    return _WORLD[key]


def fire_cache_key(cfg, fire_seed):
    f = copy.deepcopy(cfg["fire"])
    digest = hashlib.sha1(json.dumps(f, sort_keys=True).encode()).hexdigest()[:10]
    return f"fire_s{fire_seed}_{digest}"


def get_fire(cfg, fire_seed, cache=True):
    w, bxy, net = get_world(cfg)
    cdir = ROOT / "results/cache"
    cdir.mkdir(parents=True, exist_ok=True)
    path = cdir / (fire_cache_key(cfg, fire_seed) + ".pkl")
    if cache and path.exists():
        return pickle.loads(path.read_bytes())
    rng = np.random.default_rng(1000 + fire_seed)
    fg = FireGrid(w["width_m"], w["height_m"], cfg["fire"], rng)
    res = simulate_fire(fg, cfg["fire"], rng, cfg["fire"]["t_end_min"])
    res["cell"] = fg.cell
    res["fuel"] = fg.fuel
    if cache:
        path.write_bytes(pickle.dumps(res))
    return res


def sample_T(fire, xy):
    T = fire["T"]
    c = fire["cell"]
    ix = np.clip((xy[:, 0] / c).astype(int), 0, T.shape[1] - 1)
    iy = np.clip((xy[:, 1] / c).astype(int), 0, T.shape[0] - 1)
    return T[iy, ix]


def assumed_delay(kind, cfg):
    o = cfg["observe"]
    base = o["ignition_delay_median_min"] * o["timing_noise_multiplier"]
    if kind == "meter":
        return base
    if kind == "router":
        return base + o["router"]["poll_interval_min"] / 2
    if kind == "tag":
        lo, hi = o["tag"]["death_delay_min"]
        return 0.5 * (lo + hi) * o["timing_noise_multiplier"] - o["tag"]["heartbeat_s"] / 120.0
    raise ValueError(kind)


def all_spots_list(fire):
    return fire["spots"]


def run_one(cfg, fire_seed=0, obs_seed=0, keep=False):
    t_end = cfg["observe"]["t_end_min"]
    w, bxy, net = get_world(cfg)
    fire = get_fire(cfg, fire_seed)
    T_b = sample_T(fire, bxy)
    rng = np.random.default_rng(10_000 * (fire_seed + 1) + obs_seed)
    net_out = net.simulate_outages(lambda q: sample_T(fire, np.atleast_2d(q)), cfg["grid"], t_end, rng)
    obs = observe(bxy, T_b, net_out, cfg["observe"], rng, t_end)
    oc = cfg["observe"]
    p_del = {"meter": oc["meter"]["p_deliver"], "router": oc["router"]["p_deliver"], "tag": 1.0}
    windows = {"meter": cfg["classify"]["window_min"],
               "router": oc["router"]["poll_interval_min"] + cfg["classify"]["window_min"],
               "tag": cfg["classify"]["window_min"]}
    label, _ = classify_topology(obs, net, cfg["classify"], p_del, windows)
    label_time = classify_time_only(obs, cfg["classify"])

    seen = obs["delivered"] & np.isfinite(obs["t_rep"])
    corr = np.array([assumed_delay(k, cfg) for k in obs["kind"]])
    t_c = obs["t_rep"] - corr
    dev_xy = np.c_[obs["x"], obs["y"]]

    def status(t0):
        known_alive = (~obs["dead"]) | (seen & (obs["t_rep"] > t0))
        return known_alive

    fire_rows = np.where(seen & (label == "fire"))[0]
    # Grid signature check for spot candidates: another delivered death within the window
    # under the same small protective device (at most small_device_max buildings).
    small_max = cfg["classify"]["small_device_max_buildings"]
    b_small = [set(d for d in net.building_devices[b] if len(net.device_buildings[d]) <= small_max)
               for b in range(len(bxy))]
    seen_rows = np.where(seen)[0]

    def grid_partner(jj):
        row = fire_rows[jj]
        devs = b_small[obs["building"][row]]
        if not devs:
            return False
        near_t = seen_rows[np.abs(obs["t_rep"][seen_rows] - obs["t_rep"][row]) <= cfg["classify"]["window_min"]]
        return any(r != row and obs["kind"][r] != "tag" and devs & b_small[obs["building"][r]] for r in near_t)

    rec = detect_and_reconstruct(dev_xy[fire_rows], t_c[fire_rows], dev_xy, status, cfg["reconstruct"],
                                 cfg["classify"]["window_min"], rng, grid_partner)
    final_label = label.copy()
    final_label[fire_rows[rec["role"] == "outlier"]] = "other"
    acc_rows = fire_rows[rec["active"]]

    # Evaluation points: every building that truly burned by t_end, and an evaluation grid.
    rcfg = cfg["reconstruct"]
    ge = rcfg["eval_cell_m"]
    gx = np.arange(ge / 2, w["width_m"], ge)
    gy = np.arange(ge / 2, w["height_m"], ge)
    GX, GY = np.meshgrid(gx, gy)
    gxy = np.c_[GX.ravel(), GY.ravel()]
    T_g = sample_T(fire, gxy)

    out = {"fire_seed": fire_seed, "obs_seed": obs_seed}
    methods = {}
    # Naive baseline: IDW of all delivered deaths, no classification.
    all_rows = np.where(seen)[0]
    methods["idw_naive"] = (lambda q: idw(dev_xy[all_rows], t_c[all_rows], q, rcfg["idw_power"], rcfg["idw_k"]))
    methods["idw_topology"] = (lambda q: idw(dev_xy[acc_rows], t_c[acc_rows], q, rcfg["idw_power"], rcfg["idw_k"]))
    if rec["params"] is not None and len(acc_rows) > rcfg["huygens_k"] + 1:
        hc = HuygensCorrected(dev_xy[acc_rows], t_c[acc_rows], rec["params"], rcfg["huygens_k"],
                              rcfg["residual_length_m"], rcfg["idw_power"], rcfg["idw_k"])
        methods["huygens"] = hc

    # Density floor: IDW of the TRUE arrival times at every instrumented building that burned
    # (no delays, no lost messages, no grid censoring).
    inst_b = np.unique(obs["building"])
    ok_o = T_b[inst_b] <= t_end
    if ok_o.sum() >= 3:
        oxy, ot = bxy[inst_b][ok_o], T_b[inst_b][ok_o]
        methods["oracle_idw"] = (lambda q: idw(oxy, ot, q, rcfg["idw_power"], rcfg["idw_k"]))
    burned_b = T_b <= t_end
    margin = cfg["evaluate"]["interior_margin_m"]
    interior = ((gxy[:, 0] > margin) & (gxy[:, 0] < w["width_m"] - margin) &
                (gxy[:, 1] > margin) & (gxy[:, 1] < w["height_m"] - margin))
    burned_g = (T_g <= t_end) & interior
    fields = {}
    for name, f in methods.items():
        pb = np.clip(f(bxy), 0, t_end)
        err_b = np.abs(pb - T_b)[burned_b]
        out[f"{name}_bldg_med"] = float(np.median(err_b))
        out[f"{name}_bldg_p90"] = float(np.percentile(err_b, 90))
        if keep or name in ("huygens", "idw_topology"):
            pg = np.clip(f(gxy), 0, t_end)
            eg = np.abs(pg - T_g)[burned_g]
            out[f"{name}_grid_med"] = float(np.median(eg))
            out[f"{name}_grid_p90"] = float(np.percentile(eg, 90))
            if keep:
                fields[name] = pg.reshape(GX.shape)
    # Classification metrics on delivered observations.
    # A death is fire-informative if the fire reached this building or its own transformer pole.
    truth_fire = np.isin(obs["cause"], ["fire", "fire_local"])
    pred_fire = final_label == "fire"
    s = seen
    out["n_devices"] = int(len(obs["kind"]))
    out["n_delivered"] = int(s.sum())
    out["nodes_per_km2"] = float(len(obs["kind"]) / (w["width_m"] * w["height_m"] / 1e6))
    out["frac_deaths_fire"] = float(truth_fire[s].mean()) if s.any() else float("nan")
    out["cls_acc"] = float(np.mean(pred_fire[s] == truth_fire[s]))
    tp = np.sum(pred_fire & truth_fire & s)
    tn = np.sum(~pred_fire & ~truth_fire & s)
    P, N = np.sum(truth_fire & s), np.sum(~truth_fire & s)
    out["cls_balanced_acc"] = float(0.5 * (tp / max(P, 1) + tn / max(N, 1))) if N > 0 else float("nan")
    out["cls_fire_recall"] = float(tp / max(P, 1))
    out["cls_nonfire_recall"] = float(tn / N) if N > 0 else float("nan")
    pred_time_fire = label_time == "fire"
    out["cls_time_only_acc"] = float(np.mean(pred_time_fire[s] == truth_fire[s]))
    tp2 = np.sum(pred_time_fire & truth_fire & s)
    tn2 = np.sum(~pred_time_fire & ~truth_fire & s)
    out["cls_time_only_balanced_acc"] = float(0.5 * (tp2 / max(P, 1) + tn2 / max(N, 1))) if N > 0 else float("nan")
    # Fraction of fire-killed buildings whose fire signal was censored by an earlier grid outage.
    fire_reached = (obs["T_fire_building"] <= t_end) & obs["building_burns"]
    out["frac_fire_censored_by_grid"] = float(np.mean(np.isin(obs["cause"][fire_reached], ["fire_grid", "random_grid", "upstream_grid", "random_device"]))) if fire_reached.any() else float("nan")
    # Spot detection.
    ev = cfg["evaluate"]
    true_spots = [sp for sp in fire["spots"] if sp["significant"]]
    # Observable: at least one instrumented building first burned by this spot.
    own = fire["owner"]
    c = fire["cell"]
    ib = obs["building"]
    ix = np.clip((bxy[ib, 0] / c).astype(int), 0, own.shape[1] - 1)
    iy = np.clip((bxy[ib, 1] / c).astype(int), 0, own.shape[0] - 1)
    owners_inst = own[iy, ix]
    informative = seen & np.isin(obs["cause"], ["fire", "fire_local"])
    for sp in all_spots_list(fire):
        sp["observable"] = bool(np.any((owners_inst == sp["source_index"]) & informative))
    det = rec["spots"]
    for d in det:
        d["t"] = d["t"] + rec["bias"]
    # Precision: a detection is correct if it matches any true spot fire (lead >= min_lead).
    # Recall: over significant spots (lead >= significant_lead_min).
    all_spots = fire["spots"]
    matched_true = set()
    n_match = 0
    dist_err, jump_err = [], []
    for d in det:
        best, bd = None, np.inf
        for k, sp in enumerate(all_spots):
            dd = float(np.hypot(d["x"] - sp["x"], d["y"] - sp["y"]))
            if dd <= ev["spot_match_distance_m"] and abs(d["t"] - sp["t_ign"]) <= ev["spot_match_time_min"] and dd < bd:
                best, bd = k, dd
        if best is not None:
            n_match += 1
            dist_err.append(bd)
            if all_spots[best]["significant"]:
                matched_true.add(true_spots.index(all_spots[best]))
            if np.isfinite(d["jump_m"]) and np.isfinite(all_spots[best]["jump_m"]):
                jump_err.append(abs(d["jump_m"] - all_spots[best]["jump_m"]))
    n_obsable = sum(sp["observable"] for sp in true_spots)
    out["spot_n_true"] = len(true_spots)
    out["spot_n_observable"] = int(n_obsable)
    out["spot_n_detected"] = len(det)
    out["spot_n_matched_det"] = n_match
    out["spot_n_matched_true"] = len(matched_true)
    out["spot_precision"] = float(n_match / len(det)) if det else float("nan")
    out["spot_recall_all"] = float(len(matched_true) / len(true_spots)) if true_spots else float("nan")
    out["spot_recall_observable"] = float(len([k for k in matched_true if true_spots[k]["observable"]]) / n_obsable) if n_obsable else float("nan")
    out["spot_dist_err_med_m"] = float(np.median(dist_err)) if dist_err else float("nan")
    out["spot_jump_err_med_m"] = float(np.median(jump_err)) if jump_err else float("nan")
    if rec["params"] is not None:
        out["fit_R_m_min"], out["fit_dir_deg"], out["fit_lb"] = rec["params"][0], float(np.degrees(rec["params"][1])), rec["params"][2]
    if keep:
        out["_artifacts"] = {"obs": obs, "label": final_label, "label_time": label_time, "rec": rec,
                             "fields": fields, "grid_xy": (gx, gy), "T_grid": T_g.reshape(GX.shape),
                             "t_c": t_c, "net_out": net_out, "fire": fire, "true_spots": true_spots,
                             "detected_spots": det, "acc_rows": acc_rows, "fire_rows": fire_rows}
    return out
