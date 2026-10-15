"""Phase 2 item 2: protection-device trip logs as a coarse fire sensor. SYNTHETIC.

Builds on the phase 1 power network (lastgasp.grid):
1. Energisation: a device can only trip while energised. A device whose
   upstream device already opened logs nothing (phase 1 ignored this for
   logging because only building power-loss times mattered).
2. Precautionary shutoffs: the utility opens feeder breakers ("blanket" at a
   fixed time, or "proximity" when the fire comes within distance_m of any
   pole of that feeder, after a decision delay). distance_m = 0 gives a
   reactive shutoff of lines the fire has already reached, as reported for
   the Angye to Uiseong line on 2025-03-22. An optional logging blackout
   (logging_stops_min) drops all entries after that time.
3. Logging: only SCADA-monitored devices (feeder breakers and reclosers by
   default) appear in the log, with a timestamp and, with probability
   p_type_logged, the event type (protection trip vs remote/manual open).
4. Classification: fire trip versus precautionary open, using the logged type
   when present, else coordination (several feeders opening within a short
   window) and, if tags exist, whether the tag-based arrival estimate says the
   fire had reached the zone.
5. Reconstruction: each fire-classified trip becomes a pseudo-observation at
   the upwind-most point of the device's protection zone (wind direction is
   assumed known from weather data), at trip time minus the mean fault delay.
"""
from __future__ import annotations

import math

import numpy as np

from .pipeline import get_fire, get_world, sample_T
from .reconstruct import idw


def zone_spans(net):
    """Map each line device to the midpoints of the spans it protects directly."""
    c, mid = net.spans()
    zones = {}
    for child, m in zip(c, mid):
        d = net.upstream_device[child]
        if d >= 0:
            zones.setdefault(int(d), []).append(m)
    return {d: np.asarray(v) for d, v in zones.items()}


def device_ancestors(net):
    anc = {}
    for d, dev in enumerate(net.devices):
        a = list(net.pole_ancestors[dev["pole"]])
        if dev["kind"] != "transformer" and d in a:
            a.remove(d)
        anc[d] = a
    return anc


def simulate_log(net, fire, cfg, rng, t_end):
    """Return the trip log (list of dicts) and ground truth."""
    tc = cfg["phase2"]["trips"]
    net_out = net.simulate_outages(lambda q: sample_T(fire, np.atleast_2d(q)), cfg["grid"], t_end, rng)
    t_op = net_out["t_op"].copy()
    cause = net_out["cause"].copy()
    breakers = [d for d, dev in enumerate(net.devices) if dev["kind"] == "breaker"]
    pre = tc["precaution"]
    if pre["mode"] == "blanket":
        for d in breakers:
            if pre["time_min"] < t_op[d]:
                t_op[d], cause[d] = float(pre["time_min"]), "precaution"
    elif pre["mode"] == "proximity":
        feeder_poles = {d: [] for d in breakers}
        for p in range(net.n_poles):
            a = net.pole_ancestors[p]
            if a and a[0] in feeder_poles:
                feeder_poles[a[0]].append(p)
        for d in breakers:
            P = net.pole_xy[feeder_poles[d]] if feeder_poles[d] else net.pole_xy[[net.devices[d]["pole"]]]
            # First time the fire comes within distance_m of any pole: approximate with the fire
            # arrival at the pole minus distance / head rate of spread.
            Tp = sample_T(fire, P)
            t_near = float(np.min(Tp)) - pre["distance_m"] / fire["r_head_m_min"]
            t = max(0.0, t_near) + pre["decision_delay_min"]
            if t < t_op[d]:
                t_op[d], cause[d] = t, "precaution"
    # Energisation: process devices from upstream to downstream.
    anc = device_ancestors(net)
    order = np.argsort([len(anc[d]) for d in range(len(net.devices))], kind="stable")
    t_eff = np.full(len(t_op), np.inf)
    for d in order:
        if not np.isfinite(t_op[d]):
            continue
        up = min((t_eff[a] for a in anc[d]), default=np.inf)
        if t_op[d] < up:
            t_eff[d] = t_op[d]
    log = []
    logged = set(tc["logged_kinds"])
    # Logging blackout: distribution automation stops recording (reported for Yeongdeok, 2025-03-25).
    t_log_end = tc.get("logging_stops_min")
    t_log_end = t_end if t_log_end is None else min(t_end, t_log_end)
    for d in np.where(np.isfinite(t_eff) & (t_eff <= t_log_end))[0]:
        dev = net.devices[d]
        if dev["kind"] not in logged:
            continue
        true = cause[d]
        etype = "open" if true == "precaution" else "trip"
        known = rng.random() < tc["p_type_logged"]
        log.append({"device": int(d), "kind": dev["kind"], "t": float(t_eff[d] + rng.normal(0, tc["clock_sd_s"] / 60)),
                    "type": etype if known else "unknown", "true_cause": str(true)})
    log.sort(key=lambda e: e["t"])
    return log, {"t_eff": t_eff, "cause": cause}


def classify_log(log, cfg, tag_estimate=None, zones=None, wind_to=0.0, tag_xy=None):
    """Label each entry 'fire', 'precaution' or 'other'.

    The tag consistency check is applied only where an observed tag death lies within
    tag_check_radius_m of the device's zone; far from tags the tag estimate is unreliable.
    """
    tc = cfg["phase2"]["trips"]
    times = np.array([e["t"] for e in log])
    labels = []
    for k, e in enumerate(log):
        if e["type"] == "open":
            labels.append("precaution")
            continue
        if e["type"] == "trip" and tag_estimate is None:
            labels.append("fire")
            continue
        sim = int(np.sum(np.abs(times - e["t"]) <= tc["coordination_window_min"])) - 1
        if e["type"] == "unknown" and e["kind"] == "breaker" and sim >= tc["coordination_min_others"]:
            labels.append("precaution")
            continue
        near_tags = True
        if tag_xy is not None and zones is not None and e["device"] in zones and len(tag_xy):
            Z = zones[e["device"]]
            dmin = np.min(np.hypot(Z[:, None, 0] - tag_xy[None, :, 0], Z[:, None, 1] - tag_xy[None, :, 1]))
            near_tags = dmin <= tc["tag_check_radius_m"]
        if tag_estimate is not None and zones is not None and e["device"] in zones and near_tags:
            # Tag-based arrival estimate over the zone: fire must have reached it by the trip.
            T_est = float(np.min(tag_estimate(zones[e["device"]])))
            if T_est > e["t"] + tc["tag_check_margin_min"]:
                labels.append("precaution" if e["kind"] == "breaker" and e["type"] == "unknown" else "other")
                continue
        labels.append("fire")
    return labels


def pseudo_observations(log, labels, zones, cfg, wind_to_math):
    """(xy, t) pseudo-observations from fire-labelled trips."""
    tc = cfg["phase2"]["trips"]
    u = np.array([math.cos(wind_to_math), math.sin(wind_to_math)])
    xy, t = [], []
    for e, lab in zip(log, labels):
        if lab != "fire" or e["device"] not in zones:
            continue
        Z = zones[e["device"]]
        j = int(np.argmin(Z @ u))  # upwind-most span of the zone
        xy.append(Z[j])
        t.append(e["t"] - tc["assumed_fault_delay_min"])
    return np.asarray(xy).reshape(-1, 2), np.asarray(t)


def run_trips(cfg, fire_seed=0, obs_seed=0, keep=False):
    """Trips only, tags only and trips plus tags at the configured sparse tag spacing (perfect tag reception)."""
    from . import deploy
    t_end = cfg["observe"]["t_end_min"]
    world, bxy, net = get_world(cfg)
    fire = get_fire(cfg, fire_seed)
    T_b = sample_T(fire, bxy)
    burned = T_b <= t_end
    rng = np.random.default_rng(70_000 + 1000 * fire_seed + obs_seed)
    log, truth = simulate_log(net, fire, cfg, rng, t_end)
    zones = zone_spans(net)
    bearing_to = (cfg["fire"]["wind_from_deg"] + 180.0) % 360.0
    wind_to = math.radians(90.0 - bearing_to)
    out = {"fire_seed": fire_seed, "obs_seed": obs_seed, "n_log": len(log),
           "n_log_fire_true": int(sum(e["true_cause"] in ("fire_grid", "fire_local") for e in log)),
           "n_log_precaution_true": int(sum(e["true_cause"] == "precaution" for e in log))}
    rc = cfg["reconstruct"]

    def score(prefix, xy, t):
        if len(t) >= 1:
            pred = np.clip(idw(xy, t, bxy, rc["idw_power"], rc["idw_k"]), 0, t_end)
            err = np.abs(pred - T_b)[burned]
            out[f"{prefix}_bldg_med"] = float(np.median(err))
            out[f"{prefix}_bldg_p90"] = float(np.percentile(err, 90))
        else:
            out[f"{prefix}_bldg_med"] = out[f"{prefix}_bldg_p90"] = float("nan")
        out[f"{prefix}_n_obs"] = int(len(t))

    def cls_score(prefix, labels):
        truth_fire = np.array([e["true_cause"] in ("fire_grid", "fire_local") for e in log])
        truth_pre = np.array([e["true_cause"] == "precaution" for e in log])
        lab = np.array(labels)
        out[f"{prefix}_acc"] = float(np.mean((lab == "fire") == truth_fire)) if len(log) else float("nan")
        out[f"{prefix}_precaution_recall"] = float(np.mean(lab[truth_pre] == "precaution")) if truth_pre.any() else float("nan")
        out[f"{prefix}_fire_recall"] = float(np.mean(lab[truth_fire] == "fire")) if truth_fire.any() else float("nan")

    labels = classify_log(log, cfg)
    cls_score("cls_log_only", labels)
    xy_tr, t_tr = pseudo_observations(log, labels, zones, cfg, wind_to)
    score("trips", xy_tr, t_tr)
    # Sparse tags with perfect reception.
    p2 = cfg["phase2"]
    tag_xy = deploy.layout(world, bxy, p2["layout"]["kind"], p2["trips"]["tag_spacing_m"], p2["layout"]["edge_buffer_m"])
    T_tag = sample_T(fire, tag_xy)
    dies = (rng.random(len(tag_xy)) < p2["tag"]["p_die_given_fire"]) & (T_tag <= t_end)
    t_tag = T_tag[dies] + rng.uniform(*p2["tag"]["death_delay_min"], dies.sum()) - 0.5 * sum(p2["tag"]["death_delay_min"])
    out["n_tags"] = int(len(tag_xy))
    score("tags", tag_xy[dies], t_tag)
    if dies.sum() >= 3:
        tag_est = lambda q: idw(tag_xy[dies], t_tag, q, rc["idw_power"], rc["idw_k"])  # noqa: E731
        labels2 = classify_log(log, cfg, tag_est, zones, wind_to, tag_xy[dies])
    else:
        labels2 = labels
    cls_score("cls_with_tags", labels2)
    xy2, t2 = pseudo_observations(log, labels2, zones, cfg, wind_to)
    score("tags_trips", np.vstack([tag_xy[dies], xy2]), np.r_[t_tag, t2])
    if keep:
        out["_artifacts"] = {"log": log, "labels": labels, "labels2": labels2, "xy_tr": xy_tr, "t_tr": t_tr,
                             "tag_xy": tag_xy, "dies": dies, "zones": zones, "fire": fire}
    return out
