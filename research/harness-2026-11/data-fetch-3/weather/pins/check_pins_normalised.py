#!/usr/bin/env python3
"""Check a rebuilt workspace against a committed pins manifest, allowing exactly ONE known volatile field.

environment.py:984 writes biome_validation.json with checked_utc = pd.Timestamp.now(), so a faithful rebuild can never
reproduce that file's bytes. This checker:
  - hashes every pinned file and requires an exact sha256 match, EXCEPT environment/biome_validation.json;
  - for that file only: requires that the ONLY difference is the value of "checked_utc" (one occurrence), by substituting
    the pinned value (given below per manifest) into the rebuilt text and requiring the result's sha256 == the pin.
No other normalisation is applied. Exit 0 only if every pin passes on these terms.

usage: check_pins_normalised.py MANIFEST.json DATA_ROOT
"""
import hashlib, json, re, sys
from pathlib import Path

VOLATILE = 'environment/biome_validation.json'
PINNED_CHECKED_UTC = {  # manifest sha256 -> the checked_utc string inside the pinned biome_validation.json
    '286f4c47d1c21d12485b4ec2079ce09c698c21af73d64037921b34284e6592c2': '2026-11-12T09:43:38.262390+00:00',  # US2024 night-1
    'f70e52b00bfd8eaf12743cd60599238e72abefca80cbc0802c51a52a8ea2005a': '2026-11-12T14:54:31.848341+00:00',  # part-a night-1
}
RX = re.compile(rb'"checked_utc": "[^"]*"')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main(argv):
    man, root = Path(argv[1]), Path(argv[2])
    msha = sha(man.read_bytes())
    pins = json.loads(man.read_text())
    exact = missing = 0
    bad, notes = [], []
    for rel, want in sorted(pins.items()):
        p = root / rel
        if not p.is_file():
            missing += 1; bad.append(('MISSING', rel)); continue
        b = p.read_bytes()
        if sha(b) == want:
            exact += 1; continue
        if rel == VOLATILE and msha in PINNED_CHECKED_UTC:
            hits = RX.findall(b)
            if len(hits) == 1:
                fixed = RX.sub(b'"checked_utc": "' + PINNED_CHECKED_UTC[msha].encode() + b'"', b)
                if sha(fixed) == want:
                    notes.append(f'{rel}: equal after substituting the pinned checked_utc '
                                 f'(rebuilt value {hits[0].decode()})'); continue
        bad.append(('MISMATCH', rel))
    print(f'manifest {msha[:8]}: {len(pins)} pins, exact {exact}, volatile-normalised {len(notes)}, '
          f'missing {missing}, mismatched {len(bad) - missing}')
    for n in notes:
        print('  NOTE', n)
    for kind, rel in bad[:50]:
        print(' ', kind, rel)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
