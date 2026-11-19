"""Child process: one FIELD / MARGIN pass over a cache, cold then warm (BENCH_PLAN.md section 3).

    taskset -c 3 python3 research/kcf-bench/run_field.py --cache <cache> --method field|field_sample|field_check|margin1|margin10
        --out result.json [--answers answers.json] [--no-warm]

Prints one JSON object to --out. Timed region: instance construction, preconditions, field pass, read-off of every case.
Cold = first pass, including PacketModel (graph and packet load) and the HAZARD read; warm = second pass, same process.
"""
import argparse
import gc
import json
import platform
import sys
import time

from common import (MARGIN_ONE, MARGINS_TEN, add_paths, load_cases, packet_paths, specs_of, vm_kb)

add_paths()
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402
from margin_field import field as mf  # noqa: E402
from margin_field import pl  # noqa: E402


def run_pass(pm, hazard, cases, specs, method, memprobe=None):
    nm = len(MARGINS_TEN)
    ans = {"feas": [None] * len(cases), "arr": [None] * len(cases)}
    if method == "margin10":
        ans["feas10"] = [None] * len(cases)
    pre = {}
    stats = {"specs": 0, "pre_not_ok": 0, "checks": 0, "check_fail": 0}
    for spec, idxs in specs:
        for i in idxs:
            c = cases[i]
            k = (c["peak"], c["dose"], c["incurred"])
            if k not in pre:
                pre[k] = pm.full_policy_reduces_to_contact(hazard, peak_limit=k[0], dose_limit=k[1], incurred=k[2])[0]
                stats["pre_not_ok"] += not pre[k]
    for (dn, dwell, win), idxs in specs:
        stats["specs"] += 1
        if memprobe is not None:
            gc.collect()
            open("/proc/self/clear_refs", "w").write("5")      # reset the peak (VmHWM) before this spec
            before = vm_kb("VmRSS")
        origins = sorted({cases[i]["start"] for i in idxs})
        inst = pm.instance("cert", [{"node": dn, "dwell": dwell, "window": list(win)}], origins)
        if method in ("field", "field_dec", "field_sample", "field_check"):
            fld = backward(inst)
            sets = {o: issue_set(fld, pm.nidx[o]) for o in origins}
            for i in idxs:
                c = cases[i]
                o, t = c["start"], c["offset"]
                f = iv.contains(sets[o], t)
                ans["feas"][i] = f
                if f and method != "field_dec":
                    w = witness(fld, pm.nidx[o], t)
                    ans["arr"][i] = w[0]
                    if method == "field_check":
                        legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b) for k, x, a, b in w[1]]
                        chk = full_check(pm, hazard, origin=o, legs=legs, dest=dn, dwell=dwell, window=tuple(win),
                                         departure=t, incurred=c["incurred"], peak=c["peak"], dose=c["dose"])
                        stats["checks"] += 1
                        stats["check_fail"] += not (chk["full_policy_ok"] and chk["closed_and_router_replay_clear"])
        elif method == "margin1":
            fld = mf.margin_field(inst, MARGIN_ONE)
            sets = {o: mf.issue_set_at(fld, pm.nidx[o], MARGIN_ONE) for o in origins}
            fa = None
            for i in idxs:
                c = cases[i]
                o, t = c["start"], c["offset"]
                f = iv.contains(sets[o], t)
                ans["feas"][i] = f
                if f:
                    if fa is None:
                        fa = mf.field_at(fld, MARGIN_ONE)
                    ans["arr"][i] = witness(fa, pm.nidx[o], t)[0]
        elif method == "margin10":
            fld = mf.margin_field(inst, 600)
            fo = {o: mf.issue_margin(fld, pm.nidx[o]) for o in origins}
            sets = {(o, m): pl.level_set(fo[o], m) for o in origins for m in MARGINS_TEN}
            for i in idxs:
                c = cases[i]
                o, t = c["start"], c["offset"]
                ans["feas10"][i] = [iv.contains(sets[(o, m)], t) for m in MARGINS_TEN]
                ans["feas"][i] = ans["feas10"][i][0]
        else:
            raise SystemExit("unknown method " + method)
        stats["pieces"] = stats.get("pieces", 0) + fld.stats.get("pieces", 0)
        if memprobe is not None:
            memprobe.append({"dest": dn, "cases": len(idxs), "rss_before_kb": before, "peak_kb": vm_kb("VmHWM")})
    return ans, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--answers")
    ap.add_argument("--no-warm", action="store_true")
    ap.add_argument("--memprobe", action="store_true", help="untimed: per-spec peak resident set (resets VmHWM before each spec)")
    a = ap.parse_args()
    doc = load_cases(a.cache)
    cases = doc["cases"]
    specs = list(specs_of(cases).items())
    if a.method in ("field_sample", "field_check"):
        keep = {c for c in doc["sample"]}
        sidx = {i for i, c in enumerate(cases) if c["id"] in keep}
        specs = [(s, [i for i in idxs if i in sidx]) for s, idxs in specs]
        specs = [(s, idxs) for s, idxs in specs if idxs]
    graph_path, packet_dir = packet_paths(doc["region"], doc["input_time"])
    rss_import = vm_kb("VmRSS")
    res = {"cache": a.cache, "method": a.method, "n_cases": sum(len(i) for _, i in specs), "n_specs": len(specs),
           "python": platform.python_version(), "rss_after_imports_kb": rss_import}
    gc.collect()
    t0 = time.perf_counter()
    pm = PacketModel(graph_path, packet_dir)
    hazard = json.loads((packet_dir / "HAZARD.json").read_text())
    res["prep_s"] = time.perf_counter() - t0
    res["rss_baseline_kb"] = vm_kb("VmRSS")
    res["peak_after_prep_kb"] = vm_kb("VmHWM")
    probe = [] if a.memprobe else None
    ans, stats = run_pass(pm, hazard, cases, specs, a.method, probe)
    if probe is not None:
        res["memprobe"] = probe
    res["cold_s"] = time.perf_counter() - t0
    res["peak_cold_kb"] = vm_kb("VmHWM")
    res["stats"] = stats
    if not a.no_warm:
        gc.collect()
        t1 = time.perf_counter()
        ans2, _ = run_pass(pm, hazard, cases, specs, a.method)
        res["warm_s"] = time.perf_counter() - t1
        res["peak_warm_kb"] = vm_kb("VmHWM")
        res["warm_equals_cold"] = ans2 == ans
    if a.answers:
        json.dump(ans, open(a.answers, "w"), separators=(",", ":"))
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "stats"}))


if __name__ == "__main__":
    main()
