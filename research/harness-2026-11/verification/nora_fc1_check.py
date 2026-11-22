"""Nora's independent check of Leo F-C1 C2/C3/C4. Written without reusing seebefore code."""
import json, sys
import numpy as np
from pathlib import Path
from shapely.geometry import LineString, box, Point
from shapely.strtree import STRtree
R = Path('/home/user/wildfireguardian/data/routing')
I = R/'latest_inputs_try02'
for region in ('uiseong_andong_2025','yeongdeok_2025'):
    g = json.loads((R/'graphs'/region/'graph.json').read_text())
    nodes = {n['id']:(n['x'],n['y']) for n in g['nodes']}
    e0 = g['edges'][0]; ku = 'u' if 'u' in e0 else ('from' if 'from' in e0 else 'source'); kv = {'u':'v','from':'to','source':'target'}[ku]
    lines = [LineString([nodes[e[ku]], nodes[e[kv]]]) for e in g['edges'] if nodes[e[ku]]!=nodes[e[kv]]]
    tree = STRtree(lines)
    nxy = np.array(list(nodes.values()))
    gx = (nxy[:,0].min(), nxy[:,1].min(), nxy[:,0].max(), nxy[:,1].max())
    for t in sorted(p.name for p in (I/'packets'/region).iterdir()):
        z = np.load(I/'exports'/'KFS_01'/f'FORECAST_{t}.npz')
        a = z['affine_transform']; act = z['heat__initial_active_burning_probability']
        rr, cc = np.nonzero(act > 0)
        ex = a[2] + (cc+0.5)*a[0]; ey = a[5] + (rr+0.5)*a[4]
        hz = json.loads((I/'packets'/region/t/'HAZARD.json').read_text()); G = hz['grid']
        res=G['resolution']; W,H=G['width'],G['height']
        x1, y1 = G['x0']+W*res, G['y0']+H*res
        ins = (ex>G['x0'])&(ex<x1)&(ey>G['y0'])&(ey<y1)
        # alignment of packet grid with export grid
        al = ((G['x0']-a[2])/res % 1, (G['y0']-a[5])/res % 1)
        pres = {(round(x),round(y)) for x,y in zip(ex,ey)}
        def cells(mask, south):
            m = np.asarray(mask,bool).reshape(H,W); r,c = np.nonzero(m)
            y = G['y0']+(r+0.5)*res if south else y1-(r+0.5)*res
            return {(round(G['x0']+(ci+0.5)*res), round(yi)) for ci,yi in zip(c,y)}
        t0s = [cells(m['flame'][0],True) for m in hz['members']]
        t0n = [cells(m['flame'][0],False) for m in hz['members']]
        same = all(s==t0s[0] for s in t0s)
        newmax = []
        for m in hz['members']:
            seen=set(); per=[]
            for k in m['flame']:
                f = cells(k,True)-pres-seen; seen|=f; per.append(len(f))
            newmax.append(sum(per))
        # crop vs roads
        crop = [(x,y) for x,y,i in zip(ex,ey,ins) if not i]
        hit = sum(1 for x,y in crop if any(lines[j].intersects(box(x-187.5,y-187.5,x+187.5,y+187.5)) for j in tree.query(box(x-187.5,y-187.5,x+187.5,y+187.5))))
        d = np.array([min(lines[j].distance(Point(x,y)) for j in [tree.nearest(Point(x,y))]) for x,y in crop]) if crop else np.array([])
        nout = int(((nxy[:,0]<G['x0'])|(nxy[:,0]>x1)|(nxy[:,1]<G['y0'])|(nxy[:,1]>y1)).sum())
        print(f"{region}/{t}: horizon {hz['valid_until']-hz['valid_from']} | full {len(ex)} geom-inside {int(ins.sum())} "
              f"| t0 flame S-match {len(t0s[0]&pres)}/{len(t0s[0])} N-match {len(t0n[0]&pres)}/{len(t0n[0])} members-identical-t0 {same} "
              f"| new/member {newmax} | crop {len(crop)} road-hit {hit} d<=100 {int((d<=100).sum())} d<=500 {int((d<=500).sum())} d<=1km {int((d<=1000).sum())} min_d {d.min() if len(d) else None:.0f} "
              f"| nodes out {nout} | grid-align {al} | packet bbox {G['x0'],G['y0'],x1,y1} graph bbox {tuple(round(v) for v in gx)}")
