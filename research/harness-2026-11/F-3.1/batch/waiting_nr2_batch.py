"""WAITING_NR2_RULE.md batch: rebuild each HEADLINE /2 packet (v3.7 manifest, scratch --out), run
deadline_field.waiting_nr2, delete the packet. One worker; checkpointed (finished outputs are skipped).
    python3 batch/waiting_nr2_batch.py [--only REGION__START_hH_VARIANT]"""
import json, subprocess, sys, os, shutil
from concurrent.futures import ThreadPoolExecutor
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"
LEO = S + "/leo819"; FD = LEO + "/research/harness-2026-11/F-DYN"; OUT = S + "/f31/waiting_nr2"
os.makedirs(OUT, exist_ok=True)
F31 = "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"
m = json.load(open(FD + "/MANIFEST_v3_7.json"))
ents = sorted([e for e in m["entries"] if e["start_kind"] == "recorded" and e["transform"] == "no_reentry/2"],
              key=lambda e: (e["region"] != "uiseong_andong_2025", e["horizon_h"], e["start"], e["variant"]))
assert len(ents) == 48
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 1


def job(e):
    tag = "%s__%s_h%d_%s" % (e["region"], e["start"], e["horizon_h"], e["variant"])
    res = OUT + "/" + tag + ".json"
    if os.path.exists(res):
        return tag, "skip"
    cmd = list(e["cmd"]); pk = OUT + "/pk_" + tag; cmd[cmd.index("--out") + 1] = pk
    shutil.rmtree(pk, ignore_errors=True)
    r = subprocess.run(cmd, cwd=LEO, capture_output=True, text=True)
    if r.returncode:
        return tag, "BUILD_FAIL " + r.stderr[-300:]
    c2 = [sys.executable, "-m", "deadline_field.waiting_nr2", "--graph", FD + "/_data/graphs_interim/%s/graph.json" % e["region"],
          "--packet", pk, "--instance-json", FD + "/_data/INSTANCE.json", "--region", e["region"], "--start", e["start"],
          "--horizon-s", str(e["horizon_h"] * 3600), "--variant", e["variant"],
          "--summary", F31 + "/results/HEADLINE_NR2_summary.json", "--out", res + ".tmp"]
    r2 = subprocess.run(c2, cwd=F31, capture_output=True, text=True)
    shutil.rmtree(pk, ignore_errors=True)
    if os.path.exists(pk + ".plan.npz"): os.remove(pk + ".plan.npz")
    if r2.returncode:
        return tag, "RUN_FAIL %s %s" % (r2.returncode, r2.stderr[-500:])
    os.rename(res + ".tmp", res)
    return tag, "ok " + r2.stdout.strip()[-500:]


print("start workers=%d" % workers, flush=True)
todo = [e for e in ents if not only or "%s__%s_h%d_%s" % (e["region"], e["start"], e["horizon_h"], e["variant"]) == only]
with ThreadPoolExecutor(workers) as ex:
    for tag, st in ex.map(job, todo):
        print(tag, st, flush=True)
print("done", flush=True)
