"""T8 and T9 (BINDING_RULE.md rev 2.1): no instance-relevant input escapes Q or A.

T8 request projection: for each panel request, mutate one field at a time (every top-level key, every destination
subfield). Pass iff Q changes, OR build_instance's instance text is byte-identical to the unmutated one, OR
build_instance refuses the mutated request. The at-issue inputs (budgets.dose, incurred) are in Q by definition and
are checked for "Q changes".

T9 routed hazard: on one packet per region, mutate a copy of the packet one thing at a time.
- Every npz key outside A, and every REPORT.json leaf outside A's three fields (sampled deterministically), is
  perturbed: pass iff A changes OR the routed ContactModel is identical (build_instance depends on the packet only
  through it: shape, T, R, current cells, per-member events, ids) OR loading refuses.
- Each A key (ignition_time_s, current_active, support, marker) perturbed or added/removed: A must change.
- Re-zipping the npz (new zip timestamps) and editing an absolute path string in REPORT.json: A must NOT change.

Usage: python xcheck/bind_completeness.py --summary FILE [--max-report-leaves N]
"""
import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
F32 = HERE.parent
sys.path.insert(0, str(F32))
import bind_digests as BD  # noqa: E402
import cases  # noqa: E402
import generate  # noqa: E402
from p1_check import routable_contact_model  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402


def q_of(req):
    return hashlib.sha256(BD.canonical(BD.q_projection(req))).hexdigest()


def a_of(packet):
    return hashlib.sha256(BD.canonical(BD.a_projection(packet))).hexdigest()


def inst_sha(graph, req, model):
    try:
        inst, _ = build_instance(graph, req, model)
    except Exception as exc:  # a refused request is an acceptable outcome
        return "REFUSED:" + type(exc).__name__
    return hashlib.sha256(generate.instance_text(inst).encode()).hexdigest()


def request_mutations(req, graph):
    """(name, mutated request) pairs: one change each."""
    nodes = [n["id"] for n in graph["nodes"]]
    other_node = lambda cur: next(n for n in nodes if n != cur)  # noqa: E731
    edge0 = graph["edges"][0]["id"]
    out = []

    def m(name, fn):
        r = copy.deepcopy(req); fn(r); out.append((name, r))

    for k in list(req):
        m("delete:" + k, lambda r, k=k: r.pop(k))
    m("position.node", lambda r: r["position"].__setitem__("node", other_node(r["position"]["node"])))
    m("incoming_edge", lambda r: r.__setitem__("incoming_edge", edge0 if r["incoming_edge"] is None else None))
    m("departure+1", lambda r: r.__setitem__("departure", r["departure"] + 1))
    m("horizon-1", lambda r: r.__setitem__("horizon", r["horizon"] - 1))
    for i in range(len(req.get("destinations", []))):
        m("dest%d.node" % i, lambda r, i=i: r["destinations"][i].__setitem__("node", other_node(r["destinations"][i]["node"])))
        m("dest%d.dwell+1" % i, lambda r, i=i: r["destinations"][i].__setitem__("dwell", r["destinations"][i]["dwell"] + 1))
        m("dest%d.open_hi-60" % i, lambda r, i=i: r["destinations"][i]["open_intervals"][0].__setitem__(
            1, r["destinations"][i]["open_intervals"][0][1] - 60))
        m("dest%d.open_lo+60" % i, lambda r, i=i: r["destinations"][i]["open_intervals"][0].__setitem__(
            0, r["destinations"][i]["open_intervals"][0][0] + 60))
        m("dest%d.extra_key" % i, lambda r, i=i: r["destinations"][i].__setitem__("note", "x"))
    m("destinations.append", lambda r: r["destinations"].append(copy.deepcopy(r["destinations"][0]) | {"node": other_node(r["destinations"][0]["node"])}))
    k0 = next(iter(req.get("incurred", {})), None)
    if k0 is not None:
        m("incurred*2", lambda r: r["incurred"].__setitem__(k0, r["incurred"][k0] * 2 + 1))
        m("budgets.dose/2", lambda r: r["budgets"]["dose"].__setitem__(k0, r["budgets"]["dose"][k0] / 2))
    m("budgets.peak+1", lambda r: r["budgets"].__setitem__("peak", r["budgets"]["peak"] + 1))
    for k, v in (("hazard_version", 99), ("as_of", "2000-01-01T00:00:00+00:00"), ("objective", "x"),
                 ("exposure_scope", "x"), ("solver", "x")):
        m("set:" + k, lambda r, k=k, v=v: r.__setitem__(k, v))
    m("limits.wall_s+1", lambda r: r["limits"].__setitem__("wall_s", r["limits"]["wall_s"] + 1))
    m("extra_top_key", lambda r: r.__setitem__("note", "x"))
    return out


def t8(case_list):
    rows = []
    for c in case_list:
        graph = json.loads(Path(c["graph"]).read_text())
        req = json.loads(Path(c["request"]).read_text())
        model = routable_contact_model(c["packet"])
        q0, s0 = q_of(req), inst_sha(graph, req, model)
        for name, r in request_mutations(req, graph):
            q1 = q_of(r)
            s1 = inst_sha(graph, r, model)
            at_issue_field = name.startswith(("incurred", "budgets.dose", "delete:incurred", "delete:budgets"))
            ok = (q1 != q0) or (s1 == s0) or s1.startswith("REFUSED")
            if at_issue_field:
                ok = q1 != q0
            rows.append(dict(mission=c["mission"], mutation=name, Q_changed=q1 != q0,
                             instance_identical=s1 == s0, refused=s1.startswith("REFUSED"), ok=ok))
    return rows


def model_key(m):
    return (tuple(m.shape), str(m.T), str(m.R), tuple(sorted(m.current)),
            tuple(tuple(sorted((k, str(v)) for k, v in ev.items())) for ev in m.events), tuple(m.ids))


def load_model(p):
    try:
        return model_key(routable_contact_model(p))
    except Exception as exc:
        return "REFUSED:" + type(exc).__name__


def rewrite_npz(src_npz, dst_npz, arrays):
    np.savez(dst_npz, **arrays)


def leaves(x, path=()):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from leaves(v, path + (i,))
    else:
        yield path, x


def set_path(x, path, v):
    for p in path[:-1]:
        x = x[p]
    x[path[-1]] = v


A_REPORT = {("native_metadata", "construction", "assumptions", "burning_duration_s"),
            ("native_metadata", "construction", "assumptions", "initial_remaining_s")}


def t9(packets, max_leaves):
    rows = []
    for pk in packets:
        pk = Path(pk)
        a0, m0 = a_of(pk), load_model(pk)
        with np.load(pk / "constructed_arrays.npz", allow_pickle=False) as z:
            arrays = {k: z[k].copy() for k in z.files}
        report = json.loads((pk / "REPORT.json").read_text())
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / pk.name

            def fresh():
                if work.exists():
                    shutil.rmtree(work)
                shutil.copytree(pk, work)

            def rec(kind, name, expect_a_change=None):
                a1, m1 = a_of(work), load_model(work)
                changed = a1 != a0
                if expect_a_change is True:
                    ok = changed
                elif expect_a_change is False:
                    ok = not changed
                else:
                    ok = changed or m1 == m0 or str(m1).startswith("REFUSED")
                rows.append(dict(packet=pk.name, kind=kind, name=name, A_changed=changed,
                                 model_identical=m1 == m0, refused=str(m1).startswith("REFUSED"), ok=ok))

            # npz keys: perturb one element of each array
            for k in arrays:
                fresh()
                arr = {kk: v.copy() for kk, v in arrays.items()}
                x = arr[k].reshape(-1)
                if x.size == 0:
                    continue
                if x.dtype.kind == "b":
                    x[0] = not x[0]
                elif x.dtype.kind == "f":
                    i = int(np.flatnonzero(np.isfinite(x))[0]) if np.isfinite(x).any() else 0
                    x[i] = (x[i] + 1.0) if np.isfinite(x[i]) else 1.0
                else:
                    x[0] = x[0] + 1
                rewrite_npz(pk / "constructed_arrays.npz", work / "constructed_arrays.npz", arr)
                rec("npz", k, True if k in BD.A_NPZ_KEYS else None)
            # A keys added / removed
            for k in ("support", "per_cell_law_HAZARD_only"):
                fresh()
                arr = {kk: v.copy() for kk, v in arrays.items()}
                if k in arr:
                    arr.pop(k)
                else:
                    arr[k] = np.zeros(arrays["current_active"].shape, dtype=bool)
                rewrite_npz(pk / "constructed_arrays.npz", work / "constructed_arrays.npz", arr)
                rec("npz_add_remove", k, True)
            # re-zip: same arrays, new zip timestamps -> A unchanged
            fresh(); time.sleep(2.1)
            rewrite_npz(pk / "constructed_arrays.npz", work / "constructed_arrays.npz", arrays)
            raw_changed = hashlib.sha256((work / "constructed_arrays.npz").read_bytes()).hexdigest() != \
                hashlib.sha256((pk / "constructed_arrays.npz").read_bytes()).hexdigest()
            rec("rezip", "constructed_arrays.npz (raw bytes changed: %s)" % raw_changed, False)
            # REPORT leaves
            lv = list(leaves(report))
            step = max(1, len(lv) // max_leaves)
            chosen = [lv[i] for i in range(0, len(lv), step)][:max_leaves]
            chosen += [x for x in lv if tuple(x[0]) in A_REPORT and x not in chosen]
            for path, v in chosen:
                fresh()
                r = copy.deepcopy(report)
                if isinstance(v, bool):
                    nv = not v
                elif isinstance(v, (int, float)):
                    nv = v + 1
                elif isinstance(v, str):
                    nv = v + "x"
                elif v is None:
                    nv = 0
                else:
                    continue
                set_path(r, path, nv)
                (work / "REPORT.json").write_text(json.dumps(r))
                rec("report", "/".join(map(str, path)), True if tuple(path) in A_REPORT else None)
            # member ids (rows[0].request.incurred keys): renaming one must change A
            fresh()
            r = copy.deepcopy(report)
            inc = r["rows"][0]["request"]["incurred"]
            k0 = next(iter(inc)); inc["renamed"] = inc.pop(k0)
            (work / "REPORT.json").write_text(json.dumps(r))
            rec("report", "member id renamed", True)
            # absolute-path edit in REPORT -> A unchanged
            fresh()
            r = copy.deepcopy(report)
            paths = [(p, v) for p, v in leaves(r) if isinstance(v, str) and v.startswith("/")]
            if paths:
                set_path(r, paths[0][0], "/elsewhere" + paths[0][1])
                (work / "REPORT.json").write_text(json.dumps(r))
                rec("report_path", "/".join(map(str, paths[0][0])), False)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--max-report-leaves", type=int, default=60)
    ap.add_argument("--skip-t8", action="store_true")
    a = ap.parse_args()
    cs = cases.korean_cases()
    r8 = [] if a.skip_t8 else t8(cs)
    seen, pks = set(), []
    for c in cs:
        if c["region"] not in seen:
            seen.add(c["region"]); pks.append(c["packet"])
    r9 = t9(pks, a.max_report_leaves)
    s = dict(rule="BINDING_RULE.md rev 2.1",
             t8_cases=len(r8), t8_ok=sum(r["ok"] for r in r8), t8_failures=[r for r in r8 if not r["ok"]],
             t9_cases=len(r9), t9_ok=sum(r["ok"] for r in r9), t9_failures=[r for r in r9 if not r["ok"]],
             t9_packets=[Path(p).name for p in pks], t8=r8, t9=r9)
    Path(a.summary).write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps({k: v for k, v in s.items() if k not in ("t8", "t9")}, indent=1))


if __name__ == "__main__":
    main()
