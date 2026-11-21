"""Steps 6 and 7 (PROTOCOL §7, §8): kcf-robust's five rules, the margin field and the Gyeongbuk replay with closure
windows [C, max(C, A + tau)).

    python3 robust_window.py replay OUT            # 2 regions x 13 issues (25 Mar 2025 03-15 UTC)
    python3 robust_window.py twin WORK OUT         # 12 seeds x 2 issue offsets, yeongdeok_2025
    python3 robust_window.py score OUT             # tables: out/robust_window_*.json

Inputs, closure rasters and rules are kcf-robust's (lib.py, replay.inputs, twin.inputs; m*, r* from its
out/*_calibration.json, not recalibrated: amendment 2). New here:
  * arrival A per lattice pixel: the first detection disc covering the pixel centre when it is in the known area
    (time before the issue), else the central forecast F50 (minutes), else none (no reopening);
  * responder window: road cell closed on [C, max(C, A + tau)); rule b widens by m* on both sides (closes m* earlier,
    reopens m* later), c uses the dilated closure with the undilated arrival;
  * truth: [true arrival, true arrival + tau) (twin: simulator arrival; replay: reconstruction from the full disc record);
  * residents (rule a only): window only where an official reopening message, sent before the issue time and at or
    after A + tau, covers the cell (out/korea_reopen_messages_cells.json); otherwise permanent, as today;
  * margin field (research/kcf-idea-routing, keep variant, M = H) on rule a, perm and responder window: per (place,
    shelter) mu(0) against the slack L0 (end of the window that starts at 0)."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROB = REPO / "research/kcf-robust"
sys.path.insert(0, str(ROB))
import lib  # noqa: E402  (puts the product, kcf-replay, the twin and kcf-idea-routing on sys.path)
import analyze as AN  # noqa: E402
from margin_field import field as MF, pl  # noqa: E402
from wfg_roadlayer import engine  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import core, intervals as iv  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location("kcf_robust_" + name, ROB / (name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _shelter_job_last_only(job):
    """kcf-robust lib._shelter_job_last_only with the product's bounded witness (engine.witness_for): with reopening and
    no waitable nodes an earliest-arrival witness can need hours of looping and an intractable search."""
    snode, acc, origins = job
    inst = engine._W["inst"]
    inst.A = [[] for _ in range(len(inst.tail))]
    for j in engine._W["inc"].get(snode, []):
        inst.A[j] = list(acc)
    inst.AN, inst.IB = {}, {}
    fld = core.backward(inst)
    out = {}
    for on, ib in origins:
        inst.IB = {on: ib}
        S = core.issue_set(fld, on)
        res = {"set": [list(p) for p in S], "w_last": None, "w_first": None}
        if S:
            res["w_last"] = engine._wlegs(engine.witness_for(fld, on, S[-1][1], budget=300_000))
        out[on] = res
    inst.IB = {}
    return snode, out, fld.stats["pushes"]


engine._shelter_job = _shelter_job_last_only
RPL = _load("replay")
TW = _load("twin")
SC = _load("score")
TAU_MIN = json.load(open(HERE / "out/tau.json"))["frozen"]["tau_min"]
H, DWELL = lib.HORIZON_S, lib.DWELL
KST = timezone(timedelta(hours=9))
cx, cy = lib.cell_centres()


def first_cover_ts(discs):
    """Per lattice pixel: earliest disc time ('ts', epoch s) with the pixel centre inside the disc."""
    ds = [dict(d, ts=d["ts"] if "ts" in d else (d["t"].timestamp() if hasattr(d["t"], "timestamp") else d["t"])) for d in discs]
    return AN.first_cut_times(ds, cx, cy)


def arrival_rel(cover_ts, T, m_f50):
    """Seconds after T: known area -> first cover time (<= 0); else F50; else nan."""
    t = T.timestamp()
    a = np.where(cover_ts < t, cover_ts - t, np.nan)
    f = np.where(np.isfinite(m_f50), m_f50 * 60.0, np.nan)
    return np.where(np.isfinite(a), a, f)


def open_from(rid, close_s, A_pix, tau_min=TAU_MIN, plus_s=0, only=None):
    """road cell -> reopening second r = ceil(A + tau) + plus_s for closed cells with an arrival (and in `only`)."""
    pm = lib.road_pixel_map(rid)
    out = {}
    for c in close_s:
        if only is not None and c not in only:
            continue
        a = A_pix[pm[c]]
        if math.isfinite(a):
            out[c] = int(math.ceil(a + tau_min * 60.0)) + plus_s
    return out


def run_product_w(rid, close_s, open_s, T, workers=1):  # 1: the sandbox here has no POSIX semaphores
    reg = lib.region(rid)
    cfg = lib.settings()
    fire = lib._Fire(dict(close_s), T, H)
    inst = engine.build_instance(reg.road, close_s, H, open_s)
    jobs_by = defaultdict(set)
    for o in reg.origins:
        if o["node"] is None or not o["checkable"]:
            continue
        for s in reg.cands.get(o["id"], []):
            jobs_by[s["node"]].add(o["node"])
    jobs = [(sn, engine.accept(reg.road, close_s, sn, H, DWELL, open_s=open_s),
             [(on, engine.origin_closure(reg.road, close_s, on, H, open_s=open_s)) for on in sorted(ons)]) for sn, ons in sorted(jobs_by.items())]
    results = engine.run_passes(reg.road, inst, jobs, workers)
    rows = engine.assemble(reg, fire, cfg, inst, results, close_s)
    return rows, inst, jobs


def summarise(rows):
    out = lib.summarise_rows(rows)
    for r in rows:
        if not r["refusal"]:
            x = out[r["origin"]["id"]]
            x["windows"] = [list(w) for w in r["windows"]]
            last = r.get("last")
            if last and last["w_last"]:
                es = [l[1] for l in last["w_last"]["legs"] if l[0] == "EDGE"]
                x["loop"] = len(es) != len(set(es))
                x["earliest"] = last["w_last"].get("earliest", True)
    return out


class TruthW(SC.Truth):
    def __init__(self, rid, close_s, open_s):
        self.road = lib.region(rid).road
        self.close = {int(c): int(b) for c, b in close_s.items()}
        self.open = {int(c): int(r) for c, r in open_s.items()}
        self.inst = engine.build_instance(self.road, self.close, H, self.open)
        self.H = H
        self._acc = {}

    def accept(self, sn):
        if sn not in self._acc:
            self._acc[sn] = engine.accept(self.road, self.close, sn, self.H, DWELL, open_s=self.open)
        return self._acc[sn]

    def journey_ok(self, origin_node, shelter_node, depart, legs, arrival):
        if iv.contains(engine.origin_closure(self.road, self.close, origin_node, self.H, open_s=self.open), depart):
            return False, "origin"
        for kind, x, s, e in legs:
            if kind == "EDGE" and iv.contains(self.inst.B[x], s):
                return False, "edge"
            if kind == "WAIT" and iv.contains(self.inst.W[x], s):
                return False, "wait"
        if not iv.contains(self.accept(shelter_node), arrival):
            return False, "shelter"
        return True, ""


def margin_pairs(rid, inst, jobs):
    """Margin field (keep variant, M = H) per shelter pass: (origin node, shelter node, mu(0), L0)."""
    out = []
    for sn, acc, origins in jobs:
        inst.A = [[] for _ in range(len(inst.tail))]
        for j in lib.region(rid).road.inc_by_node.get(sn, []):
            inst.A[j] = list(acc)
        inst.AN = {}
        inst.IB = {on: ib for on, ib in origins}
        fld = MF.margin_field(inst, H)
        for on, _ in origins:
            f = MF.issue_margin(fld, on)
            mu0 = int(pl.value(f, 0))
            lv0 = pl.level_set(f, 0)
            L0 = lv0[0][1] if lv0 and lv0[0][0] == 0 else -1
            out.append([int(on), int(sn), mu0, int(L0)])
        inst.IB = {}
    return out


def rules_for(rid, X, A_pix, cal, m_truth, A_truth, confirm=None):
    """{rule: (close_s, open_s)} for perm a (check), responder windows a..e and truth, residents a."""
    f50 = lib.close_s_from_minutes(rid, X["m_f50"])
    ca = lib.close_s_from_minutes(rid, X["m_a"])
    ms, rs = cal["m_star_s"], cal["r_star_km"]
    cb = TW.shift_close(f50, ms)
    cc = lib.close_s_from_minutes(rid, lib.dilate_minutes(X["m_f50"], rs))
    ce = lib.close_s_from_minutes(rid, X["e"]["90"][0])
    ct = lib.close_s_from_minutes(rid, m_truth)
    R = {"a_perm": (ca, {}), "truth_perm": (ct, {}),
         "truth": (ct, open_from(rid, ct, A_truth)),
         "a": (ca, open_from(rid, ca, A_pix)), "b": (cb, open_from(rid, cb, A_pix, plus_s=ms)), "c": (cc, open_from(rid, cc, A_pix)),
         "d": (f50, open_from(rid, f50, A_pix)), "e": (ce, open_from(rid, ce, A_pix))}
    if confirm is not None:
        R["a_res"] = (ca, confirm(ca))
    return R


def do_case(rid, T, X, A_pix, cal, m_truth, A_truth, confirm, fp, margin=True):
    t0 = time.time()
    res = {"rid": rid, "issue_utc": T.isoformat(), "class": X["cls"], "tau_min": TAU_MIN, "rules": {}, "close_s": {}, "open_s": {}, "n_open": {}}
    for k, (cl, op) in rules_for(rid, X, A_pix, cal, m_truth, A_truth, confirm).items():
        t1 = time.time()
        rows, inst, jobs = run_product_w(rid, cl, op, T)
        print("  ", fp.stem, k, len(cl), len(op), round(time.time() - t1, 1), "s", flush=True)
        res["rules"][k] = summarise(rows)
        res["close_s"][k] = {str(c): b for c, b in cl.items()}
        res["open_s"][k] = {str(c): r for c, r in op.items()}
        res["n_open"][k] = {"closed": len(cl), "reopen_within_H": sum(1 for c, r in op.items() if cl[c] < r <= H),
                            "burned_over_at_issue": sum(1 for c, r in op.items() if r <= max(cl[c], 0))}
        if margin and k in ("a_perm", "a"):
            res.setdefault("margin", {})[k] = margin_pairs(rid, inst, jobs)
    res["seconds"] = round(time.time() - t0, 1)
    fp.write_text(json.dumps(res))
    print(fp.stem, X["cls"], res["seconds"], "s", res["n_open"]["a"], flush=True)


# ------------------------------------------------------------------------------------------------ replay
def replay(out, only_rid=None, hours=None):
    out = Path(out); (out / "replay").mkdir(parents=True, exist_ok=True)
    cal = json.loads((ROB / "out/replay_calibration.json").read_text())
    discs = lib.load_discs()
    full = json.loads((REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]
    for d in full:
        d["ts"] = datetime.fromisoformat(d["t_utc"]).timestamp()
    cover_full = AN.first_cut_times(full, cx, cy)
    msgs = json.loads((HERE / "out/korea_reopen_messages_cells.json").read_text())
    for rid in lib.REGIONS:
        if only_rid and rid != only_rid:
            continue
        pm = lib.road_pixel_map(rid)
        for T in lib.REPLAY_ISSUES:
            if hours and T.hour not in hours:
                continue
            fp = out / "replay" / ("%s_%s.json" % (rid, T.strftime("%H")))
            if fp.exists():
                continue
            X = RPL.inputs(discs, T)
            m_tr = RPL.recon_minutes(T)
            A_truth = np.where(np.isfinite(cover_full), cover_full - T.timestamp(), np.nan)
            known = np.where(cover_full < T.timestamp(), cover_full, np.inf)   # only discs before T are known to the system
            A_pix = arrival_rel(known, T, X["m_f50"])

            def confirm(ca, A_pix=A_pix, T=T):
                ok = set()
                for m in msgs:
                    u = datetime.strptime(m["effective_kst"], "%Y-%m-%d %H:%M").replace(tzinfo=KST).timestamp() - T.timestamp()
                    if u > 0:
                        continue
                    cells = set(m["lattice_cells"])
                    for c in ca:
                        a = A_pix[pm[c]]
                        if pm[c] in cells and math.isfinite(a) and a + TAU_MIN * 60 <= u:
                            ok.add(c)
                return open_from(rid, ca, A_pix, only=ok)
            do_case(rid, T, X, A_pix, cal, m_tr, A_truth, confirm, fp)


# ------------------------------------------------------------------------------------------------ twin
def twin(work, out, seeds=None):
    out = Path(out); (out / "twin").mkdir(parents=True, exist_ok=True)
    cal = json.loads((ROB / "out/twin_calibration.json").read_text())
    sch = TW.TL.pass_schedule(REPO / "research/kcf-replay/fire_discs.json")
    for seed, h in TW.pairs():
        if seeds is not None and seed not in seeds:
            continue
        fp = out / "twin" / ("s%d_h%d.json" % (seed, h))
        if fp.exists():
            continue
        X = TW.inputs(work, seed, h, sch)
        T = X["T"]
        arr = np.load(Path(work) / ("truth_arrival_s_seed%d.npy" % seed)).ravel()
        A_truth = np.where(np.isfinite(arr), arr - (T - TW.RT.T_IGN).total_seconds(), np.nan)
        t_end = TW.RT.T_IGN + timedelta(hours=max(TW.RT.ISSUE_OFFSETS_H))
        dets = TW.TL.detections(np.load(Path(work) / ("truth_arrival_s_seed%d.npy" % seed)), TW.RT.T_IGN, t_end, sch, seed, perfect=False)
        known = [d for d in dets if d["t"] < T]
        cov = first_cover_ts([dict(x=d["x"], y=d["y"], r_m=d["r_m"], ts=d["t"].timestamp()) for d in known]) if known else np.full(cx.shape, np.inf)
        A_pix = arrival_rel(cov, T, X["m_f50"])
        do_case(TW.RID, T, X, A_pix, cal, X["m_truth"], A_truth, None, fp)


# ------------------------------------------------------------------------------------------------ scoring
def score(out):
    out = Path(out)
    res = {}
    for kind in ("twin", "replay"):
        files = sorted((out / kind).glob("*.json"))
        if not files:
            continue
        rows_w, rows_p, later, margin = [], [], [], {"a_perm": [], "a": []}
        for fp in files:
            R = json.loads(fp.read_text())
            rid = R["rid"]
            origins = {o["id"]: o["node"] for o in lib.region(rid).origins}
            truth_w = {"close_s": R["close_s"]["truth"], "rules": R["rules"]["truth"]}
            tr = TruthW(rid, R["close_s"]["truth"], R["open_s"]["truth"])
            # place rows against the window truth (rules a..e with windows)
            orig = SC.Truth
            SC.Truth = lambda rid_, close_s_, tr=tr: tr
            try:
                rows_w += SC.place_rows(rid, truth_w, {k: R["rules"][k] for k in "abcde"}, origins, fp.stem,
                                        {"cluster": fp.stem.split("_h")[0] if kind == "twin" else fp.stem[:-3], "issue": fp.stem})
            finally:
                SC.Truth = orig
            # current rule permanent vs permanent truth (reproduction of kcf-robust's a)
            rows_p += SC.place_rows(rid, {"close_s": R["close_s"]["truth_perm"], "rules": R["rules"]["truth_perm"]}, {"a": R["rules"]["a_perm"]},
                                    origins, fp.stem, {"cluster": fp.stem})
            # step 7: later windows
            for pid, p in R["rules"]["a_perm"].items():
                if p["refused"]:
                    continue
                Lp = p["L"]
                row = {"case": fp.stem, "place": pid, "L_perm": Lp}
                for k in ("a", "a_res"):
                    if k in R["rules"]:
                        w = R["rules"][k][pid]
                        row["L_" + k] = w["L"]; row["windows_" + k] = len(w.get("windows", []))
                        row["later_" + k] = w["L"] > Lp
                later.append(row)
            for k in margin:
                margin[k] += [[fp.stem] + x for x in R.get("margin", {}).get(k, [])]
        summ = {k: SC.summary(rows_w, k) for k in "abcde"}
        boot = SC.bootstrap(rows_w, "abcde", "cluster")
        perm_a = SC.summary(rows_p, "a")
        lat = {"place_issues": len(later), "places": len({r["place"] for r in later})}
        for k in ("a", "a_res"):
            if later and ("later_" + k) in later[0]:
                lat[k] = {"place_issues_with_later_window": sum(r["later_" + k] for r in later),
                          "places_with_later_window": len({r["place"] for r in later if r["later_" + k]}),
                          "place_issues_with_more_than_one_window": sum(r["windows_" + k] > 1 for r in later),
                          "place_issues_gaining_any_departure": sum(r["L_perm"] < 0 <= r["L_" + k] for r in later),
                          "median_gain_min": float(np.median([(r["L_" + k] - r["L_perm"]) / 60 for r in later if r["later_" + k]])) if any(r["later_" + k] for r in later) else None}
        mg = {}
        for k, xs in margin.items():
            xs = [x for x in xs if x[3] >= 0]
            differ = [x for x in xs if x[3] != x[4] and x[3] != H]
            mg[k] = {"pairs_feasible_at_0": len(xs), "mu0_eq_L0": sum(x[3] == x[4] for x in xs), "mu0_eq_M": sum(x[3] == H for x in xs),
                     "differ": len(differ), "mu0_below_L0": sum(x[3] < x[4] for x in xs),
                     "max_abs_diff_s": max((abs(x[3] - x[4]) for x in differ), default=0),
                     "examples": differ[:5]}
        res[kind] = {"cases": len(files), "summary_window": summ, "bootstrap_window": boot, "a_perm_vs_perm_truth": perm_a,
                     "later_windows": lat, "margin_vs_slack": mg}
        SC.write_csv(out / ("robust_window_%s_place_rules.csv" % kind), rows_w)
        if later:
            SC.write_csv(out / ("reopen_later_windows_%s.csv" % kind), later)
    (out / "robust_window.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: {"summary": {r: {x: v[r][x] for x in ("advised", "failed", "missed", "false", "lead_median_min")} for r in "abcde" for v in [res[k]["summary_window"]]},
                          "perm_a": {x: res[k]["a_perm_vs_perm_truth"][x] for x in ("advised", "failed", "missed", "false")},
                          "later": res[k]["later_windows"], "margin": {m: {x: y for x, y in v.items() if x != "examples"} for m, v in res[k]["margin_vs_slack"].items()}}
                      for k in res}, indent=1, default=float))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "replay":
        replay(sys.argv[2], *(sys.argv[3:4] or [None]), [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None)
    elif cmd == "twin":
        twin(sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None)
    else:
        score(sys.argv[2])
