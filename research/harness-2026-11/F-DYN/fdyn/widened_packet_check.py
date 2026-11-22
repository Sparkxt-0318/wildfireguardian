"""WIDENED_GRAPH_RULE.md P2 (packet) and P3 (support), one widened packet against its v3.7 `/2` packet.

P2, on every export cell (mapped by the +N offset; HAZARD flat layout is south-up row-major):
    breakpoints equal per member; flame equal per member and bin; flux within A1 (rel <= 1e-9 or abs <= 1e-12 kW/m2);
    scenario ids differ; valid_until equal; present_fire_cells and present_fire_enclosure equal (§8(ii));
  on padding cells: flame false in every bin of every member (§8(i): catches padding read as burned).
P3: HAZARD support and npz support are false on exactly the padding cells and true on every export cell.

    python3 fdyn/widened_packet_check.py --old V37_PACKET --new WIDENED_PACKET --pad 14 [--out ROW.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REL, ABS = 1e-9, 1e-12


def load(d: Path):
    return (json.loads((d / 'HAZARD.json').read_text()), json.loads((d / 'NATIVE_METADATA.json').read_text()))


def check(old: Path, new: Path, n: int) -> dict:
    ho, mo = load(old)
    hn, mn = load(new)
    go, gn = ho['grid'], hn['grid']
    Wo, Ho, Wn, Hn = go['width'], go['height'], gn['width'], gn['height']
    r = {'old': str(old), 'new': str(new), 'pad': n}
    r['grid_offset_ok'] = (Wn == Wo + 2 * n and Hn == Ho + 2 * n and gn['x0'] == go['x0'] - n * go['resolution']
                           and gn['y0'] == go['y0'] - n * go['resolution'] and gn['resolution'] == go['resolution'])
    rows, cols = np.meshgrid(np.arange(Ho), np.arange(Wo), indexing='ij')
    idx = ((rows + n) * Wn + (cols + n)).ravel()           # old flat (south-up, row-major) -> new flat
    pad = np.ones(Hn * Wn, bool)
    pad[idx] = False
    r['padding_cells'] = int(pad.sum())
    ok_bp = ok_flame = ok_padflame = ok_sup = True
    flux_bad, max_rel, max_abs = 0, 0.0, 0.0
    if len(ho['members']) != len(hn['members']):
        r['members_equal_count'] = False
        r['P2'] = r['P3'] = False
        return r
    for a, b in zip(ho['members'], hn['members']):
        if a['breakpoints'] != b['breakpoints']:
            ok_bp = False
            continue
        fa, fb = np.asarray(a['flame'], bool), np.asarray(b['flame'], bool)
        ok_flame &= bool(np.array_equal(fa, fb[:, idx]))
        ok_padflame &= not bool(fb[:, pad].any())
        xa, xb = np.asarray(a['flux'], float), np.asarray(b['flux'], float)[:, idx]
        d = np.abs(xa - xb)
        rel = np.where(np.abs(xa) > 0, d / np.where(np.abs(xa) > 0, np.abs(xa), 1), np.where(d > 0, np.inf, 0))
        bad = (d > ABS) & (rel > REL)
        flux_bad += int(bad.sum())
        max_abs = max(max_abs, float(d.max(initial=0)))
        max_rel = max(max_rel, float(np.where(np.isfinite(rel), rel, 0).max(initial=0)))
        sb = np.asarray(b['support'], bool)
        ok_sup &= bool((~sb[:, pad]).all() and sb[:, idx].all())
    with np.load(new / 'constructed_arrays.npz', allow_pickle=False) as z:
        sn = np.asarray(z['support'], bool)                 # (S, H, W) north-up
    padn = np.flipud(pad.reshape(Hn, Wn))                   # north-up padding mask (symmetric, flip for clarity)
    npz_sup_ok = bool((~sn[:, padn]).all() and sn[:, ~padn].all())
    ids_o, ids_n = [m['id'] for m in ho['members']], [m['id'] for m in hn['members']]
    r.update({'breakpoints_equal': ok_bp, 'flame_equal_on_export_cells': ok_flame, 'flame_false_on_padding': ok_padflame,
              'flux_cells_outside_A1': flux_bad, 'flux_max_abs_diff': max_abs, 'flux_max_rel_diff': max_rel,
              'ids_differ': ids_o != ids_n and not (set(ids_o) & set(ids_n)),
              'valid_until_equal': ho['valid_until'] == hn['valid_until'],
              'present_fire_cells_equal': {f'{int(k.split(",")[0]) + n},{int(k.split(",")[1]) + n}': v   # 'row,col' +N
                                           for k, v in mo['present_fire_cells'].items()} == mn['present_fire_cells'],
              'present_fire_enclosure_equal': mo['present_fire_enclosure'] == mn['present_fire_enclosure'],
              'hazard_support_false_exactly_on_padding': ok_sup, 'npz_support_false_exactly_on_padding': npz_sup_ok})
    r['P2'] = bool(r['grid_offset_ok'] and ok_bp and ok_flame and ok_padflame and flux_bad == 0 and r['ids_differ']
                   and r['valid_until_equal'] and r['present_fire_cells_equal'] and r['present_fire_enclosure_equal'])
    r['P3'] = bool(ok_sup and npz_sup_ok and r['padding_cells'] == 9632)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', type=Path, required=True)
    ap.add_argument('--new', type=Path, required=True)
    ap.add_argument('--pad', type=int, default=14)
    ap.add_argument('--out', type=Path, default=None)
    a = ap.parse_args()
    r = check(a.old, a.new, a.pad)
    if a.out:
        a.out.write_text(json.dumps(r, indent=1))
    print(json.dumps(r))


if __name__ == '__main__':
    main()
