"""Derived exact vector DP: preserve queued arrivals through empty time layers."""
import array,time
import numpy as np
from rpipe import engines as EN
from rpipe.joint import R3Result

def r3_bounded_exact(cp, etabs, wtabs, origin, dests, E_max, *, k_limit, frontier_width, max_pops,
                     time_limit_s, rss_limit_mb):
    """Bounded exact M-dimensional-budget search on the union turn-state x lattice-time graph.

    Legality, peak (B_U) and the destination dwell (D_U) come from `cp`, which is EXACT for the joint problem.
    The only thing kept per label is the M-vector of accumulated per-member exposure; a label survives iff every
    component is <= E_max.  Dominance: a dominates b at the same (state, tick) iff a <= b componentwise, which
    is valid because future increments are identical and additive for both.

    Searches arrival ticks in [1, k_limit].  Returns the earliest arrival tick with a jointly admissible label,
    or a cap.  `truncated` True means a frontier was cut, which voids the exactness claim.
    """
    pb = cp.pb
    t0 = time.perf_counter()
    E = pb.n_edges
    ORIG = E
    M = len(etabs)
    m_ticks = pb.m_ticks.astype(np.int64)
    head = np.r_[pb.ev, origin].astype(np.int64)
    waitable_state = np.asarray(pb.waitable)[head]
    dset = set(int(d) for d in dests)
    R = int(m_ticks.max()) + 2
    K = min(int(k_limit), cp.K)
    for t in etabs + wtabs:
        t.reset()

    # parent records (compact): state, tick, parent index, kind (0 = EDGE, 1 = WAIT)
    rec_s = array.array("i")
    rec_k = array.array("i")
    rec_p = array.array("i")
    rec_t = array.array("b")

    def add_rec(s, k, p, kind):
        rec_s.append(int(s))
        rec_k.append(int(k))
        rec_p.append(int(p))
        rec_t.append(int(kind))
        return len(rec_s) - 1

    ring = [dict() for _ in range(R)]          # slot -> {state: [(Evec, rec_idx), ...]}
    cur = {ORIG: [(np.zeros(M), add_rec(ORIG, 0, -1, 1))]}
    pops = 0
    truncated = False
    cap = None
    found = None

    def prune(labels):
        """Pareto-prune, then cap the frontier width."""
        nonlocal truncated
        if len(labels) <= 1:
            return labels
        labels = sorted(labels, key=lambda t: (float(t[0].max()), float(t[0].sum())))
        keep = []
        for ev, ri in labels:
            dom = False
            for ev2, _ in keep:
                if np.all(ev2 <= ev):
                    dom = True
                    break
            if not dom:
                keep.append((ev, ri))
        if len(keep) > frontier_width:
            truncated = True
            keep = keep[:frontier_width]
        return keep

    k = 0
    while k <= K:
        if k > 0:
            slot = ring[k % R]
            arrivals = slot
            ring[k % R] = dict()
            merged = {}
            for s, lab in arrivals.items():
                merged.setdefault(s, []).extend(lab)
            for s, lab in cur.items():            # `cur` at this point holds the WAIT carries into tick k
                merged.setdefault(s, []).extend(lab)
            cur = {s: prune(lab) for s, lab in merged.items() if lab}
            # ---- destination test: EDGE arrivals only ----
            best = None
            for s, lab in arrivals.items():
                if s == ORIG or int(head[s]) not in dset:
                    continue
                if not cp.dest_ok(int(head[s]), k):
                    continue
                for ev, ri in lab:
                    if float(ev.max()) <= E_max:
                        cand = (float(ev.max()), int(s), ri, ev)
                        if best is None or cand[:3] < best[:3]:
                            best = cand
            if best is not None:
                found = best
                break
        if k == K:
            break
        if time.perf_counter() - t0 > time_limit_s:
            cap = f"WALL_CLOCK_{time_limit_s}s_AT_TICK_{k}"
            break
        if pops > max_pops:
            cap = f"MAX_POPS_{max_pops}_AT_TICK_{k}"
            break
        if k % 2048 == 0 and EN.cur_rss_mb() > rss_limit_mb:
            cap = f"RSS_{rss_limit_mb}MB_AT_TICK_{k}"
            break
        if not cur:
            # Non-waitable states may leave future EDGE arrivals in the ring.
            if not any(ring):
                cap = None
                break
            k += 1
            continue

        # ---- departures: every label expands over its state's legal successors ----
        states = list(cur)
        succ_sets = {}
        all_f = set()
        for s in states:
            fs = cp.out_by_node[int(origin)] if s == ORIG else cp.succ[s]
            fs = [f for f in fs if k + int(m_ticks[f]) <= K]
            if fs:
                ok = ~cp.edge_forbid.query(np.asarray(fs, np.int64), k)
                fs = [f for f, o in zip(fs, ok.tolist()) if o]
            succ_sets[s] = fs
            all_f.update(fs)
        if all_f:
            fl = np.asarray(sorted(all_f), np.int64)
            pos = {int(f): i for i, f in enumerate(fl.tolist())}
            EX = np.vstack([t.eval(fl, k) for t in etabs])        # (M, n_f)
            for s in states:
                fs = succ_sets[s]
                if not fs:
                    continue
                idx = np.asarray([pos[int(f)] for f in fs], np.int64)
                sub = EX[:, idx]
                for ev, ri in cur[s]:
                    pops += len(fs)
                    newv = ev[:, None] + sub
                    ok = newv.max(axis=0) <= E_max
                    if not ok.any():
                        continue
                    for j in np.flatnonzero(ok).tolist():
                        f = int(fs[j])
                        ka = k + int(m_ticks[f])
                        nr = add_rec(f, ka, ri, 0)
                        ring[ka % R].setdefault(f, []).append((newv[:, j].copy(), nr))
        # ---- waits (one tick at the head node, only if waitable and peak-admissible) ----
        nxt = {}
        ws = [s for s in states if waitable_state[s]]
        if ws:
            nodes = np.asarray([int(head[s]) for s in ws], np.int64)
            okw = ~cp.wait_forbid.query(nodes, k)
            keepn = np.flatnonzero(okw)
            if keepn.size:
                nn = nodes[keepn]
                WX = np.vstack([t.eval(nn, k) for t in wtabs])     # (M, n_w)
                for jj, i in enumerate(keepn.tolist()):
                    s = ws[i]
                    inc = WX[:, jj]
                    for ev, ri in cur[s]:
                        pops += 1
                        nv = ev + inc
                        if float(nv.max()) <= E_max:
                            nr = add_rec(s, k + 1, ri, 1)
                            nxt.setdefault(s, []).append((nv, nr))
        cur = nxt
        k += 1

    out = R3Result(status=None, t_arr_tick=None, E_vector=None, truncated=truncated, cap=cap,
                   pops=pops, wall_s=time.perf_counter() - t0, k_limit=K,
                   frontier_width=frontier_width, max_pops=max_pops, n_records=len(rec_s))
    if found is not None:
        _mx, s_, ri, ev = found
        legs = []
        i = ri
        while i >= 0 and rec_p[i] >= 0:
            s = rec_s[i]
            kk = rec_k[i]
            if rec_t[i] == 0:
                legs.append(("EDGE", int(s), int(kk - int(m_ticks[s])), int(kk)))
            else:
                legs.append(("WAIT", int(head[s]), int(kk - 1), int(kk)))
            i = rec_p[i]
        legs.reverse()
        merged = []
        for lg in legs:
            if lg[0] == "WAIT" and merged and merged[-1][0] == "WAIT" and merged[-1][1] == lg[1] \
                    and merged[-1][3] == lg[2]:
                merged[-1] = ("WAIT", lg[1], merged[-1][2], lg[3])
            else:
                merged.append(lg)
        out.update(status="ROUTE", t_arr_tick=int(k), E_vector=ev.tolist(), legs=merged,
                   dest_state=int(s_))
        return out
    if cap is not None:
        out.update(status="CAP")
        return out
    out.update(status="REFUSED" if not truncated else "CAP")
    if truncated and cap is None:
        out["cap"] = "FRONTIER_WIDTH_TRUNCATION"
    return out


# ------------------------------------------------------------------------------------------------ joint arm
