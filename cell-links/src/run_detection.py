"""Steps 6 and 7: inject simulated fire signatures into real dry-weather link noise (OpenMRG),
evaluate simple detectors, and quantify confounders (rain, ATPC, coarse logging).

Usage: .venv/bin/python -I src/run_detection.py   (reads data/raw/openmrg, an untrusted download)
Outputs: results/detection/*.csv, figures/det_*.png/svg, NUMBERS.json entries det.* and conf.*
Injected events are simulated; only the noise is observed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import OI, RAW, RESULTS, load_config, record, savefig, style  # noqa: E402
from detect import (alarm_onsets, drop_stat, first_alarm, minmax_15, minmax_stats,  # noqa: E402
                    quantize, var_stat)

CFG_NAME = "detection.json"
OUT = RESULTS / "detection"
DT = 10.0


# ----------------------------------------------------------------------------------------------
# Noise pool
# ----------------------------------------------------------------------------------------------
def load_openmrg(cfg, n_sublinks=None, rng=None):
    """Return (RSL - TSL DataFrame [time x sublink] at 10 s, metadata indexed by sublink).

    cml.nc is stored contiguously as (time, sublink), so it is read in time blocks and only the
    selected sub-links are kept."""
    import netCDF4
    root = RAW / "openmrg" / "extracted"
    meta = pd.read_csv(next(root.rglob("cml_metadata.csv"))).set_index("Sublink")
    nc = netCDF4.Dataset(next(root.rglob(cfg["openmrg_cml_glob"])))
    sub = np.asarray(nc["sublink"][:])
    cols = np.arange(len(sub))
    if n_sublinks is not None:
        cols = np.sort(rng.choice(cols, size=min(n_sublinks, len(cols)), replace=False))
    tvar = nc["time"]
    times = netCDF4.num2date(tvar[:], tvar.units, only_use_cftime_datetimes=False, only_use_python_datetimes=True)
    nt = len(times)
    out = np.empty((nt, len(cols)), dtype="float32")
    blk = 50_000
    for a in range(0, nt, blk):
        b = min(a + blk, nt)
        r = np.ma.filled(nc["rsl"][a:b, :].astype("float32"), np.nan)[:, cols]
        t = np.ma.filled(nc["tsl"][a:b, :].astype("float32"), np.nan)[:, cols]
        out[a:b] = r - t
    nc.close()
    out[np.abs(out) > 300] = np.nan
    x = pd.DataFrame(out, index=pd.DatetimeIndex(times), columns=sub[cols])
    return x, meta.loc[sub[cols]]


def wet_mask_from_gauges(index, cfg):
    """True where any city gauge reports rain within +-pad hours."""
    import glob
    root = RAW / "openmrg" / "extracted"
    files = sorted(root.rglob(cfg["openmrg_gauge_glob"]))
    g = pd.read_csv(files[0], index_col=0, parse_dates=True)
    g.index = g.index.tz_localize(None)
    rain = (g.select_dtypes("number").fillna(0).sum(axis=1) > 0).astype(float)
    rain = rain.reindex(index, method="ffill").fillna(0.0)
    pad = int(cfg["dry_pad_h"] * 3600 / DT)
    wet = rain.rolling(2 * pad + 1, center=True, min_periods=1).max() > 0
    return wet


def dry_chunks(x, wet, min_len_s):
    """Split each sublink's series into contiguous dry chunks with valid data, NaNs forward-filled
    over short gaps (up to 1 min)."""
    chunks = []
    min_n = int(min_len_s / DT)
    for col in x.columns:
        s = x[col].where(~wet.to_numpy())
        s = s.ffill(limit=6)
        v = s.notna().to_numpy()
        d = np.diff(np.concatenate([[0], v.astype(int), [0]]))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if b - a >= min_n:
                arr = s.to_numpy()[a:b].astype(float)
                chunks.append((col, a, arr - np.median(arr)))
    return chunks


def synthetic_chunks(n, length_s, rng, sigma=0.15, rho=0.98, q=0.3):
    """Fallback documented noise model: AR(1) Gaussian, then 0.3 dB quantization."""
    out = []
    m = int(length_s / DT)
    for i in range(n):
        e = rng.normal(0, sigma * np.sqrt(1 - rho**2), m)
        y = np.zeros(m)
        for k in range(1, m):
            y[k] = rho * y[k - 1] + e[k]
        out.append((f"synthetic{i}", 0, quantize(y, q)))
    return out


# ----------------------------------------------------------------------------------------------
# Logging schemes and detector statistics
# ----------------------------------------------------------------------------------------------
def observe(x10, scheme):
    """Return (time step s, dict of detector statistics) for one 10 s series under a logging scheme."""
    if scheme in ("s10", "s10_atpc2", "s10_atpc5"):
        y = quantize(x10, 0.3)
        return DT, {"drop": drop_stat(y, DT, persist=2), "var": var_stat(y, DT, win_s=180)}
    if scheme == "m1":
        y = quantize(x10[: len(x10) // 6 * 6][::6], 0.3)
        return 60.0, {"drop": drop_stat(y, 60.0, persist=1), "var": var_stat(y, 60.0, win_s=600, gap_s=900)}
    if scheme == "mm15":
        lo, hi = minmax_15(x10, DT, 1.0)
        dmin, drng = minmax_stats(lo, hi)
        return 900.0, {"drop": dmin, "var": drng}
    raise ValueError(scheme)


def apply_atpc(fade, window_db):
    """RSL-only logging with ATPC: the transmitter compensates fades beyond the hysteresis window,
    so the logged received level never drops more than `window_db`."""
    return np.minimum(fade, window_db)


# ----------------------------------------------------------------------------------------------
def far_table(pool, schemes, thr, cfg, label):
    rows, cache = [], {}
    for scheme in schemes:
        counts = {d: np.zeros(len(thr[f"{scheme}:{d}"])) for d in ("drop", "var")}
        days = 0.0
        base = "s10" if scheme.startswith("s10") else scheme  # ATPC does not change fade-free noise
        for ci, (_, _, arr) in enumerate(pool):
            if (base, ci) not in cache:
                cache[(base, ci)] = observe(arr, base)
            step, st = cache[(base, ci)]
            warm = int(cfg["warmup_h"] * 3600 / step)
            days += (len(st["drop"]) - warm) * step / 86400
            for d in ("drop", "var"):
                for i, t in enumerate(thr[f"{scheme}:{d}"]):
                    counts[d][i] += len(alarm_onsets(st[d][warm:], t, int(cfg["refractory_min"] * 60 / step)))
        for d in ("drop", "var"):
            for t, c in zip(thr[f"{scheme}:{d}"], counts[d]):
                rows.append({"noise": label, "scheme": scheme, "detector": d, "thr": t,
                             "alarms": c, "link_days": days, "far_per_link_day": c / days})
    return rows


def screen(train_chunks, cfg):
    """Rank sub-links by their alarm rate on June dry data and keep the best fraction."""
    rate = {}
    for sl, _, arr in train_chunks:
        step, st = observe(arr, "s10")
        warm = int(cfg["warmup_h"] * 3600 / step)
        n = (len(alarm_onsets(st["drop"][warm:], cfg["screen_drop_db"], 360)) +
             len(alarm_onsets(st["var"][warm:], cfg["screen_var_ratio"], 360)))
        d = (len(arr) - warm) * DT / 86400
        a, b = rate.get(sl, (0, 0.0))
        rate[sl] = (a + n, b + d)
    r = pd.Series({k: v[0] / max(v[1], 1e-9) for k, v in rate.items() if v[1] >= cfg["screen_min_days"]})
    keep = r[r <= r.quantile(cfg["screen_keep_fraction"])].index
    return set(keep), r


def inject(pool, cfg, thr, schemes, rng, pool_name):
    ev_rows = []
    lead = int(cfg["warmup_h"] * 3600 / DT)
    for scen in cfg["spread_scenarios"]:
        meta = pd.read_csv(RESULTS / "crossings" / f"links_{scen}.csv")
        sig = np.load(RESULTS / "crossings" / f"signatures_{scen}.npz")
        for _, m in meta.iterrows():
            key = f"link{int(m.link)}"
            t = sig[key + "_t"].astype(float)
            S = sig[key + "_S"].astype(float)
            n_sig = len(t)
            for ne in cfg["ne_scenarios"]:
                A = sig[key + f"_A_{ne}"].astype(float)
                need = lead + n_sig
                cands = [c for c in pool if len(c[2]) >= lead + min(n_sig, cfg["max_event_h"] * 360)]
                cid, _, arr = cands[rng.integers(len(cands))]
                n_use = min(need, len(arr))
                start = rng.integers(0, len(arr) - n_use + 1)
                noise = arr[start:start + n_use]
                k = n_use - lead
                fade = np.zeros(n_use)
                fade[lead:] = A[:k] + S[:k] * rng.standard_normal(k)
                active = np.zeros(n_use, bool)
                active[lead:] = (A[:k] >= cfg["active_db"]) | (S[:k] >= cfg["active_db"])
                tt = np.full(n_use, np.nan)
                tt[lead:] = t[:k]
                tt[:lead] = t[0] - (lead - np.arange(lead)) * DT
                for scheme in schemes:
                    f = fade
                    if scheme == "s10_atpc2":
                        f = apply_atpc(fade, 2.0)
                    elif scheme == "s10_atpc5":
                        f = apply_atpc(fade, 5.0)
                    step, st = observe(noise - f, scheme)
                    stride = int(step / DT)
                    # a coarse sample counts as active if any 10 s sample in its interval was active
                    act = active[: len(st["drop"]) * stride].reshape(-1, stride).any(axis=1)
                    dil = int(cfg["detect_window_min"] * 60 / step)
                    act_d = np.convolve(act.astype(int), np.ones(dil + 1, int))[: len(act)] > 0
                    tt_s = tt[: len(act) * stride].reshape(-1, stride)[:, -1]
                    for d in ("drop", "var"):
                        for t_thr in thr[f"{scheme}:{d}"]:
                            i = first_alarm(st[d], t_thr, act_d)
                            ev_rows.append({"pool": pool_name, "scenario": scen, "ne": ne, "link": int(m.link),
                                            "band": m.band, "L_m": m.L_m, "scheme": scheme, "detector": d,
                                            "thr": t_thr, "detected": i >= 0,
                                            "t_alarm_s": tt_s[i] if i >= 0 else np.nan,
                                            "t_first_s": m.t_first_s, "maxA": m[f"maxA_{ne}"], "maxS": m.maxS,
                                            "noise_chunk": str(cid), "truncated": need > len(arr)})
        print(f"  {pool_name}/{scen}: injected {len(meta)} links x {len(cfg['ne_scenarios'])} ne scenarios")
    return ev_rows


def main():
    cfg = load_config(CFG_NAME)
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(cfg["seed"])
    style()
    nums = {}
    schemes = cfg["schemes"]
    thr = {k: np.array(v) for k, v in cfg["thresholds"].items() if not k.startswith("_")}

    noise_kind = "openmrg"
    try:
        x, meta = load_openmrg(cfg, cfg["n_sublinks"], rng)
        meta.to_csv(OUT / "openmrg_sublinks_used.csv")
        wet = wet_mask_from_gauges(x.index, cfg)
        nums["det.noise.n_sublinks"] = (x.shape[1], "count", "OpenMRG sub-links used as noise")
        nums["det.noise.freq_median_ghz"] = (float(meta.Frequency_GHz.median()), "GHz", "Median frequency of those sub-links")
        nums["det.noise.length_median_km"] = (float(meta.Length_km.median()), "km", "Median length of those sub-links")
        nums["det.noise.wet_time_fraction"] = (float(wet.mean()), "fraction", "Share of OpenMRG time within the rain mask")
        split = pd.Timestamp(cfg["screen_split"])
        tr_mask, te_mask = x.index < split, x.index >= split
        chunks = dry_chunks(x, wet, cfg["min_chunk_h"] * 3600)
        wet_chunks = dry_chunks(x, ~wet, cfg["min_chunk_h"] * 3600)  # rainy periods for confounder FAR
        train = dry_chunks(x[tr_mask], wet[tr_mask], cfg["min_chunk_h"] * 3600)
        test = dry_chunks(x[te_mask], wet[te_mask], cfg["min_chunk_h"] * 3600)
        keep, rate = screen(train, cfg)
        rate.rename("june_alarm_rate_per_day").to_csv(OUT / "screening_rates.csv")
        screened = [c for c in test if c[0] in keep]
        print(f"OpenMRG: {x.shape[1]} sublinks, {len(chunks)} dry chunks, "
              f"{sum(len(c[2]) for c in chunks) * DT / 86400:.1f} dry link-days, "
              f"{sum(len(c[2]) for c in wet_chunks) * DT / 86400:.1f} wet link-days; wet fraction {wet.mean():.2f}; "
              f"screening keeps {len(keep)} of {len(rate)} sublinks, "
              f"{sum(len(c[2]) for c in screened) * DT / 86400:.1f} screened test link-days")
        nums["det.screen.n_kept"] = (len(keep), "count", "Sub-links kept after June screening")
        nums["det.screen.n_ranked"] = (len(rate), "count", "Sub-links with enough June dry data to rank")
        nums["det.screen.test_link_days"] = (sum(len(c[2]) for c in screened) * DT / 86400, "link-days",
                                             "Dry July-August noise on screened sub-links")
    except Exception as exc:  # documented fallback
        print("OpenMRG unavailable, using synthetic noise:", exc)
        noise_kind = "synthetic"
        chunks = synthetic_chunks(cfg["n_synthetic"], 5 * 86400, rng)
        wet_chunks, screened = [], []
    pools = {"all": chunks}
    if screened:
        pools["screened"] = screened
    nums["det.noise.dry_link_days"] = (sum(len(c[2]) for c in chunks) * DT / 86400, "link-days", f"Dry noise analysed ({noise_kind})")
    nums["det.noise.n_dry_chunks"] = (len(chunks), "count", "Dry chunks used")
    sd = np.array([np.std(c[2]) for c in chunks])
    nums["det.noise.std_median_db"] = (float(np.median(sd)), "dB", "Median per-chunk std of dry RSL-TSL (10 s)")
    nums["det.noise.std_p90_db"] = (float(np.percentile(sd, 90)), "dB", "90th percentile per-chunk std of dry RSL-TSL")

    # ---------------- False alarm rates ----------------
    far_rows = []
    for label, pool in [("all", chunks), ("screened", screened), ("wet", wet_chunks)]:
        if pool:
            far_rows += far_table(pool, schemes, thr, cfg, label)
    far = pd.DataFrame(far_rows)
    far.to_csv(OUT / "far.csv", index=False)

    # ---------------- Inject signatures ----------------
    ev_rows = []
    for pname, pool in pools.items():
        ev_rows += inject(pool, cfg, thr, schemes, rng, pname)
    ev = pd.DataFrame(ev_rows)
    ev.to_csv(OUT / "events.csv.gz", index=False)

    # ---------------- ROC and operating points ----------------
    roc = (ev.groupby(["pool", "scenario", "ne", "scheme", "detector", "thr"]).detected.mean().rename("pd").reset_index()
           .merge(far[far.noise.isin(["all", "screened"])].rename(columns={"noise": "pool"})
                  [["pool", "scheme", "detector", "thr", "far_per_link_day"]], on=["pool", "scheme", "detector", "thr"]))
    roc.to_csv(OUT / "roc.csv", index=False)
    ops = []
    for (pool, scen, ne, scheme, d), g in roc.groupby(["pool", "scenario", "ne", "scheme", "detector"]):
        for target in cfg["far_targets_per_link_day"]:
            ok = g[g.far_per_link_day <= target]
            base = {"pool": pool, "scenario": scen, "ne": ne, "scheme": scheme, "detector": d, "far_target": target}
            if ok.empty:
                ops.append({**base, "thr": np.nan, "pd": 0.0, "far": np.nan})
                continue
            best = ok.sort_values(["pd", "thr"], ascending=[True, False]).iloc[-1]
            ops.append({**base, "thr": best.thr, "pd": best["pd"], "far": best.far_per_link_day})
    ops = pd.DataFrame(ops)
    # Detection among physically affected links (peak mean loss >= 1 dB or scintillation >= 0.3 dB)
    aff = []
    for _, o in ops.iterrows():
        e = ev[(ev.pool == o.pool) & (ev.scenario == o.scenario) & (ev["ne"] == o["ne"]) & (ev.scheme == o.scheme) &
               (ev.detector == o.detector) & (ev.thr == (o.thr if np.isfinite(o.thr) else -1))]
        strong = (e.maxA >= 1.0) | (e.maxS >= 0.3)
        aff.append(e[strong].detected.mean() if len(e) and strong.any() else 0.0)
    ops["pd_affected"] = aff
    ops.to_csv(OUT / "operating_points.csv", index=False)
    with pd.option_context("display.width", 200):
        print(ops[ops.far_target == cfg["far_targets_per_link_day"][1]].to_string())

    # delays at each operating point
    delay_rows = []
    for _, o in ops.iterrows():
        if not np.isfinite(o.thr):
            continue
        e = ev[(ev.pool == o.pool) & (ev.scenario == o.scenario) & (ev["ne"] == o["ne"]) & (ev.scheme == o.scheme) &
               (ev.detector == o.detector) & (ev.thr == o.thr) & ev.detected]
        dl = (e.t_alarm_s - e.t_first_s) / 60
        delay_rows.append({**o.to_dict(), "n_det": len(e), "delay_med_min": dl.median(),
                           "delay_p10_min": dl.quantile(0.1), "delay_p90_min": dl.quantile(0.9)})
    delays = pd.DataFrame(delay_rows)
    delays.to_csv(OUT / "delays.csv", index=False)

    for _, o in ops.iterrows():
        k = f"det.{o.pool}.{o.scenario}.{o['ne']}.{o.scheme}.{o.detector}.far{o.far_target:g}"
        nums[k + ".pd"] = (float(o["pd"]), "fraction", "Share of crossed links detected at the FAR target (per link-day)")
        nums[k + ".pd_affected"] = (float(o.pd_affected), "fraction",
                                    "Share detected among links with peak loss >= 1 dB or scintillation >= 0.3 dB")
        nums[k + ".thr"] = (float(o.thr) if np.isfinite(o.thr) else None, "dB or ratio", "Threshold at the FAR target")
    for _, r in delays.iterrows():
        k = f"det.{r.pool}.{r.scenario}.{r['ne']}.{r.scheme}.{r.detector}.far{r.far_target:g}"
        nums[k + ".delay_med_min"] = (float(r.delay_med_min) if np.isfinite(r.delay_med_min) else None, "min",
                                      "Median delay from fire reaching the link ground track to alarm")
    for (lab, scheme, d), g in far.groupby(["noise", "scheme", "detector"]):
        for _, r in g.iterrows():
            nums[f"conf.far.{lab}.{scheme}.{d}.thr{r.thr:g}"] = (float(r.far_per_link_day), "per link-day",
                                                               f"False alarm rate on {lab} OpenMRG noise")

    localization(ev, ops, cfg, nums)
    figures(roc, far, ev, ops, delays, cfg)
    record(nums, "src/run_detection.py", f"configs/{CFG_NAME}")


def main_pool(ops):
    return "screened" if (ops.pool == "screened").any() else "all"


def localization(ev, ops, cfg, nums):
    """How well alarms on several links locate the fire. Each alarmed link places the fire at its
    midpoint; we report the error to the true first crossing point, and fit a plane t = a + b x + c y
    to alarm times to estimate the spread direction and speed (compared with the same fit to truth)."""
    links = pd.read_csv(RESULTS / "geometry" / "links.csv")
    target, pool = cfg["main_far_target"], main_pool(ops)
    rows = []
    for scen in cfg["spread_scenarios"]:
        meta = pd.read_csv(RESULTS / "crossings" / f"links_{scen}.csv").set_index("link")
        first = []
        for d in ("drop", "var"):
            o = ops[(ops.pool == pool) & (ops.scenario == scen) & (ops["ne"] == "lab_peak") & (ops.scheme == "s10") &
                    (ops.far_target == target) & (ops.detector == d)]
            if o.empty or not np.isfinite(o.thr.iloc[0]):
                continue
            first.append(ev[(ev.pool == pool) & (ev.scenario == scen) & (ev["ne"] == "lab_peak") & (ev.scheme == "s10") &
                            (ev.detector == d) & (ev.thr == o.thr.iloc[0]) & ev.detected][["link", "t_alarm_s", "L_m"]])
        if not first:
            continue
        e = pd.concat(first).groupby("link").agg(t_alarm_s=("t_alarm_s", "min"), L_m=("L_m", "first")).reset_index()
        if len(e) < 4:
            rows.append({"scenario": scen, "n_alarms": len(e)})
            continue
        mx = links.loc[e.link, ["x1", "x2"]].mean(axis=1).to_numpy()
        my = links.loc[e.link, ["y1", "y2"]].mean(axis=1).to_numpy()
        tx, ty = meta.loc[e.link, "x_first_utm"].to_numpy(), meta.loc[e.link, "y_first_utm"].to_numpy()
        err = np.hypot(mx - tx, my - ty)

        def fit(x, y, t):
            A = np.c_[np.ones_like(x), x, y]
            coef, *_ = np.linalg.lstsq(A, t, rcond=None)
            s = coef[1:]
            return 3.6 / np.linalg.norm(s), (np.degrees(np.arctan2(s[0], s[1])) + 360) % 360

        sp_a, az_a = fit(mx, my, e.t_alarm_s.to_numpy())
        sp_t, az_t = fit(tx, ty, meta.loc[e.link, "t_first_s"].to_numpy())
        rows.append({"scenario": scen, "n_alarms": len(e), "median_err_km": np.median(err) / 1e3,
                     "p90_err_km": np.percentile(err, 90) / 1e3, "median_L_km": np.median(e.L_m) / 1e3,
                     "speed_alarm_kmh": sp_a, "az_alarm_deg": az_a, "speed_true_kmh": sp_t, "az_true_deg": az_t,
                     "median_alarm_lag_min": float(np.median(e.t_alarm_s.to_numpy() - meta.loc[e.link, "t_first_s"].to_numpy()) / 60)})
    loc = pd.DataFrame(rows)
    loc.to_csv(OUT / "localization.csv", index=False)
    print(loc.to_string())
    units = {"n_alarms": "count", "median_err_km": "km", "p90_err_km": "km", "median_L_km": "km", "speed_alarm_kmh": "km/h",
             "az_alarm_deg": "deg", "speed_true_kmh": "km/h", "az_true_deg": "deg", "median_alarm_lag_min": "min"}
    for _, r in loc.iterrows():
        for c, u in units.items():
            if c in r and pd.notna(r[c]):
                nums[f"det.loc.{r.scenario}.{c}"] = (float(r[c]), u, f"Localization ({pool} pool, s10, FAR {target:g}/link-day): {c}")


NAMES = {"s10": "10 s, 0.3 dB", "m1": "1 min, 0.3 dB", "mm15": "15 min min/max, 1 dB",
         "s10_atpc2": "10 s RSL only, ATPC 2 dB", "s10_atpc5": "10 s RSL only, ATPC 5 dB"}
COLS = {"s10": OI["blue"], "m1": OI["green"], "mm15": OI["vermillion"], "s10_atpc2": OI["purple"], "s10_atpc5": OI["orange"]}


def figures(roc, far, ev, ops, delays, cfg):
    style()
    pool = main_pool(ops)
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.6), sharex=True, sharey=True)
    for i, scen in enumerate(cfg["spread_scenarios"]):
        for j, d in enumerate(["drop", "var"]):
            ax = axes[i, j]
            g = roc[(roc.pool == "all") & (roc.scenario == scen) & (roc["ne"] == "lab_peak") & (roc.scheme == "s10") &
                    (roc.detector == d)].sort_values("far_per_link_day")
            ax.plot(np.maximum(g.far_per_link_day, 1e-4), g["pd"], color=OI["grey"], lw=1.2, marker="o", ms=2,
                    label="10 s, unscreened links")
            for scheme in cfg["schemes"]:
                for ne, ls in [("lab_peak", "-"), ("field_bound", "--")]:
                    g = roc[(roc.pool == pool) & (roc.scenario == scen) & (roc["ne"] == ne) & (roc.scheme == scheme) &
                            (roc.detector == d)].sort_values("far_per_link_day")
                    ax.plot(np.maximum(g.far_per_link_day, 1e-4), g["pd"], color=COLS[scheme], ls=ls, marker="o", ms=2.5,
                            label=NAMES[scheme] if ne == "lab_peak" else None)
            for tgt in cfg["far_targets_per_link_day"]:
                ax.axvline(tgt, color=OI["grey"], lw=0.8, ls=":")
            ax.set_xscale("log")
            ax.set_xlim(8e-5, 30)
            ax.set_ylim(0, 0.6)
            ax.set_title(f"'{scen}' spread, {'drop below baseline' if d == 'drop' else 'variance jump'} detector", fontsize=10)
            if i == 1:
                ax.set_xlabel("False alarms per link-day on dry OpenMRG noise")
            if j == 0:
                ax.set_ylabel("Share of crossed links detected")
    h, l = axes[0, 0].get_legend_handles_labels()
    h += [plt.Line2D([], [], color="k"), plt.Line2D([], [], color="k", ls="--")]
    l += ["Lab-peak flame ne", "Field-bound flame ne"]
    fig.suptitle("Detection versus false alarms for simulated crossings injected into real link noise "
                 f"({pool} sub-links; 1e-4 means none observed)", fontsize=10.5)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=8)
    savefig(fig, "det_roc")

    target = cfg["main_far_target"]
    fig, ax = plt.subplots(figsize=(7.8, 3.8))
    bins = np.arange(-60, 721, 30)
    for scheme, d, col in [("s10", "var", OI["blue"]), ("s10", "drop", OI["vermillion"]), ("mm15", "var", OI["green"])]:
        o = ops[(ops.pool == pool) & (ops.scenario == "extreme") & (ops["ne"] == "lab_peak") & (ops.scheme == scheme) &
                (ops.detector == d) & (ops.far_target == target)]
        if o.empty or not np.isfinite(o.thr.iloc[0]):
            continue
        e = ev[(ev.pool == pool) & (ev.scenario == "extreme") & (ev["ne"] == "lab_peak") & (ev.scheme == scheme) &
               (ev.detector == d) & (ev.thr == o.thr.iloc[0]) & ev.detected]
        ax.hist(np.clip((e.t_alarm_s - e.t_first_s) / 60, -60, 719), bins=bins, histtype="step", lw=1.6, color=col,
                label=f"{NAMES[scheme]}, {d} > {o.thr.iloc[0]:g} (n = {len(e)})")
    ax.set_xlabel("Alarm time minus time the fire first reaches the link ground track (min)")
    ax.set_ylabel("Detected links")
    ax.set_title(f"Detection delay, 'extreme' spread, lab-peak ne, FAR {target:g} per link-day", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    savefig(fig, "det_delay")

    # False alarm rate in dry versus rainy periods (confounder)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, d in zip(axes, ["drop", "var"]):
        for lab, col, ls in [("screened", OI["blue"], "-"), ("all", OI["grey"], "-"), ("wet", OI["vermillion"], "--")]:
            for scheme, mk in [("s10", "o"), ("mm15", "s")]:
                g = far[(far.noise == lab) & (far.scheme == scheme) & (far.detector == d)]
                if g.empty:
                    continue
                ax.plot(g.thr, np.maximum(g.far_per_link_day, 1e-4), color=col, ls=ls, marker=mk, ms=3,
                        label=f"{ {'screened': 'Dry, screened links', 'all': 'Dry, all links', 'wet': 'Rainy periods, all links'}[lab]}, {NAMES[scheme]}")
        ax.set_yscale("log")
        ax.set_xlabel("Threshold (dB)" if d == "drop" else "Threshold (std ratio; dB for 15 min range)")
        ax.set_title("Drop detector" if d == "drop" else "Variance detector", fontsize=10)
    axes[0].set_ylabel("False alarms per link-day")
    axes[0].legend(fontsize=7, loc="upper right")
    fig.suptitle("OpenMRG false alarm rates: rain and erratic links dominate", fontsize=10.5)
    fig.tight_layout()
    savefig(fig, "det_far")


if __name__ == "__main__":
    main()
