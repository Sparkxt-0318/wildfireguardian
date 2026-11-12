"""Build a perturbed copy of a frozen regional hazard packet (F-4.2 margin experiments).

The packet is rebuilt by the unchanged packet writer (integration/src/wfg_latest: packets.write_regional_packet with the
vendored radiation operator and router validator) from the same clock-bound forecast export, event, cutoff, window and
seed as the frozen packet. The only change is a deterministic transform applied to the bridge's ignition draws:

  advance  delta >= 0 s :  b -> b - delta          (every drawn first-new ignition happens delta seconds earlier)
  rate     s > 0        :  b -> b / s              (fire timing scaled about the cutoff; s > 1 = faster)

Infinite draws (no ignition in that member) stay infinite, present fire (cells already burning at the cutoff, active on
[0, R_max)) is not changed, and the burning duration T is unchanged. With delta = 0 / s = 1 the rebuilt files must be
byte-identical to the frozen packet; `--verify-identity` checks that.

Run in its own interpreter (the writer installs namespace packages):
  python -I -B perturbed_packet.py --region uljin_2022 --cutoff 20220304T060000Z --advance 120 --out DIR
"""
import argparse, hashlib, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / 'integration/src/wfg_latest'
EVENT = {'uljin_2022': 'KFS_02', 'miryang_2022': 'KFS_11', 'hongseong_2023': 'KFS_05',
         'uiseong_andong_2025': 'KFS_01', 'yeongdeok_2025': 'KFS_01'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--region', required=True)
    ap.add_argument('--cutoff', required=True, help='tag, e.g. 20220304T060000Z')
    ap.add_argument('--inputs', type=Path, default=REPO / 'data/routing')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--advance', type=float)
    g.add_argument('--rate', type=float)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--verify-identity', action='store_true', help='require byte identity with the frozen packet (identity transform only)')
    a = ap.parse_args(argv)
    sys.path.insert(0, str(SRC))
    import build_packet as BP
    BP.install_radiation()
    import contract as CT
    import packets as P
    import numpy as np
    frozen = a.inputs / 'latest_inputs_try02/packets' / a.region / a.cutoff
    summ0 = json.loads((frozen / 'BUILD_SUMMARY.json').read_text())
    event = summ0.get('event_id') or EVENT[a.region]
    win = summ0.get('window')
    graph_path = a.inputs / 'graphs' / a.region / 'graph.json'
    graph = json.loads(graph_path.read_text())
    iso, tag = CT.normalize_cutoff(a.cutoff)[0], CT.tag(a.cutoff)
    exp = a.inputs / 'latest_inputs_try02/exports' / event
    npz = exp / ('FORECAST_%s.npz' % tag); recp = exp / ('FORECAST_RECORD_%s.json' % tag)
    rec = json.loads(recp.read_text())
    epsg = int(graph['crs'].split(':', 1)[1])
    original = P.B.draw_ignitions
    if a.advance is not None:
        if not a.advance >= 0:
            raise SystemExit('advance must be >= 0')
        transform = lambda ev: np.where(np.isfinite(ev), ev - a.advance, ev)
        spec = {'kind': 'advance', 'delta_s': a.advance}
    else:
        if not a.rate > 0:
            raise SystemExit('rate must be > 0')
        transform = lambda ev: np.where(np.isfinite(ev), ev / a.rate, ev)
        spec = {'kind': 'rate', 'scale': a.rate}

    def perturbed(q, scenario_count, seed, horizon_s):
        return transform(original(q, scenario_count, seed, horizon_s))
    P.B.draw_ignitions = perturbed
    out, hz, summ = P.write_regional_packet(graph, graph_path, npz, rec, sha(recp), iso, epsg, a.out,
                                            event_id=event, region_id=a.region, window=win)
    summ.update(perturbation=spec, frozen_packet=str(frozen), region=a.region, event_id=event, cutoff=iso, window=win)
    names = ('HAZARD.json', 'REPORT.json', 'NATIVE_METADATA.json', 'constructed_arrays.npz')

    def normalized(p):
        # The writer embeds the radiation module's absolute host path (identity.radiation_operator.module); the frozen
        # packets carry the original packaging host's path. Everything else, including the module SHA-256, must match.
        if p.suffix != '.json':
            return sha(p)
        def strip(o):
            if isinstance(o, dict):
                return {k: (None if k == 'module' and 'sha256' in o else strip(v)) for k, v in o.items()}
            if isinstance(o, list):
                return [strip(v) for v in o]
            return o
        return hashlib.sha256(json.dumps(strip(json.loads(p.read_text())), sort_keys=True).encode()).hexdigest()
    same = {n: normalized(Path(out) / n) == normalized(frozen / n) for n in names}
    # HAZARD.json flux maps come from the radiation FFT; arm64-macOS (frozen) and x86-Linux builds differ in the last bits.
    # Report the largest difference; every other field (flame sets, breakpoints, ids, identities) must match exactly.
    h0 = json.loads((frozen / 'HAZARD.json').read_text()); h1 = json.loads((Path(out) / 'HAZARD.json').read_text())
    mx_abs = mx_rel = 0.0; flame_same = len(h0['members']) == len(h1['members'])
    for m0, m1 in zip(h0['members'], h1['members']):
        f0 = np.asarray(m0['flux']); f1 = np.asarray(m1['flux'])
        if f0.shape != f1.shape or m0['flame'] != m1['flame'] or m0['breakpoints'] != m1['breakpoints'] or m0['id'] != m1['id']:
            flame_same = False; continue
        d = np.abs(f0 - f1); mx_abs = max(mx_abs, float(d.max(initial=0)))
        mx_rel = max(mx_rel, float((d / np.maximum(np.abs(f0), 1e-300)).max(initial=0)))
    for m in (h0, h1):
        m.pop('members'); m['provenance']['identity']['radiation_operator'].pop('module')
    same['HAZARD.json:non_flux_fields'] = flame_same and h0 == h1
    same['HAZARD.json:flux_max_abs_diff_kW_m2'] = mx_abs
    same['HAZARD.json:flux_max_rel_diff'] = mx_rel
    summ['identical_to_frozen'] = same
    (Path(out) / 'PERTURBATION.json').write_text(json.dumps(summ, indent=1, default=str) + '\n')
    print(json.dumps({'out': str(out), 'perturbation': spec, 'identical_to_frozen': same,
                      'ignitions_per_member': summ['ignitions_per_member']}))
    exact = ('REPORT.json', 'NATIVE_METADATA.json', 'constructed_arrays.npz', 'HAZARD.json:non_flux_fields')
    if a.verify_identity and not (all(same[k] for k in exact) and same['HAZARD.json:flux_max_rel_diff'] < 1e-9):
        raise SystemExit('IDENTITY_TRANSFORM_NOT_BYTE_IDENTICAL')


if __name__ == '__main__':
    main()
