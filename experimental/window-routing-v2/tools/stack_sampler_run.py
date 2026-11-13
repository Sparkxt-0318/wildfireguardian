import json, sys
from pathlib import Path
sys.path.insert(0, '/home/user/wildfireguardian/research/harness-2026-11/F-3.4')
import run_profile as RP
RP.HERE = Path(__file__).resolve().parent          # use the diagnostic phase_worker.py here
kit, graph, packet, req, out, budget, guard = sys.argv[1:8]
r = RP.run_one(Path(kit), Path('/home/user/wildfireguardian/data/routing'), 'fdyn', Path(req).stem, Path(out), float(budget), 'phase',
               sys.executable, paths=(graph, packet, req), memory_guard_mib=int(guard))
print(json.dumps({k: r[k] for k in ('authoritative_status', 'complete_wall_s', 'rda_stages')}, default=str))
