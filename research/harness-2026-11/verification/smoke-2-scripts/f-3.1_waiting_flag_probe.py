"""Owen: does waitable_all reach the field? Count waitable nodes in each arm's instance, and compare the WHOLE feasible
departure sets (not only the recorded departure) for every (spec, origin) of one cache."""
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, ".")
from deadline_field.core import backward, issue_set
from deadline_field.real import PacketModel
cache = Path(sys.argv[1]); root = Path(sys.argv[2])
doc = json.loads(cache.read_text()); region = doc["region_id"]; compact = doc["input_time"].replace("-", "").replace(":", "")
gp = root / "graphs" / region / "graph.json"; pd = root / "latest_inputs_try02" / "packets" / region / compact
specs = defaultdict(set)
for k, j in doc["route_checks"].items():
    q = j["request"]; specs[(q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))].add(q["start"]["node_id"])
A = {"supplied": PacketModel(gp, pd), "wait_all": PacketModel(gp, pd, waitable_all=True)}
for arm, pm in A.items():
    inst = pm.instance("cert", [{"node": s[0], "dwell": s[1], "window": list(s[2])} for s in list(specs)[:1]], sorted(list(specs.values())[0]))
    print(arm, "instance waitable nodes", sum(inst.waitable), "of", inst.n_nodes)
diff = same = 0; grown = 0; ex = []
for var in ("cert", "router"):
    for spec in sorted(specs, key=str):
        f = {arm: backward(pm.instance(var, [{"node": spec[0], "dwell": spec[1], "window": list(spec[2])}], sorted(specs[spec]))) for arm, pm in A.items()}
        for o in specs[spec]:
            a, b = issue_set(f["supplied"], A["supplied"].nidx[o]), issue_set(f["wait_all"], A["wait_all"].nidx[o])
            if a != b:
                diff += 1; la = sum(h - l for l, h in a); lb = sum(h - l for l, h in b); grown += lb > la
                if len(ex) < 3: ex.append((var, o, a[:3], b[:3]))
            else:
                same += 1
print("(spec,origin,field) whole-set identical", same, "different", diff, "of which larger with waiting", grown); print(ex)
