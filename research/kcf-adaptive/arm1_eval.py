"""Arm 1 evaluation: reproduction gate, leakage test L2/L3, scores and verdict (PROTOCOL.md 2.1, 2.5-2.7).

    python arm1_eval.py --env ENVDIR --runs WORK/arm1 --out derived/arm1.json [--gate-only]

RUNS holds the outputs of arm1_run.py: P4_real, P4_scramble, P+_real, P+_scramble, leak_real, leak_scramble,
and the SENSITIVITY runs P4_pen1e-3 and P4_pen1e-4 (PROTOCOL amendment 1; not part of the verdict).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import tta
from arm1_run import EnvStore
from cases import load_windows, paired_bootstrap, summarise

GATE_REL = 0.02


def load_run(path: Path, fires):
    """case_id -> (p, theta) for every window of every fire present in the run directory."""
    out = {}
    for ev, ws in fires.items():
        f = path / f"{ev}.npz"
        if not f.exists():
            continue
        z = np.load(f, allow_pickle=False)
        for w in ws:
            out[w.case_id] = (z[f"p_{w.case_id}"], z[f"theta_{w.case_id}"])
    return out


def gate(fires, model, env):
    """Unadapted c651 mean-field on the rebuilt inputs against the committed p_c651_meanfield."""
    un, diffs, per_fire = {}, [], {}
    se_r = se_c = n = 0.0
    for ev, ws in fires.items():
        d_ev = []
        for i, w in enumerate(ws):
            hid = model.hidden(env.at(ev, w.weather_hour))
            p = tta.predict(model, None, w, lambda v, h=hid: h)
            un[w.case_id] = p
            c = w.committed["p_c651_meanfield"]
            d_ev.append(np.abs(p - c))
            se_r += float(np.sum((p - w.y) ** 2)); se_c += float(np.sum((c - w.y) ** 2)); n += len(w.y)
        d_ev = np.concatenate(d_ev)
        diffs.append(d_ev)
        per_fire[ev] = dict(max_abs_diff=float(d_ev.max()), mean_abs_diff=float(d_ev.mean()),
                            p99_abs_diff=float(np.quantile(d_ev, 0.99)))
    d = np.concatenate(diffs)
    # fast path against the repository's own mean-field on the same rebuilt inputs (first, middle, last window)
    fp = 0.0
    for ev, ws in fires.items():
        for w in (ws[0], ws[len(ws) // 2], ws[-1]):
            r = tta.repo_meanfield(model, env.at(ev, w.weather_hour), w.initial, w.hours)[w.row, w.col]
            fp = max(fp, float(np.abs(r - un[w.case_id]).max()))
    b_r, b_c = se_r / n, se_c / n
    rel = abs(b_r - b_c) / b_c
    return un, dict(entries=int(n), max_abs_diff=float(d.max()), median_abs_diff=float(np.median(d)),
                    mean_abs_diff=float(d.mean()), p99_abs_diff=float(np.quantile(d, 0.99)),
                    share_within_1e_3=float((d <= 1e-3).mean()), brier_rebuilt=b_r, brier_committed_meanfield=b_c,
                    relative_brier_difference=rel, threshold=GATE_REL, passes=bool(rel <= GATE_REL),
                    label="c651 on rebuilt inputs" if rel <= GATE_REL else "REBUILT-INPUT c651, not the scored c651",
                    fast_path_vs_repository_meanfield_max_abs_diff=fp, per_fire=per_fire)


def leakage(real, scr):
    ids = sorted(set(real) & set(scr))
    same_p = [np.array_equal(real[c][0], scr[c][0]) for c in ids]
    same_t = [np.array_equal(real[c][1], scr[c][1]) for c in ids]
    worst = max((float(np.abs(real[c][0] - scr[c][0]).max()) for c in ids), default=None)
    return dict(windows_compared=len(ids), predictions_identical=int(sum(same_p)), parameters_identical=int(sum(same_t)),
                max_abs_prediction_difference=worst, invariant=bool(ids) and all(same_p) and all(same_t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, type=Path)
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--gate-only", action="store_true")
    a = ap.parse_args()
    torch.set_num_threads(1)
    fires = load_windows()
    model = tta.C651Model()
    env = EnvStore(a.env)
    un, g = gate(fires, model, env)
    res = dict(reproduction_gate=g, parameters_total=model.n_params,
               settings=dict(lr=tta.LR, steps=tta.STEPS, penalty=tta.PENALTY, max_history=8, dtype="float64"))
    print(json.dumps({k: v for k, v in g.items() if k != "per_fire"}, indent=1))
    if a.gate_only:
        a.out.with_name("arm1_gate.json").write_text(json.dumps(res, indent=1) + "\n")
        return

    runs = {name: load_run(a.runs / name, fires) for name in
            ("P4_real", "P4_scramble", "P+_real", "P+_scramble", "leak_real", "leak_scramble", "P4_pen1e-3", "P4_pen1e-4")}
    n_windows = sum(len(ws) for ws in fires.values())
    res["runs_windows"] = {k: len(v) for k, v in runs.items()}
    res["leakage"] = dict(
        L2_P4=leakage(runs["P4_real"], runs["P4_scramble"]), L2_Pplus=leakage(runs["P+_real"], runs["P+_scramble"]),
        L3_positive_control_P4=leakage(runs["leak_real"], runs["leak_scramble"]), windows_total=n_windows)
    lk = res["leakage"]
    lk["L2_pass"] = bool(lk["L2_P4"]["invariant"] and lk["L2_P4"]["windows_compared"] == n_windows
                         and lk["L2_Pplus"]["invariant"] and lk["L2_Pplus"]["windows_compared"] == n_windows)
    c = lk["L3_positive_control_P4"]
    lk["L3_detects_leak"] = bool(c["windows_compared"] and c["predictions_identical"] < c["windows_compared"])
    print("leakage:", json.dumps(lk, indent=1))

    def columns(names, only_history=False, subset=None):
        cols = dict(fire=[], y=[], unadapted_rebuilt=[], c651_meanfield_committed=[], c651_mc_committed=[],
                    **{n: [] for n in names})
        for ev, ws in fires.items():
            for i, w in enumerate(ws):
                if any(w.case_id not in runs[n] for n in names) or (only_history and i == 0):
                    continue
                cols["fire"].append(np.full(len(w.y), ev)); cols["y"].append(w.y.astype(float))
                cols["unadapted_rebuilt"].append(un[w.case_id])
                cols["c651_meanfield_committed"].append(w.committed["p_c651_meanfield"])
                cols["c651_mc_committed"].append(w.committed["p_c651_mc"])
                for n in names:
                    cols[n].append(runs[n][w.case_id][0])
        return {k: np.concatenate(v) for k, v in cols.items()}

    def report(names, only_history=False):
        c = columns(names, only_history)
        preds = {k: v for k, v in c.items() if k not in ("fire", "y")}
        preds["persistence"] = np.zeros(len(c["y"]))
        s = summarise(c["fire"], c["y"], preds)
        se, n = s.pop("_se"), s.pop("_n")
        pairs = [(n_, "unadapted_rebuilt") for n_ in names] + [(n_, "persistence") for n_ in names] + \
                [("unadapted_rebuilt", "persistence"), ("unadapted_rebuilt", "c651_meanfield_committed")]
        s["paired_brier_difference"] = {f"{x}_minus_{y_}": paired_bootstrap(se[x], se[y_], n) for x, y_ in pairs}
        return s

    main_names = [n for n in ("P4_real", "P+_real", "P4_pen1e-3", "P4_pen1e-4") if len(runs[n]) == n_windows]
    res["complete_runs"] = main_names
    if main_names:
        res["all_windows"] = report(main_names)
        res["windows_with_history"] = report(main_names, only_history=True)
        # verdict (PROTOCOL 2.6), primary set P4
        if "P4_real" in main_names:
            r = res["all_windows"]
            d = r["paired_brier_difference"]["P4_real_minus_unadapted_rebuilt"]
            fa, fu = r["models"]["P4_real"]["flagging"], r["models"]["unadapted_rebuilt"]["flagging"]
            better = d["ci95"][1] < 0
            less_area = fa["expected_area_per_burned_cell"] < fu["expected_area_per_burned_cell"]
            no_more_miss = fa["expected_miss_rate"] <= fu["expected_miss_rate"]
            if better and less_area and no_more_miss:
                v = "helps"
            elif less_area and not no_more_miss:
                v = "trade-off, not help"
            else:
                v = "does not help"
            dp = r["paired_brier_difference"]["P4_real_minus_persistence"]
            res["verdict_arm1"] = dict(
                verdict=v, brier_difference_vs_unadapted=d, brier_interval_below_zero=better,
                expected_area_per_burned_cell=dict(adapted=fa["expected_area_per_burned_cell"],
                                                   unadapted=fu["expected_area_per_burned_cell"]),
                expected_miss_rate=dict(adapted=fa["expected_miss_rate"], unadapted=fu["expected_miss_rate"]),
                beats_persistence=bool(dp["ci95"][1] < 0), brier_difference_vs_persistence=dp)
    if len(runs["leak_real"]) == n_windows:
        c = columns(["leak_real"])
        res["LEAKY_NOT_A_RESULT"] = dict(note="positive control: the target window was added to its own history",
                                        brier=float(np.mean((c["leak_real"] - c["y"]) ** 2)),
                                        brier_unadapted=float(np.mean((c["unadapted_rebuilt"] - c["y"]) ** 2)))
    # what the adaptation did to the parameters
    rows = []
    for name in main_names:
        for ev, ws in fires.items():
            csv = pd.read_csv(a.runs / name / f"{ev}.csv")
            csv["run"] = name
            rows.append(csv)
    if rows:
        tab = pd.concat(rows)
        tab.to_csv(a.out.with_name("arm1_windows.csv"), index=False)
        l0 = model.m.mixing_logits.detach().numpy()
        sp = lambda x: np.log1p(np.exp(x))  # noqa: E731
        res["parameter_shift"] = {}
        for name in main_names:
            t = tab[(tab.run == name) & (tab.history > 0)]
            ratio = {str(k): np.quantile(sp(l0[j] + t[f"dmix{k}"]) / sp(l0[j]), [0, .25, .5, .75, 1]).round(4).tolist()
                     for j, k in enumerate((3, 5, 7, 9))}
            res["parameter_shift"][name] = dict(windows=int(len(t)), branch_weight_ratio_min_q25_median_q75_max=ratio,
                                                seconds_per_window_median=float(t.seconds.median()))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1) + "\n")
    for key in ("all_windows", "windows_with_history"):
        if key not in res:
            continue
        r = res[key]
        print(key, r["entries"], r["positives"])
        for k, v in r["models"].items():
            print(f"  {k:26s} brier {v['brier']:.7f} area/burned {v['flagging']['expected_area_per_burned_cell']:.3f} "
                  f"exp miss {v['flagging']['expected_miss_rate']:.3f} ece {v['calibration']['ece']:.5f} "
                  f"lowbin gap {v['calibration']['lowest_bin_gap']:.5f}")
        for k, v in r["paired_brier_difference"].items():
            print(f"  {k:46s} {v['point']:+.7f} [{v['ci95'][0]:+.7f}, {v['ci95'][1]:+.7f}] {v['fires_favouring_a']}/6")
    print(json.dumps(res.get("verdict_arm1"), indent=1))
    print(json.dumps(res.get("parameter_shift"), indent=1))


if __name__ == "__main__":
    main()
