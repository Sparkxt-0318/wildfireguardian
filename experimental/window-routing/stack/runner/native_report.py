"""Campaign summary for the latest completion kit (v2; derived from the inherited native_report.py cc058ca2...).
Usage: native_report.py RUN primary

Reads analysis/LATEST_PRIMARY/{EXECUTIONS.json,SUMMARY.json}, the first accepted ENVIRONMENT record, the preflight gate and
the kit manifest, and writes NATIVE_SUMMARY_primary.json and .md. Each region and arm is reported separately and once for
all regions; attempts and distinct missions are counted separately; nothing is pooled across hosts, workloads or the
historical three-repetition campaigns; no accuracy or physical-safety claim (resolution is model-relative)."""
import collections, json, pathlib, statistics, sys

RUN, campaign = pathlib.Path(sys.argv[1]), sys.argv[2]
Q = 'LATEST_PRIMARY'
RESOLVED = ('VERIFIED_ROUTE', 'VERIFIED_FULL_OPTIMUM', 'CERTIFIED_REFUSAL')
ROUTE = ('VERIFIED_ROUTE', 'VERIFIED_FULL_OPTIMUM')


def J(p):
    return json.loads(pathlib.Path(p).read_text())


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


def _idx(p):
    parts = p.name.split('.')
    return 1 if len(parts) == 2 else int(parts[1])


envs = sorted(RUN.glob('ENVIRONMENT*.json'), key=_idx); env_list = [J(p) for p in envs]
env = next((e for e in env_list if e.get('accepted')), env_list[0] if env_list else {})
gates = sorted(RUN.glob('PREFLIGHT_GATE_try*.json'))
gate = J(RUN / 'PREFLIGHT_GATE.json') if (RUN / 'PREFLIGHT_GATE.json').exists() else (J(gates[-1]) if gates else None)
man = J(RUN / 'CANDIDATE_MANIFEST.json')
rows = J(RUN / 'analysis' / Q / 'EXECUTIONS.json'); summ = J(RUN / 'analysis' / Q / 'SUMMARY.json')
planned = collections.Counter(r['case_id'] for r in rows if r['arm'] == 'RDA_CAND')


def arm_block(X):
    per = collections.defaultdict(list)
    for r in X:
        per[r['case_id']].append(r['regional_class'])
    stable = {c: v for c, v in per.items() if len(v) == planned[c] and all(k in RESOLVED for k in v)}
    routes = sum(1 for v in stable.values() if all(k in ROUTE for k in v))
    refusals = sum(1 for v in stable.values() if all(k == 'CERTIFIED_REFUSAL' for k in v))
    return {'attempts': len(X), 'missions': len(per), 'missions_resolved_both_reps': len(stable), 'route_missions': routes,
            'refusal_missions': refusals, 'mixed_missions': len(stable) - routes - refusals,
            'missions_resolved_any_rep': sum(1 for v in per.values() if any(k in RESOLVED for k in v)),
            'resolved_attempts': sum(r['resolved'] for r in X), 'checked_route_attempts': sum(r['regional_class'] in ROUTE for r in X),
            'certified_refusal_attempts': sum(r['regional_class'] == 'CERTIFIED_REFUSAL' for r in X),
            'on_time_attempts': sum(bool(r.get('on_time')) for r in X),
            'reporting_classes': dict(collections.Counter(r.get('reporting_class') for r in X)),
            'regional_classes': dict(collections.Counter(r['regional_class'] for r in X)),
            'contradictions': sum(r.get('class') == 'CONTRADICTION' for r in X),
            'independent_states': dict(collections.Counter(r.get('independent_state') for r in X)),
            'cleanup_states': dict(collections.Counter(str(r.get('cleanup_state')) for r in X)),
            'wall_median_s': med([r.get('wall_s') for r in X]), 'wall_max_s': max([r['wall_s'] for r in X if r.get('wall_s') is not None] or [None], key=lambda v: -1 if v is None else v),
            'wall_median_resolved_s': med([r.get('wall_s') for r in X if r['resolved']]),
            'cpu_sum_s': round(sum(r.get('cpu_s') or 0 for r in X), 2),
            'rss_max_mib': max([r['rss_mib'] for r in X if r.get('rss_mib') is not None] or [None], key=lambda v: -1 if v is None else v),
            'memory_guard_stops': sum(bool(r.get('memory_guard_triggered')) for r in X),
            'per_mission': {c: v for c, v in sorted(per.items())}}


out = {'schema': 'wfg.latest-kit.campaign-summary/2', 'campaign': campaign, 'queue': Q,
       'label': 'Latest-forecast completion: two full-policy arms (RDA_BASE reference, RDA_CAND candidate), two repetitions, 30 s complete-request deadline, 3,072 MiB guard, fast cold preparation',
       'candidate_id': man.get('candidate_id'), 'candidate_manifest_files': len(man['files']),
       'host': {k: env.get('host', {}).get(k) for k in ('platform', 'machine', 'node', 'cpu', 'sw_vers', 'memsize', 'power')},
       'interpreter': {k: env.get('interpreter', {}).get(k) for k in ('version', 'realpath', 'realpath_sha256', 'numpy')},
       'environment_records': [p.name for p in envs], 'preflight_gate_pass': None if gate is None else gate.get('PASS'),
       'preflight_gate_tries': {p.name: J(p).get('PASS') for p in gates},
       'scope': ('one host and one workload; never pooled with Linux results or the historical three-repetition campaigns; resolution is '
                 'model-relative benchmark resolution under the frozen classes, not accuracy and not physical safety'),
       'all_regions': {}, 'regions': {}, 'paired': summ.get('paired')}
md = ['# Latest completion campaign summary', '', out['label'] + '.', '',
      'Host: %s %s, %s. Interpreter %s, numpy %s.' % (out['host'].get('platform'), out['host'].get('machine'), out['host'].get('cpu'),
                                                        (out['interpreter'].get('version') or '').split()[0], out['interpreter'].get('numpy')),
      '', out['scope'] + '.', '']
for scope, X in [('ALL REGIONS', rows)] + [(g, [r for r in rows if r['region'] == g]) for g in sorted({r['region'] for r in rows})]:
    blk = {arm: arm_block([r for r in X if r['arm'] == arm]) for arm in ('RDA_BASE', 'RDA_CAND')}
    if scope == 'ALL REGIONS':
        out['all_regions'] = blk
    else:
        out['regions'][scope] = blk
    md += ['## %s' % scope, '', '| Arm | Missions | Resolved in both reps (routes / refusals / mixed) | Resolved attempts | Checked-route attempts | On time | Median wall s | Max RSS MiB | Reporting classes |',
           '|---|---|---|---|---|---|---|---|---|']
    for arm, a in blk.items():
        md.append('| %s | %d | %d (%d / %d / %d) | %d of %d | %d | %d | %s | %s | %s |' % (
            arm, a['missions'], a['missions_resolved_both_reps'], a['route_missions'], a['refusal_missions'], a['mixed_missions'],
            a['resolved_attempts'], a['attempts'], a['checked_route_attempts'], a['on_time_attempts'], a['wall_median_s'], a['rss_max_mib'],
            ', '.join('%s %d' % kv for kv in sorted(a['reporting_classes'].items()))))
    md.append('')
p = summ.get('paired') or {}
md += ['Paired (same mission and repetition): %s pairs, both resolved %s, same arrival when both resolved routes %s, median wall candidate/reference %s / %s s.'
       % (p.get('pairs'), p.get('both_resolved'), p.get('same_arrival_when_both_resolved_routes'), p.get('median_wall_cand_s'), p.get('median_wall_base_s')), '',
       'Resolved classes: VERIFIED_ROUTE, VERIFIED_FULL_OPTIMUM, CERTIFIED_REFUSAL. ROAD_ONLY_ROUTE and UNSUPPORTED_REFUSAL_CLAIM are not resolved. '
       'DEADLINE_STOP is the reporting class of a deadline-terminated, unresolved attempt.', '']
(RUN / ('NATIVE_SUMMARY_%s.json' % campaign)).write_text(json.dumps(out, indent=1, default=str) + '\n')
(RUN / ('NATIVE_SUMMARY_%s.md' % campaign)).write_text('\n'.join(md) + '\n')
print('\n'.join(md))
