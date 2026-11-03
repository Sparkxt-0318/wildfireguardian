#!/usr/bin/env python3
"""Compute every impact number (path A) and write NUMBERS.json, tables/, figures/, APPLICATION_SENTENCES.md and the
generated blocks of README.md.

Run from anywhere with the venv described in README.md (Python 3.12, requirements.txt):
    python research/solve2027-impact/compute.py            # write all outputs
    python research/solve2027-impact/compute.py --check    # recompute; fail if any committed text output differs
    python research/solve2027-impact/verify.py             # path B: independent recomputation of every number

Needs the SHA-verified road graphs and HAZARD packets (python tools/fetch_routing_inputs.py): graphs for redundancy,
route lengths and fire-free trips, HAZARD.json for the scenario window (valid_from, valid_until, dt).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from wfg_impact import analysis, figures, numbers as numbers_mod, sentences, sources  # noqa: E402

SCHEMA = 'wfg.solve2027.impact_numbers/1'
CAVEATS = [
    'Fire scenarios: each recorded input time has 4 scenario members drawn independently per 375 m cell from the c651 '
    'forecast ("fire scenarios from the forecast"); they are not fire-spread simulations of the actual fire.',
    'Horizon: 1 hour after each recorded input time. Departures were checked every 10 minutes (0-50 min); times '
    'between checked departures are not checked, and a leave-by deadline of +50 min means the window may extend later.',
    'Scenario window: a departure can only be checked if arrival plus the 120 s stay ends within the 1-hour window '
    '(valid_until 3600 s), so at +50 min only places whose fastest fire-free trip to a candidate destination is at most '
    '480 s can have a checked route. Missing checked routes at later departures and early leave-by deadlines are '
    'therefore often set by the window, not by fire: use window_limited.*, not_checked_although_fits.* and '
    'deadline_set_by.* for statements about fire.',
    'Roads: provisional historical OpenStreetMap snapshot (2025-03-21) at an assumed 40 km/h (rounded up to 1 s '
    'ticks), no congestion, missing one-way tags assumed two-way, no field validation of passability.',
    'Destinations: for each place the 3 nearest (straight line) OpenStreetMap destinations with distinct road entry '
    'nodes; those used are OSM schools, community halls and one unnamed OSM point tagged amenity=shelter without '
    'shelter_type (a candidate for one Yeongdeok place; keys destinations_used.*) - not official evacuation shelters. '
    'Travel between a mapped point and its road entry '
    'node is not modelled. Places come from a 2026-10-17 OSM extract (current data) while the road graph is the '
    'pre-fire snapshot.',
    'Host: the cache was computed by the Route-Check API on the evaluated macOS arm64 host (purpose "booth") with the '
    'fixed 30 s request budget; timed-out checks that were re-checked are shown as their re-check, as in the planner.',
    'Model-relative: checked_route = a route that passed the checks within the model and its inputs; model_no_route is '
    'not proof that escape is impossible; unresolved = cannot judge, never safe. None of these numbers are evacuation '
    'outcomes, observed travel times or casualties avoided.',
]


# ------------------------------------------------------------------------------------------------ NUMBERS.json

def numbers_document(result: dict, nums: dict) -> dict:
    inputs = {row['path']: {'sha256': row['sha256'], 'bytes': row['bytes'], **({'note': row['note']} if 'note' in row else {})}
              for row in sources.input_files_record(result['entries'], True)}
    scopes = {}
    for m in result['metas']:
        scopes[m['scope']] = {k: m[k] for k in ('region', 'input_time', 'input_kst', 'scenario_set_id', 'cache_file',
                                                'cache_sha256', 'created_at', 'api_version', 'purpose', 'step_min',
                                                'shelters_per_origin', 'host', 'graph_id', 'graph_sha256',
                                                'hazard_sha256', 'hazard_file', 'valid_from_s', 'valid_until_s', 'dt_s',
                                                'route_check_records', 'recheck_records', 'travel_only_records',
                                                'tie_breaks')}
    for key, e in nums.items():
        if e['scope'] not in scopes:
            scopes[e['scope']] = {'text': e['scope_text'],
                                  'cache_files': [p for p in e['inputs'] if p.startswith('planner/cache/') and p.endswith('Z.json')]}
    for m in result['metas']:
        scopes[m['scope']]['text'] = numbers_mod._scope_text(m['scope'], {x['scope']: x for x in result['metas']})
    compact = {}
    for key, e in nums.items():
        c = {'value': e['value'], 'numerator': e['numerator'], 'denominator': e['denominator']}
        if 'share' in e:
            c['share'] = e['share']
        if 'n' in e:
            c['n'] = e['n']
        c.update({'unit': e['unit'], 'scope': e['scope'], 'subset': e['subset'], 'uses_graph': e['uses_graph'],
                  'uses_hazard': e['uses_hazard'], 'definition': e['definition']})
        compact[key] = c
    headline = {}
    for key in numbers_mod.HEADLINE_KEYS:
        e = nums[key]
        headline[key] = {k: e[k] for k in ('value', 'numerator', 'denominator', 'share', 'n', 'unit', 'definition',
                                           'scope', 'subset', 'scope_text', 'uses_graph', 'uses_hazard', 'script',
                                           'inputs', 'input_sha256') if k in e}
    return {
        'schema': SCHEMA,
        'title': 'Who needs more time: model-relative impact numbers from the recorded 2025 planner cache',
        'statement': 'Every number describes what the WildfireGuardian Route-Check API concluded for recorded fire-scenario '
                     'members of the March 2025 Uiseong-Andong and Yeongdeok fires (planner cache, computed on the '
                     'evaluated macOS host). None is an evacuation outcome.',
        'generator': {'script': numbers_mod.SCRIPT,
                      'path_a': 'research/solve2027-impact/wfg_impact/{sources,planner_rules,api_rules,maxflow,trips,analysis,numbers}.py',
                      'independent_check': 'research/solve2027-impact/verify.py (path B: research/solve2027-impact/wfg_impact/path_b.py, '
                                           'pandas + networkx, recomputes every key from route_checks)',
                      'requirements': 'research/solve2027-impact/requirements.txt', 'python': '3.12'},
        'definitions_common': {'population': numbers_mod.POP, 'cell_verdict': numbers_mod.CELL_RULE,
                               'leave_by_deadline': numbers_mod.DEADLINE_RULE, 'scenario_window': numbers_mod.WINDOW_RULE,
                               'key_format': '<metric>@<scope>[#<subset>]; see README.md "Key format"'},
        'caveats': CAVEATS,
        'inputs': inputs,
        'graphs': result['graphs'],
        'scopes': scopes,
        'headline_keys': list(numbers_mod.HEADLINE_KEYS),
        'headline': headline,
        'numbers': compact,
    }


# ------------------------------------------------------------------------------------------------ tables

def _csv_text(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def table_rows(result: dict) -> dict[str, list[dict]]:
    offs = sources.GRID_OFFSETS_S
    cases = []
    for r in result['records']:
        row = {'scope': r['scope'], 'region': r['region'], 'input_time_utc': r['input_time'], 'input_kst': r['input_kst'],
               'origin_id': r['origin_id'], 'name': r['name'] or '', 'name_en': r['name_en'] or '',
               'origin_type': r['origin_type'],
               'category': r['category'], 'checkable': r['checkable'], 'note': r['note'] or '',
               'best_verdict': r['best_verdict'],
               'leave_by_offset_s': '' if r['latest_s'] is None else r['latest_s'],
               'leave_by_kst': '' if r['latest_s'] is None else sources.kst_label(r['input_time'], r['latest_s']),
               'contiguous_offset_s': '' if r['contiguous_s'] is None else r['contiguous_s'],
               'deadline_category': r['deadline_category']}
        for t in offs:
            row[f'cell_{t:04d}s'] = r['cells'].get(t, '')
        row['other_offsets'] = ';'.join(f'{t}:{v}' for t, v in sorted(r['cells'].items()) if t not in offs)
        row['fastest_fire_free_trip_s'] = _blank(r.get('trip_min_s'))
        for t in offs:
            row[f'trip_fits_window_{t:04d}s'] = '' if 'fits' not in r else r['fits'][t]
        row['deadline_set_by'] = r.get('deadline_set_by') or ''
        row.update({'n_attempts': r['n_attempts'], 'n_rechecked_attempts': r['n_rechecked_attempts'],
                    'unresolved_reasons': ';'.join(f'{k}:{v}' for k, v in sorted(r['unresolved_reasons'].items())),
                    'api_best_verdict': (r.get('api') or {}).get('recorded', {}).get('best_verdict', ''),
                    'api_latest_checked_depart_offset_s': _blank((r.get('api') or {}).get('recorded', {}).get('latest_s')),
                    'api_latest_contiguous_checked_depart_offset_s': _blank((r.get('api') or {}).get('recorded', {}).get('contiguous_s')),
                    'entry_node': r['entry_node'] or '', 'candidate_destination_nodes': ';'.join(r['dest_nodes'] or []),
                    'best_destination_id': r['best_destination_id'] or '', 'best_arrival_s': _blank(r['best_arrival_s'])})
        cases.append(row)
    pairs = []
    for p in result['pairs']:
        pairs.append({'scope': p['scope'], 'origin_id': p['origin_id'], 'name': p['name'] or '', 'name_en': p['name_en'] or '',
                      'origin_type': p['origin_type'],
                      'depart_offset_s': p['depart_offset_s'], 'destination_id': p['destination_id'],
                      'has_comparison': p['has_comparison'],
                      'same_start_destination_offset': p.get('same_start_destination_offset', ''),
                      'checked_arrival_s': p['checked_arrival_s'], 'fastest_arrival_s': _blank(p.get('fastest_arrival_s')),
                      'extra_arrival_s': _blank(p.get('extra_arrival_s')),
                      'checked_length_m': _round(p.get('checked_length_m')), 'fastest_length_m': _round(p.get('fastest_length_m')),
                      'extra_length_m': _round(p.get('extra_length_m')),
                      'fastest_meets_flames': p.get('fastest_meets_flames', ''),
                      'fastest_contact_members_of_4': _blank(p.get('fastest_contact_members')),
                      'fastest_whole_road_contact': p.get('fastest_whole_road_contact') or '',
                      'fastest_passes_full_policy': _blank(p.get('fastest_passes_full_policy')),
                      'fastest_violations': ';'.join(p.get('fastest_violations') or [])})
    red = []
    for x in result['redundancy']:
        red.append({'region': x['region'], 'origin_id': x['origin_id'], 'name': x['name'] or '', 'name_en': x['name_en'] or '',
                    'origin_type': x['origin_type'],
                    'entry_node': x['entry_node'], 'candidate_destination_nodes': ';'.join(x['dest_nodes']),
                    'entry_out_degree': x['entry_out_degree'], 'turn_aware_paths': x['turn_aware_paths'],
                    'plain_paths': x['plain_paths'], 'single_cut_at_entry_node': x['cut_at_entry_node'] if x['turn_aware_paths'] == 1 else '',
                    'min_cut_edges_source_side': ';'.join(x['cut_edges']),
                    'min_cut_osm_ways': ';'.join(str(w) for w in x['cut_source_ways']),
                    'common_edges_on_every_route': '' if x['common_edges'] is None else len(x['common_edges']),
                    'shared_stretch_m': _round(x['shared_stretch_m']),
                    'fastest_fire_free_trip_s': min(v for v in x['trip_by_dest_s'].values() if v is not None)})
    return {'origin_cases.csv': cases, 'travel_only_pairs.csv': pairs, 'redundancy_places.csv': red}


def _blank(v):
    return '' if v is None else v


def _round(v):
    return '' if v is None else round(v, 1)


# ------------------------------------------------------------------------------------------------ README blocks

def _frac(e) -> str:
    return f'{e["numerator"]:,}/{e["denominator"]:,} ({100.0 * e["numerator"] / e["denominator"]:.1f}%)'


def index_reconciliation(result: dict, nums: dict) -> list[dict]:
    """planner/cache/INDEX.json totals per cache file against this package's counts (P4F-06). INDEX counts (precompute.py):
    origins = dispatch origins + research origins; checks = every stored route check (dispatch attempts, re-checks,
    research checks; not the travel_only checks); verdicts = every stored check except a re-checked original."""
    H, rows = nums, []
    for e in result['entries']:
        sc = e['scope']
        g = lambda k: H[f'{k}@{sc}']  # noqa: E731
        row = {'scope': sc, 'index_origins': e['origins'], 'cases': g('cases')['value'],
               'research_origins': g('research_origins')['value'], 'index_checks': e['checks'],
               'dispatch': g('records.dispatch_attempts')['value'], 'rechecks': g('records.rechecks')['value'],
               'research_checks': g('records.research_route_checks')['value'],
               'travel_only': g('records.travel_only')['value'], 'verdicts': {}}
        known = {'checked_route': ('attempts.verdict.checked_route', 'research_checks.verdict.checked_route'),
                 'model_no_route': ('attempts.verdict.model_no_route', 'research_checks.verdict.model_no_route'),
                 'unresolved/AT_ISSUE_FAILURE': ('attempts.unresolved.AT_ISSUE_FAILURE',
                                                 'research_checks.unresolved.AT_ISSUE_FAILURE'),
                 'unresolved/TIMEOUT': ('attempts.unresolved.TIMEOUT', 'research_checks.unresolved.TIMEOUT')}
        if set(e['verdicts']) - set(known):
            raise SystemExit(f'{sc}: INDEX.json verdict keys {sorted(set(e["verdicts"]) - set(known))} are not reconciled')
        if g('attempts.unresolved.other')['value'] or g('research_checks.unresolved.other')['value']:
            raise SystemExit(f'{sc}: unresolved checks without a known reason_code are not reconciled')
        for name, (disp, res) in known.items():
            row['verdicts'][name] = (e['verdicts'].get(name, 0), g(disp)['value'], g(res)['value'])
        # the identities the README table shows: they must hold exactly
        assert row['index_origins'] == row['cases'] + row['research_origins'], row
        assert row['index_checks'] == row['dispatch'] + row['rechecks'] + row['research_checks'], row
        assert all(i == d + r for i, d, r in row['verdicts'].values()), row
        assert sum(i for i, _, _ in row['verdicts'].values()) == row['index_checks'] - row['rechecks'], row
        rows.append(row)
    return rows


def readme_blocks(result: dict, nums: dict) -> dict[str, str]:
    H = nums
    rows = ['| Key (NUMBERS.json) | Value | Meaning (short; full definition in NUMBERS.json) |', '|---|---:|---|']
    ua, yd = 'Uiseong-Andong', 'Yeongdeok'
    short = {
        'records.route_checks@all/pooled': 'route-check records in the six cache files (incl. re-checks)',
        'records.rechecks@all/pooled': 're-checks of timed-out checks among them',
        'attempts@all/pooled': 'route checks behind the cases (place x forecast time x candidate destination x departure)',
        'places@all/places': 'distinct OSM-mapped villages/hamlets + care facilities checked (both regions)',
        'osm_origins_not_checkable@all/places': 'listed OSM villages with no road node within 2 km (never checked)',
        'cases@all/pooled': 'place-forecast-time cases (each place once per recorded forecast time)',
        'cell.checked_route.offset_0000s@all/pooled': 'cases with a checked route for departure at the forecast time',
        'no_checked_route_any_offset@all/pooled': 'cases with no checked route at any departure time',
        'best_verdict.model_no_route@all/pooled': 'of those, model_no_route at every attempt (no route within the model)',
        'best_verdict.unresolved@all/pooled': 'of those, >= 1 unresolved attempt (cannot judge, never safe)',
        'no_checked_route_any_offset.trip_fits_at_offset_0000s@all/pooled':
            'of those, a fire-free trip fits the window at +0 min (the window does not explain them)',
        'not_checked_although_fits.offset_0000s@uiseong_andong_2025/pooled':
            f'{ua}, departure at +0 min: no checked route although a fire-free trip fits the window',
        'not_checked_although_fits.offset_1800s@uiseong_andong_2025/pooled': f'same, {ua}, +30 min',
        'not_checked_although_fits.offset_2400s@uiseong_andong_2025/pooled': f'same, {ua}, +40 min',
        'not_checked_although_fits.offset_3000s@uiseong_andong_2025/pooled': f'same, {ua}, +50 min (only trips <= 480 s fit)',
        'not_checked_although_fits.offset_0000s@yeongdeok_2025/pooled': f'same, {yd}, +0 min',
        'not_checked_although_fits.offset_1800s@yeongdeok_2025/pooled': f'same, {yd}, +30 min',
        'window_limited_among_not_checked.offset_3000s@all/pooled':
            'cases without a checked route at +50 min that are window-limited (none possible whatever the fire)',
        'window_limited_among_not_checked.offset_3000s@uiseong_andong_2025/pooled': f'same, {ua}',
        'deadline_set_by.window@all/pooled': 'deadlines before +50 min set by the 1-hour window (next departure cannot fit)',
        'deadline_set_by.fire_or_limits@all/pooled': 'deadlines before +50 min set by fire scenarios or limits (next would fit)',
        'places.not_checked_although_fits_any_offset_any_input@all/places':
            'places with an unchecked departure that would fit the window, in >= 1 forecast time',
        'places.not_checked_although_fits_at_offset_3000s_any_input@all/places':
            'of the places unchecked at +50 min in >= 1 forecast time, those where +50 min would fit',
        'fastest_trip_s.median@uiseong_andong_2025/places#village':
            f'fastest fire-free trip to the nearest candidate, {ua} villages, median (s)',
        'fastest_trip_s.median@yeongdeok_2025/places#village': f'same, {yd} villages, median (s)',
        'fastest_trip_s.min@all/places#care_facility': 'same, care facilities, min (s)',
        'fastest_trip_s.max@all/places#care_facility': 'same, care facilities, max (s)',
        'trip_model.equals_travel_only@all/pooled': 'fire-free trip model = API travel-only route time (validation)',
        'api_check.recorded_equals_planner_rule_on_original@all/pooled': 'API recorded fields = planner rules on original attempts',
        'api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled': 'planner-displayed deadline = API latest_checked_depart_offset_s',
        'api_check.displayed_differs_explained_by_recheck@all/pooled': 'displayed differences explained by re-checks',
        'travel_only.fastest_meets_flames@all/pooled': 'fastest (travel-time-only) routes with predicted flame contact, at the leave-by time',
        'travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s': 'same, leave-by deadline before +50 min',
        'travel_only.fastest_meets_flames@all/pooled#leave_by_3000s': 'same, leave-by deadline +50 min',
        'travel_only.clear_pairs_equal_arrival@all/pooled': 'other comparisons: checked route arrives at the same second',
        'travel_only.extra_arrival_s.min@all/pooled': 'extra arrival time of the checked alternative, min (s)',
        'travel_only.extra_arrival_s.median@all/pooled': 'extra arrival time, median (s)',
        'travel_only.extra_arrival_s.max@all/pooled': 'extra arrival time, max (s)',
        'travel_only.extra_length_m.min@all/pooled': 'extra route length, min (m)',
        'travel_only.extra_length_m.median@all/pooled': 'extra route length, median (m)',
        'travel_only.extra_length_m.max@all/pooled': 'extra route length, max (m)',
        'redundancy.turn_aware_paths_1@all/places': 'places whose routes all pass through >= 1 common road segment',
        'redundancy.single_cut_at_entry_node@all/places': 'of those, the first common segment leaves the entry point',
        'redundancy.turn_aware_equals_plain@all/places': 'turn-aware count = count ignoring turn restrictions',
        'redundancy.shared_stretch_m.median@all/places': 'entry point to the end of the last common segment, median (m)',
        'redundancy.shared_stretch_within_100m@all/places': 'of those, the common segments end within 100 m',
    }
    assert set(short) == set(numbers_mod.HEADLINE_KEYS), set(short) ^ set(numbers_mod.HEADLINE_KEYS)
    for k in numbers_mod.HEADLINE_KEYS:
        e = H[k]
        val = _frac(e) if e['denominator'] else (f'{e["value"]:,}' if isinstance(e['value'], int) else f'{e["value"]}')
        if 'n' in e:
            val += f' (n = {e["n"]})'
        rows.append(f'| `{k}` | {val} | {short[k]} |')
    headline = '\n'.join(rows)

    def nd(e):
        return f'{e["numerator"]}/{e["denominator"]}'
    by = ['| Region | Forecast time | Cases | Checked at +0 min | Checked at +50 min | Window-limited at +50 min | '
          'No checked route although a fire-free trip fits: +0 · +30 · +50 min | No checked route at any departure '
          '(model_no_route + unresolved) | Deadline before +50 min: set by window + by fire/limits | Fastest route '
          'meets predicted flames |',
          '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']

    def by_row(sc, region_label, time_label):
        g = lambda k: H[f'{k}@{sc}']  # noqa: E731
        nr, un = g('best_verdict.model_no_route')['numerator'], g('best_verdict.unresolved')['numerator']
        fits = ' · '.join(nd(g(f'not_checked_although_fits.offset_{t:04d}s')) for t in (0, 1800, 3000))
        return (f'| {region_label} | {time_label} | {g("cases")["value"]} | {_frac(g("cell.checked_route.offset_0000s"))} | '
                f'{_frac(g("cell.checked_route.offset_3000s"))} | {_frac(g("window_limited.offset_3000s"))} | {fits} | '
                f'{nr} + {un} | {g("deadline_set_by.window")["numerator"]} + {g("deadline_set_by.fire_or_limits")["numerator"]} | '
                f'{_frac(g("travel_only.fastest_meets_flames"))} |')
    for m in result['metas']:
        by.append(by_row(m['scope'], sources.REGION_NAMES[m['region']], f'{m["input_kst"]} ({m["input_time"]})'))
    for sc, name in [(f'{r}/pooled', '**' + sources.REGION_NAMES[r] + ', 3 forecast times**') for r in sources.REGIONS] + \
            [('all/pooled', '**Both regions, 6 forecast times**')]:
        by.append(by_row(sc, name, 'pooled cases'))
    by_scope = '\n'.join(by)

    dl = ['| Subset | Cases | +10 | +20 | +30 | +40 | +50 (last checked; may be later) | none: model_no_route | none: unresolved |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for sc, label in [('uiseong_andong_2025/pooled#village', 'Uiseong-Andong villages'),
                      ('uiseong_andong_2025/pooled#care_facility', 'Uiseong-Andong care facilities'),
                      ('yeongdeok_2025/pooled#village', 'Yeongdeok villages')]:
        g = lambda k: H[f'{k}@{sc}']  # noqa: E731
        assert g('deadline.latest_0000s')['numerator'] == 0
        cells = [f'{g(f"deadline.latest_{t:04d}s")["numerator"]} ({g(f"deadline.latest_{t:04d}s.set_by_window")["numerator"]})'
                 for t in sources.GRID_OFFSETS_S[1:-1]]
        cells.append(str(g(f'deadline.latest_{sources.GRID_OFFSETS_S[-1]:04d}s')['numerator']))
        dl.append(f'| {label} | {g("cases")["value"]} | ' + ' | '.join(cells) +
                  f' | {g("deadline.none_model_no_route")["numerator"]} | {g("deadline.none_unresolved")["numerator"]} |')
    a_w, a_f = H['deadline_set_by.window@all/pooled'], H['deadline_set_by.fire_or_limits@all/pooled']
    deadlines = '\n'.join(dl) + (
        f'\n\nIn parentheses: deadlines set by the 1-hour window (`deadline.latest_<t>s.set_by_window@*`): at the next '
        f'departure even the fastest fire-free trip plus the 120 s stay would end after the window. Overall '
        f'{a_w["numerator"]} of the {a_w["denominator"]} deadlines before +50 min are set by the window and '
        f'{a_f["numerator"]} by the fire scenarios or model limits (`deadline_set_by.*@all/pooled`). No case had its last '
        'checked departure at +0 min (`deadline.latest_0000s@*` = 0). Yeongdeok has no care facility in the OSM extract.')

    rd = ['| Subset | Places | 1 path | 2 paths | 3 paths | >= 4 | 1 path, first common segment at the entry point |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for sc, label in [('uiseong_andong_2025/places#village', 'Uiseong-Andong villages'),
                      ('uiseong_andong_2025/places#care_facility', 'Uiseong-Andong care facilities'),
                      ('yeongdeok_2025/places#village', 'Yeongdeok villages'), ('all/places', 'All checked places')]:
        g = lambda k: H[f'{k}@{sc}']  # noqa: E731
        rd.append(f'| {label} | {g("redundancy.places")["value"]} | ' +
                  ' | '.join(str(g(f'redundancy.turn_aware_paths_{k}')['numerator']) for k in (1, 2, 3, '4plus')) +
                  f' | {g("redundancy.single_cut_at_entry_node")["numerator"]}/{g("redundancy.single_cut_at_entry_node")["denominator"]} |')
    rd += ['', '| Region | Places with 1 path | Entry point to the end of the last common segment: median (min - max) | '
           'Ends within 100 m |', '|---|---:|---:|---:|']
    for reg, label in [(r, sources.REGION_NAMES[r]) for r in sources.REGIONS] + [('all', 'Both regions')]:
        g = lambda k: H[f'{k}@{reg}/places']  # noqa: E731
        rd.append(f'| {label} | {g("redundancy.shared_stretch_m.median")["n"]} | '
                  f'{g("redundancy.shared_stretch_m.median")["value"]:,} m ({g("redundancy.shared_stretch_m.min")["value"]:,} - '
                  f'{g("redundancy.shared_stretch_m.max")["value"]:,} m) | {_frac(g("redundancy.shared_stretch_within_100m"))} |')
    x1, x2 = H['redundancy_x.no_checked_route_at_offset_0000s@all/pooled#rc1'], H['redundancy_x.no_checked_route_at_offset_0000s@all/pooled#rc2plus']
    redundancy = '\n'.join(rd) + (
        f'\n\nDescriptive only (no causal or statistical claim): no checked route at +0 min in {_frac(x1)} cases of '
        f'single-path places versus {_frac(x2)} of places with at least two paths (keys '
        '`redundancy_x.*@all/pooled#rc1|rc2plus`). Later departures are not compared here because the window, not the '
        'road network, dominates them.')

    cc = ['| Scenario set | Origins | Recorded = API rule on original attempts | Recorded = planner rules on original attempts | '
          'Displayed = recorded: latest / contiguous / best verdict | Origins with re-checked attempts | Differences explained by re-checks |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for sc in [m['scope'] for m in result['metas']] + ['all/pooled']:
        g = lambda k: H[f'{k}@{sc}']  # noqa: E731
        ex = g('api_check.displayed_differs_explained_by_recheck')
        cc.append(f'| {sc} | {g("cases")["value"]} | {g("api_check.recorded_equals_api_rule_on_original")["numerator"]} | '
                  f'{g("api_check.recorded_equals_planner_rule_on_original")["numerator"]} | '
                  f'{g("api_check.displayed_equals_recorded.latest_checked_depart_offset_s")["numerator"]} / '
                  f'{g("api_check.displayed_equals_recorded.latest_contiguous_checked_depart_offset_s")["numerator"]} / '
                  f'{g("api_check.displayed_equals_recorded.best_verdict")["numerator"]} | '
                  f'{g("api_check.origins_with_rechecked_attempts")["value"]} | {ex["numerator"]}/{ex["denominator"]} |')
    crosscheck = '\n'.join(cc)
    scopes = ['| Scope key | Cache file | SHA-256 | Scenario set | Hazard SHA-256 | Graph SHA-256 | Host | Created |',
              '|---|---|---|---|---|---|---|---|']
    for m in result['metas']:
        scopes.append(f'| {m["scope"]} | `{m["cache_file"]}` | `{m["cache_sha256"][:16]}…` | `{m["scenario_set_id"]}` | '
                      f'`{m["hazard_sha256"][:16]}…` | `{m["graph_sha256"][:16]}…` | '
                      f'{m["host"][0]["platform"]} ({m["host"][0]["results"]} results) | {m["created_at"]} |')

    # per origin type: survival curve and check-level verdicts (P4F-05)
    subsets = [('uiseong_andong_2025/pooled#village', 'Uiseong-Andong villages'),
               ('uiseong_andong_2025/pooled#care_facility', 'Uiseong-Andong care facilities'),
               ('yeongdeok_2025/pooled#village', 'Yeongdeok villages'), ('all/pooled', 'All cases (both regions)')]
    grid = sources.GRID_OFFSETS_S
    sv = ['| Subset | Cases | ' + ' | '.join(f'Checked route at +{t // 60} min' for t in grid) + ' |',
          '|---|---:|' + '---:|' * len(grid)]
    ck = ['| Subset | Route checks | checked_route | model_no_route | unresolved | unresolved by API reason: '
          'AT_ISSUE_FAILURE · TIMEOUT · other |', '|---|---:|---:|---:|---:|---:|']
    for sc, label in subsets:
        g = lambda k: H[f'{k}@{sc}']  # noqa: E731
        assert g('contiguous_differs_from_latest')['value'] == 0
        sv.append(f'| {label} | {g("cases")["value"]} | ' +
                  ' | '.join(_frac(g(f'cell.checked_route.offset_{t:04d}s')) for t in grid) + ' |')
        ck.append(f'| {label} | {g("attempts")["value"]:,} | ' +
                  ' | '.join(_frac(g(f'attempts.verdict.{v}')) for v in ('checked_route', 'model_no_route', 'unresolved')) +
                  ' | ' + ' · '.join(f'{g(f"attempts.unresolved.{c}")["numerator"]:,}' for c in ('AT_ISSUE_FAILURE', 'TIMEOUT', 'other'))
                  + ' |')
    by_type = '\n'.join(sv) + '\n\n' + '\n'.join(ck) + (
        '\n\nPer-type keys: `cell.<verdict>.offset_<t>s@<scope>#village|care_facility` (every verdict at every departure) '
        'and `attempts.verdict.*@<scope>#<type>`. No case has a gap in its checked departures '
        '(`contiguous_differs_from_latest@*` = 0 for every scope and type), so the share with a checked route at +t min '
        'equals the share whose leave-by deadline is +t min or later. A route check is one attempt (place x forecast '
        'time x candidate destination x departure) as the planner displays it; a case counts as checked at a departure '
        'if any of its three candidate destinations is.')

    # reconciliation with planner/cache/INDEX.json (P4F-06) and the travel_only records (P4F-04)
    rec = index_reconciliation(result, nums)
    ix = ['| Scenario set | Origins: INDEX = cases + research origins | Checks: INDEX = dispatch attempts + re-checks + '
          'research checks | checked_route: INDEX = displayed + research | model_no_route: INDEX = displayed + research | '
          'unresolved AT_ISSUE_FAILURE: INDEX = displayed + research | unresolved TIMEOUT: INDEX = displayed + research | '
          'travel_only records (not in INDEX) |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    tot = {'o': [0, 0, 0], 'c': [0, 0, 0, 0], 't': 0, 'v': {k: [0, 0, 0] for k in rec[0]['verdicts']}}
    for r in rec:
        ix.append(f'| {r["scope"]} | {r["index_origins"]} = {r["cases"]} + {r["research_origins"]} | '
                  f'{r["index_checks"]:,} = {r["dispatch"]:,} + {r["rechecks"]} + {r["research_checks"]} | ' +
                  ' | '.join(f'{i:,} = {d:,} + {s}' for i, d, s in r['verdicts'].values()) + f' | {r["travel_only"]} |')
        for i, x in enumerate((r['index_origins'], r['cases'], r['research_origins'])):
            tot['o'][i] += x
        for i, x in enumerate((r['index_checks'], r['dispatch'], r['rechecks'], r['research_checks'])):
            tot['c'][i] += x
        tot['t'] += r['travel_only']
        for k, v in r['verdicts'].items():
            for i, x in enumerate(v):
                tot['v'][k][i] += x
    a = 'all/pooled'
    assert (tot['o'][1], tot['o'][2], tot['c'][1], tot['c'][2], tot['c'][3], tot['t']) == (
        H[f'cases@{a}']['value'], H[f'research_origins@{a}']['value'], H[f'records.dispatch_attempts@{a}']['value'],
        H[f'records.rechecks@{a}']['value'], H[f'records.research_route_checks@{a}']['value'],
        H[f'records.travel_only@{a}']['value'])
    ix.append(f'| **all six** | {tot["o"][0]} = {tot["o"][1]} + {tot["o"][2]} | {tot["c"][0]:,} = {tot["c"][1]:,} + '
              f'{tot["c"][2]} + {tot["c"][3]} | ' + ' | '.join(f'{i:,} = {d:,} + {s}' for i, d, s in tot['v'].values()) +
              f' | {tot["t"]} |')
    t_np, t_res = H[f'travel_only.records_not_paired@{a}'], H[f'travel_only.records_not_paired.research_origin@{a}']
    t_fl, t_pairs = H[f'travel_only.records_not_paired.fastest_meets_flames@{a}'], H[f'travel_only.pairs@{a}']
    assert t_pairs['numerator'] + t_np['numerator'] == t_np['denominator'] == tot['t']
    assert t_pairs['numerator'] == t_pairs['denominator'] and t_res['numerator'] == t_res['denominator']   # "all"
    to_ex = H['attempts.unresolved.TIMEOUT@yeongdeok_2025/20250325T190000Z']['numerator']
    to_res = H['research_checks.unresolved.TIMEOUT@yeongdeok_2025/20250325T190000Z']['numerator']
    index = '\n'.join(ix) + (
        '\n\n`planner/cache/INDEX.json` is written by `planner/scripts/precompute.py`. Per cache file it counts '
        '**origins** = the OSM origins sent in dispatch plans plus the recorded research-mission origins; **checks** = '
        'every stored route-check record (dispatch attempts, re-checks of timed-out attempts and research-origin checks; '
        'the travel_only comparison checks are not counted); **verdicts** = the verdict (and reason code) of every stored '
        'check except an original that was re-checked (its re-check counts instead), i.e. the dispatch attempts as the '
        'planner displays them plus the research-origin checks. Every identity in the table holds exactly (the INDEX '
        f'verdicts add up to the checks minus the {H[f"records.rechecks@{a}"]["value"]} re-checked originals; '
        '`tests/test_cache_only.py` asserts it from INDEX.json). This package\'s village/care-facility numbers leave the '
        f'research origins and their checks out: for example INDEX lists {to_ex + to_res} TIMEOUT verdicts for '
        f'yeongdeok_2025/20250325T190000Z, of which {to_ex} are displayed dispatch attempts '
        f'(`attempts.unresolved.TIMEOUT@yeongdeok_2025/20250325T190000Z`) and {to_res} research-origin checks.\n\n'
        f'**travel_only records.** The cache files store {t_np["denominator"]} travel_only comparison checks '
        f'(`records.travel_only@all/pooled`): the {t_pairs["numerator"]} comparisons paired with village/care-facility '
        f'cases (`travel_only.pairs@all/pooled`, one per case with a checked route) and {t_np["numerator"]} records that '
        'are not paired (`travel_only.records_not_paired@all/pooled`), all of recorded research-mission origins '
        f'({t_res["numerator"]} of {t_res["denominator"]}), which are left out like every research-origin result; '
        f'{t_fl["numerator"]} of those {t_fl["denominator"]} {"has" if t_fl["numerator"] == 1 else "have"} predicted '
        'flame contact (`travel_only.records_not_paired.fastest_meets_flames@all/pooled`).')
    return {'headline': headline, 'by-scenario': by_scope, 'deadlines': deadlines, 'redundancy': redundancy,
            'crosscheck': crosscheck, 'inputs': '\n'.join(scopes), 'by-type': by_type, 'index': index}



def fill_readme(text: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        begin, end = f'<!-- BEGIN GENERATED: {name} -->', f'<!-- END GENERATED: {name} -->'
        i, j = text.find(begin), text.find(end)
        if i < 0 or j < i:
            raise SystemExit(f'README.md lacks the markers for block {name!r}')
        text = text[:i + len(begin)] + '\n' + body + '\n' + text[j:]
    return text


# ------------------------------------------------------------------------------------------------ main

def build_outputs(result: dict) -> tuple[dict, dict[str, str]]:
    if any(m['tie_breaks'] for m in result['metas']):
        raise SystemExit('equal-arrival ties among checked attempts: the localeCompare tie-break would matter')
    nums = numbers_mod.build(result)
    doc = numbers_document(result, nums)
    texts = {'NUMBERS.json': json.dumps(doc, ensure_ascii=False, indent=1) + '\n',
             'APPLICATION_SENTENCES.md': sentences.markdown(nums) + '\n'}
    for name, rows in table_rows(result).items():
        texts[f'tables/{name}'] = _csv_text(rows)
    readme = (HERE / 'README.md').read_text(encoding='utf-8')
    texts['README.md'] = fill_readme(readme, readme_blocks(result, nums))
    return nums, texts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='recompute and compare with the committed text outputs')
    ap.add_argument('--no-figures', action='store_true')
    a = ap.parse_args()
    result = analysis.run(with_graphs=True)
    nums, texts = build_outputs(result)
    if a.check:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            drawn = figures.draw_all(result, nums, Path(td), Path(td))      # the figures and their CSV twins
            for p in sorted(Path(td).glob('*.csv')):
                texts[f'tables/{p.name}'] = p.read_text(encoding='utf-8')
            bad = [name for name, body in texts.items()
                   if not (HERE / name).is_file() or (HERE / name).read_text(encoding='utf-8') != body]
            bad += [f'figures/{p.name}' for p in drawn if not figures.same_figure(p, HERE / 'figures' / p.name)]
        if bad:
            print('OUT OF DATE: ' + ', '.join(bad))
            return 1
        print(f'OK: {len(texts)} committed text outputs and {len(drawn)} figure files (SVG bytes, PNG pixels) reproduce '
              f'exactly ({len(nums)} numbers)')
        return 0
    for name, body in texts.items():
        (HERE / name).parent.mkdir(parents=True, exist_ok=True)
        (HERE / name).write_text(body, encoding='utf-8')
    if not a.no_figures:
        figures.draw_all(result, nums, HERE / 'figures', HERE / 'tables')
    print(f'wrote {len(nums)} numbers ({len(numbers_mod.HEADLINE_KEYS)} headline) and {len(texts)} text outputs')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
