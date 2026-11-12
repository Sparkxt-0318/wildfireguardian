import json, subprocess, sys, os, shutil
from concurrent.futures import ThreadPoolExecutor
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"
LEO = S + "/leo"; OUT = S + "/f31/spot"; os.makedirs(OUT, exist_ok=True)
F31 = "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"
m = json.load(open(LEO + "/research/harness-2026-11/F-DYN/MANIFEST_v3_3.json"))
rec = {"uiseong_andong_2025": ["20250323T010000Z", "20250324T090000Z", "20250325T170000Z"],
       "yeongdeok_2025": ["20250325T190000Z", "20250325T230000Z", "20250326T080000Z"]}
base = [e for e in m["entries"] if e["start"] in rec.get(e["region"], []) and e["variant"] == "kriged_mean" and e["horizon_h"] == 5]
jobs = []
for e in sorted(base, key=lambda e: (e["region"] != "uiseong_andong_2025", e["start"])):
    for d in (0, 500, 1000, 2000):
        cmd = list(e["cmd"]); i = cmd.index("--arrival"); cmd[i + 1] = S + "/spot/dilate_%dm_lag0s.npz" % d
        cmd[cmd.index("--arrival-variant") + 1] = "dilate_%dm_lag0s" % d
        o = cmd.index("--out"); cmd[o + 1] = S + "/spot/pk_%s_%s_%d" % (e["region"], e["start"], d)
        jobs.append((e, d, cmd))
def job(x):
    e, d, cmd = x
    tag = "%s__%s_h5_d%d" % (e["region"], e["start"], d)
    res = OUT + "/" + tag + ".json"
    if os.path.exists(res): return tag, "skip"
    pk = cmd[cmd.index("--out") + 1]
    r = subprocess.run(cmd, cwd=LEO, capture_output=True, text=True)
    if r.returncode: return tag, "BUILD_FAIL " + r.stderr[-400:]
    g = LEO + "/research/harness-2026-11/F-DYN/_data/graphs_interim/%s/graph.json" % e["region"]
    c2 = [sys.executable, "-m", "deadline_field.fdyn_run", "--graph", g, "--packet", pk,
          "--instance-json", LEO + "/research/harness-2026-11/F-DYN/_data/INSTANCE.json", "--region", e["region"],
          "--start", e["start"], "--horizon-s", "18000", "--out", res + ".tmp"]
    r2 = subprocess.run(c2, cwd=F31, capture_output=True, text=True)
    sha = __import__("hashlib").sha256(open(pk + "/HAZARD.json", "rb").read()).hexdigest() if os.path.exists(pk + "/HAZARD.json") else None
    shutil.rmtree(pk, ignore_errors=True)
    if r2.returncode: return tag, "RUN_FAIL " + r2.stderr[-600:]
    dd = json.load(open(res + ".tmp")); dd["spot"] = {"d_m": d, "lag_s": 0, "build_cmd": cmd, "hazard_sha256": sha}
    json.dump(dd, open(res, "w")); os.remove(res + ".tmp")
    return tag, "ok %s" % json.dumps({k: dd[k] for k in ("classes", "witness_checks")})
print(len(jobs), "jobs", flush=True)
with ThreadPoolExecutor(int(sys.argv[1])) as ex:
    for tag, st in ex.map(job, jobs): print(tag, st, flush=True)
print("done", flush=True)
