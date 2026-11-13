"""Burnset blocked-road fraction per region-start (v3.3 envelope_burnset, 5 h packets built from Leo MANIFEST_v3_3).
Edges whose closed (and router) blocked-start set covers the whole horizon [0, H]. Paths are this host's scratch layout;
adapt S/LEO to your checkout of leo/f-c1-see-before-leave 4463892."""
import json, subprocess, sys, os, shutil
sys.path.insert(0, "/home/user/wildfireguardian/research/harness-2026-11/F-3.1"); sys.path.insert(0, "/home/user/wildfireguardian")
from deadline_field.real import PacketModel
S = "/tmp/claude-0/-home-user-wildfireguardian/bb5282c2-950b-50f1-81b9-ac1de20b6fe6/scratchpad"; LEO = S + "/leo"
m = json.load(open(LEO + "/research/harness-2026-11/F-DYN/MANIFEST_v3_3.json"))
rec = {"uiseong_andong_2025": ["20250323T010000Z", "20250324T090000Z", "20250325T170000Z"],
       "yeongdeok_2025": ["20250325T190000Z", "20250325T230000Z", "20250326T080000Z"]}
out = {}
for e in m["entries"]:
    if e["variant"] != "envelope_burnset" or e["horizon_h"] != 5 or e["start"] not in rec.get(e["region"], []): continue
    pk = os.path.join(LEO, e["out"]); subprocess.run(e["cmd"], cwd=LEO, check=True, capture_output=True)
    g = LEO + "/research/harness-2026-11/F-DYN/_data/graphs_interim/%s/graph.json" % e["region"]
    pm = PacketModel(g, pk); H = pm.H; E = len(pm.g.u)
    def full(b): return bool(b) and b[0][0] == 0 and b[-1][1] >= H and len(b) == 1
    r = {"edges": E, "edges_touching_burning_cells": pm.edges_touching,
         "closed_blocked_whole_horizon": sum(full(b) for b in pm.B["closed"]),
         "router_blocked_whole_horizon": sum(full(b) for b in pm.B["router"]),
         "closed_blocked_at_t0": sum(bool(b) and b[0][0] == 0 for b in pm.B["closed"]),
         "burning_cells": len(pm.burning), "H": H}
    r["closed_blocked_whole_horizon_frac"] = round(r["closed_blocked_whole_horizon"] / E, 4)
    r["router_blocked_whole_horizon_frac"] = round(r["router_blocked_whole_horizon"] / E, 4)
    out["%s %s" % (e["region"], e["start"])] = r; print(e["region"], e["start"], r, flush=True)
    shutil.rmtree(pk, ignore_errors=True)
json.dump(out, open(S + "/f31/burnset_blocked_frac.json", "w"), indent=1)
