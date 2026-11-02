"""Input files of the impact analysis and their identity checks (standard library only).

Inputs (all read-only):
* ``planner/cache/INDEX.json`` and the six cache files it lists for the two 2025 regions
  (schema ``wfg.planner.cache/1``, written by ``planner/scripts/precompute.py`` on the evaluated macOS host);
* ``planner/public/data/regions/<region>/places.geojson`` (origin types, as the planner tags them);
* ``data/routing/graphs/<region>/graph.json`` from ``python tools/fetch_routing_inputs.py`` (SHA-verified release
  archive); only needed for road redundancy and route lengths. Its SHA-256 must equal the ``input_hashes.graph`` that
  the API recorded in every cached route check, and its ``revision`` must equal the recorded ``graph_id``.

Every file is verified by SHA-256 before use; a mismatch stops the run.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent                 # research/solve2027-impact/wfg_impact
PACKAGE_ROOT = HERE.parent                             # research/solve2027-impact
REPO = PACKAGE_ROOT.parents[1]                         # repository root
CACHE_DIR = REPO / 'planner' / 'cache'
PLACES_DIR = REPO / 'planner' / 'public' / 'data' / 'regions'
DEFAULT_ROUTING_DATA = REPO / 'data' / 'routing'

CACHE_SCHEMA = 'wfg.planner.cache/1'
REGIONS = ('uiseong_andong_2025', 'yeongdeok_2025')
REGION_NAMES = {'uiseong_andong_2025': 'Uiseong-Andong', 'yeongdeok_2025': 'Yeongdeok'}
GRID_OFFSETS_S = (0, 600, 1200, 1800, 2400, 3000)     # 10-min departure grid over [0, 3600 s) (precompute --step-min 10)
KST = dt.timezone(dt.timedelta(hours=9))


class InputIdentityError(RuntimeError):
    """An input file is missing or its bytes differ from the recorded identity."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    """Repository-relative POSIX path (used in every provenance record)."""
    return Path(path).resolve().relative_to(REPO).as_posix()


def routing_data_root() -> Path:
    return Path(os.environ.get('WFG_ROUTING_DATA', DEFAULT_ROUTING_DATA)).resolve()


def compact_time(iso: str) -> str:
    """2025-03-24T09:00:00Z -> 20250324T090000Z (the cache file name)."""
    t = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
    return t.strftime('%Y%m%dT%H%M%SZ')


def kst_label(iso: str, offset_s: int = 0) -> str:
    """KST wall-clock label of input time + offset, e.g. '2025-03-24 18:00 KST' (KST = UTC+9, no DST)."""
    t = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')) + dt.timedelta(seconds=offset_s)
    return t.astimezone(KST).strftime('%Y-%m-%d %H:%M KST')


def scope_id(region: str, input_time: str) -> str:
    return f'{region}/{compact_time(input_time)}'


def load_index() -> list[dict]:
    """INDEX.json entries of the two 2025 regions, each verified (bytes + SHA-256) against its cache file."""
    index_path = CACHE_DIR / 'INDEX.json'
    if not index_path.is_file():
        raise InputIdentityError(f'missing {index_path}')
    entries = [e for e in json.loads(index_path.read_text(encoding='utf-8')) if e['region_id'] in REGIONS]
    entries.sort(key=lambda e: (REGIONS.index(e['region_id']), e['input_time']))
    for e in entries:
        p = CACHE_DIR / e['path']
        if not p.is_file():
            raise InputIdentityError(f'missing cache file {p}')
        if p.stat().st_size != e['bytes']:
            raise InputIdentityError(f'{p}: {p.stat().st_size} bytes, INDEX.json records {e["bytes"]}')
        digest = sha256_file(p)
        if digest != e['sha256']:
            raise InputIdentityError(f'{p}: sha256 {digest} != INDEX.json {e["sha256"]}')
        e['abs_path'] = p
        e['scope'] = scope_id(e['region_id'], e['input_time'])
    if len(entries) != 6:
        raise InputIdentityError(f'expected 6 cache files for {REGIONS}, INDEX.json lists {len(entries)}')
    return entries


def load_cache(entry: dict) -> dict:
    doc = json.loads(Path(entry['abs_path']).read_text(encoding='utf-8'))
    if doc.get('schema') != CACHE_SCHEMA:
        raise InputIdentityError(f'{entry["path"]}: schema {doc.get("schema")!r} != {CACHE_SCHEMA}')
    if doc.get('region_id') != entry['region_id'] or doc.get('scenario_set_id') != entry['scenario_set_id']:
        raise InputIdentityError(f'{entry["path"]}: region/scenario set differ from INDEX.json')
    return doc


def places_path(region: str) -> Path:
    return PLACES_DIR / region / 'places.geojson'


def load_places(region: str) -> list[dict]:
    """Point features of places.geojson (properties + lon/lat). The temporary-housing file the planner would add as
    extra destinations does not exist for these regions (checked, because it would change the candidate set)."""
    p = places_path(region)
    if (p.parent / 'temporary_housing.geojson').exists():
        raise InputIdentityError(f'{p.parent}/temporary_housing.geojson exists; the analysis assumes it does not')
    fc = json.loads(p.read_text(encoding='utf-8'))
    out = []
    for f in fc['features']:
        props = dict(f['properties'])
        props['lon'], props['lat'] = f['geometry']['coordinates'][:2]
        out.append(props)
    return out


def graph_path(region: str) -> Path:
    return routing_data_root() / 'graphs' / region / 'graph.json'


def verify_graph(region: str, expected_sha256: str, expected_revision: str | None = None) -> Path:
    """The road graph exactly as the API used it: SHA-256 (and revision) must equal the cache provenance."""
    p = graph_path(region)
    if not p.is_file():
        raise InputIdentityError(f'missing {p}; run: python tools/fetch_routing_inputs.py')
    digest = sha256_file(p)
    if digest != expected_sha256:
        raise InputIdentityError(f'{p}: sha256 {digest} != API provenance input_hashes.graph {expected_sha256}')
    if expected_revision is not None:
        with open(p, 'rb') as f:
            head = f.read(4096).decode('utf-8', 'replace')
        if f'"revision": "{expected_revision}"' not in head and f'"revision":"{expected_revision}"' not in head:
            raise InputIdentityError(f'{p}: revision is not the recorded graph_id {expected_revision}')
    return p


def hazard_path(region: str, input_time: str) -> Path:
    return routing_data_root() / 'latest_inputs_try02' / 'packets' / region / compact_time(input_time) / 'HAZARD.json'


def hazard_window(region: str, input_time: str, expected_sha256: str) -> dict:
    """Scenario window of the recorded hazard packet exactly as the API used it (SHA-256 must equal the cached
    provenance input_hashes.hazard): valid_from, valid_until (s after the input time) and the time step dt (s)."""
    p = hazard_path(region, input_time)
    if not p.is_file():
        raise InputIdentityError(f'missing {p}; run: python tools/fetch_routing_inputs.py')
    digest = sha256_file(p)
    if digest != expected_sha256:
        raise InputIdentityError(f'{p}: sha256 {digest} != API provenance input_hashes.hazard {expected_sha256}')
    hz = json.loads(p.read_text(encoding='utf-8'))
    return {'path': f'data/routing/latest_inputs_try02/packets/{region}/{compact_time(input_time)}/HAZARD.json',
            'sha256': digest, 'valid_from': float(hz['valid_from']), 'valid_until': float(hz['valid_until']),
            'dt': float(hz['dt'])}


def input_files_record(entries: list[dict], with_graphs: bool) -> list[dict]:
    """[{path, sha256, bytes}] of every input file (for NUMBERS.json provenance)."""
    rows = [{'path': rel(CACHE_DIR / 'INDEX.json'), 'sha256': sha256_file(CACHE_DIR / 'INDEX.json'),
             'bytes': (CACHE_DIR / 'INDEX.json').stat().st_size}]
    for e in entries:
        rows.append({'path': rel(e['abs_path']), 'sha256': e['sha256'], 'bytes': e['bytes']})
    for r in REGIONS:
        p = places_path(r)
        rows.append({'path': rel(p), 'sha256': sha256_file(p), 'bytes': p.stat().st_size})
    if with_graphs:
        note = ('from tools/fetch_routing_inputs.py (release research-final-20261015, archive sha256 '
                'd7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202)')
        for r in REGIONS:
            p = graph_path(r)
            rows.append({'path': 'data/routing/graphs/%s/graph.json' % r, 'sha256': sha256_file(p),
                         'bytes': p.stat().st_size, 'note': note})
        for e in entries:
            p = hazard_path(e['region_id'], e['input_time'])
            rows.append({'path': f'data/routing/latest_inputs_try02/packets/{e["region_id"]}/'
                                 f'{compact_time(e["input_time"])}/HAZARD.json',
                         'sha256': sha256_file(p), 'bytes': p.stat().st_size, 'note': note + '; only valid_until and dt are read'})
    return rows
