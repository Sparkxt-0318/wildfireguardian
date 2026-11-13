"""(g) sensitivity: waiting allowed at every node, for reopening and no_reentry/1 (DESIGN.md dated addition (g)).
Instances are built exactly as in the verified runs ((c)/(d) reopening; (f) NR from the NR packet); the instance sha is
checked against the verified row BEFORE the ablation; then waitable := all nodes (ablate "all_wait", verbatim), and
exact, S1 (+replay), S2, S3(600/1800/3600) are solved with the same code.

    from the F-3.2 worktree root with its PYTHONPATH:
    python <repo>/research/harness-2026-11/F-BASE/run_fdyn_allwait.py --fdyn <(c) worktree> --fdyn-nr <NR worktree> \
        --f32 research/harness-2026-11/F-3.2 --packet REGION:START:H:VARIANT --c-dir <(c) run dir> \
        --f-dir <F-BASE/fdyn_f_nr1> --out-dir OUT
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_fdyn_nr import member_ids, sha, swap_ids  # noqa: E402

LABEL = "SENSITIVITY: waiting allowed at every node (not the documented default; default = graph dead ends only)"


def ablate(inst, kind):  # verbatim from summarize_fdyn.py (mechanism.py)
    i = copy.deepcopy(inst)
    if kind == "no_WB": i.WB = {}
    elif kind == "all_wait": i.waitable = set(range(i.nV))
    elif kind == "no_AC": i.AC = {n: [(i.dep, i.H)] for n in i.AC}
    return i


def solve_all(fbase, FS, I):
    ex = fbase.solve_exact(I)
    s1 = FS.solve_static(I, "S1")
    s2 = FS.solve_static(I, "S2")
    s1_rep = bool(fbase.replay(I, s1[2], s1[1])) if s1[0] == "ROUTE" else None
    res = dict(exact=list(ex[:2]), s1=list(s1[:2]), s1_replays_true=s1_rep, s2=list(s2[:2]),
               i_s1_route_rejected=(s1[0] == "ROUTE" and (ex[0] == "NO_ROUTE" or not s1_rep)),
               ii_s2_refuses_resolvable=(s2[0] == "NO_ROUTE" and ex[0] == "ROUTE"))
    for d in (600, 1800, 3600):
        o, T, legs, plans = FS.solve_s3(I, d)
        res[f"s3_{d}"] = dict(outcome=o, T=T, plans=plans, replays=(bool(fbase.replay(I, legs, T)) if o == "ROUTE" else None),
                              i_violation=o == "VIOLATION", ii_refuses_resolvable=(o == "REFUSED" and ex[0] == "ROUTE"))
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ("--fdyn", "--fdyn-nr", "--f32", "--c-dir", "--f-dir", "--out-dir"):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument("--packet", required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.f32.resolve()))
    import fbase
    import fbase_static as FS
    import generate
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.frontend import build_instance

    region, start, h, variant = a.packet.split(":")
    key = (region, start, h, variant)
    name = f"{region}__{start}__h{h}__{variant}.jsonl"
    crow = [json.loads(l) for l in (a.c_dir / name).read_text().splitlines()]
    frow = {(r["origin"], r["departure"]): r for r in map(json.loads, (a.f_dir / name).read_text().splitlines()[1:])}
    F, FN = a.fdyn / "research/harness-2026-11/F-DYN", a.fdyn_nr / "research/harness-2026-11/F-DYN"
    pick = lambda m, tf: next(e for e in json.loads(m.read_text())["entries"]  # noqa: E731
                              if (e["region"], e["start"], str(e["horizon_h"]), e["variant"]) == key
                              and e.get("transform", "reopening") == tf)
    ec, en = pick(F / "MANIFEST_v3_3.json", "reopening"), pick(FN / "MANIFEST_v3_6.json", "no_reentry/1")
    graph = json.loads((a.fdyn / ec["cmd"][ec["cmd"].index("--graph") + 1]).read_text())
    m_ro, m_nr = ContactModel.from_packet(str(a.fdyn / ec["out"])), ContactModel.from_packet(str(a.fdyn_nr / en["out"]))
    old_ids, new_ids = member_ids(a.fdyn / ec["out"]), member_ids(a.fdyn_nr / en["out"])
    req_dir = a.c_dir / "requests" / region / Path(ec["out"]).name
    a.out_dir.mkdir(parents=True, exist_ok=True)
    with (a.out_dir / name).open("w") as fh:
        fh.write(json.dumps(dict(header=True, packet=a.packet, label=LABEL, rule="DESIGN.md (g)",
                                 started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 script_sha256=sha(Path(__file__).read_bytes()))) + "\n")
        for r in crow[1:]:
            if "status" in r:
                continue
            f = req_dir / f"{r['origin']}__d{r['departure']}.json"
            if sha(f.read_bytes()) != r["request_sha256"]:
                fh.write(json.dumps(dict(origin=r["origin"], departure=r["departure"], status="REQUEST_SHA_MISMATCH")) + "\n")
                continue
            req = json.loads(f.read_text())
            row = dict(origin=r["origin"], departure=r["departure"], label=LABEL)
            fr = frow[(r["origin"], r["departure"])]
            for reading, q, model, ref in (("reopening", req, m_ro, r["instance_sha256"]),
                                           ("no_reentry/1", swap_ids(req, old_ids, new_ids), m_nr, fr["instance_sha256"])):
                inst, _ = build_instance(graph, q, model)
                _, _, bundle, ih, _ = generate.certify(inst)
                if ih != ref:
                    row[reading] = dict(status="INSTANCE_SHA_MISMATCH", instance_sha256=ih)
                    continue
                t = time.perf_counter()
                res = solve_all(fbase, FS, ablate(fbase.parse_instance(bundle), "all_wait"))
                res.update(instance_sha256=ih, instance_sha_matches_verified=True, seconds=time.perf_counter() - t)
                row[reading] = res
            fh.write(json.dumps(row) + "\n"); fh.flush()
            print(json.dumps({k: (v["exact"] if isinstance(v, dict) and "exact" in v else v) for k, v in row.items()
                              if k != "label"}), flush=True)


if __name__ == "__main__":
    main()
