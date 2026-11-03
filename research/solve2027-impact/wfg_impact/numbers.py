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

Sources, flagged on every number: ``uses_graph`` false = an aggregate of recorded inputs only (Route-Check API results
in the planner cache, computed on the evaluated macOS arm64 host, and the planner's place files), counted here with the
planner's rules; ``uses_graph`` true = the number also depends on this package's own computation on the SHA-verified
road graph (fire-free trip times, the scenario-window classification, road redundancy, route lengths), and
``uses_hazard`` true = also on the recorded HAZARD packets (scenario window ``valid_from``/``valid_until``, time step
``dt``). Those computations are not Route-Check API results and not evaluated-host output (SOURCE_COMPUTED).
Planner line numbers cited below refer to repository commit 0cd95db2 (``PLANNER_LINES_COMMIT``).
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
PLANNER_LINES_COMMIT = '0cd95db2'      # the planner line numbers cited in definitions are those of this commit
AT = f'at commit {PLANNER_LINES_COMMIT}'
CELL_RULE = ('The cell verdict at a departure offset follows the planner (planner/src/domain/plan.ts combineVerdicts, '
             f'lines 106-111 {AT}): checked_route if ANY of the origin\'s candidate destinations has a checked route, '
             'model_no_route only if EVERY attempted destination is model_no_route, otherwise unresolved; '
             f're-checks replace the attempt they re-ran (planner/src/api/cache.ts lines 120-145 {AT})')
DEADLINE_RULE = ('leave-by deadline (출발 마감) = the latest departure offset whose cell is checked_route '
                 f'(plan.ts latestSafeDeparture, lines 155-161 {AT}); offsets are 0, 600, ..., 3000 s after the '
                 'recorded input time; unresolved cells never count')
DEADLINE_DEF = ('The leave-by deadline (출발 마감) is the latest departure offset whose cell is checked_route '
                f'(plan.ts latestSafeDeparture, lines 155-161 {AT}); unresolved cells never count.')
ENTRY_NOTE = ('Departures, leave-by deadlines and fire-free trips start at each place\'s road entry point (진입 지점: the '
              'nearest node of the main road network, at most 2 km from the mapped point); travel between the place '
              'and that point is not modelled.')
# appended to the definition of every number that depends on this package's own road-graph computation
SOURCE_COMPUTED = {
    False: (' Source: computed by this package from the SHA-verified road graph (data/routing graph.json) and the '
            'recorded cache, not by the Route-Check API, so it is not evaluated-host output; the committed value was '
            'computed in a Linux container.'),
    True: (' Source: computed by this package from the SHA-verified road graph and hazard packets (data/routing '
           'graph.json, HAZARD.json) and the recorded cache, not by the Route-Check API, so it is not evaluated-host '
           'output; the committed value was computed in a Linux container.'),
}
WINDOW_RULE = ('A departure at offset t can only be checked if arrival plus the required stay ends by the destination '
               'window close and the hazard valid_until (3600 s): the kit accepts a destination arrival only if '
               'arrival + dwell <= min(close, horizon) (temporal_contract.py check_mission). "Fits" = for at least '
               'one candidate destination, t + fastest fire-free trip + required stay (120 s) <= 3600 s, where the '
               'fastest fire-free trip is a turn-aware Dijkstra on travel_ticks (dt = 1 s, the graph\'s 40 km/h '
               'assumption) from the entry node, with no waits. "Window-limited" = nothing fits: no route can be '
               'checked at that departure whatever the fire does. Planner verdicts are unchanged.')
WINDOW_NOTE = (' At later departure offsets many such cells are window-limited (no checked route is possible even '
               'without fire); see window_limited.* and not_checked_although_fits.*.')


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
        self.with_graphs = result['with_graphs']
        self.inputs = {row['path']: row['sha256'] for row in sources.input_files_record(result['entries'], self.with_graphs)}
        self.numbers: dict[str, dict] = {}

    def scope_inputs(self, scope: str, graphs: bool = False, hazard: bool = False) -> list[str]:
        """Every input file a number of this scope is computed from: INDEX.json, the scope's cache files and place files,
        plus the region graphs (graphs) and the scope's HAZARD packets (hazard: scenario window and time step)."""
        reg = scope.split('/')[0]
        regions = sources.REGIONS if reg == 'all' else (reg,)
        metas = [m for m in self.metas.values() if m['region'] in regions and
                 (scope.split('#')[0].endswith(('/pooled', '/places')) or m['scope'] == scope.split('#')[0])]
        files = ['planner/cache/INDEX.json'] + [m['cache_file'] for m in metas]
        files += [f'planner/public/data/regions/{r}/places.geojson' for r in regions]
        if graphs:
            files += [f'data/routing/graphs/{r}/graph.json' for r in regions]
        if hazard:
            files += [m['hazard_rel'] for m in metas]
        return files

    def add(self, key: str, value, definition: str, numerator=None, denominator=None, unit: str = 'count',
            graphs: bool = False, n: int | None = None, hazard: bool = False):
        if key in self.numbers:
            raise KeyError(f'duplicate number {key}')
        if (graphs or hazard) and not self.with_graphs:
            raise ValueError(f'{key} needs the road graph / hazard packets, but this run read no data/routing input')
        if hazard and not graphs:
            raise ValueError(f'{key}: every hazard-dependent number also depends on the road graph (fire-free trips)')
        metric, _, rest = key.partition('@')
        scope, _, subset = rest.partition('#')
        if graphs:
            definition += SOURCE_COMPUTED[hazard]
        entry = {'value': value, 'unit': unit, 'numerator': numerator, 'denominator': denominator,
                 'definition': definition, 'scope': scope, 'subset': subset or None,
                 'scope_text': _scope_text(scope, self.metas), 'script': SCRIPT,
                 'inputs': self.scope_inputs(rest, graphs, hazard), 'uses_graph': graphs, 'uses_hazard': hazard}
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
                       f'plan.ts lines 106-111 / 204 {AT}) is {v}. {CELL_RULE}.{st}')
            for cat in DEADLINE_CATS:
                k = sum(1 for r in rows if r['deadline_category'] == cat)
                if cat.startswith('latest_'):
                    t = int(cat[7:11])
                    d = (f'Cases whose leave-by deadline is exactly {t} s (+{t // 60} min) after the recorded input '
                         f'time. {DEADLINE_DEF} ' +
                         ('This is the last checked offset, so the true limit may be later: the scenario window '
                          'simply ends.' if t == LAST else
                          f'The next offset (+{t // 60 + 10} min) had no checked route; deadline.{cat}.set_by_window '
                          f'and .set_by_fire_or_limits say whether a fire-free trip would still have fitted the 1-hour '
                          f'scenario window at that next offset.'))
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
                   f'Cases that have a checked route at some departure offset but whose leave-by deadline is before '
                   f'{LAST} s, i.e. the last departure with a checked route is +{(LAST - 600) // 60} min or earlier. '
                   f'{DEADLINE_DEF} Many of these deadlines are set by the 1-hour scenario window rather than by '
                   f'fire: see deadline_set_by.*.{st}')
            kn = sum(1 for r in rows if r['latest_s'] is None)
            b.frac('no_checked_route_any_offset' + tag, kn, n,
                   'Cases with no checked route at any of the departure offsets (overall verdict model_no_route or '
                   f'unresolved; the sum of the two deadline.none_* counts).{st}')
            kl = sum(1 for r in rows if r['cells'][LAST] != pr.CHECKED)
            b.frac(f'not_checked_at_offset_{LAST:04d}s' + tag, kl, n,
                   f'Cases whose cell at the last departure offset ({LAST} s, +{LAST // 60} min) is not checked_route '
                   f'(earlier leave-by deadline, or no checked route at all).{WINDOW_NOTE}{st}')
            for t in OFFSETS:            # per origin type too: the survival curve of each type
                for cat in CELL_CATS:
                    k = sum(1 for r in rows if r['cells'][t] == cat)
                    extra = (' window_unsatisfiable ("시간창 밖") = no request was sent because the recorded arrival '
                             'window cannot be met from this offset; it is never a verdict.' if cat == pr.WINDOW_UNSATISFIABLE else '')
                    note = WINDOW_NOTE if cat in (pr.NO_ROUTE, pr.UNRESOLVED) else ''
                    b.frac(f'cell.{cat}.offset_{t:04d}s' + tag, k, n,
                           f'Cases whose cell at departure offset {t} s (+{t // 60} min after the input time) is '
                           f'{cat}. {CELL_RULE}.{extra}{note}{st}')
            kc = sum(1 for r in rows if r['latest_s'] is not None and r['contiguous_s'] != r['latest_s'])
            b.frac('contiguous_differs_from_latest' + tag, kc, sum(1 for r in rows if r['latest_s'] is not None),
                   'Cases with a checked route whose contiguous deadline (contract latest_contiguous_checked_depart_'
                   f'offset_s; plan.ts contiguousSafeDeparture, lines 169-178 {AT}) differs from the leave-by deadline. '
                   'When this is 0, the share checked at offset t equals the share whose deadline is at or after t.' + st)
            att = [(r['scope'], r['origin_id'], k, v) for r in rows for k, v in r['unresolved_reasons'].items()]
            n_att = sum(r['n_attempts'] for r in rows)
            b.add('attempts' + tag, n_att,
                  'Route-check attempts behind these cases as the planner displays them (one per origin x candidate '
                  'destination x departure offset; a re-check replaces the attempt it re-ran).' + st)
            for v in pr.VERDICTS:        # check-level verdict counts (the case-level ones are best_verdict.*)
                b.frac(f'attempts.verdict.{v}' + tag, sum(r['attempt_verdicts'].get(v, 0) for r in rows), n_att,
                       f'Displayed route-check attempts (denominator; a re-check replaces the attempt it re-ran) whose own '
                       f'verdict is {v} (numerator): counts of single checks (place x candidate destination x departure '
                       f'offset), not of cases.{st}')
            reasons = Counter()
            for _, _, code, cnt in att:
                reasons[code] += cnt
            for code in ('AT_ISSUE_FAILURE', 'TIMEOUT'):
                b.frac(f'attempts.unresolved.{code}' + tag, reasons.get(code, 0), n_att,
                       f'Displayed attempts whose verdict is unresolved with API reason_code {code} '
                       + ('(api/README.md: "The limits were already exceeded at departure, for example because of '
                          'incurred dose"; dispatch requests carry no incurred dose).' if code == 'AT_ISSUE_FAILURE'
                          else '(the fixed 30 s request budget was exceeded).') + ' Unresolved is never safe.' + st)
            other = sum(v for k, v in reasons.items() if k not in ('AT_ISSUE_FAILURE', 'TIMEOUT'))
            b.frac('attempts.unresolved.other' + tag, other, n_att,
                   'Displayed unresolved attempts with any other (or no) reason_code.' + st)


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
                   'checked_route in at least one of the region\'s three recorded scenario sets (earlier leave-by '
                   f'deadline, or no checked route at all).{WINDOW_NOTE}{st}')
            kw = sum(1 for rs in by_place.values() if any(r['latest_s'] is not None and r['latest_s'] < LAST for r in rs))
            b.frac('places.window_closes_within_hour_any_input' + tag, kw, n,
                   'Distinct places that, in at least one recorded scenario set, have a checked route at some departure '
                   f'offset but a leave-by deadline before {LAST} s (set by the scenario window or by fire/limits). '
                   f'{DEADLINE_DEF}{st}')
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
                if not b.with_graphs:
                    continue
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


def travel_unpaired_numbers(b: Builder, unpaired: list[dict]):
    """travel_only records that are not one of the village/care-facility comparisons (P4F-04)."""
    tag = '@all/pooled'
    total = sum(m['travel_only_records'] for m in b.metas.values())
    b.frac('travel_only.records_not_paired' + tag, len(unpaired), total,
           'travel_only comparison records stored in the six cache files (denominator; records.travel_only) that are '
           'not paired with a village/care-facility case (numerator): every record whose origin is not an OSM case with '
           'a checked route at the same start, destination and departure as its default checked route.')
    res = [u for u in unpaired if u['origin_type'] == 'research']
    b.frac('travel_only.records_not_paired.research_origin' + tag, len(res), len(unpaired),
           'Of the unpaired travel_only records (denominator), those of recorded research-mission origins (numerator); '
           'they are left out like every other research-origin result.')
    b.frac('travel_only.records_not_paired.fastest_meets_flames' + tag,
           sum(1 for u in unpaired if u['contact_members'] > 0), len(unpaired),
           'Of the unpaired travel_only records (denominator), those whose travel-time-only route has predicted flame '
           'contact (exposure contact = true, centre model) in at least one of the 4 scenario members (numerator); '
           'reported for completeness, not part of travel_only.fastest_meets_flames.')


def research_numbers(b: Builder, records: list[dict]):
    """Recorded research-mission origins, kept out of every village/care-facility number: their origin-cases and route
    checks as the planner shows them, so that the totals of planner/cache/INDEX.json reconcile."""
    for sc in list(b.metas) + ['all/pooled']:
        rows = [r for r in records if r['origin_type'] == 'research' and (sc == 'all/pooled' or r['scope'] == sc)]
        tag = '@' + sc
        b.add('research_origins' + tag, len(rows),
              'Recorded research-mission origins of the scenario set(s) (planner scenarioOrigins: the origins of the '
              'recorded missions, one per recorded mission); not villages or care facilities.')
        n_att = sum(r['n_attempts'] for r in rows)
        if any(r['n_rechecked_attempts'] for r in rows):
            raise AssertionError(f'{sc}: a research-origin check was re-checked; the definitions below assume none')
        for v in pr.VERDICTS:
            b.frac(f'research_checks.verdict.{v}' + tag, sum(r['attempt_verdicts'].get(v, 0) for r in rows), n_att,
                   'Route checks of the research-mission origins as the planner shows them (denominator; no re-check '
                   f'replaced any) whose verdict is {v} (numerator). Not part of any village/care-facility number.')
        reasons = Counter()
        for r in rows:
            reasons.update(r['unresolved_reasons'])
        for code in ('AT_ISSUE_FAILURE', 'TIMEOUT'):
            b.frac(f'research_checks.unresolved.{code}' + tag, reasons.get(code, 0), n_att,
                   f'Research-origin route checks (denominator) that are unresolved with API reason_code {code}.')
        b.frac('research_checks.unresolved.other' + tag,
               sum(v for k, v in reasons.items() if k not in ('AT_ISSUE_FAILURE', 'TIMEOUT')), n_att,
               'Research-origin route checks (denominator) that are unresolved with any other (or no) reason_code.')


def entry_numbers(b: Builder, records: list[dict]):
    """How far each checked place lies from its road entry point, where every check of the place started (D3)."""
    d = ('Straight-line distance (EPSG:5179 metres, rounded to 0.1 m by the planner\'s data builder; places.geojson '
         'entry.distance_m) from the mapped OSM point of a place to its road entry point (진입 지점), the nearest node '
         'of the main road network (largest strongly connected component of the road graph), which is the start node '
         'of every route check of the place (asserted). ' + ENTRY_NOTE)
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            rows = _sel(records, f'{reg}/places', sub)
            if not rows:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            st = SUBSET_TEXT[sub]
            dist = {}
            for r in rows:
                if dist.setdefault((r['region'], r['origin_id']), r['entry_distance_m']) != r['entry_distance_m']:
                    raise AssertionError(f'{r["origin_id"]}: entry distance differs between input times')
            vals = list(dist.values())
            for stat, fn in (('min', min), ('median', statistics.median), ('max', max)):
                b.add(f'entry_distance_m.{stat}' + tag, round(fn(vals), 2),
                      f'{stat} over distinct places (field n). ' + d + st, unit='m', n=len(vals))
            for lim in (500, 1000):
                b.frac(f'entry_distance_over_{lim}m' + tag, sum(1 for v in vals if v > lim), len(vals),
                       f'Distinct places (denominator) whose road entry point is more than {lim} m from the mapped point '
                       f'(numerator). ' + d + st)


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


WIN = {'graphs': True, 'hazard': True}       # fire-free trips on graph.json x dt and the window from HAZARD.json


def travel_by_deadline_numbers(b: Builder, pairs: list[dict]):
    """The travel-only flame-contact share split by the leave-by deadline (recorded results only)."""
    comp = [p for p in pairs if p.get('has_comparison') and p['same_start_destination_offset']]
    for sc in ('all/pooled', 'uiseong_andong_2025/pooled'):
        reg = sc.split('/')[0]
        sel = [p for p in comp if reg == 'all' or p['region'] == reg]
        for name, f in (('leave_by_3000s', lambda p: p['depart_offset_s'] == LAST),
                        ('leave_by_before_3000s', lambda p: p['depart_offset_s'] < LAST)):
            group = [p for p in sel if f(p)]
            b.frac(f'travel_only.fastest_meets_flames@{sc}#{name}', sum(1 for p in group if p['fastest_meets_flames']),
                   len(group), 'Travel-time-only comparisons at the leave-by deadline, restricted to cases whose '
                   'leave-by deadline is ' + ('the last checked offset (3000 s)' if name == 'leave_by_3000s' else
                                              'before 3000 s') + ' (denominator); numerator: the fastest route has '
                   'predicted flame contact (exposure contact = true) in at least one of the 4 scenario members.')


def window_numbers(b: Builder, records: list[dict], pairs: list[dict], redundancy: list[dict]):
    """Which unchecked departures could not be checked anyway because of the 1-hour scenario window (graph + hazard)."""
    scopes = list(b.metas) + [f'{r}/pooled' for r in sources.REGIONS] + ['all/pooled']
    for sc in scopes:
        for sub in ('', 'village', 'care_facility'):
            rows = _sel(records, sc, sub)
            if not rows:
                continue
            tag = f'@{sc}' + (f'#{sub}' if sub else '')
            n = len(rows)
            st = SUBSET_TEXT[sub]
            closes = [r for r in rows if r['latest_s'] is not None and r['latest_s'] < LAST]
            for by, text in (('window', 'the next departure offset is window-limited: even the fastest fire-free '
                                        'trip plus the stay would end after the 1-hour scenario window'),
                             ('fire_or_limits', 'a fire-free trip would still fit the window at the next departure '
                                                'offset, so the model\'s fire scenarios or limits (or an unresolved '
                                                'check) set the deadline')):
                k = sum(1 for r in closes if r['deadline_set_by'] == by)
                b.frac(f'deadline_set_by.{by}' + tag, k, len(closes),
                       f'Among cases whose leave-by deadline is before {LAST} s (denominator), those where {text} '
                       f'(numerator). {WINDOW_RULE}{st}', **WIN)
                for t in OFFSETS[:-1]:
                    k = sum(1 for r in rows if r['latest_s'] == t and r['deadline_set_by'] == by)
                    b.frac(f'deadline.latest_{t:04d}s.set_by_{by}' + tag, k, n,
                           f'Cases whose leave-by deadline is {t} s and where {text}. {WINDOW_RULE}{st}', **WIN)
            none = [r for r in rows if r['latest_s'] is None]
            k = sum(1 for r in none if r['fits'][0])
            b.frac('no_checked_route_any_offset.trip_fits_at_offset_0000s' + tag, k, len(none),
                   'Among cases with no checked route at any departure offset (denominator), those whose fastest '
                   f'fire-free trip fits the scenario window for departure at 0 s (numerator). {WINDOW_RULE}{st}', **WIN)
            if sub:
                continue
            for t in OFFSETS:
                lim = [r for r in rows if not r['fits'][t]]
                fit = [r for r in rows if r['fits'][t]]
                b.frac(f'window_limited.offset_{t:04d}s' + tag, len(lim), n,
                       f'Cases whose departure at {t} s (+{t // 60} min) is window-limited: no route could be checked '
                       f'whatever the fire. {WINDOW_RULE}', **WIN)
                notc = [r for r in rows if r['cells'][t] != pr.CHECKED]
                b.frac(f'window_limited_among_not_checked.offset_{t:04d}s' + tag, sum(1 for r in notc if not r['fits'][t]),
                       len(notc), f'Among cases whose cell at {t} s (+{t // 60} min) is not checked_route (denominator), '
                       f'those that are window-limited (numerator); every checked cell fits, so window-limited cells are '
                       f'always among the unchecked ones. {WINDOW_RULE}', **WIN)
                k = sum(1 for r in fit if r['cells'][t] != pr.CHECKED)
                b.frac(f'not_checked_although_fits.offset_{t:04d}s' + tag, k, len(fit),
                       f'Among cases whose fastest fire-free trip fits the scenario window for departure at {t} s '
                       f'(+{t // 60} min) (denominator), those whose cell there is not checked_route (numerator): the '
                       f'model\'s fire scenarios or limits rule it out, or the check is unresolved. {WINDOW_RULE} '
                       f'{CELL_RULE}.', **WIN)
                for v in (pr.NO_ROUTE, pr.UNRESOLVED):
                    for cls, group in (('fits', fit), ('limited', lim)):
                        k = sum(1 for r in group if r['cells'][t] == v)
                        b.frac(f'cell_window.{v}.{cls}.offset_{t:04d}s' + tag, k, n,
                               f'Cases whose cell at {t} s is {v} and whose fastest fire-free trip '
                               f'{"fits" if cls == "fits" else "does not fit (window-limited)"} the scenario window '
                               f'at that departure. {WINDOW_RULE}', **WIN)
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            rows = _sel(records, f'{reg}/places', sub)
            if not rows:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            st = SUBSET_TEXT[sub]
            by_place = defaultdict(list)
            for r in rows:
                by_place[(r['region'], r['origin_id'])].append(r)
            n = len(by_place)
            unchecked_last = [rs for rs in by_place.values() if any(r['cells'][LAST] != pr.CHECKED for r in rs)]
            k = sum(1 for rs in unchecked_last if any(r['cells'][LAST] != pr.CHECKED and r['fits'][LAST] for r in rs))
            b.frac(f'places.not_checked_although_fits_at_offset_{LAST:04d}s_any_input' + tag, k, len(unchecked_last),
                   f'Among distinct places with an unchecked departure at {LAST} s in at least one recorded scenario '
                   f'set (denominator), those for which such an unchecked {LAST} s departure would fit the scenario '
                   f'window fire-free (numerator). {WINDOW_RULE}{st}', **WIN)
            k = sum(1 for rs in by_place.values()
                    if any(r['cells'][t] != pr.CHECKED and r['fits'][t] for r in rs for t in OFFSETS))
            b.frac('places.not_checked_although_fits_any_offset_any_input' + tag, k, n,
                   'Distinct places with, in at least one recorded scenario set, at least one departure offset that '
                   f'has no checked route although its fastest fire-free trip fits the scenario window. {WINDOW_RULE}{st}',
                   **WIN)
            trip = {}
            for key, rs in by_place.items():
                vals = {r['trip_min_s'] for r in rs}
                if len(vals) != 1:
                    raise AssertionError(f'{key}: fire-free trip differs between input times')
                trip[key] = vals.pop()
            k = sum(1 for key, rs in by_place.items() if not rs[0]['fits'][LAST])
            b.frac(f'places.window_limited_at_offset_{LAST:04d}s' + tag, k, n,
                   f'Distinct places whose departure at {LAST} s is window-limited (fastest fire-free trip to the '
                   f'nearest candidate destination + 120 s stay > {3600 - LAST} s). {WINDOW_RULE}{st}', **WIN)
            for stat, fn in (('min', min), ('median', statistics.median), ('max', max)):
                v = fn(list(trip.values()))
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                b.add(f'fastest_trip_s.{stat}' + tag, v,
                      f'{stat} over distinct places (field n) of the fastest fire-free trip from the entry node to the '
                      f'nearest of the 3 candidate destinations, in seconds (turn-aware Dijkstra on travel_ticks, '
                      f'x dt = 1 s from HAZARD.json; the graph assumes 40 km/h; no congestion, no fire).{st}', unit='s',
                      n=n, **WIN)
    comp = [p for p in pairs if p.get('has_comparison') and p['same_start_destination_offset']]
    b.frac('trip_model.equals_travel_only@all/pooled', sum(1 for p in comp if p['trip_model_s'] ==
                                                           p['fastest_arrival_s'] - p['depart_offset_s']), len(comp),
           'Validation of the fire-free trip model: travel-only comparisons (denominator) whose recorded travel-time-only '
           'route (API policy travel_only) takes exactly as long (arrival - departure) as this package\'s turn-aware '
           'Dijkstra to the same destination (numerator).', **WIN)
    travel_by_deadline_numbers(b, pairs)
    single = [x for x in redundancy if x['origin_type'] in OSM_TYPES and x['turn_aware_paths'] == 1]
    for reg in list(sources.REGIONS) + ['all']:
        rows = [x for x in single if reg == 'all' or x['region'] == reg]
        tag = f'@{reg}/places'
        d = ('Places with turn-aware redundancy value 1 (field n): every legal walk from the entry node to the '
             'candidate destinations drives a common chain of road edges. Shared stretch = shortest legal-walk length '
             '(sum of straight edge chords, EPSG:5179 m) from the entry node to the end of the last road edge that '
             'every such walk drives (common edges found by growing the max-flow residual closure).')
        for stat, fn in (('min', min), ('median', statistics.median), ('max', max)):
            b.add(f'redundancy.shared_stretch_m.{stat}' + tag, round(fn([x['shared_stretch_m'] for x in rows]), 1),
                  d + f' {stat}, rounded to 0.1 m.', unit='m', graphs=True, n=len(rows))
        b.frac('redundancy.shared_stretch_within_100m' + tag, sum(1 for x in rows if x['shared_stretch_m'] <= 100.0),
               len(rows), d + ' Numerator: places whose shared stretch ends within 100 m of the entry node.', graphs=True)


HEADLINE_KEYS = (
    'records.route_checks@all/pooled', 'records.rechecks@all/pooled', 'attempts@all/pooled',
    'places@all/places', 'osm_origins_not_checkable@all/places', 'cases@all/pooled',
    'cell.checked_route.offset_0000s@all/pooled',
    'no_checked_route_any_offset@all/pooled', 'best_verdict.model_no_route@all/pooled', 'best_verdict.unresolved@all/pooled',
    'no_checked_route_any_offset.trip_fits_at_offset_0000s@all/pooled',
    'not_checked_although_fits.offset_0000s@uiseong_andong_2025/pooled',
    'not_checked_although_fits.offset_1800s@uiseong_andong_2025/pooled',
    'not_checked_although_fits.offset_2400s@uiseong_andong_2025/pooled',
    'not_checked_although_fits.offset_3000s@uiseong_andong_2025/pooled',
    'not_checked_although_fits.offset_0000s@yeongdeok_2025/pooled',
    'not_checked_although_fits.offset_1800s@yeongdeok_2025/pooled',
    'window_limited_among_not_checked.offset_3000s@all/pooled',
    'window_limited_among_not_checked.offset_3000s@uiseong_andong_2025/pooled',
    'deadline_set_by.window@all/pooled', 'deadline_set_by.fire_or_limits@all/pooled',
    'places.not_checked_although_fits_any_offset_any_input@all/places',
    'places.not_checked_although_fits_at_offset_3000s_any_input@all/places',
    'fastest_trip_s.median@uiseong_andong_2025/places#village', 'fastest_trip_s.median@yeongdeok_2025/places#village',
    'fastest_trip_s.min@all/places#care_facility', 'fastest_trip_s.max@all/places#care_facility',
    'trip_model.equals_travel_only@all/pooled',
    'api_check.recorded_equals_planner_rule_on_original@all/pooled',
    'api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled',
    'api_check.displayed_differs_explained_by_recheck@all/pooled',
    'travel_only.fastest_meets_flames@all/pooled', 'travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s',
    'travel_only.fastest_meets_flames@all/pooled#leave_by_3000s',
    'travel_only.clear_pairs_equal_arrival@all/pooled',
    'travel_only.extra_arrival_s.min@all/pooled', 'travel_only.extra_arrival_s.median@all/pooled',
    'travel_only.extra_arrival_s.max@all/pooled',
    'travel_only.extra_length_m.min@all/pooled', 'travel_only.extra_length_m.median@all/pooled',
    'travel_only.extra_length_m.max@all/pooled',
    'redundancy.turn_aware_paths_1@all/places', 'redundancy.single_cut_at_entry_node@all/places',
    'redundancy.turn_aware_equals_plain@all/places', 'redundancy.shared_stretch_m.median@all/places',
    'redundancy.shared_stretch_within_100m@all/places',
)


def build(result: dict) -> dict:
    """Every number. With ``result['with_graphs']`` false (``analysis.run(with_graphs=False)``) only the cache-only
    numbers (uses_graph false) are built: no road graph or HAZARD packet was read."""
    b = Builder(result)
    records = result['records']
    scope_numbers(b, result)
    case_numbers(b, records)
    place_numbers(b, records)
    api_numbers(b, records)
    travel_numbers(b, result['pairs'])
    if b.with_graphs:
        redundancy_numbers(b, result['redundancy'], records)
        window_numbers(b, records, result['pairs'], result['redundancy'])
    else:
        travel_by_deadline_numbers(b, result['pairs'])
    travel_unpaired_numbers(b, result['travel_unpaired'])
    research_numbers(b, records)
    entry_numbers(b, records)
    for key in HEADLINE_KEYS:                        # fully self-contained provenance on every headline number
        if key not in b.numbers and not b.with_graphs:
            continue
        e = b.numbers[key]
        e['headline'] = True
        e['input_sha256'] = {p: b.inputs[p] for p in e['inputs']}
    return b.numbers
