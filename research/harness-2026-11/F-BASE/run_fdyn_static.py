"""S1/S2 on the F-DYN sample (DESIGN.md dated addition (d)). Re-reads the (c) run's per-request rows, regenerates each
O2 instance with Thomas's build_instance (sha must match the (c) record), and for each hazard reading (no_reentry,
reopening) computes exact, S1 (+ replay on the true instance), S2.

    from the F-3.2 worktree root with its PYTHONPATH:
    python <repo>/research/harness-2026-11/F-BASE/run_fdyn_static.py --fdyn <Leo worktree> --f32 research/harness-2026-11/F-3.2 \
        --packet REGION:START:H:VARIANT --c-dir <(c) run dir> --out-dir OUT
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fdyn", type=Path, required=True)
    ap.add_argument("--f32", type=Path, required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--c-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.f32.resolve()))
    import fbase
    import fbase_static as FS
    import generate
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.frontend import build_instance

    region, start, h, variant = a.packet.split(":")
    cfile = a.c_dir / f"{region}__{start}__h{h}__{variant}.jsonl"
    lines = [json.loads(l) for l in cfile.read_text().splitlines()]
    head, rows = lines[0], lines[1:]
    F = a.fdyn / "research/harness-2026-11/F-DYN"
    entry = next(e for e in json.loads((F / "MANIFEST_v3_3.json").read_text())["entries"]
                 if (e["region"], e["start"], str(e["horizon_h"]), e["variant"]) == (region, start, h, variant))
    graph = json.loads((a.fdyn / entry["cmd"][entry["cmd"].index("--graph") + 1]).read_text())
    model = ContactModel.from_packet(str(a.fdyn / entry["out"]))
    req_dir = a.c_dir / "requests" / region / Path(entry["out"]).name
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / cfile.name
    with out.open("w") as fh:
        fh.write(json.dumps(dict(header=True, packet=a.packet, soundness=head["soundness"], rule="DESIGN.md (d)")) + "\n")
        for r in rows:
            if "status" in r:
                continue
            f = req_dir / f"{r['origin']}__d{r['departure']}.json"
            if hashlib.sha256(f.read_bytes()).hexdigest() != r["request_sha256"]:
                fh.write(json.dumps(dict(origin=r["origin"], departure=r["departure"], status="REQUEST_SHA_MISMATCH")) + "\n")
                continue
            inst, _ = build_instance(graph, json.loads(f.read_text()), model)
            _, _, bundle, ih, _ = generate.certify(inst)  # same bundle text and instance sha as the (c) run
            row = dict(origin=r["origin"], departure=r["departure"], instance_sha256=ih,
                       instance_sha_matches_c=(ih == r["instance_sha256"]))
            if not row["instance_sha_matches_c"]:
                row["status"] = "INSTANCE_SHA_MISMATCH"
                fh.write(json.dumps(row) + "\n"); fh.flush()
                continue
            base = fbase.parse_instance(bundle)
            for reading, I in (("no_reentry", FS.no_reentry(base)), ("reopening", base)):
                t = time.perf_counter()
                ex = fbase.solve_exact(I)
                s1 = FS.solve_static(I, "S1")
                s2 = FS.solve_static(I, "S2")
                s1_replays = bool(fbase.replay(I, s1[2], s1[1])) if s1[0] == "ROUTE" else None
                row[reading] = dict(exact=list(ex[:2]), s1=list(s1[:2]), s1_replays_true=s1_replays, s2=list(s2[:2]),
                                    i_s1_route_rejected=(s1[0] == "ROUTE" and (ex[0] == "NO_ROUTE" or not s1_replays)),
                                    ii_s2_refuses_resolvable=(s2[0] == "NO_ROUTE" and ex[0] == "ROUTE"),
                                    seconds=time.perf_counter() - t)
            fh.write(json.dumps(row) + "\n"); fh.flush()
            print(json.dumps({k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in ("exact", "s1", "s2")})
                              for k, v in row.items() if k in ("origin", "departure", "no_reentry", "reopening")}), flush=True)


if __name__ == "__main__":
    main()
