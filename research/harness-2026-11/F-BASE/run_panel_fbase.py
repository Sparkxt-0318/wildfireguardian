"""Run F-BASE on the 20 frozen panel missions under the rules frozen in DESIGN.md.

Inputs: bundles produced by F-3.2's frozen run_panel.py (PR #116 head a03f218), one ``.wfgc`` per mission, and
F-3.2's committed panel summary (recorded SIPP verdict/T and instance sha256 per mission).

Per mission:
  * instance identity: sha256 of the bytes from ``INSTANCE`` through the newline after ``END_INSTANCE``,
    compared with F-3.2's recorded ``instance_sha256``;
  * solvers exact, n1, n2, n3, each in a fresh process (3 runs; median wall and max peak RSS reported; parse
    time reported separately);
  * agreement of verdict and arrival second with the recorded SIPP result;
  * the exact witness is replayed by fbase.replay and, where its T equals the bundle's claim, spliced into the
    bundle in place of F-3.2's witness and checked by F-3.2's Python checker (check_py.py).

    python research/harness-2026-11/F-BASE/run_panel_fbase.py --bundles DIR --f32 <F-3.2 dir at a03f218> \
        --summary <F-3.2 results/panel_summary_py312.json> [--out RESULTS_panel.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def instance_sha(text: str) -> str:
    a = text.index("INSTANCE")
    b = text.index("END_INSTANCE") + len("END_INSTANCE")
    if text[b:b + 1] == "\n":
        b += 1
    return hashlib.sha256(text[a:b].encode()).hexdigest()


def child(solver, path):
    sys.path.insert(0, str(HERE))
    import fbase
    t0 = time.perf_counter()
    inst = fbase.parse_instance(Path(path).read_text())
    t1 = time.perf_counter()
    if solver == "exact":
        claim, T, wit = fbase.solve_exact(inst)
    else:
        claim, T = getattr(fbase, f"solve_{solver}")(inst)
        wit = []
    t2 = time.perf_counter()
    ok = fbase.replay(inst, wit, T) if (solver == "exact" and claim == "ROUTE") else None
    print(json.dumps(dict(claim=claim, T=T, witness=wit, replay_ok=ok, parse_s=t1 - t0, search_s=t2 - t1,
                          peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)))


def splice_witness(bundle_text, witness):
    head, rest = bundle_text.split("\nWITNESS ", 1)
    after = rest[rest.index("\nCERT") if "\nCERT" in rest else rest.index("\nCOCERT"):]
    legs = [f"{k} {x} {a} {b}" for k, x, a, b in witness]
    return head + "\nWITNESS " + str(len(legs)) + ("\n" + "\n".join(legs) if legs else "") + after


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", type=Path)
    ap.add_argument("--f32", type=Path)
    ap.add_argument("--summary", type=Path)
    ap.add_argument("--out", type=Path, default=HERE / "RESULTS_panel.json")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--child", nargs=2, default=None)
    args = ap.parse_args()
    if args.child:
        child(*args.child)
        return
    summary = {row["mission"]: row for row in json.loads(args.summary.read_text())}
    rows = []
    for path in sorted(args.bundles.glob("*.wfgc")):
        mission = path.stem.split("__", 1)[1]
        ref = summary[mission]
        text = path.read_text()
        rec_claim, rec_T = ref["recorded_sipp"][0][0], ref["recorded_sipp"][0][1]
        row = dict(mission=mission, region=ref["region"], instance_sha256=instance_sha(text),
                   instance_sha256_matches_f32=instance_sha(text) == ref["instance_sha256"],
                   recorded=[rec_claim, rec_T], solvers={})
        for solver in ("exact", "n1", "n2", "n3"):
            runs = []
            for _ in range(args.repeats):
                r = subprocess.run([sys.executable, __file__, "--child", solver, str(path)], capture_output=True,
                                   text=True, check=True)
                runs.append(json.loads(r.stdout.strip().splitlines()[-1]))
            first = runs[0]
            res = dict(claim=first["claim"], T=first["T"],
                       agrees=(first["claim"] == rec_claim and (first["T"] == rec_T or rec_claim == "NO_ROUTE")),
                       parse_s_median=statistics.median(r["parse_s"] for r in runs),
                       search_s_median=statistics.median(r["search_s"] for r in runs),
                       peak_rss_mib_max=max(r["peak_rss_mib"] for r in runs),
                       consistent_across_repeats=all((r["claim"], r["T"]) == (first["claim"], first["T"]) for r in runs))
            if solver == "exact":
                res["replay_ok"] = first["replay_ok"]
                if first["claim"] == "ROUTE" and first["T"] == ref["T"] and ref["claim"] == "ROUTE":
                    spliced = path.with_suffix(".fbase_witness.wfgc")
                    spliced.write_text(splice_witness(text, first["witness"]))
                    r = subprocess.run([sys.executable, str(args.f32 / "check_py.py"), str(spliced)],
                                       capture_output=True, text=True)
                    res["f32_check_py_on_fbase_witness"] = r.stdout.strip() or r.stderr.strip()[-200:]
                    res["witness_legs"] = len(first["witness"])
            row["solvers"][solver] = res
        rows.append(row)
        print(json.dumps({"mission": mission, "recorded": row["recorded"],
                          **{k: (v["claim"], v["T"], v["agrees"]) for k, v in row["solvers"].items()},
                          "sha_ok": row["instance_sha256_matches_f32"]}), flush=True)
    tally = {s: dict(agree=sum(r["solvers"][s]["agrees"] for r in rows), total=len(rows)) for s in ("exact", "n1", "n2", "n3")}
    args.out.write_text(json.dumps(dict(rule="DESIGN.md (F-BASE frozen comparison rules)", tally=tally, rows=rows), indent=1))
    print(json.dumps(tally))


if __name__ == "__main__":
    main()
