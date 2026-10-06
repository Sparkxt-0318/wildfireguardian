"""Build an isolated organized routing development package; preserve sources."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

SOURCE = Path('/Users/jp/Documents/Codex/2026-10-05/files-pasted-by-the-user-integrate/outputs/routing_preparation_integration_20261005_v1/candidate')
DEST = Path('/Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_code_refactor_20261006_v1')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if any(DEST.iterdir()):
        raise RuntimeError('Refusing to overwrite nonempty development package')
    hashes = {str(p.relative_to(SOURCE)): digest(p) for p in sorted(SOURCE.rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts and p.name != '.DS_Store'}
    mapping = {}
    for name in hashes:
        path = Path(name)
        if path.parts[0] in {'routing', 'tests', 'fixtures', 'vendor'}:
            target = path
        elif path.parts[0] in {'evidence', 'reviews'}:
            target = Path('archive/delivery') / path
        elif path.suffix == '.md':
            target = Path('docs') / path
        elif path.suffix == '.py':
            target = Path('archive/legacy_scripts') / path
        else:
            target = Path('archive/delivery') / path
        out = DEST / target
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / name, out)
        mapping[name] = str(target)
    for folder in ['verification', 'tools']:
        (DEST / folder).mkdir(exist_ok=True)
    shutil.copy2(SOURCE / 'evidence/CONTINUITY_REPLAY_FIXTURE.json', DEST / 'fixtures/continuity_replay.json')
    shutil.copy2(SOURCE / 'evidence/ROAD_INTEGRATION_SMOKE.json', DEST / 'verification/road_witness.json')
    parent = SOURCE.parent
    for name in ['OWNER_HANDOFF.md', 'BENCHMARK_REPORT.md', 'CORRECTNESS_REPORT.md', 'REPRODUCE.md', 'MANIFEST.json', 'STATUS.json']:
        out = DEST / 'archive/preparation_integration' / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parent / name, out)
    for folder in ['evidence', 'review']:
        shutil.copytree(parent / folder, DEST / 'archive/preparation_integration' / folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
    record = {'source': str(SOURCE), 'source_hashes': hashes, 'path_mapping': mapping,
              'interpretation': 'Historical artifacts copied without editing; source measurements are not refactor measurements.'}
    (DEST / 'verification/SOURCE_PROVENANCE.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'source_files': len(hashes), 'development_folder': str(DEST)}, indent=2))


if __name__ == '__main__':
    main()
