"""envelope_footprint variant files (ENVELOPE_FOOTPRINT_RULE.md @3fbd229, adopted before computing).

The burn set is the one defined in SOUND_ENVELOPE_RULE.md (finite kriged TOA | FIRMS detection | firing AHI pixel
buffered set); it is read as the finite footprint of variants/envelope_sound_lo.npz, which sound.py wrote from that
definition. lo = 0 (event ignition) and hi = 1e6 h on the burn set, NaN elsewhere; the static hazard law (whole window
[0, H) burning for burn set | present fire) is applied in _packet_child.py from the plan's footprint_mask.

    python3 research/harness-2026-11/F-DYN/fdyn/footprint.py --burn-set-from research/harness-2026-11/F-DYN/variants/envelope_sound_lo.npz \
        --out-dir research/harness-2026-11/F-DYN/variants
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

HI_BEYOND_H = 1.0e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--burn-set-from', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    with np.load(a.burn_set_from, allow_pickle=False) as z:
        burn = np.isfinite(z['arrival_h'])
        aff, t0 = z['affine_transform'], str(z['t0_utc'])
    prov = {'rule': 'ENVELOPE_FOOTPRINT_RULE.md @3fbd229 (adopted)',
            'burn_set_source': str(a.burn_set_from), 'burn_set_source_sha256':
                hashlib.sha256(a.burn_set_from.read_bytes()).hexdigest(),
            'label': 'BOUND RELATIVE TO THE FINAL MAPPED BURN SET (lo = ignition; no cell cleared within the horizon); '
                     'nothing about fire outside the mapped burn set; single implementation, not independently checked'}
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for name, val in (('envelope_footprint_lo', 0.0), ('envelope_footprint_hi', HI_BEYOND_H)):
        arr = np.where(burn, val, np.nan)
        np.savez_compressed(a.out_dir / f'{name}.npz', arrival_h=arr, affine_transform=aff, t0_utc=t0, variant=name,
                            provenance=json.dumps(prov), timestamp_exact=burn)
    print(json.dumps({'burn_set_cells': int(burn.sum())}))


if __name__ == '__main__':
    main()
