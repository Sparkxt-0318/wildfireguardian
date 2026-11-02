"""Candidate one-sentence statements for the grant application, rendered from NUMBERS.json.

Placeholders (in the sentence AND its caution, so no number is ever typed by hand): {v:KEY} value, {n:KEY} numerator,
{d:KEY} denominator, {p:KEY} numerator/denominator as a percentage (one decimal), {min:KEY} a value in seconds shown
in minutes (one decimal), {km:KEY} a value in metres shown in km (one decimal). Every key a sentence relies on is
listed under it (placeholders + ``related``). Structural facts (4 scenario members, 6 departure times 10 minutes
apart, 3 recorded input times per region, 1-hour horizon) are properties of the recorded inputs, not computed numbers.
"""
from __future__ import annotations

import re

SENTENCES = [
    {
        'id': 'S1',
        'text': (
            'Using the recorded March 2025 forecasts of the Uiseong-Andong and Yeongdeok wildfires, our planner checked '
            'vehicle departures for {v:places@all/places} OpenStreetMap-mapped villages and care facilities against 4 '
            'fire scenarios from the forecast, at six departure times 10 minutes apart after each of three recorded '
            'forecast times per region, in {v:attempts@all/pooled} recorded route checks (one per place, candidate '
            'destination and departure time).'),
        'related': ['cases@all/pooled', 'records.dispatch_attempts@all/pooled'],
        'caution': (
            'Route checks are model computations by the Route-Check API recorded on the evaluated macOS host, not field '
            'trials or drills. The 4 fire scenarios are scenario members drawn independently per cell from the '
            'forecast, not simulations of the actual fire. The cache holds {v:records.route_checks@all/pooled} '
            'route-check records in all: the {v:records.dispatch_attempts@all/pooled} above, '
            '{v:records.rechecks@all/pooled} re-checks of timed-out checks (shown in place of the original, as in the '
            'planner) and {v:records.research_route_checks@all/pooled} checks of recorded research missions. '
            '{v:osm_origins_not_checkable@all/places} further OSM villages had no road node within 2 km and were '
            'never checked.'),
    },
    {
        'id': 'S2',
        'text': (
            'In the recorded Uiseong-Andong scenarios, the share of villages and care facilities with a checked route '
            '(within the model) fell from {p:cell.checked_route.offset_0000s@uiseong_andong_2025/pooled} for departure '
            'at the forecast time to {p:cell.checked_route.offset_3000s@uiseong_andong_2025/pooled} for departure 50 '
            'minutes later ({n:cell.checked_route.offset_0000s@uiseong_andong_2025/pooled} and '
            '{n:cell.checked_route.offset_3000s@uiseong_andong_2025/pooled} of '
            '{d:cell.checked_route.offset_0000s@uiseong_andong_2025/pooled} place-and-forecast-time cases).'),
        'related': [],
        'caution': (
            'Cases count each place once per recorded forecast time ({v:places@uiseong_andong_2025/places} places x 3). '
            'A departure without a checked route means the model found no route satisfying its checks for those '
            'scenario members, or could not judge; it is not a prediction that residents could not escape. In '
            'Yeongdeok the same share went from {p:cell.checked_route.offset_0000s@yeongdeok_2025/pooled} to '
            '{p:cell.checked_route.offset_3000s@yeongdeok_2025/pooled}; quote both regions together to avoid '
            'cherry-picking.'),
    },
    {
        'id': 'S3',
        'text': (
            'In {n:no_checked_route_any_offset@all/pooled} of {d:no_checked_route_any_offset@all/pooled} '
            'place-and-forecast-time cases ({p:no_checked_route_any_offset@all/pooled}), the model found no checked '
            'route at any of the six departure times: '
            '{n:best_verdict.model_no_route@all/pooled} had no route within the model and '
            '{n:best_verdict.unresolved@all/pooled} were unresolved, which the planner never presents as safe.'),
        'related': ['deadline.none_model_no_route@all/pooled', 'deadline.none_unresolved@all/pooled',
                    'no_checked_route_at_offset_0000s@all/pooled'],
        'caution': (
            '"No route within the model" (model_no_route) is a statement about this model and input scope, not proof '
            'that escape is impossible. "Unresolved" means the system could not judge and must never be read as safe '
            'or as no-route; of all {d:attempts.unresolved.AT_ISSUE_FAILURE@all/pooled} displayed attempts, '
            '{n:attempts.unresolved.AT_ISSUE_FAILURE@all/pooled} were unresolved with API reason code AT_ISSUE_FAILURE '
            '("limits already exceeded at departure") and {n:attempts.unresolved.TIMEOUT@all/pooled} with TIMEOUT. '
            'These cases involve {n:places.no_checked_route_any_offset_any_input@all/places} distinct places; they are '
            'also exactly the {n:no_checked_route_at_offset_0000s@all/pooled} cases without a checked route for '
            'immediate departure.'),
    },
    {
        'id': 'S4',
        'text': (
            'Counting each place once, {n:places.not_checked_at_offset_3000s_any_input@all/places} of '
            '{d:places.not_checked_at_offset_3000s_any_input@all/places} villages and care facilities '
            '({p:places.not_checked_at_offset_3000s_any_input@all/places}) had no checked route for a departure 50 '
            'minutes after the forecast time in at least one of the three recorded forecast times: their leave-by time '
            'in the planner was +40 minutes or earlier, or no checked route existed.'),
        'related': ['places.window_closes_within_hour_any_input@all/places'],
        'caution': (
            'Model-relative and tied to the recorded scenarios, the 10-minute departure grid and the 1-hour horizon. Of '
            'these places, {n:places.window_closes_within_hour_any_input@all/places} had a checked departure window '
            'that closed inside the hour and {n:places.no_checked_route_any_offset_any_input@all/places} had no checked '
            'route in some forecast time (a place can be in both). A place outside this count is not "safe": the '
            'scenario window simply ends at +50 minutes.'),
    },
    {
        'id': 'S5',
        'text': (
            'At each place\'s leave-by time, the travel-time-only route to the same destination met predicted flames in '
            'at least one of 4 fire scenarios in {n:travel_only.fastest_meets_flames@all/pooled} of '
            '{d:travel_only.fastest_meets_flames@all/pooled} comparisons ({p:travel_only.fastest_meets_flames@all/pooled}, '
            'all in Uiseong-Andong); there the checked alternative took {min:travel_only.extra_arrival_s.min@all/pooled} '
            'to {min:travel_only.extra_arrival_s.max@all/pooled} minutes longer (median '
            '{min:travel_only.extra_arrival_s.median@all/pooled} minutes) and was {km:travel_only.extra_length_m.min@all/pooled} '
            'to {km:travel_only.extra_length_m.max@all/pooled} km longer.'),
        'related': ['travel_only.fastest_meets_flames@uiseong_andong_2025/pooled'],
        'caution': (
            'Only {n:travel_only.fastest_meets_flames@all/pooled} comparisons; do not generalise. The comparison exists '
            'only at each place\'s latest checked departure and toward its default checked destination. "Predicted '
            'flames" = centre-model flame contact in at least one scenario member, not an observed fire. In the other '
            '{d:travel_only.clear_pairs_equal_arrival@all/pooled} comparisons the fastest route had no predicted flame '
            'contact and arrived at the same second as the checked route '
            '({n:travel_only.clear_pairs_equal_arrival@all/pooled} of {d:travel_only.clear_pairs_equal_arrival@all/pooled}). '
            'Never describe the checked route as "safe".'),
    },
    {
        'id': 'S6',
        'text': (
            'On the road graph used for routing, every route from {n:redundancy.turn_aware_paths_1@all/places} of '
            '{d:redundancy.turn_aware_paths_1@all/places} villages and care facilities '
            '({p:redundancy.turn_aware_paths_1@all/places}) to their three candidate destinations shares at least one '
            'road segment, a single point of failure in the model\'s road network; for '
            '{n:redundancy.single_cut_at_entry_node@all/places} of these it is the first segment leaving the place\'s '
            'road entry point.'),
        'related': ['redundancy.entry_out_degree_1@all/places'],
        'caution': (
            'A property of the provisional pre-fire OSM road graph (2025-03-21 snapshot; missing one-way tags assumed '
            'two-way) and of the planner\'s entry point (nearest road node to the OSM point), not a field-verified count '
            'of access roads. "Shares at least one road segment" = the largest set of routes that pairwise share no '
            'directed road segment has one route (unit-capacity max-flow = 1, computed with and without turn '
            'restrictions, equal for {n:redundancy.turn_aware_equals_plain@all/places} of '
            '{d:redundancy.turn_aware_equals_plain@all/places} places); it ignores road capacity, travel time and fire. '
            'Candidate destinations are {v:destinations_used.school@all/places} OSM schools, '
            '{v:destinations_used.community_hall@all/places} community halls and {v:destinations_used.shelter@all/places} '
            'OSM-mapped shelter, not official evacuation shelters.'),
    },
    {
        'id': 'S7',
        'text': (
            'Every leave-by time in this analysis is reproducible: applying the planner\'s rules to the original '
            'attempts recorded by the Route-Check API reproduces the API\'s own deadline fields for '
            '{n:api_check.recorded_equals_planner_rule_on_original@all/pooled} of '
            '{d:api_check.recorded_equals_planner_rule_on_original@all/pooled} place-and-forecast-time cases, all '
            '{d:api_check.displayed_differs_explained_by_recheck@all/pooled} displayed differences are explained by '
            're-checks of timed-out checks, and an independent second implementation recomputes every reported number.'),
        'related': ['api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled'],
        'caution': (
            'This is internal consistency of software and recorded data. It does not validate the forecast, the hazard '
            'model, the road data or real-world safety. The planner displays re-checks, so its deadline equals the '
            'API\'s recorded latest_checked_depart_offset_s for '
            '{n:api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled} of '
            '{d:api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled} cases.'),
    },
    {
        'id': 'S8',
        'text': (
            'In the Uiseong-Andong scenarios, all {d:deadline.latest_3000s@all/pooled#care_facility} care-facility cases '
            '({v:places@uiseong_andong_2025/places#care_facility} OpenStreetMap-mapped facilities x 3 forecast times) '
            'still had a checked route at the last checked departure time (+50 minutes), whereas '
            '{n:not_checked_at_offset_3000s@uiseong_andong_2025/pooled#village} of '
            '{d:not_checked_at_offset_3000s@uiseong_andong_2025/pooled#village} village cases there did not.'),
        'related': ['deadline.latest_3000s@uiseong_andong_2025/pooled#care_facility'],
        'caution': (
            'Only {v:places@all/places#care_facility} care facilities are mapped in the OSM extract (none in '
            'Yeongdeok), a small and probably incomplete sample. This does not mean care facilities are safe or need no '
            'planning; it only says the model found checked routes for them up to the end of the 1-hour scenario '
            'window.'),
    },
]

_PH = re.compile(r'\{(v|n|d|p|min|km):([^}]+)\}')


def _fmt(kind: str, e: dict) -> str:
    if kind == 'v':
        v = e['value']
        return f'{v:,}' if isinstance(v, int) else f'{v}'
    if kind == 'n':
        return f'{e["numerator"]:,}'
    if kind == 'd':
        return f'{e["denominator"]:,}'
    if kind == 'p':
        return f'{100.0 * e["numerator"] / e["denominator"]:.1f}%'
    if kind == 'min':
        return f'{e["value"] / 60.0:.1f}'
    if kind == 'km':
        return f'{e["value"] / 1000.0:.1f}'
    raise ValueError(kind)


def render(s: dict, numbers: dict) -> tuple[str, str, list[str]]:
    keys: list[str] = []

    def sub(m):
        kind, key = m.group(1), m.group(2)
        if key not in numbers:
            raise KeyError(f'{s["id"]}: unknown NUMBERS.json key {key}')
        if key not in keys:
            keys.append(key)
        return _fmt(kind, numbers[key])
    text = _PH.sub(sub, s['text'])
    caution = _PH.sub(sub, s['caution'])
    for key in s.get('related', []):
        if key not in numbers:
            raise KeyError(f'{s["id"]}: unknown NUMBERS.json key {key}')
        if key not in keys:
            keys.append(key)
    return text, caution, keys


def markdown(numbers: dict) -> str:
    out = ['# Candidate application sentences (MIT Solve 2027)', '',
           '<!-- Generated by research/solve2027-impact/compute.py from NUMBERS.json; do not edit by hand. -->', '',
           'Each sentence and its caution are rendered from [`NUMBERS.json`](NUMBERS.json); the keys they rely on '
           'follow. Every number is model-relative: it describes what the Route-Check API concluded for recorded '
           'fire-scenario members of the March 2025 fires, not what happened to residents, and never an evacuation '
           'outcome or casualties avoided. Say "checked route (within the model)", never "safe route". '
           'Definitions and caveats: [README.md](README.md).', '']
    for s in SENTENCES:
        text, caution, keys = render(s, numbers)
        out += [f'## {s["id"]}', '', f'> {text}', '', 'NUMBERS.json keys: ' + ', '.join(f'`{k}`' for k in keys), '',
                f'Caution: {caution}', '']
    return '\n'.join(out)
