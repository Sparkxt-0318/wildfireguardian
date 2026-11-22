"""ArrivalScenario and its builder (F-9.3 DESIGN.md @df2c797).

Build paths (all existing, all unchanged):
  * source 'c651'                 -> integration/src/wfg_latest/build_packet.py (the recorded build command)
  * source 'zones', rule 'sampled' -> api.adapters.spread_zones.build_packet (the API 1.8 adapter child)
  * rule 'envelope' or 'sampled' from rasters / perimeter sequences -> F-DYN packet child (fdyn/_packet_child.py),
    which drives the unchanged writer through the same injection points; the envelope uses the per-cell law
    (source_law_version wfg.fdyn.envelope-per-cell/1; the kit independent checker does not apply).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
WFG = REPO / 'integration' / 'src' / 'wfg_latest'
INPUTS = REPO / 'data' / 'routing' / 'latest_inputs_try02'
FDYN = REPO / 'research' / 'harness-2026-11' / 'F-DYN'
SOURCES = ('c651', 'zones', 'perimeter_sequence', 'arrival_raster')
RULES = ('random_draws', 'sampled', 'envelope')


@dataclass
class ArrivalScenario:
    source: str
    rule: str
    region: str
    start_tag: str                       # recorded input time tag (e.g. 20250325T190000Z)
    label: str
    provenance: dict = field(default_factory=dict)
    known: dict = field(default_factory=dict)        # name -> bool array (north-up, scenario grid); reported only
    zone_plan: dict | None = None        # zones/sampled: the spread_zones plan, verbatim
    arrival_lo_h: np.ndarray | None = None   # rasters/perimeters: hours since t0 on the KFS export grid
    arrival_hi_h: np.ndarray | None = None
    horizon_h: float = 1.0
    quantum_s: float = 300.0
    graph: Path | None = None            # full-grid graph for raster/perimeter sources
    support: str | None = None           # SUPPORT_WIRING_RULE.md: None | 'c651_unknown/1' (c651) | 'known' (rasters/perimeters)

    def validate(self):
        if self.source not in SOURCES or self.rule not in RULES:
            raise ValueError(f'unknown source/rule {self.source}/{self.rule}')
        if self.source == 'c651' and self.rule != 'random_draws':
            raise ValueError('c651 uses its own random draws')
        if self.source == 'zones' and self.rule == 'sampled' and self.zone_plan is None:
            raise ValueError('zones/sampled needs the spread_zones plan')
        if self.source in ('perimeter_sequence', 'arrival_raster'):
            if self.arrival_lo_h is None or (self.rule == 'envelope' and self.arrival_hi_h is None):
                raise ValueError('raster/perimeter sources need arrival_lo_h (and arrival_hi_h for the envelope)')
            if self.graph is None:
                raise ValueError('raster/perimeter sources are built on the full grid: give the full-grid graph')
        for k, v in self.known.items():
            if np.asarray(v).dtype != bool:
                raise ValueError(f'known[{k}] must be boolean')
        if self.support is not None:
            ok = {'c651': ('c651_unknown/1',), 'perimeter_sequence': ('known',), 'arrival_raster': ('known',)}
            if self.support not in ok.get(self.source, ()):
                raise ValueError(f'SUPPORT_NOT_WIRED {self.source}/{self.support} (SUPPORT_WIRING_RULE.md section 2)')
            if self.support == 'known' and self.rule == 'envelope':      # SUPPORT_WIRING_RULE.md correction 1
                raise ValueError('SUPPORT_NOT_WIRED: per-cell envelope + mask (masks apply to scalar-law packets only)')
            if self.support == 'known' and not self.known:
                raise ValueError('SUPPORT_PROVENANCE_MISSING: support="known" needs known flags')
        return self

    def digest(self):
        h = hashlib.sha256(json.dumps({'source': self.source, 'rule': self.rule, 'region': self.region,
                                       'start': self.start_tag, 'label': self.label, 'prov': self.provenance},
                                      sort_keys=True, default=str).encode())
        if self.support is not None:             # absent by default: digests of existing scenarios are unchanged
            h.update(('support:' + self.support).encode())
        for a in (self.arrival_lo_h, self.arrival_hi_h):
            if a is not None:
                h.update(np.ascontiguousarray(a, dtype='<f8').tobytes())
        return h.hexdigest()


def _recorded_window(region, tag):
    md = json.loads((INPUTS / 'packets' / region / tag / 'NATIVE_METADATA.json').read_text())
    return md.get('regional', {}).get('window_rows_cols_north_up'), md


def _iso(tag):
    return f'{tag[0:4]}-{tag[4:6]}-{tag[6:8]}T{tag[9:11]}:00:00Z'


def support_args(sc: ArrivalScenario, work: Path, meta: dict) -> list:
    """SUPPORT_WIRING_RULE.md: the supplied/1 mask = AND of the scenario's known flags (export grid, north-up);
    perimeter sequences whose in-domain no-polygon cells become unknown before the horizon are refused."""
    flags = {k: np.asarray(v, bool) for k, v in sc.known.items()}
    if any(v.shape != (79, 237) for v in flags.values()):
        raise ValueError('SUPPORT_SHAPE: known flags must be on the KFS_01 export grid (79, 237)')
    mask = np.logical_and.reduce(list(flags.values()))
    if sc.source == 'perimeter_sequence':
        import datetime as _dt
        t0 = _dt.datetime(2025, 3, 22, 2, 24, tzinfo=_dt.timezone.utc)
        start = _dt.datetime.strptime(sc.start_tag, '%Y%m%dT%H%M%SZ').replace(tzinfo=_dt.timezone.utc)
        tn = _dt.datetime.fromisoformat(sc.provenance['perimeter_times'][-1])
        uncovered_in_domain = mask & ~np.isfinite(sc.arrival_lo_h)
        tn_after_start_h = (tn - start).total_seconds() / 3600.0
        if uncovered_in_domain.any() and tn_after_start_h < sc.horizon_h:
            raise ValueError(f'SUPPORT_TIME_DEPENDENT: {int(uncovered_in_domain.sum())} in-domain cells in no polygon '
                             f'become unknown at t_n (+{tn_after_start_h:g} h) before the horizon ({sc.horizon_h:g} h)')
    p = work / 'support.npz'
    np.savez_compressed(p, support=mask)
    prov = {'source': sc.source, 'flags': sorted(flags), 'rule_text': 'support = AND of the ArrivalScenario known flags',
            'scenario_digest': sc.digest()}
    meta['support'] = {'rule': 'supplied/1', 'unsupported_cells_export_grid': int((~mask).sum()), **prov}
    return ['--support-mask', str(p), '--support-rule', 'supplied/1', '--support-provenance', json.dumps(prov, sort_keys=True)]


def build(sc: ArrivalScenario, out: Path, python: str = sys.executable) -> dict:
    """Build the packet for a scenario; returns a small summary. out must not exist (the writer is write-once)."""
    sc.validate()
    out = Path(out)
    meta = {'interface': 'wfg.f93.arrival-scenario/1', 'source': sc.source, 'rule': sc.rule, 'label': sc.label,
            'scenario_digest': sc.digest(),
            'known_flags': {k: {'cells': int(np.asarray(v).size), 'unknown_cells': int((~np.asarray(v)).sum())}
                            for k, v in sc.known.items()}}
    if sc.source == 'c651':
        win, md = _recorded_window(sc.region, sc.start_tag)
        event = md['construction']['parent_forecast']['event_id']
        cli = (REPO / 'research' / 'harness-2026-11' / 'F-9.3' / 'support_mask' / 'build_packet_f93.py'
               if sc.support == 'c651_unknown/1' else WFG / 'build_packet.py')
        cmd = [python, '-I', '-B', str(cli), '--graph',
               str(REPO / 'data' / 'routing' / 'graphs' / sc.region / 'graph.json'),
               '--export-dir', str(INPUTS / 'exports' / event), '--event', event, '--cutoff', _iso(sc.start_tag),
               '--region', sc.region, '--out', str(out)]
        if win is not None:
            cmd += ['--window-json', json.dumps(win)]
        if sc.support == 'c651_unknown/1':
            cmd += ['--support-rule', 'c651_unknown/1']
            meta['support'] = {'rule': 'c651_unknown/1', 'cli': 'support_mask/build_packet_f93.py'}
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('C651_BUILD_FAILED ' + (r.stdout + r.stderr)[-800:])
    elif sc.source == 'zones' and sc.rule == 'sampled':
        sys.path.insert(0, str(REPO))
        from api.adapters import spread_zones as SZ
        SZ.build_packet(sc.zone_plan, graph_path=REPO / 'data' / 'routing' / 'graphs' / sc.region / 'graph.json',
                        out_dir=out, python=python)
    else:
        # raster / perimeter / zones-envelope: the F-DYN path (full grid, unchanged writer, injection points)
        work = out.parent / (out.name + '.inputs')
        work.mkdir(parents=True, exist_ok=False)
        lo_p = work / 'arrival_lo.npz'
        aff = np.array([375.0, 0.0, 1085250.0, 0.0, -375.0, 1845375.0])
        np.savez(lo_p, arrival_h=sc.arrival_lo_h, affine_transform=aff, t0_utc='2025-03-22T02:24:00+00:00')
        cmd = [python, str(FDYN / 'fdyn' / 'build.py'), '--region', sc.region, '--start', sc.start_tag,
               '--horizon-h', str(sc.horizon_h), '--arrival', str(lo_p), '--arrival-source',
               json.dumps({'f93_source': sc.source, **sc.provenance}), '--quantum-s', str(sc.quantum_s),
               '--domain', 'full_grid', '--graph', str(sc.graph), '--out', str(out)]
        if sc.support == 'known':
            cmd += support_args(sc, work, meta)
        if sc.rule == 'envelope':
            hi_p = work / 'arrival_hi.npz'
            np.savez(hi_p, arrival_h=sc.arrival_hi_h, affine_transform=aff, t0_utc='2025-03-22T02:24:00+00:00')
            cmd += ['--arrival-hi', str(hi_p), '--arrival-variant', 'envelope']
        else:
            cmd += ['--arrival-variant', f'{sc.source}_sampled', '--member-set', 'central']
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
        if r.returncode != 0:
            raise RuntimeError('F93_FDYN_BUILD_FAILED ' + (r.stdout + r.stderr)[-1500:])
    (out / 'F93_INTERFACE.json').write_text(json.dumps(meta, indent=1))
    return meta
