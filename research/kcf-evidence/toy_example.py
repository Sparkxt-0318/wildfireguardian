"""Worked 6-node toy for ALGORITHM_APPENDIX.md. Runs the repository's own deadline_field.core.backward and the
independent brute-force oracle (deadline_field/bruteforce.py) on the same instance and prints every table quoted in the
appendix.  Run from research/harness-2026-11/F-3.1:  python3 ../kcf-evidence/toy_example.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "harness-2026-11" / "F-3.1"))
from deadline_field.core import Instance, backward, issue_set, check_fixed_point
from deadline_field.bruteforce import Oracle

H = 60
# nodes 0..5 ; origin 0, shelter 5 (dwell 5 s) ; node 4 is NOT waitable
#            e0   e1   e2   e3   e4   e5   e6
tail  = [0,   1,   0,   2,   3,   1,   4]
head  = [1,   5,   2,   3,   5,   4,   5]
D     = [10,  10,  15,  15,  15,  5,   8]
names = ["0>1", "1>5", "0>2", "2>3", "3>5", "1>4", "4>5"]
B = [[], [(18, 60)], [], [], [], [], [(14, 40)]]            # flame contact: edge start seconds that are blocked
A = [[], [(0, 55)], [], [], [(0, 55)], [], [(0, 55)]]       # arrival over an edge into node 5 accepted if t+5 <= H
waitable = [False] * 6
inst = Instance(H=H, n_nodes=6, tail=tail, head=head, D=D, waitable=waitable, B=B, A=A)
fld = backward(inst)
print("edge  R (standing at head, admission false)   G = R u A")
for j in range(7):
    print(f"{names[j]:>4}  R={fld.R[j]}  G={fld.G[j]}")
S = issue_set(fld, 0)
print("origin 0 feasible departures:", S, " deadline LD =", max(hi for lo, hi in S))
print("fixed-point certificate:", check_fixed_point(fld))
raw = dict(H=H, n_nodes=6, tail=tail, head=head, D=D, waitable=waitable, forbidden=[], B=B, W=[[]] * 6, A=A, IB={})
orc = Oracle(raw)
bf = {t: orc.earliest(0, t) for t in range(H + 1)}
feas = [t for t, a in bf.items() if a is not None]
print("oracle feasible departures:", feas)
S_set = {t for lo, hi in S for t in range(lo, hi + 1)}
print("agree at every second 0..60:", S_set == set(feas))
for t in (10, 11, 25, 26, 32, 33):
    print("depart", t, "-> earliest arrival", bf[t])
