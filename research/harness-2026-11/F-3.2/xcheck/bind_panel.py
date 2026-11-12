"""Binding on the frozen 20-request Korean panel (BINDING_RULE.md rev 2.1): T1 on real request pairs, T6/T7 on real
bundles. Bundles go to --out (outside git); the summary JSON is written to --summary.

Per mission:
  1. build_instance + generate.certify (format 1), then bind_bundle.to_v2 with bind_digests.digests() of the
     generator's own inputs;
  2. the CONSUMER side recomputes G A W Q from the files on disk (bind_digests on the paths, a separate call) and runs
     both checkers with --expect: both must print ACCEPT <claim> <T> LABELS_MATCH <I16>, the same claim and T as format 1;
  3. T7 on the instance PARSED from the bound bundle's own bytes (the bytes hashed into I):
     (a) structure, checked directly against graph + request (not part of O2 today): V, E, tail/head/D per edge,
         WAITABLE set, FORBID pairs (from forbidden_turns), ORIGIN, START (incoming_edge), DEP, HOR;
     (b) O2: derive_instance.compare_semantic of EB/WB/AC/clock against derive(graph, request, cell_intervals),
         0 differences required.
T1: for every pair of missions sharing graph and packet, mission X's bundle checked with mission Y's consumer digests
must REJECT on both checkers (G and A equal, so Q alone has to catch it).
T11 (rev 2.2, Mira ledger 101 N1): for the same pairs, bundle X RELABELLED with Y's G A W Q (I unchanged) passes both
checkers (LABELS_MATCH, by design), and verify_bound.py with Y's own inputs must NOT print FULLY_BOUND.
Every mission's bundle is also run through verify_bound.py with its own inputs: FULLY_BOUND required.

Usage: python xcheck/bind_panel.py --out DIR --summary FILE [--only M ...]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
F32 = HERE.parent
sys.path.insert(0, str(F32))
import bind_bundle  # noqa: E402
import bind_digests  # noqa: E402
import cases  # noqa: E402
import derive_instance  # noqa: E402
import generate  # noqa: E402
import verify_bound  # noqa: E402
from verify_bound import parse_instance, structure_diffs  # noqa: E402
from p1_check import routable_contact_model  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402

C_BIN = F32 / "checker_c" / "wfgc_check"


def checkers(path, expect=None):
    extra = [] if expect is None else ["--expect", bind_digests.expect_arg(expect)]
    out = {}
    for name, cmd in (("py", [sys.executable, str(F32 / "check_py.py")]), ("c", [str(C_BIN)])):
        r = subprocess.run(cmd + [str(path)] + extra, capture_output=True, text=True)
        out[name] = [r.stdout.strip(), r.returncode]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["make", "-s", "-C", str(F32 / "checker_c")], check=True)
    rows, consumer = [], {}
    for c in cases.korean_cases():
        if a.only and c["mission"] not in a.only:
            continue
        t0 = time.perf_counter()
        graph = json.loads(Path(c["graph"]).read_text())
        request = json.loads(Path(c["request"]).read_text())
        model = routable_contact_model(c["packet"])
        inst, pg = build_instance(graph, request, model)
        claim, T, text1, ih, _ = generate.certify(inst)
        gen_dg = bind_digests.digests(c["graph"], c["packet"], request)          # generator side
        text2, I = bind_bundle.to_v2(text1, gen_dg)
        assert I == ih, "instance digest differs from generate's"
        key = "%s__%s" % (c["region"], c["mission"])
        p1, p2 = out / (key + ".v1.wfgc"), out / (key + ".v2.wfgc")
        p1.write_text(text1); p2.write_text(text2)
        con_dg = bind_digests.digests(c["graph"], c["packet"], c["request"])    # consumer side, from the files
        consumer[key] = dict(dg=con_dg, path=p2, graph=c["graph"], packet=str(c["packet"]), request=c["request"],
                             text1=text1)
        v1 = checkers(p1)
        v2 = checkers(p2, con_dg)
        parsed = parse_instance(p2.read_text())
        sd = structure_diffs(parsed, graph, request)
        derived = derive_instance.derive(graph, request, model.cell_intervals)
        o2 = derive_instance.compare_semantic(parsed, derived)
        want = "ACCEPT %s %d LABELS_MATCH %s" % (claim, T, I[:16])
        vb = verify_bound.verify(p2, c["graph"], c["packet"], c["request"], C_BIN)
        rows.append(dict(mission=c["mission"], region=c["region"], claim=claim, T=T, I=I, digests=con_dg,
                         generator_equals_consumer=gen_dg == con_dg, v1=v1, v2=v2,
                         v2_ok=all(v2[k] == [want, 0] for k in v2),
                         v1_ok=all(v1[k] == ["ACCEPT %s %d" % (claim, T), 0] for k in v1),
                         t7_structure_diffs=[list(map(str, x)) for x in sd][:20], t7_structure_ok=not sd,
                         t7_o2_diffs=len(o2), t7_o2_ok=not o2, verify_bound=vb["verdict"],
                         wall_s=round(time.perf_counter() - t0, 2)))
        print(json.dumps({k: rows[-1][k] for k in ("mission", "claim", "T", "v1_ok", "v2_ok", "t7_structure_ok",
                                                    "t7_o2_ok", "verify_bound", "wall_s")}), flush=True)
    # T1 on real pairs sharing graph and packet
    t1, t11 = [], []
    keys = sorted(consumer)
    for x in keys:
        for y in keys:
            cx, cy = consumer[x], consumer[y]
            if x == y or cx["graph"] != cy["graph"] or cx["packet"] != cy["packet"]:
                continue
            same_q = cx["dg"]["Q"] == cy["dg"]["Q"]
            r = checkers(cx["path"], cy["dg"])
            ok = same_q or all(v[0].startswith("REJECT") and v[1] == 1 for v in r.values())
            t1.append(dict(bundle=x, expect_of=y, same_Q=same_q, py=r["py"], c=r["c"], ok=ok))
            # T11: relabel X with Y's labels, keep X's instance
            relabelled, _ = bind_bundle.to_v2(cx["text1"], cy["dg"])
            rp = out / ("relabel__%s__as__%s.v2.wfgc" % (x, y))
            rp.write_text(relabelled)
            rc = checkers(rp, cy["dg"])
            vb = verify_bound.verify(rp, cy["graph"], cy["packet"], cy["request"], C_BIN)
            t11.append(dict(bundle=x, labels_of=y, py=rc["py"], c=rc["c"],
                            checkers_labels_match=all(v[1] == 0 and "LABELS_MATCH" in v[0] for v in rc.values()),
                            verify_bound=vb["verdict"], step=vb["step"], detail=vb["detail"],
                            ok=vb["verdict"] != "FULLY_BOUND"))
    summary = dict(rule="BINDING_RULE.md rev 2.2", missions=len(rows),
                   fully_bound=sum(r["verify_bound"] == "FULLY_BOUND" for r in rows),
                   v1_unchanged=sum(r["v1_ok"] for r in rows), v2_bound_accept=sum(r["v2_ok"] for r in rows),
                   generator_equals_consumer=sum(r["generator_equals_consumer"] for r in rows),
                   t7_structure_ok=sum(r["t7_structure_ok"] for r in rows), t7_o2_ok=sum(r["t7_o2_ok"] for r in rows),
                   t1_pairs=len(t1), t1_ok=sum(p["ok"] for p in t1), t1_same_Q=sum(p["same_Q"] for p in t1),
                   t11_pairs=len(t11), t11_ok=sum(p["ok"] for p in t11),
                   t11_checkers_labels_match=sum(p["checkers_labels_match"] for p in t11),
                   rows=rows, t1=t1, t11=t11)
    Path(a.summary).write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "t1", "t11")}))


if __name__ == "__main__":
    main()
