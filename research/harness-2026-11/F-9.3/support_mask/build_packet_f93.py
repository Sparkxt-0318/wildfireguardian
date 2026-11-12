"""CLI for the versioned writer wrapper (DESIGN.md). Same arguments as the frozen
integration/src/wfg_latest/build_packet.py, plus an optional support channel:

  build_packet_f93.py <build_packet.py arguments> [--support-rule c651_unknown/1 |
                      --support-rule supplied/1 --support-mask-npz M.npz --support-provenance JSON]

Without --support-rule this is exactly build_packet.main(argv) (complete hand-off). Run it in its own process
(python -I -B), as the frozen CLI requires.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WFG = REPO / 'integration' / 'src' / 'wfg_latest'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.path.insert(0, str(WFG))
    import build_packet as BP                     # the frozen CLI, imported (defines functions only)
    if '--support-rule' not in argv:
        return BP.main(argv)                      # complete hand-off
    ap = argparse.ArgumentParser()
    for k in ('--graph', '--export-dir', '--event', '--cutoff', '--region', '--out', '--support-rule'):
        ap.add_argument(k, required=True)
    ap.add_argument('--window-json', default=None)
    ap.add_argument('--support-mask-npz', default=None)
    ap.add_argument('--support-provenance', default=None)
    a = ap.parse_args(argv)
    BP.install_radiation()
    sys.path.insert(0, str(HERE))
    import contract as CT
    import numpy as np
    import packets_f93 as PF
    iso, _ = CT.normalize_cutoff(a.cutoff)
    exp = Path(a.export_dir); tag = CT.tag(iso)
    npz = exp / ('FORECAST_%s.npz' % tag); recp = exp / ('FORECAST_RECORD_%s.json' % tag)
    rec = json.loads(recp.read_text())
    graph = json.loads(Path(a.graph).read_text())
    crs = graph.get('crs', '')
    if not crs.startswith('EPSG:'):
        raise SystemExit('GRAPH_CRS_NOT_EPSG %r' % crs)
    epsg = int(crs.split(':', 1)[1])
    win = json.loads(a.window_json) if a.window_json else None
    if a.support_rule == 'c651_unknown/1':
        mask, prov = 'c651_unknown/1', None
    else:
        with np.load(a.support_mask_npz, allow_pickle=False) as z:
            mask = z['support']
        prov = json.loads(a.support_provenance) if a.support_provenance else None
    t0 = time.perf_counter()
    out, hz, summ = PF.write_regional_packet(graph, a.graph, npz, rec, sha(recp), iso, epsg, a.out,
                                             event_id=a.event, region_id=a.region, window=win,
                                             support_mask=mask, support_rule=a.support_rule, support_provenance=prov)
    wall = time.perf_counter() - t0
    mods = sorted(n for n, m in sys.modules.items() if n.startswith(('wildfire', 'routing')) and getattr(m, '__file__', None))
    summ.update(region=a.region, event_id=a.event, cutoff=iso, graph_file=str(a.graph), graph_sha256=sha(a.graph),
                forecast_npz_sha256=sha(npz), forecast_record_sha256=sha(recp), hazard_construction_wall_s=wall,
                source_sha256={**{n: sha(WFG / n) for n in ('contract.py', 'bridge.py', 'packets.py', 'build_packet.py')},
                               **{'F-9.3/support_mask/' + n: sha(HERE / n) for n in ('packets_f93.py', 'build_packet_f93.py')}},
                vendored_sha256={**{'radiation/' + n: h for n, h in BP.RADIATION_SHA256.items()},
                                 **{'router_validation/' + n: h for n, h in BP.ROUTER_VALIDATION_SHA256.items()}},
                radiation_modules_loaded=mods, window=win, status='BUILT')
    with (Path(out) / 'BUILD_SUMMARY.json').open('x') as f:
        json.dump(summ, f, indent=1, default=str); f.write('\n')
    print(json.dumps({k: summ.get(k) for k in ('region', 'cutoff', 'shape', 'present_fire_cells', 'support_writer')},
                     default=str))


if __name__ == '__main__':
    main()
