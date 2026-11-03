"""Candidate one-sentence statements for the grant application, rendered from NUMBERS.json.

Placeholders (in the sentence AND its caution, so no number is ever typed by hand): {v:KEY} value, {n:KEY} numerator,
{d:KEY} denominator, {p:KEY} numerator/denominator as a percentage (one decimal), {min:KEY} a value in seconds shown
in minutes (one decimal), {km:KEY} a value in metres shown in km (one decimal), {m:KEY} a value in metres rounded to
whole metres. Every key a sentence relies on is listed under it (placeholders + ``related``). Structural facts
(4 scenario members, 6 departure times 10 minutes apart, 3 recorded forecast times per region, the 1-hour scenario
window, the 120 s required stay and hence the 8-minute (480 s) trip limit at +50 minutes) are properties of the
recorded inputs, not computed numbers. Wording that depends on a number ("none", "at both", "all in Uiseong-Andong")
is asserted by tests/test_reproduction.py.

Every sentence names its destination scope: each place is checked to each of its three nearest OSM-mapped schools or
community halls, not official shelters (one Yeongdeok place also has an unnamed OSM ``amenity=shelter`` point without
``shelter_type`` among its three; DEST_NOTE). Departures that the 1-hour scenario window rules out whatever the fire
("window-limited") are never counted as fire effects (numbers.WINDOW_RULE).

Sources: verdicts, leave-by times, re-checks and travel-only results are Route-Check API results recorded on the
evaluated macOS arm64 host. Every sentence that relies on a number this package computed itself on the road graph
(``uses_graph`` true: the window classification, fire-free trips, redundancy, route lengths) says so in its caution
(COMPUTED_*; asserted by tests/test_provenance.py).

Departures and leave-by times are at each place's road entry point, not at the mapped place. Because a sentence and
its caution may be quoted alone, no sentence says "from the place" without naming that entry point, and every caution
carries the entry-point note (ENTRY_NOTE; S6, which counts routes from that point, uses ENTRY_POINT with the same
"not modelled" clause), asserted by tests/test_provenance.py.
"""
from __future__ import annotations

import re

DEST = ('each of its three nearest OSM-mapped schools or community halls (not official shelters; a checked route to any '
        'one counts)')
_HALLS = 'three nearest OSM-mapped schools or community halls'
DEST_NOTE = ('Destinations: {v:destinations_used.school@all/places} OSM schools and '
             '{v:destinations_used.community_hall@all/places} OSM community halls; for one Yeongdeok place one of '
             'its three candidates is an unnamed OSM point tagged amenity=shelter without shelter_type. None is an '
             'official evacuation shelter.')
ENTRY_POINT = ('(진입 지점: the nearest node of the main road network, at most 2 km from the mapped point; median '
               '{v:entry_distance_m.median@all/places} m, {n:entry_distance_over_1000m@all/places} of '
               '{d:entry_distance_over_1000m@all/places} places more than 1 km away)')
ENTRY_NOTE = ('Departures and leave-by times are at each place\'s road entry point ' + ENTRY_POINT + '; travel between '
              'the place and that point is not modelled.')
_NOT_API = ('not by the Route-Check API on the evaluated host, so it is not evaluated-host output; the verdicts it is '
            'combined with are recorded API results')
COMPUTED_WINDOW = ('Source: the window classification (fastest fire-free trips on the road graph) was computed by this '
                   'package from the SHA-verified road graph and hazard packets in a Linux container, ' + _NOT_API + '.')
COMPUTED_LENGTH = ('Source: arrival times and flame contact are recorded API results; the route lengths (km) were computed '
                   'by this package from the SHA-verified road graph in a Linux container, not by the Route-Check API, '
                   'so they are not evaluated-host output.')
COMPUTED_GRAPH = ('Source: computed by this package on the SHA-verified road graph in a Linux container; the Route-Check '
                  'API was not asked this question, and it is not evaluated-host output.')

SENTENCES = [
    {
        'id': 'S1',
        'text': (
            'Using forecasts our model produced retrospectively for the recorded fire conditions of the March 2025 '
            'Uiseong-Andong and Yeongdeok wildfires, our planner checked vehicle departures from the road entry point '
            'of each of {v:places@all/places} OpenStreetMap-mapped villages and care facilities (the nearest node of '
            'the model\'s main road network, at most 2 km from the mapped place) to ' + DEST + ', against '
            '4 fire scenarios from the forecast at six departure times 10 minutes apart after each of three forecast '
            'times per region, in {v:attempts@all/pooled} recorded route checks (one per place, forecast time, '
            'candidate destination and departure time).'),
        'related': ['cases@all/pooled', 'records.dispatch_attempts@all/pooled', 'destinations_used.shelter@all/places',
                    'entry_distance_m.max@all/places'],
        'caution': (
            'Route checks are model computations by the Route-Check API recorded on the evaluated macOS host, not field '
            'trials or drills. ' + ENTRY_NOTE + ' The forecasts were produced in 2026 from recorded 2025 inputs (release '
            'research-final-20261015), not issued during the fires; the 4 fire scenarios are scenario members drawn '
            'independently per cell from the forecast, not simulations of the actual fire. ' + DEST_NOTE + ' The cache '
            'holds {v:records.route_checks@all/pooled} route-check records in all: the '
            '{v:records.dispatch_attempts@all/pooled} above, {v:records.rechecks@all/pooled} re-checks of timed-out '
            'checks (shown in place of the original, as in the planner) and '
            '{v:records.research_route_checks@all/pooled} checks of recorded research missions. '
            '{v:osm_origins_not_checkable@all/places} further OSM villages had no road node within 2 km and were '
            'never checked.'),
    },
    {
        'id': 'S2',
        'text': (
            'In the recorded Uiseong-Andong scenarios, among place-and-forecast-time cases whose fastest fire-free trip '
            'to one of the place\'s ' + _HALLS + ' (not official shelters) still fits the 1-hour scenario window, '
            '{n:not_checked_although_fits.offset_0000s@uiseong_andong_2025/pooled} of '
            '{d:not_checked_although_fits.offset_0000s@uiseong_andong_2025/pooled} '
            '({p:not_checked_although_fits.offset_0000s@uiseong_andong_2025/pooled}) had no checked route (within the '
            'model) for departure at the forecast time and '
            '{n:not_checked_although_fits.offset_1800s@uiseong_andong_2025/pooled} of '
            '{d:not_checked_although_fits.offset_1800s@uiseong_andong_2025/pooled} '
            '({p:not_checked_although_fits.offset_1800s@uiseong_andong_2025/pooled}) for departure 30 minutes later '
            '(Yeongdeok: {n:not_checked_although_fits.offset_0000s@yeongdeok_2025/pooled} of '
            '{d:not_checked_although_fits.offset_0000s@yeongdeok_2025/pooled}, '
            '{p:not_checked_although_fits.offset_0000s@yeongdeok_2025/pooled}, at both).'),
        'related': ['not_checked_although_fits.offset_1800s@yeongdeok_2025/pooled',
                    'window_limited.offset_0000s@uiseong_andong_2025/pooled'],
        'caution': (
            'Window-corrected: a departure can only be checked if the fastest fire-free trip plus the required 120 s '
            'stay ends within the 1-hour scenario window. Departures where even that does not fit ("window-limited": '
            'in Uiseong-Andong {n:window_limited.offset_0000s@uiseong_andong_2025/pooled} at the forecast time and '
            '{n:window_limited.offset_1800s@uiseong_andong_2025/pooled} at +30 minutes) are left out, because no route '
            'could be checked there whatever the fire. Without this correction the decline toward +50 minutes is '
            'mostly the window: at +50 minutes only trips of up to 8 minutes fit, and '
            '{n:window_limited_among_not_checked.offset_3000s@uiseong_andong_2025/pooled} of the '
            '{d:window_limited_among_not_checked.offset_3000s@uiseong_andong_2025/pooled} Uiseong-Andong cases without '
            'a checked route then were window-limited. The corrected share at +40 and +50 minutes is '
            '{p:not_checked_although_fits.offset_2400s@uiseong_andong_2025/pooled} and '
            '{p:not_checked_although_fits.offset_3000s@uiseong_andong_2025/pooled} in Uiseong-Andong. "No checked '
            'route" = model_no_route or unresolved; it is not a prediction that residents could not escape. Cases '
            'count each place once per forecast time ({v:places@uiseong_andong_2025/places} places x 3). '
            + ENTRY_NOTE + ' ' + COMPUTED_WINDOW),
    },
    {
        'id': 'S3',
        'text': (
            'In {n:no_checked_route_any_offset@all/pooled} of {d:no_checked_route_any_offset@all/pooled} '
            'place-and-forecast-time cases ({p:no_checked_route_any_offset@all/pooled}), the model found no checked '
            'route from the place\'s road entry point to any of its ' + _HALLS + ' (not official shelters) at any of '
            'the six departure times: '
            '{n:best_verdict.model_no_route@all/pooled} had no route within the model and '
            '{n:best_verdict.unresolved@all/pooled} were unresolved, which the planner never presents as safe.'),
        'related': ['deadline.none_model_no_route@all/pooled', 'deadline.none_unresolved@all/pooled',
                    'no_checked_route_at_offset_0000s@all/pooled'],
        'caution': (
            'The window does not explain these cases: for all '
            '{n:no_checked_route_any_offset.trip_fits_at_offset_0000s@all/pooled} of them the fastest fire-free trip '
            'fits the 1-hour scenario window for departure at the forecast time. "No route within the model" '
            '(model_no_route) is a statement about this model and input scope, not proof that escape is impossible. '
            '"Unresolved" means the system could not judge and must never be read as safe or as no-route; of all '
            '{d:attempts.unresolved.AT_ISSUE_FAILURE@all/pooled} displayed attempts, '
            '{n:attempts.unresolved.AT_ISSUE_FAILURE@all/pooled} were unresolved with API reason code AT_ISSUE_FAILURE '
            '("limits already exceeded at departure") and {n:attempts.unresolved.TIMEOUT@all/pooled} with TIMEOUT. '
            'These cases involve {n:places.no_checked_route_any_offset_any_input@all/places} distinct places; they are '
            'also exactly the {n:no_checked_route_at_offset_0000s@all/pooled} cases without a checked route for '
            'immediate departure. ' + ENTRY_NOTE + ' ' + COMPUTED_WINDOW),
    },
    {
        'id': 'S4',
        'text': (
            'Counting each place once, {n:places.not_checked_although_fits_any_offset_any_input@all/places} of the '
            '{d:places.not_checked_although_fits_any_offset_any_input@all/places} OSM-mapped villages and care '
            'facilities ({p:places.not_checked_although_fits_any_offset_any_input@all/places}) had, for at least one of '
            'the three forecast times, a departure time without a checked route (within the model) to any of their ' +
            _HALLS + ' (not official shelters) although the fastest fire-free trip would still fit the 1-hour scenario '
            'window.'),
        'related': ['places.not_checked_although_fits_any_offset_any_input@uiseong_andong_2025/places',
                    'places.not_checked_although_fits_any_offset_any_input@yeongdeok_2025/places'],
        'caution': (
            'Model-relative and tied to the recorded scenarios, the 10-minute departure grid and the 1-hour scenario '
            'window. Of these places, {n:places.no_checked_route_any_offset_any_input@all/places} had no checked route '
            'at any departure time for some forecast time. Window-limited departures are not counted: of the '
            '{d:places.not_checked_although_fits_at_offset_3000s_any_input@all/places} places with an unchecked '
            'departure at +50 minutes, only {n:places.not_checked_although_fits_at_offset_3000s_any_input@all/places} '
            'had a fire-free trip that fits; the others are more than 8 minutes from every candidate destination. A '
            'place outside this count is not "safe". ' + ENTRY_NOTE + ' ' + COMPUTED_WINDOW),
    },
    {
        'id': 'S5',
        'text': (
            'At each place\'s leave-by time, the travel-time-only route to the same destination (one of the place\'s ' +
            _HALLS + ', not official shelters) met predicted flames in at least one of 4 fire '
            'scenarios in {n:travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s} of the '
            '{d:travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s} comparisons whose leave-by time was '
            'earlier than 50 minutes after the forecast time '
            '({p:travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s}), all in Uiseong-Andong, and in '
            'none of the {d:travel_only.fastest_meets_flames@all/pooled#leave_by_3000s} at +50 minutes; where it did, '
            'the checked alternative took {min:travel_only.extra_arrival_s.min@all/pooled} to '
            '{min:travel_only.extra_arrival_s.max@all/pooled} minutes longer (median '
            '{min:travel_only.extra_arrival_s.median@all/pooled} minutes) and was '
            '{km:travel_only.extra_length_m.min@all/pooled} to {km:travel_only.extra_length_m.max@all/pooled} km longer.'),
        'related': ['travel_only.fastest_meets_flames@all/pooled', 'travel_only.fastest_meets_flames@yeongdeok_2025/pooled'],
        'caution': (
            'Only {n:travel_only.fastest_meets_flames@all/pooled} of {d:travel_only.fastest_meets_flames@all/pooled} '
            'comparisons in all; do not generalise. The comparison exists only at each place\'s latest checked '
            'departure and toward its default checked destination; at +50 minutes only destinations within 8 minutes '
            'fit the 1-hour window, so those comparisons are short trips. "Predicted flames" = centre-model flame '
            'contact in at least one scenario member, not an observed fire. In the other '
            '{d:travel_only.clear_pairs_equal_arrival@all/pooled} comparisons the fastest route had no predicted flame '
            'contact and arrived at the same second as the checked route '
            '({n:travel_only.clear_pairs_equal_arrival@all/pooled} of {d:travel_only.clear_pairs_equal_arrival@all/pooled}). '
            + ENTRY_NOTE + ' ' + DEST_NOTE + ' Never describe the checked route as "safe". ' + COMPUTED_LENGTH),
    },
    {
        'id': 'S6',
        'text': (
            'On the road graph used for routing, for {n:redundancy.turn_aware_paths_1@all/places} of the '
            '{d:redundancy.turn_aware_paths_1@all/places} OSM-mapped villages and care facilities '
            '({p:redundancy.turn_aware_paths_1@all/places}), all routes starting from the place\'s mapped road entry '
            'point toward its ' + _HALLS + ' (not official shelters) pass through '
            'at least one common road segment, a single point of failure in the model\'s road network; measured along '
            'the shortest route, the last segment that all routes share ends a median of '
            '{m:redundancy.shared_stretch_m.median@all/places} m from the entry point, and within 100 m for only '
            '{n:redundancy.shared_stretch_within_100m@all/places} of the {d:redundancy.shared_stretch_within_100m@all/places}.'),
        'related': ['redundancy.entry_out_degree_1@all/places', 'redundancy.shared_stretch_m.min@all/places',
                    'redundancy.shared_stretch_m.max@all/places'],
        'caution': (
            'A property of the provisional pre-fire OSM road graph (2025-03-21 snapshot; missing one-way tags assumed '
            'two-way) and of the planner\'s road entry point ' + ENTRY_POINT + ', not a field-verified count of access '
            'roads; travel between the place and that point is not modelled. "Pass through at least one common road '
            'segment" = the largest '
            'set of routes that pairwise share no directed road segment has one route (unit-capacity max-flow = 1, '
            'computed with and without turn restrictions, equal for {n:redundancy.turn_aware_equals_plain@all/places} '
            'of {d:redundancy.turn_aware_equals_plain@all/places} places); it ignores road capacity, travel time and '
            'fire. For {n:redundancy.single_cut_at_entry_node@all/places} of the '
            '{d:redundancy.single_cut_at_entry_node@all/places} the first shared segment is the one leaving the entry '
            'point; lengths are sums of straight edge chords (EPSG:5179). ' + DEST_NOTE + ' ' + COMPUTED_GRAPH),
    },
    {
        'id': 'S7',
        'text': (
            'Every leave-by time in this analysis can be recomputed from the recorded API results: applying the '
            'planner\'s rules to the original attempts recorded by the Route-Check API reproduces the API\'s own '
            'deadline fields for {n:api_check.recorded_equals_planner_rule_on_original@all/pooled} of '
            '{d:api_check.recorded_equals_planner_rule_on_original@all/pooled} place-and-forecast-time cases, all '
            '{d:api_check.displayed_differs_explained_by_recheck@all/pooled} displayed differences are explained by '
            're-checks of timed-out checks, and an independent second implementation recomputes every reported number.'),
        'related': ['api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled'],
        'caution': (
            'Internal consistency of software and recorded data only. It does not validate the forecast, the hazard '
            'model, the road data or real-world safety. The planner displays re-checks, so its deadline equals the '
            'API\'s recorded latest_checked_depart_offset_s for '
            '{n:api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled} of '
            '{d:api_check.displayed_equals_recorded.latest_checked_depart_offset_s@all/pooled} cases. ' + ENTRY_NOTE),
    },
]

_PH = re.compile(r'\{(v|n|d|p|min|km|m):([^}]+)\}')


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
    if kind == 'm':
        return f'{round(e["value"]):,}'
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
    entry = _PH.sub(lambda m: _fmt(m.group(1), numbers[m.group(2)]), ENTRY_NOTE)
    out = ['# Candidate application sentences (MIT Solve 2027)', '',
           '<!-- Generated by research/solve2027-impact/compute.py from NUMBERS.json; do not edit by hand. -->', '',
           'Each sentence and its caution are rendered from [`NUMBERS.json`](NUMBERS.json); the keys they rely on '
           'follow. Every number is model-relative: it concerns fire-scenario members of forecasts produced '
           'retrospectively for the March 2025 fires, not what happened to residents, and is never an evacuation '
           'outcome or casualties avoided. The numbers come from two sources. Verdicts, leave-by times, re-checks and '
           'travel-only results are what the Route-Check API concluded, recorded on the evaluated macOS arm64 host '
           '(planner cache). Fire-free trip times, the 1-hour scenario-window classification, road redundancy and '
           'route lengths were computed by this package from the SHA-verified road graph and hazard packets in a Linux '
           'container: they are not Route-Check API conclusions and not evaluated-host output (NUMBERS.json '
           'uses_graph = true), and every sentence that relies on them says so in its caution. ' + entry +
           ' Departures that the 1-hour scenario window rules out whatever the fire ("window-limited") are never '
           'counted as fire effects. Say "checked route (within the model)", never "safe route". Definitions and '
           'caveats: [README.md](README.md).', '']
    for s in SENTENCES:
        text, caution, keys = render(s, numbers)
        out += [f'## {s["id"]}', '', f'> {text}', '', 'NUMBERS.json keys: ' + ', '.join(f'`{k}`' for k in keys), '',
                f'Caution: {caution}', '']
    return '\n'.join(out)
