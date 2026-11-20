"""Cross-check of the failed-evacuation verdicts of score.py with the independent route checker of
research/kcf-theorem/checker.py (PROTOCOL.md section 5.1), on a seeded sample of advised journeys.

The checker expands closure intervals to sets of seconds, so each journey gets a restricted instance: the full edge
list (tail, head, D), the full turn restrictions, and the truth closures only on the edges, wait nodes, origin and
final edge the journey uses (the only ones check_route reads).

    python3 research/kcf-robust/tests/check_failed.py OUT [twin|replay ...]
"""
import csv
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib  # noqa: E402
from score import Truth  # noqa: E402

sys.path.insert(0, str(lib.REPO / "research/kcf-theorem"))
import checker  # noqa: E402

PER_EXPERIMENT = 300


def journeys(out, kind):
    sub = "twin" if kind == "twin" else "replay"
    rows = [r for r in csv.DictReader(open(out / ("%s_rule_places.csv" % kind))) if r["advised"] == "True"]
    rng = random.Random(20261119)
    failed = [r for r in rows if r["failed"] == "True"]
    ok = [r for r in rows if r["failed"] != "True"]
    pick = rng.sample(failed, min(len(failed), PER_EXPERIMENT // 2))
    pick += rng.sample(ok, min(len(ok), PER_EXPERIMENT - len(pick)))
    pick.sort(key=lambda r: (r["tag"], r["rule"], r["place"]))
    cache = {}
    for r in pick:
        tag = r["tag"]
        if tag not in cache:
            res = json.loads((out / sub / (tag + ".json")).read_text())
            bc = json.loads((out / sub / (tag + "_bc.json")).read_text())
            rules = dict(res["rules"])
            rules.update(bc["rules"])
            rid = res.get("rid", "yeongdeok_2025")
            cache = {tag: (rid, rules, res["close_s"]["truth"])}
        rid, rules, close = cache[tag]
        yield r, rid, rules[r["rule"]][r["place"]], close


def restricted(road, tr, origin_node, x):
    legs = x["legs"]
    edges = [[road.tail[j], road.head[j], road.D[j]] for j in range(len(road.tail))]
    B, W = {}, {}
    for kind, i, s, e in legs:
        if kind == "EDGE":
            B[i] = [list(v) for v in tr.inst.B[i]]
        else:
            W[i] = [list(v) for v in tr.inst.W[i]]
    last = [i for kind, i, s, e in legs if kind == "EDGE"][-1]
    acc = tr.accept(x["shelter_node"])
    from wfg_roadlayer import engine
    ib = engine.origin_closure(road, tr.close, origin_node, tr.H)
    return {"H": tr.H, "edges": edges, "waitable": [v for v in range(len(road.waitable)) if road.waitable[v]],
            "forbidden": [list(p) for p in road.forbidden], "B": B, "W": W,
            "A": {last: [list(v) for v in acc]}, "IB": {origin_node: [list(v) for v in ib]}}


def main(out, kinds):
    out = Path(out)
    report = {}
    for kind in kinds:
        n = agree = 0
        bad = []
        trs = {}
        for r, rid, x, close in journeys(out, kind):
            key = (r["tag"],)
            if key not in trs:
                trs = {key: Truth(rid, close)}
            tr = trs[key]
            road = tr.road
            origin_node = {o["id"]: o["node"] for o in lib.region(rid).origins}[r["place"]]
            ok, why = checker.check_route(restricted(road, tr, origin_node, x), origin_node, x["L"], x["legs"])
            n += 1
            if ok == (r["failed"] != "True"):
                agree += 1
            else:
                bad.append({"tag": r["tag"], "place": r["place"], "rule": r["rule"], "score_failed": r["failed"], "checker": why})
        report[kind] = {"checked": n, "agree": agree, "disagreements": bad[:20]}
        print(kind, n, agree, flush=True)
    (out / "check_failed.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["twin", "replay"])
