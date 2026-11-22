"""Independent verifier: concurrent load_packet of masked and plain packets (8 threads x 3 rounds) vs single-threaded
digests; tools packet.np must be numpy after every round. Run in an F-3.1 tree. argv: graph, masked_dir, plain_dir"""
import sys, hashlib, numpy, threading
sys.path.insert(0, '.')
from concurrent.futures import ThreadPoolExecutor
from deadline_field.real import load_packet, PacketModel
import tools.explain_deadlines.packet as _pm
G, M, P = sys.argv[1:4]
grid = PacketModel(G, P).g.grid
def dig(d):
    pk, _ = load_packet(d, grid)
    return hashlib.sha256(repr((pk.phases, getattr(pk, 'support_false_cells', None))).encode()).hexdigest()[:16]
ref = {d: dig(d) for d in (M, P)}
bad = 0; errs = []
for rnd in range(3):
    jobs = [M, P] * 4
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(dig, d) for d in jobs]
        for d, f in zip(jobs, futs):
            try:
                if f.result() != ref[d]: bad += 1
            except Exception as e: errs.append(repr(e)[:120])
    print('round', rnd, 'np is numpy', _pm.np is numpy, 'mismatches so far', bad, 'errors', len(errs), flush=True)
print('ref', ref, 'errors', errs[:3])
