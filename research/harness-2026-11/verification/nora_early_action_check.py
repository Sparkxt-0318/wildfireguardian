"""Independent verifier: recompute the AIR-EXTRACT early-action list (EARLY_ACTION_RULE.md + amendment 1) from the pinned
inputs with own code, and compare with EARLY_ACTION_LIST.json. argv: headline, split, INSTANCE, list json"""
import json, sys, hashlib, collections, datetime as dt
HL, SP, IN, LST = sys.argv[1:5]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
L = json.load(open(LST)); print('input shas match header:', {k: sha(p) == L['inputs_sha256'][k] for k, p in (('headline', HL), ('split', SP), ('instance', IN))})
hl = json.load(open(HL)); sp = json.load(open(SP)); inst = json.load(open(IN))['instances']
V3 = ('kriged_mean', 'firms_early', 'envelope'); PREC = ['1', '1b', '2', '3']
MAP = {'no_route_origin_point_in_flame_at_departure': '1', 'lost_route_depends_on_no_reentry': '1b',
       'no_route_fire_limited_within_loaded_graph': '2', 'no_route_possibly_road_limited': '3'}
cls = {(r['region'], r['start'], r['horizon_h'], r['variant'], r['origin']): r['class'] for r in sp['rows']}
grid = {}
for i in inst:
    for h in (5, 8): grid[(i['region'], i['start_tag'], h)] = [t for t in i['depart_offsets_s'] if t < h * 3600] if h == 5 else None
def grid_of(reg, st, h):
    i = [x for x in inst if x['region'] == reg and x['start_tag'] == st][0]
    return list(range(0, h * 3600, 1800))
def clock(st, off):
    t = dt.datetime.strptime(st, '%Y%m%dT%H%M%SZ') + dt.timedelta(seconds=off + 9 * 3600)
    return t.strftime('%Y-%m-%d %H:%M KST (replay)')
G = collections.Counter(); mine = {}; issues = []
for p in hl['places']:
    reg, st, h, o = p['region'], p['start'], p['horizon_h'], p['origin']; H = h * 3600; gr = grid_of(reg, st, h)
    c = {v: cls[(reg, st, h, v, o)] for v in V3}
    pv = p['nr_cert']['per_variant']; lb = {v: pv[v].get('leave_by_s') for v in V3}; cen = {v: bool(pv[v].get('horizon_censored')) for v in V3}
    for v in V3:
        if cen[v] and lb[v] is not None and lb[v] < gr[-1]: issues.append(('censored before last grid time', reg, st, h, o, v, lb[v]))
    ne = [v for v in V3 if c[v] == 'not_evaluated']
    key = (reg, st, h, o)
    if len(ne) == 3: G['b'] += 1; mine[key] = ('b',); continue
    if ne: G['c'] += 1; mine[key] = ('c',); continue
    closed = lambda v, t: lb[v] is None or t > lb[v]
    if any(all(closed(v, t) for v in V3) for t in gr):
        labs = [MAP[c[v]] for v in V3 if c[v] in MAP]
        lab = min(labs, key=PREC.index) if labs else 'closes_in_horizon'
        prs = {}
        for v in V3:
            if lb[v] is None: prs[v] = 'none at any computed time'
            elif cen[v] or lb[v] >= H: prs[v] = 'route at every computed time to H'
            else:
                last = max(t for t in gr if t <= lb[v]); nxt = last + 1800
                prs[v] = f'+{last // 60} min ({clock(st, last)}) / ' + ('none up to the horizon (H)' if nxt >= H else f'+{nxt // 60} min ({clock(st, nxt)}), none')
        G['main:' + lab] += 1; mine[key] = ('main', lab, prs)
    elif any(any(closed(v, t) for v in V3) for t in gr): G['some'] += 1; mine[key] = ('some',)
    else: G['never'] += 1; mine[key] = ('never',)
print('my groups', dict(sorted(G.items())))
his = {}
for k, lst in (('main', L['main_list']), ('some', L['some_variants_only']), ('c', L['mixed_not_evaluated'])):
    for u in lst: his[(u['region'], u['start'], u['horizon_h'], u['origin'])] = (k, u.get('cause_label'), u['pairs'])
for u in L['not_evaluated']['units'] if isinstance(L['not_evaluated'], dict) and 'units' in L['not_evaluated'] else []:
    his[(u['region'], u['start'], u['horizon_h'], u['origin'])] = ('b', None, None)
mm = []
for k, m in mine.items():
    hk = his.get(k)
    if m[0] in ('main', 'some', 'c'):
        if hk is None or hk[0] != m[0]: mm.append(('group', k, m[0], hk and hk[0])); continue
        if m[0] == 'main' and (hk[1] != m[1] or hk[2] != m[2]): mm.append(('label/pairs', k, m[1], hk[1], {v: (m[2][v], hk[2][v]) for v in V3 if m[2][v] != hk[2][v]}))
    elif hk is not None and hk[0] != m[0]: mm.append(('group', k, m[0], hk[0]))
print('units', len(mine), 'his listed', len(his), 'mismatches', len(mm)); [print('  ', x) for x in mm[:8]]
print('censored-before-last-grid issues', len(issues), issues[:5])
print('his counts', L['counts'])
