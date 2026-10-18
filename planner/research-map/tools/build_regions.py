#!/usr/bin/env python3
"""Build one data bundle per study region for the 3D layer map (regions/<id>.js) plus regions/index.js.

Everything comes from files already in the repository (forecast fixtures, recorded route-check records,
hazard packets, places, footprints, offline basemap, booth cache) plus public Terrarium elevation tiles.
Nothing is modelled or invented here; this only re-packages recorded outputs for drawing.

Inputs: planner/ fixtures, records, places, footprints, basemaps and booth cache (all in git); the routing hazard
packets from the planner's verified release extracts (planner/scripts/fetch_planner_assets.sh); Terrarium DEM tiles
(downloaded once into ../.cache/dem). Output: ../site/regions/<id>.js and ../site/regions/index.js.

usage: python tools/build_regions.py [--only id,id] [--packets DIR]
"""
from __future__ import annotations

import argparse, base64, glob, json, math, os, subprocess, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.prepared import prep

HERE = Path(__file__).resolve().parent          # planner/research-map/tools
ROOT = HERE.parent                              # planner/research-map
REPO = ROOT.parent.parent
CACHE = ROOT / '.cache'
TERRARIUM = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

REGIONS = {
    'uljin_2022': dict(loc_ko='경북 울진군 일대', loc_en='Uljin County, Gyeongbuk'),
    'miryang_2022': dict(loc_ko='경남 밀양시 부북면 일대', loc_en='Bubuk-myeon, Miryang, Gyeongnam'),
    'hongseong_2023': dict(loc_ko='충남 홍성군 서부면 일대', loc_en='Seobu-myeon, Hongseong, Chungnam'),
    'uiseong_andong_2025': dict(loc_ko='경북 의성군 · 안동시 일대', loc_en='Uiseong County · Andong, Gyeongbuk'),
    'yeongdeok_2025': dict(loc_ko='경북 영덕군 일대', loc_en='Yeongdeok County, Gyeongbuk'),
}


def lx(lon, z): return (lon + 180) / 360 * 2 ** z * 256
def ly(lat, z): return (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / np.pi) / 2 * 2 ** z * 256


def tiles_for(z, bbox):
    W, S, E, N = bbox
    return [(z, x, y) for x in range(int(lx(W, z) // 256), int(lx(E, z) // 256) + 1)
            for y in range(int(ly(N, z) // 256), int(ly(S, z) // 256) + 1)]


def tile_path(z, x, y):
    return CACHE / 'dem' / f'{z}_{x}_{y}.png'


def fetch_tiles(tiles):
    need = [t for t in tiles if not tile_path(*t).exists()]
    def get(t):
        z, x, y = t
        p = tile_path(z, x, y)
        subprocess.run(['curl', '-sSf', '--retry', '4', '-o', str(p), TERRARIUM.format(z=z, x=x, y=y)], check=True)
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(get, need))
    return len(need)


def sample_dem(z, bbox, GXn, GYn):
    W_, S_, E_, N_ = bbox
    X0 = int(lx(W_, z) // 256); X1 = int(lx(E_, z) // 256); Y0 = int(ly(N_, z) // 256); Y1 = int(ly(S_, z) // 256)
    mos = np.zeros(((Y1 - Y0 + 1) * 256, (X1 - X0 + 1) * 256))
    for x in range(X0, X1 + 1):
        for y in range(Y0, Y1 + 1):
            a_ = np.asarray(Image.open(tile_path(z, x, y)).convert('RGB')).astype(float)
            mos[(y - Y0) * 256:(y - Y0 + 1) * 256, (x - X0) * 256:(x - X0 + 1) * 256] = a_[..., 0] * 256 + a_[..., 1] + a_[..., 2] / 256 - 32768
    lons = W_ + np.arange(GXn) / (GXn - 1) * (E_ - W_); lats = N_ - np.arange(GYn) / (GYn - 1) * (N_ - S_)
    px = lx(lons, z) - X0 * 256 - 0.5; py = ly(lats, z) - Y0 * 256 - 0.5
    PX, PY = np.meshgrid(px, py); x0 = np.clip(np.floor(PX).astype(int), 0, mos.shape[1] - 2); y0 = np.clip(np.floor(PY).astype(int), 0, mos.shape[0] - 2)
    fx = PX - x0; fy = PY - y0
    v = mos[y0, x0] * (1 - fx) * (1 - fy) + mos[y0, x0 + 1] * fx * (1 - fy) + mos[y0 + 1, x0] * (1 - fx) * fy + mos[y0 + 1, x0 + 1] * fx * fy
    return np.clip(v, 0, None)   # sea floor clipped to 0 m; the viewer draws 0 m as sea where OSM has no polygon


def enc16(a, scale=10):
    return base64.b64encode(np.round(np.clip(a * scale, 0, 65535)).astype('<u2').tobytes()).decode()


def simplify_pts(g, ts, tol):
    if len(g) <= 2:
        return [[round(x, 5), round(y, 5), ts[min(i, len(ts) - 1)] if ts else 0] for i, (x, y) in enumerate(g)]
    out, j = [], 0
    for (x, y) in LineString(g).simplify(tol).coords:
        while j < len(g) and (abs(g[j][0] - x) > 1e-9 or abs(g[j][1] - y) > 1e-9):
            j += 1
        out.append([round(x, 5), round(y, 5), ts[min(j, len(ts) - 1)] if ts else 0])
    return out


def build(rid, repo: Path, packets: Path, meta_idx: dict):
    R = repo / 'planner'
    rinfo = meta_idx[rid]
    W, S, E, N = rinfo['bbox']
    span = max(E - W, (N - S) * 1.25)
    small = span < 0.12
    kmx = (E - W) * 111.32 * math.cos(math.radians((S + N) / 2)); kmy = (N - S) * 110.57
    # ---- DEM ----
    zr, zc = (14, 12) if small else (13, 11)
    GX = 560; GY = round(GX * kmy / kmx)
    mlon, mlat = span, span * 0.8
    CB = (W - mlon, S - mlat, E + mlon, N + mlat)
    n_new = fetch_tiles(tiles_for(zr, (W, S, E, N)) + tiles_for(zc, CB))
    dem = sample_dem(zr, (W, S, E, N), GX, GY)
    ckx = (CB[2] - CB[0]) * 111.32 * math.cos(math.radians((CB[1] + CB[3]) / 2)); cky = (CB[3] - CB[1]) * 110.57
    CGX = 600; CGY = round(CGX * cky / ckx)
    cdem = sample_dem(zc, CB, CGX, CGY)
    log = [f'{rid}: DEM z{zr} {GX}x{GY} {dem.min():.0f}-{dem.max():.0f} m, context z{zc} {CGX}x{CGY} (+{n_new} tiles fetched), {kmx:.1f}x{kmy:.1f} km']
    # ---- cells ----
    fdir = R / 'mock_api/fixtures/forecast' / rid
    times = sorted(p.stem for p in fdir.glob('*.json'))
    fxs = [json.loads((fdir / f'{t}.json').read_text()) for t in times]
    ps = [f['properties'] for f in fxs[0]['features']]
    NR = max(p['row'] for p in ps) + 1; NC = max(p['col'] for p in ps) + 1
    lat_lon = np.zeros((NR + 1, NC + 1, 2))
    for f in fxs[0]['features']:
        r, c = f['properties']['row'], f['properties']['col']; q = f['geometry']['coordinates'][0]
        lat_lon[r, c] = q[0]; lat_lon[r, c + 1] = q[1]; lat_lon[r + 1, c + 1] = q[2]; lat_lon[r + 1, c] = q[3]
    K = len(times)
    valid = np.zeros((NR, NC), bool); qs = np.zeros((K, NR, NC)); burning = np.zeros((K, NR, NC), bool); known = np.zeros((K, NR, NC), bool)
    for k, fx in enumerate(fxs):
        for f in fx['features']:
            p = f['properties']; r, c = p['row'], p['col']
            valid[r, c] |= p['valid']; qs[k, r, c] = p['p_new_burn_1h'] or 0; burning[k, r, c] = p['burning_now']; known[k, r, c] = p['known_burned']
    fp = json.loads((R / 'public/data/regions' / rid / 'footprints.geojson').read_text())
    fps = sorted([(f['properties']['input_time'], f['properties']['area_km2'], prep(shape(f['geometry']))) for f in fp['features']], key=lambda x: x[0])
    first = np.full((NR, NC), 255, np.uint8)
    centers = (lat_lon[:-1, :-1] + lat_lon[1:, 1:] + lat_lon[:-1, 1:] + lat_lon[1:, :-1]) / 4
    for r in range(NR):
        for c in range(NC):
            pt = Point(*centers[r, c])
            for k, (_, _, g) in enumerate(fps):
                if g.contains(pt):
                    first[r, c] = k; break
    cellpack = dict(nr=NR, nc=NC, lattice=np.round(lat_lon, 6).reshape(-1).tolist(), valid=valid.astype(int).reshape(-1).tolist(),
                    first=first.reshape(-1).tolist(), q=[[round(float(v), 4) for v in qs[k].reshape(-1)] for k in range(K)],
                    burning=[np.flatnonzero(burning[k].reshape(-1)).tolist() for k in range(K)],
                    known=[np.flatnonzero(known[k].reshape(-1)).tolist() for k in range(K)])
    footprints = [dict(time=t, area_km2=a) for t, a, _ in fps]
    # ---- places ----
    pl = json.loads((R / 'public/data/regions' / rid / 'places.geojson').read_text())['features']
    places, bynode, byid = [], {}, {}
    for f in pl:
        p = f['properties']
        d = dict(id=p['id'], role=p['role'], cat=p['category'], name=p['name'], ne=p.get('name_en'), lon=round(f['geometry']['coordinates'][0], 5),
                 lat=round(f['geometry']['coordinates'][1], 5), vul=bool(p.get('vulnerable')), src=p.get('source_tag'), chk=p.get('checkable', True))
        byid[p['id']] = d
        if p['role'] in ('origin', 'destination'):
            places.append({k: v for k, v in d.items() if k != 'id' or True})
        for nd in [(p.get('entry') or {}).get('node'), (p.get('snap') or {}).get('node')]:
            if nd:
                bynode.setdefault(nd, d)
    # ---- recorded research cases: every policy (constraint ablation) ----
    tol = 0.00002 * (span / 0.31) ** 0.5
    rdir = R / 'mock_api/fixtures/records' / rid
    routes, policies = [], {}
    for f in sorted(rdir.glob('*.json')):
        r = json.loads(f.read_text()); o = r['outcome']; rq = r['request']; pol = r['policy']
        g = r['route']['geometry']['coordinates'] if r.get('route') else []
        ts = r['route']['properties']['times_s'] if r.get('route') else []
        pts = simplify_pts(g, ts, tol) if g else []
        ex = [dict(peak=e['peak_kw_m2'], dose=e['dose_kj_m2'], contact=e['contact']) for e in r['exposure']]
        policies.setdefault(r['case_id'], {})[pol] = dict(
            verdict=o['verdict'], reason=o['reason_code'], raw=o['raw_reason'], decision=o.get('authoritative_decision'),
            dep=o['departure_s'], arr=o['arrival_s'], L=o.get('lower_bound_L_s'), dwell_end=o.get('dwell_end_s'), compute_s=o.get('compute_s'),
            within_budget=o.get('within_budget'), length_m=r['route']['properties']['length_m'] if r.get('route') else None, pts=pts,
            limits=rq['limits'], dwell_s=rq['dwell_s'], window=rq['destination_window'], incurred=rq['incurred_dose_kj_m2'], exposure=ex,
            full_check=(dict(passed=r['full_policy_check'].get('pass'), components=r['full_policy_check'].get('failure_components')) if r.get('full_policy_check') else None))
        if pol == 'full':
            on, dn = bynode.get(rq['origin_node']), bynode.get(rq['destination_node'])
            routes.append(dict(case=r['case_id'], input_time=r['input_time'], verdict=o['verdict'], reason=o['reason_code'], raw=o['raw_reason'],
                               dep=o['departure_s'], arr=o['arrival_s'], length_m=r['route']['properties']['length_m'] if r.get('route') else None,
                               origin=(on or {}).get('name') or (on or {}).get('cat'), dest=(dn or {}).get('name') or (dn or {}).get('cat'),
                               origin_en=(on or {}).get('ne'), dest_en=(dn or {}).get('ne'), pts=pts, exposure=ex,
                               o=[on['lon'], on['lat']] if on else None, d=[dn['lon'], dn['lat']] if dn else None))
    routes.sort(key=lambda x: (x['input_time'], x['case']))
    # ---- routing hazard packets ----
    hazard = []
    for t in times:
        hz = json.loads((packets / rid / t / 'HAZARD.json').read_text()); meta = json.loads((packets / rid / t / 'NATIVE_METADATA.json').read_text())
        assert hz['grid']['width'] == NC and hz['grid']['height'] == NR, (rid, t)
        mem = []
        for m in hz['members']:
            Fx = np.array(m['flux'], float)
            enc = np.where(Fx > 1e-8, np.clip(np.round((np.log10(np.maximum(Fx, 1e-8)) + 8) / 11 * 65535), 1, 65535), 0).astype('<u2')
            mem.append(dict(id=m['id'], bp=[round(b, 3) for b in m['breakpoints']], flux=base64.b64encode(enc.tobytes()).decode(),
                            flame=[np.flatnonzero(np.array(x)).tolist() for x in m['flame']], support=int(np.array(m['support']).sum())))
        a = meta['construction']['assumptions']
        hazard.append(dict(input_time=hz['time_origin'], valid_until=hz['valid_until'], units=hz['units'], members=mem,
                           unsupported=hz['unsupported_channels'], evidence=hz['evidence_class'],
                           assumptions={k: a[k] for k in ('scenario_count', 'seed', 'horizon_s', 'dependence', 'timing', 'fuel_load_kg_m2', 'heat_of_combustion_j_kg',
                                                          'burning_duration_s', 'consumed_fraction', 'radiative_fraction', 'emission_height_m', 'receiver_height_m', 'initial_remaining_s')}))
    # ---- OSM (offline basemap of the planner) ----
    op = CACHE / 'osm' / f'osm_{rid}.json'
    if not op.exists():
        op.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['node', str(HERE / 'osm_region.mjs'), str(R / 'public/basemap' / f'{rid}.pmtiles'), *map(str, (W, S, E, N)), str(14 if small else 13), str(op)], check=True)
    osm = json.loads(op.read_text())
    def simp(t, c, tl):
        if t == 'LineString': return [LineString(c).simplify(tl).coords[:]] if len(c) > 1 else []
        if t == 'MultiLineString': return [LineString(x).simplify(tl).coords[:] for x in c if len(x) > 1]
        if t == 'Polygon': return [Polygon(c[0]).simplify(tl).exterior.coords[:]] if len(c[0]) > 3 else []
        if t == 'MultiPolygon': return [Polygon(p[0]).simplify(tl).exterior.coords[:] for p in c if len(p[0]) > 3]
        return []
    flat = lambda rings: [[v for xy in ring for v in (round(xy[0], 5), round(xy[1], 5))] for ring in rings if len(ring) > 1]
    o2 = {'roads': [], 'water': [], 'landuse': []}
    sc = (span / 0.31)
    for ln_, tl in [('roads', 0.00005 * sc), ('water', 0.00005 * sc), ('landuse', 0.00008 * sc)]:
        for f in osm.get(ln_, []):
            if ln_ == 'roads' and f['k'] in ('path',) and f['d'] not in ('track',): continue
            if f['t'] == 'Point': continue
            k = f['k']
            if ln_ == 'water':
                k = 'water' if f['t'] in ('Polygon', 'MultiPolygon') else (k if k != 'water' else 'stream')
            g = flat(simp(f['t'], f['c'], tl))
            if g: o2[ln_].append([k, f['d'], g])
    inb = lambda lon, lat: W <= lon <= E and S <= lat <= N
    peaks = [dict(n=p['n'], ne=p.get('ne'), e=p.get('e'), lon=p['c'][0], lat=p['c'][1]) for p in osm.get('pois', []) if p.get('n') and p['t'] == 'Point' and inb(*p['c'])]
    seen, labels = set(), []
    for p in osm.get('places', []):
        if not p.get('n') or p['n'] in seen or p['t'] != 'Point' or not inb(*p['c']): continue
        seen.add(p['n']); labels.append(dict(n=p['n'], ne=p.get('ne'), k=p['d'] or p['k'], lon=p['c'][0], lat=p['c'][1]))
    # ---- booth cache (dispatch plans from the real Route-Check API), when this region has one ----
    booth = booth_summary(rid, R, byid, tol)
    # ---- RQ3: travel-time-only routes that the full hazard says touch flame, per recorded case ----
    rq3 = []
    for case, pols in sorted(policies.items()):
        t = pols.get('travel_only'); f_ = pols.get('full')
        if not t: continue
        fc = t.get('full_check') or {}
        rq3.append(dict(case=case, travel_fails_full=fc.get('passed') is False, components=fc.get('components'), travel_verdict=t['verdict'],
                        full_verdict=f_['verdict'] if f_ else None, flame_only_verdict=(pols.get('flame_only') or {}).get('verdict')))
    prov = fxs[0]['provenance']
    bundle = dict(id=rid, name=rinfo['name'], year=rinfo['fire_year'], event=rinfo['event_id'], loc_ko=REGIONS[rid]['loc_ko'], loc_en=REGIONS[rid]['loc_en'],
                  bbox=[W, S, E, N], km=[kmx, kmy], dem=dict(w=GX, h=GY, b64=enc16(dem), scale=0.1),
                  context=dict(bbox=list(CB), km=[ckx, cky], w=CGX, h=CGY, scale=0.1, b64=enc16(cdem)),
                  hazard=hazard, policies=policies, cells=cellpack, input_times=[fx['input_time'] for fx in fxs], footprints=footprints,
                  places=places, routes=routes, osm=o2, peaks=peaks, labels=labels, booth=booth, rq3=rq3,
                  provenance=dict(model=prov['checkpoint'][:8], package=prov['package'] + ' ' + prov['package_version'], scenarios=len(prov['scenario_ids']), graph=prov['graph_id']))
    hp = CACHE / f'hourly_{rid}.json'
    if hp.exists():
        hr = json.loads(hp.read_text())
        if hr.get('synthetic'):
            sys.exit(f'{hp} is a synthetic rehearsal export; it is never shipped. Delete it or merge a real export.')
        bundle['hourly'] = hr   # main() moves it to <id>.hourly.js and leaves hourly_meta, so the first view does not wait for it
        log.append(f'  hourly F(h) attached from {hp.name} ({len(hr["meta"]["cutoffs"])} cutoffs, {hr["meta"]["n_samples"]} samples)')
    log.append(f'  cells {NR}x{NC}, inputs {len(times)}, cases {sorted(policies)}, places {Counter(p["role"] for p in places)}, booth {"yes" if booth else "no"}, '
               f'osm {({k: len(v) for k, v in o2.items()})}, labels {len(labels)} peaks {len(peaks)}')
    return bundle, log


def booth_summary(rid, R: Path, byid, tol):
    """Per input time: each origin's best verdict, departure deadline and routes (checked + travel-time-only comparison)."""
    files = sorted((R / 'cache' / rid).glob('*.json')) if (R / 'cache' / rid).exists() else []
    if not files:
        return None
    idx = {e['path']: e for e in json.loads((R / 'cache/INDEX.json').read_text())}
    out = []
    for fn in files:
        d = json.loads(fn.read_text())
        rc = d['route_checks']
        def route_of(job_id):
            j = rc.get(job_id) if job_id else None
            res = (j or {}).get('result') or {}
            r = res.get('route')
            if not r: return None
            return simplify_pts(r['geometry']['coordinates'], r['properties'].get('times_s') or [], tol)
        origins = []
        plan_ids = set()
        for p in d['plans']:
            for o in (p.get('result') or {}).get('plans', []):
                plan_ids.add(o['origin_id'])
                b = o.get('best') or {}
                origins.append(dict(id=o['origin_id'], v=o['best_verdict'], last=o.get('latest_checked_depart_offset_s'), contig=o.get('latest_contiguous_checked_depart_offset_s'),
                                    dest=b.get('destination_id'), dep=b.get('depart_offset_s'), arr=b.get('arrival_s'), pts=route_of(b.get('route_check_job_id'))))
        # recorded research origins: the same contract rule over their checks (window skips are not checks)
        by = {}
        for x in d['research_checks']:
            if 'job_id' not in x: continue
            res = (rc.get(x['job_id']) or {}).get('result') or {}
            by.setdefault(x['origin_id'], []).append((x['depart_offset_s'], x['destination_id'], res.get('verdict', 'unresolved'), res.get('arrival_s'), x['job_id']))
        for oid, lst in by.items():
            vs = [v for _, _, v, _, _ in lst]
            v = 'checked_route' if 'checked_route' in vs else 'model_no_route' if all(x == 'model_no_route' for x in vs) else 'unresolved'
            ok = sorted([x for x in lst if x[2] == 'checked_route'], key=lambda x: x[0])
            contig = None
            for off, _, vv, _, _ in sorted(lst):
                if vv != 'checked_route': break
                contig = off
            b = ok[-1] if ok else None
            origins.append(dict(id=oid, v=v, last=b[0] if b else None, contig=contig, dest=b[1] if b else None, dep=b[0] if b else None, arr=b[3] if b else None,
                                pts=route_of(b[4]) if b else None, research=True))
        travel = {}
        for oid, j in d['travel_only'].items():
            res = j.get('result') or {}
            fa = res.get('full_policy_assessment') or {}
            r = res.get('route')
            travel[oid] = dict(dep=res.get('departure_s'), arr=res.get('arrival_s'), contact=fa.get('whole_road_contact'), passes=fa.get('passes_full_centre_and_contact'),
                               pts=simplify_pts(r['geometry']['coordinates'], r['properties'].get('times_s') or [], tol) if r else None)
        rows = []
        for o in origins:
            pl = byid.get(o['id']) or {}
            t = travel.get(o['id'])
            if t and (o.get('dep') is None or t['dep'] != o['dep']):
                t = None      # a comparison belongs to the best checked departure; none without one (planner rule)
            dn = byid.get(o['dest']) or {}
            rows.append(dict(o, name=pl.get('name') or (o['id'].split(':')[-2] if o.get('research') else o['id']), ne=pl.get('ne'), cat=pl.get('cat', 'research' if o.get('research') else None),
                             vul=pl.get('vul', False), lon=pl.get('lon'), lat=pl.get('lat'), dname=dn.get('name'), dne=dn.get('ne'), travel=t))
        # origins with no accepted road entry within reach are never sent (점검 불가)
        for pid, pl in byid.items():
            if pl['role'] == 'origin' and pid not in plan_ids:
                rows.append(dict(id=pid, v='not_checkable', name=pl['name'], ne=pl.get('ne'), cat=pl['cat'], vul=pl['vul'], lon=pl['lon'], lat=pl['lat'], chk=pl['chk']))
        e = idx.get(f'{rid}/{fn.name}', {})
        out.append(dict(input_time=d['input_time'], scenario_set_id=d['scenario_set_id'], api=dict(version=e.get('api_version'), mode=e.get('api_mode'),
                        host=(e.get('host') or {}).get('platform'), created_at=e.get('created_at'), checks=e.get('checks'), sha256=e.get('sha256')),
                        step_min=d['generator'].get('step_min'), shelters=d['generator'].get('shelters_per_origin'), rows=rows))
    return out


def write_parts(b, rid, outd):
    """<id>.js holds what the first frame draws. The surrounding-terrain heights (<id>.ctx.js, the outer ring, added a moment
    later) and the OSM vectors (<id>.osm.js, only for drawing the terrain in the page or the 2D maps) are separate files."""
    js = lambda name, obj: f'(window.{name}=window.{name}||{{}})[{json.dumps(rid)}]=' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n'
    b = dict(b); ctx = dict(b['context']); osm = b.pop('osm')
    b['context'] = {k: v for k, v in ctx.items() if k != 'b64'}
    b['parts'] = dict(ctx_b64=len(ctx['b64']), osm_roads=len(osm['roads']), osm_landuse=len(osm['landuse']))   # texture key, see core.js
    for name, text in [(f'{rid}.js', js('WFG_REGIONS', b)), (f'{rid}.ctx.js', js('WFG_CTX', ctx['b64'])), (f'{rid}.osm.js', js('WFG_OSM', osm))]:
        (outd / name).write_text(text); print(f'  wrote {name} {len(text.encode()) / 1e6:.2f} MB')


def main(argv=None):
    ap = argparse.ArgumentParser()
    assets = Path(os.environ.get('WFG_ASSETS_DIR') or REPO / 'planner/.assets')
    ap.add_argument('--repo', default=str(REPO))
    ap.add_argument('--packets', default=str(assets / 'extracted/WFG-evaluated-routing-inputs-20261015/latest_inputs_try02/packets'))
    ap.add_argument('--out', default=str(ROOT / 'site/regions'))
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    repo, packets, outd = Path(a.repo), Path(a.packets), Path(a.out)
    if not packets.is_dir():
        sys.exit(f'hazard packets not found at {packets}; run planner/scripts/fetch_planner_assets.sh first')
    outd.mkdir(parents=True, exist_ok=True); (CACHE / 'dem').mkdir(parents=True, exist_ok=True)
    idx = {r['region_id']: r for r in json.loads((repo / 'planner/public/data/regions/index.json').read_text())}
    ids = [i for i in REGIONS if not a.only or i in a.only.split(',')]
    summary = []
    for rid in ids:
        b, log = build(rid, repo, packets, idx)
        print('\n'.join(log))
        hourly = b.pop('hourly', None)
        hf = outd / f'{rid}.hourly.js'
        if hourly:
            m = hourly['meta']
            b['hourly_meta'] = dict(n_samples=m['n_samples'], hours=m['hours'], cutoffs=len(m['cutoffs']), env=m['env'], checkpoint_sha256=m['checkpoint_sha256'])
            hf.write_text(f'(window.WFG_HOURLY=window.WFG_HOURLY||{{}})[{json.dumps(rid)}]=' + json.dumps(hourly, separators=(',', ':')) + ';\n')
            print(f'  wrote {hf.name} {hf.stat().st_size / 1e6:.2f} MB (loaded after the first view)')
        elif hf.exists():
            hf.unlink()
        write_parts(b, rid, outd)
        bs = None
        if b['booth']:
            bs = [dict(input_time=x['input_time'], counts=Counter((r['v'], 'care' if r.get('vul') else 'village' if r.get('cat') == 'village' else r.get('cat')) for r in x['rows'])) for x in b['booth']]
            bs = [dict(input_time=x['input_time'], counts={f'{k[0]}|{k[1]}': v for k, v in x['counts'].items()}) for x in bs]
        summary.append(dict(id=rid, name=b['name'], year=b['year'], event=b['event'], loc_ko=b['loc_ko'], loc_en=b['loc_en'], bbox=b['bbox'], km=b['km'],
                            inputs=b['input_times'], cases=sorted(b['policies']), rq3=b['rq3'], booth=bs,
                            origins=sum(1 for p in b['places'] if p['role'] == 'origin'), destinations=sum(1 for p in b['places'] if p['role'] == 'destination'),
                            hourly=bool(b.get('hourly_meta'))))
    if a.only:
        print('index.js not rewritten (--only); run without --only to refresh the region index')
    else:
        (outd / 'index.js').write_text('window.WFG_REGION_INDEX=' + json.dumps(summary, ensure_ascii=False, separators=(',', ':')) + ';\n')
        print('wrote index.js')


if __name__ == '__main__':
    sys.exit(main())
