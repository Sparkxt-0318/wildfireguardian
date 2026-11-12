#!/usr/bin/env python3
"""Write the input pins manifest that research/forecast-v2/scripts/pipeline.Environment(input_sha256=...) accepts.

usage: make_input_manifest.py DATA_ROOT OUT.json [EVENT ...]

DATA_ROOT is the environment directory (it holds events.json and regions/). Keys are paths relative to
DATA_ROOT.parent, which is how Environment._verify_path names them, for example "environment/events.json". The manifest covers:
  - every file directly in DATA_ROOT (events.json, biome_classes.json, ...);
  - every .tif/.tiff/.json/.csv/.txt/.npz under DATA_ROOT/regions/<event>/ (the events in events.json, or only those named);
  - DATA_ROOT.parent/baseline-terrain/<event>/elevation_m_375m.tif. This is created as a byte copy of the rebuilt
    regions/<event>/terrain/elevation_m_375m.tif when missing, the layout Environment.terrain_gradient reads.
Output: {"<relative path>": "<sha256>", ...}, sorted.
"""
import hashlib, json, shutil, sys
from pathlib import Path

SUFFIXES = {'.tif', '.tiff', '.json', '.csv', '.txt', '.npz'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    root, out, events = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), sys.argv[3:]
    base = root.parent
    events = events or sorted(e['id'] for e in json.loads((root / 'events.json').read_text()))
    pins = {}
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() in SUFFIXES:
            pins[str(p.relative_to(base))] = sha(p)
    for ev in events:
        for p in sorted((root / 'regions' / ev).rglob('*')):
            if p.is_file() and p.suffix.lower() in SUFFIXES and not p.name.endswith('.part.tif'):
                pins[str(p.relative_to(base))] = sha(p)
        src = root / 'regions' / ev / 'terrain' / 'elevation_m_375m.tif'
        dst = base / 'baseline-terrain' / ev / 'elevation_m_375m.tif'
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        if dst.exists():
            pins[str(dst.relative_to(base))] = sha(dst)
    out.write_text(json.dumps(dict(sorted(pins.items())), indent=1) + '\n')
    print(f'{len(pins)} pinned files for {len(events)} events -> {out}')


if __name__ == '__main__':
    main()
