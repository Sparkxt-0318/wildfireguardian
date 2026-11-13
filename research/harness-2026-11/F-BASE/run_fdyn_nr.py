"""No-re-entry S1/S2 and S3 on the F-DYN sample, built FROM THE NO-RE-ENTRY PACKET (DESIGN.md dated addition (f)).

For every (c) request row: the (c) request is read (sha checked); request_NR = the same request with each member-id key
in budgets.dose and incurred replaced by the NR packet's member id at the same index (asserted to be the only change);
the O2 instance is built by the unchanged build_instance from ContactModel.from_packet(NR packet). No block transform.
Computes exact, S1 (+ replay on the true NR instance), S2, and S3(600/1800/3600).

    from the F-3.2 worktree root with its PYTHONPATH:
    python <repo>/research/harness-2026-11/F-BASE/run_fdyn_nr.py --fdyn <(c) packets worktree> --fdyn-nr <NR worktree> \
        --nr-manifest MANIFEST_v3_6.json --transform no_reentry/1 --f32 research/harness-2026-11/F-3.2 \
        --packet REGION:START:H:VARIANT --c-dir <(c) run dir> --out-dir OUT [--only ORIGIN:DEP]
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def member_ids(packet_dir: Path):
    return [m["id"] for m in json.loads((packet_dir / "HAZARD.json").read_text())["members"]]


def swap_ids(req: dict, old: list, new: list) -> dict:
    if len(old) != len(new):
        raise SystemExit(f"member count differs: {len(old)} vs {len(new)}")
    m = dict(zip(old, new))
    r = copy.deepcopy(req)
    for path in (("budgets", "dose"), ("incurred",)):
        d = r
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = {m[k]: v for k, v in d[path[-1]].items()}
    # assert: only those keys changed
    a, b = copy.deepcopy(req), copy.deepcopy(r)
    for x in (a, b):
        x["budgets"]["dose"] = sorted(x["budgets"]["dose"].values())
        x["incurred"] = sorted(x["incurred"].values())
    assert a == b, "request_NR differs from the (c) request beyond member-id keys"
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fdyn", type=Path, required=True, help="worktree holding the (c) reopening packets (v3.3)")
    ap.add_argument("--fdyn-nr", type=Path, required=True, help="worktree holding the NR packets")
    ap.add_argument("--nr-manifest", required=True)
    ap.add_argument("--transform", required=True)
    ap.add_argument("--f32", type=Path, required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--c-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    sys.path.insert(0, str(a.f32.resolve()))
    import fbase
    import fbase_static as FS
    import generate
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.frontend import build_instance

    region, start, h, variant = a.packet.split(":")
    key = (region, start, h, variant)
    cfile = a.c_dir / f"{region}__{start}__h{h}__{variant}.jsonl"
    lines = [json.loads(l) for l in cfile.read_text().splitlines()]
    head, rows = lines[0], lines[1:]
    F = a.fdyn / "research/harness-2026-11/F-DYN"
    FN = a.fdyn_nr / "research/harness-2026-11/F-DYN"
    pick = lambda m, tf: next(e for e in json.loads(m.read_text())["entries"]  # noqa: E731
                              if (e["region"], e["start"], str(e["horizon_h"]), e["variant"]) == key
                              and e.get("transform", "reopening") == tf)
    entry_c = pick(F / "MANIFEST_v3_3.json", "reopening")
    entry_nr = pick(FN / a.nr_manifest, a.transform)
    graph = json.loads((a.fdyn / entry_c["cmd"][entry_c["cmd"].index("--graph") + 1]).read_text())
    nr_dir = a.fdyn_nr / entry_nr["out"]
    model = ContactModel.from_packet(str(nr_dir))
    old_ids, new_ids = member_ids(a.fdyn / entry_c["out"]), member_ids(nr_dir)
    req_dir = a.c_dir / "requests" / region / Path(entry_c["out"]).name
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / (cfile.name if a.only is None else f"{cfile.stem}__{a.only.replace(':', '_d')}.jsonl")
    with out.open("w") as fh:
        fh.write(json.dumps(dict(
            header=True, packet=a.packet, transform=a.transform, label=f"{a.transform} (labelled variant; not the default)"
            if a.transform == "no_reentry/1" else a.transform, soundness=head["soundness"], rule="DESIGN.md (f)",
            nr_manifest=a.nr_manifest, nr_packet=entry_nr["out"],
            nr_hazard_sha256=sha((nr_dir / "HAZARD.json").read_bytes()),
            started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            script_sha256=sha(Path(__file__).read_bytes()))) + "\n")
        for r in rows:
            if "status" in r:
                continue
            if a.only and f"{r['origin']}:{r['departure']}" != a.only:
                continue
            f = req_dir / f"{r['origin']}__d{r['departure']}.json"
            if sha(f.read_bytes()) != r["request_sha256"]:
                fh.write(json.dumps(dict(origin=r["origin"], departure=r["departure"], status="REQUEST_SHA_MISMATCH")) + "\n")
                continue
            req_nr = swap_ids(json.loads(f.read_text()), old_ids, new_ids)
            inst, _ = build_instance(graph, req_nr, model)
            _, _, bundle, ih, _ = generate.certify(inst)
            I = fbase.parse_instance(bundle)
            t = time.perf_counter()
            ex = fbase.solve_exact(I)
            s1 = FS.solve_static(I, "S1")
            s2 = FS.solve_static(I, "S2")
            s1_rep = bool(fbase.replay(I, s1[2], s1[1])) if s1[0] == "ROUTE" else None
            res = dict(exact=list(ex[:2]), s1=list(s1[:2]), s1_replays_true=s1_rep, s2=list(s2[:2]),
                       i_s1_route_rejected=(s1[0] == "ROUTE" and (ex[0] == "NO_ROUTE" or not s1_rep)),
                       ii_s2_refuses_resolvable=(s2[0] == "NO_ROUTE" and ex[0] == "ROUTE"))
            for d in (600, 1800, 3600):
                o, T, legs, plans = FS.solve_s3(I, d)
                res[f"s3_{d}"] = dict(outcome=o, T=T, plans=plans,
                                      replays=(bool(fbase.replay(I, legs, T)) if o == "ROUTE" else None),
                                      i_violation=o == "VIOLATION", ii_refuses_resolvable=(o == "REFUSED" and ex[0] == "ROUTE"))
            res["seconds"] = time.perf_counter() - t
            row = dict(origin=r["origin"], departure=r["departure"], request_nr_sha256=sha(json.dumps(req_nr, sort_keys=True).encode()),
                       instance_sha256=ih, blocked_edges_at_dep=sorted(j for j, v in I.EB.items() if any(lo <= I.dep <= hi for lo, hi in v)),
                       no_reentry=res)
            fh.write(json.dumps(row) + "\n"); fh.flush()
            print(json.dumps(dict(origin=r["origin"], departure=r["departure"], exact=res["exact"], s1=res["s1"], s2=res["s2"],
                                  s3={d: res[f"s3_{d}"]["outcome"] for d in (600, 1800, 3600)})), flush=True)


if __name__ == "__main__":
    main()
