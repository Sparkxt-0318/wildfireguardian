"""T3 mutation tests (PROTOCOL 5): alter valid certificates in 17 ways; the checker must reject every mutant.
Usage: python3 mutate.py CERT_DIR OUT.json [per_family]     Seeded. Works on kcf-queue.cert/1 files (.json.gz)."""
import copy, glob, gzip, hashlib, json, random, sys
import checker

def rehash(c):
    c["input_sha256"] = hashlib.sha256(json.dumps(c["data"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def rel(o, k):
    return o["start"] + (o["spread"] * (2 * k + 1)) // (2 * o["N"])

def subj(c):
    return next(o for o in c["owners"] if o["role"] == "subject")

def vehs(c, owner):
    return [v for v in c["vehicles"] if v["owner"] == owner]

def lo_of(c, e):
    from fractions import Fraction
    ed = c["data"]["edges"][str(e)]; best = None
    for cell, z in ed["segs"]:
        b = c["data"]["cell_close"].get(str(cell))
        if b is not None:
            n, d = map(int, z.split("/"))
            x = -((-(b * d - ed["D"] * n)) // d)   # ceil(b - D*z)
            x = max(x, 0)
            best = x if best is None else min(best, x)
    return best

def shift_from(path, i, delta):
    for q in path[i:]:
        q[1] += delta

def m_before_release(c, rnd):
    S = subj(c); v = rnd.choice(vehs(c, S["id"])); r = rel(S, v["k"])
    if r < 1: return None
    v["path"][0][1] = r - 1; return {"ROUTE"}

def m_before_arrival(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"]))
    if len(v["path"]) < 2: return None
    i = rnd.randrange(1, len(v["path"])); e = str(v["path"][i - 1][0])
    v["path"][i][1] = v["path"][i - 1][1] + c["data"]["edges"][e]["D"] - 1; return {"ROUTE"}

def m_edge_closed(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"]))
    cand = [i for i, (e, t) in enumerate(v["path"]) if lo_of(c, e) is not None]
    if not cand: return None
    i = rnd.choice(cand); e, t = v["path"][i]; d = max(lo_of(c, e) - t, 0)
    shift_from(v["path"], i, d); return {"EDGE_CLOSED"}

def m_wait(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"]))
    for i in range(1, len(v["path"])):
        u = c["data"]["edges"][str(v["path"][i][0])]["tail"]; b = c["data"]["cell_close"].get(str(c["data"]["nodes"][str(u)]["cell"]))
        if b is not None:
            shift_from(v["path"], i, max(b - v["path"][i][1], 0) + 1); return {"WAIT", "EDGE_CLOSED", "SHELTER"}
    return None

def m_capacity(c, rnd):
    S = subj(c); vs = vehs(c, S["id"])
    if len(vs) < 3: return None
    last = vs[-1]; ns = []
    for e, t in last["path"]:
        ed = c["data"]["edges"][str(e)]; ns.append(max(1, (round(c["rho"] * 100) * ed["cap_vph"]) // 6000))
    nmin = min(ns)
    if nmin + 1 > len(vs): return None
    for k in range(nmin):
        vs[k]["path"] = copy.deepcopy(last["path"])
    return {"CAPACITY"}

def m_nonadjacent(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"]))
    if len(v["path"]) < 3: return None
    i = rnd.randrange(1, len(v["path"]) - 1); prev = c["data"]["edges"][str(v["path"][i - 1][0])]["head"]
    bad = [e for e, ed in c["data"]["edges"].items() if ed["tail"] != prev]
    v["path"][i][0] = int(rnd.choice(bad)); return {"ROUTE"}

def m_forbidden(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"]))
    if len(v["path"]) < 2: return None
    i = rnd.randrange(len(v["path"]) - 1); c["data"]["forbidden"].append([v["path"][i][0], v["path"][i + 1][0]]); rehash(c); return {"ROUTE"}

def m_not_shelter(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"]))
    if len(v["path"]) < 2: return None
    v["path"].pop(); return {"SHELTER"}

def m_late(c, rnd):
    v = rnd.choice(vehs(c, subj(c)["id"])); v["path"][-1][1] = c["H"] - c["dwell"] + 1; return {"SHELTER", "EDGE_CLOSED", "ROUTE", "SCHEMA"}

def m_count(c, rnd):
    S = subj(c); vs = vehs(c, S["id"]); c["vehicles"].remove(rnd.choice(vs)); return {"COUNT"}

def m_release_curve(c, rnd):
    S = subj(c); S["start"] += 7200; return {"ROUTE"}

def m_hash_cell(c, rnd):
    cc = c["data"]["cell_close"]
    if not cc: return None
    k = rnd.choice(sorted(cc)); cc[k] += 1; return {"HASH"}

def m_hash_cap(c, rnd):
    e = rnd.choice(sorted(c["data"]["edges"])); c["data"]["edges"][e]["cap_vph"] += 100; return {"HASH"}

def m_neighbour_drop(c, rnd):
    nb = [o for o in c["owners"] if o["role"] == "neighbour" and "ks" not in o]
    if not nb: return None
    o = rnd.choice(nb); c["vehicles"].remove(rnd.choice(vehs(c, o["id"]))); return {"COUNT"}

def m_duplicate(c, rnd):
    c["vehicles"].append(copy.deepcopy(rnd.choice(vehs(c, subj(c)["id"])))); return {"COUNT"}

def m_negative(c, rnd):
    rnd.choice(vehs(c, subj(c)["id"]))["path"][0][1] = -1; return {"SCHEMA"}

def m_binding(c, rnd):
    c["claim"]["binding"]["slack"] += 1; return {"BINDING_MISMATCH"}

FAMILIES = [m_before_release, m_before_arrival, m_edge_closed, m_wait, m_capacity, m_nonadjacent, m_forbidden, m_not_shelter,
            m_late, m_count, m_release_curve, m_hash_cell, m_hash_cap, m_neighbour_drop, m_duplicate, m_negative, m_binding]

def main(cdir, out, per=130):
    files = sorted(glob.glob(cdir + "/*.json.gz")); rnd = random.Random(20261119)
    rep = {"certificates_available": len(files), "mutants": 0, "rejected": 0, "accepted": [], "wrong_code": [], "families": {}, "unaltered_checked": 0, "unaltered_valid": 0}
    certs = []
    import os
    iso = [f for f in files if "__ISOLATED__" in f]; con = sorted((f for f in files if "__CONTESTED__" in f), key=os.path.getsize)
    pick = rnd.sample(iso, min(len(iso), 30)) + con[:8]   # smallest contested certificates only (checker time)
    for f in pick:
        c = json.load(gzip.open(f, "rt")); r = checker.check(c); rep["unaltered_checked"] += 1; rep["unaltered_valid"] += r["valid"]
        if r["valid"]: certs.append((f, c))
    for fam in FAMILIES:
        st = {"made": 0, "rejected": 0}
        tries = 0
        while st["made"] < per and tries < per * 20 and certs:
            tries += 1
            f, c0 = rnd.choice(certs); c = copy.deepcopy(c0)
            exp = fam(c, rnd)
            if exp is None: continue
            st["made"] += 1; rep["mutants"] += 1
            res = checker.check(c); codes = {x["code"] for x in res["failures"]}
            if res["valid"]:
                rep["accepted"].append({"family": fam.__name__, "file": f.split("/")[-1]})
            else:
                st["rejected"] += 1; rep["rejected"] += 1
                if not (codes & exp):
                    rep["wrong_code"].append({"family": fam.__name__, "got": sorted(codes), "want": sorted(exp)})
        rep["families"][fam.__name__] = st
    json.dump(rep, open(out, "w"), indent=1)
    print({k: (v if not isinstance(v, list) else len(v)) for k, v in rep.items() if k != "families"})

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 130)
