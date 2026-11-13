"""SUPPORT_READ_RULE.md inputs: build A (unmasked), C (c651_unknown/1), D (supplied/1) on UA 25T17Z (recorded
window), and the T1 regression packets (HEADLINE /2 + reopening, UA 25T17Z h5 kriged_mean / firms_early, v3.7
manifest commands at Leo 819bcb91); write INPUTS.json with npz sha256 values.
    python3 batch/support_read_inputs.py --main-tree MAIN --leo LEO --out DIR"""
import argparse, hashlib, json, os, subprocess, sys
import numpy as np

W = "/home/user/wildfireguardian"
COMMON = ["--graph", W + "/data/routing/graphs/uiseong_andong_2025/graph.json",
          "--export-dir", W + "/data/routing/latest_inputs_try02/exports/KFS_01", "--event", "KFS_01",
          "--cutoff", "2025-03-25T17:00:00Z", "--region", "uiseong_andong_2025",
          "--window-json", json.dumps({"r0": 14, "r1": 78, "c0": 23, "c1": 95})]
PROV = {"rule": "WIDENED_GRAPH_RULE.md §8(iii)4 pre-test",
        "reason": "supplied/1 twin of the c651_unknown/1 pre-test packet; mask = that packet support[0]",
        "derived_from_npz_sha256": "39140349cada70644152a761b4564786da3d929202b70b2561f1f70880ce59bd"}
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("BUILD FAILED %s\n%s" % (cmd[:3], (r.stdout + r.stderr)[-1500:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-tree", required=True); ap.add_argument("--leo", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    f93 = "research/harness-2026-11/F-9.3/support_mask/build_packet_f93.py"
    inp = {"window_graph": COMMON[1]}
    if not os.path.exists(a.out + "/A"):
        run([sys.executable, "-I", "-B", "integration/src/wfg_latest/build_packet.py", *COMMON, "--out", a.out + "/A"], a.main_tree)
    if not os.path.exists(a.out + "/C"):
        run([sys.executable, "-I", "-B", f93, *COMMON, "--out", a.out + "/C", "--support-rule", "c651_unknown/1"], a.main_tree)
    np.savez(a.out + "/M.npz", support=np.load(a.out + "/C/constructed_arrays.npz")["support"][0].astype(bool))
    if not os.path.exists(a.out + "/D"):
        run([sys.executable, "-I", "-B", f93, *COMMON, "--out", a.out + "/D", "--support-rule", "supplied/1",
             "--support-mask-npz", a.out + "/M.npz", "--support-provenance", json.dumps(PROV, ensure_ascii=False)], a.main_tree)
    for x in "ACD":
        inp[x] = {"dir": a.out + "/" + x, "npz_sha256": sha(a.out + "/%s/constructed_arrays.npz" % x)}
    fd = a.leo + "/research/harness-2026-11/F-DYN"
    m = json.load(open(fd + "/MANIFEST_v3_7.json"))
    inp["fdyn_graph"] = fd + "/_data/graphs_interim/uiseong_andong_2025/graph.json"
    inp["instance_json"] = fd + "/_data/INSTANCE.json"
    inp["t1"] = {}
    for e in m["entries"]:
        if (e["region"], e["start"], e["horizon_h"]) == ("uiseong_andong_2025", "20250325T170000Z", 5) and \
                e["variant"] in ("kriged_mean", "firms_early") and e["transform"] in ("no_reentry/2", "reopening"):
            tag = "%s_%s" % (e["variant"], e["transform"].replace("/", ""))
            out = a.out + "/T1_" + tag
            if not os.path.exists(out + "/HAZARD.json"):
                cmd = list(e["cmd"]); cmd[cmd.index("--out") + 1] = out
                run(cmd, a.leo)
            inp["t1"][tag] = {"dir": out, "npz_sha256": sha(out + "/constructed_arrays.npz"),
                              "hazard_sha256": sha(out + "/HAZARD.json")}
    json.dump(inp, open(a.out + "/INPUTS.json", "w"), indent=1)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv.get("npz_sha256", vv) if isinstance(vv, dict) else vv for kk, vv in v.items()}) for k, v in inp.items()}, indent=1))


if __name__ == "__main__":
    main()
