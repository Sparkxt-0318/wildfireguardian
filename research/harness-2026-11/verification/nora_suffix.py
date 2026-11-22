# Are all NR O2 blocks suffix sets of the usable start range? (then waiting can never help: FIFO + monotone blocks)
import json, sys, glob
sys.path.insert(0, 'research/harness-2026-11/F-3.2'); sys.path.insert(0, sys.argv[3])
import generate, fbase
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import build_instance
P, REQ, _, GRAPH, IDRO = sys.argv[1:6]
graph = json.load(open(GRAPH)); m = ContactModel.from_packet(P); idnr = json.load(open(P + '/HAZARD.json'))['members'][0]['id']
for f in sorted(glob.glob(REQ + '/*__d0.json'))[:2] + sorted(glob.glob(REQ + '/*__d7200.json'))[:2]:
    q = json.loads(open(f).read().replace(IDRO, idnr)); inst, _ = build_instance(graph, q, m); _, _, b, _, _ = generate.certify(inst); I = fbase.parse_instance(b)
    bad_e = sum(1 for j, v in I.EB.items() if v and (len(v) > 1 or v[-1][1] < I.H - I.D[j]))
    bad_w = sum(1 for n, v in I.WB.items() if v and (len(v) > 1 or v[-1][1] < I.H - 1))
    print(f.split('/')[-1], 'EB edges', len([v for v in I.EB.values() if v]), 'non-suffix', bad_e, '| WB nodes', len([v for v in I.WB.values() if v]), 'non-suffix', bad_w, flush=True)
