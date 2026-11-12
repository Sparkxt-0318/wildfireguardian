"""Headline runs: v3.6 no-re-entry + reopening packet pairs x 4 variants x 6 recorded starts x {5 h, 8 h}."""
import json, subprocess, sys, os, shutil, hashlib
from concurrent.futures import ThreadPoolExecutor
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"
LEO = S + "/leo046"; FD = LEO + "/research/harness-2026-11/F-DYN"; OUT = S + "/f31/headline_nr1"; PK = S + "/pk_headline"
os.makedirs(OUT, exist_ok=True); os.makedirs(PK, exist_ok=True)
F31 = "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"
sh = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
m = json.load(open(FD + "/MANIFEST_v3_6.json"))
writer = {"leo_commit": subprocess.run(["git", "-C", LEO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
          "build_py_sha256": sh(FD + "/fdyn/build.py"), "manifest": "MANIFEST_v3_6.json",
          "manifest_sha256": sh(FD + "/MANIFEST_v3_6.json")}
pairs = {}
for e in m["entries"]:
    if e["start_kind"] == "recorded":
        pairs.setdefault((e["region"], e["start"], e["horizon_h"], e["variant"]), {})[e["transform"]] = e
keys = sorted(pairs, key=lambda k: (k[0] != "uiseong_andong_2025", k[2], k[1], k[3]))
assert len(keys) == 48 and all(set(v) == {"reopening", "no_reentry/1"} for v in pairs.values()), len(keys)
def build(e, tag):
    cmd = list(e["cmd"]); out = PK + "/" + tag; cmd[cmd.index("--out") + 1] = out
    r = subprocess.run(cmd, cwd=LEO, capture_output=True, text=True)
    return out, (r.stderr[-400:] if r.returncode else None)
def job(k):
    region, start, h, var = k
    tag = "%s__%s_h%d_%s" % (region, start, h, var)
    res = OUT + "/" + tag + ".json"
    if os.path.exists(res): return tag, "skip"
    nr, err = build(pairs[k]["no_reentry/1"], tag + "__nr")
    if err: return tag, "BUILD_FAIL nr " + err
    re_, err = build(pairs[k]["reopening"], tag + "__re")
    if err: return tag, "BUILD_FAIL re " + err
    cmd = [sys.executable, "-m", "deadline_field.headline", "--graph", FD + "/_data/graphs_interim/%s/graph.json" % region,
           "--window-graph", LEO + "/data/routing/graphs/%s/graph.json" % region, "--nr-packet", nr, "--re-packet", re_,
           "--instance-json", FD + "/_data/INSTANCE.json", "--region", region, "--start", start,
           "--horizon-s", str(h * 3600), "--out", res + ".tmp"]
    r = subprocess.run(cmd, cwd=F31, capture_output=True, text=True)
    if r.returncode: return tag, "RUN_FAIL " + r.stderr[-600:]
    d = json.load(open(res + ".tmp"))
    d["manifest_entries"] = pairs[k]; d["writer_identity"] = writer
    d["build_summaries"] = {t: json.load(open(p + "/BUILD_SUMMARY.json")) if os.path.exists(p + "/BUILD_SUMMARY.json") else None
                            for t, p in (("noreentry", nr), ("reopening", re_))}
    json.dump(d, open(res, "w")); os.remove(res + ".tmp")
    for p in (nr, re_):
        shutil.rmtree(p, ignore_errors=True)
        if os.path.exists(p + ".plan.npz"): os.remove(p + ".plan.npz")
    return tag, "ok " + json.dumps({x: d[x] for x in ("witness_checks", "acceptance7", "verdict_diff_noreentry_vs_clearing", "no_route_split")})
with ThreadPoolExecutor(int(sys.argv[1])) as ex:
    for tag, st in ex.map(job, keys):
        print(tag, st, flush=True)
print("done", flush=True)
