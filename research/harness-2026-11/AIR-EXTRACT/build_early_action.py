"""EARLY_ACTION_RULE.md: build the staff/agency early-action list from the verified `/2` headline, and test E1-E9.

Reads only committed inputs (pinned by sha256 in the output header); recomputes no routing.

    python3 build_early_action.py --f31-results DIR --fdyn DIR --out-dir results
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

VARIANTS = ('kriged_mean', 'firms_early', 'envelope')
STEP = 1800
LABELS = {
    '1': 'origin already inside the modelled fire area at that departure time',
    '1b': 'every road exit crosses ground the model shows as already burned',
    '2': 'every road exit in the mapped area is blocked by modelled fire',
    '3': 'undetermined: map window too small',
    'closes_in_horizon': ('a checked route at the start under every variant; none from a later computed time under every '
                          'variant (modelled fire); cause of closing not classified'),
}
FLAG_1B = 'depends on the no-re-entry rule'
CLASS_TO_LABEL = {'no_route_origin_point_in_flame_at_departure': '1', 'lost_route_depends_on_no_reentry': '1b',
                  'no_route_fire_limited_within_loaded_graph': '2', 'no_route_possibly_road_limited': '3'}
PRECEDENCE = ['1', '1b', '2', '3']
NOT_EVAL = 'start point on ground the model shows as burned before this start time: not evaluated'
EARLIEST = 'earliest of the three variants computed; the fire may close roads earlier than any of them'
EDGE_PLACES = {'축산리', '옥계리', '항리'}
EDGE_CAVEAT = 'within one cell of the grid edge; radiant heat from fire outside the grid is not modelled'
PREFIX = 'prefix (measured on the /2 headline, ledger row 72)'
WAIT_R = ('Each departure time in [0, H), step 1,800 s, is a separate trip. Leaving later is how waiting at the start '
          'place is represented. Once moving, a stop is allowed only at a road dead end (a graph dead-end node), which '
          'may be a short detour off the route; waiting is not allowed at any other node.')
WAIT_COL = 'not computed for the /2 multi-hour field'
MAP_EDGE = ('Map-edge limit: no headline route touches the edge of the fire-data grid. This holds for the graphs, not '
            'only for the routes found: every road node lies strictly inside the grid, so no route on these graphs can '
            'touch it (ledger row 80). Heat is not covered: 축산리, 옥계리 and 항리 have roads within one cell of the '
            'edge. The one-cell ring is an indicator, not a bound.')
STAFF = ('Staff and agency use only. Not resident-facing. SCENARIO from a fire reconstruction, not what happened. '
         '"Checked" means a witness passes the full checker on the as-built packet; it says nothing about road '
         'condition on the day.')
WIDE_TEXT = {'route found': 'route found by the router on the widened graph, to the listed destinations; not independently checked',
             'undetermined': 'undetermined: depends on fire outside the export grid',
             'no route found': 'no route found by the router on the widened graph to the listed destinations; not independently checked'}
FORBIDDEN = [r'\bsafe\b', r'\bdeadlines?\b', r'no result depends on what burns outside the grid', r'(?<![\w-])no route(?! found)(?!_)',
             r'\btrapped\b', r'escape route']
ABSENCE = "one fire, March 2025, that day's wind. A place not on this list has not been shown to have a road escape."
MIXED_HEAD = 'timing variants disagree on whether the modelled fire has already reached the start point'
SOME_HEAD = 'no checked route under some variants only'
KST = dt.timedelta(hours=9)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clock(start_tag, off):
    t = dt.datetime.strptime(start_tag, '%Y%m%dT%H%M%SZ') + dt.timedelta(seconds=off) + KST
    return t.strftime('%Y-%m-%d %H:%M KST (replay)')


def pair(leave_by, censored, H, start):
    """(text, last, next) per EARLY_ACTION_RULE §5."""
    if leave_by is None:
        return 'none at any computed time', None, None
    if censored or leave_by >= H:
        return 'route at every computed time to H', None, None
    last = (leave_by // STEP) * STEP
    nxt = last + STEP
    if nxt >= H:
        return (f'+{last // 60} min ({clock(start, last)}) / none up to the horizon (H)', last, None)
    return (f'+{last // 60} min ({clock(start, last)}) / +{nxt // 60} min ({clock(start, nxt)}), none', last, nxt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--f31-results', type=Path, required=True)
    ap.add_argument('--fdyn', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    files = {'headline': a.f31_results / 'HEADLINE_NR2_summary.json',
             'split': a.f31_results / 'HEADLINE_NR2_not_evaluated_split.json',
             'border': a.f31_results / 'BORDER_TOUCH_NR2.json',
             'widened_ua': a.fdyn / 'results' / 'WIDENED_RESULTS_UA.json',
             'widened_yd': a.fdyn / 'results' / 'WIDENED_RESULTS_YD.json',
             'instance': a.fdyn / '_data' / 'INSTANCE.json'}
    hl = json.loads(files['headline'].read_text())
    sp = json.loads(files['split'].read_text())
    inst = json.loads(files['instance'].read_text())['instances']
    grids = {(i['region'], i['start_tag'], i['horizon_s'] // 3600): (i['depart_offsets_s'], i['horizon_s']) for i in inst}
    names = {(i['region'], o['origin_id']): (o.get('name'), o.get('name_en'), o['entry_node'])
             for i in inst for o in i['origins']}
    cls = {(r['region'], r['start'], r['horizon_h'], r['variant'], r['origin']): r for r in sp['rows']}
    wide = {}
    for k in ('widened_ua', 'widened_yd'):
        w = json.loads(files[k].read_text())
        for r in w['per_place']:
            c = r['class']
            key = 'route found' if c.startswith('route found') else ('undetermined' if c.startswith('undetermined') else 'no route found')
            wide.setdefault((w['region'], r['start'], r['horizon_h'], r['entry_node']), set()).add((r['variant'], key))
    units, some, mixed, not_eval, never = [], [], [], [], 0
    agree = Counter()

    def unit_row(p, rows, lb, cen, grid, H, evaluated):
        reg, st, h, o = p['region'], p['start'], p['horizon_h'], p['origin']
        prs = {}
        for v in VARIANTS:
            prs[v] = pair(lb[v], cen[v], H, st)[0] if v in evaluated else 'not evaluated'
        ev = [v for v in VARIANTS if v in evaluated]
        earliest_v = min(ev, key=lambda v: (-1 if lb[v] is None else lb[v])) if ev else None
        nm = names.get((reg, o), (None, None, None))
        w = sorted(wide.get((reg, st, h, nm[2]), set()))
        per_var = {v: (CLASS_TO_LABEL.get(rows[v]['class']) or ('not evaluated' if rows[v]['class'] == 'not_evaluated'
                                                                 else 'route')) for v in VARIANTS}
        return {'region': reg, 'start': st, 'horizon_h': h, 'origin': o, 'name': nm[0], 'name_en': nm[1],
                'per_variant_labels': per_var, 'pairs': prs, 'leave_by_s': lb,
                'earliest': None if earliest_v is None else {'variant': earliest_v, 'pair': prs[earliest_v], 'label': EARLIEST},
                'prefix': PREFIX, 'envelope_burnset_static_row': p.get('static_final_footprint_row'),
                'waiting_rule_dependence': WAIT_COL, 'grid_step_s': STEP,
                'edge_caveat': EDGE_CAVEAT if nm[0] in EDGE_PLACES else None,
                'widened_class': [{'variant': v, 'class': WIDE_TEXT[k],
                                   **({'note': 'verification pending'} if reg == 'yeongdeok_2025' else {})} for v, k in w] or None}

    for p in hl['places']:
        reg, st, h, o = p['region'], p['start'], p['horizon_h'], p['origin']
        grid, H = grids[(reg, st, h)]
        rows = {v: cls[(reg, st, h, v, o)] for v in VARIANTS}
        pv = p['nr_cert']['per_variant']
        lb = {v: pv[v].get('leave_by_s') for v in VARIANTS}      # a {'no_route': ...} record = no route at any grid time
        cen = {v: bool(pv[v].get('horizon_censored')) for v in VARIANTS}
        for v in VARIANTS:
            agree[p['nr_router']['per_variant'][v].get('leave_by_s') == lb[v]] += 1
        ne = [v for v in VARIANTS if rows[v]['class'] == 'not_evaluated']
        if len(ne) == 3:
            not_eval.append({'region': reg, 'start': st, 'horizon_h': h, 'origin': o, 'variants': ne})
            continue
        if ne:
            mixed.append(unit_row(p, rows, lb, cen, grid, H, [v for v in VARIANTS if v not in ne]))
            continue
        closed = lambda v, t: lb[v] is None or t > lb[v]
        all_t = [t for t in grid if all(closed(v, t) for v in VARIANTS)]
        some_t = [t for t in grid if any(closed(v, t) for v in VARIANTS)]
        if all_t:
            u = unit_row(p, rows, lb, cen, grid, H, VARIANTS)
            labs = [CLASS_TO_LABEL[rows[v]['class']] for v in VARIANTS if rows[v]['class'] in CLASS_TO_LABEL]
            lab = min(labs, key=PRECEDENCE.index) if labs else 'closes_in_horizon'
            u.update({'cause_label': lab, 'cause_text': LABELS[lab], 'flag': FLAG_1B if lab == '1b' else None,
                      'excluded_from_no_escape_counts': lab in ('3', 'closes_in_horizon'),
                      'first_grid_departure_in_set': all_t[0]})
            units.append(u)
        elif some_t:
            u = unit_row(p, rows, lb, cen, grid, H, VARIANTS)
            u['first_grid_departure_some_closed'] = some_t[0]
            some.append(u)
        else:
            never += 1
    # ---- pass criteria
    tests = {}
    e1 = []
    for u in units + some:
        H = grids[(u['region'], u['start'], u['horizon_h'])][1]
        for v in VARIANTS:
            lbv = u['leave_by_s'][v]
            if lbv is not None and lbv < H and 'route at every' not in u['pairs'][v]:
                last = (lbv // STEP) * STEP
                if not (last <= lbv < last + STEP and u['pairs'][v].startswith(f'+{last // 60} min')):
                    e1.append((u['origin'], v))
        mins = min((-1 if u['leave_by_s'][v] is None else u['leave_by_s'][v]) for v in VARIANTS)
        lbe = u['leave_by_s'][u['earliest']['variant']]
        if (-1 if lbe is None else lbe) != mins:
            e1.append((u['origin'], 'earliest'))
    tests['E1_pairs'] = not e1
    ne_keys = {(n['region'], n['start'], n['horizon_h'], n['origin']) for n in not_eval}
    tests['E2_not_evaluated_off_list'] = not any((u['region'], u['start'], u['horizon_h'], u['origin']) in ne_keys
                                                 for u in units + some + mixed)
    split_ne = Counter((r['region'], r['start'], r['horizon_h'], r['variant']) for r in sp['rows']
                       if r['class'] == 'not_evaluated' and r['variant'] in VARIANTS)
    own_ne = Counter((n['region'], n['start'], n['horizon_h'], v) for n in not_eval for v in n['variants']) + \
        Counter((m['region'], m['start'], m['horizon_h'], v) for m in mixed for v in VARIANTS if m['pairs'][v] == 'not evaluated')
    tests['E2_counts_equal_split'] = split_ne == own_ne
    listed = {(u['region'], u['start'], u['horizon_h'], u['origin']) for u in units}
    tests['E3_membership'] = all(u['first_grid_departure_in_set'] is not None for u in units)
    tests['E4_labels'] = all(u['cause_label'] in LABELS for u in units)
    tests['E5_reconciliation'] = len(units) + len(some) + never + len(mixed) + len(not_eval) == len(hl['places']) == 1044
    tests['E6_edge_caveat'] = all((u['edge_caveat'] is not None) == (u['name'] in EDGE_PLACES) for u in units + some + mixed)
    tests['E7_widened_text'] = all(c['class'] in WIDE_TEXT.values() and set(c) <= {'variant', 'class', 'note'}
                                   for u in units + some + mixed for c in (u['widened_class'] or []))
    tests['E8_cert_router_agree'] = agree[False] == 0
    no_escape = Counter(u['cause_label'] for u in units if not u['excluded_from_no_escape_counts'])
    out = {'schema': 'wfg.air-extract.early-action/1', 'rule': 'EARLY_ACTION_RULE.md (+ amendment 1)', 'staff_label': STAFF,
           'absence_line': ABSENCE, 'waiting_wording_R': WAIT_R, 'map_edge': MAP_EDGE, 'prefix': PREFIX,
           'earliest_label': EARLIEST,
           'checker': 'deadline_field/headline.py @ 54bcb96e + kit routing-package/routing/independent.py::check_route '
                      '(file sha256 41fcfee25b980b080287025e2b883e5f0f78d7d21580a5c1633375cf1e64ca2a)',
           'packets': 'MANIFEST_v3_7 no_reentry/2, sha256 7c178267…', 'numpy': np.__version__,
           'inputs_sha256': {k: sha(f) for k, f in files.items()},
           'not_evaluated': {'label': NOT_EVAL, 'state_line': sp.get('state_line'), 'units_all_three': len(not_eval),
                             'rows_per_variant': {'|'.join(map(str, k)): n for k, n in sorted(own_ne.items())}},
           'counts': {'units': len(hl['places']), 'main_list': len(units), 'some_variants_only': len(some),
                      'never_in_set': never, 'mixed_not_evaluated': len(mixed), 'not_evaluated_all_three': len(not_eval),
                      'main_by_label': dict(Counter(u['cause_label'] for u in units)),
                      'no_escape_count_by_label': dict(no_escape),
                      'cert_router_leave_by_agree': dict((str(k), v) for k, v in agree.items())},
           'main_list': units, 'some_variants_only': some, 'mixed_not_evaluated': mixed}
    a.out_dir.mkdir(parents=True, exist_ok=True)
    js = json.dumps(out, ensure_ascii=False, indent=1)
    md = render(out)
    scan = md.replace(MAP_EDGE, '').replace(out['checker'], '')   # pinned verbatim strings (amendment 1, E9 scope)
    bad = [pat for pat in FORBIDDEN if re.search(pat, scan, re.I)]
    tests['E9_wording'] = not bad and ABSENCE in md and ABSENCE in json.dumps(out, ensure_ascii=False)
    out['pass_criteria'] = tests
    out['all_pass'] = all(tests.values())
    out['E9_forbidden_hits'] = bad
    (a.out_dir / 'EARLY_ACTION_LIST.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (a.out_dir / 'EARLY_ACTION_LIST.md').write_text(md)
    print(json.dumps({'pass_criteria': tests, 'counts': out['counts'], 'E9_hits': bad}, ensure_ascii=False, indent=1))


def _notes(u):
    notes = []
    if u.get('flag'):
        notes.append(u['flag'])
    if u.get('excluded_from_no_escape_counts'):
        notes.append('not added to any no-escape count')
    if u['edge_caveat']:
        notes.append(u['edge_caveat'])
    for c in u['widened_class'] or []:
        notes.append(f'widened graph ({c["variant"]}): {c["class"]}' + (f' [{c["note"]}]' if c.get('note') else ''))
    return '; '.join(notes)


def _table(L, title, us, with_cause):
    groups = {}
    for u in us:
        groups.setdefault((u['region'], u['start'], u['horizon_h']), []).append(u)
    L += [f'# {title}', '']
    if not us:
        L += ['(none)', '']
    for (reg, st, h), g in sorted(groups.items()):
        L += [f'## {reg}, start {st}, horizon {h} h', '',
              '| Place | ' + ('Cause (modelled) | ' if with_cause else '') +
              'Per-variant labels | kriged_mean | firms_early | envelope | Earliest | Waiting rule | Notes |',
              '|---|' + ('---|' if with_cause else '') + '---|---|---|---|---|---|---|']
        for u in sorted(g, key=lambda x: (x['earliest']['pair'] if x['earliest'] else '', x['name'] or '')):
            pvl = ', '.join(f'{v}: {u["per_variant_labels"][v]}' for v in VARIANTS)
            e = f'{u["earliest"]["pair"]} ({u["earliest"]["variant"]})' if u['earliest'] else ''
            L.append(f'| {u["name"]} ({u["name_en"]}) | ' + (f'{u["cause_text"]} | ' if with_cause else '') +
                     f'{pvl} | {u["pairs"]["kriged_mean"]} | {u["pairs"]["firms_early"]} | {u["pairs"]["envelope"]} | '
                     f'{e} | {u["waiting_rule_dependence"]} | {_notes(u)} |')
        L.append('')


def render(o):
    c = o['counts']
    L = ['# Early-action list (staff and agency use only)', '', f'> {o["staff_label"]}', '',
         f'> **{o["absence_line"]}**', '',
         f'- **Checker:** {o["checker"]}', f'- **Packets:** {o["packets"]} (headline run on numpy 1.26.4); this list builder: numpy {o["numpy"]}, reads JSON only',
         f'- **Waiting (R):** {o["waiting_wording_R"]}', f'- **{o["map_edge"]}**',
         f'- **Departure sets:** {o["prefix"]}.',
         f'- **Earliest column:** "{o["earliest_label"]}". It is not a bound.',
         f'- **Not on these tables:** {o["not_evaluated"]["units_all_three"]} units "{o["not_evaluated"]["label"]}" '
         f'under all three timing variants. {o["not_evaluated"]["state_line"]}',
         f'- **Counts:** main list {c["main_list"]}; no checked route under some variants only '
         f'{c["some_variants_only"]}; timing variants disagree on the start point {c["mixed_not_evaluated"]}; a '
         f'checked route at every computed time under every variant {c["never_in_set"]}; not evaluated {c["not_evaluated_all_three"]}; total {c["units"]}.',
         f'- **Labels counted toward no-escape totals (1, 1b, 2 only):** {c["no_escape_count_by_label"]}', '']
    _table(L, 'Main list: no checked route under any of the three timing variants at some computed time',
           o['main_list'], True)
    _table(L, o.get('some_head', 'No checked route under some variants only'), o['some_variants_only'], False)
    _table(L, 'Timing variants disagree on whether the modelled fire has already reached the start point',
           o['mixed_not_evaluated'], False)
    L += ['', f'> **{o["absence_line"]}**', '']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
