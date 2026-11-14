import json, sys, numpy as np
from pathlib import Path
W = Path(sys.argv[1]); D = W / 'research/harness-2026-11/F-DYN/_data'
sys.path[:0] = [str(W), str(W / 'experimental/scenario-members/src'), str(W / 'research/harness-2026-11/F-DYN'), str(W / 'integration/kit/runner'), str(W / 'integration/kit/routing_candidate/baseline')]
from fdyn.consistency import check as self_check
from tools.explain_deadlines.packet import Packet as Replay
from tools.explain_deadlines.geometry import Grid
from wfg_scenario_members.contact import ContactModel
import ffi_independent_checker as K
from road_exposure import RoadExposure
def probe(f):
    try: f(); return 'OK'
    except Exception as e: return type(e).__name__ + ' ' + str(e)[:60]
for d in sorted((D / 'packets_v37_noreentry2').glob('*/*_central_q300')):
    reg = d.parent.name; hz = json.loads((d / 'HAZARD.json').read_text()); g = hz['grid']
    grid = Grid(g['x0'], g['y0'], g['resolution'], g['width'], g['height'])
    gj = json.loads((D / f'graphs_interim/{reg}/graph.json').read_text())
    z = np.load(d / 'constructed_arrays.npz'); rep = json.loads((d / 'REPORT.json').read_text())
    asm = rep['native_metadata']['construction']['assumptions']; aff = rep['native_metadata']['affine_transform']
    bs = json.loads((d / 'BUILD_SUMMARY.json').read_text()).get('writer_identity', {})
    s = json.dumps(hz['provenance']) + json.dumps(rep)
    res = dict(self=self_check(d).get('consistent'), replay=probe(lambda: Replay(d, grid).verify_consistency()),
               contact=probe(lambda: ContactModel.from_packet(d)), kit=probe(lambda: K.Packet(d, K.Graph(gj))),
               roadexp=probe(lambda: RoadExposure(np.array(z['ignition_time_s']), np.array(z['current_active']), dict(asm), tuple(aff))),
               T_R=(asm['burning_duration_s'], asm['initial_remaining_s']), law=asm.get('version'),
               bs_transform=bs.get('transform'), bs_law=bs.get('source_law_version'),
               nr2_in_identity=('no_reentry/2' in s and 'wfg.fdyn.no-reentry-scalar/2' in s), member_id=hz['members'][0]['id'][-24:])
    print(reg[:2], d.name.split('_central')[0], res, flush=True)
