"""Static-obstacle finding (F-4.2), closed-footprint version, for verification. Stdlib + NumPy; about 1 minute.

For each frozen packet: drawn new ignitions per member (from constructed_arrays.npz). For each of the 15 published
routes (routes/*.json): how many drawn-ignition cells (any member) the route's closed footprint touches at any time,
how many of those it touches before the cell ignites, and the closed-form contact time margin min(b - t_exit).
Geometry is the whole-road contact checker's: straight node-to-node segments, linear timing, closed 375 m cells,
waits and the destination dwell as stationary segments.

  python static_obstacle.py
"""
import json, math, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import clearance as C  # noqa: E402


def main():
    pk = REPO / 'data/routing/latest_inputs_try02/packets'
    print('PACKETS: drawn new ignitions per member')
    zero = []
    for d in sorted(pk.glob('*/*')):
        with np.load(d / 'constructed_arrays.npz') as z:
            ev = z['ignition_time_s']
        n = [int(np.isfinite(ev[s]).sum()) for s in range(ev.shape[0])]
        if not any(n):
            zero.append('%s/%s' % (d.parent.name, d.name))
        print('  %-38s %s' % ('%s/%s' % (d.parent.name, d.name), n))
    print('packets with zero drawn ignitions in every member: %d of %d' % (len(zero), len(list(pk.glob('*/*')))))
    print('ROUTES (closed footprint)')
    never = 0; rows = []
    for f in sorted((HERE / 'routes').glob('*.json')):
        r = json.loads(f.read_text()); region, case = r['mission'].split('__')
        I = C.Instance(*C.load(region, case))
        tm, touched_before = C.contact_time_margin(I, r)
        # touched at any time: footprint meets any FUTURE source rectangle at r = 0, regardless of timing
        anyt = 0
        fut = [j for j, s in enumerate(I.src) if s['kind'] == 'FUTURE']
        if fut:
            for L in r['legs'] + [{'kind': 'DWELL'}]:
                if L['kind'] == 'EDGE':
                    e = I.edges[I.eidx[L['edge']]]; p0 = (I.nodes[e['u']]['x'], I.nodes[e['u']]['y']); p1 = (I.nodes[e['v']]['x'], I.nodes[e['v']]['y'])
                else:
                    n = I.nodes[L.get('node', r['destination'])]; p0 = p1 = (n['x'], n['y'])
                P0 = np.repeat([p0], len(fut), axis=0).astype(float); P1 = np.repeat([p1], len(fut), axis=0).astype(float)
                _, dm = C.seg_rect(P0, P1, I.SR[fut]); anyt += int((dm <= C.PAD_M).sum())
        if anyt == 0:
            never += 1
        print('  %-46s ignitions/member=%-14s footprint_touches_ignited_cells=%3d before_ignition=%3d contact_time_margin_s=%s'
              % (r['mission'], I.hz['ignitions_per_member'], anyt, touched_before, tm))
    print('routes whose closed footprint never touches any cell that ignites in any member: %d of 15' % never)


if __name__ == '__main__':
    main()
