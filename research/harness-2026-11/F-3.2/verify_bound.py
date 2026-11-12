"""Consumer-side verification of a format-2 certificate bundle (BINDING_RULE.md rev 2.2, "fully bound").

The consumer holds its OWN graph, packet and request. This tool runs every step and prints one verdict line:

  R2+R3  both checkers with --expect = bind_digests(own inputs): both must print ACCEPT ... LABELS_MATCH <I16>
         (this checks only the generator's labels; it does not prove the instance is the right one);
  T7(a)  structure of the instance parsed from the bundle's own bytes, against the consumer's graph and request:
         V, E, tail/head/D per edge, WAITABLE, FORBID, ORIGIN, START, DEP, HOR (O2 never re-derives these);
  T7(b)  O2: derive_instance.derive(own graph, own request, routable ContactModel of own packet) against the parsed
         instance, compare_semantic, 0 differences.

Output: `FULLY_BOUND <claim> <T> <I16>` (exit 0) only if all steps pass; else `NOT_BOUND <step>: <detail>` (exit 1).
Usage: python verify_bound.py BUNDLE --graph G.json --packet DIR --request R.json [--c-checker PATH] [--json]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bind_digests  # noqa: E402
import derive_instance  # noqa: E402
from p1_check import routable_contact_model  # noqa: E402

C_BIN = HERE / "checker_c" / "wfgc_check"


def instance_span(text):
    a = text.index("INSTANCE")
    return a, text.index("END_INSTANCE\n", a) + len("END_INSTANCE\n")


def parse_instance(text):
    """Own minimal parser of the INSTANCE section (the bytes hashed into I); used only for T7."""
    a, b = instance_span(text)
    t = text[a:b].split()
    i = 0

    def w(expected=None):
        nonlocal i
        x = t[i]; i += 1
        if expected is not None and x != expected:
            raise ValueError("expected %s got %s" % (expected, x))
        return x

    def n():
        return int(w())

    def ivl():
        m = n()
        return [(n(), n()) for _ in range(m)]

    w("INSTANCE"); w("V"); nV = n(); w("E"); nE = n()
    w("DEP"); dep = n(); w("HOR"); H = n(); w("ORIGIN"); origin = n(); w("START"); s0 = n()
    w("EDGES")
    tail, head, D = [], [], []
    for _ in range(nE):
        tail.append(n()); head.append(n()); D.append(n())
    w("WAITABLE"); wait = [n() for _ in range(n())]
    w("FORBID"); k = n(); forbid = {(n(), n()) for _ in range(k)}
    tabs = {}
    for key in ("EB", "WB", "AC"):
        w(key); tabs[key] = {}
        for _ in range(n()):
            r = n(); tabs[key][r] = ivl()
    w("END_INSTANCE")
    waitable = [False] * nV
    for x in wait:
        waitable[x] = True
    return SimpleNamespace(n_nodes=nV, E=nE, departure=dep, horizon=H, origin=origin, start_state=s0, tail=tail,
                           head=head, D=D, waitable=waitable, forbidden=forbid, edge_block=tabs["EB"],
                           wait_block=tabs["WB"], accept=tabs["AC"])


def structure_diffs(inst, graph, request):
    """T7(a). DEP/HOR are compared by compare_semantic's CLOCK record as well; both are listed here for clarity."""
    nidx = {nd["id"]: i for i, nd in enumerate(graph["nodes"])}
    eidx = {e["id"]: j for j, e in enumerate(graph["edges"])}
    d = []
    if inst.n_nodes != len(graph["nodes"]) or inst.E != len(graph["edges"]):
        return [("SIZE", (inst.n_nodes, inst.E), (len(graph["nodes"]), len(graph["edges"])))]
    for j, e in enumerate(graph["edges"]):
        want = (nidx[e["u"]], nidx[e["v"]], int(e["travel_ticks"]))
        if (inst.tail[j], inst.head[j], inst.D[j]) != want:
            d.append(("EDGE", j, (inst.tail[j], inst.head[j], inst.D[j]), want))
    want_w = [bool(nd["waitable"]) for nd in graph["nodes"]]
    if inst.waitable != want_w:
        d.append(("WAITABLE", sum(a != b for a, b in zip(inst.waitable, want_w))))
    want_f = {(eidx[a], eidx[b]) for a, b in graph["forbidden_turns"] if a in eidx and b in eidx}
    if inst.forbidden != want_f:
        d.append(("FORBID", len(inst.forbidden ^ want_f)))
    if request["position"]["node"] not in nidx or inst.origin != nidx[request["position"]["node"]]:
        d.append(("ORIGIN", inst.origin))
    inc = request["incoming_edge"]
    if inst.start_state != (inst.E if inc is None else eidx.get(inc, -1)):
        d.append(("START", inst.start_state))
    from fractions import Fraction as F
    if (F(inst.departure), F(inst.horizon)) != (F(request["departure"]), F(request["horizon"])):
        d.append(("CLOCK", (inst.departure, inst.horizon), (request["departure"], request["horizon"])))
    return d


def run_checkers(bundle, dg, c_checker):
    out = {}
    for name, cmd in (("py", [sys.executable, str(HERE / "check_py.py")]), ("c", [str(c_checker)])):
        r = subprocess.run(cmd + [str(bundle), "--expect", bind_digests.expect_arg(dg)], capture_output=True, text=True)
        out[name] = [r.stdout.strip(), r.returncode]
    return out


def verify(bundle, graph_path, packet, request_path, c_checker=C_BIN):
    rec = {"bundle": str(bundle)}
    graph = json.loads(Path(graph_path).read_text())
    request = json.loads(Path(request_path).read_text())
    dg = bind_digests.digests(graph_path, packet, request_path)
    rec["digests"] = dg
    ch = run_checkers(bundle, dg, c_checker)
    rec["checkers"] = ch
    toks = {k: v[0].split() for k, v in ch.items()}
    if not all(v[1] == 0 and toks[k][:1] == ["ACCEPT"] and "LABELS_MATCH" in toks[k] for k, v in ch.items()):
        return dict(rec, verdict="NOT_BOUND", step="R2+R3", detail="py=%r c=%r" % (ch["py"][0], ch["c"][0]))
    if toks["py"] != toks["c"]:
        return dict(rec, verdict="NOT_BOUND", step="R2+R3", detail="checkers disagree")
    claim, T, I16 = toks["py"][1], int(toks["py"][2]), toks["py"][4]
    rec.update(claim=claim, T=T, I16=I16)
    inst = parse_instance(Path(bundle).read_text())
    sd = structure_diffs(inst, graph, request)
    rec["t7a_diffs"] = [list(map(str, x)) for x in sd[:20]]
    if sd:
        return dict(rec, verdict="NOT_BOUND", step="T7a", detail="%d structure differences, first %s" % (len(sd), sd[0][0]))
    model = routable_contact_model(packet)
    o2 = derive_instance.compare_semantic(inst, derive_instance.derive(graph, request, model.cell_intervals))
    rec["t7b_o2_diffs"] = len(o2)
    if o2:
        return dict(rec, verdict="NOT_BOUND", step="T7b", detail="%d O2 differences, first %s" % (len(o2), o2[0][0]))
    return dict(rec, verdict="FULLY_BOUND", step=None, detail=None)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--request", required=True)
    ap.add_argument("--c-checker", default=str(C_BIN))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = verify(a.bundle, a.graph, a.packet, a.request, a.c_checker)
    if a.json:
        print(json.dumps(r, indent=1))
    elif r["verdict"] == "FULLY_BOUND":
        print("FULLY_BOUND %s %d %s" % (r["claim"], r["T"], r["I16"]))
    else:
        print("NOT_BOUND %s: %s" % (r["step"], r["detail"]))
    return 0 if r["verdict"] == "FULLY_BOUND" else 1


if __name__ == "__main__":
    sys.exit(main())
