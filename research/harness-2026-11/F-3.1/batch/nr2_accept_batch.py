"""no_reentry/2 acceptance 6-7 on Leo's 8 samples (MANIFEST_v3_7 @ 819bcb91)."""
import json, subprocess, sys, os, glob
from concurrent.futures import ThreadPoolExecutor
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"
LEO = S + "/leo819"; FD = LEO + "/research/harness-2026-11/F-DYN"; OUT = S + "/f31/nr2_accept"; PK = S + "/pk_nr2"
F31 = "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"
os.makedirs(OUT, exist_ok=True); os.makedirs(PK, exist_ok=True)
m = json.load(open(FD + "/MANIFEST_v3_7.json"))
RAST = {"kriged_mean": FD + "/_data/KFS_01_pswt_ok_toa.tif", "firms_early": FD + "/_data/variants/firms_early.npz",
        "envelope": FD + "/_data/variants/firms_early.npz", "envelope_burnset": FD + "/_data/variants/envelope_burnset_lo.npz"}
SAMPLES = [("yeongdeok_2025", "20250325T110000Z", "20250325T190000Z"), ("uiseong_andong_2025", "20250324T090000Z", None)]
pairs = {}
for e in m["entries"]:
    for reg, st, _ in SAMPLES:
        if e["region"] == reg and e["start"] == st and e["horizon_h"] == 5 and e["transform"] in ("no_reentry/1", "no_reentry/2"):
            pairs.setdefault((reg, st, e["variant"]), {})[e["transform"]] = e
assert len(pairs) == 8 and all(len(v) == 2 for v in pairs.values()), pairs.keys()
def build(e, tag):
    cmd = list(e["cmd"]); out = PK + "/" + tag; cmd[cmd.index("--out") + 1] = out
    r = subprocess.run(cmd, cwd=LEO, capture_output=True, text=True)
    return out, (r.stderr[-400:] if r.returncode else None), cmd
def job(k):
    reg, st, var = k
    tag = "%s__%s_h5_%s" % (reg, st, var)
    res = OUT + "/" + tag + ".json"
    if os.path.exists(res): return tag, "skip"
    p1, err, _ = build(pairs[k]["no_reentry/1"], tag + "__nr1")
    if err: return tag, "BUILD_FAIL nr1 " + err
    p2, err, cmd2 = build(pairs[k]["no_reentry/2"], tag + "__nr2")
    if err: return tag, "BUILD_FAIL nr2 " + err
    if "--synthetic-export-dir" in cmd2:
        exp = os.path.join(LEO, cmd2[cmd2.index("--synthetic-export-dir") + 1], "FORECAST_%s.npz" % st)
    else:
        exp = LEO + "/data/routing/latest_inputs_try02/exports/KFS_01/FORECAST_%s.npz" % st
    meta = PK + "/" + tag + "__meta.json"
    nm = glob.glob(p2 + "/NATIVE_METADATA*.json")
    if nm:
        d = json.load(open(nm[0]))
        json.dump({"no_reentry2": d["settings"]["fdyn"]["no_reentry2"]}, open(meta, "w"))
    inst_start = dict((r, i) for r, s_, i in SAMPLES if s_ == st)[reg] if False else [i for r, s_, i in SAMPLES if r == reg and s_ == st][0]
    cmd = [sys.executable, "-m", "deadline_field.noreentry2_accept", "--graph", FD + "/_data/graphs_interim/%s/graph.json" % reg,
           "--nr1", p1, "--nr2", p2, "--export", exp, "--raster", RAST[var], "--start", st,
           "--instance-json", FD + "/_data/INSTANCE.json", "--region", reg, "--horizon-s", "18000", "--out", res + ".tmp"]
    if nm: cmd += ["--plan-meta", meta]
    if inst_start: cmd += ["--instance-start", inst_start]
    r = subprocess.run(cmd, cwd=F31, capture_output=True, text=True)
    if r.returncode: return tag, "RUN_FAIL " + r.stderr[-800:]
    d = json.load(open(res + ".tmp")); d["manifest_entries"] = pairs[k]; d["leo_commit"] = "819bcb91"; d["export_file"] = exp
    json.dump(d, open(res, "w"), indent=1); os.remove(res + ".tmp")
    return tag, "ok " + r.stdout.strip().replace("\n", " ")[:600]
with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as ex:
    for tag, st in ex.map(job, sorted(pairs)):
        print(tag, st, flush=True)
print("done", flush=True)
