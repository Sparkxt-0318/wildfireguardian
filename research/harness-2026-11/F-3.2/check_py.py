"""Checker 1 (Python): verifies a .wfgc bundle against CERTIFICATE_SPEC.md / FORMAT.md.

Standard library only; imports nothing from the solver, the generator or wfg_sipp.
Usage: check_py.py FILE [--expect G=<hex>,A=<hex>,W=<hex>,Q=<hex>]
Format 2 (BINDING_RULE.md): the BIND section's I digest is recomputed over the instance bytes and must match; with
--expect, the G A W Q labels must match too and the line ends " LABELS_MATCH <first 16 hex of I>"; without it " UNBOUND". A format-1
bundle given --expect is rejected (BIND_MISSING).
"""
from __future__ import annotations

import bisect
import hashlib
import re
import sys


class Reject(Exception):
    pass


class Tokens:
    def __init__(self, text):
        if any(not (32 <= ord(ch) < 127 or ch in "\t\n") for ch in text):
            raise Reject("BAD_BYTE")
        spans = [(m.start(), m.end()) for m in re.finditer(r"[^ \t\n]+", text)]
        self.t = [text[a:b] for a, b in spans]
        self.spans = spans
        self.text = text
        self.i = 0

    def word(self, expected=None):
        if self.i >= len(self.t):
            raise Reject("EOF")
        w = self.t[self.i]
        self.i += 1
        if expected is not None and w != expected:
            raise Reject("EXPECTED_" + expected)
        return w

    def int(self, lo=None, hi=None):
        w = self.word()
        body = w[1:] if w.startswith("-") else w
        if not body.isdigit() or not body.isascii() or (len(body) > 1 and body[0] == "0") or w == "-0":
            raise Reject("NOT_INTEGER")  # canonical form only: no leading zeros, no "-0", no "+"
        v = int(w)
        if not -(1 << 63) <= v < (1 << 63):
            raise Reject("INT64_RANGE")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise Reject("RANGE")
        return v

    def ivl(self):
        m = self.int(0)
        out = []
        for _ in range(m):
            a, b = self.int(), self.int()
            if a > b or (out and out[-1][1] + 1 >= a):
                raise Reject("C0_INTERVAL_FORM")
            out.append((a, b))
        return out


def member(ivs, t):
    i = bisect.bisect_right(ivs, (t, 1 << 64)) - 1
    return i >= 0 and ivs[i][0] <= t <= ivs[i][1]


def subtract(a, b):
    """a minus b, both normalised lists."""
    out, k = [], 0
    for lo, hi in a:
        cur = lo
        while k < len(b) and b[k][1] < cur:
            k += 1
        q = k
        while q < len(b) and b[q][0] <= hi:
            if b[q][0] > cur:
                out.append((cur, b[q][0] - 1))
            cur = max(cur, b[q][1] + 1)
            q += 1
        if cur <= hi:
            out.append((cur, hi))
    return out


def subset(a, b):
    """a ⊆ b."""
    k = 0
    for lo, hi in a:
        while k < len(b) and b[k][1] < lo:
            k += 1
        if k == len(b) or not (b[k][0] <= lo and hi <= b[k][1]):
            return False
    return True


def intersects(a, b):
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i][1] < b[j][0]:
            i += 1
        elif b[j][1] < a[i][0]:
            j += 1
        else:
            return True
    return False


BIND_FIELDS = ("I", "G", "A", "W", "Q")


def read_bind(tk, inst_start):
    """Format 2: END_INSTANCE directly followed by a newline; I covers text[inst_start : that newline + 1]."""
    end_tok = tk.spans[tk.i - 1][1]
    if end_tok >= len(tk.text) or tk.text[end_tok] != "\n":
        raise Reject("BIND_LAYOUT")
    inst_digest = hashlib.sha256(tk.text[inst_start:end_tok + 1].encode("ascii")).hexdigest()
    tk.word("BIND")
    got = {}
    for f in BIND_FIELDS:
        tk.word(f)
        ws = []
        for _ in range(8):
            v = tk.int()
            if not 0 <= v <= 0xFFFFFFFF:
                raise Reject("BIND_WORD_RANGE")
            ws.append(v)
        got[f] = "".join("%08x" % v for v in ws)
    tk.word("END_BIND")
    if got["I"] != inst_digest:
        raise Reject("BIND_INSTANCE_DIGEST")
    return got


def check(text, expect=None):
    """Returns (claim, T, binding); binding is None for format 1, else the BIND digests (hex) and whether --expect
    was checked."""
    tk = Tokens(text)
    tk.word("WFGC"); version = tk.int(1, 2); tk.word("INSTANCE")
    inst_start = tk.spans[tk.i - 1][0]
    tk.word("V"); nV = tk.int(1); tk.word("E"); nE = tk.int(0)
    tk.word("DEP"); dep = tk.int(0); tk.word("HOR"); H = tk.int(dep)
    tk.word("ORIGIN"); origin = tk.int(0, nV - 1); tk.word("START"); s0 = tk.int(0, nE)
    tk.word("EDGES")
    tail, head, D = [], [], []
    for _ in range(nE):
        tail.append(tk.int(0, nV - 1)); head.append(tk.int(0, nV - 1)); D.append(tk.int(1))
    if s0 < nE and head[s0] != origin:
        raise Reject("START_HEAD")
    hd = head + [origin]
    tk.word("WAITABLE")
    waitable = [False] * nV
    prev = -1
    for _ in range(tk.int(0)):
        n = tk.int(0, nV - 1)
        if n <= prev:
            raise Reject("WAITABLE_ORDER")
        waitable[n] = True; prev = n
    tk.word("FORBID")
    forbid = set(); prevp = None
    for _ in range(tk.int(0)):
        p = (tk.int(0, nE), tk.int(0, nE - 1))
        if prevp is not None and p <= prevp:
            raise Reject("FORBID_ORDER")
        forbid.add(p); prevp = p
    tables = {}
    for key, size in (("EB", nE), ("WB", nV), ("AC", nV)):
        tk.word(key)
        tab, prev = {}, -1
        for _ in range(tk.int(0)):
            k = tk.int(0, size - 1)
            if k <= prev:
                raise Reject(key + "_ORDER")
            tab[k] = tk.ivl(); prev = k
        tables[key] = tab
    EB, WB, AC = tables["EB"], tables["WB"], tables["AC"]
    tk.word("END_INSTANCE")
    bind = read_bind(tk, inst_start) if version == 2 else None
    if expect is not None:
        if bind is None:
            raise Reject("BIND_MISSING")
        for f in ("G", "A", "W", "Q"):
            if bind[f] != expect[f]:
                raise Reject("BIND_" + f)
    tk.word("CLAIM")
    claim = tk.word()
    if claim == "ROUTE":
        claimed_T = tk.int(dep, H)
    elif claim == "NO_ROUTE":
        claimed_T = H + 1
    else:
        raise Reject("CLAIM_KIND")
    tk.word("WITNESS")
    legs = []
    for _ in range(tk.int(0)):
        kind = tk.word()
        if kind not in ("E", "W"):
            raise Reject("LEG_KIND")
        legs.append((kind, tk.int(), tk.int(), tk.int()))
    form = tk.word()
    if form not in ("CERT", "COCERT"):
        raise Reject("EXPECTED_CERT")
    T = tk.int()
    if T != claimed_T:
        raise Reject("THRESHOLD_MISMATCH")
    R, A, prev = {}, {}, -1
    lim = min(H, T - 1)
    for _ in range(tk.int(0)):
        s = tk.int(0, nE)
        if s <= prev:
            raise Reject("CERT_ORDER")
        R[s] = tk.ivl(); A[s] = tk.ivl(); prev = s
        hi_bound = H if form == "CERT" else lim
        for ivs in (R[s], A[s]):
            if ivs and (ivs[0][0] < dep or ivs[-1][1] > hi_bound):
                raise Reject("C0_BOUNDS")
        if form == "CERT" and not subset(A[s], R[s]):
            raise Reject("C0_A_NOT_IN_R")
        if form == "COCERT" and not subset(R[s], A[s]):   # NR ⊆ NA  <=>  A ⊆ R
            raise Reject("C0_A_NOT_IN_R")
    if form == "COCERT":
        full = [(dep, lim)] if dep <= lim else []
        R = {s: subtract(full, R[s]) if s in R else list(full) for s in range(nE + 1)}
        A = {s: subtract(full, A[s]) if s in A else list(full) for s in range(nE + 1)}
    tk.word("END")
    if tk.i != len(tk.t):
        raise Reject("TRAILING")

    # ---- witness (route claims only)
    if claim == "NO_ROUTE":
        if legs:
            raise Reject("NO_ROUTE_WITH_WITNESS")
    else:
        s, t, admitted = s0, dep, True
        for kind, x, a, b in legs:
            if a != t:
                raise Reject("W_CONTIGUITY")
            if kind == "E":
                if not 0 <= x < nE or tail[x] != hd[s] or (s, x) in forbid:
                    raise Reject("W_EDGE_LEGALITY")
                if member(EB.get(x, []), a) or b != a + D[x] or b > H:
                    raise Reject("W_EDGE_TIME")
                s, admitted = x, True
            else:
                if not 0 <= x < nV or x != hd[s] or not waitable[x]:
                    raise Reject("W_WAIT_LEGALITY")
                if member(WB.get(x, []), a) or b != a + 1 or b > H:
                    raise Reject("W_WAIT_TIME")
                admitted = False
            t = b
        if not admitted or t != claimed_T or not member(AC.get(hd[s], []), t):
            raise Reject("W_GOAL")

    # ---- certificate C1..C4
    lim = min(H, T - 1)
    if dep <= lim and not member(A.get(s0, []), dep):
        raise Reject("C1_INIT")
    out_edges = [[] for _ in range(nV)]
    for j in range(nE):
        out_edges[tail[j]].append(j)
    for s, Rs in R.items():
        n = hd[s]
        for j in out_edges[n]:
            if (s, j) in forbid:
                continue
            Dj = D[j]
            free = subtract([(a, min(b, lim - Dj)) for a, b in Rs if a <= lim - Dj], EB.get(j, []))
            if not subset([(a + Dj, b + Dj) for a, b in free], A.get(j, [])):
                raise Reject("C2_EDGE_CLOSURE")
        if waitable[n]:
            wb = WB.get(n, [])
            for a, b in Rs:
                if b + 1 <= lim and not member(wb, b):
                    raise Reject("C3_WAIT_CLOSURE")
    for s, As in A.items():
        if intersects([(a, min(b, lim)) for a, b in As if a <= lim], AC.get(hd[s], [])):
            raise Reject("C4_GOAL_REACHED")
    return claim, T, (None if bind is None else dict(bind, bound=expect is not None))


def parse_expect(arg):
    """G=<64 hex>,A=<64 hex>,W=<64 hex>,Q=<64 hex>, exactly this order, lowercase hex; None if malformed."""
    m = re.fullmatch(r"G=([0-9a-f]{64}),A=([0-9a-f]{64}),W=([0-9a-f]{64}),Q=([0-9a-f]{64})", arg)
    return None if m is None else dict(zip("GAWQ", m.groups()))


def main(argv):
    expect = None
    if len(argv) == 4 and argv[2] == "--expect":
        expect = parse_expect(argv[3])
        if expect is None:
            print("REJECT BAD_EXPECT")
            return 2
    elif len(argv) != 2:
        print("usage: check_py.py FILE [--expect G=..,A=..,W=..,Q=..]", file=sys.stderr)
        return 2
    try:
        text = sys.stdin.read() if argv[1] == "-" else open(argv[1], encoding="ascii", newline="").read()
    except (OSError, UnicodeDecodeError) as exc:
        print("REJECT IO:%s" % type(exc).__name__)
        return 2
    try:
        claim, T, bind = check(text, expect)
    except Reject as exc:
        print("REJECT %s" % exc)
        return 1
    if bind is None:
        print("ACCEPT %s %d" % (claim, T))
    elif bind["bound"]:
        print("ACCEPT %s %d LABELS_MATCH %s" % (claim, T, bind["I"][:16]))
    else:
        print("ACCEPT %s %d UNBOUND" % (claim, T))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
