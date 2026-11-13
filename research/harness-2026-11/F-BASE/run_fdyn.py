"""F-BASE on F-DYN v3.3 packets: DESIGN.md dated addition (c), fixed before any packet was built.

Per packet (one process per packet, packets sequential): Leo's fdyn/requests.py writes the requests; the sample is
origins sorted by origin_id, every 10th (index 0, 10, ...), x departures {0, 7200}. Per request: Thomas's
frontend.build_instance + generate.certify (F-3.2 @ a03f218, unchanged) -> SIPP claim/T and a .wfgc bundle; its
INSTANCE block -> F-BASE exact, N1, N2, N3; the exact ROUTE witness is replayed and spliced into the bundle and checked
by F-3.2's check_py.py.

    run from the F-3.2 worktree root with its PYTHONPATH:
    python <repo>/research/harness-2026-11/F-BASE/run_fdyn.py --fdyn <Leo worktree> --f32 research/harness-2026-11/F-3.2 \
        --packet REGION:START:H:VARIANT --out-dir OUT
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
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
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--departures", type=int, nargs="+", default=[0, 7200])
    ap.add_argument("--origin-stride", type=int, default=10)
    ap.add_argument("--max-requests", type=int, default=None, help="smoke only")
    a = ap.parse_args()
    sys.path.insert(0, str(a.f32.resolve()))
    import fbase
    import generate
    from run_panel_fbase import splice_witness
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.frontend import build_instance

    region, start, h, variant = a.packet.split(":")
    F = a.fdyn / "research/harness-2026-11/F-DYN"
    manifest = json.loads((F / "MANIFEST_v3_3.json").read_text())
    entry = next(e for e in manifest["entries"] if (e["region"], e["start"], str(e["horizon_h"]), e["variant"]) ==
                 (region, start, h, variant))
    req_dir = a.out_dir / "requests"
    subprocess.run([sys.executable, str(F / "fdyn/requests.py"), "--manifest", str(F / "MANIFEST_v3_3.json"),
                    "--instance", str(F / "_data/INSTANCE.json"), "--out-dir", str(req_dir), "--only", a.packet],
                   check=True, cwd=a.fdyn, capture_output=True)
    packet = a.fdyn / entry["out"]
    graph_path = Path(entry["cmd"][entry["cmd"].index("--graph") + 1])
    graph = json.loads((a.fdyn / graph_path).read_text())
    t0 = time.perf_counter()
    model = ContactModel.from_packet(str(packet))
    model_s = time.perf_counter() - t0
    files = sorted((req_dir / region / packet.name).glob("*.json"))
    by_origin = {}
    for f in files:
        origin, dep = f.stem.rsplit("__d", 1)
        by_origin.setdefault(origin, {})[int(dep)] = f
    origins = sorted(by_origin)[::a.origin_stride]
    todo = [(o, d, by_origin[o][d]) for o in origins for d in a.departures if d in by_origin[o]]
    if a.max_requests:
        todo = todo[:a.max_requests]
    rows = []
    out = a.out_dir / f"{region}__{start}__h{h}__{variant}.jsonl"
    with out.open("w") as fh:
        fh.write(json.dumps(dict(header=True, packet=a.packet, soundness=entry["soundness"], packet_dir=entry["out"],
                                 hazard_sha256=hashlib.sha256((packet / "HAZARD.json").read_bytes()).hexdigest(),
                                 n_origins_total=len(by_origin), origins_sampled=origins, departures=a.departures,
                                 contact_model_s=model_s)) + "\n")
        for origin, dep, f in todo:
            request = json.loads(f.read_text())
            row = dict(origin=origin, departure=dep, request_sha256=hashlib.sha256(f.read_bytes()).hexdigest())
            try:
                t = time.perf_counter()
                inst, _ = build_instance(graph, request, model)
                row["build_s"] = time.perf_counter() - t
                t = time.perf_counter()
                claim, T, text, ih, _ = generate.certify(inst)
                row.update(sipp=[claim, T if claim == "ROUTE" else None], certify_s=time.perf_counter() - t,
                           instance_sha256=ih)
            except Exception as err:  # unresolved or build failure: reported, never replaced
                row.update(status="SIPP_UNRESOLVED_OR_BUILD_FAILED", error=f"{type(err).__name__}: {err}"[:300])
                fh.write(json.dumps(row) + "\n"); fh.flush()
                continue
            I = fbase.parse_instance(text)
            for name, fn in (("exact", fbase.solve_exact), ("n1", fbase.solve_n1), ("n2", fbase.solve_n2),
                             ("n3", fbase.solve_n3)):
                t = time.perf_counter()
                res = fn(I)
                row[name] = [res[0], res[1]]
                row[name + "_s"] = time.perf_counter() - t
                if name == "exact":
                    wit = res[2]
            row["exact_agrees_sipp"] = row["exact"] == row["sipp"]
            if row["exact"][0] == "ROUTE":
                row["replay_ok"] = fbase.replay(I, wit, row["exact"][1])
                if row["exact"] == row["sipp"]:
                    sp = a.out_dir / "spliced.wfgc"
                    sp.write_text(splice_witness(text, wit))
                    c = subprocess.run([sys.executable, str(a.f32 / "check_py.py"), str(sp)], capture_output=True,
                                       text=True)
                    row["check_py"] = (c.stdout.strip() or c.stderr.strip()[-200:])[:80]
            row["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            fh.write(json.dumps(row) + "\n"); fh.flush()
            print(json.dumps({k: row.get(k) for k in ("origin", "departure", "sipp", "exact", "n1", "n2", "n3",
                                                       "check_py")}), flush=True)


if __name__ == "__main__":
    main()
