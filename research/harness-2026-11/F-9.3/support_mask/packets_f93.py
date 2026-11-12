"""Versioned writer wrapper wfg.f93.support-writer/1: the frozen packet writer plus an optional support channel.

Design and the rule for what counts as unknown: DESIGN.md in this folder (fixed before this code).

The frozen writer integration/src/wfg_latest/packets.py is imported, never edited. support_mask=None hands off
completely: the call is exactly packets.write_regional_packet(*args, **kw) and nothing here touches its output.
With a mask, the frozen writer writes the packet first, then only the support channel is rewritten, the packet gets a
distinct writer identity, and the build fails on any hard condition of DESIGN.md.

The caller must already have the frozen writer importable as `packets` with its vendored namespaces installed (as
integration/src/wfg_latest/build_packet.py does; build_packet_f93.py here does the same).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
VERSION = 'wfg.f93.support-writer/1'
RULES = ('c651_unknown/1', 'supplied/1')
SUPPORT_SEMANTICS = ('support=false: the source says nothing about this cell (unknown, not no-fire); rule %s; the router '
                     'reports UNSUPPORTED for any route occupying such a cell and withholds global optimality / '
                     'infeasibility claims (pessimistic tier-A instance of the F-9.3 three-way rule)')
TOL = 1e-6   # s, as F-DYN fdyn/consistency.py: exact b + T vs the writer's rounded-up float end


class SupportError(ValueError):
    pass


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _base():
    import packets as P          # the frozen writer, made importable by the caller
    return P


def write_regional_packet(*args, support_mask=None, support_rule=None, support_provenance=None, **kw):
    """Same signature and return value as the frozen writer, plus the optional support channel."""
    if support_mask is None:
        if support_rule is not None or support_provenance is not None:
            raise SupportError('SUPPORT_RULE_WITHOUT_MASK')
        return _base().write_regional_packet(*args, **kw)          # complete hand-off: no byte comes from here
    if support_rule not in RULES:
        raise SupportError(f'SUPPORT_RULE_UNKNOWN {support_rule!r}')
    if support_rule == 'c651_unknown/1' and not (isinstance(support_mask, str) and support_mask == 'c651_unknown/1'):
        raise SupportError('SUPPORT_RULE_MISMATCH: c651_unknown/1 is derived from the packet; pass support_mask="c651_unknown/1"')
    if support_rule == 'supplied/1':
        if isinstance(support_mask, str):
            raise SupportError('SUPPORT_SHAPE: supplied/1 needs a boolean array')
        if not support_provenance:
            raise SupportError('SUPPORT_PROVENANCE_MISSING: supplied/1 needs a non-empty support_provenance')
        m = np.asarray(support_mask)
        if m.dtype != bool or m.ndim != 2:
            raise SupportError(f'SUPPORT_SHAPE: need a boolean [H, W] array, got {m.dtype} {m.shape}')
    graph = args[0]
    out, hz, summ = _base().write_regional_packet(*args, **kw)
    try:
        hz, summ = apply_support(Path(out), graph, summ, support_mask, support_rule, support_provenance)
    except Exception:
        # never leave a half-rewritten packet that still looks like a v1 packet
        Path(out, 'SUPPORT_WRITE_FAILED').write_text('the support channel was not applied; do not use this packet\n')
        raise
    return out, hz, summ


def c651_unknown(arrays) -> np.ndarray:
    """DESIGN.md rule c651_unknown/1, native north-up: True = supported."""
    u_state = np.asarray(arrays['mask__unknown_cumulative_state'], bool)
    u_q = np.asarray(arrays['mask__policy_assigned_zero'], bool) & ~np.asarray(arrays['mask__known_burned'], bool) & ~u_state
    return ~(u_state | u_q)


def _load_npz(p):
    with np.load(p, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def apply_support(out: Path, graph, summ, support_mask, rule, provenance):
    base_files = {n: _sha(out / n) for n in ('HAZARD.json', 'REPORT.json', 'NATIVE_METADATA.json', 'constructed_arrays.npz')}
    hz0 = json.loads((out / 'HAZARD.json').read_text())
    rep0 = json.loads((out / 'REPORT.json').read_text())
    md0 = json.loads((out / 'NATIVE_METADATA.json').read_text())
    arr0 = _load_npz(out / 'constructed_arrays.npz')
    S, H, W = arr0['support'].shape
    mask = c651_unknown(arr0) if rule == 'c651_unknown/1' else np.asarray(support_mask)
    if mask.dtype != bool or mask.shape != (H, W):
        raise SupportError(f'SUPPORT_SHAPE: need bool {(H, W)}, got {mask.dtype} {mask.shape}')
    # hard condition: never unsupported where the packet itself asserts fire
    asserted = np.asarray(arr0['current_active'], bool) | np.isfinite(np.asarray(arr0['ignition_time_s'], float)).any(0)
    flame_any = np.zeros(H * W, bool)
    for m in hz0['members']:
        flame_any |= np.asarray(m['flame'], bool).any(0)
    asserted |= np.flipud(flame_any.reshape(H, W))                     # HAZARD row 0 = south -> north-up
    conflict = int((asserted & ~mask).sum())
    if conflict:
        raise SupportError(f'SUPPORT_CONFLICT: {conflict} unsupported cells carry asserted fire')
    flat = np.flipud(mask).ravel()                                     # to HAZARD layout
    row = flat.tolist()
    hz = json.loads(json.dumps(hz0))
    for m in hz['members']:
        m['support'] = [list(row) for _ in range(len(m['breakpoints']) - 1)]
    writer = {'version': VERSION, 'rule': rule, 'support_mask_sha256': hashlib.sha256(np.packbits(mask).tobytes()
              + str(mask.shape).encode()).hexdigest(), 'unsupported_cells': int((~mask).sum()), 'cells': int(mask.size),
              'provenance': provenance if provenance is not None else
              {'derived_from': 'constructed_arrays.npz masks as written by the frozen writer',
               'definition': 'U_state = mask__unknown_cumulative_state; U_q = mask__policy_assigned_zero & ~mask__known_burned & ~U_state; support = ~(U_state | U_q)'}}

    def stamp(identity):
        identity['base_packet_writer_sha256'] = identity['packet_writer_sha256']
        identity['packet_writer_sha256'] = _sha(HERE)
        identity['support_writer'] = writer

    stamp(hz['provenance']['identity'])
    hz['provenance']['support_semantics'] = SUPPORT_SEMANTICS % rule
    from routing.validation import validate_hazard                    # the router's own validator (vendored by the build)
    validate_hazard(graph, hz)
    rep = json.loads(json.dumps(rep0)); md = json.loads(json.dumps(md0))
    stamp(rep['native_metadata']['identity']); stamp(md['identity'])
    for d in (rep['native_metadata'], md):
        d['support_channel'] = SUPPORT_SEMANTICS % rule
    arr = dict(arr0)
    arr['support'] = np.broadcast_to(mask, (S, H, W)).copy()
    # write (the frozen writer's serialisation, byte for byte in form)
    with (out / 'HAZARD.json').open('w') as f:
        json.dump(hz, f, allow_nan=False, separators=(',', ':')); f.write('\n')
    for name, obj in (('REPORT.json', rep), ('NATIVE_METADATA.json', md)):
        with (out / name).open('w') as f:
            json.dump(obj, f, allow_nan=False, indent=1); f.write('\n')
    np.savez_compressed(out / 'constructed_arrays.npz', **arr)
    self_check(out, hz0, rep0, arr0, mask)
    law = array_law_check(out)
    if not law['consistent']:
        raise SupportError(f'PACKET_INCONSISTENT {law}')
    summ = dict(summ)
    summ['files_sha256_as_written_by_base'] = base_files
    summ['files_sha256'] = {n: _sha(out / n) for n in base_files}
    summ['hazard_bytes'] = (out / 'HAZARD.json').stat().st_size
    summ['support_writer'] = writer
    summ['packet_self_check'] = {'support_self_check': 'PASS', 'array_law': {'consistent': True, 'members': law['members']}}
    return hz, summ


def self_check(out, hz0, rep0, arr0, mask):
    hz = json.loads((out / 'HAZARD.json').read_text())
    arr = _load_npz(out / 'constructed_arrays.npz')
    rep = json.loads((out / 'REPORT.json').read_text())
    flat = np.flipud(mask).ravel()
    if [m['id'] for m in hz['members']] != [m['id'] for m in hz0['members']]:
        raise SupportError('SELF_CHECK ids changed')
    for m, m0 in zip(hz['members'], hz0['members']):
        for k in ('breakpoints', 'flame', 'flux'):
            if m[k] != m0[k]:
                raise SupportError(f'SELF_CHECK {k} changed for {m["id"]}')
        s = np.asarray(m['support'], bool)
        if s.shape != (len(m['breakpoints']) - 1, flat.size) or not (s == flat).all():
            raise SupportError(f'SELF_CHECK support != mask for {m["id"]}')
    if set(arr) != set(arr0):
        raise SupportError('SELF_CHECK npz names changed')
    for k in arr0:
        if k == 'support':
            continue
        a, b = arr[k], arr0[k]
        if a.dtype != b.dtype or a.shape != b.shape or a.tobytes() != b.tobytes():
            raise SupportError(f'SELF_CHECK npz {k} changed')
    if not (arr['support'] == mask[None]).all() or arr['support'].shape != arr0['support'].shape:
        raise SupportError('SELF_CHECK npz support != mask')
    if rep['native_metadata']['construction'] != rep0['native_metadata']['construction']:
        raise SupportError('SELF_CHECK construction assumptions changed')


def array_law_check(packet_dir) -> dict:
    """Mirror of F-DYN fdyn/consistency.py check(): the array law [b, b+T) / [0, R) equals HAZARD flame on every bin and
    no array knot lies strictly inside a bin."""
    d = Path(packet_dir)
    asm = json.loads((d / 'REPORT.json').read_text())['native_metadata']['construction']['assumptions']
    T, R = float(asm['burning_duration_s']), float(asm['initial_remaining_s'])
    hz = json.loads((d / 'HAZARD.json').read_text())
    a = _load_npz(d / 'constructed_arrays.npz')
    ign = np.asarray(a['ignition_time_s'], float); cur = np.asarray(a['current_active'], bool)
    S, H, W = ign.shape
    if np.isnan(ign).any():
        return {'consistent': False, 'members': S, 'array_path': 'REFUSED (NaN ignition)'}
    ok = True
    for s in range(S):
        b = np.flipud(ign[s]).ravel()
        c = np.flipud(cur).ravel() if R > 0 else np.zeros(H * W, bool)
        fin = np.isfinite(b)
        knots = set(b[fin].tolist()) | set((b[fin] + T).tolist()) | ({R} if c.any() else set())
        m = hz['members'][s]; bp = [float(x) for x in m['breakpoints']]
        for k in range(len(bp) - 1):
            lo, hi = bp[k], bp[k + 1]
            if any(lo + TOL < t < hi - TOL for t in knots):
                ok = False
            arr = (fin & (b <= lo) & (lo < b + T)) | (c & (lo < R))
            if (arr != np.asarray(m['flame'][k], bool)).any():
                ok = False
    return {'consistent': bool(ok), 'members': S}
