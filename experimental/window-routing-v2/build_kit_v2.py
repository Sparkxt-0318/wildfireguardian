"""Build kit v2 (PLAN.md): a separately identified development kit for certified routing beyond one hour.

Never modifies a frozen kit. The parent is the request-window kit built by experimental/window-routing/build_kit.py
(candidate WFG-request-window-routing-20261029). Its manifest is re-verified file by file before copying; the overlay
in stack-v2/ (hashes sealed in SOURCE_SHA256.json) is applied; queue hashes are refreshed; KIT_IDENTITY.json and a new
CANDIDATE_MANIFEST.json name the v2 kit and its parent.

  python -B build_kit_v2.py --parent PARENT_KIT --out OUT
"""
from pathlib import Path
import argparse, hashlib, json, shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PARENT_ID = 'WFG-request-window-routing-20261029'
V2_ID = 'WFG-request-window-routing-v2-20261112'
FROZEN_ROOTS = [REPO / 'integration', REPO / 'experimental/window-routing']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def overlay_files():
    return sorted(p for p in (HERE / 'stack-v2').rglob('*') if p.is_file() and '__pycache__' not in p.parts)


def check_sealed():
    sealed = json.loads((HERE / 'SOURCE_SHA256.json').read_text())
    have = {p.relative_to(HERE).as_posix(): sha(p) for p in overlay_files()}
    if have != sealed:
        raise ValueError('stack-v2 differs from SOURCE_SHA256.json: %s' % sorted(set(have.items()) ^ set(sealed.items())))
    return sealed


def verify_parent(parent):
    m = json.loads((parent / 'CANDIDATE_MANIFEST.json').read_text())
    if m.get('candidate_id') != PARENT_ID:
        raise ValueError('Parent is not the request-window kit: %s' % m.get('candidate_id'))
    for p, h in m['files'].items():
        if sha(parent / p) != h:
            raise ValueError('Parent kit changed: ' + p)
    return m


def build(out, parent):
    out, parent = Path(out).resolve(), Path(parent).resolve()
    for root in FROZEN_ROOTS + [parent]:
        if out == root.resolve() or root.resolve() in out.parents:
            raise ValueError('Refusing to build into a frozen or parent kit: ' + str(out))
    if out.exists():
        raise FileExistsError('Use a fresh output directory: ' + str(out))
    sealed = check_sealed()
    pm = verify_parent(parent)
    shutil.copytree(parent, out, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for p in sealed:
        rel = Path(p).relative_to('stack-v2'); t = out / rel; t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / p, t)
    for q in (out / 'queues').glob('*.json'):
        d = json.loads(q.read_text())
        for j in d.get('jobs', []):
            if not j.get('source_root'):
                continue
            j['core_sha256'] = sha(out / 'routing_candidate/baseline/routing-package/routing/core.py')
            for n in j.get('phaseB_sha256', {}):
                j['phaseB_sha256'][n] = sha(out / 'phaseB' / n)
            for n in j.get('checker_sha256', {}):
                j['checker_sha256'][n] = sha(out / 'routing_candidate/baseline' / n)
        q.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    ident = {'candidate_id': V2_ID, 'parent_candidate_id': PARENT_ID,
             'parent_manifest_sha256': sha(parent / 'CANDIDATE_MANIFEST.json'),
             'overlay_sha256': sealed, 'status': 'v2 development kit - NOT the frozen kit'}
    (out / 'KIT_IDENTITY.json').write_text(json.dumps(ident, indent=2, sort_keys=True) + '\n')
    (out / 'README_KIT.md').write_text('# Kit v2 (development)\n\nv2 development kit - NOT the frozen kit. Built by '
                                       'experimental/window-routing-v2/build_kit_v2.py from %s. See PLAN.md.\n' % PARENT_ID)
    files = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'CANDIDATE_MANIFEST.json'}
    man = dict(schema='wfg.latest-kit.manifest/1', candidate_id=V2_ID, parent_candidate_id=PARENT_ID,
               parent_manifest_sha256=ident['parent_manifest_sha256'], files=files)
    (out / 'CANDIDATE_MANIFEST.json').write_text(json.dumps(man, indent=2, sort_keys=True) + '\n')
    return man, pm


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    m, _ = build(a.out, a.parent)
    print(json.dumps({'candidate_id': m['candidate_id'], 'files': len(m['files']),
                      'manifest_sha256': sha(a.out / 'CANDIDATE_MANIFEST.json')}))
