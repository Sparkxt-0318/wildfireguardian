"""Path A: every reported number, with its definition, from the per-origin records of ``analysis.run``.

Key format: ``<metric>@<scope>[#<subset>]``.
* scope ``<region>/<YYYYMMDDTHHMMSSZ>`` - one recorded scenario set (one cache file);
* scope ``<region>/pooled`` and ``all/pooled`` - place-input-time CASES pooled over the recorded input times. The
  same place appears once per input time (three different scenario sets for the same places), so pooled counts are
  cases, never places;
* scope ``<region>/places`` and ``all/places`` - distinct places (no double counting across input times);
* subset ``#village`` / ``#care_facility`` - origin type as the planner tags it (LeftPanel.tsx glyphKind);
  ``#rc1`` / ``#rc2plus`` - places with one / at least two turn-aware edge-disjoint paths.

Population ("origins") unless stated otherwise: OpenStreetMap villages/hamlets and care facilities
(``nursing_home`` / ``social_facility``) with an accepted road entry node within 2 km, i.e. the origins the planner
sent to the Route-Check API. The 3 OSM villages without such a node (never checked; shown by the planner as
unresolved "도로망 2 km 밖 — 점검 불가") and the 8 recorded research-mission origins are excluded and reported
separately.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from . import planner_rules as pr, sources

OSM_TYPES = ('village', 'care_facility')
OFFSETS = sources.GRID_OFFSETS_S
LAST = OFFSETS[-1]
SCRIPT = 'research/solve2027-impact/compute.py'
CELL_CATS = (pr.CHECKED, pr.NO_ROUTE, pr.UNRESOLVED, pr.WINDOW_UNSATISFIABLE)
DEADLINE_CATS = tuple(f'latest_{t:04d}s' for t in OFFSETS) + ('none_model_no_route', 'none_unresolved')

POP = ('checked OSM origins (villages/hamlets + care facilities with an accepted road entry node within 2 km; '
       'research-mission origins and the 3 not-checkable villages excluded)')
CELL_RULE = ('the cell verdict at a departure offset follows the planner (planner/src/domain/plan.ts combineVerdicts, '
             'lines 106-111): checked_route if ANY of the origin\'s candidate destinations has a checked route, '
             'model_no_route only if EVERY attempted destination is model_no_route, otherwise unresolved; '
             're-checks replace the attempt they re-ran (planner/src/api/cache.ts lines 120-145)')
DEADLINE_RULE = ('leave-by deadline (출발 마감) = the latest departure offset whose cell is checked_route '
                 '(plan.ts latestSafeDeparture, lines 155-161); offsets are 0, 600, ..., 3000 s after the recorded '
                 'input time; unresolved cells never count')


def _scope_text(scope: str, metas: dict) -> str:
    if scope.endswith('/places'):
        reg = scope.split('/')[0]
        return ('distinct places of ' + ('both 2025 regions' if reg == 'all' else sources.REGION_NAMES[reg]) +
                ' (each place counted once, whatever the number of recorded input times)')
    if scope.endswith('/pooled'):
        reg = scope.split('/')[0]
        n = 6 if reg == 'all' else 3
        return (f'{n} recorded scenario sets pooled as place-input-time cases ('
                + ('both regions' if reg == 'all' else sources.REGION_NAMES[reg]) +
                '); a place appears once per input time, so counts are cases, not places')
    m = metas[scope]
    return (f'{sources.REGION_NAMES[m["region"]]}, recorded input time {m["input_time"]} ({m["input_kst"]}), '
            f'scenario set {m["scenario_set_id"]} (4 members), cache file {m["cache_file"]}')


class Builder:
    def __init__(self, result: dict):
        self.metas = {m['scope']: m for m in result['metas']}
        self.inputs = {row['path']: row['sha256'] for row in sources.input_files_record(result['entries'], True)}
        self.numbers: dict[str, dict] = {}

    def scope_inputs(self, scope: str, graphs: bool = False) -> list[str]:
        reg = scope.split('/')[0]
        regions = sources.REGIONS if reg == 'all' else (reg,)
        files = ['planner/cache/INDEX.json']
        for m in self.metas.values():
            if m['region'] in regions and (scope.split('#')[0].endswith(('/pooled', '/places')) or m['scope'] == scope.split('#')[0]):
                files.append(m['cache_file'])
        files += [f'planner/public/data/regions/{r}/places.geojson' for r in regions]
        if graphs:
            files += [f'data/routing/graphs/{r}/graph.json' for r in regions]
        return files

    def add(self, key: str, value, definition: str, numerator=None, denominator=None, unit: str = 'count',
            graphs: bool = False, n: int | None = None):
        if key in self.numbers:
            raise KeyError(f'duplicate number {key}')
        metric, _, rest = key.partition('@')
        scope, _, subset = rest.partition('#')
        entry = {'value': value, 'unit': unit, 'numerator': numerator, 'denominator': denominator,
                 'definition': definition, 'scope': scope, 'subset': subset or None,
                 'scope_text': _scope_text(scope, self.metas), 'script': SCRIPT,
                 'inputs': self.scope_inputs(rest, graphs), 'uses_graph': graphs}
        if n is not None:
            entry['n'] = n
        if numerator is not None and denominator:
            entry['share'] = round(numerator / denominator, 4)
        self.numbers[key] = entry

    def frac(self, key, num, den, definition, **kw):
        self.add(key, num, definition, numerator=num, denominator=den, **kw)


SUBSET_TEXT = {'': '', 'village': ' Subset: villages/hamlets (vulnerable = false).',
               'care_facility': ' Subset: care facilities (nursing_home / social_facility, vulnerable = true).'}


def _sel(records, scope: str, subset: str = ''):
    reg, _, part = scope.partition('/')
    out = [r for r in records if r['origin_type'] in OSM_TYPES]
    if reg != 'all':
        out = [r for r in out if r['region'] == reg]
    if part not in ('pooled', 'places'):
        out = [r for r in out if r['scope'] == scope]
    if subset:
        out = [r for r in out if r['origin_type'] == subset]
    return out


def case_numbers(b: Builder, records: list[dict]):
    file_scopes = list(b.metas)
    scopes = file_scopes + [f'{r}/pooled' for r in sources.REGIONS] + ['all/pooled']
    for sc in scopes:
        for sub in ('', 'village', 'care_facility'):
            rows = _sel(records, sc, sub)
            if not rows:
                continue
            tag = f'@{sc}' + (f'#{sub}' if sub else '')
            n = len(rows)
            st = SUBSET_TEXT[sub]
            b.add('cases' + tag, n, f'Number of cases: {POP}, one per recorded scenario set.{st}')
            for v in pr.VERDICTS:
                k = sum(1 for r in rows if r['best_verdict'] == v)
                b.frac(f'best_verdict.{v}' + tag, k, n,
                       f'Cases whose overall verdict (planner bestVerdict = contract best_verdict over all attempts, '
                       f'plan.ts lines 106-111 / 204) is {v}. {CELL_RULE}.{st}')
            for cat in DEADLINE_CATS:
                k = sum(1 for r in rows if r['deadline_category'] == cat)
                if cat.startswith('latest_'):
                    t = int(cat[7:11])
                    d = (f'Cases whose {DEADLINE_RULE} is exactly {t} s (+{t // 60} min)' +
                         ('; at this last checked offset the 1-hour scenario window gives no later limit, so the '
                          'true limit may be later' if t == LAST else '; the next offset (+%d min) had no checked '
                          'route' % (t // 60 + 10)) + '.')
                else:
                    v = cat[5:]
                    d = (f'Cases with no checked route at any departure offset whose overall verdict is {v}'
                         + (' (every attempt model_no_route: no route within this model and input scope; not proof '
                            'that escape is impossible).' if v == pr.NO_ROUTE else
                            ' (at least one attempt unresolved: cannot judge; never safe, never a deadline).'))
                b.frac(f'deadline.{cat}' + tag, k, n, d + st)
            k0 = sum(1 for r in rows if r['cells'][0] != pr.CHECKED)
            b.frac('no_checked_route_at_offset_0000s' + tag, k0, n,
                   f'Cases whose cell at departure offset 0 s (the recorded input time) is not checked_route '
                   f'(model_no_route or unresolved). {CELL_RULE}.{st}')
            kw = sum(1 for r in rows if r['latest_s'] is not None and r['latest_s'] < LAST)
            b.frac('window_closes_within_hour' + tag, kw, n,
                   f'Cases with a checked route at some offset whose {DEADLINE_RULE} is before {LAST} s, i.e. the '
                   f'departure offsets with a checked route end inside the recorded 1-hour scenario window.{st}')
            kn = sum(1 for r in rows if r['latest_s'] is None)
            b.frac('no_checked_route_any_offset' + tag, kn, n,
                   'Cases with no checked route at any of the departure offsets (overall verdict model_no_route or '
                   f'unresolved; the sum of the two deadline.none_* counts).{st}')
            kl = sum(1 for r in rows if r['cells'][LAST] != pr.CHECKED)
            b.frac(f'not_checked_at_offset_{LAST:04d}s' + tag, kl, n,
                   f'Cases whose cell at the last departure offset ({LAST} s, +{LAST // 60} min) is not checked_route: '
                   f'the window closes within the hour or no checked route exists at all.{st}')
            if sub:
                continue
            for t in OFFSETS:
                for cat in CELL_CATS:
                    k = sum(1 for r in rows if r['cells'][t] == cat)
                    extra = (' window_unsatisfiable ("시간창 밖") = no request was sent because the recorded arrival '
                             'window cannot be met from this offset; it is never a verdict.' if cat == pr.WINDOW_UNSATISFIABLE else '')
                    b.frac(f'cell.{cat}.offset_{t:04d}s' + tag, k, n,
                           f'Cases whose cell at departure offset {t} s (+{t // 60} min after the input time) is '
                           f'{cat}. {CELL_RULE}.{extra}')
            kc = sum(1 for r in rows if r['latest_s'] is not None and r['contiguous_s'] != r['latest_s'])
            b.frac('contiguous_differs_from_latest' + tag, kc, sum(1 for r in rows if r['latest_s'] is not None),
                   'Cases with a checked route whose contiguous deadline (contract latest_contiguous_checked_depart_'
                   'offset_s; plan.ts contiguousSafeDeparture, lines 169-178) differs from the leave-by deadline. When '
                   'this is 0, the share checked at offset t equals the share whose deadline is at or after t.')
            att = [(r['scope'], r['origin_id'], k, v) for r in rows for k, v in r['unresolved_reasons'].items()]
            n_att = sum(r['n_attempts'] for r in rows)
            b.add('attempts' + tag, n_att,
                  'Route-check attempts behind these cases as the planner displays them (one per origin x candidate '
                  'destination x departure offset; a re-check replaces the attempt it re-ran).')
            reasons = Counter()
            for _, _, code, cnt in att:
                reasons[code] += cnt
            for code in ('AT_ISSUE_FAILURE', 'TIMEOUT'):
                b.frac(f'attempts.unresolved.{code}' + tag, reasons.get(code, 0), n_att,
                       f'Displayed attempts whose verdict is unresolved with API reason_code {code} '
                       + ('(api/README.md: "The limits were already exceeded at departure, for example because of '
                          'incurred dose"; dispatch requests carry no incurred dose).' if code == 'AT_ISSUE_FAILURE'
                          else '(the fixed 30 s request budget was exceeded).') + ' Unresolved is never safe.')
            other = sum(v for k, v in reasons.items() if k not in ('AT_ISSUE_FAILURE', 'TIMEOUT'))
            b.frac('attempts.unresolved.other' + tag, other, n_att,
                   'Displayed unresolved attempts with any other (or no) reason_code.')


def place_numbers(b: Builder, records: list[dict]):
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            rows = _sel(records, f'{reg}/places', sub)
            if not rows:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            by_place = defaultdict(list)
            for r in rows:
                by_place[(r['region'], r['origin_id'])].append(r)
            n = len(by_place)
            st = SUBSET_TEXT[sub]
            b.add('places' + tag, n, f'Distinct places: {POP}.{st}')
            k0 = sum(1 for rs in by_place.values() if any(r['cells'][0] != pr.CHECKED for r in rs))
            b.frac('places.no_checked_route_at_offset_0000s_any_input' + tag, k0, n,
                   'Distinct places whose cell at departure offset 0 s is not checked_route in at least one of the '
                   f'region\'s three recorded scenario sets. {CELL_RULE}.{st}')
            kl = sum(1 for rs in by_place.values() if any(r['cells'][LAST] != pr.CHECKED for r in rs))
            b.frac(f'places.not_checked_at_offset_{LAST:04d}s_any_input' + tag, kl, n,
                   f'Distinct places whose cell at the last departure offset ({LAST} s, +{LAST // 60} min) is not '
                   'checked_route in at least one of the region\'s three recorded scenario sets (the checked departure '
                   f'window closes within the hour, or there is no checked route at all).{st}')
            kw = sum(1 for rs in by_place.values() if any(r['latest_s'] is not None and r['latest_s'] < LAST for r in rs))
            b.frac('places.window_closes_within_hour_any_input' + tag, kw, n,
                   f'Distinct places with, in at least one recorded scenario set, a checked route whose {DEADLINE_RULE} '
                   f'is before {LAST} s.{st}')
            kn = sum(1 for rs in by_place.values() if any(r['latest_s'] is None for r in rs))
            b.frac('places.no_checked_route_any_offset_any_input' + tag, kn, n,
                   'Distinct places with no checked route at any departure offset in at least one recorded scenario '
                   f'set (overall verdict model_no_route or unresolved).{st}')


def scope_numbers(b: Builder, result: dict):
    metas = result['metas']
    for m in metas:
        tag = '@' + m['scope']
        b.add('records.route_checks' + tag, m['route_check_records'],
              'Route-check records stored in the cache file (dispatch attempts, research-origin checks and re-checks).')
        b.add('records.rechecks' + tag, m['recheck_records'],
              'Route-check records that are re-checks of an unresolved/TIMEOUT attempt (precompute '
              '--recheck-timeouts); the planner shows the re-check in place of the original.')
        b.add('records.travel_only' + tag, m['travel_only_records'],
              'travel_only comparison checks stored in the cache file (policy travel_only).')
        b.add('records.dispatch_attempts' + tag, m['dispatch_attempt_records'],
              'Route-check records created by the dispatch plans (one per origin x candidate destination x departure '
              'offset), excluding re-checks.')
        b.add('records.research_route_checks' + tag, m['research_route_check_records'],
              'Route-check records of the recorded research-mission origins (not villages or care facilities).')
    b.add('records.route_checks@all/pooled', sum(m['route_check_records'] for m in metas),
          'Route-check records stored in the six cache files (dispatch attempts, research-origin checks and '
          're-checks), all computed by the Route-Check API on the evaluated macOS (arm64) host.')
    b.add('records.rechecks@all/pooled', sum(m['recheck_records'] for m in metas),
          'Re-check records among them (each replaces one unresolved/TIMEOUT attempt in the planner view).')
    b.add('records.travel_only@all/pooled', sum(m['travel_only_records'] for m in metas),
          'travel_only comparison checks stored in the six cache files.')
    b.add('records.dispatch_attempts@all/pooled', sum(m['dispatch_attempt_records'] for m in metas),
          'Route-check records created by the dispatch plans of the six cache files (one per village/care-facility '
          'origin x candidate destination x departure offset), excluding re-checks.')
    b.add('records.research_route_checks@all/pooled', sum(m['research_route_check_records'] for m in metas),
          'Route-check records of the recorded research-mission origins in the six cache files.')
    places = {r: [pr.place_from_properties(p) for p in sources.load_places(r)] for r in sources.REGIONS}
    cats = {(r, p['id']): p['category'] for r in sources.REGIONS for p in places[r]}
    for reg in list(sources.REGIONS) + ['all']:
        used = {(m['region'], d) for m in metas if reg == 'all' or m['region'] == reg for d in m['destination_ids']}
        b.add(f'destinations_used@{reg}/places', len(used),
              'Distinct candidate destinations used by the dispatch plans (the 3 nearest OSM destinations per origin by '
              'straight line, with distinct road entry nodes; planner/scripts/precompute.py dispatch_requests).')
        for c in ('school', 'community_hall', 'shelter'):
            b.add(f'destinations_used.{c}@{reg}/places', sum(1 for x in used if cats[x] == c),
                  f'Of those, OSM places the planner categorises as {c} (places.geojson category). None is an official '
                  'evacuation shelter designation.')
    for reg in list(sources.REGIONS) + ['all']:
        ps = [p for r in (sources.REGIONS if reg == 'all' else (reg,)) for p in places[r] if p['role'] == 'origin']
        tag = f'@{reg}/places'
        b.add('osm_origins_listed' + tag, len(ps),
              'OSM origins the planner lists (role "origin" in places.geojson: place=village|hamlet, '
              'amenity=nursing_home|social_facility, social_facility=*), checkable or not.')
        b.add('osm_origins_not_checkable' + tag, sum(1 for p in ps if not p['checkable']),
              'Listed OSM origins with no accepted road node within 2 km (checkable = false): never sent to the API; '
              'the planner shows them as unresolved ("도로망 2 km 밖 — 점검 불가").')
        res = {(r['region'], r['origin_id']) for r in result['records'] if r['origin_type'] == 'research'}
        res = [x for x in res if reg == 'all' or x[0] == reg]
        b.add('research_origins' + tag, len(res),
              'Recorded research-mission origins (constructed benchmark requests, one per recorded mission); '
              'reported separately, not part of the village/care-facility numbers.')


def api_numbers(b: Builder, records: list[dict]):
    scopes = list(b.metas) + ['all/pooled']
    for sc in scopes:
        rows = _sel(records, sc)
        n = len(rows)
        tag = '@' + sc
        eq = lambda a, c: a == c  # noqa: E731
        b.frac('api_check.recorded_equals_api_rule_on_original' + tag,
               sum(1 for r in rows if eq(r['api']['recorded'], r['api']['api_rule_on_original'])), n,
               'Origins whose three recorded API fields (best_verdict, latest_checked_depart_offset_s, '
               'latest_contiguous_checked_depart_offset_s) equal api/dispatch.py origin_plan re-applied to the recorded '
               'attempts.')
        b.frac('api_check.recorded_equals_planner_rule_on_original' + tag,
               sum(1 for r in rows if eq(r['api']['recorded'], r['api']['planner_rule_on_original'])), n,
               'Origins whose three recorded API fields equal this package\'s port of the planner rules applied to the '
               'ORIGINAL attempts (re-checks not substituted).')
        for f, name in (('latest_s', 'latest_checked_depart_offset_s'), ('contiguous_s', 'latest_contiguous_checked_depart_offset_s'),
                        ('best_verdict', 'best_verdict')):
            b.frac(f'api_check.displayed_equals_recorded.{name}' + tag,
                   sum(1 for r in rows if r['api']['recorded'][f] == r['api']['planner_displayed'][f]), n,
                   f'Origins whose value as the planner displays it (re-checks substituted) equals the API\'s recorded '
                   f'{name}.')
        b.add('api_check.origins_with_rechecked_attempts' + tag, sum(1 for r in rows if r['n_rechecked_attempts']),
              'Origins with at least one attempt replaced by a re-check.')
        diff = [r for r in rows if r['api']['recorded'] != r['api']['planner_displayed']]
        b.frac('api_check.displayed_differs_explained_by_recheck' + tag,
               sum(1 for r in diff if r['n_rechecked_attempts'] and r['api']['recorded'] == r['api']['planner_rule_on_original']),
               len(diff), 'Origins whose displayed fields differ from the recorded API fields (denominator) that have '
               'at least one re-checked attempt and whose original attempts reproduce the recorded fields exactly '
               '(numerator).')


def travel_numbers(b: Builder, pairs: list[dict]):
    pdef = ('Travel-time-only comparison (cache travel_only, policy travel_only = fastest route ignoring fire): the '
            'same start, destination and departure offset as the origin\'s default checked route - the earliest-'
            'arriving checked attempt at its leave-by deadline (plan.ts bestCheckedAttempt / planFromAttempts). ')
    scopes = list(b.metas) + [f'{r}/pooled' for r in sources.REGIONS] + ['all/pooled']
    for sc in scopes:
        reg, _, part = sc.partition('/')
        rows = [p for p in pairs if (reg == 'all' or p['region'] == reg) and (part == 'pooled' or p['scope'] == sc)]
        tag = '@' + sc
        n = len(rows)
        comp = [p for p in rows if p['has_comparison'] and p['same_start_destination_offset']]
        b.frac('travel_only.pairs' + tag, len(comp), n,
               pdef + 'Numerator: cases with a checked route that have such a comparison; denominator: cases with a '
               'checked route.')
        flame = [p for p in comp if p['fastest_meets_flames']]
        b.frac('travel_only.fastest_meets_flames' + tag, len(flame), len(comp),
               pdef + 'Numerator: comparisons whose fastest route has predicted flame contact (exposure contact = true, '
                      'centre model) in at least one of the 4 scenario members.')
        clear = [p for p in comp if not p['fastest_meets_flames']]
        b.frac('travel_only.clear_pairs_equal_arrival' + tag, sum(1 for p in clear if p['extra_arrival_s'] == 0), len(clear),
               pdef + 'Comparisons without predicted flame contact on the fastest route (denominator) whose checked '
                      'route arrives at exactly the same second (numerator).')
        if sc == 'all/pooled':
            for k in (1, 2, 3, 4):
                b.frac(f'travel_only.fastest_contact_members_{k}' + tag, sum(1 for p in flame if p['fastest_contact_members'] == k),
                       len(flame), pdef + f'Flame-contact comparisons in which exactly {k} of the 4 scenario members show contact.')
            b.frac('travel_only.fastest_fails_full_policy' + tag, sum(1 for p in comp if p['fastest_passes_full_policy'] is False),
                   len(comp), pdef + 'Comparisons whose fastest route fails the API\'s full-policy assessment '
                   '(full_policy_assessment.passes_full_centre_and_contact = false).')
        if flame and sc in ('all/pooled', 'uiseong_andong_2025/pooled'):
            for stat, fn in (('min', min), ('median', statistics.median), ('max', max)):
                v = fn([p['extra_arrival_s'] for p in flame])
                if isinstance(v, float) and v.is_integer():          # an even-n median of whole seconds
                    v = int(v)
                b.add(f'travel_only.extra_arrival_s.{stat}' + tag, v,
                      pdef + f'{stat} over the flame-contact comparisons (field n) of (checked arrival - fastest-route '
                      'arrival), same departure.', unit='s', n=len(flame))
                v = fn([p['extra_length_m'] for p in flame])
                b.add(f'travel_only.extra_length_m.{stat}' + tag, round(v, 1),
                      pdef + f'{stat} over the flame-contact comparisons (field n) of (checked route length - fastest '
                      'route length); length = sum of straight edge chords u->v in EPSG:5179 metres on the routing graph, '
                      'rounded to 0.1 m.', unit='m', graphs=True, n=len(flame))
    flame_places = {(p['region'], p['origin_id']) for p in pairs if p.get('fastest_meets_flames')}
    b.frac('travel_only.places_fastest_meets_flames_any_input@all/places', len(flame_places),
           len({(p['region'], p['origin_id']) for p in pairs if p.get('has_comparison')}),
           pdef + 'Distinct places with a flame-contact comparison in at least one scenario set (numerator) among places '
                  'with at least one comparison (denominator).')


def redundancy_numbers(b: Builder, redundancy: list[dict], records: list[dict]):
    rdef = ('Road redundancy on the exact routing graph the API used (SHA-256 = input_hashes.graph of every cached '
            'route check): maximum number of walks from the origin\'s entry node (진입 지점) to any of its candidate '
            'destination nodes that share no directed road edge, ')
    ta = rdef + ('each obeying the graph\'s forbidden_turns as the routing kit does (turn-aware unit-capacity max-flow '
                 'on the node-split line graph).')
    pl = rdef + 'ignoring turn restrictions (unit-capacity max-flow on the plain directed graph).'
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            rows = [x for x in redundancy if x['origin_type'] in OSM_TYPES and (reg == 'all' or x['region'] == reg)
                    and (not sub or x['origin_type'] == sub)]
            if not rows:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            n = len(rows)
            st = SUBSET_TEXT[sub]
            b.add('redundancy.places' + tag, n, 'Distinct places with a redundancy value. ' + POP + st, graphs=True)
            for k in (1, 2, 3, '4plus'):
                f = (lambda v: v >= 4) if k == '4plus' else (lambda v, k=k: v == k)
                b.frac(f'redundancy.turn_aware_paths_{k}' + tag, sum(1 for x in rows if f(x['turn_aware_paths'])), n,
                       ta + f' Places whose value is {"at least 4" if k == "4plus" else k}.' + st, graphs=True)
                b.frac(f'redundancy.plain_paths_{k}' + tag, sum(1 for x in rows if f(x['plain_paths'])), n,
                       pl + f' Places whose value is {"at least 4" if k == "4plus" else k}.' + st, graphs=True)
            b.frac('redundancy.zero_paths' + tag, sum(1 for x in rows if x['turn_aware_paths'] == 0), n,
                   ta + ' Places with no legal walk at all (would be a road-network disconnection).' + st, graphs=True)
            b.frac('redundancy.turn_aware_equals_plain' + tag, sum(1 for x in rows if x['turn_aware_paths'] == x['plain_paths']),
                   n, 'Places whose turn-aware and plain values are equal.' + st, graphs=True)
            single = [x for x in rows if x['turn_aware_paths'] == 1]
            b.frac('redundancy.single_cut_at_entry_node' + tag, sum(1 for x in single if x['cut_at_entry_node']), len(single),
                   ta + ' Among places with value 1 (denominator): those whose single bottleneck edge (source-side minimum '
                   'cut) leaves the entry node itself (numerator).' + st, graphs=True)
            b.frac('redundancy.entry_out_degree_1' + tag, sum(1 for x in rows if x['entry_out_degree'] == 1), n,
                   'Places whose entry node has exactly one outgoing directed road edge in the routing graph.' + st, graphs=True)
    val = {(x['region'], x['origin_id']): x['turn_aware_paths'] for x in redundancy}
    cases = [r for r in records if r['origin_type'] in OSM_TYPES]
    for cls, f in (('rc1', lambda v: v == 1), ('rc2plus', lambda v: v >= 2)):
        rows = [r for r in cases if f(val[(r['region'], r['origin_id'])])]
        tag = f'@all/pooled#{cls}'
        d = ('Descriptive cross-tabulation only (no causal or statistical claim): cases of places whose turn-aware '
             f'redundancy value is {"1" if cls == "rc1" else "at least 2"}')
        b.add('redundancy_x.cases' + tag, len(rows), d + '.', graphs=True)
        b.frac('redundancy_x.no_checked_route_at_offset_0000s' + tag, sum(1 for r in rows if r['cells'][0] != pr.CHECKED),
               len(rows), d + '; numerator: cases whose cell at offset 0 s is not checked_route.', graphs=True)
        b.frac(f'redundancy_x.not_checked_at_offset_{LAST:04d}s' + tag, sum(1 for r in rows if r['cells'][LAST] != pr.CHECKED),
               len(rows), d + f'; numerator: cases whose cell at offset {LAST} s is not checked_route.', graphs=True)


HEADLINE_KEYS = (
    'records.route_checks@all/pooled', 'records.rechecks@all/pooled',
    'places@all/places', 'osm_origins_not_checkable@all/places', 'cases@all/pooled',
    'cell.checked_route.offset_0000s@all/pooled', 'cell.checked_route.offset_3000s@all/pooled',
    'cell.checked_route.offset_0000s@uiseong_andong_2025/pooled', 'cell.checked_route.offset_3000s@uiseong_andong_2025/pooled',
    'cell.checked_route.offset_0000s@yeongdeok_2025/pooled', 'cell.checked_route.offset_3000s@yeongdeok_2025/pooled',
    'no_checked_route_at_offset_0000s@all/pooled', 'no_checked_route_any_offset@all/pooled', 'attempts@all/pooled',
    'best_verdict.model_no_route@all/pooled', 'best_verdict.unresolved@all/pooled',
    'window_closes_within_hour@all/pooled', 'window_closes_within_hour@uiseong_andong_2025/pooled',
    'places.no_checked_route_at_offset_0000s_any_input@all/places', 'places.not_checked_at_offset_3000s_any_input@all/places',
    'deadline.latest_3000s@all/pooled#care_facility',
    'api_check.recorded_equals_planner_rule_on_original@all/pooled',
    'api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled',
    'api_check.displayed_differs_explained_by_recheck@all/pooled',
    'travel_only.fastest_meets_flames@all/pooled', 'travel_only.fastest_meets_flames@uiseong_andong_2025/pooled',
    'travel_only.clear_pairs_equal_arrival@all/pooled',
    'travel_only.extra_arrival_s.min@all/pooled', 'travel_only.extra_arrival_s.median@all/pooled',
    'travel_only.extra_arrival_s.max@all/pooled',
    'travel_only.extra_length_m.min@all/pooled', 'travel_only.extra_length_m.median@all/pooled',
    'travel_only.extra_length_m.max@all/pooled',
    'redundancy.turn_aware_paths_1@all/places', 'redundancy.single_cut_at_entry_node@all/places',
    'redundancy.turn_aware_equals_plain@all/places',
)


def build(result: dict) -> dict:
    b = Builder(result)
    records = result['records']
    scope_numbers(b, result)
    case_numbers(b, records)
    place_numbers(b, records)
    api_numbers(b, records)
    travel_numbers(b, result['pairs'])
    redundancy_numbers(b, result['redundancy'], records)
    for key in HEADLINE_KEYS:                        # fully self-contained provenance on every headline number
        e = b.numbers[key]
        e['headline'] = True
        e['input_sha256'] = {p: b.inputs[p] for p in e['inputs']}
    return b.numbers
