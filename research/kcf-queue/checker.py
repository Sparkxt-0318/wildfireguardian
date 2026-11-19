#!/usr/bin/env python3
"""Independent checker for kcf-queue.cert/1 certificates (see CERTIFICATE_SPEC.md). Standard library only."""
import gzip
import hashlib
import json
import sys
from collections import Counter
from fractions import Fraction

KIND_ORDER = {"edge": 0, "node": 1, "shelter": 2}


def _int(x):
    return type(x) is int


def _intkey(s):
    return isinstance(s, str) and s.lstrip("-").isdigit()


def _idkey(s):
    return (0, int(s), "") if s.lstrip("-").isdigit() else (1, 0, s)


def _ceil(fr):
    return -((-fr.numerator) // fr.denominator)


def _schema(c):
    """Return (errors, model). model is a dict of parsed data when errors is empty."""
    errs = []
    if not isinstance(c, dict):
        return ["certificate is not an object"], None
    if c.get("schema") != "kcf-queue.cert/1":
        errs.append("schema tag")
    for key in ("H", "dwell", "bin_s"):
        if not _int(c.get(key)):
            errs.append(key + " not an integer")
    if _int(c.get("bin_s")) and c["bin_s"] < 1:
        errs.append("bin_s < 1")
    if type(c.get("rho")) not in (int, float):
        errs.append("rho not a number")
    d = c.get("data")
    if not isinstance(d, dict):
        return errs + ["data missing"], None
    close, nodes, edges = d.get("cell_close"), d.get("nodes"), d.get("edges")
    if not isinstance(close, dict) or not all(_intkey(k) and _int(v) for k, v in close.items()):
        errs.append("cell_close malformed")
        close = {}
    if not isinstance(nodes, dict) or not all(_intkey(k) and isinstance(v, dict) and "cell" in v
                                              and isinstance(v["cell"], (int, str)) for k, v in nodes.items()):
        errs.append("nodes malformed")
        nodes = {}
    if not isinstance(edges, dict):
        errs.append("edges malformed")
        edges = {}
    E = {}
    for k, e in edges.items():
        try:
            assert _intkey(k) and isinstance(e, dict) and _int(e["D"]) and e["D"] >= 1 and _int(e["cap_vph"])
            tail, head = str(e["tail"]), str(e["head"])
            assert tail in nodes and head in nodes and isinstance(e["segs"], list)
            lo = None
            for cell, z in e["segs"]:
                z = Fraction(z)  # raises on non-strings that are not numbers / bad text
                assert isinstance(cell, (int, str))
                if str(cell) in close:
                    s = max(_ceil(close[str(cell)] - e["D"] * z), 0)
                    lo = s if lo is None else min(lo, s)
            E[k] = (tail, head, e["D"], e["cap_vph"], lo)
        except Exception:
            errs.append("edge %s malformed" % k)
    forb = set()
    try:
        forb = {(str(a), str(b)) for a, b in d["forbidden"]}
    except Exception:
        errs.append("forbidden malformed")
    sh = d.get("shelters")
    if not isinstance(sh, list) or not all(isinstance(s, (int, str)) and str(s) in nodes for s in sh):
        errs.append("shelters malformed")
        sh = []
    owners, vehicles = c.get("owners"), c.get("vehicles")
    O, V = {}, []
    if not isinstance(owners, list) or not isinstance(vehicles, list):
        return errs + ["owners/vehicles malformed"], None
    for o in owners:
        ks = o.get("ks") if isinstance(o, dict) else None
        if isinstance(o, dict) and "ks" in o and not (
                o.get("role") == "neighbour" and isinstance(ks, list) and all(_int(x) for x in ks)
                and ks == sorted(set(ks)) and _int(o.get("N")) and all(0 <= x < o["N"] for x in ks)):
            errs.append("ks malformed, out of range, or on subject")
        elif (isinstance(o, dict) and isinstance(o.get("id"), str) and o["id"] not in O and _int(o.get("N"))
                and _int(o.get("start")) and _int(o.get("spread")) and o.get("role") in ("subject", "neighbour")
                and isinstance(o.get("origin"), (int, str)) and str(o["origin"]) in nodes):
            O[o["id"]] = o
        else:
            errs.append("owner malformed or duplicated")
    subj = [i for i, o in O.items() if o["role"] == "subject"]
    if len(subj) != 1:
        errs.append("need exactly one subject owner")
    cl = c.get("claim")
    b = cl.get("binding") if isinstance(cl, dict) else None
    if not (isinstance(cl, dict) and isinstance(cl.get("all_cleared"), bool) and len(subj) == 1
            and cl.get("subject") == subj[0] and isinstance(b, dict) and b.get("kind") in KIND_ORDER
            and isinstance(b.get("id"), (int, str)) and _int(b.get("slack")) and isinstance(b.get("vehicle"), list)
            and len(b["vehicle"]) == 2 and _int(b["vehicle"][1])):
        errs.append("claim malformed or subject mismatch")
    H = c.get("H")
    for i, v in enumerate(vehicles):
        try:
            assert isinstance(v, dict) and isinstance(v["owner"], str) and _int(v["k"]) and isinstance(v["path"], list)
            p = []
            for ent in v["path"]:
                e, t = ent
                assert isinstance(e, (int, str)) and _int(t) and (not _int(H) or 0 <= t <= H)
                p.append((str(e), t))
            V.append((v["owner"], v["k"], p, v))
        except Exception:
            errs.append("vehicle %d malformed (or entry outside 0..H)" % i)
    if errs:
        return errs, None
    return [], dict(close=close, nodes=nodes, E=E, forb=forb, sh={str(s) for s in sh}, O=O, V=V, cl=cl, subj=subj[0])


def check(cert):
    try:
        return _check(cert)
    except Exception as ex:  # never raise on bad input
        return {"valid": False, "failures": [{"code": "SCHEMA", "owner": None, "k": None,
                                              "detail": "unexpected error: %r" % (ex,)}], "binding": None}


def _check(c):
    fails = []

    def F(code, owner=None, k=None, detail=""):
        fails.append({"code": code, "owner": owner, "k": k, "detail": detail})

    try:
        h = hashlib.sha256(json.dumps(c["data"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if h != c.get("input_sha256"):
            F("HASH", detail="input_sha256 does not match data")
    except Exception:
        F("HASH", detail="cannot hash data")
    errs, m = _schema(c)
    if errs:
        for s in errs:
            F("SCHEMA", detail=s)
        return {"valid": False, "failures": fails[:50], "binding": None}
    H, dwell, bin_s = c["H"], c["dwell"], c["bin_s"]
    close, nodes, E, O = m["close"], m["nodes"], m["E"], m["O"]
    ncell = lambda u: str(nodes[u]["cell"])
    bclose = lambda u: close.get(ncell(u))
    slacks, resolved_subject, usage = [], True, Counter()
    byowner = {}
    for o, k, p, raw in m["V"]:
        byowner.setdefault(o, []).append(k)
    for o, ks in byowner.items():
        if o not in O:
            F("COUNT", o, None, "vehicle of unknown owner")
        elif O[o]["N"] < 1 or sorted(ks) != (O[o]["ks"] if "ks" in O[o] else list(range(len(ks)))) or (
                "ks" not in O[o] and len(ks) != O[o]["N"]):
            F("COUNT", o, None, "vehicles are not exactly the expected k set once each (N=%d, got %d)" % (O[o]["N"], len(ks)))
    for o in O:
        if o not in byowner and O[o].get("ks", [0]):
            F("COUNT", o, None, "owner has no vehicles")
    for o, k, p, raw in m["V"]:
        sub = o == m["subj"]
        if o not in O or O[o]["N"] < 1:
            resolved_subject &= not sub
            continue
        ow = O[o]
        r = ow["start"] + (ow["spread"] * (2 * k + 1)) // (2 * ow["N"])
        if "release" in raw and raw["release"] != r:
            F("RELEASE_CURVE", o, k, "declared release %r != %d" % (raw["release"], r))
        if not p:
            F("ROUTE", o, k, "empty path")
            resolved_subject &= not sub
            continue
        for e, t in p:
            if e in E:
                usage[(e, t // bin_s)] += 1
        if any(e not in E for e, t in p):
            F("ROUTE", o, k, "unknown edge in path")
            resolved_subject &= not sub
            continue
        a, u, prev, mine = r, str(ow["origin"]), None, []
        for i, (e, t) in enumerate(p):
            tail, head, D, cap, lo = E[e]
            if i == 0:
                if tail != u:
                    F("ROUTE", o, k, "first edge tail %s is not origin %s" % (tail, u))
                if t < r:
                    F("ROUTE", o, k, "first entry %d before release %d" % (t, r))
            else:
                if prev[1] != tail:
                    F("ROUTE", o, k, "edge %s head %s != edge %s tail %s" % (prev[0], prev[1], e, tail))
                if (prev[0], e) in m["forb"]:
                    F("ROUTE", o, k, "forbidden transition %s -> %s" % (prev[0], e))
                if t < a:
                    F("ROUTE", o, k, "entry %d earlier than %d (previous entry + D)" % (t, a))
            if lo is not None:
                if t >= lo:
                    F("EDGE_CLOSED", o, k, "edge %s entered at %d, cutoff %d" % (e, t, lo))
                mine.append((lo - 1 - t, "edge", e))
            b = bclose(u)
            if t >= a and b is not None and (t > a or i == 0) and t >= b:
                F("WAIT", o, k, "node %s entry %d (arrived %d) not before closure %d" % (u, t, a, b))
            if t > a and b is not None:
                mine.append((b - 1 - t, "node", u))
            a, u, prev = t + D, head, (e, head)
        b = bclose(u)
        if u not in m["sh"]:
            F("SHELTER", o, k, "last head %s is not a shelter" % u)
        if a < 0 or a > H - dwell or (b is not None and a >= max(b - dwell, 0)):
            F("SHELTER", o, k, "arrival %d outside accepted window" % a)
        top = H - dwell if b is None else min(H - dwell, max(b - dwell, 0) - 1)
        mine.append((top - a, "shelter", u))
        if sub:
            slacks += [(s, kd, i, o, k) for s, kd, i in mine]
    for (e, mb), n in sorted(usage.items()):
        ne = max(1, (round(c["rho"] * 100) * E[e][3]) // 6000)
        if n > ne:
            F("CAPACITY", None, None, "edge %s bin %d has %d entries > %d" % (e, mb, n, ne))
    binding = None
    if resolved_subject and slacks:
        s, kd, i, o, k = min(slacks, key=lambda x: (x[0], KIND_ORDER[x[1]], _idkey(x[2]), x[3], x[4]))
        binding = {"kind": kd, "id": i, "vehicle": [o, k], "slack": s}
        cb = m["cl"]["binding"]
        if (cb["kind"], str(cb["id"]), cb["vehicle"][0], cb["vehicle"][1], cb["slack"]) != (kd, i, o, k, s):
            F("BINDING_MISMATCH", o, k, "claimed %r, recomputed %r" % (cb, binding))
    return {"valid": not fails, "failures": fails[:50], "binding": None if fails else binding}


def _load(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    bad = 0
    for p in argv:
        try:
            res = check(_load(p))
        except Exception as ex:
            res = {"valid": False, "failures": [{"code": "SCHEMA", "detail": "unreadable: %r" % (ex,)}]}
        codes = sorted({f["code"] for f in res["failures"]})
        print("%s %s %s" % (p, "VALID" if res["valid"] else "INVALID", " ".join(codes)))
        bad += not res["valid"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
