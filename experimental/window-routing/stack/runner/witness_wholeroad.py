"""Offline (outside every deadline) whole-road check of an INDEPENDENT checker's relaxation witness with the unchanged
integration whole-road checker (adaptive_checker.HybridChecker, hash-pinned by the JOB). Used only by phase_tally_v2 to
decide whether a centre-model counterexample to a full-model optimum/refusal claim is also feasible in the full model.
Usage: witness_wholeroad.py ROOT RUN_DIR INDEPENDENT_JSON OUT_JSON [WALL_S]"""
import hashlib, json, pathlib, sys, time
R, run, indp, outp = (pathlib.Path(a) for a in sys.argv[1:5]); wall = float(sys.argv[5]) if len(sys.argv) > 5 else 150.0
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
job = json.loads((run / "JOB.json").read_text()); ind = json.loads(indp.read_text())
wit = ((ind.get("relaxation") or {}).get("witness")) or {}
src = R / job["source_root"]
sys.path[:0] = [str(src / "baseline/routing-package"), str(src / "baseline"), str(src / "search")]
import importlib
m = importlib.import_module(job["checker_module"])
files = {n: sha(pathlib.Path(m.__file__).parent / n) for n in job["checker_sha256"]}
assert files == job["checker_sha256"], "CHECKER_MODULE_HASH_MISMATCH"
from mission_contract import graph_digest
for k in ("graph_path", "request_path"):
    assert sha(R / job[k]) == job["input_sha256"][k], "INPUT_HASH_MISMATCH:" + k
graph = json.loads((R / job["graph_path"]).read_text()); request = json.loads((R / job["request_path"]).read_text())
t = time.perf_counter()
rec = m.HybridChecker(R / job["source_directory"]).check(graph, request, wit.get("legs") or [], wit.get("destination"),
        deadline=time.perf_counter() + wall, wall_s=wall, expected_graph_revision=graph["revision"], expected_graph_sha256=graph_digest(graph))
out = {"schema": "wfg.rda.witness-wholeroad/1", "label": run.name, "scope": "offline diagnostic outside the deadline; never changes on-time counts",
       "witness_arrival": wit.get("arrival"), "witness_destination": wit.get("destination"), "witness_n_legs": len(wit.get("legs") or []),
       "checker_module_sha256": files, "status": rec.get("status"), "reason": rec.get("reason"), "elapsed_s": time.perf_counter() - t,
       "wall_s": wall, "check": rec}
outp.write_text(json.dumps(out, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
print(run.name, out["status"], out["reason"], round(out["elapsed_s"], 2))
