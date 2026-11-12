"""Build an OPT-IN kit variant with outward dyadic snapping of radiation receiver boxes (F-3.4 option B).

Starts from a built request-window kit (experimental/window-routing/build_kit.py output), verifies its manifest, and
copies it to a fresh directory. It then patches exactly one place: in HybridRadiationBounds._coefficients, the
receiver box passed to the exact-rational analytic kernel (RationalKernel.source_receiver_box) is first snapped
OUTWARD to the grid 2**-k metres. Lower ends are floored and upper ends ceiled, and containment of the original box
is asserted in exact arithmetic on every call.

Why the result is still a valid enclosure: source_receiver_box(source, R) returns [lower over the inner rectangle,
upper over the outer rectangle] of the configuration factor, valid for every receiver point in R. A snapped box
R' ⊇ R is a superset of receiver points, so its lower bound is <= every value in R and its upper bound is >= every
value in R. The enclosure for R stays valid and becomes at most slightly looser. The analytic tier is intersected with
the radial binary64 tier exactly as before.

Nothing else changes: same thresholds, members, contact checking and publication rules. The frozen kit and the
window kit are not modified. The variant gets its own candidate id and manifest.

  python build_snap_kit.py --base WINDOW_KIT --out OUT --snap-bits 10
"""
import argparse, hashlib, json, shutil
from pathlib import Path

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
TARGET = 'routing_candidate/baseline/hybrid_radiation.py'
OLD = "            self._guard();a,b=self._analytic_kernel.source_receiver_box(self._rectangles[i],box)\n"
NEW = ("            self._guard();a,b=self._analytic_kernel.source_receiver_box(self._rectangles[i],_snap_out(box,%d))\n")
HELPER = '''

def _snap_out(box,bits):
    """F-3.4 option B: snap a receiver box OUTWARD to the dyadic grid 2**-bits (exact Fractions); assert containment."""
    import math as _m
    from fractions import Fraction as _F
    s=1<<bits;x0,x1,y0,y1=(_F(v) for v in box)
    out=(_F(_m.floor(x0*s),s),_F(_m.ceil(x1*s),s),_F(_m.floor(y0*s),s),_F(_m.ceil(y1*s),s))
    if not(out[0]<=x0 and out[1]>=x1 and out[2]<=y0 and out[3]>=y1):raise ArithmeticError('SNAP_NOT_OUTWARD')
    return out
'''


def build(base, out, bits):
    base = Path(base).resolve(); out = Path(out).resolve()
    if out.exists():
        raise SystemExit('Use a fresh output directory: %s' % out)
    man = json.loads((base / 'CANDIDATE_MANIFEST.json').read_text())
    bad = [p for p, h in man['files'].items() if sha(base / p) != h]
    if bad:
        raise SystemExit('Base kit does not match its manifest: %s' % bad[:5])
    shutil.copytree(base, out, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    t = out / TARGET; src = t.read_text()
    if src.count(OLD) != 1:
        raise SystemExit('Patch anchor not found exactly once in %s' % TARGET)
    src = src.replace(OLD, NEW % bits) + HELPER
    t.write_text(src)
    for p in (out / 'queues').glob('*.json'):
        q = json.loads(p.read_text())
        for j in q.get('jobs', []):
            for n in j.get('checker_sha256', {}):
                j['checker_sha256'][n] = sha(out / 'routing_candidate/baseline' / n)
        p.write_text(json.dumps(q, indent=2, sort_keys=True) + '\n')
    files = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'CANDIDATE_MANIFEST.json'}
    m = dict(schema='wfg.latest-kit.manifest/1', candidate_id='WFG-request-window-routing-20261029+snap%d-F34B' % bits,
             parent_candidate_id=man['candidate_id'], parent_manifest_sha256=sha(base / 'CANDIDATE_MANIFEST.json'),
             patch={'file': TARGET, 'snap_bits': bits, 'base_sha256': man['files'][TARGET], 'patched_sha256': sha(t)}, files=files)
    (out / 'CANDIDATE_MANIFEST.json').write_text(json.dumps(m, indent=2, sort_keys=True) + '\n')
    return m


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--snap-bits', type=int, required=True)
    a = ap.parse_args(); m = build(a.base, a.out, a.snap_bits)
    print(json.dumps({'candidate_id': m['candidate_id'], 'patch': m['patch']}))
