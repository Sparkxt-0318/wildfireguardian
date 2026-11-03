"""Provenance and attribution: which numbers depend on this package's own road-graph computation (and say so wherever
they are published), which inputs every headline number records, and the citations and versions in the README.

The source flags are checked from both sides: test_cache_only.py proves that every uses_graph = false number is
reproduced with data/routing/ unreachable; here, perturbing only the road-graph-derived values must change nothing but
numbers flagged uses_graph (and uses_hazard where trip times or the window are involved).
"""
import collections
import copy
import csv
import html
import json
import re

from conftest import PACKAGE_ROOT
import wfg_impact
from wfg_impact import analysis, figures, numbers as numbers_mod, sentences, sources

NUMBERS = json.loads((PACKAGE_ROOT / 'NUMBERS.json').read_text(encoding='utf-8'))
N = NUMBERS['numbers']
README = (PACKAGE_ROOT / 'README.md').read_text(encoding='utf-8')
SENTENCES_MD = (PACKAGE_ROOT / 'APPLICATION_SENTENCES.md').read_text(encoding='utf-8')

# families written out here independently of numbers.py: the 1-hour window classification and fire-free trip times
# (graph.json travel_ticks x HAZARD.json dt, window from HAZARD.json) and the graph-only road metrics
WINDOW_FAMILIES = ('window_limited.', 'window_limited_among_not_checked.', 'not_checked_although_fits.',
                   'deadline_set_by.', 'cell_window.', 'places.not_checked_although_fits_', 'places.window_limited_at_',
                   'no_checked_route_any_offset.trip_fits_', 'fastest_trip_s.', 'trip_model.')
GRAPH_ONLY_FAMILIES = ('redundancy.', 'redundancy_x.', 'travel_only.extra_length_m.')


def _metric(key: str) -> str:
    return key.split('@')[0]


def _is_window(key: str) -> bool:
    m = _metric(key)
    return m.startswith(WINDOW_FAMILIES) or re.fullmatch(r'deadline\.latest_\d{4}s\.set_by_(window|fire_or_limits)', m)


def test_every_number_records_its_sources():
    counts = {'window': 0, 'graph': 0, 'cache': 0}
    for key, e in N.items():
        if _is_window(key):
            assert e['uses_graph'] is True and e['uses_hazard'] is True, key
            counts['window'] += 1
        elif _metric(key).startswith(GRAPH_ONLY_FAMILIES):
            assert e['uses_graph'] is True and e['uses_hazard'] is False, key
            counts['graph'] += 1
        else:                                   # aggregates of the recorded cache and place files only
            assert e['uses_graph'] is False and e['uses_hazard'] is False, key
            counts['cache'] += 1
    assert min(counts.values()) > 100, counts


def test_headline_inputs_include_graph_and_hazard_packets_where_used():
    for key, h in NUMBERS['headline'].items():
        e = N[key]
        assert (h['uses_graph'], h['uses_hazard']) == (e['uses_graph'], e['uses_hazard'])
        caches = [p for p in h['inputs'] if p.startswith('planner/cache/') and p.endswith('Z.json')]
        graphs = sorted(p for p in h['inputs'] if p.endswith('/graph.json'))
        hazards = sorted(p for p in h['inputs'] if p.endswith('/HAZARD.json'))
        regions = sorted({p.split('/')[2] for p in caches})
        assert graphs == ([f'data/routing/graphs/{r}/graph.json' for r in regions] if e['uses_graph'] else []), key
        # the HAZARD packet of exactly the cache files (input times) the number is computed from
        expect = sorted(f'data/routing/latest_inputs_try02/packets/{p.split("/")[2]}/{p.split("/")[3][:-5]}/HAZARD.json'
                        for p in caches)
        assert hazards == (expect if e['uses_hazard'] else []), key
        for p in graphs + hazards:
            assert h['input_sha256'][p] == NUMBERS['inputs'][p]['sha256'], (key, p)
    # S2's window-corrected headline numbers cannot be computed from the cache alone: their inputs say so
    for t in ('0000', '1800'):
        h = NUMBERS['headline'][f'not_checked_although_fits.offset_{t}s@uiseong_andong_2025/pooled']
        assert 'data/routing/graphs/uiseong_andong_2025/graph.json' in h['input_sha256']
        assert sum(p.endswith('HAZARD.json') for p in h['input_sha256']) == 3
    note = NUMBERS['inputs']['data/routing/latest_inputs_try02/packets/yeongdeok_2025/20250325T190000Z/HAZARD.json']['note']
    assert note.endswith('only valid_from, valid_until and dt are read')


def _rebuild(result, mutate):
    r = copy.deepcopy(result)
    mutate(r)
    analysis.classify_window(r['records'], r['metas'], r['redundancy'])     # fits and deadline_set_by again
    return numbers_mod.build(r)


def _changed(a: dict, b: dict) -> set:
    assert set(a) == set(b)
    return {k for k in a if any(a[k].get(f) != b[k].get(f) for f in ('value', 'numerator', 'denominator'))}


def _faster_trips(r):
    """As if graph.json travel_ticks or HAZARD.json dt were different: every fire-free trip takes half as long."""
    for x in r['redundancy']:
        x['trip_by_dest_s'] = {k: (None if v is None else v // 2) for k, v in x['trip_by_dest_s'].items()}
    for p in r['pairs']:
        if p.get('trip_model_s') is not None:
            p['trip_model_s'] //= 2


def _other_roads(r):
    """As if graph.json's roads were different: other redundancy values, shared stretches and route lengths."""
    for x in r['redundancy']:
        x['turn_aware_paths'] = {2: 3, 3: 4}.get(x['turn_aware_paths'], x['turn_aware_paths'])
    for x in [x for x in r['redundancy'] if x['turn_aware_paths'] == 1][::2]:
        x['turn_aware_paths'] = 2
    for x in r['redundancy']:
        x['entry_out_degree'] += 1
        x['cut_at_entry_node'] = not x['cut_at_entry_node']
        if x['shared_stretch_m'] is not None:
            x['shared_stretch_m'] *= 2
    for p in r['pairs']:
        for k in ('checked_length_m', 'fastest_length_m', 'extra_length_m'):
            if p.get(k) is not None:
                p[k] *= 2


def test_source_flags_follow_the_real_dependencies(path_a_result):
    base = numbers_mod.build(path_a_result)
    assert _changed(base, numbers_mod.build(copy.deepcopy(path_a_result))) == set()
    for mutate, hazard, must in ((_faster_trips, True, ('fastest_trip_s.median@all/places', 'trip_model.equals_travel_only@all/pooled',
                                                        'window_limited.offset_3000s@all/pooled',
                                                        'not_checked_although_fits.offset_3000s@uiseong_andong_2025/pooled')),
                                 (_other_roads, False, ('redundancy.turn_aware_paths_1@all/places',
                                                        'redundancy.shared_stretch_m.median@all/places',
                                                        'redundancy_x.cases@all/pooled#rc1',
                                                        'travel_only.extra_length_m.median@all/pooled'))):
        changed = _changed(base, _rebuild(path_a_result, mutate))
        assert set(must) <= changed, (mutate.__name__, set(must) - changed)
        wrong = sorted(k for k in changed if not N[k]['uses_graph'] or (hazard and not N[k]['uses_hazard']))
        assert not wrong, (mutate.__name__, wrong[:20])


SOURCE_PHRASES = ('computed by this package', 'Linux container', 'not evaluated-host output')
# the blanket attributions the package once made: every number = what the Route-Check API concluded / read from the cache
BLANKET = re.compile(r'describ(?:e|es|ing) what the (?:WildfireGuardian )?Route-Check API concluded'
                     r'|read from the recorded cache, not recomputed|Every number describes', flags=re.I)


def _prose(text: str) -> str:
    """Whitespace collapsed and implicitly concatenated string literals joined, so a phrase split over lines is found."""
    return re.sub(r'''(['"]) [rbf]{0,2}\1''', '', ' '.join(text.split()))


def _svg_text(path) -> str:
    """The text of an SVG drawn with svg.fonttype 'none': one <text> element per wrapped line, joined by spaces."""
    parts = re.findall(r'<text[^>]*>([^<]*)</text>', path.read_text(encoding='utf-8'))
    return ' '.join(' '.join(html.unescape(p) for p in parts).split())


def test_attribution_is_split_wherever_numbers_are_published():
    statement = NUMBERS['statement'] + ' ' + ' '.join(NUMBERS['attribution'].values())
    assert 'evaluated macOS arm64 host' in statement and all(p in statement for p in ('Linux container', 'not evaluated-host output'))
    assert 'Every number describes what' not in statement
    assert '(planner cache and place files; uses_graph = false)' in NUMBERS['statement']   # place-file counts too
    assert any('not evaluated-host output' in c for c in NUMBERS['caveats'])
    # every number that depends on this package's own computation says so in its own definition
    for key, e in N.items():
        if e['uses_graph']:
            assert all(p in e['definition'] for p in SOURCE_PHRASES), key
    # README: no claim that every number is read from the cache; the headline Source column follows the flags
    assert 'they are read from the recorded cache, not recomputed by the router' not in README
    assert all(p in README for p in SOURCE_PHRASES) and '2-vCPU' not in README
    for key in numbers_mod.HEADLINE_KEYS:
        row = re.search(rf'^\| `{re.escape(key)}` \| [^|]+ \| ([^|]+) \|', README, flags=re.M)
        assert row and row.group(1).strip() == ('computed here' if N[key]['uses_graph'] else 'recorded'), key
    # application sentences: the preamble splits the sources; every sentence relying on a computed number says so
    preamble = SENTENCES_MD.split('## S1')[0]
    assert 'recorded on the evaluated macOS arm64 host' in preamble and all(p in preamble for p in SOURCE_PHRASES[1:])
    assert 'it describes what the Route-Check API concluded' not in SENTENCES_MD
    relying = 0
    for s in sentences.SENTENCES:
        _, caution, keys = sentences.render(s, N)
        if any(N[k]['uses_graph'] for k in keys):
            relying += 1
            assert all(p in caution for p in SOURCE_PHRASES), s['id']
    assert relying == 5                         # S2-S6
    # figure footers (committed SVGs): the recorded / computed split of that figure
    for stem, fig in (('fig1_checked_share_by_offset', 'fig1'), ('fig2_deadline_by_origin_type', 'fig2'),
                      ('fig3_travel_only_vs_checked', 'fig3')):
        text = _svg_text(PACKAGE_ROOT / 'figures' / f'{stem}.svg')
        assert figures.SOURCES[fig] in text and 'evaluated macOS arm64 host' in text, stem
        assert all(p in text for p in SOURCE_PHRASES) and 'road entry point' in text, stem
        assert 'Planning aid only — not for live evacuation operations.' in text, stem      # the exact footer text
    # no blanket attribution left anywhere: the code (module docstrings included) and every published text
    texts = {p.relative_to(PACKAGE_ROOT).as_posix(): p.read_text(encoding='utf-8')
             for p in [PACKAGE_ROOT / 'compute.py', PACKAGE_ROOT / 'verify.py',
                       *sorted((PACKAGE_ROOT / 'wfg_impact').glob('*.py')), PACKAGE_ROOT / 'NUMBERS.json']}
    texts.update({'README.md': README, 'APPLICATION_SENTENCES.md': SENTENCES_MD})
    texts.update({f'figures/{p.name}': _svg_text(p) for p in sorted((PACKAGE_ROOT / 'figures').glob('*.svg'))})
    assert {'compute.py', 'verify.py', 'wfg_impact/__init__.py', 'wfg_impact/numbers.py', 'wfg_impact/sentences.py',
            'NUMBERS.json'} <= set(texts) and len(texts) >= 19, sorted(texts)
    for name, text in texts.items():
        m = BLANKET.search(_prose(text))
        assert not m, (name, m and m.group(0))
    for old in ('All results are model-relative: they describe what the Route-Check API concluded for recorded',
                "'Every number describes what the WildfireGuardian Route-Check API concluded for recorded fire-scenario '",
                "it describes what the '\n           'Route-Check API concluded for",
                'depend on the host running this package: they are read from the recorded cache, not recomputed by'):
        assert BLANKET.search(_prose(old)), old
    package_doc = ' '.join(wfg_impact.__doc__.split())
    assert 'two sources' in package_doc and all(p in package_doc for p in ('evaluated macOS arm64 host', *SOURCE_PHRASES[1:]))


# columns of the committed tables that hold this package's own road-graph / HAZARD values (written out independently of
# the README, which must name exactly these as "computed here")
COMPUTED_COLUMNS = {
    'origin_cases.csv': {'fastest_fire_free_trip_s', 'deadline_set_by'} |
                        {f'trip_fits_window_{t:04d}s' for t in sources.GRID_OFFSETS_S},
    'travel_only_pairs.csv': {'checked_length_m', 'fastest_length_m', 'extra_length_m'},
    'redundancy_places.csv': {'entry_out_degree', 'turn_aware_paths', 'plain_paths', 'single_cut_at_entry_node',
                              'min_cut_edges_source_side', 'min_cut_osm_ways', 'common_edges_on_every_route',
                              'shared_stretch_m', 'fastest_fire_free_trip_s'},
    'fig1_checked_share_by_offset.csv': {'model_no_route_trip_fits', 'unresolved_trip_fits', 'window_limited',
                                         'model_no_route_window_limited', 'unresolved_window_limited'},
    'fig2_deadline_by_origin_type.csv': {'set_by_window', 'set_by_fire_or_limits'},
    'fig3_travel_only_vs_checked.csv': {'extra_length_m'},
}


def test_readme_names_the_table_columns_computed_here():
    import fnmatch
    files = README.split('\n## Files\n', 1)[1].split('\n## ', 1)[0]
    prose = ' '.join(files.split())
    assert 'Table columns marked "computed here"' in prose and 'not evaluated-host output' in prose
    for name, expected in COMPUTED_COLUMNS.items():
        header = (PACKAGE_ROOT / 'tables' / name).read_text(encoding='utf-8').splitlines()[0].split(',')
        assert expected <= set(header), name
        row = next(r for r in files.splitlines() if r.startswith(f'| `tables/{name}`') or
                   (name.startswith('fig') and r.startswith('| `tables/fig*_*.csv`')))
        part = row.split('computed here:', 1)[1]
        if name.startswith('fig'):
            part = part.split(name[:4] + ' ', 1)[1].split(';')[0]
        named = {c for tok in re.findall(r'`([^`]+)`', part) for c in fnmatch.filter(header, tok)}
        assert named == expected, (name, named ^ expected)
    # the row counts typed in those rows
    pairs = list(csv.DictReader((PACKAGE_ROOT / 'tables' / 'travel_only_pairs.csv').open(encoding='utf-8')))
    n_pairs = N['travel_only.pairs@all/pooled']['numerator']
    assert len(pairs) == n_pairs and f'paired with a village or care-facility case ({n_pairs};' in files
    kinds = collections.Counter(r['origin_type'] for r in
                                csv.DictReader((PACKAGE_ROOT / 'tables' / 'redundancy_places.csv').open(encoding='utf-8')))
    n_places, n_research = N['places@all/places']['value'], N['research_origins@all/places']['value']
    assert kinds == {'village': kinds['village'], 'care_facility': n_places - kinds['village'], 'research': n_research}
    assert N['redundancy.places@all/places']['value'] == n_places
    assert (f'one row per checked place ({n_places}) and per recorded research-mission origin ({n_research}, '
            '`origin_type` research, not used in any number)') in files
    # the README's "Key format" lists every subset used in a key
    key_format = ' '.join(README.split('\n## Key format\n', 1)[1].split())
    for subset in {k.split('#', 1)[1] for k in N if '#' in k}:
        assert f'`#{subset}`' in key_format, subset
    # "nearest" would read as the straight-line nearest: the trip is to whichever candidate is quickest to reach
    for key, e in [*N.items(), *NUMBERS['headline'].items()]:
        if key.startswith(('fastest_trip_s.', 'places.window_limited_at_offset_')):
            assert 'quickest-to-reach' in e['definition'] and 'nearest' not in e['definition'], key
    assert all(h['definition'] == N[k]['definition'] for k, h in NUMBERS['headline'].items())
    assert 'fire-free trip to the nearest candidate' not in README


# "from the place" (village, facility, ...) is only correct as "from the place's road entry point"
FROM_PLACE = re.compile(r"\bfrom (?:the|each|a|every|its|their) (?:places?|villages?|hamlets?|(?:care )?facilit(?:y|ies)"
                        r"|origins?)\b(?!'s (?:mapped )?road entry point)", flags=re.I)


def _entry_note(text: str) -> bool:
    return 'road entry point' in text and 'at most 2 km' in text and 'not modelled' in text


def test_departures_are_said_to_start_at_the_road_entry_point():
    preamble = SENTENCES_MD.split('## S1')[0]
    for text in (preamble, figures.FOOTER, ' '.join(NUMBERS['caveats'])):
        assert _entry_note(text)
    s1_text = sentences.render(sentences.SENTENCES[0], N)[0]
    assert 'checked vehicle departures from the road entry point of each of' in s1_text and 'at most 2 km' in s1_text
    s3_text = sentences.render(sentences.SENTENCES[2], N)[0]
    assert "no checked route from the place's road entry point to any of its" in s3_text
    # each sentence and its caution may be quoted alone: no sentence or caution places a departure at the mapped place,
    # and every caution carries the entry-point note (rendered here and in the committed APPLICATION_SENTENCES.md)
    cautions = re.findall(r'^Caution: (.+)$', SENTENCES_MD, flags=re.M)
    quoted = re.findall(r'^> (.+)$', SENTENCES_MD, flags=re.M)
    assert len(cautions) == len(quoted) == len(sentences.SENTENCES)
    for s, md_text, md_caution in zip(sentences.SENTENCES, quoted, cautions):
        text, caution, _ = sentences.render(s, N)
        assert (md_text, md_caution) == (text, caution), s['id']
        for part in (text, caution):
            assert not FROM_PLACE.search(part), (s['id'], FROM_PLACE.search(part))
        assert _entry_note(caution), s['id']
    assert not FROM_PLACE.search(SENTENCES_MD) and not FROM_PLACE.search(figures.FOOTER)
    for bad in ('no checked route from the place to any', 'trips from each village', 'routes from the care facilities'):
        assert FROM_PLACE.search(bad), bad
    assert not FROM_PLACE.search("route from the place's road entry point to any")
    g = lambda k: N[k]  # noqa: E731
    med, mx = g('entry_distance_m.median@all/places')['value'], g('entry_distance_m.max@all/places')['value']
    o500, o1k = g('entry_distance_over_500m@all/places'), g('entry_distance_over_1000m@all/places')
    readme = ' '.join(README.split())
    assert (f'at most 2 km away (median {med:,} m, maximum {mx:,} m; {o500["numerator"]} of {o500["denominator"]} places are '
            f'more than 500 m and {o1k["numerator"]} more than 1 km away') in readme
    lo, hi = g('fastest_trip_s.min@all/places#care_facility')['value'], g('fastest_trip_s.max@all/places#care_facility')['value']
    cmin, cmax = g('entry_distance_m.min@all/places#care_facility')['value'], g('entry_distance_m.max@all/places#care_facility')['value']
    assert (f'The fastest fire-free trip from their road entry points to a candidate destination takes {lo}-{hi} s') in readme
    assert f'their entry points lie {cmin:,}-{cmax:,} m from the mapped facilities' in readme
    assert 'fire-free drive from a candidate destination' not in readme


def test_planner_line_citations_name_their_commit():
    commit = numbers_mod.PLANNER_LINES_COMMIT
    assert commit == '0cd95db2'
    cite = re.compile(r'(plan|cache|adapter|controller|staticData)\.ts\b[^;]*?\blines? \d')
    texts = [e['definition'] for e in N.values()] + list(NUMBERS['definitions_common'].values())
    cited = [t for t in texts if cite.search(t)]
    assert len(cited) > 500
    assert all(f'at commit {commit}' in t for t in cited)
    assert f'## Definitions (replicated exactly from the planner; line numbers at commit {commit})' in README
    for module in ('planner_rules.py', 'analysis.py', 'api_rules.py', 'numbers.py'):
        assert commit in (PACKAGE_ROOT / 'wfg_impact' / module).read_text(encoding='utf-8'), module


def _pins(path) -> dict:
    out = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^([A-Za-z0-9_.-]+)==([^\s#]+)', line.strip())
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


def test_readme_records_the_exact_library_versions():
    req = _pins(PACKAGE_ROOT / 'requirements.txt')
    cons = _pins(sources.REPO / 'constraints-routing.txt')
    m = re.search(r'Versions used for the committed outputs: (.+?)\n\n', README, flags=re.S)
    line = ' '.join(m.group(1).split())
    assert 'Python 3.12.3' in line and f'numpy {cons["numpy"]}' in line
    for name in ('pandas', 'matplotlib', 'networkx', 'pytest', 'pillow'):
        assert f'{name} {req[name]}' in line, name


def test_owner_decision_proposes_one_link_line_for_the_frozen_research_readme():
    section = README.split('\n## Owner decision\n', 1)[1].split('\n## ', 1)[0]
    assert 'research/README.md' in section and 'FROZEN_GIT_BLOBS.json' in section
    m = re.search(r'```markdown\n(.+?)\n```', section, flags=re.S)
    line = m.group(1)
    assert '\n' not in line and line.startswith('- [solve2027-impact/](solve2027-impact/README.md): ')
    assert 'safe' not in line.lower()
    # the same text as a one-sentence paragraph, matching that file's paragraph style
    blocks = re.findall(r'```markdown\n(.+?)\n```', section, flags=re.S)
    assert len(blocks) == 2 and blocks[0] == line and '\n' not in blocks[1]
    assert blocks[1].startswith('[`solve2027-impact/`](solve2027-impact/README.md) holds model-relative ')
    assert blocks[1].split(' holds ', 1)[1] == line.split(': ', 1)[1]


def test_readme_counts_of_cache_only_numbers_match():
    cache_only = sum(1 for e in N.values() if not e['uses_graph'])
    assert f'(`uses_graph` = false, {cache_only:,} of the {len(N):,} numbers)' in ' '.join(README.split())
