"""Rule (c) summary of the F-DYN run: per region x horizon x variant agreement and naive-baseline classes, and the
mechanism ablation (mechanism.ablate: no_WB, all_wait, no_AC) on every naive failure, on instances regenerated with
Thomas's build_instance (instance sha must equal the (c) record).

    from the F-3.2 worktree root with its PYTHONPATH:
    python <repo>/research/harness-2026-11/F-BASE/summarize_fdyn.py --fdyn <Leo worktree> --c-dir <(c) run dir> --out RESULTS_fdyn.json
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def ablate(inst, kind):
    """Verbatim copy of mechanism.ablate (mechanism.py parses its CLI at import, so it cannot be imported)."""
    import copy
    i = copy.deepcopy(inst)
    if kind == "no_WB":
        i.WB = {}
    elif kind == "all_wait":
        i.waitable = set(range(i.nV))
    elif kind == "no_AC":
        i.AC = {n: [(i.dep, i.H)] for n in i.AC}
    return i


def cls(e, x):
    return ("ok" if x == e else "unsound_route" if x[0] == "ROUTE" and e[0] == "NO_ROUTE" else
            "false_no_route" if x[0] == "NO_ROUTE" else "late_T" if x[1] > e[1] else "early_T")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fdyn", type=Path, required=True)
    ap.add_argument("--c-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(Path("research/harness-2026-11/F-3.2").resolve()))
    import copy
    import fbase
    import generate
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.frontend import build_instance
    F = a.fdyn / "research/harness-2026-11/F-DYN"
    entries = json.loads((F / "MANIFEST_v3_3.json").read_text())["entries"]
    table = defaultdict(lambda: Counter())
    failures = []
    for f in sorted(a.c_dir.glob("*.jsonl")):
        L = [json.loads(l) for l in f.read_text().splitlines()]
        head = L[0]
        reg, st, h, v = head["packet"].split(":")
        key = f"{reg}|h{h}|{v}"
        for r in L[1:]:
            t = table[key]
            if "status" in r:
                t["unresolved"] += 1
                continue
            t["n"] += 1
            t["exact_agrees_sipp"] += r["exact_agrees_sipp"]
            t["exact_route"] += r["exact"][0] == "ROUTE"
            t["check_py_accept"] += bool(r.get("check_py", "").startswith("ACCEPT"))
            for n in ("n1", "n2", "n3"):
                c = cls(r["exact"], r[n])
                t[f"{n}_{c}"] += 1
                if c != "ok":
                    failures.append(dict(packet=head["packet"], soundness=head["soundness"], origin=r["origin"],
                                         departure=r["departure"], solver=n, cls=c, exact=r["exact"], naive=r[n],
                                         request_sha256=r["request_sha256"], instance_sha256=r["instance_sha256"]))
    by_packet = defaultdict(list)
    for x in failures:
        by_packet[x["packet"]].append(x)
    for p, xs in by_packet.items():
        reg, st, h, v = p.split(":")
        e = next(e for e in entries if (e["region"], e["start"], str(e["horizon_h"]), e["variant"]) == (reg, st, h, v))
        graph = json.loads((a.fdyn / e["cmd"][e["cmd"].index("--graph") + 1]).read_text())
        model = ContactModel.from_packet(str(a.fdyn / e["out"]))
        rdir = a.c_dir / "requests" / reg / Path(e["out"]).name
        for x in xs:
            rf = rdir / f"{x['origin']}__d{x['departure']}.json"
            assert hashlib.sha256(rf.read_bytes()).hexdigest() == x["request_sha256"]
            inst, _ = build_instance(graph, json.loads(rf.read_text()), model)
            _, _, bundle, ih, _ = generate.certify(inst)
            x["instance_sha_matches_c"] = ih == x["instance_sha256"]
            I = fbase.parse_instance(bundle)
            naive = getattr(fbase, f"solve_{x['solver']}")
            x["n_WB_nodes"], x["n_waitable"], x["nV"] = len(I.WB), len(I.waitable), I.nV
            for kind in ("no_WB", "all_wait", "no_AC"):
                J = ablate(I, kind)
                ex, nv = list(fbase.solve_exact(J)[:2]), list(naive(J))
                x[kind] = dict(exact=ex, naive=nv, naive_correct=ex == nv)
            print(json.dumps({k: x[k] for k in ("packet", "origin", "departure", "solver", "cls")}),
                  {k: x[k]["naive_correct"] for k in ("no_WB", "all_wait", "no_AC")}, flush=True)
    a.out.write_text(json.dumps(dict(rule="DESIGN.md (c)", table={k: dict(v) for k, v in sorted(table.items())},
                                     failures=failures), indent=1))


if __name__ == "__main__":
    main()
