"""Applicable tests of Ronchi et al. 2023 (Natural Hazards 117:1493-1519), PROTOCOL.md §6 and amendment 2(d).

Each test is a synthetic instance run through the unchanged deadline-field core (research/harness-2026-11/F-3.1,
deadline_field.core: backward, issue_set, witness_greedy), the replay's acceptance rule (dwell 120 s before a shelter
cell closes, as replay.Region.accept) and the replay's closure rules (replay.closure_s, measured_arms.closure_s,
Region.cell_distance). PASS = result equals the hand calculation exactly (integer seconds).

Usage: python3 ronchi_tests.py OUT.json
"""
from __future__ import annotations

import json, math, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
sys.path.insert(0, str(ROOT / "research/kcf-replay"))
sys.path.insert(0, str(ROOT))
from deadline_field import core, intervals as iv  # noqa: E402
import replay as RP  # noqa: E402
import measured_arms as MA  # noqa: E402

DWELL = 120


def ticks(length_m, kmh):
    return int(round(length_m / (kmh / 3.6)))


def inst(H, edges, n, B=None, waitable=None):
    tail = [e[0] for e in edges]; head = [e[1] for e in edges]; D = [e[2] for e in edges]
    return core.Instance(H=H, n_nodes=n, tail=tail, head=head, D=D, waitable=waitable or [False] * n,
                         B=B or [[] for _ in edges])


def accept(H, b_shelter=None):
    acc = (0, H - DWELL)
    return iv.subtract(acc, [(max(b_shelter - DWELL, 0), H)]) if b_shelter is not None else [acc]


def field_to(I, shelter, b_shelter=None):
    I.A = [list(accept(I.H, b_shelter)) if I.head[j] == shelter else [] for j in range(len(I.tail))]
    return core.backward(I)


def ea(fld, o, t):
    w = core.witness_greedy(fld, o, t)
    return (w[0], [leg[1] for leg in w[1] if leg[0] == "EDGE"]) if w else (None, None)


def t1a():
    H = 3600
    d = ticks(1000, 50)                               # 1 km at 50 km/h
    I = inst(H, [(0, 1, d)], 2); f = field_to(I, 1)
    got = ea(f, 0, 0)[0]; exp = d
    S = core.issue_set(f, 0); exp_S = [(0, H - DWELL - d)]
    return {"geometry": "one road, 1000 m, one road type at 50 km/h, one vehicle departing at 0 s",
            "expected": {"arrival_s": exp, "departure_set": exp_S}, "got": {"arrival_s": got, "departure_set": S},
            "result": "PASS" if (got == exp and S == exp_S) else "FAIL"}


def t1b():
    H = 3600
    segs = [(1000, 50), (2000, 80), (500, 30)]
    d = [ticks(L, v) for L, v in segs]
    I = inst(H, [(0, 1, d[0]), (1, 2, d[1]), (2, 3, d[2])], 4); f = field_to(I, 3)
    got = ea(f, 0, 0)[0]; exp = sum(d)
    return {"geometry": "three road types in series: 1000 m at 50, 2000 m at 80, 500 m at 30 km/h",
            "expected": {"arrival_s": exp, "per_segment_s": d}, "got": {"arrival_s": got},
            "result": "PASS" if got == exp else "FAIL"}


def t12():
    H = 3600
    near, far = ticks(1000, 60), ticks(5000, 60)
    I = inst(H, [(0, 1, near), (0, 2, far)], 3)
    f = field_to(I, 2)                                # destination forced to the far shelter
    got, legs = ea(f, 0, 0)
    return {"geometry": "origin with a near shelter (1 km) and a far shelter (5 km) at 60 km/h; destination forced to far",
            "expected": {"arrival_s": far, "edges": [1]}, "got": {"arrival_s": got, "edges": legs},
            "result": "PASS" if (got == far and legs == [1]) else "FAIL"}


def wt1():
    H = 3600
    s1, s2 = ticks(2000, 60), ticks(4000, 60)        # short route via node 1, long via node 2, both to node 3
    I0 = [(0, 1, s1 // 2), (1, 3, s1 - s1 // 2), (0, 2, s2 // 2), (2, 3, s2 - s2 // 2)]
    bc = 600                                          # the short route's second road closes (fire) at 600 s
    B = [[], [(max(bc - I0[1][2], 0), H)], [], []]    # edge blocked for start t if t + D >= bc (whole-edge cell, z_end = 1)
    I = inst(H, I0, 4, B=B); f = field_to(I, 3)
    # hand calculation: departing at t, the short route reaches the closing road at t + s1//2 and must leave it before
    # bc: t + s1 < bc  ->  t <= bc - s1 - 1; after that only the long route
    t_last_short = bc - s1 - 1
    a1, l1 = ea(f, 0, t_last_short); a2, l2 = ea(f, 0, t_last_short + 1)
    S = core.issue_set(f, 0)
    exp = {"short_until_s": t_last_short, "arrival_short": t_last_short + s1, "arrival_long_after": t_last_short + 1 + s2,
           "departure_set": [(0, H - DWELL - s2)]}
    got = {"arrival_at_last_short": a1, "edges_at_last_short": l1, "arrival_after": a2, "edges_after": l2,
           "departure_set": S}
    ok = (a1 == exp["arrival_short"] and l1 == [0, 1] and a2 == exp["arrival_long_after"] and l2 == [2, 3]
          and S == exp["departure_set"])
    return {"geometry": "two routes (2 km, 4 km at 60 km/h); the short route's second road is lost to fire at 600 s",
            "expected": exp, "got": got, "result": "PASS" if ok else "FAIL"}


def wt3():
    H = 3600
    d1, d2 = ticks(1500, 60), ticks(6000, 60)
    b1 = 1000                                         # shelter 1's cell closes at 1000 s
    I = inst(H, [(0, 1, d1), (0, 2, d2)], 3)
    f1 = field_to(I, 1, b_shelter=b1)
    S1 = core.issue_set(f1, 0)
    I2 = inst(H, [(0, 1, d1), (0, 2, d2)], 3); f2 = field_to(I2, 2)
    S2 = core.issue_set(f2, 0)
    # hand: shelter 1 accepts arrival a with a + DWELL < b1 -> a <= b1 - DWELL - 1; departure <= that - d1
    exp1 = [(0, b1 - DWELL - 1 - d1)]
    exp2 = [(0, H - DWELL - d2)]
    union = iv.normalize(S1 + S2)
    ok = S1 == exp1 and S2 == exp2 and union == [(0, H - DWELL - d2)]
    return {"geometry": "two shelters (1.5 km, 6 km at 60 km/h); shelter 1 lost (its cell closes at 1000 s, 120 s dwell)",
            "expected": {"shelter1_set": exp1, "shelter2_set": exp2}, "got": {"shelter1_set": S1, "shelter2_set": S2,
                                                                           "union": union},
            "result": "PASS" if ok else "FAIL"}


def b1():
    """Homogeneous, isotropic: ignition at the map midpoint, communities at the four quadrant midpoints."""
    res, W = 375.0, 81                                # 30.375 km square of 375 m cells
    cx = np.array([(c % W + 0.5) * res for c in range(W * W)]); cy = np.array([(c // W + 0.5) * res for c in range(W * W)])
    mid = W * res / 2
    disc = [{"x": mid, "y": mid, "r_m": 0.0, "t": 0}]
    d = RP.Region.cell_distance(SimpleNamespace(cxy=(cx, cy)), disc, 1)
    q = W * res / 4
    comm = [(mid - q, mid - q), (mid + q, mid - q), (mid - q, mid + q), (mid + q, mid + q)]
    cells = [int(y // res) * W + int(x // res) for x, y in comm]
    out = {}
    ok = True
    for arm in ("ORDINARY", "RUNNING", "WORST"):
        t = [RP.closure_s(arm, float(d[c])) for c in cells]
        a, v = RP.STANDINS[arm]
        exp = [max(0.0, math.hypot(cx[c] - mid, cy[c] - mid) - a) / v * 3600 for c in cells]
        good = all(abs(x - y) < 1e-6 for x, y in zip(t, exp)) and max(t) - min(t) < 1e-6
        ok &= good
        out[arm] = {"arrival_s": [round(x, 3) for x in t], "expected_s": [round(x, 3) for x in exp], "equal": good}
    for cls_ in ("quiet", "running"):
        r5, r8 = (x * 1000 for x in MA.R_KM[cls_])
        t = [MA.closure_s(r5, r8, float(d[c])) for c in cells]
        dist = [math.hypot(cx[c] - mid, cy[c] - mid) for c in cells]
        exp = [MA.closure_s(r5, r8, x) for x in dist]   # hand: piecewise curve (0,0)-(5 h,R5)-(8 h,R8); beyond R8 never
        good = len(set(t)) == 1 and t == exp           # exact equality (inf == inf allowed; harness fix, see RESULTS)
        ok &= good
        out["MEASURED:" + cls_] = {"arrival_s": [None if math.isinf(x) else round(x, 3) for x in t],
                                   "expected_s": [None if math.isinf(x) else round(x, 3) for x in exp],
                                   "R5_R8_m": [r5, r8], "distance_m": round(dist[0], 1), "equal": good}
    return {"geometry": "30.4 km square, 375 m cells, point ignition at the midpoint, one community at each quadrant "
                        "midpoint (10.6 km away); no fuel, wind or slope (the model has none)",
            "expected": "equal arrival at the four communities = distance / R (hand calculation)", "got": out,
            "result": "PASS" if ok else "FAIL"}


def t14_reduced():
    H = 3600
    a, b = ticks(4000, 120), ticks(2000, 30)
    I = inst(H, [(0, 1, a), (0, 1, b)], 2); f = field_to(I, 1)
    got, legs = ea(f, 0, 0)
    return {"geometry": "single vehicle; two routes 4000 m at 120 km/h and 2000 m at 30 km/h (T.14 main-text geometry, no traffic)",
            "expected": {"arrival_s": a, "edges": [0]}, "got": {"arrival_s": got, "edges": legs},
            "result": "PASS" if (got == a and legs == [0]) else "FAIL", "counts_as_T14": False,
            "note": "paper's WUI-NITY expected 122 s includes its own traffic-model assumptions; not comparable"}


NA = {
    "P.1": "pedestrian re-distribution: no pedestrians", "P.2": "vehicles per household: no households or vehicle allocation",
    "P.3": "response curve: no pre-evacuation behaviour", "P.4": "pedestrian walking speed: no pedestrians",
    "PT.1": "pedestrian distance to vehicles: no pedestrians", "T.2": "background traffic: no traffic",
    "T.3": "carriageway configuration: no lanes or capacity", "T.4": "speed-density / flow-density: no traffic flow",
    "T.5": "speed reduction in reduced visibility: travel times fixed, no smoke/visibility model",
    "T.6": "flow at destination: no flow", "T.7": "group evacuation: single vehicles only",
    "T.8": "lane changing / overtaking: no lanes", "T.9": "acceleration / deceleration: constant edge travel times",
    "T.10": "road crash: no incidents", "T.11": "intersection: no intersection delay or conflict model",
    "T.13": "destination choice in traffic: no traffic", "T.14": "route choice in traffic: no traffic (single-vehicle reduction run separately)",
    "T.15": "vehicle demand vs arrival distribution: no demand model", "WT.2": "lane reversal: no lanes",
    "WT.4": "refuge capacity: shelters have no capacity", "B.2": "fuel types: no fuel input", "B.3": "wind: no wind direction (isotropic reach)",
    "B.4": "valley: no slope input", "B.5": "heterogeneous: no fuel or terrain input",
}


def main(out):
    tests = {"T.1a": t1a(), "T.1b": t1b(), "T.12": t12(), "WT.1": wt1(), "WT.3": wt3(), "B.1": b1()}
    res = {"paper": "Ronchi E, Wahlqvist J, Ardinge A, et al. The verification of wildland-urban interface fire evacuation "
                    "models. Natural Hazards 117(2):1493-1519 (2023). doi:10.1007/s11069-023-05913-2",
           "applicable": tests, "not_applicable": NA, "extra_T14_single_vehicle_reduction": t14_reduced()}
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    for k, v in tests.items():
        print(k, v["result"])
    print("T.14 reduced", res["extra_T14_single_vehicle_reduction"]["result"], "| N/A:", len(NA))


if __name__ == "__main__":
    main(sys.argv[1])
