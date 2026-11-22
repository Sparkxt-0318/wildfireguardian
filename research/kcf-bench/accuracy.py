"""Accuracy checks of BENCH_PLAN.md section 6. Untimed; run after the timed runs, one cache at a time.

    python3 research/kcf-bench/accuracy.py [--only <substring>] [--max-specs N]   # writes results/accuracy/<cache>.json

Inputs: results/answers/*.json (repeat 1 of FIELD, FIELD-D, MARGIN-1, MARGIN-10), results/old.jsonl (every OLD request).
(1) OLD against itself: repeats must give the same verdict and arrival on every case.
(2) a against b and c: every sample case OLD decides: FIELD, MARGIN at margin 0 (M = 0 pass here, and MARGIN-10 at margin 0);
    arrival too. Also against the recorded verdict.
(3) b against c at margin 0 on every case of the cache, and the issue set of every origin of every spec.
(4) c at non-zero margins against the existing field on the widened instance, on the specs of the sample cases:
    MARGIN-1 answers (margin 60) and MARGIN-10 answers (all ten margins).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import CACHES, HERE, MARGIN_ONE, MARGINS_TEN, add_paths, load_cases, packet_paths, specs_of

add_paths()
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from margin_field import field as mf  # noqa: E402
from margin_field import pl  # noqa: E402

RES = HERE / "results"


def listed(lst, rec, cap=25):
    if len(lst) < cap:
        lst.append(rec)


def old_rows(cache):
    rows = defaultdict(list)
    p = RES / "old.jsonl"
    if p.exists():
        for l in p.read_text().splitlines():
            r = json.loads(l)
            if r["cache"] == cache:
                rows[r["case"]].append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--max-specs", type=int)
    ap.add_argument("--results", default=str(HERE / "results"), help="results folder of one machine class")
    a = ap.parse_args()
    global RES
    RES = Path(a.results)
    (RES / "accuracy").mkdir(exist_ok=True)
    for cache in CACHES:
        if a.only and a.only not in cache:
            continue
        tag = cache.replace("/", "__")
        doc = load_cases(cache)
        cases = doc["cases"]
        sample = set(doc["sample"])
        ld = lambda m: json.loads((RES / "answers" / ("%s__%s.json" % (m, tag))).read_text())
        A = {m: ld(m) for m in ("field", "field_dec", "margin1", "margin10")}
        out = {"cache": cache, "n_cases": len(cases), "disagreements": defaultdict(list), "counts": Counter()}
        C, D = out["counts"], out["disagreements"]
        # ---- (1) OLD repeatability and decided cases
        rows = old_rows(cache)
        dec = {}
        for cid, rs in rows.items():
            vs = {r["verdict"] for r in rs}
            arr = {r["arrival"] for r in rs if r["verdict"] == "checked_route"}
            C["old_cases"] += 1
            C["old_requests"] += len(rs)
            if len(vs) > 1 or len(arr) > 1:
                C["old_unstable_cases"] += 1
                listed(D["old_unstable"], {"case": cid, "verdicts": sorted(vs), "arrivals": sorted(map(str, arr))})
            elif vs <= {"checked_route", "model_no_route"}:
                dec[cid] = (rs[0]["verdict"], rs[0]["arrival"])
            else:
                C["old_unresolved_cases"] += 1
                C["old_unresolved_" + (rs[0]["reason"] or "none")] += 1
        C["old_decided_cases"] = len(dec)
        # ---- (2) a against b and c at margin 0, and against the recorded verdict
        # (computed below together with (3), which needs the same M = 0 pass)
        graph_path, packet_dir = packet_paths(doc["region"], doc["input_time"])
        pm = PacketModel(graph_path, packet_dir)
        idx_of = {c["id"]: i for i, c in enumerate(cases)}
        specs = list(specs_of(cases).items())
        if a.max_specs:
            specs = specs[: a.max_specs]
        for (dn, dwell, win), idxs in specs:
            origins = sorted({cases[i]["start"] for i in idxs})
            inst = pm.instance("cert", [{"node": dn, "dwell": dwell, "window": list(win)}], origins)
            fld = backward(inst)
            fm0 = mf.margin_field(inst, 0)
            fa0 = mf.field_at(fm0, 0)
            sets_f = {o: issue_set(fld, pm.nidx[o]) for o in origins}
            sets_m = {o: mf.issue_set_at(fm0, pm.nidx[o], 0) for o in origins}
            for o in origins:
                C["origin_sets_b_vs_c0"] += 1
                if sets_f[o] != sets_m[o]:
                    C["origin_sets_b_vs_c0_MISMATCH"] += 1
                    listed(D["origin_sets"], {"origin": o, "dest": dn})
            for i in idxs:
                c = cases[i]
                o, t = c["start"], c["offset"]
                fb = iv.contains(sets_f[o], t)
                fc = iv.contains(sets_m[o], t)
                ab = witness(fld, pm.nidx[o], t)[0] if fb else None
                ac = witness(fa0, pm.nidx[o], t)[0] if fc else None
                C["cases_b_vs_c0"] += 1
                if fb != fc or ab != ac:
                    C["cases_b_vs_c0_MISMATCH"] += 1
                    listed(D["b_vs_c0"], {"case": c["id"], "b": [fb, ab], "c0": [fc, ac]})
                # saved timed-run answers equal what is recomputed here
                if A["field"]["feas"][i] != fb or A["field"]["arr"][i] != ab or A["field_dec"]["feas"][i] != fb:
                    C["saved_field_answers_MISMATCH"] += 1
                if A["margin10"]["feas10"][i][0] != fc:
                    C["saved_margin10_at0_MISMATCH"] += 1
                rv = c["rec_verdict"]
                if rv in ("checked_route", "model_no_route"):
                    C["recorded_decided"] += 1
                    ok = (fb == (rv == "checked_route")) and (not fb or ab == c["rec_arrival"])
                    ok_c = (fc == (rv == "checked_route")) and (not fc or ac == c["rec_arrival"])
                    C["recorded_vs_b_MISMATCH"] += not ok
                    C["recorded_vs_c0_MISMATCH"] += not ok_c
                if c["id"] in dec:
                    v, arr = dec[c["id"]]
                    C["a_vs_bc_cases"] += 1
                    okb = fb == (v == "checked_route") and (not fb or ab == arr)
                    okc = fc == (v == "checked_route") and (not fc or ac == arr)
                    C["a_vs_b_MISMATCH"] += not okb
                    C["a_vs_c0_MISMATCH"] += not okc
                    if not okb or not okc:
                        listed(D["a_vs_bc"], {"case": c["id"], "old": [v, arr], "b": [fb, ab], "c0": [fc, ac]})
            # ---- (4) non-zero margins against the existing field on the widened instance (specs of sample cases)
            if not any(cases[i]["id"] in sample for i in idxs):
                continue
            fm = mf.margin_field(inst, 600)
            fo = {o: mf.issue_margin(fm, pm.nidx[o]) for o in origins}
            for m in sorted(set(MARGINS_TEN) | {MARGIN_ONE}):
                if m == 0:
                    continue
                ref = backward(mf.widen(inst, m))
                fa_ref = None
                for o in origins:
                    want = issue_set(ref, pm.nidx[o])
                    got = pl.level_set(fo[o], m)
                    C["margin_origin_sets"] += 1
                    if got != want:
                        C["margin_origin_sets_MISMATCH"] += 1
                        listed(D["margin_origin_sets"], {"origin": o, "dest": dn, "m": m})
                for i in idxs:
                    c = cases[i]
                    o, t = c["start"], c["offset"]
                    wf = iv.contains(issue_set(ref, pm.nidx[o]), t)
                    if m in MARGINS_TEN:
                        k = MARGINS_TEN.index(m)
                        C["margin10_cases"] += 1
                        if A["margin10"]["feas10"][i][k] != wf:
                            C["margin10_cases_MISMATCH"] += 1
                            listed(D["margin10_cases"], {"case": c["id"], "m": m})
                    if m == MARGIN_ONE:
                        C["margin1_cases"] += 1
                        wa = witness(ref, pm.nidx[o], t)[0] if wf else None
                        if A["margin1"]["feas"][i] != wf or A["margin1"]["arr"][i] != wa:
                            C["margin1_cases_MISMATCH"] += 1
                            listed(D["margin1_cases"], {"case": c["id"], "m": m, "got": [A["margin1"]["feas"][i], A["margin1"]["arr"][i]], "want": [wf, wa]})
        # cases (not specs) where margin answers change relative to margin 0, descriptive
        out["answers_by_margin_all_cases"] = [sum(1 for x in A["margin10"]["feas10"] if x[k]) for k in range(10)]
        out["margins"] = MARGINS_TEN
        out["counts"], out["disagreements"] = dict(C), {k: v for k, v in D.items()}
        (RES / "accuracy" / (tag + ".json")).write_text(json.dumps(out, indent=1))
        print(cache, json.dumps({k: v for k, v in C.items() if "MISMATCH" in k or "unstable" in k or k.endswith("_cases")}), flush=True)


if __name__ == "__main__":
    main()
