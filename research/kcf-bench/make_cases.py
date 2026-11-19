"""Write cases/<cache>.json: every route-check request of the six recorded caches and the frozen 200-case OLD sample.

    python3 research/kcf-bench/make_cases.py
Deterministic: sample = random.Random(20261119).sample(sorted(job ids), 200) per cache (BENCH_PLAN.md section 2).
"""
import hashlib
import json
import random

from common import CACHES, ROOT, SAMPLE_N, SEED, cases_path

index = json.loads((ROOT / "planner/cache/INDEX.json").read_text())
for cache in CACHES:
    p = ROOT / "planner/cache" / (cache + ".json")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    want = [r for r in index if r['path'] == cache + '.json'][0]['sha256']
    assert sha == want, 'cache does not match planner/cache/INDEX.json: ' + cache
    doc = json.loads(p.read_text())
    cases = []
    for jid in sorted(doc["route_checks"]):
        job = doc["route_checks"][jid]
        q, res = job["request"], job.get("result") or {}
        assert set(q["start"]) == {"node_id"} and set(q["destination"]) == {"node_id"} and not q.get("incoming_edge")
        cases.append({"id": jid, "start": q["start"]["node_id"], "dest": q["destination"]["node_id"],
                      "dwell": q["dwell_s"], "window": list(q["destination_window"]), "offset": int(q["depart_offset_s"]),
                      "peak": q["limits"]["peak_kw_m2"], "dose": q["limits"]["dose_kj_m2"],
                      "incurred": q.get("incurred_dose_kj_m2", 0) or 0,
                      "rec_verdict": res.get("verdict"), "rec_arrival": res.get("arrival_s"),
                      "rec_compute_s": res.get("compute_s")})
    ids = [c["id"] for c in cases]
    sample = random.Random(SEED).sample(sorted(ids), SAMPLE_N)
    out = {"cache": cache, "region": doc["region_id"], "input_time": doc["input_time"], "cache_sha256": sha,
           "n_cases": len(cases), "sample_seed": SEED, "sample": sample, "cases": cases}
    cases_path(cache).write_text(json.dumps(out, separators=(",", ":")))
    print(cache, len(cases), "cases; sample", len(sample), "sha256", sha[:12])
