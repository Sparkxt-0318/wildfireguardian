"""Score rules against a truth (PROTOCOL.md section 5). Used for the twin (truth = the twin's arrival raster) and,
labelled RECONSTRUCTED, for the replay (truth = the detection record).

    python3 score.py twin OUT
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from wfg_roadlayer import engine  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import intervals as iv  # noqa: E402

RULES = ("a", "b", "c", "d", "e")
NAMES = {"a": "CURRENT", "b": "TIME-ROBUST", "c": "REACH-ROBUST", "d": "FASTEST", "e": "FORECAST-AWARE"}


class Truth:
    def __init__(self, rid, close_s, H=lib.HORIZON_S):
        self.road = lib.region(rid).road
        self.close = {int(c): int(b) for c, b in close_s.items()}
        self.inst = engine.build_instance(self.road, self.close, H)
        self.H = H
        self._acc = {}

    def accept(self, sn):
        if sn not in self._acc:
            self._acc[sn] = engine.accept(self.road, self.close, sn, self.H, lib.DWELL)
        return self._acc[sn]

    def journey_ok(self, origin_node, shelter_node, depart, legs, arrival):
        """Is the advised journey valid in the truth instance? Returns (ok, reason)."""
        ob = engine.origin_closure(self.road, self.close, origin_node, self.H)
        if iv.contains(ob, depart):
            return False, "origin"
        for kind, x, s, e in legs:
            if kind == "EDGE":
                if iv.contains(self.inst.B[x], s):
                    return False, "edge"
            elif kind == "WAIT":
                if iv.contains(self.inst.W[x], s):
                    return False, "wait"
        if not iv.contains(self.accept(shelter_node), arrival):
            return False, "shelter"
        return True, ""


def state(r):
    return "CUT" if r["cut"] is not None else "NOT_CUT"


def place_rows(rid, truth_rules, rules, origins, tag, extra=None):
    """One row per (place, rule) with all per-place quantities."""
    tr = Truth(rid, truth_rules["close_s"])
    T = truth_rules["rules"]
    out = []
    for pid, t in T.items():
        if t["refused"] or any(rules[k][pid]["refused"] for k in rules):
            continue
        on = origins[pid]
        for k, R in rules.items():
            r = R[pid]
            advised = r["cut"] is not None and r["L"] >= 0
            ok, why = (None, "")
            if advised:
                ok, why = tr.journey_ok(on, r["shelter_node"], r["L"], r["legs"], r["arrival"])
            row = {"tag": tag, "place": pid, "rule": k, "truth_state": state(t), "rule_state": state(r),
                   "truth_cut_s": t["cut"], "rule_cut_s": r["cut"], "truth_L": t["L"], "rule_L": r["L"],
                   "advised": advised, "failed": advised and not ok, "fail_reason": why,
                   "late": advised and r["L"] > t["L"],
                   "missed": state(t) == "CUT" and (state(r) == "NOT_CUT" or r["cut"] > t["cut"]),
                   "false": state(t) == "NOT_CUT" and state(r) == "CUT",
                   "lead_set": t["cut"] is not None and t["L"] >= 0,
                   "lead_given_up_min": (t["L"] - r["L"]) / 60.0 if (t["cut"] is not None and t["L"] >= 0) else None}
            if extra:
                row.update(extra)
            out.append(row)
    return out


def summary(rows, rule):
    x = [r for r in rows if r["rule"] == rule]
    lead = [r["lead_given_up_min"] for r in x if r["lead_set"]]
    return {"rule": rule, "name": NAMES.get(rule, rule), "place_pairs": len(x),
            "advised": sum(r["advised"] for r in x), "failed": sum(r["failed"] for r in x),
            "late": sum(r["late"] for r in x),
            "true_cut": sum(r["truth_state"] == "CUT" for r in x), "missed": sum(r["missed"] for r in x),
            "true_not_cut": sum(r["truth_state"] == "NOT_CUT" for r in x), "false": sum(r["false"] for r in x),
            "lead_n": len(lead), "lead_median_min": float(np.median(lead)) if lead else None,
            "lead_mean_min": float(np.mean(lead)) if lead else None,
            "fail_reasons": {k: sum(1 for r in x if r["failed"] and r["fail_reason"] == k) for k in ("origin", "edge", "wait", "shelter")}}


def bootstrap(rows, rules, cluster_key, B=10000, seed=20261119):
    """Cluster bootstrap: differences X - a in failed count and in median lead given up."""
    rng = np.random.default_rng(seed)
    clusters = sorted({r[cluster_key] for r in rows})
    ci = {c: i for i, c in enumerate(clusters)}
    nC = len(clusters)
    fail = {k: np.zeros(nC) for k in rules}
    lead = {k: [[] for _ in range(nC)] for k in rules}
    for r in rows:
        i = ci[r[cluster_key]]
        fail[r["rule"]][i] += r["failed"]
        if r["lead_set"]:
            lead[r["rule"]][i].append(r["lead_given_up_min"])
    lead = {k: [np.asarray(v) for v in lead[k]] for k in rules}
    draws = rng.integers(0, nC, (B, nC))
    out = {}
    for k in rules:
        if k == "a":
            continue
        df = (fail[k][draws] - fail["a"][draws]).sum(1)
        dl = np.empty(B)
        for b in range(B):
            la = np.concatenate([lead["a"][i] for i in draws[b]])
            lk = np.concatenate([lead[k][i] for i in draws[b]])
            dl[b] = (np.median(lk) - np.median(la)) if la.size and lk.size else np.nan
        out[k] = {"failed_diff_point": float(fail[k].sum() - fail["a"].sum()),
                  "failed_diff_ci95": [float(np.percentile(df, 2.5)), float(np.percentile(df, 97.5))],
                  "failed_diff_ci9833": [float(np.percentile(df, 0.8333)), float(np.percentile(df, 99.1667))],
                  "lead_median_diff_ci95": [float(np.nanpercentile(dl, 2.5)), float(np.nanpercentile(dl, 97.5))]}
    return {"clusters": nC, "B": B, "seed": seed, "diff_vs_a": out}


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def twin(out):
    import run_twin as RT
    out = Path(out)
    reg = lib.region("yeongdeok_2025")
    origins = {o["id"]: o["node"] for o in reg.origins}
    rows = []
    for seed, h in RT.pairs():
        tag = "s%d_h%d" % (seed, h)
        res = json.loads((out / "twin" / (tag + ".json")).read_text())
        bc = json.loads((out / "twin" / (tag + "_bc.json")).read_text())
        rules = {"a": res["rules"]["a"], "b": bc["rules"]["b"], "c": bc["rules"]["c"], "d": res["rules"]["d"], "e": res["rules"]["e"]}
        truth = {"rules": res["rules"]["truth"], "close_s": res["close_s"]["truth"]}
        rows += place_rows("yeongdeok_2025", truth, rules, origins, tag, {"seed": seed, "h": h})
    write_csv(out / "twin_rule_places.csv", rows)
    # baseline check against kcf-validate (system arm)
    kv = {}
    for r in csv.DictReader(open(lib.REPO / "research/kcf-validate/out/twin_places.csv")):
        if r["arm"] == "system" and r["refused"] == "False":
            kv[("s%s_h%s" % (r["seed"], r["issue_offset_h"]), r["place"])] = r
    agree = sum(1 for r in rows if r["rule"] == "a" and (r["tag"], r["place"]) in kv
                and (kv[(r["tag"], r["place"])]["system_cut_s"] or None) == (None if r["rule_cut_s"] is None else "%.1f" % r["rule_cut_s"])
                and (kv[(r["tag"], r["place"])]["truth_cut_s"] or None) == (None if r["truth_cut_s"] is None else "%.1f" % r["truth_cut_s"]))
    na = sum(1 for r in rows if r["rule"] == "a")
    summ = {k: summary(rows, k) for k in RULES}
    boot = bootstrap(rows, RULES, "seed")
    verdict = {}
    for k in ("b", "c", "e"):
        b = boot["diff_vs_a"][k]
        lead_ok = summ[k]["lead_median_min"] <= summ["a"]["lead_median_min"]
        verdict[k] = {"fewer_failed_ci95": b["failed_diff_ci95"][1] < 0, "fewer_failed_ci9833": b["failed_diff_ci9833"][1] < 0,
                      "lead_not_more": lead_ok, "PASS": (b["failed_diff_ci95"][1] < 0) and lead_ok}
    res = {"baseline_check": {"place_pairs_a": na, "agree_with_kcf_validate": agree, "kcf_validate_rows": len(kv),
                              "a_missed": summ["a"]["missed"], "a_true_cut": summ["a"]["true_cut"],
                              "a_false": summ["a"]["false"], "a_true_not_cut": summ["a"]["true_not_cut"]},
           "summary": summ, "bootstrap": boot, "verdict": verdict}
    (out / "twin_scores.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["baseline_check"]))
    for k in RULES:
        s = summ[k]
        print("%-15s failed %4d/%4d late %4d missed %3d/%3d false %4d/%4d lead med %7.1f mean %7.1f (n %d)" % (
            s["name"], s["failed"], s["advised"], s["late"], s["missed"], s["true_cut"], s["false"], s["true_not_cut"],
            s["lead_median_min"], s["lead_mean_min"], s["lead_n"]))
    print(json.dumps(boot["diff_vs_a"], indent=1))
    print(json.dumps(verdict))


def replay(out):
    """Secondary, RECONSTRUCTED truth (the detection record): same metrics, clusters = region-hours."""
    out = Path(out)
    rows = []
    for rid in lib.REGIONS:
        origins = {o["id"]: o["node"] for o in lib.region(rid).origins}
        for T in lib.REPLAY_ISSUES:
            tag = "%s_%s" % (rid, T.strftime("%H"))
            res = json.loads((out / "replay" / (tag + ".json")).read_text())
            bc = json.loads((out / "replay" / (tag + "_bc.json")).read_text())
            rules = {"a": res["rules"]["a"], "b": bc["rules"]["b"], "c": bc["rules"]["c"], "d": res["rules"]["d"], "e": res["rules"]["e"]}
            truth = {"rules": res["rules"]["truth"], "close_s": res["close_s"]["truth"]}
            rows += place_rows(rid, truth, rules, origins, tag, {"region": rid, "hour_utc": T.strftime("%H")})
    write_csv(out / "replay_rule_places.csv", rows)
    summ = {k: summary(rows, k) for k in RULES}
    boot = bootstrap(rows, RULES, "tag")
    res = {"label": "RECONSTRUCTED truth (detection record), secondary", "summary": summ, "bootstrap": boot}
    (out / "replay_scores.json").write_text(json.dumps(res, indent=1))
    for k in RULES:
        s = summ[k]
        print("%-15s failed %4d/%4d late %4d missed %3d/%3d false %4d/%4d lead med %s (n %d)" % (
            s["name"], s["failed"], s["advised"], s["late"], s["missed"], s["true_cut"], s["false"], s["true_not_cut"],
            s["lead_median_min"], s["lead_n"]))
    print(json.dumps(boot["diff_vs_a"], indent=1))


if __name__ == "__main__":
    {"twin": twin, "replay": replay}[sys.argv[1]](sys.argv[2])
