"""Summarise results/ into results/summary.json and results/tables.md (BENCH_PLAN.md sections 6, 7, 8).

    python3 research/kcf-bench/analyze.py [--results DIR]
"""
import argparse
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

from common import CACHES, HERE, load_cases, short

NEW = ["field", "field_dec", "margin1", "margin10"]
NAMES = {"old": "OLD (scaled)", "field": "FIELD", "field_dec": "FIELD-D", "margin1": "MARGIN-1", "margin10": "MARGIN-10",
         "field_sample": "FIELD, sample specs only", "field_check": "FIELD + route check, sample"}


def rng(xs):
    return {"median": st.median(xs), "min": min(xs), "max": max(xs), "n": len(xs)}


def ratio(num, den):
    """Median ratio with the widest range the repeats allow: [min num / max den, max num / min den]."""
    return {"median": num["median"] / den["median"], "lo": num["min"] / den["max"], "hi": num["max"] / den["min"]}


def verdict_word(r):
    return "faster" if r["lo"] > 1 else ("slower" if r["hi"] < 1 else "not distinguished")


def fmt(x, d=2):
    return ("%." + str(d) + "f") % x if x < 100 else "%.0f" % x


def cell(r):
    return "%s (%s–%s)" % (fmt(r["median"]), fmt(r["min"]), fmt(r["max"]))


def rcell(r):
    return "%s [%s–%s] %s" % (fmt(r["median"]), fmt(r["lo"]), fmt(r["hi"]), verdict_word(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--old-n", type=int, default=200, help="requests per OLD block (3 only for the dry run)")
    a = ap.parse_args()
    res = Path(a.results)
    led = [json.loads(l) for l in (res / "ledger.jsonl").read_text().splitlines()]
    failed = [l for l in led if l["status"] != "done"]
    old = defaultdict(list)
    for l in (res / "old.jsonl").read_text().splitlines():
        r = json.loads(l)
        old[(r["cache"], r["mode"])].append(r)
    S = {"failed_tasks": [f["task"] for f in failed], "caches": {}}
    rows = []
    for cache in CACHES:
        doc = load_cases(cache)
        n = doc["n_cases"]
        tag = cache.replace("/", "__")
        c = {"n_cases": n}
        f = {}
        for m in NEW + ["field_sample", "field_check"]:
            fs = sorted((res / "field").glob("%s__%s__r*.json" % (m, tag)))
            js = [json.load(open(p)) for p in fs]
            if js:
                f[m] = {"cold": rng([j["cold_s"] for j in js]), "warm": rng([j["warm_s"] for j in js]),
                        "peak_cold_mb": rng([j["peak_cold_kb"] / 1024 for j in js]),
                        "peak_warm_mb": rng([j["peak_warm_kb"] / 1024 for j in js]),
                        "baseline_mb": rng([j["rss_baseline_kb"] / 1024 for j in js]), "n_cases": js[0]["n_cases"],
                        "n_specs": js[0]["n_specs"], "warm_equals_cold": all(j.get("warm_equals_cold") for j in js)}
        o = {}
        for mode in ("cold", "warm"):
            rs = old.get((cache, mode), [])
            by_rep = defaultdict(list)
            for r in rs:
                by_rep[r["repeat"]].append(r)
            reps = {k: v for k, v in by_rep.items() if len(v) == a.old_n}
            if not reps:
                continue
            scaled = [sum(r["wall_s"] for r in v) / len(v) * n for v in reps.values()]
            percase = defaultdict(list)
            for v in reps.values():
                for r in v:
                    percase[r["case"]].append(r["wall_s"])
            means = [st.mean(x) for x in percase.values()]
            R = random.Random(20261119)
            boot = sorted(st.mean(R.choices(means, k=len(means))) * n for _ in range(10000))
            allr = [r for v in reps.values() for r in v]
            o[mode] = {"scaled": rng(scaled), "per_case_s": rng([r["wall_s"] for r in allr]),
                       "boot95": [boot[250], boot[9750]], "repeats": len(reps),
                       "rss_mb": {"median": st.median(r["rss_mb"] for r in allr), "max": max(r["rss_mb"] for r in allr)},
                       "unresolved": sum(r["verdict"] == "unresolved" for r in allr) / len(reps),
                       "timeouts": sum(bool(r["term"]) for r in allr), "sum_wall_s_per_repeat": rng([sum(r["wall_s"] for r in v) for v in reps.values()])}
        c["field"], c["old"] = f, o
        acc_p = res / "accuracy" / (tag + ".json")
        acc = json.loads(acc_p.read_text())["counts"] if acc_p.exists() else {}
        c["accuracy"] = acc
        c["ratios"] = {}
        for mode in ("cold", "warm"):
            if mode in o:
                for m in NEW:
                    if m in f:
                        c["ratios"]["old/%s/%s" % (m, mode)] = ratio(o[mode]["scaled"], f[m][mode])
            for num, den in (("field", "margin1"), ("field", "margin10"), ("field_dec", "margin10")):
                if num in f and den in f:
                    c["ratios"]["%s/%s/%s" % (num, den, mode)] = ratio(f[num][mode], f[den][mode])
        S["caches"][cache] = c
        # ---- the one table
        def agree(m):
            if not acc:
                return "n/a"
            if m == "old":
                return "—"
            if m in ("field", "field_dec"):
                return "%d/%d vs OLD; %d/%d vs recorded" % (acc.get("a_vs_bc_cases", 0) - acc.get("a_vs_b_MISMATCH", 0),
                                                            acc.get("a_vs_bc_cases", 0), acc.get("recorded_decided", 0) - acc.get("recorded_vs_b_MISMATCH", 0),
                                                            acc.get("recorded_decided", 0))
            if m == "margin10":
                return "%d/%d vs OLD at 0; %d/%d vs FIELD at 0; %d/%d at m>0 vs widened FIELD" % (
                    acc.get("a_vs_bc_cases", 0) - acc.get("a_vs_c0_MISMATCH", 0), acc.get("a_vs_bc_cases", 0),
                    acc.get("cases_b_vs_c0", 0) - acc.get("cases_b_vs_c0_MISMATCH", 0), acc.get("cases_b_vs_c0", 0),
                    acc.get("margin10_cases", 0) - acc.get("margin10_cases_MISMATCH", 0), acc.get("margin10_cases", 0))
            if m == "margin1":
                return "%d/%d at m=60 vs widened FIELD" % (acc.get("margin1_cases", 0) - acc.get("margin1_cases_MISMATCH", 0), acc.get("margin1_cases", 0))
            return ""
        for m in ["old"] + NEW:
            if m == "old":
                if not o:
                    continue
                cold = o.get("cold", {}).get("scaled")
                warm = o.get("warm", {}).get("scaled")
                mem = "%s median, %s max per request (one worker)" % (fmt(o["cold"]["rss_mb"]["median"], 0), fmt(o["cold"]["rss_mb"]["max"], 0)) if "cold" in o else ""
                rows.append((short(cache), NAMES[m], cell(cold) if cold else "", cell(warm) if warm else "", "", "", mem, "—"))
                continue
            if m not in f:
                continue
            rc = c["ratios"].get("old/%s/cold" % m)
            rw = c["ratios"].get("old/%s/warm" % m)
            mem = "%s (baseline %s)" % (fmt(f[m]["peak_warm_mb"]["median"], 0), fmt(f[m]["baseline_mb"]["median"], 0))
            rows.append((short(cache), NAMES[m], cell(f[m]["cold"]), cell(f[m]["warm"]), rcell(rc) if rc else "", rcell(rw) if rw else "", mem, agree(m)))
    hdr = ("| cache | method | cold s, median (range) | warm s, median (range) | OLD ÷ method, cold [range] | OLD ÷ method, warm [range] | peak MB | agreement |\n"
           "|---|---|---|---|---|---|---|---|\n")
    tbl = hdr + "\n".join("| " + " | ".join(r) + " |" for r in rows) + "\n"
    (res / "tables.md").write_text(tbl)
    (res / "summary.json").write_text(json.dumps(S, indent=1, default=str))
    # probe drift
    pr = defaultdict(list)
    for l in led:
        pr["before"].append(l["probe_before_s"])
        pr["after"].append(l["probe_after_s"])
    S["probe_s"] = {k: rng(v) for k, v in pr.items()}
    (res / "summary.json").write_text(json.dumps(S, indent=1, default=str))
    print(tbl)
    print("failed tasks:", S["failed_tasks"])
    print("probe", S["probe_s"])


if __name__ == "__main__":
    main()
