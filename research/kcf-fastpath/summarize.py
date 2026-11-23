"""Summarize kcf-fastpath runs (PROTOCOL.md 4-5) into results/RESULTS.json and results/tables.md.

    python3 research/kcf-fastpath/summarize.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "runs"
OUT = HERE / "results"
CACHES = ["UA0323", "UA0324", "UA0325", "YD0325T19", "YD0325T23", "YD0326"]
SOLVERS = ["baseline", "scalar", "prune", "both"]
JOBSETS = ["full", "pass1", "repeat"]


def load(js, c, s, rep):
    m = R / js / ("%s.%s.r%d.measure.json" % (c, s, rep))
    o = R / js / ("%s.%s.r%d.json" % (c, s, rep))
    if not (m.exists() and o.exists()):
        return None
    mm, oo = json.loads(m.read_text()), json.loads(o.read_text())
    if mm["exit_code"] != 0:
        return {"failed": True}
    return {"wall": mm["wall_s"], "cpu": mm["cpu_s"], "rss": mm["peak_rss_mib"], "load": mm["loadavg_before"][0],
            "field": oo["timing_s"]["fields"], "read": oo["timing_s"]["issue_and_witness"],
            "inst": oo["timing_s"]["instances"], "jobs": oo["jobs"], "specs": oo["destination_specs"],
            "digest": oo.get("results_sha256"), "kinds": oo.get("state_kinds"),
            "verdicts": oo.get("verdict_counts")}


def ratio(base, new):
    """baseline / new: median over repeats, range [min/max, max/min], and the BENCH.md word."""
    if not base or not new:
        return None
    med = statistics.median(base) / statistics.median(new)
    lo, hi = min(base) / max(new), max(base) / min(new)
    word = "faster" if lo > 1 else ("slower" if hi < 1 else "not distinguished")
    return {"median": med, "lo": lo, "hi": hi, "word": word}


def fmt(x, nd=2):
    return "—" if x is None else ("%.*f" % (nd, x))


def main():
    OUT.mkdir(exist_ok=True)
    res = {"runs": {}, "ratios": {}, "digests": {}, "memory": {}, "shares": {}}
    md = []
    for js in JOBSETS:
        md.append("\n### Job set `%s`\n" % js)
        md.append("| cache | jobs | solver | field s, median (range) | ratio field [range] | wall s, median (range) | "
                  "ratio wall [range] | CPU s median | peak RSS MiB median (range) | repeats |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for c in CACHES:
            per = {}
            for s in SOLVERS:
                runs = [load(js, c, s, r) for r in range(1, 6)]
                runs = [x for x in runs if x is not None]
                per[s] = runs
                res["runs"]["%s/%s/%s" % (js, c, s)] = runs
            base = [x for x in per["baseline"] if not x.get("failed")]
            for s in SOLVERS:
                ok = [x for x in per[s] if not x.get("failed")]
                if not ok:
                    continue
                f = [x["field"] for x in ok]
                w = [x["wall"] for x in ok]
                rf = ratio([x["field"] for x in base], f) if s != "baseline" else None
                rw = ratio([x["wall"] for x in base], w) if s != "baseline" else None
                rc = ratio([x["cpu"] for x in base], [x["cpu"] for x in ok]) if s != "baseline" else None
                rr = ratio([x["rss"] for x in base], [x["rss"] for x in ok]) if s != "baseline" else None
                res["ratios"]["%s/%s/%s" % (js, c, s)] = {"field": rf, "wall": rw, "cpu": rc, "rss": rr}
                md.append("| %s | %d | %s | %s (%s–%s) | %s | %s (%s–%s) | %s | %s | %s (%s–%s) | %d%s |" % (
                    c, ok[0]["jobs"], s, fmt(statistics.median(f)), fmt(min(f)), fmt(max(f)),
                    "" if rf is None else "%s [%s–%s] %s" % (fmt(rf["median"]), fmt(rf["lo"]), fmt(rf["hi"]), rf["word"]),
                    fmt(statistics.median(w), 1), fmt(min(w), 1), fmt(max(w), 1),
                    "" if rw is None else "%s [%s–%s] %s" % (fmt(rw["median"]), fmt(rw["lo"]), fmt(rw["hi"]), rw["word"]),
                    fmt(statistics.median([x["cpu"] for x in ok]), 1),
                    fmt(statistics.median([x["rss"] for x in ok]), 0), fmt(min(x["rss"] for x in ok), 0),
                    fmt(max(x["rss"] for x in ok), 0), len(ok),
                    "" if len(ok) == len(per[s]) else " (%d failed)" % (len(per[s]) - len(ok))))
            d = {s: next((x["digest"] for x in per[s] if x.get("digest")), None) for s in SOLVERS}
            res["digests"]["%s/%s" % (js, c)] = {"digests": d, "all_equal": len(set(d.values())) == 1 and None not in d.values()}
    # memory probe
    md.append("\n### Memory probe (tracemalloc, untimed, full job set)\n")
    md.append("| cache | solver | solver peak MiB, sum over specs | largest spec MiB | field kept MiB, largest spec | "
              "peak ratio baseline ÷ solver (largest spec) |")
    md.append("|---|---|---|---|---|---|")
    for c in CACHES:
        base_max = None
        for s in SOLVERS:
            p = R / "memory" / ("%s.%s.json" % (c, s))
            if not p.exists():
                continue
            tm = json.loads(p.read_text())["tracemalloc"]
            pk = [x["solver_peak_bytes"] / 2 ** 20 for x in tm]
            kp = [x["field_kept_bytes"] / 2 ** 20 for x in tm]
            if s == "baseline":
                base_max = max(pk)
            res["memory"]["%s/%s" % (c, s)] = {"peak_sum_mib": sum(pk), "peak_max_mib": max(pk),
                                              "kept_sum_mib": sum(kp), "kept_max_mib": max(kp), "specs": len(tm)}
            md.append("| %s | %s | %s | %s | %s | %s |" % (c, s, fmt(sum(pk), 1), fmt(max(pk), 1), fmt(max(kp), 1),
                                                         "" if s == "baseline" or not base_max else fmt(base_max / max(pk))))
    # fast-path shares from the equality runs
    md.append("\n### Fast-path share (from the equality runs, all specs of the cache)\n")
    md.append("| cache | variant | scalar (G-clean) | scalar R only | interval | void (pruned away) |")
    md.append("|---|---|---|---|---|---|")
    for c in CACHES:
        p = OUT / ("eq_%s.json" % c)
        if not p.exists():
            continue
        e = json.loads(p.read_text())
        res["shares"][c] = e["state_kind_shares"]
        for v, sh in e["state_kind_shares"].items():
            md.append("| %s | %s | %s%% | %s%% | %s%% | %s%% |" % (c, v, *(fmt(100 * sh.get(k, 0), 2) for k in
                                                                       ("g_clean", "r_clean_only", "interval", "void"))))
    (OUT / "RESULTS.json").write_text(json.dumps(res, indent=1))
    (OUT / "tables.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
