"""Twin experiment for the five rules (PROTOCOL.md sections 3 and 5.1).

    python3 twin.py phase1 WORK OUT        # rasters, product runs (truth, a, d, e), compiled curves; per pair, resumable
    python3 twin.py calibrate OUT          # m*, r* (equal caution, no truth used)
    python3 twin.py phase2 WORK OUT        # product runs b(m*), c(r*)
    (scoring: score.py)

WORK = the folder written by research/kcf-validate/twin/run_twin.py make (truth arrival per seed, rasters).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import reachpass as RP  # noqa: E402
import run_twin as RT  # noqa: E402
import twin_lib as TL  # noqa: E402

RID = "yeongdeok_2025"
M_GRID = list(range(0, lib.HORIZON_S + 1, 300))           # timing shift levels for the curves (s)
R_GRID = [round(0.125 * k, 3) for k in range(0, 121)]     # reach levels (km), 0..15
P_LIST = ("50", "80", "90", "95", "99")


def pairs():
    return RT.pairs()


def tag_of(seed, h):
    return "s%d_h%d" % (seed, h)


def shift_close(close_s, m):
    return {c: max(0, b - m) for c, b in close_s.items()}


def shift_array(arr, m):
    out = arr.copy()
    f = out < RP.NONE
    out[f] = np.maximum(out[f] - m, 0)
    return out


def inputs(work, seed, h, sch):
    T = RT.T_IGN + timedelta(hours=h)
    arr = np.load(Path(work) / ("truth_arrival_s_seed%d.npy" % seed))
    t_end = RT.T_IGN + timedelta(hours=max(RT.ISSUE_OFFSETS_H))
    dets = TL.detections(arr, RT.T_IGN, t_end, sch, seed, perfect=False)
    d = lib.known_distance_m(dets, T)
    r5, r8, cls, info = lib.MA.curve("MEASURED", dets, T, 8)
    m_truth = RT.truth_minutes(arr, T).ravel()
    m_a = lib.minutes_r90(d, r5, r8)
    ref = RT.geotiff.read(Path(work) / ("system_%s.tif" % tag_of(seed, h))).data[::-1].ravel()
    assert np.array_equal(np.isinf(m_a), np.isinf(ref)) and np.array_equal(m_a[np.isfinite(m_a)], ref[np.isfinite(ref)]), \
        "CURRENT raster differs from the twin's system raster"
    m_f50 = lib.minutes_from_curve(d, lib.knots_r50(cls))
    e = {}
    for p in P_LIST:
        kn, src = lib.knots_expected(T, "KR", p)
        e[p] = (lib.minutes_from_curve(d, kn), kn, src)
    a80 = [r for r in json.loads((lib.REPO / "research/kcf-margin/numbers.json").read_text())["table"]
           if r["fire_set"] == "all28" and r["alpha"] == 0.2 and r["cls"] == cls]
    k80 = lib.knots_measured(*[x["R_km"] for x in sorted(a80, key=lambda r: r["h"])])
    m_a80 = lib.minutes_from_curve(d, k80)
    return dict(T=T, cls=cls, r5=r5, r8=r8, m_truth=m_truth, m_a=m_a, m_f50=m_f50, e=e, m_a80=m_a80, k80=k80)


def phase1(work, out):
    out = Path(out); (out / "twin").mkdir(parents=True, exist_ok=True)
    sch = TL.pass_schedule(lib.REPO / "research/kcf-replay/fire_discs.json")
    reg = lib.region(RID)
    g = RP.Graph(reg.road)
    for seed, h in pairs():
        tag = tag_of(seed, h)
        fp = out / "twin" / (tag + ".json")
        if fp.exists():
            continue
        t0 = time.time()
        X = inputs(work, seed, h, sch)
        T = X["T"]
        closes = {"truth": lib.close_s_from_minutes(RID, X["m_truth"]), "a": lib.close_s_from_minutes(RID, X["m_a"]),
                  "d": lib.close_s_from_minutes(RID, X["m_f50"]), "e": lib.close_s_from_minutes(RID, X["e"]["90"][0])}
        res = {"seed": seed, "h": h, "issue_utc": T.isoformat(), "class": X["cls"], "e_source": X["e"]["90"][2],
               "e_knots": X["e"]["90"][1], "r50_knots": lib.knots_r50(X["cls"]), "rules": {}, "close_s": {}}
        for k, cl in closes.items():
            rows, _ = lib.run_product(RID, cl, T)
            res["rules"][k] = lib.summarise_rows(rows)
            res["close_s"][k] = {str(c): b for c, b in cl.items()}
        # compiled curves: b (shift of F50), c (dilation of F50), e over p, a at R80, and a / truth at level 0
        base = lib.close_array_from_minutes(RID, X["m_f50"])
        curves = {}
        lv = np.stack([shift_array(base, m) for m in M_GRID])
        curves["b"] = RP.latest_by_level(g, reg, lv, lib.HORIZON_S, lib.DWELL)[0]
        lv = np.stack([lib.close_array_from_minutes(RID, lib.dilate_minutes(X["m_f50"], r)) for r in R_GRID])
        curves["c"] = RP.latest_by_level(g, reg, lv, lib.HORIZON_S, lib.DWELL)[0]
        lv = np.stack([lib.close_array_from_minutes(RID, X["e"][p][0]) for p in P_LIST]
                      + [lib.close_array_from_minutes(RID, X["m_a80"]), lib.close_array_from_minutes(RID, X["m_a"]),
                         lib.close_array_from_minutes(RID, X["m_truth"])])
        curves["other"] = RP.latest_by_level(g, reg, lv, lib.HORIZON_S, lib.DWELL, nested=False)[0]
        np.savez_compressed(out / "twin" / (tag + "_curves.npz"),
                            **{"%s|%s" % (k, oid): v for k, cv in curves.items() for oid, v in cv.items()})
        res["curve_axes"] = {"b_m_s": M_GRID, "c_r_km": R_GRID, "other": ["e%s" % p for p in P_LIST] + ["a80", "a", "truth"]}
        res["a80_knots"] = X["k80"]
        res["seconds"] = round(time.time() - t0, 1)
        fp.write_text(json.dumps(res))
        print(tag, X["cls"], res["seconds"], "s", flush=True)


def load_curves(out, tag):
    z = np.load(Path(out) / "twin" / (tag + "_curves.npz"))
    cur = {}
    for k in z.files:
        kind, oid = k.split("|", 1)
        cur.setdefault(kind, {})[oid] = z[k]
    return cur


def S_of(Ls):
    return int(sum(int(L) + 1 for L in Ls))


def calibrate(out):
    """m*, r*: smallest grid value with S(rule) <= S(a) over all evaluated place-pairs (PROTOCOL section 3)."""
    out = Path(out)
    reg = lib.region(RID)
    g = RP.Graph(reg.road)
    sch = TL.pass_schedule(lib.REPO / "research/kcf-replay/fire_discs.json")
    work = out / "twin"
    S_a = 0
    tags, ev = [], {}
    for seed, h in pairs():
        tag = tag_of(seed, h)
        res = json.loads((work / (tag + ".json")).read_text())
        refused = {pid for k in res["rules"] for pid, r in res["rules"][k].items() if r["refused"]}
        ev[tag] = sorted(pid for pid in res["rules"]["a"] if pid not in refused)
        S_a += S_of(res["rules"]["a"][pid]["L"] for pid in ev[tag])
        tags.append(tag)
    curves = {t: load_curves(out, t) for t in tags}

    def S_rule(kind, k):
        return sum(S_of(curves[t][kind][pid][k] for pid in ev[t]) for t in tags)

    Sb = [S_rule("b", k) for k in range(len(M_GRID))]
    Sc = [S_rule("c", k) for k in range(len(R_GRID))]
    # PROTOCOL amendment 2: if no grid value reaches S(a), take the grid value with the smallest S and report the gap
    kb = next((k for k, s in enumerate(Sb) if s <= S_a), None)
    kc = next((k for k, s in enumerate(Sc) if s <= S_a), None)
    reached = {"b": kb is not None, "c": kc is not None}
    if kb is None:
        kb = int(np.argmin(Sb))
    if kc is None:
        kc = int(np.argmin(Sc))
    # refine m on the 60 s grid inside (M_GRID[kb-1], M_GRID[kb]]
    m_star = M_GRID[kb]
    if kb > 0 and reached["b"]:
        fine = list(range(M_GRID[kb - 1] + 60, M_GRID[kb], 60))
        if fine:
            Sf = [0] * len(fine)
            for seed, h in pairs():
                tag = tag_of(seed, h)
                X = inputs(sch=sch, work=WORK_DIR, seed=seed, h=h)
                base = lib.close_array_from_minutes(RID, X["m_f50"])
                lv = np.stack([shift_array(base, m) for m in fine])
                best = RP.latest_by_level(g, reg, lv, lib.HORIZON_S, lib.DWELL)[0]
                for i in range(len(fine)):
                    Sf[i] += S_of(best[pid][i] for pid in ev[tag])
            for i, m in enumerate(fine):
                if Sf[i] <= S_a:
                    m_star = m
                    break
    cal = {"S_a": S_a, "m_star_s": m_star, "r_star_km": R_GRID[kc], "reached": reached, "S_b_at_m_star": Sb[kb], "S_c_at_r_star": Sc[kc], "n_place_pairs": sum(len(v) for v in ev.values()),
           "S_b_curve": dict(zip(map(str, M_GRID), Sb)), "S_c_curve": dict(zip(map(str, R_GRID), Sc)),
           "mean_leave_by_a_min": S_a / sum(len(v) for v in ev.values()) / 60.0}
    (out / "twin_calibration.json").write_text(json.dumps(cal, indent=1))
    print({k: v for k, v in cal.items() if not k.endswith("curve")})


def phase2(work, out):
    out = Path(out)
    cal = json.loads((out / "twin_calibration.json").read_text())
    sch = TL.pass_schedule(lib.REPO / "research/kcf-replay/fire_discs.json")
    for seed, h in pairs():
        tag = tag_of(seed, h)
        fp = out / "twin" / (tag + "_bc.json")
        if fp.exists():
            continue
        X = inputs(work, seed, h, sch)
        f50 = lib.close_s_from_minutes(RID, X["m_f50"])
        res = {"m_star_s": cal["m_star_s"], "r_star_km": cal["r_star_km"], "rules": {}, "close_s": {}}
        for k, cl in (("b", shift_close(f50, cal["m_star_s"])),
                      ("c", lib.close_s_from_minutes(RID, lib.dilate_minutes(X["m_f50"], cal["r_star_km"])))):
            rows, _ = lib.run_product(RID, cl, X["T"])
            res["rules"][k] = lib.summarise_rows(rows)
            res["close_s"][k] = {str(c): b for c, b in cl.items()}
        fp.write_text(json.dumps(res))
        print(tag, "b,c done", flush=True)


WORK_DIR = None

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "phase1":
        phase1(sys.argv[2], sys.argv[3])
    elif cmd == "calibrate":
        WORK_DIR = sys.argv[2]
        calibrate(sys.argv[3])
    elif cmd == "phase2":
        phase2(sys.argv[2], sys.argv[3])
