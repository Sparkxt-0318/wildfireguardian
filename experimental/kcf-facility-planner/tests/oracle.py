"""Second-by-second brute-force oracle for the portable contract, written from SCHEMA.md only.

No dominance, no interval arithmetic shortcuts: at every integer second it enumerates every (leg, node, incoming edge)
state at which the vehicle is present and tries every edge entry at that second. Presence persists (waiting is free).
It returns the earliest final unloading per vehicle chain and the longest deliverable prefix of groups.
"""


def _blocked(edge, view):
    ivs = [tuple(x) for x in edge.get("closed", [])]
    if view == "supported":
        ivs += [tuple(x) for x in edge.get("unknown", [])]
    return ivs


def _free(edge, view, d):
    D = edge["travel_s"]
    for a, b in _blocked(edge, view):
        if max(d, a) < min(d + D, b):  # positive overlap of [d, d+D) and [a, b)
            return False
    return True


def chain(case, vehicle, groups, view):
    """Return (final_unload or None, delivered_count)."""
    H = case["horizon_s"]
    wlo, whi = case["destination_window"]
    board, unload = case["board_s"], case["unload_s"]
    origin, dest = case["origin"], case["destination"]
    forb = {tuple(p) for p in case["forbidden_turns"]}
    legs = []
    for k, g in enumerate(groups):
        if k:
            legs.append(("ret", None))
        legs.append(("out", g))
    # present[t] = set of (leg_index, node, incoming)
    present = {}

    def add(t, st):
        if t <= H:
            present.setdefault(t, set()).add(st)

    best_final = None
    delivered = 0
    if not legs:
        return None, 0
    if legs[0][1]["people"] > vehicle["seats"]:
        return None, 0
    add(vehicle["available_s"] + board, (0, origin, None))
    cur = set()
    for t in range(0, H + 1):
        cur |= present.pop(t, set())
        for (li, node, inc) in list(cur):
            kind, g = legs[li]
            target = dest if kind == "out" else origin
            for e in case["edges"]:
                if e["u"] != node or (inc is not None and (inc, e["id"]) in forb):
                    continue
                a = t + e["travel_s"]
                if a > H or not _free(e, view, t):
                    continue
                add(a, (li, e["v"], e["id"]))  # pass-through / non-final arrival
                if e["v"] != target:
                    continue
                if kind == "out":
                    if not (a >= wlo and a + unload <= min(whi, H)):
                        continue
                    delivered = max(delivered, (li // 2) + 1)
                    if li == len(legs) - 1:
                        f = a + unload
                        best_final = f if best_final is None else min(best_final, f)
                    else:
                        nxt = legs[li + 2][1] if li + 2 < len(legs) else None
                        add(a + unload, (li + 1, target, e["id"]))
                        _ = nxt
                else:
                    nxt = legs[li + 1][1]
                    if nxt["people"] <= vehicle["seats"]:
                        add(a + board, (li + 1, target, e["id"]))
    return best_final, delivered


def solve(case):
    """Oracle status, final and checked people for a raw case dict (valid inputs only)."""
    res = {}
    for view in ("supported", "optimistic"):
        if case["mode"] == "parallel":
            finals, people, ok = [], 0, True
            for i, g in enumerate(case["groups"]):
                if i >= len(case["vehicles"]):
                    ok = False
                    continue
                f, dl = chain(case, case["vehicles"][i], [g], view)
                if f is None:
                    ok = False
                else:
                    finals.append(f)
                    people += g["people"]
            final = (max(finals) if finals else None) if ok else None
        else:
            f, dl = chain(case, case["vehicles"][0], case["groups"], view)
            ok = f is not None
            final = f
            people = sum(g["people"] for g in case["groups"][:dl])
        res[view] = (ok, final, people)
    # Conditional (MISSING_INPUT) schedule: chains with a supported schedule keep it, others use unknown inputs.
    cond_final = None
    if res["optimistic"][0]:
        if case["mode"] == "parallel":
            fs = []
            for i, g in enumerate(case["groups"]):
                f, _ = chain(case, case["vehicles"][i], [g], "supported")
                if f is None:
                    f, _ = chain(case, case["vehicles"][i], [g], "optimistic")
                fs.append(f)
            cond_final = max(fs)
        else:
            cond_final = res["optimistic"][1]
    if res["supported"][0]:
        status = "CHECKED_ROUTE"
    elif res["optimistic"][0]:
        status = "MISSING_INPUT"
    else:
        status = "MODEL_SCOPED_NO_ROUTE"
    return {"status": status, "final": res["supported"][1] if status == "CHECKED_ROUTE" else None,
            "optimistic_final": res["optimistic"][1] if res["optimistic"][0] else None,
            "conditional_final": cond_final,
            "people_checked": res["supported"][2]}
