"""Recompute a one-hour recovery packet on its road grid, independently of the forecast bridge."""
import argparse
import json
from pathlib import Path

import numpy as np


def rectangle_kernel(height, width, resolution, vertical_separation):
    """Solid angle of a square cell from a receiver, divided by the full sphere."""
    dy, dx = np.mgrid[1-height:height, 1-width:width] * resolution
    z = vertical_separation
    half = resolution / 2
    def corner(x, y):
        return np.arctan2(x * y, z * np.sqrt(x * x + y * y + z * z))
    solid_angle = (corner(dx + half, dy + half) + corner(dx - half, dy - half)
                   - corner(dx - half, dy + half) - corner(dx + half, dy - half))
    return solid_angle / (4 * np.pi)


def check(packet):
    hazard = json.loads((packet / 'HAZARD.json').read_bytes())
    meta = json.loads((packet / 'NATIVE_METADATA.json').read_bytes())
    height, width = meta['shape']
    law = meta['construction']['assumptions']
    duration = law['burning_duration_s']
    horizon = hazard['valid_until']
    assert 0 < horizon < duration and hazard['valid_from'] == 0
    resolution = hazard['grid']['resolution']
    kernel = rectangle_kernel(height, width, resolution, law['emission_height_m'] - law['receiver_height_m'])
    power = (law['fuel_load_kg_m2'] * law['heat_of_combustion_j_kg'] * law['consumed_fraction']
             * law['radiative_fraction'] * law['atmospheric_transmissivity'] / duration)
    target = meta['affine_transform']
    with np.load(packet / 'FULL.npz') as f:
        a = f['affine']
        r = round((target[5] - a[5]) / a[4])
        c = round((target[2] - a[2]) / a[0])
        crop = np.s_[r:r+height, c:c+width]
        born = f['ignition_time_s'][:, crop[0], crop[1]]
        seen = f['initial_burned'][crop]
        remaining = np.where(seen, np.maximum(0, duration - (f['cutoff_unix'] - f['last_detection_unix'][crop])), 0)
        q = f['q'][:, :, crop[0], crop[1]]
    with np.load(packet / 'constructed_arrays.npz') as z:
        assert np.array_equal(z['native_hourly_valid'], np.isfinite(q))
        assert np.array_equal(born, z['ignition_time_s'])
        assert np.array_equal(remaining > 0, z['current_active'])
    source_end = float(remaining.max())
    max_diff = 0.0
    checks = 0
    for k, member in enumerate(hazard['members']):
        birth = born[k]
        # All sampled new sources have residence longer than this particular horizon.
        knots = np.unique(np.r_[0., horizon, source_end, birth[np.isfinite(birth)]])
        knots = knots[(knots >= 0) & (knots <= horizon)]
        assert np.array_equal(knots, member['breakpoints'])
        assert len(member['flame']) == len(member['flux']) == len(knots) - 1
        for i, start in enumerate(knots[:-1]):
            active = ((remaining > 0) & (start < source_end)) | (birth <= start)
            routed_flame = np.array(member['flame'][i]).reshape(height, width)[::-1]
            assert np.array_equal(active, routed_flame)
            watts = np.zeros((height, width))
            for row, col in zip(*np.nonzero(active)):
                y = height - 1 - row
                x = width - 1 - col
                watts += kernel[y:y+height, x:x+width] * power
            if active.any():
                watts += 1e-8 * max(1., watts.max())
            routed = np.array(member['flux'][i]).reshape(height, width)[::-1]
            error = float(np.abs(watts / 1000 - routed).max())
            assert error < 1e-10, (packet, k, i, error)
            max_diff = max(max_diff, error)
            checks += active.size
    return dict(incident=meta['construction']['parent_forecast']['event_id'], graph=meta['graph_revision'],
                issue=meta['issued_at'], packet_sha256=meta['identity']['forecast_export_sha256'],
                member_interval_cell_checks=checks, max_flux_difference_kw_m2=max_diff)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packets', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rows = [check(p) for p in args.packets]
    result = json.dumps(rows, indent=2)
    if args.output:
        args.output.write_text(result + '\n')
    else:
        print(result)
