"""Build each selected F-DYN v3 packet from the manifest, run the deadline field (with full-checker witnesses), delete the packet."""
import json, shlex, subprocess, sys, os, shutil, hashlib
from concurrent.futures import ThreadPoolExecutor
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"
LEO = S + "/leo34"; OUT = S + "/f31/fdyn_v34"; os.makedirs(OUT, exist_ok=True)
F31 = "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"
m = json.load(open(LEO + "/research/harness-2026-11/F-DYN/MANIFEST_v3_4.json"))
rec = {"uiseong_andong_2025": ["20250323T010000Z", "20250324T090000Z", "20250325T170000Z"],
       "yeongdeok_2025": ["20250325T190000Z", "20250325T230000Z", "20250326T080000Z"]}
variants = sys.argv[1].split(",")
sel = [e for e in m["entries"] if e["start"] in rec.get(e["region"], []) and e["variant"] in variants]
sel.sort(key=lambda e: (e["horizon_h"], e["region"] != "uiseong_andong_2025", e["start"]))
def job(e):
    tag = "%s__%s_h%d_%s" % (e["region"], e["start"], e["horizon_h"], e["variant"])
    res = OUT + "/" + tag + ".json"
    if os.path.exists(res):
        return tag, "skip"
    pk = os.path.join(LEO, e["out"])
    r = subprocess.run(e["cmd"], cwd=LEO, capture_output=True, text=True)
    if r.returncode:
        return tag, "BUILD_FAIL " + r.stderr[-400:]
    h = hashlib.sha256(open(pk + "/HAZARD.json", "rb").read()).hexdigest()
    g = LEO + "/research/harness-2026-11/F-DYN/_data/graphs_interim/%s/graph.json" % e["region"]
    cmd = [sys.executable, "-m", "deadline_field.fdyn_run", "--graph", g, "--packet", pk,
           "--instance-json", LEO + "/research/harness-2026-11/F-DYN/_data/INSTANCE.json", "--region", e["region"],
           "--start", e["start"], "--horizon-s", str(e["horizon_h"] * 3600), "--out", res + ".tmp"]
    r2 = subprocess.run(cmd, cwd=F31, capture_output=True, text=True)
    if r2.returncode:
        return tag, "RUN_FAIL " + r2.stderr[-600:]
    d = json.load(open(res + ".tmp")); d["manifest_entry"] = e; d["hazard_sha256"] = h
    json.dump(d, open(res, "w")); os.remove(res + ".tmp")
    shutil.rmtree(pk, ignore_errors=True)
    return tag, "ok %s" % json.dumps({k: d[k] for k in ("classes", "witness_checks")})
with ThreadPoolExecutor(int(sys.argv[2])) as ex:
    for tag, st in ex.map(job, sel):
        print(tag, st, flush=True)
