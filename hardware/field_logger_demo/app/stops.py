"""Stops and delays (spec section 6). One implementation for REPLAY (whole session) and LIVE (rows so far, 2 s late).

Time base: every duration, window and press match uses mono_ms (monotonic within a session). UTC is never used for
durations. Durations follow one rule: last row - first row + 1 s.
"""
from .geo import Local, haversine, median, spread_p90

PARAMS = {
    "WALK": {"v_stop": 0.35, "t_min": 10.0, "r_max": 15.0, "bridge": 3.0},
    "UNKNOWN": {"v_stop": 0.35, "t_min": 10.0, "r_max": 15.0, "bridge": 3.0},
    "VEHICLE": {"v_stop": 1.0, "t_min": 10.0, "r_max": 25.0, "bridge": 3.0},
}
SUSTAIN_S = 5.0          # sustained movement that opens and closes the analysed span
SHORT_NOFIX_S = 3.0      # no-fix runs up to this long belong to what surrounds them
WINDOW_S = 2.0           # centred median window: +-2 s (5 rows at 1 Hz)
DISP_BASELINE_S = 5.0    # displacement baseline when the receiver gives no speed
MATCH_BEFORE_S, MATCH_AFTER_S = 10.0, 3.0


def params_for(mode):
    return dict(PARAMS.get(mode or "UNKNOWN", PARAMS["UNKNOWN"]))


def _obs(rows):
    """Observation rows with a time, sorted by mono (file order is already mono order; sort is stable)."""
    out = [r for r in rows if r.get("mono") is not None]
    out.sort(key=lambda r: r["mono"])
    return out


def _speeds(obs, fix_ix):
    """Speed per FIX row: RMC speed, else displacement over the last 5 s divided by the time (flagged)."""
    sp, src = {}, {}
    for n, i in enumerate(fix_ix):
        r = obs[i]
        if r.get("speed") is not None:
            sp[i], src[i] = r["speed"], "rmc"
            continue
        base = None
        for m in range(n - 1, -1, -1):          # latest fix at least 5 s earlier
            j = fix_ix[m]
            if r["t"] - obs[j]["t"] >= DISP_BASELINE_S:
                base = j
                break
        if base is None and n > 0:               # early in the file: the earliest fix we have
            base = fix_ix[0]
        if base is None or obs[base]["t"] >= r["t"]:
            sp[i], src[i] = None, None
            continue
        d = haversine(obs[base]["lat"], obs[base]["lon"], r["lat"], r["lon"])
        sp[i], src[i] = d / (r["t"] - obs[base]["t"]), "disp5"
    return sp, src


def _smooth(obs, fix_ix, sp):
    """Median of the speeds of the FIX rows within +-2 s (centred window)."""
    out = {}
    lo = 0
    n = len(fix_ix)
    hi = 0
    for k, i in enumerate(fix_ix):
        t = obs[i]["t"]
        while obs[fix_ix[lo]]["t"] < t - WINDOW_S - 1e-6:
            lo += 1
        hi = max(hi, k)
        while hi + 1 < n and obs[fix_ix[hi + 1]]["t"] <= t + WINDOW_S + 1e-6:
            hi += 1
        vals = [sp[fix_ix[m]] for m in range(lo, hi + 1) if sp[fix_ix[m]] is not None]
        out[i] = median(vals) if vals else None
    return out


def _uncovered(obs, a, b):
    """Seconds without a fix between two fixes a < b (indices into obs): their time step minus one row."""
    return max(0.0, obs[b]["t"] - obs[a]["t"] - 1.0)


def analyse(rows, mode="WALK", params=None, events=None, marks_are_stops=False, sensitivity=True, until_t=None,
            open_end=False):
    """Run the detector.

    LIVE passes until_t = now - 2 s: rows up to until_t are classified, each with its full centred window (the rows
    of the last 2 s are used for smoothing only), so a row gets the same smoothed speed it gets in REPLAY. LIVE also
    passes open_end=True while the session runs: the analysed span then reaches the last classified row, so a stop
    in progress is announced when it reaches T_min instead of when movement resumes. When the session ends, LIVE
    runs the detector once more without either, which gives exactly REPLAY's result (a stop that turns out to be
    the lead-out is withdrawn then)."""
    p = params or params_for(mode)
    obs = _obs(rows)
    res = _core(obs, p, until_t=until_t, open_end=open_end)
    res["params"] = p
    res["mode"] = mode
    if events is not None:
        res["validation"] = validate(res["stops"], events) if marks_are_stops else None
    if sensitivity:
        res["sensitivity"] = _sensitivity(res["obs"], p)
    return res


def _core(obs, p, until_t=None, open_end=False):
    v_stop, t_min, r_max, bridge = p["v_stop"], p["t_min"], p["r_max"], p["bridge"]
    fix_all = [i for i, r in enumerate(obs) if r.get("fix") and r.get("lat") is not None]
    sp, src = _speeds(obs, fix_all)
    sm = _smooth(obs, fix_all, sp)
    if until_t is not None:
        keep = sum(1 for r in obs if r["t"] <= until_t)     # obs is in time order
        obs = obs[:keep]
    fix_ix = [i for i in fix_all if i < len(obs)]
    stat = {i: (sm[i] is not None and sm[i] < v_stop) for i in fix_ix}

    # Long no-fix stretches between consecutive fixes are gaps (neither time nor distance counts as moving).
    gap_after = {}   # fix index -> next fix index, for each long gap
    for a, b in zip(fix_ix, fix_ix[1:]):
        if _uncovered(obs, a, b) > SHORT_NOFIX_S:
            gap_after[a] = b

    # Analysed span: first to last sustained movement (moving for >= 5 s without a stationary row or a gap).
    runs, cur = [], []
    for k, i in enumerate(fix_ix):
        moving = sm[i] is not None and not stat[i]
        if moving:
            if cur and fix_ix[k - 1] in gap_after:
                runs.append(cur)
                cur = []
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    sustained = [r for r in runs if obs[r[-1]]["t"] - obs[r[0]]["t"] + 1.0 >= SUSTAIN_S]
    out = {"speeds": {i: (sp[i], src[i], sm[i]) for i in fix_ix}, "fix_ix": fix_ix, "obs": obs}
    if not sustained:
        out.update({"span": None, "stops": [], "gaps": [], "states": ["lead"] * len(obs), "metrics": None,
                    "steps": []})
        return out
    a0_i, a1_i = sustained[0][0], sustained[-1][-1]
    A0, A1 = obs[a0_i]["t"], obs[a1_i]["t"]
    if open_end and fix_ix:
        A1 = max(A1, obs[fix_ix[-1]]["t"])      # LIVE: the session goes on; what follows the last movement is not lead-out yet
    span_fix = [i for i in fix_ix if A0 <= obs[i]["t"] <= A1]

    # Stop candidates: runs of stationary fixes, bridging moving interruptions and short no-fix of <= 3 s.
    cands, cur = [], []
    for i in span_fix:
        if not stat[i]:
            continue
        if cur:
            prev = cur[-1]
            between_gap = any(prev <= g < i for g in gap_after)
            if between_gap or _uncovered(obs, prev, i) > bridge:
                cands.append(cur)
                cur = []
        cur.append(i)
    if cur:
        cands.append(cur)
    stops = []
    loc = None
    for c in cands:
        first, last = c[0], c[-1]
        members = [i for i in span_fix if obs[first]["t"] <= obs[i]["t"] <= obs[last]["t"]]
        dur = obs[last]["t"] - obs[first]["t"] + 1.0
        if dur < t_min:
            continue
        lat_m = median([obs[i]["lat"] for i in members])
        lon_m = median([obs[i]["lon"] for i in members])
        loc = loc or Local(lat_m, lon_m)
        cx, cy = loc.xy(lat_m, lon_m)
        dists = []
        for i in members:
            x, y = loc.xy(obs[i]["lat"], obs[i]["lon"])
            dists.append(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5)
        p90 = spread_p90(dists)
        if p90 > r_max:
            continue
        hd = [obs[i]["hdop"] for i in members if obs[i].get("hdop") is not None]
        stops.append({"first": first, "last": last, "t0": obs[first]["t"], "t1": obs[last]["t"], "dur": dur,
                      "lat": lat_m, "lon": lon_m, "p90": p90, "n_rows": len(members),
                      "median_hdop": median(hd) if hd else None})
    for n, s in enumerate(stops, 1):
        s["n"] = n
        s["t_detect"] = s["t0"] + t_min - 1.0     # duration reaches T_min on this row

    # Gaps inside the span.
    gaps = []
    for a, b in gap_after.items():
        if A0 <= obs[a]["t"] and obs[b]["t"] <= A1:
            gaps.append({"a": a, "b": b, "t0": obs[a]["t"], "t1": obs[b]["t"], "dur": _uncovered(obs, a, b),
                         "span_m": haversine(obs[a]["lat"], obs[a]["lon"], obs[b]["lat"], obs[b]["lon"])})
    gaps.sort(key=lambda g: g["t0"])

    # Row states.
    states = []
    for r in obs:
        t = r["t"]
        if t < A0 or t > A1:
            states.append("lead")
        elif any(s["t0"] <= t <= s["t1"] for s in stops):
            states.append("stop")
        elif any(g["t0"] < t < g["t1"] for g in gaps):
            states.append("gap")
        else:
            states.append("move")
    fix_state = {i: states[i] for i in fix_ix}

    # Distance: great-circle steps between consecutive fixes while moving; short no-fix bridged, nothing across gaps.
    steps = []
    dist = 0.0
    for a, b in zip(span_fix, span_fix[1:]):
        if a in gap_after or fix_state[a] != "move" or fix_state[b] != "move":
            continue
        d = haversine(obs[a]["lat"], obs[a]["lon"], obs[b]["lat"], obs[b]["lon"])
        dist += d
        steps.append((obs[b]["t"], d))
    elapsed = A1 - A0 + 1.0
    stopped = sum(s["dur"] for s in stops)
    gap = sum(g["dur"] for g in gaps)
    moving = elapsed - stopped - gap
    m = {"elapsed": elapsed, "stopped": stopped, "gap": gap, "moving": moving, "distance": dist,
         "avg_speed": dist / moving if moving > 0 else None, "n_stops": len(stops),
         "pct_added": stopped / moving if moving > 0 else None,
         "stopped_over_elapsed": stopped / elapsed if elapsed > 0 else None,
         "stops_per_km": len(stops) / (dist / 1000.0) if dist > 0 else None,
         "longest": max((s["dur"] for s in stops), default=0.0),
         "lead_in": A0 - obs[0]["t"], "lead_out": obs[-1]["t"] - A1}
    out.update({"span": (A0, A1), "stops": stops, "gaps": gaps, "states": states, "metrics": m, "steps": steps})
    return out


def validate(stops, events):
    """One-to-one matching of button presses (event_press mono) to detected stops: a press may match a stop when it
    falls between the stop start - 10 s and the stop end + 3 s; conflicts go to the smallest press-to-start gap."""
    presses = [(e["event_no"], e["t_press"]) for e in events if e.get("t_press") is not None]
    pairs = []
    for no, tp in presses:
        for s in stops:
            if s["t0"] - MATCH_BEFORE_S <= tp <= s["t1"] + MATCH_AFTER_S:
                pairs.append((abs(tp - s["t0"]), no, s["n"], tp - s["t0"]))
    pairs.sort()
    used_p, used_s, matches = set(), set(), {}
    for _, no, sn, gap in pairs:
        if no in used_p or sn in used_s:
            continue
        used_p.add(no)
        used_s.add(sn)
        matches[sn] = (no, gap)
    for s in stops:
        mt = matches.get(s["n"])
        s["match_event"] = mt[0] if mt else None
        s["match_gap"] = mt[1] if mt else None
    k = len(matches)
    gaps = [g for _, g in matches.values()]
    return {"presses": len(presses), "detected": len(stops), "matched": k,
            "recall": k / len(presses) if presses else None, "precision": k / len(stops) if stops else None,
            "median_gap": median(gaps) if gaps else None}


def _sensitivity(obs, p):
    counts, stopped = [], []
    for fv in (0.7, 1.0, 1.3):
        for dt in (-3.0, 0.0, 3.0):
            q = dict(p, v_stop=p["v_stop"] * fv, t_min=p["t_min"] + dt)
            r = _core(obs, q)
            counts.append(len(r["stops"]))
            stopped.append(r["metrics"]["stopped"] if r["metrics"] else 0.0)
    return {"stops_min": min(counts), "stops_max": max(counts), "stopped_min": min(stopped),
            "stopped_max": max(stopped), "v_factors": [0.7, 1.0, 1.3], "t_min_values": [p["t_min"] - 3, p["t_min"],
                                                                                         p["t_min"] + 3]}
