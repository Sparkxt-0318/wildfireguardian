"""Mutation test: corrupt valid .wfgc bundles in targeted ways; every checker must reject every corruption.

Usage: python mutate.py --bundles DIR --per-class N [--c-checker PATH] [--seed S] --out FILE
Each mutation class targets one certificate condition. The unmutated bundle is a control and must be accepted.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def ivl_parse(toks, i):
    m = int(toks[i]); i += 1
    out = [(int(toks[i + 2 * k]), int(toks[i + 2 * k + 1])) for k in range(m)]
    return out, i + 2 * m


def ivl_fmt(ivs):
    return " ".join([str(len(ivs))] + ["%d %d" % p for p in ivs])


def remove_point(ivs, t):
    out = []
    for a, b in ivs:
        if a <= t <= b:
            if a <= t - 1:
                out.append((a, t - 1))
            if t + 1 <= b:
                out.append((t + 1, b))
        else:
            out.append((a, b))
    return out


def add_point(ivs, t):
    pts = sorted(ivs + [(t, t)])
    out = []
    for a, b in pts:
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def contains(ivs, t):
    return any(a <= t <= b for a, b in ivs)


class Bundle:
    def __init__(self, text):
        self.L = text.rstrip("\n").split("\n")
        L = self.L
        self.H = int(L[3].split()[3]); self.dep = int(L[3].split()[1])
        self.origin = int(L[3].split()[5]); self.s0 = int(L[3].split()[7])
        nE = int(L[2].split()[3]); self.nE = nE
        self.edges = [tuple(map(int, L[5 + j].split())) for j in range(nE)]
        self.idx = {}
        for k, line in enumerate(L):
            w = line.split(" ", 1)[0]
            if w in ("WAITABLE", "FORBID", "EB", "WB", "AC", "END_INSTANCE", "CLAIM", "WITNESS", "CERT", "COCERT", "END"):
                self.idx.setdefault("CERT" if w == "COCERT" else w, k)
        self.co = L[self.idx["CERT"]].startswith("COCERT")
        self.tables = {}
        for key in ("EB", "WB", "AC"):
            k0 = self.idx[key]; n = int(L[k0].split()[1])
            self.tables[key] = {int(L[k0 + 1 + r].split()[0]): (k0 + 1 + r, ivl_parse(L[k0 + 1 + r].split(), 1)[0])
                                for r in range(n)}
        k0 = self.idx["WAITABLE"]
        self.waitable = set(int(x) for line in L[k0 + 1:self.idx["FORBID"]] for x in line.split())
        self.claim = L[self.idx["CLAIM"]].split()
        k0 = self.idx["WITNESS"]
        self.legs = [(k0 + 1 + r, L[k0 + 1 + r]) for r in range(int(L[k0].split()[1]))]
        k0 = self.idx["CERT"]
        self.T = int(L[k0].split()[1])
        self.cert = {}
        for r in range(int(L[k0].split()[2])):
            toks = L[k0 + 1 + r].split()
            R, i = ivl_parse(toks, 1)
            A, _ = ivl_parse(toks, i)
            self.cert[int(toks[0])] = (k0 + 1 + r, R, A)

    def hd(self, s):
        return self.origin if s == self.nE else self.edges[s][1]

    def with_line(self, k, new):
        M = list(self.L); M[k] = new
        return "\n".join(M) + "\n"

    def with_cert(self, s, R, A):
        k = self.cert[s][0]
        return self.with_line(k, "%d %s %s" % (s, ivl_fmt(R), ivl_fmt(A)))


def co_mutations(b, rng, per_class):
    """COCERT bundles: listed sets are NR (= Gr) and NA (= Ga); removing a co-reachable point must be rejected."""
    states = sorted(b.cert)
    gr = [s for s in states if b.cert[s][1]]
    for _ in range(min(per_class, len(gr) * 3)):
        s = rng.choice(gr); _, NR, NA = b.cert[s]
        a, c = rng.choice(NR); t = rng.choice([a, c, rng.randint(a, c)])
        yield "C1_co_drop_coreachable_point", b.with_cert(s, remove_point(NR, t), remove_point(NA, t))
    acc = [(s, t) for s in states for (a, c) in b.cert[s][2] for t in (a, c) if not contains(b.cert[s][1], t)]
    for s, t in rng.sample(acc, min(per_class, len(acc))):
        _, NR, NA = b.cert[s]
        yield "C2_co_drop_goal_point", b.with_cert(s, NR, remove_point(NA, t))
    kt = b.idx["CERT"]; M = list(b.L)
    M[kt + 1:kt + 1 + len(states)] = [b.L[b.cert[s][0]] for s in states if s != states[-1]]
    M[kt] = "COCERT %d %d" % (b.T, len(states) - 1)
    yield "C3_co_drop_last_record", "\n".join(M) + "\n"
    yield "M7_trailing_token", "\n".join(b.L) + "\n0\n"


def mutations(b, rng, per_class):
    if b.co:
        yield from co_mutations(b, rng, per_class)
        return
    lim = min(b.H, b.T - 1)
    states = sorted(b.cert)
    # M1: delete one reachable point from R (and A)
    for _ in range(per_class):
        s = rng.choice(states); _, R, A = b.cert[s]
        a, c = rng.choice(R); t = rng.choice([a, c, rng.randint(a, c)])
        yield "M1_delete_reachable_point", b.with_cert(s, remove_point(R, t), remove_point(A, t))
    # M2: delete one admitted point from A only
    adm = [s for s in states if b.cert[s][2]]
    for _ in range(per_class):
        s = rng.choice(adm); _, R, A = b.cert[s]
        a, c = rng.choice(A); t = rng.choice([a, c, rng.randint(a, c)])
        yield "M2_delete_admitted_point", b.with_cert(s, R, remove_point(A, t))
    # M3: inject a goal arrival below T into some state entering a destination
    goals = []
    for n, (_, ac) in b.tables["AC"].items():
        for s in [j for j in range(b.nE) if b.edges[j][1] == n] + ([b.nE] if b.origin == n else []):
            for a, c in ac:
                if a <= lim:
                    goals.append((s, rng.randint(a, min(c, lim))))
    for _ in range(min(per_class, len(goals))):
        s, t = rng.choice(goals)
        if s in b.cert:
            _, R, A = b.cert[s]
            yield "M3_inject_goal", b.with_cert(s, add_point(R, t), add_point(A, t))
        else:  # new state record would need re-sorting; place it by rebuilding the CERT block
            k0 = b.idx["CERT"]; recs = {x: b.L[b.cert[x][0]] for x in b.cert}
            recs[s] = "%d %s %s" % (s, ivl_fmt([(t, t)]), ivl_fmt([(t, t)]))
            M = b.L[:k0] + ["CERT %d %d" % (b.T, len(recs))] + [recs[x] for x in sorted(recs)] + ["END"]
            yield "M3_inject_goal", "\n".join(M) + "\n"
    # M4: threshold / claim edits
    kc, kt = b.idx["CLAIM"], b.idx["CERT"]
    cert_head = b.L[kt].split()
    if b.claim[1] == "ROUTE":
        T = b.T
        for d in (-1, 1):
            M = list(b.L); M[kc] = "CLAIM ROUTE %d" % (T + d); M[kt] = "CERT %d %s" % (T + d, cert_head[2])
            yield "M4_shift_threshold", "\n".join(M) + "\n"
        M = list(b.L); M[kc] = "CLAIM NO_ROUTE"; M[kt] = "CERT %d %s" % (b.H + 1, cert_head[2])
        kw = b.idx["WITNESS"]; M[kw:kw + 1 + len(b.legs)] = ["WITNESS 0"]
        yield "M4_route_to_no_route", "\n".join(M) + "\n"
    else:
        M = list(b.L); M[kt] = "CERT %d %s" % (b.H, cert_head[2])
        yield "M4_no_route_threshold_H", "\n".join(M) + "\n"
    # M5: witness edits (route claims)
    if b.legs:
        for _ in range(min(per_class, len(b.legs))):
            k, line = rng.choice(b.legs); kind, x, s, e = line.split(); s, e = int(s), int(e)
            choice = rng.randint(0, 3)
            if choice == 0:
                new = "%s %s %d %d" % (kind, x, s + 1, e + 1)
            elif choice == 1:
                new = "%s %s %d %d" % (kind, x, s, e + 1)
            elif choice == 2 and kind == "E":
                new = "E %d %d %d" % ((int(x) + 1) % b.nE, s, e)
            else:
                new = "W %s %d %d" % (b.edges[int(x)][1] if kind == "E" else x, s, s + 1)
            if new.split() == line.split():
                continue  # no-op edit (e.g. a WAIT leg rewritten as itself) is not a corruption
            yield "M5_witness_edit", b.with_line(k, new)
        kw = b.idx["WITNESS"]; M = list(b.L)
        M[kw] = "WITNESS %d" % (len(b.legs) - 1); del M[b.legs[-1][0]]
        yield "M5_witness_drop_last", "\n".join(M) + "\n"
    # M6: instance edits that the certificate relies on
    cands = []
    for j, (k, eb) in b.tables["EB"].items():
        for s in [x for x in states if b.hd(x) == b.edges[j][0]]:
            R = b.cert[s][1]
            Aj = b.cert[j][2] if j in b.cert else []
            D = b.edges[j][2]
            for a, c in eb:
                # only a corruption if some freed departure lands outside A_j (otherwise the bundle stays valid)
                if any(not contains(Aj, t + D) for ra, rb in R
                       for t in range(max(a, ra), min(c, rb, lim - D) + 1)):
                    cands.append((j, k, eb, (a, c)))
                    break
    for j, k, eb, iv in rng.sample(cands, min(per_class, len(cands))):
        new = [p for p in eb if p != iv]
        yield "M6_drop_edge_block", b.with_line(k, "%d %s" % (j, ivl_fmt(new)))
    wc = []
    for n, (k, wb) in b.tables["WB"].items():
        for s in [x for x in states if b.hd(x) == n]:
            for a, c in b.cert[s][1]:
                if c + 1 <= lim and contains(wb, c):
                    wc.append((n, k, wb, c))
    for n, k, wb, c in rng.sample(wc, min(per_class, len(wc))):
        yield "M6_unblock_wait_second", b.with_line(k, "%d %s" % (n, ivl_fmt(remove_point(wb, c))))
    # M7: format
    yield "M7_trailing_token", "\n".join(b.L) + "\n0\n"
    yield "M7_truncated", "\n".join(b.L[:-2]) + "\n"


def run(cmd, text):
    p = subprocess.run(cmd + ["-"], input=text, capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", required=True)
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--c-checker")
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    checkers = {"py": [sys.executable, str(HERE / "check_py.py")]}
    if a.c_checker:
        checkers["c"] = [a.c_checker]
    rng = random.Random(a.seed)
    rows, fails = [], []
    for path in sorted(Path(a.bundles).glob("*.wfgc")):
        text = path.read_text()
        b = Bundle(text)
        for name, cmd in checkers.items():
            code, out = run(cmd, text)
            ok = code == 0 and out.startswith("ACCEPT")
            rows.append(dict(bundle=path.name, mutation="CONTROL_unmutated", checker=name, exit=code, out=out, ok=ok))
            if not ok:
                fails.append(rows[-1])
        for mname, mtext in mutations(b, rng, a.per_class):
            for name, cmd in checkers.items():
                code, out = run(cmd, mtext)
                ok = code != 0 and out.startswith("REJECT")
                rows.append(dict(bundle=path.name, mutation=mname, checker=name, exit=code, out=out, ok=ok))
                if not ok:
                    fails.append(rows[-1])
        print(path.name, sum(r["bundle"] == path.name for r in rows), "runs;", len(fails), "failures so far", flush=True)
    summary = {}
    for r in rows:
        key = "%s|%s" % (r["mutation"], r["checker"])
        d = summary.setdefault(key, {"runs": 0, "ok": 0, "reasons": {}})
        d["runs"] += 1; d["ok"] += r["ok"]
        reason = r["out"].split()[1] if len(r["out"].split()) > 1 else r["out"]
        d["reasons"][reason] = d["reasons"].get(reason, 0) + 1
    Path(a.out).write_text(json.dumps({"seed": a.seed, "per_class": a.per_class, "summary": summary,
                                       "failures": fails}, indent=1) + "\n")
    print(json.dumps({"runs": len(rows), "failures": len(fails)}))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
